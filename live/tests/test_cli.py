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
        """T-10.2: data 수집 중 실패 → 중단 + _notify_failure 호출."""
        self._init_state(tmp_path)

        # monkeypatch: fetch_recent_ohlc 가 ValueError 발생
        def _failing_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            raise ValueError(f"테스트: yfinance 실패 {ticker}")

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _failing_fetch)

        notify_calls: list[str] = []

        def _spy_notify(message: str) -> None:
            notify_calls.append(message)

        monkeypatch.setattr(cli_module, "_notify_failure", _spy_notify)

        exit_code = main(
            [
                "run-daily",
                "--state-dir",
                str(tmp_path),
                "--trade-date",
                "2026-04-10",
            ]
        )

        # exit code 는 @cli_exception_handler 로 1 반환
        assert exit_code == 1
        # _notify_failure 가 최소 1 번 호출되어야 한다
        assert len(notify_calls) >= 1
        assert any("yfinance" in msg or "검증" in msg or "실패" in msg for msg in notify_calls)

    def test_calculation_failure_state_unchanged_t_10_3(self, tmp_path: Path, monkeypatch):
        """T-10.3: run_daily 내부 계산 실패 → 중단 + 상태 파일 변경 없음."""
        self._init_state(tmp_path)
        state_path = tmp_path / "live_state.json"
        original_mtime = state_path.stat().st_mtime

        # CSV 준비
        _setup_flat_market_csvs(tmp_path, date(2026, 4, 10))

        # data_fetcher 는 정상 동작하도록 mock (fetch_recent_ohlc 는 빈 DF → skip 경로)
        def _mock_fetch(ticker: str, days: int = 5):  # noqa: ANN202
            return _make_recent_df(date(2026, 4, 10))

        monkeypatch.setattr(cli_module, "fetch_recent_ohlc", _mock_fetch)

        # run_daily 호출을 실패하도록 monkeypatch
        def _failing_run_daily(*args, **kwargs):  # noqa: ANN202
            raise RuntimeError("테스트: 엔진 내부 계산 실패")

        monkeypatch.setattr(cli_module, "run_daily", _failing_run_daily)

        notify_calls: list[str] = []
        monkeypatch.setattr(cli_module, "_notify_failure", lambda msg: notify_calls.append(msg))

        # append_today_to_csv 은 실제 동작 — _setup_flat_market_csvs 로 준비된 CSV 에 append
        exit_code = main(
            [
                "run-daily",
                "--state-dir",
                str(tmp_path),
                "--trade-date",
                "2026-04-10",
            ]
        )

        assert exit_code == 1
        assert len(notify_calls) >= 1
        assert any("엔진" in msg or "계산" in msg or "실행" in msg for msg in notify_calls)

        # 상태 파일 변경 없음 (저장은 run_daily 성공 후에만 수행되므로)
        assert state_path.stat().st_mtime == original_mtime


# ============================================================================
# run-daily 정상 경로 (smoke)
# ============================================================================


class TestCmdRunDailySuccess:
    def test_run_daily_smoke(self, tmp_path: Path, monkeypatch):
        """정상 경로 smoke — 초기 상태에서 1 회 실행 성공."""
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
            ]
        )
        assert exit_code == 0


# ============================================================================
# 플레이스홀더 명령어
# ============================================================================


class TestPlaceholderCommands:
    @pytest.mark.parametrize("command", ["fetch-state", "push-state", "fetch-fills", "history", "notify-failure"])
    def test_placeholder_returns_1(self, command: str, tmp_path: Path):
        exit_code = main([command, "--state-dir", str(tmp_path)])
        assert exit_code == 1


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
