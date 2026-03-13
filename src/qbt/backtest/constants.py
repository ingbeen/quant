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

# --- 버퍼존 전략 기본값 ---
DEFAULT_MA_WINDOW: Final = 200  # 이동평균 기간
DEFAULT_BUY_BUFFER_ZONE_PCT: Final = 0.03  # 매수 버퍼존 비율 (0.03 = 3%)
DEFAULT_SELL_BUFFER_ZONE_PCT: Final = 0.03  # 매도 버퍼존 비율 (0.03 = 3%)
DEFAULT_HOLD_DAYS: Final = 0  # 유지조건 기본값 (0일 = 버퍼존만 모드)
DEFAULT_RECENT_MONTHS: Final = 0  # 최근 청산 기간 기본값 (개월)

# --- 4P 확정 파라미터 (overfitting_analysis_report.md §2.1 기반) ---
FIXED_4P_MA_WINDOW: Final = 200  # 확정 이동평균 기간
FIXED_4P_BUY_BUFFER_ZONE_PCT: Final = 0.03  # 확정 매수 버퍼존 비율 (0.03 = 3%)
FIXED_4P_SELL_BUFFER_ZONE_PCT: Final = 0.05  # 확정 매도 버퍼존 비율 (0.05 = 5%)
FIXED_4P_HOLD_DAYS: Final = 3  # 확정 유지일수
FIXED_4P_RECENT_MONTHS: Final = 0  # 확정 조정기간 (0 = 비활성화)

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
DEFAULT_WFO_RECENT_MONTHS_LIST: Final = [0, 4, 8, 12]

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
COL_RECENT_MONTHS: Final = "recent_months"
COL_TOTAL_RETURN_PCT: Final = "total_return_pct"
COL_CAGR: Final = "cagr"
COL_MDD: Final = "mdd"
COL_CALMAR: Final = "calmar"
COL_TOTAL_TRADES: Final = "total_trades"
COL_WIN_RATE: Final = "win_rate"
COL_FINAL_CAPITAL: Final = "final_capital"

# --- 그리드 서치 결과 CSV 출력용 레이블 (한글) ---
DISPLAY_MA_WINDOW: Final = "이평기간"
DISPLAY_BUY_BUFFER_ZONE: Final = "매수버퍼존"
DISPLAY_SELL_BUFFER_ZONE: Final = "매도버퍼존"
DISPLAY_HOLD_DAYS: Final = "유지일"
DISPLAY_RECENT_MONTHS: Final = "조정기간(월)"
DISPLAY_TOTAL_RETURN: Final = "수익률"
DISPLAY_CAGR: Final = "CAGR"
DISPLAY_MDD: Final = "MDD"
DISPLAY_CALMAR: Final = "Calmar"
DISPLAY_TOTAL_TRADES: Final = "거래수"
DISPLAY_WIN_RATE: Final = "승률"
DISPLAY_FINAL_CAPITAL: Final = "최종자본"
