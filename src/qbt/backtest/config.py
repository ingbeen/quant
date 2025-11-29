"""
백테스트 공용 상수 및 설정

여러 모듈에서 공통으로 사용하는 상수를 정의한다.
"""

from pathlib import Path

# 데이터 경로
DATA_DIR = Path("data/raw")
RESULTS_DIR = Path("results")

# 기본 데이터 파일
DEFAULT_DATA_FILE = DATA_DIR / "QQQ_max.csv"

# 필수 컬럼 목록
REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]

# 가격 컬럼 목록 (유효성 검사 대상)
PRICE_COLUMNS = ["Open", "High", "Low", "Close"]

# 급등락 임계값 (절대값 기준, 20%)
PRICE_CHANGE_THRESHOLD = 0.20

# 거래 비용 상수 (슬리피지에 수수료 포함)
SLIPPAGE_RATE = 0.003  # 0.3% / 매수 or 매도 1회

# 손절 관련 상수
MIN_LOOKBACK_FOR_LOW = 20  # 최근 저점 탐색 최소 기간

# 초기 자본금
DEFAULT_INITIAL_CAPITAL = 10_000_000.0  # 1천만원

# 그리드 서치 기본 파라미터 (교차 전략용 - 미사용)
DEFAULT_SHORT_WINDOW_LIST = [5, 10, 20]
DEFAULT_LONG_WINDOW_LIST = [60, 100, 120, 200, 250]
DEFAULT_STOP_LOSS_PCT_LIST = [0.05, 0.1, 0.15]
DEFAULT_LOOKBACK_FOR_LOW_LIST = [20, 30, 40, 50, 60]

# 그리드 서치 기본 파라미터 (버퍼존 전략용)
DEFAULT_MA_WINDOW_LIST = [100, 150, 200, 250]
DEFAULT_BUFFER_ZONE_PCT_LIST = [0.01, 0.02, 0.03, 0.05]
DEFAULT_HOLD_DAYS_LIST = [0, 1, 2, 3, 5]
DEFAULT_RECENT_MONTHS_LIST = [4, 6, 12]

# 워킹 포워드 기본 설정
DEFAULT_TRAIN_YEARS = 5
DEFAULT_TEST_YEARS = 1

# 버퍼존 전략 기본값
DEFAULT_MA_WINDOW = 200  # 이동평균 기간
DEFAULT_BUFFER_ZONE_PCT = 0.01  # 초기 버퍼존 (1%)
DEFAULT_HOLD_DAYS = 1  # 초기 유지조건 (1일)
DEFAULT_RECENT_MONTHS = 6  # 최근 매수 기간 (6개월)
MIN_BUFFER_ZONE_PCT = 0.01  # 최소 버퍼존 (1%)
MIN_HOLD_DAYS = 0  # 최소 유지조건 (0=버퍼존만 모드)
MIN_VALID_ROWS = 2  # 백테스트 최소 유효 데이터 행 수
