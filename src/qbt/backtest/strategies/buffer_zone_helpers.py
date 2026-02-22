"""버퍼존 전략 공통 헬퍼 모듈

버퍼존 계열 전략(buffer_zone_tqqq, buffer_zone_qqq)이 공유하는
핵심 로직, 타입, 예외, 상수를 제공한다.

포함 내용:
- TypedDicts: BufferStrategyResultDict, EquityRecord, TradeRecord, HoldState, GridSearchResult
- DataClasses: BaseStrategyParams, BufferStrategyParams, PendingOrder
- 예외: PendingOrderConflictError
- 동적 조정 상수
- 헬퍼 함수 9개 (입력 검증, 밴드 계산, 신호 감지, 주문 실행 등)
- 핵심 함수: run_buffer_strategy, run_grid_search
"""

import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, TypedDict

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average, calculate_summary, load_best_grid_params
from qbt.backtest.constants import (
    COL_BUY_BUFFER_ZONE_PCT,
    COL_CAGR,
    COL_FINAL_CAPITAL,
    COL_HOLD_DAYS,
    COL_MA_WINDOW,
    COL_MDD,
    COL_RECENT_MONTHS,
    COL_SELL_BUFFER_ZONE_PCT,
    COL_TOTAL_RETURN_PCT,
    COL_TOTAL_TRADES,
    COL_WIN_RATE,
    DEFAULT_BUY_BUFFER_ZONE_PCT,
    DEFAULT_HOLD_DAYS,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MA_WINDOW,
    DEFAULT_RECENT_MONTHS,
    DEFAULT_SELL_BUFFER_ZONE_PCT,
    MIN_BUY_BUFFER_ZONE_PCT,
    MIN_HOLD_DAYS,
    MIN_SELL_BUFFER_ZONE_PCT,
    MIN_VALID_ROWS,
    SLIPPAGE_RATE,
)
from qbt.backtest.types import (
    SummaryDict,
)
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_OPEN,
)
from qbt.utils import get_logger
from qbt.utils.parallel_executor import WORKER_CACHE, execute_parallel_with_kwargs, init_worker_cache

logger = get_logger(__name__)


# ============================================================================
# 전략 공통 TypedDict
# ============================================================================


class BufferStrategyResultDict(SummaryDict):
    """run_buffer_strategy() 반환 타입.

    SummaryDict를 상속하고 전략 파라미터를 추가한다.
    """

    strategy: str
    ma_window: int
    buy_buffer_zone_pct: float
    sell_buffer_zone_pct: float
    hold_days: int


class EquityRecord(TypedDict):
    """_record_equity() 반환 타입 / equity_records 리스트 아이템.

    키 "Date"는 COL_DATE 상수의 값이다.
    buy_buffer_pct: 해당 시점의 매수 버퍼 (동적 조정 반영)
    sell_buffer_pct: 해당 시점의 매도 버퍼 (항상 고정)
    """

    Date: date
    equity: float
    position: int
    buy_buffer_pct: float
    sell_buffer_pct: float
    upper_band: float | None
    lower_band: float | None


class TradeRecord(TypedDict):
    """_execute_sell_order() 거래 기록 딕셔너리."""

    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    buy_buffer_pct: float
    hold_days_used: int
    recent_sell_count: int


class HoldState(TypedDict):
    """hold_days 상태머신의 상태 딕셔너리."""

    start_date: date
    days_passed: int
    buffer_pct: float  # 매수 버퍼 (buy buffer)
    hold_days_required: int


class GridSearchResult(TypedDict):
    """_run_buffer_strategy_for_grid() 반환 타입.

    키 이름은 backtest/constants.py의 COL_* 상수 값과 동일하다.
    """

    ma_window: int
    buy_buffer_zone_pct: float
    sell_buffer_zone_pct: float
    hold_days: int
    recent_months: int
    total_return_pct: float
    cagr: float
    mdd: float
    total_trades: int
    win_rate: float
    final_capital: float


# ============================================================================
# 동적 조정 상수
# ============================================================================

DEFAULT_BUFFER_INCREMENT_PER_BUY = 0.01  # 최근 청산 1회당 버퍼존 증가량 (0.01 = 1%)
DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY = 1  # 최근 청산 1회당 유지조건 증가량 (일)
DEFAULT_DAYS_PER_MONTH = 30  # 최근 기간 계산용 월당 일수 (근사값)


