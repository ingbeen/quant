"""레버리지 ETF 시뮬레이션 모듈

QQQ와 같은 기초 자산 데이터로부터 TQQQ와 같은 레버리지 ETF를 시뮬레이션한다.
일일 리밸런싱 기반의 3배 레버리지 ETF 동작을 재현한다.
"""

# 1. 표준 라이브러리 임포트
import math
from datetime import date
from pathlib import Path
from typing import TypedDict, cast

# 2. 서드파티 라이브러리 임포트
import numpy as np
import pandas as pd

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
    INTEGRITY_TOLERANCE,
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
)
from qbt.tqqq.data_loader import (
    create_expense_dict,
    create_ffr_dict,
    lookup_expense,
    lookup_ffr,
    lookup_funding_spread,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period

logger = get_logger(__name__)


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


# 동적 funding_spread 지원 타입 정의
# - float: 고정 spread (기존 동작)
# - dict[str, float]: 월별 spread ({"YYYY-MM": spread})
FundingSpreadSpec = float | dict[str, float]


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


def _compute_softplus_spread(a: float, b: float, ffr_ratio: float) -> float:
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
            f"_compute_softplus_spread 결과가 유효하지 않음: spread={spread} <= 0\n"
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
        spread = _compute_softplus_spread(a, b, ffr_ratio)
        spread_map[month_key] = spread

    logger.debug(
        f"월별 spread 맵 생성 완료: {len(spread_map)}개월, "
        f"a={a}, b={b}, spread 범위=[{min(spread_map.values()):.6f}, {max(spread_map.values()):.6f}]"
    )

    return spread_map


def _resolve_spread(d: date, spread_spec: FundingSpreadSpec) -> float:
    """
    특정 날짜의 funding_spread 값을 해석한다.

    FundingSpreadSpec 타입에 따라 다르게 처리:
    - float: 그대로 반환
    - dict[str, float]: 월별 키 "YYYY-MM"으로 조회, 키 없으면 MAX_FFR_MONTHS_DIFF 이내 이전 월 fallback

    제약 조건:
    - 반환 spread는 항상 > 0 (음수 불허, 0도 불허)
    - NaN/inf 반환 시 ValueError
    - min/max 클리핑 금지 (검증만 수행)

    Args:
        d: 대상 날짜
        spread_spec: funding_spread 스펙 (float 또는 dict)

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
    else:
        spread = lookup_funding_spread(d, spread_spec)

    # 3. 반환값 검증: NaN/inf 체크
    if math.isnan(spread):
        raise ValueError(f"funding_spread 반환값이 유효하지 않음: NaN (날짜: {d})\n" f"조치: spread dict 값 확인 필요")

    if math.isinf(spread):
        raise ValueError(f"funding_spread 반환값이 유효하지 않음: inf (날짜: {d})\n" f"조치: spread dict 값 확인 필요")

    # 4. 반환값 검증: spread > 0 (음수, 0 불허)
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


def simulate(
    underlying_df: pd.DataFrame,
    leverage: float,
    expense_df: pd.DataFrame,
    initial_price: float,
    *,
    ffr_df: pd.DataFrame | None = None,
    funding_spread: FundingSpreadSpec,
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
        ffr_df: 연방기금금리 DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율)), ffr_dict와 배타적
        funding_spread: FFR에 더해지는 스프레드
            - float: 고정 spread (예: 0.006 = 0.6%)
            - dict[str, float]: 월별 spread ({"YYYY-MM": spread})
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
    required_cols = {COL_DATE, COL_OPEN, COL_CLOSE}
    missing_cols = required_cols - set(underlying_df.columns)
    if missing_cols:
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
    df = underlying_df[[COL_DATE, COL_OPEN, COL_CLOSE]].copy()

    # 6. 일일 수익률 계산
    df["underlying_return"] = df[COL_CLOSE].pct_change()

    # 7. 레버리지 ETF 가격 계산 (복리, 동적 비용 반영)
    leveraged_prices = [initial_price]

    for i in range(1, len(df)):
        underlying_return = df.iloc[i]["underlying_return"]

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
            new_price = leveraged_prices[-1] * (1 + leveraged_return)
            leveraged_prices.append(new_price)

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
    actual_prices: pd.Series,
    simulated_prices: pd.Series,
) -> pd.Series:
    """
    누적배수 기반 로그차이를 계산한다.

    스케일 무관성을 가진 추적오차 지표로, 첫날 기준 누적 자산배수의 로그 비율을 측정한다.

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

    m_actual = actual_prices / initial_actual
    m_simul = simulated_prices / initial_simul

    # 로그 비율의 절대값 (%)
    ratio = m_actual / m_simul
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
    comparison_data = {
        DISPLAY_DATE: actual_overlap[COL_DATE],
        COL_ACTUAL_CLOSE: actual_overlap[COL_CLOSE],
        COL_SIMUL_CLOSE: sim_overlap[COL_CLOSE],
    }

    # 2. 일일 수익률 계산 (%)
    actual_returns = actual_overlap[COL_CLOSE].pct_change() * 100  # %
    sim_returns = sim_overlap[COL_CLOSE].pct_change() * 100  # %

    comparison_data[COL_ACTUAL_DAILY_RETURN] = actual_returns
    comparison_data[COL_SIMUL_DAILY_RETURN] = sim_returns
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
    comparison_df = pd.DataFrame(comparison_data)

    num_cols = [c for c in comparison_df.columns if c != DISPLAY_DATE]
    comparison_df[num_cols] = comparison_df[num_cols].round(4)

    # 8. CSV 저장
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
