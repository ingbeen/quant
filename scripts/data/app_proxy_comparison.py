"""대체-실물 비교 대시보드

대체 시세가 기준 시세(대개 실물 ETF)를 얼마나 잘 따르는지 화면으로 확인한다.
전체 표는 계산 스크립트의 요약 CSV 를 읽고, 고른 쌍의 차트 · 기간별 표는 같은 src 함수로 즉석 계산한다.
등록 쌍 외에 storage/stock 의 아무 두 시세나 직접 골라 비교할 수 있다.

선행: poetry run python scripts/data/generate_proxy_comparison.py

실행 명령어:
    poetry run streamlit run scripts/data/app_proxy_comparison.py
"""

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.backtest.constants import ROUND_PERCENT, ROUND_RATIO
from qbt.backtest.supplement_experiment import PHASE_WINDOWS
from qbt.common_constants import COL_DATE, PROXY_COMPARISON_RESULTS_DIR, STOCK_DIR
from qbt.utils.data_loader import load_stock_data
from qbt.utils.proxy_comparison import (
    COL_BASE,
    COL_PROXY,
    DISPLAY_BASE,
    DISPLAY_BASE_FILE,
    DISPLAY_BEFORE,
    DISPLAY_GROUP,
    DISPLAY_PROXY,
    DISPLAY_PROXY_FILE,
    PERCENT_DISPLAY_COLUMNS,
    RATIO_DISPLAY_COLUMNS,
    ROLLING_WINDOW_DAYS,
    Period,
    align_closes,
    calendar_year_periods,
    normalized_overlay,
    period_summary_records,
    rolling_correlation,
    summarize_pair,
    summarize_periods,
)

SUMMARY_PATH = PROXY_COMPARISON_RESULTS_DIR / "summary.csv"
MODE_REGISTERED = "등록 쌍"
MODE_FREE = "직접 고르기"


@st.cache_data
def _load_prices(path: Path, mtime: float) -> pd.DataFrame:
    """시세를 읽는다. mtime 은 쓰지 않고 캐시 키로만 둔다 — 파일을 다시 만들면 새로 읽는다."""
    return load_stock_data(path)


@st.cache_data
def _load_summary(path: Path, mtime: float) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def _round_for_display(df: pd.DataFrame) -> pd.DataFrame:
    digits = {col: ROUND_RATIO for col in RATIO_DISPLAY_COLUMNS} | {
        col: ROUND_PERCENT for col in PERCENT_DISPLAY_COLUMNS
    }
    return df.round({col: digit for col, digit in digits.items() if col in df.columns})


def _format_optional(value: float | None, digits: int) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _choose_pair(summary_df: pd.DataFrame | None) -> tuple[Path, Path, date | None] | None:
    """비교할 (대체, 기준, 비교 제한) 을 고른다. 비교 제한은 등록 쌍의 상장 전 교차 확인에만 있다."""
    modes = [MODE_REGISTERED, MODE_FREE] if summary_df is not None else [MODE_FREE]
    mode = st.radio("비교 방식", modes, horizontal=True)
    if mode == MODE_REGISTERED and summary_df is not None:
        labels = [
            f"{row[DISPLAY_GROUP]} · {row[DISPLAY_PROXY]} → {row[DISPLAY_BASE]}" for _, row in summary_df.iterrows()
        ]
        index = st.selectbox("등록 쌍", range(len(labels)), format_func=lambda i: labels[i])
        row = summary_df.iloc[int(index)]
        before_value = row[DISPLAY_BEFORE]
        before = None if pd.isna(before_value) else date.fromisoformat(str(before_value))
        return STOCK_DIR / str(row[DISPLAY_PROXY_FILE]), STOCK_DIR / str(row[DISPLAY_BASE_FILE]), before

    files = sorted(path.name for path in STOCK_DIR.glob("*.csv"))
    if len(files) < 2:
        st.warning(f"{STOCK_DIR} 에 시세 파일이 2개 이상 있어야 비교할 수 있습니다.")
        return None
    col_proxy, col_base = st.columns(2)
    with col_proxy:
        proxy_name = st.selectbox("대체 (따라가는 쪽)", files, index=0)
    with col_base:
        base_name = st.selectbox("기준 (대개 실물 ETF)", files, index=1)
    if proxy_name == base_name:
        st.warning("서로 다른 두 시세를 고르세요.")
        return None
    return STOCK_DIR / proxy_name, STOCK_DIR / base_name, None


