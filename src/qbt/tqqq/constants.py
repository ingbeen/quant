"""
레버리지 ETF 시뮬레이션 도메인 상수

레버리지 ETF 시뮬레이션에서 사용하는 기본값과 검증 임계값을 정의한다.
- 경로 및 스펙 설정 (데이터 파일, 결과 파일, 레버리지 상품 스펙)
- 비용 모델 파라미터 (기본값, 그리드 서치, 검증)
- 데이터 컬럼 및 키 정의 (CSV 컬럼명, 출력 레이블, 딕셔너리 키)
"""

from qbt.common_constants import (
    DISPLAY_DATE,
    ETC_DIR,
    RESULTS_DIR,
    STOCK_DIR,
)

# ============================================================
# 경로 및 스펙 설정
# ============================================================

# --- 데이터 파일 경로 ---
# TQQQ (3배 레버리지 ETF) 데이터 파일 경로
TQQQ_DATA_PATH = STOCK_DIR / "TQQQ_max.csv"
TQQQ_SYNTHETIC_PATH = STOCK_DIR / "TQQQ_synthetic_max.csv"

# 연방기금금리 월별 데이터 파일 경로
FFR_DATA_PATH = ETC_DIR / "federal_funds_rate_monthly.csv"

# 운용비율(Expense Ratio) 월별 데이터 파일 경로
EXPENSE_RATIO_DATA_PATH = ETC_DIR / "tqqq_net_expense_ratio_monthly.csv"

# TQQQ 시뮬레이션 관련 결과 파일 경로
TQQQ_VALIDATION_PATH = RESULTS_DIR / "tqqq_validation.csv"
TQQQ_DAILY_COMPARISON_PATH = RESULTS_DIR / "tqqq_daily_comparison.csv"
TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH = RESULTS_DIR / "tqqq_rate_spread_lab_monthly.csv"
TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH = RESULTS_DIR / "tqqq_rate_spread_lab_summary.csv"

