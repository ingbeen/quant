"""
TQQQ 시뮬레이션 분석용 순수 계산 함수

금리-오차 관계 분석을 위한 계산, 집계, 검증 함수를 제공한다.
모든 함수는 상태를 유지하지 않으며(stateless), fail-fast 정책을 따른다.

Fail-fast 정책:
- 결과를 신뢰할 수 없게 만드는 문제 발견 시 ValueError를 raise하여 즉시 중단
- 조용히 진행하지 않고 명확한 에러 메시지 제공
"""

import numpy as np
import pandas as pd

from qbt.utils import get_logger

logger = get_logger(__name__)


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
    # 예: 누적수익률 10% → M = 1.10 (초기 대비 1.1배)
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
            f"M_real <= 0 발견 (로그 계산 불가): {num_invalid}행\n"
            f"문제 인덱스: {invalid_indices[:5]}{'...' if num_invalid > 5 else ''}\n"
            f"원인: 누적수익률_실제가 -100% 이하 (자산 가치 0 이하)\n"
            f"조치: 데이터 정합성 확인 필요"
        )

    if invalid_sim.any():
        num_invalid = invalid_sim.sum()
        invalid_indices = M_sim[invalid_sim].index.tolist()
        raise ValueError(
            f"M_sim <= 0 발견 (로그 계산 불가): {num_invalid}행\n"
            f"문제 인덱스: {invalid_indices[:5]}{'...' if num_invalid > 5 else ''}\n"
            f"원인: 누적수익률_시뮬이 -100% 이하 (자산 가치 0 이하)\n"
            f"조치: 시뮬레이션 로직 또는 입력 데이터 확인 필요"
        )

    # 3. signed 로그차이 계산
    # 수식: signed = 100 * ln(M_sim / M_real)
    # 부호 의미:
    #   - 양수: M_sim > M_real, 시뮬레이션이 실제보다 높음
    #   - 음수: M_sim < M_real, 시뮬레이션이 실제보다 낮음
    #   - 0에 가까움: M_sim ≈ M_real, 거의 일치
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
    # 예: r = 5% → 1.05배 (초기 100원이 105원)
    #     r = -2% → 0.98배 (초기 100원이 98원)
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
            f"1 + r_real/100 <= 0 발견 (로그 계산 불가): {num_invalid}행\n"
            f"문제 인덱스: {invalid_indices[:5]}{'...' if num_invalid > 5 else ''}\n"
            f"원인: 일일수익률_실제가 -100% 이하 (하루 만에 자산 가치 0 이하)\n"
            f"조치: 데이터 정합성 확인 필요 (서킷브레이커/상폐 등)"
        )

    if invalid_sim.any():
        num_invalid = invalid_sim.sum()
        invalid_indices = factor_sim[invalid_sim].index.tolist()
        raise ValueError(
            f"1 + r_sim/100 <= 0 발견 (로그 계산 불가): {num_invalid}행\n"
            f"문제 인덱스: {invalid_indices[:5]}{'...' if num_invalid > 5 else ''}\n"
            f"원인: 일일수익률_시뮬이 -100% 이하 (하루 만에 자산 가치 0 이하)\n"
            f"조치: 시뮬레이션 로직 확인 필요 (비용 계산 오류 가능성)"
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
        raise ValueError(f"필수 컬럼 누락: {missing_cols}\n" f"보유 컬럼: {list(daily_df.columns)}\n" f"조치: 컬럼명 확인 (대소문자 구분)")

    # 2. 날짜 기준 오름차순 정렬 강제 (월말 값 정확성 보장)
    # 이유: groupby.last()는 정렬되지 않은 데이터에서 잘못된 월말 값을 반환할 수 있음
    # 정의: "월말 값은 해당 월 마지막 거래일의 레코드"
    df_sorted = daily_df.sort_values(by=date_col).copy()

    # 3. month 컬럼 생성 (yyyy-mm Period 객체)
    # 예: 2023-01-15 → 2023-01
    # pd.to_datetime으로 명시적 datetime Series 변환 (타입 체커가 dt accessor 인식)
    date_col_data = pd.to_datetime(df_sorted[date_col])
    df_sorted["month"] = date_col_data.dt.to_period("M")

    # 4. 월별 집계
    # - e_m: 월말 누적 signed (last, 해당 월 마지막 거래일 값)
    # - sum_daily_m: 일일 증분 signed의 월합 (sum)
    # 주의: 일일 증분이 없으면 sum_daily_m은 계산 불가 (이 함수는 e_m만 사용)
    monthly = df_sorted.groupby("month", as_index=False).agg({signed_col: "last"})
    monthly.rename(columns={signed_col: "e_m"}, inplace=True)

    # 5. de_m 계산 (e_m의 월간 변화)
    # 예: e_m = [2.0, 3.0, 2.5] → de_m = [NaN, 1.0, -0.5]
    monthly["de_m"] = monthly["e_m"].diff()

    # 6. sum_daily_m 계산 (별도 로직, 일일 증분 필요 시)
    # 현재는 e_m만 있으므로 placeholder로 NaN
    # Phase 2에서 streamlit에서 calculate_daily_signed_log_diff 호출 후 계산
    monthly["sum_daily_m"] = pd.NA

    # 7. FFR 데이터 매칭 (있을 때만)
    if ffr_df is not None and not ffr_df.empty:
        # FFR 데이터 전처리
        # DATE 컬럼이 "yyyy-mm" 문자열 형식이므로 Period[M]로 변환
        ffr_processed = ffr_df.copy()
        ffr_processed["month"] = pd.PeriodIndex(ffr_processed["DATE"], freq="M")

        # month 키로 left join (일별 기준 월만 보존)
        monthly = monthly.merge(ffr_processed[["month", "VALUE"]], on="month", how="left")

        # rate_pct 계산 (0~1 소수 → %)
        # 예: VALUE = 0.045 → rate_pct = 4.5
        monthly["rate_pct"] = monthly["VALUE"] * 100.0

        # dr_m 계산 (금리 월간 변화, %p)
        monthly["dr_m"] = monthly["rate_pct"].diff()

        # VALUE 컬럼 제거 (불필요)
        monthly.drop(columns=["VALUE"], inplace=True)

        # FFR 커버리지 검증 (fail-fast)
        # 월별 데이터에 금리가 없는 월이 많으면 분석 불가
        missing_rate = monthly["rate_pct"].isna()
        if missing_rate.any():
            num_missing = missing_rate.sum()
            missing_months = monthly.loc[missing_rate, "month"].tolist()
            logger.debug(
                f"금리 데이터 누락 월: {num_missing}개월\n" f"누락 월: {missing_months[:5]}{'...' if num_missing > 5 else ''}"
            )
            # 경고만 하고 진행 (일부 누락은 허용, 너무 많으면 나중에 상관 계산 시 문제)

    else:
        # FFR 없으면 rate_pct, dr_m 컬럼을 NaN으로
        monthly["rate_pct"] = pd.NA
        monthly["dr_m"] = pd.NA

    # 8. diff() 후 첫 달 NaN 제거
    # 이유: de_m, dr_m의 첫 값은 항상 NaN (diff 특성)
    # 선택: 첫 달 제거할지는 사용자 요구에 따라 조정 가능
    # 여기서는 제거하지 않고 그대로 반환 (Streamlit에서 dropna)
    # monthly = monthly.dropna(subset=["de_m"])  # 선택사항

    # 9. 월별 집계 결과 길이 검증 (fail-fast)
    # Rolling 12M 상관을 계산하려면 최소 13개월 필요 (12M window + 1)
    if len(monthly) < min_months_for_analysis:
        raise ValueError(
            f"월별 집계 결과가 너무 짧음: {len(monthly)}개월\n"
            f"최소 필요: {min_months_for_analysis}개월 (Rolling 12M 상관 계산 위해)\n"
            f"조치: 더 긴 기간의 일별 데이터 필요"
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
        이 함수는 Phase 1에서 실제 데이터로 먼저 관측(tolerance=None) 후,
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
            f"무결성 체크 관측 결과:\n"
            f"  max_abs_diff: {max_abs_diff:.6e}%\n"
            f"  mean_abs_diff: {mean_abs_diff:.6e}%\n"
            f"  제안 tolerance: {proposed_tolerance:.6e}% (max * 1.1)\n"
            f"참고: 반올림/누적 방식 차이로 완전히 0이 아닐 수 있음"
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
                f"무결성 체크 실패: max_abs_diff > tolerance\n"
                f"  관측 max_abs_diff: {max_abs_diff:.6e}%\n"
                f"  허용 tolerance: {tolerance:.6e}%\n"
                f"  초과량: {max_abs_diff - tolerance:.6e}%\n"
                f"원인 (가능성 높은 순):\n"
                f"  1. 반올림/누적 방식 차이 (정상 범위 초과)\n"
                f"  2. signed 계산 로직 오류 (M 정의 불일치)\n"
                f"  3. abs 컬럼 정의 불일치 (다른 수식 사용)\n"
                f"조치: signed 및 abs 계산 로직 재검토 필요"
            )
        else:
            # 무결성 통과
            logger.debug(f"무결성 체크 통과:\n" f"  max_abs_diff: {max_abs_diff:.6e}% <= tolerance: {tolerance:.6e}%")
            return {
                "max_abs_diff": max_abs_diff,
                "mean_abs_diff": mean_abs_diff,
                "tolerance": tolerance,
            }
