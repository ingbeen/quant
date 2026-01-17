"""
TQQQ 시뮬레이션 분석용 순수 계산 함수

금리-오차 관계 분석을 위한 계산, 집계, 검증 함수를 제공한다.
모든 함수는 상태를 유지하지 않으며(stateless), fail-fast 정책을 따른다.

Fail-fast 정책:
- 결과를 신뢰할 수 없게 만드는 문제 발견 시 ValueError를 raise하여 즉시 중단
- 조용히 진행하지 않고 명확한 에러 메시지 제공
"""

from pathlib import Path

import numpy as np
import pandas as pd

from qbt.tqqq.constants import (
    # 공유 컬럼 (다른 파일에서도 사용)
    COL_DE_M,
    COL_DR_LAG1,
    COL_DR_LAG2,
    COL_DR_M,
    COL_E_M,
    COL_FFR_VALUE,
    COL_MONTH,
    COL_RATE_PCT,
    COL_SUM_DAILY_M,
    DEFAULT_ROLLING_WINDOW,
)
from qbt.utils import get_logger

logger = get_logger(__name__)

# ============================================================
# 분석 전용 상수 (이 파일에서만 사용)
# ============================================================

# 모델용 CSV 스키마 버전
MODEL_SCHEMA_VERSION = "1.0"

# 기본 lag 리스트
DEFAULT_LAG_LIST = [1, 2]

# --- 요약 통계 내부 컬럼 (영문 토큰) ---
COL_CATEGORY = "category"  # 분석 유형
COL_X_VAR = "x_var"  # X축 변수
COL_Y_VAR = "y_var"  # Y축 변수
COL_LAG = "lag"  # 시차 (월)
COL_N = "n"  # 샘플 수
COL_CORR = "corr"  # 상관계수
COL_SLOPE = "slope"  # 기울기
COL_INTERCEPT = "intercept"  # 절편
COL_MAX_ABS_DIFF = "max_abs_diff"  # 최대 절댓값 차이 (%)
COL_MEAN_ABS_DIFF = "mean_abs_diff"  # 평균 절댓값 차이 (%)
COL_STD_DIFF = "std_diff"  # 표준편차 (%)

# --- 월별 피처 출력 헤더 (DISPLAY_) ---
DISPLAY_MONTH = "연월"
DISPLAY_RATE_PCT = "금리수준(%)"
DISPLAY_DR_M = "금리변화(%p)"
DISPLAY_E_M = "월말누적오차(%)"
DISPLAY_DE_M = "월간오차변화(%)"
DISPLAY_SUM_DAILY_M = "일일오차월합(%)"
DISPLAY_DR_LAG1 = "금리변화Lag1(%p)"
DISPLAY_DR_LAG2 = "금리변화Lag2(%p)"

# --- 요약 통계 출력 헤더 ---
DISPLAY_CATEGORY = "분석유형"
DISPLAY_X_VAR = "X축변수"
DISPLAY_Y_VAR = "Y축변수"
DISPLAY_LAG = "시차(월)"
DISPLAY_N = "샘플수"
DISPLAY_CORR = "상관계수"
DISPLAY_SLOPE = "기울기"
DISPLAY_INTERCEPT = "절편"
DISPLAY_MAX_ABS_DIFF = "최대절댓값차이(%)"
DISPLAY_MEAN_ABS_DIFF = "평균절댓값차이(%)"
DISPLAY_STD_DIFF = "표준편차(%)"

# --- 모델용 CSV 컬럼 (영문, AI 모델 입력용) ---
COL_MODEL_MONTH = "month"  # 연월
COL_MODEL_SCHEMA_VERSION = "schema_version"  # 스키마 버전
COL_MODEL_RATE_LEVEL_PCT = "rate_level_pct"  # 금리 수준 (%)
COL_MODEL_RATE_CHANGE_PCT = "rate_change_pct"  # 금리 변화 (%p)
COL_MODEL_RATE_CHANGE_LAG1_PCT = "rate_change_lag1_pct"  # 금리 변화 Lag1 (%p)
COL_MODEL_RATE_CHANGE_LAG2_PCT = "rate_change_lag2_pct"  # 금리 변화 Lag2 (%p)
COL_MODEL_ERROR_EOM_PCT = "error_eom_pct"  # 월말 누적 오차 (%)
COL_MODEL_ERROR_CHANGE_PCT = "error_change_pct"  # 월간 오차 변화 (%)
COL_MODEL_ERROR_DAILY_SUM_PCT = "error_daily_sum_pct"  # 일일 오차 월합 (%)
COL_MODEL_CV_DIFF_PCT = "cv_diff_pct"  # 교차검증 차이 (%)
COL_MODEL_ROLLING_CORR_LEVEL = "rolling_corr_rate_level_error_eom"  # Rolling 상관: 금리수준-월말오차
COL_MODEL_ROLLING_CORR_DELTA = "rolling_corr_rate_change_error_change"  # Rolling 상관: 금리변화-오차변화
COL_MODEL_ROLLING_CORR_LAG1 = "rolling_corr_rate_lag1_error_change"  # Rolling 상관: 금리Lag1-오차변화
COL_MODEL_ROLLING_CORR_LAG2 = "rolling_corr_rate_lag2_error_change"  # Rolling 상관: 금리Lag2-오차변화

__all__ = [
    "calculate_signed_log_diff_from_cumulative_returns",
    "calculate_daily_signed_log_diff",
    "aggregate_monthly",
    "validate_integrity",
    "save_monthly_features",
    "save_summary_statistics",
    "add_rate_change_lags",
    "add_rolling_features",
    "build_model_dataset",
    "save_model_csv",
]


