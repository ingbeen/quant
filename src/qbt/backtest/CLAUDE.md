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
- `SingleBacktestResult`: 각 전략의 `run_single()` 공통 반환 타입 (dataclass). strategy_name, display_name, signal_df, equity_df, trades_df, summary, params_json, result_dir, data_info 포함
- `WfoWindowResultDict`: WFO 윈도우별 IS/OOS 결과 (window_idx, is/oos 날짜, best params, is/oos 성과 지표, wfe_calmar, wfe_cagr)
- `WfoModeSummaryDict`: WFO 모드별 요약 (n_windows, oos 통계, wfe 통계, gap_calmar_median, profit_concentration, 파라미터별 리스트(param_ma_windows 등), stitched 지표)
- `MarketRegimeDict`: 시장 구간 정의 (start, end, regime_type, name). QQQ 기준 수동 분류한 구간 정보
- `RegimeSummaryDict`: 구간별 성과 요약 (name, regime_type, start_date, end_date, trading_days, 기본 지표 + avg_holding_days, profit_factor)

### 2. constants.py

백테스트 도메인 전용 상수를 정의합니다.

주요 상수 카테고리:

- 거래 비용: `SLIPPAGE_RATE` (0.3%, 슬리피지 + 수수료 통합)
- 기본 파라미터: `DEFAULT_INITIAL_CAPITAL`
- 제약 조건: `MIN_BUY_BUFFER_ZONE_PCT`, `MIN_SELL_BUFFER_ZONE_PCT`, `MIN_HOLD_DAYS`, `MIN_VALID_ROWS`, `DEFAULT_WFO_MIN_TRADES`
- WFO 파라미터 리스트: `DEFAULT_WFO_MA_WINDOW_LIST`, `DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST` 등 (그리드 서치 + 워크포워드 공용)
- WFO 윈도우 설정: `DEFAULT_WFO_INITIAL_IS_MONTHS`, `DEFAULT_WFO_OOS_MONTHS`
- WFO 결과 파일명: `WALKFORWARD_DYNAMIC_FILENAME` 등
- 시장 구간: `MARKET_REGIMES` (QQQ 기준 수동 분류, `list[MarketRegimeDict]`)
- 전략 필터링: `DEFAULT_SINGLE_BACKTEST_STRATEGIES` (단일 백테스트/대시보드에서 실행·표출할 전략 목록)

### 3. analysis.py

이동평균 계산 및 성과 지표 분석 함수를 제공합니다.

주요 함수:

- `add_single_moving_average`: 단일 이동평균(SMA/EMA) 계산
- `calculate_summary`: 거래 내역과 자본 곡선으로부터 성과 지표 계산
- `calculate_monthly_returns`: 에쿼티 데이터로부터 월별 수익률 계산
- `calculate_regime_summaries`: 시장 구간별 성과 요약 계산 (equity_df + trades_df를 구간별로 슬라이스하여 calculate_summary() 재사용 + 추가 지표(avg_holding_days, profit_factor) 계산). holding_days 컬럼 미존재 시 entry_date/exit_date로 자동 계산하는 폴백 지원. 결과는 `run_single_backtest.py`에서 호출하여 `summary.json`에 `regime_summaries` 키로 사전 저장됨

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

### 6. split_strategy.py

분할 매수매도 오케스트레이터 모듈을 제공합니다.
3개 트랜치(ma250/ma200/ma150)를 독립 실행 후 결과를 조합하는 오케스트레이터 패턴입니다.
기존 `run_buffer_strategy()`를 블랙박스로 호출하며, 기존 코드 무변경 원칙을 준수합니다.

데이터 클래스:

- `SplitTrancheConfig`: 트랜치별 설정 (tranche_id, weight, ma_window). frozen=True
- `SplitStrategyConfig`: 전략 설정 (strategy_name, display_name, base_config, total_capital, tranches, result_dir). frozen=True
- `SplitTrancheResult`: 트랜치별 백테스트 결과 (tranche_id, config, trades_df, equity_df, summary)
- `SplitStrategyResult`: 분할 매수매도 전체 결과 (combined_equity_df, combined_trades_df, combined_summary, per_tranche, config, params_json, signal_df)

설정 목록:

- `SPLIT_CONFIGS`: `list[SplitStrategyConfig]` (split_buffer_zone_tqqq, split_buffer_zone_qqq)

주요 함수:

- `run_split_backtest`: 분할 매수매도 백테스트 실행 (데이터 1회 로딩, 트랜치별 독립 실행, 결과 조합)
- `create_split_runner`: 팩토리 함수. `SplitStrategyConfig` → `Callable[[], SplitStrategyResult]` 생성

