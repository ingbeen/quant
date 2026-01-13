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
- 반환: FFR DataFrame (DATE: str (yyyy-mm), VALUE: float)
- DATE 컬럼은 `datetime.date` 객체가 아닌 `"yyyy-mm"` 문자열 형식
- 예외: FileNotFoundError (파일 부재 시)

**`load_expense_ratio_data(path: Path) -> pd.DataFrame`**:

- TQQQ 운용비율(Expense Ratio) 월별 데이터 로딩
- 입력: CSV 파일 경로
- 반환: Expense Ratio DataFrame (DATE: str (yyyy-mm), VALUE: float)
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
- `INTEGRITY_TOLERANCE = 1e-6` (0.000001%, 무결성 체크 허용 오차)
  - abs(signed)와 abs 컬럼의 최대 차이 허용값
  - 결정 근거: 실제 데이터 관측값 (max_abs_diff=4.66e-14%) + 10% 여유
  - 초과 시 ValueError 발생 (fail-fast)

**컬럼 및 키 정의**:

- FFR 데이터: `COL_FFR_DATE`, `COL_FFR_VALUE`
- Expense Ratio 데이터: `COL_EXPENSE_DATE`, `COL_EXPENSE_VALUE`
- 일별 비교: `COL_ACTUAL_CLOSE`, `COL_SIMUL_CLOSE`, `COL_ACTUAL_DAILY_RETURN`, `COL_SIMUL_DAILY_RETURN`, `COL_CUMUL_MULTIPLE_LOG_DIFF_ABS`, `COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED` 등
- 딕셔너리 키: `KEY_SPREAD`, `KEY_EXPENSE`, `KEY_OVERLAP_START`, `KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE` 등

근거 위치: [src/qbt/tqqq/constants.py](constants.py)

---

### 3. analysis_helpers.py

**TQQQ 시뮬레이션 분석용 순수 계산 함수를 제공합니다** (412줄).

금리-오차 관계 분석을 위한 계산, 집계, 검증 함수를 제공합니다.
모든 함수는 상태를 유지하지 않으며(stateless), fail-fast 정책을 따릅니다.

#### Fail-fast 정책

**원칙**: 결과를 신뢰할 수 없게 만드는 문제 발견 시 ValueError를 raise하여 즉시 중단

- 조용히 진행하지 않고 명확한 에러 메시지 제공
- simulation.py와 동일한 철학
- Streamlit 앱에서는 ValueError catch → st.error() + st.stop()

**Fail-fast 대상**:

- M_real <= 0 또는 M_sim <= 0 (누적수익률 로그 계산 불가)
- 1 + r_real/100 <= 0 또는 1 + r_sim/100 <= 0 (일일 로그 계산 불가)
- 필수 컬럼 누락 또는 입력 DataFrame 비어있음
- 금리(FFR) 데이터의 월 커버리지 부족/매칭 불가
- 무결성 체크 실패: abs(signed)와 abs 컬럼 차이가 tolerance 초과
- 월별 집계 결과가 너무 짧아 핵심 지표 계산 불가 (예: Rolling 12M 상관)

#### 주요 함수

**`calculate_signed_log_diff_from_cumulative_returns(cumul_return_real_pct, cumul_return_sim_pct) -> pd.Series`**:

- 누적수익률(%)로부터 signed 누적배수 로그차이를 계산
- 수식: `signed(%) = 100 * ln((1 + r_sim/100) / (1 + r_real/100))`
- 부호 의미:
  - 양수: 시뮬레이션이 실제보다 높음
  - 음수: 시뮬레이션이 실제보다 낮음
  - 0에 가까움: 거의 일치
- 예외: M_real <= 0 또는 M_sim <= 0 시 ValueError (fail-fast)

**`calculate_daily_signed_log_diff(daily_return_real_pct, daily_return_sim_pct) -> pd.Series`**:

