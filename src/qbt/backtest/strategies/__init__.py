"""백테스트 전략 패키지

전략별 모듈을 제공한다.
- strategy_common: SignalStrategy Protocol, 공통 타입/예외/신호 함수
- buffer_zone: 버퍼존 통합 config-driven 전략 모듈 (8개 자산, 4P 고정)
- buy_and_hold: 매수 후 보유 벤치마크 전략 (팩토리 패턴으로 멀티 티커 지원)
"""

from qbt.backtest.engines.engine_common import PendingOrder
from qbt.backtest.strategies.buffer_zone import (
    BufferStrategyParams,
    BufferZoneConfig,
    resolve_params_for_config,
)
from qbt.backtest.strategies.buy_and_hold import (
    BuyAndHoldConfig,
    BuyAndHoldParams,
    create_runner,
    run_buy_and_hold,
)
from qbt.backtest.strategies.strategy_common import PendingOrderConflictError

__all__ = [
    # Buffer zone unified (config-driven)
    "BufferZoneConfig",
    "resolve_params_for_config",
    # Buffer zone strategy (shared)
    "BufferStrategyParams",
    "PendingOrder",
    "PendingOrderConflictError",
    # Buy and hold strategy
    "BuyAndHoldConfig",
    "BuyAndHoldParams",
    "create_runner",
    "run_buy_and_hold",
]
