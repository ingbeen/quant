# Implementation Plan: 포트폴리오 백테스트 엔진 구현

> 작성/운영 규칙(SoT): 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 참고하세요.

**상태**: ✅ Done

---

🚫 **이 영역은 삭제/수정 금지** 🚫

**상태 옵션**: 🟡 Draft / 🔄 In Progress / ✅ Done

**Done 처리 규칙**:

- ✅ Done 조건: DoD 모두 [x] + `skipped=0` + `failed=0`
- ⚠️ **스킵이 1개라도 존재하면 Done 처리 금지 + DoD 테스트 항목 체크 금지**
- 상세: [docs/CLAUDE.md](../CLAUDE.md) 섹션 3, 5 참고

---

**작성일**: 2026-03-17 14:00
**마지막 업데이트**: 2026-03-17 22:10
**관련 범위**: backtest, common_constants
**관련 문서**: docs/PLAN_portfolio_experiment.md, docs/tranche_design.md, docs/strategy_validation_report.md

---

## 0) 고정 규칙 (이 plan은 반드시 아래 규칙을 따른다)

> 🚫 **이 영역은 삭제/수정 금지** 🚫
> 이 섹션(0)은 지워지면 안 될 뿐만 아니라 **문구가 수정되면 안 됩니다.**
> 규칙의 상세 정의/예외는 반드시 [docs/CLAUDE.md](../CLAUDE.md)를 따릅니다.

- `poetry run python validate_project.py`는 **마지막 Phase에서만 실행**한다. 실패하면 즉시 수정 후 재검증한다.
- Phase 0은 "레드(의도적 실패 테스트)" 허용, Phase 1부터는 **그린 유지**를 원칙으로 한다.
- 이미 생성된 plan은 **체크리스트 업데이트 외 수정 금지**한다.
- 스킵은 가능하면 **Phase 분해로 제거**한다.

---

## 1) 목표(Goal)

- [x] 복수 자산의 독립 시그널 + 목표 비중 배분 + 월간 리밸런싱을 처리하는 포트폴리오 백테스트 엔진 구현
- [x] 엔진 타입 정의 (`portfolio_types.py`) 및 핵심 계약을 테스트로 고정
- [x] `PORTFOLIO_RESULTS_DIR` 상수 추가 (`common_constants.py`)

## 2) 비목표(Non-Goals)

- 7가지 실험 실행 CLI 스크립트 (run_portfolio_backtest.py) → **계획서 2**
- 포트폴리오 비교 대시보드 (app_portfolio_backtest.py) → **계획서 3**
- 기존 `buffer_zone_helpers.py`, `analysis.py`, `split_strategy.py` 변경 없음
- 파라미터 최적화 / WFO → 해당 없음

## 3) 배경/맥락(Context)

### 현재 문제점 / 동기

PLAN_portfolio_experiment.md에서 정의한 7가지 포트폴리오 실험(A-1~A-3, B-1~B-3, C-1)을
실행하기 위한 엔진이 없다. 기존 단일 자산 엔진(`run_buffer_strategy`)은 복수 자산의
비중 배분·리밸런싱을 지원하지 않는다.

### 핵심 설계 결정 (계획서 작성 전 확정)

| 항목 | 결정값 | 근거 |
|---|---|---|
| 리밸런싱 임계값 | 상대 ±20% (`target × ±0.20`) | 소규모 배분(TQQQ 7%)의 과관대 방지 |
| 리밸런싱 트리거 범위 | 매수 자산 중 하나라도 초과 시 → 전 매수 자산 일괄 리밸런싱 | 거래 수 최소화 |
| 현금 부족 처리 | 가용 현금 비례 배분 (scale_factor), 다음 리밸런싱 조정 | 단순성 |
| TQQQ 시그널 소스 | QQQ EMA-200 (`signal_data_path = QQQ_DATA_PATH`) | PLAN §2.3, Gayed & Bilello(2016) |
| 결과 저장 경로 | `storage/results/portfolio/` (신규 루트) | 기존 backtest 결과와 구조적 분리 |
| 타겟 비중 기준 | 총 포트폴리오 가치 대비 (매도 자산 비중 재배분 금지) | PLAN §2.4 분산 구조 보존 |
| 리밸런싱 체결 | 다음 영업일 시가 (pending_order 생성) | 기존 전략과 동일 체결 규칙 |

