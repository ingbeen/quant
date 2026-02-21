"""
주식 데이터 다운로드 스크립트

Yahoo Finance에서 주식 데이터를 다운로드하여 CSV로 저장한다.

실행 명령어:
    # 전체 기간 다운로드
    poetry run python scripts/data/download_data.py QQQ

    # 시작 날짜 지정
    poetry run python scripts/data/download_data.py SPY --start 2020-01-01

    # 기간 지정
    poetry run python scripts/data/download_data.py AAPL --start 2020-01-01 --end 2023-12-31
"""

import argparse
import sys

from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.stock_downloader import download_stock_data

logger = get_logger(__name__)


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
