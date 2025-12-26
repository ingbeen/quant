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

from qbt.common_constants import QQQ_DATA_PATH, RESULTS_DIR
from qbt.tqqq import find_optimal_cost_model
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_ACTUAL_CUMUL_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_MAX,
    COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    COL_CUMUL_RETURN_REL_DIFF,
    COL_SIMUL_CLOSE,
    COL_SIMUL_CUMUL_RETURN,
    DEFAULT_EXPENSE_RANGE,
    DEFAULT_EXPENSE_STEP,
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_SPREAD_RANGE,
    DEFAULT_SPREAD_STEP,
    DISPLAY_EXPENSE,
    DISPLAY_SPREAD,
    FFR_DATA_PATH,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    KEY_CUMULATIVE_RETURN_ACTUAL,
    KEY_CUMULATIVE_RETURN_REL_DIFF,
    KEY_CUMULATIVE_RETURN_SIMULATED,
    KEY_EXPENSE,
    KEY_FINAL_CLOSE_ACTUAL,
    KEY_FINAL_CLOSE_SIMULATED,
    KEY_OVERLAP_DAYS,
    KEY_OVERLAP_END,
    KEY_OVERLAP_START,
    KEY_SPREAD,
    MAX_TOP_STRATEGIES,
    TQQQ_DATA_PATH,
    TQQQ_VALIDATION_PATH,
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
        f"{DISPLAY_SPREAD}={DEFAULT_SPREAD_RANGE[0]}~{DEFAULT_SPREAD_RANGE[1]}% (step={DEFAULT_SPREAD_STEP}%), "
        f"{DISPLAY_EXPENSE}={DEFAULT_EXPENSE_RANGE[0]*100:.2f}~{DEFAULT_EXPENSE_RANGE[1]*100:.2f}% "
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

    # 빈 결과 방어
    if not top_strategies:
        logger.error("비용 모델 캘리브레이션 실패: 유효한 전략을 찾을 수 없습니다.")
        return 1

    if top_strategies:
        first_strategy = top_strategies[0]
        logger.debug(f"검증 기간: {first_strategy['overlap_start']} ~ {first_strategy['overlap_end']}")
        logger.debug(f"총 일수: {first_strategy['overlap_days']:,}일")
        logger.debug(f"레버리지: {first_strategy['leverage']:.1f}배")
        logger.debug("-" * 120)

    # 4. 상위 전략 테이블 출력
    columns = [
        (DISPLAY_SPREAD, 14, Align.RIGHT),
        (DISPLAY_EXPENSE, 14, Align.RIGHT),
        (COL_ACTUAL_CLOSE, 11, Align.RIGHT),
        (COL_SIMUL_CLOSE, 11, Align.RIGHT),
        (COL_ACTUAL_CUMUL_RETURN, 18, Align.RIGHT),
        (COL_SIMUL_CUMUL_RETURN, 18, Align.RIGHT),
        (COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE, 24, Align.RIGHT),
        (COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN, 24, Align.RIGHT),
    ]
    table = TableLogger(columns, logger, indent=2)

    rows = []
    for _, strategy in enumerate(top_strategies, start=1):
        row = [
            f"{strategy[KEY_SPREAD]:.4f}",
            f"{strategy[KEY_EXPENSE]*100:.2f}",
            f"{strategy[KEY_FINAL_CLOSE_ACTUAL]:.2f}",
            f"{strategy[KEY_FINAL_CLOSE_SIMULATED]:.2f}",
            f"{strategy[KEY_CUMULATIVE_RETURN_ACTUAL]*100:.2f}",
            f"{strategy[KEY_CUMULATIVE_RETURN_SIMULATED]*100:.2f}",
            f"{strategy[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]:.4f}",
            f"{strategy[KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN]:.4f}",
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
            KEY_SPREAD: round(strategy[KEY_SPREAD], 4),
            KEY_EXPENSE: round(strategy[KEY_EXPENSE], 6),
            # 종가 (2개)
            COL_ACTUAL_CLOSE: round(strategy[KEY_FINAL_CLOSE_ACTUAL], 2),
            COL_SIMUL_CLOSE: round(strategy[KEY_FINAL_CLOSE_SIMULATED], 2),
            # 누적수익률/성과 (6개)
            COL_ACTUAL_CUMUL_RETURN: round(strategy[KEY_CUMULATIVE_RETURN_ACTUAL] * 100, 2),
            COL_SIMUL_CUMUL_RETURN: round(strategy[KEY_CUMULATIVE_RETURN_SIMULATED] * 100, 2),
            COL_CUMUL_RETURN_REL_DIFF: round(strategy[KEY_CUMULATIVE_RETURN_REL_DIFF], 2),
            COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE: round(strategy[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE], 4),
            COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN: round(strategy[KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN], 4),
            COL_CUMUL_MULTIPLE_LOG_DIFF_MAX: round(strategy[KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX], 4),
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
            "start_date": str(top_strategies[0][KEY_OVERLAP_START]),
            "end_date": str(top_strategies[0][KEY_OVERLAP_END]),
            "total_days": int(top_strategies[0][KEY_OVERLAP_DAYS]),
        },
        "results_summary": {
            "top_strategy": {
                "rank": 1,
                KEY_SPREAD: round(top_strategies[0][KEY_SPREAD], 4),
                KEY_EXPENSE: round(top_strategies[0][KEY_EXPENSE], 6),
                "cumul_multiple_log_diff_mean_pct": round(top_strategies[0][KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN], 4),
            },
            "cumul_multiple_log_diff_mean_pct": {
                "min": round(results_df[COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN].min(), 4),
                "max": round(results_df[COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN].max(), 4),
                "median": round(results_df[COL_CUMUL_MULTIPLE_LOG_DIFF_MEAN].median(), 4),
            },
            "cumul_multiple_log_diff_rmse_pct": {
                "min": round(results_df[COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE].min(), 4),
                "max": round(results_df[COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE].max(), 4),
                "median": round(results_df[COL_CUMUL_MULTIPLE_LOG_DIFF_RMSE].median(), 4),
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
