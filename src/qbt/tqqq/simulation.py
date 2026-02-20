"""레버리지 ETF 시뮬레이션 모듈

QQQ와 같은 기초 자산 데이터로부터 TQQQ와 같은 레버리지 ETF를 시뮬레이션한다.
일일 리밸런싱 기반의 3배 레버리지 ETF 동작을 재현한다.

학습 포인트:
1. typing 모듈: 함수 파라미터와 반환값의 타입을 명시하여 코드 안정성 향상
2. pandas (pd): 데이터프레임을 활용한 시계열 데이터 처리
3. numpy (np): 배열 기반 수치 연산 (로그, 제곱근 등)
4. | 연산자: 타입 힌트에서 "또는"을 의미 (예: Path | None = Path 또는 None)
"""

# 1. 표준 라이브러리 임포트
import math  # 수학 함수 (isnan, isinf 등)
from collections.abc import Callable  # 함수 타입 힌트
from datetime import date  # 날짜 객체 사용 (년-월-일 정보)
from pathlib import Path  # 파일 경로 처리 (문자열보다 안전)
from typing import cast  # 타입 캐스팅 함수 (타입 힌트 시스템용)

# 2. 서드파티 라이브러리 임포트
import numpy as np  # 수치 계산 라이브러리 (배열, 로그, 제곱근 등)
import pandas as pd  # 데이터프레임 라이브러리 (엑셀 같은 표 형태 데이터)