# ============================================================================
# 예외 클래스
# ============================================================================


class PendingOrderConflictError(Exception):
    """Pending Order 충돌 예외

    이 예외는 백테스트의 Critical Invariant 위반을 나타냅니다.

    발생 조건:
    - pending_order가 이미 존재하는 상태에서 새로운 신호가 발생하려 할 때

    왜 중요한가:
    - pending은 "신호일 종가 → 체결일 시가" 사이의 단일 예약 상태를 나타냄
    - 이 기간에 새로운 신호가 발생하면 논리적 모순 (두 신호가 동시에 존재할 수 없음)
    - 이는 매우 크리티컬한 버그로, 발견 즉시 백테스트를 중단해야 함

    디버깅 방법:
    - 예외 메시지에서 기존 pending 정보 및 새 신호 발생 시점 확인
    - hold_days 로직, 신호 감지 로직에서 타이밍 문제 검토
    """

    pass


# ============================================================================
# DataClasses
# ============================================================================


@dataclass
class BaseStrategyParams:
    """전략 파라미터의 기본 클래스.

    학습 포인트:
    1. @dataclass 데코레이터: 클래스를 데이터 컨테이너로 만듦
    2. 타입 힌트와 함께 변수 선언만 하면 __init__ 메서드 자동 생성
    3. 클래스 상속의 기본 - 공통 속성을 부모 클래스에 정의
    """

    initial_capital: float  # 초기 자본금


@dataclass
class BufferStrategyParams(BaseStrategyParams):
    """버퍼존 전략 파라미터를 담는 데이터 클래스.

    학습 포인트:
    - 클래스 상속: (BaseStrategyParams) - 부모 클래스의 속성 상속
    - BaseStrategyParams의 initial_capital도 사용 가능
    """

    ma_window: int  # 이동평균 기간 (예: 200일)
    buy_buffer_zone_pct: float  # 매수 버퍼 비율 (upper_band 기준) — 동적 조정됨
    sell_buffer_zone_pct: float  # 매도 버퍼 비율 (lower_band 기준) — 항상 고정
    hold_days: int  # 최소 보유 일수 (예: 5일)
    recent_months: int  # 최근 청산 기간 (예: 6개월)


@dataclass
class PendingOrder:
    """예약된 주문 정보

    신호 발생 시점에 생성되며, 다음 거래일 시가에 실제 체결됩니다.
    이를 통해 신호 발생일과 체결일을 명확히 분리하고, 미래 데이터 참조를 방지합니다.

    타입 안정성:
    - order_type은 Literal["buy", "sell"]로 제한하여 타입 체크 시점에 오류 방지

    중요: 미래 데이터 참조 방지
    - execute_date, price_raw를 저장하지 않음 (look-ahead bias 방지)
    - 다음 날 루프에서 해당 날짜의 시가를 조회하여 체결
    - 마지막 날 신호는 자연스럽게 미체결됨 (다음 날이 없으므로)
    """

    order_type: Literal["buy", "sell"]  # 주문 유형 (타입 안전)
    signal_date: date  # 신호 발생 날짜 (디버깅/로깅용)
    buy_buffer_zone_pct: float  # 신호 시점의 매수 버퍼 비율 (0~1)
    hold_days_used: int  # 신호 시점의 유지일수
    recent_sell_count: int  # 신호 시점의 최근 청산 횟수


# ============================================================================
# 파라미터 결정 공통 함수
# ============================================================================