- 일일수익률(%)로부터 일일 증분 signed 로그오차를 계산
- "그날 시뮬레이션이 실제 대비 얼마나 더/덜 벌었는가"를 나타냄
- 월별 집계 시 sum하여 월간 누적 오차 계산에 사용
- 예외: 1 + r <= 0 시 ValueError (fail-fast)

**`aggregate_monthly(daily_df, date_col, signed_col, ffr_df=None, min_months_for_analysis=13) -> pd.DataFrame`**:

- 일별 데이터를 월별로 집계하고 금리 데이터와 매칭
- 처리 흐름:
  1. 날짜 기준 오름차순 정렬 (월말 값 정확성 보장)
  2. month = 날짜.to_period("M") 생성
  3. 월별 집계: e_m (월말 누적 signed), sum_daily_m (일일 증분 월합)
  4. de_m: e_m의 월간 변화 (diff)
  5. 금리 데이터 join (month 키)
  6. rate_pct, dr_m 계산
- 월말 값 정의: "해당 월 마지막 거래일의 레코드"
- 예외: 필수 컬럼 누락, 금리 커버리지 부족, 월별 결과 부족 시 ValueError (fail-fast)

**`validate_integrity(signed_series, abs_series, tolerance=None) -> dict`**:

- abs(signed)와 abs 컬럼의 무결성 검증
- tolerance가 None이면 관측 모드 (실제 데이터로 max/mean 로그 출력)
- tolerance가 주어지면 검증 모드 (max_abs_diff > tolerance 시 ValueError)
- 반올림/누적 방식 차이로 완전히 0은 아닐 수 있음

근거 위치: [src/qbt/tqqq/analysis_helpers.py](analysis_helpers.py)

---

### 4. simulation.py

**레버리지 ETF 시뮬레이션 엔진을 제공합니다** (676줄).

#### 주요 함수

**제네릭 월별 데이터 함수**:

**`_create_monthly_data_dict(df, date_col, value_col, data_type)`**:

- 월별 데이터 DataFrame을 O(1) 조회용 딕셔너리로 변환
- 입력: DataFrame, 날짜 컬럼명, 값 컬럼명, 데이터 타입("FFR"/"Expense")
- 반환: `{"YYYY-MM": value}` 딕셔너리
- 중복 월 검증: 중복 발견 시 즉시 ValueError (데이터 무결성 보장)
- 데이터 타입에 따라 명확한 에러 메시지 제공

**`_lookup_monthly_data(date_value, data_dict, max_months_diff, data_type)`**:

- 월별 데이터 딕셔너리에서 특정 날짜의 값 조회
- 입력: 날짜, 데이터 딕셔너리, 최대 월 차이, 데이터 타입
- 반환: 해당 값 (float)
- 조회 로직: 정확한 월 매칭 → 이전 월 폴백
- 데이터 검증: 최근 데이터와의 월 차이가 max_months_diff 초과 시 예외
- 데이터 타입에 따라 명확한 에러 메시지 제공

**`_create_ffr_dict(ffr_df)`**:

- FFR DataFrame을 O(1) 조회용 딕셔너리로 변환
- 내부적으로 `_create_monthly_data_dict()` 호출
- 입력: FFR DataFrame (DATE: str (yyyy-mm), VALUE: float)
- 반환: `{"YYYY-MM": ffr_value}` 딕셔너리

**`_lookup_ffr(date_value, ffr_dict)`**:

- FFR 딕셔너리에서 특정 날짜의 금리 조회
- 내부적으로 `_lookup_monthly_data()` 호출
- 입력: 날짜, FFR 딕셔너리
- 반환: FFR 값 (float)

**`_create_expense_dict(expense_df)`**:

- Expense DataFrame을 O(1) 조회용 딕셔너리로 변환
- 내부적으로 `_create_monthly_data_dict()` 호출
- 입력: Expense DataFrame (DATE: str (yyyy-mm), VALUE: float)
- 반환: `{"YYYY-MM": expense_value}` 딕셔너리

**`_lookup_expense(date_value, expense_dict)`**:

- Expense 딕셔너리에서 특정 날짜의 운용비율 조회
- 내부적으로 `_lookup_monthly_data()` 호출
- 입력: 날짜, Expense 딕셔너리
- 반환: Expense 값 (float)

