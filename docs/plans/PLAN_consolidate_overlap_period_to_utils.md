# Implementation Plan: extract_overlap_period 유틸 통합 + _common.py 삭제

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-02-19 22:00
**마지막 업데이트**: 2026-02-19 22:30
**관련 범위**: utils, tqqq, backtest, scripts, tests
**관련 문서**: `src/qbt/utils/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] `extract_overlap_period` 함수를 `src/qbt/utils/data_loader.py`로 이동하여 도메인 공통 유틸로 통합
- [x] `scripts/backtest/_common.py` 삭제 (인라인 로직으로 대체)
- [x] `pyproject.toml`의 `known-local-folder = ["_common"]` 삭제

## 2) 비목표(Non-Goals)

- `extract_overlap_period`의 동작 변경 (순수 리팩토링, 동작 동일)
- 새로운 공통 함수 추가 (예: `load_and_filter` 래퍼 등)
- `simulation.py` 내부의 `extract_overlap_period` 호출 로직 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

1. **로직 중복**: `scripts/backtest/_common.py`의 공통 날짜 필터링과 `src/qbt/tqqq/simulation.py`의 `extract_overlap_period`가 동일한 로직 (set 교집합 + isin 필터링)
2. **`_common.py` 의존성**: `known-local-folder` 설정이 필요하고, 로컬 폴더 import 패턴이 비표준적
3. **QQQ/TQQQ 하드코딩**: `_common.py`가 경로를 하드코딩하여 범용성이 없음

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/utils/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `src/qbt/backtest/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] `extract_overlap_period`가 `src/qbt/utils/data_loader.py`에 존재
- [x] `scripts/backtest/_common.py` 삭제됨
- [x] `pyproject.toml`에서 `known-local-folder` 삭제됨
- [x] 모든 기존 호출자의 import 경로 업데이트 완료
- [x] 테스트 이동 (`test_tqqq_simulation.py` → `test_data_loader.py`)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=293, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 관련 CLAUDE.md 문서 업데이트
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**유틸 (함수 이동 대상)**:
- `src/qbt/utils/data_loader.py` — `extract_overlap_period` 추가
- `src/qbt/utils/__init__.py` — export 추가

**TQQQ 도메인 (import 변경)**:
- `src/qbt/tqqq/simulation.py` — 로컬 정의 제거, utils import로 변경
- `src/qbt/tqqq/__init__.py` — re-export 경로 변경 (`utils.data_loader`에서 가져옴)

**백테스트 스크립트 (_common.py 제거)**:
- `scripts/backtest/run_single_backtest.py` — `_common` import 제거, 인라인 호출로 변경
- `scripts/backtest/run_grid_search.py` — 동일
- `scripts/backtest/_common.py` — **삭제**

**TQQQ 스크립트 (import 변경)**:
- `scripts/tqqq/generate_daily_comparison.py` — import 경로 변경
- `scripts/tqqq/spread_lab/tune_softplus_params.py` — import 경로 변경
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py` — import 경로 변경

**설정**:
- `pyproject.toml` — `known-local-folder` 삭제

**테스트**:
- `tests/test_data_loader.py` — `TestExtractOverlapPeriod` 클래스 추가 (이동)
- `tests/test_tqqq_simulation.py` — `TestExtractOverlapPeriod` 클래스 제거, import 정리
- `tests/test_integration.py` — import 경로 변경

**문서**:
- `src/qbt/utils/CLAUDE.md` — `extract_overlap_period` 함수 설명 추가
- `src/qbt/tqqq/CLAUDE.md` — `extract_overlap_period` 항목을 utils 참조로 변경
- `scripts/CLAUDE.md` — `_common.py` 관련 설명 제거
- `tests/CLAUDE.md` — 테스트 위치 변경 반영

### 데이터/결과 영향

- 없음 (순수 리팩토링, 동작 변경 없음)

## 6) 단계별 계획(Phases)

### Phase 1 — 함수 이동 + import 업데이트 (그린 유지)

**작업 내용**:

**1-1. `src/qbt/utils/data_loader.py`에 `extract_overlap_period` 추가**
- `simulation.py:851-901`의 함수를 그대로 이동
- "학습 포인트" 주석 제거 (utils 모듈 스타일에 맞게 간결화)
- docstring은 Google 스타일 유지 (한글)
- import: `COL_DATE`는 이미 `data_loader.py`에서 import 중

- [x] `extract_overlap_period` 함수를 `utils/data_loader.py` 하단에 추가

**1-2. `src/qbt/utils/__init__.py` export 추가**

- [x]`extract_overlap_period`를 `__all__`에 추가

**1-3. `src/qbt/tqqq/simulation.py` 수정**
- 로컬 `extract_overlap_period` 함수 정의(851-901행) 제거
- 파일 상단에 `from qbt.utils.data_loader import extract_overlap_period` 추가
- 내부 호출은 그대로 동작 (함수명 동일)

- [x]`simulation.py`에서 함수 정의 제거 + utils import 추가

**1-4. `src/qbt/tqqq/__init__.py` re-export 변경**
- `from qbt.tqqq.simulation import extract_overlap_period` → `from qbt.utils.data_loader import extract_overlap_period`

- [x]`tqqq/__init__.py` re-export 경로 변경

**1-5. TQQQ 스크립트 import 변경**
- `scripts/tqqq/generate_daily_comparison.py`: `from qbt.tqqq.simulation import extract_overlap_period` → `from qbt.utils.data_loader import extract_overlap_period`
- `scripts/tqqq/spread_lab/tune_softplus_params.py`: 동일
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py`: 동일

