"""백테스트 CSV 저장용 DataFrame 변환 유틸리티

CLI 스크립트에서 반복되는 trades CSV 준비, OHLC 전일대비% 및 버퍼존 밴드 계산
패턴을 공용 함수로 제공한다. CSV 저장(to_csv) 자체는 호출부에서 수행한다.
"""

from __future__ import annotations

import pandas as pd

from qbt.backtest.constants import (
    COL_BUY_BUFFER_PCT,
    COL_ENTRY_DATE,
    COL_ENTRY_PRICE,
    COL_EXIT_DATE,
    COL_EXIT_PRICE,
    COL_HOLDING_DAYS,
    COL_LOWER_BAND,
    COL_PNL,
    COL_PNL_PCT,
    COL_UPPER_BAND,
    ROUND_CAPITAL,
    ROUND_PRICE,
    ROUND_RATIO,
)
from qbt.common_constants import COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN

# OHLC 전일대비% 컬럼명 (signal CSV에 저장되어 대시보드가 tooltip에 사용)
COL_OPEN_PCT: str = "open_pct"
COL_HIGH_PCT: str = "high_pct"
COL_LOW_PCT: str = "low_pct"
COL_CLOSE_PCT: str = "close_pct"

OHLC_CHANGE_PCT_COLUMNS: tuple[str, ...] = (COL_OPEN_PCT, COL_HIGH_PCT, COL_LOW_PCT, COL_CLOSE_PCT)
"""signal CSV에 저장되는 OHLC 전일대비% 컬럼명. 대시보드가 직접 참조한다."""

BUFFER_BAND_COLUMNS: tuple[str, ...] = (COL_UPPER_BAND, COL_LOWER_BAND)
"""buffer_zone 전략의 시그널 CSV에 저장되는 밴드 컬럼명."""


def add_holding_days(df: pd.DataFrame) -> pd.DataFrame:
    """trades DataFrame에 holding_days 컬럼을 추가한다.

    entry_date와 exit_date 사이의 달력일 수를 계산한다.
    이미 COL_HOLDING_DAYS 컬럼이 있으면 그대로 반환한다.

    Args:
        df: 거래 내역 DataFrame (entry_date, exit_date 컬럼 필요)

    Returns:
        holding_days 컬럼이 추가된 DataFrame (원본 변경 없음)
    """
    if df.empty or COL_HOLDING_DAYS in df.columns:
        return df

    if COL_ENTRY_DATE in df.columns and COL_EXIT_DATE in df.columns:
        result = df.copy()
        result[COL_HOLDING_DAYS] = result.apply(
            lambda row: (row[COL_EXIT_DATE] - row[COL_ENTRY_DATE]).days,
            axis=1,
        )
        return result

    return df


def prepare_trades_for_csv(trades_df: pd.DataFrame) -> pd.DataFrame:
    """거래 DataFrame에 holding_days 추가, 반올림, 정수 변환을 적용한다.

    빈 DataFrame 입력 시 빈 복사본을 반환한다.

    Args:
        trades_df: 거래 내역 DataFrame (entry_date, exit_date, entry_price, exit_price, pnl 등)

    Returns:
        CSV 저장용으로 변환된 DataFrame 복사본
    """
    export = trades_df.copy()

    if export.empty:
        return export

    # holding_days 추가
    export = add_holding_days(export)

    # 반올림 규칙 적용
    round_dict: dict[str, int] = {}
    if COL_ENTRY_PRICE in export.columns:
        round_dict[COL_ENTRY_PRICE] = ROUND_PRICE
    if COL_EXIT_PRICE in export.columns:
        round_dict[COL_EXIT_PRICE] = ROUND_PRICE
    if COL_PNL in export.columns:
        round_dict[COL_PNL] = ROUND_CAPITAL
    if COL_PNL_PCT in export.columns:
        round_dict[COL_PNL_PCT] = ROUND_RATIO
    if COL_BUY_BUFFER_PCT in export.columns:
        round_dict[COL_BUY_BUFFER_PCT] = ROUND_RATIO

    export = export.round(round_dict)

    # pnl 정수 변환
    if COL_PNL in export.columns:
        export[COL_PNL] = export[COL_PNL].astype(int)

    return export


