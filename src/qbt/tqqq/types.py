"""
레버리지 ETF 시뮬레이션 도메인 TypedDict 정의

시뮬레이션 도메인에서 사용하는 딕셔너리 구조를 타입으로 정의한다.
- 검증 지표 (ValidationMetricsDict)
"""

from datetime import date
from typing import TypedDict


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
