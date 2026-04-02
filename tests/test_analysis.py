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

from qbt.backtest.analysis import (
    add_single_moving_average,
    calculate_calmar,
    calculate_regime_summaries,
    calculate_summary,
)
from qbt.backtest.types import MarketRegimeDict
from qbt.common_constants import COL_CLOSE, COL_DATE, EPSILON


class TestAddSingleMovingAverage:
    """이동평균 계산 테스트 클래스"""

    def test_normal_calculation(self, enable_numpy_warnings):
        """
        정상적인 이동평균 계산 테스트

        데이터 신뢰성: MA는 매매 신호 생성의 핵심이므로 정확해야 합니다.

        Given: 5일치 종가 데이터
        When: window=3으로 이동평균 계산
        Then:
          - MA_3 컬럼 추가됨
          - 처음 2행은 NaN (window-1개)
          - 3행부터 정확한 평균값

        Note: enable_numpy_warnings 픽스처로 부동소수점 오류 감지
        """
        # Given: 간단한 데이터 (100, 110, 120, 130, 140)
        df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 110.0, 120.0, 130.0, 140.0]}
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
        assert result.iloc[2]["ma_3"] == pytest.approx(110.0, abs=EPSILON), "3일 이동평균: (100+110+120)/3 = 110.0"

        # 4일(idx 3): (110+120+130)/3 = 120.0
        assert result.iloc[3]["ma_3"] == pytest.approx(120.0, abs=EPSILON)

        # 5일(idx 4): (120+130+140)/3 = 130.0
        assert result.iloc[4]["ma_3"] == pytest.approx(130.0, abs=EPSILON)

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
            {COL_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)], COL_CLOSE: [100.0, 110.0, 120.0]}
        )

        # When
        result = add_single_moving_average(df, window=10)

        # Then: 모두 NaN
        assert result["ma_10"].isna().all(), "데이터가 부족하면 모든 MA 값이 NaN이어야 합니다"

    @pytest.mark.parametrize("invalid_window", [0, -5, -1])
    def test_invalid_window(self, invalid_window):
        """
        잘못된 window 값 테스트

        안정성: 0이나 음수는 거부해야 합니다.

        Given: 정상 데이터
        When: window=0 또는 음수 (parametrize로 여러 값 테스트)
        Then: ValueError

        Args:
            invalid_window: 테스트할 잘못된 window 값 (0, -5, -1)
        """
        # Given
        df = pd.DataFrame({COL_DATE: [date(2023, 1, 1)], COL_CLOSE: [100.0]})

        # When & Then
        with pytest.raises(ValueError):
            add_single_moving_average(df, window=invalid_window)


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
                COL_DATE: [
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
        assert summary["final_capital"] == pytest.approx(15000.0, abs=EPSILON), "최종 자본은 equity curve의 마지막 값"

        # 총 수익률: (15000 - 10000) / 10000 * 100 = 50%
        assert summary["total_return_pct"] == pytest.approx(50.0, abs=0.1), "총 수익률 = (15000-10000)/10000 * 100 = 50%"

        # CAGR 계산: (15000/10000)^(1/2) - 1 ≈ 0.2247 = 22.47%
        # 2년 = 730일 (대략)
        expected_cagr = ((15000.0 / 10000.0) ** (365.0 / 730.0) - 1) * 100
        assert summary["cagr"] == pytest.approx(
            expected_cagr, abs=1.0
        ), f"CAGR 계산 오차가 큽니다. 기대: {expected_cagr:.2f}, 실제: {summary['cagr']:.2f}"

        # MDD: 12000 → 11000 = -8.33%
        expected_mdd = (11000.0 / 12000.0 - 1) * 100  # ≈ -8.33%
        assert summary["mdd"] == pytest.approx(expected_mdd, abs=0.1), "MDD = (11000/12000 - 1) * 100 ≈ -8.33%"

        # 승률: 1승 / 2거래 = 50%
        assert summary["win_rate"] == pytest.approx(50.0, abs=EPSILON), "승률 = 1/2 * 100 = 50%"

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

        equity_df = pd.DataFrame(
            {COL_DATE: [date(2021, 1, 1), date(2022, 1, 1)], "equity": [10000.0, 10000.0]}
        )  # 변화 없음

        initial_capital = 10000.0

        # When
        summary = calculate_summary(trades_df, equity_df, initial_capital)

        # Then
        assert summary["total_trades"] == 0, "거래 횟수는 0"
        assert summary["win_rate"] == 0.0, "거래가 없으면 승률은 0"
        assert summary["total_return_pct"] == pytest.approx(0, abs=EPSILON), "수익률은 0%"

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

        equity_df = pd.DataFrame({COL_DATE: [date(2021, 1, 1), date(2021, 4, 1)], "equity": [10000.0, 9650.0]})  # -350

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
                COL_DATE: [date(2021, 1, 1), date(2021, 2, 1), date(2021, 3, 1)],
                "equity": [10000.0, 11000.0, 12000.0],  # 계속 상승
            }
        )

        # When
        summary = calculate_summary(trades_df, equity_df, 10000.0)

        # Then
        assert summary["mdd"] == 0.0, "하락이 없으면 MDD는 0"

    @pytest.mark.parametrize(
        "invalid_capital,equity_values",
        [
            (0.0, [0.0, 1000.0]),  # zero capital
            (-10000.0, [-10000.0, -9000.0]),  # negative capital
        ],
        ids=["zero_capital", "negative_capital"],
    )
    def test_calculate_summary_invalid_initial_capital(self, invalid_capital, equity_values):
        """
        initial_capital이 유효하지 않은 경우 방어 테스트

        정책: initial_capital <= 0이면 즉시 ValueError 발생
        이유: 수익률 계산 시 나눗셈 분모로 사용되므로 0/음수 불가

        Given: initial_capital=0 또는 음수 (parametrize로 여러 값 테스트)
        When: calculate_summary 호출
        Then: ValueError 발생

        Args:
            invalid_capital: 테스트할 잘못된 초기 자본 값 (0.0, -10000.0)
            equity_values: 해당 케이스의 equity 값 리스트
        """
        # Given
        trades_df = pd.DataFrame({"entry_date": [date(2021, 1, 1)], "exit_date": [date(2021, 2, 1)], "pnl": [1000.0]})

        equity_df = pd.DataFrame({COL_DATE: [date(2021, 1, 1), date(2021, 2, 1)], "equity": equity_values})

        # When & Then
        with pytest.raises(ValueError) as exc_info:
            calculate_summary(trades_df, equity_df, initial_capital=invalid_capital)

        error_msg = str(exc_info.value)
        assert "initial_capital" in error_msg and "양수" in error_msg, "initial_capital 검증 에러 메시지"

    def test_calculate_summary_zero_peak(self):
        """
        equity가 모두 0인 경우 RuntimeError 발생 테스트

        정책: equity=0은 final_capital<=0 또는 peak=0으로 내부 불변조건 위반
        이유: initial_capital > 0이면 equity=0은 논리적으로 불가능

        Given: equity curve가 모두 0 (극단적 케이스)
        When: calculate_summary 호출
        Then: RuntimeError 발생 (final_capital <= 0 또는 peak=0)
        """
        # Given
        trades_df = pd.DataFrame(columns=["entry_date", "exit_date", "pnl"])

        equity_df = pd.DataFrame(
            {COL_DATE: [date(2021, 1, 1), date(2021, 2, 1), date(2021, 3, 1)], "equity": [0.0, 0.0, 0.0]}
        )

        initial_capital = 10000.0

        # When / Then
        with pytest.raises(RuntimeError, match="불변조건"):
            calculate_summary(trades_df, equity_df, initial_capital)

    def test_calmar_normal(self):
        """
        정상적인 Calmar Ratio 계산 테스트

        정책: Calmar = CAGR / |MDD|

        Given:
          - Equity curve: 10000 → 12000 → 11000 → 15000 (2년)
          - CAGR ≈ 22.47%, MDD ≈ -8.33%
        When: calculate_summary 호출
        Then: calmar ≈ 22.47 / 8.33 ≈ 2.70 (CAGR/|MDD|)
        """
        # Given
        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 1, 1)],
                "exit_date": [date(2021, 6, 1)],
                "pnl": [5000.0],
            }
        )

        equity_df = pd.DataFrame(
            {
                COL_DATE: [
                    date(2021, 1, 1),
                    date(2021, 6, 1),
                    date(2021, 8, 1),
                    date(2023, 1, 1),
                ],
                "equity": [10000.0, 12000.0, 11000.0, 15000.0],
            }
        )

        # When
        summary = calculate_summary(trades_df, equity_df, 10000.0)

        # Then
        assert "calmar" in summary, "summary에 calmar 키가 있어야 합니다"
        expected_calmar = summary["cagr"] / abs(summary["mdd"])
        assert summary["calmar"] == pytest.approx(
            expected_calmar, abs=0.01
        ), f"Calmar = CAGR / |MDD| = {summary['cagr']:.2f} / {abs(summary['mdd']):.2f}"

    def test_calmar_mdd_zero(self):
        """
        MDD=0일 때 Calmar 안전 처리 테스트

        정책: |MDD| < EPSILON이면 Calmar = 1e10 + CAGR (CAGR > 0) 또는 0.0

        Given: Equity가 계속 상승 (MDD=0)
        When: calculate_summary 호출
        Then: calmar = 1e10 + CAGR (양수 CAGR이므로 매우 큰 값)
        """
        # Given
        trades_df = pd.DataFrame({"entry_date": [date(2021, 1, 1)], "exit_date": [date(2021, 2, 1)], "pnl": [1000.0]})

        equity_df = pd.DataFrame(
            {
                COL_DATE: [date(2021, 1, 1), date(2021, 6, 1), date(2022, 1, 1)],
                "equity": [10000.0, 11000.0, 12000.0],
            }
        )

        # When
        summary = calculate_summary(trades_df, equity_df, 10000.0)

        # Then: MDD=0이고 CAGR>0이면 매우 큰 값
        assert summary["mdd"] == 0.0, "하락이 없으면 MDD는 0"
        assert summary["calmar"] > 1e10, "MDD=0, CAGR>0이면 Calmar는 1e10보다 커야 합니다"

    def test_calmar_empty_equity(self):
        """
        빈 equity_df일 때 Calmar = 0.0 테스트

        Given: 빈 equity_df
        When: calculate_summary 호출
        Then: calmar = 0.0
        """
        # Given
        trades_df = pd.DataFrame(columns=["entry_date", "exit_date", "pnl"])
        equity_df = pd.DataFrame(columns=[COL_DATE, "equity"])

        # When
        summary = calculate_summary(trades_df, equity_df, 10000.0)

        # Then
        assert summary["calmar"] == 0.0, "빈 equity_df이면 calmar는 0.0"

    def test_empty_equity_contains_start_end_date_keys(self):
        """
        목적: 빈 equity_df일 때 start_date, end_date 키가 존재하는지 검증

        정책: 다운스트림 코드에서 start_date/end_date 접근 시 KeyError 방지.
              빈 equity_df이면 기간 정보가 없으므로 None을 반환한다.

        Given: 빈 equity_df
        When: calculate_summary 호출
        Then: start_date, end_date 키가 존재하고 값은 None
        """
        # Given
        trades_df = pd.DataFrame(columns=["entry_date", "exit_date", "pnl"])
        equity_df = pd.DataFrame(columns=[COL_DATE, "equity"])

        # When
        summary = calculate_summary(trades_df, equity_df, 10000.0)

        # Then
        assert "start_date" in summary, "빈 equity_df 반환에도 start_date 키가 존재해야 함"
        assert "end_date" in summary, "빈 equity_df 반환에도 end_date 키가 존재해야 함"
        assert summary["start_date"] is None, "빈 equity_df이면 start_date는 None"
        assert summary["end_date"] is None, "빈 equity_df이면 end_date는 None"

    def test_cagr_runtime_error_when_final_capital_zero(self) -> None:
        """
        목적: final_capital이 0 이하일 때 RuntimeError가 발생하는지 검증

        정책: 비레버리지 백테스트에서 전액 손실은 내부 불변조건 위반
              final_capital <= 0은 논리적으로 불가능하므로 RuntimeError 발생

        Given: equity가 10000 -> 0으로 하락, 기간 1년
        When: calculate_summary 호출
        Then: RuntimeError 발생
        """
        # Given
        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 1, 1)],
                "exit_date": [date(2021, 6, 1)],
                "pnl": [-10000.0],
            }
        )
        equity_df = pd.DataFrame(
            {
                COL_DATE: [date(2021, 1, 1), date(2022, 1, 1)],
                "equity": [10000.0, 0.0],
            }
        )

        # When / Then
        with pytest.raises(RuntimeError, match="final_capital"):
            calculate_summary(trades_df, equity_df, 10000.0)

    def test_cagr_negative_when_final_capital_very_small(self) -> None:
        """
        목적: final_capital이 매우 작은 양수일 때 CAGR이 큰 음수인지 검증

        Given: equity가 10000 → 1.0으로 하락, 기간 1년
        When: calculate_summary 호출
        Then: CAGR이 큰 음수 (약 -99.99%)
        """
        # Given
        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 1, 1)],
                "exit_date": [date(2021, 6, 1)],
                "pnl": [-9999.0],
            }
        )
        equity_df = pd.DataFrame(
            {
                COL_DATE: [date(2021, 1, 1), date(2022, 1, 1)],
                "equity": [10000.0, 1.0],
            }
        )

        # When
        summary = calculate_summary(trades_df, equity_df, 10000.0)

        # Then: (1/10000)^(1/1) - 1 ≈ -0.9999 = -99.99%
        assert summary["cagr"] < -99.0, "거의 전액 손실 시 CAGR은 -99% 이하"


