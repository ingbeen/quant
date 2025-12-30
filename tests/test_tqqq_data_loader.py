"""
TQQQ 도메인 전용 데이터 로더 테스트

이 파일은 무엇을 검증하나요?
1. FFR 데이터가 정확히 로드되는가?
2. 일별 비교 데이터가 정확히 로드되는가?
3. 필수 컬럼이 없으면 즉시 실패하는가?
4. 파일이 없을 때 명확한 에러를 내는가?

왜 중요한가요?
TQQQ 시뮬레이션의 모든 결과는 FFR 데이터와 비교 데이터에 의존합니다.
잘못된 데이터는 잘못된 비용 계산과 검증 결과를 초래합니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.tqqq.data_loader import (
    load_comparison_data,
    load_expense_ratio_data,
    load_ffr_data,
)


class TestLoadFfrData:
    """연방기금금리(FFR) 데이터 로딩 테스트"""

    def test_normal_load(self, tmp_path, sample_ffr_df):
        """
        FFR 데이터 정상 로딩 테스트

        데이터 신뢰성: TQQQ 시뮬레이션의 비용 계산에 필수적인 데이터입니다.

        Given: DATE, VALUE 컬럼이 있는 CSV
        When: load_ffr_data 호출
        Then:
          - VALUE 컬럼이 그대로 유지됨 (rename 없음)
          - 날짜 파싱 및 정렬
        """
        # Given
        csv_path = tmp_path / "ffr.csv"
        sample_ffr_df.to_csv(csv_path, index=False)

        # When
        df = load_ffr_data(csv_path)

        # Then: 원본 CSV 스키마 회귀 탐지를 위해 리터럴 유지
        assert "VALUE" in df.columns, "VALUE 컬럼이 유지되어야 합니다"
        assert "DATE" in df.columns, "DATE 컬럼이 유지되어야 합니다"
        assert len(df) == 3
        # FFR 데이터는 날짜 파싱을 하지 않음 (문자열 그대로 유지)

    def test_value_in_decimal_range(self, tmp_path, sample_ffr_df):
        """
        FFR VALUE 값이 0~1 비율 범위에 있는지 검증

        Given: VALUE가 0~1 범위의 소수인 CSV
        When: load_ffr_data 호출
        Then: VALUE 값이 모두 0~1 사이
        """
        # Given
        csv_path = tmp_path / "ffr.csv"
        sample_ffr_df.to_csv(csv_path, index=False)

        # When
        df = load_ffr_data(csv_path)

        # Then
        assert (df["VALUE"] >= 0).all(), "VALUE 값이 0 이상이어야 합니다"
        assert (df["VALUE"] <= 1).all(), "VALUE 값이 1 이하여야 합니다 (비율 형식)"

    def test_file_not_found(self, tmp_path):
        """
        FFR 파일 부재 테스트

        Given: 존재하지 않는 파일
        When: load_ffr_data 호출
        Then: FileNotFoundError
        """
        # Given
        non_existent = tmp_path / "no_ffr.csv"

        # When & Then
        with pytest.raises(FileNotFoundError):
            load_ffr_data(non_existent)


class TestLoadExpenseRatioData:
    """운용비율(Expense Ratio) 데이터 로딩 테스트"""

    def test_normal_load(self, tmp_path, sample_expense_df):
        """
        Expense Ratio 데이터 정상 로딩 테스트

        Given: DATE, VALUE 컬럼이 있는 CSV
        When: load_expense_ratio_data 호출
        Then:
          - VALUE 컬럼이 그대로 유지됨
          - 날짜 파싱 및 정렬
        """
        # Given
        csv_path = tmp_path / "expense.csv"
        sample_expense_df.to_csv(csv_path, index=False)

        # When
        df = load_expense_ratio_data(csv_path)

        # Then: 원본 CSV 스키마 회귀 탐지를 위해 리터럴 유지
        assert "VALUE" in df.columns, "VALUE 컬럼이 유지되어야 합니다"
        assert "DATE" in df.columns, "DATE 컬럼이 유지되어야 합니다"
        assert len(df) == 3

    def test_value_in_decimal_range(self, tmp_path, sample_expense_df):
        """
        Expense Ratio VALUE 값이 0~1 비율 범위에 있는지 검증

        Given: VALUE가 0~1 범위의 소수인 CSV
        When: load_expense_ratio_data 호출
        Then: VALUE 값이 모두 0~1 사이
        """
        # Given
        csv_path = tmp_path / "expense.csv"
        sample_expense_df.to_csv(csv_path, index=False)

        # When
        df = load_expense_ratio_data(csv_path)

        # Then
        assert (df["VALUE"] >= 0).all(), "VALUE 값이 0 이상이어야 합니다"
        assert (df["VALUE"] <= 1).all(), "VALUE 값이 1 이하여야 합니다 (비율 형식)"

    def test_file_not_found(self, tmp_path):
        """
        Expense Ratio 파일 부재 테스트

        Given: 존재하지 않는 파일
        When: load_expense_ratio_data 호출
        Then: FileNotFoundError
        """
        # Given
        non_existent = tmp_path / "no_expense.csv"

        # When & Then
        with pytest.raises(FileNotFoundError):
            load_expense_ratio_data(non_existent)


class TestLoadComparisonData:
    """비교 데이터 (TQQQ 검증용) 로딩 테스트"""

    def test_normal_load(self, tmp_path):
        """
        비교 데이터 정상 로딩 테스트

        데이터 신뢰성: 시뮬레이션 결과를 실제 데이터와 비교 검증하는 데 사용됩니다.

        Given: Date, Simulated_Close, Actual_Close 컬럼
        When: load_comparison_data 호출
        Then:
          - COMPARISON_COLUMNS 컬럼 존재
          - Date 파싱 및 정렬
        """
        # Given: 비교 데이터 생성 (실제 컬럼명 사용)
        from qbt.common_constants import DISPLAY_DATE
        from qbt.tqqq.constants import (
            COL_ACTUAL_CLOSE,
            COL_ACTUAL_CUMUL_RETURN,
            COL_ACTUAL_DAILY_RETURN,
            COL_CUMUL_MULTIPLE_LOG_DIFF,
            COL_DAILY_RETURN_ABS_DIFF,
            COL_SIMUL_CLOSE,
            COL_SIMUL_CUMUL_RETURN,
            COL_SIMUL_DAILY_RETURN,
        )

        comparison_df = pd.DataFrame(
            {
                DISPLAY_DATE: [date(2023, 1, 2), date(2023, 1, 3)],
                COL_ACTUAL_CLOSE: [100.0, 102.0],
                COL_SIMUL_CLOSE: [100.5, 101.8],
                COL_ACTUAL_DAILY_RETURN: [0.01, 0.02],
                COL_SIMUL_DAILY_RETURN: [0.01, 0.02],
                COL_DAILY_RETURN_ABS_DIFF: [0.0, 0.0],
                COL_ACTUAL_CUMUL_RETURN: [0.01, 0.03],
                COL_SIMUL_CUMUL_RETURN: [0.01, 0.03],
                COL_CUMUL_MULTIPLE_LOG_DIFF: [0.0, 0.0],
            }
        )
        csv_path = tmp_path / "comparison.csv"
        comparison_df.to_csv(csv_path, index=False)

        # When
        df = load_comparison_data(csv_path)

        # Then
        from qbt.common_constants import DISPLAY_DATE
        from qbt.tqqq.constants import COMPARISON_COLUMNS

        for col in COMPARISON_COLUMNS:
            assert col in df.columns, f"필수 컬럼 '{col}'이 없습니다"

        assert len(df) == 2
        # 날짜는 pandas Timestamp로 변환됨 (datetime.date가 아님)
        assert df[DISPLAY_DATE].dtype == "datetime64[ns]", "날짜가 datetime으로 변환되어야 합니다"

    def test_missing_columns(self, tmp_path):
        """
        비교 데이터 필수 컬럼 누락 테스트

        Given: Actual_Close 컬럼 누락
        When: load_comparison_data 호출
        Then: ValueError
        """
        # Given: 일부 컬럼 누락
        from qbt.common_constants import DISPLAY_DATE
        from qbt.tqqq.constants import COL_SIMUL_CLOSE

        incomplete_df = pd.DataFrame(
            {
                DISPLAY_DATE: [date(2023, 1, 2)],
                COL_SIMUL_CLOSE: [100.0],
                # 다른 필수 컬럼들 누락
            }
        )
        csv_path = tmp_path / "incomplete_comparison.csv"
        incomplete_df.to_csv(csv_path, index=False)

        # When & Then
        with pytest.raises(ValueError) as exc_info:
            load_comparison_data(csv_path)

        assert "필수 컬럼" in str(exc_info.value)
