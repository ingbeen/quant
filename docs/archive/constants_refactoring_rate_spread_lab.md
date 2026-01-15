# 상수 리팩토링 계획: constants.py 전면 정리 + 하드코딩 전수 상수화

## 1. 목표

TQQQ Rate Spread Lab의 상수 관리를 루트 CLAUDE.md의 "상수 명명 규칙"에 맞게 전면 리팩토링하여,
모든 하드코딩된 문자열/숫자/리스트를 상수로 변환하고 단일 진실 소스(SSOT)를 구축한다.

## 2. 현황 분석

### 2.1 constants.py 기존 상수 분류

**올바른 명명 (COL_, KEY_, DISPLAY_ 접두사 준수)**:
- CSV 컬럼: `COL_FFR_DATE`, `COL_FFR_VALUE`, `COL_EXPENSE_DATE`, `COL_EXPENSE_VALUE`
- 일별 비교 컬럼: `COL_ACTUAL_CLOSE`, `COL_SIMUL_CLOSE`, `COL_ACTUAL_DAILY_RETURN`, `COL_SIMUL_DAILY_RETURN`, etc.
- 월별 피처 컬럼: `COL_MONTH`, `COL_RATE_PCT`, `COL_DR_M`, `COL_E_M`, `COL_DE_M`, `COL_SUM_DAILY_M`, `COL_DR_LAG1`, `COL_DR_LAG2`
- 요약 통계 컬럼: `COL_CATEGORY`, `COL_X_VAR`, `COL_Y_VAR`, `COL_LAG`, `COL_N`, `COL_CORR`, etc.
- 딕셔너리 키: `KEY_SPREAD`, `KEY_OVERLAP_START`, `KEY_FINAL_CLOSE_ACTUAL`, etc.
- 출력 레이블: `DISPLAY_SPREAD` (하나만 정의됨)

### 2.2 누락된 상수 (하드코딩 조사 결과)

#### A. 임시/중간 계산 컬럼명 (COL_ 접두사 필요)
- `"daily_signed"`: 일일 증분 signed 로그오차
- `"month"`: 월별 집계용 Period 컬럼
- `"sum_daily_m_calc"`: sum_daily_m 계산용 임시 컬럼
- `"diff"`: de_m - sum_daily_m 차이
- `"abs_diff"`: diff의 절댓값
- `"dr_lag"`: Delta 분석용 임시 lag 컬럼
- `"VALUE"`: FFR/Expense CSV의 값 컬럼 (기존 `COL_FFR_VALUE`, `COL_EXPENSE_VALUE`를 사용하되, aggregate_monthly에서 `"VALUE"` 하드코딩 제거 필요)

#### B. 분석 파라미터 (PARAM_ 또는 적절한 접두사)
- `13`: 최소 분석 개월 수 (min_months_for_analysis)
- `5`: top N (교차검증 상위 표시)
- `30`: histogram bins
- `[0, 1, 2]`: lag 옵션 리스트
- `3`: streamlit 컬럼 개수 (UI 레이아웃)

#### C. 요약 통계 dict 키값 (KEY_ 접두사, 내부 dict 생성용)
- `"category"`, `"x_var"`, `"y_var"`, `"lag"`, `"n"`, `"corr"`, `"slope"`, `"intercept"`: 이미 COL_로 정의되어 있지만, dict 생성 시 사용하는 키는 별도로 필요할 수 있음 → 기존 COL_ 상수를 그대로 사용 가능
- `"max_abs_diff"`, `"mean_abs_diff"`, `"std_diff"`: 이미 COL_로 정의됨

#### D. 문자열 값 (분석 유형 등, CATEGORY_ 또는 VALUE_ 접두사)
- `"Level"`, `"Delta"`, `"CrossValidation"`: 분석 유형 카테고리 값
- `"rate_pct"`, `"e_m"`, `"de_m"`, `"sum_daily_m"`: x_var, y_var 값으로 사용 (컬럼명 문자열)
- `f"dr_m_lag{lag}"`: 동적 생성 문자열 (lag 값에 따라 변함)

