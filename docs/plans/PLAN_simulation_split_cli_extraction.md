# Implementation Plan: simulation.py 모듈 분할 + CLI 비즈니스 로직 분리 (D-4 + C-2)

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

**작성일**: 2026-02-20 23:00
**마지막 업데이트**: 2026-02-20 23:00
**관련 범위**: src/qbt/tqqq, scripts/tqqq/spread_lab, tests
**관련 문서**: `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] 목표 1: `simulation.py`(2114줄, 24개 함수)를 관심사별 3개 모듈로 분할 (보고서 D-4)
- [x] 목표 2: `validate_walkforward_fixed_ab.py`의 비즈니스 로직 2개 함수를 비즈니스 로직 계층으로 이동 (보고서 C-2)
- [x] 목표 3: CLI 스크립트의 `_calculate_metrics_fast` private import 제거 (캡슐화 위반 해소)

## 2) 비목표(Non-Goals)

- 비즈니스 로직 변경: 모든 분할/이동은 동작 동일성(behavioral equivalence) 보장
- `app_rate_spread_lab.py` 파일 분할 (D-5): 별도 계획서 대상
- 3개 워크포워드 스크립트 통합 (D-3): 별도 계획서 대상
- C-1, C-3 (다른 CLI 스크립트 로직 분리): 별도 계획서 대상
- 새로운 함수/기능 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- D-4: `simulation.py`가 2114줄, 24개 함수로 과대함. 시뮬레이션 엔진, softplus 파라미터 최적화, 워크포워드 검증 등 서로 다른 관심사가 한 파일에 밀집
- C-2: `validate_walkforward_fixed_ab.py`에 ~218줄의 비즈니스 로직(`_run_fixed_ab_walkforward`, `_calculate_rate_segmented_from_stitched`)이 CLI에 직접 구현. 계층 분리 원칙 위반
- C-2의 `_calculate_metrics_fast` private import (줄 41): 모듈 캡슐화 위반. 다른 3개 워크포워드 스크립트는 모두 public API만 사용하는 깨끗한 구조
- 두 작업은 밀접하게 연관: C-2 함수들이 walkforward 관심사에 속하므로, D-4 분할 시 생성되는 `walkforward.py`에 직접 배치하면 중간 이동 없이 효율적

### 분할 설계

`simulation.py`(24개 함수) → 3개 모듈로 분할:

| 모듈 | 관심사 | 함수 수 | 예상 줄 수 |
|------|--------|---------|-----------|
| `simulation.py` (core) | 시뮬레이션 엔진, 비용 계산, 검증 지표 | 12개 | ~940 |
| `optimization.py` (신규) | softplus 파라미터 탐색, 벡터화 연산 | 6개 | ~500 |
| `walkforward.py` (신규) | 워크포워드 검증, stitched RMSE | 6+2(C-2)개 | ~920 |

모듈 간 의존성 (순방향만, 순환 없음):

```
simulation.py (core) ← optimization.py ← walkforward.py
```

### `_calculate_metrics_fast` 배치 결정

`_calculate_metrics_fast`는 optimization과 walkforward 양쪽에서 사용됨. 순환 의존성 방지를 위해 **core(simulation.py)에 잔류**:
- `optimization.py`에서 import하여 사용
- `walkforward.py`에서 import하여 사용
- 동일 패키지(`qbt.tqqq`) 내 private 함수 공유는 Python 관례상 허용

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md`(루트): 계층 분리 원칙, 상수 관리
- `src/qbt/tqqq/CLAUDE.md`: 시뮬레이션 엔진, 함수 목록
- `scripts/CLAUDE.md`: CLI 스크립트 규칙 (비즈니스 로직 구현 금지)
- `tests/CLAUDE.md`: 테스트 작성 원칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] D-4: `simulation.py`가 12개 core 함수만 포함 (~940줄) — 실제: 12개, 943줄
- [x] D-4: `optimization.py`가 6개 최적화 함수 포함 (~500줄) — 실제: 6개, 524줄
- [x] D-4: `walkforward.py`가 8개 워크포워드 함수 포함 (~920줄) — 실제: 8개, 927줄
- [x] C-2: `validate_walkforward_fixed_ab.py`에서 비즈니스 로직 2개 함수 제거, `walkforward.py`에서 import
- [x] C-2: `validate_walkforward_fixed_ab.py`에서 `_calculate_metrics_fast` private import 제거
- [x] `__init__.py` 변경 불필요 확인 (re-export 대상 3개 함수 모두 core에 잔류)
- [x] 모든 scripts/ import 경로 업데이트 완료 (4개 파일)
- [x] 모든 tests/ import 경로 업데이트 완료 (test_tqqq_simulation.py)
- [x] `poetry run python validate_project.py` 통과 (passed=301, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `tqqq/CLAUDE.md` 업데이트 (신규 모듈 2개 반영)
- [x] `PROJECT_ANALYSIS_REPORT.md` 해결 상태 업데이트 (C-2, D-4)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

**모듈 분할 (D-4)**:
- `src/qbt/tqqq/simulation.py` — 12개 함수 제거 (optimization 6개 + walkforward 6개)
- `src/qbt/tqqq/optimization.py` — 신규 생성, 6개 함수
- `src/qbt/tqqq/walkforward.py` — 신규 생성, 6개 기존 함수 + 2개 C-2 함수

**C-2 CLI 로직 분리**:
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py` — 비즈니스 로직 2개 함수 제거, import로 대체

**import 경로 업데이트 (scripts/ 4파일)**:
- `scripts/tqqq/spread_lab/tune_softplus_params.py` — `find_optimal_softplus_params`를 `optimization`에서 import
- `scripts/tqqq/spread_lab/validate_walkforward.py` — walkforward 함수를 `walkforward`에서 import
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_b.py` — 동일
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py` — 동일 + C-2 함수 import 추가

**import 경로 업데이트 (tests/ 1파일)**:
- `tests/test_tqqq_simulation.py` — 상단 import 12개 + local import ~27개소 + monkeypatch 대상 5개소

**문서 업데이트**:
- `src/qbt/tqqq/CLAUDE.md` — 신규 모듈 설명 추가
- `PROJECT_ANALYSIS_REPORT.md` — C-2, D-4 해결 상태 반영

### 데이터/결과 영향

- 없음. 모든 변경은 import 경로 변경 및 파일 분할이며 비즈니스 로직 변경 없음
- 출력 CSV/JSON 내용 동일

## 6) 단계별 계획(Phases)

### Phase 1 — `optimization.py` 생성 및 import 업데이트 (그린 유지)

**작업 내용**:

- [x] `src/qbt/tqqq/optimization.py` 생성
  - 이동 대상 함수 6개:
    - `_build_monthly_spread_map_from_dict` (simulation.py:231-272)
    - `_precompute_daily_costs_vectorized` (simulation.py:556-615)
    - `_simulate_prices_vectorized` (simulation.py:618-653)
    - `_evaluate_softplus_candidate` (simulation.py:1121-1209)
    - `_prepare_optimization_data` (simulation.py:1212-1281)
    - `find_optimal_softplus_params` (simulation.py:1284-1447)
  - 필요한 import 구성:
    - core에서: `_validate_ffr_coverage`, `_calculate_metrics_fast`
    - 외부: `qbt.tqqq.constants`(SOFTPLUS_GRID_* 등), `qbt.tqqq.data_loader`, `qbt.tqqq.types`, `qbt.utils.parallel_executor`
- [x] `simulation.py`에서 이동된 6개 함수 제거
- [x] `simulation.py`에서 이동된 함수에서만 사용하던 import 정리 (사용처 없는 import 제거)
- [x] `scripts/tqqq/spread_lab/tune_softplus_params.py` import 변경:
  - `from qbt.tqqq.simulation import find_optimal_softplus_params` → `from qbt.tqqq.optimization import find_optimal_softplus_params`
  - `generate_static_spread_series`는 core에 잔류하므로 `simulation` import 유지
- [x] `tests/test_tqqq_simulation.py` optimization 관련 import 변경:
  - 상단 import: `_evaluate_softplus_candidate`, `_precompute_daily_costs_vectorized` → `from qbt.tqqq.optimization import ...`
  - local import (~12개소): `find_optimal_softplus_params`, `_build_monthly_spread_map_from_dict`, `_simulate_prices_vectorized` 등 → `from qbt.tqqq.optimization import ...`
  - monkeypatch 대상 변경 (4개소): `import qbt.tqqq.simulation as sim_module` → `import qbt.tqqq.optimization as opt_module` (SOFTPLUS_GRID_* 상수 패치 대상 변경)

---

### Phase 2 — `walkforward.py` 생성 + C-2 비즈니스 로직 이동 (그린 유지)

**작업 내용**:

- [x] `src/qbt/tqqq/walkforward.py` 생성
  - simulation.py에서 이동할 함수 6개:
    - `_local_refine_search` (simulation.py:1455-1551)
    - `run_walkforward_validation` (simulation.py:1554-1771)
    - `_simulate_stitched_periods` (simulation.py:1774-1848)
    - `calculate_stitched_walkforward_rmse` (simulation.py:1851-1934)
    - `calculate_fixed_ab_stitched_rmse` (simulation.py:1937-2022)
    - `calculate_rate_segmented_rmse` (simulation.py:2025-2114)
  - C-2에서 이동할 함수 2개 (public화, `_` 접두사 제거):
    - `_run_fixed_ab_walkforward` → `run_fixed_ab_walkforward` (validate_walkforward_fixed_ab.py:251-394)
    - `_calculate_rate_segmented_from_stitched` → `calculate_rate_segmented_from_stitched` (validate_walkforward_fixed_ab.py:397-470)
  - 필요한 import 구성:
    - core에서: `simulate`, `build_monthly_spread_map`, `compute_softplus_spread`, `calculate_validation_metrics`, `_calculate_metrics_fast`, `_validate_ffr_coverage`
    - optimization에서: `find_optimal_softplus_params`, `_prepare_optimization_data`, `_evaluate_softplus_candidate`
    - 외부: `qbt.tqqq.constants`, `qbt.tqqq.data_loader`, `qbt.tqqq.types`, `qbt.utils.parallel_executor`, `qbt.utils.data_loader`
- [x] `simulation.py`에서 이동된 6개 함수 제거
- [x] `simulation.py`에서 이동된 함수에서만 사용하던 import 정리
- [x] `validate_walkforward_fixed_ab.py` C-2 수정:
  - 로컬 함수 `_run_fixed_ab_walkforward`, `_calculate_rate_segmented_from_stitched` 제거
  - `from qbt.tqqq.walkforward import run_fixed_ab_walkforward, calculate_rate_segmented_from_stitched` 추가
  - `from qbt.tqqq.simulation import _calculate_metrics_fast` 제거 (캡슐화 위반 해소)
  - 기존 simulation import를 walkforward/simulation으로 분리:
    - walkforward로 이동: `calculate_fixed_ab_stitched_rmse`, `calculate_rate_segmented_rmse`
    - simulation 잔류: `build_monthly_spread_map`, `calculate_validation_metrics`, `compute_softplus_spread`, `simulate`
- [x] `scripts/tqqq/spread_lab/validate_walkforward.py` import 변경:
  - `from qbt.tqqq.simulation import calculate_stitched_walkforward_rmse, run_walkforward_validation` → `from qbt.tqqq.walkforward import ...`
- [x] `scripts/tqqq/spread_lab/validate_walkforward_fixed_b.py` import 변경:
  - 동일 패턴 적용
- [x] `tests/test_tqqq_simulation.py` walkforward 관련 import 변경:
  - 상단 import: `calculate_fixed_ab_stitched_rmse`, `calculate_rate_segmented_rmse`, `calculate_stitched_walkforward_rmse` → `from qbt.tqqq.walkforward import ...`
  - local import (~5개소): `_local_refine_search`, `run_walkforward_validation` → `from qbt.tqqq.walkforward import ...`
  - monkeypatch 대상 변경 (1개소): walkforward 상수(WALKFORWARD_*, DEFAULT_TRAIN_WINDOW_MONTHS) 패치 대상을 `qbt.tqqq.walkforward`로 변경

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/tqqq/CLAUDE.md` 업데이트:
  - `optimization.py` 모듈 설명 추가 (6개 함수 목록)
  - `walkforward.py` 모듈 설명 추가 (8개 함수 목록)
  - `simulation.py` 함수 목록에서 이동된 함수 제거
- [x] `PROJECT_ANALYSIS_REPORT.md` 업데이트:
  - C-2: `[향후 과제]` → `[해결됨 - Plan 7]`
  - D-4: `[향후 과제]` → `[해결됨 - Plan 7]`
  - 요약 테이블 해결 건수 업데이트 (30/37 → 32/37)
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=301, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. TQQQ시뮬레이션 / simulation.py 3개 모듈 분할 + CLI 비즈니스 로직 분리 (동작 동일)
2. TQQQ시뮬레이션 / simulation.py → core + optimization + walkforward 모듈 분할
3. TQQQ시뮬레이션 / D-4 파일 분할 + C-2 CLI 로직 분리 — 24개 함수를 3개 모듈로 재배치
4. TQQQ시뮬레이션 / 관심사 분리 리팩토링 — 시뮬레이션/최적화/워크포워드 모듈화
5. TQQQ시뮬레이션 / simulation.py 2114줄 → 3개 모듈 분할 + validate_fixed_ab 로직 추출

## 7) 리스크(Risks)

- **순환 import**: `optimization.py` → `simulation.py` → `optimization.py` 순환 위험. 의존성 방향을 `simulation(core) ← optimization ← walkforward` 단방향으로 엄격히 유지하여 방지
- **monkeypatch 대상 변경**: 테스트에서 상수를 monkeypatch할 때 대상 모듈이 변경됨. `import qbt.tqqq.simulation as sim_module` → `import qbt.tqqq.optimization as opt_module` 등으로 변경 필요. 누락 시 테스트가 의도한 상수를 패치하지 못해 실패
- **import 누락**: 함수 이동 시 해당 함수를 import하는 모든 위치를 업데이트해야 함. Grep으로 전수 검색하여 방지
- **private 함수 간 의존성**: `_local_refine_search`(walkforward)가 `_evaluate_softplus_candidate`(optimization)와 `_prepare_optimization_data`(optimization)를 사용. 동일 패키지 내 private 공유로 허용하되, import 경로 정확히 설정
- **C-2 함수 public화**: `_run_fixed_ab_walkforward` → `run_fixed_ab_walkforward`로 이름 변경. 함수 시그니처와 동작은 동일, 호출처(CLI 스크립트) import만 변경

## 8) 메모(Notes)

- 이 계획서는 `PROJECT_ANALYSIS_REPORT.md`의 C-2, D-4 항목을 대상으로 함
- C-2와 D-4를 통합한 이유: C-2 함수들이 walkforward 관심사에 속하므로, D-4에서 생성되는 `walkforward.py`에 직접 배치하면 중간 이동 불필요
- `__init__.py`는 변경 불필요: re-export 대상 3개 함수(`simulate`, `build_monthly_spread_map`, `calculate_validation_metrics`)가 모두 core에 잔류
- D-3(워크포워드 스크립트 통합), D-5(app_rate_spread_lab.py 분할), C-1/C-3(기타 CLI 로직 분리)은 별도 계획서 대상

### 분할 상세 — 각 모듈별 함수 배치

#### `simulation.py` (core, 12개 함수 잔류)

| 함수명 | 현재 줄 | 가시성 |
|--------|---------|--------|
| `_softplus` | 113-137 | Private |
| `compute_softplus_spread` | 140-177 | Public |
| `build_monthly_spread_map` | 180-228 | Public |
| `generate_static_spread_series` | 287-358 | Public |
| `_resolve_spread` | 367-416 | Private |
| `_validate_ffr_coverage` | 419-488 | Private |
| `_calculate_daily_cost` | 490-548 | Private |
| `_calculate_metrics_fast` | 656-692 | Private |
| `simulate` | 695-850 | Public |
| `_calculate_cumul_multiple_log_diff` | 853-911 | Private |
| `_save_daily_comparison_csv` | 914-1003 | Private |
| `calculate_validation_metrics` | 1006-1113 | Public |

잔류 항목: `FundingSpreadSpec` 타입 별칭 (줄 105), 로컬 상수 `COL_STATIC_*` 5개 (줄 280-284), `INTEGRITY_TOLERANCE` (줄 364)

#### `optimization.py` (신규, 6개 함수)

| 함수명 | 현재 줄 | 가시성 |
|--------|---------|--------|
| `_build_monthly_spread_map_from_dict` | 231-272 | Private |
| `_precompute_daily_costs_vectorized` | 556-615 | Private |
| `_simulate_prices_vectorized` | 618-653 | Private |
| `_evaluate_softplus_candidate` | 1121-1209 | Private |
| `_prepare_optimization_data` | 1212-1281 | Private |
| `find_optimal_softplus_params` | 1284-1447 | Public |

#### `walkforward.py` (신규, 8개 함수 = 기존 6개 + C-2 2개)

| 함수명 | 현재 위치 | 가시성 |
|--------|----------|--------|
| `_local_refine_search` | simulation.py:1455-1551 | Private |
| `run_walkforward_validation` | simulation.py:1554-1771 | Public |
| `_simulate_stitched_periods` | simulation.py:1774-1848 | Private |
| `calculate_stitched_walkforward_rmse` | simulation.py:1851-1934 | Public |
| `calculate_fixed_ab_stitched_rmse` | simulation.py:1937-2022 | Public |
| `calculate_rate_segmented_rmse` | simulation.py:2025-2114 | Public |
| `run_fixed_ab_walkforward` | validate_fixed_ab.py:251-394 | Public (C-2, 이름변경) |
| `calculate_rate_segmented_from_stitched` | validate_fixed_ab.py:397-470 | Public (C-2, 이름변경) |

### import 경로 변경 상세 — scripts/

#### `tune_softplus_params.py`

```python
# Before
from qbt.tqqq.simulation import find_optimal_softplus_params, generate_static_spread_series

# After
from qbt.tqqq.optimization import find_optimal_softplus_params
from qbt.tqqq.simulation import generate_static_spread_series
```

#### `validate_walkforward.py`

```python
# Before
from qbt.tqqq.simulation import calculate_stitched_walkforward_rmse, run_walkforward_validation

# After
from qbt.tqqq.walkforward import calculate_stitched_walkforward_rmse, run_walkforward_validation
```

#### `validate_walkforward_fixed_b.py`

```python
# Before
from qbt.tqqq.simulation import calculate_stitched_walkforward_rmse, run_walkforward_validation

# After
from qbt.tqqq.walkforward import calculate_stitched_walkforward_rmse, run_walkforward_validation
```

#### `validate_walkforward_fixed_ab.py`

```python
# Before
from qbt.tqqq.simulation import (
    _calculate_metrics_fast,  # private import 위반
    build_monthly_spread_map,
    calculate_fixed_ab_stitched_rmse,
    calculate_rate_segmented_rmse,
    calculate_validation_metrics,
    compute_softplus_spread,
    simulate,
)
# + 로컬 함수 _run_fixed_ab_walkforward, _calculate_rate_segmented_from_stitched 정의

# After
from qbt.tqqq.simulation import (
    build_monthly_spread_map,
    calculate_validation_metrics,
    compute_softplus_spread,
    simulate,
)
from qbt.tqqq.walkforward import (
    calculate_fixed_ab_stitched_rmse,
    calculate_rate_segmented_from_stitched,
    calculate_rate_segmented_rmse,
    run_fixed_ab_walkforward,
)
# 로컬 함수 제거, _calculate_metrics_fast private import 제거
```

### import 경로 변경 상세 — tests/test_tqqq_simulation.py

#### 상단 import (12개 → 3개 모듈로 분리)

```python
# Before (줄 25-37)
from qbt.tqqq.simulation import (
    _calculate_daily_cost,           # core 유지
    _evaluate_softplus_candidate,    # → optimization
    _precompute_daily_costs_vectorized, # → optimization
    _validate_ffr_coverage,          # core 유지
    calculate_fixed_ab_stitched_rmse, # → walkforward
    calculate_rate_segmented_rmse,   # → walkforward
    calculate_stitched_walkforward_rmse, # → walkforward
    calculate_validation_metrics,    # core 유지
    compute_softplus_spread,         # core 유지
    generate_static_spread_series,   # core 유지
    simulate,                        # core 유지
)

# After
from qbt.tqqq.simulation import (
    _calculate_daily_cost,
    _validate_ffr_coverage,
    calculate_validation_metrics,
    compute_softplus_spread,
    generate_static_spread_series,
    simulate,
)
from qbt.tqqq.optimization import (
    _evaluate_softplus_candidate,
    _precompute_daily_costs_vectorized,
)
from qbt.tqqq.walkforward import (
    calculate_fixed_ab_stitched_rmse,
    calculate_rate_segmented_rmse,
    calculate_stitched_walkforward_rmse,
)
```

#### local import 변경 (~27개소)

optimization 관련 (~12개소):
- `find_optimal_softplus_params` (6개소): `simulation` → `optimization`
- `_build_monthly_spread_map_from_dict` (4개소): `simulation` → `optimization`
- `_simulate_prices_vectorized` (1개소): `simulation` → `optimization`
- `_calculate_metrics_fast` (1개소): core 유지 (simulation)

walkforward 관련 (~5개소):
- `_local_refine_search` (3개소): `simulation` → `walkforward`
- `run_walkforward_validation` (2개소): `simulation` → `walkforward`

core 유지 (~10개소):
- `_softplus` (5개소), `_save_daily_comparison_csv` (2개소), `build_monthly_spread_map` (2개소), `compute_softplus_spread` (1개소): 변경 없음

#### monkeypatch 대상 변경 (5개소)

```python
# Before (줄 1730, 1873, 2061, 2173)
import qbt.tqqq.simulation as sim_module
monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_A_MIN", ...)

# After — optimization 상수 패치
import qbt.tqqq.optimization as opt_module
monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_A_MIN", ...)

# Before (줄 2268)
import qbt.tqqq.simulation as sim_module
monkeypatch.setattr(sim_module, "DEFAULT_TRAIN_WINDOW_MONTHS", ...)

# After — walkforward + optimization 상수 패치
import qbt.tqqq.walkforward as wf_module
import qbt.tqqq.optimization as opt_module
monkeypatch.setattr(wf_module, "DEFAULT_TRAIN_WINDOW_MONTHS", ...)
monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_A_MIN", ...)
```

### 진행 로그 (KST)

- 2026-02-20 23:00: 계획서 초안 작성
- 2026-02-21 00:30: Phase 1 완료 (optimization.py 생성, import 업데이트)
- 2026-02-21 01:00: Phase 2 완료 (walkforward.py 생성, C-2 로직 이동, 테스트 import 업데이트)
- 2026-02-21 01:30: Phase 3 완료 (문서 업데이트, 검증 통과 — passed=301, failed=0, skipped=0)

---
