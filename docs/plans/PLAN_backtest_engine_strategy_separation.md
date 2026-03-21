# Implementation Plan: 백테스트 엔진-전략 분리 리팩터링

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

**작성일**: 2026-03-21 00:00
**마지막 업데이트**: 2026-03-21 03:00
**관련 범위**: backtest, scripts/backtest, tests
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

- [x] 단일 백테스트 엔진과 포트폴리오 엔진을 별도 파일로 분리한다
- [x] 버퍼존 전략과 B&H 전략을 엔진에서 독립적인 클래스로 추출하고 공통 인터페이스(`SignalStrategy` Protocol)를 정의한다
- [x] 엔진 공통 함수(체결, equity 기록)와 전략 공통 함수(신호 감지, 밴드 계산)를 각각 별도 파일로 분리한다
- [x] 이후 전략 추가 시 엔진 파일을 수정하지 않아도 되는 구조를 만든다

## 2) 비목표(Non-Goals)

- 기존 백테스트 결과 수치의 변경: 리팩터링이므로 동일 입력에 동일 결과를 보장한다
- 포트폴리오 설정 구조(`PortfolioConfig`, `PORTFOLIO_CONFIGS`)의 대규모 변경
- 그리드 서치 로직 변경
- 워크포워드 검증 로직 변경
- Streamlit 대시보드 앱 수정

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

- `buffer_zone_helpers.py` 한 파일에 전략 로직(신호 감지, 밴드 계산)과 엔진 로직(체결, equity, 그리드 서치)이 뒤섞여 있음
- `portfolio_strategy.py`가 `buffer_zone_helpers.py`의 private 함수(`_compute_bands`, `_detect_buy_signal`, `_detect_sell_signal`)를 `# type: ignore[import]`와 `# pyright: ignore[reportPrivateUsage]`로 억지 import하는 코드 스멜 존재
- 새 전략 추가 시 엔진 로직을 수정해야 하는 구조적 결합
- 단일 백테스트와 포트폴리오가 동일 전략 파일을 공유하지 못하고 엔진이 전략 로직을 복제하는 상황

### 현재 의존 관계 (삭제될 파일 중심)

```
buffer_zone_helpers.py (삭제 대상)
  ← buffer_zone.py
  ← portfolio_strategy.py (private import 코드 스멜)
  ← walkforward.py
  ← backtest/__init__.py
  ← strategies/__init__.py
  ← scripts/backtest/run_param_plateau_all.py
  ← scripts/backtest/run_walkforward.py
  ← tests/test_buffer_zone_helpers.py
  ← tests/test_backtest_walkforward.py
  ← tests/test_integration.py

portfolio_strategy.py (삭제 대상)
  ← scripts/backtest/run_portfolio_backtest.py
  ← tests/test_portfolio_strategy.py
```

### 목표 파일 구조

```
src/qbt/backtest/
├── strategies/
│   ├── __init__.py               (수정)
│   ├── strategy_common.py        (신규) 전략 공통: SignalStrategy Protocol, 신호/밴드 함수
│   ├── buffer_zone.py            (수정) BufferZoneStrategy 클래스 추가
│   └── buy_and_hold.py           (수정) BuyAndHoldStrategy 클래스 추가
├── engines/
│   ├── __init__.py               (신규)
│   ├── engine_common.py          (신규) 엔진 공통: PendingOrder, 체결/equity 함수
│   ├── backtest_engine.py        (신규) 단일 백테스트 엔진 (run_backtest, run_grid_search)
│   └── portfolio_engine.py       (신규) 포트폴리오 엔진 (run_portfolio_backtest)
├── strategies/buffer_zone_helpers.py  (삭제)
├── portfolio_strategy.py              (삭제)
└── (기타 파일 유지)
```

### 핵심 설계 결정

**1. SignalStrategy Protocol**

두 엔진이 공통으로 사용하는 전략 인터페이스:

```python
class SignalStrategy(Protocol):
    def check_buy(
        prev_close, cur_close, prev_upper, cur_upper,
        hold_state: HoldState | None,
        hold_days_required: int,   # 엔진이 파라미터로 전달
    ) -> tuple[bool, HoldState | None]: ...

    def check_sell(
        prev_close, cur_close, prev_lower, cur_lower
    ) -> bool: ...
```

