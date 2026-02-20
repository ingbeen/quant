"""Buy & Hold 벤치마크 전략 모듈

매수 후 보유하는 가장 기본적인 전략을 구현한다.
버퍼존 전략의 성과를 비교하기 위한 벤치마크 용도이다.

팩토리 패턴:
    BuyAndHoldConfig로 티커별 설정을 정의하고,
    create_runner()로 각 설정에 대한 실행 함수를 생성한다.
    CONFIGS 리스트에 티커를 추가하면 자동으로 전략이 확장된다.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from qbt.backtest.analysis import calculate_summary
from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    MIN_VALID_ROWS,
    SLIPPAGE_RATE,
)
from qbt.backtest.types import SingleBacktestResult, SummaryDict
from qbt.common_constants import (
    BUY_AND_HOLD_QQQ_RESULTS_DIR,
    BUY_AND_HOLD_TQQQ_RESULTS_DIR,
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import load_stock_data

logger = get_logger(__name__)


# ============================================================================
# 설정 데이터클래스 및 팩토리
# ============================================================================


@dataclass(frozen=True)
class BuyAndHoldConfig:
    """Buy & Hold 전략의 티커별 설정.

    각 티커(QQQ, TQQQ 등)에 대한 전략 식별 정보와 데이터 경로를 담는다.
    CONFIGS 리스트에 추가하면 자동으로 전략 레지스트리에 등록된다.
    """

    strategy_name: str  # 전략 내부 식별자 (예: "buy_and_hold_qqq")
    display_name: str  # 전략 표시명 (예: "Buy & Hold (QQQ)")
    trade_data_path: Path  # 매매용 데이터 경로
    result_dir: Path  # 결과 저장 디렉토리


# 티커별 설정 목록 (새 티커 추가 시 여기에 한 줄 추가)
CONFIGS: list[BuyAndHoldConfig] = [
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_qqq",
        display_name="Buy & Hold (QQQ)",
        trade_data_path=QQQ_DATA_PATH,
        result_dir=BUY_AND_HOLD_QQQ_RESULTS_DIR,
    ),
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_tqqq",
        display_name="Buy & Hold (TQQQ)",
        trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
        result_dir=BUY_AND_HOLD_TQQQ_RESULTS_DIR,
    ),
]


# ============================================================================
# 파라미터 데이터클래스
# ============================================================================


@dataclass
class BuyAndHoldParams:
    """Buy & Hold 전략 파라미터를 담는 데이터 클래스.

    Buy & Hold: 매수 후 그대로 보유하는 가장 기본적인 전략 (벤치마크용)
    """

    initial_capital: float  # 초기 자본금


# ============================================================================
# 핵심 전략 로직
# ============================================================================


def run_buy_and_hold(
    trade_df: pd.DataFrame,
    params: BuyAndHoldParams,
) -> tuple[pd.DataFrame, SummaryDict]:
    """
    Buy & Hold 벤치마크 전략을 실행한다.

    첫날 trade_df 시가에 매수 후 보유한다. 강제청산 없음 (버퍼존 전략과 동일).
    에쿼티는 trade_df 종가 기준으로 계산한다.

    Args:
        trade_df: 매매용 DataFrame (체결가: Open, 에쿼티: Close)
        params: Buy & Hold 파라미터

    Returns:
        tuple: (equity_df, summary)
            - equity_df: 자본 곡선 DataFrame
            - summary: 요약 지표 딕셔너리
    """
    # 1. 파라미터 검증
    if params.initial_capital <= 0:
        raise ValueError(f"initial_capital은 양수여야 합니다: {params.initial_capital}")

    # 2. trade_df 필수 컬럼 검증
    required_cols = [COL_OPEN, COL_CLOSE, COL_DATE]
    missing = set(required_cols) - set(trade_df.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 3. 최소 행 수 검증
    if len(trade_df) < MIN_VALID_ROWS:
        raise ValueError(f"유효 데이터 부족: {len(trade_df)}행 (최소 {MIN_VALID_ROWS}행 필요)")

    logger.debug("Buy & Hold 실행 시작")

    trade_df = trade_df.copy()

    # 4. 첫날 trade_df 시가에 매수
    buy_price_raw = trade_df.iloc[0][COL_OPEN]
    buy_price = buy_price_raw * (1 + SLIPPAGE_RATE)

    shares = int(params.initial_capital / buy_price)
    buy_amount = shares * buy_price
    capital_after_buy = params.initial_capital - buy_amount

    # 5. 자본 곡선 계산 (trade_df 종가 기준)
    equity_records: list[dict[str, object]] = []

    for _, row in trade_df.iterrows():
        equity = capital_after_buy + shares * row[COL_CLOSE]
        equity_records.append({COL_DATE: row[COL_DATE], "equity": equity, "position": shares})

    equity_df = pd.DataFrame(equity_records)

    # 6. 강제청산 없음 (버퍼존 전략과 동일 정책)
    trades_df = pd.DataFrame()

    # 7. calculate_summary 호출
    summary = calculate_summary(trades_df, equity_df, params.initial_capital)

    logger.debug(f"Buy & Hold 완료: 총 수익률={summary['total_return_pct']:.2f}%, CAGR={summary['cagr']:.2f}%")

    return equity_df, summary


def resolve_params() -> BuyAndHoldParams:
    """
    Buy & Hold 전략의 파라미터를 결정한다.

    Returns:
        BuyAndHoldParams: 전략 파라미터 (항상 DEFAULT_INITIAL_CAPITAL 사용)
    """
    params = BuyAndHoldParams(initial_capital=DEFAULT_INITIAL_CAPITAL)

    logger.debug(f"Buy & Hold 파라미터 결정: initial_capital={DEFAULT_INITIAL_CAPITAL}")

    return params


# ============================================================================
# 팩토리 함수
# ============================================================================


def create_runner(config: BuyAndHoldConfig) -> Callable[[], SingleBacktestResult]:
    """
    BuyAndHoldConfig에 대한 run_single 실행 함수를 생성한다.

    팩토리 패턴: config별로 데이터 소스와 결과 경로가 다른 실행 함수를 반환한다.

    Args:
        config: Buy & Hold 전략 설정 (티커별)

    Returns:
        Callable: 인자 없이 호출 가능한 run_single 함수
    """

    def run_single() -> SingleBacktestResult:
        """
        Buy & Hold 전략 단일 백테스트를 실행한다.

        데이터 로딩부터 전략 실행까지 자체 수행한다.
        Buy & Hold는 signal과 trade가 동일한 데이터를 사용한다.

        Returns:
            SingleBacktestResult: 백테스트 결과 컨테이너
        """
        # 1. 데이터 로딩
        trade_df = load_stock_data(config.trade_data_path)

        # 2. 파라미터 결정
        params = resolve_params()

        # 3. 전략 실행
        equity_df, summary = run_buy_and_hold(trade_df, params)

        # 4. 시그널 DataFrame 구성 (trade_df OHLC, MA 없음)
        bh_signal_df = trade_df[[COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]].copy()

        # 5. 거래 내역 (Buy & Hold는 매도 없음)
        trades_df = pd.DataFrame()

        # 6. JSON 저장용 파라미터
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
