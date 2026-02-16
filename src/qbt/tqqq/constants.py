"""
레버리지 ETF 시뮬레이션 도메인 상수

레버리지 ETF 시뮬레이션에서 사용하는 기본값과 검증 임계값을 정의한다.
- 경로 및 스펙 설정 (데이터 파일, 결과 파일, 레버리지 상품 스펙)
- 비용 모델 파라미터 (기본값, 그리드 서치, 검증)
- 데이터 컬럼 및 키 정의 (CSV 컬럼명, 출력 레이블, 딕셔너리 키)
"""

from typing import Final

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
TQQQ_DATA_PATH: Final = STOCK_DIR / "TQQQ_max.csv"
TQQQ_SYNTHETIC_PATH: Final = STOCK_DIR / "TQQQ_synthetic_max.csv"

# 연방기금금리 월별 데이터 파일 경로
FFR_DATA_PATH: Final = ETC_DIR / "federal_funds_rate_monthly.csv"

# 운용비율(Expense Ratio) 월별 데이터 파일 경로
EXPENSE_RATIO_DATA_PATH: Final = ETC_DIR / "tqqq_net_expense_ratio_monthly.csv"

# TQQQ 시뮬레이션 관련 결과 파일 경로
TQQQ_DAILY_COMPARISON_PATH: Final = RESULTS_DIR / "tqqq_daily_comparison.csv"

# --- 스프레드 검증 결과 파일 경로 (spread_lab 하위폴더) ---
SPREAD_LAB_DIR: Final = RESULTS_DIR / "spread_lab"
TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH: Final = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_monthly.csv"
TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH: Final = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_summary.csv"
TQQQ_RATE_SPREAD_LAB_MODEL_PATH: Final = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_model.csv"
SOFTPLUS_TUNING_CSV_PATH: Final = SPREAD_LAB_DIR / "tqqq_softplus_tuning.csv"
SOFTPLUS_SPREAD_SERIES_STATIC_PATH: Final = SPREAD_LAB_DIR / "tqqq_softplus_spread_series_static.csv"

__all__ = [
    # 경로
    "DISPLAY_DATE",
    "FFR_DATA_PATH",
    "EXPENSE_RATIO_DATA_PATH",
    "TQQQ_DATA_PATH",
    "TQQQ_SYNTHETIC_PATH",
    "TQQQ_DAILY_COMPARISON_PATH",
    "SPREAD_LAB_DIR",
    "TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH",
    "TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH",
    "TQQQ_RATE_SPREAD_LAB_MODEL_PATH",
    "SOFTPLUS_TUNING_CSV_PATH",
    "SOFTPLUS_SPREAD_SERIES_STATIC_PATH",
    # 레버리지 상품 스펙
    "DEFAULT_LEVERAGE_MULTIPLIER",
    "DEFAULT_SYNTHETIC_INITIAL_PRICE",
    # 비용 모델 파라미터
    "DEFAULT_FUNDING_SPREAD",
    "DEFAULT_PRE_LISTING_EXPENSE_RATIO",
    "MAX_EXPENSE_MONTHS_DIFF",
    "MAX_FFR_MONTHS_DIFF",
    # CSV 컬럼명 (내부용 영문 토큰)
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
    "COL_CUMUL_MULTIPLE_LOG_DIFF_ABS",
    "COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED",
    "COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE",
    "COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN",
    "COL_CUMUL_MULTIPLE_LOG_DIFF_MAX",
    # Rate Spread Lab 내부 컬럼 (영문 토큰)
    "COL_MONTH",
    "COL_RATE_PCT",
    "COL_DR_M",
    "COL_E_M",
    "COL_DE_M",
    "COL_SUM_DAILY_M",
    "COL_DR_LAG1",
    "COL_DR_LAG2",
    "COL_DAILY_SIGNED",
    # UI 레이블
    "DISPLAY_ERROR_END_OF_MONTH_PCT",
    # 딕셔너리 키
    "KEY_SPREAD",
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
    # 분석 기본값 파라미터 (공유)
    "DEFAULT_MIN_MONTHS_FOR_ANALYSIS",
    "DEFAULT_TOP_N_CROSS_VALIDATION",
    "DEFAULT_ROLLING_WINDOW",
    # Softplus 동적 스프레드 모델 파라미터
    "DEFAULT_SOFTPLUS_A",
    "DEFAULT_SOFTPLUS_B",
    "SOFTPLUS_GRID_STAGE1_A_RANGE",
    "SOFTPLUS_GRID_STAGE1_A_STEP",
    "SOFTPLUS_GRID_STAGE1_B_RANGE",
    "SOFTPLUS_GRID_STAGE1_B_STEP",
    "SOFTPLUS_GRID_STAGE2_A_DELTA",
    "SOFTPLUS_GRID_STAGE2_A_STEP",
    "SOFTPLUS_GRID_STAGE2_B_DELTA",
    "SOFTPLUS_GRID_STAGE2_B_STEP",
    # 워크포워드 검증 파라미터
    "DEFAULT_TRAIN_WINDOW_MONTHS",
    "WALKFORWARD_LOCAL_REFINE_A_DELTA",
    "WALKFORWARD_LOCAL_REFINE_A_STEP",
    "WALKFORWARD_LOCAL_REFINE_B_DELTA",
    "WALKFORWARD_LOCAL_REFINE_B_STEP",
    "TQQQ_WALKFORWARD_PATH",
    "TQQQ_WALKFORWARD_SUMMARY_PATH",
    # b 고정 워크포워드 결과 경로
    "TQQQ_WALKFORWARD_FIXED_B_PATH",
    "TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH",
    # 완전 고정 (a,b) 워크포워드 결과 경로
    "TQQQ_WALKFORWARD_FIXED_AB_PATH",
    "TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH",
    # 금리 구간별 RMSE 분해
    "DEFAULT_RATE_BOUNDARY_PCT",
]

