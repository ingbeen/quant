# 백테스트 도메인 가이드

> 이 문서는 `src/qbt/backtest/` 패키지의 백테스트 도메인에 대한 가이드입니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../../../CLAUDE.md)를 참고하세요.

## 도메인 목적

백테스트 도메인은 과거 데이터를 기반으로 거래 전략을 시뮬레이션하고 성과를 측정합니다.
이동평균 기반 버퍼존 전략 및 매수 후 보유(Buy & Hold) 벤치마크 전략을 제공합니다.

---

## 모듈 구성

### 1. types.py

백테스트 도메인의 공통 TypedDict 및 dataclass 정의를 제공합니다.
전략 전용 타입은 각 전략 모듈에 정의합니다.

공통 타입:

- `OpenPositionDict`: 미청산 포지션 정보 (entry_date, entry_price, shares). 백테스트 종료 시 보유 중인 포지션의 진입 정보를 담으며, summary에 포함되어 summary.json에 저장된다
- `SummaryDict`: `calculate_summary()` 반환 타입 (성과 지표 요약). `open_position: NotRequired[OpenPositionDict]` 필드를 포함하여 미청산 포지션 정보를 전달한다
- `BestGridParams`: grid_results.csv 최적 파라미터 (ma_window, buy_buffer_zone_pct, sell_buffer_zone_pct, hold_days)
- `BufferStrategyParams`: 버퍼존 전략 파라미터 (dataclass, frozen=True). initial_capital, ma_window, buy/sell_buffer_zone_pct, hold_days. `run_backtest()` 및 `run_grid_search()` 호출 시 사용. `buffer_zone.py`에서 이곳으로 이동하여 순환 의존성 해소
- `SingleBacktestResult`: 각 전략의 `run_single()` 공통 반환 타입 (dataclass). strategy_name, display_name, signal_df, equity_df, trades_df, summary, params_json, result_dir, data_info 포함
- `WfoWindowResultDict`: WFO 윈도우별 IS/OOS 결과 (window_idx, is/oos 날짜, best params, is/oos 성과 지표, wfe_calmar, wfe_cagr)
- `WfoModeSummaryDict`: WFO 모드별 요약 (n_windows, oos 통계, wfe 통계, gap_calmar_median, profit_concentration, 파라미터별 리스트(param_ma_windows 등), stitched 지표)

### 2. constants.py

백테스트 도메인 전용 상수를 정의합니다.

주요 상수 카테고리:

- 거래 비용: `SLIPPAGE_RATE` (매수 또는 매도 1회당 0.3%, 슬리피지 + 수수료 통합. 왕복 = 매수 + 매도 = 2 × `SLIPPAGE_RATE` ≈ 0.6%)
- 기본 파라미터: `DEFAULT_INITIAL_CAPITAL`
- 수치 안정성: `CALMAR_MDD_ZERO_SUBSTITUTE` (Calmar MDD=0 처리 대용값, `1e10`)
- 제약 조건: `MIN_BUY_BUFFER_ZONE_PCT`, `MIN_SELL_BUFFER_ZONE_PCT`, `MIN_HOLD_DAYS`, `MIN_VALID_ROWS`, `DEFAULT_WFO_MIN_TRADES`
- WFO 파라미터 리스트: `DEFAULT_WFO_MA_WINDOW_LIST`, `DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST` 등 (그리드 서치 + 워크포워드 공용)
- WFO 윈도우 설정: `DEFAULT_WFO_INITIAL_IS_MONTHS`, `DEFAULT_WFO_OOS_MONTHS`
- WFO 결과 파일명: `WALKFORWARD_DYNAMIC_FILENAME` 등

### 3. analysis.py

이동평균 계산 및 성과 지표 분석 함수를 제공합니다.

주요 함수:

- `add_single_moving_average`: 단순이동평균(SMA) 계산. 유형 선택 파라미터가 없다 (「도메인 규칙 1-1」 참고)
- `calculate_summary`: 거래 내역과 자본 곡선으로부터 성과 지표 계산
- `calculate_monthly_returns`: 에쿼티 데이터로부터 월별 수익률 계산
- `calculate_yearly_returns`: 월별 수익률 리스트로부터 연간 복리 수익률 계산 (대시보드 히트맵에 12월 오른쪽 "연간" 컬럼으로 표시)
- `calculate_sharpe_ratio`: 일별 수익률 기반 연율화 샤프 비율 (rf=0 기준, std=0 또는 데이터 부족 시 0.0 반환)
- `calculate_sortino_ratio`: 일별 수익률 기반 연율화 소르티노 비율 (하방 편차 기준, 하방 편차=0 시 0.0 반환)
- `calculate_benchmark_yearly_returns`: 벤치마크(QQQ 등) Close 컬럼과 기간으로부터 연간 복리 수익률 리스트 계산 (대시보드 "연간 수익률 vs QQQ" 섹션에서 사용)

### 4. parameter_stability.py

파라미터 고원 분석 모듈을 제공합니다.
고원 분석 CSV(param*plateau/)를 로딩하고 시각화용 데이터를 가공한다.
4P 확정값은 `constants.py`의 `FIXED_4P*\*` 상수를 참조한다.

주요 함수:

- `load_plateau_pivot(param_name, metric)`: 피벗 CSV 로드 (metric은 run_param_plateau_all.py에서 생성한 지표와 일치해야 함)
- `get_current_value(param_name)`: 4P 확정 파라미터값 반환 (`constants.py`의 `FIXED_4P_*` 참조)
- `get_plateau_dir()`: 고원 분석 결과 디렉토리 경로 반환
- `find_plateau_range(series, threshold_ratio)`: 고원 구간 탐지 (최대값 대비 threshold 이상인 연속 범위)
- `find_plateau_range_with_trade_filter(metric_series, trades_series, min_trades, threshold_ratio)`: 거래 수 필터를 적용한 고원 구간 탐지 (극단 파라미터에서 거래 수 극소로 Calmar가 왜곡되는 경우에 사용)

