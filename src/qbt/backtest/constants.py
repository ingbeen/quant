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
# 매수 또는 매도 1회당 0.3%. 왕복(매수 + 매도) 비용은 2 * SLIPPAGE_RATE 이며,
# 매수와 매도가 각각 별도의 비용 이벤트로 누적되는 것이 의도된 설계이다.
SLIPPAGE_RATE: Final = 0.003  # 0.3% / 매수 or 매도 1회 (왕복 0.6%)

# 초기 자본금
DEFAULT_INITIAL_CAPITAL: Final = 10_000_000.0  # 1천만원

# ============================================================
# 전략 파라미터
# ============================================================

# --- 4P 확정 파라미터 (근거: docs/research/전략_검증_보고서.md §2.1) ---
FIXED_4P_MA_WINDOW: Final = 200  # 확정 이동평균 기간
FIXED_4P_BUY_BUFFER_ZONE_PCT: Final = 0.03  # 확정 매수 버퍼존 비율 (0.03 = 3%)
FIXED_4P_SELL_BUFFER_ZONE_PCT: Final = 0.05  # 확정 매도 버퍼존 비율 (0.05 = 5%)
FIXED_4P_HOLD_DAYS: Final = 3  # 확정 유지일수

MIN_VALID_ROWS: Final = 2  # 백테스트 최소 유효 데이터 행 수

# --- WFO 파라미터 리스트 (그리드 서치 + 워크포워드 공용) ---
DEFAULT_WFO_MA_WINDOW_LIST: Final = [100, 150, 200]
DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST: Final = [0.01, 0.03, 0.05]
DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST: Final = [0.01, 0.03, 0.05]
DEFAULT_WFO_HOLD_DAYS_LIST: Final = [0, 2, 3, 5]

# --- WFO 최소 거래수 ---
DEFAULT_WFO_MIN_TRADES: Final = 3  # IS 최적 파라미터 선택 시 최소 거래수 제약

# --- WFO 윈도우 설정 ---
DEFAULT_WFO_INITIAL_IS_MONTHS: Final = 72  # 초기 IS 기간 (6년)
DEFAULT_WFO_OOS_MONTHS: Final = 24  # OOS 기간 (2년)

# --- WFO 모드 (walkforward_summary.json 의 키) ---
KEY_WFO_DYNAMIC: Final = "dynamic"  # 윈도우마다 IS 그리드에서 다시 고른다
KEY_WFO_FULLY_FIXED: Final = "fully_fixed"  # 4P 를 모든 윈도우에 고정한다

# --- 결과 파일명 (러너가 쓰고 대시보드가 읽는다) ---
SIGNAL_FILENAME: Final = "signal.csv"
EQUITY_FILENAME: Final = "equity.csv"
TRADES_FILENAME: Final = "trades.csv"
SUMMARY_FILENAME: Final = "summary.json"

# --- WFO 결과 파일명 ---
WALKFORWARD_DYNAMIC_FILENAME: Final = "walkforward_dynamic.csv"
WALKFORWARD_FULLY_FIXED_FILENAME: Final = "walkforward_fully_fixed.csv"
WALKFORWARD_EQUITY_DYNAMIC_FILENAME: Final = "walkforward_equity_dynamic.csv"
WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME: Final = "walkforward_equity_fully_fixed.csv"
WALKFORWARD_SUMMARY_FILENAME: Final = "walkforward_summary.json"

# --- WFO 윈도우별 상세 CSV 디렉토리명 ---
WFO_WINDOWS_DYNAMIC_DIR: Final = "wfo_windows_dynamic"
WFO_WINDOWS_FULLY_FIXED_DIR: Final = "wfo_windows_fully_fixed"

# ============================================================
# 결과 데이터 컬럼 및 표시
# ============================================================

# --- 핵심 컬럼명 상수 (도메인 내 2개 이상 파일에서 사용) ---
COL_EQUITY: Final = "equity"
COL_PNL: Final = "pnl"
COL_ENTRY_DATE: Final = "entry_date"
COL_EXIT_DATE: Final = "exit_date"
COL_UPPER_BAND: Final = "upper_band"
COL_LOWER_BAND: Final = "lower_band"
COL_ENTRY_PRICE: Final = "entry_price"
COL_EXIT_PRICE: Final = "exit_price"
COL_SHARES: Final = "shares"
COL_PNL_PCT: Final = "pnl_pct"
COL_BUY_BUFFER_PCT: Final = "buy_buffer_pct"
COL_SELL_BUFFER_PCT: Final = "sell_buffer_pct"
COL_HOLD_DAYS_USED: Final = "hold_days_used"
COL_ORDER_AMOUNT: Final = "order_amount"
COL_HOLDING_DAYS: Final = "holding_days"
COL_DRAWDOWN_PCT: Final = "drawdown_pct"

# --- 포트폴리오 거래 기록의 trade_type 값 ---
TRADE_TYPE_SIGNAL: Final = "signal"  # 신호 · 배분 변화에 따른 청산
TRADE_TYPE_REBALANCE: Final = "rebalance"  # 목표 비중으로 줄이는 부분 매도

# --- 포트폴리오 결과의 rebalance_reason 값 ---
# 리밸런싱했는데 사유가 빈 문자열이면 배분 규칙 매매법이 목표 비중 변화에 맞춰 조정한 것이다
REBALANCE_REASON_MONTHLY: Final = "monthly"  # 월말에 판단해 다음 거래일에 체결하는 정기 리밸런싱
REBALANCE_REASON_METHODS: Final = "methods"  # 매매법 사이 비중 되돌리기

# --- DataFrame 컬럼명 (내부용) ---
COL_MA_WINDOW: Final = "ma_window"
COL_BUY_BUFFER_ZONE_PCT: Final = "buy_buffer_zone_pct"
COL_SELL_BUFFER_ZONE_PCT: Final = "sell_buffer_zone_pct"
COL_HOLD_DAYS: Final = "hold_days"
COL_CAGR: Final = "cagr"
COL_MDD: Final = "mdd"
COL_CALMAR: Final = "calmar"
COL_TOTAL_TRADES: Final = "total_trades"
COL_WIN_RATE: Final = "win_rate"

# ============================================================
# 이름 생성 함수
# ============================================================


def ma_col_name(window: int) -> str:
    """MA 컬럼명을 생성한다.

    Args:
        window: 이동평균 기간

    Returns:
        MA 컬럼명 문자열. 예: ma_col_name(200) -> 'ma_200'
    """
    return f"ma_{window}"


def wfo_window_filename(window_idx: int, filename: str) -> str:
    """WFO 윈도우별 상세 파일명. 예: wfo_window_filename(3, SIGNAL_FILENAME) -> 'w03_signal.csv'"""
    return f"w{window_idx:02d}_{filename}"
