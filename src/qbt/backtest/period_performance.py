"""구간별 성과 계산

자본 곡선을 구간으로 잘라 본다 — 기간 나눠 보기 · 하락장 / 횡보장 · 시작 달 바꿔 보기 · 수익 쏠림.
러너가 `summary.json` 에 저장하고 대시보드가 읽는다. 값은 저장 형태로 반올림해 돌려준다.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final, TypedDict

import pandas as pd

from qbt.backtest.analysis import calculate_drawdown_pct_series, calculate_yearly_returns
from qbt.backtest.constants import COL_EQUITY, MIN_VALID_ROWS
from qbt.common_constants import ANNUAL_DAYS, COL_CLOSE, COL_DATE, ROUND_PERCENT

KIND_BEAR: Final = "하락장"
KIND_SIDEWAYS: Final = "횡보장"

_RECENT_YEARS: Final = (20, 10, 5, 3)

# 날짜는 SPY 합성 종가의 고점 · 바닥 → 전략 결과를 보고 고른 값이 아님
_SINCE_PERIODS: Final = (
    ("닷컴 정점부터", "2000-03-24"),
    ("닷컴 바닥 뒤부터", "2002-10-09"),
    ("금융위기 직전 고점부터", "2007-10-09"),
    ("금융위기 바닥 뒤부터", "2009-03-09"),
)

# (종류, 이름, 시작일, 끝날)
_MARKET_REGIMES: Final = (
    (KIND_BEAR, "1987 블랙먼데이", "1987-08-25", "1987-10-19"),
    (KIND_BEAR, "1990 걸프전", "1990-07-16", "1990-10-11"),
    (KIND_BEAR, "1998 LTCM 사태", "1998-07-17", "1998-08-31"),
    (KIND_BEAR, "닷컴 붕괴", "2000-03-24", "2002-10-09"),
    (KIND_BEAR, "금융위기", "2007-10-09", "2009-03-09"),
    (KIND_BEAR, "2011 유럽재정위기", "2011-04-29", "2011-10-03"),
    (KIND_BEAR, "2018 4분기", "2018-09-20", "2018-12-24"),
    (KIND_BEAR, "코로나", "2020-02-19", "2020-03-23"),
    (KIND_BEAR, "2022 긴축", "2022-01-03", "2022-10-12"),
    (KIND_BEAR, "2025 관세", "2025-02-19", "2025-04-08"),
    (KIND_SIDEWAYS, "1994 금리 인상", "1994-01-01", "1994-12-31"),
    (KIND_SIDEWAYS, "2015 ~ 16 박스권", "2015-01-01", "2016-06-30"),
)

_ROLLING_YEARS: Final = (5, 10)


class SplitRow(TypedDict):
    """기간 나눠 보기의 한 줄. 값이 없는 구간은 요청한 날짜와 None 값을 갖는다."""

    label: str
    start_date: str
    end_date: str
    cagr: float | None
    mdd: float | None
    total_return_pct: float | None


class RegimeRow(TypedDict):
    """하락장 · 횡보장의 한 줄. 값이 없는 국면은 정의한 날짜와 None 값을 갖는다."""

    kind: str
    label: str
    start_date: str
    end_date: str
    return_pct: float | None
    mdd: float | None
    signal_return_pct: float | None


class RollingPoint(TypedDict):
    """그달 첫 거래일에 시작해 정해진 햇수를 보유했을 때의 연 수익."""

    start_date: str
    cagr: float


class RollingHorizon(TypedDict):
    """보유 햇수 하나의 시작 달별 연 수익과 요약. 경우가 0 이면 요약 값은 None 이다."""

    years: int
    points: list[RollingPoint]
    count: int
    min_cagr: float | None
    min_start_date: str | None
    p10_cagr: float | None
    median_cagr: float | None
    negative_count: int


class ConcentrationDict(TypedDict):
    """연간 수익률로 본 수익 쏠림. 전체 합이 0 이하면 몫은 None 이다."""

    year_count: int
    positive_years: int
    negative_years: int
    median_pct: float
    mean_pct: float
    top_years: list[int]
    top3_share_pct: float | None
    mean_without_top3_pct: float
    mean_without_top5_pct: float


class PeriodPerformanceDict(TypedDict):
    """`summary.json` 의 구간별 성과."""

    splits: list[SplitRow]
    regimes: list[RegimeRow]
    rolling: list[RollingHorizon]
    concentration: ConcentrationDict


class YearlyAssetContribution(TypedDict):
    """한 해의 수익률과 자산별 기여(%p, 직전 연말 계좌 대비). other_pct 는 자산에 나뉘지 않은 몫이다."""

    year: int
    return_pct: float
    assets: dict[str, float]
    other_pct: float


def _require_min_rows(equity_df: pd.DataFrame) -> None:
    if len(equity_df) < MIN_VALID_ROWS:
        raise ValueError(f"자본 곡선은 {MIN_VALID_ROWS}행 이상이어야 합니다: {len(equity_df)}행")


def _date_indexed(df: pd.DataFrame, col: str) -> pd.Series[float]:
    index = pd.DatetimeIndex(pd.to_datetime(df[COL_DATE]))
    return pd.Series(df[col].astype(float).to_numpy(), index=index).sort_index()


def _iso(day: pd.Timestamp) -> str:
    return day.strftime("%Y-%m-%d")


def _pct(value: float) -> float:
    # 0.0 을 더해 -0.0 제거 → 표에 「-0.00」으로 보이는 것을 막음
    return round(float(value), ROUND_PERCENT) + 0.0


def _return_pct(window: pd.Series[float]) -> float:
    return (float(window.iloc[-1]) / float(window.iloc[0]) - 1) * 100


def _cagr_pct(first_value: float, last_value: float, days: int) -> float:
    if first_value <= 0 or last_value <= 0 or days <= 0:
        raise RuntimeError(
            f"내부 불변조건 위반: 연 수익을 잴 수 없다 (first_value={first_value}, last_value={last_value}, days={days})"
        )
    return ((last_value / first_value) ** (ANNUAL_DAYS / days) - 1) * 100


def _mdd_pct(window: pd.Series[float]) -> float:
    return float(calculate_drawdown_pct_series(window).min())


def _measurable_window(equity: pd.Series[float], start: pd.Timestamp, end: pd.Timestamp) -> pd.Series[float] | None:
    # 구간이 데이터 밖으로 나가면 값 없음 → 일부만 잰 값이 온전한 값처럼 읽히는 것을 막음
    if start < equity.index[0] or end > equity.index[-1]:
        return None
    window = equity.loc[start:end]
    return window if len(window) >= MIN_VALID_ROWS else None


def _requested_splits(equity: pd.Series[float]) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    first, last = equity.index[0], equity.index[-1]
    middle = equity.index[equity.index.searchsorted(first + (last - first) / 2, side="right") - 1]
    return [
        ("전체", first, last),
        ("앞 절반", first, middle),
        ("뒤 절반", middle, last),
        *((f"최근 {years}년", last - pd.DateOffset(years=years), last) for years in _RECENT_YEARS),
        *((label, pd.Timestamp(day), last) for label, day in _SINCE_PERIODS),
    ]


def _split_row(equity: pd.Series[float], label: str, start: pd.Timestamp, end: pd.Timestamp) -> SplitRow:
    window = _measurable_window(equity, start, end)
    if window is None:
        return SplitRow(
            label=label, start_date=_iso(start), end_date=_iso(end), cagr=None, mdd=None, total_return_pct=None
        )
    days = (window.index[-1] - window.index[0]).days
    return SplitRow(
        label=label,
        start_date=_iso(window.index[0]),
        end_date=_iso(window.index[-1]),
        cagr=_pct(_cagr_pct(float(window.iloc[0]), float(window.iloc[-1]), days)),
        mdd=_pct(_mdd_pct(window)),
        total_return_pct=_pct(_return_pct(window)),
    )


def _regime_row(
    equity: pd.Series[float], signal: pd.Series[float] | None, kind: str, label: str, start: str, end: str
) -> RegimeRow:
    window = _measurable_window(equity, pd.Timestamp(start), pd.Timestamp(end))
    if window is None:
        return RegimeRow(
            kind=kind, label=label, start_date=start, end_date=end, return_pct=None, mdd=None, signal_return_pct=None
        )
    signal_return_pct: float | None = None
    if signal is not None:
        signal_window = signal.loc[window.index[0] : window.index[-1]]
        if len(signal_window) >= MIN_VALID_ROWS:
            signal_return_pct = _pct(_return_pct(signal_window))
    return RegimeRow(
        kind=kind,
        label=label,
        start_date=_iso(window.index[0]),
        end_date=_iso(window.index[-1]),
        return_pct=_pct(_return_pct(window)),
        mdd=_pct(_mdd_pct(window)),
        signal_return_pct=signal_return_pct,
    )


def _rolling_horizon(equity: pd.Series[float], years: int) -> RollingHorizon:
    index = pd.DatetimeIndex(equity.index)
    values = equity.to_numpy()
    last = index[-1]
    starts: list[pd.Timestamp] = []
    cagrs: list[float] = []
    for start in index[~index.to_period("M").duplicated()]:
        target = start + pd.DateOffset(years=years)
        if target > last:
            break
        start_pos = int(index.searchsorted(start))
        end_pos = int(index.searchsorted(target, side="right")) - 1
        # 보유 기간 안에 다음 행이 없는 시작은 잴 수 없음
        if end_pos <= start_pos:
            continue
        starts.append(start)
        cagrs.append(_cagr_pct(float(values[start_pos]), float(values[end_pos]), (index[end_pos] - start).days))

    if not cagrs:
        return RollingHorizon(
            years=years,
            points=[],
            count=0,
            min_cagr=None,
            min_start_date=None,
            p10_cagr=None,
            median_cagr=None,
            negative_count=0,
        )

    values = pd.Series(cagrs)
    return RollingHorizon(
        years=years,
        points=[RollingPoint(start_date=_iso(s), cagr=_pct(c)) for s, c in zip(starts, cagrs, strict=True)],
        count=len(cagrs),
        min_cagr=_pct(float(values.min())),
        min_start_date=_iso(starts[int(values.to_numpy().argmin())]),
        p10_cagr=_pct(float(values.quantile(0.1))),
        median_cagr=_pct(float(values.median())),
        negative_count=int((values < 0).sum()),
    )


def _concentration(equity_df: pd.DataFrame) -> ConcentrationDict:
    # 히트맵의 연간 칸과 같은 값으로 재서 화면의 숫자로 손 계산이 맞음
    yearly = calculate_yearly_returns(equity_df)
    returns = pd.Series({int(str(entry["year"])): float(str(entry["return_pct"])) for entry in yearly}).sort_index()
    # 같은 수익률이면 이른 해 먼저 → 실행마다 저장 결과가 달라지지 않음
    ranked = returns.sort_values(ascending=False, kind="stable")
    total = float(returns.sum())
    count = len(returns)
    top3_sum = float(ranked.iloc[:3].sum())
    return ConcentrationDict(
        year_count=count,
        positive_years=int((returns > 0).sum()),
        negative_years=int((returns < 0).sum()),
        median_pct=_pct(float(returns.median())),
        mean_pct=_pct(total / count),
        top_years=[int(year) for year in ranked.index[:3]],
        top3_share_pct=_pct(top3_sum / total * 100) if total > 0 else None,
        mean_without_top3_pct=_pct((total - top3_sum) / count),
        mean_without_top5_pct=_pct((total - float(ranked.iloc[:5].sum())) / count),
    )


def calculate_period_performance(equity_df: pd.DataFrame, *, signal_df: pd.DataFrame | None) -> PeriodPerformanceDict:
    """자본 곡선의 구간별 성과를 저장 형태로 계산한다.

    Args:
        equity_df: 날짜 · equity 열이 있는 자본 곡선 (2행 이상)
        signal_df: 날짜 · 종가 열이 있는 신호 시세. 있으면 국면마다 같은 구간의 신호 시세 등락을 붙인다

    Raises:
        ValueError: equity_df 가 2행 미만일 때
    """
    _require_min_rows(equity_df)
    equity = _date_indexed(equity_df, COL_EQUITY)
    signal = None if signal_df is None else _date_indexed(signal_df, COL_CLOSE)
    return PeriodPerformanceDict(
        splits=[_split_row(equity, *period) for period in _requested_splits(equity)],
        regimes=[_regime_row(equity, signal, *regime) for regime in _MARKET_REGIMES],
        rolling=[_rolling_horizon(equity, years) for years in _ROLLING_YEARS],
        concentration=_concentration(equity_df),
    )


def calculate_yearly_asset_contributions(
    equity_df: pd.DataFrame, asset_ids: Sequence[str]
) -> list[YearlyAssetContribution]:
    """해마다 수익률을 자산별 기여(%p)로 나눈다.

    기여는 `{자산}_contribution` 열의 그해 변화를 직전 연말 계좌로 나눈 값이다. 첫 해의 기준은 첫 행이다.

    Args:
        equity_df: 날짜 · equity · `{자산}_contribution` 열이 있는 자본 곡선 (2행 이상)
        asset_ids: 나눌 자산 키

    Raises:
        ValueError: equity_df 가 2행 미만이거나 기여 열이 없을 때
    """
    _require_min_rows(equity_df)
    columns = {asset_id: f"{asset_id}_contribution" for asset_id in asset_ids}
    missing = [col for col in columns.values() if col not in equity_df.columns]
    if missing:
        raise ValueError(f"자산 기여 열이 없습니다: {missing}")

    table = equity_df[[COL_EQUITY, *columns.values()]].astype(float)
    table = table.set_axis(pd.DatetimeIndex(pd.to_datetime(equity_df[COL_DATE]))).sort_index()

    # 해 나눔은 calculate_yearly_returns 와 같음 — 첫 행뿐인 해는 내지 않고, 첫 해의 기준은 첫 행
    year_ends = table.iloc[1:].resample("YE").last().dropna()
    previous = year_ends.shift(1)
    previous.iloc[0] = table.iloc[0]

    bases = previous[COL_EQUITY].to_numpy()
    ends = year_ends[COL_EQUITY].to_numpy()
    changes = {asset_id: year_ends[col].to_numpy() - previous[col].to_numpy() for asset_id, col in columns.items()}

    rows: list[YearlyAssetContribution] = []
    for i, year_end in enumerate(pd.DatetimeIndex(year_ends.index)):
        base = float(bases[i])
        assets = {asset_id: float(change[i]) / base * 100 for asset_id, change in changes.items()}
        return_pct = (float(ends[i]) / base - 1) * 100
        rows.append(
            YearlyAssetContribution(
                year=year_end.year,
                return_pct=_pct(return_pct),
                assets={asset_id: _pct(value) for asset_id, value in assets.items()},
                other_pct=_pct(return_pct - sum(assets.values())),
            )
        )
    return rows
