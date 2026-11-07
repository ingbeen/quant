"""주식 데이터 다운로드 · 검증 · 저장 유틸리티

Yahoo Finance에서 주식 데이터를 다운로드하고, 데이터 유효성을 검증하는 함수를 제공한다.

주요 기능:
1. 주식 데이터 유효성 검증 (중복 날짜, 결측치, 0값, 음수, 급등락)
2. 시세 CSV 저장 (가격 반올림 → 검증 → 저장 — 수집 시세와 합성 · 대용 시세가 같은 함수로 저장한다)
3. 받을 마지막 날 정하기 (기본은 그저께, 날짜를 주면 뉴욕에서 그날 봉이 끝나기 전인 날을 뺀다)
4. Yahoo Finance에서 주식 데이터 다운로드 — 기존 파일과 견줘(price_revision) 비정상이 아니면 저장
5. 비정상 종목의 덮어쓰기 동의 — 답이 y 인 종목만 응답으로 저장
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import yfinance as yf

from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    PRICE_COLUMNS,
    REQUIRED_COLUMNS,
    STOCK_DIR,
)
from qbt.utils.data_loader import load_stock_data, validate_price_series
from qbt.utils.logger import get_logger
from qbt.utils.price_revision import PriceEvents, PriceRevision, RevisionKind, judge_revision

logger = get_logger(__name__)

# 데이터 검증 관련 상수
DEFAULT_PRICE_CHANGE_THRESHOLD = 0.50

# 수집 · 합성 시세 파일의 가격 자릿수 — 결과 파일(ROUND_PRICE)과 다른 이유는 루트 CLAUDE.md 「가격 반올림 자릿수」
ROUND_INPUT_PRICE = 6

YFINANCE_VERSION: Final = yf.__version__
# history(auto_adjust=False) 의 열 — 배당 · 분할 기록과 원시 종가를 같은 응답에서 얻으려고 수정 가격을 직접 만든다
COL_ADJ_CLOSE: Final = "Adj Close"
COL_DIVIDENDS: Final = "Dividends"
COL_STOCK_SPLITS: Final = "Stock Splits"

# 받을 마지막 날의 기본 — 한국 날짜 D 의 0시에도 뉴욕 D−1 장이 열려 있을 수 있음 → 시각을 따지지 않고 늘 마감된 D−2 까지
EXCLUDED_RECENT_DAYS: Final = 2
NEW_YORK_TIMEZONE: Final = "America/New_York"
# 받는 종목 모두의 그날 봉이 끝나는 시각 — 주식은 16:00 마감, 금 선물(GC=F)은 17:00 마감 뒤 18:00 에 다음 거래 시작
NEW_YORK_DAY_END: Final = time(18, 0)


@dataclass(frozen=True)
class StockDownload:
    """받은 결과 — 판정이 비정상이면 파일을 쓰지 않았고, 덮어쓸 때 저장할 응답은 revision.prices 다."""

    ticker: str
    path: Path
    revision: PriceRevision


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


def resolve_cutoff_date(end_date: date | None, now: datetime) -> date:
    """
    받을 마지막 날.

    Args:
        end_date: 받을 마지막 날(포함). None 이면 오늘에서 EXCLUDED_RECENT_DAYS 를 뺀 날
        now: 지금 시각 (시간대 포함 — 그 시간대의 날짜를 오늘로 본다)

    Returns:
        end_date 가 있으면 그날과, 뉴욕에서 그날 봉이 다 끝난 마지막 날(NEW_YORK_DAY_END) 중 이른 날

    Raises:
        ValueError: now 에 시간대가 없을 때, end_date 가 오늘보다 뒤일 때
        ZoneInfoNotFoundError: end_date 가 있는데 뉴욕 시간대 자료가 없을 때
    """
    if now.tzinfo is None:
        raise ValueError("지금 시각에 시간대가 없습니다 — 뉴욕에서 그날 봉이 끝났는지 가를 수 없습니다")
    today = now.date()
    if end_date is None:
        return today - timedelta(days=EXCLUDED_RECENT_DAYS)
    if end_date > today:
        raise ValueError(f"받을 마지막 날 {end_date} 가 오늘({today})보다 뒤입니다 — 오늘이나 그 이전 날짜를 주세요")

    new_york_now = now.astimezone(_new_york_zone())
    closed = new_york_now.date() if new_york_now.time() >= NEW_YORK_DAY_END else new_york_now.date() - timedelta(days=1)
    if closed < end_date:
        logger.debug(f"뉴욕에서 그날 봉이 끝나기({NEW_YORK_DAY_END:%H:%M}) 전인 날은 빼고 {closed} 까지 받습니다 (요청 {end_date})")
    return min(end_date, closed)


def _new_york_zone() -> ZoneInfo:
    try:
        return ZoneInfo(NEW_YORK_TIMEZONE)
    except ZoneInfoNotFoundError:
        raise ZoneInfoNotFoundError(
            f"뉴욕 시간대 자료({NEW_YORK_TIMEZONE})가 없습니다 — 운영체제의 tzdata 를 설치하거나 " f"`poetry add tzdata` 로 넣은 뒤 다시 실행하세요"
        ) from None


def adjust_prices(raw: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance auto_adjust 와 같은 수정 가격 — 시가 · 고가 · 저가 × (수정 종가 ÷ 원시 종가), 종가 = 수정 종가, 거래량 그대로.

    Args:
        raw: history(auto_adjust=False) 를 날짜 열로 편 표 (COL_DATE · 원시 가격 · COL_ADJ_CLOSE · COL_VOLUME)

    Returns:
        REQUIRED_COLUMNS 표
    """
    ratio = (raw[COL_ADJ_CLOSE] / raw[COL_CLOSE]).to_numpy()
    adjusted = pd.DataFrame(
        {
            COL_DATE: raw[COL_DATE],
            COL_OPEN: raw[COL_OPEN] * ratio,
            COL_HIGH: raw[COL_HIGH] * ratio,
            COL_LOW: raw[COL_LOW] * ratio,
            COL_CLOSE: raw[COL_ADJ_CLOSE],
            COL_VOLUME: raw[COL_VOLUME],
        }
    )
    return adjusted[REQUIRED_COLUMNS]


