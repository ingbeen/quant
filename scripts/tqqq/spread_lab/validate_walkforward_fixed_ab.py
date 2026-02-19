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
from datetime import date

import numpy as np
import pandas as pd

from qbt.common_constants import COL_CLOSE, COL_DATE, META_JSON_PATH, QQQ_DATA_PATH
from qbt.tqqq.analysis_helpers import save_walkforward_results, save_walkforward_summary
from qbt.tqqq.constants import (
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_RATE_BOUNDARY_PCT,
    DEFAULT_TRAIN_WINDOW_MONTHS,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    KEY_OVERLAP_DAYS,
    SOFTPLUS_TUNING_CSV_PATH,
    SPREAD_LAB_DIR,
    TQQQ_DATA_PATH,
    TQQQ_WALKFORWARD_FIXED_AB_PATH,
    TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH,
)
from qbt.tqqq.data_loader import create_ffr_dict, load_expense_ratio_data, load_ffr_data, lookup_ffr
from qbt.tqqq.simulation import (
    _calculate_metrics_fast,
    build_monthly_spread_map,
    calculate_fixed_ab_stitched_rmse,
    calculate_rate_segmented_rmse,
    calculate_validation_metrics,
    compute_softplus_spread,
    extract_overlap_period,
    simulate,
)
from qbt.tqqq.types import WalkforwardSummaryDict
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# 튜닝 CSV 컬럼명
COL_A = "a"
COL_B = "b"


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
    result_df = _run_fixed_ab_walkforward(
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
    rate_segmented = _calculate_rate_segmented_from_stitched(
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


def _run_fixed_ab_walkforward(
    qqq_df: pd.DataFrame,
    tqqq_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    a: float,
    b: float,
) -> pd.DataFrame:
    """
    고정 (a,b)로 워크포워드 윈도우별 월간 테스트 RMSE를 산출한다.

    동적/b고정 워크포워드와 동일한 윈도우 구조를 사용하되,
    파라미터 재최적화 없이 고정 (a,b)를 그대로 적용한다.

    Args:
        qqq_df: QQQ DataFrame
        tqqq_df: TQQQ DataFrame
        ffr_df: FFR DataFrame
        expense_df: Expense Ratio DataFrame
        a: 고정 softplus a 파라미터
        b: 고정 softplus b 파라미터

    Returns:
        워크포워드 결과 DataFrame (기존과 동일 포맷)
    """
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

    min_required_months = DEFAULT_TRAIN_WINDOW_MONTHS + 1
    if total_months < min_required_months:
        raise ValueError(f"데이터 부족: 워크포워드에 최소 {min_required_months}개월 필요, " f"현재 {total_months}개월")

    # 4. 워크포워드 시작점 계산
    first_test_idx = DEFAULT_TRAIN_WINDOW_MONTHS
    test_month_indices = list(range(first_test_idx, total_months))

    # 5. 고정 spread_map 1회 생성
    spread_map = build_monthly_spread_map(ffr_df, a, b)

    # 6. FFR 딕셔너리 (spread_test 계산용)
    ffr_dict_for_spread = create_ffr_dict(ffr_df)

    # 7. 워크포워드 결과 생성
    results: list[dict[str, object]] = []

    for i, test_idx in enumerate(test_month_indices):
        test_month = months[test_idx]
        train_start_idx = test_idx - DEFAULT_TRAIN_WINDOW_MONTHS
        train_end_idx = test_idx - 1
        train_start = months[train_start_idx]
        train_end = months[train_end_idx]

        # 테스트 데이터 추출
        test_underlying = underlying_overlap[underlying_overlap["_month"] == test_month].copy()
        test_actual = actual_overlap[actual_overlap["_month"] == test_month].copy()

        # 테스트 RMSE 계산
        if len(test_underlying) > 0 and len(test_actual) > 0:
            test_initial_price = float(test_actual.iloc[0][COL_CLOSE])

            sim_test = simulate(
                underlying_df=test_underlying,
                leverage=DEFAULT_LEVERAGE_MULTIPLIER,
                expense_df=expense_df,
                initial_price=test_initial_price,
                ffr_df=ffr_df,
                funding_spread=spread_map,
            )

            test_metrics = calculate_validation_metrics(
                simulated_df=sim_test,
                actual_df=test_actual,
                output_path=None,
            )

            test_rmse = test_metrics[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]
            n_test_days = test_metrics[KEY_OVERLAP_DAYS]
        else:
            test_rmse = float("nan")
            n_test_days = 0

        # 학습 데이터로 train RMSE 계산 (고정 a,b 기준)
        train_underlying = underlying_overlap[
            underlying_overlap["_month"].isin(months[train_start_idx : train_end_idx + 1])
        ].copy()
        train_actual = actual_overlap[actual_overlap["_month"].isin(months[train_start_idx : train_end_idx + 1])].copy()

        if len(train_underlying) > 0 and len(train_actual) > 0:
            train_initial_price = float(train_actual.iloc[0][COL_CLOSE])
            sim_train = simulate(
                underlying_df=train_underlying,
                leverage=DEFAULT_LEVERAGE_MULTIPLIER,
                expense_df=expense_df,
                initial_price=train_initial_price,
                ffr_df=ffr_df,
                funding_spread=spread_map,
            )
            sim_train_overlap, actual_train_overlap = extract_overlap_period(sim_train, train_actual)
            train_actual_prices = actual_train_overlap[COL_CLOSE].to_numpy(dtype=np.float64)
            train_sim_prices = sim_train_overlap[COL_CLOSE].to_numpy(dtype=np.float64)
            train_rmse, _, _ = _calculate_metrics_fast(train_actual_prices, train_sim_prices)
        else:
            train_rmse = float("nan")

        # FFR 및 spread 계산
        test_year, test_mon = map(int, test_month.split("-"))
        test_date = date(test_year, test_mon, 1)
        ffr_ratio_test = lookup_ffr(test_date, ffr_dict_for_spread)
        ffr_pct_test = ffr_ratio_test * 100.0
        spread_test_val = compute_softplus_spread(a, b, ffr_ratio_test)

        # 결과 저장
        result: dict[str, object] = {
            "train_start": train_start,
            "train_end": train_end,
            "test_month": test_month,
            "a_best": a,
            "b_best": b,
            "train_rmse_pct": train_rmse,
            "test_rmse_pct": test_rmse,
            "n_train_days": len(train_underlying),
            "n_test_days": n_test_days,
            "search_mode": "fixed_ab",
            "ffr_pct_test": ffr_pct_test,
            "spread_test": spread_test_val,
        }
        results.append(result)

        logger.debug(
            f"완전 고정 WF [{i + 1}/{len(test_month_indices)}] "
            f"test={test_month}, train_rmse={train_rmse:.4f}%, test_rmse={test_rmse:.4f}%"
        )

    return pd.DataFrame(results)


def _calculate_rate_segmented_from_stitched(
    qqq_df: pd.DataFrame,
    tqqq_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    a: float,
    b: float,
) -> dict[str, float | int | None]:
    """
    고정 (a,b) 연속 시뮬레이션 결과에서 금리 구간별 RMSE를 분해한다.

    Args:
        qqq_df: QQQ DataFrame
        tqqq_df: TQQQ DataFrame
        ffr_df: FFR DataFrame
        expense_df: Expense Ratio DataFrame
        a: 고정 softplus a 파라미터
        b: 고정 softplus b 파라미터

    Returns:
        금리 구간별 RMSE 딕셔너리
    """
    # 1. 겹치는 기간 추출
    underlying_overlap, actual_overlap = extract_overlap_period(qqq_df, tqqq_df)

    # 2. 테스트 기간 결정
    underlying_overlap = underlying_overlap.copy()
    actual_overlap = actual_overlap.copy()
    underlying_overlap["_month"] = underlying_overlap[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")
    actual_overlap["_month"] = actual_overlap[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")

    months = sorted(underlying_overlap["_month"].unique())
    first_test_month = months[DEFAULT_TRAIN_WINDOW_MONTHS]
    last_test_month = months[-1]

    # 3. 테스트 기간 필터링
    test_underlying = underlying_overlap[
        (underlying_overlap["_month"] >= first_test_month) & (underlying_overlap["_month"] <= last_test_month)
    ].copy()
    test_actual = actual_overlap[
        (actual_overlap["_month"] >= first_test_month) & (actual_overlap["_month"] <= last_test_month)
    ].copy()

    test_underlying = test_underlying.drop(columns=["_month"])
    test_actual = test_actual.drop(columns=["_month"])

    # 4. 고정 spread_map으로 시뮬레이션
    spread_map = build_monthly_spread_map(ffr_df, a, b)
    initial_price = float(test_actual.iloc[0][COL_CLOSE])

    simulated_df = simulate(
        underlying_df=test_underlying,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
        expense_df=expense_df,
        initial_price=initial_price,
        ffr_df=ffr_df,
        funding_spread=spread_map,
    )

    # 5. 겹치는 기간 추출
    sim_overlap, actual_overlap_final = extract_overlap_period(simulated_df, test_actual)

    actual_prices = actual_overlap_final[COL_CLOSE].to_numpy(dtype=np.float64)
    simulated_prices = sim_overlap[COL_CLOSE].to_numpy(dtype=np.float64)
    dates_list: list[date] = list(actual_overlap_final[COL_DATE])

    # 6. 금리 구간별 RMSE 분해
    return calculate_rate_segmented_rmse(
        actual_prices=actual_prices,
        simulated_prices=simulated_prices,
        dates=dates_list,
        ffr_df=ffr_df,
        rate_boundary_pct=DEFAULT_RATE_BOUNDARY_PCT,
    )


if __name__ == "__main__":
    sys.exit(main())
