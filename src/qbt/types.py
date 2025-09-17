"""
QBT 타입 정의

백테스팅 시스템에서 사용하는 모든 타입을 정의합니다.
"""

from typing import TypedDict, List, Literal, Optional, Dict, Any
from datetime import datetime


class TradeRecord(TypedDict):
    """거래 기록 타입"""

    ticker: str
    action: Literal["BUY", "SELL"]
    date: str
    price: float
    quantity: float
    amount: float
    commission: float
    capital_after: float
    position_after: float


class BacktestResult(TypedDict):
    """백테스트 결과 타입"""

    strategy_name: str
    ticker: str
    start_date: str
    end_date: str
    initial_capital: float
    final_value: float
    total_return: float
    total_return_pct: float
    trades: List[TradeRecord]
    daily_returns: List[float]
    portfolio_values: List[float]
    num_trades: int
    num_buy_trades: int
    num_sell_trades: int
    win_rate: float
    win_rate_pct: float
    total_commission: float
    is_benchmark: bool


class BacktestResultWithExcess(BacktestResult):
    """초과 수익률이 포함된 백테스트 결과 타입"""

    excess_return: float
    excess_return_pct: float


class ExecutionResult(TypedDict):
    """거래 실행 결과 타입"""

    success: bool
    action: Literal["BUY", "SELL"]
    ticker: str
    date: str
    price: float
    quantity: float
    amount: float
    commission: float
    total_cost: float
    capital_after: float
    position_after: float


class ExecutionError(TypedDict):
    """거래 실행 오류 타입"""

    success: Literal[False]
    error: str
    quantity: Literal[0]
    amount: Literal[0]
    commission: Literal[0]


class ExecutionSummary(TypedDict):
    """실행 요약 정보 타입"""

    total_executions: int
    buy_count: int
    sell_count: int
    total_commission: float


class CacheInfo(TypedDict):
    """캐시 정보 타입"""

    cached_datasets: int
    cache_keys: List[str]
    memory_usage_mb: float


class PerformanceMetrics(TypedDict):
    """성과 지표 타입"""

    total_trades: int
    total_days: int
    has_returns: bool
    portfolio_start_value: float
    portfolio_end_value: float


class StrategyComparison(TypedDict):
    """전략 비교 정보 타입"""

    total_return_pct: float
    num_trades: int
    win_rate_pct: float
    total_commission: float
    excess_return_pct: float
    is_benchmark: bool


class ComparisonResult(TypedDict):
    """비교 결과 타입"""

    benchmark_name: Optional[str]
    num_strategies: int
    strategies: Dict[str, StrategyComparison]


class TradeSignalData(TypedDict):
    """거래 신호 데이터 타입"""

    action: Literal["BUY", "SELL"]
    ticker: str
    signal_date: str
    execution_date: str
    signal_price: float
    execution_price: float
    quantity: Optional[float]


class StrategyTaskData(TypedDict):
    """병렬 실행을 위한 전략 작업 데이터 타입"""

    strategy_class: type
    strategy_args: Dict[str, Any]
    strategy_name: str
    data: Any  # pandas.DataFrame (mypy에서 import 문제로 Any 사용)
    ticker: str


class FailedStrategy(TypedDict):
    """실패한 전략 정보 타입"""

    strategy: str
    error: str


# 리터럴 타입 정의
ActionType = Literal["BUY", "SELL"]
PositionSizeMethod = Literal["max_capital", "cash_percent", "portfolio_percent", "fixed_amount"]