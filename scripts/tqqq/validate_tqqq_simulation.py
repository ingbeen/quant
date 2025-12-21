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
    MAX_TOP_STRATEGIES,
)
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

    # 3. 메타 정보 헤더 출력
    logger.debug("=" * 120)
    logger.debug("비용 모델 캘리브레이션 결과")
    logger.debug("=" * 120)

    if top_strategies:
        first_strategy = top_strategies[0]
        logger.debug(f"검증 기간: {first_strategy['overlap_start']} ~ {first_strategy['overlap_end']}")
        logger.debug(f"총 일수: {first_strategy['overlap_days']:,}일")
        logger.debug(f"레버리지: {first_strategy['leverage']:.1f}배")
        logger.debug("-" * 120)

    # 4. 상위 전략 테이블 출력
    columns = [
        ("Spread", 10, Align.RIGHT),
        ("Expense(%)", 11, Align.RIGHT),
        ("종가_실제", 11, Align.RIGHT),
        ("종가_시뮬", 11, Align.RIGHT),
        ("누적수익률_실제(%)", 18, Align.RIGHT),
        ("누적수익률_시뮬(%)", 18, Align.RIGHT),
        ("로그차이RMSE(%)", 16, Align.RIGHT),
        ("로그차이평균(%)", 16, Align.RIGHT),
    ]
    table = TableLogger(columns, logger, indent=2)

    rows = []
    for _, strategy in enumerate(top_strategies, start=1):
        row = [
            f"{strategy['funding_spread']:.4f}",
            f"{strategy['expense_ratio']*100:.2f}",
            f"{strategy['final_close_actual']:.2f}",
            f"{strategy['final_close_simulated']:.2f}",
            f"{strategy['cumulative_return_actual']*100:.2f}",
            f"{strategy['cumulative_return_simulated']*100:.2f}",
            f"{strategy['cumul_multiple_log_diff_rmse_pct']:.4f}",
            f"{strategy['cumul_multiple_log_diff_mean_pct']:.4f}",
        ]
        rows.append(row)

    table.print_table(rows)

    # 5. 결과 저장 (CSV) - 상위 전략
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_csv_path = TQQQ_VALIDATION_PATH

    rows = []
    for _, strategy in enumerate(top_strategies, start=1):
        row = {
            # 파라미터 (2개)
            "funding_spread": round(strategy["funding_spread"], 4),
            "expense_ratio": round(strategy["expense_ratio"], 6),
            # 종가 (2개)
            "종가_실제": round(strategy["final_close_actual"], 2),
            "종가_시뮬": round(strategy["final_close_simulated"], 2),
            # 누적수익률/성과 (6개)
            "누적수익률_실제(%)": round(strategy["cumulative_return_actual"] * 100, 2),
            "누적수익률_시뮬레이션(%)": round(strategy["cumulative_return_simulated"] * 100, 2),
            "누적수익률_상대차이(%)": round(strategy["cumulative_return_rel_diff_pct"], 2),
            "누적배수로그차이_RMSE(%)": round(strategy["cumul_multiple_log_diff_rmse_pct"], 4),
            "누적배수로그차이_평균(%)": round(strategy["cumul_multiple_log_diff_mean_pct"], 4),
            "누적배수로그차이_최대(%)": round(strategy["cumul_multiple_log_diff_max_pct"], 4),
        }
        rows.append(row)

    results_df = pd.DataFrame(rows)
    results_df.to_csv(results_csv_path, index=False, encoding="utf-8-sig")
    logger.debug(f"검증 결과 저장: {results_csv_path} ({len(rows)}행)")

    # 6. 메타데이터 저장
    metadata = {
        "execution_params": {
            "leverage": round(DEFAULT_LEVERAGE_MULTIPLIER, 1),
            "spread_range": [round(x, 4) for x in DEFAULT_SPREAD_RANGE],
            "spread_step": round(DEFAULT_SPREAD_STEP, 4),
            "expense_range": [round(x, 6) for x in DEFAULT_EXPENSE_RANGE],
            "expense_step": round(DEFAULT_EXPENSE_STEP, 6),
            "max_top_strategies": MAX_TOP_STRATEGIES,
        },
        "overlap_period": {
            "start_date": str(top_strategies[0]["overlap_start"]),
            "end_date": str(top_strategies[0]["overlap_end"]),
            "total_days": int(top_strategies[0]["overlap_days"]),
        },
        "results_summary": {
            "top_strategy": {
                "rank": 1,
                "funding_spread": round(top_strategies[0]["funding_spread"], 4),
                "expense_ratio": round(top_strategies[0]["expense_ratio"], 6),
                "cumul_multiple_log_diff_mean_pct": round(
                    top_strategies[0]["cumul_multiple_log_diff_mean_pct"], 4
                ),
            },
            "cumul_multiple_log_diff_mean_pct": {
                "min": round(results_df["누적배수로그차이_평균(%)"].min(), 4),
                "max": round(results_df["누적배수로그차이_평균(%)"].max(), 4),
                "median": round(results_df["누적배수로그차이_평균(%)"].median(), 4),
            },
            "cumul_multiple_log_diff_rmse_pct": {
                "min": round(results_df["누적배수로그차이_RMSE(%)"].min(), 4),
                "max": round(results_df["누적배수로그차이_RMSE(%)"].max(), 4),
                "median": round(results_df["누적배수로그차이_RMSE(%)"].median(), 4),
            },
        },
        "csv_info": {
            "path": str(results_csv_path),
            "row_count": len(rows),
            "file_size_bytes": results_csv_path.stat().st_size,
        },
    }

    save_metadata("tqqq_validation", metadata)
    logger.debug("메타데이터 저장 완료: storage/results/meta.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
