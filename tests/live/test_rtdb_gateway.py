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
    ChartMeta,
    ChartSeries,
    DailyResult,
    DriftReport,
    EquityChartMeta,
    EquityChartSeries,
    SignalDetection,
)
from live.rtdb_gateway import (
    delete_all_except_device_tokens,
    fetch_pending_balance_adjusts,
    fetch_unprocessed_fills,
    mark_balance_adjusts_processed,
    mark_fills_processed,
    read_device_tokens,
    remove_invalid_tokens,
    write_chart_archive_year,
    write_chart_meta,
    write_chart_recent,
    write_equity_archive_year,
    write_equity_meta,
    write_equity_recent,
    write_read_model,
)
from live.state import create_initial_state

# ============================================================================
# RefStore — 경로 → mock reference 매핑
# ============================================================================


class _MockRef:
    """firebase_admin.db.reference 가 반환하는 객체의 mock.

    ``get()`` 은 RTDB 의 계층적 읽기를 느슨하게 흉내낸다:

    1. 정확히 해당 경로에 값이 저장되어 있으면 그 값을 반환.
    2. 그렇지 않으면 ``{path}/...`` 하위 경로들을 스캔하여 **즉시 자식** 을
       dict 로 묶어 반환한다. 자식이 하나도 없으면 ``None``.

    실제 Firebase RTDB 의 트리 구조 동작을 단순화한 모방이다.
    """

    def __init__(self, path: str, store: dict[str, Any]) -> None:
        self.path = path
        self.store = store

    def get(self) -> Any:
        if self.path in self.store:
            return self.store[self.path]
        prefix = self.path + "/"
        children: dict[str, Any] = {}
        for key, value in self.store.items():
            if not key.startswith(prefix):
                continue
            remainder = key[len(prefix) :]
            if "/" in remainder:
                continue
            children[remainder] = value
        return children if children else None

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
    def test_writes_portfolio_signals_pending(self, mock_db, mock_app):
        """write_read_model 은 `/latest/portfolio|signals|pending_orders` 3 경로만 쓴다.

        ``/history/summary/{date}`` 쓰기는 PLAN_LIVE_CHARTS_RESTRUCTURE 로 제거됨
        — equity 시계열은 별도 `/charts/equity/` 경로가 담당한다.
        """
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
            updated_applied_fill_dismiss_ids={},
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

        # /latest/drift 경로는 제거됨 — drift_pct 는 /latest/portfolio 에서 읽는다.
        assert "/latest/drift" not in mock_db
        assert mock_db["/latest/portfolio"]["drift_pct"] == 0.0

        # /history/summary/ RTDB 경로는 제거됨 — equity 시계열은 /charts/equity/ 소관.
        assert "/history/summary/2026-04-10" not in mock_db
        assert not any(key.startswith("/history/summary") for key in mock_db)

    def test_drift_pct_is_stored_as_0_to_1_ratio(self, mock_db, mock_app):
        """
        목적: 프로젝트 네이밍 관례(`_pct` = 0~1 ratio) 에 따라 `/latest/portfolio`
              의 ``drift_pct`` 는 **0~1 ratio** 로 저장된다.

        Given: drift_pct=0.0350 (3.5%) 인 DailyResult.
        When:  write_read_model 호출.
        Then:  저장된 값이 0.0350 (× 100 스케일이 아님), [0, 1] 범위 내.
        """
        # Given
        state = create_initial_state(100_000_000.0)
        state.assets["sso"].model_shares = 100
        drift_ratio = 0.0350

        result = DailyResult(
            execution_date="2026-04-10",
            updated_state=state,
            updated_applied_fill_ids={},
            updated_applied_balance_adjust_ids={},
            updated_applied_fill_dismiss_ids={},
            signals={},
            order_intents={},
            executions=None,
            rebalance_triggered=False,
            model_equity=100_000_000.0,
            actual_equity=96_500_000.0,
            drift_pct=drift_ratio,
            drift_report=DriftReport(
                model_equity=100_000_000.0,
                actual_equity=96_500_000.0,
                drift_pct=drift_ratio,
                per_asset={},
                recommendation="주의",
            ),
            ma_distances={},
            notification_body="test",
            pending_fill_reminders=[],
        )

        # When
        write_read_model(mock_app, state, result)

        # Then
        portfolio_drift = mock_db["/latest/portfolio"]["drift_pct"]
        assert portfolio_drift == pytest.approx(
            drift_ratio, abs=1e-6
        ), f"/latest/portfolio drift_pct 는 0~1 ratio 여야 함 (expected≈{drift_ratio})"
        assert 0.0 <= portfolio_drift <= 1.0


