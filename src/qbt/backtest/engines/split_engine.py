"""스플릿 매매 엔진

종가 고점에서 일정 비율씩 내려간 가격마다 칸을 사고, 앞 칸의 매수가로 되판다.
`run_backtest` 는 「최대 1 포지션 + 다음 날 시가 체결」이라 칸마다 다른 진입가와 장중 지정가를 담지 못해 따로 둔다.
체결 · 기록 · 요약은 다른 엔진과 같은 함수를 쓴다.

체결 규칙:
- k번째 칸의 매수가 = 고점 × (1 - 하락 비율)^k, 매도가 = 고점 × (1 - 하락 비율)^(k-1)
- 칸은 1번부터 차고 깊은 칸부터 팔리므로 보유 칸은 언제나 1 ~ n 번이다
- 지정가에 닿으면 그 가격에 체결하고, 시가가 건너뛰면 시가에 체결한다. 칸 가격은 체결가와 무관하게 고정이다
- 일봉에 장중 순서가 없어 캔들 방향으로 가정한다 — 양봉은 시가 → 저가 → 고가 → 종가, 음봉은 시가 → 고가 → 저가 → 종가
- 칸 금액은 칸이 모두 빈 상태에서 첫 칸을 살 때 정하고(자산 ÷ 칸 수), 다시 모두 빌 때까지 고정이다
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from qbt.backtest.analysis import calculate_summary
from qbt.backtest.constants import MIN_VALID_ROWS
from qbt.backtest.engines.engine_common import (
    EquityRecord,
    TradeRecord,
    create_trade_record,
    execute_buy_order,
    execute_sell_order,
    record_equity,
)
from qbt.backtest.types import OpenPositionDict, SummaryDict
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    EPSILON,
    ROUND_PRICE,
)
from qbt.utils import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class _Lot:
    """보유 중인 칸 하나."""

    entry_date: date
    entry_price: float  # 슬리피지 반영 체결가
    shares: int


class _Ladder:
    """고점 · 보유 칸 · 현금 · 칸 금액을 들고 칸을 사고판다."""

    def __init__(self, capital: float, anchor: float, drop_pct: float, max_lots: int) -> None:
        self.cash = capital
        self.anchor = anchor
        self.lots: list[_Lot] = []
        self.trades: list[TradeRecord] = []
        self._ratio = 1 - drop_pct
        self._max_lots = max_lots
        self._lot_amount = capital / max_lots

    def _next_buy_level(self) -> float:
        return self.anchor * self._ratio ** (len(self.lots) + 1)

    def _top_sell_level(self) -> float:
        return self.anchor * self._ratio ** (len(self.lots) - 1)

    def _buy(self, day: date, price_raw: float) -> bool:
        if not self.lots:
            self._lot_amount = self.cash / self._max_lots

        shares, buy_price, cost = execute_buy_order(price_raw, self._lot_amount)
        if shares <= 0:
            logger.debug(f"매수 불가 (칸 금액 부족): 날짜={day}, 필요가격={buy_price:.2f}, 칸 금액={self._lot_amount:.2f}")
            return False
        # 판 칸은 언제나 이익이라 남은 칸의 금액만큼은 현금이 있다
        if cost > self.cash + EPSILON:
            raise RuntimeError(f"내부 불변조건 위반: 칸 비용 {cost} 이 현금 {self.cash} 보다 크다 ({day})")

        self.cash -= cost
        self.lots.append(_Lot(day, buy_price, shares))
        return True

    def _sell(self, day: date, price_raw: float) -> None:
        lot = self.lots.pop()
        sell_price, proceeds, pnl, pnl_pct = execute_sell_order(price_raw, lot.shares, lot.entry_price)
        self.cash += proceeds
        self.trades.append(
            create_trade_record(
                entry_date=lot.entry_date,
                exit_date=day,
                entry_price=lot.entry_price,
                exit_price=sell_price,
                shares=lot.shares,
                pnl=pnl,
                pnl_pct=pnl_pct,
            )
        )

    def buy_down_to(self, price: float, day: date, *, at_price: bool) -> None:
        """가격이 price 까지 내려온 동안 닿은 칸을 산다. at_price 면 칸 가격 대신 price 에 체결한다 (시가 갭)."""
        while len(self.lots) < self._max_lots:
            level = self._next_buy_level()
            if price > level:
                return
            # 1주도 못 사면 멈춘다 — 칸을 건너뛰면 보유 칸이 1 ~ n 번이라는 전제가 깨진다
            if not self._buy(day, price if at_price else level):
                return

    def sell_up_to(self, price: float, day: date, *, at_price: bool) -> None:
        """가격이 price 까지 올라온 동안 닿은 칸을 깊은 칸부터 판다. at_price 면 price 에 체결한다 (시가 갭)."""
        while self.lots:
            level = self._top_sell_level()
            if price < level:
                return
            self._sell(day, price if at_price else level)

    def update_anchor(self, close: float, day: date) -> None:
        """새 최고 종가로 고점을 옮긴다. 칸 가격이 바뀌므로 칸이 모두 빈 상태여야 한다."""
        if close <= self.anchor:
            return
        # 종가가 고점 위면 그날 경로의 끝이 모든 매도가(고점 이하)를 지나므로 칸이 남을 수 없다
        if self.lots:
            raise RuntimeError(f"내부 불변조건 위반: 칸 {len(self.lots)}개 보유 중 새 최고 종가 {close} ({day})")
        self.anchor = close


def _intraday_path(open_price: float, high: float, low: float, close: float) -> tuple[float, float, float]:
    """시가 다음에 지나가는 가격 순서. 양봉(시가 = 종가 포함)은 저가 먼저, 음봉은 고가 먼저."""
    if close >= open_price:
        return (low, high, close)
    return (high, low, close)


def run_split_backtest(
    df: pd.DataFrame,
    initial_capital: float,
    drop_pct: float,
    max_lots: int,
) -> tuple[pd.DataFrame, pd.DataFrame, SummaryDict]:
    """스플릿 매매 백테스트를 실행한다. 첫날은 고점만 기록하고 둘째 날부터 매매한다.

    Args:
        df: 시세 DataFrame (날짜순, Date · Open · High · Low · Close)
        initial_capital: 초기 자본금
        drop_pct: 칸 사이 하락 비율 (0.05 = 5%)
        max_lots: 칸 수

    Returns:
        tuple: (trades_df, equity_df, summary). 끝날 보유 칸은 summary 의 open_lots (없으면 키가 없다)

    Raises:
        ValueError: 파라미터 범위 밖, 필수 컬럼 누락 또는 데이터 부족 시
    """
    if not 0 < drop_pct < 1:
        raise ValueError(f"칸 사이 하락 비율(drop_pct)은 0 초과 1 미만이어야 합니다(0.05 = 5%): {drop_pct}")
    if max_lots < 1:
        raise ValueError(f"칸 수(max_lots)는 1 이상이어야 합니다: {max_lots}")
    missing = {COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE} - set(df.columns)
    if missing:
        raise ValueError(f"스플릿 매매 필수 컬럼 누락: {missing}")
    if len(df) < MIN_VALID_ROWS:
        raise ValueError(f"유효 데이터 부족: {len(df)}행 (최소 {MIN_VALID_ROWS}행 필요)")

    dates = df[COL_DATE].tolist()
    opens = df[COL_OPEN].astype(float).tolist()
    highs = df[COL_HIGH].astype(float).tolist()
    lows = df[COL_LOW].astype(float).tolist()
    closes = df[COL_CLOSE].astype(float).tolist()

    ladder = _Ladder(initial_capital, closes[0], drop_pct, max_lots)
    equity_records: list[EquityRecord] = [record_equity(dates[0], initial_capital, 0, closes[0])]

    for day, open_price, high, low, close in zip(dates[1:], opens[1:], highs[1:], lows[1:], closes[1:], strict=True):
        ladder.sell_up_to(open_price, day, at_price=True)
        ladder.buy_down_to(open_price, day, at_price=True)

        current = open_price
        for target in _intraday_path(open_price, high, low, close):
            if target > current:
                ladder.sell_up_to(target, day, at_price=False)
            elif target < current:
                ladder.buy_down_to(target, day, at_price=False)
            current = target

        position = sum(lot.shares for lot in ladder.lots)
        equity_records.append(record_equity(day, ladder.cash, position, close))
        ladder.update_anchor(close, day)

    trades_df = pd.DataFrame(ladder.trades, columns=list(TradeRecord.__annotations__))
    equity_df = pd.DataFrame(equity_records)
    summary = calculate_summary(trades_df, equity_df, initial_capital)

    # 칸마다 진입가가 달라 open_position 한 줄로 합치지 않는다 — 평균이 진입가처럼 읽힌다
    if ladder.lots:
        open_lots: list[OpenPositionDict] = [
            {
                "entry_date": str(lot.entry_date),
                "entry_price": round(lot.entry_price, ROUND_PRICE),
                "shares": lot.shares,
            }
            for lot in ladder.lots
        ]
        summary["open_lots"] = open_lots

    return trades_df, equity_df, summary
