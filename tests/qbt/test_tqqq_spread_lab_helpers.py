"""
spread_lab_helpers 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 일별 데이터를 월별로 정확히 집계하는가? (prepare_monthly_data)
2. sum_daily_m이 일일 증분 signed 로그오차의 월별 합과 일치하는가?
3. 필수 컬럼 누락 시 ValueError가 발생하는가?
4. 금리 변화 lag 컬럼이 정확히 생성되는가? (add_rate_change_lags)
5. lag 추가 시 원본 DataFrame의 불변성이 보장되는가?

왜 중요한가요?
금리-오차 분석의 월별 데이터 준비와 lag 피처 생성이 이 함수들에 의존합니다.
잘못된 집계나 lag 계산은 분석 결과를 오도할 수 있습니다.

Note:
    모든 테스트는 synthetic(고정) 데이터를 사용하여 결정적(deterministic)으로 작성됩니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_ACTUAL_DAILY_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DE_M,
    COL_DR_LAG1,
    COL_DR_LAG2,
    COL_DR_M,
    COL_E_M,
    COL_MONTH,
    COL_RATE_PCT,
    COL_SIMUL_DAILY_RETURN,
    COL_SUM_DAILY_M,
)
from qbt.tqqq.spread_lab_helpers import add_rate_change_lags, prepare_monthly_data


def _build_daily_df(n_months: int = 14) -> pd.DataFrame:
    """
    prepare_monthly_data 테스트용 일별 비교 데이터를 생성한다.

    각 월마다 2일치 데이터를 생성하여 최소 데이터로 충분한 월 수를 확보한다.

    Args:
        n_months: 생성할 월 수 (기본 14, aggregate_monthly의 min_months=13 충족)

    Returns:
        일별 비교 DataFrame (날짜, 일일수익률_실제, 일일수익률_시뮬, 누적배수_로그차이_signed(%))
    """
    dates: list[date] = []
    actual_returns: list[float] = []
    sim_returns: list[float] = []
    cumul_signed: list[float] = []

    cumul = 0.0
    for i in range(n_months):
        year = 2022 + (i // 12)
        month = (i % 12) + 1

        # 각 월 2일치 데이터
        for day_offset in range(2):
            dates.append(date(year, month, 15 + day_offset))
            r_real = 1.0 + day_offset * 0.5  # 1.0%, 1.5%
            r_sim = 1.1 + day_offset * 0.5  # 1.1%, 1.5%
            actual_returns.append(r_real)
            sim_returns.append(r_sim)
            # 누적 signed: 단순 누적 (aggregate_monthly가 월말 last를 사용)
            cumul += 0.1
            cumul_signed.append(cumul)

    return pd.DataFrame(
        {
            DISPLAY_DATE: dates,
            COL_ACTUAL_DAILY_RETURN: actual_returns,
            COL_SIMUL_DAILY_RETURN: sim_returns,
            COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED: cumul_signed,
        }
    )


def _build_ffr_df(n_months: int = 14) -> pd.DataFrame:
    """
    prepare_monthly_data 테스트용 FFR 데이터를 생성한다.

    Args:
        n_months: 생성할 월 수

    Returns:
        FFR DataFrame (DATE: yyyy-mm 문자열, VALUE: 0~1 비율)
    """
    ffr_dates: list[str] = []
    ffr_values: list[float] = []

    for i in range(n_months):
        year = 2022 + (i // 12)
        month = (i % 12) + 1
        ffr_dates.append(f"{year}-{month:02d}")
        # 금리: 0.01에서 시작하여 점진적 상승
        ffr_values.append(0.01 + i * 0.002)

    return pd.DataFrame({"DATE": ffr_dates, "VALUE": ffr_values})


class TestPrepareMonthlyData:
    """prepare_monthly_data() 함수 테스트

    목적: 일별 데이터를 월별로 정확히 집계하고 금리 매칭이 올바른지 검증
    배경: Spread Lab의 모든 분석은 이 함수가 반환하는 월별 데이터에 의존
    """

    def test_normal_flow_returns_expected_columns(self):
        """
        정상 흐름: 월별 DataFrame이 필수 컬럼을 포함하여 반환되는지 검증

        Given: 14개월 일별 데이터 + FFR 데이터
        When: prepare_monthly_data() 호출
        Then:
            - month, e_m, de_m, sum_daily_m, rate_pct, dr_m 컬럼 존재
            - 반환 행 수가 입력 월 수와 일치
            - sum_daily_m에 NaN이 아닌 실제 값 존재
        """
        # Given
        daily_df = _build_daily_df(n_months=14)
        ffr_df = _build_ffr_df(n_months=14)

        # When
        result = prepare_monthly_data(daily_df, ffr_df)

        # Then: 필수 컬럼 존재
        expected_cols = {COL_MONTH, COL_E_M, COL_DE_M, COL_SUM_DAILY_M, COL_RATE_PCT, COL_DR_M}
        assert expected_cols.issubset(set(result.columns)), f"누락된 컬럼: {expected_cols - set(result.columns)}"

        # 반환 행 수 = 14개월
        assert len(result) == 14

        # sum_daily_m이 실제 값으로 채워져 있는지 확인 (pd.NA가 아님)
        assert result[COL_SUM_DAILY_M].notna().all(), "sum_daily_m에 NaN이 존재"

    def test_sum_daily_m_accuracy(self):
        """
        sum_daily_m이 일일 증분 signed 로그오차의 월별 합계와 정확히 일치하는지 검증

        Given: 14개월 일별 데이터 + FFR 데이터
        When: prepare_monthly_data() 호출
        Then: 각 월의 sum_daily_m = 해당 월 일일 signed 로그오차 합계

        검증 방식:
            독립적으로 calculate_daily_signed_log_diff를 호출하여
            월별 합산 결과와 비교
        """
        from qbt.tqqq.analysis_helpers import calculate_daily_signed_log_diff

        # Given
        daily_df = _build_daily_df(n_months=14)
        ffr_df = _build_ffr_df(n_months=14)

        # 독립적으로 expected sum_daily_m 계산
        daily_signed = calculate_daily_signed_log_diff(
            daily_return_real_pct=daily_df[COL_ACTUAL_DAILY_RETURN],
            daily_return_sim_pct=daily_df[COL_SIMUL_DAILY_RETURN],
        )
        daily_df_copy = daily_df.copy()
        daily_df_copy["_daily_signed"] = daily_signed
        daily_df_copy["_month"] = pd.to_datetime(daily_df_copy[DISPLAY_DATE]).dt.to_period("M")
        expected_sums = daily_df_copy.groupby("_month")["_daily_signed"].sum()

        # When
        result = prepare_monthly_data(daily_df, ffr_df)

        # Then: 각 월의 sum_daily_m이 독립 계산 결과와 일치
        for _, row in result.iterrows():
            month = row[COL_MONTH]
            actual_sum = float(row[COL_SUM_DAILY_M])
            expected_sum = float(expected_sums[month])
            assert actual_sum == pytest.approx(
                expected_sum, abs=1e-12
            ), f"{month}: sum_daily_m={actual_sum}, expected={expected_sum}"

    def test_missing_required_column_raises_value_error(self):
        """
        필수 컬럼이 누락되면 ValueError가 발생하는지 검증

        Given: COL_ACTUAL_DAILY_RETURN 컬럼이 없는 DataFrame
        When: prepare_monthly_data() 호출
        Then: ValueError 또는 KeyError 발생
        """
        # Given: 필수 컬럼(일일수익률_실제) 누락
        daily_df = pd.DataFrame(
            {
                DISPLAY_DATE: [date(2022, 1, 15), date(2022, 1, 16)],
                COL_SIMUL_DAILY_RETURN: [1.0, 1.5],
                COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED: [0.1, 0.2],
            }
        )
        ffr_df = _build_ffr_df(n_months=14)

        # When & Then: 컬럼 누락으로 예외 발생
        with pytest.raises((ValueError, KeyError)):
            prepare_monthly_data(daily_df, ffr_df)


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