### 임계값 ±20% 상대 밴드 참고표

| 자산 (타겟) | 하한 | 상한 | 절대 허용폭 |
|---|---|---|---|
| TQQQ 7% | 5.6% | 8.4% | ±1.4%p |
| QQQ/SPY 19.5% (B시리즈) | 15.6% | 23.4% | ±3.9%p |
| QQQ/SPY 30% (A시리즈) | 24.0% | 36.0% | ±6.0%p |
| GLD 40% | 32.0% | 48.0% | ±8.0%p |

### 영향받는 규칙(반드시 읽고 전체 숙지)

> 아래 문서에 기재된 규칙을 **모두 숙지**하고 준수합니다.

- `CLAUDE.md` (루트)
- `src/qbt/backtest/CLAUDE.md`
- `src/qbt/utils/CLAUDE.md`
- `tests/CLAUDE.md`
- `scripts/CLAUDE.md`

## 4) 완료 조건(Definition of Done)

- [x] `PortfolioConfig`, `AssetSlotConfig`, `PortfolioResult` 등 타입 정의 완료
- [x] `run_portfolio_backtest()` 구현 완료 (시그널 + 리밸런싱 + 에쿼티 계산)
- [x] `tests/test_portfolio_strategy.py` 작성 및 전체 통과
- [x] `PORTFOLIO_RESULTS_DIR` 상수 추가 완료 (`common_constants.py`)
- [x] `src/qbt/backtest/CLAUDE.md` — 신규 모듈 설명 업데이트 완료
- [x] `poetry run python validate_project.py` 통과 (failed=0, skipped=0; 결과 기록 필수)
- [x] `poetry run black .` 실행 완료
- [x] plan 체크박스 최신화

## 5) 변경 범위(Scope)

### 변경 대상 파일 (예상)

신규:

- `src/qbt/backtest/portfolio_types.py` — 타입 정의 (AssetSlotConfig, PortfolioConfig, PortfolioResult 등)
- `src/qbt/backtest/portfolio_strategy.py` — 엔진 구현 (run_portfolio_backtest + 헬퍼 함수)
- `tests/test_portfolio_strategy.py` — 핵심 계약 테스트

수정:

- `src/qbt/common_constants.py` — `PORTFOLIO_RESULTS_DIR` 상수 추가 (1줄)
- `src/qbt/backtest/CLAUDE.md` — portfolio_types.py, portfolio_strategy.py 모듈 설명 추가

변경 없음:

- `src/qbt/backtest/buffer_zone_helpers.py` (import만 사용)
- `src/qbt/backtest/analysis.py` (import만 사용)
- `src/qbt/backtest/split_strategy.py`

### 데이터/결과 영향

- 기존 결과 CSV/JSON 변경 없음
- `storage/results/portfolio/` 디렉토리는 계획서 2의 CLI 스크립트 실행 시 생성됨
- `conftest.py`의 `mock_storage_paths` 픽스처에 `PORTFOLIO_RESULTS_DIR` 패치 필요 여부 검토 (Phase 2)

---

## 6) 단계별 계획(Phases)

### Phase 0 — 타입 정의 + 핵심 계약 테스트 (레드)

핵심 불변조건/정책을 코드로 먼저 고정한다. 엔진 미구현이므로 테스트는 실패(레드).

**작업 내용**:

