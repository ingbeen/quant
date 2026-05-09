"""live.storage_gateway — GCS 기반 정본 저장소 게이트웨이 테스트.

본 테스트는 [docs/BRIEFING_git_state_to_gcs.md](../../docs/BRIEFING_git_state_to_gcs.md)
§6.1 / §6.5 의 정책을 코드로 고정한다 (Phase 0).

핵심 정책:

- 단일 객체 read / write / list / delete 시그니처
- 실패 시 ``RuntimeError`` 전파 (자동 복구 금지 — live 도메인 핵심 원칙 1)
- generation precondition (``if_generation_match``) 위반 시 ``RuntimeError``
- ``state_workspace`` 컨텍스트:

  - tempdir 생성 → 모든 blob download → yield → 변경된 파일만 upload → tempdir 삭제
  - 변경 감지: download 시점 sha256 스냅샷 vs 종료 시점 sha256 비교
  - write 순서 보호: ``live_state.json`` 을 가장 마지막에 upload (BRIEFING §6.5)
  - read-only (``push_on_success=False``) 시 upload skip
  - 컨텍스트 본문 예외 시 upload skip (LiveState 일관성 보호)
"""

from __future__ import annotations

import pytest

from live import storage_gateway

# ============================================================================
# download_blob
# ============================================================================


class TestDownloadBlob:
    """``storage_gateway.download_blob`` 의 시그니처 / 동작 / 예외 정책 고정."""

    def test_writes_blob_content_to_local_file(self, fake_gcs_bucket, tmp_path):
        """
        목적: download_blob 이 GCS blob 의 내용을 지정 로컬 경로에 기록하는지 검증.

        Given: GCS 에 'live_state.json' blob 이 존재 (`{"foo":1}`)
        When: download_blob 으로 다운로드
        Then: 로컬 파일에 동일 바이트가 기록됨
        """
        # Given
        fake_gcs_bucket.seed("live_state.json", b'{"foo":1}')
        dest = tmp_path / "dest.json"

        # When
        storage_gateway.download_blob("live_state.json", dest)

        # Then
        assert dest.read_bytes() == b'{"foo":1}'

    def test_missing_blob_raises_runtime_error(self, fake_gcs_bucket, tmp_path):
        """
        목적: 없는 blob 다운로드 시 RuntimeError 전파 (자동 복구 금지 원칙).

        live 도메인 핵심 원칙 1 — 장애 시 자동 복구 금지. 외부 의존 (GCS) 의
        모든 실패는 RuntimeError 로 호출자에게 전파되어야 한다.
        """
        with pytest.raises(RuntimeError):
            storage_gateway.download_blob("missing.json", tmp_path / "x")


# ============================================================================
# upload_blob
# ============================================================================


class TestUploadBlob:
    """``storage_gateway.upload_blob`` 의 시그니처 / generation 정책."""

    def test_writes_local_file_to_blob(self, fake_gcs_bucket, tmp_path):
        """
        목적: upload_blob 이 로컬 파일 내용을 GCS blob 으로 업로드하는지 검증.
        """
        # Given
        local = tmp_path / "data.json"
        local.write_bytes(b'{"bar":2}')

        # When
        storage_gateway.upload_blob(local, "data.json")

        # Then
        blob = fake_gcs_bucket.blob("data.json")
        assert blob.exists_in_fake
        assert blob._data == b'{"bar":2}'

    def test_returns_new_generation(self, fake_gcs_bucket, tmp_path):
        """
        목적: upload_blob 은 업로드 후 새 generation 을 반환한다.

        낙관적 동시성 (optimistic concurrency) 흐름에서 호출자가 generation 을
        보관해두고 다음 upload 시 ``if_generation_match`` 로 사용할 수 있어야 한다.
        """
        local = tmp_path / "x.json"
        local.write_bytes(b"v1")

        gen1 = storage_gateway.upload_blob(local, "x.json")
        local.write_bytes(b"v2")
        gen2 = storage_gateway.upload_blob(local, "x.json")

        assert gen2 > gen1

    def test_generation_precondition_match_succeeds(self, fake_gcs_bucket, tmp_path):
        """``if_generation_match`` 가 현재 generation 과 일치하면 업로드 성공."""
        local = tmp_path / "x.json"
        local.write_bytes(b"v1")

        gen1 = storage_gateway.upload_blob(local, "x.json")
        local.write_bytes(b"v2")

        # generation 일치 → 정상 업로드
        gen2 = storage_gateway.upload_blob(local, "x.json", if_generation_match=gen1)
        assert gen2 > gen1

    def test_generation_precondition_mismatch_raises_runtime_error(self, fake_gcs_bucket, tmp_path):
        """
        목적: generation mismatch (412 PreconditionFailed) 시 RuntimeError 전파.

        BRIEFING §6.5 — 동시 실행 충돌 감지. 다른 실행이 동시에 덮어써서 generation
        이 변했다면 즉시 실패하고 호출자에게 전파한다 (자동 복구 금지).
        """
        local = tmp_path / "x.json"
        local.write_bytes(b"v1")
        storage_gateway.upload_blob(local, "x.json")

        # 일부러 잘못된 generation 으로 업로드 시도
        with pytest.raises(RuntimeError):
            storage_gateway.upload_blob(local, "x.json", if_generation_match=999)


