"""live.cli 알림 커버리지 계약을 검증한다."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from live import cli as cli_module
from live.cli import _collect_all_tickers, main

# ============================================================================
# 공통 fixture / 헬퍼
# ============================================================================


@pytest.fixture
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``cli_module.ephemeral_state_repo`` 를 ``tmp_path`` 로 교체하여 state 를 격리한다."""

    @contextmanager
    def fake_ephemeral(*, push_on_success: bool, commit_subcommand: str):
        del push_on_success, commit_subcommand
        yield tmp_path

    monkeypatch.setattr(cli_module, "ephemeral_state_repo", fake_ephemeral)
    return tmp_path


def _spy_notify(calls: list[tuple[Any, str]]):
    """``_safe_notify_failure`` 를 대체할 spy 함수."""

    def _inner(rtdb_app: Any, message: str) -> None:
        calls.append((rtdb_app, message))

    return _inner


def _install_notify_spy(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[Any, str]]:
    """테스트용 notify spy 를 설치하고 호출 기록 리스트를 반환한다."""
    calls: list[tuple[Any, str]] = []
    monkeypatch.setattr(cli_module, "_safe_notify_failure", _spy_notify(calls))
    return calls


def _make_recent_df(trade_date: date) -> pd.DataFrame:
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


def _setup_flat_csvs(state_dir: Path, trade_date: date, rows: int = 210) -> None:
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
# main() 공통 알림 훅: allow-list 정책 (run-daily 만 알림)
# ============================================================================


