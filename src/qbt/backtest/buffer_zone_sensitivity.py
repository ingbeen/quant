"""버퍼존 규칙 민감도 — 값을 하나씩 바꾼 결과로 과최적화를 판단할 표를 만든다.

합격 · 불합격을 내지 않는다 — 합격선을 정하는 것 자체가 과최적화다 (사용자 결정 2026-11-01).
결과와 판단은 `docs/research/전략_검증_보고서.md` 부록 N.

전략은 `BufferZoneV2Strategy` 를 옵션으로 돌린다. 신호와 매매는 같은 시세이고, 폭은 기본폭 × 배수다.
"""

from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Final

import pandas as pd

from qbt.backtest.constants import (
    COL_ENTRY_DATE,
    COL_EXIT_DATE,
    COL_PNL_PCT,
    DEFAULT_INITIAL_CAPITAL,
    SLIPPAGE_RATE,
    ma_col_name,
)
from qbt.backtest.engines.backtest_engine import prepare_common_period, run_backtest
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
    COL_OPEN,
    GLD_DATA_PATH,
    GSPC_DATA_PATH,
    IXIC_DATA_PATH,
    NDX_DATA_PATH,
    QLD_SYNTHETIC_DATA_PATH,
    QQQ_DATA_PATH,
    ROUND_PERCENT,
    ROUND_RATIO,
    SPY_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)

# 결과 파일 (러너가 쓰고 대시보드가 읽는다)
SENSITIVITY_RESULTS_DIR: Final = BACKTEST_RESULTS_DIR / "buffer_zone_sensitivity"
CELLS_FILENAME: Final = "cells.csv"
RULES_FILENAME: Final = "rules.csv"
TRADES_FILENAME: Final = "trades.csv"
CSV_ENCODING: Final = "utf-8-sig"

# 묶음 — 후보 값을 고를 때 어느 시세를 봤는가
GROUP_SEEN: Final = "만든 구간"
GROUP_UNSEEN: Final = "안 본 구간"
GROUP_FULL: Final = "전체 구간"

# 실험
EXPERIMENT_SELL: Final = "매도 폭"
EXPERIMENT_BUY: Final = "매수 폭"
EXPERIMENT_MA: Final = "이평선 기간"
EXPERIMENT_MONTH: Final = "한달 길이"
EXPERIMENT_RULE: Final = "규칙 조합"

# 거래 상태
STATUS_CLOSED: Final = "끝남"
STATUS_OPEN: Final = "보유 중"

# 결과 표의 열
DISPLAY_GROUP: Final = "묶음"
DISPLAY_DATASET: Final = "데이터"
DISPLAY_EXPERIMENT: Final = "실험"
DISPLAY_BASE_SELL: Final = "기준 매도 폭"
DISPLAY_VALUE: Final = "값"
DISPLAY_RULE: Final = "규칙"
DISPLAY_START: Final = "시작일"
DISPLAY_END: Final = "끝날"
DISPLAY_CAGR: Final = "연복리(%)"
DISPLAY_MDD: Final = "최대 낙폭(%)"
DISPLAY_CLOSED: Final = "끝난 거래"
DISPLAY_HELD: Final = "보유 날 비율(%)"
DISPLAY_BH_CAGR: Final = "Buy & Hold 연복리(%)"
DISPLAY_BH_MDD: Final = "Buy & Hold 최대 낙폭(%)"
DISPLAY_CAGR_DIFF: Final = "연복리 차이(%p)"
DISPLAY_MDD_DIFF: Final = "낙폭 차이(%p)"
DISPLAY_WINS: Final = "익절"
DISPLAY_LOSSES: Final = "손절"
DISPLAY_WORST: Final = "최악 거래 손익(%)"
DISPLAY_LOWEST: Final = "보유 중 진입가 대비 최저(%)"
DISPLAY_STATUS: Final = "상태"
DISPLAY_ENTRY_DATE: Final = "진입일"
DISPLAY_EXIT_DATE: Final = "청산일"
DISPLAY_PNL: Final = "손익(%)"

_PERCENT_COLUMNS: Final = (
    DISPLAY_CAGR,
    DISPLAY_MDD,
    DISPLAY_HELD,
    DISPLAY_BH_CAGR,
    DISPLAY_BH_MDD,
    DISPLAY_CAGR_DIFF,
    DISPLAY_MDD_DIFF,
    DISPLAY_WORST,
    DISPLAY_LOWEST,
    DISPLAY_PNL,
)
_RATIO_COLUMNS: Final = (DISPLAY_BASE_SELL, DISPLAY_VALUE)

