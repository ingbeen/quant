"""레버리지 ETF 시뮬레이션 파라미터 최적화 모듈

softplus 동적 스프레드 모델의 최적 (a, b) 파라미터를 2-Stage Grid Search로 탐색한다.
벡터화된 시뮬레이션과 병렬 처리를 사용하여 성능을 최적화한다.
"""

from datetime import date

import numpy as np
import pandas as pd

from qbt.common_constants import COL_CLOSE, COL_DATE, EPSILON, TRADING_DAYS_PER_YEAR
from qbt.tqqq.constants import (
    DEFAULT_LEVERAGE_MULTIPLIER,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    KEY_CUMULATIVE_RETURN_ACTUAL,
    KEY_CUMULATIVE_RETURN_REL_DIFF,
    KEY_CUMULATIVE_RETURN_SIMULATED,
    KEY_FINAL_CLOSE_ACTUAL,
    KEY_FINAL_CLOSE_REL_DIFF,
    KEY_FINAL_CLOSE_SIMULATED,
    KEY_OVERLAP_DAYS,
    KEY_OVERLAP_END,
    KEY_OVERLAP_START,
    SOFTPLUS_GRID_STAGE1_A_RANGE,
    SOFTPLUS_GRID_STAGE1_A_STEP,
    SOFTPLUS_GRID_STAGE1_B_RANGE,
    SOFTPLUS_GRID_STAGE1_B_STEP,
    SOFTPLUS_GRID_STAGE2_A_DELTA,
    SOFTPLUS_GRID_STAGE2_A_STEP,
    SOFTPLUS_GRID_STAGE2_B_DELTA,
    SOFTPLUS_GRID_STAGE2_B_STEP,
)
from qbt.tqqq.data_loader import (
    create_expense_dict,
    create_ffr_dict,
    lookup_expense,
    lookup_ffr,
)
from qbt.tqqq.simulation import (
    _calculate_metrics_fast,  # pyright: ignore[reportPrivateUsage]
    _validate_ffr_coverage,  # pyright: ignore[reportPrivateUsage]
)
from qbt.tqqq.types import SimulationCacheDict, SoftplusCandidateDict
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period
from qbt.utils.parallel_executor import WORKER_CACHE, execute_parallel, init_worker_cache

logger = get_logger(__name__)


def _build_monthly_spread_map_from_dict(
    ffr_dict: dict[str, float],
    a: float,
    b: float,
) -> dict[str, float]:
    """
    FFR 딕셔너리로부터 월별 softplus spread 맵을 생성한다 (벡터화 버전).

    build_monthly_spread_map의 최적화 버전으로, DataFrame 생성 오버헤드 없이
    dict에서 직접 spread 맵을 생성한다. numpy 벡터화를 사용하여 성능을 개선했다.

    수식: spread = softplus(a + b * ffr_pct)
    여기서 ffr_pct = 100.0 * ffr_ratio (0~1 비율을 % 단위로 변환)

    Args:
        ffr_dict: FFR 딕셔너리 {"YYYY-MM": ffr_ratio (0~1 비율)}
        a: softplus 절편 파라미터
        b: softplus 기울기 파라미터

    Returns:
        {"YYYY-MM": spread} 형태의 딕셔너리

    Raises:
        ValueError: FFR 딕셔너리가 비어있을 때
    """
    if not ffr_dict:
        raise ValueError("FFR 딕셔너리가 비어있습니다")

    # 월별 키와 값을 배열로 변환
    months = list(ffr_dict.keys())
    ffr_ratios = np.array(list(ffr_dict.values()))

    # 벡터화된 softplus 계산
    # softplus(x) = log1p(exp(-abs(x))) + max(x, 0) (수치 안정 버전)
    ffr_pct = 100.0 * ffr_ratios
    x = a + b * ffr_pct
    spreads = np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0.0)

    # 딕셔너리로 변환
    spread_map = dict(zip(months, spreads.tolist(), strict=True))

    return spread_map


