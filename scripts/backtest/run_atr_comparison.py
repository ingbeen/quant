"""
ATR(14,3.0) vs ATR(22,3.0) OOS 비교 실험 스크립트

IS 최적화 없이 ATR 파라미터를 고정하여 WFO Dynamic OOS 성과를 비교합니다.
PBO 0.65 경고에 대한 독립적 검증 근거를 제공합니다.

실행 명령어:
    poetry run python scripts/backtest/run_atr_comparison.py
"""

import json
import sys
import time

from qbt.backtest.atr_comparison import (
    build_comparison_summary,
    build_window_comparison,
    run_single_atr_config,
)
from qbt.backtest.constants import (
    ATR_COMPARISON_SUMMARY_FILENAME,
    ATR_COMPARISON_WINDOWS_FILENAME,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST,
    DEFAULT_WFO_HOLD_DAYS_LIST,
    DEFAULT_WFO_INITIAL_IS_MONTHS,
    DEFAULT_WFO_MA_WINDOW_LIST,
    DEFAULT_WFO_OOS_MONTHS,
    DEFAULT_WFO_RECENT_MONTHS_LIST,
    DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST,
    SLIPPAGE_RATE,
)
from qbt.common_constants import (
    BUFFER_ZONE_ATR_TQQQ_RESULTS_DIR,
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

# ATR 비교 설정 (로컬 상수 — 이 파일에서만 사용)
ATR_CONFIG_A_PERIOD = 14
ATR_CONFIG_A_MULTIPLIER = 3.0
ATR_CONFIG_B_PERIOD = 22
ATR_CONFIG_B_MULTIPLIER = 3.0


def _print_comparison_summary(summary: dict[str, object]) -> None:
    """비교 요약을 테이블로 출력한다."""
    a_label = f"ATR({summary['a_atr_period']},{summary['a_atr_multiplier']})"
    b_label = f"ATR({summary['b_atr_period']},{summary['b_atr_multiplier']})"

    columns = [
        ("항목", 25, Align.LEFT),
        (a_label, 15, Align.RIGHT),
        (b_label, 15, Align.RIGHT),
    ]
    rows = [
        [
            "Stitched CAGR",
            f"{summary['a_stitched_cagr']:.2f}%",
            f"{summary['b_stitched_cagr']:.2f}%",
        ],
        [
            "Stitched MDD",
            f"{summary['a_stitched_mdd']:.2f}%",
            f"{summary['b_stitched_mdd']:.2f}%",
        ],
        [
            "Stitched Calmar",
            f"{summary['a_stitched_calmar']:.4f}",
            f"{summary['b_stitched_calmar']:.4f}",
        ],
        [
            "OOS CAGR 평균",
            f"{summary['a_oos_cagr_mean']:.2f}%",
            f"{summary['b_oos_cagr_mean']:.2f}%",
        ],
        [
            "OOS Calmar 평균",
            f"{summary['a_oos_calmar_mean']:.4f}",
            f"{summary['b_oos_calmar_mean']:.4f}",
        ],
        [
            "CAGR 우위 (윈도우)",
            str(summary["a_wins_cagr"]),
            str(summary["b_wins_cagr"]),
        ],
        [
            "Calmar 우위 (윈도우)",
            str(summary["a_wins_calmar"]),
            str(summary["b_wins_calmar"]),
        ],
    ]

    table = TableLogger(columns, logger)
    table.print_table(rows, title="ATR 비교 실험 결과")

    # 차이 통계 출력
    diff_columns = [
        ("차이 통계 (A - B)", 25, Align.LEFT),
        ("값", 15, Align.RIGHT),
    ]
    diff_rows = [
        ["CAGR 차이 평균", f"{summary['diff_cagr_mean']:.2f}%p"],
        ["CAGR 차이 중앙값", f"{summary['diff_cagr_median']:.2f}%p"],
        ["Calmar 차이 평균", f"{summary['diff_calmar_mean']:.4f}"],
        ["Calmar 차이 중앙값", f"{summary['diff_calmar_median']:.4f}"],
    ]

    diff_table = TableLogger(diff_columns, logger)
    diff_table.print_table(diff_rows, title="차이 통계 (A - B)")


# JSON 반올림 규칙
_PCT_KEYS = {
    "a_stitched_cagr",
    "a_stitched_mdd",
    "a_stitched_total_return_pct",
    "b_stitched_cagr",
    "b_stitched_mdd",
    "b_stitched_total_return_pct",
    "a_oos_cagr_mean",
    "b_oos_cagr_mean",
    "diff_cagr_mean",
    "diff_cagr_median",
}

_RATIO_KEYS = {
    "a_stitched_calmar",
    "b_stitched_calmar",
    "a_oos_calmar_mean",
    "b_oos_calmar_mean",
    "diff_calmar_mean",
    "diff_calmar_median",
}


def _round_summary_for_json(summary: dict[str, object]) -> dict[str, object]:
    """요약 통계를 JSON 저장용 반올림 규칙에 맞게 변환한다."""
    result: dict[str, object] = {}
    for key, value in summary.items():
        if key in _PCT_KEYS and isinstance(value, int | float):
            result[key] = round(float(value), 2)
        elif key in _RATIO_KEYS and isinstance(value, int | float):
            result[key] = round(float(value), 4)
        else:
            result[key] = value
    return result


@cli_exception_handler
def main() -> int:
    """메인 실행 함수."""
    total_start = time.time()

    logger.debug("=" * 60)
    logger.debug("ATR 비교 실험 시작: ATR(14,3.0) vs ATR(22,3.0)")

    # 1. 데이터 로딩
    signal_df = load_stock_data(QQQ_DATA_PATH)
    trade_df = load_stock_data(TQQQ_SYNTHETIC_DATA_PATH)
    signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    logger.debug(f"데이터 로딩 완료: {signal_df[COL_DATE].min()} ~ " f"{signal_df[COL_DATE].max()}, {len(signal_df)}행")

    # 2. ATR(14,3.0) WFO 실행
    logger.debug("-" * 40)
    logger.debug(f"[A] ATR({ATR_CONFIG_A_PERIOD}, {ATR_CONFIG_A_MULTIPLIER}) 실행")
    config_a_start = time.time()
    config_a = run_single_atr_config(
        signal_df=signal_df,
        trade_df=trade_df,
        atr_period=ATR_CONFIG_A_PERIOD,
        atr_multiplier=ATR_CONFIG_A_MULTIPLIER,
        initial_is_months=DEFAULT_WFO_INITIAL_IS_MONTHS,
        oos_months=DEFAULT_WFO_OOS_MONTHS,
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window_list=list(DEFAULT_WFO_MA_WINDOW_LIST),
        buy_buffer_zone_pct_list=list(DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST),
        sell_buffer_zone_pct_list=list(DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST),
        hold_days_list=list(DEFAULT_WFO_HOLD_DAYS_LIST),
        recent_months_list=list(DEFAULT_WFO_RECENT_MONTHS_LIST),
    )
    logger.debug(f"[A] 완료: {time.time() - config_a_start:.1f}초")

    # 3. ATR(22,3.0) WFO 실행
    logger.debug("-" * 40)
    logger.debug(f"[B] ATR({ATR_CONFIG_B_PERIOD}, {ATR_CONFIG_B_MULTIPLIER}) 실행")
    config_b_start = time.time()
    config_b = run_single_atr_config(
        signal_df=signal_df,
        trade_df=trade_df,
        atr_period=ATR_CONFIG_B_PERIOD,
        atr_multiplier=ATR_CONFIG_B_MULTIPLIER,
        initial_is_months=DEFAULT_WFO_INITIAL_IS_MONTHS,
        oos_months=DEFAULT_WFO_OOS_MONTHS,
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window_list=list(DEFAULT_WFO_MA_WINDOW_LIST),
        buy_buffer_zone_pct_list=list(DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST),
        sell_buffer_zone_pct_list=list(DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST),
        hold_days_list=list(DEFAULT_WFO_HOLD_DAYS_LIST),
        recent_months_list=list(DEFAULT_WFO_RECENT_MONTHS_LIST),
    )
    logger.debug(f"[B] 완료: {time.time() - config_b_start:.1f}초")

    # 4. 윈도우별 비교 + 요약 생성
    logger.debug("-" * 40)
    comparison_df = build_window_comparison(config_a, config_b)
    summary = build_comparison_summary(config_a, config_b, comparison_df)

    # 5. 결과 출력
    _print_comparison_summary(summary)

    # 6. 결과 저장
    result_dir = BUFFER_ZONE_ATR_TQQQ_RESULTS_DIR
    result_dir.mkdir(parents=True, exist_ok=True)

    # 윈도우별 비교 CSV 저장 (반올림 규칙 적용)
    round_cols: dict[str, int] = {}
    for col in comparison_df.columns:
        if "cagr" in col or "mdd" in col or "win_rate" in col:
            round_cols[col] = 2
        elif "calmar" in col:
            round_cols[col] = 4
    if round_cols:
        comparison_df = comparison_df.round(round_cols)
    comparison_df.to_csv(result_dir / ATR_COMPARISON_WINDOWS_FILENAME, index=False)
    logger.debug(f"윈도우별 비교 CSV 저장: {result_dir / ATR_COMPARISON_WINDOWS_FILENAME}")

    # 요약 JSON 저장 (반올림 규칙 적용)
    rounded_summary = _round_summary_for_json(summary)
    summary_path = result_dir / ATR_COMPARISON_SUMMARY_FILENAME
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(rounded_summary, f, indent=2, ensure_ascii=False, default=str)
    logger.debug(f"요약 JSON 저장: {summary_path}")

    # 7. 메타데이터 저장
    total_elapsed = time.time() - total_start
    metadata = {
        "experiment": "ATR OOS 비교",
        "config_a": {
            "atr_period": ATR_CONFIG_A_PERIOD,
            "atr_multiplier": ATR_CONFIG_A_MULTIPLIER,
        },
        "config_b": {
            "atr_period": ATR_CONFIG_B_PERIOD,
            "atr_multiplier": ATR_CONFIG_B_MULTIPLIER,
        },
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
        },
        "data_period": {
            "start_date": str(signal_df[COL_DATE].min()),
            "end_date": str(signal_df[COL_DATE].max()),
            "total_days": len(signal_df),
        },
        "results_summary": {
            "n_windows": summary["n_windows"],
            "a_stitched_cagr": round(float(summary["a_stitched_cagr"]), 2),  # type: ignore[arg-type]
            "b_stitched_cagr": round(float(summary["b_stitched_cagr"]), 2),  # type: ignore[arg-type]
            "a_wins_cagr": summary["a_wins_cagr"],
            "b_wins_cagr": summary["b_wins_cagr"],
        },
        "elapsed_seconds": round(total_elapsed, 1),
    }
    save_metadata("atr_comparison", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")
    logger.debug(f"전체 소요 시간: {total_elapsed:.1f}초")

    return 0


if __name__ == "__main__":
    sys.exit(main())
