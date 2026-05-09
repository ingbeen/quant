"""GCS 기반 정본 저장소 게이트웨이.

[BRIEFING §6.1 / §6.5](../../docs/BRIEFING_git_state_to_gcs.md) 의 정책 구현.

핵심:

- 단일 객체 download / upload / list / delete + ephemeral 워크스페이스 컨텍스트.
- 모든 외부 의존(GCS) 실패는 ``RuntimeError`` 로 전파한다 (자동 복구 금지 — live
  도메인 핵심 원칙 1).
- generation precondition (``if_generation_match``) 위반은 ``RuntimeError``.
- ``state_workspace`` 컨텍스트는 변경된 파일만 upload 하며 ``live_state.json`` 을
  마지막에 업로드한다 (LiveState 일관성 보호 — BRIEFING §6.5).

함수:

- :func:`download_blob` — 단일 blob → 로컬 파일
- :func:`upload_blob` — 로컬 파일 → 단일 blob (낙관적 동시성 옵션)
- :func:`list_blobs_with_prefix` — prefix 매칭 blob 목록
- :func:`delete_blob` — 단일 blob 삭제 (Soft Delete 자동 보호)
- :func:`state_workspace` — 매 CLI 실행마다 GCS ↔ tempdir 동기화 컨텍스트
"""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from firebase_admin import storage as fa_storage

from live.constants import DEFAULT_LIVE_STATE_FILENAME, STATE_BUCKET_NAME
from qbt.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = [
    "download_blob",
    "upload_blob",
    "list_blobs_with_prefix",
    "delete_blob",
    "state_workspace",
]


def _bucket():
    """버킷 핸들 획득. firebase_admin 이 내부적으로 캐싱한다."""
    try:
        return fa_storage.bucket(name=STATE_BUCKET_NAME)
    except Exception as exc:
        raise RuntimeError(f"GCS 버킷 핸들 획득 실패: bucket={STATE_BUCKET_NAME}, exc={exc}") from exc


def download_blob(blob_path: Path | str, dest_local_path: Path) -> None:
    """GCS blob 의 내용을 지정 로컬 경로에 download 한다.

    Args:
        blob_path: GCS 객체 경로 (예: ``'live_state.json'`` 또는 ``'data/stock/SPY.csv'``).
        dest_local_path: 다운로드 대상 로컬 파일 경로. 부모 디렉토리는 자동 생성.

    Raises:
        RuntimeError: 다운로드 실패 시 (없는 blob / 네트워크 / 권한 등).
    """
    name = str(blob_path)
    dest_local_path.parent.mkdir(parents=True, exist_ok=True)
    bucket = _bucket()
    blob = bucket.blob(name)
    try:
        blob.download_to_filename(str(dest_local_path))
    except Exception as exc:
        raise RuntimeError(f"GCS download 실패: blob={name}, dest={dest_local_path}, exc={exc}") from exc


def upload_blob(
    local_path: Path,
    blob_path: Path | str,
    *,
    if_generation_match: int | None = None,
) -> int:
    """로컬 파일을 GCS blob 으로 upload 한다.

    Args:
        local_path: 업로드할 로컬 파일 경로.
        blob_path: GCS 객체 경로.
        if_generation_match: 낙관적 동시성 체크. 지정 시 현재 generation 과 일치할
            때만 업로드. 일치하지 않으면 ``RuntimeError`` (412 PreconditionFailed).

    Returns:
        업로드 후 새 generation 정수.

    Raises:
        RuntimeError: 업로드 실패 또는 generation mismatch.
    """
    name = str(blob_path)
    bucket = _bucket()
    blob = bucket.blob(name)
    try:
        if if_generation_match is not None:
            blob.upload_from_filename(str(local_path), if_generation_match=if_generation_match)
        else:
            blob.upload_from_filename(str(local_path))
    except Exception as exc:
        raise RuntimeError(
            f"GCS upload 실패: blob={name}, local={local_path}, " f"if_generation_match={if_generation_match}, exc={exc}"
        ) from exc
    # ``blob.generation`` 은 업로드 직후 서버 응답으로 항상 채워지지만, 타입 스텁은
    # ``int | None`` 으로 표기되어 있다. 호출자에게는 항상 ``int`` 를 반환한다.
    return int(blob.generation or 0)