def download_stock_data(ticker: str, cutoff_date: date) -> StockDownload:
    """
    주식 데이터를 전체 기간으로 받아 기존 `{ticker}_max.csv` 와 견준 뒤(price_revision.judge_revision) 비정상이 아니면 저장한다.

    Args:
        ticker: 주식 티커 (예: QQQ, SPY)
        cutoff_date: 받을 마지막 날 (resolve_cutoff_date). 기존 파일이 더 뒤까지 있으면 기존 끝날까지 견준다 —
            기존 행은 판정 없이 지우지 않는다

    Returns:
        StockDownload — 비정상이면 파일을 쓰지 않았다

    Raises:
        ValueError: 데이터가 없을 때, 응답에 수정 종가 · 배당 · 분할 열이 없을 때, 기존 파일 · 저장할 표가 검사에 걸릴 때
    """
    # 1. 전체 기간의 원시 시세 · 수정 종가 · 배당 · 분할 받기
    history = yf.Ticker(ticker).history(period="max", auto_adjust=False)
    if history.empty:
        raise ValueError(f"데이터를 찾을 수 없습니다: {ticker}")
    missing = [col for col in (COL_ADJ_CLOSE, COL_DIVIDENDS, COL_STOCK_SPLITS) if col not in history.columns]
    if missing:
        raise ValueError(f"{ticker} 응답에 {missing} 열이 없습니다 — 기존 시세와 견줄 수 없습니다")

    # 2. 날짜 열로 펴고 수정 가격 · 기록 만들기 (기록은 기준일로 자르기 전 전체)
    raw = history.reset_index()
    raw[COL_DATE] = pd.to_datetime(raw[COL_DATE]).dt.date
    events = PriceEvents(
        dividends=raw.loc[raw[COL_DIVIDENDS] > 0].set_index(COL_DATE)[COL_DIVIDENDS],
        splits=raw.loc[raw[COL_STOCK_SPLITS] > 0].set_index(COL_DATE)[COL_STOCK_SPLITS],
        raw_close=raw.set_index(COL_DATE)[COL_CLOSE],
    )
    prices = adjust_prices(raw)

    # 3. 견줄 범위 — 기존 끝날보다 이르게 자르지 않는다
    csv_path = STOCK_DIR / f"{ticker}_max.csv"
    existing = load_stock_data(csv_path) if csv_path.exists() else None
    last_day = cutoff_date if existing is None else max(cutoff_date, existing[COL_DATE].iloc[-1])
    response = prices[prices[COL_DATE] <= last_day].reset_index(drop=True)

    # 4. 판정 → 비정상이 아니면 가격 반올림 → 검증 → 저장
    revision = judge_revision(existing, response, events, price_decimals=ROUND_INPUT_PRICE)
    _log_revision(ticker, revision)
    if revision.kind is not RevisionKind.ABNORMAL:
        save_stock_csv(revision.prices, csv_path)

    excluded = len(prices) - len(response)
    if excluded > 0:
        logger.debug(f"{last_day} 뒤 {excluded}행 제외")
    return StockDownload(ticker=ticker, path=csv_path, revision=revision)


