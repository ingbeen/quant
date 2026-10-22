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
from lightweight_charts_v5 import lightweight_charts_v5_component
from plotly.subplots import make_subplots

from qbt.backtest.constants import (
    EQUITY_FILENAME,
    LEDGER_FILENAME,
    PORTFOLIO_SIGNAL_PREFIX,
    REBALANCE_REASON_METHODS,
    REBALANCE_REASON_MONTHLY,
    SUMMARY_FILENAME,
    TRADE_TYPE_SIGNAL,
    TRADES_FILENAME,
)
from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS
from qbt.common_constants import (
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

# --- 리밸런싱 사유(엔진의 rebalance_reason 값) → 화면 문구 ---
# 리밸런싱했는데 사유가 빈 값이면 배분 규칙 매매법이 목표 비중 변화에 맞춰 조정한 것이다
_REBALANCE_REASON_LABELS: dict[str, str] = {
    REBALANCE_REASON_MONTHLY: "월초 정기",
    REBALANCE_REASON_METHODS: "매매법 사이 비중",
    "": "배분 조정",
}

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
    # 매매법이 여럿인 실험만 — 매매법별 장부 (날짜 × 매매법)
    ledger_df: pd.DataFrame | None = None


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
        if cfg.result_dir.is_dir() and (cfg.result_dir / SUMMARY_FILENAME).exists():
            result.append(cfg.result_dir)

    return result


def _cache_args(path: Path) -> tuple[Path, float]:
    """캐시 로더에 넘길 (경로, 수정 시각)을 만든다.

    수정 시각은 캐시 키로만 쓰인다 — 러너가 파일을 다시 만들면 키가 바뀌어 새로 읽는다.
    없는 파일은 0.0 이라, 나중에 생기면 역시 키가 바뀐다.
    """
    return path, (path.stat().st_mtime if path.exists() else 0.0)


@st.cache_data
def _load_equity_csv(path: Path, mtime: float) -> pd.DataFrame:
    """equity.csv를 로드한다 (Date 열 datetime 변환, 빈 리밸런싱 사유는 빈 문자열). 인자는 `_cache_args` 참고."""
    df = pd.read_csv(path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    df["rebalance_reason"] = df["rebalance_reason"].fillna("")
    return df


@st.cache_data
def _load_trades_csv(path: Path, mtime: float) -> pd.DataFrame:
    """trades.csv를 로드한다 (entry_date / exit_date datetime 변환). 인자는 `_cache_args` 참고."""
    df = pd.read_csv(path)
    for col in ("entry_date", "exit_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


@st.cache_data
def _load_summary_json(path: Path, mtime: float) -> dict[str, Any]:
    """summary.json을 로드한다. 인자는 `_cache_args` 참고."""
    with path.open(encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
    return result


@st.cache_data
def _load_signal_csv(path: Path, mtime: float) -> pd.DataFrame:
    """signal_{asset_id}.csv를 로드한다 (Date 열 datetime 변환). 인자는 `_cache_args` 참고."""
    df = pd.read_csv(path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


@st.cache_data
def _load_ledger_csv(path: Path, mtime: float) -> pd.DataFrame | None:
    """ledger.csv(매매법별 장부)를 로드한다 (Date 열 datetime 변환, 빈 리밸런싱 사유는 빈 문자열).

    매매법이 하나인 실험에는 없어 None. 인자는 `_cache_args` 참고.
    """
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"])
    df["rebalance_reason"] = df["rebalance_reason"].fillna("")
    return df


def _load_experiment_data(experiment_dir: Path) -> _ExperimentData:
    """한 실험의 모든 결과 데이터를 로드한다.

    Args:
        experiment_dir: 실험 결과 디렉토리 경로

    Returns:
        _ExperimentData 인스턴스
    """
    summary = _load_summary_json(*_cache_args(experiment_dir / SUMMARY_FILENAME))
    equity_df = _load_equity_csv(*_cache_args(experiment_dir / EQUITY_FILENAME))
    trades_df = _load_trades_csv(*_cache_args(experiment_dir / TRADES_FILENAME))

    # signal_{asset_id}.csv 탐색 및 로드
    signal_dfs: dict[str, pd.DataFrame] = {}
    for signal_path in sorted(experiment_dir.glob(f"{PORTFOLIO_SIGNAL_PREFIX}*.csv")):
        # "signal_qqq.csv" → asset_id = "qqq"
        asset_id = signal_path.stem.removeprefix(PORTFOLIO_SIGNAL_PREFIX)
        signal_dfs[asset_id] = _load_signal_csv(*_cache_args(signal_path))

    display_name: str = summary["display_name"]

    return _ExperimentData(
        experiment_name=experiment_dir.name,
        display_name=display_name,
        result_dir=experiment_dir,
        equity_df=equity_df,
        trades_df=trades_df,
        summary=summary,
        signal_dfs=signal_dfs,
        ledger_df=_load_ledger_csv(*_cache_args(experiment_dir / LEDGER_FILENAME)),
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


def _palette_color(id_: str, ids: tuple[str, ...]) -> str:
    """ID(자산 · 실험 · 매매법)의 hex 색상을 반환한다.

    ids(해당 차트에 등장하는 전체 ID 집합)를 정렬한 순서로 팔레트 색상을 할당한다.
    """
    return _build_color_map(ids)[id_]


def _weight_columns(equity_df: pd.DataFrame) -> list[str]:
    """equity_df에서 {asset_id}_weight 컬럼명 리스트를 반환한다."""
    return [c for c in equity_df.columns if c.endswith("_weight")]


def _asset_id_from_weight_col(col: str) -> str:
    """'{asset_id}_weight' 컬럼명에서 asset_id를 추출한다."""
    return col.removesuffix("_weight")


def _get_asset_ids_from_equity(equity_df: pd.DataFrame) -> list[str]:
    """equity_df의 weight 컬럼에서 자산 ID 리스트를 추출한다."""
    return [_asset_id_from_weight_col(c) for c in _weight_columns(equity_df)]


def _method_display_names(summary: dict[str, Any]) -> dict[str, str]:
    """summary.json 의 per_method 에서 {method_id: 표시 이름} 을 만든다 (매매법이 여럿인 실험만)."""
    return {str(m["method_id"]): str(m["display_name"]) for m in summary["per_method"]}


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
    max_abs_monthly = max(abs(min(monthly_vals)), abs(max(monthly_vals)))
    max_abs_yearly = max(abs(min(yearly_vals)), abs(max(yearly_vals)))

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
    contrib_cols: list[str] = []
    for aid in asset_ids:
        col = f"{aid}_contribution"
        df[col] = equity_df[col].to_numpy()
        contrib_cols.append(col)

    df = df.set_index("Date")

    # 분기별 기여도 변동분 (스택 바차트)
    # 첫 분기는 직전 분기가 없으므로 그 분기 말 누적값이 곧 변동분이다 (기여도는 0 에서 출발)
    quarterly = df[contrib_cols].resample("QE").last()
    quarterly_diff = quarterly.diff().fillna(quarterly)

    if quarterly_diff.empty:
        st.info("분기별 기여도를 계산할 수 없습니다.")
        return

    fig_contrib = go.Figure()
    quarter_labels = [f"{d.year}Q{(d.month - 1) // 3 + 1}" for d in quarterly_diff.index]
    asset_ids_tuple = tuple(asset_ids)

    for aid in asset_ids:
        col = f"{aid}_contribution"
        color = _palette_color(aid, asset_ids_tuple)
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
        fill_color = _hex_to_rgba(_palette_color(aid, asset_ids_tuple), 0.6)

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
                fillcolor=fill_color,
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
    realized_vals = [float(final_row[f"{aid}_realized_pnl"]) for aid in asset_ids]
    unrealized_vals = [float(final_row[f"{aid}_unrealized_pnl"]) for aid in asset_ids]
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
# 매매법별 손익 (매매법이 여럿인 실험)
# ============================================================


def _render_method_section(exp: _ExperimentData) -> None:
    """매매법별 손익 · 몫 추이 · 최종일 요약 · 계좌 종목 합계를 표시한다.

    숫자는 러너가 summary.json(per_method · pnl_check · netting · account_holdings)과
    ledger.csv 에 미리 계산해 둔다 — 여기서는 읽어서 보여주기만 한다.
    """
    st.subheader("매매법별 손익")
    st.caption(
        "매매법마다 자기 몫(자본) · 현금 · 보유 주수를 따로 갖습니다. 장부에는 각 매매법이 혼자 매매한 것처럼 "
        "비용을 매기고, 같은 날 같은 종목을 매매법끼리 반대로 사고팔아 계좌에서 아낀 비용은 「상계 절감」으로 따로 둡니다. "
        "그래서 계좌 손익 = Σ 매매법 손익 + 상계 절감입니다. 위 섹션들의 자산 이름은 「매매법.종목」입니다."
    )

    ledger_df = exp.ledger_df
    if ledger_df is None or ledger_df.empty:
        st.info("매매법 장부가 없습니다.")
        return

    method_ids = list(dict.fromkeys(ledger_df["method_id"].astype(str)))
    method_ids_tuple = tuple(method_ids)
    per_method: list[dict[str, Any]] = exp.summary["per_method"]
    names = _method_display_names(exp.summary)

    # 누적 손익 (실현 + 미실현)
    fig_pnl = go.Figure()
    for method_id in method_ids:
        rows = ledger_df[ledger_df["method_id"] == method_id]
        label = names[method_id]
        fig_pnl.add_trace(
            go.Scatter(
                x=rows["Date"],
                y=rows["pnl"],
                mode="lines",
                name=label,
                line={"color": _palette_color(method_id, method_ids_tuple), "width": 2},
                hovertemplate=f"{label}: %{{y:+,.0f}}원<extra></extra>",
            )
        )
    fig_pnl.update_layout(
        title="매매법별 누적 손익 (실현 + 미실현)",
        height=_SUB_CHART_HEIGHT,
        xaxis_title="날짜",
        yaxis_title="누적 손익 (원)",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig_pnl, width="stretch", key=f"method_pnl_{exp.experiment_name}")

    # 몫 추이와 목표 몫 — 임계값은 이 결과를 만든 실행의 값이다(상수를 바꾸고 다시 돌리기 전에도 그린 장부와 맞는다)
    threshold_rate = float(exp.summary["portfolio_config"]["rebalance_threshold_rate"])
    fig_share = go.Figure()
    for method_id in method_ids:
        rows = ledger_df[ledger_df["method_id"] == method_id]
        label = names[method_id]
        color = _palette_color(method_id, method_ids_tuple)
        fig_share.add_trace(
            go.Scatter(
                x=rows["Date"],
                y=rows["share"] * 100,
                mode="lines",
                name=label,
                line={"color": color, "width": 2},
                hovertemplate=f"{label}: %{{y:.1f}}%<extra></extra>",
            )
        )
        fig_share.add_trace(
            go.Scatter(
                x=rows["Date"],
                y=rows["target_share"] * 100,
                mode="lines",
                name=f"{label} 목표",
                line={"color": color, "width": 1, "dash": "dash"},
                hovertemplate=f"{label} 목표: %{{y:.1f}}%<extra></extra>",
            )
        )
    fig_share.update_layout(
        title=f"매매법 몫 추이 (점선 = 목표 몫, 월말에 상대 편차 {threshold_rate * 100:g}% 를 넘으면 되돌림)",
        height=_SUB_CHART_HEIGHT,
        xaxis_title="날짜",
        yaxis_title="계좌 대비 몫 (%)",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig_share, width="stretch", key=f"method_share_{exp.experiment_name}")

    # 최종일 매매법 요약
    summary_rows = [
        {
            "매매법": names[m["method_id"]],
            "목표 몫 (%)": round(float(m["target_share"]) * 100, 1),
            "최종 몫 (%)": round(float(m["final_share"]) * 100, 1),
            "최종 자본 (원)": int(m["final_equity"]),
            "손익 (원)": int(m["pnl"]),
            "실현 (원)": int(m["realized_pnl"]),
            "미실현 (원)": int(m["unrealized_pnl"]),
            "장부 비용 (원)": int(m["cost"]),
            "이전 누적 (원)": int(m["transfers"]),
            "몫 되돌리기 횟수": int(m["method_rebalance_days"]),
        }
        for m in per_method
    ]
    st.markdown("**최종일 매매법 요약**")
    st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)

    asset_rows = [
        {
            "매매법": names[m["method_id"]],
            "자산 키": str(a["asset_id"]),
            "손익 (원)": int(a["pnl"]),
        }
        for m in per_method
        for a in m["assets"]
    ]
    st.markdown("**매매법 × 종목 손익 (최종일, 실현 + 미실현)**")
    st.dataframe(pd.DataFrame(asset_rows), width="stretch", hide_index=True)

    # 대조: 계좌 손익 = Σ 매매법 손익 + 상계 절감
    pnl_check: dict[str, Any] = exp.summary["pnl_check"]
    netting: dict[str, Any] = exp.summary["netting"]
    st.markdown("**대조: 계좌 손익 = Σ 매매법 손익 + 상계 절감**")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "계좌 손익 (원)": int(pnl_check["account_pnl"]),
                    "Σ 매매법 손익 (원)": int(pnl_check["methods_pnl_sum"]),
                    "상계 절감 (원)": int(pnl_check["netting_savings"]),
                    "차이 (원)": int(pnl_check["difference"]),
                    "상계가 있던 날": int(netting["netting_days"]),
                    "상계된 주수": int(netting["netted_shares"]),
                }
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    # 계좌 종목 합계 (실제 계좌에 보이는 모습)
    holdings: list[dict[str, Any]] = exp.summary["account_holdings"]
    st.markdown("**계좌 종목 합계 (최종일 — 실제 계좌에는 이렇게 보인다)**")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "종목": str(h["asset_id"]).upper(),
                    "주수": int(h["shares"]),
                    "평가액 (원)": int(h["value"]),
                    "비중 (%)": round(float(h["weight"]) * 100, 2),
                }
                for h in holdings
            ]
        ),
        width="stretch",
        hide_index=True,
    )


