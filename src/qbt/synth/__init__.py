"""합성 데이터 생성 모듈

레버리지 ETF 등의 합성 데이터를 생성하는 기능을 제공한다.
"""

from qbt.synth.leveraged_etf import (
    find_optimal_multiplier,
    generate_daily_comparison_csv,
    simulate_leveraged_etf,
    validate_simulation,
)

__all__ = [
    "simulate_leveraged_etf",
    "find_optimal_multiplier",
    "validate_simulation",
    "generate_daily_comparison_csv",
]
