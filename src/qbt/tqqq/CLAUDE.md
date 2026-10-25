# 레버리지 ETF 시뮬레이션 도메인 가이드

> 이 문서는 `src/qbt/tqqq/` 패키지의 레버리지 ETF 시뮬레이션 도메인에 대한 가이드입니다.

## 도메인 목적

레버리지 ETF 시뮬레이션 도메인은 기초 자산 데이터로부터 레버리지 상품의 가격을 모델링하고,
실제 데이터와 비교하여 비용 모델의 정확도를 검증합니다.
QQQ(기초 자산)로부터 TQQQ(3배 레버리지 ETF)를 재현하는 것이 주요 사용 사례입니다.

---

## 모듈 지도

함수 · 시그니처 · 열 이름은 각 모듈 docstring 이 정본입니다.

- `constants.py` — 도메인 상수 (데이터 · 결과 경로, 레버리지 스펙, 비용 모델 기본값, 일별 비교 CSV 열 이름)
- `data_loader.py` — 월별 데이터(연방기금금리 · 운용비율)와 일별 비교 CSV 로딩, 월별 값 딕셔너리 생성 · 조회
- `simulation.py` — 시뮬레이션 엔진(`simulate`)과 실제 대비 검증 지표, softplus 스프레드
- `analysis_helpers.py` — 금리-오차 관계 분석의 계산 · 월별 집계 (signed 로그차이)
- `spread_lab_helpers.py` — 스프레드 랩 앱 전용 월별 데이터 준비
- `visualization.py` — 일별 비교 · 스프레드 랩 앱의 Plotly 차트

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

금리 데이터 (FFR) · 운용비율 데이터 (Expense Ratio):

- 형식: `DATE` (`"yyyy-mm"` 문자열 — `datetime.date` 객체가 아니다), `VALUE` (0~1 비율)
- 날짜마다 그 달 값을 조회하고, 없으면 허용 개월 수(`MAX_FFR_MONTHS_DIFF` · `MAX_EXPENSE_MONTHS_DIFF`) 안의 이전 달 값을 쓴다 — 그보다 비면 ValueError

두 파일 모두 값이 빈 칸 · inf 이거나 상한(`data_loader.py` 의 `MAX_FFR_VALUE` · `MAX_EXPENSE_VALUE`) 이상이면 ValueError 다 — 손으로 고치는 파일이라 % 로 적은 값(설명서 표기 그대로의 운용비율 0.82 등)이 들어올 수 있다. 하한은 없다(음수 금리를 그대로 쓴다).

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
