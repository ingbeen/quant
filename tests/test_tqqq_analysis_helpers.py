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
    add_rate_change_lags,
    add_rolling_features,
    aggregate_monthly,
    build_model_dataset,
    calculate_daily_signed_log_diff,
    calculate_signed_log_diff_from_cumulative_returns,
    save_model_csv,
    save_monthly_features,
    save_summary_statistics,
    validate_integrity,
)
from qbt.tqqq.constants import (
    COL_DE_M,
    COL_DR_LAG1,
    COL_DR_LAG2,
    COL_DR_M,
    COL_E_M,
    # 모델용 CSV 컬럼
    COL_MODEL_CV_DIFF_PCT,
    COL_MODEL_ERROR_CHANGE_PCT,
    COL_MODEL_ERROR_DAILY_SUM_PCT,
    COL_MODEL_ERROR_EOM_PCT,
    COL_MODEL_MONTH,
    COL_MODEL_RATE_CHANGE_LAG1_PCT,
    COL_MODEL_RATE_CHANGE_LAG2_PCT,
    COL_MODEL_RATE_CHANGE_PCT,
    COL_MODEL_RATE_LEVEL_PCT,
    COL_MODEL_ROLLING_CORR_DELTA,
    COL_MODEL_ROLLING_CORR_LAG1,
    COL_MODEL_ROLLING_CORR_LAG2,
    COL_MODEL_ROLLING_CORR_LEVEL,
    COL_MODEL_SCHEMA_VERSION,
    COL_MONTH,
    COL_RATE_PCT,
    COL_SUM_DAILY_M,
    DEFAULT_ROLLING_WINDOW,
    # 출력용 한글 헤더 (CSV 저장 검증용)
    DISPLAY_CATEGORY,
    DISPLAY_CORR,
    DISPLAY_DE_M,
    DISPLAY_DR_LAG1,
    DISPLAY_DR_LAG2,
    DISPLAY_DR_M,
    DISPLAY_E_M,
    DISPLAY_INTERCEPT,
    DISPLAY_LAG,
    DISPLAY_MAX_ABS_DIFF,
    DISPLAY_MEAN_ABS_DIFF,
    DISPLAY_MONTH,
    DISPLAY_N,
    DISPLAY_RATE_PCT,
    DISPLAY_SLOPE,
    DISPLAY_STD_DIFF,
    DISPLAY_SUM_DAILY_M,
    DISPLAY_X_VAR,
    DISPLAY_Y_VAR,
    MODEL_SCHEMA_VERSION,
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
        assert monthly.loc[0, COL_E_M] == 2.0  # 2023-01 월말
        assert monthly.loc[1, COL_E_M] == 3.0  # 2023-02 월말

        # 첫 달은 NaN, 두 번째 달은 차이값 확인
        de_m_values = monthly[COL_DE_M].tolist()
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
        assert monthly.loc[0, COL_E_M] == 2.0  # 정렬 후 월말이므로 2.0

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
        assert monthly.loc[0, COL_RATE_PCT] == pytest.approx(4.5)  # 0.045 * 100
        assert pd.isna(monthly.loc[0, COL_DR_M])  # 첫 달


class TestSaveMonthlyFeatures:
    """save_monthly_features() 함수 테스트"""

    def test_csv_saving_with_korean_columns_and_rounding(self, tmp_path):
        """
        CSV 저장 시 한글 컬럼명 변경 및 소수점 라운딩 테스트

        Given:
            - 내부 컬럼명(상수 기준)의 월별 DataFrame (부동소수점 오차 포함)
        When: save_monthly_features() 호출
        Then:
            - 한글 컬럼명으로 변경
            - 소수점 4자리로 라운딩
            - CSV 파일 생성
        """
        # Given (상수 기준 컬럼명 사용)
        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.Period("2023-01"),
                COL_RATE_PCT: [4.123456789],
                COL_DR_M: [0.051234567],
                COL_E_M: [-0.03999999999998],
                COL_DE_M: [-0.001999999999],
                COL_SUM_DAILY_M: [-0.03888888888],
                COL_DR_LAG1: [0.045],
                COL_DR_LAG2: [0.038],
            }
        )
        output_path = tmp_path / "test_monthly.csv"

        # When
        save_monthly_features(monthly_df, output_path)

        # Then
        assert output_path.exists()
        saved_df = pd.read_csv(output_path)

        # 1. 컬럼명 검증 (한글 DISPLAY_* 상수)
        assert DISPLAY_MONTH in saved_df.columns
        assert DISPLAY_RATE_PCT in saved_df.columns
        assert DISPLAY_DR_M in saved_df.columns
        assert DISPLAY_E_M in saved_df.columns
        assert DISPLAY_DE_M in saved_df.columns
        assert DISPLAY_SUM_DAILY_M in saved_df.columns
        assert DISPLAY_DR_LAG1 in saved_df.columns
        assert DISPLAY_DR_LAG2 in saved_df.columns

        # 2. 라운딩 검증 (4자리)
        assert saved_df[DISPLAY_RATE_PCT].iloc[0] == pytest.approx(4.1235, abs=0.00001)
        assert saved_df[DISPLAY_DR_M].iloc[0] == pytest.approx(0.0512, abs=0.00001)
        assert saved_df[DISPLAY_E_M].iloc[0] == pytest.approx(-0.0400, abs=0.00001)
        assert saved_df[DISPLAY_DE_M].iloc[0] == pytest.approx(-0.0020, abs=0.00001)
        assert saved_df[DISPLAY_SUM_DAILY_M].iloc[0] == pytest.approx(-0.0389, abs=0.00001)

    def test_missing_required_columns_raises(self, tmp_path):
        """
        필수 컬럼 누락 시 ValueError 발생 테스트

        Given: 필수 컬럼이 없는 DataFrame
        When: save_monthly_features() 호출
        Then: ValueError 발생
        """
        # Given
        monthly_df = pd.DataFrame({"month": pd.Period("2023-01"), "rate_pct": [4.0]})
        output_path = tmp_path / "test_monthly.csv"

        # When & Then
        with pytest.raises(ValueError, match="필수 컬럼 누락"):
            save_monthly_features(monthly_df, output_path)