- [x] `src/qbt/backtest/portfolio_types.py` 생성

  ```python
  # 자산 슬롯 설정 (frozen: 불변)
  @dataclass(frozen=True)
  class AssetSlotConfig:
      asset_id: str          # "qqq", "tqqq", "spy", "gld"
      signal_data_path: Path # EMA-200 계산 대상 (TQQQ → QQQ 경로)
      trade_data_path: Path  # 실제 매매 대상 (TQQQ → 합성 데이터 경로)
      target_weight: float   # 예: 0.30 (30%)

  # 포트폴리오 실험 설정 (frozen: 불변)
  @dataclass(frozen=True)
  class PortfolioConfig:
      experiment_name: str               # "portfolio_a2"
      display_name: str                  # "A-2 (QQQ 30% / SPY 30% / GLD 40%)"
      asset_slots: tuple[AssetSlotConfig, ...]
      total_capital: float               # 10_000_000.0
      rebalance_threshold_rate: float    # 0.20 (상대 ±20%)
      result_dir: Path
      # 전 자산 공통 4P 파라미터 (PLAN §4.1)
      ma_window: int                     # 200
      buy_buffer_zone_pct: float         # 0.03
      sell_buffer_zone_pct: float        # 0.05
      hold_days: int                     # 3
      ma_type: str                       # "ema"

  # 자산별 결과 (포지션별 거래 내역 + 시그널 데이터)
  @dataclass
  class PortfolioAssetResult:
      asset_id: str
      trades_df: pd.DataFrame       # 해당 자산 거래 내역
      signal_df: pd.DataFrame       # 시그널 데이터 (OHLCV + MA + 밴드) — 대시보드용

  # 포트폴리오 전체 결과
  @dataclass
  class PortfolioResult:
      experiment_name: str
      display_name: str
      equity_df: pd.DataFrame       # 합산 에쿼티 (하단 컬럼 명세 참고)
      trades_df: pd.DataFrame       # 전 자산 거래 (asset_id 태그 포함)
      summary: Mapping[str, object] # calculate_summary() 호환
      per_asset: list[PortfolioAssetResult]
      config: PortfolioConfig
      params_json: dict[str, Any]   # JSON 저장용 파라미터
  ```

  **equity_df 컬럼 명세 (대시보드 계획서 3 고려)**:

  | 컬럼 | 타입 | 설명 |
  |---|---|---|
  | `Date` | date | 날짜 |
  | `equity` | float | 합산 에쿼티 (shared_cash + 전 자산 평가액) |
  | `cash` | float | 미투자 현금 |
  | `drawdown_pct` | float | 드로우다운 (%) |
  | `{asset_id}_value` | float | 자산별 주식 평가액 (position × close) |
  | `{asset_id}_weight` | float | 자산별 실제 비중 (value / equity) |
  | `{asset_id}_signal` | str | "buy" 또는 "sell" |
  | `rebalanced` | bool | 해당일 리밸런싱 실행 여부 |

  **trades_df 추가 컬럼** (기존 TradeRecord 필드 + 포트폴리오 전용):

  | 추가 컬럼 | 타입 | 설명 |
  |---|---|---|
  | `asset_id` | str | 자산 식별자 ("qqq", "spy" 등) |
  | `trade_type` | str | "signal" 또는 "rebalance" — 거래 원인 |

