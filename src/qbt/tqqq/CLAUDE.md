# 레버리지 ETF 시뮬레이션 도메인 가이드

> 이 문서는 `src/qbt/tqqq/` 패키지의 레버리지 ETF 시뮬레이션 도메인에 대한 상세 가이드입니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../../../CLAUDE.md)를 참고하세요.

## 도메인 목적

레버리지 ETF 시뮬레이션 도메인은 기초 자산 데이터로부터 레버리지 상품의 가격을 모델링하고,
실제 데이터와 비교하여 비용 모델의 정확도를 검증합니다.
QQQ(기초 자산)로부터 TQQQ(3배 레버리지 ETF)를 재현하는 것이 주요 사용 사례입니다.

---

## 스크립트 실행 순서

TQQQ 시뮬레이션 관련 스크립트는 다음 순서로 실행합니다:

1. **validate_tqqq_simulation.py**: 최적 비용 모델 파라미터 탐색 (그리드 서치)
2. **generate_tqqq_daily_comparison.py**: 일별 비교 데이터 생성 (실제 vs 시뮬)
3. **generate_synthetic_tqqq.py**: 합성 데이터 생성 (QQQ 전체 기간)

**실행 순서 이유**:

- 1단계에서 최적 파라미터를 찾은 후, 2·3단계에서 해당 파라미터 사용
- 2단계는 실제 TQQQ와 겹치는 기간만 비교
- 3단계는 QQQ의 가장 빠른 시작일부터 전체 기간 데이터 생성

근거 위치: [scripts/tqqq/](../../../scripts/tqqq/)

---

## 모듈 구성

### 1. data_loader.py

**TQQQ 도메인 전용 데이터 로딩 함수를 제공합니다** (88줄).

이 모듈의 함수들은 TQQQ 시뮬레이션 및 검증에 필요한 데이터를 로딩합니다.
프로젝트 전반의 공통 데이터 로딩 함수는 `utils/data_loader.py`를 참고하세요.

#### 주요 함수

**`load_ffr_data(path: Path) -> pd.DataFrame`**:

- 연방기금금리(FFR) 월별 데이터 로딩
- 입력: CSV 파일 경로
- 반환: FFR DataFrame (DATE: str (yyyy-mm), FFR: float)
- VALUE 컬럼을 FFR로 자동 rename
- DATE 컬럼은 `datetime.date` 객체가 아닌 `"yyyy-mm"` 문자열 형식
- 예외: FileNotFoundError (파일 부재 시)

**`load_comparison_data(path: Path) -> pd.DataFrame`**:

- TQQQ 일별 비교 CSV 파일 로딩 및 검증
- 입력: CSV 파일 경로
- 반환: 일별 비교 DataFrame (COMPARISON_COLUMNS 컬럼 포함)
- 필수 컬럼 검증 (COMPARISON_COLUMNS 기준)
- 날짜 컬럼을 datetime으로 자동 변환
- 예외:
  - FileNotFoundError (파일 부재 시)
  - ValueError (필수 컬럼 누락 시)

근거 위치: [src/qbt/tqqq/data_loader.py](data_loader.py)

---

### 2. constants.py

**레버리지 ETF 시뮬레이션 도메인 전용 상수를 정의합니다** (공통 상수는 `common_constants.py` 참고):

**경로 및 스펙 설정**:

- `TQQQ_DATA_PATH = Path("storage/stock/TQQQ_max.csv")` (실제 TQQQ 데이터)
- `TQQQ_SYNTHETIC_PATH = Path("storage/stock/TQQQ_synthetic_max.csv")` (합성 데이터)
- `FFR_DATA_PATH = Path("storage/etc/federal_funds_rate_monthly.csv")` (금리 데이터)
- `TQQQ_VALIDATION_PATH = Path("storage/results/tqqq_validation.csv")` (검증 결과)
- `TQQQ_DAILY_COMPARISON_PATH = Path("storage/results/tqqq_daily_comparison.csv")` (일별 비교)
- `DEFAULT_LEVERAGE_MULTIPLIER = 3.0` (TQQQ 3배 레버리지)
- `DEFAULT_SYNTHETIC_INITIAL_PRICE = 200.0` (합성 데이터 초기 가격)

