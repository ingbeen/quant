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
from qbt.backtest.strategies.buffer_zone_helpers import (  # type: ignore[import]
    HoldState,
    _compute_bands,  # pyright: ignore[reportPrivateUsage]
    _detect_buy_signal,  # pyright: ignore[reportPrivateUsage]
    _detect_sell_signal,  # pyright: ignore[reportPrivateUsage]
)
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

    buffer_zone_helpers의 PendingOrder와 달리 capital, rebalance_sell_amount 필드를 포함한다.
    매수 시 capital에 투자 자본금을 저장하고, rebalance_sell_amount는 0.0.
    리밸런싱 매도 시 rebalance_sell_amount에 초과분 대금을 저장 (> 0.0 = 부분 매도).
    신호 기반 매도 시 rebalance_sell_amount = 0.0 (전량 매도).
    """

    order_type: Literal["buy", "sell"]  # 주문 유형
    signal_date: date  # 신호 발생 날짜
    capital: float  # 매수 자본 (매도 시 0.0)
    rebalance_sell_amount: float = 0.0  # 리밸런싱 부분 매도 대금 (0.0 = 전량 매도)


@dataclass
class _AssetState:
    """자산별 런타임 상태."""

    position: int  # 보유 수량
    signal_state: str  # "buy" | "sell"
    pending_order: _PortfolioPendingOrder | None  # 예약 주문 (None = 없음)
    hold_state: HoldState | None  # hold_days 상태머신


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
    threshold: float | None = None,
) -> bool:
    """리밸런싱 필요 여부를 판정한다.

    매수 시그널 자산 중 하나라도 |actual/target - 1| > threshold이면 True.
    target=0인 자산은 건너뛴다.

    Args:
        asset_states: {asset_id: _AssetState}
        equity_vals: {asset_id: 현재 평가액}
        total_equity: 총 에쿼티
        config: 포트폴리오 설정
        threshold: 리밸런싱 임계값. None이면 config.rebalance_threshold_rate 사용.
            월 첫날: MONTHLY_REBALANCE_THRESHOLD_RATE, 매일: DAILY_REBALANCE_THRESHOLD_RATE

    Returns:
        True이면 리밸런싱 실행 필요
    """
    if total_equity < EPSILON:
        return False

    slot_dict = {slot.asset_id: slot for slot in config.asset_slots}
    effective_threshold = threshold if threshold is not None else config.rebalance_threshold_rate

    for asset_id, state in asset_states.items():
        if state.signal_state != "buy":
            continue
        slot = slot_dict.get(asset_id)
        if slot is None or slot.target_weight == 0:
            continue

        actual = equity_vals.get(asset_id, 0.0) / total_equity
        deviation = abs(actual / slot.target_weight - 1.0)
        if deviation > effective_threshold:
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
            )


# ============================================================================
# 내부 헬퍼 함수
# ============================================================================


def _load_and_prepare_data(
    slot: AssetSlotConfig,
    ma_window: int,
    ma_type: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """자산 슬롯의 데이터를 로딩하고 MA를 계산한다.

    Args:
        slot: 자산 슬롯 설정
        ma_window: 이동평균 기간
        ma_type: 이동평균 유형 ("ema" 또는 "sma")

    Returns:
        (signal_df_with_ma, trade_df)
    """
    signal_df = load_stock_data(slot.signal_data_path)
    trade_df = load_stock_data(slot.trade_data_path)

    # signal/trade 데이터 경로가 다르면 교집합 기간 추출
    if slot.signal_data_path != slot.trade_data_path:
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    # MA 계산
    signal_df = add_single_moving_average(signal_df, ma_window, ma_type)

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

    전 자산 데이터의 날짜 교집합을 구하고 MA 워밍업 완료 이후 첫 날짜를 반환한다.
    여러 실험을 동일 기간으로 정렬할 때 글로벌 시작일을 결정하는 데 사용한다.

    Args:
        config: 포트폴리오 실험 설정

    Returns:
        MA 워밍업 완료 이후 첫 유효 거래일 (date 객체)

    Raises:
        ValueError: 공통 기간 없음 또는 MA 컬럼 누락 시
    """
    ma_col = f"ma_{config.ma_window}"

    # 1. 자산별 데이터 로딩 + MA 계산 (signal_data_path 기준 캐시)
    signal_cache: dict[str, pd.DataFrame] = {}
    asset_trade_dfs: dict[str, pd.DataFrame] = {}
    asset_signal_dfs: dict[str, pd.DataFrame] = {}

    for slot in config.asset_slots:
        signal_key = str(slot.signal_data_path)
        if signal_key not in signal_cache:
            signal_df_raw, trade_df = _load_and_prepare_data(slot, config.ma_window, config.ma_type)
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

    # 3. MA 유효 구간 필터링 (MA 워밍업 완료 이후 첫 인덱스)
    valid_start_indices: list[int] = []
    for asset_id in asset_signal_dfs:
        sdf = asset_signal_dfs[asset_id]
        if ma_col not in sdf.columns:
            raise ValueError(f"MA 컬럼 누락: {ma_col} (asset_id={asset_id})")
        valid_mask = sdf[ma_col].notna()
        if valid_mask.any():
            valid_start_indices.append(int(valid_mask.idxmax()))
        else:
            valid_start_indices.append(len(sdf))

    valid_start = max(valid_start_indices)

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

    ma_col = f"ma_{config.ma_window}"

    # 2. 자산별 데이터 로딩 + MA 계산
    # signal_data_path 기준으로 중복 로딩 방지 (캐시)
    signal_cache: dict[str, pd.DataFrame] = {}
    asset_signal_dfs: dict[str, pd.DataFrame] = {}
    asset_trade_dfs: dict[str, pd.DataFrame] = {}

    for slot in config.asset_slots:
        signal_key = str(slot.signal_data_path)
        if signal_key not in signal_cache:
            signal_df_raw, trade_df = _load_and_prepare_data(slot, config.ma_window, config.ma_type)
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

    # MA 유효 구간 필터링 (MA 값이 있는 첫 인덱스 이후만 사용)
    valid_start_indices: list[int] = []
    for asset_id in asset_signal_dfs:
        sdf = asset_signal_dfs[asset_id]
        if ma_col not in sdf.columns:
            raise ValueError(f"MA 컬럼 누락: {ma_col} (asset_id={asset_id})")
        valid_mask = sdf[ma_col].notna()
        if valid_mask.any():
            valid_start_indices.append(int(valid_mask.idxmax()))
        else:
            valid_start_indices.append(len(sdf))

    valid_start = max(valid_start_indices)

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

    # 4. 자산별 상태 초기화
    # strategy_type="buy_and_hold" 자산은 항상 매수 상태로 시작 (버퍼존 신호 대기 없음)
    asset_states: dict[str, _AssetState] = {
        slot.asset_id: _AssetState(
            position=0,
            signal_state="buy" if slot.strategy_type == "buy_and_hold" else "sell",
            pending_order=None,
            hold_state=None,
        )
        for slot in config.asset_slots
    }

    shared_cash = config.total_capital

    # 자산별 진입 정보 (entry_price, entry_date)
    entry_prices: dict[str, float] = {slot.asset_id: 0.0 for slot in config.asset_slots}
    entry_dates: dict[str, date | None] = {slot.asset_id: None for slot in config.asset_slots}
    entry_hold_days: dict[str, int] = {slot.asset_id: 0 for slot in config.asset_slots}

    # 자산별 이전 밴드 값 초기화
    prev_upper_bands: dict[str, float] = {}
    prev_lower_bands: dict[str, float] = {}

    slot_dict = {slot.asset_id: slot for slot in config.asset_slots}
    first_trade_date = trade_dates[0]

    # 5. 첫 날 초기화
    # strategy_type="buy_and_hold" 자산은 day 0에 buy pending_order 생성 (i=1에서 즉시 매수)
    for slot in config.asset_slots:
        asset_id = slot.asset_id
        signal_df = asset_signal_dfs[asset_id]
        first_row = signal_df.iloc[0]
        ma_val = float(first_row[ma_col])
        u, lb = _compute_bands(ma_val, config.buy_buffer_zone_pct, config.sell_buffer_zone_pct)
        prev_upper_bands[asset_id] = u
        prev_lower_bands[asset_id] = lb

        if slot.strategy_type == "buy_and_hold":
            # 초기 매수 자본: total_capital × target_weight
            # 여러 buy_and_hold 자산이 동시에 매수될 때 공정한 자본 배분을 위해
            # shared_cash 잔액이 아닌 total_capital 기준으로 고정 계산
            initial_capital = config.total_capital * slot.target_weight
            asset_states[asset_id].pending_order = _PortfolioPendingOrder(
                order_type="buy",
                signal_date=first_trade_date,
                capital=initial_capital,
            )

    # 거래 기록 및 에쿼티 기록
    all_trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []

    # 첫 날 에쿼티 기록
    first_row_dict: dict[str, Any] = {
        COL_DATE: first_trade_date,
        "equity": shared_cash,
        "cash": shared_cash,
        "rebalanced": False,
    }
    for asset_id in asset_states:
        first_row_dict[f"{asset_id}_value"] = 0.0
        first_row_dict[f"{asset_id}_weight"] = 0.0
        first_row_dict[f"{asset_id}_signal"] = "sell"
    equity_rows.append(first_row_dict)

    # 6. 메인 루프 (i = 1 ~ N-1)
    for i in range(1, n):
        current_date = trade_dates[i]
        rebalanced_today = False

        # 6-1. pending_order 체결 (trade_df[i].Open 기준) — 2패스 방식
        # 1패스: 전 자산 sell pending_order 먼저 체결 (매도 대금이 매수 자본으로 사용)
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

                logger.debug(
                    f"매도 체결: {asset_id}, 날짜={current_date}, "
                    f"가격={sell_price:.2f}, 수량={shares_sold}, "
                    f"잔여포지션={state.position}"
                )

            state.pending_order = None

        # 2패스: 전 자산 buy pending_order 체결 (매도 후 현금으로 매수)
        for asset_id, state in asset_states.items():
            if state.pending_order is None or state.pending_order.order_type != "buy":
                continue

            trade_df = asset_trade_dfs[asset_id]
            open_price = float(trade_df.iloc[i][COL_OPEN])
            order = state.pending_order

            if state.position == 0:
                buy_price = open_price * (1.0 + SLIPPAGE_RATE)
                buy_capital = order.capital
                if buy_capital <= 0:
                    # capital이 없으면 가용 현금 전체 사용 (초기 진입)
                    buy_capital = shared_cash * slot_dict[asset_id].target_weight
                shares = int(buy_capital / buy_price)
                if shares > 0:
                    cost = shares * buy_price
                    shared_cash -= cost
                    state.position = shares
                    entry_prices[asset_id] = buy_price
                    entry_dates[asset_id] = current_date
                    logger.debug(f"매수 체결: {asset_id}, 날짜={current_date}, " f"가격={buy_price:.2f}, 수량={shares}")

            state.pending_order = None

        # 6-2. 에쿼티 계산 (trade_df[i].Close 기준)
        asset_positions = {aid: st.position for aid, st in asset_states.items()}
        asset_closes_map: dict[str, float] = {}
        for asset_id in asset_states:
            trade_df = asset_trade_dfs[asset_id]
            asset_closes_map[asset_id] = float(trade_df.iloc[i][COL_CLOSE])

        current_equity = _compute_portfolio_equity(shared_cash, asset_positions, asset_closes_map)

        # 6-3. 시그널 판정 (signal_df[i].Close 기준)
        for asset_id, state in asset_states.items():
            signal_df = asset_signal_dfs[asset_id]
            signal_row = signal_df.iloc[i]
            prev_signal_row = signal_df.iloc[i - 1]

            ma_val = float(signal_row[ma_col])
            upper_band, lower_band = _compute_bands(ma_val, config.buy_buffer_zone_pct, config.sell_buffer_zone_pct)
            prev_upper = prev_upper_bands[asset_id]
            prev_lower = prev_lower_bands[asset_id]

            prev_close = float(prev_signal_row[COL_CLOSE])
            cur_close = float(signal_row[COL_CLOSE])

            slot = slot_dict[asset_id]

            if slot.strategy_type == "buy_and_hold":
                # buy_and_hold 자산: 버퍼존 매도 신호 무시, 항상 투자 상태 유지.
                # 포지션이 없는 경우(리밸런싱 부분 매도 후 전량 소진 등)에만 재매수 신호 판정.
                if state.position == 0 and state.pending_order is None:
                    target_w = slot.target_weight
                    buy_capital = current_equity * target_w
                    state.pending_order = _PortfolioPendingOrder(
                        order_type="buy",
                        signal_date=current_date,
                        capital=buy_capital,
                    )
                    state.signal_state = "buy"
                prev_upper_bands[asset_id] = upper_band
                prev_lower_bands[asset_id] = lower_band
                continue

            if state.position == 0:
                # 매수 시그널 판정 (hold_state 상태머신)
                if state.hold_state is not None:
                    hs = state.hold_state
                    if cur_close > upper_band:
                        hs["days_passed"] += 1
                        if hs["days_passed"] >= hs["hold_days_required"]:
                            if state.pending_order is None:
                                # 매수 pending_order: capital = total_equity × target_weight
                                target_w = slot.target_weight
                                buy_capital = current_equity * target_w
                                state.pending_order = _PortfolioPendingOrder(
                                    order_type="buy",
                                    signal_date=current_date,
                                    capital=buy_capital,
                                )
                                state.signal_state = "buy"
                                entry_hold_days[asset_id] = hs["hold_days_required"]
                            state.hold_state = None
                    else:
                        state.hold_state = None

                if state.hold_state is None:
                    buy_detected = _detect_buy_signal(prev_close, cur_close, prev_upper, upper_band)
                    if buy_detected:
                        if config.hold_days > 0:
                            state.hold_state = HoldState(
                                start_date=current_date,
                                days_passed=0,
                                buffer_pct=config.buy_buffer_zone_pct,
                                hold_days_required=config.hold_days,
                            )
                        else:
                            if state.pending_order is None:
                                target_w = slot.target_weight
                                buy_capital = current_equity * target_w
                                state.pending_order = _PortfolioPendingOrder(
                                    order_type="buy",
                                    signal_date=current_date,
                                    capital=buy_capital,
                                )
                                state.signal_state = "buy"
                                entry_hold_days[asset_id] = 0

            elif state.position > 0:
                sell_detected = _detect_sell_signal(prev_close, cur_close, prev_lower, lower_band)
                if sell_detected:
                    if state.pending_order is None:
                        state.pending_order = _PortfolioPendingOrder(
                            order_type="sell",
                            signal_date=current_date,
                            capital=0.0,
                        )
                        state.signal_state = "sell"

            prev_upper_bands[asset_id] = upper_band
            prev_lower_bands[asset_id] = lower_band

        # 6-4. 이중 트리거 리밸런싱 판정
        # - 월 첫 거래일: 10% 임계값 (MONTHLY_REBALANCE_THRESHOLD_RATE)
        # - 매일(월 중간): 20% 임계값 (DAILY_REBALANCE_THRESHOLD_RATE)
        equity_vals_now: dict[str, float] = {
            aid: asset_states[aid].position * asset_closes_map[aid] for aid in asset_states
        }
        is_month_start = _is_first_trading_day_of_month(trade_dates, i)
        if is_month_start:
            if _check_rebalancing_needed(
                asset_states, equity_vals_now, current_equity, config, threshold=MONTHLY_REBALANCE_THRESHOLD_RATE
            ):
                _execute_rebalancing(asset_states, equity_vals_now, config, shared_cash, current_date)
                rebalanced_today = True
        elif _check_rebalancing_needed(
            asset_states, equity_vals_now, current_equity, config, threshold=DAILY_REBALANCE_THRESHOLD_RATE
        ):
            _execute_rebalancing(asset_states, equity_vals_now, config, shared_cash, current_date)
            rebalanced_today = True

        # 6-5. 에쿼티 행 기록
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

    # 7. 결과 조합
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

    # params_json 구성
    params_json: dict[str, Any] = {
        "experiment_name": config.experiment_name,
        "display_name": config.display_name,
        "total_capital": config.total_capital,
        "ma_window": config.ma_window,
        "ma_type": config.ma_type,
        "buy_buffer_zone_pct": config.buy_buffer_zone_pct,
        "sell_buffer_zone_pct": config.sell_buffer_zone_pct,
        "hold_days": config.hold_days,
        "rebalance_threshold_rate": config.rebalance_threshold_rate,
        "assets": [
            {
                "asset_id": slot.asset_id,
                "target_weight": slot.target_weight,
                "signal_data_path": str(slot.signal_data_path),
                "trade_data_path": str(slot.trade_data_path),
                "strategy_type": slot.strategy_type,
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
