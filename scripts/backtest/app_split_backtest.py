"""분할 매수매도 백테스트 시각화 대시보드

3개 트랜치(ma250/ma200/ma150)의 독립 매매와 합산 결과를 시각화한다.
캔들스틱 + MA + 밴드 + 매매 마커로 매매 근거를 시각적으로 확인하고,
포지션 변화(보유수량, 평균단가)를 실시간으로 추적한다.

선행 스크립트:
    poetry run python scripts/backtest/run_split_backtest.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_split_backtest.py
"""

import json
from datetime import date
from pathlib import Path
from typing import Any, TypedDict, cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component  # type: ignore[import-untyped]

from qbt.backtest.constants import SPLIT_TRANCHE_IDS
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
DEFAULT_EQUITY_PANE_HEIGHT = 250
DEFAULT_POSITION_PANE_HEIGHT = 150
DEFAULT_DRAWDOWN_PANE_HEIGHT = 150

# --- 캔들스틱 기본 색상 ---
COLOR_UP = "rgb(38, 166, 154)"
COLOR_DOWN = "rgb(239, 83, 80)"
COLOR_BUY_MARKER = "#26a69a"
COLOR_SELL_MARKER = "#ef5350"

# --- 에쿼티/드로우다운 색상 ---
COLOR_EQUITY_LINE = "rgba(33, 150, 243, 1)"
COLOR_EQUITY_TOP = "rgba(33, 150, 243, 0.3)"
COLOR_EQUITY_BOTTOM = "rgba(33, 150, 243, 0.05)"
COLOR_DRAWDOWN_LINE = "rgba(244, 67, 54, 1)"
COLOR_DRAWDOWN_TOP = "rgba(244, 67, 54, 0.3)"
COLOR_DRAWDOWN_BOTTOM = "rgba(244, 67, 54, 0.05)"

# --- 트랜치별 색상 체계 ---
TRANCHE_COLORS: dict[str, dict[str, str]] = {
    "ma250": {
        "ma": "rgba(66, 133, 244, 0.9)",  # 파랑
        "upper": "rgba(66, 133, 244, 0.5)",
        "lower": "rgba(66, 133, 244, 0.5)",
        "equity": "rgba(66, 133, 244, 0.8)",
        "marker_buy": "#4285f4",
        "marker_sell": "#1a73e8",
        "bg": "rgba(66, 133, 244, 0.12)",
    },
    "ma200": {
        "ma": "rgba(255, 152, 0, 0.9)",  # 주황
        "upper": "rgba(255, 152, 0, 0.5)",
        "lower": "rgba(255, 152, 0, 0.5)",
        "equity": "rgba(255, 152, 0, 0.8)",
        "marker_buy": "#ff9800",
        "marker_sell": "#e68a00",
        "bg": "rgba(255, 152, 0, 0.12)",
    },
    "ma150": {
        "ma": "rgba(76, 175, 80, 0.9)",  # 초록
        "upper": "rgba(76, 175, 80, 0.5)",
        "lower": "rgba(76, 175, 80, 0.5)",
        "equity": "rgba(76, 175, 80, 0.8)",
        "marker_buy": "#4caf50",
        "marker_sell": "#388e3c",
        "bg": "rgba(76, 175, 80, 0.12)",
    },
}

# --- 트랜치 한글 레이블 ---
TRANCHE_DISPLAY: dict[str, str] = {
    "ma250": "MA 250 (장기)",
    "ma200": "MA 200 (기준)",
    "ma150": "MA 150 (중기)",
}

# --- 거래 내역 한글 컬럼 매핑 ---
TRADE_COLUMN_RENAME: dict[str, str] = {
    "tranche_id": "트랜치",
    "ma_window": "MA",
    "entry_date": "진입일",
    "exit_date": "청산일",
    "entry_price": "진입가",
    "exit_price": "청산가",
    "shares": "수량",
    "pnl": "손익금액",
    "pnl_pct": "손익률",
    "holding_days": "보유기간(일)",
    "tranche_seq": "순번",
}

# --- 초기 줌 ---
DEFAULT_ZOOM_LEVEL = 99999


