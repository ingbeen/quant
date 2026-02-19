"""Buy & Hold 벤치마크 전략 모듈

매수 후 보유하는 가장 기본적인 전략을 구현한다.
버퍼존 전략의 성과를 비교하기 위한 벤치마크 용도이다.
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from qbt.backtest.analysis import calculate_summary
from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    MIN_VALID_ROWS,
    SLIPPAGE_RATE,
)
from qbt.backtest.types import SingleBacktestResult, SummaryDict
from qbt.common_constants import BUY_AND_HOLD_RESULTS_DIR, COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN
from qbt.utils import get_logger

logger = get_logger(__name__)

# 전략 식별 상수
STRATEGY_NAME = "buy_and_hold"
DISPLAY_NAME = "Buy & Hold"


# ============================================================================
# 전략 전용 TypedDict (types.py에서 이동)
# ============================================================================


class BuyAndHoldResultDict(SummaryDict):
    """run_buy_and_hold() 반환 타입.

    SummaryDict를 상속하고 전략 식별자를 추가한다.
    """

    strategy: str


@dataclass
class BuyAndHoldParams:
    """Buy & Hold 전략 파라미터를 담는 데이터 클래스.

    Buy & Hold: 매수 후 그대로 보유하는 가장 기본적인 전략 (벤치마크용)
    """

    initial_capital: float  # 초기 자본금


def run_buy_and_hold(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    params: BuyAndHoldParams,
) -> tuple[pd.DataFrame, BuyAndHoldResultDict]:
    """
    Buy & Hold 벤치마크 전략을 실행한다.

    첫날 trade_df 시가에 매수 후 보유한다. 강제청산 없음 (버퍼존 전략과 동일).
    에쿼티는 trade_df 종가 기준으로 계산한다.

    Args:
        signal_df: 시그널용 DataFrame (Buy & Hold에서는 미사용, 일관성을 위해 유지)
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
    base_summary = calculate_summary(trades_df, equity_df, params.initial_capital)
    summary: BuyAndHoldResultDict = {**base_summary, "strategy": STRATEGY_NAME}

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


def run_single(signal_df: pd.DataFrame, trade_df: pd.DataFrame) -> SingleBacktestResult:
    """
    Buy & Hold 전략 단일 백테스트를 실행한다.

    Args:
        signal_df: 시그널용 DataFrame (Buy & Hold에서는 미사용)
        trade_df: 매매용 DataFrame (TQQQ)

    Returns:
        SingleBacktestResult: 백테스트 결과 컨테이너
    """
    # 1. 파라미터 결정
    params = resolve_params()

    # 2. 전략 실행
    equity_df, summary = run_buy_and_hold(signal_df, trade_df, params)

    # 3. 시그널 DataFrame 구성 (trade_df OHLC, MA 없음)
    bh_signal_df = trade_df[[COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]].copy()

    # 4. 거래 내역 (Buy & Hold는 매도 없음)
    trades_df = pd.DataFrame()

    # 5. JSON 저장용 파라미터
    params_json: dict[str, Any] = {
        "strategy": STRATEGY_NAME,
        "initial_capital": round(DEFAULT_INITIAL_CAPITAL),
    }

    return SingleBacktestResult(
        strategy_name=STRATEGY_NAME,
        display_name=DISPLAY_NAME,
        signal_df=bh_signal_df,
        equity_df=equity_df,
        trades_df=trades_df,
        summary=summary,
        params_json=params_json,
        result_dir=BUY_AND_HOLD_RESULTS_DIR,
    )
