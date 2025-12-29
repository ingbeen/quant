"""TQQQ 도메인 전용 데이터 로딩 유틸리티

TQQQ 시뮬레이션 및 검증에 필요한 데이터 로딩 함수를 제공한다.

주요 기능:
1. 연방기금금리(FFR) 월별 데이터 로딩
2. TQQQ 일별 비교 데이터 로딩

이 모듈의 함수들은 TQQQ 도메인에서만 사용되며,
프로젝트 전반의 공통 데이터 로딩은 utils/data_loader.py를 참고한다.
"""

from pathlib import Path

import pandas as pd

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_EXPENSE_DATE,
    COL_FFR_DATE,
    COMPARISON_COLUMNS,
)
from qbt.utils import get_logger

# 모듈 레벨 로거 생성
logger = get_logger(__name__)


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

    df = pd.read_csv(path)

    # 필수 컬럼 검증
    missing_columns = [col for col in COMPARISON_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_columns}")

    # 날짜 컬럼을 datetime으로 변환
    df[DISPLAY_DATE] = pd.to_datetime(df[DISPLAY_DATE])

    return df
