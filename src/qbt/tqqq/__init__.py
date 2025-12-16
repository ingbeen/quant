"""
TQQQ 레버리지 ETF 시뮬레이션 및 시각화 패키지
"""

# 시뮬레이션 함수
# 시각화 차트 함수
from qbt.tqqq.dashboard import (
    create_cumulative_return_diff_chart,
    create_daily_return_diff_histogram,
    create_price_comparison_chart,
)
from qbt.tqqq.simulation import (
    calculate_validation_metrics,
    extract_overlap_period,
    find_optimal_cost_model,
    simulate,
)

__all__ = [
    # 시뮬레이션
    "simulate",
    "find_optimal_cost_model",
    "extract_overlap_period",
    "calculate_validation_metrics",
    # 시각화
    "create_price_comparison_chart",
    "create_daily_return_diff_histogram",
    "create_cumulative_return_diff_chart",
]
