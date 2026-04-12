"""GitHub Actions workflow yaml 구조 계약을 문자열 기반으로 검증한다."""

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
        """cron 은 '50 17 * * 1-5' (월~금 17:50 ET)."""
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
        """actions/cache@v5 + Poetry venv 경로 캐싱."""
        assert "actions/cache@v5" in daily_run_yaml
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

    def test_workflow_dispatch_accepts_trade_date_input(self, daily_run_yaml: str):
        """주말 / 과거 재현 수동 테스트를 위해 workflow_dispatch 에 trade_date
        입력이 선언되어 있어야 한다."""
        assert "trade_date:" in daily_run_yaml
        assert "YYYY-MM-DD" in daily_run_yaml
        # required: false / type: string 형태
        assert "required: false" in daily_run_yaml
        assert "type: string" in daily_run_yaml

    def test_run_step_uses_trade_date_env_and_conditional_flag(self, daily_run_yaml: str):
        """run step 에 TRADE_DATE 환경변수 주입 + shell 조건부 분기로 flag 전달."""
        assert "TRADE_DATE: ${{ github.event.inputs.trade_date }}" in daily_run_yaml
        # shell 에서 $TRADE_DATE 값에 따라 --trade-date 인자 조건부 전달
        assert 'if [ -n "$TRADE_DATE" ]; then' in daily_run_yaml
        assert 'poetry run python -m live run-daily --trade-date "$TRADE_DATE"' in daily_run_yaml

    def test_no_legacy_or_history_comments(self, daily_run_yaml: str):
        """루트 CLAUDE.md "주석 작성 원칙" — 변경 이력 / 과거 상태 주석 금지.

        ``기존``, ``이전``, ``테스트 코드`` 같은 표현이 주석에 남아 있으면 문서
        내구성 원칙 위반이다. 현재 상태만 기술하도록 강제한다.
        """
        forbidden = ("테스트 코드", "기존은", "기존 한 줄", "이전 버전")
        for phrase in forbidden:
            assert phrase not in daily_run_yaml, f"과거 상태 주석 남아있음: {phrase}"


# ============================================================================
# keepalive.yml
# ============================================================================


class TestKeepaliveWorkflow:
    """keepalive.yml 은 quant (퍼블릭) 리포에 월 1회 빈 commit 을 남겨
    GitHub Actions 의 60일 비활성 정책으로부터 daily_run 스케줄을 보호한다.
    """

    def test_file_exists(self):
        assert KEEPALIVE_PATH.exists()

    def test_monthly_cron(self, keepalive_yaml: str):
        """매월 1일 cron."""
        assert "0 0 1 * *" in keepalive_yaml

    def test_workflow_dispatch_supported(self, keepalive_yaml: str):
        assert "workflow_dispatch" in keepalive_yaml

    def test_targets_quant_with_allow_empty_commit(self, keepalive_yaml: str):
        """quant 리포 자체를 checkout 하고 빈 commit 을 남긴다. qbt-live-state
        는 더 이상 건드리지 않는다. 주석 블록은 제외하고 실행 코드 영역만 확인."""
        code_lines = [line for line in keepalive_yaml.splitlines() if not line.lstrip().startswith("#")]
        code = "\n".join(code_lines)

        # 실행 코드에 빈 commit 명령
        assert "git commit --allow-empty" in code
        # 실행 코드에는 qbt-live-state 언급이 없다
        assert "qbt-live-state" not in code
        assert "STATE_REPO_PAT" not in code
        # 기본 GITHUB_TOKEN 에 push 권한 부여
        assert "contents: write" in code

    def test_no_legacy_comment_block(self, keepalive_yaml: str):
        """루트 CLAUDE.md "주석 작성 원칙" — 과거 버전 주석 블록 금지."""
        forbidden = ("이전 버전", "heartbeat", "과거에는", "qbt-live-state 타겟")
        for phrase in forbidden:
            assert phrase not in keepalive_yaml, f"과거 상태 주석 남아있음: {phrase}"

    def test_keepalive_commit_message(self, keepalive_yaml: str):
        """커밋 메시지 포맷: ``keepalive: YYYY-MM-DD``."""
        assert "keepalive: $(date -u +%Y-%m-%d)" in keepalive_yaml
