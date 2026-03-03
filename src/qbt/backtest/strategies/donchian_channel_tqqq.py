"""Donchian Channel (TQQQ) 전략

QQQ 시그널 + TQQQ 합성 데이터 매매 Donchian Channel 전략의 설정 및 실행을 담당한다.
핵심 로직은 donchian_helpers에서 임포트한다.

전략 개요:
- 매수: QQQ 종가가 55일 최고가를 돌파하면 TQQQ 매수
- 매도: QQQ 종가가 20일 최저가를 돌파하면 TQQQ 매도
- 체결: 신호 발생 익일 시가 (slippage 적용)
"""

from typing import Any

from qbt.backtest.constants import (
    DEFAULT_ENTRY_CHANNEL_DAYS,
    DEFAULT_EXIT_CHANNEL_DAYS,
    DEFAULT_INITIAL_CAPITAL,
)
from qbt.backtest.strategies.donchian_helpers import (
    DonchianStrategyParams,
    run_donchian_strategy,
)
from qbt.backtest.types import SingleBacktestResult
from qbt.common_constants import (
    DONCHIAN_CHANNEL_TQQQ_RESULTS_DIR,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)

# ============================================================================
# 전략 식별
# ============================================================================

STRATEGY_NAME = "donchian_channel_tqqq"
DISPLAY_NAME = "Donchian Channel (TQQQ)"

# ============================================================================
# 데이터 소스 경로
# ============================================================================

SIGNAL_DATA_PATH = QQQ_DATA_PATH
TRADE_DATA_PATH = TQQQ_SYNTHETIC_DATA_PATH

# ============================================================================
# 파라미터 오버라이드 (None = DEFAULT 사용)
# ============================================================================

OVERRIDE_ENTRY_CHANNEL_DAYS: int | None = None
OVERRIDE_EXIT_CHANNEL_DAYS: int | None = None


# ============================================================================
# 파라미터 결정
# ============================================================================


def resolve_params() -> tuple[DonchianStrategyParams, dict[str, str]]:
    """파라미터를 결정한다 (OVERRIDE → DEFAULT 폴백).

    Returns:
        (params, sources) 튜플
        - params: DonchianStrategyParams
        - sources: 파라미터 출처 딕셔너리
    """
    sources: dict[str, str] = {}

    if OVERRIDE_ENTRY_CHANNEL_DAYS is not None:
        entry_days = OVERRIDE_ENTRY_CHANNEL_DAYS
        sources["entry_channel_days"] = "override"
    else:
        entry_days = DEFAULT_ENTRY_CHANNEL_DAYS
        sources["entry_channel_days"] = "default"

    if OVERRIDE_EXIT_CHANNEL_DAYS is not None:
        exit_days = OVERRIDE_EXIT_CHANNEL_DAYS
        sources["exit_channel_days"] = "override"
    else:
        exit_days = DEFAULT_EXIT_CHANNEL_DAYS
        sources["exit_channel_days"] = "default"

    params = DonchianStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        entry_channel_days=entry_days,
        exit_channel_days=exit_days,
    )

    return params, sources


# ============================================================================
# 단일 백테스트 실행
# ============================================================================


def run_single() -> SingleBacktestResult:
    """단일 백테스트를 실행하고 결과를 반환한다.

    Returns:
        SingleBacktestResult 컨테이너
    """
    # 1. 데이터 로딩
    signal_df = load_stock_data(SIGNAL_DATA_PATH)
    trade_df = load_stock_data(TRADE_DATA_PATH)
    signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    # 2. 파라미터 결정
    params, sources = resolve_params()

    logger.debug(
        f"[{STRATEGY_NAME}] 파라미터: "
        f"entry_channel_days={params.entry_channel_days}, "
        f"exit_channel_days={params.exit_channel_days}, "
        f"initial_capital={params.initial_capital:.0f}"
    )

    # 3. 전략 실행
    trades_df, equity_df, summary = run_donchian_strategy(
        signal_df=signal_df,
        trade_df=trade_df,
        params=params,
        strategy_name=STRATEGY_NAME,
    )

    # 4. 파라미터 JSON 구성
    params_json: dict[str, Any] = {
        "entry_channel_days": params.entry_channel_days,
        "exit_channel_days": params.exit_channel_days,
        "initial_capital": round(DEFAULT_INITIAL_CAPITAL),
        "param_source": sources,
    }

    # 5. 결과 컨테이너 반환
    return SingleBacktestResult(
        strategy_name=STRATEGY_NAME,
        display_name=DISPLAY_NAME,
        signal_df=signal_df,
        equity_df=equity_df,
        trades_df=trades_df,
        summary=summary,
        params_json=params_json,
        result_dir=DONCHIAN_CHANNEL_TQQQ_RESULTS_DIR,
        data_info={
            "signal_path": str(SIGNAL_DATA_PATH),
            "trade_path": str(TRADE_DATA_PATH),
        },
    )
