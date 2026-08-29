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

    def test_cron_is_utc_weekday_22_27(self, daily_run_yaml: str):
        """cron 은 '27 22 * * 1-5' (UTC 월~금 22:27 = KST 화~토 07:27).

        GitHub Actions cron 은 항상 UTC 로 해석된다. env.TZ 는 job 런타임에만
        영향이 있을 뿐 스케줄 해석에는 무관하므로, 한국 시각 고정을 위해
        반드시 UTC 기준 값을 사용해야 한다. 라운드 분 (`:00`, `:30`, `:50`) 은
        GitHub 스케줄러 큐 혼잡으로 지연이 크므로, 비인기 분을 사용한다.
        """
        assert "27 22 * * 1-5" in daily_run_yaml
        # 과거 값이 남아있으면 안 된다.
        assert "50 17 * * 1-5" not in daily_run_yaml
        assert "50 22 * * 1-5" not in daily_run_yaml

    def test_timezone_america_new_york(self, daily_run_yaml: str):
        """timezone: America/New_York (job 런타임 TZ; cron 해석과는 무관)."""
        assert "America/New_York" in daily_run_yaml

    def test_workflow_dispatch_supported(self, daily_run_yaml: str):
        """수동 실행을 위해 workflow_dispatch 지원."""
        assert "workflow_dispatch" in daily_run_yaml

    def test_python_3_12(self, daily_run_yaml: str):
        assert "3.12" in daily_run_yaml

    def test_poetry_cache_step(self, daily_run_yaml: str):
        """actions/cache@v5 + 프로젝트 내 .venv 경로 캐싱."""
        assert "actions/cache@v5" in daily_run_yaml
        assert ".venv" in daily_run_yaml

    def test_credentials_use_gcp_application_default(self, daily_run_yaml: str):
        """자격증명은 ``GOOGLE_APPLICATION_CREDENTIALS`` 단일 (Firebase Admin SDK 가 RTDB / GCS / FCM 공용)."""
        assert "GOOGLE_APPLICATION_CREDENTIALS" in daily_run_yaml

    def test_no_external_repo_checkout(self, daily_run_yaml: str):
        """CLI 가 GCS 정본을 직접 동기화하므로 외부 repo 를 actions/checkout 으로 받지 않는다."""
        assert "repository:" not in daily_run_yaml

    def test_no_shell_git_commands(self, daily_run_yaml: str):
        """workflow shell step 에 git 명령이 들어있지 않아야 한다 (정본 동기화는 storage_gateway)."""
        assert "git add" not in daily_run_yaml
        assert "git push" not in daily_run_yaml

    def test_run_daily_has_no_state_dir_flag(self, daily_run_yaml: str):
        """CLI 가 매 실행마다 자체 state workspace 를 생성하므로 ``--state-dir`` 인자가 없다."""
        assert "--state-dir" not in daily_run_yaml

    def test_no_retry_logic(self, daily_run_yaml: str):
        """장애 시 자동 복구 금지 원칙에 따라 재시도 로직이 없어야 한다."""
        assert "run_first" not in daily_run_yaml
        assert "run_retry" not in daily_run_yaml
        assert "sleep 300" not in daily_run_yaml
        assert "continue-on-error" not in daily_run_yaml

    def test_notify_failure_job(self, daily_run_yaml: str):
        """notify-failure job 이 if: failure() 로 트리거."""
        assert "notify-failure" in daily_run_yaml
        assert "failure()" in daily_run_yaml

    def test_run_daily_command(self, daily_run_yaml: str):
        """live.cli run-daily 호출."""
        assert "python -m live run-daily" in daily_run_yaml

    def test_secrets_referenced(self, daily_run_yaml: str):
        """3 종 시크릿이 모두 참조되어야 한다 (Firebase 자격증명 + 텔레그램 봇/채팅)."""
        for secret in (
            "FIREBASE_CONFIG",
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
        """.claude/rules/python.md "주석 작성 원칙" — 변경 이력 / 과거 상태 주석 금지.

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

    def test_monthly_cron_utc_day1(self, keepalive_yaml: str):
        """cron 은 UTC 매월 1일 01:00 에 월 1회 fire.

        keepalive 의 목적은 단순히 "월 1회 활동" 을 GitHub 에 알리는 것이므로,
        정확한 시각/시간대는 중요하지 않다. UTC 기준 1일 01:00 을 쓰면 월 정확히
        한 번만 발화되고 가드 로직이 필요 없어 구조가 단순하다.
        """
        assert "0 1 1 * *" in keepalive_yaml
        # 과거의 복잡한 UTC 28-31 방식이 남아있으면 안 된다.
        assert "30 16 28-31 * *" not in keepalive_yaml
        # 오래된 UTC 1일 00:00 값도 남아있으면 안 된다.
        assert "0 0 1 * *" not in keepalive_yaml

    def test_no_kst_guard(self, keepalive_yaml: str):
        """단순화 후에는 KST 일자 가드가 존재하지 않는다.

        cron 자체가 월 1회만 발화하므로 내부 가드로 스킵할 이유가 없다.
        """
        assert "TZ=Asia/Seoul date +%d" not in keepalive_yaml
        assert "steps.guard.outputs.skip" not in keepalive_yaml

    def test_workflow_dispatch_supported(self, keepalive_yaml: str):
        assert "workflow_dispatch" in keepalive_yaml

    def test_targets_quant_with_allow_empty_commit(self, keepalive_yaml: str):
        """quant 리포 자체를 checkout 하고 빈 commit 을 남긴다 (외부 repo 참조 없음).

        주석 블록은 제외하고 실행 코드 영역만 확인.
        """
        code_lines = [line for line in keepalive_yaml.splitlines() if not line.lstrip().startswith("#")]
        code = "\n".join(code_lines)

        # 실행 코드에 빈 commit 명령
        assert "git commit --allow-empty" in code
        # 외부 repo 참조 없음 (자기 자신만 checkout)
        assert "repository:" not in code
        # 기본 GITHUB_TOKEN 에 push 권한 부여
        assert "contents: write" in code

    def test_no_legacy_comment_block(self, keepalive_yaml: str):
        """.claude/rules/python.md "주석 작성 원칙" — 과거 버전 주석 블록 금지."""
        forbidden = ("이전 버전", "heartbeat", "과거에는")
        for phrase in forbidden:
            assert phrase not in keepalive_yaml, f"과거 상태 주석 남아있음: {phrase}"

    def test_keepalive_commit_message(self, keepalive_yaml: str):
        """커밋 메시지 포맷: ``keepalive: YYYY-MM-DD`` (UTC 기준 날짜)."""
        assert "keepalive: $(date -u +%Y-%m-%d)" in keepalive_yaml