def resolve_buffer_params(
    grid_results_path: Path,
    override_ma_window: int | None,
    override_buy_buffer_zone_pct: float | None,
    override_sell_buffer_zone_pct: float | None,
    override_hold_days: int | None,
    override_recent_months: int | None,
) -> tuple[BufferStrategyParams, dict[str, str]]:
    """
    버퍼존 전략의 파라미터를 결정한다.

    폴백 체인: OVERRIDE → grid_results.csv 최적값 → DEFAULT.
    버퍼존 계열 전략(QQQ, TQQQ)이 공유하는 공통 로직이다.

    Args:
        grid_results_path: 그리드 서치 결과 CSV 경로
        override_ma_window: MA 기간 오버라이드 (None이면 폴백)
        override_buy_buffer_zone_pct: 매수 버퍼존 비율 오버라이드 (None이면 폴백)
        override_sell_buffer_zone_pct: 매도 버퍼존 비율 오버라이드 (None이면 폴백)
        override_hold_days: 유지일수 오버라이드 (None이면 폴백)
        override_recent_months: 조정기간 오버라이드 (None이면 폴백)

    Returns:
        tuple: (params, sources)
            - params: 전략 파라미터
            - sources: 각 파라미터의 출처 딕셔너리
    """
    grid_params = load_best_grid_params(grid_results_path)

    if grid_params is not None:
        logger.debug(f"grid_results.csv 최적값 로드 완료: {grid_results_path}")
    else:
        logger.debug("grid_results.csv 없음, DEFAULT 상수 사용")

    # 1. ma_window
    if override_ma_window is not None:
        ma_window = override_ma_window
        ma_window_source = "OVERRIDE"
    elif grid_params is not None:
        ma_window = grid_params["ma_window"]
        ma_window_source = "grid_best"
    else:
        ma_window = DEFAULT_MA_WINDOW
        ma_window_source = "DEFAULT"

    # 2. buy_buffer_zone_pct
    if override_buy_buffer_zone_pct is not None:
        buy_buffer_zone_pct = override_buy_buffer_zone_pct
        buy_bz_source = "OVERRIDE"
    elif grid_params is not None:
        buy_buffer_zone_pct = grid_params["buy_buffer_zone_pct"]
        buy_bz_source = "grid_best"
    else:
        buy_buffer_zone_pct = DEFAULT_BUY_BUFFER_ZONE_PCT
        buy_bz_source = "DEFAULT"

    # 3. sell_buffer_zone_pct
    if override_sell_buffer_zone_pct is not None:
        sell_buffer_zone_pct = override_sell_buffer_zone_pct
        sell_bz_source = "OVERRIDE"
    elif grid_params is not None:
        sell_buffer_zone_pct = grid_params["sell_buffer_zone_pct"]
        sell_bz_source = "grid_best"
    else:
        sell_buffer_zone_pct = DEFAULT_SELL_BUFFER_ZONE_PCT
        sell_bz_source = "DEFAULT"

    # 4. hold_days
    if override_hold_days is not None:
        hold_days = override_hold_days
        hd_source = "OVERRIDE"
    elif grid_params is not None:
        hold_days = grid_params["hold_days"]
        hd_source = "grid_best"
    else:
        hold_days = DEFAULT_HOLD_DAYS
        hd_source = "DEFAULT"

    # 5. recent_months
    if override_recent_months is not None:
        recent_months = override_recent_months
        rm_source = "OVERRIDE"
    elif grid_params is not None:
        recent_months = grid_params["recent_months"]
        rm_source = "grid_best"
    else:
        recent_months = DEFAULT_RECENT_MONTHS
        rm_source = "DEFAULT"

    params = BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=ma_window,
        buy_buffer_zone_pct=buy_buffer_zone_pct,
        sell_buffer_zone_pct=sell_buffer_zone_pct,
        hold_days=hold_days,
        recent_months=recent_months,
    )

    sources = {
        "ma_window": ma_window_source,
        "buy_buffer_zone_pct": buy_bz_source,
        "sell_buffer_zone_pct": sell_bz_source,
        "hold_days": hd_source,
        "recent_months": rm_source,
    }

    logger.debug(
        f"파라미터 결정: ma_window={ma_window} ({ma_window_source}), "
        f"buy_buffer={buy_buffer_zone_pct} ({buy_bz_source}), "
        f"sell_buffer={sell_buffer_zone_pct} ({sell_bz_source}), "
        f"hold_days={hold_days} ({hd_source}), "
        f"recent_months={recent_months} ({rm_source})"
    )

    return params, sources


# ============================================================================
# Helper Functions for run_buffer_strategy
# ============================================================================


