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

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import (
    COL_LOWER_BAND,
    COL_UPPER_BAND,
    DEFAULT_INITIAL_CAPITAL,
    ma_col_name,
)
from qbt.backtest.engines.backtest_engine import run_backtest
from qbt.backtest.strategies.buffer_zone import (
    BufferZoneConfig,
    BufferZoneStrategy,
    resolve_params_for_config,
)
from qbt.backtest.strategies.buffer_zone_helpers import compute_bands
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldConfig, BuyAndHoldStrategy
from qbt.backtest.types import SingleBacktestResult
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import load_signal_trade_pair, load_stock_data

logger = get_logger(__name__)


# ============================================================================
# 내부 헬퍼
# ============================================================================


def _enrich_equity_with_bands(
    equity_df: pd.DataFrame,
    signal_df: pd.DataFrame,
    ma_col: str,
    buy_buffer_pct: float,
    sell_buffer_pct: float,
) -> pd.DataFrame:
    """equity_df에 버퍼존 밴드 컬럼을 추가한다.

    signal_df의 MA 값으로 upper_band, lower_band, buy_buffer_pct, sell_buffer_pct 컬럼을
    equity_df에 Date 기준으로 join하여 추가한다.
    대시보드에서 밴드 오버레이 표시에 사용된다.

    Args:
        equity_df: 기본 에쿼티 DataFrame (Date, equity, position 컬럼)
        signal_df: 시그널 DataFrame (MA 컬럼 포함)
        ma_col: 이동평균 컬럼명 (예: "ma_200")
        buy_buffer_pct: 매수 버퍼존 비율 (0~1)
        sell_buffer_pct: 매도 버퍼존 비율 (0~1)

    Returns:
        밴드 컬럼이 추가된 equity_df
    """
    # signal_df에서 Date, MA 컬럼만 추출 후 밴드 계산
    band_df = signal_df[[COL_DATE, ma_col]].copy()
    band_df[COL_UPPER_BAND] = band_df[ma_col].apply(lambda ma: compute_bands(ma, buy_buffer_pct, sell_buffer_pct)[0])
    band_df[COL_LOWER_BAND] = band_df[ma_col].apply(lambda ma: compute_bands(ma, buy_buffer_pct, sell_buffer_pct)[1])
    band_df["buy_buffer_pct"] = buy_buffer_pct
    band_df["sell_buffer_pct"] = sell_buffer_pct
    band_df = band_df.drop(columns=[ma_col])

    # equity_df에 Date 기준으로 join
    enriched = equity_df.merge(band_df, on=COL_DATE, how="left")
    return enriched


# ============================================================================
# 팩토리 함수
# ============================================================================


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
        signal_df, trade_df = load_signal_trade_pair(config.signal_data_path, config.trade_data_path)

        # 2. 파라미터 결정
        params, sources = resolve_params_for_config(config)
        ma_col = ma_col_name(params.ma_window)

        # 3. 이동평균 계산
        signal_df = add_single_moving_average(signal_df, params.ma_window, ma_type=config.ma_type)

        # 4. MA 유효 구간 필터링
        valid_mask = signal_df[ma_col].notna()
        filtered_signal = signal_df[valid_mask].reset_index(drop=True)
        filtered_trade = trade_df[valid_mask].reset_index(drop=True)

        # 5. 전략 생성 및 실행
        strategy = BufferZoneStrategy(
            ma_col=ma_col,
            buy_buffer_pct=params.buy_buffer_zone_pct,
            sell_buffer_pct=params.sell_buffer_zone_pct,
            hold_days=params.hold_days,
        )
        trades_df, equity_df, summary = run_backtest(
            strategy,
            filtered_signal,
            filtered_trade,
            params.initial_capital,
            strategy_name=config.strategy_name,
        )

        # 6. equity_df에 밴드 컬럼 post-processing으로 보강
        equity_df = _enrich_equity_with_bands(
            equity_df,
            filtered_signal,
            ma_col,
            params.buy_buffer_zone_pct,
            params.sell_buffer_zone_pct,
        )

        # 7. JSON 저장용 파라미터
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
            signal_df=filtered_signal,
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
        첫 매수 시점은 시계열 2번째 날 시가 (Day 0에서 신호 → Day 1에서 체결).

        Returns:
            SingleBacktestResult: 백테스트 결과 컨테이너
        """
        # 1. 데이터 로딩
        trade_df = load_stock_data(config.trade_data_path)
        signal_df = trade_df.copy()

        # 2. 전략 생성 및 실행 (MA 계산/필터링 불필요)
        strategy = BuyAndHoldStrategy()
        trades_df, equity_df, summary = run_backtest(
            strategy,
            signal_df,
            trade_df,
            DEFAULT_INITIAL_CAPITAL,
            strategy_name=config.strategy_name,
        )

        # 3. 시그널 DataFrame: trade_df OHLC만 추출 (MA 컬럼 없음)
        bh_signal_df = trade_df[[COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]].copy()

        # 4. JSON 저장용 파라미터
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
