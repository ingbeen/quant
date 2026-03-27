"""포트폴리오 플래닝 로직 테스트

OrderIntent 모델, 시그널 intent 생성, projected portfolio, 리밸런싱 intent 생성,
intent 병합 및 이중 트리거 임계값을 검증한다.
"""

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from qbt.backtest.engines.portfolio_planning import (
    OrderIntent,
    ProjectedPortfolio,
    compute_projected_portfolio,
    generate_signal_intents,
    merge_intents,
)
from qbt.backtest.engines.portfolio_rebalance import (
    DEFAULT_REBALANCE_POLICY,
    RebalancePolicy,
)
from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.common_constants import COL_CLOSE, COL_DATE

# ============================================================================
# Mock 전략 클래스 (TestGenerateSignalIntents에서 사용)
# ============================================================================


class _MockBuyStrategy:
    """항상 buy signal을 반환하는 mock 전략 (SignalStrategy Protocol 구현)."""

    def check_buy(self, signal_df: pd.DataFrame, i: int, current_date: date) -> bool:  # noqa: ARG002
        return True

    def check_sell(self, signal_df: pd.DataFrame, i: int) -> bool:  # noqa: ARG002
        return False

    def get_buy_meta(self) -> dict[str, float | int]:
        return {"hold_days_used": 3}


class _MockSellStrategy:
    """항상 sell signal을 반환하는 mock 전략."""

    def check_buy(self, signal_df: pd.DataFrame, i: int, current_date: date) -> bool:  # noqa: ARG002
        return False

    def check_sell(self, signal_df: pd.DataFrame, i: int) -> bool:  # noqa: ARG002
        return True

    def get_buy_meta(self) -> dict[str, float | int]:
        return {}


class _MockHoldStrategy:
    """아무 signal도 발생하지 않는 mock 전략."""

    def check_buy(self, signal_df: pd.DataFrame, i: int, current_date: date) -> bool:  # noqa: ARG002
        return False

    def check_sell(self, signal_df: pd.DataFrame, i: int) -> bool:  # noqa: ARG002
        return False

    def get_buy_meta(self) -> dict[str, float | int]:
        return {}


# ============================================================================
# 테스트 클래스
# ============================================================================


