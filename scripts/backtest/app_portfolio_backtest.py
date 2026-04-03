"""포트폴리오 비교 대시보드

포트폴리오 실험 결과를 비교한다.
전체 비교 탭에서 에쿼티 곡선·드로우다운·성과 지표를 나란히 보고,
실험별 탭에서 자산 비중 추이·거래 현황·시그널 차트를 상세 확인한다.

선행 스크립트:
    poetry run python scripts/backtest/run_portfolio_backtest.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_portfolio_backtest.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component  # type: ignore[import-untyped]
from plotly.subplots import make_subplots

from qbt.backtest.constants import DEFAULT_PORTFOLIO_EXPERIMENTS
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    PORTFOLIO_RESULTS_DIR,
)

# ============================================================
# 로컬 상수 (이 파일에서만 사용)
# ============================================================

# --- 차트 높이 ---
_CHART_HEIGHT = 500
_SUB_CHART_HEIGHT = 300
_SMALL_CHART_HEIGHT = 250
_SIGNAL_CHART_HEIGHT = 500

# --- 시그널 차트 색상 ---
_COLOR_UP = "rgb(38, 166, 154)"
_COLOR_DOWN = "rgb(239, 83, 80)"
_COLOR_MA_LINE = "rgba(255, 152, 0, 0.9)"
_COLOR_UPPER_BAND = "rgba(33, 150, 243, 0.6)"
_COLOR_LOWER_BAND = "rgba(244, 67, 54, 0.6)"
_COLOR_BUY_MARKER = "#26a69a"
_COLOR_SELL_MARKER = "#ef5350"

# --- 시그널 차트 줌 ---
_DEFAULT_ZOOM_LEVEL = 99999

# --- 성과 지표 테이블 컬럼 레이블 ---
_COL_DISPLAY_NAME = "실험"
_COL_CAGR = "CAGR (%)"
_COL_MDD = "MDD (%)"
_COL_CALMAR = "Calmar"
_COL_TOTAL_RETURN = "총 수익률 (%)"
_COL_TOTAL_TRADES = "총 거래 수"
_COL_START_DATE = "시작일"
_COL_END_DATE = "종료일"

# --- 거래 내역 한글 컬럼 매핑 ---
_TRADE_COLUMN_RENAME: dict[str, str] = {
    "asset_id": "자산",
    "trade_type": "거래유형",
    "entry_date": "진입일",
    "entry_price": "진입가",
    "exit_date": "청산일",
    "exit_price": "청산가",
    "pnl": "손익금액",
    "pnl_pct": "손익률",
    "holding_days": "보유기간(일)",
}

# --- 자산별 색상 ---
_ASSET_COLORS: dict[str, str] = {
    "qqq": "#1f77b4",  # 파랑
    "tqqq": "#ff7f0e",  # 주황
    "spy": "#2ca02c",  # 초록
    "gld": "#d62728",  # 빨강
    "tlt": "#9467bd",  # 보라 (채권)
    "iwm": "#8c564b",  # 갈색 (소형주)
    "efa": "#e377c2",  # 분홍 (선진국 국제)
    "eem": "#7f7f7f",  # 회색 (신흥국)
}
_ASSET_COLOR_FALLBACK = "#888888"  # 매핑 없는 자산

# --- 실험별 색상 (전체 비교 에쿼티 차트용) ---
_EXPERIMENT_COLORS: dict[str, str] = {
    # A 시리즈: QQQ / SPY / GLD (파랑 계열)
    "portfolio_a1": "#aec7e8",
    "portfolio_a2": "#1f77b4",
    "portfolio_a3": "#17becf",
    # B 시리즈: TQQQ 포함 (주황-빨강 계열)
    "portfolio_b1": "#ffbb78",
    "portfolio_b2": "#ff7f0e",
    "portfolio_b3": "#d62728",
    # C/D 시리즈: 단일 자산 비교군
    "portfolio_c1": "#9467bd",  # 보라 (QQQ + TQQQ)
    "portfolio_d1": "#2ca02c",  # 진한 초록 (QQQ 단일)
    "portfolio_d2": "#8c4f00",  # 진한 갈색 (TQQQ 단일)
    # E 시리즈: SPY / GLD / TLT (초록 계열, 연→진)
    "portfolio_e1": "#c7e9c0",
    "portfolio_e2": "#74c476",
    "portfolio_e3": "#238b45",
    "portfolio_e4": "#006d2c",
    "portfolio_e5": "#00441b",
    # F 시리즈: SPY / TQQQ / GLD / TLT (분홍-장미 계열)
    "portfolio_f1": "#e7b8d4",
    "portfolio_f2": "#d46b98",
    "portfolio_f3": "#b52b6e",
    "portfolio_f4": "#7a1446",
    "portfolio_f5": "#e066a0",
    "portfolio_f5h": "#f0a0c4",
    "portfolio_f6": "#c84080",
    "portfolio_f6h": "#e880b0",
    "portfolio_f7": "#a01060",
    "portfolio_f7h": "#d06090",
    # G 시리즈: SPY / GLD / TLT B&H 변형 (청록 계열)
    "portfolio_g1": "#c7fbf8",
    "portfolio_g2": "#66d4cf",
    "portfolio_g3": "#1aada8",
    "portfolio_g4": "#0e7470",
    # H 시리즈: TQQQ / GLD / TLT 공격적 (황금-갈색 계열)
    "portfolio_h1": "#e6c880",
    "portfolio_h2": "#c8912a",
    "portfolio_h3": "#8c5e00",
}
_EXPERIMENT_COLOR_FALLBACK = "#888888"


# ============================================================
# 데이터 구조
# ============================================================


@dataclass
class _ExperimentData:
    """로딩된 실험 결과 데이터."""

    experiment_name: str
    display_name: str
    equity_df: pd.DataFrame
    trades_df: pd.DataFrame
    summary: dict[str, Any]
    signal_dfs: dict[str, pd.DataFrame] = field(default_factory=dict)


# ============================================================
# 데이터 로딩
# ============================================================


def _discover_experiments() -> list[Path]:
    """PORTFOLIO_RESULTS_DIR 하위에서 활성 실험의 summary.json이 있는 폴더를 탐색한다.

    DEFAULT_PORTFOLIO_EXPERIMENTS에 포함된 실험만 반환한다.

    Returns:
        유효한 실험 결과 폴더 경로 리스트 (알파벳 순 정렬)
    """
    if not PORTFOLIO_RESULTS_DIR.exists():
        return []

    result: list[Path] = []
    for sub_dir in sorted(PORTFOLIO_RESULTS_DIR.iterdir()):
        if sub_dir.is_dir() and (sub_dir / "summary.json").exists() and sub_dir.name in DEFAULT_PORTFOLIO_EXPERIMENTS:
            result.append(sub_dir)

    return result


@st.cache_data
def _load_equity_csv(experiment_dir_str: str) -> pd.DataFrame:
    """equity.csv를 로드한다.

    Args:
        experiment_dir_str: 실험 디렉토리 경로 (문자열, 캐시 키용)

    Returns:
        equity DataFrame (Date 열 datetime 변환)
    """
    path = Path(experiment_dir_str) / "equity.csv"
    df = pd.read_csv(path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


@st.cache_data
def _load_trades_csv(experiment_dir_str: str) -> pd.DataFrame:
    """trades.csv를 로드한다.

    Args:
        experiment_dir_str: 실험 디렉토리 경로 (문자열, 캐시 키용)

    Returns:
        trades DataFrame (entry_date / exit_date datetime 변환)
    """
    path = Path(experiment_dir_str) / "trades.csv"
    df = pd.read_csv(path)
    for col in ("entry_date", "exit_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


@st.cache_data
def _load_summary_json(experiment_dir_str: str) -> dict[str, Any]:
    """summary.json을 로드한다.

    Args:
        experiment_dir_str: 실험 디렉토리 경로 (문자열, 캐시 키용)

    Returns:
        summary 딕셔너리
    """
    path = Path(experiment_dir_str) / "summary.json"
    with path.open(encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
    return result


@st.cache_data
def _load_signal_csv(signal_path_str: str) -> pd.DataFrame:
    """signal_{asset_id}.csv를 로드한다.

    Args:
        signal_path_str: signal CSV 파일 경로 (문자열, 캐시 키용)

    Returns:
        signal DataFrame (Date 열 datetime 변환)
    """
    df = pd.read_csv(signal_path_str)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


def _load_experiment_data(experiment_dir: Path) -> _ExperimentData:
    """한 실험의 모든 결과 데이터를 로드한다.

    Args:
        experiment_dir: 실험 결과 디렉토리 경로

    Returns:
        _ExperimentData 인스턴스
    """
    dir_str = str(experiment_dir)
    summary = _load_summary_json(dir_str)
    equity_df = _load_equity_csv(dir_str)
    trades_df = _load_trades_csv(dir_str)

    # signal_{asset_id}.csv 탐색 및 로드
    signal_dfs: dict[str, pd.DataFrame] = {}
    for signal_path in sorted(experiment_dir.glob("signal_*.csv")):
        # "signal_qqq.csv" → asset_id = "qqq"
        asset_id = signal_path.stem.removeprefix("signal_")
        signal_dfs[asset_id] = _load_signal_csv(str(signal_path))

    display_name: str = str(summary.get("display_name", experiment_dir.name))

    return _ExperimentData(
        experiment_name=experiment_dir.name,
        display_name=display_name,
        equity_df=equity_df,
        trades_df=trades_df,
        summary=summary,
        signal_dfs=signal_dfs,
    )


# ============================================================
# 헬퍼 함수
# ============================================================


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """hex 색상 코드를 rgba 문자열로 변환한다.

    Plotly는 8자리 hex(#RRGGBBAA)를 지원하지 않으므로 rgba() 형식으로 변환한다.

    Args:
        hex_color: 6자리 hex 색상 코드 (예: "#aec7e8")
        alpha: 투명도 (0.0 ~ 1.0)

    Returns:
        rgba 문자열 (예: "rgba(174, 199, 232, 0.1)")
    """
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _get_asset_color(asset_id: str) -> str:
    """자산 ID에 대한 색상을 반환한다."""
    return _ASSET_COLORS.get(asset_id, _ASSET_COLOR_FALLBACK)


def _get_experiment_color(experiment_name: str) -> str:
    """실험명에 대한 색상을 반환한다."""
    return _EXPERIMENT_COLORS.get(experiment_name, _EXPERIMENT_COLOR_FALLBACK)


def _extract_portfolio_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """summary.json에서 portfolio_summary 블록을 추출한다."""
    ps = summary.get("portfolio_summary", {})
    return ps if isinstance(ps, dict) else {}


def _extract_per_asset(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """summary.json에서 per_asset 리스트를 추출한다."""
    pa = summary.get("per_asset", [])
    return pa if isinstance(pa, list) else []


def _weight_columns(equity_df: pd.DataFrame) -> list[str]:
    """equity_df에서 {asset_id}_weight 컬럼명 리스트를 반환한다."""
    return [c for c in equity_df.columns if c.endswith("_weight")]


def _asset_id_from_weight_col(col: str) -> str:
    """'{asset_id}_weight' 컬럼명에서 asset_id를 추출한다."""
    return col.removesuffix("_weight")


# ============================================================
# 전체 비교 탭
# ============================================================


def _render_comparison_tab(experiments: list[_ExperimentData]) -> None:
    """전체 비교 탭 — 포트폴리오 실험의 성과 지표·에쿼티 곡선·드로우다운을 비교한다."""

    # ---- 성과 지표 비교 테이블 ----
    st.subheader("성과 지표 비교")

    rows: list[dict[str, Any]] = []
    for exp in experiments:
        ps = _extract_portfolio_summary(exp.summary)
        rows.append(
            {
                _COL_DISPLAY_NAME: exp.display_name,
                _COL_CAGR: ps.get("cagr", "N/A"),
                _COL_MDD: ps.get("mdd", "N/A"),
                _COL_CALMAR: ps.get("calmar", "N/A"),
                _COL_TOTAL_RETURN: ps.get("total_return_pct", "N/A"),
                _COL_TOTAL_TRADES: ps.get("total_trades", "N/A"),
                _COL_START_DATE: ps.get("start_date", "N/A"),
                _COL_END_DATE: ps.get("end_date", "N/A"),
            }
        )

    compare_df = pd.DataFrame(rows)
    st.dataframe(compare_df, hide_index=True, width="stretch")

    # ---- 실험 선택 ----
    st.subheader("에쿼티 곡선 비교")

    all_names = [exp.display_name for exp in experiments]
    selected = st.multiselect(
        "비교할 실험 선택",
        options=all_names,
        default=all_names,
        key="comparison_multiselect",
    )

    selected_exps = [e for e in experiments if e.display_name in selected]

    if not selected_exps:
        st.info("비교할 실험을 1개 이상 선택하세요.")
        return

    # ---- 에쿼티 곡선 비교 ----
    fig_equity = go.Figure()
    for exp in selected_exps:
        color = _get_experiment_color(exp.experiment_name)
        fig_equity.add_trace(
            go.Scatter(
                x=exp.equity_df["Date"],
                y=exp.equity_df["equity"],
                mode="lines",
                name=exp.display_name,
                line={"color": color, "width": 2},
                hovertemplate=("%{x|%Y-%m-%d}<br>" f"{exp.display_name}: %{{y:,.0f}}원<extra></extra>"),
            )
        )

    fig_equity.update_layout(
        title="에쿼티 곡선 비교",
        xaxis_title="날짜",
        yaxis_title="에쿼티 (원)",
        height=_CHART_HEIGHT,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hovermode="x unified",
    )
    st.plotly_chart(fig_equity, width="stretch")

    # ---- 드로우다운 비교 ----
    st.subheader("드로우다운 비교")

    fig_dd = go.Figure()
    for exp in selected_exps:
        color = _get_experiment_color(exp.experiment_name)
        fig_dd.add_trace(
            go.Scatter(
                x=exp.equity_df["Date"],
                y=exp.equity_df["drawdown_pct"],
                mode="lines",
                name=exp.display_name,
                line={"color": color, "width": 1.5},
                fill="tozeroy",
                fillcolor=color.replace(")", ", 0.1)").replace("rgb", "rgba")
                if color.startswith("rgb")
                else _hex_to_rgba(color, 0.1),
                hovertemplate=("%{x|%Y-%m-%d}<br>" f"{exp.display_name}: %{{y:.2f}}%<extra></extra>"),
            )
        )

    fig_dd.update_layout(
        title="드로우다운 비교",
        xaxis_title="날짜",
        yaxis_title="드로우다운 (%)",
        height=_SUB_CHART_HEIGHT,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hovermode="x unified",
    )
    st.plotly_chart(fig_dd, width="stretch")


# ============================================================
# 개별 실험 탭
# ============================================================


def _render_experiment_tab(exp: _ExperimentData) -> None:
    """개별 실험 탭 — 요약·에쿼티·비중 추이·거래·시그널을 상세 표시한다."""

    ps = _extract_portfolio_summary(exp.summary)
    per_asset = _extract_per_asset(exp.summary)

    # ---- 섹션 1: 요약 지표 ----
    st.subheader("요약 지표")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("CAGR", f"{ps.get('cagr', 'N/A')}%")
    col2.metric("MDD", f"{ps.get('mdd', 'N/A')}%")
    col3.metric("Calmar", str(ps.get("calmar", "N/A")))
    col4.metric("총 수익률", f"{ps.get('total_return_pct', 'N/A')}%")

    # 자산별 목표 비중
    if per_asset:
        asset_cols = st.columns(len(per_asset))
        for col, asset_info in zip(asset_cols, per_asset, strict=False):
            asset_id = str(asset_info.get("asset_id", ""))
            target_weight = asset_info.get("target_weight", 0)
            weight_pct = round(float(target_weight) * 100, 1) if isinstance(target_weight, int | float) else 0.0
            col.metric(asset_id.upper(), f"{weight_pct}%")

    st.caption(
        f"기간: {ps.get('start_date', 'N/A')} ~ {ps.get('end_date', 'N/A')} "
        f"| 초기 자본: {int(ps.get('initial_capital', 0)):,}원 "
        f"| 최종 자본: {int(ps.get('final_capital', 0)):,}원"
    )

    # ---- 섹션 2: 에쿼티 + 드로우다운 ----
    st.subheader("에쿼티 및 드로우다운")

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.05,
        subplot_titles=["에쿼티 (원)", "드로우다운 (%)"],
    )

    fig.add_trace(
        go.Scatter(
            x=exp.equity_df["Date"],
            y=exp.equity_df["equity"],
            mode="lines",
            name="에쿼티",
            line={"color": "rgba(33, 150, 243, 1)", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(33, 150, 243, 0.08)",
            hovertemplate="%{x|%Y-%m-%d}<br>에쿼티: %{y:,.0f}원<extra></extra>",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=exp.equity_df["Date"],
            y=exp.equity_df["drawdown_pct"],
            mode="lines",
            name="드로우다운",
            line={"color": "rgba(244, 67, 54, 1)", "width": 1.5},
            fill="tozeroy",
            fillcolor="rgba(244, 67, 54, 0.15)",
            hovertemplate="%{x|%Y-%m-%d}<br>드로우다운: %{y:.2f}%<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # 리밸런싱 발생일 마커 (rebalanced=True인 행)
    if "rebalanced" in exp.equity_df.columns:
        reb_df = exp.equity_df[exp.equity_df["rebalanced"] == True]  # noqa: E712
        if not reb_df.empty:
            fig.add_trace(
                go.Scatter(
                    x=reb_df["Date"],
                    y=reb_df["equity"],
                    mode="markers",
                    name="리밸런싱",
                    marker={"symbol": "circle", "color": "orange", "size": 4, "opacity": 0.6},
                    hovertemplate="%{x|%Y-%m-%d}<br>리밸런싱<extra></extra>",
                ),
                row=1,
                col=1,
            )

    fig.update_layout(
        height=_CHART_HEIGHT,
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch", key=f"equity_chart_{exp.experiment_name}")

    # ---- 섹션 3: 자산별 비중 추이 ----
    st.subheader("자산별 비중 추이")

    weight_cols = _weight_columns(exp.equity_df)
    if weight_cols:
        fig_weight = go.Figure()

        # 현금 비중 계산 (1 - 합산 비중)
        total_weight = exp.equity_df[weight_cols].sum(axis=1)
        cash_weight = (1.0 - total_weight).clip(lower=0.0)

        # 현금 (최하단)
        fig_weight.add_trace(
            go.Scatter(
                x=exp.equity_df["Date"],
                y=cash_weight * 100,
                mode="lines",
                name="현금",
                stackgroup="one",
                line={"width": 0},
                fillcolor="rgba(180, 180, 180, 0.6)",
                hovertemplate="%{x|%Y-%m-%d}<br>현금: %{y:.1f}%<extra></extra>",
            )
        )

        # 자산별 비중 (스택)
        for col in weight_cols:
            asset_id = _asset_id_from_weight_col(col)
            color = _get_asset_color(asset_id)
            # hex → rgba 변환
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            fill_color = f"rgba({r}, {g}, {b}, 0.6)"

            fig_weight.add_trace(
                go.Scatter(
                    x=exp.equity_df["Date"],
                    y=exp.equity_df[col] * 100,
                    mode="lines",
                    name=asset_id.upper(),
                    stackgroup="one",
                    line={"width": 0},
                    fillcolor=fill_color,
                    hovertemplate=(f"%{{x|%Y-%m-%d}}<br>{asset_id.upper()}: %{{y:.1f}}%<extra></extra>"),
                )
            )

        fig_weight.update_layout(
            title="자산별 비중 추이 (리밸런싱 효과 포함)",
            xaxis_title="날짜",
            yaxis_title="비중 (%)",
            yaxis={"range": [0, 100]},
            height=_SUB_CHART_HEIGHT,
            hovermode="x unified",
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        )
        st.plotly_chart(fig_weight, width="stretch", key=f"weight_chart_{exp.experiment_name}")
    else:
        st.info("비중 데이터가 없습니다.")

    # ---- 섹션 4: 자산별 거래 현황 ----
    st.subheader("자산별 거래 현황")

    if not exp.trades_df.empty and "asset_id" in exp.trades_df.columns:
        trade_count_df = exp.trades_df.groupby(["asset_id", "trade_type"]).size().reset_index(name="count")

        asset_ids = trade_count_df["asset_id"].unique().tolist()
        trade_types = trade_count_df["trade_type"].unique().tolist()

        fig_bar = go.Figure()
        type_colors = {"signal": "#1f77b4", "rebalance": "#ff7f0e"}

        for trade_type in trade_types:
            sub = trade_count_df[trade_count_df["trade_type"] == trade_type]
            counts = []
            for aid in asset_ids:
                row = sub[sub["asset_id"] == aid]
                counts.append(int(row["count"].values[0]) if not row.empty else 0)

            fig_bar.add_trace(
                go.Bar(
                    x=[aid.upper() for aid in asset_ids],
                    y=counts,
                    name="신호 거래" if trade_type == "signal" else "리밸런싱 거래",
                    marker_color=type_colors.get(trade_type, "#888888"),
                )
            )

        fig_bar.update_layout(
            title="자산별 거래 수 (신호 거래 vs 리밸런싱 거래)",
            xaxis_title="자산",
            yaxis_title="거래 수",
            barmode="group",
            height=_SMALL_CHART_HEIGHT,
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        )
        st.plotly_chart(fig_bar, width="stretch", key=f"bar_chart_{exp.experiment_name}")
    else:
        st.info("거래 데이터가 없습니다.")

    # ---- 섹션 5: 거래 내역 테이블 ----
    st.subheader("거래 내역")

    if not exp.trades_df.empty:
        # 자산 필터
        asset_filter_options = ["전체"]
        if "asset_id" in exp.trades_df.columns:
            asset_filter_options += sorted(exp.trades_df["asset_id"].unique().tolist())

        selected_asset = st.selectbox(
            "자산 필터",
            options=asset_filter_options,
            key=f"asset_filter_{exp.experiment_name}",
        )

        display_df = exp.trades_df.copy()
        if selected_asset != "전체":
            display_df = display_df[display_df["asset_id"] == selected_asset]

        # 표시할 컬럼만 선택 후 한글 변환
        display_cols = [c for c in _TRADE_COLUMN_RENAME if c in display_df.columns]
        display_df = display_df[display_cols].rename(columns=_TRADE_COLUMN_RENAME)

        st.dataframe(display_df, hide_index=True, width="stretch")
    else:
        st.info("거래 내역이 없습니다.")

    # ---- 섹션 6: 시그널 차트 ----
    st.subheader("시그널 차트")

    if exp.signal_dfs:
        asset_options = sorted(exp.signal_dfs.keys())
        selected_signal_asset = st.selectbox(
            "시그널 차트 자산 선택",
            options=asset_options,
            format_func=lambda x: x.upper(),
            key=f"signal_asset_{exp.experiment_name}",
        )

        signal_df = exp.signal_dfs[selected_signal_asset]
        _render_signal_chart(
            signal_df=signal_df,
            trades_df=exp.trades_df,
            asset_id=selected_signal_asset,
            experiment_name=exp.experiment_name,
            summary=exp.summary,
        )
    else:
        st.info("시그널 데이터가 없습니다.")

    # ---- 섹션 7: 파라미터 정보 ----
    with st.expander("파라미터 상세 정보"):
        portfolio_config = exp.summary.get("portfolio_config", {})
        st.json(portfolio_config)


# ============================================================
# 시그널 차트 (lightweight-charts 캔들스틱)
# ============================================================


def _find_asset_config(summary: dict[str, Any], asset_id: str) -> dict[str, Any] | None:
    """summary.json의 portfolio_config.assets에서 해당 자산의 설정을 찾는다."""
    config = summary.get("portfolio_config", {})
    assets: list[dict[str, Any]] = config.get("assets", [])
    for asset_cfg in assets:
        if asset_cfg.get("asset_id") == asset_id:
            return asset_cfg
    return None


def _compute_bands_for_signal(
    signal_df: pd.DataFrame,
    ma_col: str,
    buy_buffer_zone_pct: float,
    sell_buffer_zone_pct: float,
) -> pd.DataFrame:
    """signal_df에 상단/하단 밴드 컬럼을 추가한 복사본을 반환한다.

    Args:
        signal_df: 시그널 데이터 (ma_col 포함)
        ma_col: 이동평균 컬럼명 (예: "ma_200")
        buy_buffer_zone_pct: 매수 버퍼존 비율 (0.03 = 3%)
        sell_buffer_zone_pct: 매도 버퍼존 비율 (0.05 = 5%)

    Returns:
        upper_band, lower_band 컬럼이 추가된 DataFrame 복사본
    """
    df = signal_df.copy()
    df["upper_band"] = df[ma_col] * (1 + sell_buffer_zone_pct)
    df["lower_band"] = df[ma_col] * (1 - buy_buffer_zone_pct)
    return df


def _detect_ma_col(signal_df: pd.DataFrame) -> str | None:
    """signal_df에서 ma_* 컬럼을 탐지한다."""
    ma_cols = [c for c in signal_df.columns if c.startswith("ma_")]
    return ma_cols[0] if ma_cols else None


def _build_portfolio_candle_data(
    signal_df: pd.DataFrame,
    ma_col: str | None,
) -> list[dict[str, object]]:
    """signal_df를 lightweight-charts 캔들스틱 데이터로 변환한다.

    customValues를 포함하여 tooltip에서 OHLC, 전일대비%, MA, 밴드를 표시한다.
    """
    has_upper_band = "upper_band" in signal_df.columns
    has_lower_band = "lower_band" in signal_df.columns

    # 전일종가 시리즈 (전일대비% 계산용)
    prev_close = signal_df[COL_CLOSE].shift(1)

    candle_data: list[dict[str, object]] = []
    for i, row in enumerate(signal_df.itertuples(index=False)):
        d: date = getattr(row, COL_DATE)
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

        # customValues 구성 (Record<string, string>)
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

        # 밴드
        if has_upper_band:
            upper_val = row.upper_band  # type: ignore[attr-defined]
            if pd.notna(upper_val):
                cv["upper"] = f"{float(upper_val):.2f}"
        if has_lower_band:
            lower_val = row.lower_band  # type: ignore[attr-defined]
            if pd.notna(lower_val):
                cv["lower"] = f"{float(lower_val):.2f}"

        if cv:
            candle_entry["customValues"] = cv

        candle_data.append(candle_entry)

    return candle_data


def _build_lwc_series_data(df: pd.DataFrame, col: str) -> list[dict[str, object]]:
    """DataFrame의 특정 컬럼에서 lightweight-charts Line 시리즈 데이터를 생성한다."""
    data: list[dict[str, object]] = []
    for row in df.itertuples(index=False):
        val = getattr(row, col)
        if pd.notna(val):
            d: date = getattr(row, COL_DATE)
            data.append({"time": d.strftime("%Y-%m-%d"), "value": float(val)})
    return data


def _build_portfolio_markers(
    trades_df: pd.DataFrame,
    asset_id: str,
) -> list[dict[str, object]]:
    """해당 자산의 trades에서 Buy/Sell 마커를 생성한다."""
    markers: list[dict[str, object]] = []
    if trades_df.empty or "asset_id" not in trades_df.columns:
        return markers

    asset_trades = trades_df[trades_df["asset_id"] == asset_id]
    if asset_trades.empty or "entry_date" not in asset_trades.columns:
        return markers

    for trade in asset_trades.itertuples(index=False):
        entry_d = trade.entry_date
        if pd.notna(entry_d) and pd.notna(trade.entry_price):
            markers.append(
                {
                    "time": pd.Timestamp(entry_d).strftime("%Y-%m-%d"),
                    "position": "belowBar",
                    "color": _COLOR_BUY_MARKER,
                    "shape": "arrowUp",
                    "text": f"Buy ${trade.entry_price:.1f}",
                    "size": 2,
                }
            )

        exit_d = trade.exit_date
        if pd.notna(exit_d) and pd.notna(trade.exit_price):
            pnl_pct = float(trade.pnl_pct) * 100 if pd.notna(trade.pnl_pct) else 0.0
            markers.append(
                {
                    "time": pd.Timestamp(exit_d).strftime("%Y-%m-%d"),
                    "position": "aboveBar",
                    "color": _COLOR_SELL_MARKER,
                    "shape": "arrowDown",
                    "text": f"Sell {pnl_pct:+.1f}%",
                    "size": 2,
                }
            )

    return markers


def _render_signal_chart(
    signal_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    asset_id: str,
    experiment_name: str,
    summary: dict[str, Any],
) -> None:
    """lightweight-charts 캔들스틱 + MA + 밴드 + Buy/Sell 마커를 표시한다.

    Args:
        signal_df: 시그널 데이터 (OHLCV + ma_{N})
        trades_df: 거래 내역 (asset_id 컬럼 포함)
        asset_id: 표시할 자산 ID
        experiment_name: 실험명 (Streamlit 위젯 key 중복 방지용)
        summary: summary.json 데이터 (자산별 buffer params 추출용)
    """
    # 1. MA 컬럼 탐지
    ma_col = _detect_ma_col(signal_df)

    # 2. 밴드 계산 (buffer_zone 전략 자산만)
    asset_config = _find_asset_config(summary, asset_id)
    display_df = signal_df
    if ma_col and asset_config and asset_config.get("strategy_id") == "buffer_zone":
        buy_pct = float(asset_config.get("buy_buffer_zone_pct", 0.03))
        sell_pct = float(asset_config.get("sell_buffer_zone_pct", 0.05))
        display_df = _compute_bands_for_signal(signal_df, ma_col, buy_pct, sell_pct)

    # 3. 데이터 준비
    candle_data = _build_portfolio_candle_data(display_df, ma_col)
    markers = _build_portfolio_markers(trades_df, asset_id)

    # 4. 차트 테마
    chart_theme: dict[str, object] = {
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

    # 5. 캔들스틱 시리즈 + 마커
    candle_series: dict[str, object] = {
        "type": "Candlestick",
        "data": candle_data,
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
        candle_series["markers"] = markers

    pane_series: list[dict[str, object]] = [candle_series]

    # 6. MA 오버레이
    if ma_col:
        ma_data = _build_lwc_series_data(display_df, ma_col)
        if ma_data:
            window = ma_col.removeprefix("ma_")
            pane_series.append(
                {
                    "type": "Line",
                    "data": ma_data,
                    "options": {
                        "color": _COLOR_MA_LINE,
                        "lineWidth": 2,
                        "priceLineVisible": False,
                        "lastValueVisible": False,
                        "crosshairMarkerVisible": False,
                        "title": f"EMA-{window}",
                    },
                }
            )

    # 7. 상단 밴드
    if "upper_band" in display_df.columns:
        upper_data = _build_lwc_series_data(display_df, "upper_band")
        if upper_data:
            pane_series.append(
                {
                    "type": "Line",
                    "data": upper_data,
                    "options": {
                        "color": _COLOR_UPPER_BAND,
                        "lineWidth": 2,
                        "lineStyle": 2,
                        "priceLineVisible": False,
                        "lastValueVisible": False,
                        "crosshairMarkerVisible": False,
                    },
                }
            )

    # 8. 하단 밴드
    if "lower_band" in display_df.columns:
        lower_data = _build_lwc_series_data(display_df, "lower_band")
        if lower_data:
            pane_series.append(
                {
                    "type": "Line",
                    "data": lower_data,
                    "options": {
                        "color": _COLOR_LOWER_BAND,
                        "lineWidth": 2,
                        "lineStyle": 2,
                        "priceLineVisible": False,
                        "lastValueVisible": False,
                        "crosshairMarkerVisible": False,
                    },
                }
            )

    # 9. 렌더링
    chart_title = f"{asset_id.upper()} 시그널 차트"
    pane = {
        "chart": chart_theme,
        "series": pane_series,
        "height": _SIGNAL_CHART_HEIGHT,
        "title": chart_title,
    }

    lightweight_charts_v5_component(
        name=f"portfolio_signal_{experiment_name}_{asset_id}",
        charts=[pane],
        height=_SIGNAL_CHART_HEIGHT,
        zoom_level=_DEFAULT_ZOOM_LEVEL,
        scroll_padding=60,
        key=f"signal_chart_{experiment_name}_{asset_id}",
    )


# ============================================================
# 메인
# ============================================================


def main() -> None:
    """포트폴리오 비교 대시보드 진입점."""
    st.set_page_config(
        page_title="포트폴리오 비교 대시보드",
        layout="wide",
    )
    st.title("포트폴리오 비교 대시보드")
    st.caption("포트폴리오 실험 결과 비교")

    # 실험 탐색
    experiment_dirs = _discover_experiments()

    if not experiment_dirs:
        st.error(
            "포트폴리오 실험 결과가 없습니다. "
            "먼저 run_portfolio_backtest.py를 실행하세요.\n\n"
            "실행 명령어: `poetry run python scripts/backtest/run_portfolio_backtest.py`"
        )
        return

    # 데이터 로드
    experiments = [_load_experiment_data(d) for d in experiment_dirs]

    # 탭 구성: "전체 비교" + 실험별 탭
    tab_labels = ["전체 비교", *[exp.display_name for exp in experiments]]
    tabs = st.tabs(tab_labels)

    with tabs[0]:
        _render_comparison_tab(experiments)

    for i, exp in enumerate(experiments):
        with tabs[i + 1]:
            _render_experiment_tab(exp)


if __name__ == "__main__":
    main()