__all__ = [
    # 경로
    "DISPLAY_DATE",
    "FFR_DATA_PATH",
    "EXPENSE_RATIO_DATA_PATH",
    "TQQQ_DATA_PATH",
    "TQQQ_SYNTHETIC_PATH",
    "TQQQ_VALIDATION_PATH",
    "TQQQ_DAILY_COMPARISON_PATH",
    "TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH",
    "TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH",
    # 레버리지 상품 스펙
    "DEFAULT_LEVERAGE_MULTIPLIER",
    "DEFAULT_SYNTHETIC_INITIAL_PRICE",
    # 비용 모델 파라미터
    "DEFAULT_FUNDING_SPREAD",
    "DEFAULT_SPREAD_RANGE",
    "DEFAULT_SPREAD_STEP",
    "MAX_FFR_MONTHS_DIFF",
    "MAX_EXPENSE_MONTHS_DIFF",
    "MAX_TOP_STRATEGIES",
    "INTEGRITY_TOLERANCE",
    # CSV 컬럼명
    "COL_FFR_DATE",
    "COL_FFR_VALUE",
    "COL_EXPENSE_DATE",
    "COL_EXPENSE_VALUE",
    "COL_ACTUAL_CLOSE",
    "COL_SIMUL_CLOSE",
    "COL_ACTUAL_DAILY_RETURN",
    "COL_SIMUL_DAILY_RETURN",
    "COL_DAILY_RETURN_ABS_DIFF",
    "COL_ACTUAL_CUMUL_RETURN",
    "COL_SIMUL_CUMUL_RETURN",
    "COL_CUMUL_RETURN_REL_DIFF",
    "COL_CUMUL_MULTIPLE_LOG_DIFF_ABS",
    "COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED",
    "COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE",
    "COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN",
    "COL_CUMUL_MULTIPLE_LOG_DIFF_MAX",
    "COL_MONTH",
    "COL_RATE_PCT",
    "COL_DR_M",
    "COL_E_M",
    "COL_DE_M",
    "COL_SUM_DAILY_M",
    "COL_DR_LAG1",
    "COL_DR_LAG2",
    "COL_CATEGORY",
    "COL_X_VAR",
    "COL_Y_VAR",
    "COL_LAG",
    "COL_N",
    "COL_CORR",
    "COL_SLOPE",
    "COL_INTERCEPT",
    "COL_MAX_ABS_DIFF",
    "COL_MEAN_ABS_DIFF",
    "COL_STD_DIFF",
    # 컬럼 그룹
    "COMPARISON_COLUMNS",
    # 임시 컬럼
    "COL_TEMP_MONTH",
    "COL_TEMP_DAILY_SIGNED",
    "COL_TEMP_SUM_DAILY_M_CALC",
    "COL_TEMP_DIFF",
    "COL_TEMP_ABS_DIFF",
    "COL_TEMP_DR_LAG",
    # UI 레이블
    "DISPLAY_SPREAD",
    "DISPLAY_CHART_DIFF_DISTRIBUTION",
    "DISPLAY_AXIS_DIFF_PCT",
    "DISPLAY_AXIS_FREQUENCY",
    "DISPLAY_ERROR_END_OF_MONTH_PCT",
    "DISPLAY_DELTA_MONTHLY_PCT",
    # 딕셔너리 키
    "KEY_SPREAD",
    "KEY_META_TYPE_RATE_SPREAD_LAB",
    "KEY_TEMP_CATEGORY",
    "KEY_TEMP_X_VAR",
    "KEY_TEMP_Y_VAR",
    "KEY_TEMP_LAG",
    "KEY_TEMP_N",
    "KEY_TEMP_CORR",
    "KEY_TEMP_SLOPE",
    "KEY_TEMP_INTERCEPT",
    "KEY_TEMP_MAX_ABS_DIFF",
    "KEY_TEMP_MEAN_ABS_DIFF",
    "KEY_TEMP_STD_DIFF",
    "KEY_OVERLAP_START",
    "KEY_OVERLAP_END",
    "KEY_OVERLAP_DAYS",
    "KEY_FINAL_CLOSE_ACTUAL",
    "KEY_FINAL_CLOSE_SIMULATED",
    "KEY_FINAL_CLOSE_REL_DIFF",
    "KEY_CUMULATIVE_RETURN_ACTUAL",
    "KEY_CUMULATIVE_RETURN_SIMULATED",
    "KEY_CUMULATIVE_RETURN_REL_DIFF",
    "KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN",
    "KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE",
    "KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX",
    # 분석 파라미터
    "PARAM_MIN_MONTHS_FOR_ANALYSIS",
    "PARAM_TOP_N_CROSS_VALIDATION",
    "PARAM_HISTOGRAM_BINS",
    "PARAM_LAG_OPTIONS",
    "PARAM_STREAMLIT_COLUMNS",
    # 카테고리 값
    "CATEGORY_VALUE_LEVEL",
    "CATEGORY_VALUE_DELTA",
    "CATEGORY_VALUE_CROSS_VALIDATION",
    # 템플릿
    "TEMPLATE_DR_LAG_VAR",
]

# --- 레버리지 상품 스펙 ---
DEFAULT_LEVERAGE_MULTIPLIER = 3.0  # TQQQ 3배 레버리지
DEFAULT_SYNTHETIC_INITIAL_PRICE = 200.0  # 합성 데이터 초기 가격

# ============================================================
# 비용 모델 파라미터
# ============================================================

# --- 기본값 ---
DEFAULT_FUNDING_SPREAD = 0.0034  # FFR 스프레드 비율 (예시 0.004 = 0.4%)

# --- 그리드 서치 범위 ---
DEFAULT_SPREAD_RANGE = (0.002, 0.01)  # 스프레드 범위 (%)
DEFAULT_SPREAD_STEP = 0.0001  # 스프레드 증분 (%)

