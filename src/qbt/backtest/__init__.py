"""백테스트 패키지"""

from qbt.backtest.analysis import (
    add_single_moving_average,
    calculate_monthly_returns,
    calculate_regime_summaries,
    calculate_summary,
)
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    run_buffer_strategy,
    run_grid_search,
)
from qbt.backtest.strategies.buy_and_hold import (
    BuyAndHoldParams,
    run_buy_and_hold,
)
from qbt.backtest.types import (
    BestGridParams,
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
    "run_buy_and_hold",
    "run_grid_search",
    "BufferStrategyParams",
    "BuyAndHoldParams",
    # Types
    "BestGridParams",
    "MarketRegimeDict",
    "RegimeSummaryDict",
    "SingleBacktestResult",
]
