"""
TQQQ 시뮬레이션 파라미터 그리드 서치 스크립트

비용 모델 파라미터(funding spread, expense ratio)의 다양한 조합을 탐색하여
실제 TQQQ 데이터와 가장 유사한 시뮬레이션을 생성하는 최적 파라미터를 찾는다.
상위 전략을 CSV로 저장한다.
모든 파라미터는 상수에서 정의됩니다.

실행 명령어:
    poetry run python scripts/tqqq/validate_tqqq_simulation.py
"""

import sys

import pandas as pd

from qbt.common_constants import (
    FFR_DATA_PATH,
    QQQ_DATA_PATH,
    RESULTS_DIR,
    TQQQ_DATA_PATH,
    TQQQ_VALIDATION_PATH,
)
from qbt.tqqq import find_optimal_cost_model
from qbt.tqqq.constants import (
    DEFAULT_EXPENSE_RANGE,
    DEFAULT_EXPENSE_STEP,
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_SPREAD_RANGE,
    DEFAULT_SPREAD_STEP,
)
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
    # 1. 데이터 로드
    logger.debug("QQQ, TQQQ 및 FFR 데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)

    # 2. 비용 모델 캘리브레이션
    logger.debug(
        f"비용 모델 캘리브레이션 시작: "
        f"leverage={DEFAULT_LEVERAGE_MULTIPLIER}, "
        f"spread={DEFAULT_SPREAD_RANGE[0]}~{DEFAULT_SPREAD_RANGE[1]}% (step={DEFAULT_SPREAD_STEP}%), "
        f"expense={DEFAULT_EXPENSE_RANGE[0]*100:.2f}~{DEFAULT_EXPENSE_RANGE[1]*100:.2f}% "
        f"(step={DEFAULT_EXPENSE_STEP*100:.2f}%)"
    )

    top_strategies = find_optimal_cost_model(
        underlying_df=qqq_df,
        actual_leveraged_df=tqqq_df,
        ffr_df=ffr_df,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
        spread_range=DEFAULT_SPREAD_RANGE,
        spread_step=DEFAULT_SPREAD_STEP,
        expense_range=DEFAULT_EXPENSE_RANGE,
        expense_step=DEFAULT_EXPENSE_STEP,
        max_workers=None,
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
