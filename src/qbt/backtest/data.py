"""데이터 로딩 및 검증 모듈"""

from pathlib import Path

import pandas as pd

from qbt.backtest.config import (
    PRICE_CHANGE_THRESHOLD,
    PRICE_COLUMNS,
    REQUIRED_COLUMNS,
)
from qbt.backtest.exceptions import DataValidationError
from qbt.utils import get_logger

logger = get_logger(__name__)


def load_data(path: Path) -> pd.DataFrame:
    """
    CSV 파일에서 주식 데이터를 로드하고 전처리한다.

    날짜 파싱, 정렬, 필수 컬럼 검증, 중복 제거를 수행한다.
    데이터 유효성 검증(validate_data)은 별도로 호출해야 한다.

    Args:
        path: CSV 파일 경로

    Returns:
        전처리된 DataFrame (날짜순 정렬됨)

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        DataValidationError: 필수 컬럼이 누락되었을 때
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
        raise DataValidationError(f"필수 컬럼이 누락되었습니다: {sorted(missing_columns)}")

    # 4. 날짜 컬럼 파싱
    df["Date"] = pd.to_datetime(df["Date"]).dt.date

    # 5. 날짜순 정렬
    df = df.sort_values("Date").reset_index(drop=True)

    # 6. 중복 날짜 제거 (첫 번째 값 유지)
    duplicate_count = df.duplicated(subset=["Date"]).sum()
    if duplicate_count > 0:
        logger.warning(f"중복 날짜 {duplicate_count}건 제거됨")
        df = df.drop_duplicates(subset=["Date"], keep="first").reset_index(drop=True)

    logger.debug(f"전처리 완료: {len(df):,}행, 기간 {df['Date'].min()} ~ {df['Date'].max()}")

    return df


def validate_data(df: pd.DataFrame) -> None:
    """
    데이터 유효성을 검증한다.

    다음 항목을 검사하며, 이상 발견 시 즉시 예외를 발생시킨다:
    - 가격 컬럼의 결측치, 0, 음수 값
    - 전일 대비 급등락 (임계값 이상)

    어떠한 형태의 보간도 수행하지 않는다.

    Args:
        df: 검증할 DataFrame (load_data로 전처리된 상태)

    Raises:
        DataValidationError: 데이터 이상이 감지되었을 때
    """
    logger.debug("데이터 유효성 검증 시작")

    # 1. 결측치 검사
    for col in PRICE_COLUMNS:
        null_mask = df[col].isna()
        if null_mask.any():
            null_indices = df.index[null_mask].tolist()
            null_dates = df.loc[null_mask, "Date"].tolist()
            raise DataValidationError(
                f"결측치 발견 - 컬럼: {col}, "
                f"인덱스: {null_indices[:5]}{'...' if len(null_indices) > 5 else ''}, "
                f"날짜: {null_dates[:5]}{'...' if len(null_dates) > 5 else ''}"
            )

    # 2. 0 값 검사
    for col in PRICE_COLUMNS:
        zero_mask = df[col] == 0
        if zero_mask.any():
            zero_indices = df.index[zero_mask].tolist()
            zero_dates = df.loc[zero_mask, "Date"].tolist()
            raise DataValidationError(
                f"0 값 발견 - 컬럼: {col}, "
                f"인덱스: {zero_indices[:5]}{'...' if len(zero_indices) > 5 else ''}, "
                f"날짜: {zero_dates[:5]}{'...' if len(zero_dates) > 5 else ''}"
            )

    # 3. 음수 값 검사
    for col in PRICE_COLUMNS:
        negative_mask = df[col] < 0
        if negative_mask.any():
            negative_indices = df.index[negative_mask].tolist()
            negative_dates = df.loc[negative_mask, "Date"].tolist()
            ellipsis = "..." if len(negative_indices) > 5 else ""
            raise DataValidationError(
                f"음수 값 발견 - 컬럼: {col}, "
                f"인덱스: {negative_indices[:5]}{ellipsis}, "
                f"날짜: {negative_dates[:5]}{ellipsis}"
            )

    # 4. 전일 대비 급등락 검사 (Close 기준)
    df_copy = df.copy()
    df_copy["pct_change"] = df_copy["Close"].pct_change()

    # 첫 번째 행은 NaN이므로 제외
    extreme_mask = df_copy["pct_change"].abs() >= PRICE_CHANGE_THRESHOLD
    extreme_mask = extreme_mask.fillna(False)

    if extreme_mask.any():
        extreme_rows = df_copy[extreme_mask]
        for _, row in extreme_rows.iterrows():
            pct = row["pct_change"] * 100
            logger.warning(f"급등락 감지 - 날짜: {row['Date']}, " f"변동률: {pct:+.2f}%, 종가: {row['Close']:.2f}")

        first_extreme = extreme_rows.iloc[0]
        raise DataValidationError(
            f"전일 대비 급등락 감지 (임계값: {PRICE_CHANGE_THRESHOLD * 100:.0f}%) - "
            f"날짜: {first_extreme['Date']}, "
            f"변동률: {first_extreme['pct_change'] * 100:+.2f}%"
        )

    logger.debug("데이터 유효성 검증 완료: 이상 없음")


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
        df[col_name] = df["Close"].rolling(window=window).mean()
    elif ma_type == "ema":
        df[col_name] = df["Close"].ewm(span=window, adjust=False).mean()
    else:
        raise ValueError(f"지원하지 않는 ma_type: {ma_type}")

    # 유효 데이터 수 확인
    valid_rows = df[col_name].notna().sum()
    logger.debug(f"이동평균 계산 완료: 유효 데이터 {valid_rows:,}행 (전체 {len(df):,}행)")

    return df