# 탐색 값 — 폭은 배수를 곱하기 전 기본폭 (0.10 = 10%)
SELL_BASE_VALUES: Final = (
    0.03,
    0.04,
    0.05,
    0.06,
    0.07,
    0.075,
    0.08,
    0.09,
    0.10,
    0.11,
    0.12,
    0.125,
    0.13,
    0.14,
    0.15,
    0.16,
    0.18,
    0.20,
)
BUY_BASE_VALUES: Final = (0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.075, 0.08, 0.10, 0.12, 0.15)
MA_WINDOW_VALUES: Final = (100, 150, 200, 250, 300)
MONTH_DAYS_VALUES: Final = (15, 18, 20, 21, 22, 25)

# 매도 10% 가 의심 대상 → 그 위에서만 재면 결론이 거기 묶임
BASE_SELL_PCTS: Final = (0.05, 0.10)

_CANDIDATE_SELL_PCT: Final = 0.10

_YEAR_2004_START: Final = date(2004, 1, 2)
_GSPC_OHLC_START: Final = date(1962, 1, 2)  # 이 날부터 시가 · 고가 · 저가가 있음
_GSPC_UNSEEN_END: Final = date(1993, 11, 10)  # 다음 날이 SPY 측정 첫날
_NASDAQ_UNSEEN_END: Final = date(1999, 12, 20)  # 다음 날이 QQQ 측정 첫날


@dataclass(frozen=True)
class SensitivityDataset:
    """측정할 시세 하나와 그 구간. start 가 None 이면 이평선이 계산되는 첫날, end 가 None 이면 시세 끝이다."""

    label: str
    group: str
    data_path: Path
    leverage: int = 1
    start: date | None = None
    end: date | None = None


@dataclass(frozen=True)
class RuleParams:
    """규칙 값 한 벌. 폭은 배수를 곱하기 전 기본폭이다."""

    ma_window: int
    buy_base_pct: float
    sell_base_pct: float
    month_days: int
    wait_for_pullback: bool


@dataclass(frozen=True)
class SensitivityCase:
    """값 하나를 바꾼 칸. 매도 폭 실험은 기준 매도 폭이 없다 (base_sell_pct = None)."""

    experiment: str
    base_sell_pct: float | None
    value: float
    params: RuleParams


@dataclass(frozen=True)
class EntryStats:
    """진입가 대비 손익. 끝난 거래가 없으면 worst_pnl_pct, 산 적이 없으면 lowest_vs_entry_pct 가 None 이다."""

    closed: int
    wins: int
    losses: int
    worst_pnl_pct: float | None
    lowest_vs_entry_pct: float | None


@dataclass(frozen=True)
class SensitivityTables:
    """데이터 하나의 결과 행들 — 표시용 열 이름, 반올림 전 값."""

    cells: list[dict[str, object]]
    rules: list[dict[str, object]]
    trades: list[dict[str, object]]


DATASETS: Final = (
    SensitivityDataset("QQQ 2004 ~", GROUP_SEEN, QQQ_DATA_PATH, start=_YEAR_2004_START),
    SensitivityDataset("QLD 2004 ~", GROUP_SEEN, QLD_SYNTHETIC_DATA_PATH, leverage=2, start=_YEAR_2004_START),
    SensitivityDataset("TQQQ 2004 ~", GROUP_SEEN, TQQQ_SYNTHETIC_DATA_PATH, leverage=3, start=_YEAR_2004_START),
    SensitivityDataset("QQQ 1999 ~", GROUP_SEEN, QQQ_DATA_PATH),
    SensitivityDataset("QLD 1999 ~", GROUP_SEEN, QLD_SYNTHETIC_DATA_PATH, leverage=2),
    SensitivityDataset("TQQQ 1999 ~", GROUP_SEEN, TQQQ_SYNTHETIC_DATA_PATH, leverage=3),
    SensitivityDataset("SPY", GROUP_SEEN, SPY_DATA_PATH),
    SensitivityDataset("GLD", GROUP_SEEN, GLD_DATA_PATH),
    SensitivityDataset("TLT", GROUP_SEEN, TLT_DATA_PATH),
    SensitivityDataset("^GSPC 1962 ~ 1993", GROUP_UNSEEN, GSPC_DATA_PATH, start=_GSPC_OHLC_START, end=_GSPC_UNSEEN_END),
    SensitivityDataset("^NDX ~ 1999", GROUP_UNSEEN, NDX_DATA_PATH, end=_NASDAQ_UNSEEN_END),
    SensitivityDataset("^IXIC ~ 1999", GROUP_UNSEEN, IXIC_DATA_PATH, end=_NASDAQ_UNSEEN_END),
    SensitivityDataset("^GSPC 전체", GROUP_FULL, GSPC_DATA_PATH, start=_GSPC_OHLC_START),
    SensitivityDataset("^NDX 전체", GROUP_FULL, NDX_DATA_PATH),
    SensitivityDataset("^IXIC 전체", GROUP_FULL, IXIC_DATA_PATH),
)

