"""
룩업테이블 스프레드 모델 워크포워드 검증 스크립트

인샘플 최적 조합(bin_width, stat_func)으로 워크포워드 검증을 수행한다.
60개월 훈련 / 1개월 테스트 슬라이딩 윈도우로,
각 훈련 윈도우의 실현 스프레드로 룩업테이블을 구축하고 테스트 월에 적용한다.

사전 준비:
    poetry run python scripts/tqqq/spread_lab/tune_lookup_params.py

실행 명령어:
    poetry run python scripts/tqqq/spread_lab/validate_walkforward_lookup.py
"""

import sys
import time
from datetime import date

import numpy as np
import pandas as pd

from qbt.common_constants import COL_CLOSE, COL_DATE, EPSILON, QQQ_DATA_PATH
from qbt.tqqq.analysis_helpers import (
    LOOKUP_WALKFORWARD_REQUIRED_COLUMNS,
    save_walkforward_results,
    save_walkforward_summary,
)
from qbt.tqqq.constants import (
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_TRAIN_WINDOW_MONTHS,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    KEY_OVERLAP_DAYS,
    LOOKUP_TUNING_CSV_PATH,
    LOOKUP_WALKFORWARD_PATH,
    LOOKUP_WALKFORWARD_SUMMARY_PATH,
    SPREAD_LAB_DIR,
    TQQQ_DATA_PATH,
)
from qbt.tqqq.data_loader import create_ffr_dict, load_expense_ratio_data, load_ffr_data, lookup_ffr
from qbt.tqqq.lookup_spread import (
    build_lookup_table,
    build_monthly_spread_map_from_lookup,
    calculate_realized_spread,
    lookup_spread_from_table,
)
from qbt.tqqq.simulation import (
    calculate_validation_metrics,
    extract_overlap_period,
    simulate,
)
from qbt.tqqq.types import WalkforwardSummaryDict
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """룩업테이블 워크포워드 검증 메인 함수"""
    start_time = time.time()

    # 1. 인샘플 최적 조합 로드
    logger.debug("인샘플 최적 조합 로드")
    if not LOOKUP_TUNING_CSV_PATH.exists():
        raise FileNotFoundError(f"인샘플 튜닝 결과가 없습니다. 먼저 tune_lookup_params.py를 실행하세요: " f"{LOOKUP_TUNING_CSV_PATH}")

    tuning_df = pd.read_csv(LOOKUP_TUNING_CSV_PATH)
    best_row = tuning_df.iloc[0]  # RMSE 기준 정렬되어 있음
    bin_width_pct: float = float(best_row["bin_width_pct"])
    stat_func: str = str(best_row["stat_func"])
    logger.debug(f"최적 조합: bin_width={bin_width_pct}%, stat_func={stat_func}")

    # 2. 데이터 로딩
    logger.debug("데이터 로딩")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)

    # 3. 워크포워드 실행
    logger.debug("워크포워드 검증 시작")
    result_df, stitched_rmse = _run_lookup_walkforward(
        qqq_df=qqq_df,
        tqqq_df=tqqq_df,
        ffr_df=ffr_df,
        expense_df=expense_df,
        bin_width_pct=bin_width_pct,
        stat_func=stat_func,
    )

    # 4. 요약 통계 계산
    test_rmse_values = result_df["test_rmse_pct"].dropna().to_numpy(dtype=np.float64)
    summary: WalkforwardSummaryDict = {
        "test_rmse_mean": float(np.mean(test_rmse_values)),
        "test_rmse_median": float(np.median(test_rmse_values)),
        "test_rmse_std": float(np.std(test_rmse_values)),
        "test_rmse_min": float(np.min(test_rmse_values)),
        "test_rmse_max": float(np.max(test_rmse_values)),
        "a_mean": 0.0,  # 룩업테이블 모델: softplus 파라미터 없음
        "a_std": 0.0,
        "b_mean": 0.0,
        "b_std": 0.0,
        "n_test_months": len(test_rmse_values),
        "train_window_months": DEFAULT_TRAIN_WINDOW_MONTHS,
        "stitched_rmse": stitched_rmse,
    }

    logger.debug("=== 워크포워드 검증 결과 ===")
    logger.debug(f"  모델: 룩업테이블 (bin_width={bin_width_pct}%, stat={stat_func})")
    logger.debug(f"  테스트 월수: {summary['n_test_months']}")
    logger.debug(f"  월별 RMSE 평균: {summary['test_rmse_mean']:.4f}%")
    logger.debug(f"  월별 RMSE 중앙값: {summary['test_rmse_median']:.4f}%")
    logger.debug(f"  Stitched RMSE: {stitched_rmse:.4f}%")

    # 5. CSV 저장
    SPREAD_LAB_DIR.mkdir(parents=True, exist_ok=True)
    save_walkforward_results(result_df, LOOKUP_WALKFORWARD_PATH, LOOKUP_WALKFORWARD_REQUIRED_COLUMNS)
    save_walkforward_summary(summary, LOOKUP_WALKFORWARD_SUMMARY_PATH)
    logger.debug(f"결과 저장: {LOOKUP_WALKFORWARD_PATH}")

    # 6. 메타데이터 저장
    elapsed = time.time() - start_time
    metadata = {
        "model_type": "lookup_table",
        "funding_spread_mode": "lookup_table_ffr_monthly",
        "walkforward_settings": {
            "train_window_months": DEFAULT_TRAIN_WINDOW_MONTHS,
            "test_step_months": 1,
            "bin_width_pct": bin_width_pct,
            "stat_func": stat_func,
        },
        "summary": summary,
        "elapsed_time_sec": round(elapsed, 1),
        "input_files": {
            "qqq": str(QQQ_DATA_PATH),
            "tqqq": str(TQQQ_DATA_PATH),
            "ffr": str(FFR_DATA_PATH),
            "expense": str(EXPENSE_RATIO_DATA_PATH),
            "tuning_csv": str(LOOKUP_TUNING_CSV_PATH),
        },
        "output_files": {
            "walkforward_csv": str(LOOKUP_WALKFORWARD_PATH),
            "summary_csv": str(LOOKUP_WALKFORWARD_SUMMARY_PATH),
        },
    }
    save_metadata("tqqq_lookup_walkforward", metadata)

    logger.debug(f"완료 (소요시간: {elapsed:.1f}초)")
    return 0


