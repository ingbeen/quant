"""여러 매매법 — 매매법 장부, 비중이 바뀌는 매매법의 배분 변화, 매매법 사이 비중 되돌리기, 종목 단위 상계

한 실험의 매매법은 각자 몫(자본) · 현금 · 보유 주수 · 손익을 갖는다(MethodBook).
체결은 매매법마다 단독 매매처럼 비용을 매기고, 같은 날 같은 종목의 반대 매매가 계좌에서 상계돼
아끼는 비용은 계좌의 「상계 절감」으로 따로 둔다 — Σ 매매법 손익 + 상계 절감 = 계좌 손익.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd

from qbt.backtest.allocator_registry import WeightAllocator
from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.backtest.engines.portfolio_planning import OrderIntent, ProjectedPortfolio
from qbt.backtest.portfolio_types import (
    AssetSlotConfig,
    AssetState,
    PortfolioResult,
    list_position_keys,
    resolve_methods,
)
from qbt.backtest.strategies.strategy_common import SignalStrategy
from qbt.common_constants import COL_DATE, EPSILON

# ============================================================================
# 매매법 장부
# ============================================================================


@dataclass
class MethodBook:
    """매매법 하나의 장부 (엔진 루프가 날마다 갱신한다).

    자산별 dict 의 키는 결과 파일의 자산 키(position_key)다. 매매법이 하나면 자산 id 와 같다.

    Attributes:
        method_id: 매매법 식별자
        target_share: 계좌 대비 목표 몫
        initial_capital: 처음 받은 자본 (총 자본 × 목표 몫)
        asset_of_key: {키: 자산 id} — 상계는 자산 id 단위로 묶는다
        cash: 현금
        asset_states: {키: 보유 주수 · 신호 상태}
        entry_prices / entry_dates / entry_hold_days: 진입 정보 (execute_orders 와 같은 형식)
        realized_pnl: {키: 누적 실현손익}
        targets: {키: 매매법 자본 대비 목표 비중} — 슬롯 매매법은 고정, 비중변동 매매법은 배분 규칙이 바꾼다
        slots: {키: 슬롯 설정} — 슬롯 매매법만
        strategies: {키: 신호 전략} — 슬롯 매매법만
        allocator: 배분 규칙 — 비중변동 매매법만
        allocator_data: {자산 id · series_id: 시세} — 배분 규칙 입력
        cost: 단독 매매로 매긴 비용 누적 (C안 장부 비용)
        transfers: 매매법 사이 이전 누적 (받으면 +, 내주면 −)
        next_day_intents: 다음 거래일 시가에 체결할 의도
        next_day_reason: 그 의도의 리밸런싱 사유 ("monthly" | "methods" | "")
        next_day_transfer: 다음 거래일에 받을(+) · 내줄(−) 이전 계획액
    """

    method_id: str
    target_share: float
    initial_capital: float
    asset_of_key: dict[str, str]
    cash: float
    asset_states: dict[str, AssetState]
    entry_prices: dict[str, float]
    entry_dates: dict[str, date | None]
    entry_hold_days: dict[str, int]
    realized_pnl: dict[str, float]
    targets: dict[str, float]
    slots: dict[str, AssetSlotConfig] = field(default_factory=dict)
    strategies: dict[str, SignalStrategy] = field(default_factory=dict)
    allocator: WeightAllocator | None = None
    allocator_data: dict[str, pd.DataFrame] = field(default_factory=dict)
    cost: float = 0.0
    transfers: float = 0.0
    next_day_intents: dict[str, OrderIntent] = field(default_factory=dict)
    next_day_reason: str = ""
    next_day_transfer: float = 0.0

    def positions(self) -> dict[str, int]:
        """{키: 보유 주수}."""
        return {key: state.position for key, state in self.asset_states.items()}


# ============================================================================
# 종목 단위 상계
# ============================================================================


@dataclass(frozen=True)
class NettingResult:
    """한 자산의 하루 상계 결과.

    Attributes:
        gross_shares: 매매법 주문 주수 합 Σ|Δ|
        net_shares: 계좌가 실제로 체결하는 순량 ΣΔ (부호: + 매수, − 매도)
        savings: 장부 비용 합 − 계좌 실제 비용
    """

    gross_shares: int
    net_shares: int
    savings: float


def compute_netting(share_deltas: Sequence[int], open_price: float) -> NettingResult:
    """같은 날 같은 자산의 매매법별 주수 변화로 상계를 계산한다.

    매수는 시가 × (1 + SLIPPAGE_RATE), 매도는 시가 × (1 − SLIPPAGE_RATE) 로 체결되므로,
    상계된 주수(사는 쪽과 파는 쪽이 서로 맞춘 몫)는 양쪽에서 비용을 한 번씩 덜 낸다:
    절감 = (Σ|Δ| − |ΣΔ|) × 시가 × SLIPPAGE_RATE.

    Args:
        share_deltas: 매매법별 주수 변화 (+ 매수, − 매도)
        open_price: 그날 시가

    Returns:
        NettingResult
    """
    gross = sum(abs(delta) for delta in share_deltas)
    net = sum(share_deltas)
    savings = (gross - abs(net)) * open_price * SLIPPAGE_RATE
    return NettingResult(gross_shares=gross, net_shares=net, savings=savings)


# ============================================================================
# 매매법 사이 비중 되돌리기
# ============================================================================


def plan_method_transfers(
    method_equities: Mapping[str, float],
    target_shares: Mapping[str, float],
    threshold_rate: float,
) -> dict[str, float] | None:
    """매매법 몫이 목표에서 벗어났으면 목표 몫으로 되돌리는 이전액을 계산한다.

    어느 매매법이든 |몫 ÷ 목표 − 1| 이 임계값을 넘으면 전 매매법을 되돌린다(매매법 안 리밸런싱과 같은 규칙).
    몫은 매매법 자본 합 기준이다 — 상계 절감은 매매법에 나누지 않는다.

    Args:
        method_equities: {method_id: 매매법 자본}
        target_shares: {method_id: 목표 몫}
        threshold_rate: 상대 편차 임계값 (0.10 = 10%)

    Returns:
        {method_id: 이전액 (+ 받음, − 내줌)}, 합 0. 되돌릴 필요가 없으면 None
    """
    total = sum(method_equities.values())
    if total < EPSILON:
        raise RuntimeError(f"내부 불변조건 위반: 매매법 자본 합이 0 이하 (method_equities={dict(method_equities)})")

    triggered = any(
        abs((equity / total) / target_shares[method_id] - 1.0) > threshold_rate
        for method_id, equity in method_equities.items()
    )
    if not triggered:
        return None
    return {method_id: total * target_shares[method_id] - equity for method_id, equity in method_equities.items()}


def cap_transfers(planned: Mapping[str, float], cash_after_sells: Mapping[str, float]) -> dict[str, float]:
    """체결일의 실제 이전액을 정한다.

    내주는 쪽은 매도 뒤 현금 안에서만 내준다. 밤사이 가격이 내려 매도 대금이 계획보다 적으면
    받는 쪽이 계획 비율대로 덜 받는다 — 어느 장부도 현금이 음수가 되지 않는다.

    Args:
        planned: {method_id: 계획 이전액 (+ 받음, − 내줌)}
        cash_after_sells: {method_id: 매도 체결 뒤 현금}

    Returns:
        {method_id: 실제 이전액}
    """
    given = {
        method_id: min(-amount, max(cash_after_sells[method_id], 0.0))
        for method_id, amount in planned.items()
        if amount < 0
    }
    total_given = sum(given.values())
    total_requested = sum(amount for amount in planned.values() if amount > 0)

    actual: dict[str, float] = {}
    for method_id, amount in planned.items():
        if amount < 0:
            actual[method_id] = -given[method_id]
        elif amount > 0:
            actual[method_id] = total_given * amount / total_requested
        else:
            actual[method_id] = 0.0
    return actual


# ============================================================================
# 비중이 바뀌는 매매법의 배분 변화
# ============================================================================


def _validate_allocation(new_targets: Mapping[str, float], assets: Sequence[str]) -> dict[str, float]:
    """배분 규칙이 낸 목표 비중을 검증하고 매매법 전 자산으로 채운다(없는 자산 0)."""
    unknown = sorted(set(new_targets) - set(assets))
    if unknown:
        raise ValueError(f"배분 규칙이 매매법에 없는 자산의 비중을 냈습니다: {unknown} (매매법 자산: {list(assets)})")
    non_finite = {asset_id: w for asset_id, w in new_targets.items() if not math.isfinite(w)}
    if non_finite:
        raise ValueError(f"배분 규칙이 숫자가 아닌 비중(NaN · 무한대)을 냈습니다: {non_finite}. 규칙의 계산 입력을 확인하세요")
    negative = {asset_id: w for asset_id, w in new_targets.items() if w < 0}
    if negative:
        raise ValueError(f"배분 규칙이 음수 비중을 냈습니다: {negative}. 비중은 0 이상이어야 합니다")
    total = sum(new_targets.values())
    if total > 1.0 + EPSILON:
        raise ValueError(f"배분 규칙이 낸 비중 합이 1 을 넘습니다: {total:.6f}. 합은 1 이하여야 합니다")
    return {asset_id: float(new_targets.get(asset_id, 0.0)) for asset_id in assets}


def generate_allocation_intents(
    old_targets: Mapping[str, float],
    new_targets: Mapping[str, float] | None,
    positions: Mapping[str, int],
    equity_vals: Mapping[str, float],
    method_equity: float,
) -> dict[str, OrderIntent]:
    """배분 규칙의 목표 변화를 주문 의도로 바꾼다.

    - 새 목표 0 · 보유 중 → EXIT_ALL (전량 청산)
    - 새 목표 > 0 · 보유 0 → ENTER_TO_TARGET (목표 = 매매법 자본 × 비중)
    - 새 목표 > 0 · 보유 중 · 목표가 바뀜 → REDUCE_TO_TARGET / INCREASE_TO_TARGET (그 금액으로 증감)
    - 그 외 → 의도 없음

    Args:
        old_targets: {자산: 직전 목표 비중} — 매매법 자산 전부를 키로 갖는다
        new_targets: 배분 규칙이 낸 목표 비중. None 이면 목표 변경 없음
        positions: {자산: 보유 주수}
        equity_vals: {자산: 평가액}
        method_equity: 매매법 자본

    Returns:
        {자산: OrderIntent}

    Raises:
        ValueError: 모르는 자산 · 음수 비중 · 합 1 초과
    """
    if new_targets is None:
        return {}
    targets = _validate_allocation(new_targets, list(old_targets))

    intents: dict[str, OrderIntent] = {}
    for asset_id, new_weight in targets.items():
        position = positions[asset_id]
        current_amount = equity_vals[asset_id]
        if new_weight == 0:
            if position > 0:
                intents[asset_id] = OrderIntent(
                    asset_id=asset_id,
                    intent_type="EXIT_ALL",
                    current_amount=current_amount,
                    target_amount=0.0,
                    delta_amount=-current_amount,
                    target_weight=0.0,
                    reason="allocation exit",
                )
        elif position == 0:
            target_amount = method_equity * new_weight
            intents[asset_id] = OrderIntent(
                asset_id=asset_id,
                intent_type="ENTER_TO_TARGET",
                current_amount=0.0,
                target_amount=target_amount,
                delta_amount=target_amount,
                target_weight=new_weight,
                reason="allocation enter",
            )
        elif new_weight != old_targets[asset_id]:
            target_amount = method_equity * new_weight
            delta = target_amount - current_amount
            if delta != 0:
                intents[asset_id] = OrderIntent(
                    asset_id=asset_id,
                    intent_type="REDUCE_TO_TARGET" if delta < 0 else "INCREASE_TO_TARGET",
                    current_amount=current_amount,
                    target_amount=target_amount,
                    delta_amount=delta,
                    target_weight=new_weight,
                    reason="allocation change",
                )
    return intents


def compute_allocation_projection(
    targets: Mapping[str, float],
    allocation_intents: Mapping[str, OrderIntent],
    equity_vals: Mapping[str, float],
    cash: float,
) -> ProjectedPortfolio:
    """배분 변화 의도를 반영한 예상 상태를 만든다 (슬롯 매매법의 compute_projected_portfolio 에 해당).

    - 청산 자산: 평가액 → 현금, 예상 금액 0
    - active: 목표 비중 > 0 인 자산
    - 판정 제외: 진입 · 조정 의도가 난 자산 (그날 이미 목표로 매매한다)

    Args:
        targets: {자산: 변화 반영 뒤 목표 비중} — 매매법 자산 전부
        allocation_intents: generate_allocation_intents 결과
        equity_vals: {자산: 평가액}
        cash: 매매법 현금

    Returns:
        ProjectedPortfolio
    """
    projected_amounts = dict(equity_vals)
    projected_cash = cash
    for asset_id, intent in allocation_intents.items():
        if intent.intent_type == "EXIT_ALL":
            projected_cash += equity_vals[asset_id]
            projected_amounts[asset_id] = 0.0

    return ProjectedPortfolio(
        projected_amounts=projected_amounts,
        projected_cash=projected_cash,
        active_assets={asset_id for asset_id, weight in targets.items() if weight > 0},
        check_excluded_assets={
            asset_id for asset_id, intent in allocation_intents.items() if intent.intent_type != "EXIT_ALL"
        },
    )


# ============================================================================
# 결과 요약 (매매법이 여럿인 실험)
# ============================================================================


def summarize_methods(result: PortfolioResult) -> dict[str, Any]:
    """매매법별 손익 · 상계 · 계좌 종목 합계 요약을 만든다 (반올림하지 않은 값, 저장은 러너가 한다).

    Returns:
        {"per_method": [...], "netting": {...}, "account_holdings": [...], "pnl_check": {...}}
        pnl_check 는 「Σ 매매법 손익 + 상계 절감 = 계좌 손익」의 최종일 대조다
    """
    infos = list_position_keys(result.config)
    methods = resolve_methods(result.config)
    ledger = result.ledger_df
    last = result.equity_df.iloc[-1]
    last_ledger = ledger[ledger[COL_DATE] == last[COL_DATE]].set_index("method_id")

    per_method: list[dict[str, Any]] = []
    for method in methods:
        keys = [info.key for info in infos if info.method_id == method.method_id]
        row = last_ledger.loc[method.method_id]
        of_method = ledger["method_id"] == method.method_id
        per_method.append(
            {
                "method_id": method.method_id,
                "display_name": method.display_name,
                "target_share": method.target_weight,
                "final_share": float(row["share"]),
                "final_equity": float(row["equity"]),
                "pnl": float(row["pnl"]),
                "realized_pnl": sum(float(last[f"{key}_realized_pnl"]) for key in keys),
                "unrealized_pnl": sum(float(last[f"{key}_unrealized_pnl"]) for key in keys),
                "cost": float(row["cost"]),
                "transfers": float(row["transfers"]),
                "rebalanced_days": int((of_method & (ledger["rebalanced"] == True)).sum()),  # noqa: E712
                "method_rebalance_days": int((of_method & (ledger["rebalance_reason"] == "methods")).sum()),
                "assets": [{"asset_id": key, "pnl": float(last[f"{key}_contribution"])} for key in keys],
            }
        )

    netting_df = result.netting_df
    netting = {
        "savings_total": float(netting_df["savings"].sum()),
        "netting_rows": len(netting_df),
        "netting_days": int(netting_df[COL_DATE].nunique()),
        # 상계된 주수 = 사는 쪽과 파는 쪽이 서로 맞춘 주수 = (Σ|Δ| − |ΣΔ|) ÷ 2 (양쪽에서 한 번씩 세지 않는다)
        "netted_shares": int((netting_df["gross_shares"] - netting_df["net_shares"].abs()).sum()) // 2,
    }

    holdings: dict[str, dict[str, float]] = {}
    for info in infos:
        entry = holdings.setdefault(info.asset_id, {"shares": 0.0, "value": 0.0, "weight": 0.0})
        entry["shares"] += float(last[f"{info.key}_shares"])
        entry["value"] += float(last[f"{info.key}_value"])
        entry["weight"] += float(last[f"{info.key}_weight"])
    account_holdings = [
        {"asset_id": asset_id, "shares": int(v["shares"]), "value": v["value"], "weight": v["weight"]}
        for asset_id, v in holdings.items()
    ]

    savings = float(last["netting_savings"]) if "netting_savings" in result.equity_df.columns else 0.0
    account_pnl = float(last["equity"]) - result.config.total_capital
    methods_pnl = sum(item["pnl"] for item in per_method)
    pnl_check = {
        "account_pnl": account_pnl,
        "methods_pnl_sum": methods_pnl,
        "netting_savings": savings,
        "difference": account_pnl - (methods_pnl + savings),
    }

    return {"per_method": per_method, "netting": netting, "account_holdings": account_holdings, "pnl_check": pnl_check}


def account_target_weights(result: PortfolioResult) -> dict[str, float]:
    """자산 키별 계좌 대비 목표 비중 = 매매법 몫 × 매매법 안 비중.

    비중이 바뀌는 매매법 자산은 최종일 목표 비중을 쓴다. 매매법이 하나면 슬롯 비중 그대로다(1.0 × 비중).
    """
    weights: dict[str, float] = {}
    for info in list_position_keys(result.config):
        if info.slot is not None:
            weights[info.key] = info.method_share * info.slot.target_weight
            continue
        if result.state_log_df.empty:
            raise RuntimeError(f"내부 불변조건 위반: state_log_df 가 비어 비중변동 매매법 자산의 목표 비중을 알 수 없음 (key={info.key})")
        final_target = float(result.state_log_df.iloc[-1][f"{info.key}_target_weight"])
        weights[info.key] = info.method_share * final_target
    return weights