def calculate_signed_log_diff_from_cumulative_returns(
    cumul_return_real_pct: pd.Series,
    cumul_return_sim_pct: pd.Series,
) -> pd.Series:
    """
    누적수익률(%)로부터 signed 누적배수 로그차이를 계산한다.

    누적수익률을 누적배수(M)로 변환한 후, 로그 비율로 스케일 무관 추적오차를 계산한다.
    signed 값은 방향성 정보를 포함하여 시뮬레이션이 실제보다 높은지/낮은지 판단 가능하다.

    계산 수식:
        M_real = 1 + (누적수익률_실제(%) / 100)
        M_sim  = 1 + (누적수익률_시뮬(%) / 100)
        signed(%) = 100 * ln(M_sim / M_real)

    Args:
        cumul_return_real_pct: 누적수익률_실제 (%, Series)
        cumul_return_sim_pct: 누적수익률_시뮬 (%, Series)

    Returns:
        signed 누적배수 로그차이 (%, Series)
        - 양수: 시뮬레이션이 실제보다 높음
        - 음수: 시뮬레이션이 실제보다 낮음

    Raises:
        ValueError: M_real <= 0 또는 M_sim <= 0인 경우 (로그 계산 불가)
            - 에러 메시지에 문제 행 수, 날짜 범위 포함

    Examples:
        >>> # 시뮬레이션이 실제보다 약간 높은 경우
        >>> real = pd.Series([10.0, 20.0, 30.0])  # 누적 10%, 20%, 30%
        >>> sim = pd.Series([11.0, 21.0, 31.0])   # 누적 11%, 21%, 31%
        >>> signed = calculate_signed_log_diff_from_cumulative_returns(real, sim)
        >>> # signed는 모두 양수 (시뮬이 더 높음)
    """
    # 1. 누적수익률(%)을 누적배수(M)로 변환
    # 설명: 누적수익률 = (현재가격 / 초기가격 - 1) * 100
    #       따라서 M = 현재가격 / 초기가격 = 1 + 누적수익률(%)/100
    # 예: 누적수익률 10% -> M = 1.10 (초기 대비 1.1배)
    M_real = 1.0 + cumul_return_real_pct / 100.0
    M_sim = 1.0 + cumul_return_sim_pct / 100.0

    # 2. M <= 0 검증 (fail-fast)
    # 이유: ln(M)을 계산해야 하는데 M <= 0이면 로그 함수 정의역 밖
    # 발생 조건: 누적수익률이 -100% 이하 (자산 가치가 0 이하로 떨어짐)
    invalid_real = M_real <= 0
    invalid_sim = M_sim <= 0

    if invalid_real.any():
        num_invalid = invalid_real.sum()
        # 인덱스를 통해 위치 정보 제공 (날짜가 있으면 날짜, 없으면 인덱스 번호)
        invalid_indices = M_real[invalid_real].index.tolist()
        raise ValueError(
            f"M_real <= 0 발견 (로그 계산 불가): {num_invalid}행\n문제 인덱스: {invalid_indices[:5]}{'...' if num_invalid > 5 else ''}\n원인: 누적수익률_실제가 -100% 이하 (자산 가치 0 이하)\n조치: 데이터 정합성 확인 필요"
        )

    if invalid_sim.any():
        num_invalid = invalid_sim.sum()
        invalid_indices = M_sim[invalid_sim].index.tolist()
        raise ValueError(
            f"M_sim <= 0 발견 (로그 계산 불가): {num_invalid}행\n문제 인덱스: {invalid_indices[:5]}{'...' if num_invalid > 5 else ''}\n원인: 누적수익률_시뮬이 -100% 이하 (자산 가치 0 이하)\n조치: 시뮬레이션 로직 또는 입력 데이터 확인 필요"
        )

    # 3. signed 로그차이 계산
    # 수식: signed = 100 * ln(M_sim / M_real)
    # 부호 의미:
    #   - 양수: M_sim > M_real, 시뮬레이션이 실제보다 높음
    #   - 음수: M_sim < M_real, 시뮬레이션이 실제보다 낮음
    #   - 0에 가까움: M_sim = M_real, 거의 일치
    ratio = M_sim / M_real
    signed_pct = pd.Series(100.0 * np.log(ratio), index=ratio.index)

    return signed_pct


def calculate_daily_signed_log_diff(
    daily_return_real_pct: pd.Series,
    daily_return_sim_pct: pd.Series,
) -> pd.Series:
    """
    일일수익률(%)로부터 일일 증분 signed 로그오차를 계산한다.

    "그날 시뮬레이션이 실제 대비 얼마나 더/덜 벌었는가"를 나타내는 지표.
    월별 집계 시 sum하여 월간 누적 오차를 계산하는 데 사용된다.

    계산 수식:
        일일_signed(%) = 100 * ln((1 + r_sim/100) / (1 + r_real/100))

    Args:
        daily_return_real_pct: 일일수익률_실제 (%, Series)
        daily_return_sim_pct: 일일수익률_시뮬 (%, Series)

    Returns:
        일일 증분 signed 로그오차 (%, Series)
        - 양수: 그날 시뮬이 실제보다 더 벌었음
        - 음수: 그날 시뮬이 실제보다 덜 벌었음

    Raises:
        ValueError: 1 + r_real/100 <= 0 또는 1 + r_sim/100 <= 0인 경우 (로그 계산 불가)
            - 에러 메시지에 문제 행 수, 날짜 범위 포함

    Note:
        흔한 실수: 일일수익률이 % 단위인지 확인 필요 (0~1 소수가 아님)
        예: 5% 수익 = 5.0 (% 단위), 0.05 (소수 단위) X
    """
    # 1. 일일수익률(%)을 배수로 변환
    # 설명: 일일수익률 r%이면 그날 자산은 (1 + r/100)배가 됨
    # 예: r = 5% -> 1.05배 (초기 100원이 105원)
    #     r = -2% -> 0.98배 (초기 100원이 98원)
    factor_real = 1.0 + daily_return_real_pct / 100.0
    factor_sim = 1.0 + daily_return_sim_pct / 100.0

    # 2. 1+r <= 0 검증 (fail-fast)
    # 이유: ln(1+r)을 계산해야 하는데 1+r <= 0이면 로그 함수 정의역 밖
    # 발생 조건: 일일수익률이 -100% 이하 (하루 만에 자산 가치가 0 이하로 떨어짐)
    # 참고: 일일수익률 -100%는 매우 비정상적 (서킷브레이커, 상폐 등 극단 상황)
    invalid_real = factor_real <= 0
    invalid_sim = factor_sim <= 0

    if invalid_real.any():
        num_invalid = invalid_real.sum()
        invalid_indices = factor_real[invalid_real].index.tolist()
        raise ValueError(
            f"1 + r_real/100 <= 0 발견 (로그 계산 불가): {num_invalid}행\n문제 인덱스: {invalid_indices[:5]}{'...' if num_invalid > 5 else ''}\n원인: 일일수익률_실제가 -100% 이하 (하루 만에 자산 가치 0 이하)\n조치: 데이터 정합성 확인 필요 (서킷브레이커/상폐 등)"
        )

    if invalid_sim.any():
        num_invalid = invalid_sim.sum()
        invalid_indices = factor_sim[invalid_sim].index.tolist()
        raise ValueError(
            f"1 + r_sim/100 <= 0 발견 (로그 계산 불가): {num_invalid}행\n문제 인덱스: {invalid_indices[:5]}{'...' if num_invalid > 5 else ''}\n원인: 일일수익률_시뮬이 -100% 이하 (하루 만에 자산 가치 0 이하)\n조치: 시뮬레이션 로직 확인 필요 (비용 계산 오류 가능성)"
        )

    # 3. 일일 증분 signed 로그오차 계산
    # 수식: daily_signed = 100 * ln(factor_sim / factor_real)
    # 부호 의미:
    #   - 양수: 그날 시뮬이 실제보다 더 벌었음
    #   - 음수: 그날 시뮬이 실제보다 덜 벌었음
    # 활용: 월별로 sum하면 그 달의 누적 오차 (de_m 교차검증용)
    ratio = factor_sim / factor_real
    daily_signed_pct = pd.Series(100.0 * np.log(ratio), index=ratio.index)

    return daily_signed_pct


