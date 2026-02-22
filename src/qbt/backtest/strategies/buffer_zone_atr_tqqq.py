"""버퍼존 ATR 전략 (TQQQ) 모듈

QQQ 시그널 + TQQQ 합성 데이터 매매 전략에 ATR 트레일링 스탑을 추가한 설정 및 실행을 담당한다.
핵심 로직은 buffer_zone_helpers에서 임포트한다.

매도 조건: 하단밴드 하향돌파 OR ATR 트레일링 스탑 (둘 중 먼저 걸리는 쪽)
ATR 시그널 소스: QQQ (signal_df) 고정
ATR 기준가: highest_close_since_entry (매수 후 최고 종가) 고정
"""

from typing import Any

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import (
    DEFAULT_ATR_MULTIPLIER,
    DEFAULT_ATR_PERIOD,
    DEFAULT_INITIAL_CAPITAL,
)
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    resolve_buffer_params,
    run_buffer_strategy,
)
from qbt.backtest.types import SingleBacktestResult
from qbt.common_constants import (
    BUFFER_ZONE_ATR_TQQQ_RESULTS_DIR,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)

# 전략 식별 상수
STRATEGY_NAME = "buffer_zone_atr_tqqq"
DISPLAY_NAME = "버퍼존 전략 ATR (TQQQ)"

# 데이터 소스 경로 (QQQ 시그널 + TQQQ 합성 매매)
SIGNAL_DATA_PATH = QQQ_DATA_PATH
TRADE_DATA_PATH = TQQQ_SYNTHETIC_DATA_PATH

# 그리드 서치 결과 파일 경로
GRID_RESULTS_PATH = BUFFER_ZONE_ATR_TQQQ_RESULTS_DIR / "grid_results.csv"

# 파라미터 오버라이드 (None = grid_results.csv 최적값 사용, 값 설정 = 수동)
# 폴백 체인: OVERRIDE → grid_results.csv 최적값 → DEFAULT
OVERRIDE_MA_WINDOW: int | None = None
OVERRIDE_BUY_BUFFER_ZONE_PCT: float | None = None
OVERRIDE_SELL_BUFFER_ZONE_PCT: float | None = None
OVERRIDE_HOLD_DAYS: int | None = None
OVERRIDE_RECENT_MONTHS: int | None = None

# ATR 파라미터 오버라이드 (None = DEFAULT 사용)
OVERRIDE_ATR_PERIOD: int | None = None
OVERRIDE_ATR_MULTIPLIER: float | None = None

# MA 유형 (grid_search와 동일하게 EMA 사용)
MA_TYPE = "ema"


def resolve_params() -> tuple[BufferStrategyParams, dict[str, str]]:
    """
    버퍼존 ATR 전략 (TQQQ)의 파라미터를 결정한다.

    폴백 체인: OVERRIDE → grid_results.csv 최적값 → DEFAULT
    ATR 파라미터: OVERRIDE → DEFAULT

    Returns:
        tuple: (params, sources)
            - params: 전략 파라미터 (ATR 포함)
            - sources: 각 파라미터의 출처 딕셔너리
    """
    params, sources = resolve_buffer_params(
        GRID_RESULTS_PATH,
        OVERRIDE_MA_WINDOW,
        OVERRIDE_BUY_BUFFER_ZONE_PCT,
        OVERRIDE_SELL_BUFFER_ZONE_PCT,
        OVERRIDE_HOLD_DAYS,
        OVERRIDE_RECENT_MONTHS,
    )

    # ATR 파라미터 결정
    if OVERRIDE_ATR_PERIOD is not None:
        atr_period = OVERRIDE_ATR_PERIOD
        sources["atr_period"] = "OVERRIDE"
    else:
        atr_period = DEFAULT_ATR_PERIOD
        sources["atr_period"] = "DEFAULT"

    if OVERRIDE_ATR_MULTIPLIER is not None:
        atr_multiplier = OVERRIDE_ATR_MULTIPLIER
        sources["atr_multiplier"] = "OVERRIDE"
    else:
        atr_multiplier = DEFAULT_ATR_MULTIPLIER
        sources["atr_multiplier"] = "DEFAULT"

    # ATR 필드가 포함된 새 params 생성
    params = BufferStrategyParams(
        initial_capital=params.initial_capital,
        ma_window=params.ma_window,
        buy_buffer_zone_pct=params.buy_buffer_zone_pct,
        sell_buffer_zone_pct=params.sell_buffer_zone_pct,
        hold_days=params.hold_days,
        recent_months=params.recent_months,
        atr_period=atr_period,
        atr_multiplier=atr_multiplier,
    )

    return params, sources


def run_single() -> SingleBacktestResult:
    """
    버퍼존 ATR 전략 (TQQQ) 단일 백테스트를 실행한다.

    데이터 로딩부터 전략 실행까지 자체 수행한다.
    시그널은 QQQ, 매매는 TQQQ 합성 데이터를 사용한다.
    매도 조건: 하단밴드 하향돌파 OR ATR 트레일링 스탑

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
        "buy_buffer_zone_pct": round(params.buy_buffer_zone_pct, 4),
        "sell_buffer_zone_pct": round(params.sell_buffer_zone_pct, 4),
        "hold_days": params.hold_days,
        "recent_months": params.recent_months,
        "atr_period": params.atr_period,
        "atr_multiplier": params.atr_multiplier,
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
        result_dir=BUFFER_ZONE_ATR_TQQQ_RESULTS_DIR,
        data_info={
            "signal_path": str(SIGNAL_DATA_PATH),
            "trade_path": str(TRADE_DATA_PATH),
        },
    )
