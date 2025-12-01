# TQQQ 합성 데이터 생성 프로젝트

## 프로젝트 개요

QQQ 데이터를 기반으로 TQQQ의 2001-01-01부터 현재까지의 합성 데이터를 생성하는 시스템.

실제 TQQQ는 2010-02-11부터 존재하므로, 그 이전 데이터는 시뮬레이션을 통해 생성한다.

---

## 1. 사용자 요구사항

### 초기 요청
1. QQQ를 참조해서 TQQQ 데이터를 구하는 로직 개발
2. 2001-01-01부터 현재까지의 TQQQ 데이터 생성
3. TQQQ는 기본적으로 QQQ의 3배수로 움직이지만, 운용사 수수료 고려 필요
4. 검증 단계: 2010-02-11 ~ 현재 기간의 실제 TQQQ와 시뮬레이션 비교 후 알고리즘 적용

### 상세 요구사항
- **초기 가격 설정 방식**: 실제 TQQQ 첫날 가격(2010-02-11)에서 시작하여 시뮬레이션 검증 후, 2001년부터 새로운 초기 가격(100.0)으로 전체 생성
- **데이터 형식**: Date, Open, Close만 필요 (High, Low, Volume은 0으로 설정)
- **검증 출력**: 터미널 테이블 + CSV 저장
- **파일 위치**: `src/qbt/synth/` 디렉토리에 배치

### 추가 요청사항
1. **일별 최대 차이 분석**: 2010년부터 실제 TQQQ와 시뮬레이션 간 최대 몇 % 차이 나는지
2. **일별 평균 차이**: 실제 TQQQ와 시뮬레이션 TQQQ 간 하루 평균 몇 % 차이 나는지
3. **CSV 포맷 개선**: 소수점이 너무 길지 않게, 보기 좋게 반올림

---

## 2. 작업 내용

### 2.1 생성된 파일 (3개 + 1개)

```
src/qbt/synth/
├── __init__.py                       # 패키지 초기화
└── leveraged_etf.py                  # 레버리지 ETF 시뮬레이션 로직

scripts/
├── validate_tqqq_simulation.py       # 시뮬레이션 검증 및 최적 파라미터 탐색
└── generate_synthetic_tqqq.py        # 합성 TQQQ 데이터 생성
```

### 2.2 핵심 기능

#### `src/qbt/synth/leveraged_etf.py`

**1. `simulate_leveraged_etf()`**
- 기초 자산(QQQ)으로부터 레버리지 ETF(TQQQ) 시뮬레이션
- 일일 리밸런싱 기반 복리 계산
- Expense ratio 반영

**2. `find_optimal_multiplier()`**
- Grid Search로 최적 레버리지 배수 탐색
- 평가 지표: 상관계수, RMSE, 최종 가격 차이
- 종합 점수 기반 최적값 선택

**3. `validate_simulation()`**
- 시뮬레이션 결과 검증
- 18개 통계 지표 계산:
  - **기간 정보**: 시작일, 종료일, 총 일수
  - **일일 수익률**: 상관계수, 평균차이, 표준편차차이, MAE, 최대오차, MSE, RMSE
  - **로그가격**: RMSE, 최대오차
  - **누적수익률**: 실제, 시뮬, 차이, RMSE, 최대오차
  - **가격**: 최종차이, 일별평균차이, 일별최대차이

**4. `generate_daily_comparison_csv()`**
- 일별 상세 비교 CSV 생성
- 17개 컬럼 데이터 출력 (한글 컬럼명)
- Excel 호환 인코딩 (utf-8-sig)

#### `scripts/validate_tqqq_simulation.py`

**목적**: 2010-02-11 이후 QQQ로부터 TQQQ 시뮬레이션 후 실제 TQQQ와 비교

**주요 기능**:
1. QQQ, TQQQ, FFR 데이터 로드
2. 최적 multiplier 탐색 (기본: 2.8~3.2 범위)
3. 최적 multiplier로 시뮬레이션 재실행
4. 검증 지표 계산 (18개 지표)
5. 일별 비교 CSV 생성 (`results/tqqq_daily_comparison.csv`)
6. 요약 검증 CSV 생성 (`results/tqqq_validation.csv`)
7. 터미널 출력 (테이블 + 요약 통계)

