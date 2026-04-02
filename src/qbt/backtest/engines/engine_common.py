"""엔진 공통 모듈

단일 백테스트 엔진과 포트폴리오 엔진이 공유하는 데이터 타입과 체결 계산 함수를 제공한다.

포함 내용:
- PendingOrder: 예약된 주문 정보 (신호일과 체결일 분리)
- TradeRecord: 거래 기록 딕셔너리
- PortfolioTradeRecord: 포트폴리오 전용 거래 기록 (TradeRecord 확장)
- EquityRecord: equity 기록 딕셔너리
- execute_buy_order: 매수 체결 계산 (순수 함수)
- execute_sell_order: 매도 체결 계산 (순수 함수)
- create_trade_record: TradeRecord 생성 헬퍼
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


class TradeRecord(TypedDict):
    """거래 기록 딕셔너리. 단일 백테스트 엔진에서 사용."""

    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    buy_buffer_pct: float
    hold_days_used: int


class PortfolioTradeRecord(TradeRecord):
    """포트폴리오 전용 거래 기록. TradeRecord를 확장한다."""

    asset_id: str
    trade_type: str  # "signal" | "rebalance"


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


# ============================================================================
# 체결 계산 함수 (순수 함수 — 상태 변경 없음)
# ============================================================================


def execute_buy_order(
    open_price: float,
    amount: float,
) -> tuple[int, float, float]:
    """매수 체결 계산. 상태 업데이트는 호출부에서 수행한다.

    슬리피지를 적용한 매수가로 체결 수량과 비용을 계산한다.
    단일 엔진은 전체 자본을, 포트폴리오 엔진은 delta_amount를 amount로 전달한다.

    Args:
        open_price: 시가 (슬리피지 적용 전)
        amount: 매수에 사용할 금액

    Returns:
        (shares, buy_price, total_cost) 튜플.
        shares=0이면 금액 부족으로 미체결, total_cost=0.0.
    """
    buy_price = open_price * (1 + SLIPPAGE_RATE)
    shares = int(amount / buy_price)

    if shares <= 0:
        return (0, buy_price, 0.0)

    cost = shares * buy_price
    return (shares, buy_price, cost)


def execute_sell_order(
    open_price: float,
    shares_to_sell: int,
    entry_price: float,
) -> tuple[float, float, float, float]:
    """매도 체결 계산. 상태 업데이트는 호출부에서 수행한다.

    슬리피지를 적용한 매도가로 매도 대금, 손익, 손익률을 계산한다.
    단일 엔진은 전량 매도를, 포트폴리오 엔진은 부분 매도도 지원한다.

    Args:
        open_price: 시가 (슬리피지 적용 전)
        shares_to_sell: 매도할 수량
        entry_price: 진입가

    Returns:
        (sell_price, proceeds, pnl, pnl_pct) 튜플.
    """
    sell_price = open_price * (1 - SLIPPAGE_RATE)
    proceeds = shares_to_sell * sell_price
    pnl = (sell_price - entry_price) * shares_to_sell
    pnl_pct = (sell_price - entry_price) / entry_price
    return (sell_price, proceeds, pnl, pnl_pct)


def create_trade_record(
    entry_date: date,
    exit_date: date,
    entry_price: float,
    exit_price: float,
    shares: int,
    pnl: float,
    pnl_pct: float,
    buy_buffer_pct: float = 0.0,
    hold_days_used: int = 0,
) -> TradeRecord:
    """TradeRecord TypedDict를 생성한다.

    Args:
        entry_date: 진입 날짜
        exit_date: 청산 날짜
        entry_price: 진입가
        exit_price: 청산가
        shares: 체결 수량
        pnl: 손익
        pnl_pct: 손익률
        buy_buffer_pct: 매수 시 버퍼존 비율 (기본값 0.0, B&H용)
        hold_days_used: 매수 시 유지일수 (기본값 0, B&H용)

    Returns:
        TradeRecord TypedDict
    """
    return {
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "shares": shares,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "buy_buffer_pct": buy_buffer_pct,
        "hold_days_used": hold_days_used,
    }


def record_equity(
    current_date: date,
    capital: float,
    position: int,
    close_price: float,
) -> EquityRecord:
    """현재 시점의 equity를 기록한다.

    Args:
        current_date: 현재 날짜
        capital: 현재 보유 현금
        position: 현재 포지션 수량
        close_price: 현재 종가

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
    }
