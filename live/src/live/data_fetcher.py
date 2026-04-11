"""주가 데이터 수집 및 CSV 누적 모듈.

Step 5에서 다음 함수들이 구현된다 (설계서 2장, 부록 A 참고).

- ``fetch_recent_ohlc(ticker: str, days: int = 5) -> pd.DataFrame``
- ``append_today_to_csv(csv_path: Path, today_row: pd.DataFrame) -> None``
- ``rebuild_full_csv(ticker: str, csv_path: Path, period: str = "max") -> None``
- ``load_csv(csv_path: Path) -> pd.DataFrame``

원칙:

- yfinance 호출은 예외 발생 시 즉시 전파. 자동 재시도 없음.
- CSV 포맷은 QBT 본체 ``src/qbt/utils/data_loader.py`` 와 호환되어야 한다.
- 같은 날짜 중복 append 금지 (멱등성 유지).
"""
