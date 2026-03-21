# 백테스트 폐기 모듈 아카이브

> 삭제일: 2026-03-10
> 근거: `docs/overfitting_analysis_report.md` (이하 "보고서")
> 계획서: `docs/plans/PLAN_backtest_cleanup.md`

---

## 삭제 대상 소스 모듈 (6개)

### 1. `src/qbt/backtest/cpcv.py` — CSCV/PBO/DSR 과최적화 통계 검증

**목적**: CSCV(조합적 대칭 교차검증) 기반 PBO(백테스트 과최적화 확률)와 DSR(Deflated Sharpe Ratio)을 계산하여 파라미터 탐색의 과최적화 위험을 정량화.

**핵심 함수/클래스**:

- `_norm_cdf()`, `_norm_ppf()`, `_logit()`: scipy 대체 수학 유틸리티
- `_compute_annualized_sharpe()`: 일별 수익률 → 연간화 Sharpe
- `_compute_calmar_from_returns()`: 일별 수익률 → Calmar Ratio
- `generate_cscv_splits()`: C(n_blocks, n_blocks//2) 대칭 IS/OOS 분할 생성
- `calculate_pbo()`: CSCV 기반 PBO 계산
- `calculate_dsr()`: Deflated Sharpe Ratio 계산 (다중검정 보정)
- `generate_param_combinations()`: 파라미터 리스트 → BufferStrategyParams 리스트
- `build_returns_matrix()`: 병렬 실행으로 수익률 행렬 구축
- `run_cscv_analysis()`: 통합 오케스트레이션 (행렬 → PBO → DSR)

**폐기 사유**: 결론 완료. 보고서 §4~5에 전략별 PBO/DSR 수치가 기록됨.

**주요 결과 수치** (보고서 §4.2, §5):

| 전략 | PBO | DSR | Z-Score | 판정 |
|---|---|---|---|---|
| 버퍼존 (QQQ) | 0.40 | 0.78 | 0.778 | 경고 수준 |
| 버퍼존 (TQQQ) | 0.45 | 0.79 | 0.806 | 동전 던지기에 근접 |
| ATR WFO (TQQQ) | 0.65 | 0.35 | -0.390 | 명확한 과최적화 |

---

### 2. `src/qbt/backtest/atr_comparison.py` — ATR 고정 WFO OOS 비교 실험

**목적**: ATR(14,3.0) vs ATR(22,3.0) 두 고정 설정으로 IS 최적화 없이 WFO OOS 성과를 비교. PBO 경고에 대한 독립 검증 증거 제공.

**핵심 함수/클래스**:

- `AtrComparisonResultDict`, `WindowComparisonRow`: TypedDict
- `run_single_atr_config()`: 단일 ATR 설정 WFO 실행 + Stitched Equity 생성
- `build_window_comparison()`: 윈도우별 OOS 비교 DataFrame 생성
- `build_comparison_summary()`: 요약 통계 (Stitched 지표, 우위 카운트)

**폐기 사유**: ATR WFO 전략 폐기 (보고서 §3.3)에 따라 불필요. 결론 완료된 일회성 실험.

---

### 3. `src/qbt/backtest/wfo_comparison.py` — Expanding vs Rolling WFO 비교 실험

**목적**: Expanding Anchored WFO와 Rolling Window WFO(IS=120개월)의 동일 OOS 성과 차이를 측정. 위기 데이터 망각 위험 검증.

**핵심 함수/클래스**:

- `WfoComparisonResultDict`, `WfoComparisonWindowRow`: TypedDict
- `run_single_wfo_mode()`: 단일 WFO 모드 실행 + Stitched Equity 생성
- `build_window_comparison()`: 윈도우별 Expanding vs Rolling 비교 DataFrame
- `build_comparison_summary()`: IS 분기 통계 포함 요약

**폐기 사유**: ATR WFO 전략 폐기 (보고서 §3.3)에 따라 불필요.

---

### 4. `src/qbt/backtest/strategies/buffer_zone_atr_tqqq.py` — 버퍼존 ATR 전략 설정/실행

**목적**: QQQ 시그널 + TQQQ 매매에 ATR 트레일링 스탑을 추가한 전략의 설정 및 단일 백테스트 실행.

**핵심 함수/클래스**:

- `STRATEGY_NAME = "buffer_zone_atr_tqqq"`, `DISPLAY_NAME = "버퍼존 전략 ATR (TQQQ)"`
- `resolve_params()`: OVERRIDE → grid_results.csv → DEFAULT 폴백 + ATR 파라미터 결정
- `run_single()`: 단일 백테스트 실행 → `SingleBacktestResult`

**ATR 핵심 설계**: ATR 시그널은 QQQ(signal_df) 고정, `close < highest_close_since_entry - atr_value * multiplier` 발동.

**폐기 사유**: "실전 투입 부적절" 판정 (보고서 §3.3). PBO 0.65, DSR Z-Score -0.390.

---

### 5. `src/qbt/backtest/strategies/donchian_helpers.py` — Donchian Channel 전략 엔진

**목적**: Donchian Channel(터틀 트레이딩) 전략의 핵심 실행 엔진. N일 최고가/M일 최저가 기반 독립적 프레임워크.

**핵심 함수/클래스**:

- `DonchianStrategyParams`: 전략 파라미터 (initial_capital, entry_channel_days, exit_channel_days)
- `DonchianEquityRecord`, `DonchianTradeRecord`, `DonchianStrategyResultDict`: TypedDict
- `compute_donchian_channels()`: Donchian Channel 상단/하단 계산 (shift(1) lookahead 방지)
- `run_donchian_strategy()`: 전략 실행 (pending order 패턴 사용)

**폐기 사유**: overfitting 보고서에서 한 번도 언급되지 않은 실험적 코드.

---

### 6. `src/qbt/backtest/strategies/donchian_channel_tqqq.py` — Donchian Channel 전략 래퍼

**목적**: QQQ 시그널 + TQQQ 매매 Donchian Channel 전략의 설정 및 실행 래퍼.

**핵심 함수/클래스**:

- `STRATEGY_NAME = "donchian_channel_tqqq"`, `DISPLAY_NAME = "Donchian Channel (TQQQ)"`
- `resolve_params()`: OVERRIDE → DEFAULT 폴백
- `run_single()`: 단일 백테스트 실행 → `SingleBacktestResult`

**폐기 사유**: donchian_helpers.py와 동일. 실험적 코드.

---

## 삭제 대상 스크립트 (5개)

### 1. `scripts/backtest/run_cpcv_analysis.py`

**쓰임새**: `--strategy` 인자로 전략을 선택하여 CSCV/PBO/DSR 분석 실행. 병렬로 수익률 행렬 구축 후 PBO + DSR 계산.
**선행**: 데이터 CSV 존재 (QQQ, TQQQ synthetic)
**후행**: `cscv_analysis.json`, `cscv_logit_lambdas.csv` 저장
**비즈니스 로직 의존**: `cpcv.py`

### 2. `scripts/backtest/run_atr_comparison.py`

**쓰임새**: ATR(14,3.0) vs ATR(22,3.0) 고정 OOS 비교 실험 실행.
**선행**: 데이터 CSV 존재
**후행**: `atr_comparison_windows.csv`, `atr_comparison_summary.json` 저장
**비즈니스 로직 의존**: `atr_comparison.py`

### 3. `scripts/backtest/run_wfo_comparison.py`

**쓰임새**: Expanding vs Rolling WFO 비교 실험 실행.
**선행**: 데이터 CSV 존재
**후행**: `wfo_comparison_windows.csv`, `wfo_comparison_summary.json` 저장
**비즈니스 로직 의존**: `wfo_comparison.py`

### 4. `scripts/backtest/run_wfo_stitched_backtest.py`

**쓰임새**: WFO Dynamic 결과를 대시보드 호환 형식으로 변환. `walkforward_dynamic.csv` → params_schedule → OOS 전체 1회 실행.
**선행**: `run_walkforward.py --strategy buffer_zone_atr_tqqq` 실행 완료
**후행**: `buffer_zone_atr_tqqq_wfo/` 하위에 signal/equity/trades/summary 저장
**비즈니스 로직 의존**: `walkforward.py`, `buffer_zone_helpers.py`, `analysis.py`

### 5. `scripts/backtest/run_cross_asset_bh_comparison.py`

**쓰임새**: 7개 자산 Buy & Hold 벤치마크와 버퍼존 전략 성과 비교 테이블 생성.
**선행**: `run_single_backtest.py` 실행 완료 (전략 결과 존재)
**후행**: `cross_asset_bh_comparison.csv`, `cross_asset_bh_detail.csv` 저장
**비즈니스 로직 의존**: `buy_and_hold.py`

---

## 삭제 대상 테스트 (4개)

| 테스트 파일 | 테스트 대상 모듈 |
|---|---|
| `tests/test_cpcv.py` | `cpcv.py` |
| `tests/test_atr_comparison.py` | `atr_comparison.py` |
| `tests/test_wfo_comparison.py` | `wfo_comparison.py` |
| `tests/test_donchian_helpers.py` | `donchian_helpers.py` |

---

## 삭제 대상 결과 데이터

### 폴더 전체 삭제

- `storage/results/backtest/donchian_channel_tqqq/`
- `storage/results/backtest/buffer_zone_atr_tqqq_wfo/`
- `storage/results/backtest/buffer_zone_qqq_3p/`

### 폴더 내 특정 파일 삭제

- `storage/results/backtest/buffer_zone_atr_tqqq/` 내: `cscv_*`, `walkforward_*`, `atr_comparison_*`, `wfo_comparison_*`
- `storage/results/backtest/buffer_zone_tqqq/` 내: `cscv_*`, `walkforward_*`
- `storage/results/backtest/buffer_zone_qqq/` 내: `cscv_*`, `walkforward_*`
- `storage/results/backtest/cross_asset_bh_comparison.csv`, `cross_asset_bh_detail.csv`

---

---

# 분할 매수매도(Split Tranche) 폐기 모듈 아카이브

> 삭제일: 2026-03-21
> 근거: `docs/strategy_validation_report.md §25` — 백테스트·WFO 검증 결과 기각 확정 (2026-03-15)
> 계획서: `docs/plans/PLAN_portfolio_rebalancing_v2.md`
> 복원: `git show 6f0a9bd2a4feb0f59d564d52cc62ffb98c2e4885 -- <파일경로>`

**폐기 사유 요약** (`strategy_validation_report.md §25`):

백테스트에서 단일 MA-200 대비 모든 지표가 열등하여 기각. 기각 근거 5가지:

1. **성과 열등** (§25.2): QQQ 기준 MDD -4.51%p 악화(−36.49% → −41.00%), CAGR −0.24%p, Calmar −0.04, 거래 수 3배 증가.
2. **시그널 상관관계 과다** (§25.3): MA-150/200/250은 기초 데이터 ~60% 공유, 쌍별 상관 ~0.93. 포트폴리오 표준편차 감소 1.7% (비상관 3전략이면 42%). 실질 독립 베팅 수 ~1.03 → 사실상 1개 시그널.
3. **MDD 악화의 구조적 원인** (§25.4): 급락 시 MA-250(느린 트랜치)이 1/3 자본을 추가 하락에 노출 → MA-150 조기 청산 이득 상쇄. 이진 멀티 트랜치 시스템의 **부분 노출 문제(partial exposure problem)**.
4. **WFO가 "고원 내 이동은 노이즈"임을 증명** (§25.5): QQQ WFO Dynamic 11개 윈도우 전부 MA=200 (MA-150/250 선택 0회). Fixed(Calmar 0.432)가 Dynamic(0.315)보다 37% 우세 → 고원 내 이동 추적 자체가 무의미.
5. **암묵적 과최적화 위험** (§25.6): 트랜치 수(3), 구체적 MA 값(150/200/250), 가중치(33:34:33), 간격(50일) 모두 암묵적 자유도 추가 — Harvey, Liu & Zhu(2016) 기준 연구자 자유도 확장.

**올바른 고원 해석** (§25.7): "고원 내 여러 포인트를 쓰자"가 아니라 "아무거나 1개 골라도 괜찮다는 자신감을 갖자". 고원이 넓을수록 시그널이 비슷해져 분산 효과는 오히려 줄어든다.

**대안** (§25.8): 단일 MA-200 고정 + 자산 추가(QQQ/SPY 병행). 교차 자산 분산이 파라미터 분산보다 효과 ~25배 우세.

---

## 삭제 대상 소스 모듈 (1개)

### 1. `src/qbt/backtest/split_strategy.py` — 분할 매수매도 오케스트레이터

**목적**: 3개 트랜치(ma250/ma200/ma150)를 공유 자본(shared_cash)으로 운용하는 분할 버퍼존 전략 오케스트레이터. 트랜치별 독립 시그널 + 공유 현금 배분 + 합산 에쿼티 구성.

**핵심 설계 원칙**:

- **공유 자본(shared_cash)**: 전체 자본을 단일 현금 풀로 관리. 분리된 계좌가 아님.
- **매수 배분**: 체결 시점의 `shared_cash ÷ 미보유 트랜치 수`로 자동 배분. 미보유 트랜치 수는 체결 루프 시작 시점 기준.
- **매도 복귀**: 해당 트랜치의 전량 매도 대금이 `shared_cash`에 복귀.
- **체결 순서**: 트랜치 순서(ma250 → ma200 → ma150) 고정. 같은 날 복수 체결 시 앞 트랜치 매수가 현금을 먼저 소비.

**전략 설정 목록 (`SPLIT_CONFIGS`)**:

| 전략명 | 대상 자산 | 결과 저장 경로 |
|---|---|---|
| `split_buffer_zone_tqqq` | QQQ 시그널 + TQQQ 매매 | `storage/results/backtest/split_buffer_zone_tqqq/` |
| `split_buffer_zone_qqq` | QQQ 시그널 + QQQ 매매 | `storage/results/backtest/split_buffer_zone_qqq/` |

**트랜치 구성** (constants.py의 `SPLIT_TRANCHE_*` 상수 기반):

| tranche_id | ma_window | weight |
|---|---|---|
| `ma250` | 250 | 0.33 |
| `ma200` | 200 | 0.34 |
| `ma150` | 150 | 0.33 |

**데이터 클래스**:

- `SplitTrancheConfig` (frozen): `tranche_id`, `weight`, `ma_window`
- `SplitStrategyConfig` (frozen): `strategy_name`, `display_name`, `base_config(BufferZoneConfig)`, `total_capital`, `tranches`, `result_dir`
- `SplitTrancheResult`: `tranche_id`, `config`, `trades_df`, `equity_df`, `summary(BufferStrategyResultDict)`
- `SplitStrategyResult`: `strategy_name`, `display_name`, `combined_equity_df`, `combined_trades_df`, `combined_summary`, `per_tranche`, `config`, `params_json`, `signal_df`
- `_TrancheState` (내부용): 날짜별 통합 루프에서 트랜치별 상태 관리 (position, entry_price, pending_order, hold_state, prev_upper/lower_band 등)

**핵심 함수**:

- `run_split_backtest(config)`: 공유 자본 방식 분할 백테스트 실행 (날짜별 통합 루프, 7단계)
  1. 입력 검증 (중복 tranche_id 감지)
  2. 데이터 로딩 1회 (signal/trade 데이터, 겹치는 기간 추출)
  3. 모든 트랜치 MA 사전 계산
  4. MA 유효 시작점 결정 (가장 큰 MA 윈도우 기준)
  5. 트랜치별 상태 초기화
  6. 날짜별 통합 루프 (pending order 체결 → 밴드 계산 + 에쿼티 기록 → 시그널 판정)
  7. 결과 조합 (트랜치별 결과 → 합산 에쿼티 → 합산 거래 → 합산 summary)
- `_build_combined_equity(tranche_results, final_cash, total_capital)`: 트랜치별 주식 평가액 + 현금 역산으로 합산 에쿼티 구성. `active_tranches`, `avg_entry_price` 컬럼 포함.
- `_combine_trades(tranche_results)`: 트랜치별 거래 합산. `tranche_id`, `tranche_seq`, `ma_window` 컬럼 태깅 후 entry_date 오름차순 정렬.
- `_calculate_combined_summary(combined_equity_df, combined_trades_df, total_capital, tranche_results)`: 합산 에쿼티로 `calculate_summary()` 재사용.
- `_build_params_json(config)`: JSON 저장용 파라미터 딕셔너리 생성 (total_capital, buy/sell_buffer_zone_pct, hold_days, ma_type, tranches 리스트).
- `_get_latest_entry_price(trades_df, equity_df, current_date, open_position)`: 현재 보유 포지션의 entry_price 반환 (합산 에쿼티의 avg_entry_price 계산용).

**의존성**:

- `analysis.py`: `add_single_moving_average`, `calculate_summary`
- `strategies/buffer_zone_helpers.py`: `_compute_bands`, `_detect_buy_signal`, `_detect_sell_signal`, `HoldState`, `PendingOrder`, `TradeRecord`, `BufferStrategyResultDict`
- `strategies/buffer_zone.py`: `BufferZoneConfig`
- `utils/data_loader.py`: `load_stock_data`, `extract_overlap_period`
- `backtest/constants.py`: `SLIPPAGE_RATE`, `SPLIT_TRANCHE_IDS`, `SPLIT_TRANCHE_MA_WINDOWS`, `SPLIT_TRANCHE_WEIGHTS`
- `common_constants.py`: `SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR`, `SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR` (이 상수들도 함께 삭제됨)

---

## 삭제 대상 스크립트 (2개)

### 1. `scripts/backtest/run_split_backtest.py`

**쓰임새**: `--strategy` 인자로 분할 전략을 선택하여 실행. 결과를 CSV/JSON으로 저장하고 트랜치별 성과 테이블을 출력.
**선행**: 데이터 CSV 존재 (QQQ, TQQQ synthetic)
**후행**: `split_buffer_zone_{tqqq|qqq}/` 하위에 `signal.csv`, `equity.csv`, `trades.csv`, `summary.json` 저장. `meta.json`에 `"split_backtest"` 타입으로 이력 기록.
**비즈니스 로직 의존**: `split_strategy.py`

**`signal.csv` 특이사항**: 3개 MA(ma_150/200/250) + 6개 밴드(upper_band_{150,200,250}, lower_band_{150,200,250}) + 전일종가대비(change_pct) 포함. 밴드 계산: `upper = ma × (1 + buy_buffer_zone_pct)`, `lower = ma × (1 - sell_buffer_zone_pct)`.

**`equity.csv` 특이사항**: `equity`, `drawdown_pct`, `active_tranches`, `avg_entry_price`, `{tranche_id}_equity`, `{tranche_id}_position` 컬럼 포함.

**`summary.json` 구조**:
```json
{
  "display_name": "...",
  "split_summary": { "initial_capital", "final_capital", "total_return_pct", "cagr", "mdd", "calmar", "total_trades", "active_open_positions" },
  "tranches": [ { "tranche_id", "ma_window", "weight", "initial_capital", "summary": {...}, "open_position": {...} } ],
  "split_config": { "total_capital", "buy_buffer_zone_pct", "sell_buffer_zone_pct", "hold_days", "ma_type", "tranches": [...] }
}
```

### 2. `scripts/backtest/app_split_backtest.py`

**쓰임새**: 분할 전략 결과를 Streamlit + lightweight-charts-v5로 시각화.
**선행**: `run_split_backtest.py` 실행 완료 (결과 CSV/JSON 존재)
**실행 명령**: `poetry run streamlit run scripts/backtest/app_split_backtest.py`

**주요 기능**:
- `_discover_split_strategies()`: `BACKTEST_RESULTS_DIR` 하위에서 `split_` 접두사 디렉토리 + `split_summary` 키 존재 여부로 분할 전략 자동 탐색
- 캔들스틱 + 트랜치별 MA 라인 + 상단/하단 밴드 오버레이
- 매수/매도 마커 (트랜치 ID 포함, 트랜치별 색상 구분)
- **트랜치 포커스 뷰**: "전체 보기 (MA 라인만)" / "ma250 포커스" / "ma200 포커스" / "ma150 포커스" 선택 가능. 포커스 모드에서는 해당 트랜치의 MA + 밴드 + 마커만 표시.
- 합산 에쿼티 + 드로우다운 차트 (Plotly)
- 트랜치별 보유수량(position) 차트 + 평균단가(avg_entry_price) 오버레이 (Plotly)
- 합산 요약 지표 + 트랜치별 성과 비교 테이블

---

## 삭제 대상 테스트 (1개)

| 테스트 파일 | 테스트 대상 모듈 |
|---|---|
| `tests/test_split_strategy.py` | `split_strategy.py` |

**테스트 클래스 목록**:

| 클래스 | 테스트 수 | 검증 대상 |
|---|---|---|
| `TestSplitTrancheConfig` | 2 | frozen dataclass 생성 및 불변성 |
| `TestSplitStrategyConfig` | 1 | config 생성 |
| `TestSplitConfigs` | 5 | SPLIT_CONFIGS 불변조건 (weight 합, tranche_id 중복, 상수 사용, 4P 파라미터) |
| `TestRunSplitBacktest` | 9 | 핵심 오케스트레이터 로직 (자본 배분, MA 창 독립성, 에쿼티 컬럼, 현금 포함, 거래 태깅, active_tranches, avg_entry_price) |
| `TestSplitBacktestAdditional` | 5 | 미청산 포지션, 빈 거래 트랜치, 데이터 1회 로딩, 합산 summary, params_json 구조) |

---

## 복원 안내

git history에서 삭제된 파일 복원:

```bash
git show 6f0a9bd2a4feb0f59d564d52cc62ffb98c2e4885 -- src/qbt/backtest/split_strategy.py > split_strategy.py
git show 6f0a9bd2a4feb0f59d564d52cc62ffb98c2e4885 -- scripts/backtest/run_split_backtest.py > run_split_backtest.py
git show 6f0a9bd2a4feb0f59d564d52cc62ffb98c2e4885 -- scripts/backtest/app_split_backtest.py > app_split_backtest.py
git show 6f0a9bd2a4feb0f59d564d52cc62ffb98c2e4885 -- tests/test_split_strategy.py > test_split_strategy.py
```
