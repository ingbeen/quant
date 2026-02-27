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
DEFAULT_BUY_BUFFER_ZONE_PCT: Final = 0.03  # 매수 버퍼존 비율 (0.03 = 3%)
DEFAULT_SELL_BUFFER_ZONE_PCT: Final = 0.03  # 매도 버퍼존 비율 (0.03 = 3%)
DEFAULT_HOLD_DAYS: Final = 0  # 유지조건 기본값 (0일 = 버퍼존만 모드)
DEFAULT_RECENT_MONTHS: Final = 0  # 최근 청산 기간 기본값 (개월)

# --- 버퍼존 전략 제약 조건 ---
MIN_BUY_BUFFER_ZONE_PCT: Final = 0.01  # 최소 매수 버퍼존 비율 (0.01 = 1%)
MIN_SELL_BUFFER_ZONE_PCT: Final = 0.01  # 최소 매도 버퍼존 비율 (0.01 = 1%)
MIN_HOLD_DAYS: Final = 0  # 최소 유지조건 (0일 = 버퍼존만 모드)
MIN_VALID_ROWS: Final = 2  # 백테스트 최소 유효 데이터 행 수

# --- WFO 파라미터 리스트 (그리드 서치 + 워크포워드 공용) ---
DEFAULT_WFO_MA_WINDOW_LIST: Final = [100, 150, 200]  # 3개
DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST: Final = [0.01, 0.03, 0.05]  # 3개
DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST: Final = [0.01, 0.03, 0.05]  # 3개
DEFAULT_WFO_HOLD_DAYS_LIST: Final = [0, 2, 3, 5]  # 4개
DEFAULT_WFO_RECENT_MONTHS_LIST: Final = [0, 4, 8, 12]  # 4개
# 3 × 3 × 3 × 4 × 4 = 432개

# --- ATR 트레일링 스탑 기본값 ---
DEFAULT_ATR_PERIOD: Final = 22  # Chandelier Exit 표준
DEFAULT_ATR_MULTIPLIER: Final = 3.0  # Chandelier Exit 표준

# --- WFO ATR 파라미터 리스트 ---
DEFAULT_WFO_ATR_PERIOD_LIST: Final = [14, 22]  # Wilder 표준(14) + Chandelier Exit 표준(22)
DEFAULT_WFO_ATR_MULTIPLIER_LIST: Final = [2.5, 3.0]  # 약간 공격적(2.5) + Chandelier Exit 기본(3.0)

# --- WFO 최소 거래수 ---
DEFAULT_WFO_MIN_TRADES: Final = 3  # IS 최적 파라미터 선택 시 최소 거래수 제약

# --- WFO 윈도우 설정 ---
DEFAULT_WFO_INITIAL_IS_MONTHS: Final = 72  # 초기 IS 기간 (6년)
DEFAULT_WFO_OOS_MONTHS: Final = 24  # OOS 기간 (2년)

# --- WFO 고정값 ---
DEFAULT_WFO_FIXED_SELL_BUFFER_PCT: Final = 0.05  # sell_fixed 모드에서 고정할 매도 버퍼 비율

# --- WFO 결과 파일명 ---
WALKFORWARD_DYNAMIC_FILENAME: Final = "walkforward_dynamic.csv"
WALKFORWARD_SELL_FIXED_FILENAME: Final = "walkforward_sell_fixed.csv"
WALKFORWARD_FULLY_FIXED_FILENAME: Final = "walkforward_fully_fixed.csv"
WALKFORWARD_EQUITY_DYNAMIC_FILENAME: Final = "walkforward_equity_dynamic.csv"
WALKFORWARD_EQUITY_SELL_FIXED_FILENAME: Final = "walkforward_equity_sell_fixed.csv"
WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME: Final = "walkforward_equity_fully_fixed.csv"
WALKFORWARD_SUMMARY_FILENAME: Final = "walkforward_summary.json"

# ============================================================
# CSCV 과최적화 검증 상수
# ============================================================

# --- CSCV 블록 설정 ---
DEFAULT_CSCV_N_BLOCKS: Final = 6  # 시계열 블록 수 (짝수). C(6,3)=20 조합
DEFAULT_CSCV_METRIC: Final = "sharpe"  # 기본 성과 지표 ("sharpe" 또는 "calmar")

# --- CSCV 결과 파일명 ---
CSCV_ANALYSIS_FILENAME: Final = "cscv_analysis.json"
CSCV_LOGIT_LAMBDAS_FILENAME: Final = "cscv_logit_lambdas.csv"

# ============================================================
# 결과 데이터 컬럼 및 표시
# ============================================================

# --- DataFrame 컬럼명 (내부용) ---
COL_MA_WINDOW: Final = "ma_window"
COL_BUY_BUFFER_ZONE_PCT: Final = "buy_buffer_zone_pct"
COL_SELL_BUFFER_ZONE_PCT: Final = "sell_buffer_zone_pct"
COL_HOLD_DAYS: Final = "hold_days"
COL_RECENT_MONTHS: Final = "recent_months"
COL_TOTAL_RETURN_PCT: Final = "total_return_pct"
COL_CAGR: Final = "cagr"
COL_MDD: Final = "mdd"
COL_TOTAL_TRADES: Final = "total_trades"
COL_WIN_RATE: Final = "win_rate"
COL_FINAL_CAPITAL: Final = "final_capital"
COL_ATR_PERIOD: Final = "atr_period"
COL_ATR_MULTIPLIER: Final = "atr_multiplier"

# --- 그리드 서치 결과 CSV 출력용 레이블 (한글) ---
DISPLAY_MA_WINDOW: Final = "이평기간"
DISPLAY_BUY_BUFFER_ZONE: Final = "매수버퍼존"
DISPLAY_SELL_BUFFER_ZONE: Final = "매도버퍼존"
DISPLAY_HOLD_DAYS: Final = "유지일"
DISPLAY_RECENT_MONTHS: Final = "조정기간(월)"
DISPLAY_TOTAL_RETURN: Final = "수익률"
DISPLAY_CAGR: Final = "CAGR"
DISPLAY_MDD: Final = "MDD"
DISPLAY_TOTAL_TRADES: Final = "거래수"
DISPLAY_WIN_RATE: Final = "승률"
DISPLAY_FINAL_CAPITAL: Final = "최종자본"