# ============================================================================
# list_blobs_with_prefix
# ============================================================================


class TestListBlobsWithPrefix:
    """``storage_gateway.list_blobs_with_prefix`` 의 시그니처 / 동작."""

    def test_returns_blobs_matching_prefix(self, fake_gcs_bucket):
        """prefix 로 시작하는 객체만 반환."""
        # Given
        fake_gcs_bucket.seed("data/stock/SPY.csv", b"a")
        fake_gcs_bucket.seed("data/stock/QQQ.csv", b"b")
        fake_gcs_bucket.seed("live_state.json", b"c")

        # When
        result = storage_gateway.list_blobs_with_prefix("data/stock/")

        # Then
        names = sorted(b.name for b in result)
        assert names == ["data/stock/QQQ.csv", "data/stock/SPY.csv"]

    def test_empty_prefix_returns_all_blobs(self, fake_gcs_bucket):
        """빈 prefix 는 모든 blob 반환 (state_workspace 의 전체 download 에 사용)."""
        # Given
        fake_gcs_bucket.seed("a.json", b"a")
        fake_gcs_bucket.seed("b/c.json", b"b")

        # When
        result = storage_gateway.list_blobs_with_prefix("")

        # Then
        assert len(result) == 2


# ============================================================================
# delete_blob
# ============================================================================


class TestDeleteBlob:
    """``storage_gateway.delete_blob`` 의 시그니처 / 예외 정책."""

    def test_removes_blob(self, fake_gcs_bucket):
        """delete_blob 호출 시 blob 이 list 에서 사라진다 (Soft Delete 보호는 GCS 자체 책임)."""
        # Given
        fake_gcs_bucket.seed("temp.json", b"a")

        # When
        storage_gateway.delete_blob("temp.json")

        # Then
        assert storage_gateway.list_blobs_with_prefix("") == []

    def test_missing_blob_raises_runtime_error(self, fake_gcs_bucket):
        """없는 blob 삭제 시 RuntimeError 전파 (자동 복구 금지 원칙)."""
        with pytest.raises(RuntimeError):
            storage_gateway.delete_blob("missing.json")


# ============================================================================
# state_workspace 컨텍스트
# ============================================================================


