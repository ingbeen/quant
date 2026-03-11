# Implementation Plan: 리팩토링 후 문서/주석/코드 정합성 복원

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

**작성일**: 2026-03-11 20:00
**마지막 업데이트**: 2026-03-11 21:30
**관련 범위**: backtest, tqqq, scripts, tests, docs
**관련 문서**: `PLAN_backtest_cleanup.md`, `PLAN_backtest_4p_transition.md`, `PLAN_tqqq_refactoring.md`
**선행 계획서**: `PLAN_tqqq_refactoring.md` (완료 후 착수)

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

- [x] 문서-코드 불일치 7건 수정: CLAUDE.md(루트/backtest), README.md에서 삭제/추가된 파일/설정 반영
- [x] 소스코드 docstring 부정확 2건 수정: simulation.py, analysis_helpers.py의 함수/컬럼명 오참조 수정
- [x] ATR dead code 전면 제거: ATR 전략 폐기 후 walkforward.py, buffer_zone_helpers.py, types.py, constants.py에 잔존하는 ATR 코드 삭제
- [x] 테스트 커버리지 보완: spread_lab_helpers.py의 prepare_monthly_data 함수 테스트 추가

## 2) 비목표(Non-Goals)

- 비즈니스 로직 변경 (전략 실행, 시뮬레이션 결과에 영향 없음)
- hold_days_plateau 디렉토리 삭제 (legacy 데이터, 코드가 아닌 데이터 정리)
- visualization.py 변경
- 스크립트 로직 변경
- 새로운 전략/기능 추가

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

3건의 대규모 리팩토링(PLAN_backtest_cleanup, PLAN_backtest_4p_transition, PLAN_tqqq_refactoring) 완료 후, 문서/주석/소스코드 간 정합성 검사를 수행한 결과 **11건의 불일치**가 발견되었다.

불일치 유형별 분류:

**A. 문서와 실제 코드/파일 구조 불일치 (7건)**

1. 루트 CLAUDE.md 라인 88: `buffer_zone.py (9개 자산)` → 실제 8개 (qqq_4p 삭제됨)
2. 루트 CLAUDE.md 라인 92: `tqqq/types.py` 기재 → 삭제됨 (simulation.py 인라인)
3. 루트 CLAUDE.md 라인 90-96: `spread_lab_helpers.py` 누락 → 신규 추가 파일
4. README.md 라인 209: `tqqq/ (constants.py, types.py)` → types.py 삭제됨
5. README.md 라인 232: `hold_days_plateau/` 별도 기재 → 루트 CLAUDE.md는 `param_plateau/` 통합으로 기재
6. backtest CLAUDE.md 라인 83: walkforward.py 설명에 "ATR 선택적 컬럼 처리" → ATR 전략 폐기됨
7. backtest CLAUDE.md 라인 166-168: buy_and_hold CONFIGS 2개만 기재 → 실제 8개

**B. 소스코드 docstring 부정확 (2건)**

8. simulation.py 라인 425: docstring `FFR: float` → 실제 컬럼명 `VALUE`
9. analysis_helpers.py 라인 210: `simulation.py의 _lookup_ffr` → 실제 `data_loader.py의 lookup_ffr`

**C. 논리적 어긋남 (2건)**

10. ATR 전략 폐기(buffer_zone_atr_tqqq.py 삭제) 후 walkforward.py, buffer_zone_helpers.py, types.py, constants.py에 ATR 관련 코드가 광범위하게 잔존 (dead code)
11. spread_lab_helpers.py의 prepare_monthly_data 함수 테스트 부재

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `scripts/CLAUDE.md`
- `tests/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 문서-코드 불일치 7건 수정 완료 (CLAUDE.md 루트/backtest, README.md)
- [x] 소스코드 docstring 2건 수정 완료 (simulation.py, analysis_helpers.py)
- [x] ATR dead code 전면 제거 완료 (walkforward.py, buffer_zone_helpers.py, types.py, constants.py)
- [x] ATR 관련 테스트 제거 완료 (test_buffer_zone_helpers.py 내 ATR 클래스/import)
- [x] prepare_monthly_data 테스트 추가 완료 (test_tqqq_spread_lab_helpers.py)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] 필요한 문서 업데이트 (CLAUDE.md 파일들)
- [x] plan 체크박스 최신화 (Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

문서:

- `CLAUDE.md` (루트): 디렉토리 구조 수정 (9→8, types.py 삭제, spread_lab_helpers.py 추가)
- `README.md`: tqqq types.py 제거, hold_days_plateau 정리
- `src/qbt/backtest/CLAUDE.md`: buy_and_hold CONFIGS 8개 반영, walkforward ATR 설명 제거

소스 (docstring):

- `src/qbt/tqqq/simulation.py`: simulate() docstring FFR→VALUE 수정
- `src/qbt/tqqq/analysis_helpers.py`: aggregate_monthly() docstring 함수 참조 수정

소스 (ATR dead code 제거):

- `src/qbt/backtest/walkforward.py`: ATR 파라미터/로직 제거 (run_walkforward, select_best_calmar_params, build_params_schedule, load_wfo_results_from_csv)
- `src/qbt/backtest/strategies/buffer_zone_helpers.py`: BufferStrategyParams ATR 필드 제거, _calculate_atr 삭제, _detect_atr_stop_signal 삭제, run_buffer_strategy ATR 로직 제거, run_grid_search ATR 파라미터/로직 제거, _run_buffer_strategy_for_grid ATR 결과 제거
- `src/qbt/backtest/types.py`: WfoWindowResultDict ATR 필드 제거, GridSearchResult ATR 필드 제거
- `src/qbt/backtest/constants.py`: COL_ATR_PERIOD, COL_ATR_MULTIPLIER 상수 제거

테스트:

- `tests/test_buffer_zone_helpers.py`: ATR 테스트 클래스(TestATRCalculation) 삭제, ATR 관련 import 제거
- `tests/test_backtest_walkforward.py`: ATR 관련 테스트 확인 및 제거 (있는 경우)
- `tests/test_tqqq_spread_lab_helpers.py`: prepare_monthly_data 테스트 추가

### 데이터/결과 영향

- 없음 (문서/주석 수정 + dead code 제거 + 테스트 추가, 비즈니스 로직 동작 동일)

## 6) 단계별 계획(Phases)

### Phase 1 — 문서 + docstring 정합성 복원 (순수 텍스트 변경)

**작업 내용**:

- [x] `CLAUDE.md` (루트) 수정:
  - 라인 88: `(9개 자산)` → `(8개 자산)`
  - 라인 92: `types.py # TypedDict 정의 (검증 지표)` 줄 삭제
  - 라인 94 부근: `spread_lab_helpers.py # Spread Lab 앱 전용 분석 함수` 추가
