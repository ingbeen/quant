"""포트폴리오 데이터 — 자산 데이터 로딩/검증 및 에쿼티 DataFrame 빌드 함수"""

from typing import Any

import pandas as pd

from qbt.backtest.analysis import calculate_drawdown_pct_series
from qbt.backtest.constants import COL_EQUITY
from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.backtest.strategy_registry import STRATEGY_REGISTRY
from qbt.common_constants import EPSILON
from qbt.utils.data_loader import extract_overlap_period, load_stock_data


def load_and_prepare_data(
    slot: AssetSlotConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """자산 슬롯의 데이터를 로딩하고 전략별 전처리를 적용한다.

    전처리는 STRATEGY_REGISTRY의 prepare_signal_df를 경유한다.
    buffer_zone: MA 컬럼 추가, buy_and_hold: 원본 그대로 반환.

    Args:
        slot: 자산 슬롯 설정

    Returns:
        (signal_df, trade_df) — buffer_zone이면 MA 컬럼 포함
    """
    signal_df = load_stock_data(slot.signal_data_path)
    trade_df = load_stock_data(slot.trade_data_path)

    # signal/trade 데이터 경로가 다르면 교집합 기간 추출
    if slot.signal_data_path != slot.trade_data_path:
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    # MA 계산 (registry의 prepare_signal_df 경유)
    spec = STRATEGY_REGISTRY.get(slot.strategy_id)
    if spec is None:
        raise ValueError(f"미등록 strategy_id: '{slot.strategy_id}'")
    signal_df = spec.prepare_signal_df(signal_df, slot)

    return signal_df, trade_df


def validate_portfolio_config(config: PortfolioConfig) -> None:
    """포트폴리오 설정을 검증한다.

    Args:
        config: 포트폴리오 설정

    Raises:
        ValueError: 검증 실패 시
    """
    # 1. target_weight 합 ≤ 1.0
    total_weight = sum(slot.target_weight for slot in config.asset_slots)
    if total_weight > 1.0 + EPSILON:
        raise ValueError(
            f"target_weight 합이 1.0을 초과합니다: {total_weight:.4f} " f"(자산: {[s.asset_id for s in config.asset_slots]})"
        )

    # 2. target_weight ≥ 0
    for slot in config.asset_slots:
        if slot.target_weight < 0:
            raise ValueError(
                f"target_weight는 0 이상이어야 합니다: asset_id={slot.asset_id}, " f"target_weight={slot.target_weight}"
            )

    # 3. asset_id 중복 없음
    asset_ids = [slot.asset_id for slot in config.asset_slots]
    if len(asset_ids) != len(set(asset_ids)):
        seen: set[str] = set()
        duplicates: list[str] = []
        for aid in asset_ids:
            if aid in seen:
                duplicates.append(aid)
            else:
                seen.add(aid)
        raise ValueError(f"asset_id 중복이 있습니다: {duplicates}")


def build_combined_equity(
    equity_rows: list[dict[str, Any]],
    initial_capital: float,
) -> pd.DataFrame:
    """에쿼티 행 목록을 DataFrame으로 변환하고 drawdown을 계산한다."""
    equity_df = pd.DataFrame(equity_rows)

    # drawdown 계산 (analysis.py의 공용 함수 사용 — 방어 로직 통일)
    equity_df["drawdown_pct"] = calculate_drawdown_pct_series(equity_df[COL_EQUITY])

    return equity_df
