"""live.cli 진입점 및 명령어 통합 테스트.

TODO T-10.1 ~ T-10.3 시나리오 고정.

테스트 원칙:
- 실제 yfinance 호출 금지 (monkeypatch 로 live.data_fetcher 내부 함수 교체)
- 파일 I/O 는 tmp_path 로 격리
- git 작업은 ``state_dir`` fixture 로 ephemeral_state_repo 전체 대체 — 네트워크 없음
- notify_failure 훅은 monkeypatch 로 감시
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from live import cli as cli_module
from live.cli import main
from live.state import load_state

# ============================================================================
# 공통 fixture
# ============================================================================


@pytest.fixture
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``cli_module.ephemeral_state_repo`` 를 ``tmp_path`` 를 yield 하는 가짜 컨텍스트
    매니저로 교체한다. 실제 git clone/push 는 절대 호출되지 않는다.

    Returns:
        ``tmp_path`` 와 동일한 ``Path`` — 테스트는 이 경로를 state_dir 로 사용.
    """

    @contextmanager
    def fake_ephemeral(*, push_on_success: bool, commit_subcommand: str):
        del push_on_success, commit_subcommand
        yield tmp_path

    monkeypatch.setattr(cli_module, "ephemeral_state_repo", fake_ephemeral)
    return tmp_path


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
    def test_init_creates_live_state_json_t_10_1(self, state_dir: Path):
        """T-10.1: init --capital 100000000 → live_state.json 생성 + 4 자산 초기화."""
        exit_code = main(["init", "--capital", "100000000"])
        assert exit_code == 0
        state_path = state_dir / "live_state.json"
        assert state_path.exists()

        loaded = load_state(state_path)
        assert loaded.portfolio_id == "portfolio_q2_2xs"
        assert loaded.shared_cash_model == pytest.approx(100_000_000.0)
        assert loaded.shared_cash_actual == pytest.approx(100_000_000.0)
        assert set(loaded.assets.keys()) == {"sso", "qld", "gld", "tlt"}

    def test_init_negative_capital_fails(self, state_dir: Path):
        """음수 capital → 실패 (exit code 1)."""
        del state_dir  # fixture 설치만 필요
        exit_code = main(["init", "--capital", "-1000"])
        assert exit_code == 1


# ============================================================================
# run-daily 에러 시나리오
# ============================================================================


class TestCmdRunDailyFailures:
    def _init_state(self, state_dir: Path) -> None:
        """상태 파일 초기화."""
        main(["init", "--capital", "100000000"])
        assert (state_dir / "live_state.json").exists()

    def test_data_fetch_failure_calls_notify_t_10_2(self, state_dir: Path, monkeypatch):
        """T-10.2: data 수집 중 실패 → 중단 + _safe_notify_failure 호출."""
        self._init_state(state_dir)

        # monkeypatch: fetch_recent_ohlc 가 ValueError 발생
        def _failing_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            raise ValueError(f"테스트: yfinance 실패 {ticker}")

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _failing_fetch)
        # RTDB 초기화는 None 반환으로 강제 (실제 Firebase 연결 없음)
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)

        notify_calls: list[str] = []

        def _spy_notify(rtdb_app, message: str) -> None:  # noqa: ANN001
            notify_calls.append(message)

        monkeypatch.setattr(cli_module, "_safe_notify_failure", _spy_notify)

        exit_code = main(["run-daily", "--trade-date", "2026-04-10"])

        # exit code 는 main 의 try/except 에서 1 반환
        assert exit_code == 1
        assert len(notify_calls) >= 1
        assert any("yfinance" in msg or "검증" in msg or "실패" in msg or "데이터" in msg for msg in notify_calls)

    def test_calculation_failure_state_unchanged_t_10_3(self, state_dir: Path, monkeypatch):
        """T-10.3: run_daily 내부 계산 실패 → 중단 + 상태 파일 변경 없음."""
        self._init_state(state_dir)
        state_path = state_dir / "live_state.json"
        original_mtime = state_path.stat().st_mtime

        # CSV 준비
        _setup_flat_market_csvs(state_dir, date(2026, 4, 10))

        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(date(2026, 4, 10))

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)

        # run_daily 호출을 실패하도록 monkeypatch
        def _failing_run_daily(*args, **kwargs):  # noqa: ANN202
            raise RuntimeError("테스트: 엔진 내부 계산 실패")

        monkeypatch.setattr(cli_module, "run_daily", _failing_run_daily)
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
        assert any("엔진" in msg or "계산" in msg or "실행" in msg for msg in notify_calls)

        # 상태 파일 변경 없음
        assert state_path.stat().st_mtime == original_mtime


