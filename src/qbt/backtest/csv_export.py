"""백테스트 CSV 저장용 DataFrame 변환 유틸리티

CLI 스크립트에서 반복되는 trades CSV 준비, change_pct 계산 패턴을 공용 함수로 제공한다.
CSV 저장(to_csv) 자체는 호출부에서 수행한다.
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
    COL_PNL,
    COL_PNL_PCT,
    ROUND_CAPITAL,
    ROUND_PRICE,
    ROUND_RATIO,
)
from qbt.common_constants import COL_CLOSE


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


def calculate_change_pct(df: pd.DataFrame, close_col: str = COL_CLOSE) -> pd.Series[float]:
    """전일대비 변동률(%) 시리즈를 계산한다.

    Args:
        df: 종가 컬럼을 포함하는 DataFrame
        close_col: 종가 컬럼명 (기본: COL_CLOSE)

    Returns:
        전일대비 변동률 시리즈 (단위: %)
    """
    return df[close_col].pct_change() * 100
