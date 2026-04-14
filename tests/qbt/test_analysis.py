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
    calculate_summary,
    calculate_yearly_returns,
)
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


class TestCalculateYearlyReturns:
    """calculate_yearly_returns 단위 테스트

    정책: 같은 연도의 월별 수익률(%)을 복리 누적하여 연간 수익률(%)을 산출한다.
    공식: yearly_pct = (prod(1 + monthly_pct/100) - 1) * 100
    """

    def test_full_year_uniform_one_percent(self):
        """
        목적: 12개월 모두 1%인 경우 연간 복리 수익률 검증

        정책: (1.01)^12 - 1 ≈ 0.12683 = 12.6825...%

        Given: 2023년 12개월, 모든 월 return_pct=1.0
        When: calculate_yearly_returns 호출
        Then: 연간 수익률 약 12.68% (반올림 2자리 = 12.68)
        """
        # Given
        monthly_returns: list[dict[str, object]] = [{"year": 2023, "month": m, "return_pct": 1.0} for m in range(1, 13)]

        # When
        result = calculate_yearly_returns(monthly_returns)

        # Then
        assert len(result) == 1, "1개 연도만 있어야 합니다"
        assert result[0]["year"] == 2023
        # (1.01)^12 = 1.12682503... → 12.6825%
        expected_pct = ((1.01**12) - 1) * 100
        assert result[0]["return_pct"] == pytest.approx(round(expected_pct, 2), abs=EPSILON)

    def test_partial_year(self):
        """
        목적: 한 해의 일부 월만 있는 경우에도 정상 처리되는지 검증

        정책: 존재하는 월만 누적 곱한다.

        Given: 2023년 1~3월만 (1%, 2%, -1%)
        When: calculate_yearly_returns 호출
        Then: (1.01 * 1.02 * 0.99 - 1) * 100 = 1.9898%
        """
        # Given
        monthly_returns: list[dict[str, object]] = [
            {"year": 2023, "month": 1, "return_pct": 1.0},
            {"year": 2023, "month": 2, "return_pct": 2.0},
            {"year": 2023, "month": 3, "return_pct": -1.0},
        ]

        # When
        result = calculate_yearly_returns(monthly_returns)

        # Then
        assert len(result) == 1
        expected_pct = (1.01 * 1.02 * 0.99 - 1) * 100  # ≈ 1.9898
        assert result[0]["return_pct"] == pytest.approx(round(expected_pct, 2), abs=EPSILON)

    def test_multi_year_sorted_ascending(self):
        """
        목적: 여러 연도가 섞여 있을 때 연도 오름차순으로 정렬되어 반환되는지 검증

        Given: 2024년 + 2022년 + 2023년 (입력 순서 무작위)
        When: calculate_yearly_returns 호출
        Then: result는 [2022, 2023, 2024] 순서
        """
        # Given (입력 순서를 일부러 섞는다)
        monthly_returns: list[dict[str, object]] = [
            {"year": 2024, "month": 1, "return_pct": 5.0},
            {"year": 2022, "month": 12, "return_pct": -3.0},
            {"year": 2023, "month": 6, "return_pct": 2.0},
        ]

        # When
        result = calculate_yearly_returns(monthly_returns)

        # Then
        years = [int(str(r["year"])) for r in result]
        assert years == [2022, 2023, 2024], "연도 오름차순으로 정렬되어야 합니다"

    def test_empty_input(self):
        """
        목적: 빈 입력 시 빈 리스트 반환 검증

        정책: monthly_returns가 빈 리스트면 yearly_returns도 빈 리스트.

        Given: 빈 리스트
        When: calculate_yearly_returns 호출
        Then: 빈 리스트 반환
        """
        # Given / When
        result = calculate_yearly_returns([])

        # Then
        assert result == []

    def test_mixed_positive_negative(self):
        """
        목적: 양수 + 음수 수익률이 섞여 있을 때 복리 누적이 정확한지 검증

        Given: 2023년 1월 +10%, 2월 -10%
        When: calculate_yearly_returns 호출
        Then: 1.10 * 0.90 = 0.99 → -1%
        """
        # Given
        monthly_returns: list[dict[str, object]] = [
            {"year": 2023, "month": 1, "return_pct": 10.0},
            {"year": 2023, "month": 2, "return_pct": -10.0},
        ]

        # When
        result = calculate_yearly_returns(monthly_returns)

        # Then
        assert len(result) == 1
        # 1.10 * 0.90 = 0.99 → -1%
        assert result[0]["return_pct"] == pytest.approx(-1.0, abs=EPSILON)

    def test_consistency_with_calculate_monthly_returns(self):
        """
        목적: calculate_monthly_returns 결과를 입력으로 받아 연간 수익률이
              equity 직접 비율과 거의 일치하는지 검증 (왕복 일관성)

        정책: monthly compound ≈ 연초 대비 연말 비율

        Given:
          - 12개월 equity 데이터 (월말마다 1% 상승)
        When:
          - calculate_monthly_returns → calculate_yearly_returns
        Then:
          - equity[12]/equity[0] - 1 비율과 거의 동일
        """
        from qbt.backtest.analysis import calculate_monthly_returns

        # Given: 2023년 12월말 ~ 2024년 12월말 (총 13개 월말 시점)
        # 매월 1% 복리 상승
        dates = [
            date(2023, 12, 31),
            date(2024, 1, 31),
            date(2024, 2, 29),
            date(2024, 3, 31),
            date(2024, 4, 30),
            date(2024, 5, 31),
            date(2024, 6, 30),
            date(2024, 7, 31),
            date(2024, 8, 31),
            date(2024, 9, 30),
            date(2024, 10, 31),
            date(2024, 11, 30),
            date(2024, 12, 31),
        ]
        equities = [10000.0 * (1.01**i) for i in range(13)]
        equity_df = pd.DataFrame({COL_DATE: dates, "equity": equities})

        # When
        monthly = calculate_monthly_returns(equity_df)
        yearly = calculate_yearly_returns(monthly)

        # Then: 2024년 한 해 12번 1% 복리 → ≈ 12.68%
        assert len(yearly) == 1
        assert int(str(yearly[0]["year"])) == 2024
        expected_pct = ((1.01**12) - 1) * 100
        # 반올림 2자리 적용으로 인한 미세한 누적 오차 허용 (0.05 이내)
        assert float(str(yearly[0]["return_pct"])) == pytest.approx(expected_pct, abs=0.05)


