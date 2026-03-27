"""포트폴리오 플래닝 — 주문 의도 모델과 시그널/투영/병합 함수

Signal → Projected → Merge 흐름의 핵심 로직을 담당한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal

import pandas as pd

from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.backtest.strategies.strategy_common import SignalStrategy
from qbt.backtest.strategy_registry import STRATEGY_REGISTRY

if TYPE_CHECKING:
    from qbt.backtest.engines.portfolio_execution import AssetState


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
class ProjectedPortfolio:
    """signal intents 반영 후 예상 포트폴리오 상태.

    signal intents를 적용한 뒤 리밸런싱 기준이 되는 "예상" 포트폴리오를 나타낸다.
    EXIT_ALL 자산의 평가액은 projected_cash로 이동하고, active_assets에서 제거된다.
    ENTER_TO_TARGET 자산은 active_assets에 추가된다 (아직 position=0이므로 amount=0).
    """

    projected_amounts: dict[str, float]  # {asset_id: 예상 평가액}
    projected_cash: float  # EXIT_ALL 매도 예상 대금 포함 현금
    active_assets: set[str]  # 리밸런싱 대상 자산 집합 (signal_state == "buy" 기준)


def create_strategy_for_slot(slot: AssetSlotConfig) -> SignalStrategy:
    """STRATEGY_REGISTRY를 경유하여 전략 객체를 생성한다.

    Args:
        slot: 자산 슬롯 설정

    Returns:
        SignalStrategy를 구현한 전략 객체

    Raises:
        ValueError: 미등록 strategy_id인 경우
    """
    spec = STRATEGY_REGISTRY.get(slot.strategy_id)
    if spec is None:
        raise ValueError(f"미등록 strategy_id: '{slot.strategy_id}'")
    return spec.create_strategy(slot)


def compute_portfolio_equity(
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


def generate_signal_intents(
    asset_states: dict[str, AssetState],
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
        asset_states: {asset_id: AssetState} (position, signal_state)
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


def compute_projected_portfolio(
    asset_states: dict[str, AssetState],
    signal_intents: dict[str, OrderIntent],
    equity_vals: dict[str, float],
    asset_closes_map: dict[str, float],
    shared_cash: float,
) -> ProjectedPortfolio:
    """signal intents 반영 후 예상 포트폴리오 상태를 계산한다.

    signal intent 실행 결과를 반영하여 리밸런싱의 기준이 되는 projected 상태를 구성한다.

    - EXIT_ALL 자산: projected_amounts[asset_id]=0, active에서 제거, cash 증가 (현재 평가액 추가)
    - ENTER_TO_TARGET 자산: active에 추가 (아직 position=0이므로 projected_amounts=0 유지)
    - 기타 자산: 현재 상태 유지

    Args:
        asset_states: {asset_id: AssetState}
        signal_intents: {asset_id: OrderIntent} — EXIT_ALL 또는 ENTER_TO_TARGET
        equity_vals: {asset_id: 현재 평가액}
        asset_closes_map: {asset_id: 현재 종가} (사용 안 함, 확장성 위해 유지)
        shared_cash: 현재 미투자 현금

    Returns:
        ProjectedPortfolio (projected_amounts, projected_cash, active_assets)
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

    return ProjectedPortfolio(
        projected_amounts=projected_amounts,
        projected_cash=projected_cash,
        active_assets=active_assets,
    )


def merge_intents(
    signal_intents: dict[str, OrderIntent],
    rebalance_intents: dict[str, OrderIntent],
) -> dict[str, OrderIntent]:
    """signal intent와 rebalance intent를 통합하여 자산당 1개를 반환한다.

    우선순위 규칙:
    1. EXIT_ALL: 항상 우선 (rebalance intent 무시)
    2. ENTER_TO_TARGET + INCREASE_TO_TARGET → ENTER_TO_TARGET (rebalance target_amount/delta_amount 사용)
    3. 단독 signal intent → 그대로 통과
    4. 단독 rebalance intent → 그대로 통과

    EXIT_ALL + REDUCE 조합은 compute_projected_portfolio가 선행되므로 발생하지 않는다.
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
