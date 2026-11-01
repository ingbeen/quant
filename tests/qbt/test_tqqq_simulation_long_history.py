"""
tqqq/simulation 의 simulate_long_history 테스트

이 파일은 무엇을 검증하나요?
1. 1999년 이전 달의 비용: 상장 전 운용보수와 그 달 금리 · 스프레드
2. 가산금리 상한: 넘는 달만 상한으로 깎인다
3. 금리가 없는 구간은 멈춘다
4. 1999년 이후는 기존 합성과 같은 값이다

왜 중요한가요?
그때는 없던 상품이라 실물과 대조할 수 없다. 비용 계산이 틀려도 에러가 나지 않고 닷컴 경험 투자자의 수익률만 달라진다.
"""

import math
from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, TRADING_DAYS_PER_YEAR
from qbt.tqqq.data_loader import build_extended_expense_dict, create_ffr_dict
from qbt.tqqq.simulation import build_monthly_spread_map, simulate, simulate_long_history

_SOFTPLUS_A = -6.1
_SOFTPLUS_B = 0.37
_PRE_LISTING_EXPENSE = 0.0095
_INITIAL_PRICE = 100.0


def _flat_underlying(days: list[date]) -> pd.DataFrame:
    """가격이 그대로인 기초 자산 — 가격 변화가 곧 그날 비용이다."""
    return pd.DataFrame(
        {
            COL_DATE: days,
            COL_OPEN: [50.0] * len(days),
            COL_HIGH: [50.0] * len(days),
            COL_LOW: [50.0] * len(days),
            COL_CLOSE: [50.0] * len(days),
        }
    )


