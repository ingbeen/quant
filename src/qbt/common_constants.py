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
