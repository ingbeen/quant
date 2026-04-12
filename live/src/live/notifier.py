"""FCM + 텔레그램 알림 (항상 동시 발송).

일일 리포트 및 실패 알림을 FCM 과 텔레그램 두 채널로 동시 발송한다. FCM 과
텔레그램은 **항상 독립 발송** 되며, 한쪽 채널의 실패가 다른 쪽 채널을 막지
않는다.

발송 종류:

- :func:`send_all` — 일일 리포트 (MA 근접도 포함, 시그널/리밸런싱 요약)
- :func:`send_failure_all` — 에러 상세 메시지를 포함한 실패 알림

만료 토큰(`UnregisteredError`) 감지 시 ``NotificationOutcome.fcm_invalid_tokens`` 에
누적되며, 호출자는 이를 ``rtdb_gateway.remove_invalid_tokens`` 로 정리할 수 있다.

**알림 채널 자체의 실패는 로그로만 기록한다**. 알림 발송이 실패한 상황에서
다시 알림을 보내는 것은 모순이며 무한 루프 / 토큰 낭비를 유발한다. 따라서
:func:`_safe_fcm` / :func:`_safe_telegram` 은 예외를 ``logger.error`` 로만
기록하고 기본값을 반환한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests
from firebase_admin import messaging
from firebase_admin.exceptions import FirebaseError

from live.models import DailyResult
from qbt.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = [
    "NotificationOutcome",
    "send_all",
    "send_failure_all",
]


_TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


@dataclass
class NotificationOutcome:
    """알림 발송 결과 요약.

    - ``fcm_sent_count``: 성공적으로 전송된 FCM 메시지 개수
    - ``fcm_invalid_tokens``: 만료/등록 해제된 토큰 (호출자가 RTDB 에서 제거)
    - ``telegram_ok``: 텔레그램 발송 성공 여부
    """

    fcm_sent_count: int = 0
    fcm_invalid_tokens: list[str] = field(default_factory=list)
    telegram_ok: bool = False


# ============================================================================
# 본문 빌더
# ============================================================================


def _format_pct(value: float) -> str:
    """비율(0~1) 을 ``±X.XX%`` 형식으로 변환."""
    return f"{value * 100:+.2f}%"


def _build_daily_body(result: DailyResult) -> str:
    """일일 리포트 본문 생성. MA 근접도 / 시그널 / 리밸런싱 / 리마인더 포함."""
    lines: list[str] = []
    lines.append(f"[QBT Live] {result.execution_date}")
    lines.append(f"model equity: {result.model_equity:,.0f}")
    lines.append(f"actual equity: {result.actual_equity:,.0f}")
    lines.append(f"drift: {result.drift_pct:.2f}%")

    if result.signals:
        sig_summaries: list[str] = []
        for asset_id, sig in result.signals.items():
            if sig.state in ("buy", "sell"):
                sig_summaries.append(f"{asset_id.upper()} {sig.state}")
        if sig_summaries:
            lines.append("시그널: " + ", ".join(sig_summaries))

    if result.ma_distances:
        ma_parts = [f"{aid.upper()} {_format_pct(dist)}" for aid, dist in result.ma_distances.items()]
        lines.append("MA 근접도: " + ", ".join(ma_parts))

    if result.rebalance_triggered:
        lines.append("리밸런싱: 발생")

    if result.pending_fill_reminders:
        lines.append(f"미입력 체결 리마인더: {len(result.pending_fill_reminders)} 건")

    return "\n".join(lines)


def _build_failure_body(message: str) -> str:
    """실패 알림 본문 (에러 상세 포함)."""
    return f"[QBT Live 실패]\n{message}"


# ============================================================================
# FCM / 텔레그램 발송 헬퍼
# ============================================================================


def _send_fcm_messages(tokens: list[str], body: str) -> tuple[int, list[str]]:
    """FCM 으로 본문을 멀티 토큰 전송한다.

    Args:
        tokens: 발송 대상 device 토큰 리스트.
        body: 메시지 본문.

    Returns:
        (성공 개수, 만료 토큰 리스트) 튜플.
    """
    if not tokens:
        return 0, []

    messages = [
        messaging.Message(
            notification=messaging.Notification(title="QBT Live", body=body),
            token=token,
        )
        for token in tokens
    ]
    response = messaging.send_each(messages)

    invalid: list[str] = []
    for token, individual in zip(tokens, response.responses, strict=True):
        if not individual.success:
            err = individual.exception
            if isinstance(err, FirebaseError):
                code = getattr(err, "code", "")
                if "UNREGISTERED" in str(code).upper() or "NOT_FOUND" in str(code).upper():
                    invalid.append(token)
    return response.success_count, invalid


def _send_telegram_message(tg_token: str, tg_chat: str, body: str) -> bool:
    """텔레그램 Bot API 로 본문 전송. 200 OK 면 True."""
    url = _TELEGRAM_API_URL.format(token=tg_token)
    response = requests.post(
        url,
        json={"chat_id": tg_chat, "text": body},
        timeout=10,
    )
    return response.status_code == 200


def _safe_fcm(tokens: list[str], body: str) -> tuple[int, list[str]]:
    """FCM 발송을 try-except 로 감싼 안전 호출.

    알림 채널 실패는 알림으로 재발송하지 않는다 — 로그만 기록하고 기본값 반환.
    """
    try:
        return _send_fcm_messages(tokens, body)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"FCM 발송 실패 (로그만 기록, 재발송 없음): {exc}", exc_info=True)
        return 0, []


def _safe_telegram(tg_token: str, tg_chat: str, body: str) -> bool:
    """텔레그램 발송을 try-except 로 감싼 안전 호출.

    알림 채널 실패는 알림으로 재발송하지 않는다 — 로그만 기록하고 False 반환.
    """
    try:
        return _send_telegram_message(tg_token, tg_chat, body)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"텔레그램 발송 실패 (로그만 기록, 재발송 없음): {exc}", exc_info=True)
        return False


# ============================================================================
# 공개 API
# ============================================================================


def send_all(
    tokens: list[str],
    tg_token: str,
    tg_chat: str,
    result: DailyResult,
) -> NotificationOutcome:
    """일일 리포트를 FCM + 텔레그램으로 동시 발송한다.

    한쪽 채널이 예외를 던져도 다른 쪽 채널에는 영향이 없다.

    Args:
        tokens: FCM device 토큰 목록.
        tg_token: 텔레그램 봇 토큰.
        tg_chat: 텔레그램 채팅 ID.
        result: 당일 ``DailyResult``.

    Returns:
        :class:`NotificationOutcome` — 발송 결과 요약.
    """
    body = _build_daily_body(result)
    fcm_count, invalid_tokens = _safe_fcm(tokens, body)
    telegram_ok = _safe_telegram(tg_token, tg_chat, body)

    return NotificationOutcome(
        fcm_sent_count=fcm_count,
        fcm_invalid_tokens=invalid_tokens,
        telegram_ok=telegram_ok,
    )


def send_failure_all(
    tokens: list[str],
    tg_token: str,
    tg_chat: str,
    message: str,
) -> NotificationOutcome:
    """실패 알림을 FCM + 텔레그램으로 동시 발송한다.

    Args:
        tokens: FCM device 토큰 목록.
        tg_token: 텔레그램 봇 토큰.
        tg_chat: 텔레그램 채팅 ID.
        message: 에러 상세 메시지 (stack trace 등).
    """
    body = _build_failure_body(message)
    fcm_count, invalid_tokens = _safe_fcm(tokens, body)
    telegram_ok = _safe_telegram(tg_token, tg_chat, body)

    return NotificationOutcome(
        fcm_sent_count=fcm_count,
        fcm_invalid_tokens=invalid_tokens,
        telegram_ok=telegram_ok,
    )
