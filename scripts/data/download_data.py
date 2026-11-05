"""
주식 데이터 다운로드 스크립트

Yahoo Finance에서 주식 데이터를 다운로드하여 CSV로 저장한다.
인자 없이 돌리면 레버리지 합성이 쓰는 FRED 월별 연방기금금리도 전체 기간을 받아 금리 파일을 다시 쓴다.

실행 명령어:
    # 전체 종목 일괄 다운로드 + 월별 금리 (인자 없이 실행)
    poetry run python scripts/data/download_data.py

    # 특정 종목 다운로드 (금리는 받지 않는다)
    poetry run python scripts/data/download_data.py QQQ
"""

import argparse
import sys
from typing import Final

from qbt.tqqq.constants import FFR_DATA_PATH
from qbt.tqqq.data_loader import download_ffr_monthly
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.stock_downloader import download_stock_data

logger = get_logger(__name__)

# 전체 다운로드 대상 티커 목록 (인자 없이 실행 시 사용)
# 야후 원본 시세 전부 — 인자 없는 다운로드 뒤 합성 생성만 돌리는 흐름의 입력 (scripts/CLAUDE.md)
DEFAULT_TICKERS: Final = ("SPY", "QQQ", "GLD", "TLT", "TQQQ", "SSO", "QLD", "^NDX", "UOPIX", "RYNVX", "VFINX")


def parse_args():
    """CLI 인자를 파싱한다."""
    parser = argparse.ArgumentParser(
        description="Yahoo Finance에서 주식 데이터 다운로드",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            사용 예시:
            # 전체 종목 일괄 다운로드
            poetry run python scripts/data/download_data.py

            # 특정 종목 다운로드
            poetry run python scripts/data/download_data.py QQQ
        """,
    )
    parser.add_argument(
        "ticker",
        nargs="?",
        default=None,
        help="주식 티커 심볼 (예: QQQ, SPY). 미지정 시 전체 종목과 월별 연방기금금리(FRED) 다운로드",
    )

    return parser.parse_args()


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    args = parse_args()

    tickers = (args.ticker.upper(),) if args.ticker is not None else DEFAULT_TICKERS
    for ticker in tickers:
        logger.debug(f"데이터 다운로드 시작: {ticker}")
        csv_path = download_stock_data(ticker)
        logger.debug(f"다운로드 완료: {csv_path}")

    # 금리는 전체 갱신 때만 — 티커 하나만 받을 때 다른 입력이 바뀌지 않게
    if args.ticker is None:
        download_ffr_monthly(FFR_DATA_PATH)

    return 0


if __name__ == "__main__":
    sys.exit(main())
