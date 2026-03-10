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
