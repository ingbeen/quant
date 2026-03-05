"""백테스트 파라미터 안정성 분석 대시보드

overfitting_analysis_report.md 11.2절 "1단계: 파라미터 안정성 확인"의
3가지 분석 항목을 시각화한다.

- 섹션 A: Calmar 분포 히스토그램 (432개 전체)
- 섹션 B: MA별 buy_buffer x sell_buffer 히트맵 (평균 Calmar)
- 섹션 C: 인접 파라미터 비교 바 차트
- 섹션 D: 통과 기준 판정 요약

선행 스크립트:
    poetry run python scripts/backtest/run_grid_search.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_parameter_stability.py
"""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.backtest.constants import (
    COL_BUY_BUFFER_ZONE_PCT,
    COL_CALMAR,
    COL_MA_WINDOW,
    COL_SELL_BUFFER_ZONE_PCT,
)
from qbt.backtest.parameter_stability import (
    build_adjacent_comparison,
    build_calmar_histogram_data,
    build_heatmap_data,
    evaluate_stability_criteria,
    load_grid_results,
)
from qbt.common_constants import BUFFER_ZONE_QQQ_RESULTS_DIR

# ============================================================
# 로컬 상수 (이 파일에서만 사용)
# ============================================================

# 전략별 그리드 서치 결과 경로 매핑
_STRATEGY_GRID_PATHS: dict[str, Path] = {
    "buffer_zone_qqq": BUFFER_ZONE_QQQ_RESULTS_DIR / "grid_results.csv",
}

# 전략별 표시명
_STRATEGY_DISPLAY_NAMES: dict[str, str] = {
    "buffer_zone_qqq": "버퍼존 전략 (QQQ)",
}

# 히트맵 색상 스케일
DEFAULT_HEATMAP_COLORSCALE = "YlOrRd"

# 차트 높이
DEFAULT_CHART_HEIGHT = 400
DEFAULT_HEATMAP_HEIGHT = 350