# ============================================================================
# run-daily 정상 경로 (smoke)
# ============================================================================


class TestCmdRunDailySuccess:
    def test_run_daily_smoke(self, state_dir: Path, monkeypatch):
        """정상 경로 smoke — RTDB/알림을 모두 mock 한다."""
        main(["init", "--capital", "100000000"])

        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)
        monkeypatch.setattr(cli_module, "_send_daily_notifications", lambda app, result: None)

        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])
        assert exit_code == 0

    def test_run_daily_persists_history(self, state_dir: Path, monkeypatch):
        """run-daily 가 history/daily/{date}.json 과 summary.jsonl 을 저장한다."""
        main(["init", "--capital", "100000000"])
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(trade_date)

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)
        monkeypatch.setattr(cli_module, "_send_daily_notifications", lambda app, result: None)

        main(["run-daily", "--trade-date", trade_date.isoformat()])

        assert (state_dir / "history" / "daily" / f"{trade_date.isoformat()}.json").exists()
        assert (state_dir / "history" / "summary.jsonl").exists()

    def test_run_daily_with_rtdb_calls_publish(self, state_dir: Path, monkeypatch):
        """RTDB 활성화 시 publish_to_rtdb 와 send_daily_notifications 가 호출된다."""
        main(["init", "--capital", "100000000"])
        trade_date = date(2026, 4, 10)
        _setup_flat_market_csvs(state_dir, trade_date)

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

        exit_code = main(["run-daily", "--trade-date", trade_date.isoformat()])
        assert exit_code == 0
        assert len(publish_calls) == 1
        assert len(notify_calls) == 1


# ============================================================================
# placeholder → 실구현된 명령어 테스트
# ============================================================================


