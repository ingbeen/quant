# 레버리지 ETF 시뮬레이션 도메인 가이드

> 이 문서는 `src/qbt/tqqq/` 패키지의 레버리지 ETF 시뮬레이션 도메인에 대한 가이드입니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../../../CLAUDE.md)를 참고하세요.

## 도메인 목적

레버리지 ETF 시뮬레이션 도메인은 기초 자산 데이터로부터 레버리지 상품의 가격을 모델링하고,
실제 데이터와 비교하여 비용 모델의 정확도를 검증합니다.
QQQ(기초 자산)로부터 TQQQ(3배 레버리지 ETF)를 재현하는 것이 주요 사용 사례입니다.

---

## 모듈 구성

### 1. types.py

레버리지 ETF 시뮬레이션 도메인의 TypedDict 정의를 제공합니다.

주요 타입:

- `ValidationMetricsDict`: `calculate_validation_metrics()` 반환 타입 (검증 지표)
- `SoftplusCandidateDict`: softplus 후보 평가 결과 (ValidationMetricsDict 상속)
- `SimulationCacheDict`: 병렬 처리 시 WORKER_CACHE 데이터 구조
- `WalkforwardSummaryDict`: `run_walkforward_validation()` 반환 요약 통계

### 2. constants.py

레버리지 ETF 시뮬레이션 도메인 전용 상수를 정의합니다.

주요 상수 카테고리:

- 경로 및 스펙 설정 (데이터 파일, 결과 파일, 레버리지 상품 스펙)
- 비용 모델 파라미터 (기본값, 그리드 서치 범위, 검증 임계값)
- 데이터 컬럼 및 키 정의 (CSV 컬럼명, 출력 레이블, 딕셔너리 키)

### 3. data_loader.py

TQQQ 도메인 전용 데이터 로딩 및 월별 데이터 조회 함수를 제공합니다.

주요 함수:

데이터 로딩:

- `load_ffr_data`: 연방기금금리(FFR) 월별 데이터 로딩
- `load_expense_ratio_data`: TQQQ 운용비율 월별 데이터 로딩
- `load_comparison_data`: 일별 비교 CSV 파일 로딩 및 검증

월별 데이터 딕셔너리 생성 및 조회 (simulation.py, analysis_helpers.py에서 공유):

- `create_monthly_data_dict`: 월별 데이터 DataFrame을 딕셔너리로 변환 (제네릭)
- `lookup_monthly_data`: 특정 날짜의 월별 데이터 값을 딕셔너리에서 조회 (제네릭, fallback 지원)
- `create_ffr_dict`: FFR DataFrame을 딕셔너리로 변환
- `lookup_ffr`: FFR 값 조회 (최대 2개월 fallback)
- `create_expense_dict`: Expense Ratio DataFrame을 딕셔너리로 변환
- `lookup_expense`: Expense Ratio 값 조회 (최대 12개월 fallback)

DATE 컬럼 형식: `"yyyy-mm"` 문자열 (datetime.date 객체가 아님)

### 4. simulation.py

레버리지 ETF 시뮬레이션 엔진을 제공합니다.

주요 함수:

- `simulate`: 기초 자산 데이터로부터 레버리지 ETF 가격 시뮬레이션
- `find_optimal_softplus_params`: 2-Stage Grid Search로 최적 softplus 파라미터 탐색
- `calculate_validation_metrics`: 시뮬레이션 결과와 실제 데이터 비교 및 오차 분석
- `extract_overlap_period`: 기초 자산과 실제 레버리지 ETF의 겹치는 기간 추출
- `run_walkforward_validation`: 워크포워드 검증 (60개월 Train, 1개월 Test)

### 5. analysis_helpers.py

금리-오차 관계 분석을 위한 계산, 집계, 검증, CSV 저장 함수를 제공합니다.

주요 함수:

계산/집계:

- `calculate_signed_log_diff_from_cumulative_returns`: 누적수익률로부터 signed 로그차이 계산
- `calculate_daily_signed_log_diff`: 일일수익률로부터 일일 증분 signed 로그오차 계산
- `aggregate_monthly`: 일별 데이터를 월별로 집계하고 금리 데이터와 매칭
- `validate_integrity`: abs(signed)와 abs 컬럼의 무결성 검증

피처 생성:

- `add_rate_change_lags`: 금리 변화 lag 컬럼 생성 (dr_lag1, dr_lag2)
- `add_rolling_features`: rolling correlation 컬럼 생성 (12개월 윈도우 기본)
- `build_model_dataset`: 모델용 DF 생성 (영문 컬럼, schema_version 포함)

