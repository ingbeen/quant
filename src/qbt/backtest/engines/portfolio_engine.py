"""포트폴리오 백테스트 엔진

복수 자산의 독립 시그널 + 목표 비중 배분 + 이중 트리거 리밸런싱을 처리한다.

주요 설계 결정:
- 시그널: signal_data_path 기준 EMA-200 버퍼존 (자산별 독립)
- TQQQ/QQQ 시그널 공유: signal_data_path를 동일하게 설정하면 자동으로 공유
- 리밸런싱: 이중 트리거 체계
    - 월 첫 거래일: 편차 10% 초과 시 (MONTHLY_REBALANCE_THRESHOLD_RATE)
    - 매일: 편차 20% 초과 시 긴급 (DAILY_REBALANCE_THRESHOLD_RATE)
- 부분 매도: 리밸런싱 시 초과분(대금 기준)만 매도, 신호 기반 매도는 전량 유지
- 현금 부족: scale_factor 비례 배분
- 전략 주입: SignalStrategy Protocol을 통해 전략을 의존성 주입 방식으로 사용
- 결과: PortfolioResult (equity_df, trades_df, per_asset, summary)
"""

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average, calculate_summary
from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.backtest.portfolio_types import (
    AssetSlotConfig,
    PortfolioAssetResult,
    PortfolioConfig,
    PortfolioResult,
)
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldStrategy
from qbt.backtest.strategies.strategy_common import SignalStrategy
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN, EPSILON
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)

# 월 첫 거래일 리밸런싱 임계값: |actual/target - 1| > 0.10이면 트리거 (정기 리밸런싱)
MONTHLY_REBALANCE_THRESHOLD_RATE: float = 0.10

# 매일 긴급 리밸런싱 임계값: |actual/target - 1| > 0.20이면 트리거 (급격한 편차 대응)
DAILY_REBALANCE_THRESHOLD_RATE: float = 0.20


# ============================================================================
# 내부 데이터클래스 (private)
# ============================================================================


@dataclass
class _PortfolioPendingOrder:
    """포트폴리오 전략 전용 예약 주문.

    engine_common의 PendingOrder와 달리 capital, rebalance_sell_amount, is_rebalance 필드를 포함한다.
    매수 시 capital에 투자 자본금을 저장하고, rebalance_sell_amount는 0.0.
    리밸런싱 매도 시 rebalance_sell_amount에 초과분 대금을 저장 (> 0.0 = 부분 매도).
    신호 기반 매도 시 rebalance_sell_amount = 0.0 (전량 매도).
    리밸런싱 추가매수 시 is_rebalance=True: position > 0인 자산에도 체결을 허용한다.
    """

    order_type: Literal["buy", "sell"]  # 주문 유형
    signal_date: date  # 신호 발생 날짜
    capital: float  # 매수 자본 (매도 시 0.0)
    rebalance_sell_amount: float = 0.0  # 리밸런싱 부분 매도 대금 (0.0 = 전량 매도)
    is_rebalance: bool = False  # 리밸런싱 추가매수 여부 (True이면 position > 0에도 체결)


@dataclass
class _AssetState:
    """자산별 런타임 상태."""

    position: int  # 보유 수량
    signal_state: Literal["buy", "sell"]  # 현재 시그널 상태
    pending_order: _PortfolioPendingOrder | None  # 예약 주문 (None = 없음)


# ============================================================================
# 전략 팩토리
# ============================================================================


def _create_strategy_for_slot(slot: AssetSlotConfig) -> SignalStrategy:
    """strategy_type 기반으로 전략 객체를 생성한다.

    Args:
        slot: 자산 슬롯 설정

    Returns:
        SignalStrategy를 구현한 전략 객체

    Raises:
        ValueError: 미등록 strategy_type인 경우
    """
    if slot.strategy_type == "buffer_zone":
        return BufferZoneStrategy(
            ma_col=f"ma_{slot.ma_window}",
            buy_buffer_pct=slot.buy_buffer_zone_pct,
            sell_buffer_pct=slot.sell_buffer_zone_pct,
            hold_days=slot.hold_days,
            ma_type=slot.ma_type,
        )
    elif slot.strategy_type == "buy_and_hold":
        return BuyAndHoldStrategy()
    raise ValueError(f"미등록 strategy_type: '{slot.strategy_type}'. " f"사용 가능: 'buffer_zone', 'buy_and_hold'")