def _precompute_daily_costs_vectorized(
    month_keys: np.ndarray,
    ffr_dict: dict[str, float],
    expense_dict: dict[str, float],
    spread_map: dict[str, float],
    leverage: float,
) -> np.ndarray:
    """
    모든 거래일의 일일 비용을 한 번에 사전 계산한다 (벡터화 버전).

    고유 월(unique months)만 추출하여 월별 1회만 비용을 계산하고,
    numpy 인덱싱으로 일별 배열로 매핑한다.
    기존 _calculate_daily_cost와 동일한 비용 공식 및 fallback 로직을 적용한다.

    Args:
        month_keys: 각 거래일의 "YYYY-MM" 문자열 배열
        ffr_dict: FFR 딕셔너리 ({"YYYY-MM": ffr_value})
        expense_dict: Expense 딕셔너리 ({"YYYY-MM": expense_value})
        spread_map: 월별 spread 맵 ({"YYYY-MM": spread})
        leverage: 레버리지 배율

    Returns:
        일별 비용 배열 (len = len(month_keys))

    Raises:
        ValueError: spread_map에 필요한 월 키가 누락된 경우
        ValueError: FFR 또는 Expense 데이터 조회 실패 시
    """
    # 1. 고유 월만 추출 (순서 유지, 중복 제거)
    unique_months: list[str] = list(dict.fromkeys(str(mk) for mk in month_keys))

    # 2. 월별 비용 계산 (월당 1회만 계산)
    month_to_cost: dict[str, float] = {}
    for month_key in unique_months:
        # FFR 조회 (lookup_ffr과 동일한 fallback 로직)
        year, month = map(int, month_key.split("-"))
        d = date(year, month, 1)
        ffr = lookup_ffr(d, ffr_dict)

        # Expense 조회 (lookup_expense와 동일한 fallback 로직)
        expense = lookup_expense(d, expense_dict)

        # Spread 조회 (dict 타입: 정확한 키 필요, fallback 없음)
        if month_key not in spread_map:
            raise ValueError(
                f"spread_map에 키 누락: {month_key}\n"
                f"보유 키: {sorted(spread_map.keys())[:5]}{'...' if len(spread_map) > 5 else ''}"
            )
        spread = spread_map[month_key]

        # 일일 비용 = ((FFR + spread) * (leverage - 1) + expense) / 거래일수
        funding_rate = ffr + spread
        leverage_cost = funding_rate * (leverage - 1)
        annual_cost = leverage_cost + expense
        month_to_cost[month_key] = annual_cost / TRADING_DAYS_PER_YEAR

    # 3. 월별 비용을 일별 배열로 매핑
    daily_costs = np.array([month_to_cost[str(mk)] for mk in month_keys])

    return daily_costs


def _simulate_prices_vectorized(
    underlying_returns: np.ndarray,
    daily_costs: np.ndarray,
    leverage: float,
    initial_price: float,
) -> np.ndarray:
    """
    numpy cumprod로 레버리지 ETF 가격을 한 번에 계산한다 (벡터화 버전).

    기존 simulate() 함수의 Python for-loop을 대체하며,
    동일한 복리 계산 로직을 numpy 연산으로 수행한다.

    수식:
        leveraged_returns = underlying_returns * leverage - daily_costs
        leveraged_returns[0] = 0.0  (첫날: 수익률 없음)
        prices = initial_price * cumprod(1 + leveraged_returns)

    Args:
        underlying_returns: 기초 자산 일일 수익률 배열 (첫 요소는 0.0이어야 함)
        daily_costs: 사전 계산된 일일 비용 배열
        leverage: 레버리지 배율
        initial_price: 시작 가격

    Returns:
        시뮬레이션 가격 numpy 배열
    """
    # 1. 레버리지 수익률 계산
    leveraged_returns = underlying_returns * leverage - daily_costs

    # 2. 첫날은 수익률 없음 (initial_price 유지)
    leveraged_returns[0] = 0.0

    # 3. 복리 효과 적용 (cumprod)
    prices: np.ndarray = initial_price * np.cumprod(1 + leveraged_returns)

    return prices


