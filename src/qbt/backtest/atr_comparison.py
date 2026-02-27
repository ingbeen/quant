"""ATR 비교 실험 모듈

ATR 파라미터를 고정하여 WFO Dynamic OOS 성과를 비교한다.
IS 최적화 없이 고정한 ATR로 WFO를 실행하여
"우연히 잘 맞은 것"인지 "구조적으로 우수한 것"인지 검증한다.

주요 함수:
- run_single_atr_config: 단일 ATR 설정으로 WFO + Stitched Equity + 요약 생성
- build_window_comparison: 두 ATR 설정의 윈도우별 비교 DataFrame 생성
- build_comparison_summary: 두 ATR 설정의 요약 통계 생성
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


class AtrComparisonResultDict(TypedDict):
    """단일 ATR 설정의 WFO 실행 결과.

    run_single_atr_config()의 반환 타입.
    """

    atr_period: int
    atr_multiplier: float
    window_results: list[WfoWindowResultDict]
    mode_summary: WfoModeSummaryDict


class WindowComparisonRow(TypedDict):
    """윈도우별 비교 행.

    build_window_comparison() 결과 DataFrame의 각 행 구조.
    """

    window_idx: int
    oos_start: str
    oos_end: str
    a_oos_cagr: float
    a_oos_mdd: float
    a_oos_calmar: float
    a_oos_trades: int
    a_oos_win_rate: float
    b_oos_cagr: float
    b_oos_mdd: float
    b_oos_calmar: float
    b_oos_trades: int
    b_oos_win_rate: float
    diff_oos_cagr: float
    diff_oos_mdd: float
    diff_oos_calmar: float


# ============================================================
# 공개 함수
# ============================================================


def run_single_atr_config(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    atr_period: int,
    atr_multiplier: float,
    initial_is_months: int = 72,
    oos_months: int = 24,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    ma_window_list: list[int] | None = None,
    buy_buffer_zone_pct_list: list[float] | None = None,
    sell_buffer_zone_pct_list: list[float] | None = None,
    hold_days_list: list[int] | None = None,
    recent_months_list: list[int] | None = None,
    min_trades: int = 3,
) -> AtrComparisonResultDict:
    """단일 ATR 설정으로 WFO + Stitched Equity + 요약을 실행한다.

    ATR 파라미터를 고정하고 나머지 버퍼존 파라미터는 IS 최적화한다.
    run_walkforward()에 atr_period_list=[atr_period]로 전달하여
    ATR 차원을 제거한 그리드(432개)로 IS 최적화를 수행한다.

    Args:
        signal_df: 시그널용 DataFrame (MA 컬럼 미포함, 내부에서 계산)
        trade_df: 매매용 DataFrame
        atr_period: 고정할 ATR 기간 (예: 14, 22)
        atr_multiplier: 고정할 ATR 배수 (예: 3.0)
        initial_is_months: 초기 IS 기간 (개월)
        oos_months: OOS 기간 (개월)
        initial_capital: 초기 자본금
        ma_window_list: MA 윈도우 리스트 (None이면 기본값)
        buy_buffer_zone_pct_list: 매수 버퍼존 리스트 (None이면 기본값)
        sell_buffer_zone_pct_list: 매도 버퍼존 리스트 (None이면 기본값)
        hold_days_list: 유지일 리스트 (None이면 기본값)
        recent_months_list: 조정기간 리스트 (None이면 기본값)
        min_trades: IS 최적 파라미터 선택 시 최소 거래수 제약

    Returns:
        ATR 비교 결과 딕셔너리 (윈도우 결과 + 모드 요약)
    """
    logger.debug(f"ATR({atr_period}, {atr_multiplier}) WFO 실행 시작")

    # 1. WFO 실행 (ATR 고정)
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
        atr_period_list=[atr_period],
        atr_multiplier_list=[atr_multiplier],
    )

    # 2. Stitched Equity 생성
    stitched_summary = _run_stitched_equity(signal_df, trade_df, window_results, initial_capital)

    # 3. 모드 요약 계산
    mode_summary = calculate_wfo_mode_summary(window_results, stitched_summary)

    logger.debug(
        f"ATR({atr_period}, {atr_multiplier}) WFO 완료: "
        f"윈도우 {len(window_results)}개, "
        f"Stitched CAGR={mode_summary.get('stitched_cagr', 0.0):.2f}%"
    )

    return {
        "atr_period": atr_period,
        "atr_multiplier": atr_multiplier,
        "window_results": window_results,
        "mode_summary": mode_summary,
    }


def build_window_comparison(
    config_a: AtrComparisonResultDict,
    config_b: AtrComparisonResultDict,
) -> pd.DataFrame:
    """두 ATR 설정의 윈도우별 OOS 성과를 비교한다.

    각 윈도우에서 A와 B의 OOS 지표를 나란히 배치하고 차이(A - B)를 계산한다.

    Args:
        config_a: 첫 번째 ATR 설정 결과
        config_b: 두 번째 ATR 설정 결과

    Returns:
        윈도우별 비교 DataFrame

    Raises:
        ValueError: 두 설정의 윈도우 수가 다른 경우
    """
    results_a = config_a["window_results"]
    results_b = config_b["window_results"]

    if len(results_a) != len(results_b):
        raise ValueError(
            f"윈도우 수 불일치: "
            f"ATR({config_a['atr_period']})={len(results_a)}개, "
            f"ATR({config_b['atr_period']})={len(results_b)}개"
        )

    rows: list[WindowComparisonRow] = []
    for wr_a, wr_b in zip(results_a, results_b, strict=True):
        row: WindowComparisonRow = {
            "window_idx": wr_a["window_idx"],
            "oos_start": wr_a["oos_start"],
            "oos_end": wr_a["oos_end"],
            "a_oos_cagr": wr_a["oos_cagr"],
            "a_oos_mdd": wr_a["oos_mdd"],
            "a_oos_calmar": wr_a["oos_calmar"],
            "a_oos_trades": wr_a["oos_trades"],
            "a_oos_win_rate": wr_a["oos_win_rate"],
            "b_oos_cagr": wr_b["oos_cagr"],
            "b_oos_mdd": wr_b["oos_mdd"],
            "b_oos_calmar": wr_b["oos_calmar"],
            "b_oos_trades": wr_b["oos_trades"],
            "b_oos_win_rate": wr_b["oos_win_rate"],
            "diff_oos_cagr": wr_a["oos_cagr"] - wr_b["oos_cagr"],
            "diff_oos_mdd": wr_a["oos_mdd"] - wr_b["oos_mdd"],
            "diff_oos_calmar": wr_a["oos_calmar"] - wr_b["oos_calmar"],
        }
        rows.append(row)

    return pd.DataFrame(rows)


def build_comparison_summary(
    config_a: AtrComparisonResultDict,
    config_b: AtrComparisonResultDict,
    comparison_df: pd.DataFrame,
) -> dict[str, object]:
    """두 ATR 설정의 요약 통계를 생성한다.

    Stitched 지표, 윈도우별 우위 카운트, 차이 통계를 포함한다.

    Args:
        config_a: 첫 번째 ATR 설정 결과
        config_b: 두 번째 ATR 설정 결과
        comparison_df: build_window_comparison() 결과

    Returns:
        요약 통계 딕셔너리
    """
    summary_a = config_a["mode_summary"]
    summary_b = config_b["mode_summary"]

    n_windows = len(comparison_df)

    # 윈도우별 우위 카운트
    a_wins_cagr = int((comparison_df["diff_oos_cagr"] > 0).sum())
    b_wins_cagr = int((comparison_df["diff_oos_cagr"] < 0).sum())
    a_wins_calmar = int((comparison_df["diff_oos_calmar"] > 0).sum())
    b_wins_calmar = int((comparison_df["diff_oos_calmar"] < 0).sum())

    # 차이 통계
    diff_cagrs = comparison_df["diff_oos_cagr"].tolist()
    diff_calmars = comparison_df["diff_oos_calmar"].tolist()

    return {
        "a_atr_period": config_a["atr_period"],
        "a_atr_multiplier": config_a["atr_multiplier"],
        "b_atr_period": config_b["atr_period"],
        "b_atr_multiplier": config_b["atr_multiplier"],
        "n_windows": n_windows,
        # A Stitched 지표
        "a_stitched_cagr": summary_a.get("stitched_cagr", 0.0),
        "a_stitched_mdd": summary_a.get("stitched_mdd", 0.0),
        "a_stitched_calmar": summary_a.get("stitched_calmar", 0.0),
        "a_stitched_total_return_pct": summary_a.get("stitched_total_return_pct", 0.0),
        # B Stitched 지표
        "b_stitched_cagr": summary_b.get("stitched_cagr", 0.0),
        "b_stitched_mdd": summary_b.get("stitched_mdd", 0.0),
        "b_stitched_calmar": summary_b.get("stitched_calmar", 0.0),
        "b_stitched_total_return_pct": summary_b.get("stitched_total_return_pct", 0.0),
        # 우위 카운트
        "a_wins_cagr": a_wins_cagr,
        "b_wins_cagr": b_wins_cagr,
        "a_wins_calmar": a_wins_calmar,
        "b_wins_calmar": b_wins_calmar,
        # 차이 통계 (A - B)
        "diff_cagr_mean": sum(diff_cagrs) / n_windows if n_windows > 0 else 0.0,
        "diff_cagr_median": median(diff_cagrs) if diff_cagrs else 0.0,
        "diff_calmar_mean": sum(diff_calmars) / n_windows if n_windows > 0 else 0.0,
        "diff_calmar_median": median(diff_calmars) if diff_calmars else 0.0,
        # OOS 통계
        "a_oos_cagr_mean": summary_a["oos_cagr_mean"],
        "b_oos_cagr_mean": summary_b["oos_cagr_mean"],
        "a_oos_calmar_mean": summary_a["oos_calmar_mean"],
        "b_oos_calmar_mean": summary_b["oos_calmar_mean"],
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
