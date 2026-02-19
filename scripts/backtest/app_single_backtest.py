"""백테스트 단일 전략 시각화 대시보드 (표시 전용)

run_single_backtest.py가 생성한 결과 파일을 로드하여 시각화한다.
Streamlit + lightweight-charts-v5 + Plotly 기반 인터랙티브 대시보드.

선행 스크립트:
    poetry run python scripts/backtest/run_single_backtest.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_single_backtest.py
"""

import json
from datetime import date
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component  # type: ignore[import-untyped]

from qbt.common_constants import (
    BUFFER_ZONE_EQUITY_PATH,
    BUFFER_ZONE_SIGNAL_PATH,
    BUFFER_ZONE_SUMMARY_PATH,
    BUFFER_ZONE_TRADES_PATH,
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

# --- 초기 줌 레벨 ---
DEFAULT_ZOOM_LEVEL = 200


# ============================================================
# 데이터 로딩 함수
# ============================================================


@st.cache_data
def _load_signal_csv() -> pd.DataFrame:
    """시그널 CSV를 로드한다."""
    df = pd.read_csv(BUFFER_ZONE_SIGNAL_PATH)
    df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
    return df


@st.cache_data
def _load_equity_csv() -> pd.DataFrame:
    """에쿼티 CSV를 로드한다."""
    df = pd.read_csv(BUFFER_ZONE_EQUITY_PATH)
    df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
    return df


@st.cache_data
def _load_trades_csv() -> pd.DataFrame:
    """거래 내역 CSV를 로드한다."""
    df = pd.read_csv(BUFFER_ZONE_TRADES_PATH)
    if not df.empty:
        df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.date
        df["exit_date"] = pd.to_datetime(df["exit_date"]).dt.date
    return df


@st.cache_data
def _load_summary_json() -> dict[str, Any]:
    """요약 JSON을 로드한다."""
    with BUFFER_ZONE_SUMMARY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


# ============================================================
# 차트 데이터 변환 함수 (표시 변환만 수행)
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
                "size": 2,
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
                "size": 2,
            }
        )

    return markers


def _build_equity_data(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """에쿼티 곡선 데이터를 Area 시리즈용으로 변환한다."""
    equity_data: list[dict[str, object]] = []
    for _, row in equity_df.iterrows():
        d: date = row[COL_DATE]
        equity_data.append({"time": d.strftime("%Y-%m-%d"), "value": float(row["equity"])})
    return equity_data


def _build_drawdown_data(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """CSV의 drawdown_pct 컬럼에서 Area 시리즈 데이터를 생성한다."""
    dd_data: list[dict[str, object]] = []
    for _, row in equity_df.iterrows():
        d: date = row[COL_DATE]
        dd_data.append({"time": d.strftime("%Y-%m-%d"), "value": float(row["drawdown_pct"])})
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
    """메인 차트를 렌더링한다 (캔들+MA+밴드+마커+에쿼티+드로우다운)."""
    # 1. 데이터 준비
    candle_data = _build_candle_data(signal_df)
    ma_data = _build_ma_data(signal_df, ma_col)
    upper_band_data = _build_band_data(equity_df, "upper_band")
    lower_band_data = _build_band_data(equity_df, "lower_band")
    markers = _build_markers(trades_df)
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
                    "lineWidth": 2,
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
                    "lineWidth": 2,
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
                },
            }
        ],
        "height": DEFAULT_DRAWDOWN_PANE_HEIGHT,
        "title": "드로우다운 (%)",
    }

    # 6. 렌더링
    total_height = DEFAULT_CANDLE_PANE_HEIGHT + DEFAULT_EQUITY_PANE_HEIGHT + DEFAULT_DRAWDOWN_PANE_HEIGHT
    lightweight_charts_v5_component(
        name="backtest_main_chart",
        charts=[pane1, pane2, pane3],
        height=total_height,
        zoom_level=DEFAULT_ZOOM_LEVEL,
        key="main_chart",
    )