- [x]TQQQ 스크립트 3개 import 변경

**1-6. 백테스트 스크립트 수정 + `_common.py` 삭제**

`run_single_backtest.py` 변경:
- `from _common import load_backtest_data` 제거
- `QQQ_DATA_PATH`, `TQQQ_SYNTHETIC_DATA_PATH`는 이미 import 중 (25-34행)
- `from qbt.utils.data_loader import load_stock_data, extract_overlap_period` 추가
- `load_backtest_data(logger)` 호출을 인라인으로 변경:
  ```python
  signal_df = load_stock_data(QQQ_DATA_PATH)
  trade_df = load_stock_data(TQQQ_SYNTHETIC_DATA_PATH)
  signal_df, trade_df = extract_overlap_period(signal_df, trade_df)
  ```

`run_grid_search.py` 변경:
- `from _common import load_backtest_data` 제거
- `from qbt.common_constants import ...`에 `QQQ_DATA_PATH`, `TQQQ_SYNTHETIC_DATA_PATH` 추가
- `from qbt.utils.data_loader import load_stock_data, extract_overlap_period` 추가 (또는 기존 utils import에 추가)
- `load_backtest_data(logger)` 호출을 동일하게 인라인으로 변경

`_common.py` 삭제

- [x]`run_single_backtest.py` 수정
- [x]`run_grid_search.py` 수정
- [x]`scripts/backtest/_common.py` 삭제

**1-7. `pyproject.toml` 수정**
- `[tool.ruff.lint.isort]` 섹션에서 `known-local-folder = ["_common"]` 삭제

- [x]`pyproject.toml` 수정

---

### Phase 2 — 테스트 이동 + import 업데이트 (그린 유지)

**작업 내용**:

**2-1. `tests/test_data_loader.py`에 `TestExtractOverlapPeriod` 추가**
- `test_tqqq_simulation.py:350-402`의 `TestExtractOverlapPeriod` 클래스를 이동
- import 변경: `from qbt.utils.data_loader import extract_overlap_period`
- 기존 테스트 로직 그대로 유지 (Given-When-Then 패턴, docstring)

- [x]`TestExtractOverlapPeriod` 클래스를 `test_data_loader.py`에 추가

**2-2. `tests/test_tqqq_simulation.py` 정리**
- `TestExtractOverlapPeriod` 클래스 제거
- `extract_overlap_period` import 제거

- [x]`test_tqqq_simulation.py`에서 이동한 클래스 + import 제거

**2-3. `tests/test_integration.py` import 변경**
- `from qbt.tqqq import ... extract_overlap_period ...` → `from qbt.utils.data_loader import extract_overlap_period` (또는 tqqq re-export 유지 시 변경 불필요)
- tqqq `__init__.py`에서 re-export를 유지하므로 기존 import도 동작하지만, 정식 경로로 변경

- [x]`test_integration.py` import 변경

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**:

- [x]`src/qbt/utils/CLAUDE.md` 업데이트: `data_loader.py` 섹션에 `extract_overlap_period` 추가
- [x]`src/qbt/tqqq/CLAUDE.md` 업데이트: `extract_overlap_period` 항목을 "utils로 이동됨" 반영
- [x]`scripts/CLAUDE.md` 업데이트: `_common.py` 관련 설명 제거
- [x]`tests/CLAUDE.md` 업데이트: `extract_overlap_period` 테스트 위치 변경 반영
- [x]`poetry run black .` 실행
- [x]DoD 체크리스트 최종 업데이트 및 체크 완료
- [x]전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=293, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 유틸 / extract_overlap_period 공통 유틸 통합 + _common.py 삭제
2. 리팩토링 / 겹치는 기간 추출 함수 utils 통합 + 로컬 모듈 제거
3. 유틸 / 두 DataFrame 공통 날짜 필터 함수 utils로 이동 + 중복 제거
4. 리팩토링 / extract_overlap_period 도메인 독립 유틸로 승격
5. 유틸 / 공통 날짜 필터 통합 + backtest _common.py 삭제 + isort 설정 정리

## 7) 리스크(Risks)

- **순환 import**: `utils/data_loader.py` → `common_constants.py`만 의존하므로 순환 위험 없음
- **re-export 누락**: `tqqq/__init__.py`에서 re-export를 유지하므로 `from qbt.tqqq import extract_overlap_period` 패턴도 계속 동작
- **테스트 누락**: 기존 테스트를 그대로 이동하므로 커버리지 변화 없음

## 8) 메모(Notes)

- `extract_overlap_period`의 `simulation.py` 버전이 `_common.py` 버전보다 완성도가 높음 (빈 결과 검증 + 정렬 포함)
- `_common.py`의 DEBUG 로깅은 CLI 계층 책임이므로, 필요 시 스크립트에서 직접 추가 (현재는 생략)

### 진행 로그 (KST)

- 2026-02-19 22:00: 계획서 초안 작성
- 2026-02-19 22:30: 전체 구현 완료, validate_project.py 통과 (passed=293, failed=0, skipped=0)
