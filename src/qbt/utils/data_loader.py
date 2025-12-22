"""데이터 로딩 및 검증 유틸리티

모든 CSV 파일 로딩과 데이터 검증을 담당하는 공통 함수를 제공한다.
"""

from pathlib import Path

import pandas as pd

from qbt.common_constants import COL_DATE, DISPLAY_DATE, REQUIRED_COLUMNS
from qbt.tqqq.constants import (
    COL_FFR,
    COL_FFR_DATE,
    COL_FFR_VALUE_RAW,
    COMPARISON_COLUMNS,
)
from qbt.utils import get_logger

logger = get_logger(__name__)


def load_stock_data(path: Path) -> pd.DataFrame:
    """
    CSV 파일에서 주식 데이터를 로드하고 전처리한다.

    날짜 파싱, 정렬, 필수 컬럼 검증, 중복 제거를 수행한다.

    Args:
        path: CSV 파일 경로

    Returns:
        전처리된 DataFrame (날짜순 정렬됨)

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        ValueError: 필수 컬럼이 누락되었을 때
    """
    # 1. 파일 존재 여부 확인
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    logger.debug(f"데이터 로딩 시작: {path}")

    # 2. CSV 파일 로드
    df = pd.read_csv(path)
    logger.debug(f"원본 데이터 행 수: {len(df):,}")

    # 3. 필수 컬럼 검증
    missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError(f"필수 컬럼이 누락되었습니다: {sorted(missing_columns)}")

    # 4. 날짜 컬럼 파싱
    df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date

    # 5. 날짜순 정렬
    df = df.sort_values(COL_DATE).reset_index(drop=True)

    # 6. 중복 날짜 제거 (첫 번째 값 유지)
    duplicate_count = df.duplicated(subset=[COL_DATE]).sum()
    if duplicate_count > 0:
        logger.warning(f"중복 날짜 {duplicate_count}건 제거됨")
        df = df.drop_duplicates(subset=[COL_DATE], keep="first").reset_index(drop=True)

    logger.debug(f"전처리 완료: {len(df):,}행, 기간 {df[COL_DATE].min()} ~ {df[COL_DATE].max()}")

    return df


def load_ffr_data(path: Path) -> pd.DataFrame:
    """
    연방기금금리 월별 데이터를 로드한다.

    Args:
        path: CSV 파일 경로

    Returns:
        FFR DataFrame (DATE: str (yyyy-mm), FFR: float)

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
    """
    if not path.exists():
        raise FileNotFoundError(f"FFR 파일을 찾을 수 없습니다: {path}")

    logger.debug(f"FFR 데이터 로딩: {path}")
    df = pd.read_csv(path)
    df.rename(columns={COL_FFR_VALUE_RAW: COL_FFR}, inplace=True)

    logger.debug(f"FFR 로드 완료: {len(df)}개월, 범위 {df[COL_FFR_DATE].min()} ~ {df[COL_FFR_DATE].max()}")

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

    df = pd.read_csv(path)

    # 필수 컬럼 검증
    missing_columns = [col for col in COMPARISON_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_columns}")

    # 날짜 컬럼을 datetime으로 변환
    df[DISPLAY_DATE] = pd.to_datetime(df[DISPLAY_DATE])

    return df
