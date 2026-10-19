"""포트폴리오 플래닝 — 주문 의도 모델과 시그널/투영/병합 함수

Signal → Projected → Merge 흐름의 핵심 로직을 담당한다.
"""

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from qbt.backtest.portfolio_types import AssetSlotConfig, AssetState
from qbt.backtest.strategies.strategy_common import SignalStrategy


@dataclass
class OrderIntent:
    """자산별 주문 의도를 나타내는 모델.

    signal 또는 rebalance 로직이 생성한 주문 의도를 통일된 형태로 표현한다.
    merge_intents에서 signal/rebalance intent를 통합하여 자산당 1개를 보장한다.

    intent_type 종류:
    - EXIT_ALL: 보유 전량 청산 (signal sell)
    - ENTER_TO_TARGET: 신규 진입 — 목표 금액만큼 산다 (signal buy)
    - REDUCE_TO_TARGET: 목표 금액을 넘는 만큼 판다 (rebalance)
    - INCREASE_TO_TARGET: 목표 금액에 모자란 만큼 산다 (rebalance)
    """

    intent_type: Literal["EXIT_ALL", "ENTER_TO_TARGET", "REDUCE_TO_TARGET", "INCREASE_TO_TARGET"]
    # 증감 금액 (음수 = 매도, 양수 = 매수) — 목표 금액 − 현재 평가액이고, 리밸런싱 매수는 현금이 모자라면 비례로 줄인 금액이다.
    # EXIT_ALL 은 전량을 팔아 체결이 이 값을 보지 않는다
    delta_amount: float
    reason: str  # 생성 이유 (상태 로그의 pending_reason)
    hold_days_used: int = 0  # 진입 시 hold_days 파라미터 (TradeRecord에 기록)


@dataclass
class ProjectedPortfolio:
    """signal intents 반영 후 예상 포트폴리오 상태.

    signal intents를 적용한 뒤 리밸런싱 기준이 되는 "예상" 포트폴리오를 나타낸다.
    EXIT_ALL 자산의 평가액은 projected_cash로 이동하고, active_assets에서 제거된다.
    ENTER_TO_TARGET 자산은 active_assets와 check_excluded_assets에 추가된다 (아직 position=0이므로 amount=0).
    """

    projected_amounts: dict[str, float]  # {asset_id: 예상 평가액}
    projected_cash: float  # EXIT_ALL 매도 예상 대금 포함 현금
    active_assets: set[str]  # 리밸런싱 대상 자산 집합 (슬롯: 신호 상태 buy, 배분 규칙: 목표 비중 > 0)
    # 그날 신호 · 배분 규칙으로 들어오거나 목표 비중이 바뀐 자산. 리밸런싱 편차 판정에서 뺀다 —
    # 진입 자산은 보유가 0 이라 편차가 100% 로 계산되고, 조정 자산은 그날 이미 목표로 매매한다
    # (결정 근거: docs/research/전략_검증_보고서.md 부록 L.5)
    check_excluded_assets: set[str] = field(default_factory=set)


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
    total_value = sum(asset_positions[aid] * asset_closes[aid] for aid in asset_positions)
    return shared_cash + total_value


