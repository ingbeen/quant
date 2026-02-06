"""백테스트 분석 모듈

이동평균 계산 및 성과 지표 계산 기능을 제공한다.

학습 포인트:
1. 이동평균(Moving Average): 일정 기간의 가격 평균을 계산하여 추세 파악
2. SMA (Simple MA): 단순 평균, EMA (Exponential MA): 최근 데이터에 가중치
3. CAGR: 연평균 복리 성장률 - 투자 성과를 연 단위로 환산
4. MDD: 최대 낙폭 - 최고점 대비 최대 하락 비율
"""

import pandas as pd

from qbt.backtest.types import SummaryDict
from qbt.common_constants import ANNUAL_DAYS, COL_CLOSE, COL_DATE, EPSILON
from qbt.utils import get_logger

logger = get_logger(__name__)


def add_single_moving_average(
    df: pd.DataFrame,
    window: int,
    ma_type: str = "sma",
) -> pd.DataFrame:
    """
    지정된 기간의 이동평균을 계산하여 컬럼으로 추가한다.

    학습 포인트:
    1. .rolling(window=N): N개 행의 이동 윈도우 생성
    2. .mean(): 각 윈도우의 평균 계산
    3. .ewm(): 지수 가중 이동평균 (최근 데이터에 더 큰 가중치)
    4. .notna(): NaN이 아닌 값 체크 (True/False)

    Args:
        df: 주식 데이터 DataFrame (Close 컬럼 필수)
        window: 이동평균 기간 (예: 20 = 20일 이동평균)
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
    # .copy(): 원본 데이터를 변경하지 않도록 복사본 생성
    df = df.copy()

    # 컬럼명 설정
    # f-string으로 동적 컬럼명 생성 (예: "ma_20", "ma_50")
    col_name = f"ma_{window}"

    # 이동평균 계산
    if ma_type == "sma":
        # SMA (Simple Moving Average): 단순 이동평균
        # .rolling(window=20): 20개 행씩 묶어 이동 윈도우 생성
        # .mean(): 각 윈도우의 평균 계산
        # 예: [1,2,3,4,5]에서 window=3 → [NaN, NaN, 2, 3, 4]
        df[col_name] = df[COL_CLOSE].rolling(window=window).mean()
    elif ma_type == "ema":
        # EMA (Exponential Moving Average): 지수 이동평균
        # .ewm(): 지수 가중 이동평균 (최근 데이터에 더 큰 가중치)
        # span: EMA 기간, adjust=False: 표준 EMA 공식 사용
        df[col_name] = df[COL_CLOSE].ewm(span=window, adjust=False).mean()
    else:
        raise ValueError(f"지원하지 않는 ma_type: {ma_type}")

    # 유효 데이터 수 확인
    # .notna(): NaN이 아닌 값 확인 (True/False Series 반환)
    # .sum(): True를 1로 세어 합계 (유효 데이터 개수)
    valid_rows = df[col_name].notna().sum()
    logger.debug(f"이동평균 계산 완료: 유효 데이터 {valid_rows:,}행 (전체 {len(df):,}행)")

    return df


def calculate_summary(
    trades_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    initial_capital: float,
) -> SummaryDict:
    """
    거래 내역과 자본 곡선으로 요약 지표를 계산한다.

    Args:
        trades_df: 거래 내역 DataFrame
        equity_df: 자본 곡선 DataFrame
        initial_capital: 초기 자본금

    Returns:
        요약 지표 딕셔너리
    """
    # initial_capital 검증
    if initial_capital <= 0:
        raise ValueError(f"initial_capital은 양수여야 합니다: {initial_capital}")

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

    final_capital: float = float(equity_df.iloc[-1]["equity"])
    total_return: float = final_capital - initial_capital
    total_return_pct: float = (total_return / initial_capital) * 100

    # 기간 계산
    start_date: pd.Timestamp = pd.Timestamp(equity_df.iloc[0][COL_DATE])
    end_date: pd.Timestamp = pd.Timestamp(equity_df.iloc[-1][COL_DATE])
    years: float = float((end_date - start_date).days) / ANNUAL_DAYS

    # CAGR
    if years > 0 and final_capital > 0:
        cagr: float = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
    else:
        cagr = 0.0

    # MDD 계산
    equity_df = equity_df.copy()
    equity_df["peak"] = equity_df["equity"].cummax()

    # peak가 0인 케이스 방어 (수치 안정성)
    safe_peak: pd.Series[float] = equity_df["peak"].replace(0, EPSILON)
    equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / safe_peak
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
