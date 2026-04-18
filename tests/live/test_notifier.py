"""live.notifier — FCM + 텔레그램 동시 발송 테스트.

firebase_admin / requests 를 monkeypatch 로 대체하여 외부 호출 없이 검증한다.
"""

from __future__ import annotations

from typing import Any

import pytest

from live import notifier as notifier_module
from live.models import DailyResult, DriftReport, SignalDetection
from live.notifier import (
    NotificationOutcome,
    send_all,
    send_failure_all,
)
from live.state import create_initial_state

# ============================================================================
# fixtures
# ============================================================================


def _make_daily_result() -> DailyResult:
    state = create_initial_state(100_000_000.0)
    drift_report = DriftReport(
        model_equity=100_000_000.0,
        actual_equity=99_500_000.0,
        drift_pct=0.005,
        per_asset={},
        recommendation="정상",
    )
    return DailyResult(
        execution_date="2026-04-10",
        updated_state=state,
        updated_applied_fill_ids={},
        updated_applied_balance_adjust_ids={},
        updated_applied_fill_dismiss_ids={},
        signals={
            "sso": SignalDetection(
                state="buy",
                close=420.5,
                upper_band=418.0,
                lower_band=398.0,
                ma_value=410.0,
                ma_distance_pct=0.0256,
            ),
            "qld": SignalDetection(
                state="none",
                close=85.0,
                upper_band=87.0,
                lower_band=80.0,
                ma_value=84.0,
                ma_distance_pct=0.0119,
            ),
        },
        order_intents={},
        executions=None,
        rebalance_triggered=True,
        model_equity=100_000_000.0,
        actual_equity=99_500_000.0,
        drift_pct=0.005,
        drift_report=drift_report,
        ma_distances={"sso": 0.0256, "qld": 0.0119},
        notification_body="",
        pending_fill_reminders=["sso pending"],
        model_sync_applied=False,
    )


@pytest.fixture
def patched_fcm_success(monkeypatch):
    """FCM 발송 mock — 모두 성공."""
    calls: dict[str, Any] = {}

    def _mock_send(tokens: list[str], body: str) -> tuple[int, list[str]]:
        calls["tokens"] = tokens
        calls["body"] = body
        return len(tokens), []

    monkeypatch.setattr(notifier_module, "_send_fcm_messages", _mock_send)
    return calls


@pytest.fixture
def patched_telegram_success(monkeypatch):
    """텔레그램 발송 mock — 200 응답."""
    calls: dict[str, Any] = {}

    def _mock_send(tg_token: str, tg_chat: str, body: str) -> bool:
        calls["tg_token"] = tg_token
        calls["tg_chat"] = tg_chat
        calls["body"] = body
        return True

    monkeypatch.setattr(notifier_module, "_send_telegram_message", _mock_send)
    return calls


# ============================================================================
# send_all
# ============================================================================


