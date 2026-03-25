"""단일 백테스트 엔진

단일 자산 버퍼존 전략 백테스트 및 그리드 서치를 제공한다.
SignalStrategy Protocol을 통해 전략을 의존성 주입 방식으로 사용한다.

주요 함수:
- run_backtest: 전략 객체를 받아 단일 백테스트를 실행
- run_grid_search: 파라미터 그리드 탐색 (병렬 처리)
- run_buffer_strategy: BufferStrategyParams 기반 버퍼존 백테스트 편의 래퍼
"""

import os
from datetime import date
from typing import TypedDict

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average, calculate_summary
from qbt.backtest.constants import (
    CALMAR_MDD_ZERO_SUBSTITUTE,
    COL_BUY_BUFFER_ZONE_PCT,
    COL_CAGR,
    COL_CALMAR,
    COL_FINAL_CAPITAL,
    COL_HOLD_DAYS,
    COL_MA_WINDOW,
    COL_MDD,
    COL_SELL_BUFFER_ZONE_PCT,
    COL_TOTAL_RETURN_PCT,
    COL_TOTAL_TRADES,
    COL_WIN_RATE,
    DEFAULT_BUFFER_MA_TYPE,
    DEFAULT_INITIAL_CAPITAL,
    MIN_BUY_BUFFER_ZONE_PCT,
    MIN_HOLD_DAYS,
    MIN_SELL_BUFFER_ZONE_PCT,
    MIN_VALID_ROWS,
)
from qbt.backtest.engines.engine_common import (
    EquityRecord,
    PendingOrder,
    TradeRecord,
    execute_buy_order,
    execute_sell_order,
    record_equity,
)
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.strategy_common import (
    PendingOrderConflictError,
    SignalStrategy,
)
from qbt.backtest.types import BufferStrategyParams, SummaryDict
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_OPEN,
    EPSILON,
)
from qbt.utils import get_logger
from qbt.utils.parallel_executor import WORKER_CACHE, execute_parallel_with_kwargs, init_worker_cache

logger = get_logger(__name__)


# ============================================================================
# TypedDict
# ============================================================================


class GridSearchResult(TypedDict):
    """_run_backtest_for_grid() 반환 타입.

    키 이름은 backtest/constants.py의 COL_* 상수 값과 동일하다.
    """

    ma_window: int
    buy_buffer_zone_pct: float
    sell_buffer_zone_pct: float
    hold_days: int
    total_return_pct: float
    cagr: float
    mdd: float
    calmar: float
    total_trades: int
    win_rate: float
    final_capital: float


# ============================================================================
# 내부 헬퍼
# ============================================================================


def _validate_backtest_inputs(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
) -> None:
    """백테스트 입력 데이터를 검증한다.

    Args:
        signal_df: 시그널용 DataFrame
        trade_df: 매매용 DataFrame

    Raises:
        ValueError: 검증 실패 시
    """
    # 1. signal_df 필수 컬럼 확인
    signal_required = [COL_DATE, COL_CLOSE]
    signal_missing = set(signal_required) - set(signal_df.columns)
    if signal_missing:
        raise ValueError(f"signal_df 필수 컬럼 누락: {signal_missing}")

    # 2. trade_df 필수 컬럼 확인
    trade_required = [COL_DATE, COL_OPEN, COL_CLOSE]
    trade_missing = set(trade_required) - set(trade_df.columns)
    if trade_missing:
        raise ValueError(f"trade_df 필수 컬럼 누락: {trade_missing}")

    # 3. 날짜 정렬 일치 검증
    signal_dates = list(signal_df[COL_DATE])
    trade_dates = list(trade_df[COL_DATE])
    if signal_dates != trade_dates:
        raise ValueError("signal_df와 trade_df의 날짜가 일치하지 않습니다")


def _check_pending_conflict(
    pending_order: PendingOrder | None,
    signal_type: str,
    current_date: date,
) -> None:
    """Pending order 충돌을 검사한다 (Critical Invariant).

    Args:
        pending_order: 현재 pending order
        signal_type: 발생한 신호 타입
        current_date: 현재 날짜

    Raises:
        PendingOrderConflictError: pending이 이미 존재하는 경우
    """
    if pending_order is not None:
        raise PendingOrderConflictError(
            f"Pending order 충돌 감지: 기존 pending(type={pending_order.order_type}, "
            f"signal_date={pending_order.signal_date}) "
            f"존재 중 신규 {signal_type} 신호 발생(current_date={current_date})"
        )


