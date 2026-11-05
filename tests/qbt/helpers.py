"""여러 테스트 파일이 같이 쓰는 합성 데이터 · 설정 헬퍼

pytest 가 테스트 파일의 폴더(`tests/qbt`)를 import 경로에 넣으므로 `from helpers import …` 로 쓴다.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    GLD_SYNTHETIC_DATA_PATH,
    QLD_SYNTHETIC_DATA_PATH,
    QQQ_SYNTHETIC_DATA_PATH,
    SPY_SYNTHETIC_DATA_PATH,
    SSO_SYNTHETIC_DATA_PATH,
    TLT_SYNTHETIC_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
    UPRO_SYNTHETIC_DATA_PATH,
)

# 매매하는 합성 시세 → 같은 지수의 1배 합성 — 버퍼존 신호는 2 · 3배도 1배 시세 (docs/MEMORY.md 「버퍼존 레버리지는 1배 신호」)
ONE_TIMES_SIGNAL_OF: dict[Path, Path] = {
    QQQ_SYNTHETIC_DATA_PATH: QQQ_SYNTHETIC_DATA_PATH,
    QLD_SYNTHETIC_DATA_PATH: QQQ_SYNTHETIC_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH: QQQ_SYNTHETIC_DATA_PATH,
    SPY_SYNTHETIC_DATA_PATH: SPY_SYNTHETIC_DATA_PATH,
    SSO_SYNTHETIC_DATA_PATH: SPY_SYNTHETIC_DATA_PATH,
    UPRO_SYNTHETIC_DATA_PATH: SPY_SYNTHETIC_DATA_PATH,
    GLD_SYNTHETIC_DATA_PATH: GLD_SYNTHETIC_DATA_PATH,
    TLT_SYNTHETIC_DATA_PATH: TLT_SYNTHETIC_DATA_PATH,
}


def weekdays(start: date, end: date) -> list[date]:
    """start ~ end 의 평일 (양 끝 포함)."""
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _stock_df_from_closes(closes: list[float]) -> pd.DataFrame:
    """2024-01-02 부터 평일마다 한 행인 합성 시세 (시가 = 종가 − 0.5, 고가 · 저가 = 종가 ± 1)."""
    dates: list[date] = []
    current = date(2024, 1, 2)
    for _ in closes:
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [c - 0.5 for c in closes],
            COL_HIGH: [c + 1.0 for c in closes],
            COL_LOW: [c - 1.0 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * len(closes),
        }
    )


def make_rising_stock_df(n_rows: int = 50, base_price: float = 100.0) -> pd.DataFrame:
    """처음 10일 base_price(이동평균 수렴) → 이후 base_price × 1.10(매수 신호)인 포트폴리오 테스트용 시세."""
    return _stock_df_from_closes([base_price] * 10 + [base_price * 1.10] * (n_rows - 10))


def make_rise_then_fall_stock_df(n_rows: int = 60, base_price: float = 100.0) -> pd.DataFrame:
    """처음 10일 base_price → 30일 base_price × 1.10(매수 신호) → 나머지 base_price × 0.85(매도 신호)인 시세."""
    return _stock_df_from_closes([base_price] * 10 + [base_price * 1.10] * 30 + [base_price * 0.85] * (n_rows - 40))


def make_portfolio_config(
    asset_paths: dict[str, tuple[Path, Path]],
    result_dir: Path,
    *,
    target_weights: dict[str, float] | None = None,
    ma_window: int = 5,
    hold_days: int = 0,
    total_capital: float = 10_000_000.0,
) -> PortfolioConfig:
    """자산 슬롯만으로 된 테스트용 PortfolioConfig.

    Args:
        asset_paths: {asset_id: (signal_path, trade_path)}
        result_dir: 결과 저장 디렉토리 (tmp_path)
        target_weights: {asset_id: weight} (기본값: 동일 비중 배분, 빠진 자산은 0.25)
        ma_window: 이동평균 기간 (슬롯마다 같은 값)
        hold_days: 유지일수 (슬롯마다 같은 값)
        total_capital: 총 초기 자본금
    """
    if target_weights is None:
        equal_weight = 1.0 / len(asset_paths)
        target_weights = {aid: equal_weight for aid in asset_paths}

    slots = tuple(
        AssetSlotConfig(
            asset_id=aid,
            signal_data_path=signal_path,
            trade_data_path=trade_path,
            target_weight=target_weights.get(aid, 0.25),
            ma_window=ma_window,
            hold_days=hold_days,
        )
        for aid, (signal_path, trade_path) in asset_paths.items()
    )

    return PortfolioConfig(
        experiment_name="test_portfolio",
        display_name="Test Portfolio",
        asset_slots=slots,
        total_capital=total_capital,
        result_dir=result_dir,
    )
