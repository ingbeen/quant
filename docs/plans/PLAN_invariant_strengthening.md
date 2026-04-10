# Implementation Plan: 불변조건 위반 시 즉시 중단 강화

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

**작성일**: 2026-04-10 10:35
**마지막 업데이트**: 2026-04-10 10:50
**관련 범위**: backtest, tqqq, tests
**관련 문서**: 루트 CLAUDE.md, src/qbt/backtest/CLAUDE.md, src/qbt/tqqq/CLAUDE.md, tests/CLAUDE.md

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

- [x] 백테스트 도메인의 "내부 불변조건상 절대 발생할 수 없는 값"이 무음 기본값으로 대체되는 4개 지점을 RuntimeError로 강화한다.
- [x] TQQQ `_calculate_cumul_multiple_log_diff`에 누적배수 ≤ 0 사전 검증을 추가하여 `np.log` 정의역 위반을 fail-fast 처리한다.
- [x] 강화된 모든 RuntimeError가 회귀 테스트로 고정되어 있다.

## 2) 비목표(Non-Goals)

- 사용 가능한 비즈니스 케이스(예: WFE 분모 0 = IS Calmar 0)를 RuntimeError로 바꾸는 것은 본 plan 범위 밖이다. 본 plan은 "절대 발생할 수 없는 값"에만 한정한다.
- 산식·로직 변경 없음 (분기 추가만).
- analysis.py ↔ csv_export.py 의존 방향 정리는 Plan 3에서 처리한다.

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

루트 CLAUDE.md "불가능 조건 처리" 정책:

> 내부 불변조건이 보장하는 "로직상 절대 발생할 수 없는 조건"에 대한 방어 코드 규칙:
> - 조용히 기본값을 반환하거나 건너뛰지 않는다 (return, continue, 0 대체 금지)
> - RuntimeError를 발생시켜 사용자가 즉시 인지할 수 있도록 한다
> - 메시지에 "내부 불변조건 위반" 접두사와 위반된 변수/값을 포함한다

현재 다음 지점들이 정책을 위반한다:

1. `src/qbt/backtest/analysis.py:309-310` — `calculate_regime_summaries`에서 `regime_equity.iloc[0][COL_EQUITY] <= 0` 발생 시 `initial_capital = 1.0`로 무음 대체. `calculate_summary`(L184)는 동일 조건에 대해 RuntimeError를 발생시키므로 정책이 일관되지 않음.
2. `src/qbt/backtest/analysis.py:185-186` — `years == 0`(start_date == end_date) 케이스에서 `cagr = 0.0` 무음 반환. `MIN_VALID_ROWS = 2`이고 정상 백테스트는 시작/종료가 같을 수 없으므로 불변조건 위반.
3. `src/qbt/backtest/engines/portfolio_execution.py:172` — `open_prices.get(asset_id, 0.0)`. 호출부에서 `current_positions`/`order_intents`와 동일 자산 집합을 기반으로 `open_prices`를 채우므로 누락은 호출부 버그(불변조건 위반). 0.0 대체는 `int(amount/0)` 등 추가 오류를 유발.
4. `src/qbt/tqqq/simulation.py` `_calculate_cumul_multiple_log_diff` — `m_actual / m_simul` 결과에 `np.log`를 호출하기 전 사전 검증 부재. `analysis_helpers`의 signed 버전은 `M <= 0` 사전 검증으로 fail-fast를 구현하나 abs 버전은 `np.maximum(ratio, EPSILON)` clip만 수행하여 잘못된 값 통과 가능.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- 루트 `CLAUDE.md` (특히 "불가능 조건 처리", "예외 처리" 절)
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/tqqq/CLAUDE.md`
- `tests/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `analysis.calculate_regime_summaries`에서 `regime_equity` 시작 equity ≤ 0 시 RuntimeError를 발생시키며, 메시지에 regime 이름·문제 값이 포함된다.
- [x] `analysis.calculate_summary`에서 `years == 0` 케이스가 RuntimeError를 발생시킨다.
- [x] `portfolio_execution.execute_orders`에서 BUY/SELL 처리 시 `open_prices`에 자산이 없으면 RuntimeError를 발생시킨다.
- [x] `simulation._calculate_cumul_multiple_log_diff`가 `m_actual <= 0` 또는 `m_simul <= 0`인 경우 ValueError를 발생시키며, 메시지에 문제 인덱스와 원인이 포함된다.
- [x] 위 4개 변경 모두에 대한 회귀 테스트가 추가/조정되어 있다.
- [x] `poetry run python validate_project.py` 통과 (passed=501, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] 도메인 CLAUDE.md 업데이트 (정책 명시)
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일(예상)

- `src/qbt/backtest/analysis.py` — regime 시작 equity 가드, years==0 가드
- `src/qbt/backtest/engines/portfolio_execution.py` — open_prices 누락 가드
- `src/qbt/tqqq/simulation.py` — `_calculate_cumul_multiple_log_diff` 사전 검증
- `tests/test_analysis.py` — regime + years==0 RuntimeError 회귀 테스트
- `tests/test_portfolio_execution.py` — open_prices 누락 RuntimeError 회귀 테스트
- `tests/test_tqqq_simulation_outputs.py` 또는 `tests/test_tqqq_simulation_core.py` — M ≤ 0 ValueError 회귀 테스트
- `README.md`: 변경 없음

### 데이터/결과 영향

