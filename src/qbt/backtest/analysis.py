"""백테스트 분석 모듈

이동평균 계산, 성과 지표 계산 기능을 제공한다.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from qbt.backtest.constants import (
    COL_EQUITY,
    COL_PNL,
    ma_col_name,
)
from qbt.backtest.types import SummaryDict
from qbt.common_constants import ANNUAL_DAYS, COL_CLOSE, COL_DATE, EPSILON, ROUND_PERCENT, TRADING_DAYS_PER_YEAR
from qbt.utils import get_logger

logger = get_logger(__name__)

# MDD=0 이고 CAGR>0 인 Calmar 의 대용값 — 무한대 대신 큰 유한값을 두어 정렬 · 최댓값 선택이 그대로 돈다
CALMAR_MDD_ZERO_SUBSTITUTE = 1e10


def add_single_moving_average(
    df: pd.DataFrame,
    window: int,
) -> pd.DataFrame:
    """
    지정된 기간의 단순이동평균(SMA)을 계산하여 컬럼으로 추가한다.

    이 프로젝트의 이동평균은 SMA 하나로 통일한다. 채택 근거는
    `src/qbt/backtest/CLAUDE.md` 「1-1」 및 `docs/research/전략_검증_보고서.md` 부록 G 참고.

    Args:
        df: 주식 데이터 DataFrame (Close 컬럼 필수)
        window: 이동평균 기간 (예: 20 = 20일 이동평균)

    Returns:
        이동평균 컬럼이 추가된 DataFrame (원본 복사본). 창이 차기 전(window-1 행)은 NaN 이라 호출자가 유효 행만 쓴다

    Raises:
        ValueError: window < 1인 경우
    """
    if window < 1:
        raise ValueError(f"window는 1 이상이어야 합니다: {window}")

    logger.debug(f"이동평균 계산: window={window}")

    df = df.copy()
    col_name = ma_col_name(window)
    df[col_name] = df[COL_CLOSE].rolling(window=window).mean()

    valid_rows = df[col_name].notna().sum()
    logger.debug(f"이동평균 계산 완료: 유효 데이터 {valid_rows:,}행 (전체 {len(df):,}행)")

    return df


def add_moving_averages(df: pd.DataFrame, windows: Iterable[int]) -> pd.DataFrame:
    """이동평균 여러 개를 더한다. 이미 있는 이동평균 열은 다시 계산하지 않는다.

    구간을 잘라 넘기는 호출자(워크포워드 IS)가 전체 기간으로 계산해 둔 값을 조각에서 다시 계산하면
    앞부분이 비어 시작일이 밀린다 — 그래서 있는 열은 그대로 둔다.
    """
    for window in windows:
        if ma_col_name(window) not in df.columns:
            df = add_single_moving_average(df, window)
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
        raise RuntimeError("내부 불변조건 위반: equity_df 가 비었다 (호출자는 백테스트를 돈 2행 이상의 에쿼티를 넘긴다)")

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

    mdd = float(calculate_drawdown_pct_series(equity_df[COL_EQUITY].astype(float)).min())

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


def _period_end_returns_pct(equity_df: pd.DataFrame, rule: str) -> pd.Series[float]:
    """기간 말 에쿼티의 직전 기간 말 대비 수익률(%)을 계산한다.

    첫 기간은 첫 행 에쿼티 대비다 — 시작일부터 첫 기간 말까지를 버리면 첫 달 · 첫 해 수익률이 빠진다.
    기간 말은 첫 행 뒤의 행에서만 구한다 — 첫 행뿐인 기간(시작일 = 그 기간의 마지막 거래일)은 길이가 0 이라 내지 않는다.

    Args:
        equity_df: 자본 곡선 DataFrame (Date, equity 컬럼 필수, 2행 이상)
        rule: 리샘플 주기 ("ME" 월말, "YE" 연말)

    Returns:
        기간 말 날짜를 인덱스로 하는 수익률(%) 시리즈
    """
    eq = equity_df[[COL_DATE, COL_EQUITY]].copy()
    eq[COL_DATE] = pd.to_datetime(eq[COL_DATE])
    equity = eq.set_index(COL_DATE)[COL_EQUITY].sort_index()

    period_end = equity.iloc[1:].resample(rule).last().dropna()
    previous = period_end.shift(1)
    previous.iloc[0] = equity.iloc[0]
    return (period_end / previous - 1) * 100


def calculate_monthly_returns(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """
    에쿼티 데이터로부터 월별 수익률을 계산한다.

    첫 달은 첫 행 에쿼티 대비, 그 뒤는 직전 월말 대비다.

    Args:
        equity_df: 자본 곡선 DataFrame (Date, equity 컬럼 필수)

    Returns:
        월별 수익률 리스트 [{year, month, return_pct}, ...]. 2행 미만이면 빈 리스트.
    """
    if len(equity_df) < 2:
        return []

    monthly_returns = _period_end_returns_pct(equity_df, "ME")
    dt_index = pd.DatetimeIndex(monthly_returns.index)
    return [
        {
            "year": int(dt_index[i].year),
            "month": int(dt_index[i].month),
            "return_pct": round(float(monthly_returns.iloc[i]), ROUND_PERCENT),
        }
        for i in range(len(monthly_returns))
    ]


def calculate_yearly_returns(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """
    에쿼티 데이터로부터 연간 수익률을 계산한다.

    첫 해는 첫 행 에쿼티 대비, 그 뒤는 직전 연말 대비다.
    월별 수익률을 복리하지 않는다 — 저장 자릿수로 깎인 월 수익률을 복리하면 오차가 쌓인다.

    Args:
        equity_df: 자본 곡선 DataFrame (Date, equity 컬럼 필수)

    Returns:
        연간 수익률 리스트 [{year, return_pct}, ...] (year 오름차순). 2행 미만이면 빈 리스트.
    """
    if len(equity_df) < 2:
        return []

    yearly_returns = _period_end_returns_pct(equity_df, "YE")
    dt_index = pd.DatetimeIndex(yearly_returns.index)
    return [
        {
            "year": int(dt_index[i].year),
            "return_pct": round(float(yearly_returns.iloc[i]), ROUND_PERCENT),
        }
        for i in range(len(yearly_returns))
    ]


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