class TestSendAll:
    def test_returns_notification_outcome(self, patched_fcm_success, patched_telegram_success):
        result = _make_daily_result()
        outcome = send_all(
            tokens=["t1", "t2"],
            tg_token="bot:abc",
            tg_chat="chat_xyz",
            result=result,
        )
        assert isinstance(outcome, NotificationOutcome)

    def test_fcm_called_with_all_tokens(self, patched_fcm_success, patched_telegram_success):
        result = _make_daily_result()
        send_all(
            tokens=["t1", "t2", "t3"],
            tg_token="bot:abc",
            tg_chat="chat_xyz",
            result=result,
        )
        assert patched_fcm_success["tokens"] == ["t1", "t2", "t3"]

    def test_telegram_called_with_credentials(self, patched_fcm_success, patched_telegram_success):
        result = _make_daily_result()
        send_all(
            tokens=["t1"],
            tg_token="my_bot_token",
            tg_chat="my_chat_id",
            result=result,
        )
        assert patched_telegram_success["tg_token"] == "my_bot_token"
        assert patched_telegram_success["tg_chat"] == "my_chat_id"

    def test_body_contains_ma_distance_line(self, patched_fcm_success, patched_telegram_success):
        """본문에 MA 근접도 섹션이 포함되어야 한다."""
        result = _make_daily_result()
        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]
        assert "MA 근접도" in body
        assert "SPY" in body

    def test_ma_distance_uses_signal_tickers(self, patched_fcm_success, patched_telegram_success):
        """MA 근접도는 signal 티커(SPY, QQQ)로 표시되어야 하며, trade 티커(SSO, QLD)는 표시되지 않아야 한다.

        Given: sso/qld 의 ma_distances 가 포함된 DailyResult
        When: send_all 호출
        Then: 본문에 SPY/QQQ 가 표시되고, MA 근접도 라인에 SSO/QLD 는 없다
        """
        result = _make_daily_result()
        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]

        ma_line = [line for line in body.splitlines() if "MA 근접도" in line]
        assert len(ma_line) == 1
        ma_text = ma_line[0]
        assert "SPY" in ma_text
        assert "QQQ" in ma_text
        assert "SSO" not in ma_text
        assert "QLD" not in ma_text

    def test_body_contains_signals_when_buy_or_sell(self, patched_fcm_success, patched_telegram_success):
        result = _make_daily_result()
        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]
        assert "시그널" in body
        assert "SSO buy" in body  # 매수 시그널 표시

    def test_body_contains_rebalance_when_triggered(self, patched_fcm_success, patched_telegram_success):
        result = _make_daily_result()
        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]
        assert "리밸런싱" in body

    def test_body_contains_drift(self, patched_fcm_success, patched_telegram_success):
        result = _make_daily_result()
        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]
        assert "drift" in body

    def test_fcm_failure_does_not_block_telegram(self, monkeypatch, patched_telegram_success):
        """FCM 예외가 발생해도 텔레그램은 정상 발송."""

        def _failing_fcm(tokens, body):  # noqa: ANN001
            raise RuntimeError("FCM down")

        monkeypatch.setattr(notifier_module, "_send_fcm_messages", _failing_fcm)

        outcome = send_all(["t1"], "bot", "chat", _make_daily_result())
        assert outcome.fcm_sent_count == 0
        assert outcome.telegram_ok is True

    def test_telegram_failure_does_not_block_fcm(self, patched_fcm_success, monkeypatch):
        """텔레그램 예외가 발생해도 FCM 은 정상 발송."""

        def _failing_telegram(tg_token, tg_chat, body):  # noqa: ANN001
            raise RuntimeError("Telegram down")

        monkeypatch.setattr(notifier_module, "_send_telegram_message", _failing_telegram)

        outcome = send_all(["t1", "t2"], "bot", "chat", _make_daily_result())
        assert outcome.fcm_sent_count == 2
        assert outcome.telegram_ok is False

    def test_both_failures_return_zero(self, monkeypatch):
        def _fail_fcm(tokens, body):  # noqa: ANN001
            raise RuntimeError("x")

        def _fail_tg(tg_token, tg_chat, body):  # noqa: ANN001
            raise RuntimeError("y")

        monkeypatch.setattr(notifier_module, "_send_fcm_messages", _fail_fcm)
        monkeypatch.setattr(notifier_module, "_send_telegram_message", _fail_tg)

        outcome = send_all(["t1"], "bot", "chat", _make_daily_result())
        assert outcome.fcm_sent_count == 0
        assert outcome.telegram_ok is False

    def test_invalid_tokens_propagated(self, monkeypatch, patched_telegram_success):
        """FCM mock 이 invalid_tokens 를 반환하면 outcome 에 누적."""

        def _mock_fcm(tokens, body):  # noqa: ANN001
            return 1, ["expired_token"]

        monkeypatch.setattr(notifier_module, "_send_fcm_messages", _mock_fcm)
        outcome = send_all(["valid", "expired_token"], "bot", "chat", _make_daily_result())
        assert outcome.fcm_invalid_tokens == ["expired_token"]


# ============================================================================
# send_failure_all
# ============================================================================


class TestSendFailureAll:
    def test_failure_body_contains_message_and_marker(self, patched_fcm_success, patched_telegram_success):
        send_failure_all(
            tokens=["t1"],
            tg_token="bot",
            tg_chat="chat",
            message="yfinance 수집 실패: timeout",
        )
        body = patched_telegram_success["body"]
        assert "[QBT Live 실패]" in body
        assert "yfinance 수집 실패" in body
        assert "timeout" in body

    def test_failure_send_independent_channels(self, monkeypatch, patched_telegram_success):
        """FCM 예외 시에도 텔레그램 발송."""

        def _fail_fcm(tokens, body):  # noqa: ANN001
            raise RuntimeError("fcm gone")

        monkeypatch.setattr(notifier_module, "_send_fcm_messages", _fail_fcm)

        outcome = send_failure_all(["t1"], "bot", "chat", "오류 발생")
        assert outcome.telegram_ok is True
        assert outcome.fcm_sent_count == 0


