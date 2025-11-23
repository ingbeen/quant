"""백테스트 패키지"""

from qbt.backtest.core import (
    StrategyParams,
    add_moving_averages,
    generate_walkforward_windows,
    load_data,
    run_buy_and_hold,
    run_grid_search,
    run_strategy,
    run_walkforward,
    validate_data,
)
from qbt.backtest.exceptions import DataValidationError
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
    save_walkforward_results,
)

__all__ = [
    # Core functions
    "load_data",
    "validate_data",
    "add_moving_averages",
    "run_strategy",
    "run_buy_and_hold",
    "run_grid_search",
    "run_walkforward",
    "generate_walkforward_windows",
    "StrategyParams",
    "DataValidationError",
    # Report functions
    "create_result_directory",
    "save_trades",
    "save_equity",
    "save_summary",
    "save_grid_results",
    "save_walkforward_results",
    "plot_equity_curve",
    "plot_drawdown",
    "plot_grid_heatmap",
    "generate_html_report",
]