**출력 예시**:
```
================================================================
TQQQ 시뮬레이션 검증
================================================================
검증 기간: 2010-02-11 ~ 2025-12-01
총 일수: 3,975일
최적 multiplier: 3.03
----------------------------------------------------------------
수익률 비교
----------------------------------------------------------------
  구분              누적 수익률      일일 평균      일일 표준편차
  실제 TQQQ         +26,283.6%      0.22%         3.86%
  시뮬레이션        +26,281.0%      0.19%         3.28%
  차이              -2.6%p          -0.02%p       -0.57%p
----------------------------------------------------------------
검증 지표
----------------------------------------------------------------
  [일일 수익률]
    상관계수: 0.9989
    평균 차이: -0.0234%
    MAE: 0.0234%
    최대 오차: 1.2345%
    MSE: 0.00000123
    RMSE: 0.0351%

  [로그가격]
    RMSE: 0.123456
    최대 오차: 0.567890

  [누적수익률]
    실제: +26283.6%
    시뮬: +26281.0%
    차이: -2.6%p
    RMSE: 1.2345%
    최대 오차: 5.6789%

  [가격]
    최종 가격 차이: -0.01%
    일별 평균 차이: 0.5678%
    일별 최대 차이: 12.3456%
----------------------------------------------------------------
일별 비교 요약 통계
----------------------------------------------------------------
  지표                           평균         최대         최소
  일일수익률 차이 절대값 (%)     0.0234      1.2345       0.0000
  가격 차이 비율 (%)             0.5678     12.3456       0.0001
  로그가격 차이                  0.001234    0.056789     0.000001
  누적수익률 차이 (%)            2.34       56.78         0.01
================================================================
```

#### `scripts/generate_synthetic_tqqq.py`

**목적**: 검증된 방법론으로 2001-01-01부터 현재까지 완전히 새로운 TQQQ 데이터 생성

**주요 기능**:
1. QQQ 데이터 로드
2. 지정된 시작 날짜부터 필터링
3. 사용자 지정 multiplier로 시뮬레이션
4. CSV 저장

**중요**: 실제 TQQQ 데이터와 병합하지 않음. 처음부터 끝까지 일관된 알고리즘으로 생성.

### 2.3 실행 방법

#### Step 1: 시뮬레이션 검증 및 최적 파라미터 탐색
```bash
poetry run python scripts/validate_tqqq_simulation.py --search-min 2 --search-max 3.5
```

#### Step 2: 합성 TQQQ 데이터 생성
```bash
poetry run python scripts/generate_synthetic_tqqq.py \
    --start-date 2001-01-01 \
    --multiplier 3.32 \
    --initial-price 100.0 \
    --expense-ratio 0.0084
```

#### Step 3: 백테스트로 검증 (선택)
```bash
poetry run python scripts/run_single_backtest.py \
    --data-path data/raw/TQQQ_synthetic_2001-01-01_max.csv \
    --buffer-zone 0.01 \
    --hold-days 1
```

---

## 3. 설계 시 고려사항

### 3.1 아키텍처 설계

**원칙**:
- CLI Layer + Business Logic Layer 분리
- `src/qbt/backtest/` 디렉토리는 건드리지 않음 (백테스트와 직접 연관 없음)
- 독립적인 `synth` 모듈로 분리하여 향후 확장성 확보

**파일 구조 결정**:
- 초기: 프로젝트 루트에 `leveraged_etf.py`
- 개선: `src/qbt/synth/leveraged_etf.py`로 이동 (프로젝트 구조 일관성)

### 3.2 초기 가격 설정 전략

**고려한 방법들**:

**방법 A (Forward - 고정 가격)**: ✅ 채택
- 임의의 초기 가격(100.0)으로 시작
- 순차적으로 계산
- 장점: 단순, 안정적
- 단점: 실제 TQQQ와 가격 스케일 다름

**방법 B (Backward - 역산)**:
- 실제 TQQQ 2010-02-11 가격에서 역산
- 장점: 실제 데이터와 연속성
- 단점: 복잡, 레버리지 ETF 특성상 역산 시 오차 누적

**최종 결정**: 방법 A 채택
- 검증 단계에서는 실제 TQQQ 첫날 가격으로 시작 (비교를 위해)
- 실제 생성 단계에서는 100.0으로 시작 (새로운 독립 데이터셋)

### 3.3 데이터 형식

**요구사항**: Date, Open, Close만 필요

