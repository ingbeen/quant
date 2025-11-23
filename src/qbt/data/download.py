"""주식 데이터 다운로드 모듈"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from qbt.utils import get_logger

logger = get_logger(__name__)


def download_stock_data(
    ticker: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Path:
    """
    주식 데이터를 다운로드하고 CSV로 저장 (Date, Open, High, Low, Close, Volume 포함)

    Args:
        ticker: 주식 티커 (예: QQQ, SPY)
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)

    Returns:
        저장된 CSV 파일의 경로
    """
    try:

        # 1. 출력 디렉토리 생성
        output_path = Path("data/raw")
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

        # 8. CSV 파일로 저장
        csv_path = output_path / filename
        df.to_csv(csv_path, index=False)

        # 9. 결과 출력
        logger.debug(f"데이터 저장 완료: {csv_path}")
        logger.debug(f"기간: {df['Date'].min()} ~ {df['Date'].max()}")
        logger.debug(f"행 수: {len(df):,}")
        if filtered_count > 0:
            logger.debug(f"최근 데이터 제외: {filtered_count}행 (오늘 포함 최근 2일)")
            logger.debug(
                f"포함된 마지막 날짜: {cutoff_date} ({cutoff_date} 이후 데이터 제외)"
            )

        return csv_path

    except Exception:
        raise