def _render_calmar_histogram(calmar_series: pd.Series) -> None:  # type: ignore[type-arg]
    """섹션 A: Calmar 분포 히스토그램."""
    st.header("A. Calmar 분포")

    # 기본 통계
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("전체 조합 수", f"{len(calmar_series)}개")
    col2.metric("Calmar > 0 비율", f"{float((calmar_series > 0).mean()) * 100:.1f}%")
    col3.metric("평균", f"{float(calmar_series.mean()):.4f}")
    col4.metric("표준편차", f"{float(calmar_series.std()):.4f}")

    # 히스토그램
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=calmar_series,
            nbinsx=30,
            marker_color="rgba(33, 150, 243, 0.7)",
            name="Calmar",
        )
    )

    # 최적값 수직선
    optimal = float(calmar_series.max())
    fig.add_vline(
        x=optimal,
        line_dash="dash",
        line_color="red",
        annotation_text=f"최적: {optimal:.4f}",
    )

    # 중앙값 수직선
    median = float(calmar_series.median())
    fig.add_vline(
        x=median,
        line_dash="dot",
        line_color="green",
        annotation_text=f"중앙값: {median:.4f}",
    )

    fig.update_layout(
        xaxis_title="Calmar Ratio",
        yaxis_title="빈도",
        height=DEFAULT_CHART_HEIGHT,
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")


def _render_heatmaps(df: pd.DataFrame) -> None:
    """섹션 B: MA별 buy_buffer x sell_buffer 히트맵."""
    st.header("B. MA별 Buy/Sell Buffer 히트맵 (평균 Calmar)")

    ma_values = [100, 150, 200]

    # 전체 데이터에서 zmin/zmax 통일을 위한 범위 계산
    all_means: list[float] = []
    for ma in ma_values:
        heatmap_df = build_heatmap_data(df, ma_window=ma)
        all_means.extend(heatmap_df["calmar_mean"].tolist())

    zmin = min(all_means) if all_means else 0.0
    zmax = max(all_means) if all_means else 1.0

    cols = st.columns(3)

    for i, ma in enumerate(ma_values):
        with cols[i]:
            st.subheader(f"MA = {ma}")
            heatmap_df = build_heatmap_data(df, ma_window=ma)

            # 피벗: buy_buffer(행) x sell_buffer(열)
            buy_vals = sorted(heatmap_df[COL_BUY_BUFFER_ZONE_PCT].unique())
            sell_vals = sorted(heatmap_df[COL_SELL_BUFFER_ZONE_PCT].unique())

            # 행렬 구성
            z_matrix: list[list[float]] = []
            cagr_matrix: list[list[float]] = []
            mdd_matrix: list[list[float]] = []
            min_matrix: list[list[float]] = []

            for buy in buy_vals:
                z_row: list[float] = []
                cagr_row: list[float] = []
                mdd_row: list[float] = []
                min_row: list[float] = []
                for sell in sell_vals:
                    cell = heatmap_df[
                        (heatmap_df[COL_BUY_BUFFER_ZONE_PCT] == buy) & (heatmap_df[COL_SELL_BUFFER_ZONE_PCT] == sell)
                    ]
                    if len(cell) > 0:
                        z_row.append(float(cell["calmar_mean"].iloc[0]))
                        cagr_row.append(float(cell["cagr_mean"].iloc[0]))
                        mdd_row.append(float(cell["mdd_mean"].iloc[0]))
                        min_row.append(float(cell["calmar_min"].iloc[0]))
                    else:
                        z_row.append(0.0)
                        cagr_row.append(0.0)
                        mdd_row.append(0.0)
                        min_row.append(0.0)
                z_matrix.append(z_row)
                cagr_matrix.append(cagr_row)
                mdd_matrix.append(mdd_row)
                min_matrix.append(min_row)

            # customdata로 보조 지표 포함
            customdata = np.stack(
                [
                    np.array(cagr_matrix),
                    np.array(mdd_matrix),
                    np.array(min_matrix),
                ],
                axis=-1,
            )

            # 축 레이블
            x_labels = [f"{s:.0%}" for s in sell_vals]
            y_labels = [f"{b:.0%}" for b in buy_vals]
            text_labels = [[f"{v:.3f}" for v in row] for row in z_matrix]

            fig = go.Figure(
                data=go.Heatmap(
                    z=z_matrix,  # type: ignore[arg-type]
                    x=x_labels,  # type: ignore[arg-type]
                    y=y_labels,  # type: ignore[arg-type]
                    customdata=customdata,
                    hovertemplate=(
                        "Buy Buffer: %{y}<br>"
                        "Sell Buffer: %{x}<br>"
                        "Calmar 평균: %{z:.4f}<br>"
                        "CAGR 평균: %{customdata[0]:.2f}%<br>"
                        "MDD 평균: %{customdata[1]:.2f}%<br>"
                        "Calmar 최소: %{customdata[2]:.4f}"
                        "<extra></extra>"
                    ),
                    colorscale=DEFAULT_HEATMAP_COLORSCALE,
                    zmin=zmin,
                    zmax=zmax,
                    text=text_labels,  # type: ignore[arg-type]
                    texttemplate="%{text}",
                )
            )

            fig.update_layout(
                xaxis_title="Sell Buffer",
                yaxis_title="Buy Buffer",
                height=DEFAULT_HEATMAP_HEIGHT,
            )
            st.plotly_chart(fig, width="stretch")


def _render_adjacent_comparison(df: pd.DataFrame, optimal_calmar: float) -> None:
    """섹션 C: 인접 파라미터 비교 바 차트."""
    st.header("C. 인접 파라미터 비교")

    # 최적 파라미터 기준
    optimal_idx = df[COL_CALMAR].idxmax()
    optimal_row = df.loc[optimal_idx]  # type: ignore[call-overload]
    optimal_ma = int(optimal_row[COL_MA_WINDOW])  # type: ignore[call-overload]
    optimal_buy = float(optimal_row[COL_BUY_BUFFER_ZONE_PCT])  # type: ignore[call-overload]
    optimal_sell = float(optimal_row[COL_SELL_BUFFER_ZONE_PCT])  # type: ignore[call-overload]

    st.markdown(
        f"**최적 파라미터**: MA={optimal_ma}, "
        f"Buy Buffer={optimal_buy:.0%}, "
        f"Sell Buffer={optimal_sell:.0%}, "
        f"Calmar={optimal_calmar:.4f}"
    )

    adj_df = build_adjacent_comparison(df, optimal_ma, optimal_buy, optimal_sell)

    threshold = optimal_calmar * 0.7  # 30% 이내 임계선

    col1, col2 = st.columns(2)

    # Buy/Sell buffer 비교
    with col1:
        st.subheader("Buy/Sell Buffer 변화")
        buffer_df = adj_df[adj_df["axis"].isin(["buy_buffer", "sell_buffer"])]

        fig = go.Figure()

        for axis_name, color in [
            ("buy_buffer", "rgba(33, 150, 243, 0.8)"),
            ("sell_buffer", "rgba(255, 152, 0, 0.8)"),
        ]:
            axis_data = buffer_df[buffer_df["axis"] == axis_name]
            fig.add_trace(
                go.Bar(
                    x=[f"{v:.0%}" for v in axis_data["param_value"]],
                    y=axis_data["calmar_mean"],
                    name=axis_name.replace("_", " ").title(),
                    marker_color=color,
                )
            )

        # 30% 임계선
        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"70% 임계: {threshold:.4f}",
        )

        fig.update_layout(
            xaxis_title="파라미터 값",
            yaxis_title="평균 Calmar",
            height=DEFAULT_CHART_HEIGHT,
            barmode="group",
        )
        st.plotly_chart(fig, width="stretch")

    # Hold days 비교
    with col2:
        st.subheader("Hold Days 변화")
        hold_df = adj_df[adj_df["axis"] == "hold_days"]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=[str(int(v)) for v in hold_df["param_value"]],
                y=hold_df["calmar_mean"],
                name="Hold Days",
                marker_color="rgba(76, 175, 80, 0.8)",
            )
        )

        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"70% 임계: {threshold:.4f}",
        )

        fig.update_layout(
            xaxis_title="Hold Days",
            yaxis_title="평균 Calmar",
            height=DEFAULT_CHART_HEIGHT,
        )
        st.plotly_chart(fig, width="stretch")


