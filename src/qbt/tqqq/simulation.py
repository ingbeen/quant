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
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_ACTUAL_CUMUL_RETURN,
    COL_ACTUAL_DAILY_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_EXPENSE_DATE,
    COL_EXPENSE_VALUE,
    COL_FFR_DATE,
    COL_FFR_VALUE,
    COL_SIMUL_CLOSE,
    COL_SIMUL_CUMUL_RETURN,
    COL_SIMUL_DAILY_RETURN,
    DEFAULT_FUNDING_SPREAD,
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_SPREAD_RANGE,
    DEFAULT_SPREAD_STEP,
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
    KEY_SPREAD,
    MAX_EXPENSE_MONTHS_DIFF,
    MAX_FFR_MONTHS_DIFF,
    MAX_TOP_STRATEGIES,
)
from qbt.utils import get_logger
from qbt.utils.parallel_executor import WORKER_CACHE, execute_parallel, init_worker_cache

logger = get_logger(__name__)


def _create_monthly_data_dict(df: pd.DataFrame, date_col: str, value_col: str, data_type: str) -> dict[str, float]:
    """
    월별 데이터 DataFrame을 딕셔너리로 변환한다 (O(1) 조회용).

    FFR, Expense Ratio 등 월별 데이터를 공통으로 처리하는 제네릭 함수이다.

    Args:
        df: 월별 데이터 DataFrame
        date_col: 날짜 컬럼명 (yyyy-mm 문자열 형식)
        value_col: 값 컬럼명
        data_type: 데이터 타입 ("FFR", "Expense" 등, 에러 메시지용)

    Returns:
        {"YYYY-MM": value} 형태의 딕셔너리

    Raises:
        ValueError: 빈 DataFrame 또는 중복 월 발견 시
    """
    # 1. 빈 DataFrame 검증
    if df.empty:
        raise ValueError(f"{data_type} 데이터가 비어있습니다")

    # 2. 딕셔너리 생성 및 중복 월 검증
    data_dict: dict[str, float] = {}
    for _, row in df.iterrows():
        month_key = str(row[date_col])
        value = float(row[value_col])

        # 중복 월 발견 시 즉시 예외 (데이터 무결성 보장)
        if month_key in data_dict:
            raise ValueError(
                f"{data_type} 데이터 무결성 오류: 월 {month_key}이(가) 중복 존재합니다. " f"기존 값: {data_dict[month_key]}, 중복 값: {value}"
            )

        data_dict[month_key] = value

    return data_dict


def _lookup_monthly_data(date_value: date, data_dict: dict[str, float], max_months_diff: int, data_type: str) -> float:
    """
    특정 날짜의 월별 데이터 값을 딕셔너리에서 조회한다.

    FFR, Expense Ratio 등 월별 데이터를 공통으로 조회하는 제네릭 함수이다.

    Args:
        date_value: 조회할 날짜
        data_dict: 월별 데이터 딕셔너리 ({"YYYY-MM": value})
        max_months_diff: 최대 허용 월 차이 (예: FFR=2, Expense=12)
        data_type: 데이터 타입 ("FFR", "Expense" 등, 에러 메시지용)

    Returns:
        해당 월 또는 가장 가까운 이전 월의 값

    Raises:
        ValueError: 월 키 없음 + 이전 월 없음, 또는 월 차이 초과 시
    """
    # 1. 해당 월의 키 생성
    year_month_str = f"{date_value.year:04d}-{date_value.month:02d}"

    # 2. 딕셔너리에서 직접 조회 시도
    if year_month_str in data_dict:
        return data_dict[year_month_str]

    # 3. 월 키가 없으면 이전 월 중 가장 가까운 값 사용
    previous_months = [key for key in data_dict.keys() if key < year_month_str]

    if not previous_months:
        raise ValueError(f"{data_type} 데이터 부족: {year_month_str} 이전의 {data_type} 데이터가 존재하지 않습니다.")

    # 4. 가장 가까운 이전 월 찾기
    closest_month = max(previous_months)

    # 5. 월 차이 계산
    query_year, query_month = date_value.year, date_value.month
    closest_year, closest_month_num = map(int, closest_month.split("-"))
    total_months = (query_year - closest_year) * 12 + (query_month - closest_month_num)

    # 6. 월 차이가 max_months_diff 초과 시 예외
    if total_months > max_months_diff:
        raise ValueError(
            f"{data_type} 데이터 부족: 필요 월 {year_month_str}의 {data_type} 데이터가 없으며, "
            f"가장 가까운 이전 데이터는 {closest_month} ({total_months}개월 전)입니다. "
            f"최대 {max_months_diff}개월 이내의 데이터만 사용 가능합니다."
        )

    # 7. 가장 가까운 이전 월의 값 반환
    return data_dict[closest_month]