# ============================================================================
# 빈 토큰 / 본문 빌더
# ============================================================================


class TestDailyBodyLayout:
    """_build_daily_body 레이아웃 계약: 강조 블록(시그널/리밸런싱/리마인더) 이
    equity/drift 보다 상단에 위치하고 빈 줄로 구분된다."""

    def test_highlights_appear_before_equity(self, patched_fcm_success, patched_telegram_success):
        """Given 시그널 + 리밸런싱 + 리마인더 전부 있는 결과
        When send_all
        Then 강조 항목이 equity 줄보다 위에 있다."""
        result = _make_daily_result()
        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]
        lines = body.splitlines()

        signal_idx = next(i for i, line in enumerate(lines) if "시그널" in line)
        rebalance_idx = next(i for i, line in enumerate(lines) if "리밸런싱" in line)
        reminder_idx = next(i for i, line in enumerate(lines) if "미입력 체결 리마인더" in line)
        equity_idx = next(i for i, line in enumerate(lines) if "model equity" in line)

        assert signal_idx < equity_idx
        assert rebalance_idx < equity_idx
        assert reminder_idx < equity_idx

    def test_blank_line_separates_highlights_from_equity(self, patched_fcm_success, patched_telegram_success):
        """Given 강조 항목이 있는 결과
        When send_all
        Then 강조 블록과 equity 블록 사이에 빈 줄이 존재한다."""
        result = _make_daily_result()
        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]
        lines = body.splitlines()

        equity_idx = next(i for i, line in enumerate(lines) if "model equity" in line)

        # 강조 블록 마지막과 equity 사이에 빈 줄
        assert equity_idx >= 2  # 제목 + 빈 줄 + 강조 항목 + 빈 줄 이후
        assert lines[equity_idx - 1].strip() == ""

    def test_no_extra_blank_line_when_no_highlights(self, patched_fcm_success, patched_telegram_success):
        """Given 강조 항목이 하나도 없는 결과
        When send_all
        Then 제목 직후 빈 줄 1 개만 있고 equity 가 바로 따라온다."""
        result = _make_daily_result()
        # 강조 항목 전부 제거
        result.signals = {}
        result.rebalance_triggered = False
        result.pending_fill_reminders = []

        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]
        lines = body.splitlines()

        # 첫 줄: 제목, 둘째 줄: 빈 줄, 셋째 줄: model equity
        assert "[QBT Live]" in lines[0]
        assert lines[1].strip() == ""
        assert "model equity" in lines[2]

    def test_model_sync_applied_shown_when_true(self, patched_fcm_success, patched_telegram_success):
        """Given model_sync_applied=True When send_all Then 강조 블록에 'Model 동기화 적용' 라인 노출."""
        result = _make_daily_result()
        result.model_sync_applied = True

        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]

        assert "Model 동기화 적용" in body

    def test_model_sync_applied_hidden_when_false(self, patched_fcm_success, patched_telegram_success):
        """Given model_sync_applied=False When send_all Then 본문에 'Model 동기화 적용' 문자열 없음."""
        result = _make_daily_result()
        result.model_sync_applied = False

        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]

        assert "Model 동기화 적용" not in body

    def test_model_sync_appears_first_in_highlights(self, patched_fcm_success, patched_telegram_success):
        """Given 동기화 + 시그널 + 리밸런싱 + 리마인더 모두 존재 When send_all Then 동기화 라인이 최상단."""
        result = _make_daily_result()
        result.model_sync_applied = True

        send_all(["t1"], "bot", "chat", result)
        body = patched_telegram_success["body"]
        lines = body.splitlines()

        sync_idx = next(i for i, line in enumerate(lines) if "Model 동기화 적용" in line)
        signal_idx = next(i for i, line in enumerate(lines) if "시그널" in line)
        rebalance_idx = next(i for i, line in enumerate(lines) if "리밸런싱" in line)
        reminder_idx = next(i for i, line in enumerate(lines) if "미입력 체결 리마인더" in line)

        assert sync_idx < signal_idx
        assert sync_idx < rebalance_idx
        assert sync_idx < reminder_idx


