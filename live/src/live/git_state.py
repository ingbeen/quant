"""qbt-live-state 프라이빗 리포 git 동기화 헬퍼.

설계서 1.3 / 4.2 / 10.1: 모든 정본은 qbt-live-state 리포에 commit 된다.
GitHub Actions 환경에서는 ``actions/checkout`` 으로 리포가 이미 체크아웃되어 있으므로
본 모듈은 ``git`` subprocess 호출만 담당한다.

함수:

- :func:`git_pull` — 원격 변경사항 가져오기
- :func:`git_commit_and_push` — 변경된 모든 파일 add / commit / push (변경 없으면 noop)

원칙:

- subprocess 실행. 실패 시 RuntimeError 전파 (자동 복구 금지).
- git 자격증명은 호출자(GitHub Actions actions/checkout 또는 사용자 환경) 책임.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

__all__ = ["git_pull", "git_commit_and_push"]


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """git subcommand 실행. 실패 시 RuntimeError."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} 실패 (cwd={cwd}, returncode={result.returncode}): " f"stderr={result.stderr.strip()}"
        )
    return result


def git_pull(state_dir: Path) -> None:
    """``state_dir`` 에서 ``git pull`` 을 실행한다.

    Args:
        state_dir: qbt-live-state 작업 디렉토리.

    Raises:
        RuntimeError: git pull 실패 시 (네트워크 / 인증 / 충돌).
    """
    _run_git(["pull", "--ff-only"], state_dir)


def git_commit_and_push(
    state_dir: Path,
    message: str,
    *,
    user_name: str = "qbt-live-bot",
    user_email: str = "qbt-live-bot@noreply.github.com",
) -> bool:
    """변경된 모든 파일을 commit & push 한다.

    변경 사항이 없으면 noop 으로 ``False`` 반환. push 까지 성공하면 ``True``.

    Args:
        state_dir: qbt-live-state 작업 디렉토리.
        message: commit 메시지.
        user_name: git config user.name (CI 환경 기본값).
        user_email: git config user.email.

    Returns:
        커밋 + push 가 발생하면 ``True``, 변경 없음으로 skip 시 ``False``.

    Raises:
        RuntimeError: git 명령 실패 시.
    """
    # 1. user.name / user.email 설정 (멱등)
    _run_git(["config", "user.name", user_name], state_dir)
    _run_git(["config", "user.email", user_email], state_dir)

    # 2. 모든 변경 stage
    _run_git(["add", "-A"], state_dir)

    # 3. 변경사항 확인
    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=str(state_dir),
        check=False,
    )
    if diff_result.returncode == 0:
        # 변경 없음
        return False

    # 4. commit + push
    _run_git(["commit", "-m", message], state_dir)
    _run_git(["push"], state_dir)
    return True