### 5. walkforward.py

워크포워드 검증(WFO) 비즈니스 로직을 제공합니다.
Expanding Anchored 및 Rolling Window 모드를 지원한다.

주요 함수:

- `generate_wfo_windows`: 월 기반 Expanding Anchored 또는 Rolling 윈도우 생성 (`rolling_is_months` 파라미터로 모드 전환)
- `select_best_calmar_params`: Calmar(CAGR/|MDD|) 기준 최적 파라미터 선택 (MDD=0 + CAGR>0 최우선 처리, min_trades 필터링 적용)
- `run_walkforward`: 핵심 WFO 루프 (IS 그리드 서치 → Calmar 최적 → OOS 독립 평가, wfe_calmar + wfe_cagr 계산)
- `build_params_schedule`: WFO 결과에서 params_schedule 구성
- `load_wfo_results_from_csv`: WFO 결과 CSV를 읽어 WfoWindowResultDict 리스트로 반환 (필수 컬럼 검증, 정수 타입 보정)
- `calculate_wfo_mode_summary`: OOS 성과 통계 + WFE(calmar/cagr/robust) + gap_calmar + Profit Concentration + 파라미터 안정성 진단
- `_calculate_profit_concentration`: Profit Concentration V2 방식 (end - prev_end) 계산
- `run_stitched_equity`: WFO params_schedule 기반 Stitched Equity 생성. 전체 signal_df에 먼저 MA를 계산하여 연속성 보장 후 OOS 구간 슬라이싱. window_end_equities 반환 (Profit Concentration 계산용)
- `run_window_detail_backtests`: 각 윈도우의 best params로 IS_start~OOS_end 백테스트 실행. equity_df에 밴드/드로우다운 포함. `WindowDetailData` 리스트 반환
- `WindowDetailData`: 윈도우별 상세 백테스트 결과 dataclass (window_idx, signal_df, equity_df, trades_df, ma_col)

### 6. portfolio_types.py

포트폴리오 백테스트에서 사용하는 데이터클래스를 정의한다.

설정 데이터클래스 (frozen=True):

- `AssetSlotConfig`: 자산 슬롯 설정 (asset_id, signal_data_path, trade_data_path, target_weight, strategy_id)
  - `strategy_id="buffer_zone"` (기본값): 버퍼존 신호에 따라 매수/매도. `STRATEGY_REGISTRY` 키와 일치해야 함.
  - `strategy_id="buy_and_hold"`: 즉시 매수 후 매도 신호 무시 (G 시리즈 GLD·TLT 처리에 사용)
  - 유효하지 않은 strategy_id는 엔진이 registry 조회 후 ValueError로 처리
  - 슬롯별 전략 파라미터 (buffer_zone에서 사용, buy_and_hold는 무시): `ma_window=200`, `buy_buffer_zone_pct=0.03`, `sell_buffer_zone_pct=0.05`, `hold_days=3`
- `PortfolioConfig`: 포트폴리오 실험 설정 (experiment_name, display_name, asset_slots, total_capital, result_dir)
  - 전략 파라미터(ma_window, buy/sell_buffer_zone_pct, hold_days)는 슬롯 레벨(AssetSlotConfig)로 이동.
  - 리밸런싱 정책은 엔진 레벨의 `DEFAULT_REBALANCE_POLICY`(RebalancePolicy 인스턴스)로 고정되며 PortfolioConfig에서 제거됨.

결과 데이터클래스:

- `PortfolioAssetResult`: 자산별 결과 (asset_id, trades_df, signal_df)
- `PortfolioResult`: 포트폴리오 전체 결과 (equity_df, trades_df, summary, config(필수), per_asset, params_json, state_log_df)

equity_df 컬럼: Date, equity, cash, drawdown_pct, rebalanced, rebalance_reason, {asset_id}\_value, {asset_id}\_weight, {asset_id}\_signal, {asset_id}\_shares, {asset_id}\_avg_price, {asset_id}\_realized_pnl, {asset_id}\_unrealized_pnl, {asset_id}\_current_price, {asset_id}\_return_pct, total_pnl, total_return_pct

파생 뷰 컬럼 (보유 현황·기여도 표시 용도, `build_combined_equity`에서 SSoT로 계산):

- `{asset_id}_current_price`: shares > 0이면 `value / shares`, 아니면 0.0
- `{asset_id}_return_pct`: shares > 0 and avg_price > 0이면 `(current_price / avg_price - 1) * 100`, 아니면 0.0
- `{asset_id}_contribution`: `realized_pnl + unrealized_pnl` (자산별 누적 기여 손익)
- `total_pnl`: `equity - initial_capital`
- `total_return_pct`: `total_pnl / initial_capital * 100`

대시보드 등 CLI 계층은 위 파생 컬럼을 직접 읽어 사용하며, 동일한 계산을 자체 수행하지 않는다.

state_log_df 컬럼 (매 거래일 1행, 디버깅/검증용): Date, equity, cash, is_month_start, rebalanced, rebalance_reason, {aid}\_close, {aid}\_shares, {aid}\_weight, {aid}\_signal_today, {aid}\_pending_intent, {aid}\_pending_reason, {aid}\_pending_delta, {aid}\_executed_intent, {aid}\_exec_side, {aid}\_exec_shares, {aid}\_exec_price

### 6-1. portfolio_validation.py

PortfolioResult에 대한 5개 정합성 규칙 검증을 제공한다. `run_portfolio_backtest.py`에서 각 실험 실행 직후 호출되어 위반 시 WARNING 로그를 남긴다.

주요 함수:

- `validate_portfolio_result(result) -> list[str]`: 5개 규칙 검증, 위반 메시지 리스트 반환

