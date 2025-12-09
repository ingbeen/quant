"""
주식 데이터 다운로드 스크립트

Yahoo Finance에서 주식 데이터를 다운로드하여 CSV로 저장한다.
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from qbt.config import DATA_DIR
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler

logger = get_logger(__name__)


def download_stock_data(
    ticker: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Path:
    """
    주식 데이터를 다운로드하고 CSV로 저장한다.

    Args:
        ticker: 주식 티커 (예: QQQ, SPY)
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)

    Returns:
        저장된 CSV 파일의 경로
    """
    # 1. 출력 디렉토리 생성
    output_path = DATA_DIR
    output_path.mkdir(parents=True, exist_ok=True)

    # 2. yfinance Ticker 객체 생성
    yf_ticker = yf.Ticker(ticker)

    # 3. 날짜 조건별 데이터 다운로드 및 파일명 생성
    if start_date and end_date:
        df = yf_ticker.history(start=start_date, end=end_date)
        filename = f"{ticker}_{start_date}_{end_date}.csv"
    elif start_date:
        df = yf_ticker.history(start=start_date)
        filename = f"{ticker}_{start_date}_latest.csv"
    else:
        df = yf_ticker.history(period="max")
        filename = f"{ticker}_max.csv"

    # 4. 데이터 유효성 검증
    if df.empty:
        raise ValueError(f"데이터를 찾을 수 없습니다: {ticker}")

    # 5. 인덱스를 Date 컬럼으로 변환
    df.reset_index(inplace=True)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date

    # 6. 필요한 컬럼만 선택 (Date, Open, High, Low, Close, Volume)
    required_columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    df = df[required_columns]

    # 7. 최근 데이터 필터링 (오늘 포함 최근 2일 제외)
    cutoff_date = date.today() - timedelta(days=2)
    original_count = len(df)
    df = df[df["Date"] <= cutoff_date]
    filtered_count = original_count - len(df)

    # 8. 가격 컬럼을 소수점 6자리로 라운딩
    price_columns = ["Open", "High", "Low", "Close"]
    df[price_columns] = df[price_columns].round(6)

    # 9. CSV 파일로 저장
    csv_path = output_path / filename
    df.to_csv(csv_path, index=False)

    # 10. 결과 출력
    logger.debug(f"데이터 저장 완료: {csv_path}")
    logger.debug(f"기간: {df['Date'].min()} ~ {df['Date'].max()}")
    logger.debug(f"행 수: {len(df):,}")
    if filtered_count > 0:
        logger.debug(f"최근 데이터 제외: {filtered_count}행 (오늘 포함 최근 2일)")

    return csv_path


def parse_args():
    """CLI 인자를 파싱한다."""
    parser = argparse.ArgumentParser(
        description="Yahoo Finance에서 주식 데이터 다운로드",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            사용 예시:
            # 전체 기간 다운로드
            poetry run python scripts/data/download_data.py QQQ

            # 기간 지정 다운로드
            poetry run python scripts/data/download_data.py SPY --start 2020-01-01 --end 2023-12-31
        """,
    )
    parser.add_argument("ticker", help="주식 티커 심볼 (예: QQQ, SPY)")
    parser.add_argument("--start", help="시작 날짜 (YYYY-MM-DD)")
    parser.add_argument("--end", help="종료 날짜 (YYYY-MM-DD)")

    return parser.parse_args()


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    args = parse_args()
    ticker = args.ticker.upper()

    logger.debug(f"데이터 다운로드 시작: {ticker}")

    csv_path = download_stock_data(
        ticker=ticker,
        start_date=args.start,
        end_date=args.end,
    )
    logger.debug(f"다운로드 완료: {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