def _render_monthly_heatmap(monthly_returns: list[dict[str, Any]]) -> None:
    """월별/연도별 수익률 히트맵을 Plotly로 렌더링한다."""
    if not monthly_returns:
        st.info("월별 수익률 히트맵을 표시하기에 데이터가 부족합니다.")
        return

    # 1. JSON 데이터를 DataFrame으로 변환 후 피벗
    returns_df = pd.DataFrame(monthly_returns)
    pivot = returns_df.pivot_table(values="return_pct", index="year", columns="month")

    # 2. 피벗 테이블을 Plotly 히트맵으로 변환
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

    # 3. 최대 절대값으로 대칭 색상 스케일 설정
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
        st.info("거래 내역이 없어 보유 기간 히스토그램을 표시할 수 없습니다.")
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

        # ---- 결과 파일 존재 확인 ----
        required_files = [
            BUFFER_ZONE_SIGNAL_PATH,
            BUFFER_ZONE_EQUITY_PATH,
            BUFFER_ZONE_TRADES_PATH,
            BUFFER_ZONE_SUMMARY_PATH,
        ]
        missing_files = [p for p in required_files if not p.exists()]
        if missing_files:
            st.warning(
                "결과 파일이 없습니다. 먼저 백테스트를 실행해주세요:\n\n"
                "```\npoetry run python scripts/backtest/run_single_backtest.py\n```\n\n"
                f"누락 파일: {', '.join(str(p) for p in missing_files)}"
            )
            st.stop()
            return

        # ---- 데이터 로딩 ----
        signal_df = _load_signal_csv()
        equity_df = _load_equity_csv()
        trades_df = _load_trades_csv()
        summary_data = _load_summary_json()

        summary = summary_data["summary"]
        params = summary_data["params"]
        monthly_returns: list[dict[str, Any]] = summary_data.get("monthly_returns", [])

        # MA 컬럼명 결정
        ma_window = params["ma_window"]
        ma_col = f"ma_{ma_window}"
        ma_type = params.get("ma_type", "ema")

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
            total_trades = int(summary["total_trades"])
            win_rate = float(summary["win_rate"])
            st.metric("거래수 / 승률", f"{total_trades}회 / {win_rate:.1f}%")

        st.divider()

        # ---- Section 2: 메인 차트 ----
        st.header("1. QQQ 시그널 차트 + 전략 오버레이")
        buffer_zone_pct = params["buffer_zone_pct"]
        st.markdown(
            f"캔들스틱: QQQ OHLC | 이동평균: {ma_type.upper()} {ma_window}일 | "
            f"밴드: 버퍼존 {buffer_zone_pct:.0%} | 마커: Buy/Sell 체결 시점"
        )
        _render_main_chart(signal_df, equity_df, trades_df, ma_col)

        st.divider()

        # ---- Section 3: 월별 수익률 히트맵 ----
        st.header("2. 월별/연도별 수익률 히트맵")
        st.markdown("에쿼티 기준 월간 수익률을 연도별로 비교합니다.")
        _render_monthly_heatmap(monthly_returns)

        st.divider()

        # ---- Section 4: 포지션 보유 기간 분포 ----
        st.header("3. 포지션 보유 기간 분포")
        st.markdown("각 거래의 진입~청산 기간(일) 분포를 보여줍니다.")
        _render_holding_period_histogram(trades_df)

        st.divider()

        # ---- Section 5: 전체 거래 상세 내역 ----
        st.header("4. 전체 거래 상세 내역")
        if not trades_df.empty:
            display_df = trades_df.copy()
            # 손익률을 %로 변환
            display_df["pnl_pct"] = display_df["pnl_pct"] * 100
            display_df = display_df.rename(columns=TRADE_COLUMN_RENAME)
            st.dataframe(display_df, width="stretch")  # type: ignore[call-overload]
            st.caption(f"총 {len(trades_df)}건의 거래")
        else:
            st.info("거래 내역이 없습니다.")

        st.divider()

        # ---- Section 6: 사용 파라미터 ----
        st.header("5. 사용 파라미터")
        param_source = params.get("param_source", {})
        st.json(
            {
                "이동평균 유형": ma_type.upper(),
                "이동평균 기간": f"{ma_window} ({param_source.get('ma_window', '')})",
                "버퍼존 비율": f"{buffer_zone_pct:.2%} ({param_source.get('buffer_zone_pct', '')})",
                "유지일 (hold_days)": f"{params['hold_days']} ({param_source.get('hold_days', '')})",
                "조정기간 (월)": f"{params['recent_months']} ({param_source.get('recent_months', '')})",
                "초기 자본": f"{params['initial_capital']:,.0f}원",
                "데이터": summary_data.get("data_info", {}),
            }
        )

        # ---- 푸터 ----
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - 백테스트 전략 대시보드")

    except Exception as e:
        st.error("애플리케이션 실행 중 오류가 발생했습니다:")
        st.exception(e)
        return


if __name__ == "__main__":
    main()
