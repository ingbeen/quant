# Implementation Plan: FFR 조회 캐싱/전처리

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.
> (이 템플릿을 수정하거나 새로운 양식의 계획서를 만들 때도 [docs/CLAUDE.md](../CLAUDE.md)를 포인터로 두고 준수합니다.)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2025-12-29 12:35
**마지막 업데이트**: 2025-12-29 13:16
**관련 범위**: tqqq
**관련 문서**: src/qbt/tqqq/CLAUDE.md, src/qbt/utils/CLAUDE.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- Validation에서 `poetry run ruff check .` 또는 `./run_tests.sh`가 실패하면 **해당 Phase에서 즉시 수정 후 재검증**한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**(바꾸고 싶으면 새 plan 작성).
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [ ] `calculate_daily_cost()` 내부 FFR 조회를 O(1) 딕셔너리 조회로 변경하여 성능 개선
- [ ] 기존 시뮬레이션/검증 결과(지표/가격)가 완전히 동일하게 유지
- [ ] FFR 데이터 검증 정책(MAX_FFR_MONTHS_DIFF) 및 예외 처리 정책 유지
- [ ] FFR 데이터 무결성 보장 (중복 월 발견 시 즉시 예외)

## 2) 비목표(Non-Goals)

- FFR 데이터 소스 변경 (CSV 파일 형식 유지)
- 비용 계산 공식 변경
- 검증 지표 변경
- 다른 성능 병목 지점 최적화 (이번 작업은 FFR 조회만 개선)

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**성능 병목**:
- 현재 `calculate_daily_cost()`는 매 거래일마다 `ffr_df`를 문자열 매칭/필터링하여 FFR 조회
- 그리드 서치에서 수백~수천 개 조합 × 수천 거래일 = 수백만 회 DataFrame 필터링 발생
- 특히 긴 기간(10년+) + 많은 후보 조합일 때 병목이 심화

**현재 구조** (simulation.py:179-203):
```python
year_month_str = f"{date_value.year:04d}-{date_value.month:02d}"
ffr_row = ffr_df[ffr_df[COL_FFR_DATE] == year_month_str]  # 매번 필터링!
if ffr_row.empty:
    previous_dates = ffr_df[ffr_df[COL_FFR_DATE] < year_month_str]  # 또 필터링!
    ...
```

