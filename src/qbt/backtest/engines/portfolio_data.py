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
    """에쿼티 행 목록을 DataFrame으로 변환하고 파생 뷰 컬럼을 계산한다.

    추가하는 파생 컬럼:
        - drawdown_pct: equity 곡선 기준 드로우다운(%)
        - {asset_id}_current_price: shares > 0이면 value/shares, 아니면 0.0
        - {asset_id}_return_pct: avg_price > 0 and shares > 0이면 (current_price/avg_price - 1)*100, 아니면 0.0
        - total_pnl: equity - initial_capital
        - total_return_pct: total_pnl/initial_capital * 100

    이 컬럼들은 보유 현황·수익률 표시 용도이며, 단일 진실 공급원(SSoT) 원칙에 따라
    엔진에서 한 번만 계산한다 (대시보드 등 CLI 계층에서 동일 계산 중복 금지).
    """
    if initial_capital <= 0:
        # 입력 검증: PortfolioConfig.total_capital은 양수여야 한다.
        raise ValueError(f"initial_capital은 양수여야 합니다: {initial_capital}")

    equity_df = pd.DataFrame(equity_rows)

    # drawdown 계산 (analysis.py의 공용 함수 사용 — 방어 로직 통일)
    equity_df["drawdown_pct"] = calculate_drawdown_pct_series(equity_df[COL_EQUITY])

    # 파생 뷰 컬럼 계산
    _attach_holding_view_columns(equity_df, initial_capital)

    return equity_df


def _attach_holding_view_columns(equity_df: pd.DataFrame, initial_capital: float) -> None:
    """equity_df에 보유 현황 파생 컬럼을 in-place로 추가한다.

    자산 식별: `{asset_id}_shares` 패턴의 컬럼에서 asset_id를 추론한다.
    각 자산에 대해 current_price, return_pct를 계산하고,
    포트폴리오 단위로 total_pnl, total_return_pct를 계산한다.

    Args:
        equity_df: equity_rows로부터 만든 DataFrame (in-place로 컬럼 추가)
        initial_capital: 초기 자본금 (양수)
    """
    # 1. 자산 식별: {asset_id}_shares 컬럼에서 asset_id 추출
    suffix = "_shares"
    asset_ids = [col[: -len(suffix)] for col in equity_df.columns if col.endswith(suffix)]

    # 2. 자산별 current_price / return_pct
    for asset_id in asset_ids:
        shares_col = f"{asset_id}_shares"
        value_col = f"{asset_id}_value"
        avg_price_col = f"{asset_id}_avg_price"
        current_price_col = f"{asset_id}_current_price"
        return_pct_col = f"{asset_id}_return_pct"

        if value_col not in equity_df.columns or avg_price_col not in equity_df.columns:
            # 입력 row가 표준 포맷이 아니면 안전하게 0 처리 — 정상 흐름에서는 도달 불가
            equity_df[current_price_col] = 0.0
            equity_df[return_pct_col] = 0.0
            continue

        shares_series = equity_df[shares_col]
        value_series = equity_df[value_col]
        avg_price_series = equity_df[avg_price_col]

        has_position = shares_series > 0
        # current_price = value / shares (보유 시), 그 외 0.0
        current_price_series = pd.Series(0.0, index=equity_df.index)
        current_price_series.loc[has_position] = value_series.loc[has_position] / shares_series.loc[has_position]
        equity_df[current_price_col] = current_price_series

        # return_pct = (current_price / avg_price - 1) * 100 (보유 + 유효 평균가), 그 외 0.0
        valid_for_return = has_position & (avg_price_series > 0)
        return_pct_series = pd.Series(0.0, index=equity_df.index)
        return_pct_series.loc[valid_for_return] = (
            current_price_series.loc[valid_for_return] / avg_price_series.loc[valid_for_return] - 1.0
        ) * 100.0
        equity_df[return_pct_col] = return_pct_series

    # 3. 포트폴리오 누적 손익
    equity_df["total_pnl"] = equity_df[COL_EQUITY] - initial_capital
    equity_df["total_return_pct"] = (equity_df["total_pnl"] / initial_capital) * 100.0
