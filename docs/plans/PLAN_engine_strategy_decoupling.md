# Implementation Plan: 엔진-전략 의존성 분리 (Engine-Strategy Decoupling)

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: 🟡 Draft

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-03-21 00:00
**마지막 업데이트**: 2026-03-21 00:00
**관련 범위**: backtest (engines, strategies, runners, walkforward, portfolio)
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

- [ ] 백테스트 엔진(`backtest_engine.py`)과 포트폴리오 엔진(`portfolio_engine.py`)에서 버퍼존 전용 로직을 완전히 제거한다
- [ ] 모든 전략 고유 로직(밴드 계산, 상태머신 등)을 각 전략 클래스 내부로 이동한다
- [ ] B&H 첫 매수 타이밍을 수정한다 (시계열 3번째 날 → **2번째 날** 시가)
- [ ] `PortfolioConfig`에서 4P 파라미터를 제거하고 `AssetSlotConfig` 슬롯 레벨로 이동한다

## 2) 비목표(Non-Goals)

- TQQQ 도메인 변경
- 기존 버퍼존 `equity.csv` / `trades.csv` 컬럼 포맷 변경 (runner post-processing으로 유지)
- 대시보드 앱 코드 변경 (Feature Detection으로 자동 적응)
- WFO 윈도우 생성 로직 변경 (`params_schedule` 타입만 변경)
- `BufferStrategyParams` 제거 (그리드서치/WFO 파라미터 표현에 계속 사용)

## 3) 배경/맥락(Context)

### 현재 문제점

| 위치 | 버퍼존 전제 코드 | 영향 |
|------|-----------------|------|
| `backtest_engine.py` loop | `range(1, n)` — day 0 루프 제외 | B&H가 3번째 날 시가 매수 (잘못된 타이밍) |
| `backtest_engine.py` | `compute_bands` + `prev_band` 직접 추적 | 엔진이 밴드 계산 담당 (전략 역할 침범) |
| `backtest_engine.py` | `BufferStrategyParams` 강제 요구 | B&H가 dummy 파라미터 생성 필요 |
| `portfolio_engine.py` | day 0 `prev=cur` 우회 처리 | 의도 숨긴 핵 |
| `portfolio_engine.py` | `compute_bands` + `prev_band` 직접 추적 | 동일 |
| `engine_common.py` `PendingOrder` | `buy_buffer_zone_pct`, `hold_days_used` 필드 | 버퍼존 전용이 범용 타입에 혼재 |
| `engine_common.py` `EquityRecord` | `buy_buffer_pct`, `sell_buffer_pct`, `upper_band`, `lower_band` | 버퍼존 전용이 범용 타입에 혼재 |
| `PortfolioConfig` | `ma_window`, `buy_buffer_zone_pct`, `sell_buffer_zone_pct`, `hold_days`, `ma_type` | B&H 슬롯도 받지만 완전히 무시 |
| `strategy_common.py` | `compute_bands`, `detect_buy_signal`, `detect_sell_signal` | 버퍼존 전용 함수가 공통 모듈에 위치 |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- [루트 CLAUDE.md](../../CLAUDE.md)
- [src/qbt/backtest/CLAUDE.md](../../src/qbt/backtest/CLAUDE.md)
- [tests/CLAUDE.md](../../tests/CLAUDE.md)
- [docs/CLAUDE.md](../CLAUDE.md)

---

## 4) 완료 조건(Definition of Done)

- [ ] 모든 테스트 통과 (failed=0, skipped=0)
- [ ] `poetry run python validate_project.py` 통과 (결과 기록 필요)
- [ ] `poetry run black .` 실행 완료
- [ ] `backtest_engine.run_backtest` 시그니처에서 `BufferStrategyParams` 제거됨
- [ ] `backtest_engine` / `portfolio_engine`에서 `compute_bands` 호출 없음
- [ ] `PortfolioConfig`에서 `ma_window`, `buy_buffer_zone_pct`, `sell_buffer_zone_pct`, `hold_days`, `ma_type` 제거됨
- [ ] `AssetSlotConfig`에 전략별 파라미터 추가됨
- [ ] B&H 첫 매수: **시계열 2번째 날 시가** (테스트로 고정)
- [ ] 버퍼존 신호 타이밍: 기존과 동일 (테스트로 고정)
- [ ] `params_schedule` 타입: `dict[date, SignalStrategy]`
- [ ] 계획서 체크박스 최신화

