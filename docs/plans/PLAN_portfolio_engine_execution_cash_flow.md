# Implementation Plan: 포트폴리오 엔진 — Execution 현실화 + Cash Flow 정확화

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

**작성일**: 2026-03-26 15:20
**마지막 업데이트**: 2026-03-26 15:20
**관련 범위**: backtest (engines/portfolio_engine.py)
**관련 문서**: `src/qbt/backtest/CLAUDE.md`, `tests/CLAUDE.md`

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

- [x] SELL 먼저 체결 → 실제 현금 확정 → BUY 수량 계산 순서 보장
- [x] BUY 총 비용 > available_cash일 때 자산별 최종 BUY amount 비례 축소 정책 적용
- [x] Step A + B 로직을 `_execute_orders` 순수 함수로 추출 (테스트 가능성 확보)
- [x] 기존 trades 포맷 및 출력 스키마 유지

## 2) 비목표(Non-Goals)

- fee/slippage 상수(`SLIPPAGE_RATE`) 변경 없음
- fractional shares 도입 없음 (int floor 유지)
- `_generate_signal_intents`, `_compute_projected_portfolio`, `_build_rebalance_intents`, `_merge_intents` 로직 변경 없음
- 출력 스키마(equity.csv, trades.csv, summary.json) 변경 없음
- 리밸런싱 임계값 및 이중 트리거 규칙 변경 없음
- 단일 자산 백테스트 엔진(`backtest_engine.py`) 변경 없음

## 3) 배경/맥락(Context)

### 현재 문제점

**문제 A — BUY 시 현금 검증 없음**

현재 Step B:

```python
shares = int(buy_capital / buy_price)
if shares > 0:
    cost = shares * buy_price
    shared_cash -= cost  # ← 음수 현금 발생 가능
```

복수 BUY intent가 있을 때 각 매수 비용의 합이 `available_cash`를 초과해도 그대로 체결된다. 현금이 음수가 되는 상태가 허용된다.

**문제 B — ENTER_TO_TARGET amount가 execution-time 현금과 연동되지 않음**

`_generate_signal_intents`에서 ENTER_TO_TARGET의 `delta_amount`는 `current_equity × target_weight`로 고정된다.
execution 당일 실제 sell 후 확보된 현금(open 가격 체결)이 반영되지 않는다. 특히 동일 날 SELL + BUY가 동시에 발생할 때 cash planning과 실제 execution 간 gap이 발생한다.

**두 문제의 관계**

- A만 해결: planning 단계의 delta_amount가 여전히 over-optimistic할 수 있음
- B만 해결: 현금 검증 로직 없이는 여전히 음수 현금 가능
- 두 문제 동시 해결 필요

### 확정된 설계 결정

| 항목 | 결정 |
|------|------|
| fee/slippage | `SLIPPAGE_RATE` 기존과 동일 적용 |
| cash 부족 정책 | 비례 축소 (merge 이후 자산별 최종 BUY amount에 동일 비율 적용) |
| fractional shares | 불허 — `int()` floor 유지, leftover cash 정상 동작으로 허용 |
| scale_factor 적용 대상 | 개별 signal/rebalance 하위 주문이 아닌, merge 이후 `OrderIntent.delta_amount` 단위 |

### `_execute_orders` 설계

```
입력:
  order_intents: dict[str, OrderIntent]   ← merged intents (전일 생성)
  open_prices:   dict[str, float]          ← 당일 open 가격
  current_positions: dict[str, int]        ← 자산별 현재 보유수량
  current_cash:  float
  entry_prices, entry_dates, entry_hold_days: 진입 정보
  current_date:  date

처리 흐름:
  1. SELL 단계: EXIT_ALL, REDUCE_TO_TARGET 체결
     - sell_price = open_price × (1 − SLIPPAGE_RATE)
     - shares_sold 계산, sell_amount = shares_sold × sell_price
     - available_cash += sell_amount
  2. CASH 확정: available_cash = current_cash + sell_proceeds
  3. BUY 단계:
     a. ENTER_TO_TARGET, INCREASE_TO_TARGET 수집
     b. 각 raw_shares = floor(delta_amount / buy_price), raw_cost = raw_shares × buy_price
     c. total_raw_cost = Σ raw_cost
     d. total_raw_cost > available_cash이면:
        scale_factor = available_cash / total_raw_cost
        adjusted_amount = delta_amount × scale_factor
        shares = floor(adjusted_amount / buy_price)
        (아니면: shares = raw_shares)
     e. 체결: cost = shares × buy_price, available_cash -= cost
  4. _ExecutionResult 반환

반환:
  _ExecutionResult(updated_cash, updated_positions, updated_entry_prices,
                   updated_entry_dates, updated_entry_hold_days,
                   new_trades, rebalanced)
```

### `_ExecutionResult` 데이터클래스

```python
@dataclass
class _ExecutionResult:
    updated_cash: float
    updated_positions: dict[str, int]
    updated_entry_prices: dict[str, float]
    updated_entry_dates: dict[str, date | None]
    updated_entry_hold_days: dict[str, int]
    new_trades: list[dict[str, Any]]
    rebalanced: bool
```

