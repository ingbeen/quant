"""
TQQQ 시뮬레이션 파라미터 그리드 서치 스크립트

비용 모델 파라미터(funding spread, expense ratio)의 다양한 조합을 탐색하여
실제 TQQQ 데이터와 가장 유사한 시뮬레이션을 생성하는 최적 파라미터를 찾는다.
상위 전략을 CSV로 저장한다.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from qbt.common_constants import (
    FFR_DATA_PATH,
    QQQ_DATA_PATH,
    RESULTS_DIR,
    TQQQ_DATA_PATH,
    TQQQ_VALIDATION_PATH,
)
from qbt.synth import find_optimal_cost_model
from qbt.synth.constants import DEFAULT_LEVERAGE_MULTIPLIER
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
        description="TQQQ 시뮬레이션 파라미터 그리드 서치",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            사용 예시:
            # 기본 범위로 그리드 서치
            poetry run python scripts/tqqq/validate_tqqq_simulation.py

            # 탐색 범위 좁히기
            poetry run python scripts/tqqq/validate_tqqq_simulation.py \\
              --spread-min 0.6 --spread-max 0.7 \\
              --expense-min 0.008 --expense-max 0.010
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
        "--spread-min",
        type=float,
        default=0.4,
        help="funding spread 탐색 최소값",
    )
    parser.add_argument(
        "--spread-max",
        type=float,
        default=0.9,
        help="funding spread 탐색 최대값",
    )
    parser.add_argument(
        "--spread-step",
        type=float,
        default=0.05,
        help="funding spread 탐색 간격",
    )
    parser.add_argument(
        "--expense-min",
        type=float,
        default=0.007,
        help="expense ratio 탐색 최소값",
    )
    parser.add_argument(
        "--expense-max",
        type=float,
        default=0.011,
        help="expense ratio 탐색 최대값",
    )
    parser.add_argument(
        "--expense-step",
        type=float,
        default=0.001,
        help="expense ratio 탐색 간격",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="병렬 처리 워커 수 (기본값: CPU 코어 수 - 1)",
    )

    args = parser.parse_args()

    # 1. 데이터 로드
    logger.debug("QQQ, TQQQ 및 FFR 데이터 로딩 시작")
    qqq_df = load_stock_data(args.qqq_path)
    tqqq_df = load_stock_data(args.tqqq_path)
    ffr_df = load_ffr_data(args.ffr_path)

    # 2. 비용 모델 캘리브레이션
    logger.debug(
        f"비용 모델 캘리브레이션 시작: "
        f"leverage={args.leverage}, "
        f"spread={args.spread_min}~{args.spread_max}% (step={args.spread_step}%), "
        f"expense={args.expense_min*100:.2f}~{args.expense_max*100:.2f}% "
        f"(step={args.expense_step*100:.2f}%)"
    )

    top_strategies = find_optimal_cost_model(
        underlying_df=qqq_df,
        actual_leveraged_df=tqqq_df,
        ffr_df=ffr_df,
        leverage=args.leverage,
        spread_range=(args.spread_min, args.spread_max),
        spread_step=args.spread_step,
        expense_range=(args.expense_min, args.expense_max),
        expense_step=args.expense_step,
        max_workers=args.workers,
    )

    # 3. 상위 전략 테이블 출력
    logger.debug("=" * 120)
    logger.debug("상위 전략")

    columns = [
        ("Rank", 6, Align.RIGHT),
        ("Spread(%)", 12, Align.RIGHT),
        ("Expense(%)", 12, Align.RIGHT),
        ("자산배수평균차이(%)", 20, Align.RIGHT),
        ("자산배수RMSE(%)", 16, Align.RIGHT),
    ]
    table = TableLogger(columns, logger, indent=2)

    rows = []
    for rank, strategy in enumerate(top_strategies, start=1):
        row = [
            str(rank),
            f"{strategy['funding_spread']:.2f}",
            f"{strategy['expense_ratio']*100:.2f}",
            f"{strategy['asset_multiple_mean_diff_pct']:.4f}",
            f"{strategy['asset_multiple_rmse_diff_pct']:.4f}",
        ]
        rows.append(row)

    table.print_table(rows)

    # 4. 결과 저장 (CSV) - 상위 전략
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_csv_path = TQQQ_VALIDATION_PATH

    rows = []
    for rank, strategy in enumerate(top_strategies, start=1):
        row = {
            # 메타 정보 (7개)
            "rank": rank,
            "검증기간_시작": strategy["overlap_start"],
            "검증기간_종료": strategy["overlap_end"],
            "총일수": strategy["overlap_days"],
            "leverage": round(strategy["leverage"], 2),
            "funding_spread": round(strategy["funding_spread"], 2),
            "expense_ratio": round(strategy["expense_ratio"], 6),
            # 누적수익률/성과 (5개)
            "누적수익률_실제(%)": round(strategy["cumulative_return_actual"] * 100, 2),
            "누적수익률_시뮬레이션(%)": round(strategy["cumulative_return_simulated"] * 100, 2),
            "자산배수_평균차이(%)": round(strategy["asset_multiple_mean_diff_pct"], 4),
            "자산배수_RMSE(%)": round(strategy["asset_multiple_rmse_diff_pct"], 4),
            "자산배수_최대차이(%)": round(strategy["asset_multiple_max_diff_pct"], 4),
        }
        rows.append(row)

    results_df = pd.DataFrame(rows)
    results_df.to_csv(results_csv_path, index=False, encoding="utf-8-sig")
    logger.debug(f"검증 결과 저장: {results_csv_path} ({len(rows)}행)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
