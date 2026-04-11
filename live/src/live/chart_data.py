"""차트 시계열 생성 모듈 (RTDB 업로드용).

Step 14에서 다음 함수가 구현된다 (설계서 7장, 부록 A 참고).

- ``build_chart_series(csv_dir: Path, user_trades) -> dict[str, ChartSeries]``

생성 내용 (자산별 전체 기간):

- ``dates``: 날짜 리스트
- ``close``: 종가 리스트
- ``ema_200``: 200일 EMA (초기 199일은 ``None``)
- ``upper_band`` / ``lower_band``: 버퍼존 밴드
- ``buy_signals`` / ``sell_signals``: 시스템 시그널 인덱스
- ``user_buys`` / ``user_sells``: 사용자 체결 인덱스

용도: RTDB ``/latest/chart_data/{asset_id}`` 에 매일 덮어쓰기 저장.
앱(TradingView Lightweight Charts) 에서 기간 선택 렌더링.
"""
