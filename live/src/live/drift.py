"""fill 자동 매칭 + idempotency + drift 계산.

책임:

- :func:`classify_fill` — 사용자 입력 fill 을 pending_order 와 매칭하여
  ``"system_fill"`` 또는 ``"personal_trade"`` 로 분류
- :func:`apply_fills_idempotent` — fill 리스트를 LiveState 의 actual 축에 반영하되,
  ``applied_fill_ids`` 로 중복 방지
- :func:`compute_drift` — model / actual equity 의 차이를 :class:`DriftReport` 로 요약.
  임계값 기준 recommendation 포함.

설계 원칙:

- 입력 ``LiveState`` 및 ``applied_ids`` 는 불변. 새 객체를 반환한다.
- 매수/매도 방향 판정은 pending_order 의 ``intent_type`` 을 기반으로 한다.
- drift 계산은 ``cash + sum(shares * close)`` 기반.
"""

from __future__ import annotations

import copy
from datetime import datetime
from typing import Literal

from live.constants import (
    BUY_INTENT_TYPES,
    DRIFT_CORRECTION_RATIO,
    DRIFT_WARNING_RATIO,
    KST_TIMEZONE,
    SELL_INTENT_TYPES,
)
from live.models import ActualFill, AssetDrift, DriftReport, LiveState

__all__ = ["classify_fill", "apply_fills_idempotent", "compute_drift"]


def classify_fill(fill: ActualFill, state: LiveState) -> Literal["system_fill", "personal_trade"]:
    """fill 을 pending_order 와 매칭하여 분류한다.

    규칙:

    - state 에 해당 asset_id 가 없으면 ``personal_trade``
    - pending_order 가 없으면 ``personal_trade``
    - pending 방향 == fill 방향 이면 ``system_fill``, 아니면 ``personal_trade``

    Args:
        fill: 사용자 입력 체결.
        state: 현재 LiveState.

    Returns:
        ``"system_fill"`` 또는 ``"personal_trade"``.
    """
    asset = state.assets.get(fill.asset_id)
    if asset is None or asset.pending_order is None:
        return "personal_trade"

    pending_is_buy = asset.pending_order["intent_type"] in BUY_INTENT_TYPES
    pending_is_sell = asset.pending_order["intent_type"] in SELL_INTENT_TYPES
    fill_is_buy = fill.direction == "buy"
    fill_is_sell = fill.direction == "sell"

    if pending_is_buy and fill_is_buy:
        return "system_fill"
    if pending_is_sell and fill_is_sell:
        return "system_fill"
    return "personal_trade"


def _apply_single_fill(state: LiveState, fill: ActualFill) -> None:
    """단일 fill 을 in-place 로 state 의 actual 축에 반영한다.

    이 함수는 :func:`apply_fills_idempotent` 내부에서 deepcopy 된 state 에 대해
    호출되므로 입력 불변성 원칙을 깨지 않는다.
    """
    asset = state.assets.get(fill.asset_id)
    if asset is None:
        # 알 수 없는 자산 — 무시 (분류는 personal_trade 이나 실제 반영 대상 아님)
        return

    proceeds = fill.actual_price * fill.actual_shares

    if fill.direction == "buy":
        prev_shares = asset.actual_shares
        prev_avg = asset.actual_avg_entry_price
        new_shares = prev_shares + fill.actual_shares
        if new_shares > 0:
            total_cost = prev_avg * prev_shares + fill.actual_price * fill.actual_shares
            asset.actual_avg_entry_price = total_cost / new_shares
        asset.actual_shares = new_shares
        asset.actual_entry_date = fill.trade_date
        state.shared_cash_actual -= proceeds

    elif fill.direction == "sell":
        new_shares = asset.actual_shares - fill.actual_shares
        if new_shares < 0:
            new_shares = 0  # 방어: 음수 금지
        asset.actual_shares = new_shares
        state.shared_cash_actual += proceeds
        if new_shares == 0:
            asset.actual_avg_entry_price = 0.0
            asset.actual_entry_date = None


def apply_fills_idempotent(
    state: LiveState,
    fills: list[ActualFill],
    applied_ids: dict[str, str],
) -> tuple[LiveState, dict[str, str]]:
    """fill 리스트를 LiveState 에 반영한다 (idempotency 보장).

    각 fill 의 ``rtdb_key`` 가 ``applied_ids`` 에 이미 있으면 skip 한다.
    새 fill 은 actual 축(`actual_shares`, `actual_avg_entry_price`,
    `actual_entry_date`, `shared_cash_actual`) 을 갱신한다.

    Args:
        state: 현재 LiveState.
        fills: 반영할 ActualFill 목록.
        applied_ids: 기존에 적용된 fill ID → ISO 타임스탬프 맵.

    Returns:
        (새 LiveState, 새 applied_ids) 튜플. 입력은 변경되지 않는다.
    """
    new_state = copy.deepcopy(state)
    new_ids = dict(applied_ids)
    now_iso = datetime.now(KST_TIMEZONE).replace(microsecond=0).isoformat()

    for fill in fills:
        if fill.rtdb_key in new_ids:
            continue  # 이미 반영된 fill
        _apply_single_fill(new_state, fill)
        new_ids[fill.rtdb_key] = now_iso

    new_state.updated_at = now_iso
    return new_state, new_ids


def compute_drift(state: LiveState, closes: dict[str, float]) -> DriftReport:
    """model / actual equity 의 차이를 :class:`DriftReport` 로 요약한다.

    ``DriftReport.recommendation`` 은 ``DRIFT_WARNING_RATIO`` /
    ``DRIFT_CORRECTION_RATIO`` 임계값에 따라 "정상" / "주의" / "보정 필요" 중
    하나로 결정된다.

    Args:
        state: 현재 LiveState.
        closes: 자산 ID → 당일 종가 맵.

    Returns:
        :class:`DriftReport` (자산별 per_asset 포함).
    """
    per_asset: dict[str, AssetDrift] = {}

    asset_model_value_sum = 0.0
    asset_actual_value_sum = 0.0

    for asset_id, asset in state.assets.items():
        close = float(closes.get(asset_id, 0.0))
        model_value = asset.model_shares * close
        actual_value = asset.actual_shares * close

        asset_model_value_sum += model_value
        asset_actual_value_sum += actual_value

        value_diff = actual_value - model_value
        if model_value > 0:
            asset_drift_pct = abs(value_diff) / model_value * 100.0
        else:
            asset_drift_pct = 0.0

        per_asset[asset_id] = AssetDrift(
            asset_id=asset_id,
            model_shares=asset.model_shares,
            actual_shares=asset.actual_shares,
            shares_diff=asset.actual_shares - asset.model_shares,
            model_value=model_value,
            actual_value=actual_value,
            value_diff=value_diff,
            drift_pct=asset_drift_pct,
        )

    model_equity = state.shared_cash_model + asset_model_value_sum
    actual_equity = state.shared_cash_actual + asset_actual_value_sum

    if model_equity > 0:
        drift_ratio = abs(actual_equity - model_equity) / model_equity
    else:
        drift_ratio = 0.0
    drift_pct = drift_ratio * 100.0

    if drift_ratio >= DRIFT_CORRECTION_RATIO:
        recommendation = "보정 필요"
    elif drift_ratio >= DRIFT_WARNING_RATIO:
        recommendation = "주의"
    else:
        recommendation = "정상"

    return DriftReport(
        model_equity=model_equity,
        actual_equity=actual_equity,
        drift_pct=drift_pct,
        per_asset=per_asset,
        recommendation=recommendation,
    )
