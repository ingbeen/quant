"""대용 시계열 유틸리티

실물 ETF 가 상장하기 전 기간을 비슷하게 움직이는 다른 시세(대용)로 채운다.
이음매는 실물 첫 거래일이고, 대용은 그날 종가 비율로 스케일해 잇는다.
"""

import math
from collections.abc import Sequence

import pandas as pd

from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    EPSILON,
    PRICE_COLUMNS,
    REQUIRED_COLUMNS,
)


def _require_strictly_increasing_dates(df: pd.DataFrame, name: str) -> None:
    if df.empty:
        raise ValueError(f"{name} 시세가 비어 있습니다")
    dates = df[COL_DATE]
    if not (dates.is_monotonic_increasing and dates.is_unique):
        raise ValueError(f"{name} 시세의 날짜가 중복 없는 오름차순이 아닙니다 — load_stock_data 로 읽은 시세를 넘기세요")


def compute_seam_scale(proxy_df: pd.DataFrame, actual_df: pd.DataFrame) -> float:
    """실물 첫 거래일(이음매) 종가 ÷ 그날 대용 종가.

    Raises:
        ValueError: 날짜가 중복 없는 오름차순이 아니거나, 이음매 날짜가 대용에 없을 때
    """
    _require_strictly_increasing_dates(proxy_df, "대용")
    _require_strictly_increasing_dates(actual_df, "실물")
    seam_date = actual_df[COL_DATE].iloc[0]
    seam_rows = proxy_df[proxy_df[COL_DATE] == seam_date]
    if seam_rows.empty:
        raise ValueError(f"이음매(실물 첫 거래일 {seam_date})가 대용 시세에 없습니다 — 대용 시세의 기간을 확인하세요")
    return float(actual_df[COL_CLOSE].iloc[0]) / float(seam_rows[COL_CLOSE].iloc[0])


def rescale_to_actual(proxy_df: pd.DataFrame, actual_df: pd.DataFrame) -> pd.DataFrame:
    """대용 전 구간의 가격을 이음매 종가에 맞춘다. 수익률과 거래량은 바뀌지 않는다.

    Raises:
        ValueError: compute_seam_scale 과 같다
    """
    scale = compute_seam_scale(proxy_df, actual_df)
    result = proxy_df[REQUIRED_COLUMNS].copy()
    result[PRICE_COLUMNS] = result[PRICE_COLUMNS] * scale
    return result


def splice_proxy(proxy_df: pd.DataFrame, actual_df: pd.DataFrame) -> pd.DataFrame:
    """이음매 앞은 스케일한 대용(거래량 0), 이음매부터는 실물 행 그대로인 시계열.

    이음매 날의 종가 수익률은 대용의 수익률이고, 그 다음 날부터 실물 수익률이다.

    Raises:
        ValueError: compute_seam_scale 과 같은 경우, 이음매 앞 대용 행이 없을 때
    """
    rescaled = rescale_to_actual(proxy_df, actual_df)
    seam_date = actual_df[COL_DATE].iloc[0]
    before_seam = rescaled[rescaled[COL_DATE] < seam_date].copy()
    if before_seam.empty:
        raise ValueError(f"이음매(실물 첫 거래일 {seam_date}) 앞의 대용 시세가 없어 채울 구간이 없습니다")
    # 대용의 거래량은 실물 거래량이 아니다
    before_seam[COL_VOLUME] = 0
    return pd.concat([before_seam, actual_df[REQUIRED_COLUMNS]], ignore_index=True)


def build_daily_rebalanced_composite(components: Sequence[tuple[pd.DataFrame, float]]) -> pd.DataFrame:
    """매일 비율을 다시 맞추는 바스켓. 첫날 종가 1.0, 거래량 0.

    기간은 가장 늦은 시작일부터 가장 이른 끝날까지다. 고가 · 저가는 구성 종목 값의 가중합이라
    실제 바스켓의 장중 값이 아닌 근사다.

    Args:
        components: (시세, 비중) 목록. 비중은 0 보다 크고 합이 1

    Raises:
        ValueError: 구성 2개 미만, 비중이 0 이하 · 합이 1 이 아님, 날짜가 중복 없는 오름차순이 아님,
            겹치는 기간이 없음, 겹치는 기간 안에서 구성 종목의 날짜가 다름
    """
    if len(components) < 2:
        raise ValueError(f"합성에는 구성 종목이 2개 이상 필요합니다: {len(components)}개")
    weights = [weight for _, weight in components]
    if any(weight <= 0 for weight in weights):
        raise ValueError(f"구성 비중은 0 보다 커야 합니다: {weights}")
    if not math.isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=EPSILON):
        raise ValueError(f"구성 비중의 합이 1 이 아닙니다: {sum(weights)}")
    for number, (df, _) in enumerate(components, start=1):
        _require_strictly_increasing_dates(df, f"구성 종목 {number}")

    start = max(df[COL_DATE].iloc[0] for df, _ in components)
    end = min(df[COL_DATE].iloc[-1] for df, _ in components)
    if start > end:
        raise ValueError(f"구성 종목의 겹치는 기간이 없습니다 (가장 늦은 시작 {start}, 가장 이른 끝 {end})")
    windows = [df[(df[COL_DATE] >= start) & (df[COL_DATE] <= end)].reset_index(drop=True) for df, _ in components]

    # 보간하지 않는다 — 한 종목에만 있는 날짜를 버리거나 메우면 이틀 수익률이 하루로 합쳐진다
    reference_dates = windows[0][COL_DATE].tolist()
    for number, window in enumerate(windows[1:], start=2):
        dates = window[COL_DATE].tolist()
        if dates != reference_dates:
            only_first = sorted(set(reference_dates) - set(dates))
            only_this = sorted(set(dates) - set(reference_dates))
            raise ValueError(
                f"겹치는 기간 안에서 구성 종목의 날짜가 다릅니다 — 구성 종목 1 에만: {only_first[:5]}, "
                f"구성 종목 {number} 에만: {only_this[:5]}. 원본 시세를 확인하세요"
            )

    # 그날 각 가격 ÷ 구성 종목 전날 종가의 가중합 (첫날은 그날 종가로 나눈다)
    weighted = {col: pd.Series(0.0, index=range(len(reference_dates))) for col in PRICE_COLUMNS}
    for window, weight in zip(windows, weights, strict=True):
        prev_close = window[COL_CLOSE].shift(1).fillna(window[COL_CLOSE].iloc[0])
        for col in PRICE_COLUMNS:
            weighted[col] = weighted[col] + weight * window[col] / prev_close

    close = weighted[COL_CLOSE].cumprod()
    prev_composite_close = close.shift(1).fillna(1.0)
    result = pd.DataFrame({COL_DATE: reference_dates})
    for col in (COL_OPEN, COL_HIGH, COL_LOW):
        result[col] = prev_composite_close * weighted[col]
    result[COL_CLOSE] = close
    result[COL_VOLUME] = 0
    return result[REQUIRED_COLUMNS]