# ============================================================================
# 그리드 서치 병렬 헬퍼 (module-level, pickle 가능)
# ============================================================================


def _run_backtest_for_grid(
    params: BufferStrategyParams,
) -> GridSearchResult:
    """그리드 서치를 위해 단일 파라미터 조합에 대해 백테스트를 실행한다.

    병렬 실행을 위한 헬퍼 함수. 예외 발생 시 즉시 전파한다.
    signal_df, trade_df는 WORKER_CACHE에서 조회한다.
    signal_df에는 해당 ma_window 컬럼이 사전 계산되어 있어야 한다.

    Args:
        params: 전략 파라미터

    Returns:
        성과 지표 딕셔너리

    Raises:
        예외 발생 시 즉시 전파
    """
    # WORKER_CACHE에서 DataFrame 조회
    signal_df = WORKER_CACHE["signal_df"]
    trade_df = WORKER_CACHE["trade_df"]

    # MA 컬럼 기준으로 유효 행 필터링
    ma_col = f"ma_{params.ma_window}"
    valid_mask = signal_df[ma_col].notna()
    filtered_signal = signal_df[valid_mask].reset_index(drop=True)
    filtered_trade = trade_df[valid_mask].reset_index(drop=True)

    # BufferZoneStrategy 생성 (파라미터 포함)
    strategy = BufferZoneStrategy(
        ma_col=ma_col,
        buy_buffer_pct=params.buy_buffer_zone_pct,
        sell_buffer_pct=params.sell_buffer_zone_pct,
        hold_days=params.hold_days,
    )

    _, _, summary = run_backtest(strategy, filtered_signal, filtered_trade, params.initial_capital, log_trades=False)

    # Calmar 계산 (CAGR / |MDD|, MDD=0 안전 처리)
    cagr = summary["cagr"]
    abs_mdd = abs(summary["mdd"])
    if abs_mdd < EPSILON:
        calmar = CALMAR_MDD_ZERO_SUBSTITUTE + cagr if cagr > 0 else 0.0
    else:
        calmar = cagr / abs_mdd

    result: GridSearchResult = {
        COL_MA_WINDOW: params.ma_window,
        COL_BUY_BUFFER_ZONE_PCT: params.buy_buffer_zone_pct,
        COL_SELL_BUFFER_ZONE_PCT: params.sell_buffer_zone_pct,
        COL_HOLD_DAYS: params.hold_days,
        COL_TOTAL_RETURN_PCT: summary["total_return_pct"],
        COL_CAGR: summary["cagr"],
        COL_MDD: summary["mdd"],
        COL_CALMAR: calmar,
        COL_TOTAL_TRADES: summary["total_trades"],
        COL_WIN_RATE: summary["win_rate"],
        COL_FINAL_CAPITAL: summary["final_capital"],
    }

    return result


# ============================================================================
# 핵심 함수
# ============================================================================


