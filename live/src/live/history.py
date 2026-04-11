"""히스토리 저장 모듈 (Git 정본, 전체 영구 보존).

Step 15에서 다음 함수들이 구현된다 (설계서 10.1 참고).

- ``save_daily_log(date, payload: dict) -> Path``
    일별 상세 로그를 ``history/daily/{YYYY-MM-DD}.json`` 으로 저장.
- ``append_summary(summary: dict) -> None``
    요약을 ``history/summary.jsonl`` 에 JSON 라인 형식으로 append.
- ``append_user_trade(trade: dict) -> None``
    사용자 체결 입력을 ``history/user_trades.jsonl`` 에 append.

원칙:

- **전체 영구 보존**. 자동 정리 없음.
- 같은 날짜 중복 호출 시에도 덮어쓰지 않고 각각 append (호출자 책임).
- 저장 위치는 qbt-live-state 프라이빗 리포 내부.
"""
