"""버퍼존 세 줄 — 돈을 3등분해 매도선만 다르게 둔 규칙과 투자자별 결과를 잰다.

합격 · 불합격을 내지 않는다 — 합격선을 정하는 것 자체가 과최적화다 (사용자 결정 2026-11-01).
결과와 판단은 `docs/research/전략_검증_보고서.md` 부록 N.

세 몫의 매수 규칙은 같고 몫끼리 돈을 옮기지 않는다. 각 몫을 같은 돈으로 돌려 자산을 평균한다 —
수익률 · 낙폭은 3등분의 합과 같은 뜻이고, 정수 주수로 나뉘는 차이가 생기지 않는다.
합성 시세는 이 모듈이 만들지 않는다 — 도메인 경계를 지켜 러너가 `qbt.tqqq` 로 만들어 넘긴다.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, cast

import pandas as pd

from qbt.backtest.analysis import calculate_drawdown_pct_series, calculate_summary
from qbt.backtest.buffer_zone_sensitivity import (
    DISPLAY_BH_CAGR,
    DISPLAY_BH_MDD,
    DISPLAY_CAGR,
    DISPLAY_CLOSED,
    DISPLAY_END,
    DISPLAY_ENTRY_DATE,
    DISPLAY_EXIT_DATE,
    DISPLAY_LOSSES,
    DISPLAY_LOWEST,
    DISPLAY_MDD,
    DISPLAY_PNL,
    DISPLAY_START,
    DISPLAY_STATUS,
    DISPLAY_WINS,
    DISPLAY_WORST,
    STATUS_CLOSED,
    EntryStats,
    entry_price,
    round_for_csv,
    slice_period,
    trade_rows,
)
from qbt.backtest.constants import COL_EQUITY, COL_PNL, DEFAULT_INITIAL_CAPITAL, ma_col_name
from qbt.backtest.engines.backtest_engine import run_backtest
from qbt.backtest.strategies.buffer_zone_v2 import (
    BUFFER_ZONE_V2_BASE_BAND_PCT,
    BUFFER_ZONE_V2_MA_WINDOW,
    BUFFER_ZONE_V2_MONTH_DAYS,
    BufferZoneV2Strategy,
)
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldStrategy
from qbt.backtest.types import SummaryDict
from qbt.common_constants import (
    BACKTEST_RESULTS_DIR,
    COL_CLOSE,
    COL_DATE,
    NDX_DATA_PATH,
    QLD_SYNTHETIC_DATA_PATH,
    QQQ_DATA_PATH,
    ROUND_PERCENT,
    ROUND_RATIO,
    TQQQ_SYNTHETIC_DATA_PATH,
)

# 결과 파일 (러너가 쓰고 대시보드가 읽는다)
THREE_LINES_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buffer_zone_three_lines"
INVESTORS_FILENAME: Final = "investors.csv"
THREE_LINES_TRADES_FILENAME: Final = "trades.csv"
PLATEAU_FILENAME: Final = "plateau.csv"
EQUITY_FILENAME: Final = "equity.csv"

# 투자자 — 앞 둘이 본 답, 뒤 둘은 가정을 바꾼 대조
INVESTOR_2004: Final = "2004년 투자자"
INVESTOR_DOTCOM: Final = "닷컴 경험 투자자"
CHECK_COST_CAP: Final = "대조 — 비용 상한"
CHECK_PRE_BUBBLE: Final = "대조 — 버블 직전 진입"
MAIN_INVESTORS: Final = (INVESTOR_2004, INVESTOR_DOTCOM)

# 고원 표의 방식
METHOD_THREE: Final = "세 줄"
METHOD_ONE: Final = "한 줄"

# 결과 표의 열 (나머지는 민감도 표와 같은 이름을 쓴다)
DISPLAY_INVESTOR: Final = "투자자"
DISPLAY_LEVERAGE: Final = "배수"
DISPLAY_FIRST_BUY: Final = "첫 매수일"
DISPLAY_HELD_AT_PEAK: Final = "닷컴 고점 날 보유 몫"
DISPLAY_FINAL: Final = "최종 자산 배수"
DISPLAY_DOTCOM: Final = "닷컴 구간 낙폭(%)"
DISPLAY_BH_FINAL: Final = "Buy & Hold 최종 자산 배수"
DISPLAY_BH_DOTCOM: Final = "Buy & Hold 닷컴 구간 낙폭(%)"
DISPLAY_SELL_LINE: Final = "매도선(%)"
DISPLAY_FROM_PEAK: Final = "보유 중 고점 대비(%)"
DISPLAY_CENTER: Final = "가운데 매도 폭(%)"
DISPLAY_METHOD: Final = "방식"
DISPLAY_EQUITY_DATE: Final = "날짜"
DISPLAY_THREE_MULTIPLE: Final = "세 줄 자산 배수"
DISPLAY_BH_MULTIPLE: Final = "Buy & Hold 자산 배수"

_NEW_PERCENT_COLUMNS: Final = (DISPLAY_FROM_PEAK, DISPLAY_DOTCOM, DISPLAY_BH_DOTCOM)
_MULTIPLE_COLUMNS: Final = (DISPLAY_FINAL, DISPLAY_BH_FINAL, DISPLAY_THREE_MULTIPLE, DISPLAY_BH_MULTIPLE)

# 매도선 — 폭은 배수를 곱하기 전 기본폭 (0.10 = 10%)
_CENTER_SELL_PCT: Final = 0.10
_LINE_OFFSET_PCT: Final = 0.025
PLATEAU_CENTERS: Final = (0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15)

# 나스닥 종합 지수 고점과 저점 달 — 나스닥 100 고점(2000-03-27)도 이 안
DOTCOM_PEAK_DATE: Final = date(2000, 3, 10)
DOTCOM_END_DATE: Final = date(2002, 10, 31)

_YEAR_2004_START: Final = date(2004, 1, 2)

_ROUND_WIDTH: Final = 4


def line_widths(center: float) -> tuple[float, float, float]:
    """가운데 값의 세 매도 기본폭. 더하기 오차가 폭에 남으면 칸마다 밴드가 미세하게 달라져 반올림한다.

    Args:
        center: 가운데 매도 기본폭 (0.10 = 10%)

    Returns:
        좁은 몫 · 가운데 몫 · 넓은 몫의 기본폭
    """
    return (
        round(center - _LINE_OFFSET_PCT, _ROUND_WIDTH),
        round(center, _ROUND_WIDTH),
        round(center + _LINE_OFFSET_PCT, _ROUND_WIDTH),
    )


SELL_LINES: Final = line_widths(_CENTER_SELL_PCT)


@dataclass(frozen=True)
class ThreeLinesCase:
    """투자자 × 배수 하나. synthetic 이면 러너가 data_path 시세를 leverage 배로 합성해 넘긴다.

    start 가 None 이면 이평선이 계산되는 첫날부터다. 끝날은 늘 시세 끝이다.
    """

    investor: str
    leverage: int
    data_path: Path
    synthetic: bool = False
    capped_cost: bool = False
    start: date | None = None
    held_from_start: bool = False


@dataclass(frozen=True)
class ThreeLinesTables:
    """판 하나의 결과 — 표시용 열 이름, 반올림 전 값. 대조 판은 plateau · equity 가 비어 있다."""

    investor_row: dict[str, object]
    trades: list[dict[str, object]]
    plateau: list[dict[str, object]]
    equity: pd.DataFrame


CASES: Final = (
    ThreeLinesCase(INVESTOR_2004, 1, QQQ_DATA_PATH, start=_YEAR_2004_START),
    ThreeLinesCase(INVESTOR_2004, 2, QLD_SYNTHETIC_DATA_PATH, start=_YEAR_2004_START),
    ThreeLinesCase(INVESTOR_2004, 3, TQQQ_SYNTHETIC_DATA_PATH, start=_YEAR_2004_START),
    ThreeLinesCase(INVESTOR_DOTCOM, 1, NDX_DATA_PATH),
    ThreeLinesCase(INVESTOR_DOTCOM, 2, NDX_DATA_PATH, synthetic=True),
    ThreeLinesCase(INVESTOR_DOTCOM, 3, NDX_DATA_PATH, synthetic=True),
    ThreeLinesCase(CHECK_COST_CAP, 2, NDX_DATA_PATH, synthetic=True, capped_cost=True),
    ThreeLinesCase(CHECK_COST_CAP, 3, NDX_DATA_PATH, synthetic=True, capped_cost=True),
    ThreeLinesCase(CHECK_PRE_BUBBLE, 1, QQQ_DATA_PATH, held_from_start=True),
    ThreeLinesCase(CHECK_PRE_BUBBLE, 2, QLD_SYNTHETIC_DATA_PATH, held_from_start=True),
    ThreeLinesCase(CHECK_PRE_BUBBLE, 3, TQQQ_SYNTHETIC_DATA_PATH, held_from_start=True),
)


class _HeldFromStartStrategy(BufferZoneV2Strategy):
    """이미 들고 있던 사람 — 첫날 신호로 둘째 날 시가에 산다. Buy & Hold 와 같은 시점이고, 그 뒤는 같은 규칙이다."""

    def check_buy(self, signal_df: pd.DataFrame, i: int) -> bool:
        if i == 0:
            return True
        return super().check_buy(signal_df, i)


def run_line(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    sell_base_pct: float,
    leverage: int,
    *,
    held_from_start: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, SummaryDict]:
    """몫 하나를 돌린다. 눌림 제거 · 이평선 200일 · 한달 21거래일 · 매수 5% 고정이고 폭은 기본폭 × 배수다.

    Args:
        signal_df: 신호 표 (200일 이평선 열 포함)
        trade_df: 매매 표
        sell_base_pct: 매도 기본폭 (0.10 = 10%)
        leverage: 레버리지 배수
        held_from_start: True 면 빈손 대신 둘째 날 시가에 산다

    Returns:
        (거래 표, 에쿼티 표, 요약)
    """
    strategy_class = _HeldFromStartStrategy if held_from_start else BufferZoneV2Strategy
    strategy = strategy_class(
        ma_col_name(BUFFER_ZONE_V2_MA_WINDOW),
        BUFFER_ZONE_V2_BASE_BAND_PCT * leverage,
        BUFFER_ZONE_V2_MONTH_DAYS,
        sell_band_pct=sell_base_pct * leverage,
        wait_for_pullback=False,
    )
    return run_backtest(strategy, signal_df, trade_df, DEFAULT_INITIAL_CAPITAL, log_trades=False)


def average_equity(equity_dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """몫들의 자산을 날짜별로 평균한다.

    Args:
        equity_dfs: 같은 날짜를 가진 몫별 에쿼티 표

    Returns:
        Date · equity 열만 있는 표

    Raises:
        RuntimeError: 몫의 날짜가 서로 다를 때 (같은 시세를 돌렸으므로 도달 불가)
    """
    first_dates = equity_dfs[0][COL_DATE].tolist()
    for equity_df in equity_dfs[1:]:
        if equity_df[COL_DATE].tolist() != first_dates:
            raise RuntimeError(f"내부 불변조건 위반: 몫의 날짜가 다르다 (첫 몫 {len(first_dates)}행, 다른 몫 {len(equity_df)}행)")
    equities = pd.concat(
        [equity_df[COL_EQUITY].astype(float).reset_index(drop=True) for equity_df in equity_dfs], axis=1
    )
    return pd.DataFrame({COL_DATE: first_dates, COL_EQUITY: equities.mean(axis=1)})


def from_peak_pct(trade_df: pd.DataFrame, entry_date: date, exit_date: date | None, pnl_pct: float) -> float:
    """거래를 끝낸 값이 보유 중 최고 종가보다 얼마나 낮은가 (%). 진입가 대비 손익과 나란히 보는 낙폭이다.

    Args:
        trade_df: 매매 표
        entry_date: 진입일
        exit_date: 청산일. None 이면 보유 중이라 마지막 종가까지 본다
        pnl_pct: 진입가 대비 손익 (%, +10.0 = 10%)

    Returns:
        고점 대비 (%, -25.0 = 25% 낮음)

    Raises:
        RuntimeError: 보유 중 종가가 없을 때
    """
    held = trade_df[trade_df[COL_DATE] >= entry_date]
    if exit_date is not None:
        # 청산일은 종가 전에 팔림 → 그날 종가는 보유 중이 아님
        held = held[held[COL_DATE] < exit_date]
    if held.empty:
        raise RuntimeError(f"내부 불변조건 위반: 보유 중 종가가 없음 (진입일 {entry_date}, 청산일 {exit_date})")
    value = entry_price(trade_df, entry_date) * (1 + pnl_pct / 100.0)
    return (value / float(held[COL_CLOSE].max()) - 1) * 100.0


def window_drawdown_pct(dates: list[date], values: pd.Series) -> float | None:
    """닷컴 구간 안의 최대 낙폭 (%). 구간 안 고점 대비이고, 구간을 겪지 않았으면 None 이다.

    Args:
        dates: 날짜 목록
        values: 같은 길이의 자산 값

    Returns:
        낙폭 (%, 0 이하) 또는 None
    """
    in_window = [DOTCOM_PEAK_DATE <= day <= DOTCOM_END_DATE for day in dates]
    window = values.reset_index(drop=True)[in_window]
    if window.empty:
        return None
    return float(calculate_drawdown_pct_series(window).min())


def held_lines_on(periods: list[tuple[date, date | None]], day: date) -> int:
    """그날 들고 있는 몫의 수. 그날 시가에 산 몫은 들고 있고, 그날 판 몫은 들고 있지 않다.

    Args:
        periods: (진입일, 청산일) 목록. 보유 중이면 청산일이 None
        day: 볼 날

    Returns:
        몫의 수
    """
    return sum(1 for entry, exit_ in periods if entry <= day and (exit_ is None or exit_ > day))


def _equity_summary(equity: pd.DataFrame) -> SummaryDict:
    """합친 자본 곡선의 요약. 거래를 세는 칸은 몫별 표에서 따로 센다 — 여기 값은 0 이고 쓰지 않는다."""
    return calculate_summary(pd.DataFrame(columns=[COL_PNL]), equity, DEFAULT_INITIAL_CAPITAL)


def trade_row_stats(rows: list[dict[str, object]]) -> EntryStats:
    """세 몫의 매도 내역을 몫별 한 건씩 센다. 손익 0 은 손절이다 — 비용을 내고 본전이면 번 것이 없다.

    Args:
        rows: 민감도 거래 행 모양의 행들 (보유 중 행 포함)

    Returns:
        끝난 거래 수 · 익절 · 손절 · 최악 거래 손익(%) · 보유 중까지 본 진입가 대비 최저(%)
    """
    closed_pnls = [cast(float, row[DISPLAY_PNL]) for row in rows if row[DISPLAY_STATUS] == STATUS_CLOSED]
    wins = sum(1 for pnl in closed_pnls if pnl > 0)
    return EntryStats(
        closed=len(closed_pnls),
        wins=wins,
        losses=len(closed_pnls) - wins,
        worst_pnl_pct=min(closed_pnls, default=None),
        lowest_vs_entry_pct=min((cast(float, row[DISPLAY_LOWEST]) for row in rows), default=None),
    )


def _line_trade_rows(
    names: dict[str, object],
    sell_base_pct: float,
    leverage: int,
    trades_df: pd.DataFrame,
    summary: SummaryDict,
    trade_df: pd.DataFrame,
) -> list[dict[str, object]]:
    """몫 하나의 매도 내역 — 민감도의 거래 행에 매도선과 고점 대비를 더한다."""
    key = {**names, DISPLAY_SELL_LINE: round(sell_base_pct * leverage * 100.0, ROUND_PERCENT)}
    rows = trade_rows(key, trades_df, summary, trade_df)
    for row in rows:
        row[DISPLAY_FROM_PEAK] = from_peak_pct(
            trade_df,
            cast(date, row[DISPLAY_ENTRY_DATE]),
            cast("date | None", row[DISPLAY_EXIT_DATE]),
            cast(float, row[DISPLAY_PNL]),
        )
    return rows


def _investor_row(
    names: dict[str, object],
    signal_df: pd.DataFrame,
    trades: list[dict[str, object]],
    equity: pd.DataFrame,
    buy_and_hold_equity: pd.DataFrame,
    buy_and_hold: SummaryDict,
) -> dict[str, object]:
    """판 하나의 요약 행. 세 몫을 합친 값이고, 거래를 세는 칸은 몫별 매도를 한 건씩 센다."""
    dates = signal_df[COL_DATE].tolist()
    summary = _equity_summary(equity)
    stats = trade_row_stats(trades)
    periods = [(cast(date, row[DISPLAY_ENTRY_DATE]), cast("date | None", row[DISPLAY_EXIT_DATE])) for row in trades]
    dotcom = window_drawdown_pct(dates, equity[COL_EQUITY])
    return {
        **names,
        DISPLAY_START: summary["start_date"],
        DISPLAY_END: summary["end_date"],
        DISPLAY_FIRST_BUY: min((entry for entry, _ in periods), default=None),
        DISPLAY_HELD_AT_PEAK: None if dotcom is None else held_lines_on(periods, DOTCOM_PEAK_DATE),
        DISPLAY_FINAL: summary["final_capital"] / DEFAULT_INITIAL_CAPITAL,
        DISPLAY_CAGR: summary["cagr"],
        DISPLAY_MDD: summary["mdd"],
        DISPLAY_DOTCOM: dotcom,
        DISPLAY_CLOSED: stats.closed,
        DISPLAY_WINS: stats.wins,
        DISPLAY_LOSSES: stats.losses,
        DISPLAY_WORST: stats.worst_pnl_pct,
        DISPLAY_LOWEST: stats.lowest_vs_entry_pct,
        DISPLAY_BH_FINAL: buy_and_hold["final_capital"] / DEFAULT_INITIAL_CAPITAL,
        DISPLAY_BH_CAGR: buy_and_hold["cagr"],
        DISPLAY_BH_MDD: buy_and_hold["mdd"],
        DISPLAY_BH_DOTCOM: window_drawdown_pct(dates, buy_and_hold_equity[COL_EQUITY]),
    }


def _plateau_rows(
    names: dict[str, object],
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    leverage: int,
    buy_and_hold: SummaryDict,
) -> list[dict[str, object]]:
    """가운데 값마다 세 줄과 한 줄. 가운데 값끼리 폭이 겹쳐 폭마다 한 번만 돌린다 (백테스트 한 번이 0.5초 안팎)."""
    runs: dict[float, tuple[pd.DataFrame, pd.DataFrame, SummaryDict]] = {}

    def run_width(width: float) -> tuple[pd.DataFrame, pd.DataFrame, SummaryDict]:
        if width not in runs:
            runs[width] = run_line(signal_df, trade_df, width, leverage)
        return runs[width]

    def row(method: str, center: float, cagr: float, mdd: float, closed: int) -> dict[str, object]:
        return {
            **names,
            DISPLAY_METHOD: method,
            DISPLAY_CENTER: round(center * 100.0, ROUND_PERCENT),
            DISPLAY_CAGR: cagr,
            DISPLAY_MDD: mdd,
            DISPLAY_CLOSED: closed,
            DISPLAY_BH_CAGR: buy_and_hold["cagr"],
            DISPLAY_BH_MDD: buy_and_hold["mdd"],
        }

    rows: list[dict[str, object]] = []
    for center in PLATEAU_CENTERS:
        widths = line_widths(center)
        line_runs = [run_width(width) for width in widths]
        equity = average_equity([equity_df for _, equity_df, _ in line_runs])
        three = _equity_summary(equity)
        closed = sum(len(trades_df) for trades_df, _, _ in line_runs)
        rows.append(row(METHOD_THREE, center, three["cagr"], three["mdd"], closed))

        trades_df, _, one = run_width(widths[1])
        rows.append(row(METHOD_ONE, center, one["cagr"], one["mdd"], len(trades_df)))
    return rows


def evaluate_case(case: ThreeLinesCase, price_df: pd.DataFrame) -> ThreeLinesTables:
    """판 하나의 요약 · 매도 내역 · 고원 · 일별 자산을 만든다.

    Args:
        case: 투자자와 배수
        price_df: 시세 표 (합성이면 합성한 표)

    Returns:
        표시용 열 이름의 결과 (반올림 전)
    """
    signal_df, trade_df = slice_period(price_df, [BUFFER_ZONE_V2_MA_WINDOW], case.start, None)
    names: dict[str, object] = {DISPLAY_INVESTOR: case.investor, DISPLAY_LEVERAGE: case.leverage}

    line_equities: list[pd.DataFrame] = []
    trades: list[dict[str, object]] = []
    for width in SELL_LINES:
        trades_df, equity_df, summary = run_line(
            signal_df, trade_df, width, case.leverage, held_from_start=case.held_from_start
        )
        line_equities.append(equity_df)
        trades += _line_trade_rows(names, width, case.leverage, trades_df, summary, trade_df)
    equity = average_equity(line_equities)

    _, buy_and_hold_equity, buy_and_hold = run_backtest(
        BuyAndHoldStrategy(), signal_df, trade_df, DEFAULT_INITIAL_CAPITAL, log_trades=False
    )
    investor_row = _investor_row(names, signal_df, trades, equity, buy_and_hold_equity, buy_and_hold)

    if case.investor not in MAIN_INVESTORS:
        return ThreeLinesTables(investor_row, trades, [], pd.DataFrame())

    plateau = _plateau_rows(names, signal_df, trade_df, case.leverage, buy_and_hold)
    equity_table = pd.DataFrame(
        {
            DISPLAY_INVESTOR: case.investor,
            DISPLAY_LEVERAGE: case.leverage,
            DISPLAY_EQUITY_DATE: equity[COL_DATE],
            DISPLAY_THREE_MULTIPLE: equity[COL_EQUITY] / DEFAULT_INITIAL_CAPITAL,
            DISPLAY_BH_MULTIPLE: buy_and_hold_equity[COL_EQUITY].astype(float).to_numpy() / DEFAULT_INITIAL_CAPITAL,
        }
    )
    return ThreeLinesTables(investor_row, trades, plateau, equity_table)


def round_three_lines_csv(df: pd.DataFrame) -> pd.DataFrame:
    """결과 표를 저장 자릿수로 반올림한다. 민감도와 같은 열은 그 규칙을 쓴다. 표에 없는 열은 건너뛴다."""
    digits = {col: ROUND_PERCENT for col in _NEW_PERCENT_COLUMNS} | {col: ROUND_RATIO for col in _MULTIPLE_COLUMNS}
    return round_for_csv(df).round({col: digit for col, digit in digits.items() if col in df.columns})
