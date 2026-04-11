"""live.cli 진입점 및 명령어 통합 테스트.

TODO T-10.1 ~ T-10.3 시나리오 고정.

테스트 원칙:
- 실제 yfinance 호출 금지 (monkeypatch 로 live.data_fetcher 내부 함수 교체)
- 파일 I/O 는 tmp_path 로 격리
- notify_failure 훅은 monkeypatch 로 감시
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from live import cli as cli_module
from live.cli import main
from live.state import load_state

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


def _setup_flat_market_csvs(state_dir: Path, trade_date: date, rows: int = 210) -> None:
    """state_dir/data/stock/ 에 6 종 티커의 평탄 CSV 를 미리 준비한다.

    MA(200) 워밍업을 위해 충분한 행을 생성.
    """
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
    for ticker in ("SPY", "QQQ", "SSO", "QLD", "GLD", "TLT"):
        df.to_csv(stock_dir / f"{ticker}.csv", index=False)


# ============================================================================
# init 명령어
# ============================================================================


class TestCmdInit:
    def test_init_creates_live_state_json_t_10_1(self, tmp_path: Path):
        """T-10.1: init --capital 100000000 → live_state.json 생성 + 4 자산 초기화."""
        exit_code = main(
            [
                "init",
                "--capital",
                "100000000",
                "--state-dir",
                str(tmp_path),
            ]
        )
        assert exit_code == 0
        state_path = tmp_path / "live_state.json"
        assert state_path.exists()

        loaded = load_state(state_path)
        assert loaded.portfolio_id == "portfolio_q2_2xs"
        assert loaded.shared_cash_model == pytest.approx(100_000_000.0)
        assert loaded.shared_cash_actual == pytest.approx(100_000_000.0)
        assert set(loaded.assets.keys()) == {"sso", "qld", "gld", "tlt"}

    def test_init_creates_parent_directory(self, tmp_path: Path):
        """state-dir 가 없을 때 자동 생성."""
        target_dir = tmp_path / "nested" / "live-state"
        exit_code = main(
            [
                "init",
                "--capital",
                "50000000",
                "--state-dir",
                str(target_dir),
            ]
        )
        assert exit_code == 0
        assert (target_dir / "live_state.json").exists()

    def test_init_negative_capital_fails(self, tmp_path: Path):
        """음수 capital → 실패 (exit code 1)."""
        exit_code = main(
            [
                "init",
                "--capital",
                "-1000",
                "--state-dir",
                str(tmp_path),
            ]
        )
        assert exit_code == 1


# ============================================================================
# run-daily 에러 시나리오
# ============================================================================


class TestCmdRunDailyFailures:
    def _init_state(self, tmp_path: Path) -> None:
        """상태 파일 초기화."""
        main(["init", "--capital", "100000000", "--state-dir", str(tmp_path)])

    def test_data_fetch_failure_calls_notify_t_10_2(self, tmp_path: Path, monkeypatch):
        """T-10.2: data 수집 중 실패 → 중단 + _safe_notify_failure 호출."""
        self._init_state(tmp_path)

        # monkeypatch: fetch_recent_ohlc 가 ValueError 발생
        def _failing_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            raise ValueError(f"테스트: yfinance 실패 {ticker}")

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _failing_fetch)

        notify_calls: list[str] = []

        def _spy_notify(rtdb_app, message: str) -> None:  # noqa: ANN001
            notify_calls.append(message)

        monkeypatch.setattr(cli_module, "_safe_notify_failure", _spy_notify)

        exit_code = main(
            [
                "run-daily",
                "--state-dir",
                str(tmp_path),
                "--trade-date",
                "2026-04-10",
                "--no-rtdb",
            ]
        )

        # exit code 는 main 의 try/except 에서 1 반환
        assert exit_code == 1
        assert len(notify_calls) >= 1
        assert any("yfinance" in msg or "검증" in msg or "실패" in msg or "데이터" in msg for msg in notify_calls)

    def test_calculation_failure_state_unchanged_t_10_3(self, tmp_path: Path, monkeypatch):
        """T-10.3: run_daily 내부 계산 실패 → 중단 + 상태 파일 변경 없음."""
        self._init_state(tmp_path)
        state_path = tmp_path / "live_state.json"
        original_mtime = state_path.stat().st_mtime

        # CSV 준비
        _setup_flat_market_csvs(tmp_path, date(2026, 4, 10))

        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(date(2026, 4, 10))

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)

        # run_daily 호출을 실패하도록 monkeypatch
        def _failing_run_daily(*args, **kwargs):  # noqa: ANN202
            raise RuntimeError("테스트: 엔진 내부 계산 실패")

        monkeypatch.setattr(cli_module, "run_daily", _failing_run_daily)

        notify_calls: list[str] = []
        monkeypatch.setattr(
            cli_module,
            "_safe_notify_failure",
            lambda app, msg: notify_calls.append(msg),
        )

        exit_code = main(
            [
                "run-daily",
                "--state-dir",
                str(tmp_path),
                "--trade-date",
                "2026-04-10",
                "--no-rtdb",
            ]
        )

        assert exit_code == 1
        assert len(notify_calls) >= 1
        assert any("엔진" in msg or "계산" in msg or "실행" in msg for msg in notify_calls)

        # 상태 파일 변경 없음
        assert state_path.stat().st_mtime == original_mtime


# ============================================================================
# run-daily 정상 경로 (smoke)
# ============================================================================


class TestCmdRunDailySuccess:
    def test_run_daily_smoke_no_rtdb_no_notify(self, tmp_path: Path, monkeypatch):
        """정상 경로 smoke — RTDB / 알림 비활성화 (오프라인 dry-run)."""
        main(["init", "--capital", "100000000", "--state-dir", str(tmp_path)])

        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(tmp_path, trade_date)

        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)

        exit_code = main(
            [
                "run-daily",
                "--state-dir",
                str(tmp_path),
                "--trade-date",
                trade_date.isoformat(),
                "--no-rtdb",
                "--no-notify",
            ]
        )
        assert exit_code == 0

    def test_run_daily_persists_history(self, tmp_path: Path, monkeypatch):
        """run-daily 가 history/daily/{date}.json 과 summary.jsonl 을 저장한다."""
        main(["init", "--capital", "100000000", "--state-dir", str(tmp_path)])
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(tmp_path, trade_date)

        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)

        main(
            [
                "run-daily",
                "--state-dir",
                str(tmp_path),
                "--trade-date",
                trade_date.isoformat(),
                "--no-rtdb",
                "--no-notify",
            ]
        )

        assert (tmp_path / "history" / "daily" / f"{trade_date.isoformat()}.json").exists()
        assert (tmp_path / "history" / "summary.jsonl").exists()

    def test_run_daily_with_rtdb_calls_publish(self, tmp_path: Path, monkeypatch):
        """RTDB 활성화 시 publish_to_rtdb 와 send_daily_notifications 가 호출된다."""
        main(["init", "--capital", "100000000", "--state-dir", str(tmp_path)])
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(tmp_path, trade_date)

        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)

        # Firebase 초기화 mock — fake app 객체 반환
        fake_app = object()
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: fake_app)

        # rtdb_gateway 호출 모두 mock
        monkeypatch.setattr(cli_module.rtdb_gateway, "fetch_unprocessed_fills", lambda app: [])

        publish_calls: list[bool] = []

        def _spy_publish(app, state_dir, state, result):  # noqa: ANN001
            publish_calls.append(True)

        monkeypatch.setattr(cli_module, "_publish_to_rtdb", _spy_publish)

        notify_calls: list[bool] = []

        def _spy_notify(app, result):  # noqa: ANN001
            notify_calls.append(True)

        monkeypatch.setattr(cli_module, "_send_daily_notifications", _spy_notify)

        exit_code = main(
            [
                "run-daily",
                "--state-dir",
                str(tmp_path),
                "--trade-date",
                trade_date.isoformat(),
            ]
        )
        assert exit_code == 0
        assert len(publish_calls) == 1
        assert len(notify_calls) == 1


# ============================================================================
# placeholder → 실구현된 명령어 테스트
# ============================================================================


class TestFetchState:
    def test_fetch_state_calls_git_pull(self, tmp_path: Path, monkeypatch):
        called: list[Path] = []

        def _spy_pull(state_dir):  # noqa: ANN001
            called.append(state_dir)

        monkeypatch.setattr(cli_module.git_state, "git_pull", _spy_pull)

        exit_code = main(["fetch-state", "--state-dir", str(tmp_path)])
        assert exit_code == 0
        assert called == [tmp_path]


class TestPushState:
    def test_push_state_calls_git_commit_and_push(self, tmp_path: Path, monkeypatch):
        captured: dict[str, object] = {}

        def _spy_push(state_dir, message, **kw):  # noqa: ANN001
            captured["state_dir"] = state_dir
            captured["message"] = message
            return True

        monkeypatch.setattr(cli_module.git_state, "git_commit_and_push", _spy_push)

        exit_code = main(["push-state", "--state-dir", str(tmp_path), "-m", "test commit"])
        assert exit_code == 0
        assert captured["state_dir"] == tmp_path
        assert captured["message"] == "test commit"

    def test_push_state_no_changes_returns_0(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(cli_module.git_state, "git_commit_and_push", lambda d, m, **kw: False)
        exit_code = main(["push-state", "--state-dir", str(tmp_path)])
        assert exit_code == 0


class TestFetchFills:
    def test_fetch_fills_returns_1_when_rtdb_init_fails(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)
        exit_code = main(["fetch-fills", "--state-dir", str(tmp_path)])
        assert exit_code == 1

    def test_fetch_fills_outputs_json(self, tmp_path: Path, monkeypatch, capsys):
        from live.models import ActualFill

        fake_app = object()
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

        exit_code = main(["fetch-fills", "--state-dir", str(tmp_path)])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "fill_test" in captured.out
        assert "sso" in captured.out


class TestHistoryCmd:
    def test_history_outputs_recent_lines(self, tmp_path: Path, capsys):
        # history/summary.jsonl 직접 작성
        hist_dir = tmp_path / "history"
        hist_dir.mkdir(parents=True)
        (hist_dir / "summary.jsonl").write_text(
            '{"date":"2026-04-08","equity":100}\n'
            '{"date":"2026-04-09","equity":101}\n'
            '{"date":"2026-04-10","equity":102}\n',
            encoding="utf-8",
        )

        exit_code = main(["history", "--state-dir", str(tmp_path), "--tail", "2"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "2026-04-09" in captured.out
        assert "2026-04-10" in captured.out
        assert "2026-04-08" not in captured.out  # tail=2 로 제외됨

    def test_history_no_file_returns_0(self, tmp_path: Path):
        exit_code = main(["history", "--state-dir", str(tmp_path)])
        assert exit_code == 0


class TestNotifyFailureCmd:
    def test_notify_failure_calls_safe_notify(self, tmp_path: Path, monkeypatch):
        notify_calls: list[str] = []
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)
        monkeypatch.setattr(
            cli_module,
            "_safe_notify_failure",
            lambda app, msg: notify_calls.append(msg),
        )

        exit_code = main(["notify-failure", "--state-dir", str(tmp_path), "-m", "수동 실패 테스트"])
        assert exit_code == 0
        assert "수동 실패 테스트" in notify_calls[0]


# ============================================================================
# argparse 기본
# ============================================================================


class TestMainArgv:
    def test_main_accepts_argv_list(self, tmp_path: Path):
        """main 은 argv 리스트를 직접 받을 수 있다 (테스트 용이)."""
        exit_code = main(["init", "--capital", "10000000", "--state-dir", str(tmp_path)])
        assert exit_code == 0

    def test_main_missing_subcommand_exits_with_error(self):
        """subcommand 없이 호출 → SystemExit (argparse)."""
        with pytest.raises(SystemExit):
            main([])


# ============================================================================
# .env 자동 로드 (python-dotenv)
# ============================================================================


class TestDotenvLoading:
    """``_load_dotenv_if_present`` 동작 검증.

    로컬 수동 테스트에서 매번 ``export`` 하지 않고 프로젝트 루트의 ``.env``
    파일로 환경변수를 공급할 수 있게 한 기능. GitHub Actions 는 파일 없이
    동작해야 하고, 기존 환경변수를 덮어쓰면 안 된다.
    """

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
        """Given 기존 env 가 있고 `.env` 에도 같은 키가 있을 때
        When 로드 호출 시 Then 기존 env 값이 우선한다 (override=False).

        이 동작이 없으면 GitHub Actions 의 ``env:`` 블록이 무력화될 수 있다.
        """
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
        """``_PROJECT_ROOT`` 가 실제 프로젝트 루트를 가리키는지 확인.

        루트에는 ``pyproject.toml`` 과 ``live`` 디렉토리가 존재해야 한다.
        이 검사는 파일 레이아웃 변경으로 ``parents[3]`` 인덱스가 깨지는 사고를
        방지한다.
        """
        root = cli_module._PROJECT_ROOT
        assert (root / "pyproject.toml").is_file()
        assert (root / "live").is_dir()
        assert cli_module._DOTENV_PATH == root / ".env"
