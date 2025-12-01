
# TQQQ 시뮬레이션/검증 리팩토링 프롬프트

다음 세 개의 파일을 기준으로 TQQQ 시뮬레이션 & 검증 로직을 리팩토링해 주세요.

- `src/qbt/synth/leveraged_etf.py`
- `scripts/validate_tqqq_simulation.py`
- `TQQQ.md`

이 프롬프트는 **기존 구현**과 **이미 실행된 검증 결과**를 바탕으로,
아래의 변경 요구사항을 모두 반영하도록 하는 “통합 스펙 문서”입니다.

---

## 0. 목표

1. **“실제 TQQQ 구조”에 더 가깝게** 모델링하기
   - multiplier(레버리지 배수)는 3.0으로 고정
   - 대신 **비용 모델(FFR + 스프레드 + expense ratio)** 를 캘리브레이션

2. 검증 기준/로그/CSV를 정리해서
   - **핵심 지표 위주로 간결하게**
   - 사람이 봐도 바로 이해할 수 있게 만들기

3. `TQQQ.md` 문서의
   - 잘못된 숫자(예전 최적 multiplier 등)
   - 애매한 표현(누적 수익률 기준 등)을
   - **현재 코드/설계에 맞게 업데이트**하기

---

## 1. 현재 구현 요약 (참고용)

> 이 섹션은 현재 코드/문서를 이해하기 위한 요약입니다.  
> 실제 구현 시에는 아래 “변경 요구사항”에 따라 수정합니다.

### 1.1 `leveraged_etf.py` 요약

- `calculate_daily_cost(date_value, ffr_df, expense_ratio)`
  - FFR 월별 데이터에서 해당 월 금리를 조회
  - `funding_rate = (FFR + 0.6) / 100`
  - 레버리지 비용: `funding_rate * 2` (3배 중 2배만 빌린 돈)
  - 총 연간 비용: `annual_cost = leverage_cost + expense_ratio`
  - 일별 비용: `annual_cost / 252`
- `simulate_leveraged_etf(underlying_df, leverage, expense_ratio, initial_price, ffr_df)`
  - `underlying_return = Close.pct_change()`
  - 일별 레버리지 수익률: `underlying_return * leverage - daily_cost`
  - 전일 가격 * (1 + 레버리지 수익률) 로 가격 경로 계산
  - O/H/L/V 합성 (Open = 전일 Close, High/Low/Volume = 0)
- `find_optimal_multiplier(...)`
  - 겹치는 기간(2010-02-11~)에서
  - 여러 multiplier를 그리드 서치 (기본 2.8~3.2, step 0.01)
  - 평가 지표:  
    - 일일 수익률 상관계수  
    - 누적 수익률 RMSE  
    - 최종 가격 차이 비율  
  - 위 지표들을 가중합해 **최적 multiplier 하나**만 반환
- `validate_simulation(simulated_df, actual_df)`
  - 기간 정보 + 일일 수익률 + 로그가격 + 누적수익률 + 가격 관련 지표들을 계산
  - `mse_daily_return`, `rmse_daily_return`, `rmse_log_price`, `rmse_cumulative_return` 등 다양한 지표 반환

### 1.2 `validate_tqqq_simulation.py` 요약

- QQQ, TQQQ, FFR CSV 로딩
- `find_optimal_multiplier(...)` 호출 → 최적 multiplier 탐색
- 최적 multiplier로 시뮬 다시 실행
- `validate_simulation(...)` 호출 → 검증 지표 계산
- `tqqq_daily_comparison.csv`, `tqqq_validation.csv` 생성
- 터미널 로그에 검증 결과 테이블/요약 통계 출력

### 1.3 `TQQQ.md` 요약 (문서)

- 프로젝트 개요/요구사항/구현 파일 설명
- “최적 multiplier 3.32” 등 예전 실행 기준 숫자 사용
- 검증 지표를 “18개 지표”라고 설명하지만 실제 코드는 더 많음
- “누적 수익률 차이 ± 20% 이내”라는 기준이 **상대 오차인지, 퍼센트포인트인지** 애매하게 서술됨

---

## 2. 큰 방향 변경 요약

아래는 이번 리팩토링에서 반영해야 할 **핵심 방향**입니다.

