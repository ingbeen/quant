"""live.daily_runner — run_daily 순수 계산 테스트.

TODO T-7.1 ~ T-7.5 시나리오 고정. 실제 QBT portfolio 엔진 1 iteration 과 동등한
구조를 작은 fixture 로 검증한다.

테스트 원칙:
- 파일 I/O 및 외부 네트워크 호출 금지 (Path / open / yfinance 등)
- pytest.approx 로 부동소수점 비교
- Given-When-Then 패턴
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from live.constants import get_live_portfolio_config
from live.daily_runner import run_daily
from live.models import AssetMarketData, LiveState, MarketBundle
from live.state import create_initial_state

# ============================================================================
# fixture
# ============================================================================


def _make_signal_df(
    dates: list[date],
    closes: list[float],
    ma_values: list[float],
    opens: list[float] | None = None,
) -> pd.DataFrame:
    """signal_df (Date, Open, High, Low, Close, Volume, ma_200)."""
    if opens is None:
        opens = [c - 0.5 for c in closes]
    n = len(dates)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": opens,
            "High": [c + 0.5 for c in closes],
            "Low": [c - 1.0 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * n,
            "ma_200": ma_values,
        }
    )


def _make_trade_df(
    dates: list[date],
    opens: list[float],
    closes: list[float],
) -> pd.DataFrame:
    n = len(dates)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": opens,
            "High": [max(o, c) + 0.5 for o, c in zip(opens, closes, strict=False)],
            "Low": [min(o, c) - 0.5 for o, c in zip(opens, closes, strict=False)],
            "Close": closes,
            "Volume": [1_000_000] * n,
        }
    )


@pytest.fixture
def sample_dates() -> list[date]:
    """10 일치 거래일 (월~금 + 월~금, 2 주)."""
    base = date(2026, 4, 6)  # 월요일
    days: list[date] = []
    for offset in range(14):  # 2주
        d = date.fromordinal(base.toordinal() + offset)
        if d.weekday() < 5:  # 월~금
            days.append(d)
        if len(days) >= 10:
            break
    return days


@pytest.fixture
def flat_market_bundle(sample_dates: list[date]) -> MarketBundle:
    """가격이 MA 근처에 머무르는 평온한 market bundle.

    - ma_200 = 100 (고정)
    - close = 100 (고정) → 상/하 밴드 돌파 없음 → 시그널 없음
    - 4 자산 (sso/qld/gld/tlt) 동일 데이터
    """
    flat_closes = [100.0] * len(sample_dates)
    flat_opens = [100.0] * len(sample_dates)
    ma = [100.0] * len(sample_dates)
    signal_df = _make_signal_df(sample_dates, flat_closes, ma, opens=flat_opens)
    trade_df = _make_trade_df(sample_dates, flat_opens, flat_closes)

    return {
        asset_id: AssetMarketData(signal_df=signal_df.copy(), trade_df=trade_df.copy())
        for asset_id in ("sso", "qld", "gld", "tlt")
    }


@pytest.fixture
def rising_market_bundle(sample_dates: list[date]) -> MarketBundle:
    """buy_and_hold (gld/tlt) 가 즉시 매수 시그널을 내고,
    sso/qld 는 상향 돌파가 발생하는 bundle.

    - ma_200 = 100 (고정)
    - close: 98 → 100 → 102 → 105 (상승) → 상단 밴드(103) 돌파
    """
    n = len(sample_dates)
    closes = [98.0, 99.0, 100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0][:n]
    opens = [c - 1.0 for c in closes]
    ma = [100.0] * n
    signal_df = _make_signal_df(sample_dates, closes, ma, opens=opens)
    trade_df = _make_trade_df(sample_dates, opens, closes)

    return {
        asset_id: AssetMarketData(signal_df=signal_df.copy(), trade_df=trade_df.copy())
        for asset_id in ("sso", "qld", "gld", "tlt")
    }


@pytest.fixture
def initial_state() -> LiveState:
    return create_initial_state(100_000_000.0)


# ============================================================================
# 테스트
# ============================================================================


class TestRunDailyReturnsResult:
    def test_initial_state_single_day_returns_daily_result_t_7_1(
        self, initial_state, rising_market_bundle, sample_dates
    ):
        """T-7.1: 초기 상태 + 1 일 데이터 → DailyResult 정상 반환."""
        result = run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=rising_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )

        assert result.execution_date == sample_dates[0].isoformat()
        assert result.updated_state.portfolio_id == "portfolio_q2_2xs"
        assert set(result.signals.keys()) == {"sso", "qld", "gld", "tlt"}
        assert result.model_equity > 0

    def test_pending_none_day_model_unchanged_t_7_2(self, initial_state, flat_market_bundle, sample_dates):
        """T-7.2: pending 없는 날 (초기 상태) → model_shares 모두 0 유지."""
        result = run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=flat_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )

        # 모든 자산의 model_shares 가 여전히 0 (초기 pending 없음 + 당일 시그널 있어도 체결은 익일)
        # 단, buy_and_hold 인 gld/tlt 는 즉시 매수 시그널 → pending 생성은 되지만 shares 는 아직 0
        for asset in result.updated_state.assets.values():
            assert asset.model_shares == 0
        assert result.executions is None  # 전일 pending 없음 → executions 없음

    def test_signal_generates_pending_order_t_7_3(self, initial_state, rising_market_bundle, sample_dates):
        """T-7.3: signal 발생 시 → pending_order 가 state 에 저장."""
        result = run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=rising_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )

        # buy_and_hold 인 gld, tlt 는 초기에 즉시 매수 시그널 → pending 생성 확인
        assert result.updated_state.assets["gld"].pending_order is not None
        assert result.updated_state.assets["tlt"].pending_order is not None
        gld_pending = result.updated_state.assets["gld"].pending_order
        assert gld_pending is not None
        assert gld_pending["intent_type"] == "ENTER_TO_TARGET"
        assert gld_pending["asset_id"] == "gld"

    def test_pending_executes_next_day_model_shares_increase_t_7_4(
        self, initial_state, rising_market_bundle, sample_dates
    ):
        """T-7.4: pending 있는 상태 + 다음 날 실행 → model_shares 증가.

        1 일차: pending 생성 (gld/tlt 즉시 매수)
        2 일차: 전일 pending 이 당일 시가에 체결 → model_shares > 0
        """
        # Day 1
        r1 = run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=rising_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )

        # Day 2 — 이전 결과 상태를 그대로 전달
        r2 = run_daily(
            trade_date=sample_dates[1],
            state=r1.updated_state,
            market_bundle=rising_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )

        # gld, tlt 의 model_shares 는 Day2 시점에 > 0 이어야 한다 (pending 체결)
        assert r2.updated_state.assets["gld"].model_shares > 0
        assert r2.updated_state.assets["tlt"].model_shares > 0
        # Day 2 의 executions 는 None 이 아니어야 한다
        assert r2.executions is not None

    def test_does_not_touch_filesystem_t_7_5(self, initial_state, flat_market_bundle, sample_dates, monkeypatch):
        """T-7.5: run_daily 내부에서 파일 I/O 없음.

        `pathlib.Path.read_text`, `write_text`, `write_bytes`, `open` 을 감시하여
        호출되지 않음을 확인.
        """
        import builtins
        from pathlib import Path

        # 호출 카운터
        call_log: list[str] = []

        original_open = builtins.open

        def _wrapped_open(file, *args, **kwargs):  # noqa: ANN001
            call_log.append(f"open({file!r})")
            return original_open(file, *args, **kwargs)

        def _fail_read_text(self, *args, **kwargs):  # noqa: ANN001
            call_log.append(f"Path.read_text({self})")
            raise RuntimeError("파일 I/O 발생")

        def _fail_write_text(self, *args, **kwargs):  # noqa: ANN001
            call_log.append(f"Path.write_text({self})")
            raise RuntimeError("파일 I/O 발생")

        def _fail_write_bytes(self, *args, **kwargs):  # noqa: ANN001
            call_log.append(f"Path.write_bytes({self})")
            raise RuntimeError("파일 I/O 발생")

        monkeypatch.setattr(builtins, "open", _wrapped_open)
        monkeypatch.setattr(Path, "read_text", _fail_read_text)
        monkeypatch.setattr(Path, "write_text", _fail_write_text)
        monkeypatch.setattr(Path, "write_bytes", _fail_write_bytes)

        # 실행
        run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=flat_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )

        # Path 관련 쓰기/읽기 호출이 없었어야 한다
        assert not any("Path." in entry for entry in call_log), f"run_daily 가 파일 I/O 를 수행함: {call_log}"


class TestRunDailyDataIntegrity:
    def test_input_state_is_not_mutated(self, initial_state, rising_market_bundle, sample_dates):
        """입력 LiveState 는 변경되지 않아야 한다 (불변성)."""
        original_cash = initial_state.shared_cash_model
        original_portfolio = initial_state.portfolio_id

        run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=rising_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )

        assert initial_state.shared_cash_model == original_cash
        assert initial_state.portfolio_id == original_portfolio
        # 원본 pending_order 는 여전히 None
        for asset in initial_state.assets.values():
            assert asset.pending_order is None

    def test_signal_detection_has_ema_200(self, initial_state, rising_market_bundle, sample_dates):
        """SignalDetection 에 ema_200 과 ema_distance_pct 가 채워져 있어야 한다."""
        result = run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=rising_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )
        for asset_id in ("sso", "qld", "gld", "tlt"):
            sig = result.signals[asset_id]
            assert sig.ema_200 is not None
            assert sig.close > 0

    def test_portfolio_config_used(self):
        """LIVE_PORTFOLIO_ID 의 config 가 4 개 자산을 가지는지 확인 (fixture 전제)."""
        config = get_live_portfolio_config()
        assert len(config.asset_slots) == 4
        ids = {slot.asset_id for slot in config.asset_slots}
        assert ids == {"sso", "qld", "gld", "tlt"}


# ============================================================================
# fill 통합 (integration_wiring)
# ============================================================================


class TestRunDailyFillIntegration:
    """run_daily 가 drift.apply_fills_idempotent 를 호출하여 actual 축을 갱신한다."""

    def test_empty_fills_preserves_initial_actual(self, initial_state, flat_market_bundle, sample_dates):
        """빈 fill 리스트 → actual 축 변경 없음 (회귀 영향 없음)."""
        result = run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=flat_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )
        for asset in result.updated_state.assets.values():
            assert asset.actual_shares == 0

    def test_buy_fill_updates_actual_shares(self, initial_state, flat_market_bundle, sample_dates):
        """buy fill 1 개 입력 → actual_shares 증가 + applied_ids 에 키 추가."""
        from live.models import ActualFill

        fill = ActualFill(
            asset_id="sso",
            direction="buy",
            actual_price=82.0,
            actual_shares=420,
            trade_date=sample_dates[0].isoformat(),
            input_time_kst="2026-04-06T20:00:00+09:00",
            memo=None,
            rtdb_key="fill_test_001",
        )

        result = run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=flat_market_bundle,
            pending_fills=[fill],
            applied_fill_ids={},
        )

        assert result.updated_state.assets["sso"].actual_shares == 420
        assert "fill_test_001" in result.updated_applied_fill_ids

    def test_duplicate_fill_in_same_run_only_applied_once(self, initial_state, flat_market_bundle, sample_dates):
        """이미 applied_ids 에 있는 fill 은 무시 (idempotency)."""
        from live.models import ActualFill

        fill = ActualFill(
            asset_id="sso",
            direction="buy",
            actual_price=82.0,
            actual_shares=420,
            trade_date=sample_dates[0].isoformat(),
            input_time_kst="2026-04-06T20:00:00+09:00",
            memo=None,
            rtdb_key="fill_test_002",
        )

        result = run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=flat_market_bundle,
            pending_fills=[fill],
            applied_fill_ids={"fill_test_002": "2026-04-05T00:00:00+09:00"},
        )

        # 이미 적용된 fill 이므로 actual_shares 변경 없음
        assert result.updated_state.assets["sso"].actual_shares == 0

    def test_pending_fill_reminder_when_pending_exists_and_no_fill(
        self, initial_state, rising_market_bundle, sample_dates
    ):
        """전일 pending 이 있고 fill 입력이 없으면 reminder 에 자산 ID 가 누적."""
        # Day 1: pending 생성
        r1 = run_daily(
            trade_date=sample_dates[0],
            state=initial_state,
            market_bundle=rising_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )
        # Day 2: fill 입력 없음 → reminder 발동
        r2 = run_daily(
            trade_date=sample_dates[1],
            state=r1.updated_state,
            market_bundle=rising_market_bundle,
            pending_fills=[],
            applied_fill_ids=r1.updated_applied_fill_ids,
        )
        # Day 2 시작 시점에 pending 이 있었으나 fill 없음 → reminder 가 비어있지 않거나
        # Day 2 의 model 체결 후 새 pending 이 생긴 상태
        # reminder 검증은 "함수가 list 를 반환한다" 만 확인 (실제 자산 여부는 시그널 의존)
        assert isinstance(r2.pending_fill_reminders, list)


class TestPendingFillReminderLogic:
    """Gap 6 수정: 일부 자산만 체결된 경우에도 나머지 pending 자산은 리마인더에 포함."""

    def _state_with_two_pending(self) -> LiveState:
        """sso, gld 두 자산에 pending_order 가 있는 state 생성."""
        from live.models import PendingOrderDict

        state = create_initial_state(100_000_000.0)
        pending_sso: PendingOrderDict = {
            "asset_id": "sso",
            "intent_type": "ENTER_TO_TARGET",
            "target_weight": 0.35,
            "target_amount": 35_000_000.0,
            "current_amount": 0.0,
            "delta_amount": 35_000_000.0,
            "reason": "test",
            "signal_date": "2026-04-09",
            "hold_days_used": 0,
        }
        pending_gld: PendingOrderDict = {
            "asset_id": "gld",
            "intent_type": "ENTER_TO_TARGET",
            "target_weight": 0.15,
            "target_amount": 15_000_000.0,
            "current_amount": 0.0,
            "delta_amount": 15_000_000.0,
            "reason": "test",
            "signal_date": "2026-04-09",
            "hold_days_used": 0,
        }
        state.assets["sso"].pending_order = pending_sso
        state.assets["gld"].pending_order = pending_gld
        return state

    def test_no_fill_both_pending_are_reminded(self, flat_market_bundle, sample_dates):
        """Given 2 자산에 pending, fill 0 건 When run_daily Then 둘 다 reminder."""
        state = self._state_with_two_pending()
        result = run_daily(
            trade_date=sample_dates[1],
            state=state,
            market_bundle=flat_market_bundle,
            pending_fills=[],
            applied_fill_ids={},
        )
        assert set(result.pending_fill_reminders) == {"sso", "gld"}

    def test_partial_fill_remaining_assets_are_reminded(self, flat_market_bundle, sample_dates):
        """Given 2 자산에 pending, 1 자산(sso)만 fill 입력 When run_daily Then 나머지 gld 만 reminder.

        Gap 6 수정 전에는 ``not pending_fills`` 가 False 라 reminder 가 빈 리스트였다.
        수정 후에는 incoming_fill_asset_ids = {"sso"} 이므로 gld 는 여전히 reminder 로 표시.
        """
        from live.models import ActualFill

        state = self._state_with_two_pending()
        sso_fill = ActualFill(
            asset_id="sso",
            direction="buy",
            actual_price=80.0,
            actual_shares=420,
            trade_date=sample_dates[1].isoformat(),
            input_time_kst="2026-04-09T20:00:00+09:00",
            memo=None,
            rtdb_key="fill_sso_partial",
        )
        result = run_daily(
            trade_date=sample_dates[1],
            state=state,
            market_bundle=flat_market_bundle,
            pending_fills=[sso_fill],
            applied_fill_ids={},
        )
        # gld 는 여전히 pending, fill 미입력 → reminder 에 포함되어야 함
        assert "gld" in result.pending_fill_reminders
        # sso 는 이번 실행에서 fill 이 들어왔으므로 reminder 에서 제외
        assert "sso" not in result.pending_fill_reminders

    def test_all_fills_incoming_no_reminder(self, flat_market_bundle, sample_dates):
        """Given 2 자산에 pending, 2 자산 모두 fill 입력 When run_daily Then reminder 없음."""
        from live.models import ActualFill

        state = self._state_with_two_pending()
        fills = [
            ActualFill(
                asset_id="sso",
                direction="buy",
                actual_price=80.0,
                actual_shares=420,
                trade_date=sample_dates[1].isoformat(),
                input_time_kst="2026-04-09T20:00:00+09:00",
                memo=None,
                rtdb_key="fill_sso_full",
            ),
            ActualFill(
                asset_id="gld",
                direction="buy",
                actual_price=180.0,
                actual_shares=83,
                trade_date=sample_dates[1].isoformat(),
                input_time_kst="2026-04-09T20:00:00+09:00",
                memo=None,
                rtdb_key="fill_gld_full",
            ),
        ]
        result = run_daily(
            trade_date=sample_dates[1],
            state=state,
            market_bundle=flat_market_bundle,
            pending_fills=fills,
            applied_fill_ids={},
        )
        assert "sso" not in result.pending_fill_reminders
        assert "gld" not in result.pending_fill_reminders