class TestCalculateDrawdownPctSeries:
    """calculate_drawdown_pct_series 함수 테스트"""

    def test_basic_drawdown_calculation(self):
        """
        목적: drawdown_pct 시리즈가 정확히 계산됨을 검증

        Given: 에쿼티 [100, 110, 90, 120]
        When: calculate_drawdown_pct_series 호출
        Then: [0, 0, -(110-90)/110*100, 0]
        """
        from qbt.backtest.analysis import calculate_drawdown_pct_series

        # Given
        equity = pd.Series([100.0, 110.0, 90.0, 120.0])

        # When
        result = calculate_drawdown_pct_series(equity)

        # Then
        assert result.iloc[0] == pytest.approx(0.0, abs=1e-6)
        assert result.iloc[1] == pytest.approx(0.0, abs=1e-6)
        expected_dd = (90.0 - 110.0) / 110.0 * 100  # -18.18...
        assert result.iloc[2] == pytest.approx(expected_dd, abs=0.01)
        assert result.iloc[3] == pytest.approx(0.0, abs=1e-6)

    def test_monotonically_increasing(self):
        """
        목적: 단조 증가 시 drawdown이 항상 0임을 검증

        Given: 에쿼티 [100, 110, 120, 130]
        When: calculate_drawdown_pct_series 호출
        Then: 모든 값이 0
        """
        from qbt.backtest.analysis import calculate_drawdown_pct_series

        # Given
        equity = pd.Series([100.0, 110.0, 120.0, 130.0])

        # When
        result = calculate_drawdown_pct_series(equity)

        # Then
        assert (result == 0.0).all()

    def test_zero_peak_raises_runtime_error(self):
        """
        목적: peak=0일 때 RuntimeError가 발생함을 검증

        정책: initial_capital > 0이면 peak=0은 내부 불변조건 위반

        Given: 에쿼티 [0, 10, 5] (첫 값이 0)
        When: calculate_drawdown_pct_series 호출
        Then: RuntimeError 발생
        """
        from qbt.backtest.analysis import calculate_drawdown_pct_series

        # Given
        equity = pd.Series([0.0, 10.0, 5.0])

        # When / Then
        with pytest.raises(RuntimeError, match="peak"):
            calculate_drawdown_pct_series(equity)


