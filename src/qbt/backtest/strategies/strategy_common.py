"""전략 공통 모듈

SignalStrategy Protocol, 공통 타입, 예외, 신호/밴드 계산 함수를 제공한다.

포함 내용:
- SignalStrategy Protocol: 단일/포트폴리오 엔진이 공통으로 사용하는 전략 인터페이스
- HoldState: hold_days 상태머신 상태
- PendingOrderConflictError: Pending Order 충돌 예외
- compute_bands: 이동평균 기준 상하단 밴드 계산
- detect_buy_signal: 상향돌파 신호 감지
- detect_sell_signal: 하향돌파 신호 감지
"""

from datetime import date
from typing import Protocol, TypedDict, runtime_checkable

# ============================================================================
# 공통 TypedDict
# ============================================================================


class HoldState(TypedDict):
    """hold_days 상태머신의 상태 딕셔너리."""

    start_date: date
    days_passed: int
    buffer_pct: float  # 매수 버퍼 (buy buffer)
    hold_days_required: int


# ============================================================================
# 예외 클래스
# ============================================================================


class PendingOrderConflictError(Exception):
    """Pending Order 충돌 예외

    이 예외는 백테스트의 Critical Invariant 위반을 나타냅니다.

    발생 조건:
    - pending_order가 이미 존재하는 상태에서 새로운 신호가 발생하려 할 때

    왜 중요한가:
    - pending은 "신호일 종가 → 체결일 시가" 사이의 단일 예약 상태를 나타냄
    - 이 기간에 새로운 신호가 발생하면 논리적 모순 (두 신호가 동시에 존재할 수 없음)
    - 이는 매우 크리티컬한 버그로, 발견 즉시 백테스트를 중단해야 함

    디버깅 방법:
    - 예외 메시지에서 기존 pending 정보 및 새 신호 발생 시점 확인
    - hold_days 로직, 신호 감지 로직에서 타이밍 문제 검토
    """

    pass


# ============================================================================
# SignalStrategy Protocol
# ============================================================================


@runtime_checkable
class SignalStrategy(Protocol):
    """전략 인터페이스 Protocol.

    단일 백테스트 엔진과 포트폴리오 엔진이 공통으로 사용하는 전략 인터페이스.
    이 Protocol을 준수하는 클래스는 check_buy, check_sell 메서드를 구현해야 한다.

    설계 원칙:
    - check_buy는 매수 여부와 갱신된 HoldState를 함께 반환한다.
    - check_sell은 매도 여부만 반환한다.
    - hold_days_required는 생성자가 아닌 check_buy 호출 시 매번 전달한다.
      (포트폴리오 엔진이 config.hold_days를 매 호출마다 전달하기 위함)
    """

    def check_buy(
        self,
        prev_close: float,
        cur_close: float,
        prev_upper: float,
        cur_upper: float,
        hold_state: "HoldState | None",
        hold_days_required: int,
    ) -> tuple[bool, "HoldState | None"]:
        """매수 신호 여부와 갱신된 HoldState를 반환한다.

        Args:
            prev_close: 전일 종가
            cur_close: 당일 종가
            prev_upper: 전일 상단 밴드
            cur_upper: 당일 상단 밴드
            hold_state: 현재 hold_days 상태 (None이면 대기 없음)
            hold_days_required: 신호 확정까지 대기 기간 (0 = 버퍼존만 모드)

        Returns:
            tuple: (매수 여부, 갱신된 HoldState)
                - 매수 여부: True이면 이번 날짜에 buy pending을 생성해야 함
                - 갱신된 HoldState: None이면 상태 없음
        """
        ...

    def check_sell(
        self,
        prev_close: float,
        cur_close: float,
        prev_lower: float,
        cur_lower: float,
    ) -> bool:
        """매도 신호 여부를 반환한다.

        Args:
            prev_close: 전일 종가
            cur_close: 당일 종가
            prev_lower: 전일 하단 밴드
            cur_lower: 당일 하단 밴드

        Returns:
            True이면 이번 날짜에 sell pending을 생성해야 함
        """
        ...


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