from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    DISPLAY_DATE,
    EPSILON,
    REQUIRED_COLUMNS,
    TRADING_DAYS_PER_YEAR,
)
from qbt.tqqq.analysis_helpers import (
    calculate_signed_log_diff_from_cumulative_returns,
    validate_integrity,
)
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_ACTUAL_CUMUL_RETURN,
    COL_ACTUAL_DAILY_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_FFR_DATE,
    COL_FFR_VALUE,
    COL_SIMUL_CLOSE,
    COL_SIMUL_CUMUL_RETURN,
    COL_SIMUL_DAILY_RETURN,
    DEFAULT_FUNDING_SPREAD,
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_RATE_BOUNDARY_PCT,
    DEFAULT_TRAIN_WINDOW_MONTHS,
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
    MAX_FFR_MONTHS_DIFF,
    SOFTPLUS_GRID_STAGE1_A_RANGE,
    SOFTPLUS_GRID_STAGE1_A_STEP,
    SOFTPLUS_GRID_STAGE1_B_RANGE,
    SOFTPLUS_GRID_STAGE1_B_STEP,
    SOFTPLUS_GRID_STAGE2_A_DELTA,
    SOFTPLUS_GRID_STAGE2_A_STEP,
    SOFTPLUS_GRID_STAGE2_B_DELTA,
    SOFTPLUS_GRID_STAGE2_B_STEP,
    WALKFORWARD_LOCAL_REFINE_A_DELTA,
    WALKFORWARD_LOCAL_REFINE_A_STEP,
    WALKFORWARD_LOCAL_REFINE_B_DELTA,
    WALKFORWARD_LOCAL_REFINE_B_STEP,
)
from qbt.tqqq.data_loader import (
    create_expense_dict,
    create_ffr_dict,
    lookup_expense,
    lookup_ffr,
    lookup_monthly_data,
)
from qbt.tqqq.types import (
    SimulationCacheDict,
    SoftplusCandidateDict,
    ValidationMetricsDict,
    WalkforwardSummaryDict,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period
from qbt.utils.parallel_executor import WORKER_CACHE, execute_parallel, init_worker_cache

logger = get_logger(__name__)

# 동적 funding_spread 지원 타입 정의
# - float: 고정 spread (기존 동작)
# - dict[str, float]: 월별 spread ({"YYYY-MM": spread})
# - Callable[[date], float]: 날짜를 받아 spread를 반환하는 함수
FundingSpreadSpec = float | dict[str, float] | Callable[[date], float]


# ============================================================
# Softplus 동적 스프레드 모델 함수
# ============================================================


def _softplus(x: float) -> float:
    """
    수치 안정 버전 softplus 함수를 계산한다.

    softplus(x) = log(1 + exp(x)) 를 수치적으로 안정하게 계산한다.
    x가 크면 overflow, x가 작으면 underflow를 방지하는 변환 사용.

    수치 안정 수식:
        softplus(x) = log1p(exp(-abs(x))) + max(x, 0)

    특성:
        - 항상 양수 반환 (> 0)
        - x -> -inf: 결과 -> 0 (점근)
        - x -> +inf: 결과 -> x (점근)
        - 부드러운 ReLU 근사 (미분 가능)

    Args:
        x: 입력 값

    Returns:
        softplus(x) 값 (항상 > 0)
    """
    # 수치 안정 계산: log1p(exp(-|x|)) + max(x, 0)
    # 이 공식은 x의 부호에 관계없이 안정적으로 계산된다.
    return math.log1p(math.exp(-abs(x))) + max(x, 0.0)


def compute_softplus_spread(a: float, b: float, ffr_ratio: float) -> float:
    """
    softplus 기반 동적 spread를 계산한다.

    수식: spread = softplus(a + b * ffr_pct)
    여기서 ffr_pct = 100.0 * ffr_ratio (0~1 비율을 % 단위로 변환)

    예시:
        a = -5.0, b = 1.0, ffr_ratio = 0.05 (5%)
        ffr_pct = 5.0
        spread = softplus(-5.0 + 1.0 * 5.0) = softplus(0.0) ≈ 0.693

    Args:
        a: 절편 파라미터 (음수일 때 저금리 구간 spread 감소)
        b: 기울기 파라미터 (양수일 때 고금리 구간 spread 증가)
        ffr_ratio: 연방기금금리 (0~1 비율, 예: 0.05 = 5%)

    Returns:
        계산된 spread 값 (항상 > 0)

    Raises:
        ValueError: spread <= 0인 경우 (softplus는 이론적으로 항상 > 0이므로 방어적 체크)
    """
    # 1. FFR을 % 단위로 변환 (프롬프트 요구사항)
    ffr_pct = 100.0 * ffr_ratio

    # 2. softplus 계산
    spread = _softplus(a + b * ffr_pct)

    # 3. 방어적 체크 (softplus는 항상 > 0이지만 수치 오류 대비)
    if spread <= 0:
        raise ValueError(
            f"compute_softplus_spread 결과가 유효하지 않음: spread={spread} <= 0\n"
            f"파라미터: a={a}, b={b}, ffr_ratio={ffr_ratio}, ffr_pct={ffr_pct}\n"
            f"조치: 파라미터 값 확인 필요"
        )

    return spread


def build_monthly_spread_map(
    ffr_df: pd.DataFrame,
    a: float,
    b: float,
) -> dict[str, float]:
    """
    FFR 데이터로부터 월별 softplus spread 맵을 생성한다.

    각 월의 FFR 값에 대해 softplus(a + b * ffr_pct) 공식을 적용하여
    월별 spread 딕셔너리를 생성한다. 이 딕셔너리는 simulate() 함수의
    funding_spread 파라미터로 전달할 수 있다.

    Args:
        ffr_df: FFR DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율))
        a: softplus 절편 파라미터
        b: softplus 기울기 파라미터

    Returns:
        {"YYYY-MM": spread} 형태의 딕셔너리

    Raises:
        ValueError: FFR DataFrame이 비어있거나 필수 컬럼 누락 시
        ValueError: spread 계산 결과가 유효하지 않을 때
    """
    # 1. 필수 컬럼 검증
    if ffr_df.empty:
        raise ValueError("FFR DataFrame이 비어있습니다")

    required_cols = {COL_FFR_DATE, COL_FFR_VALUE}
    missing_cols = required_cols - set(ffr_df.columns)
    if missing_cols:
        raise ValueError(f"FFR DataFrame 필수 컬럼 누락: {missing_cols}")

    # 2. 월별 spread 계산
    spread_map: dict[str, float] = {}
    for _, row in ffr_df.iterrows():
        month_key = str(row[COL_FFR_DATE])
        ffr_ratio = float(row[COL_FFR_VALUE])

        # softplus spread 계산
        spread = compute_softplus_spread(a, b, ffr_ratio)
        spread_map[month_key] = spread

    logger.debug(
        f"월별 spread 맵 생성 완료: {len(spread_map)}개월, "
        f"a={a}, b={b}, spread 범위=[{min(spread_map.values()):.6f}, {max(spread_map.values()):.6f}]"
    )

    return spread_map


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


# ============================================================
# 정적 Spread 시계열 생성
# ============================================================

# 정적 spread 시계열 CSV 컬럼명 (이 모듈에서만 사용)
COL_STATIC_MONTH = "month"
COL_STATIC_FFR_PCT = "ffr_pct"
COL_STATIC_A_GLOBAL = "a_global"
COL_STATIC_B_GLOBAL = "b_global"
COL_STATIC_SPREAD_GLOBAL = "spread_global"


def generate_static_spread_series(
    ffr_df: pd.DataFrame,
    a: float,
    b: float,
    underlying_overlap_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    전체기간 단일 최적 (a, b)에 대해 월별 spread 시계열 DataFrame을 생성한다.

    기초자산 overlap 기간의 고유 월을 추출하고, 각 월의 FFR 값으로
    softplus(a + b * ffr_pct) 공식을 적용하여 spread를 계산한다.

    FFR 누락 월 처리: lookup_ffr (최대 2개월 이전 값 fallback, 초과 시 ValueError)

    Args:
        ffr_df: FFR DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율))
        a: softplus 절편 파라미터
        b: softplus 기울기 파라미터
        underlying_overlap_df: 기초자산 겹침 기간 DataFrame (Date 컬럼 필수)

    Returns:
        DataFrame (month, ffr_pct, a_global, b_global, spread_global)
        month 오름차순 정렬

    Raises:
        ValueError: overlap DataFrame이 비어있을 때
        ValueError: FFR 조회 실패 (최대 2개월 fallback 초과) 시
    """
    # 1. 입력 검증
    if underlying_overlap_df.empty:
        raise ValueError("기초자산 overlap DataFrame이 비어있습니다")

    # 2. overlap 기간 고유 월 추출 (오름차순 정렬)
    overlap_months = sorted(underlying_overlap_df[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}").unique())

    # 3. FFR 딕셔너리 생성
    ffr_dict = create_ffr_dict(ffr_df)

    # 4. 각 월에 대해 FFR 조회 및 spread 계산
    rows: list[dict[str, object]] = []
    for month_key in overlap_months:
        # 월 문자열을 date 객체로 변환 (1일 기준)
        year, mon = map(int, month_key.split("-"))
        month_date = date(year, mon, 1)

        # FFR 조회 (2개월 fallback)
        ffr_ratio = lookup_ffr(month_date, ffr_dict)
        ffr_pct = ffr_ratio * 100.0

        # softplus spread 계산
        spread = compute_softplus_spread(a, b, ffr_ratio)

        rows.append(
            {
                COL_STATIC_MONTH: month_key,
                COL_STATIC_FFR_PCT: ffr_pct,
                COL_STATIC_A_GLOBAL: a,
                COL_STATIC_B_GLOBAL: b,
                COL_STATIC_SPREAD_GLOBAL: spread,
            }
        )

    result_df = pd.DataFrame(rows)

    logger.debug(
        f"정적 spread 시계열 생성 완료: {len(result_df)}개월, "
        f"a={a:.4f}, b={b:.4f}, "
        f"spread 범위=[{result_df[COL_STATIC_SPREAD_GLOBAL].min():.6f}, "
        f"{result_df[COL_STATIC_SPREAD_GLOBAL].max():.6f}]"
    )

    return result_df


# 무결성 체크 허용 오차 (%)
# abs(signed)와 abs 컬럼의 최대 차이 허용값
# 결정 근거: 실제 데이터 관측값 (max_abs_diff=4.66e-14%) + 10% 여유 -> 1e-6%로 확정
INTEGRITY_TOLERANCE = 1e-6  # 0.000001%


def _resolve_spread(d: date, spread_spec: FundingSpreadSpec) -> float:
    """
    특정 날짜의 funding_spread 값을 해석한다.

    FundingSpreadSpec 타입에 따라 다르게 처리:
    - float: 그대로 반환
    - dict[str, float]: 월별 키 "YYYY-MM"으로 조회, 키 없으면 MAX_FFR_MONTHS_DIFF 이내 이전 월 fallback
    - Callable[[date], float]: 함수 호출, 반환값 검증

    제약 조건 (프롬프트에서 확정):
    - 반환 spread는 항상 > 0 (음수 불허, 0도 불허)
    - NaN/inf 반환 시 ValueError
    - min/max 클리핑 금지 (검증만 수행)

    Args:
        d: 대상 날짜
        spread_spec: funding_spread 스펙 (float, dict, 또는 Callable)

    Returns:
        해당 날짜의 spread 값 (> 0)

    Raises:
        ValueError: 이전 월 없음, 월 차이 초과, NaN/inf 반환, spread <= 0 등
    """
    spread: float

    # 1. float 타입: 그대로 사용
    if isinstance(spread_spec, float | int):
        spread = float(spread_spec)

    # 2. dict 타입: 월별 키 조회 (키 없으면 MAX_FFR_MONTHS_DIFF 이내 이전 월 fallback)
    elif isinstance(spread_spec, dict):
        spread = lookup_monthly_data(d, spread_spec, MAX_FFR_MONTHS_DIFF, "funding_spread")

    # 3. Callable 타입: 함수 호출
    else:
        spread = spread_spec(d)

    # 4. 반환값 검증: NaN/inf 체크
    if math.isnan(spread):
        raise ValueError(f"funding_spread 반환값이 유효하지 않음: NaN (날짜: {d})\n" f"조치: spread 함수 또는 dict 값 확인 필요")

    if math.isinf(spread):
        raise ValueError(f"funding_spread 반환값이 유효하지 않음: inf (날짜: {d})\n" f"조치: spread 함수 또는 dict 값 확인 필요")

    # 5. 반환값 검증: spread > 0 (음수, 0 불허)
    if spread <= 0:
        raise ValueError(f"funding_spread는 양수여야 합니다 (> 0): {spread} (날짜: {d})\n" f"조치: spread 값을 양수로 수정")

    return spread


def _validate_ffr_coverage(
    overlap_start: date,
    overlap_end: date,
    ffr_df: pd.DataFrame,
) -> None:
    """
    overlap 기간에 필요한 FFR 데이터 커버리지를 사전 검증한다.

    Args:
        overlap_start: 겹치는 기간 시작일
        overlap_end: 겹치는 기간 종료일
        ffr_df: FFR DataFrame (DATE: str (yyyy-mm), FFR: float)

    Raises:
        ValueError: FFR 데이터 부족 시 (필요 월 범위 미커버 또는 월 차 정책 위반)
    """
    # 1. 필요한 월 범위 계산
    start_year_month = f"{overlap_start.year:04d}-{overlap_start.month:02d}"
    end_year_month = f"{overlap_end.year:04d}-{overlap_end.month:02d}"

    # 2. FFR 데이터 존재 여부 확인
    ffr_dates = set(ffr_df[COL_FFR_DATE])
    if not ffr_dates:
        raise ValueError(f"FFR 데이터 부족: 필요 기간 {start_year_month}~{end_year_month}에 대한 " f"FFR 데이터가 전혀 존재하지 않습니다.")

    # 3. FFR 데이터 범위 확인
    ffr_start = min(ffr_dates)
    ffr_end = max(ffr_dates)

    # 4. overlap 기간의 모든 월 생성
    required_months = set()
    current = overlap_start
    while current <= overlap_end:
        month_str = f"{current.year:04d}-{current.month:02d}"
        required_months.add(month_str)
        # 다음 달로 이동
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    # 5. 필요한 월 중 FFR 데이터가 없는 월 찾기
    missing_months = required_months - ffr_dates

    # 6. 누락된 월이 있으면 가장 가까운 이전 월 찾기 및 월 차 검증
    if missing_months:
        for missing_month in sorted(missing_months):
            # 이전 월 찾기
            previous_dates = [d for d in ffr_dates if d < missing_month]
            if not previous_dates:
                raise ValueError(
                    f"FFR 데이터 부족: 필요 기간 {start_year_month}~{end_year_month}에서 {missing_month}의 "
                    f"FFR 데이터가 없으며, 이전 데이터도 존재하지 않습니다. "
                    f"FFR 데이터 범위: {ffr_start}~{ffr_end}"
                )

            closest_date_str = max(previous_dates)
            # 월 차이 계산
            missing_year, missing_month_num = map(int, missing_month.split("-"))
            closest_year, closest_month_num = map(int, closest_date_str.split("-"))
            total_months = (missing_year - closest_year) * 12 + (missing_month_num - closest_month_num)

            if total_months > MAX_FFR_MONTHS_DIFF:
                raise ValueError(
                    f"FFR 데이터 부족: 필요 기간 {start_year_month}~{end_year_month}에서 {missing_month}의 "
                    f"FFR 데이터가 없으며, 가장 가까운 이전 데이터는 {closest_date_str} ({total_months}개월 전)입니다. "
                    f"최대 {MAX_FFR_MONTHS_DIFF}개월 이내의 데이터만 사용 가능합니다. "
                    f"FFR 데이터 범위: {ffr_start}~{ffr_end}"
                )


def _calculate_daily_cost(
    date_value: date,
    ffr_dict: dict[str, float],
    expense_dict: dict[str, float],
    funding_spread: FundingSpreadSpec,
    leverage: float,
) -> float:
    """
    특정 날짜의 일일 비용률을 계산한다.

    FFR 및 Expense 데이터 커버리지는 호출 측에서 사전 검증되어야 한다.

    Args:
        date_value: 계산 대상 날짜
        ffr_dict: 연방기금금리 딕셔너리 ({"YYYY-MM": ffr_value})
        expense_dict: 운용비용 딕셔너리 ({"YYYY-MM": expense_value}, 0~1 비율)
        funding_spread: FFR에 더해지는 스프레드
            - float: 고정 spread (예: 0.006 = 0.6%)
            - dict[str, float]: 월별 spread ({"YYYY-MM": spread})
            - Callable[[date], float]: 날짜를 받아 spread를 반환하는 함수
        leverage: 레버리지 배율 (예: 3.0 = 3배 레버리지)

    Returns:
        일일 비용률 (소수, 예: 0.0001905 = 0.01905%)

    Raises:
        ValueError: FFR 또는 Expense 데이터가 존재하지 않을 때
        ValueError: funding_spread가 유효하지 않을 때 (NaN, inf, <= 0, 키 누락 등)
    """
    # 1. 해당 월의 FFR 조회 (딕셔너리 O(1) 조회)
    ffr = lookup_ffr(date_value, ffr_dict)

    # 2. 해당 월의 Expense Ratio 조회 (딕셔너리 O(1) 조회)
    expense_ratio = lookup_expense(date_value, expense_dict)

    # 3. 동적 spread 해석
    # FundingSpreadSpec 타입에 따라 float, dict, Callable 처리
    spread = _resolve_spread(date_value, funding_spread)

    # 4. All-in funding rate 계산
    # FFR은 0~1 비율이므로 직접 사용 (예: 0.05 = 5.0%)
    funding_rate = ffr + spread

    # 5. 레버리지 비용 (차입 비율 = leverage - 1)
    # 레버리지 배율에 따라 빌린 돈의 비율 계산
    # 예: 3배 레버리지 = 자기 자본 1배 + 빌린 돈 2배 → leverage - 1 = 2
    # 예: 2배 레버리지 = 자기 자본 1배 + 빌린 돈 1배 → leverage - 1 = 1
    leverage_cost = funding_rate * (leverage - 1)

    # 6. 총 연간 비용
    # 레버리지 비용 + 운용 비용
    annual_cost = leverage_cost + expense_ratio

    # 7. 일별 비용 (연간 거래일 수로 환산)
    # 연간 비용을 거래일 수로 나눔 (약 252일)
    daily_cost = annual_cost / TRADING_DAYS_PER_YEAR

    # 계산된 일일 비용 반환
    return daily_cost


# ============================================================
# 벡터화 내부 함수 (성능 최적화용)
# ============================================================


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


def _calculate_metrics_fast(
    actual_prices: np.ndarray,
    simulated_prices: np.ndarray,
) -> tuple[float, float, float]:
    """
    누적배수 로그차이 기반 메트릭을 경량으로 계산한다 (벡터화 버전).

    기존 calculate_validation_metrics에서 RMSE, mean, max 세 가지만 추출한
    경량 버전이다. extract_overlap_period, signed log diff, DataFrame 생성 등을
    생략하여 그리드 서치 성능을 개선한다.

    계산 방식 (기존 _calculate_cumul_multiple_log_diff와 동일):
        M_actual(t) = actual_prices(t) / actual_prices(0)
        M_sim(t) = simulated_prices(t) / simulated_prices(0)
        로그차이(%) = |ln(M_actual(t) / M_sim(t))| × 100

    Args:
        actual_prices: 실제 가격 numpy 배열
        simulated_prices: 시뮬레이션 가격 numpy 배열

    Returns:
        (rmse, mean, max) 튜플 (단위: %)
    """
    # 1. 누적배수 계산
    m_actual = actual_prices / actual_prices[0]
    m_simul = simulated_prices / simulated_prices[0]

    # 2. 로그차이 abs (%) 계산
    ratio = m_actual / m_simul
    log_diff_abs_pct = np.abs(np.log(np.maximum(ratio, EPSILON))) * 100.0

    # 3. RMSE, mean, max 계산
    rmse = float(np.sqrt(np.mean(log_diff_abs_pct**2)))
    mean_val = float(np.mean(log_diff_abs_pct))
    max_val = float(np.max(log_diff_abs_pct))

    return rmse, mean_val, max_val


def simulate(
    underlying_df: pd.DataFrame,
    leverage: float,
    expense_df: pd.DataFrame,
    initial_price: float,
    ffr_df: pd.DataFrame | None = None,
    funding_spread: FundingSpreadSpec = DEFAULT_FUNDING_SPREAD,
    ffr_dict: dict[str, float] | None = None,
    expense_dict: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    기초 자산 데이터로부터 레버리지 ETF를 시뮬레이션한다.

    일일 리밸런싱을 가정하여 각 거래일마다 기초 자산 수익률의
    레버리지 배수만큼 움직이도록 계산한다. 스왑비용은 연방기금금리와
    스프레드를 기반으로 동적으로 계산하며, 운용비용은 월별 데이터를 사용한다.

    FFR 및 Expense 데이터 커버리지는 함수 내부에서 자동 검증된다.

    Args:
        underlying_df: 기초 자산 DataFrame (Date, Close 컬럼 필수)
        leverage: 레버리지 배수 (예: 3.0)
        expense_df: 운용비용 DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율))
        initial_price: 시작 가격
        ffr_df: 연방기금금리 DataFrame (DATE: str (yyyy-mm), FFR: float), ffr_dict와 배타적
        funding_spread: FFR에 더해지는 스프레드
            - float: 고정 spread (예: 0.006 = 0.6%)
            - dict[str, float]: 월별 spread ({"YYYY-MM": spread})
            - Callable[[date], float]: 날짜를 받아 spread를 반환하는 함수
        ffr_dict: 이미 검증된 FFR 딕셔너리 (내부 사용), ffr_df와 배타적
        expense_dict: 이미 검증된 Expense 딕셔너리 (내부 사용)

    Returns:
        시뮬레이션된 레버리지 ETF DataFrame (Date, Open, High, Low, Close, Volume 컬럼)

    Raises:
        ValueError: 파라미터가 유효하지 않을 때
        ValueError: 필수 컬럼이 누락되었을 때
        ValueError: FFR 또는 Expense 데이터 커버리지가 부족할 때
        ValueError: ffr_df와 ffr_dict 모두 제공되거나 모두 누락된 경우
        ValueError: funding_spread가 유효하지 않을 때 (NaN, inf, <= 0, 키 누락 등)
    """
    # 1. 파라미터 검증
    if leverage <= 0:
        raise ValueError(f"leverage는 양수여야 합니다: {leverage}")

    if initial_price <= 0:
        raise ValueError(f"initial_price는 양수여야 합니다: {initial_price}")

    # ffr_df와 ffr_dict 중 정확히 하나만 제공되어야 함
    if (ffr_df is None) == (ffr_dict is None):
        raise ValueError("ffr_df 또는 ffr_dict 중 정확히 하나만 제공해야 합니다")

    # 2. 필수 컬럼 검증
    # 학습 포인트: set(집합) 자료형
    # - {값1, 값2}: 중괄호로 생성, 중복 없음, 순서 없음
    # - set 연산: A - B (차집합), A & B (교집합), A | B (합집합)
    required_cols = {COL_DATE, COL_OPEN, COL_CLOSE}  # 필요한 컬럼 집합
    missing_cols = required_cols - set(underlying_df.columns)  # 차집합: 필요한데 없는 컬럼
    if missing_cols:  # 빈 set은 False, 값 있으면 True
        raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_cols}")

    if underlying_df.empty:
        raise ValueError("underlying_df가 비어있습니다")

    if expense_df.empty:
        raise ValueError("expense_df가 비어있습니다")

    # 3. FFR 처리
    if ffr_df is not None:
        # ffr_df 제공 시: 검증 + 변환
        start_date = underlying_df[COL_DATE].min()
        end_date = underlying_df[COL_DATE].max()
        _validate_ffr_coverage(start_date, end_date, ffr_df)
        ffr_dict_to_use: dict[str, float] = create_ffr_dict(ffr_df)
    else:
        # ffr_dict 직접 제공 시: 이미 검증된 것으로 간주
        ffr_dict_to_use = cast(dict[str, float], ffr_dict)

    # 4. Expense 처리
    if expense_dict is None:
        # expense_df 제공 시: 변환
        expense_dict_to_use: dict[str, float] = create_expense_dict(expense_df)
    else:
        # expense_dict 직접 제공 시: 이미 검증된 것으로 간주
        expense_dict_to_use = expense_dict

    # 5. 데이터 복사 (원본 보존)
    # 학습 포인트: DataFrame 인덱싱과 복사
    # - df[[컬럼1, 컬럼2]]: 리스트로 여러 컬럼 선택
    # - .copy(): 깊은 복사 (원본 데이터 보호)
    df = underlying_df[[COL_DATE, COL_OPEN, COL_CLOSE]].copy()

    # 6. 일일 수익률 계산
    # 학습 포인트: .pct_change() - 이전 값 대비 변화율 계산
    # (오늘 값 - 어제 값) / 어제 값
    # 예: [100, 110, 105] -> [NaN, 0.1, -0.0454...]
    df["underlying_return"] = df[COL_CLOSE].pct_change()

    # 7. 레버리지 ETF 가격 계산 (복리, 동적 비용 반영)
    # 첫 날은 initial_price, 이후는 전일 가격 * (1 + 수익률)
    # 학습 포인트: 리스트에 값을 누적하며 계산
    leveraged_prices = [initial_price]  # 빈 리스트에 초기값 추가

    # 학습 포인트: range(시작, 끝) - 시작부터 끝-1까지 반복
    # len(df)가 100이면 range(1, 100)은 1~99 (총 99번)
    for i in range(1, len(df)):
        # .iloc[i]: i번째 행 접근 (0부터 시작하는 인덱스)
        # [컬럼명]: 해당 컬럼 값 추출
        underlying_return = df.iloc[i]["underlying_return"]

        # 학습 포인트: pd.isna() - NaN(결측치) 여부 확인
        # pct_change()의 첫 값은 항상 NaN (이전 값 없음)
        if pd.isna(underlying_return):
            # 첫 번째 행의 경우 수익률이 NaN이므로 initial_price 유지
            leveraged_prices.append(initial_price)
        else:
            # 동적 비용 계산
            current_date = df.iloc[i][COL_DATE]
            daily_cost = _calculate_daily_cost(
                current_date, ffr_dict_to_use, expense_dict_to_use, funding_spread, leverage
            )

            # 레버리지 수익률 = 기초 자산 수익률 × 배율 - 일일 비용
            # 예: 기초 자산 +1%, 3배 레버리지 -> +3% - 비용
            leveraged_return = underlying_return * leverage - daily_cost

            # 가격 업데이트 (복리 효과)
            # 학습 포인트: 리스트[-1]은 마지막 요소 (파이썬 음수 인덱싱)
            new_price = leveraged_prices[-1] * (1 + leveraged_return)
            leveraged_prices.append(new_price)  # 리스트 끝에 추가

    # 8. 기초 자산 Close 보존 (오버나이트 수익률 계산에 필요)
    underlying_close_series = df[COL_CLOSE].copy()

    # 계산된 가격 리스트를 DataFrame 컬럼에 할당
    df[COL_CLOSE] = leveraged_prices

    # 9. OHLV 데이터 구성
    # Open: 기초 자산의 오버나이트 갭을 레버리지 배율로 반영
    # 수식: TQQQ_Open(t) = TQQQ_Close(t-1) × (1 + (QQQ_Open(t)/QQQ_Close(t-1) - 1) × leverage)
    underlying_overnight_return = df[COL_OPEN] / underlying_close_series.shift(1) - 1
    leveraged_open = df[COL_CLOSE].shift(1) * (1 + underlying_overnight_return * leverage)
    # 첫날은 initial_price (shift(1)로 NaN 발생 → fillna)
    df[COL_OPEN] = leveraged_open.fillna(initial_price)

    # High, Low: 합성 데이터이므로 Open/Close 기반 근사값 사용
    df[COL_HIGH] = df[[COL_OPEN, COL_CLOSE]].max(axis=1)
    df[COL_LOW] = df[[COL_OPEN, COL_CLOSE]].min(axis=1)
    # Volume: 합성 데이터이므로 0
    df[COL_VOLUME] = 0

    # 10. 불필요한 컬럼 제거 및 순서 정렬
    result_df = df[REQUIRED_COLUMNS].copy()

    return result_df