def _overlay_chart(proxy_df: pd.DataFrame, base_df: pd.DataFrame, proxy_label: str, base_label: str) -> go.Figure:
    overlay = normalized_overlay(proxy_df, base_df)
    fig = go.Figure()
    # 날짜가 두 시세의 합집합이라 한쪽에만 있는 날은 NaN — 끊어 그리면 데이터 공백처럼 보인다
    fig.add_trace(
        go.Scatter(x=overlay[COL_DATE], y=overlay[COL_PROXY], name=f"대체 {proxy_label}", mode="lines", connectgaps=True)
    )
    fig.add_trace(
        go.Scatter(x=overlay[COL_DATE], y=overlay[COL_BASE], name=f"기준 {base_label}", mode="lines", connectgaps=True)
    )
    base_first: date = base_df[COL_DATE].iloc[0]
    fig.add_vline(x=base_first, line_dash="dash", line_color="gray")
    fig.add_annotation(x=base_first, y=1.0, yref="paper", text=f"기준 첫 거래일 {base_first}", showarrow=False)
    fig.update_layout(yaxis_type="log", yaxis_title="첫 겹치는 날 = 1 (로그 눈금)", hovermode="x unified", height=480)
    return fig


def _rolling_chart(aligned: pd.DataFrame, rolling_min: float | None, rolling_min_date: date | None) -> go.Figure:
    rolling = rolling_correlation(aligned, ROLLING_WINDOW_DAYS)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=rolling.index, y=rolling.to_numpy(), name="12개월 이동 상관", mode="lines"))
    if rolling_min is not None and rolling_min_date is not None:
        fig.add_trace(
            go.Scatter(
                x=[rolling_min_date],
                y=[rolling_min],
                name=f"최저 {rolling_min:.4f}",
                mode="markers",
                marker={"size": 10, "color": "red"},
            )
        )
    fig.update_layout(yaxis_title="상관", hovermode="x unified", height=360)
    return fig


def _period_table(aligned: pd.DataFrame, periods: list[Period]) -> pd.DataFrame:
    return _round_for_display(pd.DataFrame(period_summary_records(summarize_periods(aligned, periods))))


def _show_pair(proxy_path: Path, base_path: Path, before: date | None) -> None:
    proxy_df = _load_prices(proxy_path, proxy_path.stat().st_mtime)
    base_df = _load_prices(base_path, base_path.stat().st_mtime)
    proxy_label = proxy_path.name.removesuffix("_max.csv")
    base_label = base_path.name.removesuffix("_max.csv")
    try:
        aligned = align_closes(proxy_df, base_df, before=before)
    except ValueError as exc:
        st.warning(f"두 시세를 비교할 수 없습니다: {exc}")
        return
    summary = summarize_pair(aligned)

    st.subheader(f"{proxy_label} → {base_label}")
    if before is not None:
        st.caption(f"상장 전 교차 확인 — 지표 · 이동 상관 · 기간별 표는 실물 첫 거래일 {before} 앞까지만 잰다. 겹쳐 그리기는 전 구간이다")
    cols = st.columns(6)
    cols[0].metric("비교 기간", f"{summary.trading_days:,}일", f"{summary.start} 부터", delta_color="off")
    cols[1].metric("일간 상관", _format_optional(summary.daily_corr, ROUND_RATIO))
    cols[2].metric("월간 상관", _format_optional(summary.monthly_corr, ROUND_RATIO))
    cols[3].metric("CAGR 차(대체 − 기준)", f"{summary.cagr_diff:+.{ROUND_PERCENT}f}%p")
    cols[4].metric("MDD 차(대체 − 기준)", f"{summary.mdd_diff:+.{ROUND_PERCENT}f}%p")
    cols[5].metric("12개월 상관 최저", _format_optional(summary.rolling_corr_min, ROUND_RATIO))

    st.markdown("#### 누적수익 겹쳐 그리기")
    st.markdown(
        """
        두 시세를 첫 겹치는 날 = 1 로 맞춰 겹쳐 그립니다. 선이 붙어 있을수록 대체가 기준을 잘 따릅니다.
        - **세로선(기준 첫 거래일) 왼쪽은 대체만 있는 구간**입니다. 대조할 실물이 없어 맞는지 확인할 수 없고,
          대체 판 백테스트는 이 구간을 대체 시세 그대로 씁니다
        - 로그 눈금이라 같은 비율의 움직임이 같은 높이로 보입니다
        """
    )
    st.plotly_chart(_overlay_chart(proxy_df, base_df, proxy_label, base_label), width="stretch")

    st.markdown("#### 12개월 이동 상관")
    st.markdown(
        f"""
        그날까지 {ROLLING_WINDOW_DAYS}거래일(약 1년)의 일간 수익률로 잰 상관입니다. 1 에 가까울수록 같이 움직입니다.
        - 전체 상관이 높아도 **특정 시기에만 어긋나는지**를 봅니다. 빨간 점이 가장 낮은 때입니다
        - 일간 상관은 거래 마감 시각 차이(선물 · 해외 펀드)나 하루 단위 잡음(초단기채)에 낮게 나올 수 있습니다.
          월말에 한 번 판단하는 전략에는 월간 상관이 더 직접적입니다
        """
    )
    st.plotly_chart(_rolling_chart(aligned, summary.rolling_corr_min, summary.rolling_corr_min_date), width="stretch")

    st.markdown("#### 기간별 비교")
    st.markdown(
        """
        기간마다 일간 상관과 수익률을 비교합니다. 수익률은 기간 첫날의 전날 종가가 기준이고, 차이는 대체 − 기준입니다.
        국면은 보완 전략 판정에 쓰는 구간입니다(겹치는 기간 밖 · 거래일 2일 미만인 기간은 빠집니다).
        """
    )
    tab_year, tab_phase = st.tabs(["연도별", "국면별"])
    with tab_year:
        st.dataframe(
            _period_table(aligned, calendar_year_periods(summary.start, summary.end)), width="stretch", hide_index=True
        )
    with tab_phase:
        phases = [Period(window.display_name, window.start, window.end) for window in PHASE_WINDOWS]
        st.dataframe(_period_table(aligned, phases), width="stretch", hide_index=True)