- [x] `README.md` 수정:
  - 라인 209: `tqqq/ # TQQQ 시뮬레이션 (constants.py, types.py)` → types.py 제거
  - 라인 232: `hold_days_plateau/` 줄 삭제 (param_plateau 통합 설명으로 충분)
- [x] `src/qbt/backtest/CLAUDE.md` 수정:
  - 라인 83: `load_wfo_results_from_csv` 설명에서 "ATR 선택적 컬럼 처리" 제거
  - 라인 166-168: buy_and_hold CONFIGS 목록에 cross-asset 6개 추가 (SPY, IWM, EFA, EEM, GLD, TLT)
- [x] `src/qbt/tqqq/simulation.py` 수정:
  - 라인 425: `FFR: float` → `VALUE: float (0~1 비율)`
- [x] `src/qbt/tqqq/analysis_helpers.py` 수정:
  - 라인 210: `simulation.py의 _lookup_ffr와 동일한 정책` → `data_loader.py의 lookup_ffr과 동일한 정책`

---

### Phase 2 — ATR dead code 전면 제거

ATR 전략(buffer_zone_atr_tqqq)이 PLAN_backtest_cleanup에서 폐기 삭제된 후, 지원 코드가 잔존하는 상태.
PLAN_backtest_cleanup의 비목표에 "walkforward.py 모듈 변경"이 명시되어 의도적으로 유보되었으나, 현재 ATR 코드를 호출하는 코드가 전무하여 dead code로 확정.

**의존성 순서**: buffer_zone_helpers.py → walkforward.py → types.py → constants.py 순서로 정리 (역방향 의존 해소)

**작업 내용**:

- [x] `src/qbt/backtest/strategies/buffer_zone_helpers.py` 수정:
  - `BufferStrategyParams` 클래스: `atr_period`, `atr_multiplier` 필드 제거
  - `_calculate_atr()` 함수 삭제 (라인 670-713)
  - `_detect_atr_stop_signal()` 함수 삭제 (라인 716-737)
  - `run_buffer_strategy()` 내부: ATR 사전 계산 로직 제거 (use_atr, atr_series), ATR 트레일링 스탑 감지 로직 제거
  - `run_grid_search()`: `atr_period_list`, `atr_multiplier_list` 파라미터 제거, ATR 조합 생성 로직 제거
  - `_run_buffer_strategy_for_grid()`: ATR 결과 필드 설정 로직 제거
- [x] `src/qbt/backtest/walkforward.py` 수정:
  - `COL_ATR_PERIOD`, `COL_ATR_MULTIPLIER` import 제거
  - `run_walkforward()`: `atr_period_list`, `atr_multiplier_list` 파라미터 제거, `run_grid_search()` 호출에서 ATR 인자 제거, ATR 파라미터 추출 로직 제거 (use_atr ~ best_atr_multiplier), OOS 파라미터 구성에서 ATR 제거, WFO 결과에 ATR 포함 로직 제거
  - `build_params_schedule()`: ATR 파라미터 전파 로직 제거
  - `load_wfo_results_from_csv()`: ATR 컬럼 정수 보정 로직 제거
- [x] `src/qbt/backtest/types.py` 수정:
  - `WfoWindowResultDict`: `best_atr_period`, `best_atr_multiplier` 필드 제거
  - `GridSearchResult`: `atr_period`, `atr_multiplier` 필드 제거