- 정상 입력에서는 결과가 동일 (분기 추가만, 기존 산식 불변).
- 비정상 입력 시 무음 0/1.0 대체 → 명시적 예외로 변경. 사용자가 결과를 신뢰할 수 없는 상태로 진행하지 않는다.

## 6) 단계별 계획(Phases)

### Phase 0 — 인바리언트 테스트 우선 작성 (레드)

**작업 내용**:

- [x] `tests/test_analysis.py`에 다음 회귀 테스트 추가 (Given/When/Then):
  - `test_regime_summaries_zero_initial_equity_raises` — regime 시작 equity가 0인 입력에 대해 `RuntimeError("내부 불변조건 위반")` 발생
  - `test_calculate_summary_zero_years_raises` — equity_df 시작/종료 날짜가 동일한 경우 `RuntimeError`
- [x] `tests/test_portfolio_execution.py`에 회귀 테스트 추가:
  - `test_buy_intent_missing_open_price_raises` — ENTER_TO_TARGET 자산이 open_prices에 없을 때 `RuntimeError`
  - `test_sell_intent_missing_open_price_raises` — EXIT_ALL 자산이 open_prices에 없을 때 `RuntimeError`
- [x] `tests/test_tqqq_simulation_outputs.py`에 회귀 테스트 추가:
  - `test_negative_actual_price_raises` — actual_prices 중 ≤ 0이 있으면 ValueError
  - `test_negative_simulated_price_raises` — simulated_prices 중 ≤ 0이 있으면 ValueError
- [x] 이 시점에 새 테스트들은 의도적으로 실패(레드) 상태로 두며 직접 실행 명령은 수행하지 않는다 (validate_project.py는 마지막 Phase에서만).

---

### Phase 1 — 구현 (그린 전환)

**작업 내용**:

- [x] `src/qbt/backtest/analysis.py`
  - `calculate_regime_summaries`에서 `initial_capital <= 0` 분기를 RuntimeError로 변경 (메시지에 regime name + 값 포함)
  - `calculate_summary`에서 `years == 0` 케이스를 RuntimeError로 변경 (메시지에 start/end date 포함)
- [x] `src/qbt/backtest/engines/portfolio_execution.py`
  - BUY 루프와 SELL 루프 진입 전 또는 내부에서 `if asset_id not in open_prices: raise RuntimeError(...)` 가드 추가 (BUY/SELL 양쪽 모두)
- [x] `src/qbt/tqqq/simulation.py`
  - `_calculate_cumul_multiple_log_diff` 함수 내 `m_actual = ...` 직후 `m_actual <= 0` 또는 `m_simul <= 0` 검사 추가 → ValueError (`analysis_helpers`의 signed 버전과 일관된 메시지 형식)

---

### Phase 2 — 도메인 문서 정합성 보강

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md`의 분석/엔진 섹션에 새로운 RuntimeError 사례를 짧게 기술 (정책 일관성)
- [x] `src/qbt/tqqq/CLAUDE.md`의 "누적배수 로그차이 지표" 섹션에 abs 버전도 M ≤ 0 사전 검증을 수행함을 명시

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] 필요한 문서 업데이트 (README.md 변경 없음)
- [x] `poetry run black .` 실행(자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=501, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 불변조건 위반 시 즉시 중단 강화 (regime / years / open_prices / 누적배수)
2. 백테스트 / 무음 기본값 제거 및 RuntimeError 강화 + 회귀 테스트
3. 백테스트 / 분석·체결·시뮬 fail-fast 정책 일관화
4. 백테스트 / silent fallback 4건 제거 + 사전 검증 1건 추가
5. 백테스트 / 정합성 가드 강화 (analysis / portfolio_execution / tqqq simulation)

## 7) 리스크(Risks)

- 기존 결과 CSV 중 1행짜리 backtest나 regime 시작 자본 0인 케이스가 있다면 재실행 시 RuntimeError가 발생할 수 있음 → 정상 입력 데이터에서는 발생 불가하므로 데이터 자체에 이상이 있는 신호로 해석.
- 기존 테스트 중 silent fallback 동작에 의존하는 케이스가 있을 가능성 → 발견 시 새 정책에 맞게 조정 (단순히 fallback 결과를 검증하던 테스트라면 RuntimeError 발생을 검증하는 형태로 교체).

## 8) 메모(Notes)

- WFE 분모 0(`walkforward.py:379-386`)는 IS Calmar = 0이 비즈니스적으로 발생 가능(IS 결과가 평탄)하므로 본 plan에서는 제외한다. 향후 표시 정책 개선이 필요하면 별도 plan으로 다룬다.
- 포트폴리오 리밸런싱의 `target_weight == 0` 케이스는 `should_rebalance`에서 이미 가드되어 있고, `build_rebalance_intents`에서는 `target_amount = 0`으로 정상 동작하므로 추가 가드가 필요 없다.

### 진행 로그 (KST)

- 2026-04-10 10:35: Plan 작성
- 2026-04-10 10:42: Phase 0 회귀 테스트 6건 추가 완료 (analysis 2건, portfolio_execution 2건, tqqq simulation 2건)
- 2026-04-10 10:46: Phase 1 구현 완료 — analysis(2건) / portfolio_execution(2건) / simulation(1건) 가드 추가
- 2026-04-10 10:48: Phase 2 도메인 CLAUDE.md 보강 완료
- 2026-04-10 10:50: 마지막 Phase 완료 — black + validate_project 통과 (passed=501, failed=0, skipped=0)

---
