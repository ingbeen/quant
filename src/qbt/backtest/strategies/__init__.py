"""백테스트 전략 패키지

전략별 모듈을 제공한다.
- strategy_common: SignalStrategy Protocol
- buffer_zone_helpers: 버퍼존 전용 compute_bands, detect_buy/sell_signal
- buffer_zone: 버퍼존 통합 config-driven 전략 모듈 (4P 고정, CONFIGS 는 buffer_zone.py 참조)
- buy_and_hold: 매수 후 보유 벤치마크 전략 (팩토리 패턴으로 멀티 티커 지원)
"""