### 새로운 메인 루프 흐름

```
for i in range(0, n):
    Step A+B: _execute_orders(next_day_intents, open_prices, ...) → _ExecutionResult
              ← 상태 갱신 (cash, positions, entry info, trades 수집)
    Step C: Equity 계산 (변경 없음)
    Step D: Signal → Projected → Rebalance → Merge → next_day_intents (변경 없음)
    Step E: Equity row 기록 (변경 없음)
```

### 영향받는 규칙 (반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`

---

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다.

- [x] `_ExecutionResult` dataclass 구현 완료
- [x] `_execute_orders` 함수 구현 완료 (SELL → cash 확정 → BUY 비례 축소 포함)
- [x] 메인 루프 Step A/B가 `_execute_orders` 호출로 교체됨
- [x] Phase 0 테스트 (`TestExecuteOrders`) 모두 그린
- [x] 기존 테스트 회귀 없음 (`TestQQQTQQQSharedSignal` 등 기존 통합 테스트 통과)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=410, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트 (execution 함수 섹션 반영)
- [x] plan 체크박스 최신화

---

## 5) 변경 범위(Scope)

### 변경 대상 파일

- `src/qbt/backtest/engines/portfolio_engine.py` — `_ExecutionResult` 추가, `_execute_orders` 추출, 메인 루프 리팩토링
- `tests/test_portfolio_strategy.py` — `TestExecuteOrders` 클래스 추가
- `src/qbt/backtest/CLAUDE.md` — `portfolio_engine.py` 섹션에 `_ExecutionResult`, `_execute_orders` 설명 추가
- `README.md`: 변경 없음

### 데이터/결과 영향

- 출력 파일 스키마 변경 없음 (equity.csv, trades.csv, summary.json)
- 현금 음수 버그가 수정되므로, 복수 BUY intent가 동시에 발생하는 날 일부 수치 변동 가능 (의도된 버그 수정 결과)
- `_build_rebalance_intents`의 planning-time scale_factor는 그대로 유지됨 (execution-time scale_factor와 독립적으로 작동)

---

## 6) 단계별 계획(Phases)

### Phase 0 — `_execute_orders` 계약을 테스트로 먼저 고정 (레드)

`_execute_orders`가 아직 존재하지 않으므로 모든 테스트는 `ImportError`/`AttributeError`로 실패한다(레드). Phase 1에서 구현 후 그린으로 전환한다.

**작업 내용**:

- [x] `test_portfolio_strategy.py`에 `TestExecuteOrders` 클래스 추가:
  - [x] `test_sell_proceeds_increase_cash`: EXIT_ALL 체결 시 sell_price × shares만큼 cash 증가 계약
  - [x] `test_sell_before_buy_cash_flows`: SELL 체결 후 확보된 현금이 BUY에 활용되어 available_cash가 정확히 반영되는 계약
  - [x] `test_buy_sufficient_cash_no_scaling`: available_cash 충분 시 scale 없이 raw_shares로 체결되는 계약
  - [x] `test_buy_cash_shortage_proportional_scaling`: total_raw_cost > available_cash이면 각 BUY amount를 동일 비율로 축소한 뒤 shares를 계산하는 계약
  - [x] `test_exit_all_clears_position`: EXIT_ALL → updated_positions[asset_id] = 0
  - [x] `test_reduce_to_target_partial_position`: REDUCE_TO_TARGET → position이 delta_amount 기준 수량만큼 감소
  - [x] `test_enter_to_target_creates_new_position`: ENTER_TO_TARGET → updated_positions > 0, entry_price/date 기록
  - [x] `test_increase_to_target_weighted_avg_entry_price`: INCREASE_TO_TARGET → 가중평균 entry_price 업데이트 계약

**Validation (레드 확인)**:

- [x] 새 테스트들이 `ImportError` 또는 `AttributeError`로 실패하는지 확인
  ```
  poetry run pytest tests/test_portfolio_strategy.py::TestExecuteOrders -v
  ```

---

### Phase 1 — `_execute_orders` 구현 및 메인 루프 리팩토링 (그린 전환)

**작업 내용**:

1. **`_ExecutionResult` dataclass 추가** (`portfolio_engine.py`):
   - [x] `updated_cash: float`
   - [x] `updated_positions: dict[str, int]`
   - [x] `updated_entry_prices: dict[str, float]`
   - [x] `updated_entry_dates: dict[str, date | None]`
   - [x] `updated_entry_hold_days: dict[str, int]`
   - [x] `new_trades: list[dict[str, Any]]`
   - [x] `rebalanced_today: bool`