1. **multiplier = 3.0 고정**
   - 이제 더 이상 multiplier를 그리드 서치하지 않는다.
   - TQQQ는 “3배 레버리지 ETF”이므로 이 값은 개념적으로 고정하는 것이 자연스럽다.

2. **비용 모델 캘리브레이션 (2D grid search)**
   - FFR 위에 더해지는 **스프레드(funding spread)** 와  
     **운용 보수(expense ratio)** 를 그리드 서치로 찾는다.
   - 예시:
     - funding_spread: 0.4% ~ 0.8% (step 0.01%)
     - expense_ratio: 0.7% ~ 1.1% (step 0.05% 또는 0.01%)

3. **누적 수익률 차이: “상대 오차” 기준으로 변경**
   - 지금은 `(시뮬 누적수익률 - 실제 누적수익률) * 100` (퍼센트포인트)만 보고  
     `|…| > 20` 이면 WARNING.
   - 앞으로는  
     `상대 오차(%) = |시뮬 - 실제| / |실제| * 100`  
     기준으로 “±20% 이내면 OK”로 본다.

4. **최고 전략이 아니라, 상위 10개 전략을 모두 남기기**
   - 단일 best 전략 1개만 쓰는 게 아니라
   - **스코어 기준 상위 10개 전략**을:
     - 로그에 표 형태로 출력
     - `tqqq_validation.csv`에 10행으로 모두 저장

5. **“최고 전략” 스코어는 누적수익률이 아니라 복합 지표로**
   - 누적수익률 자체는 단지 결과일 뿐,  
     “경로가 잘 맞는지”를 보기엔 부족하다.
   - 아래 **중요 지표**들을 조합해 스코어링한다.
     1. 일일 수익률 상관계수 (가장 중요)
     2. 일일 수익률 RMSE (실제 변동성 대비)
     3. 최종 가격 차이 (절대값 %)
     4. 누적 수익률 상대 차이 (%)

6. **요약 통계에서 “최소(min)” 지표는 제거**
   - 일일 오차의 최소값은 대부분 0에 가깝고  
     분석에 크게 도움이 안 되므로 **평균 & 최대만** 남긴다.

7. **MSE 지표는 출력/CSV에서 제거**
   - RMSE만 있어도 충분히 정보가 겹치지 않고 해석이 더 직관적이다.
   - 필요하면 내부에서만 계산/사용 가능하지만  
     로그/CSV에는 **RMSE만 남기고 MSE는 제거**한다.

8. **중요 지표들에 대한 “문장형 요약”을 로그에 추가**
   - 숫자만 나열하는 대신,
   - “상관계수가 0.999라서 일일 패턴이 거의 완벽하게 맞는다” 같은
     **인간이 이해하기 쉬운 설명 로그**를 마지막에 한 번 더 출력한다.

9. **`tqqq_daily_comparison.csv` 슬림화 + 반올림**
   - 컬럼이 너무 많아서 실무에서 보기 어렵다.
   - 핵심 컬럼만 남기고 나머지는 제거.
   - 숫자 소수점도 3~4자리 정도로 반올림해서 저장.

10. **`TQQQ.md` 문서 오류 & 구버전 내용 업데이트**
    - multiplier=3.32, 18개 지표 등의 예전 내용을
      새 구조(3배 고정 + 비용 캘리브레이션, top 10 전략, 상대 오차 기준)로 갱신.

---

## 3. 상세 요구사항 – 코드 레벨 변경

### 3.1 비용 모델 캘리브레이션 (multiplier = 3.0 고정)

#### 3.1.1 `calculate_daily_cost` 시그니처 확장

```python
def calculate_daily_cost(
    date_value: date,
    ffr_df: pd.DataFrame,
    expense_ratio: float,
    funding_spread: float = 0.6,
) -> float:
    ...
    funding_rate = (ffr + funding_spread) / 100
    leverage_cost = funding_rate * 2  # 3배 중 빌린 2배
    annual_cost = leverage_cost + expense_ratio
    daily_cost = annual_cost / 252
    return daily_cost
````

* 기존 0.6을 **하드코딩하지 말고 인자로 받는** 구조로 변경.
* 기본값은 그대로 0.6 유지.

#### 3.1.2 `simulate_leveraged_etf` 에 funding_spread 전달

```python
def simulate_leveraged_etf(
    underlying_df: pd.DataFrame,
    leverage: float,
    expense_ratio: float,
    initial_price: float,
    ffr_df: pd.DataFrame,
    funding_spread: float = 0.6,
) -> pd.DataFrame:
    ...
    daily_cost = calculate_daily_cost(
        current_date,
        ffr_df=ffr_df,
        expense_ratio=expense_ratio,
        funding_spread=funding_spread,
    )
    ...
