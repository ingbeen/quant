"""백테스트 단일 전략 시각화 대시보드

QQQ 시그널 + TQQQ 매매 버퍼존 전략의 백테스트 결과를 시각화한다.
Streamlit + lightweight-charts-v5 + Plotly 기반 인터랙티브 대시보드.

실행 명령어:
    poetry run streamlit run scripts/backtest/app_single_backtest.py
"""

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component  # type: ignore[import-untyped]

from qbt.backtest import (
    BufferStrategyParams,
    add_single_moving_average,
    load_best_grid_params,
    run_buffer_strategy,
)
from qbt.backtest.constants import (
    DEFAULT_BUFFER_ZONE_PCT,
    DEFAULT_HOLD_DAYS,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MA_WINDOW,
    DEFAULT_RECENT_MONTHS,
)
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    GRID_RESULTS_PATH,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils.data_loader import load_stock_data

# ============================================================
# 로컬 상수 (이 파일에서만 사용)
# ============================================================

# --- Sidebar 파라미터 범위 ---
DEFAULT_MA_WINDOW_MIN = 50
DEFAULT_MA_WINDOW_MAX = 300
DEFAULT_BUFFER_ZONE_PCT_MIN = 0.01
DEFAULT_BUFFER_ZONE_PCT_MAX = 0.10
DEFAULT_BUFFER_ZONE_PCT_STEP = 0.01
DEFAULT_HOLD_DAYS_MIN = 0
DEFAULT_HOLD_DAYS_MAX = 10
DEFAULT_RECENT_MONTHS_MIN = 0
DEFAULT_RECENT_MONTHS_MAX = 12

# --- 차트 높이 ---
DEFAULT_CANDLE_PANE_HEIGHT = 500
DEFAULT_CHANGE_PANE_HEIGHT = 100
DEFAULT_EQUITY_PANE_HEIGHT = 200
DEFAULT_DRAWDOWN_CHART_HEIGHT = 300

# --- 차트 색상 ---
COLOR_UP = "rgb(38, 166, 154)"
COLOR_DOWN = "rgb(239, 83, 80)"
COLOR_MA_LINE = "rgba(255, 152, 0, 0.9)"
COLOR_UPPER_BAND = "rgba(33, 150, 243, 0.4)"
COLOR_LOWER_BAND = "rgba(244, 67, 54, 0.4)"
COLOR_BUY_MARKER = "#26a69a"
COLOR_SELL_MARKER = "#ef5350"
COLOR_EQUITY_LINE = "rgba(33, 150, 243, 1)"
COLOR_EQUITY_TOP = "rgba(33, 150, 243, 0.3)"
COLOR_EQUITY_BOTTOM = "rgba(33, 150, 243, 0.05)"
COLOR_CHANGE_POSITIVE = "rgba(38, 166, 154, 0.6)"
COLOR_CHANGE_NEGATIVE = "rgba(239, 83, 80, 0.6)"
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
    "exit_reason": "청산사유",
    "buffer_zone_pct": "버퍼존",
    "hold_days_used": "유지일",
    "recent_buy_count": "최근매수횟수",
}

# --- 월별 히트맵 한글 월 레이블 ---
MONTH_LABELS = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]

# --- 초기 줌 레벨 ---
DEFAULT_ZOOM_LEVEL = 200


# ============================================================
# 데이터 로딩 함수
# ============================================================


@st.cache_data
def _load_signal_data(path: Path) -> pd.DataFrame:
    """시그널(QQQ) 데이터를 로드하고 캐싱한다."""
    return load_stock_data(path)


@st.cache_data
def _load_trade_data(path: Path) -> pd.DataFrame:
    """매매(TQQQ) 데이터를 로드하고 캐싱한다."""
    return load_stock_data(path)


@st.cache_data
def _load_grid_params(path: Path) -> dict[str, object] | None:
    """grid_results.csv에서 최적 파라미터를 로드한다."""
    result = load_best_grid_params(path)
    if result is not None:
        return dict(result)
    return None


