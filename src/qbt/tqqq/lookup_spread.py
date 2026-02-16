"""
룩업테이블 스프레드 모델

TQQQ 실제 수익률에서 스프레드를 역산한 뒤, 금리 구간별로 집계하여
모델 가정 없이 스프레드를 결정하는 방식을 제공한다.

핵심 수식 (역산):
    시뮬레이션 수식:
        leveraged_return = underlying_return * leverage - daily_cost
        daily_cost = ((ffr + spread) * (leverage - 1) + expense) / 252

    역산:
        daily_cost = underlying_return * leverage - leveraged_return
        annual_cost = daily_cost * 252
        spread = (annual_cost - expense) / (leverage - 1) - ffr
"""

import math
from datetime import date

import numpy as np
import pandas as pd

from qbt.common_constants import COL_CLOSE, COL_DATE, TRADING_DAYS_PER_YEAR
from qbt.tqqq.constants import COL_FFR_DATE, COL_FFR_VALUE
from qbt.tqqq.data_loader import create_expense_dict, create_ffr_dict, lookup_expense, lookup_ffr


def calculate_realized_spread(
    qqq_df: pd.DataFrame,
    tqqq_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    leverage: float,
) -> pd.DataFrame:
    """
    QQQ/TQQQ 실제 수익률에서 실현 스프레드를 역산한다.

    시뮬레이션 수식을 역으로 풀어 각 거래일의 실제 스프레드를 도출한다.

    Args:
        qqq_df: QQQ DataFrame (Date, Close 컬럼 필수)
        tqqq_df: TQQQ DataFrame (Date, Close 컬럼 필수)
        ffr_df: FFR DataFrame (DATE: yyyy-mm, VALUE: 0~1 비율)
        expense_df: Expense Ratio DataFrame (DATE: yyyy-mm, VALUE: 0~1 비율)
        leverage: 레버리지 배율 (예: 3.0)

    Returns:
        DataFrame with columns: date, month, ffr_pct, realized_spread
        첫 번째 날(pct_change NaN)은 제외된다.
    """
    if leverage <= 1.0:
        raise ValueError(f"leverage는 1보다 커야 합니다: {leverage}")

    # 1. 일일 수익률 계산
    qqq = qqq_df[[COL_DATE, COL_CLOSE]].copy()
    tqqq = tqqq_df[[COL_DATE, COL_CLOSE]].copy()

    qqq["qqq_return"] = qqq[COL_CLOSE].pct_change()
    tqqq["tqqq_return"] = tqqq[COL_CLOSE].pct_change()

    # 2. 날짜 기준 병합
    merged = pd.merge(
        qqq[[COL_DATE, "qqq_return"]],
        tqqq[[COL_DATE, "tqqq_return"]],
        on=COL_DATE,
        how="inner",
    )

    # 3. 첫 날(NaN) 제거
    merged = merged.dropna(subset=["qqq_return", "tqqq_return"]).reset_index(drop=True)

    # 4. FFR/Expense 딕셔너리 생성
    ffr_dict = create_ffr_dict(ffr_df)
    expense_dict = create_expense_dict(expense_df)

    # 5. 각 날짜별 실현 스프레드 역산
    results: list[dict[str, object]] = []

    for _, row in merged.iterrows():
        d: date = row[COL_DATE]
        qqq_ret: float = row["qqq_return"]
        tqqq_ret: float = row["tqqq_return"]

        # FFR 및 Expense 조회
        ffr = lookup_ffr(d, ffr_dict)
        expense = lookup_expense(d, expense_dict)

        # 역산: daily_cost = qqq_return * leverage - tqqq_return
        daily_cost = qqq_ret * leverage - tqqq_ret

        # 역산: annual_cost = daily_cost * 252
        annual_cost = daily_cost * TRADING_DAYS_PER_YEAR

        # 역산: spread = (annual_cost - expense) / (leverage - 1) - ffr
        spread = (annual_cost - expense) / (leverage - 1) - ffr

        month_key = f"{d.year:04d}-{d.month:02d}"
        ffr_pct = ffr * 100.0

        results.append(
            {
                "date": d,
                "month": month_key,
                "ffr_pct": ffr_pct,
                "realized_spread": spread,
            }
        )

    return pd.DataFrame(results)


def build_lookup_table(
    realized_df: pd.DataFrame,
    bin_width_pct: float,
    stat_func: str,
) -> dict[float, float]:
    """
    금리 구간별 스프레드 룩업테이블을 생성한다.

    Args:
        realized_df: 실현 스프레드 DataFrame (ffr_pct, realized_spread 컬럼 필수)
        bin_width_pct: 금리 구간 폭 (%, 예: 1.0 = 1%씩 구간 분할)
        stat_func: 통계량 ("mean" 또는 "median")

    Returns:
        dict[float, float]: 구간 중앙값 → 스프레드 매핑
        예: {0.5: 0.003, 1.5: 0.005} (1% 구간 폭 기준)

    Raises:
        ValueError: 지원하지 않는 stat_func가 지정된 경우
    """
    if stat_func not in ("mean", "median"):
        raise ValueError(f"stat_func는 'mean' 또는 'median'만 지원합니다: {stat_func}")

    if bin_width_pct <= 0:
        raise ValueError(f"bin_width_pct는 양수여야 합니다: {bin_width_pct}")

    # 1. 금리 구간 할당
    # floor(ffr_pct / bin_width) * bin_width → 구간 시작점
    # 구간 중앙 = 구간 시작 + bin_width / 2
    ffr_pct = realized_df["ffr_pct"].to_numpy(dtype=np.float64)
    bin_starts = np.floor(ffr_pct / bin_width_pct) * bin_width_pct
    bin_centers = bin_starts + bin_width_pct / 2.0

    # 2. DataFrame에 구간 중앙 컬럼 추가
    df = realized_df.copy()
    df["bin_center"] = bin_centers

    # 3. 구간별 통계량 계산
    if stat_func == "mean":
        grouped = df.groupby("bin_center")["realized_spread"].mean()
    else:
        grouped = df.groupby("bin_center")["realized_spread"].median()

    return dict(grouped)