_BASE_PARAMS: Final = RuleParams(
    ma_window=BUFFER_ZONE_V2_MA_WINDOW,
    buy_base_pct=BUFFER_ZONE_V2_BASE_BAND_PCT,
    sell_base_pct=BUFFER_ZONE_V2_BASE_BAND_PCT,
    month_days=BUFFER_ZONE_V2_MONTH_DAYS,
    wait_for_pullback=False,
)

RULE_COMBOS: Final = (
    ("V2 (눌림 있음 · 매도 5%)", replace(_BASE_PARAMS, wait_for_pullback=True)),
    ("눌림 제거 · 매도 5%", _BASE_PARAMS),
    ("눌림 있음 · 매도 10%", replace(_BASE_PARAMS, sell_base_pct=_CANDIDATE_SELL_PCT, wait_for_pullback=True)),
    ("눌림 제거 · 매도 10%", replace(_BASE_PARAMS, sell_base_pct=_CANDIDATE_SELL_PCT)),
)


def build_cases() -> list[SensitivityCase]:
    """값을 하나씩 바꾼 칸 전부를 만든다.

    Returns:
        매도 폭 실험 다음에 기준 매도 폭별 매수 폭 · 이평선 기간 · 한달 길이 실험 순서의 칸 목록
    """
    cases = [
        SensitivityCase(EXPERIMENT_SELL, None, value, replace(_BASE_PARAMS, sell_base_pct=value))
        for value in SELL_BASE_VALUES
    ]
    for base_sell in BASE_SELL_PCTS:
        base = replace(_BASE_PARAMS, sell_base_pct=base_sell)
        cases += [
            SensitivityCase(EXPERIMENT_BUY, base_sell, value, replace(base, buy_base_pct=value))
            for value in BUY_BASE_VALUES
        ]
        cases += [
            SensitivityCase(EXPERIMENT_MA, base_sell, value, replace(base, ma_window=value))
            for value in MA_WINDOW_VALUES
        ]
        cases += [
            SensitivityCase(EXPERIMENT_MONTH, base_sell, value, replace(base, month_days=value))
            for value in MONTH_DAYS_VALUES
        ]
    return cases