# ============================================================================
# write_chart_meta / write_chart_recent / write_chart_archive_year
# ============================================================================


def _sample_chart_series() -> ChartSeries:
    """테스트용 ChartSeries (마커는 ISO 날짜 문자열)."""
    return ChartSeries(
        dates=["2026-04-08", "2026-04-09"],
        close=[100.0, 101.0],
        ma_value=[99.5, 99.6],
        upper_band=[102.0, 102.1],
        lower_band=[97.0, 97.1],
        buy_signals=["2026-04-08"],
        sell_signals=[],
        user_buys=["2026-04-09"],
        user_sells=[],
    )


class TestWriteChartMeta:
    def test_writes_meta_per_asset(self, mock_db, mock_app):
        """
        목적: write_chart_meta 가 /charts/prices/{asset_id}/meta 에 자산별로 쓴다.

        Given: 두 자산에 대한 ChartMeta 맵
        When:  write_chart_meta
        Then:  각 자산의 /charts/prices/{asset_id}/meta 에 payload 존재, 필드 일치.
        """
        meta_map = {
            "sso": ChartMeta(
                first_date="2013-01-02",
                last_date="2026-04-14",
                ma_window=200,
                recent_months=6,
                archive_years=[2013, 2014, 2015],
            ),
            "qld": ChartMeta(
                first_date="2013-01-02",
                last_date="2026-04-14",
                ma_window=200,
                recent_months=6,
                archive_years=[2013, 2014, 2015],
            ),
        }

        write_chart_meta(mock_app, meta_map)

        assert "/charts/prices/sso/meta" in mock_db
        assert "/charts/prices/qld/meta" in mock_db
        assert mock_db["/charts/prices/sso/meta"]["archive_years"] == [2013, 2014, 2015]
        assert mock_db["/charts/prices/sso/meta"]["recent_months"] == 6
        assert mock_db["/charts/prices/sso/meta"]["ma_window"] == 200
        # 구 경로는 쓰지 않는다.
        assert "/latest/chart_data/sso/meta" not in mock_db


class TestWriteChartRecent:
    def test_writes_recent_per_asset(self, mock_db, mock_app):
        """
        목적: write_chart_recent 가 /charts/prices/{asset_id}/recent 에 자산별로 쓴다.

        Given: 두 자산에 대한 ChartSeries (recent slice)
        When:  write_chart_recent
        Then:  각 자산의 /charts/prices/{asset_id}/recent 에 payload 존재, 마커는 ISO 날짜 문자열.
        """
        chart = _sample_chart_series()
        write_chart_recent(mock_app, {"sso": chart, "qld": chart})

        assert "/charts/prices/sso/recent" in mock_db
        assert "/charts/prices/qld/recent" in mock_db
        assert mock_db["/charts/prices/sso/recent"]["close"] == [100.0, 101.0]
        assert mock_db["/charts/prices/sso/recent"]["buy_signals"] == ["2026-04-08"]
        assert mock_db["/charts/prices/sso/recent"]["user_buys"] == ["2026-04-09"]
        assert "/latest/chart_data/sso/recent" not in mock_db


class TestWriteChartArchiveYear:
    def test_writes_archive_year_per_asset(self, mock_db, mock_app):
        """
        목적: write_chart_archive_year 가 /charts/prices/{asset_id}/archive/{YYYY} 에 쓴다.

        Given: 특정 연도 ChartSeries 맵
        When:  write_chart_archive_year(year=2026)
        Then:  경로에 /archive/2026 이 포함된다.
        """
        chart = _sample_chart_series()
        write_chart_archive_year(mock_app, year=2026, year_map={"sso": chart, "qld": chart})

        assert "/charts/prices/sso/archive/2026" in mock_db
        assert "/charts/prices/qld/archive/2026" in mock_db
        assert mock_db["/charts/prices/sso/archive/2026"]["close"] == [100.0, 101.0]
        assert "/latest/chart_data/sso/archive/2026" not in mock_db

    def test_writes_archive_year_different_years_independent(self, mock_db, mock_app):
        """
        목적: 동일 자산에 대해 서로 다른 연도 write 는 서로 덮어쓰지 않는다.
        """
        chart_a = _sample_chart_series()
        chart_b = ChartSeries(
            dates=["2025-12-30", "2025-12-31"],
            close=[50.0, 51.0],
            ma_value=[49.0, 49.5],
            upper_band=[52.0, 52.5],
            lower_band=[46.0, 46.5],
            buy_signals=[],
            sell_signals=[],
            user_buys=[],
            user_sells=[],
        )
        write_chart_archive_year(mock_app, year=2026, year_map={"sso": chart_a})
        write_chart_archive_year(mock_app, year=2025, year_map={"sso": chart_b})

        assert "/charts/prices/sso/archive/2026" in mock_db
        assert "/charts/prices/sso/archive/2025" in mock_db
        assert mock_db["/charts/prices/sso/archive/2026"]["close"] == [100.0, 101.0]
        assert mock_db["/charts/prices/sso/archive/2025"]["close"] == [50.0, 51.0]


