# Implementation Plan: TQQQ 시뮬레이션 병렬처리 성능 최적화

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: Draft

---

**이 영역은 삭제/수정 금지**

**상태 옵션**: Draft / In Progress / Done

**Done 처리 규칙**:

- Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-01-30 (KST)
**마지막 업데이트**: 2026-01-30 (KST)
**관련 범위**: tqqq, utils
**관련 문서**: src/qbt/tqqq/CLAUDE.md, src/qbt/utils/CLAUDE.md, tests/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 이 영역은 삭제/수정 금지
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python validate_project.py`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] 목표 1: `simulate()` 함수의 Python for-loop를 numpy 벡터화로 대체하여 시뮬레이션 속도를 대폭 개선한다.
- [ ] 목표 2: 그리드 서치용 경량 RMSE 계산 함수를 생성하여 불필요한 메트릭 계산을 제거한다.
- [ ] 목표 3: expense_dict를 WORKER_CACHE에 사전 계산하여 매 후보 평가 시 반복 생성을 제거한다.
- [ ] 목표 4: 기존 외부 API/동작은 변경 없이 유지한다 (내부 최적화만 수행).

## 2) 비목표(Non-Goals)

- 그리드 서치 파라미터 범위 변경 (현재 범위는 적절함)
- Walkforward의 ProcessPoolExecutor 재사용 (아키텍처 변경이 크고 효과 제한적)
- `simulate()` 공개 API 시그니처 변경
- fork 컨텍스트 전환 (안정성 우려)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

`run_softplus_tuning.py`와 `run_walkforward_validation.py`의 실행 시간이 매우 오래 걸린다.
분석 결과, 파라미터 범위 자체는 적절하며 (softplus 총 1,860개, walkforward local refine 336개/월),
**병목은 개별 후보 평가의 비효율에 있다.**

핵심 병목 3가지:

1. **`simulate()` Python for-loop** (최대 병목):
   - `simulation.py:742-766`에서 순수 Python for-loop으로 ~3,780일(softplus) 또는 ~1,260일(walkforward) 반복
   - 매 반복: `df.iloc[i]["col"]` (느린 pandas 접근), `calculate_daily_cost()` 호출 (문자열 포맷팅 + dict 조회 + isinstance 분기 + 검증), list.append
   - 총 반복 횟수: softplus ~703만, walkforward ~5,272만

2. **`calculate_validation_metrics()` 과도한 계산** (중간 병목):
   - `simulation.py:1048-1155`에서 그리드 서치에는 RMSE만 필요한데 매번:
     - `extract_overlap_period()` 중복 호출 (이미 겹치는 데이터)
     - signed log diff 계산 (불필요)
     - 누적수익률/종가 상대차이 등 다수 부가 지표 (불필요)

3. **expense_dict 반복 생성** (낮은 병목):
   - `_evaluate_softplus_candidate` -> `simulate()` 호출 시 expense_df(DataFrame)를 매번 iterrows로 dict 변환

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/tqqq/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [ ] 기능 요구사항 충족: 세 가지 최적화 모두 적용 완료
- [ ] 수치 동등성 검증: 최적화 전후 결과가 부동소수점 오차 범위 내 동일
- [ ] 회귀/신규 테스트 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [ ] `poetry run black .` 실행 완료
- [ ] 필요한 문서 업데이트
- [ ] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/tqqq/simulation.py`: 핵심 최적화 (벡터화 함수 추가, 후보 평가 함수 수정)
- `tests/test_tqqq_simulation.py`: 수치 동등성 테스트 추가

### 데이터/결과 영향

- 출력 스키마 변경: 없음
- 기존 결과 비교: 부동소수점 오차 범위(1e-10) 내 동일해야 함

## 6) 단계별 계획(Phases)

### Phase 0 -- 수치 동등성 테스트 작성 (레드)

새로운 벡터화 함수가 기존 함수와 동일한 결과를 산출하는지 검증하는 테스트를 먼저 작성한다.

