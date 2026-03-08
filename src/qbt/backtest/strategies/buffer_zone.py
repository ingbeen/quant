"""버퍼존 통합 전략 모듈

config-driven 방식으로 9개 자산의 버퍼존 전략을 통합 관리한다.
기존 buffer_zone_tqqq, buffer_zone_qqq 모듈과 동일한 실행 로직을 공유하되,
BufferZoneConfig 기반으로 확장성을 제공한다.

CONFIGS 목록 (9개):
    - buffer_zone_tqqq: QQQ 시그널 + TQQQ 합성 매매 (override→grid→DEFAULT)
    - buffer_zone_qqq: QQQ 시그널 + QQQ 매매 (override→grid→DEFAULT)
    - buffer_zone_qqq_4p: QQQ 4P 기준선 (고정 파라미터)
    - buffer_zone_spy ~ buffer_zone_tlt: 교차 자산 검증 (고정 파라미터)
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL
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
    BUFFER_ZONE_QQQ_4P_RESULTS_DIR,
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

    각 자산에 대한 전략 식별 정보, 데이터 경로, 파라미터 결정 방식을 담는다.
    CONFIGS 리스트에 추가하면 자동으로 전략 레지스트리에 등록된다.

    파라미터 결정 방식:
        - override가 설정된 경우: 해당 값 고정 사용 (cross-asset 패턴)
        - override=None + grid_results_path 존재: grid 최적값 사용 (기존 패턴)
        - override=None + grid_results_path=None: DEFAULT 상수 사용
    """

    strategy_name: str  # 전략 내부 식별자 (예: "buffer_zone_tqqq")
    display_name: str  # 전략 표시명 (예: "버퍼존 전략 (TQQQ)")
    signal_data_path: Path  # 시그널용 데이터 경로
    trade_data_path: Path  # 매매용 데이터 경로
    result_dir: Path  # 결과 저장 디렉토리
    grid_results_path: Path | None  # 그리드 서치 결과 CSV 경로 (None이면 grid 건너뜀)
    override_ma_window: int | None  # MA 기간 오버라이드 (None이면 폴백)
    override_buy_buffer_zone_pct: float | None  # 매수 버퍼존 비율 오버라이드 (None이면 폴백)
    override_sell_buffer_zone_pct: float | None  # 매도 버퍼존 비율 오버라이드 (None이면 폴백)
    override_hold_days: int | None  # 유지일수 오버라이드 (None이면 폴백)
    override_recent_months: int | None  # 조정기간 오버라이드 (None이면 폴백)
    ma_type: str  # 이동평균 유형 ("ema" 또는 "sma")


# ============================================================================
# CONFIGS 리스트 (9개)
# ============================================================================

# cross-asset 공통 고정값
_CROSS_ASSET_MA_WINDOW = 200
_CROSS_ASSET_BUY_BUFFER_PCT = 0.03  # 매수 버퍼존 비율 (0.03 = 3%)
_CROSS_ASSET_SELL_BUFFER_PCT = 0.05  # 매도 버퍼존 비율 (0.05 = 5%)
_CROSS_ASSET_HOLD_DAYS = 2
_CROSS_ASSET_RECENT_MONTHS = 0