#### E. 메타데이터 타입
- `"tqqq_rate_spread_lab"`: meta.json의 csv_type (KEY_ 접두사)

#### F. UI 레이블/설명 (DISPLAY_ 접두사)
- 다양한 마크다운 문자열 (분석 제목, 설명, 안내 등)
- 차트 레이블: `"차이 분포"`, `"차이 (%)"`, `"빈도"`, `"월말 누적 오차 (%)"`, `"월간 변화 (%)"` 등

### 2.3 기존 상수명 변경 필요 여부

대부분의 상수가 이미 올바른 명명 규칙을 따르고 있으므로 **기존 상수명은 유지**한다.
단, 누락된 상수들을 추가하고 하드코딩을 전수 제거한다.

## 3. 리팩토링 전략

### 3.1 상수 추가 원칙

루트 CLAUDE.md의 상수 명명 규칙을 엄격히 준수하고, 필요 시 프로젝트별 규칙 추가:
- `COL_`: DataFrame/CSV 컬럼명 (임시 컬럼 포함)
- `KEY_`: 딕셔너리 키 (meta.json 타입 등 중요한 키)
- `KEY_TEMP_`: 내부 dict 생성용 임시 키 (rename 전 단계, 오타 방지 목적)
- `DISPLAY_`: UI 표시 문자열 (섹션 타이틀, 차트 레이블, 설명)
- `PARAM_` 또는 `DEFAULT_`: 분석 파라미터 (최소 개월 수, top N, bins 등)
- `CATEGORY_VALUE_`: 카테고리 값 (Level, Delta, CrossValidation)

### 3.2 임시 컬럼 상수화 전략

**원칙**: 내부 임시 컬럼도 전역 상수로 승격하여 일관성 확보

예:
- `COL_TEMP_MONTH = "month"` (월별 집계용)
- `COL_TEMP_DAILY_SIGNED = "daily_signed"` (일일 증분 signed)
- `COL_TEMP_SUM_DAILY_M_CALC = "sum_daily_m_calc"` (계산용 임시)
- `COL_TEMP_DIFF = "diff"` (교차검증 차이)
- `COL_TEMP_ABS_DIFF = "abs_diff"` (절댓값)
- `COL_TEMP_DR_LAG = "dr_lag"` (Delta 분석 임시)

**근거**: 컬럼명 불일치 방지, 리팩토링 시 검색/교체 용이성

### 3.3 분석 유형 카테고리 값 상수화

요약 통계 CSV의 "분석유형" 컬럼에 들어갈 값들:
- `CATEGORY_VALUE_LEVEL = "Level"`
- `CATEGORY_VALUE_DELTA = "Delta"`
- `CATEGORY_VALUE_CROSS_VALIDATION = "CrossValidation"`

### 3.4 메타데이터 타입 상수화

- `KEY_META_TYPE_RATE_SPREAD_LAB = "tqqq_rate_spread_lab"`

### 3.5 분석 파라미터 상수화

- `PARAM_MIN_MONTHS_FOR_ANALYSIS = 13` (Rolling 12M 상관 계산 위해 최소 13개월)
- `PARAM_TOP_N_CROSS_VALIDATION = 5` (교차검증 상위 표시 개수)
- `PARAM_HISTOGRAM_BINS = 30` (히스토그램 기본 bins)
- `PARAM_LAG_OPTIONS = [0, 1, 2]` (Delta 분석 lag 선택지)
- `PARAM_STREAMLIT_COLUMNS = 3` (요약 통계 표시용 컬럼 개수)

### 3.6 UI 레이블 상수화 전략

UI 레이블은 매우 많으므로 **핵심 레이블만 상수화**하고, 일회성 마크다운 문자열은 하드코딩 유지 (YAGNI 원칙).

**상수화 대상** (재사용되는 핵심 레이블):
- `DISPLAY_CHART_DIFF_DISTRIBUTION = "차이 분포"`
- `DISPLAY_AXIS_DIFF_PCT = "차이 (%)"`
- `DISPLAY_AXIS_FREQUENCY = "빈도"`
- `DISPLAY_ERROR_END_OF_MONTH_PCT = "월말 누적 오차 (%)"`
- `DISPLAY_DELTA_MONTHLY_PCT = "월간 변화 (%)"`