def _ffr(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame({"DATE": [month for month, _ in rows], "VALUE": [value for _, value in rows]})


def _spread(ffr_ratio: float) -> float:
    return math.log1p(math.exp(_SOFTPLUS_A + _SOFTPLUS_B * ffr_ratio * 100.0))


def _expected_second_close(leverage: float, ffr_ratio: float, spread: float, expense: float) -> float:
    annual_cost = (ffr_ratio + spread) * (leverage - 1) + expense
    return _INITIAL_PRICE * (1 - annual_cost / TRADING_DAYS_PER_YEAR)


EXPENSE_DF = pd.DataFrame({"DATE": ["2010-02"], "VALUE": [0.02]})


class TestSimulateLongHistory:
    def test_before_1999_uses_pre_listing_expense(self) -> None:
        """
        목적: 1999년 이전 달은 상장 전 운용보수와 그 달 금리 · 스프레드를 쓴다

        Given: 1990-01 금리 8%, 가격 변화 없음, 3배
        When: simulate_long_history
        Then: 둘째 날 종가 = 100 × (1 - ((8% + 스프레드) × 2 + 0.95%) / 252)
        """
        # Given
        underlying = _flat_underlying([date(1990, 1, 2), date(1990, 1, 3)])

        # When
        actual = simulate_long_history(underlying, 3.0, _ffr([("1990-01", 0.08)]), EXPENSE_DF)

        # Then
        expected = _expected_second_close(3.0, 0.08, _spread(0.08), _PRE_LISTING_EXPENSE)
        assert float(actual[COL_CLOSE].iloc[1]) == pytest.approx(expected, abs=1e-6)

    def test_expense_file_wins_after_its_first_month(self) -> None:
        """
        목적: 운용보수 파일이 있는 달은 그 값을 쓴다 — 앞쪽을 채우면서 실제 값을 덮으면 안 된다

        Given: 운용보수 파일 2010-02 ~ 값 2%, 그 달 금리 1%
        When: simulate_long_history
        Then: 비용에 2% 가 들어간다
        """
        # Given
        underlying = _flat_underlying([date(2010, 2, 2), date(2010, 2, 3)])

        # When
        actual = simulate_long_history(underlying, 2.0, _ffr([("2010-02", 0.01)]), EXPENSE_DF)

        # Then
        expected = _expected_second_close(2.0, 0.01, _spread(0.01), 0.02)
        assert float(actual[COL_CLOSE].iloc[1]) == pytest.approx(expected, abs=1e-6)

    def test_spread_cap_applies_only_above_cap(self) -> None:
        """
        목적: 상한은 넘는 달만 깎는다

        Given: 금리 9.85% 달(스프레드 약 8.23%)과 3% 달(약 0.68%), 상한 1.6%
        When: spread_cap 을 주고 실행
        Then: 앞 달은 스프레드 1.6%, 뒤 달은 모델 값 그대로
        """
        # Given
        high = _flat_underlying([date(1989, 3, 1), date(1989, 3, 2)])
        low = _flat_underlying([date(1993, 3, 1), date(1993, 3, 2)])
        ffr = _ffr([("1989-03", 0.0985), ("1993-03", 0.03)])

        # When
        high_actual = simulate_long_history(high, 3.0, ffr, EXPENSE_DF, spread_cap=0.016)
        low_actual = simulate_long_history(low, 3.0, ffr, EXPENSE_DF, spread_cap=0.016)

        # Then
        high_expected = _expected_second_close(3.0, 0.0985, 0.016, _PRE_LISTING_EXPENSE)
        low_expected = _expected_second_close(3.0, 0.03, _spread(0.03), _PRE_LISTING_EXPENSE)
        assert float(high_actual[COL_CLOSE].iloc[1]) == pytest.approx(high_expected, abs=1e-6)
        assert float(low_actual[COL_CLOSE].iloc[1]) == pytest.approx(low_expected, abs=1e-6)

    @pytest.mark.parametrize("spread_cap", [0.0, -0.01])
    def test_non_positive_cap_raises(self, spread_cap: float) -> None:
        """
        목적: 0 이하 상한은 스프레드를 없애거나 음수로 만든다 — 시작 전에 멈춘다

        Given: 0 · 음수 상한
        When: simulate_long_history
        Then: ValueError
        """
        # Given
        underlying = _flat_underlying([date(1990, 1, 2), date(1990, 1, 3)])

        # When / Then
        with pytest.raises(ValueError, match="spread_cap"):
            simulate_long_history(underlying, 3.0, _ffr([("1990-01", 0.08)]), EXPENSE_DF, spread_cap=spread_cap)

    def test_gap_in_rates_raises(self) -> None:
        """
        목적: 금리가 없는 달이 허용 개월 수를 넘으면 멈춘다 — 옛 금리로 조용히 채우지 않는다

        Given: 1990-01 금리만 있고 시세는 1990-06
        When: simulate_long_history
        Then: ValueError
        """
        # Given
        underlying = _flat_underlying([date(1990, 6, 1), date(1990, 6, 4)])

        # When / Then
        with pytest.raises(ValueError, match="FFR"):
            simulate_long_history(underlying, 3.0, _ffr([("1990-01", 0.08)]), EXPENSE_DF)

    def test_same_as_simulate_without_cap_after_1999(self) -> None:
        """
        목적: 상한 없는 판의 1999년 이후는 기존 합성과 같은 계산이다 — 이 함수가 새 모델을 만들지 않는다

        Given: 2023 년 시세, 금리, 운용보수
        When: simulate_long_history 와 기존 조립으로 부른 simulate
        Then: 모든 가격이 같다
        """
        # Given
        days = [date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)]
        underlying = pd.DataFrame(
            {
                COL_DATE: days,
                COL_OPEN: [100.0, 100.5, 99.5],
                COL_HIGH: [101.0, 102.0, 100.0],
                COL_LOW: [99.0, 100.0, 98.0],
                COL_CLOSE: [100.0, 101.0, 99.0],
            }
        )
        ffr = _ffr([("2023-01", 0.045)])
        expense = pd.DataFrame({"DATE": ["2023-01"], "VALUE": [0.0088]})

        # When
        actual = simulate_long_history(underlying, 3.0, ffr, expense)
        expected = simulate(
            underlying,
            3.0,
            _INITIAL_PRICE,
            ffr_dict=create_ffr_dict(ffr),
            expense_dict=build_extended_expense_dict(expense),
            funding_spread=build_monthly_spread_map(ffr, _SOFTPLUS_A, _SOFTPLUS_B),
        )

        # Then
        pd.testing.assert_frame_equal(actual, expected)

    def test_input_is_not_modified(self) -> None:
        """
        목적: 원본 표를 바꾸지 않는다

        Given: 금리 · 운용보수 · 시세 표
        When: simulate_long_history
        Then: 호출 전과 같다
        """
        # Given
        underlying = _flat_underlying([date(1990, 1, 2), date(1990, 1, 3)])
        ffr = _ffr([("1990-01", 0.08)])
        before = (underlying.copy(), ffr.copy(), EXPENSE_DF.copy())

        # When
        simulate_long_history(underlying, 3.0, ffr, EXPENSE_DF)

        # Then
        pd.testing.assert_frame_equal(underlying, before[0])
        pd.testing.assert_frame_equal(ffr, before[1])
        pd.testing.assert_frame_equal(EXPENSE_DF, before[2])
