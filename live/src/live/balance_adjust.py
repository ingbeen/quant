"""자산 직접 보정 (balance adjust) 적용 로직.

앱이 RTDB ``/balance_adjust/inbox/{uuid}`` 에 기록한 잔고 보정 레코드를 읽어
:class:`LiveState` 의 ``actual_*`` 축을 덮어쓴다. 호출 경로는
:func:`live.daily_runner.run_daily` 내부에서 fills 반영 직후이다.

:class:`ActualFill` 과의 차이:

- fill: "buy/sell 이벤트" — 기존 포지션에 가감
- balance_adjust: "현재 잔고를 이 값으로 덮어쓰기" — 교체 의미

사용자가 오프라인에서 여러 거래를 했거나 세금/배당 조정이 필요할 때 fill 여러
건으로 쪼개지 않고 **최종 잔고 1 개 값** 으로 간단히 보정하기 위한 경로.

원칙:

- 입력 ``state`` / ``applied_ids`` 불변. 새 객체 반환.
- idempotency: ``rtdb_key`` 가 ``applied_ids`` 에 있으면 skip.
- 자산 + cash 동시 보정 가능 (한 레코드에 둘 다 set).
- 알 수 없는 ``asset_id`` 는 무시 (로그 없이 skip).
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

from live.models import BalanceAdjust, LiveState

__all__ = ["apply_balance_adjusts_idempotent"]

_KST = timezone(timedelta(hours=9))


def apply_balance_adjusts_idempotent(
    state: LiveState,
    adjusts: list[BalanceAdjust],
    applied_ids: dict[str, str],
) -> tuple[LiveState, dict[str, str]]:
    """balance adjust 리스트를 LiveState 에 반영한다 (idempotency 보장).

    각 adjust 의 ``rtdb_key`` 가 ``applied_ids`` 에 이미 있으면 skip 한다.
    새 adjust 는 다음 규칙으로 ``actual_*`` 축을 덮어쓴다:

    - ``asset_id`` + ``new_shares`` 가 모두 set: 해당 자산의 ``actual_shares`` 교체.
      교체 후 ``actual_avg_entry_price`` / ``actual_entry_date`` 는 유지 (평균가는
      과거 체결 기준으로 보존, 단 새 shares 가 0 이면 둘 다 리셋).
    - ``new_cash`` 가 set: ``shared_cash_actual`` 교체.
    - ``asset_id`` 와 ``new_cash`` 가 모두 None: 무효 adjust — skip (로그 없이).

    Args:
        state: 현재 LiveState.
        adjusts: 반영할 BalanceAdjust 목록.
        applied_ids: 기존에 적용된 adjust ID → ISO 타임스탬프 맵.

    Returns:
        (새 LiveState, 새 applied_ids) 튜플. 입력은 변경되지 않는다.
    """
    new_state = copy.deepcopy(state)
    new_ids = dict(applied_ids)
    now_iso = datetime.now(_KST).replace(microsecond=0).isoformat()

    for adjust in adjusts:
        if adjust.rtdb_key in new_ids:
            continue  # 이미 반영된 adjust
        _apply_single_adjust(new_state, adjust)
        new_ids[adjust.rtdb_key] = now_iso

    if adjusts:
        new_state.updated_at = now_iso
    return new_state, new_ids


def _apply_single_adjust(state: LiveState, adjust: BalanceAdjust) -> None:
    """단일 balance_adjust 를 in-place 로 state 에 반영한다.

    :func:`apply_balance_adjusts_idempotent` 내부에서 deepcopy 된 state 에만
    호출되므로 입력 불변성 원칙은 깨지지 않는다.
    """
    # 자산 shares 보정
    if adjust.asset_id is not None and adjust.new_shares is not None:
        asset = state.assets.get(adjust.asset_id)
        if asset is not None:
            asset.actual_shares = int(adjust.new_shares)
            if asset.actual_shares == 0:
                asset.actual_avg_entry_price = 0.0
                asset.actual_entry_date = None
            # 양의 shares 인 경우 평균가 / entry_date 는 기존 값 유지
            # (balance_adjust 는 "현재 잔고" 만 보정하고 원가 정보는 건드리지 않음)

    # 공유 cash 보정
    if adjust.new_cash is not None:
        state.shared_cash_actual = float(adjust.new_cash)