# --- 레버리지 상품 스펙 ---
DEFAULT_LEVERAGE_MULTIPLIER: Final = 3.0  # TQQQ 3배 레버리지
DEFAULT_SYNTHETIC_INITIAL_PRICE: Final = 200.0  # 합성 데이터 초기 가격

# ============================================================
# 비용 모델 파라미터
# ============================================================

# --- 기본값 ---
DEFAULT_FUNDING_SPREAD: Final = 0.0034  # FFR 스프레드 비율 (예시 0.004 = 0.4%)
DEFAULT_PRE_LISTING_EXPENSE_RATIO: Final = 0.0095  # TQQQ 상장 이전 운용비율 가정값 (0.0095 = 0.95%)

# --- 데이터 검증 ---
MAX_EXPENSE_MONTHS_DIFF: Final = 12  # Expense Ratio 데이터 최대 월 차이 (개월)
MAX_FFR_MONTHS_DIFF: Final = 2  # FFR 데이터 최대 월 차이 (개월)

# ============================================================
# 분석 기본값 파라미터 (공유)
# ============================================================

DEFAULT_MIN_MONTHS_FOR_ANALYSIS: Final = 13  # Rolling 12M 상관 계산 위해 최소 13개월
DEFAULT_TOP_N_CROSS_VALIDATION: Final = 5  # 교차검증 상위 표시 개수
DEFAULT_ROLLING_WINDOW: Final = 12  # Rolling 상관 계산 window (12개월)

# ============================================================
# Softplus 동적 스프레드 모델 파라미터
# ============================================================

# --- 전체기간 최적 파라미터 (과최적화 검증 완료) ---
DEFAULT_SOFTPLUS_A: Final = -6.1  # softplus 절편 파라미터
DEFAULT_SOFTPLUS_B: Final = 0.37  # softplus 기울기 파라미터

# --- 2-Stage Grid Search 범위 ---
# Stage 1: 조대 그리드 탐색
SOFTPLUS_GRID_STAGE1_A_RANGE: Final = (-10.0, -3.0)  # a 파라미터 범위
SOFTPLUS_GRID_STAGE1_A_STEP: Final = 0.25  # a 파라미터 증분
SOFTPLUS_GRID_STAGE1_B_RANGE: Final = (0.00, 1.50)  # b 파라미터 범위
SOFTPLUS_GRID_STAGE1_B_STEP: Final = 0.05  # b 파라미터 증분

# Stage 2: 정밀 그리드 탐색 (Stage 1 최적값 주변)
SOFTPLUS_GRID_STAGE2_A_DELTA: Final = 0.75  # a 파라미터 탐색 반경
SOFTPLUS_GRID_STAGE2_A_STEP: Final = 0.05  # a 파라미터 증분
SOFTPLUS_GRID_STAGE2_B_DELTA: Final = 0.30  # b 파라미터 탐색 반경
SOFTPLUS_GRID_STAGE2_B_STEP: Final = 0.02  # b 파라미터 증분

# ============================================================
# 워크포워드 검증 파라미터
# ============================================================

# --- 윈도우 설정 ---
DEFAULT_TRAIN_WINDOW_MONTHS: Final = 60  # 학습 기간 (60개월 = 5년)

# --- Local Refine 탐색 범위 ---
# 직전 월 최적값 주변에서 국소 탐색
WALKFORWARD_LOCAL_REFINE_A_DELTA: Final = 0.50  # a 파라미터 탐색 반경
WALKFORWARD_LOCAL_REFINE_A_STEP: Final = 0.05  # a 파라미터 증분 (21개 후보)
WALKFORWARD_LOCAL_REFINE_B_DELTA: Final = 0.15  # b 파라미터 탐색 반경
WALKFORWARD_LOCAL_REFINE_B_STEP: Final = 0.02  # b 파라미터 증분 (16개 후보)

# --- 워크포워드 결과 파일 경로 ---
TQQQ_WALKFORWARD_PATH: Final = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward.csv"
TQQQ_WALKFORWARD_SUMMARY_PATH: Final = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_summary.csv"

