"""Spread Lab 앱 전용 분석 함수

app_rate_spread_lab.py에서만 사용되는 데이터 준비 함수를 제공한다.
analysis_helpers.py의 핵심 계산 함수(calculate_daily_signed_log_diff, aggregate_monthly)를
활용하여 월별 데이터를 준비한다.
"""

import pandas as pd

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.analysis_helpers import (
    aggregate_monthly,
    calculate_daily_signed_log_diff,
)
from qbt.tqqq.constants import (
    COL_ACTUAL_DAILY_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_MONTH,
    COL_SIMUL_DAILY_RETURN,
    COL_SUM_DAILY_M,
    ROLLING_CORR_WINDOW_MONTHS,
)

COL_DAILY_SIGNED = "daily_signed"  # 일일 증분 signed 로그오차

# 월간 변화(de_m · dr_m)는 첫 달이 비어 Rolling 상관의 첫 값을 내려면 창보다 한 달이 더 있어야 한다
MIN_MONTHS_FOR_ANALYSIS = ROLLING_CORR_WINDOW_MONTHS + 1


def prepare_monthly_data(
    daily_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    일별 데이터를 월별로 집계하고 금리 데이터와 매칭한다.

    처리 흐름:
        1. 일일 증분 signed 로그오차 계산
        2. 일별 데이터에 추가
        3. aggregate_monthly() 호출하여 월별 집계
        4. sum_daily_m 계산 (aggregate_monthly는 e_m, de_m만 제공)

    Args:
        daily_df: 일별 비교 데이터
        ffr_df: 금리 데이터

    Returns:
        월별 DataFrame (month, e_m, de_m, sum_daily_m, rate_pct, dr_m)

    Raises:
        ValueError: 필수 컬럼 누락, 금리 커버리지 부족, 월별 결과가 MIN_MONTHS_FOR_ANALYSIS 미만 등
    """
    # 1. 일일 증분 signed 로그오차 계산
    daily_signed = calculate_daily_signed_log_diff(
        daily_return_real_pct=daily_df[COL_ACTUAL_DAILY_RETURN],
        daily_return_sim_pct=daily_df[COL_SIMUL_DAILY_RETURN],
    )

    # 2. 일별 데이터에 추가
    daily_with_signed = daily_df.copy()
    daily_with_signed[COL_DAILY_SIGNED] = daily_signed

    # 3. 월별 집계 (aggregate_monthly는 e_m, de_m만 제공)
    monthly = aggregate_monthly(
        daily_df=daily_with_signed,
        date_col=DISPLAY_DATE,
        signed_col=COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
        ffr_df=ffr_df,
        min_months_for_analysis=MIN_MONTHS_FOR_ANALYSIS,
    )

    # 4. sum_daily_m 계산 (일일 증분의 월합)
    date_col_data = pd.to_datetime(daily_with_signed[DISPLAY_DATE])
    daily_with_signed[COL_MONTH] = date_col_data.dt.to_period("M")
    sum_daily_monthly = daily_with_signed.groupby(COL_MONTH, as_index=False)[COL_DAILY_SIGNED].sum()
    sum_daily_monthly[COL_SUM_DAILY_M] = sum_daily_monthly[COL_DAILY_SIGNED]
    sum_daily_monthly = sum_daily_monthly.drop(columns=[COL_DAILY_SIGNED])

    # 5. monthly에 sum_daily_m 합치기
    monthly = monthly.merge(sum_daily_monthly, on=COL_MONTH, how="left")

    return monthly