class TestMainAllowListNotifyPolicy:
    """``main()`` 공통 예외 훅은 **자동 실행 커맨드 (run-daily)** 실패에만
    FCM + 텔레그램 알림을 발송한다 (allow-list 정책).

    사용자 직접 실행 커맨드 (init / reset / rebuild-data / drift / fetch-fills /
    backfill-chart-years) 는 터미널 stderr + ERROR 로그로만 실패를 노출하며,
    알림은 발송하지 않는다. ``notify-failure`` 는 재귀 방지를 위해 allow-list 에
    포함하지 않는다 (allow-list 에 없으므로 자동 제외).
    """

    @pytest.mark.parametrize(
        "command_args",
        [
            ["init", "--capital", "100000000"],
            ["reset", "--capital", "100000000"],
            ["rebuild-data", "SPY"],
            ["rebuild-data"],
            ["drift"],
            ["fetch-fills"],
            ["backfill-chart-years"],
        ],
    )
    def test_user_executed_command_failure_does_not_notify(
        self,
        command_args: list[str],
        state_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Given 사용자 직접 실행 커맨드의 func 가 예외 raise When main 실행
        Then _safe_notify_failure 호출되지 않고 exit 1 반환.
        """
        del state_dir
        notify_calls = _install_notify_spy(monkeypatch)

        def _fail(_args: Any) -> int:
            raise RuntimeError("테스트용 강제 실패")

        for attr_name in (
            "_cmd_init",
            "_cmd_reset",
            "_cmd_rebuild_data",
            "_cmd_drift",
            "_cmd_fetch_fills",
            "_cmd_backfill_chart_years",
        ):
            monkeypatch.setattr(cli_module, attr_name, _fail)

        exit_code = main(command_args)

        assert exit_code == 1
        assert notify_calls == [], f"{command_args[0]} 실패 시 notify 호출되면 안 됨 (allow-list 정책)"

    def test_run_daily_failure_still_notifies(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given run-daily 실행 중 예외 When main 실행 Then _safe_notify_failure 1 회 호출."""
        del state_dir
        notify_calls = _install_notify_spy(monkeypatch)

        def _fail(_args: Any) -> int:
            raise RuntimeError("테스트용 run-daily 실패")

        monkeypatch.setattr(cli_module, "_cmd_run_daily", _fail)

        exit_code = main(["run-daily"])

        assert exit_code == 1
        assert len(notify_calls) == 1
        assert "run-daily" in notify_calls[0][1]


# ============================================================================
# notify-failure 재귀 방지
# ============================================================================


class TestNotifyFailureCommandNoRecursion:
    """``notify-failure`` 커맨드 자체가 실패해도 ``_safe_notify_failure`` 를
    재귀 호출하지 않아야 한다. 알림 명령 자체의 실패에 대해 알림을 다시
    보내는 것은 무한 루프 / 토큰 낭비를 유발한다.
    """

    def test_notify_failure_command_calls_safe_notify_exactly_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given notify-failure 커맨드 When 정상 실행 Then _safe_notify_failure 1 회만 호출."""
        call_count = {"count": 0}

        def _counting_notify(rtdb_app: Any, message: str) -> None:
            call_count["count"] += 1

        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)
        monkeypatch.setattr(cli_module, "_safe_notify_failure", _counting_notify)

        exit_code = main(["notify-failure", "-m", "테스트 알림"])

        assert exit_code == 0
        assert call_count["count"] == 1  # main 훅에서 중복 호출되지 않아야 함

    def test_notify_failure_command_even_on_rtdb_init_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given notify-failure 에서 rtdb_app 초기화 예외 When main 실행 Then _safe_notify_failure 재귀 호출 없음."""
        call_count = {"count": 0}

        def _counting_notify(rtdb_app: Any, message: str) -> None:
            call_count["count"] += 1

        def _failing_init() -> Any:
            raise RuntimeError("테스트: rtdb 초기화 중 예외")

        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", _failing_init)
        monkeypatch.setattr(cli_module, "_safe_notify_failure", _counting_notify)

        exit_code = main(["notify-failure", "-m", "테스트"])

        # notify-failure 에서 rtdb 초기화 실패 → main 훅이 캐치하더라도
        # 재귀 방지로 _safe_notify_failure 는 호출되지 않아야 한다
        assert exit_code == 1
        assert call_count["count"] == 0, "notify-failure 커맨드 실패 시 _safe_notify_failure 재귀 호출 금지"


# ============================================================================
# _cmd_run_daily 진입 전 코드 알림 커버리지
# ============================================================================


class TestRunDailyPreTryCoverage:
    """``_cmd_run_daily`` 의 try 블록 진입 전 코드에서 발생한 예외도 알림 훅을 통과해야 한다."""

    def test_invalid_trade_date_triggers_notify(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 잘못된 --trade-date 문자열 When main 실행 Then notify 호출."""
        notify_calls = _install_notify_spy(monkeypatch)

        exit_code = main(["run-daily", "--trade-date", "2026-13-40"])

        assert exit_code == 1
        assert len(notify_calls) >= 1

    def test_nyse_session_check_failure_triggers_notify(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given _is_nyse_session 내부에서 예외 When cron 모드 실행 Then notify 호출."""
        notify_calls = _install_notify_spy(monkeypatch)

        def _failing_session(d: date) -> bool:
            raise RuntimeError("테스트: NYSE 달력 로드 실패")

        monkeypatch.setattr(cli_module, "_is_nyse_session", _failing_session)

        exit_code = main(["run-daily"])

        assert exit_code == 1
        assert len(notify_calls) >= 1


# ============================================================================
# history 저장 실패 → raise + notify (silent continue 금지)
# ============================================================================


class TestHistoryPersistFailureRaises:
    """``_persist_history`` 실패 시 RuntimeError 로 전파되어 알림 훅에 도달해야 한다."""

    def _init_state(self) -> None:
        main(["init", "--capital", "100000000"])

    def test_history_save_failure_aborts_run_daily(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given _persist_history 실패 When run-daily Then exit 1 + notify."""
        self._init_state()
        trade_date = date(2026, 4, 10)
        _setup_flat_csvs(state_dir, trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", lambda t, days=5: _make_recent_df(trade_date))
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)

        def _failing_persist(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("테스트: 히스토리 저장 실패")

        monkeypatch.setattr(cli_module, "_persist_history", _failing_persist)
        notify_calls = _install_notify_spy(monkeypatch)

        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])

        assert exit_code == 1, "history 저장 실패가 silent continue 되어 exit 0 반환 — fallback 제거 필요"
        assert len(notify_calls) >= 1, "history 저장 실패 시 notify 호출 누락"


# ============================================================================
# calendar 로드 실패 → raise + notify (fallback 금지)
# ============================================================================


class TestCalendarLoadFailureRaises:
    """``_get_nyse_calendar()`` 실패 시 RuntimeError 로 전파되어야 한다 (fallback 금지)."""

    def _init_state(self) -> None:
        main(["init", "--capital", "100000000"])

    def test_calendar_load_failure_aborts_run_daily(self, state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given _get_nyse_calendar 실패 When run-daily Then exit 1 + notify."""
        self._init_state()
        trade_date = date(2026, 4, 10)
        _setup_flat_csvs(state_dir, trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", lambda t, days=5: _make_recent_df(trade_date))
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)

        # _is_nyse_session 은 정상 통과 (휴장 체크용 별도 경로)
        monkeypatch.setattr(cli_module, "_is_nyse_session", lambda d: True)

        # _get_nyse_calendar 만 실패 → _refresh_live_csvs 경로에서 폭발
        def _failing_calendar() -> Any:
            raise RuntimeError("테스트: exchange_calendars 로드 실패")

        monkeypatch.setattr(cli_module, "_get_nyse_calendar", _failing_calendar)
        notify_calls = _install_notify_spy(monkeypatch)

        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])

        assert exit_code == 1, "calendar 로드 실패가 fallback 으로 흡수되어 exit 0 반환 — fallback 제거 필요"
        assert len(notify_calls) >= 1, "calendar 로드 실패 시 notify 호출 누락"
