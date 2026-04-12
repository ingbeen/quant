"""차트 시계열 빌더 (앱 차트 화면용).

자산별 전체 기간 시계열(close / EMA / 버퍼 밴드 / 신호·체결 마커) 을 생성하여
RTDB ``/latest/chart_data/{asset_id}`` 에 업로드할 수 있도록 :class:`ChartSeries`
형태로 반환한다.

본 모듈은 순수 데이터 변환만 담당한다. 실제 RTDB 쓰기는
:func:`live.rtdb_gateway.write_chart_data` 가 수행한다.

원칙:

- 데이터 소스: ``{state_dir}/data/stock/{TICKER}.csv``
- EMA / 밴드는 QBT 의 :func:`add_single_moving_average` 재사용 (SSoT)
- 이동평균 워밍업 구간은 ``None``
- 사용자 체결 마커는 dates 에서 인덱스로 변환
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from live.constants import (
    extract_ticker_from_path,
    get_live_portfolio_config,
    live_csv_path,
)
from live.data_fetcher import load_csv
from live.models import ChartSeries, UserTrade
from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.common_constants import COL_CLOSE, COL_DATE

__all__ = ["build_chart_series"]


def _ticker_for_chart(slot: AssetSlotConfig) -> str:
    """차트는 trade_data_path 의 티커를 우선 사용 (실제 보유 자산 가격)."""
    return extract_ticker_from_path(slot.trade_data_path)


def _to_optional_float_list(values: list[Any]) -> list[float | None]:
    """NaN → None 변환을 포함한 리스트화."""
    out: list[float | None] = []
    for v in values:
        if v is None:
            out.append(None)
        elif isinstance(v, float) and math.isnan(v):
            out.append(None)
        else:
            out.append(float(v))
    return out


def build_chart_series(
    state_dir: Path,
    user_trades: dict[str, list[UserTrade]] | None = None,
    signal_history: dict[str, list[tuple[str, str]]] | None = None,
) -> dict[str, ChartSeries]:
    """자산별 전체 기간 :class:`ChartSeries` 를 생성한다.

    Args:
        state_dir: qbt-live-state 디렉토리 (CSV 위치).
        user_trades: 자산 ID → 사용자 체결 마커 리스트 (선택).
        signal_history: 자산 ID → ``(date_iso, state)`` 튜플 리스트 (선택).
            각 날짜의 신호 상태가 ``"buy"`` / ``"sell"`` 인 경우 해당 날짜 인덱스를
            ``buy_signals`` / ``sell_signals`` 에 기록한다. ``history.load_signal_history``
            로 로드하여 전달한다.

    Returns:
        ``{asset_id: ChartSeries}`` (Q-2-2XS 4 자산).
    """
    user_trades = user_trades or {}
    signal_history = signal_history or {}
    config = get_live_portfolio_config()

    series_map: dict[str, ChartSeries] = {}

    for slot in config.asset_slots:
        ticker = _ticker_for_chart(slot)
        csv_path = live_csv_path(state_dir, ticker)
        df = load_csv(csv_path)

        # MA 컬럼 추가
        df = add_single_moving_average(df, window=slot.ma_window, ma_type=slot.ma_type)
        ma_col = f"ma_{slot.ma_window}"

        dates = [d.isoformat() if hasattr(d, "isoformat") else str(d) for d in df[COL_DATE].tolist()]
        close_list = [float(c) for c in df[COL_CLOSE].tolist()]
        raw_ema = _to_optional_float_list(df[ma_col].tolist())

        # 이동평균 초기 워밍업 (ma_window - 1 일) 은 None 으로 표시
        # QBT 의 EMA 계산은 첫 행부터 값을 채우지만, 차트 표시상 의미 있는 값으로
        # 간주되지 않는 워밍업 구간을 명시적으로 None 으로 마스킹.
        warmup = slot.ma_window - 1
        ema_list: list[float | None] = [None] * min(warmup, len(raw_ema)) + raw_ema[warmup:]

        # 밴드 계산
        upper_list: list[float | None] = []
        lower_list: list[float | None] = []
        for ema in ema_list:
            if ema is None:
                upper_list.append(None)
                lower_list.append(None)
            else:
                upper_list.append(ema * (1.0 + slot.buy_buffer_zone_pct))
                lower_list.append(ema * (1.0 - slot.sell_buffer_zone_pct))

        # 사용자 체결 마커 → dates 의 인덱스로 변환
        date_to_idx = {d: i for i, d in enumerate(dates)}
        user_trades_for_asset = user_trades.get(slot.asset_id, [])
        user_buys = [
            date_to_idx[t.date] for t in user_trades_for_asset if t.direction == "buy" and t.date in date_to_idx
        ]
        user_sells = [
            date_to_idx[t.date] for t in user_trades_for_asset if t.direction == "sell" and t.date in date_to_idx
        ]

        # 과거 신호 이력 → dates 의 인덱스로 변환
        signal_entries = signal_history.get(slot.asset_id, [])
        buy_signals = [date_to_idx[d] for d, s in signal_entries if s == "buy" and d in date_to_idx]
        sell_signals = [date_to_idx[d] for d, s in signal_entries if s == "sell" and d in date_to_idx]

        series_map[slot.asset_id] = ChartSeries(
            dates=dates,
            close=close_list,
            ema_200=ema_list,
            upper_band=upper_list,
            lower_band=lower_list,
            buy_signals=buy_signals,
            sell_signals=sell_signals,
            user_buys=user_buys,
            user_sells=user_sells,
        )

    return series_map
