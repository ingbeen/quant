"""버퍼존 전략 전용 헬퍼 모듈

BufferZoneStrategy 내부에서 사용하는 HoldState 타입과 밴드/신호 계산 함수를 제공한다.
strategy_common.py의 SignalStrategy Protocol과 분리하여 버퍼존 전용 로직을 캡슐화한다.

포함 내용:
- HoldState: hold_days 상태머신 상태 TypedDict
- compute_bands: 이동평균 기준 상하단 밴드 계산
- detect_buy_signal: 상향돌파 신호 감지
- detect_sell_signal: 하향돌파 신호 감지
"""

from datetime import date
from typing import TypedDict

# ============================================================================
# 버퍼존 전용 TypedDict
# ============================================================================


class HoldState(TypedDict):
    """hold_days 상태머신의 상태 딕셔너리.

    BufferZoneStrategy가 상향돌파 후 일정 기간(hold_days) 동안
    상단 밴드 위에서 유지되는지 추적할 때 사용한다.
    """

    start_date: date
    days_passed: int
    buffer_pct: float  # 매수 버퍼 (buy buffer)
    hold_days_required: int


# ============================================================================
# 밴드/신호 계산 함수
# ============================================================================


def compute_bands(
    ma_value: float,
    buy_buffer_pct: float,
    sell_buffer_pct: float,
) -> tuple[float, float]:
    """이동평균 기준 상하단 밴드를 계산한다.

    upper_band는 매수 버퍼, lower_band는 매도 버퍼.

    Args:
        ma_value: 이동평균 값
        buy_buffer_pct: 매수 버퍼존 비율 (upper_band용, 0~1)
        sell_buffer_pct: 매도 버퍼존 비율 (lower_band용, 0~1)

    Returns:
        tuple: (upper_band, lower_band)
            - upper_band: 상단 밴드 = ma * (1 + buy_buffer_pct)
            - lower_band: 하단 밴드 = ma * (1 - sell_buffer_pct)
    """
    upper_band = ma_value * (1 + buy_buffer_pct)
    lower_band = ma_value * (1 - sell_buffer_pct)
    return upper_band, lower_band


def detect_buy_signal(
    prev_close: float,
    close: float,
    prev_upper_band: float,
    upper_band: float,
) -> bool:
    """상향돌파 신호를 감지한다.

    Args:
        prev_close: 전일 종가
        close: 당일 종가
        prev_upper_band: 전일 상단 밴드
        upper_band: 당일 상단 밴드

    Returns:
        bool: 상향돌파 감지 여부
    """
    # 상향돌파 체크: 전일 종가 <= 상단밴드 AND 당일 종가 > 상단밴드
    return prev_close <= prev_upper_band and close > upper_band


def detect_sell_signal(
    prev_close: float,
    close: float,
    prev_lower_band: float,
    lower_band: float,
) -> bool:
    """하향돌파 신호를 감지한다.

    Args:
        prev_close: 전일 종가
        close: 당일 종가
        prev_lower_band: 전일 하단 밴드
        lower_band: 당일 하단 밴드

    Returns:
        bool: 하향돌파 감지 여부
    """
    # 하향돌파 체크: 전일 종가 >= 하단밴드 AND 당일 종가 < 하단밴드
    return prev_close >= prev_lower_band and close < lower_band