검증 규칙: 시그널-체결 1일 lag, 리밸런싱 비중 정합성, EXIT_ALL 주수 0, 현금 비음수, 에쿼티 등식

### 7. engines/ 패키지

백테스트 엔진을 엔진 공통 로직 / 단일 백테스트 엔진 / 포트폴리오 엔진으로 분리한 패키지입니다.
`SignalStrategy` Protocol을 통해 전략을 의존성 주입 방식으로 사용하므로, 새 전략 추가 시 엔진 파일 수정이 불필요합니다.

포트폴리오 엔진은 책임 단위로 4개 모듈로 분리되어 있다:

- `portfolio_planning.py`: 주문 의도(OrderIntent), 시그널/투영/병합 함수
- `portfolio_rebalance.py`: 리밸런싱 정책(RebalancePolicy), 월 첫 거래일 판정 함수
- `portfolio_execution.py`: 체결 결과(ExecutionResult), SELL→BUY 순 체결 함수
- `portfolio_data.py`: 데이터 로딩/검증, 에쿼티 DataFrame 빌드 함수
- `portfolio_engine.py`: facade (공개 API 2개 + 내부 헬퍼: `_load_portfolio_data_with_common_period`, `compute_portfolio_effective_start_date`, `run_portfolio_backtest`)

#### engines/engine_common.py

체결 계산 및 에쿼티 기록 등 두 엔진이 공유하는 공통 로직을 제공합니다.

데이터 구조:

- `PendingOrder`: 예약 주문 (order_type, signal_date). 신호일과 체결일 분리
- `TradeRecord`: 거래 기록 TypedDict. buy_buffer_pct, hold_days_used 포함 (CSV 호환)
- `PortfolioTradeRecord(TradeRecord)`: 포트폴리오 전용 거래 기록. TradeRecord를 확장하여 asset_id, trade_type, pre_shares, post_shares, order_amount 필드 추가
- `EquityRecord`: equity 기록 TypedDict. Date, equity, position만 포함

공통 함수 (순수 계산 함수 — 상태 변경 없음):

- `execute_buy_order(open_price, amount) -> (shares, buy_price, cost)`: 매수 체결 계산. 단일 엔진은 전체 자본을, 포트폴리오 엔진은 delta_amount를 amount로 전달
- `execute_sell_order(open_price, shares_to_sell, entry_price) -> (sell_price, proceeds, pnl, pnl_pct)`: 매도 체결 계산. 단일 엔진은 전량 매도, 포트폴리오 엔진은 부분 매도도 지원
- `create_trade_record(entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct, buy_buffer_pct=0.0, hold_days_used=0) -> TradeRecord`: TradeRecord 생성 헬퍼
- `record_equity(current_date, capital, position, close_price) -> EquityRecord`

#### engines/backtest_engine.py

단일 자산 버퍼존 전략 백테스트 및 그리드 서치를 제공합니다.

TypedDict:

- `GridSearchResult`: 그리드 서치 결과 딕셔너리

주요 함수:

- `filter_valid_rows(signal_df, trade_df, ma_col) -> tuple[pd.DataFrame, pd.DataFrame]`: MA 컬럼 기준 유효 행(NaN 아닌 행) 필터링
- `run_backtest(strategy, signal_df, trade_df, initial_capital, log_trades, strategy_name, params_schedule) -> tuple[trades_df, equity_df, summary]`: SignalStrategy 의존성 주입 방식 실행. `initial_capital: float`를 직접 전달한다.
- `run_grid_search(signal_df, trade_df, ...) -> pd.DataFrame`: 파라미터 그리드 탐색 (병렬 처리, WORKER_CACHE 패턴)
- `run_buffer_strategy(signal_df, trade_df, params, ...) -> ...`: `BufferZoneStrategy` + `run_backtest` 편의 래퍼
- `_run_backtest_for_grid(params)`: 그리드 서치용 module-level 병렬 헬퍼 (pickle 가능)
- `_check_pending_conflict(pending_order, signal_type, signal_date)`: Pending Order 충돌 감지 (Critical Invariant 강제)

#### engines/portfolio_engine.py

포트폴리오 백테스트 엔진을 제공한다.
복수 자산의 독립 시그널 + 목표 비중 배분 + 이중 트리거 리밸런싱을 처리한다.

데이터클래스 (각 하위 모듈에 정의, portfolio_engine.py가 import하여 사용):

- `OrderIntent` (portfolio_planning.py): 자산별 주문 의도 모델 (asset_id, intent_type, current_amount, target_amount, delta_amount, target_weight, reason, hold_days_used)
  - intent_type: `EXIT_ALL` (signal sell 전량 청산) / `ENTER_TO_TARGET` (signal buy 신규 진입) / `REDUCE_TO_TARGET` (rebalance 초과분 매도) / `INCREASE_TO_TARGET` (rebalance 미달분 매수)
- `ProjectedPortfolio` (portfolio_planning.py): signal intents 반영 후 예상 포트폴리오 상태 (projected_amounts, projected_cash, active_assets)
  - EXIT_ALL 자산은 projected_amounts=0, active_assets에서 제거, projected_cash 증가
  - ENTER_TO_TARGET 자산은 active_assets에 추가 (position=0이므로 amount=0 유지)
- `AssetState` (portfolio_types.py): 자산별 런타임 상태 (position, signal_state)
- `ExecutionResult` (portfolio_execution.py): `execute_orders()` 반환값 (updated_cash, updated_positions, updated_entry_prices, updated_entry_dates, updated_entry_hold_days, new_trades, rebalanced_today)
- `RebalancePolicy` (portfolio_rebalance.py): 이중 트리거 리밸런싱 정책 (frozen=True)
  - `monthly_threshold_rate`: 월 첫 거래일 임계값 (기본 0.10 = 10%)
  - `daily_threshold_rate`: 매일 긴급 임계값 (기본 0.20 = 20%)
  - `get_threshold(is_month_start) -> float`: 해당 거래일 기준 임계값 반환
  - `should_rebalance(projected, slot_dict, total_equity_projected, is_month_start) -> bool`: 임계값 초과 여부 판정
  - `build_rebalance_intents(projected, slot_dict, total_equity_projected, current_date) -> dict[str, OrderIntent]`: 리밸런싱 intent 생성 (threshold 체크 없이 항상 생성)
