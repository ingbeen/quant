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
from pathlib import Path
from typing import Any

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
from qbt.backtest.dashboard_charts import (
    build_monthly_heatmap,
    build_price_pane,
    build_trade_markers,
    chart_component_args,
)
from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS

# ============================================================
# 로컬 상수 (이 파일에서만 사용)
# ============================================================

# --- 차트 높이 ---
_CHART_HEIGHT = 500
_SUB_CHART_HEIGHT = 300

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


# 캐시 로더의 mtime 은 쓰지 않고 캐시 키로만 둔다 — 러너가 파일을 다시 만들면 새로 읽는다


@st.cache_data
def _load_equity_csv(path: Path, mtime: float) -> pd.DataFrame:
    """equity.csv를 로드한다 (Date 열 datetime 변환, 빈 리밸런싱 사유는 빈 문자열)."""
    df = pd.read_csv(path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    df["rebalance_reason"] = df["rebalance_reason"].fillna("")
    return df


@st.cache_data
def _load_trades_csv(path: Path, mtime: float) -> pd.DataFrame:
    """trades.csv를 로드한다 (entry_date / exit_date datetime 변환)."""
    df = pd.read_csv(path)
    for col in ("entry_date", "exit_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


@st.cache_data
def _load_summary_json(path: Path, mtime: float) -> dict[str, Any]:
    """summary.json을 로드한다."""
    with path.open(encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
    return result


@st.cache_data
def _load_signal_csv(path: Path, mtime: float) -> pd.DataFrame:
    """signal_{asset_id}.csv를 로드한다 (Date 열 datetime 변환)."""
    df = pd.read_csv(path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


@st.cache_data
def _load_ledger_csv(path: Path, mtime: float) -> pd.DataFrame:
    """ledger.csv(매매법별 장부)를 로드한다 (Date 열 datetime 변환, 빈 리밸런싱 사유는 빈 문자열)."""
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
    summary_path = experiment_dir / SUMMARY_FILENAME
    equity_path = experiment_dir / EQUITY_FILENAME
    trades_path = experiment_dir / TRADES_FILENAME
    summary = _load_summary_json(summary_path, summary_path.stat().st_mtime)
    equity_df = _load_equity_csv(equity_path, equity_path.stat().st_mtime)
    trades_df = _load_trades_csv(trades_path, trades_path.stat().st_mtime)

    # signal_{asset_id}.csv 탐색 및 로드
    signal_dfs: dict[str, pd.DataFrame] = {}
    for signal_path in sorted(experiment_dir.glob(f"{PORTFOLIO_SIGNAL_PREFIX}*.csv")):
        # "signal_qqq.csv" → asset_id = "qqq"
        asset_id = signal_path.stem.removeprefix(PORTFOLIO_SIGNAL_PREFIX)
        signal_dfs[asset_id] = _load_signal_csv(signal_path, signal_path.stat().st_mtime)

    display_name: str = summary["display_name"]
    # 장부는 매매법이 여럿인 실험에만 있다
    ledger_path = experiment_dir / LEDGER_FILENAME
    ledger_df = _load_ledger_csv(ledger_path, ledger_path.stat().st_mtime) if ledger_path.exists() else None

    return _ExperimentData(
        experiment_name=experiment_dir.name,
        display_name=display_name,
        result_dir=experiment_dir,
        equity_df=equity_df,
        trades_df=trades_df,
        summary=summary,
        signal_dfs=signal_dfs,
        ledger_df=ledger_df,
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
# 월별 수익률 히트맵 (Monthly Returns)
# ============================================================


def _render_monthly_returns_section(exp: _ExperimentData) -> None:
    """월별 수익률 히트맵 — 수익률은 러너가 summary.json 에 저장한 값이다."""
    st.subheader("월별 수익률")
    fig = build_monthly_heatmap(exp.summary["monthly_returns"], exp.summary["yearly_returns"])
    st.plotly_chart(fig, width="stretch", key=f"monthly_heatmap_{exp.experiment_name}")


# ============================================================
# 자산별 수익 기여도 (Asset Contribution)
# ============================================================


def _render_contribution_section(exp: _ExperimentData) -> None:
    """자산별 수익 기여도를 실현+미실현 손익 기반으로 표시한다.

    총 기여도 = 누적 실현손익 + 미실현손익이며, 엔진(`build_combined_equity`)이
    `{asset_id}_contribution` 컬럼으로 계산해 equity CSV에 저장한다.
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

    # ---- 월별 수익률 히트맵 ----
    st.divider()
    _render_monthly_returns_section(exp)

    # ---- 자산별 수익 기여도 ----
    st.divider()
    _render_contribution_section(exp)

    # ---- 매매법이 여럿인 실험: 매매법별 손익 ----
    if exp.ledger_df is not None:
        st.divider()
        _render_method_section(exp)


# ============================================================
# 시그널 차트 (lightweight-charts 캔들스틱)
# ============================================================


def _render_signal_chart(
    signal_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    asset_id: str,
    experiment_name: str,
    open_position: dict[str, Any] | None = None,
) -> None:
    """한 자산의 캔들 + 이동평균 · 밴드 + 신호 거래 마커.

    밴드는 시그널 CSV 에서 읽는다(버퍼존 자산만 있다 — 에쿼티는 계좌 단위라 자산 차트에 넣지 않는다).
    리밸런싱 거래는 그리지 않는다 — 비중을 맞추는 부분 매매라 화살표로 그리면 매수 후 보유 자산에도
    Sell 이 줄지어 나온다(리밸런싱일은 에쿼티 차트 마커가 보인다).

    Args:
        signal_df: 시그널 데이터 (OHLC + ma_{N} + 4종 % + 버퍼존 자산이면 밴드)
        trades_df: 포트폴리오 전체 거래 내역 (asset_id · trade_type 컬럼 포함)
        asset_id: 표시할 자산 ID
        experiment_name: 실험명 (Streamlit 위젯 key 중복 방지용)
        open_position: summary.per_asset 의 그 자산 open_position. 있으면 그 진입일에 "Buy (보유중)" 마커
    """
    signal_trades = trades_df[(trades_df["asset_id"] == asset_id) & (trades_df["trade_type"] == TRADE_TYPE_SIGNAL)]
    markers = build_trade_markers(
        signal_trades,
        open_entry_date=None if open_position is None else str(open_position["entry_date"]),
    )
    pane = build_price_pane(signal_df, signal_df, markers, title=f"{asset_id.upper()} 시그널 차트")
    lightweight_charts_v5_component(
        **chart_component_args(
            [pane],
            name=f"portfolio_signal_{experiment_name}_{asset_id}",
            key=f"signal_chart_{experiment_name}_{asset_id}",
        )
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
