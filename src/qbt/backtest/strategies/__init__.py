"""백테스트 전략 패키지

전략별 모듈을 제공한다.
- buffer_zone: 이동평균 기반 버퍼존 전략
- buy_and_hold: 매수 후 보유 벤치마크 전략
"""

from qbt.backtest.strategies.buffer_zone import (
    BaseStrategyParams,
    BufferStrategyParams,
    PendingOrder,
    PendingOrderConflictError,
    run_buffer_strategy,
    run_grid_search,
)
from qbt.backtest.strategies.buffer_zone import (
    resolve_params as buffer_zone_resolve_params,
)
from qbt.backtest.strategies.buffer_zone import (
    run_single as buffer_zone_run_single,
)
from qbt.backtest.strategies.buy_and_hold import (
    BuyAndHoldParams,
    run_buy_and_hold,
)
from qbt.backtest.strategies.buy_and_hold import (
    resolve_params as buy_and_hold_resolve_params,
)
from qbt.backtest.strategies.buy_and_hold import (
    run_single as buy_and_hold_run_single,
)

__all__ = [
    # Buffer zone strategy
    "BaseStrategyParams",
    "BufferStrategyParams",
    "PendingOrder",
    "PendingOrderConflictError",
    "run_buffer_strategy",
    "run_grid_search",
    "buffer_zone_resolve_params",
    "buffer_zone_run_single",
    # Buy and hold strategy
    "BuyAndHoldParams",
    "run_buy_and_hold",
    "buy_and_hold_resolve_params",
    "buy_and_hold_run_single",
]
