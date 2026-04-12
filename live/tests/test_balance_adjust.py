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
    new_cash: float | None = None,
    reason: str = "test",
) -> BalanceAdjust:
    return BalanceAdjust(
        rtdb_key=rtdb_key,
        input_time_kst="2026-04-10T20:00:00+09:00",
        reason=reason,
        asset_id=asset_id,
        new_shares=new_shares,
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