def list_blobs_with_prefix(prefix: str) -> list[Any]:
    """``prefix`` 로 시작하는 blob 들을 반환한다.

    Args:
        prefix: GCS 객체 경로 prefix (예: ``'data/stock/'``). 빈 문자열은 전체.

    Returns:
        blob 객체 리스트. 호출자는 ``b.name`` / ``b.size`` / ``b.generation`` 등을 사용.

    Raises:
        RuntimeError: list 호출 실패 시.
    """
    bucket = _bucket()
    try:
        return list(bucket.list_blobs(prefix=prefix))
    except Exception as exc:
        raise RuntimeError(f"GCS list 실패: prefix={prefix!r}, exc={exc}") from exc


def delete_blob(blob_path: Path | str) -> None:
    """blob 을 삭제한다. Soft Delete 는 GCS 자체 정책으로 자동 보호.

    Args:
        blob_path: GCS 객체 경로.

    Raises:
        RuntimeError: 삭제 실패 (없는 blob / 권한 등).
    """
    name = str(blob_path)
    bucket = _bucket()
    blob = bucket.blob(name)
    try:
        blob.delete()
    except Exception as exc:
        raise RuntimeError(f"GCS delete 실패: blob={name}, exc={exc}") from exc


# ============================================================================
# state_workspace — ephemeral 워크스페이스 컨텍스트
# ============================================================================


def _sha256(path: Path) -> str:
    """파일의 sha256 hex digest. 변경 감지에 사용."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _sort_for_upload(names: list[str]) -> list[str]:
    """upload 순서 정렬 — ``live_state.json`` 을 가장 마지막으로.

    BRIEFING §6.5 — 부분 실패 시 LiveState 갱신을 마지막으로 미루어 다음 실행이
    정합 복원 가능하도록 한다.
    """
    rest = sorted(n for n in names if n != DEFAULT_LIVE_STATE_FILENAME)
    if DEFAULT_LIVE_STATE_FILENAME in names:
        return rest + [DEFAULT_LIVE_STATE_FILENAME]
    return rest


@contextmanager
def state_workspace(*, push_on_success: bool) -> Iterator[Path]:
    """매 CLI 실행마다 GCS 버킷 ↔ tempdir 동기화 흐름.

    [BRIEFING §6.2 / §6.5](../../docs/BRIEFING_git_state_to_gcs.md) 의 정책 구현.

    흐름:

    1. tempdir 생성
    2. 버킷의 모든 blob 을 tempdir 로 download (구조 그대로)
    3. download 시점 sha256 스냅샷 기록
    4. ``yield workspace``
    5. 정상 종료 시 sha256 비교로 **변경된 파일만** upload
    6. ``live_state.json`` 은 항상 마지막에 upload (BRIEFING §6.5)
    7. tempdir 자동 삭제

    본문 예외 시: ``yield`` 가 예외를 다시 raise 하므로 5~6 단계로 진입하지 않는다.
    부분 upload 로 LiveState 일관성이 깨지는 시나리오 방지.

    Args:
        push_on_success: ``True`` 면 정상 종료 시 변경분 upload. 읽기 전용 명령
            (``drift`` / ``backfill-chart-years``) 은 ``False``.

    Yields:
        tempdir 내부의 워크스페이스 루트 (``Path``). 이 경로를 ``state_dir`` 로 사용.

    Raises:
        RuntimeError: download / upload 실패 시 (자동 복구 금지 원칙에 따라 전파).
    """
    with tempfile.TemporaryDirectory(prefix="qbt-live-gcs-") as td:
        workspace = Path(td) / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        logger.debug(f"state_workspace 시작: {workspace}")

        # 1. 버킷의 모든 blob 을 tempdir 로 download
        blobs = list_blobs_with_prefix("")
        snapshots: dict[str, str] = {}  # name → sha256
        for blob in blobs:
            local = workspace / blob.name
            download_blob(blob.name, local)
            snapshots[blob.name] = _sha256(local)
        logger.debug(f"state_workspace download 완료: {len(blobs)} blobs")

        # 2. yield — 본문 예외 시 자동 raise 후 아래 코드 미실행
        yield workspace

        # 3. 정상 종료 — push_on_success 시에만 변경분 upload
        if not push_on_success:
            logger.debug("state_workspace read-only — upload skip")
            return

        modified: list[str] = []
        for local_file in workspace.rglob("*"):
            if not local_file.is_file():
                continue
            rel = local_file.relative_to(workspace).as_posix()  # GCS 는 '/' 사용
            current_hash = _sha256(local_file)
            old_hash = snapshots.get(rel)
            if old_hash != current_hash:
                modified.append(rel)

        for name in _sort_for_upload(modified):
            local_file = workspace / Path(name)
            upload_blob(local_file, name)
            logger.debug(f"state_workspace upload: {name}")

        logger.debug(f"state_workspace upload 완료: {len(modified)} files")