```

* `leverage` 기본값은 세부 구현에 따라 `3.0`으로 주어도 되고,
  호출 시 항상 3.0을 넘겨도 된다.
  (이번 리팩토링에서 **검증/캘리브레이션 단계에서는 leverage=3.0으로 고정**할 것.)

#### 3.1.3 새로운 캘리브레이션 함수 추가

기존 `find_optimal_multiplier`는 유지하되,
새로운 비용 모델 캘리브레이션용 함수를 추가한다.

```python
def find_optimal_cost_model(
    underlying_df: pd.DataFrame,
    actual_leveraged_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    leverage: float = 3.0,
    spread_range: tuple[float, float] = (0.4, 0.8),
    spread_step: float = 0.01,
    expense_range: tuple[float, float] = (0.0075, 0.0105),
    expense_step: float = 0.0005,
) -> tuple[dict, list[dict]]:
    """
    multiplier는 3.0으로 고정하고,
    funding_spread와 expense_ratio 2D grid search로
    상위 10개 전략을 찾는다.

    Returns:
        best_strategy: dict
        top_strategies: list[dict]  # score 기준 내림차순 상위 10개
    """
```

구현 아이디어:

1. QQQ/TQQQ 겹치는 기간 추출 (기존 `find_optimal_multiplier`와 동일)

2. `initial_price`는 실제 TQQQ 첫날 종가 사용

3. double for-loop:

   ```python
   candidates = []
   for spread in np.arange(spread_range[0], spread_range[1] + 1e-12, spread_step):
       for expense in np.arange(expense_range[0], expense_range[1] + 1e-12, expense_step):
           sim_df = simulate_leveraged_etf(
               underlying_overlap,
               leverage=leverage,
               expense_ratio=expense,
               initial_price=initial_price,
               ffr_df=ffr_df,
               funding_spread=spread,
           )
           metrics = validate_simulation(sim_df, actual_overlap)
           score = compute_strategy_score(metrics)
           candidates.append({**metrics, "funding_spread": spread, "expense_ratio": expense, "leverage": leverage, "score": score})
   ```

4. `candidates`를 `score` 기준 내림차순 정렬

5. `best_strategy = candidates[0]`, `top_strategies = candidates[:10]` 반환

### 3.2 “최고 전략” 스코어 정의

`compute_strategy_score(metrics: dict) -> float` 헬퍼 함수를 별도로 두는 것을 추천.

사용할 핵심 지표:

* `corr = metrics["correlation"]`                  # 일일 수익률 상관계수
* `rmse_daily = metrics["rmse_daily_return"]`      # 일일 수익률 RMSE (소수)
* `std_actual = actual_returns.std()`              # 실제 일일 수익률 표준편차
* `final_price_diff = abs(metrics["final_price_diff_pct"])`  # 최종 가격 차이 절대값 (%)
* `rel_cum_diff = metrics["cumulative_return_relative_diff_pct"]`  # 누적 수익률 상대 차이 (%)

정규화 예시:

```python
rmse_rel = rmse_daily / (std_actual + 1e-12)          # 실제 변동성 대비 RMSE (무차원)
final_diff_norm = final_price_diff / 10.0             # 10% 기준으로 0~1 스케일
rel_cum_norm = rel_cum_diff / 20.0                    # 허용 기준(20%) 대비 스케일
```

스코어 예시(가중합):

```python
score = (
    0.6 * corr
    - 0.25 * rmse_rel
    - 0.10 * final_diff_norm
    - 0.05 * rel_cum_norm
)
```

* 상관계수 가중치(0.6)를 가장 크게 둔다.
* 나머지 항들은 “패널티”처럼 빼는 방식(작을수록 좋은 값).
* 가중치는 이후 실험하면서 조정 가능하지만,
  기본적으로 **“corr가 높고, rmse_rel/최종 가격 차이/누적 수익률 상대 오차가 작은 전략”**이 점수가 높게 나오도록 설계한다.

> 중요: 스코어는 “누적 수익률 크기” 자체가 아니라
> “경로를 얼마나 잘 재현하느냐”에 집중해야 한다.

### 3.3 누적 수익률 “상대 오차” 지표 추가

`validate_simulation` 에서 누적 수익률을 계산할 때,
기존에 있던 값들에 더해서 **상대 오차(%)** 지표를 하나 더 추가한다.

```python
sim_cumulative = ...
actual_cumulative = ...
cumulative_return_diff_pct = (sim_cumulative - actual_cumulative) * 100  # 기존