def run_backtest(
    strategy: SignalStrategy,
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    initial_capital: float,
    log_trades: bool = True,
    strategy_name: str = "",
    params_schedule: dict[date, SignalStrategy] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, SummaryDict]:
    """전략 객체를 받아 단일 자산 백테스트를 실행한다.

    롱 온리, 최대 1 포지션 전략을 사용한다.
    signal_df로 시그널을 생성하고, trade_df로 실제 매수/매도를 수행한다.
    strategy.check_buy(), strategy.check_sell()로 신호를 감지한다.

    핵심 실행 규칙:
    - 시그널: signal_df의 close vs 전략 내부 MA/밴드 계산
    - 체결: trade_df의 open (다음 날 시가)
    - equity = cash + position * trade_df.close (모든 시점)
    - final_capital = 마지막 equity (평가액 포함)
    - pending_order: 단일 슬롯 (충돌 시 PendingOrderConflictError)

    MA 필터링 책임:
    - 호출자가 유효 데이터 구간(MA 워밍업 이후)으로 signal_df/trade_df를 사전 필터링해야 한다.
    - run_backtest 자체는 전달받은 데이터를 그대로 사용한다.

    Args:
        strategy: SignalStrategy Protocol을 구현한 전략 객체
        signal_df: 시그널용 DataFrame (전략에 필요한 MA 컬럼 포함, 사전 필터링됨)
        trade_df: 매매용 DataFrame (체결가: Open, 에쿼티: Close)
        initial_capital: 초기 자본금
        log_trades: 거래 로그 출력 여부 (기본값: True)
        strategy_name: 전략 식별 이름 (기본값: "")
        params_schedule: 구간별 전략 전환 스케줄 (기본값: None)
            {date: SignalStrategy} 형태. 해당 날짜부터 새 전략 객체로 교체.
            None이면 단일 전략으로 전체 기간 실행.

    Returns:
        tuple: (trades_df, equity_df, summary)
            - trades_df: 거래 내역 DataFrame
            - equity_df: 자본 곡선 DataFrame
            - summary: 요약 지표 딕셔너리 (SummaryDict)

    Raises:
        ValueError: 필수 컬럼 누락 또는 데이터 부족 시
        PendingOrderConflictError: pending 존재 중 신규 신호 발생 시 (Critical Invariant 위반)
    """
    if log_trades:
        logger.debug(f"백테스트 실행 시작: strategy_name={strategy_name!r}, initial_capital={initial_capital}")

    # 1. 데이터 검증
    _validate_backtest_inputs(signal_df, trade_df)

    if len(signal_df) < MIN_VALID_ROWS:
        raise ValueError(f"유효 데이터 부족: {len(signal_df)}행 (최소 {MIN_VALID_ROWS}행 필요)")

    # 2. params_schedule 날짜 목록 사전 정렬
    sorted_switch_dates: list[date] = []
    next_switch_idx = 0
    if params_schedule is not None:
        sorted_switch_dates = sorted(params_schedule.keys())

    # 3. 초기화
    capital = initial_capital
    position = 0
    entry_price = 0.0
    entry_date: date | None = None

    trades: list[TradeRecord] = []
    equity_records: list[EquityRecord] = []
    pending_order: PendingOrder | None = None

    # 매수 체결 시 엔진 로컬 상태 (strategy.get_buy_meta()에서 갱신)
    entry_buy_buffer_pct: float = 0.0
    entry_hold_days_used: int = 0

    # 4. 백테스트 루프 (Day 0부터 시작 — B&H 첫 매수 타이밍 fix)
    # 시그널: signal_df의 close, MA → 전략 내부에서 밴드/돌파 감지
    # 체결: trade_df의 open → 매수/매도 체결가
    # 에쿼티: trade_df의 close → 포지션 평가
    for i in range(0, len(signal_df)):
        signal_row = signal_df.iloc[i]
        trade_row = trade_df.iloc[i]
        current_date = signal_row[COL_DATE]

        # 4-0. params_schedule 전환 체크 (strategy 객체 직접 교체)
        if params_schedule is not None and next_switch_idx < len(sorted_switch_dates):
            if current_date >= sorted_switch_dates[next_switch_idx]:
                strategy = params_schedule[sorted_switch_dates[next_switch_idx]]
                next_switch_idx += 1
                if log_trades:
                    logger.debug(f"전략 교체: {current_date}")

        # 4-1. 예약된 주문 실행 (trade_df의 오늘 시가로 체결)
        if pending_order is not None:
            if pending_order.order_type == "buy" and position == 0:
                position, capital, entry_price, entry_date, success = execute_buy_order(
                    pending_order, float(trade_row[COL_OPEN]), current_date, capital, position
                )
                if success and log_trades:
                    logger.debug(
                        f"매수 체결: {entry_date}, 가격={entry_price:.2f}, " f"수량={position}, 매수버퍼={entry_buy_buffer_pct:.2%}"
                    )

            elif pending_order.order_type == "sell" and position > 0:
                assert entry_date is not None, "포지션이 있으면 entry_date는 None이 아니어야 함"
                position, capital, trade_record = execute_sell_order(
                    pending_order,
                    float(trade_row[COL_OPEN]),
                    current_date,
                    capital,
                    position,
                    entry_price,
                    entry_date,
                    hold_days_used=entry_hold_days_used,
                    buy_buffer_pct=entry_buy_buffer_pct,
                )
                trades.append(trade_record)
                if log_trades:
                    logger.debug(f"매도 체결: {current_date}, 손익률={trade_record['pnl_pct']*100:.2f}%")

            pending_order = None

        # 4-2. 에쿼티 기록 (trade_df의 종가로 평가)
        equity_record = record_equity(
            current_date=current_date,
            capital=capital,
            position=position,
            close_price=float(trade_row[COL_CLOSE]),
        )
        equity_records.append(equity_record)

        # 4-3. 신호 감지 및 주문 예약 (signal_df 기준, 전략 내부에서 처리)
        if position == 0:
            # 매수 로직 — strategy.check_buy()에 위임 (내부 prev 상태 갱신 포함)
            buy = strategy.check_buy(signal_df, i, current_date)

            if buy:
                # 매수 신호: get_buy_meta()로 메타데이터 수집 → 엔진 로컬 상태 갱신
                meta = strategy.get_buy_meta()
                entry_buy_buffer_pct = float(meta.get("buy_buffer_pct", 0.0))
                entry_hold_days_used = int(meta.get("hold_days_used", 0))

                _check_pending_conflict(pending_order, "buy", current_date)
                pending_order = PendingOrder(
                    order_type="buy",
                    signal_date=current_date,
                )

        elif position > 0:
            # 매도 로직 — strategy.check_sell()에 위임 (내부 prev 상태 갱신 포함)
            sell = strategy.check_sell(signal_df, i)

            if sell:
                _check_pending_conflict(pending_order, "sell", current_date)
                pending_order = PendingOrder(
                    order_type="sell",
                    signal_date=current_date,
                )

    # 5. 백테스트 종료 (강제청산 없음)
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_records)

    # 6. 요약 지표 계산
    summary = calculate_summary(trades_df, equity_df, initial_capital)

    # 7. 미청산 포지션 정보 기록
    if position > 0 and entry_date is not None:
        summary["open_position"] = {
            "entry_date": str(entry_date),
            "entry_price": round(entry_price, 6),
            "shares": position,
        }

    if log_trades:
        logger.debug(f"백테스트 완료: 총 거래={summary['total_trades']}, 총 수익률={summary['total_return_pct']:.2f}%")

    return trades_df, equity_df, summary


