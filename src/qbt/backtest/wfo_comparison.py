"""Expanding vs Rolling WFO 비교 실험 모듈

동일 OOS 기간에서 Expanding Anchored WFO와 Rolling Window WFO의
성과 차이를 측정한다. IS 데이터 구성의 영향을 분리 검증한다.

주요 함수:
- run_single_wfo_mode: 단일 WFO 모드(Expanding 또는 Rolling) 실행
- build_window_comparison: 윈도우별 Expanding vs Rolling 비교 DataFrame 생성
- build_comparison_summary: 비교 요약 통계 생성
"""

from datetime import date as date_type
from statistics import median
from typing import TypedDict

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL
from qbt.backtest.strategies.buffer_zone_helpers import run_buffer_strategy
from qbt.backtest.types import WfoModeSummaryDict, WfoWindowResultDict
from qbt.backtest.walkforward import (
    build_params_schedule,
    calculate_wfo_mode_summary,
    run_walkforward,
)
from qbt.common_constants import COL_DATE
from qbt.utils import get_logger

logger = get_logger(__name__)

# ============================================================
# TypedDict 정의
# ============================================================


class WfoComparisonResultDict(TypedDict):
    """단일 WFO 모드의 실행 결과.

    run_single_wfo_mode()의 반환 타입.
    """

    window_type: str  # "expanding" 또는 "rolling"
    rolling_is_months: int | None
    window_results: list[WfoWindowResultDict]
    mode_summary: WfoModeSummaryDict


class WfoComparisonWindowRow(TypedDict):
    """윈도우별 비교 행.

    build_window_comparison() 결과 DataFrame의 각 행 구조.
    """

    window_idx: int
    oos_start: str
    oos_end: str
    expanding_is_start: str
    rolling_is_start: str
    is_identical: bool
    exp_oos_cagr: float
    exp_oos_mdd: float
    exp_oos_calmar: float
    exp_oos_trades: int
    roll_oos_cagr: float
    roll_oos_mdd: float
    roll_oos_calmar: float
    roll_oos_trades: int
    diff_oos_cagr: float
    diff_oos_mdd: float
    diff_oos_calmar: float


# ============================================================
# 공개 함수
# ============================================================


def run_single_wfo_mode(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    rolling_is_months: int | None = None,
    initial_is_months: int = 72,
    oos_months: int = 24,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    ma_window_list: list[int] | None = None,
    buy_buffer_zone_pct_list: list[float] | None = None,
    sell_buffer_zone_pct_list: list[float] | None = None,
    hold_days_list: list[int] | None = None,
    recent_months_list: list[int] | None = None,
    min_trades: int = 3,
    atr_period_list: list[int] | None = None,
    atr_multiplier_list: list[float] | None = None,
) -> WfoComparisonResultDict:
    """단일 WFO 모드(Expanding 또는 Rolling)를 실행한다.

    Args:
        signal_df: 시그널용 DataFrame (MA 컬럼 미포함, 내부에서 계산)
        trade_df: 매매용 DataFrame
        rolling_is_months: Rolling IS 최대 길이 (개월).
            None이면 Expanding 모드. int이면 Rolling 모드.
        initial_is_months: 초기 IS 기간 (개월)
        oos_months: OOS 기간 (개월)
        initial_capital: 초기 자본금
        ma_window_list: MA 윈도우 리스트 (None이면 기본값)
        buy_buffer_zone_pct_list: 매수 버퍼존 리스트 (None이면 기본값)
        sell_buffer_zone_pct_list: 매도 버퍼존 리스트 (None이면 기본값)
        hold_days_list: 유지일 리스트 (None이면 기본값)
        recent_months_list: 조정기간 리스트 (None이면 기본값)
        min_trades: IS 최적 파라미터 선택 시 최소 거래수 제약
        atr_period_list: ATR 기간 리스트 (None이면 ATR 미사용)
        atr_multiplier_list: ATR 배수 리스트 (None이면 ATR 미사용)

    Returns:
        WFO 모드 실행 결과 딕셔너리
    """
    window_type = "expanding" if rolling_is_months is None else "rolling"
    logger.debug(f"WFO {window_type} 모드 실행 시작 (rolling_is_months={rolling_is_months})")

    # 1. WFO 실행
    window_results = run_walkforward(
        signal_df=signal_df,
        trade_df=trade_df,
        ma_window_list=ma_window_list,
        buy_buffer_zone_pct_list=buy_buffer_zone_pct_list,
        sell_buffer_zone_pct_list=sell_buffer_zone_pct_list,
        hold_days_list=hold_days_list,
        recent_months_list=recent_months_list,
        initial_is_months=initial_is_months,
        oos_months=oos_months,
        initial_capital=initial_capital,
        min_trades=min_trades,
        atr_period_list=atr_period_list,
        atr_multiplier_list=atr_multiplier_list,
        rolling_is_months=rolling_is_months,
    )

    # 2. Stitched Equity 생성
    stitched_summary = _run_stitched_equity(signal_df, trade_df, window_results, initial_capital)

    # 3. 모드 요약 계산
    mode_summary = calculate_wfo_mode_summary(window_results, stitched_summary)

    logger.debug(
        f"WFO {window_type} 모드 완료: "
        f"윈도우 {len(window_results)}개, "
        f"Stitched CAGR={mode_summary.get('stitched_cagr', 0.0):.2f}%"
    )

    return {
        "window_type": window_type,
        "rolling_is_months": rolling_is_months,
        "window_results": window_results,
        "mode_summary": mode_summary,
    }