`should_always_hold()` 미사용 이유: `check_buy()`가 항상 True를 반환하는 것만으로 "즉시 진입" 동작을 표현할 수 있다. 엔진이 day 0에도 모든 전략에 대해 `check_buy()`를 호출하므로, B&H는 자연스럽게 즉시 매수 pending을 생성한다. 별도 메서드로 분리하면 Protocol이 행동이 아닌 메타 정보를 노출하게 되어 설계 원칙에 위배된다.

**2. 전략 클래스**

- `BufferZoneStrategy`: `check_buy`에 hold_days 상태머신 포함, `check_sell`은 하향돌파 감지
- `BuyAndHoldStrategy`: `check_buy` 항상 `(True, None)` (파라미터 무시), `check_sell` 항상 `False`

**3. 단일 백테스트 엔진 — DI(의존성 주입) 방식**

```python
# engines/backtest_engine.py
def run_backtest(strategy: SignalStrategy, signal_df, trade_df, params, ...) -> tuple[...]
```
- `create_runner`(buffer_zone.py)와 `create_runner`(buy_and_hold.py)가 각자 전략 객체를 생성해서 주입
- `walkforward.py`도 `BufferZoneStrategy()` 인스턴스를 생성해서 직접 호출

**4. 포트폴리오 엔진 — 팩토리 방식**

`AssetSlotConfig.strategy_type: str`은 유지 (기존 configs 수정 최소화). 포트폴리오 엔진 내부에 팩토리 함수를 두어 전략 객체를 생성:

```python
# engines/portfolio_engine.py 내부
def _create_strategy_for_slot(slot: AssetSlotConfig) -> SignalStrategy:
    if slot.strategy_type == "buffer_zone":
        return BufferZoneStrategy()
    elif slot.strategy_type == "buy_and_hold":
        return BuyAndHoldStrategy()
    raise ValueError(...)
```

엔진의 메인 루프는 `slot.strategy_type` 문자열 분기 대신 `strategy.check_buy()`, `strategy.check_sell()`을 호출한다.

- **day 0 초기화**: 모든 전략에 대해 `check_buy(prev=cur=day0_data)`를 호출한다. B&H는 항상 True → 즉시 pending buy 생성. BufferZone은 `prev==cur`이면 상향돌파 조건(`prev_close <= prev_upper AND cur_close > cur_upper`)이 성립 불가 → False → 아무것도 안 함.
- **position=0 재진입**: 루프 내에서 항상 `check_buy()`를 호출. B&H → 즉시 True, BufferZone → 신호 대기.
- `signal_state="buy"` 초기화도 day 0 `check_buy()` 결과로 자동 결정 (B&H: True → "buy", BufferZone: False → "sell").

**5. 이전 파일 삭제 전략 (backward compat → 삭제)**

Phase 2-3에서 구 함수들이 `engines/`로 이전된 후, `buffer_zone_helpers.py`와 `portfolio_strategy.py`는 re-export wrapper로 잠시 유지한다. Phase 4에서 모든 import 경로를 업데이트한 후 삭제한다.

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `src/qbt/backtest/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`
- 루트 `CLAUDE.md`

## 4) 완료 조건(Definition of Done)

> Done은 "서술"이 아니라 "체크리스트 상태"로만 판단합니다. (정의/예외는 docs/CLAUDE.md)

- [x] 기능 요구사항 충족: 단일 백테스트, 포트폴리오 백테스트, 그리드 서치, WFO 모두 동작
- [x] `SignalStrategy` Protocol 구현 및 `BufferZoneStrategy`, `BuyAndHoldStrategy` 클래스 완성
- [x] `engines/backtest_engine.py`, `engines/portfolio_engine.py` 신규 생성 완료
- [x] `buffer_zone_helpers.py`, `portfolio_strategy.py` 삭제 완료
- [x] private import 코드 스멜 (`# type: ignore[import]`, `# pyright: ignore[reportPrivateUsage]`) 모두 제거
- [x] 회귀/신규 테스트 추가 (`test_strategy_interface.py`)
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; passed=390, failed=0, skipped=0)
- [x] `poetry run black .` 실행 완료 (마지막 Phase에서 자동 포맷 적용)
- [x] `src/qbt/backtest/CLAUDE.md` 업데이트 완료
- [x] plan 체크박스 최신화(Phase/DoD/Validation 모두 반영)