class TestSaveSummaryStatistics:
    """save_summary_statistics() 함수 테스트"""

    def test_csv_saving_with_korean_columns_and_rounding(self, tmp_path):
        """
        요약 통계 CSV 저장 시 한글 컬럼명 및 라운딩 테스트

        Given:
            - 내부 컬럼명(상수 기준)의 월별 DataFrame (충분한 데이터)
        When: save_summary_statistics() 호출
        Then:
            - 한글 컬럼명으로 변경
            - 소수점 4자리로 라운딩
            - Level, Delta, CrossValidation 요약 포함
        """
        # Given (최소 13개월 데이터, 상수 기준 컬럼명 사용)
        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=13, freq="M"),
                COL_RATE_PCT: [4.0 + i * 0.1 for i in range(13)],
                COL_DR_M: [0.0] + [0.05 + i * 0.01 for i in range(12)],
                COL_E_M: [-0.04 + i * 0.002 for i in range(13)],
                COL_DE_M: [0.0] + [-0.001 + i * 0.0001 for i in range(12)],
                COL_SUM_DAILY_M: [-0.038 + i * 0.002 for i in range(13)],
            }
        )
        output_path = tmp_path / "test_summary.csv"

        # When
        save_summary_statistics(monthly_df, output_path)

        # Then
        assert output_path.exists()
        saved_df = pd.read_csv(output_path)

        # 1. 컬럼명 검증 (한글 DISPLAY_* 상수)
        assert DISPLAY_CATEGORY in saved_df.columns
        assert DISPLAY_X_VAR in saved_df.columns
        assert DISPLAY_Y_VAR in saved_df.columns
        assert DISPLAY_LAG in saved_df.columns
        assert DISPLAY_N in saved_df.columns
        assert DISPLAY_CORR in saved_df.columns
        assert DISPLAY_SLOPE in saved_df.columns
        assert DISPLAY_INTERCEPT in saved_df.columns

        # 2. Level 요약 존재 확인
        level_rows = saved_df[saved_df[DISPLAY_CATEGORY] == "Level"]
        assert len(level_rows) > 0

        # 3. 라운딩 검증 (4자리)
        numeric_cols = [DISPLAY_CORR, DISPLAY_SLOPE, DISPLAY_INTERCEPT]
        for col in numeric_cols:
            if col in level_rows.columns:
                value = level_rows[col].iloc[0]
                if pd.notna(value):
                    # 소수점 자릿수 확인
                    str_value = str(value)
                    if "." in str_value:
                        decimal_places = len(str_value.split(".")[-1])
                        assert decimal_places <= 4, f"{col} 컬럼의 소수점 자릿수가 4자리를 초과: {decimal_places}"

    def test_cross_validation_with_korean_columns(self, tmp_path):
        """
        교차검증 요약에 한글 컬럼명 적용 테스트

        Given: 내부 컬럼명(상수 기준)의 월별 데이터
        When: save_summary_statistics() 호출
        Then: CrossValidation 요약에 한글 컬럼명 포함
        """
        # Given (상수 기준 컬럼명 사용)
        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=5, freq="M"),
                COL_RATE_PCT: [4.0, 4.1, 4.2, 4.3, 4.4],
                COL_DR_M: [0.0, 0.05, 0.06, 0.07, 0.08],
                COL_E_M: [-0.04, -0.038, -0.036, -0.034, -0.032],
                COL_DE_M: [0.0, 0.002, 0.002, 0.002, 0.002],
                COL_SUM_DAILY_M: [-0.038, -0.036, -0.034, -0.032, -0.030],
            }
        )
        output_path = tmp_path / "test_summary_cross.csv"

        # When
        save_summary_statistics(monthly_df, output_path)

        # Then
        assert output_path.exists()
        saved_df = pd.read_csv(output_path)

        # CrossValidation 요약 존재 확인
        cross_rows = saved_df[saved_df[DISPLAY_CATEGORY] == "CrossValidation"]
        assert len(cross_rows) > 0

        # 한글 컬럼명 확인
        assert DISPLAY_MAX_ABS_DIFF in cross_rows.columns
        assert DISPLAY_MEAN_ABS_DIFF in cross_rows.columns
        assert DISPLAY_STD_DIFF in cross_rows.columns

        # 라운딩 확인 (4자리)
        for col in [DISPLAY_MAX_ABS_DIFF, DISPLAY_MEAN_ABS_DIFF, DISPLAY_STD_DIFF]:
            value = cross_rows[col].iloc[0]
            if pd.notna(value):
                str_value = str(value)
                if "." in str_value:
                    decimal_places = len(str_value.split(".")[-1])
                    assert decimal_places <= 4