# ============================================================================
# equity 차트 write (/charts/equity/)
# ============================================================================


def _sample_equity_meta() -> EquityChartMeta:
    return EquityChartMeta(
        first_date="2024-01-02",
        last_date="2026-04-10",
        recent_months=6,
        archive_years=[2024, 2025, 2026],
    )


def _sample_equity_series() -> EquityChartSeries:
    return EquityChartSeries(
        dates=["2026-04-09", "2026-04-10"],
        model_equity=[12_345_678, 12_400_000],
        actual_equity=[12_300_000, 12_350_001],
        drift_pct=[0.0037, 0.0041],
    )


class TestWriteEquityMeta:
    def test_writes_meta_to_charts_equity_path(self, mock_db, mock_app):
        """
        목적: write_equity_meta 가 /charts/equity/meta 단일 경로에 쓴다.

        Given: EquityChartMeta 인스턴스.
        When:  write_equity_meta 호출.
        Then:  /charts/equity/meta 에 payload, 주가 경로 아님.
        """
        meta = _sample_equity_meta()
        write_equity_meta(mock_app, meta)

        assert "/charts/equity/meta" in mock_db
        assert mock_db["/charts/equity/meta"]["first_date"] == "2024-01-02"
        assert mock_db["/charts/equity/meta"]["archive_years"] == [2024, 2025, 2026]
        # 주가 차트 경로에는 쓰지 않는다.
        assert "/charts/prices/meta" not in mock_db


class TestWriteEquityRecent:
    def test_writes_recent_to_charts_equity_path(self, mock_db, mock_app):
        """
        목적: write_equity_recent 가 /charts/equity/recent 에 쓴다.

        Given: EquityChartSeries (recent).
        When:  write_equity_recent 호출.
        Then:  /charts/equity/recent 에 3 시계열이 그대로 보존된다.
        """
        series = _sample_equity_series()
        write_equity_recent(mock_app, series)

        payload = mock_db["/charts/equity/recent"]
        assert payload["dates"] == ["2026-04-09", "2026-04-10"]
        assert payload["model_equity"] == [12_345_678, 12_400_000]
        assert payload["actual_equity"] == [12_300_000, 12_350_001]
        assert payload["drift_pct"] == [0.0037, 0.0041]


class TestWriteEquityArchiveYear:
    def test_writes_archive_year_to_charts_equity_path(self, mock_db, mock_app):
        """
        목적: write_equity_archive_year 가 /charts/equity/archive/{YYYY} 에 쓴다.
        """
        series = _sample_equity_series()
        write_equity_archive_year(mock_app, year=2026, series=series)

        assert "/charts/equity/archive/2026" in mock_db
        assert mock_db["/charts/equity/archive/2026"]["dates"] == ["2026-04-09", "2026-04-10"]

    def test_writes_different_years_independent(self, mock_db, mock_app):
        """
        목적: 서로 다른 연도 write 는 독립적으로 저장된다.
        """
        series_a = _sample_equity_series()
        series_b = EquityChartSeries(
            dates=["2025-12-30"],
            model_equity=[11_000_000],
            actual_equity=[10_950_000],
            drift_pct=[0.0045],
        )
        write_equity_archive_year(mock_app, year=2026, series=series_a)
        write_equity_archive_year(mock_app, year=2025, series=series_b)

        assert mock_db["/charts/equity/archive/2026"]["model_equity"] == [12_345_678, 12_400_000]
        assert mock_db["/charts/equity/archive/2025"]["model_equity"] == [11_000_000]


# ============================================================================
# delete_all_except_device_tokens (reset 초기화 경로)
# ============================================================================


