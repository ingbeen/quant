"""데이터 로딩 및 검증 유틸리티

스크립트에서 공통으로 사용하는 데이터 로딩 및 검증 함수를 제공한다.
"""

from logging import Logger
from pathlib import Path

import pandas as pd


def load_and_validate_data(data_path: Path, logger: Logger) -> pd.DataFrame:
    """
    데이터를 로드하고 검증한다.

    Args:
        data_path: 데이터 파일 경로
        logger: 로거 인스턴스

    Returns:
        검증된 DataFrame

    Raises:
        FileNotFoundError: 파일을 찾을 수 없는 경우
        DataValidationError: 데이터 검증 실패 시
    """
    # 순환 임포트 방지를 위해 함수 내부에서 import
    from qbt.backtest.data import load_data, validate_data
    from qbt.backtest.exceptions import DataValidationError

    # 데이터 로딩 및 검증 (예외는 CLI 계층에서 처리)
    logger.debug(f"데이터 파일 경로: {data_path}")
    df = load_data(data_path)
    validate_data(df)

    logger.debug("=" * 60)
    logger.debug("데이터 로딩 및 검증 완료")
    logger.debug(f"총 행 수: {len(df):,}")
    logger.debug(f"기간: {df['Date'].min()} ~ {df['Date'].max()}")
    logger.debug("=" * 60)

    return df
