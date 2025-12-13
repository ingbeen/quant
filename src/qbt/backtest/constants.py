"""
백테스트 도메인 상수

백테스트 도메인에서만 사용하는 전략 파라미터와 상수를 정의한다.
"""

# 거래 비용 상수 (슬리피지에 수수료 포함)
SLIPPAGE_RATE = 0.003  # 0.3% / 매수 or 매도 1회

# 초기 자본금
DEFAULT_INITIAL_CAPITAL = 10_000_000.0  # 1천만원

# 그리드 서치 기본 파라미터 (버퍼존 전략용)
DEFAULT_MA_WINDOW_LIST = [100, 150, 200, 250]
DEFAULT_BUFFER_ZONE_PCT_LIST = [0.01, 0.02, 0.03, 0.05]
DEFAULT_HOLD_DAYS_LIST = [0, 1, 2, 3, 5]
DEFAULT_RECENT_MONTHS_LIST = [4, 6, 12]

# 버퍼존 전략 기본값
DEFAULT_MA_WINDOW = 200  # 이동평균 기간
DEFAULT_BUFFER_ZONE_PCT = 0.01  # 초기 버퍼존 (1%)
DEFAULT_HOLD_DAYS = 1  # 초기 유지조건 (1일)
DEFAULT_RECENT_MONTHS = 6  # 최근 매수 기간 (6개월)
MIN_BUFFER_ZONE_PCT = 0.01  # 최소 버퍼존 (1%)
MIN_HOLD_DAYS = 0  # 최소 유지조건 (0=버퍼존만 모드)
MIN_VALID_ROWS = 2  # 백테스트 최소 유효 데이터 행 수

# 동적 조정 관련 상수
BUFFER_INCREMENT_PER_BUY = 0.01  # 최근 매수 1회당 버퍼존 증가량 (1%)
HOLD_DAYS_INCREMENT_PER_BUY = 1  # 최근 매수 1회당 유지조건 증가량 (1일)
DAYS_PER_MONTH = 30  # 최근 기간 계산용 월당 일수 (근사값)
