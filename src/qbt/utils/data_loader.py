"""데이터 로딩 및 검증 유틸리티

프로젝트 전반에서 사용되는 공통 CSV 파일 로딩 함수를 제공한다.

참고:
- TQQQ 도메인 전용 데이터 로더: tqqq/data_loader.py 참고
"""

from pathlib import Path

import pandas as pd

from qbt.common_constants import COL_DATE, PRICE_COLUMNS, REQUIRED_COLUMNS
from qbt.utils.logger import get_logger

logger = get_logger(__name__)


def load_stock_data(path: Path) -> pd.DataFrame:
    """
    CSV 파일에서 주식 데이터를 로드하고 전처리한다.

    날짜 파싱, 정렬, 필수 컬럼 검증을 하고, 중복 날짜 · 가격의 결측 · 0 · 음수가 있으면 멈춘다(지우거나 메우지 않는다).

    Args:
        path: CSV 파일 경로

    Returns:
        전처리된 DataFrame (날짜순 정렬됨)

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        ValueError: 필수 컬럼이 누락되었거나, 중복 날짜 · 가격의 결측 · 0 · 음수가 있을 때
    """
    # 1. 파일 존재 여부 확인
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    logger.debug(f"데이터 로딩 시작: {path}")

    # 2. CSV 파일 로드
    df = pd.read_csv(path, parse_dates=[COL_DATE])

    logger.debug(f"원본 데이터 행 수: {len(df):,}")

    # 3. 필수 컬럼 검증
    missing_columns = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError(f"필수 컬럼이 누락되었습니다: {sorted(missing_columns)}")

    # 4. 날짜 컬럼 파싱
    df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date

    # 5. 날짜순 정렬
    df = df.sort_values(COL_DATE).reset_index(drop=True)

    # 6. 중복 날짜 · 가격 값 검증
    validate_price_series(df)

    logger.debug(f"전처리 완료: {len(df):,}행, 기간 {df[COL_DATE].min()} ~ {df[COL_DATE].max()}")

    return df


def validate_price_series(df: pd.DataFrame) -> None:
    """시세 표에 중복 날짜나 가격 열(`PRICE_COLUMNS`)의 결측 · 0 · 음수가 있으면 ValueError — 지우거나 메우지 않는다.

    시세를 읽을 때(`load_stock_data`)와 받거나 만든 시세를 저장하기 전(`validate_stock_data` · 생성 스크립트)에
    같은 검사를 쓴다. 거래량은 보지 않는다(대용 · 합성 시세는 거래량이 0 이다).

    Raises:
        ValueError: 중복 날짜(날짜 포함) · 결측 · 0 · 음수(열 · 인덱스 · 날짜 포함)가 있을 때
    """
    # 1. 중복 날짜 검사 — 어느 행이 맞는지 알 수 없으므로 고르지 않는다
    duplicate_dates = df.loc[df.duplicated(subset=[COL_DATE]), COL_DATE].unique().tolist()
    if duplicate_dates:
        ellipsis = "..." if len(duplicate_dates) > 5 else ""
        raise ValueError(f"중복 날짜 발견 - {len(duplicate_dates)}개, 날짜: {duplicate_dates[:5]}{ellipsis}")

    # 2. 결측치 검사
    for col in PRICE_COLUMNS:
        null_mask = df[col].isna()
        if null_mask.any():
            null_indices = df.index[null_mask].tolist()
            null_dates = df.loc[null_mask, COL_DATE].tolist()
            raise ValueError(
                f"결측치 발견 - 컬럼: {col}, 인덱스: {null_indices[:5]}{'...' if len(null_indices) > 5 else ''}, 날짜: {null_dates[:5]}{'...' if len(null_dates) > 5 else ''}"
            )

    # 3. 0 값 검사
    for col in PRICE_COLUMNS:
        zero_mask = df[col] == 0
        if zero_mask.any():
            zero_indices = df.index[zero_mask].tolist()
            zero_dates = df.loc[zero_mask, COL_DATE].tolist()
            raise ValueError(
                f"0 값 발견 - 컬럼: {col}, 인덱스: {zero_indices[:5]}{'...' if len(zero_indices) > 5 else ''}, 날짜: {zero_dates[:5]}{'...' if len(zero_dates) > 5 else ''}"
            )

    # 4. 음수 값 검사
    for col in PRICE_COLUMNS:
        negative_mask = df[col] < 0
        if negative_mask.any():
            negative_indices = df.index[negative_mask].tolist()
            negative_dates = df.loc[negative_mask, COL_DATE].tolist()
            ellipsis = "..." if len(negative_indices) > 5 else ""
            raise ValueError(
                f"음수 값 발견 - 컬럼: {col}, 인덱스: {negative_indices[:5]}{ellipsis}, 날짜: {negative_dates[:5]}{ellipsis}"
            )


def extract_overlap_period(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    두 DataFrame의 겹치는 기간을 추출한다.

    Args:
        df1: 첫 번째 DataFrame (Date 컬럼 필수)
        df2: 두 번째 DataFrame (Date 컬럼 필수)

    Returns:
        (df1_overlap, df2_overlap) 튜플
            - df1_overlap: 겹치는 기간의 df1 (날짜순 정렬, reset_index 완료)
            - df2_overlap: 겹치는 기간의 df2 (날짜순 정렬, reset_index 완료)

    Raises:
        ValueError: 겹치는 기간이 없을 때
    """
    # 1. 겹치는 날짜 추출 (set 교집합)
    dates1 = set(df1[COL_DATE])
    dates2 = set(df2[COL_DATE])
    overlap_dates_set = dates1 & dates2

    if not overlap_dates_set:
        raise ValueError("두 DataFrame 간 겹치는 기간이 없습니다")

    # 2. 날짜순 정렬
    overlap_dates = sorted(overlap_dates_set)

    # 3. 겹치는 기간 데이터 추출
    df1_overlap = df1[df1[COL_DATE].isin(overlap_dates)].sort_values(COL_DATE).reset_index(drop=True)
    df2_overlap = df2[df2[COL_DATE].isin(overlap_dates)].sort_values(COL_DATE).reset_index(drop=True)

    return df1_overlap, df2_overlap


def load_signal_trade_pair(
    signal_path: Path,
    trade_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """시그널 + 매매 데이터를 로드하고, 경로가 다르면 겹치는 기간을 추출한다.

    signal_path == trade_path인 경우 한 번만 로드하고 독립 복사본을 반환한다.
    경로가 다르면 각각 로드한 뒤 extract_overlap_period로 겹치는 기간만 추출한다.

    Args:
        signal_path: 시그널 데이터 CSV 경로
        trade_path: 매매 데이터 CSV 경로

    Returns:
        (signal_df, trade_df) 튜플. 두 DataFrame은 독립 복사본.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        ValueError: 필수 컬럼 누락 또는 겹치는 기간 없을 때
    """
    if signal_path == trade_path:
        trade_df = load_stock_data(trade_path)
        signal_df = trade_df.copy()
    else:
        signal_df = load_stock_data(signal_path)
        trade_df = load_stock_data(trade_path)
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    return signal_df, trade_df
