"""
Expanding vs Rolling WFO 비교 실험 스크립트

동일 OOS 기간에서 Expanding Anchored WFO와 Rolling Window WFO의
성과 차이를 측정합니다. Rolling IS=120개월(10년)로 고정하여
위기 데이터 망각 위험을 정량적으로 검증합니다.

실행 명령어:
    poetry run python scripts/backtest/run_wfo_comparison.py
"""

import json
import sys
import time

from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_WFO_ATR_MULTIPLIER_LIST,
    DEFAULT_WFO_ATR_PERIOD_LIST,
    DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST,
    DEFAULT_WFO_HOLD_DAYS_LIST,
    DEFAULT_WFO_INITIAL_IS_MONTHS,
    DEFAULT_WFO_MA_WINDOW_LIST,
    DEFAULT_WFO_OOS_MONTHS,
    DEFAULT_WFO_RECENT_MONTHS_LIST,
    DEFAULT_WFO_ROLLING_IS_MONTHS,
    DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST,
    SLIPPAGE_RATE,
    WFO_COMPARISON_SUMMARY_FILENAME,
    WFO_COMPARISON_WINDOWS_FILENAME,
)
from qbt.backtest.wfo_comparison import (
    build_comparison_summary,
    build_window_comparison,
    run_single_wfo_mode,
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


def _print_comparison_summary(summary: dict[str, object]) -> None:
    """비교 요약을 테이블로 출력한다."""
    columns = [
        ("항목", 30, Align.LEFT),
        ("Expanding", 15, Align.RIGHT),
        ("Rolling", 15, Align.RIGHT),
    ]
    rows = [
        [
            "Stitched CAGR",
            f"{summary['exp_stitched_cagr']:.2f}%",
            f"{summary['roll_stitched_cagr']:.2f}%",
        ],
        [
            "Stitched MDD",
            f"{summary['exp_stitched_mdd']:.2f}%",
            f"{summary['roll_stitched_mdd']:.2f}%",
        ],
        [
            "Stitched Calmar",
            f"{summary['exp_stitched_calmar']:.4f}",
            f"{summary['roll_stitched_calmar']:.4f}",
        ],
        [
            "OOS CAGR 평균",
            f"{summary['exp_oos_cagr_mean']:.2f}%",
            f"{summary['roll_oos_cagr_mean']:.2f}%",
        ],
        [
            "OOS Calmar 평균",
            f"{summary['exp_oos_calmar_mean']:.4f}",
            f"{summary['roll_oos_calmar_mean']:.4f}",
        ],
        [
            "CAGR 우위 (윈도우)",
            str(summary["exp_wins_cagr"]),
            str(summary["roll_wins_cagr"]),
        ],
        [
            "Calmar 우위 (윈도우)",
            str(summary["exp_wins_calmar"]),
            str(summary["roll_wins_calmar"]),
        ],
    ]

    table = TableLogger(columns, logger)
    table.print_table(rows, title="Expanding vs Rolling WFO 비교 결과")

    # IS 분기 통계 출력
    info_columns = [
        ("IS 분기 통계", 30, Align.LEFT),
        ("값", 15, Align.RIGHT),
    ]
    info_rows = [
        ["Rolling IS 최대 길이", f"{summary['rolling_is_months']}개월"],
        ["전체 윈도우 수", str(summary["n_windows"])],
        ["IS 동일 윈도우 수", str(summary["n_identical"])],
        ["IS 분기 윈도우 수", str(summary["n_diverged"])],
    ]

    info_table = TableLogger(info_columns, logger)
    info_table.print_table(info_rows, title="IS 분기 통계")

    # 차이 통계 출력
    diff_columns = [
        ("차이 통계 (Exp - Roll)", 30, Align.LEFT),
        ("값", 15, Align.RIGHT),
    ]
    diff_rows = [
        ["CAGR 차이 평균 (전체)", f"{summary['diff_cagr_mean']:.2f}%p"],
        ["CAGR 차이 중앙값 (전체)", f"{summary['diff_cagr_median']:.2f}%p"],
        ["Calmar 차이 평균 (전체)", f"{summary['diff_calmar_mean']:.4f}"],
        ["Calmar 차이 중앙값 (전체)", f"{summary['diff_calmar_median']:.4f}"],
        ["CAGR 차이 평균 (분기)", f"{summary['diverged_diff_cagr_mean']:.2f}%p"],
        ["CAGR 차이 중앙값 (분기)", f"{summary['diverged_diff_cagr_median']:.2f}%p"],
        ["Calmar 차이 평균 (분기)", f"{summary['diverged_diff_calmar_mean']:.4f}"],
        ["Calmar 차이 중앙값 (분기)", f"{summary['diverged_diff_calmar_median']:.4f}"],
    ]

    diff_table = TableLogger(diff_columns, logger)
    diff_table.print_table(diff_rows, title="차이 통계 (Expanding - Rolling)")


# JSON 반올림 규칙
_PCT_KEYS = {
    "exp_stitched_cagr",
    "exp_stitched_mdd",
    "exp_stitched_total_return_pct",
    "roll_stitched_cagr",
    "roll_stitched_mdd",
    "roll_stitched_total_return_pct",
    "exp_oos_cagr_mean",
    "roll_oos_cagr_mean",
    "diff_cagr_mean",
    "diff_cagr_median",
    "diverged_diff_cagr_mean",
    "diverged_diff_cagr_median",
}

_RATIO_KEYS = {
    "exp_stitched_calmar",
    "roll_stitched_calmar",
    "exp_oos_calmar_mean",
    "roll_oos_calmar_mean",
    "diff_calmar_mean",
    "diff_calmar_median",
    "diverged_diff_calmar_mean",
    "diverged_diff_calmar_median",
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
    logger.debug(f"Expanding vs Rolling WFO 비교 실험 시작 (Rolling IS={DEFAULT_WFO_ROLLING_IS_MONTHS}개월)")

    # 1. 데이터 로딩
    signal_df = load_stock_data(QQQ_DATA_PATH)
    trade_df = load_stock_data(TQQQ_SYNTHETIC_DATA_PATH)
    signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    logger.debug(f"데이터 로딩 완료: {signal_df[COL_DATE].min()} ~ " f"{signal_df[COL_DATE].max()}, {len(signal_df)}행")

    # 공통 파라미터
    ma_window_list = list(DEFAULT_WFO_MA_WINDOW_LIST)
    buy_buffer_zone_pct_list = list(DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST)
    sell_buffer_zone_pct_list = list(DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST)
    hold_days_list = list(DEFAULT_WFO_HOLD_DAYS_LIST)
    recent_months_list = list(DEFAULT_WFO_RECENT_MONTHS_LIST)
    atr_period_list = list(DEFAULT_WFO_ATR_PERIOD_LIST)
    atr_multiplier_list = list(DEFAULT_WFO_ATR_MULTIPLIER_LIST)

    # 2. Expanding WFO Dynamic 실행
    logger.debug("-" * 40)
    logger.debug("[Expanding] WFO Dynamic 실행")
    exp_start = time.time()
    expanding = run_single_wfo_mode(
        signal_df=signal_df,
        trade_df=trade_df,
        rolling_is_months=None,
        initial_is_months=DEFAULT_WFO_INITIAL_IS_MONTHS,
        oos_months=DEFAULT_WFO_OOS_MONTHS,
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window_list=ma_window_list,
        buy_buffer_zone_pct_list=buy_buffer_zone_pct_list,
        sell_buffer_zone_pct_list=sell_buffer_zone_pct_list,
        hold_days_list=hold_days_list,
        recent_months_list=recent_months_list,
        atr_period_list=atr_period_list,
        atr_multiplier_list=atr_multiplier_list,
    )
    logger.debug(f"[Expanding] 완료: {time.time() - exp_start:.1f}초")

    # 3. Rolling WFO Dynamic 실행
    logger.debug("-" * 40)
    logger.debug(f"[Rolling] WFO Dynamic 실행 (IS={DEFAULT_WFO_ROLLING_IS_MONTHS}개월)")
    roll_start = time.time()
    rolling = run_single_wfo_mode(
        signal_df=signal_df,
        trade_df=trade_df,
        rolling_is_months=DEFAULT_WFO_ROLLING_IS_MONTHS,
        initial_is_months=DEFAULT_WFO_INITIAL_IS_MONTHS,
        oos_months=DEFAULT_WFO_OOS_MONTHS,
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window_list=ma_window_list,
        buy_buffer_zone_pct_list=buy_buffer_zone_pct_list,
        sell_buffer_zone_pct_list=sell_buffer_zone_pct_list,
        hold_days_list=hold_days_list,
        recent_months_list=recent_months_list,
        atr_period_list=atr_period_list,
        atr_multiplier_list=atr_multiplier_list,
    )
    logger.debug(f"[Rolling] 완료: {time.time() - roll_start:.1f}초")

    # 4. 윈도우별 비교 + 요약 생성
    logger.debug("-" * 40)
    comparison_df = build_window_comparison(expanding, rolling)
    summary = build_comparison_summary(expanding, rolling, comparison_df)

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
    comparison_df.to_csv(result_dir / WFO_COMPARISON_WINDOWS_FILENAME, index=False)
    logger.debug(f"윈도우별 비교 CSV 저장: {result_dir / WFO_COMPARISON_WINDOWS_FILENAME}")

    # 요약 JSON 저장 (반올림 규칙 적용)
    rounded_summary = _round_summary_for_json(summary)
    summary_path = result_dir / WFO_COMPARISON_SUMMARY_FILENAME
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(rounded_summary, f, indent=2, ensure_ascii=False, default=str)
    logger.debug(f"요약 JSON 저장: {summary_path}")

    # 7. 메타데이터 저장
    total_elapsed = time.time() - total_start
    metadata = {
        "experiment": "Expanding vs Rolling WFO 비교",
        "rolling_is_months": DEFAULT_WFO_ROLLING_IS_MONTHS,
        "execution_params": {
            "initial_is_months": DEFAULT_WFO_INITIAL_IS_MONTHS,
            "oos_months": DEFAULT_WFO_OOS_MONTHS,
            "ma_window_list": list(DEFAULT_WFO_MA_WINDOW_LIST),
            "buy_buffer_zone_pct_list": [round(x, 4) for x in DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST],
            "sell_buffer_zone_pct_list": [round(x, 4) for x in DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST],
            "hold_days_list": list(DEFAULT_WFO_HOLD_DAYS_LIST),
            "recent_months_list": list(DEFAULT_WFO_RECENT_MONTHS_LIST),
            "atr_period_list": list(DEFAULT_WFO_ATR_PERIOD_LIST),
            "atr_multiplier_list": list(DEFAULT_WFO_ATR_MULTIPLIER_LIST),
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
            "n_identical": summary["n_identical"],
            "n_diverged": summary["n_diverged"],
            "exp_stitched_cagr": round(float(summary["exp_stitched_cagr"]), 2),  # type: ignore[arg-type]
            "roll_stitched_cagr": round(float(summary["roll_stitched_cagr"]), 2),  # type: ignore[arg-type]
            "exp_wins_cagr": summary["exp_wins_cagr"],
            "roll_wins_cagr": summary["roll_wins_cagr"],
        },
        "elapsed_seconds": round(total_elapsed, 1),
    }
    save_metadata("wfo_comparison", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")
    logger.debug(f"전체 소요 시간: {total_elapsed:.1f}초")

    return 0


if __name__ == "__main__":
    sys.exit(main())
