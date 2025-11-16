#!/usr/bin/env python3
"""
QBT (Quant BackTest) CLI

Main entry point for running data downloads, backtests, and other operations.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="QBT - Quantitative Backtesting Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령어")

    # Download 서브커맨드
    download_parser = subparsers.add_parser(
        "download", help="Yahoo Finance에서 주식 데이터 다운로드"
    )
    download_parser.add_argument("ticker", help="주식 티커 심볼 (예: QQQ, SPY)")
    download_parser.add_argument("--start", help="시작 날짜 (YYYY-MM-DD)")
    download_parser.add_argument("--end", help="종료 날짜 (YYYY-MM-DD)")

    # 향후 추가될 서브커맨드
    # backtest_parser = subparsers.add_parser("backtest", help="백테스트 실행")
    # ...

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "download":
        from qbt.data.download import download_stock_data

        ticker = args.ticker.upper()

        try:
            csv_path = download_stock_data(
                ticker=ticker,
                start_date=args.start,
                end_date=args.end,
            )

            print(f"\n[SUCCESS] 다운로드 완료!")
            print(f"파일 경로: {csv_path}")

        except Exception as e:
            print(f"[ERROR] 다운로드 실패: {e}")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