def _calculate_cumul_multiple_log_diff(
    actual_prices: pd.Series,  # Series: DataFrame의 한 컬럼 (1차원 배열)
    simulated_prices: pd.Series,
) -> pd.Series:
    """
    누적배수 기반 로그차이를 계산한다.

    스케일 무관성을 가진 추적오차 지표로, 첫날 기준 누적 자산배수의 로그 비율을 측정한다.

    학습 포인트:
    1. Series: DataFrame의 한 컬럼, 인덱스를 가진 1차원 배열
    2. numpy 브로드캐스팅: 배열 전체에 연산 자동 적용
    3. np.log(): 자연로그 (ln)
    4. np.maximum(): 두 값 중 큰 값 선택 (0으로 나누기 방지)

    계산 방식:
      - M_actual(t) = actual_close(t) / actual_close(0)  (누적 자산배수)
      - M_sim(t) = simul_close(t) / simul_close(0)
      - 로그차이(%) = |ln(M_actual(t) / M_sim(t))| × 100

    특징:
      - 스케일 무관: 실제 10 vs 시뮬 9 = 실제 1000 vs 시뮬 900 (동일한 비율)
      - 안정성: 특정 기준일 의존 없음 (롤링 윈도우 미사용)
      - 금융 표준: 연속 복리 수익률 차이와 동일한 개념

    Args:
        actual_prices: 실제 TQQQ 종가 시계열
        simulated_prices: 시뮬레이션 TQQQ 종가 시계열

    Returns:
        누적배수 로그차이 시계열 (단위: %)

    Raises:
        ValueError: 입력 시계열 길이가 다를 때
    """
    if len(actual_prices) != len(simulated_prices):
        raise ValueError(f"가격 시계열 길이가 일치하지 않습니다: actual={len(actual_prices)}, simulated={len(simulated_prices)}")

    # 첫날 기준 누적배수 계산
    initial_actual = float(actual_prices.iloc[0])
    initial_simul = float(simulated_prices.iloc[0])

    # 학습 포인트: Series 브로드캐스팅
    # Series / 스칼라 → Series의 모든 요소를 스칼라로 나눔
    # 예: [100, 110, 105] / 100 → [1.0, 1.1, 1.05]
    m_actual = actual_prices / initial_actual
    m_simul = simulated_prices / initial_simul

    # 로그 비율의 절대값
    # 학습 포인트: numpy 함수는 배열 전체에 적용됨
    ratio = m_actual / m_simul  # Series / Series → Series
    # np.maximum(ratio, EPSILON): ratio와 EPSILON 중 큰 값 (0 방지)
    # np.log(): 자연로그 계산
    # np.abs(): 절대값
    # * 100.0: 퍼센트로 변환
    # pd.Series(..., index=...): 원래 인덱스 유지하며 Series 생성
    log_diff_pct = pd.Series(np.abs(np.log(np.maximum(ratio, EPSILON))) * 100.0, index=actual_prices.index)

    return log_diff_pct