**하드코딩 유지** (일회성 문자열):
- 페이지 타이틀, 섹션 설명, 안내 메시지 등

### 3.7 동적 생성 문자열 처리

`f"dr_m_lag{lag}"` 같은 동적 생성 문자열은 상수화 불가 → **헬퍼 함수 제공**:
```python
def get_dr_lag_var_name(lag: int) -> str:
    """Delta 분석용 dr_lag 변수명을 생성한다."""
    return f"dr_m_lag{lag}"
```

또는 템플릿 상수:
```python
TEMPLATE_DR_LAG_VAR = "dr_m_lag{}"  # .format(lag) 사용
```

## 4. 구현 계획

### 4.1 constants.py 수정

**추가할 상수 (섹션별 구분)**:

#### (1) 임시/중간 계산 컬럼명
```python
# --- 임시/중간 계산 컬럼명 (내부 처리용) ---
COL_TEMP_MONTH = "month"  # 월별 집계용 Period 컬럼
COL_TEMP_DAILY_SIGNED = "daily_signed"  # 일일 증분 signed 로그오차
COL_TEMP_SUM_DAILY_M_CALC = "sum_daily_m_calc"  # sum_daily_m 계산용 임시
COL_TEMP_DIFF = "diff"  # de_m - sum_daily_m 차이
COL_TEMP_ABS_DIFF = "abs_diff"  # diff 절댓값
COL_TEMP_DR_LAG = "dr_lag"  # Delta 분석용 임시 lag 컬럼
```

#### (2) 분석 파라미터
```python
# --- 분석 파라미터 (Rate Spread Lab) ---
PARAM_MIN_MONTHS_FOR_ANALYSIS = 13  # Rolling 12M 상관 계산 위해 최소 13개월
PARAM_TOP_N_CROSS_VALIDATION = 5  # 교차검증 상위 표시 개수
PARAM_HISTOGRAM_BINS = 30  # 히스토그램 기본 bins
PARAM_LAG_OPTIONS = [0, 1, 2]  # Delta 분석 lag 선택지
PARAM_STREAMLIT_COLUMNS = 3  # 요약 통계 표시용 컬럼 개수
```

#### (3) 카테고리 값 (분석 유형)
```python
# --- 요약 통계 카테고리 값 ---
CATEGORY_VALUE_LEVEL = "Level"  # Level 분석
CATEGORY_VALUE_DELTA = "Delta"  # Delta 분석
CATEGORY_VALUE_CROSS_VALIDATION = "CrossValidation"  # 교차검증
```

#### (4) 메타데이터 및 임시 dict 키
```python
# --- 메타데이터 타입 키 ---
KEY_META_TYPE_RATE_SPREAD_LAB = "tqqq_rate_spread_lab"  # Rate Spread Lab CSV 타입

# --- 요약 통계 dict 생성용 임시 키 (rename 전 단계) ---
# 용도: save_summary_statistics에서 DataFrame 생성 시 dict 키로 사용
# 최종 CSV 컬럼명(COL_)과 구분하기 위해 KEY_TEMP_ 접두사 사용
KEY_TEMP_CATEGORY = "category"  # 분석 유형 임시 키
KEY_TEMP_X_VAR = "x_var"  # X축 변수 임시 키
KEY_TEMP_Y_VAR = "y_var"  # Y축 변수 임시 키
KEY_TEMP_LAG = "lag"  # 시차 임시 키
KEY_TEMP_N = "n"  # 샘플 수 임시 키
KEY_TEMP_CORR = "corr"  # 상관계수 임시 키
KEY_TEMP_SLOPE = "slope"  # 기울기 임시 키
KEY_TEMP_INTERCEPT = "intercept"  # 절편 임시 키
KEY_TEMP_MAX_ABS_DIFF = "max_abs_diff"  # 최대 절댓값 차이 임시 키
KEY_TEMP_MEAN_ABS_DIFF = "mean_abs_diff"  # 평균 절댓값 차이 임시 키
KEY_TEMP_STD_DIFF = "std_diff"  # 표준편차 임시 키
```

