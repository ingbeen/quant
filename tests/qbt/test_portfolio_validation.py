"""포트폴리오 정합성 검증 함수 단위 테스트

portfolio_validation.py의 개별 검증 규칙을 독립적으로 테스트한다.
소규모 인라인 DataFrame으로 정상/위반 케이스를 검증한다.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.constants import REBALANCE_REASON_METHODS, REBALANCE_REASON_MONTHLY
from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig, PortfolioResult
from qbt.backtest.portfolio_validation import (
    _check_cash_non_negative,
    _check_equity_equation,
    _check_exit_all_shares_zero,
    _check_method_rebalance_weight_consistency,
    _check_signal_execution_lag,
    validate_portfolio_result,
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
        assert violations == ["[규칙1] qqq: 2024-01-02 pending=ENTER_TO_TARGET -> 다음날 executed="]

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

    def test_last_day_pending_is_not_checked(self):
        """
        목적: 마지막 날의 pending 은 체결할 다음 거래일이 없어 검사하지 않는다.

        Given: 마지막 날(2024-01-03)에만 pending=EXIT_ALL
        When: _check_signal_execution_lag() 호출
        Then: 빈 리스트
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2), date(2024, 1, 3)],
                "qqq_close": [100.0, 101.0],
                "qqq_pending_intent": ["", "EXIT_ALL"],
                "qqq_executed_intent": ["", ""],
            }
        )

        # When
        violations = _check_signal_execution_lag(df, ["qqq"])

        # Then
        assert violations == []

    def test_different_intent_executed_next_day(self):
        """
        목적: 다음 날 체결이 있어도 pending 과 다른 종류면 위반이다.

        Given: 2024-01-02 pending=ENTER_TO_TARGET, 다음 날 executed=EXIT_ALL
        When: _check_signal_execution_lag() 호출
        Then: 위반 1건 (두 값이 함께 보고된다)
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2), date(2024, 1, 3)],
                "qqq_close": [100.0, 101.0],
                "qqq_pending_intent": ["ENTER_TO_TARGET", ""],
                "qqq_executed_intent": ["", "EXIT_ALL"],
            }
        )

        # When
        violations = _check_signal_execution_lag(df, ["qqq"])

        # Then
        assert violations == ["[규칙1] qqq: 2024-01-02 pending=ENTER_TO_TARGET -> 다음날 executed=EXIT_ALL"]

    def test_nan_pending_is_reported(self):
        """
        목적: pending 칸이 NaN 이면 건너뛰지 않고 위반으로 낸다 — 엔진은 그 칸에 빈 문자열이나 의도 이름만 쓴다.

        Given: 2024-01-02 pending=NaN
        When: _check_signal_execution_lag() 호출
        Then: 위반 1건
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2), date(2024, 1, 3)],
                "qqq_close": [100.0, 101.0],
                "qqq_pending_intent": [float("nan"), ""],
                "qqq_executed_intent": ["", ""],
            }
        )

        # When
        violations = _check_signal_execution_lag(df, ["qqq"])

        # Then
        assert len(violations) == 1
        assert "pending=nan" in violations[0]

    def test_missing_intent_columns_raise(self):
        """
        목적: 자산의 의도 열이 없으면 그 자산을 조용히 건너뛰지 않고 멈춘다.

        Given: qqq 의 pending · executed 열이 없는 상태 로그
        When: _check_signal_execution_lag(df, ["qqq"]) 호출
        Then: KeyError
        """
        # Given
        df = pd.DataFrame({"Date": [date(2024, 1, 2), date(2024, 1, 3)], "qqq_close": [100.0, 101.0]})

        # When & Then
        with pytest.raises(KeyError, match="qqq_pending_intent"):
            _check_signal_execution_lag(df, ["qqq"])


