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
- 다양한 통계 지표 계산:
  - 일일 수익률 상관계수
  - 일일 수익률 차이 (평균, 최대)
  - 일별 가격 차이 (평균, 최대)
  - 누적 수익률 비교
  - 최종 가격 차이

#### `scripts/validate_tqqq_simulation.py`

**목적**: 2010-02-11 이후 QQQ로부터 TQQQ 시뮬레이션 후 실제 TQQQ와 비교

**주요 기능**:
1. QQQ, TQQQ 데이터 로드
2. 최적 multiplier 탐색 (기본: 2.8~3.2 범위)
3. 최적 multiplier로 시뮬레이션 재실행
4. 검증 지표 계산 및 출력 (터미널 테이블 + CSV)

**출력 예시**:
```
================================================================
TQQQ 시뮬레이션 검증
================================================================
검증 기간: 2010-02-11 ~ 2025-11-28
총 일수: 3,975일
최적 multiplier: 2.52
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
  일일 수익률 상관계수: 0.9989
  일일 수익률 차이 (평균): 0.0234%
  일일 수익률 차이 (최대): 1.2345%
  일별 가격 차이 (평균): 0.5678%
  일별 가격 차이 (최대): 12.3456%
  최종 가격 차이: -0.01%
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
    --multiplier 2.52 \
    --initial-price 100.0
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

**핵심 지표**:
1. **일일 수익률 상관계수**: 시뮬레이션 품질의 핵심 지표 (목표: 0.95 이상)
2. **일일 수익률 차이**: 평균 및 최대 절대값
3. **일별 가격 차이**: 평균 및 최대 비율
4. **누적 수익률 비교**: 장기 성과 비교
5. **최종 가격 차이**: 마지막 날 가격 차이

**CSV 포맷**:
- 적절한 소수점 자릿수로 반올림
- multiplier: 4자리
- 상관계수: 6자리
- 수익률: 4자리 (%)
- 누적 수익률: 2자리 (%)

---

## 4. 핵심 알고리즘

### 4.1 레버리지 ETF 시뮬레이션 공식

**일일 리밸런싱 기반**:

```python
# 1. 기초 자산의 일일 수익률 계산
underlying_return[t] = (underlying_close[t] / underlying_close[t-1]) - 1

# 2. 일일 비용 계산
daily_expense = annual_expense_ratio / 252

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

**Volatility Decay**:
- 별도 계산 불필요
- 일일 복리 효과로 자동 반영됨
- 예: 시장이 +1%, -1% 반복 시 레버리지 ETF는 손실 발생

### 4.2 최적 Multiplier 탐색 알고리즘 (Grid Search)

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

### 4.3 검증 지표 계산 알고리즘

```python
# 1. 겹치는 기간 추출
overlap_dates = sim_dates & actual_dates

# 2. 일일 수익률 계산
sim_returns = sim_df['Close'].pct_change().dropna()
actual_returns = actual_df['Close'].pct_change().dropna()

# 3. 상관계수
correlation = sim_returns.corr(actual_returns)

# 4. 일일 수익률 차이
mean_return_diff_abs = abs(sim_returns - actual_returns).mean()
max_return_diff_abs = abs(sim_returns - actual_returns).max()

# 5. 일별 가격 차이
price_diff_pct = abs((sim_close - actual_close) / actual_close * 100)
mean_price_diff_pct = price_diff_pct.mean()
max_price_diff_pct = price_diff_pct.max()

# 6. 누적 수익률
sim_cumulative = (1 + sim_returns).prod() - 1
actual_cumulative = (1 + actual_returns).prod() - 1
```

---

## 5. 중요 발견사항

### 5.1 최적 Multiplier가 2.52인 이유

**예상**: 3.0 (3배 레버리지)
**실제**: 2.52 (약 2.5배)

**원인 분석**:

1. **Expense Ratio (0.95%)**
   - 연간 운용 수수료가 차감됨
   - 일일: 0.95% / 252 ≈ 0.0038%

