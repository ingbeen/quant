"""live.rtdb_gateway — Firebase Admin SDK mock 기반 테스트.

Firebase 실제 호출 없이 ``firebase_admin.db.reference`` 를 monkeypatch 로 대체하여
RTDB 진입점 호출 시그니처와 페이로드 구조를 검증한다.
"""

from __future__ import annotations

import logging
from datetime import date
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
    SignalDetection,
)
from live.rtdb_gateway import (
    fetch_pending_balance_adjusts,
    fetch_unprocessed_fills,
    mark_balance_adjusts_processed,
    mark_fills_processed,
    prune_history_summary,
    read_device_tokens,
    remove_invalid_tokens,
    write_chart_archive_year,
    write_chart_meta,
    write_chart_recent,
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

    이 규칙 덕분에 ``write_read_model`` 처럼 ``/history/summary/{date}`` 단위로
    ``set`` 한 결과를 ``/history/summary`` 의 부모 ``get`` 에서 dict 로 되돌려
    읽을 수 있다. 실제 Firebase RTDB 의 트리 구조 동작을 단순화한 모방이다.
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

        # /latest/drift 경로는 제거됨 — drift_pct 는 /latest/portfolio 에서 읽는다.
        assert "/latest/drift" not in mock_db
        assert mock_db["/latest/portfolio"]["drift_pct"] == 0.0

        assert "/history/summary/2026-04-10" in mock_db

    def test_drift_pct_is_stored_as_0_to_1_ratio(self, mock_db, mock_app):
        """
        목적: 프로젝트 네이밍 관례(`_pct` = 0~1 ratio) 에 따라 `/latest/portfolio`
              와 `/history/summary/{date}` 의 ``drift_pct`` 는 **0~1 ratio** 로
              저장된다 (과거 `× 100 스케일` 에서 0~1 ratio 로 통일됨).

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
        history_drift = mock_db["/history/summary/2026-04-10"]["drift_pct"]

        assert portfolio_drift == pytest.approx(
            drift_ratio, abs=1e-6
        ), f"/latest/portfolio drift_pct 는 0~1 ratio 여야 함 (expected≈{drift_ratio})"
        assert history_drift == pytest.approx(
            drift_ratio, abs=1e-6
        ), f"/history/summary drift_pct 는 0~1 ratio 여야 함 (expected≈{drift_ratio})"
        assert 0.0 <= portfolio_drift <= 1.0
        assert 0.0 <= history_drift <= 1.0


# ============================================================================
# prune_history_summary
# ============================================================================


class TestPruneHistorySummary:
    """``/history/summary/{date}`` rolling window 정리 정책.

    정책:

    - ``today - retention_days`` **이전** 날짜 키는 삭제된다.
    - 그 이상 ("오늘 이후" 포함) 날짜 키는 보존된다.
    - ``/history/summary`` 가 비어 있거나 존재하지 않으면 no-op.
    - 날짜 포맷이 ISO 8601 이 아닌 키는 무시한다 (파싱 실패 시 건너뜀).
    """

    def test_removes_entries_older_than_retention(self, mock_db, mock_app):
        """
        목적: retention 기간을 넘긴 날짜 키만 삭제되고 최신 키는 보존된다.

        경계 정책: ``cutoff = today - retention_days``, ``entry_date < cutoff`` 이면 삭제.
        따라서 retention 경계일(정확히 today - retention_days) 자체는 **보존** 된다.

        Given: /history/summary 에 경계 전후 여러 날짜 키가 존재한다.
        When:  retention_days=90, today=2026-04-14 로 prune 호출 → cutoff=2026-01-14.
        Then:  cutoff 미만 키(2025-12-31, 2026-01-13)는 삭제, cutoff 이상 키는 보존.
        """
        # Given
        mock_db["/history/summary/2025-12-31"] = {"execution_date": "2025-12-31"}  # cutoff 미만
        mock_db["/history/summary/2026-01-13"] = {"execution_date": "2026-01-13"}  # cutoff 미만
        mock_db["/history/summary/2026-01-14"] = {"execution_date": "2026-01-14"}  # cutoff 정확 일치
        mock_db["/history/summary/2026-01-15"] = {"execution_date": "2026-01-15"}  # cutoff 초과
        mock_db["/history/summary/2026-04-10"] = {"execution_date": "2026-04-10"}

        # When
        prune_history_summary(mock_app, retention_days=90, today=date(2026, 4, 14))

        # Then
        assert "/history/summary/2025-12-31" not in mock_db  # cutoff 미만 → 삭제
        assert "/history/summary/2026-01-13" not in mock_db  # cutoff 미만 → 삭제
        assert "/history/summary/2026-01-14" in mock_db  # cutoff 일치 → 보존
        assert "/history/summary/2026-01-15" in mock_db  # cutoff 초과 → 보존
        assert "/history/summary/2026-04-10" in mock_db  # 최근 → 보존

    def test_empty_history_summary_is_noop(self, mock_db, mock_app):
        """
        목적: /history/summary 가 비어 있으면 아무 일도 하지 않는다.

        Given: mock store 가 비어 있음.
        When:  prune 호출.
        Then:  예외 없이 종료, store 변화 없음.
        """
        # Given / When
        prune_history_summary(mock_app, retention_days=90, today=date(2026, 4, 14))

        # Then
        assert mock_db == {}

    def test_invalid_date_keys_are_skipped_with_warning(self, mock_db, mock_app, caplog):
        """
        목적: ISO 8601 파싱 실패 키는 건너뛰되, 운영자가 침해를 인지할 수 있도록
              WARNING 로그로 기록한다 (파손 키 보호 의도 유지 + 침해 가시화).

        Given: /history/summary 아래에 파싱 불가능한 키가 존재.
        When:  prune 호출.
        Then:  해당 키는 그대로 유지, 예외 없음, WARNING 로그에 파손 키가 포함.

        주의: qbt ``setup_logger`` 는 ``propagate=False`` 이므로 caplog 기본 캡처가
        닿지 않는다. 본 테스트는 ``caplog.handler`` 를 live 로거에 직접 부착한다.
        """
        # Given
        mock_db["/history/summary/not-a-date"] = {"execution_date": "invalid"}
        mock_db["/history/summary/2026-04-10"] = {"execution_date": "2026-04-10"}

        rtdb_logger = logging.getLogger("live.rtdb_gateway")
        caplog.set_level(logging.WARNING, logger="live.rtdb_gateway")
        rtdb_logger.addHandler(caplog.handler)
        try:
            # When
            prune_history_summary(mock_app, retention_days=90, today=date(2026, 4, 14))
        finally:
            rtdb_logger.removeHandler(caplog.handler)

        # Then
        assert "/history/summary/not-a-date" in mock_db  # 파싱 실패 → 건너뜀
        assert "/history/summary/2026-04-10" in mock_db
        warnings = [rec.getMessage() for rec in caplog.records if rec.levelname == "WARNING"]
        assert any("not-a-date" in msg for msg in warnings), f"파손 키 WARNING 로그가 없음. 현재 WARNING 로그: {warnings!r}"

    def test_keeps_today_and_future_entries(self, mock_db, mock_app):
        """
        목적: 오늘 이후 날짜는 무조건 보존한다 (retention 기준이 음수가 되는 경우 없음).

        Given: 오늘 / 오늘 이후 키가 존재.
        When:  prune 호출.
        Then:  모두 보존.
        """
        # Given
        mock_db["/history/summary/2026-04-14"] = {"execution_date": "2026-04-14"}
        mock_db["/history/summary/2026-04-15"] = {"execution_date": "2026-04-15"}

        # When
        prune_history_summary(mock_app, retention_days=90, today=date(2026, 4, 14))

        # Then
        assert "/history/summary/2026-04-14" in mock_db
        assert "/history/summary/2026-04-15" in mock_db

    def test_non_dict_root_is_noop(self, mock_db, mock_app):
        """
        목적: /history/summary 가 dict 가 아닌 예상 외 타입이면 조용히 건너뛴다.

        Given: /history/summary 가 문자열로 저장됨 (이상 케이스).
        When:  prune 호출.
        Then:  예외 없이 종료, 원본 보존.
        """
        # Given
        mock_db["/history/summary"] = "not a dict"

        # When
        prune_history_summary(mock_app, retention_days=90, today=date(2026, 4, 14))

        # Then
        assert mock_db["/history/summary"] == "not a dict"


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
        목적: write_chart_meta 가 /latest/chart_data/{asset_id}/meta 에 자산별로 쓴다.

        Given: 두 자산에 대한 ChartMeta 맵
        When:  write_chart_meta
        Then:  각 자산의 /latest/chart_data/{asset_id}/meta 에 payload 존재, 필드 일치.
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

        assert "/latest/chart_data/sso/meta" in mock_db
        assert "/latest/chart_data/qld/meta" in mock_db
        assert mock_db["/latest/chart_data/sso/meta"]["archive_years"] == [2013, 2014, 2015]
        assert mock_db["/latest/chart_data/sso/meta"]["recent_months"] == 6
        assert mock_db["/latest/chart_data/sso/meta"]["ma_window"] == 200


class TestWriteChartRecent:
    def test_writes_recent_per_asset(self, mock_db, mock_app):
        """
        목적: write_chart_recent 가 /latest/chart_data/{asset_id}/recent 에 자산별로 쓴다.

        Given: 두 자산에 대한 ChartSeries (recent slice)
        When:  write_chart_recent
        Then:  각 자산의 /latest/chart_data/{asset_id}/recent 에 payload 존재, 마커는 ISO 날짜 문자열.
        """
        chart = _sample_chart_series()
        write_chart_recent(mock_app, {"sso": chart, "qld": chart})

        assert "/latest/chart_data/sso/recent" in mock_db
        assert "/latest/chart_data/qld/recent" in mock_db
        assert mock_db["/latest/chart_data/sso/recent"]["close"] == [100.0, 101.0]
        assert mock_db["/latest/chart_data/sso/recent"]["buy_signals"] == ["2026-04-08"]
        assert mock_db["/latest/chart_data/sso/recent"]["user_buys"] == ["2026-04-09"]


class TestWriteChartArchiveYear:
    def test_writes_archive_year_per_asset(self, mock_db, mock_app):
        """
        목적: write_chart_archive_year 가 /latest/chart_data/{asset_id}/archive/{YYYY} 에 쓴다.

        Given: 특정 연도 ChartSeries 맵
        When:  write_chart_archive_year(year=2026)
        Then:  경로에 /archive/2026 이 포함된다.
        """
        chart = _sample_chart_series()
        write_chart_archive_year(mock_app, year=2026, year_map={"sso": chart, "qld": chart})

        assert "/latest/chart_data/sso/archive/2026" in mock_db
        assert "/latest/chart_data/qld/archive/2026" in mock_db
        assert mock_db["/latest/chart_data/sso/archive/2026"]["close"] == [100.0, 101.0]

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

        assert "/latest/chart_data/sso/archive/2026" in mock_db
        assert "/latest/chart_data/sso/archive/2025" in mock_db
        assert mock_db["/latest/chart_data/sso/archive/2026"]["close"] == [100.0, 101.0]
        assert mock_db["/latest/chart_data/sso/archive/2025"]["close"] == [50.0, 51.0]


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