def _evaluate_softplus_candidate(params: dict[str, float]) -> SoftplusCandidateDict:
    """
    단일 softplus (a, b) 파라미터 조합을 시뮬레이션하고 평가한다 (벡터화 버전).

    2-stage grid search에서 병렬 실행을 위한 헬퍼 함수.
    pickle 가능하도록 최상위 레벨에 정의한다.
    사전 계산된 numpy 배열을 WORKER_CACHE에서 조회하여 성능을 개선한다.

    Args:
        params: 파라미터 딕셔너리 {
            "a": softplus 절편 파라미터,
            "b": softplus 기울기 파라미터,
            "leverage": 레버리지 배수,
            "initial_price": 초기 가격,
        }

    Returns:
        평가 결과 딕셔너리 {
            "a": float,
            "b": float,
            "cumul_multiple_log_diff_rmse_pct": float,
            ... (기타 검증 지표)
        }
    """
    # WORKER_CACHE에서 사전 계산된 배열 조회
    ffr_dict: dict[str, float] = WORKER_CACHE["ffr_dict"]
    underlying_returns: np.ndarray = WORKER_CACHE["underlying_returns"]
    actual_prices: np.ndarray = WORKER_CACHE["actual_prices"]
    expense_dict: dict[str, float] = WORKER_CACHE["expense_dict"]
    date_month_keys: np.ndarray = WORKER_CACHE["date_month_keys"]
    overlap_start: date = WORKER_CACHE["overlap_start"]
    overlap_end: date = WORKER_CACHE["overlap_end"]
    overlap_days: int = WORKER_CACHE["overlap_days"]
    actual_cumulative_return: float = WORKER_CACHE["actual_cumulative_return"]

    leverage: float = params["leverage"]
    initial_price: float = params["initial_price"]

    # 1. softplus spread 맵 생성 (벡터화 버전)
    spread_map = _build_monthly_spread_map_from_dict(ffr_dict, params["a"], params["b"])

    # 2. 일일 비용 사전 계산
    daily_costs = _precompute_daily_costs_vectorized(
        month_keys=date_month_keys,
        ffr_dict=ffr_dict,
        expense_dict=expense_dict,
        spread_map=spread_map,
        leverage=leverage,
    )

    # 3. 벡터화 시뮬레이션
    simulated_prices = _simulate_prices_vectorized(
        underlying_returns=underlying_returns.copy(),
        daily_costs=daily_costs,
        leverage=leverage,
        initial_price=initial_price,
    )

    # 4. 경량 메트릭 계산 (RMSE, mean, max)
    rmse, mean_val, max_val = _calculate_metrics_fast(actual_prices, simulated_prices)

    # 5. 추가 메트릭 (기존 candidate dict 구조 유지)
    final_close_simulated = float(simulated_prices[-1])
    final_close_actual = float(actual_prices[-1])
    final_close_rel_diff_pct = ((final_close_simulated - final_close_actual) / final_close_actual) * 100

    sim_cumulative = float(simulated_prices[-1] / simulated_prices[0]) - 1.0
    cumulative_return_rel_diff_pct = ((sim_cumulative - actual_cumulative_return) / actual_cumulative_return) * 100

    # 6. candidate 딕셔너리 생성 (기존 키 모두 포함)
    candidate: SoftplusCandidateDict = {
        "a": params["a"],
        "b": params["b"],
        "leverage": leverage,
        KEY_OVERLAP_START: overlap_start,
        KEY_OVERLAP_END: overlap_end,
        KEY_OVERLAP_DAYS: overlap_days,
        KEY_FINAL_CLOSE_ACTUAL: final_close_actual,
        KEY_FINAL_CLOSE_SIMULATED: final_close_simulated,
        KEY_FINAL_CLOSE_REL_DIFF: final_close_rel_diff_pct,
        KEY_CUMULATIVE_RETURN_SIMULATED: sim_cumulative,
        KEY_CUMULATIVE_RETURN_ACTUAL: actual_cumulative_return,
        KEY_CUMULATIVE_RETURN_REL_DIFF: cumulative_return_rel_diff_pct,
        KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN: mean_val,
        KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE: rmse,
        KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX: max_val,
    }

    return candidate