class TestAddRateChangeLags:
    """add_rate_change_lags() 함수 테스트"""

    def test_lag_columns_created_correctly(self):
        """
        lag 컬럼이 정확히 생성되는지 테스트

        Given:
            - dr_m 컬럼이 있는 월별 DataFrame
            - lag_list = [1, 2]
        When: add_rate_change_lags() 호출
        Then:
            - dr_lag1, dr_lag2 컬럼이 생성됨
            - 값이 shift와 동일
        """
        # Given
        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=5, freq="M"),
                COL_DR_M: [0.1, 0.2, 0.3, 0.4, 0.5],
            }
        )

        # When
        result = add_rate_change_lags(monthly_df, lag_list=[1, 2])

        # Then
        assert COL_DR_LAG1 in result.columns
        assert COL_DR_LAG2 in result.columns

        # lag1 = shift(1)
        assert pd.isna(result[COL_DR_LAG1].iloc[0])
        assert result[COL_DR_LAG1].iloc[1] == pytest.approx(0.1)
        assert result[COL_DR_LAG1].iloc[2] == pytest.approx(0.2)

        # lag2 = shift(2)
        assert pd.isna(result[COL_DR_LAG2].iloc[0])
        assert pd.isna(result[COL_DR_LAG2].iloc[1])
        assert result[COL_DR_LAG2].iloc[2] == pytest.approx(0.1)

    def test_original_dataframe_not_modified(self):
        """
        원본 DataFrame이 변경되지 않는지 테스트 (불변성)

        Given: 원본 DataFrame
        When: add_rate_change_lags() 호출
        Then: 원본에 lag 컬럼이 추가되지 않음
        """
        # Given
        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=3, freq="M"),
                COL_DR_M: [0.1, 0.2, 0.3],
            }
        )
        original_columns = set(monthly_df.columns)

        # When
        add_rate_change_lags(monthly_df, lag_list=[1, 2])

        # Then: 원본 변경 없음
        assert set(monthly_df.columns) == original_columns


