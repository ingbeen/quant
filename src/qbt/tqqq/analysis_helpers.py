"""
TQQQ 시뮬레이션 분석용 순수 계산 함수

금리-오차 관계 분석을 위한 계산 · 집계 함수를 제공한다.
모든 함수는 상태를 유지하지 않으며(stateless), fail-fast 정책을 따른다.

Fail-fast 정책:
- 결과를 신뢰할 수 없게 만드는 문제 발견 시 ValueError를 raise하여 즉시 중단
- 조용히 진행하지 않고 명확한 에러 메시지 제공
"""

from datetime import date

import numpy as np
import pandas as pd

from qbt.tqqq.constants import (
    COL_DE_M,
    COL_DR_M,
    COL_E_M,
    COL_MONTH,
    COL_RATE_PCT,
)
from qbt.tqqq.data_loader import create_ffr_dict, lookup_ffr

__all__ = [
    "calculate_signed_log_diff_from_cumulative_returns",
    "calculate_daily_signed_log_diff",
    "aggregate_monthly",
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
            - 에러 메시지에 문제 행 수와 앞 5개 인덱스 포함

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
            - 에러 메시지에 문제 행 수와 앞 5개 인덱스 포함

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
    ffr_df: pd.DataFrame,
    min_months_for_analysis: int,
) -> pd.DataFrame:
    """
    일별 데이터를 월별로 집계하고 금리 데이터와 매칭한다.

    월말(last) 누적 signed 값과 그 월간 변화, 금리 수준/변화를 계산한다.
    금리 데이터 매칭은 딕셔너리 기반 조회 + MAX_FFR_MONTHS_DIFF fallback으로 수행된다.

    처리 흐름:
        1. 날짜 기준 오름차순 정렬 (월말 값 정확성 보장)
        2. month = 날짜.to_period("M") 생성
        3. e_m: 월말 누적 signed (last)
        4. de_m: e_m의 월간 변화 (diff)
        5. FFR 딕셔너리 기반 조회 (MAX_FFR_MONTHS_DIFF fallback, 초과 시 ValueError)
        6. rate_pct, dr_m 계산

    FFR 매칭 정책:
        - 해당 월 FFR이 존재하면 직접 사용
        - 없으면 최대 MAX_FFR_MONTHS_DIFF 이전 값 fallback
        - 갭 초과 시 ValueError (fail-fast)
        - data_loader.py의 lookup_ffr과 동일한 정책

    Args:
        daily_df: 일별 데이터 (날짜, signed 컬럼 필수)
        date_col: 날짜 컬럼명
        signed_col: signed 컬럼명
        ffr_df: 금리 데이터 (DATE: yyyy-mm 문자열, VALUE: 0~1 소수)
        min_months_for_analysis: 최소 필요 월 수

    Returns:
        월별 DataFrame (month, e_m, de_m, rate_pct, dr_m)
        - month: Period[M] (yyyy-mm)
        - e_m: 월말 누적 signed (%)
        - de_m: 월간 변화 (%)
        - rate_pct: 금리 수준 (%)
        - dr_m: 금리 월간 변화 (%p)

    Raises:
        ValueError: 아래 조건 중 하나라도 해당하면 fail-fast
            - 필수 컬럼 누락, daily_df 또는 ffr_df가 비어있음
            - FFR 데이터 갭이 MAX_FFR_MONTHS_DIFF 초과
            - 월별 집계 결과가 min_months_for_analysis 미만

    Note:
        월말 값 정의: "해당 월 마지막 거래일의 레코드"
        정렬이 보장되지 않으면 잘못된 월말 값이 추출될 수 있으므로 함수 내부에서 강제 정렬
    """
    # 1. 필수 컬럼 검증 (fail-fast)
    if daily_df.empty:
        raise ValueError("daily_df가 비어있음 (월별 집계 불가)")

    required_cols = [date_col, signed_col]
    missing_cols = sorted(set(required_cols) - set(daily_df.columns))

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

    # 4. 월별 집계 — e_m: 월말 누적 signed (last, 해당 월 마지막 거래일 값)
    monthly = df_sorted.groupby(COL_MONTH, as_index=False).agg({signed_col: "last"})
    monthly = monthly.rename(columns={signed_col: COL_E_M})

    # 5. de_m 계산 (e_m의 월간 변화)
    # 예: e_m = [2.0, 3.0, 2.5] -> de_m = [NaN, 1.0, -0.5]
    monthly[COL_DE_M] = monthly[COL_E_M].diff()

    # 6. FFR 데이터 매칭
    # 딕셔너리 기반 조회 + MAX_FFR_MONTHS_DIFF fallback + fail-fast (lookup_ffr와 동일한 정책)
    ffr_dict = create_ffr_dict(ffr_df)

    # Period 객체를 date로 변환하여 lookup_ffr 호출
    ffr_values: list[float] = []
    for period in monthly[COL_MONTH]:
        date_value = date(period.year, period.month, 1)
        ffr_value = lookup_ffr(date_value, ffr_dict)
        ffr_values.append(ffr_value)

    # rate_pct 계산 (0~1 소수 -> %)
    # 예: VALUE = 0.045 -> rate_pct = 4.5
    monthly[COL_RATE_PCT] = [v * 100.0 for v in ffr_values]

    # dr_m 계산 (금리 월간 변화, %p)
    monthly[COL_DR_M] = monthly[COL_RATE_PCT].diff()

    # 7. 월별 집계 결과 길이 검증 (fail-fast)
    if len(monthly) < min_months_for_analysis:
        raise ValueError(
            f"월별 집계 결과가 너무 짧음: {len(monthly)}개월\n최소 필요: {min_months_for_analysis}개월\n조치: 더 긴 기간의 일별 데이터 필요"
        )

    return monthly