---

## 5) 변경 범위(Scope)

### 변경 대상 파일

**전략 계층**
- `src/qbt/backtest/strategies/strategy_common.py` — Protocol 변경, 버퍼존 전용 함수 제거
- `src/qbt/backtest/strategies/buffer_zone_helpers.py` — **신규 생성**: `HoldState`, `compute_bands`, `detect_buy_signal`, `detect_sell_signal`
- `src/qbt/backtest/strategies/buffer_zone.py` — `BufferZoneStrategy` stateful 리팩터링
- `src/qbt/backtest/strategies/buy_and_hold.py` — `BuyAndHoldStrategy` 단순화
- `src/qbt/backtest/strategies/__init__.py` — export 업데이트

**엔진 계층**
- `src/qbt/backtest/engines/engine_common.py` — `PendingOrder`, `EquityRecord` 경량화
- `src/qbt/backtest/engines/backtest_engine.py` — 버퍼존 의존성 제거, 루프 day 0 시작
- `src/qbt/backtest/engines/portfolio_engine.py` — 전략 의존성 제거

**러너/WFO 계층**
- `src/qbt/backtest/runners.py` — 새 전략/엔진 인터페이스 적용, equity enrichment
- `src/qbt/backtest/walkforward.py` — `params_schedule` 타입 변경

**포트폴리오 계층**
- `src/qbt/backtest/portfolio_types.py` — `AssetSlotConfig` 파라미터 추가, `PortfolioConfig` 4P 제거
- `src/qbt/backtest/portfolio_configs.py` — 슬롯 레벨 파라미터 적용

**문서**
- `src/qbt/backtest/CLAUDE.md` — 새 아키텍처 반영

**테스트**
- `tests/test_strategy_interface.py` — 새 Protocol 계약으로 전면 재작성
- `tests/test_buy_and_hold.py` — B&H 타이밍 변경 반영
- `tests/test_buffer_zone_helpers.py` — 이동된 함수 import 경로 수정
- `tests/test_buffer_zone.py` — 새 전략 인터페이스 반영
- `tests/test_portfolio_strategy.py` — 슬롯별 파라미터 반영
- `tests/test_portfolio_configs.py` — 새 config 구조 반영

### 데이터/결과 영향

- **B&H 결과 파일** (`storage/results/backtest/buy_and_hold_*/`): 첫 매수 1일 앞당겨져 재실행 필요
- **버퍼존 결과 파일**: 변화 없음 (신호 타이밍 동일)
- **포트폴리오 결과 파일**: 포트폴리오 내 B&H 슬롯 첫 매수 1일 앞당겨져 재실행 필요

---

## 6) 아키텍처 설계

### 새 SignalStrategy Protocol

```python
class SignalStrategy(Protocol):
    def check_buy(self, signal_df: pd.DataFrame, i: int, current_date: date) -> bool:
        """i번째 날 매수 신호 여부. 내부 prev 상태 갱신 포함."""
        ...

    def check_sell(self, signal_df: pd.DataFrame, i: int) -> bool:
        """i번째 날 매도 신호 여부. 내부 prev 상태 갱신 포함."""
        ...

    def get_buy_meta(self) -> dict[str, float | int]:
        """check_buy True 직후 호출. TradeRecord용 메타데이터 반환."""
        ...
```

### BufferZoneStrategy (stateful)

생성자: `BufferZoneStrategy(ma_col: str, buy_buffer_pct: float, sell_buffer_pct: float, hold_days: int, ma_type: str = "ema")`

내부 상태: `_prev_upper: float | None`, `_prev_lower: float | None`, `_hold_state: HoldState | None`, `_last_buy_buffer_pct`, `_last_hold_days_used`