#### (5) UI 레이블 (핵심만)
```python
# --- UI 표시 레이블 (Rate Spread Lab) ---
DISPLAY_CHART_DIFF_DISTRIBUTION = "차이 분포"  # 히스토그램 차트명
DISPLAY_AXIS_DIFF_PCT = "차이 (%)"  # X축 레이블
DISPLAY_AXIS_FREQUENCY = "빈도"  # Y축 레이블
DISPLAY_ERROR_END_OF_MONTH_PCT = "월말 누적 오차 (%)"  # Level 차트 y축
DISPLAY_DELTA_MONTHLY_PCT = "월간 변화 (%)"  # Delta 차트 y축
```

#### (6) 변수명 템플릿
```python
# --- 동적 변수명 템플릿 ---
TEMPLATE_DR_LAG_VAR = "dr_m_lag{}"  # Delta 분석용 dr_lag 변수명 템플릿 (.format(lag) 사용)
```

**__all__ 업데이트**:
추가된 상수를 모두 `__all__` 리스트에 포함.

### 4.2 streamlit_rate_spread_lab.py 수정

**하드코딩 제거 대상** (라인별):

| 라인 | 기존 하드코딩 | 새 상수 |
|------|--------------|---------|
| 130 | `"daily_signed"` | `COL_TEMP_DAILY_SIGNED` |
| 139 | `13` | `PARAM_MIN_MONTHS_FOR_ANALYSIS` |
| 145 | `"month"` | `COL_TEMP_MONTH` |
| 146 | `"daily_signed"` | `COL_TEMP_DAILY_SIGNED` |
| 148 | `"sum_daily_m_calc"` | `COL_TEMP_SUM_DAILY_M_CALC` |
| 148 | `"daily_signed"` | `COL_TEMP_DAILY_SIGNED` |
| 149 | `"daily_signed"` | `COL_TEMP_DAILY_SIGNED` |
| 152 | `"month"` | `COL_TEMP_MONTH` |
| 155 | `"sum_daily_m"` | (이미 상수 `COL_SUM_DAILY_M` 존재, import 추가) |
| 155 | `"sum_daily_m_calc"` | `COL_TEMP_SUM_DAILY_M_CALC` |
| 156 | `"sum_daily_m_calc"` | `COL_TEMP_SUM_DAILY_M_CALC` |
| 189 | `"de_m", "sum_daily_m"` | `COL_DE_M, COL_SUM_DAILY_M` (import 추가) |
| 197 | `"diff"` | `COL_TEMP_DIFF` |
| 200 | `"diff"` | `COL_TEMP_DIFF` |
| 211 | `"abs_diff"` | `COL_TEMP_ABS_DIFF` |
| 211 | `"diff"` | `COL_TEMP_DIFF` |
| 212 | `5` | `PARAM_TOP_N_CROSS_VALIDATION` |
| 212 | `"abs_diff"` | `COL_TEMP_ABS_DIFF` |
| 213 | `"month", "de_m", "sum_daily_m", "diff", "abs_diff"` | `COL_TEMP_MONTH, COL_DE_M, COL_SUM_DAILY_M, COL_TEMP_DIFF, COL_TEMP_ABS_DIFF` |
| 221 | `"diff"` | `COL_TEMP_DIFF` |
| 222 | `30` | `PARAM_HISTOGRAM_BINS` |
| 223 | `"차이 분포"` | `DISPLAY_CHART_DIFF_DISTRIBUTION` |
| 229 | `"차이 (%)"` | `DISPLAY_AXIS_DIFF_PCT` |
| 230 | `"빈도"` | `DISPLAY_AXIS_FREQUENCY` |
| 274 | `"dr_lag1"` | (이미 상수 `COL_DR_LAG1` 존재하지만 임시 컬럼명으로 사용, 주의 필요) |
| 274 | `"dr_m"` | (이미 상수 `COL_DR_M` 존재, import 추가) |
| 275 | `"dr_lag2"` | (이미 상수 `COL_DR_LAG2` 존재하지만 임시 컬럼명으로 사용, 주의 필요) |
| 275 | `"dr_m"` | `COL_DR_M` (import 추가) |
| 299 | `"month"` | `COL_TEMP_MONTH` |
| 300 | `"month"` | `COL_TEMP_MONTH` |
| 304 | `"tqqq_rate_spread_lab"` | `KEY_META_TYPE_RATE_SPREAD_LAB` |
| 315 | `3` | `PARAM_STREAMLIT_COLUMNS` |
| 319 | `"month"` | `COL_TEMP_MONTH` |
| 319 | `"month"` | `COL_TEMP_MONTH` |
| 322 | `"rate_pct"` | `COL_RATE_PCT` (import 추가) |
| 323 | `"rate_pct"` | `COL_RATE_PCT` |
| 326 | `"e_m"` | `COL_E_M` (import 추가) |
| 327 | `"e_m"` | `COL_E_M` |
| 363 | `"e_m"` | `COL_E_M` |
| 363 | `"월말 누적 오차 (%)"` | `DISPLAY_ERROR_END_OF_MONTH_PCT` |
| 384 | `"de_m"` | `COL_DE_M` |
| 385 | `"월간 변화 (%)"` | `DISPLAY_DELTA_MONTHLY_PCT` |
| 388 | `[0, 1, 2]` | `PARAM_LAG_OPTIONS` |