class TestOrderIntentModel:
    """OrderIntent 모델 계약 검증.

    핵심 계약: OrderIntent는 4가지 intent_type을 지원한다.
    - EXIT_ALL: 보유 전량 청산 (signal sell)
    - ENTER_TO_TARGET: 신규 진입 목표 달성 (signal buy)
    - REDUCE_TO_TARGET: 초과분 매도 목표 달성 (rebalance)
    - INCREASE_TO_TARGET: 미달분 매수 목표 달성 (rebalance)
    """

    def test_exit_all_intent_type(self) -> None:
        """
        목적: EXIT_ALL 타입으로 OrderIntent를 생성할 수 있어야 함.

        Given: intent_type="EXIT_ALL" 파라미터
        When:  OrderIntent 생성
        Then:  intent.intent_type == "EXIT_ALL", hold_days_used 기본값 0
        """
        # Given / When
        intent = OrderIntent(
            asset_id="qqq",
            intent_type="EXIT_ALL",
            current_amount=100_000.0,
            target_amount=0.0,
            delta_amount=-100_000.0,
            target_weight=0.0,
            reason="signal sell",
        )

        # Then
        assert intent.intent_type == "EXIT_ALL"
        assert intent.hold_days_used == 0  # 기본값

    def test_enter_to_target_intent_type(self) -> None:
        """
        목적: ENTER_TO_TARGET 타입으로 OrderIntent를 생성할 수 있어야 함.

        Given: intent_type="ENTER_TO_TARGET", hold_days_used=3
        When:  OrderIntent 생성
        Then:  intent.intent_type == "ENTER_TO_TARGET", intent.hold_days_used == 3
        """
        intent = OrderIntent(
            asset_id="qqq",
            intent_type="ENTER_TO_TARGET",
            current_amount=0.0,
            target_amount=300_000.0,
            delta_amount=300_000.0,
            target_weight=0.30,
            reason="signal buy",
            hold_days_used=3,
        )

        assert intent.intent_type == "ENTER_TO_TARGET"
        assert intent.hold_days_used == 3

    def test_reduce_to_target_intent_type(self) -> None:
        """
        목적: REDUCE_TO_TARGET 타입으로 OrderIntent를 생성할 수 있어야 함.

        Given: intent_type="REDUCE_TO_TARGET", delta_amount < 0
        When:  OrderIntent 생성
        Then:  intent.intent_type == "REDUCE_TO_TARGET"
        """
        intent = OrderIntent(
            asset_id="qqq",
            intent_type="REDUCE_TO_TARGET",
            current_amount=400_000.0,
            target_amount=300_000.0,
            delta_amount=-100_000.0,
            target_weight=0.30,
            reason="rebalance",
        )

        assert intent.intent_type == "REDUCE_TO_TARGET"
        assert intent.delta_amount == pytest.approx(-100_000.0, abs=0.01)

    def test_increase_to_target_intent_type(self) -> None:
        """
        목적: INCREASE_TO_TARGET 타입으로 OrderIntent를 생성할 수 있어야 함.

        Given: intent_type="INCREASE_TO_TARGET", delta_amount > 0
        When:  OrderIntent 생성
        Then:  intent.intent_type == "INCREASE_TO_TARGET"
        """
        intent = OrderIntent(
            asset_id="gld",
            intent_type="INCREASE_TO_TARGET",
            current_amount=200_000.0,
            target_amount=300_000.0,
            delta_amount=100_000.0,
            target_weight=0.30,
            reason="rebalance",
        )

        assert intent.intent_type == "INCREASE_TO_TARGET"
        assert intent.delta_amount == pytest.approx(100_000.0, abs=0.01)