class TestAddRollingFeatures:
    """add_rolling_features() 함수 테스트"""

    def test_rolling_correlation_columns_created(self):
        """
        rolling correlation 컬럼이 정확히 생성되는지 테스트

        Given:
            - 13개월 이상의 월별 데이터 (rolling 12M 가능)
            - 필수 컬럼: rate_pct, dr_m, e_m, de_m, dr_lag1, dr_lag2
        When: add_rolling_features() 호출
        Then:
            - rolling correlation 컬럼들이 생성됨
        """
        # Given: 15개월 데이터 (rolling 12 가능)
        n = 15
        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=n, freq="M"),
                COL_RATE_PCT: [4.0 + i * 0.1 for i in range(n)],
                COL_DR_M: [0.1] * n,
                COL_E_M: [-0.04 + i * 0.002 for i in range(n)],
                COL_DE_M: [0.002] * n,
                COL_DR_LAG1: [None] + [0.1] * (n - 1),
                COL_DR_LAG2: [None, None] + [0.1] * (n - 2),
            }
        )

        # When
        result = add_rolling_features(monthly_df, window=DEFAULT_ROLLING_WINDOW)

        # Then: rolling correlation 컬럼 존재
        assert COL_MODEL_ROLLING_CORR_LEVEL in result.columns
        assert COL_MODEL_ROLLING_CORR_DELTA in result.columns
        assert COL_MODEL_ROLLING_CORR_LAG1 in result.columns
        assert COL_MODEL_ROLLING_CORR_LAG2 in result.columns

    def test_fail_fast_when_data_length_less_than_window(self):
        """
        데이터 길이가 window 미만일 때 fail-fast (ValueError)

        Fail-fast 정책: rolling 데이터 부족 시 예외 raise

        Given:
            - 10개월 데이터 (rolling 12M 불가)
        When: add_rolling_features(window=12) 호출
        Then: ValueError raise
        """
        # Given: 10개월 (window=12 미만)
        n = 10
        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=n, freq="M"),
                COL_RATE_PCT: [4.0 + i * 0.1 for i in range(n)],
                COL_DR_M: [0.1] * n,
                COL_E_M: [-0.04 + i * 0.002 for i in range(n)],
                COL_DE_M: [0.002] * n,
                COL_DR_LAG1: [None] + [0.1] * (n - 1),
                COL_DR_LAG2: [None, None] + [0.1] * (n - 2),
            }
        )

        # When & Then
        with pytest.raises(ValueError, match="데이터 부족|window"):
            add_rolling_features(monthly_df, window=12)

    def test_min_periods_equals_window(self):
        """
        min_periods = window 설정 확인 (불완전 window 허용 금지)

        Given: 정확히 window 크기의 데이터
        When: add_rolling_features() 호출
        Then:
            - 첫 번째 유효한 rolling 값은 window번째 행에서 시작
            - 이전 행들은 NaN
        """
        # Given: 정확히 12개월 (경계 케이스)
        n = 12
        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=n, freq="M"),
                COL_RATE_PCT: [4.0 + i * 0.1 for i in range(n)],
                COL_DR_M: [0.1] * n,
                COL_E_M: [-0.04 + i * 0.002 for i in range(n)],
                COL_DE_M: [0.002] * n,
                COL_DR_LAG1: [None] + [0.1] * (n - 1),
                COL_DR_LAG2: [None, None] + [0.1] * (n - 2),
            }
        )

        # When
        result = add_rolling_features(monthly_df, window=12)

        # Then: 첫 11개 행은 NaN (min_periods=12)
        corr_col = COL_MODEL_ROLLING_CORR_LEVEL
        for i in range(11):
            assert pd.isna(result[corr_col].iloc[i]), f"행 {i}는 NaN이어야 함"

        # 12번째 행(인덱스 11)부터 값 존재
        assert pd.notna(result[corr_col].iloc[11])


