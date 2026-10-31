"""TQQQ 시뮬레이션 출력 테스트

검증 지표 계산과 일별 비교 CSV 저장 기능을 검증한다.
"""

import math
from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, DISPLAY_DATE, ROUND_PRICE
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_ACTUAL_CUMUL_RETURN,
    COL_ACTUAL_DAILY_RETURN,
    COL_ACTUAL_HIGH,
    COL_ACTUAL_LOW,
    COL_ACTUAL_OPEN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_SIMUL_CLOSE,
    COL_SIMUL_CUMUL_RETURN,
    COL_SIMUL_DAILY_RETURN,
    COL_SIMUL_HIGH,
    COL_SIMUL_LOW,
    COL_SIMUL_OPEN,
    DAILY_COMPARISON_TARGETS,
)
from qbt.tqqq.simulation import (
    _save_daily_comparison_csv,
    calculate_validation_metrics,
)


class TestDailyComparisonTargets:
    """일별 비교 상품 표의 계약 테스트"""

    def test_leverage_by_product(self):
        """
        목적: 상품별 배율을 숫자로 고정한다 — 배율이 틀리면 CSV 는 그대로 만들어지고 오차만 커 보인다

        Given: 일별 비교 상품 표
        When: 이름별 배율을 모은다
        Then: TQQQ 3배, QLD 2배
        """
        # When
        leverage_by_name = {name: leverage for name, _, leverage, _ in DAILY_COMPARISON_TARGETS}

        # Then
        assert leverage_by_name == {"TQQQ": 3.0, "QLD": 2.0}

    def test_files_by_product(self):
        """
        목적: 상품별 실물 시세와 CSV 파일을 고정한다 — 실물이 바뀌면 다른 상품과 비교한 값이, CSV 가 겹치면
              뒤 상품이 앞 상품 결과를 덮어쓴 값이 에러 없이 나간다

        Given: 일별 비교 상품 표
        When: 이름별 파일 이름을 모은다
        Then: 상품마다 자기 실물 시세와 자기 CSV 다
        """
        # When
        files_by_name = {name: (actual.name, csv.name) for name, actual, _, csv in DAILY_COMPARISON_TARGETS}

        # Then
        assert files_by_name == {
            "TQQQ": ("TQQQ_max.csv", "tqqq_daily_comparison.csv"),
            "QLD": ("QLD_max.csv", "qld_daily_comparison.csv"),
        }


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

    def test_log_diff_metrics_use_magnitude_of_signed(self):
        """
        목적: 로그차이 지표(평균 · RMSE · 최대)가 누적배수 로그차이의 크기(부호 뺀 값)로 계산됨을 검증 —
              부호 있는 값을 그대로 평균하면 위아래 오차가 상쇄돼 작게 나온다

        Given: 시뮬이 실제보다 한 번 높고 한 번 낮은 3일 데이터
        When: calculate_validation_metrics
        Then: 손으로 계산한 |100 × ln(M_sim / M_real)| 의 평균 · RMSE · 최대와 같고, 누적수익률은 마지막 날 기준 비율이다
        """
        # Given: 실제 100 → 110 → 100, 시뮬 100 → 121 → 90
        simulated_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)], COL_CLOSE: [100.0, 121.0, 90.0]}
        )
        actual_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)], COL_CLOSE: [100.0, 110.0, 100.0]}
        )
        diffs = [0.0, abs(100 * math.log(1.21 / 1.10)), abs(100 * math.log(0.90 / 1.00))]

        # When
        metrics = calculate_validation_metrics(simulated_df, actual_df)

        # Then
        assert metrics["cumul_multiple_log_diff_mean_pct"] == pytest.approx(sum(diffs) / 3, abs=1e-12)
        assert metrics["cumul_multiple_log_diff_rmse_pct"] == pytest.approx(
            math.sqrt(sum(d**2 for d in diffs) / 3), abs=1e-12
        )
        assert metrics["cumul_multiple_log_diff_max_pct"] == pytest.approx(max(diffs), abs=1e-12)
        assert metrics["cumulative_return_actual"] == pytest.approx(0.0, abs=1e-12)
        assert metrics["cumulative_return_simulated"] == pytest.approx(-0.10, abs=1e-12)


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
          - 누적배수 로그차이 포함 (abs 는 signed 의 크기)
          - 올바른 행 수
        """
        # Given
        actual_overlap = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                COL_OPEN: [99.0, 104.0, 101.0],
                COL_HIGH: [101.0, 106.0, 103.0],
                COL_LOW: [98.0, 103.0, 100.0],
                COL_CLOSE: [100.0, 105.0, 102.0],
            }
        )

        sim_overlap = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                COL_OPEN: [99.5, 104.5, 101.5],
                COL_HIGH: [101.5, 106.5, 103.5],
                COL_LOW: [98.5, 103.5, 100.5],
                COL_CLOSE: [100.5, 104.8, 102.2],
            }
        )

        actual_cumulative = pd.Series([0.0, 5.0, 2.0])
        sim_cumulative = pd.Series([0.0, 4.28, 1.69])
        signed_log_diff = pd.Series([0.0, -0.05, 0.1])

        output_path = tmp_path / "test_comparison.csv"

        # When
        _save_daily_comparison_csv(
            sim_overlap, actual_overlap, actual_cumulative, sim_cumulative, signed_log_diff, output_path
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
            COL_ACTUAL_OPEN,
            COL_SIMUL_OPEN,
            COL_ACTUAL_HIGH,
            COL_SIMUL_HIGH,
            COL_ACTUAL_LOW,
            COL_SIMUL_LOW,
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

        # abs 로그차이는 signed 의 크기다
        assert result_df[COL_CUMUL_MULTIPLE_LOG_DIFF_ABS].tolist() == pytest.approx([0.0, 0.05, 0.1], abs=1e-9)

        # 실제 · 시뮬 열이 각각 자기 표의 그 가격이다 — 열을 바꿔 넣으면 비교가 조용히 틀린다
        assert result_df[COL_ACTUAL_HIGH].tolist() == [101.0, 106.0, 103.0]
        assert result_df[COL_SIMUL_HIGH].tolist() == [101.5, 106.5, 103.5]
        assert result_df[COL_ACTUAL_LOW].tolist() == [98.0, 103.0, 100.0]
        assert result_df[COL_SIMUL_LOW].tolist() == [98.5, 103.5, 100.5]
        assert result_df[COL_ACTUAL_OPEN].tolist() == [99.0, 104.0, 101.0]
        assert result_df[COL_SIMUL_OPEN].tolist() == [99.5, 104.5, 101.5]

    def test_csv_numeric_precision(self, tmp_path):
        """
        목적: 시가 · 고가 · 저가 · 종가는 가격 자릿수(ROUND_PRICE), % 열은 4자리로 반올림됨을 검증 — % 열을 백분율 기본(2자리)으로
              낮추면 스프레드 랩의 일일 증분 오차 재계산이 깨지므로 4자리는 정책 값으로 고정한다

        Given: 소수점이 긴 가격과 누적수익률 · 로그차이
        When: _save_daily_comparison_csv 호출
        Then: 가격 · % 열이 각 자릿수로 정확히 반올림됨
        """
        # Given
        actual_overlap = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)],
                COL_OPEN: [100.111111, 105.111111],
                COL_HIGH: [100.555555, 105.999999],
                COL_LOW: [100.012345, 105.012345],
                COL_CLOSE: [100.123456, 105.789012],
            }
        )

        sim_overlap = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)],
                COL_OPEN: [100.222222, 105.222222],
                COL_HIGH: [100.666666, 105.888888],
                COL_LOW: [100.023456, 105.023456],
                COL_CLOSE: [100.234567, 105.890123],
            }
        )

        actual_cumulative = pd.Series([0.0, 5.6593456])
        sim_cumulative = pd.Series([0.0, 5.6408123])
        signed_log_diff = pd.Series([0.0111111, -0.0222222])

        output_path = tmp_path / "test_precision.csv"

        # When
        _save_daily_comparison_csv(
            sim_overlap, actual_overlap, actual_cumulative, sim_cumulative, signed_log_diff, output_path
        )

        # Then
        result_df = pd.read_csv(output_path, encoding="utf-8-sig")

        assert result_df[COL_ACTUAL_CLOSE].iloc[0] == pytest.approx(round(100.123456, ROUND_PRICE), abs=1e-9)
        assert result_df[COL_SIMUL_CLOSE].iloc[0] == pytest.approx(round(100.234567, ROUND_PRICE), abs=1e-9)
        assert result_df[COL_ACTUAL_OPEN].iloc[0] == pytest.approx(round(100.111111, ROUND_PRICE), abs=1e-9)
        assert result_df[COL_SIMUL_OPEN].iloc[0] == pytest.approx(round(100.222222, ROUND_PRICE), abs=1e-9)
        assert result_df[COL_ACTUAL_HIGH].iloc[0] == pytest.approx(round(100.555555, ROUND_PRICE), abs=1e-9)
        assert result_df[COL_SIMUL_HIGH].iloc[0] == pytest.approx(round(100.666666, ROUND_PRICE), abs=1e-9)
        assert result_df[COL_ACTUAL_LOW].iloc[0] == pytest.approx(round(100.012345, ROUND_PRICE), abs=1e-9)
        assert result_df[COL_SIMUL_LOW].iloc[0] == pytest.approx(round(100.023456, ROUND_PRICE), abs=1e-9)
        assert result_df[COL_ACTUAL_CUMUL_RETURN].iloc[1] == pytest.approx(5.6593, abs=1e-9)
        assert result_df[COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED].iloc[1] == pytest.approx(-0.0222, abs=1e-9)
        # (105.789012 / 100.123456 - 1) * 100 = 5.65857…
        assert result_df[COL_ACTUAL_DAILY_RETURN].iloc[1] == pytest.approx(5.6586, abs=1e-9)
