"""
구간별 고정 스프레드 모델 (오라클) 생성 스크립트

전체 기간 TQQQ 데이터에서 실현 스프레드를 역산하고,
사용자 정의 구간 경계(0%, 2%, 4%)로 스프레드를 집계하여
오라클 모델을 생성한다.

오라클 모델: 미래 데이터를 참조하는 전제이므로 워크포워드 불필요,
인샘플 RMSE로 적합도만 평가한다.

실행 명령어:
    poetry run python scripts/tqqq/spread_lab/generate_segment_spread.py
"""

import sys
import time

import pandas as pd

from qbt.common_constants import QQQ_DATA_PATH
from qbt.tqqq.constants import (
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_SEGMENT_BOUNDARIES,
    DEFAULT_SEGMENT_STAT_FUNC,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    SEGMENT_SPREAD_CSV_PATH,
    SPREAD_LAB_DIR,
    TQQQ_DATA_PATH,
)
from qbt.tqqq.data_loader import load_expense_ratio_data, load_ffr_data
from qbt.tqqq.lookup_spread import (
    build_segment_table,
    calculate_realized_spread,
    evaluate_segment_combination,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """구간별 고정 스프레드 모델 생성 메인 함수"""
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

    # 3. 구간별 스프레드 테이블 생성
    boundaries = list(DEFAULT_SEGMENT_BOUNDARIES)
    stat_func = DEFAULT_SEGMENT_STAT_FUNC
    logger.debug(f"구간 경계: {boundaries}%, 통계량: {stat_func}")

    table = build_segment_table(realized_df, boundaries, stat_func)
    logger.debug(f"구간별 스프레드 테이블 생성: {len(table)}개 구간")

    # 4. 인샘플 RMSE 평가
    logger.debug("인샘플 RMSE 평가 시작")
    eval_result = evaluate_segment_combination(
        realized_df=realized_df,
        boundaries=boundaries,
        stat_func=stat_func,
        ffr_df=ffr_df,
        expense_df=expense_df,
        underlying_df=qqq_df,
        actual_df=tqqq_df,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
    )
    logger.debug(f"인샘플 RMSE: {eval_result['rmse_pct']:.4f}%")

    # 5. 결과 로그 출력
    logger.debug("=== 구간별 고정 스프레드 모델 (오라클) ===")
    segment_details = eval_result["segment_details"]
    for detail in segment_details:  # type: ignore[union-attr]
        spread_str = f"{detail['spread']:.6f}" if detail["spread"] is not None else "N/A"
        logger.debug(f"  구간: {detail['segment']}, 스프레드: {spread_str}, 관측일수: {detail['n_days']}")
    logger.debug(f"  인샘플 RMSE: {eval_result['rmse_pct']:.4f}%")
    logger.debug(f"  유효 구간 수: {eval_result['n_segments']}")

    # 6. CSV 저장
    SPREAD_LAB_DIR.mkdir(parents=True, exist_ok=True)

    csv_rows: list[dict[str, object]] = []
    for detail in segment_details:  # type: ignore[union-attr]
        csv_rows.append(
            {
                "구간": detail["segment"],
                "스프레드": detail["spread"],
                "관측일수": detail["n_days"],
            }
        )
    # RMSE 행 추가
    csv_rows.append(
        {
            "구간": "전체",
            "스프레드": None,
            "관측일수": len(realized_df),
        }
    )

    results_df = pd.DataFrame(csv_rows)
    results_df["통계량"] = stat_func
    rmse_pct = float(str(eval_result["rmse_pct"]))
    results_df["인샘플_RMSE_pct"] = round(rmse_pct, 4)
    results_df.to_csv(SEGMENT_SPREAD_CSV_PATH, index=False, encoding="utf-8-sig")
    logger.debug(f"결과 저장: {SEGMENT_SPREAD_CSV_PATH}")

    # 7. 메타데이터 저장
    elapsed = time.time() - start_time
    metadata = {
        "model_type": "segment_spread_oracle",
        "boundaries": boundaries,
        "stat_func": stat_func,
        "n_segments": eval_result["n_segments"],
        "rmse_pct": rmse_pct,
        "segment_details": segment_details,
        "n_realized_spread_days": len(realized_df),
        "elapsed_time_sec": round(elapsed, 1),
        "input_files": {
            "qqq": str(QQQ_DATA_PATH),
            "tqqq": str(TQQQ_DATA_PATH),
            "ffr": str(FFR_DATA_PATH),
            "expense": str(EXPENSE_RATIO_DATA_PATH),
        },
        "output_files": {
            "segment_spread_csv": str(SEGMENT_SPREAD_CSV_PATH),
        },
    }
    save_metadata("tqqq_segment_spread", metadata)

    logger.debug(f"완료 (소요시간: {elapsed:.1f}초)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