class TestBuildModelDataset:
    """build_model_dataset() 함수 테스트"""

    def test_model_dataset_has_english_columns(self):
        """
        모델용 DF가 영문 컬럼을 가지는지 테스트

        Given: 충분한 월별 데이터 (15개월)
        When: build_model_dataset() 호출
        Then:
            - 모든 컬럼이 영문
            - schema_version 컬럼 포함
        """
        # Given: 15개월 데이터
        n = 15
        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=n, freq="M"),
                COL_RATE_PCT: [4.0 + i * 0.1 for i in range(n)],
                COL_DR_M: [0.1] * n,
                COL_E_M: [-0.04 + i * 0.002 for i in range(n)],
                COL_DE_M: [0.002] * n,
                COL_SUM_DAILY_M: [0.001] * n,
            }
        )

        # When
        result = build_model_dataset(monthly_df, window=DEFAULT_ROLLING_WINDOW)

        # Then: 영문 컬럼 확인
        assert COL_MODEL_MONTH in result.columns
        assert COL_MODEL_SCHEMA_VERSION in result.columns
        assert COL_MODEL_RATE_LEVEL_PCT in result.columns
        assert COL_MODEL_RATE_CHANGE_PCT in result.columns
        assert COL_MODEL_ERROR_EOM_PCT in result.columns
        assert COL_MODEL_ERROR_CHANGE_PCT in result.columns
        assert COL_MODEL_CV_DIFF_PCT in result.columns

        # schema_version 값 확인
        assert (result[COL_MODEL_SCHEMA_VERSION] == MODEL_SCHEMA_VERSION).all()

    def test_cv_diff_calculated_correctly(self):
        """
        cv_diff_pct가 정확히 계산되는지 테스트

        계산: cv_diff_pct = error_change_pct - error_daily_sum_pct

        Given: de_m, sum_daily_m 값이 있는 데이터
        When: build_model_dataset() 호출
        Then: cv_diff_pct = de_m - sum_daily_m
        """
        # Given
        n = 15
        de_m_vals = [0.002] * n
        sum_daily_m_vals = [0.001] * n
        expected_cv_diff = [0.001] * n  # de_m - sum_daily_m

        monthly_df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=n, freq="M"),
                COL_RATE_PCT: [4.0 + i * 0.1 for i in range(n)],
                COL_DR_M: [0.1] * n,
                COL_E_M: [-0.04 + i * 0.002 for i in range(n)],
                COL_DE_M: de_m_vals,
                COL_SUM_DAILY_M: sum_daily_m_vals,
            }
        )

        # When
        result = build_model_dataset(monthly_df, window=DEFAULT_ROLLING_WINDOW)

        # Then: cv_diff 검증
        for i in range(n):
            if pd.notna(result[COL_MODEL_CV_DIFF_PCT].iloc[i]):
                assert result[COL_MODEL_CV_DIFF_PCT].iloc[i] == pytest.approx(expected_cv_diff[i], abs=1e-6)


