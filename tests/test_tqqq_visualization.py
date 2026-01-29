"""TQQQ 시뮬레이션 시각화 모듈 테스트

visualization.py의 차트 생성 함수들을 검증한다.
- 반환 타입 검증 (plotly.graph_objects.Figure)
- 필수 trace 존재 확인
- 결측치 처리 검증
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import pytest

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_DE_M,
    COL_DR_M,
    COL_E_M,
    COL_MONTH,
    COL_RATE_PCT,
    COL_SIMUL_CLOSE,
    COL_SUM_DAILY_M,
)
from qbt.tqqq.visualization import (
    create_cumulative_return_diff_chart,
    create_daily_return_diff_histogram,
    create_delta_chart,
    create_level_chart,
    create_price_comparison_chart,
)


class TestPriceComparisonChart:
    """가격 비교 차트 생성 함수 테스트"""

    def test_basic_chart_creation(self):
        """
        기본 가격 비교 차트를 생성한다.

        Given: 실제 종가와 시뮬레이션 종가를 포함한 일별 데이터
        When: create_price_comparison_chart 호출
        Then: 2개의 trace를 가진 Figure 객체 반환
        """
        # Given
        df = pd.DataFrame(
            {
                DISPLAY_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                COL_ACTUAL_CLOSE: [100.0, 102.0, 101.5],
                COL_SIMUL_CLOSE: [100.0, 101.8, 101.2],
            }
        )

        # When
        fig = create_price_comparison_chart(df)

        # Then
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 2
        # Trace 타입 검증
        assert isinstance(fig.data[0], go.Scatter)
        assert isinstance(fig.data[1], go.Scatter)
        assert fig.data[0].name == "실제 TQQQ"
        assert fig.data[1].name == "시뮬레이션 TQQQ"

    def test_chart_with_single_row(self):
        """
        단일 행 데이터로도 차트를 생성한다.

        Given: 1개의 데이터 포인트만 있는 DataFrame
        When: create_price_comparison_chart 호출
        Then: 정상적으로 Figure 객체 반환
        """
        # Given
        df = pd.DataFrame(
            {
                DISPLAY_DATE: [date(2023, 1, 1)],
                COL_ACTUAL_CLOSE: [100.0],
                COL_SIMUL_CLOSE: [100.0],
            }
        )

        # When
        fig = create_price_comparison_chart(df)

        # Then
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 2


class TestDailyReturnDiffHistogram:
    """일일수익률 차이 히스토그램 생성 함수 테스트"""

    def test_basic_histogram_creation(self):
        """
        기본 히스토그램을 생성한다.

        Given: 일일수익률 절대차이를 포함한 데이터
        When: create_daily_return_diff_histogram 호출
        Then: 2개의 trace를 가진 Figure 객체 반환 (히스토그램 + rug plot)
        """
        # Given
        df = pd.DataFrame({COL_DAILY_RETURN_ABS_DIFF: [0.1, 0.2, 0.15, 0.3, 0.25, 0.18]})

        # When
        fig = create_daily_return_diff_histogram(df)

        # Then
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 2
        # Trace 타입 검증
        assert isinstance(fig.data[0], go.Histogram)
        assert isinstance(fig.data[1], go.Scatter)
        # go.Histogram은 plotly-stubs에 _histogram.pyi 미제공 -> dict 접근 사용
        assert fig.data[0]["name"] == "일일수익률 차이"
        assert fig.data[1].name == "개별 관측값"

    def test_histogram_with_nan_values(self):
        """
        결측치가 있는 데이터에서 히스토그램을 생성한다.

        Given: NaN을 포함한 일일수익률 차이 데이터
        When: create_daily_return_diff_histogram 호출
        Then: NaN을 제외하고 차트 생성
        """
        # Given
        df = pd.DataFrame({COL_DAILY_RETURN_ABS_DIFF: [0.1, None, 0.15, 0.3, None, 0.18]})

        # When
        fig = create_daily_return_diff_histogram(df)

        # Then
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 2
        # Rug plot의 데이터 포인트 개수가 NaN을 제외한 개수와 일치
        assert isinstance(fig.data[1], go.Scatter)
        assert len(fig.data[1].x) == 4


class TestCumulativeReturnDiffChart:
    """누적배수 로그차이 차트 생성 함수 테스트"""

    def test_basic_chart_creation_signed(self):
        """
        signed 누적배수 로그차이 차트를 생성한다.

        Given: signed 누적배수 로그차이를 포함한 일별 데이터
        When: create_cumulative_return_diff_chart 호출
        Then: 1개의 trace를 가진 Figure 객체 반환
        """
        # Given
        df = pd.DataFrame(
            {
                DISPLAY_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED: [0.0, 0.05, -0.02],
            }
        )

        # When
        fig = create_cumulative_return_diff_chart(df)

        # Then
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1
        # Trace 타입 검증
        assert isinstance(fig.data[0], go.Scatter)
        assert fig.data[0].name == "누적배수 로그차이 (signed)"

    def test_chart_handles_positive_and_negative_values(self):
        """
        양수와 음수를 모두 포함한 데이터를 처리한다.

        Given: 양수와 음수가 섞인 signed 로그차이 데이터
        When: create_cumulative_return_diff_chart 호출
        Then: 정상적으로 Figure 객체 반환
        """
        # Given
        df = pd.DataFrame(
            {
                DISPLAY_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
                COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED: [0.1, -0.05, 0.08, -0.12],
            }
        )

        # When
        fig = create_cumulative_return_diff_chart(df)

        # Then
        assert isinstance(fig, go.Figure)
        # 양수/음수 값이 모두 포함되어 있는지 확인
        assert isinstance(fig.data[0], go.Scatter)
        y_values = fig.data[0].y
        assert any(y > 0 for y in y_values)
        assert any(y < 0 for y in y_values)


class TestLevelChart:
    """Level 차트 생성 함수 테스트"""

    @pytest.fixture
    def sample_monthly_df(self):
        """월별 데이터 샘플 픽스처"""
        return pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=15, freq="M"),
                COL_RATE_PCT: [4.5, 4.6, 4.7, 4.8, 5.0, 5.2, 5.1, 5.0, 4.9, 4.7, 4.5, 4.3, 4.2, 4.1, 4.0],
                COL_E_M: [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.32, 0.28, 0.25, 0.2, 0.15, 0.1, 0.05, 0.0, -0.05],
                COL_DE_M: [
                    0.0,
                    0.05,
                    0.05,
                    0.05,
                    0.05,
                    0.05,
                    -0.03,
                    -0.04,
                    -0.03,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                ],
                COL_SUM_DAILY_M: [
                    0.0,
                    0.05,
                    0.05,
                    0.05,
                    0.05,
                    0.05,
                    -0.03,
                    -0.04,
                    -0.03,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                ],
            }
        )

    def test_basic_chart_creation(self, sample_monthly_df):
        """
        기본 Level 차트를 생성한다.

        Given: 월별 데이터 (rate_pct, e_m 컬럼 포함)
        When: create_level_chart 호출
        Then: Figure 객체 반환, 서브플롯 2개 (산점도 + 시계열), trace 4개 이상
        """
        # Given
        df = sample_monthly_df

        # When
        fig = create_level_chart(df, y_col=COL_E_M, y_label="월말 누적 signed (%)")

        # Then
        assert isinstance(fig, go.Figure)
        # 산점도 trace + 추세선 + 시계열 2개 = 최소 4개
        assert len(fig.data) >= 4

    def test_y_col_parameter_variations(self, sample_monthly_df):
        """
        y_col 파라미터 변경에 따라 차트가 생성된다.

        Given: 월별 데이터
        When: y_col을 e_m, de_m, sum_daily_m으로 각각 호출
        Then: 모두 정상적으로 Figure 객체 반환
        """
        # Given
        df = sample_monthly_df

        # When & Then: e_m
        fig_em = create_level_chart(df, y_col=COL_E_M, y_label="월말 누적 signed (%)")
        assert isinstance(fig_em, go.Figure)

        # When & Then: de_m
        fig_dem = create_level_chart(df, y_col=COL_DE_M, y_label="월간 변화 (%)")
        assert isinstance(fig_dem, go.Figure)

        # When & Then: sum_daily_m
        fig_sum = create_level_chart(df, y_col=COL_SUM_DAILY_M, y_label="일일 증분 월합 (%)")
        assert isinstance(fig_sum, go.Figure)

    def test_handles_missing_values(self):
        """
        결측치를 자동으로 제거하고 차트를 생성한다.

        Given: NaN을 포함한 월별 데이터
        When: create_level_chart 호출
        Then: NaN을 제외하고 정상적으로 차트 생성
        """
        # Given
        df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=5, freq="M"),
                COL_RATE_PCT: [4.5, None, 4.7, 4.8, 5.0],
                COL_E_M: [0.1, 0.15, None, 0.25, 0.3],
            }
        )

        # When
        fig = create_level_chart(df, y_col=COL_E_M, y_label="월말 누적 signed (%)")

        # Then
        assert isinstance(fig, go.Figure)
        # NaN이 제거되어 유효한 데이터만 차트에 포함됨
        assert len(fig.data) > 0


class TestDeltaChart:
    """Delta 차트 생성 함수 테스트"""

    @pytest.fixture
    def sample_monthly_df(self):
        """월별 데이터 샘플 픽스처 (Rolling 상관 계산 가능한 15개월)"""
        return pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=15, freq="M"),
                COL_RATE_PCT: [4.5, 4.6, 4.7, 4.8, 5.0, 5.2, 5.1, 5.0, 4.9, 4.7, 4.5, 4.3, 4.2, 4.1, 4.0],
                COL_DE_M: [
                    0.0,
                    0.05,
                    0.05,
                    0.05,
                    0.05,
                    0.05,
                    -0.03,
                    -0.04,
                    -0.03,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                ],
                COL_SUM_DAILY_M: [
                    0.0,
                    0.05,
                    0.05,
                    0.05,
                    0.05,
                    0.05,
                    -0.03,
                    -0.04,
                    -0.03,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                    -0.05,
                ],
                COL_DR_M: [0.0, 0.1, 0.1, 0.1, 0.2, 0.2, -0.1, -0.1, -0.1, -0.2, -0.2, -0.2, -0.1, -0.1, -0.1],
            }
        )

    def test_basic_chart_creation(self, sample_monthly_df):
        """
        기본 Delta 차트를 생성한다.

        Given: 월별 데이터 (de_m, dr_m 컬럼 포함, 15개월)
        When: create_delta_chart 호출 (lag=0)
        Then: Figure 객체 및 유효 데이터 DataFrame 반환
        """
        # Given
        df = sample_monthly_df

        # When
        fig, valid_df = create_delta_chart(df, y_col=COL_DE_M, y_label="월간 변화 (%)", lag=0)

        # Then
        assert isinstance(fig, go.Figure)
        assert isinstance(valid_df, pd.DataFrame)
        assert len(valid_df) > 0

    def test_lag_parameter_variations(self, sample_monthly_df):
        """
        lag 파라미터 변경에 따라 차트가 생성된다.

        Given: 월별 데이터
        When: lag를 0, 1, 2로 각각 호출
        Then: 모두 정상적으로 Figure 및 DataFrame 반환
        """
        # Given
        df = sample_monthly_df

        # When & Then: lag=0
        fig0, valid_df0 = create_delta_chart(df, y_col=COL_DE_M, y_label="월간 변화 (%)", lag=0)
        assert isinstance(fig0, go.Figure)
        assert len(valid_df0) == 15  # shift(0)이므로 결측치 없음

        # When & Then: lag=1
        fig1, valid_df1 = create_delta_chart(df, y_col=COL_DE_M, y_label="월간 변화 (%)", lag=1)
        assert isinstance(fig1, go.Figure)
        assert len(valid_df1) == 14  # shift(1)으로 첫 행 NaN 제거

        # When & Then: lag=2
        fig2, valid_df2 = create_delta_chart(df, y_col=COL_DE_M, y_label="월간 변화 (%)", lag=2)
        assert isinstance(fig2, go.Figure)
        assert len(valid_df2) == 13  # shift(2)로 첫 2행 NaN 제거

    def test_rolling_correlation_with_sufficient_data(self, sample_monthly_df):
        """
        12개월 이상 데이터로 Rolling 상관을 계산한다.

        Given: 15개월 월별 데이터
        When: create_delta_chart 호출
        Then: Rolling 상관 trace가 포함됨 (서브플롯 2에 trace 추가)
        """
        # Given
        df = sample_monthly_df

        # When
        fig, _ = create_delta_chart(df, y_col=COL_DE_M, y_label="월간 변화 (%)", lag=0)

        # Then
        # 산점도 + 추세선 + Rolling 상관 = 3개 이상
        assert len(fig.data) >= 3
        # Rolling 상관 trace 확인 (모든 trace가 Scatter)
        rolling_corr_trace = []
        for trace in fig.data:
            assert isinstance(trace, go.Scatter)
            if isinstance(trace.name, str) and "Rolling 12M" in trace.name:
                rolling_corr_trace.append(trace)
        assert len(rolling_corr_trace) > 0

    def test_rolling_correlation_with_insufficient_data(self):
        """
        12개월 미만 데이터로는 Rolling 상관 계산 안내 메시지를 표시한다.

        Given: 10개월 월별 데이터 (12개월 미만)
        When: create_delta_chart 호출
        Then: 안내 메시지 annotation 포함
        """
        # Given
        df = pd.DataFrame(
            {
                COL_MONTH: pd.period_range("2023-01", periods=10, freq="M"),
                COL_DE_M: [0.05, 0.06, 0.04, 0.07, 0.05, 0.03, 0.06, 0.04, 0.05, 0.07],
                COL_DR_M: [0.1, 0.12, 0.09, 0.13, 0.11, 0.08, 0.12, 0.10, 0.11, 0.13],
            }
        )

        # When
        fig, _ = create_delta_chart(df, y_col=COL_DE_M, y_label="월간 변화 (%)", lag=0)

        # Then
        assert isinstance(fig, go.Figure)
        # annotation이 추가되었는지 확인
        assert len(fig.layout.annotations) > 0
