"""live 도메인 상수 정의.

Step 2에서 아래 항목들이 구현된다.

- ``LIVE_TICKERS``: 실매매 대상 티커 목록
- ``SIGNAL_TRADE_MAP``: 시그널 → 실거래 자산 매핑 (예: SPY → SSO, QQQ → QLD)
- ``DRIFT_*``: drift 임계값 (정상/주의/보정 필요)
- 경로 상수 (qbt-live-state 디렉토리 기준)

설계서 참고: ``docs/DESIGN_QBT_LIVE_FINAL.md`` 부록 B, 5.1.
"""
