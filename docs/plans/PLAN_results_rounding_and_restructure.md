# Implementation Plan: 결과 파일 반올림 및 results 디렉토리 구조 개편

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
**마지막 업데이트**: 2026-02-20 00:30
**관련 범위**: backtest, tqqq, utils, scripts, common_constants, tests, docs
**관련 문서**: `CLAUDE.md`(루트), `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/CLAUDE.md`

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

- [x] 목표 1: 단일 백테스트 결과 파일(signal CSV, equity CSV, trades CSV, summary JSON)의 수치를 적절한 소수점 자릿수로 반올림하여 저장
- [x] 목표 2: 루트 `CLAUDE.md`에 CSV/JSON 출력값 반올림 규칙을 코딩 표준으로 추가
- [x] 목표 3: `storage/results/` 디렉토리를 도메인별 하위 폴더(`backtest/`, `tqqq/`)로 구조 개편

## 2) 비목표(Non-Goals)

- TQQQ 도메인 CSV 파일의 반올림 변경 (이미 `analysis_helpers.py`에서 4자리 라운딩 적용 중)
- `grid_results.csv`의 반올림 변경 (이미 적절하게 처리됨)
- `meta.json` 내부 문자열 경로의 일괄 업데이트 (기존 이력 데이터, 재생성 시 자동 갱신)
- 비즈니스 로직 계층(`src/qbt/`)의 내부 계산 정밀도 변경

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

**Task 1 - 반올림**: `_save_results()` 함수가 DataFrame을 그대로 CSV로 저장하여 `43.131466450331125` 같은 불필요하게 긴 소수점 값 기록. `grid_results.csv`에는 이미 `.round()` 패턴 존재.

**Task 2 - 문서화**: CSV/JSON 출력값의 반올림 기준이 문서화되어 있지 않아 일관성 유지 어려움.

**Task 3 - 디렉토리**: `storage/results/`에 backtest와 tqqq 결과가 플랫하게 혼재. 도메인별 분리 필요.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md`, `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`, `tests/CLAUDE.md`, `docs/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] signal/equity/trades CSV 및 summary JSON 값이 적절한 소수점으로 반올림됨
- [x] `CLAUDE.md`에 반올림 규칙 추가됨
- [x] `storage/results/backtest/`, `storage/results/tqqq/` 하위 구조로 경로 상수 변경됨
- [x] 기존 파일이 새 경로로 이동됨
- [x] 테스트 픽스처 업데이트 완료
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트 (README/CLAUDE/plan 등)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일

**소스 코드:**
- `scripts/backtest/run_single_backtest.py` — `_save_results()` 함수에 `.round()` 적용
- `src/qbt/common_constants.py` — `BACKTEST_RESULTS_DIR`, `TQQQ_RESULTS_DIR` 추가, 경로 상수 변경
- `src/qbt/tqqq/constants.py` — `RESULTS_DIR` → `TQQQ_RESULTS_DIR` import 변경

**테스트:**
- `tests/conftest.py` — `mock_results_dir`, `mock_storage_paths` 픽스처 업데이트
- `tests/test_integration.py` — 하드코딩 경로 수정

