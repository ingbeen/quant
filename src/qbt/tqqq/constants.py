"""
레버리지 ETF 시뮬레이션 도메인 상수

레버리지 ETF 시뮬레이션에서 사용하는 기본값과 경로를 정의한다.
- 경로 및 스펙 설정 (데이터 파일, 결과 파일, 레버리지 상품 스펙)
- 비용 모델 파라미터 (기본값)
- 데이터 컬럼 및 키 정의 (CSV 컬럼명, 딕셔너리 키)
"""

from typing import Final

from qbt.common_constants import (
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    ETC_DIR,
    QLD_DATA_PATH,
    QLD_SYNTHETIC_DATA_PATH,
    STOCK_DIR,
    TQQQ_RESULTS_DIR,
    TQQQ_SYNTHETIC_DATA_PATH,
)

# ============================================================
# 경로 및 스펙 설정
# ============================================================

# --- 데이터 파일 경로 ---
# TQQQ (3배 레버리지 ETF) 데이터 파일 경로
TQQQ_DATA_PATH: Final = STOCK_DIR / "TQQQ_max.csv"

# 연방기금금리 월별 데이터 파일 경로
FFR_DATA_PATH: Final = ETC_DIR / "federal_funds_rate_monthly.csv"

# 운용비율(Expense Ratio) 월별 데이터 파일 경로
EXPENSE_RATIO_DATA_PATH: Final = ETC_DIR / "tqqq_net_expense_ratio_monthly.csv"

# TQQQ 시뮬레이션 관련 결과 파일 경로
TQQQ_DAILY_COMPARISON_PATH: Final = TQQQ_RESULTS_DIR / "tqqq_daily_comparison.csv"
QLD_DAILY_COMPARISON_PATH: Final = TQQQ_RESULTS_DIR / "qld_daily_comparison.csv"

# --- 레버리지 상품 스펙 ---
DEFAULT_LEVERAGE_MULTIPLIER: Final = 3.0  # TQQQ 3배 레버리지
LEVERAGE_2X: Final = 2.0  # QLD · SSO 2배 레버리지

# 일별 비교 상품 — (상품 이름, 실물 시세, 배율, 일별 비교 CSV)
DAILY_COMPARISON_TARGETS: Final = (
    ("TQQQ", TQQQ_DATA_PATH, DEFAULT_LEVERAGE_MULTIPLIER, TQQQ_DAILY_COMPARISON_PATH),
    ("QLD", QLD_DATA_PATH, LEVERAGE_2X, QLD_DAILY_COMPARISON_PATH),
)

# 합성 시세 파일 — 상품 이름: 생성 파일. 일별 비교로 검증한 상품만 합성
SYNTHETIC_DATA_PATHS: Final = {
    "TQQQ": TQQQ_SYNTHETIC_DATA_PATH,
    "QLD": QLD_SYNTHETIC_DATA_PATH,
}

# ============================================================
# 비용 모델 파라미터
# ============================================================

# --- 기본값 ---
DEFAULT_PRE_LISTING_EXPENSE_RATIO: Final = 0.0095  # TQQQ 상장 이전 운용비율 가정값 (0.0095 = 0.95%)

# ============================================================
# 분석 기본값 파라미터
# ============================================================

# 금리 변화 vs 오차 변화의 Rolling 상관 창 (개월) — 차트와 월별 집계의 최소 개월 수가 함께 쓴다
ROLLING_CORR_WINDOW_MONTHS: Final = 12

# ============================================================
# Softplus 동적 스프레드 모델 파라미터
# ============================================================

# --- 전체기간 튜닝 최적값 (스프레드 랩 튜닝 결과의 RMSE 최소 행) ---
DEFAULT_SOFTPLUS_A: Final = -6.1  # softplus 절편 파라미터
DEFAULT_SOFTPLUS_B: Final = 0.37  # softplus 기울기 파라미터

# ============================================================
# 데이터 컬럼 정의 (일별 비교 CSV 의 열은 한글 헤더 그대로)
# ============================================================