class TestCalculateCalmar:
    """calculate_calmar 단위 테스트

    정책: Calmar = CAGR / |MDD|, MDD=0 안전 처리
    - |MDD| >= EPSILON: cagr / abs(mdd)
    - |MDD| < EPSILON, CAGR > 0: CALMAR_MDD_ZERO_SUBSTITUTE + cagr
    - |MDD| < EPSILON, CAGR <= 0: 0.0
    """

    def test_normal(self):
        """
        정상 케이스: cagr / abs(mdd)

        Given: cagr=10.0, mdd=-5.0
        When: calculate_calmar 호출
        Then: 10.0 / 5.0 = 2.0
        """
        # Given / When
        result = calculate_calmar(cagr=10.0, mdd=-5.0)

        # Then
        assert result == pytest.approx(2.0, abs=EPSILON)

    def test_mdd_zero_cagr_positive(self):
        """
        MDD=0, CAGR>0: CALMAR_MDD_ZERO_SUBSTITUTE + cagr 반환

        Given: cagr=5.0, mdd=0.0
        When: calculate_calmar 호출
        Then: 1e10 + 5.0 반환 (MDD=0인 전략들끼리 CAGR로 차별화)
        """
        from qbt.backtest.constants import CALMAR_MDD_ZERO_SUBSTITUTE

        # Given / When
        result = calculate_calmar(cagr=5.0, mdd=0.0)

        # Then
        assert result == pytest.approx(CALMAR_MDD_ZERO_SUBSTITUTE + 5.0, abs=EPSILON)

    def test_mdd_zero_cagr_zero(self):
        """
        MDD=0, CAGR=0: 0.0 반환

        Given: cagr=0.0, mdd=0.0
        When: calculate_calmar 호출
        Then: 0.0
        """
        # Given / When
        result = calculate_calmar(cagr=0.0, mdd=0.0)

        # Then
        assert result == pytest.approx(0.0, abs=EPSILON)

    def test_mdd_zero_cagr_negative(self):
        """
        MDD=0, CAGR<0: 0.0 반환

        Given: cagr=-3.0, mdd=0.0
        When: calculate_calmar 호출
        Then: 0.0
        """
        # Given / When
        result = calculate_calmar(cagr=-3.0, mdd=0.0)

        # Then
        assert result == pytest.approx(0.0, abs=EPSILON)


