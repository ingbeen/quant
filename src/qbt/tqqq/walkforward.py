"""레버리지 ETF 워크포워드 검증 모듈

워크포워드 방식으로 softplus 동적 스프레드 모델의 out-of-sample 성능을 평가한다.
60개월 학습 / 1개월 테스트 윈도우 방식, 연속(stitched) RMSE, 금리 구간별 RMSE 분해,
고정 (a,b) 과최적화 진단 등을 제공한다.
"""

from datetime import date

import numpy as np
import pandas as pd

from qbt.common_constants import COL_CLOSE, COL_DATE, EPSILON
from qbt.tqqq.constants import (
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_RATE_BOUNDARY_PCT,
    DEFAULT_TRAIN_WINDOW_MONTHS,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    KEY_OVERLAP_DAYS,
    WALKFORWARD_LOCAL_REFINE_A_DELTA,
    WALKFORWARD_LOCAL_REFINE_A_STEP,
    WALKFORWARD_LOCAL_REFINE_B_DELTA,
    WALKFORWARD_LOCAL_REFINE_B_STEP,
)
from qbt.tqqq.data_loader import create_ffr_dict, lookup_ffr
from qbt.tqqq.optimization import (
    evaluate_softplus_candidate,
    find_optimal_softplus_params,
    prepare_optimization_data,
)
from qbt.tqqq.simulation import (
    build_monthly_spread_map,
    calculate_metrics_fast,
    calculate_validation_metrics,
    compute_softplus_spread,
    simulate,
)
from qbt.tqqq.types import SoftplusCandidateDict, WalkforwardSummaryDict
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period
from qbt.utils.parallel_executor import init_worker_cache

logger = get_logger(__name__)


def _local_refine_search(
    underlying_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    a_prev: float,
    b_prev: float,
    leverage: float = DEFAULT_LEVERAGE_MULTIPLIER,
    fixed_b: float | None = None,
) -> tuple[float, float, float, list[SoftplusCandidateDict]]:
    """
    직전 월 최적 (a_prev, b_prev) 주변에서 국소 탐색을 수행한다.

    워크포워드 검증에서 첫 구간 이후 사용되는 local refine 탐색 함수.
    탐색 범위:
        - a in [a_prev - DELTA_A, a_prev + DELTA_A] step STEP_A
        - b in [max(0, b_prev - DELTA_B), b_prev + DELTA_B] step STEP_B (b >= 0 제약)

    목적함수: cumul_multiple_log_diff_rmse_pct 최소화

    Args:
        underlying_df: 학습 기간 기초 자산 DataFrame
        actual_df: 학습 기간 실제 레버리지 ETF DataFrame
        ffr_df: 연방기금금리 DataFrame
        expense_df: 운용비용 DataFrame
        a_prev: 직전 월 최적 a 파라미터
        b_prev: 직전 월 최적 b 파라미터
        leverage: 레버리지 배수 (기본값: 3.0)
        fixed_b: b 파라미터 고정값 (None이면 b도 탐색, 설정 시 a만 탐색)

    Returns:
        (a_best, b_best, best_rmse, candidates) 튜플
            - a_best: 최적 절편 파라미터
            - b_best: 최적 기울기 파라미터 (fixed_b 설정 시 fixed_b와 동일)
            - best_rmse: 최적 RMSE (%)
            - candidates: 전체 탐색 결과 리스트

    Raises:
        ValueError: 겹치는 기간이 없을 때
        ValueError: FFR 또는 Expense 데이터 커버리지가 부족할 때
    """
    # 1. 공통 초기화 (겹치는 기간 추출, FFR 검증, 배열 변환)
    initial_price, cache_data = prepare_optimization_data(underlying_df, actual_df, ffr_df, expense_df)

    # 2. Local Refine 파라미터 조합 생성
    a_min = a_prev - WALKFORWARD_LOCAL_REFINE_A_DELTA
    a_max = a_prev + WALKFORWARD_LOCAL_REFINE_A_DELTA

    a_values = np.arange(a_min, a_max + EPSILON, WALKFORWARD_LOCAL_REFINE_A_STEP)
    if fixed_b is not None:
        b_values = np.array([fixed_b])
        b_log_min = fixed_b
        b_log_max = fixed_b
    else:
        b_log_min = max(0.0, b_prev - WALKFORWARD_LOCAL_REFINE_B_DELTA)  # b >= 0 제약
        b_log_max = b_prev + WALKFORWARD_LOCAL_REFINE_B_DELTA
        b_values = np.arange(b_log_min, b_log_max + EPSILON, WALKFORWARD_LOCAL_REFINE_B_STEP)

    param_combinations = []
    for a in a_values:
        for b in b_values:
            param_combinations.append(
                {
                    "a": float(a),
                    "b": float(b),
                    "leverage": leverage,
                    "initial_price": initial_price,
                }
            )

    logger.debug(
        f"Local Refine 탐색: a in [{a_min:.4f}, {a_max:.4f}], "
        f"b in [{b_log_min:.4f}, {b_log_max:.4f}], 조합 수: {len(param_combinations)}"
    )

    # 3. 순차 실행
    init_worker_cache(dict(cache_data))
    candidates = [evaluate_softplus_candidate(p) for p in param_combinations]

    # 4. RMSE 기준 정렬 및 최적값 추출
    candidates.sort(key=lambda x: x[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE])
    best = candidates[0]
    a_best = best["a"]
    b_best = best["b"]
    best_rmse = best[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]

    logger.debug(f"Local Refine 완료: a_best={a_best:.4f}, b_best={b_best:.4f}, RMSE={best_rmse:.4f}%")

    return a_best, b_best, best_rmse, candidates