**주의 사항**:
- 274-275 라인의 `"dr_lag1"`, `"dr_lag2"`는 DataFrame 컬럼명으로 생성하는 것이므로, CSV 컬럼명 `COL_DR_LAG1`, `COL_DR_LAG2`와는 다른 맥락이다.
  - **해결**: 내부 임시 컬럼명과 CSV 출력 컬럼명이 같으므로 상수 재사용 가능.
  - 하지만 더 명확하게 하려면 `COL_DR_LAG1`, `COL_DR_LAG2`를 그대로 사용하되, 주석으로 "임시 컬럼이자 CSV 출력 컬럼명" 명시.

### 4.3 analysis_helpers.py 수정

**하드코딩 제거 대상** (주요 라인):

| 라인 | 기존 하드코딩 | 새 상수 |
|------|--------------|---------|
| 269 | `"month"` | `COL_TEMP_MONTH` |
| 275 | `"month"` | `COL_TEMP_MONTH` |
| 276 | `"e_m"` | `COL_E_M` (이미 import됨) |
| 280 | `"de_m"`, `"e_m"` | `COL_DE_M`, `COL_E_M` (이미 import됨) |
| 285 | `"sum_daily_m"` | `COL_SUM_DAILY_M` (이미 import됨) |
| 292 | `"month"` | `COL_TEMP_MONTH` |
| 295 | `"month"`, `"VALUE"` | `COL_TEMP_MONTH`, `COL_FFR_VALUE` (VALUE는 FFR_VALUE와 같음, import 필요) |
| 298 | `"rate_pct"` | `COL_RATE_PCT` (이미 import됨) |
| 299 | `"VALUE"` | `COL_FFR_VALUE` (import 필요) |
| 302 | `"dr_m"` | `COL_DR_M` (이미 import됨) |
| 305 | `"VALUE"` | `COL_FFR_VALUE` |
| 309 | `"rate_pct"` | `COL_RATE_PCT` |
| 312 | `"month"` | `COL_TEMP_MONTH` |
| 318 | `"rate_pct"`, `"dr_m"` | `COL_RATE_PCT`, `COL_DR_M` |
| 431 | `"month", "rate_pct", "dr_m", "e_m", "de_m", "sum_daily_m"` | `COL_TEMP_MONTH, COL_RATE_PCT, COL_DR_M, COL_E_M, COL_DE_M, COL_SUM_DAILY_M` |
| 437 | `"dr_lag1", "dr_lag2"` | `COL_DR_LAG1, COL_DR_LAG2` (이미 import됨) |
| 442 | `"month"` | `COL_TEMP_MONTH` |
| 445 | `"month"` | `COL_TEMP_MONTH` |
| 493 | `"month", "rate_pct", "dr_m", "e_m", "de_m", "sum_daily_m"` | `COL_TEMP_MONTH, COL_RATE_PCT, COL_DR_M, COL_E_M, COL_DE_M, COL_SUM_DAILY_M` |
| 499 | `"rate_pct", "e_m"` | `COL_RATE_PCT, COL_E_M` |
| 503 | `"rate_pct"`, `"e_m"` | `COL_RATE_PCT`, `COL_E_M` |
| 510-517 | `"category": "Level"` 등 | 키: `KEY_TEMP_CATEGORY` 등, 값: `CATEGORY_VALUE_LEVEL` |
| 535-542 | `"category": "Delta"` 등 | 키: `KEY_TEMP_CATEGORY` 등, 값: `CATEGORY_VALUE_DELTA` |
| 551-561 | `"category": "Delta"` 등 | 키: `KEY_TEMP_CATEGORY` 등, 값: `CATEGORY_VALUE_DELTA` |
| 570-585 | `"category": "CrossValidation"` 등 | 키: `KEY_TEMP_CATEGORY` 등, 값: `CATEGORY_VALUE_CROSS_VALIDATION` |
| 602-614 | `{"category": COL_CATEGORY, ...}` | 키: `KEY_TEMP_CATEGORY`, 값: `COL_CATEGORY` (rename_map) |
| 527 | `"dr_lag"` | `COL_TEMP_DR_LAG` |
| 528 | `"dr_lag", "de_m"` | `COL_TEMP_DR_LAG, COL_DE_M` |
| 531 | `"dr_lag"` | `COL_TEMP_DR_LAG` |
| 536, 554 | `f"dr_m_lag{lag}"` | `TEMPLATE_DR_LAG_VAR.format(lag)` |
| 547 | `"dr_lag", "sum_daily_m"` | `COL_TEMP_DR_LAG, COL_SUM_DAILY_M` |
| 549 | `"dr_lag"`, `"sum_daily_m"` | `COL_TEMP_DR_LAG`, `COL_SUM_DAILY_M` |
| 567 | `"de_m", "sum_daily_m"` | `COL_DE_M, COL_SUM_DAILY_M` |
| 569 | `"de_m"`, `"sum_daily_m"` | `COL_DE_M`, `COL_SUM_DAILY_M` |