**작업 내용**:

- [ ] `tests/test_tqqq_simulation.py`에 수치 동등성 테스트 클래스 `TestVectorizedSimulation` 추가
  - [ ] `test_simulate_fast_matches_simulate`: 벡터화 시뮬레이션이 기존 simulate()와 동일한 가격 배열 산출 검증
  - [ ] `test_calculate_rmse_fast_matches_full`: 경량 RMSE가 calculate_validation_metrics의 RMSE와 동일 검증
  - [ ] `test_precompute_daily_costs_matches_per_day`: 사전 계산 비용이 개별 calculate_daily_cost()와 동일 검증

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

### Phase 1 -- 핵심 벡터화 함수 구현 (그린 유지)

`simulation.py`에 내부 전용 벡터화 함수를 추가하고, `_evaluate_softplus_candidate`에서 사용하도록 수정한다.

**작업 내용**:

#### 1-1. 사전 계산 함수 (`_precompute_daily_costs_vectorized`)

```python
def _precompute_daily_costs_vectorized(
    month_keys: np.ndarray,           # 각 거래일의 "YYYY-MM" 문자열 배열
    ffr_dict: dict[str, float],       # FFR 딕셔너리
    expense_dict: dict[str, float],   # Expense 딕셔너리
    spread_map: dict[str, float],     # 월별 spread 맵
    leverage: float,
) -> np.ndarray:
```

- [ ] 고유 월(unique months)만 추출하여 비용 계산 (월별 1회만)
- [ ] 월별 비용을 일별 배열로 매핑 (numpy 인덱싱)
- [ ] fallback 로직: 기존 `_lookup_monthly_data`와 동일한 "최근 이전 월" 폴백 적용

#### 1-2. 벡터화 시뮬레이션 함수 (`_simulate_prices_vectorized`)

```python
def _simulate_prices_vectorized(
    underlying_returns: np.ndarray,   # 기초 자산 일일 수익률 배열
    daily_costs: np.ndarray,          # 사전 계산된 일일 비용 배열
    leverage: float,
    initial_price: float,
) -> np.ndarray:
```

- [ ] `leveraged_returns = underlying_returns * leverage - daily_costs`
- [ ] `leveraged_returns[0] = 0.0` (첫날: 수익률 없음)
- [ ] `prices = initial_price * np.cumprod(1 + leveraged_returns)`
- [ ] 반환: 시뮬레이션 가격 numpy 배열

#### 1-3. 경량 RMSE 계산 함수 (`_calculate_metrics_fast`)

```python
def _calculate_metrics_fast(
    actual_prices: np.ndarray,
    simulated_prices: np.ndarray,
) -> tuple[float, float, float]:
```

- [ ] 누적배수 로그차이 abs 배열 계산 (기존 `_calculate_cumul_multiple_log_diff`와 동일 로직)
- [ ] RMSE, mean, max 세 가지 지표만 반환
- [ ] extract_overlap_period, signed log diff, DataFrame 생성 등 생략

#### 1-4. `_evaluate_softplus_candidate` 수정

- [ ] WORKER_CACHE에서 사전 계산된 배열 사용:
  - `underlying_returns`: `underlying_overlap[COL_CLOSE].pct_change().values` (NaN -> 0.0)
  - `actual_prices`: `actual_overlap[COL_CLOSE].values`
  - `expense_dict`: `_create_expense_dict(expense_df)` 결과
  - `date_month_keys`: 각 거래일의 "YYYY-MM" 배열
  - `overlap_start`, `overlap_end`, `overlap_days`: 기간 정보
- [ ] 새로운 빠른 경로 사용:
  1. `build_monthly_spread_map_from_dict` -> spread_map
  2. `_precompute_daily_costs_vectorized` -> daily_costs
  3. `_simulate_prices_vectorized` -> simulated_prices
  4. `_calculate_metrics_fast` -> rmse, mean, max
