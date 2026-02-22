"""
백테스트 워크포워드 검증(WFO) 실행 스크립트

3-Mode 비교를 수행하여 과최적화 검증 파이프라인을 구축합니다.
--strategy 인자로 실행할 전략을 선택할 수 있습니다 (기본값: all).

실행 명령어:
    poetry run python scripts/backtest/run_walkforward.py
    poetry run python scripts/backtest/run_walkforward.py --strategy buffer_zone_tqqq
    poetry run python scripts/backtest/run_walkforward.py --strategy buffer_zone_qqq
"""

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST,
    DEFAULT_WFO_FIXED_SELL_BUFFER_PCT,
    DEFAULT_WFO_HOLD_DAYS_LIST,
    DEFAULT_WFO_INITIAL_IS_MONTHS,
    DEFAULT_WFO_MA_WINDOW_LIST,
    DEFAULT_WFO_OOS_MONTHS,
    DEFAULT_WFO_RECENT_MONTHS_LIST,
    DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST,
    SLIPPAGE_RATE,
    WALKFORWARD_DYNAMIC_FILENAME,
    WALKFORWARD_EQUITY_DYNAMIC_FILENAME,
    WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME,
    WALKFORWARD_EQUITY_SELL_FIXED_FILENAME,
    WALKFORWARD_FULLY_FIXED_FILENAME,
    WALKFORWARD_SELL_FIXED_FILENAME,
    WALKFORWARD_SUMMARY_FILENAME,
)
from qbt.backtest.strategies import buffer_zone_qqq, buffer_zone_tqqq
from qbt.backtest.strategies.buffer_zone_helpers import run_buffer_strategy
from qbt.backtest.types import WfoModeSummaryDict, WfoWindowResultDict
from qbt.backtest.walkforward import (
    build_params_schedule,
    calculate_wfo_mode_summary,
    run_walkforward,
)
from qbt.common_constants import (
    COL_DATE,
    META_JSON_PATH,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import extract_overlap_period, load_stock_data
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# 전략별 설정 매핑
STRATEGY_CONFIG: dict[str, dict[str, Path]] = {
    buffer_zone_tqqq.STRATEGY_NAME: {
        "signal_path": QQQ_DATA_PATH,
        "trade_path": TQQQ_SYNTHETIC_DATA_PATH,
        "result_dir": buffer_zone_tqqq.GRID_RESULTS_PATH.parent,
    },
    buffer_zone_qqq.STRATEGY_NAME: {
        "signal_path": QQQ_DATA_PATH,
        "trade_path": QQQ_DATA_PATH,
        "result_dir": buffer_zone_qqq.GRID_RESULTS_PATH.parent,
    },
}


def _load_data(strategy_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """전략에 맞는 데이터를 로딩한다."""
    config = STRATEGY_CONFIG[strategy_name]
    signal_path = config["signal_path"]
    trade_path = config["trade_path"]

    signal_df = load_stock_data(signal_path)

    if signal_path == trade_path:
        trade_df = signal_df.copy()
    else:
        trade_df = load_stock_data(trade_path)
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    return signal_df, trade_df


def _run_stitched_equity(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    window_results: list[WfoWindowResultDict],
    initial_capital: float,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Stitched Equity를 생성한다.

    WFO 결과의 params_schedule을 사용하여 첫 OOS 시작일부터 마지막 OOS 종료일까지
    연속 자본곡선을 생성한다.

    Args:
        signal_df: 시그널용 DataFrame
        trade_df: 매매용 DataFrame
        window_results: WFO 윈도우 결과 리스트
        initial_capital: 초기 자본금

    Returns:
        (equity_df, summary) 튜플
    """
    initial_params, schedule = build_params_schedule(window_results)

    # OOS 범위 결정
    first_oos_start = window_results[0]["oos_start"]
    last_oos_end = window_results[-1]["oos_end"]

    # OOS 구간 데이터 슬라이스
    from datetime import date as date_type

    oos_start_date = date_type.fromisoformat(str(first_oos_start))
    oos_end_date = date_type.fromisoformat(str(last_oos_end))

    oos_mask = (signal_df[COL_DATE] >= oos_start_date) & (signal_df[COL_DATE] <= oos_end_date)
    oos_signal = signal_df[oos_mask].reset_index(drop=True)
    oos_trade = trade_df[oos_mask].reset_index(drop=True)

    # 모든 MA 윈도우 사전 계산
    all_ma_windows = {initial_params.ma_window}
    for p in schedule.values():
        all_ma_windows.add(p.ma_window)

    for window in all_ma_windows:
        oos_signal = add_single_moving_average(oos_signal, window, ma_type="ema")

    # stitched 실행
    trades_df, equity_df, summary = run_buffer_strategy(
        oos_signal,
        oos_trade,
        initial_params,
        log_trades=False,
        params_schedule=schedule,
    )

    return equity_df, dict(summary)


def _run_single_mode(
    mode_name: str,
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    ma_window_list: list[int],
    buy_buffer_zone_pct_list: list[float],
    sell_buffer_zone_pct_list: list[float],
    hold_days_list: list[int],
    recent_months_list: list[int],
    initial_capital: float,
) -> tuple[list[WfoWindowResultDict], WfoModeSummaryDict, pd.DataFrame]:
    """단일 WFO 모드를 실행한다.

    Args:
        mode_name: 모드 이름 (dynamic / sell_fixed / fully_fixed)
        signal_df: 시그널 DataFrame
        trade_df: 매매 DataFrame
        기타: 파라미터 리스트들

    Returns:
        (window_results, mode_summary, equity_df) 튜플
    """
    start_time = time.time()

    window_results = run_walkforward(
        signal_df=signal_df,
        trade_df=trade_df,
        ma_window_list=ma_window_list,
        buy_buffer_zone_pct_list=buy_buffer_zone_pct_list,
        sell_buffer_zone_pct_list=sell_buffer_zone_pct_list,
        hold_days_list=hold_days_list,
        recent_months_list=recent_months_list,
        initial_is_months=DEFAULT_WFO_INITIAL_IS_MONTHS,
        oos_months=DEFAULT_WFO_OOS_MONTHS,
        initial_capital=initial_capital,
    )

    # Stitched Equity 생성
    equity_df, stitched_summary = _run_stitched_equity(signal_df, trade_df, window_results, initial_capital)

    # 모드 요약 계산
    mode_summary = calculate_wfo_mode_summary(window_results, stitched_summary)

    elapsed = time.time() - start_time
    logger.debug(f"[{mode_name}] 완료: {elapsed:.1f}초, 윈도우 {len(window_results)}개")

    return window_results, mode_summary, equity_df


def _save_results(
    strategy_name: str,
    result_dir: Path,
    dynamic_results: list[WfoWindowResultDict],
    sell_fixed_results: list[WfoWindowResultDict],
    fully_fixed_results: list[WfoWindowResultDict],
    dynamic_equity: pd.DataFrame,
    sell_fixed_equity: pd.DataFrame,
    fully_fixed_equity: pd.DataFrame,
    all_summaries: dict[str, object],
) -> None:
    """WFO 결과를 CSV/JSON으로 저장한다."""
    result_dir.mkdir(parents=True, exist_ok=True)

    # WFO 윈도우 결과 CSV 저장
    for filename, results in [
        (WALKFORWARD_DYNAMIC_FILENAME, dynamic_results),
        (WALKFORWARD_SELL_FIXED_FILENAME, sell_fixed_results),
        (WALKFORWARD_FULLY_FIXED_FILENAME, fully_fixed_results),
    ]:
        df = pd.DataFrame(results)
        # 반올림 규칙 적용
        round_cols = {}
        for col in df.columns:
            if col.endswith("_pct") or col in [
                "is_cagr",
                "oos_cagr",
                "is_mdd",
                "oos_mdd",
                "is_win_rate",
                "oos_win_rate",
            ]:
                round_cols[col] = 2
            elif col in ["is_calmar", "oos_calmar", "wfe_calmar"]:
                round_cols[col] = 4
            elif col.endswith("_buffer_zone_pct"):
                round_cols[col] = 4
        if round_cols:
            df = df.round(round_cols)
        df.to_csv(result_dir / filename, index=False)

    # Equity CSV 저장
    for filename, eq_df in [
        (WALKFORWARD_EQUITY_DYNAMIC_FILENAME, dynamic_equity),
        (WALKFORWARD_EQUITY_SELL_FIXED_FILENAME, sell_fixed_equity),
        (WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME, fully_fixed_equity),
    ]:
        if not eq_df.empty:
            eq_export = eq_df.round(
                {"equity": 0, "buy_buffer_pct": 4, "sell_buffer_pct": 4, "upper_band": 6, "lower_band": 6}
            )
            eq_export.to_csv(result_dir / filename, index=False)

    # 요약 JSON 저장
    summary_path = result_dir / WALKFORWARD_SUMMARY_FILENAME
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(all_summaries, f, indent=2, ensure_ascii=False, default=str)

    logger.debug(f"결과 저장 완료: {result_dir}")


def _print_mode_summary(mode_name: str, summary: WfoModeSummaryDict) -> None:
    """모드별 요약을 테이블로 출력한다."""
    columns = [
        ("항목", 20, Align.LEFT),
        ("값", 15, Align.RIGHT),
    ]
    rows = [
        ["윈도우 수", str(summary["n_windows"])],
        ["OOS CAGR 평균", f"{summary['oos_cagr_mean']:.2f}%"],
        ["OOS CAGR 표준편차", f"{summary['oos_cagr_std']:.2f}%"],
        ["OOS MDD 평균", f"{summary['oos_mdd_mean']:.2f}%"],
        ["OOS MDD 최악", f"{summary['oos_mdd_worst']:.2f}%"],
        ["OOS Calmar 평균", f"{summary['oos_calmar_mean']:.4f}"],
        ["WFE 평균", f"{summary['wfe_calmar_mean']:.4f}"],
        ["WFE 중앙값", f"{summary['wfe_calmar_median']:.4f}"],
        ["OOS 총 거래수", str(summary["oos_trades_total"])],
    ]

    if "stitched_cagr" in summary:
        rows.append(["Stitched CAGR", f"{summary['stitched_cagr']:.2f}%"])
    if "stitched_mdd" in summary:
        rows.append(["Stitched MDD", f"{summary['stitched_mdd']:.2f}%"])

    table = TableLogger(columns, logger)
    table.print_table(rows, title=f"[{mode_name}] WFO 요약")


@cli_exception_handler
def main() -> int:
    """메인 실행 함수."""
    # 1. argparse
    parser = argparse.ArgumentParser(description="백테스트 워크포워드 검증 (3-Mode)")
    parser.add_argument(
        "--strategy",
        choices=["all", *STRATEGY_CONFIG.keys()],
        default="all",
        help="실행할 전략 (기본값: all)",
    )
    args = parser.parse_args()

    # 2. 전략 목록 결정
    if args.strategy == "all":
        strategy_names = list(STRATEGY_CONFIG.keys())
    else:
        strategy_names = [args.strategy]

    logger.debug(f"실행 전략: {strategy_names}")

    # 3. 전략별 WFO 실행
    for strategy_name in strategy_names:
        result_dir = STRATEGY_CONFIG[strategy_name]["result_dir"]
        total_start = time.time()

        logger.debug("=" * 60)
        logger.debug(f"[{strategy_name}] 워크포워드 검증 시작")

        # 3-1. 데이터 로딩
        signal_df, trade_df = _load_data(strategy_name)
        logger.debug(f"데이터 로딩 완료: {signal_df[COL_DATE].min()} ~ {signal_df[COL_DATE].max()}, " f"{len(signal_df)}행")

        # 3-2. Mode 1: Dynamic (모든 파라미터 IS 최적화)
        logger.debug("-" * 40)
        logger.debug("[Mode 1: Dynamic] 모든 파라미터 IS 최적화")
        dynamic_results, dynamic_summary, dynamic_equity = _run_single_mode(
            "dynamic",
            signal_df,
            trade_df,
            list(DEFAULT_WFO_MA_WINDOW_LIST),
            list(DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST),
            list(DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST),
            list(DEFAULT_WFO_HOLD_DAYS_LIST),
            list(DEFAULT_WFO_RECENT_MONTHS_LIST),
            DEFAULT_INITIAL_CAPITAL,
        )

        # 3-3. Mode 2: Sell Fixed (sell_buffer=0.05 고정)
        logger.debug("-" * 40)
        logger.debug(f"[Mode 2: Sell Fixed] sell_buffer={DEFAULT_WFO_FIXED_SELL_BUFFER_PCT} 고정")
        sell_fixed_results, sell_fixed_summary, sell_fixed_equity = _run_single_mode(
            "sell_fixed",
            signal_df,
            trade_df,
            list(DEFAULT_WFO_MA_WINDOW_LIST),
            list(DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST),
            [DEFAULT_WFO_FIXED_SELL_BUFFER_PCT],  # 고정
            list(DEFAULT_WFO_HOLD_DAYS_LIST),
            list(DEFAULT_WFO_RECENT_MONTHS_LIST),
            DEFAULT_INITIAL_CAPITAL,
        )

        # 3-4. Mode 3: Fully Fixed (첫 윈도우 best params 고정)
        logger.debug("-" * 40)
        logger.debug("[Mode 3: Fully Fixed] 첫 IS 윈도우 최적 파라미터 고정")
        first_best = dynamic_results[0]
        fully_fixed_results, fully_fixed_summary, fully_fixed_equity = _run_single_mode(
            "fully_fixed",
            signal_df,
            trade_df,
            [first_best["best_ma_window"]],
            [first_best["best_buy_buffer_zone_pct"]],
            [first_best["best_sell_buffer_zone_pct"]],
            [first_best["best_hold_days"]],
            [first_best["best_recent_months"]],
            DEFAULT_INITIAL_CAPITAL,
        )

        # 3-5. 요약 출력
        _print_mode_summary("Dynamic", dynamic_summary)
        _print_mode_summary("Sell Fixed", sell_fixed_summary)
        _print_mode_summary("Fully Fixed", fully_fixed_summary)

        # 3-6. 결과 저장
        all_summaries: dict[str, object] = {
            "strategy": strategy_name,
            "dynamic": dynamic_summary,
            "sell_fixed": sell_fixed_summary,
            "fully_fixed": fully_fixed_summary,
        }

        _save_results(
            strategy_name,
            result_dir,
            dynamic_results,
            sell_fixed_results,
            fully_fixed_results,
            dynamic_equity,
            sell_fixed_equity,
            fully_fixed_equity,
            all_summaries,
        )

        # 3-7. 메타데이터 저장
        total_elapsed = time.time() - total_start
        metadata = {
            "strategy": strategy_name,
            "execution_params": {
                "initial_is_months": DEFAULT_WFO_INITIAL_IS_MONTHS,
                "oos_months": DEFAULT_WFO_OOS_MONTHS,
                "ma_window_list": list(DEFAULT_WFO_MA_WINDOW_LIST),
                "buy_buffer_zone_pct_list": [round(x, 4) for x in DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST],
                "sell_buffer_zone_pct_list": [round(x, 4) for x in DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST],
                "hold_days_list": list(DEFAULT_WFO_HOLD_DAYS_LIST),
                "recent_months_list": list(DEFAULT_WFO_RECENT_MONTHS_LIST),
                "initial_capital": round(DEFAULT_INITIAL_CAPITAL, 2),
                "slippage_rate": round(SLIPPAGE_RATE, 4),
                "fixed_sell_buffer_pct": round(DEFAULT_WFO_FIXED_SELL_BUFFER_PCT, 4),
            },
            "data_period": {
                "start_date": str(signal_df[COL_DATE].min()),
                "end_date": str(signal_df[COL_DATE].max()),
                "total_days": len(signal_df),
            },
            "results_summary": {
                "n_windows_dynamic": dynamic_summary["n_windows"],
                "dynamic_oos_cagr_mean": round(dynamic_summary["oos_cagr_mean"], 2),
                "sell_fixed_oos_cagr_mean": round(sell_fixed_summary["oos_cagr_mean"], 2),
                "fully_fixed_oos_cagr_mean": round(fully_fixed_summary["oos_cagr_mean"], 2),
            },
            "elapsed_seconds": round(total_elapsed, 1),
        }

        save_metadata("backtest_walkforward", metadata)
        logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")
        logger.debug(f"[{strategy_name}] 전체 소요 시간: {total_elapsed:.1f}초")

    return 0


if __name__ == "__main__":
    sys.exit(main())
