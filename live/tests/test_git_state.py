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
    def test_pull_calls_git_with_ff_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[list[str]] = []

        def _spy_run(args: list[str], cwd: Path, check: bool, capture_output: bool, text: bool) -> _FakeCompleted:
            captured.append(list(args))
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _spy_run)

        git_state.git_pull(tmp_path)

        assert len(captured) == 1
        assert captured[0][:3] == ["git", "pull", "--ff-only"]

    def test_pull_failure_raises_runtime_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def _failing_run(args: list[str], cwd: Path, check: bool, capture_output: bool, text: bool) -> _FakeCompleted:
            return _FakeCompleted(returncode=1, stderr="conflict")

        monkeypatch.setattr(subprocess, "run", _failing_run)

        with pytest.raises(RuntimeError, match="git pull"):
            git_state.git_pull(tmp_path)


# ============================================================================
# git_commit_and_push
# ============================================================================


class TestGitCommitAndPush:
    def test_no_changes_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """diff --cached --quiet 가 0 (변경 없음) → noop."""
        call_log: list[list[str]] = []

        def _fake_run(
            args: list[str], cwd: Path, check: bool = False, capture_output: bool = False, text: bool = False
        ) -> _FakeCompleted:
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

    def test_with_changes_calls_commit_and_push(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        call_log: list[list[str]] = []

        def _fake_run(
            args: list[str], cwd: Path, check: bool = False, capture_output: bool = False, text: bool = False
        ) -> _FakeCompleted:
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

    def test_commit_failure_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fake_run(
            args: list[str], cwd: Path, check: bool = False, capture_output: bool = False, text: bool = False
        ) -> _FakeCompleted:
            if args[:3] == ["git", "diff", "--cached"]:
                return _FakeCompleted(returncode=1)
            if args[:2] == ["git", "commit"]:
                return _FakeCompleted(returncode=1, stderr="commit failed")
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _fake_run)

        with pytest.raises(RuntimeError, match="git commit"):
            git_state.git_commit_and_push(tmp_path, "test")

    def test_user_config_set_before_commit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        call_log: list[list[str]] = []

        def _fake_run(
            args: list[str], cwd: Path, check: bool = False, capture_output: bool = False, text: bool = False
        ) -> _FakeCompleted:
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


# ============================================================================
# embed_pat_in_url
# ============================================================================


class TestEmbedPatInUrl:
    def test_embeds_pat_into_https_netloc(self) -> None:
        """Given HTTPS URL + PAT When embed 호출 Then netloc 에 PAT@host 형태."""
        url = "https://github.com/ingbeen/qbt-live-state.git"
        out = git_state.embed_pat_in_url(url, "ghp_abc123")
        assert out == "https://ghp_abc123@github.com/ingbeen/qbt-live-state.git"

    def test_rejects_non_https_scheme(self) -> None:
        """Given SSH URL When embed 호출 Then ValueError."""
        url = "git@github.com:ingbeen/qbt-live-state.git"
        with pytest.raises(ValueError, match="HTTPS"):
            git_state.embed_pat_in_url(url, "ghp_abc")

    def test_rejects_empty_pat(self) -> None:
        """Given 빈 PAT When embed 호출 Then ValueError."""
        with pytest.raises(ValueError, match="pat"):
            git_state.embed_pat_in_url("https://github.com/a/b.git", "")

    def test_replaces_existing_userinfo(self) -> None:
        """Given 이미 userinfo 가 있는 URL 에도 새 PAT 가 덮어쓰기."""
        url = "https://olduser@github.com/a/b.git"
        out = git_state.embed_pat_in_url(url, "newpat")
        assert "newpat@" in out
        assert "olduser" not in out


# ============================================================================
# git_clone_shallow
# ============================================================================


class TestGitCloneShallow:
    def test_clone_invokes_git_clone_depth_1(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given 원격 URL + PAT When clone 호출 Then git clone --depth 1 <url>."""
        captured: list[list[str]] = []

        def _spy_run(
            args: list[str], check: bool = False, capture_output: bool = False, text: bool = False
        ) -> _FakeCompleted:
            captured.append(list(args))
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _spy_run)

        dest = tmp_path / "clone-dest"
        git_state.git_clone_shallow("https://github.com/a/b.git", dest, pat="ghp_xyz")

        assert len(captured) == 1
        cmd = captured[0]
        assert cmd[:4] == ["git", "clone", "--depth", "1"]
        # PAT 가 URL 에 embed 되어 전달됐는지
        assert any("ghp_xyz@github.com" in part for part in cmd)
        # dest 경로가 마지막 인자
        assert cmd[-1] == str(dest)

    def test_clone_without_pat_uses_raw_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[list[str]] = []

        def _spy_run(
            args: list[str], check: bool = False, capture_output: bool = False, text: bool = False
        ) -> _FakeCompleted:
            captured.append(list(args))
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _spy_run)

        git_state.git_clone_shallow("https://github.com/a/b.git", tmp_path / "c", pat=None)

        assert len(captured) == 1
        cmd = captured[0]
        # PAT 없이 원본 URL 그대로 사용
        assert "https://github.com/a/b.git" in cmd

    def test_clone_failure_raises_runtime_error_without_leaking_pat(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given git clone 실패 When 호출 Then RuntimeError 전파.

        에러 메시지는 PAT 를 포함하면 안 된다 (로그 / 알림 누출 방지).
        """

        def _failing_run(
            args: list[str], check: bool = False, capture_output: bool = False, text: bool = False
        ) -> _FakeCompleted:
            return _FakeCompleted(returncode=128, stderr="authentication failed")

        monkeypatch.setattr(subprocess, "run", _failing_run)

        dest = tmp_path / "c"
        with pytest.raises(RuntimeError) as exc_info:
            git_state.git_clone_shallow("https://github.com/a/b.git", dest, pat="ghp_secret_token_XYZ")

        assert "git clone" in str(exc_info.value)
        assert "ghp_secret_token_XYZ" not in str(exc_info.value)

    def test_clone_creates_parent_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def _ok_run(
            args: list[str], check: bool = False, capture_output: bool = False, text: bool = False
        ) -> _FakeCompleted:
            return _FakeCompleted(returncode=0)

        monkeypatch.setattr(subprocess, "run", _ok_run)

        dest = tmp_path / "nested" / "deeper" / "clone-here"
        assert not dest.parent.exists()

        git_state.git_clone_shallow("https://github.com/a/b.git", dest, pat="tok")

        # clone 실행 전에 parent 디렉토리가 생성되어야 함
        assert dest.parent.is_dir()
