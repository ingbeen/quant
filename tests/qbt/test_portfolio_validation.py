"""포트폴리오 정합성 검증 함수 단위 테스트

portfolio_validation.py의 개별 검증 규칙을 독립적으로 테스트한다.
소규모 인라인 DataFrame으로 정상/위반 케이스를 검증한다.
"""

from datetime import date

import pandas as pd

from qbt.backtest.portfolio_validation import (
    _check_cash_non_negative,
    _check_equity_equation,
    _check_exit_all_shares_zero,
    _check_rebalance_weight_consistency,
    _check_signal_execution_lag,
)


class TestCheckSignalExecutionLag:
    """규칙 1: 시그널-체결 1일 lag 검증 함수 테스트."""

    def test_matching_pending_and_executed(self):
        """
        목적: pending intent가 다음날 정확히 체결되면 위반 없음.

        Given: i일 pending=ENTER_TO_TARGET, i+1일 executed=ENTER_TO_TARGET
        When: _check_signal_execution_lag() 호출
        Then: 빈 리스트 반환
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)],
                "qqq_close": [100.0, 101.0, 102.0],
                "qqq_pending_intent": ["ENTER_TO_TARGET", "", ""],
                "qqq_executed_intent": ["", "ENTER_TO_TARGET", ""],
            }
        )

        # When
        violations = _check_signal_execution_lag(df, ["qqq"])

        # Then
        assert violations == []

    def test_mismatch_pending_and_executed(self):
        """
        목적: pending과 다음날 executed가 불일치하면 위반 감지.

        Given: i일 pending=ENTER_TO_TARGET, i+1일 executed="" (미체결)
        When: _check_signal_execution_lag() 호출
        Then: 위반 1건
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2), date(2024, 1, 3)],
                "qqq_close": [100.0, 101.0],
                "qqq_pending_intent": ["ENTER_TO_TARGET", ""],
                "qqq_executed_intent": ["", ""],
            }
        )

        # When
        violations = _check_signal_execution_lag(df, ["qqq"])

        # Then
        assert len(violations) == 1
        assert "규칙1" in violations[0]

    def test_no_pending_no_violation(self):
        """
        목적: pending이 없으면 검증 대상 없음.

        Given: 모든 날 pending=""
        When: _check_signal_execution_lag() 호출
        Then: 빈 리스트
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2), date(2024, 1, 3)],
                "qqq_close": [100.0, 101.0],
                "qqq_pending_intent": ["", ""],
                "qqq_executed_intent": ["", ""],
            }
        )

        # When
        violations = _check_signal_execution_lag(df, ["qqq"])

        # Then
        assert violations == []


class TestCheckRebalanceWeightConsistency:
    """규칙 2: 리밸런싱 후 비중 정합성 검증 함수 테스트."""

    def test_weight_within_threshold(self):
        """
        목적: 리밸런싱 후 비중 편차가 임계값 이내이면 통과.

        Given: target=0.50, actual=0.48 (편차 4%)
        When: _check_rebalance_weight_consistency() 호출
        Then: 빈 리스트
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2)],
                "rebalanced": [True],
                "qqq_close": [100.0],
                "qqq_shares": [480],
                "qqq_weight": [0.48],
            }
        )

        # When
        violations = _check_rebalance_weight_consistency(df, ["qqq"], {"qqq": 0.50})

        # Then
        assert violations == []

    def test_weight_exceeds_threshold(self):
        """
        목적: 리밸런싱 후 비중 편차가 임계값 초과하면 위반 감지.

        Given: target=0.50, actual=0.30 (편차 40%)
        When: _check_rebalance_weight_consistency() 호출
        Then: 위반 1건
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2)],
                "rebalanced": [True],
                "qqq_close": [100.0],
                "qqq_shares": [300],
                "qqq_weight": [0.30],
            }
        )

        # When
        violations = _check_rebalance_weight_consistency(df, ["qqq"], {"qqq": 0.50})

        # Then
        assert len(violations) == 1
        assert "규칙2" in violations[0]


class TestCheckExitAllSharesZero:
    """규칙 3: EXIT_ALL 후 주수 0 검증 함수 테스트."""

    def test_shares_zero_after_exit_all(self):
        """
        목적: EXIT_ALL 체결 후 shares=0이면 통과.

        Given: executed_intent=EXIT_ALL, shares=0
        When: _check_exit_all_shares_zero() 호출
        Then: 빈 리스트
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2)],
                "qqq_close": [100.0],
                "qqq_executed_intent": ["EXIT_ALL"],
                "qqq_shares": [0],
            }
        )

        # When
        violations = _check_exit_all_shares_zero(df, ["qqq"])

        # Then
        assert violations == []

    def test_shares_nonzero_after_exit_all(self):
        """
        목적: EXIT_ALL 체결 후 shares > 0이면 위반 감지.

        Given: executed_intent=EXIT_ALL, shares=100
        When: _check_exit_all_shares_zero() 호출
        Then: 위반 1건
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2)],
                "qqq_close": [100.0],
                "qqq_executed_intent": ["EXIT_ALL"],
                "qqq_shares": [100],
            }
        )

        # When
        violations = _check_exit_all_shares_zero(df, ["qqq"])

        # Then
        assert len(violations) == 1
        assert "규칙3" in violations[0]


class TestCheckCashNonNegative:
    """규칙 4: 현금 비음수 검증 함수 테스트."""

    def test_all_positive_cash(self):
        """
        목적: 현금이 항상 양수이면 통과.

        Given: cash = [1000, 2000]
        When: _check_cash_non_negative() 호출
        Then: 빈 리스트
        """
        # Given
        df = pd.DataFrame({"Date": [date(2024, 1, 2), date(2024, 1, 3)], "cash": [1000, 2000]})

        # When
        violations = _check_cash_non_negative(df)

        # Then
        assert violations == []

    def test_negative_cash_detected(self):
        """
        목적: 현금이 음수인 행이 있으면 위반 감지.

        Given: cash = [1000, -500]
        When: _check_cash_non_negative() 호출
        Then: 위반 1건
        """
        # Given
        df = pd.DataFrame({"Date": [date(2024, 1, 2), date(2024, 1, 3)], "cash": [1000, -500]})

        # When
        violations = _check_cash_non_negative(df)

        # Then
        assert len(violations) == 1
        assert "규칙4" in violations[0]


class TestCheckEquityEquation:
    """규칙 5: 에쿼티 등식 검증 함수 테스트."""

    def test_equity_matches_equation(self):
        """
        목적: equity = cash + sum(values)이면 통과.

        Given: cash=3000, qqq_value=5000, spy_value=2000, equity=10000
        When: _check_equity_equation() 호출
        Then: 빈 리스트
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2)],
                "cash": [3000],
                "qqq_value": [5000],
                "spy_value": [2000],
                "equity": [10000],
            }
        )

        # When
        violations = _check_equity_equation(df)

        # Then
        assert violations == []

    def test_equity_mismatch_detected(self):
        """
        목적: equity != cash + sum(values)이면 위반 감지.

        Given: cash=3000, qqq_value=5000, equity=9000 (실제: 8000)
        When: _check_equity_equation() 호출
        Then: 위반 1건
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2)],
                "cash": [3000],
                "qqq_value": [5000],
                "equity": [9000],  # 실제 합계는 8000
            }
        )

        # When
        violations = _check_equity_equation(df)

        # Then
        assert len(violations) == 1
        assert "규칙5" in violations[0]