def _create_ffr_dict(ffr_df: pd.DataFrame) -> dict[str, float]:
    """
    FFR DataFrame을 딕셔너리로 변환한다 (O(1) 조회용).

    내부적으로 제네릭 월별 데이터 함수를 사용한다.

    Args:
        ffr_df: FFR DataFrame (DATE: str (yyyy-mm), VALUE: float)

    Returns:
        {"YYYY-MM": ffr_value} 형태의 딕셔너리

    Raises:
        ValueError: 빈 DataFrame 또는 중복 월 발견 시
    """
    return _create_monthly_data_dict(ffr_df, COL_FFR_DATE, COL_FFR_VALUE, "FFR")


def _lookup_ffr(date_value: date, ffr_dict: dict[str, float]) -> float:
    """
    특정 날짜의 FFR 값을 딕셔너리에서 조회한다.

    내부적으로 제네릭 월별 데이터 함수를 사용한다.

    Args:
        date_value: 조회할 날짜
        ffr_dict: FFR 딕셔너리 ({"YYYY-MM": ffr_value})

    Returns:
        FFR 값 (0~1 비율, 예: 0.045 = 4.5%)

    Raises:
        ValueError: 월 키 없음 + 이전 월 없음, 또는 월 차이 초과 시
    """
    return _lookup_monthly_data(date_value, ffr_dict, MAX_FFR_MONTHS_DIFF, "FFR")


def _create_expense_dict(expense_df: pd.DataFrame) -> dict[str, float]:
    """
    Expense Ratio DataFrame을 딕셔너리로 변환한다 (O(1) 조회용).

    내부적으로 제네릭 월별 데이터 함수를 사용한다.

    Args:
        expense_df: Expense Ratio DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율))

    Returns:
        {"YYYY-MM": expense_value} 형태의 딕셔너리

    Raises:
        ValueError: 빈 DataFrame 또는 중복 월 발견 시
    """
    return _create_monthly_data_dict(expense_df, COL_EXPENSE_DATE, COL_EXPENSE_VALUE, "Expense")


def _lookup_expense(date_value: date, expense_dict: dict[str, float]) -> float:
    """
    특정 날짜의 Expense Ratio 값을 딕셔너리에서 조회한다.

    내부적으로 제네릭 월별 데이터 함수를 사용한다.

    Args:
        date_value: 조회할 날짜
        expense_dict: Expense Ratio 딕셔너리 ({"YYYY-MM": expense_value})

    Returns:
        Expense Ratio 값 (0~1 비율, 예: 0.0095 = 0.95%)

    Raises:
        ValueError: 월 키 없음 + 이전 월 없음, 또는 월 차이 초과 시
    """
    return _lookup_monthly_data(date_value, expense_dict, MAX_EXPENSE_MONTHS_DIFF, "Expense")


