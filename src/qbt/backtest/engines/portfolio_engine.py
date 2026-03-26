"""포트폴리오 백테스트 엔진

복수 자산의 독립 시그널 + 목표 비중 배분 + 이중 트리거 리밸런싱을 처리한다.

주요 설계 결정:
- 주문 모델: OrderIntent 기반 (EXIT_ALL / ENTER_TO_TARGET / REDUCE_TO_TARGET / INCREASE_TO_TARGET)
- 흐름: Signal → ProjectedPortfolio → Rebalance → MergeIntents → Execution (next_day_intents)
- 리밸런싱: 이중 트리거 체계
    - 월 첫 거래일: 편차 10% 초과 시 (MONTHLY_REBALANCE_THRESHOLD_RATE)
    - 매일: 편차 20% 초과 시 긴급 (DAILY_REBALANCE_THRESHOLD_RATE)
- 주문 충돌 해소: merge_intents 우선순위 규칙으로 자산당 1개 보장
- projected state: signal intent 반영 후 리밸런싱 계획 → planning 왜곡 방지
- 체결 기준: 익일 open 가격 (Lookahead 방지)
- 체결 흐름: SELL 먼저 체결 → available_cash 확정 → BUY 체결 (_execute_orders)
- 현금 부족 시: BUY 총 비용이 available_cash 초과이면 raw_shares × scale_factor로 비례 축소
- 부분 매도: 리밸런싱 REDUCE_TO_TARGET은 delta_amount 기준 수량, 신호 EXIT_ALL은 전량
- 결과: PortfolioResult (equity_df, trades_df, per_asset, summary)
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average, calculate_summary
from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.backtest.portfolio_types import (
    AssetSlotConfig,
    PortfolioAssetResult,
    PortfolioConfig,
    PortfolioResult,
)
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldStrategy
from qbt.backtest.strategies.strategy_common import SignalStrategy
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN, EPSILON
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)

# 월 첫 거래일 리밸런싱 임계값: |actual/target - 1| > 0.10이면 트리거 (정기 리밸런싱)
MONTHLY_REBALANCE_THRESHOLD_RATE: float = 0.10

# 매일 긴급 리밸런싱 임계값: |actual/target - 1| > 0.20이면 트리거 (급격한 편차 대응)
DAILY_REBALANCE_THRESHOLD_RATE: float = 0.20


# ============================================================================
# 내부 데이터클래스 (private)
# ============================================================================


@dataclass
class OrderIntent:
    """자산별 주문 의도를 나타내는 모델.

    signal 또는 rebalance 로직이 생성한 주문 의도를 통일된 형태로 표현한다.
    merge_intents에서 signal/rebalance intent를 통합하여 자산당 1개를 보장한다.

    intent_type 종류:
    - EXIT_ALL: 보유 전량 청산 (signal sell)
    - ENTER_TO_TARGET: 신규 진입하여 target_amount 도달 (signal buy)
    - REDUCE_TO_TARGET: 초과분 매도하여 target_amount 도달 (rebalance)
    - INCREASE_TO_TARGET: 미달분 매수하여 target_amount 도달 (rebalance)
    """

    asset_id: str
    intent_type: Literal["EXIT_ALL", "ENTER_TO_TARGET", "REDUCE_TO_TARGET", "INCREASE_TO_TARGET"]
    current_amount: float  # 현재 평가액
    target_amount: float  # 목표 금액
    delta_amount: float  # target_amount - current_amount (음수 = 매도, 양수 = 매수)
    target_weight: float  # 목표 비중 (0~1)
    reason: str  # 생성 이유 (로깅/디버깅용)
    hold_days_used: int = 0  # 진입 시 hold_days 파라미터 (TradeRecord에 기록)


@dataclass
class _ProjectedPortfolio:
    """signal intents 반영 후 예상 포트폴리오 상태.

    signal intents를 적용한 뒤 리밸런싱 기준이 되는 "예상" 포트폴리오를 나타낸다.
    EXIT_ALL 자산의 평가액은 projected_cash로 이동하고, active_assets에서 제거된다.
    ENTER_TO_TARGET 자산은 active_assets에 추가된다 (아직 position=0이므로 amount=0).
    """

    projected_amounts: dict[str, float]  # {asset_id: 예상 평가액}
    projected_cash: float  # EXIT_ALL 매도 예상 대금 포함 현금
    active_assets: set[str]  # 리밸런싱 대상 자산 집합 (signal_state == "buy" 기준)


@dataclass
class _AssetState:
    """자산별 런타임 상태."""

    position: int  # 보유 수량
    signal_state: Literal["buy", "sell"]  # 현재 시그널 상태


@dataclass
class _ExecutionResult:
    """_execute_orders() 반환값.

    SELL → BUY 순으로 체결한 결과를 담는다.
    """

    updated_cash: float
    updated_positions: dict[str, int]
    updated_entry_prices: dict[str, float]
    updated_entry_dates: dict[str, date | None]
    updated_entry_hold_days: dict[str, int]
    new_trades: list[dict[str, Any]]
    rebalanced_today: bool


# ============================================================================
# 전략 팩토리
# ============================================================================


def _create_strategy_for_slot(slot: AssetSlotConfig) -> SignalStrategy:
    """strategy_type 기반으로 전략 객체를 생성한다.

    Args:
        slot: 자산 슬롯 설정

    Returns:
        SignalStrategy를 구현한 전략 객체

    Raises:
        ValueError: 미등록 strategy_type인 경우
    """
    if slot.strategy_type == "buffer_zone":
        return BufferZoneStrategy(
            ma_col=f"ma_{slot.ma_window}",
            buy_buffer_pct=slot.buy_buffer_zone_pct,
            sell_buffer_pct=slot.sell_buffer_zone_pct,
            hold_days=slot.hold_days,
            ma_type=slot.ma_type,
        )
    elif slot.strategy_type == "buy_and_hold":
        return BuyAndHoldStrategy()
    raise ValueError(f"미등록 strategy_type: '{slot.strategy_type}'. " f"사용 가능: 'buffer_zone', 'buy_and_hold'")


# ============================================================================
# 공개 헬퍼 함수 (테스트 대상)
# ============================================================================


def _compute_portfolio_equity(
    shared_cash: float,
    asset_positions: dict[str, int],
    asset_closes: dict[str, float],
) -> float:
    """포트폴리오 에쿼티를 계산한다.

    Args:
        shared_cash: 미투자 현금
        asset_positions: {asset_id: 보유수량}
        asset_closes: {asset_id: 종가}

    Returns:
        equity = shared_cash + Σ(position × close)
    """
    total_value = sum(asset_positions[aid] * asset_closes[aid] for aid in asset_positions if aid in asset_closes)
    return shared_cash + total_value


def _is_first_trading_day_of_month(trade_dates: list[date], i: int) -> bool:
    """월 첫 거래일 여부를 판정한다.

    Args:
        trade_dates: 전체 거래일 목록
        i: 현재 인덱스 (0-based)

    Returns:
        True이면 이전 거래일과 월이 다름 (= 월 첫 거래일)
        False이면 i=0이거나 동일 월
    """
    if i <= 0:
        return False
    return trade_dates[i].month != trade_dates[i - 1].month


def _generate_signal_intents(
    asset_states: dict[str, "_AssetState"],
    strategies: dict[str, SignalStrategy],
    asset_signal_dfs: dict[str, pd.DataFrame],
    equity_vals: dict[str, float],
    slot_dict: dict[str, AssetSlotConfig],
    current_equity: float,
    i: int,
    current_date: date,
) -> dict[str, OrderIntent]:
    """전략 기반으로 시그널 intent를 생성한다.

    1. position=0 + buy signal → ENTER_TO_TARGET (target_amount = current_equity × target_weight)
    2. position>0 + sell signal → EXIT_ALL (current_amount = equity_vals[asset_id])
    3. 그 외(HOLD) → intent 생성 안 함

    Args:
        asset_states: {asset_id: _AssetState} (position, signal_state)
        strategies: {asset_id: SignalStrategy}
        asset_signal_dfs: {asset_id: signal DataFrame}
        equity_vals: {asset_id: 현재 평가액}
        slot_dict: {asset_id: AssetSlotConfig}
        current_equity: 총 에쿼티
        i: 현재 행 인덱스
        current_date: 현재 날짜

    Returns:
        {asset_id: OrderIntent} — HOLD 자산은 포함하지 않음
    """
    intents: dict[str, OrderIntent] = {}

    for asset_id, state in asset_states.items():
        strategy = strategies[asset_id]
        signal_df = asset_signal_dfs[asset_id]
        slot = slot_dict[asset_id]

        if state.position == 0:
            # 매수 시그널 판정 (내부 prev 상태 갱신 포함)
            buy_now = strategy.check_buy(signal_df, i, current_date)
            if buy_now:
                meta = strategy.get_buy_meta()
                target_amount = current_equity * slot.target_weight
                intents[asset_id] = OrderIntent(
                    asset_id=asset_id,
                    intent_type="ENTER_TO_TARGET",
                    current_amount=0.0,
                    target_amount=target_amount,
                    delta_amount=target_amount,
                    target_weight=slot.target_weight,
                    reason="signal buy",
                    hold_days_used=int(meta.get("hold_days_used", 0)),
                )
        elif state.position > 0:
            # 매도 시그널 판정 (내부 prev 상태 갱신 포함)
            sell_now = strategy.check_sell(signal_df, i)
            if sell_now:
                current_amount = equity_vals.get(asset_id, 0.0)
                intents[asset_id] = OrderIntent(
                    asset_id=asset_id,
                    intent_type="EXIT_ALL",
                    current_amount=current_amount,
                    target_amount=0.0,
                    delta_amount=-current_amount,
                    target_weight=0.0,
                    reason="signal sell",
                )

    return intents


def _compute_projected_portfolio(
    asset_states: dict[str, "_AssetState"],
    signal_intents: dict[str, OrderIntent],
    equity_vals: dict[str, float],
    asset_closes_map: dict[str, float],
    shared_cash: float,
) -> _ProjectedPortfolio:
    """signal intents 반영 후 예상 포트폴리오 상태를 계산한다.

    signal intent 실행 결과를 반영하여 리밸런싱의 기준이 되는 projected 상태를 구성한다.

    - EXIT_ALL 자산: projected_amounts[asset_id]=0, active에서 제거, cash 증가 (현재 평가액 추가)
    - ENTER_TO_TARGET 자산: active에 추가 (아직 position=0이므로 projected_amounts=0 유지)
    - 기타 자산: 현재 상태 유지

    Args:
        asset_states: {asset_id: _AssetState}
        signal_intents: {asset_id: OrderIntent} — EXIT_ALL 또는 ENTER_TO_TARGET
        equity_vals: {asset_id: 현재 평가액}
        asset_closes_map: {asset_id: 현재 종가} (사용 안 함, 확장성 위해 유지)
        shared_cash: 현재 미투자 현금

    Returns:
        _ProjectedPortfolio (projected_amounts, projected_cash, active_assets)
    """
    # 현재 active_assets: signal_state == "buy"인 자산
    active_assets: set[str] = {aid for aid, st in asset_states.items() if st.signal_state == "buy"}

    # projected_amounts: 현재 평가액에서 시작
    projected_amounts: dict[str, float] = {aid: equity_vals.get(aid, 0.0) for aid in asset_states}
    projected_cash = shared_cash

    for asset_id, intent in signal_intents.items():
        if intent.intent_type == "EXIT_ALL":
            # 전량 청산: 평가액 → cash로 이동, active에서 제거
            projected_cash += equity_vals.get(asset_id, 0.0)
            projected_amounts[asset_id] = 0.0
            active_assets.discard(asset_id)

        elif intent.intent_type == "ENTER_TO_TARGET":
            # 신규 진입 예정: active에 추가 (아직 position=0)
            active_assets.add(asset_id)
            # projected_amounts[asset_id]는 0.0 유지 (position 없음)

    return _ProjectedPortfolio(
        projected_amounts=projected_amounts,
        projected_cash=projected_cash,
        active_assets=active_assets,
    )


def _build_rebalance_intents(
    projected: _ProjectedPortfolio,
    slot_dict: dict[str, AssetSlotConfig],
    total_equity_projected: float,
    threshold: float,
    current_date: date,
) -> dict[str, OrderIntent]:
    """projected 상태 기반으로 리밸런싱 intent를 생성한다.

    1. active_assets 중 |actual/target - 1| > threshold인 자산이 없으면 {} 반환
    2. 하나라도 초과 시: 전체 active 자산에 대해 REDUCE_TO_TARGET / INCREASE_TO_TARGET 생성
    3. scale_factor: projected_cash + 예상 매도 수익 기준 매수 가능액 계산

    Args:
        projected: _ProjectedPortfolio (signal intents 반영 후 예상 상태)
        slot_dict: {asset_id: AssetSlotConfig} (target_weight 참조용)
        total_equity_projected: projected 상태 기준 총 에쿼티
        threshold: 리밸런싱 임계값 (월: MONTHLY_REBALANCE_THRESHOLD_RATE, 일: DAILY_REBALANCE_THRESHOLD_RATE)
        current_date: 현재 날짜 (OrderIntent.reason 기록용)

    Returns:
        {asset_id: OrderIntent} — threshold 미초과 시 빈 dict
    """
    if total_equity_projected < EPSILON:
        return {}

    # 1. threshold 초과 여부 확인 (active_assets만 대상)
    threshold_exceeded = False
    for asset_id in projected.active_assets:
        slot = slot_dict.get(asset_id)
        if slot is None or slot.target_weight == 0:
            continue
        current_amount = projected.projected_amounts.get(asset_id, 0.0)
        actual_weight = current_amount / total_equity_projected
        deviation = abs(actual_weight / slot.target_weight - 1.0)
        if deviation > threshold:
            threshold_exceeded = True
            break

    if not threshold_exceeded:
        return {}

    # 2. active_assets 전체에 대해 매도/매수 intent 생성
    sell_intents: dict[str, float] = {}  # {asset_id: 매도 필요 금액}
    buy_intents: dict[str, float] = {}  # {asset_id: 매수 필요 금액}

    for asset_id in projected.active_assets:
        slot = slot_dict.get(asset_id)
        if slot is None:
            continue
        target_amount = total_equity_projected * slot.target_weight
        current_amount = projected.projected_amounts.get(asset_id, 0.0)
        delta = target_amount - current_amount
        if delta < 0:
            sell_intents[asset_id] = abs(delta)
        elif delta > 0:
            buy_intents[asset_id] = delta

    # 3. 현금 부족 시 scale_factor 비례 축소
    estimated_sell_proceeds = sum(sell_intents.values())
    available_cash = projected.projected_cash + estimated_sell_proceeds
    total_buy_needed = sum(buy_intents.values())

    if total_buy_needed > available_cash and total_buy_needed > EPSILON:
        scale_factor = available_cash / total_buy_needed
        buy_intents = {aid: amt * scale_factor for aid, amt in buy_intents.items()}

    # 4. OrderIntent 생성
    result: dict[str, OrderIntent] = {}

    for asset_id, excess_value in sell_intents.items():
        slot = slot_dict[asset_id]
        current_amount = projected.projected_amounts.get(asset_id, 0.0)
        target_amount = total_equity_projected * slot.target_weight
        result[asset_id] = OrderIntent(
            asset_id=asset_id,
            intent_type="REDUCE_TO_TARGET",
            current_amount=current_amount,
            target_amount=target_amount,
            delta_amount=-excess_value,
            target_weight=slot.target_weight,
            reason=f"rebalance {current_date}",
        )

    for asset_id, buy_amount in buy_intents.items():
        slot = slot_dict[asset_id]
        current_amount = projected.projected_amounts.get(asset_id, 0.0)
        target_amount = total_equity_projected * slot.target_weight
        result[asset_id] = OrderIntent(
            asset_id=asset_id,
            intent_type="INCREASE_TO_TARGET",
            current_amount=current_amount,
            target_amount=target_amount,
            delta_amount=buy_amount,
            target_weight=slot.target_weight,
            reason=f"rebalance {current_date}",
        )

    return result


def _merge_intents(
    signal_intents: dict[str, OrderIntent],
    rebalance_intents: dict[str, OrderIntent],
) -> dict[str, OrderIntent]:
    """signal intent와 rebalance intent를 통합하여 자산당 1개를 반환한다.

    우선순위 규칙:
    1. EXIT_ALL: 항상 우선 (rebalance intent 무시)
    2. ENTER_TO_TARGET + INCREASE_TO_TARGET → ENTER_TO_TARGET (rebalance target_amount/delta_amount 사용)
    3. 단독 signal intent → 그대로 통과
    4. 단독 rebalance intent → 그대로 통과

    EXIT_ALL + REDUCE 조합은 _compute_projected_portfolio가 선행되므로 발생하지 않는다.
    (EXIT_ALL 자산은 projected에서 active_assets에서 제거되므로 rebalance 대상 제외)

    Args:
        signal_intents: {asset_id: OrderIntent} — signal에서 생성
        rebalance_intents: {asset_id: OrderIntent} — rebalance에서 생성

    Returns:
        {asset_id: OrderIntent} — 자산당 1개 보장
    """
    merged: dict[str, OrderIntent] = {}
    all_assets = set(signal_intents) | set(rebalance_intents)

    for asset_id in all_assets:
        sig = signal_intents.get(asset_id)
        reb = rebalance_intents.get(asset_id)

        if sig is not None and sig.intent_type == "EXIT_ALL":
            # EXIT_ALL은 항상 우선
            merged[asset_id] = sig
        elif (
            sig is not None
            and sig.intent_type == "ENTER_TO_TARGET"
            and reb is not None
            and reb.intent_type == "INCREASE_TO_TARGET"
        ):
            # 신규 진입 + 리밸런싱 매수 → ENTER_TO_TARGET (rebalance target 사용, signal hold_days_used 보존)
            merged[asset_id] = OrderIntent(
                asset_id=asset_id,
                intent_type="ENTER_TO_TARGET",
                current_amount=sig.current_amount,
                target_amount=reb.target_amount,
                delta_amount=reb.delta_amount,
                target_weight=reb.target_weight,
                reason="signal_buy+rebalance",
                hold_days_used=sig.hold_days_used,
            )
        elif sig is not None:
            merged[asset_id] = sig
        elif reb is not None:
            merged[asset_id] = reb

    return merged


def _execute_orders(
    order_intents: dict[str, OrderIntent],
    open_prices: dict[str, float],
    current_positions: dict[str, int],
    current_cash: float,
    entry_prices: dict[str, float],
    entry_dates: dict[str, date | None],
    entry_hold_days: dict[str, int],
    current_date: date,
) -> _ExecutionResult:
    """주문 의도 목록을 SELL → BUY 순으로 체결하고 결과를 반환한다.

    SELL을 먼저 체결하여 확보된 현금을 포함한 available_cash를 계산한 뒤
    BUY 체결에 활용한다. BUY 총 비용이 available_cash를 초과하면 자산별
    BUY amount를 동일 비율(scale_factor)로 축소하여 음수 현금이 발생하지 않도록 한다.

    처리 흐름:
        1. SELL 단계: EXIT_ALL(전량), REDUCE_TO_TARGET(delta_amount 기준) 체결
        2. CASH 확정: available_cash = current_cash + sell_proceeds
        3. BUY 단계:
           a. raw_shares = floor(delta_amount / buy_price)
           b. total_raw_cost = Σ raw_shares × buy_price
           c. total_raw_cost > available_cash 이면 scale_factor 적용
              adjusted_amount = delta_amount × scale_factor
              shares = floor(adjusted_amount / buy_price)
           d. ENTER_TO_TARGET: 신규 진입, entry 정보 기록
              INCREASE_TO_TARGET: 가중평균 entry_price 업데이트
        4. _ExecutionResult 반환

    Args:
        order_intents: {asset_id: OrderIntent} — 체결할 주문 의도 목록
        open_prices: {asset_id: 당일 시가} — 체결 기준 가격
        current_positions: {asset_id: 현재 보유 수량}
        current_cash: 현재 보유 현금
        entry_prices: {asset_id: 진입 가격}
        entry_dates: {asset_id: 진입 날짜}
        entry_hold_days: {asset_id: 진입 시 hold_days}
        current_date: 체결 날짜

    Returns:
        _ExecutionResult (updated_cash, updated_positions, updated_entry_prices,
                          updated_entry_dates, updated_entry_hold_days, new_trades, rebalanced_today)
    """
    # 1. 상태 복사 (원본 불변)
    positions = dict(current_positions)
    e_prices = dict(entry_prices)
    e_dates = dict(entry_dates)
    e_hold_days = dict(entry_hold_days)
    cash = current_cash
    new_trades: list[dict[str, Any]] = []
    rebalanced_today = False

    # 2. SELL 선행 체결 (EXIT_ALL, REDUCE_TO_TARGET)
    for asset_id, intent in order_intents.items():
        if intent.intent_type not in ("EXIT_ALL", "REDUCE_TO_TARGET"):
            continue
        position = positions.get(asset_id, 0)
        if position <= 0:
            continue

        open_price = open_prices.get(asset_id, 0.0)
        sell_price = open_price * (1.0 - SLIPPAGE_RATE)

        if intent.intent_type == "EXIT_ALL":
            shares_sold = position
        else:
            # REDUCE_TO_TARGET: delta_amount 기준 수량 (내림)
            shares_to_sell = int(abs(intent.delta_amount) / sell_price)
            shares_sold = min(shares_to_sell, position)

        if shares_sold > 0:
            sell_amount = shares_sold * sell_price
            cash += sell_amount

            e_date = e_dates.get(asset_id)
            e_price = e_prices.get(asset_id, 0.0)

            trade_record: dict[str, Any] = {
                "entry_date": e_date,
                "exit_date": current_date,
                "entry_price": e_price,
                "exit_price": sell_price,
                "shares": shares_sold,
                "pnl": (sell_price - e_price) * shares_sold,
                "pnl_pct": (sell_price - e_price) / (e_price + EPSILON),
                "hold_days_used": e_hold_days.get(asset_id, 0),
                "asset_id": asset_id,
                "trade_type": "rebalance" if intent.intent_type == "REDUCE_TO_TARGET" else "signal",
            }
            new_trades.append(trade_record)

            positions[asset_id] = position - shares_sold

            # 전량 매도(position=0)인 경우에만 진입 정보 초기화
            if positions[asset_id] == 0:
                e_prices[asset_id] = 0.0
                e_dates[asset_id] = None

            if intent.intent_type == "REDUCE_TO_TARGET":
                rebalanced_today = True

            logger.debug(
                f"매도 체결: {asset_id}, 날짜={current_date}, "
                f"가격={sell_price:.2f}, 수량={shares_sold}, "
                f"잔여포지션={positions[asset_id]}"
            )

    # 3. BUY 후행 체결 (ENTER_TO_TARGET, INCREASE_TO_TARGET)
    # 3-1. raw_shares 및 raw_cost 계산 (scale 전)
    buy_order_ids: list[str] = []
    buy_raw_shares: dict[str, int] = {}
    buy_prices_map: dict[str, float] = {}

    for asset_id, intent in order_intents.items():
        if intent.intent_type not in ("ENTER_TO_TARGET", "INCREASE_TO_TARGET"):
            continue
        if intent.delta_amount <= 0:
            continue
        open_price = open_prices.get(asset_id, 0.0)
        buy_price = open_price * (1.0 + SLIPPAGE_RATE)
        raw_shares = int(intent.delta_amount / buy_price)
        if raw_shares > 0:
            buy_order_ids.append(asset_id)
            buy_raw_shares[asset_id] = raw_shares
            buy_prices_map[asset_id] = buy_price

    # 3-2. available_cash vs total_raw_cost → scale_factor 결정
    # available_cash: SELL 체결 후 확보된 현금 (sell_proceeds 포함)
    available_cash = cash
    total_raw_cost = sum(buy_raw_shares[aid] * buy_prices_map[aid] for aid in buy_order_ids)

    if total_raw_cost > available_cash and total_raw_cost > EPSILON:
        scale_factor = available_cash / total_raw_cost
    else:
        scale_factor = 1.0

    # 3-3. BUY 체결 (scale_factor 적용)
    for asset_id in buy_order_ids:
        intent = order_intents[asset_id]
        buy_price = buy_prices_map[asset_id]

        if scale_factor < 1.0:
            # 비례 축소: raw_shares × scale_factor 기준으로 shares 재계산
            # delta_amount 기준이 아닌 raw_shares 기준으로 scale해야
            # Σ(shares × buy_price) ≤ available_cash 보장 (음수 현금 방지)
            shares = int(buy_raw_shares[asset_id] * scale_factor)
        else:
            shares = buy_raw_shares[asset_id]

        if shares > 0:
            cost = shares * buy_price
            cash -= cost

            prev_position = positions.get(asset_id, 0)
            if prev_position == 0:
                # 신규 진입 (ENTER_TO_TARGET)
                positions[asset_id] = shares
                e_prices[asset_id] = buy_price
                e_dates[asset_id] = current_date
                e_hold_days[asset_id] = intent.hold_days_used
            else:
                # 리밸런싱 추가매수 (INCREASE_TO_TARGET): entry_price 가중평균 업데이트
                prev_entry_price = e_prices.get(asset_id, 0.0)
                positions[asset_id] = prev_position + shares
                e_prices[asset_id] = (prev_entry_price * prev_position + buy_price * shares) / positions[asset_id]

            if intent.intent_type == "INCREASE_TO_TARGET":
                rebalanced_today = True

            logger.debug(f"매수 체결: {asset_id}, 날짜={current_date}, 가격={buy_price:.2f}, 수량={shares}")

    return _ExecutionResult(
        updated_cash=cash,
        updated_positions=positions,
        updated_entry_prices=e_prices,
        updated_entry_dates=e_dates,
        updated_entry_hold_days=e_hold_days,
        new_trades=new_trades,
        rebalanced_today=rebalanced_today,
    )


# ============================================================================
# 내부 헬퍼 함수
# ============================================================================


def _load_and_prepare_data(
    slot: AssetSlotConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """자산 슬롯의 데이터를 로딩하고 MA를 계산한다.

    buffer_zone 슬롯: 슬롯별 MA 파라미터(ma_window, ma_type)로 이동평균 계산.
    buy_and_hold 슬롯: MA 계산 생략 (불필요).

    Args:
        slot: 자산 슬롯 설정

    Returns:
        (signal_df, trade_df) — buffer_zone이면 MA 컬럼 포함
    """
    signal_df = load_stock_data(slot.signal_data_path)
    trade_df = load_stock_data(slot.trade_data_path)

    # signal/trade 데이터 경로가 다르면 교집합 기간 추출
    if slot.signal_data_path != slot.trade_data_path:
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    # MA 계산 (buffer_zone 슬롯만)
    if slot.strategy_type == "buffer_zone":
        signal_df = add_single_moving_average(signal_df, slot.ma_window, slot.ma_type)

    return signal_df, trade_df


def _validate_portfolio_config(config: PortfolioConfig) -> None:
    """포트폴리오 설정을 검증한다.

    Args:
        config: 포트폴리오 설정

    Raises:
        ValueError: 검증 실패 시
    """
    # 1. target_weight 합 ≤ 1.0
    total_weight = sum(slot.target_weight for slot in config.asset_slots)
    if total_weight > 1.0 + EPSILON:
        raise ValueError(
            f"target_weight 합이 1.0을 초과합니다: {total_weight:.4f} " f"(자산: {[s.asset_id for s in config.asset_slots]})"
        )

    # 2. target_weight ≥ 0
    for slot in config.asset_slots:
        if slot.target_weight < 0:
            raise ValueError(
                f"target_weight는 0 이상이어야 합니다: asset_id={slot.asset_id}, " f"target_weight={slot.target_weight}"
            )

    # 3. asset_id 중복 없음
    asset_ids = [slot.asset_id for slot in config.asset_slots]
    if len(asset_ids) != len(set(asset_ids)):
        seen = set()
        duplicates = [aid for aid in asset_ids if aid in seen or seen.add(aid)]  # type: ignore[func-returns-value]
        raise ValueError(f"asset_id 중복이 있습니다: {duplicates}")


def _build_combined_equity(
    equity_rows: list[dict[str, Any]],
    initial_capital: float,
) -> pd.DataFrame:
    """에쿼티 행 목록을 DataFrame으로 변환하고 drawdown을 계산한다."""
    equity_df = pd.DataFrame(equity_rows)

    # drawdown 계산
    peak = equity_df["equity"].cummax()
    equity_df["drawdown_pct"] = (equity_df["equity"] - peak) / (peak + EPSILON) * 100.0

    return equity_df


# ============================================================================
# 공개 API
# ============================================================================


def compute_portfolio_effective_start_date(config: PortfolioConfig) -> date:
    """포트폴리오 실험의 유효 시작일을 계산한다.

    전 자산 데이터의 날짜 교집합을 구하고 buffer_zone 슬롯의 MA 워밍업 완료 이후
    첫 날짜를 반환한다. buy_and_hold 슬롯은 MA 워밍업이 없으므로 valid_start 계산에서 제외.
    여러 실험을 동일 기간으로 정렬할 때 글로벌 시작일을 결정하는 데 사용한다.

    Args:
        config: 포트폴리오 실험 설정

    Returns:
        MA 워밍업 완료 이후 첫 유효 거래일 (date 객체)

    Raises:
        ValueError: 공통 기간 없음 또는 MA 컬럼 누락 시
    """
    # 1. 자산별 데이터 로딩 + MA 계산 (signal_data_path 기준 캐시, 슬롯별 MA 파라미터 사용)
    signal_cache: dict[str, pd.DataFrame] = {}
    asset_trade_dfs: dict[str, pd.DataFrame] = {}
    asset_signal_dfs: dict[str, pd.DataFrame] = {}
    slot_dict = {slot.asset_id: slot for slot in config.asset_slots}

    for slot in config.asset_slots:
        signal_key = f"{slot.signal_data_path}::{slot.strategy_type}::{slot.ma_window}::{slot.ma_type}"
        if signal_key not in signal_cache:
            signal_df_raw, trade_df = _load_and_prepare_data(slot)
            signal_cache[signal_key] = signal_df_raw
        else:
            signal_df_raw = signal_cache[signal_key]
            trade_df = load_stock_data(slot.trade_data_path)
            if slot.signal_data_path != slot.trade_data_path:
                signal_df_raw, trade_df = extract_overlap_period(signal_df_raw.copy(), trade_df)

        asset_signal_dfs[slot.asset_id] = signal_df_raw
        asset_trade_dfs[slot.asset_id] = trade_df

    # 2. 공통 기간 추출 (전 자산 trade_df의 날짜 교집합)
    date_sets = [set(df[COL_DATE]) for df in asset_trade_dfs.values()]
    common_dates_set: set[date] = date_sets[0]
    for ds in date_sets[1:]:
        common_dates_set &= ds

    if not common_dates_set:
        raise ValueError("전 자산의 공통 거래 기간이 없습니다.")

    # 공통 기간으로 필터링
    for asset_id in asset_signal_dfs:
        signal_df = asset_signal_dfs[asset_id]
        trade_df = asset_trade_dfs[asset_id]

        mask_s = pd.Series(signal_df[COL_DATE]).isin(common_dates_set)
        mask_t = pd.Series(trade_df[COL_DATE]).isin(common_dates_set)

        asset_signal_dfs[asset_id] = signal_df[mask_s.values].reset_index(drop=True)
        asset_trade_dfs[asset_id] = trade_df[mask_t.values].reset_index(drop=True)

    # 3. MA 유효 구간 필터링 (buffer_zone 슬롯만 대상, buy_and_hold는 MA 없음)
    valid_start_indices: list[int] = []
    for asset_id in asset_signal_dfs:
        slot = slot_dict[asset_id]
        if slot.strategy_type != "buffer_zone":
            continue
        ma_col = f"ma_{slot.ma_window}"
        sdf = asset_signal_dfs[asset_id]
        if ma_col not in sdf.columns:
            raise ValueError(f"MA 컬럼 누락: {ma_col} (asset_id={asset_id})")
        valid_mask = sdf[ma_col].notna()
        if valid_mask.any():
            valid_start_indices.append(int(valid_mask.idxmax()))
        else:
            valid_start_indices.append(len(sdf))

    valid_start = max(valid_start_indices) if valid_start_indices else 0

    # 4. 유효 시작 인덱스의 첫 trade_df 날짜 반환
    first_trade_df = next(iter(asset_trade_dfs.values()))
    first_trade_df_filtered = first_trade_df.iloc[valid_start:].reset_index(drop=True)

    if len(first_trade_df_filtered) < 1:
        raise ValueError("유효 데이터 부족: MA 워밍업 후 데이터가 없습니다.")

    return date(
        first_trade_df_filtered[COL_DATE].iloc[0].year,
        first_trade_df_filtered[COL_DATE].iloc[0].month,
        first_trade_df_filtered[COL_DATE].iloc[0].day,
    )


def run_portfolio_backtest(config: PortfolioConfig, start_date: date | None = None) -> PortfolioResult:
    """포트폴리오 백테스트를 실행한다.

    복수 자산의 독립 시그널 + 목표 비중 배분 + 이중 트리거 리밸런싱을 수행한다.
    OrderIntent 기반 주문 모델로 signal과 rebalance 충돌을 merge_intents가 해소한다.

    메인 루프 흐름:
        Step A: SELL 체결 (전일 next_day_intents: EXIT_ALL, REDUCE_TO_TARGET)
        Step B: BUY 체결 (전일 next_day_intents: ENTER_TO_TARGET, INCREASE_TO_TARGET)
        Step C: Equity 계산 (당일 종가 기준)
        Step D: Signal → Projected → Rebalance → Merge → next_day_intents
        Step E: Equity row 기록

    Args:
        config: 포트폴리오 실험 설정
        start_date: 백테스트 시작일 하한 (None이면 MA 워밍업 완료 시점부터 자동 결정).
            여러 실험을 동일 기간으로 정렬할 때 global_start_date를 전달한다.

    Returns:
        PortfolioResult (equity_df, trades_df, summary, per_asset 포함)

    Raises:
        ValueError: 설정 검증 실패 또는 공통 기간 없음
    """
    logger.debug(f"포트폴리오 백테스트 시작: {config.experiment_name}")

    # 1. 설정 검증
    _validate_portfolio_config(config)

    slot_dict = {slot.asset_id: slot for slot in config.asset_slots}

    # 2. 자산별 데이터 로딩 + MA 계산 (슬롯별 MA 파라미터 사용)
    # signal_data_path 기준으로 중복 로딩 방지 (캐시)
    signal_cache: dict[str, pd.DataFrame] = {}
    asset_signal_dfs: dict[str, pd.DataFrame] = {}
    asset_trade_dfs: dict[str, pd.DataFrame] = {}

    for slot in config.asset_slots:
        signal_key = f"{slot.signal_data_path}::{slot.strategy_type}::{slot.ma_window}::{slot.ma_type}"
        if signal_key not in signal_cache:
            signal_df_raw, trade_df = _load_and_prepare_data(slot)
            signal_cache[signal_key] = signal_df_raw
        else:
            # 같은 시그널 경로 → 캐시 재사용
            signal_df_raw = signal_cache[signal_key]
            trade_df = load_stock_data(slot.trade_data_path)
            if slot.signal_data_path != slot.trade_data_path:
                signal_df_raw, trade_df = extract_overlap_period(signal_df_raw.copy(), trade_df)

        asset_signal_dfs[slot.asset_id] = signal_df_raw
        asset_trade_dfs[slot.asset_id] = trade_df

    # 3. 공통 기간 추출 (전 자산 trade_df의 날짜 교집합)
    date_sets = [set(df[COL_DATE]) for df in asset_trade_dfs.values()]
    common_dates_set: set[date] = date_sets[0]
    for ds in date_sets[1:]:
        common_dates_set &= ds

    if not common_dates_set:
        raise ValueError("전 자산의 공통 거래 기간이 없습니다.")

    # 공통 기간으로 필터링
    for asset_id in asset_signal_dfs:
        signal_df = asset_signal_dfs[asset_id]
        trade_df = asset_trade_dfs[asset_id]

        mask_s = pd.Series(signal_df[COL_DATE]).isin(common_dates_set)
        mask_t = pd.Series(trade_df[COL_DATE]).isin(common_dates_set)

        asset_signal_dfs[asset_id] = signal_df[mask_s.values].reset_index(drop=True)
        asset_trade_dfs[asset_id] = trade_df[mask_t.values].reset_index(drop=True)

    # MA 유효 구간 필터링 (buffer_zone 슬롯의 MA NaN 기준만, buy_and_hold 슬롯 제외)
    valid_start_indices: list[int] = []
    for asset_id in asset_signal_dfs:
        slot = slot_dict[asset_id]
        if slot.strategy_type != "buffer_zone":
            continue
        ma_col = f"ma_{slot.ma_window}"
        sdf = asset_signal_dfs[asset_id]
        if ma_col not in sdf.columns:
            raise ValueError(f"MA 컬럼 누락: {ma_col} (asset_id={asset_id})")
        valid_mask = sdf[ma_col].notna()
        if valid_mask.any():
            valid_start_indices.append(int(valid_mask.idxmax()))
        else:
            valid_start_indices.append(len(sdf))

    valid_start = max(valid_start_indices) if valid_start_indices else 0

    for asset_id in asset_signal_dfs:
        asset_signal_dfs[asset_id] = asset_signal_dfs[asset_id].iloc[valid_start:].reset_index(drop=True)
        asset_trade_dfs[asset_id] = asset_trade_dfs[asset_id].iloc[valid_start:].reset_index(drop=True)

    # start_date 필터: MA 워밍업 완료 이후 추가로 시작일 하한 적용
    # 여러 실험의 공통 기간 정렬 시 사용 (global_start_date 전달)
    if start_date is not None:
        for asset_id in asset_signal_dfs:
            sdf = asset_signal_dfs[asset_id]
            tdf = asset_trade_dfs[asset_id]
            mask_s = pd.Series(sdf[COL_DATE]) >= start_date
            mask_t = pd.Series(tdf[COL_DATE]) >= start_date
            asset_signal_dfs[asset_id] = sdf[mask_s.values].reset_index(drop=True)
            asset_trade_dfs[asset_id] = tdf[mask_t.values].reset_index(drop=True)

    n = len(next(iter(asset_trade_dfs.values())))
    if n < 2:
        raise ValueError(f"유효 데이터 부족: {n}행 (최소 2행 필요)")

    trade_dates = list(next(iter(asset_trade_dfs.values()))[COL_DATE])

    # 4. 전략 객체 생성 (자산별 strategy_type 기반 팩토리, 슬롯별 파라미터 사용)
    strategies: dict[str, SignalStrategy] = {
        slot.asset_id: _create_strategy_for_slot(slot) for slot in config.asset_slots
    }

    # 5. 자산별 상태 초기화 (모든 자산 "sell"로 시작, pending_order 없음)
    asset_states: dict[str, _AssetState] = {
        slot.asset_id: _AssetState(position=0, signal_state="sell") for slot in config.asset_slots
    }

    shared_cash = config.total_capital

    # 자산별 진입 정보 (entry_price, entry_date, entry_hold_days)
    entry_prices: dict[str, float] = {slot.asset_id: 0.0 for slot in config.asset_slots}
    entry_dates: dict[str, date | None] = {slot.asset_id: None for slot in config.asset_slots}
    entry_hold_days: dict[str, int] = {slot.asset_id: 0 for slot in config.asset_slots}

    # 거래 기록 및 에쿼티 기록
    all_trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []

    # next_day_intents: 전일 생성된 merged intents → 당일 체결 대상
    next_day_intents: dict[str, OrderIntent] = {}

    # 6. 메인 루프: 전일 intents 체결 → 당일 에쿼티 → 당일 signal → projected → rebalance → merge
    # 신호와 체결을 하루씩 분리(Lookahead 방지): i일 종가 시그널 → i+1일 시가 체결
    for i in range(0, n):
        current_date = trade_dates[i]
        rebalanced_today = False

        # Step A+B: SELL → BUY 순 체결 (SELL 확보 현금 → BUY에 활용, 부족 시 비례 축소)
        open_prices_map: dict[str, float] = {aid: float(asset_trade_dfs[aid].iloc[i][COL_OPEN]) for aid in asset_states}
        exec_result = _execute_orders(
            order_intents=next_day_intents,
            open_prices=open_prices_map,
            current_positions={aid: st.position for aid, st in asset_states.items()},
            current_cash=shared_cash,
            entry_prices=entry_prices,
            entry_dates=entry_dates,
            entry_hold_days=entry_hold_days,
            current_date=current_date,
        )
        shared_cash = exec_result.updated_cash
        for aid, new_pos in exec_result.updated_positions.items():
            if aid in asset_states:
                asset_states[aid].position = new_pos
        entry_prices = exec_result.updated_entry_prices
        entry_dates = exec_result.updated_entry_dates
        entry_hold_days = exec_result.updated_entry_hold_days
        all_trades.extend(exec_result.new_trades)
        rebalanced_today = exec_result.rebalanced_today

        # Step C: 에쿼티 계산 (체결 완료 후, 당일 종가 기준)
        # 체결 후에 계산해야 리밸런싱 판정 시 목표 비중 편차가 정확히 반영된다
        asset_positions = {aid: st.position for aid, st in asset_states.items()}
        asset_closes_map: dict[str, float] = {}
        for asset_id in asset_states:
            trade_df = asset_trade_dfs[asset_id]
            asset_closes_map[asset_id] = float(trade_df.iloc[i][COL_CLOSE])

        current_equity = _compute_portfolio_equity(shared_cash, asset_positions, asset_closes_map)

        # Step D: Signal → Projected → Rebalance → Merge (익일 체결용 next_day_intents 생성)
        equity_vals_now: dict[str, float] = {
            aid: asset_states[aid].position * asset_closes_map[aid] for aid in asset_states
        }

        # D.1: signal intents 생성 (전략 호출, 내부 prev 상태 갱신 포함)
        signal_intents = _generate_signal_intents(
            asset_states, strategies, asset_signal_dfs, equity_vals_now, slot_dict, current_equity, i, current_date
        )

        # D.2: projected portfolio 계산 (signal intents 반영 후 예상 상태)
        projected = _compute_projected_portfolio(
            asset_states, signal_intents, equity_vals_now, asset_closes_map, shared_cash
        )

        # D.3: rebalance intents 생성 (projected 기준, 이중 트리거 임계값 적용)
        total_equity_projected = projected.projected_cash + sum(projected.projected_amounts.values())
        is_month_start = _is_first_trading_day_of_month(trade_dates, i)
        threshold = MONTHLY_REBALANCE_THRESHOLD_RATE if is_month_start else DAILY_REBALANCE_THRESHOLD_RATE
        rebalance_intents = _build_rebalance_intents(
            projected, slot_dict, total_equity_projected, threshold, current_date
        )

        # D.4: signal + rebalance 통합 (우선순위 규칙 적용, 자산당 1개 보장)
        merged_intents = _merge_intents(signal_intents, rebalance_intents)

        # D.5: signal_state 업데이트 (EXIT_ALL → "sell", ENTER_TO_TARGET → "buy")
        for asset_id, intent in merged_intents.items():
            if intent.intent_type == "EXIT_ALL":
                asset_states[asset_id].signal_state = "sell"
            elif intent.intent_type == "ENTER_TO_TARGET":
                asset_states[asset_id].signal_state = "buy"

        # D.6: 익일 체결용 intents 저장
        next_day_intents = merged_intents

        # Step E: 에쿼티 행 기록 (자산별 value/weight/signal 포함)
        row: dict[str, Any] = {
            COL_DATE: current_date,
            "equity": current_equity,
            "cash": shared_cash,
            "rebalanced": rebalanced_today,
        }
        for asset_id, st in asset_states.items():
            val = st.position * asset_closes_map[asset_id]
            row[f"{asset_id}_value"] = val
            row[f"{asset_id}_weight"] = val / (current_equity + EPSILON)
            row[f"{asset_id}_signal"] = st.signal_state
        equity_rows.append(row)

    # 8. 결과 조합
    equity_df = _build_combined_equity(equity_rows, config.total_capital)

    # trades_df 정리
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
        if "trade_type" not in trades_df.columns:
            trades_df["trade_type"] = "signal"
    else:
        trades_df = pd.DataFrame(
            columns=[
                "entry_date",
                "exit_date",
                "entry_price",
                "exit_price",
                "shares",
                "pnl",
                "pnl_pct",
                "hold_days_used",
                "asset_id",
                "trade_type",
            ]
        )

    # 성과 요약 (합산 에쿼티 기준)
    summary = calculate_summary(trades_df, equity_df, config.total_capital)

    # 자산별 결과
    per_asset: list[PortfolioAssetResult] = []
    for slot in config.asset_slots:
        asset_id = slot.asset_id
        asset_trades = trades_df[trades_df["asset_id"] == asset_id] if len(trades_df) > 0 else pd.DataFrame()
        per_asset.append(
            PortfolioAssetResult(
                asset_id=asset_id,
                trades_df=asset_trades,
                signal_df=asset_signal_dfs[asset_id],
            )
        )

    # params_json 구성 (전략 파라미터는 슬롯 레벨로 이동)
    params_json: dict[str, Any] = {
        "experiment_name": config.experiment_name,
        "display_name": config.display_name,
        "total_capital": config.total_capital,
        # 리밸런싱 임계값: 엔진 레벨 상수로 고정 (모든 실험에 동일하게 적용됨)
        "monthly_rebalance_threshold_rate": MONTHLY_REBALANCE_THRESHOLD_RATE,
        "daily_rebalance_threshold_rate": DAILY_REBALANCE_THRESHOLD_RATE,
        "assets": [
            {
                "asset_id": slot.asset_id,
                "target_weight": slot.target_weight,
                "signal_data_path": str(slot.signal_data_path),
                "trade_data_path": str(slot.trade_data_path),
                "strategy_type": slot.strategy_type,
                "ma_window": slot.ma_window,
                "ma_type": slot.ma_type,
                "buy_buffer_zone_pct": slot.buy_buffer_zone_pct,
                "sell_buffer_zone_pct": slot.sell_buffer_zone_pct,
                "hold_days": slot.hold_days,
            }
            for slot in config.asset_slots
        ],
    }

    logger.debug(
        f"포트폴리오 백테스트 완료: {config.experiment_name}, "
        f"총 거래={len(trades_df)}, 총 수익률={summary.get('total_return_pct', 0):.2f}%"
    )

    return PortfolioResult(
        experiment_name=config.experiment_name,
        display_name=config.display_name,
        equity_df=equity_df,
        trades_df=trades_df,
        summary=summary,
        per_asset=per_asset,
        config=config,
        params_json=params_json,
    )