- `check_buy(signal_df, i, current_date)`:
  - `_prev_upper is None`이면 최초 호출 → i > 0이면 `signal_df.iloc[i-1]`로 초기화, i=0이면 현재행으로 초기화 후 **False 반환**
  - 이후: 밴드 계산 → hold_state 로직 → 상향돌파 감지 → prev 갱신 → bool 반환
- `check_sell(signal_df, i)`:
  - 최초 호출 처리 동일 (초기화 후 False)
  - 이후: 하향돌파 감지 → prev 갱신 → bool 반환
- `get_buy_meta()`: `{"buy_buffer_pct": _last_buy_buffer_pct, "hold_days_used": _last_hold_days_used}`

### BuyAndHoldStrategy (stateless)

- `check_buy(signal_df, i, current_date) -> bool`: 항상 `True`
- `check_sell(signal_df, i) -> bool`: 항상 `False`
- `get_buy_meta() -> dict`: `{}`

### engine_common 경량화

| 타입 | 현재 필드 | 변경 후 필드 |
|------|-----------|-------------|
| `PendingOrder` | `order_type`, `signal_date`, `buy_buffer_zone_pct`, `hold_days_used` | `order_type`, `signal_date` |
| `EquityRecord` | `Date`, `equity`, `position`, `buy_buffer_pct`, `sell_buffer_pct`, `upper_band`, `lower_band` | `Date`, `equity`, `position` |
| `record_equity()` | buffer 파라미터 다수 | `current_date`, `capital`, `position`, `close_price` |
| `execute_sell_order()` | `order`에서 buffer_pct 추출 | `buy_buffer_pct=0.0`, `hold_days_used=0` 명시적 파라미터 |

> `TradeRecord`의 `buy_buffer_pct`, `hold_days_used`는 유지 (CSV 호환). 값은 엔진 로컬 변수 `entry_buy_buffer_pct`, `entry_hold_days_used`에서 제공.

### backtest_engine 새 루프 구조

```
run_backtest(strategy, signal_df, trade_df, initial_capital, ...)

루프: range(0, n)   ← Day 0부터 시작 (B&H Day 0 fix)
  i=0: pending=None → skip execute → equity 기록 → check_buy → B&H: True → PendingOrder 생성
  i=1: pending 실행 (day 2 시가 매수) → equity → position>0 → check_sell
  i=N-1: pending 정상 체결, 마지막 날 신호는 미체결

엔진 로컬 상태:
  entry_buy_buffer_pct: float = 0.0   (strategy.get_buy_meta()에서 갱신)
  entry_hold_days_used: int = 0       (strategy.get_buy_meta()에서 갱신)
```

### B&H 타이밍 (수정 후)

| 날 | i | 동작 |
|----|---|------|
| 1번째 | 0 | equity 기록 → `check_buy` → **True** → `PendingOrder("buy")` 생성 |
| **2번째** | 1 | pending 실행 → **2번째 날 시가 매수** ✓ |

### AssetSlotConfig 재설계

```python
@dataclass(frozen=True)
class AssetSlotConfig:
    asset_id: str
    signal_data_path: Path
    trade_data_path: Path
    target_weight: float
    strategy_type: Literal["buffer_zone", "buy_and_hold"] = "buffer_zone"
    # 전략별 파라미터 (buffer_zone에서 사용, buy_and_hold는 무시)
    ma_window: int = 200
    buy_buffer_zone_pct: float = 0.03
    sell_buffer_zone_pct: float = 0.05
    hold_days: int = 3
    ma_type: Literal["ema", "sma"] = "ema"
```

`PortfolioConfig`에서 제거: `ma_window`, `buy_buffer_zone_pct`, `sell_buffer_zone_pct`, `hold_days`, `ma_type`

---

## 7) 단계별 계획(Phases)

### Phase 0 — 인바리언트를 테스트로 먼저 고정 (레드)

**목표**: 변경 후의 계약을 테스트로 먼저 고정. 현재 코드에서는 실패해야 함.