class TestGenerateSignalIntents:
    """generate_signal_intents 계약 검증.

    핵심 계약:
    - position=0 + buy signal → ENTER_TO_TARGET (target_amount = current_equity × target_weight)
    - position>0 + sell signal → EXIT_ALL
    - 신호 없음(HOLD) → dict에 포함 안 됨
    """

    def _make_signal_df(self) -> pd.DataFrame:
        """최소 signal DataFrame 생성 (mock 전략은 df를 사용하지 않음)."""
        return pd.DataFrame({COL_DATE: [date(2024, 1, 2)], COL_CLOSE: [100.0]})

    def test_buy_signal_generates_enter_to_target(self) -> None:
        """
        목적: position=0이고 buy signal 발생 시 ENTER_TO_TARGET 생성 검증.

        Given: position=0, signal_state="sell", buy strategy
               current_equity=1_000_000, target_weight=0.30
        When:  generate_signal_intents() 호출
        Then:  qqq에 ENTER_TO_TARGET intent 생성
               target_amount ≈ current_equity × 0.30 = 300,000
        """
        from qbt.backtest.engines.portfolio_engine import (  # pyright: ignore[reportPrivateUsage]
            AssetState as NewAssetState,
        )

        # Given
        asset_states = {"qqq": NewAssetState(position=0, signal_state="sell")}
        strategies: dict[str, Any] = {"qqq": _MockBuyStrategy()}
        signal_dfs = {"qqq": self._make_signal_df()}
        equity_vals = {"qqq": 0.0}
        slot_dict = {"qqq": AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), target_weight=0.30)}
        current_equity = 1_000_000.0

        # When
        intents = generate_signal_intents(
            asset_states, strategies, signal_dfs, equity_vals, slot_dict, current_equity, 0, date(2024, 1, 2)
        )

        # Then
        assert "qqq" in intents, "buy signal 발생 시 qqq에 intent가 생성되어야 함"
        assert intents["qqq"].intent_type == "ENTER_TO_TARGET"
        assert intents["qqq"].target_amount == pytest.approx(300_000.0, rel=1e-6)

    def test_sell_signal_generates_exit_all(self) -> None:
        """
        목적: position>0이고 sell signal 발생 시 EXIT_ALL 생성 검증.

        Given: position=100, signal_state="buy", sell strategy
               equity_vals["qqq"]=100_000
        When:  generate_signal_intents() 호출
        Then:  qqq에 EXIT_ALL intent 생성
               current_amount == equity_vals["qqq"], target_amount == 0
        """
        from qbt.backtest.engines.portfolio_engine import (  # pyright: ignore[reportPrivateUsage]
            AssetState as NewAssetState,
        )

        # Given
        asset_states = {"qqq": NewAssetState(position=100, signal_state="buy")}
        strategies: dict[str, Any] = {"qqq": _MockSellStrategy()}
        signal_dfs = {"qqq": self._make_signal_df()}
        equity_vals = {"qqq": 100_000.0}
        slot_dict = {"qqq": AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), target_weight=0.30)}
        current_equity = 1_000_000.0

        # When
        intents = generate_signal_intents(
            asset_states, strategies, signal_dfs, equity_vals, slot_dict, current_equity, 0, date(2024, 1, 2)
        )

        # Then
        assert "qqq" in intents, "sell signal 발생 시 qqq에 intent가 생성되어야 함"
        assert intents["qqq"].intent_type == "EXIT_ALL"
        assert intents["qqq"].current_amount == pytest.approx(100_000.0, abs=0.01)
        assert intents["qqq"].target_amount == pytest.approx(0.0, abs=0.01)

    def test_no_signal_generates_no_intent(self) -> None:
        """
        목적: signal이 없으면 intent가 생성되지 않음(HOLD) 검증.

        Given: position=0, hold strategy (buy도 sell도 없음)
        When:  generate_signal_intents() 호출
        Then:  빈 dict 반환 (qqq에 intent 없음)
        """
        from qbt.backtest.engines.portfolio_engine import (  # pyright: ignore[reportPrivateUsage]
            AssetState as NewAssetState,
        )

        # Given
        asset_states = {"qqq": NewAssetState(position=0, signal_state="sell")}
        strategies: dict[str, Any] = {"qqq": _MockHoldStrategy()}
        signal_dfs = {"qqq": self._make_signal_df()}
        equity_vals = {"qqq": 0.0}
        slot_dict = {"qqq": AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), target_weight=0.30)}
        current_equity = 1_000_000.0

        # When
        intents = generate_signal_intents(
            asset_states, strategies, signal_dfs, equity_vals, slot_dict, current_equity, 0, date(2024, 1, 2)
        )

        # Then
        assert "qqq" not in intents, "신호 없으면 qqq에 intent가 생성되면 안 됨"