def _rebalance_day(shares: int, executed_intent: str, rebalance_reason: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """규칙 2 입력 — 매매법 m(자본 100,000)이 2024-01-02 에 리밸런싱한 날, qqq(종가 100)를 shares 주 보유.

    qqq 의 매매법 자본 대비 비중 = shares × 100 / 100,000. 반환은 (상태 로그, 장부).
    """
    d = date(2024, 1, 2)
    state_log = pd.DataFrame(
        {"Date": [d], "qqq_close": [100.0], "qqq_shares": [shares], "qqq_executed_intent": [executed_intent]}
    )
    ledger = pd.DataFrame(
        {
            "Date": [d],
            "method_id": ["m"],
            "equity": [100_000.0],
            "rebalanced": [True],
            "rebalance_reason": [rebalance_reason],
        }
    )
    return state_log, ledger


class TestCheckMethodRebalanceWeightConsistency:
    """규칙 2: 리밸런싱 후 매매법 자본 대비 비중 정합성 검증 함수 테스트.

    REDUCE/INCREASE 를 처리한 자산을 보고, 장부 사유가 있는 날(월말 · 매매법 사이)은 주문 없이 남은 보유 자산도 본다.
    사유가 빈 날(배분 규칙의 조정만)의 매매하지 않은 자산과, 그날 새로 진입한 자산은 보지 않는다.
    """

    def test_weight_within_threshold(self):
        """
        목적: 리밸런싱 후 비중 편차가 임계값 이내이면 통과.

        Given: 월말 리밸런싱한 날, target=0.50, actual=0.48 (편차 4%)
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 빈 리스트
        """
        # Given
        state_log, ledger = _rebalance_day(480, "INCREASE_TO_TARGET", REBALANCE_REASON_MONTHLY)

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": 0.50})

        # Then
        assert violations == []

    def test_weight_exceeds_threshold(self):
        """
        목적: 리밸런싱 후 비중 편차가 임계값 초과하면 위반 감지.

        Given: 월말 리밸런싱한 날, target=0.50, actual=0.30 (편차 40%)
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 위반 1건
        """
        # Given
        state_log, ledger = _rebalance_day(300, "INCREASE_TO_TARGET", REBALANCE_REASON_MONTHLY)

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": 0.50})

        # Then
        assert len(violations) == 1
        assert "규칙2" in violations[0]

    def test_tolerance_boundary_19pct_passes(self):
        """
        목적: 허용 오차가 상대 편차 0.20 임을 고정한다 (경계 아래 통과).
              리밸런싱 정책의 임계값과 무관한 검사 기준이다.

        Given: 월말 리밸런싱한 날, target=0.50, actual=0.405 (상대 편차 19%)
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 빈 리스트
        """
        # Given
        state_log, ledger = _rebalance_day(405, "INCREASE_TO_TARGET", REBALANCE_REASON_MONTHLY)

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": 0.50})

        # Then
        assert violations == []

    def test_tolerance_boundary_21pct_fails(self):
        """
        목적: 허용 오차가 상대 편차 0.20 임을 고정한다 (경계 위 위반).
              허용 오차가 무한대로 바뀌어 검사가 늘 통과하는 회귀를 막는다.

        Given: 월말 리밸런싱한 날, target=0.50, actual=0.395 (상대 편차 21%)
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 위반 1건
        """
        # Given
        state_log, ledger = _rebalance_day(395, "INCREASE_TO_TARGET", REBALANCE_REASON_MONTHLY)

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": 0.50})

        # Then
        assert len(violations) == 1
        assert "규칙2" in violations[0]

    @pytest.mark.parametrize("reason", [REBALANCE_REASON_MONTHLY, REBALANCE_REASON_METHODS])
    def test_untraded_holding_checked_when_method_rebalanced(self, reason: str):
        """
        목적: 사유가 있는 리밸런싱은 보유 자산 전부를 목표로 맞추므로, 그날 매매하지 않은 보유 자산도 검사한다 —
              리밸런싱 주문에서 빠져 허용 범위를 벗어난 채 남은 자산을 잡는다.

        Given: 사유가 월말 · 매매법 사이인 리밸런싱한 날, qqq 매매 없음(executed=""), actual=0.30 (target 0.50)
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 위반 1건
        """
        # Given
        state_log, ledger = _rebalance_day(300, "", reason)

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": 0.50})

        # Then
        assert len(violations) == 1
        assert "규칙2" in violations[0]

    def test_untraded_holding_skipped_on_allocation_only_day(self):
        """
        목적: 배분 규칙의 조정만 있던 날(사유가 빈 날)은 바뀐 자산만 매매하므로 매매하지 않은 자산의 이탈은 보지 않는다.

        Given: 사유가 빈 리밸런싱한 날, qqq 매매 없음(executed=""), actual=0.30 (target 0.50)
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 빈 리스트
        """
        # Given
        state_log, ledger = _rebalance_day(300, "", "")

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": 0.50})

        # Then
        assert violations == []

    def test_traded_holding_checked_on_allocation_only_day(self):
        """
        목적: 배분 규칙의 조정만 있던 날에도 그날 목표로 맞춘(REDUCE/INCREASE) 자산은 검사한다.

        Given: 사유가 빈 리밸런싱한 날, qqq 를 REDUCE_TO_TARGET 으로 매매, actual=0.30 (target 0.50)
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 위반 1건
        """
        # Given
        state_log, ledger = _rebalance_day(300, "REDUCE_TO_TARGET", "")

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": 0.50})

        # Then
        assert len(violations) == 1
        assert "규칙2" in violations[0]

    @pytest.mark.parametrize("reason", [REBALANCE_REASON_MONTHLY, REBALANCE_REASON_METHODS])
    def test_entering_asset_skipped_when_method_rebalanced(self, reason: str):
        """
        목적: 사유가 있는 리밸런싱 날에도 그날 새로 진입한 자산은 보지 않는다 — 진입 수량은 정수 주와
              현금 부족 축소를 그대로 받아, 소액 계좌에서는 정상 체결도 허용 범위를 벗어난다.

        Given: 사유가 월말 · 매매법 사이인 리밸런싱한 날, qqq 를 ENTER_TO_TARGET 으로 진입, actual=0.30 (target 0.50)
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 빈 리스트
        """
        # Given
        state_log, ledger = _rebalance_day(300, "ENTER_TO_TARGET", reason)

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": 0.50})

        # Then
        assert violations == []

    def test_unheld_asset_skipped_when_method_rebalanced(self):
        """
        목적: 사유가 있는 리밸런싱 날에도 보유하지 않은 자산은 보지 않는다 — 매도 신호로 비워 둔 슬롯은
              목표가 있어도 0주가 정상이다.

        Given: 월말 리밸런싱한 날, qqq 0주 (target 0.50)
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 빈 리스트
        """
        # Given
        state_log, ledger = _rebalance_day(0, "", REBALANCE_REASON_MONTHLY)

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": 0.50})

        # Then
        assert violations == []

    def test_allocator_asset_target_read_from_state_log(self):
        """
        목적: 비중이 바뀌는 매매법의 자산은 고정 목표가 없어, 그날 체결이 맞추려던 목표를 상태 로그에서 읽어 견준다.

        Given: 고정 목표가 없는(None) qqq, 상태 로그의 그날 목표 0.50, REDUCE_TO_TARGET 으로 매매, actual=0.30
        When: _check_method_rebalance_weight_consistency() 호출
        Then: 목표 0.50 대비 위반 1건
        """
        # Given
        state_log, ledger = _rebalance_day(300, "REDUCE_TO_TARGET", "")
        state_log["qqq_target_weight"] = [0.50]

        # When
        violations = _check_method_rebalance_weight_consistency(state_log, ledger, {"qqq": "m"}, {"qqq": None})

        # Then
        assert len(violations) == 1
        assert "target=0.5000" in violations[0]


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

    def test_missing_executed_column_raises(self):
        """
        목적: 자산의 체결 의도 열이 없으면 그 자산을 조용히 건너뛰지 않고 멈춘다.

        Given: qqq 의 executed 열이 없는 상태 로그
        When: _check_exit_all_shares_zero(df, ["qqq"]) 호출
        Then: KeyError
        """
        # Given
        df = pd.DataFrame({"Date": [date(2024, 1, 2)], "qqq_close": [100.0], "qqq_shares": [100]})

        # When & Then
        with pytest.raises(KeyError, match="qqq_executed_intent"):
            _check_exit_all_shares_zero(df, ["qqq"])


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

    def test_empty_value_cols_raises_runtime_error(self):
        """
        목적: 자산 평가액 컬럼(_value 접미사)이 하나도 없으면
              내부 불변조건 위반으로 즉시 중단한다 (silent pass 금지).

        Given: cash/equity만 있고 *_value 컬럼이 전혀 없는 equity_df.
               정상 흐름에서는 portfolio_engine이 항상 자산별 _value 컬럼을
               생성하므로 발생 불가한 비정상 입력이다.
        When: _check_equity_equation() 호출
        Then: RuntimeError 발생. value_cols가 비면 sum=0.0으로 등식 검증이
              우회되어 가드가 무력화되므로 즉시 실패해야 한다.
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2)],
                "cash": [10000],
                "equity": [10000],
            }
        )

        # When & Then
        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            _check_equity_equation(df)


_DAYS = [date(2024, 1, 2), date(2024, 1, 3)]


def _minimal_state_log() -> pd.DataFrame:
    """_minimal_result 와 맞는 상태 로그 — 이틀 내내 qqq 3주 · tlt 2주(종가 100), 주문 · 체결 없음."""
    return pd.DataFrame(
        {
            "Date": _DAYS,
            "qqq_close": [100.0, 100.0],
            "qqq_shares": [3, 3],
            "qqq_pending_intent": ["", ""],
            "qqq_executed_intent": ["", ""],
            "tlt_close": [100.0, 100.0],
            "tlt_shares": [2, 2],
            "tlt_pending_intent": ["", ""],
            "tlt_executed_intent": ["", ""],
        }
    )


def _minimal_result(state_log: pd.DataFrame, rebalanced_last_day: bool = False) -> PortfolioResult:
    """검사기가 끝까지 도는 최소 결과 — 매매법 하나(줄임 표기), 자본 1,000, 이틀 내내 qqq 300 · tlt 200 · 현금 500.

    두 자산의 목표 비중은 0.5 씩이다. 상태 로그만 바꿔 넣는다 — 에쿼티 · 장부는 규칙 4 · 5 · 6 · 7 을 위반 없이 지난다.
    rebalanced_last_day 면 장부의 마지막 날(2024-01-03)이 월말 리밸런싱한 날이다.
    """
    dummy = Path("dummy")
    config = PortfolioConfig(
        experiment_name="t",
        display_name="T",
        total_capital=1_000.0,
        result_dir=dummy,
        asset_slots=(
            AssetSlotConfig("qqq", dummy, dummy, target_weight=0.5, strategy_id="buy_and_hold"),
            AssetSlotConfig("tlt", dummy, dummy, target_weight=0.5, strategy_id="buy_and_hold"),
        ),
    )
    equity = pd.DataFrame(
        {
            "Date": _DAYS,
            "equity": [1_000.0, 1_000.0],
            "cash": [500.0, 500.0],
            "qqq_value": [300.0, 300.0],
            "tlt_value": [200.0, 200.0],
        }
    )
    ledger = pd.DataFrame(
        {
            "Date": _DAYS,
            "method_id": ["t", "t"],
            "equity": [1_000.0, 1_000.0],
            "cash": [500.0, 500.0],
            "share": [1.0, 1.0],
            "target_share": [1.0, 1.0],
            "pnl": [0.0, 0.0],
            "cost": [0.0, 0.0],
            "transfers": [0.0, 0.0],
            "rebalanced": [False, rebalanced_last_day],
            "rebalance_reason": ["", REBALANCE_REASON_MONTHLY if rebalanced_last_day else ""],
        }
    )
    return PortfolioResult("T", equity, pd.DataFrame(), {}, config, state_log_df=state_log, ledger_df=ledger)


class TestValidatePortfolioResult:
    """검사기 전체: 상태 로그 기반 규칙(1 · 2 · 3)이 설정의 자산 전부에 실제로 돌고, 입력이 모자라면 조용히 건너뛰지 않는다.

    위반은 설정의 둘째 자산(tlt)에 심는다 — 첫 자산만 보는 회귀를 함께 잡는다.
    """

    def test_empty_state_log_raises(self):
        """
        목적: 상태 로그가 빈 결과는 규칙 1 · 2 · 3 · 7 을 건너뛰고 통과시키지 않고 멈춘다.
              엔진은 거래일마다 상태 로그 한 행을 쓰므로 비어 있으면 내부 불변조건 위반이다.

        Given: 상태 로그가 빈 최소 결과
        When: validate_portfolio_result() 호출
        Then: RuntimeError
        """
        # Given
        result = _minimal_result(pd.DataFrame())

        # When & Then
        with pytest.raises(RuntimeError, match="state_log_df"):
            validate_portfolio_result(result)

    def test_position_keys_come_from_config(self):
        """
        목적: 검사할 자산 키는 설정에서 읽는다 — 상태 로그의 열 이름에서 뽑으면 열이 빠진 자산의 검사가 조용히 사라진다.

        Given: 상태 로그에 tlt 의 종가 열이 없고, tlt 의 2024-01-02 pending 이 다음 날 체결되지 않았다
        When: validate_portfolio_result() 호출
        Then: tlt 의 규칙 1 위반 1건
        """
        # Given
        state_log = _minimal_state_log().drop(columns=["tlt_close"])
        state_log.loc[0, "tlt_pending_intent"] = "EXIT_ALL"

        # When
        violations = validate_portfolio_result(_minimal_result(state_log))

        # Then
        assert violations == ["[규칙1] tlt: 2024-01-02 pending=EXIT_ALL -> 다음날 executed="]

    def test_rebalance_weight_violations_reported_for_single_method(self):
        """
        목적: 매매법이 하나인 실험도 규칙 2 를 지난다 — 리밸런싱한 날 보유 자산의 비중이 목표에서 벗어나면 자산마다 위반을 낸다.

        Given: 월말 리밸런싱한 날(2024-01-03) 비중이 qqq 0.30 · tlt 0.20 (목표 각 0.50)
        When: validate_portfolio_result() 호출
        Then: 규칙 2 위반이 qqq · tlt 하나씩
        """
        # Given
        result = _minimal_result(_minimal_state_log(), rebalanced_last_day=True)

        # When
        violations = validate_portfolio_result(result)

        # Then
        assert [v.split(":")[0] for v in violations] == ["[규칙2] 2024-01-03 qqq", "[규칙2] 2024-01-03 tlt"]

    def test_exit_all_violation_reported(self):
        """
        목적: 검사기가 규칙 3 을 지난다 — EXIT_ALL 을 체결한 날 주수가 남아 있으면 위반을 낸다.

        Given: tlt 의 2024-01-02 pending=EXIT_ALL 이 다음 날 체결됐는데 그날 주수가 2
        When: validate_portfolio_result() 호출
        Then: tlt 의 규칙 3 위반 1건
        """
        # Given
        state_log = _minimal_state_log()
        state_log.loc[0, "tlt_pending_intent"] = "EXIT_ALL"
        state_log.loc[1, "tlt_executed_intent"] = "EXIT_ALL"

        # When
        violations = validate_portfolio_result(_minimal_result(state_log))

        # Then
        assert violations == ["[규칙3] 2024-01-03 tlt: EXIT_ALL 후 shares=2"]
