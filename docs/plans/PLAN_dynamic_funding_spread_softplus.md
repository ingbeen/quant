# Implementation Plan: 동적 Funding Spread + Softplus 기반 FFR 모델

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: 🔄 In Progress

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-01-19 20:30
**마지막 업데이트**: 2026-01-19 20:30
**관련 범위**: tqqq, scripts/tqqq, utils
**관련 문서**: src/qbt/tqqq/CLAUDE.md, scripts/CLAUDE.md, tests/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run python validate_project.py`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] 목표 1: `funding_spread` 동적 입력 지원 (float, dict[str, float], Callable[[date], float])
- [ ] 목표 2: softplus 기반 f(FFR) 동적 스프레드 함수 구현 (`spread = softplus(a + b * ffr_pct)`)
- [ ] 목표 3: (a, b) 글로벌 튜닝 기능 구현 (2-stage grid search, RMSE 최소화)
- [ ] 목표 4: rolling corr inf/NaN 가드 구현
- [ ] 목표 5: meta.json append 기록 기능 추가
- [ ] 목표 6: Streamlit 앱에 softplus 동적 모드 추가 (기존 고정 spread 유지)
- [ ] 목표 7: 베이스라인 동일성 검증 (고정 float spread 모드 결과가 수정 전과 동일)

## 2) 비목표(Non-Goals)

- 워크포워드(Walk-forward) 검증: 프롬프트 2에서 진행 예정
- 기존 3개 CSV 스키마 변경: 유지
- Streamlit UI에서 워크포워드 토글: 프롬프트 2에서 다룸
- 기초 자산 데이터 다운로드/검증 로직 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- **핵심 문제**: Streamlit 분석에서 FFR(금리 수준)과 월말 누적오차(e_m) 사이에 강한 양(+) 관계 관측
  - 고금리 구간에서 시뮬레이션 TQQQ가 실제보다 높게 나옴 (비용 과소 반영)
  - `funding_spread`를 FFR 수준에 따라 동적으로 증가시키는 로직 필요
- **현재 한계**: `simulate()` 함수가 `funding_spread: float`만 지원
- **목표**: TQQQ 실존 기간 동안 실제 TQQQ와 시뮬레이션의 RMSE 최소화

### 핵심 제약 조건 (프롬프트에서 확정)

1. **베이스라인 동작 불변**: 단일 float로 `funding_spread`를 넣을 때 결과가 수정 전과 동일
2. **단위**: `funding_spread`는 ratio 단위 (예: 0.0034 = 0.34%)
3. **min/max 클리핑(출력 clamp) 금지**
4. **음수 불허, 0도 불허**: 반환 spread는 항상 `> 0`
5. **목적함수**: `cumul_multiple_log_diff_rmse_pct` 최소화
6. **FFR 스케일**: `ffr_pct = 100.0 * ffr_ratio`

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md` (TQQQ 시뮬레이션 도메인)
- `src/qbt/utils/CLAUDE.md` (유틸리티)
- `scripts/CLAUDE.md` (CLI 스크립트)
- `tests/CLAUDE.md` (테스트)

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [ ] 고정 spread(float) 모드 실행 시 수정 전과 동일한 결과 (핵심 지표 포함)
- [ ] softplus 동적 모드가 실행 가능 (글로벌 (a,b) 탐색/선정)
- [ ] rolling corr inf 제거 확인
- [ ] meta.json에 append 기록 확인
- [ ] 회귀/신규 테스트 추가
- [ ] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed/failed/skipped 수 기록)
- [ ] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [ ] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**핵심 구현:**
- `src/qbt/tqqq/simulation.py`: `_resolve_spread()` 유틸 추가, `calculate_daily_cost()` 및 `simulate()` 수정
- `src/qbt/tqqq/constants.py`: softplus 관련 상수 추가 (grid search 범위 등)
- `src/qbt/tqqq/analysis_helpers.py`: rolling corr inf/NaN 가드 추가

**Streamlit 앱:**
- `scripts/tqqq/streamlit_rate_spread_lab.py`: softplus 동적 모드 UI 및 튜닝 로직 추가

**테스트:**
- `tests/test_tqqq_simulation.py`: 동적 spread 지원 테스트 추가
- `tests/test_tqqq_analysis_helpers.py`: rolling corr 가드 테스트 추가

### 데이터/결과 영향

- 기존 3개 CSV 스키마 유지 (변경 없음)
  - `tqqq_rate_spread_lab_model.csv`
  - `tqqq_rate_spread_lab_monthly.csv`
  - `tqqq_rate_spread_lab_summary.csv`
- `meta.json`에 새로운 키 추가 (기존 구조 확장)

## 6) 단계별 계획(Phases)

### Phase 0 - 베이스라인 백업 및 테스트 준비

**작업 내용**:

