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

# DataFrame 내부 컬럼명 (영문)
COL_GRID_MA_WINDOW = "ma_window"
COL_GRID_BUFFER_ZONE_PCT = "buffer_zone_pct"
COL_GRID_HOLD_DAYS = "hold_days"
COL_GRID_RECENT_MONTHS = "recent_months"
COL_GRID_TOTAL_RETURN_PCT = "total_return_pct"
COL_GRID_CAGR = "cagr"
COL_GRID_MDD = "mdd"
COL_GRID_TOTAL_TRADES = "total_trades"
COL_GRID_WIN_RATE = "win_rate"
COL_GRID_FINAL_CAPITAL = "final_capital"

# 출력용 컬럼명 (한글)
COL_GRID_DISPLAY_MA_WINDOW = "이평기간"
COL_GRID_DISPLAY_BUFFER_ZONE = "버퍼존"
COL_GRID_DISPLAY_HOLD_DAYS = "유지일"
COL_GRID_DISPLAY_RECENT_MONTHS = "조정기간"
COL_GRID_DISPLAY_TOTAL_RETURN = "수익률"
COL_GRID_DISPLAY_CAGR = "CAGR"
COL_GRID_DISPLAY_MDD = "MDD"
COL_GRID_DISPLAY_TOTAL_TRADES = "거래수"
COL_GRID_DISPLAY_WIN_RATE = "승률"
COL_GRID_DISPLAY_FINAL_CAPITAL = "최종자본"

# 컬럼 매핑 딕셔너리 (CSV 저장용)
GRID_COLUMN_MAPPING = {
    COL_GRID_MA_WINDOW: COL_GRID_DISPLAY_MA_WINDOW,
    COL_GRID_BUFFER_ZONE_PCT: COL_GRID_DISPLAY_BUFFER_ZONE,
    COL_GRID_HOLD_DAYS: COL_GRID_DISPLAY_HOLD_DAYS,
    COL_GRID_RECENT_MONTHS: COL_GRID_DISPLAY_RECENT_MONTHS,
    COL_GRID_TOTAL_RETURN_PCT: COL_GRID_DISPLAY_TOTAL_RETURN,
    COL_GRID_CAGR: COL_GRID_DISPLAY_CAGR,
    COL_GRID_MDD: COL_GRID_DISPLAY_MDD,
    COL_GRID_TOTAL_TRADES: COL_GRID_DISPLAY_TOTAL_TRADES,
    COL_GRID_WIN_RATE: COL_GRID_DISPLAY_WIN_RATE,
    COL_GRID_FINAL_CAPITAL: COL_GRID_DISPLAY_FINAL_CAPITAL,
}
