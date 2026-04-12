"""주가 데이터 수집 및 CSV 누적 append.

매일 실행 모드에서 yfinance 로 최근 N 일 데이터를 가져와 live 전용 CSV 에
1 행씩 append 한다.

QBT 본체 재사용:

- :func:`qbt.utils.data_loader.load_stock_data` — CSV 파싱 / 정렬 / 필수 컬럼 검증
  (live :func:`load_csv` 가 이를 얇게 래핑)
- :data:`qbt.common_constants.COL_DATE`, :data:`REQUIRED_COLUMNS`,
  :data:`PRICE_COLUMNS` — QBT 표준 컬럼 포맷

QBT 본체 재사용하지 않는 이유:

- :func:`qbt.utils.stock_downloader.download_stock_data` 는 "최근 2일 제외" 필터가
  하드코딩되어 live 매일 실행 모드와 충돌
- 저장 경로가 ``STOCK_DIR`` 로 고정되어 qbt-live-state 리포 경로와 다름
- 파일명 규칙이 달라짐 (QBT: ``{TICKER}_max.csv``, live: ``{TICKER}.csv``)

검증 책임 분리:

- 본 모듈은 "가져오기 / 쓰기" 만 담당한다. OHLC 논리 / 종가 연속성 / 날짜 누락
  검증은 :mod:`live.data_validator` 소관이다. 본 모듈은 yfinance 빈 응답만 방어한다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from live.constants import DEFAULT_PRICE_DECIMALS, DEFAULT_RECENT_FETCH_DAYS
from qbt.common_constants import COL_DATE, PRICE_COLUMNS, REQUIRED_COLUMNS
from qbt.utils.data_loader import load_stock_data

__all__ = [
    "fetch_recent_ohlc",
    "append_today_to_csv",
    "rebuild_full_csv",
    "load_csv",
]


def _yf_history_to_qbt_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    """yfinance ``Ticker.history()`` 결과를 QBT 표준 DataFrame 으로 변환한다.

    변환 규칙:

    1. ``DatetimeIndex`` → ``Date`` 컬럼 (``datetime.date`` 객체)
    2. ``REQUIRED_COLUMNS`` 만 선택 (Dividends / Stock Splits 등 제거)
    3. 가격 컬럼 6 자리 반올림
    4. Date 오름차순 정렬

    Args:
        raw_df: yfinance 에서 반환된 원본 DataFrame.

    Returns:
        QBT 표준 포맷 DataFrame.
    """
    df = raw_df.copy()
    df.reset_index(inplace=True)

    # yfinance 는 때때로 index 이름이 "Date" 또는 "Datetime" 로 돌아온다.
    # reset_index 후 첫 컬럼이 날짜 컬럼이라 가정하고 이름을 통일한다.
    first_col = df.columns[0]
    if first_col != COL_DATE:
        df = df.rename(columns={first_col: COL_DATE})

    df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date

    df = df[REQUIRED_COLUMNS]
    df[PRICE_COLUMNS] = df[PRICE_COLUMNS].round(DEFAULT_PRICE_DECIMALS)

    df = df.sort_values(COL_DATE).reset_index(drop=True)
    return df


def fetch_recent_ohlc(ticker: str, days: int = DEFAULT_RECENT_FETCH_DAYS) -> pd.DataFrame:
    """yfinance 에서 최근 ``days`` 일의 OHLCV 를 가져온다.

    QBT 와 달리 "최근 2 일 제외" 필터를 적용하지 않는다. live 매일 실행 모드는
    당일 데이터가 필요하므로 yfinance 반환값을 그대로 변환하여 돌려준다.

    Args:
        ticker: 티커 심볼 (예: ``"SPY"``).
        days: 조회할 최근 일수 (기본 5).

    Returns:
        QBT 표준 포맷 DataFrame (Date / Open / High / Low / Close / Volume).

    Raises:
        ValueError: yfinance 가 빈 DataFrame 을 반환할 때.
    """
    if days <= 0:
        raise ValueError(f"days 는 양수여야 한다. 입력: {days}")

    yf_ticker = yf.Ticker(ticker)
    raw = yf_ticker.history(period=f"{days}d")

    if raw.empty:
        raise ValueError(f"yfinance 데이터 없음: ticker={ticker}, days={days}")

    return _yf_history_to_qbt_df(raw)


def append_today_to_csv(csv_path: Path, today_row: pd.DataFrame) -> None:
    """기존 CSV 에 1 행을 append 한다 (중복 날짜 방지).

    규칙:

    - ``today_row`` 는 반드시 1 행 DataFrame 이어야 한다.
    - 파일이 없거나 빈 경우 → 부모 디렉토리 생성 후 새 CSV 로 저장.
    - 파일이 있고 해당 날짜가 이미 존재하면 → 변경 없이 return (중복 append 방지).
    - 파일이 있고 해당 날짜가 없으면 → 기존 데이터와 concat 후 정렬하여 저장.
    - 가격 컬럼은 저장 직전에 6 자리 반올림.

    Args:
        csv_path: 대상 CSV 파일 경로.
        today_row: 저장할 1 행 DataFrame (Date / Open / High / Low / Close / Volume).

    Raises:
        ValueError: ``today_row`` 가 1 행이 아닐 때.
    """
    if len(today_row) != 1:
        raise ValueError(f"today_row 는 1 행 DataFrame 이어야 한다. 실제: {len(today_row)} 행")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new_row = today_row.copy()
    new_row[COL_DATE] = pd.to_datetime(new_row[COL_DATE]).dt.date
    new_row[PRICE_COLUMNS] = new_row[PRICE_COLUMNS].round(DEFAULT_PRICE_DECIMALS)
    new_date = new_row[COL_DATE].iloc[0]

    if not csv_path.exists():
        out = new_row[REQUIRED_COLUMNS].sort_values(COL_DATE).reset_index(drop=True)
        out.to_csv(csv_path, index=False)
        return

    existing = load_stock_data(csv_path)
    if new_date in set(existing[COL_DATE]):
        # 중복 날짜 — 기존 값을 덮어쓰지 않고 그대로 유지
        return

    combined = pd.concat([existing, new_row[REQUIRED_COLUMNS]], ignore_index=True)
    combined = combined.sort_values(COL_DATE).reset_index(drop=True)
    combined[PRICE_COLUMNS] = combined[PRICE_COLUMNS].round(DEFAULT_PRICE_DECIMALS)
    combined.to_csv(csv_path, index=False)


def rebuild_full_csv(ticker: str, csv_path: Path, period: str = "max") -> None:
    """yfinance 에서 전체 기간 데이터를 가져와 CSV 를 완전히 재작성한다.

    스플릿 대응 시나리오에서 사용된다. 기존 CSV 는 덮어쓰기된다.
    부모 디렉토리는 자동 생성.

    Args:
        ticker: 티커 심볼.
        csv_path: 저장 대상 CSV 경로.
        period: yfinance period 문자열 (기본 ``"max"``).

    Raises:
        ValueError: yfinance 가 빈 DataFrame 을 반환할 때.
    """
    yf_ticker = yf.Ticker(ticker)
    raw = yf_ticker.history(period=period)

    if raw.empty:
        raise ValueError(f"yfinance 데이터 없음: ticker={ticker}, period={period}")

    df = _yf_history_to_qbt_df(raw)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)


def load_csv(csv_path: Path) -> pd.DataFrame:
    """live 전용 CSV 로드 래퍼. 내부적으로 QBT ``load_stock_data`` 를 호출한다.

    QBT 본체의 검증 / 정렬 / 중복 제거 로직을 그대로 재사용하여 SSoT 를 유지한다.
    live 측에 wrapper 를 두는 이유: 호출처에서 ``from live.data_fetcher import load_csv``
    단일 import 경로를 제공하고, 향후 live 전용 전처리가 추가될 때 확장 지점을 확보.

    Args:
        csv_path: CSV 파일 경로.

    Returns:
        전처리된 DataFrame (Date 오름차순, 중복 제거, 필수 컬럼 검증 완료).

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때.
        ValueError: 필수 컬럼 누락 등.
    """
    return load_stock_data(csv_path)