**할 일**

- [ ] `tests/test_strategy_interface.py` 전면 재작성
  - 새 Protocol 시그니처 계약 고정: `check_buy(signal_df, i, current_date) -> bool`
  - B&H: 모든 i에서 `check_buy` → True
  - BufferZone: i=0 → False (최초 호출, 초기화만), i>0 상향돌파 조건 → True
  - `get_buy_meta()` 반환 타입/키 계약 고정
- [ ] `tests/test_buy_and_hold.py` 업데이트
  - B&H 첫 매수가 **시계열 2번째 날 시가**임을 고정 (현재 3번째 날 → 실패 예상)
  - `run_backtest` 새 시그니처 (`initial_capital: float`, 루프 day 0 시작) 기준으로 작성

**Validation**: 의도적 실패 확인 (`failed > 0` 정상)

---

### Phase 1 — 전략 계층 재구성 (그린 유지)

**목표**: 새 Protocol 구현 + 버퍼존 전용 함수를 적절한 위치로 이동.

**할 일**

- [ ] `strategies/buffer_zone_helpers.py` **신규 생성**
  - `strategy_common.py`에서 이동: `HoldState`, `compute_bands`, `detect_buy_signal`, `detect_sell_signal`
- [ ] `strategies/strategy_common.py` 정제
  - 제거: `HoldState`, `compute_bands`, `detect_buy_signal`, `detect_sell_signal`
  - 유지: `PendingOrderConflictError`, `SignalStrategy` Protocol
  - `SignalStrategy` Protocol 새 시그니처 적용:
    - `check_buy(self, signal_df, i, current_date) -> bool`
    - `check_sell(self, signal_df, i) -> bool`
    - `get_buy_meta(self) -> dict[str, float | int]`
- [ ] `strategies/buffer_zone.py` — `BufferZoneStrategy` stateful 리팩터링
  - 생성자: `(ma_col, buy_buffer_pct, sell_buffer_pct, hold_days)`
  - 내부 상태: `_prev_upper`, `_prev_lower`, `_hold_state`, `_last_buy_buffer_pct`, `_last_hold_days_used`
  - `check_buy(signal_df, i, current_date)`: 내부에서 밴드 계산 + hold_state 관리
    - `_prev_upper is None`: 최초 호출 처리 (i=0이면 초기화 후 False, i>0이면 i-1 행으로 초기화)
    - True 반환 시 `_last_buy_buffer_pct`, `_last_hold_days_used` 갱신
  - `check_sell(signal_df, i)`: 내부에서 하향돌파 감지
  - `get_buy_meta()`: `{"buy_buffer_pct": ..., "hold_days_used": ...}`
  - `CONFIGS` 각 항목에서 `resolve_params_for_config` 호출 시 `BufferZoneStrategy` 생성자 파라미터 매핑
- [ ] `strategies/buy_and_hold.py` — `BuyAndHoldStrategy` 단순화
  - 파라미터 없는 생성자
  - `check_buy(signal_df, i, current_date) -> bool`: 항상 `True`
  - `check_sell(signal_df, i) -> bool`: 항상 `False`
  - `get_buy_meta() -> dict`: `{}`
- [ ] `strategies/__init__.py` — export 업데이트
- [ ] `tests/test_strategy_interface.py` — Phase 0 테스트가 통과하도록 확인
- [ ] `tests/test_buffer_zone_helpers.py` — import 경로 수정 (`strategy_common` → `buffer_zone_helpers`)
- [ ] `tests/test_buffer_zone.py` — 새 전략 인터페이스 반영

**Validation**: Phase 0 테스트 포함 전체 통과 확인

---

### Phase 2 — engine_common 경량화 (그린 유지)

**목표**: `PendingOrder`, `EquityRecord`에서 버퍼존 전용 필드 제거.

**할 일**

