"""
워크포워드 검증 통합 스크립트

3가지 모드를 순차 실행하여 과최적화를 정량적으로 진단한다:
  1. 동적 워크포워드: a, b 모두 매월 최적화 (60개월 Train, 1개월 Test)
  2. b 고정 워크포워드: 전체기간 최적 b를 고정하고 a만 최적화
  3. 완전 고정 (a,b) 워크포워드: 전체기간 최적 (a, b)를 재최적화 없이 적용

사전 준비:
    poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py

실행 명령어:
    poetry run python scripts/tqqq/spread_lab/validate_walkforward.py
"""

import sys
import time
from pathlib import Path
from typing import Any

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
    TQQQ_WALKFORWARD_FIXED_B_PATH,
    TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH,
    TQQQ_WALKFORWARD_PATH,
    TQQQ_WALKFORWARD_SUMMARY_PATH,
    WALKFORWARD_LOCAL_REFINE_A_DELTA,
    WALKFORWARD_LOCAL_REFINE_A_STEP,
    WALKFORWARD_LOCAL_REFINE_B_DELTA,
    WALKFORWARD_LOCAL_REFINE_B_STEP,
)
from qbt.tqqq.data_loader import load_expense_ratio_data, load_ffr_data
from qbt.tqqq.types import WalkforwardSummaryDict
from qbt.tqqq.walkforward import (
    calculate_fixed_ab_stitched_rmse,
    calculate_rate_segmented_from_stitched,
    calculate_stitched_walkforward_rmse,
    run_fixed_ab_walkforward,
    run_walkforward_validation,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)


def _log_summary(
    title: str,
    summary: WalkforwardSummaryDict,
    stitched_rmse: float,
    extra_lines: list[str] | None = None,
) -> None:
    """결과 요약을 로그로 출력한다.

    Args:
        title: 요약 제목
        summary: 워크포워드 요약 통계
        stitched_rmse: 연속 워크포워드 RMSE
        extra_lines: 추가 출력 라인 (금리 구간별 RMSE 등)
    """
    logger.debug(f"{title}:")
    logger.debug(f"  테스트 월 수: {summary['n_test_months']}개월")
    logger.debug(f"  테스트 RMSE 평균: {summary['test_rmse_mean']:.4f}%")
    logger.debug(f"  테스트 RMSE 중앙값: {summary['test_rmse_median']:.4f}%")
    logger.debug(f"  테스트 RMSE 표준편차: {summary['test_rmse_std']:.4f}%")
    logger.debug(f"  테스트 RMSE 범위: [{summary['test_rmse_min']:.4f}%, {summary['test_rmse_max']:.4f}%]")
    logger.debug(f"  연속 워크포워드 RMSE: {stitched_rmse:.4f}%")
    logger.debug(f"  a 평균 (std): {summary['a_mean']:.4f} ({summary['a_std']:.4f})")
    logger.debug(f"  b 평균 (std): {summary['b_mean']:.4f} ({summary['b_std']:.4f})")
    if extra_lines:
        for line in extra_lines:
            logger.debug(f"  {line}")
    logger.debug("-" * 80)


def _save_results(
    result_df: pd.DataFrame,
    summary: WalkforwardSummaryDict,
    result_path: Path,
    summary_path: Path,
) -> None:
    """CSV 결과 및 요약을 저장한다.

    Args:
        result_df: 워크포워드 결과 DataFrame
        summary: 워크포워드 요약 통계
        result_path: 결과 CSV 경로
        summary_path: 요약 CSV 경로
    """
    save_walkforward_results(result_df, result_path)
    logger.debug(f"워크포워드 결과 저장: {result_path} ({len(result_df)}행)")

    save_walkforward_summary(summary, summary_path)
    logger.debug(f"워크포워드 요약 저장: {summary_path}")


def _build_common_metadata(
    summary: WalkforwardSummaryDict,
    stitched_rmse: float,
    elapsed_time: float,
) -> dict[str, Any]:
    """공통 메타데이터 딕셔너리를 생성한다.

    Args:
        summary: 워크포워드 요약 통계
        stitched_rmse: 연속 워크포워드 RMSE
        elapsed_time: 소요 시간 (초)

    Returns:
        공통 메타데이터 딕셔너리
    """
    return {
        "funding_spread_mode": "softplus_ffr_monthly",
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
        },
    }


