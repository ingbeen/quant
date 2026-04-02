"""
백테스트 워크포워드 검증(WFO) 실행 스크립트

2-Mode 비교(Dynamic/Fully Fixed)를 수행하여 과최적화 검증 파이프라인을 구축합니다.
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

from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST,
    DEFAULT_WFO_HOLD_DAYS_LIST,
    DEFAULT_WFO_INITIAL_IS_MONTHS,
    DEFAULT_WFO_MA_WINDOW_LIST,
    DEFAULT_WFO_OOS_MONTHS,
    DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST,
    SLIPPAGE_RATE,
    WALKFORWARD_DYNAMIC_FILENAME,
    WALKFORWARD_EQUITY_DYNAMIC_FILENAME,
    WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME,
    WALKFORWARD_FULLY_FIXED_FILENAME,
    WALKFORWARD_SUMMARY_FILENAME,
    WFO_WINDOWS_DYNAMIC_DIR,
    WFO_WINDOWS_FULLY_FIXED_DIR,
)
from qbt.backtest.csv_export import prepare_trades_for_csv
from qbt.backtest.strategies import buffer_zone
from qbt.backtest.types import WfoModeSummaryDict, WfoWindowResultDict
from qbt.backtest.walkforward import (
    calculate_wfo_mode_summary,
    run_stitched_equity,
    run_walkforward,
    run_window_detail_backtests,
)
from qbt.common_constants import (
    COL_DATE,
    META_JSON_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import extract_overlap_period, load_stock_data
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# 전략별 설정 매핑 (WFO 대상: 기존 전략만)
_tqqq = buffer_zone.get_config("buffer_zone_tqqq")
_qqq = buffer_zone.get_config("buffer_zone_qqq")
STRATEGY_CONFIG: dict[str, dict[str, Path]] = {
    _tqqq.strategy_name: {
        "signal_path": _tqqq.signal_data_path,
        "trade_path": _tqqq.trade_data_path,
        "result_dir": _tqqq.result_dir,
    },
    _qqq.strategy_name: {
        "signal_path": _qqq.signal_data_path,
        "trade_path": _qqq.trade_data_path,
        "result_dir": _qqq.result_dir,
    },
}


def _load_data(strategy_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """전략에 맞는 데이터를 로딩한다."""
    config = STRATEGY_CONFIG[strategy_name]
    signal_path = Path(str(config["signal_path"]))
    trade_path = Path(str(config["trade_path"]))

    signal_df = load_stock_data(signal_path)

    if signal_path == trade_path:
        trade_df = signal_df.copy()
    else:
        trade_df = load_stock_data(trade_path)
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    return signal_df, trade_df


def _run_single_mode(
    mode_name: str,
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    ma_window_list: list[int],
    buy_buffer_zone_pct_list: list[float],
    sell_buffer_zone_pct_list: list[float],
    hold_days_list: list[int],
    initial_capital: float,
) -> tuple[list[WfoWindowResultDict], WfoModeSummaryDict, pd.DataFrame]:
    """단일 WFO 모드를 실행한다.

    Args:
        mode_name: 모드 이름 (dynamic / fully_fixed)
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
        initial_is_months=DEFAULT_WFO_INITIAL_IS_MONTHS,
        oos_months=DEFAULT_WFO_OOS_MONTHS,
        initial_capital=initial_capital,
    )

    # Stitched Equity 생성
    equity_df, stitched_summary = run_stitched_equity(signal_df, trade_df, window_results, initial_capital)

    # 모드 요약 계산
    mode_summary = calculate_wfo_mode_summary(window_results, stitched_summary)

    elapsed = time.time() - start_time
    logger.debug(f"[{mode_name}] 완료: {elapsed:.1f}초, 윈도우 {len(window_results)}개")

    return window_results, mode_summary, equity_df


# JSON 반올림 규칙: 백분율 2자리, 비율 4자리
_PCT_FIELDS = {
    "oos_cagr_mean",
    "oos_cagr_std",
    "oos_mdd_mean",
    "oos_mdd_worst",
    "oos_win_rate_mean",
    "stitched_cagr",
    "stitched_mdd",
    "stitched_total_return_pct",
}

_RATIO_FIELDS = {
    "oos_calmar_mean",
    "oos_calmar_std",
    "wfe_calmar_mean",
    "wfe_calmar_median",
    "wfe_cagr_mean",
    "wfe_cagr_median",
    "gap_calmar_median",
    "wfe_calmar_robust",
    "profit_concentration_max",
    "stitched_calmar",
}