- [x] `tests/test_portfolio_strategy.py` 생성 — 아래 계약 테스트 작성 (현재 레드)

  **테스트 1: 상대 임계값 경계 조건** (`test_rebalancing_trigger_relative`)

  ```
  Given: target_weight=0.30, actual_weight=0.36 (|0.36/0.30 - 1| = 0.20)
  When:  _check_rebalancing_needed() 호출
  Then:  False 반환 (≤ 0.20 → 트리거 없음, 경계값 포함 미실행)

  Given: target_weight=0.30, actual_weight=0.361 (|0.361/0.30 - 1| > 0.20)
  When:  _check_rebalancing_needed() 호출
  Then:  True 반환 (> 0.20 → 트리거)
  ```

  **테스트 2: 매도 자산 리밸런싱 제외** (`test_rebalancing_excludes_sold_assets`)

  ```
  Given: SPY 시그널 = "sell" (현금 보유 중), QQQ 시그널 = "buy"
         QQQ 실제 비중 35% (타겟 30%, 초과 > ±20%)
  When:  리밸런싱 실행
  Then:  QQQ만 리밸런싱 (30%로 조정)
         SPY 포지션 = 0 유지, 현금 증가 (QQQ 매도분 + SPY 기존 현금)
         SPY 타겟 비중(30%)은 현금으로 그대로 유지
  ```

  **테스트 3: QQQ+TQQQ 시그널 공유** (`test_qqq_tqqq_shared_signal`)

  ```
  Given: QQQ AssetSlotConfig(signal_data_path=QQQ_PATH)
         TQQQ AssetSlotConfig(signal_data_path=QQQ_PATH)  ← 동일 경로
         QQQ 시그널 → "sell" 전환
  When:  엔진 내부 시그널 판정
  Then:  QQQ 매도 pending_order 생성
         TQQQ 매도 pending_order 생성 (동일 날짜)
         두 포지션 모두 청산, 합산 금액 shared_cash 복귀
  ```

  **테스트 4: 현금 부족 시 비례 배분** (`test_cash_partial_fill_on_rebalancing`)

  ```
  Given: 리밸런싱 트리거, 총 매수 필요액 = 3,000,000
         가용 현금 = 2,000,000 (< 필요액)
  When:  _execute_rebalancing() 호출
  Then:  scale_factor = 2,000,000 / 3,000,000 = 0.667
         각 매수 자산: target_buy × 0.667만큼만 매수
         실행 후 shared_cash ≈ 0 (잔여 현금은 주식 수량 정수화 오차)
  ```

  **테스트 5: 에쿼티 산식** (`test_portfolio_equity_formula`)

  ```
  Given: shared_cash=3,000,000, QQQ position=10주 × close=400, GLD position=5주 × close=200
  When:  equity 계산
  Then:  equity = 3,000,000 + 10×400 + 5×200 = 8,000,000
  ```

  **테스트 6: 월 첫 거래일 판정** (`test_monthly_rebalancing_only_on_first_day`)

  ```
  Given: 날짜 목록 [2024-01-30, 2024-01-31, 2024-02-01, 2024-02-02]
  When:  각 날짜에 대해 _is_first_trading_day_of_month() 호출
  Then:  2024-01-30 → False (전 거래일 1월)
         2024-01-31 → False (전 거래일 1월)
         2024-02-01 → True  (전 거래일 1월 → 2월로 전환)
         2024-02-02 → False (전 거래일 2월)
  ```

  **테스트 7: B-1 초기 현금 버퍼** (`test_b1_initial_cash_stays_uninvested`)

  ```
  Given: B-1 config (QQQ 19.5%, TQQQ 7%, SPY 19.5%, GLD 40%)
         target_weight 합 = 0.86 (현금 14% 자연 발생)
         전 자산 시그널 = "buy" (첫날)
  When:  초기 투자 실행
  Then:  QQQ + TQQQ + SPY + GLD 투자액 = total × 0.86
         shared_cash = total × 0.14 (미투자 잔여)
  ```

  **테스트 8: 리밸런싱 순서 (매도 먼저)** (`test_rebalancing_sell_before_buy`)

  ```
  Given: QQQ 과비중 (매도 필요), GLD 과소비중 (매수 필요)
         초기 shared_cash = 0
  When:  _execute_rebalancing() 호출
  Then:  QQQ 매도 pending_order 먼저 생성
         GLD 매수 pending_order는 다음날 QQQ 매도 대금 확보 후 생성
         (동일 날짜에 순차 처리: 매도 체결 → 현금 확보 → 매수 체결)
  ```

  > 참고: 리밸런싱의 매도·매수는 모두 다음 영업일 시가 체결(pending_order).
  > 실제 대금 흐름은 체결일에 발생하므로 테스트에서는 pending_order 생성 여부로 검증.

---

### Phase 1 — 엔진 구현 + 상수 추가 (그린)

Phase 0 테스트를 모두 통과시킨다.

**작업 내용**:

- [x] `src/qbt/common_constants.py` 수정 (1줄 추가)

  ```python
  PORTFOLIO_RESULTS_DIR: Final = RESULTS_DIR / "portfolio"  # 포트폴리오 실험 결과
  ```