CSV 저장:

- `save_monthly_features`: 월별 피처 CSV 저장 (한글 헤더, 4자리 라운딩)
- `save_summary_statistics`: 요약 통계 CSV 저장 (Level/Delta/CrossValidation)
- `save_model_csv`: 모델용 CSV 저장 (영문 헤더, schema_version 포함)

Fail-fast 정책: 결과를 신뢰할 수 없게 만드는 문제 발견 시 ValueError를 raise하여 즉시 중단

### 6. lookup_spread.py

룩업테이블 스프레드 모델을 제공합니다.

softplus 모델과 달리 함수 형태를 가정하지 않고, TQQQ 실제 수익률에서 스프레드를 역산하여
금리 구간별로 집계한 룩업테이블을 사용합니다.

주요 함수:

- `calculate_realized_spread`: QQQ/TQQQ 수익률에서 실현 스프레드 역산
- `build_lookup_table`: 금리 구간별 스프레드 테이블 생성 (mean/median)
- `lookup_spread_from_table`: 테이블에서 스프레드 조회 (빈 구간 시 인접 구간 fallback)
- `build_monthly_spread_map_from_lookup`: FundingSpreadSpec 호환 월별 스프레드 맵 생성
- `evaluate_lookup_combination`: 단일 (bin_width, stat_func) 조합의 인샘플 RMSE 평가

### 7. visualization.py

Plotly 기반 차트 생성 함수를 제공합니다.

주요 함수:

- `create_price_comparison_chart`: 실제 종가 vs 시뮬레이션 종가 라인 차트
- `create_daily_return_diff_histogram`: 일일수익률 절대차이 히스토그램
- `create_cumulative_return_diff_chart`: 누적배수 로그차이 라인 차트
- `create_level_chart`: 금리 수준 vs 오차 수준 산점도
- `create_delta_chart`: 금리 변화 vs 오차 변화 산점도

---

## 도메인 규칙

### 1. 시뮬레이션 규칙

일일 리밸런싱 모델:

- 매일 목표 레버리지 배율로 포지션 재조정
- 기초 자산의 일일 수익률에 배율 적용
- 복리 효과 반영 (전일 가격 기준으로 누적)

레버리지 배율:

- 목표 레버리지 배율: `DEFAULT_LEVERAGE_MULTIPLIER = 3.0`
- 일일 수익률에 배율 적용: `leveraged_return = underlying_return * leverage - daily_cost`

### 2. 비용 구조 (동적 비용 모델)

자금 조달 비용:

```
funding_spread = softplus(a + b * FFR_pct)  # 기본값: a=-6.1, b=0.37
일일 자금 조달 비용 = (FFR + funding_spread) * (leverage - 1) / TRADING_DAYS_PER_YEAR
```

- funding_spread는 softplus 모델로 금리에 따라 동적 결정 (과최적화 검증 완료)
- 기본 파라미터: `DEFAULT_SOFTPLUS_A = -6.1`, `DEFAULT_SOFTPLUS_B = 0.37`
- 레버리지 차입 비율: `leverage - 1` (예: 3배 레버리지 -> 2배 차입)
- 금리는 월별 FFR 데이터 사용 (년-월 기준 조회)

운용 비용:

```
일일 운용 비용 = expense_ratio(date) / TRADING_DAYS_PER_YEAR
```

- 데이터 소스: `storage/etc/tqqq_net_expense_ratio_monthly.csv`
- 월별로 실제 운용비율을 동적으로 적용

총 비용:

```
총 일일 비용 = 일일 자금 조달 비용 + 일일 운용 비용
```

### 3. 데이터 요구사항

기초 자산 데이터: OHLCV, 날짜순 정렬, 결측치 없음

금리 데이터 (FFR):

- 형식: `DATE` (yyyy-mm 문자열), `VALUE` (0~1 비율)
- 검증: 최근 데이터와의 시간 차이 `MAX_FFR_MONTHS_DIFF` (2개월) 이내

운용비율 데이터 (Expense Ratio):

- 형식: `DATE` (yyyy-mm 문자열), `VALUE` (0~1 비율)
- 검증: 최근 데이터와의 시간 차이 `MAX_EXPENSE_MONTHS_DIFF` (12개월) 이내

### 4. 검증 임계값

