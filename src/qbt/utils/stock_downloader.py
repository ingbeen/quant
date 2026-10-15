"""주식 데이터 다운로드 · 검증 · 저장 유틸리티

Yahoo Finance에서 주식 데이터를 다운로드하고, 데이터 유효성을 검증하는 함수를 제공한다.

주요 기능:
1. 주식 데이터 유효성 검증 (중복 날짜, 결측치, 0값, 음수, 급등락)
2. 시세 CSV 저장 (가격 반올림 → 검증 → 저장 — 수집 시세와 합성 · 대용 시세가 같은 함수로 저장한다)
3. Yahoo Finance에서 주식 데이터 다운로드 및 CSV 저장
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from qbt.common_constants import COL_CLOSE, COL_DATE, PRICE_COLUMNS, REQUIRED_COLUMNS, STOCK_DIR
from qbt.utils.data_loader import validate_price_series
from qbt.utils.logger import get_logger

logger = get_logger(__name__)

# 데이터 검증 관련 상수
DEFAULT_PRICE_CHANGE_THRESHOLD = 0.50

# 수집 · 합성 시세 파일의 가격 자릿수 — 결과 파일(ROUND_PRICE)과 다른 이유는 루트 CLAUDE.md 「가격 반올림 자릿수」
ROUND_INPUT_PRICE = 6


def validate_stock_data(df: pd.DataFrame) -> None:
    """
    데이터 유효성을 검증한다.

    다음 항목을 검사하며, 이상 발견 시 즉시 예외를 발생시킨다:
    - 중복 날짜, 가격 컬럼의 결측치, 0, 음수 값
    - 전일 대비 급등락 (임계값 이상)

    어떠한 형태의 보간도 수행하지 않는다.

    Args:
        df: 검증할 DataFrame

    Raises:
        ValueError: 데이터 이상이 감지되었을 때
    """
    # 1. 중복 날짜 · 가격의 결측치 · 0 · 음수 검사
    validate_price_series(df)

    # 2. 전일 대비 급등락 검사 (Close 기준)
    df_copy = df.copy()
    df_copy["pct_change"] = df_copy[COL_CLOSE].pct_change()

    # 첫 번째 행은 NaN이므로 제외
    extreme_mask = df_copy["pct_change"].abs() >= DEFAULT_PRICE_CHANGE_THRESHOLD
    extreme_mask = extreme_mask.fillna(False)

    if extreme_mask.any():
        extreme_rows = df_copy[extreme_mask]
        for _, row in extreme_rows.iterrows():
            pct = row["pct_change"] * 100
            logger.warning(f"급등락 감지 - 날짜: {row[COL_DATE]}, 변동률: {pct:+.2f}%, 종가: {row[COL_CLOSE]:.2f}")

        first_extreme = extreme_rows.iloc[0]
        raise ValueError(
            f"전일 대비 급등락 감지 (임계값: {DEFAULT_PRICE_CHANGE_THRESHOLD * 100:.0f}%) - 날짜: {first_extreme[COL_DATE]}, 변동률: {first_extreme['pct_change'] * 100:+.2f}%"
        )

    logger.debug("데이터 유효성 검증 완료: 이상 없음")


def save_stock_csv(df: pd.DataFrame, path: Path, *, check_price_spikes: bool = True) -> None:
    """
    시세 표를 가격 반올림 → 검증 → 저장 순서로 저장한다. 검증에 걸리면 파일을 쓰지 않는다.

    Args:
        df: 저장할 시세 DataFrame (원본은 바꾸지 않는다)
        path: 저장 경로 (상위 폴더가 없으면 만든다)
        check_price_spikes: 전일 대비 급등락까지 검사한다. 급등락 기준을 넘는 날이 정상인 시세(레버리지 합성)만 False

    Raises:
        ValueError: 중복 날짜 · 가격의 결측 · 0 · 음수, check_price_spikes 이면 급등락
    """
    rounded = df.copy()
    rounded[PRICE_COLUMNS] = rounded[PRICE_COLUMNS].round(ROUND_INPUT_PRICE)
    if check_price_spikes:
        validate_stock_data(rounded)
    else:
        validate_price_series(rounded)
    path.parent.mkdir(parents=True, exist_ok=True)
    rounded.to_csv(path, index=False)
    logger.debug(f"저장: {path} ({len(rounded):,}행, {rounded[COL_DATE].min()} ~ {rounded[COL_DATE].max()})")


def download_stock_data(ticker: str) -> Path:
    """
    주식 데이터를 전체 기간으로 다운로드하고 `{ticker}_max.csv` 로 저장한다.

    Args:
        ticker: 주식 티커 (예: QQQ, SPY)

    Returns:
        저장된 CSV 파일의 경로
    """
    # 1. yfinance Ticker 객체 생성
    yf_ticker = yf.Ticker(ticker)

    # 2. 전체 기간 데이터 다운로드
    df = yf_ticker.history(period="max")

    # 3. 데이터 유효성 검증
    if df.empty:
        raise ValueError(f"데이터를 찾을 수 없습니다: {ticker}")

    # 4. 인덱스를 Date 컬럼으로 변환
    df.reset_index(inplace=True)
    df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date

    # 5. 필요한 컬럼만 선택 (Date, Open, High, Low, Close, Volume)
    df = df[REQUIRED_COLUMNS]

    # 6. 최근 데이터 필터링 (오늘 포함 최근 2일 제외)
    cutoff_date = date.today() - timedelta(days=2)
    original_count = len(df)
    df = df[df[COL_DATE] <= cutoff_date]
    filtered_count = original_count - len(df)

    # 7. 가격 반올림 → 검증 → 저장 (검증 통과 시에만 저장)
    csv_path = STOCK_DIR / f"{ticker}_max.csv"
    save_stock_csv(df, csv_path)

    # 8. 결과 출력
    if filtered_count > 0:
        logger.debug(f"최근 데이터 제외: {filtered_count}행 (오늘 포함 최근 2일)")

    return csv_path
