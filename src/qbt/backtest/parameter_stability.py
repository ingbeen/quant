"""파라미터 안정성 분석 모듈

overfitting_analysis_report.md 11.2절 "1단계: 파라미터 안정성 확인"에 대응한다.
grid_results.csv(432개 파라미터 조합)를 분석하여 파라미터 안정성을 진단한다.

대응 관계:
- build_calmar_histogram_data: 11.2절 "Calmar 분포 확인"
- build_heatmap_data: 11.2절 "buy/sell buffer 히트맵"
- build_adjacent_comparison: 11.2절 "인접 파라미터 비교"
- evaluate_stability_criteria: 11.2절 통과 기준 판정
"""

from pathlib import Path
from typing import Any

import pandas as pd

from qbt.backtest.constants import (
    COL_BUY_BUFFER_ZONE_PCT,
    COL_CAGR,
    COL_CALMAR,
    COL_FINAL_CAPITAL,
    COL_HOLD_DAYS,
    COL_MA_WINDOW,
    COL_MDD,
    COL_RECENT_MONTHS,
    COL_SELL_BUFFER_ZONE_PCT,
    COL_TOTAL_RETURN_PCT,
    COL_TOTAL_TRADES,
    COL_WIN_RATE,
    DISPLAY_BUY_BUFFER_ZONE,
    DISPLAY_CAGR,
    DISPLAY_CALMAR,
    DISPLAY_FINAL_CAPITAL,
    DISPLAY_HOLD_DAYS,
    DISPLAY_MA_WINDOW,
    DISPLAY_MDD,
    DISPLAY_RECENT_MONTHS,
    DISPLAY_SELL_BUFFER_ZONE,
    DISPLAY_TOTAL_RETURN,
    DISPLAY_TOTAL_TRADES,
    DISPLAY_WIN_RATE,
)

# DISPLAY -> COL 컬럼명 매핑 (CSV 로드 시 rename용)
_DISPLAY_TO_COL: dict[str, str] = {
    DISPLAY_MA_WINDOW: COL_MA_WINDOW,
    DISPLAY_BUY_BUFFER_ZONE: COL_BUY_BUFFER_ZONE_PCT,
    DISPLAY_SELL_BUFFER_ZONE: COL_SELL_BUFFER_ZONE_PCT,
    DISPLAY_HOLD_DAYS: COL_HOLD_DAYS,
    DISPLAY_RECENT_MONTHS: COL_RECENT_MONTHS,
    DISPLAY_TOTAL_RETURN: COL_TOTAL_RETURN_PCT,
    DISPLAY_CAGR: COL_CAGR,
    DISPLAY_MDD: COL_MDD,
    DISPLAY_CALMAR: COL_CALMAR,
    DISPLAY_TOTAL_TRADES: COL_TOTAL_TRADES,
    DISPLAY_WIN_RATE: COL_WIN_RATE,
    DISPLAY_FINAL_CAPITAL: COL_FINAL_CAPITAL,
}

# 필수 COL 컬럼 목록 (로드 후 검증용)
_REQUIRED_COLUMNS: list[str] = [
    COL_MA_WINDOW,
    COL_BUY_BUFFER_ZONE_PCT,
    COL_SELL_BUFFER_ZONE_PCT,
    COL_HOLD_DAYS,
    COL_RECENT_MONTHS,
    COL_CAGR,
    COL_MDD,
    COL_CALMAR,
]

# 인접 30% 이내 판정 임계값
_ADJACENT_THRESHOLD_RATIO = 0.7  # 최적 대비 70% 이상이면 통과

# Calmar > 0 과반수 기준
_CALMAR_POSITIVE_MAJORITY_RATIO = 0.5  # 50% 초과

# 히트맵 고원 판정 임계값 (셀 간 max-min 차이)
_PLATEAU_RANGE_THRESHOLD = 0.05


