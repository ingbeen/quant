#!/usr/bin/env python3
"""
주식 데이터 다운로드 스크립트
Date, Open, Close, Volume 컬럼만 포함하여 다운로드

Usage:
    python scripts/download_data.py QQQ
    python scripts/download_data.py QQQ --start=2020-01-01
    python scripts/download_data.py QQQ --start=2020-01-01 --end=2023-12-31
"""

import argparse
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd
import yfinance as yf


def download_stock_data(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Path:
    """
    주식 데이터를 다운로드하고 CSV로 저장 (Date, Open, Close, Volume만 포함)

    Args:
        symbol: 주식 티커 (예: QQQ, SPY)
        start_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식)

    Returns:
        저장된 CSV 파일의 경로
    """
    # 출력 디렉토리 생성
    output_path = Path("data/raw")
    output_path.mkdir(parents=True, exist_ok=True)

    # yfinance Ticker 객체 생성
    ticker = yf.Ticker(symbol)

    print(f"[INFO] {symbol} 데이터 다운로드 중...")

    try:
        # 데이터 다운로드 (최대 기간)
        if start_date and end_date:
            df = ticker.history(start=start_date, end=end_date)
            filename = f"{symbol}_{start_date}_{end_date}.csv"
        elif start_date:
            df = ticker.history(start=start_date)
            filename = f"{symbol}_{start_date}_latest.csv"
        else:
            df = ticker.history(period="max")
            filename = f"{symbol}_max.csv"

        if df.empty:
            raise ValueError(f"데이터를 찾을 수 없습니다: {symbol}")

        # 인덱스를 Date 컬럼으로 변환
        df.reset_index(inplace=True)
        df["Date"] = pd.to_datetime(df["Date"]).dt.date

        # 필요한 컬럼만 선택 (Date, Open, Close, Volume)
        required_columns = ["Date", "Open", "Close", "Volume"]
        df = df[required_columns]

        # 최근 2일(오늘 포함) 데이터 제외
        cutoff_date = date.today() - timedelta(days=1)  # 어제까지의 데이터만 포함
        original_count = len(df)
        df = df[df["Date"] <= cutoff_date]
        filtered_count = original_count - len(df)

        # CSV 파일로 저장
        csv_path = output_path / filename
        df.to_csv(csv_path, index=False)

        print(f"[SUCCESS] 데이터 저장 완료: {csv_path}")
        print(f"[DATA] 데이터 정보:")
        print(f"   기간: {df['Date'].min()} ~ {df['Date'].max()}")
        print(f"   행 수: {len(df):,}")
        print(f"   컬럼: {list(df.columns)}")
        if filtered_count > 0:
            print(f"[FILTER] 최근 데이터 제외: {filtered_count}행 (오늘 포함 최근 2일)")
            print(f"[FILTER] 제외 기준일: {cutoff_date} 이후 데이터")

        return csv_path

    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        raise


def get_stock_info(symbol: str) -> dict:
    """주식 기본 정보 조회"""
    ticker = yf.Ticker(symbol)
    info = ticker.info

    relevant_info = {
        "symbol": info.get("symbol"),
        "longName": info.get("longName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "marketCap": info.get("marketCap"),
        "currency": info.get("currency"),
        "exchange": info.get("exchange"),
    }

    return {k: v for k, v in relevant_info.items() if v is not None}


def main():
    parser = argparse.ArgumentParser(description="주식 데이터 다운로드")
    parser.add_argument("symbol", help="주식 티커 심볼 (예: QQQ, SPY)")
    parser.add_argument("--start", help="시작 날짜 (YYYY-MM-DD)")
    parser.add_argument("--end", help="종료 날짜 (YYYY-MM-DD)")
    parser.add_argument("--info", action="store_true", help="주식 정보만 조회")

    args = parser.parse_args()

    symbol = args.symbol.upper()

    if args.info:
        print(f"[INFO] {symbol} 정보:")
        info = get_stock_info(symbol)
        for key, value in info.items():
            print(f"   {key}: {value}")
        return

    try:
        csv_path = download_stock_data(
            symbol=symbol,
            start_date=args.start,
            end_date=args.end,
        )

        print(f"\n[SUCCESS] 다운로드 완료!")
        print(f"다음 단계: python scripts/create_duckdb_cache.py {csv_path}")

    except Exception as e:
        print(f"[ERROR] 다운로드 실패: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
