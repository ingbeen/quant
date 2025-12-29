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

__all__ = [
    "DISPLAY_DATE",
    "FFR_DATA_PATH",
    "TQQQ_DATA_PATH",
    "TQQQ_SYNTHETIC_PATH",
    "TQQQ_VALIDATION_PATH",
    "TQQQ_DAILY_COMPARISON_PATH",
    # (아래에 정의되는 상수들도 __all__에 포함)
]

# --- 레버리지 상품 스펙 ---
DEFAULT_LEVERAGE_MULTIPLIER = 3.0  # TQQQ 3배 레버리지
DEFAULT_SYNTHETIC_INITIAL_PRICE = 200.0  # 합성 데이터 초기 가격

# ============================================================
# 비용 모델 파라미터
# ============================================================

# --- 기본값 ---
DEFAULT_FUNDING_SPREAD = 0.004  # FFR 스프레드 비율 (예시 0.004 = 0.4%)

# --- 그리드 서치 범위 ---
DEFAULT_SPREAD_RANGE = (0.004, 0.008)  # 스프레드 범위 (%)
DEFAULT_SPREAD_STEP = 0.0005  # 스프레드 증분 (%)

# --- 데이터 검증 및 결과 제한 ---
MAX_FFR_MONTHS_DIFF = 2  # FFR 데이터 최대 월 차이 (개월)
MAX_EXPENSE_MONTHS_DIFF = 12  # Expense Ratio 데이터 최대 월 차이 (개월)
MAX_TOP_STRATEGIES = 50  # find_optimal_cost_model 반환 상위 전략 수

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
COL_CUMUL_MULTIPLE_LOG_DIFF = "누적배수_로그차이(%)"

# 검증 결과 컬럼
COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE = "누적배수로그차이_RMSE(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN = "누적배수로그차이_평균(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_MAX = "누적배수로그차이_최대(%)"

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
    COL_CUMUL_MULTIPLE_LOG_DIFF,
]

# --- 출력용 레이블 (사용자 표시용) ---
DISPLAY_SPREAD = "Funding Spread"

# --- 딕셔너리 키 (내부 사용) ---

# 비용 모델
KEY_SPREAD = "spread"

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
