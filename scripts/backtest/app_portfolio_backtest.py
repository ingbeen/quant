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

import numpy as np
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
    "shares": "수량",
    "pnl": "손익금액",
    "pnl_pct": "손익률",
    "holding_days": "보유기간(일)",
    "pre_shares": "체결전수량",
    "post_shares": "체결후수량",
    "order_amount": "체결금액",
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


def _shares_columns(equity_df: pd.DataFrame) -> list[str]:
    """equity_df에서 {asset_id}_shares 컬럼명 리스트를 반환한다."""
    return [c for c in equity_df.columns if c.endswith("_shares")]


def _has_holdings_data(equity_df: pd.DataFrame) -> bool:
    """equity_df에 보유 상세 데이터(shares, avg_price)가 존재하는지 확인한다."""
    return len(_shares_columns(equity_df)) > 0


def _get_asset_ids_from_equity(equity_df: pd.DataFrame) -> list[str]:
    """equity_df의 weight 컬럼에서 자산 ID 리스트를 추출한다."""
    return [_asset_id_from_weight_col(c) for c in _weight_columns(equity_df)]


# ============================================================
# 신규 섹션: 포트폴리오 보유 현황 (My Holdings)
# ============================================================


@st.fragment
def _render_holdings_section(exp: _ExperimentData) -> None:
    """특정 날짜의 포트폴리오 보유 현황을 표시한다.

    거래일 전용 select_slider로 선택한 일자의 종목별 보유수, 평균매수가,
    현재가, 평가금액, 비중, 수익률을 보여준다.
    @st.fragment로 격리되어 날짜 변경 시 이 섹션만 재렌더링된다.
    """
    st.subheader("포트폴리오 보유 현황")

    if not _has_holdings_data(exp.equity_df):
        st.info("보유 상세 데이터가 없습니다. run_portfolio_backtest.py를 재실행하세요.")
        return

    equity_df = exp.equity_df
    ps = _extract_portfolio_summary(exp.summary)
    per_asset = _extract_per_asset(exp.summary)
    initial_capital = int(ps.get("initial_capital", 0))

    # 거래일 전용 선택 슬라이더 (equity_df에 존재하는 날짜만 옵션으로 제공)
    trading_dates: list[date] = pd.to_datetime(equity_df["Date"]).dt.date.tolist()

    selected_date = st.select_slider(
        "조회 날짜",
        options=trading_dates,
        value=trading_dates[-1],
        key=f"holdings_date_{exp.experiment_name}",
    )

    # 선택 날짜의 데이터 행 (select_slider이므로 항상 유효한 거래일)
    date_mask = pd.to_datetime(equity_df["Date"]).dt.date == selected_date
    row = equity_df[date_mask.values].iloc[0]
    total_equity = int(row["equity"])
    cash = int(row["cash"])
    total_pnl = total_equity - initial_capital
    total_return_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0.0

    # 요약 카드
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 평가금액", f"{total_equity:,}원", f"{total_return_pct:+.2f}%")
    col2.metric("투자원금", f"{initial_capital:,}원")
    col3.metric("평가손익", f"{total_pnl:+,}원")
    col4.metric("현금 잔고", f"{cash:,}원", f"{cash / total_equity * 100:.1f}%" if total_equity > 0 else "0%")

    # 보유 종목 테이블
    asset_ids = _get_asset_ids_from_equity(equity_df)
    target_weights: dict[str, float] = {}
    for pa in per_asset:
        aid = str(pa.get("asset_id", ""))
        target_weights[aid] = float(pa.get("target_weight", 0))

    holdings_rows: list[dict[str, Any]] = []
    for asset_id in asset_ids:
        shares_col = f"{asset_id}_shares"
        avg_price_col = f"{asset_id}_avg_price"
        value_col = f"{asset_id}_value"
        weight_col = f"{asset_id}_weight"

        shares = int(row.get(shares_col, 0)) if shares_col in equity_df.columns else 0
        avg_price = float(row.get(avg_price_col, 0)) if avg_price_col in equity_df.columns else 0.0
        value = int(row.get(value_col, 0)) if value_col in equity_df.columns else 0
        weight = float(row.get(weight_col, 0)) if weight_col in equity_df.columns else 0.0

        # 현재가 = 평가액 / 주수 (0 방지)
        current_price = value / shares if shares > 0 else 0.0
        # 종목별 수익률
        asset_return_pct = ((current_price / avg_price - 1) * 100) if avg_price > 0 and shares > 0 else 0.0

        holdings_rows.append(
            {
                "종목": asset_id.upper(),
                "보유수": shares,
                "평균매수가": f"${avg_price:.2f}" if avg_price > 0 else "-",
                "현재가": f"${current_price:.2f}" if shares > 0 else "-",
                "평가금액": f"{value:,}원",
                "실제비중": f"{weight * 100:.1f}%",
                "목표비중": f"{target_weights.get(asset_id, 0) * 100:.1f}%",
                "수익률": f"{asset_return_pct:+.2f}%" if shares > 0 else "-",
            }
        )

    if holdings_rows:
        st.dataframe(pd.DataFrame(holdings_rows), hide_index=True, width="stretch")

    # 목표 비중 vs 실제 비중 이중 도넛 차트
    actual_labels = [r["종목"] for r in holdings_rows] + ["현금"]
    actual_values = [float(row.get(f"{aid}_weight", 0)) * 100 for aid in asset_ids] + [
        cash / total_equity * 100 if total_equity > 0 else 0
    ]
    target_labels = [aid.upper() for aid in asset_ids] + ["현금"]
    target_values = [target_weights.get(aid, 0) * 100 for aid in asset_ids] + [
        max(0, 100 - sum(target_weights.get(aid, 0) * 100 for aid in asset_ids))
    ]
    actual_colors = [_get_asset_color(aid) for aid in asset_ids] + ["#b4b4b4"]
    target_colors = actual_colors

    fig_donut = make_subplots(
        rows=1,
        cols=2,
        specs=[[{"type": "domain"}, {"type": "domain"}]],
        subplot_titles=["실제 비중", "목표 비중"],
    )
    fig_donut.add_trace(
        go.Pie(
            labels=actual_labels,
            values=actual_values,
            hole=0.5,
            marker={"colors": actual_colors},
            textinfo="label+percent",
            hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig_donut.add_trace(
        go.Pie(
            labels=target_labels,
            values=target_values,
            hole=0.5,
            marker={"colors": target_colors},
            textinfo="label+percent",
            hovertemplate="%{label}: %{value:.1f}%<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig_donut.update_layout(height=_SMALL_CHART_HEIGHT, showlegend=False)
    st.plotly_chart(fig_donut, width="stretch", key=f"donut_{exp.experiment_name}")


# ============================================================
# 신규 섹션: 체결 전후 비교 (Before/After Execution)
# ============================================================


def _render_execution_comparison_section(exp: _ExperimentData) -> None:
    """체결 발생일의 자산별 전후 변화를 비교한다.

    사전 생성된 execution_comparison.csv를 로드하여 긴 표 형태로 표시한다.
    데이터가 많으므로 기본 숨김(expander collapsed) 상태로 제공한다.
    """
    with st.expander("체결 전후 비교", expanded=False):
        experiment_dir = PORTFOLIO_RESULTS_DIR / exp.experiment_name
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

            # 리밸런싱 사유 변환
            reason = str(row.get("rebalance_reason", ""))
            if reason == "nan":
                reason = ""
            reason_text = ""
            if reason == "monthly":
                reason_text = "월초 정기"
            elif reason == "daily":
                reason_text = "긴급"

            # 거래 내역 (NaN 처리)
            trade_info = str(row.get("trade_info", ""))
            if trade_info == "nan":
                trade_info = ""

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
                    "거래 내역": trade_info if trade_info else "-",
                }
            )

        st.caption(f"총 {len(comparison_df['date'].unique())}개 체결일")
        st.dataframe(pd.DataFrame(display_rows), hide_index=True, width="stretch")


# ============================================================
# 신규 섹션: 리밸런싱 히스토리 (Rebalancing Log)
# ============================================================


def _render_rebalancing_history_section(exp: _ExperimentData) -> None:
    """리밸런싱 이벤트 타임라인을 표시한다."""
    st.subheader("리밸런싱 히스토리")

    equity_df = exp.equity_df
    trades_df = exp.trades_df

    if "rebalanced" not in equity_df.columns:
        st.info("리밸런싱 데이터가 없습니다.")
        return

    reb_df = equity_df[equity_df["rebalanced"] == True].copy()  # noqa: E712
    if reb_df.empty:
        st.info("리밸런싱이 발생하지 않았습니다.")
        return

    # 기간 정보
    total_days = len(equity_df)
    reb_count = len(reb_df)
    months_approx = total_days / 21  # 영업일 기준 대략 월수
    freq_text = f"{months_approx / reb_count:.1f}개월당 1회" if reb_count > 0 else "N/A"

    st.caption(f"총 {reb_count}회 리밸런싱 | 평균 빈도: {freq_text}")

    # 리밸런싱 이벤트 테이블
    has_reason = "rebalance_reason" in equity_df.columns
    asset_ids = _get_asset_ids_from_equity(equity_df)
    per_asset = _extract_per_asset(exp.summary)
    target_weights: dict[str, float] = {}
    for pa in per_asset:
        target_weights[str(pa.get("asset_id", ""))] = float(pa.get("target_weight", 0))

    reb_rows: list[dict[str, Any]] = []
    for _, row in reb_df.iterrows():
        d = row["Date"]
        date_str = pd.Timestamp(d).strftime("%Y-%m-%d") if pd.notna(d) else "N/A"

        trigger = ""
        if has_reason:
            reason = str(row.get("rebalance_reason", ""))
            trigger = "월초 정기" if reason == "monthly" else ("긴급" if reason == "daily" else "")

        # 비중 편차 사유 분석
        deviation_parts: list[str] = []
        for asset_id in asset_ids:
            weight_col = f"{asset_id}_weight"
            if weight_col in equity_df.columns:
                actual_w = float(row.get(weight_col, 0))
                target_w = target_weights.get(asset_id, 0)
                if target_w > 0:
                    deviation = abs(actual_w / target_w - 1.0)
                    if deviation > 0.08:  # 8% 이상 편차 표시
                        deviation_parts.append(f"{asset_id.upper()} {actual_w * 100:.1f}% (목표 {target_w * 100:.0f}%)")

        detail = ", ".join(deviation_parts) if deviation_parts else "-"

        # 해당 일자 리밸런싱 거래 수
        reb_trades_count = 0
        if not trades_df.empty and "exit_date" in trades_df.columns and "trade_type" in trades_df.columns:
            reb_day_trades = trades_df[(trades_df["exit_date"] == d) & (trades_df["trade_type"] == "rebalance")]
            reb_trades_count = len(reb_day_trades)

        reb_rows.append(
            {
                "리밸런싱일": date_str,
                "트리거": trigger if trigger else "-",
                "거래 수": reb_trades_count,
                "비중 편차 상세": detail,
            }
        )

    st.dataframe(pd.DataFrame(reb_rows), hide_index=True, width="stretch")

    # 리밸런싱 전후 비중 변화 차트 (최근 5건)
    recent_reb = reb_df.tail(5)
    if len(recent_reb) > 0 and _has_holdings_data(equity_df):
        st.caption("최근 리밸런싱 전후 비중 변화")
        fig_reb = go.Figure()

        for _, reb_row in recent_reb.iterrows():
            reb_idx = equity_df.index[equity_df["Date"] == reb_row["Date"]]
            if reb_idx.empty:
                continue
            idx = reb_idx[0]
            if idx == 0:
                continue

            prev_r = equity_df.iloc[idx - 1]
            curr_r = equity_df.iloc[idx]
            date_label = pd.Timestamp(reb_row["Date"]).strftime("%m/%d")

            for asset_id in asset_ids:
                weight_col = f"{asset_id}_weight"
                if weight_col not in equity_df.columns:
                    continue
                pre_w = float(prev_r.get(weight_col, 0)) * 100
                post_w = float(curr_r.get(weight_col, 0)) * 100
                color = _get_asset_color(asset_id)

                fig_reb.add_trace(
                    go.Bar(
                        x=[f"{date_label} 전", f"{date_label} 후"],
                        y=[pre_w, post_w],
                        name=asset_id.upper(),
                        marker_color=color,
                        showlegend=bool(_ == recent_reb.index[0]),
                        legendgroup=asset_id,
                        hovertemplate=f"{asset_id.upper()}: %{{y:.1f}}%<extra></extra>",
                    )
                )

        fig_reb.update_layout(
            barmode="stack",
            height=_SMALL_CHART_HEIGHT,
            yaxis_title="비중 (%)",
            yaxis={"range": [0, 100]},
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        )
        st.plotly_chart(fig_reb, width="stretch", key=f"reb_chart_{exp.experiment_name}")


# ============================================================
# 신규 섹션: 월별 수익률 히트맵 (Monthly Returns)
# ============================================================


def _render_monthly_returns_section(exp: _ExperimentData) -> None:
    """월별 수익률을 히트맵으로 표시한다."""
    st.subheader("월별 수익률")

    equity_df = exp.equity_df
    if equity_df.empty or "equity" not in equity_df.columns:
        st.info("에쿼티 데이터가 없습니다.")
        return

    # 월별 수익률 계산
    df = equity_df[["Date", "equity"]].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")

    # 월말 에쿼티 기준 수익률
    monthly = df["equity"].resample("ME").last()
    monthly_return = monthly.pct_change() * 100
    monthly_return = monthly_return.dropna()

    if monthly_return.empty:
        st.info("월별 수익률을 계산할 수 없습니다.")
        return

    # 년도 x 월 피벗
    dt_index = pd.DatetimeIndex(monthly_return.index)
    mr_df = pd.DataFrame(
        {
            "year": dt_index.year,
            "month": dt_index.month,
            "return_pct": monthly_return.values,
        }
    )

    pivot = mr_df.pivot(index="year", columns="month", values="return_pct")

    # 연간 수익률 계산 (월별 복리)
    yearly_returns: list[float] = []
    for year in pivot.index:
        monthly_vals = pivot.loc[year].dropna().values
        if len(monthly_vals) > 0:
            cumulative = np.prod(1 + monthly_vals / 100) - 1
            yearly_returns.append(cumulative * 100)
        else:
            yearly_returns.append(0.0)

    # 13열 (1~12월 + 연간)
    month_labels = ["1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]
    year_labels = [str(y) for y in pivot.index]

    # 히트맵 데이터 (NaN → None)
    z_data: list[list[float | None]] = []
    text_data: list[list[str]] = []

    for i, year in enumerate(pivot.index):
        row_z: list[float | None] = []
        row_text: list[str] = []
        for m in range(1, 13):
            val = pivot.loc[year, m] if m in pivot.columns and pd.notna(pivot.loc[year].get(m)) else None
            row_z.append(round(float(val), 2) if val is not None else None)
            row_text.append(f"{float(val):.2f}%" if val is not None else "")
        # 연간 합계
        row_z.append(round(yearly_returns[i], 2))
        row_text.append(f"{yearly_returns[i]:.2f}%")
        z_data.append(row_z)
        text_data.append(row_text)

    x_labels = month_labels + ["연간"]

    # 색상 범위 (대칭)
    all_vals = [v for row in z_data for v in row if v is not None]
    max_abs = max(abs(min(all_vals)), abs(max(all_vals))) if all_vals else 10

    fig_heatmap = go.Figure(
        data=go.Heatmap(
            z=z_data,
            x=x_labels,
            y=year_labels,
            text=text_data,
            texttemplate="%{text}",
            textfont={"size": 11},
            colorscale=[
                [0, "rgb(239, 83, 80)"],
                [0.5, "rgb(255, 255, 255)"],
                [1, "rgb(38, 166, 154)"],
            ],
            zmin=-max_abs,
            zmax=max_abs,
            hovertemplate="%{y}년 %{x}: %{text}<extra></extra>",
            colorbar={"title": "수익률 (%)"},
        )
    )

    fig_heatmap.update_layout(
        height=max(_SMALL_CHART_HEIGHT, len(year_labels) * 40 + 100),
        xaxis={"side": "top"},
        yaxis={"autorange": "reversed"},
    )
    st.plotly_chart(fig_heatmap, width="stretch", key=f"monthly_heatmap_{exp.experiment_name}")


# ============================================================
# 신규 섹션: 자산별 수익 기여도 (Asset Contribution)
# ============================================================


def _render_contribution_section(exp: _ExperimentData) -> None:
    """자산별 수익 기여도를 실현+미실현 손익 기반으로 표시한다.

    총 기여도 = 누적 실현손익 + 미실현손익.
    매도 후에도 실현손익이 유지되어 자산별 기여 이력이 끊기지 않는다.
    신규 컬럼(_realized_pnl, _unrealized_pnl)이 없으면 기존 방식(value 기반)으로 fallback.
    """
    st.subheader("자산별 수익 기여도")

    equity_df = exp.equity_df
    if equity_df.empty:
        st.info("에쿼티 데이터가 없습니다.")
        return

    asset_ids = _get_asset_ids_from_equity(equity_df)

    # PnL 컬럼 존재 여부 확인 (graceful fallback)
    has_pnl_cols = all(
        f"{aid}_realized_pnl" in equity_df.columns and f"{aid}_unrealized_pnl" in equity_df.columns for aid in asset_ids
    )

    if not has_pnl_cols:
        _render_contribution_section_legacy(exp, asset_ids)
        return

    # 총 기여도 = realized_pnl + unrealized_pnl (자산별)
    df = equity_df[["Date"]].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    contrib_cols: list[str] = []
    for aid in asset_ids:
        col = f"{aid}_contribution"
        df[col] = equity_df[f"{aid}_realized_pnl"].to_numpy() + equity_df[f"{aid}_unrealized_pnl"].to_numpy()
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

    for aid in asset_ids:
        col = f"{aid}_contribution"
        if col not in quarterly_diff.columns:
            continue
        color = _get_asset_color(aid)
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
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig_contrib, width="stretch", key=f"contrib_bar_{exp.experiment_name}")

    # 누적 기여도 면적 차트 (실현+미실현 손익)
    fig_cum = go.Figure()
    for aid in asset_ids:
        col = f"{aid}_contribution"
        if col not in df.columns:
            continue
        color = _get_asset_color(aid)
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        fig_cum.add_trace(
            go.Scatter(
                x=df.index,
                y=df[col],
                mode="lines",
                name=aid.upper(),
                stackgroup="one",
                line={"width": 0},
                fillcolor=f"rgba({r}, {g}, {b}, 0.6)",
                hovertemplate=f"{aid.upper()}: %{{y:+,.0f}}원<extra></extra>",
            )
        )

    fig_cum.update_layout(
        title="누적 자산별 기여도 (실현+미실현 손익)",
        height=_SUB_CHART_HEIGHT,
        xaxis_title="날짜",
        yaxis_title="누적 기여 금액 (원)",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig_cum, width="stretch", key=f"contrib_cum_{exp.experiment_name}")

    # 실현/미실현 분해 차트 (자산별 마지막 값 기준 수평 바)
    final_row = equity_df.iloc[-1]
    realized_vals = [float(final_row.get(f"{aid}_realized_pnl", 0)) for aid in asset_ids]
    unrealized_vals = [float(final_row.get(f"{aid}_unrealized_pnl", 0)) for aid in asset_ids]
    labels = [aid.upper() for aid in asset_ids]

    fig_decomp = go.Figure()
    fig_decomp.add_trace(
        go.Bar(
            y=labels,
            x=realized_vals,
            name="실현손익",
            orientation="h",
            marker_color="rgba(55, 128, 191, 0.8)",
            hovertemplate="%{y}: %{x:+,.0f}원<extra>실현손익</extra>",
        )
    )
    fig_decomp.add_trace(
        go.Bar(
            y=labels,
            x=unrealized_vals,
            name="미실현손익",
            orientation="h",
            marker_color="rgba(219, 64, 82, 0.8)",
            hovertemplate="%{y}: %{x:+,.0f}원<extra>미실현손익</extra>",
        )
    )
    fig_decomp.update_layout(
        title="자산별 손익 분해 (최종일 기준)",
        barmode="stack",
        height=max(250, len(asset_ids) * 60 + 100),
        xaxis_title="손익 (원)",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig_decomp, width="stretch", key=f"contrib_decomp_{exp.experiment_name}")


def _render_contribution_section_legacy(exp: _ExperimentData, asset_ids: list[str]) -> None:
    """기존 방식(value 기반) 자산별 수익 기여도 fallback."""
    equity_df = exp.equity_df
    value_cols = [f"{aid}_value" for aid in asset_ids if f"{aid}_value" in equity_df.columns]

    if not value_cols:
        st.info("자산별 평가액 데이터가 없습니다.")
        return

    st.caption("(PnL 컬럼 미존재 -- 기존 방식으로 표시)")

    df = equity_df[["Date"] + value_cols].copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date")

    cumulative = df[value_cols].copy()
    for col in value_cols:
        cumulative[col] = cumulative[col] - cumulative[col].iloc[0]

    fig_cum = go.Figure()
    for aid in asset_ids:
        col = f"{aid}_value"
        if col not in cumulative.columns:
            continue
        color = _get_asset_color(aid)
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)

        fig_cum.add_trace(
            go.Scatter(
                x=cumulative.index,
                y=cumulative[col],
                mode="lines",
                name=aid.upper(),
                stackgroup="one",
                line={"width": 0},
                fillcolor=f"rgba({r}, {g}, {b}, 0.6)",
                hovertemplate=f"{aid.upper()}: %{{y:+,.0f}}원<extra></extra>",
            )
        )

    fig_cum.update_layout(
        title="누적 자산별 기여도 (초기 대비 평가액 변동)",
        height=_SUB_CHART_HEIGHT,
        xaxis_title="날짜",
        yaxis_title="누적 기여 금액 (원)",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig_cum, width="stretch", key=f"contrib_cum_legacy_{exp.experiment_name}")


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

        # 목표 비중 수평선 오버레이
        target_weights_map: dict[str, float] = {}
        for pa_info in per_asset:
            aid = str(pa_info.get("asset_id", ""))
            tw = float(pa_info.get("target_weight", 0))
            target_weights_map[aid] = tw
        for col in weight_cols:
            asset_id = _asset_id_from_weight_col(col)
            tw = target_weights_map.get(asset_id, 0)
            if tw > 0:
                color = _get_asset_color(asset_id)
                fig_weight.add_hline(
                    y=tw * 100,
                    line_dash="dash",
                    line_color=color,
                    line_width=1,
                    opacity=0.5,
                    annotation_text=f"{asset_id.upper()} 목표",
                    annotation_position="right",
                    annotation_font_size=9,
                    annotation_font_color=color,
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

    # ---- 신규 섹션: 포트폴리오 보유 현황 ----
    st.divider()
    _render_holdings_section(exp)

    # ---- 신규 섹션: 체결 전후 비교 ----
    st.divider()
    _render_execution_comparison_section(exp)

    # ---- 신규 섹션: 리밸런싱 히스토리 ----
    st.divider()
    _render_rebalancing_history_section(exp)

    # ---- 신규 섹션: 월별 수익률 히트맵 ----
    st.divider()
    _render_monthly_returns_section(exp)

    # ---- 신규 섹션: 자산별 수익 기여도 ----
    st.divider()
    _render_contribution_section(exp)


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

    # lightweight-charts는 마커가 시간순 정렬되어야 정상 표시된다
    markers.sort(key=lambda m: str(m["time"]))
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