# ============================================================================
# 공개 헬퍼 함수 (테스트 대상)
# ============================================================================


def _compute_portfolio_equity(
    shared_cash: float,
    asset_positions: dict[str, int],
    asset_closes: dict[str, float],
) -> float:
    """포트폴리오 에쿼티를 계산한다.

    Args:
        shared_cash: 미투자 현금
        asset_positions: {asset_id: 보유수량}
        asset_closes: {asset_id: 종가}

    Returns:
        equity = shared_cash + Σ(position × close)
    """
    total_value = sum(asset_positions[aid] * asset_closes[aid] for aid in asset_positions if aid in asset_closes)
    return shared_cash + total_value


def _is_first_trading_day_of_month(trade_dates: list[date], i: int) -> bool:
    """월 첫 거래일 여부를 판정한다.

    Args:
        trade_dates: 전체 거래일 목록
        i: 현재 인덱스 (0-based)

    Returns:
        True이면 이전 거래일과 월이 다름 (= 월 첫 거래일)
        False이면 i=0이거나 동일 월
    """
    if i <= 0:
        return False
    return trade_dates[i].month != trade_dates[i - 1].month


def _check_rebalancing_needed(
    asset_states: dict[str, _AssetState],
    equity_vals: dict[str, float],
    total_equity: float,
    config: PortfolioConfig,
    threshold: float,
) -> bool:
    """리밸런싱 필요 여부를 판정한다.

    매수 시그널 자산 중 하나라도 |actual/target - 1| > threshold이면 True.
    target=0인 자산은 건너뛴다.

    Args:
        asset_states: {asset_id: _AssetState}
        equity_vals: {asset_id: 현재 평가액}
        total_equity: 총 에쿼티
        config: 포트폴리오 설정 (asset_slots의 target_weight 참조용)
        threshold: 리밸런싱 임계값 (호출자가 명시적으로 전달).
            월 첫날: MONTHLY_REBALANCE_THRESHOLD_RATE
            매일: DAILY_REBALANCE_THRESHOLD_RATE

    Returns:
        True이면 리밸런싱 실행 필요
    """
    if total_equity < EPSILON:
        return False

    slot_dict = {slot.asset_id: slot for slot in config.asset_slots}

    for asset_id, state in asset_states.items():
        if state.signal_state != "buy":
            continue
        slot = slot_dict.get(asset_id)
        if slot is None or slot.target_weight == 0:
            continue

        actual = equity_vals.get(asset_id, 0.0) / total_equity
        deviation = abs(actual / slot.target_weight - 1.0)
        if deviation > threshold:
            return True

    return False