def _validate_buffer_strategy_inputs(
    params: BufferStrategyParams, signal_df: pd.DataFrame, trade_df: pd.DataFrame, ma_col: str
) -> None:
    """
    버퍼존 전략의 입력 파라미터와 데이터를 검증한다.

    Args:
        params: 전략 파라미터
        signal_df: 시그널용 DataFrame (MA, 밴드, 돌파 감지)
        trade_df: 매매용 DataFrame (체결, 에쿼티)
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

    if params.recent_months < 0:
        raise ValueError(f"recent_months는 0 이상이어야 합니다: {params.recent_months}")

    # 2. signal_df 필수 컬럼 확인 (시그널: MA, Close, Date)
    signal_required = [ma_col, COL_CLOSE, COL_DATE]
    signal_missing = set(signal_required) - set(signal_df.columns)
    if signal_missing:
        raise ValueError(f"signal_df 필수 컬럼 누락: {signal_missing}")

    # 3. trade_df 필수 컬럼 확인 (매매: Open, Close, Date)
    trade_required = [COL_OPEN, COL_CLOSE, COL_DATE]
    trade_missing = set(trade_required) - set(trade_df.columns)
    if trade_missing:
        raise ValueError(f"trade_df 필수 컬럼 누락: {trade_missing}")

    # 4. 날짜 정렬 일치 검증
    signal_dates = list(signal_df[COL_DATE])
    trade_dates = list(trade_df[COL_DATE])
    if signal_dates != trade_dates:
        raise ValueError("signal_df와 trade_df의 날짜가 일치하지 않습니다")


def _compute_bands(
    ma_value: float,
    buy_buffer_pct: float,
    sell_buffer_pct: float,
) -> tuple[float, float]:
    """
    이동평균 기준 상하단 밴드를 계산한다.

    upper_band는 매수 버퍼(동적 조정됨), lower_band는 매도 버퍼(항상 고정).

    Args:
        ma_value: 이동평균 값
        buy_buffer_pct: 매수 버퍼존 비율 (upper_band용, 0~1)
        sell_buffer_pct: 매도 버퍼존 비율 (lower_band용, 0~1)

    Returns:
        tuple: (upper_band, lower_band)
            - upper_band: 상단 밴드 = ma * (1 + buy_buffer_pct)
            - lower_band: 하단 밴드 = ma * (1 - sell_buffer_pct)
    """
    upper_band = ma_value * (1 + buy_buffer_pct)
    lower_band = ma_value * (1 - sell_buffer_pct)
    return upper_band, lower_band


def _check_pending_conflict(
    pending_order: PendingOrder | None, signal_type: Literal["buy", "sell"], current_date: date
) -> None:
    """
    Pending order 충돌을 검사한다 (Critical Invariant).

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


def _record_equity(
    current_date: date,
    capital: float,
    position: int,
    close_price: float,
    buy_buffer_pct: float,
    sell_buffer_pct: float,
    upper_band: float | None,
    lower_band: float | None,
) -> EquityRecord:
    """
    현재 시점의 equity를 기록한다.

    Args:
        current_date: 현재 날짜
        capital: 현재 보유 현금
        position: 현재 포지션 수량
        close_price: 현재 종가
        buy_buffer_pct: 현재 매수 버퍼존 비율 (동적 조정 반영)
        sell_buffer_pct: 현재 매도 버퍼존 비율 (항상 고정)
        upper_band: 상단 밴드 (첫 날은 None 가능)
        lower_band: 하단 밴드 (첫 날은 None 가능)

    Returns:
        equity 기록 딕셔너리
    """
    if position > 0:
        equity = capital + position * close_price
    else:
        equity = capital

    return {
        COL_DATE: current_date,
        "equity": equity,
        "position": position,
        "buy_buffer_pct": buy_buffer_pct,
        "sell_buffer_pct": sell_buffer_pct,
        "upper_band": upper_band,
        "lower_band": lower_band,
    }


