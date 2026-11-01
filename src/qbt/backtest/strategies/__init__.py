"""백테스트 전략 패키지

전략별 모듈을 제공한다.
- strategy_common: SignalStrategy Protocol
- buffer_zone_helpers: 버퍼존 전용 compute_bands, detect_buy/sell_signal
- buffer_zone: 버퍼존 통합 config-driven 전략 모듈 (4P 고정, CONFIGS 는 buffer_zone.py 참조)
- buffer_zone_v2: 돌파 뒤 한달을 지켜보고 장중 손절로 파는 버퍼존 (신호 · 매매 같은 티커)
- split_ladder: 스플릿 매매의 값과 자산별 설정 (계산은 engines/split_engine.py)
- buy_and_hold: 매수 후 보유 벤치마크 전략 (팩토리 패턴으로 멀티 티커 지원)
"""