def _round_summary_for_json(summary: dict[str, object]) -> dict[str, object]:
    """WfoModeSummaryDict를 JSON 저장용 반올림 규칙에 맞게 변환한다.

    Args:
        summary: WfoModeSummaryDict 또는 동등한 딕셔너리

    Returns:
        반올림 적용된 딕셔너리 (원본 변경 없음)
    """
    result: dict[str, object] = {}
    for key, value in summary.items():
        if key in _PCT_FIELDS and isinstance(value, int | float):
            result[key] = round(float(value), 2)
        elif key in _RATIO_FIELDS and isinstance(value, int | float):
            result[key] = round(float(value), 4)
        else:
            result[key] = value
    return result


def _save_window_detail_csvs(
    window_results: list[WfoWindowResultDict],
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    result_dir: Path,
    mode_dir_name: str,
    initial_capital: float,
) -> None:
    """윈도우별 상세 CSV(signal, equity, trades)를 저장한다.

    비즈니스 로직(백테스트 실행, 밴드/드로우다운 계산)은 walkforward 모듈에 위임하고,
    이 함수는 CSV 포맷팅과 저장만 수행한다.

    Args:
        window_results: WFO 윈도우 결과 리스트
        signal_df: 시그널용 원본 DataFrame (전체 기간)
        trade_df: 매매용 원본 DataFrame (전체 기간)
        result_dir: 전략 결과 디렉토리
        mode_dir_name: 모드별 하위 디렉토리명
        initial_capital: 초기 자본금
    """
    window_dir = result_dir / mode_dir_name
    window_dir.mkdir(parents=True, exist_ok=True)

    # 비즈니스 로직은 walkforward 모듈에 위임
    details = run_window_detail_backtests(
        window_results,
        signal_df,
        trade_df,
        initial_capital,
    )

    # CSV 포맷팅 및 저장 (CLI 책임)
    for detail in details:
        idx = detail.window_idx
        ma_col = detail.ma_col

        # --- signal CSV 저장 ---
        signal_cols = [COL_DATE, "Open", "High", "Low", "Close", ma_col, "change_pct"]
        signal_export = detail.signal_df[[c for c in signal_cols if c in detail.signal_df.columns]].copy()
        signal_round: dict[str, int] = {
            "Open": 6,
            "High": 6,
            "Low": 6,
            "Close": 6,
            "change_pct": 2,
        }
        if ma_col in signal_export.columns:
            signal_round[ma_col] = 6
        signal_export = signal_export.round(signal_round)
        signal_export.to_csv(window_dir / f"w{idx:02d}_signal.csv", index=False)

        # --- equity CSV 저장 ---
        equity_export = detail.equity_df.copy()
        equity_round: dict[str, int] = {
            "equity": 0,
            "upper_band": 6,
            "lower_band": 6,
            "buy_buffer_pct": 4,
            "sell_buffer_pct": 4,
            "drawdown_pct": 2,
        }
        equity_export = equity_export.round(equity_round)
        equity_export["equity"] = equity_export["equity"].astype(int)
        equity_export.to_csv(window_dir / f"w{idx:02d}_equity.csv", index=False)

        # --- trades CSV 저장 ---
        prepare_trades_for_csv(detail.trades_df).to_csv(window_dir / f"w{idx:02d}_trades.csv", index=False)

    logger.debug(f"윈도우별 상세 CSV 저장 완료: {window_dir} ({len(details)}개 윈도우)")