def _execute_rebalancing(
    asset_states: dict[str, _AssetState],
    equity_vals: dict[str, float],
    config: PortfolioConfig,
    shared_cash: float,
    current_date: date,
) -> None:
    """리밸런싱 pending_order를 생성한다 (in-place 수정).

    1. 총 에쿼티 = shared_cash + 전 자산 평가액
    2. 매수 시그널 자산별 target_amount 계산
    3. 초과 자산: 매도 pending_order 생성
    4. 미달 자산: 매수 pending_order 생성 (현금 부족 시 scale_factor 적용)

    매도 예상 대금을 매수 자본에 반영하여 shared_cash=0이어도 동작한다.

    Args:
        asset_states: {asset_id: _AssetState} — in-place 수정
        equity_vals: {asset_id: 현재 평가액}
        config: 포트폴리오 설정
        shared_cash: 현재 미투자 현금
        current_date: pending_order 생성 날짜
    """
    total_equity = shared_cash + sum(equity_vals.values())
    slot_dict = {slot.asset_id: slot for slot in config.asset_slots}

    # 매수 시그널 자산만 대상
    buy_signal_assets = {aid for aid, st in asset_states.items() if st.signal_state == "buy"}

    # 1. 매도 대상 (초과 자산) 판별
    sell_orders: dict[str, float] = {}
    for asset_id in buy_signal_assets:
        slot = slot_dict.get(asset_id)
        if slot is None:
            continue
        target_amount = total_equity * slot.target_weight
        delta = target_amount - equity_vals.get(asset_id, 0.0)
        if delta < 0:  # 초과 → 매도
            sell_orders[asset_id] = abs(delta)

    estimated_sell_proceeds = sum(sell_orders.values())

    # 2. 매수 대상 (미달 자산) 판별
    buy_orders: dict[str, float] = {}
    for asset_id in buy_signal_assets:
        slot = slot_dict.get(asset_id)
        if slot is None:
            continue
        target_amount = total_equity * slot.target_weight
        delta = target_amount - equity_vals.get(asset_id, 0.0)
        if delta > 0:  # 미달 → 매수
            buy_orders[asset_id] = delta

    total_buy_needed = sum(buy_orders.values())
    available_cash = shared_cash + estimated_sell_proceeds

    # 3. 현금 부족 시 scale_factor 비례 축소
    if total_buy_needed > available_cash and total_buy_needed > EPSILON:
        scale_factor = available_cash / total_buy_needed
        buy_orders = {aid: amt * scale_factor for aid, amt in buy_orders.items()}

    # 4. pending_order 생성
    for asset_id, excess_value in sell_orders.items():
        # 이미 pending_order가 있으면 덮어쓰지 않음 (시그널 pending_order 우선)
        if asset_states[asset_id].pending_order is None:
            asset_states[asset_id].pending_order = _PortfolioPendingOrder(
                order_type="sell",
                signal_date=current_date,
                capital=0.0,
                rebalance_sell_amount=excess_value,  # 부분 매도: 초과분 대금 기준
            )

    for asset_id, capital in buy_orders.items():
        if asset_states[asset_id].pending_order is None:
            asset_states[asset_id].pending_order = _PortfolioPendingOrder(
                order_type="buy",
                signal_date=current_date,
                capital=capital,
                is_rebalance=True,  # 리밸런싱 추가매수: position > 0에도 체결 허용
            )


# ============================================================================
# 내부 헬퍼 함수
# ============================================================================