- [ ] `engines/engine_common.py`
  - `PendingOrder`: `buy_buffer_zone_pct`, `hold_days_used` 필드 제거 → `order_type`, `signal_date`만
  - `EquityRecord`: `buy_buffer_pct`, `sell_buffer_pct`, `upper_band`, `lower_band` 제거 → `Date`, `equity`, `position`만
  - `record_equity()`: 버퍼존 파라미터 제거 (`current_date`, `capital`, `position`, `close_price`만)
  - `execute_sell_order()`: `buy_buffer_pct: float = 0.0`, `hold_days_used: int = 0` 명시적 파라미터로 수신

**Validation**: 전체 테스트 통과 확인

---

### Phase 3 — backtest_engine 분리 (그린 유지)

**목표**: 엔진이 `BufferStrategyParams`, `compute_bands`, `prev_band` 의존성 완전 제거.

**할 일**

- [ ] `engines/backtest_engine.py`
  - `run_backtest()` 새 시그니처:
    ```python
    def run_backtest(
        strategy: SignalStrategy,
        signal_df: pd.DataFrame,
        trade_df: pd.DataFrame,
        initial_capital: float,
        log_trades: bool = True,
        strategy_name: str = "",
        params_schedule: dict[date, SignalStrategy] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, SummaryDict]:
    ```
  - 루프: `range(0, n)` (Day 0부터)
  - 엔진 로컬 상태: `entry_buy_buffer_pct = 0.0`, `entry_hold_days_used = 0`
  - buy 신호 시: `meta = strategy.get_buy_meta()` → 로컬 변수 갱신
  - `compute_bands` 호출 없음, `prev_upper_band`/`prev_lower_band` 추적 없음
  - 반환: `SummaryDict` (버퍼존 전용 필드 없음)
  - `params_schedule` 처리: 날짜 도달 시 `strategy` 객체 교체 (새 객체는 `_prev_upper=None`으로 시작 → 자동으로 `i-1` 행에서 초기화)
  - `_validate_backtest_inputs(signal_df, trade_df, initial_capital)`:
    - signal_df 필수: `COL_DATE`, `COL_CLOSE`
    - trade_df 필수: `COL_DATE`, `COL_OPEN`, `COL_CLOSE`
    - MA 컬럼 검증 없음, `BufferStrategyParams` 검증 없음
  - `run_buffer_strategy()` 편의 래퍼 업데이트:
    - 내부에서 `BufferZoneStrategy(ma_col, ...)` 생성
    - MA valid_mask 필터링 후 `run_backtest` 호출
  - `_run_backtest_for_grid()`: `BufferZoneStrategy(ma_col, ...)` 생성 + valid_mask 필터링 후 호출
  - `BufferStrategyResultDict` 제거 (SummaryDict 반환으로 대체)
- [ ] `tests/test_buffer_zone_helpers.py` — 새 engine API 반영
- [ ] `tests/test_buy_and_hold.py` — B&H 타이밍 테스트 통과 확인

**Validation**: 전체 테스트 통과 확인

---

### Phase 4 — runners.py 업데이트 + equity enrichment (그린 유지)

**목표**: 새 전략/엔진 인터페이스 적용. 버퍼존 equity_df에 band 컬럼 post-processing으로 보강.

**할 일**

- [ ] `runners.py`
  - `create_buffer_zone_runner()`:
    - MA 계산 후 valid_mask 필터링 (기존과 동일)
    - `BufferZoneStrategy(ma_col, buy_buffer_pct, sell_buffer_pct, hold_days)` 생성
    - `run_backtest(strategy, filtered_signal, filtered_trade, initial_capital, ...)`
    - equity_df post-processing: `_enrich_equity_with_bands(equity_df, signal_df, ma_col, buy_buffer_pct, sell_buffer_pct)` 호출
    - summary에 파라미터 추가: `summary["ma_window"] = params.ma_window` 등
  - `create_buy_and_hold_runner()`:
    - dummy params 제거 (MA 계산 불필요)
    - `BuyAndHoldStrategy()` 생성
    - `run_backtest(strategy, trade_df, trade_df, initial_capital, ...)`
    - signal_df = trade_df OHLC 그대로 (MA 컬럼 제거 불필요)
  - `_enrich_equity_with_bands(equity_df, signal_df, ma_col, buy_pct, sell_pct) -> pd.DataFrame` **신규 함수**:
    - signal_df의 MA 값으로 `upper_band`, `lower_band`, `buy_buffer_pct`, `sell_buffer_pct` 컬럼을 equity_df에 추가
    - signal_df와 equity_df를 Date 기준으로 join

