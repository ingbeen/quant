"""포트폴리오 백테스트 엔진

한 실험의 매매법(들)이 각자 장부(몫 · 현금 · 보유 주수 · 손익)를 갖고 매매한다.
매매법이 하나인 실험(asset_slots 줄임 표기)은 장부 하나가 곧 계좌다.

주요 설계 결정:
- 주문 모델: OrderIntent 기반 (EXIT_ALL / ENTER_TO_TARGET / REDUCE_TO_TARGET / INCREASE_TO_TARGET)
- 흐름: Signal(슬롯 전략 | 배분 규칙) → ProjectedPortfolio → Rebalance → MergeIntents → Execution (next_day_intents)
- 리밸런싱: 월 마지막 거래일 종가에 매매법 안 편차가 임계값(RebalancePolicy.threshold_rate)을 넘으면
  다음 거래일 시가에 체결한다. 같은 날 매매법 몫의 편차가 임계값을 넘으면 매매법 사이 비중을 먼저 되돌린다
- 체결 순서: 전 매매법 매도 → 매매법 사이 이전 → 전 매매법 매수 (매매법별로 execute_orders)
- 종목 단위 상계: 매매법 장부는 단독 매매처럼 비용을 내고, 같은 날 반대 매매로 아낀 비용은 계좌의 상계 절감
- 현금 부족 시: BUY 총 비용이 매매법 현금을 넘으면 raw_shares × scale_factor로 비례 축소
- 부분 매도: 리밸런싱 REDUCE_TO_TARGET은 delta_amount 기준 수량, 신호 EXIT_ALL은 전량
- 결과: PortfolioResult (equity_df, trades_df, per_asset, summary, state_log_df, ledger_df, netting_df)
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from qbt.backtest.allocator_registry import ALLOCATOR_REGISTRY
from qbt.backtest.analysis import calculate_summary
from qbt.backtest.constants import (
    COL_ENTRY_DATE,
    COL_ENTRY_PRICE,
    COL_EQUITY,
    COL_EXIT_DATE,
    COL_EXIT_PRICE,
    COL_HOLD_DAYS_USED,
    COL_PNL,
    COL_PNL_PCT,
    COL_SHARES,
    SLIPPAGE_RATE,
    ma_col_name,
)
from qbt.backtest.engines.engine_common import PortfolioTradeRecord
from qbt.backtest.engines.portfolio_data import (
    build_combined_equity,
    load_and_prepare_data,
    validate_portfolio_config,
)
from qbt.backtest.engines.portfolio_execution import ExecutionResult, execute_orders
from qbt.backtest.engines.portfolio_methods import (
    MethodBook,
    cap_transfers,
    compute_allocation_projection,
    compute_netting,
    generate_allocation_intents,
    plan_method_transfers,
)
from qbt.backtest.engines.portfolio_planning import (
    OrderIntent,
    ProjectedPortfolio,
    compute_portfolio_equity,
    compute_projected_portfolio,
    create_strategy_for_slot,
    generate_signal_intents,
    merge_intents,
)
from qbt.backtest.engines.portfolio_rebalance import (
    DEFAULT_REBALANCE_POLICY,
    is_last_trading_day_of_month,
)
from qbt.backtest.portfolio_types import (
    AllocatorMethodConfig,
    AssetSlotConfig,
    AssetState,
    MethodConfig,
    PortfolioAssetResult,
    PortfolioConfig,
    PortfolioResult,
    SlotMethodConfig,
    asset_close_col,
    asset_executed_intent_col,
    asset_pending_intent_col,
    asset_shares_col,
    asset_signal_today_col,
    asset_value_col,
    asset_weight_col,
    position_key,
    resolve_methods,
)
from qbt.backtest.strategy_registry import STRATEGY_REGISTRY
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN, EPSILON
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)

_SELL_INTENT_TYPES = ("EXIT_ALL", "REDUCE_TO_TARGET")
_BUY_INTENT_TYPES = ("ENTER_TO_TARGET", "INCREASE_TO_TARGET")
_REBALANCE_REASON_MONTHLY = "monthly"
_REBALANCE_REASON_METHODS = "methods"
_NETTING_COLUMNS = [COL_DATE, "asset_id", "gross_shares", "net_shares", "open_price", "savings"]


@dataclass
class _PortfolioData:
    """매매법 · 자산 키별로 읽어 공통 기간으로 맞춘 데이터.

    signal_dfs · trade_dfs 의 키는 결과 파일의 자산 키(position_key)다.
    """

    methods: tuple[MethodConfig, ...]
    multi_method: bool
    keys_by_method: dict[str, list[str]]
    asset_of_key: dict[str, str]
    slot_of_key: dict[str, AssetSlotConfig]
    signal_dfs: dict[str, pd.DataFrame]
    trade_dfs: dict[str, pd.DataFrame]
    series_dfs: dict[str, dict[str, pd.DataFrame]]  # {method_id: {series_id: 시세}}
    valid_start: int


def _load_portfolio_data_with_common_period(config: PortfolioConfig) -> _PortfolioData:
    """매매법 · 자산별 데이터 로딩 → 공통 기간 필터링 → 워밍업 인덱스 계산.

    signal_data_path 기준 캐시, 날짜 교집합 필터링(매매 데이터 + 신호용 시세), 워밍업 구간 계산을
    한 곳에서 수행한다.

    Args:
        config: 포트폴리오 실험 설정

    Returns:
        _PortfolioData — valid_start 는 워밍업 완료 후 첫 유효 인덱스이고, 시세들은 공통 기간으로
        필터링된 상태(워밍업 슬라이싱 미적용)다.

    Raises:
        ValueError: 공통 기간 없음 또는 MA 컬럼 누락 시
    """
    methods = resolve_methods(config)
    multi_method = len(methods) > 1

    # 1. 자산별 데이터 로딩 + MA 계산 (signal_data_path 기준 캐시, 슬롯별 MA 파라미터 사용)
    signal_cache: dict[str, pd.DataFrame] = {}
    keys_by_method: dict[str, list[str]] = {}
    asset_of_key: dict[str, str] = {}
    slot_of_key: dict[str, AssetSlotConfig] = {}
    asset_trade_dfs: dict[str, pd.DataFrame] = {}
    asset_signal_dfs: dict[str, pd.DataFrame] = {}
    series_dfs: dict[str, dict[str, pd.DataFrame]] = {}
    allocator_keys: list[str] = []

    for method in methods:
        keys: list[str] = []
        if isinstance(method, SlotMethodConfig):
            for slot in method.asset_slots:
                key = position_key(method.method_id, slot.asset_id, multi_method=multi_method)
                signal_key = f"{slot.signal_data_path}::{slot.strategy_id}::{slot.ma_window}"
                if signal_key not in signal_cache:
                    signal_df_raw, trade_df = load_and_prepare_data(slot)
                    signal_cache[signal_key] = signal_df_raw
                else:
                    signal_df_raw = signal_cache[signal_key]
                    trade_df = load_stock_data(slot.trade_data_path)
                    if slot.signal_data_path != slot.trade_data_path:
                        signal_df_raw, trade_df = extract_overlap_period(signal_df_raw.copy(), trade_df)

                asset_signal_dfs[key] = signal_df_raw
                asset_trade_dfs[key] = trade_df
                slot_of_key[key] = slot
                asset_of_key[key] = slot.asset_id
                keys.append(key)
        else:
            for asset in method.assets:
                key = position_key(method.method_id, asset.asset_id, multi_method=multi_method)
                signal_df_raw = load_stock_data(asset.signal_data_path)
                trade_df = load_stock_data(asset.trade_data_path)
                if asset.signal_data_path != asset.trade_data_path:
                    signal_df_raw, trade_df = extract_overlap_period(signal_df_raw, trade_df)
                asset_signal_dfs[key] = signal_df_raw
                asset_trade_dfs[key] = trade_df
                asset_of_key[key] = asset.asset_id
                allocator_keys.append(key)
                keys.append(key)
            series_dfs[method.method_id] = {
                series.series_id: load_stock_data(series.data_path) for series in method.signal_series
            }
        keys_by_method[method.method_id] = keys

    # 2. 공통 기간 추출 (전 자산 trade_df 와 신호용 시세의 날짜 교집합)
    # 배분 규칙이 받는 시세(비중변동 매매법 자산의 signal_df · 신호용 시세)는 행이 거래일과 정확히 맞아야
    # 하므로 교집합에 넣는다. 슬롯 signal_df 는 기존 동작대로 넣지 않는다
    date_sets = [set(df[COL_DATE]) for df in asset_trade_dfs.values()]
    date_sets += [set(asset_signal_dfs[key][COL_DATE]) for key in allocator_keys]
    date_sets += [set(df[COL_DATE]) for by_id in series_dfs.values() for df in by_id.values()]
    common_dates_set: set[date] = date_sets[0]
    for ds in date_sets[1:]:
        common_dates_set &= ds

    if not common_dates_set:
        raise ValueError("전 자산의 공통 거래 기간이 없습니다.")

    # 공통 기간으로 필터링
    for key in asset_signal_dfs:
        signal_df = asset_signal_dfs[key]
        trade_df = asset_trade_dfs[key]

        mask_s = pd.Series(signal_df[COL_DATE]).isin(common_dates_set)
        mask_t = pd.Series(trade_df[COL_DATE]).isin(common_dates_set)

        asset_signal_dfs[key] = signal_df[mask_s.values].reset_index(drop=True)
        asset_trade_dfs[key] = trade_df[mask_t.values].reset_index(drop=True)

    for by_id in series_dfs.values():
        for series_id, series_df in by_id.items():
            mask = pd.Series(series_df[COL_DATE]).isin(common_dates_set)
            by_id[series_id] = series_df[mask.values].reset_index(drop=True)

    # 3. 워밍업 구간 (슬롯: registry 의 get_warmup_periods 와 MA 컬럼, 배분 규칙: 판단에 필요한 행 수)
    valid_start_indices: list[int] = []
    for key in asset_signal_dfs:
        slot = slot_of_key.get(key)
        if slot is None:
            continue
        spec = STRATEGY_REGISTRY.get(slot.strategy_id)
        if spec is None:
            raise ValueError(f"미등록 strategy_id: '{slot.strategy_id}'")
        warmup = spec.get_warmup_periods(slot)
        if warmup == 0:
            continue
        ma_col = ma_col_name(slot.ma_window)
        sdf = asset_signal_dfs[key]
        if ma_col not in sdf.columns:
            raise ValueError(f"MA 컬럼 누락: {ma_col} (asset_id={key})")
        valid_mask = sdf[ma_col].notna()
        if valid_mask.any():
            valid_start_indices.append(int(valid_mask.idxmax()))
        else:
            valid_start_indices.append(len(sdf))

    for method in methods:
        if isinstance(method, AllocatorMethodConfig):
            allocator_warmup = ALLOCATOR_REGISTRY[method.allocator_id].get_warmup_periods(method)
            if allocator_warmup > 0:
                valid_start_indices.append(allocator_warmup - 1)

    valid_start = max(valid_start_indices) if valid_start_indices else 0

    return _PortfolioData(
        methods=methods,
        multi_method=multi_method,
        keys_by_method=keys_by_method,
        asset_of_key=asset_of_key,
        slot_of_key=slot_of_key,
        signal_dfs=asset_signal_dfs,
        trade_dfs=asset_trade_dfs,
        series_dfs=series_dfs,
        valid_start=valid_start,
    )


def compute_portfolio_effective_start_date(config: PortfolioConfig) -> date:
    """포트폴리오 실험의 유효 시작일을 계산한다.

    전 자산 데이터의 날짜 교집합을 구하고 buffer_zone 슬롯의 MA 워밍업 · 배분 규칙의 워밍업 완료 이후
    첫 날짜를 반환한다. buy_and_hold 슬롯은 MA 워밍업이 없으므로 valid_start 계산에서 제외.
    각 실험은 자기 자산 조합의 고유 시작일을 사용하므로, 실험마다 결과 기간이
    달라질 수 있다 (CLI 러너에서 이 값을 `run_portfolio_backtest`의 `start_date`로 전달).

    Args:
        config: 포트폴리오 실험 설정

    Returns:
        워밍업 완료 이후 첫 유효 거래일 (date 객체)

    Raises:
        ValueError: 공통 기간 없음 또는 MA 컬럼 누락 시
    """
    validate_portfolio_config(config)
    data = _load_portfolio_data_with_common_period(config)

    first_trade_df = next(iter(data.trade_dfs.values()))
    first_trade_df_filtered = first_trade_df.iloc[data.valid_start :].reset_index(drop=True)

    if len(first_trade_df_filtered) < 1:
        raise ValueError("유효 데이터 부족: MA 워밍업 후 데이터가 없습니다.")

    return date(
        first_trade_df_filtered[COL_DATE].iloc[0].year,
        first_trade_df_filtered[COL_DATE].iloc[0].month,
        first_trade_df_filtered[COL_DATE].iloc[0].day,
    )


def _create_books(
    config: PortfolioConfig,
    data: _PortfolioData,
    allocator_signal_dfs: dict[str, pd.DataFrame],
    allocator_series_dfs: dict[str, dict[str, pd.DataFrame]],
) -> list[MethodBook]:
    """매매법마다 빈 장부를 만든다 (현금 = 총 자본 × 목표 몫, 보유 0, 신호 상태 sell).

    배분 규칙에는 워밍업 · 시작일로 잘리기 전 시세를 준다 — get_warmup_periods 가 약속한 과거 행이 있어야 한다.
    """
    books: list[MethodBook] = []
    for method in data.methods:
        keys = data.keys_by_method[method.method_id]
        book = MethodBook(
            method_id=method.method_id,
            target_share=method.target_weight,
            initial_capital=config.total_capital * method.target_weight,
            asset_of_key={key: data.asset_of_key[key] for key in keys},
            cash=config.total_capital * method.target_weight,
            asset_states={key: AssetState(position=0, signal_state="sell") for key in keys},
            entry_prices={key: 0.0 for key in keys},
            entry_dates={key: None for key in keys},
            entry_hold_days={key: 0 for key in keys},
            realized_pnl={key: 0.0 for key in keys},
            targets={},
        )
        if isinstance(method, SlotMethodConfig):
            book.slots = {key: data.slot_of_key[key] for key in keys}
            book.strategies = {key: create_strategy_for_slot(data.slot_of_key[key]) for key in keys}
            book.targets = {key: data.slot_of_key[key].target_weight for key in keys}
        else:
            book.allocator = ALLOCATOR_REGISTRY[method.allocator_id].create_allocator(method)
            book.targets = {key: 0.0 for key in keys}
            book.allocator_data = {data.asset_of_key[key]: allocator_signal_dfs[key] for key in keys}
            book.allocator_data.update(allocator_series_dfs[method.method_id])
        books.append(book)
    return books


def _execute_into_book(
    book: MethodBook,
    intents: dict[str, OrderIntent],
    open_prices: dict[str, float],
    current_date: date,
) -> ExecutionResult:
    """의도를 매매법 장부에 체결하고(execute_orders) 장부를 갱신한다."""
    result = execute_orders(
        order_intents=intents,
        open_prices=open_prices,
        current_positions=book.positions(),
        current_cash=book.cash,
        entry_prices=book.entry_prices,
        entry_dates=book.entry_dates,
        entry_hold_days=book.entry_hold_days,
        current_date=current_date,
    )
    book.cash = result.updated_cash
    for key, new_pos in result.updated_positions.items():
        book.asset_states[key].position = new_pos
    book.entry_prices = result.updated_entry_prices
    book.entry_dates = result.updated_entry_dates
    book.entry_hold_days = result.updated_entry_hold_days
    for trade in result.new_trades:
        book.realized_pnl[trade["asset_id"]] += trade["pnl"]
    return result


def _plan_book(
    book: MethodBook,
    signal_dfs: dict[str, pd.DataFrame],
    closes: dict[str, float],
    method_equity: float,
    i: int,
    allocator_index: int,
    current_date: date,
    is_month_end: bool,
) -> tuple[dict[str, OrderIntent], dict[str, OrderIntent], ProjectedPortfolio]:
    """매매법의 그날 신호(슬롯 전략 | 배분 규칙) 의도와 예상 상태를 만든다.

    allocator_index 는 배분 규칙 시세(잘리기 전) 안에서 오늘의 행 번호다.

    Returns:
        (진입 · 청산 의도, 배분 규칙의 비중 조정 의도, 예상 상태). 슬롯 매매법은 조정 의도가 없다
    """
    equity_vals = {key: state.position * closes[key] for key, state in book.asset_states.items()}

    if book.allocator is None:
        signal_intents = generate_signal_intents(
            book.asset_states, book.strategies, signal_dfs, equity_vals, book.slots, method_equity, i, current_date
        )
        projected = compute_projected_portfolio(book.asset_states, signal_intents, equity_vals, book.cash)
        return signal_intents, {}, projected

    new_weights = book.allocator.target_weights(book.allocator_data, allocator_index, current_date, is_month_end)
    key_of_asset = {asset_id: key for key, asset_id in book.asset_of_key.items()}
    new_targets = (
        None
        if new_weights is None
        else {key_of_asset.get(asset_id, asset_id): weight for asset_id, weight in new_weights.items()}
    )
    allocation_intents = generate_allocation_intents(
        book.targets, new_targets, book.positions(), equity_vals, method_equity
    )
    if new_targets is not None:
        book.targets = {key: float(new_targets.get(key, 0.0)) for key in book.targets}
    projected = compute_allocation_projection(book.targets, allocation_intents, equity_vals, book.cash)
    signal_intents = {k: v for k, v in allocation_intents.items() if v.intent_type in ("EXIT_ALL", "ENTER_TO_TARGET")}
    adjust_intents = {
        k: v for k, v in allocation_intents.items() if v.intent_type in ("REDUCE_TO_TARGET", "INCREASE_TO_TARGET")
    }
    return signal_intents, adjust_intents, projected


def _book_pnl(book: MethodBook, closes: dict[str, float]) -> float:
    """매매법 누적 손익 = Σ 실현 + Σ 미실현."""
    unrealized = sum(
        (closes[key] - book.entry_prices[key]) * state.position
        for key, state in book.asset_states.items()
        if state.position > 0
    )
    return sum(book.realized_pnl.values()) + unrealized


def _build_params_json(config: PortfolioConfig) -> dict[str, Any]:
    """JSON 저장용 파라미터. 매매법 하나 줄임 표기는 기존 형식 그대로다."""
    params_json: dict[str, Any] = {
        "experiment_name": config.experiment_name,
        "display_name": config.display_name,
        "total_capital": config.total_capital,
        # 리밸런싱 규칙: 엔진 레벨 상수로 고정 (모든 실험에 동일하게 적용됨)
        "rebalance_check_day": "last_trading_day_of_month",
        "rebalance_threshold_rate": DEFAULT_REBALANCE_POLICY.threshold_rate,
    }
    if not config.methods:
        params_json["assets"] = [_slot_params(slot) for slot in config.asset_slots]
        return params_json

    methods_json: list[dict[str, Any]] = []
    for method in config.methods:
        entry: dict[str, Any] = {
            "method_id": method.method_id,
            "display_name": method.display_name,
            "target_weight": method.target_weight,
        }
        if isinstance(method, SlotMethodConfig):
            entry["assets"] = [_slot_params(slot) for slot in method.asset_slots]
        else:
            entry["allocator_id"] = method.allocator_id
            entry["assets"] = [
                {
                    "asset_id": asset.asset_id,
                    "signal_data_path": str(asset.signal_data_path),
                    "trade_data_path": str(asset.trade_data_path),
                }
                for asset in method.assets
            ]
            entry["signal_series"] = [
                {"series_id": series.series_id, "data_path": str(series.data_path)} for series in method.signal_series
            ]
        methods_json.append(entry)
    params_json["methods"] = methods_json
    return params_json


def _slot_params(slot: AssetSlotConfig) -> dict[str, Any]:
    return {
        "asset_id": slot.asset_id,
        "target_weight": slot.target_weight,
        "signal_data_path": str(slot.signal_data_path),
        "trade_data_path": str(slot.trade_data_path),
        "strategy_id": slot.strategy_id,
        "ma_window": slot.ma_window,
        "buy_buffer_zone_pct": slot.buy_buffer_zone_pct,
        "sell_buffer_zone_pct": slot.sell_buffer_zone_pct,
        "hold_days": slot.hold_days,
    }


def run_portfolio_backtest(config: PortfolioConfig, start_date: date | None = None) -> PortfolioResult:
    """포트폴리오 백테스트를 실행한다.

    매매법마다 신호(슬롯 전략 | 배분 규칙) + 목표 비중 배분 + 월말 판단 리밸런싱을 수행하고,
    매매법이 여럿이면 매매법 사이 비중 되돌리기와 종목 단위 상계를 더한다.

    메인 루프 흐름:
        Step A: 체결 — 전 매매법 SELL → 매매법 사이 이전 → 전 매매법 BUY (전일 next_day_intents), 상계 계산
        Step C: Equity 계산 (당일 종가 기준, 매매법별 · 계좌)
        Step D: Signal → Projected → (매매법 사이 판정) → Rebalance → Merge → next_day_intents
        Step E: Equity · State Log · 장부 행 기록

    Args:
        config: 포트폴리오 실험 설정
        start_date: 백테스트 시작일 하한 (None이면 워밍업 완료 시점부터 자동 결정).
            CLI 러너에서는 각 실험의 `compute_portfolio_effective_start_date(config)`
            결과를 전달하여 실험별 독립 기간으로 실행한다.

    Returns:
        PortfolioResult

    Raises:
        ValueError: 설정 검증 실패 또는 공통 기간 없음
    """
    logger.debug(f"포트폴리오 백테스트 시작: {config.experiment_name}")

    # 1. 설정 검증
    validate_portfolio_config(config)

    # 2. 자산별 데이터 로딩 + 공통 기간 필터링 + 워밍업 인덱스 계산
    data = _load_portfolio_data_with_common_period(config)
    valid_start = data.valid_start
    asset_signal_dfs = data.signal_dfs
    asset_trade_dfs = data.trade_dfs

    # 배분 규칙용: 잘리기 전 시세와 거래일 (아래 슬라이싱은 dict 항목을 새 DataFrame 으로 바꿀 뿐 원본을 바꾸지 않는다)
    full_trade_dates = list(next(iter(asset_trade_dfs.values()))[COL_DATE])
    allocator_signal_dfs = dict(asset_signal_dfs)
    allocator_series_dfs = {method_id: dict(by_id) for method_id, by_id in data.series_dfs.items()}

    # 워밍업 구간 슬라이싱
    for key in asset_signal_dfs:
        asset_signal_dfs[key] = asset_signal_dfs[key].iloc[valid_start:].reset_index(drop=True)
        asset_trade_dfs[key] = asset_trade_dfs[key].iloc[valid_start:].reset_index(drop=True)
    for by_id in data.series_dfs.values():
        for series_id in by_id:
            by_id[series_id] = by_id[series_id].iloc[valid_start:].reset_index(drop=True)

    # start_date 필터: 워밍업 완료 이후 추가로 시작일 하한 적용
    if start_date is not None:
        for key in asset_signal_dfs:
            sdf = asset_signal_dfs[key]
            tdf = asset_trade_dfs[key]
            mask_s = pd.Series(sdf[COL_DATE]) >= start_date
            mask_t = pd.Series(tdf[COL_DATE]) >= start_date
            asset_signal_dfs[key] = sdf[mask_s.values].reset_index(drop=True)
            asset_trade_dfs[key] = tdf[mask_t.values].reset_index(drop=True)
        for by_id in data.series_dfs.values():
            for series_id in by_id:
                series_df = by_id[series_id]
                mask = pd.Series(series_df[COL_DATE]) >= start_date
                by_id[series_id] = series_df[mask.values].reset_index(drop=True)

    n = len(next(iter(asset_trade_dfs.values())))
    if n < 2:
        raise ValueError(f"유효 데이터 부족: {n}행 (최소 2행 필요)")

    trade_dates = list(next(iter(asset_trade_dfs.values()))[COL_DATE])
    allocator_offset = full_trade_dates.index(trade_dates[0])

    # 3. 매매법 장부 (매매법이 하나면 장부 = 계좌)
    books = _create_books(config, data, allocator_signal_dfs, allocator_series_dfs)
    target_shares = {book.method_id: book.target_share for book in books}
    multi_method = data.multi_method
    keys_of_asset: dict[str, list[str]] = {}
    for key, asset_id in data.asset_of_key.items():
        keys_of_asset.setdefault(asset_id, []).append(key)

    # 상계 절감 누적 — 매매법에 나누지 않고 계좌 현금으로 둔다
    netting_savings = 0.0

    # 거래 기록 및 에쿼티 기록
    all_trades: list[Any] = []
    equity_rows: list[dict[str, Any]] = []
    state_log_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    netting_rows: list[dict[str, Any]] = []

    # 4. 메인 루프: 전일 intents 체결 → 당일 에쿼티 → 당일 signal → projected → rebalance → merge
    # 신호와 체결을 하루씩 분리(Lookahead 방지): i일 종가 시그널 → i+1일 시가 체결
    for i in range(0, n):
        current_date = trade_dates[i]

        # Step A: SELL → 이전 → BUY 순 체결 (SELL 확보 현금 → BUY에 활용, 부족 시 비례 축소)
        # state_log용: 체결 예정 intents + 체결 전 포지션 보관
        open_prices_map: dict[str, float] = {
            key: float(asset_trade_dfs[key].iloc[i][COL_OPEN]) for key in asset_trade_dfs
        }
        intents_executed_today: dict[str, dict[str, OrderIntent]] = {}
        pre_exec_positions: dict[str, dict[str, int]] = {}
        new_trades_by_book: dict[str, list[PortfolioTradeRecord]] = {}
        rebalanced_by_book: dict[str, bool] = {}
        reason_by_book: dict[str, str] = {}
        # 오늘 체결이 맞추려던 목표 비중 (오늘 판단에서 바뀌기 전 값 — 상태 로그 · 검사기 규칙 2 가 쓴다)
        targets_in_effect = {book.method_id: dict(book.targets) for book in books}

        for book in books:
            intents_executed_today[book.method_id] = dict(book.next_day_intents)
            pre_exec_positions[book.method_id] = book.positions()
            reason_by_book[book.method_id] = book.next_day_reason
            sell_intents = {k: v for k, v in book.next_day_intents.items() if v.intent_type in _SELL_INTENT_TYPES}
            sell_result = _execute_into_book(book, sell_intents, open_prices_map, current_date)
            new_trades_by_book[book.method_id] = list(sell_result.new_trades)
            rebalanced_by_book[book.method_id] = sell_result.rebalanced_today

        planned_transfers = {book.method_id: book.next_day_transfer for book in books}
        transferred: dict[str, float] = {book.method_id: 0.0 for book in books}
        if any(amount != 0.0 for amount in planned_transfers.values()):
            transferred = cap_transfers(planned_transfers, {book.method_id: book.cash for book in books})
            for book in books:
                book.cash += transferred[book.method_id]
                book.transfers += transferred[book.method_id]

        for book in books:
            buy_intents = {k: v for k, v in book.next_day_intents.items() if v.intent_type in _BUY_INTENT_TYPES}
            buy_result = _execute_into_book(book, buy_intents, open_prices_map, current_date)
            new_trades_by_book[book.method_id].extend(buy_result.new_trades)
            rebalanced_by_book[book.method_id] = (
                rebalanced_by_book[book.method_id] or buy_result.rebalanced_today or transferred[book.method_id] != 0.0
            )
            # 단독 매매로 매긴 비용(C안 장부 비용): 주수 변화 × 시가 × SLIPPAGE_RATE
            pre = pre_exec_positions[book.method_id]
            book.cost += sum(
                abs(state.position - pre[key]) * open_prices_map[key] * SLIPPAGE_RATE
                for key, state in book.asset_states.items()
            )
            all_trades.extend(new_trades_by_book[book.method_id])
            book.next_day_transfer = 0.0

        # 종목 단위 상계: 같은 자산을 둘 이상의 매매법이 든 경우만
        if multi_method:
            for asset_id, keys in keys_of_asset.items():
                if len(keys) < 2:
                    continue
                deltas = [
                    book.asset_states[key].position - pre_exec_positions[book.method_id][key]
                    for book in books
                    for key in keys
                    if key in book.asset_states
                ]
                netting = compute_netting(deltas, open_prices_map[keys[0]])
                if netting.gross_shares > abs(netting.net_shares):
                    netting_savings += netting.savings
                    netting_rows.append(
                        {
                            COL_DATE: current_date,
                            "asset_id": asset_id,
                            "gross_shares": netting.gross_shares,
                            "net_shares": netting.net_shares,
                            "open_price": open_prices_map[keys[0]],
                            "savings": netting.savings,
                        }
                    )

        rebalanced_today = any(rebalanced_by_book.values())
        rebalance_reason_today = next(
            (reason_by_book[book.method_id] for book in books if rebalanced_by_book[book.method_id]), ""
        )

        # Step C: 에쿼티 계산 (체결 완료 후, 당일 종가 기준)
        # 체결 후에 계산해야 리밸런싱 판정 시 목표 비중 편차가 정확히 반영된다
        asset_closes_map: dict[str, float] = {
            key: float(asset_trade_dfs[key].iloc[i][COL_CLOSE]) for key in asset_trade_dfs
        }
        method_equity = {
            book.method_id: compute_portfolio_equity(book.cash, book.positions(), asset_closes_map) for book in books
        }
        current_equity = sum(method_equity.values()) + netting_savings
        shared_cash = sum(book.cash for book in books) + netting_savings

        # Step D: Signal → Projected → (매매법 사이 판정) → Rebalance → Merge (익일 체결용 intents 생성)
        is_month_end = is_last_trading_day_of_month(trade_dates, i)
        plans = {
            book.method_id: _plan_book(
                book,
                asset_signal_dfs,
                asset_closes_map,
                method_equity[book.method_id],
                i,
                i + allocator_offset,
                current_date,
                is_month_end,
            )
            for book in books
        }

        # 매매법 사이 판정 (월 마지막 거래일, 매매법이 여럿일 때)
        method_transfers: dict[str, float] | None = None
        if multi_method and is_month_end:
            method_transfers = plan_method_transfers(
                method_equity, target_shares, DEFAULT_REBALANCE_POLICY.threshold_rate
            )

        signal_intents_by_book: dict[str, dict[str, OrderIntent]] = {}
        for book in books:
            signal_intents, adjust_intents, projected = plans[book.method_id]
            signal_intents_by_book[book.method_id] = signal_intents
            total_equity_projected = projected.projected_cash + sum(projected.projected_amounts.values())

            if method_transfers is not None:
                # 매매법 사이 되돌리기: 이전액을 예상 현금에 더하고 보유 종목 전부를 새 몫으로 맞춘다
                transfer = method_transfers[book.method_id]
                projected.projected_cash += transfer
                rebalance_intents = DEFAULT_REBALANCE_POLICY.build_rebalance_intents(
                    projected, book.targets, total_equity_projected + transfer, current_date
                )
                book.next_day_reason = _REBALANCE_REASON_METHODS
                book.next_day_transfer = transfer
            elif is_month_end and DEFAULT_REBALANCE_POLICY.should_rebalance(
                projected, book.targets, total_equity_projected
            ):
                rebalance_intents = DEFAULT_REBALANCE_POLICY.build_rebalance_intents(
                    projected, book.targets, total_equity_projected, current_date
                )
                book.next_day_reason = _REBALANCE_REASON_MONTHLY
            else:
                rebalance_intents = {}
                book.next_day_reason = ""

            # signal + rebalance 통합 (리밸런싱이 걸리면 배분 규칙의 조정 의도 대신 리밸런싱 의도)
            merged_intents = merge_intents(signal_intents, rebalance_intents if rebalance_intents else adjust_intents)

            # signal_state 업데이트 (EXIT_ALL → "sell", ENTER_TO_TARGET → "buy")
            for key, intent in merged_intents.items():
                if intent.intent_type == "EXIT_ALL":
                    book.asset_states[key].signal_state = "sell"
                elif intent.intent_type == "ENTER_TO_TARGET":
                    book.asset_states[key].signal_state = "buy"

            book.next_day_intents = merged_intents

        # Step E: 에쿼티 행 기록 (자산별 value/weight/signal/shares/avg_price 포함)
        row: dict[str, Any] = {
            COL_DATE: current_date,
            COL_EQUITY: current_equity,
            "cash": shared_cash,
            "rebalanced": rebalanced_today,
            "rebalance_reason": rebalance_reason_today,
        }
        if multi_method:
            row["netting_savings"] = netting_savings
        for book in books:
            for key, st in book.asset_states.items():
                val = st.position * asset_closes_map[key]
                row[asset_value_col(key)] = val
                row[asset_weight_col(key)] = val / (current_equity + EPSILON) if current_equity > 0 else 0.0
                row[f"{key}_signal"] = st.signal_state
                row[asset_shares_col(key)] = st.position
                row[f"{key}_avg_price"] = book.entry_prices[key]
                # 자산별 손익 추적 (매도 후에도 기여 이력 유지)
                row[f"{key}_realized_pnl"] = book.realized_pnl[key]
                unrealized = (asset_closes_map[key] - book.entry_prices[key]) * st.position if st.position > 0 else 0.0
                row[f"{key}_unrealized_pnl"] = unrealized
        equity_rows.append(row)

        # Step F: state_log 행 수집 (디버깅/검증용, 비즈니스 로직 변경 없음)
        state_row: dict[str, Any] = {
            COL_DATE: current_date,
            COL_EQUITY: current_equity,
            "cash": shared_cash,
            "is_month_end": is_month_end,
            "rebalanced": rebalanced_today,
            "rebalance_reason": rebalance_reason_today,
        }
        for book in books:
            _append_state_log_columns(
                state_row,
                book,
                signal_intents_by_book[book.method_id],
                intents_executed_today[book.method_id],
                pre_exec_positions[book.method_id],
                new_trades_by_book[book.method_id],
                open_prices_map,
                asset_closes_map,
                current_equity,
                targets_in_effect[book.method_id],
            )
        state_log_rows.append(state_row)

        # 장부 행 (매매법별)
        total_method_equity = sum(method_equity.values())
        for book in books:
            book_rebalanced = rebalanced_by_book[book.method_id]
            ledger_rows.append(
                {
                    COL_DATE: current_date,
                    "method_id": book.method_id,
                    "equity": method_equity[book.method_id],
                    "cash": book.cash,
                    "share": method_equity[book.method_id] / total_method_equity,
                    "target_share": book.target_share,
                    "pnl": _book_pnl(book, asset_closes_map),
                    "cost": book.cost,
                    "transfers": book.transfers,
                    "rebalanced": book_rebalanced,
                    "rebalance_reason": reason_by_book[book.method_id] if book_rebalanced else "",
                }
            )

    # 5. 결과 조합
    equity_df = build_combined_equity(equity_rows, config.total_capital)

    # trades_df 정리
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
    else:
        trades_df = pd.DataFrame(
            columns=[
                COL_ENTRY_DATE,
                COL_EXIT_DATE,
                COL_ENTRY_PRICE,
                COL_EXIT_PRICE,
                COL_SHARES,
                COL_PNL,
                COL_PNL_PCT,
                COL_HOLD_DAYS_USED,
                "asset_id",
                "trade_type",
            ]
        )

    # 성과 요약 (합산 에쿼티 기준)
    summary = calculate_summary(trades_df, equity_df, config.total_capital)

    # 자산별 결과 (자산 키 단위)
    per_asset: list[PortfolioAssetResult] = []
    for book in books:
        for key in book.asset_states:
            asset_trades = trades_df[trades_df["asset_id"] == key] if len(trades_df) > 0 else pd.DataFrame()
            per_asset.append(
                PortfolioAssetResult(
                    asset_id=key,
                    trades_df=asset_trades,
                    signal_df=asset_signal_dfs[key],
                )
            )

    params_json = _build_params_json(config)

    logger.debug(
        f"포트폴리오 백테스트 완료: {config.experiment_name}, " f"총 거래={len(trades_df)}, 총 수익률={summary['total_return_pct']:.2f}%"
    )

    # state_log DataFrame 구성
    state_log_df = pd.DataFrame(state_log_rows) if state_log_rows else pd.DataFrame()

    return PortfolioResult(
        experiment_name=config.experiment_name,
        display_name=config.display_name,
        equity_df=equity_df,
        trades_df=trades_df,
        summary=summary,
        per_asset=per_asset,
        config=config,
        params_json=params_json,
        state_log_df=state_log_df,
        ledger_df=pd.DataFrame(ledger_rows),
        netting_df=pd.DataFrame(netting_rows, columns=_NETTING_COLUMNS),
    )


def _append_state_log_columns(
    state_row: dict[str, Any],
    book: MethodBook,
    signal_intents: dict[str, OrderIntent],
    intents_executed: dict[str, OrderIntent],
    pre_exec_positions: dict[str, int],
    new_trades: list[PortfolioTradeRecord],
    open_prices_map: dict[str, float],
    asset_closes_map: dict[str, float],
    current_equity: float,
    targets_in_effect: dict[str, float],
) -> None:
    """매매법 장부의 자산 키별 state_log 컬럼을 state_row 에 채운다.

    당일 체결: intents_executed(전일 결정) + new_trades(매도) + 포지션 변화(매수).
    처리한 의도는 1주 미만이라 0주로 끝나도 기록한다 — 검사기 규칙 1(다음 날 처리)이 이 기록을 본다.
    """
    executed_trades_by_key: dict[str, list[PortfolioTradeRecord]] = {}
    for trade in new_trades:
        executed_trades_by_key.setdefault(trade["asset_id"], []).append(trade)

    for key, st in book.asset_states.items():
        close_val = asset_closes_map[key]
        val = st.position * close_val
        weight = val / (current_equity + EPSILON) if current_equity > 0 else 0.0

        state_row[asset_close_col(key)] = close_val
        state_row[asset_shares_col(key)] = st.position
        state_row[asset_weight_col(key)] = weight

        # 당일 시그널 판정: signal_intents에서 추출
        signal_intent = signal_intents.get(key)
        if signal_intent and signal_intent.intent_type == "EXIT_ALL":
            state_row[asset_signal_today_col(key)] = "sell"
        elif signal_intent and signal_intent.intent_type == "ENTER_TO_TARGET":
            state_row[asset_signal_today_col(key)] = "buy"
        else:
            state_row[asset_signal_today_col(key)] = "hold"

        # 익일 체결 예정 (merged_intents)
        pending = book.next_day_intents.get(key)
        state_row[asset_pending_intent_col(key)] = pending.intent_type if pending else ""
        state_row[f"{key}_pending_reason"] = pending.reason if pending else ""
        state_row[f"{key}_pending_delta"] = pending.delta_amount if pending else 0.0

        # 당일 체결 결과
        intent_executed = intents_executed.get(key)
        trades_for_key = executed_trades_by_key.get(key, [])
        if intent_executed:
            is_sell = intent_executed.intent_type in _SELL_INTENT_TYPES
            if is_sell:
                # 매도: new_trades에서 체결 상세 추출
                total_shares = sum(int(t["shares"]) for t in trades_for_key)
                exec_price = float(trades_for_key[0]["exit_price"]) if trades_for_key else 0.0
            else:
                # 매수: 포지션 변화에서 추출
                total_shares = abs(st.position - pre_exec_positions[key])
                exec_price = open_prices_map[key] if total_shares > 0 else 0.0
            state_row[asset_executed_intent_col(key)] = intent_executed.intent_type
            state_row[f"{key}_exec_side"] = "sell" if is_sell else "buy"
            state_row[f"{key}_exec_shares"] = total_shares
            state_row[f"{key}_exec_price"] = exec_price
        else:
            state_row[asset_executed_intent_col(key)] = ""
            state_row[f"{key}_exec_side"] = ""
            state_row[f"{key}_exec_shares"] = 0
            state_row[f"{key}_exec_price"] = 0.0

        if book.allocator is not None:
            state_row[f"{key}_target_weight"] = targets_in_effect[key]