class TestComputeProjectedPortfolio:
    """compute_projected_portfolio 계약 검증.

    핵심 계약:
    - EXIT_ALL 자산: projected_amounts[asset_id]=0, active에서 제거, cash 증가
    - ENTER_TO_TARGET 자산: active에 추가 (아직 position=0이므로 amount는 0)
    - intent 없는 기존 보유 자산: 현재 상태 유지
    """

    def _make_intent(
        self,
        asset_id: str,
        intent_type: str,
        current_amount: float = 0.0,
        target_amount: float = 0.0,
        delta_amount: float = 0.0,
    ) -> Any:
        """테스트용 OrderIntent 생성 헬퍼."""
        return OrderIntent(
            asset_id=asset_id,
            intent_type=intent_type,  # type: ignore[arg-type]
            current_amount=current_amount,
            target_amount=target_amount,
            delta_amount=delta_amount,
            target_weight=0.30,
            reason="test",
        )

    def test_exit_all_removes_from_active_and_increases_cash(self) -> None:
        """
        목적: EXIT_ALL intent → projected_amounts=0, active 제거, cash 증가 검증.

        Given: QQQ position=100, equity_val=100_000, shared_cash=50_000
               EXIT_ALL intent for qqq
        When:  compute_projected_portfolio() 호출
        Then:  projected.projected_amounts["qqq"] == 0
               "qqq" not in projected.active_assets
               projected.projected_cash ≈ 50_000 + 100_000 = 150_000
        """
        from qbt.backtest.engines.portfolio_engine import (  # pyright: ignore[reportPrivateUsage]
            AssetState as NewAssetState,
        )

        # Given
        asset_states = {"qqq": NewAssetState(position=100, signal_state="buy")}
        signal_intents = {"qqq": self._make_intent("qqq", "EXIT_ALL", current_amount=100_000.0)}
        equity_vals = {"qqq": 100_000.0}
        asset_closes_map = {"qqq": 1000.0}
        shared_cash = 50_000.0

        # When
        projected = compute_projected_portfolio(
            asset_states, signal_intents, equity_vals, asset_closes_map, shared_cash
        )

        # Then
        assert projected.projected_amounts.get("qqq", 0.0) == pytest.approx(0.0, abs=0.01)
        assert "qqq" not in projected.active_assets
        assert projected.projected_cash == pytest.approx(150_000.0, abs=0.01)

    def test_enter_to_target_adds_to_active(self) -> None:
        """
        목적: ENTER_TO_TARGET intent → active에 추가, cash 변화 없음 검증.

        Given: QQQ position=0 (signal_state="sell"), shared_cash=500_000
               ENTER_TO_TARGET intent for qqq
        When:  compute_projected_portfolio() 호출
        Then:  "qqq" in projected.active_assets
               projected.projected_amounts["qqq"] == 0 (아직 position 없음)
               projected.projected_cash == 500_000 (변화 없음)
        """
        from qbt.backtest.engines.portfolio_engine import (  # pyright: ignore[reportPrivateUsage]
            AssetState as NewAssetState,
        )

        # Given
        asset_states = {"qqq": NewAssetState(position=0, signal_state="sell")}
        signal_intents = {
            "qqq": self._make_intent("qqq", "ENTER_TO_TARGET", target_amount=300_000.0, delta_amount=300_000.0)
        }
        equity_vals = {"qqq": 0.0}
        asset_closes_map = {"qqq": 1000.0}
        shared_cash = 500_000.0

        # When
        projected = compute_projected_portfolio(
            asset_states, signal_intents, equity_vals, asset_closes_map, shared_cash
        )

        # Then
        assert "qqq" in projected.active_assets
        assert projected.projected_amounts.get("qqq", 0.0) == pytest.approx(0.0, abs=0.01)
        assert projected.projected_cash == pytest.approx(500_000.0, abs=0.01)