# ============================================================
# 전략 실행 함수 (캐싱)
# ============================================================


@st.cache_data
def _run_strategy(
    _signal_df: pd.DataFrame,
    _trade_df: pd.DataFrame,
    ma_window: int,
    ma_type: str,
    buffer_zone_pct: float,
    hold_days: int,
    recent_months: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object], pd.DataFrame]:
    """
    전략을 실행하고 결과를 캐싱한다.

    Args:
        _signal_df: 시그널 DataFrame (언더스코어 접두사: Streamlit 캐시 해싱 제외)
        _trade_df: 매매 DataFrame
        ma_window: 이동평균 기간
        ma_type: 이동평균 유형 (sma/ema)
        buffer_zone_pct: 버퍼존 비율
        hold_days: 유지일
        recent_months: 조정기간

    Returns:
        tuple: (trades_df, equity_df, summary, processed_signal_df)
    """
    # 1. 이동평균 계산
    signal_df = add_single_moving_average(_signal_df.copy(), ma_window, ma_type)
    trade_df = _trade_df.copy()

    # 2. 공통 날짜 필터링
    common_dates = set(signal_df[COL_DATE]) & set(trade_df[COL_DATE])
    signal_df = signal_df[signal_df[COL_DATE].isin(common_dates)].reset_index(drop=True)
    trade_df = trade_df[trade_df[COL_DATE].isin(common_dates)].reset_index(drop=True)

    # 3. 전략 파라미터 설정
    params = BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=ma_window,
        buffer_zone_pct=buffer_zone_pct,
        hold_days=hold_days,
        recent_months=recent_months,
    )

    # 4. 전략 실행
    trades_df, equity_df, summary = run_buffer_strategy(signal_df, trade_df, params, log_trades=False)

    return trades_df, equity_df, dict(summary), signal_df


# ============================================================
# 차트 데이터 변환 함수
# ============================================================


def _build_candle_data(signal_df: pd.DataFrame) -> list[dict[str, object]]:
    """signal_df를 lightweight-charts 캔들스틱 데이터로 변환한다."""
    candle_data: list[dict[str, object]] = []
    for _, row in signal_df.iterrows():
        d: date = row[COL_DATE]
        candle_data.append(
            {
                "time": d.strftime("%Y-%m-%d"),
                "open": float(row[COL_OPEN]),
                "high": float(row[COL_HIGH]),
                "low": float(row[COL_LOW]),
                "close": float(row[COL_CLOSE]),
            }
        )
    return candle_data


def _build_ma_data(signal_df: pd.DataFrame, ma_col: str) -> list[dict[str, object]]:
    """이동평균 데이터를 Line 시리즈용으로 변환한다."""
    ma_data: list[dict[str, object]] = []
    for _, row in signal_df.iterrows():
        val = row[ma_col]
        if pd.notna(val):
            d: date = row[COL_DATE]
            ma_data.append({"time": d.strftime("%Y-%m-%d"), "value": float(val)})
    return ma_data


def _build_band_data(equity_df: pd.DataFrame, band_col: str) -> list[dict[str, object]]:
    """밴드(upper/lower) 데이터를 Line 시리즈용으로 변환한다."""
    band_data: list[dict[str, object]] = []
    for _, row in equity_df.iterrows():
        val = row[band_col]
        if val is not None and pd.notna(val):
            d: date = row[COL_DATE]
            band_data.append({"time": d.strftime("%Y-%m-%d"), "value": float(val)})
    return band_data


