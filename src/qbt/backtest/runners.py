"""백테스트 전략 러너 팩토리 모듈

전략 설정(Config)을 받아 실행 가능한 Callable을 반환하는 팩토리 함수를 제공한다.

역할 분리:
- buffer_zone.py / buy_and_hold.py: 전략 클래스 + 설정 데이터클래스 + CONFIGS 목록
- runners.py: 데이터 로딩 + MA 계산 + 전략 실행 로직 (팩토리)

순환 의존성 해결:
- 기존: buffer_zone.py가 run_backtest를 deferred import (순환 방지 목적)
  backtest_engine.py → buffer_zone.py (BufferStrategyParams)
  buffer_zone.create_runner → backtest_engine.py (run_backtest)   [deferred]
- 변경: runners.py가 두 모듈을 모두 top-level로 import (순환 없음)
  runners.py → backtest_engine.py (run_backtest)
  runners.py → buffer_zone.py (BufferZoneStrategy, ...)
  runners.py → buy_and_hold.py (BuyAndHoldStrategy, ...)
  backtest_engine.py → types.py (BufferStrategyParams)            [순환 아님]
  buffer_zone.py: backtest_engine 관련 import 없음
"""

from collections.abc import Callable
from typing import Any

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import (
    DEFAULT_BUFFER_MA_TYPE,
    DEFAULT_INITIAL_CAPITAL,
    MIN_BUY_BUFFER_ZONE_PCT,
    MIN_SELL_BUFFER_ZONE_PCT,
)
from qbt.backtest.engines.backtest_engine import run_backtest
from qbt.backtest.strategies.buffer_zone import (
    BufferZoneConfig,
    BufferZoneStrategy,
    resolve_params_for_config,
)
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldConfig, BuyAndHoldStrategy
from qbt.backtest.types import BufferStrategyParams, SingleBacktestResult
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)


def create_buffer_zone_runner(config: BufferZoneConfig) -> Callable[[], SingleBacktestResult]:
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


def create_buy_and_hold_runner(config: BuyAndHoldConfig) -> Callable[[], SingleBacktestResult]:
    """BuyAndHoldConfig에 대한 run_single 실행 함수를 생성한다.

    팩토리 패턴: config별로 데이터 소스와 결과 경로가 다른 실행 함수를 반환한다.
    엔진 기반(run_backtest + BuyAndHoldStrategy)으로 실행한다.

    Args:
        config: Buy & Hold 전략 설정 (티커별)

    Returns:
        Callable: 인자 없이 호출 가능한 run_single 함수
    """

    def run_single() -> SingleBacktestResult:
        """Buy & Hold 전략 단일 백테스트를 실행한다.

        엔진 기반(run_backtest + BuyAndHoldStrategy)으로 실행한다.
        첫 매수 시점은 MA 워밍업 이후 day 2 시가 (버퍼존과 동일한 엔진 규칙 적용).

        Returns:
            SingleBacktestResult: 백테스트 결과 컨테이너
        """
        # 1. 데이터 로딩
        trade_df = load_stock_data(config.trade_data_path)
        signal_df = trade_df.copy()

        # 2. dummy BufferStrategyParams 생성 (BuyAndHoldStrategy는 파라미터 무시)
        #    ma_window=1: EMA-1 = 종가 자체 (NaN 없음), buy/sell_buffer=MIN (0에 가장 근접한 유효값)
        dummy_params = BufferStrategyParams(
            initial_capital=DEFAULT_INITIAL_CAPITAL,
            ma_window=1,
            buy_buffer_zone_pct=MIN_BUY_BUFFER_ZONE_PCT,
            sell_buffer_zone_pct=MIN_SELL_BUFFER_ZONE_PCT,
            hold_days=0,
        )

        # 3. MA 사전 계산 (ma_window=1)
        signal_df = add_single_moving_average(signal_df, dummy_params.ma_window, ma_type=DEFAULT_BUFFER_MA_TYPE)

        # 4. 전략 실행
        trades_df, equity_df, summary = run_backtest(
            BuyAndHoldStrategy(),
            signal_df,
            trade_df,
            dummy_params,
            strategy_name=config.strategy_name,
        )

        # 5. 시그널 DataFrame: trade_df OHLC만 추출 (ma 컬럼 제외)
        bh_signal_df = trade_df[[COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]].copy()

        # 6. JSON 저장용 파라미터 (dummy MA 파라미터 노출 안 함)
        params_json: dict[str, Any] = {
            "strategy": config.strategy_name,
            "initial_capital": round(DEFAULT_INITIAL_CAPITAL),
        }

        return SingleBacktestResult(
            strategy_name=config.strategy_name,
            display_name=config.display_name,
            signal_df=bh_signal_df,
            equity_df=equity_df,
            trades_df=trades_df,
            summary=summary,
            params_json=params_json,
            result_dir=config.result_dir,
            data_info={
                "trade_path": str(config.trade_data_path),
            },
        )

    return run_single