class TestDeleteAllExceptDeviceTokens:
    """``reset`` CLI 가 호출하는 RTDB 전체 초기화 경로 정책.

    - /device_tokens 는 삭제하지 않는다 (FCM 토큰 유지).
    - /charts 최상위를 삭제한다 (주가 + equity 차트 전부).
    - /history/summary 는 더 이상 RTDB 에 쓰지 않으므로 삭제 대상 목록에 포함되지 않는다
      (PLAN_LIVE_CHARTS_RESTRUCTURE).
    """

    def test_deletes_expected_paths_and_keeps_device_tokens(self, monkeypatch, mock_app):
        # Given — 삭제 호출을 추적할 수 있는 fake _db_reference
        deleted_paths: list[str] = []

        class _RecordingRef:
            def __init__(self, path: str) -> None:
                self._path = path

            def delete(self) -> None:
                deleted_paths.append(self._path)

        monkeypatch.setattr(rtdb_module, "_db_reference", lambda app, path: _RecordingRef(path))

        # When
        delete_all_except_device_tokens(mock_app)

        # Then — /device_tokens 는 포함되지 않고, 신규 /charts 가 포함된다.
        assert "/device_tokens" not in deleted_paths
        assert "/latest" in deleted_paths
        assert "/charts" in deleted_paths
        assert "/fills/inbox" in deleted_paths
        assert "/balance_adjust/inbox" in deleted_paths
        assert "/fill_dismiss/inbox" in deleted_paths
        # /history/summary 는 더 이상 RTDB 에 존재하지 않으므로 삭제 목록에 없다.
        assert "/history/summary" not in deleted_paths


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

    def test_dict_to_actual_fill_missing_required_raises(self):
        """Given fill dict 에 필수 필드 누락 When 변환 Then ValueError."""
        from live.rtdb_gateway import _dict_to_actual_fill

        incomplete = {"asset_id": "sso", "direction": "buy"}
        with pytest.raises(ValueError, match="fill 필수 필드 누락"):
            _dict_to_actual_fill(incomplete, rtdb_key="fill_bad")

    def test_dict_to_balance_adjust_no_fields_raises(self):
        """Given adjust dict 에 4 개 보정 필드 모두 없음 When 변환 Then ValueError."""
        from live.rtdb_gateway import _dict_to_balance_adjust

        empty_adjust = {"reason": "test"}
        with pytest.raises(ValueError, match="유효한"):
            _dict_to_balance_adjust(empty_adjust, rtdb_key="adj_bad")

    def test_dict_to_balance_adjust_null_values_raises(self):
        """Given adjust dict 에 모든 보정 필드 키는 있지만 값이 null When 변환 Then ValueError.

        키가 존재하더라도 값이 null 이면 무효한 adjust 이므로 즉시 실패해야 한다.
        """
        from live.rtdb_gateway import _dict_to_balance_adjust

        null_adjust = {
            "new_shares": None,
            "new_avg_price": None,
            "new_entry_date": None,
            "new_cash": None,
            "reason": "test",
        }
        with pytest.raises(ValueError, match="유효한"):
            _dict_to_balance_adjust(null_adjust, rtdb_key="adj_null")

    def test_dict_to_balance_adjust_new_avg_price_parsed(self):
        """Given adjust dict 에 new_avg_price 지정 When 변환 Then float 으로 파싱된다."""
        from live.rtdb_gateway import _dict_to_balance_adjust

        raw = {
            "asset_id": "sso",
            "new_avg_price": 85.0,
            "reason": "평균가 재입력",
            "input_time_kst": "2026-04-10T20:00:00+09:00",
        }
        adjust = _dict_to_balance_adjust(raw, rtdb_key="adj_avg")

        assert adjust.new_avg_price == pytest.approx(85.0)
        assert adjust.new_shares is None
        assert adjust.new_entry_date is None
        assert adjust.new_cash is None
        assert adjust.asset_id == "sso"

    def test_dict_to_balance_adjust_new_entry_date_parsed(self):
        """Given adjust dict 에 new_entry_date 지정 When 변환 Then str 로 파싱된다."""
        from live.rtdb_gateway import _dict_to_balance_adjust

        raw = {
            "asset_id": "sso",
            "new_entry_date": "2026-04-01",
            "reason": "진입일 재입력",
            "input_time_kst": "2026-04-10T20:00:00+09:00",
        }
        adjust = _dict_to_balance_adjust(raw, rtdb_key="adj_date")

        assert adjust.new_entry_date == "2026-04-01"
        assert adjust.new_shares is None
        assert adjust.new_avg_price is None

    def test_dict_to_actual_fill_invalid_direction_raises(self):
        """Given fill 의 direction 이 buy/sell 외 값 When 변환 Then ValueError.

        RTDB 에서 잘못된 direction 이 들어오면 입구에서 즉시 차단해야 한다.
        """
        from live.rtdb_gateway import _dict_to_actual_fill

        bad_fill = {
            "asset_id": "sso",
            "direction": "hold",
            "actual_price": 82.0,
            "actual_shares": 100,
            "trade_date": "2026-04-10",
            "input_time_kst": "2026-04-10T20:00:00+09:00",
        }
        with pytest.raises(ValueError, match="fill direction 값이 유효하지 않음"):
            _dict_to_actual_fill(bad_fill, rtdb_key="fill_bad_dir")