def _build_markers(trades_df: pd.DataFrame) -> list[dict[str, object]]:
    """trades_df에서 Buy/Sell 마커를 생성한다."""
    markers: list[dict[str, object]] = []
    if trades_df.empty:
        return markers

    for _, trade in trades_df.iterrows():
        # Buy 마커 (진입일)
        entry_d: date = trade["entry_date"]
        markers.append(
            {
                "time": entry_d.strftime("%Y-%m-%d"),
                "position": "belowBar",
                "color": COLOR_BUY_MARKER,
                "shape": "arrowUp",
                "text": f"Buy ${trade['entry_price']:.1f}",
                "size": 1,
            }
        )
        # Sell 마커 (청산일)
        exit_d: date = trade["exit_date"]
        pnl_pct = trade["pnl_pct"] * 100
        markers.append(
            {
                "time": exit_d.strftime("%Y-%m-%d"),
                "position": "aboveBar",
                "color": COLOR_SELL_MARKER,
                "shape": "arrowDown",
                "text": f"Sell {pnl_pct:+.1f}%",
                "size": 1,
            }
        )

    return markers


def _build_change_pct_data(signal_df: pd.DataFrame) -> list[dict[str, object]]:
    """전일대비% 데이터를 Histogram 시리즈용으로 변환한다."""
    close_series = signal_df[COL_CLOSE]
    change_pct = close_series.pct_change() * 100

    histogram_data: list[dict[str, object]] = []
    for i in range(len(signal_df)):
        if pd.notna(change_pct.iloc[i]):
            d: date = signal_df.iloc[i][COL_DATE]
            val = float(change_pct.iloc[i])
            color = COLOR_CHANGE_POSITIVE if val >= 0 else COLOR_CHANGE_NEGATIVE
            histogram_data.append({"time": d.strftime("%Y-%m-%d"), "value": val, "color": color})

    return histogram_data


def _build_equity_data(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """에쿼티 곡선 데이터를 Area 시리즈용으로 변환한다."""
    equity_data: list[dict[str, object]] = []
    for _, row in equity_df.iterrows():
        d: date = row[COL_DATE]
        equity_data.append({"time": d.strftime("%Y-%m-%d"), "value": float(row["equity"])})
    return equity_data


def _build_drawdown_data(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """드로우다운 데이터를 Area 시리즈용으로 변환한다."""
    equity_series = equity_df["equity"].astype(float)
    peak = equity_series.cummax()
    # peak가 0인 경우 방어
    safe_peak = peak.replace(0, 1e-12)
    drawdown = (equity_series - peak) / safe_peak * 100

    dd_data: list[dict[str, object]] = []
    for i in range(len(equity_df)):
        d: date = equity_df.iloc[i][COL_DATE]
        dd_data.append({"time": d.strftime("%Y-%m-%d"), "value": float(drawdown.iloc[i])})

    return dd_data


# ============================================================
# 차트 렌더링 함수
# ============================================================


def _render_main_chart(
    signal_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    ma_col: str,
) -> None:
    """메인 차트를 렌더링한다 (캔들+MA+밴드+마커+전일대비%+에쿼티)."""
    # 1. 데이터 준비
    candle_data = _build_candle_data(signal_df)
    ma_data = _build_ma_data(signal_df, ma_col)
    upper_band_data = _build_band_data(equity_df, "upper_band")
    lower_band_data = _build_band_data(equity_df, "lower_band")
    markers = _build_markers(trades_df)
    change_data = _build_change_pct_data(signal_df)
    equity_data = _build_equity_data(equity_df)

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
    }

    # 3. Pane 1: 캔들스틱 + MA + 밴드 + 마커
    candle_series: dict[str, object] = {
        "type": "Candlestick",
        "data": candle_data,
        "options": {
            "upColor": COLOR_UP,
            "downColor": COLOR_DOWN,
            "borderVisible": False,
            "wickUpColor": COLOR_UP,
            "wickDownColor": COLOR_DOWN,
            "priceLineVisible": True,
        },
    }
    if markers:
        candle_series["markers"] = markers

    pane1_series: list[dict[str, object]] = [candle_series]

    # MA 오버레이
    if ma_data:
        pane1_series.append(
            {
                "type": "Line",
                "data": ma_data,
                "options": {
                    "color": COLOR_MA_LINE,
                    "lineWidth": 2,
                    "priceLineVisible": False,
                    "crosshairMarkerVisible": False,
                },
            }
        )

    # Upper Band 오버레이
    if upper_band_data:
        pane1_series.append(
            {
                "type": "Line",
                "data": upper_band_data,
                "options": {
                    "color": COLOR_UPPER_BAND,
                    "lineWidth": 1,
                    "lineStyle": 2,
                    "priceLineVisible": False,
                    "crosshairMarkerVisible": False,
                },
            }
        )

    # Lower Band 오버레이
    if lower_band_data:
        pane1_series.append(
            {
                "type": "Line",
                "data": lower_band_data,
                "options": {
                    "color": COLOR_LOWER_BAND,
                    "lineWidth": 1,
                    "lineStyle": 2,
                    "priceLineVisible": False,
                    "crosshairMarkerVisible": False,
                },
            }
        )

    pane1 = {
        "chart": chart_theme,
        "series": pane1_series,
        "height": DEFAULT_CANDLE_PANE_HEIGHT,
        "title": "QQQ (시그널)",
    }

    # 4. Pane 2: 전일대비% Histogram
    pane2 = {
        "chart": chart_theme,
        "series": [
            {
                "type": "Histogram",
                "data": change_data,
                "options": {
                    "priceLineVisible": False,
                    "priceFormat": {"type": "custom", "formatter": "{value}%"},
                },
            }
        ],
        "height": DEFAULT_CHANGE_PANE_HEIGHT,
        "title": "전일대비 (%)",
    }

    # 5. Pane 3: 에쿼티 곡선
    pane3 = {
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
                    "priceFormat": {"type": "custom", "formatter": "{value}"},
                },
            }
        ],
        "height": DEFAULT_EQUITY_PANE_HEIGHT,
        "title": "에쿼티 (원)",
    }

    # 6. 렌더링
    total_height = DEFAULT_CANDLE_PANE_HEIGHT + DEFAULT_CHANGE_PANE_HEIGHT + DEFAULT_EQUITY_PANE_HEIGHT
    lightweight_charts_v5_component(
        name="backtest_main_chart",
        charts=[pane1, pane2, pane3],
        height=total_height,
        zoom_level=DEFAULT_ZOOM_LEVEL,
        key="main_chart",
    )


