"""합성 데이터 생성 모듈

레버리지 ETF 등의 합성 데이터를 생성하는 기능을 제공한다.
"""

from qbt.synth.leveraged_etf import (
    calculate_validation_metrics,
    extract_overlap_period,
    find_optimal_cost_model,
    simulate_leveraged_etf,
)

__all__ = [
    "simulate_leveraged_etf",
    "find_optimal_cost_model",
    "extract_overlap_period",
    "calculate_validation_metrics",
]