- [x] 현재 3개 CSV 파일 백업 (비교용)
- [x] 현재 Streamlit 앱을 고정 spread 모드로 실행하여 summary CSV의 핵심 지표 기록
- [x] 동적 spread 지원을 위한 테스트 케이스 설계 (레드 테스트 추가)
  - float 모드: 기존 동작 유지 확인
  - dict 모드: 월별 키 조회, 키 누락 시 ValueError
  - Callable 모드: 함수 호출, 반환값 검증 (NaN/inf/<=0 시 ValueError)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=74, failed=0, skipped=0)

---

### Phase 1 - 동적 funding_spread 지원 구현 (simulation.py)

**작업 내용**:

- [x] 타입 정의: `FundingSpreadSpec = float | dict[str, float] | Callable[[date], float]`
- [x] `_resolve_spread(d: date, spread_spec: FundingSpreadSpec) -> float` 헬퍼 함수 구현
  - float: 그대로 반환
  - dict: `month_key = f"{d.year:04d}-{d.month:02d}"` 키 조회, 없으면 ValueError
  - Callable: 함수 호출, 반환값 검증 (NaN/inf면 ValueError, <=0이면 ValueError)
  - 최종 spread <= 0이면 ValueError
- [x] `calculate_daily_cost()` 함수 시그니처 수정: `funding_spread: FundingSpreadSpec`
  - 내부에서 `_resolve_spread()` 호출
- [x] `simulate()` 함수 시그니처 수정: `funding_spread: FundingSpreadSpec`
- [x] `_evaluate_cost_model_candidate()` 병렬 함수도 수정 (기존 float 지원 유지)
- [x] Phase 0 레드 테스트가 그린으로 전환 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=74, failed=0, skipped=0)

---

### Phase 2 - softplus 함수 및 월별 spread 맵 생성

**작업 내용**:

- [x] constants.py에 상수 추가:
  - `SOFTPLUS_GRID_STAGE1_A_RANGE = (-10.0, -3.0)`
  - `SOFTPLUS_GRID_STAGE1_A_STEP = 0.25`
  - `SOFTPLUS_GRID_STAGE1_B_RANGE = (0.00, 1.50)`
  - `SOFTPLUS_GRID_STAGE1_B_STEP = 0.05`
  - `SOFTPLUS_GRID_STAGE2_A_DELTA = 0.75`
  - `SOFTPLUS_GRID_STAGE2_A_STEP = 0.05`
  - `SOFTPLUS_GRID_STAGE2_B_DELTA = 0.30`
  - `SOFTPLUS_GRID_STAGE2_B_STEP = 0.02`
- [x] `softplus(x: float) -> float` 함수 구현
  - 수치 안정 버전: `log1p(exp(-abs(x))) + max(x, 0)`
- [x] `compute_softplus_spread(a: float, b: float, ffr_ratio: float) -> float` 함수 구현
  - `ffr_pct = 100.0 * ffr_ratio`
  - `spread = softplus(a + b * ffr_pct)`
  - spread <= 0이면 ValueError (softplus는 항상 > 0이므로 이론적으로 불가, 방어적 체크)
- [x] `build_monthly_spread_map(ffr_df: pd.DataFrame, a: float, b: float) -> dict[str, float]` 함수 구현
  - FFR 데이터로부터 각 월별 spread 계산
  - 반환: {"YYYY-MM": spread} 딕셔너리
- [x] 테스트 추가: softplus 함수 수치 검증, spread 맵 생성 검증

**Validation**:

- [x] `poetry run python validate_project.py` (passed=74, failed=0, skipped=0)

---

### Phase 3 - (a,b) 글로벌 튜닝 (2-stage grid search)

**작업 내용**:

- [x] `find_optimal_softplus_params()` 함수 구현
  - Stage 1: 조대 그리드 탐색
    - a in [-10.0, -3.0] step 0.25
    - b in [0.00, 1.50] step 0.05
  - Stage 2: 정밀 그리드 탐색
    - a in [a* - 0.75, a* + 0.75] step 0.05
    - b in [b* - 0.30, b* + 0.30] step 0.02
  - 평가 함수: 기존 `calculate_validation_metrics()` 재사용
  - 목적함수: `cumul_multiple_log_diff_rmse_pct` 최소화
  - 반환: `(a_best, b_best, best_rmse, all_candidates)`
- [x] 성능 최적화:
  - 데이터 로딩/정렬은 한 번만 수행
  - FFR dict, expense dict 캐싱
  - 병렬 처리 고려 (execute_parallel 활용)
- [x] 테스트 추가: 튜닝 함수 동작 검증 (작은 그리드로 테스트)

**Validation**:

- [x] `poetry run python validate_project.py` (passed=226, failed=0, skipped=0)

---

### Phase 4 - rolling corr inf/NaN 가드 (analysis_helpers.py)

**작업 내용**:

- [x] `add_rolling_features()` 함수 수정
  - corr 계산 전: 윈도우 내 표준편차가 0 또는 매우 작으면 결과를 NaN으로 처리
  - corr 계산 후: ±inf 값을 NaN으로 치환
  - `np.isinf()` 및 `np.isnan()` 활용
