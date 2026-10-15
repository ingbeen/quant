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
- 비용 모델 파라미터 (기본값)
- 데이터 컬럼 및 키 정의 (CSV 컬럼명, 딕셔너리 키)
- 분석 파라미터 (Rolling 상관 창 `ROLLING_CORR_WINDOW_MONTHS`)

### 2. data_loader.py

TQQQ 도메인 전용 데이터 로딩 및 월별 데이터 조회 함수를 제공합니다.

주요 함수:

데이터 로딩:

- `load_monthly_data`: 월별 데이터(연방기금금리 · TQQQ 운용비율) 파일 로딩. 값 검사는 딕셔너리를 만들 때 한다
- `load_comparison_data`: 일별 비교 CSV 파일 로딩 및 검증

월별 데이터 딕셔너리 생성 및 조회 (simulation.py, analysis_helpers.py에서 공유):

- `_create_monthly_data_dict`: 월별 데이터 DataFrame을 딕셔너리로 변환 (제네릭, private)
- `_lookup_monthly_data`: 특정 날짜의 월별 데이터 값을 딕셔너리에서 조회 (제네릭, fallback 지원, private)
- `create_ffr_dict`: FFR DataFrame을 딕셔너리로 변환
- `lookup_ffr`: FFR 값 조회 (최대 `MAX_FFR_MONTHS_DIFF` fallback)
- `create_expense_dict`: Expense Ratio DataFrame을 딕셔너리로 변환
- `lookup_expense`: Expense Ratio 값 조회 (최대 `MAX_EXPENSE_MONTHS_DIFF` fallback)
- `lookup_funding_spread`: funding spread 값 조회 (최대 `MAX_FFR_MONTHS_DIFF` fallback)
- `build_extended_expense_dict`: 운용비율 딕셔너리를 1999-01부터 확장 (합성 데이터 생성용, `DEFAULT_PRE_LISTING_EXPENSE_RATIO` 적용)

DATE 컬럼 형식: `"yyyy-mm"` 문자열 (datetime.date 객체가 아님)

### 3. simulation.py

레버리지 ETF 시뮬레이션 엔진(core)을 제공합니다.

주요 타입:

- `ValidationMetricsDict`: `calculate_validation_metrics()` 반환 타입 (검증 지표 TypedDict)

주요 함수:

- `simulate`: 기초 자산 데이터로부터 레버리지 ETF 가격 시뮬레이션
- `calculate_validation_metrics`: 시뮬레이션 결과와 실제 데이터 비교 및 오차 분석
- `_calculate_daily_cost`: 일일 비용(자금 조달 + 운용) 계산 (private)
- `_compute_softplus_spread`: softplus 모델로 funding spread 계산 (private)
- `build_monthly_spread_map`: FFR 데이터로 월별 spread 딕셔너리 생성

`simulate` 는 월별 값(FFR · 운용비율 · spread)을 `{"YYYY-MM": 값}` 딕셔너리로 받고, 둘째 거래일부터 날마다 조회한다 — 허용 개월 수를 넘게 비면 그 날짜에서 ValueError 다.

참고: `extract_overlap_period`는 `utils/data_loader.py`에 위치.

### 4. analysis_helpers.py

금리-오차 관계 분석을 위한 계산 · 집계 함수를 제공합니다.

주요 함수:

계산/집계:

- `calculate_signed_log_diff_from_cumulative_returns`: 누적수익률로부터 signed 로그차이 계산
- `calculate_daily_signed_log_diff`: 일일수익률로부터 일일 증분 signed 로그오차 계산
- `aggregate_monthly`: 일별 데이터를 월별로 집계하고 금리 데이터와 매칭

Fail-fast 정책: 결과를 신뢰할 수 없게 만드는 문제 발견 시 ValueError를 raise하여 즉시 중단

### 5. spread_lab_helpers.py

Spread Lab 앱(`app_rate_spread_lab.py`) 전용 분석 함수를 제공합니다.
`analysis_helpers.py`의 핵심 계산 함수를 활용하여 월별 데이터를 준비합니다.

주요 함수:

- `prepare_monthly_data`: 일별 비교 데이터를 월별로 집계 (일일 증분 계산 + aggregate_monthly + sum_daily_m 합치기). 월이 Rolling 상관 창 + 1 개월보다 적으면 멈춘다

### 6. visualization.py

Plotly 기반 차트 생성 함수를 제공합니다.

주요 함수:

- `create_price_comparison_chart`: 실제 종가 vs 시뮬레이션 종가 라인 차트
- `create_daily_return_diff_histogram`: 일일수익률 절대차이 히스토그램
- `create_cumulative_return_diff_chart`: 누적배수 로그차이 라인 차트
- `create_level_scatter_chart`: 금리 수준 vs 오차 수준 산점도
- `create_level_timeseries_chart`: 금리 수준과 오차 수준 시계열 차트
- `create_delta_scatter_chart`: 금리 변화 vs 오차 변화 산점도
- `create_rolling_correlation_chart`: rolling correlation 시계열 차트

---

## 도메인 규칙

### 1. 시뮬레이션 규칙

일일 리밸런싱 모델:

- 매일 목표 레버리지 배율로 포지션 재조정
- 기초 자산의 일일 수익률에 배율 적용
- 복리 효과 반영 (전일 가격 기준으로 누적)

레버리지 배율:

- 목표 레버리지 배율: `DEFAULT_LEVERAGE_MULTIPLIER`
- 일일 수익률에 배율 적용: `leveraged_return = underlying_return * leverage - daily_cost`

### 2. 비용 구조 (동적 비용 모델)

자금 조달 비용:

```
funding_spread = softplus(a + b * FFR_pct)  # a, b 기본값은 아래 상수 참조
일일 자금 조달 비용 = (FFR + funding_spread) * (leverage - 1) / TRADING_DAYS_PER_YEAR
```

- funding_spread는 softplus 모델로 금리에 따라 동적 결정 — 고정 스프레드(0.0034)는 고금리 구간에서 비용을 과소 반영해 시뮬레이션이 실제보다 높게 나온다. 근거는 고정 스프레드로 만든 일별 비교의 「금리 수준 vs 월말 누적 오차」 추세선 우상향이다 `[실측] 2026-02-08`(커밋 `8b43280`). 그 앱의 차트는 softplus 를 적용한 일별 비교로 그려 남은 편향을 본다
- 기본 파라미터: `DEFAULT_SOFTPLUS_A`, `DEFAULT_SOFTPLUS_B` — 스프레드 랩 튜닝의 전체기간 RMSE 최소값이다. 그 앱의 워크포워드 RMSE 는 과최적화 여부를 가리지 못한다(이유는 앱 docstring)
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
- 검증: 최근 데이터와의 시간 차이 `MAX_FFR_MONTHS_DIFF` 이내

운용비율 데이터 (Expense Ratio):

- 형식: `DATE` (yyyy-mm 문자열), `VALUE` (0~1 비율)
- 검증: 최근 데이터와의 시간 차이 `MAX_EXPENSE_MONTHS_DIFF` 이내

두 파일 모두 값이 빈 칸 · inf 이거나 상한(`data_loader.py` 의 `MAX_FFR_VALUE` · `MAX_EXPENSE_VALUE`) 이상이면 ValueError 다 — 손으로 고치는 파일이라 % 로 적은 값(설명서 표기 그대로의 운용비율 0.82 등)이 들어올 수 있다. 하한은 없다(음수 금리를 그대로 쓴다).

### 4. 검증 임계값

- 금리 데이터 갭: `MAX_FFR_MONTHS_DIFF` (초과 시 ValueError)

---

## 핵심 계산 로직

### 누적배수 로그차이 지표 (2종)

두 지표는 동일한 누적배수 정의를 공유하지만, 용도가 다르다.

공통 정의:

```
M(t) = Close(t) / Close(0)   # 첫날 종가 기준 누적 자산배수
```

#### 1) 추적오차 크기 (abs)

- 계산: 아래 signed 의 절댓값 (`simulation.calculate_validation_metrics` 가 지표와 일별 비교 CSV 의 abs 열에 쓴다)
- 수식: `abs_log_diff(%) = |ln(M_actual(t) / M_sim(t))| × 100`
- 용도: RMSE 최적화, 절대 오차 크기 측정 (부호 무관)
- 비고: 절댓값이므로 분자/분모 순서를 바꿔도 결과가 동일하다.

#### 2) 방향성 (signed)

- 함수: `analysis_helpers.calculate_signed_log_diff_from_cumulative_returns`
- 수식: `signed_log_diff(%) = 100 × ln(M_sim / M_real)`
- 용도: 금리-오차 회귀 분석 등 부호가 의미를 갖는 분석
- 부호 해석:
  - 양수: 시뮬레이션이 실제보다 높음(오버슈트)
  - 음수: 시뮬레이션이 실제보다 낮음(언더슈트)
- 비고: 부호 의미를 고정하기 위해 `M_sim / M_real` 순서를 반드시 준수한다.

오차 지표:

- RMSE: 경로 전체 추적 품질 평가 (최적화 기준, 낮을수록 우수)
- 평균/최대: 보조 지표

---

## CSV 파일 형식

### tqqq_daily_comparison.csv

경로: `storage/results/tqqq/tqqq_daily_comparison.csv`

주요 컬럼: 날짜, 종가(실제/시뮬), 일일수익률, 누적수익률, 누적배수 로그차이(abs/signed)

용도: 대시보드 시각화, 금리-오차 관계 분석 (softplus 동적 스프레드 모델 사용). 대시보드 설명은 `scripts/CLAUDE.md` · 각 앱 docstring

---

## 테스트 커버리지

tqqq 도메인 테스트 파일은 [tests/qbt/](../../../tests/qbt/) 디렉토리의 `test_tqqq_*.py` 파일들에 위치한다. 파일 목록은 변경 빈도가 높으므로 본 문서에 나열하지 않으며, 디렉토리를 직접 참조할 것.

**테스트 범위** (계약/불변조건 단위):

- 일일 비용 계산 로직
- 레버리지 수익률 적용 및 복리 효과
- 누적배수 로그차이 계산
- FFR/Expense 딕셔너리 생성, 조회, 갭 검증
- 엣지 케이스 (FFR 갭 초과, 빈 데이터)