# --- b 고정 워크포워드 결과 파일 경로 ---
TQQQ_WALKFORWARD_FIXED_B_PATH: Final = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_fixed_b.csv"
TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH: Final = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_fixed_b_summary.csv"

# --- 완전 고정 (a,b) 워크포워드 결과 파일 경로 ---
TQQQ_WALKFORWARD_FIXED_AB_PATH: Final = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_fixed_ab.csv"
TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH: Final = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_fixed_ab_summary.csv"

# --- 금리 구간별 RMSE 분해 ---
DEFAULT_RATE_BOUNDARY_PCT: Final = 2.0  # 금리 구간 경계값 (%, 0~2% = 저금리, 2%+ = 고금리)

# ============================================================
# 데이터 컬럼 정의 (내부 계산용 영문 토큰)
# ============================================================

# --- FFR 데이터 ---
COL_FFR_DATE: Final = "DATE"  # FFR CSV의 날짜 컬럼
COL_FFR_VALUE: Final = "VALUE"  # FFR CSV의 금리 값 컬럼

# --- Expense Ratio 데이터 ---
COL_EXPENSE_DATE: Final = "DATE"  # Expense Ratio CSV의 날짜 컬럼
COL_EXPENSE_VALUE: Final = "VALUE"  # Expense Ratio CSV의 값 컬럼

# --- 일별 비교 데이터 - 종가 ---
COL_ACTUAL_CLOSE: Final = "종가_실제"
COL_SIMUL_CLOSE: Final = "종가_시뮬"

# --- 일별 비교 데이터 - 일일수익률 ---
COL_ACTUAL_DAILY_RETURN: Final = "일일수익률_실제"
COL_SIMUL_DAILY_RETURN: Final = "일일수익률_시뮬"
COL_DAILY_RETURN_ABS_DIFF: Final = "일일수익률_절대차이"

# --- 일별 비교 데이터 - 누적수익률 ---
COL_ACTUAL_CUMUL_RETURN: Final = "누적수익률_실제(%)"
COL_SIMUL_CUMUL_RETURN: Final = "누적수익률_시뮬(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_ABS: Final = "누적배수_로그차이_abs(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED: Final = "누적배수_로그차이_signed(%)"

# --- 검증 결과 컬럼 ---
COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE: Final = "누적배수로그차이_RMSE(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN: Final = "누적배수로그차이_평균(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_MAX: Final = "누적배수로그차이_최대(%)"

# --- Rate Spread Lab 내부 컬럼 (영문 토큰) ---
COL_MONTH: Final = "month"  # 월별 집계용 Period 컬럼
COL_RATE_PCT: Final = "rate_pct"  # 금리 수준 (%)
COL_DR_M: Final = "dr_m"  # 금리 변화 (%p)
COL_E_M: Final = "e_m"  # 월말 누적 오차 (%)
COL_DE_M: Final = "de_m"  # 월간 오차 변화 (%)
COL_SUM_DAILY_M: Final = "sum_daily_m"  # 일일 오차 월합 (%)
COL_DR_LAG1: Final = "dr_lag1"  # 금리 변화 Lag1 (%p)
COL_DR_LAG2: Final = "dr_lag2"  # 금리 변화 Lag2 (%p)
COL_DAILY_SIGNED: Final = "daily_signed"  # 일일 증분 signed 로그오차


# ============================================================
# 출력용 한글 헤더 (DISPLAY_)
# ============================================================

# --- UI 표시 레이블 ---
DISPLAY_ERROR_END_OF_MONTH_PCT: Final = "월말 누적 오차 (%)"  # Level 차트 y축

# ============================================================
# 딕셔너리 키 (KEY_)
# ============================================================

# --- 비용 모델 ---
KEY_SPREAD: Final = "spread"

# --- 겹치는 기간 정보 ---
KEY_OVERLAP_START: Final = "overlap_start"
KEY_OVERLAP_END: Final = "overlap_end"
KEY_OVERLAP_DAYS: Final = "overlap_days"

# --- 종가 정보 ---
KEY_FINAL_CLOSE_ACTUAL: Final = "final_close_actual"
KEY_FINAL_CLOSE_SIMULATED: Final = "final_close_simulated"
KEY_FINAL_CLOSE_REL_DIFF: Final = "final_close_rel_diff_pct"

# --- 누적수익률 ---
KEY_CUMULATIVE_RETURN_ACTUAL: Final = "cumulative_return_actual"
KEY_CUMULATIVE_RETURN_SIMULATED: Final = "cumulative_return_simulated"
KEY_CUMULATIVE_RETURN_REL_DIFF: Final = "cumulative_return_rel_diff_pct"

# --- 검증 지표 ---
KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN: Final = "cumul_multiple_log_diff_mean_pct"
KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE: Final = "cumul_multiple_log_diff_rmse_pct"
KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX: Final = "cumul_multiple_log_diff_max_pct"
