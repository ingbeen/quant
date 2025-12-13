"""
TQQQ 일별 비교 CSV 생성 스크립트

지정된 파라미터로 TQQQ를 시뮬레이션하고 실제 TQQQ 데이터와 일별로 비교하여
상세 검증 지표와 일별 비교 CSV를 생성한다.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from qbt.common_constants import (
    COL_ASSET_MULTIPLE_REL_DIFF,
    COL_CLOSE,
    COL_DAILY_RETURN_ABS_DIFF,
    FFR_DATA_PATH,
    QQQ_DATA_PATH,
    TQQQ_DAILY_COMPARISON_PATH,
    TQQQ_DATA_PATH,
)
from qbt.synth import extract_overlap_period, simulate_leveraged_etf, validate_and_generate_comparison
from qbt.synth.constants import DEFAULT_EXPENSE_RATIO, DEFAULT_FUNDING_SPREAD, DEFAULT_LEVERAGE_MULTIPLIER
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_ffr_data, load_stock_data
from qbt.utils.formatting import Align, TableLogger

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    parser = argparse.ArgumentParser(
        description="TQQQ 일별 비교 CSV 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            사용 예시:
            # 기본 파라미터로 일별 비교 생성
            poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py

            # 특정 파라미터로 일별 비교 생성
            poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py \\
              --funding-spread 0.65 \\
              --expense-ratio 0.009

            # 출력 파일 경로 지정
            poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py \\
              --output results/tqqq_daily_custom.csv
        """,
    )
    parser.add_argument(
        "--qqq-path",
        type=Path,
        default=QQQ_DATA_PATH,
        help="QQQ CSV 파일 경로",
    )
    parser.add_argument(
        "--tqqq-path",
        type=Path,
        default=TQQQ_DATA_PATH,
        help="TQQQ CSV 파일 경로",
    )
    parser.add_argument(
        "--ffr-path",
        type=Path,
        default=FFR_DATA_PATH,
        help="연방기금금리 CSV 파일 경로",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=DEFAULT_LEVERAGE_MULTIPLIER,
        help="레버리지 배수",
    )
    parser.add_argument(
        "--funding-spread",
        type=float,
        default=DEFAULT_FUNDING_SPREAD,
        help="펀딩 스프레드 (%%)",
    )
    parser.add_argument(
        "--expense-ratio",
        type=float,
        default=DEFAULT_EXPENSE_RATIO,
        help="연간 비용 비율",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=TQQQ_DAILY_COMPARISON_PATH,
        help="출력 CSV 파일 경로",
    )

    args = parser.parse_args()

    # 1. 데이터 로드
    logger.debug("QQQ, TQQQ 및 FFR 데이터 로딩 시작")
    qqq_df = load_stock_data(args.qqq_path)
    tqqq_df = load_stock_data(args.tqqq_path)
    ffr_df = load_ffr_data(args.ffr_path)

    # 2. 겹치는 기간 추출 및 시뮬레이션 실행
    logger.debug("겹치는 기간 추출 및 시뮬레이션 실행")
    overlap_dates, qqq_overlap, tqqq_overlap = extract_overlap_period(qqq_df, tqqq_df)
    logger.debug(f"겹치는 기간: {overlap_dates[0]} ~ {overlap_dates[-1]} ({len(overlap_dates):,}일)")

    # 3. 시뮬레이션 실행
    logger.debug(
        f"시뮬레이션 실행: leverage={args.leverage}, "
        f"funding_spread={args.funding_spread}%, "
        f"expense_ratio={args.expense_ratio*100:.2f}%"
    )

    initial_price = float(tqqq_overlap.iloc[0][COL_CLOSE])
    simulated_df = simulate_leveraged_etf(
        underlying_df=qqq_overlap,
        leverage=args.leverage,
        expense_ratio=args.expense_ratio,
        initial_price=initial_price,
        ffr_df=ffr_df,
        funding_spread=args.funding_spread,
    )

    logger.debug("시뮬레이션 완료")

    # 4. 검증 및 일별 비교 CSV 생성 (통합 함수 사용)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    logger.debug(f"검증 지표 계산 및 일별 비교 CSV 생성: {args.output}")
    validation_results = validate_and_generate_comparison(
        simulated_df=simulated_df,
        actual_df=tqqq_overlap,
        output_path=args.output,
    )

    daily_df = pd.read_csv(args.output)
    logger.debug(f"일별 비교 CSV 저장 완료: {len(daily_df):,}행")

    # 6. 결과 출력 (터미널)
    logger.debug("=" * 64)
    logger.debug("TQQQ 시뮬레이션 검증")
    logger.debug("=" * 64)
    logger.debug(f"검증 기간: {validation_results['overlap_start']} ~ {validation_results['overlap_end']}")
    logger.debug(f"총 일수: {validation_results['overlap_days']:,}일")
    logger.debug(f"레버리지: {args.leverage:.1f}배")
    logger.debug(f"Funding Spread: {args.funding_spread:.2f}%")
    logger.debug(f"Expense Ratio: {args.expense_ratio*100:.2f}%")

    logger.debug("-" * 64)
    logger.debug("검증 지표")
    logger.debug("-" * 64)

    # 누적수익률 관련
    logger.debug("  [누적수익률]")
    logger.debug(f"    실제: +{validation_results['cumulative_return_actual']*100:.1f}%")
    logger.debug(f"    시뮬: +{validation_results['cumulative_return_simulated']*100:.1f}%")
    logger.debug(f"    평균 오차: {validation_results['asset_multiple_mean_error_pct']:.2f}%")
    logger.debug(f"    RMSE: {validation_results['asset_multiple_rmse_pct']:.4f}%")
    logger.debug(f"    최대 오차: {validation_results['asset_multiple_max_error_pct']:.4f}%")

    # 품질 검증
    mean_error_pct = validation_results["asset_multiple_mean_error_pct"]
    if mean_error_pct > 20:
        logger.warning(f"자산배수 평균 오차가 큽니다: {mean_error_pct:.2f}% (권장: ±20% 이내)")

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
            "자산배수 상대차이 (%)",
            f"{daily_df[COL_ASSET_MULTIPLE_REL_DIFF].mean():.2f}",
            f"{daily_df[COL_ASSET_MULTIPLE_REL_DIFF].max():.2f}",
        ],
    ]

    summary_table.print_table(rows)

    # 문장형 요약
    logger.debug("-" * 64)
    logger.debug("[요약]")
    logger.debug("-" * 64)

    mean_error = validation_results["asset_multiple_mean_error_pct"]

    # 자산배수 평균 오차 해석
    if mean_error < 1:
        error_desc = "거의 완전히 일치"
    elif mean_error < 5:
        error_desc = "매우 근접"
    elif mean_error < 20:
        error_desc = "양호하게 일치"
    else:
        error_desc = "다소 차이 존재"

    logger.debug(f"- 자산배수 평균 오차는 {mean_error:.2f}%로, 장기 성과도 {error_desc}합니다.")
    logger.debug("-" * 64)

    logger.debug("=" * 64)
    logger.debug(f"일별 비교 CSV 저장 완료: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
