"""TQQQ 시뮬레이션 시각화 모듈

Plotly 기반 차트 생성 함수를 제공한다.
대시보드 및 분석 보고서에서 사용할 수 있는 인터랙티브 차트를 생성한다.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_DR_M,
    COL_MONTH,
    COL_RATE_PCT,
    COL_SIMUL_CLOSE,
)


def create_price_comparison_chart(df: pd.DataFrame) -> go.Figure:
    """
    실제 종가 vs 시뮬레이션 종가 비교 라인 차트를 생성한다.

    Args:
        df: 일별 비교 데이터
            필수 컬럼: DISPLAY_DATE, COL_ACTUAL_CLOSE, COL_SIMUL_CLOSE

    Returns:
        Plotly Figure 객체 (인터랙티브 라인 차트)
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
            필수 컬럼: COL_DAILY_RETURN_ABS_DIFF

    Returns:
        Plotly Figure 객체 (히스토그램 + Rug plot)
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
    누적배수 로그차이 라인 차트를 생성한다 (signed 버전, 방향성 포함).

    Args:
        df: 일별 비교 데이터
            필수 컬럼: DISPLAY_DATE, COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED

    Returns:
        Plotly Figure 객체 (인터랙티브 라인 차트)
    """
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df[DISPLAY_DATE],
            y=df[COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED],
            mode="lines",
            name="누적배수 로그차이 (signed)",
            line={"color": "#d62728", "width": 2},
            fill="tozeroy",
            hovertemplate="<b>날짜</b>: %{x|%Y-%m-%d}<br>" + "<b>차이</b>: %{y:.2f}%<br>" + "<extra></extra>",
        )
    )

    # 0 기준선
    fig.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="기준선 (0%)")

    fig.update_layout(
        title="누적배수 로그차이 추이 (signed, 방향성 포함)",
        xaxis_title="날짜",
        yaxis_title="누적배수 로그차이 (%)",
        hovermode="x unified",
        height=500,
    )

    fig.update_xaxes(
        tickformat="%Y-%m-%d",
    )

    return fig


def create_level_chart(
    monthly_df: pd.DataFrame,
    y_col: str,
    y_label: str,
) -> go.Figure:
    """
    금리 수준 vs 오차 수준 산점도 및 시계열 라인 차트를 생성한다.

    Args:
        monthly_df: 월별 데이터
        y_col: y축 컬럼명 (e_m, de_m, sum_daily_m 중 하나)
        y_label: y축 레이블 (의미 설명 포함)

    Returns:
        Plotly Figure 객체 (서브플롯 2개: 산점도 + 시계열)
    """
    # 결측치 제거
    plot_df = monthly_df.dropna(subset=[COL_RATE_PCT, y_col])

    # 서브플롯 생성: 위(산점도), 아래(시계열)
    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=["금리 수준 vs 오차 (산점도)", "시계열 추이"],
        row_heights=[0.5, 0.5],
        vertical_spacing=0.15,
    )

    # 1. 산점도: rate_pct vs y_col
    fig.add_trace(
        go.Scatter(
            x=plot_df[COL_RATE_PCT],
            y=plot_df[y_col],
            mode="markers",
            name="월별 데이터",
            marker={"color": "#1f77b4", "size": 8},
            hovertemplate="<b>금리</b>: %{x:.2f}%<br>" + f"<b>{y_label}</b>: %{{y:.2f}}%<br>" + "<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # 추세선 (OLS)
    x = np.asarray(plot_df[COL_RATE_PCT].values, dtype=np.float64)
    y = np.asarray(plot_df[y_col].values, dtype=np.float64)
    if len(x) > 1:
        coef = np.polyfit(x, y, 1)
        trend_y = np.polyval(coef, x)
        fig.add_trace(
            go.Scatter(
                x=plot_df[COL_RATE_PCT],
                y=trend_y.tolist(),
                mode="lines",
                name=f"추세선 (y={coef[0]:.2f}x+{coef[1]:.2f})",
                line={"color": "red", "dash": "dash"},
            ),
            row=1,
            col=1,
        )

    # 2. 시계열 라인: month vs rate_pct, y_col
    plot_df_ts = plot_df.copy()
    plot_df_ts["month_str"] = plot_df_ts[COL_MONTH].astype(str)

    fig.add_trace(
        go.Scatter(
            x=plot_df_ts["month_str"],
            y=plot_df_ts[COL_RATE_PCT],
            mode="lines",
            name="금리 수준",
            line={"color": "#2ca02c", "width": 2},
            yaxis="y3",
            hovertemplate="<b>월</b>: %{x}<br>" + "<b>금리</b>: %{y:.2f}%<br>" + "<extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=plot_df_ts["month_str"],
            y=plot_df_ts[y_col],
            mode="lines",
            name=y_label,
            line={"color": "#ff7f0e", "width": 2},
            yaxis="y4",
            hovertemplate="<b>월</b>: %{x}<br>" + f"<b>{y_label}</b>: %{{y:.2f}}%<br>" + "<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # 레이아웃 업데이트
    fig.update_xaxes(title_text="금리 수준 (%)", row=1, col=1)
    fig.update_yaxes(title_text=y_label, row=1, col=1)

    fig.update_xaxes(title_text="월", row=2, col=1)
    fig.update_yaxes(title_text="금리 (%)", row=2, col=1, secondary_y=False)

    # 이중 y축 설정 (시계열 차트)
    fig.update_layout(
        yaxis3={"overlaying": "y2", "side": "left", "title": "금리 (%)"},
        yaxis4={"overlaying": "y2", "side": "right", "title": y_label},
        height=800,
        hovermode="x unified",
    )

    return fig


def create_delta_chart(
    monthly_df: pd.DataFrame,
    y_col: str,
    y_label: str,
    lag: int,
) -> tuple[go.Figure, pd.DataFrame]:
    """
    금리 변화 vs 오차 변화 산점도 및 Rolling 상관을 생성한다.

    Args:
        monthly_df: 월별 데이터
        y_col: y축 컬럼명 (de_m 또는 sum_daily_m)
        y_label: y축 레이블
        lag: Lag 개월 수 (0, 1, 2)

    Returns:
        (Plotly Figure 객체, 유효 데이터 DataFrame)
    """
    # Lag 적용: dr_m을 k개월 shift
    df = monthly_df.copy()
    df["dr_shifted"] = df[COL_DR_M].shift(lag)

    # 결측치 제거 (dr_shifted와 y_col 모두 존재하는 행만)
    plot_df = df.dropna(subset=["dr_shifted", y_col])

    # 샘플 수
    n = len(plot_df)

    # 서브플롯 생성: 위(산점도), 아래(Rolling 12M 상관)
    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=[
            f"금리 변화 (Lag {lag}) vs 오차 변화 (n={n})",
            "Rolling 12개월 상관",
        ],
        row_heights=[0.5, 0.5],
        vertical_spacing=0.15,
    )

    # 1. 산점도: dr_shifted vs y_col
    fig.add_trace(
        go.Scatter(
            x=plot_df["dr_shifted"],
            y=plot_df[y_col],
            mode="markers",
            name="월별 데이터",
            marker={"color": "#1f77b4", "size": 8},
            hovertemplate="<b>금리 변화 (Lag "
            + str(lag)
            + ")</b>: %{x:.2f}%p<br>"
            + f"<b>{y_label}</b>: %{{y:.2f}}%<br>"
            + "<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # 추세선
    x = np.asarray(plot_df["dr_shifted"].values, dtype=np.float64)
    y = np.asarray(plot_df[y_col].values, dtype=np.float64)
    if len(x) > 1:
        coef = np.polyfit(x, y, 1)
        trend_y = np.polyval(coef, x)
        fig.add_trace(
            go.Scatter(
                x=plot_df["dr_shifted"],
                y=trend_y.tolist(),
                mode="lines",
                name=f"추세선 (y={coef[0]:.2f}x+{coef[1]:.2f})",
                line={"color": "red", "dash": "dash"},
            ),
            row=1,
            col=1,
        )

    # 2. Rolling 12M 상관
    if len(plot_df) >= 12:
        plot_df_sorted = plot_df.sort_values(by=COL_MONTH).reset_index(drop=True)
        rolling_corr = (
            plot_df_sorted[["dr_shifted", y_col]]
            .rolling(window=12)
            .corr()
            .iloc[0::2, -1]  # dr_shifted와 y_col의 상관만 추출
            .reset_index(drop=True)
        )

        # month 문자열 변환
        plot_df_sorted["month_str"] = plot_df_sorted[COL_MONTH].astype(str)

        fig.add_trace(
            go.Scatter(
                x=plot_df_sorted["month_str"],
                y=rolling_corr,
                mode="lines+markers",
                name="Rolling 12M 상관",
                line={"color": "#2ca02c", "width": 2},
                hovertemplate="<b>월</b>: %{x}<br>" + "<b>상관</b>: %{y:.2f}<br>" + "<extra></extra>",
            ),
            row=2,
            col=1,
        )

        # 0 기준선
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)
    else:
        # 데이터 부족 안내
        fig.add_annotation(
            text=f"Rolling 12M 상관 계산 불가 (샘플 수: {len(plot_df)}, 최소: 12)",
            xref="x2",
            yref="y2",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": "red"},
            row=2,
            col=1,
        )

    # 레이아웃 업데이트
    fig.update_xaxes(title_text=f"금리 변화 (Lag {lag}, %p)", row=1, col=1)
    fig.update_yaxes(title_text=y_label, row=1, col=1)

    fig.update_xaxes(title_text="월", row=2, col=1)
    fig.update_yaxes(title_text="상관 계수", row=2, col=1)

    fig.update_layout(
        height=800,
        hovermode="x unified",
    )

    return fig, plot_df
