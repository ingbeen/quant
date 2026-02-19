"""Buy & Hold 벤치마크 전략 모듈

매수 후 보유하는 가장 기본적인 전략을 구현한다.
버퍼존 전략의 성과를 비교하기 위한 벤치마크 용도이다.
"""

from dataclasses import dataclass

import pandas as pd

from qbt.backtest.analysis import calculate_summary
from qbt.backtest.constants import (
    MIN_VALID_ROWS,
    SLIPPAGE_RATE,
)
from qbt.backtest.types import BuyAndHoldResultDict
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN
from qbt.utils import get_logger

logger = get_logger(__name__)


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
    summary: BuyAndHoldResultDict = {**base_summary, "strategy": "buy_and_hold"}

    logger.debug(f"Buy & Hold 완료: 총 수익률={summary['total_return_pct']:.2f}%, CAGR={summary['cagr']:.2f}%")

    return equity_df, summary