# --- FFR 데이터 ---
COL_FFR_DATE: Final = "DATE"  # FFR CSV의 날짜 컬럼
COL_FFR_VALUE: Final = "VALUE"  # FFR CSV의 금리 값 컬럼

# --- Expense Ratio 데이터 ---
COL_EXPENSE_DATE: Final = "DATE"  # Expense Ratio CSV의 날짜 컬럼
COL_EXPENSE_VALUE: Final = "VALUE"  # Expense Ratio CSV의 값 컬럼

# --- 일별 비교 데이터 - 시가 · 고가 · 저가 · 종가 ---
COL_ACTUAL_OPEN: Final = "시가_실제"
COL_SIMUL_OPEN: Final = "시가_시뮬"
COL_ACTUAL_HIGH: Final = "고가_실제"
COL_SIMUL_HIGH: Final = "고가_시뮬"
COL_ACTUAL_LOW: Final = "저가_실제"
COL_SIMUL_LOW: Final = "저가_시뮬"
COL_ACTUAL_CLOSE: Final = "종가_실제"
COL_SIMUL_CLOSE: Final = "종가_시뮬"

# 일별 비교의 가격 종류 — 이름: (시세 열, 실제 열, 시뮬 열). 이 순서가 CSV 열과 화면 선택지의 순서다
DAILY_COMPARISON_PRICES: Final = {
    "시가": (COL_OPEN, COL_ACTUAL_OPEN, COL_SIMUL_OPEN),
    "고가": (COL_HIGH, COL_ACTUAL_HIGH, COL_SIMUL_HIGH),
    "저가": (COL_LOW, COL_ACTUAL_LOW, COL_SIMUL_LOW),
    "종가": (COL_CLOSE, COL_ACTUAL_CLOSE, COL_SIMUL_CLOSE),
}

# --- 일별 비교 데이터 - 일일수익률 ---
COL_ACTUAL_DAILY_RETURN: Final = "일일수익률_실제"
COL_SIMUL_DAILY_RETURN: Final = "일일수익률_시뮬"
COL_DAILY_RETURN_ABS_DIFF: Final = "일일수익률_절대차이"

# --- 일별 비교 데이터 - 누적수익률 ---
COL_ACTUAL_CUMUL_RETURN: Final = "누적수익률_실제(%)"
COL_SIMUL_CUMUL_RETURN: Final = "누적수익률_시뮬(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_ABS: Final = "누적배수_로그차이_abs(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED: Final = "누적배수_로그차이_signed(%)"

# --- Rate Spread Lab 내부 컬럼 (영문 토큰) ---
COL_MONTH: Final = "month"  # 월별 집계용 Period 컬럼
COL_RATE_PCT: Final = "rate_pct"  # 금리 수준 (%)
COL_DR_M: Final = "dr_m"  # 금리 변화 (%p)
COL_E_M: Final = "e_m"  # 월말 누적 오차 (%)
COL_DE_M: Final = "de_m"  # 월간 오차 변화 (%)
COL_SUM_DAILY_M: Final = "sum_daily_m"  # 일일 오차 월합 (%)

# ============================================================
# 딕셔너리 키 (KEY_)
# ============================================================

# --- 겹치는 기간 정보 ---
KEY_OVERLAP_START: Final = "overlap_start"
KEY_OVERLAP_END: Final = "overlap_end"
KEY_OVERLAP_DAYS: Final = "overlap_days"

# --- 누적수익률 ---
KEY_CUMULATIVE_RETURN_ACTUAL: Final = "cumulative_return_actual"
KEY_CUMULATIVE_RETURN_SIMULATED: Final = "cumulative_return_simulated"

# --- 검증 지표 ---
KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN: Final = "cumul_multiple_log_diff_mean_pct"
KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE: Final = "cumul_multiple_log_diff_rmse_pct"
KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX: Final = "cumul_multiple_log_diff_max_pct"