class TestBuildRebalanceIntents:
    """RebalancePolicy.should_rebalance + build_rebalance_intents 계약 검증.

    핵심 계약:
    - active 자산 중 threshold 초과 자산이 없으면 should_rebalance=False → 인텐트 없음
    - threshold 초과 시 전체 active 자산에 대해 REDUCE/INCREASE 생성
    - inactive 자산(exit 예정)은 대상에서 제외
    """

    def _make_projected(
        self,
        active_assets: set[str],
        projected_amounts: dict[str, float],
        projected_cash: float,
    ) -> Any:
        """테스트용 ProjectedPortfolio 생성."""
        return ProjectedPortfolio(
            projected_amounts=projected_amounts,
            projected_cash=projected_cash,
            active_assets=active_assets,
        )

    def test_no_rebalance_when_threshold_not_exceeded(self) -> None:
        """
        목적: active 자산 편차가 daily_threshold_rate 이하이면 should_rebalance=False 검증.

        Given: QQQ 31% (target 30%), daily_threshold_rate=0.20
               |31/30 - 1| = 0.033 < 0.20
        When:  policy.should_rebalance(..., is_month_start=False)
        Then:  False → 리밸런싱 인텐트 없음
        """
        # Given: QQQ 31% (편차 3.3% < 20%)
        total_equity = 1_000_000.0
        projected = self._make_projected(
            active_assets={"qqq"},
            projected_amounts={"qqq": 310_000.0},  # 31%
            projected_cash=690_000.0,
        )
        slot_dict = {"qqq": AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), target_weight=0.30)}
        policy = RebalancePolicy(monthly_threshold_rate=0.10, daily_threshold_rate=0.20)

        # When: 일중 기준(is_month_start=False) → daily_threshold_rate=0.20 적용
        result_intents: dict[str, Any] = {}
        if policy.should_rebalance(projected, slot_dict, total_equity, is_month_start=False):
            result_intents = policy.build_rebalance_intents(projected, slot_dict, total_equity, date(2024, 1, 2))

        # Then
        assert result_intents == {}, "threshold 미초과 시 리밸런싱 인텐트가 없어야 함"

    def test_rebalance_generates_reduce_and_increase(self) -> None:
        """
        목적: threshold 초과 시 REDUCE_TO_TARGET/INCREASE_TO_TARGET 생성 검증.

        Given: QQQ 50% (target 30%), GLD 10% (target 30%)
               |50/30 - 1| = 0.667 > 0.20 → daily threshold 초과
               total_equity=1,000,000, projected_cash=400,000
        When:  policy.should_rebalance() → True → policy.build_rebalance_intents() 호출
        Then:  QQQ → REDUCE_TO_TARGET
               GLD → INCREASE_TO_TARGET
        """
        # Given: QQQ 과비중, GLD 과소비중
        total_equity = 1_000_000.0
        projected = self._make_projected(
            active_assets={"qqq", "gld"},
            projected_amounts={"qqq": 500_000.0, "gld": 100_000.0},  # 50%, 10%
            projected_cash=400_000.0,
        )
        slot_dict = {
            "qqq": AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), target_weight=0.30),
            "gld": AssetSlotConfig("gld", Path("dummy"), Path("dummy"), target_weight=0.30),
        }
        policy = RebalancePolicy(monthly_threshold_rate=0.10, daily_threshold_rate=0.20)

        # When: 일중 기준(is_month_start=False) → daily_threshold_rate=0.20 적용, 편차 66.7% > 20% → 트리거
        result: dict[str, Any] = {}
        if policy.should_rebalance(projected, slot_dict, total_equity, is_month_start=False):
            result = policy.build_rebalance_intents(projected, slot_dict, total_equity, date(2024, 1, 2))

        # Then
        assert "qqq" in result, "QQQ 과비중이므로 REDUCE_TO_TARGET이 생성되어야 함"
        assert result["qqq"].intent_type == "REDUCE_TO_TARGET"
        assert "gld" in result, "GLD 과소비중이므로 INCREASE_TO_TARGET이 생성되어야 함"
        assert result["gld"].intent_type == "INCREASE_TO_TARGET"


