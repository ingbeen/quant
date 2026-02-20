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

- `SummaryDict`: `calculate_summary()` 반환 타입 (성과 지표 요약)
- `BestGridParams`: grid_results.csv 최적 파라미터 (ma_window, buffer_zone_pct, hold_days, recent_months)
- `SingleBacktestResult`: 각 전략의 `run_single()` 공통 반환 타입 (dataclass). strategy_name, display_name, signal_df, equity_df, trades_df, summary, params_json, result_dir, data_info 포함

### 2. constants.py

백테스트 도메인 전용 상수를 정의합니다.

주요 상수 카테고리:

- 거래 비용: `SLIPPAGE_RATE` (0.3%, 슬리피지 + 수수료 통합)
- 기본 파라미터: `DEFAULT_INITIAL_CAPITAL`, `DEFAULT_MA_WINDOW`, `DEFAULT_BUFFER_ZONE_PCT` 등
- 제약 조건: `MIN_BUFFER_ZONE_PCT`, `MIN_HOLD_DAYS`, `MIN_VALID_ROWS`
- 그리드 서치 기본값: `DEFAULT_MA_WINDOW_LIST`, `DEFAULT_BUFFER_ZONE_PCT_LIST` 등
- 그리드 서치 결과 CSV 출력용 레이블: `DISPLAY_MA_WINDOW`, `DISPLAY_BUFFER_ZONE` 등

### 3. analysis.py

이동평균 계산 및 성과 지표 분석 함수를 제공합니다.

주요 함수:

- `add_single_moving_average`: 단일 이동평균(SMA/EMA) 계산
- `calculate_summary`: 거래 내역과 자본 곡선으로부터 성과 지표 계산
- `load_best_grid_params`: grid_results.csv에서 CAGR 1위 파라미터 로딩 (파일 없으면 None 반환)
- `calculate_monthly_returns`: 에쿼티 데이터로부터 월별 수익률 계산

### 4. strategies/ 패키지

전략 실행 엔진을 전략별로 분리한 패키지입니다.

#### strategies/buffer_zone.py

버퍼존 전략의 전체 구현을 포함합니다 (데이터 클래스, 헬퍼 함수, 실행 함수, 전략 전용 타입).

전략 식별 상수:

- `STRATEGY_NAME`: 전략 내부 식별자 (`"buffer_zone"`)
- `DISPLAY_NAME`: 전략 표시명 (`"버퍼존 전략"`)

데이터 소스 경로:

- `SIGNAL_DATA_PATH`: 시그널용 데이터 경로 (`QQQ_DATA_PATH`)
- `TRADE_DATA_PATH`: 매매용 데이터 경로 (`TQQQ_SYNTHETIC_DATA_PATH`)

전략 전용 TypedDict (types.py에서 이동):

- `BufferStrategyResultDict`: `run_buffer_strategy()` 반환 타입
- `EquityRecord`: equity 기록 딕셔너리
- `TradeRecord`: 거래 기록 딕셔너리
- `HoldState`: hold_days 상태머신 상태
- `GridSearchResult`: 그리드 서치 결과 딕셔너리

데이터 클래스:

- `BaseStrategyParams`: 전략 파라미터 기본 클래스
- `BufferStrategyParams`: 버퍼존 전략 파라미터
- `PendingOrder`: 예약 주문 정보 (신호일과 체결일 분리)

예외 클래스:

- `PendingOrderConflictError`: Pending Order 충돌 예외 (Critical Invariant 위반)

로컬 상수 (`buffer_zone.py` 상단):

- `DEFAULT_BUFFER_INCREMENT_PER_BUY`: 최근 매수 1회당 버퍼존 증가량 (0.01 = 1%)
- `DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY`: 최근 매수 1회당 유지조건 증가량 (1일)
- `DEFAULT_DAYS_PER_MONTH`: 최근 기간 계산용 월당 일수 (30일 근사값)

헬퍼 함수 (9개):

- `_validate_buffer_strategy_inputs`, `_compute_bands`, `_check_pending_conflict`
- `_record_equity`, `_execute_buy_order`, `_execute_sell_order`
- `_detect_buy_signal`, `_detect_sell_signal`, `_calculate_recent_buy_count`

오버라이드 상수 (`buffer_zone.py` 상단):

- `OVERRIDE_MA_WINDOW`: MA 기간 수동 설정 (None = 자동)
- `OVERRIDE_BUFFER_ZONE_PCT`: 버퍼존 비율 수동 설정 (None = 자동)
- `OVERRIDE_HOLD_DAYS`: 유지일 수동 설정 (None = 자동)
- `OVERRIDE_RECENT_MONTHS`: 조정기간 수동 설정 (None = 자동)
- `MA_TYPE`: 이동평균 유형 ("ema")

주요 함수:

- `run_buffer_strategy`: 버퍼존 전략 실행
- `run_grid_search`: 파라미터 그리드 탐색 (병렬 처리)
- `_run_buffer_strategy_for_grid`: 그리드 서치용 병렬 실행 헬퍼
- `resolve_params`: 파라미터 결정 (폴백 체인: OVERRIDE → grid_best → DEFAULT)
- `run_single`: 단일 백테스트 실행 (인자 없음, 자체 데이터 로딩) → `SingleBacktestResult` 반환