def _log_revision(ticker: str, revision: PriceRevision) -> None:
    match revision.kind:
        case RevisionKind.NEW:
            logger.debug(f"{ticker}: 기존 파일 없음 — 새로 저장")
        case RevisionKind.NOISE:
            appended = len(revision.prices) - revision.existing_rows
            logger.debug(f"{ticker}: 흔들림뿐 — 기존 {revision.existing_rows:,}행 그대로, 새 날짜 {appended:,}행")
        case RevisionKind.EXPLAINED:
            logger.debug(f"{ticker}: 배당 · 분할 기록으로 설명되는 변화 — 응답으로 덮어씀: {' / '.join(revision.applied)}")
        case RevisionKind.ABNORMAL:
            logger.warning(f"{ticker}: 기존 시세와 다른 변화 {len(revision.issues):,}건 — 덮어쓰지 않음 (원인은 시세 받기 뒤 블록)")


def confirm_overwrites(downloads: Sequence[StockDownload], ask: Callable[[str], str] | None) -> bool:
    """
    비정상 종목마다 덮어쓸지 묻고, 답이 y · Y 인 종목만 응답으로 저장한다 — 그 밖의 답 · 빈 답(EOF)은 그대로 둔다.

    Args:
        downloads: 비정상 판정을 받은 종목
        ask: 질문을 보이고 답 한 줄을 돌려준다(EOF 면 빈 문자열). None 이면(터미널이 아님) 묻지 않고 아무것도 덮어쓰지 않는다

    Returns:
        묻지 못했으면 True

    Raises:
        ValueError: 비정상이 아닌 종목이 섞였을 때
    """
    not_abnormal = [d.ticker for d in downloads if d.revision.kind is not RevisionKind.ABNORMAL]
    if not_abnormal:
        raise ValueError(f"덮어쓸지 묻는 것은 비정상 종목뿐입니다 — 섞인 종목: {not_abnormal}")
    if ask is None:
        logger.warning("터미널이 아니라 묻지 않았습니다 — 비정상 종목은 덮어쓰지 않았습니다")
        return True
    for download in downloads:
        answer = ask(f"{download.ticker} 를 이번 응답으로 덮어쓸까요? [y/N]: ")
        if answer.strip().lower() == "y":
            save_stock_csv(download.revision.prices, download.path)
            logger.debug(f"덮어씀: {download.path}")
        else:
            logger.debug(f"그대로 둠: {download.path}")
    return False
