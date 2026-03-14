"""버퍼존 통합 전략 모듈

config-driven 방식으로 멀티 자산의 버퍼존 전략을 통합 관리한다.
전 자산 4P 고정 파라미터(MA=200, buy=0.03, sell=0.05, hold=3)로 통일한다.

CONFIGS 목록:
    - buffer_zone_tqqq: QQQ 시그널 + TQQQ 합성 매매 (4P 고정, ma_type=ema)
    - buffer_zone_qqq: QQQ 시그널 + QQQ 매매 (4P 고정)
    - buffer_zone_spy ~ buffer_zone_tlt: 교차 자산 검증 (4P 고정)
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    FIXED_4P_BUY_BUFFER_ZONE_PCT,
    FIXED_4P_HOLD_DAYS,
    FIXED_4P_MA_WINDOW,
    FIXED_4P_SELL_BUFFER_ZONE_PCT,
)
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    resolve_buffer_params,
    run_buffer_strategy,
)
from qbt.backtest.types import SingleBacktestResult
from qbt.common_constants import (
    BUFFER_ZONE_EEM_RESULTS_DIR,
    BUFFER_ZONE_EFA_RESULTS_DIR,
    BUFFER_ZONE_GLD_RESULTS_DIR,
    BUFFER_ZONE_IWM_RESULTS_DIR,
    BUFFER_ZONE_QQQ_RESULTS_DIR,
    BUFFER_ZONE_SPY_RESULTS_DIR,
    BUFFER_ZONE_TLT_RESULTS_DIR,
    BUFFER_ZONE_TQQQ_RESULTS_DIR,
    EEM_DATA_PATH,
    EFA_DATA_PATH,
    GLD_DATA_PATH,
    IWM_DATA_PATH,
    QQQ_DATA_PATH,
    SPY_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)


# ============================================================================
# 설정 데이터클래스
# ============================================================================


@dataclass(frozen=True)
class BufferZoneConfig:
    """버퍼존 통합 전략의 자산별 설정.

    각 자산에 대한 전략 식별 정보, 데이터 경로, 파라미터를 담는다.
    CONFIGS 리스트에 추가하면 자동으로 전략 레지스트리에 등록된다.

    파라미터는 직접 설정하며, 기본값은 4P 확정 파라미터를 사용한다.
    """

    strategy_name: str  # 전략 내부 식별자 (예: "buffer_zone_tqqq")
    display_name: str  # 전략 표시명 (예: "버퍼존 전략 (TQQQ)")
    signal_data_path: Path  # 시그널용 데이터 경로
    trade_data_path: Path  # 매매용 데이터 경로
    result_dir: Path  # 결과 저장 디렉토리
    ma_window: int = FIXED_4P_MA_WINDOW  # 이동평균 기간
    buy_buffer_zone_pct: float = FIXED_4P_BUY_BUFFER_ZONE_PCT  # 매수 버퍼존 비율
    sell_buffer_zone_pct: float = FIXED_4P_SELL_BUFFER_ZONE_PCT  # 매도 버퍼존 비율
    hold_days: int = FIXED_4P_HOLD_DAYS  # 유지일수
    ma_type: str = "ema"  # 이동평균 유형 ("ema" 또는 "sma")


# ============================================================================
# CONFIGS 리스트
# ============================================================================

CONFIGS: list[BufferZoneConfig] = [
    # --- TQQQ (QQQ 시그널 + TQQQ 합성 매매) ---
    BufferZoneConfig(
        strategy_name="buffer_zone_tqqq",
        display_name="버퍼존 전략 (TQQQ)",
        signal_data_path=QQQ_DATA_PATH,
        trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
        result_dir=BUFFER_ZONE_TQQQ_RESULTS_DIR,
    ),
    # --- QQQ ---
    BufferZoneConfig(
        strategy_name="buffer_zone_qqq",
        display_name="버퍼존 전략 (QQQ)",
        signal_data_path=QQQ_DATA_PATH,
        trade_data_path=QQQ_DATA_PATH,
        result_dir=BUFFER_ZONE_QQQ_RESULTS_DIR,
    ),
    # --- cross-asset ---
    BufferZoneConfig(
        strategy_name="buffer_zone_spy",
        display_name="버퍼존 전략 (SPY)",
        signal_data_path=SPY_DATA_PATH,
        trade_data_path=SPY_DATA_PATH,
        result_dir=BUFFER_ZONE_SPY_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_iwm",
        display_name="버퍼존 전략 (IWM)",
        signal_data_path=IWM_DATA_PATH,
        trade_data_path=IWM_DATA_PATH,
        result_dir=BUFFER_ZONE_IWM_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_efa",
        display_name="버퍼존 전략 (EFA)",
        signal_data_path=EFA_DATA_PATH,
        trade_data_path=EFA_DATA_PATH,
        result_dir=BUFFER_ZONE_EFA_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_eem",
        display_name="버퍼존 전략 (EEM)",
        signal_data_path=EEM_DATA_PATH,
        trade_data_path=EEM_DATA_PATH,
        result_dir=BUFFER_ZONE_EEM_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_gld",
        display_name="버퍼존 전략 (GLD)",
        signal_data_path=GLD_DATA_PATH,
        trade_data_path=GLD_DATA_PATH,
        result_dir=BUFFER_ZONE_GLD_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_tlt",
        display_name="버퍼존 전략 (TLT)",
        signal_data_path=TLT_DATA_PATH,
        trade_data_path=TLT_DATA_PATH,
        result_dir=BUFFER_ZONE_TLT_RESULTS_DIR,
    ),
]


# ============================================================================
# 설정 조회 함수
# ============================================================================


def get_config(strategy_name: str) -> BufferZoneConfig:
    """이름으로 BufferZoneConfig를 조회한다.

    Args:
        strategy_name: 전략 내부 식별자 (예: "buffer_zone_tqqq")

    Returns:
        BufferZoneConfig: 해당 설정

    Raises:
        ValueError: strategy_name이 CONFIGS에 존재하지 않는 경우
    """
    for config in CONFIGS:
        if config.strategy_name == strategy_name:
            return config
    available = [c.strategy_name for c in CONFIGS]
    raise ValueError(f"존재하지 않는 strategy_name: '{strategy_name}'. 사용 가능: {available}")


# ============================================================================
# 파라미터 결정 함수
# ============================================================================


def resolve_params_for_config(
    config: BufferZoneConfig,
) -> tuple[BufferStrategyParams, dict[str, str]]:
    """BufferZoneConfig에 따라 전략 파라미터를 결정한다.

    config의 파라미터를 resolve_buffer_params()에 전달한다.

    Args:
        config: 버퍼존 전략 설정

    Returns:
        tuple: (params, sources)
            - params: 전략 파라미터
            - sources: 각 파라미터의 출처 딕셔너리
    """
    return resolve_buffer_params(
        config.ma_window,
        config.buy_buffer_zone_pct,
        config.sell_buffer_zone_pct,
        config.hold_days,
    )


# ============================================================================
# 팩토리 함수
# ============================================================================


def create_runner(config: BufferZoneConfig) -> Callable[[], SingleBacktestResult]:
    """BufferZoneConfig에 대한 run_single 실행 함수를 생성한다.

    팩토리 패턴: config별로 데이터 소스와 결과 경로가 다른 실행 함수를 반환한다.

    Args:
        config: 버퍼존 전략 설정

    Returns:
        Callable: 인자 없이 호출 가능한 run_single 함수
    """

    def run_single() -> SingleBacktestResult:
        """버퍼존 전략 단일 백테스트를 실행한다.

        데이터 로딩부터 전략 실행까지 자체 수행한다.

        Returns:
            SingleBacktestResult: 백테스트 결과 컨테이너
        """
        # 1. 데이터 로딩 및 overlap 처리
        if config.signal_data_path == config.trade_data_path:
            # signal == trade: 동일 데이터, overlap 불필요
            trade_df = load_stock_data(config.trade_data_path)
            signal_df = trade_df.copy()
        else:
            # signal != trade: 겹치는 기간 추출 필요
            signal_df = load_stock_data(config.signal_data_path)
            trade_df = load_stock_data(config.trade_data_path)
            signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

        # 2. 파라미터 결정
        params, sources = resolve_params_for_config(config)

        # 3. 이동평균 계산
        signal_df = add_single_moving_average(signal_df, params.ma_window, ma_type=config.ma_type)

        # 4. 전략 실행
        trades_df, equity_df, summary = run_buffer_strategy(
            signal_df, trade_df, params, strategy_name=config.strategy_name
        )

        # 5. JSON 저장용 파라미터
        params_json: dict[str, Any] = {
            "ma_window": params.ma_window,
            "ma_type": config.ma_type,
            "buy_buffer_zone_pct": round(params.buy_buffer_zone_pct, 4),
            "sell_buffer_zone_pct": round(params.sell_buffer_zone_pct, 4),
            "hold_days": params.hold_days,
            "initial_capital": round(DEFAULT_INITIAL_CAPITAL),
            "param_source": sources,
        }

        return SingleBacktestResult(
            strategy_name=config.strategy_name,
            display_name=config.display_name,
            signal_df=signal_df,
            equity_df=equity_df,
            trades_df=trades_df,
            summary=summary,
            params_json=params_json,
            result_dir=config.result_dir,
            data_info={
                "signal_path": str(config.signal_data_path),
                "trade_path": str(config.trade_data_path),
            },
        )

    return run_single
