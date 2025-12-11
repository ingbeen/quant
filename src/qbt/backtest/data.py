"""백테스트 기술지표 모듈"""

import pandas as pd

from qbt.common_constants import COL_CLOSE
from qbt.utils import get_logger

logger = get_logger(__name__)


def add_single_moving_average(
    df: pd.DataFrame,
    window: int,
    ma_type: str = "sma",
) -> pd.DataFrame:
    """
    지정된 기간의 이동평균을 계산하여 컬럼으로 추가한다.

    Args:
        df: 주식 데이터 DataFrame (Close 컬럼 필수)
        window: 이동평균 기간
        ma_type: 이동평균 유형 ("sma" 또는 "ema", 기본값: "sma")

    Returns:
        이동평균 컬럼이 추가된 DataFrame (원본 복사본)

    Raises:
        ValueError: window < 1인 경우
    """
    if window < 1:
        raise ValueError(f"window는 1 이상이어야 합니다: {window}")

    logger.debug(f"이동평균 계산: window={window}, type={ma_type}")

    # DataFrame 복사 (원본 보존)
    df = df.copy()

    # 컬럼명 설정
    col_name = f"ma_{window}"

    # 이동평균 계산
    if ma_type == "sma":
        df[col_name] = df[COL_CLOSE].rolling(window=window).mean()
    elif ma_type == "ema":
        df[col_name] = df[COL_CLOSE].ewm(span=window, adjust=False).mean()
    else:
        raise ValueError(f"지원하지 않는 ma_type: {ma_type}")

    # 유효 데이터 수 확인
    valid_rows = df[col_name].notna().sum()
    logger.debug(f"이동평균 계산 완료: 유효 데이터 {valid_rows:,}행 (전체 {len(df):,}행)")

    return df