def add_ohlc_change_pct(df: pd.DataFrame) -> pd.DataFrame:
    """signal DataFrame에 OHLC 4종 전일대비%(`open_pct`/`high_pct`/`low_pct`/`close_pct`)
    컬럼을 추가한 복사본을 반환한다.

    각 OHLC 가격을 전일 종가로 나누어 변동률(%)을 계산한다. 첫 행은 비교 대상이 없으므로
    NaN으로 채워진다. 빈 DataFrame이 입력되면 컬럼만 추가된 빈 복사본을 반환한다.

    이 함수는 대시보드(`scripts/backtest/app_*.py`)가 캔들 tooltip에 사용할 4종 % 값을
    CSV에서 직접 읽을 수 있도록 사전 계산하기 위한 SSoT다.

    Args:
        df: OHLC 컬럼(`COL_OPEN`/`COL_HIGH`/`COL_LOW`/`COL_CLOSE`)을 포함하는 시그널 DataFrame

    Returns:
        4종 % 컬럼이 추가된 DataFrame 복사본 (원본 변경 없음)

    Raises:
        ValueError: 필수 OHLC 컬럼이 누락된 경우
    """
    required = (COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"add_ohlc_change_pct: 필수 컬럼이 누락되었습니다: {missing}")

    result = df.copy()
    if result.empty:
        for col in OHLC_CHANGE_PCT_COLUMNS:
            result[col] = pd.Series(dtype=float)
        return result

    prev_close = result[COL_CLOSE].shift(1)
    result[COL_OPEN_PCT] = (result[COL_OPEN] / prev_close - 1.0) * 100.0
    result[COL_HIGH_PCT] = (result[COL_HIGH] / prev_close - 1.0) * 100.0
    result[COL_LOW_PCT] = (result[COL_LOW] / prev_close - 1.0) * 100.0
    result[COL_CLOSE_PCT] = (result[COL_CLOSE] / prev_close - 1.0) * 100.0
    return result


def add_buffer_zone_bands(
    df: pd.DataFrame,
    ma_col: str,
    buy_buffer_zone_pct: float,
    sell_buffer_zone_pct: float,
) -> pd.DataFrame:
    """signal DataFrame에 buffer_zone 전략의 `upper_band`/`lower_band` 컬럼을
    추가한 복사본을 반환한다.

    산식 (도메인 절대 규칙, `src/qbt/backtest/CLAUDE.md` 핵심 계산 로직 참조):
        upper_band = ma * (1 + buy_buffer_zone_pct)   # 매수 진입 기준
        lower_band = ma * (1 - sell_buffer_zone_pct)  # 매도 청산 기준

    Args:
        df: 이동평균 컬럼(`ma_col`)을 포함하는 시그널 DataFrame
        ma_col: 이동평균 컬럼명 (예: `"ma_200"`)
        buy_buffer_zone_pct: 매수 버퍼존 비율 (0.03 = 3%)
        sell_buffer_zone_pct: 매도 버퍼존 비율 (0.05 = 5%)

    Returns:
        밴드 컬럼이 추가된 DataFrame 복사본 (원본 변경 없음)

    Raises:
        ValueError: `ma_col`이 DataFrame에 존재하지 않는 경우
    """
    if ma_col not in df.columns:
        raise ValueError(f"add_buffer_zone_bands: ma_col='{ma_col}' 컬럼이 DataFrame에 존재하지 않습니다")

    result = df.copy()
    result[COL_UPPER_BAND] = result[ma_col] * (1.0 + buy_buffer_zone_pct)
    result[COL_LOWER_BAND] = result[ma_col] * (1.0 - sell_buffer_zone_pct)
    return result