# ============================================================
# 전략 데이터 타입
# ============================================================


class SplitStrategyData(TypedDict):
    """분할 전략 데이터 컨테이너."""

    strategy_name: str
    display_name: str
    result_dir: Path
    summary_data: dict[str, Any]
    signal_df: pd.DataFrame
    equity_df: pd.DataFrame
    trades_df: pd.DataFrame


# ============================================================
# 데이터 로딩
# ============================================================


@st.cache_data
def _load_csv(path_str: str) -> pd.DataFrame:
    """CSV를 로드하고 날짜 컬럼을 파싱한다."""
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
        return cast(dict[str, Any], json.load(f))


def _discover_split_strategies() -> list[SplitStrategyData]:
    """BACKTEST_RESULTS_DIR에서 분할 전략 결과를 자동 탐색한다.

    split_ 접두사 디렉토리를 탐색하고, summary.json에 split_summary 키가 있으면
    분할 전략으로 판별한다.
    """
    if not BACKTEST_RESULTS_DIR.exists():
        return []

    strategies: list[SplitStrategyData] = []

    for subdir in sorted(BACKTEST_RESULTS_DIR.iterdir()):
        if not subdir.is_dir() or not subdir.name.startswith("split_"):
            continue

        summary_path = subdir / "summary.json"
        signal_path = subdir / "signal.csv"
        equity_path = subdir / "equity.csv"
        trades_path = subdir / "trades.csv"

        # 필수 파일 존재 확인
        if not all(p.exists() for p in [summary_path, signal_path, equity_path]):
            continue

        summary_data = _load_json(str(summary_path))

        # 분할 전략 판별: split_summary 키 존재
        if "split_summary" not in summary_data:
            continue

        signal_df = _load_csv(str(signal_path))
        equity_df = _load_csv(str(equity_path))

        if trades_path.exists():
            trades_df = _load_csv(str(trades_path))
            if not trades_df.empty and "entry_date" in trades_df.columns:
                trades_df["entry_date"] = pd.to_datetime(trades_df["entry_date"]).dt.date
            if not trades_df.empty and "exit_date" in trades_df.columns:
                trades_df["exit_date"] = pd.to_datetime(trades_df["exit_date"]).dt.date
        else:
            trades_df = pd.DataFrame()

        display_name = summary_data.get("display_name", subdir.name)

        strategies.append(
            SplitStrategyData(
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
# 공통 차트 테마
# ============================================================

_CHART_THEME: dict[str, Any] = {
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


# ============================================================
# 캔들스틱 차트 데이터 구축
# ============================================================


def _build_candle_data(
    signal_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    focus_tranche: str | None,
) -> list[dict[str, object]]:
    """signal_df를 lightweight-charts 캔들스틱 데이터로 변환한다.

    customValues에 OHLC 가격, 전일대비%, MA, 밴드, 에쿼티, 드로우다운을 포함한다.
    """
    prev_close = signal_df[COL_CLOSE].shift(1)

    # 포커스 트랜치 또는 전체 MA 컬럼 목록
    if focus_tranche:
        ma_cols = [f"ma_{focus_tranche.replace('ma', '')}"]
    else:
        ma_cols = [f"ma_{tid.replace('ma', '')}" for tid in SPLIT_TRANCHE_IDS]
    ma_cols = [c for c in ma_cols if c in signal_df.columns]

    # 에쿼티/드로우다운 매핑 (날짜 → 값)
    has_equity = "equity" in equity_df.columns
    has_drawdown = "drawdown_pct" in equity_df.columns
    equity_map: dict[date, dict[str, float]] = {}
    for row in equity_df.itertuples(index=False):
        d: date = getattr(row, COL_DATE)
        entry: dict[str, float] = {}
        if has_equity and pd.notna(row.equity):
            entry["equity"] = float(cast(float, row.equity))
        if has_drawdown and pd.notna(row.drawdown_pct):
            entry["dd"] = float(cast(float, row.drawdown_pct))
        if entry:
            equity_map[d] = entry

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

        cv: dict[str, str] = {
            "open": f"{open_val:.2f}",
            "high": f"{high_val:.2f}",
            "low": f"{low_val:.2f}",
            "close": f"{close_val:.2f}",
        }

        # 전일종가대비%
        pc = prev_close.iloc[i]
        if pd.notna(pc) and pc != 0:
            pc_float = float(pc)
            cv["close_pct"] = f"{(close_val / pc_float - 1) * 100:+.2f}"

        # MA
        for mc in ma_cols:
            val = getattr(row, mc, None)
            if val is not None and pd.notna(val):
                cv[mc] = f"{val:.2f}"

        # 밴드 (포커스 시에만)
        if focus_tranche:
            mw = focus_tranche.replace("ma", "")
            for band_type in ["upper_band", "lower_band"]:
                band_col = f"{band_type}_{mw}"
                if hasattr(row, band_col):
                    bval = getattr(row, band_col)
                    if pd.notna(bval):
                        cv[band_col] = f"{bval:.2f}"

        # 에쿼티 + 드로우다운 (tooltip용)
        if d in equity_map:
            eq_data = equity_map[d]
            if "equity" in eq_data:
                cv["equity"] = f"{int(eq_data['equity']):,}"
            if "dd" in eq_data:
                cv["dd"] = f"{eq_data['dd']:.2f}"

        candle_entry["customValues"] = cv
        candle_data.append(candle_entry)

    return candle_data


def _build_series_data(df: pd.DataFrame, col: str) -> list[dict[str, object]]:
    """DataFrame의 특정 컬럼에서 Line 시리즈 데이터를 생성한다."""
    data: list[dict[str, object]] = []
    for row in df.itertuples(index=False):
        val = getattr(row, col, None)
        if val is not None and pd.notna(val):
            d: date = getattr(row, COL_DATE)
            data.append({"time": d.strftime("%Y-%m-%d"), "value": float(val)})
    return data


def _build_markers(
    trades_df: pd.DataFrame,
    focus_tranche: str | None,
    summary_data: dict[str, Any],
) -> list[dict[str, object]]:
    """trades_df에서 Buy/Sell 마커를 생성한다.

    트랜치별 색상 구분 + 트랜치 ID를 마커 텍스트에 포함한다.
    """
    markers: list[dict[str, object]] = []
    if trades_df.empty:
        return markers

    for trade in trades_df.itertuples(index=False):
        tid = str(trade.tranche_id)

        # 포커스 모드: 해당 트랜치 마커만 표시
        if focus_tranche and tid != focus_tranche:
            continue

        colors = TRANCHE_COLORS.get(tid, TRANCHE_COLORS["ma200"])

        entry_d = cast(date, trade.entry_date)
        markers.append(
            {
                "time": entry_d.strftime("%Y-%m-%d"),
                "position": "belowBar",
                "color": colors["marker_buy"],
                "shape": "arrowUp",
                "text": f"{tid}-Buy ${trade.entry_price:.1f}",
                "size": 2,
            }
        )
        exit_d = cast(date, trade.exit_date)
        pnl_pct = cast(float, trade.pnl_pct) * 100
        markers.append(
            {
                "time": exit_d.strftime("%Y-%m-%d"),
                "position": "aboveBar",
                "color": colors["marker_sell"],
                "shape": "arrowDown",
                "text": f"{tid}-Sell {pnl_pct:+.1f}%",
                "size": 2,
            }
        )

    # 미청산 포지션 마커
    tranches_info = summary_data.get("tranches", [])
    for t_info in tranches_info:
        tid = t_info.get("tranche_id", "")
        if focus_tranche and tid != focus_tranche:
            continue
        open_pos = t_info.get("open_position")
        if open_pos:
            colors = TRANCHE_COLORS.get(tid, TRANCHE_COLORS["ma200"])
            markers.append(
                {
                    "time": open_pos["entry_date"],
                    "position": "belowBar",
                    "color": colors["marker_buy"],
                    "shape": "arrowUp",
                    "text": f"{tid}-Buy ${open_pos['entry_price']:.1f} (보유중)",
                    "size": 2,
                }
            )

    # lightweight-charts는 마커가 시간순 정렬되어야 정상 표시됨
    markers.sort(key=lambda m: str(m["time"]))

    return markers


# ============================================================
# Section 1: 요약 지표
# ============================================================


def _render_summary(strategy: SplitStrategyData) -> None:
    """합산 레벨 요약 지표 + 트랜치별 비교 테이블을 렌더링한다."""
    summary = strategy["summary_data"]["split_summary"]

    st.header("1. 요약 지표")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("총 수익률", f"{summary['total_return_pct']:.2f}%")
    with col2:
        st.metric("CAGR", f"{summary['cagr']:.2f}%")
    with col3:
        st.metric("MDD", f"{summary['mdd']:.2f}%")
    with col4:
        st.metric("Calmar", f"{summary['calmar']:.2f}")
    with col5:
        st.metric("총 거래수", f"{summary['total_trades']}회")

    # 트랜치별 비교 테이블
    st.subheader("트랜치별 성과 비교")
    tranches = strategy["summary_data"].get("tranches", [])
    if tranches:
        rows: list[dict[str, Any]] = []
        for t in tranches:
            s = t["summary"]
            rows.append(
                {
                    "트랜치": TRANCHE_DISPLAY.get(t["tranche_id"], t["tranche_id"]),
                    "MA": t["ma_window"],
                    "가중치": f"{t['weight']:.0%}",
                    "수익률(%)": s["total_return_pct"],
                    "CAGR(%)": s["cagr"],
                    "MDD(%)": s["mdd"],
                    "Calmar": s["calmar"],
                    "거래수": s["total_trades"],
                    "승률(%)": s["win_rate"],
                    "상태": "보유중" if "open_position" in t else "청산",
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ============================================================
# Section 2: 메인 캔들스틱 차트
# ============================================================


def _render_candlestick_chart(
    strategy: SplitStrategyData,
    chart_key: str,
) -> None:
    """캔들스틱 차트를 렌더링한다 (MA + 밴드 + 매매 마커)."""
    signal_df = strategy["signal_df"]
    trades_df = strategy["trades_df"]

    st.header("2. 캔들스틱 차트 (매매 근거 확인)")

    # 포커스 트랜치 선택
    focus_options = ["전체 보기 (MA 라인만)"] + [f"{TRANCHE_DISPLAY[tid]} 포커스" for tid in SPLIT_TRANCHE_IDS]
    focus_choice = st.selectbox(
        "트랜치 포커스",
        focus_options,
        key=f"focus_{chart_key}",
        help="전체 보기: 3개 MA 라인만 표시 | 포커스: 선택한 트랜치의 MA + 상단/하단 밴드 + 해당 마커만 표시",
    )

    # 포커스 결정
    focus_tranche: str | None = None
    if focus_choice != focus_options[0]:
        for tid in SPLIT_TRANCHE_IDS:
            if TRANCHE_DISPLAY[tid] in focus_choice:
                focus_tranche = tid
                break

    equity_df = strategy["equity_df"]

    # 1. 캔들 데이터 (에쿼티/드로우다운 tooltip 포함)
    candle_data = _build_candle_data(signal_df, equity_df, focus_tranche)

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

    # 마커
    markers = _build_markers(trades_df, focus_tranche, strategy["summary_data"])
    if markers:
        candle_series["markers"] = markers

    pane1_series: list[dict[str, object]] = [candle_series]

    # 2. MA 라인
    if focus_tranche:
        # 포커스: 해당 MA + 밴드
        mw = focus_tranche.replace("ma", "")
        ma_col = f"ma_{mw}"
        colors = TRANCHE_COLORS[focus_tranche]

        if ma_col in signal_df.columns:
            ma_data = _build_series_data(signal_df, ma_col)
            if ma_data:
                pane1_series.append(
                    {
                        "type": "Line",
                        "data": ma_data,
                        "options": {
                            "color": colors["ma"],
                            "lineWidth": 2,
                            "priceLineVisible": False,
                            "lastValueVisible": False,
                            "crosshairMarkerVisible": False,
                        },
                    }
                )

        # 밴드
        for band_type, band_color_key in [("upper_band", "upper"), ("lower_band", "lower")]:
            band_col = f"{band_type}_{mw}"
            if band_col in signal_df.columns:
                band_data = _build_series_data(signal_df, band_col)
                if band_data:
                    pane1_series.append(
                        {
                            "type": "Line",
                            "data": band_data,
                            "options": {
                                "color": colors[band_color_key],
                                "lineWidth": 2,
                                "lineStyle": 2,
                                "priceLineVisible": False,
                                "lastValueVisible": False,
                                "crosshairMarkerVisible": False,
                            },
                        }
                    )
    else:
        # 전체 보기: 3개 MA 라인만
        for tid in SPLIT_TRANCHE_IDS:
            mw = tid.replace("ma", "")
            ma_col = f"ma_{mw}"
            if ma_col in signal_df.columns:
                ma_data = _build_series_data(signal_df, ma_col)
                if ma_data:
                    colors = TRANCHE_COLORS[tid]
                    pane1_series.append(
                        {
                            "type": "Line",
                            "data": ma_data,
                            "options": {
                                "color": colors["ma"],
                                "lineWidth": 2,
                                "priceLineVisible": False,
                                "lastValueVisible": False,
                                "crosshairMarkerVisible": False,
                            },
                        }
                    )

    pane1 = {
        "chart": _CHART_THEME,
        "series": pane1_series,
        "height": DEFAULT_CANDLE_PANE_HEIGHT,
        "title": f"{strategy['display_name']} — {'전체' if not focus_tranche else TRANCHE_DISPLAY.get(focus_tranche, focus_tranche)}",
    }

    # Pane 2: 에쿼티 곡선
    equity_data = _build_series_data(equity_df, "equity")
    equity_pane_series: list[dict[str, object]] = [
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
    ]

    # 트랜치별 에쿼티 오버레이
    for tid in SPLIT_TRANCHE_IDS:
        eq_col = f"{tid}_equity"
        if eq_col in equity_df.columns:
            t_data = _build_series_data(equity_df, eq_col)
            if t_data:
                t_colors = TRANCHE_COLORS[tid]
                equity_pane_series.append(
                    {
                        "type": "Line",
                        "data": t_data,
                        "options": {
                            "color": t_colors["equity"],
                            "lineWidth": 1,
                            "priceLineVisible": False,
                            "lastValueVisible": False,
                            "crosshairMarkerVisible": False,
                            "priceFormat": {"type": "price", "precision": 0, "minMove": 1},
                        },
                    }
                )

    pane2 = {
        "chart": _CHART_THEME,
        "series": equity_pane_series,
        "height": DEFAULT_EQUITY_PANE_HEIGHT,
        "title": "에쿼티 (원) — 트랜치별 오버레이",
    }

    # Pane 3: 드로우다운
    dd_data = _build_series_data(equity_df, "drawdown_pct")
    pane3 = {
        "chart": _CHART_THEME,
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

    total_height = DEFAULT_CANDLE_PANE_HEIGHT + DEFAULT_EQUITY_PANE_HEIGHT + DEFAULT_DRAWDOWN_PANE_HEIGHT
    lightweight_charts_v5_component(
        name=f"candle_{chart_key}",
        charts=[pane1, pane2, pane3],
        height=total_height,
        zoom_level=DEFAULT_ZOOM_LEVEL,
        scroll_padding=60,
        key=f"candle_chart_{chart_key}",
    )


# ============================================================
# Section 3: 포지션 추적 차트
# ============================================================


def _render_position_tracking(
    strategy: SplitStrategyData,
    chart_key: str,
) -> None:
    """포지션 추적 차트를 렌더링한다 (active_tranches + avg_entry_price + 트랜치별 보유수량)."""
    equity_df = strategy["equity_df"]
    signal_df = strategy["signal_df"]

    st.header("3. 포지션 추적 (보유 상태 변화)")

    # 3-1. 평균단가 vs 종가
    if "avg_entry_price" in equity_df.columns:
        st.subheader("3-1. 가중 평균 진입가 vs 종가")

        # 날짜 기준으로 signal_df의 Close와 equity_df의 avg_entry_price를 결합
        merged = pd.merge(
            signal_df[[COL_DATE, COL_CLOSE]],
            equity_df[[COL_DATE, "avg_entry_price"]],
            on=COL_DATE,
            how="inner",
        )

        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=[d.strftime("%Y-%m-%d") for d in merged[COL_DATE]],
                y=merged[COL_CLOSE],
                mode="lines",
                name="종가",
                line={"color": "rgba(255, 255, 255, 0.6)", "width": 1},
            )
        )

        # avg_entry_price (None 포함 — 미보유 구간은 끊어서 표시)
        fig.add_trace(
            go.Scatter(
                x=[d.strftime("%Y-%m-%d") for d in merged[COL_DATE]],
                y=merged["avg_entry_price"],
                mode="lines",
                name="가중 평균 진입가",
                line={"color": "#ffc107", "width": 2, "shape": "hv"},
                connectgaps=False,
            )
        )

        fig.update_layout(
            height=300,
            margin={"l": 60, "r": 40, "t": 30, "b": 60},
            paper_bgcolor="#0e1117",
            plot_bgcolor="#131722",
            font={"color": "#D1D4DC"},
            xaxis={"gridcolor": "#1e222d"},
            yaxis={"gridcolor": "#1e222d", "title": "가격"},
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
        )
        st.plotly_chart(fig, width="stretch", key=f"avg_price_{chart_key}")

    # 4-2. 보유 트랜치 수
    if "active_tranches" in equity_df.columns:
        st.subheader("3-2. 동시 보유 트랜치 수")

        fig_at = go.Figure()
        fig_at.add_trace(
            go.Bar(
                x=[d.strftime("%Y-%m-%d") for d in equity_df[COL_DATE]],
                y=equity_df["active_tranches"],
                marker_color="rgba(33, 150, 243, 0.6)",
                hovertemplate="날짜: %{x}<br>보유 트랜치: %{y}<extra></extra>",
            )
        )
        fig_at.update_layout(
            height=200,
            margin={"l": 60, "r": 40, "t": 30, "b": 60},
            paper_bgcolor="#0e1117",
            plot_bgcolor="#131722",
            font={"color": "#D1D4DC"},
            xaxis={"gridcolor": "#1e222d"},
            yaxis={"gridcolor": "#1e222d", "title": "트랜치 수", "dtick": 1, "range": [-0.5, 3.5]},
            bargap=0,
        )
        st.plotly_chart(fig_at, width="stretch", key=f"active_tranches_{chart_key}")

    # 4-3. 트랜치별 보유수량
    st.subheader("3-3. 트랜치별 보유수량 변화")
    fig_pos = go.Figure()

    for tid in SPLIT_TRANCHE_IDS:
        pos_col = f"{tid}_position"
        if pos_col in equity_df.columns:
            colors = TRANCHE_COLORS[tid]
            fig_pos.add_trace(
                go.Scatter(
                    x=[d.strftime("%Y-%m-%d") for d in equity_df[COL_DATE]],
                    y=equity_df[pos_col],
                    mode="lines",
                    name=TRANCHE_DISPLAY.get(tid, tid),
                    line={"color": colors["equity"], "width": 1.5},
                    fill="tozeroy",
                    fillcolor=colors["bg"],
                )
            )

    fig_pos.update_layout(
        height=250,
        margin={"l": 60, "r": 40, "t": 30, "b": 60},
        paper_bgcolor="#0e1117",
        plot_bgcolor="#131722",
        font={"color": "#D1D4DC"},
        xaxis={"gridcolor": "#1e222d"},
        yaxis={"gridcolor": "#1e222d", "title": "보유 주수"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02},
    )
    st.plotly_chart(fig_pos, width="stretch", key=f"position_{chart_key}")


# ============================================================
# Section 4: 거래 상세 테이블
# ============================================================


def _style_trade_rows(row: pd.Series) -> list[str]:
    """트랜치별 배경색 + 손익 기반 색상을 반환한다."""
    tid_col = TRADE_COLUMN_RENAME.get("tranche_id", "트랜치")
    pnl_col = TRADE_COLUMN_RENAME.get("pnl_pct", "손익률")

    tid = str(row.get(tid_col, ""))
    pnl = row.get(pnl_col, 0)

    # 손익 우선
    if isinstance(pnl, int | float) and pnl > 0:
        return ["background-color: rgba(38, 166, 154, 0.15)"] * len(row)
    elif isinstance(pnl, int | float) and pnl < 0:
        return ["background-color: rgba(239, 83, 80, 0.15)"] * len(row)

    # 트랜치 배경색
    for t_id, colors in TRANCHE_COLORS.items():
        if t_id in tid or TRANCHE_DISPLAY.get(t_id, "") == tid:
            return [f"background-color: {colors['bg']}"] * len(row)

    return [""] * len(row)


def _render_trades_table(
    strategy: SplitStrategyData,
    chart_key: str,
) -> None:
    """거래 상세 테이블을 렌더링한다."""
    trades_df = strategy["trades_df"]

    st.header("4. 거래 상세 내역")

    if trades_df.empty:
        st.info("거래 내역이 없습니다.")
        return

    display_df = trades_df.copy()

    # 손익률을 % 단위로 변환
    if "pnl_pct" in display_df.columns:
        display_df["pnl_pct"] = display_df["pnl_pct"] * 100

    # 표시할 컬럼 선택 및 순서
    display_cols = [
        c
        for c in [
            "tranche_id",
            "ma_window",
            "tranche_seq",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "shares",
            "pnl",
            "pnl_pct",
            "holding_days",
        ]
        if c in display_df.columns
    ]
    display_df = display_df[display_cols]

    # 한글 컬럼명
    display_df = display_df.rename(columns=TRADE_COLUMN_RENAME)

    styled_df = display_df.style.apply(_style_trade_rows, axis=1)
    st.dataframe(styled_df, width="stretch", hide_index=True)  # type: ignore[call-overload]
    st.caption(f"총 {len(trades_df)}건의 거래")


# ============================================================
# Section 5: 사용 파라미터
# ============================================================


def _render_params(strategy: SplitStrategyData) -> None:
    """사용 파라미터를 JSON으로 표시한다."""
    st.header("5. 사용 파라미터")
    split_config = strategy["summary_data"].get("split_config", {})
    st.json(split_config)


# ============================================================
# 전략 탭 렌더링
# ============================================================


def _render_strategy_tab(strategy: SplitStrategyData) -> None:
    """하나의 분할 전략 탭 내부를 렌더링한다."""
    chart_key = strategy["strategy_name"]

    _render_summary(strategy)
    st.divider()

    _render_candlestick_chart(strategy, chart_key)
    st.divider()

    _render_position_tracking(strategy, chart_key)
    st.divider()

    _render_trades_table(strategy, chart_key)
    st.divider()

    _render_params(strategy)


# ============================================================
# 메인 앱
# ============================================================


def main() -> None:
    """Streamlit 앱 메인 함수."""
    try:
        st.set_page_config(
            page_title="분할 매수매도 대시보드",
            page_icon=":bar_chart:",
            layout="wide",
        )

        st.title("분할 매수매도 대시보드")
        st.markdown("3개 트랜치(MA 250/200/150)의 독립 매매와 합산 결과를 시각화합니다. " "캔들스틱 차트에서 매매 근거를 확인하고, 포지션 변화를 추적합니다.")

        strategies = _discover_split_strategies()

        if not strategies:
            st.warning(
                "분할 매수매도 결과 파일이 없습니다. 먼저 백테스트를 실행해주세요:\n\n"
                "```\n"
                "poetry run python scripts/backtest/run_split_backtest.py\n"
                "```"
            )
            st.stop()
            return

        # 동적 탭 생성
        tab_labels = [s["display_name"] for s in strategies]
        tabs = st.tabs(tab_labels)

        for tab, strategy in zip(tabs, strategies, strict=True):
            with tab:
                _render_strategy_tab(strategy)

        # 푸터
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - 분할 매수매도 대시보드")

    except Exception as e:
        st.error("애플리케이션 실행 중 오류가 발생했습니다:")
        st.exception(e)
        return


if __name__ == "__main__":
    main()