class TestStateWorkspace:
    """``storage_gateway.state_workspace`` 의 흐름 / 정책 고정.

    BRIEFING §6.2 워크스페이스 컨텍스트 정의:

    - tempdir 생성 → 모든 blob 을 tempdir 로 download → yield → 변경된 파일만
      upload (live_state.json 마지막) → tempdir 자동 삭제

    BRIEFING §6.5 LiveState 일관성 보호:

    - live_state.json 을 항상 마지막에 upload
    - 컨텍스트 본문 예외 시 upload skip
    """

    def test_downloads_all_blobs_into_tempdir(self, fake_gcs_bucket):
        """
        목적: 컨텍스트 진입 시 GCS 의 모든 blob 이 tempdir 에 download 되는지 검증.
        """
        # Given
        fake_gcs_bucket.seed("live_state.json", b'{"v":1}')
        fake_gcs_bucket.seed("data/stock/SPY.csv", b"date,close\n2026-01-01,100\n")

        # When + Then
        with storage_gateway.state_workspace(push_on_success=False) as workspace:
            assert (workspace / "live_state.json").read_bytes() == b'{"v":1}'
            assert (workspace / "data/stock/SPY.csv").read_bytes() == b"date,close\n2026-01-01,100\n"

    def test_uploads_only_modified_files(self, fake_gcs_bucket):
        """
        목적: 변경된 파일만 GCS 로 upload (불필요한 트래픽 절감 — BRIEFING §6.2).

        Given: blob A / B 가 존재, 컨텍스트 안에서 A 만 수정
        Then: A 만 generation 이 증가, B 는 그대로
        """
        # Given
        fake_gcs_bucket.seed("a.txt", b"a-original")
        fake_gcs_bucket.seed("b.txt", b"b-original")
        gen_a_before = fake_gcs_bucket.blob("a.txt").generation
        gen_b_before = fake_gcs_bucket.blob("b.txt").generation

        # When
        with storage_gateway.state_workspace(push_on_success=True) as workspace:
            (workspace / "a.txt").write_bytes(b"a-modified")
            # b.txt 는 건드리지 않음

        # Then
        assert fake_gcs_bucket.blob("a.txt").generation > gen_a_before
        assert fake_gcs_bucket.blob("b.txt").generation == gen_b_before
        assert fake_gcs_bucket.blob("a.txt")._data == b"a-modified"

    def test_uploads_newly_created_files(self, fake_gcs_bucket):
        """
        목적: 컨텍스트 안에서 새로 생성된 파일도 upload 대상에 포함.

        예: history/states/2026-05-09.json 같은 신규 일별 스냅샷.
        """
        # Given
        fake_gcs_bucket.seed("live_state.json", b'{"v":1}')

        # When
        with storage_gateway.state_workspace(push_on_success=True) as workspace:
            new_file = workspace / "history/states/2026-05-09.json"
            new_file.parent.mkdir(parents=True, exist_ok=True)
            new_file.write_bytes(b'{"snapshot":"new"}')

        # Then
        new_blob = fake_gcs_bucket.blob("history/states/2026-05-09.json")
        assert new_blob.exists_in_fake
        assert new_blob._data == b'{"snapshot":"new"}'

    def test_live_state_json_uploaded_last(self, fake_gcs_bucket):
        """
        목적: BRIEFING §6.5 — LiveState 최신성 보호.

        live_state.json 이 컨텍스트 종료 시점에 가장 마지막으로 upload 되어야 한다.
        부분 실패 시 LiveState 만 늦게 갱신되어 다음 실행이 정합 복원할 수 있다.
        """
        # Given (seed 는 upload_log 에 기록되지 않음)
        fake_gcs_bucket.seed("live_state.json", b'{"v":0}')
        fake_gcs_bucket.seed("data/stock/SPY.csv", b"old")
        fake_gcs_bucket.seed("history/summary.jsonl", b"old\n")

        # When
        with storage_gateway.state_workspace(push_on_success=True) as workspace:
            (workspace / "live_state.json").write_bytes(b'{"v":1}')
            (workspace / "data/stock/SPY.csv").write_bytes(b"new")
            (workspace / "history/summary.jsonl").write_bytes(b"new\n")

        # Then — upload_log 의 마지막 원소가 live_state.json
        assert fake_gcs_bucket.upload_log[-1] == "live_state.json"
        # 그리고 다른 두 파일은 live_state.json 보다 먼저 upload 되어야 함
        assert "data/stock/SPY.csv" in fake_gcs_bucket.upload_log[:-1]
        assert "history/summary.jsonl" in fake_gcs_bucket.upload_log[:-1]

    def test_read_only_mode_skips_upload(self, fake_gcs_bucket):
        """
        목적: ``push_on_success=False`` 면 컨텍스트 안에서 파일을 수정해도
        upload 가 일어나지 않는다 (drift / backfill-chart-years 같은 read-only 명령).
        """
        # Given
        fake_gcs_bucket.seed("a.txt", b"a-original")
        gen_before = fake_gcs_bucket.blob("a.txt").generation

        # When
        with storage_gateway.state_workspace(push_on_success=False) as workspace:
            (workspace / "a.txt").write_bytes(b"a-modified-but-not-pushed")

        # Then — generation / 데이터 그대로
        assert fake_gcs_bucket.blob("a.txt").generation == gen_before
        assert fake_gcs_bucket.blob("a.txt")._data == b"a-original"
        assert fake_gcs_bucket.upload_log == []

    def test_tempdir_cleaned_after_context(self, fake_gcs_bucket):
        """컨텍스트 종료 시 tempdir 가 자동 삭제되는지 검증 (디스크 leak 방지)."""
        # Given
        fake_gcs_bucket.seed("a.txt", b"a")

        # When
        with storage_gateway.state_workspace(push_on_success=False) as workspace:
            captured = workspace
            assert captured.exists()

        # Then
        assert not captured.exists()

    def test_exception_inside_context_skips_upload(self, fake_gcs_bucket):
        """
        목적: BRIEFING §6.5 — 명령 중간 예외 시 부분 upload 로 LiveState 일관성이
        깨지지 않도록, 컨텍스트 본문에서 예외가 raise 되면 upload 단계 자체로
        진입하지 않는다.

        Given: 'a.txt' 가 GCS 에 존재
        When: 컨텍스트 안에서 a.txt 수정 후 ValueError raise
        Then: GCS 의 a.txt 는 원본 그대로 (부분 upload 없음)
        """
        # Given
        fake_gcs_bucket.seed("a.txt", b"a-original")
        gen_before = fake_gcs_bucket.blob("a.txt").generation

        # When
        with pytest.raises(ValueError):
            with storage_gateway.state_workspace(push_on_success=True) as workspace:
                (workspace / "a.txt").write_bytes(b"a-half-written")
                raise ValueError("simulated mid-command failure")

        # Then
        assert fake_gcs_bucket.blob("a.txt").generation == gen_before
        assert fake_gcs_bucket.blob("a.txt")._data == b"a-original"
        assert fake_gcs_bucket.upload_log == []