class TestEmptyTokens:
    def test_empty_token_list_skips_fcm(self, monkeypatch, patched_telegram_success):
        called: list[bool] = []

        def _mock_fcm(tokens, body):  # noqa: ANN001
            called.append(True)
            return 0, []

        monkeypatch.setattr(notifier_module, "_send_fcm_messages", _mock_fcm)
        outcome = send_all([], "bot", "chat", _make_daily_result())
        # 빈 토큰 리스트도 _safe_fcm 을 거치지만 내부에서 0 반환
        assert outcome.fcm_sent_count == 0
        assert outcome.telegram_ok is True


# ============================================================================
# _safe_fcm / _safe_telegram — 실패 시 로그 기록 (알림 재발송 금지)
# ============================================================================


class TestNotifierErrorLogging:
    """알림 채널 발송 실패 시 재발송 없이 logger.error 로만 기록해야 한다."""

    def test_safe_fcm_logs_error_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given _send_fcm_messages 가 예외 When _safe_fcm Then logger.error 기록 + (0, []) 반환.

        notifier 의 logger 는 ``qbt.utils.logger.get_logger`` 로 생성되며
        ``propagate=False`` 로 설정되어 pytest caplog 가 자동으로 잡지 못한다.
        따라서 logger 자체를 spy 로 monkeypatch 한다.
        """
        logged: list[str] = []

        def _spy_error(message: str, *args, **kwargs) -> None:  # noqa: ANN001, ANN002, ANN003
            logged.append(message)

        def _failing_fcm(tokens, body):  # noqa: ANN001
            raise RuntimeError("테스트: FCM 네트워크 에러")

        monkeypatch.setattr(notifier_module, "_send_fcm_messages", _failing_fcm)
        monkeypatch.setattr(notifier_module.logger, "error", _spy_error)

        result = notifier_module._safe_fcm(["t1"], "테스트 본문")

        assert result == (0, [])
        assert any("FCM" in msg or "fcm" in msg.lower() for msg in logged), "FCM 실패 시 logger.error 기록 누락"
        assert any("테스트: FCM 네트워크 에러" in msg for msg in logged), "에러 메시지가 로그에 포함되지 않음 — 디버깅 정보 손실"

    def test_safe_telegram_logs_error_on_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given _send_telegram_message 가 예외 When _safe_telegram Then logger.error 기록 + False 반환."""
        logged: list[str] = []

        def _spy_error(message: str, *args, **kwargs) -> None:  # noqa: ANN001, ANN002, ANN003
            logged.append(message)

        def _failing_tg(tg_token, tg_chat, body):  # noqa: ANN001
            raise RuntimeError("테스트: 텔레그램 API 에러")

        monkeypatch.setattr(notifier_module, "_send_telegram_message", _failing_tg)
        monkeypatch.setattr(notifier_module.logger, "error", _spy_error)

        result = notifier_module._safe_telegram("bot", "chat", "테스트 본문")

        assert result is False
        assert any("텔레그램" in msg or "telegram" in msg.lower() for msg in logged), "텔레그램 실패 시 logger.error 기록 누락"
        assert any("테스트: 텔레그램 API 에러" in msg for msg in logged), "에러 메시지가 로그에 포함되지 않음 — 디버깅 정보 손실"

    def test_safe_fcm_does_not_raise_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given _send_fcm_messages 가 예외 When _safe_fcm Then raise 하지 않음.

        알림 실패가 상위 로직을 중단시키면 이미 실패한 흐름이 더 크게 깨진다.
        """

        def _failing_fcm(tokens, body):  # noqa: ANN001
            raise RuntimeError("테스트")

        monkeypatch.setattr(notifier_module, "_send_fcm_messages", _failing_fcm)

        # raise 하지 않고 (0, []) 반환해야 함
        result = notifier_module._safe_fcm(["t1"], "본문")
        assert result == (0, [])

    def test_safe_telegram_does_not_raise_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Given _send_telegram_message 가 예외 When _safe_telegram Then raise 하지 않음."""

        def _failing_tg(tg_token, tg_chat, body):  # noqa: ANN001
            raise RuntimeError("테스트")

        monkeypatch.setattr(notifier_module, "_send_telegram_message", _failing_tg)

        result = notifier_module._safe_telegram("bot", "chat", "본문")
        assert result is False