def _run_standard(
    qqq_df: pd.DataFrame,
    tqqq_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
) -> None:
    """동적 워크포워드 검증을 실행한다 (a, b 모두 최적화).

    Args:
        qqq_df: QQQ DataFrame
        tqqq_df: TQQQ DataFrame
        ffr_df: FFR DataFrame
        expense_df: Expense Ratio DataFrame
    """
    logger.debug("=" * 80)
    logger.debug("모드 1: 동적 워크포워드 검증 (Softplus 동적 스프레드)")
    logger.debug("=" * 80)
    logger.debug(f"학습 기간: {DEFAULT_TRAIN_WINDOW_MONTHS}개월 (5년)")
    logger.debug("테스트 기간: 1개월")
    logger.debug("첫 구간: 2-stage grid search (글로벌 탐색)")
    logger.debug("이후 구간: local refine (직전 월 최적값 주변 탐색)")
    logger.debug(
        f"Local Refine 범위: a_delta={WALKFORWARD_LOCAL_REFINE_A_DELTA}, " f"b_delta={WALKFORWARD_LOCAL_REFINE_B_DELTA}"
    )
    logger.debug("-" * 80)

    start_time = time.perf_counter()

    result_df, summary = run_walkforward_validation(
        underlying_df=qqq_df,
        actual_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
        train_window_months=DEFAULT_TRAIN_WINDOW_MONTHS,
    )

    elapsed_time = time.perf_counter() - start_time
    logger.debug(f"동적 워크포워드 검증 완료: 소요시간 {elapsed_time:.2f}초")
    logger.debug("-" * 80)

    # 연속(stitched) 워크포워드 RMSE 계산
    stitched_rmse = calculate_stitched_walkforward_rmse(
        walkforward_result_df=result_df,
        underlying_df=qqq_df,
        actual_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
    )
    summary["stitched_rmse"] = stitched_rmse

    _log_summary("동적 워크포워드 검증 결과 요약", summary, stitched_rmse)

    # CSV 저장
    _save_results(result_df, summary, TQQQ_WALKFORWARD_PATH, TQQQ_WALKFORWARD_SUMMARY_PATH)

    # 메타데이터 저장
    metadata = _build_common_metadata(summary, stitched_rmse, elapsed_time)
    metadata["tuning_policy"] = {
        "first_window": "full_grid_2stage",
        "subsequent_windows": "local_refine",
        "local_refine_a_delta": WALKFORWARD_LOCAL_REFINE_A_DELTA,
        "local_refine_a_step": WALKFORWARD_LOCAL_REFINE_A_STEP,
        "local_refine_b_delta": WALKFORWARD_LOCAL_REFINE_B_DELTA,
        "local_refine_b_step": WALKFORWARD_LOCAL_REFINE_B_STEP,
    }
    metadata["output_files"] = {
        "walkforward_csv": str(TQQQ_WALKFORWARD_PATH),
        "walkforward_summary_csv": str(TQQQ_WALKFORWARD_SUMMARY_PATH),
    }

    save_metadata("tqqq_walkforward", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")


def _run_fixed_b(
    qqq_df: pd.DataFrame,
    tqqq_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    b_global: float,
) -> None:
    """b 고정 워크포워드 검증을 실행한다 (a만 최적화).

    Args:
        qqq_df: QQQ DataFrame
        tqqq_df: TQQQ DataFrame
        ffr_df: FFR DataFrame
        expense_df: Expense Ratio DataFrame
        b_global: 전체기간 최적 b 값
    """
    logger.debug("=" * 80)
    logger.debug("모드 2: b 고정 워크포워드 검증 (a만 최적화)")
    logger.debug("=" * 80)
    logger.debug(f"학습 기간: {DEFAULT_TRAIN_WINDOW_MONTHS}개월 (5년)")
    logger.debug("테스트 기간: 1개월")
    logger.debug(f"고정 b 값: {b_global:.4f} (전체기간 튜닝 결과)")
    logger.debug("-" * 80)

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

    # 연속(stitched) 워크포워드 RMSE 계산
    stitched_rmse = calculate_stitched_walkforward_rmse(
        walkforward_result_df=result_df,
        underlying_df=qqq_df,
        actual_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
    )
    summary["stitched_rmse"] = stitched_rmse

    _log_summary(
        "b 고정 워크포워드 검증 결과 요약",
        summary,
        stitched_rmse,
        extra_lines=[f"고정 b 값: {b_global:.4f}"],
    )

    # CSV 저장
    _save_results(result_df, summary, TQQQ_WALKFORWARD_FIXED_B_PATH, TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH)

    # 메타데이터 저장
    metadata = _build_common_metadata(summary, stitched_rmse, elapsed_time)
    metadata["b_mode"] = "fixed"
    metadata["b_fixed_value"] = round(b_global, 4)
    metadata["b_source"] = "global_tuning"
    metadata["input_files"]["tuning_csv"] = str(SOFTPLUS_TUNING_CSV_PATH)
    metadata["output_files"] = {
        "walkforward_csv": str(TQQQ_WALKFORWARD_FIXED_B_PATH),
        "walkforward_summary_csv": str(TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH),
    }

    save_metadata("tqqq_walkforward_fixed_b", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")


def _run_fixed_ab(
    qqq_df: pd.DataFrame,
    tqqq_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    a_global: float,
    b_global: float,
) -> None:
    """완전 고정 (a,b) 워크포워드 검증을 실행한다 (과최적화 진단).

    Args:
        qqq_df: QQQ DataFrame
        tqqq_df: TQQQ DataFrame
        ffr_df: FFR DataFrame
        expense_df: Expense Ratio DataFrame
        a_global: 전체기간 최적 a 값
        b_global: 전체기간 최적 b 값
    """
    logger.debug("=" * 80)
    logger.debug("모드 3: 완전 고정 (a,b) 워크포워드 검증 (과최적화 진단)")
    logger.debug("=" * 80)
    logger.debug(f"학습 기간: {DEFAULT_TRAIN_WINDOW_MONTHS}개월 (5년)")
    logger.debug("테스트 기간: 1개월")
    logger.debug(f"고정 a 값: {a_global:.4f} (전체기간 튜닝 결과)")
    logger.debug(f"고정 b 값: {b_global:.4f} (전체기간 튜닝 결과)")
    logger.debug("-" * 80)

    start_time = time.perf_counter()

    # 월별 테스트 RMSE 산출 (워크포워드 윈도우 구조 활용)
    result_df = run_fixed_ab_walkforward(
        qqq_df=qqq_df,
        tqqq_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
        a=a_global,
        b=b_global,
    )

    # 연속(stitched) 워크포워드 RMSE 계산
    stitched_rmse = calculate_fixed_ab_stitched_rmse(
        underlying_df=qqq_df,
        actual_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
        a=a_global,
        b=b_global,
    )

    # 금리 구간별 RMSE 분해
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

    # 요약 통계 계산
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

    # 금리 구간별 RMSE 추가
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

    _log_summary(
        "완전 고정 (a,b) 워크포워드 검증 결과 요약",
        summary,
        stitched_rmse,
        extra_lines=[
            f"고정 a 값: {a_global:.4f}",
            f"고정 b 값: {b_global:.4f}",
            f"금리 구간별 RMSE (저금리 <{DEFAULT_RATE_BOUNDARY_PCT}%): {rate_segmented['low_rate_rmse']}",
            f"금리 구간별 RMSE (고금리 >={DEFAULT_RATE_BOUNDARY_PCT}%): {rate_segmented['high_rate_rmse']}",
            f"저금리 거래일 수: {rate_segmented['low_rate_days']}",
            f"고금리 거래일 수: {rate_segmented['high_rate_days']}",
        ],
    )

    # CSV 저장
    _save_results(result_df, summary, TQQQ_WALKFORWARD_FIXED_AB_PATH, TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH)

    # 메타데이터 저장
    metadata = _build_common_metadata(summary, stitched_rmse, elapsed_time)
    metadata["ab_mode"] = "fixed"
    metadata["a_fixed_value"] = round(a_global, 4)
    metadata["b_fixed_value"] = round(b_global, 4)
    metadata["ab_source"] = "global_tuning"
    metadata["rate_segmented_rmse"] = {
        "low_rate_rmse": round(rate_segmented["low_rate_rmse"], 4)
        if rate_segmented["low_rate_rmse"] is not None
        else None,
        "high_rate_rmse": round(rate_segmented["high_rate_rmse"], 4)
        if rate_segmented["high_rate_rmse"] is not None
        else None,
        "low_rate_days": rate_segmented["low_rate_days"],
        "high_rate_days": rate_segmented["high_rate_days"],
        "rate_boundary_pct": rate_segmented["rate_boundary_pct"],
    }
    metadata["input_files"]["tuning_csv"] = str(SOFTPLUS_TUNING_CSV_PATH)
    metadata["output_files"] = {
        "walkforward_csv": str(TQQQ_WALKFORWARD_FIXED_AB_PATH),
        "walkforward_summary_csv": str(TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH),
    }

    save_metadata("tqqq_walkforward_fixed_ab", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    3가지 모드를 순차 실행한다:
      1. 동적 워크포워드 (a, b 모두 최적화)
      2. b 고정 워크포워드 (a만 최적화)
      3. 완전 고정 (a,b) 워크포워드 (과최적화 진단)

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 튜닝 CSV 존재 확인 + (a_global, b_global) 로드
    if not SOFTPLUS_TUNING_CSV_PATH.exists():
        raise FileNotFoundError(
            f"튜닝 결과 CSV가 없습니다: {SOFTPLUS_TUNING_CSV_PATH}\n"
            f"먼저 실행: poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py"
        )

    tuning_df = pd.read_csv(SOFTPLUS_TUNING_CSV_PATH)
    a_global = float(tuning_df.iloc[0][COL_A])
    b_global = float(tuning_df.iloc[0][COL_B])
    logger.debug(f"전체기간 최적 (a, b) 로드: a={a_global:.4f}, b={b_global:.4f}")

    # 2. QQQ, TQQQ, FFR, Expense 데이터 로드 (1회, 공유)
    logger.debug("QQQ, TQQQ, FFR 및 Expense Ratio 데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)

    # 3. SPREAD_LAB_DIR 생성
    SPREAD_LAB_DIR.mkdir(parents=True, exist_ok=True)

    # 4. 모드 1: 동적 워크포워드
    _run_standard(qqq_df, tqqq_df, ffr_df, expense_df)

    # 5. 모드 2: b 고정 워크포워드
    _run_fixed_b(qqq_df, tqqq_df, ffr_df, expense_df, b_global)

    # 6. 모드 3: 완전 고정 (a,b) 워크포워드
    _run_fixed_ab(qqq_df, tqqq_df, ffr_df, expense_df, a_global, b_global)

    return 0


if __name__ == "__main__":
    sys.exit(main())
