"""live.git_state — git subprocess wrapper 테스트.

실제 git 호출 없이 ``subprocess.run`` 을 monkeypatch 하여 동작 검증.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from live import git_state


class _FakeCompleted:
    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = ""


# ============================================================================
# git_pull
# ============================================================================


class TestGitPull:
    def test_pull_calls_git_with_ff_only(self, tmp_path: Path, monkeypatch):
        captured: list[list[str]] = []

        def _spy_run(args, cwd, check, capture_output, text):  # noqa: ANN001
            captured.append(list(args))
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _spy_run)

        git_state.git_pull(tmp_path)

        assert len(captured) == 1
        assert captured[0][:3] == ["git", "pull", "--ff-only"]

    def test_pull_failure_raises_runtime_error(self, tmp_path: Path, monkeypatch):
        def _failing_run(args, cwd, check, capture_output, text):  # noqa: ANN001
            return _FakeCompleted(returncode=1, stderr="conflict")

        monkeypatch.setattr(subprocess, "run", _failing_run)

        with pytest.raises(RuntimeError, match="git pull"):
            git_state.git_pull(tmp_path)


# ============================================================================
# git_commit_and_push
# ============================================================================


class TestGitCommitAndPush:
    def test_no_changes_returns_false(self, tmp_path: Path, monkeypatch):
        """diff --cached --quiet 가 0 (변경 없음) → noop."""
        call_log: list[list[str]] = []

        def _fake_run(args, cwd, check=False, capture_output=False, text=False):  # noqa: ANN001
            call_log.append(list(args))
            # diff --cached --quiet 명령은 변경 없음 (returncode=0) 반환
            if args[:3] == ["git", "diff", "--cached"]:
                return _FakeCompleted(returncode=0)
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        pushed = git_state.git_commit_and_push(tmp_path, "test")
        assert pushed is False
        # commit / push 가 호출되지 않았는지 확인
        assert not any(args[:2] == ["git", "commit"] for args in call_log)
        assert not any(args[:2] == ["git", "push"] for args in call_log)

    def test_with_changes_calls_commit_and_push(self, tmp_path: Path, monkeypatch):
        call_log: list[list[str]] = []

        def _fake_run(args, cwd, check=False, capture_output=False, text=False):  # noqa: ANN001
            call_log.append(list(args))
            # diff --cached --quiet → 변경 있음 (returncode=1)
            if args[:3] == ["git", "diff", "--cached"]:
                return _FakeCompleted(returncode=1)
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        pushed = git_state.git_commit_and_push(tmp_path, "test message")
        assert pushed is True
        # commit / push 호출 확인
        assert any(args[:2] == ["git", "commit"] for args in call_log)
        assert any(args[:2] == ["git", "push"] for args in call_log)

    def test_commit_failure_raises(self, tmp_path: Path, monkeypatch):
        def _fake_run(args, cwd, check=False, capture_output=False, text=False):  # noqa: ANN001
            if args[:3] == ["git", "diff", "--cached"]:
                return _FakeCompleted(returncode=1)
            if args[:2] == ["git", "commit"]:
                return _FakeCompleted(returncode=1, stderr="commit failed")
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        with pytest.raises(RuntimeError, match="git commit"):
            git_state.git_commit_and_push(tmp_path, "test")

    def test_user_config_set_before_commit(self, tmp_path: Path, monkeypatch):
        call_log: list[list[str]] = []

        def _fake_run(args, cwd, check=False, capture_output=False, text=False):  # noqa: ANN001
            call_log.append(list(args))
            if args[:3] == ["git", "diff", "--cached"]:
                return _FakeCompleted(returncode=1)
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        git_state.git_commit_and_push(tmp_path, "test", user_name="my-bot", user_email="bot@example.com")

        # user.name / user.email 설정이 commit 이전에 호출되었는지 확인
        config_calls = [args for args in call_log if args[:2] == ["git", "config"]]
        assert any("user.name" in args for args in config_calls)
        assert any("user.email" in args for args in config_calls)
        assert any("my-bot" in args for args in config_calls)