cumulative_return_relative_diff_pct = (
    abs(sim_cumulative - actual_cumulative)
    / (abs(actual_cumulative) + 1e-12)
    * 100.0
)
```

리턴 딕셔너리에 필드를 추가:

```python
return {
    ...
    "cumulative_return_simulated": sim_cumulative,
    "cumulative_return_actual": actual_cumulative,
    "cumulative_return_diff_pct": cumulative_return_diff_pct,
    "cumulative_return_relative_diff_pct": cumulative_return_relative_diff_pct,
    ...
}
```

### 3.4 품질 체크 로직 수정 (WARNING 조건)

`validate_tqqq_simulation.py`에서 현재는

```python
if abs(validation_results["cumulative_return_diff_pct"]) > 20:
    logger.warning(...)
```

이렇게 되어 있는데, 이를 **상대 오차 기준**으로 바꾼다.

```python
cum_diff_pctp = validation_results["cumulative_return_diff_pct"]
cum_rel_diff_pct = validation_results["cumulative_return_relative_diff_pct"]

logger.debug(
    "    차이: "
    f"{cum_diff_pctp:+.1f}%p "
    f"(실제 대비 {cum_rel_diff_pct:.2f}% 상대 차이)"
)

if cum_rel_diff_pct > 20:
    logger.warning(
        "누적 수익률 상대 차이가 큽니다: "
        f"{cum_rel_diff_pct:.2f}% (권장: ±20% 이내)"
    )
