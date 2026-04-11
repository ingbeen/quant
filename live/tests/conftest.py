"""live 도메인 공통 pytest 픽스처.

테스트 작성 원칙은 ``tests/CLAUDE.md`` 와 ``live/CLAUDE.md`` 를 참고한다.
외부 네트워크 호출(Firebase, yfinance, 텔레그램) 은 **항상 mock** 처리한다.

본 파일의 autouse fixture 는 네트워크 격리 안전망을 제공한다.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def block_real_network_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    """실수로 실제 FCM / 텔레그램 네트워크 호출이 나가지 않도록 안전망.

    개별 테스트가 ``_safe_notify_failure`` / ``_send_daily_notifications`` 를 명시적으로
    mock 하지 않아도, 이 autouse fixture 가 **모든 live 테스트**에 대해 기본적으로
    no-op 으로 교체한다. 개별 테스트가 이 함수의 호출 여부를 검증해야 하는 경우는
    해당 테스트 내부에서 다시 monkeypatch 로 덮어쓸 수 있다 (autouse 보다 우선 적용).

    배경: Phase 4 작업 중 일부 테스트가 `fetch_pending_balance_adjusts` mock 을
    빠뜨려 `cli._cmd_run_daily` 가 예외 → `_safe_notify_failure` → 실제 텔레그램
    API 호출로 이어진 사건 이후 추가됨.
    """
    try:
        from live import cli as cli_module
    except ImportError:
        return

    monkeypatch.setattr(cli_module, "_safe_notify_failure", lambda app, msg: None, raising=False)
    monkeypatch.setattr(
        cli_module, "_send_daily_notifications", lambda app, result: None, raising=False
    )
