"""백테스트 패키지"""

from qbt.backtest.analysis import (
    add_single_moving_average,
    calculate_monthly_returns,
    calculate_regime_summaries,
    calculate_summary,
)
from qbt.backtest.engines.backtest_engine import run_buffer_strategy, run_grid_search
from qbt.backtest.types import (
    BufferStrategyParams,
    MarketRegimeDict,
    RegimeSummaryDict,
    SingleBacktestResult,
)

__all__ = [
    # Analysis functions
    "add_single_moving_average",
    "calculate_monthly_returns",
    "calculate_regime_summaries",
    "calculate_summary",
    # Strategy functions
    "run_buffer_strategy",
    "run_grid_search",
    "BufferStrategyParams",
    # Types
    "MarketRegimeDict",
    "RegimeSummaryDict",
    "SingleBacktestResult",
]
