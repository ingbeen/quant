"""TQQQ 도메인 전용 데이터 로딩 및 월별 조회 유틸리티

TQQQ 시뮬레이션 및 검증에 필요한 데이터 로딩, 월별 데이터 조회 함수를 제공한다.

주요 기능:
1. 연방기금금리(FFR) 월별 데이터 로딩
2. TQQQ 일별 비교 데이터 로딩
3. 월별 데이터 딕셔너리 생성 및 조회 (FFR, Expense Ratio)
4. 운용비율 딕셔너리 확장 (합성 데이터 생성용)

이 모듈의 함수들은 TQQQ 도메인에서만 사용되며,
프로젝트 전반의 공통 데이터 로딩은 utils/data_loader.py를 참고한다.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_ACTUAL_CUMUL_RETURN,
    COL_ACTUAL_DAILY_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_EXPENSE_DATE,
    COL_EXPENSE_VALUE,
    COL_FFR_DATE,
    COL_FFR_VALUE,
    COL_SIMUL_CLOSE,
    COL_SIMUL_CUMUL_RETURN,
    COL_SIMUL_DAILY_RETURN,
    DEFAULT_PRE_LISTING_EXPENSE_RATIO,
    MAX_EXPENSE_MONTHS_DIFF,
    MAX_FFR_MONTHS_DIFF,
)
from qbt.utils import get_logger

# 모듈 레벨 로거 생성
logger = get_logger(__name__)

# 일별 비교 데이터 필수 컬럼 목록
COMPARISON_COLUMNS = [
    DISPLAY_DATE,
    COL_ACTUAL_CLOSE,
    COL_SIMUL_CLOSE,
    COL_ACTUAL_DAILY_RETURN,
    COL_SIMUL_DAILY_RETURN,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_ACTUAL_CUMUL_RETURN,
    COL_SIMUL_CUMUL_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
]


def load_ffr_data(path: Path) -> pd.DataFrame:
    """
    연방기금금리 월별 데이터를 로드한다.

    Args:
        path: CSV 파일 경로

    Returns:
        FFR DataFrame (DATE: str (yyyy-mm), VALUE: float)

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
    """
    if not path.exists():
        raise FileNotFoundError(f"FFR 파일을 찾을 수 없습니다: {path}")

    logger.debug(f"FFR 데이터 로딩: {path}")
    df = pd.read_csv(path)

    logger.debug(f"FFR 로드 완료: {len(df)}개월, 범위 {df[COL_FFR_DATE].min()} ~ {df[COL_FFR_DATE].max()}")

    return df


def load_expense_ratio_data(path: Path) -> pd.DataFrame:
    """
    운용비율(Expense Ratio) 월별 데이터를 로드한다.

    Args:
        path: CSV 파일 경로

    Returns:
        Expense Ratio DataFrame (DATE: str (yyyy-mm), VALUE: float)

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
    """
    if not path.exists():
        raise FileNotFoundError(f"Expense Ratio 파일을 찾을 수 없습니다: {path}")

    logger.debug(f"Expense Ratio 데이터 로딩: {path}")
    df = pd.read_csv(path)

    logger.debug(f"Expense Ratio 로드 완료: {len(df)}개월, 범위 {df[COL_EXPENSE_DATE].min()} ~ {df[COL_EXPENSE_DATE].max()}")

    return df


def load_comparison_data(path: Path) -> pd.DataFrame:
    """
    일별 비교 CSV 파일을 로드하고 검증한다.

    Args:
        path: CSV 파일 경로

    Returns:
        로드된 DataFrame

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        ValueError: 필수 컬럼이 누락되었을 때
    """
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    # parse_dates로 읽기 시점에 날짜 컬럼 자동 파싱 (성능 향상)
    df = pd.read_csv(path, parse_dates=[DISPLAY_DATE])

    # 필수 컬럼 검증
    missing_columns = sorted(set(COMPARISON_COLUMNS) - set(df.columns))
    if missing_columns:
        raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_columns}")

    return df


# ============================================================
# 월별 데이터 딕셔너리 생성 및 조회 함수
# ============================================================


def create_monthly_data_dict(df: pd.DataFrame, date_col: str, value_col: str, data_type: str) -> dict[str, float]:
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


def lookup_monthly_data(date_value: date, data_dict: dict[str, float], max_months_diff: int, data_type: str) -> float:
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


def create_ffr_dict(ffr_df: pd.DataFrame) -> dict[str, float]:
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
    return create_monthly_data_dict(ffr_df, COL_FFR_DATE, COL_FFR_VALUE, "FFR")


def lookup_ffr(date_value: date, ffr_dict: dict[str, float]) -> float:
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
    return lookup_monthly_data(date_value, ffr_dict, MAX_FFR_MONTHS_DIFF, "FFR")


def create_expense_dict(expense_df: pd.DataFrame) -> dict[str, float]:
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
    return create_monthly_data_dict(expense_df, COL_EXPENSE_DATE, COL_EXPENSE_VALUE, "Expense")


def lookup_expense(date_value: date, expense_dict: dict[str, float]) -> float:
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
    return lookup_monthly_data(date_value, expense_dict, MAX_EXPENSE_MONTHS_DIFF, "Expense")


def build_extended_expense_dict(expense_df: pd.DataFrame) -> dict[str, float]:
    """
    운용비율 딕셔너리를 생성하고, 1999-01부터 실제 데이터 시작 전까지 고정값으로 확장한다.

    TQQQ 실제 운용비율 데이터는 2010-02부터 존재하므로,
    1999-01 ~ 2010-01 구간에 DEFAULT_PRE_LISTING_EXPENSE_RATIO를 적용한다.

    Args:
        expense_df: Expense Ratio DataFrame (DATE: str (yyyy-mm), VALUE: float)

    Returns:
        1999-01부터 커버하는 확장된 expense 딕셔너리
    """
    # 1. 기존 expense_df를 딕셔너리로 변환
    expense_dict = create_expense_dict(expense_df)

    # 2. 최초 월 확인
    earliest_month = min(expense_dict.keys())
    earliest_year, earliest_month_num = map(int, earliest_month.split("-"))

    # 3. 1999-01 ~ 최초 월 직전까지 고정값 채우기
    fill_year = 1999
    fill_month = 1

    while True:
        fill_key = f"{fill_year:04d}-{fill_month:02d}"

        # 최초 월에 도달하면 종료
        if fill_year > earliest_year or (fill_year == earliest_year and fill_month >= earliest_month_num):
            break

        expense_dict[fill_key] = DEFAULT_PRE_LISTING_EXPENSE_RATIO

        # 다음 월로 이동
        fill_month += 1
        if fill_month > 12:
            fill_month = 1
            fill_year += 1

    return expense_dict