def main() -> None:
    """Streamlit 앱 메인 함수"""
    try:
        st.set_page_config(page_title="대체-실물 비교 대시보드", page_icon=":bar_chart:", layout="wide")
        st.title("대체-실물 비교 대시보드")
        st.markdown(
            """
            실물 ETF 가 상장하기 전 기간을 채우는 **대체 시세**가 실물을 얼마나 잘 따르는지 봅니다.
            비교는 **기준(대개 실물) 첫 거래일부터, 두 시세가 모두 있는 날만** 씁니다.
            - **상관**: 두 시세가 같은 방향으로 움직이는 정도. 1 이면 똑같이, 0 이면 무관
            - **CAGR · MDD 차**: 연평균 수익률과 최대 낙폭이 대체와 기준에서 얼마나 다른가 (대체 − 기준)
            """
        )

        summary_df: pd.DataFrame | None = None
        st.header("1. 등록 쌍 전체")
        if SUMMARY_PATH.exists():
            summary_df = _load_summary(SUMMARY_PATH, SUMMARY_PATH.stat().st_mtime)
            st.markdown(
                """
                - **대체 판**: 대체 판 백테스트가 쓰는 대체와 실물
                - **이어 붙인 판**: 지금 주 비교(2007-06 부터)가 상장 전 구간에 쓰는 기존 대용과 실물
                - **상장 전 교차 확인**: 실물이 없는 구간을 대체와 기존 대용끼리 비교 (기준이 실물이 아니다)
                """
            )
            st.dataframe(summary_df, width="stretch", hide_index=True)
        else:
            st.warning(
                f"요약 파일이 없습니다: {SUMMARY_PATH}. 등록 쌍을 보려면 먼저 "
                "`poetry run python scripts/data/generate_proxy_comparison.py` 를 실행하세요. "
                "직접 고르기는 그대로 쓸 수 있습니다."
            )

        st.divider()
        st.header("2. 한 쌍 자세히 보기")
        chosen = _choose_pair(summary_df)
        if chosen is not None:
            _show_pair(*chosen)

        st.markdown("---")
        st.caption("QBT (Quant BackTest) - 대체-실물 비교 대시보드")

    except Exception as e:
        st.error("애플리케이션 실행 중 오류가 발생했습니다:")
        st.exception(e)
        return


if __name__ == "__main__":
    main()
