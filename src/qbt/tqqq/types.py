"""
레버리지 ETF 시뮬레이션 도메인 TypedDict 정의

시뮬레이션 도메인에서 사용하는 딕셔너리 구조를 타입으로 정의한다.
- 검증 지표 (ValidationMetricsDict, CostModelCandidateDict, SoftplusCandidateDict)
- 워커 캐시 (SimulationCacheDict)
- 워크포워드 요약 (WalkforwardSummaryDict)
"""

from datetime import date
from typing import NotRequired, TypedDict

import numpy as np


class ValidationMetricsDict(TypedDict):
    """calculate_validation_metrics() 반환 타입.

    시뮬레이션과 실제 데이터의 비교 검증 지표를 담는 딕셔너리.
    키 이름은 tqqq/constants.py의 KEY_* 상수 값과 동일하다.
    """

    overlap_start: date
    overlap_end: date
    overlap_days: int
    final_close_actual: float
    final_close_simulated: float
    final_close_rel_diff_pct: float
    cumulative_return_simulated: float
    cumulative_return_actual: float
    cumulative_return_rel_diff_pct: float
    cumul_multiple_log_diff_mean_pct: float
    cumul_multiple_log_diff_rmse_pct: float
    cumul_multiple_log_diff_max_pct: float


class CostModelCandidateDict(ValidationMetricsDict):
    """_evaluate_cost_model_candidate() 반환 타입.

    ValidationMetricsDict를 상속하고 비용 모델 파라미터를 추가한다.
    """

    leverage: float
    spread: float


class SoftplusCandidateDict(ValidationMetricsDict):
    """_evaluate_softplus_candidate() 반환 타입.

    ValidationMetricsDict를 상속하고 softplus 파라미터를 추가한다.
    """

    a: float
    b: float
    leverage: float


class SimulationCacheDict(TypedDict):
    """WORKER_CACHE에 저장되는 시뮬레이션 사전 계산 데이터 구조.

    병렬 처리 시 워커 프로세스 간 공유하는 캐시 데이터.
    """

    ffr_dict: dict[str, float]
    expense_dict: dict[str, float]
    underlying_returns: np.ndarray
    actual_prices: np.ndarray
    date_month_keys: np.ndarray
    overlap_start: date
    overlap_end: date
    overlap_days: int
    actual_cumulative_return: float


class WalkforwardSummaryDict(TypedDict):
    """run_walkforward_validation() 반환 요약 통계 딕셔너리."""

    test_rmse_mean: float
    test_rmse_median: float
    test_rmse_std: float
    test_rmse_min: float
    test_rmse_max: float
    a_mean: float
    a_std: float
    b_mean: float
    b_std: float
    n_test_months: int
    train_window_months: int
    stitched_rmse: NotRequired[float]