## 5) 변경 범위(Scope)

### 신규 생성 파일

| 파일 | 내용 |
|------|------|
| `src/qbt/backtest/strategies/strategy_common.py` | `SignalStrategy` Protocol, `HoldState`, `PendingOrderConflictError`, `compute_bands`, `detect_buy_signal`, `detect_sell_signal` |
| `src/qbt/backtest/engines/__init__.py` | 패키지 초기화 |
| `src/qbt/backtest/engines/engine_common.py` | `PendingOrder`, `TradeRecord`, `EquityRecord`, `execute_buy_order`, `execute_sell_order`, `record_equity` |
| `src/qbt/backtest/engines/backtest_engine.py` | `run_backtest(strategy, ...)`, `run_grid_search(...)` |
| `src/qbt/backtest/engines/portfolio_engine.py` | `run_portfolio_backtest(...)`, `compute_portfolio_effective_start_date(...)` |
| `tests/test_strategy_interface.py` | `SignalStrategy` Protocol 계약 테스트 |

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/qbt/backtest/strategies/buffer_zone.py` | `BufferZoneStrategy` 클래스 추가, `create_runner` → `backtest_engine.run_backtest` 사용 |
| `src/qbt/backtest/strategies/buy_and_hold.py` | `BuyAndHoldStrategy` 클래스 추가, `create_runner` → `backtest_engine.run_backtest` 사용 |
| `src/qbt/backtest/strategies/__init__.py` | import 경로 업데이트 |
| `src/qbt/backtest/__init__.py` | import 경로 업데이트 |
| `src/qbt/backtest/walkforward.py` | `backtest_engine.run_backtest` 직접 사용 |
| `src/qbt/backtest/portfolio_types.py` | 필요 시 수정 |
| `scripts/backtest/run_single_backtest.py` | import 경로 업데이트 |
| `scripts/backtest/run_portfolio_backtest.py` | import 경로 업데이트 |
| `scripts/backtest/run_param_plateau_all.py` | import 경로 업데이트 |
| `scripts/backtest/run_walkforward.py` | import 경로 업데이트 |
| `tests/test_buffer_zone_helpers.py` | import 경로 업데이트 (`strategy_common`, `engine_common`, `backtest_engine`) |
| `tests/test_backtest_walkforward.py` | import 경로 업데이트 |
| `tests/test_integration.py` | import 경로 업데이트 |
| `tests/test_portfolio_strategy.py` | import 경로 업데이트 |
| `tests/test_buy_and_hold.py` | `BuyAndHoldStrategy` 관련 테스트 추가 |
| `tests/test_buffer_zone.py` | `BufferZoneStrategy` 관련 테스트 추가 |
| `src/qbt/backtest/CLAUDE.md` | 새 구조 반영 |

### 삭제 파일

| 파일 | 이전 위치 |
|------|----------|
| `src/qbt/backtest/strategies/buffer_zone_helpers.py` | 내용이 `strategy_common.py`, `engine_common.py`, `backtest_engine.py`로 분해됨 |
| `src/qbt/backtest/portfolio_strategy.py` | 내용이 `engines/portfolio_engine.py`로 이전됨 |

### 데이터/결과 영향

- 백테스트 결과(equity, trades, summary) 수치 무변경: 동일한 알고리즘을 재구성하는 리팩터링
- CSV/JSON 출력 스키마 무변경
- 기존 `storage/results/` 파일 재생성 불필요

## 6) 단계별 계획(Phases)

---

### Phase 0 — 전략 인터페이스 고정 + 공통 파일 신규 생성 (레드 허용)

> 새로운 `SignalStrategy` Protocol 인터페이스 계약을 테스트로 먼저 고정한다.
> 전략 클래스 stub(NotImplementedError)을 두어 ImportError 없이 테스트가 실패(레드)하도록 한다.

**작업 내용**:

- [x] `src/qbt/backtest/strategies/strategy_common.py` 신규 생성
  - `SignalStrategy` Protocol 정의 (`check_buy`, `check_sell`)
  - `HoldState` TypedDict (현재 `buffer_zone_helpers.py`에서 이전)
  - `PendingOrderConflictError` 예외 클래스 (현재 `buffer_zone_helpers.py`에서 이전)
  - `compute_bands(ma_value, buy_buffer_pct, sell_buffer_pct) -> tuple[float, float]`
  - `detect_buy_signal(prev_close, close, prev_upper, upper) -> bool`
  - `detect_sell_signal(prev_close, close, prev_lower, lower) -> bool`
  - ※ `buffer_zone_helpers.py`는 아직 건드리지 않음 (기존 테스트 그린 유지)
- [x] `src/qbt/backtest/engines/` 디렉토리 및 `__init__.py` 신규 생성
- [x] `src/qbt/backtest/engines/engine_common.py` 신규 생성
  - `PendingOrder` dataclass (현재 `buffer_zone_helpers.py`에서 이전)
  - `TradeRecord` TypedDict (현재 `buffer_zone_helpers.py`에서 이전)
  - `EquityRecord` TypedDict (현재 `buffer_zone_helpers.py`에서 이전)
  - `execute_buy_order(order, open_price, execute_date, capital, position) -> tuple`
  - `execute_sell_order(order, open_price, execute_date, capital, position, entry_price, entry_date) -> tuple`
  - `record_equity(current_date, capital, position, close_price, ...) -> EquityRecord`
  - ※ 기존 `buffer_zone_helpers.py`의 private 함수를 공개 이름으로 재정의
- [x] `src/qbt/backtest/strategies/buffer_zone.py`에 `BufferZoneStrategy` stub 추가
  - `check_buy(...)`: `raise NotImplementedError`
  - `check_sell(...)`: `raise NotImplementedError`
- [x] `src/qbt/backtest/strategies/buy_and_hold.py`에 `BuyAndHoldStrategy` stub 추가
  - `check_buy(...)`: `raise NotImplementedError`
  - `check_sell(...)`: `raise NotImplementedError`
- [x] `tests/test_strategy_interface.py` 신규 생성 (인터페이스 계약 테스트, 레드)
  - `TestBufferZoneStrategyInterface`: `check_buy` stub 호출 시 `NotImplementedError` 발생 확인
  - `TestBuyAndHoldStrategyInterface`: `check_buy` stub 호출 시 `NotImplementedError` 발생 확인
  - `TestSignalStrategyProtocol`: `isinstance(strategy, SignalStrategy)` Protocol 준수 확인
  - ※ Phase 0에서는 "NotImplementedError 발생"을 확인하는 테스트 → 의도적 레드가 아닌 정상 통과
  - ※ 실제 동작 계약 테스트(예: B&H는 항상 True 반환)는 Phase 0에서 `@pytest.mark.xfail(strict=True)`로 마킹 → Phase 1에서 xfail → pass로 전환

**Validation**:
- 기존 테스트: 모두 통과 (그린)
- `test_strategy_interface.py`의 계약 테스트: `xfail` (레드 허용)

---

### Phase 1 — 전략 클래스 구현 (그린)

**작업 내용**:

- [x] `src/qbt/backtest/strategies/buffer_zone.py`: `BufferZoneStrategy` 완전 구현
  - `check_buy(prev_close, cur_close, prev_upper, cur_upper, hold_state, hold_days_required) -> tuple[bool, HoldState | None]`
    - `hold_days_required == 0`: 즉시 `detect_buy_signal` 결과 반환
    - `hold_days_required > 0`: hold_state 상태머신 업데이트 후 반환
  - `check_sell(prev_close, cur_close, prev_lower, cur_lower) -> bool`
    - `detect_sell_signal` 결과 반환
  - `strategy_common.py`에서 `detect_buy_signal`, `detect_sell_signal`, `HoldState` import
- [x] `src/qbt/backtest/strategies/buy_and_hold.py`: `BuyAndHoldStrategy` 완전 구현
  - `check_buy(...) -> (True, None)`: 항상 매수 (파라미터 무시)
  - `check_sell(...) -> False`: 항상 매도 안 함 (파라미터 무시)
- [x] `tests/test_strategy_interface.py`: xfail 테스트 → 실제 동작 계약 테스트로 전환
  - `BufferZoneStrategy.check_buy` 정상 동작 검증 (신호 감지, hold_days 포함)
  - `BuyAndHoldStrategy.check_buy` 항상 `(True, None)` 반환 검증
  - `BuyAndHoldStrategy.check_sell` 항상 `False` 반환 검증
  - day 0 check_buy 패턴 검증: `prev==cur` 데이터로 호출 시 B&H → True, BufferZone → False

**Validation**:
- `poetry run pytest tests/test_strategy_interface.py -v` (전부 통과)
- 기존 테스트 전부 통과 (그린 유지)

---

### Phase 2 — 단일 백테스트 엔진 분리 (그린)

**작업 내용**:

- [x] `src/qbt/backtest/engines/backtest_engine.py` 신규 생성
  - `_validate_backtest_inputs(strategy, params, signal_df, trade_df, ma_col)`: 입력 검증
  - `_run_backtest_for_grid(params: BufferStrategyParams) -> GridSearchResult`: 병렬 그리드 서치용 헬퍼 (module-level, pickle 가능)
  - `run_backtest(strategy, signal_df, trade_df, params, log_trades, strategy_name, params_schedule) -> tuple[trades_df, equity_df, summary]`
    - `engine_common.py`의 `execute_buy_order`, `execute_sell_order`, `record_equity` 사용
    - `strategy.check_buy()`, `strategy.check_sell()` 호출
    - 기존 `run_buffer_strategy`와 동일한 로직, 동일한 반환 타입
  - `run_grid_search(strategy_cls, signal_df, trade_df, ...) -> pd.DataFrame`
    - `_run_backtest_for_grid` + WORKER_CACHE 패턴 유지
- [x] `src/qbt/backtest/strategies/buffer_zone_helpers.py`: `run_buffer_strategy` → `backtest_engine.run_backtest` 래핑으로 교체 (backward compat 유지, 삭제는 Phase 4)
  - `run_buffer_strategy(signal_df, trade_df, params, ...) -> ...`: `BufferZoneStrategy()` 생성 후 `backtest_engine.run_backtest` 위임
  - `run_grid_search(...)`: `backtest_engine.run_grid_search` 위임
- [x] `src/qbt/backtest/strategies/buffer_zone.py`: `create_runner` 내부의 `run_buffer_strategy` 호출 → `backtest_engine.run_backtest(BufferZoneStrategy(), ...)` 로 변경
- [x] `src/qbt/backtest/walkforward.py`: `run_buffer_strategy` 호출 → `backtest_engine.run_backtest(BufferZoneStrategy(), ...)` 로 변경
- [x] `scripts/backtest/run_param_plateau_all.py`: `run_buffer_strategy` import → `backtest_engine.run_backtest` + `BufferZoneStrategy` import로 변경
- [x] `scripts/backtest/run_walkforward.py`: `run_buffer_strategy` import → `backtest_engine.run_backtest` + `BufferZoneStrategy` import로 변경

**Validation**:
- `poetry run pytest tests/test_buffer_zone_helpers.py -v` (전부 통과)
- `poetry run pytest tests/test_backtest_walkforward.py -v` (전부 통과)
- `poetry run pytest tests/test_integration.py -v` (전부 통과)
- 기존 전체 테스트 통과 (그린 유지)

---

### Phase 3 — 포트폴리오 엔진 분리 (그린)

**작업 내용**:

- [x] `src/qbt/backtest/engines/portfolio_engine.py` 신규 생성
  - `_create_strategy_for_slot(slot: AssetSlotConfig) -> SignalStrategy`: strategy_type 기반 팩토리
    - `"buffer_zone"` → `BufferZoneStrategy()`
    - `"buy_and_hold"` → `BuyAndHoldStrategy()`
    - 미등록 타입 → `ValueError`
  - 나머지 함수는 현재 `portfolio_strategy.py`에서 이전
    - `_compute_portfolio_equity`, `_is_first_trading_day_of_month`, `_check_rebalancing_needed`, `_execute_rebalancing` (내부 헬퍼 유지)
    - `compute_portfolio_effective_start_date(config) -> date`
    - `run_portfolio_backtest(config, start_date) -> PortfolioResult`
  - 메인 루프의 `slot.strategy_type == "buffer_zone"` / `"buy_and_hold"` 분기 전부 제거
    - day 0 초기화: 모든 전략에 대해 `strategy.check_buy(prev=cur=day0_data)` 호출
      - True이면 `signal_state="buy"` + pending buy 생성
      - False이면 `signal_state="sell"` (아무것도 안 함)
    - 메인 루프: position==0이면 항상 `strategy.check_buy(...)` 호출 (hold_days_required=`config.hold_days`)
    - 매도 조건: position>0이면 항상 `strategy.check_sell(...)` 호출
  - `buffer_zone_helpers.py`의 private import (`# type: ignore[import]`, `# pyright: ignore`) 완전 제거