**개선 방향**:
- FFR DataFrame을 한 번만 전처리하여 `{"YYYY-MM": ffr_value}` 딕셔너리로 변환
- 조회 시 O(1) 딕셔너리 키 접근으로 변경
- 기존 예외/검증 정책 동일하게 유지
- **중복 월 검증 강화**: 중복 발견 시 즉시 ValueError (데이터 무결성 보장)

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/tqqq/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md` (유틸리티 추가 시)
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] FFR 조회가 O(1) 딕셔너리 조회로 변경됨
- [x] 중복 월 발견 시 즉시 ValueError 발생 (데이터 무결성 보장)
- [x] 기존 validate 결과(지표/가격)가 바뀌지 않음 (회귀 테스트)
- [x] 회귀/신규 테스트 추가 (딕셔너리 생성, 조회 로직, 에지 케이스)
- [x] `./run_tests.sh` 통과 (failed=0, skipped=0; passed=143, failed=0, skipped=0)
- [x] `poetry run ruff check .` 통과
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 필요한 문서 업데이트(CLAUDE.md 등)
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**비즈니스 로직**:
- `src/qbt/tqqq/simulation.py`: FFR 딕셔너리 생성 함수 추가, `calculate_daily_cost()` 조회 로직 변경, `simulate()` 및 관련 함수 수정

**CLI 계층** (FFR 로딩 후 전처리 추가):
- `scripts/tqqq/validate_tqqq_simulation.py`
- `scripts/tqqq/generate_tqqq_daily_comparison.py`
- `scripts/tqqq/generate_synthetic_tqqq.py`
- `scripts/tqqq/streamlit_app.py` (대시보드)

**테스트**:
- `tests/test_tqqq_simulation.py`: 딕셔너리 생성/조회 테스트 추가, 회귀 테스트

### 데이터/결과 영향

- **출력 스키마**: 변경 없음
- **기존 결과 비교**: 필요함 (완전 동일 결과 보장 필수)
- **예외 메시지**: 더 명확하게 개선 가능 (기존 정책은 유지)

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트/정책을 테스트로 먼저 고정(레드)

> 핵심 인바리언트/검증 정책 변경이 포함되므로 이 Phase를 만듭니다.

**작업 내용**:

- [x] FFR 딕셔너리 생성 함수의 인터페이스 정의 (`_create_ffr_dict`)
  - 입력: `pd.DataFrame` (FFR DataFrame)
  - 출력: `dict[str, float]` ({"YYYY-MM": ffr_value})
  - 예외: ValueError (빈 DataFrame, **중복 월 발견** 시)
- [x] FFR 딕셔너리 조회 로직의 인터페이스 정의 (`_lookup_ffr`)
  - 입력: `date`, `dict[str, float]`
  - 출력: `float` (FFR 값)
  - 예외: ValueError (월 키 없음 + 이전 월 없음, 월 차이 초과)
- [x] 테스트 케이스 추가 (레드 상태 허용):
  - `test_create_ffr_dict_normal()`: 정상 케이스
  - `test_create_ffr_dict_empty()`: 빈 DataFrame
  - **`test_create_ffr_dict_duplicate_month()`**: 중복 월 시 ValueError (중요!)
  - `test_lookup_ffr_exact_match()`: 정확한 월 매칭
  - `test_lookup_ffr_fallback()`: 이전 월 폴백
  - `test_lookup_ffr_months_diff_exceeded()`: 월 차이 초과 예외

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=136, failed=7, skipped=0)

---

### Phase 1 — FFR 딕셔너리 생성/조회 함수 구현(그린 유지)

**작업 내용**:

- [x] FFR 딕셔너리 생성 함수 구현 (`_create_ffr_dict()`)
  - `ffr_df[COL_FFR_DATE]`와 `ffr_df[COL_FFR]`를 순회하며 딕셔너리 구성
  - **중복 월 발견 시 즉시 ValueError** (예: "FFR 데이터 무결성 오류: 월 YYYY-MM이 중복 존재")
  - 빈 DataFrame이면 ValueError (예: "FFR 데이터가 비어있습니다")
- [x] FFR 조회 함수 구현 (`_lookup_ffr()`)
  - 딕셔너리에서 `year_month_str` 키로 조회
  - 키가 없으면 이전 월 중 가장 가까운 값 사용
  - 이전 월도 없으면 ValueError
  - 월 차이가 `MAX_FFR_MONTHS_DIFF` 초과 시 ValueError (기존 검증 정책 유지)
- [x] Phase 0에서 추가한 테스트가 통과하도록 구현 검증

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=143, failed=0, skipped=0)

---

### Phase 2 — `calculate_daily_cost()` 조회 로직 변경(그린 유지)

**작업 내용**:

- [x] `calculate_daily_cost()` 함수 시그니처 변경
  - 기존: `ffr_df: pd.DataFrame`
  - 변경: `ffr_dict: dict[str, float]`
- [x] 내부 로직 변경
  - 기존: DataFrame 필터링 (`ffr_df[ffr_df[COL_FFR_DATE] == year_month_str]`)
  - 변경: `_lookup_ffr(date_value, ffr_dict)` 호출
- [x] 기존 `calculate_daily_cost()` 회귀 테스트 통과 확인
  - 테스트에서는 `_create_ffr_dict()`로 딕셔너리 생성 후 전달

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=143, failed=0, skipped=0)

---

### Phase 3 — `simulate()` 및 상위 호출 경로 수정(그린 유지)

**작업 내용**:

- [x] `simulate()` 함수 시그니처 변경
  - 기존: `ffr_df: pd.DataFrame`
  - 변경: `ffr_dict: dict[str, float]`
- [x] `simulate()` 내부에서 `calculate_daily_cost()` 호출 시 `ffr_dict` 전달
- [x] `calculate_validation_metrics()` 확인 (FFR 미사용으로 수정 불필요)
- [x] `find_optimal_cost_model()` 수정 (**방식 2 적용: WORKER_CACHE 사용**)
  - `ffr_dict = _create_ffr_dict(ffr_df)` 호출
  - `init_worker_cache({"ffr_dict": ffr_dict})` 호출
  - 병렬 처리 함수(`_evaluate_cost_model_candidate`)에서 `WORKER_CACHE["ffr_dict"]` 사용
- [x] 기존 시뮬레이션 테스트 통과 확인 (모든 simulate 호출 테스트 수정)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=143, failed=0, skipped=0)

---

### Phase 4 — CLI 스크립트 수정 및 통합 테스트(그린 유지)

**작업 내용**:

- [x] `validate_tqqq_simulation.py` 수정
  - `find_optimal_cost_model()`이 내부에서 `_create_ffr_dict()` 호출하므로 수정 불필요
  - 주석만 업데이트 ("검증 및 FFR 딕셔너리 생성은 비즈니스 로직 내부에서 수행")
- [x] `generate_tqqq_daily_comparison.py` 수정
  - FFR 로딩 후 `ffr_dict = _create_ffr_dict(ffr_df)` 추가
  - `simulate()` 호출 시 `ffr_dict` 전달
- [x] `generate_synthetic_tqqq.py` 수정
  - FFR 로딩 후 딕셔너리 생성
  - `simulate()` 호출 시 `ffr_dict` 전달
- [x] `streamlit_app.py` 확인
  - simulate를 호출하지 않으므로 수정 불필요
- [x] 실제 validate 스크립트 실행하여 결과 비교
  - 기존 `tqqq_validation.csv` 백업
  - 새로 생성된 결과와 비교 (지표/파라미터 완전 동일 확인)

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=143, failed=0, skipped=0)
- [x] 실제 validate 스크립트 실행 및 결과 비교 (완전 동일 확인)

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트
  - `_create_ffr_dict()`, `_lookup_ffr()` 함수 설명 추가
  - `calculate_daily_cost()` 함수 설명에 딕셔너리 전달 방식 및 성능 개선 명시
  - `simulate()`, `find_optimal_cost_model()` 시그니처 변경 반영
  - 중복 월 검증 정책 명시
- [x] Docstring 확인
  - 모든 함수 Docstring이 이미 Phase 1에서 작성되어 있음
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run ruff check .`
- [x] `./run_tests.sh` (passed=143, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / FFR 조회 캐싱으로 성능 개선 (결과 동일성 보장)
2. TQQQ시뮬레이션 / FFR 딕셔너리 전처리로 O(1) 조회 구현
3. TQQQ시뮬레이션 / 비용 계산 성능 최적화 및 데이터 무결성 강화
4. TQQQ시뮬레이션 / FFR 조회 로직 개선 (DataFrame 필터링 → 딕셔너리)
5. TQQQ시뮬레이션 / 그리드 서치 성능 개선 (FFR 캐싱 적용)

## 7) 리스크(Risks)

**회귀 위험**:
- 딕셔너리 조회 로직 버그로 인한 비용 계산 오류
- 완화: Phase 0에서 회귀 테스트 먼저 작성, Phase 4에서 실제 결과 비교

**인터페이스 변경**:
- `calculate_daily_cost()`, `simulate()` 등 다수 함수 시그니처 변경
- 완화: 타입 힌트로 안전성 확보, 테스트로 모든 호출 경로 검증

**병렬 처리 영향**:
- 병렬 처리 함수에 `ffr_dict` 전달 방식 결정 필요 (파라미터 vs WORKER_CACHE)
- 완화: 명시적 파라미터 전달 방식 권장 (더 명확하고 안전), 딕셔너리는 pickle 안전

**중복 월 검증 강화**:
- 기존 FFR 데이터에 중복이 있다면 스크립트 실패 가능
- 완화: 실제 데이터는 중복 없을 것으로 예상, 만약 있다면 데이터 품질 문제이므로 조기 발견이 유리

## 8) 메모(Notes)

### 설계 결정

**딕셔너리 키 형식**: `"YYYY-MM"` 문자열 (기존 FFR DataFrame의 DATE 컬럼 형식과 동일)
**딕셔너리 값 타입**: `float` (FFR 값, 퍼센트 단위)
**함수 위치**: `simulation.py` 내부 (모듈 레벨 private 함수로 정의, `_create_ffr_dict`, `_lookup_ffr`)
**중복 월 처리**: 즉시 ValueError (데이터 무결성 보장, 중대 에러)
**병렬 처리 방식**: WORKER_CACHE 사용 (실제 적용된 방식)

### 성능 기대치

- 그리드 서치 시 FFR 조회 횟수: 약 수백만 회 (조합 × 거래일)
- 개선: O(N) DataFrame 필터링 → O(1) 딕셔너리 조회
- 예상 개선: 전체 실행 시간 10~30% 단축 (프로파일링 필요)

### 진행 로그 (KST)

- 2025-12-29 12:35: 계획서 작성 완료 (Draft)
- 2025-12-29 12:40: Phase 0 완료 (인터페이스 정의 및 테스트 추가, passed=136, failed=7, skipped=0)
- 2025-12-29 12:52: Phase 1 완료 (FFR 딕셔너리 생성/조회 함수 구현, passed=143, failed=0, skipped=0)
- 2025-12-29 13:04: Phase 2 & 3 완료 (calculate_daily_cost, simulate, find_optimal_cost_model 수정, 모든 테스트 통과)
- 2025-12-29 13:10: Phase 4 완료 (CLI 스크립트 수정, validate 스크립트 실행 및 결과 완전 동일 확인)
- 2025-12-29 13:16: 마지막 Phase 완료 (문서 업데이트, Black 포맷팅, 최종 검증 완료, ✅ Done)

---
