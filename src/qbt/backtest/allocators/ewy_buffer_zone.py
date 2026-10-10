"""EWY 200일선 배분 규칙

EWY(한국 주식) 종가에 Q-2-2XS 와 같은 버퍼존 신호를 쓴다. 매수 구간은 EWY 100%, 매도 구간은 SHY 100% 다 —
판 돈이 이자 없는 현금이 아니라 기준선과 같은 SHY 로 가야 같은 조건에서 겨룬다.
"""

from collections.abc import Mapping
from datetime import date
from typing import Final

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import ma_col_name
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy

EWY_RISK_ASSET_ID: Final = "ewy"
EWY_SAFE_ASSET_ID: Final = "shy"
EWY_ASSET_IDS: Final = (EWY_RISK_ASSET_ID, EWY_SAFE_ASSET_ID)

_IN_MARKET: Final = {EWY_RISK_ASSET_ID: 1.0, EWY_SAFE_ASSET_ID: 0.0}
_OUT_OF_MARKET: Final = {EWY_RISK_ASSET_ID: 0.0, EWY_SAFE_ASSET_ID: 1.0}


class EwyBufferZoneAllocator:
    """첫 호출은 매도 구간(SHY 100%)으로 시작하고, 그 뒤 버퍼존 신호가 난 날에만 전환한다.

    미보유면 check_buy, 보유면 check_sell 을 하루 한 번 부른다 — 버퍼존 슬롯과 같은 호출 순서라 신호 날짜가 같다.
    보유 여부는 신호로 바꾼다(엔진이 1주 미만으로 0주를 체결해도 보유로 본다).
    """

    def __init__(self, ma_window: int, buy_buffer_pct: float, sell_buffer_pct: float, hold_days: int) -> None:
        self._ma_window = ma_window
        self._strategy = BufferZoneStrategy(ma_col_name(ma_window), buy_buffer_pct, sell_buffer_pct, hold_days)
        self._signal_df: pd.DataFrame | None = None
        self._first_row = 0
        self._held: bool | None = None

    def target_weights(
        self,
        data: Mapping[str, pd.DataFrame],
        i: int,
        current_date: date,
        is_check_day: bool,
    ) -> Mapping[str, float] | None:
        if self._signal_df is None:
            # 이동평균은 잘리기 전 시세로 내고, 전략에는 첫 호출 행을 0 행으로 넘긴다 — 엔진이 슬롯에 시작일로 자른
            # 시세를 넘기는 것과 같게. 0 행이 아니면 전략이 전날 행으로 밴드를 잡아 첫날 돌파를 판정한다
            self._first_row = i
            with_ma = add_single_moving_average(data[EWY_RISK_ASSET_ID], self._ma_window)
            self._signal_df = with_ma.iloc[i:].reset_index(drop=True)
        row = i - self._first_row
        first_call = self._held is None
        held = bool(self._held)

        if not held and self._strategy.check_buy(self._signal_df, row, current_date):
            self._held = True
            return dict(_IN_MARKET)
        if held and self._strategy.check_sell(self._signal_df, row):
            self._held = False
            return dict(_OUT_OF_MARKET)
        if first_call:
            self._held = False
            return dict(_OUT_OF_MARKET)
        return None