- [x] `src/qbt/backtest/portfolio_strategy.py`: `portfolio_engine.py` re-export wrapper로 교체 (backward compat 유지, 삭제는 Phase 4)
  - `from qbt.backtest.engines.portfolio_engine import run_portfolio_backtest, compute_portfolio_effective_start_date`
  - `__all__` 정의
- [x] `tests/test_portfolio_strategy.py`: `portfolio_strategy.py` re-export를 통해 동작하므로 import 경로 변경 불필요 (re-export 덕에 그린 유지)

**Validation**:
- `poetry run pytest tests/test_portfolio_strategy.py -v` (전부 통과)
- 기존 전체 테스트 통과 (그린 유지)

---

### Phase 4 — 구 파일 삭제 + 전체 import 경로 정리 (그린)

**작업 내용**:

- [x] `src/qbt/backtest/strategies/buffer_zone_helpers.py` 삭제
- [x] `src/qbt/backtest/portfolio_strategy.py` 삭제
- [x] `src/qbt/backtest/__init__.py`: `buffer_zone_helpers` → `backtest_engine`, `strategy_common`, `engine_common` import로 교체
- [x] `src/qbt/backtest/strategies/__init__.py`: `buffer_zone_helpers` import 제거, 새 경로로 교체
- [x] `tests/test_buffer_zone_helpers.py`: import 경로 전면 업데이트
  - `from qbt.backtest.strategies.buffer_zone_helpers import ...` → 새 경로로 변경
    - `BufferStrategyParams`, `resolve_buffer_params` → `buffer_zone.py`
    - `PendingOrder`, `TradeRecord`, `EquityRecord`, `execute_buy_order`, `execute_sell_order`, `record_equity` → `engine_common.py`
    - `PendingOrderConflictError`, `HoldState`, `compute_bands`, `detect_buy_signal`, `detect_sell_signal` → `strategy_common.py`
    - `run_buffer_strategy`, `run_grid_search` → `backtest_engine.py`