def _execute_buy_order(
    order: PendingOrder,
    open_price: float,
    execute_date: date,
    capital: float,
    position: int,
) -> tuple[int, float, float, date, bool]:
    """
    매수 주문을 실행한다.

    Args:
        order: 실행할 매수 주문
        open_price: 체결 날짜의 시가 (슬리피지 적용 전)
        execute_date: 체결 날짜
        capital: 현재 보유 현금
        position: 현재 포지션 (0이어야 함)

    Returns:
        tuple: (new_position, new_capital, entry_price, entry_date, executed)
            - new_position: 새 포지션 수량
            - new_capital: 새 자본
            - entry_price: 진입 가격 (슬리피지 적용)
            - entry_date: 진입 날짜
            - executed: 실행 여부 (자본 부족 시 False)
    """
    # 슬리피지 적용 (매수 시 +0.3%)
    buy_price = open_price * (1 + SLIPPAGE_RATE)
    shares = int(capital / buy_price)

    if shares > 0:
        buy_amount = shares * buy_price
        new_capital = capital - buy_amount
        return shares, new_capital, buy_price, execute_date, True
    else:
        # 자본 부족으로 매수 불가
        logger.debug(f"매수 불가 (자본 부족): 날짜={execute_date}, 필요가격={buy_price:.2f}, " f"현재자본={capital:.2f}, 가능수량=0")
        return position, capital, 0.0, execute_date, False


def _execute_sell_order(
    order: PendingOrder,
    open_price: float,
    execute_date: date,
    capital: float,
    position: int,
    entry_price: float,
    entry_date: date,
) -> tuple[int, float, TradeRecord]:
    """
    매도 주문을 실행한다.

    Args:
        order: 실행할 매도 주문
        open_price: 체결 날짜의 시가 (슬리피지 적용 전)
        execute_date: 체결 날짜
        capital: 현재 보유 현금
        position: 현재 포지션 수량
        entry_price: 진입 가격
        entry_date: 진입 날짜

    Returns:
        tuple: (new_position, new_capital, trade_record)
            - new_position: 새 포지션 (0)
            - new_capital: 새 자본 (매도 금액 추가)
            - trade_record: 거래 기록 딕셔너리
    """
    # 슬리피지 적용 (매도 시 -0.3%)
    sell_price = open_price * (1 - SLIPPAGE_RATE)
    sell_amount = position * sell_price
    new_capital = capital + sell_amount

    trade_record: TradeRecord = {
        "entry_date": entry_date,
        "exit_date": execute_date,
        "entry_price": entry_price,
        "exit_price": sell_price,
        "shares": position,
        "pnl": (sell_price - entry_price) * position,
        "pnl_pct": (sell_price - entry_price) / entry_price,
        "buy_buffer_pct": order.buy_buffer_zone_pct,
        "hold_days_used": 0,
        "recent_sell_count": 0,
    }

    return 0, new_capital, trade_record


def _detect_buy_signal(
    prev_close: float,
    close: float,
    prev_upper_band: float,
    upper_band: float,
) -> bool:
    """
    상향돌파 신호를 감지한다 (상태머신 방식).

    Args:
        prev_close: 전일 종가
        close: 당일 종가
        prev_upper_band: 전일 상단 밴드
        upper_band: 당일 상단 밴드

    Returns:
        bool: 상향돌파 감지 여부
    """
    # 상향돌파 체크: 전일 종가 <= 상단밴드 AND 당일 종가 > 상단밴드
    return prev_close <= prev_upper_band and close > upper_band


def _detect_sell_signal(
    prev_close: float,
    close: float,
    prev_lower_band: float,
    lower_band: float,
) -> bool:
    """
    하향돌파 신호를 감지한다 (상태머신 방식).

    Args:
        prev_close: 전일 종가
        close: 당일 종가
        prev_lower_band: 전일 하단 밴드
        lower_band: 당일 하단 밴드

    Returns:
        bool: 하향돌파 감지 여부
    """
    # 하향돌파 체크: 전일 종가 >= 하단밴드 AND 당일 종가 < 하단밴드
    return prev_close >= prev_lower_band and close < lower_band


def _calculate_recent_sell_count(
    exit_dates: list[date],
    current_date: date,
    recent_months: int,
) -> int:
    """
    최근 N개월 내 청산 횟수를 계산한다.

    가산 누적: 60일 내 청산이 2회 발생하면 count=2.
    당일 청산(d == current_date)은 포함하지 않는다.

    Args:
        exit_dates: 모든 청산 날짜 리스트 (datetime.date 객체)
        current_date: 현재 날짜 (datetime.date 객체)
        recent_months: 최근 기간 (개월), 0이면 항상 0 반환

    Returns:
        최근 N개월 내 청산 횟수
    """
    if recent_months == 0:
        return 0

    # 최근 N개월을 일수로 환산
    # 정확한 월 계산 대신 근사값 사용 (백테스트 성능 최적화)
    cutoff_date = current_date - timedelta(days=recent_months * DEFAULT_DAYS_PER_MONTH)
    count = sum(1 for d in exit_dates if d >= cutoff_date and d < current_date)
    return count