def aggregate_monthly(
    daily_df: pd.DataFrame,
    date_col: str,
    signed_col: str,
    ffr_df: pd.DataFrame | None = None,
    min_months_for_analysis: int = 13,
) -> pd.DataFrame:
    """
    일별 데이터를 월별로 집계하고 금리 데이터와 매칭한다.

    월말(last) 누적 signed 값, 일일 증분 signed의 월합, 금리 수준/변화를 계산한다.
    금리 데이터와의 매칭은 to_period("M") 기반으로 수행된다.

    처리 흐름:
        1. 날짜 기준 오름차순 정렬 (월말 값 정확성 보장)
        2. month = 날짜.to_period("M") 생성
        3. 월별 집계:
           - e_m: 월말 누적 signed (last)
           - sum_daily_m: 일일 증분 signed의 월합 (sum)
        4. de_m: e_m의 월간 변화 (diff)
        5. 금리 데이터 join (month 키)
        6. rate_pct, dr_m 계산
        7. diff() 후 첫 달 NaN 제거

    Args:
        daily_df: 일별 데이터 (날짜, signed 컬럼 필수)
        date_col: 날짜 컬럼명
        signed_col: signed 컬럼명
        ffr_df: 금리 데이터 (DATE: yyyy-mm 문자열, VALUE: 0~1 소수), None이면 금리 생략
        min_months_for_analysis: 최소 필요 월 수 (기본 13, 테스트 시 조정 가능)

    Returns:
        월별 DataFrame (month, e_m, de_m, sum_daily_m, rate_pct, dr_m)
        - month: Period[M] (yyyy-mm)
        - e_m: 월말 누적 signed (%)
        - de_m: 월간 변화 (%)
        - sum_daily_m: 일일 증분 signed 월합 (%)
        - rate_pct: 금리 수준 (%, FFR 있을 때만)
        - dr_m: 금리 월간 변화 (%p, FFR 있을 때만)

    Raises:
        ValueError: 아래 조건 중 하나라도 해당하면 fail-fast
            - 필수 컬럼 누락 또는 daily_df가 비어있음
            - 금리 데이터 월 커버리지 부족 (분석 대상 월 범위를 충족하지 못함)
            - 월별 집계 결과가 너무 짧아 핵심 지표 계산 불가 (예: Rolling 12M 상관)

    Note:
        월말 값 정의: "해당 월 마지막 거래일의 레코드"
        정렬이 보장되지 않으면 잘못된 월말 값이 추출될 수 있으므로 함수 내부에서 강제 정렬
    """
    # 1. 필수 컬럼 검증 (fail-fast)
    if daily_df.empty:
        raise ValueError("daily_df가 비어있음 (월별 집계 불가)")

    missing_cols = []
    if date_col not in daily_df.columns:
        missing_cols.append(date_col)
    if signed_col not in daily_df.columns:
        missing_cols.append(signed_col)

    if missing_cols:
        raise ValueError(f"필수 컬럼 누락: {missing_cols}\n보유 컬럼: {list(daily_df.columns)}\n조치: 컬럼명 확인 (대소문자 구분)")

    # 2. 날짜 기준 오름차순 정렬 강제 (월말 값 정확성 보장)
    # 이유: groupby.last()는 정렬되지 않은 데이터에서 잘못된 월말 값을 반환할 수 있음
    # 정의: "월말 값은 해당 월 마지막 거래일의 레코드"
    df_sorted = daily_df.sort_values(by=date_col).copy()

    # 3. month 컬럼 생성 (yyyy-mm Period 객체)
    # 예: 2023-01-15 -> 2023-01
    # pd.to_datetime으로 명시적 datetime Series 변환 (타입 체커가 dt accessor 인식)
    date_col_data = pd.to_datetime(df_sorted[date_col])
    df_sorted[COL_MONTH] = date_col_data.dt.to_period("M")

    # 4. 월별 집계
    # - e_m: 월말 누적 signed (last, 해당 월 마지막 거래일 값)
    # - sum_daily_m: 일일 증분 signed의 월합 (sum)
    # 주의: 일일 증분이 없으면 sum_daily_m은 계산 불가 (이 함수는 e_m만 사용)
    monthly = df_sorted.groupby(COL_MONTH, as_index=False).agg({signed_col: "last"})
    monthly.rename(columns={signed_col: COL_E_M}, inplace=True)

    # 5. de_m 계산 (e_m의 월간 변화)
    # 예: e_m = [2.0, 3.0, 2.5] -> de_m = [NaN, 1.0, -0.5]
    monthly[COL_DE_M] = monthly[COL_E_M].diff()

    # 6. sum_daily_m 계산 (별도 로직, 일일 증분 필요 시)
    # 현재는 e_m만 있으므로 placeholder로 NaN
    # Streamlit에서 calculate_daily_signed_log_diff 호출 후 계산
    monthly[COL_SUM_DAILY_M] = pd.NA

    # 7. FFR 데이터 매칭 (있을 때만)
    if ffr_df is not None and not ffr_df.empty:
        # FFR 데이터 전처리
        # DATE 컬럼이 "yyyy-mm" 문자열 형식이므로 Period[M]로 변환
        ffr_processed = ffr_df.copy()
        ffr_processed[COL_MONTH] = pd.PeriodIndex(ffr_processed["DATE"], freq="M")

        # month 키로 left join (일별 기준 월만 보존)
        monthly = monthly.merge(ffr_processed[[COL_MONTH, COL_FFR_VALUE]], on=COL_MONTH, how="left")

        # rate_pct 계산 (0~1 소수 -> %)
        # 예: VALUE = 0.045 -> rate_pct = 4.5
        monthly[COL_RATE_PCT] = monthly[COL_FFR_VALUE] * 100.0

        # dr_m 계산 (금리 월간 변화, %p)
        monthly[COL_DR_M] = monthly[COL_RATE_PCT].diff()

        # VALUE 컬럼 제거 (불필요)
        monthly.drop(columns=[COL_FFR_VALUE], inplace=True)

        # FFR 커버리지 검증 (fail-fast)
        # 월별 데이터에 금리가 없는 월이 많으면 분석 불가
        missing_rate = monthly[COL_RATE_PCT].isna()
        if missing_rate.any():
            num_missing = missing_rate.sum()
            missing_months = monthly.loc[missing_rate, COL_MONTH].tolist()
            logger.debug(f"금리 데이터 누락 월: {num_missing}개월\n누락 월: {missing_months[:5]}{'...' if num_missing > 5 else ''}")
            # 경고만 하고 진행 (일부 누락은 허용, 너무 많으면 나중에 상관 계산 시 문제)

    else:
        # FFR 없으면 rate_pct, dr_m 컬럼을 NaN으로
        monthly[COL_RATE_PCT] = pd.NA
        monthly[COL_DR_M] = pd.NA

    # 8. diff() 후 첫 달 NaN 제거
    # 이유: de_m, dr_m의 첫 값은 항상 NaN (diff 특성)
    # 선택: 첫 달 제거할지는 사용자 요구에 따라 조정 가능
    # 여기서는 제거하지 않고 그대로 반환 (Streamlit에서 dropna)
    # monthly = monthly.dropna(subset=["de_m"])  # 선택사항

    # 9. 월별 집계 결과 길이 검증 (fail-fast)
    # Rolling 12M 상관을 계산하려면 최소 13개월 필요 (12M window + 1)
    if len(monthly) < min_months_for_analysis:
        raise ValueError(
            f"월별 집계 결과가 너무 짧음: {len(monthly)}개월\n최소 필요: {min_months_for_analysis}개월 (Rolling 12M 상관 계산 위해)\n조치: 더 긴 기간의 일별 데이터 필요"
        )

    return monthly


