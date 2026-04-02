"""포트폴리오 백테스트 엔진

복수 자산의 독립 시그널 + 목표 비중 배분 + 이중 트리거 리밸런싱을 처리한다.

주요 설계 결정:
- 주문 모델: OrderIntent 기반 (EXIT_ALL / ENTER_TO_TARGET / REDUCE_TO_TARGET / INCREASE_TO_TARGET)
- 흐름: Signal → ProjectedPortfolio → Rebalance → MergeIntents → Execution (next_day_intents)
- 리밸런싱: 이중 트리거 체계 (RebalancePolicy)
    - 월 첫 거래일: 편차 10% 초과 시 트리거 (monthly_threshold_rate)
    - 매일: 편차 20% 초과 시 긴급 트리거 (daily_threshold_rate)
- 주문 충돌 해소: merge_intents 우선순위 규칙으로 자산당 1개 보장
- projected state: signal intent 반영 후 리밸런싱 계획 → planning 왜곡 방지
- 체결 기준: 익일 open 가격 (Lookahead 방지)
- 체결 흐름: SELL 먼저 체결 → available_cash 확정 → BUY 체결 (execute_orders)
- 현금 부족 시: BUY 총 비용이 available_cash 초과이면 raw_shares × scale_factor로 비례 축소
- 부분 매도: 리밸런싱 REDUCE_TO_TARGET은 delta_amount 기준 수량, 신호 EXIT_ALL은 전량
- 결과: PortfolioResult (equity_df, trades_df, per_asset, summary)
"""

from datetime import date
from typing import Any

import pandas as pd

