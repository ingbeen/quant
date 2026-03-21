"""엔진 공통 모듈

단일 백테스트 엔진과 포트폴리오 엔진이 공유하는 데이터 타입과 체결/equity 기록 함수를 제공한다.

포함 내용:
- PendingOrder: 예약된 주문 정보 (신호일과 체결일 분리)
- TradeRecord: 거래 기록 딕셔너리
- EquityRecord: equity 기록 딕셔너리
- execute_buy_order: 매수 주문 실행
- execute_sell_order: 매도 주문 실행
- record_equity: equity 기록 생성
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal, TypedDict

from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# TypedDict
# ============================================================================


class EquityRecord(TypedDict):
    """record_equity() 반환 타입 / equity_records 리스트 아이템.

    키 "Date"는 COL_DATE 상수의 값이다.
    """

    Date: date
    equity: float
    position: int
    buy_buffer_pct: float
    sell_buffer_pct: float
    upper_band: float | None
    lower_band: float | None


class TradeRecord(TypedDict):
    """execute_sell_order() 거래 기록 딕셔너리."""

    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    buy_buffer_pct: float
    hold_days_used: int


# ============================================================================
# DataClass
# ============================================================================


@dataclass
class PendingOrder:
    """예약된 주문 정보

    신호 발생 시점에 생성되며, 다음 거래일 시가에 실제 체결됩니다.
    이를 통해 신호 발생일과 체결일을 명확히 분리하고, 미래 데이터 참조를 방지합니다.

    타입 안정성:
    - order_type은 Literal["buy", "sell"]로 제한하여 타입 체크 시점에 오류 방지

    중요: 미래 데이터 참조 방지
    - execute_date, price_raw를 저장하지 않음 (look-ahead bias 방지)
    - 다음 날 루프에서 해당 날짜의 시가를 조회하여 체결
    - 마지막 날 신호는 자연스럽게 미체결됨 (다음 날이 없으므로)
    """

    order_type: Literal["buy", "sell"]  # 주문 유형 (타입 안전)
    signal_date: date  # 신호 발생 날짜 (디버깅/로깅용)
    buy_buffer_zone_pct: float  # 신호 시점의 매수 버퍼 비율 (0~1)
    hold_days_used: int  # 신호 시점의 유지일수


# ============================================================================
# 체결/equity 기록 함수
# ============================================================================


def execute_buy_order(
    order: PendingOrder,
    open_price: float,
    execute_date: date,
    capital: float,
    position: int,
) -> tuple[int, float, float, date, bool]:
    """매수 주문을 실행한다.

    Args:
        order: 실행할 매수 주문
        open_price: 체결 날짜의 시가 (슬리피지 적용 전)
        execute_date: 체결 날짜
        capital: 현재 보유 현금
        position: 현재 포지션 (0이어야 함)

    Returns:
        tuple: (new_position, new_capital, entry_price, entry_date, executed)
            - new_position: 새 포지션 수량
            - new_capital: 새 자본
            - entry_price: 진입 가격 (슬리피지 적용)
            - entry_date: 진입 날짜
            - executed: 실행 여부 (자본 부족 시 False)
    """
    # 슬리피지 적용 (매수 시 +0.3%)
    buy_price = open_price * (1 + SLIPPAGE_RATE)
    shares = int(capital / buy_price)

    if shares > 0:
        buy_amount = shares * buy_price
        new_capital = capital - buy_amount
        return shares, new_capital, buy_price, execute_date, True
    else:
        # 자본 부족으로 매수 불가
        logger.debug(f"매수 불가 (자본 부족): 날짜={execute_date}, 필요가격={buy_price:.2f}, " f"현재자본={capital:.2f}, 가능수량=0")
        return position, capital, 0.0, execute_date, False


def execute_sell_order(
    order: PendingOrder,
    open_price: float,
    execute_date: date,
    capital: float,
    position: int,
    entry_price: float,
    entry_date: date,
) -> tuple[int, float, TradeRecord]:
    """매도 주문을 실행한다.

    Args:
        order: 실행할 매도 주문
        open_price: 체결 날짜의 시가 (슬리피지 적용 전)
        execute_date: 체결 날짜
        capital: 현재 보유 현금
        position: 현재 포지션 수량
        entry_price: 진입 가격
        entry_date: 진입 날짜

    Returns:
        tuple: (new_position, new_capital, trade_record)
            - new_position: 새 포지션 (0)
            - new_capital: 새 자본 (매도 금액 추가)
            - trade_record: 거래 기록 딕셔너리
    """
    # 슬리피지 적용 (매도 시 -0.3%)
    sell_price = open_price * (1 - SLIPPAGE_RATE)
    sell_amount = position * sell_price
    new_capital = capital + sell_amount

    trade_record: TradeRecord = {
        "entry_date": entry_date,
        "exit_date": execute_date,
        "entry_price": entry_price,
        "exit_price": sell_price,
        "shares": position,
        "pnl": (sell_price - entry_price) * position,
        "pnl_pct": (sell_price - entry_price) / entry_price,
        "buy_buffer_pct": order.buy_buffer_zone_pct,
        "hold_days_used": 0,
    }

    return 0, new_capital, trade_record


def record_equity(
    current_date: date,
    capital: float,
    position: int,
    close_price: float,
    buy_buffer_pct: float,
    sell_buffer_pct: float,
    upper_band: float | None,
    lower_band: float | None,
) -> EquityRecord:
    """현재 시점의 equity를 기록한다.

    Args:
        current_date: 현재 날짜
        capital: 현재 보유 현금
        position: 현재 포지션 수량
        close_price: 현재 종가
        buy_buffer_pct: 현재 매수 버퍼존 비율
        sell_buffer_pct: 현재 매도 버퍼존 비율
        upper_band: 상단 밴드 (첫 날은 None 가능)
        lower_band: 하단 밴드 (첫 날은 None 가능)

    Returns:
        equity 기록 딕셔너리
    """
    if position > 0:
        equity = capital + position * close_price
    else:
        equity = capital

    return {
        "Date": current_date,
        "equity": equity,
        "position": position,
        "buy_buffer_pct": buy_buffer_pct,
        "sell_buffer_pct": sell_buffer_pct,
        "upper_band": upper_band,
        "lower_band": lower_band,
    }