**비용 모델 파라미터**:

- `DEFAULT_FUNDING_SPREAD`: FFR 스프레드 비율 기본값
- `DEFAULT_EXPENSE_RATIO`: 연간 비용 비율 기본값
- 그리드 서치 범위:
  - `DEFAULT_SPREAD_RANGE`: 스프레드 탐색 범위
  - `DEFAULT_SPREAD_STEP`: 스프레드 증분
  - `DEFAULT_EXPENSE_RANGE`: expense ratio 탐색 범위
  - `DEFAULT_EXPENSE_STEP`: expense ratio 증분

**데이터 검증 및 결과 제한**:

- `MAX_FFR_MONTHS_DIFF = 2` (FFR 데이터 최대 월 차이, 초과 시 예외)
- `MAX_TOP_STRATEGIES`: find_optimal_cost_model 반환 상위 전략 수

**컬럼 및 키 정의**:

- FFR 데이터: `COL_FFR_DATE`, `COL_FFR_VALUE_RAW`, `COL_FFR`
- 일별 비교: `COL_ACTUAL_CLOSE`, `COL_SIMUL_CLOSE`, `COL_ACTUAL_DAILY_RETURN`, `COL_SIMUL_DAILY_RETURN`, `COL_CUMUL_MULTIPLE_LOG_DIFF` 등
- 딕셔너리 키: `KEY_SPREAD`, `KEY_EXPENSE`, `KEY_OVERLAP_START`, `KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE` 등

근거 위치: [src/qbt/tqqq/constants.py](constants.py)

---

### 3. simulation.py

**레버리지 ETF 시뮬레이션 엔진을 제공합니다** (676줄).

#### 주요 함수

**`calculate_daily_cost(date_value, ffr_df, expense_ratio, funding_spread)`**:

- 특정 날짜의 일일 비용률 계산
- 입력: 날짜, FFR DataFrame, 연간 expense ratio, funding spread
- 반환: 일일 비용률 (소수)
- 비용 공식:
  ```
  연간 자금 조달 비용률 = (FFR + funding_spread) × 레버리지 차입 비율
  일일 자금 조달 비용 = 연간 자금 조달 비용률 / TRADING_DAYS_PER_YEAR
  일일 운용 비용 = expense_ratio / TRADING_DAYS_PER_YEAR
  총 일일 비용 = 일일 자금 조달 비용 + 일일 운용 비용
  ```
- FFR 데이터 검증: 최근 데이터와의 월 차이가 `MAX_FFR_MONTHS_DIFF` 초과 시 예외

**`simulate(underlying_df, ffr_df, leverage, funding_spread, expense_ratio, initial_price)`**:

- 기초 자산 데이터로부터 레버리지 ETF 가격 시뮬레이션
- 입력: 기초 자산 DataFrame, FFR DataFrame, 레버리지 배수, spread, expense ratio, 초기 가격
- 반환: 시뮬레이션 결과 DataFrame (OHLCV 형식)
- 시뮬레이션 로직:
  1. 기초 자산 일일 수익률 계산 (`pct_change()`)
  2. 각 거래일마다:
     - 동적 비용 계산 (`calculate_daily_cost`)
     - 레버리지 수익률 = 기초 수익률 × 레버리지 배수 - 일일 비용
     - 가격 업데이트 (복리 효과 반영)
  3. OHLV 데이터 구성 (Open = 전일 Close, High/Low/Volume = 0)

**`extract_overlap_period(underlying_df, actual_leveraged_df)`**:

- 기초 자산과 실제 레버리지 ETF의 겹치는 기간 추출
- 입력: 기초 자산 DataFrame, 실제 레버리지 ETF DataFrame
- 반환: `(overlap_start, overlap_end, overlap_days)` 튜플