2. **`_execute_orders` 함수 구현** (`portfolio_engine.py`):
   - [x] SELL 단계: EXIT_ALL(전량) / REDUCE_TO_TARGET(delta_amount 기준 수량) 체결
     - `sell_price = open_price × (1 − SLIPPAGE_RATE)`
     - sell 체결 후 `available_cash += sell_amount`
     - trades 기록 (기존 포맷 유지)
     - EXIT_ALL 시 entry_prices/dates/hold_days 초기화
   - [x] CASH 확정: `available_cash = current_cash + sell_proceeds`
   - [x] BUY 단계:
     - 각 BUY intent의 `raw_shares = floor(delta_amount / buy_price)`, `raw_cost = raw_shares × buy_price`
     - `total_raw_cost = Σ raw_cost`
     - `total_raw_cost > available_cash`이면 `scale_factor = available_cash / total_raw_cost` 적용
       - `shares = floor(raw_shares × scale_factor)` (음수 현금 방지 보장)
     - ENTER_TO_TARGET(position=0): 신규 진입, entry_price/date/hold_days 기록
     - INCREASE_TO_TARGET(position>0): 가중평균 entry_price 업데이트
     - `available_cash -= shares × buy_price`
   - [x] `_ExecutionResult` 반환

3. **메인 루프 리팩토링** (`run_portfolio_backtest`):
   - [x] Step A (SELL 체결) 제거
   - [x] Step B (BUY 체결) 제거
   - [x] open_prices 사전 계산: `{asset_id: float(asset_trade_dfs[asset_id].iloc[i][COL_OPEN])}`
   - [x] `_execute_orders` 호출 및 결과 반영:
     - `shared_cash` 갱신
     - `asset_states[asset_id].position` 갱신
     - `entry_prices`, `entry_dates`, `entry_hold_days` 갱신
     - `all_trades.extend(result.new_trades)`
     - `rebalanced_today = result.rebalanced_today`

4. **`_execute_orders`를 테스트에서 import 가능하도록 공개**:
   - [x] `portfolio_engine.py`에서 `_execute_orders`, `_ExecutionResult` 심볼 확인 (pyright 통과 기준)

**Validation (그린 확인)**:

- [x] Phase 0 테스트 모두 통과
  ```
  poetry run pytest tests/test_portfolio_strategy.py::TestExecuteOrders -v
  ```
- [x] 기존 통합 테스트 회귀 없음
  ```
  poetry run pytest tests/test_portfolio_strategy.py -v
  ```

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**:

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트:
  - `portfolio_engine.py` 섹션에 `_ExecutionResult` dataclass 설명 추가
  - `_execute_orders` 함수 설명 추가 (SELL 선행 → cash 확정 → BUY 비례 축소)
- [x] `portfolio_engine.py` 모듈 docstring 업데이트 (Execution 흐름 반영)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트
- [x] 전체 Phase 체크리스트 최종 업데이트

**Validation**:

- [x] `poetry run python validate_project.py` (passed=410, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 엔진 Execution 현실화 — SELL 선행 + BUY 비례 축소 + 음수 현금 버그 수정
2. 백테스트 / 포트폴리오 엔진 Cash Flow 정확화 — _execute_orders 추출 + 가용 현금 기반 BUY 체결
3. 백테스트 / 포트폴리오 엔진 체결 로직 개선 — SELL→현금확정→BUY 흐름 + 비례 축소 정책
4. 백테스트 / 포트폴리오 엔진 _execute_orders 도입 — 음수 현금 방지 + 테스트 가능성 확보
5. 백테스트 / 포트폴리오 엔진 Execution 재설계 — _ExecutionResult + SELL 우선 + BUY 비례 축소

---

## 7) 리스크(Risks)

| 리스크 | 확률 | 완화책 |
|--------|------|--------|
| planning-time scale_factor + execution-time scale_factor 이중 적용으로 예상보다 작은 BUY 수량 | 중 | 의도된 동작 (planning은 예상, execution은 실제). 테스트로 명시적으로 고정 |
| open_prices 사전 계산이 기존 asset_trade_dfs 접근 패턴과 다르게 동작 | 저 | Phase 1 Validation에서 기존 통합 테스트로 확인 |
| `_execute_orders` 반환값 언팩 시 `asset_states` position 갱신 누락 | 저 | Phase 0 테스트에서 position 변화량을 명시적으로 고정 |

## 8) 메모(Notes)

### 핵심 설계 결정 요약

- **SELL 선행 원칙**: `available_cash = current_cash + sell_proceeds`는 execution 함수 내부에서 계산
- **BUY 비례 축소 기준**: `total_raw_cost = Σ floor(delta_amount / buy_price) × buy_price`가 available_cash를 초과할 때만 scale 적용
- **scale_factor 적용 순서**: `adjusted_amount = delta_amount × scale_factor` → `shares = floor(adjusted_amount / buy_price)`
- **leftover cash**: floor 연산으로 인한 미사용 현금은 정상 동작으로 허용
- **planning-time scale_factor 유지**: `_build_rebalance_intents`의 기존 scale_factor는 그대로 유지. execution-time scale_factor와 독립적으로 작동 (planning은 예상 기반, execution은 실제 기반)

### 진행 로그 (KST)

- 2026-03-26 15:20: 계획서 초안 작성 — 확인 질문 3개 답변 수렴 완료 후 설계 확정
- 2026-03-26 17:40: 구현 완료 — Phase 0(RED→GREEN), Phase 1, 마지막 Phase 전체 완료. passed=410, failed=0, skipped=0
  - 설계 수정: delta_amount × scale_factor → raw_shares × scale_factor (음수 현금 방지 수학적 보장)

---
