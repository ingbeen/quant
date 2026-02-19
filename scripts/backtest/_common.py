"""
백테스트 스크립트 공통 데이터 로딩 모듈

run_single_backtest.py와 run_grid_search.py에서 공통으로 사용하는
QQQ/TQQQ 데이터 로딩 및 공통 날짜 필터 로직을 제공한다.
"""

import logging

import pandas as pd

from qbt.common_constants import (
    COL_DATE,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils.data_loader import load_stock_data


def load_backtest_data(logger: logging.Logger) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    QQQ, TQQQ 데이터를 로딩하고 공통 날짜로 필터링한다.

    Args:
        logger: 로깅에 사용할 로거

    Returns:
        tuple: (signal_df, trade_df) 공통 날짜 기준 정렬된 DataFrame
    """
    logger.debug(f"시그널 데이터: {QQQ_DATA_PATH}")
    logger.debug(f"매매 데이터: {TQQQ_SYNTHETIC_DATA_PATH}")
    signal_df = load_stock_data(QQQ_DATA_PATH)
    trade_df = load_stock_data(TQQQ_SYNTHETIC_DATA_PATH)

    # 공통 날짜로 필터링
    common_dates = set(signal_df[COL_DATE]) & set(trade_df[COL_DATE])
    signal_df = signal_df[signal_df[COL_DATE].isin(common_dates)].reset_index(drop=True)
    trade_df = trade_df[trade_df[COL_DATE].isin(common_dates)].reset_index(drop=True)

    logger.debug("=" * 60)
    logger.debug("데이터 로딩 완료")
    logger.debug(
        f"시그널(QQQ) 행 수: {len(signal_df):,}, "
        f"기간: {signal_df[COL_DATE].min()} ~ {signal_df[COL_DATE].max()}"
    )
    logger.debug(
        f"매매(TQQQ) 행 수: {len(trade_df):,}, "
        f"기간: {trade_df[COL_DATE].min()} ~ {trade_df[COL_DATE].max()}"
    )
    logger.debug(f"공통 기간: {len(signal_df):,}행")
    logger.debug("=" * 60)

    return signal_df, trade_df
