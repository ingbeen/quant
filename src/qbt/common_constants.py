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

# 결과 파일 경로
GRID_RESULTS_PATH = RESULTS_DIR / "grid_results.csv"
META_JSON_PATH = RESULTS_DIR / "meta.json"

# ============================================================
# 데이터 관련 상수
# ============================================================

# CSV 파일 컬럼명
COL_DATE = "Date"  # 주식 데이터 CSV 날짜 컬럼 (영문)
DISPLAY_DATE = "날짜"  # 출력/비교 데이터 날짜 컬럼 (한글)
COL_OPEN = "Open"
COL_HIGH = "High"
COL_LOW = "Low"
COL_CLOSE = "Close"
COL_VOLUME = "Volume"

# 컬럼 그룹
REQUIRED_COLUMNS = [COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME]
PRICE_COLUMNS = [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]

# 연간 영업일 상수
ANNUAL_DAYS = 365.25  # CAGR 계산용 (윤년 포함)
TRADING_DAYS_PER_YEAR = 252  # 일일 비용 환산용 (연간 거래일 수)

# 수치 안정성 상수
EPSILON = 1e-12  # 분모 0 방지 및 로그 계산 안정성 확보

# 메타데이터 관리 상수
MAX_HISTORY_COUNT = 5  # meta.json에 유지할 최대 이력 개수
