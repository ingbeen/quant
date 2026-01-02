"""
tqqq/analysis_helpers 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 누적수익률 → signed 로그차이 계산이 정확한가?
2. 일일수익률 → 일일 signed 로그차이 계산이 정확한가?
3. abs(signed)와 abs 컬럼의 무결성 체크가 정확한가?
4. 월별 집계 (de_m, sum_daily_m) 로직이 정확한가?
5. Fail-fast 정책이 제대로 작동하는가? (M <= 0, 1+r <= 0 등)

왜 중요한가요?
금리-오차 관계 분석의 모든 계산이 이 함수들에 의존합니다.
계산 오류는 잘못된 분석 결과로 이어져 spread 조정 판단을 오도할 수 있습니다.
Fail-fast 정책은 잘못된 결과가 조용히 생성되는 것을 방지합니다.

Note:
    모든 테스트는 synthetic(고정) 데이터를 사용하여 결정적(deterministic)으로 작성됩니다.
    "실제 데이터에서 M이 1.xx인지" 같은 전제 확인은 런타임 로그로만 수행됩니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.tqqq.analysis_helpers import (
    aggregate_monthly,
    calculate_daily_signed_log_diff,
    calculate_signed_log_diff_from_cumulative_returns,
    validate_integrity,
)


class TestCalculateSignedLogDiffFromCumulativeReturns:
    """누적수익률 → signed 로그차이 계산 테스트"""

    def test_normal_signed_calculation(self):
        """
        정상적인 signed 계산 테스트

        계산 정확성: M = 1 + 누적수익률(%)/100 변환 후 ln(M_sim/M_real) 계산

        Given:
            - 누적수익률_실제 = [10.0, 20.0, 30.0]%
            - 누적수익률_시뮬 = [11.0, 21.0, 31.0]%
        When: calculate_signed_log_diff_from_cumulative_returns 호출
        Then:
            - M_real = [1.10, 1.20, 1.30]
            - M_sim = [1.11, 1.21, 1.31]
            - signed = 100 * ln(M_sim / M_real)
            - 모든 값이 양수 (시뮬이 실제보다 높음)
        """
        # Given: synthetic 데이터 (%)
        import numpy as np

        cumul_real = pd.Series([10.0, 20.0, 30.0], name="cumul_real")
        cumul_sim = pd.Series([11.0, 21.0, 31.0], name="cumul_sim")

        # When
        signed = calculate_signed_log_diff_from_cumulative_returns(cumul_real, cumul_sim)

        # Then: 예상 결과 계산
        # M_real = 1 + cumul_real / 100 = [1.10, 1.20, 1.30]
        # M_sim = 1 + cumul_sim / 100 = [1.11, 1.21, 1.31]
        # signed = 100 * ln(M_sim / M_real)
        expected = 100 * np.log(np.array([1.11 / 1.10, 1.21 / 1.20, 1.31 / 1.30]))
        assert np.allclose(signed.to_numpy(), expected, rtol=1e-6)
        assert (signed > 0).all(), "시뮬이 실제보다 높으므로 모두 양수여야 함"

    def test_sim_lower_than_real_gives_negative_signed(self):
        """
        시뮬레이션이 실제보다 낮을 때 음수 signed 반환

        부호 의미: signed < 0이면 시뮬이 실제보다 낮음을 의미

        Given:
            - 누적수익률_실제 = [10.0, 20.0]%
            - 누적수익률_시뮬 = [9.0, 18.0]% (실제보다 낮음)
        When: calculate_signed_log_diff_from_cumulative_returns
        Then: signed는 모두 음수
        """
        # Given
        cumul_real = pd.Series([10.0, 20.0])
        cumul_sim = pd.Series([9.0, 18.0])  # 실제보다 낮음

        # When
        signed = calculate_signed_log_diff_from_cumulative_returns(cumul_real, cumul_sim)

        # Then
        assert (signed < 0).all(), "시뮬이 실제보다 낮으므로 모두 음수여야 함"

    def test_fail_fast_when_m_real_is_zero_or_negative(self):
        """
        M_real <= 0일 때 fail-fast (ValueError)

        Fail-fast 정책: 로그 계산 불가능한 경우 즉시 중단

        Given:
            - 누적수익률_실제 = [-100.0, 10.0]% (첫 값 -100%는 M=0)
            - 누적수익률_시뮬 = [10.0, 20.0]%
        When: calculate_signed_log_diff_from_cumulative_returns
        Then: ValueError raise (로그 계산 불가, M_real <= 0)
        """
        # Given: M_real = 1 + (-100)/100 = 0 (로그 불가)
        cumul_real = pd.Series([-100.0, 10.0])
        cumul_sim = pd.Series([10.0, 20.0])

        # When & Then
        with pytest.raises(ValueError, match="로그 계산 불가"):
            calculate_signed_log_diff_from_cumulative_returns(cumul_real, cumul_sim)

    def test_fail_fast_when_m_sim_is_zero_or_negative(self):
        """
        M_sim <= 0일 때 fail-fast (ValueError)

        Given:
            - 누적수익률_실제 = [10.0, 20.0]%
            - 누적수익률_시뮬 = [-101.0, 10.0]% (첫 값 M < 0)
        When: calculate_signed_log_diff_from_cumulative_returns
        Then: ValueError raise
        """
        # Given
        cumul_real = pd.Series([10.0, 20.0])
        cumul_sim = pd.Series([-101.0, 10.0])  # M_sim = -0.01 < 0

        # When & Then
        with pytest.raises(ValueError, match="로그 계산 불가"):
            calculate_signed_log_diff_from_cumulative_returns(cumul_real, cumul_sim)


class TestCalculateDailySignedLogDiff:
    """일일수익률 → 일일 signed 로그차이 계산 테스트"""

    def test_normal_daily_signed_calculation(self):
        """
        정상적인 일일 signed 계산

        계산 정확성: 100 * ln((1 + r_sim/100) / (1 + r_real/100))

        Given:
            - 일일수익률_실제 = [1.0, 2.0, -1.0]% (양수/음수 혼합)
            - 일일수익률_시뮬 = [1.5, 2.5, -0.5]% (실제보다 약간 높음)
        When: calculate_daily_signed_log_diff
        Then:
            - signed = 100 * ln((1 + r_sim/100) / (1 + r_real/100))
            - 모든 값이 양수 (시뮬이 더 벌었음)
        """
        # Given: % 단위
        import numpy as np

        daily_real = pd.Series([1.0, 2.0, -1.0])
        daily_sim = pd.Series([1.5, 2.5, -0.5])  # 항상 실제보다 0.5%p 높음

        # When
        signed = calculate_daily_signed_log_diff(daily_real, daily_sim)

        # Then
        expected = 100 * np.log((1 + daily_sim / 100) / (1 + daily_real / 100))
        assert np.allclose(signed.to_numpy(), expected, rtol=1e-6)
        assert (signed > 0).all(), "시뮬이 더 벌었으므로 모두 양수"

    def test_fail_fast_when_1_plus_r_real_is_zero_or_negative(self):
        """
        1 + r_real/100 <= 0일 때 fail-fast

        Fail-fast: 일일수익률이 -100% 이하면 로그 계산 불가

        Given:
            - 일일수익률_실제 = [-100.0, 1.0]% (첫 값 -100%는 1+r=0)
            - 일일수익률_시뮬 = [1.0, 2.0]%
        When: calculate_daily_signed_log_diff
        Then: ValueError raise
        """
        # Given
        daily_real = pd.Series([-100.0, 1.0])  # 1 + (-100)/100 = 0
        daily_sim = pd.Series([1.0, 2.0])

        # When & Then
        with pytest.raises(ValueError, match="로그 계산 불가"):
            calculate_daily_signed_log_diff(daily_real, daily_sim)

    def test_fail_fast_when_1_plus_r_sim_is_zero_or_negative(self):
        """
        1 + r_sim/100 <= 0일 때 fail-fast

        Given:
            - 일일수익률_실제 = [1.0, 2.0]%
            - 일일수익률_시뮬 = [-105.0, 1.0]% (첫 값 M < 0)
        When: calculate_daily_signed_log_diff
        Then: ValueError raise
        """
        # Given
        daily_real = pd.Series([1.0, 2.0])
        daily_sim = pd.Series([-105.0, 1.0])  # 1 + (-105)/100 = -0.05

        # When & Then
        with pytest.raises(ValueError, match="로그 계산 불가"):
            calculate_daily_signed_log_diff(daily_real, daily_sim)


class TestValidateIntegrity:
    """abs(signed) vs abs 무결성 체크 테스트"""

    def test_integrity_check_passes_when_diff_is_small(self):
        """
        차이가 작을 때 무결성 체크 통과

        Given:
            - signed = [1.234, -2.345, 3.456]
            - abs_col = [1.234, 2.345, 3.456] (완전히 일치)
            - tolerance = 1e-6
        When: validate_integrity
        Then:
            - max_abs_diff, mean_abs_diff 반환
            - ValueError raise 안 함
        """
        # Given: 완전히 일치하는 경우
        signed = pd.Series([1.234, -2.345, 3.456])
        abs_col = pd.Series([1.234, 2.345, 3.456])  # abs(signed)와 동일
        tolerance = 1e-6

        # When
        result = validate_integrity(signed, abs_col, tolerance)

        # Then
        assert result["max_abs_diff"] < tolerance
        assert result["mean_abs_diff"] < tolerance

    def test_integrity_check_observes_when_tolerance_is_none(self):
        """
        tolerance=None일 때 관측만 수행 (ValueError 안 냄)

        Given:
            - signed, abs_col (약간의 차이)
            - tolerance = None
        When: validate_integrity
        Then:
            - max_abs_diff, mean_abs_diff 반환
            - ValueError raise 안 함 (관측 모드)
        """
        # Given
        signed = pd.Series([1.234, -2.345, 3.456])
        abs_col = pd.Series([1.235, 2.346, 3.457])  # 약간 다름
        tolerance = None

        # When
        result = validate_integrity(signed, abs_col, tolerance)

        # Then
        assert "max_abs_diff" in result
        assert "mean_abs_diff" in result
        assert result["max_abs_diff"] > 0  # 차이 존재

    def test_fail_fast_when_diff_exceeds_tolerance(self):
        """
        차이가 tolerance를 초과하면 fail-fast

        Fail-fast: abs(signed)와 abs가 크게 다르면 계산 오류 의심

        Given:
            - signed = [1.0, -2.0]
            - abs_col = [1.5, 2.5] (큰 차이)
            - tolerance = 0.1
        When: validate_integrity
        Then: ValueError raise (max_abs_diff > tolerance)
        """
        # Given
        signed = pd.Series([1.0, -2.0])
        abs_col = pd.Series([1.5, 2.5])  # 0.5 차이 (tolerance 0.1 초과)
        tolerance = 0.1

        # When & Then
        with pytest.raises(ValueError, match="tolerance"):
            validate_integrity(signed, abs_col, tolerance)


class TestAggregateMonthly:
    """월별 집계 테스트"""

    def test_normal_monthly_aggregation(self):
        """
        정상적인 월별 집계

        월말(last) 정렬: 날짜 오름차순 정렬 후 월말 값 추출

        Given:
            - 일별 데이터 (3일, 2개월: 2023-01-15, 2023-01-31, 2023-02-15)
            - signed 값: [1.0, 2.0, 3.0]
        When: aggregate_monthly
        Then:
            - 2023-01: e_m=2.0 (월말)
            - 2023-02: e_m=3.0 (월말)
            - de_m: NaN, 1.0 (3.0 - 2.0)
        """
        # Given: synthetic 일별 데이터 (datetime으로 변환)
        daily_df = pd.DataFrame(
            {
                "Date": pd.to_datetime([date(2023, 1, 15), date(2023, 1, 31), date(2023, 2, 15)]),
                "signed": [1.0, 2.0, 3.0],
            }
        )

        # When
        monthly = aggregate_monthly(
            daily_df, date_col="Date", signed_col="signed", ffr_df=None, min_months_for_analysis=1
        )

        # Then: 예상 결과
        assert len(monthly) == 2  # 2개월
        assert monthly.loc[0, "e_m"] == 2.0  # 2023-01 월말
        assert monthly.loc[1, "e_m"] == 3.0  # 2023-02 월말

        # 첫 달은 NaN, 두 번째 달은 차이값 확인
        de_m_values = monthly["de_m"].tolist()
        assert pd.isna(de_m_values[0])  # 첫 달은 NaN
        assert de_m_values[1] == pytest.approx(1.0)  # 3.0 - 2.0

    def test_sorting_enforced_for_correct_month_end(self):
        """
        월말(last) 추출 전 정렬 강제 확인

        정렬 전제: 날짜가 뒤죽박죽이어도 함수 내부에서 정렬 후 월말 추출

        Given:
            - 일별 데이터가 정렬되지 않음 (2023-01-31, 2023-01-15 순)
        When: aggregate_monthly
        Then: 정렬 후 월말 값 정확히 추출 (2.0이어야 함, 1.0 아님)
        """
        # Given: 정렬 안 된 데이터 (월말이 먼저, datetime으로 변환)
        daily_df = pd.DataFrame(
            {
                "Date": pd.to_datetime([date(2023, 1, 31), date(2023, 1, 15)]),  # 역순
                "signed": [2.0, 1.0],
            }
        )

        # When
        monthly = aggregate_monthly(
            daily_df, date_col="Date", signed_col="signed", ffr_df=None, min_months_for_analysis=1
        )

        # Then
        assert monthly.loc[0, "e_m"] == 2.0  # 정렬 후 월말이므로 2.0

    def test_fail_fast_when_required_columns_missing(self):
        """
        필수 컬럼 누락 시 fail-fast

        Given:
            - daily_df에 signed 컬럼 없음
        When: aggregate_monthly
        Then: ValueError raise (필수 컬럼 누락)
        """
        # Given: signed 컬럼 없음
        daily_df = pd.DataFrame({"Date": pd.to_datetime([date(2023, 1, 15)])})

        # When & Then
        with pytest.raises(ValueError, match="필수 컬럼"):
            aggregate_monthly(daily_df, date_col="Date", signed_col="signed", ffr_df=None)

    def test_fail_fast_when_daily_df_is_empty(self):
        """
        빈 DataFrame일 때 fail-fast

        Given:
            - daily_df가 비어있음
        When: aggregate_monthly
        Then: ValueError raise
        """
        # Given
        daily_df = pd.DataFrame({"Date": pd.to_datetime([]), "signed": []})

        # When & Then
        with pytest.raises(ValueError, match="비어있음"):
            aggregate_monthly(daily_df, date_col="Date", signed_col="signed", ffr_df=None)

    def test_ffr_integration_and_matching_by_month(self):
        """
        FFR 데이터 매칭 테스트 (to_period("M") 기반)

        매칭 규칙: month = 날짜.to_period("M"), join으로 금리 붙임

        Given:
            - 일별 데이터: 2023-01-15, 2023-01-31
            - FFR: {"2023-01": 0.045}
        When: aggregate_monthly(ffr_df 포함)
        Then:
            - 2023-01에 rate_pct = 4.5 붙음
            - dr_m: NaN (첫 달)
        """
        # Given (datetime으로 변환)
        daily_df = pd.DataFrame(
            {
                "Date": pd.to_datetime([date(2023, 1, 15), date(2023, 1, 31)]),
                "signed": [1.0, 2.0],
            }
        )
        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "VALUE": [0.045]})

        # When
        monthly = aggregate_monthly(
            daily_df, date_col="Date", signed_col="signed", ffr_df=ffr_df, min_months_for_analysis=1
        )

        # Then
        assert monthly.loc[0, "rate_pct"] == pytest.approx(4.5)  # 0.045 * 100
        assert pd.isna(monthly.loc[0, "dr_m"])  # 첫 달
