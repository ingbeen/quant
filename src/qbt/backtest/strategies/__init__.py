"""백테스트 전략 패키지

전략별 모듈을 제공한다.
- strategy_common: SignalStrategy Protocol, PendingOrderConflictError
- buffer_zone_helpers: 버퍼존 전용 HoldState, compute_bands, detect_buy/sell_signal
- buffer_zone: 버퍼존 통합 config-driven 전략 모듈 (8개 자산, 4P 고정)
- buy_and_hold: 매수 후 보유 벤치마크 전략 (팩토리 패턴으로 멀티 티커 지원)
- runners: create_buffer_zone_runner, create_buy_and_hold_runner 팩토리

PendingOrder는 engines.engine_common에서 직접 import한다 (계층 분리 원칙).
"""

from qbt.backtest.strategies.buffer_zone import (
    BufferZoneConfig,
    resolve_params_for_config,
)
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldConfig
from qbt.backtest.strategies.strategy_common import PendingOrderConflictError
from qbt.backtest.types import BufferStrategyParams

__all__ = [
    # Buffer zone unified (config-driven)
    "BufferZoneConfig",
    "resolve_params_for_config",
    # Buffer zone strategy (shared)
    "BufferStrategyParams",
    "PendingOrderConflictError",
    # Buy and hold strategy
    "BuyAndHoldConfig",
]
