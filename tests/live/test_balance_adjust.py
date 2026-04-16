"""live.balance_adjust ``apply_balance_adjusts_idempotent`` 계약을 검증한다."""

from __future__ import annotations

import pytest

from live.balance_adjust import apply_balance_adjusts_idempotent
from live.models import BalanceAdjust
from live.state import create_initial_state


@pytest.fixture
def initial_state():
    """기본 state 생성: cash 초기값, 자산 shares 0."""
    return create_initial_state(100_000_000.0)


def _make_adjust(
    rtdb_key: str,
    *,
    asset_id: str | None = None,
    new_shares: int | None = None,
    new_avg_price: float | None = None,
    new_entry_date: str | None = None,
    new_cash: float | None = None,
    reason: str = "test",
) -> BalanceAdjust:
    return BalanceAdjust(
        rtdb_key=rtdb_key,
        input_time_kst="2026-04-10T20:00:00+09:00",
        reason=reason,
        asset_id=asset_id,
        new_shares=new_shares,
        new_avg_price=new_avg_price,
        new_entry_date=new_entry_date,
        new_cash=new_cash,
    )


class TestApplyBalanceAdjustsIdempotent:
    def test_asset_shares_overwritten(self, initial_state):
        """Given 자산 shares 보정 When apply Then actual_shares 교체."""
        adjust = _make_adjust("adj_001", asset_id="sso", new_shares=420)
        new_state, new_ids = apply_balance_adjusts_idempotent(initial_state, [adjust], {})

        assert new_state.assets["sso"].actual_shares == 420
        assert "adj_001" in new_ids
        # 다른 자산은 변경 없음
        assert new_state.assets["gld"].actual_shares == 0

    def test_shared_cash_overwritten(self, initial_state):
        """Given cash 보정 When apply Then shared_cash_actual 교체."""
        adjust = _make_adjust("adj_002", new_cash=95_000_000.0)
        new_state, _ = apply_balance_adjusts_idempotent(initial_state, [adjust], {})

        assert new_state.shared_cash_actual == pytest.approx(95_000_000.0)
        # model cash 는 변경 없음
        assert new_state.shared_cash_model == pytest.approx(100_000_000.0)

    def test_asset_and_cash_together(self, initial_state):
        """Given 자산 + cash 동시 보정 When apply Then 둘 다 반영."""
        adjust = _make_adjust("adj_003", asset_id="gld", new_shares=100, new_cash=85_000_000.0)
        new_state, _ = apply_balance_adjusts_idempotent(initial_state, [adjust], {})

        assert new_state.assets["gld"].actual_shares == 100
        assert new_state.shared_cash_actual == pytest.approx(85_000_000.0)

    def test_idempotent_duplicate_skipped(self, initial_state):
        """Given 같은 rtdb_key 가 applied_ids 에 있음 When apply Then skip."""
        adjust = _make_adjust("adj_dup", asset_id="sso", new_shares=500)
        applied_ids = {"adj_dup": "2026-04-09T09:00:00+09:00"}

        new_state, new_ids = apply_balance_adjusts_idempotent(initial_state, [adjust], applied_ids)

        # 변경 없음
        assert new_state.assets["sso"].actual_shares == 0
        # applied_ids 도 변경 없음
        assert new_ids == applied_ids

    def test_zero_shares_resets_entry_fields(self, initial_state):
        """Given new_shares=0 보정 When apply Then avg_entry_price / entry_date 리셋."""
        # 먼저 기존 state 에 actual 값 세팅
        initial_state.assets["sso"].actual_shares = 420
        initial_state.assets["sso"].actual_avg_entry_price = 82.05
        initial_state.assets["sso"].actual_entry_date = "2026-03-01"

        adjust = _make_adjust("adj_zero", asset_id="sso", new_shares=0)
        new_state, _ = apply_balance_adjusts_idempotent(initial_state, [adjust], {})

        assert new_state.assets["sso"].actual_shares == 0
        assert new_state.assets["sso"].actual_avg_entry_price == pytest.approx(0.0)
        assert new_state.assets["sso"].actual_entry_date is None

    def test_unknown_asset_raises(self, initial_state):
        """Given 존재하지 않는 asset_id When apply Then ValueError (fail-fast)."""
        adjust = _make_adjust("adj_ghost", asset_id="unknown_asset", new_shares=42)
        with pytest.raises(ValueError, match="알 수 없는 asset_id"):
            apply_balance_adjusts_idempotent(initial_state, [adjust], {})

    def test_input_state_immutable(self, initial_state):
        """Given apply 호출 후 Then 입력 state 는 변경되지 않는다."""
        original_sso = initial_state.assets["sso"].actual_shares
        adjust = _make_adjust("adj_imm", asset_id="sso", new_shares=500)
        apply_balance_adjusts_idempotent(initial_state, [adjust], {})

        assert initial_state.assets["sso"].actual_shares == original_sso

    def test_multiple_adjusts_all_applied(self, initial_state):
        """Given 여러 adjust When apply Then 순차 반영."""
        adjusts = [
            _make_adjust("a1", asset_id="sso", new_shares=100),
            _make_adjust("a2", asset_id="gld", new_shares=50),
            _make_adjust("a3", new_cash=90_000_000.0),
        ]
        new_state, new_ids = apply_balance_adjusts_idempotent(initial_state, adjusts, {})

        assert new_state.assets["sso"].actual_shares == 100
        assert new_state.assets["gld"].actual_shares == 50
        assert new_state.shared_cash_actual == pytest.approx(90_000_000.0)
        assert len(new_ids) == 3