- `DEFAULT_REBALANCE_POLICY` (portfolio_rebalance.py): 기본 RebalancePolicy 인스턴스 (monthly=0.10, daily=0.20). `run_portfolio_backtest`에서 사용

주문 흐름 함수 (portfolio_planning.py / portfolio_execution.py):

- `generate_signal_intents(asset_states, strategies, asset_signal_dfs, equity_vals, slot_dict, current_equity, i, current_date) -> dict[str, OrderIntent]`: 전략 시그널 기반 intent 생성 (buy→ENTER_TO_TARGET, sell→EXIT_ALL, hold→없음)
- `compute_projected_portfolio(asset_states, signal_intents, equity_vals, shared_cash) -> ProjectedPortfolio`: signal intents 반영 후 예상 포트폴리오 상태 계산
- `merge_intents(signal_intents, rebalance_intents) -> dict[str, OrderIntent]`: signal/rebalance intent 통합, 자산당 1개 보장 (우선순위: EXIT_ALL > ENTER+INCREASE → ENTER > 단독 통과)
- `execute_orders(order_intents, open_prices, current_positions, current_cash, entry_prices, entry_dates, entry_hold_days, current_date) -> ExecutionResult`: SELL → BUY 순 체결. SELL 확보 현금을 BUY에 활용하며, BUY 총 비용이 available_cash를 초과하면 `raw_shares × scale_factor`로 비례 축소하여 음수 현금을 방지한다. order_intents에 있는 자산이 `open_prices`에 누락되면 `RuntimeError("내부 불변조건 위반")` 발생 — 호출부가 동일 자산 집합으로 채워야 한다는 호출 계약을 강제한다

공개 함수 (portfolio_engine.py facade + 하위 모듈):

- `compute_portfolio_effective_start_date(config: PortfolioConfig) -> date`: 포트폴리오 실험의 유효 시작일 계산 (전 자산 교집합 + MA 워밍업 후 첫 날짜). 각 실험이 자기 자산 조합 기준으로 독립 시작일을 산출하므로 CLI 러너에서 실험마다 호출하여 `run_portfolio_backtest`에 전달한다.
- `run_portfolio_backtest(config: PortfolioConfig, start_date: date | None = None) -> PortfolioResult`: 포트폴리오 백테스트 실행. `start_date` 파라미터로 MA 워밍업 이후 추가 시작일 하한을 지정할 수 있다 (CLI 러너에서 실험별 `compute_portfolio_effective_start_date` 결과를 전달).
- `is_first_trading_day_of_month(trade_dates, i) -> bool` (portfolio_rebalance.py): 월 첫 거래일 판정
- `compute_portfolio_equity(shared_cash, asset_positions, asset_closes) -> float` (portfolio_planning.py): 에쿼티 산식 계산
- `create_strategy_for_slot(slot: AssetSlotConfig) -> SignalStrategy` (portfolio_planning.py): STRATEGY_REGISTRY 경유 팩토리 (미등록 strategy_id → ValueError)

설계 특징:

- 주문 모델: OrderIntent 기반 (EXIT_ALL / ENTER_TO_TARGET / REDUCE_TO_TARGET / INCREASE_TO_TARGET)
- 흐름: Signal → ProjectedPortfolio → Rebalance → MergeIntents → Execution (next_day_intents)
- TQQQ/QQQ 시그널 공유: signal_data_path가 동일하면 자동으로 같은 시그널 발생
- 현금 버퍼: target_weight 합 < 1.0이면 잔여분 자동으로 현금 유지 (B시리즈)
- 이중 트리거 리밸런싱: `DEFAULT_REBALANCE_POLICY` (RebalancePolicy) — 월 첫날 10% / 매일 20% 긴급 트리거
- 주문 충돌 해소: merge_intents 우선순위 규칙으로 자산당 1개 보장 (충돌 예외 없음)
- projected state: signal intent 반영 후 리밸런싱 계획 수립 → planning 왜곡 방지
- 부분 매도: REDUCE_TO_TARGET은 delta_amount 기준 수량, EXIT_ALL은 전량
- SignalStrategy 팩토리: STRATEGY_REGISTRY 경유, strategy_id 문자열 분기 없음

### 8. portfolio_configs.py

포트폴리오 백테스트 실험 설정을 제공한다.

설정 목록:

- `PORTFOLIO_CONFIGS: list[PortfolioConfig]`
  - 실험 구성과 자산 비중은 변경 빈도가 매우 높으므로 본 문서에 직접 나열하지 않는다.
  - 최신 실험 목록·자산 슬롯·target_weight·strategy_id는 `src/qbt/backtest/portfolio_configs.py`를 직접 확인할 것.

주요 함수:

- `get_portfolio_config(experiment_name)`: 이름으로 PortfolioConfig 조회. 없으면 ValueError

---

### 9. strategy_registry.py

전략 확장 가능 구조를 제공한다.
`StrategySpec` 데이터클래스와 `STRATEGY_REGISTRY` 딕셔너리를 통해
포트폴리오 엔진이 `strategy_id` 문자열로 전략 동작을 조회한다.

데이터클래스:

- `StrategySpec` (frozen=True): 전략 명세
  - `strategy_id`: 전략 식별자 (STRATEGY_REGISTRY의 키)
  - `create_strategy(slot) -> SignalStrategy`: 전략 객체 생성 팩토리
  - `prepare_signal_df(df, slot) -> pd.DataFrame`: signal DataFrame 전처리 (buffer_zone → MA 컬럼 추가, buy_and_hold → 원본 반환)
  - `get_warmup_periods(slot) -> int`: MA 워밍업 기간 (buffer_zone → `slot.ma_window`, buy_and_hold → `0`)