def _load_and_prepare_data(
    slot: AssetSlotConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """자산 슬롯의 데이터를 로딩하고 MA를 계산한다.

    buffer_zone 슬롯: 슬롯별 MA 파라미터(ma_window, ma_type)로 이동평균 계산.
    buy_and_hold 슬롯: MA 계산 생략 (불필요).

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

    # MA 계산 (buffer_zone 슬롯만)
    if slot.strategy_type == "buffer_zone":
        signal_df = add_single_moving_average(signal_df, slot.ma_window, slot.ma_type)

    return signal_df, trade_df


def _validate_portfolio_config(config: PortfolioConfig) -> None:
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
        seen = set()
        duplicates = [aid for aid in asset_ids if aid in seen or seen.add(aid)]  # type: ignore[func-returns-value]
        raise ValueError(f"asset_id 중복이 있습니다: {duplicates}")


def _build_combined_equity(
    equity_rows: list[dict[str, Any]],
    initial_capital: float,
) -> pd.DataFrame:
    """에쿼티 행 목록을 DataFrame으로 변환하고 drawdown을 계산한다."""
    equity_df = pd.DataFrame(equity_rows)

    # drawdown 계산
    peak = equity_df["equity"].cummax()
    equity_df["drawdown_pct"] = (equity_df["equity"] - peak) / (peak + EPSILON) * 100.0

    return equity_df


# ============================================================================
# 공개 API
# ============================================================================


def compute_portfolio_effective_start_date(config: PortfolioConfig) -> date:
    """포트폴리오 실험의 유효 시작일을 계산한다.

    전 자산 데이터의 날짜 교집합을 구하고 buffer_zone 슬롯의 MA 워밍업 완료 이후
    첫 날짜를 반환한다. buy_and_hold 슬롯은 MA 워밍업이 없으므로 valid_start 계산에서 제외.
    여러 실험을 동일 기간으로 정렬할 때 글로벌 시작일을 결정하는 데 사용한다.

    Args:
        config: 포트폴리오 실험 설정

    Returns:
        MA 워밍업 완료 이후 첫 유효 거래일 (date 객체)

    Raises:
        ValueError: 공통 기간 없음 또는 MA 컬럼 누락 시
    """
    # 1. 자산별 데이터 로딩 + MA 계산 (signal_data_path 기준 캐시, 슬롯별 MA 파라미터 사용)
    signal_cache: dict[str, pd.DataFrame] = {}
    asset_trade_dfs: dict[str, pd.DataFrame] = {}
    asset_signal_dfs: dict[str, pd.DataFrame] = {}
    slot_dict = {slot.asset_id: slot for slot in config.asset_slots}

    for slot in config.asset_slots:
        signal_key = f"{slot.signal_data_path}::{slot.strategy_type}::{slot.ma_window}::{slot.ma_type}"
        if signal_key not in signal_cache:
            signal_df_raw, trade_df = _load_and_prepare_data(slot)
            signal_cache[signal_key] = signal_df_raw
        else:
            signal_df_raw = signal_cache[signal_key]
            trade_df = load_stock_data(slot.trade_data_path)
            if slot.signal_data_path != slot.trade_data_path:
                signal_df_raw, trade_df = extract_overlap_period(signal_df_raw.copy(), trade_df)

        asset_signal_dfs[slot.asset_id] = signal_df_raw
        asset_trade_dfs[slot.asset_id] = trade_df

    # 2. 공통 기간 추출 (전 자산 trade_df의 날짜 교집합)
    date_sets = [set(df[COL_DATE]) for df in asset_trade_dfs.values()]
    common_dates_set: set[date] = date_sets[0]
    for ds in date_sets[1:]:
        common_dates_set &= ds

    if not common_dates_set:
        raise ValueError("전 자산의 공통 거래 기간이 없습니다.")

    # 공통 기간으로 필터링
    for asset_id in asset_signal_dfs:
        signal_df = asset_signal_dfs[asset_id]
        trade_df = asset_trade_dfs[asset_id]

        mask_s = pd.Series(signal_df[COL_DATE]).isin(common_dates_set)
        mask_t = pd.Series(trade_df[COL_DATE]).isin(common_dates_set)

        asset_signal_dfs[asset_id] = signal_df[mask_s.values].reset_index(drop=True)
        asset_trade_dfs[asset_id] = trade_df[mask_t.values].reset_index(drop=True)

    # 3. MA 유효 구간 필터링 (buffer_zone 슬롯만 대상, buy_and_hold는 MA 없음)
    valid_start_indices: list[int] = []
    for asset_id in asset_signal_dfs:
        slot = slot_dict[asset_id]
        if slot.strategy_type != "buffer_zone":
            continue
        ma_col = f"ma_{slot.ma_window}"
        sdf = asset_signal_dfs[asset_id]
        if ma_col not in sdf.columns:
            raise ValueError(f"MA 컬럼 누락: {ma_col} (asset_id={asset_id})")
        valid_mask = sdf[ma_col].notna()
        if valid_mask.any():
            valid_start_indices.append(int(valid_mask.idxmax()))
        else:
            valid_start_indices.append(len(sdf))

    valid_start = max(valid_start_indices) if valid_start_indices else 0

    # 4. 유효 시작 인덱스의 첫 trade_df 날짜 반환
    first_trade_df = next(iter(asset_trade_dfs.values()))
    first_trade_df_filtered = first_trade_df.iloc[valid_start:].reset_index(drop=True)

    if len(first_trade_df_filtered) < 1:
        raise ValueError("유효 데이터 부족: MA 워밍업 후 데이터가 없습니다.")

    return date(
        first_trade_df_filtered[COL_DATE].iloc[0].year,
        first_trade_df_filtered[COL_DATE].iloc[0].month,
        first_trade_df_filtered[COL_DATE].iloc[0].day,
    )


def run_portfolio_backtest(config: PortfolioConfig, start_date: date | None = None) -> PortfolioResult:
    """포트폴리오 백테스트를 실행한다.

    복수 자산의 독립 시그널 + 목표 비중 배분 + 월간 리밸런싱을 수행한다.
    SignalStrategy Protocol을 통해 전략을 의존성 주입 방식으로 사용한다.

    Args:
        config: 포트폴리오 실험 설정
        start_date: 백테스트 시작일 하한 (None이면 MA 워밍업 완료 시점부터 자동 결정).
            여러 실험을 동일 기간으로 정렬할 때 global_start_date를 전달한다.
            MA 워밍업 필터링 이후에 추가로 적용되므로 실제 시작일은
            max(valid_start 날짜, start_date)가 된다.

    Returns:
        PortfolioResult (equity_df, trades_df, summary, per_asset 포함)

    Raises:
        ValueError: 설정 검증 실패 또는 공통 기간 없음
    """
    logger.debug(f"포트폴리오 백테스트 시작: {config.experiment_name}")

    # 1. 설정 검증
    _validate_portfolio_config(config)

    slot_dict = {slot.asset_id: slot for slot in config.asset_slots}

    # 2. 자산별 데이터 로딩 + MA 계산 (슬롯별 MA 파라미터 사용)
    # signal_data_path 기준으로 중복 로딩 방지 (캐시)
    signal_cache: dict[str, pd.DataFrame] = {}
    asset_signal_dfs: dict[str, pd.DataFrame] = {}
    asset_trade_dfs: dict[str, pd.DataFrame] = {}

    for slot in config.asset_slots:
        signal_key = f"{slot.signal_data_path}::{slot.strategy_type}::{slot.ma_window}::{slot.ma_type}"
        if signal_key not in signal_cache:
            signal_df_raw, trade_df = _load_and_prepare_data(slot)
            signal_cache[signal_key] = signal_df_raw
        else:
            # 같은 시그널 경로 → 캐시 재사용
            signal_df_raw = signal_cache[signal_key]
            trade_df = load_stock_data(slot.trade_data_path)
            if slot.signal_data_path != slot.trade_data_path:
                signal_df_raw, trade_df = extract_overlap_period(signal_df_raw.copy(), trade_df)

        asset_signal_dfs[slot.asset_id] = signal_df_raw
        asset_trade_dfs[slot.asset_id] = trade_df

    # 3. 공통 기간 추출 (전 자산 trade_df의 날짜 교집합)
    date_sets = [set(df[COL_DATE]) for df in asset_trade_dfs.values()]
    common_dates_set: set[date] = date_sets[0]
    for ds in date_sets[1:]:
        common_dates_set &= ds

    if not common_dates_set:
        raise ValueError("전 자산의 공통 거래 기간이 없습니다.")

    # 공통 기간으로 필터링
    for asset_id in asset_signal_dfs:
        signal_df = asset_signal_dfs[asset_id]
        trade_df = asset_trade_dfs[asset_id]

        mask_s = pd.Series(signal_df[COL_DATE]).isin(common_dates_set)
        mask_t = pd.Series(trade_df[COL_DATE]).isin(common_dates_set)

        asset_signal_dfs[asset_id] = signal_df[mask_s.values].reset_index(drop=True)
        asset_trade_dfs[asset_id] = trade_df[mask_t.values].reset_index(drop=True)

    # MA 유효 구간 필터링 (buffer_zone 슬롯의 MA NaN 기준만, buy_and_hold 슬롯 제외)
    valid_start_indices: list[int] = []
    for asset_id in asset_signal_dfs:
        slot = slot_dict[asset_id]
        if slot.strategy_type != "buffer_zone":
            continue
        ma_col = f"ma_{slot.ma_window}"
        sdf = asset_signal_dfs[asset_id]
        if ma_col not in sdf.columns:
            raise ValueError(f"MA 컬럼 누락: {ma_col} (asset_id={asset_id})")
        valid_mask = sdf[ma_col].notna()
        if valid_mask.any():
            valid_start_indices.append(int(valid_mask.idxmax()))
        else:
            valid_start_indices.append(len(sdf))

    valid_start = max(valid_start_indices) if valid_start_indices else 0

    for asset_id in asset_signal_dfs:
        asset_signal_dfs[asset_id] = asset_signal_dfs[asset_id].iloc[valid_start:].reset_index(drop=True)
        asset_trade_dfs[asset_id] = asset_trade_dfs[asset_id].iloc[valid_start:].reset_index(drop=True)

    # start_date 필터: MA 워밍업 완료 이후 추가로 시작일 하한 적용
    # 여러 실험의 공통 기간 정렬 시 사용 (global_start_date 전달)
    if start_date is not None:
        for asset_id in asset_signal_dfs:
            sdf = asset_signal_dfs[asset_id]
            tdf = asset_trade_dfs[asset_id]
            mask_s = pd.Series(sdf[COL_DATE]) >= start_date
            mask_t = pd.Series(tdf[COL_DATE]) >= start_date
            asset_signal_dfs[asset_id] = sdf[mask_s.values].reset_index(drop=True)
            asset_trade_dfs[asset_id] = tdf[mask_t.values].reset_index(drop=True)

    n = len(next(iter(asset_trade_dfs.values())))
    if n < 2:
        raise ValueError(f"유효 데이터 부족: {n}행 (최소 2행 필요)")

    trade_dates = list(next(iter(asset_trade_dfs.values()))[COL_DATE])

    # 4. 전략 객체 생성 (자산별 strategy_type 기반 팩토리, 슬롯별 파라미터 사용)
    strategies: dict[str, SignalStrategy] = {
        slot.asset_id: _create_strategy_for_slot(slot) for slot in config.asset_slots
    }

    # 5. 자산별 상태 초기화 (모든 자산 "sell"로 시작)
    asset_states: dict[str, _AssetState] = {
        slot.asset_id: _AssetState(
            position=0,
            signal_state="sell",
            pending_order=None,
        )
        for slot in config.asset_slots
    }

    shared_cash = config.total_capital

    # 자산별 진입 정보 (entry_price, entry_date)
    entry_prices: dict[str, float] = {slot.asset_id: 0.0 for slot in config.asset_slots}
    entry_dates: dict[str, date | None] = {slot.asset_id: None for slot in config.asset_slots}
    entry_hold_days: dict[str, int] = {slot.asset_id: 0 for slot in config.asset_slots}

    # 거래 기록 및 에쿼티 기록
    all_trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []

    # 6. 메인 루프: 전일 체결 → 당일 에쿼티 → 당일 시그널 → 리밸런싱 판정
    # 신호와 체결을 하루씩 분리(Lookahead 방지): i일 종가 시그널 → i+1일 시가 체결
    # Day 0: 전일 pending 없음 → 에쿼티 초기 기록 → 최초 시그널 판정만 수행
    for i in range(0, n):
        current_date = trade_dates[i]
        rebalanced_today = False

        # Step A: 매도 선행 체결 (trade_df[i].Open 기준)
        # 매도를 먼저 처리해야 확보된 현금을 당일 매수에 즉시 활용할 수 있다 (shared_cash 재사용)
        for asset_id, state in asset_states.items():
            if state.pending_order is None or state.pending_order.order_type != "sell":
                continue
            if state.position <= 0:
                state.pending_order = None
                continue

            trade_df = asset_trade_dfs[asset_id]
            open_price = float(trade_df.iloc[i][COL_OPEN])
            order = state.pending_order
            sell_price = open_price * (1.0 - SLIPPAGE_RATE)

            if order.rebalance_sell_amount > 0.0:
                # 부분 매도 (리밸런싱): 초과 대금 기준으로 수량 계산 (내림)
                shares_to_sell = int(order.rebalance_sell_amount / sell_price)
                shares_sold = min(shares_to_sell, state.position)
            else:
                # 전량 매도 (신호 기반)
                shares_sold = state.position

            if shares_sold > 0:
                sell_amount = shares_sold * sell_price
                shared_cash += sell_amount

                e_date = entry_dates.get(asset_id)
                e_price = entry_prices.get(asset_id, 0.0)

                trade_record: dict[str, Any] = {
                    "entry_date": e_date,
                    "exit_date": current_date,
                    "entry_price": e_price,
                    "exit_price": sell_price,
                    "shares": shares_sold,
                    "pnl": (sell_price - e_price) * shares_sold,
                    "pnl_pct": (sell_price - e_price) / (e_price + EPSILON),
                    "hold_days_used": entry_hold_days.get(asset_id, 0),
                    "asset_id": asset_id,
                    "trade_type": "rebalance" if order.rebalance_sell_amount > 0.0 else "signal",
                }
                all_trades.append(trade_record)

                state.position -= shares_sold

                # 전량 매도(신호 기반)인 경우에만 진입 정보 초기화
                if state.position == 0:
                    entry_prices[asset_id] = 0.0
                    entry_dates[asset_id] = None

                if order.rebalance_sell_amount > 0.0:
                    rebalanced_today = True

                logger.debug(
                    f"매도 체결: {asset_id}, 날짜={current_date}, "
                    f"가격={sell_price:.2f}, 수량={shares_sold}, "
                    f"잔여포지션={state.position}"
                )

            state.pending_order = None

        # Step B: 매수 후행 체결 (Step A에서 확보된 현금 포함하여 매수)
        for asset_id, state in asset_states.items():
            if state.pending_order is None or state.pending_order.order_type != "buy":
                continue

            trade_df = asset_trade_dfs[asset_id]
            open_price = float(trade_df.iloc[i][COL_OPEN])
            order = state.pending_order

            if state.position == 0 or order.is_rebalance:
                buy_price = open_price * (1.0 + SLIPPAGE_RATE)
                buy_capital = order.capital
                if buy_capital <= 0:
                    # capital이 없으면 가용 현금 전체 사용 (초기 진입)
                    buy_capital = shared_cash * slot_dict[asset_id].target_weight
                shares = int(buy_capital / buy_price)
                if shares > 0:
                    cost = shares * buy_price
                    shared_cash -= cost
                    if state.position == 0:
                        # 신규 진입: entry_price = buy_price
                        state.position = shares
                        entry_prices[asset_id] = buy_price
                        entry_dates[asset_id] = current_date
                    else:
                        # 리밸런싱 추가매수: entry_price 가중평균 업데이트
                        prev_position = state.position
                        prev_entry_price = entry_prices.get(asset_id, 0.0)
                        state.position += shares
                        entry_prices[asset_id] = (
                            prev_entry_price * prev_position + buy_price * shares
                        ) / state.position
                    if order.is_rebalance:
                        rebalanced_today = True
                    logger.debug(f"매수 체결: {asset_id}, 날짜={current_date}, " f"가격={buy_price:.2f}, 수량={shares}")

            state.pending_order = None

        # Step C: 에쿼티 계산 (체결 완료 후, 당일 종가 기준)
        # 체결 후에 계산해야 리밸런싱 판정 시 목표 비중 편차가 정확히 반영된다
        asset_positions = {aid: st.position for aid, st in asset_states.items()}
        asset_closes_map: dict[str, float] = {}
        for asset_id in asset_states:
            trade_df = asset_trade_dfs[asset_id]
            asset_closes_map[asset_id] = float(trade_df.iloc[i][COL_CLOSE])

        current_equity = _compute_portfolio_equity(shared_cash, asset_positions, asset_closes_map)

        # Step D: 시그널 판정 (signal_df[i].Close 기준, 익일 체결 예약)
        # 전략의 check_buy/check_sell은 내부 prev 상태를 순차적으로 갱신한다 (stateful).
        # 신호 발생 시 pending_order만 등록하고 실제 체결은 익일 Step A/B에서 처리한다
        for asset_id, state in asset_states.items():
            signal_df = asset_signal_dfs[asset_id]
            strategy = strategies[asset_id]
            slot = slot_dict[asset_id]

            if state.position == 0:
                # 매수 시그널 판정 — strategy.check_buy()에 위임 (내부 prev 상태 갱신 포함)
                buy_now = strategy.check_buy(signal_df, i, current_date)

                if buy_now:
                    meta = strategy.get_buy_meta()
                    if state.pending_order is None:
                        target_w = slot.target_weight
                        buy_capital = current_equity * target_w
                        state.pending_order = _PortfolioPendingOrder(
                            order_type="buy",
                            signal_date=current_date,
                            capital=buy_capital,
                        )
                        state.signal_state = "buy"
                        entry_hold_days[asset_id] = int(meta.get("hold_days_used", 0))

            elif state.position > 0:
                # 매도 시그널 판정 — strategy.check_sell()에 위임 (내부 prev 상태 갱신 포함)
                sell_now = strategy.check_sell(signal_df, i)
                if sell_now and state.pending_order is None:
                    state.pending_order = _PortfolioPendingOrder(
                        order_type="sell",
                        signal_date=current_date,
                        capital=0.0,
                    )
                    state.signal_state = "sell"

        # Step E: 이중 트리거 리밸런싱 판정 (Step C 에쿼티 기준)
        # 월 첫 거래일(정기): 10% 초과 시 트리거 — 정기적인 비중 재조정
        # 나머지 날(긴급): 20% 초과 시 트리거 — 급격한 비중 이탈 대응
        equity_vals_now: dict[str, float] = {
            aid: asset_states[aid].position * asset_closes_map[aid] for aid in asset_states
        }
        is_month_start = _is_first_trading_day_of_month(trade_dates, i)
        if is_month_start:
            if _check_rebalancing_needed(
                asset_states, equity_vals_now, current_equity, config, threshold=MONTHLY_REBALANCE_THRESHOLD_RATE
            ):
                _execute_rebalancing(asset_states, equity_vals_now, config, shared_cash, current_date)
        elif _check_rebalancing_needed(
            asset_states, equity_vals_now, current_equity, config, threshold=DAILY_REBALANCE_THRESHOLD_RATE
        ):
            _execute_rebalancing(asset_states, equity_vals_now, config, shared_cash, current_date)

        # Step F: 에쿼티 행 기록 (자산별 value/weight/signal 포함)
        row: dict[str, Any] = {
            COL_DATE: current_date,
            "equity": current_equity,
            "cash": shared_cash,
            "rebalanced": rebalanced_today,
        }
        for asset_id, st in asset_states.items():
            val = st.position * asset_closes_map[asset_id]
            row[f"{asset_id}_value"] = val
            row[f"{asset_id}_weight"] = val / (current_equity + EPSILON)
            row[f"{asset_id}_signal"] = st.signal_state
        equity_rows.append(row)

    # 8. 결과 조합
    equity_df = _build_combined_equity(equity_rows, config.total_capital)

    # trades_df 정리 (asset_id, trade_type 컬럼 표준화)
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
        # trade_type 컬럼 추가: 현재는 모두 "signal" (리밸런싱 체결은 signal_date로 구분 가능)
        if "trade_type" not in trades_df.columns:
            trades_df["trade_type"] = "signal"
    else:
        trades_df = pd.DataFrame(
            columns=[
                "entry_date",
                "exit_date",
                "entry_price",
                "exit_price",
                "shares",
                "pnl",
                "pnl_pct",
                "hold_days_used",
                "asset_id",
                "trade_type",
            ]
        )

    # 성과 요약 (합산 에쿼티 기준)
    summary = calculate_summary(trades_df, equity_df, config.total_capital)

    # 자산별 결과
    per_asset: list[PortfolioAssetResult] = []
    for slot in config.asset_slots:
        asset_id = slot.asset_id
        asset_trades = trades_df[trades_df["asset_id"] == asset_id] if len(trades_df) > 0 else pd.DataFrame()
        per_asset.append(
            PortfolioAssetResult(
                asset_id=asset_id,
                trades_df=asset_trades,
                signal_df=asset_signal_dfs[asset_id],
            )
        )

    # params_json 구성 (전략 파라미터는 슬롯 레벨로 이동)
    params_json: dict[str, Any] = {
        "experiment_name": config.experiment_name,
        "display_name": config.display_name,
        "total_capital": config.total_capital,
        # 리밸런싱 임계값: 엔진 레벨 상수로 고정 (모든 실험에 동일하게 적용됨)
        "monthly_rebalance_threshold_rate": MONTHLY_REBALANCE_THRESHOLD_RATE,
        "daily_rebalance_threshold_rate": DAILY_REBALANCE_THRESHOLD_RATE,
        "assets": [
            {
                "asset_id": slot.asset_id,
                "target_weight": slot.target_weight,
                "signal_data_path": str(slot.signal_data_path),
                "trade_data_path": str(slot.trade_data_path),
                "strategy_type": slot.strategy_type,
                "ma_window": slot.ma_window,
                "ma_type": slot.ma_type,
                "buy_buffer_zone_pct": slot.buy_buffer_zone_pct,
                "sell_buffer_zone_pct": slot.sell_buffer_zone_pct,
                "hold_days": slot.hold_days,
            }
            for slot in config.asset_slots
        ],
    }

    logger.debug(
        f"포트폴리오 백테스트 완료: {config.experiment_name}, "
        f"총 거래={len(trades_df)}, 총 수익률={summary.get('total_return_pct', 0):.2f}%"
    )

    return PortfolioResult(
        experiment_name=config.experiment_name,
        display_name=config.display_name,
        equity_df=equity_df,
        trades_df=trades_df,
        summary=summary,
        per_asset=per_asset,
        config=config,
        params_json=params_json,
    )