def _save_daily_comparison_csv(
    sim_overlap: pd.DataFrame,
    actual_overlap: pd.DataFrame,
    cumul_multiple_log_diff_series: pd.Series,
    signed_log_diff_series: pd.Series,
    output_path: Path,
    integrity_tolerance: float | None = None,
) -> None:
    """
    일별 비교 CSV를 저장한다.

    calculate_validation_metrics()의 헬퍼 함수.
    누적배수 로그차이(abs, signed)는 이미 계산된 값을 받아서 사용한다.

    Args:
        sim_overlap: 겹치는 기간의 시뮬레이션 DataFrame
        actual_overlap: 겹치는 기간의 실제 DataFrame
        cumul_multiple_log_diff_series: 누적배수 로그차이 abs 시계열 (이미 계산됨)
        signed_log_diff_series: 누적배수 로그차이 signed 시계열 (이미 계산됨)
        output_path: CSV 저장 경로
        integrity_tolerance: 무결성 체크 허용 오차 (%, None이면 기본값 사용)
    """
    # 1. 기본 데이터 준비
    # 학습 포인트: 딕셔너리 생성
    # {키1: 값1, 키2: 값2, ...}
    # 여러 Series를 담는 딕셔너리 (나중에 DataFrame으로 변환)
    comparison_data = {
        DISPLAY_DATE: actual_overlap[COL_DATE],
        COL_ACTUAL_CLOSE: actual_overlap[COL_CLOSE],
        COL_SIMUL_CLOSE: sim_overlap[COL_CLOSE],
    }

    # 2. 일일 수익률 계산
    # .pct_change(): 이전 값 대비 변화율
    # * 100: 퍼센트로 변환 (0.05 → 5.0%)
    actual_returns = actual_overlap[COL_CLOSE].pct_change() * 100  # %
    sim_returns = sim_overlap[COL_CLOSE].pct_change() * 100  # %

    # 딕셔너리에 새 키-값 쌍 추가
    comparison_data[COL_ACTUAL_DAILY_RETURN] = actual_returns
    comparison_data[COL_SIMUL_DAILY_RETURN] = sim_returns
    # .abs(): 절대값 (음수를 양수로)
    comparison_data[COL_DAILY_RETURN_ABS_DIFF] = (actual_returns - sim_returns).abs()

    # 3. 누적수익률 (%)
    initial_actual = float(actual_overlap.iloc[0][COL_CLOSE])
    initial_sim = float(sim_overlap.iloc[0][COL_CLOSE])

    actual_cumulative = (actual_overlap[COL_CLOSE] / initial_actual - 1) * 100
    sim_cumulative = (sim_overlap[COL_CLOSE] / initial_sim - 1) * 100

    comparison_data[COL_ACTUAL_CUMUL_RETURN] = actual_cumulative
    comparison_data[COL_SIMUL_CUMUL_RETURN] = sim_cumulative

    # 4. 누적배수 로그차이 abs (기존과 동일, 컬럼명만 변경)
    comparison_data[COL_CUMUL_MULTIPLE_LOG_DIFF_ABS] = cumul_multiple_log_diff_series

    # 5. 누적배수 로그차이 signed (전달받은 값 사용)
    comparison_data[COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED] = signed_log_diff_series

    # 6. 무결성 체크: abs(signed) vs abs
    # tolerance 확정값 사용 (실제 데이터 관측 기반)
    # 테스트에서는 integrity_tolerance 파라미터로 조정 가능
    if integrity_tolerance is None:
        integrity_tolerance = INTEGRITY_TOLERANCE

    validate_integrity(
        signed_series=signed_log_diff_series,
        abs_series=cumul_multiple_log_diff_series,
        tolerance=integrity_tolerance,
    )
    # 무결성 체크 통과 (ValueError 발생하지 않으면 정상)

    # 7. DataFrame 생성 및 반올림
    # 딕셔너리를 DataFrame으로 변환
    comparison_df = pd.DataFrame(comparison_data)

    # 학습 포인트: 리스트 컴프리헨션 (List Comprehension)
    # [표현식 for 변수 in 리스트 if 조건]
    # 날짜 컬럼을 제외한 모든 숫자 컬럼 선택
    num_cols = [c for c in comparison_df.columns if c != DISPLAY_DATE]

    # .round(4): 소수점 4자리로 반올림
    # comparison_df[num_cols]: 여러 컬럼 동시 선택
    comparison_df[num_cols] = comparison_df[num_cols].round(4)

    # 8. CSV 저장
    # to_csv() 메서드: DataFrame을 CSV 파일로 저장
    # index=False: 행 인덱스 제외
    comparison_df.to_csv(output_path, index=False, encoding="utf-8")


