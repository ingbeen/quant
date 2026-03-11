# TQQQ 스프레드 모델 검증 폐기 모듈 아카이브

> 삭제일: 2026-03-11
> 근거: Softplus 파라미터 확정 (a=-6.1, b=0.37), 워크포워드 3-Mode 검증 완료
> 계획서: `docs/plans/PLAN_tqqq_spread_lab_cleanup.md`

---

## 삭제 대상 소스 모듈 (2개)

### 1. `src/qbt/tqqq/optimization.py` -- Softplus 파라미터 2-Stage Grid Search 최적화

**목적**: softplus 동적 스프레드 모델의 최적 (a, b) 파라미터를 2-Stage Grid Search로 탐색. 벡터화된 시뮬레이션으로 성능 최적화.

**핵심 함수**:

- `find_optimal_softplus_params()`: 2-Stage Grid Search로 최적 softplus 파라미터 탐색 (Stage 1: 조대 그리드, Stage 2: 정밀 그리드)
- `evaluate_softplus_candidate()`: 단일 softplus (a, b) 후보 평가 (병렬 처리 워커 함수)
- `prepare_optimization_data()`: 최적화에 필요한 데이터 전처리 (기초 자산, 실제 ETF, FFR, Expense 로딩 및 겹치는 기간 추출)
- `_precompute_daily_costs_vectorized()`: 벡터화된 일일 비용 계산
- `_simulate_prices_vectorized()`: 벡터화된 가격 시뮬레이션
- `_build_monthly_spread_map_from_dict()`: 딕셔너리 기반 월별 spread map 생성

**의존성**: `simulation.py`(core)의 `calculate_metrics_fast`, `validate_ffr_coverage` 사용

**폐기 사유**: Softplus 파라미터 확정 (a=-6.1, b=0.37). 전체기간 2-Stage Grid Search 완료 후 재탐색 불필요.

---

### 2. `src/qbt/tqqq/walkforward.py` -- 워크포워드 검증 (과최적화 진단)

**목적**: 워크포워드 방식으로 softplus 동적 스프레드 모델의 out-of-sample 성능을 평가. 60개월 학습 / 1개월 테스트 윈도우 방식, 연속(stitched) RMSE, 금리 구간별 RMSE 분해, 고정 (a,b) 과최적화 진단.

**핵심 함수**:

- `run_walkforward_validation()`: 워크포워드 검증 (60개월 Train, 1개월 Test)
- `calculate_stitched_walkforward_rmse()`: 워크포워드 결과를 연속 시뮬레이션한 RMSE 계산
- `calculate_fixed_ab_stitched_rmse()`: 고정 (a,b) 아웃오브샘플 RMSE 계산
- `calculate_rate_segmented_rmse()`: 금리 구간별 RMSE 분해
- `run_fixed_ab_walkforward()`: 고정 (a,b) 워크포워드 실행
- `calculate_rate_segmented_from_stitched()`: stitched 결과에서 금리 구간별 RMSE 계산
- `_local_refine_search()`: 로컬 정밀 탐색 (직전 월 최적값 주변)
- `_simulate_stitched_periods()`: 연속 기간 시뮬레이션

**의존성**: `simulation.py`(core) + `optimization.py` 사용

**폐기 사유**: 워크포워드 3-Mode 검증 완료 (동적/b고정/완전고정). 과최적화 진단 결론 도출 후 재검증 불필요.

---

## 삭제 대상 스크립트 (3개)

### 1. `scripts/tqqq/spread_lab/generate_rate_spread_lab.py`

**쓰임새**: 일별 비교 데이터와 금리 데이터를 로드하여 월별 집계 후 금리-오차 관계 분석용 CSV 3개 생성 (monthly, summary, model).
**선행**: `generate_daily_comparison.py` 실행 (tqqq_daily_comparison.csv 생성)
**후행**: `tqqq_rate_spread_lab_monthly.csv`, `tqqq_rate_spread_lab_summary.csv`, `tqqq_rate_spread_lab_model.csv` 저장
**비즈니스 로직 의존**: `analysis_helpers.py` (save_monthly_features, save_summary_statistics, build_model_dataset, save_model_csv)

### 2. `scripts/tqqq/spread_lab/tune_softplus_params.py`