class TestNewAvgPriceAndEntryDate:
    """new_avg_price / new_entry_date 신규 필드 계약 테스트.

    이번 plan (PLAN_balance_adjust_new_avg_price.md) 에서 추가된 시나리오.
    질문 1 = D 안 (new_avg_price + new_entry_date 동시 추가),
    질문 2 = A 안 (asset_id 필수 fail-fast) 의 정책을 고정한다.
    """

    @pytest.fixture
    def state_with_position(self):
        """SSO 에 기존 포지션이 있는 state (평균가 보정 테스트용)."""
        state = create_initial_state(100_000_000.0)
        state.assets["sso"].actual_shares = 420
        state.assets["sso"].actual_avg_entry_price = 80.00
        state.assets["sso"].actual_entry_date = "2026-03-01"
        return state

    def test_ba_1_new_avg_price_only(self, state_with_position):
        """
        [T-BA.1] Given actual_shares > 0 + new_avg_price 단독
        When apply
        Then actual_avg_entry_price 변경, actual_shares / actual_entry_date 유지.
        """
        adjust = _make_adjust("ba1", asset_id="sso", new_avg_price=85.00)
        new_state, new_ids = apply_balance_adjusts_idempotent(state_with_position, [adjust], {})

        sso = new_state.assets["sso"]
        assert sso.actual_shares == 420  # 유지
        assert sso.actual_avg_entry_price == pytest.approx(85.00)  # 변경
        assert sso.actual_entry_date == "2026-03-01"  # 유지
        assert "ba1" in new_ids

    def test_ba_2_new_shares_and_new_avg_price(self, state_with_position):
        """
        [T-BA.2] Given new_shares > 0 + new_avg_price 동시 지정
        When apply
        Then 두 필드 모두 변경, actual_entry_date 는 유지.
        """
        adjust = _make_adjust("ba2", asset_id="sso", new_shares=500, new_avg_price=82.50)
        new_state, _ = apply_balance_adjusts_idempotent(state_with_position, [adjust], {})

        sso = new_state.assets["sso"]
        assert sso.actual_shares == 500
        assert sso.actual_avg_entry_price == pytest.approx(82.50)
        assert sso.actual_entry_date == "2026-03-01"  # 기존 값 유지

    def test_ba_3_new_shares_zero_overrides_new_avg_price(self, state_with_position):
        """
        [T-BA.3] Given new_shares=0 + new_avg_price 동시 지정
        When apply
        Then new_shares=0 리셋 규칙 우선 (avg_price=0.0, entry_date=None), new_avg_price 무시.
        """
        adjust = _make_adjust("ba3", asset_id="sso", new_shares=0, new_avg_price=85.00)
        new_state, _ = apply_balance_adjusts_idempotent(state_with_position, [adjust], {})

        sso = new_state.assets["sso"]
        assert sso.actual_shares == 0
        assert sso.actual_avg_entry_price == pytest.approx(0.0)  # 리셋 우선
        assert sso.actual_entry_date is None  # 리셋

    def test_ba_4_new_avg_price_without_position_raises(self, initial_state):
        """
        [T-BA.4] Given new_avg_price 단독 + actual_shares == 0
        When apply
        Then ValueError (보유 주수가 0 인 자산의 평균가 설정 불가).
        """
        adjust = _make_adjust("ba4", asset_id="sso", new_avg_price=85.00)
        with pytest.raises(ValueError, match="보유 주수가 0"):
            apply_balance_adjusts_idempotent(initial_state, [adjust], {})

    def test_ba_5_new_avg_price_without_asset_id_raises(self, state_with_position):
        """
        [T-BA.5] Given new_avg_price 지정 + asset_id=None
        When apply
        Then ValueError (new_avg_price 지정 시 asset_id 필수 — 2 단계 검증의 최후 방어선).
        """
        adjust = _make_adjust("ba5", asset_id=None, new_avg_price=85.00)
        with pytest.raises(ValueError, match="asset_id"):
            apply_balance_adjusts_idempotent(state_with_position, [adjust], {})

    def test_ba_6_new_entry_date_only(self, state_with_position):
        """
        [T-BA.6] Given actual_shares > 0 + new_entry_date 단독
        When apply
        Then actual_entry_date 변경, actual_avg_entry_price / actual_shares 유지.
        """
        adjust = _make_adjust("ba6", asset_id="sso", new_entry_date="2026-04-01")
        new_state, _ = apply_balance_adjusts_idempotent(state_with_position, [adjust], {})

        sso = new_state.assets["sso"]
        assert sso.actual_shares == 420  # 유지
        assert sso.actual_avg_entry_price == pytest.approx(80.00)  # 유지
        assert sso.actual_entry_date == "2026-04-01"  # 변경

    def test_ba_7_new_entry_date_without_position_raises(self, initial_state):
        """
        [T-BA.7] Given new_entry_date 단독 + actual_shares == 0
        When apply
        Then ValueError (보유 주수가 0 인 자산의 진입일 설정 불가).
        """
        adjust = _make_adjust("ba7", asset_id="sso", new_entry_date="2026-04-01")
        with pytest.raises(ValueError, match="보유 주수가 0"):
            apply_balance_adjusts_idempotent(initial_state, [adjust], {})

    def test_ba_8_all_fields_none_raises(self, initial_state):
        """
        [T-BA.8] Given 모든 보정 필드 None
        When apply
        Then ValueError (유효한 값이 없음).

        참고: 이 검증은 rtdb_gateway._dict_to_balance_adjust 에서 수행되므로
        여기서는 해당 경로를 직접 호출한다.
        """
        from live.rtdb_gateway import _dict_to_balance_adjust

        raw = {
            "reason": "invalid",
            "input_time_kst": "2026-04-10T20:00:00+09:00",
        }
        with pytest.raises(ValueError, match="유효한"):
            _dict_to_balance_adjust(raw, "ba8")

    def test_ba_9_model_axis_immutable(self, state_with_position):
        """
        [T-BA.9] Given new_avg_price 적용
        When apply
        Then model_* / shared_cash_model 필드는 절대 변하지 않는다 (model/actual 분리 원칙).
        """
        sso_before_model_shares = state_with_position.assets["sso"].model_shares
        sso_before_model_avg = state_with_position.assets["sso"].model_avg_entry_price
        sso_before_model_date = state_with_position.assets["sso"].model_entry_date
        before_cash_model = state_with_position.shared_cash_model

        adjust = _make_adjust(
            "ba9",
            asset_id="sso",
            new_shares=500,
            new_avg_price=82.50,
            new_entry_date="2026-04-01",
            new_cash=99_000_000.0,
        )
        new_state, _ = apply_balance_adjusts_idempotent(state_with_position, [adjust], {})

        # model 축은 불변
        sso = new_state.assets["sso"]
        assert sso.model_shares == sso_before_model_shares
        assert sso.model_avg_entry_price == pytest.approx(sso_before_model_avg)
        assert sso.model_entry_date == sso_before_model_date
        assert new_state.shared_cash_model == pytest.approx(before_cash_model)

        # actual 축은 변경
        assert sso.actual_shares == 500
        assert sso.actual_avg_entry_price == pytest.approx(82.50)
        assert sso.actual_entry_date == "2026-04-01"
        assert new_state.shared_cash_actual == pytest.approx(99_000_000.0)