- [ ] 반환 candidate dict 구조 유지 (기존 키 모두 포함)

#### 1-5. WORKER_CACHE 사전 계산 로직 추가

`find_optimal_softplus_params`와 `_local_refine_search`에서:

- [ ] `expense_dict = _create_expense_dict(expense_df)` 사전 계산
- [ ] `underlying_returns` 배열 사전 계산
- [ ] `actual_prices` 배열 사전 계산
- [ ] `date_month_keys` 배열 사전 계산
- [ ] 기간 정보 (`overlap_start`, `overlap_end`, `overlap_days`) 사전 계산
- [ ] 모든 사전 계산 데이터를 `cache_data`에 추가

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

### Phase 2 -- `_evaluate_cost_model_candidate` 동일 최적화 적용 (그린 유지)

기존 고정 스프레드 그리드 서치 함수 `_evaluate_cost_model_candidate` (simulation.py:786-)에도 동일한 벡터화 최적화를 적용한다.

**작업 내용**:

- [ ] `_evaluate_cost_model_candidate`에서도 벡터화 경로 사용
- [ ] `find_optimal_cost_model`에서 WORKER_CACHE에 사전 계산 데이터 추가

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

### 마지막 Phase -- 문서 정리 및 최종 검증

**작업 내용**:

- [ ] 필요한 문서 업데이트
- [ ] `poetry run black .` 실행 (자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) -- 5개 중 1개 선택

1. TQQQ시뮬레이션 / simulate 벡터화 및 그리드 서치 최적화 (병렬처리 성능 개선)
2. TQQQ시뮬레이션 / numpy cumprod 벡터화로 후보 평가 성능 대폭 개선
3. TQQQ시뮬레이션 / 시뮬레이션 핫패스 벡터화 + 경량 RMSE 함수 + expense_dict 캐시
4. TQQQ시뮬레이션 / 그리드 서치 병렬처리 성능 최적화 (for-loop 제거, 불필요 계산 제거)
5. TQQQ시뮬레이션 / 성능 최적화 (벡터화 시뮬레이션, 경량 메트릭, 캐시 개선)

## 7) 리스크(Risks)

- **수치 동등성 깨짐**: 벡터화 과정에서 부동소수점 연산 순서가 달라져 결과가 미세하게 달라질 수 있음.
  - 완화: Phase 0에서 동등성 테스트를 먼저 작성하고, 적절한 tolerance (1e-10)로 검증.
- **fallback 로직 누락**: `_lookup_monthly_data`의 "최근 이전 월" 폴백이 벡터화 버전에서 누락될 수 있음.
  - 완화: 사전 계산 시 동일한 폴백 로직을 적용하고, 테스트에서 검증.
- **WORKER_CACHE 크기 증가**: 사전 계산 배열 추가로 프로세스 간 pickle 전송량 증가.
  - 완화: numpy 배열은 pandas DataFrame보다 훨씬 작으며, 추가되는 것은 1D 배열과 dict뿐.

## 8) 메모(Notes)

### 성능 분석 데이터

- Softplus 튜닝: 1,860개 후보 x ~3,780일 시뮬레이션 = ~703만 Python loop 반복
- Walkforward: ~41,844개 후보 x ~1,260일 시뮬레이션 = ~5,272만 Python loop 반복
- 파라미터 범위 자체는 적절 (Stage 1: 899개, Stage 2: 961개, Local Refine: 336개/월)

### 기대 효과

- `simulate()` 벡터화: 예상 10-50x 속도 향상 (Python for-loop + pandas iloc 제거 -> numpy cumprod)
- 경량 RMSE: 예상 2-3x 추가 향상 (extract_overlap_period, signed log diff, 부가 지표 생략)
- expense_dict 캐시: 예상 1.1-1.2x 추가 향상 (iterrows 변환 제거)

### 진행 로그 (KST)

- 2026-01-30: 성능 분석 완료, 계획서 작성

---
