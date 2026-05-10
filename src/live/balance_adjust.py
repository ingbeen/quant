"""자산 직접 보정 (balance adjust) 적용 로직.

앱이 RTDB ``/balance_adjust/inbox/{uuid}`` 에 기록한 잔고 보정 레코드를 읽어
:class:`LiveState` 의 ``actual_*`` 축을 덮어쓴다. 호출 경로는
:func:`live.daily_runner.run_daily` 내부에서 fills 반영 직후이다.

:class:`ActualFill` 과의 차이:

- fill: "buy/sell 이벤트" — 기존 포지션에 가감
- balance_adjust: "현재 잔고를 이 값으로 덮어쓰기" — 교체 의미

사용자가 오프라인에서 여러 거래를 했거나 세금/배당 조정, 평균가 / 진입일 재입력이
필요할 때 fill 여러 건으로 쪼개지 않고 **최종 잔고 1 개 값** 으로 간단히
보정하기 위한 경로.

**actual 축 전용**: 모든 보정은 ``actual_*`` / ``shared_cash_actual`` 만 건드리며
``model_*`` / ``shared_cash_model`` 은 절대 변경하지 않는다 (model/actual 분리
원칙).

원칙:

- 입력 ``state`` / ``applied_ids`` 불변. 새 객체 반환.
- idempotency: ``rtdb_key`` 가 ``applied_ids`` 에 있으면 skip.
- 자산 + cash 동시 보정 가능 (한 레코드에 둘 다 set).
- 알 수 없는 ``asset_id`` 가 전달되면 즉시 ``ValueError`` 로 중단한다 (fail-fast).
- ``new_avg_price`` / ``new_entry_date`` 는 ``asset_id`` 필수 + ``actual_shares > 0``
  조건에서만 허용한다 (silent skip 금지 원칙).
"""

from __future__ import annotations

import copy
from datetime import datetime

from live.constants import EMPTY_POSITION_AVG_PRICE, KST_TIMEZONE
from live.models import BalanceAdjust, LiveState

__all__ = ["apply_balance_adjusts_idempotent"]


def apply_balance_adjusts_idempotent(
    state: LiveState,
    adjusts: list[BalanceAdjust],
    applied_ids: dict[str, str],
) -> tuple[LiveState, dict[str, str]]:
    """balance adjust 리스트를 LiveState 에 반영한다 (idempotency 보장).

    각 adjust 의 ``rtdb_key`` 가 ``applied_ids`` 에 이미 있으면 skip 한다.
    새 adjust 는 다음 규칙으로 ``actual_*`` 축을 덮어쓴다 (우선순위 순):

    1. ``asset_id`` + ``new_shares`` 지정:
       - ``new_shares == 0`` 이면 ``actual_shares=0`` + ``actual_avg_entry_price=0.0``
         + ``actual_entry_date=None`` 리셋 (``new_avg_price`` / ``new_entry_date``
         가 동시 지정되어도 무시).
       - ``new_shares > 0`` 이면 ``actual_shares`` 교체. ``new_avg_price`` /
         ``new_entry_date`` 가 같이 지정되었으면 해당 필드도 갱신.
    2. ``asset_id`` + ``new_avg_price`` / ``new_entry_date`` 만 지정 (``new_shares``
       는 None): 현재 ``actual_shares > 0`` 일 때만 해당 필드 갱신. ``actual_shares
       == 0`` 이면 ``ValueError``.
    3. ``new_cash`` 지정: ``shared_cash_actual`` 교체 (기존 동작).

    model 축 (``model_*`` / ``shared_cash_model``) 은 절대 건드리지 않는다.

    Args:
        state: 현재 LiveState.
        adjusts: 반영할 BalanceAdjust 목록.
        applied_ids: 기존에 적용된 adjust ID → ISO 타임스탬프 맵.

    Returns:
        (새 LiveState, 새 applied_ids) 튜플. 입력은 변경되지 않는다.
    """
    new_state = copy.deepcopy(state)
    new_ids = dict(applied_ids)
    now_iso = datetime.now(KST_TIMEZONE).replace(microsecond=0).isoformat()

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

    Raises:
        ValueError: ``adjust.asset_id`` 가 state 에 존재하지 않을 때 (fail-fast),
            또는 ``new_avg_price`` / ``new_entry_date`` 가 지정되었는데 ``asset_id``
            가 None 일 때, 또는 ``actual_shares == 0`` 인 자산에 ``new_avg_price``
            / ``new_entry_date`` 를 단독 지정할 때.
    """
    # 평균가 / 진입일 보정은 asset_id 필수
    if (adjust.new_avg_price is not None or adjust.new_entry_date is not None) and adjust.asset_id is None:
        raise ValueError(
            f"new_avg_price / new_entry_date 지정 시 asset_id 필수 — balance_adjust 반영 불가. " f"rtdb_key={adjust.rtdb_key!r}"
        )

    # 자산 축 보정 (shares / 평균가 / 진입일)
    if adjust.asset_id is not None and (
        adjust.new_shares is not None or adjust.new_avg_price is not None or adjust.new_entry_date is not None
    ):
        asset = state.assets.get(adjust.asset_id)
        if asset is None:
            raise ValueError(
                f"알 수 없는 asset_id={adjust.asset_id!r} — balance_adjust 반영 불가. " f"rtdb_key={adjust.rtdb_key!r}"
            )

        if adjust.new_shares is not None:
            # 1. new_shares 지정 경로
            asset.actual_shares = int(adjust.new_shares)
            if asset.actual_shares == 0:
                # new_shares=0 리셋 규칙이 평균가 / 진입일 보정보다 우선
                asset.actual_avg_entry_price = EMPTY_POSITION_AVG_PRICE
                asset.actual_entry_date = None
            else:
                # new_shares > 0: 동시 지정된 평균가 / 진입일을 적용 (없으면 기존 값 유지)
                if adjust.new_avg_price is not None:
                    asset.actual_avg_entry_price = float(adjust.new_avg_price)
                if adjust.new_entry_date is not None:
                    asset.actual_entry_date = str(adjust.new_entry_date)
        else:
            # 2. new_shares 미지정 경로 (평균가 / 진입일 단독 보정)
            if asset.actual_shares == 0:
                raise ValueError(
                    f"보유 주수가 0 인 자산의 평균가 / 진입일을 설정할 수 없음 "
                    f"(asset_id={adjust.asset_id!r}, rtdb_key={adjust.rtdb_key!r})"
                )
            if adjust.new_avg_price is not None:
                asset.actual_avg_entry_price = float(adjust.new_avg_price)
            if adjust.new_entry_date is not None:
                asset.actual_entry_date = str(adjust.new_entry_date)

    # 공유 cash 보정 (QBT 본체와 동일하게 소수점 유지)
    if adjust.new_cash is not None:
        state.shared_cash_actual = float(adjust.new_cash)
