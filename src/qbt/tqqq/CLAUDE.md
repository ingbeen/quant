# 레버리지 ETF 시뮬레이션 도메인 가이드

> 이 문서는 `src/qbt/tqqq/` 패키지의 레버리지 ETF 시뮬레이션 도메인에 대한 가이드입니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../../../CLAUDE.md)를 참고하세요.

## 도메인 목적

레버리지 ETF 시뮬레이션 도메인은 기초 자산 데이터로부터 레버리지 상품의 가격을 모델링하고,
실제 데이터와 비교하여 비용 모델의 정확도를 검증합니다.
QQQ(기초 자산)로부터 TQQQ(3배 레버리지 ETF)를 재현하는 것이 주요 사용 사례입니다.

---

## 모듈 구성

### 1. constants.py

레버리지 ETF 시뮬레이션 도메인 전용 상수를 정의합니다.

주요 상수 카테고리:

- 경로 및 스펙 설정 (데이터 파일, 결과 파일, 레버리지 상품 스펙)
- 비용 모델 파라미터 (기본값, 그리드 서치 범위, 검증 임계값)
- 데이터 컬럼 및 키 정의 (CSV 컬럼명, 출력 레이블, 딕셔너리 키)

### 2. data_loader.py

TQQQ 도메인 전용 데이터 로딩 함수를 제공합니다.

주요 함수:

- `load_ffr_data`: 연방기금금리(FFR) 월별 데이터 로딩
- `load_expense_ratio_data`: TQQQ 운용비율 월별 데이터 로딩
- `load_comparison_data`: 일별 비교 CSV 파일 로딩 및 검증

DATE 컬럼 형식: `"yyyy-mm"` 문자열 (datetime.date 객체가 아님)

### 3. simulation.py

레버리지 ETF 시뮬레이션 엔진을 제공합니다.

주요 함수:

- `simulate`: 기초 자산 데이터로부터 레버리지 ETF 가격 시뮬레이션
- `find_optimal_cost_model`: 그리드 서치로 최적 비용 모델 파라미터 탐색
- `calculate_validation_metrics`: 시뮬레이션 결과와 실제 데이터 비교 및 오차 분석
- `extract_overlap_period`: 기초 자산과 실제 레버리지 ETF의 겹치는 기간 추출

### 4. analysis_helpers.py

금리-오차 관계 분석을 위한 계산, 집계, 검증 함수를 제공합니다.

주요 함수:

- `calculate_signed_log_diff_from_cumulative_returns`: 누적수익률로부터 signed 로그차이 계산
- `calculate_daily_signed_log_diff`: 일일수익률로부터 일일 증분 signed 로그오차 계산
- `aggregate_monthly`: 일별 데이터를 월별로 집계하고 금리 데이터와 매칭
- `validate_integrity`: abs(signed)와 abs 컬럼의 무결성 검증

Fail-fast 정책: 결과를 신뢰할 수 없게 만드는 문제 발견 시 ValueError를 raise하여 즉시 중단

### 5. visualization.py

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
일일 자금 조달 비용 = (FFR + funding_spread) * (leverage - 1) / TRADING_DAYS_PER_YEAR
```

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

- Funding Spread 탐색 범위: `DEFAULT_SPREAD_RANGE`
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

용도: 대시보드 시각화, 금리-오차 관계 분석

### tqqq_validation.csv

경로: `storage/results/tqqq_validation.csv`

주요 컬럼: funding_spread, 종가, 누적수익률, 누적배수로그차이(RMSE/평균/최대)

용도: 최적 비용 모델 파라미터 선정

### tqqq_rate_spread_lab_monthly.csv

경로: `storage/results/tqqq_rate_spread_lab_monthly.csv`

주요 컬럼: 연월, 금리수준, 금리변화, 월말누적오차, 월간오차변화, 일일오차월합

용도: AI/모델링, 금리-오차 관계 분석

---

## Streamlit 앱

### streamlit_daily_comparison.py

TQQQ 시뮬레이션 일별 비교 대시보드

- 가격 비교 차트: 실제 TQQQ vs 시뮬레이션
- 오차 분석 차트: 히스토그램, 시계열 오차 추이

### streamlit_rate_spread_lab.py

금리-오차 관계 분석 연구용 앱

- Level 탭: 금리 수준 vs 월말 누적 signed 오차
- Delta 탭: 금리 변화 vs 오차 변화 (Lag 옵션: 0/1/2 개월)
- 교차검증 탭: de_m vs sum_daily_m 차이 분석

캐시 정책: 서버 기동 시 1회만 데이터 빌드, CSV 1회 저장

---

## 테스트 커버리지

**주요 테스트 파일**: `tests/test_tqqq_simulation.py`, `tests/test_tqqq_analysis_helpers.py`, `tests/test_tqqq_visualization.py`

**테스트 범위**:

- 일일 비용 계산 로직
- 레버리지 수익률 적용 및 복리 효과
- 누적배수 로그차이 계산
- 비용 모델 최적화 (그리드 서치)
- 엣지 케이스 (FFR 갭 초과, 빈 데이터)