# ============================================================================
# 핵심 전략 실행 함수
# ============================================================================


def _run_buffer_strategy_for_grid(
    params: BufferStrategyParams,
) -> GridSearchResult:
    """
    그리드 서치를 위해 단일 파라미터 조합에 대해 버퍼존 전략을 실행한다.

    병렬 실행을 위한 헬퍼 함수. 예외 발생 시 즉시 전파한다.
    signal_df, trade_df는 WORKER_CACHE에서 조회한다.

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
    _, _, summary = run_buffer_strategy(signal_df, trade_df, params, log_trades=False)

    return {
        COL_MA_WINDOW: params.ma_window,
        COL_BUY_BUFFER_ZONE_PCT: params.buy_buffer_zone_pct,
        COL_SELL_BUFFER_ZONE_PCT: params.sell_buffer_zone_pct,
        COL_HOLD_DAYS: params.hold_days,
        COL_RECENT_MONTHS: params.recent_months,
        COL_TOTAL_RETURN_PCT: summary["total_return_pct"],
        COL_CAGR: summary["cagr"],
        COL_MDD: summary["mdd"],
        COL_TOTAL_TRADES: summary["total_trades"],
        COL_WIN_RATE: summary["win_rate"],
        COL_FINAL_CAPITAL: summary["final_capital"],
    }


def run_grid_search(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    ma_window_list: list[int],
    buy_buffer_zone_pct_list: list[float],
    sell_buffer_zone_pct_list: list[float],
    hold_days_list: list[int],
    recent_months_list: list[int],
    initial_capital: float = 10_000_000.0,
) -> pd.DataFrame:
    """
    버퍼존 전략 파라미터 그리드 탐색을 수행한다.

    모든 파라미터 조합에 대해 EMA 기반 버퍼존 전략을 실행하고
    성과 지표를 기록한다.

    Args:
        signal_df: 시그널용 DataFrame (MA 계산, 밴드 비교, 돌파 감지)
        trade_df: 매매용 DataFrame (체결가: Open, 에쿼티: Close)
        ma_window_list: 이동평균 기간 목록
        buy_buffer_zone_pct_list: 매수 버퍼존 비율 목록
        sell_buffer_zone_pct_list: 매도 버퍼존 비율 목록
        hold_days_list: 유지조건 일수 목록
        recent_months_list: 최근 청산 기간 목록
        initial_capital: 초기 자본금

    Returns:
        그리드 탐색 결과 DataFrame (각 조합별 성과 지표 포함)
    """
    logger.debug(
        f"그리드 탐색 시작: "
        f"ma_window={ma_window_list}, buy_buffer_zone_pct={buy_buffer_zone_pct_list}, "
        f"sell_buffer_zone_pct={sell_buffer_zone_pct_list}, "
        f"hold_days={hold_days_list}, recent_months={recent_months_list}"
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
                    for recent_months in recent_months_list:
                        param_combinations.append(
                            {
                                "params": BufferStrategyParams(
                                    ma_window=ma_window,
                                    buy_buffer_zone_pct=buy_buffer_zone_pct,
                                    sell_buffer_zone_pct=sell_buffer_zone_pct,
                                    hold_days=hold_days,
                                    recent_months=recent_months,
                                    initial_capital=initial_capital,
                                ),
                            }
                        )

    logger.debug(f"총 {len(param_combinations)}개 조합 병렬 실행 시작 (DataFrame 캐시 사용)")

    # 3. 병렬 실행 (signal_df, trade_df를 워커 캐시에 저장)
    raw_count = os.cpu_count()
    cpu_count = raw_count - 1 if raw_count is not None else None
    results = execute_parallel_with_kwargs(
        func=_run_buffer_strategy_for_grid,
        inputs=param_combinations,
        max_workers=cpu_count,
        initializer=init_worker_cache,
        initargs=({"signal_df": signal_df, "trade_df": trade_df},),
    )

    # 4. 딕셔너리 리스트를 DataFrame으로 변환
    results_df = pd.DataFrame(results)

    # 5. 정렬
    results_df = results_df.sort_values(by=COL_CAGR, ascending=False).reset_index(drop=True)

    logger.debug(f"그리드 탐색 완료: {len(results_df)}개 조합 테스트됨")

    return results_df


def run_buffer_strategy(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    params: BufferStrategyParams,
    log_trades: bool = True,
    strategy_name: str = "buffer_zone",
) -> tuple[pd.DataFrame, pd.DataFrame, BufferStrategyResultDict]:
    """
    버퍼존 전략으로 백테스트를 실행한다.

    롱 온리, 최대 1 포지션 전략을 사용한다.
    signal_df로 시그널을 생성하고, trade_df로 실제 매수/매도를 수행한다.

    핵심 실행 규칙:
    - 시그널: signal_df의 close vs signal_df의 MA 밴드
    - 체결: trade_df의 open (다음 날 시가)
    - equity = cash + position * trade_df.close (모든 시점)
    - final_capital = 마지막 equity (평가액 포함)
    - pending_order: 단일 슬롯 (충돌 시 PendingOrderConflictError)
    - lower_band: 항상 sell_buffer_zone_pct 기준 고정
    - upper_band: recent_sell_count 기반 동적 확장

    Args:
        signal_df: 시그널용 DataFrame (MA 계산, 밴드 비교, 돌파 감지)
        trade_df: 매매용 DataFrame (체결가: Open, 에쿼티: Close)
        params: 전략 파라미터
        log_trades: 거래 로그 출력 여부 (기본값: True)
        strategy_name: 전략 식별 이름 (기본값: "buffer_zone")

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
        logger.debug(f"버퍼존 전략 실행 시작: params={params}")

    # 1. 파라미터 및 데이터 검증
    ma_col = f"ma_{params.ma_window}"
    _validate_buffer_strategy_inputs(params, signal_df, trade_df, ma_col)

    # 2. 유효 데이터만 사용 (signal_df의 ma_window 이후부터)
    signal_df = signal_df.copy()
    trade_df = trade_df.copy()

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
    entry_date = None
    all_exit_dates: list[date] = []  # 청산 날짜 누적 (동적 조정 기준)

    trades: list[TradeRecord] = []
    equity_records: list[EquityRecord] = []
    pending_order: PendingOrder | None = None
    hold_state: HoldState | None = None

    entry_hold_days = 0
    entry_recent_sell_count = 0

    # 3-1. 첫 날 에쿼티 기록 및 prev band 초기화
    first_signal_row = signal_df.iloc[0]
    first_trade_row = trade_df.iloc[0]
    first_ma_value = first_signal_row[ma_col]
    first_upper_band, first_lower_band = _compute_bands(
        first_ma_value,
        params.buy_buffer_zone_pct,  # 초기 buy buffer
        params.sell_buffer_zone_pct,  # sell buffer (고정)
    )

    # 에쿼티는 trade_df의 종가로 계산
    first_equity_record = _record_equity(
        first_signal_row[COL_DATE],
        params.initial_capital,
        0,
        first_trade_row[COL_CLOSE],
        params.buy_buffer_zone_pct,
        params.sell_buffer_zone_pct,
        first_upper_band,
        first_lower_band,
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

        # 4-1. 동적 파라미터 계산
        if params.recent_months > 0:
            recent_sell_count = _calculate_recent_sell_count(all_exit_dates, current_date, params.recent_months)
            # 동적 확장은 upper_band(매수)에만 적용
            current_buy_buffer_pct = params.buy_buffer_zone_pct + (recent_sell_count * DEFAULT_BUFFER_INCREMENT_PER_BUY)

            if params.hold_days > 0:
                current_hold_days = params.hold_days + (recent_sell_count * DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY)
            else:
                current_hold_days = params.hold_days
        else:
            recent_sell_count = 0
            current_buy_buffer_pct = params.buy_buffer_zone_pct
            current_hold_days = params.hold_days

        # lower_band는 항상 고정 (sell_buffer_zone_pct)
        current_sell_buffer_pct = params.sell_buffer_zone_pct

        # 4-2. 예약된 주문 실행 (trade_df의 오늘 시가로 체결)
        if pending_order is not None:
            if pending_order.order_type == "buy" and position == 0:
                position, capital, entry_price, entry_date, success = _execute_buy_order(
                    pending_order, trade_row[COL_OPEN], current_date, capital, position
                )
                if success:
                    entry_hold_days = pending_order.hold_days_used
                    entry_recent_sell_count = pending_order.recent_sell_count
                    if log_trades:
                        logger.debug(
                            f"매수 체결: {entry_date}, 가격={entry_price:.2f}, "
                            f"수량={position}, 매수버퍼={pending_order.buy_buffer_zone_pct:.2%}"
                        )

            elif pending_order.order_type == "sell" and position > 0:
                assert entry_date is not None, "포지션이 있으면 entry_date는 None이 아니어야 함"
                position, capital, trade_record = _execute_sell_order(
                    pending_order, trade_row[COL_OPEN], current_date, capital, position, entry_price, entry_date
                )
                trade_record["hold_days_used"] = entry_hold_days
                trade_record["recent_sell_count"] = entry_recent_sell_count
                trades.append(trade_record)
                # 청산 완료 → all_exit_dates에 기록
                all_exit_dates.append(current_date)
                if log_trades:
                    logger.debug(f"매도 체결: {current_date}, 손익률={trade_record['pnl_pct']*100:.2f}%")

            pending_order = None

        # 4-3. 버퍼존 밴드 계산 (signal_df의 MA 기준)
        ma_value = signal_row[ma_col]
        upper_band, lower_band = _compute_bands(ma_value, current_buy_buffer_pct, current_sell_buffer_pct)

        # 4-4. 에쿼티 기록 (trade_df의 종가로 평가)
        equity_record = _record_equity(
            current_date,
            capital,
            position,
            trade_row[COL_CLOSE],
            current_buy_buffer_pct,
            current_sell_buffer_pct,
            upper_band,
            lower_band,
        )
        equity_records.append(equity_record)

        # 4-5. 신호 감지 및 주문 예약 (signal_df 기준)
        prev_signal_row = signal_df.iloc[i - 1]

        if position == 0:
            # 매수 로직 (상태머신) - signal_df의 close로 판단
            if hold_state is not None:
                if signal_row[COL_CLOSE] > upper_band:
                    hold_state["days_passed"] += 1

                    if hold_state["days_passed"] >= hold_state["hold_days_required"]:
                        _check_pending_conflict(pending_order, "buy", current_date)
                        pending_order = PendingOrder(
                            order_type="buy",
                            signal_date=current_date,
                            buy_buffer_zone_pct=hold_state["buffer_pct"],
                            hold_days_used=hold_state["hold_days_required"],
                            recent_sell_count=recent_sell_count,
                        )
                        hold_state = None
                else:
                    hold_state = None

            if hold_state is None:
                breakout_detected = _detect_buy_signal(
                    prev_close=prev_signal_row[COL_CLOSE],
                    close=signal_row[COL_CLOSE],
                    prev_upper_band=prev_upper_band,
                    upper_band=upper_band,
                )

                if breakout_detected:
                    if current_hold_days > 0:
                        hold_state = {
                            "start_date": current_date,
                            "days_passed": 0,
                            "buffer_pct": current_buy_buffer_pct,
                            "hold_days_required": current_hold_days,
                        }
                    else:
                        _check_pending_conflict(pending_order, "buy", current_date)
                        pending_order = PendingOrder(
                            order_type="buy",
                            signal_date=current_date,
                            buy_buffer_zone_pct=current_buy_buffer_pct,
                            hold_days_used=0,
                            recent_sell_count=recent_sell_count,
                        )

        elif position > 0:
            # 매도 로직 - signal_df의 close로 판단
            breakout_detected = _detect_sell_signal(
                prev_close=prev_signal_row[COL_CLOSE],
                close=signal_row[COL_CLOSE],
                prev_lower_band=prev_lower_band,
                lower_band=lower_band,
            )

            if breakout_detected:
                _check_pending_conflict(pending_order, "sell", current_date)
                pending_order = PendingOrder(
                    order_type="sell",
                    signal_date=current_date,
                    buy_buffer_zone_pct=current_buy_buffer_pct,
                    hold_days_used=0,
                    recent_sell_count=recent_sell_count,
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
        logger.debug(f"버퍼존 전략 완료: 총 거래={summary['total_trades']}, 총 수익률={summary['total_return_pct']:.2f}%")

    return trades_df, equity_df, summary