**`calculate_daily_cost(date_value, ffr_dict, expense_dict, funding_spread, leverage)`**:

- 특정 날짜의 일일 비용률 계산
- 입력: 날짜, FFR 딕셔너리, Expense 딕셔너리, funding spread, 레버리지 배수
- 반환: 일일 비용률 (소수)
- 성능: FFR 및 Expense 조회 O(1) 딕셔너리 조회 (기존 DataFrame 필터링 대비 대폭 개선)
- 동적 비용 적용: 날짜에 따라 FFR과 Expense가 동적으로 조회됨
- 비용 공식:
  ```
  연간 자금 조달 비용률 = (FFR(date) + funding_spread) × 레버리지 차입 비율
  일일 자금 조달 비용 = 연간 자금 조달 비용률 / TRADING_DAYS_PER_YEAR
  일일 운용 비용 = expense_ratio(date) / TRADING_DAYS_PER_YEAR
  총 일일 비용 = 일일 자금 조달 비용 + 일일 운용 비용
  ```

**`simulate(underlying_df, leverage, initial_price, ffr_df, expense_df, funding_spread, ffr_dict=None, expense_dict=None)`**:

- 기초 자산 데이터로부터 레버리지 ETF 가격 시뮬레이션
- 입력: 기초 자산 DataFrame, 레버리지 배수, 초기 가격, FFR DataFrame, Expense DataFrame, spread
- FFR 커버리지 검증은 함수 내부에서 자동 수행됨 (ffr_df 사용 시)
- 반환: 시뮬레이션 결과 DataFrame (OHLCV 형식)
- 시뮬레이션 로직:
  1. FFR 커버리지 검증 + 딕셔너리 변환 (자동)
  2. 기초 자산 일일 수익률 계산 (`pct_change()`)
  3. 각 거래일마다:
     - 동적 비용 계산 (`calculate_daily_cost`, O(1) FFR 조회)
     - 레버리지 수익률 = 기초 수익률 × 레버리지 배수 - 일일 비용
     - 가격 업데이트 (복리 효과 반영)
  4. OHLV 데이터 구성 (Open = 전일 Close, High/Low/Volume = 0)

**`extract_overlap_period(underlying_df, actual_leveraged_df)`**:

- 기초 자산과 실제 레버리지 ETF의 겹치는 기간 추출
- 입력: 기초 자산 DataFrame, 실제 레버리지 ETF DataFrame
- 반환: `(overlap_start, overlap_end, overlap_days)` 튜플

**`find_optimal_cost_model(underlying_df, actual_df, ffr_df, expense_df, leverage, spread_range, spread_step)`**:

- 그리드 서치로 최적 비용 모델 파라미터 탐색
- 입력: 기초 자산 DataFrame, 실제 레버리지 ETF DataFrame, FFR DataFrame, Expense DataFrame, 레버리지 배수, spread 그리드 범위/증분
- FFR/Expense 커버리지 검증 및 딕셔너리 변환은 병렬 실행 전 한 번만 수행 (성능 최적화)
- 반환: 상위 전략 리스트 (딕셔너리, 최대 `MAX_TOP_STRATEGIES`개)
- 처리 흐름:
  1. 겹치는 기간 추출 (`extract_overlap_period`)
  2. FFR 커버리지 검증 (overlap 기간에 대한 FFR 데이터 충분성 확인, fail-fast)
  3. FFR/Expense 딕셔너리 생성 (`_create_ffr_dict`, `_create_expense_dict`) - 검증 완료 후 한 번만 전처리
  4. 그리드 생성 (spread만 탐색, expense는 CSV 기반으로 고정)
  5. 병렬 실행 (`execute_parallel`, 검증된 딕셔너리는 WORKER_CACHE 활용)
     - 각 spread 값마다 `simulate()` 실행 (ffr_dict, expense_dict 사용)
     - `calculate_validation_metrics()` 호출하여 오차 계산
  6. 결과 정렬 (누적배수 로그차이 RMSE 오름차순)
  7. 상위 전략 반환

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