def build_window_comparison(
    expanding: WfoComparisonResultDict,
    rolling: WfoComparisonResultDict,
) -> pd.DataFrame:
    """윈도우별 Expanding vs Rolling 비교 DataFrame을 생성한다.

    각 윈도우에서 두 모드의 OOS 지표를 나란히 배치하고 차이(Expanding - Rolling)를 계산한다.

    Args:
        expanding: Expanding 모드 실행 결과
        rolling: Rolling 모드 실행 결과

    Returns:
        윈도우별 비교 DataFrame

    Raises:
        ValueError: 두 모드의 윈도우 수가 다른 경우
    """
    results_exp = expanding["window_results"]
    results_roll = rolling["window_results"]

    if len(results_exp) != len(results_roll):
        raise ValueError(f"윈도우 수 불일치: " f"Expanding={len(results_exp)}개, " f"Rolling={len(results_roll)}개")

    rows: list[WfoComparisonWindowRow] = []
    for wr_exp, wr_roll in zip(results_exp, results_roll, strict=True):
        row: WfoComparisonWindowRow = {
            "window_idx": wr_exp["window_idx"],
            "oos_start": wr_exp["oos_start"],
            "oos_end": wr_exp["oos_end"],
            "expanding_is_start": wr_exp["is_start"],
            "rolling_is_start": wr_roll["is_start"],
            "is_identical": wr_exp["is_start"] == wr_roll["is_start"],
            "exp_oos_cagr": wr_exp["oos_cagr"],
            "exp_oos_mdd": wr_exp["oos_mdd"],
            "exp_oos_calmar": wr_exp["oos_calmar"],
            "exp_oos_trades": wr_exp["oos_trades"],
            "roll_oos_cagr": wr_roll["oos_cagr"],
            "roll_oos_mdd": wr_roll["oos_mdd"],
            "roll_oos_calmar": wr_roll["oos_calmar"],
            "roll_oos_trades": wr_roll["oos_trades"],
            "diff_oos_cagr": wr_exp["oos_cagr"] - wr_roll["oos_cagr"],
            "diff_oos_mdd": wr_exp["oos_mdd"] - wr_roll["oos_mdd"],
            "diff_oos_calmar": wr_exp["oos_calmar"] - wr_roll["oos_calmar"],
        }
        rows.append(row)

    return pd.DataFrame(rows)


