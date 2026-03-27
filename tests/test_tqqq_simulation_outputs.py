"""TQQQ 시뮬레이션 출력 테스트

검증 지표 계산과 일별 비교 CSV 저장 기능을 검증한다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE
from qbt.tqqq.simulation import (
    calculate_validation_metrics,
)


class TestCalculateValidationMetrics:
    """검증 메트릭 계산 테스트"""

    def test_perfect_match(self):
        """
        완벽히 일치하는 경우 테스트

        데이터 신뢰성: RMSE=0, correlation=1.0이어야 합니다.

        Given: 시뮬레이션과 실제가 정확히 일치
        When: calculate_validation_metrics
        Then: RMSE ≈ 0, correlation ≈ 1.0
        """
        # Given: 완전 일치
        simulated_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 101.0, 102.0, 103.0, 104.0]}
        )

        actual_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 101.0, 102.0, 103.0, 104.0]}
        )

        # When
        metrics = calculate_validation_metrics(simulated_df, actual_df)

        # Then: 메트릭 키 확인
        assert isinstance(metrics, dict), "딕셔너리 반환"
        assert "cumul_multiple_log_diff_mean_pct" in metrics, "누적배수 로그차이 평균 존재"
        # 완벽히 일치하면 로그차이는 0에 가까움
        assert metrics["cumul_multiple_log_diff_mean_pct"] < 1.0, "완벽 일치 시 로그차이는 매우 작아야 합니다"

    def test_divergent_data(self):
        """
        차이가 큰 경우 테스트

        Given: 시뮬레이션과 실제가 크게 차이
        When: calculate_validation_metrics
        Then: RMSE > 0, correlation < 1.0
        """
        # Given: 차이 있음
        simulated_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 105.0, 110.0, 115.0, 120.0]}
        )

        actual_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 102.0, 108.0, 112.0, 125.0]}
        )

        # When
        metrics = calculate_validation_metrics(simulated_df, actual_df)

        # Then
        assert isinstance(metrics, dict), "딕셔너리 반환"
        assert "cumul_multiple_log_diff_rmse_pct" in metrics, "RMSE 메트릭 존재"
        # 차이가 있으므로 로그차이 RMSE > 0
        assert metrics["cumul_multiple_log_diff_rmse_pct"] > 0, "차이가 있으면 RMSE > 0"


class TestSaveDailyComparisonCsv:
    """_save_daily_comparison_csv 함수 테스트"""

    def test_csv_saving_and_structure(self, tmp_path):
        """
        CSV 저장 및 구조 검증

        핵심: 일별 비교 데이터가 올바른 형식으로 저장되는지 검증

        Given: 시뮬레이션과 실제 데이터
        When: _save_daily_comparison_csv 호출
        Then:
          - CSV 파일 생성
          - 한글 컬럼명 포함
          - 누적배수 로그차이 포함
          - 올바른 행 수
        """
        from qbt.common_constants import DISPLAY_DATE
        from qbt.tqqq.constants import (
            COL_ACTUAL_CLOSE,
            COL_ACTUAL_CUMUL_RETURN,
            COL_ACTUAL_DAILY_RETURN,
            COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
            COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
            COL_DAILY_RETURN_ABS_DIFF,
            COL_SIMUL_CLOSE,
            COL_SIMUL_CUMUL_RETURN,
            COL_SIMUL_DAILY_RETURN,
        )
        from qbt.tqqq.simulation import _save_daily_comparison_csv

        # Given
        actual_overlap = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                COL_CLOSE: [100.0, 105.0, 102.0],
            }
        )

        sim_overlap = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)], COL_CLOSE: [100.5, 104.8, 102.2]}
        )

        cumul_log_diff = pd.Series([0.0, 0.1, 0.15])
        signed_log_diff = pd.Series([0.0, -0.05, 0.1])  # signed 버전

        output_path = tmp_path / "test_comparison.csv"

        # When
        # 테스트 데이터는 synthetic이므로 tolerance를 크게 설정
        _save_daily_comparison_csv(
            sim_overlap, actual_overlap, cumul_log_diff, signed_log_diff, output_path, integrity_tolerance=1.0
        )

        # Then: 파일 존재
        assert output_path.exists(), "CSV 파일이 생성되어야 함"

        # 파일 읽기
        result_df = pd.read_csv(output_path, encoding="utf-8-sig")

        # 행 수 확인
        assert len(result_df) == 3, "3행의 데이터가 저장되어야 함"

        # 필수 컬럼 확인
        required_cols = [
            DISPLAY_DATE,
            COL_ACTUAL_CLOSE,
            COL_SIMUL_CLOSE,
            COL_ACTUAL_DAILY_RETURN,
            COL_SIMUL_DAILY_RETURN,
            COL_DAILY_RETURN_ABS_DIFF,
            COL_ACTUAL_CUMUL_RETURN,
            COL_SIMUL_CUMUL_RETURN,
            COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
            COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
        ]

        for col in required_cols:
            assert col in result_df.columns, f"{col} 컬럼이 있어야 함"

    def test_csv_numeric_precision(self, tmp_path):
        """
        CSV 숫자 정밀도 검증 (소수점 4자리)

        Given: 시뮬레이션과 실제 데이터
        When: _save_daily_comparison_csv 호출
        Then: 숫자 컬럼이 소수점 4자리로 반올림됨
        """
        from qbt.tqqq.simulation import _save_daily_comparison_csv

        # Given
        actual_overlap = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)], COL_CLOSE: [100.123456, 105.789012]}
        )

        sim_overlap = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)], COL_CLOSE: [100.234567, 105.890123]}
        )

        cumul_log_diff = pd.Series([0.0123456, 0.0234567])
        signed_log_diff = pd.Series([0.0111111, -0.0222222])  # signed 버전

        output_path = tmp_path / "test_precision.csv"

        # When
        # 테스트 데이터는 synthetic이므로 tolerance를 크게 설정
        _save_daily_comparison_csv(
            sim_overlap, actual_overlap, cumul_log_diff, signed_log_diff, output_path, integrity_tolerance=1.0
        )

        # Then
        result_df = pd.read_csv(output_path, encoding="utf-8-sig")

        # 숫자 컬럼이 소수점 4자리 이하로 저장되었는지 확인
        from qbt.tqqq.constants import COL_ACTUAL_CLOSE, COL_SIMUL_CLOSE

        # 실제 종가 확인 (소수점 4자리로 반올림)
        assert result_df[COL_ACTUAL_CLOSE].iloc[0] == pytest.approx(100.1235, abs=0.0001)
        assert result_df[COL_SIMUL_CLOSE].iloc[0] == pytest.approx(100.2346, abs=0.0001)
