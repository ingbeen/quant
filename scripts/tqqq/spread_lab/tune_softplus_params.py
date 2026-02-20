"""
Softplus 동적 스프레드 모델 파라미터 튜닝 스크립트

2-Stage Grid Search로 최적 (a, b) 파라미터를 탐색하여 CSV로 저장한다.
Streamlit 앱에서 분리하여 spawn 경고 없이 실행 가능하다.

실행 명령어:
    poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py
"""

import sys
import time
from typing import Any

import pandas as pd

from qbt.common_constants import META_JSON_PATH, QQQ_DATA_PATH
from qbt.tqqq.analysis_helpers import save_static_spread_series
from qbt.tqqq.constants import (
    COL_A,
    COL_B,
    COL_RMSE_PCT,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    SOFTPLUS_GRID_STAGE1_A_RANGE,
    SOFTPLUS_GRID_STAGE1_A_STEP,
    SOFTPLUS_GRID_STAGE1_B_RANGE,
    SOFTPLUS_GRID_STAGE1_B_STEP,
    SOFTPLUS_GRID_STAGE2_A_DELTA,
    SOFTPLUS_GRID_STAGE2_A_STEP,
    SOFTPLUS_GRID_STAGE2_B_DELTA,
    SOFTPLUS_GRID_STAGE2_B_STEP,
    SOFTPLUS_SPREAD_SERIES_STATIC_PATH,
    SOFTPLUS_TUNING_CSV_PATH,
    SPREAD_LAB_DIR,
    TQQQ_DATA_PATH,
)
from qbt.tqqq.data_loader import load_expense_ratio_data, load_ffr_data
from qbt.tqqq.optimization import find_optimal_softplus_params
from qbt.tqqq.simulation import generate_static_spread_series
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import extract_overlap_period, load_stock_data
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 데이터 로드
    logger.debug("QQQ, TQQQ, FFR 및 Expense Ratio 데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)

    # 2. 그리드 서치 정보 출력
    a_count_s1 = (
        int((SOFTPLUS_GRID_STAGE1_A_RANGE[1] - SOFTPLUS_GRID_STAGE1_A_RANGE[0]) / SOFTPLUS_GRID_STAGE1_A_STEP) + 1
    )
    b_count_s1 = (
        int((SOFTPLUS_GRID_STAGE1_B_RANGE[1] - SOFTPLUS_GRID_STAGE1_B_RANGE[0]) / SOFTPLUS_GRID_STAGE1_B_STEP) + 1
    )
    total_s1 = a_count_s1 * b_count_s1

    a_count_s2 = int(2 * SOFTPLUS_GRID_STAGE2_A_DELTA / SOFTPLUS_GRID_STAGE2_A_STEP) + 1
    b_count_s2 = int(2 * SOFTPLUS_GRID_STAGE2_B_DELTA / SOFTPLUS_GRID_STAGE2_B_STEP) + 1
    total_s2 = a_count_s2 * b_count_s2

    logger.debug("=" * 80)
    logger.debug("Softplus 동적 스프레드 모델 파라미터 튜닝")
    logger.debug("=" * 80)
    logger.debug(
        f"Stage 1: a=[{SOFTPLUS_GRID_STAGE1_A_RANGE[0]}, {SOFTPLUS_GRID_STAGE1_A_RANGE[1]}] "
        f"step={SOFTPLUS_GRID_STAGE1_A_STEP}, "
        f"b=[{SOFTPLUS_GRID_STAGE1_B_RANGE[0]}, {SOFTPLUS_GRID_STAGE1_B_RANGE[1]}] "
        f"step={SOFTPLUS_GRID_STAGE1_B_STEP} -> {total_s1}개 조합"
    )
    logger.debug(
        f"Stage 2: a_delta={SOFTPLUS_GRID_STAGE2_A_DELTA} step={SOFTPLUS_GRID_STAGE2_A_STEP}, "
        f"b_delta={SOFTPLUS_GRID_STAGE2_B_DELTA} step={SOFTPLUS_GRID_STAGE2_B_STEP} -> {total_s2}개 조합"
    )
    logger.debug(f"총 탐색 조합: {total_s1 + total_s2}개")
    logger.debug("-" * 80)

    # 3. 튜닝 실행
    logger.debug("2-Stage Grid Search 시작...")
    start_time = time.perf_counter()

    a_best, b_best, best_rmse, all_candidates = find_optimal_softplus_params(
        underlying_df=qqq_df,
        actual_leveraged_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
    )

    elapsed_time = time.perf_counter() - start_time
    logger.debug(f"튜닝 완료: 소요시간 {elapsed_time:.2f}초")
    logger.debug("-" * 80)

    # 4. 결과 출력
    logger.debug("최적 파라미터:")
    logger.debug(f"  a = {a_best:.4f}")
    logger.debug(f"  b = {b_best:.4f}")
    logger.debug(f"  RMSE = {best_rmse:.4f}%")
    logger.debug("-" * 80)

    # 5. 상위 10개 결과 출력
    candidates_sorted = sorted(all_candidates, key=lambda x: x[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE])
    top_10 = candidates_sorted[:10]

    logger.debug("상위 10개 후보:")
    for i, candidate in enumerate(top_10, start=1):
        logger.debug(
            f"  {i:2d}. a={candidate['a']:.4f}, b={candidate['b']:.4f}, "
            f"RMSE={candidate[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]:.4f}%"
        )

    # 6. CSV 저장
    SPREAD_LAB_DIR.mkdir(parents=True, exist_ok=True)

    csv_rows: list[dict[str, Any]] = []
    for candidate in candidates_sorted:
        csv_row = {
            COL_A: round(candidate["a"], 4),
            COL_B: round(candidate["b"], 4),
            COL_RMSE_PCT: round(candidate[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE], 4),
        }
        csv_rows.append(csv_row)

    results_df = pd.DataFrame(csv_rows)
    results_df.to_csv(SOFTPLUS_TUNING_CSV_PATH, index=False, encoding="utf-8-sig")
    logger.debug(f"튜닝 결과 저장: {SOFTPLUS_TUNING_CSV_PATH} ({len(csv_rows)}행)")

    # 7. 정적 spread 시계열 CSV 생성
    # 기초자산 overlap 기간 추출
    overlap_underlying, _ = extract_overlap_period(qqq_df, tqqq_df)

    # 전체기간 최적 (a, b)로 월별 spread 시계열 생성
    static_spread_df = generate_static_spread_series(
        ffr_df=ffr_df,
        a=a_best,
        b=b_best,
        underlying_overlap_df=overlap_underlying,
    )

    # CSV 저장
    save_static_spread_series(static_spread_df, SOFTPLUS_SPREAD_SERIES_STATIC_PATH)
    logger.debug(f"정적 spread 시계열 저장: {SOFTPLUS_SPREAD_SERIES_STATIC_PATH} ({len(static_spread_df)}행)")

    # 8. 메타데이터 저장
    metadata = {
        "funding_spread_mode": "softplus_ffr_monthly",
        "softplus_a": round(a_best, 4),
        "softplus_b": round(b_best, 4),
        "ffr_scale": "pct",
        "objective": "cumul_multiple_log_diff_rmse_pct",
        "best_rmse_pct": round(best_rmse, 4),
        "elapsed_time_sec": round(elapsed_time, 2),
        "grid_settings": {
            "stage1": {
                "a_range": list(SOFTPLUS_GRID_STAGE1_A_RANGE),
                "a_step": SOFTPLUS_GRID_STAGE1_A_STEP,
                "b_range": list(SOFTPLUS_GRID_STAGE1_B_RANGE),
                "b_step": SOFTPLUS_GRID_STAGE1_B_STEP,
                "combinations": total_s1,
            },
            "stage2": {
                "a_delta": SOFTPLUS_GRID_STAGE2_A_DELTA,
                "a_step": SOFTPLUS_GRID_STAGE2_A_STEP,
                "b_delta": SOFTPLUS_GRID_STAGE2_B_DELTA,
                "b_step": SOFTPLUS_GRID_STAGE2_B_STEP,
                "combinations": total_s2,
            },
        },
        "input_files": {
            "qqq_data": str(QQQ_DATA_PATH),
            "tqqq_data": str(TQQQ_DATA_PATH),
            "ffr_data": str(FFR_DATA_PATH),
            "expense_data": str(EXPENSE_RATIO_DATA_PATH),
        },
        "csv_info": {
            "path": str(SOFTPLUS_TUNING_CSV_PATH),
            "row_count": len(csv_rows),
        },
        "static_spread_csv": {
            "path": str(SOFTPLUS_SPREAD_SERIES_STATIC_PATH),
            "row_count": len(static_spread_df),
        },
    }

    save_metadata("tqqq_softplus_tuning", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