def validate_ffr_coverage(
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


def calculate_daily_cost(
    date_value: date,
    ffr_dict: dict[str, float],
    expense_dict: dict[str, float],
    funding_spread: float,
    leverage: float,
) -> float:
    """
    특정 날짜의 일일 비용률을 계산한다.

    FFR 및 Expense 데이터 커버리지는 호출 측에서 사전 검증되어야 한다.

    Args:
        date_value: 계산 대상 날짜
        ffr_dict: 연방기금금리 딕셔너리 ({"YYYY-MM": ffr_value})
        expense_dict: 운용비용 딕셔너리 ({"YYYY-MM": expense_value}, 0~1 비율)
        funding_spread: FFR에 더해지는 스프레드 (예: 0.006 = 0.6%)
        leverage: 레버리지 배율 (예: 3.0 = 3배 레버리지)

    Returns:
        일일 비용률 (소수, 예: 0.0001905 = 0.01905%)

    Raises:
        ValueError: FFR 또는 Expense 데이터가 존재하지 않을 때
    """
    # 1. 해당 월의 FFR 조회 (딕셔너리 O(1) 조회)
    ffr = _lookup_ffr(date_value, ffr_dict)

    # 2. 해당 월의 Expense Ratio 조회 (딕셔너리 O(1) 조회)
    expense_ratio = _lookup_expense(date_value, expense_dict)

    # 3. All-in funding rate 계산
    # FFR은 0~1 비율이므로 직접 사용 (예: 0.05 = 5.0%)
    funding_rate = ffr + funding_spread

    # 4. 레버리지 비용 (차입 비율 = leverage - 1)
    # 레버리지 배율에 따라 빌린 돈의 비율 계산
    # 예: 3배 레버리지 = 자기 자본 1배 + 빌린 돈 2배 → leverage - 1 = 2
    # 예: 2배 레버리지 = 자기 자본 1배 + 빌린 돈 1배 → leverage - 1 = 1
    leverage_cost = funding_rate * (leverage - 1)

    # 5. 총 연간 비용
    # 레버리지 비용 + 운용 비용
    annual_cost = leverage_cost + expense_ratio

    # 6. 일별 비용 (연간 거래일 수로 환산)
    # 연간 비용을 거래일 수로 나눔 (약 252일)
    daily_cost = annual_cost / TRADING_DAYS_PER_YEAR

    # 계산된 일일 비용 반환
    return daily_cost


def simulate(
    underlying_df: pd.DataFrame,
    leverage: float,
    expense_df: pd.DataFrame,
    initial_price: float,
    ffr_df: pd.DataFrame | None = None,
    funding_spread: float = DEFAULT_FUNDING_SPREAD,
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
        funding_spread: FFR에 더해지는 스프레드 (예: 0.006 = 0.6%)
        ffr_dict: 이미 검증된 FFR 딕셔너리 (내부 사용), ffr_df와 배타적
        expense_dict: 이미 검증된 Expense 딕셔너리 (내부 사용)

    Returns:
        시뮬레이션된 레버리지 ETF DataFrame (Date, Open, High, Low, Close, Volume 컬럼)

    Raises:
        ValueError: 파라미터가 유효하지 않을 때
        ValueError: 필수 컬럼이 누락되었을 때
        ValueError: FFR 또는 Expense 데이터 커버리지가 부족할 때
        ValueError: ffr_df와 ffr_dict 모두 제공되거나 모두 누락된 경우
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
    required_cols = {COL_DATE, COL_CLOSE}  # 필요한 컬럼 집합
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
        validate_ffr_coverage(start_date, end_date, ffr_df)
        ffr_dict_to_use: dict[str, float] = _create_ffr_dict(ffr_df)
    else:
        # ffr_dict 직접 제공 시: 이미 검증된 것으로 간주
        ffr_dict_to_use = cast(dict[str, float], ffr_dict)

    # 4. Expense 처리
    if expense_dict is None:
        # expense_df 제공 시: 변환
        expense_dict_to_use: dict[str, float] = _create_expense_dict(expense_df)
    else:
        # expense_dict 직접 제공 시: 이미 검증된 것으로 간주
        expense_dict_to_use = expense_dict

    # 5. 데이터 복사 (원본 보존)
    # 학습 포인트: DataFrame 인덱싱과 복사
    # - df[[컬럼1, 컬럼2]]: 리스트로 여러 컬럼 선택
    # - .copy(): 깊은 복사 (원본 데이터 보호)
    df = underlying_df[[COL_DATE, COL_CLOSE]].copy()

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
            daily_cost = calculate_daily_cost(
                current_date, ffr_dict_to_use, expense_dict_to_use, funding_spread, leverage
            )

            # 레버리지 수익률 = 기초 자산 수익률 × 배율 - 일일 비용
            # 예: 기초 자산 +1%, 3배 레버리지 -> +3% - 비용
            leveraged_return = underlying_return * leverage - daily_cost

            # 가격 업데이트 (복리 효과)
            # 학습 포인트: 리스트[-1]은 마지막 요소 (파이썬 음수 인덱싱)
            new_price = leveraged_prices[-1] * (1 + leveraged_return)
            leveraged_prices.append(new_price)  # 리스트 끝에 추가

    # 계산된 가격 리스트를 DataFrame 컬럼에 할당
    df[COL_CLOSE] = leveraged_prices

    # 8. OHLV 데이터 구성
    # Open: 전일 Close (첫날은 initial_price)
    df[COL_OPEN] = df[COL_CLOSE].shift(1).fillna(initial_price)

    # High, Low, Volume: 0 (합성 데이터이므로 사용하지 않음)
    df[COL_HIGH] = 0.0
    df[COL_LOW] = 0.0
    df[COL_VOLUME] = 0

    # 9. 불필요한 컬럼 제거 및 순서 정렬
    result_df = df[REQUIRED_COLUMNS].copy()

    return result_df


def _evaluate_cost_model_candidate(params: dict) -> dict:
    """
    단일 비용 모델 파라미터 조합을 시뮬레이션하고 평가한다.

    그리드 서치에서 병렬 실행을 위한 헬퍼 함수. pickle 가능하도록 최상위 레벨에 정의한다.
    DataFrame들과 딕셔너리들은 WORKER_CACHE에서 조회한다.

    Args:
        params: 파라미터 딕셔너리 {
            "leverage": 레버리지 배수,
            "spread": funding spread 값,
            "initial_price": 초기 가격,
        }

    Returns:
        후보 평가 결과 딕셔너리
    """
    # WORKER_CACHE에서 DataFrame들과 딕셔너리들 조회
    underlying_overlap = WORKER_CACHE["underlying_overlap"]
    actual_overlap = WORKER_CACHE["actual_overlap"]
    ffr_dict = WORKER_CACHE["ffr_dict"]
    expense_dict = WORKER_CACHE["expense_dict"]

    # expense_df 재구성 (simulate 함수가 필요로 함)
    expense_dates = list(expense_dict.keys())
    expense_values = list(expense_dict.values())
    expense_df = pd.DataFrame({"DATE": expense_dates, "VALUE": expense_values})

    # 시뮬레이션 실행
    sim_df = simulate(
        underlying_overlap,
        leverage=params["leverage"],
        expense_df=expense_df,
        initial_price=params["initial_price"],
        ffr_dict=ffr_dict,
        funding_spread=params[KEY_SPREAD],
    )

    # 검증 지표 계산
    metrics = calculate_validation_metrics(
        simulated_df=sim_df,
        actual_df=actual_overlap,
        output_path=None,  # CSV 저장 안 함
    )

    # candidate 딕셔너리 생성 (expense는 CSV에서 로드하므로 포함하지 않음)
    candidate = {
        "leverage": params["leverage"],
        KEY_SPREAD: params[KEY_SPREAD],
        **metrics,
    }

    return candidate


def extract_overlap_period(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:  # 튜플 반환 타입
    """
    두 DataFrame의 겹치는 기간을 추출한다.

    학습 포인트:
    1. set 집합 연산: & (교집합), | (합집합), - (차집합)
    2. .isin() 메서드: 값이 리스트/집합에 포함되는지 확인
    3. 메서드 체이닝: 여러 메서드를 연속 호출
    4. tuple 언패킹: 반환값을 두 변수로 받을 수 있음

    Args:
        df1: 첫 번째 DataFrame (Date 컬럼 필수)
        df2: 두 번째 DataFrame (Date 컬럼 필수)

    Returns:
        (df1_overlap, df2_overlap) 튜플
            - df1_overlap: 겹치는 기간의 df1 (reset_index 완료)
            - df2_overlap: 겹치는 기간의 df2 (reset_index 완료)

    Raises:
        ValueError: 겹치는 기간이 없을 때
    """
    # 1. 겹치는 날짜 추출
    # 학습 포인트: DataFrame 컬럼을 set으로 변환
    dates1 = set(df1[COL_DATE])  # df1의 모든 날짜를 집합으로
    dates2 = set(df2[COL_DATE])  # df2의 모든 날짜를 집합으로
    # & 연산자: 교집합 (두 집합 모두에 있는 요소)
    overlap_dates = dates1 & dates2

    if not overlap_dates:
        raise ValueError("두 DataFrame 간 겹치는 기간이 없습니다")

    # 2. 날짜순 정렬
    # sorted() 함수: 리스트/집합을 정렬하여 리스트로 반환
    overlap_dates = sorted(overlap_dates)

    # 3. 겹치는 기간 데이터 추출
    # 학습 포인트: 메서드 체이닝 - 한 줄에 여러 작업 수행
    # 1) .isin(): 날짜가 overlap_dates에 포함되는지 확인 (불린 인덱싱)
    # 2) .sort_values(): 날짜 컬럼 기준 정렬
    # 3) .reset_index(drop=True): 인덱스를 0부터 다시 매김 (원래 인덱스 버림)
    df1_overlap = df1[df1[COL_DATE].isin(overlap_dates)].sort_values(COL_DATE).reset_index(drop=True)
    df2_overlap = df2[df2[COL_DATE].isin(overlap_dates)].sort_values(COL_DATE).reset_index(drop=True)

    # 학습 포인트: 튜플 반환
    # return a, b는 (a, b) 튜플을 반환
    # 호출 시: df1_result, df2_result = extract_overlap_period(df1, df2)
    return df1_overlap, df2_overlap


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
    output_path: Path,
) -> None:
    """
    일별 비교 CSV를 저장한다.

    calculate_validation_metrics()의 헬퍼 함수.
    누적배수 로그차이는 이미 계산된 값을 받아서 사용한다.

    Args:
        sim_overlap: 겹치는 기간의 시뮬레이션 DataFrame
        actual_overlap: 겹치는 기간의 실제 DataFrame
        cumul_multiple_log_diff_series: 누적배수 로그차이 시계열 (이미 계산됨)
        output_path: CSV 저장 경로
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

    # 4. 누적배수 로그차이
    comparison_data[COL_CUMUL_MULTIPLE_LOG_DIFF] = cumul_multiple_log_diff_series

    # 5. DataFrame 생성 및 반올림
    # 딕셔너리를 DataFrame으로 변환
    comparison_df = pd.DataFrame(comparison_data)

    # 학습 포인트: 리스트 컴프리헨션 (List Comprehension)
    # [표현식 for 변수 in 리스트 if 조건]
    # 날짜 컬럼을 제외한 모든 숫자 컬럼 선택
    # 예: comparison_df.columns = ["날짜", "실제종가", "시뮬종가"]
    #     → num_cols = ["실제종가", "시뮬종가"]
    num_cols = [c for c in comparison_df.columns if c != DISPLAY_DATE]

    # .round(4): 소수점 4자리로 반올림
    # comparison_df[num_cols]: 여러 컬럼 동시 선택
    comparison_df[num_cols] = comparison_df[num_cols].round(4)

    # 6. CSV 저장
    # to_csv() 메서드: DataFrame을 CSV 파일로 저장
    # index=False: 행 인덱스 제외
    # encoding="utf-8-sig": 한글 엑셀 호환 (BOM 포함 UTF-8)
    comparison_df.to_csv(output_path, index=False, encoding="utf-8-sig")


def calculate_validation_metrics(
    simulated_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    output_path: Path | None = None,
) -> dict:
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

    # 4. 누적배수 로그차이 계산
    cumul_multiple_log_diff_series = _calculate_cumul_multiple_log_diff(
        actual_overlap[COL_CLOSE],
        sim_overlap[COL_CLOSE],
    )

    # 5. 검증 지표 계산
    cumul_multiple_log_diff_mean = float(cumul_multiple_log_diff_series.mean())
    cumul_multiple_log_diff_rmse = float(np.sqrt((cumul_multiple_log_diff_series**2).mean()))
    cumul_multiple_log_diff_max = float(cumul_multiple_log_diff_series.max())

    # 6. 일별 비교 CSV 생성 (요청 시에만)
    if output_path is not None:
        _save_daily_comparison_csv(sim_overlap, actual_overlap, cumul_multiple_log_diff_series, output_path)

    # 7. 누적수익률 상대차이 계산 (마지막 날 기준, 실제 기준 퍼센트)
    cumulative_return_rel_diff_pct = ((sim_cumulative - actual_cumulative) / actual_cumulative) * 100

    # 8. 마지막 날 종가 추출
    final_close_actual = float(actual_overlap.iloc[-1][COL_CLOSE])
    final_close_simulated = float(sim_overlap.iloc[-1][COL_CLOSE])

    # 9. 종가 상대차이 계산 (실제 기준 퍼센트)
    final_close_rel_diff_pct = ((final_close_simulated - final_close_actual) / final_close_actual) * 100

    # 10. 검증 결과 반환
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


def find_optimal_cost_model(
    underlying_df: pd.DataFrame,
    actual_leveraged_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    leverage: float = DEFAULT_LEVERAGE_MULTIPLIER,
    spread_range: tuple[float, float] = DEFAULT_SPREAD_RANGE,
    spread_step: float = DEFAULT_SPREAD_STEP,
    max_workers: int | None = None,
) -> list[dict]:
    """
    multiplier를 고정하고 비용 모델 파라미터를 grid search로 캘리브레이션한다.

    funding_spread를 탐색하여 실제 레버리지 ETF와 가장 유사한 시뮬레이션을
    생성하는 최적 비용 모델을 찾는다. expense_ratio는 CSV 데이터를 사용한다.

    ProcessPoolExecutor를 사용하여 병렬로 실행된다.
    FFR 및 Expense 커버리지 검증 및 딕셔너리 변환은 병렬 실행 전 한 번만 수행된다.

    Args:
        underlying_df: 기초 자산 DataFrame (QQQ)
        actual_leveraged_df: 실제 레버리지 ETF DataFrame (TQQQ)
        ffr_df: 연방기금금리 DataFrame (DATE: str (yyyy-mm), FFR: float)
        expense_df: 운용비용 DataFrame (DATE: str (yyyy-mm), VALUE: float (0~1 비율))
        leverage: 레버리지 배수 (기본값: 3.0)
        spread_range: funding spread 탐색 범위 (min, max) (%)
        spread_step: funding spread 탐색 간격 (%)
        max_workers: 최대 워커 수 (None이면 CPU 코어 수 - 1)

    Returns:
        top_strategies: 누적배수 로그차이 평균 기준 상위 전략 리스트

    Raises:
        ValueError: 겹치는 기간이 없을 때
        ValueError: FFR 또는 Expense 데이터 커버리지가 부족할 때
    """
    # 1. 겹치는 기간 추출
    underlying_overlap, actual_overlap = extract_overlap_period(underlying_df, actual_leveraged_df)

    # 2. FFR 커버리지 검증 (fail-fast)
    overlap_start = underlying_overlap[COL_DATE].min()
    overlap_end = underlying_overlap[COL_DATE].max()
    validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

    # 3. 검증 완료 후 FFR 및 Expense 딕셔너리 생성 (한 번만)
    ffr_dict = _create_ffr_dict(ffr_df)
    expense_dict = _create_expense_dict(expense_df)

    # 4. 실제 레버리지 ETF 첫날 가격을 initial_price로 사용
    initial_price = float(actual_overlap.iloc[0][COL_CLOSE])

    # 5. Grid search를 위한 파라미터 조합 생성 (spread만 탐색)
    spread_values = np.arange(spread_range[0], spread_range[1] + EPSILON, spread_step)

    # 모든 파라미터 조합 리스트 생성 (DataFrame은 캐시에서 조회)
    param_combinations = []
    for spread in spread_values:
        param_combinations.append(
            {
                "leverage": leverage,
                KEY_SPREAD: float(spread),
                "initial_price": initial_price,
            }
        )

    # 6. 병렬 실행 (DataFrame들과 FFR/Expense 딕셔너리를 워커 캐시에 저장)
    candidates = execute_parallel(
        _evaluate_cost_model_candidate,
        param_combinations,
        max_workers=max_workers,
        initializer=init_worker_cache,
        initargs=(
            {
                "underlying_overlap": underlying_overlap,
                "actual_overlap": actual_overlap,
                "ffr_dict": ffr_dict,
                "expense_dict": expense_dict,
            },
        ),
    )

    # 7. 누적배수 로그차이 RMSE 기준 오름차순 정렬 (낮을수록 우수, 경로 전체 추적 정확도)
    candidates.sort(key=lambda x: x["cumul_multiple_log_diff_rmse_pct"])

    # 8. 상위 전략 반환
    top_strategies = candidates[:MAX_TOP_STRATEGIES]

    return top_strategies
