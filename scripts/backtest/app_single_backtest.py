"""백테스트 전략별 시각화 대시보드 (동적 탭)

BACKTEST_RESULTS_DIR 하위 전략별 결과 폴더를 자동 탐색하여
각 전략마다 독립된 탭에서 시각화를 제공한다.
전략이 추가되면 결과 폴더만 있으면 자동으로 탭이 생성된다.

선행 스크립트:
    poetry run python scripts/backtest/run_single_backtest.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_single_backtest.py
"""

import json
from datetime import date
from pathlib import Path
from typing import Any, TypedDict

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component  # type: ignore[import-untyped]

from qbt.common_constants import (
    BACKTEST_RESULTS_DIR,
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
)

# ============================================================
# 로컬 상수 (이 파일에서만 사용)
# ============================================================

# --- 차트 높이 ---
DEFAULT_CANDLE_PANE_HEIGHT = 500
DEFAULT_EQUITY_PANE_HEIGHT = 200
DEFAULT_DRAWDOWN_PANE_HEIGHT = 150

# --- 차트 색상 ---
COLOR_UP = "rgb(38, 166, 154)"
COLOR_DOWN = "rgb(239, 83, 80)"
COLOR_MA_LINE = "rgba(255, 152, 0, 0.9)"
COLOR_UPPER_BAND = "rgba(33, 150, 243, 0.6)"
COLOR_LOWER_BAND = "rgba(244, 67, 54, 0.6)"
COLOR_BUY_MARKER = "#26a69a"
COLOR_SELL_MARKER = "#ef5350"
COLOR_EQUITY_LINE = "rgba(33, 150, 243, 1)"
COLOR_EQUITY_TOP = "rgba(33, 150, 243, 0.3)"
COLOR_EQUITY_BOTTOM = "rgba(33, 150, 243, 0.05)"
COLOR_DRAWDOWN_LINE = "rgba(244, 67, 54, 1)"
COLOR_DRAWDOWN_TOP = "rgba(244, 67, 54, 0.3)"
COLOR_DRAWDOWN_BOTTOM = "rgba(244, 67, 54, 0.05)"

# --- 거래 내역 한글 컬럼 매핑 ---
TRADE_COLUMN_RENAME = {
    "entry_date": "진입일",
    "exit_date": "청산일",
    "entry_price": "진입가",
    "exit_price": "청산가",
    "shares": "수량",
    "pnl": "손익금액",
    "pnl_pct": "손익률",
    "buffer_zone_pct": "버퍼존",
    "hold_days_used": "유지일",
    "recent_buy_count": "최근매수횟수",
    "holding_days": "보유기간(일)",
}

# --- 월별 히트맵 한글 월 레이블 ---
MONTH_LABELS = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]

# --- 초기 줌: 전체 데이터 표시 ---
# 데이터 길이보다 큰 값 → TSX에서 fitContent() 자동 호출
DEFAULT_ZOOM_LEVEL = 99999


# ============================================================
# 전략 데이터 타입
# ============================================================


class StrategyData(TypedDict):
    """자동 탐색된 전략 데이터 컨테이너."""

    strategy_name: str
    display_name: str
    result_dir: Path
    summary_data: dict[str, Any]
    signal_df: pd.DataFrame
    equity_df: pd.DataFrame
    trades_df: pd.DataFrame


# ============================================================
# 전략 자동 탐색
# ============================================================


@st.cache_data
def _load_csv(path_str: str) -> pd.DataFrame:
    """CSV를 로드하고 날짜 컬럼을 파싱한다.

    st.cache_data는 hashable 인자만 지원하므로 Path 대신 str을 사용한다.
    """
    try:
        df = pd.read_csv(path_str)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    if COL_DATE in df.columns:
        df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
    return df