**딕셔너리 키 vs 값 처리** (사용자 결정 반영):
- **딕셔너리 키** (`"category"`, `"x_var"` 등): `KEY_TEMP_` 상수로 변경 (오타 방지, 5개 위치에서 반복 사용)
- **딕셔너리 값** (`"Level"`, `"Delta"` 등 카테고리 값): `CATEGORY_VALUE_` 상수로 변경
- **딕셔너리 값** (컬럼명 문자열 `"rate_pct"`, `"e_m"`, `"de_m"`, `"sum_daily_m"`): 문자열 그대로 유지 (x_var, y_var에 들어가는 값)

**수정 필요**:
- 510-517, 533-542, 551-561, 570-585 라인의 딕셔너리 생성 로직에서:
  - 키: `KEY_TEMP_CATEGORY`, `KEY_TEMP_X_VAR` 등 상수 사용
  - 값 (카테고리): `CATEGORY_VALUE_LEVEL`, `CATEGORY_VALUE_DELTA`, `CATEGORY_VALUE_CROSS_VALIDATION` 사용
  - 값 (컬럼명 문자열): `"rate_pct"`, `"e_m"` 등 하드코딩 유지
- 602-614 라인의 rename_map:
  - 키: `KEY_TEMP_CATEGORY`, `KEY_TEMP_X_VAR` 등 상수 사용
  - 값: `COL_CATEGORY`, `COL_X_VAR` 등 상수 사용

## 5. 순환 import 방지 확인

**현재 import 구조**:
- `constants.py`: 다른 모듈 import 없음 (common_constants만 import)
- `analysis_helpers.py`: `constants.py` import
- `streamlit_rate_spread_lab.py`: `constants.py`, `analysis_helpers` import

**순환 가능성**: 없음 (constants.py는 다른 모듈을 import하지 않음)

## 6. 검증 방법

