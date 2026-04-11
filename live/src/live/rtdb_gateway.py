"""Firebase Realtime Database 게이트웨이.

Step 12에서 다음 함수들이 구현된다 (설계서 10장, 부록 A 참고).

- ``fetch_unprocessed_fills(app) -> list[ActualFill]``
- ``mark_fills_processed(app, keys: list[str]) -> None``
- ``write_read_model(app, state: LiveState, result: DailyResult) -> None``
- ``write_chart_data(app, series: dict[str, ChartSeries]) -> None``
- ``read_device_tokens(app) -> list[str]``
- ``remove_invalid_tokens(app, tokens: list[str]) -> None``

원칙:

- Firebase Admin SDK 초기화는 이 모듈에서 담당 (모듈 상단 cache 또는 ``initialize_app``).
- RTDB URL: ``https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app``
- RTDB 쓰기 실패 시 즉시 예외 전파. 호출자가 중단 + 알림을 책임진다.
"""
