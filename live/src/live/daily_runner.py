"""일일 실행 메인 (순수 계산, 파일 I/O 없음).

설계서 4.2 의 실행 순서 중 **5 ~ 9 단계** (fill → 체결 → equity → 시그널 →
익일 pending 생성) 를 담당하는 순수 계산 함수이다. 파일 I/O 및 외부 네트워크
호출은 호출자(CLI 계층) 가 처리한다.

구현 원칙:

- 입력 ``LiveState`` 는 불변으로 다루고 새 객체를 반환 (원본 보호)
- QBT 코어 함수 재사용: ``generate_signal_intents``, ``compute_projected_portfolio``,
  ``merge_intents``, ``DEFAULT_REBALANCE_POLICY``, ``execute_orders``,
  ``is_first_trading_day_of_month``
- ``BufferZoneStrategy`` 의 상태는 :mod:`live.buffer_serializer` 로 왕복
- QBT 본체 수정 없음
"""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date

import pandas as pd

from live.buffer_serializer import extract_buffer_state, restore_buffer_state
from live.constants import get_live_portfolio_config
from live.models import (
    ActualFill,
    AssetLiveState,
    BufferZoneState,
    DailyResult,
    LiveState,
    MarketBundle,
    OrderIntent,
    PendingOrderDict,
    SignalDetection,
)
from qbt.backtest.engines.portfolio_execution import execute_orders
from qbt.backtest.engines.portfolio_planning import (
    compute_portfolio_equity,
    compute_projected_portfolio,
    create_strategy_for_slot,
    generate_signal_intents,
    merge_intents,
)
from qbt.backtest.engines.portfolio_rebalance import (
    DEFAULT_REBALANCE_POLICY,
    is_first_trading_day_of_month,
)
from qbt.backtest.portfolio_types import AssetSlotConfig, AssetState
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.strategy_common import SignalStrategy
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN, EPSILON

__all__ = ["run_daily"]


# ============================================================================
# 헬퍼 — 인덱스/전략/상태 변환
# ============================================================================


def _find_trade_index(trade_df: pd.DataFrame, trade_date: date) -> int:
    """trade_df 에서 주어진 날짜의 행 인덱스를 찾는다.

    Raises:
        ValueError: 해당 날짜가 trade_df 에 존재하지 않을 때.
    """
    matches = trade_df.index[trade_df[COL_DATE] == trade_date].tolist()
    if not matches:
        raise ValueError(f"trade_date {trade_date} 가 trade_df 에 없음")
    return int(matches[0])


def _build_slot_dict() -> dict[str, AssetSlotConfig]:
    """Q-2-2XS 의 asset_id → AssetSlotConfig 매핑을 반환."""
    config = get_live_portfolio_config()
    return {slot.asset_id: slot for slot in config.asset_slots}


def _create_strategies(slot_dict: dict[str, AssetSlotConfig]) -> dict[str, SignalStrategy]:
    """슬롯별 SignalStrategy 인스턴스 생성."""
    return {asset_id: create_strategy_for_slot(slot) for asset_id, slot in slot_dict.items()}


def _restore_buffer_strategies(strategies: dict[str, SignalStrategy], state: LiveState) -> None:
    """LiveState 의 buffer_zone_state 를 각 BufferZoneStrategy 에 복원 (in-place)."""
    for asset_id, strategy in strategies.items():
        if not isinstance(strategy, BufferZoneStrategy):
            continue
        bzs = state.assets[asset_id].buffer_zone_state
        if bzs is not None:
            restore_buffer_state(strategy, bzs)


def _extract_buffer_states(
    strategies: dict[str, SignalStrategy],
) -> dict[str, BufferZoneState]:
    """BufferZoneStrategy 각각에서 내부 상태를 추출."""
    out: dict[str, BufferZoneState] = {}
    for asset_id, strategy in strategies.items():
        if isinstance(strategy, BufferZoneStrategy):
            out[asset_id] = extract_buffer_state(strategy)
    return out