- [x] `tests/test_backtest_walkforward.py`: import 경로 업데이트
- [x] `tests/test_integration.py`: import 경로 업데이트
- [x] `tests/test_portfolio_strategy.py`: `portfolio_strategy.py` → `portfolio_engine.py` import로 변경
  - 내부 함수 접근 테스트 (`_check_rebalancing_needed` 등): `portfolio_engine.py`에서 직접 import
- [x] `scripts/backtest/run_single_backtest.py`: import 경로 업데이트 (필요 시)
- [x] `scripts/backtest/run_portfolio_backtest.py`: `portfolio_strategy` → `portfolio_engine` import로 변경

**Validation**:
- `poetry run pytest tests/ -v` (전부 통과)
- import 오류 없음 확인

---

### 마지막 Phase — 문서 정리 및 최종 검증

**작업 내용**

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트
  - 모듈 구성 섹션에 `engines/` 패키지 추가
  - 삭제된 `buffer_zone_helpers.py`, `portfolio_strategy.py` 항목 제거
  - `strategy_common.py` 및 각 전략 클래스 설명 추가
- [x] `scripts/CLAUDE.md` 업데이트 (백테스트 관련 import 경로 변경 반영, 필요 시)
- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] 변경 기능 및 전체 플로우 최종 검증
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 최종 업데이트 및 상태 확정

