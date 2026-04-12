"""live.buffer_serializer — BufferZoneStrategy 직렬화 어댑터 테스트.

설계서 4.3 및 TODO T-4.1 ~ T-4.3 시나리오를 고정한다.

테스트 철학 (tests/CLAUDE.md):
- Given-When-Then
- QBT 본체 수정 없음을 간접 검증 (실제 BufferZoneStrategy 사용)
- 부동소수점은 pytest.approx
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from live.buffer_serializer import extract_buffer_state, get_current_bands, restore_buffer_state
from live.models import BufferZoneState
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.buffer_zone_helpers import HoldState

# ============================================================================
# 테스트 픽스처
# ============================================================================


def _make_signal_df() -> pd.DataFrame:
    """ma_200 과 Close 컬럼을 가진 최소 signal_df 를 생성한다.

    Close 가 ma * 1.05 로 상승하여 상단 밴드(ma * 1.03) 돌파 매수 시그널을 유도한다.
    """
    # 10 개 행. ma=100 고정, close 는 상승 추세
    ma_values = [100.0] * 10
    close_values = [98.0, 99.0, 100.0, 101.0, 102.5, 103.5, 104.5, 105.0, 106.0, 107.0]
    return pd.DataFrame({"ma_200": ma_values, "Close": close_values})


def _make_fresh_strategy(hold_days: int = 0) -> BufferZoneStrategy:
    return BufferZoneStrategy(
        ma_col="ma_200",
        buy_buffer_pct=0.03,
        sell_buffer_pct=0.05,
        hold_days=hold_days,
    )


def _run_strategy_for_a_few_days(strategy: BufferZoneStrategy, n_days: int = 5) -> None:
    """실제 전략을 여러 날 구동하여 내부 상태를 자연스럽게 갱신시킨다."""
    signal_df = _make_signal_df()
    current_date = date(2026, 4, 1)
    for i in range(n_days):
        strategy.check_buy(signal_df, i, current_date)


# ============================================================================
# extract_buffer_state
# ============================================================================


class TestExtractBufferState:
    def test_initial_strategy_has_none_bands(self):
        """갓 생성된 strategy 는 prev_upper/prev_lower 가 None."""
        strategy = _make_fresh_strategy()
        state = extract_buffer_state(strategy)
        assert state.prev_upper is None
        assert state.prev_lower is None

    def test_initial_strategy_has_none_hold_state(self):
        strategy = _make_fresh_strategy(hold_days=3)
        state = extract_buffer_state(strategy)
        assert state.hold_state is None

    def test_initial_meta_fields_are_defaults(self):
        strategy = _make_fresh_strategy()
        state = extract_buffer_state(strategy)
        assert state.last_buy_buffer_pct == pytest.approx(0.0)
        assert state.last_hold_days_used == 0

    def test_schema_version_is_one(self):
        strategy = _make_fresh_strategy()
        state = extract_buffer_state(strategy)
        assert state.schema_version == 1

    def test_extract_after_running_updates_bands(self):
        """strategy 를 구동하면 내부 prev 밴드가 None 에서 벗어난다."""
        strategy = _make_fresh_strategy()
        _run_strategy_for_a_few_days(strategy, n_days=5)
        state = extract_buffer_state(strategy)
        assert state.prev_upper is not None
        assert state.prev_lower is not None
        # ma=100, buy=3%, sell=5% → upper=103, lower=95
        assert state.prev_upper == pytest.approx(103.0)
        assert state.prev_lower == pytest.approx(95.0)

    def test_returns_buffer_zone_state_instance(self):
        strategy = _make_fresh_strategy()
        state = extract_buffer_state(strategy)
        assert isinstance(state, BufferZoneState)


# ============================================================================
# restore_buffer_state
# ============================================================================


class TestRestoreBufferState:
    def test_restore_none_hold_state_t_4_1(self):
        """T-4.1: hold_state 없는 상태 왕복 → 원본과 일치."""
        # Given
        source = _make_fresh_strategy()
        _run_strategy_for_a_few_days(source, n_days=5)
        saved = extract_buffer_state(source)
        assert saved.hold_state is None  # 전제 확인

        # When: 새 strategy 에 restore
        target = _make_fresh_strategy()
        restore_buffer_state(target, saved)
        restored = extract_buffer_state(target)

        # Then
        assert restored.prev_upper == pytest.approx(saved.prev_upper)
        assert restored.prev_lower == pytest.approx(saved.prev_lower)
        assert restored.hold_state is None
        assert restored.last_buy_buffer_pct == pytest.approx(saved.last_buy_buffer_pct)
        assert restored.last_hold_days_used == saved.last_hold_days_used

    def test_restore_with_hold_state_t_4_2(self):
        """T-4.2: hold_state 있는 상태 왕복."""
        # Given
        hold_state: HoldState = {
            "start_date": date(2026, 4, 5),
            "days_passed": 2,
            "buffer_pct": 0.03,
            "hold_days_required": 3,
        }
        source_state = BufferZoneState(
            prev_upper=103.0,
            prev_lower=95.0,
            hold_state=hold_state,
            last_buy_buffer_pct=0.03,
            last_hold_days_used=3,
        )

        # When
        strategy = _make_fresh_strategy(hold_days=3)
        restore_buffer_state(strategy, source_state)
        restored = extract_buffer_state(strategy)

        # Then
        assert restored.prev_upper == pytest.approx(103.0)
        assert restored.prev_lower == pytest.approx(95.0)
        assert restored.hold_state is not None
        assert restored.hold_state["start_date"] == date(2026, 4, 5)
        assert restored.hold_state["days_passed"] == 2
        assert restored.hold_state["buffer_pct"] == pytest.approx(0.03)
        assert restored.hold_state["hold_days_required"] == 3
        assert restored.last_buy_buffer_pct == pytest.approx(0.03)
        assert restored.last_hold_days_used == 3

    def test_restore_all_private_fields_t_4_3(self):
        """T-4.3: 모든 private 변수 왕복 검증.

        Given: 수동으로 모든 필드에 non-default 값을 설정한 BufferZoneState.
        When : fresh strategy 에 restore → 다시 extract.
        Then : 5 개 private 필드가 원본과 정확히 일치.
        """
        # Given
        hold_state: HoldState = {
            "start_date": date(2026, 3, 15),
            "days_passed": 1,
            "buffer_pct": 0.025,
            "hold_days_required": 5,
        }
        expected = BufferZoneState(
            prev_upper=120.5,
            prev_lower=88.25,
            hold_state=hold_state,
            last_buy_buffer_pct=0.025,
            last_hold_days_used=5,
        )

        # When
        strategy = _make_fresh_strategy(hold_days=5)
        restore_buffer_state(strategy, expected)
        actual = extract_buffer_state(strategy)

        # Then
        assert actual.prev_upper == pytest.approx(expected.prev_upper)
        assert actual.prev_lower == pytest.approx(expected.prev_lower)
        assert actual.hold_state == expected.hold_state
        assert actual.last_buy_buffer_pct == pytest.approx(expected.last_buy_buffer_pct)
        assert actual.last_hold_days_used == expected.last_hold_days_used

    def test_restore_mutates_strategy_in_place(self):
        """restore 는 동일 strategy 객체의 내부 상태를 변경한다 (새 객체 반환 없음)."""
        strategy = _make_fresh_strategy()
        obj_id_before = id(strategy)

        target_state = BufferZoneState(
            prev_upper=110.0,
            prev_lower=90.0,
            hold_state=None,
            last_buy_buffer_pct=0.03,
            last_hold_days_used=0,
        )
        restore_buffer_state(strategy, target_state)

        assert id(strategy) == obj_id_before  # 동일 객체
        extracted = extract_buffer_state(strategy)
        assert extracted.prev_upper == pytest.approx(110.0)

    def test_restore_does_not_change_constructor_params(self):
        """restore 는 _ma_col, _buy_buffer_pct 등 생성자 파라미터를 건드리지 않는다."""
        strategy = BufferZoneStrategy(
            ma_col="ma_200",
            buy_buffer_pct=0.03,
            sell_buffer_pct=0.05,
            hold_days=3,
        )
        state = BufferZoneState(
            prev_upper=100.0,
            prev_lower=80.0,
            hold_state=None,
            last_buy_buffer_pct=0.99,  # 의도적으로 다른 값
            last_hold_days_used=99,
        )
        restore_buffer_state(strategy, state)

        # 생성자 파라미터 불변 확인 (SSoT: BufferZoneStrategy)
        assert strategy._ma_col == "ma_200"
        assert strategy._buy_buffer_pct == pytest.approx(0.03)
        assert strategy._sell_buffer_pct == pytest.approx(0.05)
        assert strategy._hold_days == 3

    def test_restore_rejects_unknown_schema_version(self):
        """schema_version 불일치 시 ValueError."""
        strategy = _make_fresh_strategy()
        bad_state = BufferZoneState(
            prev_upper=None,
            prev_lower=None,
            hold_state=None,
            last_buy_buffer_pct=0.0,
            last_hold_days_used=0,
            schema_version=999,
        )
        with pytest.raises(ValueError, match="schema_version"):
            restore_buffer_state(strategy, bad_state)


# ============================================================================
# extract → restore roundtrip
# ============================================================================


class TestRoundtrip:
    def test_extract_restore_identity(self):
        """A = extract(s1); restore(s2, A); B = extract(s2); A == B."""
        source = _make_fresh_strategy()
        _run_strategy_for_a_few_days(source, n_days=5)
        a = extract_buffer_state(source)

        target = _make_fresh_strategy()
        restore_buffer_state(target, a)
        b = extract_buffer_state(target)

        assert a == b

    def test_roundtrip_via_live_state_json(self, tmp_path):
        """state.py 의 save/load 파이프라인을 경유한 통합 왕복.

        LiveState 안의 buffer_zone_state 로 저장 → load 후 strategy 복원 → extract → 원본과 일치.
        """
        from live.state import create_initial_state, load_state, save_state

        # Given: 실제 strategy 구동 후 상태 추출
        source = _make_fresh_strategy()
        _run_strategy_for_a_few_days(source, n_days=5)
        extracted = extract_buffer_state(source)

        live_state = create_initial_state(100_000_000.0)
        live_state.assets["sso"].buffer_zone_state = extracted

        path = tmp_path / "live_state.json"
        save_state(live_state, path)
        loaded = load_state(path)
        loaded_bzs = loaded.assets["sso"].buffer_zone_state

        # When: 새 strategy 생성 후 restore
        assert loaded_bzs is not None
        target = _make_fresh_strategy()
        restore_buffer_state(target, loaded_bzs)
        re_extracted = extract_buffer_state(target)

        # Then
        assert re_extracted.prev_upper == pytest.approx(extracted.prev_upper)
        assert re_extracted.prev_lower == pytest.approx(extracted.prev_lower)
        assert re_extracted.last_buy_buffer_pct == pytest.approx(extracted.last_buy_buffer_pct)
        assert re_extracted.last_hold_days_used == extracted.last_hold_days_used


class TestGetCurrentBands:
    """get_current_bands 는 strategy 의 현재 내부 밴드 상태를 그대로 반환한다."""

    def test_initial_strategy_returns_none_bands(self):
        """Given 새 전략 When get_current_bands Then (None, None)."""
        strategy = _make_fresh_strategy()
        upper, lower = get_current_bands(strategy)
        assert upper is None
        assert lower is None

    def test_bands_match_prev_upper_lower_after_check(self):
        """Given 전략을 며칠 구동 When get_current_bands Then extract 결과와 동일."""
        strategy = _make_fresh_strategy()
        _run_strategy_for_a_few_days(strategy)

        upper, lower = get_current_bands(strategy)
        extracted = extract_buffer_state(strategy)

        assert upper == pytest.approx(extracted.prev_upper)
        assert lower == pytest.approx(extracted.prev_lower)