def run_walkforward_validation(
    underlying_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    leverage: float = DEFAULT_LEVERAGE_MULTIPLIER,
    train_window_months: int = DEFAULT_TRAIN_WINDOW_MONTHS,
    fixed_b: float | None = None,
) -> tuple[pd.DataFrame, WalkforwardSummaryDict]:
    """
    워크포워드 검증을 수행한다 (60개월 Train, 1개월 Test).

    워크포워드 시작점은 train_window_months 학습이 가능한 첫 달부터 자동 계산된다.
    첫 구간은 2-stage grid search, 이후 구간은 local refine으로 (a, b) 파라미터를 튜닝한다.
    테스트 월의 spread 계산에는 해당 월 FFR 값을 사용한다 (A안).

    Args:
        underlying_df: 기초 자산 DataFrame (QQQ)
        actual_df: 실제 레버리지 ETF DataFrame (TQQQ)
        ffr_df: 연방기금금리 DataFrame
        expense_df: 운용비용 DataFrame
        leverage: 레버리지 배수 (기본값: 3.0)
        train_window_months: 학습 기간 (기본값: 60개월)
        fixed_b: b 파라미터 고정값 (None이면 b도 최적화, 설정 시 a만 최적화)

    Returns:
        (result_df, summary) 튜플
            - result_df: 워크포워드 결과 DataFrame
            - summary: 요약 통계 딕셔너리

    Raises:
        ValueError: 데이터 부족 (train_window_months + 1 개월 미만)
        ValueError: FFR 또는 Expense 데이터 커버리지가 부족할 때
    """
    # 1. 겹치는 기간 추출
    underlying_overlap, actual_overlap = extract_overlap_period(underlying_df, actual_df)

    # 2. 월별 그룹핑을 위한 월 컬럼 추가
    underlying_overlap = underlying_overlap.copy()
    actual_overlap = actual_overlap.copy()
    underlying_overlap["_month"] = underlying_overlap[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")
    actual_overlap["_month"] = actual_overlap[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")

    # 3. 고유 월 리스트 추출 및 정렬
    months = sorted(underlying_overlap["_month"].unique())
    total_months = len(months)

    # 4. 데이터 부족 검증
    min_required_months = train_window_months + 1  # train + test 1개월
    if total_months < min_required_months:
        raise ValueError(
            f"데이터 부족: 워크포워드에 최소 {min_required_months}개월 필요, "
            f"현재 {total_months}개월\n"
            f"기간: {months[0]} ~ {months[-1]}\n"
            f"조치: 더 긴 기간의 데이터 사용"
        )

    # 5. 워크포워드 시작점 계산
    # 첫 테스트 월 인덱스 = train_window_months (0-indexed)
    first_test_idx = train_window_months
    test_month_indices = list(range(first_test_idx, total_months))

    logger.debug(
        f"워크포워드 설정: train={train_window_months}개월, "
        f"테스트 월 수={len(test_month_indices)}, "
        f"첫 테스트 월={months[first_test_idx]}"
    )

    # 6. FFR 딕셔너리 생성 (한 번만, spread_test 계산용)
    ffr_dict_for_spread = create_ffr_dict(ffr_df)

    # 7. 워크포워드 결과 저장 리스트
    results: list[dict[str, object]] = []
    a_prev: float | None = None
    b_prev: float | None = None

    # 8. 각 테스트 월에 대해 워크포워드 수행
    for i, test_idx in enumerate(test_month_indices):
        test_month = months[test_idx]
        train_start_idx = test_idx - train_window_months
        train_end_idx = test_idx - 1  # 테스트 직전 월까지

        train_months = months[train_start_idx : train_end_idx + 1]
        train_start = train_months[0]
        train_end = train_months[-1]

        # 학습 데이터 추출
        train_underlying = underlying_overlap[underlying_overlap["_month"].isin(train_months)].copy()
        train_actual = actual_overlap[actual_overlap["_month"].isin(train_months)].copy()

        # 테스트 데이터 추출
        test_underlying = underlying_overlap[underlying_overlap["_month"] == test_month].copy()
        test_actual = actual_overlap[actual_overlap["_month"] == test_month].copy()

        # 9. 파라미터 튜닝
        if i == 0:
            # 첫 구간: 2-stage grid search
            search_mode = "full_grid_2stage"
            a_best, b_best, train_rmse, _ = find_optimal_softplus_params(
                underlying_df=train_underlying,
                actual_leveraged_df=train_actual,
                ffr_df=ffr_df,
                expense_df=expense_df,
                leverage=leverage,
                fixed_b=fixed_b,
            )
        else:
            # 이후 구간: local refine
            search_mode = "local_refine"
            assert a_prev is not None and b_prev is not None
            a_best, b_best, train_rmse, _ = _local_refine_search(
                underlying_df=train_underlying,
                actual_df=train_actual,
                ffr_df=ffr_df,
                expense_df=expense_df,
                a_prev=a_prev,
                b_prev=b_prev,
                leverage=leverage,
                fixed_b=fixed_b,
            )

        # 10. 테스트 월 RMSE 계산
        # softplus spread 맵 생성
        spread_map = build_monthly_spread_map(ffr_df, a_best, b_best)

        # 테스트 기간 시뮬레이션
        if len(test_underlying) > 0 and len(test_actual) > 0:
            test_initial_price = float(test_actual.iloc[0][COL_CLOSE])

            sim_test = simulate(
                underlying_df=test_underlying,
                leverage=leverage,
                expense_df=expense_df,
                initial_price=test_initial_price,
                ffr_df=ffr_df,
                funding_spread=spread_map,
            )

            # 테스트 검증 지표 계산
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

        # 11. 테스트 월 FFR 및 spread 계산
        test_year, test_mon = map(int, test_month.split("-"))
        test_date = date(test_year, test_mon, 1)
        ffr_ratio_test = lookup_ffr(test_date, ffr_dict_for_spread)
        ffr_pct_test = ffr_ratio_test * 100.0
        spread_test_val = compute_softplus_spread(a_best, b_best, ffr_ratio_test)

        # 12. 결과 저장
        result: dict[str, object] = {
            "train_start": train_start,
            "train_end": train_end,
            "test_month": test_month,
            "a_best": a_best,
            "b_best": b_best,
            "train_rmse_pct": train_rmse,
            "test_rmse_pct": test_rmse,
            "n_train_days": len(train_underlying),
            "n_test_days": n_test_days,
            "search_mode": search_mode,
            "ffr_pct_test": ffr_pct_test,
            "spread_test": spread_test_val,
        }
        results.append(result)

        # 13. 다음 구간을 위해 현재 최적값 저장
        a_prev = a_best
        b_prev = b_best

        logger.debug(
            f"워크포워드 [{i + 1}/{len(test_month_indices)}] "
            f"test={test_month}, a={a_best:.4f}, b={b_best:.4f}, "
            f"train_rmse={train_rmse:.4f}%, test_rmse={test_rmse:.4f}%"
        )

    # 14. 결과 DataFrame 생성
    result_df = pd.DataFrame(results)

    # 15. 요약 통계 계산
    test_rmse_values = result_df["test_rmse_pct"].dropna()
    a_values = result_df["a_best"]
    b_values = result_df["b_best"]

    summary: WalkforwardSummaryDict = {
        "test_rmse_mean": float(test_rmse_values.mean()) if len(test_rmse_values) > 0 else float("nan"),
        "test_rmse_median": float(test_rmse_values.median()) if len(test_rmse_values) > 0 else float("nan"),
        "test_rmse_std": float(test_rmse_values.std()) if len(test_rmse_values) > 0 else float("nan"),
        "test_rmse_min": float(test_rmse_values.min()) if len(test_rmse_values) > 0 else float("nan"),
        "test_rmse_max": float(test_rmse_values.max()) if len(test_rmse_values) > 0 else float("nan"),
        "a_mean": float(a_values.mean()),
        "a_std": float(a_values.std()),
        "b_mean": float(b_values.mean()),
        "b_std": float(b_values.std()),
        "n_test_months": len(test_month_indices),
        "train_window_months": train_window_months,
    }

    logger.debug(
        f"워크포워드 완료: {summary['n_test_months']}개월 테스트, "
        f"test_rmse 평균={summary['test_rmse_mean']:.4f}%, "
        f"a 평균={summary['a_mean']:.4f} (std={summary['a_std']:.4f}), "
        f"b 평균={summary['b_mean']:.4f} (std={summary['b_std']:.4f})"
    )

    return result_df, summary


def _simulate_stitched_periods(
    underlying_overlap: pd.DataFrame,
    actual_overlap: pd.DataFrame,
    first_test_month: str,
    last_test_month: str,
    spread_map: dict[str, float],
    expense_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    leverage: float,
) -> float:
    """
    테스트 기간을 필터링하고 연속 시뮬레이션하여 RMSE를 계산한다.

    calculate_stitched_walkforward_rmse와 calculate_fixed_ab_stitched_rmse의
    공통 로직(기간 필터링, 시뮬레이션, RMSE 산출)을 추출한 헬퍼 함수.

    Args:
        underlying_overlap: 겹치는 기간의 기초 자산 DataFrame
        actual_overlap: 겹치는 기간의 실제 레버리지 ETF DataFrame
        first_test_month: 첫 테스트 월 (yyyy-mm)
        last_test_month: 마지막 테스트 월 (yyyy-mm)
        spread_map: 월별 funding spread 딕셔너리 ({"yyyy-mm": spread})
        expense_df: 운용비용 DataFrame
        ffr_df: 연방기금금리 DataFrame
        leverage: 레버리지 배수

    Returns:
        연속 시뮬레이션 RMSE (%, 누적배수 로그차이 기반)

    Raises:
        ValueError: 테스트 기간에 해당하는 데이터가 부족할 때
    """
    # 1. 월 컬럼 생성 및 테스트 기간 필터링
    underlying_with_month = underlying_overlap.copy()
    actual_with_month = actual_overlap.copy()
    underlying_with_month["_month"] = underlying_with_month[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")
    actual_with_month["_month"] = actual_with_month[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")

    # 2. 테스트 기간 필터링
    test_underlying = underlying_with_month[
        (underlying_with_month["_month"] >= first_test_month) & (underlying_with_month["_month"] <= last_test_month)
    ].copy()
    test_actual = actual_with_month[
        (actual_with_month["_month"] >= first_test_month) & (actual_with_month["_month"] <= last_test_month)
    ].copy()

    # _month 컬럼 제거 (simulate에 불필요)
    test_underlying = test_underlying.drop(columns=["_month"])
    test_actual = test_actual.drop(columns=["_month"])

    if test_underlying.empty or test_actual.empty:
        raise ValueError(f"테스트 기간({first_test_month} ~ {last_test_month})에 해당하는 데이터가 없습니다")

    # 3. initial_price 설정 (첫 테스트일의 실제 TQQQ 가격)
    initial_price = float(test_actual.iloc[0][COL_CLOSE])

    # 4. 연속 시뮬레이션 실행 (spread_map을 FundingSpreadSpec dict로 전달)
    simulated_df = simulate(
        underlying_df=test_underlying,
        leverage=leverage,
        expense_df=expense_df,
        initial_price=initial_price,
        ffr_df=ffr_df,
        funding_spread=spread_map,
    )

    # 5. RMSE 계산
    sim_overlap, actual_overlap_final = extract_overlap_period(simulated_df, test_actual)

    actual_prices = actual_overlap_final[COL_CLOSE].to_numpy(dtype=np.float64)
    simulated_prices = sim_overlap[COL_CLOSE].to_numpy(dtype=np.float64)

    rmse, _, _ = calculate_metrics_fast(actual_prices, simulated_prices)

    return rmse


def calculate_stitched_walkforward_rmse(
    walkforward_result_df: pd.DataFrame,
    underlying_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    leverage: float = DEFAULT_LEVERAGE_MULTIPLIER,
) -> float:
    """
    워크포워드 결과를 연속으로 붙인(stitched) 시뮬레이션의 RMSE를 계산한다.

    기존 워크포워드 평균 RMSE는 월별 initial_price 리셋 방식이라 누적 오차가 상쇄된다.
    이 함수는 전체 테스트 기간을 연속 시뮬레이션하여 정적 RMSE와 동일 정의로 비교 가능하게 한다.

    동작 방식:
        1. 워크포워드 result_df에서 test_month -> spread_test 매핑 생성
        2. 첫 테스트 월 ~ 마지막 테스트 월의 기초자산/실제 데이터 필터링
        3. 첫 테스트 월의 실제 가격을 initial_price로 설정
        4. spread_test를 월별 funding_spread로 사용하여 전체 기간 1회 연속 시뮬레이션
        5. 정적 RMSE와 동일 수식(누적배수 로그차이 RMSE)으로 산출

    RMSE 수식 (정적 RMSE와 동일):
        M_actual(t) = actual_prices(t) / actual_prices(0)
        M_simul(t) = simulated_prices(t) / simulated_prices(0)
        log_diff_abs_pct = |ln(M_actual / M_simul)| * 100
        RMSE = sqrt(mean(log_diff_abs_pct²)), 단위: %

    Args:
        walkforward_result_df: 워크포워드 결과 DataFrame (test_month, spread_test 컬럼 필수)
        underlying_df: 기초 자산 DataFrame (QQQ, Date/Close 컬럼 필수)
        actual_df: 실제 레버리지 ETF DataFrame (TQQQ, Date/Close 컬럼 필수)
        ffr_df: 연방기금금리 DataFrame (DATE: str (yyyy-mm), VALUE: float)
        expense_df: 운용비용 DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율))
        leverage: 레버리지 배수 (기본값: 3.0)

    Returns:
        연속 워크포워드 RMSE (%, 누적배수 로그차이 기반)

    Raises:
        ValueError: walkforward_result_df가 비어있을 때
        ValueError: 필수 컬럼(test_month, spread_test)이 누락되었을 때
        ValueError: 테스트 기간에 해당하는 데이터가 부족할 때
    """
    # 1. 입력 검증
    if walkforward_result_df.empty:
        raise ValueError("walkforward_result_df가 비어있습니다")

    required_cols = {"test_month", "spread_test"}
    missing_cols = required_cols - set(walkforward_result_df.columns)
    if missing_cols:
        raise ValueError(f"워크포워드 결과에 필수 컬럼이 누락되었습니다: {missing_cols}")

    # 2. test_month -> spread_test 매핑 생성
    spread_map: dict[str, float] = dict(
        zip(
            walkforward_result_df["test_month"].astype(str),
            walkforward_result_df["spread_test"].astype(float),
            strict=True,
        )
    )

    # 3. 테스트 기간 결정
    test_months_sorted = sorted(spread_map.keys())
    first_test_month = test_months_sorted[0]
    last_test_month = test_months_sorted[-1]

    # 4. 겹치는 기간 추출
    underlying_overlap, actual_overlap = extract_overlap_period(underlying_df, actual_df)

    # 5. 연속 시뮬레이션 및 RMSE 계산
    rmse = _simulate_stitched_periods(
        underlying_overlap=underlying_overlap,
        actual_overlap=actual_overlap,
        first_test_month=first_test_month,
        last_test_month=last_test_month,
        spread_map=spread_map,
        expense_df=expense_df,
        ffr_df=ffr_df,
        leverage=leverage,
    )

    logger.debug(f"연속 워크포워드 RMSE 계산 완료: {rmse:.4f}% " f"(기간: {first_test_month} ~ {last_test_month})")

    return rmse


def calculate_fixed_ab_stitched_rmse(
    underlying_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    a: float,
    b: float,
    train_window_months: int = DEFAULT_TRAIN_WINDOW_MONTHS,
    leverage: float = DEFAULT_LEVERAGE_MULTIPLIER,
) -> float:
    """
    전체기간 최적 고정 (a, b)를 아웃오브샘플에 그대로 적용한 stitched RMSE를 계산한다.

    기존 calculate_stitched_walkforward_rmse()와 유사하지만, 워크포워드 result_df 대신
    고정 (a, b)와 FFR로 spread_map을 직접 1회 생성하여 사용한다.
    파라미터 재최적화 없이 고정값을 그대로 적용하므로, 인샘플/아웃오브샘플 격차를 통해
    과최적화 여부를 진단할 수 있다.

    동작 방식:
        1. 겹치는 기간 추출 (extract_overlap_period)
        2. 테스트 기간 결정 (train_window_months 이후부터 끝까지)
        3. build_monthly_spread_map(ffr_df, a, b)로 고정 spread_map 1회 생성
        4. simulate() 연속 실행 (initial_price = 첫 테스트일 실제 가격)
        5. calculate_metrics_fast()로 RMSE 산출

    Args:
        underlying_df: 기초 자산 DataFrame (QQQ, Date/Close 컬럼 필수)
        actual_df: 실제 레버리지 ETF DataFrame (TQQQ, Date/Close 컬럼 필수)
        ffr_df: 연방기금금리 DataFrame (DATE: str (yyyy-mm), VALUE: float)
        expense_df: 운용비용 DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율))
        a: softplus 절편 파라미터 (전체기간 최적값)
        b: softplus 기울기 파라미터 (전체기간 최적값)
        train_window_months: 학습 기간 (기본값: 60개월), 테스트 시작점 결정에 사용
        leverage: 레버리지 배수 (기본값: 3.0)

    Returns:
        연속 고정 (a,b) 워크포워드 RMSE (%, 누적배수 로그차이 기반)

    Raises:
        ValueError: 데이터가 비어있을 때
        ValueError: 테스트 기간에 해당하는 데이터가 부족할 때
    """
    # 1. 입력 검증
    if underlying_df.empty or actual_df.empty:
        raise ValueError("underlying_df 또는 actual_df가 비어있습니다")

    if ffr_df.empty:
        raise ValueError("ffr_df가 비어있습니다")

    # 2. 겹치는 기간 추출
    underlying_overlap, actual_overlap = extract_overlap_period(underlying_df, actual_df)

    # 3. 테스트 기간 결정 (train_window_months 이후부터 끝까지)
    underlying_with_month = underlying_overlap.copy()
    underlying_with_month["_month"] = underlying_with_month[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")

    months = sorted(underlying_with_month["_month"].unique())
    total_months = len(months)

    min_required_months = train_window_months + 1
    if total_months < min_required_months:
        raise ValueError(f"데이터 부족: 워크포워드에 최소 {min_required_months}개월 필요, " f"현재 {total_months}개월")

    first_test_month = months[train_window_months]
    last_test_month = months[-1]

    # 4. 고정 spread_map 1회 생성
    spread_map = build_monthly_spread_map(ffr_df, a, b)

    # 5. 연속 시뮬레이션 및 RMSE 계산
    rmse = _simulate_stitched_periods(
        underlying_overlap=underlying_overlap,
        actual_overlap=actual_overlap,
        first_test_month=first_test_month,
        last_test_month=last_test_month,
        spread_map=spread_map,
        expense_df=expense_df,
        ffr_df=ffr_df,
        leverage=leverage,
    )

    logger.debug(
        f"완전 고정 (a,b) 워크포워드 RMSE 계산 완료: {rmse:.4f}% " f"(a={a}, b={b}, 기간: {first_test_month} ~ {last_test_month})"
    )

    return rmse


def calculate_rate_segmented_rmse(
    actual_prices: np.ndarray,
    simulated_prices: np.ndarray,
    dates: list[date],
    ffr_df: pd.DataFrame,
    rate_boundary_pct: float = DEFAULT_RATE_BOUNDARY_PCT,
) -> dict[str, float | int | None]:
    """
    연속 시뮬레이션 결과를 금리 구간별로 분해하여 각 구간의 RMSE를 산출한다.

    전체 시뮬레이션에서 각 거래일의 FFR을 조회하고, 금리 경계값으로
    저금리/고금리 구간을 분류한 뒤 각 구간별 RMSE를 계산한다.

    Args:
        actual_prices: 실제 가격 numpy 배열
        simulated_prices: 시뮬레이션 가격 numpy 배열
        dates: 거래일 리스트 (date 객체)
        ffr_df: 연방기금금리 DataFrame (DATE: str (yyyy-mm), VALUE: float)
        rate_boundary_pct: 금리 구간 경계값 (%, 기본값: 2.0)

    Returns:
        금리 구간별 RMSE 딕셔너리:
            - "low_rate_rmse": 저금리 구간 RMSE (%) 또는 None (해당 구간 없을 때)
            - "high_rate_rmse": 고금리 구간 RMSE (%) 또는 None
            - "low_rate_days": 저금리 구간 거래일 수
            - "high_rate_days": 고금리 구간 거래일 수
            - "rate_boundary_pct": 사용된 금리 경계값

    Raises:
        ValueError: 입력 배열 길이가 일치하지 않을 때
        ValueError: dates 길이가 가격 배열과 일치하지 않을 때
    """
    # 1. 입력 검증
    if len(actual_prices) != len(simulated_prices):
        raise ValueError(f"actual_prices({len(actual_prices)})와 " f"simulated_prices({len(simulated_prices)}) 길이가 다릅니다")

    if len(dates) != len(actual_prices):
        raise ValueError(f"dates({len(dates)})와 actual_prices({len(actual_prices)}) 길이가 다릅니다")

    if len(actual_prices) == 0:
        raise ValueError("입력 데이터가 비어있습니다")

    # 2. FFR 딕셔너리 생성
    ffr_dict = create_ffr_dict(ffr_df)

    # 3. 각 거래일의 FFR 조회 및 구간 분류
    # 누적배수 계산 (전체 기준)
    m_actual = actual_prices / actual_prices[0]
    m_simul = simulated_prices / simulated_prices[0]
    ratio = m_actual / m_simul
    log_diff_abs_pct = np.abs(np.log(np.maximum(ratio, EPSILON))) * 100.0

    low_indices: list[int] = []
    high_indices: list[int] = []

    for i, d in enumerate(dates):
        ffr_ratio = lookup_ffr(d, ffr_dict)
        ffr_pct = ffr_ratio * 100.0
        if ffr_pct < rate_boundary_pct:
            low_indices.append(i)
        else:
            high_indices.append(i)

    # 4. 구간별 RMSE 계산
    low_rate_rmse: float | None = None
    high_rate_rmse: float | None = None

    if len(low_indices) > 0:
        low_diffs = log_diff_abs_pct[low_indices]
        low_rate_rmse = float(np.sqrt(np.mean(low_diffs**2)))

    if len(high_indices) > 0:
        high_diffs = log_diff_abs_pct[high_indices]
        high_rate_rmse = float(np.sqrt(np.mean(high_diffs**2)))

    result: dict[str, float | int | None] = {
        "low_rate_rmse": low_rate_rmse,
        "high_rate_rmse": high_rate_rmse,
        "low_rate_days": len(low_indices),
        "high_rate_days": len(high_indices),
        "rate_boundary_pct": rate_boundary_pct,
    }

    logger.debug(
        f"금리 구간별 RMSE 분해 완료: "
        f"저금리(<{rate_boundary_pct}%) RMSE={low_rate_rmse}, 일수={len(low_indices)}, "
        f"고금리(>={rate_boundary_pct}%) RMSE={high_rate_rmse}, 일수={len(high_indices)}"
    )

    return result


def run_fixed_ab_walkforward(
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
            train_rmse, _, _ = calculate_metrics_fast(train_actual_prices, train_sim_prices)
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


def calculate_rate_segmented_from_stitched(
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
