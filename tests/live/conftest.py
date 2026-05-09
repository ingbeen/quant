"""live 도메인 공통 pytest 픽스처.

테스트 작성 원칙은 ``tests/CLAUDE.md`` 와 ``live/CLAUDE.md`` 를 참고한다.
외부 네트워크 호출(Firebase, yfinance, 텔레그램) 은 **항상 mock** 처리한다.

본 파일의 autouse fixture 는 네트워크 격리 안전망을 제공한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest


@pytest.fixture(autouse=True)
def block_real_network_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    """실수로 실제 FCM / 텔레그램 네트워크 호출이 나가지 않도록 안전망.

    개별 테스트가 ``_safe_notify_failure`` / ``_send_daily_notifications`` 를 명시적으로
    mock 하지 않아도, 이 autouse fixture 가 **모든 live 테스트**에 대해 기본적으로
    no-op 으로 교체한다. 개별 테스트가 이 함수의 호출 여부를 검증해야 하는 경우는
    해당 테스트 내부에서 다시 monkeypatch 로 덮어쓸 수 있다 (autouse 보다 우선 적용).

    배경: 과거에 일부 테스트가 `fetch_pending_balance_adjusts` 등 의존성 mock 을
    빠뜨려 `cli._cmd_run_daily` 가 예외 → `_safe_notify_failure` → 실제 텔레그램
    API 호출로 이어진 사고가 있었기 때문에 안전망으로 유지한다.
    """
    try:
        from live import cli as cli_module
    except ImportError:
        return

    monkeypatch.setattr(cli_module, "_safe_notify_failure", lambda app, msg: None, raising=False)
    monkeypatch.setattr(cli_module, "_send_daily_notifications", lambda app, result: None, raising=False)


# ============================================================================
# Fake GCS bucket — storage_gateway 테스트용 in-memory 시뮬레이션
# ============================================================================


class FakePreconditionError(Exception):
    """google.api_core.exceptions.PreconditionFailed (412) 시뮬레이션."""


class FakeNotFoundError(Exception):
    """google.cloud.exceptions.NotFound (404) 시뮬레이션."""


class FakeBlob:
    """``google.cloud.storage.Blob`` 의 최소 시뮬레이션.

    storage_gateway 가 사용하는 메서드만 흉내낸다: upload_from_filename /
    download_to_filename / delete / generation. ``if_generation_match`` precondition
    위반은 :class:`FakePreconditionError` 를 raise 한다 (실제
    ``google.api_core.exceptions.PreconditionFailed`` 와 동일 위치).
    """

    def __init__(self, name: str, *, _bucket: "FakeBucket | None" = None) -> None:
        self.name = name
        self._bucket = _bucket
        self._data: bytes | None = None
        self.generation: int = 0
        self.size: int = 0

    def upload_from_filename(
        self,
        filename: str,
        *,
        if_generation_match: int | None = None,
    ) -> None:
        if if_generation_match is not None and self.generation != if_generation_match:
            raise FakePreconditionError(
                f"generation mismatch: expected={if_generation_match}, actual={self.generation}"
            )
        self._data = Path(filename).read_bytes()
        self.generation += 1
        self.size = len(self._data)
        if self._bucket is not None:
            self._bucket.upload_log.append(self.name)

    def download_to_filename(self, filename: str) -> None:
        if self._data is None:
            raise FakeNotFoundError(f"blob not found: {self.name}")
        Path(filename).write_bytes(self._data)

    def delete(self) -> None:
        if self._data is None:
            raise FakeNotFoundError(f"blob not found: {self.name}")
        self._data = None
        self.size = 0

    def reload(self) -> None:  # storage_gateway 가 metadata refresh 시 사용 가능
        if self._data is None:
            raise FakeNotFoundError(f"blob not found: {self.name}")

    @property
    def exists_in_fake(self) -> bool:
        return self._data is not None


class FakeBucket:
    """``google.cloud.storage.Bucket`` 의 최소 시뮬레이션.

    blobs 를 dict 로 보관하고 prefix 기반 list 만 제공한다. Soft Delete 는
    시뮬레이션하지 않는다 (테스트 범위 외).

    부가 기능 (테스트 편의):

    - ``upload_log``: blob.upload_from_filename 호출 순서를 name 으로 기록.
      live_state.json 마지막 upload 같은 순서 정책 검증에 사용.
    - ``seed(name, content)``: tracker 를 거치지 않고 blob 데이터를 직접 주입.
      테스트의 'Given' 단계에서 사용.
    """

    def __init__(self, name: str = "qbt-live.firebasestorage.app") -> None:
        self.name = name
        self._blobs: dict[str, FakeBlob] = {}
        self.upload_log: list[str] = []

    def blob(self, name: str) -> FakeBlob:
        if name not in self._blobs:
            self._blobs[name] = FakeBlob(name, _bucket=self)
        return self._blobs[name]

    def list_blobs(self, prefix: str = "") -> list[FakeBlob]:
        return [b for n, b in self._blobs.items() if n.startswith(prefix) and b.exists_in_fake]

    def seed(self, name: str, content: bytes) -> FakeBlob:
        """테스트 헬퍼 — upload_log tracker 를 거치지 않고 blob 을 직접 주입한다.

        Given 단계에서 GCS 에 사전 데이터를 심을 때 사용. 실제 ``upload_from_filename``
        호출과 구분되어 ``upload_log`` 에 기록되지 않는다.
        """
        blob = self.blob(name)
        blob._data = content
        blob.size = len(content)
        blob.generation = 1
        return blob


@pytest.fixture
def fake_gcs_bucket(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeBucket]:
    """``firebase_admin.storage.bucket(...)`` 호출을 in-memory FakeBucket 으로 대체.

    storage_gateway 의 모든 단위 테스트가 본 픽스처를 사용한다. 테스트는 픽스처가
    반환한 ``FakeBucket`` 에 직접 blob 을 심거나 결과를 검증할 수 있다.

    Yields:
        :class:`FakeBucket` 인스턴스.
    """
    fake = FakeBucket()

    def _mock_bucket(name: str | None = None) -> FakeBucket:
        # 실제 firebase_admin.storage.bucket(name=...) 시그니처와 호환.
        return fake

    # firebase_admin.storage 가 아직 import 되지 않은 환경에서도 안전하게 patch.
    import firebase_admin.storage as fa_storage

    monkeypatch.setattr(fa_storage, "bucket", _mock_bucket)
    yield fake
