"""Spread Lab 앱 전용 분석 함수

app_rate_spread_lab.py에서만 사용되는 데이터 준비 및 피처 생성 함수를 제공한다.
analysis_helpers.py의 핵심 계산 함수(calculate_daily_signed_log_diff, aggregate_monthly)를
활용하여 월별 데이터를 준비하고 lag 피처를 생성한다.
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
    COL_DAILY_SIGNED,
    COL_DR_LAG1,
    COL_DR_LAG2,
    COL_DR_M,
    COL_MONTH,
    COL_SIMUL_DAILY_RETURN,
    COL_SUM_DAILY_M,
    DEFAULT_MIN_MONTHS_FOR_ANALYSIS,
)

# 기본 lag 리스트
DEFAULT_LAG_LIST = [1, 2]


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
        ValueError: 필수 컬럼 누락, 금리 커버리지 부족, 월별 결과 부족 등
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
        min_months_for_analysis=DEFAULT_MIN_MONTHS_FOR_ANALYSIS,
    )

    # 4. sum_daily_m 계산 (일일 증분의 월합)
    date_col_data = pd.to_datetime(daily_with_signed[DISPLAY_DATE])
    daily_with_signed[COL_MONTH] = date_col_data.dt.to_period("M")
    sum_daily_monthly = daily_with_signed.groupby(COL_MONTH, as_index=False)[COL_DAILY_SIGNED].sum()
    sum_daily_monthly[COL_SUM_DAILY_M] = sum_daily_monthly[COL_DAILY_SIGNED]
    sum_daily_monthly = sum_daily_monthly.drop(columns=[COL_DAILY_SIGNED])

    # 5. monthly에 merge하여 sum_daily_m 업데이트
    monthly = monthly.drop(columns=[COL_SUM_DAILY_M])
    monthly = monthly.merge(sum_daily_monthly, on=COL_MONTH, how="left")

    return monthly


def add_rate_change_lags(
    df_monthly: pd.DataFrame,
    lag_list: list[int] | None = None,
) -> pd.DataFrame:
    """
    dr_m 기반 lag 컬럼을 생성한다.

    delta 분석 및 모델 입력에 활용하기 위해 금리 변화의 시차 컬럼을 생성한다.
    원본 DataFrame을 변경하지 않고 복사본에서 작업한다.

    Args:
        df_monthly: 월별 DataFrame (dr_m 컬럼 필수)
        lag_list: 생성할 lag 값 리스트 (기본값: [1, 2])

    Returns:
        lag 컬럼이 추가된 DataFrame (원본 불변)
        - dr_lag1: dr_m.shift(1)
        - dr_lag2: dr_m.shift(2)

    Raises:
        ValueError: dr_m 컬럼이 없는 경우
    """
    if lag_list is None:
        lag_list = DEFAULT_LAG_LIST

    # 필수 컬럼 검증
    if COL_DR_M not in df_monthly.columns:
        raise ValueError(f"필수 컬럼 누락: {COL_DR_M}")

    # 원본 불변성 보장
    result = df_monthly.copy()

    # lag 컬럼 생성
    lag_col_map = {1: COL_DR_LAG1, 2: COL_DR_LAG2}
    for lag in lag_list:
        col_name = lag_col_map.get(lag)
        if col_name:
            result[col_name] = result[COL_DR_M].shift(lag)

    return result