### 5. visualization.py

**TQQQ 시뮬레이션 시각화 모듈** (비즈니스 로직, `src/qbt/tqqq/visualization.py`).

Plotly 기반 차트 생성 함수를 제공하여 대시보드 및 분석 보고서에서 사용할 수 있는 인터랙티브 차트를 생성합니다.

**주요 함수**:

- `create_price_comparison_chart(df)`: 실제 종가 vs 시뮬레이션 종가 라인 차트
- `create_daily_return_diff_histogram(df)`: 일일수익률 절대차이 히스토그램 + Rug plot
- `create_cumulative_return_diff_chart(df)`: 누적배수 로그차이 라인 차트 (signed 버전, 방향성 포함)
- `create_level_chart(monthly_df, y_col, y_label)`: 금리 수준 vs 오차 수준 산점도 + 시계열 라인 차트 (서브플롯 2개)
- `create_delta_chart(monthly_df, y_col, y_label, lag)`: 금리 변화 vs 오차 변화 산점도 + Rolling 12M 상관 (서브플롯 2개, tuple 반환)

**설계 특징**:

- 모든 함수는 상태 비저장 (stateless)
- 반환 타입: `plotly.graph_objects.Figure` (create_delta_chart는 `tuple[go.Figure, pd.DataFrame]`)
- 결측치 자동 처리 (dropna)
- 한글 레이블 및 툴팁 지원
- 추세선 (OLS 1차 다항식) 자동 계산

근거 위치: [src/qbt/tqqq/visualization.py](visualization.py), [tests/test_tqqq_visualization.py](../../../tests/test_tqqq_visualization.py)

---

### 6. streamlit_daily_comparison.py (scripts/tqqq/)

**TQQQ 시뮬레이션 일별 비교 대시보드** (CLI 계층, `scripts/tqqq/streamlit_daily_comparison.py`).

**주요 기능**:

- 가격 비교 차트: 실제 TQQQ vs 시뮬레이션 (시계열 라인 차트, Plotly)
- 오차 분석 차트: 히스토그램, 시계열 오차 추이, 통계 요약
- 데이터 캐싱: Streamlit 캐시 데코레이터로 반복 로딩 방지
- signed 기반 오차 지표 사용 (방향성 파악 가능)

**아키텍처**:

- CLI 계층으로서 비즈니스 로직(visualization 모듈) 호출
- 차트 생성은 visualization.py에 위임
- 데이터 로딩만 담당

근거 위치: [scripts/tqqq/streamlit_daily_comparison.py](../../../scripts/tqqq/streamlit_daily_comparison.py)

---

### 7. streamlit_rate_spread_lab.py (scripts/tqqq/)

**TQQQ 금리-오차 관계 분석 연구용 앱** (CLI 계층, `scripts/tqqq/streamlit_rate_spread_lab.py`).

**목적**: 금리 환경과 시뮬레이션 오차의 관계를 시각화하여 spread 조정 전략 수립 지원

**주요 기능**:

- **Level 탭**: 금리 수준 vs 월말 누적 signed 오차
  - 산점도 + 추세선
  - 시계열 라인 차트 (금리 vs 오차 동시 표시, 이중 y축)
  - y축 선택: e_m (월말 누적 signed, 기본), de_m (월간 변화), sum_daily_m (일일 증분 월합)
  - y축 의미 캡션 표시
- **Delta 탭**: 금리 변화 vs 오차 변화
  - 산점도 + 추세선
  - Lag 옵션: 0/1/2 개월 (드롭다운 선택)
  - 샘플 수(n) 표시 (lag에 따라 변함)
  - Rolling 12개월 상관 시계열 (유효 월 수 부족 시 경고)
  - y축 선택: de_m (기본), sum_daily_m
- **교차검증 탭**: de_m vs sum_daily_m 차이 분석
  - 차이 통계 (최대, 평균, 표준편차)
  - 차이가 큰 상위 5개월 표시
  - 히스토그램
  - 차이 원인 설명 (반올림, 결측, 계산 방식)