class TestMergeIntents:
    """merge_intents 계약 검증.

    핵심 계약:
    - EXIT_ALL은 항상 우선 (rebalance intent 무시)
    - ENTER_TO_TARGET + INCREASE_TO_TARGET → ENTER_TO_TARGET (rebalance target_amount 사용)
    - 단독 signal/rebalance intent는 그대로 통과
    - 결과: 자산당 1개 intent 보장
    """

    def _make_intent(
        self,
        asset_id: str,
        intent_type: str,
        delta_amount: float = 0.0,
        target_amount: float = 0.0,
        hold_days_used: int = 0,
    ) -> Any:
        """테스트용 OrderIntent 생성 헬퍼."""
        return OrderIntent(
            asset_id=asset_id,
            intent_type=intent_type,  # type: ignore[arg-type]
            current_amount=0.0,
            target_amount=target_amount,
            delta_amount=delta_amount,
            target_weight=0.30,
            reason="test",
            hold_days_used=hold_days_used,
        )

    def test_exit_all_overrides_rebalance(self) -> None:
        """
        목적: EXIT_ALL signal이 rebalance intent를 항상 우선하는지 검증.

        Given: signal → EXIT_ALL, rebalance → REDUCE_TO_TARGET
        When:  merge_intents() 호출
        Then:  merged["qqq"].intent_type == "EXIT_ALL"
        """
        # Given
        signal_intents: dict[str, Any] = {"qqq": self._make_intent("qqq", "EXIT_ALL")}
        rebalance_intents: dict[str, Any] = {
            "qqq": self._make_intent("qqq", "REDUCE_TO_TARGET", delta_amount=-100_000.0)
        }

        # When
        merged = merge_intents(signal_intents, rebalance_intents)

        # Then
        assert "qqq" in merged
        assert merged["qqq"].intent_type == "EXIT_ALL"

    def test_enter_plus_increase_becomes_enter_with_rebalance_target(self) -> None:
        """
        목적: ENTER_TO_TARGET + INCREASE_TO_TARGET → ENTER_TO_TARGET (rebalance target 사용) 검증.

        Given: signal → ENTER_TO_TARGET (target=300_000, hold_days_used=3)
               rebalance → INCREASE_TO_TARGET (target=320_000, delta=320_000)
        When:  merge_intents() 호출
        Then:  merged.intent_type == "ENTER_TO_TARGET"
               merged.target_amount == 320_000 (rebalance의 target 사용)
               merged.hold_days_used == 3 (signal의 hold_days_used 보존)
        """
        # Given
        signal_intents: dict[str, Any] = {
            "qqq": self._make_intent("qqq", "ENTER_TO_TARGET", target_amount=300_000.0, hold_days_used=3)
        }
        rebalance_intents: dict[str, Any] = {
            "qqq": self._make_intent("qqq", "INCREASE_TO_TARGET", target_amount=320_000.0, delta_amount=320_000.0)
        }

        # When
        merged = merge_intents(signal_intents, rebalance_intents)

        # Then
        assert merged["qqq"].intent_type == "ENTER_TO_TARGET"
        assert merged["qqq"].target_amount == pytest.approx(320_000.0, abs=0.01)
        assert merged["qqq"].hold_days_used == 3  # signal의 hold_days_used 보존

    def test_single_rebalance_passes_through(self) -> None:
        """
        목적: rebalance intent만 있으면 그대로 통과 검증.

        Given: signal={}, rebalance → REDUCE_TO_TARGET
        When:  merge_intents() 호출
        Then:  merged["qqq"].intent_type == "REDUCE_TO_TARGET"
        """
        # Given
        signal_intents: dict[str, Any] = {}
        rebalance_intents: dict[str, Any] = {
            "qqq": self._make_intent("qqq", "REDUCE_TO_TARGET", delta_amount=-100_000.0)
        }

        # When
        merged = merge_intents(signal_intents, rebalance_intents)

        # Then
        assert "qqq" in merged
        assert merged["qqq"].intent_type == "REDUCE_TO_TARGET"