**`find_optimal_cost_model(underlying_df, actual_df, ffr_df, leverage, spread_range, spread_step, expense_range, expense_step)`**:

- 그리드 서치로 최적 비용 모델 파라미터 탐색
- 입력: 기초 자산 DataFrame, 실제 레버리지 ETF DataFrame, FFR DataFrame, 레버리지 배수, 그리드 범위/증분
- 반환: 상위 전략 리스트 (딕셔너리, 최대 `MAX_TOP_STRATEGIES`개)
- 검증: 내부에서 FFR 커버리지 검증 수행 (`validate_ffr_coverage`)
- 처리 흐름:
  1. 겹치는 기간 추출 (`extract_overlap_period`)
  2. FFR 커버리지 검증 (overlap 기간에 대한 FFR 데이터 충분성 확인)
  3. 그리드 생성 (spread × expense 조합)
  4. 병렬 실행 (`execute_parallel`)
     - 각 조합마다 `simulate()` 실행
     - `calculate_validation_metrics()` 호출하여 오차 계산
  5. 결과 정렬 (누적배수 로그차이 RMSE 오름차순)
  6. 상위 전략 반환

**`calculate_validation_metrics(underlying_df, simul_df, ffr_df, leverage, funding_spread, expense_ratio)`**:

- 시뮬레이션 결과와 실제 데이터 비교 및 오차 분석
- 입력: 기초 자산 DataFrame, 시뮬레이션 DataFrame, FFR DataFrame, 레버리지 배수, spread, expense ratio
- 반환: 일별 비교 DataFrame
- 계산 지표:
  - 일일 수익률 (실제 / 시뮬)
  - 일일 수익률 절대 차이
  - 누적 수익률 (실제 / 시뮬, %)
  - 누적배수 로그차이 (스케일 무관 추적오차, %)

근거 위치: [src/qbt/tqqq/simulation.py](simulation.py)

---

### 4. streamlit_app.py (scripts/tqqq/)

**대시보드는 별도 스크립트로 분리되어 `scripts/tqqq/streamlit_app.py`에 위치합니다** (CLI 계층).

**주요 기능**:

- 가격 비교 차트: 실제 TQQQ vs 시뮬레이션 (시계열 라인 차트, Plotly)
- 오차 분석 차트: 히스토그램, 시계열 오차 추이, 통계 요약
- 데이터 캐싱: Streamlit 캐시 데코레이터로 반복 로딩 방지

근거 위치: [scripts/tqqq/streamlit_app.py](../../../scripts/tqqq/streamlit_app.py)

---

## 도메인 규칙

### 1. 시뮬레이션 규칙

**일일 리밸런싱 모델**:

- 매일 목표 레버리지 배율로 포지션 재조정
- 기초 자산의 일일 수익률에 배율 적용
- 복리 효과 반영 (전일 가격 기준으로 누적)

**레버리지 배율**:

- 목표 레버리지 배율: `DEFAULT_LEVERAGE_MULTIPLIER = 3.0`
- 일일 수익률에 배율 적용: `leveraged_return = underlying_return × leverage - daily_cost`

근거 위치: [constants.py의 DEFAULT_LEVERAGE_MULTIPLIER](constants.py), [simulation.py의 simulate](simulation.py)

---

### 2. 비용 구조 (동적 비용 모델)

**자금 조달 비용**:

- 공식: `(FFR + funding_spread) × (leverage - 1) / TRADING_DAYS_PER_YEAR`
- 레버리지 차입 비율: `leverage - 1` (예: 3배 레버리지 → 2배 차입, 2배 레버리지 → 1배 차입)
- 금리는 월별 FFR 데이터 사용 (년-월 기준 조회)
- 레버리지 비용은 leverage 파라미터를 명시적으로 받아 `(leverage - 1)` 배율 적용

**운용 비용**:

- 공식: `expense_ratio / TRADING_DAYS_PER_YEAR`
- 연간 비율을 일별로 환산

