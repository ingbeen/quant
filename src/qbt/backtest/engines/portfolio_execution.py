"""포트폴리오 체결 -- 자산 상태 및 SELL->BUY 순 주문 체결 함수"""

from dataclasses import dataclass
from datetime import date

from qbt.backtest.constants import COL_ENTRY_DATE, COL_EXIT_DATE
from qbt.backtest.engines.engine_common import (
    PortfolioTradeRecord,
    execute_buy_order,
    execute_sell_order,
)
from qbt.backtest.engines.portfolio_planning import OrderIntent
from qbt.common_constants import EPSILON
from qbt.utils import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutionResult:
    """execute_orders() 반환값.

    SELL -> BUY 순으로 체결한 결과를 담는다.
    """

    updated_cash: float
    updated_positions: dict[str, int]
    updated_entry_prices: dict[str, float]
    updated_entry_dates: dict[str, date | None]
    updated_entry_hold_days: dict[str, int]
    new_trades: list[PortfolioTradeRecord]
    rebalanced_today: bool


def execute_orders(
    order_intents: dict[str, OrderIntent],
    open_prices: dict[str, float],
    current_positions: dict[str, int],
    current_cash: float,
    entry_prices: dict[str, float],
    entry_dates: dict[str, date | None],
    entry_hold_days: dict[str, int],
    current_date: date,
) -> ExecutionResult:
    """주문 의도 목록을 SELL -> BUY 순으로 체결하고 결과를 반환한다.

    SELL을 먼저 체결하여 확보된 현금을 포함한 available_cash를 계산한 뒤
    BUY 체결에 활용한다. BUY 총 비용이 available_cash를 초과하면 자산별
    BUY amount를 동일 비율(scale_factor)로 축소하여 음수 현금이 발생하지 않도록 한다.

    처리 흐름:
        1. SELL 단계: EXIT_ALL(전량), REDUCE_TO_TARGET(delta_amount 기준) 체결
        2. CASH 확정: available_cash = current_cash + sell_proceeds
        3. BUY 단계:
           a. raw_shares = floor(delta_amount / buy_price)
           b. total_raw_cost = raw_shares x buy_price
           c. total_raw_cost > available_cash 이면 scale_factor 적용
              adjusted_amount = delta_amount x scale_factor
              shares = floor(adjusted_amount / buy_price)
           d. ENTER_TO_TARGET: 신규 진입, entry 정보 기록
              INCREASE_TO_TARGET: 가중평균 entry_price 업데이트
        4. ExecutionResult 반환

    Args:
        order_intents: {asset_id: OrderIntent}
        open_prices: {asset_id: 당일 시가}
        current_positions: {asset_id: 현재 보유 수량}
        current_cash: 현재 보유 현금
        entry_prices: {asset_id: 진입 가격}
        entry_dates: {asset_id: 진입 날짜}
        entry_hold_days: {asset_id: 진입 시 hold_days}
        current_date: 체결 날짜

    Returns:
        ExecutionResult
    """
    # 1. 상태 복사 (원본 불변)
    positions = dict(current_positions)
    e_prices = dict(entry_prices)
    e_dates = dict(entry_dates)
    e_hold_days = dict(entry_hold_days)
    cash = current_cash
    new_trades: list[PortfolioTradeRecord] = []
    rebalanced_today = False

    # 2. SELL 선행 체결 (EXIT_ALL, REDUCE_TO_TARGET)
    for asset_id, intent in order_intents.items():
        if intent.intent_type not in ("EXIT_ALL", "REDUCE_TO_TARGET"):
            continue
        position = positions.get(asset_id, 0)
        if position <= 0:
            raise RuntimeError(f"내부 불변조건 위반: SELL intent 대상의 position <= 0 (asset_id={asset_id}, position={position})")

        open_price = open_prices.get(asset_id, 0.0)
        e_date = e_dates.get(asset_id)
        e_price = e_prices.get(asset_id, 0.0)

        if intent.intent_type == "EXIT_ALL":
            shares_sold = position
        else:
            # REDUCE_TO_TARGET: delta_amount 기준 수량 (내림)
            # sell_price 계산을 위해 execute_sell_order 활용
            sell_price_for_calc, _, _, _ = execute_sell_order(open_price, 1, e_price)
            shares_to_sell = int(abs(intent.delta_amount) / sell_price_for_calc)
            shares_sold = min(shares_to_sell, position)

        if shares_sold > 0:
            sell_price, sell_amount, pnl, pnl_pct = execute_sell_order(open_price, shares_sold, e_price)
            cash += sell_amount

            assert e_date is not None, "position > 0이면 entry_date는 항상 존재해야 함"
            trade_record: PortfolioTradeRecord = {
                COL_ENTRY_DATE: e_date,
                COL_EXIT_DATE: current_date,
                "entry_price": e_price,
                "exit_price": sell_price,
                "shares": shares_sold,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "buy_buffer_pct": 0.0,
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
            raise RuntimeError(
                f"내부 불변조건 위반: BUY intent의 delta_amount <= 0 (asset_id={asset_id}, delta_amount={intent.delta_amount})"
            )
        open_price = open_prices.get(asset_id, 0.0)
        raw_shares, buy_price, _ = execute_buy_order(open_price, intent.delta_amount)
        if raw_shares > 0:
            buy_order_ids.append(asset_id)
            buy_raw_shares[asset_id] = raw_shares
            buy_prices_map[asset_id] = buy_price

    # 3-2. available_cash vs total_raw_cost -> scale_factor 결정
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
            # 비례 축소: raw_shares x scale_factor 기준으로 shares 재계산
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

    return ExecutionResult(
        updated_cash=cash,
        updated_positions=positions,
        updated_entry_prices=e_prices,
        updated_entry_dates=e_dates,
        updated_entry_hold_days=e_hold_days,
        new_trades=new_trades,
        rebalanced_today=rebalanced_today,
    )