- [x] `src/qbt/backtest/portfolio_strategy.py` 생성

  **로컬 상수** (이 파일에서만 사용):

  ```python
  # 상대 리밸런싱 임계값: |actual/target - 1| > 이 값이면 트리거
  REBALANCE_THRESHOLD_RATE: Final = 0.20
  ```

  **내부 상태 타입** (모듈 상단, private):

  ```python
  @dataclass
  class _AssetState:
      """자산별 런타임 상태."""
      position: int                      # 보유 수량
      signal_state: str                  # "buy" | "sell"
      pending_order: PendingOrder | None # 예약 주문 (None = 없음)
      hold_state: HoldState | None       # hold_days 상태머신
  ```

  **공개 함수**:

  ```python
  def run_portfolio_backtest(config: PortfolioConfig) -> PortfolioResult:
      """포트폴리오 백테스트 실행."""
  ```

  **메인 루프 구조**:

  ```
  run_portfolio_backtest(config):
    1. 입력 검증
       - target_weight 합 ≤ 1.0 (초과 시 ValueError)
       - asset_id 중복 없음 (중복 시 ValueError)
       - target_weight ≥ 0 (음수 시 ValueError)

    2. 자산별 데이터 로딩 + MA 계산
       - load_stock_data(signal_data_path) → signal_df
       - load_stock_data(trade_data_path) → trade_df
       - signal_data_path != trade_data_path인 경우:
         extract_overlap_period() 적용
       - add_single_moving_average(signal_df, config.ma_window, config.ma_type)
       - _compute_bands() 적용 (upper_band, lower_band 컬럼 추가)

    3. 공통 기간 추출
       - 모든 자산 trade_df의 교집합 날짜로 필터링
       - 빈 결과 시 ValueError

    4. 자산별 상태 초기화
       - _AssetState(position=0, signal_state="buy", pending_order=None, hold_state=None)
       - shared_cash = config.total_capital

    5. 날짜별 통합 루프 (i = 1 ~ N-1):

       5-1. pending_order 체결 (trade_df[i].Open 기준)
            매수 체결:
              buy_price = trade_open * (1 + SLIPPAGE_RATE)
              shares = int(buy_capital / buy_price)
              shared_cash -= shares * buy_price
            매도 체결:
              sell_price = trade_open * (1 - SLIPPAGE_RATE)
              sell_amount = position * sell_price
              shared_cash += sell_amount
              position = 0
              TradeRecord 기록 (trade_type 필드 포함)

       5-2. 에쿼티 기록 (trade_df[i].Close 기준)
            {asset_id}_value = position * close
            equity = shared_cash + Σ({asset_id}_value)
            drawdown = (equity - peak) / peak * 100
            {asset_id}_signal = state.signal_state
            {asset_id}_weight = value / equity

       5-3. 시그널 판정 (signal_df[i].Close 기준)
            _detect_buy_signal() / _detect_sell_signal() 호출
            신호 변화 시 pending_order 생성
            signal_data_path가 동일한 자산은 동일 시그널 발생 → 동시 pending_order

       5-4. 월 첫 거래일 판정 → 리밸런싱
            _is_first_trading_day_of_month(trade_dates, i):
              trade_dates[i].month != trade_dates[i-1].month
            리밸런싱 필요 여부 확인:
              _check_rebalancing_needed():
                매수 시그널 자산 중 |actual_weight/target_weight - 1| > 0.20
                하나라도 초과 시 True
            리밸런싱 실행:
              _execute_rebalancing():
                1. 매수 시그널 자산의 target_amount = total × target_weight
                2. 초과 자산: delta < 0 → 매도 pending_order 생성
                3. total_sell_proceeds 계산 (예상)
                4. 미달 자산: delta > 0 → 매수 pending_order 생성
                   - 가용 현금 = shared_cash + total_sell_proceeds (추정)
                   - 부족 시: scale_factor 적용 후 비례 매수
                trade_type = "rebalance" 태깅

    6. 결과 조합
       - PortfolioAssetResult 생성 (자산별)
       - combined_trades_df: 전 자산 trades 통합 (asset_id 태깅)
       - equity_df 구성 (_build_combined_equity)
       - calculate_summary(equity_df, trades_df, config.total_capital) 호출
       - params_json 구성 (실험명, 자산 설정, 4P 등)
       - PortfolioResult 반환
  ```

  **리밸런싱 로직 상세**:

  ```
  _check_rebalancing_needed(asset_states, equity_vals, total_equity, config):
    for each asset in buy_signal_assets:
      target = config.asset_slots[asset].target_weight
      if target == 0:
        continue
      actual = equity_vals[asset] / total_equity
      if abs(actual / target - 1) > REBALANCE_THRESHOLD_RATE:
        return True
    return False

  _execute_rebalancing(asset_states, trade_dfs, equity_vals, config, shared_cash, day_idx):
    total_equity = shared_cash + sum(equity_vals.values())
    buy_signal_assets = {id for id, st in asset_states.items() if st.signal_state == "buy"}

    # 매도 대상: 초과 자산
    sell_orders = {}
    for asset in buy_signal_assets:
      target_amount = total_equity * config.asset_slots[asset].target_weight
      delta = target_amount - equity_vals[asset]
      if delta < 0:  # 초과 → 매도
        sell_orders[asset] = abs(delta)

    estimated_sell_proceeds = sum(sell_orders.values())

    # 매수 대상: 미달 자산
    buy_orders = {}
    for asset in buy_signal_assets:
      target_amount = total_equity * config.asset_slots[asset].target_weight
      delta = target_amount - equity_vals[asset]
      if delta > 0:  # 미달 → 매수
        buy_orders[asset] = delta

    total_buy_needed = sum(buy_orders.values())
    available_cash = shared_cash + estimated_sell_proceeds

    if total_buy_needed > available_cash and total_buy_needed > 0:
      scale_factor = available_cash / total_buy_needed
      buy_orders = {a: v * scale_factor for a, v in buy_orders.items()}

    # pending_order 생성 (다음 영업일 시가 체결)
    for asset, amount in sell_orders.items():
      asset_states[asset].pending_order = PendingOrder(order_type="sell", ...)
    for asset, amount in buy_orders.items():
      asset_states[asset].pending_order = PendingOrder(order_type="buy", capital=amount, ...)
  ```

  **재사용 임포트** (`buffer_zone_helpers.py`에서):

  ```python
  from qbt.backtest.strategies.buffer_zone_helpers import (  # type: ignore[import]
      HoldState,
      PendingOrder,
      _compute_bands,        # pyright: ignore[reportPrivateUsage]
      _detect_buy_signal,    # pyright: ignore[reportPrivateUsage]
      _detect_sell_signal,   # pyright: ignore[reportPrivateUsage]
  )
  from qbt.backtest.constants import SLIPPAGE_RATE
  from qbt.backtest.analysis import add_single_moving_average, calculate_summary
  from qbt.utils.data_loader import load_stock_data, extract_overlap_period
  ```