- 금리 데이터 갭: `MAX_FFR_MONTHS_DIFF = 2` (초과 시 ValueError)
- 무결성 허용 오차: `INTEGRITY_TOLERANCE = 1e-6` (0.000001%)

---

## 핵심 계산 로직

### 누적배수 로그차이 계산

목적: 스케일에 무관한 추적오차 측정

수식:

```
M_actual(t) = actual_close(t) / actual_close(0)  # 누적 자산배수
M_sim(t) = simul_close(t) / simul_close(0)
로그차이(%) = ln(M_actual(t) / M_sim(t)) * 100
```

오차 지표:

- RMSE: 경로 전체 추적 품질 평가 (최적화 기준, 낮을수록 우수)
- 평균/최대: 보조 지표

---

## CSV 파일 형식

### tqqq_daily_comparison.csv

경로: `storage/results/tqqq_daily_comparison.csv`

주요 컬럼: 날짜, 종가(실제/시뮬), 일일수익률, 누적수익률, 누적배수 로그차이(abs/signed)

용도: 대시보드 시각화, 금리-오차 관계 분석 (softplus 동적 스프레드 모델 사용)

### tqqq_rate_spread_lab_monthly.csv

경로: `storage/results/spread_lab/tqqq_rate_spread_lab_monthly.csv`

주요 컬럼: 연월, 금리수준, 금리변화, 월말누적오차, 월간오차변화, 일일오차월합, lag1, lag2

용도: 사람이 읽기 쉬운 한글 헤더 CSV, 분석 결과 확인

### tqqq_rate_spread_lab_model.csv

경로: `storage/results/spread_lab/tqqq_rate_spread_lab_model.csv`

주요 컬럼 (영문):

- `month`: 연월 (yyyy-mm)
- `schema_version`: 스키마 버전 (현재 "1.0")
- `rate_level_pct`: 금리 수준 (%)
- `rate_change_pct`: 금리 변화 (%)
- `rate_change_lag1_pct`, `rate_change_lag2_pct`: 금리 변화 lag 1, 2
- `error_eom_pct`: 월말 누적 오차 (%)
- `error_change_pct`: 월간 오차 변화 (%)
- `error_daily_sum_pct`: 일일 오차 월합 (%)
- `cv_diff_pct`: 교차검증 차이 (error_change - error_daily_sum)
- `rolling_corr_level`, `rolling_corr_delta`, `rolling_corr_lag1`, `rolling_corr_lag2`: 12개월 rolling correlation

용도: AI/ML 모델링, 프로그래밍 API 연동 (영문 헤더로 일관성 유지)

---

## Streamlit 앱

### app_daily_comparison.py

TQQQ 시뮬레이션 일별 비교 대시보드

- 가격 비교 차트: 실제 TQQQ vs 시뮬레이션
- 오차 분석 차트: 히스토그램, 시계열 오차 추이

---

## CLI 스크립트

### 스프레드 모델 검증 (scripts/tqqq/spread_lab/)

스프레드 모델 확정 후 재검증이 필요한 경우에만 사용하는 스크립트입니다.
연산 집약적인 작업은 CLI 스크립트로 분리하여 spawn 경고 없이 실행 가능합니다.
Streamlit 앱은 CLI 스크립트 실행 결과 CSV를 로드하여 시각화합니다.

- `generate_rate_spread_lab.py`: 금리-오차 관계 분석용 CSV 3개 생성 (monthly, summary, model)
- `tune_softplus_params.py`: Softplus 동적 스프레드 모델 파라미터 튜닝 (2-Stage Grid Search)
- `validate_walkforward.py`: 워크포워드 검증 (60개월 Train, 1개월 Test)
- `validate_walkforward_fixed_b.py`: b 고정 워크포워드 검증 (b 고정, a만 최적화)
- `validate_walkforward_fixed_ab.py`: 완전 고정 (a,b) 워크포워드 검증 (과최적화 진단)
- `app_rate_spread_lab.py`: 금리-오차 관계 분석 연구용 앱 (시각화 전용, 단일 흐름: 오차분석→튜닝→과최적화진단→상세분석)

---

## 테스트 커버리지

**주요 테스트 파일**: `tests/test_tqqq_simulation.py`, `tests/test_tqqq_analysis_helpers.py`, `tests/test_tqqq_visualization.py`

**테스트 범위**:

- 일일 비용 계산 로직
- 레버리지 수익률 적용 및 복리 효과
- 누적배수 로그차이 계산
- Softplus 파라미터 최적화
- 엣지 케이스 (FFR 갭 초과, 빈 데이터)
