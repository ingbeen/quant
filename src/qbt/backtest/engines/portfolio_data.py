"""포트폴리오 데이터 — 자산 데이터 로딩/검증 및 에쿼티 DataFrame 빌드 함수"""

from pathlib import Path
from typing import Any

import pandas as pd

from qbt.backtest.allocator_registry import ALLOCATOR_REGISTRY
from qbt.backtest.analysis import calculate_drawdown_pct_series
from qbt.backtest.constants import COL_EQUITY
from qbt.backtest.portfolio_types import (
    ASSET_COL_SUFFIX_SHARES,
    POSITION_KEY_SEPARATOR,
    AllocatorMethodConfig,
    AssetSlotConfig,
    MethodConfig,
    PortfolioConfig,
    SlotMethodConfig,
    asset_shares_col,
    asset_value_col,
    resolve_methods,
)
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


def _find_duplicates(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in ids:
        if item in seen:
            duplicates.append(item)
        else:
            seen.add(item)
    return duplicates


def _validate_slots(asset_slots: tuple[AssetSlotConfig, ...]) -> None:
    """슬롯 묶음(매매법 하나 안)을 검증한다: 슬롯 1개 이상, target_weight 합 ≤ 1.0, 각 ≥ 0, asset_id 중복 없음."""
    if not asset_slots:
        raise ValueError("슬롯이 없는 매매법입니다. asset_slots 에 자산을 1개 이상 넣으세요")
    total_weight = sum(slot.target_weight for slot in asset_slots)
    if total_weight > 1.0 + EPSILON:
        raise ValueError(
            f"target_weight 합이 1.0을 초과합니다: {total_weight:.4f} " f"(자산: {[s.asset_id for s in asset_slots]})"
        )

    for slot in asset_slots:
        if slot.target_weight < 0:
            raise ValueError(
                f"target_weight는 0 이상이어야 합니다: asset_id={slot.asset_id}, " f"target_weight={slot.target_weight}"
            )

    duplicates = _find_duplicates([slot.asset_id for slot in asset_slots])
    if duplicates:
        raise ValueError(f"asset_id 중복이 있습니다: {duplicates}")


def _validate_allocator_method(method: AllocatorMethodConfig) -> None:
    """비중이 바뀌는 매매법을 검증한다: 배분 규칙 등록, 자산 id 중복 없음, 신호용 시세 id 가 자산 id 와 겹치지 않음."""
    if method.allocator_id not in ALLOCATOR_REGISTRY:
        raise ValueError(
            f"등록되지 않은 allocator_id 입니다: '{method.allocator_id}' (method_id={method.method_id}). "
            f"allocator_registry.ALLOCATOR_REGISTRY 에 등록된 값: {sorted(ALLOCATOR_REGISTRY)}"
        )
    asset_ids = [asset.asset_id for asset in method.assets]
    if not asset_ids:
        raise ValueError(f"매매할 자산이 없습니다: method_id={method.method_id}. assets 에 AllocationAssetConfig 를 1개 이상 넣으세요")
    duplicates = _find_duplicates(asset_ids)
    if duplicates:
        raise ValueError(f"asset_id 중복이 있습니다: {duplicates} (method_id={method.method_id})")
    series_ids = [series.series_id for series in method.signal_series]
    collisions = sorted((set(series_ids) & set(asset_ids)) | set(_find_duplicates(series_ids)))
    if collisions:
        raise ValueError(
            f"신호용 시세 series_id 가 자산 id 나 다른 series_id 와 겹칩니다: {collisions} "
            f"(method_id={method.method_id}). 배분 규칙의 입력 키가 겹치므로 다른 이름을 쓰세요"
        )


def _method_trade_paths(method: MethodConfig) -> dict[str, Path]:
    if isinstance(method, SlotMethodConfig):
        return {slot.asset_id: slot.trade_data_path for slot in method.asset_slots}
    return {asset.asset_id: asset.trade_data_path for asset in method.assets}


def validate_portfolio_config(config: PortfolioConfig) -> None:
    """포트폴리오 설정을 검증한다.

    Args:
        config: 포트폴리오 설정

    Raises:
        ValueError: 검증 실패 시
    """
    # 1. asset_slots(매매법 하나 줄임 표기)와 methods 중 정확히 하나
    if bool(config.asset_slots) == bool(config.methods):
        raise ValueError(
            "asset_slots 와 methods 중 정확히 하나를 채워야 합니다 "
            f"(experiment_name={config.experiment_name}, asset_slots {len(config.asset_slots)}개, "
            f"methods {len(config.methods)}개). 매매법이 하나면 asset_slots, 여럿이면 methods 를 쓰세요"
        )

    methods = resolve_methods(config)
    multi_method = len(methods) > 1

    # 2. 매매법 몫: 각 > 0, 합 1.0
    for method in methods:
        if not method.target_weight > 0:
            raise ValueError(
                f"매매법 몫(target_weight)은 0 보다 커야 합니다: method_id={method.method_id}, "
                f"target_weight={method.target_weight}"
            )
    total_share = sum(method.target_weight for method in methods)
    if not abs(total_share - 1.0) <= EPSILON:
        raise ValueError(
            f"매매법 몫(target_weight)의 합이 1.0 이어야 합니다: {total_share:.6f} " f"(매매법: {[m.method_id for m in methods]})"
        )

    # 3. method_id 중복 없음
    duplicates = _find_duplicates([method.method_id for method in methods])
    if duplicates:
        raise ValueError(f"method_id 중복이 있습니다: {duplicates}. 매매법마다 다른 method_id 를 쓰세요")

    # 4. 매매법별 검증 + 자산 키 구분자 금지 + 같은 자산은 같은 매매 데이터
    trade_path_of_asset: dict[str, Path] = {}
    for method in methods:
        if isinstance(method, SlotMethodConfig):
            _validate_slots(method.asset_slots)
        else:
            _validate_allocator_method(method)

        trade_paths = _method_trade_paths(method)
        if multi_method:
            for item_id in [method.method_id, *trade_paths]:
                if POSITION_KEY_SEPARATOR in item_id:
                    raise ValueError(
                        f"매매법이 여럿인 실험에서는 id 에 '{POSITION_KEY_SEPARATOR}' 를 쓸 수 없습니다 "
                        f"(결과 키 「매매법{POSITION_KEY_SEPARATOR}자산」의 구분자): '{item_id}' (method_id={method.method_id})"
                    )
        for asset_id, trade_path in trade_paths.items():
            known = trade_path_of_asset.setdefault(asset_id, trade_path)
            if known != trade_path:
                raise ValueError(
                    f"같은 자산 id '{asset_id}' 를 매매법들이 다른 매매 데이터 경로로 듭니다: {known} vs {trade_path}. "
                    f"상계는 자산 id 단위라 같은 종목은 같은 매매 데이터를 써야 합니다"
                )


def build_combined_equity(
    equity_rows: list[dict[str, Any]],
    initial_capital: float,
) -> pd.DataFrame:
    """에쿼티 행 목록을 DataFrame으로 변환하고 파생 뷰 컬럼을 계산한다.

    추가하는 파생 컬럼:
        - drawdown_pct: equity 곡선 기준 드로우다운(%)
        - {asset_id}_current_price: shares > 0이면 value/shares, 아니면 0.0
        - {asset_id}_return_pct: avg_price > 0 and shares > 0이면 (current_price/avg_price - 1)*100, 아니면 0.0
        - {asset_id}_contribution: realized_pnl + unrealized_pnl (자산별 누적 기여 손익)
        - total_pnl: equity - initial_capital
        - total_return_pct: total_pnl/initial_capital * 100

    이 컬럼들은 보유 현황·수익률·기여도 표시 용도이며, 단일 진실 공급원(SSoT) 원칙에 따라
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
    각 자산에 대해 current_price, return_pct, contribution을 계산하고,
    포트폴리오 단위로 total_pnl, total_return_pct를 계산한다.

    Args:
        equity_df: equity_rows로부터 만든 DataFrame (in-place로 컬럼 추가)
        initial_capital: 초기 자본금 (양수)
    """
    # 1. 자산 식별: {asset_id}_shares 컬럼에서 asset_id 추출
    asset_ids = [
        col[: -len(ASSET_COL_SUFFIX_SHARES)] for col in equity_df.columns if col.endswith(ASSET_COL_SUFFIX_SHARES)
    ]

    # 2. 자산별 current_price / return_pct / contribution
    for asset_id in asset_ids:
        shares_col = asset_shares_col(asset_id)
        value_col = asset_value_col(asset_id)
        avg_price_col = f"{asset_id}_avg_price"
        realized_pnl_col = f"{asset_id}_realized_pnl"
        unrealized_pnl_col = f"{asset_id}_unrealized_pnl"
        current_price_col = f"{asset_id}_current_price"
        return_pct_col = f"{asset_id}_return_pct"
        contribution_col = f"{asset_id}_contribution"

        if value_col not in equity_df.columns or avg_price_col not in equity_df.columns:
            # 입력 row가 표준 포맷이 아니면 안전하게 0 처리 — 정상 흐름에서는 도달 불가
            equity_df[current_price_col] = 0.0
            equity_df[return_pct_col] = 0.0
            equity_df[contribution_col] = 0.0
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

        # contribution = realized_pnl + unrealized_pnl (자산별 누적 기여 손익)
        # portfolio_engine이 매 거래일 두 컬럼을 모두 채워주므로 부재는 내부 불변조건 위반.
        if realized_pnl_col not in equity_df.columns or unrealized_pnl_col not in equity_df.columns:
            raise RuntimeError(
                f"내부 불변조건 위반: {realized_pnl_col}/{unrealized_pnl_col} 컬럼이 누락되었습니다 "
                f"(asset_id={asset_id}). portfolio_engine 출력 스키마를 확인하세요."
            )
        equity_df[contribution_col] = equity_df[realized_pnl_col] + equity_df[unrealized_pnl_col]

    # 3. 포트폴리오 누적 손익
    equity_df["total_pnl"] = equity_df[COL_EQUITY] - initial_capital
    equity_df["total_return_pct"] = (equity_df["total_pnl"] / initial_capital) * 100.0