def _render_stability_summary(criteria: dict[str, Any]) -> None:
    """섹션 D: 통과 기준 판정 요약."""
    st.header("D. 통과 기준 판정 요약")

    # 판정 테이블
    rows = [
        {
            "기준": "Calmar > 0 비율 (과반수 216+)",
            "결과": f"{criteria['calmar_positive_ratio'] * 100:.1f}% ({criteria['calmar_positive_count']}개)",
            "판정": "PASS" if criteria["calmar_positive_pass"] else "FAIL",
        },
        {
            "기준": "인접 파라미터 Calmar (최적 대비 30% 이내)",
            "결과": f"최소 평균 Calmar: {criteria['adjacent_min_calmar']:.4f} (임계: {criteria['adjacent_within_threshold']:.4f})",
            "판정": "PASS" if criteria["adjacent_pass"] else "FAIL",
        },
        {
            "기준": "종합 판정",
            "결과": "",
            "판정": "PASS" if criteria["overall_pass"] else "FAIL",
        },
    ]

    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, width="stretch", hide_index=True)

    if criteria["overall_pass"]:
        st.success("파라미터 안정성 1단계 검증: 통과")
    else:
        st.error("파라미터 안정성 1단계 검증: 미달")


def main() -> None:
    """Streamlit 앱 메인 함수."""
    st.set_page_config(
        page_title="파라미터 안정성 분석 대시보드",
        layout="wide",
    )

    st.title("파라미터 안정성 분석 대시보드")
    st.markdown("overfitting_analysis_report.md 11.2절 '1단계: 파라미터 안정성 확인'")

    # 전략 선택
    strategy_options = list(_STRATEGY_DISPLAY_NAMES.keys())
    selected = st.selectbox(
        "전략 선택",
        options=strategy_options,
        format_func=lambda x: _STRATEGY_DISPLAY_NAMES[x],
    )

    if selected is None:
        st.warning("전략을 선택해주세요.")
        return

    grid_path = _STRATEGY_GRID_PATHS[selected]

    if not grid_path.exists():
        st.error(f"grid_results.csv를 찾을 수 없습니다: {grid_path}")
        st.info("먼저 그리드 서치를 실행해주세요: " "`poetry run python scripts/backtest/run_grid_search.py`")
        return

    # 데이터 로드
    df = load_grid_results(grid_path)

    # 최적 Calmar
    optimal_calmar = float(df[COL_CALMAR].max())

    # 최적 파라미터
    optimal_idx = df[COL_CALMAR].idxmax()
    optimal_row = df.loc[optimal_idx]  # type: ignore[call-overload]
    optimal_ma = int(optimal_row[COL_MA_WINDOW])  # type: ignore[call-overload]
    optimal_buy = float(optimal_row[COL_BUY_BUFFER_ZONE_PCT])  # type: ignore[call-overload]
    optimal_sell = float(optimal_row[COL_SELL_BUFFER_ZONE_PCT])  # type: ignore[call-overload]

    # 섹션 A: Calmar 분포
    calmar_series = build_calmar_histogram_data(df)
    _render_calmar_histogram(calmar_series)

    st.divider()

    # 섹션 B: 히트맵
    _render_heatmaps(df)

    st.divider()

    # 섹션 C: 인접 비교
    _render_adjacent_comparison(df, optimal_calmar)

    st.divider()

    # 섹션 D: 판정 요약
    criteria = evaluate_stability_criteria(
        df,
        optimal_calmar=optimal_calmar,
        optimal_ma=optimal_ma,
        optimal_buy=optimal_buy,
        optimal_sell=optimal_sell,
    )
    _render_stability_summary(criteria)


if __name__ == "__main__":
    main()
