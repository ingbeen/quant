"""
백테스트 도메인 상수

백테스트 도메인에서만 사용하는 전략 파라미터와 상수를 정의한다.
- 백테스트 기본 설정 (거래 비용, 초기 자본)
- 전략 파라미터 (버퍼존 기본값, 제약 조건, 그리드 서치)
- 결과 데이터 컬럼 및 표시
"""

from typing import Final

# ============================================================
# 백테스트 기본 설정
# ============================================================

# 거래 비용 상수 (슬리피지에 수수료 포함)
SLIPPAGE_RATE: Final = 0.003  # 0.3% / 매수 or 매도 1회

# 초기 자본금
DEFAULT_INITIAL_CAPITAL: Final = 10_000_000.0  # 1천만원

# ============================================================
# 전략 파라미터
# ============================================================

# --- 버퍼존 전략 기본값 ---
DEFAULT_MA_WINDOW: Final = 200  # 이동평균 기간
DEFAULT_BUFFER_ZONE_PCT: Final = 0.03  # 버퍼존 비율 (0.03 = 3%)
DEFAULT_HOLD_DAYS: Final = 0  # 유지조건 기본값 (0일 = 버퍼존만 모드)
DEFAULT_RECENT_MONTHS: Final = 0  # 최근 매수 기간 기본값 (개월)

# --- 버퍼존 전략 제약 조건 ---
MIN_BUFFER_ZONE_PCT: Final = 0.01  # 최소 버퍼존 비율 (0.01 = 1%)
MIN_HOLD_DAYS: Final = 0  # 최소 유지조건 (0일 = 버퍼존만 모드)
MIN_VALID_ROWS: Final = 2  # 백테스트 최소 유효 데이터 행 수

# --- 그리드 서치 파라미터 ---
DEFAULT_MA_WINDOW_LIST: Final = [100, 150, 200, 250]
DEFAULT_BUFFER_ZONE_PCT_LIST: Final = [0.01, 0.02, 0.03, 0.04, 0.05]
DEFAULT_HOLD_DAYS_LIST: Final = [0, 1, 2, 3, 4, 5]
DEFAULT_RECENT_MONTHS_LIST: Final = [0, 2, 4, 6, 8, 10, 12]

# ============================================================
# 결과 데이터 컬럼 및 표시
# ============================================================

# --- DataFrame 컬럼명 (내부용) ---
COL_MA_WINDOW: Final = "ma_window"
COL_BUFFER_ZONE_PCT: Final = "buffer_zone_pct"
COL_HOLD_DAYS: Final = "hold_days"
COL_RECENT_MONTHS: Final = "recent_months"
COL_TOTAL_RETURN_PCT: Final = "total_return_pct"
COL_CAGR: Final = "cagr"
COL_MDD: Final = "mdd"
COL_TOTAL_TRADES: Final = "total_trades"
COL_WIN_RATE: Final = "win_rate"
COL_FINAL_CAPITAL: Final = "final_capital"