def _build_asset_states(state: LiveState) -> dict[str, AssetState]:
    """LiveState → QBT AssetState (model 축 기준).

    QBT ``AssetState.signal_state`` 는 ``Literal["buy", "sell"]`` 만 허용한다.
    live 의 "hold" 상태는 QBT 로 전달 시 "sell" 로 매핑한다 (포지션 없음과 동일).
    """
    out: dict[str, AssetState] = {}
    for asset_id, asset in state.assets.items():
        qbt_state = "buy" if asset.signal_state == "buy" else "sell"
        out[asset_id] = AssetState(position=asset.model_shares, signal_state=qbt_state)
    return out


def _pending_order_to_intent(pending: PendingOrderDict) -> OrderIntent:
    """PendingOrderDict → OrderIntent (execute_orders 호출용)."""
    return OrderIntent(
        asset_id=pending["asset_id"],
        intent_type=pending["intent_type"],  # type: ignore[arg-type]
        current_amount=pending["current_amount"],
        target_amount=pending["target_amount"],
        delta_amount=pending["delta_amount"],
        target_weight=pending["target_weight"],
        reason=pending["reason"],
        hold_days_used=pending["hold_days_used"],
    )


def _intent_to_pending_order(intent: OrderIntent, signal_date: date) -> PendingOrderDict:
    """OrderIntent → PendingOrderDict (state 저장용)."""
    return {
        "asset_id": intent.asset_id,
        "intent_type": intent.intent_type,
        "signal_date": signal_date.isoformat(),
        "current_amount": intent.current_amount,
        "target_amount": intent.target_amount,
        "delta_amount": intent.delta_amount,
        "target_weight": intent.target_weight,
        "hold_days_used": intent.hold_days_used,
        "reason": intent.reason,
    }


def _ema_col_name(slot: AssetSlotConfig) -> str:
    """슬롯의 MA 컬럼명을 반환 (예: ``ma_200``)."""
    return f"ma_{slot.ma_window}"


def _build_signal_detections(
    strategies: dict[str, SignalStrategy],
    market_bundle: MarketBundle,
    signal_intents: dict[str, OrderIntent],
    slot_dict: dict[str, AssetSlotConfig],
    i: int,
) -> tuple[dict[str, SignalDetection], dict[str, float]]:
    """signal_intents 와 시장 데이터를 기반으로 SignalDetection 및 ema_distance 를 계산."""
    signals: dict[str, SignalDetection] = {}
    ema_distances: dict[str, float] = {}

    for asset_id, slot in slot_dict.items():
        signal_df = market_bundle[asset_id].signal_df
        close = float(signal_df.iloc[i][COL_CLOSE])

        ma_col = _ema_col_name(slot)
        ema_200 = float(signal_df.iloc[i][ma_col]) if ma_col in signal_df.columns else None

        # 버퍼존 밴드 (BufferZoneStrategy 일 때만)
        upper_band: float | None = None
        lower_band: float | None = None
        if ema_200 is not None and isinstance(strategies[asset_id], BufferZoneStrategy):
            upper_band = ema_200 * (1.0 + slot.buy_buffer_zone_pct)
            lower_band = ema_200 * (1.0 - slot.sell_buffer_zone_pct)

        # EMA 근접도 (설계서 8장)
        if ema_200 is not None and ema_200 > 0:
            ema_distance_pct = (close - ema_200) / ema_200
        else:
            ema_distance_pct = 0.0
        ema_distances[asset_id] = ema_distance_pct

        # 시그널 상태 결정
        intent = signal_intents.get(asset_id)
        state_str: str = "hold"
        if intent is not None:
            if intent.intent_type == "ENTER_TO_TARGET":
                state_str = "buy"
            elif intent.intent_type == "EXIT_ALL":
                state_str = "sell"

        signals[asset_id] = SignalDetection(
            state=state_str,  # type: ignore[arg-type]
            close=close,
            upper_band=upper_band,
            lower_band=lower_band,
            ema_200=ema_200,
            ema_distance_pct=ema_distance_pct,
        )

    return signals, ema_distances


# ============================================================================
# 메인: run_daily
# ============================================================================


