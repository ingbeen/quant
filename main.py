#!/usr/bin/env python3
"""
QBT (Quant BackTest) CLI

Main entry point for running data downloads, backtests, and other operations.
"""

import argparse
import os
import sys

from qbt.utils import get_logger, setup_logger

logger = get_logger(__name__)


def setup_download_parser(subparsers):
    """Download 서브커맨드 파서 설정"""
    parser = subparsers.add_parser(
        "download", help="Yahoo Finance에서 주식 데이터 다운로드"
    )
    parser.add_argument("ticker", help="주식 티커 심볼 (예: QQQ, SPY)")
    parser.add_argument("--start", help="시작 날짜 (YYYY-MM-DD)")
    parser.add_argument("--end", help="종료 날짜 (YYYY-MM-DD)")
    return parser


def handle_download(args):
    """Download 명령 처리"""
    from qbt.data.download import download_stock_data

    ticker = args.ticker.upper()
    download_stock_data(
        ticker=ticker,
        start_date=args.start,
        end_date=args.end,
    )


def main():
    logger.debug("QBT 시작")

    # Logger 초기화 (환경 변수로 레벨 제어 가능)
    log_level = os.getenv("QBT_LOG_LEVEL", "DEBUG")
    setup_logger(name="qbt", level=log_level)

    parser = argparse.ArgumentParser(
        description="QBT - Quantitative Backtesting Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령어")

    # 서브커맨드 파서 설정
    setup_download_parser(subparsers)

    # 향후 추가될 서브커맨드
    # setup_backtest_parser(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # 명령 실행
    if args.command == "download":
        handle_download(args)

    logger.debug("QBT 종료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