등록된 전략:

- `STRATEGY_REGISTRY: dict[str, StrategySpec]`
  - `"buffer_zone"`: BufferZoneStrategy 생성 + MA 컬럼 추가 + ma_window 워밍업
  - `"buy_and_hold"`: BuyAndHoldStrategy 생성 + 원본 반환 + 워밍업 0

### 10. strategies/ 패키지

전략 관련 모듈을 담은 패키지입니다.
전략 클래스(`SignalStrategy` Protocol 구현체)와 config-driven 팩토리 패턴을 제공합니다.

#### strategies/strategy_common.py

두 엔진이 공유하는 전략 공통 인터페이스와 신호 감지 함수를 제공합니다.

Protocol:

- `SignalStrategy`: 전략 공통 인터페이스
  - `check_buy(signal_df, i, current_date) -> bool`: i번째 날 매수 신호 여부. 내부 prev 상태 갱신 포함.
  - `check_sell(signal_df, i) -> bool`: i번째 날 매도 신호 여부. 내부 prev 상태 갱신 포함.
  - `get_buy_meta() -> dict[str, float | int]`: check_buy True 직후 호출. TradeRecord용 메타데이터 반환.

예외 클래스:

- `PendingOrderConflictError`: Pending Order 충돌 예외 (Critical Invariant 위반)

신호 감지 함수 (strategy_common.py에서 제거됨): `compute_bands`, `detect_buy_signal`, `detect_sell_signal`는 `buffer_zone_helpers.py`로 이동.

#### strategies/buffer_zone_helpers.py

버퍼존 전략 전용 신호 감지 함수와 HoldState TypedDict를 제공합니다.
(strategy_common.py에서 이동됨)

TypedDict:

- `HoldState`: hold_days 상태머신 상태 (start_date, days_passed, buffer_pct, hold_days_required)

신호 감지 함수:

- `compute_bands(ma_value, buy_buffer_pct, sell_buffer_pct) -> tuple[float, float]`: upper_band, lower_band 계산
- `detect_buy_signal(prev_close, close, prev_upper, upper) -> bool`: 상향돌파 감지
- `detect_sell_signal(prev_close, close, prev_lower, lower) -> bool`: 하향돌파 감지

#### strategies/buffer_zone.py

버퍼존 통합 config-driven 전략 모듈 (4P 고정). 단일 전략 클래스로 전 자산의 버퍼존 전략을 처리한다.

설정 데이터클래스:

- `BufferZoneConfig`: 자산별 전략 설정 (strategy*name, display_name, signal_data_path, trade_data_path, result_dir + 기본값 있는 필드: ma_window, buy_buffer_zone_pct, sell_buffer_zone_pct, hold_days). frozen=True. 기본값은 `constants.py`의 `FIXED_4P*\*` 참조

설정 목록:

- `CONFIGS`: `list[BufferZoneConfig]` (전 자산 4P 고정). 새 자산 추가 시 여기에 한 줄 추가. config당 필수 필드(strategy_name, display_name, 경로)만 명시, 나머지는 기본값 활용
  - 자산 라인업은 변경 빈도가 높으므로 본 문서에 직접 나열하지 않는다. 최신 자산 목록·시그널/매매 데이터 경로·표시명은 [src/qbt/backtest/strategies/buffer_zone.py](strategies/buffer_zone.py)의 `CONFIGS`를 직접 확인할 것.

전략 클래스:

- `BufferZoneStrategy`: `SignalStrategy` Protocol 구현체 (stateful)
  - 생성자: `(ma_col, buy_buffer_pct, sell_buffer_pct, hold_days)`
  - 내부 상태: `_prev_upper`, `_prev_lower`, `_hold_state`, `_last_buy_buffer_pct`, `_last_hold_days_used`
  - `_update_bands(signal_df, i) -> tuple | None`: 밴드 계산 + prev 상태 갱신. check_buy/check_sell 공용. 초기화 시 None 반환
  - `check_buy(signal_df, i, current_date) -> bool`: `_update_bands` 호출 후 hold_state 상태머신 처리
  - `check_sell(signal_df, i) -> bool`: `_update_bands` 호출 후 하향돌파 감지
  - `get_buy_meta() -> dict`: `{"buy_buffer_pct": ..., "hold_days_used": ...}`

파라미터 결정 함수:

- `resolve_buffer_params(ma_window, buy_buffer_zone_pct, sell_buffer_zone_pct, hold_days) -> BufferStrategyParams`: 파라미터 검증 후 BufferStrategyParams 생성
- `resolve_params_for_config(config) -> BufferStrategyParams`: config의 파라미터를 resolve_buffer_params()에 전달

주요 함수:

- `get_config(strategy_name)`: 이름으로 BufferZoneConfig 조회. 존재하지 않으면 ValueError

#### strategies/buy_and_hold.py

Buy & Hold 벤치마크 전략 구현입니다. 팩토리 패턴으로 멀티 티커를 지원한다.

설정 데이터클래스:

- `BuyAndHoldConfig`: 티커별 전략 설정 (strategy_name, display_name, trade_data_path, result_dir)

티커별 설정 목록:

- `CONFIGS`: `list[BuyAndHoldConfig]`. 새 티커 추가 시 여기에 한 줄 추가
  - 자산 라인업은 변경 빈도가 높으므로 본 문서에 직접 나열하지 않는다. 최신 티커 목록은 [src/qbt/backtest/strategies/buy_and_hold.py](strategies/buy_and_hold.py)의 `CONFIGS`를 직접 확인할 것.

전략 클래스:

- `BuyAndHoldStrategy`: `SignalStrategy` Protocol 구현체 (stateless)
  - 파라미터 없는 생성자
  - `check_buy(signal_df, i, current_date) -> bool`: 항상 `True` 반환 (즉시 매수)
  - `check_sell(signal_df, i) -> bool`: 항상 `False` 반환 (매도 없음)
  - `get_buy_meta() -> dict`: `{}` 반환

#### strategies/**init**.py

전략 패키지의 공개 API를 export합니다.
`buffer_zone.py`의 `get_config()`, `create_runner()`는 패키지 레벨에서 re-export하지 않으며, 스크립트에서 `buffer_zone` 모듈을 직접 import하여 사용한다.

엔진 함수(`run_buffer_strategy`, `run_grid_search`)는 `engines/backtest_engine.py`에 속하므로 이 패키지에서 re-export하지 않는다 (순환 import 방지).

export 심볼: `BufferZoneConfig`, `resolve_params_for_config`, `BufferStrategyParams`, `PendingOrderConflictError`, `BuyAndHoldConfig`

PendingOrder는 계층 분리 원칙에 따라 `engines.engine_common`에서 직접 import한다 (re-export 하지 않음).

### 11. runners.py

전략 설정(Config)을 받아 실행 가능한 Callable을 반환하는 팩토리 함수를 제공합니다.
`buffer_zone.py`와 `backtest_engine.py` 사이의 순환 의존성을 해소하기 위해 분리된 모듈입니다.

역할 분리:

- `buffer_zone.py` / `buy_and_hold.py`: 전략 클래스 + 설정 데이터클래스 + CONFIGS 목록
- `runners.py`: 데이터 로딩 + MA 계산 + 전략 실행 로직 (팩토리)

순환 의존성 해결:

- `runners.py`가 `buffer_zone.py`와 `backtest_engine.py`를 모두 top-level로 import하여 순환 없이 팩토리 역할을 수행한다.

주요 함수:

- `create_buffer_zone_runner(config: BufferZoneConfig) -> Callable[[], SingleBacktestResult]`: 버퍼존 전략 runner 팩토리. 데이터 로딩, overlap 처리, MA 계산, `run_backtest(BufferZoneStrategy(), ...)` 수행. equity_df에 band 컬럼 post-processing으로 보강 (`_enrich_equity_with_bands`).
- `create_buy_and_hold_runner(config: BuyAndHoldConfig) -> Callable[[], SingleBacktestResult]`: B&H 전략 runner 팩토리. `run_backtest(BuyAndHoldStrategy(), ...)` 기반으로 실행. dummy params 불필요. B&H 첫 매수는 시계열 2번째 날 시가.
- `_enrich_equity_with_bands(equity_df, signal_df, ma_col, buy_pct, sell_pct) -> pd.DataFrame`: signal_df의 MA 값으로 upper_band, lower_band, buy_buffer_pct, sell_buffer_pct 컬럼을 equity_df에 추가.

### 12. csv_export.py

백테스트 CSV 저장용 DataFrame 변환 유틸리티를 제공한다.
CLI 스크립트에서 반복되는 trades CSV 준비, OHLC 전일대비% 계산, buffer_zone 밴드
컬럼 추가 패턴을 공용 함수로 제공한다. 대시보드(`scripts/backtest/app_*.py`)가
도메인 연산을 직접 수행하지 않도록, signal CSV 저장 단계의 SSoT 역할을 한다.
CSV 저장(to_csv) 자체는 호출부에서 수행한다.

의존 방향 (고정): `analysis.py` → `csv_export.py` 단방향. `csv_export.py`는 `analysis.py`를 import하지 않는다. 회귀 방지 테스트로 고정되어 있으며, 역방향 의존이 발생하면 순환 import 위험이 있으므로 절대 금지한다.

주요 함수:

- `add_holding_days(df) -> pd.DataFrame`: trades DataFrame에 `holding_days` 컬럼 추가 (entry_date/exit_date 기반 일수 계산). `prepare_trades_for_csv`가 사용
- `prepare_trades_for_csv(trades_df) -> pd.DataFrame`: trades DataFrame 변환 (holding_days 추가, 반올림, 정수 변환). 빈 DataFrame 입력 시 빈 복사본 반환
- `add_ohlc_change_pct(df) -> pd.DataFrame`: signal DataFrame에 OHLC 4종 전일대비% 컬럼(`open_pct`/`high_pct`/`low_pct`/`close_pct`) 추가. 첫 행은 NaN. 대시보드 캔들 tooltip의 SSoT
- `add_buffer_zone_bands(df, ma_col, buy_buffer_zone_pct, sell_buffer_zone_pct) -> pd.DataFrame`: signal DataFrame에 `upper_band`/`lower_band` 컬럼 추가. 산식: `ma * (1 ± buffer)`. buffer_zone 전략 자산의 시그널 CSV에만 적용

상수:

- `OHLC_CHANGE_PCT_COLUMNS`: 4종 % 컬럼명 튜플 (`open_pct`, `high_pct`, `low_pct`, `close_pct`)
- `BUFFER_BAND_COLUMNS`: 밴드 컬럼명 튜플 (`upper_band`, `lower_band`)

---

## 도메인 규칙

### 1. 전략 파라미터

- 이동평균 기간 (`ma_window`): 추세 판단의 기준 기간, 1 이상
- 매수 버퍼존 (`buy_buffer_zone_pct`): upper_band 기준 매수 진입 허용 범위 (비율, 0~1)
- 매도 버퍼존 (`sell_buffer_zone_pct`): lower_band 기준 매도 청산 허용 범위 (비율, 0~1)
- 유지 조건 (`hold_days`): 신호 확정까지 대기 기간 (일), 0 = 버퍼존만 모드

> 이동평균 유형은 파라미터가 아니다. **SMA 로 고정**되어 있다 (아래 규칙 참고).

