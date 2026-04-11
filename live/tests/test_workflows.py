"""GitHub Actions workflow yaml 구조 검증.

설계서 12장 cron / timezone / retry / notify-failure / Poetry 캐싱 요구사항을
정적으로 확인한다 (실제 실행은 사용자 수동 테스트 M-11.1~M-11.3).

PyYAML 미설치 환경 대응을 위해 문자열 기반 검증 사용.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DAILY_RUN_PATH = REPO_ROOT / ".github" / "workflows" / "daily_run.yml"
KEEPALIVE_PATH = REPO_ROOT / ".github" / "workflows" / "keepalive.yml"


@pytest.fixture(scope="module")
def daily_run_yaml() -> str:
    assert DAILY_RUN_PATH.exists(), f"daily_run.yml 누락: {DAILY_RUN_PATH}"
    return DAILY_RUN_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def keepalive_yaml() -> str:
    assert KEEPALIVE_PATH.exists(), f"keepalive.yml 누락: {KEEPALIVE_PATH}"
    return KEEPALIVE_PATH.read_text(encoding="utf-8")


# ============================================================================
# daily_run.yml
# ============================================================================


class TestDailyRunWorkflow:
    def test_file_exists(self):
        assert DAILY_RUN_PATH.exists()

    def test_cron_is_weekday_17_50(self, daily_run_yaml: str):
        """설계서 12장: cron '50 17 * * 1-5' (월~금 17:50 ET)."""
        assert "50 17 * * 1-5" in daily_run_yaml

    def test_timezone_america_new_york(self, daily_run_yaml: str):
        """timezone: America/New_York."""
        assert "America/New_York" in daily_run_yaml

    def test_workflow_dispatch_supported(self, daily_run_yaml: str):
        """수동 실행을 위해 workflow_dispatch 지원."""
        assert "workflow_dispatch" in daily_run_yaml

    def test_python_3_12(self, daily_run_yaml: str):
        assert "3.12" in daily_run_yaml

    def test_poetry_cache_step(self, daily_run_yaml: str):
        """actions/cache@v4 + Poetry venv 경로 캐싱."""
        assert "actions/cache@v4" in daily_run_yaml
        assert "pypoetry" in daily_run_yaml

    def test_state_repo_pat_injected_to_cli_env(self, daily_run_yaml: str):
        """CLI 가 ephemeral mode 로 state repo 를 clone 하므로 STATE_REPO_PAT 을
        workflow env 에 주입해야 한다 (별도 checkout step 은 더 이상 없음)."""
        assert "STATE_REPO_PAT: ${{ secrets.STATE_REPO_PAT }}" in daily_run_yaml

    def test_no_explicit_state_repo_checkout(self, daily_run_yaml: str):
        """CLI 가 shallow clone 을 담당하므로 actions/checkout 으로 state repo 를
        받지 않는다."""
        assert "repository: ingbeen/qbt-live-state" not in daily_run_yaml

    def test_no_shell_git_commit_push(self, daily_run_yaml: str):
        """CLI 가 commit/push 를 담당하므로 workflow shell step 에 git 명령이
        들어있지 않아야 한다."""
        assert "git add -A" not in daily_run_yaml
        assert "git push" not in daily_run_yaml

    def test_run_daily_has_no_state_dir_flag(self, daily_run_yaml: str):
        """CLI 가 ephemeral 이므로 --state-dir 인자가 사용되지 않는다."""
        assert "--state-dir" not in daily_run_yaml

    def test_retry_step_present(self, daily_run_yaml: str):
        """1 차 시도 실패 시 5분 대기 후 재시도."""
        assert "run_first" in daily_run_yaml
        assert "run_retry" in daily_run_yaml
        assert "sleep 300" in daily_run_yaml

    def test_notify_failure_job(self, daily_run_yaml: str):
        """notify-failure job 이 if: failure() 로 트리거."""
        assert "notify-failure" in daily_run_yaml
        assert "failure()" in daily_run_yaml

    def test_run_daily_command(self, daily_run_yaml: str):
        """live.cli run-daily 호출."""
        assert "python -m live run-daily" in daily_run_yaml

    def test_secrets_referenced(self, daily_run_yaml: str):
        """4 종 시크릿이 모두 참조되어야 한다."""
        for secret in (
            "FIREBASE_CONFIG",
            "STATE_REPO_PAT",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
        ):
            assert secret in daily_run_yaml, f"{secret} 누락"


# ============================================================================
# keepalive.yml
# ============================================================================


class TestKeepaliveWorkflow:
    def test_file_exists(self):
        assert KEEPALIVE_PATH.exists()

    def test_monthly_cron(self, keepalive_yaml: str):
        """매월 1일 cron."""
        assert "0 0 1 * *" in keepalive_yaml

    def test_workflow_dispatch_supported(self, keepalive_yaml: str):
        assert "workflow_dispatch" in keepalive_yaml

    def test_state_repo_checkout(self, keepalive_yaml: str):
        assert "ingbeen/qbt-live-state" in keepalive_yaml

    def test_heartbeat_log(self, keepalive_yaml: str):
        assert "heartbeat" in keepalive_yaml
