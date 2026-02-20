"""백테스트 전략 패키지

전략별 모듈을 제공한다.
- buffer_zone_helpers: 버퍼존 계열 전략 공통 로직
- buffer_zone_tqqq: QQQ 시그널 + TQQQ 매매 버퍼존 전략
- buffer_zone_qqq: QQQ 시그널 + QQQ 매매 버퍼존 전략
- buy_and_hold: 매수 후 보유 벤치마크 전략 (팩토리 패턴으로 멀티 티커 지원)
"""

from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    PendingOrder,
    PendingOrderConflictError,
    run_buffer_strategy,
    run_grid_search,
)
from qbt.backtest.strategies.buy_and_hold import (
    BuyAndHoldConfig,
    BuyAndHoldParams,
    create_runner,
    run_buy_and_hold,
)

__all__ = [
    # Buffer zone strategy (shared)
    "BufferStrategyParams",
    "PendingOrder",
    "PendingOrderConflictError",
    "run_buffer_strategy",
    "run_grid_search",
    # Buy and hold strategy
    "BuyAndHoldConfig",
    "BuyAndHoldParams",
    "create_runner",
    "run_buy_and_hold",
]
