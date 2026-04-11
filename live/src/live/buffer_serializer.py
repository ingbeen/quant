"""BufferZoneStrategy 직렬화/역직렬화 어댑터.

QBT 본체 수정 없이 어댑터로 :class:`BufferZoneStrategy` 의 내부 상태를 추출하고
복원한다. live 환경은 매일 프로세스가 중단/재개되므로 전략의 private 상태를
``LiveState`` 에 저장/복원해야 한다.

BufferZoneStrategy 는 매일 실행되는 live 환경에서 다음 5 개의 private 속성을 유지해야
한다 (SSoT: ``src/qbt/backtest/strategies/buffer_zone.py``).

- ``_prev_upper: float | None`` — 전일 상단 밴드
- ``_prev_lower: float | None`` — 전일 하단 밴드
- ``_hold_state: HoldState | None`` — hold_days 상태머신
- ``_last_buy_buffer_pct: float`` — 최근 buy meta
- ``_last_hold_days_used: int`` — 최근 buy meta

이 어댑터는 QBT 본체의 해당 속성을 ``getattr`` / ``setattr`` 로 접근하여
:class:`BufferZoneState` 로 왕복시킨다. ``getattr``/``setattr`` 를 사용하는 이유는
pyright strict 모드의 ``reportPrivateUsage`` 경고를 우회하기 위함이며, 런타임
동작은 직접 속성 접근과 동일하다.

QBT 본체 수정 금지 원칙에 따라 어댑터는 live 측에만 존재하며, QBT 쪽은 건드리지
않는다. 만약 QBT 의 속성 이름이 변경되면 이 모듈의 테스트가 즉시 실패하여 변경을
감지할 수 있다.
"""

from __future__ import annotations

from live.models import BufferZoneState, HoldState
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy

__all__ = ["extract_buffer_state", "restore_buffer_state"]


# SSoT: BufferZoneStrategy 의 private 속성 이름 목록.
# 이 목록이 변경되면 BufferZoneState 의 필드도 함께 업데이트되어야 한다.
_PREV_UPPER_ATTR = "_prev_upper"
_PREV_LOWER_ATTR = "_prev_lower"
_HOLD_STATE_ATTR = "_hold_state"
_LAST_BUY_BUFFER_PCT_ATTR = "_last_buy_buffer_pct"
_LAST_HOLD_DAYS_USED_ATTR = "_last_hold_days_used"

# 현재 지원하는 BufferZoneState schema 버전.
_SUPPORTED_SCHEMA_VERSION = 1


def extract_buffer_state(strategy: BufferZoneStrategy) -> BufferZoneState:
    """``BufferZoneStrategy`` 의 내부 상태를 :class:`BufferZoneState` 로 추출한다.

    Args:
        strategy: 상태를 추출할 대상 전략 인스턴스.

    Returns:
        현재 내부 상태를 담은 새 :class:`BufferZoneState`. schema_version 은 항상 1.
    """
    prev_upper: float | None = getattr(strategy, _PREV_UPPER_ATTR)
    prev_lower: float | None = getattr(strategy, _PREV_LOWER_ATTR)
    hold_state: HoldState | None = getattr(strategy, _HOLD_STATE_ATTR)
    last_buy_buffer_pct: float = getattr(strategy, _LAST_BUY_BUFFER_PCT_ATTR)
    last_hold_days_used: int = getattr(strategy, _LAST_HOLD_DAYS_USED_ATTR)

    return BufferZoneState(
        prev_upper=prev_upper,
        prev_lower=prev_lower,
        hold_state=hold_state,
        last_buy_buffer_pct=last_buy_buffer_pct,
        last_hold_days_used=last_hold_days_used,
        schema_version=_SUPPORTED_SCHEMA_VERSION,
    )


def restore_buffer_state(strategy: BufferZoneStrategy, state: BufferZoneState) -> None:
    """``BufferZoneStrategy`` 인스턴스의 내부 상태를 ``state`` 로 복원한다 (in-place).

    생성자 파라미터(``_ma_col``, ``_buy_buffer_pct``, ``_sell_buffer_pct``,
    ``_hold_days``) 는 건드리지 않는다. 호출자는 복원 대상 strategy 가 원본과 동일한
    생성자 파라미터로 초기화되어 있음을 보장해야 한다.

    Args:
        strategy: 복원 대상 전략 인스턴스.
        state: 복원할 :class:`BufferZoneState`.

    Raises:
        ValueError: ``state.schema_version`` 이 지원 범위 밖일 때.
    """
    if state.schema_version != _SUPPORTED_SCHEMA_VERSION:
        raise ValueError(
            "BufferZoneState schema_version 불일치. " f"기대: {_SUPPORTED_SCHEMA_VERSION}, 실제: {state.schema_version}"
        )

    setattr(strategy, _PREV_UPPER_ATTR, state.prev_upper)
    setattr(strategy, _PREV_LOWER_ATTR, state.prev_lower)
    setattr(strategy, _HOLD_STATE_ATTR, state.hold_state)
    setattr(strategy, _LAST_BUY_BUFFER_PCT_ATTR, state.last_buy_buffer_pct)
    setattr(strategy, _LAST_HOLD_DAYS_USED_ATTR, state.last_hold_days_used)