def slice_period(
    price_df: pd.DataFrame,
    ma_windows: list[int] | tuple[int, ...],
    start: date | None,
    end: date | None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """이평선을 계산한 뒤 구간을 자른다. 자른 뒤 계산하면 앞부분이 비어 시작일이 밀린다.

    Args:
        price_df: 시세 표 (신호와 매매에 같이 쓴다)
        ma_windows: 이평선 기간들 — 가장 긴 이평선이 계산되는 첫날보다 앞은 버린다
        start: 구간 시작일 (포함). None 이면 잘라내지 않는다
        end: 구간 끝날 (포함). None 이면 잘라내지 않는다

    Returns:
        (신호 표, 매매 표) — 신호 표에만 이평선 열이 있다
    """
    signal_df, trade_df = prepare_common_period(price_df, price_df, list(ma_windows))
    mask = pd.Series(True, index=signal_df.index)
    if start is not None:
        mask &= signal_df[COL_DATE] >= start
    if end is not None:
        mask &= signal_df[COL_DATE] <= end
    return signal_df[mask].reset_index(drop=True), trade_df[mask].reset_index(drop=True)


def run_rule(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    params: RuleParams,
    leverage: int,
) -> tuple[pd.DataFrame, pd.DataFrame, SummaryDict]:
    """규칙 값 한 벌로 백테스트한다.

    Args:
        signal_df: 신호 표 (params.ma_window 이평선 열 포함)
        trade_df: 매매 표
        params: 규칙 값
        leverage: 레버리지 배수 — 매수 · 매도 폭에 곱한다

    Returns:
        (거래 표, 에쿼티 표, 요약)
    """
    strategy = BufferZoneV2Strategy(
        ma_col_name(params.ma_window),
        params.buy_base_pct * leverage,
        params.month_days,
        sell_band_pct=params.sell_base_pct * leverage,
        wait_for_pullback=params.wait_for_pullback,
    )
    return run_backtest(strategy, signal_df, trade_df, DEFAULT_INITIAL_CAPITAL, log_trades=False)


def run_buy_and_hold(signal_df: pd.DataFrame, trade_df: pd.DataFrame) -> SummaryDict:
    """같은 구간의 Buy & Hold 요약. 첫날 신호로 둘째 날 시가에 산다."""
    _, _, summary = run_backtest(BuyAndHoldStrategy(), signal_df, trade_df, DEFAULT_INITIAL_CAPITAL, log_trades=False)
    return summary


def held_days_pct(equity_df: pd.DataFrame) -> float:
    """주식을 들고 있던 날의 비율 (%)."""
    return float((equity_df["position"] > 0).mean()) * 100.0


def _entry_price(trade_df: pd.DataFrame, entry_date: date) -> float:
    """그날 시가 + 슬리피지. 저장 진입가는 반올림돼 저가 시세에서 어긋남."""
    return float(trade_df.loc[trade_df[COL_DATE] == entry_date, COL_OPEN].iloc[0]) * (1 + SLIPPAGE_RATE)


def _lowest_vs_entry_pct(trade_df: pd.DataFrame, entry_date: date, exit_date: date | None) -> float:
    """보유 중 종가의 진입가 대비 최저 (%)."""
    held = trade_df[trade_df[COL_DATE] >= entry_date]
    if exit_date is not None:
        # 청산일은 종가 전에 팔림 → 그날 종가는 보유 중이 아님
        held = held[held[COL_DATE] < exit_date]
    if held.empty:
        raise RuntimeError(f"내부 불변조건 위반: 보유 중 종가가 없음 (진입일 {entry_date}, 청산일 {exit_date})")
    return (float(held[COL_CLOSE].min()) / _entry_price(trade_df, entry_date) - 1) * 100.0


def _holding_periods(trades_df: pd.DataFrame, summary: SummaryDict) -> list[tuple[date, date | None, float | None]]:
    """(진입일, 청산일, 손익 비율) 목록. 끝난 거래 뒤에 보유 중 거래가 오고, 보유 중은 청산일 · 손익이 None 이다."""
    periods: list[tuple[date, date | None, float | None]] = [
        (row[COL_ENTRY_DATE], row[COL_EXIT_DATE], float(row[COL_PNL_PCT])) for _, row in trades_df.iterrows()
    ]
    open_position = summary.get("open_position")
    if open_position is not None:
        periods.append((date.fromisoformat(open_position["entry_date"]), None, None))
    return periods


def entry_stats(trades_df: pd.DataFrame, summary: SummaryDict, trade_df: pd.DataFrame) -> EntryStats:
    """낙폭과 별개로 산 값보다 높게 팔았는지 본다.

    Args:
        trades_df: 끝난 거래 표
        summary: 요약 (보유 중 거래의 진입일)
        trade_df: 매매 표

    Returns:
        끝난 거래 수 · 익절 · 손절 · 최악 거래 손익(%) · 보유 중 진입가 대비 최저(%)
    """
    closed = len(trades_df)
    wins = int((trades_df[COL_PNL_PCT] > 0).sum())
    lows = [_lowest_vs_entry_pct(trade_df, entry, exit_) for entry, exit_, _ in _holding_periods(trades_df, summary)]
    return EntryStats(
        closed=closed,
        wins=wins,
        losses=closed - wins,
        worst_pnl_pct=float(trades_df[COL_PNL_PCT].min()) * 100.0 if closed > 0 else None,
        lowest_vs_entry_pct=min(lows) if lows else None,
    )


def _metrics_row(
    trades_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    summary: SummaryDict,
    buy_and_hold: SummaryDict,
    trade_df: pd.DataFrame,
) -> dict[str, object]:
    stats = entry_stats(trades_df, summary, trade_df)
    return {
        DISPLAY_START: summary["start_date"],
        DISPLAY_END: summary["end_date"],
        DISPLAY_CAGR: summary["cagr"],
        DISPLAY_MDD: summary["mdd"],
        DISPLAY_CLOSED: stats.closed,
        DISPLAY_HELD: held_days_pct(equity_df),
        DISPLAY_BH_CAGR: buy_and_hold["cagr"],
        DISPLAY_BH_MDD: buy_and_hold["mdd"],
        DISPLAY_CAGR_DIFF: summary["cagr"] - buy_and_hold["cagr"],
        DISPLAY_MDD_DIFF: summary["mdd"] - buy_and_hold["mdd"],
        DISPLAY_WINS: stats.wins,
        DISPLAY_LOSSES: stats.losses,
        DISPLAY_WORST: stats.worst_pnl_pct,
        DISPLAY_LOWEST: stats.lowest_vs_entry_pct,
    }


def _trade_rows(
    key: dict[str, object],
    trades_df: pd.DataFrame,
    summary: SummaryDict,
    trade_df: pd.DataFrame,
) -> list[dict[str, object]]:
    """칸 하나의 거래 행. 보유 중 거래의 손익은 마지막 종가로 평가한 값이다."""
    rows: list[dict[str, object]] = []
    for entry, exit_, pnl_ratio in _holding_periods(trades_df, summary):
        if pnl_ratio is None:
            pnl_pct = (float(trade_df[COL_CLOSE].iloc[-1]) / _entry_price(trade_df, entry) - 1) * 100.0
        else:
            pnl_pct = pnl_ratio * 100.0
        rows.append(
            {
                **key,
                DISPLAY_STATUS: STATUS_OPEN if exit_ is None else STATUS_CLOSED,
                DISPLAY_ENTRY_DATE: entry,
                DISPLAY_EXIT_DATE: exit_,
                DISPLAY_PNL: pnl_pct,
                DISPLAY_LOWEST: _lowest_vs_entry_pct(trade_df, entry, exit_),
            }
        )
    return rows


def evaluate_dataset(dataset: SensitivityDataset, price_df: pd.DataFrame) -> SensitivityTables:
    """데이터 하나의 칸 · 규칙 조합 · 거래 목록을 만든다.

    이평선 실험은 값마다 같은 기간(가장 긴 이평선이 계산되는 첫날부터)으로 재고, Buy & Hold 도 그 기간으로 맞춘다.

    Args:
        dataset: 데이터와 구간
        price_df: 시세 표

    Returns:
        표시용 열 이름의 결과 행들 (반올림 전)
    """
    base_period = slice_period(price_df, [BUFFER_ZONE_V2_MA_WINDOW], dataset.start, dataset.end)
    ma_period = slice_period(price_df, MA_WINDOW_VALUES, dataset.start, dataset.end)
    base_buy_and_hold = run_buy_and_hold(*base_period)
    ma_buy_and_hold = run_buy_and_hold(*ma_period)
    names: dict[str, object] = {DISPLAY_GROUP: dataset.group, DISPLAY_DATASET: dataset.label}

    cells: list[dict[str, object]] = []
    rules: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []

    for case in build_cases():
        is_ma = case.experiment == EXPERIMENT_MA
        signal_df, trade_df = ma_period if is_ma else base_period
        trades_df, equity_df, summary = run_rule(signal_df, trade_df, case.params, dataset.leverage)
        key: dict[str, object] = {
            **names,
            DISPLAY_EXPERIMENT: case.experiment,
            DISPLAY_BASE_SELL: case.base_sell_pct,
            DISPLAY_VALUE: case.value,
        }
        buy_and_hold = ma_buy_and_hold if is_ma else base_buy_and_hold
        cells.append({**key, **_metrics_row(trades_df, equity_df, summary, buy_and_hold, trade_df)})
        trades += _trade_rows(key, trades_df, summary, trade_df)

    signal_df, trade_df = base_period
    for rule_name, params in RULE_COMBOS:
        trades_df, equity_df, summary = run_rule(signal_df, trade_df, params, dataset.leverage)
        metrics = _metrics_row(trades_df, equity_df, summary, base_buy_and_hold, trade_df)
        rules.append({**names, DISPLAY_RULE: rule_name, **metrics})
        key = {**names, DISPLAY_EXPERIMENT: EXPERIMENT_RULE, DISPLAY_BASE_SELL: None, DISPLAY_VALUE: rule_name}
        trades += _trade_rows(key, trades_df, summary, trade_df)

    return SensitivityTables(cells=cells, rules=rules, trades=trades)


def round_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """결과 표의 % 열은 ROUND_PERCENT, 비율 열은 ROUND_RATIO 자리로 반올림한다. 표에 없는 열은 건너뛴다."""
    digits = {col: ROUND_PERCENT for col in _PERCENT_COLUMNS} | {col: ROUND_RATIO for col in _RATIO_COLUMNS}
    return df.round({col: digit for col, digit in digits.items() if col in df.columns})