def _save_results(
    strategy_name: str,
    result_dir: Path,
    dynamic_results: list[WfoWindowResultDict],
    fully_fixed_results: list[WfoWindowResultDict],
    dynamic_equity: pd.DataFrame,
    fully_fixed_equity: pd.DataFrame,
    all_summaries: dict[str, object],
) -> None:
    """WFO 결과를 CSV/JSON으로 저장한다."""
    result_dir.mkdir(parents=True, exist_ok=True)

    # WFO 윈도우 결과 CSV 저장
    for filename, results in [
        (WALKFORWARD_DYNAMIC_FILENAME, dynamic_results),
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
            elif col in ["is_calmar", "oos_calmar", "wfe_calmar", "wfe_cagr"]:
                round_cols[col] = 4
            elif col.endswith("_buffer_zone_pct"):
                round_cols[col] = 4
        if round_cols:
            df = df.round(round_cols)
        df.to_csv(result_dir / filename, index=False)

    # Equity CSV 저장
    for filename, eq_df in [
        (WALKFORWARD_EQUITY_DYNAMIC_FILENAME, dynamic_equity),
        (WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME, fully_fixed_equity),
    ]:
        if not eq_df.empty:
            eq_export = eq_df.round(
                {"equity": 0, "buy_buffer_pct": 4, "sell_buffer_pct": 4, "upper_band": 6, "lower_band": 6}
            )
            eq_export.to_csv(result_dir / filename, index=False)

    # 요약 JSON 저장 (반올림 규칙 적용)
    rounded_summaries: dict[str, object] = {"strategy": all_summaries.get("strategy", "")}
    for mode_key in ["dynamic", "fully_fixed"]:
        if mode_key in all_summaries:
            mode_data = all_summaries[mode_key]
            if isinstance(mode_data, dict):
                rounded_summaries[mode_key] = _round_summary_for_json(mode_data)
            else:
                rounded_summaries[mode_key] = mode_data

    summary_path = result_dir / WALKFORWARD_SUMMARY_FILENAME
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(rounded_summaries, f, indent=2, ensure_ascii=False, default=str)

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
        ["WFE Calmar 평균", f"{summary['wfe_calmar_mean']:.4f}"],
        ["WFE Calmar 중앙값", f"{summary['wfe_calmar_median']:.4f}"],
        ["WFE Calmar Robust", f"{summary['wfe_calmar_robust']:.4f}"],
        ["WFE CAGR 평균", f"{summary['wfe_cagr_mean']:.4f}"],
        ["WFE CAGR 중앙값", f"{summary['wfe_cagr_median']:.4f}"],
        ["Gap Calmar 중앙값", f"{summary['gap_calmar_median']:.4f}"],
        ["PC 최대", f"{summary['profit_concentration_max']:.4f}"],
        ["PC 최대 윈도우", str(summary["profit_concentration_window_idx"])],
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
    parser = argparse.ArgumentParser(description="백테스트 워크포워드 검증 (2-Mode)")
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
        result_dir = Path(str(STRATEGY_CONFIG[strategy_name]["result_dir"]))
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
            DEFAULT_INITIAL_CAPITAL,
        )

        # 3-3. Mode 2: Fully Fixed (첫 윈도우 best params 고정)
        logger.debug("-" * 40)
        logger.debug("[Mode 2: Fully Fixed] 첫 IS 윈도우 최적 파라미터 고정")
        first_best = dynamic_results[0]

        fully_fixed_results, fully_fixed_summary, fully_fixed_equity = _run_single_mode(
            "fully_fixed",
            signal_df,
            trade_df,
            [first_best["best_ma_window"]],
            [first_best["best_buy_buffer_zone_pct"]],
            [first_best["best_sell_buffer_zone_pct"]],
            [first_best["best_hold_days"]],
            DEFAULT_INITIAL_CAPITAL,
        )

        # 3-4. 요약 출력
        _print_mode_summary("Dynamic", dynamic_summary)
        _print_mode_summary("Fully Fixed", fully_fixed_summary)

        # 3-5. 결과 저장
        all_summaries: dict[str, object] = {
            "strategy": strategy_name,
            "dynamic": dynamic_summary,
            "fully_fixed": fully_fixed_summary,
        }

        _save_results(
            strategy_name,
            result_dir,
            dynamic_results,
            fully_fixed_results,
            dynamic_equity,
            fully_fixed_equity,
            all_summaries,
        )

        # 3-6. 윈도우별 상세 CSV 저장
        _save_window_detail_csvs(
            dynamic_results,
            signal_df,
            trade_df,
            result_dir,
            WFO_WINDOWS_DYNAMIC_DIR,
            DEFAULT_INITIAL_CAPITAL,
        )
        _save_window_detail_csvs(
            fully_fixed_results,
            signal_df,
            trade_df,
            result_dir,
            WFO_WINDOWS_FULLY_FIXED_DIR,
            DEFAULT_INITIAL_CAPITAL,
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
                "initial_capital": round(DEFAULT_INITIAL_CAPITAL, 2),
                "slippage_rate": round(SLIPPAGE_RATE, 4),
            },
            "data_period": {
                "start_date": str(signal_df[COL_DATE].min()),
                "end_date": str(signal_df[COL_DATE].max()),
                "total_days": len(signal_df),
            },
            "results_summary": {
                "n_windows_dynamic": dynamic_summary["n_windows"],
                "dynamic_oos_cagr_mean": round(dynamic_summary["oos_cagr_mean"], 2),
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