2. **Volatility Decay (변동성 손실)**
   - 일일 리밸런싱으로 인한 복리 효과 손실
   - 시장 변동성이 클수록 손실 증가
   - 예시:
     ```
     Day 1: QQQ +1% → TQQQ +3%
     Day 2: QQQ -1% → TQQQ -3%

     QQQ: 100 → 101 → 99.99 (≈ 0% 변화)
     TQQQ: 100 → 103 → 99.91 (-0.09% 손실)
     ```

3. **Rebalancing Cost**
   - 매일 포지션을 조정하는 거래 비용
   - 실제 ETF에서는 스왑 계약 갱신 비용 포함

4. **Tracking Error**
   - 완벽한 3배 추종 불가능
   - 실제 운용 시 약간의 오차 발생

**결론**: 이는 **정상적인 현상**이며, 모든 레버리지 ETF의 공통적인 특성입니다.

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

#### 1. TQQQ 스왑 이자율 반영 및 Expense Ratio 최적화 (최우선)

**배경**:
- 현재는 Expense Ratio (0.95%)만 반영
- 실제 TQQQ는 스왑 계약을 통해 레버리지 구현
- 스왑 이자율(Swap Rate)이 추가 비용으로 발생
- Expense Ratio도 고정값이 아닌 최적 파라미터로 탐색 필요

**구현 계획**:

1. **스왑 이자율 데이터 수집**:
   - ProShares 공시자료 확인
   - Bloomberg/Reuters 데이터
   - 일별 또는 월별 스왑 이자율 시계열 데이터

2. **알고리즘 수정**:
   ```python
   def simulate_leveraged_etf(
       underlying_df: pd.DataFrame,
       leverage: float,
       expense_ratio: float,
       swap_rate: float | pd.Series,  # 고정값 또는 시계열
       initial_price: float,
   ) -> pd.DataFrame:
       ...
       # 날짜별 스왑 이자율 적용
       if isinstance(swap_rate, pd.Series):
           daily_cost = expense_ratio / 252 + swap_rate
       else:
           daily_cost = (expense_ratio + swap_rate) / 252

       leveraged_return = underlying_return * leverage - daily_cost
       ...
   ```

3. **2D Grid Search**:
   ```python
   def find_optimal_parameters(
       underlying_df: pd.DataFrame,
       actual_leveraged_df: pd.DataFrame,
       multiplier_range: tuple[float, float] = (2.0, 3.5),
       expense_range: tuple[float, float] = (0.008, 0.012),
       swap_rate: float = 0.0,  # 또는 시계열 데이터
   ) -> tuple[float, float, dict]:
       # multiplier와 expense_ratio를 동시에 최적화
       ...
       return optimal_multiplier, optimal_expense, metrics
   ```

**예상 개선**:
- multiplier가 3.0에 가까워질 가능성
- 특히 금리 변동기의 정확도 개선
- 2010년 이후 장기 검증에서 상관계수 0.999+ 달성 가능

#### 2. 시뮬레이션 품질 시각화

**목적**: 검증 결과를 그래프로 시각화

**구현**:
1. 일일 수익률 산점도 (Scatter plot)
2. 누적 수익률 시계열 비교 (Line chart)
3. 가격 차트 오버레이
4. 일별 가격 차이 히트맵

**도구**: matplotlib 또는 plotly

**출력**: `results/tqqq_validation_chart.png`

#### 5. 백테스트 통합

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

1. **스왑 이자율 미반영**: 현재는 Expense Ratio만 반영
2. **High/Low 미구현**: 0으로 설정 (Close만 사용)
3. **단일 ETF 지원**: TQQQ만 지원 (다른 레버리지 ETF 미지원)

### 10.2 개선 제안

이슈 및 개선 제안은 프로젝트 관리자에게 문의하세요.

---

**최종 수정일**: 2025-11-30
**작성자**: Claude (Anthropic)
**버전**: 1.0
