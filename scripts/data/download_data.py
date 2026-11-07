"""
주식 데이터 다운로드 스크립트

Yahoo Finance에서 주식 데이터를 다운로드하여 CSV로 저장한다.
기존 파일이 있으면 받은 시세와 견준다 — 흔들림뿐이면 기존 행을 그대로 두고 새 날짜 행만 붙이고, 배당 · 분할 기록으로
설명되는 변화면 덮어쓰고, 그 밖은 덮어쓰지 않은 채 원인 블록을 낸다(터미널이면 종목마다 덮어쓸지 묻는다).
인자 없이 돌리면 레버리지 합성이 쓰는 FRED 월별 연방기금금리도 전체 기간을 받아 금리 파일을 다시 쓰고,
GLD 합성의 금 사슬이 쓰는 Perth Mint 금값 · FRED 호주달러 환율도 받는다.

실행 명령어:
    # 전체 종목 일괄 다운로드 + 월별 금리 · 금 대용 자료 (인자 없이 실행)
    poetry run python scripts/data/download_data.py

    # 특정 종목 다운로드 (금리 · 금 대용 자료는 받지 않는다)
    poetry run python scripts/data/download_data.py QQQ

    # 받을 마지막 날 지정 (그날 포함 — 뉴욕에서 그날 봉이 끝나기 전인 날은 빠진다)
    poetry run python scripts/data/download_data.py --end 2026-11-06
"""

import argparse
import sys
from datetime import date, datetime
from typing import Final

from qbt.common_constants import AUD_USD_DATA_PATH, PERTH_MINT_GOLD_DATA_PATH
from qbt.tqqq.constants import FFR_DATA_PATH
from qbt.tqqq.data_loader import download_ffr_monthly
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.gold_proxy import download_gold_proxy_sources
from qbt.utils.price_revision import RevisionKind, format_abnormal_block
from qbt.utils.stock_downloader import (
    YFINANCE_VERSION,
    StockDownload,
    confirm_overwrites,
    download_stock_data,
    resolve_cutoff_date,
)

logger = get_logger(__name__)

# 전체 다운로드 대상 티커 목록 (인자 없이 실행 시 사용)
# 야후 원본 시세 전부 — 인자 없는 다운로드 뒤 합성 생성만 돌리는 흐름의 입력 (scripts/CLAUDE.md)
DEFAULT_TICKERS: Final = (
    "SPY",
    "QQQ",
    "GLD",
    "TLT",
    "TQQQ",
    "SSO",
    "QLD",
    "^NDX",
    "UOPIX",
    "RYNVX",
    "VFINX",
    "UPRO",
    "ULPIX",
    "VUSTX",
    "GC=F",
)


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

            # 받을 마지막 날 지정 (그날 포함)
            poetry run python scripts/data/download_data.py --end 2026-11-06
        """,
    )
    parser.add_argument(
        "ticker",
        nargs="?",
        default=None,
        help="주식 티커 심볼 (예: QQQ, SPY). 미지정 시 전체 종목과 월별 연방기금금리(FRED) · 금 대용 자료(Perth Mint 금값 · FRED 호주달러 환율) 다운로드",
    )
    parser.add_argument(
        "--end",
        type=_parse_end_date,
        default=None,
        help="받을 마지막 날 YYYY-MM-DD (그날 포함, 오늘까지). 뉴욕에서 그날 봉이 끝나기 전인 날은 빠진다. 미지정 시 그저께까지",
    )

    return parser.parse_args()


def _parse_end_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"날짜는 YYYY-MM-DD 로 주세요: {text!r}") from None


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패 · 덮어쓸지 묻지 못한 비정상 종목이 있음)
    """
    args = parse_args()
    now = datetime.now().astimezone()
    cutoff_date = resolve_cutoff_date(args.end, now)
    logger.debug(f"받을 마지막 날: {cutoff_date}")

    tickers = (args.ticker.upper(),) if args.ticker is not None else DEFAULT_TICKERS
    abnormal: list[StockDownload] = []
    for ticker in tickers:
        logger.debug(f"데이터 다운로드 시작: {ticker}")
        download = download_stock_data(ticker, cutoff_date)
        if download.revision.kind is RevisionKind.ABNORMAL:
            abnormal.append(download)
        else:
            logger.debug(f"다운로드 완료: {download.path}")

    # 금리 · 금 대용 받기 앞에서 묻는다 — 뒤 단계가 실패해도 원인 블록이 묻히지 않게
    unanswered = _confirm_overwrites(abnormal, now, cutoff_date) if abnormal else False

    # 금리 · 금 대용 자료는 전체 갱신 때만 — 티커 하나만 받을 때 다른 입력이 바뀌지 않게
    if args.ticker is None:
        download_ffr_monthly(FFR_DATA_PATH)
        download_gold_proxy_sources(PERTH_MINT_GOLD_DATA_PATH, AUD_USD_DATA_PATH)

    if unanswered:
        logger.error("덮어쓸지 묻지 못한 비정상 종목이 있습니다 — 위 원인 블록을 확인하고 터미널에서 다시 실행해 답하세요")
        return 1
    return 0


def _confirm_overwrites(abnormal: list[StockDownload], now: datetime, cutoff_date: date) -> bool:
    """비정상 종목의 원인 블록을 내고, 터미널이면 종목마다 덮어쓸지 묻는다. 묻지 못했으면 True."""
    entries = [(download.ticker, download.path, download.revision) for download in abnormal]
    block = format_abnormal_block(entries, run_at=now, cutoff_date=cutoff_date, yfinance_version=YFINANCE_VERSION)
    logger.warning(f"비정상 {len(abnormal)}종목 — 원인 블록:\n{block}")

    # 동의 없이 덮어쓰지 않게 — 터미널이 아니면(파이프 · 에이전트 실행) 묻지 않음
    return confirm_overwrites(abnormal, _ask_in_terminal if sys.stdin.isatty() else None)


def _ask_in_terminal(question: str) -> str:
    print(question, end="", flush=True)
    return sys.stdin.readline()  # EOF 면 빈 문자열 → 그대로 둠


if __name__ == "__main__":
    sys.exit(main())
