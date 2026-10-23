"""대시보드 차트 생성 모듈

단일 · 포트폴리오 · 워크포워드 대시보드가 같은 모양으로 그리는 차트를 만든다 —
lightweight-charts 캔들 차트의 패널 설정과 월별 수익률 히트맵(Plotly 그림).
Streamlit 과 차트 컴포넌트는 import 하지 않는다. 컴포넌트 호출과 화면 배치는 각 앱이 한다.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypedDict

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from qbt.backtest.constants import (
    COL_DRAWDOWN_PCT,
    COL_ENTRY_DATE,
    COL_EQUITY,
    COL_EXIT_DATE,
    COL_LOWER_BAND,
    COL_PNL_PCT,
    COL_UPPER_BAND,
)
from qbt.backtest.csv_export import OHLC_CHANGE_PCT_COLUMNS
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN

_PRICE_PANE_HEIGHT = 500
_EQUITY_PANE_HEIGHT = 200
_DRAWDOWN_PANE_HEIGHT = 150
_HEATMAP_MIN_HEIGHT = 250

_COLOR_UP = "rgb(38, 166, 154)"
_COLOR_DOWN = "rgb(239, 83, 80)"
_COLOR_MA_LINE = "rgba(255, 152, 0, 0.9)"
_COLOR_UPPER_BAND = "rgba(33, 150, 243, 0.6)"
_COLOR_LOWER_BAND = "rgba(244, 67, 54, 0.6)"
_COLOR_BUY_MARKER = "#26a69a"
_COLOR_SELL_MARKER = "#ef5350"
_COLOR_EQUITY_LINE = "rgba(33, 150, 243, 1)"
_COLOR_EQUITY_TOP = "rgba(33, 150, 243, 0.3)"
_COLOR_EQUITY_BOTTOM = "rgba(33, 150, 243, 0.05)"
_COLOR_DRAWDOWN_LINE = "rgba(244, 67, 54, 1)"
_COLOR_DRAWDOWN_TOP = "rgba(244, 67, 54, 0.3)"
_COLOR_DRAWDOWN_BOTTOM = "rgba(244, 67, 54, 0.05)"

# 데이터 길이보다 큰 값이면 컴포넌트가 fitContent() 로 전체 기간을 보인다
_ZOOM_FIT_ALL = 99999
_SCROLL_PADDING = 60

_CHART_THEME: dict[str, object] = {
    "layout": {
        "background": {"color": "#131722"},
        "textColor": "#D1D4DC",
        "fontFamily": "Arial",
        "fontSize": 12,
    },
    "grid": {
        "vertLines": {"color": "#1e222d", "visible": True},
        "horzLines": {"color": "#1e222d", "visible": True},
    },
    "crosshair": {
        "mode": 0,
        "vertLine": {"color": "rgba(255, 255, 255, 0.3)", "style": 2},
        "horzLine": {"color": "rgba(255, 255, 255, 0.3)", "style": 2},
    },
    "timeScale": {"minBarSpacing": 0.2},
    "localization": {"dateFormat": "yyyy-MM-dd"},
}

# 캔들 툴팁에 넣는 겹침 표의 열 — (열, 툴팁 키, 표기). 표에 있는 열만 넣는다
_OVERLAY_TOOLTIPS: tuple[tuple[str, str, Callable[[float], str]], ...] = (
    (COL_UPPER_BAND, "upper", lambda v: f"{v:.2f}"),
    (COL_LOWER_BAND, "lower", lambda v: f"{v:.2f}"),
    (COL_EQUITY, "equity", lambda v: f"{int(v):,}"),
    (COL_DRAWDOWN_PCT, "dd", lambda v: f"{v:.2f}"),
)

_MONTH_LABELS = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]
_HEATMAP_COLORSCALE = [[0.0, _COLOR_DOWN], [0.5, "rgb(255, 255, 255)"], [1.0, _COLOR_UP]]


class ChartPane(TypedDict):
    """lightweight-charts 패널 하나."""

    chart: dict[str, object]
    series: list[dict[str, object]]
    height: int
    title: str


class ChartComponentArgs(TypedDict):
    """`lightweight_charts_v5_component` 에 그대로 넘기는 인자."""

    name: str
    charts: list[ChartPane]
    height: int
    zoom_level: int
    scroll_padding: int
    key: str


def _time_strings(dates: pd.Series) -> list[str]:
    return pd.to_datetime(dates).dt.strftime("%Y-%m-%d").tolist()


def _line_data(df: pd.DataFrame, col: str) -> list[dict[str, object]]:
    rows = df[df[col].notna()]
    return [
        {"time": t, "value": float(v)} for t, v in zip(_time_strings(rows[COL_DATE]), rows[col].tolist(), strict=True)
    ]


def _find_ma_column(signal_df: pd.DataFrame) -> str | None:
    for col in signal_df.columns:
        if str(col).startswith("ma_"):
            return str(col)
    return None


def _overlay_tooltips(overlay_df: pd.DataFrame) -> dict[str, dict[str, str]]:
    by_time: dict[str, dict[str, str]] = {}
    times = _time_strings(overlay_df[COL_DATE])
    for col, key, fmt in _OVERLAY_TOOLTIPS:
        if col not in overlay_df.columns:
            continue
        for time, value in zip(times, overlay_df[col].tolist(), strict=True):
            if pd.notna(value):
                by_time.setdefault(time, {})[key] = fmt(float(value))
    return by_time


def _candle_data(signal_df: pd.DataFrame, overlay_df: pd.DataFrame, ma_col: str | None) -> list[dict[str, object]]:
    ohlc = [signal_df[col].tolist() for col in (COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE)]
    pcts = {col: signal_df[col].tolist() for col in OHLC_CHANGE_PCT_COLUMNS}
    ma_values = signal_df[ma_col].tolist() if ma_col is not None else None
    overlay = _overlay_tooltips(overlay_df)

    candles: list[dict[str, object]] = []
    for i, time in enumerate(_time_strings(signal_df[COL_DATE])):
        open_, high, low, close = (float(values[i]) for values in ohlc)
        tooltip = {"open": f"{open_:.2f}", "high": f"{high:.2f}", "low": f"{low:.2f}", "close": f"{close:.2f}"}
        for col, values in pcts.items():
            if pd.notna(values[i]):
                tooltip[col] = f"{float(values[i]):+.2f}"
        if ma_values is not None and pd.notna(ma_values[i]):
            tooltip["ma"] = f"{float(ma_values[i]):.2f}"
        tooltip.update(overlay.get(time, {}))
        candles.append({"time": time, "open": open_, "high": high, "low": low, "close": close, "customValues": tooltip})
    return candles


def _overlay_line(df: pd.DataFrame, col: str, color: str, *, dashed: bool) -> dict[str, object] | None:
    data = _line_data(df, col)
    if not data:
        return None
    options: dict[str, object] = {
        "color": color,
        "lineWidth": 2,
        "priceLineVisible": False,
        "lastValueVisible": False,
        "crosshairMarkerVisible": False,
    }
    if dashed:
        options["lineStyle"] = 2
    return {"type": "Line", "data": data, "options": options}


def build_price_pane(
    signal_df: pd.DataFrame,
    overlay_df: pd.DataFrame,
    markers: list[dict[str, object]],
    *,
    title: str,
) -> ChartPane:
    """캔들 패널 — 이동평균 · 상단 · 하단 밴드 선과 마커를 얹는다.

    Args:
        signal_df: 날짜 · OHLC · 전일대비% 4열과, 있으면 이동평균(`ma_{기간}`) 열
        overlay_df: 밴드 선과 툴팁의 밴드 · 에쿼티 · 드로우다운을 읽을 날짜별 표. 그 열이 있을 때만 넣는다
            (매수 후 보유는 밴드가 없다)
        markers: 캔들에 붙일 마커 (`build_trade_markers` 와 앱이 더한 것). 순서와 관계없이 시간순으로 정렬해 붙인다
        title: 패널 제목
    """
    ma_col = _find_ma_column(signal_df)
    candle_series: dict[str, object] = {
        "type": "Candlestick",
        "data": _candle_data(signal_df, overlay_df, ma_col),
        "options": {
            "upColor": _COLOR_UP,
            "downColor": _COLOR_DOWN,
            "borderVisible": False,
            "wickUpColor": _COLOR_UP,
            "wickDownColor": _COLOR_DOWN,
            "priceLineVisible": False,
        },
    }
    if markers:
        # 보이는 구간의 마커를 날짜로 이진 탐색해 고름 → 시간순이 아니면 확대할 때 마커가 빠짐
        candle_series["markers"] = sorted(markers, key=lambda marker: str(marker["time"]))

    lines: list[dict[str, object] | None] = []
    if ma_col is not None:
        lines.append(_overlay_line(signal_df, ma_col, _COLOR_MA_LINE, dashed=False))
    for col, color in ((COL_UPPER_BAND, _COLOR_UPPER_BAND), (COL_LOWER_BAND, _COLOR_LOWER_BAND)):
        if col in overlay_df.columns:
            lines.append(_overlay_line(overlay_df, col, color, dashed=True))

    series = [candle_series, *(line for line in lines if line is not None)]
    return {"chart": _CHART_THEME, "series": series, "height": _PRICE_PANE_HEIGHT, "title": title}


def build_equity_panes(equity_df: pd.DataFrame) -> list[ChartPane]:
    """에쿼티 · 드로우다운 패널 둘 (캔들 패널 아래에 둔다)."""
    equity_options: dict[str, object] = {
        "lineColor": _COLOR_EQUITY_LINE,
        "topColor": _COLOR_EQUITY_TOP,
        "bottomColor": _COLOR_EQUITY_BOTTOM,
        "lineWidth": 2,
        "priceLineVisible": False,
        "priceFormat": {"type": "price", "precision": 0, "minMove": 1},
    }
    drawdown_options: dict[str, object] = {
        "lineColor": _COLOR_DRAWDOWN_LINE,
        "topColor": _COLOR_DRAWDOWN_TOP,
        "bottomColor": _COLOR_DRAWDOWN_BOTTOM,
        "lineWidth": 2,
        "priceLineVisible": False,
        "priceFormat": {"type": "price", "precision": 2, "minMove": 0.01},
        "invertFilledArea": True,
        "fixedMaxValue": 0,
    }
    return [
        {
            "chart": _CHART_THEME,
            "series": [{"type": "Area", "data": _line_data(equity_df, COL_EQUITY), "options": equity_options}],
            "height": _EQUITY_PANE_HEIGHT,
            "title": "에쿼티 (원)",
        },
        {
            "chart": _CHART_THEME,
            "series": [{"type": "Area", "data": _line_data(equity_df, COL_DRAWDOWN_PCT), "options": drawdown_options}],
            "height": _DRAWDOWN_PANE_HEIGHT,
            "title": "드로우다운 (%)",
        },
    ]


def _buy_marker(time: str, text: str) -> dict[str, object]:
    return {
        "time": time,
        "position": "belowBar",
        "color": _COLOR_BUY_MARKER,
        "shape": "arrowUp",
        "text": text,
        "size": 2,
    }


def build_trade_markers(trades_df: pd.DataFrame, *, open_entry_date: str | None = None) -> list[dict[str, object]]:
    """거래마다 진입일 「Buy」 · 청산일 「Sell ±손익%」, 미청산 진입일이면 「Buy (보유중)」 마커 (거래 순서).

    Buy 에 가격을 적지 않는다 — 캔들은 신호 시세라 신호와 매매 종목이 다른 전략은 체결가가 캔들 가격대와 맞지 않고,
    포트폴리오 거래 기록의 진입가는 체결가가 아니라 매도 시점 평균 단가다.
    """
    markers: list[dict[str, object]] = []
    entries = _time_strings(trades_df[COL_ENTRY_DATE])
    exits = _time_strings(trades_df[COL_EXIT_DATE])
    for entry, exit_, pnl_pct in zip(entries, exits, trades_df[COL_PNL_PCT].tolist(), strict=True):
        markers.append(_buy_marker(entry, "Buy"))
        markers.append(
            {
                "time": exit_,
                "position": "aboveBar",
                "color": _COLOR_SELL_MARKER,
                "shape": "arrowDown",
                "text": f"Sell {float(pnl_pct) * 100:+.1f}%",
                "size": 2,
            }
        )
    if open_entry_date is not None:
        markers.append(_buy_marker(pd.Timestamp(open_entry_date).strftime("%Y-%m-%d"), "Buy (보유중)"))
    return markers


def chart_component_args(panes: list[ChartPane], *, name: str, key: str) -> ChartComponentArgs:
    """컴포넌트 인자 — 높이는 패널 높이의 합이고, 처음에는 전체 기간을 보인다."""
    return {
        "name": name,
        "charts": panes,
        "height": sum(pane["height"] for pane in panes),
        "zoom_level": _ZOOM_FIT_ALL,
        "scroll_padding": _SCROLL_PADDING,
        "key": key,
    }


def build_monthly_heatmap(
    monthly_returns: Sequence[Mapping[str, Any]],
    yearly_returns: Sequence[Mapping[str, Any]],
) -> go.Figure:
    """월별 수익률(연도 × 월) 히트맵 옆에 연간 수익률 열을 붙인 그림.

    월별과 연간은 색 범위를 따로 잡는다(각자 0 을 가운데로 대칭) — 한 범위면 큰 연간 변동이 월별 칸의 대비를 묻는다.

    Args:
        monthly_returns: `summary.json` 의 `monthly_returns` (year · month · return_pct)
        yearly_returns: `summary.json` 의 `yearly_returns` (year · return_pct). 월별에 나온 해가 모두 있어야 한다
    """
    pivot = pd.DataFrame(list(monthly_returns)).pivot_table(values="return_pct", index="year", columns="month")
    years = sorted(pivot.index.tolist())
    yearly_by_year = {int(str(entry["year"])): float(str(entry["return_pct"])) for entry in yearly_returns}

    z_monthly: list[list[float | None]] = []
    for year in years:
        row: list[float | None] = []
        for month in range(1, 13):
            cell = pivot.loc[year, month] if month in pivot.columns else None
            row.append(float(str(cell)) if pd.notna(cell) else None)
        z_monthly.append(row)
    z_yearly = [[yearly_by_year[int(year)]] for year in years]

    text_monthly = [[f"{v:.2f}%" if v is not None else "" for v in row] for row in z_monthly]
    text_yearly = [[f"{row[0]:.2f}%"] for row in z_yearly]
    max_abs_monthly = max(abs(v) for row in z_monthly for v in row if v is not None)
    max_abs_yearly = max(abs(row[0]) for row in z_yearly)
    year_labels = [str(y) for y in years]

    # 월별(12열) · 연간(1열)이 연도 축을 공유한다. 두 그림 사이를 넉넉히 띄워 월별 컬러바 자리를 둔다
    fig = make_subplots(rows=1, cols=2, column_widths=[12, 1], shared_yaxes=True, horizontal_spacing=0.12)
    for col, z, text, x, coloraxis in (
        (1, z_monthly, text_monthly, _MONTH_LABELS, "coloraxis"),
        (2, z_yearly, text_yearly, ["연간"], "coloraxis2"),
    ):
        # plotly-stubs 의 Heatmap 이 2차원 z · 문자열 축을 받지 않아 트레이스를 dict 로 넘긴다
        fig.add_trace(
            {
                "type": "heatmap",
                "z": z,
                "x": x,
                "y": year_labels,
                "text": text,
                "texttemplate": "%{text}",
                "textfont": {"size": 11},
                "coloraxis": coloraxis,
                "hovertemplate": "%{y}년 %{x}: %{text}<extra></extra>",
            },
            row=1,
            col=col,
        )
        fig.update_xaxes(side="top", row=1, col=col)
        fig.update_yaxes(autorange="reversed", row=1, col=col)

    # 컬러바 위치(paper 좌표): column_widths=[12, 1] · horizontal_spacing=0.12 이면 월별 그림이 [0, 0.812],
    # 연간 그림이 [0.932, 1.0] — 월별 컬러바는 월별 그림 바로 오른쪽, 연간 컬러바는 그림 밖 오른쪽 여백에 둔다
    fig.update_layout(
        height=max(_HEATMAP_MIN_HEIGHT, len(years) * 40 + 100),
        coloraxis={
            "colorscale": _HEATMAP_COLORSCALE,
            "cmin": -max_abs_monthly,
            "cmax": max_abs_monthly,
            "colorbar": {"title": "월별 (%)", "x": 0.83, "xanchor": "left", "len": 0.9, "thickness": 14},
        },
        coloraxis2={
            "colorscale": _HEATMAP_COLORSCALE,
            "cmin": -max_abs_yearly,
            "cmax": max_abs_yearly,
            "colorbar": {"title": "연간 (%)", "x": 1.02, "xanchor": "left", "len": 0.9, "thickness": 14},
        },
        margin={"r": 120},
    )
    return fig
