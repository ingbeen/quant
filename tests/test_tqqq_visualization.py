"""TQQQ 시뮬레이션 시각화 모듈 테스트

visualization.py의 차트 생성 함수들을 검증한다.
- 반환 타입 검증 (plotly.graph_objects.Figure)
- 필수 trace 존재 확인
- 결측치 처리 검증
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_SIMUL_CLOSE,
)
from qbt.tqqq.visualization import (
    create_cumulative_return_diff_chart,
    create_daily_return_diff_histogram,
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
        assert fig.data[0].name == "일일수익률 차이"
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
        y_values = fig.data[0].y
        assert any(y > 0 for y in y_values)
        assert any(y < 0 for y in y_values)