- **데이터 로딩**:
  - mtime 기반 캐시 (최신 CSV 자동 반영)
  - fail-fast 에러 처리 (ValueError → st.error + st.stop)
- **차트**: Plotly 인터랙티브 (화면 표시만, 저장 금지)

근거 위치: [scripts/tqqq/streamlit_rate_spread_lab.py](../../../scripts/tqqq/streamlit_rate_spread_lab.py)

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

- **데이터 소스**: `storage/etc/tqqq_net_expense_ratio_monthly.csv`
- **형식**: DATE (yyyy-mm), VALUE (연간 운용비율, 0~1 소수)
- **적용 방식**: 월별로 실제 운용비율을 적용하여 시뮬레이션 정확도 향상
- **조회 로직**:
  - 해당 월 또는 가장 가까운 이전 월의 값 사용
  - 최대 월 차이: 12개월 (MAX_EXPENSE_MONTHS_DIFF)
  - 허용 갭 초과 시 ValueError
- 공식: `expense_ratio(date) / TRADING_DAYS_PER_YEAR`
- 연간 비율을 일별로 환산

**총 비용**:

- `총 일일 비용 = 일일 자금 조달 비용 + 일일 운용 비용`
- `= [(FFR + funding_spread) × (leverage - 1) + expense_ratio(date)] / TRADING_DAYS_PER_YEAR`
- 운용 비용은 날짜에 따라 동적으로 조회되어 적용됨

근거 위치: [simulation.py의 calculate_daily_cost](simulation.py), [constants.py](constants.py), [data_loader.py의 load_expense_ratio_data](data_loader.py)

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
- 형식: `DATE` (yyyy-mm 문자열), `VALUE` (0~1 비율, 예: 0.0463 = 4.63%)
- 검증: 최근 데이터와의 시간 차이 `MAX_FFR_MONTHS_DIFF` (2개월) 이내
- 예외 발생: 허용 갭 초과 시 `ValueError`

**운용비율 데이터 (Expense Ratio)**:

- 월별 TQQQ 운용비율 (Net Expense Ratio)
- 형식: `DATE` (yyyy-mm 문자열), `VALUE` (0~1 비율, 예: 0.0095 = 0.95%)
- 데이터 경로: `storage/etc/tqqq_net_expense_ratio_monthly.csv`
- 검증:
  - 중복 월 금지
  - 최근 데이터와의 시간 차이 `MAX_EXPENSE_MONTHS_DIFF` (12개월) 이내
- 예외 발생: 중복 월, 허용 갭 초과 시 `ValueError`

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

### 3. 대시보드 구현 (streamlit_daily_comparison.py)

**데이터 캐싱**:

- Streamlit 캐시 데코레이터로 반복 로딩 방지 (`@st.cache_data`)
- 성능 최적화

**차트 생성**:

- visualization 모듈의 차트 생성 함수 호출
- Plotly 기반 인터랙티브 차트
- 상태 비저장 함수 방식

**검증**:

- 필수 컬럼 확인
- 결측치 처리 (visualization 모듈에서 자동 처리)

근거 위치: [scripts/tqqq/streamlit_daily_comparison.py](../../../scripts/tqqq/streamlit_daily_comparison.py), [src/qbt/tqqq/visualization.py](visualization.py)

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

**컬럼** (10개):

1. `날짜`: 거래일
2. `종가_실제`: 실제 TQQQ 종가
3. `종가_시뮬`: 시뮬레이션 종가
4. `일일수익률_실제`: 실제 일일 수익률 (%)
5. `일일수익률_시뮬`: 시뮬레이션 일일 수익률 (%)
6. `일일수익률_절대차이`: 일일 수익률 차이 절댓값
7. `누적수익률_실제(%)`: 실제 누적 수익률
8. `누적수익률_시뮬레이션(%)`: 시뮬레이션 누적 수익률
9. `누적배수_로그차이_abs(%)`: **스케일 무관 추적오차 지표 (절댓값)**
10. `누적배수_로그차이_signed(%)`: **스케일 무관 추적오차 지표 (부호 포함, 방향성)**

