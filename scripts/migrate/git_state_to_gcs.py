"""qbt-live-state git 리포 → GCS 버킷 1회성 마이그레이션 스크립트.

본 스크립트는 [BRIEFING_git_state_to_gcs.md §6.6](../../docs/BRIEFING_git_state_to_gcs.md)
의 정본 데이터 1회성 이관을 자동화한다.

흐름:

1. 임시 디렉토리에 ``qbt-live-state`` 리포를 일반 clone (depth 미지정 — 전체 데이터)
2. ``.git/`` 을 제외한 모든 파일을 GCS 버킷에 업로드 (디렉토리 구조 1:1 미러링)
3. 업로드 검증: 객체 수 / 총 사이즈 / ``live_state.json`` sha256 비교
4. 검증 실패 시 stderr + ``sys.exit(1)``

전제:

- ``GOOGLE_APPLICATION_CREDENTIALS`` 환경변수 — Firebase service account JSON 경로
- ``STATE_REPO_PAT`` 환경변수 — qbt-live-state private repo clone 용 GitHub PAT
  (본 스크립트가 1회 실행 후 폐기되는 마이그레이션 도구이므로, 본 변수도 cutover
  시점에만 일시적으로 사용한다)

실행:

    poetry run python scripts/migrate/git_state_to_gcs.py [--dry-run]

본 스크립트는 cutover 직전 1회 실행 후 폐기 / 보관은 운영자 결정.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage as fa_storage

# 본 스크립트는 1회성이므로 live 모듈의 상수에 의존하지 않고 자체 상수로 운영한다.
# 이렇게 하면 마이그레이션 후 live 모듈이 변경되어도 본 스크립트의 동작은 영향받지 않는다.
STATE_REPO_URL = "https://github.com/ingbeen/qbt-live-state.git"
STATE_BUCKET_NAME = "qbt-live.firebasestorage.app"
LIVE_STATE_FILENAME = "live_state.json"


def _embed_pat(url: str, pat: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(netloc=f"{pat}@{parsed.hostname}"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _clone_state_repo(dest: Path, pat: str) -> None:
    """qbt-live-state 리포를 일반 clone (depth 미지정)."""
    url = _embed_pat(STATE_REPO_URL, pat)
    result = subprocess.run(
        ["git", "clone", url, str(dest)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # PAT 가 stderr 에 노출되지 않도록 원본 URL 만 표시.
        sys.stderr.write(
            f"[ERROR] git clone 실패 (remote={STATE_REPO_URL}, "
            f"returncode={result.returncode}): stderr={result.stderr.strip()}\n"
        )
        sys.exit(1)


def _initialize_firebase() -> None:
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
        sys.stderr.write("[ERROR] GOOGLE_APPLICATION_CREDENTIALS 환경변수 미설정\n")
        sys.exit(1)
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {"storageBucket": STATE_BUCKET_NAME})


def _collect_files(root: Path) -> list[Path]:
    """``.git/`` 메타데이터를 제외한 모든 파일을 수집한다."""
    files: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part == ".git" for part in p.parts):
            continue
        files.append(p)
    return files


def _upload_files(files: list[Path], root: Path, *, dry_run: bool) -> None:
    """파일을 GCS 버킷에 업로드 (또는 dry-run 시 시뮬레이션)."""
    bucket = fa_storage.bucket()
    for f in files:
        rel = f.relative_to(root).as_posix()
        size = f.stat().st_size
        if dry_run:
            print(f"[dry-run] gs://{STATE_BUCKET_NAME}/{rel}  ({size} bytes)")
            continue
        blob = bucket.blob(rel)
        blob.upload_from_filename(str(f))
        print(f"upload    gs://{STATE_BUCKET_NAME}/{rel}  ({size} bytes)")


def _verify(files: list[Path], root: Path) -> None:
    """업로드 검증. 실패 시 sys.exit(1)."""
    bucket = fa_storage.bucket()
    blobs = list(bucket.list_blobs())

    # 1. 객체 수 / 이름 비교
    blob_names = sorted(b.name for b in blobs)
    file_names = sorted(f.relative_to(root).as_posix() for f in files)
    if blob_names != file_names:
        missing = set(file_names) - set(blob_names)
        extra = set(blob_names) - set(file_names)
        sys.stderr.write(
            f"[ERROR] 객체 이름 집합 불일치: blob={len(blob_names)}, file={len(file_names)}\n"
            f"  로컬에만 존재 (업로드 누락): {sorted(missing)}\n"
            f"  버킷에만 존재 (사전 잔재): {sorted(extra)}\n"
        )
        sys.exit(1)
    print(f"[OK] 객체 이름 집합 일치 — {len(file_names)} 개")

    # 2. live_state.json sha256 비교 (가장 중요한 정본)
    live_state_local = root / LIVE_STATE_FILENAME
    if live_state_local.exists():
        local_hash = _sha256(live_state_local)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            bucket.blob(LIVE_STATE_FILENAME).download_to_filename(tmp.name)
            remote_hash = _sha256(Path(tmp.name))
        if local_hash != remote_hash:
            sys.stderr.write(
                f"[ERROR] {LIVE_STATE_FILENAME} sha256 불일치: "
                f"local={local_hash}, remote={remote_hash}\n"
            )
            sys.exit(1)
        print(f"[OK] {LIVE_STATE_FILENAME} sha256 일치 — {local_hash[:16]}...")

    # 3. 총 사이즈 비교
    local_size = sum(f.stat().st_size for f in files)
    # blob.size 가 None 인 케이스 방어
    remote_size = sum((b.size or 0) for b in blobs)
    if local_size != remote_size:
        sys.stderr.write(f"[ERROR] 총 사이즈 불일치: local={local_size}, remote={remote_size}\n")
        sys.exit(1)
    print(f"[OK] 총 사이즈 일치 — {local_size} bytes")


def main() -> int:
    parser = argparse.ArgumentParser(description="qbt-live-state git → GCS 1회성 마이그레이션")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 업로드 없이 대상 파일 목록 / 사이즈만 출력",
    )
    args = parser.parse_args()

    pat = os.environ.get("STATE_REPO_PAT")
    if not pat:
        sys.stderr.write("[ERROR] STATE_REPO_PAT 환경변수 미설정 (qbt-live-state clone 용)\n")
        return 1

    _initialize_firebase()

    with tempfile.TemporaryDirectory(prefix="qbt-live-migration-") as td:
        clone_root = Path(td) / "qbt-live-state"
        print(f"[1/3] qbt-live-state 리포 clone → {clone_root}")
        _clone_state_repo(clone_root, pat)

        files = _collect_files(clone_root)
        print(f"      collected {len(files)} files")

        if args.dry_run:
            print(f"[2/3] [dry-run] 업로드 시뮬레이션")
            _upload_files(files, clone_root, dry_run=True)
            print(f"[3/3] [dry-run] 검증 단계 skip — 실제 실행 시 객체 수 / 사이즈 / sha256 비교")
            return 0

        print(f"[2/3] {len(files)} 파일을 gs://{STATE_BUCKET_NAME} 으로 업로드")
        _upload_files(files, clone_root, dry_run=False)

        print(f"[3/3] 업로드 검증")
        _verify(files, clone_root)

    print("\n마이그레이션 완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