- [x] `build_model_dataset()` 함수에도 가드 반영 확인
- [x] 테스트 추가: inf/NaN 발생 시나리오 검증

**Validation**:

- [x] `poetry run python validate_project.py` (passed=228, failed=0, skipped=0)

---

### Phase 5 - Streamlit 앱 수정 (softplus 모드 추가)

**작업 내용**:

- [ ] 기존 고정 spread 실행 경로 유지 (베이스라인 검증용)
- [ ] softplus 동적 spread 모드 실행 경로 추가
  - 사이드바 또는 탭으로 모드 선택 UI 추가
  - "(a, b) 글로벌 튜닝 실행" 버튼
  - 튜닝 진행 상황 표시 (progress bar)
  - 결과 표시: 최적 (a, b), RMSE, 그리드 서치 결과 테이블
- [ ] 결과 CSV 자동 저장 (기존 3개 CSV 유지)
- [ ] 캐시 정책 유지 (st.cache_resource, st.cache_data)

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

### Phase 6 - 메타 기록 구현

**작업 내용**:

- [ ] Streamlit 앱에서 튜닝 실행 시 meta.json에 append 기록
- [ ] 기록 키 (최소 포함):
  - `funding_spread_mode`: `"fixed_float"` / `"softplus_ffr_monthly"`
  - `softplus_a`, `softplus_b`
  - `ffr_scale`: `"pct"`
  - `objective`: `"cumul_multiple_log_diff_rmse_pct"`
  - `grid_settings`: stage1/stage2 범위/스텝
  - `output_files`: 기존 3개 CSV 경로
  - `best_rmse_pct`: 최적 RMSE 값
- [ ] 테스트 추가: 메타 기록 형식 검증

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

### Phase 7 - 베이스라인 동일성 검증

**작업 내용**:

- [ ] 고정 spread(float) 모드로 Streamlit 앱 실행
- [ ] Phase 0에서 백업한 CSV와 비교
  - 핵심 지표가 동일한지 확인 (summary CSV 비교)
  - 소수점 허용 오차 고려 (부동소수점 특성)
- [ ] 검증 결과 문서화

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

---

### 마지막 Phase - 문서 정리 및 최종 검증

**작업 내용**

- [ ] 필요한 문서 업데이트 (CLAUDE.md 등)
- [ ] `poetry run black .` 실행(자동 포맷 적용)
- [ ] 변경 기능 및 전체 플로우 최종 검증
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료
- [ ] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [ ] `poetry run python validate_project.py` (passed=__, failed=__, skipped=__)

#### Commit Messages (Final candidates) - 5개 중 1개 선택

1. TQQQ시뮬레이션 / 동적 funding_spread 지원 (float/dict/Callable) + softplus 모델 구현
2. TQQQ시뮬레이션 / softplus 기반 FFR 동적 스프레드 + 2-stage grid search 튜닝
3. TQQQ시뮬레이션 / FFR 연동 동적 비용 모델 + rolling corr inf 가드 추가
4. TQQQ시뮬레이션 / 동적 스프레드 지원 및 글로벌 파라미터 튜닝 기능 구현
5. TQQQ시뮬레이션 / softplus 동적 비용 모델 + Streamlit 튜닝 UI 추가

## 7) 리스크(Risks)

1. **성능 위험**: 2-stage grid search가 시간이 오래 걸릴 수 있음
   - 완화: 데이터 캐싱, 병렬 처리 적용
2. **베이스라인 회귀**: 기존 float 모드 동작이 달라질 수 있음
   - 완화: Phase 0에서 베이스라인 백업, Phase 7에서 동일성 검증
3. **수치 안정성**: softplus 계산 시 overflow/underflow 가능
   - 완화: 수치 안정 버전 softplus 사용 (`log1p(exp(-abs(x))) + max(x, 0)`)

## 8) 메모(Notes)

### 핵심 수식

**softplus (수치 안정 버전)**:
```
softplus(x) = log1p(exp(-abs(x))) + max(x, 0)
```

**동적 spread 계산**:
```
ffr_pct = 100.0 * ffr_ratio
spread = softplus(a + b * ffr_pct)
```

**Grid search 범위 (프롬프트에서 확정)**:
- Stage 1:
  - a in [-10.0, -3.0] step 0.25 (29개)
  - b in [0.00, 1.50] step 0.05 (31개)
  - 총 899 조합
- Stage 2:
  - a in [a* - 0.75, a* + 0.75] step 0.05 (31개)
  - b in [b* - 0.30, b* + 0.30] step 0.02 (31개)
  - 총 961 조합

### 참고 파일

- 기존 CSV 위치: `storage/results/tqqq_rate_spread_lab_*.csv`
- FFR 데이터: `storage/etc/federal_funds_rate_monthly.csv`
- 메타 기록: `storage/results/meta.json`

### 진행 로그 (KST)

- 2026-01-19 20:30: 계획서 초안 작성

---