**하드코딩 로그 메시지 수정 (8개 파일):**
- `scripts/backtest/run_single_backtest.py` (260행)
- `scripts/backtest/run_grid_search.py` (240행)
- `scripts/tqqq/generate_daily_comparison.py` (144행)
- `scripts/tqqq/spread_lab/tune_softplus_params.py` (206행)
- `scripts/tqqq/spread_lab/validate_walkforward.py` (159행)
- `scripts/tqqq/spread_lab/generate_rate_spread_lab.py` (180행)
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_b.py` (169행)
- `scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py` (249행)

**문서:**
- `CLAUDE.md` (루트) — 반올림 규칙 추가, 디렉토리 구조 업데이트, CSV 파일 저장 위치 업데이트
- `src/qbt/backtest/CLAUDE.md` — CSV 경로 참조 업데이트
- `src/qbt/tqqq/CLAUDE.md` — CSV 경로 참조 업데이트
- `README.md` — 결과 파일 경로 업데이트

### 데이터/결과 영향

- 기존 CSV/JSON 결과 파일의 수치 정밀도 변경 (Task 1)
- 기존 `storage/results/` 파일이 하위 디렉토리로 물리적 이동 필요 (Task 3)
- `meta.json`은 `storage/results/meta.json` 위치 유지

## 6) 단계별 계획(Phases)

### Phase 1 — Task 1: 결과 파일 반올림 적용 (그린 유지)

**작업 내용**:

- [x] `scripts/backtest/run_single_backtest.py`의 `_save_results()` 함수 수정:

  **1-1. signal CSV 반올림** (to_csv 직전에 추가):
  ```python
  ma_col = f"ma_{ma_window}"
  signal_export = signal_export.round({
      COL_OPEN: 2, COL_HIGH: 2, COL_LOW: 2, COL_CLOSE: 2,
      ma_col: 2,        # 가격: 소수점 2자리
      "change_pct": 2,  # 백분율: 소수점 2자리
  })
  ```
  주의: `_save_results()`에 `ma_window` 파라미터가 이미 존재하므로 동적 컬럼명 구성 가능.

  **1-2. equity CSV 반올림** (to_csv 직전에 추가):
  ```python
  equity_export = equity_export.round({
      "equity": 0,           # 자본금: 정수
      "buffer_zone_pct": 4,  # 비율: 소수점 4자리
      "upper_band": 2,       # 가격: 소수점 2자리
      "lower_band": 2,       # 가격: 소수점 2자리
      "drawdown_pct": 2,     # 백분율: 소수점 2자리
  })
  ```

  **1-3. trades CSV 반올림** (to_csv 직전에 추가):
  ```python
  trades_export = trades_export.round({
      "entry_price": 2,      # 가격: 소수점 2자리
      "exit_price": 2,
      "pnl": 0,              # 자본금: 정수
      "pnl_pct": 4,          # 비율(0~1): 소수점 4자리
      "buffer_zone_pct": 4,  # 비율: 소수점 4자리
  })
  ```

  **1-4. summary JSON 반올림** (`summary_data` dict 구성 시):
  ```python
  "summary": {
      "initial_capital": round(float(str(summary["initial_capital"]))),
      "final_capital": round(float(str(summary["final_capital"]))),
      "total_return_pct": round(float(str(summary["total_return_pct"])), 2),
      "cagr": round(float(str(summary["cagr"])), 2),
      "mdd": round(float(str(summary["mdd"])), 2),
      "win_rate": round(float(str(summary["win_rate"])), 2),
      ...
  },
  "params": {
      "buffer_zone_pct": round(buffer_zone_pct, 4),
      "initial_capital": round(DEFAULT_INITIAL_CAPITAL),
      ...
  },
  ```

---

### Phase 2 — Task 3: 디렉토리 구조 개편 - 상수 및 소스 변경 (그린 유지)

**작업 내용**:

- [x] `src/qbt/common_constants.py` 수정:
  ```python
  RESULTS_DIR: Final = STORAGE_DIR / "results"  # 유지
  BACKTEST_RESULTS_DIR: Final = RESULTS_DIR / "backtest"  # 추가
  TQQQ_RESULTS_DIR: Final = RESULTS_DIR / "tqqq"          # 추가

  GRID_RESULTS_PATH: Final = BACKTEST_RESULTS_DIR / "grid_results.csv"
  SINGLE_BACKTEST_SIGNAL_PATH: Final = BACKTEST_RESULTS_DIR / "single_backtest_signal.csv"
  SINGLE_BACKTEST_EQUITY_PATH: Final = BACKTEST_RESULTS_DIR / "single_backtest_equity.csv"
  SINGLE_BACKTEST_TRADES_PATH: Final = BACKTEST_RESULTS_DIR / "single_backtest_trades.csv"
  SINGLE_BACKTEST_SUMMARY_PATH: Final = BACKTEST_RESULTS_DIR / "single_backtest_summary.json"
  META_JSON_PATH: Final = RESULTS_DIR / "meta.json"  # 유지
  ```

- [x] `src/qbt/tqqq/constants.py` 수정:
  - import에서 `RESULTS_DIR` → `TQQQ_RESULTS_DIR`로 변경
  ```python
  from qbt.common_constants import (DISPLAY_DATE, ETC_DIR, TQQQ_RESULTS_DIR, STOCK_DIR)
  TQQQ_DAILY_COMPARISON_PATH: Final = TQQQ_RESULTS_DIR / "tqqq_daily_comparison.csv"
  SPREAD_LAB_DIR: Final = TQQQ_RESULTS_DIR / "spread_lab"
  ```
  SPREAD_LAB_DIR 파생 경로들은 `SPREAD_LAB_DIR` 기반이므로 자동 반영.

- [x] 하드코딩 로그 메시지 8개 파일 수정:
  `"storage/results/meta.json"` → `f"{META_JSON_PATH}"` (각 파일에 `META_JSON_PATH` import 추가)

- [x] 기존 결과 파일 물리적 이동:
  ```bash
  mkdir -p storage/results/backtest storage/results/tqqq
  mv storage/results/grid_results.csv storage/results/backtest/
  mv storage/results/single_backtest_*.csv storage/results/single_backtest_*.json storage/results/backtest/
  mv storage/results/tqqq_daily_comparison.csv storage/results/tqqq/
  mv storage/results/spread_lab storage/results/tqqq/
  ```

---

### Phase 3 — 테스트 수정 (그린 유지)

**작업 내용**:

- [x] `tests/conftest.py`의 `mock_results_dir` 픽스처 수정:
  - `backtest/`, `tqqq/` 하위 디렉토리 생성
  - `common_constants.BACKTEST_RESULTS_DIR`, `common_constants.TQQQ_RESULTS_DIR` 패치
  - `tqqq_constants.TQQQ_DAILY_COMPARISON_PATH`, `tqqq_constants.SPREAD_LAB_DIR` 패치
  - 반환 dict에 `BACKTEST_RESULTS_DIR`, `TQQQ_RESULTS_DIR` 추가

- [x] `tests/conftest.py`의 `mock_storage_paths` 픽스처 수정 (동일 패턴)

- [x] `tests/test_integration.py`의 `test_full_tqqq_pipeline` 수정 (235행):
  `mock_storage_paths["RESULTS_DIR"] / "tqqq_daily_comparison.csv"` → `mock_storage_paths["TQQQ_RESULTS_DIR"] / "tqqq_daily_comparison.csv"`

참고: 테스트에서 `SPREAD_LAB_DIR` 파생 경로를 직접 사용하는 테스트는 없음 (검증 완료).

---

### Phase 4 (마지막 Phase) — 문서 정리 및 최종 검증

**작업 내용**:

- [x] 루트 `CLAUDE.md` 수정:
  - "코딩 표준" 섹션에 **출력 데이터 반올림 규칙** 추가 (정밀도 가이드라인 테이블 포함)
  - "디렉토리 구조" 섹션 업데이트 (results 하위에 backtest/, tqqq/ 반영)
  - "데이터 처리 규칙" > "CSV 파일 저장 위치" 섹션을 backtest/tqqq로 분리

- [x] `src/qbt/backtest/CLAUDE.md` 수정: CSV 경로를 `storage/results/backtest/`로 업데이트
- [x] `src/qbt/tqqq/CLAUDE.md` 수정: CSV 경로를 `storage/results/tqqq/`로 업데이트
- [x] `README.md` 수정: 모든 `storage/results/` 경로를 새 구조로 업데이트
- [x] `poetry run black .` 실행
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료

**Validation**:

- [x] `poetry run python validate_project.py` (passed=284, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 결과 파일 / CSV·JSON 반올림 적용 + results 디렉토리 도메인별 구조 개편
2. 백테스트·TQQQ / 출력 정밀도 규칙 추가 및 결과 경로 backtest·tqqq 분리
3. 결과 파일 / 소수점 반올림 + storage/results 하위 디렉토리 분리 + 문서 업데이트
4. 프로젝트 / 출력 반올림 규칙 도입 + results 폴더 구조 개편 (backtest/tqqq 분리)
5. 결과 파일 / 반올림 기준 코딩 표준 추가 + 경로 상수 도메인별 분리

## 7) 리스크(Risks)

- **tqqq constants import-time 값 캡처**: `SPREAD_LAB_DIR`과 그 파생 경로는 import 시점에 계산됨. 소스 변경으로 프로덕션은 문제 없으나, 테스트 `conftest.py`에서 `tqqq_constants.SPREAD_LAB_DIR`도 명시적 패치 필요.
- **기존 결과 파일 이동 누락**: 물리적 이동을 잊으면 대시보드 앱이 파일을 찾지 못함. Phase 2에서 확인.
- **반올림으로 인한 미세 표시 변화**: 시각적으로 더 깔끔해지므로 수용 가능.

## 8) 메모(Notes)

### 참고 패턴

- `run_grid_search.py` 181-190행: DataFrame `.round()` 패턴 (Task 1 참고)
- `_save_results()` 246-250행: `round(float(str(...)), 2)` 패턴 (JSON용)

### 핵심 결정 사항

1. `equity` 컬럼: `round(0)` 적용 시 float64 유지 (`10000000.0`). 기존 패턴과 일관.
2. MA 컬럼명: `f"ma_{ma_window}"` 키로 동적 구성.
3. `RESULTS_DIR` 유지: `META_JSON_PATH`가 사용하며, 향후 확장성 고려.
4. `tqqq/constants.py`의 `__all__`: 수정 불필요 (기존 import 경로만 변경).

### 진행 로그 (KST)

- 2026-02-19 22:00: Draft 작성 완료
- 2026-02-20 00:30: Phase 1~4 완료, validate_project.py 통과 (passed=284, failed=0, skipped=0)