def _prepare_optimization_data(
    underlying_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
) -> tuple[float, SimulationCacheDict]:
    """
    softplus 파라미터 최적화를 위한 공통 초기화를 수행한다.

    겹치는 기간 추출, FFR 검증, 딕셔너리 생성, numpy 배열 변환,
    워커 캐시 데이터 구성을 한 곳에서 처리한다.

    Args:
        underlying_df: 기초 자산 DataFrame (QQQ)
        actual_df: 실제 레버리지 ETF DataFrame (TQQQ)
        ffr_df: 연방기금금리 DataFrame (DATE: str (yyyy-mm), VALUE: float)
        expense_df: 운용비용 DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율))

    Returns:
        (initial_price, cache_data) 튜플
            - initial_price: 실제 레버리지 ETF 첫날 가격
            - cache_data: 병렬 워커 캐시 초기화용 딕셔너리

    Raises:
        ValueError: 겹치는 기간이 없을 때
        ValueError: FFR 커버리지가 부족할 때
    """
    # 1. 겹치는 기간 추출
    underlying_overlap, actual_overlap = extract_overlap_period(underlying_df, actual_df)

    # 2. FFR 커버리지 검증 (fail-fast)
    overlap_start = underlying_overlap[COL_DATE].min()
    overlap_end = underlying_overlap[COL_DATE].max()
    _validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

    # 3. 검증 완료 후 FFR 딕셔너리 생성 (한 번만)
    ffr_dict = create_ffr_dict(ffr_df)

    # 4. 실제 레버리지 ETF 첫날 가격을 initial_price로 사용
    initial_price = float(actual_overlap.iloc[0][COL_CLOSE])

    # 5. 사전 계산 배열 준비 (벡터화 최적화)
    expense_dict = create_expense_dict(expense_df)

    underlying_returns = np.array(underlying_overlap[COL_CLOSE].pct_change().fillna(0.0).tolist(), dtype=np.float64)

    actual_prices = np.array(actual_overlap[COL_CLOSE].tolist(), dtype=np.float64)

    date_month_keys = np.array(
        [f"{d.year:04d}-{d.month:02d}" for d in underlying_overlap[COL_DATE]],
        dtype=object,
    )

    overlap_days = len(underlying_overlap)
    actual_cumulative_return = float(actual_prices[-1] / actual_prices[0]) - 1.0

    # 6. 워커 캐시 초기화 데이터 구성
    cache_data: SimulationCacheDict = {
        "ffr_dict": ffr_dict,
        "expense_dict": expense_dict,
        "underlying_returns": underlying_returns,
        "actual_prices": actual_prices,
        "date_month_keys": date_month_keys,
        "overlap_start": overlap_start,
        "overlap_end": overlap_end,
        "overlap_days": overlap_days,
        "actual_cumulative_return": actual_cumulative_return,
    }

    return initial_price, cache_data