**Breaking Change (2025-12-31)**:

- 기존 `누적배수_로그차이(%)` 컬럼명이 `누적배수_로그차이_abs(%)`로 변경됨
- 값은 동일하게 유지 (절댓값), 컬럼명만 변경
- `누적배수_로그차이_signed(%)` 컬럼 신규 추가 (부호 포함)
- 외부 노트북/스크립트에서 컬럼명 참조 시 업데이트 필요

**용도**:

- 대시보드 시각화 (abs 사용)
- 금리-오차 관계 분석 (signed 사용, 연구용 앱)
- 일별 성과 분석

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

### tqqq_rate_spread_lab_monthly.csv (월별 피처)

**경로**: `storage/results/tqqq_rate_spread_lab_monthly.csv`

**컬럼** (8개, 모두 한글):

1. `연월`: 월 Period (yyyy-MM 형식 문자열)
2. `금리수준(%)`: FFR 금리 (0~100 범위, 예: 4.5 = 4.5%)
3. `금리변화(%p)`: 전월 대비 금리 변화량 (percentage point)
4. `월말누적오차(%)`: 해당 월 마지막 거래일의 누적배수 로그차이 (signed)
5. `월간오차변화(%)`: 전월 대비 누적오차 변화량
6. `일일오차월합(%)`: 해당 월 내 일일 signed 로그차이의 합계
7. `금리변화Lag1(%p)`: 1개월 전 금리 변화 (lag 분석용)
8. `금리변화Lag2(%p)`: 2개월 전 금리 변화 (lag 분석용)

**라운딩 정책**: 모든 수치 컬럼 4자리 (예: 4.1235%, 0.0512%p)

**용도**: AI/모델링, 금리-오차 관계 분석, Streamlit 앱 데이터 소스

근거 위치: [analysis_helpers.py의 save_monthly_features](analysis_helpers.py), [constants.py](constants.py)

---

### tqqq_rate_spread_lab_summary.csv (요약 통계)

**경로**: `storage/results/tqqq_rate_spread_lab_summary.csv`

**컬럼** (11개, 모두 한글):

1. `분석유형`: Level / Delta / CrossValidation
2. `X축변수`: 독립변수 이름 (예: rate_pct, dr_m_lag0)
3. `Y축변수`: 종속변수 이름 (예: e_m, de_m, sum_daily_m)
4. `시차(월)`: Delta 분석의 lag 값 (0/1/2), Level/CrossValidation은 0 또는 None
5. `샘플수`: 유효 데이터 포인트 개수
6. `상관계수`: Pearson 상관계수 (Level/Delta만 해당)
7. `기울기`: OLS 회귀 기울기 (Level/Delta만 해당)
8. `절편`: OLS 회귀 절편 (Level/Delta만 해당)
9. `최대절댓값차이(%)`: de_m - sum_daily_m 최대 차이 (CrossValidation만 해당)
10. `평균절댓값차이(%)`: de_m - sum_daily_m 평균 차이 (CrossValidation만 해당)
11. `표준편차(%)`: de_m - sum_daily_m 표준편차 (CrossValidation만 해당)

**라운딩 정책**: 모든 수치 컬럼 4자리 (예: 0.9123, 0.0045)

**용도**: AI/해석, 금리-오차 관계 패턴 발견, 교차검증 품질 확인

근거 위치: [analysis_helpers.py의 save_summary_statistics](analysis_helpers.py), [constants.py](constants.py)

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
- **Plotly**: 대시보드 차트 (visualization.py, streamlit_daily_comparison.py)
- **Streamlit**: 대시보드 프레임워크 (streamlit_daily_comparison.py)

근거 위치: [simulation.py](simulation.py), [visualization.py](visualization.py), [scripts/tqqq/streamlit_daily_comparison.py](../../../scripts/tqqq/streamlit_daily_comparison.py)
