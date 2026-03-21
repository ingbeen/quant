"""단일 백테스트 엔진

단일 자산 버퍼존 전략 백테스트 및 그리드 서치를 제공한다.
SignalStrategy Protocol을 통해 전략을 의존성 주입 방식으로 사용한다.

주요 함수:
- run_backtest: 전략 객체를 받아 단일 백테스트를 실행
- run_grid_search: 파라미터 그리드 탐색 (병렬 처리)
"""

import os
from datetime import date
from typing import TypedDict

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average, calculate_summary
from qbt.backtest.constants import (
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
from qbt.backtest.strategies.buffer_zone import BufferStrategyParams
from qbt.backtest.strategies.strategy_common import (
    HoldState,
    PendingOrderConflictError,
    SignalStrategy,
    compute_bands,
)
from qbt.backtest.types import SummaryDict
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


class BufferStrategyResultDict(SummaryDict):
    """run_backtest() 반환 타입.

    SummaryDict를 상속하고 전략 파라미터를 추가한다.
    """

    strategy: str
    ma_window: int
    buy_buffer_zone_pct: float
    sell_buffer_zone_pct: float
    hold_days: int


# ============================================================================
# 내부 헬퍼
# ============================================================================


def _validate_backtest_inputs(
    params: BufferStrategyParams,
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    ma_col: str,
) -> None:
    """버퍼존 전략의 입력 파라미터와 데이터를 검증한다.

    Args:
        params: 전략 파라미터
        signal_df: 시그널용 DataFrame
        trade_df: 매매용 DataFrame
        ma_col: 이동평균 컬럼명

    Raises:
        ValueError: 검증 실패 시
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

    # 2. signal_df 필수 컬럼 확인
    signal_required = [ma_col, COL_CLOSE, COL_DATE]
    signal_missing = set(signal_required) - set(signal_df.columns)
    if signal_missing:
        raise ValueError(f"signal_df 필수 컬럼 누락: {signal_missing}")

    # 3. trade_df 필수 컬럼 확인
    trade_required = [COL_OPEN, COL_CLOSE, COL_DATE]
    trade_missing = set(trade_required) - set(trade_df.columns)
    if trade_missing:
        raise ValueError(f"trade_df 필수 컬럼 누락: {trade_missing}")

    # 4. 날짜 정렬 일치 검증
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

    Args:
        params: 전략 파라미터

    Returns:
        성과 지표 딕셔너리

    Raises:
        예외 발생 시 즉시 전파
    """
    from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy

    # WORKER_CACHE에서 DataFrame 조회
    signal_df = WORKER_CACHE["signal_df"]
    trade_df = WORKER_CACHE["trade_df"]
    _, _, summary = run_backtest(BufferZoneStrategy(), signal_df, trade_df, params, log_trades=False)

    # Calmar 계산 (CAGR / |MDD|, MDD=0 안전 처리)
    cagr = summary["cagr"]
    abs_mdd = abs(summary["mdd"])
    if abs_mdd < EPSILON:
        calmar = 1e10 + cagr if cagr > 0 else 0.0
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
    params: BufferStrategyParams,
    log_trades: bool = True,
    strategy_name: str = "buffer_zone",
    params_schedule: dict[date, BufferStrategyParams] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, BufferStrategyResultDict]:
    """전략 객체를 받아 단일 자산 백테스트를 실행한다.

    롱 온리, 최대 1 포지션 전략을 사용한다.
    signal_df로 시그널을 생성하고, trade_df로 실제 매수/매도를 수행한다.
    strategy.check_buy(), strategy.check_sell()로 신호를 감지한다.

    핵심 실행 규칙:
    - 시그널: signal_df의 close vs signal_df의 MA 밴드
    - 체결: trade_df의 open (다음 날 시가)
    - equity = cash + position * trade_df.close (모든 시점)
    - final_capital = 마지막 equity (평가액 포함)
    - pending_order: 단일 슬롯 (충돌 시 PendingOrderConflictError)

    Args:
        strategy: SignalStrategy Protocol을 구현한 전략 객체
        signal_df: 시그널용 DataFrame (MA 계산, 밴드 비교, 돌파 감지)
        trade_df: 매매용 DataFrame (체결가: Open, 에쿼티: Close)
        params: 전략 파라미터 (초기 구간 파라미터)
        log_trades: 거래 로그 출력 여부 (기본값: True)
        strategy_name: 전략 식별 이름 (기본값: "buffer_zone")
        params_schedule: 구간별 파라미터 전환 스케줄 (기본값: None)
            {date: BufferStrategyParams} 형태. 해당 날짜부터 새 파라미터 적용.
            None이면 기존 동작과 완전히 동일.

    Returns:
        tuple: (trades_df, equity_df, summary)
            - trades_df: 거래 내역 DataFrame
            - equity_df: 자본 곡선 DataFrame
            - summary: 요약 지표 딕셔너리

    Raises:
        ValueError: 파라미터 검증 실패 또는 필수 컬럼 누락 시
        PendingOrderConflictError: pending 존재 중 신규 신호 발생 시 (Critical Invariant 위반)
    """
    if log_trades:
        logger.debug(f"백테스트 실행 시작: params={params}")

    # 1. 파라미터 및 데이터 검증
    ma_col = f"ma_{params.ma_window}"
    _validate_backtest_inputs(params, signal_df, trade_df, ma_col)

    # 2. 유효 데이터만 사용 (signal_df의 ma_window 이후부터)
    signal_df = signal_df.copy()
    trade_df = trade_df.copy()

    # 2-1. params_schedule의 모든 고유 MA 윈도우를 signal_df에 사전 계산
    sorted_switch_dates: list[date] = []
    next_switch_idx = 0
    if params_schedule is not None:
        # 모든 고유 MA 윈도우 수집 (현재 params + schedule의 모든 params)
        all_ma_windows = {params.ma_window}
        for sched_params in params_schedule.values():
            all_ma_windows.add(sched_params.ma_window)

        # signal_df에 없는 MA 컬럼 사전 계산
        for window in all_ma_windows:
            col = f"ma_{window}"
            if col not in signal_df.columns:
                signal_df = add_single_moving_average(signal_df, window, ma_type="ema")

        # schedule 날짜 정렬
        sorted_switch_dates = sorted(params_schedule.keys())

    # signal_df에서 MA가 유효한 행의 인덱스를 기준으로 양쪽 모두 필터
    valid_mask = signal_df[ma_col].notna()
    signal_df = signal_df[valid_mask].reset_index(drop=True)
    trade_df = trade_df[valid_mask].reset_index(drop=True)

    if len(signal_df) < MIN_VALID_ROWS:
        raise ValueError(f"유효 데이터 부족: {len(signal_df)}행 (최소 {MIN_VALID_ROWS}행 필요)")

    # 3. 초기화
    capital = params.initial_capital
    position = 0
    entry_price = 0.0
    entry_date: date | None = None

    trades: list[TradeRecord] = []
    equity_records: list[EquityRecord] = []
    pending_order: PendingOrder | None = None
    hold_state: HoldState | None = None

    entry_hold_days = 0

    # 3-1. 첫 날 에쿼티 기록 및 prev band 초기화
    first_signal_row = signal_df.iloc[0]
    first_trade_row = trade_df.iloc[0]
    first_ma_value = float(first_signal_row[ma_col])
    first_upper_band, first_lower_band = compute_bands(
        first_ma_value,
        params.buy_buffer_zone_pct,
        params.sell_buffer_zone_pct,
    )

    # 에쿼티는 trade_df의 종가로 계산
    first_equity_record = record_equity(
        current_date=first_signal_row[COL_DATE],
        capital=params.initial_capital,
        position=0,
        close_price=float(first_trade_row[COL_CLOSE]),
        buy_buffer_pct=params.buy_buffer_zone_pct,
        sell_buffer_pct=params.sell_buffer_zone_pct,
        upper_band=first_upper_band,
        lower_band=first_lower_band,
    )
    equity_records.append(first_equity_record)

    prev_upper_band: float = first_upper_band
    prev_lower_band: float = first_lower_band

    # 4. 백테스트 루프
    # 시그널: signal_df의 close, ma → 밴드/돌파 감지
    # 체결: trade_df의 open → 매수/매도 체결가
    # 에쿼티: trade_df의 close → 포지션 평가
    for i in range(1, len(signal_df)):
        signal_row = signal_df.iloc[i]
        trade_row = trade_df.iloc[i]
        current_date = signal_row[COL_DATE]

        # 4-0. params_schedule 전환 체크
        if params_schedule is not None and next_switch_idx < len(sorted_switch_dates):
            if current_date >= sorted_switch_dates[next_switch_idx]:
                params = params_schedule[sorted_switch_dates[next_switch_idx]]
                ma_col = f"ma_{params.ma_window}"
                next_switch_idx += 1
                if log_trades:
                    logger.debug(f"파라미터 전환: {current_date}, 새 params={params}")

        # 4-1. 파라미터 적용
        current_buy_buffer_pct = params.buy_buffer_zone_pct
        current_hold_days = params.hold_days
        current_sell_buffer_pct = params.sell_buffer_zone_pct

        # 4-2. 예약된 주문 실행 (trade_df의 오늘 시가로 체결)
        if pending_order is not None:
            if pending_order.order_type == "buy" and position == 0:
                position, capital, entry_price, entry_date, success = execute_buy_order(
                    pending_order, float(trade_row[COL_OPEN]), current_date, capital, position
                )
                if success:
                    entry_hold_days = pending_order.hold_days_used
                    if log_trades:
                        logger.debug(
                            f"매수 체결: {entry_date}, 가격={entry_price:.2f}, "
                            f"수량={position}, 매수버퍼={pending_order.buy_buffer_zone_pct:.2%}"
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
                )
                trade_record["hold_days_used"] = entry_hold_days
                trades.append(trade_record)
                if log_trades:
                    logger.debug(f"매도 체결: {current_date}, 손익률={trade_record['pnl_pct']*100:.2f}%")

            pending_order = None

        # 4-3. 버퍼존 밴드 계산 (signal_df의 MA 기준)
        ma_value = float(signal_row[ma_col])
        upper_band, lower_band = compute_bands(ma_value, current_buy_buffer_pct, current_sell_buffer_pct)

        # 4-4. 에쿼티 기록 (trade_df의 종가로 평가)
        equity_record = record_equity(
            current_date=current_date,
            capital=capital,
            position=position,
            close_price=float(trade_row[COL_CLOSE]),
            buy_buffer_pct=current_buy_buffer_pct,
            sell_buffer_pct=current_sell_buffer_pct,
            upper_band=upper_band,
            lower_band=lower_band,
        )
        equity_records.append(equity_record)

        # 4-5. 신호 감지 및 주문 예약 (signal_df 기준)
        prev_signal_row = signal_df.iloc[i - 1]

        if position == 0:
            # 매수 로직 — strategy.check_buy()에 위임
            old_hold_state = hold_state
            buy, new_hold_state = strategy.check_buy(
                prev_close=float(prev_signal_row[COL_CLOSE]),
                cur_close=float(signal_row[COL_CLOSE]),
                prev_upper=prev_upper_band,
                cur_upper=upper_band,
                hold_state=hold_state,
                hold_days_required=current_hold_days,
            )

            if buy:
                # 매수 신호: PendingOrder 생성
                # hold_state가 있었으면 그 시점의 buffer_pct, hold_days 사용
                if old_hold_state is not None:
                    pend_buffer_pct = old_hold_state["buffer_pct"]
                    hold_days_used = old_hold_state["hold_days_required"]
                else:
                    pend_buffer_pct = current_buy_buffer_pct
                    hold_days_used = 0

                _check_pending_conflict(pending_order, "buy", current_date)
                pending_order = PendingOrder(
                    order_type="buy",
                    signal_date=current_date,
                    buy_buffer_zone_pct=pend_buffer_pct,
                    hold_days_used=hold_days_used,
                )
                hold_state = None

            elif new_hold_state is not None:
                if old_hold_state is None:
                    # 신규 HoldState 생성 (첫 돌파 감지) — 엔진이 실제 값 주입
                    new_hold_state["start_date"] = current_date
                    new_hold_state["buffer_pct"] = current_buy_buffer_pct
                # else: 대기 중 (days_passed 증가) — buffer_pct, start_date는 이미 올바름
                hold_state = new_hold_state

            else:
                # 신호 없음 또는 hold 해제
                hold_state = None

        elif position > 0:
            # 매도 로직 — strategy.check_sell()에 위임
            sell = strategy.check_sell(
                prev_close=float(prev_signal_row[COL_CLOSE]),
                cur_close=float(signal_row[COL_CLOSE]),
                prev_lower=prev_lower_band,
                cur_lower=lower_band,
            )

            if sell:
                _check_pending_conflict(pending_order, "sell", current_date)
                pending_order = PendingOrder(
                    order_type="sell",
                    signal_date=current_date,
                    buy_buffer_zone_pct=current_buy_buffer_pct,
                    hold_days_used=0,
                )

        # 4-6. 다음 루프를 위해 전일 밴드 저장
        prev_upper_band = upper_band
        prev_lower_band = lower_band

    # 5. 백테스트 종료 (강제청산 없음)
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_records)

    # 6. 요약 지표 계산
    base_summary = calculate_summary(trades_df, equity_df, params.initial_capital)
    summary: BufferStrategyResultDict = {
        **base_summary,
        "strategy": strategy_name,
        "ma_window": params.ma_window,
        "buy_buffer_zone_pct": params.buy_buffer_zone_pct,
        "sell_buffer_zone_pct": params.sell_buffer_zone_pct,
        "hold_days": params.hold_days,
    }

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
    initial_capital: float = 10_000_000.0,
) -> pd.DataFrame:
    """버퍼존 전략 파라미터 그리드 탐색을 수행한다.

    모든 파라미터 조합에 대해 EMA 기반 버퍼존 전략을 실행하고
    성과 지표를 기록한다.

    Args:
        signal_df: 시그널용 DataFrame (MA 계산, 밴드 비교, 돌파 감지)
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
        signal_df = add_single_moving_average(signal_df, window, ma_type="ema")

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
    params_schedule: dict[date, BufferStrategyParams] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, "BufferStrategyResultDict"]:
    """버퍼존 전략으로 백테스트를 실행한다.

    `run_backtest(BufferZoneStrategy(), ...)` 편의 래퍼.

    Args:
        signal_df: 시그널용 DataFrame (MA 계산, 밴드 비교, 돌파 감지)
        trade_df: 매매용 DataFrame (체결가: Open, 에쿼티: Close)
        params: 전략 파라미터 (초기 구간 파라미터)
        log_trades: 거래 로그 출력 여부 (기본값: True)
        strategy_name: 전략 식별 이름 (기본값: "buffer_zone")
        params_schedule: 구간별 파라미터 전환 스케줄 (기본값: None)

    Returns:
        tuple: (trades_df, equity_df, summary)

    Raises:
        ValueError: 파라미터 검증 실패 또는 필수 컬럼 누락 시
        PendingOrderConflictError: pending 존재 중 신규 신호 발생 시 (Critical Invariant 위반)
    """
    from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy

    return run_backtest(
        BufferZoneStrategy(),
        signal_df,
        trade_df,
        params,
        log_trades=log_trades,
        strategy_name=strategy_name,
        params_schedule=params_schedule,
    )