def load_grid_results(grid_results_path: Path) -> pd.DataFrame:
    """grid_results.csv 로드 후 내부 컬럼명(COL_*)으로 변환.

    Args:
        grid_results_path: grid_results.csv 파일 경로

    Returns:
        COL_* 컬럼명으로 변환된 DataFrame

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        ValueError: 필수 컬럼이 부족할 때
    """
    if not grid_results_path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {grid_results_path}")

    df = pd.read_csv(grid_results_path)

    # DISPLAY -> COL 컬럼명 변환 (존재하는 컬럼만)
    rename_map = {k: v for k, v in _DISPLAY_TO_COL.items() if k in df.columns}
    df = df.rename(columns=rename_map)

    # 필수 컬럼 검증
    missing = [col for col in _REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼이 부족합니다: {missing}")

    return df


def build_calmar_histogram_data(df: pd.DataFrame) -> pd.Series:
    """전체 Calmar 값 Series 반환.

    Args:
        df: load_grid_results()로 로드한 DataFrame

    Returns:
        Calmar 값 Series (전체 행 수와 동일)
    """
    return df[COL_CALMAR].copy()


def build_heatmap_data(df: pd.DataFrame, ma_window: int) -> pd.DataFrame:
    """MA별 buy_buffer x sell_buffer 히트맵 집계 데이터 생성.

    hold_days/recent_months를 평균 집계하여 핵심 파라미터(buy/sell buffer)의
    견고성을 측정한다.

    Args:
        df: load_grid_results()로 로드한 DataFrame
        ma_window: 필터링할 MA 기간 (100, 150, 200)

    Returns:
        buy_buffer x sell_buffer별 집계 DataFrame (9행)
        컬럼: buy_buffer_zone_pct, sell_buffer_zone_pct, calmar_mean, calmar_min,
              cagr_mean, mdd_mean
    """
    # 1. MA 필터링
    filtered = df[df[COL_MA_WINDOW] == ma_window].copy()

    # 2. buy_buffer x sell_buffer별 groupby 집계
    grouped = filtered.groupby([COL_BUY_BUFFER_ZONE_PCT, COL_SELL_BUFFER_ZONE_PCT])

    result = grouped.agg(
        calmar_mean=(COL_CALMAR, "mean"),
        calmar_min=(COL_CALMAR, "min"),
        cagr_mean=(COL_CAGR, "mean"),
        mdd_mean=(COL_MDD, "mean"),
    ).reset_index()

    return result


def build_adjacent_comparison(
    df: pd.DataFrame,
    optimal_ma: int,
    optimal_buy: float,
    optimal_sell: float,
) -> pd.DataFrame:
    """최적 파라미터 기준 인접 조합 비교 데이터 생성.

    buy/sell buffer 각각 한 단계 변경 + hold_days 축 변화를 포함한다.
    hold_days/recent_months는 평균 집계한다.

    Args:
        df: load_grid_results()로 로드한 DataFrame
        optimal_ma: 최적 MA 기간
        optimal_buy: 최적 매수 버퍼존 비율
        optimal_sell: 최적 매도 버퍼존 비율

    Returns:
        비교 테이블 DataFrame
        컬럼: axis, param_name, param_value, calmar_mean
    """
    rows: list[dict[str, object]] = []

    # 1. buy_buffer 인접 비교 (MA, sell 고정, hold/recent 평균)
    unique_buys = sorted(df[COL_BUY_BUFFER_ZONE_PCT].unique())
    for buy_val in unique_buys:
        subset = df[
            (df[COL_MA_WINDOW] == optimal_ma)
            & (df[COL_BUY_BUFFER_ZONE_PCT] == buy_val)
            & (df[COL_SELL_BUFFER_ZONE_PCT] == optimal_sell)
        ]
        if len(subset) > 0:
            rows.append(
                {
                    "axis": "buy_buffer",
                    "param_name": "buy_buffer_zone_pct",
                    "param_value": buy_val,
                    "calmar_mean": float(subset[COL_CALMAR].mean()),
                }
            )

    # 2. sell_buffer 인접 비교 (MA, buy 고정, hold/recent 평균)
    unique_sells = sorted(df[COL_SELL_BUFFER_ZONE_PCT].unique())
    for sell_val in unique_sells:
        subset = df[
            (df[COL_MA_WINDOW] == optimal_ma)
            & (df[COL_BUY_BUFFER_ZONE_PCT] == optimal_buy)
            & (df[COL_SELL_BUFFER_ZONE_PCT] == sell_val)
        ]
        if len(subset) > 0:
            rows.append(
                {
                    "axis": "sell_buffer",
                    "param_name": "sell_buffer_zone_pct",
                    "param_value": sell_val,
                    "calmar_mean": float(subset[COL_CALMAR].mean()),
                }
            )

    # 3. hold_days 축 비교 (MA, buy, sell 고정, recent 평균)
    unique_holds = sorted(df[COL_HOLD_DAYS].unique())
    for hold_val in unique_holds:
        subset = df[
            (df[COL_MA_WINDOW] == optimal_ma)
            & (df[COL_BUY_BUFFER_ZONE_PCT] == optimal_buy)
            & (df[COL_SELL_BUFFER_ZONE_PCT] == optimal_sell)
            & (df[COL_HOLD_DAYS] == hold_val)
        ]
        if len(subset) > 0:
            rows.append(
                {
                    "axis": "hold_days",
                    "param_name": "hold_days",
                    "param_value": hold_val,
                    "calmar_mean": float(subset[COL_CALMAR].mean()),
                }
            )

    return pd.DataFrame(rows)


def evaluate_stability_criteria(
    df: pd.DataFrame,
    optimal_ma: int,
    optimal_buy: float,
    optimal_sell: float,
) -> dict[str, Any]:
    """보고서 11.2절 통과 기준 평가 (5개 기준 + 3단계 판정).

    기준값을 단일 최적 Calmar 대신 최적 셀 평균 Calmar로 사용하여
    동일한 집계 기준(평균 대 평균)으로 비교한다.

    Args:
        df: load_grid_results()로 로드한 DataFrame
        optimal_ma: 최적 MA 기간
        optimal_buy: 최적 매수 버퍼존 비율
        optimal_sell: 최적 매도 버퍼존 비율

    Returns:
        판정 결과 dict:
        - calmar_positive_ratio: Calmar > 0 비율 (0~1)
        - calmar_positive_count: Calmar > 0 개수
        - calmar_positive_pass: 과반수 통과 여부
        - plateau_range: best_ma 내 9셀 max-min 차이
        - plateau_pass: 고원 형태 통과 여부
        - opt_cell_mean: 최적 셀 평균 Calmar
        - adjacent_threshold: 인접 판정 임계값
        - adjacent_min_mean: 인접 셀 중 최소 평균 Calmar
        - adjacent_pass: 인접 기준 통과 여부
        - ma_gap_pct: MA=100이 best_ma 대비 낮은 비율 (%)
        - ma_dependency_warn: MA 의존성 경고 여부
        - sell_dependency_warn: sell_buffer 의존성 경고 여부
        - overall_verdict: 종합 판정 ("pass" | "conditional" | "fail")
    """
    # 1. Calmar > 0 비율
    total_count = len(df)
    positive_count = int((df[COL_CALMAR] > 0).sum())
    positive_ratio = positive_count / total_count if total_count > 0 else 0.0
    calmar_positive_pass = positive_ratio > _CALMAR_POSITIVE_MAJORITY_RATIO

    # 2. 히트맵 고원 판정: best_ma 내 9셀의 max-min 차이
    best_ma_df = df[df[COL_MA_WINDOW] == optimal_ma]
    cell_means = best_ma_df.groupby([COL_BUY_BUFFER_ZONE_PCT, COL_SELL_BUFFER_ZONE_PCT])[COL_CALMAR].mean()
    plateau_range = float(cell_means.max() - cell_means.min()) if len(cell_means) > 0 else 0.0
    plateau_pass = plateau_range < _PLATEAU_RANGE_THRESHOLD

    # 3. 인접 파라미터 (평균 대 평균, 30% 이내)
    # 3-1. 최적 셀 평균 Calmar 계산
    opt_cell_mask = (
        (df[COL_MA_WINDOW] == optimal_ma)
        & (df[COL_BUY_BUFFER_ZONE_PCT] == optimal_buy)
        & (df[COL_SELL_BUFFER_ZONE_PCT] == optimal_sell)
    )
    opt_cell_data = df.loc[opt_cell_mask, COL_CALMAR]
    opt_cell_mean = float(opt_cell_data.mean()) if len(opt_cell_data) > 0 else 0.0

    # 3-2. 인접 셀 평균 계산 (buy 또는 sell을 한 단계 변경)
    adjacent_df = build_adjacent_comparison(df, optimal_ma, optimal_buy, optimal_sell)
    buffer_adjacent = adjacent_df[adjacent_df["axis"].isin(["buy_buffer", "sell_buffer"])]

    threshold = opt_cell_mean * _ADJACENT_THRESHOLD_RATIO
    if len(buffer_adjacent) > 0:
        adjacent_min_mean = float(buffer_adjacent["calmar_mean"].min())
        adjacent_pass = adjacent_min_mean >= threshold
    else:
        adjacent_min_mean = 0.0
        adjacent_pass = False

    # 4. MA 의존성: MA=100 평균 vs best_ma 평균
    ma100_data = df[df[COL_MA_WINDOW] == 100]
    best_ma_mean = float(best_ma_df[COL_CALMAR].mean()) if len(best_ma_df) > 0 else 0.0
    ma100_mean = float(ma100_data[COL_CALMAR].mean()) if len(ma100_data) > 0 else 0.0

    if best_ma_mean > 0:
        ma_gap_pct = (best_ma_mean - ma100_mean) / best_ma_mean * 100
    else:
        ma_gap_pct = 0.0
    ma_dependency_warn = ma_gap_pct > 10.0

    # 5. sell_buffer 의존성: sell_buffer=0.01 평균이 전체 최저인지
    unique_sells = sorted(df[COL_SELL_BUFFER_ZONE_PCT].unique())
    sell_means = {
        sell_val: float(df[df[COL_SELL_BUFFER_ZONE_PCT] == sell_val][COL_CALMAR].mean()) for sell_val in unique_sells
    }
    min_sell_val = min(sell_means, key=sell_means.get) if sell_means else 0.0  # type: ignore[arg-type]
    sell_dependency_warn = min_sell_val == 0.01

    # 6. 종합 판정 (3단계)
    # ✓/✗ 판정 대상: calmar_positive, plateau, adjacent (3개)
    # △ 주의 대상: ma_dependency, sell_dependency (2개, fail에 포함하지 않음)
    fail_count = sum([not calmar_positive_pass, not plateau_pass, not adjacent_pass])

    if fail_count == 0:
        overall_verdict = "pass"
    elif fail_count == 1:
        overall_verdict = "conditional"
    else:
        overall_verdict = "fail"

    return {
        "calmar_positive_ratio": positive_ratio,
        "calmar_positive_count": positive_count,
        "calmar_positive_pass": calmar_positive_pass,
        "plateau_range": plateau_range,
        "plateau_pass": plateau_pass,
        "opt_cell_mean": opt_cell_mean,
        "adjacent_threshold": threshold,
        "adjacent_min_mean": adjacent_min_mean,
        "adjacent_pass": adjacent_pass,
        "ma_gap_pct": ma_gap_pct,
        "ma_dependency_warn": ma_dependency_warn,
        "sell_dependency_warn": sell_dependency_warn,
        "overall_verdict": overall_verdict,
    }
