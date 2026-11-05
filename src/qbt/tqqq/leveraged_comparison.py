"""레버리지 합성 검증

검증 ② 합성 ↔ 실물 레버리지 ETF 추적, ③ 레버리지 ETF 상장 전 펀드 대조(연 수익 · 해마다 비용),
④ 대조할 실물이 없는 구간에서 가정만 바꾼 판을 잰다. 정의와 근거는 `docs/research/합성_시세_연장.md` 5장.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Final

import numpy as np
import pandas as pd

from qbt.common_constants import (
    ANNUAL_DAYS,
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    PRICE_COLUMNS,
)
from qbt.tqqq.data_loader import lookup_ffr
from qbt.tqqq.synthetic import build_cost_inputs, month_of, simulate_leveraged
from qbt.utils.data_loader import extract_overlap_period
from qbt.utils.proxy_comparison import PairSummary, align_closes, summarize_pair

# 해마다 비용에 넣는 해의 최소 거래일 — 공통 날짜가 중간에 비는 해를 뺌 (첫 해 · 마지막 해는 늘 뺀다)
MIN_YEAR_TRADING_DAYS: Final = 200

# simulate 가 가산금리 0 을 거부 → 사실상 0 으로 둠
_ZERO_SPREAD: Final = 1e-12

VARIANT_ADOPTED: Final = "채택"
VARIANT_UNCAPPED: Final = "상한 없음"
VARIANT_ZERO_SPREAD: Final = "가산금리 0"
VARIANT_DIVIDEND: Final = "배당 보정"

_BASE: Final = "base"
_PRODUCT: Final = "product"
_MODEL: Final = "model"


@dataclass(frozen=True)
class TrackingSummary:
    """실물 첫날 ~ 끝날의 추적 오차.

    누적 차는 실물 첫날을 1 로 맞춘 누적 배수의 로그 비(%, 양수면 시뮬레이션이 높다) — rmse · mean · max 는 그 절댓값,
    last 는 마지막 날의 부호 있는 값. 하루 수익률 절대차와 한 날치 예측 오차(전날 실물 종가 대비, RMSE)는 %p 다.
    """

    start: date
    end: date
    trading_days: int
    rmse: float
    mean: float
    max: float
    max_date: date
    last: float
    daily_abs_diff_mean: float
    one_day_open: float
    one_day_close: float
    one_day_high: float
    one_day_low: float


@dataclass(frozen=True)
class YearCost:
    """한 해의 비용 (연 %). 실제 = Σ ln(1 + 배율 × 기초 r) − Σ ln(1 + 상품 r), 모형은 상품 대신 합성.
    평균 금리는 그해 거래일의 금리 평균 (%)."""

    year: int
    trading_days: int
    mean_ffr: float
    actual_cost: float
    model_cost: float


@dataclass(frozen=True)
class AssumptionResult:
    """가정 판 하나의 Buy & Hold — 구간 첫날 종가에 사서 끝날 종가까지. 연 수익(달력일 기준) · 최악 낙폭은 %."""

    variant: str
    product: str
    leverage: float
    start: date
    end: date
    cagr: float
    mdd: float


def _ratio_returns(closes: pd.Series) -> pd.Series:
    return closes / closes.shift(1) - 1.0


def summarize_tracking(simulated_df: pd.DataFrame, actual_df: pd.DataFrame) -> TrackingSummary:
    """
    시뮬레이션이 실물을 얼마나 따르는지 잰다 (검증 ②). 두 시세가 모두 있는 날만 쓴다 — 실물 첫날 앞의 시뮬레이션은 빠진다.

    한 날치 예측은 「전날 실물 종가 × 시뮬의 그날 값 ÷ 시뮬의 전날 종가」다 — 시뮬레이션이 낸 시가 · 고가 · 저가 · 종가를
    그대로 쓰므로 종가 예측에는 그날 비용이 들어 있다.

    Raises:
        ValueError: 겹치는 날이 2일 미만일 때
    """
    simulated, actual = extract_overlap_period(simulated_df, actual_df)
    if len(actual) < 2:
        raise ValueError(f"시뮬레이션과 실물의 겹치는 날이 2일 이상 필요합니다: {len(actual)}일")

    sim_close = simulated[COL_CLOSE]
    actual_close = actual[COL_CLOSE]
    signed = 100.0 * np.log((sim_close / sim_close.iloc[0]) / (actual_close / actual_close.iloc[0]))
    abs_diff = signed.abs()
    max_position = int(np.argmax(abs_diff.to_numpy()))
    daily_abs_diff = ((_ratio_returns(actual_close) - _ratio_returns(sim_close)) * 100.0).abs().iloc[1:]

    prev_actual_close = actual_close.shift(1)
    prev_sim_close = sim_close.shift(1)

    def one_day_rmse(column: str) -> float:
        predicted = prev_actual_close * simulated[column] / prev_sim_close
        error = ((predicted - actual[column]) / prev_actual_close * 100.0).iloc[1:]
        return float(np.sqrt((error**2).mean()))

    return TrackingSummary(
        start=actual[COL_DATE].iloc[0],
        end=actual[COL_DATE].iloc[-1],
        trading_days=len(actual),
        rmse=float(np.sqrt((abs_diff**2).mean())),
        mean=float(abs_diff.mean()),
        max=float(abs_diff.iloc[max_position]),
        max_date=actual[COL_DATE].iloc[max_position],
        last=float(signed.iloc[-1]),
        daily_abs_diff_mean=float(daily_abs_diff.mean()),
        one_day_open=one_day_rmse(COL_OPEN),
        one_day_close=one_day_rmse(COL_CLOSE),
        one_day_high=one_day_rmse(COL_HIGH),
        one_day_low=one_day_rmse(COL_LOW),
    )


def compare_around(product_df: pd.DataFrame, fund_df: pd.DataFrame, split: date) -> tuple[PairSummary, PairSummary]:
    """
    견줄 시세와 펀드를 split 앞(그날 제외) · 뒤(그날 포함) 두 구간에서 비교한다 (검증 ③ 연 수익).
    두 시세가 모두 있는 날만 쓰고, 결과의 「대용」 쪽이 견줄 시세 · 「실물」 쪽이 펀드다.

    Raises:
        ValueError: 어느 구간이든 겹치는 날이 2일 미만일 때 (align_closes)
    """
    before = align_closes(product_df[product_df[COL_DATE] < split], fund_df[fund_df[COL_DATE] < split])
    after = align_closes(product_df[product_df[COL_DATE] >= split], fund_df[fund_df[COL_DATE] >= split])
    return summarize_pair(before), summarize_pair(after)


def yearly_costs(
    base_df: pd.DataFrame,
    product_df: pd.DataFrame,
    model_df: pd.DataFrame,
    leverage: float,
    ffr_dict: dict[str, float],
    *,
    min_days: int = MIN_YEAR_TRADING_DAYS,
) -> list[YearCost]:
    """
    해마다 실제 상품과 합성이 기초의 배율 수익에서 덜 번 만큼(비용)을 잰다 (검증 ③ 해마다 비용).
    세 시세가 모두 있는 날만 쓰고, 하루 수익률을 그 날짜의 해로 묶는다. 비용은 그해의 합이라 한 해를 다 덮는 해만 낸다 —
    공통 날짜의 첫 해 · 마지막 해(부분 연도)와 거래일이 min_days 미만인 해는 뺀다.

    Raises:
        ValueError: 배율 × 기초 하루 수익률이 −100% 이하인 날이 있을 때 (로그를 잴 수 없다),
            금리가 그 날짜를 덮지 못할 때 (lookup_ffr)
    """
    merged = (
        base_df[[COL_DATE, COL_CLOSE]]
        .rename(columns={COL_CLOSE: _BASE})
        .merge(product_df[[COL_DATE, COL_CLOSE]].rename(columns={COL_CLOSE: _PRODUCT}), on=COL_DATE)
        .merge(model_df[[COL_DATE, COL_CLOSE]].rename(columns={COL_CLOSE: _MODEL}), on=COL_DATE)
        .sort_values(COL_DATE)
        .reset_index(drop=True)
    )
    returns = merged[[_BASE, _PRODUCT, _MODEL]].apply(_ratio_returns).iloc[1:]
    dates = merged[COL_DATE].iloc[1:]

    levered = 1.0 + leverage * returns[_BASE]
    if bool((levered <= 0).any()):
        raise ValueError(f"배율 × 기초 하루 수익률이 −100% 이하인 날이 있어 비용을 잴 수 없습니다: {dates[levered <= 0].tolist()[:5]}")
    log_levered = np.log(levered)

    daily = pd.DataFrame(
        {
            "year": [d.year for d in dates],
            "actual": log_levered - np.log1p(returns[_PRODUCT]),
            "model": log_levered - np.log1p(returns[_MODEL]),
            "ffr": [lookup_ffr(d, ffr_dict) for d in dates],
        }
    )
    grouped = daily.groupby("year", as_index=False).agg(
        days=("actual", "size"), actual=("actual", "sum"), model=("model", "sum"), ffr=("ffr", "mean")
    )
    partial_years = {int(grouped["year"].min()), int(grouped["year"].max())}
    return [
        YearCost(
            year=int(row["year"]),
            trading_days=int(row["days"]),
            mean_ffr=float(row["ffr"]) * 100.0,
            actual_cost=float(row["actual"]) * 100.0,
            model_cost=float(row["model"]) * 100.0,
        )
        for row in grouped.to_dict("records")
        if int(row["year"]) not in partial_years and int(row["days"]) >= min_days
    ]


def annual_gap_rate(base_cagr: float, target_cagr: float) -> float:
    """
    연 수익 base_cagr 인 시세를 target_cagr 로 맞추려면 해마다 더 붙여야 하는 비율 (연 수익은 %, 반환은 0~1 비율).

    (1 + target) ÷ (1 + base) − 1 이다 — 두 연 수익의 단순 차를 복리로 붙이면 target 을 넘는다.
    """
    return (1.0 + target_cagr / 100.0) / (1.0 + base_cagr / 100.0) - 1.0


def _with_annual_drift(df: pd.DataFrame, annual_rate: float) -> pd.DataFrame:
    """가격 열에 연 annual_rate 를 달력일 비례로 붙인 시세 — 첫날에서 d 일 뒤는 (1 + annual_rate)^(d ÷ ANNUAL_DAYS) 배.

    연 수익을 달력일로 재므로(_cagr) 같은 기준으로 붙여야 연 수익이 정확히 annual_rate 만큼 오른다.
    """
    elapsed_days = np.array([(day - df[COL_DATE].iloc[0]).days for day in df[COL_DATE]], dtype=float)
    factors = (1.0 + annual_rate) ** (elapsed_days / ANNUAL_DAYS)
    result = df.copy()
    result[PRICE_COLUMNS] = result[PRICE_COLUMNS].mul(factors, axis=0)
    return result


def _cagr(closes: pd.Series, start: date, end: date) -> float:
    days = (end - start).days
    return float(((closes.iloc[-1] / closes.iloc[0]) ** (ANNUAL_DAYS / days) - 1.0) * 100.0)


def _mdd(closes: pd.Series) -> float:
    return float((closes / closes.cummax() - 1.0).min() * 100.0)


def assumption_variants(
    underlying_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    products: Sequence[tuple[str, float]],
    *,
    end: date,
    dividend_gap_rate: float | None,
) -> list[AssumptionResult]:
    """
    기초 첫날 ~ end 에서 가정만 바꾼 판의 Buy & Hold 를 상품마다 잰다 (검증 ④). 행은 판 순서 · 상품 순서다.

    판: 채택(합성 파일과 같은 비용 입력), 상한 없음, 가산금리 0, 배당 보정(채택 비용에 연 수익을
    dividend_gap_rate 만큼 복리로 높인 기초 — dividend_gap_rate 가 None 이면 이 판은 없다).

    Args:
        underlying_df: 1배 기초 시세 (합성 파일의 기초)
        ffr_df: 월별 금리
        expense_df: 월별 운용비율
        products: (상품 이름, 배율)
        end: 구간 끝날 (그날 포함)
        dividend_gap_rate: 배당 보정 폭 (연 비율, annual_gap_rate — 0.0052 = 연 0.52%).
            None 은 기초가 배당을 담아 보정할 것이 없을 때다

    Raises:
        ValueError: 구간의 날이 2일 미만일 때, build_cost_inputs · simulate 와 같다
    """
    window = underlying_df[underlying_df[COL_DATE] <= end].reset_index(drop=True)
    if len(window) < 2:
        raise ValueError(f"가정 판의 구간에 날이 2일 이상 필요합니다: {len(window)}일 (끝날 {end})")
    start = window[COL_DATE].iloc[0]
    last = window[COL_DATE].iloc[-1]

    first_month = month_of(start)
    adopted = build_cost_inputs(ffr_df, expense_df, first_month)
    variants = [
        (VARIANT_ADOPTED, window, adopted),
        (VARIANT_UNCAPPED, window, build_cost_inputs(ffr_df, expense_df, first_month, spread_cap=None)),
        (VARIANT_ZERO_SPREAD, window, replace(adopted, spread={month: _ZERO_SPREAD for month in adopted.spread})),
    ]
    if dividend_gap_rate is not None:
        variants.append((VARIANT_DIVIDEND, _with_annual_drift(window, dividend_gap_rate), adopted))

    results: list[AssumptionResult] = []
    for variant, underlying, costs in variants:
        for product, leverage in products:
            closes = simulate_leveraged(underlying, leverage, costs)[COL_CLOSE]
            results.append(
                AssumptionResult(
                    variant=variant,
                    product=product,
                    leverage=leverage,
                    start=start,
                    end=last,
                    cagr=_cagr(closes, start, last),
                    mdd=_mdd(closes),
                )
            )
    return results
