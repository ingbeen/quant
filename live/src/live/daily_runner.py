"""일일 실행 엔진 (순수 계산, I/O 없음).

Step 7에서 다음 함수가 구현된다 (설계서 4.2, 부록 A 참고).

- ``run_daily(trade_date, state, market_bundle, pending_fills, applied_fill_ids) -> DailyResult``

실행 순서 (설계서 4.2):

1. fills 자동 매칭 → actual 반영
2. 전일 pending → 당일 시가 model 체결
3. signal intents → projected → 리밸런싱 → merge
4. 익일 pending 생성
5. 미입력 체크 → 리마인더 목록 생성
6. DailyResult 반환 (파일 I/O 없음)

원칙:

- 파일 I/O 및 네트워크 호출 금지. 순수 계산만.
- QBT 코어 재사용 (``qbt.backtest.strategies.buffer_zone`` 등). QBT 본체 수정 금지.
- 예외 발생 시 그대로 전파. 상태 변경은 호출자가 save 하기 전까지 미반영.
"""