**Validation**: 전체 테스트 통과 확인

---

### Phase 5 — walkforward.py params_schedule 타입 변경 (그린 유지)

**목표**: stitched equity에서 `dict[date, SignalStrategy]` 사용. WFO는 버퍼존 전용이므로 내부에서 BufferZoneStrategy 생성.

**할 일**

- [ ] `walkforward.py`
  - `build_params_schedule(wfo_results, signal_df)`:
    - 반환 타입 `dict[date, BufferStrategyParams]` → `dict[date, SignalStrategy]`
    - 내부에서 `BufferZoneStrategy(f"ma_{p.ma_window}", p.buy_buffer_zone_pct, ...)` 생성
    - 호출 전제: signal_df에 해당 MA 컬럼이 사전 계산되어 있어야 함
  - `run_walkforward()`:
    - OOS 백테스트 시 `BufferZoneStrategy(...)` 직접 생성 + `run_backtest` 호출
    - IS 그리드서치: `run_grid_search` 그대로 사용 (`BufferStrategyParams` 기반)
  - stitched equity 호출부: `params_schedule: dict[date, SignalStrategy]` 타입 적용
    - 주의: `params_schedule`에 포함된 모든 `ma_window`에 해당하는 MA 컬럼을 signal_df에 사전 계산 후 전달
- [ ] `tests/test_backtest_walkforward.py` — params_schedule 타입 변경 반영
- [ ] `tests/test_wfo_stitched.py` — `build_params_schedule` 반환 타입 변경 반영

**Validation**: 전체 테스트 통과 확인

---

### Phase 6 — 포트폴리오 계층 재설계 (그린 유지)

**목표**: `PortfolioConfig` 4P 파라미터 제거, 슬롯 레벨 파라미터 적용, 포트폴리오 엔진 완전 분리.

**할 일**

- [ ] `portfolio_types.py`
  - `AssetSlotConfig`: 슬롯별 파라미터 추가 (`ma_window=200`, `buy_buffer_zone_pct=0.03`, `sell_buffer_zone_pct=0.05`, `hold_days=3`, `ma_type="ema"` — 모두 기본값)
  - `PortfolioConfig`: `ma_window`, `buy_buffer_zone_pct`, `sell_buffer_zone_pct`, `hold_days`, `ma_type` 제거
  - `PortfolioResult.config` 기본값: 제거된 필드 반영
- [ ] `portfolio_engine.py`
  - `_create_strategy_for_slot(slot)`:
    - `buffer_zone`: `BufferZoneStrategy(f"ma_{slot.ma_window}", slot.buy_buffer_zone_pct, ..., slot.ma_type)` 생성
    - `buy_and_hold`: `BuyAndHoldStrategy()` 생성
  - `_load_and_prepare_data(slot)`:
    - `buffer_zone` 슬롯만 MA 계산 (`slot.ma_window`, `slot.ma_type` 사용)
    - `buy_and_hold` 슬롯: MA 계산 없음
  - valid_start 계산: `buffer_zone` 슬롯의 MA NaN 기준만 (B&H 슬롯 제외)
  - 루프: `range(0, n)` — day 0 `prev=cur` 우회 처리 제거 (전략이 내부적으로 처리)
  - `prev_upper_bands`, `prev_lower_bands` 추적 제거
  - `compute_bands` 호출 없음
  - `compute_portfolio_effective_start_date()`: `slot.ma_window` 기준으로 재계산 (`config.ma_window` 제거)
