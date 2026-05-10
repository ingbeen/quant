"""live.cli 진입점 및 명령어 통합 계약을 검증한다."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from live import cli as cli_module
from live.cli import _collect_all_tickers, main
from live.models import ChartMeta

# ============================================================================
# 공통 fixture
# ============================================================================


@pytest.fixture
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``storage_gateway.state_workspace`` 를 ``tmp_path`` 를 yield 하는 가짜 컨텍스트
    매니저로 교체한다. 실제 GCS download/upload 는 절대 호출되지 않는다.

    Returns:
        ``tmp_path`` 와 동일한 ``Path`` — 테스트는 이 경로를 state_dir 로 사용.
    """

    @contextmanager
    def fake_state_workspace(*, push_on_success: bool):
        del push_on_success
        yield tmp_path

    monkeypatch.setattr(cli_module.storage_gateway, "state_workspace", fake_state_workspace)
    return tmp_path


class _FakeRtdbApp:
    """RTDB 통합 호출을 전부 무력화한 mock Firebase App."""


def _mock_rtdb_for_cli(monkeypatch: pytest.MonkeyPatch) -> _FakeRtdbApp:
    """CLI run-daily / fetch-fills 경로의 RTDB 의존성을 일괄 mock 한다.

    ``_require_rtdb_app`` 은 fake app 을 반환하고, 모든 rtdb_gateway 함수는
    no-op 으로 교체된다. _publish_to_rtdb 와 _send_daily_notifications 역시
    no-op 으로 둔다.
    """
    fake_app = _FakeRtdbApp()
    monkeypatch.setattr(cli_module, "_require_rtdb_app", lambda: fake_app)
    monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: fake_app)
    monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_fills", lambda app: [])
    monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_balance_adjusts", lambda app: [])
    monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_fill_dismisses", lambda app: [])
    monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_model_syncs", lambda app: [])
    monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fills_processed", lambda app, keys: None)
    monkeypatch.setattr(cli_module.rtdb_gateway, "mark_balance_adjusts_processed", lambda app, keys: None)
    monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fill_dismisses_processed", lambda app, keys: None)
    monkeypatch.setattr(cli_module.rtdb_gateway, "mark_model_syncs_processed", lambda app, keys: None)
    monkeypatch.setattr(cli_module, "_publish_to_rtdb", lambda app, sd, st, r, nk: None)
    monkeypatch.setattr(cli_module, "_send_daily_notifications", lambda app, result: None)
    return fake_app


# ============================================================================
# 공통 헬퍼
# ============================================================================


def _make_recent_df(trade_date: date) -> pd.DataFrame:
    """data_fetcher.fetch_recent_ohlc 의 반환 형태를 모사."""
    return pd.DataFrame(
        {
            "Date": [trade_date],
            "Open": [100.0],
            "High": [101.0],
            "Low": [99.0],
            "Close": [100.5],
            "Volume": [1_000_000],
        }
    )


def _create_state_file(state_dir: Path, capital: float = 100_000_000) -> None:
    """``state_dir`` 안에 초기 ``live_state.json`` 을 직접 생성한다.

    init 명령 제거 후, 다른 테스트들이 fixture 상태 셋업용으로 사용하던
    ``main(["init", "--capital", N])`` 호출을 대체한다. CLI 진입점 / argparse /
    state_workspace 컨텍스트를 거치지 않고 ``create_initial_state`` +
    ``save_state`` 만 직접 호출하므로 더 가볍다.
    """
    from live.constants import DEFAULT_LIVE_STATE_FILENAME
    from live.state import create_initial_state, save_state

    state = create_initial_state(capital)
    save_state(state, state_dir / DEFAULT_LIVE_STATE_FILENAME)


def _setup_flat_market_csvs(state_dir: Path, trade_date: date, rows: int = 210) -> None:
    """state_dir/data/stock/ 에 포트폴리오 티커별 평탄 CSV 를 준비한다."""
    import pandas as pd

    dates = [date.fromordinal(trade_date.toordinal() - rows + 1 + i) for i in range(rows)]
    df = pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0] * rows,
            "High": [100.5] * rows,
            "Low": [99.5] * rows,
            "Close": [100.0] * rows,
            "Volume": [1_000_000] * rows,
        }
    )
    stock_dir = state_dir / "data" / "stock"
    stock_dir.mkdir(parents=True, exist_ok=True)
    for ticker in _collect_all_tickers():
        df.to_csv(stock_dir / f"{ticker}.csv", index=False)


# ============================================================================
# rebuild-data 명령어
# ============================================================================


