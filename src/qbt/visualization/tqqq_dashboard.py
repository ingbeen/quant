"""TQQQ 시뮬레이션 대시보드 컴포넌트

일별 비교 CSV 데이터를 Plotly 차트로 시각화한다.
"""


import pandas as pd
import plotly.graph_objects as go

from qbt.common_constants import (
    COL_ACTUAL_CLOSE,
    COL_CUMUL_RETURN_DIFF,
    COL_DAILY_RETURN_DIFF,
    COL_DATE_KR,
    COL_SIMUL_CLOSE,
)


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
            x=df[COL_DATE_KR],
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
            x=df[COL_DATE_KR],
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
    daily_diff = df[COL_DAILY_RETURN_DIFF].dropna()

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
        title=f"일일수익률 차이 분포 (평균: {mean_diff:.2f}%, 표준편차: {std_diff:.2f}%, 범위: [{min_diff:.2f}%, {max_diff:.2f}%])",
        xaxis_title="일일수익률 차이 (%)",
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
    누적수익률 차이 라인 차트를 생성한다.

    Args:
        df: 일별 비교 데이터

    Returns:
        Plotly Figure 객체
    """
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df[COL_DATE_KR],
            y=df[COL_CUMUL_RETURN_DIFF],
            mode="lines",
            name="누적수익률 차이",
            line={"color": "#d62728", "width": 2},
            fill="tozeroy",
            hovertemplate="<b>날짜</b>: %{x|%Y-%m-%d}<br>" + "<b>차이</b>: %{y:.2f}%<br>" + "<extra></extra>",
        )
    )

    # 0 기준선
    fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="기준선 (0%)")

    fig.update_layout(
        title="누적수익률 차이 추이",
        xaxis_title="날짜",
        yaxis_title="누적수익률 차이 (%)",
        hovermode="x unified",
        height=500,
    )

    fig.update_xaxes(
        tickformat="%Y-%m-%d",
    )

    return fig