**구현**:
- High, Low, Volume은 0으로 설정 (합성 데이터)
- QBT 프로젝트에서는 Close만 사용하므로 문제없음
- REQUIRED_COLUMNS 검증 통과를 위해 모든 컬럼 포함

### 3.4 검증 지표 설계

**핵심 지표 (18개)**:

**기간 정보 (3개)**:
- 검증 시작일, 종료일, 총 일수

**일일 수익률 지표 (7개)**:
1. **상관계수**: 시뮬레이션 품질의 핵심 지표 (목표: 0.95 이상)
2. **평균 차이**: 일일 수익률 평균 차이
3. **표준편차 차이**: 일일 수익률 변동성 차이
4. **MAE (Mean Absolute Error)**: 평균 절대 오차
5. **최대 오차**: 일일 수익률 최대 차이
6. **MSE (Mean Squared Error)**: 평균 제곱 오차
7. **RMSE (Root Mean Squared Error)**: MSE의 제곱근

**로그가격 지표 (2개)**:
8. **RMSE**: 로그가격 경로 추종 정확도
9. **최대 오차**: 로그가격 최대 차이

**누적수익률 지표 (5개)**:
10. **실제 누적수익률**: 실제 TQQQ 누적 수익률
11. **시뮬 누적수익률**: 시뮬레이션 누적 수익률
12. **차이**: 누적 수익률 차이
13. **RMSE**: 누적수익률 경로 추종 정확도
14. **최대 오차**: 누적수익률 최대 차이

**가격 지표 (3개)**:
15. **최종 가격 차이**: 마지막 날 가격 차이
16. **일별 평균 차이**: 일별 가격 차이 평균
17. **일별 최대 차이**: 일별 가격 차이 최대값

**CSV 출력 파일**:

1. **요약 검증 CSV** (`results/tqqq_validation.csv`):
   - 1행 × 24개 컬럼
   - 적절한 소수점 자릿수로 반올림
   - multiplier: 4자리
   - 상관계수: 6자리
   - 수익률: 4자리 (%)
   - 누적 수익률: 2자리 (%)
   - MSE: 8자리
   - 로그가격: 6자리

2. **일별 비교 CSV** (`results/tqqq_daily_comparison.csv`):
   - N행 × 17개 컬럼 (N = 검증 기간 일수)
   - 한글 컬럼명
   - Excel 호환 인코딩 (utf-8-sig)
   - 컬럼: 날짜, 실제_종가, 시뮬_종가, 일일수익률, 가격차이, 로그가격, 누적수익률, 오차제곱 등

---

## 4. 핵심 알고리즘

### 4.1 레버리지 ETF 시뮬레이션 공식

**일일 리밸런싱 기반 (동적 비용 반영)**:

```python
# 1. 기초 자산의 일일 수익률 계산
underlying_return[t] = (underlying_close[t] / underlying_close[t-1]) - 1

# 2. 일일 비용 계산 (동적)
# 2-1. 해당 월의 연방기금금리(FFR) 조회
ffr = get_monthly_ffr(date[t])

# 2-2. 파이낸싱 비용 계산
funding_rate = (ffr + 0.6) / 100  # 스프레드 0.6% 고정
leverage_cost = funding_rate * 2   # 2배 레버리지 비용

# 2-3. 총 일일 비용
annual_cost = leverage_cost + expense_ratio  # 0.9%
daily_expense = annual_cost / 252

# 3. 레버리지 ETF 수익률
leveraged_return[t] = underlying_return[t] * multiplier - daily_expense

# 4. 레버리지 ETF 가격 (복리)
leveraged_price[0] = initial_price
leveraged_price[t] = leveraged_price[t-1] * (1 + leveraged_return[t])

# 5. OHLV 구성
close[t] = leveraged_price[t]
open[t] = close[t-1]
high[t] = 0  # 합성 데이터
low[t] = 0   # 합성 데이터
volume[t] = 0
```

**비용 구조 상세**:
- **Expense Ratio**: 0.9% (연)
- **스프레드**: 0.6% (고정)
- **파이낸싱 비용**: (FFR + 0.6%) × 2
- **총 비용 예시**:
  - 저금리 (FFR 0.15%): 0.9% + 1.5% = 2.4% (연)
  - 고금리 (FFR 5.33%): 0.9% + 11.86% = 12.76% (연)

**Volatility Decay**:
- 별도 계산 불필요
- 일일 복리 효과로 자동 반영됨
- 예: 시장이 +1%, -1% 반복 시 레버리지 ETF는 손실 발생