@st.cache_data
def _load_json(path_str: str) -> dict[str, Any]:
    """JSON 파일을 로드한다."""
    with Path(path_str).open("r", encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def _discover_strategies() -> list[StrategyData]:
    """
    BACKTEST_RESULTS_DIR 하위 디렉토리를 스캔하여 전략 데이터를 자동 탐색한다.

    각 디렉토리에 summary.json이 존재하면 유효한 전략 결과로 간주한다.
    display_name은 summary.json에서 필수로 읽으며, 없으면 ValueError를 발생시킨다.

    Returns:
        전략 데이터 리스트 (디렉토리명 정렬)
    """
    if not BACKTEST_RESULTS_DIR.exists():
        return []

    strategies: list[StrategyData] = []

    for subdir in sorted(BACKTEST_RESULTS_DIR.iterdir()):
        if not subdir.is_dir():
            continue

        summary_path = subdir / "summary.json"
        signal_path = subdir / "signal.csv"
        equity_path = subdir / "equity.csv"
        trades_path = subdir / "trades.csv"

        # summary.json, signal.csv, equity.csv 필수
        if not summary_path.exists() or not signal_path.exists() or not equity_path.exists():
            continue

        summary_data = _load_json(str(summary_path))
        signal_df = _load_csv(str(signal_path))
        equity_df = _load_csv(str(equity_path))

        # trades는 선택 (Buy & Hold는 빈 파일)
        if trades_path.exists():
            trades_df = _load_csv(str(trades_path))
            if not trades_df.empty and "entry_date" in trades_df.columns:
                trades_df["entry_date"] = pd.to_datetime(trades_df["entry_date"]).dt.date
            if not trades_df.empty and "exit_date" in trades_df.columns:
                trades_df["exit_date"] = pd.to_datetime(trades_df["exit_date"]).dt.date
        else:
            trades_df = pd.DataFrame()

        # display_name 필수 검증
        display_name = summary_data.get("display_name", "")
        if not display_name:
            raise ValueError(f"summary.json에 display_name이 없습니다: {summary_path}. " "run_single_backtest.py를 재실행하세요.")

        strategies.append(
            StrategyData(
                strategy_name=subdir.name,
                display_name=display_name,
                result_dir=subdir,
                summary_data=summary_data,
                signal_df=signal_df,
                equity_df=equity_df,
                trades_df=trades_df,
            )
        )

    return strategies


# ============================================================
# 차트 데이터 변환 함수 (Feature Detection 기반)
# ============================================================


def _detect_ma_col(signal_df: pd.DataFrame) -> str | None:
    """signal_df에서 ma_* 컬럼을 찾아 반환한다."""
    for col in signal_df.columns:
        if col.startswith("ma_"):
            return col
    return None


def _build_candle_data(
    signal_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    ma_col: str | None,
) -> list[dict[str, object]]:
    """signal_df를 lightweight-charts 캔들스틱 데이터로 변환한다.

    customValues를 포함하여 tooltip에서 표시할 수 있게 한다.
    OHLC 가격, 전일종가대비%, MA, 밴드, 에쿼티, 드로우다운을 포함한다.
    """
    # 1. 밴드 + 에쿼티 + 드로우다운 데이터를 날짜 기준으로 매핑
    has_upper = "upper_band" in equity_df.columns
    has_lower = "lower_band" in equity_df.columns
    has_equity = "equity" in equity_df.columns
    has_drawdown = "drawdown_pct" in equity_df.columns

    equity_map: dict[date, dict[str, float]] = {}
    for row in equity_df.itertuples(index=False):
        d: date = getattr(row, COL_DATE)
        entry: dict[str, float] = {}
        if has_upper and pd.notna(row.upper_band):
            entry["upper"] = float(row.upper_band)  # type: ignore[arg-type]
        if has_lower and pd.notna(row.lower_band):
            entry["lower"] = float(row.lower_band)  # type: ignore[arg-type]
        if has_equity and pd.notna(row.equity):
            entry["equity"] = float(row.equity)  # type: ignore[arg-type]
        if has_drawdown and pd.notna(row.drawdown_pct):
            entry["dd"] = float(row.drawdown_pct)  # type: ignore[arg-type]
        if entry:
            equity_map[d] = entry

    # 2. 전일종가 시리즈 (각 OHLC의 전일종가대비% 계산용)
    prev_close = signal_df[COL_CLOSE].shift(1)

    candle_data: list[dict[str, object]] = []
    for i, row in enumerate(signal_df.itertuples(index=False)):
        d = getattr(row, COL_DATE)
        open_val = float(getattr(row, COL_OPEN))
        high_val = float(getattr(row, COL_HIGH))
        low_val = float(getattr(row, COL_LOW))
        close_val = float(getattr(row, COL_CLOSE))

        candle_entry: dict[str, object] = {
            "time": d.strftime("%Y-%m-%d"),
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
        }

        # 3. customValues 구성 (Record<string, string>)
        cv: dict[str, str] = {}

        # OHLC 가격
        cv["open"] = f"{open_val:.2f}"
        cv["high"] = f"{high_val:.2f}"
        cv["low"] = f"{low_val:.2f}"
        cv["close"] = f"{close_val:.2f}"

        # 전일종가대비% (첫날 제외)
        pc = prev_close.iloc[i]
        if pd.notna(pc) and pc != 0:
            pc_float = float(pc)
            cv["open_pct"] = f"{(open_val / pc_float - 1) * 100:+.2f}"
            cv["high_pct"] = f"{(high_val / pc_float - 1) * 100:+.2f}"
            cv["low_pct"] = f"{(low_val / pc_float - 1) * 100:+.2f}"
            cv["close_pct"] = f"{(close_val / pc_float - 1) * 100:+.2f}"

        # MA
        if ma_col and ma_col in signal_df.columns:
            ma_val = getattr(row, ma_col)
            if pd.notna(ma_val):
                cv["ma"] = f"{ma_val:.2f}"

        # 밴드 + 에쿼티 + 드로우다운
        if d in equity_map:
            eq_data = equity_map[d]
            if "upper" in eq_data:
                cv["upper"] = f"{eq_data['upper']:.2f}"
            if "lower" in eq_data:
                cv["lower"] = f"{eq_data['lower']:.2f}"
            if "equity" in eq_data:
                cv["equity"] = f"{int(eq_data['equity']):,}"
            if "dd" in eq_data:
                cv["dd"] = f"{eq_data['dd']:.2f}"

        if cv:
            candle_entry["customValues"] = cv

        candle_data.append(candle_entry)

    return candle_data


def _build_series_data(df: pd.DataFrame, col: str) -> list[dict[str, object]]:
    """DataFrame의 특정 컬럼에서 Line 시리즈 데이터를 생성한다.

    signal_df의 MA 컬럼, equity_df의 밴드 컬럼 등 공통 변환에 사용한다.
    """
    data: list[dict[str, object]] = []
    for row in df.itertuples(index=False):
        val = getattr(row, col)
        if pd.notna(val):
            d: date = getattr(row, COL_DATE)
            data.append({"time": d.strftime("%Y-%m-%d"), "value": float(val)})
    return data


def _build_markers(trades_df: pd.DataFrame) -> list[dict[str, object]]:
    """trades_df에서 Buy/Sell 마커를 생성한다."""
    markers: list[dict[str, object]] = []
    if trades_df.empty:
        return markers

    for trade in trades_df.itertuples(index=False):
        entry_d: date = trade.entry_date  # type: ignore[assignment]
        markers.append(
            {
                "time": entry_d.strftime("%Y-%m-%d"),
                "position": "belowBar",
                "color": COLOR_BUY_MARKER,
                "shape": "arrowUp",
                "text": f"Buy ${trade.entry_price:.1f}",
                "size": 2,
            }
        )
        exit_d: date = trade.exit_date  # type: ignore[assignment]
        pnl_pct = trade.pnl_pct * 100  # type: ignore[operator]
        markers.append(
            {
                "time": exit_d.strftime("%Y-%m-%d"),
                "position": "aboveBar",
                "color": COLOR_SELL_MARKER,
                "shape": "arrowDown",
                "text": f"Sell {pnl_pct:+.1f}%",
                "size": 2,
            }
        )

    return markers


def _build_open_position_marker(
    summary_data: dict[str, Any],
) -> list[dict[str, object]]:
    """미청산 포지션(summary.json의 open_position)의 Buy 마커를 생성한다.

    Feature Detection: summary에 open_position 키가 있으면 마커를 생성한다.
    모든 전략에 대해 동일하게 동작한다.
    """
    summary = summary_data.get("summary", {})
    open_pos = summary.get("open_position")
    if open_pos is None:
        return []

    return [
        {
            "time": open_pos["entry_date"],
            "position": "belowBar",
            "color": COLOR_BUY_MARKER,
            "shape": "arrowUp",
            "text": f"Buy ${open_pos['entry_price']:.1f} (보유중)",
            "size": 2,
        }
    ]


def _build_equity_data(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """에쿼티 곡선 데이터를 Area 시리즈용으로 변환한다."""
    equity_data: list[dict[str, object]] = []
    for row in equity_df.itertuples(index=False):
        d: date = getattr(row, COL_DATE)
        equity_data.append({"time": d.strftime("%Y-%m-%d"), "value": float(row.equity)})  # type: ignore[arg-type]
    return equity_data


def _build_drawdown_data(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """CSV의 drawdown_pct 컬럼에서 Area 시리즈 데이터를 생성한다."""
    dd_data: list[dict[str, object]] = []
    for row in equity_df.itertuples(index=False):
        d: date = getattr(row, COL_DATE)
        dd_data.append({"time": d.strftime("%Y-%m-%d"), "value": float(row.drawdown_pct)})  # type: ignore[arg-type]
    return dd_data


# ============================================================
# 차트 렌더링 함수 (Feature Detection 기반)
# ============================================================


def _render_main_chart(
    strategy: StrategyData,
    chart_key: str,
) -> None:
    """메인 차트를 렌더링한다 (캔들 + 조건부 MA/밴드/마커 + 에쿼티 + 드로우다운).

    Feature Detection: 컬럼 존재 여부로 오버레이를 결정한다.
    """
    signal_df = strategy["signal_df"]
    equity_df = strategy["equity_df"]
    trades_df = strategy["trades_df"]

    # Feature detection
    ma_col = _detect_ma_col(signal_df)
    has_upper = "upper_band" in equity_df.columns
    has_lower = "lower_band" in equity_df.columns
    has_trades = not trades_df.empty and "entry_date" in trades_df.columns

    # 1. 데이터 준비
    candle_data = _build_candle_data(signal_df, equity_df, ma_col)
    equity_data = _build_equity_data(equity_df)
    dd_data = _build_drawdown_data(equity_df)

    # 2. 차트 테마
    chart_theme = {
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

    # 3. Pane 1: 캔들스틱 + 조건부 오버레이
    candle_series: dict[str, object] = {
        "type": "Candlestick",
        "data": candle_data,
        "options": {
            "upColor": COLOR_UP,
            "downColor": COLOR_DOWN,
            "borderVisible": False,
            "wickUpColor": COLOR_UP,
            "wickDownColor": COLOR_DOWN,
            "priceLineVisible": False,
        },
    }

    # 마커 (완료된 거래 + 미청산 포지션)
    markers: list[dict[str, object]] = []
    if has_trades:
        markers = _build_markers(trades_df)
    open_markers = _build_open_position_marker(strategy["summary_data"])
    markers.extend(open_markers)
    if markers:
        candle_series["markers"] = markers

    pane1_series: list[dict[str, object]] = [candle_series]

    # MA 오버레이 (ma_* 컬럼 존재 시)
    if ma_col:
        ma_data = _build_series_data(signal_df, ma_col)
        if ma_data:
            pane1_series.append(
                {
                    "type": "Line",
                    "data": ma_data,
                    "options": {
                        "color": COLOR_MA_LINE,
                        "lineWidth": 2,
                        "priceLineVisible": False,
                        "lastValueVisible": False,
                        "crosshairMarkerVisible": False,
                    },
                }
            )

    # Upper Band 오버레이
    if has_upper:
        upper_data = _build_series_data(equity_df, "upper_band")
        if upper_data:
            pane1_series.append(
                {
                    "type": "Line",
                    "data": upper_data,
                    "options": {
                        "color": COLOR_UPPER_BAND,
                        "lineWidth": 2,
                        "lineStyle": 2,
                        "priceLineVisible": False,
                        "lastValueVisible": False,
                        "crosshairMarkerVisible": False,
                    },
                }
            )

    # Lower Band 오버레이
    if has_lower:
        lower_data = _build_series_data(equity_df, "lower_band")
        if lower_data:
            pane1_series.append(
                {
                    "type": "Line",
                    "data": lower_data,
                    "options": {
                        "color": COLOR_LOWER_BAND,
                        "lineWidth": 2,
                        "lineStyle": 2,
                        "priceLineVisible": False,
                        "lastValueVisible": False,
                        "crosshairMarkerVisible": False,
                    },
                }
            )

    chart_title = f"{strategy['display_name']}"

    pane1 = {
        "chart": chart_theme,
        "series": pane1_series,
        "height": DEFAULT_CANDLE_PANE_HEIGHT,
        "title": chart_title,
    }

    # 4. Pane 2: 에쿼티 곡선
    pane2 = {
        "chart": chart_theme,
        "series": [
            {
                "type": "Area",
                "data": equity_data,
                "options": {
                    "lineColor": COLOR_EQUITY_LINE,
                    "topColor": COLOR_EQUITY_TOP,
                    "bottomColor": COLOR_EQUITY_BOTTOM,
                    "lineWidth": 2,
                    "priceLineVisible": False,
                    "priceFormat": {"type": "price", "precision": 0, "minMove": 1},
                },
            }
        ],
        "height": DEFAULT_EQUITY_PANE_HEIGHT,
        "title": "에쿼티 (원)",
    }

    # 5. Pane 3: 드로우다운
    pane3 = {
        "chart": chart_theme,
        "series": [
            {
                "type": "Area",
                "data": dd_data,
                "options": {
                    "lineColor": COLOR_DRAWDOWN_LINE,
                    "topColor": COLOR_DRAWDOWN_TOP,
                    "bottomColor": COLOR_DRAWDOWN_BOTTOM,
                    "lineWidth": 2,
                    "priceLineVisible": False,
                    "priceFormat": {"type": "price", "precision": 2, "minMove": 0.01},
                    "invertFilledArea": True,
                    "fixedMaxValue": 0,
                },
            }
        ],
        "height": DEFAULT_DRAWDOWN_PANE_HEIGHT,
        "title": "드로우다운 (%)",
    }

    # 6. 렌더링
    total_height = DEFAULT_CANDLE_PANE_HEIGHT + DEFAULT_EQUITY_PANE_HEIGHT + DEFAULT_DRAWDOWN_PANE_HEIGHT
    lightweight_charts_v5_component(
        name=f"chart_{chart_key}",
        charts=[pane1, pane2, pane3],
        height=total_height,
        zoom_level=DEFAULT_ZOOM_LEVEL,
        scroll_padding=60,
        key=f"main_chart_{chart_key}",
    )


def _render_monthly_heatmap(monthly_returns: list[dict[str, Any]]) -> None:
    """월별/연도별 수익률 히트맵을 Plotly로 렌더링한다."""
    if not monthly_returns:
        st.info("월별 수익률 히트맵을 표시하기에 데이터가 부족합니다.")
        return

    returns_df = pd.DataFrame(monthly_returns)
    pivot = returns_df.pivot_table(values="return_pct", index="year", columns="month")

    years = sorted(pivot.index.tolist())
    months = list(range(1, 13))

    z_values: list[list[float | None]] = []
    for year in years:
        row: list[float | None] = []
        for month in months:
            if month in pivot.columns and year in pivot.index:
                raw_val = pivot.loc[year, month]
                row.append(float(str(raw_val)) if pd.notna(raw_val) else None)
            else:
                row.append(None)
        z_values.append(row)

    flat_values = [v for row in z_values for v in row if v is not None]
    if not flat_values:
        st.info("월별 수익률 데이터가 없습니다.")
        return

    max_abs = max(abs(v) for v in flat_values)

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,  # type: ignore[arg-type]
            x=MONTH_LABELS,  # type: ignore[arg-type]
            y=[str(y) for y in years],  # type: ignore[arg-type]
            colorscale="RdYlGn",
            zmid=0,
            zmin=-max_abs,
            zmax=max_abs,
            text=[[f"{v:.1f}%" if v is not None else "" for v in row] for row in z_values],  # type: ignore[arg-type]
            texttemplate="%{text}",
            textfont={"size": 11},
            hovertemplate="연도: %{y}<br>월: %{x}<br>수익률: %{z:.2f}%<extra></extra>",
            colorbar={"title": "수익률 (%)"},
        )
    )

    fig.update_layout(
        xaxis_title="월",
        yaxis_title="연도",
        yaxis={"autorange": "reversed"},
        height=max(300, len(years) * 40 + 100),
        margin={"l": 60, "r": 40, "t": 30, "b": 60},
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font={"color": "#D1D4DC"},
    )

    st.plotly_chart(fig, width="stretch")


def _render_holding_period_histogram(trades_df: pd.DataFrame) -> None:
    """포지션 보유 기간 분포 히스토그램을 Plotly로 렌더링한다."""
    if trades_df.empty or "holding_days" not in trades_df.columns:
        st.info("이 전략에서는 보유 기간 분포를 표시할 수 없습니다.")
        return

    holding_days = trades_df["holding_days"].tolist()

    fig = go.Figure(
        data=go.Histogram(
            x=holding_days,
            nbinsx=min(30, max(5, len(holding_days))),
            marker_color="rgba(33, 150, 243, 0.7)",
            marker_line={"color": "rgba(33, 150, 243, 1)", "width": 1},
            hovertemplate="보유기간: %{x}일<br>빈도: %{y}<extra></extra>",
        )
    )

    fig.update_layout(
        xaxis_title="보유 기간 (일)",
        yaxis_title="빈도",
        height=300,
        bargap=0.05,
        margin={"l": 60, "r": 40, "t": 30, "b": 60},
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font={"color": "#D1D4DC"},
        xaxis={"gridcolor": "#1e222d"},
        yaxis={"gridcolor": "#1e222d"},
    )

    st.plotly_chart(fig, width="stretch")


# ============================================================
# 전략 탭 렌더링
# ============================================================


def _style_pnl_rows(row: pd.Series) -> list[str]:  # type: ignore[type-arg]
    """손익률 기반 행별 배경색을 반환한다.

    수익 거래는 옅은 초록, 손실 거래는 옅은 빨강 배경을 적용한다.
    """
    pnl_col = TRADE_COLUMN_RENAME.get("pnl_pct", "손익률")
    pnl = row.get(pnl_col, 0)
    if pnl > 0:
        return ["background-color: rgba(38, 166, 154, 0.15)"] * len(row)
    elif pnl < 0:
        return ["background-color: rgba(239, 83, 80, 0.15)"] * len(row)
    return [""] * len(row)


def _render_strategy_tab(strategy: StrategyData) -> None:
    """하나의 전략 탭 내부를 렌더링한다."""
    summary_data = strategy["summary_data"]
    summary = summary_data["summary"]
    params = summary_data.get("params", {})
    monthly_returns: list[dict[str, Any]] = summary_data.get("monthly_returns", [])
    trades_df = strategy["trades_df"]
    has_trades = not trades_df.empty and "entry_date" in trades_df.columns

    # ---- 요약 지표 ----
    st.header("요약 지표")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("총 수익률", f"{summary['total_return_pct']:.2f}%")
    with col2:
        st.metric("CAGR", f"{summary['cagr']:.2f}%")
    with col3:
        st.metric("MDD", f"{summary['mdd']:.2f}%")
    with col4:
        total_trades = int(summary["total_trades"])
        win_rate = float(summary["win_rate"])
        st.metric("거래수 / 승률", f"{total_trades}회 / {win_rate:.1f}%")

    st.divider()

    # ---- Section 1: 메인 차트 ----
    st.header("1. 메인 차트")
    _render_main_chart(strategy, strategy["strategy_name"])

    st.divider()

    # ---- Section 2: 전체 거래 상세 내역 ----
    st.header("2. 전체 거래 상세 내역")
    if has_trades:
        display_df = trades_df.copy()
        display_df["pnl_pct"] = display_df["pnl_pct"] * 100
        display_df = display_df.rename(columns=TRADE_COLUMN_RENAME)
        styled_df = display_df.style.apply(_style_pnl_rows, axis=1)
        st.dataframe(styled_df, width="stretch")  # type: ignore[call-overload]
        st.caption(f"총 {len(trades_df)}건의 거래")
    else:
        st.info("이 전략에서는 거래 내역이 없습니다.")

    st.divider()

    # ---- Section 3: 사용 파라미터 ----
    st.header("3. 사용 파라미터")
    st.json(params)

    st.divider()

    # ---- Section 4: 월별 수익률 히트맵 ----
    st.header("4. 월별/연도별 수익률 히트맵")
    st.markdown("에쿼티 기준 월간 수익률을 연도별로 비교합니다.")
    _render_monthly_heatmap(monthly_returns)

    st.divider()

    # ---- Section 5: 포지션 보유 기간 분포 ----
    st.header("5. 포지션 보유 기간 분포")
    if has_trades:
        st.markdown("각 거래의 진입~청산 기간(일) 분포를 보여줍니다.")
        _render_holding_period_histogram(trades_df)
    else:
        st.info("이 전략에서는 보유 기간 분포를 표시할 수 없습니다.")


# ============================================================
# 메인 앱
# ============================================================


def main() -> None:
    """Streamlit 앱 메인 함수."""
    try:
        st.set_page_config(
            page_title="백테스트 전략 대시보드",
            page_icon=":chart_with_upwards_trend:",
            layout="wide",
        )

        st.title("백테스트 전략 대시보드")
        st.markdown("전략별 백테스트 결과를 시각화합니다. 전략이 추가되면 자동으로 탭이 생성됩니다.")

        # ---- 전략 자동 탐색 ----
        strategies = _discover_strategies()

        if not strategies:
            st.warning(
                "결과 파일이 없습니다. 먼저 백테스트를 실행해주세요:\n\n"
                "```\npoetry run python scripts/backtest/run_single_backtest.py\n```"
            )
            st.stop()
            return

        # ---- 동적 탭 생성 ----
        tab_labels = [s["display_name"] for s in strategies]
        tabs = st.tabs(tab_labels)

        for tab, strategy in zip(tabs, strategies, strict=True):
            with tab:
                _render_strategy_tab(strategy)

        # ---- 푸터 ----
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - 백테스트 전략 대시보드")

    except Exception as e:
        st.error("애플리케이션 실행 중 오류가 발생했습니다:")
        st.exception(e)
        return


if __name__ == "__main__":
    main()
