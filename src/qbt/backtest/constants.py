"""
백테스트 도메인 상수

백테스트 도메인에서만 사용하는 전략 파라미터와 상수를 정의한다.
- 백테스트 기본 설정 (거래 비용, 초기 자본)
- 전략 파라미터 (버퍼존 기본값, 제약 조건, 그리드 서치)
- 결과 데이터 컬럼 및 표시
- 시장 구간 정의 (QQQ 기준)
"""

from typing import Final

from qbt.backtest.types import MarketRegimeDict

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

# --- Calmar MDD=0 처리 대용값 (MDD=0인 구간에서 Calmar 정렬 유지) ---
CALMAR_MDD_ZERO_SUBSTITUTE: Final = 1e10

# --- 버퍼존/그리드서치 기본 이동평균 유형 ---
DEFAULT_BUFFER_MA_TYPE: Final = "ema"

# --- 4P 확정 파라미터 (overfitting_analysis_report.md §2.1 기반) ---
FIXED_4P_MA_WINDOW: Final = 200  # 확정 이동평균 기간
FIXED_4P_BUY_BUFFER_ZONE_PCT: Final = 0.03  # 확정 매수 버퍼존 비율 (0.03 = 3%)
FIXED_4P_SELL_BUFFER_ZONE_PCT: Final = 0.05  # 확정 매도 버퍼존 비율 (0.05 = 5%)
FIXED_4P_HOLD_DAYS: Final = 3  # 확정 유지일수

# --- 버퍼존 전략 제약 조건 ---
MIN_BUY_BUFFER_ZONE_PCT: Final = 0.01  # 최소 매수 버퍼존 비율 (0.01 = 1%)
MIN_SELL_BUFFER_ZONE_PCT: Final = 0.01  # 최소 매도 버퍼존 비율 (0.01 = 1%)
MIN_HOLD_DAYS: Final = 0  # 최소 유지조건 (0일 = 버퍼존만 모드)
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

# --- WFO 결과 파일명 ---
WALKFORWARD_DYNAMIC_FILENAME: Final = "walkforward_dynamic.csv"
WALKFORWARD_FULLY_FIXED_FILENAME: Final = "walkforward_fully_fixed.csv"
WALKFORWARD_EQUITY_DYNAMIC_FILENAME: Final = "walkforward_equity_dynamic.csv"
WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME: Final = "walkforward_equity_fully_fixed.csv"
WALKFORWARD_SUMMARY_FILENAME: Final = "walkforward_summary.json"

# ============================================================
# 시장 구간 정의 (QQQ 기준, 수동 분류)
# ============================================================

# QQQ 기준 수동 분류 (상승/횡보/하락)
MARKET_REGIMES: Final[list[MarketRegimeDict]] = [
    {"start": "1999-03-10", "end": "2000-03-27", "regime_type": "bull", "name": "닷컴 버블 상승기"},
    {"start": "2000-03-28", "end": "2002-10-09", "regime_type": "bear", "name": "닷컴 붕괴"},
    {"start": "2002-10-10", "end": "2004-01-26", "regime_type": "bull", "name": "닷컴 후 초기 회복"},
    {"start": "2004-01-27", "end": "2006-07-21", "regime_type": "sideways", "name": "금리인상기 박스권"},
    {"start": "2006-07-24", "end": "2007-10-31", "regime_type": "bull", "name": "글로벌 성장기"},
    {"start": "2007-11-01", "end": "2009-03-09", "regime_type": "bear", "name": "글로벌 금융위기"},
    {"start": "2009-03-10", "end": "2011-07-25", "regime_type": "bull", "name": "QE1/QE2 상승기"},
    {"start": "2011-07-26", "end": "2012-09-18", "regime_type": "sideways", "name": "유럽 재정위기 횡보"},
    {"start": "2012-09-19", "end": "2015-07-20", "regime_type": "bull", "name": "QE3 상승기"},
    {"start": "2015-07-21", "end": "2016-06-30", "regime_type": "sideways", "name": "중국/유가 불안"},
    {"start": "2016-07-01", "end": "2018-09-28", "regime_type": "bull", "name": "트럼프 랠리"},
    {"start": "2018-10-01", "end": "2018-12-24", "regime_type": "bear", "name": "2018 Q4 조정"},
    {"start": "2018-12-26", "end": "2020-02-19", "regime_type": "bull", "name": "2019 회복 랠리"},
    {"start": "2020-02-20", "end": "2020-03-23", "regime_type": "bear", "name": "코로나 급락"},
    {"start": "2020-03-24", "end": "2021-11-19", "regime_type": "bull", "name": "포스트코로나 랠리"},
    {"start": "2021-11-22", "end": "2022-10-13", "regime_type": "bear", "name": "금리인상 약세장"},
    {"start": "2022-10-14", "end": "2025-02-18", "regime_type": "bull", "name": "AI 랠리"},
    {"start": "2025-02-19", "end": "2025-05-12", "regime_type": "bear", "name": "관세 충격"},
    {"start": "2025-05-13", "end": "2026-02-17", "regime_type": "bull", "name": "회복기"},
]

# ============================================================
# 결과 데이터 컬럼 및 표시
# ============================================================

# --- DataFrame 컬럼명 (내부용) ---
COL_MA_WINDOW: Final = "ma_window"
COL_BUY_BUFFER_ZONE_PCT: Final = "buy_buffer_zone_pct"
COL_SELL_BUFFER_ZONE_PCT: Final = "sell_buffer_zone_pct"
COL_HOLD_DAYS: Final = "hold_days"
COL_TOTAL_RETURN_PCT: Final = "total_return_pct"
COL_CAGR: Final = "cagr"
COL_MDD: Final = "mdd"
COL_CALMAR: Final = "calmar"
COL_TOTAL_TRADES: Final = "total_trades"
COL_WIN_RATE: Final = "win_rate"
COL_FINAL_CAPITAL: Final = "final_capital"

# ============================================================
# 단일 백테스트 활성 전략 필터
# ============================================================

# run_single_backtest.py / app_single_backtest.py에서 실행·표출할 전략 목록
DEFAULT_SINGLE_BACKTEST_STRATEGIES: Final[list[str]] = [
    "buffer_zone_tqqq",
    "buffer_zone_qqq",
    "buffer_zone_tlt",
    "buffer_zone_gld",
    "buy_and_hold_qqq",
    "buy_and_hold_tqqq",
    "buy_and_hold_tlt",
    "buy_and_hold_gld",
]
