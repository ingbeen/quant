# Implementation Plan: 백테스트 규칙 위반 수정 + Dead Code + 하위호환 제거

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

**작성일**: 2026-02-19 16:00
**마지막 업데이트**: 2026-02-19 17:00
**관련 범위**: backtest, scripts, common_constants, tests
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `scripts/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] CLAUDE.md 계층 분리 원칙 위반 수정: `_calculate_monthly_returns`를 비즈니스 로직 계층으로 이동
- [x] CLAUDE.md 반올림 규칙 위반 수정: `DISPLAY_FINAL_CAPITAL` 반올림 2→0자리
- [x] CLAUDE.md 타입 힌트 규칙 위반 수정: `print_summary_stats` 타입 누락
- [x] Dead Code 정리: 미사용 상수 8개 제거 + conftest monkeypatch 정리
- [x] 하위호환 fallback 제거: `display_name` 없으면 예외 발생
- [x] 중복 None 체크 제거: `_build_band_data`의 `val is not None` 제거

## 2) 비목표(Non-Goals)

- 성능 개선 (iterrows → itertuples 등) → Plan 2에서 처리
- 코드 중복 제거 (데이터 로딩, 함수 통합 등) → Plan 2에서 처리
- `_save_results` 함수 분리 → Plan 2에서 처리
- 새로운 기능 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

전략별 분리 대규모 리팩토링 이후, 아래 문제들이 남아있다:

1. **계층 위반**: `_calculate_monthly_returns`가 CLI 스크립트(`run_single_backtest.py`)에 위치. CLAUDE.md "CLI 계층에 도메인 로직 포함 금지" 규칙 위반.

2. **반올림 규칙 위반**: `run_grid_search.py`에서 `DISPLAY_FINAL_CAPITAL`을 2자리로 반올림. CLAUDE.md "자본금 → 정수(0자리)" 규칙 위반.

3. **타입 힌트 누락**: `run_grid_search.py`의 `print_summary_stats(results_df)`에 `pd.DataFrame` 타입 힌트 없음.

4. **Dead Code**: 리팩토링으로 `result.result_dir / "signal.csv"` 동적 패턴 도입 후, `common_constants.py`의 개별 파일 경로 상수 8개(`BUFFER_ZONE_SIGNAL_PATH` 등)가 `src/`, `scripts/`에서 미사용. `tests/conftest.py`의 monkeypatch도 무효.

5. **하위호환 fallback**: `app_single_backtest.py`의 `_discover_strategies()`에서 `summary.json`에 `display_name` 없으면 디렉토리명을 fallback으로 사용. 리팩토링 완료 후에는 `display_name` 필수이므로 없으면 예외 발생해야 함.

6. **중복 None 체크**: `_build_band_data`에서 `val is not None and pd.notna(val)` — `pd.notna`가 None도 처리하므로 `val is not None` 중복.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트): 계층 분리, 반올림 규칙, 타입 힌트, 상수 관리
- `src/qbt/backtest/CLAUDE.md`: 백테스트 도메인 규칙
- `scripts/CLAUDE.md`: CLI 스크립트 규칙
- `tests/CLAUDE.md`: 테스트 작성 규칙

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `_calculate_monthly_returns`가 `src/qbt/backtest/analysis.py`에 위치하고, CLI에서는 import만 수행
- [x] `DISPLAY_FINAL_CAPITAL` 반올림이 0자리
- [x] `print_summary_stats`에 `pd.DataFrame` 타입 힌트 존재
- [x] `common_constants.py`에서 미사용 상수 8개 제거됨
- [x] `conftest.py`에서 해당 monkeypatch 8줄 제거됨
- [x] `_discover_strategies()`에서 `display_name` 없으면 `ValueError` 발생
- [x] `_build_band_data`에서 `val is not None` 중복 제거됨
- [x] 기존 테스트 전부 통과 (회귀 없음)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트 (analysis.py에 calculate_monthly_returns 추가)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/analysis.py`: `calculate_monthly_returns` 함수 추가
- `src/qbt/backtest/__init__.py`: export 추가
- `src/qbt/common_constants.py`: 미사용 상수 8개 제거
- `scripts/backtest/run_single_backtest.py`: `_calculate_monthly_returns` 제거 → import 변경
- `scripts/backtest/run_grid_search.py`: 반올림 수정 + 타입 힌트 추가
- `scripts/backtest/app_single_backtest.py`: display_name fallback 제거 + _build_band_data 수정
- `tests/conftest.py`: 불필요한 monkeypatch 제거
- `src/qbt/backtest/CLAUDE.md`: analysis.py 섹션에 함수 추가

### 데이터/결과 영향

