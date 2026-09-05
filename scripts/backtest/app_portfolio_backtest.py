"""포트폴리오 비교 대시보드

포트폴리오 실험 결과를 비교한다.
전체 비교 탭에서 에쿼티 곡선·드로우다운·성과 지표를 나란히 보고,
실험별 탭에서 자산 비중 추이·시그널 차트·수익 기여도를 상세 확인한다.

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

import numpy as np
import pandas as pd
import plotly.colors as pc
import plotly.graph_objects as go
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component  # type: ignore[import-untyped]
from plotly.subplots import make_subplots

from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS
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
_COL_SHARPE = "Sharpe"
_COL_SORTINO = "Sortino"
_COL_TOTAL_RETURN = "총 수익률 (%)"
_COL_TOTAL_TRADES = "총 거래 수"
_COL_START_DATE = "시작일"
_COL_END_DATE = "종료일"

# --- 벤치마크 ---
_BENCHMARK_QQQ_FILENAME = "benchmark_qqq.json"
_COLOR_PORTFOLIO_BAR = "rgb(33, 150, 243)"
_COLOR_BENCHMARK_BAR = "rgb(255, 152, 0)"

# --- 동적 색상 팔레트 ---
# 자산/실험 ID를 정렬한 후 인덱스 기반으로 팔레트에서 색상을 할당한다.
# 신규 자산이나 실험이 추가되어도 코드 수정 없이 자동으로 구분되는 색을 받는다.
# 팔레트 길이를 초과하면 wrap-around(% len)로 순환한다.
_COLOR_PALETTE: tuple[str, ...] = tuple(pc.qualitative.Light24)


# ============================================================
# 데이터 구조
# ============================================================


@dataclass
class _ExperimentData:
    """로딩된 실험 결과 데이터."""

    experiment_name: str
    display_name: str
    result_dir: Path
    equity_df: pd.DataFrame
    trades_df: pd.DataFrame
    summary: dict[str, Any]
    signal_dfs: dict[str, pd.DataFrame] = field(default_factory=dict)


# ============================================================
# 데이터 로딩
# ============================================================


def _discover_experiments() -> list[Path]:
    """PORTFOLIO_CONFIGS에 등록된 실험의 결과 폴더를 탐색한다.

    Returns:
        유효한 실험 결과 폴더 경로 리스트 (CONFIGS 등록 순서)
    """
    result: list[Path] = []
    for cfg in PORTFOLIO_CONFIGS:
        if cfg.result_dir.is_dir() and (cfg.result_dir / "summary.json").exists():
            result.append(cfg.result_dir)

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


@st.cache_data
def _load_execution_comparison_csv(experiment_dir_str: str) -> pd.DataFrame | None:
    """execution_comparison.csv를 로드한다.

    Args:
        experiment_dir_str: 실험 디렉토리 경로 (문자열, 캐시 키용)

    Returns:
        execution_comparison DataFrame. 파일 미존재 시 None.
    """
    path = Path(experiment_dir_str) / "execution_comparison.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


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
        result_dir=experiment_dir,
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


@st.cache_data
def _build_color_map(ids: tuple[str, ...]) -> dict[str, str]:
    """ID 집합을 정렬된 순서로 팔레트 색상에 매핑한다.

    동일한 입력 tuple에 대해 결정적으로 동일한 색상 맵을 반환한다.
    팔레트보다 ID가 많으면 wrap-around로 순환하며, 이 경우 일부 색상이
    중복될 수 있다.

    Args:
        ids: 색상을 할당할 ID 집합 (해시를 위해 tuple)

    Returns:
        {id: hex_color} 형태의 매핑
    """
    sorted_ids = sorted(set(ids))
    palette_len = len(_COLOR_PALETTE)
    return {id_: _COLOR_PALETTE[i % palette_len] for i, id_ in enumerate(sorted_ids)}


def _get_asset_color(asset_id: str, asset_ids: tuple[str, ...]) -> str:
    """자산 ID에 대한 색상을 반환한다.

    asset_ids 컨텍스트(해당 차트에 등장하는 전체 자산 집합)를 기준으로
    정렬 인덱스 팔레트에서 색상을 할당한다.

    Args:
        asset_id: 색상을 조회할 자산 ID
        asset_ids: 색상 할당 컨텍스트 (해당 차트의 전체 자산 집합)

    Returns:
        hex 색상 문자열
    """
    return _build_color_map(asset_ids)[asset_id]


def _get_experiment_color(experiment_name: str, experiment_names: tuple[str, ...]) -> str:
    """실험명에 대한 색상을 반환한다.

    experiment_names 컨텍스트(해당 차트에 등장하는 전체 실험 집합)를 기준으로
    정렬 인덱스 팔레트에서 색상을 할당한다.

    Args:
        experiment_name: 색상을 조회할 실험명
        experiment_names: 색상 할당 컨텍스트 (해당 차트의 전체 실험 집합)

    Returns:
        hex 색상 문자열
    """
    return _build_color_map(experiment_names)[experiment_name]


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


def _get_asset_ids_from_equity(equity_df: pd.DataFrame) -> list[str]:
    """equity_df의 weight 컬럼에서 자산 ID 리스트를 추출한다."""
    return [_asset_id_from_weight_col(c) for c in _weight_columns(equity_df)]


# ============================================================
# 신규 섹션: 체결 전후 비교 (Before/After Execution)
# ============================================================


def _render_execution_comparison_section(exp: _ExperimentData) -> None:
    """체결 발생일의 자산별 전후 변화를 비교한다.

    사전 생성된 execution_comparison.csv를 로드하여 긴 표 형태로 표시한다.
    데이터가 많으므로 기본 숨김(expander collapsed) 상태로 제공한다.
    """
    with st.expander("체결 전후 비교", expanded=False):
        experiment_dir = exp.result_dir
        comparison_df = _load_execution_comparison_csv(str(experiment_dir))

        if comparison_df is None or comparison_df.empty:
            st.info("체결 전후 비교 데이터가 없습니다. run_portfolio_backtest.py를 재실행하세요.")
            return

        # 표시용 DataFrame 구성
        display_rows: list[dict[str, str]] = []
        for _, row in comparison_df.iterrows():
            asset_id = str(row["asset_id"])
            is_cash = asset_id == "cash"

            delta_shares = int(row["delta_shares"])
            delta_value = int(row["delta_value"])

            # 체결 사유 변환
            reason = str(row.get("rebalance_reason", ""))
            if reason == "nan":
                reason = ""
            reason_text = ""
            if reason == "monthly":
                reason_text = "월초 정기"
            elif reason == "daily":
                reason_text = "긴급"
            else:
                reason_text = "시그널"

            display_rows.append(
                {
                    "체결일": str(row["date"]),
                    "사유": reason_text,
                    "종목": "현금" if is_cash else asset_id.upper(),
                    "전일 주수": "-" if is_cash else str(int(row["pre_shares"])),
                    "전일 비중": f"{float(row['pre_weight_pct']):.1f}%",
                    "전일 평가액": f"{int(row['pre_value']):,}",
                    "당일 주수": "-" if is_cash else str(int(row["post_shares"])),
                    "당일 비중": f"{float(row['post_weight_pct']):.1f}%",
                    "당일 평가액": f"{int(row['post_value']):,}",
                    "주수 변동": "-" if is_cash else (f"{delta_shares:+d}" if delta_shares != 0 else "-"),
                    "금액 변동": f"{delta_value:+,}" if delta_value != 0 else "-",
                }
            )

        st.caption(f"총 {len(comparison_df['date'].unique())}개 체결일")
        st.dataframe(pd.DataFrame(display_rows), hide_index=True, width="stretch")


# ============================================================
# 신규 섹션: 월별 수익률 히트맵 (Monthly Returns)
# ============================================================


def _render_monthly_returns_section(exp: _ExperimentData) -> None:
    """월별 수익률을 히트맵으로 표시한다.

    월별/연간 수익률은 `run_portfolio_backtest.py`가 계산하여 summary.json에
    저장한 값을 사용한다. 이 함수는 데이터를 읽어 시각화만 담당한다.
    """
    st.subheader("월별 수익률")

    monthly_returns: list[dict[str, Any]] = exp.summary.get("monthly_returns", [])
    yearly_returns: list[dict[str, Any]] = exp.summary.get("yearly_returns", [])

    if not monthly_returns:
        st.info("월별 수익률 데이터가 없습니다. run_portfolio_backtest.py를 재실행하세요.")
        return

    # 1. 연도 x 월 피벗 구성
    returns_df = pd.DataFrame(monthly_returns)
    pivot = returns_df.pivot_table(values="return_pct", index="year", columns="month")
    years = sorted(pivot.index.tolist())

    # 2. 연간 수익률 매핑 (year -> return_pct)
    yearly_map: dict[int, float] = {}
    for entry in yearly_returns:
        yearly_map[int(str(entry["year"]))] = float(str(entry["return_pct"]))

    # 3. 월별(12열)과 연간(1열) 데이터 분리 구성
    # 색상 스케일을 각각 자기 데이터 기준으로 독립 적용하여
    # 연간 변동폭이 월별 셀의 대비를 압도하지 않도록 한다.
    month_labels = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]
    year_labels = [str(y) for y in years]

    z_monthly: list[list[float | None]] = []
    text_monthly: list[list[str]] = []
    z_yearly: list[list[float | None]] = []
    text_yearly: list[list[str]] = []

    for year in years:
        row_z: list[float | None] = []
        row_text: list[str] = []
        for m in range(1, 13):
            val: float | None = None
            if m in pivot.columns:
                cell = pivot.loc[year, m]
                if pd.notna(cell):
                    val = float(str(cell))
            row_z.append(val)
            row_text.append(f"{val:.2f}%" if val is not None else "")
        z_monthly.append(row_z)
        text_monthly.append(row_text)

        yearly_val = yearly_map.get(int(year))
        z_yearly.append([yearly_val])
        text_yearly.append([f"{yearly_val:.2f}%" if yearly_val is not None else ""])

    # 4. 색상 범위 (월별/연간 각자 대칭)
    monthly_vals = [v for row in z_monthly for v in row if v is not None]
    yearly_vals = [v for row in z_yearly for v in row if v is not None]
    max_abs_monthly = max(abs(min(monthly_vals)), abs(max(monthly_vals))) if monthly_vals else 10.0
    max_abs_yearly = max(abs(min(yearly_vals)), abs(max(yearly_vals))) if yearly_vals else 10.0

    _heatmap_colorscale = [
        [0.0, "rgb(239, 83, 80)"],
        [0.5, "rgb(255, 255, 255)"],
        [1.0, "rgb(38, 166, 154)"],
    ]

    # 5. make_subplots로 월별(12열) + 연간(1열) 분리, y축(연도) 공유
    # horizontal_spacing을 넉넉히 잡아 두 subplot 사이에 월별 컬러바가 들어갈 공간을 확보.
    # 레이아웃: [월별 히트맵] [월별 컬러바] [연간 히트맵] [연간 컬러바]
    fig_heatmap = make_subplots(
        rows=1,
        cols=2,
        column_widths=[12, 1],
        shared_yaxes=True,
        horizontal_spacing=0.12,
    )

    fig_heatmap.add_trace(
        go.Heatmap(
            z=z_monthly,
            x=month_labels,
            y=year_labels,
            text=text_monthly,
            texttemplate="%{text}",
            textfont={"size": 11},
            coloraxis="coloraxis",
            hovertemplate="%{y}년 %{x}: %{text}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig_heatmap.add_trace(
        go.Heatmap(
            z=z_yearly,
            x=["연간"],
            y=year_labels,
            text=text_yearly,
            texttemplate="%{text}",
            textfont={"size": 11},
            coloraxis="coloraxis2",
            hovertemplate="%{y}년 %{x}: %{text}<extra></extra>",
        ),
        row=1,
        col=2,
    )

    fig_heatmap.update_xaxes(side="top", row=1, col=1)
    fig_heatmap.update_xaxes(side="top", row=1, col=2)
    fig_heatmap.update_yaxes(autorange="reversed", row=1, col=1)
    fig_heatmap.update_yaxes(autorange="reversed", row=1, col=2)

    # 컬러바 위치 계산 근거 (paper 좌표, xanchor="left" 기본값):
    # column_widths=[12,1], horizontal_spacing=0.12 →
    #   월별 subplot 영역: [0, 0.812], 연간 subplot 영역: [0.932, 1.000]
    # 월별 컬러바는 월별 subplot 바로 우측(~0.83)에 두어 월별 히트맵 옆에 정렬.
    # 연간 컬러바는 figure 오른쪽(연간 subplot 우측 여백)에 둔다.
    fig_heatmap.update_layout(
        height=max(_SMALL_CHART_HEIGHT, len(year_labels) * 40 + 100),
        coloraxis={
            "colorscale": _heatmap_colorscale,
            "cmin": -max_abs_monthly,
            "cmax": max_abs_monthly,
            "colorbar": {"title": "월별 (%)", "x": 0.83, "xanchor": "left", "len": 0.9, "thickness": 14},
        },
        coloraxis2={
            "colorscale": _heatmap_colorscale,
            "cmin": -max_abs_yearly,
            "cmax": max_abs_yearly,
            "colorbar": {"title": "연간 (%)", "x": 1.02, "xanchor": "left", "len": 0.9, "thickness": 14},
        },
        margin={"r": 120},
    )
    st.plotly_chart(fig_heatmap, width="stretch", key=f"monthly_heatmap_{exp.experiment_name}")


# ============================================================
# 신규 섹션: 연간 수익률 벤치마크 비교 (vs QQQ)
# ============================================================


@st.cache_data
def _load_benchmark_qqq_json() -> dict[str, Any] | None:
    """benchmark_qqq.json을 로드한다. 파일이 없으면 None 반환."""
    path = PORTFOLIO_RESULTS_DIR / _BENCHMARK_QQQ_FILENAME
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
    return result


def _render_benchmark_comparison_section(exp: _ExperimentData) -> None:
    """연간 수익률을 QQQ 벤치마크와 비교하는 바차트 섹션.

    포트폴리오 연간 수익률과 QQQ 연간 수익률을 연도별 grouped bar로 표시하고,
    각 연도의 초과 수익(%p)을 별도 라인으로 병기한다.
    """
    st.subheader("연간 수익률 vs QQQ")

    benchmark = _load_benchmark_qqq_json()
    if benchmark is None:
        st.info(f"{_BENCHMARK_QQQ_FILENAME} 파일이 없습니다. " "먼저 run_portfolio_backtest.py를 실행하세요.")
        return

    yearly_returns: list[dict[str, Any]] = exp.summary.get("yearly_returns", [])
    bench_yearly: list[dict[str, Any]] = benchmark.get("yearly_returns", [])
    if not yearly_returns or not bench_yearly:
        st.info("연간 수익률 데이터가 없습니다.")
        return

    # 연도별 매핑 (inner join)
    port_map: dict[int, float] = {int(str(e["year"])): float(str(e["return_pct"])) for e in yearly_returns}
    bench_map: dict[int, float] = {int(str(e["year"])): float(str(e["return_pct"])) for e in bench_yearly}
    common_years = sorted(set(port_map.keys()) & set(bench_map.keys()))

    if not common_years:
        st.info("포트폴리오와 QQQ 벤치마크의 공통 연도가 없습니다.")
        return

    port_vals = [port_map[y] for y in common_years]
    bench_vals = [bench_map[y] for y in common_years]
    excess_vals = [p - b for p, b in zip(port_vals, bench_vals, strict=True)]
    year_labels = [str(y) for y in common_years]

    # grouped bar: 포트폴리오 vs QQQ
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.08,
        subplot_titles=["연간 수익률 (%)", "초과 수익 (%p)"],
    )

    fig.add_trace(
        go.Bar(
            x=year_labels,
            y=port_vals,
            name=exp.display_name,
            marker_color=_COLOR_PORTFOLIO_BAR,
            text=[f"{v:+.2f}%" for v in port_vals],
            textposition="outside",
            hovertemplate=f"%{{x}}<br>{exp.display_name}: %{{y:+.2f}}%<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=year_labels,
            y=bench_vals,
            name="QQQ",
            marker_color=_COLOR_BENCHMARK_BAR,
            text=[f"{v:+.2f}%" for v in bench_vals],
            textposition="outside",
            hovertemplate="%{x}<br>QQQ: %{y:+.2f}%<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # 초과 수익(%p) — 양수/음수 색상 분기
    excess_colors = [_COLOR_UP if v >= 0 else _COLOR_DOWN for v in excess_vals]
    fig.add_trace(
        go.Bar(
            x=year_labels,
            y=excess_vals,
            name="초과 수익 (%p)",
            marker_color=excess_colors,
            text=[f"{v:+.2f}" for v in excess_vals],
            textposition="outside",
            hovertemplate="%{x}<br>초과: %{y:+.2f}%p<extra></extra>",
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        height=_CHART_HEIGHT,
        barmode="group",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        margin={"t": 60},
    )
    fig.update_yaxes(title_text="수익률 (%)", row=1, col=1)
    fig.update_yaxes(title_text="초과 (%p)", row=2, col=1)
    fig.update_xaxes(title_text="연도", row=2, col=1)

    st.plotly_chart(fig, width="stretch", key=f"benchmark_compare_{exp.experiment_name}")

    # 승/패 요약 caption
    wins = sum(1 for v in excess_vals if v > 0)
    losses = sum(1 for v in excess_vals if v < 0)
    ties = sum(1 for v in excess_vals if v == 0)
    avg_excess = sum(excess_vals) / len(excess_vals) if excess_vals else 0.0
    st.caption(
        f"비교 기간 {benchmark.get('start_date', 'N/A')} ~ {benchmark.get('end_date', 'N/A')} "
        f"| 공통 연도 {len(common_years)}개 | QQQ 대비 승 {wins} / 패 {losses} / 무 {ties} "
        f"| 평균 초과 수익 {avg_excess:+.2f}%p "
        "(첫/마지막 해는 부분 기간일 수 있음)"
    )


# ============================================================
# 신규 섹션: 자산별 수익 기여도 (Asset Contribution)
# ============================================================


def _render_contribution_section(exp: _ExperimentData) -> None:
    """자산별 수익 기여도를 실현+미실현 손익 기반으로 표시한다.

    총 기여도 = 누적 실현손익 + 미실현손익이며, `run_portfolio_backtest.py`가
    `{asset_id}_contribution` 컬럼을 equity CSV에 사전 계산해 둔다.
    매도 후에도 실현손익이 유지되어 자산별 기여 이력이 끊기지 않는다.
    """
    st.subheader("자산별 수익 기여도")

    equity_df = exp.equity_df
    if equity_df.empty:
        st.info("에쿼티 데이터가 없습니다.")
        return

    asset_ids = _get_asset_ids_from_equity(equity_df)

    # contribution 컬럼은 엔진이 사전 계산. 컬럼 부재 시 사용자가 재실행해야 한다.
    missing = [f"{aid}_contribution" for aid in asset_ids if f"{aid}_contribution" not in equity_df.columns]
    if missing:
        st.error("기여도 컬럼이 누락되었습니다: " + ", ".join(missing) + ". run_portfolio_backtest.py를 재실행하세요.")
        return

    df = equity_df[["Date"]].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    contrib_cols: list[str] = []
    for aid in asset_ids:
        col = f"{aid}_contribution"
        df[col] = equity_df[col].to_numpy()
        contrib_cols.append(col)

    df = df.set_index("Date")

    # 분기별 기여도 변동분 (스택 바차트)
    quarterly = df[contrib_cols].resample("QE").last()
    quarterly_diff = quarterly.diff()
    quarterly_diff = quarterly_diff.iloc[1:]

    if quarterly_diff.empty:
        st.info("분기별 기여도를 계산할 수 없습니다.")
        return

    fig_contrib = go.Figure()
    quarter_labels = [f"{d.year}Q{(d.month - 1) // 3 + 1}" for d in quarterly_diff.index]
    asset_ids_tuple = tuple(asset_ids)

    for aid in asset_ids:
        col = f"{aid}_contribution"
        if col not in quarterly_diff.columns:
            continue
        color = _get_asset_color(aid, asset_ids_tuple)
        fig_contrib.add_trace(
            go.Bar(
                x=quarter_labels,
                y=quarterly_diff[col].values,
                name=aid.upper(),
                marker_color=color,
                hovertemplate=f"{aid.upper()}: %{{y:+,.0f}}원<extra></extra>",
            )
        )

    fig_contrib.update_layout(
        title="분기별 자산 기여도 (실현+미실현 손익 변동분)",
        barmode="relative",
        height=_SUB_CHART_HEIGHT,
        xaxis_title="분기",
        yaxis_title="기여 금액 (원)",
        yaxis_hoverformat="+,.0f",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig_contrib, width="stretch", key=f"contrib_bar_{exp.experiment_name}")

    # 누적 기여도 면적 차트 (실현+미실현 손익)
    fig_cum = go.Figure()
    for aid in asset_ids:
        col = f"{aid}_contribution"
        if col not in df.columns:
            continue
        color = _get_asset_color(aid, asset_ids_tuple)
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        # stackgroup/hovermode=x unified 조합에서 d3-format(:+,.0f)이 불안정하게 적용되는
        # 사례가 있어, Python 측에서 미리 포맷한 문자열을 text로 전달하고 %{text}를 참조한다.
        # mode="lines"라 text가 라인 위에 표시되지 않고 hover 라벨 용도로만 쓰인다.
        preformatted = [f"{v:+,.0f}" for v in df[col]]
        fig_cum.add_trace(
            go.Scatter(
                x=df.index,
                y=df[col],
                mode="lines",
                name=aid.upper(),
                stackgroup="one",
                line={"width": 0},
                fillcolor=f"rgba({r}, {g}, {b}, 0.6)",
                text=preformatted,
                hovertemplate=f"{aid.upper()}: %{{text}}원<extra></extra>",
            )
        )

    fig_cum.update_layout(
        title="누적 자산별 기여도 (실현+미실현 손익)",
        height=_SUB_CHART_HEIGHT,
        xaxis_title="날짜",
        yaxis_title="누적 기여 금액 (원)",
        yaxis_hoverformat="+,.0f",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig_cum, width="stretch", key=f"contrib_cum_{exp.experiment_name}")

    # 실현/미실현 분해 차트 (자산별 마지막 값 기준 수평 바)
    final_row = equity_df.iloc[-1]
    realized_vals = [float(final_row.get(f"{aid}_realized_pnl", 0)) for aid in asset_ids]
    unrealized_vals = [float(final_row.get(f"{aid}_unrealized_pnl", 0)) for aid in asset_ids]
    labels = [aid.upper() for aid in asset_ids]

    # barmode="stack" stacked bar 에서도 d3-format이 불안정할 수 있어 text 방식으로 통일한다.
    # textposition="none"으로 바 위에 라벨이 노출되는 것을 차단하고 hover 라벨에만 사용한다.
    realized_text = [f"{v:+,.0f}" for v in realized_vals]
    unrealized_text = [f"{v:+,.0f}" for v in unrealized_vals]

    fig_decomp = go.Figure()
    fig_decomp.add_trace(
        go.Bar(
            y=labels,
            x=realized_vals,
            name="실현손익",
            orientation="h",
            marker_color="rgba(55, 128, 191, 0.8)",
            text=realized_text,
            textposition="none",
            hovertemplate="%{y}: %{text}원<extra>실현손익</extra>",
        )
    )
    fig_decomp.add_trace(
        go.Bar(
            y=labels,
            x=unrealized_vals,
            name="미실현손익",
            orientation="h",
            marker_color="rgba(219, 64, 82, 0.8)",
            text=unrealized_text,
            textposition="none",
            hovertemplate="%{y}: %{text}원<extra>미실현손익</extra>",
        )
    )
    fig_decomp.update_layout(
        title="자산별 손익 분해 (최종일 기준)",
        barmode="stack",
        height=max(250, len(asset_ids) * 60 + 100),
        xaxis_title="손익 (원)",
        xaxis_hoverformat="+,.0f",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig_decomp, width="stretch", key=f"contrib_decomp_{exp.experiment_name}")


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
                _COL_SHARPE: ps.get("sharpe_ratio", "N/A"),
                _COL_SORTINO: ps.get("sortino_ratio", "N/A"),
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
    # 색상 할당 컨텍스트는 전체 experiments 기준으로 고정한다.
    # multiselect 선택이 변해도 같은 실험은 항상 동일한 색상을 받는다.
    all_experiment_names_tuple = tuple(e.experiment_name for e in experiments)

    fig_equity = go.Figure()
    for exp in selected_exps:
        color = _get_experiment_color(exp.experiment_name, all_experiment_names_tuple)
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
        color = _get_experiment_color(exp.experiment_name, all_experiment_names_tuple)
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

    # ---- 요약 지표 ----
    st.subheader("요약 지표")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("CAGR", f"{ps.get('cagr', 'N/A')}%")
    col2.metric("MDD", f"{ps.get('mdd', 'N/A')}%")
    col3.metric("Calmar", str(ps.get("calmar", "N/A")))
    col4.metric("Sharpe", str(ps.get("sharpe_ratio", "N/A")))
    col5.metric("Sortino", str(ps.get("sortino_ratio", "N/A")))
    col6.metric("총 수익률", f"{ps.get('total_return_pct', 'N/A')}%")

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

    # ---- 에쿼티 + 드로우다운 ----
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

    # 리밸런싱 발생일 마커 (rebalanced=True인 행, 사유 hover 포함)
    if "rebalanced" in exp.equity_df.columns:
        reb_df = exp.equity_df[exp.equity_df["rebalanced"] == True].copy()  # noqa: E712
        if not reb_df.empty:
            # 리밸런싱 사유 hover 텍스트 구성
            hover_texts: list[str] = []
            has_reason = "rebalance_reason" in reb_df.columns
            for _, reb_row in reb_df.iterrows():
                d_str = pd.Timestamp(reb_row["Date"]).strftime("%Y-%m-%d")
                if has_reason and str(reb_row.get("rebalance_reason", "")):
                    reason = str(reb_row["rebalance_reason"])
                    reason_label = "월초 정기" if reason == "monthly" else "긴급"
                    hover_texts.append(f"{d_str}<br>리밸런싱 ({reason_label})")
                else:
                    hover_texts.append(f"{d_str}<br>리밸런싱")

            fig.add_trace(
                go.Scatter(
                    x=reb_df["Date"],
                    y=reb_df["equity"],
                    mode="markers",
                    name="리밸런싱",
                    marker={"symbol": "circle", "color": "orange", "size": 4, "opacity": 0.6},
                    text=hover_texts,
                    hovertemplate="%{text}<extra></extra>",
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

    # ---- 자산별 비중 추이 ----
    st.subheader("자산별 비중 추이")

    weight_cols = _weight_columns(exp.equity_df)
    if weight_cols:
        fig_weight = go.Figure()
        weight_asset_ids_tuple = tuple(_asset_id_from_weight_col(c) for c in weight_cols)

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
            color = _get_asset_color(asset_id, weight_asset_ids_tuple)
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

    # ---- 시그널 차트 ----
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
        per_asset_list: list[dict[str, Any]] = exp.summary.get("per_asset", [])
        asset_meta = next(
            (a for a in per_asset_list if a.get("asset_id") == selected_signal_asset),
            None,
        )
        open_position_meta: dict[str, Any] | None = asset_meta.get("open_position") if asset_meta else None
        _render_signal_chart(
            signal_df=signal_df,
            trades_df=exp.trades_df,
            asset_id=selected_signal_asset,
            experiment_name=exp.experiment_name,
            open_position=open_position_meta,
        )
    else:
        st.info("시그널 데이터가 없습니다.")

    # ---- 파라미터 정보 ----
    with st.expander("파라미터 상세 정보"):
        portfolio_config = exp.summary.get("portfolio_config", {})
        st.json(portfolio_config)

    # ---- 신규 섹션: 체결 전후 비교 ----
    st.divider()
    _render_execution_comparison_section(exp)

    # ---- 신규 섹션: 월별 수익률 히트맵 ----
    st.divider()
    _render_monthly_returns_section(exp)

    # ---- 신규 섹션: 연간 수익률 벤치마크 비교 (vs QQQ) ----
    st.divider()
    _render_benchmark_comparison_section(exp)

    # ---- 신규 섹션: 자산별 수익 기여도 ----
    st.divider()
    _render_contribution_section(exp)


# ============================================================
# 시그널 차트 (lightweight-charts 캔들스틱)
# ============================================================


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
    전일종가대비%(`open_pct`/`high_pct`/`low_pct`/`close_pct`) 및 buffer_zone 자산의
    `upper_band`/`lower_band`는 `run_portfolio_backtest.py`가 사전 계산해 signal CSV에
    저장한 컬럼을 직접 읽는다.
    """
    has_upper_band = "upper_band" in signal_df.columns
    has_lower_band = "lower_band" in signal_df.columns

    # 4종 전일대비% 컬럼은 numpy 배열로 미리 추출해 인덱스 접근.
    # itertuples namedtuple 속성은 정적 타입 체커가 인식하지 못하므로 배열 추출이 가장 클린하다.
    pct_arrays: dict[str, np.ndarray[Any, Any]] = {}
    for pct_col in ("open_pct", "high_pct", "low_pct", "close_pct"):
        if pct_col in signal_df.columns:
            pct_arrays[pct_col] = signal_df[pct_col].to_numpy()

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

        # 전일종가대비% (CSV 사전 계산 컬럼 — 첫날은 NaN이므로 제외)
        for pct_col, pct_arr in pct_arrays.items():
            v = pct_arr[i]
            if pd.notna(v):
                cv[pct_col] = f"{float(v):+.2f}"

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
    open_position: dict[str, Any] | None = None,
) -> list[dict[str, object]]:
    """해당 자산의 trades에서 Buy/Sell 마커를 생성한다.

    완료된 거래의 Buy/Sell에 더해, `open_position`이 주어지면 미청산 매수
    체결일에도 "Buy $XX.X (보유중)" 마커를 추가한다 (단일 백테스트와 동일 규약).

    Args:
        trades_df: 포트폴리오 전체 거래 내역 (asset_id 컬럼 포함)
        asset_id: 마커를 생성할 자산 ID
        open_position: summary.per_asset[asset_id].open_position. `None`이면 미청산 없음.
            존재 시 dict 형태 {"entry_date": str, "entry_price": float, "shares": int}

    Returns:
        시간 순 정렬된 마커 리스트.
    """
    markers: list[dict[str, object]] = []

    # 분할 매도 시 동일 entry_date가 여러 행에 반복되므로, Buy 마커는 진입일당 1회만 생성
    seen_entry_dates: set[str] = set()

    if not trades_df.empty and "asset_id" in trades_df.columns:
        asset_trades = trades_df[trades_df["asset_id"] == asset_id]
        if not asset_trades.empty and "entry_date" in asset_trades.columns:
            for trade in asset_trades.itertuples(index=False):
                entry_d = trade.entry_date
                if pd.notna(entry_d) and pd.notna(trade.entry_price):
                    entry_key = pd.Timestamp(entry_d).strftime("%Y-%m-%d")
                    if entry_key not in seen_entry_dates:
                        seen_entry_dates.add(entry_key)
                        markers.append(
                            {
                                "time": entry_key,
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

    # 미청산 포지션 Buy 마커 (trades_df의 Buy와 중복되지 않을 때만 추가)
    if open_position is not None:
        entry_date_val = open_position.get("entry_date")
        entry_price_val = open_position.get("entry_price")
        if entry_date_val and entry_price_val is not None:
            entry_key = pd.Timestamp(str(entry_date_val)).strftime("%Y-%m-%d")
            if entry_key not in seen_entry_dates:
                markers.append(
                    {
                        "time": entry_key,
                        "position": "belowBar",
                        "color": _COLOR_BUY_MARKER,
                        "shape": "arrowUp",
                        "text": f"Buy ${float(entry_price_val):.1f} (보유중)",
                        "size": 2,
                    }
                )

    # lightweight-charts는 마커가 시간순 정렬되어야 정상 표시된다
    markers.sort(key=lambda m: str(m["time"]))
    return markers


def _render_signal_chart(
    signal_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    asset_id: str,
    experiment_name: str,
    open_position: dict[str, Any] | None = None,
) -> None:
    """lightweight-charts 캔들스틱 + MA + 밴드 + Buy/Sell 마커를 표시한다.

    `signal_df`의 `upper_band`/`lower_band` 컬럼은 `run_portfolio_backtest.py`가
    buffer_zone 자산에 한해 사전 계산해 둔 값이며, buy_and_hold 자산은 컬럼이
    존재하지 않으므로 Feature Detection으로 자동 분기된다.

    Args:
        signal_df: 시그널 데이터 (OHLCV + ma_{N} + 4종 % + buffer_zone일 경우 밴드)
        trades_df: 거래 내역 (asset_id 컬럼 포함)
        asset_id: 표시할 자산 ID
        experiment_name: 실험명 (Streamlit 위젯 key 중복 방지용)
        open_position: 미청산 포지션 정보. 존재 시 "Buy $XX.X (보유중)" 마커 추가.
    """
    # 1. MA 컬럼 탐지
    ma_col = _detect_ma_col(signal_df)

    # 2. 데이터 준비 (밴드 컬럼은 CSV에서 직접 읽음)
    candle_data = _build_portfolio_candle_data(signal_df, ma_col)
    markers = _build_portfolio_markers(trades_df, asset_id, open_position=open_position)

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
        ma_data = _build_lwc_series_data(signal_df, ma_col)
        if ma_data:
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
                    },
                }
            )

    # 7. 상단 밴드
    if "upper_band" in signal_df.columns:
        upper_data = _build_lwc_series_data(signal_df, "upper_band")
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
    if "lower_band" in signal_df.columns:
        lower_data = _build_lwc_series_data(signal_df, "lower_band")
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
