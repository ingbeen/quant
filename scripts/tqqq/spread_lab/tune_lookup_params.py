"""
룩업테이블 스프레드 모델 인샘플 최적화 스크립트

전체기간 데이터로 실현 스프레드를 역산한 뒤,
구간 폭(0.5%, 1.0%, 2.0%) × 통계량(mean, median) 6가지 조합을 평가하여
최적 조합을 선정한다.

실행 명령어:
    poetry run python scripts/tqqq/spread_lab/tune_lookup_params.py
"""

import sys
import time

import pandas as pd

from qbt.common_constants import QQQ_DATA_PATH
from qbt.tqqq.constants import (
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_LOOKUP_BIN_WIDTHS,
    DEFAULT_LOOKUP_STAT_FUNCS,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    LOOKUP_TUNING_CSV_PATH,
    SPREAD_LAB_DIR,
    TQQQ_DATA_PATH,
)
from qbt.tqqq.data_loader import load_expense_ratio_data, load_ffr_data
from qbt.tqqq.lookup_spread import calculate_realized_spread, evaluate_lookup_combination
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """룩업테이블 스프레드 모델 인샘플 최적화 메인 함수"""
    start_time = time.time()

    # 1. 데이터 로딩
    logger.debug("데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)

    logger.debug(f"QQQ: {len(qqq_df)}행, TQQQ: {len(tqqq_df)}행")
    logger.debug(f"FFR: {len(ffr_df)}행, Expense: {len(expense_df)}행")

    # 2. 실현 스프레드 역산
    logger.debug("실현 스프레드 역산 시작")
    realized_df = calculate_realized_spread(
        qqq_df=qqq_df,
        tqqq_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
    )
    logger.debug(f"실현 스프레드 산출: {len(realized_df)}일")

    # 3. 6가지 조합 평가
    logger.debug("조합별 인샘플 RMSE 평가 시작")
    results: list[dict[str, object]] = []

    for bin_width in DEFAULT_LOOKUP_BIN_WIDTHS:
        for stat_func in DEFAULT_LOOKUP_STAT_FUNCS:
            logger.debug(f"평가 중: bin_width={bin_width}%, stat_func={stat_func}")

            result = evaluate_lookup_combination(
                realized_df=realized_df,
                bin_width_pct=bin_width,
                stat_func=stat_func,
                ffr_df=ffr_df,
                expense_df=expense_df,
                underlying_df=qqq_df,
                actual_df=tqqq_df,
                leverage=DEFAULT_LEVERAGE_MULTIPLIER,
            )
            results.append(result)

            logger.debug(f"  -> RMSE={result['rmse_pct']:.4f}%, " f"n_bins={result['n_bins']}")

    # 4. 결과 정렬 (RMSE 기준 오름차순)
    results_df = pd.DataFrame(results).sort_values("rmse_pct").reset_index(drop=True)

    # 5. 최적 조합 출력
    best = results_df.iloc[0]
    logger.debug("=== 인샘플 최적화 결과 ===")
    for _, row in results_df.iterrows():
        marker = " *" if row["bin_width_pct"] == best["bin_width_pct"] and row["stat_func"] == best["stat_func"] else ""
        logger.debug(
            f"  bin_width={row['bin_width_pct']}%, "
            f"stat={row['stat_func']}, "
            f"RMSE={row['rmse_pct']:.4f}%, "
            f"n_bins={row['n_bins']}{marker}"
        )
    logger.debug(
        f"최적: bin_width={best['bin_width_pct']}%, " f"stat={best['stat_func']}, " f"RMSE={best['rmse_pct']:.4f}%"
    )

    # 6. CSV 저장
    SPREAD_LAB_DIR.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(LOOKUP_TUNING_CSV_PATH, index=False, encoding="utf-8-sig")
    logger.debug(f"결과 저장: {LOOKUP_TUNING_CSV_PATH}")

    # 7. 메타데이터 저장
    elapsed = time.time() - start_time
    metadata = {
        "model_type": "lookup_table",
        "bin_widths_tested": list(DEFAULT_LOOKUP_BIN_WIDTHS),
        "stat_funcs_tested": list(DEFAULT_LOOKUP_STAT_FUNCS),
        "n_combinations": len(results),
        "best_bin_width_pct": float(best["bin_width_pct"]),
        "best_stat_func": str(best["stat_func"]),
        "best_rmse_pct": float(best["rmse_pct"]),
        "best_n_bins": int(best["n_bins"]),
        "n_realized_spread_days": len(realized_df),
        "elapsed_time_sec": round(elapsed, 1),
        "input_files": {
            "qqq": str(QQQ_DATA_PATH),
            "tqqq": str(TQQQ_DATA_PATH),
            "ffr": str(FFR_DATA_PATH),
            "expense": str(EXPENSE_RATIO_DATA_PATH),
        },
        "output_files": {
            "tuning_csv": str(LOOKUP_TUNING_CSV_PATH),
        },
    }
    save_metadata("tqqq_lookup_tuning", metadata)

    logger.debug(f"완료 (소요시간: {elapsed:.1f}초)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