- `grid_results.csv`의 `최종자본` 컬럼 소수점이 2자리 → 0자리로 변경됨 (다음 실행 시)
- 기존 `summary.json`에 `display_name`이 없는 경우 앱 실행 시 예외 발생 (사용자가 스크립트 재실행 필요)

## 6) 단계별 계획(Phases)

### Phase 1 — `_calculate_monthly_returns` 이동 + 반올림/타입 수정 (그린 유지)

**작업 내용**:

- [x] `src/qbt/backtest/analysis.py`에 `calculate_monthly_returns` 함수 추가 (private → public으로 네이밍 변경)
  - `_calculate_monthly_returns` 로직을 그대로 이동
  - Google 스타일 Docstring 작성 (한글)
  - 타입 힌트 완비: `(equity_df: pd.DataFrame) -> list[dict[str, object]]`
- [x] `src/qbt/backtest/__init__.py`에 `calculate_monthly_returns` export 추가
- [x] `scripts/backtest/run_single_backtest.py`에서 `_calculate_monthly_returns` 제거하고 `from qbt.backtest.analysis import calculate_monthly_returns`로 변경
- [x] `scripts/backtest/run_grid_search.py`:
  - `print_summary_stats(results_df)` → `print_summary_stats(results_df: pd.DataFrame)` 타입 힌트 추가
  - `DISPLAY_FINAL_CAPITAL: 2` → `DISPLAY_FINAL_CAPITAL: 0` 반올림 수정

---

### Phase 2 — Dead Code 제거 + 하위호환 fallback 제거 + 중복 정리 (그린 유지)

**작업 내용**:

- [x] `src/qbt/common_constants.py`에서 미사용 상수 8개 제거:
  - `BUFFER_ZONE_SIGNAL_PATH`, `BUFFER_ZONE_EQUITY_PATH`, `BUFFER_ZONE_TRADES_PATH`, `BUFFER_ZONE_SUMMARY_PATH`
  - `BUY_AND_HOLD_SIGNAL_PATH`, `BUY_AND_HOLD_EQUITY_PATH`, `BUY_AND_HOLD_TRADES_PATH`, `BUY_AND_HOLD_SUMMARY_PATH`
- [x] `tests/conftest.py`의 `mock_results_dir`, `mock_storage_paths` 두 픽스처에서 해당 8줄 monkeypatch 제거
  - 각 픽스처의 docstring에서 `BUFFER_ZONE_*_PATH`, `BUY_AND_HOLD_*_PATH` 언급도 제거
- [x] `scripts/backtest/app_single_backtest.py`의 `_discover_strategies()`에서 하위호환 fallback 제거:
  - 변경 전: `display_name = summary_data.get("display_name", subdir.name)`
  - 변경 후: `display_name`이 없거나 빈 문자열이면 `ValueError` 발생
  - 에러 메시지에 전략 디렉토리 경로 포함 (디버깅 용이성)
- [x] `scripts/backtest/app_single_backtest.py`의 `_build_band_data()`에서 중복 None 체크 제거:
  - 변경 전: `if val is not None and pd.notna(val):`
  - 변경 후: `if pd.notna(val):`

---

### Phase 3 (마지막) — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - analysis.py 섹션의 "주요 함수"에 `calculate_monthly_returns` 추가
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=293, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 규칙 위반 수정 + Dead Code 정리 + 하위호환 제거
2. 백테스트 / 계층 분리 위반 수정 + 미사용 상수 제거 + fallback 제거
3. 백테스트 / CLAUDE.md 규칙 준수를 위한 코드 정리 및 하위호환 제거
4. 백테스트 / monthly_returns 이동 + 반올림 수정 + dead code 정리
5. 백테스트 / 리팩토링 후속 정리 (규칙 위반·dead code·fallback 제거)

## 7) 리스크(Risks)

- `display_name` fallback 제거로 기존 `summary.json` 사용 시 앱 실행 오류 → 사용자가 `run_single_backtest.py` 재실행하여 해결 (사용자 사전 인지 완료)
- `common_constants.py` 상수 제거 시 숨겨진 참조가 있을 수 있음 → Grep으로 전체 검색하여 확인 완료 (src/, scripts/에서 미사용 확인됨)

## 8) 메모(Notes)

- Plan 2 (성능 + 코드 중복 제거 + 가독성)와 병행 진행 예정
- 사용자가 전략 스크립트를 재실행할 예정이므로 하위호환 불필요

### 진행 로그 (KST)

- 2026-02-19 16:00: Plan 작성 완료
- 2026-02-19 17:00: Phase 1~3 완료, 전체 검증 통과 (passed=293, failed=0, skipped=0)

---