from qbt.backtest.analysis import calculate_summary
from qbt.backtest.constants import COL_EQUITY, ma_col_name
from qbt.backtest.engines.portfolio_data import (
    build_combined_equity,
    load_and_prepare_data,
    validate_portfolio_config,
)
from qbt.backtest.engines.portfolio_execution import (
    AssetState,
    execute_orders,
)
from qbt.backtest.engines.portfolio_planning import (
    OrderIntent,
    compute_portfolio_equity,
    compute_projected_portfolio,
    create_strategy_for_slot,
    generate_signal_intents,
    merge_intents,
)
from qbt.backtest.engines.portfolio_rebalance import (
    DEFAULT_REBALANCE_POLICY,
    is_first_trading_day_of_month,
)
from qbt.backtest.portfolio_types import (
    PortfolioAssetResult,
    PortfolioConfig,
    PortfolioResult,
)
from qbt.backtest.strategies.strategy_common import SignalStrategy
from qbt.backtest.strategy_registry import STRATEGY_REGISTRY
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN, EPSILON
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)


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
        signal_key = f"{slot.signal_data_path}::{slot.strategy_id}::{slot.ma_window}::{slot.ma_type}"
        if signal_key not in signal_cache:
            signal_df_raw, trade_df = load_and_prepare_data(slot)
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

    # 3. MA 워밍업 구간 필터링 (registry의 get_warmup_periods 경유)
    # warmup > 0인 슬롯만 MA NaN 체크 대상 (warmup == 0이면 워밍업 없음)
    valid_start_indices: list[int] = []
    for asset_id in asset_signal_dfs:
        slot = slot_dict[asset_id]
        spec = STRATEGY_REGISTRY.get(slot.strategy_id)
        if spec is None:
            raise ValueError(f"미등록 strategy_id: '{slot.strategy_id}'")
        warmup = spec.get_warmup_periods(slot)
        if warmup == 0:
            continue
        ma_col = ma_col_name(slot.ma_window)
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

    복수 자산의 독립 시그널 + 목표 비중 배분 + 이중 트리거 리밸런싱을 수행한다.
    OrderIntent 기반 주문 모델로 signal과 rebalance 충돌을 merge_intents가 해소한다.

    메인 루프 흐름:
        Step A: SELL 체결 (전일 next_day_intents: EXIT_ALL, REDUCE_TO_TARGET)
        Step B: BUY 체결 (전일 next_day_intents: ENTER_TO_TARGET, INCREASE_TO_TARGET)
        Step C: Equity 계산 (당일 종가 기준)
        Step D: Signal → Projected → Rebalance → Merge → next_day_intents
        Step E: Equity row 기록

    Args:
        config: 포트폴리오 실험 설정
        start_date: 백테스트 시작일 하한 (None이면 MA 워밍업 완료 시점부터 자동 결정).
            여러 실험을 동일 기간으로 정렬할 때 global_start_date를 전달한다.

    Returns:
        PortfolioResult (equity_df, trades_df, summary, per_asset 포함)

    Raises:
        ValueError: 설정 검증 실패 또는 공통 기간 없음
    """
    logger.debug(f"포트폴리오 백테스트 시작: {config.experiment_name}")

    # 1. 설정 검증
    validate_portfolio_config(config)

    slot_dict = {slot.asset_id: slot for slot in config.asset_slots}

    # 2. 자산별 데이터 로딩 + MA 계산 (슬롯별 MA 파라미터 사용)
    # signal_data_path 기준으로 중복 로딩 방지 (캐시)
    signal_cache: dict[str, pd.DataFrame] = {}
    asset_signal_dfs: dict[str, pd.DataFrame] = {}
    asset_trade_dfs: dict[str, pd.DataFrame] = {}

    for slot in config.asset_slots:
        signal_key = f"{slot.signal_data_path}::{slot.strategy_id}::{slot.ma_window}::{slot.ma_type}"
        if signal_key not in signal_cache:
            signal_df_raw, trade_df = load_and_prepare_data(slot)
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

    # MA 워밍업 구간 필터링 (registry의 get_warmup_periods 경유)
    # warmup > 0인 슬롯만 MA NaN 체크 대상 (warmup == 0이면 워밍업 없음)
    valid_start_indices: list[int] = []
    for asset_id in asset_signal_dfs:
        slot = slot_dict[asset_id]
        spec = STRATEGY_REGISTRY.get(slot.strategy_id)
        if spec is None:
            raise ValueError(f"미등록 strategy_id: '{slot.strategy_id}'")
        warmup = spec.get_warmup_periods(slot)
        if warmup == 0:
            continue
        ma_col = ma_col_name(slot.ma_window)
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
        slot.asset_id: create_strategy_for_slot(slot) for slot in config.asset_slots
    }

    # 5. 자산별 상태 초기화 (모든 자산 "sell"로 시작, pending_order 없음)
    asset_states: dict[str, AssetState] = {
        slot.asset_id: AssetState(position=0, signal_state="sell") for slot in config.asset_slots
    }

    shared_cash = config.total_capital

    # 자산별 진입 정보 (entry_price, entry_date, entry_hold_days)
    entry_prices: dict[str, float] = {slot.asset_id: 0.0 for slot in config.asset_slots}
    entry_dates: dict[str, date | None] = {slot.asset_id: None for slot in config.asset_slots}
    entry_hold_days: dict[str, int] = {slot.asset_id: 0 for slot in config.asset_slots}

    # 거래 기록 및 에쿼티 기록
    all_trades: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []

    # next_day_intents: 전일 생성된 merged intents → 당일 체결 대상
    next_day_intents: dict[str, OrderIntent] = {}

    # 6. 메인 루프: 전일 intents 체결 → 당일 에쿼티 → 당일 signal → projected → rebalance → merge
    # 신호와 체결을 하루씩 분리(Lookahead 방지): i일 종가 시그널 → i+1일 시가 체결
    for i in range(0, n):
        current_date = trade_dates[i]
        rebalanced_today = False

        # Step A+B: SELL → BUY 순 체결 (SELL 확보 현금 → BUY에 활용, 부족 시 비례 축소)
        open_prices_map: dict[str, float] = {aid: float(asset_trade_dfs[aid].iloc[i][COL_OPEN]) for aid in asset_states}
        exec_result = execute_orders(
            order_intents=next_day_intents,
            open_prices=open_prices_map,
            current_positions={aid: st.position for aid, st in asset_states.items()},
            current_cash=shared_cash,
            entry_prices=entry_prices,
            entry_dates=entry_dates,
            entry_hold_days=entry_hold_days,
            current_date=current_date,
        )
        shared_cash = exec_result.updated_cash
        for aid, new_pos in exec_result.updated_positions.items():
            if aid in asset_states:
                asset_states[aid].position = new_pos
        entry_prices = exec_result.updated_entry_prices
        entry_dates = exec_result.updated_entry_dates
        entry_hold_days = exec_result.updated_entry_hold_days
        all_trades.extend(exec_result.new_trades)
        rebalanced_today = exec_result.rebalanced_today

        # Step C: 에쿼티 계산 (체결 완료 후, 당일 종가 기준)
        # 체결 후에 계산해야 리밸런싱 판정 시 목표 비중 편차가 정확히 반영된다
        asset_positions = {aid: st.position for aid, st in asset_states.items()}
        asset_closes_map: dict[str, float] = {}
        for asset_id in asset_states:
            trade_df = asset_trade_dfs[asset_id]
            asset_closes_map[asset_id] = float(trade_df.iloc[i][COL_CLOSE])

        current_equity = compute_portfolio_equity(shared_cash, asset_positions, asset_closes_map)

        # Step D: Signal → Projected → Rebalance → Merge (익일 체결용 next_day_intents 생성)
        equity_vals_now: dict[str, float] = {
            aid: asset_states[aid].position * asset_closes_map[aid] for aid in asset_states
        }

        # D.1: signal intents 생성 (전략 호출, 내부 prev 상태 갱신 포함)
        signal_intents = generate_signal_intents(
            asset_states, strategies, asset_signal_dfs, equity_vals_now, slot_dict, current_equity, i, current_date
        )

        # D.2: projected portfolio 계산 (signal intents 반영 후 예상 상태)
        projected = compute_projected_portfolio(
            asset_states, signal_intents, equity_vals_now, asset_closes_map, shared_cash
        )

        # D.3: rebalance intents 생성 (projected 기준, 이중 트리거 임계값 적용)
        total_equity_projected = projected.projected_cash + sum(projected.projected_amounts.values())
        is_month_start = is_first_trading_day_of_month(trade_dates, i)
        if DEFAULT_REBALANCE_POLICY.should_rebalance(projected, slot_dict, total_equity_projected, is_month_start):
            rebalance_intents = DEFAULT_REBALANCE_POLICY.build_rebalance_intents(
                projected, slot_dict, total_equity_projected, current_date
            )
        else:
            rebalance_intents = {}

        # D.4: signal + rebalance 통합 (우선순위 규칙 적용, 자산당 1개 보장)
        merged_intents = merge_intents(signal_intents, rebalance_intents)

        # D.5: signal_state 업데이트 (EXIT_ALL → "sell", ENTER_TO_TARGET → "buy")
        for asset_id, intent in merged_intents.items():
            if intent.intent_type == "EXIT_ALL":
                asset_states[asset_id].signal_state = "sell"
            elif intent.intent_type == "ENTER_TO_TARGET":
                asset_states[asset_id].signal_state = "buy"

        # D.6: 익일 체결용 intents 저장
        next_day_intents = merged_intents

        # Step E: 에쿼티 행 기록 (자산별 value/weight/signal 포함)
        row: dict[str, Any] = {
            COL_DATE: current_date,
            COL_EQUITY: current_equity,
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
    equity_df = build_combined_equity(equity_rows, config.total_capital)

    # trades_df 정리
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
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
        "monthly_rebalance_threshold_rate": DEFAULT_REBALANCE_POLICY.monthly_threshold_rate,
        "daily_rebalance_threshold_rate": DEFAULT_REBALANCE_POLICY.daily_threshold_rate,
        "assets": [
            {
                "asset_id": slot.asset_id,
                "target_weight": slot.target_weight,
                "signal_data_path": str(slot.signal_data_path),
                "trade_data_path": str(slot.trade_data_path),
                "strategy_id": slot.strategy_id,
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