# --- 데이터 검증 및 결과 제한 ---
MAX_FFR_MONTHS_DIFF = 2  # FFR 데이터 최대 월 차이 (개월)
MAX_EXPENSE_MONTHS_DIFF = 12  # Expense Ratio 데이터 최대 월 차이 (개월)
MAX_TOP_STRATEGIES = 50  # find_optimal_cost_model 반환 상위 전략 수

# 무결성 체크 허용 오차 (%)
# abs(signed)와 abs 컬럼의 최대 차이 허용값
# 결정 근거: 실제 데이터 관측값 (max_abs_diff=4.66e-14%) + 10% 여유 → 1e-6%로 확정
INTEGRITY_TOLERANCE = 1e-6  # 0.000001%

# ============================================================
# 데이터 컬럼 및 키 정의
# ============================================================

# --- CSV 컬럼명 (DataFrame 내부용) ---

# FFR 데이터
COL_FFR_DATE = "DATE"  # FFR CSV의 날짜 컬럼
COL_FFR_VALUE = "VALUE"  # FFR CSV의 금리 값 컬럼

# Expense Ratio 데이터
COL_EXPENSE_DATE = "DATE"  # Expense Ratio CSV의 날짜 컬럼
COL_EXPENSE_VALUE = "VALUE"  # Expense Ratio CSV의 값 컬럼

# 일별 비교 데이터 - 종가
COL_ACTUAL_CLOSE = "종가_실제"
COL_SIMUL_CLOSE = "종가_시뮬"

# 일별 비교 데이터 - 일일수익률
COL_ACTUAL_DAILY_RETURN = "일일수익률_실제"
COL_SIMUL_DAILY_RETURN = "일일수익률_시뮬"
COL_DAILY_RETURN_ABS_DIFF = "일일수익률_절대차이"