### 6.1 기능 동일성 검증
- 리팩토링 전후 앱 실행 결과 (차트, CSV 값) 비교
- `tqqq_rate_spread_lab_monthly.csv`, `tqqq_rate_spread_lab_summary.csv` 내용 일치 확인

### 6.2 하드코딩 제거 확인
- `grep -n '["'\''][a-z_]*["'\'']' streamlit_rate_spread_lab.py analysis_helpers.py` 실행하여 문자열 리터럴 대폭 감소 확인
- 매직 넘버 검색: `grep -n '[^a-zA-Z_][0-9][0-9]*[^.]' streamlit_rate_spread_lab.py`

### 6.3 타입 체크 및 린트
- `poetry run python validate_project.py --only-pyright` (타입 에러 없음)
- `poetry run python validate_project.py --only-lint` (린트 에러 없음)

### 6.4 앱 실행 테스트
```bash
poetry run streamlit run scripts/tqqq/streamlit_rate_spread_lab.py
```
- 모든 탭 (핵심, 델타, 교차검증) 정상 동작 확인
- CSV 저장 확인
- 차트 정상 표시 확인

## 7. 주요 파일 경로

- `/home/leeyubeen/workspace/quant/src/qbt/tqqq/constants.py` (상수 정의)
- `/home/leeyubeen/workspace/quant/scripts/tqqq/streamlit_rate_spread_lab.py` (CLI 앱)
- `/home/leeyubeen/workspace/quant/src/qbt/tqqq/analysis_helpers.py` (비즈니스 로직)

## 8. 리팩토링 순서

1. **constants.py 수정**: 누락 상수 추가, __all__ 업데이트
2. **analysis_helpers.py 수정**: 하드코딩 → 상수 참조 변경, import 추가
3. **streamlit_rate_spread_lab.py 수정**: 하드코딩 → 상수 참조 변경, import 추가
4. **검증**:
   - PyRight 타입 체크
   - Ruff 린트
   - Streamlit 앱 실행 및 동작 확인
   - CSV 결과 비교

## 9. 예상 효과

- **단일 진실 소스 (SSOT)**: 모든 컬럼명/키/파라미터가 constants.py에 집중
- **변경 누락 방지**: 컬럼명 변경 시 한 곳만 수정하면 전체 반영
- **타입 안정성 향상**: 문자열 오타 방지 (IDE 자동완성, 타입 체커 지원)
- **가독성 향상**: 하드코딩 대신 명확한 상수명 사용
- **유지보수 비용 감소**: 이후 FutureWarning 해결, 모델용 CSV 스키마 고정 등 작업 시 일관성 보장

## 10. 제외 사항

- **일회성 UI 문자열**: 마크다운 설명, 안내 메시지 등은 하드코딩 유지 (YAGNI 원칙, 사용자 결정)
- **상수 기본값**: `min_months_for_analysis=13` 같은 함수 파라미터 기본값은 상수화하되, 호출 시 명시적으로 전달
- **딕셔너리 값 (컬럼명 문자열)**: `"rate_pct"`, `"e_m"` 등 x_var, y_var 값으로 들어가는 컬럼명은 하드코딩 유지 (변수명 자체이므로)

## 11. 명명 규칙 보완 (프로젝트 문서 업데이트)

이번 리팩토링에서 추가된 `KEY_TEMP_` 접두사 규칙을 프로젝트 문서에 반영:

**루트 CLAUDE.md 또는 src/qbt/tqqq/CLAUDE.md 업데이트**:
```markdown
- KEY_: 딕셔너리 키 (meta.json 타입 등 중요한 키)
- KEY_TEMP_: 내부 dict 생성용 임시 키 (rename 전 단계, 오타 방지 목적)
  - 예: KEY_TEMP_CATEGORY, KEY_TEMP_X_VAR (save_summary_statistics에서 사용)
  - 최종 CSV 컬럼명(COL_CATEGORY, COL_X_VAR)과 구분하기 위해 별도 접두사 사용
```

**문서 업데이트 위치**: `/home/leeyubeen/workspace/quant/src/qbt/tqqq/CLAUDE.md` (TQQQ 도메인 특화 규칙)