def _render_drawdown_chart(equity_df: pd.DataFrame) -> None:
    """드로우다운 차트를 별도 컴포넌트로 렌더링한다."""
    dd_data = _build_drawdown_data(equity_df)

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
    }

    pane = {
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
                    "priceFormat": {"type": "custom", "formatter": "{value}%"},
                    "invertFilledArea": True,
                },
            }
        ],
        "height": DEFAULT_DRAWDOWN_CHART_HEIGHT,
        "title": "드로우다운 (%)",
    }

    lightweight_charts_v5_component(
        name="backtest_drawdown",
        charts=[pane],
        height=DEFAULT_DRAWDOWN_CHART_HEIGHT,
        zoom_level=DEFAULT_ZOOM_LEVEL,
        key="drawdown_chart",
    )


def _render_monthly_heatmap(equity_df: pd.DataFrame) -> None:
    """월별/연도별 수익률 히트맵을 Plotly로 렌더링한다."""
    if equity_df.empty or len(equity_df) < 2:
        st.info("월별 수익률 히트맵을 표시하기에 데이터가 부족합니다.")
        return

    # 1. 에쿼티 데이터를 날짜 인덱스로 변환
    eq = equity_df[[COL_DATE, "equity"]].copy()
    eq[COL_DATE] = pd.to_datetime(eq[COL_DATE])
    eq = eq.set_index(COL_DATE)

    # 2. 월말 리샘플링
    monthly_equity = eq["equity"].resample("ME").last().dropna()
    if len(monthly_equity) < 2:
        st.info("월별 수익률 히트맵을 표시하기에 데이터가 부족합니다.")
        return

    # 3. 월간 수익률 계산 (%)
    monthly_returns = monthly_equity.pct_change().dropna() * 100

    # 4. 연도-월 피벗 테이블 생성
    dt_index = pd.DatetimeIndex(monthly_returns.index)
    returns_df = pd.DataFrame(
        {
            "return_pct": monthly_returns.values,
            "year": dt_index.year,
            "month": dt_index.month,
        }
    )

    pivot = returns_df.pivot_table(values="return_pct", index="year", columns="month")

    # 5. 피벗 테이블을 Plotly 히트맵으로 변환
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

    # 6. 최대 절대값으로 대칭 색상 스케일 설정
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
    if trades_df.empty:
        st.info("거래 내역이 없어 보유 기간 히스토그램을 표시할 수 없습니다.")
        return

    # 보유 기간 계산 (일)
    holding_days = []
    for _, trade in trades_df.iterrows():
        entry: date = trade["entry_date"]
        exit_d: date = trade["exit_date"]
        days = (exit_d - entry).days
        holding_days.append(days)

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
# 메인 앱
# ============================================================