```

* 이렇게 하면 **26,000% vs 26,200%**처럼
  실질적으로 거의 동일한 경우는 WARNING이 뜨지 않는다.

### 3.5 요약 통계에서 “최소” 제거 & MSE 제거

#### 3.5.1 요약 테이블 컬럼 구성

현재 요약 테이블은

* 평균 / 최대 / 최소 3개 컬럼인데,
  **최소(min)**는 거의 항상 의미 있는 정보를 주지 않는다.

변경:

* `지표`, `평균`, `최대` **두 컬럼만** 사용.

```python
columns = [
    ("지표", 30, Align.LEFT),
    ("평균", 12, Align.RIGHT),
    ("최대", 12, Align.RIGHT),
]
```

각 row는 `최소` 컬럼을 삭제하고 두 값만 출력한다.

#### 3.5.2 MSE → 로그/CSV에서 제거

* `validate_simulation` 내부에서 `mse_daily_return`을 아예 제거하거나,
* **리턴은 유지하되**:

  * 로그 출력에서 `MSE` 줄 삭제
  * `tqqq_validation.csv`에서 `일일수익률_MSE` 컬럼 제거

RMSE 지표는 그대로 유지:

* `일일수익률_RMSE_pct`
* `로그가격_RMSE`
* `누적수익률_RMSE_pct`

---

## 4. tqqq_validation.csv 구조 변경 (Top 10 전략)

### 4.1 현재

* 1행 × 여러 컬럼 (단일 최적 multiplier 기준)
* 주요 컬럼:

  * 검증일, 기간, 총일수, 최적_multiplier, expense_ratio
  * 일일 수익률/로그가격/누적수익률/가격 관련 지표들

### 4.2 변경 요구사항

1. **상위 10개 전략 모두 저장**

   * 각 행이 “하나의 전략(=spread + expense_ratio + leverage)”을 나타낸다.
   * `rank` 컬럼(1~10)을 추가한다.

2. 새로운/정리된 컬럼 예시:

필수:

* `rank` (1~10)
* `검증일`
* `검증기간_시작`, `검증기간_종료`, `총일수`
* `leverage` (항상 3.0 예상이지만 명시)
* `funding_spread`
* `expense_ratio`
* `strategy_score`

핵심 성능 지표:

* `일일수익률_상관계수`
* `일일수익률_RMSE_pct`
* `일일수익률_MAE_pct`
* `최종가격_차이_pct`
* `누적수익률_실제_pct`
* `누적수익률_시뮬레이션_pct`
* `누적수익률_차이_pct`       # 퍼센트포인트
* `누적수익률_상대차이_pct`   # 상대 오차(%)
* `로그가격_RMSE`
* `일별가격_평균차이_pct`
* `일별가격_최대차이_pct`

3. 소수점 자릿수 예시:

* 상관계수: 6자리
* 수익률/차이(%): 4자리
* 누적 수익률(%): 2자리
* 로그가격 RMSE: 6자리
* strategy_score: 6자리 정도

4. 쓰기 방식:

* `top_strategies` 리스트를 받아서 `rank`를 붙이고 DataFrame 생성
* 항상 **10행** (혹은 실제 후보가 10개 미만이면 그 수만큼) 저장

---

## 5. tqqq_daily_comparison.csv 슬림화

### 5.1 현재 문제점

* 컬럼 수가 많아서 사람이 보기 부담스럽다.
* 오차 제곱 등 분석용 컬럼이 많아, 실무에서 바로 쓰기엔 과한 수준.
* 소수점 자릿수도 지나치게 길다.

### 5.2 남길 컬럼 제안

다음 정도의 컬럼만 남기고 나머지는 제거한다.

1. 날짜 & 가격

* `날짜`
* `실제_종가`
* `시뮬_종가`

2. 일일 수익률

* `실제_일일수익률` (%)
* `시뮬_일일수익률` (%)
* `일일수익률_차이` (%)

3. 가격/누적수익률 차이

* `가격_차이_비율` (%)
* `실제_누적수익률` (%)
* `시뮬_누적수익률` (%)
* `누적수익률_차이` (%)

총 10개 컬럼.

### 5.3 구현 힌트

1. 기존 `generate_daily_comparison_csv`에서
   불필요한 컬럼(`…_절대값`, `로그가격_*`, `오차제곱`)은 생성하지 않도록 수정.
2. DataFrame 생성 후, 숫자 컬럼 일괄 반올림:

```python
num_cols = [c for c in comparison_df.columns if c != "날짜"]
comparison_df[num_cols] = comparison_df[num_cols].round(4)
```

3. 요약 통계(평균/최대)는
   이 CSV를 다시 읽어 계산하거나,
   내부 계산용 시리즈를 별도로 사용하는 방식으로 구현.

---

## 6. 로그 출력 개선 (중요 지표 요약 + 설명)

### 6.1 상위 10개 전략 비교 테이블

* `validate_tqqq_simulation.py`에서
  `top_strategies`를 받아 **상위 10개 전략을 표 형식으로 로그**에 출력:

예시 컬럼:

* rank
* funding_spread
* expense_ratio
* strategy_score
* 일일수익률_상관계수
* 일일수익률_RMSE_pct
* 최종가격_차이_pct
* 누적수익률_상대차이_pct

### 6.2 최상위 전략에 대한 “문장형 요약”

best_strategy(=rank 1)에 대해 마지막에 다음과 같이 설명 로그를 추가:

예시:

```text
[요약]
- 일일 수익률 상관계수 0.9989로, 실제 TQQQ의 일간 움직임을 거의 완벽하게 따라갑니다.
- 일일 수익률 RMSE는 0.20%로, 실제 변동성(약 3.9%)의 약 5% 수준입니다.
- 최종 가격 차이는 -0.20%로, 15년 이상 기간 동안 거의 동일한 수준입니다.
- 누적 수익률 상대 차이는 0.20%로, 장기 성과도 거의 완전히 일치합니다.
```

* 이 요약은 숫자 + 해석을 같이 제공해,
  검증 로그만 봐도 “아, 이 정도면 충분히 잘 맞는구나”를 바로 이해할 수 있도록 한다.

---

## 7. TQQQ.md 문서 업데이트 요구사항

마지막으로 `TQQQ.md`도 현재 설계/구현에 맞게 고쳐 주세요.

### 7.1 multiplier 관련 내용 수정

* “최적 multiplier=3.32”와 같이 **특정 multiplier 값**을 강조하던 부분은 삭제/수정.
* 대신:

  * **검증 단계**: multiplier = 3.0 고정
  * **캘리브레이션 대상**: funding_spread, expense_ratio
  * **상위 10개 전략을 score 기준으로 선택**한다는 구조를 설명.

### 7.2 검증 지표 개수 표현 완화

* “18개 지표”처럼 **정확한 개수 숫자**를 문서에 박아 두는 대신,

  * “기간 정보 + 일일 수익률 + 로그가격 + 누적수익률 + 가격 지표들을 계산한다” 식으로 표현.
* 필요하다면, 실제 코드의 필드 목록을 bullet로 나열하되
  개수를 숫자로 하드코딩하지 않는다.

### 7.3 누적 수익률 기준 표현 수정

* “누적 수익률 차이 ±20% 이내”라는 문장을
  다음과 같이 명확히 한다.

예시:

> * 누적 수익률 상대 차이(%) =
>   `|시뮬 누적수익률 - 실제 누적수익률| / |실제 누적수익률| × 100`
> * 검증 기준: **상대 차이 ±20% 이내면 허용**

* 퍼센트포인트(예: 26,283% vs 26,231% → 52.2%p 차이)는
  “보조 지표”로 언급하더라도, 기준은 **상대 오차** 위주로 설명.

### 7.4 Top 10 전략 저장/로그 방식 설명 추가

* 문서에 다음 내용을 추가:

  * 검증 과정에서 **비용 모델 파라미터(funding_spread, expense_ratio)** 에 대한 2D grid search를 수행한다.
  * score 기준 상위 10개 조합을 선택하고,

    * `results/tqqq_validation.csv`에 10행으로 저장
    * 검증 스크립트 실행 시 로그로도 표 형태로 출력
  * 최종적으로는 “상위 1개 전략(best_strategy)”의 지표를 중심으로 해석하지만,
    필요 시 상위 10개 전략을 비교하면서 튜닝할 수 있다.

### 7.5 숫자 예시는 “예시일 뿐”임을 명시

* 문서에 나오는 **구체적인 값(예: 상관계수, 누적수익률 등)** 은

  * “예시 (202X-XX-XX 기준)”이라는 문구를 함께 두고,
  * 실제 실행 시점에 따라 달라질 수 있음을 명시.

---

## 8. 요약

1. **코드 측면**

   * multiplier는 3.0에 고정
   * 비용 모델(FFR + spread + expense_ratio)을 2D grid search로 캘리브레이션
   * `find_optimal_cost_model` 추가, 상위 10개 전략 반환
   * `validate_simulation`에 누적 수익률 상대 오차 지표 추가
   * 품질 체크는 상대 오차 기준으로 변경
   * 요약 통계에서 최소(min) 제거, MSE 출력/CSV 제거
   * `tqqq_daily_comparison.csv`는 핵심 컬럼 위주로 슬림화 + 반올림

2. **로그/CSV 측면**

   * 상위 10개 전략을 score 기준으로 정렬하여 로그 & `tqqq_validation.csv`에 반영
   * 최상위 전략에 대해 숫자 + 해석이 포함된 요약 로그를 추가

3. **문서(TQQQ.md) 측면**

   * multiplier 관련 오래된 예시(3.32 등) 제거/수정
   * 검증 지표 개수 표현 완화
   * 누적 수익률 기준을 “상대 오차 ±20%”로 명확화
   * Top 10 전략 구조와 score 개념을 문서에 반영

위 요구사항을 모두 반영하여
`leveraged_etf.py`, `validate_tqqq_simulation.py`, `TQQQ.md`를 수정해 주세요.

```

---

위 `.md`를 그대로 복사해서 쓰면 돼.  
추가로, 혹시 나중에 “실제 코드까지 같이 짜 줘” 쪽으로 가고 싶으면,  
이 프롬프트를 기준으로 바로 구현용 요청을 이어가도 된다.
```
