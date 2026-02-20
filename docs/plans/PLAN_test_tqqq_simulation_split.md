# Implementation Plan: test_tqqq_simulation.py 테스트 파일 분리

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

**작성일**: 2026-02-21 02:00
**마지막 업데이트**: 2026-02-21 02:00
**관련 범위**: tests
**관련 문서**: `tests/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 목표 1: `test_tqqq_simulation.py`(3480줄, 26개 클래스)를 소스 모듈 분할에 맞춰 3개 테스트 파일로 분리
- [x] 목표 2: data_loader 관련 테스트 클래스 4개를 기존 `test_tqqq_data_loader.py`로 이동

## 2) 비목표(Non-Goals)

- 테스트 로직 변경: 모든 분리는 파일 이동만 수행하며, 테스트 코드 자체의 수정 없음
- 새로운 테스트 추가
- 테스트 클래스/메서드 이름 변경
- conftest.py 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `PLAN_simulation_split_cli_extraction.md`에 의해 `simulation.py`가 3개 모듈로 분할 완료:
  - `simulation.py` (core, 12개 함수)
  - `optimization.py` (6개 함수)
  - `walkforward.py` (8개 함수)
- 테스트 파일 `test_tqqq_simulation.py`는 3480줄, 26개 클래스가 하나의 파일에 잔류
- 소스 모듈과 테스트 파일의 1:1 대응이 깨져 탐색성 저하
- data_loader 관련 테스트 4개 클래스가 `test_tqqq_data_loader.py`가 아닌 `test_tqqq_simulation.py`에 배치되어 있음

### 분리 매핑 (26개 클래스 → 4개 파일)

#### `test_tqqq_simulation.py` (core, 12개 클래스 잔류)

| 클래스명 | 현재 줄 | 테스트 대상 함수 |
|---------|---------|----------------|
| TestCalculateDailyCost | 45 | `_calculate_daily_cost` |
| TestSimulate | 215 | `simulate` |
| TestCalculateValidationMetrics | 422 | `calculate_validation_metrics` |
| TestSimulateValidation | 480 | `simulate` (파라미터 검증) |
| TestSaveDailyComparisonCsv | 582 | `_save_daily_comparison_csv` |
| TestValidateFfrCoverage | 703 | `_validate_ffr_coverage` |
| TestCalculateDailyCostWithDynamicExpense | 1095 | `_calculate_daily_cost` (동적 expense) |
| TestSoftplusFunctions | 1122 | `_softplus`, `compute_softplus_spread`, `build_monthly_spread_map` |
| TestDynamicFundingSpread | 1376 | `_calculate_daily_cost` (dict/callable/float dispatch) |
| TestGenerateStaticSpreadSeries | 2371 | `generate_static_spread_series` |
| TestCLIScriptExists | 2490 | CLI 스크립트 존재 확인 |
| TestSimulateOvernightOpen | 3312 | `simulate` (Open 가격 overnight gap) |

#### `test_tqqq_optimization.py` (신규, 5개 클래스)

| 클래스명 | 현재 줄 | 테스트 대상 함수 |
|---------|---------|----------------|
| TestFindOptimalSoftplusParams | 1693 | `find_optimal_softplus_params` |
| TestFixedBParameter | 2025 | `find_optimal_softplus_params` (fixed_b) |
| TestVectorizedSimulation | 2525 | 벡터화/루프 수치 동등성 검증 |
| TestEvaluateSoftplusCandidate | 3173 | `_evaluate_softplus_candidate` |
| TestPrecomputeDailyCostsVectorizedErrors | 3283 | `_precompute_daily_costs_vectorized` (에러) |

#### `test_tqqq_walkforward.py` (신규, 5개 클래스)

| 클래스명 | 현재 줄 | 테스트 대상 함수 |
|---------|---------|----------------|
| TestLocalRefineSearch | 1916 | `_local_refine_search` |
| TestRunWalkforwardValidation | 2201 | `run_walkforward_validation` |
| TestCalculateStitchedWalkforwardRmse | 2749 | `calculate_stitched_walkforward_rmse` |
| TestCalculateFixedAbStitchedRmse | 2955 | `calculate_fixed_ab_stitched_rmse` |
| TestCalculateRateSegmentedRmse | 3074 | `calculate_rate_segmented_rmse` |

#### `test_tqqq_data_loader.py` (기존 파일에 추가, 4개 클래스 이동)

| 클래스명 | 현재 줄 | 테스트 대상 함수 |
|---------|---------|----------------|
| TestCreateFfrDict | 835 | `create_ffr_dict` |
| TestLookupFfr | 892 | `lookup_ffr` |
| TestExpenseRatioLoading | 964 | `load_expense_ratio_data`, `create_expense_dict` |
| TestGenericMonthlyDataDict | 1015 | `create_monthly_data_dict`, `lookup_monthly_data` |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md`(루트): 코딩 표준, 품질 검증
- `tests/CLAUDE.md`: 테스트 작성 원칙
- `src/qbt/tqqq/CLAUDE.md`: 시뮬레이션 도메인 가이드

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x]`test_tqqq_optimization.py` 신규 생성 (5개 클래스)
- [x]`test_tqqq_walkforward.py` 신규 생성 (5개 클래스)
- [x]`test_tqqq_data_loader.py`에 4개 클래스 추가 (기존 3개 + 이동 4개 = 7개 클래스)
- [x]`test_tqqq_simulation.py`에서 이동된 14개 클래스 제거 (잔류 12개 클래스)
- [x]각 파일의 docstring 및 import 정리
- [x]`poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x]`poetry run black .` 실행 완료
- [x]`tests/CLAUDE.md` 파일 구조 업데이트 (신규 테스트 파일 반영)
- [x]`src/qbt/tqqq/CLAUDE.md` 테스트 커버리지 섹션 업데이트
- [x]plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**테스트 파일 분리**:
- `tests/test_tqqq_simulation.py` — 14개 클래스 제거, 12개 잔류
- `tests/test_tqqq_optimization.py` — 신규 생성, 5개 클래스
- `tests/test_tqqq_walkforward.py` — 신규 생성, 5개 클래스
- `tests/test_tqqq_data_loader.py` — 4개 클래스 추가

**문서 업데이트**:
- `tests/CLAUDE.md` — 폴더 구조에 신규 파일 반영
- `src/qbt/tqqq/CLAUDE.md` — 테스트 커버리지 섹션 업데이트

### 데이터/결과 영향

- 없음. 테스트 파일 분리만 수행하며, 테스트 로직/결과 변경 없음
- 총 테스트 수(passed/failed/skipped) 동일 유지

## 6) 단계별 계획(Phases)

### Phase 1 — `test_tqqq_optimization.py` 생성 (그린 유지)

**작업 내용**:

- [x]`tests/test_tqqq_optimization.py` 신규 생성
  - 파일 docstring 작성 (optimization 모듈 테스트 설명)
  - 이동 대상 5개 클래스:
    - TestFindOptimalSoftplusParams (줄 1693-1914)
    - TestFixedBParameter (줄 2025-2199)
    - TestVectorizedSimulation (줄 2525-2747)
    - TestEvaluateSoftplusCandidate (줄 3173-3281)
    - TestPrecomputeDailyCostsVectorizedErrors (줄 3283-3310)
  - 필요한 import 구성:
    - `from qbt.tqqq.optimization import ...` (find_optimal_softplus_params, _evaluate_softplus_candidate, _precompute_daily_costs_vectorized, _build_monthly_spread_map_from_dict, _simulate_prices_vectorized)
    - `from qbt.tqqq.simulation import ...` (simulate, _calculate_daily_cost, compute_softplus_spread, calculate_validation_metrics, _calculate_metrics_fast)
    - 기타: numpy, pandas, pytest, datetime, WORKER_CACHE 등
    - monkeypatch 대상: `import qbt.tqqq.optimization as opt_module`
- [x]`test_tqqq_simulation.py`에서 이동된 5개 클래스 제거
- [x]`test_tqqq_simulation.py` 상단 import에서 optimization 전용 import 제거 (사용처 없는 것만)

---

### Phase 2 — `test_tqqq_walkforward.py` 생성 (그린 유지)

**작업 내용**:

- [x]`tests/test_tqqq_walkforward.py` 신규 생성
  - 파일 docstring 작성 (walkforward 모듈 테스트 설명)
  - 이동 대상 5개 클래스:
    - TestLocalRefineSearch (줄 1916-2023)
    - TestRunWalkforwardValidation (줄 2201-2369)
    - TestCalculateStitchedWalkforwardRmse (줄 2749-2953)
    - TestCalculateFixedAbStitchedRmse (줄 2955-3072)
    - TestCalculateRateSegmentedRmse (줄 3074-3171)
  - 필요한 import 구성:
    - `from qbt.tqqq.walkforward import ...` (_local_refine_search, run_walkforward_validation, calculate_stitched_walkforward_rmse, calculate_fixed_ab_stitched_rmse, calculate_rate_segmented_rmse)
    - `from qbt.tqqq.optimization import ...` (find_optimal_softplus_params)
    - `from qbt.tqqq.simulation import ...` (simulate, build_monthly_spread_map, compute_softplus_spread, calculate_validation_metrics)
    - 기타: numpy, pandas, pytest, datetime 등
    - monkeypatch 대상: `import qbt.tqqq.walkforward as wf_module`, `import qbt.tqqq.optimization as opt_module`
- [x]`test_tqqq_simulation.py`에서 이동된 5개 클래스 제거
- [x]`test_tqqq_simulation.py` 상단 import에서 walkforward 전용 import 제거 (사용처 없는 것만)

---

### Phase 3 — data_loader 테스트 이동 (그린 유지)

**작업 내용**:

- [x]`tests/test_tqqq_data_loader.py`에 4개 클래스 추가 (기존 3개 클래스 아래에 배치)
  - 이동 대상 4개 클래스:
    - TestCreateFfrDict (줄 835-890)
    - TestLookupFfr (줄 892-962)
    - TestExpenseRatioLoading (줄 964-1013)
    - TestGenericMonthlyDataDict (줄 1015-1093)
  - 필요한 import 추가:
    - `from qbt.tqqq.data_loader import create_ffr_dict, lookup_ffr, create_expense_dict, create_monthly_data_dict, lookup_monthly_data`
    - `from qbt.tqqq.constants import COL_FFR_DATE, COL_FFR_VALUE, COL_EXPENSE_DATE, COL_EXPENSE_VALUE`
    - 기타: numpy (TestGenericMonthlyDataDict에서 사용)
  - 파일 docstring 업데이트 (이동된 테스트 반영)
- [x]`test_tqqq_simulation.py`에서 이동된 4개 클래스 제거
- [x]`test_tqqq_simulation.py` 상단 import에서 data_loader 전용 import 제거 (사용처 없는 것만)

---

### Phase 4 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x]`test_tqqq_simulation.py` docstring 업데이트 (분리 후 남은 내용 반영)
- [x]`tests/CLAUDE.md` 폴더 구조 업데이트:
  - `test_tqqq_optimization.py` 추가
  - `test_tqqq_walkforward.py` 추가
- [x]`src/qbt/tqqq/CLAUDE.md` 테스트 커버리지 섹션 업데이트:
  - `tests/test_tqqq_optimization.py` 추가
  - `tests/test_tqqq_walkforward.py` 추가
- [x]`poetry run black .` 실행
- [x]DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=301, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 테스트 / test_tqqq_simulation.py 모듈별 분리 (simulation + optimization + walkforward + data_loader)
2. 테스트 / TQQQ 테스트 파일 분리 — 소스 모듈 분할에 맞춘 테스트 재배치
3. 테스트 / test_tqqq_simulation.py 3480줄 → 4개 파일 분리 (동작 동일)
4. 테스트 / TQQQ 시뮬레이션 테스트 모듈화 — core/optimization/walkforward/data_loader 분리
5. 테스트 / 소스 모듈 분할에 맞춘 테스트 파일 재배치 (26개 클래스 → 4개 파일)

## 7) 리스크(Risks)

- **import 누락**: 각 테스트 클래스가 사용하는 모든 import를 정확히 새 파일로 옮겨야 함. 클래스 내부의 local import도 확인 필요
- **상단 import 정리 오류**: `test_tqqq_simulation.py`에서 이동된 클래스 전용 import를 제거할 때, 잔류 클래스에서도 사용하는 import를 실수로 제거할 위험. 각 import의 사용처를 Grep으로 확인하여 방지
- **data_loader import 충돌**: `test_tqqq_data_loader.py`에 기존 import와 새로 추가되는 import 간 중복/충돌 가능. 이미 존재하는 import를 확인 후 병합

## 8) 메모(Notes)

- 이 계획서는 `PLAN_simulation_split_cli_extraction.md` 완료 후 후속 작업
- 비즈니스 로직 변경 없음 — 순수한 테스트 파일 재배치
- TestVectorizedSimulation은 optimization 모듈의 벡터화 함수를 검증하는 것이 주 목적이므로 `test_tqqq_optimization.py`에 배치
- TestCLIScriptExists는 특정 모듈에 종속되지 않으나, tqqq 시뮬레이션 관련 스크립트 확인이므로 `test_tqqq_simulation.py`에 잔류

### 진행 로그 (KST)

- 2026-02-21 02:00: 계획서 초안 작성
- 2026-02-21 02:40: Phase 1-4 완료 (검증 통과 — passed=301, failed=0, skipped=0)

---
