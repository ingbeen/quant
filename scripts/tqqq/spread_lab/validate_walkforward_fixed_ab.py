"""
완전 고정 (a,b) 워크포워드 검증 스크립트 (과최적화 진단)

전체기간 최적 (a, b)를 아무 재최적화 없이 아웃오브샘플에 그대로 적용하여
과최적화 여부를 정량적으로 진단한다.
60개월 Train, 1개월 Test 윈도우 구조로 월별 테스트 RMSE도 함께 산출한다.

사전 준비:
    poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py

실행 명령어:
    poetry run python scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py
"""

import sys
import time

import pandas as pd

from qbt.common_constants import META_JSON_PATH, QQQ_DATA_PATH
from qbt.tqqq.analysis_helpers import save_walkforward_results, save_walkforward_summary
from qbt.tqqq.constants import (
    COL_A,
    COL_B,
    DEFAULT_RATE_BOUNDARY_PCT,
    DEFAULT_TRAIN_WINDOW_MONTHS,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    SOFTPLUS_TUNING_CSV_PATH,
    SPREAD_LAB_DIR,
    TQQQ_DATA_PATH,
    TQQQ_WALKFORWARD_FIXED_AB_PATH,
    TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH,
)
from qbt.tqqq.data_loader import load_expense_ratio_data, load_ffr_data
from qbt.tqqq.types import WalkforwardSummaryDict
from qbt.tqqq.walkforward import (
    calculate_fixed_ab_stitched_rmse,
    calculate_rate_segmented_from_stitched,
    run_fixed_ab_walkforward,
)
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
    # 1. 전체기간 최적 (a, b) 값 로드
    if not SOFTPLUS_TUNING_CSV_PATH.exists():
        raise FileNotFoundError(
            f"튜닝 결과 CSV가 없습니다: {SOFTPLUS_TUNING_CSV_PATH}\n"
            f"먼저 실행: poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py"
        )

    tuning_df = pd.read_csv(SOFTPLUS_TUNING_CSV_PATH)
    a_global = float(tuning_df.iloc[0][COL_A])
    b_global = float(tuning_df.iloc[0][COL_B])
    logger.debug(f"전체기간 최적 (a, b) 로드: a={a_global:.4f}, b={b_global:.4f}")

    # 2. 데이터 로드
    logger.debug("QQQ, TQQQ, FFR 및 Expense Ratio 데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)

    # 3. 워크포워드 검증 정보 출력
    logger.debug("=" * 80)
    logger.debug("완전 고정 (a,b) 워크포워드 검증 (과최적화 진단)")
    logger.debug("=" * 80)
    logger.debug(f"학습 기간: {DEFAULT_TRAIN_WINDOW_MONTHS}개월 (5년)")
    logger.debug("테스트 기간: 1개월")
    logger.debug(f"고정 a 값: {a_global:.4f} (전체기간 튜닝 결과)")
    logger.debug(f"고정 b 값: {b_global:.4f} (전체기간 튜닝 결과)")
    logger.debug("-" * 80)

    start_time = time.perf_counter()

    # 4. 월별 테스트 RMSE 산출 (워크포워드 윈도우 구조 활용)
    result_df = run_fixed_ab_walkforward(
        qqq_df=qqq_df,
        tqqq_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
        a=a_global,
        b=b_global,
    )

    # 5. 연속(stitched) 워크포워드 RMSE 계산
    logger.debug("연속 워크포워드 RMSE 계산 시작...")
    stitched_rmse = calculate_fixed_ab_stitched_rmse(
        underlying_df=qqq_df,
        actual_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
        a=a_global,
        b=b_global,
    )
    logger.debug(f"연속 워크포워드 RMSE: {stitched_rmse:.4f}%")

    # 6. 금리 구간별 RMSE 분해
    logger.debug("금리 구간별 RMSE 분해 시작...")
    rate_segmented = calculate_rate_segmented_from_stitched(
        qqq_df=qqq_df,
        tqqq_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
        a=a_global,
        b=b_global,
    )

    elapsed_time = time.perf_counter() - start_time
    logger.debug(f"완전 고정 (a,b) 워크포워드 검증 완료: 소요시간 {elapsed_time:.2f}초")
    logger.debug("-" * 80)

    # 7. 요약 통계 계산
    test_rmse_values = result_df["test_rmse_pct"].dropna()
    summary: WalkforwardSummaryDict = {
        "test_rmse_mean": float(test_rmse_values.mean()) if len(test_rmse_values) > 0 else float("nan"),
        "test_rmse_median": float(test_rmse_values.median()) if len(test_rmse_values) > 0 else float("nan"),
        "test_rmse_std": float(test_rmse_values.std()) if len(test_rmse_values) > 0 else float("nan"),
        "test_rmse_min": float(test_rmse_values.min()) if len(test_rmse_values) > 0 else float("nan"),
        "test_rmse_max": float(test_rmse_values.max()) if len(test_rmse_values) > 0 else float("nan"),
        "a_mean": a_global,
        "a_std": 0.0,
        "b_mean": b_global,
        "b_std": 0.0,
        "n_test_months": len(result_df),
        "train_window_months": DEFAULT_TRAIN_WINDOW_MONTHS,
        "stitched_rmse": stitched_rmse,
    }

    # 금리 구간별 RMSE 추가 (optional 키)
    low_rmse = rate_segmented["low_rate_rmse"]
    high_rmse = rate_segmented["high_rate_rmse"]
    low_days = rate_segmented["low_rate_days"]
    high_days = rate_segmented["high_rate_days"]
    boundary = rate_segmented["rate_boundary_pct"]

    if low_rmse is not None:
        summary["low_rate_rmse"] = float(low_rmse)
    else:
        summary["low_rate_rmse"] = None
    if high_rmse is not None:
        summary["high_rate_rmse"] = float(high_rmse)
    else:
        summary["high_rate_rmse"] = None
    if low_days is not None:
        summary["low_rate_days"] = int(low_days)
    if high_days is not None:
        summary["high_rate_days"] = int(high_days)
    if boundary is not None:
        summary["rate_boundary_pct"] = float(boundary)

    # 8. 결과 요약 출력
    logger.debug("완전 고정 (a,b) 워크포워드 검증 결과 요약:")
    logger.debug(f"  고정 a 값: {a_global:.4f}")
    logger.debug(f"  고정 b 값: {b_global:.4f}")
    logger.debug(f"  테스트 월 수: {summary['n_test_months']}개월")
    logger.debug(f"  테스트 RMSE 평균: {summary['test_rmse_mean']:.4f}%")
    logger.debug(f"  테스트 RMSE 중앙값: {summary['test_rmse_median']:.4f}%")
    logger.debug(f"  테스트 RMSE 표준편차: {summary['test_rmse_std']:.4f}%")
    logger.debug(f"  테스트 RMSE 범위: [{summary['test_rmse_min']:.4f}%, {summary['test_rmse_max']:.4f}%]")
    logger.debug(f"  연속 워크포워드 RMSE: {stitched_rmse:.4f}%")
    logger.debug(f"  금리 구간별 RMSE (저금리 <{DEFAULT_RATE_BOUNDARY_PCT}%): {rate_segmented['low_rate_rmse']}")
    logger.debug(f"  금리 구간별 RMSE (고금리 >={DEFAULT_RATE_BOUNDARY_PCT}%): {rate_segmented['high_rate_rmse']}")
    logger.debug(f"  저금리 거래일 수: {rate_segmented['low_rate_days']}")
    logger.debug(f"  고금리 거래일 수: {rate_segmented['high_rate_days']}")
    logger.debug("-" * 80)

    # 9. CSV 저장
    SPREAD_LAB_DIR.mkdir(parents=True, exist_ok=True)

    save_walkforward_results(result_df, TQQQ_WALKFORWARD_FIXED_AB_PATH)
    logger.debug(f"워크포워드 결과 저장: {TQQQ_WALKFORWARD_FIXED_AB_PATH} ({len(result_df)}행)")

    save_walkforward_summary(summary, TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH)
    logger.debug(f"워크포워드 요약 저장: {TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH}")

    # 10. 메타데이터 저장
    metadata = {
        "funding_spread_mode": "softplus_ffr_monthly",
        "ab_mode": "fixed",
        "a_fixed_value": round(a_global, 4),
        "b_fixed_value": round(b_global, 4),
        "ab_source": "global_tuning",
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
            "n_test_months": summary["n_test_months"],
            "stitched_rmse": round(stitched_rmse, 4),
        },
        "rate_segmented_rmse": {
            "low_rate_rmse": round(rate_segmented["low_rate_rmse"], 4)
            if rate_segmented["low_rate_rmse"] is not None
            else None,
            "high_rate_rmse": round(rate_segmented["high_rate_rmse"], 4)
            if rate_segmented["high_rate_rmse"] is not None
            else None,
            "low_rate_days": rate_segmented["low_rate_days"],
            "high_rate_days": rate_segmented["high_rate_days"],
            "rate_boundary_pct": rate_segmented["rate_boundary_pct"],
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
            "walkforward_csv": str(TQQQ_WALKFORWARD_FIXED_AB_PATH),
            "walkforward_summary_csv": str(TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH),
        },
    }

    save_metadata("tqqq_walkforward_fixed_ab", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
