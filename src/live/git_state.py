"""qbt-live-state 프라이빗 리포 git 동기화 헬퍼.

live 정본(상태 / idempotency 원장 / 주가 CSV / 히스토리) 은 모두 qbt-live-state
프라이빗 리포에 commit 된다. 로컬과 GitHub Actions 양쪽에서 동일한 코드 경로로
동작하도록, 본 모듈은 실행 시마다 tempdir 에 clone → 작업 → commit/push → cleanup
흐름을 지원하는 얇은 subprocess 래퍼를 제공한다.

함수:

- :func:`git_clone_shallow` — ``--depth 1`` shallow clone (PAT embed 지원)
- :func:`git_pull` — 원격 변경사항 가져오기
- :func:`git_commit_and_push` — 변경된 모든 파일 add / commit / push (변경 없으면 noop)

원칙:

- subprocess 실행. 실패 시 RuntimeError 전파 (자동 복구 금지).
- git 자격증명은 호출자 책임. ``git_clone_shallow`` 는 PAT 를 URL 에 embed 하는 헬퍼 제공.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from live.constants import GIT_BOT_EMAIL, GIT_BOT_NAME

__all__ = [
    "git_clone_shallow",
    "git_pull",
    "git_commit_and_push",
    "embed_pat_in_url",
]


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


def embed_pat_in_url(remote_url: str, pat: str) -> str:
    """HTTPS git remote URL 에 GitHub PAT 를 embed 한다.

    ``https://github.com/owner/repo.git`` → ``https://<PAT>@github.com/owner/repo.git``.

    Args:
        remote_url: HTTPS git remote URL (예: ``https://github.com/ingbeen/qbt-live-state.git``).
        pat: GitHub Personal Access Token.

    Returns:
        PAT 가 netloc 에 embed 된 URL 문자열.

    Raises:
        ValueError: ``remote_url`` 이 HTTPS 가 아니거나 ``pat`` 이 빈 문자열.
    """
    if not pat:
        raise ValueError("embed_pat_in_url: pat 이 비어있습니다")
    parsed = urlparse(remote_url)
    if parsed.scheme != "https":
        raise ValueError(f"embed_pat_in_url: HTTPS URL 만 지원 (입력: {remote_url})")
    # netloc 에 이미 userinfo 가 있으면 그대로 유지하지 않고 새 PAT 로 교체
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    new_netloc = f"{pat}@{host}"
    return urlunparse(parsed._replace(netloc=new_netloc))


def git_clone_shallow(remote_url: str, dest: Path, *, pat: str | None = None) -> None:
    """원격 리포를 ``--depth 1`` shallow clone 으로 ``dest`` 에 받아온다.

    ``pat`` 이 주어지면 URL 에 embed 하여 HTTPS 인증을 처리한다. ``pat`` 이 ``None`` 인
    경우 URL 을 그대로 사용하며, 인증은 호출자 git credential helper 책임.

    Args:
        remote_url: git remote URL (HTTPS 권장).
        dest: clone 대상 경로. 존재하지 않거나 비어있어야 한다.
        pat: 선택. GitHub Personal Access Token.

    Raises:
        RuntimeError: git clone 실패 시 (네트워크 / 인증 / 권한 / 존재하지 않는 리포).
        ValueError: ``pat`` 이 빈 문자열이거나 URL 형식이 잘못된 경우.
    """
    effective_url = embed_pat_in_url(remote_url, pat) if pat else remote_url
    # clone 은 dest 디렉토리를 직접 만들기 때문에 parent 만 존재하면 된다.
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "clone", "--depth", "1", effective_url, str(dest)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # 에러 메시지에 PAT 가 포함되지 않도록 주의: 원본 remote_url 만 노출
        raise RuntimeError(
            f"git clone --depth 1 실패 (remote={remote_url}, dest={dest}, "
            f"returncode={result.returncode}): stderr={result.stderr.strip()}"
        )


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
    user_name: str = GIT_BOT_NAME,
    user_email: str = GIT_BOT_EMAIL,
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
