"""버퍼존 전략 (TQQQ) 모듈

QQQ 시그널 + TQQQ 합성 데이터 매매 전략의 설정 및 실행을 담당한다.
핵심 로직은 buffer_zone_helpers에서 임포트한다.
"""

from typing import Any

from qbt.backtest.analysis import add_single_moving_average, load_best_grid_params
from qbt.backtest.constants import (
    DEFAULT_BUFFER_ZONE_PCT,
    DEFAULT_HOLD_DAYS,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MA_WINDOW,
    DEFAULT_RECENT_MONTHS,
)
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    run_buffer_strategy,
)
from qbt.backtest.types import SingleBacktestResult
from qbt.common_constants import (
    BUFFER_ZONE_TQQQ_RESULTS_DIR,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)

# 전략 식별 상수
STRATEGY_NAME = "buffer_zone_tqqq"
DISPLAY_NAME = "버퍼존 전략 (TQQQ)"

# 데이터 소스 경로 (버퍼존 TQQQ: QQQ 시그널 + TQQQ 합성 매매)
SIGNAL_DATA_PATH = QQQ_DATA_PATH
TRADE_DATA_PATH = TQQQ_SYNTHETIC_DATA_PATH

# 그리드 서치 결과 파일 경로
GRID_RESULTS_PATH = BUFFER_ZONE_TQQQ_RESULTS_DIR / "grid_results.csv"

# 파라미터 오버라이드 (None = grid_results.csv 최적값 사용, 값 설정 = 수동)
# 폴백 체인: OVERRIDE → grid_results.csv 최적값 → DEFAULT
OVERRIDE_MA_WINDOW: int | None = None
OVERRIDE_BUFFER_ZONE_PCT: float | None = None
OVERRIDE_HOLD_DAYS: int | None = None
OVERRIDE_RECENT_MONTHS: int | None = None

# MA 유형 (grid_search와 동일하게 EMA 사용)
MA_TYPE = "ema"


def resolve_params() -> tuple[BufferStrategyParams, dict[str, str]]:
    """
    버퍼존 전략 (TQQQ)의 파라미터를 결정한다.

    폴백 체인: OVERRIDE → grid_results.csv 최적값 → DEFAULT

    Returns:
        tuple: (params, sources)
            - params: 전략 파라미터
            - sources: 각 파라미터의 출처 딕셔너리
    """
    grid_params = load_best_grid_params(GRID_RESULTS_PATH)

    if grid_params is not None:
        logger.debug(f"grid_results.csv 최적값 로드 완료: {GRID_RESULTS_PATH}")
    else:
        logger.debug("grid_results.csv 없음, DEFAULT 상수 사용")

    # 1. ma_window
    if OVERRIDE_MA_WINDOW is not None:
        ma_window = OVERRIDE_MA_WINDOW
        ma_window_source = "OVERRIDE"
    elif grid_params is not None:
        ma_window = grid_params["ma_window"]
        ma_window_source = "grid_best"
    else:
        ma_window = DEFAULT_MA_WINDOW
        ma_window_source = "DEFAULT"

    # 2. buffer_zone_pct
    if OVERRIDE_BUFFER_ZONE_PCT is not None:
        buffer_zone_pct = OVERRIDE_BUFFER_ZONE_PCT
        bz_source = "OVERRIDE"
    elif grid_params is not None:
        buffer_zone_pct = grid_params["buffer_zone_pct"]
        bz_source = "grid_best"
    else:
        buffer_zone_pct = DEFAULT_BUFFER_ZONE_PCT
        bz_source = "DEFAULT"

    # 3. hold_days
    if OVERRIDE_HOLD_DAYS is not None:
        hold_days = OVERRIDE_HOLD_DAYS
        hd_source = "OVERRIDE"
    elif grid_params is not None:
        hold_days = grid_params["hold_days"]
        hd_source = "grid_best"
    else:
        hold_days = DEFAULT_HOLD_DAYS
        hd_source = "DEFAULT"

    # 4. recent_months
    if OVERRIDE_RECENT_MONTHS is not None:
        recent_months = OVERRIDE_RECENT_MONTHS
        rm_source = "OVERRIDE"
    elif grid_params is not None:
        recent_months = grid_params["recent_months"]
        rm_source = "grid_best"
    else:
        recent_months = DEFAULT_RECENT_MONTHS
        rm_source = "DEFAULT"

    params = BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=ma_window,
        buffer_zone_pct=buffer_zone_pct,
        hold_days=hold_days,
        recent_months=recent_months,
    )

    sources = {
        "ma_window": ma_window_source,
        "buffer_zone_pct": bz_source,
        "hold_days": hd_source,
        "recent_months": rm_source,
    }

    logger.debug(
        f"파라미터 결정: ma_window={ma_window} ({ma_window_source}), "
        f"buffer_zone={buffer_zone_pct} ({bz_source}), "
        f"hold_days={hold_days} ({hd_source}), "
        f"recent_months={recent_months} ({rm_source})"
    )

    return params, sources


def run_single() -> SingleBacktestResult:
    """
    버퍼존 전략 (TQQQ) 단일 백테스트를 실행한다.

    데이터 로딩부터 전략 실행까지 자체 수행한다.
    시그널은 QQQ, 매매는 TQQQ 합성 데이터를 사용한다.

    Returns:
        SingleBacktestResult: 백테스트 결과 컨테이너
    """
    # 1. 데이터 로딩
    signal_df = load_stock_data(SIGNAL_DATA_PATH)
    trade_df = load_stock_data(TRADE_DATA_PATH)
    signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    # 2. 파라미터 결정
    params, sources = resolve_params()

    # 3. 이동평균 계산
    signal_df = add_single_moving_average(signal_df, params.ma_window, ma_type=MA_TYPE)

    # 4. 전략 실행
    trades_df, equity_df, summary = run_buffer_strategy(signal_df, trade_df, params, strategy_name=STRATEGY_NAME)

    # 5. JSON 저장용 파라미터
    params_json: dict[str, Any] = {
        "ma_window": params.ma_window,
        "ma_type": MA_TYPE,
        "buffer_zone_pct": round(params.buffer_zone_pct, 4),
        "hold_days": params.hold_days,
        "recent_months": params.recent_months,
        "initial_capital": round(DEFAULT_INITIAL_CAPITAL),
        "param_source": sources,
    }

    return SingleBacktestResult(
        strategy_name=STRATEGY_NAME,
        display_name=DISPLAY_NAME,
        signal_df=signal_df,
        equity_df=equity_df,
        trades_df=trades_df,
        summary=summary,
        params_json=params_json,
        result_dir=BUFFER_ZONE_TQQQ_RESULTS_DIR,
        data_info={
            "signal_path": str(SIGNAL_DATA_PATH),
            "trade_path": str(TRADE_DATA_PATH),
        },
    )