#### strategies/buy_and_hold.py

Buy & Hold 벤치마크 전략 구현입니다. 팩토리 패턴으로 멀티 티커를 지원한다.

설정 데이터클래스:

- `BuyAndHoldConfig`: 티커별 전략 설정 (strategy_name, display_name, trade_data_path, result_dir)

티커별 설정 목록:

- `CONFIGS`: `list[BuyAndHoldConfig]`. 새 티커 추가 시 여기에 한 줄 추가
  - `buy_and_hold_qqq`: QQQ 데이터 (`QQQ_DATA_PATH`) 사용
  - `buy_and_hold_tqqq`: TQQQ 합성 데이터 (`TQQQ_SYNTHETIC_DATA_PATH`) 사용

파라미터 데이터클래스:

- `BuyAndHoldParams`: Buy & Hold 전략 파라미터 (initial_capital)

주요 함수:

- `run_buy_and_hold`: 매수 후 보유 벤치마크 전략 실행 (`trade_df`만 받음, `signal_df` 미사용) → `SummaryDict` 반환
- `resolve_params`: 파라미터 결정 (항상 DEFAULT_INITIAL_CAPITAL 사용)
- `create_runner`: 팩토리 함수. `BuyAndHoldConfig` → `Callable[[], SingleBacktestResult]` 생성

#### strategies/**init**.py

전략 패키지의 공개 API를 export합니다.

설계 결정 사항:

- helpers.py 미생성: YAGNI 원칙 적용. 버퍼존 전용 헬퍼는 `buffer_zone.py`에 직접 배치.
  향후 버퍼존 계열 전략 추가 시 공통 헬퍼를 추출하여 helpers.py 생성 예정.

---

## 도메인 규칙

### 1. 전략 파라미터

- 이동평균 기간 (`ma_window`): 추세 판단의 기준 기간, 1 이상
- 버퍼존 (`buffer_zone_pct`): 이동평균선 주변 허용 범위 (비율, 0~1)
- 유지 조건 (`hold_days`): 신호 확정까지 대기 기간 (일), 0 = 버퍼존만 모드
- 조정 기간 (`recent_months`): 최근 거래 분석 기간, 0이면 동적 조정 비활성화

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

---

## 핵심 계산 로직

### 버퍼존 밴드 계산

```
upper_band = ma * (1 + buffer_zone_pct)
lower_band = ma * (1 - buffer_zone_pct)
```

### 동적 파라미터 조정

```
adjusted_buffer_pct = base_buffer_pct + (recent_buy_count * DEFAULT_BUFFER_INCREMENT_PER_BUY)
adjusted_hold_days = base_hold_days + (recent_buy_count * DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY)
```

주의: 하드코딩 금지, 상수 사용 필수

### 성과 지표 계산

- 총 수익률: `(final_capital - initial_capital) / initial_capital * 100`
- CAGR: `((final_capital / initial_capital) ^ (ANNUAL_DAYS / 총일수)) - 1`
- MDD: 자본 곡선에서 최대 낙폭 계산
- 승률: `profitable_trades / total_trades * 100`

---

## CSV 파일 형식

### grid_results.csv

경로: `storage/results/backtest/buffer_zone/grid_results.csv`

주요 컬럼: 이평기간, 버퍼존, 유지일, 조정기간(월), 수익률, CAGR, MDD, 거래수, 승률, 최종자본

정렬: CAGR 내림차순

---

## 대시보드 앱 아키텍처

### 동적 전략 탭 (`scripts/backtest/app_single_backtest.py`)

대시보드는 `BACKTEST_RESULTS_DIR` 하위 디렉토리를 자동 탐색하여 전략별 탭을 생성한다.
새로운 전략이 추가되면 결과 폴더만 있으면 앱 코드 수정 없이 자동으로 탭이 추가된다.

핵심 설계:

- **전략 자동 탐색**: `_discover_strategies()`가 하위 디렉토리의 `summary.json` 존재 여부로 유효한 전략 결과를 판별
- **Feature Detection**: 전략명 분기(`if strategy == "buffer_zone"`) 없이 DataFrame 컬럼 감지로 차트 오버레이 결정
  - `ma_*` 컬럼 존재 → MA 오버레이 추가
  - `upper_band`/`lower_band` 존재 → 밴드 오버레이 추가
  - `trades_df`가 비어있지 않음 → 마커 추가
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

주요 테스트 파일: `tests/test_strategy.py`, `tests/test_analysis.py`

테스트 범위:

- 신호 생성 로직 및 거래 체결 타이밍
- Pending Order 충돌 감지
- 파라미터 유효성 검증
- 엣지 케이스 (빈 데이터, 극단값)
- 동적 파라미터 조정
- 그리드 서치 병렬 처리
- resolve_params 폴백 체인 (OVERRIDE → grid_best → DEFAULT)
- run_single → SingleBacktestResult 구조 검증
