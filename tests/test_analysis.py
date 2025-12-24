"""
backtest/analysis 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 이동평균(MA) 계산이 정확한가?
2. 백테스트 성과 지표(CAGR, MDD, 승률 등)가 정확한가?
3. 거래가 없을 때 안전하게 처리되는가?
4. 출력 DataFrame의 스키마가 일관적인가?

왜 중요한가요?
잘못된 지표 계산은 전략 평가를 왜곡합니다.
예: MDD가 실제보다 작게 계산되면 위험을 과소평가하게 됩니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.analysis import add_single_moving_average, calculate_summary
from qbt.common_constants import EPSILON


class TestAddSingleMovingAverage:
    """이동평균 계산 테스트 클래스"""

    def test_normal_calculation(self):
        """
        정상적인 이동평균 계산 테스트

        데이터 신뢰성: MA는 매매 신호 생성의 핵심이므로 정확해야 합니다.

        Given: 5일치 종가 데이터
        When: window=3으로 이동평균 계산
        Then:
          - MA_3 컬럼 추가됨
          - 처음 2행은 NaN (window-1개)
          - 3행부터 정확한 평균값
        """
        # Given: 간단한 데이터 (100, 110, 120, 130, 140)
        df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 1) for i in range(5)], "Close": [100.0, 110.0, 120.0, 130.0, 140.0]}
        )

        # When: 3일 이동평균
        result = add_single_moving_average(df, window=3)

        # Then: 컬럼 추가 확인
        assert "ma_3" in result.columns, "ma_3 컬럼이 추가되어야 합니다"

        # 처음 2행은 NaN (데이터 부족)
        assert pd.isna(result.iloc[0]["ma_3"]), "window-1개는 NaN이어야 합니다"
        assert pd.isna(result.iloc[1]["ma_3"])

        # 3행부터 계산 확인
        # 3일(idx 2): (100+110+120)/3 = 110.0
        assert abs(result.iloc[2]["ma_3"] - 110.0) < EPSILON, "3일 이동평균: (100+110+120)/3 = 110.0"

        # 4일(idx 3): (110+120+130)/3 = 120.0
        assert abs(result.iloc[3]["ma_3"] - 120.0) < EPSILON

        # 5일(idx 4): (120+130+140)/3 = 130.0
        assert abs(result.iloc[4]["ma_3"] - 130.0) < EPSILON

    def test_window_larger_than_data(self):
        """
        window가 데이터보다 클 때 테스트

        안정성: 모든 값이 NaN이어야 하며, 에러가 나면 안 됩니다.

        Given: 3행 데이터
        When: window=10
        Then: 모든 MA 값이 NaN
        """
        # Given
        df = pd.DataFrame(
            {"Date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)], "Close": [100.0, 110.0, 120.0]}
        )

        # When
        result = add_single_moving_average(df, window=10)

        # Then: 모두 NaN
        assert result["ma_10"].isna().all(), "데이터가 부족하면 모든 MA 값이 NaN이어야 합니다"

    def test_invalid_window(self):
        """
        잘못된 window 값 테스트

        안정성: 0이나 음수는 거부해야 합니다.

        Given: 정상 데이터
        When: window=0 또는 음수
        Then: ValueError
        """
        # Given
        df = pd.DataFrame({"Date": [date(2023, 1, 1)], "Close": [100.0]})

        # When & Then: window=0
        with pytest.raises(ValueError):
            add_single_moving_average(df, window=0)

        # window=-5
        with pytest.raises(ValueError):
            add_single_moving_average(df, window=-5)


class TestCalculateSummary:
    """백테스트 성과 지표 계산 테스트"""

    def test_normal_summary(self):
        """
        정상적인 성과 지표 계산 테스트

        데이터 신뢰성: 핵심 지표들이 수학적으로 정확해야 합니다.

        Given:
          - 초기 자본 10,000
          - 2년 운용 (730일)
          - 승 1회, 패 1회
          - Equity curve: 시작 10,000 → 중간 12,000 → 최종 15,000
        When: calculate_summary 호출
        Then:
          - total_return_pct ≈ 50%
          - CAGR 정확히 계산
          - MDD 정확히 계산
          - win_rate = 50%
        """
        # Given: 거래 내역 (실제 컬럼명: pnl)
        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 1, 1), date(2021, 6, 1)],
                "exit_date": [date(2021, 3, 1), date(2021, 9, 1)],
                "pnl": [2000.0, -500.0],  # 승 1회, 패 1회
            }
        )

        # Equity curve (실제 컬럼명: equity 소문자)
        equity_df = pd.DataFrame(
            {
                "Date": [
                    date(2021, 1, 1),
                    date(2021, 6, 1),  # 중간 peak
                    date(2021, 8, 1),  # drawdown
                    date(2023, 1, 1),  # 최종 (2년 후)
                ],
                "equity": [10000.0, 12000.0, 11000.0, 15000.0],
            }
        )

        initial_capital = 10000.0

        # When
        summary = calculate_summary(trades_df, equity_df, initial_capital)

        # Then: 딕셔너리 반환 확인
        assert isinstance(summary, dict), "딕셔너리를 반환해야 합니다"

        # 최종 자본
        assert abs(summary["final_capital"] - 15000.0) < EPSILON, "최종 자본은 equity curve의 마지막 값"

        # 총 수익률: (15000 - 10000) / 10000 * 100 = 50%
        assert abs(summary["total_return_pct"] - 50.0) < 0.1, "총 수익률 = (15000-10000)/10000 * 100 = 50%"

        # CAGR 계산: (15000/10000)^(1/2) - 1 ≈ 0.2247 = 22.47%
        # 2년 = 730일 (대략)
        expected_cagr = ((15000.0 / 10000.0) ** (365.0 / 730.0) - 1) * 100
        assert (
            abs(summary["cagr"] - expected_cagr) < 1.0
        ), f"CAGR 계산 오차가 큽니다. 기대: {expected_cagr:.2f}, 실제: {summary['cagr']:.2f}"

        # MDD: 12000 → 11000 = -8.33%
        expected_mdd = (11000.0 / 12000.0 - 1) * 100  # ≈ -8.33%
        assert abs(summary["mdd"] - expected_mdd) < 0.1, "MDD = (11000/12000 - 1) * 100 ≈ -8.33%"

        # 승률: 1승 / 2거래 = 50%
        assert abs(summary["win_rate"] - 50.0) < EPSILON, "승률 = 1/2 * 100 = 50%"

        # 거래 횟수
        assert summary["total_trades"] == 2

    def test_no_trades(self):
        """
        거래가 없을 때 테스트

        안정성: 거래 0건일 때도 안전하게 처리해야 합니다.

        Given: 빈 trades_df
        When: calculate_summary 호출
        Then:
          - win_rate = 0.0
          - total_trades = 0
          - 기타 지표는 equity 기반으로 계산
        """
        # Given: 빈 거래 (실제 컬럼명: pnl)
        trades_df = pd.DataFrame(columns=["entry_date", "exit_date", "pnl"])

        equity_df = pd.DataFrame({"Date": [date(2021, 1, 1), date(2022, 1, 1)], "equity": [10000.0, 10000.0]})  # 변화 없음

        initial_capital = 10000.0

        # When
        summary = calculate_summary(trades_df, equity_df, initial_capital)

        # Then
        assert summary["total_trades"] == 0, "거래 횟수는 0"
        assert summary["win_rate"] == 0.0, "거래가 없으면 승률은 0"
        assert abs(summary["total_return_pct"]) < EPSILON, "수익률은 0%"

    def test_all_losing_trades(self):
        """
        모든 거래가 손실일 때 테스트

        Given: 3개 거래 모두 Profit < 0
        When: calculate_summary
        Then: win_rate = 0.0
        """
        # Given (실제 컬럼명: pnl, equity)
        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 1, 1), date(2021, 2, 1), date(2021, 3, 1)],
                "exit_date": [date(2021, 1, 15), date(2021, 2, 15), date(2021, 3, 15)],
                "pnl": [-100.0, -50.0, -200.0],
            }
        )

        equity_df = pd.DataFrame({"Date": [date(2021, 1, 1), date(2021, 4, 1)], "equity": [10000.0, 9650.0]})  # -350

        # When
        summary = calculate_summary(trades_df, equity_df, 10000.0)

        # Then
        assert summary["win_rate"] == 0.0, "모두 손실이면 승률 0%"
        assert summary["total_trades"] == 3

    def test_mdd_zero(self):
        """
        MDD가 0인 경우 (계속 상승)

        Given: Equity가 계속 증가
        When: calculate_summary
        Then: MDD = 0.0
        """
        # Given (실제 컬럼명: pnl, equity)
        trades_df = pd.DataFrame({"entry_date": [date(2021, 1, 1)], "exit_date": [date(2021, 2, 1)], "pnl": [1000.0]})

        equity_df = pd.DataFrame(
            {
                "Date": [date(2021, 1, 1), date(2021, 2, 1), date(2021, 3, 1)],
                "equity": [10000.0, 11000.0, 12000.0],  # 계속 상승
            }
        )

        # When
        summary = calculate_summary(trades_df, equity_df, 10000.0)

        # Then
        assert summary["mdd"] == 0.0, "하락이 없으면 MDD는 0"
