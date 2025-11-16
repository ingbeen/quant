#!/usr/bin/env python3
"""
QBT (Quant BackTest) CLI

Main entry point for running data downloads, backtests, and other operations.
"""

import argparse
import sys

from qbt.data.download import download_stock_data
from qbt.utils import get_logger, setup_logger

# Logger 초기화 (환경 변수로 레벨 제어 가능)
log_level = "DEBUG"
setup_logger(name="qbt", level=log_level)
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
    """Download 커맨드 실행"""

    ticker = args.ticker.upper()
    download_stock_data(
        ticker=ticker,
        start_date=args.start,
        end_date=args.end,
    )


def main():
    """CLI 진입점"""
    parser = argparse.ArgumentParser(
        description="QBT - Quantitative Backtesting Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령어")

    # 서브커맨드 파서 설정
    setup_download_parser(subparsers)

    # 향후 추가될 서브커맨드
    # setup_backtest_parser(subparsers)
    # 핸들러 함수도 함께 추가: handle_backtest(args)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        # 명령 실행
        if args.command == "download":
            handle_download(args)
    except Exception as e:
        logger.error(f"실행 실패: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