def run_grid_search(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    ma_window_list: list[int],
    buy_buffer_zone_pct_list: list[float],
    sell_buffer_zone_pct_list: list[float],
    hold_days_list: list[int],
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> pd.DataFrame:
    """버퍼존 전략 파라미터 그리드 탐색을 수행한다.

    모든 파라미터 조합에 대해 EMA 기반 버퍼존 전략을 실행하고
    성과 지표를 기록한다.

    Args:
        signal_df: 시그널용 DataFrame (MA 계산 대상)
        trade_df: 매매용 DataFrame (체결가: Open, 에쿼티: Close)
        ma_window_list: 이동평균 기간 목록
        buy_buffer_zone_pct_list: 매수 버퍼존 비율 목록
        sell_buffer_zone_pct_list: 매도 버퍼존 비율 목록
        hold_days_list: 유지조건 일수 목록
        initial_capital: 초기 자본금

    Returns:
        그리드 탐색 결과 DataFrame (각 조합별 성과 지표 포함)
    """
    logger.debug(
        f"그리드 탐색 시작: "
        f"ma_window={ma_window_list}, buy_buffer_zone_pct={buy_buffer_zone_pct_list}, "
        f"sell_buffer_zone_pct={sell_buffer_zone_pct_list}, "
        f"hold_days={hold_days_list}"
    )

    # 1. signal_df에 모든 이동평균 기간에 대해 EMA 미리 계산
    signal_df = signal_df.copy()
    trade_df = trade_df.copy()
    logger.debug(f"이동평균 사전 계산 (EMA): {sorted(ma_window_list)}")

    for window in ma_window_list:
        signal_df = add_single_moving_average(signal_df, window, ma_type=DEFAULT_BUFFER_MA_TYPE)

    logger.debug("이동평균 사전 계산 완료")

    # 2. 파라미터 조합 생성
    param_combinations: list[dict[str, BufferStrategyParams]] = []

    for ma_window in ma_window_list:
        for buy_buffer_zone_pct in buy_buffer_zone_pct_list:
            for sell_buffer_zone_pct in sell_buffer_zone_pct_list:
                for hold_days in hold_days_list:
                    param_combinations.append(
                        {
                            "params": BufferStrategyParams(
                                ma_window=ma_window,
                                buy_buffer_zone_pct=buy_buffer_zone_pct,
                                sell_buffer_zone_pct=sell_buffer_zone_pct,
                                hold_days=hold_days,
                                initial_capital=initial_capital,
                            ),
                        }
                    )

    logger.debug(f"총 {len(param_combinations)}개 조합 병렬 실행 시작 (DataFrame 캐시 사용)")

    # 3. 병렬 실행 (signal_df, trade_df를 워커 캐시에 저장)
    raw_count = os.cpu_count()
    cpu_count = raw_count - 1 if raw_count is not None else None
    results = execute_parallel_with_kwargs(
        func=_run_backtest_for_grid,
        inputs=param_combinations,
        max_workers=cpu_count,
        initializer=init_worker_cache,
        initargs=({"signal_df": signal_df, "trade_df": trade_df},),
    )

    # 4. 딕셔너리 리스트를 DataFrame으로 변환
    results_df = pd.DataFrame(results)

    # 5. Calmar 기준 내림차순 정렬
    results_df = results_df.sort_values(by=COL_CALMAR, ascending=False).reset_index(drop=True)

    logger.debug(f"그리드 탐색 완료: {len(results_df)}개 조합 테스트됨")

    return results_df


def run_buffer_strategy(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    params: BufferStrategyParams,
    log_trades: bool = True,
    strategy_name: str = "buffer_zone",
    params_schedule: dict[date, SignalStrategy] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, SummaryDict]:
    """버퍼존 전략으로 백테스트를 실행한다.

    `BufferStrategyParams`를 받아 내부에서 `BufferZoneStrategy`를 생성하고
    `run_backtest`를 호출하는 편의 래퍼.

    초기 MA 계산 및 유효 구간 필터링을 내부에서 수행한다.
    params_schedule에 포함된 전략들의 MA 컬럼은 호출자가 사전 계산해야 한다.

    Args:
        signal_df: 시그널용 DataFrame (초기 MA 사전 계산 불필요, 내부에서 처리)
        trade_df: 매매용 DataFrame (체결가: Open, 에쿼티: Close)
        params: 전략 파라미터 (초기 구간 파라미터)
        log_trades: 거래 로그 출력 여부 (기본값: True)
        strategy_name: 전략 식별 이름 (기본값: "buffer_zone")
        params_schedule: 구간별 전략 전환 스케줄 (기본값: None)
            {date: SignalStrategy} 형태. 해당 날짜부터 해당 전략 객체로 교체.
            포함된 전략이 사용하는 MA 컬럼은 signal_df에 사전 계산되어 있어야 한다.

    Returns:
        tuple: (trades_df, equity_df, summary)

    Raises:
        ValueError: 파라미터 검증 실패 또는 필수 컬럼 누락 시
        PendingOrderConflictError: pending 존재 중 신규 신호 발생 시 (Critical Invariant 위반)
    """
    # 1. 파라미터 검증
    if params.ma_window < 1:
        raise ValueError(f"ma_window는 1 이상이어야 합니다: {params.ma_window}")
    if params.buy_buffer_zone_pct < MIN_BUY_BUFFER_ZONE_PCT:
        raise ValueError(f"buy_buffer_zone_pct는 {MIN_BUY_BUFFER_ZONE_PCT} 이상이어야 합니다: {params.buy_buffer_zone_pct}")
    if params.sell_buffer_zone_pct < MIN_SELL_BUFFER_ZONE_PCT:
        raise ValueError(f"sell_buffer_zone_pct는 {MIN_SELL_BUFFER_ZONE_PCT} 이상이어야 합니다: {params.sell_buffer_zone_pct}")
    if params.hold_days < MIN_HOLD_DAYS:
        raise ValueError(f"hold_days는 {MIN_HOLD_DAYS} 이상이어야 합니다: {params.hold_days}")

    # 2. 초기 MA 계산
    ma_col = f"ma_{params.ma_window}"
    signal_df = signal_df.copy()
    trade_df = trade_df.copy()

    if ma_col not in signal_df.columns:
        signal_df = add_single_moving_average(signal_df, params.ma_window, ma_type=DEFAULT_BUFFER_MA_TYPE)

    # 3. MA 유효 구간 필터링 (초기 MA 기준)
    valid_mask = signal_df[ma_col].notna()
    filtered_signal = signal_df[valid_mask].reset_index(drop=True)
    filtered_trade = trade_df[valid_mask].reset_index(drop=True)

    # 4. BufferZoneStrategy 생성 및 실행
    strategy = BufferZoneStrategy(
        ma_col=ma_col,
        buy_buffer_pct=params.buy_buffer_zone_pct,
        sell_buffer_pct=params.sell_buffer_zone_pct,
        hold_days=params.hold_days,
    )

    return run_backtest(
        strategy,
        filtered_signal,
        filtered_trade,
        params.initial_capital,
        log_trades=log_trades,
        strategy_name=strategy_name,
        params_schedule=params_schedule,
    )
