"""백테스트 분석 모듈

이동평균 계산 및 성과 지표 계산 기능을 제공한다.
"""

import pandas as pd

from qbt.common_constants import ANNUAL_DAYS, COL_CLOSE, COL_DATE
from qbt.utils import get_logger

logger = get_logger(__name__)


def add_single_moving_average(
    df: pd.DataFrame,
    window: int,
    ma_type: str = "sma",
) -> pd.DataFrame:
    """
    지정된 기간의 이동평균을 계산하여 컬럼으로 추가한다.

    Args:
        df: 주식 데이터 DataFrame (Close 컬럼 필수)
        window: 이동평균 기간
        ma_type: 이동평균 유형 ("sma" 또는 "ema", 기본값: "sma")

    Returns:
        이동평균 컬럼이 추가된 DataFrame (원본 복사본)

    Raises:
        ValueError: window < 1인 경우
    """
    if window < 1:
        raise ValueError(f"window는 1 이상이어야 합니다: {window}")

    logger.debug(f"이동평균 계산: window={window}, type={ma_type}")

    # DataFrame 복사 (원본 보존)
    df = df.copy()

    # 컬럼명 설정
    col_name = f"ma_{window}"

    # 이동평균 계산
    if ma_type == "sma":
        df[col_name] = df[COL_CLOSE].rolling(window=window).mean()
    elif ma_type == "ema":
        df[col_name] = df[COL_CLOSE].ewm(span=window, adjust=False).mean()
    else:
        raise ValueError(f"지원하지 않는 ma_type: {ma_type}")

    # 유효 데이터 수 확인
    valid_rows = df[col_name].notna().sum()
    logger.debug(f"이동평균 계산 완료: 유효 데이터 {valid_rows:,}행 (전체 {len(df):,}행)")

    return df


def calculate_summary(
    trades_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    initial_capital: float,
) -> dict:
    """
    거래 내역과 자본 곡선으로 요약 지표를 계산한다.

    Args:
        trades_df: 거래 내역 DataFrame
        equity_df: 자본 곡선 DataFrame
        initial_capital: 초기 자본금

    Returns:
        요약 지표 딕셔너리
    """
    if equity_df.empty:
        return {
            "initial_capital": initial_capital,
            "final_capital": initial_capital,
            "total_return": 0.0,
            "total_return_pct": 0.0,
            "cagr": 0.0,
            "mdd": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
        }

    final_capital = equity_df.iloc[-1]["equity"]
    total_return = final_capital - initial_capital
    total_return_pct = (total_return / initial_capital) * 100

    # 기간 계산
    start_date = pd.to_datetime(equity_df.iloc[0][COL_DATE])
    end_date = pd.to_datetime(equity_df.iloc[-1][COL_DATE])
    years = (end_date - start_date).days / ANNUAL_DAYS

    # CAGR
    if years > 0 and final_capital > 0:
        cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
    else:
        cagr = 0.0

    # MDD 계산
    equity_df = equity_df.copy()
    equity_df["peak"] = equity_df["equity"].cummax()
    equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"]
    mdd = equity_df["drawdown"].min() * 100

    # 거래 통계
    total_trades = len(trades_df)
    if total_trades > 0:
        winning_trades = len(trades_df[trades_df["pnl"] > 0])
        losing_trades = len(trades_df[trades_df["pnl"] <= 0])
        win_rate = (winning_trades / total_trades) * 100
    else:
        winning_trades = 0
        losing_trades = 0
        win_rate = 0.0

    return {
        "initial_capital": initial_capital,
        "final_capital": final_capital,
        "total_return": total_return,
        "total_return_pct": total_return_pct,
        "cagr": cagr,
        "mdd": mdd,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "start_date": str(equity_df.iloc[0][COL_DATE]),
        "end_date": str(equity_df.iloc[-1][COL_DATE]),
    }