class TestCalculateRegimeSummaries:
    """시장 구간별 성과 요약 계산 테스트

    calculate_regime_summaries()가 equity_df와 trades_df를 시장 구간별로
    분할하여 올바른 성과 지표를 계산하는지 검증한다.
    """

    def test_basic_two_regimes(self):
        """
        2개 구간(상승+하락)에 걸치는 equity+trades의 구간별 지표 검증

        Given:
          - 2개 시장 구간: bull(2021-01-01~2021-06-30), bear(2021-07-01~2021-12-31)
          - equity curve가 상승→하락 패턴
          - 각 구간에 1개씩 거래 존재
        When: calculate_regime_summaries 호출
        Then:
          - 2개 구간 결과 반환
          - 각 구간의 regime_type, name, 거래수 정확
          - CAGR, MDD 등 지표가 양/음 부호 올바름
        """
        # Given
        # 상승 구간: equity 10000 → 15000
        # 하락 구간: equity 15000 → 12000
        dates_bull = [date(2021, 1, 4), date(2021, 3, 1), date(2021, 6, 30)]
        dates_bear = [date(2021, 7, 1), date(2021, 9, 1), date(2021, 12, 31)]

        equity_df = pd.DataFrame(
            {
                COL_DATE: dates_bull + dates_bear,
                "equity": [10000.0, 12000.0, 15000.0, 15000.0, 13000.0, 12000.0],
            }
        )

        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 2, 1), date(2021, 8, 1)],
                "exit_date": [date(2021, 5, 1), date(2021, 11, 1)],
                "pnl": [3000.0, -1500.0],
                "holding_days": [89, 92],
            }
        )

        regimes: list[MarketRegimeDict] = [
            {"start": "2021-01-01", "end": "2021-06-30", "regime_type": "bull", "name": "상승기"},
            {"start": "2021-07-01", "end": "2021-12-31", "regime_type": "bear", "name": "하락기"},
        ]

        # When
        results = calculate_regime_summaries(equity_df, trades_df, regimes)

        # Then
        assert len(results) == 2, "2개 구간 결과가 반환되어야 합니다"

        bull_result = results[0]
        assert bull_result["name"] == "상승기"
        assert bull_result["regime_type"] == "bull"
        assert bull_result["total_trades"] == 1
        assert bull_result["total_return_pct"] > 0, "상승 구간 수익률은 양수"
        assert bull_result["cagr"] > 0, "상승 구간 CAGR은 양수"
        assert bull_result["trading_days"] == 3

        bear_result = results[1]
        assert bear_result["name"] == "하락기"
        assert bear_result["regime_type"] == "bear"
        assert bear_result["total_trades"] == 1
        assert bear_result["total_return_pct"] < 0, "하락 구간 수익률은 음수"
        assert bear_result["mdd"] < 0, "하락 구간 MDD는 음수"

    def test_regime_no_overlap(self):
        """
        데이터 범위 밖 구간은 결과 리스트에서 제외된다.

        Given:
          - equity 데이터: 2021-01-01 ~ 2021-12-31
          - 구간: 2025-01-01 ~ 2025-12-31 (데이터 범위 밖)
        When: calculate_regime_summaries 호출
        Then: 빈 리스트 반환
        """
        # Given
        equity_df = pd.DataFrame(
            {
                COL_DATE: [date(2021, 1, 4), date(2021, 6, 30), date(2021, 12, 31)],
                "equity": [10000.0, 12000.0, 15000.0],
            }
        )

        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 3, 1)],
                "exit_date": [date(2021, 5, 1)],
                "pnl": [2000.0],
                "holding_days": [61],
            }
        )

        regimes: list[MarketRegimeDict] = [
            {"start": "2025-01-01", "end": "2025-12-31", "regime_type": "bull", "name": "미래 구간"},
        ]

        # When
        results = calculate_regime_summaries(equity_df, trades_df, regimes)

        # Then
        assert len(results) == 0, "데이터 범위 밖 구간은 결과에서 제외"

    def test_no_trades_regime(self):
        """
        거래 없는 구간 (Buy & Hold 등) 테스트

        Given:
          - equity 데이터만 존재, 거래 없음
        When: calculate_regime_summaries 호출
        Then: total_trades=0, avg_holding_days=0.0, profit_factor=0.0
        """
        # Given
        equity_df = pd.DataFrame(
            {
                COL_DATE: [date(2021, 1, 4), date(2021, 6, 30), date(2021, 12, 31)],
                "equity": [10000.0, 12000.0, 15000.0],
            }
        )

        trades_df = pd.DataFrame(columns=["entry_date", "exit_date", "pnl", "holding_days"])

        regimes: list[MarketRegimeDict] = [
            {"start": "2021-01-01", "end": "2021-12-31", "regime_type": "bull", "name": "전체 상승"},
        ]

        # When
        results = calculate_regime_summaries(equity_df, trades_df, regimes)

        # Then
        assert len(results) == 1
        result = results[0]
        assert result["total_trades"] == 0
        assert result["avg_holding_days"] == pytest.approx(0.0, abs=EPSILON)
        assert result["profit_factor"] == pytest.approx(0.0, abs=EPSILON)

    def test_profit_factor_calculation(self):
        """
        수익/손실 거래 혼합 시 profit_factor 계산 검증

        정책: profit_factor = 총수익 / |총손실|

        Given:
          - 거래 3건: +5000, -2000, +3000 (총수익 8000, 총손실 2000)
        When: calculate_regime_summaries 호출
        Then: profit_factor = 8000 / 2000 = 4.0
        """
        # Given
        equity_df = pd.DataFrame(
            {
                COL_DATE: [date(2021, 1, 4), date(2021, 6, 30), date(2021, 12, 31)],
                "equity": [10000.0, 15000.0, 16000.0],
            }
        )

        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 2, 1), date(2021, 4, 1), date(2021, 8, 1)],
                "exit_date": [date(2021, 3, 1), date(2021, 5, 1), date(2021, 10, 1)],
                "pnl": [5000.0, -2000.0, 3000.0],
                "holding_days": [28, 30, 61],
            }
        )

        regimes: list[MarketRegimeDict] = [
            {"start": "2021-01-01", "end": "2021-12-31", "regime_type": "bull", "name": "전체"},
        ]

        # When
        results = calculate_regime_summaries(equity_df, trades_df, regimes)

        # Then
        assert len(results) == 1
        result = results[0]
        assert result["profit_factor"] == pytest.approx(4.0, abs=0.01), "profit_factor = 8000 / 2000 = 4.0"
        assert result["avg_holding_days"] == pytest.approx((28 + 30 + 61) / 3, abs=0.1), "평균 보유기간 = (28+30+61)/3"

    def test_holding_days_auto_computed(self):
        """
        trades_df에 holding_days 컬럼이 없을 때 entry_date/exit_date로 자동 계산

        정책: holding_days 컬럼 미존재 시 entry_date~exit_date 일수 차이로 폴백

        Given:
          - trades_df에 entry_date, exit_date, pnl만 있고 holding_days 없음
          - 거래 2건: (2021-02-01 ~ 2021-05-01 = 89일), (2021-08-01 ~ 2021-11-01 = 92일)
        When: calculate_regime_summaries 호출
        Then: avg_holding_days == (89 + 92) / 2 = 90.5
        """
        # Given
        equity_df = pd.DataFrame(
            {
                COL_DATE: [date(2021, 1, 4), date(2021, 6, 30), date(2021, 12, 31)],
                "equity": [10000.0, 13000.0, 15000.0],
            }
        )

        # holding_days 컬럼 없이 entry_date, exit_date, pnl만 존재
        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 2, 1), date(2021, 8, 1)],
                "exit_date": [date(2021, 5, 1), date(2021, 11, 1)],
                "pnl": [3000.0, 2000.0],
            }
        )

        regimes: list[MarketRegimeDict] = [
            {"start": "2021-01-01", "end": "2021-12-31", "regime_type": "bull", "name": "전체"},
        ]

        # When
        results = calculate_regime_summaries(equity_df, trades_df, regimes)

        # Then
        assert len(results) == 1
        result = results[0]
        # (2021-05-01 - 2021-02-01).days = 89, (2021-11-01 - 2021-08-01).days = 92
        # avg_holding_days = (89 + 92) / 2 = 90.5
        assert result["avg_holding_days"] == pytest.approx(
            90.5, abs=0.1
        ), "holding_days 컬럼 없을 때 entry_date/exit_date로 자동 계산: (89+92)/2 = 90.5"

    def test_profit_factor_no_loss(self):
        """
        손실 거래 없을 때 profit_factor = 0.0 반환 (무한대 대신)

        정책: 분모(총손실)가 0이면 무한대 대신 0.0 반환 (N/A 의미)

        Given:
          - 거래 2건 모두 수익 (+3000, +2000)
        When: calculate_regime_summaries 호출
        Then: profit_factor = 0.0
        """
        # Given
        equity_df = pd.DataFrame(
            {
                COL_DATE: [date(2021, 1, 4), date(2021, 6, 30), date(2021, 12, 31)],
                "equity": [10000.0, 13000.0, 15000.0],
            }
        )

        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2021, 2, 1), date(2021, 8, 1)],
                "exit_date": [date(2021, 5, 1), date(2021, 11, 1)],
                "pnl": [3000.0, 2000.0],
                "holding_days": [89, 92],
            }
        )

        regimes: list[MarketRegimeDict] = [
            {"start": "2021-01-01", "end": "2021-12-31", "regime_type": "bull", "name": "전체"},
        ]

        # When
        results = calculate_regime_summaries(equity_df, trades_df, regimes)

        # Then
        assert len(results) == 1
        result = results[0]
        assert result["profit_factor"] == pytest.approx(0.0, abs=EPSILON), "손실 거래 없으면 profit_factor = 0.0"
