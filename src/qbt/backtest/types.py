"""
백테스트 도메인 TypedDict 정의

백테스트 도메인에서 사용하는 딕셔너리 구조를 타입으로 정의한다.
- 성과 요약 (SummaryDict, BuyAndHoldResultDict, BufferStrategyResultDict)
- 거래/자본 기록 (EquityRecord, TradeRecord)
- 상태 관리 (HoldState)
- 그리드 서치 결과 (GridSearchResult)
- 최적 파라미터 (BestGridParams)
"""

from datetime import date
from typing import NotRequired, TypedDict


class SummaryDict(TypedDict):
    """calculate_summary() 반환 타입.

    성과 지표 요약 딕셔너리.
    equity_df가 비어있는 경우 start_date/end_date가 포함되지 않으므로 NotRequired.
    """

    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    cagr: float
    mdd: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    start_date: NotRequired[str]
    end_date: NotRequired[str]


class BuyAndHoldResultDict(SummaryDict):
    """run_buy_and_hold() 반환 타입.

    SummaryDict를 상속하고 전략 식별자를 추가한다.
    """

    strategy: str


class BufferStrategyResultDict(SummaryDict):
    """run_buffer_strategy() 반환 타입.

    SummaryDict를 상속하고 전략 파라미터를 추가한다.
    """

    strategy: str
    ma_window: int
    buffer_zone_pct: float
    hold_days: int


class EquityRecord(TypedDict):
    """_record_equity() 반환 타입 / equity_records 리스트 아이템.

    키 "Date"는 COL_DATE 상수의 값이다.
    """

    Date: date
    equity: float
    position: int
    buffer_zone_pct: float
    upper_band: float | None
    lower_band: float | None


class TradeRecord(TypedDict):
    """_execute_sell_order() 거래 기록 딕셔너리."""

    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    exit_reason: str
    buffer_zone_pct: float
    hold_days_used: int
    recent_buy_count: int


class HoldState(TypedDict):
    """hold_days 상태머신의 상태 딕셔너리."""

    start_date: date
    days_passed: int
    buffer_pct: float
    hold_days_required: int


class GridSearchResult(TypedDict):
    """_run_buffer_strategy_for_grid() 반환 타입.

    키 이름은 backtest/constants.py의 COL_* 상수 값과 동일하다.
    """

    ma_window: int
    buffer_zone_pct: float
    hold_days: int
    recent_months: int
    total_return_pct: float
    cagr: float
    mdd: float
    total_trades: int
    win_rate: float
    final_capital: float


class BestGridParams(TypedDict):
    """load_best_grid_params() 반환 타입.

    grid_results.csv에서 CAGR 1위 파라미터 4개를 담는다.
    """

    ma_window: int
    buffer_zone_pct: float
    hold_days: int
    recent_months: int