**Validation** (Phase 1):

- [x] `poetry run python validate_project.py --only-tests` 통과

---

### Phase 2 — 엣지 케이스 테스트 + CLAUDE.md 업데이트 (그린)

- [x] 엣지 케이스 테스트 추가 (`tests/test_portfolio_strategy.py`에 추가)

  - `test_invalid_config_weight_sum_exceeds_one`: target_weight 합 > 1.0 → ValueError
  - `test_invalid_config_duplicate_asset_id`: asset_id 중복 → ValueError
  - `test_no_overlap_period`: 공통 기간 없음 → ValueError
  - `test_single_asset_portfolio`: 자산 1개 포트폴리오 (GLD 100%) 정상 동작
  - `test_rebalancing_not_triggered_after_just_rebalanced`: 리밸런싱 직후 같은 월에 재트리거 없음
  - `test_c1_full_cash_on_sell`: C-1 (QQQ 50% + TQQQ 50%) 매도 시 전액 현금화

- [x] `src/qbt/backtest/CLAUDE.md` 업데이트

  - `portfolio_types.py` 모듈 설명 추가 (AssetSlotConfig, PortfolioConfig, PortfolioResult)
  - `portfolio_strategy.py` 모듈 설명 추가 (run_portfolio_backtest, REBALANCE_THRESHOLD_RATE)

- [x] `tests/conftest.py` 확인 — `mock_storage_paths`에 `PORTFOLIO_RESULTS_DIR` 패치 필요 시 추가 (불필요: 테스트에서 result_dir=tmp_path 직접 사용)

**Validation** (Phase 2):

- [x] `poetry run python validate_project.py --only-tests` 통과

---

### 마지막 Phase — 최종 검증

**작업 내용**:

- [x] `poetry run black .` 실행 (자동 포맷 적용)
- [x] DoD 체크리스트 최종 업데이트 및 체크 완료
- [x] 전체 Phase 체크리스트 확인

**Validation**:

- [x] `poetry run python validate_project.py` (passed=365, failed=0, skipped=0)

#### Commit Messages (Final candidates) — 5개 중 1개 선택