def calculate_validation_metrics(
    simulated_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    output_path: Path | None = None,
) -> ValidationMetricsDict:
    """
    시뮬레이션 검증 지표를 계산하고, 선택적으로 일별 비교 CSV를 생성한다.

    누적배수 로그차이를 한 번만 계산하고 검증 지표와 CSV 생성에 활용한다.

    Args:
        simulated_df: 시뮬레이션 DataFrame (Date, Close 컬럼 필수)
        actual_df: 실제 DataFrame (Date, Close 컬럼 필수)
        output_path: CSV 저장 경로 (None이면 저장 안 함)

    Returns:
        검증 결과 딕셔너리: {
            'overlap_start': date,
            'overlap_end': date,
            'overlap_days': int,
            'cumulative_return_simulated': float,
            'cumulative_return_actual': float,
            'cumulative_return_abs_diff': float,
            'cumul_multiple_log_diff_mean_pct': float,
            'cumul_multiple_log_diff_rmse_pct': float,
            'cumul_multiple_log_diff_max_pct': float,
        }

    Raises:
        ValueError: 겹치는 기간이 없을 때
    """
    # 1. 겹치는 기간 추출
    sim_overlap, actual_overlap = extract_overlap_period(simulated_df, actual_df)

    # 2. 일일 수익률 계산 (검증 지표용)
    sim_returns = sim_overlap[COL_CLOSE].pct_change().dropna()
    actual_returns = actual_overlap[COL_CLOSE].pct_change().dropna()

    # 3. 누적 수익률 (전통적 방식)
    sim_prod = (1 + sim_returns).prod()
    actual_prod = (1 + actual_returns).prod()
    # Scalar 타입을 Python float로 안전하게 변환 (타입 캐스팅)
    sim_cumulative = cast(float, sim_prod) - 1.0
    actual_cumulative = cast(float, actual_prod) - 1.0

    # 4. 누적배수 로그차이 abs 계산
    cumul_multiple_log_diff_series = _calculate_cumul_multiple_log_diff(
        actual_overlap[COL_CLOSE],
        sim_overlap[COL_CLOSE],
    )

    # 5. 누적배수 로그차이 signed 계산
    # 초기 가격 기준 누적수익률 (시계열)
    initial_actual = float(actual_overlap.iloc[0][COL_CLOSE])
    initial_sim = float(sim_overlap.iloc[0][COL_CLOSE])
    actual_cumulative_series = (actual_overlap[COL_CLOSE] / initial_actual - 1) * 100
    sim_cumulative_series = (sim_overlap[COL_CLOSE] / initial_sim - 1) * 100

    # signed 로그차이 계산
    signed_log_diff_series = calculate_signed_log_diff_from_cumulative_returns(
        cumul_return_real_pct=actual_cumulative_series,
        cumul_return_sim_pct=sim_cumulative_series,
    )

    # 6. 검증 지표 계산
    cumul_multiple_log_diff_mean = float(cumul_multiple_log_diff_series.mean())
    cumul_multiple_log_diff_rmse = float(np.sqrt((cumul_multiple_log_diff_series**2).mean()))
    cumul_multiple_log_diff_max = float(cumul_multiple_log_diff_series.max())

    # 7. 일별 비교 CSV 생성 (요청 시에만)
    if output_path is not None:
        _save_daily_comparison_csv(
            sim_overlap,
            actual_overlap,
            cumul_multiple_log_diff_series,
            signed_log_diff_series,
            output_path,
        )

    # 8. 누적수익률 상대차이 계산 (마지막 날 기준, 실제 기준 퍼센트)
    cumulative_return_rel_diff_pct = ((sim_cumulative - actual_cumulative) / actual_cumulative) * 100

    # 9. 마지막 날 종가 추출
    final_close_actual = float(actual_overlap.iloc[-1][COL_CLOSE])
    final_close_simulated = float(sim_overlap.iloc[-1][COL_CLOSE])

    # 10. 종가 상대차이 계산 (실제 기준 퍼센트)
    final_close_rel_diff_pct = ((final_close_simulated - final_close_actual) / final_close_actual) * 100

    # 11. 검증 결과 반환
    return {
        # 기간 정보
        KEY_OVERLAP_START: sim_overlap[COL_DATE].iloc[0],
        KEY_OVERLAP_END: sim_overlap[COL_DATE].iloc[-1],
        KEY_OVERLAP_DAYS: len(sim_overlap),
        # 종가 정보
        KEY_FINAL_CLOSE_ACTUAL: final_close_actual,
        KEY_FINAL_CLOSE_SIMULATED: final_close_simulated,
        KEY_FINAL_CLOSE_REL_DIFF: final_close_rel_diff_pct,
        # 누적 수익률
        KEY_CUMULATIVE_RETURN_SIMULATED: sim_cumulative,
        KEY_CUMULATIVE_RETURN_ACTUAL: actual_cumulative,
        KEY_CUMULATIVE_RETURN_REL_DIFF: cumulative_return_rel_diff_pct,
        # 누적배수 로그차이 기반 정확도 지표
        KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN: cumul_multiple_log_diff_mean,
        KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE: cumul_multiple_log_diff_rmse,
        KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX: cumul_multiple_log_diff_max,
    }


