"""포트폴리오 디버그 대시보드

포트폴리오 백테스트의 일별 엔진 내부 상태를 시각적으로 탐색한다.
사전 생성된 state_log.csv + equity.csv + trades.csv를 읽기만 하며,
앱 내 연산은 최소화한다.

선행 스크립트:
    poetry run python scripts/backtest/run_portfolio_backtest.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_portfolio_debug.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from qbt.backtest.constants import DEFAULT_PORTFOLIO_EXPERIMENTS
from qbt.common_constants import PORTFOLIO_RESULTS_DIR

# ============================================================
# 로컬 상수
# ============================================================

_CHART_HEIGHT = 500
_SUB_CHART_HEIGHT = 300

_ASSET_COLORS: dict[str, str] = {
    "qqq": "#1f77b4",
    "tqqq": "#ff7f0e",
    "spy": "#2ca02c",
    "gld": "#d62728",
    "tlt": "#9467bd",
    "iwm": "#8c564b",
    "efa": "#e377c2",
    "eem": "#7f7f7f",
}
_COLOR_FALLBACK = "#888888"

_SIGNAL_LABELS: dict[str, str] = {
    "buy": "매수 시그널",
    "sell": "매도 시그널",
    "hold": "보유 유지",
}

_INTENT_LABELS: dict[str, str] = {
    "EXIT_ALL": "전량 청산",
    "ENTER_TO_TARGET": "신규 진입",
    "REDUCE_TO_TARGET": "비중 축소",
    "INCREASE_TO_TARGET": "비중 확대",
}


# ============================================================
# 데이터 로딩
# ============================================================


def _discover_experiments() -> list[Path]:
    """활성 실험 중 state_log.csv가 있는 폴더를 탐색한다."""
    if not PORTFOLIO_RESULTS_DIR.exists():
        return []
    result: list[Path] = []
    for sub_dir in sorted(PORTFOLIO_RESULTS_DIR.iterdir()):
        if sub_dir.is_dir() and (sub_dir / "state_log.csv").exists() and sub_dir.name in DEFAULT_PORTFOLIO_EXPERIMENTS:
            result.append(sub_dir)
    return result


@st.cache_data
def _load_state_log(dir_str: str) -> pd.DataFrame:
    """state_log.csv를 로드한다."""
    df = pd.read_csv(Path(dir_str) / "state_log.csv")
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


@st.cache_data
def _load_equity(dir_str: str) -> pd.DataFrame:
    """equity.csv를 로드한다."""
    df = pd.read_csv(Path(dir_str) / "equity.csv")
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


@st.cache_data
def _load_summary(dir_str: str) -> dict[str, Any]:
    """summary.json을 로드한다."""
    path = Path(dir_str) / "summary.json"
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


def _get_asset_ids(state_log_df: pd.DataFrame) -> list[str]:
    """state_log_df에서 자산 ID 목록을 추출한다."""
    return [c.removesuffix("_close") for c in state_log_df.columns if c.endswith("_close")]


def _get_asset_color(asset_id: str) -> str:
    """자산 색상을 반환한다."""
    return _ASSET_COLORS.get(asset_id, _COLOR_FALLBACK)


# ============================================================
# 뷰 1: 일별 상태 네비게이터
# ============================================================


@st.fragment
def _render_daily_navigator(
    state_log_df: pd.DataFrame,
    asset_ids: list[str],
    summary: dict[str, Any],
    exp_name: str,
) -> None:
    """select_slider로 거래일을 이동하며 해당일의 상세 상태를 표시한다."""
    st.subheader("일별 상태 네비게이터")

    trading_dates: list[date] = pd.to_datetime(state_log_df["Date"]).dt.date.tolist()
    selected_date = st.select_slider(
        "거래일 선택",
        options=trading_dates,
        value=trading_dates[-1],
        key=f"debug_date_{exp_name}",
    )

    date_mask = pd.to_datetime(state_log_df["Date"]).dt.date == selected_date
    row = state_log_df[date_mask.values].iloc[0]

    # 기본 정보
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("에쿼티", f"{int(row['equity']):,}원")
    col2.metric("현금", f"{int(row['cash']):,}원")
    reb_text = ""
    if row.get("rebalanced"):
        reason = str(row.get("rebalance_reason", ""))
        reb_text = "월초 정기" if reason == "monthly" else ("긴급" if reason == "daily" else "예")
    col3.metric("리밸런싱", reb_text if reb_text else "없음")
    col4.metric("월 첫 거래일", "예" if row.get("is_month_start") else "아니오")

    # 자산별 카드
    target_weights: dict[str, float] = {}
    for pa in summary.get("per_asset", []):
        target_weights[str(pa.get("asset_id", ""))] = float(pa.get("target_weight", 0))

    for aid in asset_ids:
        color = _get_asset_color(aid)
        signal_today = str(row.get(f"{aid}_signal_today", "hold"))
        pending = str(row.get(f"{aid}_pending_intent", ""))
        executed = str(row.get(f"{aid}_executed_intent", ""))
        shares = int(row.get(f"{aid}_shares", 0))
        weight = float(row.get(f"{aid}_weight", 0))
        close = float(row.get(f"{aid}_close", 0))
        tw = target_weights.get(aid, 0)

        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.markdown(f"**:{color[1:]}[{aid.upper()}]**")
            c2.metric("보유", f"{shares:,}주")
            c3.metric("비중", f"{weight * 100:.1f}% (목표 {tw * 100:.0f}%)")
            c4.metric("종가", f"${close:.2f}")

            # 시그널/체결/pending 요약
            parts: list[str] = []
            if signal_today != "hold":
                parts.append(f"시그널: {_SIGNAL_LABELS.get(signal_today, signal_today)}")
            if executed and executed != "nan":
                exec_side = str(row.get(f"{aid}_exec_side", ""))
                exec_shares = int(row.get(f"{aid}_exec_shares", 0))
                exec_price = float(row.get(f"{aid}_exec_price", 0))
                label = _INTENT_LABELS.get(executed, executed)
                parts.append(f"체결: {label} ({exec_side} {exec_shares}주 @${exec_price:.2f})")
            if pending and pending != "nan":
                label = _INTENT_LABELS.get(pending, pending)
                parts.append(f"익일 예정: {label}")

            c5.caption(" | ".join(parts) if parts else "변동 없음")


# ============================================================
# 뷰 2: 동기화 시계열 차트
# ============================================================


def _render_synchronized_charts(
    state_log_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    asset_ids: list[str],
    summary: dict[str, Any],
    exp_name: str,
) -> None:
    """에쿼티/비중/현금/주수 4행 서브플롯을 동기화하여 표시한다."""
    st.subheader("동기화 시계열 차트")

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.35, 0.25, 0.15, 0.25],
        vertical_spacing=0.03,
        subplot_titles=["에쿼티 (원)", "자산별 비중 (%)", "현금 잔고 (원)", "자산별 주수"],
    )

    dates = equity_df["Date"]

    # (1) 에쿼티 곡선 + 리밸런싱 마커
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=equity_df["equity"],
            mode="lines",
            name="에쿼티",
            line={"color": "rgba(33, 150, 243, 1)", "width": 2},
            hovertemplate="%{x|%Y-%m-%d}<br>에쿼티: %{y:,.0f}원<extra></extra>",
        ),
        row=1,
        col=1,
    )

    if "rebalanced" in equity_df.columns:
        reb = equity_df[equity_df["rebalanced"] == True]  # noqa: E712
        if not reb.empty:
            fig.add_trace(
                go.Scatter(
                    x=reb["Date"],
                    y=reb["equity"],
                    mode="markers",
                    name="리밸런싱",
                    marker={"symbol": "diamond", "color": "orange", "size": 6},
                    hovertemplate="%{x|%Y-%m-%d}<br>리밸런싱<extra></extra>",
                ),
                row=1,
                col=1,
            )

    # 체결일 마커 (state_log 기반)
    for aid in asset_ids:
        exec_col = f"{aid}_executed_intent"
        if exec_col not in state_log_df.columns:
            continue
        exec_rows = state_log_df[state_log_df[exec_col].astype(str).isin(["ENTER_TO_TARGET", "EXIT_ALL"])]
        if exec_rows.empty:
            continue
        color = _get_asset_color(aid)
        for _, er in exec_rows.iterrows():
            intent = str(er[exec_col])
            marker_symbol = "triangle-up" if intent == "ENTER_TO_TARGET" else "triangle-down"
            fig.add_trace(
                go.Scatter(
                    x=[er["Date"]],
                    y=[er["equity"]],
                    mode="markers",
                    name=f"{aid.upper()} {'매수' if intent == 'ENTER_TO_TARGET' else '매도'}",
                    marker={"symbol": marker_symbol, "color": color, "size": 8},
                    showlegend=False,
                    hovertemplate=f"%{{x|%Y-%m-%d}}<br>{aid.upper()} {_INTENT_LABELS.get(intent, intent)}<extra></extra>",
                ),
                row=1,
                col=1,
            )

    # (2) 자산별 비중 추이
    target_weights: dict[str, float] = {}
    for pa in summary.get("per_asset", []):
        target_weights[str(pa.get("asset_id", ""))] = float(pa.get("target_weight", 0))

    for aid in asset_ids:
        weight_col = f"{aid}_weight"
        if weight_col not in equity_df.columns:
            continue
        color = _get_asset_color(aid)
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=equity_df[weight_col] * 100,
                mode="lines",
                name=f"{aid.upper()} 비중",
                line={"color": color, "width": 1.5},
                hovertemplate=f"%{{x|%Y-%m-%d}}<br>{aid.upper()}: %{{y:.1f}}%<extra></extra>",
            ),
            row=2,
            col=1,
        )
        tw = target_weights.get(aid, 0)
        if tw > 0:
            fig.add_hline(
                y=tw * 100,
                line_dash="dot",
                line_color=color,
                line_width=1,
                opacity=0.4,
                row=2,
                col=1,
            )

    # (3) 현금 잔고
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=equity_df["cash"],
            mode="lines",
            name="현금",
            line={"color": "#b4b4b4", "width": 1.5},
            fill="tozeroy",
            fillcolor="rgba(180, 180, 180, 0.2)",
            hovertemplate="%{x|%Y-%m-%d}<br>현금: %{y:,.0f}원<extra></extra>",
        ),
        row=3,
        col=1,
    )

    # (4) 자산별 주수
    for aid in asset_ids:
        shares_col = f"{aid}_shares"
        if shares_col not in equity_df.columns:
            continue
        color = _get_asset_color(aid)
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=equity_df[shares_col],
                mode="lines",
                name=f"{aid.upper()} 주수",
                line={"color": color, "width": 1.5},
                hovertemplate=f"%{{x|%Y-%m-%d}}<br>{aid.upper()}: %{{y:,.0f}}주<extra></extra>",
            ),
            row=4,
            col=1,
        )

    fig.update_layout(
        height=_CHART_HEIGHT + _SUB_CHART_HEIGHT * 2,
        hovermode="x unified",
        showlegend=True,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig, width="stretch", key=f"sync_chart_{exp_name}")


# ============================================================
# 뷰 3: 체결 상세 테이블
# ============================================================


def _render_execution_detail_table(
    state_log_df: pd.DataFrame,
    asset_ids: list[str],
    exp_name: str,
) -> None:
    """체결 발생일만 필터링하여 상세 테이블로 표시한다."""
    st.subheader("체결 상세 테이블")

    rows: list[dict[str, str]] = []
    for _, log_row in state_log_df.iterrows():
        for aid in asset_ids:
            executed = str(log_row.get(f"{aid}_executed_intent", ""))
            if not executed or executed == "nan" or executed == "":
                continue
            side = str(log_row.get(f"{aid}_exec_side", ""))
            exec_shares = int(log_row.get(f"{aid}_exec_shares", 0))
            exec_price = float(log_row.get(f"{aid}_exec_price", 0))
            shares_after = int(log_row.get(f"{aid}_shares", 0))
            weight_after = float(log_row.get(f"{aid}_weight", 0))
            reason = str(log_row.get("rebalance_reason", ""))
            reason_text = ""
            if reason == "monthly":
                reason_text = "월초 정기"
            elif reason == "daily":
                reason_text = "긴급"
            elif executed in ("EXIT_ALL", "ENTER_TO_TARGET"):
                reason_text = "시그널"
            else:
                reason_text = "리밸런싱"

            d = pd.Timestamp(log_row["Date"]).strftime("%Y-%m-%d")
            rows.append(
                {
                    "날짜": d,
                    "자산": aid.upper(),
                    "체결유형": _INTENT_LABELS.get(executed, executed),
                    "방향": "매도" if side == "sell" else "매수",
                    "체결수량": f"{exec_shares:,}",
                    "체결가격": f"${exec_price:.2f}",
                    "체결후 주수": f"{shares_after:,}",
                    "체결후 비중": f"{weight_after * 100:.1f}%",
                    "사유": reason_text,
                }
            )

    if rows:
        st.caption(f"총 {len(rows)}건 체결")
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info("체결 내역이 없습니다.")


# ============================================================
# 뷰 4: 시그널-체결 추적
# ============================================================


def _render_signal_execution_tracking(
    state_log_df: pd.DataFrame,
    asset_ids: list[str],
    exp_name: str,
) -> None:
    """시그널 발생일과 다음날 체결을 쌍으로 표시한다."""
    st.subheader("시그널-체결 추적")

    rows: list[dict[str, str]] = []
    for aid in asset_ids:
        pending_col = f"{aid}_pending_intent"
        executed_col = f"{aid}_executed_intent"
        if pending_col not in state_log_df.columns or executed_col not in state_log_df.columns:
            continue

        for i in range(len(state_log_df) - 1):
            pending = str(state_log_df.iloc[i][pending_col])
            if not pending or pending == "nan" or pending == "":
                continue

            signal_date = pd.Timestamp(state_log_df.iloc[i]["Date"]).strftime("%Y-%m-%d")
            signal_today = str(state_log_df.iloc[i].get(f"{aid}_signal_today", ""))
            next_executed = str(state_log_df.iloc[i + 1][executed_col])
            exec_date = pd.Timestamp(state_log_df.iloc[i + 1]["Date"]).strftime("%Y-%m-%d")
            exec_shares = int(state_log_df.iloc[i + 1].get(f"{aid}_exec_shares", 0))
            matched = pending == next_executed if next_executed and next_executed != "nan" else False

            rows.append(
                {
                    "자산": aid.upper(),
                    "시그널일": signal_date,
                    "시그널": _SIGNAL_LABELS.get(signal_today, signal_today),
                    "Pending Intent": _INTENT_LABELS.get(pending, pending),
                    "체결일": exec_date,
                    "체결 Intent": _INTENT_LABELS.get(next_executed, next_executed) if next_executed != "nan" else "-",
                    "체결수량": f"{exec_shares:,}" if exec_shares > 0 else "-",
                    "매칭": "OK" if matched else "MISMATCH",
                }
            )

    if rows:
        df = pd.DataFrame(rows)
        mismatch_count = len(df[df["매칭"] == "MISMATCH"])
        if mismatch_count > 0:
            st.warning(f"불일치 {mismatch_count}건 발견")
        else:
            st.success(f"총 {len(df)}건 모두 정상 매칭")
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("시그널-체결 쌍이 없습니다.")


# ============================================================
# 메인
# ============================================================


def main() -> None:
    """포트폴리오 디버그 대시보드 진입점."""
    st.set_page_config(
        page_title="포트폴리오 디버그 대시보드",
        layout="wide",
    )
    st.title("포트폴리오 디버그 대시보드")
    st.caption("일별 엔진 상태 탐색 | 시그널-체결 추적 | 정합성 검증")

    experiment_dirs = _discover_experiments()

    if not experiment_dirs:
        st.error(
            "state_log.csv가 포함된 포트폴리오 실험 결과가 없습니다. "
            "먼저 run_portfolio_backtest.py를 실행하세요.\n\n"
            "실행 명령어: `poetry run python scripts/backtest/run_portfolio_backtest.py`"
        )
        return

    # 실험 선택 (단일)
    exp_names = [d.name for d in experiment_dirs]
    selected_exp = st.selectbox("실험 선택", options=exp_names, key="debug_exp_select")
    exp_dir = PORTFOLIO_RESULTS_DIR / str(selected_exp)
    dir_str = str(exp_dir)

    # 데이터 로드
    state_log_df = _load_state_log(dir_str)
    equity_df = _load_equity(dir_str)
    summary = _load_summary(dir_str)

    asset_ids = _get_asset_ids(state_log_df)
    display_name: str = str(summary.get("display_name", selected_exp))

    st.caption(f"실험: {display_name} | 거래일 수: {len(state_log_df)} | 자산: {', '.join(a.upper() for a in asset_ids)}")

    # 뷰 1: 일별 상태 네비게이터
    st.divider()
    _render_daily_navigator(state_log_df, asset_ids, summary, str(selected_exp))

    # 뷰 2: 동기화 시계열 차트
    st.divider()
    _render_synchronized_charts(state_log_df, equity_df, asset_ids, summary, str(selected_exp))

    # 뷰 3: 체결 상세 테이블
    st.divider()
    _render_execution_detail_table(state_log_df, asset_ids, str(selected_exp))

    # 뷰 4: 시그널-체결 추적
    st.divider()
    _render_signal_execution_tracking(state_log_df, asset_ids, str(selected_exp))

    # Raw state_log 테이블 (접힘)
    with st.expander("Raw State Log (전체 데이터)", expanded=False):
        st.dataframe(state_log_df, hide_index=True, width="stretch")


if __name__ == "__main__":
    main()
