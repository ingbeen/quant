"""live.rtdb_gateway — Firebase Admin SDK mock 기반 테스트.

Firebase 실제 호출 없이 ``firebase_admin.db.reference`` 를 monkeypatch 로 대체하여
RTDB 진입점 호출 시그니처와 페이로드 구조를 검증한다.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from live import rtdb_gateway as rtdb_module
from live.models import (
    ActualFill,
    ChartSeries,
    DailyResult,
    DriftReport,
    SignalDetection,
)
from live.rtdb_gateway import (
    fetch_pending_balance_adjusts,
    fetch_unprocessed_fills,
    mark_balance_adjusts_processed,
    mark_fills_processed,
    read_device_tokens,
    remove_invalid_tokens,
    write_chart_data,
    write_read_model,
)
from live.state import create_initial_state

# ============================================================================
# RefStore — 경로 → mock reference 매핑
# ============================================================================


class _MockRef:
    """firebase_admin.db.reference 가 반환하는 객체의 mock."""

    def __init__(self, path: str, store: dict[str, Any]) -> None:
        self.path = path
        self.store = store

    def get(self) -> Any:
        return self.store.get(self.path)

    def set(self, value: Any) -> None:
        self.store[self.path] = value

    def update(self, value: dict[str, Any]) -> None:
        existing = self.store.get(self.path)
        if isinstance(existing, dict):
            existing.update(value)
            self.store[self.path] = existing
        else:
            self.store[self.path] = dict(value)

    def delete(self) -> None:
        self.store.pop(self.path, None)


@pytest.fixture
def mock_db(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """firebase_admin.db.reference 를 in-memory store 로 대체한다."""
    store: dict[str, Any] = {}
    monkeypatch.setattr(rtdb_module, "_db_reference", lambda app, path: _MockRef(path, store))
    return store


@pytest.fixture
def mock_app() -> MagicMock:
    return MagicMock(name="firebase_app")


# ============================================================================
# fetch_unprocessed_fills
# ============================================================================


class TestFetchUnprocessedFills:
    def test_returns_only_unprocessed(self, mock_db, mock_app):
        mock_db["/fills/inbox"] = {
            "fill_a": {
                "asset_id": "sso",
                "direction": "buy",
                "actual_price": 82.0,
                "actual_shares": 100,
                "trade_date": "2026-04-10",
                "input_time_kst": "2026-04-10T20:00:00+09:00",
                "memo": None,
                "processed": False,
            },
            "fill_b": {
                "asset_id": "qld",
                "direction": "sell",
                "actual_price": 90.0,
                "actual_shares": 50,
                "trade_date": "2026-04-10",
                "input_time_kst": "2026-04-10T21:00:00+09:00",
                "memo": "test",
                "processed": True,  # 이미 처리됨
            },
        }

        fills = fetch_unprocessed_fills(mock_app)
        assert len(fills) == 1
        assert fills[0].rtdb_key == "fill_a"
        assert fills[0].asset_id == "sso"

    def test_empty_inbox_returns_empty_list(self, mock_db, mock_app):
        fills = fetch_unprocessed_fills(mock_app)
        assert fills == []

    def test_invalid_root_type_returns_empty(self, mock_db, mock_app):
        mock_db["/fills/inbox"] = "not a dict"
        assert fetch_unprocessed_fills(mock_app) == []


# ============================================================================
# mark_fills_processed
# ============================================================================


class TestMarkFillsProcessed:
    def test_marks_each_key_processed(self, mock_db, mock_app):
        mock_db["/fills/inbox/fill_a"] = {"processed": False, "asset_id": "sso"}
        mock_db["/fills/inbox/fill_b"] = {"processed": False, "asset_id": "qld"}

        mark_fills_processed(mock_app, ["fill_a", "fill_b"])

        assert mock_db["/fills/inbox/fill_a"]["processed"] is True
        assert mock_db["/fills/inbox/fill_b"]["processed"] is True

    def test_empty_keys_is_noop(self, mock_db, mock_app):
        mark_fills_processed(mock_app, [])
        assert mock_db == {}


# ============================================================================
# balance_adjust RTDB 경로
# ============================================================================


class TestFetchPendingBalanceAdjusts:
    def test_returns_only_unprocessed(self, mock_db, mock_app):
        mock_db["/balance_adjust/inbox"] = {
            "adj_a": {
                "asset_id": "sso",
                "new_shares": 420,
                "new_cash": None,
                "reason": "년초 잔고 조정",
                "input_time_kst": "2026-04-10T20:00:00+09:00",
                "processed": False,
            },
            "adj_b": {
                "asset_id": None,
                "new_shares": None,
                "new_cash": 95000000.0,
                "reason": "cash 보정",
                "input_time_kst": "2026-04-10T21:00:00+09:00",
                "processed": True,  # 이미 처리됨
            },
        }

        adjusts = fetch_pending_balance_adjusts(mock_app)
        assert len(adjusts) == 1
        assert adjusts[0].rtdb_key == "adj_a"
        assert adjusts[0].asset_id == "sso"
        assert adjusts[0].new_shares == 420
        assert adjusts[0].new_cash is None

    def test_cash_only_adjust(self, mock_db, mock_app):
        mock_db["/balance_adjust/inbox"] = {
            "adj_cash": {
                "asset_id": None,
                "new_shares": None,
                "new_cash": 85000000.0,
                "reason": "배당 반영",
                "input_time_kst": "2026-04-10T22:00:00+09:00",
                "processed": False,
            },
        }
        adjusts = fetch_pending_balance_adjusts(mock_app)
        assert len(adjusts) == 1
        assert adjusts[0].asset_id is None
        assert adjusts[0].new_cash == 85000000.0

    def test_empty_inbox_returns_empty(self, mock_db, mock_app):
        assert fetch_pending_balance_adjusts(mock_app) == []


class TestMarkBalanceAdjustsProcessed:
    def test_marks_each_key_processed(self, mock_db, mock_app):
        mock_db["/balance_adjust/inbox/adj_a"] = {"processed": False, "asset_id": "sso"}
        mock_db["/balance_adjust/inbox/adj_b"] = {"processed": False, "asset_id": "gld"}

        mark_balance_adjusts_processed(mock_app, ["adj_a", "adj_b"])

        assert mock_db["/balance_adjust/inbox/adj_a"]["processed"] is True
        assert mock_db["/balance_adjust/inbox/adj_b"]["processed"] is True

    def test_empty_keys_is_noop(self, mock_db, mock_app):
        mark_balance_adjusts_processed(mock_app, [])
        assert mock_db == {}


# ============================================================================
# write_read_model
# ============================================================================


class TestWriteReadModel:
    def test_writes_portfolio_signals_pending_drift_history(self, mock_db, mock_app):
        state = create_initial_state(100_000_000.0)
        state.assets["sso"].model_shares = 100
        state.assets["sso"].pending_order = {
            "asset_id": "sso",
            "intent_type": "ENTER_TO_TARGET",
            "signal_date": "2026-04-10",
            "current_amount": 0.0,
            "target_amount": 35_000_000.0,
            "delta_amount": 35_000_000.0,
            "target_weight": 0.35,
            "hold_days_used": 3,
            "reason": "test",
        }

        result = DailyResult(
            execution_date="2026-04-10",
            updated_state=state,
            updated_applied_fill_ids={},
            updated_applied_balance_adjust_ids={},
            signals={
                "sso": SignalDetection(
                    state="buy",
                    close=420.0,
                    upper_band=418.0,
                    lower_band=398.0,
                    ma_value=410.0,
                    ma_distance_pct=0.0244,
                ),
            },
            order_intents={},
            executions=None,
            rebalance_triggered=False,
            model_equity=100_000_000.0,
            actual_equity=100_000_000.0,
            drift_pct=0.0,
            drift_report=DriftReport(
                model_equity=100_000_000.0,
                actual_equity=100_000_000.0,
                drift_pct=0.0,
                per_asset={},
                recommendation="정상",
            ),
            ma_distances={"sso": 0.0244},
            notification_body="test",
            pending_fill_reminders=[],
        )

        write_read_model(mock_app, state, result)

        assert "/latest/portfolio" in mock_db
        assert mock_db["/latest/portfolio"]["execution_date"] == "2026-04-10"
        assert mock_db["/latest/portfolio"]["assets"]["sso"]["model_shares"] == 100

        assert "/latest/signals" in mock_db
        assert mock_db["/latest/signals"]["sso"]["state"] == "buy"

        assert "/latest/pending_orders" in mock_db
        assert "sso" in mock_db["/latest/pending_orders"]

        assert "/latest/drift" in mock_db
        assert mock_db["/latest/drift"]["drift_pct"] == 0.0

        assert "/history/summary/2026-04-10" in mock_db


# ============================================================================
# write_chart_data
# ============================================================================


class TestWriteChartData:
    def test_writes_each_asset_chart_series(self, mock_db, mock_app):
        chart = ChartSeries(
            dates=["2026-04-08", "2026-04-09"],
            close=[100.0, 101.0],
            ma_value=[99.5, 99.6],
            upper_band=[102.0, 102.1],
            lower_band=[97.0, 97.1],
            buy_signals=[],
            sell_signals=[],
            user_buys=[],
            user_sells=[],
        )
        write_chart_data(mock_app, {"sso": chart, "qld": chart})

        assert "/latest/chart_data/sso" in mock_db
        assert "/latest/chart_data/qld" in mock_db
        assert mock_db["/latest/chart_data/sso"]["close"] == [100.0, 101.0]


# ============================================================================
# device_tokens
# ============================================================================


class TestDeviceTokens:
    def test_read_device_tokens_string_values(self, mock_db, mock_app):
        mock_db["/device_tokens"] = {
            "device_1": "token_aaa",
            "device_2": "token_bbb",
        }
        tokens = read_device_tokens(mock_app)
        assert set(tokens) == {"token_aaa", "token_bbb"}

    def test_read_device_tokens_dict_values(self, mock_db, mock_app):
        mock_db["/device_tokens"] = {
            "device_1": {"token": "token_x", "registered_at": "2026-04-01"},
        }
        tokens = read_device_tokens(mock_app)
        assert tokens == ["token_x"]

    def test_read_device_tokens_empty(self, mock_db, mock_app):
        assert read_device_tokens(mock_app) == []

    def test_remove_invalid_tokens_deletes_matching(self, mock_db, mock_app):
        mock_db["/device_tokens"] = {
            "device_1": "token_keep",
            "device_2": "token_invalid",
        }
        remove_invalid_tokens(mock_app, ["token_invalid"])

        assert "/device_tokens/device_2" not in mock_db

    def test_remove_invalid_empty_list_is_noop(self, mock_db, mock_app):
        mock_db["/device_tokens"] = {"device_1": "tok"}
        remove_invalid_tokens(mock_app, [])
        assert "/device_tokens" in mock_db


# ============================================================================
# helper smoke
# ============================================================================


class TestHelpers:
    def test_dict_to_actual_fill_minimum_fields(self):
        from live.rtdb_gateway import _dict_to_actual_fill

        fill = _dict_to_actual_fill(
            {
                "asset_id": "sso",
                "direction": "buy",
                "actual_price": 80.5,
                "actual_shares": 100,
                "trade_date": "2026-04-10",
                "input_time_kst": "2026-04-10T20:00:00+09:00",
            },
            rtdb_key="fill_xyz",
        )
        assert isinstance(fill, ActualFill)
        assert fill.asset_id == "sso"
        assert fill.actual_shares == 100
        assert fill.rtdb_key == "fill_xyz"