- [ ] `portfolio_configs.py`
  - 모든 `PortfolioConfig` 정의에서 `ma_window`, `buy_buffer_zone_pct`, `sell_buffer_zone_pct`, `hold_days`, `ma_type` 제거
  - `buffer_zone` 슬롯에 파라미터 명시 (`ma_window=200, buy_buffer_zone_pct=0.03, ...`)
  - `buy_and_hold` 슬롯: 기본값 사용 (파라미터 무시되므로 명시 불필요)
- [ ] `tests/test_portfolio_strategy.py` — 새 슬롯 config 구조 반영
- [ ] `tests/test_portfolio_configs.py` — `PortfolioConfig` 구조 변경 반영

**Validation**: 전체 테스트 통과 확인

---

### Phase 7 — 문서 정리 및 최종 검증 (마지막 Phase)

**작업 내용**

- [ ] `src/qbt/backtest/CLAUDE.md` 업데이트
  - 새 `SignalStrategy` Protocol 시그니처 반영
  - `BufferZoneStrategy` 생성자 파라미터 반영
  - `engine_common` 변경 사항 반영
  - `AssetSlotConfig` 새 필드 반영
  - `PortfolioConfig` 제거된 필드 반영
  - `runners.py` B&H 타이밍 코멘트 수정
- [ ] `poetry run black .` (자동 포맷 적용)
- [ ] DoD 체크리스트 최종 업데이트 및 체크 완료

**Validation**

- [ ] `poetry run python validate_project.py` (passed=\_\_, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. `백테스트 / 엔진-전략 완전 분리 — B&H 타이밍 수정 + BufferStrategyParams 엔진 제거 + PortfolioConfig 재설계`
2. `백테스트 / SignalStrategy Protocol 재설계 — 엔진 버퍼존 의존성 제거 + Day 0 타이밍 fix`
3. `백테스트 / 엔진 전략 의존성 분리 — stateful strategy + engine decoupling + 슬롯별 파라미터`
4. `백테스트 / engine-strategy decoupling — B&H day-2 fix + 포트폴리오 슬롯 파라미터 재설계`
5. `백테스트 / 전략 계층 분리 리팩터링 (B&H 타이밍 수정 + 엔진 버퍼존 의존 제거)`

---

## 8) 리스크(Risks)

| 리스크 | 완화책 |
|--------|--------|
| B&H 결과 변경 (의도된 수정) | Phase 0에서 새 타이밍 테스트로 계약 고정 |
| BufferZoneStrategy 상태 초기화 오류 (최초 호출 처리) | Phase 1 테스트에서 i=0, i>0 분기 모두 커버 |
| WFO stitched MA 사전 계산 누락 | Phase 5 테스트에서 MA 컬럼 존재 검증 추가 |
| 포트폴리오 B&H 슬롯 valid_start 오류 (MA 없는 슬롯 제외 처리) | Phase 6 테스트에서 B&H 전용 포트폴리오 케이스 추가 |
| equity.csv upper/lower_band 컬럼 누락 | Phase 4 runner enrichment로 보강, 대시보드 Feature Detection 자동 적응 |

## 9) 메모(Notes)

### 결정 사항

- `HoldState` TypedDict: `buffer_zone_helpers.py`로 이동 (Strategy 내부용, Protocol에서 노출 안 함)
- `compute_bands`, `detect_buy_signal`, `detect_sell_signal`: `strategy_common.py` → `buffer_zone_helpers.py` 이동
- `BufferStrategyParams`: 유지 (그리드서치/WFO 파라미터 표현에 계속 사용). 단 엔진 시그니처에서 제거
- `TradeRecord`의 `buy_buffer_pct`, `hold_days_used`: 유지 (CSV 호환). `execute_sell_order` 명시적 파라미터로 전달
- `run_buffer_strategy()` 편의 래퍼: 유지 (하위 호환, 내부 구현만 업데이트)
- `params_schedule`에서 전략 교체 시: 새 `BufferZoneStrategy` 객체는 `_prev_upper=None`으로 시작 → 첫 호출 시 `signal_df.iloc[i-1]`로 자동 초기화 (WFO stitched 경계 안전)

### 진행 로그 (KST)

- 2026-03-21 00:00: 계획서 작성