class TestDualTriggerThreshold:
    """이중 트리거 임계값 계약 테스트.

    핵심 계약:
    - DEFAULT_REBALANCE_POLICY.monthly_threshold_rate = 0.10 (월 첫날 임계값)
    - DEFAULT_REBALANCE_POLICY.daily_threshold_rate = 0.20 (매일 임계값)
    - RebalancePolicy.should_rebalance(): is_month_start에 따라 임계값 결정
    - 10%~20% 편차 구간: 월 첫날에만 트리거, 일중에는 패스
    """

    def test_default_rebalance_policy_threshold_values(self) -> None:
        """
        목적: DEFAULT_REBALANCE_POLICY의 임계값이 정확한지 검증.

        Given: qbt.backtest.engines.portfolio_rebalance 모듈의 DEFAULT_REBALANCE_POLICY
        When:  monthly_threshold_rate, daily_threshold_rate 조회
        Then:  monthly_threshold_rate == 0.10
               daily_threshold_rate == 0.20
        """
        assert DEFAULT_REBALANCE_POLICY.monthly_threshold_rate == pytest.approx(0.10, abs=1e-9)
        assert DEFAULT_REBALANCE_POLICY.daily_threshold_rate == pytest.approx(0.20, abs=1e-9)

    def test_check_rebalancing_monthly_threshold_triggers_at_11pct(self) -> None:
        """
        목적: monthly_threshold_rate=0.10 기준, 편차 11%에서 월 첫날 트리거됨을 검증.

        Given: target=0.30, actual=0.333 → |0.333/0.30 - 1| ≈ 0.11 > 0.10
               RebalancePolicy(monthly_threshold_rate=0.10, ...)
        When:  policy.should_rebalance(..., is_month_start=True)
        Then:  True (월 임계값 초과 → 트리거)
        """
        # Given: QQQ 33.3% (target 30%, 편차 11%)
        total_equity = 100_000.0
        projected = ProjectedPortfolio(
            projected_amounts={"qqq": 33_300.0},
            projected_cash=66_700.0,
            active_assets={"qqq"},
        )
        slot_dict = {"qqq": AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), target_weight=0.30)}
        policy = RebalancePolicy(monthly_threshold_rate=0.10, daily_threshold_rate=0.20)

        # When: 월 첫 거래일 기준(is_month_start=True) → monthly_threshold_rate=0.10 적용
        triggers = policy.should_rebalance(projected, slot_dict, total_equity, is_month_start=True)

        # Then
        assert triggers, "편차 11% > 월 임계값 10%이면 트리거되어야 함"

    def test_check_rebalancing_daily_no_trigger_at_15pct(self) -> None:
        """
        목적: daily_threshold_rate=0.20 기준, 편차 15%에서 트리거 없음을 검증.

        Given: target=0.30, actual=0.345 → |0.345/0.30 - 1| = 0.15 < 0.20
               RebalancePolicy(daily_threshold_rate=0.20)
        When:  policy.should_rebalance(..., is_month_start=False)
        Then:  False (월 중간 임계값 미달 → 패스)
        """
        # Given: QQQ 34.5% (target 30%, 편차 15%)
        total_equity = 100_000.0
        projected = ProjectedPortfolio(
            projected_amounts={"qqq": 34_500.0},
            projected_cash=65_500.0,
            active_assets={"qqq"},
        )
        slot_dict = {"qqq": AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), target_weight=0.30)}
        policy = RebalancePolicy(monthly_threshold_rate=0.10, daily_threshold_rate=0.20)

        # When: 일중 기준(is_month_start=False) → daily_threshold_rate=0.20 적용
        triggers = policy.should_rebalance(projected, slot_dict, total_equity, is_month_start=False)

        # Then
        assert not triggers, "편차 15% < 매일 임계값 20%이면 트리거 없어야 함"

    def test_check_rebalancing_monthly_no_trigger_below_10pct(self) -> None:
        """
        목적: monthly_threshold_rate=0.10 기준, 편차 9%에서 월 첫날 트리거 없음을 검증.

        Given: target=0.30, actual=0.327 → |0.327/0.30 - 1| = 0.09 < 0.10
               RebalancePolicy(monthly_threshold_rate=0.10)
        When:  policy.should_rebalance(..., is_month_start=True)
        Then:  False (편차 < 월 임계값 → 패스)
        """
        # Given: QQQ 32.7% (target 30%, 편차 9%)
        total_equity = 100_000.0
        projected = ProjectedPortfolio(
            projected_amounts={"qqq": 32_700.0},
            projected_cash=67_300.0,
            active_assets={"qqq"},
        )
        slot_dict = {"qqq": AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), target_weight=0.30)}
        policy = RebalancePolicy(monthly_threshold_rate=0.10, daily_threshold_rate=0.20)

        # When: 월 첫 거래일 기준(is_month_start=True) → monthly_threshold_rate=0.10 적용
        triggers = policy.should_rebalance(projected, slot_dict, total_equity, is_month_start=True)

        # Then
        assert not triggers, "편차 9% < 월 임계값 10%이면 트리거 없어야 함"
