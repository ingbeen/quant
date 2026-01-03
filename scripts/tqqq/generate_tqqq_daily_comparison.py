"""
TQQQ 일별 비교 CSV 생성 스크립트

지정된 파라미터로 TQQQ를 시뮬레이션하고 실제 TQQQ 데이터와 일별로 비교하여
상세 검증 지표와 일별 비교 CSV를 생성한다.
모든 파라미터는 상수에서 정의됩니다.

실행 명령어:
    poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py
"""

import sys

import pandas as pd

from qbt.common_constants import COL_CLOSE, QQQ_DATA_PATH
from qbt.tqqq import calculate_validation_metrics, extract_overlap_period, simulate
from qbt.tqqq.constants import (
    COL_ACTUAL_CUMUL_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
    COL_CUMUL_MULTIPLE_LOG_DIFF_MAX,
    COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_SIMUL_CUMUL_RETURN,
    DEFAULT_FUNDING_SPREAD,
    DEFAULT_LEVERAGE_MULTIPLIER,
    DISPLAY_SPREAD,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    KEY_CUMULATIVE_RETURN_ACTUAL,
    KEY_CUMULATIVE_RETURN_SIMULATED,
    KEY_OVERLAP_DAYS,
    KEY_OVERLAP_END,
    KEY_OVERLAP_START,
    TQQQ_DAILY_COMPARISON_PATH,
    TQQQ_DATA_PATH,
)
from qbt.tqqq.data_loader import load_expense_ratio_data, load_ffr_data
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
    # 1. 데이터 로드
    logger.debug("QQQ, TQQQ, FFR 및 Expense Ratio 데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)

    # 2. 겹치는 기간 추출
    qqq_overlap, tqqq_overlap = extract_overlap_period(qqq_df, tqqq_df)

    # 3. 시뮬레이션 실행
    logger.debug(f"시뮬레이션 실행: leverage={DEFAULT_LEVERAGE_MULTIPLIER}, {DISPLAY_SPREAD}={DEFAULT_FUNDING_SPREAD:.4f}")

    initial_price = float(tqqq_overlap.iloc[0][COL_CLOSE])
    simulated_df = simulate(
        underlying_df=qqq_overlap,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
        initial_price=initial_price,
        ffr_df=ffr_df,
        expense_df=expense_df,
        funding_spread=DEFAULT_FUNDING_SPREAD,
    )

    logger.debug("시뮬레이션 완료")

    # 4. 검증 지표 계산 및 일별 비교 CSV 생성
    TQQQ_DAILY_COMPARISON_PATH.parent.mkdir(exist_ok=True, parents=True)
    logger.debug(f"검증 지표 계산 및 일별 비교 CSV 생성: {TQQQ_DAILY_COMPARISON_PATH}")
    validation_results = calculate_validation_metrics(
        simulated_df=simulated_df,
        actual_df=tqqq_overlap,
        output_path=TQQQ_DAILY_COMPARISON_PATH,
    )

    daily_df = pd.read_csv(TQQQ_DAILY_COMPARISON_PATH)
    logger.debug(f"일별 비교 CSV 저장 완료: {len(daily_df):,}행")

    # 5. 메타데이터 저장
    metadata = {
        "execution_params": {
            "leverage": round(DEFAULT_LEVERAGE_MULTIPLIER, 1),
            "funding_spread": round(DEFAULT_FUNDING_SPREAD, 4),
        },
        "overlap_period": {
            "start_date": str(validation_results[KEY_OVERLAP_START]),
            "end_date": str(validation_results[KEY_OVERLAP_END]),
            "total_days": int(validation_results[KEY_OVERLAP_DAYS]),
        },
        "validation_metrics": {
            "cumulative_return_actual_pct": round(validation_results[KEY_CUMULATIVE_RETURN_ACTUAL] * 100, 2),
            "cumulative_return_simulated_pct": round(validation_results[KEY_CUMULATIVE_RETURN_SIMULATED] * 100, 2),
            "cumul_multiple_log_diff_mean_pct": round(validation_results[KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN], 4),
            "cumul_multiple_log_diff_rmse_pct": round(validation_results[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE], 4),
            "cumul_multiple_log_diff_max_pct": round(validation_results[KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX], 4),
        },
        "daily_stats": {
            "daily_return_abs_diff": {
                "mean": round(daily_df[COL_DAILY_RETURN_ABS_DIFF].mean(), 4),
                "max": round(daily_df[COL_DAILY_RETURN_ABS_DIFF].max(), 4),
            },
            "cumul_multiple_log_diff": {
                "mean": round(daily_df[COL_CUMUL_MULTIPLE_LOG_DIFF_ABS].mean(), 4),
                "max": round(daily_df[COL_CUMUL_MULTIPLE_LOG_DIFF_ABS].max(), 4),
            },
        },
        "csv_info": {
            "path": str(TQQQ_DAILY_COMPARISON_PATH),
            "row_count": len(daily_df),
            "file_size_bytes": TQQQ_DAILY_COMPARISON_PATH.stat().st_size,
        },
    }

    save_metadata("tqqq_daily_comparison", metadata)
    logger.debug("메타데이터 저장 완료: storage/results/meta.json")

    # 6. 결과 출력 (터미널)
    logger.debug("=" * 64)
    logger.debug("TQQQ 시뮬레이션 검증")
    logger.debug("=" * 64)
    logger.debug(f"검증 기간: {validation_results[KEY_OVERLAP_START]} ~ {validation_results[KEY_OVERLAP_END]}")
    logger.debug(f"총 일수: {validation_results[KEY_OVERLAP_DAYS]:,}일")
    logger.debug(f"레버리지: {DEFAULT_LEVERAGE_MULTIPLIER:.1f}배")
    logger.debug(f"{DISPLAY_SPREAD}: {DEFAULT_FUNDING_SPREAD:.4f}")

    logger.debug("-" * 64)
    logger.debug("검증 지표")
    logger.debug("-" * 64)

    # 누적수익률 관련
    logger.debug(f"{COL_ACTUAL_CUMUL_RETURN}: +{validation_results[KEY_CUMULATIVE_RETURN_ACTUAL]*100:.1f}%")
    logger.debug(f"{COL_SIMUL_CUMUL_RETURN}: +{validation_results[KEY_CUMULATIVE_RETURN_SIMULATED]*100:.1f}%")
    logger.debug(f"{COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE}: {validation_results[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]:.4f}%")
    logger.debug(f"{COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN}: {validation_results[KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN]:.2f}%")
    logger.debug(f"{COL_CUMUL_MULTIPLE_LOG_DIFF_MAX}: {validation_results[KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX]:.4f}%")
    logger.debug(f"일일수익률_절대차이 평균: {daily_df[COL_DAILY_RETURN_ABS_DIFF].mean():.4f}%")
    logger.debug(f"일일수익률_절대차이 최대: {daily_df[COL_DAILY_RETURN_ABS_DIFF].max():.4f}%")

    logger.debug("-" * 64)

    logger.debug(f"일별 비교 CSV 저장 완료: {TQQQ_DAILY_COMPARISON_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
