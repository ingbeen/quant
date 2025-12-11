"""
QBT 프로젝트 공통 상수

모든 도메인에서 공통으로 사용하는 데이터 관련 상수를 정의한다.
"""

# CSV 파일 컬럼명
COL_DATE = "Date"
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

# 일별 비교 컬럼명 (한글)
COL_DATE_KR = "날짜"
COL_ACTUAL_CLOSE = "실제_종가"
COL_SIMUL_CLOSE = "시뮬_종가"
COL_DAILY_RETURN_DIFF = "일일수익률_차이"
COL_CUMUL_RETURN_DIFF = "누적수익률_차이"

# 일별 비교 필수 컬럼 그룹
COMPARISON_COLUMNS = [
    COL_DATE_KR,
    COL_ACTUAL_CLOSE,
    COL_SIMUL_CLOSE,
    COL_DAILY_RETURN_DIFF,
    COL_CUMUL_RETURN_DIFF,
]