CONFIGS: list[BufferZoneConfig] = [
    # --- 기존 2개 (override=None, grid 폴백) ---
    BufferZoneConfig(
        strategy_name="buffer_zone_tqqq",
        display_name="버퍼존 전략 (TQQQ)",
        signal_data_path=QQQ_DATA_PATH,
        trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
        result_dir=BUFFER_ZONE_TQQQ_RESULTS_DIR,
        grid_results_path=BUFFER_ZONE_TQQQ_RESULTS_DIR / "grid_results.csv",
        override_ma_window=None,
        override_buy_buffer_zone_pct=None,
        override_sell_buffer_zone_pct=None,
        override_hold_days=None,
        override_recent_months=None,
        ma_type="ema",
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_qqq",
        display_name="버퍼존 전략 (QQQ)",
        signal_data_path=QQQ_DATA_PATH,
        trade_data_path=QQQ_DATA_PATH,
        result_dir=BUFFER_ZONE_QQQ_RESULTS_DIR,
        grid_results_path=BUFFER_ZONE_QQQ_RESULTS_DIR / "grid_results.csv",
        override_ma_window=None,
        override_buy_buffer_zone_pct=None,
        override_sell_buffer_zone_pct=None,
        override_hold_days=None,
        override_recent_months=None,
        ma_type="ema",
    ),
    # --- QQQ 4P 기준선 (고정 파라미터) ---
    BufferZoneConfig(
        strategy_name="buffer_zone_qqq_4p",
        display_name="버퍼존 전략 (QQQ 4P)",
        signal_data_path=QQQ_DATA_PATH,
        trade_data_path=QQQ_DATA_PATH,
        result_dir=BUFFER_ZONE_QQQ_4P_RESULTS_DIR,
        grid_results_path=None,
        override_ma_window=_CROSS_ASSET_MA_WINDOW,
        override_buy_buffer_zone_pct=_CROSS_ASSET_BUY_BUFFER_PCT,
        override_sell_buffer_zone_pct=_CROSS_ASSET_SELL_BUFFER_PCT,
        override_hold_days=_CROSS_ASSET_HOLD_DAYS,
        override_recent_months=_CROSS_ASSET_RECENT_MONTHS,
        ma_type="ema",
    ),
    # --- cross-asset 6개 (고정 파라미터) ---
    BufferZoneConfig(
        strategy_name="buffer_zone_spy",
        display_name="버퍼존 전략 (SPY)",
        signal_data_path=SPY_DATA_PATH,
        trade_data_path=SPY_DATA_PATH,
        result_dir=BUFFER_ZONE_SPY_RESULTS_DIR,
        grid_results_path=None,
        override_ma_window=_CROSS_ASSET_MA_WINDOW,
        override_buy_buffer_zone_pct=_CROSS_ASSET_BUY_BUFFER_PCT,
        override_sell_buffer_zone_pct=_CROSS_ASSET_SELL_BUFFER_PCT,
        override_hold_days=_CROSS_ASSET_HOLD_DAYS,
        override_recent_months=_CROSS_ASSET_RECENT_MONTHS,
        ma_type="ema",
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_iwm",
        display_name="버퍼존 전략 (IWM)",
        signal_data_path=IWM_DATA_PATH,
        trade_data_path=IWM_DATA_PATH,
        result_dir=BUFFER_ZONE_IWM_RESULTS_DIR,
        grid_results_path=None,
        override_ma_window=_CROSS_ASSET_MA_WINDOW,
        override_buy_buffer_zone_pct=_CROSS_ASSET_BUY_BUFFER_PCT,
        override_sell_buffer_zone_pct=_CROSS_ASSET_SELL_BUFFER_PCT,
        override_hold_days=_CROSS_ASSET_HOLD_DAYS,
        override_recent_months=_CROSS_ASSET_RECENT_MONTHS,
        ma_type="ema",
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_efa",
        display_name="버퍼존 전략 (EFA)",
        signal_data_path=EFA_DATA_PATH,
        trade_data_path=EFA_DATA_PATH,
        result_dir=BUFFER_ZONE_EFA_RESULTS_DIR,
        grid_results_path=None,
        override_ma_window=_CROSS_ASSET_MA_WINDOW,
        override_buy_buffer_zone_pct=_CROSS_ASSET_BUY_BUFFER_PCT,
        override_sell_buffer_zone_pct=_CROSS_ASSET_SELL_BUFFER_PCT,
        override_hold_days=_CROSS_ASSET_HOLD_DAYS,
        override_recent_months=_CROSS_ASSET_RECENT_MONTHS,
        ma_type="ema",
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_eem",
        display_name="버퍼존 전략 (EEM)",
        signal_data_path=EEM_DATA_PATH,
        trade_data_path=EEM_DATA_PATH,
        result_dir=BUFFER_ZONE_EEM_RESULTS_DIR,
        grid_results_path=None,
        override_ma_window=_CROSS_ASSET_MA_WINDOW,
        override_buy_buffer_zone_pct=_CROSS_ASSET_BUY_BUFFER_PCT,
        override_sell_buffer_zone_pct=_CROSS_ASSET_SELL_BUFFER_PCT,
        override_hold_days=_CROSS_ASSET_HOLD_DAYS,
        override_recent_months=_CROSS_ASSET_RECENT_MONTHS,
        ma_type="ema",
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_gld",
        display_name="버퍼존 전략 (GLD)",
        signal_data_path=GLD_DATA_PATH,
        trade_data_path=GLD_DATA_PATH,
        result_dir=BUFFER_ZONE_GLD_RESULTS_DIR,
        grid_results_path=None,
        override_ma_window=_CROSS_ASSET_MA_WINDOW,
        override_buy_buffer_zone_pct=_CROSS_ASSET_BUY_BUFFER_PCT,
        override_sell_buffer_zone_pct=_CROSS_ASSET_SELL_BUFFER_PCT,
        override_hold_days=_CROSS_ASSET_HOLD_DAYS,
        override_recent_months=_CROSS_ASSET_RECENT_MONTHS,
        ma_type="ema",
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_tlt",
        display_name="버퍼존 전략 (TLT)",
        signal_data_path=TLT_DATA_PATH,
        trade_data_path=TLT_DATA_PATH,
        result_dir=BUFFER_ZONE_TLT_RESULTS_DIR,
        grid_results_path=None,
        override_ma_window=_CROSS_ASSET_MA_WINDOW,
        override_buy_buffer_zone_pct=_CROSS_ASSET_BUY_BUFFER_PCT,
        override_sell_buffer_zone_pct=_CROSS_ASSET_SELL_BUFFER_PCT,
        override_hold_days=_CROSS_ASSET_HOLD_DAYS,
        override_recent_months=_CROSS_ASSET_RECENT_MONTHS,
        ma_type="ema",
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

    resolve_buffer_params()에 config의 override/grid 값을 위임한다.

    Args:
        config: 버퍼존 전략 설정

    Returns:
        tuple: (params, sources)
            - params: 전략 파라미터
            - sources: 각 파라미터의 출처 딕셔너리
    """
    return resolve_buffer_params(
        config.grid_results_path,
        config.override_ma_window,
        config.override_buy_buffer_zone_pct,
        config.override_sell_buffer_zone_pct,
        config.override_hold_days,
        config.override_recent_months,
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
            "recent_months": params.recent_months,
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