def find_optimal_softplus_params(
    underlying_df: pd.DataFrame,
    actual_leveraged_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    leverage: float = DEFAULT_LEVERAGE_MULTIPLIER,
    max_workers: int | None = None,
    fixed_b: float | None = None,
) -> tuple[float, float, float, list[SoftplusCandidateDict]]:
    """
    softplus 동적 스프레드 모델의 최적 (a, b) 파라미터를 2-stage grid search로 탐색한다.

    Stage 1에서 조대 그리드로 대략적인 최적점을 찾고,
    Stage 2에서 해당 영역 주변을 정밀 탐색하여 최종 최적값을 결정한다.

    목적함수: cumul_multiple_log_diff_rmse_pct 최소화

    Args:
        underlying_df: 기초 자산 DataFrame (QQQ)
        actual_leveraged_df: 실제 레버리지 ETF DataFrame (TQQQ)
        ffr_df: 연방기금금리 DataFrame (DATE: str (yyyy-mm), VALUE: float)
        expense_df: 운용비용 DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율))
        leverage: 레버리지 배수 (기본값: 3.0)
        max_workers: 최대 워커 수 (None이면 기본값 2)
        fixed_b: b 파라미터 고정값 (None이면 b도 그리드 서치, 설정 시 a만 최적화)

    Returns:
        (a_best, b_best, best_rmse, all_candidates) 튜플
            - a_best: 최적 절편 파라미터
            - b_best: 최적 기울기 파라미터 (fixed_b 설정 시 fixed_b와 동일)
            - best_rmse: 최적 RMSE (%)
            - all_candidates: 전체 후보 리스트 (Stage 1 + Stage 2)

    Raises:
        ValueError: 겹치는 기간이 없을 때
        ValueError: FFR 또는 Expense 데이터 커버리지가 부족할 때
        ValueError: fixed_b가 음수일 때
    """
    # 0. fixed_b 검증
    if fixed_b is not None and fixed_b < 0:
        raise ValueError(f"fixed_b는 0 이상이어야 합니다: {fixed_b}")

    # 1. 공통 초기화 (겹치는 기간 추출, FFR 검증, 배열 변환)
    initial_price, cache_data = _prepare_optimization_data(underlying_df, actual_leveraged_df, ffr_df, expense_df)

    # ============================================================
    # Stage 1: 조대 그리드 탐색
    # ============================================================
    logger.debug(
        f"Stage 1 시작: a in [{SOFTPLUS_GRID_STAGE1_A_RANGE[0]}, {SOFTPLUS_GRID_STAGE1_A_RANGE[1]}] "
        f"step {SOFTPLUS_GRID_STAGE1_A_STEP}, "
        f"b in [{SOFTPLUS_GRID_STAGE1_B_RANGE[0]}, {SOFTPLUS_GRID_STAGE1_B_RANGE[1]}] "
        f"step {SOFTPLUS_GRID_STAGE1_B_STEP}"
    )

    # Stage 1 파라미터 조합 생성
    a_values_s1 = np.arange(
        SOFTPLUS_GRID_STAGE1_A_RANGE[0],
        SOFTPLUS_GRID_STAGE1_A_RANGE[1] + EPSILON,
        SOFTPLUS_GRID_STAGE1_A_STEP,
    )
    if fixed_b is not None:
        b_values_s1 = np.array([fixed_b])
    else:
        b_values_s1 = np.arange(
            SOFTPLUS_GRID_STAGE1_B_RANGE[0],
            SOFTPLUS_GRID_STAGE1_B_RANGE[1] + EPSILON,
            SOFTPLUS_GRID_STAGE1_B_STEP,
        )

    param_combinations_s1 = []
    for a in a_values_s1:
        for b in b_values_s1:
            param_combinations_s1.append(
                {
                    "a": float(a),
                    "b": float(b),
                    "leverage": leverage,
                    "initial_price": initial_price,
                }
            )

    logger.debug(f"Stage 1 조합 수: {len(param_combinations_s1)}")

    # Stage 1 병렬 실행
    candidates_s1 = execute_parallel(
        _evaluate_softplus_candidate,
        param_combinations_s1,
        max_workers=max_workers,
        initializer=init_worker_cache,
        initargs=(cache_data,),
    )

    # Stage 1 최적값 찾기
    candidates_s1.sort(key=lambda x: x[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE])
    best_s1 = candidates_s1[0]
    a_star = best_s1["a"]
    b_star = best_s1["b"]

    logger.debug(
        f"Stage 1 완료: a*={a_star:.4f}, b*={b_star:.4f}, " f"RMSE={best_s1[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]:.4f}%"
    )

    # ============================================================
    # Stage 2: 정밀 그리드 탐색
    # ============================================================
    logger.debug(
        f"Stage 2 시작: a in [{a_star - SOFTPLUS_GRID_STAGE2_A_DELTA:.4f}, "
        f"{a_star + SOFTPLUS_GRID_STAGE2_A_DELTA:.4f}] step {SOFTPLUS_GRID_STAGE2_A_STEP}, "
        f"b in [{b_star - SOFTPLUS_GRID_STAGE2_B_DELTA:.4f}, "
        f"{b_star + SOFTPLUS_GRID_STAGE2_B_DELTA:.4f}] step {SOFTPLUS_GRID_STAGE2_B_STEP}"
    )

    # Stage 2 파라미터 조합 생성 (a*, b* 주변)
    a_values_s2 = np.arange(
        a_star - SOFTPLUS_GRID_STAGE2_A_DELTA,
        a_star + SOFTPLUS_GRID_STAGE2_A_DELTA + EPSILON,
        SOFTPLUS_GRID_STAGE2_A_STEP,
    )
    if fixed_b is not None:
        b_values_s2 = np.array([fixed_b])
    else:
        b_values_s2 = np.arange(
            max(0.0, b_star - SOFTPLUS_GRID_STAGE2_B_DELTA),  # b는 음수 불가
            b_star + SOFTPLUS_GRID_STAGE2_B_DELTA + EPSILON,
            SOFTPLUS_GRID_STAGE2_B_STEP,
        )

    param_combinations_s2 = []
    for a in a_values_s2:
        for b in b_values_s2:
            param_combinations_s2.append(
                {
                    "a": float(a),
                    "b": float(b),
                    "leverage": leverage,
                    "initial_price": initial_price,
                }
            )

    logger.debug(f"Stage 2 조합 수: {len(param_combinations_s2)}")

    # Stage 2 병렬 실행
    candidates_s2 = execute_parallel(
        _evaluate_softplus_candidate,
        param_combinations_s2,
        max_workers=max_workers,
        initializer=init_worker_cache,
        initargs=(cache_data,),
    )

    # Stage 2 최적값 찾기
    candidates_s2.sort(key=lambda x: x[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE])
    best_s2 = candidates_s2[0]
    a_best = best_s2["a"]
    b_best = best_s2["b"]
    best_rmse = best_s2[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]

    logger.debug(f"Stage 2 완료: a_best={a_best:.4f}, b_best={b_best:.4f}, " f"RMSE={best_rmse:.4f}%")

    # 전체 후보 병합 (중복 제거는 하지 않음, 호출자가 필요시 처리)
    all_candidates = candidates_s1 + candidates_s2

    return a_best, b_best, best_rmse, all_candidates