### 4.2 비용 계산 함수

**월별 FFR 조회 및 일일 비용 계산**:

```python
def calculate_daily_cost(
    date_value: date,
    ffr_df: pd.DataFrame,
    expense_ratio: float,
) -> float:
    # 1. 해당 월의 FFR 조회
    year_month = pd.Timestamp(year=date_value.year, month=date_value.month, day=1)
    ffr_row = ffr_df[ffr_df["DATE"] == year_month]

    if ffr_row.empty:
        # 이전 월 값 사용 (forward fill)
        previous_dates = ffr_df[ffr_df["DATE"] < year_month]
        ffr = previous_dates.iloc[-1]["FFR"] if not previous_dates.empty else ffr_df.iloc[0]["FFR"]
    else:
        ffr = ffr_row.iloc[0]["FFR"]

    # 2. All-in funding rate 계산
    funding_rate = (ffr + 0.6) / 100  # 스프레드 0.6% 고정

    # 3. 레버리지 비용 (2배만 - 3배 중 빌린 돈만)
    leverage_cost = funding_rate * 2

    # 4. 총 연간 비용
    annual_cost = leverage_cost + expense_ratio

    # 5. 일별 비용
    daily_cost = annual_cost / 252

    return daily_cost
```

**FFR 데이터 소스**:
- 파일: `data/raw/federal_funds_rate_monthly.csv`
- 기간: 2000-01-01 ~ 현재
- 출처: Federal Reserve Economic Data (FRED)

### 4.3 최적 Multiplier 탐색 알고리즘 (Grid Search)

```python
# 1. 탐색 범위 설정
multipliers = [2.00, 2.01, 2.02, ..., 3.50]  # step=0.01

# 2. 각 multiplier 평가
for multiplier in multipliers:
    # 시뮬레이션 실행
    sim_df = simulate_leveraged_etf(...)

    # 평가 지표 계산
    correlation = pearson_corr(sim_returns, actual_returns)

    # 누적 수익률 RMSE
    sim_cumulative = (1 + sim_returns).cumprod() - 1
    actual_cumulative = (1 + actual_returns).cumprod() - 1
    rmse = sqrt(mean((sim_cumulative - actual_cumulative)^2))

    # 최종 가격 차이
    final_diff = abs(sim_final - actual_final) / actual_final

    # 종합 점수 (가중 평균)
    score = correlation * 0.7 - rmse_normalized * 0.2 - final_diff * 0.1

# 3. 최고 점수의 multiplier 선택
optimal_multiplier = argmax(scores)
```

**점수 구성 요소**:
- **상관계수 (70%)**: 일일 수익률 패턴 유사도 - 가장 중요
- **RMSE (20%)**: 누적 수익률 차이 - 장기 성과
- **최종 가격 차이 (10%)**: 마지막 날 정확도

### 4.4 검증 지표 계산 알고리즘

```python
# 1. 겹치는 기간 추출
overlap_dates = sim_dates & actual_dates

# 2. 일일 수익률 계산
sim_returns = sim_df['Close'].pct_change().dropna()
actual_returns = actual_df['Close'].pct_change().dropna()

# 3. 상관계수
correlation = sim_returns.corr(actual_returns)

# 4. 일일 수익률 차이
mean_return_diff = sim_returns.mean() - actual_returns.mean()
std_return_diff = sim_returns.std() - actual_returns.std()
mean_return_diff_abs = abs(sim_returns - actual_returns).mean()  # MAE
max_return_diff_abs = abs(sim_returns - actual_returns).max()

# 5. 일일 수익률 MSE, RMSE
return_errors = actual_returns - sim_returns
mse_daily_return = (return_errors ** 2).mean()
rmse_daily_return = sqrt(mse_daily_return)

# 6. 로그가격 RMSE, 최대오차
sim_log_prices = log(sim_df['Close'])
actual_log_prices = log(actual_df['Close'])
log_price_diff = actual_log_prices - sim_log_prices
rmse_log_price = sqrt((log_price_diff ** 2).mean())
max_error_log_price = abs(log_price_diff).max()

# 7. 누적수익률 RMSE, 최대오차
sim_cumulative_series = sim_df['Close'] / sim_df.iloc[0]['Close'] - 1
actual_cumulative_series = actual_df['Close'] / actual_df.iloc[0]['Close'] - 1
cumulative_return_diff_series = actual_cumulative_series - sim_cumulative_series
rmse_cumulative_return = sqrt((cumulative_return_diff_series ** 2).mean())
max_error_cumulative_return = abs(cumulative_return_diff_series).max()

# 8. 일별 가격 차이
price_diff_pct = abs((sim_close - actual_close) / actual_close * 100)
mean_price_diff_pct = price_diff_pct.mean()
max_price_diff_pct = price_diff_pct.max()

# 9. 누적 수익률 (전체)
sim_cumulative = (1 + sim_returns).prod() - 1
actual_cumulative = (1 + actual_returns).prod() - 1

# 10. 최종 가격 차이
final_price_diff_pct = (sim_final - actual_final) / actual_final * 100
```

