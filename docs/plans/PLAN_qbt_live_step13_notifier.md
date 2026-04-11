# Implementation Plan: QBT Live - Step 13 알림 (notifier.py)

> SoT: [docs/CLAUDE.md](../CLAUDE.md)

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

---

**작성일**: 2026-04-11 14:15
**관련 문서**: 설계서 8장, 11장, 부록 A, TODO Step 13

---

## 0) 고정 규칙

> 🚫 삭제/수정 금지 🚫

- validate_project 는 마지막 Phase 에서만
- Phase 0 레드 허용, Phase 1 이후 그린 유지

## 1) 목표

- [x] 목표 1: `send_all(tokens, tg_token, tg_chat, result)` — FCM + 텔레그램 동시 발송
- [x] 목표 2: `send_failure_all(tokens, tg_token, tg_chat, msg)` — 에러 상세 포함 실패 알림
- [x] 목표 3: 200 일선 근접도 (`ema_distance_pct`) 를 알림 본문에 포함
- [x] 목표 4: FCM 과 텔레그램은 **항상 독립 발송** — 한쪽 실패해도 다른쪽 정상 시도
- [x] 목표 5: 만료 토큰 감지 → 호출자에게 invalid_tokens 리스트 반환

## 2) 비목표

- 실제 FCM/Telegram 호출 (수동 테스트 M-13.1~13.3)
- RTDB device_tokens 직접 읽기 (Step 12 rtdb_gateway 가 담당)

## 3) 배경/맥락

### 동기

- 일일 리포트 / 시그널 / 리밸런싱 / 에러 / 미입력 리마인더 5 종 알림 (설계서 8장)
- FCM 과 텔레그램은 동시 발송 정책 (한쪽 실패 → 다른쪽 독립)
- 에러 알림에는 stack trace 또는 상세 메시지 포함

### 설계 결정

#### D1. 함수 시그니처 (부록 A)

```python
def send_all(
    tokens: list[str],
    tg_token: str,
    tg_chat: str,
    result: DailyResult,
) -> NotificationOutcome
def send_failure_all(
    tokens: list[str],
    tg_token: str,
    tg_chat: str,
    message: str,
) -> NotificationOutcome
```

`NotificationOutcome` 은 dataclass: `fcm_sent_count`, `fcm_invalid_tokens`, `telegram_ok`.

#### D2. 본문 포맷

- `_build_daily_body(result)`: "실행일: ... / model: ... / drift: ... / 시그널: SSO buy / EMA 근접도: SSO -2.4%, ..."
- `_build_failure_body(message)`: "[QBT Live 실패]\n{message}"
- 이모지 금지, 한글 메시지 (CLAUDE.md)

#### D3. FCM 호출

- `firebase_admin.messaging.send_each(messages)` 로 멀티 토큰 전송
- 각 응답에서 `UnregisteredError` 발생 시 invalid_tokens 에 누적
- firebase_admin lazy import

#### D4. 텔레그램 호출

- `requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage", json={"chat_id": tg_chat, "text": body})`
- 응답 status 200 → ok, 그 외 → False (에러 로그만)

#### D5. 독립 발송

- `try-except` 로 FCM 과 텔레그램을 각각 감싼다. 한쪽 예외가 다른쪽을 막지 않는다.

## 4) DoD

- [x] `live/src/live/notifier.py` 구현
- [x] `live/tests/test_notifier.py` mock 기반 테스트
- [x] firebase_admin / requests 모두 monkeypatch 격리
- [x] black + validate_project 통과
- [x] TODO Step 13 체크박스
- [x] plan Done

## 5) 변경 범위

### 신규

- `live/tests/test_notifier.py`

### 수정

- `live/src/live/notifier.py` (구현)
- `docs/TODO_QBT_LIVE.md`

## 6) 단계별 계획

### Phase 0 — 테스트 선작성

- [x] FCM 성공 / 일부 토큰 만료 / 텔레그램 200 / 텔레그램 4xx / 양쪽 모두 호출 / 한쪽 예외 무시 / 본문에 ema_distance 포함

### Phase 1 — 구현

- [x] `_NotificationOutcome` dataclass
- [x] `_build_daily_body` / `_build_failure_body`
- [x] `_send_fcm` / `_send_telegram` (private)
- [x] `send_all` / `send_failure_all`

### Phase 2 — 문서

- [x] TODO Step 13

### 마지막 Phase — 검증

- [x] black + validate_project
- [x] plan Done

**Validation**: `poetry run python validate_project.py` (passed=741, failed=0, skipped=0)

#### Commit Messages (Final candidates)

1. `live / FCM + 텔레그램 동시 발송 (Step 13)`
2. `live / notifier.py — send_all/send_failure_all`
3. `live / 200일선 근접도 본문 + 만료 토큰 감지`
4. `live / Step 13 독립 발송 + invalid_tokens 누적`
5. `live / 알림 모듈 + mock 기반 테스트`

## 7) 리스크

- 실제 FCM 응답 형식 변동 → mock 의 fidelity 한계
- 텔레그램 rate limit (429) — 본 Step 에서는 무시 (재시도 정책 없음)

## 8) 메모

### 진행 로그 (KST)

- 2026-04-11 14:15: 계획서 작성 + 구현