def validate_integrity(
    signed_series: pd.Series,
    abs_series: pd.Series,
    tolerance: float | None = None,
) -> dict[str, float]:
    """
    abs(signed)와 abs 컬럼의 무결성을 검증한다.

    signed 로그차이의 절댓값과 기존 abs 컬럼이 거의 일치해야 한다.
    반올림/누적 방식 차이로 완전히 0이 아닐 수 있으나, 큰 차이는 계산 로직 오류를 의미한다.

    tolerance 결정 규칙:
        - tolerance가 None이면 실제 데이터로 max_abs_diff, mean_abs_diff를 먼저 로그로 출력
        - 관측값을 기반으로 tolerance = max(1e-6, observed_max_abs_diff * 1.1) 제안
        - tolerance가 주어지면 max_abs_diff > tolerance일 때 ValueError raise

    Args:
        signed_series: signed 로그차이 (%, Series)
        abs_series: 기존 abs 컬럼 (%, Series)
        tolerance: 허용 오차 (%, None이면 관측만 수행)

    Returns:
        검증 결과 딕셔너리:
            - max_abs_diff: 최대 절댓값 차이 (%)
            - mean_abs_diff: 평균 절댓값 차이 (%)
            - tolerance: 사용된 또는 제안된 tolerance (%)

    Raises:
        ValueError: tolerance가 주어졌고 max_abs_diff > tolerance인 경우
            - 에러 메시지에 관측값, 허용값 포함
            - 차이 원인 안내: 반올림/누적 방식 차이, 정의 불일치 등

    Note:
        이 함수는 실제 데이터로 먼저 관측(tolerance=None) 후,
        tolerance를 코드 상수로 확정하고 CLAUDE.md에 기록하는 데 사용된다.
    """
    # 1. abs(signed) 계산
    # 설명: signed는 부호를 포함하므로 절댓값을 취해서 abs 컬럼과 비교
    abs_signed = signed_series.abs()

    # 2. 차이 계산
    # 이유: 둘이 거의 같아야 하지만, 반올림/누적 방식 차이로 완전히 0은 아닐 수 있음
    abs_diff = (abs_signed - abs_series).abs()

    # 3. 통계 계산
    max_abs_diff = float(abs_diff.max())
    mean_abs_diff = float(abs_diff.mean())

    # 4. tolerance 결정
    if tolerance is None:
        # 관측 모드: 실제 데이터로 max/mean 로그 출력
        proposed_tolerance = max(1e-6, max_abs_diff * 1.1)  # 관측값 + 10% 여유
        logger.debug(
            f"무결성 체크 관측 결과:\n  max_abs_diff: {max_abs_diff:.6e}%\n  mean_abs_diff: {mean_abs_diff:.6e}%\n  제안 tolerance: {proposed_tolerance:.6e}% (max * 1.1)\n참고: 반올림/누적 방식 차이로 완전히 0이 아닐 수 있음"
        )
        return {
            "max_abs_diff": max_abs_diff,
            "mean_abs_diff": mean_abs_diff,
            "tolerance": proposed_tolerance,  # 제안값
        }
    else:
        # 검증 모드: tolerance와 비교
        if max_abs_diff > tolerance:
            # Fail-fast: 무결성 실패
            raise ValueError(
                f"무결성 체크 실패: max_abs_diff > tolerance\n  관측 max_abs_diff: {max_abs_diff:.6e}%\n  허용 tolerance: {tolerance:.6e}%\n  초과량: {max_abs_diff - tolerance:.6e}%\n원인 (가능성 높은 순):\n  1. 반올림/누적 방식 차이 (정상 범위 초과)\n  2. signed 계산 로직 오류 (M 정의 불일치)\n  3. abs 컬럼 정의 불일치 (다른 수식 사용)\n조치: signed 및 abs 계산 로직 재검토 필요"
            )
        else:
            # 무결성 통과
            logger.debug(f"무결성 체크 통과:\n  max_abs_diff: {max_abs_diff:.6e}% <= tolerance: {tolerance:.6e}%")
            return {
                "max_abs_diff": max_abs_diff,
                "mean_abs_diff": mean_abs_diff,
                "tolerance": tolerance,
            }