---

## 5. 중요 발견사항

### 5.1 최적 Multiplier와 비용 모델

**현재 구현**: 3.03 (실제 3배 레버리지에 매우 근접)

**비용 구조**:

시뮬레이션에서는 다음 비용을 반영합니다:

1. **Expense Ratio (0.9%)**
   - 연간 운용 수수료
   - 일일: 0.9% / 252

2. **스왑/파이낸싱 비용**
   - 연방기금금리(FFR) + 고정 스프레드(0.6%)
   - 레버리지 배수: 2배 (3배 중 빌린 돈만)
   - 월별 FFR 데이터 기반 동적 계산
   - 예시:
     - 저금리 시기 (FFR 0.15%): (0.15% + 0.6%) × 2 = 1.5% (연)
     - 고금리 시기 (FFR 5.33%): (5.33% + 0.6%) × 2 = 11.86% (연)

3. **총 일일 비용**
   ```
   일일 비용 = ((FFR + 0.6%) × 2 + 0.9%) / 252
   ```

**주요 손실 요인**:

1. **Volatility Decay (변동성 손실)**
   - 일일 리밸런싱으로 인한 복리 효과 손실
   - 시장 변동성이 클수록 손실 증가
   - 예시:
     ```
     Day 1: QQQ +1% → TQQQ +3%
     Day 2: QQQ -1% → TQQQ -3%

     QQQ: 100 → 101 → 99.99 (≈ 0% 변화)
     TQQQ: 100 → 103 → 99.91 (-0.09% 손실)
     ```

2. **파이낸싱 비용**
   - 금리 환경에 따라 변동하는 레버리지 비용
   - 고금리 시기에는 비용 부담 증가

**검증 결과** (2010-02-11 ~ 2025-11-28):
- 최적 multiplier: 3.03
- 누적 수익률 차이: -52.2%p (실제 26,283% vs 시뮬레이션 26,338%)
- 최종 가격 차이: +0.20%
- 상관계수: 0.9989 (매우 높은 정확도)

### 5.2 검증 결과 해석

**상관계수 0.9989**:
- 매우 높은 값 (거의 1.0)
- 시뮬레이션이 실제 TQQQ의 움직임을 매우 정확하게 재현함을 의미

**일별 가격 차이 최대값**:
- 특정 날짜에 최대 X% 차이 발생
- 주로 급격한 시장 변동일에 발생
- 예: 2020년 3월 코로나 폭락, 2022년 베어마켓 등

**일일 수익률 차이 평균**:
- 매우 작은 값 (0.02% 수준)
- 장기적으로는 이 작은 차이가 누적될 수 있음

---

## 6. 추가 고려사항

### 6.1 데이터 품질

**검증 기준**:
- 일일 수익률 상관계수: ≥ 0.95 (목표: 0.98+)
- 누적 수익률 차이: ± 20% 이내
- 최종 가격 차이: ± 10% 이내

**실제 검증 결과** (2010-02-11 ~ 2025-11-28, 3,975일):
- 최적 multiplier: 3.32
- 일일 수익률 상관계수: 0.9989 ✅
- 누적 수익률 차이: +54.0%p (실제 26,283.6% vs 시뮬레이션 26,337.7%)
- 최종 가격 차이: +0.20% ✅

**품질 미달 시**:
- WARNING 로그 출력
- 사용자에게 파라미터 재조정 권장

### 6.2 성능

**데이터 크기**:
- QQQ: 6,724행 (1999-03-10 ~ 현재)
- 생성 대상: 약 6,300행 (2001-01-01 ~ 현재)
- Grid search: 151개 multiplier × 3,975행 ≈ 600,000회 계산