def generate_signal_intents(
    asset_states: dict[str, AssetState],
    strategies: dict[str, SignalStrategy],
    asset_signal_dfs: dict[str, pd.DataFrame],
    equity_vals: dict[str, float],
    slot_dict: dict[str, AssetSlotConfig],
    current_equity: float,
    i: int,
) -> dict[str, OrderIntent]:
    """전략 기반으로 시그널 intent를 생성한다.

    1. position=0 + buy signal → ENTER_TO_TARGET (증감액 = current_equity × target_weight)
    2. position>0 + sell signal → EXIT_ALL (증감액 = −평가액)
    3. 그 외(HOLD) → intent 생성 안 함

    Args:
        asset_states: {asset_id: AssetState} (position, signal_state)
        strategies: {asset_id: SignalStrategy}
        asset_signal_dfs: {asset_id: signal DataFrame}
        equity_vals: {asset_id: 현재 평가액}
        slot_dict: {asset_id: AssetSlotConfig}
        current_equity: 총 에쿼티
        i: 현재 행 인덱스

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
            buy_now = strategy.check_buy(signal_df, i)
            if buy_now:
                meta = strategy.get_buy_meta()
                intents[asset_id] = OrderIntent(
                    intent_type="ENTER_TO_TARGET",
                    delta_amount=current_equity * slot.target_weight,
                    reason="signal buy",
                    hold_days_used=int(meta.get("hold_days_used", 0)),
                )
        elif state.position > 0:
            # 매도 시그널 판정 (내부 prev 상태 갱신 포함)
            sell_now = strategy.check_sell(signal_df, i)
            if sell_now:
                # equity_vals는 호출부 계약상 asset_states 전 자산에 대해 사전 채워진다 — 누락은 호출부 버그다
                if asset_id not in equity_vals:
                    raise RuntimeError(
                        f"내부 불변조건 위반: equity_vals에 asset_id 누락 "
                        f"(asset_id={asset_id}, available_keys={sorted(equity_vals.keys())})"
                    )
                intents[asset_id] = OrderIntent(
                    intent_type="EXIT_ALL",
                    delta_amount=-equity_vals[asset_id],
                    reason="signal sell",
                )

    return intents


def compute_projected_portfolio(
    asset_states: dict[str, AssetState],
    signal_intents: dict[str, OrderIntent],
    equity_vals: dict[str, float],
    shared_cash: float,
) -> ProjectedPortfolio:
    """signal intents 반영 후 예상 포트폴리오 상태를 계산한다.

    signal intent 실행 결과를 반영하여 리밸런싱의 기준이 되는 projected 상태를 구성한다.

    - EXIT_ALL 자산: projected_amounts[asset_id]=0, active에서 제거, cash 증가 (현재 평가액 추가)
    - ENTER_TO_TARGET 자산: active와 check_excluded에 추가 (아직 position=0이므로 projected_amounts=0 유지)
    - 기타 자산: 현재 상태 유지

    Args:
        asset_states: {asset_id: AssetState}
        signal_intents: {asset_id: OrderIntent} — EXIT_ALL 또는 ENTER_TO_TARGET
        equity_vals: {asset_id: 현재 평가액}
        shared_cash: 현재 미투자 현금

    Returns:
        ProjectedPortfolio (projected_amounts, projected_cash, active_assets, check_excluded_assets)
    """
    # 현재 active_assets: signal_state == "buy"인 자산
    active_assets: set[str] = {aid for aid, st in asset_states.items() if st.signal_state == "buy"}

    # equity_vals는 호출부 계약상 asset_states 전 자산에 대해 사전 채워진다 — 누락은 호출부 버그다
    missing_vals = [aid for aid in asset_states if aid not in equity_vals]
    if missing_vals:
        raise RuntimeError(
            f"내부 불변조건 위반: equity_vals에 asset 누락 "
            f"(missing={missing_vals}, available_keys={sorted(equity_vals.keys())})"
        )

    # projected_amounts: 현재 평가액에서 시작
    projected_amounts: dict[str, float] = {aid: equity_vals[aid] for aid in asset_states}
    projected_cash = shared_cash
    check_excluded_assets: set[str] = set()

    for asset_id, intent in signal_intents.items():
        if intent.intent_type == "EXIT_ALL":
            # 전량 청산: 평가액 → cash로 이동, active에서 제거
            projected_cash += equity_vals[asset_id]
            projected_amounts[asset_id] = 0.0
            active_assets.discard(asset_id)

        elif intent.intent_type == "ENTER_TO_TARGET":
            # 신규 진입 예정: active에 추가 (아직 position=0)
            active_assets.add(asset_id)
            check_excluded_assets.add(asset_id)
            # projected_amounts[asset_id]는 0.0 유지 (position 없음)

    return ProjectedPortfolio(
        projected_amounts=projected_amounts,
        projected_cash=projected_cash,
        active_assets=active_assets,
        check_excluded_assets=check_excluded_assets,
    )


def merge_intents(
    signal_intents: dict[str, OrderIntent],
    rebalance_intents: dict[str, OrderIntent],
) -> dict[str, OrderIntent]:
    """signal intent와 rebalance intent를 통합하여 자산당 1개를 반환한다.

    우선순위 규칙:
    1. EXIT_ALL: 항상 우선 (rebalance intent 무시)
    2. ENTER_TO_TARGET + INCREASE_TO_TARGET → ENTER_TO_TARGET (rebalance 의 delta_amount 사용)
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
    # 집합 대신 삽입 순서(신호 → 리밸런싱)로 돈다. 이 순서가 같은 날 체결 순서가 되는데, 집합은
    # 문자열 해시 무작위화로 실행마다 순서가 바뀌어 같은 코드에서도 결과 파일이 달라진다
    all_assets = list(dict.fromkeys([*signal_intents, *rebalance_intents]))

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
            # 신규 진입 + 리밸런싱 매수 → ENTER_TO_TARGET (rebalance 금액 사용, signal hold_days_used 보존)
            merged[asset_id] = OrderIntent(
                intent_type="ENTER_TO_TARGET",
                delta_amount=reb.delta_amount,
                reason="signal_buy+rebalance",
                hold_days_used=sig.hold_days_used,
            )
        elif sig is not None:
            merged[asset_id] = sig
        elif reb is not None:
            merged[asset_id] = reb

    return merged