class TestSaveModelCsv:
    """save_model_csv() 함수 테스트"""

    def test_csv_saved_with_english_columns(self, tmp_path):
        """
        CSV가 영문 컬럼으로 저장되는지 테스트

        Given: 모델용 DataFrame (영문 컬럼)
        When: save_model_csv() 호출
        Then:
            - CSV 파일 생성
            - 영문 컬럼명 유지
        """
        # Given
        model_df = pd.DataFrame(
            {
                COL_MODEL_MONTH: ["2023-01", "2023-02"],
                COL_MODEL_SCHEMA_VERSION: [MODEL_SCHEMA_VERSION, MODEL_SCHEMA_VERSION],
                COL_MODEL_RATE_LEVEL_PCT: [4.5, 4.6],
                COL_MODEL_RATE_CHANGE_PCT: [0.1, 0.1],
                COL_MODEL_RATE_CHANGE_LAG1_PCT: [None, 0.1],
                COL_MODEL_RATE_CHANGE_LAG2_PCT: [None, None],
                COL_MODEL_ERROR_EOM_PCT: [-0.04, -0.038],
                COL_MODEL_ERROR_CHANGE_PCT: [0.002, 0.002],
                COL_MODEL_ERROR_DAILY_SUM_PCT: [0.001, 0.001],
                COL_MODEL_CV_DIFF_PCT: [0.001, 0.001],
                COL_MODEL_ROLLING_CORR_LEVEL: [None, None],
                COL_MODEL_ROLLING_CORR_DELTA: [None, None],
                COL_MODEL_ROLLING_CORR_LAG1: [None, None],
                COL_MODEL_ROLLING_CORR_LAG2: [None, None],
            }
        )
        output_path = tmp_path / "test_model.csv"

        # When
        save_model_csv(model_df, output_path)

        # Then
        assert output_path.exists()
        saved_df = pd.read_csv(output_path)

        # 영문 컬럼명 확인
        assert COL_MODEL_MONTH in saved_df.columns
        assert COL_MODEL_SCHEMA_VERSION in saved_df.columns
        assert COL_MODEL_RATE_LEVEL_PCT in saved_df.columns

    def test_numeric_values_rounded_to_4_decimals(self, tmp_path):
        """
        수치 컬럼이 4자리로 라운딩되는지 테스트

        Given: 부동소수점 오차가 있는 값
        When: save_model_csv() 호출
        Then: 4자리로 라운딩됨
        """
        # Given
        model_df = pd.DataFrame(
            {
                COL_MODEL_MONTH: ["2023-01"],
                COL_MODEL_SCHEMA_VERSION: [MODEL_SCHEMA_VERSION],
                COL_MODEL_RATE_LEVEL_PCT: [4.123456789],
                COL_MODEL_RATE_CHANGE_PCT: [0.099999999],
                COL_MODEL_RATE_CHANGE_LAG1_PCT: [0.088888888],
                COL_MODEL_RATE_CHANGE_LAG2_PCT: [0.077777777],
                COL_MODEL_ERROR_EOM_PCT: [-0.03999999999],
                COL_MODEL_ERROR_CHANGE_PCT: [0.00199999999],
                COL_MODEL_ERROR_DAILY_SUM_PCT: [0.00099999999],
                COL_MODEL_CV_DIFF_PCT: [0.00099999999],
                COL_MODEL_ROLLING_CORR_LEVEL: [0.123456789],
                COL_MODEL_ROLLING_CORR_DELTA: [0.234567890],
                COL_MODEL_ROLLING_CORR_LAG1: [0.345678901],
                COL_MODEL_ROLLING_CORR_LAG2: [0.456789012],
            }
        )
        output_path = tmp_path / "test_model_round.csv"

        # When
        save_model_csv(model_df, output_path)

        # Then
        saved_df = pd.read_csv(output_path)
        assert saved_df[COL_MODEL_RATE_LEVEL_PCT].iloc[0] == pytest.approx(4.1235, abs=0.00001)
