"""
b 고정 워크포워드 검증 스크립트

전체기간 최적 b를 고정하고 a만 워크포워드 최적화하여 과최적화 진단을 지원한다.
60개월 Train, 1개월 Test 워크포워드 검증을 수행하여 CSV로 저장한다.

사전 준비:
    poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py

실행 명령어:
    poetry run python scripts/tqqq/spread_lab/validate_walkforward_fixed_b.py
"""

import sys
import time

import pandas as pd

from qbt.common_constants import META_JSON_PATH, QQQ_DATA_PATH
from qbt.tqqq.analysis_helpers import save_walkforward_results, save_walkforward_summary
from qbt.tqqq.constants import (
    COL_B,
    DEFAULT_TRAIN_WINDOW_MONTHS,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    SOFTPLUS_TUNING_CSV_PATH,
    SPREAD_LAB_DIR,
    TQQQ_DATA_PATH,
    TQQQ_WALKFORWARD_FIXED_B_PATH,
    TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH,
)
from qbt.tqqq.data_loader import load_expense_ratio_data, load_ffr_data
from qbt.tqqq.walkforward import calculate_stitched_walkforward_rmse, run_walkforward_validation
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 전체기간 최적 b 값 로드
    if not SOFTPLUS_TUNING_CSV_PATH.exists():
        raise FileNotFoundError(
            f"튜닝 결과 CSV가 없습니다: {SOFTPLUS_TUNING_CSV_PATH}\n"
            f"먼저 실행: poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py"
        )

    tuning_df = pd.read_csv(SOFTPLUS_TUNING_CSV_PATH)
    b_global = float(tuning_df.iloc[0][COL_B])
    logger.debug(f"전체기간 최적 b 값 로드: {b_global:.4f}")

    # 2. 데이터 로드
    logger.debug("QQQ, TQQQ, FFR 및 Expense Ratio 데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)

    # 3. 워크포워드 검증 정보 출력
    logger.debug("=" * 80)
    logger.debug("b 고정 워크포워드 검증 (a만 최적화)")
    logger.debug("=" * 80)
    logger.debug(f"학습 기간: {DEFAULT_TRAIN_WINDOW_MONTHS}개월 (5년)")
    logger.debug("테스트 기간: 1개월")
    logger.debug(f"고정 b 값: {b_global:.4f} (전체기간 튜닝 결과)")
    logger.debug("-" * 80)

    # 4. 워크포워드 검증 실행
    logger.debug("b 고정 워크포워드 검증 시작...")
    start_time = time.perf_counter()

    result_df, summary = run_walkforward_validation(
        underlying_df=qqq_df,
        actual_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
        train_window_months=DEFAULT_TRAIN_WINDOW_MONTHS,
        fixed_b=b_global,
    )

    elapsed_time = time.perf_counter() - start_time
    logger.debug(f"b 고정 워크포워드 검증 완료: 소요시간 {elapsed_time:.2f}초")
    logger.debug("-" * 80)

    # 5. 연속(stitched) 워크포워드 RMSE 계산
    logger.debug("연속 워크포워드 RMSE 계산 시작...")
    stitched_rmse = calculate_stitched_walkforward_rmse(
        walkforward_result_df=result_df,
        underlying_df=qqq_df,
        actual_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
    )
    summary["stitched_rmse"] = stitched_rmse
    logger.debug(f"연속 워크포워드 RMSE: {stitched_rmse:.4f}%")

    # 6. 결과 요약 출력
    logger.debug("b 고정 워크포워드 검증 결과 요약:")
    logger.debug(f"  고정 b 값: {b_global:.4f}")
    logger.debug(f"  테스트 월 수: {summary['n_test_months']}개월")
    logger.debug(f"  테스트 RMSE 평균: {summary['test_rmse_mean']:.4f}%")
    logger.debug(f"  테스트 RMSE 중앙값: {summary['test_rmse_median']:.4f}%")
    logger.debug(f"  테스트 RMSE 표준편차: {summary['test_rmse_std']:.4f}%")
    logger.debug(f"  테스트 RMSE 범위: [{summary['test_rmse_min']:.4f}%, {summary['test_rmse_max']:.4f}%]")
    logger.debug(f"  연속 워크포워드 RMSE: {stitched_rmse:.4f}%")
    logger.debug(f"  a 평균 (std): {summary['a_mean']:.4f} ({summary['a_std']:.4f})")
    logger.debug(f"  b 평균 (std): {summary['b_mean']:.4f} ({summary['b_std']:.4f})")
    logger.debug("-" * 80)

    # 7. CSV 저장
    SPREAD_LAB_DIR.mkdir(parents=True, exist_ok=True)

    save_walkforward_results(result_df, TQQQ_WALKFORWARD_FIXED_B_PATH)
    logger.debug(f"워크포워드 결과 저장: {TQQQ_WALKFORWARD_FIXED_B_PATH} ({len(result_df)}행)")

    save_walkforward_summary(summary, TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH)
    logger.debug(f"워크포워드 요약 저장: {TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH}")

    # 8. 메타데이터 저장
    metadata = {
        "funding_spread_mode": "softplus_ffr_monthly",
        "b_mode": "fixed",
        "b_fixed_value": round(b_global, 4),
        "b_source": "global_tuning",
        "walkforward_settings": {
            "train_window_months": DEFAULT_TRAIN_WINDOW_MONTHS,
            "test_step_months": 1,
            "test_month_ffr_usage": "same_month",
        },
        "summary": {
            "test_rmse_mean": round(summary["test_rmse_mean"], 4),
            "test_rmse_median": round(summary["test_rmse_median"], 4),
            "test_rmse_std": round(summary["test_rmse_std"], 4),
            "test_rmse_min": round(summary["test_rmse_min"], 4),
            "test_rmse_max": round(summary["test_rmse_max"], 4),
            "a_mean": round(summary["a_mean"], 4),
            "a_std": round(summary["a_std"], 4),
            "b_mean": round(summary["b_mean"], 4),
            "b_std": round(summary["b_std"], 4),
            "n_test_months": summary["n_test_months"],
            "stitched_rmse": round(stitched_rmse, 4),
        },
        "elapsed_time_sec": round(elapsed_time, 2),
        "input_files": {
            "qqq_data": str(QQQ_DATA_PATH),
            "tqqq_data": str(TQQQ_DATA_PATH),
            "ffr_data": str(FFR_DATA_PATH),
            "expense_data": str(EXPENSE_RATIO_DATA_PATH),
            "tuning_csv": str(SOFTPLUS_TUNING_CSV_PATH),
        },
        "output_files": {
            "walkforward_csv": str(TQQQ_WALKFORWARD_FIXED_B_PATH),
            "walkforward_summary_csv": str(TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH),
        },
    }

    save_metadata("tqqq_walkforward_fixed_b", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