1. 백테스트 / 포트폴리오 백테스트 엔진 구현 (멀티자산 시그널 + 리밸런싱)
2. 백테스트 / 포트폴리오 엔진 + 타입 정의 + 핵심 계약 테스트 고정
3. 백테스트 / 포트폴리오 엔진 신규 구현 (상대 ±20% 리밸런싱 정책)
4. 백테스트 / 멀티자산 포트폴리오 엔진 + PORTFOLIO_RESULTS_DIR 상수 추가
5. 백테스트 / 포트폴리오 실험 기반 엔진 구현 (A/B/C 시리즈 공통 기반)

---

## 7) 리스크(Risks)

| 리스크 | 설명 | 완화책 |
|---|---|---|
| TQQQ 시그널 공유 구현 오류 | signal_data_path가 동일해도 MA 계산 시 별도 객체로 처리될 수 있음 | Phase 0 test_qqq_tqqq_shared_signal로 계약 고정 |
| 리밸런싱 체결 타이밍 불일치 | 매도 대금이 다음날 시가에 확보되므로 매수 자본 계산 시 타이밍 오차 발생 가능 | pending_order 2단계 처리 (매도→체결→매수) 명시 + 테스트 검증 |
| 비례 축소 엣지 케이스 | available_cash = 0 이면 scale_factor = 0 → 매수 안 됨 | 0 처리 명시 (구현 주석) + test_cash_partial_fill로 검증 |
| equity_df 컬럼 수 증가 | 자산 수 × 3 컬럼(value, weight, signal) → 대형 포트폴리오 시 컬럼 많아짐 | 현재 최대 4자산 × 3 = 12 컬럼 + 공통 4 = 16 컬럼 (허용 범위) |
| 기존 테스트 회귀 | common_constants.py 수정이 conftest.py mock_storage_paths에 영향 줄 수 있음 | Phase 1 완료 후 --only-tests 실행으로 즉시 확인 |

---

## 8) 메모(Notes)

### 설계 결정 기록

**signal_data_path를 통한 TQQQ 시그널 공유 메커니즘**:

QQQ와 TQQQ 모두 `signal_data_path = QQQ_DATA_PATH`로 설정하면,
엔진은 동일한 QQQ 데이터에서 EMA-200을 계산하여 두 자산에 동일한 시그널을 발생시킨다.
별도의 "그룹" 개념 없이 자연스럽게 동시 매수/매도가 구현된다.
이것이 PLAN §2.3, §4.2의 "QQQ와 TQQQ는 항상 동시에 매수/매도된다"를 코드로 표현하는 방식이다.

**리밸런싱 pending_order와 시그널 pending_order 충돌 처리**:

같은 날 시그널 변화와 리밸런싱이 동시에 발생하는 경우:
- 우선순위: 시그널 pending_order 실행 후 리밸런싱 판단
- 시그널로 이미 pending_order가 있는 자산은 리밸런싱에서 제외 (당일 체결 후 내일 재평가)

**B시리즈 현금 버퍼 동작 원리**:

target_weight 합이 1.0 미만인 경우(예: B-1 = 0.86),
초기 투자 후 shared_cash에 자연스럽게 미투자 잔액이 남는다.
리밸런싱 시에도 각 자산을 target_weight 기준으로 조정하면,
총 투자액 = total × 0.86, 현금 = total × 0.14가 자동 유지된다.
별도의 "현금 버퍼 슬롯"은 구현하지 않는다.

**계획서 전체 구성 (3개)**:

| 계획서 | 파일명 | 내용 |
|---|---|---|
| 계획서 1 (현재) | PLAN_portfolio_engine.md | 엔진 + 타입 + 상수 |
| 계획서 2 | PLAN_portfolio_scripts.md | CLI 스크립트 (7가지 실험 실행 + 결과 저장) |
| 계획서 3 | PLAN_portfolio_dashboard.md | 포트폴리오 비교 대시보드 |

### 진행 로그 (KST)

- 2026-03-17 14:00: 계획서 초안 작성 완료 (설계 결정 사항 반영)
- 2026-03-17 22:10: 전 Phase 구현 완료. validate_project.py 통과 (passed=365, failed=0, skipped=0)
