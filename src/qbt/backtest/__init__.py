"""백테스트 패키지"""

from qbt.backtest.data import load_data, validate_data
from qbt.backtest.exceptions import DataValidationError
from qbt.backtest.metrics import calculate_summary
from qbt.backtest.report import (
    create_result_directory,
    generate_html_report,
    plot_drawdown,
    plot_equity_curve,
    plot_grid_heatmap,
    save_equity,
    save_grid_results,
    save_summary,
    save_trades,
)
from qbt.backtest.strategy import (
    BufferStrategyParams,
    StrategyParams,
    add_single_moving_average,
    run_buffer_strategy,
    run_buy_and_hold,
    run_grid_search,
)

__all__ = [
    # Data functions
    "load_data",
    "validate_data",
    # Strategy functions
    "add_single_moving_average",
    "run_buffer_strategy",
    "run_buy_and_hold",
    "run_grid_search",
    "StrategyParams",
    "BufferStrategyParams",
    # Metrics functions
    "calculate_summary",
    # Exceptions
    "DataValidationError",
    # Report functions
    "create_result_directory",
    "save_trades",
    "save_equity",
    "save_summary",
    "save_grid_results",
    "plot_equity_curve",
    "plot_drawdown",
    "plot_grid_heatmap",
    "generate_html_report",
]