class TestAnalysisModuleInvariants:
    """analysis 모듈의 구조적 불변조건 검증.

    개별 함수 동작이 아닌 모듈 의존 방향 / 엣지 케이스 정책을 고정한다.
    """

    def test_csv_export_does_not_depend_on_analysis(self):
        """
        csv_export 모듈은 analysis를 import해서는 안 된다 (단방향 의존).

        정책: 저장 계층(csv_export) → 계산 계층(analysis) 방향이 자연스럽다.
              역방향 의존이 생기면 순환 가능성이 발생한다.

        Given: qbt.backtest.csv_export 모듈을 fresh import
        When:  csv_export 모듈의 import 그래프를 점검
        Then:  analysis 모듈을 직접 import하지 않음
        """
        import qbt.backtest.csv_export as csv_export

        # csv_export 모듈의 namespace에 analysis 관련 심볼이 없는지 확인
        assert "analysis" not in csv_export.__dict__, "csv_export가 analysis 모듈을 import해서는 안 됨"
        # analysis의 핵심 함수 이름들이 csv_export 네임스페이스에 노출되어 있지 않은지 확인
        for forbidden in ("calculate_summary", "add_single_moving_average"):
            assert forbidden not in csv_export.__dict__, f"csv_export가 analysis의 {forbidden}를 import해서는 안 됨 (단방향 의존 위반)"

    def test_calculate_summary_zero_years_raises(self):
        """
        equity_df의 시작일과 종료일이 동일한 경우 RuntimeError 발생

        정책: years == 0은 정상 백테스트에서 발생할 수 없는 조건(MIN_VALID_ROWS=2 보장).
              과거에는 cagr=0.0으로 무음 반환되었으나 fail-fast로 강화한다.

        Given:
          - equity_df의 모든 행이 같은 날짜
        When: calculate_summary 호출
        Then: RuntimeError("내부 불변조건 위반")
        """
        # Given
        same_date = date(2023, 6, 15)
        trades_df = pd.DataFrame(columns=["entry_date", "exit_date", "pnl"])
        equity_df = pd.DataFrame(
            {
                COL_DATE: [same_date, same_date],
                "equity": [10000.0, 11000.0],
            }
        )

        # When / Then
        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            calculate_summary(trades_df, equity_df, initial_capital=10000.0)
