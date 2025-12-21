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
DEFAULT_BUFFER_ZONE_PCT_LIST = [0.01, 0.02, 0.03, 0.04, 0.05]
DEFAULT_HOLD_DAYS_LIST = [0, 1, 2, 3, 4, 5]
DEFAULT_RECENT_MONTHS_LIST = [0, 2, 4, 6, 8, 10, 12]

# 버퍼존 전략 기본값
DEFAULT_MA_WINDOW = 200  # 이동평균 기간
DEFAULT_BUFFER_ZONE_PCT = 0.03  # 버퍼존 기본값 (%)
DEFAULT_HOLD_DAYS = 0  # 유지조건 기본값 (0일 = 버퍼존만 모드)
DEFAULT_RECENT_MONTHS = 0  # 최근 매수 기간 기본값 (개월)
MIN_BUFFER_ZONE_PCT = 0.01  # 최소 버퍼존 (%)
MIN_HOLD_DAYS = 0  # 최소 유지조건 (0일 = 버퍼존만 모드)
MIN_VALID_ROWS = 2  # 백테스트 최소 유효 데이터 행 수
BUFFER_INCREMENT_PER_BUY = 0.01  # 최근 매수 1회당 버퍼존 증가량 (%)
HOLD_DAYS_INCREMENT_PER_BUY = 1  # 최근 매수 1회당 유지조건 증가량 (일)
DAYS_PER_MONTH = 30  # 최근 기간 계산용 월당 일수 (근사값)

# ============================================================
# 그리드 서치 결과 컬럼명
# ============================================================

# DataFrame 내부 컬럼명
COL_MA_WINDOW = "ma_window"
COL_BUFFER_ZONE_PCT = "buffer_zone_pct"
COL_HOLD_DAYS = "hold_days"
COL_RECENT_MONTHS = "recent_months"
COL_TOTAL_RETURN_PCT = "total_return_pct"
COL_CAGR = "cagr"
COL_MDD = "mdd"
COL_TOTAL_TRADES = "total_trades"
COL_WIN_RATE = "win_rate"
COL_FINAL_CAPITAL = "final_capital"

# 출력용 레이블 (로그/CSV 출력용)
DISPLAY_MA_WINDOW = "이평기간"
DISPLAY_BUFFER_ZONE = "버퍼존"
DISPLAY_HOLD_DAYS = "유지일"
DISPLAY_RECENT_MONTHS = "조정기간"
DISPLAY_TOTAL_RETURN = "수익률"
DISPLAY_CAGR = "CAGR"
DISPLAY_MDD = "MDD"
DISPLAY_TOTAL_TRADES = "거래수"
DISPLAY_WIN_RATE = "승률"
DISPLAY_FINAL_CAPITAL = "최종자본"