def lookup_spread_from_table(
    ffr_pct: float,
    lookup_table: dict[float, float],
    bin_width_pct: float,
) -> float:
    """
    룩업테이블에서 특정 금리에 해당하는 스프레드를 조회한다.

    해당 금리 구간이 테이블에 없으면 가장 가까운 구간의 값을 반환한다.

    Args:
        ffr_pct: 금리 수준 (%, 예: 4.5 = 4.5%)
        lookup_table: 구간 중앙값 → 스프레드 매핑
        bin_width_pct: 구간 폭 (%)

    Returns:
        해당 구간의 스프레드 값

    Raises:
        ValueError: 빈 테이블이 전달된 경우
    """
    if not lookup_table:
        raise ValueError("룩업테이블이 비어있습니다")

    # 해당 금리의 구간 중앙 계산
    bin_start = math.floor(ffr_pct / bin_width_pct) * bin_width_pct
    bin_center = bin_start + bin_width_pct / 2.0

    # 정확한 구간이 있으면 바로 반환
    if bin_center in lookup_table:
        return lookup_table[bin_center]

    # 없으면 가장 가까운 구간 찾기
    table_keys = np.array(list(lookup_table.keys()))
    distances = np.abs(table_keys - bin_center)
    nearest_key = table_keys[np.argmin(distances)]

    return lookup_table[float(nearest_key)]


def build_monthly_spread_map_from_lookup(
    ffr_df: pd.DataFrame,
    lookup_table: dict[float, float],
    bin_width_pct: float,
) -> dict[str, float]:
    """
    룩업테이블을 사용하여 월별 스프레드 맵을 생성한다.

    기존 build_monthly_spread_map()과 동일한 dict[str, float] 형태를 반환하여
    simulate()의 funding_spread 파라미터에 그대로 전달 가능하다.

    Args:
        ffr_df: FFR DataFrame (DATE: yyyy-mm, VALUE: 0~1 비율)
        lookup_table: 구간 중앙값 → 스프레드 매핑
        bin_width_pct: 구간 폭 (%)

    Returns:
        dict[str, float]: {"YYYY-MM": spread} 형태의 월별 스프레드 맵
    """
    spread_map: dict[str, float] = {}

    for _, row in ffr_df.iterrows():
        month_key: str = row[COL_FFR_DATE]
        ffr_ratio: float = row[COL_FFR_VALUE]
        ffr_pct = ffr_ratio * 100.0

        spread = lookup_spread_from_table(ffr_pct, lookup_table, bin_width_pct)
        spread_map[month_key] = spread

    return spread_map


def evaluate_lookup_combination(
    realized_df: pd.DataFrame,
    bin_width_pct: float,
    stat_func: str,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    underlying_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    leverage: float,
) -> dict[str, object]:
    """
    단일 (bin_width, stat_func) 조합의 인샘플 RMSE를 평가한다.

    Args:
        realized_df: 실현 스프레드 DataFrame
        bin_width_pct: 구간 폭 (%)
        stat_func: 통계량 ("mean" 또는 "median")
        ffr_df: FFR DataFrame
        expense_df: Expense Ratio DataFrame
        underlying_df: QQQ DataFrame (시뮬레이션 입력)
        actual_df: TQQQ DataFrame (비교 대상)
        leverage: 레버리지 배율

    Returns:
        dict with keys: bin_width_pct, stat_func, rmse_pct, n_bins
    """
    from qbt.tqqq.simulation import calculate_validation_metrics, extract_overlap_period, simulate

    # 1. 룩업테이블 생성
    table = build_lookup_table(realized_df, bin_width_pct, stat_func)

    # 2. 월별 스프레드 맵 생성
    spread_map = build_monthly_spread_map_from_lookup(ffr_df, table, bin_width_pct)

    # 3. 겹치는 기간 추출
    underlying_overlap, actual_overlap = extract_overlap_period(underlying_df, actual_df)

    # 4. 시뮬레이션 실행
    initial_price = float(actual_overlap.iloc[0][COL_CLOSE])
    sim_df = simulate(
        underlying_df=underlying_overlap,
        leverage=leverage,
        expense_df=expense_df,
        initial_price=initial_price,
        ffr_df=ffr_df,
        funding_spread=spread_map,
    )

    # 5. 검증 지표 계산
    metrics = calculate_validation_metrics(
        simulated_df=sim_df,
        actual_df=actual_overlap,
        output_path=None,
    )

    return {
        "bin_width_pct": bin_width_pct,
        "stat_func": stat_func,
        "rmse_pct": metrics["cumul_multiple_log_diff_rmse_pct"],
        "n_bins": len(table),
    }