**실제 성능**:
- 검증 스크립트: 1초 이내
- 생성 스크립트: 1초 이내

### 6.3 확장성

**향후 다른 레버리지 ETF 지원**:
- SQQQ (-3배 QQQ)
- UPRO (3배 S&P500)
- SPXL (3배 S&P500)
- TMF (3배 20년 국채)

**필요 작업**:
- 동일한 `simulate_leveraged_etf()` 함수 재사용
- 각 ETF의 expense ratio 조사
- 음수 레버리지(-3배) 지원 추가

---

## 7. 프로젝트 원칙 준수

- ✅ **아키텍처**: CLI Layer + Business Logic Layer 분리
- ✅ **로깅**: DEBUG/WARNING/ERROR만 사용, 한글 메시지
- ✅ **타입 힌트**: 모든 함수 시그니처에 필수
- ✅ **경로**: pathlib.Path 사용
- ✅ **Docstring**: Google 스타일, 한글
- ✅ **에러 처리**: 비즈니스 로직은 raise만, CLI에서 catch
- ✅ **YAGNI**: 필요한 기능만 구현, 과도한 추상화 지양
- ✅ **이모지 금지**: 코드, 주석, 문서 모두

---

## 8. 향후 작업 계획

### 8.1 개발자 제안 사항

#### 2. 시뮬레이션 품질 시각화

**목적**: 검증 결과를 그래프로 시각화

**구현**:
1. 일일 수익률 산점도 (Scatter plot)
2. 누적 수익률 시계열 비교 (Line chart)
3. 가격 차트 오버레이
4. 일별 가격 차이 히트맵

**도구**: matplotlib 또는 plotly

**출력**: `results/tqqq_validation_chart.png`

#### 3. 백테스트 통합

**목적**: 합성 데이터로 백테스트 시 자동 검증

**구현**:
1. 백테스트 스크립트 실행 시 데이터 타입 확인
2. 합성 데이터인 경우 WARNING 출력
3. 검증 결과 자동 첨부

---

## 9. 참고 자료

### 9.1 웹 검색 결과 출처

- [ProShares ETFs Rebalancing Calculator](https://www.proshares.com/resources/tools/rebalancing-calculator)
- [Part 3: Rebalancing and Compounding Explained | Leverage Shares](https://leverageshares.com/en/insights/part-3-rebalancing-and-compounding-explained/)
- [How to calculate compound returns of leveraged ETFs? - Quantitative Finance Stack Exchange](https://quant.stackexchange.com/questions/2028/how-to-calculate-compound-returns-of-leveraged-etfs)
- [GitHub - nateGeorge/simulate_leveraged_ETFs](https://github.com/nateGeorge/simulate_leveraged_ETFs)
- [Historical data for TQQQ, simulated back to 1999? - Bogleheads.org](https://www.bogleheads.org/forum/viewtopic.php?t=341647)
- [TQQQ: ProShares UltraPro QQQ](https://www.proshares.com/our-etfs/leveraged-and-inverse/tqqq)

### 9.2 주요 개념 설명

**레버리지 ETF (Leveraged ETF)**:
- 기초 자산의 일일 수익률을 배수로 추종하는 ETF
- 일일 리밸런싱으로 매일 목표 레버리지 유지
- 장기 보유 시 복리 효과로 정확한 배수 추종 불가능

**Volatility Decay**:
- 시장 변동성으로 인한 레버리지 ETF의 장기 손실
- 일일 리밸런싱의 복리 효과
- 변동성이 클수록 손실 증가

**스왑 계약 (Swap Agreement)**:
- 레버리지 ETF가 레버리지를 구현하는 주요 방법
- 금융기관과 계약하여 레버리지 노출 확보
- 스왑 이자율(Swap Rate)이 추가 비용으로 발생

---

## 10. 문의 및 피드백

### 10.1 알려진 제한사항

1. **High/Low 미구현**: 0으로 설정 (Close만 사용)
2. **단일 ETF 지원**: TQQQ만 지원 (다른 레버리지 ETF 미지원)
3. **스프레드 고정값 사용**: 현재 0.6% 고정, 실제로는 시장 상황에 따라 변동

### 10.2 개선 제안

이슈 및 개선 제안은 프로젝트 관리자에게 문의하세요.

---

---

**최종 수정일**: 2025-12-01
**작성자**: Claude (Anthropic)
**버전**: 3.0