### 1-1. 이동평균은 SMA 하나뿐이다 (절대 규칙)

`add_single_moving_average` 는 **유형을 고르는 파라미터를 갖지 않으며**, 항상 단순이동평균을 계산한다.
EMA 계산 경로와 `ma_type` 파라미터·상수·필드는 코드베이스에서 제거되었다.
`tests/qbt/test_ma_type_policy.py` 가 시그니처에 `ma_type` 이 없음을 검증하여 재도입을 막는다.

채택 근거 (상세는 `docs/research/전략_검증_보고서.md` 부록 G):

1. **대중성** — "200일 이동평균" 의 경제적 논거는 자기실현적 예언(많은 참여자가 같은 선을 본다)에 기반한다.
   더 널리 쓰이는 SMA 가 그 논거에 더 부합한다.
2. **과최적화 자유도 축소** — 검증 보고서가 "EMA vs SMA 선택" 을 실질 시행 횟수 `+2` 로 카운트한다.
   대중적 기본값으로 고정하면 자유도가 줄어든다.
3. **연속성 함정 제거** — EMA 는 재귀식이라 구간을 슬라이스하면 워밍업이 리셋된다.
   SMA 는 `ma_window` 개 행만 확보되면 그 이전 데이터가 결과에 영향을 주지 않으므로 이 계열의 버그가 성립하지 않는다.
4. **워밍업 미완료 구간의 가짜 신호 제거** — EMA 는 1행째부터 값이 나오지만 그 값은 이동평균이 아니라
   사실상 그날 종가다. 밴드가 가격에 밀착해 "추세 돌파" 가 아닌 신호가 발생한다.
   SMA 는 `ma_window` 미만 구간을 NaN 으로 두어 `filter_valid_rows` 가 자동 제외한다.

**부작용**: SMA 는 앞 `ma_window - 1` 행이 NaN 이므로 백테스트 유효 시작일이 EMA 시절보다 뒤로 밀린다.
전환 이전(EMA 기준) 결과와 비교할 때는 **반드시 공통 기간으로 잘라 재계산**한다.
짧은 합성 데이터로 테스트를 만들 때도 `ma_window` 를 데이터 길이에 맞춰 지정해야 워밍업 구간에 갇히지 않는다.

### 2. 비용 모델

- 매수: `price_raw * (1 + SLIPPAGE_RATE)`
- 매도: `price_raw * (1 - SLIPPAGE_RATE)`
- 왕복(매수+매도) 비용은 `2 × SLIPPAGE_RATE` ≈ 0.6%로, 매수와 매도가 각각 별도의 비용 이벤트로 누적된다. 이는 의도된 설계이며 슬리피지 이중 적용이 아니다.

### 3. 체결 타이밍 규칙 (절대 규칙)

신호 발생과 체결 실행의 분리:

- 신호 발생: i일 종가 기준으로 상단/하단 밴드 돌파 감지
- 체결 실행: i+1일 시가에 실제 매수/매도 (hold_days=0 기준)

### 4. Equity 및 Final Capital 정의 (절대 규칙)

- Equity: `equity = cash + position_shares * close`
- Final Capital: 마지막 날 equity와 동일, 강제청산 없음

### 5. Pending Order 정책 (절대 규칙)

단일 슬롯 원칙:

- `pending_order`는 반드시 단일 변수로 관리 (리스트 누적 금지)
- 신호일에 생성, 체결일에 실행 후 `None`으로 초기화

Critical Invariant:

- `pending_order`가 존재하는 동안 새로운 신호 발생 시 `PendingOrderConflictError` 예외

### 6. hold_days 규칙 (Lookahead 방지, 절대 규칙)

일반화 (hold_days = H):

- 돌파일: i
- 유지조건 체크: i+1 ~ i+H일 종가
- 신호 확정일: i+H일 종가
- 체결일: i+H+1일 시가

Lookahead 금지:

- 금지: i일에 i+1 ~ i+H를 미리 검사해 `pending`을 선적재하는 방식
- 필수: 매일 순차적으로 유지조건 체크 (상태머신 방식)

### 7. 마지막 날 규칙

- N-1일 종가에서 생성된 `pending`은 N일 시가에서 정상 체결
- N일 종가에서 발생한 신호는 N+1일 시가가 없으므로 무시
- 강제청산 없음: 마지막 날에 포지션이 남아있어도 강제 매도하지 않음
- 미청산 포지션 기록: 종료 시 포지션이 남아있으면 summary에 `open_position` (entry_date, entry_price, shares) 포함. 대시보드에서 `"Buy $XX.X (보유중)"` 마커로 표시된다

---

## 핵심 계산 로직

### 버퍼존 밴드 계산

```
upper_band = ma * (1 + buy_buffer_zone_pct)   # 매수 진입 기준
lower_band = ma * (1 - sell_buffer_zone_pct)   # 매도 청산 기준
```

### 성과 지표 계산

- 총 수익률: `(final_capital - initial_capital) / initial_capital * 100`
- CAGR: `((final_capital / initial_capital) ^ (ANNUAL_DAYS / 총일수)) - 1`
- MDD: 자본 곡선에서 최대 낙폭 계산
- Calmar: `CAGR / |MDD|` (|MDD| < EPSILON이면 CAGR > 0일 때 1e10 + CAGR, 아니면 0.0)
- 승률: `profitable_trades / total_trades * 100`

---

## CSV 파일 형식

---

## 대시보드 앱 아키텍처

### 동적 전략 탭 (`scripts/backtest/app_single_backtest.py`)

대시보드는 `BACKTEST_RESULTS_DIR` 하위 디렉토리를 자동 탐색하여 전략별 탭을 생성한다.
새로운 전략이 추가되면 결과 폴더만 있으면 앱 코드 수정 없이 자동으로 탭이 추가된다.

핵심 설계:

- **전략 자동 탐색**: `_discover_strategies()`가 하위 디렉토리의 `summary.json` 존재 여부로 유효한 전략 결과를 판별
- **Feature Detection**: 전략명 분기(`if strategy == "buffer_zone"`) 없이 데이터 존재 여부로 차트 오버레이 결정
  - `ma_*` 컬럼 존재 → MA 오버레이 추가
  - `upper_band`/`lower_band` 존재 → 밴드 오버레이 추가 (단일 백테스트는 equity_df, 포트폴리오는 signal_df의 컬럼을 본다 — buffer_zone 자산만 컬럼 존재)
  - `trades_df`가 비어있지 않음 → 완료된 거래 Buy/Sell 마커 추가
  - `summary.open_position` 존재 → 미청산 포지션 Buy 마커 추가 (`"Buy $XX.X (보유중)"`)
- **날짜 표기**: `localization.dateFormat: "yyyy-MM-dd"` 설정으로 한국식 날짜 형식 적용
- **customValues**: lightweight-charts v5 내장 기능. Python에서 `customValues` dict를 전달하여 JS `subscribeCrosshairMove` 콜백에서 tooltip으로 표시
  - OHLC 가격: `open`, `high`, `low`, `close`
  - 전일종가대비%: `open_pct`, `high_pct`, `low_pct`, `close_pct` — 모두 `run_*.py`가 사전 계산해 signal CSV에 저장한 컬럼을 직접 읽는다 (대시보드는 산식을 자체 수행하지 않는다)
  - 지표: `ma`, `upper`, `lower`
  - 포트폴리오: `equity`, `dd`
- **display_name 필수**: `summary.json`에 `display_name`이 없으면 `ValueError` 발생

### 포트폴리오 비교 대시보드 (`scripts/backtest/app_portfolio_backtest.py`)

설정에 정의된 포트폴리오 실험 결과를 비교하는 대시보드.

핵심 설계:

- **실험 자동 탐색**: `_discover_experiments()`가 `PORTFOLIO_RESULTS_DIR` 하위 summary.json 존재 여부로 유효 실험 판별
- **탭 구조**: "전체 비교" 탭 + 실험별 탭 (알파벳 순 자동 생성)
- **Plotly 전용**: lightweight-charts 없이 Plotly만 사용 (멀티 시리즈 라인 차트가 주목적)
- **에쿼티 비교**: 초기 자본이 동일(10,000,000원)이므로 정규화 없이 절대값 비교
- **전체 비교 탭 주요 기능**: 성과 지표 테이블, 에쿼티 곡선 비교 (멀티 셀렉트), 드로우다운 비교, 실험 해설(행동 가이드)
- **실험별 탭 주요 기능**: 요약 지표(Sharpe/Sortino 포함), 에쿼티+드로우다운 서브플롯, 자산별 비중 추이(스택 에어리어), 거래 현황 바차트, 거래 내역 테이블(자산 필터), 시그널 차트(Plotly 캔들스틱, 자산 선택), 파라미터 expander, 월별 수익률 히트맵, 연간 수익률 vs QQQ 바차트, 자산별 수익 기여도
- **미청산 포지션 Buy 마커**: summary.json의 `per_asset[*].open_position`(= `{entry_date, entry_price, shares}`) 존재 시 시그널 차트에 `"Buy $XX.X (보유중)"` 마커를 표시. 단일 백테스트 대시보드(`summary.open_position`)와 동일 규약이며, 포트폴리오에서는 자산별 키(`per_asset`)에 담긴다. `run_portfolio_backtest.py`가 equity.csv의 `{asset_id}_shares` 변화(0→양수 마지막 전환)에서 `entry_date`를 파생하여 저장한다.

선행 조건: `run_portfolio_backtest.py`를 먼저 실행하여 `storage/results/portfolio/` 데이터 생성 필요

### Vendor Fork (`vendor/streamlit-lightweight-charts-v5/`)

- `streamlit-lightweight-charts-v5` 포크를 `vendor/` 디렉토리에 포함
- TSX 소스에 `subscribeCrosshairMove` 기반 커스텀 tooltip 추가
- cleanup 함수에 `unsubscribeCrosshairMove` + tooltip DOM 제거 포함
- `pyproject.toml`에서 editable 모드로 참조: `{path = "vendor/streamlit-lightweight-charts-v5", develop = true}`
- `develop = true`로 Poetry가 editable 설치 → `__file__`이 vendor 디렉토리를 직접 가리킴
- 팀원은 `poetry install`만 실행하면 됨 (Node.js 불필요, 빌드 결과물 포함)
- TSX 수정 후 반영 절차 (2단계):
  ```bash
  # 1. 프론트엔드 빌드
  cd vendor/streamlit-lightweight-charts-v5/lightweight_charts_v5/frontend && npm run build
  # 2. Streamlit 앱 재시작 + 브라우저 하드 리프레시 (Ctrl+Shift+R)
  ```

---

## 테스트 커버리지

테스트 파일은 [tests/qbt/](../../../tests/qbt/) 디렉토리에 위치한다. 구체적인 파일 목록은 변경 빈도가 높으므로 본 문서에 나열하지 않으며, 디렉토리를 직접 참조할 것.

테스트 범위 (계약/불변조건 단위):

- 신호 생성 로직 및 거래 체결 타이밍
- Pending Order 충돌 감지
- 파라미터 유효성 검증
- 엣지 케이스 (빈 데이터, 극단값)
- 그리드 서치 병렬 처리
- resolve_params 파라미터 결정 (FIXED 고정값)
- run_single → SingleBacktestResult 구조 검증
- 워크포워드 윈도우 생성 / 파라미터 선택 / 요약 집계 / 일정 스케줄링
- 포트폴리오 엔진 (계획 / 체결 / 검증 / 전략 타입 / 상태 로그)
- 미청산 포지션 (open_position): 포지션 보유 시 포함 / 미보유 시 미포함 검증