class TestFetchFills:
    """fetch-fills 는 RTDB 만 읽으므로 state_dir 가 필요 없다."""

    def test_fetch_fills_returns_1_when_rtdb_init_fails(self, monkeypatch):
        monkeypatch.setattr(cli_module, "_initialize_rtdb_app", lambda: None)
        exit_code = main(["fetch-fills"])
        assert exit_code == 1

    def test_fetch_fills_outputs_json(self, monkeypatch, capsys):
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

        exit_code = main(["fetch-fills"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "fill_test" in captured.out
        assert "sso" in captured.out


class TestHistoryCmd:
    def test_history_outputs_recent_lines(self, state_dir: Path, capsys):
        # history/summary.jsonl 직접 작성
        hist_dir = state_dir / "history"
        hist_dir.mkdir(parents=True)
        (hist_dir / "summary.jsonl").write_text(
            '{"date":"2026-04-08","equity":100}\n'
            '{"date":"2026-04-09","equity":101}\n'
            '{"date":"2026-04-10","equity":102}\n',
            encoding="utf-8",
        )

        exit_code = main(["history", "--tail", "2"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "2026-04-09" in captured.out
        assert "2026-04-10" in captured.out
        assert "2026-04-08" not in captured.out  # tail=2 로 제외됨

    def test_history_no_file_returns_0(self, state_dir: Path):
        del state_dir  # fixture 설치만 필요
        exit_code = main(["history"])
        assert exit_code == 0


class TestNotifyFailureCmd:
    """notify-failure 는 state_dir 가 필요 없다."""

    def test_notify_failure_calls_safe_notify(self, monkeypatch):
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
    def test_main_accepts_argv_list(self, state_dir: Path):
        """main 은 argv 리스트를 직접 받을 수 있다 (테스트 용이)."""
        del state_dir  # fixture 설치만 필요
        exit_code = main(["init", "--capital", "10000000"])
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


# ============================================================================
# ephemeral_state_repo 컨텍스트 매니저
# ============================================================================


class TestEphemeralStateRepo:
    """CLI 가 매 실행마다 qbt-live-state 리포를 tempdir 에 clone 하고,
    쓰기 명령이면 commit/push 를 자동 수행하며, 어떤 경우에도 tempdir 을
    정리하는지 검증한다.
    """

    @pytest.fixture
    def _fake_git(self, monkeypatch: pytest.MonkeyPatch) -> dict:
        """git_clone_shallow / git_commit_and_push 를 모킹하고 호출 기록을 수집."""
        log: dict = {"clone": [], "push": []}

        def fake_clone(remote_url: str, dest: Path, *, pat: str | None = None) -> None:
            log["clone"].append({"remote_url": remote_url, "dest": dest, "pat": pat})
            # 실제 clone 을 시뮬레이션 — 빈 디렉토리 생성
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "live_state.json").write_text("{}", encoding="utf-8")

        def fake_push(
            state_dir: Path,
            message: str,
            *,
            user_name: str = "qbt-live-bot",
            user_email: str = "qbt-live-bot@noreply.github.com",
        ) -> bool:
            log["push"].append(
                {
                    "state_dir": state_dir,
                    "message": message,
                    "user_name": user_name,
                    "user_email": user_email,
                }
            )
            return True

        monkeypatch.setattr("live.git_state.git_clone_shallow", fake_clone)
        monkeypatch.setattr("live.git_state.git_commit_and_push", fake_push)
        monkeypatch.setenv("STATE_REPO_PAT", "ghp_test_token")
        return log

    def test_write_command_clones_and_pushes(self, _fake_git: dict):
        """Given 쓰기 명령(push_on_success=True) When 컨텍스트 진입/탈출 Then clone + push 모두 호출."""
        with cli_module.ephemeral_state_repo(push_on_success=True, commit_subcommand="run-daily") as state_dir:
            assert state_dir.is_dir()
            assert (state_dir / "live_state.json").is_file()

        assert len(_fake_git["clone"]) == 1
        assert len(_fake_git["push"]) == 1
        push_call = _fake_git["push"][0]
        assert push_call["message"].startswith("auto: live run-daily")
        assert "KST" in push_call["message"]

    def test_read_only_command_clones_but_does_not_push(self, _fake_git: dict):
        """Given 읽기 전용 명령(push_on_success=False) Then clone 은 호출, push 는 skip."""
        with cli_module.ephemeral_state_repo(push_on_success=False, commit_subcommand="drift") as state_dir:
            assert state_dir.is_dir()

        assert len(_fake_git["clone"]) == 1
        assert len(_fake_git["push"]) == 0

    def test_exception_in_context_skips_push(self, _fake_git: dict):
        """Given 컨텍스트 내부에서 예외 발생 Then push 호출되지 않고 예외 전파."""
        with pytest.raises(RuntimeError, match="내부 에러"):
            with cli_module.ephemeral_state_repo(push_on_success=True, commit_subcommand="run-daily"):
                raise RuntimeError("내부 에러")

        assert len(_fake_git["clone"]) == 1
        assert len(_fake_git["push"]) == 0

    def test_tempdir_is_cleaned_up_on_success(self, _fake_git: dict):
        """Given 정상 종료 Then tempdir 은 더 이상 존재하지 않는다."""
        captured_path: list[Path] = []
        with cli_module.ephemeral_state_repo(push_on_success=True, commit_subcommand="run-daily") as state_dir:
            captured_path.append(state_dir)

        assert captured_path[0].exists() is False

    def test_tempdir_is_cleaned_up_on_exception(self, _fake_git: dict):
        """Given 내부 예외 Then tempdir 은 정리되어야 한다."""
        captured_path: list[Path] = []
        with pytest.raises(RuntimeError):
            with cli_module.ephemeral_state_repo(push_on_success=True, commit_subcommand="run-daily") as state_dir:
                captured_path.append(state_dir)
                raise RuntimeError("boom")

        assert captured_path[0].exists() is False

    def test_missing_pat_raises_value_error(self, monkeypatch: pytest.MonkeyPatch):
        """Given STATE_REPO_PAT 미설정 Then 즉시 ValueError."""
        monkeypatch.delenv("STATE_REPO_PAT", raising=False)

        with pytest.raises(ValueError, match="STATE_REPO_PAT"):
            with cli_module.ephemeral_state_repo(push_on_success=True, commit_subcommand="run-daily"):
                pass

    def test_clone_receives_state_repo_url_and_pat(self, _fake_git: dict):
        """Given 정상 호출 Then clone 에 상수 STATE_REPO_URL 과 env PAT 가 전달된다."""
        from live.constants import STATE_REPO_URL

        with cli_module.ephemeral_state_repo(push_on_success=True, commit_subcommand="init"):
            pass

        clone_call = _fake_git["clone"][0]
        assert clone_call["remote_url"] == STATE_REPO_URL
        assert clone_call["pat"] == "ghp_test_token"