**총 비용**:

- `총 일일 비용 = 일일 자금 조달 비용 + 일일 운용 비용`
- `= [(FFR + funding_spread) × (leverage - 1) + expense_ratio] / TRADING_DAYS_PER_YEAR`

근거 위치: [simulation.py의 calculate_daily_cost](simulation.py), [constants.py](constants.py)

---

### 3. 가격 계산

**기본 로직**:

1. 전일 종가 기준
2. 기초 자산 일일 수익률 계산 (`pct_change()`)
3. 레버리지 배율 적용
4. 일일 비용 차감
5. 신규 종가 산출: `new_price = prev_price × (1 + leveraged_return)`

**OHLCV 추정**:

- Open: 전일 Close (첫날은 `initial_price`)
- High, Low, Volume: 0 (합성 데이터이므로 사용 안 함)

근거 위치: [simulation.py의 simulate](simulation.py)

---

### 4. 데이터 요구사항

**기초 자산 데이터**:

- OHLCV (시가, 고가, 저가, 종가, 거래량)
- 날짜순 정렬
- 결측치 없음
- 필수 컬럼: `COL_DATE`, `COL_CLOSE` (최소)

**금리 데이터 (FFR)**:

- 월별 기준 금리 (Federal Funds Rate)
- 형식: `DATE` (yyyy-mm 문자열), `VALUE` (금리 %, 소수)
- 검증: 최근 데이터와의 시간 차이 `MAX_FFR_MONTHS_DIFF` (2개월) 이내
- 예외 발생: 허용 갭 초과 시 `ValueError`

**실제 레버리지 상품 데이터**:

- 검증을 위한 실제 가격 (예: TQQQ)
- 기초 자산과 기간 일치 필요 (겹치는 구간 추출)

근거 위치: [simulation.py의 calculate_daily_cost, extract_overlap_period](simulation.py), [constants.py의 MAX_FFR_MONTHS_DIFF](constants.py)

---

### 5. 검증 임계값

**비용 파라미터 범위**:

- Funding Spread: `DEFAULT_SPREAD_RANGE`에 정의된 범위
- Expense Ratio: `DEFAULT_EXPENSE_RANGE`에 정의된 범위
- 그리드 증분: `DEFAULT_SPREAD_STEP`, `DEFAULT_EXPENSE_STEP`에 정의

**금리 데이터 갭**:

- 허용 가능한 최대 월 차이: `MAX_FFR_MONTHS_DIFF = 2`
- 초과 시 즉시 예외 발생 (`ValueError`)

**결과 제한**:

- 최적화 결과 반환 개수: `MAX_TOP_STRATEGIES`에 정의

근거 위치: [constants.py](constants.py), [simulation.py의 calculate_daily_cost](simulation.py)

---

## 핵심 계산 로직

### 누적배수 로그차이 계산

**목적**: 스케일에 무관한 추적오차 측정 (금액에 관계없이 일관된 비교)

**수식**:

```
M_actual(t) = actual_close(t) / actual_close(0)  # 누적 자산배수 (첫날 대비)
M_sim(t) = simul_close(t) / simul_close(0)
로그차이(%) = |ln(M_actual(t) / M_sim(t))| × 100
```

**특징**:

- 첫날 가격 기준 누적배수 사용
- 로그 비율로 스케일 무관성 확보
- 롤링 윈도우 미사용 (안정성 향상)
- 금융 표준 방법 (연속 복리 수익률 차이)

**구현 세부사항**:

- 수치 안정성: `EPSILON` (매우 작은 양수 값) 사용
- 분모 0 방지를 위한 최소값 처리
- `pd.Series` 타입 보장 (인덱스 보존)

**오차 지표**:

- **RMSE (Root Mean Square Error)**: 경로 전체 추적 품질 평가 (최적화 기준, 낮을수록 우수)
- **평균**: 평균 로그 추적오차 (보조 지표)
- **최대**: 최악 시점 이탈 정도 (보조 지표)

