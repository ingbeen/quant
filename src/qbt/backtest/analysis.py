"""백테스트 분석 모듈

이동평균 계산, 성과 지표 계산 기능을 제공한다.

학습 포인트:
1. 이동평균(Moving Average): 일정 기간의 가격 평균을 계산하여 추세 파악
2. SMA (Simple MA): 단순 평균, EMA (Exponential MA): 최근 데이터에 가중치
3. CAGR: 연평균 복리 성장률 - 투자 성과를 연 단위로 환산
4. MDD: 최대 낙폭 - 최고점 대비 최대 하락 비율
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from qbt.backtest.constants import (
    CALMAR_MDD_ZERO_SUBSTITUTE,
    COL_EQUITY,
    COL_PNL,
    ROUND_PERCENT,
    ma_col_name,
)
from qbt.backtest.types import SummaryDict
from qbt.common_constants import ANNUAL_DAYS, COL_CLOSE, COL_DATE, EPSILON, TRADING_DAYS_PER_YEAR
from qbt.utils import get_logger

logger = get_logger(__name__)


def add_single_moving_average(
    df: pd.DataFrame,
    window: int,
    ma_type: Literal["ema", "sma"] = "sma",
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
    col_name = ma_col_name(window)

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


def calculate_drawdown_pct_series(equity_series: pd.Series[float]) -> pd.Series[float]:
    """에쿼티 시리즈로부터 drawdown_pct(%) 시리즈를 계산한다.

    cummax 대비 하락률을 백분율로 반환한다.

    Args:
        equity_series: 에쿼티 값 시리즈

    Returns:
        drawdown_pct 시리즈 (0 이하 값, 단위: %)
    """
    peak = equity_series.cummax()
    if (peak == 0).any():
        raise RuntimeError("내부 불변조건 위반: equity peak에 0이 존재 (initial_capital > 0이면 불가능)")
    return (equity_series - peak) / peak * 100


def calculate_calmar(cagr: float, mdd: float) -> float:
    """CAGR / |MDD| 기준 Calmar를 계산한다. MDD=0 안전 처리 포함.

    Args:
        cagr: 연평균 복리 성장률 (퍼센트 단위, 예: 10.0 = 10%)
        mdd: 최대 낙폭 (퍼센트 단위, 예: -5.0 = -5%)

    Returns:
        Calmar 비율.
        - |MDD| < EPSILON, CAGR > 0: CALMAR_MDD_ZERO_SUBSTITUTE + cagr
        - |MDD| < EPSILON, CAGR <= 0: 0.0
        - 정상: cagr / abs(mdd)
    """
    abs_mdd = abs(mdd)
    if abs_mdd < EPSILON:
        return CALMAR_MDD_ZERO_SUBSTITUTE + cagr if cagr > 0 else 0.0
    return cagr / abs_mdd


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
            "calmar": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "start_date": None,
            "end_date": None,
        }

    final_capital: float = float(equity_df.iloc[-1][COL_EQUITY])
    total_return: float = final_capital - initial_capital
    total_return_pct: float = (total_return / initial_capital) * 100

    # 기간 계산
    start_date: pd.Timestamp = pd.Timestamp(equity_df.iloc[0][COL_DATE])
    end_date: pd.Timestamp = pd.Timestamp(equity_df.iloc[-1][COL_DATE])
    years: float = float((end_date - start_date).days) / ANNUAL_DAYS

    # CAGR
    if years > 0 and final_capital > 0:
        cagr: float = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
    elif years > 0 and final_capital <= 0:
        raise RuntimeError(f"내부 불변조건 위반: final_capital <= 0 (비레버리지 백테스트에서 전액 손실 불가, final_capital={final_capital})")
    else:
        # years <= 0: 정상 백테스트는 MIN_VALID_ROWS=2와 서로 다른 시작/종료 날짜를 보장하므로 도달 불가
        raise RuntimeError(
            f"내부 불변조건 위반: years <= 0 "
            f"(equity_df 시작/종료 날짜가 같으면 CAGR 정의 불가, "
            f"start_date={start_date.date()}, end_date={end_date.date()}, years={years})"
        )

    # MDD 계산
    equity_df = equity_df.copy()
    equity_df["peak"] = equity_df[COL_EQUITY].cummax()

    if (equity_df["peak"] == 0).any():
        raise RuntimeError("내부 불변조건 위반: equity peak에 0이 존재 (initial_capital > 0이면 불가능)")
    equity_df["drawdown"] = (equity_df[COL_EQUITY] - equity_df["peak"]) / equity_df["peak"]
    mdd = equity_df["drawdown"].min() * 100

    # Calmar 계산 (CAGR / |MDD|, MDD=0 안전 처리)
    calmar: float = calculate_calmar(cagr, mdd)

    # 거래 통계
    total_trades = len(trades_df)
    if total_trades > 0:
        winning_trades = len(trades_df[trades_df[COL_PNL] > 0])
        # pnl=0은 손실로 분류 (winning + losing = total)
        losing_trades = len(trades_df[trades_df[COL_PNL] <= 0])
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
        "calmar": calmar,
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate": win_rate,
        "start_date": str(equity_df.iloc[0][COL_DATE]),
        "end_date": str(equity_df.iloc[-1][COL_DATE]),
    }


def calculate_monthly_returns(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """
    에쿼티 데이터로부터 월별 수익률을 계산한다.

    월말 리샘플링으로 에쿼티 값을 추출한 뒤, 월간 수익률(%)을 계산한다.

    Args:
        equity_df: 자본 곡선 DataFrame (Date, equity 컬럼 필수)

    Returns:
        월별 수익률 리스트 [{year, month, return_pct}, ...]
    """
    if equity_df.empty or len(equity_df) < 2:
        return []

    # 1. 에쿼티 데이터를 날짜 인덱스로 변환
    eq = equity_df[[COL_DATE, COL_EQUITY]].copy()
    eq[COL_DATE] = pd.to_datetime(eq[COL_DATE])
    eq = eq.set_index(COL_DATE)

    # 2. 월말 리샘플링
    monthly_equity = eq[COL_EQUITY].resample("ME").last().dropna()
    if len(monthly_equity) < 2:
        return []

    # 3. 월간 수익률 계산 (%)
    monthly_returns = monthly_equity.pct_change().dropna() * 100

    # 4. 결과 리스트 생성
    dt_index = pd.DatetimeIndex(monthly_returns.index)
    result: list[dict[str, object]] = []
    for i in range(len(monthly_returns)):
        result.append(
            {
                "year": int(dt_index[i].year),
                "month": int(dt_index[i].month),
                "return_pct": round(float(monthly_returns.iloc[i]), ROUND_PERCENT),
            }
        )

    return result


def calculate_yearly_returns(monthly_returns: list[dict[str, object]]) -> list[dict[str, object]]:
    """
    월별 수익률 리스트로부터 연간 복리 수익률을 계산한다.

    같은 연도에 속한 월별 수익률(%)을 복리 누적하여 연간 수익률(%)을 산출한다.
    공식: yearly_pct = (prod(1 + monthly_pct / 100) - 1) * 100

    Args:
        monthly_returns: `calculate_monthly_returns()`의 반환값과 동일한 구조
                        ([{year, month, return_pct}, ...])

    Returns:
        연간 수익률 리스트 [{year, return_pct}, ...] (year 오름차순).
        빈 입력 시 빈 리스트 반환.
    """
    if not monthly_returns:
        return []

    # 1. 연도별 월간 수익률 그룹핑
    grouped: dict[int, list[float]] = {}
    for entry in monthly_returns:
        year = int(str(entry["year"]))
        return_pct = float(str(entry["return_pct"]))
        grouped.setdefault(year, []).append(return_pct)

    # 2. 연도 오름차순으로 복리 누적
    result: list[dict[str, object]] = []
    for year in sorted(grouped.keys()):
        cumulative = 1.0
        for monthly_pct in grouped[year]:
            cumulative *= 1.0 + monthly_pct / 100.0
        yearly_pct = (cumulative - 1.0) * 100.0
        result.append(
            {
                "year": year,
                "return_pct": round(yearly_pct, ROUND_PERCENT),
            }
        )

    return result


def _daily_returns_from_equity(equity_df: pd.DataFrame) -> np.ndarray:
    """에쿼티 DataFrame에서 일별 수익률 numpy 배열을 계산한다.

    equity 컬럼의 pct_change() 결과에서 NaN을 제거해 반환한다.

    Args:
        equity_df: 자본 곡선 DataFrame (equity 컬럼 필수)

    Returns:
        일별 수익률 배열 (길이 = len(equity_df) - 1)
    """
    if equity_df.empty or len(equity_df) < 2:
        return np.array([], dtype=float)
    series = equity_df[COL_EQUITY].astype(float)
    returns = series.pct_change().dropna().to_numpy()
    return returns


def calculate_sharpe_ratio(equity_df: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
    """일별 수익률 기반 연율화 샤프 비율을 계산한다.

    공식: (mean(r) - rf_daily) / std(r) * sqrt(TRADING_DAYS_PER_YEAR)

    Args:
        equity_df: 자본 곡선 DataFrame (equity 컬럼 필수)
        risk_free_rate: 연간 무위험 수익률 (0.03 = 3%). 기본 0.0.

    Returns:
        연율화 샤프 비율. 데이터가 부족(2행 미만)하거나 std가 EPSILON 미만이면 0.0 반환.
    """
    returns = _daily_returns_from_equity(equity_df)
    if returns.size < 2:
        return 0.0

    std = float(np.std(returns, ddof=1))
    if std < EPSILON:
        return 0.0

    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess_mean = float(np.mean(returns)) - rf_daily
    sharpe = excess_mean / std * np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(sharpe)


def calculate_sortino_ratio(equity_df: pd.DataFrame, risk_free_rate: float = 0.0) -> float:
    """일별 수익률 기반 연율화 소르티노 비율을 계산한다.

    하방 편차(downside deviation)만으로 리스크를 측정한다. 하방 편차는
    `sqrt(mean(min(r - rf_daily, 0) ** 2))`로 정의되며, 상승 변동은 리스크에 포함하지 않는다.

    Args:
        equity_df: 자본 곡선 DataFrame (equity 컬럼 필수)
        risk_free_rate: 연간 무위험 수익률 (0.03 = 3%). 기본 0.0.

    Returns:
        연율화 소르티노 비율. 데이터가 부족하거나 하방 편차가 EPSILON 미만이면 0.0 반환
        (모든 수익이 양수이거나 손실 변동성이 없는 경우).
    """
    returns = _daily_returns_from_equity(equity_df)
    if returns.size < 2:
        return 0.0

    rf_daily = risk_free_rate / TRADING_DAYS_PER_YEAR
    excess = returns - rf_daily
    downside = np.minimum(excess, 0.0)
    downside_dev = float(np.sqrt(np.mean(downside**2)))
    if downside_dev < EPSILON:
        return 0.0

    sortino = float(np.mean(excess)) / downside_dev * np.sqrt(TRADING_DAYS_PER_YEAR)
    return float(sortino)


def calculate_benchmark_yearly_returns(
    benchmark_df: pd.DataFrame,
    start_date: pd.Timestamp | str,
    end_date: pd.Timestamp | str,
) -> list[dict[str, object]]:
    """벤치마크(예: QQQ) 종가로부터 지정 기간의 연간 복리 수익률을 계산한다.

    Close 컬럼을 equity 개념으로 취급하여 `calculate_monthly_returns` 및
    `calculate_yearly_returns`와 동일한 방식으로 월별→연간 수익률을 산출한다.

    Args:
        benchmark_df: 벤치마크 OHLCV DataFrame (Date, Close 컬럼 필수)
        start_date: 시작일 (inclusive)
        end_date: 종료일 (inclusive)

    Returns:
        연간 수익률 리스트 [{year, return_pct}, ...] (year 오름차순).
        기간 내 데이터가 2행 미만이면 빈 리스트 반환.
    """
    if benchmark_df.empty:
        return []

    df = benchmark_df[[COL_DATE, COL_CLOSE]].copy()
    df[COL_DATE] = pd.to_datetime(df[COL_DATE])
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    mask = (df[COL_DATE] >= start_ts) & (df[COL_DATE] <= end_ts)
    df = df.loc[mask].reset_index(drop=True)
    if len(df) < 2:
        return []

    # Close 컬럼을 equity 컬럼명으로 바꾸어 기존 월별/연간 계산 파이프라인 재사용
    df = df.rename(columns={COL_CLOSE: COL_EQUITY})
    monthly = calculate_monthly_returns(df)
    return calculate_yearly_returns(monthly)