- [x] `src/qbt/backtest/constants.py` 수정:
  - `COL_ATR_PERIOD`, `COL_ATR_MULTIPLIER` 상수 제거
- [x] `tests/test_buffer_zone_helpers.py` 수정:
  - `_calculate_atr`, `_detect_atr_stop_signal` import 제거
  - `TestATRCalculation` 클래스 및 관련 테스트 삭제
  - ATR 파라미터를 전달하는 기존 테스트가 있으면 수정
- [x] `tests/test_backtest_walkforward.py` 확인:
  - ATR 관련 테스트 코드가 있으면 제거
  - `run_walkforward()`, `run_grid_search()` 호출에서 ATR 인자 전달 부분 제거

---

### Phase 3 (마지막) — prepare_monthly_data 테스트 추가 + 최종 검증

**작업 내용**:

- [x] `tests/test_tqqq_spread_lab_helpers.py`에 `TestPrepareMonthlyData` 클래스 추가:
  - 정상 흐름 테스트: 일별 데이터 + FFR → 월별 DataFrame 반환 (month, e_m, de_m, sum_daily_m, rate_pct, dr_m 컬럼 존재 및 값 검증)
  - sum_daily_m 정확성 테스트: 일일 증분 signed 로그오차의 월별 합계가 정확한지 검증
  - 필수 컬럼 누락 시 ValueError 테스트
- [x] `src/qbt/backtest/CLAUDE.md` 갱신:
  - walkforward.py 섹션: ATR 제거 반영 (run_walkforward 시그니처, load_wfo_results_from_csv 설명)
  - buffer_zone_helpers.py 섹션: 필요 시 ATR 관련 내용 확인/제거
- [x] `poetry run black .` 실행
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=341, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 프로젝트 / 리팩토링 후 문서-코드 정합성 복원 + ATR dead code 제거
2. 프로젝트 / 문서/주석/코드 불일치 11건 수정 + ATR 잔여 코드 정리
3. 프로젝트 / CLAUDE.md 동기화 + ATR dead code 삭제 + 테스트 보강
4. 프로젝트 / 3차 리팩토링 후속 정리 (문서 9건 + ATR 제거 + 테스트 추가)
5. 프로젝트 / 정합성 검사 기반 문서 갱신, dead code 삭제, 커버리지 보완

## 7) 리스크(Risks)

- **walkforward.py 함수 시그니처 변경 (ATR 파라미터 제거)**: `run_walkforward()`와 `run_grid_search()`의 공개 API가 변경됨. 대응: 현재 ATR 파라미터를 전달하는 코드가 전무함을 grep으로 확인 완료. run_walkforward.py 스크립트는 이미 ATR 인자를 전달하지 않음
- **BufferStrategyParams 필드 제거 시 기존 테스트 오류**: ATR 필드에 의존하는 테스트가 있을 수 있음. 대응: ATR 관련 테스트는 Phase 2에서 동시에 정리
- **types.py WfoWindowResultDict 변경 시 run_walkforward.py 영향**: WFO 결과 CSV에 best_atr_period 컬럼이 포함된 기존 데이터 존재 가능. 대응: load_wfo_results_from_csv()에서 ATR 컬럼은 선택적이었으므로, 제거해도 기존 CSV 로딩에 영향 없음 (unknown 컬럼은 pandas가 자동 무시하지 않으므로, 필드 접근만 제거하면 됨)
- **prepare_monthly_data 테스트 작성 시 의존성 구성**: aggregate_monthly()와 calculate_daily_signed_log_diff()를 조합하는 통합 테스트이므로 fixture 구성이 복잡함. 대응: 최소한의 테스트 데이터로 핵심 계약만 검증 (sum_daily_m 정확성, 반환 컬럼 존재)

## 8) 메모(Notes)

- ATR dead code 유보 근거 (선행 계획서): PLAN_backtest_cleanup 비목표 "walkforward.py 모듈 변경", PLAN_backtest_4p_transition 비목표 "walkforward.py 모듈 변경 (Plan A에서 ATR 분기만 제거됨)"
- ATR dead code 제거 결정 근거: ATR 전략 모듈(buffer_zone_atr_tqqq.py) 삭제, run_walkforward.py 스크립트의 ATR 분기 삭제 완료. ATR 코드를 호출하는 프로덕션 코드가 전무하여 dead code로 확정
- hold_days_plateau/ 디렉토리: 물리적으로 존재하나 legacy 데이터. 코드 정리 범위가 아니므로 유지. 문서에서만 param_plateau/ 통합으로 정리
- Phase 0 불필요: 핵심 인바리언트/정책 변경 없음. 문서 수정 + dead code 제거 + 테스트 추가만 수행

### 진행 로그 (KST)

- 2026-03-11 20:00: 계획서 초안 작성
- 2026-03-11 21:00: Phase 1 완료 (문서 + docstring 정합성 복원)
- 2026-03-11 21:15: Phase 2 완료 (ATR dead code 전면 제거)
- 2026-03-11 21:30: Phase 3 완료 (prepare_monthly_data 테스트 추가 + 최종 검증 통과)

---