헬퍼 함수:

- `_combine_equity`: 트랜치별 에쿼티를 합산 (active_tranches, avg_entry_price 포함)
- `_combine_trades`: 트랜치별 거래를 합산 (tranche_id, tranche_seq, ma_window 태깅)
- `_calculate_combined_summary`: 합산 에쿼티로 calculate_summary() 호출
- `_build_params_json`: JSON 저장용 파라미터 딕셔너리 생성

설계 근거: `docs/tranche_architecture.md`, `docs/tranche_final_recommendation.md`

### 7. strategies/ 패키지

전략 실행 엔진을 전략별로 분리한 패키지입니다.

#### strategies/buffer_zone_helpers.py

버퍼존 계열 전략(buffer_zone_tqqq, buffer_zone_qqq)이 공유하는 핵심 로직, 타입, 예외, 상수를 제공합니다.

전략 전용 TypedDict:

- `BufferStrategyResultDict`: `run_buffer_strategy()` 반환 타입
- `EquityRecord`: equity 기록 딕셔너리
- `TradeRecord`: 거래 기록 딕셔너리
- `HoldState`: hold_days 상태머신 상태
- `GridSearchResult`: 그리드 서치 결과 딕셔너리

데이터 클래스:

- `BufferStrategyParams`: 버퍼존 전략 파라미터 (initial_capital, ma_window, buy/sell_buffer_zone_pct, hold_days)
- `PendingOrder`: 예약 주문 정보 (신호일과 체결일 분리)

예외 클래스:

- `PendingOrderConflictError`: Pending Order 충돌 예외 (Critical Invariant 위반)

헬퍼 함수:

- `_validate_buffer_strategy_inputs`, `_compute_bands`, `_check_pending_conflict`
- `_record_equity`, `_execute_buy_order`, `_execute_sell_order`
- `_detect_buy_signal`, `_detect_sell_signal`

파라미터 결정 함수:

- `resolve_buffer_params`: 전달받은 파라미터로 BufferStrategyParams를 생성한다. sources 딕셔너리는 "FIXED"로 통일.

핵심 함수:

- `run_buffer_strategy`: 버퍼존 전략 실행. `params_schedule` 파라미터로 구간별 파라미터 전환 지원. 종료 시 포지션 보유 중이면 summary에 `open_position` 포함
- `run_grid_search`: 파라미터 그리드 탐색 (병렬 처리)
- `_run_buffer_strategy_for_grid`: 그리드 서치용 병렬 실행 헬퍼

#### strategies/buffer_zone.py

버퍼존 통합 config-driven 전략 모듈 (4P 고정). 기존 buffer_zone_tqqq, buffer_zone_qqq를 통합한다.

설정 데이터클래스:

- `BufferZoneConfig`: 자산별 전략 설정 (strategy*name, display_name, signal_data_path, trade_data_path, result_dir + 기본값 있는 필드: ma_window, buy_buffer_zone_pct, sell_buffer_zone_pct, hold_days, ma_type). frozen=True. 기본값은 `constants.py`의 `FIXED_4P*\*` 참조

설정 목록:

- `CONFIGS`: `list[BufferZoneConfig]` (전 자산 4P 고정). 새 자산 추가 시 여기에 한 줄 추가. config당 필수 필드(strategy_name, display_name, 경로)만 명시, 나머지는 기본값 활용
  - buffer_zone_tqqq: QQQ 시그널 + TQQQ 합성 매매 (4P 고정, ma_type=ema)
  - buffer_zone_qqq: QQQ 시그널 + QQQ 매매 (4P 고정)
  - cross-asset 6개: buffer_zone_spy, buffer_zone_iwm, buffer_zone_efa, buffer_zone_eem, buffer_zone_gld, buffer_zone_tlt (4P 고정)

주요 함수:

- `get_config(strategy_name)`: 이름으로 BufferZoneConfig 조회. 존재하지 않으면 ValueError
- `resolve_params_for_config(config)`: config의 파라미터를 resolve_buffer_params()에 전달
- `create_runner(config)`: 팩토리 함수. `BufferZoneConfig` → `Callable[[], SingleBacktestResult]` 생성. 데이터 로딩, overlap 처리, MA 계산, 전략 실행을 자체 수행

#### strategies/buy_and_hold.py

Buy & Hold 벤치마크 전략 구현입니다. 팩토리 패턴으로 멀티 티커를 지원한다.