근거 위치: [simulation.py의 \_calculate_cumul_multiple_log_diff, calculate_validation_metrics](simulation.py)

---

## 구현 원칙

### 1. 합성 데이터 생성

**초기화**:

- 기초 자산의 시작 가격으로부터 역산
- 초기 레버리지 상품 가격 설정 (`initial_price`)

**일별 갱신**:

1. 기초 자산 수익률 계산
2. 레버리지 적용
3. 비용 차감
4. 가격 업데이트 (복리 효과)

**OHLCV 추정**:

- 종가 기준으로 시가/고가/저가 생성
- 거래량은 0 (합성 데이터)

근거 위치: [simulation.py의 simulate](simulation.py)

---

### 2. 파라미터 탐색

**그리드 생성**:

- spread와 expense의 모든 조합 생성
- 범위와 증분으로 격자 생성

**병렬 처리**:

- 독립적인 시뮬레이션을 병렬 실행 (`execute_parallel`)
- pickle 가능한 함수 사용 (`_evaluate_cost_model_candidate`)
- 입력 순서 보장

**최적 전략 선택**:

- 오차 기반 순위 결정 (누적배수 로그차이 RMSE 오름차순)
- 상위 전략만 반환 (`MAX_TOP_STRATEGIES`)

근거 위치: [simulation.py의 find_optimal_cost_model, \_evaluate_cost_model_candidate](simulation.py)

---

### 3. 대시보드 구현 (streamlit_app.py)

**데이터 캐싱**:

- Streamlit 캐시 데코레이터로 반복 로딩 방지 (`@st.cache_data`)
- 성능 최적화

**차트 생성**:

- Plotly 기반 인터랙티브 차트
- 상태 비저장 함수 방식

**검증**:

- 필수 컬럼 확인
- 결측치 처리

근거 위치: [scripts/tqqq/streamlit_app.py](../../../scripts/tqqq/streamlit_app.py)

---

## 출력 형식

### 합성 데이터

- 기초 자산과 동일한 OHLCV 형식
- 날짜 정렬
- CSV 저장: `TQQQ_synthetic_max.csv`

### 일별 비교 데이터

- 날짜별 실제/시뮬 가격
- 일일 수익률 및 차이
- 누적 수익률
- 누적배수 로그차이 (스케일 무관 추적오차)
- 한글 컬럼명
- CSV 저장: `tqqq_daily_comparison.csv`

### 검증 결과

- 파라미터 조합별 오차 지표
- 상위 전략 리스트
- CSV 저장: `tqqq_validation.csv`

근거 위치: [constants.py](constants.py)

---

## CSV 파일 형식

### tqqq_daily_comparison.csv (일별 비교)

**경로**: `storage/results/tqqq_daily_comparison.csv`

**컬럼** (9개):

1. `날짜`: 거래일
2. `종가_실제`: 실제 TQQQ 종가
3. `종가_시뮬`: 시뮬레이션 종가
4. `일일수익률_실제`: 실제 일일 수익률 (%)
5. `일일수익률_시뮬`: 시뮬레이션 일일 수익률 (%)
6. `일일수익률_절대차이`: 일일 수익률 차이 절댓값
7. `누적수익률_실제(%)`: 실제 누적 수익률
8. `누적수익률_시뮬레이션(%)`: 시뮬레이션 누적 수익률
9. `누적배수_로그차이(%)`: **스케일 무관 추적오차 지표**

**용도**: 대시보드 시각화, 일별 성과 분석

근거 위치: [constants.py의 COMPARISON_COLUMNS](constants.py), [simulation.py의 calculate_validation_metrics](simulation.py)

---

### tqqq_validation.csv (그리드 서치 결과)

**경로**: `storage/results/tqqq_validation.csv`

**컬럼** (10개):

