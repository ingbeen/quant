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
from datetime import date
from pathlib import Path
from typing import Any

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    FIXED_4P_BUY_BUFFER_ZONE_PCT,
    FIXED_4P_HOLD_DAYS,
    FIXED_4P_MA_WINDOW,
    FIXED_4P_SELL_BUFFER_ZONE_PCT,
    MIN_BUY_BUFFER_ZONE_PCT,
    MIN_HOLD_DAYS,
    MIN_SELL_BUFFER_ZONE_PCT,
)
from qbt.backtest.strategies.strategy_common import (
    HoldState,
    detect_buy_signal,
    detect_sell_signal,
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
# 전략 파라미터 데이터클래스
# ============================================================================


@dataclass
class BufferStrategyParams:
    """버퍼존 전략 파라미터를 담는 데이터 클래스."""

    initial_capital: float  # 초기 자본금
    ma_window: int  # 이동평균 기간 (예: 200일)
    buy_buffer_zone_pct: float  # 매수 버퍼 비율 (upper_band 기준)
    sell_buffer_zone_pct: float  # 매도 버퍼 비율 (lower_band 기준)
    hold_days: int  # 신호 확정 대기 기간 (0 = 버퍼존만 모드)


# ============================================================================
# 파라미터 결정 공통 함수
# ============================================================================


def resolve_buffer_params(
    ma_window: int,
    buy_buffer_zone_pct: float,
    sell_buffer_zone_pct: float,
    hold_days: int,
) -> tuple[BufferStrategyParams, dict[str, str]]:
    """버퍼존 전략의 파라미터를 결정한다.

    전달받은 파라미터로 BufferStrategyParams를 생성한다.

    Args:
        ma_window: 이동평균 기간
        buy_buffer_zone_pct: 매수 버퍼존 비율
        sell_buffer_zone_pct: 매도 버퍼존 비율
        hold_days: 유지일수

    Returns:
        tuple: (params, sources)
            - params: 전략 파라미터
            - sources: 각 파라미터의 출처 딕셔너리

    Raises:
        ValueError: 파라미터 범위 위반 시
    """
    if buy_buffer_zone_pct < MIN_BUY_BUFFER_ZONE_PCT:
        raise ValueError(f"buy_buffer_zone_pct는 {MIN_BUY_BUFFER_ZONE_PCT} 이상이어야 합니다: {buy_buffer_zone_pct}")
    if sell_buffer_zone_pct < MIN_SELL_BUFFER_ZONE_PCT:
        raise ValueError(f"sell_buffer_zone_pct는 {MIN_SELL_BUFFER_ZONE_PCT} 이상이어야 합니다: {sell_buffer_zone_pct}")
    if hold_days < MIN_HOLD_DAYS:
        raise ValueError(f"hold_days는 {MIN_HOLD_DAYS} 이상이어야 합니다: {hold_days}")

    params = BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=ma_window,
        buy_buffer_zone_pct=buy_buffer_zone_pct,
        sell_buffer_zone_pct=sell_buffer_zone_pct,
        hold_days=hold_days,
    )

    sources = {
        "ma_window": "FIXED",
        "buy_buffer_zone_pct": "FIXED",
        "sell_buffer_zone_pct": "FIXED",
        "hold_days": "FIXED",
    }

    logger.debug(
        f"파라미터 결정: ma_window={ma_window}, "
        f"buy_buffer={buy_buffer_zone_pct}, "
        f"sell_buffer={sell_buffer_zone_pct}, "
        f"hold_days={hold_days}"
    )

    return params, sources


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
        # 순환 import 방지를 위해 run_backtest를 지연 import한다.
        # (backtest_engine.py가 이 모듈에서 BufferStrategyParams를 import하기 때문)
        from qbt.backtest.engines.backtest_engine import run_backtest  # noqa: PLC0415

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
        trades_df, equity_df, summary = run_backtest(
            BufferZoneStrategy(), signal_df, trade_df, params, strategy_name=config.strategy_name
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


# ============================================================================
# 전략 클래스
# ============================================================================


class BufferZoneStrategy:
    """버퍼존 전략 클래스.

    SignalStrategy Protocol을 구현한다.
    check_buy에 hold_days 상태머신을 포함하고, check_sell은 하향돌파를 감지한다.

    사용 예:
        strategy = BufferZoneStrategy()
        buy, hold_state = strategy.check_buy(prev_close, cur_close, prev_upper, cur_upper, hold_state, hold_days)
        sell = strategy.check_sell(prev_close, cur_close, prev_lower, cur_lower)
    """

    def check_buy(
        self,
        prev_close: float,
        cur_close: float,
        prev_upper: float,
        cur_upper: float,
        hold_state: HoldState | None,
        hold_days_required: int,
    ) -> tuple[bool, HoldState | None]:
        """매수 신호 여부와 갱신된 HoldState를 반환한다.

        hold_days_required == 0:
            detect_buy_signal() 결과를 즉시 반환한다. (True, None)
        hold_days_required > 0:
            1. hold_state가 None이고 상향돌파 감지 시 → HoldState 생성 (False, new_hold_state)
            2. hold_state가 있고 cur_close > cur_upper 유지 시 → days_passed 증가
               hold_days_required 도달 시 → (True, None) 반환
               미달 시 → (False, 갱신 hold_state) 반환
            3. hold_state가 있고 cur_close <= cur_upper 이탈 시 → 상태 해제 (False, None)

        Args:
            prev_close: 전일 종가
            cur_close: 당일 종가
            prev_upper: 전일 상단 밴드
            cur_upper: 당일 상단 밴드
            hold_state: 현재 hold_days 상태 (None이면 대기 없음)
            hold_days_required: 신호 확정까지 대기 기간 (0 = 버퍼존만 모드)

        Returns:
            tuple: (매수 여부, 갱신된 HoldState)
        """

        if hold_days_required == 0:
            # 즉시 신호: detect_buy_signal 결과 반환
            buy = detect_buy_signal(prev_close, cur_close, prev_upper, cur_upper)
            return buy, None

        # hold_days > 0: 상태머신 처리
        if hold_state is not None:
            # 대기 중 — 상단밴드 위 유지 여부 확인
            if cur_close > cur_upper:
                new_days_passed = hold_state["days_passed"] + 1
                if new_days_passed >= hold_state["hold_days_required"]:
                    # 유지 조건 충족 → 매수 신호
                    return True, None
                else:
                    # 유지 중 — 상태 갱신
                    updated_hold_state: HoldState = {
                        "start_date": hold_state["start_date"],
                        "days_passed": new_days_passed,
                        "buffer_pct": hold_state["buffer_pct"],
                        "hold_days_required": hold_state["hold_days_required"],
                    }
                    return False, updated_hold_state
            else:
                # 상단밴드 아래로 이탈 → 상태 해제
                return False, None

        # hold_state가 None인 경우 — 상향돌파 감지
        breakout = detect_buy_signal(prev_close, cur_close, prev_upper, cur_upper)
        if breakout:
            # 상향돌파 감지 → HoldState 생성 (아직 매수 아님).
            # start_date, buffer_pct는 엔진이 실제 값으로 채워준다 (플레이스홀더 사용).
            new_hold_state: HoldState = {
                "start_date": date.min,  # 플레이스홀더: 엔진이 current_date로 덮어씀
                "days_passed": 0,
                "buffer_pct": 0.0,  # 플레이스홀더: 엔진이 params.buy_buffer_zone_pct로 덮어씀
                "hold_days_required": hold_days_required,
            }
            return False, new_hold_state

        return False, None

    def check_sell(
        self,
        prev_close: float,
        cur_close: float,
        prev_lower: float,
        cur_lower: float,
    ) -> bool:
        """매도 신호 여부를 반환한다.

        detect_sell_signal() 결과를 반환한다.

        Args:
            prev_close: 전일 종가
            cur_close: 당일 종가
            prev_lower: 전일 하단 밴드
            cur_lower: 당일 하단 밴드

        Returns:
            True이면 매도 신호 (하향돌파)
        """
        return detect_sell_signal(prev_close, cur_close, prev_lower, cur_lower)