# ============================================================
# 전체 비교 탭
# ============================================================


def _render_comparison_tab(experiments: list[_ExperimentData]) -> None:
    """전체 비교 탭 — 포트폴리오 실험의 성과 지표·에쿼티 곡선·드로우다운을 비교한다."""

    # ---- 성과 지표 비교 테이블 ----
    st.subheader("성과 지표 비교")

    rows: list[dict[str, Any]] = []
    for exp in experiments:
        ps: dict[str, Any] = exp.summary["portfolio_summary"]
        rows.append(
            {
                _COL_DISPLAY_NAME: exp.display_name,
                _COL_CAGR: ps["cagr"],
                _COL_MDD: ps["mdd"],
                _COL_CALMAR: ps["calmar"],
                _COL_SHARPE: ps["sharpe_ratio"],
                _COL_SORTINO: ps["sortino_ratio"],
                _COL_TOTAL_RETURN: ps["total_return_pct"],
                _COL_TOTAL_TRADES: ps["total_trades"],
                _COL_START_DATE: ps["start_date"],
                _COL_END_DATE: ps["end_date"],
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
        color = _palette_color(exp.experiment_name, all_experiment_names_tuple)
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
    st.caption("실험마다 시작일이 다릅니다(위 표의 시작일). 늦게 시작한 실험의 곡선은 그 시작일의 초기 자본에서 출발합니다.")

    # ---- 드로우다운 비교 ----
    st.subheader("드로우다운 비교")

    fig_dd = go.Figure()
    for exp in selected_exps:
        color = _palette_color(exp.experiment_name, all_experiment_names_tuple)
        fig_dd.add_trace(
            go.Scatter(
                x=exp.equity_df["Date"],
                y=exp.equity_df["drawdown_pct"],
                mode="lines",
                name=exp.display_name,
                line={"color": color, "width": 1.5},
                fill="tozeroy",
                fillcolor=_hex_to_rgba(color, 0.1),
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


def _build_rebalance_hover_texts(exp: _ExperimentData, reb_df: pd.DataFrame) -> list[str]:
    """리밸런싱한 날마다 사유를 적은 hover 문구를 만든다.

    매매법이 여럿이면 장부의 매매법별 사유를 쓴다 — equity 의 사유는 그날 리밸런싱한 매매법 중 설정 순서상
    첫 매매법의 사유 하나라, 같은 날 다른 매매법이 한 일을 가린다. 매매법이 하나면 장부 = 계좌라 equity 의 사유가 곧 그 사유다.

    Args:
        exp: 실험 데이터
        reb_df: equity_df 에서 리밸런싱한 날의 행

    Returns:
        reb_df 의 행 순서대로 만든 hover 문구
    """
    days = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in reb_df["Date"]]
    if exp.ledger_df is None:
        return [
            f"{day}<br>리밸런싱 ({_REBALANCE_REASON_LABELS[reason]})"
            for day, reason in zip(days, reb_df["rebalance_reason"], strict=True)
        ]

    names = _method_display_names(exp.summary)
    reasons_by_date: dict[pd.Timestamp, list[str]] = {}
    for row in exp.ledger_df[exp.ledger_df["rebalanced"]].itertuples(index=False):
        line = f"{names[str(row.method_id)]}: {_REBALANCE_REASON_LABELS[str(row.rebalance_reason)]}"
        reasons_by_date.setdefault(pd.Timestamp(row.Date), []).append(line)
    return [
        "<br>".join([f"{day}<br>리밸런싱", *reasons_by_date[pd.Timestamp(d)]])
        for day, d in zip(days, reb_df["Date"], strict=True)
    ]


def _render_experiment_tab(exp: _ExperimentData) -> None:
    """개별 실험 탭 — 요약·에쿼티·비중 추이·거래·시그널을 상세 표시한다."""

    ps: dict[str, Any] = exp.summary["portfolio_summary"]
    per_asset: list[dict[str, Any]] = exp.summary["per_asset"]

    # ---- 요약 지표 ----
    st.subheader("요약 지표")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("CAGR", f"{ps['cagr']}%")
    col2.metric("MDD", f"{ps['mdd']}%")
    col3.metric("Calmar", str(ps["calmar"]))
    col4.metric("Sharpe", str(ps["sharpe_ratio"]))
    col5.metric("Sortino", str(ps["sortino_ratio"]))
    col6.metric("총 수익률", f"{ps['total_return_pct']}%")

    # 자산별 목표 비중
    asset_cols = st.columns(len(per_asset))
    for col, asset_info in zip(asset_cols, per_asset, strict=False):
        weight_pct = round(float(asset_info["target_weight"]) * 100, 1)
        col.metric(str(asset_info["asset_id"]).upper(), f"{weight_pct}%")

    st.caption(
        f"기간: {ps['start_date']} ~ {ps['end_date']} "
        f"| 초기 자본: {int(ps['initial_capital']):,}원 "
        f"| 최종 자본: {int(ps['final_capital']):,}원"
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
    reb_df = exp.equity_df[exp.equity_df["rebalanced"]]
    if not reb_df.empty:
        fig.add_trace(
            go.Scatter(
                x=reb_df["Date"],
                y=reb_df["equity"],
                mode="markers",
                name="리밸런싱",
                marker={"symbol": "circle", "color": "orange", "size": 4, "opacity": 0.6},
                text=_build_rebalance_hover_texts(exp, reb_df),
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

        cash_weight = exp.equity_df["cash"] / exp.equity_df["equity"]

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
            fill_color = _hex_to_rgba(_palette_color(asset_id, weight_asset_ids_tuple), 0.6)

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
        asset_meta = next(
            (a for a in per_asset if a["asset_id"] == selected_signal_asset),
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

    # ---- 신규 섹션: 월별 수익률 히트맵 ----
    st.divider()
    _render_monthly_returns_section(exp)

    # ---- 신규 섹션: 자산별 수익 기여도 ----
    st.divider()
    _render_contribution_section(exp)

    # ---- 매매법이 여럿인 실험: 매매법별 손익 ----
    if exp.ledger_df is not None:
        st.divider()
        _render_method_section(exp)


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
            upper_val = row.upper_band
            if pd.notna(upper_val):
                cv["upper"] = f"{float(upper_val):.2f}"
        if has_lower_band:
            lower_val = row.lower_band
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
    """해당 자산의 신호 거래에서 Buy/Sell 마커를 생성한다.

    리밸런싱 거래(`trade_type == "rebalance"`)는 그리지 않는다 — 비중을 맞추는 부분 매매라
    화살표로 그리면 매수 후 보유 자산에도 Sell 이 줄지어 나온다(리밸런싱일은 에쿼티 차트 마커가 보인다).
    Buy 마커에는 가격을 적지 않는다 — trades 의 entry_price 는 체결가가 아니라 매도 시점 평균 단가다.

    Args:
        trades_df: 포트폴리오 전체 거래 내역 (asset_id · trade_type 컬럼 포함)
        asset_id: 마커를 생성할 자산 ID
        open_position: summary.per_asset[asset_id].open_position. `None`이면 미청산 없음.
            있으면 그 진입일의 Buy 마커를 "Buy (보유중)" 으로 표시한다

    Returns:
        시간 순 정렬된 마커 리스트.
    """
    # 분할 매도 시 같은 진입일이 여러 행에 반복되므로 Buy 마커는 진입일당 하나만 둔다
    buy_markers: dict[str, dict[str, object]] = {}
    sell_markers: list[dict[str, object]] = []

    def buy_marker(entry_key: str) -> dict[str, object]:
        return buy_markers.setdefault(
            entry_key,
            {
                "time": entry_key,
                "position": "belowBar",
                "color": _COLOR_BUY_MARKER,
                "shape": "arrowUp",
                "text": "Buy",
                "size": 2,
            },
        )

    signal_trades = trades_df[(trades_df["asset_id"] == asset_id) & (trades_df["trade_type"] == TRADE_TYPE_SIGNAL)]
    for trade in signal_trades.itertuples(index=False):
        buy_marker(pd.Timestamp(trade.entry_date).strftime("%Y-%m-%d"))
        sell_markers.append(
            {
                "time": pd.Timestamp(trade.exit_date).strftime("%Y-%m-%d"),
                "position": "aboveBar",
                "color": _COLOR_SELL_MARKER,
                "shape": "arrowDown",
                "text": f"Sell {float(trade.pnl_pct) * 100:+.1f}%",
                "size": 2,
            }
        )

    if open_position is not None:
        entry_key = pd.Timestamp(str(open_position["entry_date"])).strftime("%Y-%m-%d")
        buy_marker(entry_key)["text"] = "Buy (보유중)"

    # lightweight-charts는 마커가 시간순 정렬되어야 정상 표시된다
    markers = [*buy_markers.values(), *sell_markers]
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
        open_position: 미청산 포지션 정보. 존재 시 "Buy (보유중)" 마커 추가.
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
