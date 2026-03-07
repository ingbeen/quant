"""백테스트 전략 패키지

전략별 모듈을 제공한다.
- buffer_zone_helpers: 버퍼존 계열 전략 공통 로직
- buffer_zone: 버퍼존 통합 config-driven 전략 모듈 (9개 자산)
- buffer_zone_atr_tqqq: QQQ 시그널 + TQQQ 매매 버퍼존 ATR 전략
- buy_and_hold: 매수 후 보유 벤치마크 전략 (팩토리 패턴으로 멀티 티커 지원)
- donchian_helpers: Donchian Channel 전략 핵심 로직
- donchian_channel_tqqq: QQQ 시그널 + TQQQ 매매 Donchian Channel 전략
"""

from qbt.backtest.strategies.buffer_zone import (
    BufferZoneConfig,
    resolve_params_for_config,
)
from qbt.backtest.strategies.buffer_zone import (
    create_runner as create_buffer_zone_runner,
)
from qbt.backtest.strategies.buffer_zone import (
    get_config as get_buffer_zone_config,
)
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    PendingOrder,
    PendingOrderConflictError,
    resolve_buffer_params,
    run_buffer_strategy,
    run_grid_search,
)
from qbt.backtest.strategies.buy_and_hold import (
    BuyAndHoldConfig,
    BuyAndHoldParams,
    create_runner,
    run_buy_and_hold,
)
from qbt.backtest.strategies.donchian_helpers import (
    DonchianStrategyParams,
    run_donchian_strategy,
)

__all__ = [
    # Buffer zone unified (config-driven)
    "BufferZoneConfig",
    "create_buffer_zone_runner",
    "get_buffer_zone_config",
    "resolve_params_for_config",
    # Buffer zone strategy (shared)
    "BufferStrategyParams",
    "PendingOrder",
    "PendingOrderConflictError",
    "resolve_buffer_params",
    "run_buffer_strategy",
    "run_grid_search",
    # Buy and hold strategy
    "BuyAndHoldConfig",
    "BuyAndHoldParams",
    "create_runner",
    "run_buy_and_hold",
    # Donchian Channel strategy
    "DonchianStrategyParams",
    "run_donchian_strategy",
]