def main() -> None:
    """Streamlit 앱 메인 함수."""
    try:
        # ---- 페이지 설정 ----
        st.set_page_config(
            page_title="백테스트 전략 대시보드",
            page_icon=":chart_with_upwards_trend:",
            layout="wide",
        )

        st.title("백테스트 전략 대시보드")
        st.markdown("QQQ 시그널 + TQQQ 매매 버퍼존 전략 백테스트 결과를 시각화합니다.")

        # ---- 데이터 로딩 ----
        signal_df = _load_signal_data(QQQ_DATA_PATH)
        trade_df = _load_trade_data(TQQQ_SYNTHETIC_DATA_PATH)
        grid_params = _load_grid_params(GRID_RESULTS_PATH)

        # ---- Sidebar: 파라미터 설정 ----
        st.sidebar.header("전략 파라미터")

        if grid_params is not None:
            st.sidebar.success("grid_results.csv 최적값 로드됨")
            default_ma = int(str(grid_params["ma_window"]))
            default_bz = float(str(grid_params["buffer_zone_pct"]))
            default_hd = int(str(grid_params["hold_days"]))
            default_rm = int(str(grid_params["recent_months"]))
        else:
            st.sidebar.info("grid_results.csv 없음, 기본값 사용")
            default_ma = DEFAULT_MA_WINDOW
            default_bz = DEFAULT_BUFFER_ZONE_PCT
            default_hd = DEFAULT_HOLD_DAYS
            default_rm = DEFAULT_RECENT_MONTHS

        ma_type = st.sidebar.selectbox("이동평균 유형", options=["ema", "sma"], index=0, format_func=lambda x: x.upper())

        ma_window = st.sidebar.slider(
            "이동평균 기간",
            min_value=DEFAULT_MA_WINDOW_MIN,
            max_value=DEFAULT_MA_WINDOW_MAX,
            value=min(max(default_ma, DEFAULT_MA_WINDOW_MIN), DEFAULT_MA_WINDOW_MAX),
            step=10,
        )

        buffer_zone_pct = st.sidebar.slider(
            "버퍼존 비율",
            min_value=DEFAULT_BUFFER_ZONE_PCT_MIN,
            max_value=DEFAULT_BUFFER_ZONE_PCT_MAX,
            value=min(max(default_bz, DEFAULT_BUFFER_ZONE_PCT_MIN), DEFAULT_BUFFER_ZONE_PCT_MAX),
            step=DEFAULT_BUFFER_ZONE_PCT_STEP,
            format="%.2f",
        )

        hold_days = st.sidebar.slider(
            "유지일 (hold_days)",
            min_value=DEFAULT_HOLD_DAYS_MIN,
            max_value=DEFAULT_HOLD_DAYS_MAX,
            value=min(max(default_hd, DEFAULT_HOLD_DAYS_MIN), DEFAULT_HOLD_DAYS_MAX),
        )

        recent_months = st.sidebar.slider(
            "조정기간 (월)",
            min_value=DEFAULT_RECENT_MONTHS_MIN,
            max_value=DEFAULT_RECENT_MONTHS_MAX,
            value=min(max(default_rm, DEFAULT_RECENT_MONTHS_MIN), DEFAULT_RECENT_MONTHS_MAX),
        )

        # ---- 전략 실행 ----
        trades_df, equity_df, summary, processed_signal_df = _run_strategy(
            signal_df,
            trade_df,
            ma_window,
            ma_type,
            buffer_zone_pct,
            hold_days,
            recent_months,
        )

        ma_col = f"ma_{ma_window}"

        # ---- Section 1: 요약 지표 ----
        st.header("요약 지표")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("총 수익률", f"{summary['total_return_pct']:.2f}%")
        with col2:
            st.metric("CAGR", f"{summary['cagr']:.2f}%")
        with col3:
            st.metric("MDD", f"{summary['mdd']:.2f}%")
        with col4:
            total_trades = int(str(summary["total_trades"]))
            win_rate = float(str(summary["win_rate"]))
            st.metric("거래수 / 승률", f"{total_trades}회 / {win_rate:.1f}%")

        st.divider()

        # ---- Section 2: 메인 차트 ----
        st.header("1. QQQ 시그널 차트 + 전략 오버레이")
        st.markdown(
            f"캔들스틱: QQQ OHLC | 이동평균: {ma_type.upper()} {ma_window}일 | "
            f"밴드: 버퍼존 {buffer_zone_pct:.0%} | 마커: Buy/Sell 체결 시점"
        )
        _render_main_chart(processed_signal_df, equity_df, trades_df, ma_col)

        st.divider()

        # ---- Section 3: 드로우다운 차트 ----
        st.header("2. 드로우다운")
        st.markdown("에쿼티 고점 대비 하락률을 시계열로 표시합니다.")
        _render_drawdown_chart(equity_df)

        st.divider()

        # ---- Section 4: 월별 수익률 히트맵 ----
        st.header("3. 월별/연도별 수익률 히트맵")
        st.markdown("에쿼티 기준 월간 수익률을 연도별로 비교합니다.")
        _render_monthly_heatmap(equity_df)

        st.divider()

        # ---- Section 5: 포지션 보유 기간 분포 ----
        st.header("4. 포지션 보유 기간 분포")
        st.markdown("각 거래의 진입~청산 기간(일) 분포를 보여줍니다.")
        _render_holding_period_histogram(trades_df)

        st.divider()

        # ---- Section 6: 사용 파라미터 ----
        st.header("5. 사용 파라미터")
        param_source = "grid_results.csv 최적값" if grid_params is not None else "DEFAULT 상수"
        st.json(
            {
                "기본값 출처": param_source,
                "이동평균 유형": ma_type.upper(),
                "이동평균 기간": ma_window,
                "버퍼존 비율": f"{buffer_zone_pct:.2%}",
                "유지일 (hold_days)": hold_days,
                "조정기간 (월)": recent_months,
                "초기 자본": f"{DEFAULT_INITIAL_CAPITAL:,.0f}원",
                "데이터": {
                    "시그널": str(QQQ_DATA_PATH),
                    "매매": str(TQQQ_SYNTHETIC_DATA_PATH),
                },
            }
        )

        st.divider()

        # ---- Section 7: 전체 거래 상세 내역 ----
        st.header("6. 전체 거래 상세 내역")
        if not trades_df.empty:
            display_df = trades_df.copy()
            # 손익률을 %로 변환
            display_df["pnl_pct"] = display_df["pnl_pct"] * 100
            display_df = display_df.rename(columns=TRADE_COLUMN_RENAME)
            st.dataframe(display_df, width="stretch")  # type: ignore[call-overload]
            st.caption(f"총 {len(trades_df)}건의 거래")
        else:
            st.info("거래 내역이 없습니다.")

        # ---- 푸터 ----
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - 백테스트 전략 대시보드")

    except Exception as e:
        st.error("애플리케이션 실행 중 오류가 발생했습니다:")
        st.exception(e)
        return


if __name__ == "__main__":
    main()