설정 데이터클래스:

- `BuyAndHoldConfig`: 티커별 전략 설정 (strategy_name, display_name, trade_data_path, result_dir)

티커별 설정 목록:

- `CONFIGS`: `list[BuyAndHoldConfig]`. 새 티커 추가 시 여기에 한 줄 추가
  - `buy_and_hold_qqq`: QQQ 데이터 (`QQQ_DATA_PATH`) 사용
  - `buy_and_hold_tqqq`: TQQQ 합성 데이터 (`TQQQ_SYNTHETIC_DATA_PATH`) 사용
  - cross-asset: buy_and_hold_spy, buy_and_hold_iwm, buy_and_hold_efa, buy_and_hold_eem, buy_and_hold_gld, buy_and_hold_tlt

파라미터 데이터클래스:

- `BuyAndHoldParams`: Buy & Hold 전략 파라미터 (initial_capital)

주요 함수:

- `run_buy_and_hold`: 매수 후 보유 벤치마크 전략 실행 (`trade_df`만 받음, `signal_df` 미사용) → `tuple[pd.DataFrame, SummaryDict]` 반환 (equity_df, summary). 항상 포지션을 보유하므로 summary에 `open_position` 포함 (shares > 0인 경우)
- `resolve_params`: 파라미터 결정 (항상 DEFAULT_INITIAL_CAPITAL 사용)
- `create_runner`: 팩토리 함수. `BuyAndHoldConfig` → `Callable[[], SingleBacktestResult]` 생성

#### strategies/**init**.py

전략 패키지의 공개 API를 export합니다.
`buffer_zone.py`의 `get_config()`, `create_runner()`는 패키지 레벨에서 re-export하지 않으며, 스크립트에서 `buffer_zone` 모듈을 직접 import하여 사용한다.

설계 결정 사항:

- 버퍼존 계열 전략은 `buffer_zone.py` 통합 모듈의 config-driven 팩토리 패턴으로 관리.
- 공통 로직은 `buffer_zone_helpers.py`에 추출하여 코드 중복을 방지.

---

## 도메인 규칙

### 1. 전략 파라미터

- 이동평균 기간 (`ma_window`): 추세 판단의 기준 기간, 1 이상
- 매수 버퍼존 (`buy_buffer_zone_pct`): upper_band 기준 매수 진입 허용 범위 (비율, 0~1)
- 매도 버퍼존 (`sell_buffer_zone_pct`): lower_band 기준 매도 청산 허용 범위 (비율, 0~1)
- 유지 조건 (`hold_days`): 신호 확정까지 대기 기간 (일), 0 = 버퍼존만 모드

### 2. 비용 모델

- 매수: `price_raw * (1 + SLIPPAGE_RATE)`
- 매도: `price_raw * (1 - SLIPPAGE_RATE)`

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
  - `upper_band`/`lower_band` 존재 → 밴드 오버레이 추가
  - `trades_df`가 비어있지 않음 → 완료된 거래 Buy/Sell 마커 추가
  - `summary.open_position` 존재 → 미청산 포지션 Buy 마커 추가 (`"Buy $XX.X (보유중)"`)
- **날짜 표기**: `localization.dateFormat: "yyyy-MM-dd"` 설정으로 한국식 날짜 형식 적용
- **customValues**: lightweight-charts v5 내장 기능. Python에서 `customValues` dict를 전달하여 JS `subscribeCrosshairMove` 콜백에서 tooltip으로 표시
  - OHLC 가격: `open`, `high`, `low`, `close`
  - 전일종가대비%: `open_pct`, `high_pct`, `low_pct`, `close_pct`
  - 지표: `ma`, `upper`, `lower`
  - 포트폴리오: `equity`, `dd`
- **display_name 필수**: `summary.json`에 `display_name`이 없으면 `ValueError` 발생

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

주요 테스트 파일: `tests/test_buffer_zone_helpers.py`, `tests/test_buffer_zone.py`, `tests/test_buy_and_hold.py`, `tests/test_analysis.py`, `tests/test_backtest_walkforward.py`

테스트 범위:

- 신호 생성 로직 및 거래 체결 타이밍
- Pending Order 충돌 감지
- 파라미터 유효성 검증
- 엣지 케이스 (빈 데이터, 극단값)
- 그리드 서치 병렬 처리
- resolve_params 파라미터 결정 (FIXED 고정값)
- run_single → SingleBacktestResult 구조 검증
- 미청산 포지션 (open_position): 포지션 보유 시 포함 / 미보유 시 미포함 검증