**쓰임새**: 2-Stage Grid Search로 최적 Softplus (a, b) 파라미터를 탐색하여 튜닝 결과 CSV와 정적 spread 시계열 CSV 저장.
**선행**: 데이터 CSV 존재 (QQQ, TQQQ, FFR, Expense Ratio)
**후행**: `tqqq_softplus_tuning.csv`, `tqqq_softplus_spread_series_static.csv` 저장
**비즈니스 로직 의존**: `optimization.py` (find_optimal_softplus_params), `analysis_helpers.py` (save_static_spread_series)

### 3. `scripts/tqqq/spread_lab/validate_walkforward.py`

**쓰임새**: 3가지 모드(동적/b고정/완전고정) 워크포워드 검증을 순차 실행하여 과최적화 정량적 진단.
**선행**: `tune_softplus_params.py` 실행 (tqqq_softplus_tuning.csv 필요)
**후행**: 워크포워드 결과 CSV 6개 (각 모드별 결과 + 요약) 저장
**비즈니스 로직 의존**: `walkforward.py` (run_walkforward_validation, calculate_stitched_walkforward_rmse 등), `analysis_helpers.py` (save_walkforward_results, save_walkforward_summary)

---

## analysis_helpers.py에서 삭제되는 함수 (8개)

| 함수 | 목적 | 호출처 (삭제됨) |
|---|---|---|
| `add_rolling_features()` | rolling correlation 컬럼 생성 (12개월 윈도우) | `generate_rate_spread_lab.py` |
| `build_model_dataset()` | 모델용 DF 생성 (영문 컬럼, schema_version 포함) | `generate_rate_spread_lab.py` |
| `save_monthly_features()` | 월별 피처 CSV 저장 (한글 헤더, 4자리 라운딩) | `generate_rate_spread_lab.py` |
| `save_summary_statistics()` | 요약 통계 CSV 저장 (Level/Delta/CrossValidation) | `generate_rate_spread_lab.py` |
| `save_model_csv()` | 모델용 CSV 저장 (영문 헤더, schema_version 포함) | `generate_rate_spread_lab.py` |
| `save_walkforward_results()` | 워크포워드 결과 DataFrame CSV 저장 | `validate_walkforward.py` |
| `save_walkforward_summary()` | 워크포워드 요약 통계 CSV 저장 | `validate_walkforward.py` |
| `save_static_spread_series()` | 정적 spread 시계열 CSV 저장 | `tune_softplus_params.py` |

**삭제 사유**: 모든 호출처(스크립트 3개)가 삭제되므로 불필요.

**유지 함수** (app_rate_spread_lab.py 또는 simulation.py에서 사용):

- `calculate_signed_log_diff_from_cumulative_returns()`: simulation.py에서 사용
- `calculate_daily_signed_log_diff()`: prepare_monthly_data 내부 사용
- `aggregate_monthly()`: prepare_monthly_data 내부 사용
- `prepare_monthly_data()`: app_rate_spread_lab.py에서 사용
- `validate_integrity()`: simulation.py에서 사용
- `add_rate_change_lags()`: app_rate_spread_lab.py에서 사용

---

## 삭제 대상 테스트 (2개)

| 테스트 파일 | 테스트 대상 모듈 |
|---|---|
| `tests/test_tqqq_optimization.py` | `optimization.py` |
| `tests/test_tqqq_walkforward.py` | `walkforward.py` |

---

## 삭제 대상 결과 CSV (3개, 앱 미사용)

| CSV 파일 | 생성 스크립트 |
|---|---|
| `storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_monthly.csv` | `generate_rate_spread_lab.py` |
| `storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_summary.csv` | `generate_rate_spread_lab.py` |
| `storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_model.csv` | `generate_rate_spread_lab.py` |

**유지 CSV** (앱에서 로드):

- `tqqq_softplus_tuning.csv` (튜닝 결과)
- `tqqq_softplus_spread_series_static.csv` (정적 spread 시계열)
- `tqqq_rate_spread_lab_walkforward.csv` + `_summary.csv` (동적 워크포워드)
- `tqqq_rate_spread_lab_walkforward_fixed_b.csv` + `_summary.csv` (b 고정)
- `tqqq_rate_spread_lab_walkforward_fixed_ab.csv` + `_summary.csv` (완전 고정)

---

## 복원 안내

향후 재검증이 필요한 경우 git history에서 삭제된 스크립트/모듈을 복원할 수 있다.