1. `funding_spread`: 자금 조달 스프레드 (소수, 예: 0.004 = 0.4%)
2. `expense_ratio`: 연간 운용 비용 비율 (소수, 예: 0.008 = 0.8%)
3. `종가_실제`: 실제 TQQQ 마지막 날 종가
4. `종가_시뮬`: 시뮬레이션 마지막 날 종가
5. `누적수익률_실제(%)`: 실제 TQQQ 전체 기간 누적 수익률
6. `누적수익률_시뮬레이션(%)`: 시뮬레이션 전체 기간 누적 수익률
7. `누적수익률_상대차이(%)`: 누적수익률 상대차이 (실제 기준)
8. `누적배수로그차이_RMSE(%)`: **RMSE 로그 추적오차** (최적화 기준, 낮을수록 우수)
9. `누적배수로그차이_평균(%)`: 평균 로그 추적오차 (보조 지표)
10. `누적배수로그차이_최대(%)`: 최대 로그 추적오차 (최악 시점 이탈 정도)

**메타 정보** (터미널 헤더에만 표시, CSV에는 미포함):

- 검증 기간 (시작일 ~ 종료일)
- 총 거래일 수
- 레버리지 배율

**용도**: 최적 비용 모델 파라미터 선정, 성능 벤치마킹

**정렬 기준**: `누적배수로그차이_RMSE(%)` 오름차순 (낮을수록 경로 전체 추적이 우수)

근거 위치: [scripts/tqqq/validate_tqqq_simulation.py](../../../scripts/tqqq/validate_tqqq_simulation.py), [constants.py](constants.py)

---

## 사용 예시

### 단일 시뮬레이션

```python
from qbt.tqqq import simulate
from qbt.utils.data_loader import load_stock_data, load_ffr_data

qqq_df = load_stock_data("storage/stock/QQQ_max.csv")
ffr_df = load_ffr_data()

simul_df = simulate(
    underlying_df=qqq_df,
    ffr_df=ffr_df,
    leverage=3.0,
    funding_spread=0.004,
    expense_ratio=0.0085,
    initial_price=200.0
)
```

### 최적 비용 모델 탐색

```python
from qbt.tqqq import find_optimal_cost_model
from qbt.utils.data_loader import load_tqqq_data

tqqq_df = load_tqqq_data()

top_strategies = find_optimal_cost_model(
    underlying_df=qqq_df,
    actual_df=tqqq_df,
    ffr_df=ffr_df,
    leverage=3.0,
    spread_range=(0.004, 0.008),
    spread_step=0.0005,
    expense_range=(0.0075, 0.0105),
    expense_step=0.0005
)
```

### 검증 메트릭 계산

```python
from qbt.tqqq import calculate_validation_metrics

comparison_df = calculate_validation_metrics(
    underlying_df=qqq_df,
    simul_df=simul_df,
    ffr_df=ffr_df,
    leverage=3.0,
    funding_spread=0.004,
    expense_ratio=0.0085
)
```

근거 위치: [scripts/tqqq/](../../../scripts/tqqq/)

---

## 테스트 커버리지

**주요 테스트 파일**: [tests/test_tqqq_simulation.py](../../../tests/test_tqqq_simulation.py) (468줄)

**테스트 범위**:

- 일일 비용 계산 로직
- 레버리지 수익률 적용
- 복리 효과 검증
- 누적배수 로그차이 계산
- 겹치는 기간 추출
- 비용 모델 최적화 (그리드 서치)
- 검증 메트릭 계산
- 엣지 케이스 (FFR 갭 초과, 빈 데이터)

근거 위치: [tests/test_tqqq_simulation.py](../../../tests/test_tqqq_simulation.py)

---

## 주요 의존성

- **pandas**: 시계열 데이터 처리, DataFrame 연산
- **numpy**: 로그 계산, 수치 안정성 (EPSILON)
- **Plotly**: 대시보드 차트 (streamlit_app.py)
- **Streamlit**: 대시보드 프레임워크 (streamlit_app.py)

근거 위치: [simulation.py](simulation.py), [scripts/tqqq/streamlit_app.py](../../../scripts/tqqq/streamlit_app.py)
