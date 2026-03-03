"""Donchian Channel 전략 핵심 로직

Donchian Channel (터틀 트레이딩) 전략의 실행 엔진을 제공한다.
N일 최고가 / M일 최저가 기반으로 매매 신호를 생성하고 백테스트를 실행한다.

핵심 규칙:
- 매수: close > upper_channel (N일 신고가 돌파)
- 매도: close < lower_channel (M일 신저가 돌파)
- 체결: 신호 발생 익일 시가 (pending order 패턴)
- 비용: SLIPPAGE_RATE 적용
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal, TypedDict

import pandas as pd

from qbt.backtest.analysis import calculate_summary
from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.backtest.strategies.buffer_zone_helpers import PendingOrderConflictError
from qbt.backtest.types import SummaryDict
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN
from qbt.utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# TypedDict 정의
# ============================================================================


class DonchianEquityRecord(TypedDict):
    """Donchian 전략 equity 기록 딕셔너리."""

    Date: date
    equity: float
    position: int
    upper_channel: float | None
    lower_channel: float | None


class DonchianTradeRecord(TypedDict):
    """Donchian 전략 거래 기록 딕셔너리."""

    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float


class DonchianStrategyResultDict(SummaryDict, total=False):
    """Donchian 전략 결과 딕셔너리 (SummaryDict 확장)."""

    strategy: str
    entry_channel_days: int
    exit_channel_days: int


# ============================================================================
# 데이터 클래스
# ============================================================================


@dataclass(frozen=True)
class DonchianStrategyParams:
    """Donchian Channel 전략 파라미터."""

    initial_capital: float  # 초기 자본금
    entry_channel_days: int  # 매수 채널 기간 (예: 55일 최고가)
    exit_channel_days: int  # 매도 채널 기간 (예: 20일 최저가)


@dataclass
class _DonchianPendingOrder:
    """Donchian 전략 예약 주문 (내부용).

    신호 발생 시점에 생성되며, 다음 거래일 시가에 체결된다.
    """

    order_type: Literal["buy", "sell"]
    signal_date: date


# ============================================================================
# 채널 계산
# ============================================================================


def compute_donchian_channels(
    signal_df: pd.DataFrame,
    entry_days: int,
    exit_days: int,
) -> tuple[pd.Series, pd.Series]:
    """Donchian Channel 상단/하단을 계산한다.

    Args:
        signal_df: OHLCV DataFrame (High, Low 컬럼 필수)
        entry_days: 매수 채널 기간 (N일 최고가)
        exit_days: 매도 채널 기간 (M일 최저가)

    Returns:
        (upper_channel, lower_channel) 시리즈 튜플
        - upper_channel: 이전 N일간 최고가 (shift(1) 적용)
        - lower_channel: 이전 M일간 최저가 (shift(1) 적용)
    """
    # 1. rolling + shift(1): 당일 데이터 미포함 (lookahead 방지)
    upper_channel: pd.Series = signal_df[COL_HIGH].rolling(window=entry_days).max().shift(1)
    lower_channel: pd.Series = signal_df[COL_LOW].rolling(window=exit_days).min().shift(1)

    return upper_channel, lower_channel


# ============================================================================
# 내부 헬퍼 함수
# ============================================================================


def _validate_donchian_inputs(
    params: DonchianStrategyParams,
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
) -> None:
    """Donchian 전략 입력을 검증한다.

    Args:
        params: 전략 파라미터
        signal_df: 시그널 DataFrame
        trade_df: 매매 DataFrame

    Raises:
        ValueError: 유효하지 않은 입력
    """
    if params.entry_channel_days <= 0 or params.exit_channel_days <= 0:
        raise ValueError(f"채널 일수는 1 이상이어야 합니다: " f"entry={params.entry_channel_days}, exit={params.exit_channel_days}")

    if params.initial_capital <= 0:
        raise ValueError(f"초기 자본금은 양수여야 합니다: {params.initial_capital}")

    # 최소 데이터 행 수: entry_channel_days + 2 (rolling + shift + 최소 1일 실행)
    min_rows = params.entry_channel_days + 2
    if len(signal_df) < min_rows:
        raise ValueError(
            f"데이터 행 수가 부족합니다: {len(signal_df)}행 < 최소 {min_rows}행 "
            f"(entry_channel_days={params.entry_channel_days} + 2)"
        )

    if len(trade_df) < min_rows:
        raise ValueError(f"매매 데이터 행 수가 부족합니다: {len(trade_df)}행 < 최소 {min_rows}행")


def _record_donchian_equity(
    current_date: date,
    capital: float,
    position: int,
    close_price: float,
    upper_channel: float | None,
    lower_channel: float | None,
) -> DonchianEquityRecord:
    """일별 equity를 기록한다.

    Args:
        current_date: 현재 날짜
        capital: 현재 현금
        position: 현재 포지션 수량
        close_price: 당일 종가 (trade_df 기준)
        upper_channel: 당일 상단 채널 값
        lower_channel: 당일 하단 채널 값

    Returns:
        DonchianEquityRecord 딕셔너리
    """
    if position > 0:
        equity = capital + position * close_price
    else:
        equity = capital

    return {
        "Date": current_date,
        "equity": equity,
        "position": position,
        "upper_channel": upper_channel,
        "lower_channel": lower_channel,
    }


# ============================================================================
# 핵심 전략 실행 함수
# ============================================================================


def run_donchian_strategy(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    params: DonchianStrategyParams,
    log_trades: bool = True,
    strategy_name: str = "donchian_channel",
) -> tuple[pd.DataFrame, pd.DataFrame, DonchianStrategyResultDict]:
    """Donchian Channel 전략을 실행한다.

    Args:
        signal_df: 시그널 DataFrame (QQQ). 채널 계산 및 신호 감지에 사용.
        trade_df: 매매 DataFrame (TQQQ). 체결 가격 및 equity 계산에 사용.
        params: DonchianStrategyParams
        log_trades: 거래 로그 출력 여부
        strategy_name: 전략 이름 (로깅용)

    Returns:
        (trades_df, equity_df, summary) 튜플
        - trades_df: 거래 내역 DataFrame
        - equity_df: equity 곡선 DataFrame
        - summary: 성과 요약 딕셔너리

    Raises:
        ValueError: 유효하지 않은 입력
        PendingOrderConflictError: pending order 충돌
    """
    # 1. 입력 검증
    _validate_donchian_inputs(params, signal_df, trade_df)

    # 2. Donchian Channel 계산
    upper_series, lower_series = compute_donchian_channels(
        signal_df, params.entry_channel_days, params.exit_channel_days
    )

    # 3. 상태 초기화
    capital: float = params.initial_capital
    position: int = 0
    entry_price: float = 0.0
    entry_date: date = signal_df.iloc[0][COL_DATE]
    pending_order: _DonchianPendingOrder | None = None

    trades: list[DonchianTradeRecord] = []
    equity_records: list[DonchianEquityRecord] = []

    prev_upper: float | None = None
    prev_lower: float | None = None
    prev_close: float | None = None

    # 4. 첫날 equity 기록
    first_signal_row = signal_df.iloc[0]
    first_trade_row = trade_df.iloc[0]
    first_date: date = first_signal_row[COL_DATE]
    first_upper = upper_series.iloc[0] if pd.notna(upper_series.iloc[0]) else None
    first_lower = lower_series.iloc[0] if pd.notna(lower_series.iloc[0]) else None

    equity_records.append(
        _record_donchian_equity(
            first_date,
            capital,
            position,
            float(first_trade_row[COL_CLOSE]),
            first_upper,
            first_lower,
        )
    )
    prev_close = float(first_signal_row[COL_CLOSE])
    prev_upper = first_upper
    prev_lower = first_lower

    # 5. 일별 루프 (i=1부터)
    for i in range(1, len(signal_df)):
        signal_row = signal_df.iloc[i]
        trade_row = trade_df.iloc[i]
        current_date = signal_row[COL_DATE]

        signal_close = float(signal_row[COL_CLOSE])
        trade_open = float(trade_row[COL_OPEN])
        trade_close = float(trade_row[COL_CLOSE])

        # 5-1. 채널값 조회
        upper_val = float(upper_series.iloc[i]) if pd.notna(upper_series.iloc[i]) else None
        lower_val = float(lower_series.iloc[i]) if pd.notna(lower_series.iloc[i]) else None

        # 5-2. Pending order 체결
        if pending_order is not None:
            if pending_order.order_type == "buy":
                # 매수 체결: trade_df 시가 기준
                buy_price = trade_open * (1 + SLIPPAGE_RATE)
                shares = int(capital / buy_price)

                if shares > 0:
                    buy_amount = shares * buy_price
                    capital -= buy_amount
                    position = shares
                    entry_price = buy_price
                    entry_date = current_date

                    if log_trades:
                        logger.debug(
                            f"[{strategy_name}] 매수 체결: "
                            f"날짜={current_date}, 가격={buy_price:.2f}, "
                            f"수량={shares}, 잔액={capital:.0f}"
                        )
                else:
                    if log_trades:
                        logger.debug(f"[{strategy_name}] 매수 불가 (자본 부족): " f"날짜={current_date}, 필요가격={buy_price:.2f}")

                pending_order = None

            elif pending_order.order_type == "sell":
                # 매도 체결: trade_df 시가 기준
                sell_price = trade_open * (1 - SLIPPAGE_RATE)
                sell_amount = position * sell_price
                capital += sell_amount

                trade_record: DonchianTradeRecord = {
                    "entry_date": entry_date,
                    "exit_date": current_date,
                    "entry_price": entry_price,
                    "exit_price": sell_price,
                    "shares": position,
                    "pnl": (sell_price - entry_price) * position,
                    "pnl_pct": (sell_price - entry_price) / entry_price,
                }
                trades.append(trade_record)

                if log_trades:
                    logger.debug(
                        f"[{strategy_name}] 매도 체결: "
                        f"날짜={current_date}, 가격={sell_price:.2f}, "
                        f"PnL={trade_record['pnl']:.0f}"
                    )

                position = 0
                pending_order = None

        # 5-3. Equity 기록
        equity_records.append(
            _record_donchian_equity(
                current_date,
                capital,
                position,
                trade_close,
                upper_val,
                lower_val,
            )
        )

        # 5-4. 신호 감지 (채널값 유효할 때만)
        if pending_order is None:
            # 매수 신호: position == 0 AND 상향 돌파
            if (
                position == 0
                and upper_val is not None
                and prev_upper is not None
                and prev_close <= prev_upper
                and signal_close > upper_val
            ):
                pending_order = _DonchianPendingOrder(
                    order_type="buy",
                    signal_date=current_date,
                )
                if log_trades:
                    logger.debug(
                        f"[{strategy_name}] 매수 신호: "
                        f"날짜={current_date}, 종가={signal_close:.2f}, "
                        f"upper_channel={upper_val:.2f}"
                    )

            # 매도 신호: position > 0 AND 하향 돌파
            elif (
                position > 0
                and lower_val is not None
                and prev_lower is not None
                and prev_close >= prev_lower
                and signal_close < lower_val
            ):
                pending_order = _DonchianPendingOrder(
                    order_type="sell",
                    signal_date=current_date,
                )
                if log_trades:
                    logger.debug(
                        f"[{strategy_name}] 매도 신호: "
                        f"날짜={current_date}, 종가={signal_close:.2f}, "
                        f"lower_channel={lower_val:.2f}"
                    )

        else:
            # Pending order 충돌 감지 (pending_order가 존재하는 경우)
            # 매수 pending 중 매도 신호 또는 매도 pending 중 매수 신호
            if (
                pending_order.order_type == "buy"
                and position == 0
                and lower_val is not None
                and prev_lower is not None
                and prev_close >= prev_lower
                and signal_close < lower_val
            ):
                raise PendingOrderConflictError(
                    f"매수 pending 중 매도 신호 발생: " f"pending_date={pending_order.signal_date}, current_date={current_date}"
                )

            if (
                pending_order.order_type == "sell"
                and position > 0
                and upper_val is not None
                and prev_upper is not None
                and prev_close <= prev_upper
                and signal_close > upper_val
            ):
                raise PendingOrderConflictError(
                    f"매도 pending 중 매수 신호 발생: " f"pending_date={pending_order.signal_date}, current_date={current_date}"
                )

        # 5-5. 이전값 업데이트
        prev_close = signal_close
        prev_upper = upper_val
        prev_lower = lower_val

    # 6. 결과 구성
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_records)

    # 7. 성과 요약 계산
    base_summary: SummaryDict = calculate_summary(trades_df, equity_df, params.initial_capital)

    summary: DonchianStrategyResultDict = {
        **base_summary,
        "strategy": strategy_name,
        "entry_channel_days": params.entry_channel_days,
        "exit_channel_days": params.exit_channel_days,
    }

    # 8. 미청산 포지션 기록
    if position > 0:
        summary["open_position"] = {
            "entry_date": str(entry_date),
            "entry_price": round(entry_price, 6),
            "shares": position,
        }

    return trades_df, equity_df, summary