# ============================================================
# Softplus 파라미터 최적화 (2-stage grid search)
# ============================================================


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


# ============================================================
# 워크포워드 검증 (Local Refine + 60m Train / 1m Test)
# ============================================================


def _local_refine_search(
    underlying_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    a_prev: float,
    b_prev: float,
    leverage: float = DEFAULT_LEVERAGE_MULTIPLIER,
    max_workers: int | None = None,
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
        max_workers: 최대 워커 수 (None이면 기본값 2)
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
    initial_price, cache_data = _prepare_optimization_data(underlying_df, actual_df, ffr_df, expense_df)

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

    # 7. 병렬 실행
    candidates = execute_parallel(
        _evaluate_softplus_candidate,
        param_combinations,
        max_workers=max_workers,
        initializer=init_worker_cache,
        initargs=(cache_data,),
        log_progress=False,
    )

    # 8. RMSE 기준 정렬 및 최적값 추출
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
    max_workers: int | None = None,
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
        max_workers: 최대 워커 수 (None이면 기본값 2)
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
                max_workers=max_workers,
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
                max_workers=max_workers,
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

        # 10. 테스트 월 FFR 및 spread 계산
        test_year, test_mon = map(int, test_month.split("-"))
        test_date = date(test_year, test_mon, 1)
        ffr_ratio_test = lookup_ffr(test_date, ffr_dict_for_spread)
        ffr_pct_test = ffr_ratio_test * 100.0
        spread_test_val = compute_softplus_spread(a_best, b_best, ffr_ratio_test)

        # 11. 결과 저장
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

        # 12. 다음 구간을 위해 현재 최적값 저장
        a_prev = a_best
        b_prev = b_best

        logger.debug(
            f"워크포워드 [{i + 1}/{len(test_month_indices)}] "
            f"test={test_month}, a={a_best:.4f}, b={b_best:.4f}, "
            f"train_rmse={train_rmse:.4f}%, test_rmse={test_rmse:.4f}%"
        )

    # 13. 결과 DataFrame 생성
    result_df = pd.DataFrame(results)

    # 14. 요약 통계 계산
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

    rmse, _, _ = _calculate_metrics_fast(actual_prices, simulated_prices)

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
        5. _calculate_metrics_fast()로 RMSE 산출

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
