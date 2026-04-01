"""전략 레지스트리 모듈

전략 확장 가능 구조를 제공한다.
StrategySpec 데이터클래스와 STRATEGY_REGISTRY 딕셔너리를 통해
포트폴리오 엔진이 strategy_id 문자열로 전략 동작을 조회한다.

등록된 전략:
- "buffer_zone": 버퍼존 이동평균 전략
- "buy_and_hold": 즉시 매수 후 보유 전략
"""

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldStrategy
from qbt.backtest.strategies.strategy_common import SignalStrategy

# ============================================================================
# StrategySpec 데이터클래스
# ============================================================================


@dataclass(frozen=True)
class StrategySpec:
    """전략 명세 데이터클래스.

    포트폴리오 엔진이 strategy_id로 조회하여 전략 동작을 결정한다.

    Attributes:
        strategy_id: 전략 식별자 (STRATEGY_REGISTRY의 키)
        create_strategy: AssetSlotConfig를 받아 SignalStrategy 객체를 반환하는 팩토리
        prepare_signal_df: signal DataFrame에 전략별 전처리를 적용하는 함수
            - buffer_zone: MA 컬럼 추가
            - buy_and_hold: 원본 그대로 반환
        get_warmup_periods: MA 워밍업 기간을 반환하는 함수
            - buffer_zone: slot.ma_window 반환
            - buy_and_hold: 0 반환
    """

    strategy_id: str
    create_strategy: Callable[[AssetSlotConfig], SignalStrategy]
    prepare_signal_df: Callable[[pd.DataFrame, AssetSlotConfig], pd.DataFrame]
    get_warmup_periods: Callable[[AssetSlotConfig], int]


# ============================================================================
# buffer_zone 전략 전용 함수
# ============================================================================


def _create_buffer_zone_strategy(slot: AssetSlotConfig) -> SignalStrategy:
    """buffer_zone 전략 객체를 생성한다.

    Args:
        slot: 자산 슬롯 설정

    Returns:
        BufferZoneStrategy 인스턴스
    """
    return BufferZoneStrategy(
        ma_col=f"ma_{slot.ma_window}",
        buy_buffer_pct=slot.buy_buffer_zone_pct,
        sell_buffer_pct=slot.sell_buffer_zone_pct,
        hold_days=slot.hold_days,
    )


def _prepare_buffer_zone_signal_df(df: pd.DataFrame, slot: AssetSlotConfig) -> pd.DataFrame:
    """buffer_zone 슬롯용 signal DataFrame에 MA 컬럼을 추가한다.

    원본 DataFrame을 변경하지 않고 MA 컬럼이 추가된 새 DataFrame을 반환한다.

    Args:
        df: 원본 OHLCV DataFrame
        slot: 자산 슬롯 설정 (ma_window, ma_type 참조)

    Returns:
        MA 컬럼(ma_{ma_window})이 추가된 DataFrame
    """
    return add_single_moving_average(df, slot.ma_window, slot.ma_type)


def _get_buffer_zone_warmup_periods(slot: AssetSlotConfig) -> int:
    """buffer_zone 슬롯의 MA 워밍업 기간을 반환한다.

    Args:
        slot: 자산 슬롯 설정

    Returns:
        slot.ma_window (MA 계산에 필요한 최소 데이터 행 수)
    """
    return slot.ma_window


# ============================================================================
# buy_and_hold 전략 전용 함수
# ============================================================================


def _create_buy_and_hold_strategy(slot: AssetSlotConfig) -> SignalStrategy:
    """buy_and_hold 전략 객체를 생성한다.

    Args:
        slot: 자산 슬롯 설정 (사용하지 않음, 파라미터 없는 생성자)

    Returns:
        BuyAndHoldStrategy 인스턴스
    """
    return BuyAndHoldStrategy()


def _prepare_buy_and_hold_signal_df(df: pd.DataFrame, slot: AssetSlotConfig) -> pd.DataFrame:
    """buy_and_hold 슬롯용 signal DataFrame을 그대로 반환한다.

    MA 계산이 불필요하므로 원본을 변경 없이 반환한다.

    Args:
        df: 원본 OHLCV DataFrame
        slot: 자산 슬롯 설정 (사용하지 않음)

    Returns:
        원본 df 그대로 반환
    """
    return df


def _get_buy_and_hold_warmup_periods(slot: AssetSlotConfig) -> int:
    """buy_and_hold 슬롯의 MA 워밍업 기간을 반환한다.

    MA 계산이 없으므로 워밍업이 필요 없다.

    Args:
        slot: 자산 슬롯 설정 (사용하지 않음)

    Returns:
        0 (워밍업 없음)
    """
    return 0


# ============================================================================
# 전략 레지스트리
# ============================================================================

STRATEGY_REGISTRY: dict[str, StrategySpec] = {
    "buffer_zone": StrategySpec(
        strategy_id="buffer_zone",
        create_strategy=_create_buffer_zone_strategy,
        prepare_signal_df=_prepare_buffer_zone_signal_df,
        get_warmup_periods=_get_buffer_zone_warmup_periods,
    ),
    "buy_and_hold": StrategySpec(
        strategy_id="buy_and_hold",
        create_strategy=_create_buy_and_hold_strategy,
        prepare_signal_df=_prepare_buy_and_hold_signal_df,
        get_warmup_periods=_get_buy_and_hold_warmup_periods,
    ),
}