# 일별 비교 데이터 - 누적수익률
COL_ACTUAL_CUMUL_RETURN = "누적수익률_실제(%)"
COL_SIMUL_CUMUL_RETURN = "누적수익률_시뮬(%)"
COL_CUMUL_RETURN_REL_DIFF = "누적수익률_상대차이(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_ABS = "누적배수_로그차이_abs(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED = "누적배수_로그차이_signed(%)"

# 검증 결과 컬럼
COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE = "누적배수로그차이_RMSE(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN = "누적배수로그차이_평균(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_MAX = "누적배수로그차이_최대(%)"

# 월별 피처 CSV 컬럼명 (Rate Spread Lab)
COL_MONTH = "연월"
COL_RATE_PCT = "금리수준(%)"
COL_DR_M = "금리변화(%p)"
COL_E_M = "월말누적오차(%)"
COL_DE_M = "월간오차변화(%)"
COL_SUM_DAILY_M = "일일오차월합(%)"
COL_DR_LAG1 = "금리변화Lag1(%p)"
COL_DR_LAG2 = "금리변화Lag2(%p)"

# 요약 통계 CSV 컬럼명 (Rate Spread Lab)
COL_CATEGORY = "분석유형"
COL_X_VAR = "X축변수"
COL_Y_VAR = "Y축변수"
COL_LAG = "시차(월)"
COL_N = "샘플수"
COL_CORR = "상관계수"
COL_SLOPE = "기울기"
COL_INTERCEPT = "절편"
COL_MAX_ABS_DIFF = "최대절댓값차이(%)"
COL_MEAN_ABS_DIFF = "평균절댓값차이(%)"
COL_STD_DIFF = "표준편차(%)"

# 컬럼 그룹
COMPARISON_COLUMNS = [
    DISPLAY_DATE,
    COL_ACTUAL_CLOSE,
    COL_SIMUL_CLOSE,
    COL_ACTUAL_DAILY_RETURN,
    COL_SIMUL_DAILY_RETURN,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_ACTUAL_CUMUL_RETURN,
    COL_SIMUL_CUMUL_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
]

# --- 임시/중간 계산 컬럼명 (내부 처리용) ---
COL_TEMP_MONTH = "month"  # 월별 집계용 Period 컬럼
COL_TEMP_DAILY_SIGNED = "daily_signed"  # 일일 증분 signed 로그오차
COL_TEMP_SUM_DAILY_M_CALC = "sum_daily_m_calc"  # sum_daily_m 계산용 임시
COL_TEMP_DIFF = "diff"  # de_m - sum_daily_m 차이
COL_TEMP_ABS_DIFF = "abs_diff"  # diff 절댓값
COL_TEMP_DR_LAG = "dr_lag"  # Delta 분석용 임시 lag 컬럼

# --- 출력용 레이블 (사용자 표시용) ---
DISPLAY_SPREAD = "Funding Spread"

# --- UI 표시 레이블 (Rate Spread Lab) ---
DISPLAY_CHART_DIFF_DISTRIBUTION = "차이 분포"  # 히스토그램 차트명
DISPLAY_AXIS_DIFF_PCT = "차이 (%)"  # X축 레이블
DISPLAY_AXIS_FREQUENCY = "빈도"  # Y축 레이블
DISPLAY_ERROR_END_OF_MONTH_PCT = "월말 누적 오차 (%)"  # Level 차트 y축
DISPLAY_DELTA_MONTHLY_PCT = "월간 변화 (%)"  # Delta 차트 y축

# --- 딕셔너리 키 (내부 사용) ---

# 비용 모델
KEY_SPREAD = "spread"

# 메타데이터 타입
KEY_META_TYPE_RATE_SPREAD_LAB = "tqqq_rate_spread_lab"  # Rate Spread Lab CSV 타입

# 요약 통계 dict 생성용 임시 키 (rename 전 단계)
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

# 겹치는 기간 정보
KEY_OVERLAP_START = "overlap_start"
KEY_OVERLAP_END = "overlap_end"
KEY_OVERLAP_DAYS = "overlap_days"

# 종가 정보
KEY_FINAL_CLOSE_ACTUAL = "final_close_actual"
KEY_FINAL_CLOSE_SIMULATED = "final_close_simulated"
KEY_FINAL_CLOSE_REL_DIFF = "final_close_rel_diff_pct"

# 누적수익률
KEY_CUMULATIVE_RETURN_ACTUAL = "cumulative_return_actual"
KEY_CUMULATIVE_RETURN_SIMULATED = "cumulative_return_simulated"
KEY_CUMULATIVE_RETURN_REL_DIFF = "cumulative_return_rel_diff_pct"

# 검증 지표
KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN = "cumul_multiple_log_diff_mean_pct"
KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE = "cumul_multiple_log_diff_rmse_pct"
KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX = "cumul_multiple_log_diff_max_pct"

# ============================================================
# 분석 파라미터 (Rate Spread Lab)
# ============================================================

# --- 분석 파라미터 ---
PARAM_MIN_MONTHS_FOR_ANALYSIS = 13  # Rolling 12M 상관 계산 위해 최소 13개월
PARAM_TOP_N_CROSS_VALIDATION = 5  # 교차검증 상위 표시 개수
PARAM_HISTOGRAM_BINS = 30  # 히스토그램 기본 bins
PARAM_LAG_OPTIONS = [0, 1, 2]  # Delta 분석 lag 선택지
PARAM_STREAMLIT_COLUMNS = 3  # 요약 통계 표시용 컬럼 개수

# ============================================================
# 카테고리 값 (분석 유형)
# ============================================================

# --- 요약 통계 카테고리 값 ---
CATEGORY_VALUE_LEVEL = "Level"  # Level 분석
CATEGORY_VALUE_DELTA = "Delta"  # Delta 분석
CATEGORY_VALUE_CROSS_VALIDATION = "CrossValidation"  # 교차검증

# ============================================================
# 동적 변수명 템플릿
# ============================================================

# --- 동적 변수명 템플릿 ---
TEMPLATE_DR_LAG_VAR = "dr_m_lag{}"  # Delta 분석용 dr_lag 변수명 템플릿 (.format(lag) 사용)