def build_comparison_summary(
    expanding: WfoComparisonResultDict,
    rolling: WfoComparisonResultDict,
    comparison_df: pd.DataFrame,
) -> dict[str, object]:
    """비교 요약 통계를 생성한다.

    Stitched 지표, 윈도우별 우위 카운트, 차이 통계를 포함한다.

    Args:
        expanding: Expanding 모드 실행 결과
        rolling: Rolling 모드 실행 결과
        comparison_df: build_window_comparison() 결과

    Returns:
        요약 통계 딕셔너리
    """
    summary_exp = expanding["mode_summary"]
    summary_roll = rolling["mode_summary"]

    n_windows = len(comparison_df)

    # 윈도우별 우위 카운트 (Expanding - Rolling)
    exp_wins_cagr = int((comparison_df["diff_oos_cagr"] > 0).sum())
    roll_wins_cagr = int((comparison_df["diff_oos_cagr"] < 0).sum())
    exp_wins_calmar = int((comparison_df["diff_oos_calmar"] > 0).sum())
    roll_wins_calmar = int((comparison_df["diff_oos_calmar"] < 0).sum())

    # IS가 동일한 윈도우 수 / 다른 윈도우 수
    n_identical = int(comparison_df["is_identical"].sum())
    n_diverged = n_windows - n_identical

    # 차이 통계
    diff_cagrs = comparison_df["diff_oos_cagr"].tolist()
    diff_calmars = comparison_df["diff_oos_calmar"].tolist()

    # 분기된 윈도우(IS가 다른 윈도우)만의 차이 통계
    diverged_mask = ~comparison_df["is_identical"]
    diverged_df = comparison_df[diverged_mask]
    diverged_diff_cagrs = diverged_df["diff_oos_cagr"].tolist() if len(diverged_df) > 0 else []
    diverged_diff_calmars = diverged_df["diff_oos_calmar"].tolist() if len(diverged_df) > 0 else []

    return {
        "rolling_is_months": rolling["rolling_is_months"],
        "n_windows": n_windows,
        "n_identical": n_identical,
        "n_diverged": n_diverged,
        # Expanding Stitched 지표
        "exp_stitched_cagr": summary_exp.get("stitched_cagr", 0.0),
        "exp_stitched_mdd": summary_exp.get("stitched_mdd", 0.0),
        "exp_stitched_calmar": summary_exp.get("stitched_calmar", 0.0),
        "exp_stitched_total_return_pct": summary_exp.get("stitched_total_return_pct", 0.0),
        # Rolling Stitched 지표
        "roll_stitched_cagr": summary_roll.get("stitched_cagr", 0.0),
        "roll_stitched_mdd": summary_roll.get("stitched_mdd", 0.0),
        "roll_stitched_calmar": summary_roll.get("stitched_calmar", 0.0),
        "roll_stitched_total_return_pct": summary_roll.get("stitched_total_return_pct", 0.0),
        # 우위 카운트 (전체)
        "exp_wins_cagr": exp_wins_cagr,
        "roll_wins_cagr": roll_wins_cagr,
        "exp_wins_calmar": exp_wins_calmar,
        "roll_wins_calmar": roll_wins_calmar,
        # 차이 통계 (전체, Expanding - Rolling)
        "diff_cagr_mean": sum(diff_cagrs) / n_windows if n_windows > 0 else 0.0,
        "diff_cagr_median": median(diff_cagrs) if diff_cagrs else 0.0,
        "diff_calmar_mean": sum(diff_calmars) / n_windows if n_windows > 0 else 0.0,
        "diff_calmar_median": median(diff_calmars) if diff_calmars else 0.0,
        # 차이 통계 (분기된 윈도우만)
        "diverged_diff_cagr_mean": (
            sum(diverged_diff_cagrs) / len(diverged_diff_cagrs) if diverged_diff_cagrs else 0.0
        ),
        "diverged_diff_cagr_median": (median(diverged_diff_cagrs) if diverged_diff_cagrs else 0.0),
        "diverged_diff_calmar_mean": (
            sum(diverged_diff_calmars) / len(diverged_diff_calmars) if diverged_diff_calmars else 0.0
        ),
        "diverged_diff_calmar_median": (median(diverged_diff_calmars) if diverged_diff_calmars else 0.0),
        # OOS 통계
        "exp_oos_cagr_mean": summary_exp["oos_cagr_mean"],
        "roll_oos_cagr_mean": summary_roll["oos_cagr_mean"],
        "exp_oos_calmar_mean": summary_exp["oos_calmar_mean"],
        "roll_oos_calmar_mean": summary_roll["oos_calmar_mean"],
    }


# ============================================================
# 내부 함수
# ============================================================


def _run_stitched_equity(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    window_results: list[WfoWindowResultDict],
    initial_capital: float,
) -> dict[str, object]:
    """Stitched Equity를 생성하고 요약 정보를 반환한다.

    WFO 결과의 params_schedule을 사용하여 첫 OOS 시작일부터
    마지막 OOS 종료일까지 연속 자본곡선을 생성한다.

    Args:
        signal_df: 시그널용 DataFrame
        trade_df: 매매용 DataFrame
        window_results: WFO 윈도우 결과 리스트
        initial_capital: 초기 자본금

    Returns:
        stitched_summary 딕셔너리 (calculate_summary 결과 + window_end_equities)
    """
    initial_params, schedule = build_params_schedule(window_results)

    # OOS 범위 결정
    first_oos_start = window_results[0]["oos_start"]
    last_oos_end = window_results[-1]["oos_end"]

    oos_start_date = date_type.fromisoformat(str(first_oos_start))
    oos_end_date = date_type.fromisoformat(str(last_oos_end))

    # OOS 구간 데이터 슬라이스
    oos_mask = (signal_df[COL_DATE] >= oos_start_date) & (signal_df[COL_DATE] <= oos_end_date)
    oos_signal = signal_df[oos_mask].reset_index(drop=True)
    oos_trade = trade_df[oos_mask].reset_index(drop=True)

    # 모든 MA 윈도우 사전 계산
    all_ma_windows = {initial_params.ma_window}
    for p in schedule.values():
        all_ma_windows.add(p.ma_window)

    for window in all_ma_windows:
        oos_signal = add_single_moving_average(oos_signal, window, ma_type="ema")

    # Stitched 실행
    _, equity_df, summary = run_buffer_strategy(
        oos_signal,
        oos_trade,
        initial_params,
        log_trades=False,
        params_schedule=schedule,
    )

    result_summary: dict[str, object] = dict(summary)

    # Profit Concentration 계산용 윈도우 경계 equity 추출
    window_end_equities: list[float] = []
    for wr in window_results:
        oos_end_str = str(wr["oos_end"])
        oos_end_d = date_type.fromisoformat(oos_end_str)
        mask = equity_df[COL_DATE] <= oos_end_d
        if mask.any():
            window_end_equities.append(float(equity_df[mask].iloc[-1]["equity"]))
    result_summary["window_end_equities"] = window_end_equities

    return result_summary
