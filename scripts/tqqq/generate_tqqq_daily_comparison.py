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

from qbt.common_constants import (
    COL_CLOSE,
    COL_CUMUL_MULTIPLE_LOG_DIFF,
    COL_DAILY_RETURN_ABS_DIFF,
    FFR_DATA_PATH,
    QQQ_DATA_PATH,
    TQQQ_DAILY_COMPARISON_PATH,
    TQQQ_DATA_PATH,
)
from qbt.tqqq import calculate_validation_metrics, extract_overlap_period, simulate
from qbt.tqqq.constants import DEFAULT_EXPENSE_RATIO, DEFAULT_FUNDING_SPREAD, DEFAULT_LEVERAGE_MULTIPLIER
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_ffr_data, load_stock_data
from qbt.utils.formatting import Align, TableLogger
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
    logger.debug("QQQ, TQQQ 및 FFR 데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)

    # 2. 겹치는 기간 추출 및 시뮬레이션 실행
    qqq_overlap, tqqq_overlap = extract_overlap_period(qqq_df, tqqq_df)

    # 3. 시뮬레이션 실행
    logger.debug(
        f"시뮬레이션 실행: leverage={DEFAULT_LEVERAGE_MULTIPLIER}, "
        f"funding_spread={DEFAULT_FUNDING_SPREAD:.4f}, "
        f"expense_ratio={DEFAULT_EXPENSE_RATIO*100:.2f}%"
    )

    initial_price = float(tqqq_overlap.iloc[0][COL_CLOSE])
    simulated_df = simulate(
        underlying_df=qqq_overlap,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
        expense_ratio=DEFAULT_EXPENSE_RATIO,
        initial_price=initial_price,
        ffr_df=ffr_df,
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
            "expense_ratio": round(DEFAULT_EXPENSE_RATIO, 6),
        },
        "overlap_period": {
            "start_date": str(validation_results["overlap_start"]),
            "end_date": str(validation_results["overlap_end"]),
            "total_days": int(validation_results["overlap_days"]),
        },
        "validation_metrics": {
            "cumulative_return_actual_pct": round(validation_results["cumulative_return_actual"] * 100, 2),
            "cumulative_return_simulated_pct": round(validation_results["cumulative_return_simulated"] * 100, 2),
            "cumul_multiple_log_diff_mean_pct": round(validation_results["cumul_multiple_log_diff_mean_pct"], 4),
            "cumul_multiple_log_diff_rmse_pct": round(validation_results["cumul_multiple_log_diff_rmse_pct"], 4),
            "cumul_multiple_log_diff_max_pct": round(validation_results["cumul_multiple_log_diff_max_pct"], 4),
        },
        "daily_stats": {
            "daily_return_abs_diff": {
                "mean": round(daily_df[COL_DAILY_RETURN_ABS_DIFF].mean(), 4),
                "max": round(daily_df[COL_DAILY_RETURN_ABS_DIFF].max(), 4),
            },
            "cumul_multiple_log_diff": {
                "mean": round(daily_df[COL_CUMUL_MULTIPLE_LOG_DIFF].mean(), 4),
                "max": round(daily_df[COL_CUMUL_MULTIPLE_LOG_DIFF].max(), 4),
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
    logger.debug(f"검증 기간: {validation_results['overlap_start']} ~ {validation_results['overlap_end']}")
    logger.debug(f"총 일수: {validation_results['overlap_days']:,}일")
    logger.debug(f"레버리지: {DEFAULT_LEVERAGE_MULTIPLIER:.1f}배")
    logger.debug(f"Funding Spread: {DEFAULT_FUNDING_SPREAD:.4f}")
    logger.debug(f"Expense Ratio: {DEFAULT_EXPENSE_RATIO*100:.2f}%")

    logger.debug("-" * 64)
    logger.debug("검증 지표")
    logger.debug("-" * 64)

    # 누적수익률 관련
    logger.debug("  [누적수익률]")
    logger.debug(f"    실제: +{validation_results['cumulative_return_actual']*100:.1f}%")
    logger.debug(f"    시뮬: +{validation_results['cumulative_return_simulated']*100:.1f}%")
    logger.debug(f"    평균 로그차이: {validation_results['cumul_multiple_log_diff_mean_pct']:.2f}%")
    logger.debug(f"    RMSE: {validation_results['cumul_multiple_log_diff_rmse_pct']:.4f}%")
    logger.debug(f"    최대 로그차이: {validation_results['cumul_multiple_log_diff_max_pct']:.4f}%")

    # 품질 검증
    mean_log_diff_pct = validation_results["cumul_multiple_log_diff_mean_pct"]
    if mean_log_diff_pct > 20:
        logger.warning(f"누적배수 로그차이 평균이 큽니다: {mean_log_diff_pct:.2f}% (권장: ±20% 이내)")

    # 일별 비교 요약 통계
    logger.debug("-" * 64)
    logger.debug("일별 비교 요약 통계")
    logger.debug("-" * 64)

    columns = [
        ("지표", 30, Align.LEFT),
        ("평균", 12, Align.RIGHT),
        ("최대", 12, Align.RIGHT),
    ]
    summary_table = TableLogger(columns, logger, indent=2)

    rows = [
        [
            "일일수익률 절대차이 (%)",
            f"{daily_df[COL_DAILY_RETURN_ABS_DIFF].mean():.4f}",
            f"{daily_df[COL_DAILY_RETURN_ABS_DIFF].max():.4f}",
        ],
        [
            "누적배수 로그차이 (%)",
            f"{daily_df[COL_CUMUL_MULTIPLE_LOG_DIFF].mean():.2f}",
            f"{daily_df[COL_CUMUL_MULTIPLE_LOG_DIFF].max():.2f}",
        ],
    ]

    summary_table.print_table(rows)

    # 문장형 요약
    logger.debug("-" * 64)
    logger.debug("[요약]")
    logger.debug("-" * 64)

    mean_log_diff = validation_results["cumul_multiple_log_diff_mean_pct"]

    # 누적배수 로그차이 평균 해석
    if mean_log_diff < 1:
        diff_desc = "거의 완전히 일치"
    elif mean_log_diff < 5:
        diff_desc = "매우 근접"
    elif mean_log_diff < 20:
        diff_desc = "양호하게 일치"
    else:
        diff_desc = "다소 차이 존재"

    logger.debug(f"- 누적배수 로그차이 평균은 {mean_log_diff:.2f}%로, 장기 성과도 {diff_desc}합니다.")
    logger.debug("-" * 64)

    logger.debug("=" * 64)
    logger.debug(f"일별 비교 CSV 저장 완료: {TQQQ_DAILY_COMPARISON_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
