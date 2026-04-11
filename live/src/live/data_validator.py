"""주가 데이터 검증 모듈.

Step 6에서 다음 함수들이 구현된다 (설계서 3장, 부록 A 참고).

- ``validate_ohlc_logic(row) -> list[str]``
- ``validate_prev_close(csv_close: float, yf_close: float) -> list[str]``
- ``validate_date_gap(csv_last: date, today: date, calendar) -> list[str]``

검증 항목:

1. OHLC 논리 (``High < Low``, 0/음수 가격)
2. 전일 종가 연속성 (CSV vs yfinance 1% 이상 차이)
3. 거래일 누락 (exchange_calendars 기반)

원칙: 검증 실패 시 에러 메시지 리스트 반환. 호출자가 즉시 중단 + 알림을 책임진다.
보간/자동 복구 금지.
"""
