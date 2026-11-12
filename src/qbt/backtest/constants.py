"""
백테스트 도메인 상수

백테스트 도메인에서만 사용하는 전략 파라미터와 상수를 정의한다.
- 백테스트 기본 설정 (거래 비용, 초기 자본, 연율화 일수, 수치 안정성)
- 전략 파라미터 (버퍼존 기본값, 제약 조건, 그리드 서치)
- 결과 데이터 컬럼 및 표시
"""

from typing import Any, Final

# ============================================================
# 백테스트 기본 설정
# ============================================================

# 거래 비용 상수 (슬리피지에 수수료 포함)
# 매수 또는 매도 1회당 0.3%. 왕복(매수 + 매도) 비용은 2 * SLIPPAGE_RATE 이며,
# 매수와 매도가 각각 별도의 비용 이벤트로 누적되는 것이 의도된 설계이다.
SLIPPAGE_RATE: Final = 0.003  # 0.3% / 매수 or 매도 1회 (왕복 0.6%)

# 초기 자본금
DEFAULT_INITIAL_CAPITAL: Final = 10_000_000.0  # 1천만원

# 1년의 평균 달력 일수 (윤년 포함) — CAGR 의 연수 환산에 쓴다
ANNUAL_DAYS: Final = 365.25

# 연간 거래일 수(주말 · 공휴일 제외) — 일 단위와 연 단위를 서로 바꿀 때 씀
TRADING_DAYS_PER_YEAR: Final = 252

# 수치 안정성 상수 — 분모 0 방지 및 로그 계산 안정성 확보
EPSILON: Final = 1e-12

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

# --- WFO 선택 파라미터 (표시 라벨, 모드 요약의 키, 비율 여부 — 비율은 % 로 보인다) ---
# 판단 문구와 대시보드 파라미터 추이가 같은 목록 · 같은 라벨을 쓴다
WFO_PARAM_SPECS: Final[tuple[tuple[str, str, bool], ...]] = (
    ("MA Window", "param_ma_windows", False),
    ("Buy Buffer(%)", "param_buy_buffers", True),
    ("Sell Buffer(%)", "param_sell_buffers", True),
    ("Hold Days", "param_hold_days", False),
)

# --- WFO 판단 기준 — 판단 문구가 쓰고, 대시보드 「지표를 해석하는 방법」도 이 값으로 기준을 적는다 ---
PC_CONCENTRATION_THRESHOLD: Final = 0.5  # 한 윈도우의 수익 기여 비중이 이 이상이면 집중 경고 (0.5 = 전체 수익의 50%)
STITCHED_CALMAR_GOOD_THRESHOLD: Final = 1.0  # 이어 붙인 자본곡선의 Calmar 가 이 이상이면 위험 대비 수익이 양호하다

# --- 파라미터 고원: 최대값을 포함하면서 최대값 대비 이 비율 이상이 끊기지 않는 범위 (0.8 = 80%) ---
DEFAULT_PLATEAU_THRESHOLD_RATIO: Final = 0.8

# --- 결과 파일명 (러너가 쓰고 대시보드가 읽는다) ---
SIGNAL_FILENAME: Final = "signal.csv"
EQUITY_FILENAME: Final = "equity.csv"
TRADES_FILENAME: Final = "trades.csv"
SUMMARY_FILENAME: Final = "summary.json"
# 포트폴리오 실험 폴더에만 있는 파일 — 자산 키별 시그널은 portfolio_signal_filename
LEDGER_FILENAME: Final = "ledger.csv"
NETTING_FILENAME: Final = "netting.csv"
PORTFOLIO_SIGNAL_PREFIX: Final = "signal_"
# 포트폴리오 summary.json 의 기간 키 — 러너가 쓰고, 일부만 돌릴 때 다른 실험의 저장 기간 대조가 읽는다
KEY_PORTFOLIO_SUMMARY: Final = "portfolio_summary"
KEY_START_DATE: Final = "start_date"
KEY_END_DATE: Final = "end_date"
# summary.json 의 구간별 성과 키 — 러너 저장 · 대시보드 표시
KEY_PERIOD_PERFORMANCE: Final = "period_performance"
KEY_YEARLY_ASSET_CONTRIBUTIONS: Final = "yearly_asset_contributions"

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
# 대시보드 표시 (단일 · 포트폴리오 앱과 차트 모듈이 함께 쓴다)
# ============================================================

# Plotly 날짜 축의 눈금 · 정보창 형식 — `fig.update_xaxes(**KOREAN_DATE_AXIS)`.
# 먼저 맞는 항목을 쓰고 경계("M12" · "M1")는 양쪽에 걸림 → 긴 간격부터 둠
KOREAN_DATE_AXIS: Final[dict[str, Any]] = {
    "tickformatstops": [
        {"dtickrange": ["M12", None], "value": "%Y년"},
        {"dtickrange": ["M1", "M12"], "value": "%Y년 %-m월"},
        {"dtickrange": [None, "M1"], "value": "%Y-%m-%d"},
    ],
    "hoverformat": "%Y-%m-%d",
}

DISPLAY_NO_DATA: Final = "데이터 없음"
DISPLAY_PERIOD_CAPTION_SPLITS: Final = (
    "연 수익은 해마다 평균 몇 % 불었는지, 최악 낙폭은 고점에서 가장 많이 빠진 비율입니다(그 구간 첫날을 고점으로 다시 잽니다). " "구간 시작이 전략 시작보다 이르면 「데이터 없음」입니다."
)
DISPLAY_PERIOD_CAPTION_ROLLING: Final = "그달 첫 거래일에 넣고 범례의 햇수만큼 들고 있었다면 해마다 평균 몇 % 불었는지입니다. 선이 평평할수록 언제 시작해도 비슷했다는 뜻입니다."
DISPLAY_PERIOD_CAPTION_CONCENTRATION: Final = (
    "연간 수익률로 본 쏠림입니다. 몫은 가장 좋았던 세 해의 수익률 합 ÷ 모든 해의 수익률 합이고, "
    "「0% 로 바꾼 평균」은 그 해들에 수익이 없었다고 칠 때의 해마다 평균입니다. 첫 해 · 마지막 해는 일부 기간 그대로입니다."
)
DISPLAY_PERIOD_CAPTION_REGIMES: Final = (
    "날짜는 SPY 종가의 고점 → 바닥이고, 횡보장은 지수가 제자리였던 구간입니다. 전략 결과를 보고 고른 날짜가 아닙니다. " "QQQ 계열은 자기 고점 · 바닥과 며칠 ~ 몇 주 어긋납니다."
)

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

# --- 포트폴리오 주문 의도(OrderIntent.intent_type) 묶음 ---
# 체결은 매도 묶음을 먼저, 매수 묶음을 나중에 한다 (매도 대금을 매수에 쓴다)
SELL_INTENT_TYPES: Final = ("EXIT_ALL", "REDUCE_TO_TARGET")
BUY_INTENT_TYPES: Final = ("ENTER_TO_TARGET", "INCREASE_TO_TARGET")
# 보유를 목표 금액으로 증감하는 의도 (리밸런싱 · 배분 규칙의 비중 조정) — 진입 · 청산이 아니다
REBALANCE_INTENT_TYPES: Final = ("REDUCE_TO_TARGET", "INCREASE_TO_TARGET")

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


def portfolio_signal_filename(asset_key: str) -> str:
    """포트폴리오 자산 키별 시그널 파일명. 예: portfolio_signal_filename("qqq") -> 'signal_qqq.csv'"""
    return f"{PORTFOLIO_SIGNAL_PREFIX}{asset_key}.csv"
