"""백테스트 엔진 패키지

엔진별 모듈을 제공한다.
- engine_common: PendingOrder, TradeRecord, EquityRecord, 체결/equity 기록 공통 함수
- backtest_engine: 단일 백테스트 엔진 (run_backtest, run_grid_search)
- portfolio_planning: 주문 의도(OrderIntent), 시그널/투영/병합 함수
- portfolio_rebalance: 리밸런싱 정책(RebalancePolicy), 월 첫 거래일 판정 함수
- portfolio_execution: SELL→BUY 순 체결 함수 (AssetState는 portfolio_types.py에 정의)
- portfolio_data: 데이터 로딩/검증, 에쿼티 DataFrame 빌드 함수
- portfolio_engine: 포트폴리오 백테스트 facade (run_portfolio_backtest)
"""
