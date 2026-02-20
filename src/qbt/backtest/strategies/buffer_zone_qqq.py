"""버퍼존 전략 (QQQ) 모듈

QQQ 시그널 + QQQ 매매 전략의 설정 및 실행을 담당한다.
핵심 로직은 buffer_zone_helpers에서 임포트한다.
"""

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
    BUFFER_ZONE_QQQ_RESULTS_DIR,
    QQQ_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import load_stock_data

logger = get_logger(__name__)

# 전략 식별 상수
STRATEGY_NAME = "buffer_zone_qqq"
DISPLAY_NAME = "버퍼존 전략 (QQQ)"

# 데이터 소스 경로 (버퍼존 QQQ: QQQ 시그널 + QQQ 매매, 동일 데이터)
SIGNAL_DATA_PATH = QQQ_DATA_PATH
TRADE_DATA_PATH = QQQ_DATA_PATH

# 그리드 서치 결과 파일 경로
GRID_RESULTS_PATH = BUFFER_ZONE_QQQ_RESULTS_DIR / "grid_results.csv"

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
    버퍼존 전략 (QQQ)의 파라미터를 결정한다.

    폴백 체인: OVERRIDE → grid_results.csv 최적값 → DEFAULT

    Returns:
        tuple: (params, sources)
            - params: 전략 파라미터
            - sources: 각 파라미터의 출처 딕셔너리
    """
    return resolve_buffer_params(
        GRID_RESULTS_PATH,
        OVERRIDE_MA_WINDOW,
        OVERRIDE_BUFFER_ZONE_PCT,
        OVERRIDE_HOLD_DAYS,
        OVERRIDE_RECENT_MONTHS,
    )


def run_single() -> SingleBacktestResult:
    """
    버퍼존 전략 (QQQ) 단일 백테스트를 실행한다.

    데이터 로딩부터 전략 실행까지 자체 수행한다.
    시그널과 매매 모두 QQQ 데이터를 사용한다 (동일 데이터).

    Returns:
        SingleBacktestResult: 백테스트 결과 컨테이너
    """
    # 1. 데이터 로딩 (QQQ 단일 데이터, overlap 불필요)
    trade_df = load_stock_data(TRADE_DATA_PATH)
    signal_df = trade_df.copy()

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
        result_dir=BUFFER_ZONE_QQQ_RESULTS_DIR,
        data_info={
            "signal_path": str(SIGNAL_DATA_PATH),
            "trade_path": str(TRADE_DATA_PATH),
        },
    )
