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

# 거래 비용 상수
# COMMISSION_RATE: 매수 가능 수량 계산 시에만 사용 (실제 거래 비용에서는 차감하지 않음)
COMMISSION_RATE = 0.0005  # 0.05% / 체결당
SLIPPAGE_RATE_PER_SIDE = 0.003  # 0.3% / 매수 or 매도 한 번 (실제 가격에 적용)

# 손절 관련 상수
MIN_LOOKBACK_FOR_LOW = 20  # 최근 저점 탐색 최소 기간

# 초기 자본금
DEFAULT_INITIAL_CAPITAL = 10_000_000.0  # 1천만원

# 그리드 서치 기본 파라미터
DEFAULT_SHORT_WINDOW_LIST = [5, 10, 20]
DEFAULT_LONG_WINDOW_LIST = [60, 100, 120, 200, 250]
DEFAULT_STOP_LOSS_PCT_LIST = [0.05, 0.1, 0.15]
DEFAULT_LOOKBACK_FOR_LOW_LIST = [20, 30, 40, 50, 60]

# 워킹 포워드 기본 설정
DEFAULT_TRAIN_YEARS = 5
DEFAULT_TEST_YEARS = 1
