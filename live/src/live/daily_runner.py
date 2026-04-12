"""일일 실행 메인 (순수 계산, 파일 I/O 없음).

fill 반영 → 전일 pending 체결 → 당일 equity 계산 → 시그널/리밸런싱 → 익일 pending
생성 → balance_adjust 반영 → drift 계산까지를 담당하는 순수 계산 함수이다.
파일 I/O 및 외부 네트워크 호출은 호출자(CLI 계층) 가 처리한다.

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
from datetime import date
from typing import Literal

import pandas as pd

from live.balance_adjust import apply_balance_adjusts_idempotent
from live.buffer_serializer import extract_buffer_state, get_current_bands, restore_buffer_state
from live.constants import BUY_INTENT_TYPES, SELL_INTENT_TYPES, get_live_portfolio_config
from live.drift import apply_fills_idempotent, compute_drift
from live.models import (
    ActualFill,
    BalanceAdjust,
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
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN

__all__ = ["run_daily"]


# ============================================================================
# 헬퍼 — 인덱스/전략/상태 변환
# ============================================================================


def _validate_trade_date_alignment(market_bundle: MarketBundle) -> None:
    """모든 자산의 trade_df 날짜 집합이 동일한지 검증한다.

    Raises:
        RuntimeError: 자산 간 trade_df 날짜 집합이 불일치할 때.
    """
    date_sets: dict[str, set[date]] = {}
    for asset_id, data in market_bundle.items():
        date_sets[asset_id] = set(data.trade_df[COL_DATE].tolist())

    reference_id = next(iter(date_sets))
    reference = date_sets[reference_id]
    for asset_id, dates in date_sets.items():
        if dates != reference:
            diff = reference.symmetric_difference(dates)
            raise RuntimeError(
                f"내부 불변조건 위반: trade_df 날짜 집합 불일치. " f"{reference_id} vs {asset_id}, 차이={sorted(diff)[:5]}"
            )


def _find_trade_index(trade_df: pd.DataFrame, trade_date: date) -> int:
    """trade_df 에서 주어진 날짜의 행 인덱스를 찾는다.

    Raises:
        RuntimeError: 해당 날짜가 trade_df 에 존재하지 않을 때 (내부 불변조건 위반).
    """
    matches = trade_df.index[trade_df[COL_DATE] == trade_date].tolist()
    if not matches:
        raise RuntimeError(f"내부 불변조건 위반: trade_date {trade_date} 가 trade_df 에 없음")
    return int(matches[0])


def _build_slot_dict() -> dict[str, AssetSlotConfig]:
    """live 포트폴리오의 ``asset_id → AssetSlotConfig`` 매핑을 반환."""
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

    ``AssetLiveState.signal_state`` 가 QBT ``AssetState.signal_state`` 와 동일한
    ``Literal["buy", "sell"]`` 이므로 별도 매핑 없이 그대로 전달한다.
    """
    return {
        asset_id: AssetState(position=asset.model_shares, signal_state=asset.signal_state)
        for asset_id, asset in state.assets.items()
    }