def run_daily(
    trade_date: date,
    state: LiveState,
    market_bundle: MarketBundle,
    pending_fills: list[ActualFill],
    applied_fill_ids: dict[str, str],
) -> DailyResult:
    """1 일치 live 실행을 수행한다 (순수 계산, 파일 I/O 없음).

    설계서 4.2 의 5 ~ 9 단계를 담당한다. 입력 ``state`` 는 불변으로 다루고
    새 ``LiveState`` 를 ``DailyResult.updated_state`` 로 반환한다.

    Args:
        trade_date: 처리 대상 거래일.
        state: 현재 LiveState (전일 실행 결과).
        market_bundle: 자산별 signal_df / trade_df.
        pending_fills: RTDB 에서 읽어온 미처리 fill 목록 (Step 8 에서 실제 반영).
        applied_fill_ids: 기존 적용된 fill ID → 타임스탬프 맵.

    Returns:
        DailyResult: 갱신된 LiveState + 시그널 / 체결 / drift 정보.
    """
    # 0. 입력 복사 (원본 불변 유지)
    working_state = copy.deepcopy(state)
    working_applied_ids = dict(applied_fill_ids)

    slot_dict = _build_slot_dict()

    # 1. 전략 객체 생성 및 저장된 버퍼존 상태 복원
    strategies = _create_strategies(slot_dict)
    _restore_buffer_strategies(strategies, working_state)

    # 2. Step 5 (fill 처리) — Step 8 에서 실제 로직 연결 예정.
    #    현재는 pending_fills 를 받기만 하고 실제 actual 반영은 하지 않는다.
    #    applied_fill_ids 에 rtdb_key 만 기록하는 것도 Step 8 에서 수행한다.
    pending_fill_reminders: list[str] = []

    # 3. 인덱스 결정 (자산별 trade_df 는 동일 날짜 집합이라 가정)
    first_asset_id = next(iter(market_bundle))
    i = _find_trade_index(market_bundle[first_asset_id].trade_df, trade_date)

    # 4. Step 6 (전일 pending → 당일 시가 체결, model 축)
    #    state.assets[].pending_order 가 있으면 OrderIntent 로 변환 후 execute_orders 호출.
    next_day_intents: dict[str, OrderIntent] = {}
    for asset_id, asset in working_state.assets.items():
        if asset.pending_order is not None:
            next_day_intents[asset_id] = _pending_order_to_intent(asset.pending_order)

    asset_states = _build_asset_states(working_state)
    shared_cash_model = working_state.shared_cash_model
    entry_prices: dict[str, float] = {aid: asset.model_avg_entry_price for aid, asset in working_state.assets.items()}
    entry_dates: dict[str, date | None] = {
        aid: (date.fromisoformat(asset.model_entry_date) if asset.model_entry_date else None)
        for aid, asset in working_state.assets.items()
    }
    entry_hold_days: dict[str, int] = {aid: asset.entry_hold_days for aid, asset in working_state.assets.items()}

    open_prices_map: dict[str, float] = {
        aid: float(market_bundle[aid].trade_df.iloc[i][COL_OPEN]) for aid in asset_states
    }

    executions = None
    if next_day_intents:
        executions = execute_orders(
            order_intents=next_day_intents,
            open_prices=open_prices_map,
            current_positions={aid: st.position for aid, st in asset_states.items()},
            current_cash=shared_cash_model,
            entry_prices=entry_prices,
            entry_dates=entry_dates,
            entry_hold_days=entry_hold_days,
            current_date=trade_date,
        )
        shared_cash_model = executions.updated_cash
        for aid, new_pos in executions.updated_positions.items():
            asset_states[aid].position = new_pos
        entry_prices = executions.updated_entry_prices
        entry_dates = executions.updated_entry_dates
        entry_hold_days = executions.updated_entry_hold_days

    # 전일 pending 은 이제 비운다 (당일 체결 반영됨)
    for asset in working_state.assets.values():
        asset.pending_order = None

    # 5. Step 7 (당일 종가 equity, model 축)
    asset_closes_map: dict[str, float] = {
        aid: float(market_bundle[aid].trade_df.iloc[i][COL_CLOSE]) for aid in asset_states
    }
    asset_positions = {aid: st.position for aid, st in asset_states.items()}
    model_equity = compute_portfolio_equity(shared_cash_model, asset_positions, asset_closes_map)

    # actual 축 equity (actual_shares 기준; cash 는 shared_cash_actual)
    actual_positions = {aid: asset.actual_shares for aid, asset in working_state.assets.items()}
    actual_equity = compute_portfolio_equity(working_state.shared_cash_actual, actual_positions, asset_closes_map)

    # drift_pct (단순 계산; Step 8 에서 정교화)
    if model_equity > EPSILON:
        drift_pct = abs(model_equity - actual_equity) / model_equity * 100.0
    else:
        drift_pct = 0.0

    # 6. Step 8 (시그널 → projected → rebalance → merge → 익일 pending)
    equity_vals_now: dict[str, float] = {
        aid: asset_states[aid].position * asset_closes_map[aid] for aid in asset_states
    }

    signal_intents = generate_signal_intents(
        asset_states=asset_states,
        strategies=strategies,
        asset_signal_dfs={aid: md.signal_df for aid, md in market_bundle.items()},
        equity_vals=equity_vals_now,
        slot_dict=slot_dict,
        current_equity=model_equity,
        i=i,
        current_date=trade_date,
    )

    projected = compute_projected_portfolio(asset_states, signal_intents, equity_vals_now, shared_cash_model)

    # trade_dates 리스트 생성 (월 첫 거래일 판정용)
    trade_dates_list = list(market_bundle[first_asset_id].trade_df[COL_DATE])
    total_equity_projected = projected.projected_cash + sum(projected.projected_amounts.values())
    is_month_start = is_first_trading_day_of_month(trade_dates_list, i)

    rebalance_triggered = False
    if DEFAULT_REBALANCE_POLICY.should_rebalance(projected, slot_dict, total_equity_projected, is_month_start):
        rebalance_intents = DEFAULT_REBALANCE_POLICY.build_rebalance_intents(
            projected, slot_dict, total_equity_projected, trade_date
        )
        rebalance_triggered = True
    else:
        rebalance_intents = {}

    merged_intents = merge_intents(signal_intents, rebalance_intents)

    # 7. signal_state 갱신 + 익일 pending 저장
    for asset_id, intent in merged_intents.items():
        asset_ls = working_state.assets[asset_id]
        if intent.intent_type == "EXIT_ALL":
            asset_ls.signal_state = "sell"
        elif intent.intent_type == "ENTER_TO_TARGET":
            asset_ls.signal_state = "buy"
        asset_ls.pending_order = _intent_to_pending_order(intent, trade_date)

    # 8. BufferZoneStrategy 상태 추출 → working_state 에 저장
    buffer_states = _extract_buffer_states(strategies)
    for asset_id, bzs in buffer_states.items():
        working_state.assets[asset_id].buffer_zone_state = bzs

    # 9. LiveState 의 model 축 갱신 (AssetLiveState 재구성)
    for asset_id, asset_state in asset_states.items():
        asset_ls = working_state.assets[asset_id]
        asset_ls.model_shares = int(asset_state.position)
        asset_ls.model_avg_entry_price = float(entry_prices[asset_id])
        entry_d = entry_dates[asset_id]
        asset_ls.model_entry_date = entry_d.isoformat() if entry_d else None
        asset_ls.entry_hold_days = int(entry_hold_days[asset_id])

    working_state.shared_cash_model = shared_cash_model
    working_state.last_signal_date = trade_date.isoformat()
    working_state.last_model_execution_date = trade_date.isoformat()
    if rebalance_triggered:
        working_state.last_rebalance_date = trade_date.isoformat()

    # 10. SignalDetection / ema_distances 구성
    signals_map, ema_distances = _build_signal_detections(strategies, market_bundle, signal_intents, slot_dict, i)

    # 11. 알림 본문 요약 (Step 13 notifier 에서 교체)
    body_lines = [f"실행일: {trade_date.isoformat()}", f"model equity: {model_equity:,.0f}"]
    if merged_intents:
        body_lines.append(f"익일 체결 대기: {len(merged_intents)} 건")
    notification_body = "\n".join(body_lines)

    return DailyResult(
        execution_date=trade_date.isoformat(),
        updated_state=working_state,
        updated_applied_fill_ids=working_applied_ids,
        signals=signals_map,
        order_intents=merged_intents,
        executions=executions,
        rebalance_triggered=rebalance_triggered,
        model_equity=float(model_equity),
        actual_equity=float(actual_equity),
        drift_pct=float(drift_pct),
        ema_distances=ema_distances,
        notification_body=notification_body,
        pending_fill_reminders=pending_fill_reminders,
        chart_series={},
    )


# `replace` 는 향후 dataclass 부분 갱신 유틸로 사용될 수 있도록 import 유지
_ = replace
_ = AssetLiveState
