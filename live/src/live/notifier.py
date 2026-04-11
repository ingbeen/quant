"""알림 모듈 (FCM + 텔레그램, 항상 동시 발송).

Step 13에서 다음 함수들이 구현된다 (설계서 8장, 11장, 부록 A 참고).

- ``send_all(tokens, tg_token, tg_chat, result: DailyResult) -> None``
    일일 리포트, 시그널, 리밸런싱, 미입력 리마인더 포함.
- ``send_failure_all(tokens, tg_token, tg_chat, msg: str) -> None``
    에러 상세 메시지를 포함한 실패 알림.

원칙:

- FCM 과 텔레그램은 **항상 동시 발송**. 하나가 실패해도 다른 하나는 독립적으로 시도.
- 에러 알림에는 반드시 에러 상세 메시지 포함 (사용자 디버깅 용이).
- 200일선 근접도(``(close - ema_200) / ema_200 * 100``) 를 본문에 포함.
- 이모지 사용 금지, 한글 메시지 원칙.
"""