def _pending_order_to_intent(pending: PendingOrderDict) -> OrderIntent:
    """PendingOrderDict → OrderIntent (execute_orders 호출용)."""
    return OrderIntent(
        asset_id=pending["asset_id"],
        intent_type=pending["intent_type"],
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


def _ma_col_name(slot: AssetSlotConfig) -> str:
    """슬롯의 MA 컬럼명을 반환 (예: ``ma_200``)."""
    return f"ma_{slot.ma_window}"


def _build_signal_detections(
    strategies: dict[str, SignalStrategy],
    market_bundle: MarketBundle,
    signal_intents: dict[str, OrderIntent],
    slot_dict: dict[str, AssetSlotConfig],
    i: int,
) -> tuple[dict[str, SignalDetection], dict[str, float]]:
    """signal_intents 와 시장 데이터를 기반으로 SignalDetection 및 ma_distance 를 계산.

    ``SignalDetection.upper_band / lower_band`` 는 BufferZoneStrategy 일 때
    전략 내부 상태 (`_prev_upper` / `_prev_lower`) 를 그대로 노출한다.
    ``_update_bands`` 가 이미 호출되었으므로 이 값은 "당일 종가 기준" 이다.
    즉시 계산이 아닌 전략 상태 기반으로 공급하여 "전략이 실제로 판단에 사용한
    밴드" 와 공개 값이 일치하도록 한다.
    """
    signals: dict[str, SignalDetection] = {}
    ma_distances: dict[str, float] = {}

    for asset_id, slot in slot_dict.items():
        signal_df = market_bundle[asset_id].signal_df
        close = float(signal_df.iloc[i][COL_CLOSE])

        ma_col = _ma_col_name(slot)
        ma_value = float(signal_df.iloc[i][ma_col]) if ma_col in signal_df.columns else None

        # 버퍼존 밴드 (BufferZoneStrategy 일 때만, strategy 내부 상태 기반)
        upper_band: float | None = None
        lower_band: float | None = None
        strategy = strategies[asset_id]
        if isinstance(strategy, BufferZoneStrategy):
            upper_band, lower_band = get_current_bands(strategy)

        # MA 근접도 (비율 0~1, 4자리 반올림)
        if ma_value is not None and ma_value > 0:
            ma_distance_pct = round((close - ma_value) / ma_value, 4)
        else:
            ma_distance_pct = 0.0
        ma_distances[asset_id] = ma_distance_pct

        # 시그널 상태 결정
        intent = signal_intents.get(asset_id)
        state_str: Literal["buy", "sell", "none"] = "none"
        if intent is not None:
            if intent.intent_type in BUY_INTENT_TYPES:
                state_str = "buy"
            elif intent.intent_type in SELL_INTENT_TYPES:
                state_str = "sell"

        signals[asset_id] = SignalDetection(
            state=state_str,
            close=close,
            upper_band=upper_band,
            lower_band=lower_band,
            ma_value=ma_value,
            ma_distance_pct=ma_distance_pct,
        )

    return signals, ma_distances


# ============================================================================
# 메인: run_daily
# ============================================================================


def run_daily(
    trade_date: date,
    state: LiveState,
    market_bundle: MarketBundle,
    pending_fills: list[ActualFill],
    applied_fill_ids: dict[str, str],
    pending_adjusts: list[BalanceAdjust] | None = None,
    applied_balance_adjust_ids: dict[str, str] | None = None,
) -> DailyResult:
    """1 일치 live 실행을 수행한다 (순수 계산, 파일 I/O 없음).

    입력 ``state`` 는 불변으로 다루고 새 ``LiveState`` 를 ``DailyResult.updated_state``
    로 반환한다. 호출자는 결과를 저장/전송하기 전 순수 계산 결과를 검증할 수
    있으며, 회귀 검증은 이 함수의 결과를 그대로 비교한다.

    처리 순서:

    1. fills 반영 (actual 축 갱신, idempotent)
    2. 전일 pending 체결 (model 축 체결)
    3. 당일 종가 equity 계산 (model + actual)
    4. 시그널 생성 / 리밸런싱 / 익일 pending 저장
    5. **balance_adjust 반영 (actual 축 교체, idempotent)** — fills 보다 나중
    6. drift 계산 (compute_drift 를 호출해 완전 DriftReport 생성)

    Args:
        trade_date: 처리 대상 거래일.
        state: 현재 LiveState (전일 실행 결과).
        market_bundle: 자산별 signal_df / trade_df.
        pending_fills: RTDB 에서 읽어온 미처리 fill 목록.
        applied_fill_ids: 기존 적용된 fill rtdb_key → 타임스탬프 맵.
        pending_adjusts: RTDB 에서 읽어온 미처리 balance_adjust 목록.
            ``None`` 또는 빈 리스트이면 noop. fills 반영 직후 actual 축을 덮어쓴다.
        applied_balance_adjust_ids: 기존 적용된 adjust rtdb_key → 타임스탬프 맵.
            ``None`` 이면 빈 dict 로 초기화된다.

    Returns:
        DailyResult: 갱신된 LiveState + 시그널 / 체결 / 완전 DriftReport.
    """
    # 입력 정규화
    if pending_adjusts is None:
        pending_adjusts = []
    if applied_balance_adjust_ids is None:
        applied_balance_adjust_ids = {}

    # 0. 입력 복사 (원본 불변 유지)
    working_state = copy.deepcopy(state)
    working_applied_ids = dict(applied_fill_ids)
    working_applied_adjust_ids = dict(applied_balance_adjust_ids)

    # 1. RTDB fills → actual 축 반영 + idempotency
    #    drift.apply_fills_idempotent 가 새 state / 새 applied_ids 를 반환한다.
    #    빈 리스트인 경우 노옵.
    if pending_fills:
        working_state, working_applied_ids = apply_fills_idempotent(working_state, pending_fills, working_applied_ids)

    slot_dict = _build_slot_dict()

    # 2. 전략 객체 생성 및 저장된 버퍼존 상태 복원
    strategies = _create_strategies(slot_dict)
    _restore_buffer_strategies(strategies, working_state)

    # 3. 미입력 체결 리마인더
    #    pending_order 가 있는 자산 중 이번 실행에서 fill 이 들어오지 않은
    #    자산을 검출. 일부 자산만 체결된 경우에도 나머지 미체결 자산은 모두
    #    리마인더로 표시되어야 한다.
    incoming_fill_asset_ids = {fill.asset_id for fill in pending_fills}
    pending_fill_reminders: list[str] = [
        asset_id
        for asset_id, asset in working_state.assets.items()
        if asset.pending_order is not None and asset_id not in incoming_fill_asset_ids
    ]

    # 4. trade_df 날짜 집합 동일성 검증 + 인덱스 결정
    _validate_trade_date_alignment(market_bundle)
    first_asset_id = next(iter(market_bundle))
    i = _find_trade_index(market_bundle[first_asset_id].trade_df, trade_date)

    # 5. 전일 pending → 당일 시가 체결 (model 축)
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

    # 6. 당일 종가 equity (model 축)
    asset_closes_map: dict[str, float] = {
        aid: float(market_bundle[aid].trade_df.iloc[i][COL_CLOSE]) for aid in asset_states
    }
    asset_positions = {aid: st.position for aid, st in asset_states.items()}
    model_equity = compute_portfolio_equity(shared_cash_model, asset_positions, asset_closes_map)

    # 7. 시그널 → projected → rebalance → merge → 익일 pending
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

    # 8. signal_state 갱신 + 익일 pending 저장
    #    signal_state 는 "포지션 보유 여부" 원장이므로 전량 매도/신규 진입만 전환.
    #    REDUCE_TO_TARGET (일부 매도) 는 포지션이 남아 있으므로 "buy" 유지,
    #    INCREASE_TO_TARGET (추가 매수) 는 이미 "buy" 이므로 변경 불필요.
    for asset_id, intent in merged_intents.items():
        asset_ls = working_state.assets[asset_id]
        if intent.intent_type == "EXIT_ALL":
            asset_ls.signal_state = "sell"
        elif intent.intent_type == "ENTER_TO_TARGET":
            asset_ls.signal_state = "buy"
        asset_ls.pending_order = _intent_to_pending_order(intent, trade_date)

    # 9. BufferZoneStrategy 상태 추출 → working_state 에 저장
    buffer_states = _extract_buffer_states(strategies)
    for asset_id, bzs in buffer_states.items():
        working_state.assets[asset_id].buffer_zone_state = bzs

    # 10. LiveState 의 model 축 갱신 (AssetLiveState 재구성)
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

    # 11. balance_adjust 반영 (actual 축 교체) — fills 보다 나중 순서.
    #     fills 가 먼저 actual_shares 를 가감한 뒤, balance_adjust 가 최종 잔고를
    #     덮어쓴다. idempotency 는 applied_balance_adjust_ids 로 보장한다.
    if pending_adjusts:
        working_state, working_applied_adjust_ids = apply_balance_adjusts_idempotent(
            working_state, pending_adjusts, working_applied_adjust_ids
        )

    # 12. SignalDetection / ma_distances 구성
    signals_map, ma_distances = _build_signal_detections(strategies, market_bundle, signal_intents, slot_dict, i)

    # 13. drift 계산 — drift.compute_drift 가 유일한 정본.
    #     actual 축 (shares 및 cash) 은 위의 balance_adjust 반영이 완료된 상태를 쓴다.
    drift_report = compute_drift(working_state, asset_closes_map)

    # 14. 알림 본문 요약 (notifier 에서 최종 본문으로 교체됨)
    body_lines = [f"실행일: {trade_date.isoformat()}", f"model equity: {model_equity:,.0f}"]
    if merged_intents:
        body_lines.append(f"익일 체결 대기: {len(merged_intents)} 건")
    notification_body = "\n".join(body_lines)

    return DailyResult(
        execution_date=trade_date.isoformat(),
        updated_state=working_state,
        updated_applied_fill_ids=working_applied_ids,
        updated_applied_balance_adjust_ids=working_applied_adjust_ids,
        signals=signals_map,
        order_intents=merged_intents,
        executions=executions,
        rebalance_triggered=rebalance_triggered,
        model_equity=round(float(model_equity)),
        actual_equity=round(float(drift_report.actual_equity)),
        drift_pct=float(drift_report.drift_pct),
        drift_report=drift_report,
        ma_distances=ma_distances,
        notification_body=notification_body,
        pending_fill_reminders=pending_fill_reminders,
    )