class TestCmdRebuildData:
    """``rebuild-data`` 는 티커 생략 시 전체 운영 티커를 순회하고,
    명시하면 해당 티커 1 개만 재다운로드한다.
    """

    def test_rebuild_data_single_ticker_rebuilds_only_that_ticker(
        self, state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given rebuild-data SPY When main 실행 Then SPY 한 티커만 rebuild_full_csv 호출."""
        del state_dir  # fixture 설치만 필요
        calls: list[str] = []

        def _spy_rebuild(ticker: str, csv_path: Path, period: str = "max") -> None:
            del csv_path, period
            calls.append(ticker)

        monkeypatch.setattr(cli_module, "rebuild_full_csv", _spy_rebuild)

        exit_code = main(["rebuild-data", "SPY"])

        assert exit_code == 0
        assert calls == ["SPY"]

    def test_rebuild_data_no_ticker_rebuilds_all_operating_tickers(
        self, state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given rebuild-data (티커 생략) When main 실행 Then 전체 운영 티커 순회 rebuild_full_csv 호출."""
        del state_dir  # fixture 설치만 필요
        calls: list[str] = []

        def _spy_rebuild(ticker: str, csv_path: Path, period: str = "max") -> None:
            del csv_path, period
            calls.append(ticker)

        monkeypatch.setattr(cli_module, "rebuild_full_csv", _spy_rebuild)

        exit_code = main(["rebuild-data"])

        assert exit_code == 0
        assert calls == _collect_all_tickers()

    def test_rebuild_data_lowercase_ticker_is_uppercased(
        self, state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given rebuild-data spy (소문자) When main 실행 Then 대문자 SPY 로 호출."""
        del state_dir
        calls: list[str] = []

        def _spy_rebuild(ticker: str, csv_path: Path, period: str = "max") -> None:
            del csv_path, period
            calls.append(ticker)

        monkeypatch.setattr(cli_module, "rebuild_full_csv", _spy_rebuild)

        exit_code = main(["rebuild-data", "spy"])

        assert exit_code == 0
        assert calls == ["SPY"]


# ============================================================================
# reset 명령어 (신규 순서 + 주가 차트 자동 재생성)
# ============================================================================


def _install_reset_spies(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """reset 경로의 외부 의존성을 일괄 mock 하고, 호출 기록 dict 를 반환한다.

    reset 의 9 단계 전 과정 (사전 검증 → Git 파일 작업 → RTDB 삭제 →
    RTDB 주가 차트 재생성) 을 커버한다. 반환 dict 의 각 키는 호출 횟수 / 인자를
    순서대로 담는다 (여러 테스트가 같은 시나리오를 공유).
    """
    calls: dict[str, list[Any]] = {
        "require_rtdb_app": [],
        "delete_all_except_device_tokens": [],
        "rebuild_full_csv": [],
        "build_chart_meta_and_year_slices": [],
        "write_chart_meta": [],
        "write_chart_year_slice": [],
        "write_equity_meta": [],
        "write_equity_year_slice": [],
        "write_history_fills": [],
        "write_history_balance_adjusts": [],
        "write_history_signals": [],
        "order": [],
    }

    fake_app = _FakeRtdbApp()

    def _spy_require() -> _FakeRtdbApp:
        calls["require_rtdb_app"].append(True)
        calls["order"].append("require_rtdb_app")
        return fake_app

    monkeypatch.setattr(cli_module, "_require_rtdb_app", _spy_require)

    def _spy_delete(app: Any) -> None:
        calls["delete_all_except_device_tokens"].append(app)
        calls["order"].append("delete_all_except_device_tokens")

    monkeypatch.setattr(cli_module.rtdb_gateway, "delete_all_except_device_tokens", _spy_delete)

    def _spy_rebuild(ticker: str, csv_path: Path, period: str = "max") -> None:
        del csv_path
        calls["rebuild_full_csv"].append((ticker, period))
        calls["order"].append("rebuild_full_csv")

    monkeypatch.setattr(cli_module, "rebuild_full_csv", _spy_rebuild)

    stub_meta = {
        "sso": ChartMeta(
            first_date="2020-01-01",
            last_date="2026-04-17",
            ma_window=200,
            years=[2024, 2025],
        ),
    }

    def _spy_meta_and_slices(
        state_dir: Path,
        *,
        years: list[int] | None,
        user_trades: dict[str, Any],
        signal_history: dict[str, Any],
    ) -> tuple[dict[str, ChartMeta], dict[int, dict[str, Any]]]:
        del state_dir
        calls["build_chart_meta_and_year_slices"].append(
            {"years": years, "user_trades": user_trades, "signal_history": signal_history}
        )
        calls["order"].append("build_chart_meta_and_year_slices")
        # years=None 이면 stub_meta 의 자산별 years 합집합을 자동 사용 (실제 함수와 동일 의미론)
        if years is None:
            target = sorted({y for m in stub_meta.values() for y in m.years})
        else:
            target = list(years)
        return stub_meta, {y: {} for y in target}

    monkeypatch.setattr(cli_module, "build_chart_meta_and_year_slices", _spy_meta_and_slices)

    def _spy_write_meta(app: Any, m: Any) -> None:
        del app
        calls["write_chart_meta"].append(m)
        calls["order"].append("write_chart_meta")

    monkeypatch.setattr(cli_module.rtdb_gateway, "write_chart_meta", _spy_write_meta)

    def _spy_write_year_slice(app: Any, *, year: int, year_map: Any) -> None:
        del app
        calls["write_chart_year_slice"].append({"year": year, "map": year_map})
        calls["order"].append("write_chart_year_slice")

    monkeypatch.setattr(cli_module.rtdb_gateway, "write_chart_year_slice", _spy_write_year_slice)

    # equity / history writers — reset 은 호출해서는 안 된다 (summary.jsonl 부재)
    monkeypatch.setattr(
        cli_module.rtdb_gateway,
        "write_equity_meta",
        lambda app, m: calls["write_equity_meta"].append(m),
    )
    monkeypatch.setattr(
        cli_module.rtdb_gateway,
        "write_equity_year_slice",
        lambda app, *, year, series: calls["write_equity_year_slice"].append({"year": year, "series": series}),
    )
    monkeypatch.setattr(
        cli_module.rtdb_gateway,
        "write_history_fills",
        lambda app, fills, ts: calls["write_history_fills"].append((fills, ts)),
    )
    monkeypatch.setattr(
        cli_module.rtdb_gateway,
        "write_history_balance_adjusts",
        lambda app, adjusts, ts: calls["write_history_balance_adjusts"].append((adjusts, ts)),
    )
    monkeypatch.setattr(
        cli_module.rtdb_gateway,
        "write_history_signals",
        lambda app, date_iso, signals: calls["write_history_signals"].append((date_iso, signals)),
    )

    return calls


class TestCmdReset:
    """``reset`` 은 9 단계 순서 (사전 검증 → Git → RTDB 삭제 → 주가 차트 재생성) 로
    동작하며, 사용자 직접 실행 명령이므로 실패 알림을 발송하지 않는다.

    본 테스트 클래스는 정책을 고정한다:
    - Firebase 초기화 실패 시 Git / RTDB 미수정.
    - GCS 동기화 성공 후에만 RTDB 삭제 및 차트 쓰기 발생.
    - 주가 차트 (meta + 연도 슬라이스) 는 생성되고, equity / `/history/*` 는 생성되지 않는다.
    - 차트 재생성 시 체결/시그널 마커는 빈 리스트로 전달된다.
    - 중간 실패 시 reset 재실행으로 멱등 복구 가능하다.
    """

    def test_reset_aborts_on_firebase_init_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given Firebase init 실패 When reset 실행 Then storage workspace / RTDB 어떤 쓰기도 없음."""
        workspace_called: list[bool] = []

        @contextmanager
        def _record_workspace(**kwargs: Any):
            del kwargs
            workspace_called.append(True)
            yield Path("/unused")

        monkeypatch.setattr(cli_module.storage_gateway, "state_workspace", _record_workspace)

        def _raise() -> None:
            raise RuntimeError("Firebase 초기화 실패")

        monkeypatch.setattr(cli_module, "_require_rtdb_app", _raise)

        rtdb_delete_called: list[bool] = []
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "delete_all_except_device_tokens",
            lambda app: rtdb_delete_called.append(True),
        )

        exit_code = main(["reset", "--capital", "100000000"])

        # main() 예외 훅이 exit 1 반환 + Firebase 실패이므로 workspace / RTDB 미진입
        assert exit_code == 1
        assert rtdb_delete_called == []
        assert workspace_called == []

    def test_reset_calls_storage_upload_before_rtdb_delete(
        self, state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given reset 성공 경로 When 실행 Then GCS 정본 작업 (state_workspace 내 CSV 재구성 + upload) 이 RTDB delete 보다 먼저 수행됨."""
        del state_dir
        calls = _install_reset_spies(monkeypatch)

        exit_code = main(["reset", "--capital", "100000000"])
        assert exit_code == 0

        # 순서 검증: CSV 재구성 (state_workspace 내 정본 작업 단계) 가 RTDB delete 보다 먼저.
        order = calls["order"]
        first_rebuild = order.index("rebuild_full_csv")
        first_delete = order.index("delete_all_except_device_tokens")
        assert first_rebuild < first_delete

    def test_reset_writes_price_charts_and_skips_equity_history(
        self, state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given reset 성공 경로 When 실행 Then 주가 차트 (meta + 연도 슬라이스) 만 RTDB 에 쓰고,
        equity / /history/* 쓰기는 발생하지 않음.
        """
        del state_dir
        calls = _install_reset_spies(monkeypatch)

        exit_code = main(["reset", "--capital", "100000000"])
        assert exit_code == 0

        # 주가 차트는 write 1 회 이상
        assert len(calls["write_chart_meta"]) == 1
        assert len(calls["write_chart_year_slice"]) >= 1  # meta.years 수 만큼

        # equity / history 는 write 되지 않음
        assert calls["write_equity_meta"] == []
        assert calls["write_equity_year_slice"] == []
        assert calls["write_history_fills"] == []
        assert calls["write_history_balance_adjusts"] == []
        assert calls["write_history_signals"] == []

    def test_reset_price_chart_markers_are_empty(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given reset 경로 When 차트 빌더 호출 Then user_trades / signal_history 는 빈 dict.

        N+1 회피 + meta/slices 통합으로 build_chart_meta_and_year_slices 가
        **정확히 1 회만** 호출되어야 한다 (자산 frame 1 회 로드 보장).
        """
        del state_dir
        calls = _install_reset_spies(monkeypatch)

        exit_code = main(["reset", "--capital", "100000000"])
        assert exit_code == 0

        # 통합 빌더는 정확히 1 회 호출되어야 한다.
        assert len(calls["build_chart_meta_and_year_slices"]) == 1
        args = calls["build_chart_meta_and_year_slices"][0]
        assert args["user_trades"] == {}
        assert args["signal_history"] == {}
        # reset 은 자산 frame 1 회 로드 + 자동 years 합집합을 위해 years=None 으로 호출한다.
        assert args["years"] is None

    def test_reset_is_idempotent_when_rtdb_write_fails_midway(
        self, state_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given RTDB write_chart_year_slice 실패 시 reset 이 중단되고,
        재실행 시 정상 성공 경로와 동일한 최종 쓰기 결과가 도출됨을 검증.
        """
        del state_dir

        # 1차 실행: 연도 슬라이스 쓰기에서 실패
        calls_first = _install_reset_spies(monkeypatch)

        def _fail_year_slice(app: Any, *, year: int, year_map: Any) -> None:
            del app, year, year_map
            raise RuntimeError("테스트: RTDB year_slice 쓰기 실패")

        monkeypatch.setattr(cli_module.rtdb_gateway, "write_chart_year_slice", _fail_year_slice)

        exit_code_first = main(["reset", "--capital", "100000000"])
        assert exit_code_first == 1  # 실패로 중단

        # 2차 실행: 모든 쓰기 정상. 성공 경로와 동일한 결과가 나와야 한다.
        calls_second = _install_reset_spies(monkeypatch)
        exit_code_second = main(["reset", "--capital", "100000000"])
        assert exit_code_second == 0
        assert len(calls_second["write_chart_meta"]) == 1
        assert len(calls_second["write_chart_year_slice"]) >= 1

        # 1차 실행이 year_slice 쓰기 직전까지 진행했는지 확인 (meta 는 이미 시도됨)
        # 단, 이 테스트의 핵심은 "재실행이 가능하다" 이므로 자세한 부분 상태는 허용.
        del calls_first


# ============================================================================
# run-daily 에러 시나리오
# ============================================================================


class TestCmdRunDailyFailures:
    def _setup_state(self, state_dir: Path) -> None:
        """상태 파일 초기화."""
        _create_state_file(state_dir)
        assert (state_dir / "live_state.json").exists()

    def test_data_fetch_failure_calls_notify(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given data 수집 중 실패 When run-daily Then 중단 + _safe_notify_failure 호출."""
        self._setup_state(state_dir)

        def _failing_fetch(ticker: str, days: int = 5) -> pd.DataFrame:
            raise ValueError(f"테스트: yfinance 실패 {ticker}")

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _failing_fetch)
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)

        notify_calls: list[str] = []

        def _spy_notify(rtdb_app: object, message: str) -> None:
            notify_calls.append(message)

        monkeypatch.setattr(cli_module, "_safe_notify_failure", _spy_notify)

        exit_code = main(["run-daily", "--trade-date", "2026-04-10"])

        # exit code 는 main 의 try/except 에서 1 반환
        assert exit_code == 1
        assert len(notify_calls) >= 1
        assert any("yfinance" in msg or "검증" in msg or "실패" in msg or "데이터" in msg for msg in notify_calls)

    def test_calculation_failure_state_unchanged(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given run_daily 내부 계산 실패 When run-daily Then 중단 + 상태 파일 변경 없음."""
        self._setup_state(state_dir)
        state_path = state_dir / "live_state.json"
        original_mtime = state_path.stat().st_mtime

        _setup_flat_market_csvs(state_dir, date(2026, 4, 10))

        def _mock_fetch(ticker: str, days: int = 5) -> pd.DataFrame:
            return _make_recent_df(date(2026, 4, 10))

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)
        _mock_rtdb_for_cli(monkeypatch)

        def _failing_run_daily(*args: object, **kwargs: object) -> object:
            raise RuntimeError("테스트: 엔진 내부 계산 실패")

        monkeypatch.setattr(cli_module, "run_daily", _failing_run_daily)

        notify_calls: list[str] = []
        monkeypatch.setattr(
            cli_module,
            "_safe_notify_failure",
            lambda app, msg: notify_calls.append(msg),
        )

        exit_code = main(["run-daily", "--trade-date", "2026-04-10"])

        assert exit_code == 1
        assert len(notify_calls) >= 1
        assert any("엔진" in msg or "계산" in msg or "실행" in msg for msg in notify_calls)

        # 상태 파일 변경 없음
        assert state_path.stat().st_mtime == original_mtime


# ============================================================================
# run-daily 정상 경로 (smoke)
# ============================================================================


class TestCmdRunDailySuccess:
    def test_run_daily_smoke(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 정상 파이프라인 When run-daily Then exit 0."""
        _create_state_file(state_dir)

        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        def _mock_fetch(ticker: str, days: int = 5) -> pd.DataFrame:
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)
        _mock_rtdb_for_cli(monkeypatch)

        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])
        assert exit_code == 0

    def test_run_daily_persists_history(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given run-daily When 정상 종료 Then history/daily, summary.jsonl, states/{date}.json 저장."""
        _create_state_file(state_dir)
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        def _mock_fetch(ticker: str, days: int = 5) -> pd.DataFrame:
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)
        _mock_rtdb_for_cli(monkeypatch)

        main(["run-daily", "--trade-date", trade_date.isoformat()])

        assert (state_dir / "history" / "daily" / f"{trade_date.isoformat()}.json").exists()
        assert (state_dir / "history" / "summary.jsonl").exists()

        # history/states/{date}.json 스냅샷이 생성되고, 같은 시점 live_state.json 과
        # 바이트 단위로 동일해야 한다 (save_state 직렬화 규칙 재사용 계약).
        snapshot_path = state_dir / "history" / "states" / f"{trade_date.isoformat()}.json"
        live_state_path = state_dir / "live_state.json"
        assert snapshot_path.exists()
        assert snapshot_path.read_bytes() == live_state_path.read_bytes()

    def test_run_daily_with_rtdb_calls_publish(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given RTDB 활성화 When run-daily Then publish_to_rtdb + send_daily_notifications 호출."""
        _create_state_file(state_dir)
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        def _mock_fetch(ticker: str, days: int = 5) -> pd.DataFrame:
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)

        fake_app = object()
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: fake_app)

        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_fills", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_balance_adjusts", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_fill_dismisses", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_model_syncs", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fills_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_balance_adjusts_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fill_dismisses_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_model_syncs_processed", lambda app, keys: None)

        publish_calls: list[bool] = []

        def _spy_publish(app: object, state_dir: Path, state: object, result: object, newly_keys: object) -> None:
            publish_calls.append(True)

        monkeypatch.setattr(cli_module, "_publish_to_rtdb", _spy_publish)

        notify_calls: list[bool] = []

        def _spy_notify(app: object, result: object) -> None:
            notify_calls.append(True)

        monkeypatch.setattr(cli_module, "_send_daily_notifications", _spy_notify)

        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])
        assert exit_code == 0
        assert len(publish_calls) == 1
        assert len(notify_calls) == 1

    def test_publish_to_rtdb_writes_chart_meta_and_year_slice(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """
        목적: ``_publish_to_rtdb`` 가 주가 / equity 차트의 meta + 현재 연도 슬라이스를
              모두 호출한다.

        Given: 빌더와 write 함수들을 스파이로 교체.
        When:  _publish_to_rtdb 호출.
        Then:  write_chart_meta + write_chart_year_slice + write_equity_meta +
               write_equity_year_slice 가 호출되며, 연도 슬라이스는 execution_date
               의 연도로 호출된다.
        """
        # Given
        monkeypatch.setattr(cli_module.rtdb_gateway, "write_read_model", lambda app, state, result: None)
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fills_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module.history, "load_user_trades", lambda d: {})
        monkeypatch.setattr(cli_module.history, "load_signal_history", lambda d: {})

        sentinel_meta = {"sso": object()}
        sentinel_year_map = {"sso": object()}
        sentinel_equity_meta = object()
        sentinel_equity_year = object()

        # 통합 함수 1 회 호출로 meta + 현재 연도 슬라이스를 모두 받는다 (자산 frame 1 회 로드).
        meta_and_slices_call_count = {"n": 0}

        def _spy_meta_and_slices(state_dir, *, years, user_trades, signal_history):  # noqa: ANN001, ANN202
            del state_dir, user_trades, signal_history
            meta_and_slices_call_count["n"] += 1
            return sentinel_meta, {y: sentinel_year_map for y in years}

        monkeypatch.setattr(cli_module, "build_chart_meta_and_year_slices", _spy_meta_and_slices)
        monkeypatch.setattr(cli_module, "build_equity_meta", lambda state_dir: sentinel_equity_meta)
        monkeypatch.setattr(
            cli_module,
            "build_equity_year_slice",
            lambda state_dir, year: sentinel_equity_year,
        )

        meta_calls: list[object] = []
        year_slice_calls: list[tuple[int, object]] = []
        equity_meta_calls: list[object] = []
        equity_year_calls: list[tuple[int, object]] = []
        history_signals_calls: list[tuple[str, dict[str, object]]] = []

        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_chart_meta",
            lambda app, meta_map: meta_calls.append(meta_map),
        )
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_chart_year_slice",
            lambda app, year, year_map: year_slice_calls.append((year, year_map)),
        )
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_equity_meta",
            lambda app, meta: equity_meta_calls.append(meta),
        )
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_equity_year_slice",
            lambda app, year, series: equity_year_calls.append((year, series)),
        )
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_history_signals",
            lambda app, execution_date, signals: history_signals_calls.append((execution_date, signals)),
        )

        sentinel_signals = {"sso": object(), "qld": object(), "gld": object(), "tlt": object()}

        class _StubResult:
            execution_date = "2026-04-14"
            signals = sentinel_signals

        # When
        cli_module._publish_to_rtdb(
            rtdb_app=object(),
            state_dir=tmp_path,
            state=object(),
            result=_StubResult(),  # type: ignore[arg-type]
            newly_applied_fill_keys=set(),
        )

        # Then — 주가 차트
        assert meta_calls == [sentinel_meta]
        assert year_slice_calls == [(2026, sentinel_year_map)]
        # 통합 함수는 정확히 1 회만 호출 (자산 frame 1 회 로드 보장).
        assert meta_and_slices_call_count["n"] == 1
        # Then — equity 차트
        assert equity_meta_calls == [sentinel_equity_meta]
        assert equity_year_calls == [(2026, sentinel_equity_year)]
        # Then — /history/signals/ 미러
        assert history_signals_calls == [("2026-04-14", sentinel_signals)]


# ============================================================================
# placeholder → 실구현된 명령어 테스트
# ============================================================================


class TestFetchFills:
    """fetch-fills 는 RTDB 만 읽으므로 state_dir 가 필요 없다."""

    def test_fetch_fills_rtdb_init_failure_exits_without_notify(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given Firebase 초기화 실패 When fetch-fills Then exit 1 + allow-list 정책으로 알림 미발송.

        fetch-fills 는 사용자 직접 실행 커맨드이므로 ``_NOTIFY_FAILURE_COMMANDS`` 에
        포함되지 않는다. 실패 시 터미널 stderr + ERROR 로그로만 노출된다.
        """
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)
        notify_calls: list[str] = []
        monkeypatch.setattr(
            cli_module,
            "_safe_notify_failure",
            lambda app, msg: notify_calls.append(msg),
        )
        exit_code = main(["fetch-fills"])
        assert exit_code == 1
        assert notify_calls == []

    def test_fetch_fills_outputs_json(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from live.models import ActualFill

        fake_app = object()
        monkeypatch.setattr(cli_module, "_require_rtdb_app", lambda: fake_app)
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: fake_app)
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "fetch_unprocessed_fills",
            lambda app: [
                ActualFill(
                    asset_id="sso",
                    direction="buy",
                    actual_price=82.0,
                    actual_shares=420,
                    trade_date="2026-04-10",
                    input_time_kst="2026-04-10T20:00:00+09:00",
                    memo=None,
                    rtdb_key="fill_test",
                )
            ],
        )

        exit_code = main(["fetch-fills"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "fill_test" in captured.out
        assert "sso" in captured.out


class TestCmdBackfillChartYears:
    """``backfill-chart-years`` 수동 CLI 의 계약 테스트.

    정상 경로 / --year 옵션 / --dry-run / --target 옵션 / RTDB 초기화 실패를
    고정한다.
    """

    def _stub_meta(self, years: list[int]) -> dict[str, ChartMeta]:
        """build_chart_meta 의 반환값을 모사한다 (자산별 ChartMeta)."""
        return {
            "sso": ChartMeta(
                first_date="2013-01-02",
                last_date="2026-04-14",
                ma_window=200,
                years=years,
            ),
            "qld": ChartMeta(
                first_date="2013-01-02",
                last_date="2026-04-14",
                ma_window=200,
                years=years,
            ),
        }

    def _stub_equity_meta(self, years: list[int]) -> object:
        """build_equity_meta 의 반환값을 모사한다."""
        from live.models import EquityChartMeta

        return EquityChartMeta(
            first_date="2024-01-02",
            last_date="2026-04-14",
            years=years,
        )

    def _setup_common_mocks(
        self,
        monkeypatch: pytest.MonkeyPatch,
        years: list[int],
        equity_years: list[int] | None = None,
    ) -> tuple[list[tuple[int, object]], list[object], list[tuple[int, object]], list[object],]:
        """주가 / equity 빌더 및 write 함수를 모두 스파이로 세팅한다.

        Returns:
            (price_year_calls, price_meta_calls, equity_year_calls, equity_meta_calls)
        """
        meta_stub = self._stub_meta(years)

        def _fake_meta_and_slices(
            state_dir: Path,
            *,
            years: list[int] | None,
            user_trades: object,
            signal_history: object,
        ) -> tuple[dict[str, ChartMeta], dict[int, dict[str, object]]]:
            del state_dir, user_trades, signal_history
            # backfill 은 years=None 으로 호출하여 자동 합집합 사용한다.
            target = sorted({y for m in meta_stub.values() for y in m.years}) if years is None else list(years)
            return meta_stub, {y: {"sso": f"sso_{y}", "qld": f"qld_{y}"} for y in target}

        monkeypatch.setattr(cli_module, "build_chart_meta_and_year_slices", _fake_meta_and_slices)

        # equity 빌더 스텁
        eq_years = equity_years if equity_years is not None else years
        equity_meta_stub = self._stub_equity_meta(eq_years)
        monkeypatch.setattr(cli_module, "build_equity_meta", lambda state_dir: equity_meta_stub)
        monkeypatch.setattr(
            cli_module,
            "build_equity_year_slices",
            lambda state_dir, *, years: {y: f"equity_series_{y}" for y in years},
        )

        price_year_calls: list[tuple[int, object]] = []
        price_meta_calls: list[object] = []
        equity_year_calls: list[tuple[int, object]] = []
        equity_meta_calls: list[object] = []

        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_chart_year_slice",
            lambda app, year, year_map: price_year_calls.append((year, year_map)),
        )
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_chart_meta",
            lambda app, meta_map: price_meta_calls.append(meta_map),
        )
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_equity_year_slice",
            lambda app, year, series: equity_year_calls.append((year, series)),
        )
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_equity_meta",
            lambda app, meta: equity_meta_calls.append(meta),
        )

        # history 로더는 사용되지 않을 수 있지만 안전하게 no-op
        monkeypatch.setattr(cli_module.history, "load_user_trades", lambda d: {})
        monkeypatch.setattr(cli_module.history, "load_signal_history", lambda d: {})

        return (price_year_calls, price_meta_calls, equity_year_calls, equity_meta_calls)

    def test_backfill_full_covers_all_years(
        self,
        state_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        목적: 인자 없이 실행(기본 --target=all)하면 주가 / equity 양쪽의
              years 전체를 순회 재생성한다.

        Given: years=[2024, 2025, 2026], RTDB / 빌더 스파이.
        When:  main(["backfill-chart-years"])
        Then:  주가 + equity 각각 3 연도 슬라이스 write + meta 1 회.
        """
        del state_dir  # fixture 설치만 필요
        monkeypatch.setattr(cli_module, "_require_rtdb_app", lambda: object())
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: object())

        price_years, price_meta, equity_years, equity_meta = self._setup_common_mocks(
            monkeypatch, years=[2024, 2025, 2026]
        )

        exit_code = main(["backfill-chart-years"])
        assert exit_code == 0
        assert sorted(year for year, _ in price_years) == [2024, 2025, 2026]
        assert len(price_meta) == 1
        assert sorted(year for year, _ in equity_years) == [2024, 2025, 2026]
        assert len(equity_meta) == 1

    def test_backfill_year_option_targets_single_year(
        self,
        state_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        목적: --year 지정 시 해당 연도만 재생성한다 (기본 target=all).

        Given: years=[2024, 2025, 2026].
        When:  main(["backfill-chart-years", "--year", "2025"])
        Then:  주가 / equity 각각 2025 연도만 write, meta 는 1 회씩.
        """
        del state_dir
        monkeypatch.setattr(cli_module, "_require_rtdb_app", lambda: object())
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: object())

        price_years, price_meta, equity_years, equity_meta = self._setup_common_mocks(
            monkeypatch, years=[2024, 2025, 2026]
        )

        exit_code = main(["backfill-chart-years", "--year", "2025"])
        assert exit_code == 0
        assert [year for year, _ in price_years] == [2025]
        assert [year for year, _ in equity_years] == [2025]
        assert len(price_meta) == 1
        assert len(equity_meta) == 1

    def test_backfill_target_prices_only(
        self,
        state_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        목적: --target prices 지정 시 주가 차트만 재생성하고 equity 는 손대지 않는다.
        """
        del state_dir
        monkeypatch.setattr(cli_module, "_require_rtdb_app", lambda: object())
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: object())

        price_years, price_meta, equity_years, equity_meta = self._setup_common_mocks(monkeypatch, years=[2024, 2025])

        exit_code = main(["backfill-chart-years", "--target", "prices"])
        assert exit_code == 0
        assert sorted(year for year, _ in price_years) == [2024, 2025]
        assert len(price_meta) == 1
        # equity 는 손대지 않는다.
        assert equity_years == []
        assert equity_meta == []

    def test_backfill_target_equity_only(
        self,
        state_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        목적: --target equity 지정 시 equity 차트만 재생성하고 주가는 손대지 않는다.
        """
        del state_dir
        monkeypatch.setattr(cli_module, "_require_rtdb_app", lambda: object())
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: object())

        price_years, price_meta, equity_years, equity_meta = self._setup_common_mocks(monkeypatch, years=[2024, 2025])

        exit_code = main(["backfill-chart-years", "--target", "equity"])
        assert exit_code == 0
        assert sorted(year for year, _ in equity_years) == [2024, 2025]
        assert len(equity_meta) == 1
        # 주가는 손대지 않는다.
        assert price_years == []
        assert price_meta == []

    def test_backfill_dry_run_skips_write(
        self,
        state_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """
        목적: --dry-run 시 write 함수를 단 한 번도 호출하지 않고 대상 연도를 출력한다.

        Given: years=[2024, 2025, 2026].
        When:  main(["backfill-chart-years", "--dry-run"])
        Then:  write_chart_* / write_equity_* 가 0 회 호출되고 stdout 에
               대상 연도 목록(주가 + equity) 이 포함된다.
        """
        del state_dir
        monkeypatch.setattr(cli_module, "_require_rtdb_app", lambda: object())
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: object())

        price_years, price_meta, equity_years, equity_meta = self._setup_common_mocks(
            monkeypatch, years=[2024, 2025, 2026]
        )

        exit_code = main(["backfill-chart-years", "--dry-run"])
        assert exit_code == 0
        assert price_years == []
        assert price_meta == []
        assert equity_years == []
        assert equity_meta == []
        out = capsys.readouterr().out
        assert "2024" in out
        assert "2025" in out
        assert "2026" in out
        # dry-run 출력에 target 표시가 포함된다.
        assert "target=all" in out

    def test_backfill_rtdb_init_failure_exits_without_notify(
        self,
        state_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        목적: Firebase 초기화 실패 시 exit 1 + allow-list 정책으로 알림 미발송.

        backfill-chart-years 는 사용자 직접 실행 커맨드이므로
        ``_NOTIFY_FAILURE_COMMANDS`` 에 포함되지 않는다. 실패 시 터미널 stderr +
        ERROR 로그로만 노출된다.

        Given: _initialize_rtdb_app → None
        When:  backfill-chart-years 실행
        Then:  exit=1, _safe_notify_failure 호출되지 않음.
        """
        del state_dir
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)

        self._setup_common_mocks(monkeypatch, years=[2025])  # type: ignore[func-returns-value]

        notify_calls: list[str] = []
        monkeypatch.setattr(
            cli_module,
            "_safe_notify_failure",
            lambda app, msg: notify_calls.append(msg),
        )

        exit_code = main(["backfill-chart-years"])
        assert exit_code == 1
        assert notify_calls == []


class TestNotifyFailureCmd:
    """notify-failure 는 state_dir 가 필요 없다."""

    def test_notify_failure_calls_safe_notify(self, monkeypatch: pytest.MonkeyPatch) -> None:
        notify_calls: list[str] = []
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)
        monkeypatch.setattr(
            cli_module,
            "_safe_notify_failure",
            lambda app, msg: notify_calls.append(msg),
        )

        exit_code = main(["notify-failure", "-m", "수동 실패 테스트"])
        assert exit_code == 0
        assert "수동 실패 테스트" in notify_calls[0]


# ============================================================================
# argparse 기본
# ============================================================================


class TestMainArgv:
    def test_main_accepts_argv_list(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given argv 리스트 When main 호출 Then 정상 실행.

        argparse 처리 + dispatch 가 정상 동작하는지만 검증하므로 가장 가벼운
        커맨드(``rebuild-data SPY``) 를 사용하고 외부 의존성은 mock 한다.
        """
        del state_dir  # fixture 설치만 필요
        monkeypatch.setattr(cli_module, "rebuild_full_csv", lambda ticker, csv_path, period="max": None)
        exit_code = main(["rebuild-data", "SPY"])
        assert exit_code == 0

    def test_main_missing_subcommand_exits_with_error(self) -> None:
        """subcommand 없이 호출 → SystemExit (argparse)."""
        with pytest.raises(SystemExit):
            main([])


# ============================================================================
# .env 자동 로드 (python-dotenv)
# ============================================================================


class TestDotenvLoading:
    """``_load_dotenv_if_present`` 동작을 검증한다."""

    def test_dotenv_injects_variables_when_file_present(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given `.env` 파일이 존재하면 When 로드 호출 시 Then os.environ 에 주입된다."""
        dotenv_path = tmp_path / ".env"
        dotenv_path.write_text(
            "QBT_TEST_DOTENV_KEY=from_env_file\nQBT_TEST_DOTENV_OTHER=xyz\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("QBT_TEST_DOTENV_KEY", raising=False)
        monkeypatch.delenv("QBT_TEST_DOTENV_OTHER", raising=False)

        cli_module._load_dotenv_if_present(dotenv_path=dotenv_path)

        import os

        assert os.environ.get("QBT_TEST_DOTENV_KEY") == "from_env_file"
        assert os.environ.get("QBT_TEST_DOTENV_OTHER") == "xyz"

    def test_dotenv_no_file_is_noop(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given `.env` 파일이 없으면 When 로드 호출 시 Then 예외 없이 통과한다."""
        missing_path = tmp_path / "nonexistent.env"
        assert not missing_path.exists()
        monkeypatch.setenv("QBT_TEST_DOTENV_PREEXIST", "kept")

        cli_module._load_dotenv_if_present(dotenv_path=missing_path)

        import os

        assert os.environ.get("QBT_TEST_DOTENV_PREEXIST") == "kept"

    def test_dotenv_does_not_override_existing_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 기존 env + `.env` 동일 키 When 로드 Then 기존 env 우선 (override=False)."""
        dotenv_path = tmp_path / ".env"
        dotenv_path.write_text(
            "QBT_TEST_DOTENV_OVERRIDE=from_file\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("QBT_TEST_DOTENV_OVERRIDE", "from_actions")

        cli_module._load_dotenv_if_present(dotenv_path=dotenv_path)

        import os

        assert os.environ.get("QBT_TEST_DOTENV_OVERRIDE") == "from_actions"

    def test_project_root_constant_points_to_repo_root(self) -> None:
        """Given ``_PROJECT_ROOT`` 상수 Then 실제 프로젝트 루트를 가리킨다."""
        root = cli_module._PROJECT_ROOT
        assert (root / "pyproject.toml").is_file()
        assert (root / "src" / "live").is_dir()
        assert cli_module._DOTENV_PATH == root / ".env"


# ============================================================================
# data_validator wiring
#
# 참고: ``state_workspace`` 컨텍스트 매니저 자체의 단위 계약(다운로드/업로드/변경
# 감지/예외 시 upload skip 등)은 ``tests/live/test_storage_gateway.py`` 가 검증한다.
# 본 파일은 cli 명령이 그 컨텍스트를 통해 정상 동작하는지에 집중한다.
# ============================================================================


class TestValidateAgainstCsv:
    """순수 함수 ``_validate_against_csv`` 단위 테스트 — OHLC 논리 + 동일 날짜
    CSV vs yfinance 종가 일치를 검증한다."""

    def _make_recent(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def _make_csv(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_passes_on_valid_inputs(self):
        """Given 정상 OHLC + CSV 종가 일치 When 검증 Then 에러 없음."""
        recent = self._make_recent(
            [
                {"Date": date(2026, 4, 8), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
                {"Date": date(2026, 4, 9), "Open": 100.5, "High": 102.0, "Low": 100.0, "Close": 101.0, "Volume": 1000},
            ]
        )
        csv_df = self._make_csv(
            [
                {"Date": date(2026, 4, 8), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
                {"Date": date(2026, 4, 9), "Open": 100.5, "High": 102.0, "Low": 100.0, "Close": 101.0, "Volume": 1000},
            ]
        )
        cli_module._validate_against_csv("SPY", recent, csv_df)  # 예외 없음

    def test_raises_on_high_lt_low(self):
        """Given yfinance 행 중 High<Low 위반 When 검증 Then ValueError."""
        recent = self._make_recent(
            [
                {"Date": date(2026, 4, 10), "Open": 100.0, "High": 90.0, "Low": 95.0, "Close": 92.0, "Volume": 1000},
            ]
        )
        with pytest.raises(ValueError, match="SPY"):
            cli_module._validate_against_csv("SPY", recent, None)

    def test_raises_on_csv_yfinance_close_mismatch(self):
        """Given CSV 의 과거 날짜 종가가 yfinance 와 1% 이상 차이 When 검증 Then ValueError.

        #11 시나리오 재현: 사용자가 CSV 를 $100 으로 조작한 경우.
        """
        recent = self._make_recent(
            [
                {
                    "Date": date(2026, 4, 10),
                    "Open": 450.0,
                    "High": 452.0,
                    "Low": 449.0,
                    "Close": 450.12,
                    "Volume": 1000,
                },
            ]
        )
        csv_df = self._make_csv(
            [
                {"Date": date(2026, 4, 10), "Open": 450.0, "High": 452.0, "Low": 449.0, "Close": 100.0, "Volume": 1000},
            ]
        )
        with pytest.raises(ValueError, match=r"SPY.*전일 종가 불일치"):
            cli_module._validate_against_csv("SPY", recent, csv_df)

    def test_no_csv_skips_prev_close_check(self):
        """Given csv_df=None When 검증 Then OHLC 만 검증하고 종가 비교는 skip."""
        recent = self._make_recent(
            [
                {"Date": date(2026, 4, 10), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
            ]
        )
        cli_module._validate_against_csv("SPY", recent, None)  # 예외 없음

    def test_overlapping_dates_only(self):
        """Given CSV 에 없는 yfinance 날짜는 종가 비교 skip When 겹치는 날짜만 체크."""
        recent = self._make_recent(
            [
                {"Date": date(2026, 4, 9), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
                {"Date": date(2026, 4, 10), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
            ]
        )
        # CSV 에는 4-9 만 있음 (4-10 은 새로 append 될 예정)
        csv_df = self._make_csv(
            [
                {"Date": date(2026, 4, 9), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
            ]
        )
        cli_module._validate_against_csv("SPY", recent, csv_df)  # 예외 없음

    def test_small_diff_below_threshold_passes(self):
        """Given 차이율이 1% 미만 (정상 라운딩 오차) When 검증 Then 통과."""
        recent = self._make_recent(
            [
                {"Date": date(2026, 4, 10), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
            ]
        )
        csv_df = self._make_csv(
            [
                # 0.5% 차이 — 임계값 1% 미만
                {"Date": date(2026, 4, 10), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0, "Volume": 1000},
            ]
        )
        cli_module._validate_against_csv("SPY", recent, csv_df)  # 예외 없음

    def test_date_gap_detected_when_calendar_provided(self):
        """Given CSV 가 월요일까지 있고 trade_date 가 목요일 (수요일 거래일 누락)
        When validate_date_gap 까지 검증 Then ValueError.

        FakeCalendar 로 ``exchange_calendars`` 의존성을 주입 (실제 NYSE 호출 없음).
        """

        class _FakeCalendar:
            """(csv_last, today) 사이의 모든 날짜를 영업일로 간주."""

            def sessions_in_range(self, start, end):
                import pandas as _pd

                return _pd.date_range(start.date(), end.date(), freq="D")

        recent = self._make_recent(
            [
                {"Date": date(2026, 4, 9), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
            ]
        )
        csv_df = self._make_csv(
            [
                # CSV 마지막 = 4월 6일
                {"Date": date(2026, 4, 6), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
            ]
        )

        with pytest.raises(ValueError, match=r"SPY.*거래일 누락"):
            cli_module._validate_against_csv(
                "SPY",
                recent,
                csv_df,
                trade_date=date(2026, 4, 9),
                calendar=_FakeCalendar(),
            )

    def test_date_gap_not_checked_when_calendar_none(self):
        """Given calendar 미주입 When 검증 Then gap 검증 skip (기존 동작 유지)."""
        recent = self._make_recent(
            [
                {"Date": date(2026, 4, 9), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
            ]
        )
        csv_df = self._make_csv(
            [
                {"Date": date(2026, 4, 6), "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1000},
            ]
        )
        cli_module._validate_against_csv("SPY", recent, csv_df, trade_date=None, calendar=None)  # 예외 없음


class TestRunDailyValidatorIntegration:
    """``run-daily`` 파이프라인에서 validator 가 실패 시 RuntimeError 전파 +
    notify_failure 호출까지 가는지 통합 검증."""

    def _setup_state(self, state_dir: Path) -> None:
        _create_state_file(state_dir)
        assert (state_dir / "live_state.json").exists()

    def test_ohlc_logic_failure_aborts_and_notifies(self, state_dir: Path, monkeypatch):
        """Given yfinance 가 High<Low 인 행을 반환 When run-daily Then RuntimeError + notify."""
        self._setup_state(state_dir)
        _setup_flat_market_csvs(state_dir, date(2026, 4, 10))

        def _bad_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            # High=90, Low=95 → 논리 위반
            return pd.DataFrame(
                {
                    "Date": [date(2026, 4, 10)],
                    "Open": [100.0],
                    "High": [90.0],
                    "Low": [95.0],
                    "Close": [92.0],
                    "Volume": [1000],
                }
            )

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _bad_fetch)
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)

        notify_calls: list[str] = []
        monkeypatch.setattr(
            cli_module,
            "_safe_notify_failure",
            lambda app, msg: notify_calls.append(msg),
        )

        exit_code = main(["run-daily", "--trade-date", "2026-04-10"])

        assert exit_code == 1
        assert len(notify_calls) >= 1
        assert any("검증" in msg or "OHLC" in msg or "High" in msg for msg in notify_calls)

    def test_newly_applied_fills_persist_to_user_trades_jsonl(self, state_dir: Path, monkeypatch):
        """Given RTDB 에 새 fill 도착 When run-daily Then history/user_trades.jsonl 에 append."""
        _create_state_file(state_dir)
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)

        # Firebase 초기화 mock — fake app 반환
        fake_app = object()
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: fake_app)

        # 새 fill 1 건 주입 (sso buy)
        from live.models import ActualFill

        new_fill = ActualFill(
            asset_id="sso",
            direction="buy",
            actual_price=82.0,
            actual_shares=420,
            trade_date="2026-04-10",
            input_time_kst="2026-04-10T20:00:00+09:00",
            memo=None,
            rtdb_key="fill_new_001",
        )
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_fills", lambda app: [new_fill])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_balance_adjusts", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_fill_dismisses", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_model_syncs", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fill_dismisses_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_model_syncs_processed", lambda app, keys: None)

        # /history/fills/ 미러 호출 추적 (PLAN_LIVE_HISTORY_RTDB_MIRROR)
        history_fill_calls: list[tuple[list[Any], str]] = []
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_history_fills",
            lambda app, fills, applied_at: history_fill_calls.append((list(fills), applied_at)),
        )

        monkeypatch.setattr(cli_module, "_publish_to_rtdb", lambda *a, **kw: None)
        monkeypatch.setattr(cli_module, "_send_daily_notifications", lambda app, result: None)

        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])
        assert exit_code == 0

        # user_trades.jsonl 에 fill 기록 검증 (확장 스키마)
        user_trades_path = state_dir / "history" / "user_trades.jsonl"
        assert user_trades_path.exists()
        lines = user_trades_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert '"asset_id": "sso"' in lines[0]
        assert '"direction": "buy"' in lines[0]
        assert '"date": "2026-04-10"' in lines[0]
        # 확장 스키마: actual_price / actual_shares / rtdb_key / applied_at 포함
        assert '"actual_price": 82.0' in lines[0]
        assert '"actual_shares": 420' in lines[0]
        assert '"rtdb_key": "fill_new_001"' in lines[0]
        assert '"applied_at"' in lines[0]

        # /history/fills/ 미러 호출: 신규 fill 1 건만 전달
        assert len(history_fill_calls) == 1
        mirrored_fills, applied_at_value = history_fill_calls[0]
        assert len(mirrored_fills) == 1
        assert mirrored_fills[0].rtdb_key == "fill_new_001"
        # applied_at 은 KST ISO 8601 형식
        assert applied_at_value.endswith("+09:00")

    def test_already_applied_fill_is_not_re_appended(self, state_dir: Path, monkeypatch):
        """Given applied_fill_ids.json 에 이미 있는 fill When run-daily Then user_trades 에 추가되지 않음."""
        _create_state_file(state_dir)
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        # applied_fill_ids.json 에 fill_existing 을 미리 주입
        import json

        applied_path = state_dir / "applied_fill_ids.json"
        applied_path.write_text(json.dumps({"fill_existing": "2026-04-09T00:00:00+09:00"}), encoding="utf-8")

        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)

        fake_app = object()
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: fake_app)

        from live.models import ActualFill

        existing_fill = ActualFill(
            asset_id="gld",
            direction="buy",
            actual_price=180.0,
            actual_shares=100,
            trade_date="2026-04-09",
            input_time_kst="2026-04-09T20:00:00+09:00",
            memo=None,
            rtdb_key="fill_existing",
        )
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_fills", lambda app: [existing_fill])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_balance_adjusts", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_fill_dismisses", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_model_syncs", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fill_dismisses_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_model_syncs_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module, "_publish_to_rtdb", lambda *a, **kw: None)
        monkeypatch.setattr(cli_module, "_send_daily_notifications", lambda app, result: None)

        main(["run-daily", "--trade-date", trade_date.isoformat()])

        # user_trades.jsonl 은 존재하지 않거나 비어있음 (기존 fill 은 skip)
        user_trades_path = state_dir / "history" / "user_trades.jsonl"
        if user_trades_path.exists():
            content = user_trades_path.read_text(encoding="utf-8").strip()
            assert content == "", f"기존 fill 이 중복 append 되었음: {content}"

    def test_holiday_early_exit_skips_state_workspace(self, state_dir: Path, monkeypatch):
        """Given 휴장일 trade_date When run-daily (cron 모드) Then state_workspace 진입 없이 exit 0."""
        del state_dir  # fixture 설치만 필요
        # 휴장 체크 강제: 항상 False
        monkeypatch.setattr(cli_module, "_is_nyse_session", lambda d: False)

        # storage_gateway.state_workspace 가 호출되면 실패하도록 sentinel 주입
        def _fail_workspace(**kwargs):
            raise AssertionError("휴장일에 state_workspace 가 호출되면 안 됨")

        monkeypatch.setattr(cli_module.storage_gateway, "state_workspace", _fail_workspace)

        # cron 모드 (no --trade-date)
        exit_code = main(["run-daily"])
        assert exit_code == 0

    def test_holiday_bypassed_when_trade_date_explicit(self, state_dir: Path, monkeypatch):
        """Given 휴장 체크는 False 이지만 --trade-date 명시 When run-daily Then 정상 진행."""
        _create_state_file(state_dir)
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        monkeypatch.setattr(cli_module, "_is_nyse_session", lambda d: False)  # 휴장으로 보여도
        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", lambda t, days=5: _make_recent_df(trade_date))
        _mock_rtdb_for_cli(monkeypatch)

        # --trade-date 명시 → 휴장 체크 bypass
        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])
        assert exit_code == 0

    def test_idempotency_blocks_duplicate_cron_run(self, state_dir: Path, monkeypatch):
        """Given state.last_model_execution_date == trade_date When cron 재실행 Then 조기 종료."""
        _create_state_file(state_dir)

        today = date.today()
        # state 를 수동 수정: last_model_execution_date 를 오늘로 세팅
        import json

        state_path = state_dir / "live_state.json"
        state_dict = json.loads(state_path.read_text(encoding="utf-8"))
        state_dict["last_model_execution_date"] = today.isoformat()
        state_path.write_text(json.dumps(state_dict, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(cli_module, "_is_nyse_session", lambda d: True)  # 영업일 가정

        # 이후 단계가 호출되면 실패하도록 sentinel
        def _fail_fetch(*a, **kw):
            raise AssertionError("idempotency 체크 통과 후 불필요한 단계 진입")

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _fail_fetch)

        # cron 모드 (no --trade-date) → 조기 종료
        exit_code = main(["run-daily"])
        assert exit_code == 0

    def test_balance_adjust_applied_and_audited(self, state_dir: Path, monkeypatch):
        """Given RTDB 에 balance_adjust 1 건 When run-daily Then state 반영 + audit append + mark_processed."""
        _create_state_file(state_dir)
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", lambda t, days=5: _make_recent_df(trade_date))
        fake_app = object()
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: fake_app)
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_fills", lambda app: [])

        from live.models import BalanceAdjust

        adjust = BalanceAdjust(
            rtdb_key="adj_001",
            input_time_kst="2026-04-10T20:00:00+09:00",
            reason="테스트 잔고 보정",
            asset_id="sso",
            new_shares=420,
            new_cash=None,
        )
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_balance_adjusts", lambda app: [adjust])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_fill_dismisses", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_model_syncs", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_model_syncs_processed", lambda app, keys: None)

        mark_calls: list[list[str]] = []
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "mark_balance_adjusts_processed",
            lambda app, keys: mark_calls.append(list(keys)),
        )
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fill_dismisses_processed", lambda app, keys: None)

        # /history/balance_adjusts/ 미러 호출 추적 (PLAN_LIVE_HISTORY_RTDB_MIRROR)
        history_adjust_calls: list[tuple[list[Any], str]] = []
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_history_balance_adjusts",
            lambda app, adjusts, applied_at: history_adjust_calls.append((list(adjusts), applied_at)),
        )

        monkeypatch.setattr(cli_module, "_publish_to_rtdb", lambda *a, **kw: None)
        monkeypatch.setattr(cli_module, "_send_daily_notifications", lambda app, result: None)

        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])
        assert exit_code == 0

        # state 반영 확인
        from live.state import load_state

        new_state = load_state(state_dir / "live_state.json")
        assert new_state.assets["sso"].actual_shares == 420

        # audit 파일 생성 확인 (확장 스키마: applied_at 포함)
        audit_path = state_dir / "history" / "balance_adjusts.jsonl"
        assert audit_path.exists()
        content = audit_path.read_text(encoding="utf-8").strip()
        assert "adj_001" in content
        assert '"asset_id": "sso"' in content
        assert '"new_shares": 420' in content
        assert '"applied_at"' in content

        # RTDB mark 호출 확인
        assert len(mark_calls) == 1
        assert mark_calls[0] == ["adj_001"]

        # /history/balance_adjusts/ 미러 호출 — 신규 adjust 1 건 + applied_at 동일 부여
        assert len(history_adjust_calls) == 1
        mirrored_adjusts, applied_at_value = history_adjust_calls[0]
        assert len(mirrored_adjusts) == 1
        assert mirrored_adjusts[0].rtdb_key == "adj_001"
        assert applied_at_value.endswith("+09:00")

        # applied_balance_adjust_ids.json 에 기록 확인
        import json as _json

        adjust_ids_path = state_dir / "applied_balance_adjust_ids.json"
        assert adjust_ids_path.exists()
        ids_data = _json.loads(adjust_ids_path.read_text(encoding="utf-8"))
        assert "adj_001" in ids_data

    def test_already_applied_balance_adjust_is_not_re_audited(self, state_dir: Path, monkeypatch):
        """Given applied_balance_adjust_ids.json 에 이미 있음 When run-daily Then audit skip + mark skip."""
        _create_state_file(state_dir)
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        # applied_balance_adjust_ids.json 미리 세팅
        import json as _json

        adjust_ids_path = state_dir / "applied_balance_adjust_ids.json"
        adjust_ids_path.write_text(
            _json.dumps({"adj_existing": "2026-04-09T00:00:00+09:00"}),
            encoding="utf-8",
        )

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", lambda t, days=5: _make_recent_df(trade_date))
        fake_app = object()
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: fake_app)
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_fills", lambda app: [])

        from live.models import BalanceAdjust

        existing_adjust = BalanceAdjust(
            rtdb_key="adj_existing",
            input_time_kst="2026-04-09T20:00:00+09:00",
            reason="이전 보정",
            asset_id="gld",
            new_shares=500,
            new_cash=None,
        )
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_balance_adjusts", lambda app: [existing_adjust])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_fill_dismisses", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_model_syncs", lambda app: [])
        mark_calls: list[list[str]] = []
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "mark_balance_adjusts_processed",
            lambda app, keys: mark_calls.append(list(keys)),
        )
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fill_dismisses_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_model_syncs_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module, "_publish_to_rtdb", lambda *a, **kw: None)
        monkeypatch.setattr(cli_module, "_send_daily_notifications", lambda app, result: None)

        main(["run-daily", "--trade-date", trade_date.isoformat()])

        # state 변경 없음 (이미 처리된 adjust)
        from live.state import load_state

        new_state = load_state(state_dir / "live_state.json")
        assert new_state.assets["gld"].actual_shares == 0

        # audit jsonl 은 없거나 비어있음
        audit_path = state_dir / "history" / "balance_adjusts.jsonl"
        if audit_path.exists():
            content = audit_path.read_text(encoding="utf-8").strip()
            assert content == "", f"기존 adjust 가 중복 audit 되었음: {content}"

        # RTDB mark 도 호출되지 않음
        assert mark_calls == []

    def test_model_sync_inbox_applied_and_marked(self, state_dir: Path, monkeypatch):
        """Given RTDB model_sync inbox 1 건 When run-daily Then model=actual 반영 + mark_processed 호출.

        앱이 /model_sync/inbox/{uuid} 에 요청 1 건을 썼다고 가정.
        - Stage 2.6 balance_adjust 로 actual 만 먼저 수정 (sso new_shares=200).
        - Stage 2.7 model_sync 가 "model = actual" 덮어쓰기 → model_shares=200 으로 수렴.
        - 실행 후 mark_model_syncs_processed 가 해당 rtdb_key 와 함께 호출되어야 한다.
        """
        _create_state_file(state_dir)
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", lambda t, days=5: _make_recent_df(trade_date))
        fake_app = object()
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: fake_app)
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_fills", lambda app: [])

        from live.models import BalanceAdjust, ModelSync

        # 같은 배치에 balance_adjust + model_sync → actual 을 먼저 수정한 뒤 model 복사.
        adjust = BalanceAdjust(
            rtdb_key="adj_pre_sync",
            input_time_kst="2026-04-10T19:00:00+09:00",
            reason="sync rehearsal",
            asset_id="sso",
            new_shares=200,
            new_avg_price=80.0,
            new_entry_date="2026-03-15",
        )
        sync = ModelSync(
            rtdb_key="sync_cli_001",
            input_time_kst="2026-04-10T20:00:00+09:00",
        )
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_balance_adjusts", lambda app: [adjust])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_pending_fill_dismisses", lambda app: [])
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_model_syncs", lambda app: [sync])
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_balance_adjusts_processed", lambda app, keys: None)
        monkeypatch.setattr(cli_module.rtdb_gateway, "mark_fill_dismisses_processed", lambda app, keys: None)

        mark_sync_calls: list[list[str]] = []
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "mark_model_syncs_processed",
            lambda app, keys: mark_sync_calls.append(list(keys)),
        )
        monkeypatch.setattr(
            cli_module.rtdb_gateway,
            "write_history_balance_adjusts",
            lambda app, adjusts, applied_at: None,
        )

        monkeypatch.setattr(cli_module, "_publish_to_rtdb", lambda *a, **kw: None)
        monkeypatch.setattr(cli_module, "_send_daily_notifications", lambda app, result: None)

        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])
        assert exit_code == 0

        # state 반영 확인 — Stage 2.6 의 adjust 로 actual 변경, Stage 2.7 의 sync 로 model = actual.
        from live.state import load_state

        new_state = load_state(state_dir / "live_state.json")
        assert new_state.assets["sso"].actual_shares == 200
        assert new_state.assets["sso"].model_shares == 200

        # mark_model_syncs_processed 가 rtdb_key 와 함께 호출되었는지 검증
        assert len(mark_sync_calls) == 1
        assert mark_sync_calls[0] == ["sync_cli_001"]

        # history/daily/{date}.json 에 model_sync_applied=True 기록 (영구 추적)
        import json as _json

        daily_path = state_dir / "history" / "daily" / f"{trade_date.isoformat()}.json"
        assert daily_path.exists()
        daily_payload = _json.loads(daily_path.read_text(encoding="utf-8"))
        assert daily_payload.get("model_sync_applied") is True

    def test_idempotency_bypassed_when_trade_date_explicit(self, state_dir: Path, monkeypatch):
        """Given 같은 날짜 state 이미 처리 + --trade-date 명시 When Then 실행 진행."""
        _create_state_file(state_dir)
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        # state 의 last_model_execution_date 를 trade_date 로 세팅
        import json

        state_path = state_dir / "live_state.json"
        state_dict = json.loads(state_path.read_text(encoding="utf-8"))
        state_dict["last_model_execution_date"] = trade_date.isoformat()
        state_path.write_text(json.dumps(state_dict, ensure_ascii=False), encoding="utf-8")

        monkeypatch.setattr(cli_module, "_is_nyse_session", lambda d: True)
        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", lambda t, days=5: _make_recent_df(trade_date))
        _mock_rtdb_for_cli(monkeypatch)

        # --trade-date 명시 → idempotency bypass
        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])
        assert exit_code == 0

    def test_csv_manipulation_detected_as_prev_close_mismatch(self, state_dir: Path, monkeypatch):
        """Given 사용자가 CSV 종가를 조작 (#11 시나리오) When run-daily Then RuntimeError.

        yfinance 가 반환한 2026-04-10 종가(정상 100.5) 와 CSV 에 저장된 2026-04-10 종가
        (조작된 50.0) 가 50% 차이 → validate_prev_close 트리거.
        """
        self._setup_state(state_dir)
        _setup_flat_market_csvs(state_dir, date(2026, 4, 10))

        # CSV 의 2026-04-10 행을 직접 조작 (SPY 만)
        spy_path = state_dir / "data" / "stock" / "SPY.csv"
        df = pd.read_csv(spy_path)
        df.loc[df["Date"].astype(str) == "2026-04-10", "Close"] = 50.0
        df.to_csv(spy_path, index=False)

        def _normal_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            # yfinance 는 정상 값(100.5) 반환
            return _make_recent_df(date(2026, 4, 10))

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _normal_fetch)
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)

        notify_calls: list[str] = []
        monkeypatch.setattr(
            cli_module,
            "_safe_notify_failure",
            lambda app, msg: notify_calls.append(msg),
        )

        exit_code = main(["run-daily", "--trade-date", "2026-04-10"])

        assert exit_code == 1
        assert len(notify_calls) >= 1
        assert any("종가 불일치" in msg or "검증" in msg for msg in notify_calls)


# ============================================================================
# _build_market_bundle 공통 기간 필터링
# ============================================================================


class TestBuildMarketBundleCommonPeriod:
    """_build_market_bundle 이 서로 다른 날짜 범위를 가진 자산들을
    공통 기간(교집합)으로 정렬하는지 검증한다."""

    def test_different_date_ranges_aligned_to_common_period(self, tmp_path: Path) -> None:
        """
        목적: trade_df 시작일이 다른 자산들이 교집합으로 정렬되는지 검증.

        Given: SSO(2006-06-21~), GLD(2004-11-18~) 등 서로 다른 시작일을 가진 CSV
        When: _build_market_bundle 호출
        Then: 모든 자산의 trade_df 날짜 집합이 동일 (교집합)
        """
        from live.cli import _build_market_bundle

        stock_dir = tmp_path / "data" / "stock"
        stock_dir.mkdir(parents=True, exist_ok=True)

        # 공통 기간 (5일)
        common_dates = [date(2026, 4, i) for i in range(1, 6)]
        # GLD 에만 있는 추가 날짜 (2일)
        extra_dates = [date(2026, 3, 30), date(2026, 3, 31)]

        def _make_csv(dates: list[date]) -> pd.DataFrame:
            n = len(dates)
            return pd.DataFrame(
                {
                    "Date": dates,
                    "Open": [100.0] * n,
                    "High": [100.5] * n,
                    "Low": [99.5] * n,
                    "Close": [100.0] * n,
                    "Volume": [1_000_000] * n,
                }
            )

        # GLD 는 extra_dates + common_dates, 나머지 티커는 common_dates 만
        for ticker in _collect_all_tickers():
            if ticker == "GLD":
                df = _make_csv(extra_dates + common_dates)
            else:
                df = _make_csv(common_dates)
            df.to_csv(stock_dir / f"{ticker}.csv", index=False)

        bundle = _build_market_bundle(tmp_path)

        # 모든 자산의 trade_df 날짜 집합이 동일해야 한다
        date_sets = [set(data.trade_df["Date"].tolist()) for data in bundle.values()]
        reference = date_sets[0]
        for ds in date_sets[1:]:
            assert ds == reference

        # 교집합 = common_dates (5일)
        assert reference == set(common_dates)

    def test_signal_df_also_filtered_to_common_period(self, tmp_path: Path) -> None:
        """
        목적: signal_df 도 공통 기간으로 필터링되는지 검증.

        Given: signal 티커와 trade 티커가 다른 자산 (예: SSO → SPY signal)
        When: _build_market_bundle 호출
        Then: signal_df 도 trade_df 와 동일한 공통 기간으로 필터링됨
        """
        from live.cli import _build_market_bundle

        stock_dir = tmp_path / "data" / "stock"
        stock_dir.mkdir(parents=True, exist_ok=True)

        common_dates = [date(2026, 4, i) for i in range(1, 6)]
        extra_dates = [date(2026, 3, 30), date(2026, 3, 31)]

        def _make_csv(dates: list[date]) -> pd.DataFrame:
            n = len(dates)
            return pd.DataFrame(
                {
                    "Date": dates,
                    "Open": [100.0] * n,
                    "High": [100.5] * n,
                    "Low": [99.5] * n,
                    "Close": [100.0] * n,
                    "Volume": [1_000_000] * n,
                }
            )

        for ticker in _collect_all_tickers():
            if ticker == "GLD":
                df = _make_csv(extra_dates + common_dates)
            else:
                df = _make_csv(common_dates)
            df.to_csv(stock_dir / f"{ticker}.csv", index=False)

        bundle = _build_market_bundle(tmp_path)

        # signal_df 도 공통 기간으로 잘려야 한다
        for asset_id, data in bundle.items():
            signal_dates = set(data.signal_df["Date"].tolist())
            trade_dates = set(data.trade_df["Date"].tolist())
            assert signal_dates == trade_dates, f"{asset_id}: signal_df/trade_df 날짜 불일치"
