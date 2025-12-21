"""
QBT 프로젝트 공통 상수

모든 도메인에서 공통으로 사용하는 상수를 정의한다.
- 데이터 관련 상수 (컬럼명, 연간 영업일 등)
- 경로 상수 (디렉토리, 데이터 파일, 결과 파일)
"""

from pathlib import Path

# ============================================================
# 경로 상수
# ============================================================

# 디렉토리 경로
STORAGE_DIR = Path("storage")
STOCK_DIR = STORAGE_DIR / "stock"
ETC_DIR = STORAGE_DIR / "etc"
RESULTS_DIR = STORAGE_DIR / "results"

# 주식 데이터 파일 경로
QQQ_DATA_PATH = STOCK_DIR / "QQQ_max.csv"
TQQQ_DATA_PATH = STOCK_DIR / "TQQQ_max.csv"
TQQQ_SYNTHETIC_PATH = STOCK_DIR / "TQQQ_synthetic_max.csv"

# 기타 데이터 파일 경로
FFR_DATA_PATH = ETC_DIR / "federal_funds_rate_monthly.csv"

# 결과 파일 경로
GRID_RESULTS_PATH = RESULTS_DIR / "grid_results.csv"
TQQQ_VALIDATION_PATH = RESULTS_DIR / "tqqq_validation.csv"
TQQQ_DAILY_COMPARISON_PATH = RESULTS_DIR / "tqqq_daily_comparison.csv"

# ============================================================
# 데이터 관련 상수
# ============================================================

# CSV 파일 컬럼명
COL_DATE = "Date"
COL_OPEN = "Open"
COL_HIGH = "High"
COL_LOW = "Low"
COL_CLOSE = "Close"
COL_VOLUME = "Volume"

# FFR (Federal Funds Rate) 데이터 컬럼명
COL_FFR_DATE = "DATE"  # FFR CSV의 날짜 컬럼 (대문자)
COL_FFR_VALUE_RAW = "VALUE"  # FFR CSV의 원본 금리 값 컬럼
COL_FFR = "FFR"  # 변환 후 금리 컬럼명

# 컬럼 그룹
REQUIRED_COLUMNS = [COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME]
PRICE_COLUMNS = [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]

# 연간 영업일 상수
ANNUAL_DAYS = 365.25  # CAGR 계산용 (윤년 포함)
TRADING_DAYS_PER_YEAR = 252  # 일일 비용 환산용 (연간 거래일 수)

# 수치 안정성 상수
EPSILON = 1e-12  # 분모 0 방지 및 로그 계산 안정성 확보

# 일별 비교 컬럼명 (한글)
COL_DATE_KR = "날짜"
COL_ACTUAL_CLOSE = "종가_실제"
COL_SIMUL_CLOSE = "종가_시뮬"

# 일일수익률
COL_ACTUAL_DAILY_RETURN = "일일수익률_실제"
COL_SIMUL_DAILY_RETURN = "일일수익률_시뮬"
COL_DAILY_RETURN_ABS_DIFF = "일일수익률_절대차이"

# 누적수익률
COL_ACTUAL_CUMUL_RETURN = "누적수익률_실제(%)"
COL_SIMUL_CUMUL_RETURN = "누적수익률_시뮬레이션(%)"
COL_CUMUL_MULTIPLE_LOG_DIFF = "누적배수_로그차이(%)"

# 일별 비교 필수 컬럼 그룹
COMPARISON_COLUMNS = [
    COL_DATE_KR,
    COL_ACTUAL_CLOSE,
    COL_SIMUL_CLOSE,
    COL_ACTUAL_DAILY_RETURN,
    COL_SIMUL_DAILY_RETURN,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_ACTUAL_CUMUL_RETURN,
    COL_SIMUL_CUMUL_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF,
]