def _run_lookup_walkforward(
    qqq_df: pd.DataFrame,
    tqqq_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    bin_width_pct: float,
    stat_func: str,
) -> tuple[pd.DataFrame, float]:
    """
    룩업테이블 워크포워드 검증을 수행한다.

    각 윈도우에서 훈련 기간의 실현 스프레드로 룩업테이블을 구축하고,
    테스트 월에 적용하여 RMSE를 산출한다.
    추가로 stitched RMSE를 계산한다 (테스트 구간을 이어붙여 연속 시뮬레이션).

    Args:
        qqq_df: QQQ DataFrame
        tqqq_df: TQQQ DataFrame
        ffr_df: FFR DataFrame
        expense_df: Expense Ratio DataFrame
        bin_width_pct: 금리 구간 폭 (%)
        stat_func: 통계량 ("mean" 또는 "median")

    Returns:
        (결과 DataFrame, stitched RMSE)
    """
    leverage = DEFAULT_LEVERAGE_MULTIPLIER

    # 1. 겹치는 기간 추출
    underlying_overlap, actual_overlap = extract_overlap_period(qqq_df, tqqq_df)

    # 2. 월 컬럼 추가
    underlying_overlap = underlying_overlap.copy()
    actual_overlap = actual_overlap.copy()
    underlying_overlap["_month"] = underlying_overlap[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")
    actual_overlap["_month"] = actual_overlap[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")

    # 3. 고유 월 리스트
    months = sorted(underlying_overlap["_month"].unique())
    total_months = len(months)

    min_required = DEFAULT_TRAIN_WINDOW_MONTHS + 1
    if total_months < min_required:
        raise ValueError(f"데이터 부족: 워크포워드에 최소 {min_required}개월 필요, " f"현재 {total_months}개월")

    first_test_idx = DEFAULT_TRAIN_WINDOW_MONTHS
    test_month_indices = list(range(first_test_idx, total_months))

    # 4. FFR 딕셔너리 (spread_test 계산용)
    ffr_dict_for_spread = create_ffr_dict(ffr_df)

    # 5. 워크포워드 루프
    results: list[dict[str, object]] = []
    stitched_spread_map: dict[str, float] = {}

    for i, test_idx in enumerate(test_month_indices):
        test_month = months[test_idx]
        train_start_idx = test_idx - DEFAULT_TRAIN_WINDOW_MONTHS
        train_end_idx = test_idx - 1
        train_start = months[train_start_idx]
        train_end = months[train_end_idx]

        # 5-1. 훈련 데이터 추출
        train_months_set = set(months[train_start_idx : train_end_idx + 1])
        train_underlying = underlying_overlap[underlying_overlap["_month"].isin(train_months_set)].copy()
        train_actual = actual_overlap[actual_overlap["_month"].isin(train_months_set)].copy()

        # 5-2. 훈련 데이터로 실현 스프레드 역산
        train_realized = calculate_realized_spread(
            qqq_df=train_underlying.drop(columns=["_month"]),
            tqqq_df=train_actual.drop(columns=["_month"]),
            ffr_df=ffr_df,
            expense_df=expense_df,
            leverage=leverage,
        )

        # 5-3. 룩업테이블 구축
        lookup_table = build_lookup_table(train_realized, bin_width_pct, stat_func)

        # 5-4. 테스트 데이터 추출
        test_underlying = underlying_overlap[underlying_overlap["_month"] == test_month].copy()
        test_actual = actual_overlap[actual_overlap["_month"] == test_month].copy()

        # 5-5. 테스트 RMSE 계산
        if len(test_underlying) > 0 and len(test_actual) > 0:
            test_initial_price = float(test_actual.iloc[0][COL_CLOSE])

            # 테스트 월의 스프레드 결정
            test_spread_map = build_monthly_spread_map_from_lookup(ffr_df, lookup_table, bin_width_pct)

            sim_test = simulate(
                underlying_df=test_underlying.drop(columns=["_month"]),
                leverage=leverage,
                expense_df=expense_df,
                initial_price=test_initial_price,
                ffr_df=ffr_df,
                funding_spread=test_spread_map,
            )

            test_metrics = calculate_validation_metrics(
                simulated_df=sim_test,
                actual_df=test_actual.drop(columns=["_month"]),
                output_path=None,
            )

            test_rmse = test_metrics[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]
            n_test_days = test_metrics[KEY_OVERLAP_DAYS]
        else:
            test_rmse = float("nan")
            n_test_days = 0

        # 5-6. 테스트 월의 FFR 및 스프레드 기록
        test_year, test_mon = map(int, test_month.split("-"))
        test_date = date(test_year, test_mon, 1)
        ffr_ratio_test = lookup_ffr(test_date, ffr_dict_for_spread)
        ffr_pct_test = ffr_ratio_test * 100.0
        spread_test_val = lookup_spread_from_table(ffr_pct_test, lookup_table, bin_width_pct)

        # stitched용 스프레드 저장 (simulate()는 양수만 허용 → 음수/0은 EPSILON 클램핑)
        stitched_spread_map[test_month] = max(spread_test_val, EPSILON)

        result: dict[str, object] = {
            "train_start": train_start,
            "train_end": train_end,
            "test_month": test_month,
            "bin_width_pct": bin_width_pct,
            "stat_func": stat_func,
            "test_rmse_pct": test_rmse,
            "n_train_days": len(train_underlying),
            "n_test_days": n_test_days,
            "n_bins": len(lookup_table),
            "ffr_pct_test": ffr_pct_test,
            "spread_test": spread_test_val,
        }
        results.append(result)

        logger.debug(
            f"룩업테이블 WF [{i + 1}/{len(test_month_indices)}] "
            f"test={test_month}, test_rmse={test_rmse:.4f}%, "
            f"n_bins={len(lookup_table)}"
        )

    result_df = pd.DataFrame(results)

    # 6. Stitched RMSE 계산
    stitched_rmse = _calculate_stitched_rmse(
        underlying_overlap=underlying_overlap,
        actual_overlap=actual_overlap,
        months=months,
        stitched_spread_map=stitched_spread_map,
        ffr_df=ffr_df,
        expense_df=expense_df,
        leverage=leverage,
    )

    return result_df, stitched_rmse


def _calculate_stitched_rmse(
    underlying_overlap: pd.DataFrame,
    actual_overlap: pd.DataFrame,
    months: list[str],
    stitched_spread_map: dict[str, float],
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    leverage: float,
) -> float:
    """
    테스트 구간을 이어붙여 연속 시뮬레이션의 stitched RMSE를 계산한다.

    워크포워드에서 각 테스트 월에 사용한 스프레드를 그대로 적용하여
    테스트 기간 전체를 하나의 연속 시뮬레이션으로 실행한다.

    Args:
        underlying_overlap: 월 컬럼이 포함된 QQQ overlap DataFrame
        actual_overlap: 월 컬럼이 포함된 TQQQ overlap DataFrame
        months: 고유 월 리스트
        stitched_spread_map: 테스트 월별 스프레드 매핑
        ffr_df: FFR DataFrame
        expense_df: Expense Ratio DataFrame
        leverage: 레버리지 배율

    Returns:
        stitched RMSE (%)
    """
    first_test_month = months[DEFAULT_TRAIN_WINDOW_MONTHS]
    last_test_month = months[-1]

    # 테스트 기간 필터링
    test_underlying = underlying_overlap[
        (underlying_overlap["_month"] >= first_test_month) & (underlying_overlap["_month"] <= last_test_month)
    ].copy()
    test_actual = actual_overlap[
        (actual_overlap["_month"] >= first_test_month) & (actual_overlap["_month"] <= last_test_month)
    ].copy()

    test_underlying_clean = test_underlying.drop(columns=["_month"])
    test_actual_clean = test_actual.drop(columns=["_month"])

    # 연속 시뮬레이션
    initial_price = float(test_actual_clean.iloc[0][COL_CLOSE])
    sim_stitched = simulate(
        underlying_df=test_underlying_clean,
        leverage=leverage,
        expense_df=expense_df,
        initial_price=initial_price,
        ffr_df=ffr_df,
        funding_spread=stitched_spread_map,
    )

    # RMSE 계산
    metrics = calculate_validation_metrics(
        simulated_df=sim_stitched,
        actual_df=test_actual_clean,
        output_path=None,
    )

    return metrics[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]


if __name__ == "__main__":
    sys.exit(main())
