"""TQQQ 시뮬레이션 검증 대시보드

일별 비교 CSV 데이터를 Streamlit + Plotly로 시각화한다.

실행 명령어:
    poetry run streamlit run scripts/tqqq/streamlit_app.py
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_CUMUL_MULTIPLE_LOG_DIFF,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_SIMUL_CLOSE,
    TQQQ_DAILY_COMPARISON_PATH,
)
from qbt.utils.data_loader import load_comparison_data


def create_price_comparison_chart(df: pd.DataFrame) -> go.Figure:
    """
    실제 종가 vs 시뮬레이션 종가 비교 라인 차트를 생성한다.

    Args:
        df: 일별 비교 데이터

    Returns:
        Plotly Figure 객체
    """
    fig = go.Figure()

    # 실제 종가
    fig.add_trace(
        go.Scatter(
            x=df[DISPLAY_DATE],
            y=df[COL_ACTUAL_CLOSE],
            mode="lines",
            name="실제 TQQQ",
            line={"color": "#1f77b4", "width": 2},
            hovertemplate="<b>날짜</b>: %{x|%Y-%m-%d}<br>" + "<b>실제 종가</b>: $%{y:.2f}<br>" + "<extra></extra>",
        )
    )

    # 시뮬레이션 종가
    fig.add_trace(
        go.Scatter(
            x=df[DISPLAY_DATE],
            y=df[COL_SIMUL_CLOSE],
            mode="lines",
            name="시뮬레이션 TQQQ",
            line={"color": "#ff7f0e", "width": 2, "dash": "dash"},
            hovertemplate="<b>날짜</b>: %{x|%Y-%m-%d}<br>" + "<b>시뮬 종가</b>: $%{y:.2f}<br>" + "<extra></extra>",
        )
    )

    fig.update_layout(
        title="TQQQ 가격 비교: 실제 vs 시뮬레이션",
        xaxis_title="날짜",
        yaxis_title="가격 (USD)",
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        height=500,
    )

    fig.update_xaxes(
        tickformat="%Y-%m-%d",
    )

    return fig


def create_daily_return_diff_histogram(df: pd.DataFrame) -> go.Figure:
    """
    일일수익률 차이 분포 히스토그램을 생성한다.

    Args:
        df: 일별 비교 데이터

    Returns:
        Plotly Figure 객체
    """
    # 결측치 제거
    daily_diff = df[COL_DAILY_RETURN_ABS_DIFF].dropna()

    # 통계 계산
    mean_diff = daily_diff.mean()
    std_diff = daily_diff.std()
    min_diff = daily_diff.min()
    max_diff = daily_diff.max()

    fig = go.Figure()

    fig.add_trace(
        go.Histogram(
            x=daily_diff,
            nbinsx=50,
            name="일일수익률 차이",
            marker={"color": "#2ca02c", "line": {"color": "white", "width": 1}},
            hovertemplate="<b>차이 범위</b>: %{x:.2f}%<br>" + "<b>빈도</b>: %{y}<br>" + "<extra></extra>",
        )
    )

    # Rug plot 추가 (개별 데이터 포인트)
    fig.add_trace(
        go.Scatter(
            x=daily_diff,
            y=[0] * len(daily_diff),
            mode="markers",
            name="개별 관측값",
            marker={
                "color": "rgba(0, 0, 0, 0.3)",
                "size": 8,
                "symbol": "line-ns-open",
                "line": {"width": 2},
            },
            hovertemplate="<b>차이</b>: %{x:.2f}%<br>" + "<extra></extra>",
            yaxis="y2",
        )
    )

    # 평균선 추가
    fig.add_vline(x=mean_diff, line_dash="dash", line_color="red", annotation_text=f"평균: {mean_diff:.2f}%")

    fig.update_layout(
        title=f"일일수익률 절대차이 분포 (평균: {mean_diff:.2f}%, 표준편차: {std_diff:.2f}%, 범위: [{min_diff:.2f}%, {max_diff:.2f}%])",
        xaxis_title="일일수익률 절대차이 (%)",
        yaxis_title="빈도",
        yaxis2={
            "overlaying": "y",
            "side": "left",
            "showgrid": False,
            "showticklabels": False,
            "range": [0, 1],
        },
        height=500,
    )

    return fig


def create_cumulative_return_diff_chart(df: pd.DataFrame) -> go.Figure:
    """
    누적배수 로그차이 라인 차트를 생성한다.

    Args:
        df: 일별 비교 데이터

    Returns:
        Plotly Figure 객체
    """
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df[DISPLAY_DATE],
            y=df[COL_CUMUL_MULTIPLE_LOG_DIFF],
            mode="lines",
            name="누적배수 로그차이",
            line={"color": "#d62728", "width": 2},
            fill="tozeroy",
            hovertemplate="<b>날짜</b>: %{x|%Y-%m-%d}<br>" + "<b>차이</b>: %{y:.2f}%<br>" + "<extra></extra>",
        )
    )

    # 0 기준선
    fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="기준선 (0%)")

    fig.update_layout(
        title="누적배수 로그차이 추이",
        xaxis_title="날짜",
        yaxis_title="누적배수 로그차이 (%)",
        hovermode="x unified",
        height=500,
    )

    fig.update_xaxes(
        tickformat="%Y-%m-%d",
    )

    return fig


@st.cache_data
def load_data(csv_path: Path):
    """
    데이터를 로드하고 캐싱한다.

    Args:
        csv_path: CSV 파일 경로

    Returns:
        로드된 DataFrame
    """
    return load_comparison_data(csv_path)


def main():
    """Streamlit 앱 메인 함수"""
    try:
        # 페이지 설정
        st.set_page_config(
            page_title="TQQQ 시뮬레이션 검증 대시보드",
            page_icon=":chart_with_upwards_trend:",
            layout="wide",
        )

        # 타이틀
        st.title("TQQQ 시뮬레이션 검증 대시보드")
        st.markdown(
            """
            이 대시보드는 레버리지 ETF 시뮬레이션 결과를 실제 TQQQ 데이터와 비교하여 검증합니다.
            - **데이터 소스**: `tqqq_daily_comparison.csv`
            - **시각화**: Plotly 인터랙티브 차트 (확대/축소, 범례 토글, 툴팁 지원)
            """
        )

        # 데이터 로드
        csv_path = TQQQ_DAILY_COMPARISON_PATH
        df = load_data(csv_path)

        # 요약 지표
        st.header("요약 지표")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="검증 기간",
                value=f"{len(df):,}일",
                delta=f"{df[DISPLAY_DATE].min().strftime('%Y-%m-%d')} ~ {df[DISPLAY_DATE].max().strftime('%Y-%m-%d')}",
            )

        with col2:
            final_actual = df[COL_ACTUAL_CLOSE].iloc[-1]
            final_simul = df[COL_SIMUL_CLOSE].iloc[-1]
            price_diff_pct = ((final_simul - final_actual) / final_actual) * 100
            st.metric(label="최종 종가 (실제)", value=f"${final_actual:.2f}", delta=None)

        with col3:
            st.metric(label="최종 종가 (시뮬)", value=f"${final_simul:.2f}", delta=f"{price_diff_pct:+.2f}%")

        with col4:
            final_log_diff = df[COL_CUMUL_MULTIPLE_LOG_DIFF].iloc[-1]
            st.metric(label="최종 누적배수 로그차이", value=f"{final_log_diff:.2f}%")

        st.divider()

        # Section 1: 가격 비교 차트
        st.header("1. 가격 비교: 실제 vs 시뮬레이션")
        st.markdown(
            """
            실제 TQQQ 종가와 시뮬레이션 종가를 비교합니다.
            두 선이 가까울수록 시뮬레이션 정확도가 높습니다.
            """
        )
        price_chart = create_price_comparison_chart(df)
        st.plotly_chart(price_chart, width="stretch")

        st.divider()

        # Section 2: 일일수익률 차이 히스토그램
        st.header("2. 일일수익률 차이 분포")
        st.markdown(
            """
            일일수익률의 차이(실제 - 시뮬레이션)가 얼마나 분산되어 있는지 보여줍니다.
            평균이 0에 가깝고 분산이 작을수록 시뮬레이션이 정확합니다.
            """
        )
        histogram = create_daily_return_diff_histogram(df)
        st.plotly_chart(histogram, width="stretch")

        st.divider()

        # Section 3: 누적수익률 차이 차트
        st.header("3. 누적수익률 차이 추이")
        st.markdown(
            """
            시간에 따른 누적수익률 차이를 추적합니다.
            0 기준선에 가까울수록 장기 성과가 실제 데이터와 일치합니다.
            """
        )
        cumulative_chart = create_cumulative_return_diff_chart(df)
        st.plotly_chart(cumulative_chart, width="stretch")

        st.divider()

        # 푸터
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - TQQQ 시뮬레이션 검증 대시보드")

    except Exception as e:
        st.error("애플리케이션 실행 중 오류가 발생했습니다:")
        st.exception(e)
        return


if __name__ == "__main__":
    main()