def save_monthly_features(monthly_df: pd.DataFrame, output_path: Path) -> None:
    """
    월별 피처 DataFrame을 CSV로 저장한다 (AI/모델링용).

    저장 시 month 오름차순 정렬하여 시계열 순서를 보장한다.
    내부 컬럼명(영문 토큰)을 출력용 한글 헤더(DISPLAY_*)로 변경하고 소수점은 4자리로 라운딩한다.

    Args:
        monthly_df: 월별 집계 DataFrame
            필수 컬럼: month, rate_pct, dr_m, e_m, de_m, sum_daily_m
            선택 컬럼: dr_lag1, dr_lag2 (있으면 함께 저장)
        output_path: 출력 CSV 파일 경로

    Raises:
        ValueError: 필수 컬럼 누락 시
    """
    # 1. 필수 컬럼 검증
    required_cols = [COL_MONTH, COL_RATE_PCT, COL_DR_M, COL_E_M, COL_DE_M, COL_SUM_DAILY_M]
    missing = [col for col in required_cols if col not in monthly_df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 2. 저장할 컬럼 선택 (선택 컬럼 포함)
    optional_cols = [COL_DR_LAG1, COL_DR_LAG2]
    cols_to_save = required_cols + [col for col in optional_cols if col in monthly_df.columns]

    # 3. 복사 및 정렬 (원본 보호, 시계열 순서 보장)
    df_to_save = monthly_df[cols_to_save].copy()
    df_to_save = df_to_save.sort_values(COL_MONTH).reset_index(drop=True)

    # 4. month를 문자열로 변환 (CSV 호환성)
    df_to_save[COL_MONTH] = df_to_save[COL_MONTH].astype(str)

    # 5. 컬럼명 변경 (내부 토큰 -> 출력용 한글 헤더)
    rename_map = {
        COL_MONTH: DISPLAY_MONTH,
        COL_RATE_PCT: DISPLAY_RATE_PCT,
        COL_DR_M: DISPLAY_DR_M,
        COL_E_M: DISPLAY_E_M,
        COL_DE_M: DISPLAY_DE_M,
        COL_SUM_DAILY_M: DISPLAY_SUM_DAILY_M,
        COL_DR_LAG1: DISPLAY_DR_LAG1,
        COL_DR_LAG2: DISPLAY_DR_LAG2,
    }
    df_to_save = df_to_save.rename(columns=rename_map)

    # 6. 수치 컬럼 라운딩 (4자리 통일)
    numeric_cols = [DISPLAY_RATE_PCT, DISPLAY_DR_M, DISPLAY_E_M, DISPLAY_DE_M, DISPLAY_SUM_DAILY_M]
    if DISPLAY_DR_LAG1 in df_to_save.columns:
        numeric_cols.append(DISPLAY_DR_LAG1)
    if DISPLAY_DR_LAG2 in df_to_save.columns:
        numeric_cols.append(DISPLAY_DR_LAG2)

    for col in numeric_cols:
        if col in df_to_save.columns:
            df_to_save[col] = df_to_save[col].round(4)

    # 7. CSV 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_to_save.to_csv(output_path, index=False, encoding="utf-8")
    logger.debug(f"월별 피처 CSV 저장 완료: {output_path} ({len(df_to_save)}행)")


# summary CSV 스키마 정의 (컬럼 목록 및 순서 고정)
# FutureWarning 방지를 위해 concat 전 모든 DataFrame을 이 스키마로 정규화
_SUMMARY_COLUMNS = [
    COL_CATEGORY,
    COL_X_VAR,
    COL_Y_VAR,
    COL_LAG,
    COL_N,
    COL_CORR,
    COL_SLOPE,
    COL_INTERCEPT,
    COL_MAX_ABS_DIFF,
    COL_MEAN_ABS_DIFF,
    COL_STD_DIFF,
]


def _normalize_summary_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    summary DataFrame을 표준 스키마와 dtype으로 정규화한다.

    FutureWarning 방지를 위해 concat 전에 모든 summary DataFrame에 적용한다.
    - 컬럼 정렬/생성: reindex로 누락 컬럼은 NaN으로 채움
    - dtype 강제: 문자열/정수/실수 컬럼별 명시적 타입 지정

    Args:
        df: 정규화할 summary DataFrame

    Returns:
        정규화된 DataFrame (동일 스키마, 동일 dtype)
    """
    # 1. 컬럼 정렬/생성 (누락 컬럼은 NaN으로 채움)
    df = df.reindex(columns=_SUMMARY_COLUMNS)

    # 2. dtype 강제 적용
    # 문자열 컬럼: pandas StringDtype
    df[COL_CATEGORY] = df[COL_CATEGORY].astype("string")
    df[COL_X_VAR] = df[COL_X_VAR].astype("string")
    df[COL_Y_VAR] = df[COL_Y_VAR].astype("string")

    # 정수 컬럼: pandas nullable Int64 (None 허용)
    df[COL_LAG] = df[COL_LAG].astype("Int64")
    df[COL_N] = df[COL_N].astype("Int64")

    # 실수 컬럼: float64
    float_cols = [COL_CORR, COL_SLOPE, COL_INTERCEPT, COL_MAX_ABS_DIFF, COL_MEAN_ABS_DIFF, COL_STD_DIFF]
    for col in float_cols:
        df[col] = df[col].astype("float64")

    return df


def save_summary_statistics(monthly_df: pd.DataFrame, output_path: Path) -> None:
    """
    요약 통계 DataFrame을 CSV로 저장한다 (AI/해석용).

    Level, Delta, 교차검증 요약을 모두 포함한 단일 CSV를 생성한다.
    내부 컬럼명(영문 토큰)을 출력용 한글 헤더(DISPLAY_*)로 변경하고 소수점은 4자리로 라운딩한다.

    FutureWarning 방지:
        concat 전에 모든 summary DataFrame을 _normalize_summary_df()로 정규화하여
        동일한 스키마와 dtype을 보장한다.

    Args:
        monthly_df: 월별 집계 DataFrame
            필수 컬럼: month, rate_pct, dr_m, e_m, de_m, sum_daily_m
        output_path: 출력 CSV 파일 경로

    Raises:
        ValueError: 필수 컬럼 누락, 데이터 부족 등
    """
    # 1. 필수 컬럼 검증
    required_cols = [COL_MONTH, COL_RATE_PCT, COL_DR_M, COL_E_M, COL_DE_M, COL_SUM_DAILY_M]
    missing = [col for col in required_cols if col not in monthly_df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 2. Level 요약 (rate_pct vs e_m)
    level_valid = monthly_df.dropna(subset=[COL_RATE_PCT, COL_E_M])
    if len(level_valid) < 2:
        raise ValueError(f"Level 요약 불가: 유효 데이터 {len(level_valid)}개 (최소 2개 필요)")

    level_corr = level_valid[COL_RATE_PCT].corr(level_valid[COL_E_M])
    level_fit = np.polyfit(level_valid[COL_RATE_PCT], level_valid[COL_E_M], 1)
    level_slope, level_intercept = level_fit[0], level_fit[1]

    level_summary = pd.DataFrame(
        [
            {
                COL_CATEGORY: "Level",
                COL_X_VAR: "rate_pct",
                COL_Y_VAR: "e_m",
                COL_LAG: 0,
                COL_N: len(level_valid),
                COL_CORR: level_corr,
                COL_SLOPE: level_slope,
                COL_INTERCEPT: level_intercept,
            }
        ]
    )

    # 3. Delta 요약 (dr_m.shift(lag) vs de_m, lag 0/1/2)
    delta_rows = []
    dr_lag_col = "dr_lag"  # 로컬 임시 컬럼명

    for lag in [0, 1, 2]:
        # dr_m.shift(lag) vs de_m
        df_lag = monthly_df.copy()
        df_lag[dr_lag_col] = df_lag[COL_DR_M].shift(lag)
        delta_valid = df_lag.dropna(subset=[dr_lag_col, COL_DE_M])

        if len(delta_valid) >= 2:
            corr_de = delta_valid[dr_lag_col].corr(delta_valid[COL_DE_M])
            fit_de = np.polyfit(delta_valid[dr_lag_col], delta_valid[COL_DE_M], 1)
            delta_rows.append(
                {
                    COL_CATEGORY: "Delta",
                    COL_X_VAR: f"dr_m_lag{lag}",
                    COL_Y_VAR: "de_m",
                    COL_LAG: lag,
                    COL_N: len(delta_valid),
                    COL_CORR: corr_de,
                    COL_SLOPE: fit_de[0],
                    COL_INTERCEPT: fit_de[1],
                }
            )

        # dr_m.shift(lag) vs sum_daily_m
        delta_valid_sum = df_lag.dropna(subset=[dr_lag_col, COL_SUM_DAILY_M])
        if len(delta_valid_sum) >= 2:
            corr_sum = delta_valid_sum[dr_lag_col].corr(delta_valid_sum[COL_SUM_DAILY_M])
            fit_sum = np.polyfit(delta_valid_sum[dr_lag_col], delta_valid_sum[COL_SUM_DAILY_M], 1)
            delta_rows.append(
                {
                    COL_CATEGORY: "Delta",
                    COL_X_VAR: f"dr_m_lag{lag}",
                    COL_Y_VAR: "sum_daily_m",
                    COL_LAG: lag,
                    COL_N: len(delta_valid_sum),
                    COL_CORR: corr_sum,
                    COL_SLOPE: fit_sum[0],
                    COL_INTERCEPT: fit_sum[1],
                }
            )

    delta_summary = pd.DataFrame(delta_rows) if delta_rows else pd.DataFrame()

    # 4. 교차검증 요약 (de_m vs sum_daily_m 차이)
    cross_valid = monthly_df.dropna(subset=[COL_DE_M, COL_SUM_DAILY_M])
    if len(cross_valid) >= 1:
        diff = cross_valid[COL_DE_M] - cross_valid[COL_SUM_DAILY_M]
        cross_summary = pd.DataFrame(
            [
                {
                    COL_CATEGORY: "CrossValidation",
                    COL_X_VAR: "de_m",
                    COL_Y_VAR: "sum_daily_m",
                    COL_LAG: None,
                    COL_N: len(cross_valid),
                    COL_CORR: None,
                    COL_SLOPE: None,
                    COL_INTERCEPT: None,
                    COL_MAX_ABS_DIFF: diff.abs().max(),
                    COL_MEAN_ABS_DIFF: diff.abs().mean(),
                    COL_STD_DIFF: diff.std(),
                }
            ]
        )
    else:
        cross_summary = pd.DataFrame()

    # 5. 전체 요약 결합 (FutureWarning 방지를 위해 정규화 후 concat)
    summary_list = [level_summary]
    if not delta_summary.empty:
        summary_list.append(delta_summary)
    if not cross_summary.empty:
        summary_list.append(cross_summary)

    # 정규화: 모든 DataFrame을 동일한 스키마와 dtype으로 변환
    # 이렇게 하면 pandas가 dtype을 추론하지 않아 FutureWarning이 발생하지 않음
    normalized_summaries = [_normalize_summary_df(s) for s in summary_list if not s.empty]
    full_summary = pd.concat(normalized_summaries, ignore_index=True)

    # 6. 컬럼명 변경 (내부 토큰 -> 출력용 한글 헤더)
    rename_map = {
        COL_CATEGORY: DISPLAY_CATEGORY,
        COL_X_VAR: DISPLAY_X_VAR,
        COL_Y_VAR: DISPLAY_Y_VAR,
        COL_LAG: DISPLAY_LAG,
        COL_N: DISPLAY_N,
        COL_CORR: DISPLAY_CORR,
        COL_SLOPE: DISPLAY_SLOPE,
        COL_INTERCEPT: DISPLAY_INTERCEPT,
        COL_MAX_ABS_DIFF: DISPLAY_MAX_ABS_DIFF,
        COL_MEAN_ABS_DIFF: DISPLAY_MEAN_ABS_DIFF,
        COL_STD_DIFF: DISPLAY_STD_DIFF,
    }
    full_summary = full_summary.rename(columns=rename_map)

    # 7. 수치 컬럼 라운딩 (4자리 통일)
    numeric_cols = [
        DISPLAY_CORR,
        DISPLAY_SLOPE,
        DISPLAY_INTERCEPT,
        DISPLAY_MAX_ABS_DIFF,
        DISPLAY_MEAN_ABS_DIFF,
        DISPLAY_STD_DIFF,
    ]
    for col in numeric_cols:
        if col in full_summary.columns:
            full_summary[col] = full_summary[col].round(4)

    # 8. CSV 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    full_summary.to_csv(output_path, index=False, encoding="utf-8")
    logger.debug(f"요약 통계 CSV 저장 완료: {output_path} ({len(full_summary)}행)")


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


def add_rolling_features(
    df_monthly: pd.DataFrame,
    window: int = DEFAULT_ROLLING_WINDOW,
) -> pd.DataFrame:
    """
    rolling 파생피처를 생성한다.

    금리/오차 관계의 "최근 안정성"을 모델이 학습할 수 있도록 rolling correlation을 계산한다.
    데이터 길이가 window 미만이면 fail-fast 정책에 따라 예외를 발생시킨다.

    Rolling correlation 계산 대상:
        - rate_level_pct(=rate_pct) vs error_eom_pct(=e_m)
        - rate_change_pct(=dr_m) vs error_change_pct(=de_m)
        - rate_change_lag1_pct vs error_change_pct
        - rate_change_lag2_pct vs error_change_pct

    Args:
        df_monthly: 월별 DataFrame
            필수 컬럼: rate_pct, dr_m, e_m, de_m, dr_lag1, dr_lag2
        window: rolling window 크기 (기본값: 12)

    Returns:
        rolling correlation 컬럼이 추가된 DataFrame
        - rolling_corr_rate_level_error_eom
        - rolling_corr_rate_change_error_change
        - rolling_corr_rate_lag1_error_change
        - rolling_corr_rate_lag2_error_change

    Raises:
        ValueError: 데이터 길이가 window 미만인 경우 (fail-fast)
    """
    # 데이터 길이 검증 (fail-fast)
    if len(df_monthly) < window:
        raise ValueError(f"데이터 부족: {len(df_monthly)}개월 < window {window}개월\n" f"조치: 더 긴 기간의 데이터 필요")

    # 원본 불변성 보장
    result = df_monthly.copy()

    # Rolling correlation 계산
    # min_periods = window로 설정하여 불완전 window 허용 금지
    # 1. rate_level_pct vs error_eom_pct
    result[COL_MODEL_ROLLING_CORR_LEVEL] = (
        result[COL_RATE_PCT].rolling(window=window, min_periods=window).corr(result[COL_E_M])
    )

    # 2. rate_change_pct vs error_change_pct
    result[COL_MODEL_ROLLING_CORR_DELTA] = (
        result[COL_DR_M].rolling(window=window, min_periods=window).corr(result[COL_DE_M])
    )

    # 3. rate_change_lag1_pct vs error_change_pct
    if COL_DR_LAG1 in result.columns:
        result[COL_MODEL_ROLLING_CORR_LAG1] = (
            result[COL_DR_LAG1].rolling(window=window, min_periods=window).corr(result[COL_DE_M])
        )
    else:
        result[COL_MODEL_ROLLING_CORR_LAG1] = pd.NA

    # 4. rate_change_lag2_pct vs error_change_pct
    if COL_DR_LAG2 in result.columns:
        result[COL_MODEL_ROLLING_CORR_LAG2] = (
            result[COL_DR_LAG2].rolling(window=window, min_periods=window).corr(result[COL_DE_M])
        )
    else:
        result[COL_MODEL_ROLLING_CORR_LAG2] = pd.NA

    return result


def build_model_dataset(
    df_monthly: pd.DataFrame,
    window: int = DEFAULT_ROLLING_WINDOW,
) -> pd.DataFrame:
    """
    AI 모델이 읽을 수 있는 고정 스키마의 모델용 DataFrame을 생성한다.

    내부에서 add_rate_change_lags(), add_rolling_features()를 호출하여
    lag 및 rolling 피처를 생성한 후, 영문 컬럼명으로 변환하고 schema_version을 추가한다.

    Args:
        df_monthly: 월별 DataFrame
            필수 컬럼: month, rate_pct, dr_m, e_m, de_m, sum_daily_m
        window: rolling window 크기 (기본값: 12)

    Returns:
        모델용 DataFrame (영문 컬럼, schema_version 포함)

    Raises:
        ValueError: 필수 컬럼 누락 또는 데이터 부족 시
    """
    # 필수 컬럼 검증
    required_cols = [COL_MONTH, COL_RATE_PCT, COL_DR_M, COL_E_M, COL_DE_M, COL_SUM_DAILY_M]
    missing = [col for col in required_cols if col not in df_monthly.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 1. lag 피처 생성
    df_with_lags = add_rate_change_lags(df_monthly)

    # 2. rolling 피처 생성
    df_with_rolling = add_rolling_features(df_with_lags, window=window)

    # 3. cv_diff_pct 계산 (error_change_pct - error_daily_sum_pct)
    df_with_rolling[COL_MODEL_CV_DIFF_PCT] = df_with_rolling[COL_DE_M] - df_with_rolling[COL_SUM_DAILY_M]

    # 4. 모델용 컬럼 선택 및 rename
    # 내부 컬럼 -> 모델용 영문 컬럼
    rename_map = {
        COL_MONTH: COL_MODEL_MONTH,
        COL_RATE_PCT: COL_MODEL_RATE_LEVEL_PCT,
        COL_DR_M: COL_MODEL_RATE_CHANGE_PCT,
        COL_DR_LAG1: COL_MODEL_RATE_CHANGE_LAG1_PCT,
        COL_DR_LAG2: COL_MODEL_RATE_CHANGE_LAG2_PCT,
        COL_E_M: COL_MODEL_ERROR_EOM_PCT,
        COL_DE_M: COL_MODEL_ERROR_CHANGE_PCT,
        COL_SUM_DAILY_M: COL_MODEL_ERROR_DAILY_SUM_PCT,
        # COL_MODEL_CV_DIFF_PCT는 이미 영문명으로 생성됨
        # rolling 컬럼도 이미 영문명으로 생성됨
    }

    # 선택할 컬럼 목록
    cols_to_select = [
        COL_MONTH,
        COL_RATE_PCT,
        COL_DR_M,
        COL_DR_LAG1,
        COL_DR_LAG2,
        COL_E_M,
        COL_DE_M,
        COL_SUM_DAILY_M,
        COL_MODEL_CV_DIFF_PCT,
        COL_MODEL_ROLLING_CORR_LEVEL,
        COL_MODEL_ROLLING_CORR_DELTA,
        COL_MODEL_ROLLING_CORR_LAG1,
        COL_MODEL_ROLLING_CORR_LAG2,
    ]

    result = df_with_rolling[cols_to_select].copy()
    result = result.rename(columns=rename_map)

    # 5. schema_version 컬럼 추가
    result[COL_MODEL_SCHEMA_VERSION] = MODEL_SCHEMA_VERSION

    # 6. month를 문자열로 변환 (CSV 호환성)
    result[COL_MODEL_MONTH] = result[COL_MODEL_MONTH].astype(str)

    # 7. 컬럼 순서 정리 (schema_version을 두 번째에)
    col_order = [
        COL_MODEL_MONTH,
        COL_MODEL_SCHEMA_VERSION,
        COL_MODEL_RATE_LEVEL_PCT,
        COL_MODEL_RATE_CHANGE_PCT,
        COL_MODEL_RATE_CHANGE_LAG1_PCT,
        COL_MODEL_RATE_CHANGE_LAG2_PCT,
        COL_MODEL_ERROR_EOM_PCT,
        COL_MODEL_ERROR_CHANGE_PCT,
        COL_MODEL_ERROR_DAILY_SUM_PCT,
        COL_MODEL_CV_DIFF_PCT,
        COL_MODEL_ROLLING_CORR_LEVEL,
        COL_MODEL_ROLLING_CORR_DELTA,
        COL_MODEL_ROLLING_CORR_LAG1,
        COL_MODEL_ROLLING_CORR_LAG2,
    ]
    result = result[col_order]

    return result


def save_model_csv(df_model: pd.DataFrame, output_path: Path) -> None:
    """
    모델용 DataFrame을 CSV로 저장한다.

    모든 수치 컬럼을 4자리로 라운딩하고, month 기준 오름차순 정렬 후 저장한다.

    Args:
        df_model: 모델용 DataFrame (영문 컬럼)
        output_path: 출력 CSV 파일 경로

    Raises:
        ValueError: 필수 컬럼 누락 시
    """
    # 필수 컬럼 검증
    required_cols = [COL_MODEL_MONTH, COL_MODEL_SCHEMA_VERSION]
    missing = [col for col in required_cols if col not in df_model.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 복사 및 정렬
    df_to_save = df_model.copy()
    df_to_save = df_to_save.sort_values(COL_MODEL_MONTH).reset_index(drop=True)

    # 수치 컬럼 라운딩 (4자리)
    # None/object 타입 컬럼은 먼저 numeric으로 변환 후 라운딩
    numeric_cols = [
        COL_MODEL_RATE_LEVEL_PCT,
        COL_MODEL_RATE_CHANGE_PCT,
        COL_MODEL_RATE_CHANGE_LAG1_PCT,
        COL_MODEL_RATE_CHANGE_LAG2_PCT,
        COL_MODEL_ERROR_EOM_PCT,
        COL_MODEL_ERROR_CHANGE_PCT,
        COL_MODEL_ERROR_DAILY_SUM_PCT,
        COL_MODEL_CV_DIFF_PCT,
        COL_MODEL_ROLLING_CORR_LEVEL,
        COL_MODEL_ROLLING_CORR_DELTA,
        COL_MODEL_ROLLING_CORR_LAG1,
        COL_MODEL_ROLLING_CORR_LAG2,
    ]
    for col in numeric_cols:
        if col in df_to_save.columns:
            # object 타입이면 numeric으로 변환 (None -> NaN)
            if df_to_save[col].dtype == "object":
                df_to_save[col] = pd.to_numeric(df_to_save[col], errors="coerce")
            df_to_save[col] = df_to_save[col].round(4)

    # CSV 저장
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_to_save.to_csv(output_path, index=False, encoding="utf-8")
    logger.debug(f"모델용 CSV 저장 완료: {output_path} ({len(df_to_save)}행)")