**Validation**:

- [x] `poetry run python validate_project.py` (passed=390, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 엔진-전략 분리 리팩터링 (SignalStrategy Protocol + engines 패키지)
2. 백테스트 / buffer_zone_helpers·portfolio_strategy 분해 및 engines 패키지 도입
3. 백테스트 / 전략 인터페이스(SignalStrategy) 도입 및 단일·포트폴리오 엔진 분리
4. 백테스트 / 리팩터링(동작 동일) — 엔진/전략 계층 분리 및 private import 코드 스멜 제거
5. 백테스트 / 아키텍처 개선 — strategy_common, engine_common, backtest_engine, portfolio_engine 분리

## 7) 리스크(Risks)

| 리스크 | 영향도 | 완화책 |
|--------|--------|--------|
| `run_backtest` 구현 중 `run_buffer_strategy`와 결과 수치 차이 발생 | 높음 | Phase 2에서 기존 테스트 전부 통과를 확인하며 진행. 기존 `run_buffer_strategy`를 먼저 `run_backtest` 래핑으로 만들어 점진적 검증 |
| hold_days 상태머신을 `BufferZoneStrategy.check_buy`로 이전 시 로직 오류 | 높음 | `test_buffer_zone_helpers.py`의 hold_days 관련 테스트 전부 Phase 1~2에서 통과 확인 |
| `portfolio_engine.py` 전환 시 B&H 초기 진입 타이밍 변경 | 중간 | `should_always_hold()` 패턴으로 day 0 pending buy 동작 동일하게 구현. `test_portfolio_strategy.py` 통과 확인 |
| `buffer_zone_helpers.py` 삭제 후 누락된 import 경로 발견 | 중간 | Phase 4에서 grep으로 `buffer_zone_helpers` 잔여 참조 전수 확인 후 삭제 |
| 그리드 서치 병렬 처리(WORKER_CACHE + pickle) 동작 이상 | 낮음 | `_run_backtest_for_grid`를 module-level 함수로 유지. `test_buffer_zone_helpers.py`의 그리드 서치 테스트로 검증 |

## 8) 메모(Notes)

### 핵심 결정 사항

- **`should_always_hold()` 제거**: 초기 `check_buy`/`check_sell` 2메서드 Protocol에서 `should_always_hold()`를 제거했다. 엔진이 day 0에도 모든 전략에 `check_buy(prev=cur=day0_data)`를 호출하면, B&H는 항상 True → 즉시 pending buy, BufferZone은 prev==cur 조건에서 상향돌파 불가 → False. `should_always_hold()`는 행동이 아닌 메타 정보를 Protocol에 노출하는 설계 문제가 있었다.
- **hold_days 파라미터 전달 방식**: 전략 클래스 생성자가 아닌 `check_buy(hold_days_required=...)` 호출 시 전달. 포트폴리오 엔진은 `config.hold_days`를 매 호출마다 전달.
- **포트폴리오 엔진의 strategy_type**: `AssetSlotConfig.strategy_type: str` 유지. 변경 시 `portfolio_configs.py` 전면 수정이 필요하고 `frozen=True` dataclass에 Protocol 객체 저장 시 `__hash__` 복잡성이 증가하므로 팩토리 방식으로 절충.
- **`PendingOrderConflictError` 위치**: `strategy_common.py`에 정의 (단일 슬롯 원칙은 전략 계약). `engine_common.py`의 `PendingOrder`와 분리.
- **`BufferStrategyResultDict` 위치**: `strategies/buffer_zone.py`로 이전 (버퍼존 전략 고유 결과 타입).
- **`GridSearchResult` 위치**: `engines/backtest_engine.py`로 이전 (그리드 서치는 엔진 기능).

### 진행 로그 (KST)

- 2026-03-21 00:00: 계획서 초안 작성 완료
- 2026-03-21 01:00: `should_always_hold()` 제거 — day 0 `check_buy(prev=cur)` 패턴으로 대체
- 2026-03-21 03:00: Phase 0~4 + 마지막 Phase 전체 완료. validate_project.py passed=390, failed=0, skipped=0. `buffer_zone_helpers.py`와 `portfolio_strategy.py` 삭제 완료. `strategies/__init__.py`에서 엔진 함수 re-export 제거(순환 import 방지). `buffer_zone.py`의 `run_backtest` 지연 import 적용.

---
