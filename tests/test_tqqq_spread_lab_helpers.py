"""
spread_lab_helpers 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 금리 변화 lag 컬럼이 정확히 생성되는가?
2. lag 추가 시 원본 DataFrame의 불변성이 보장되는가?

왜 중요한가요?
금리-오차 분석의 lag 피처 생성이 이 함수에 의존합니다.
잘못된 lag 계산은 분석 결과를 오도할 수 있습니다.

Note:
    모든 테스트는 synthetic(고정) 데이터를 사용하여 결정적(deterministic)으로 작성됩니다.
"""

import pandas as pd
import pytest

from qbt.tqqq.constants import (
    COL_DR_LAG1,
    COL_DR_LAG2,
    COL_DR_M,
    COL_MONTH,
)
from qbt.tqqq.spread_lab_helpers import add_rate_change_lags


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
