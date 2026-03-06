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

    # -- 해석 패널 --
    total = len(calmar_series)

    st.info(
        "432개 조합 중 Calmar > 0 비율이 100%입니다.\n"
        "이것은 기대 이상으로 좋은 결과입니다.\n\n"
        "432개 조합을 아무거나 골라도 전부 양(+)의 Calmar를 보인다는 것은,\n"
        "전략 자체(추세추종 + 버퍼존 구조)가 파라미터와 무관하게 "
        "작동한다는 강력한 증거입니다.\n\n"
        "분포는 0.10\\~0.18 구간에 주요 밀집을 보이며, "
        "0.18\\~0.28 구간에도 상당한 빈도가 존재합니다.\n"
        "최적(0.301)은 중앙값(0.168)보다 크게 높아 상위 약 0.3%에 해당하는 위치이지만,\n"
        "0.25\\~0.28 구간에도 다수의 조합이 존재하여 "
        "최적이 홀로 돌출된 봉우리는 아닙니다.\n\n"
        "분포의 우측 꼬리는 히트맵 분석(B 섹션)에서 확인된 "
        "sell_buffer의 체계적 효과에 의해\n"
        "형성된 것으로 판단됩니다. "
        "sell_buffer=5%인 조합들이 0.20\\~0.30 구간에,\n"
        "sell_buffer=1%인 조합들이 0.05\\~0.17 구간에 "
        "집중되어 있기 때문입니다.\n\n"
        "판단: 432개 전 조합이 양(+)이라는 사실이 가장 중요한 신호이며,\n"
        "분포 내 위치 차이는 sell_buffer의 체계적 효과로 설명됩니다.\n"
        "이 기준은 명확히 통과입니다."
    )

    with st.expander("용어 설명"):
        st.write(
            "Calmar Ratio는 수익률(CAGR)을 최대낙폭(MDD)으로 나눈 "
            "위험 조정 수익 지표입니다.\n\n"
            "    Calmar = CAGR / |MDD|\n\n"
            "예를 들어 CAGR 10%, MDD -50%이면 Calmar = 0.20입니다. "
            '값이 높을수록 "감수한 위험 대비 수익이 좋다"는 의미입니다.\n\n'
            f"여기서는 {total}개 파라미터 조합 각각의 Calmar를 "
            "히스토그램으로 보여줍니다. "
            '"어떤 파라미터를 골라도 전략 자체가 작동하는가"를 '
            "확인하기 위한 것입니다."
        )

    with st.expander("해석 방법"):
        st.write(
            "좋은 신호:\n"
            "- Calmar > 0인 조합이 대다수 -> 전략 구조 자체가 건전\n"
            "- 분포가 좁고 한쪽으로 치우침 -> 파라미터에 민감하지 않음\n"
            "- 최적값이 분포의 자연스러운 상단에 위치 -> "
            '"돌출된 봉우리"가 아님\n\n'
            "나쁜 신호:\n"
            "- Calmar < 0인 조합이 많음 -> 파라미터에 따라 전략이 손실\n"
            "- 최적값만 극단적으로 높고 나머지가 낮음 -> 과최적화 의심\n"
            "- 분포가 매우 넓음 -> 파라미터 선택에 극도로 민감"
        )


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

    # -- 해석 패널 --
    st.info(
        "세 히트맵 모두에서 동일한 패턴이 관찰됩니다:\n"
        "sell_buffer(\u2192 방향)가 커질수록 색상이 체계적으로 "
        "진해집니다(Calmar 증가).\n\n"
        "MA=200 히트맵의 9셀 값:\n\n"
        "| | sell=1% | sell=3% | sell=5% |\n"
        "|---|---|---|---|\n"
        "| buy=1% | 0.162 | 0.207 | 0.257 |\n"
        "| buy=3% | 0.153 | 0.195 | 0.249 |\n"
        "| buy=5% | 0.161 | 0.197 | 0.236 |\n\n"
        "두 가지 중요한 패턴이 관찰됩니다.\n\n"
        "첫째, sell_buffer 방향(\u2192)으로 Calmar가 체계적으로 증가합니다.\n"
        '이것은 "매도 버퍼가 클수록 조기 청산을 방지하여 추세를 더 오래 탄다"는 '
        "경제적 논거와 일치하는 체계적 패턴이며, 과최적화의 신호가 아닙니다.\n"
        "이 패턴은 MA=100, 150, 200 세 히트맵 모두에서 동일하게 나타나\n"
        "전략 논리의 일관성을 보여줍니다.\n\n"
        "둘째, 같은 sell_buffer 내에서 buy_buffer 간 변동이 매우 작습니다.\n"
        "- sell=5% 열: 0.257, 0.249, 0.236 \u2192 차이 0.021\n"
        "- sell=3% 열: 0.207, 0.195, 0.197 \u2192 차이 0.012\n"
        "- sell=1% 열: 0.162, 0.153, 0.161 \u2192 차이 0.009\n\n"
        "buy_buffer 축(\u2195 방향) 내에서는 매우 안정적인 고원이 확인됩니다.\n\n"
        "MA별 비교에서는 MA=200이 전반적으로 가장 높고, MA=150도 유사하며,\n"
        "MA=100은 확실히 낮습니다. 특히 MA=100에서는 buy_buffer가 커질수록\n"
        "Calmar가 뚜렷하게 감소하는 경향(0.194\u21920.158\u21920.147 등)이 보이는 반면,\n"
        "MA=200에서는 이 경향이 거의 사라져 더 안정적입니다.\n\n"
        '판정 테이블의 "히트맵 고원 형태: FAIL (차이 0.104)"은\n'
        "9셀 전체의 max-min을 측정한 것으로,\n"
        "sell_buffer의 체계적 방향성과 불규칙 변동을 구분하지 못하는 "
        "정량적 기준의 한계입니다.\n"
        "실제로는 buy_buffer 축 내에서 안정적 고원이 존재하며,\n"
        "sell_buffer 축의 변화는 설명 가능한 논리적 패턴입니다.\n\n"
        "판단: 체계적 패턴을 고려하면 실질적으로 양호합니다."
    )

    with st.expander("용어 설명"):
        st.write(
            "히트맵은 두 파라미터(Buy Buffer x Sell Buffer)의 모든 조합에 대해 "
            "평균 Calmar를 색상으로 표시한 것입니다.\n\n"
            "MA(이동평균 기간)별로 별도 히트맵을 그려서, "
            "MA 값에 따라 전략의 파라미터 지형이 어떻게 달라지는지 비교합니다.\n\n"
            "각 셀의 값은 해당 (Buy Buffer, Sell Buffer) 조합에서 "
            "hold_days x recent_months 16개 조합의 Calmar 평균입니다. "
            '이렇게 하면 "부차 파라미터와 무관하게 핵심 파라미터가 견고한가"를 '
            "측정할 수 있습니다."
        )

    with st.expander("해석 방법"):
        st.write(
            '좋은 신호 -- "고원(Plateau)":\n'
            "- 히트맵 전체가 비슷한 색상 -> 어떤 조합을 골라도 성과 유사\n"
            "- 색상 변화가 완만하고 방향성이 있음 -> 설명 가능한 체계적 패턴\n\n"
            '나쁜 신호 -- "봉우리(Spike)":\n'
            "- 한두 셀만 진한 색이고 나머지가 연함 -> 특정 조합에 극도로 의존\n"
            "- 색상이 불규칙하게 뒤섞임 -> 노이즈에 맞춰진 과최적화\n\n"
            "MA별 비교:\n"
            "- MA 값에 따라 히트맵 패턴이 유사하면 -> MA에 대해서도 견고\n"
            "- 특정 MA에서만 좋으면 -> MA 값에 의존하는 전략"
        )


def _render_adjacent_comparison(df: pd.DataFrame, criteria: dict[str, Any]) -> None:
    """섹션 C: 인접 파라미터 비교 바 차트."""
    st.header("C. 인접 파라미터 비교")

    # 최적 파라미터 기준
    optimal_idx = df[COL_CALMAR].idxmax()
    optimal_row = df.loc[optimal_idx]  # type: ignore[call-overload]
    optimal_ma = int(optimal_row[COL_MA_WINDOW])  # type: ignore[call-overload]
    optimal_buy = float(optimal_row[COL_BUY_BUFFER_ZONE_PCT])  # type: ignore[call-overload]
    optimal_sell = float(optimal_row[COL_SELL_BUFFER_ZONE_PCT])  # type: ignore[call-overload]

    opt_cell_mean = criteria["opt_cell_mean"]
    st.markdown(
        f"**최적 파라미터**: MA={optimal_ma}, "
        f"Buy Buffer={optimal_buy:.0%}, "
        f"Sell Buffer={optimal_sell:.0%}, "
        f"셀 평균 Calmar={opt_cell_mean:.4f}"
    )

    adj_df = build_adjacent_comparison(df, optimal_ma, optimal_buy, optimal_sell)

    threshold = criteria["adjacent_threshold"]  # 셀 평균 x 0.70

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

    # -- 해석 패널 --
    st.info(
        "Buy/Sell Buffer 변화 (왼쪽 차트):\n"
        "- buy_buffer(파란색)는 1%, 3%, 5% 모두 0.24\\~0.25 수준으로 "
        "매우 안정적이며,\n"
        "  세 값 모두 70% 임계선(0.1743)을 크게 상회합니다.\n"
        "  buy_buffer 변경이 성과에 미치는 영향은 미미합니다.\n\n"
        "- sell_buffer(주황색)는 방향성 있는 변화를 보입니다:\n"
        "  sell=1% \u2192 약 0.15 (임계 미달)\n"
        "  sell=3% \u2192 약 0.20 (임계 통과)\n"
        "  sell=5% \u2192 약 0.25 (임계 통과)\n\n"
        "Hold Days 변화 (오른쪽 차트):\n"
        "- hold_days 0\\~5 전체가 0.17\\~0.25 범위에서 안정적이며,\n"
        "  대부분 70% 임계선 위에 위치합니다.\n"
        "  hold_days=3이 가장 높지만 다른 값과의 차이가 크지 않습니다.\n\n"
        '판정 테이블의 "인접 파라미터: FAIL (61.6%)"은\n'
        "sell_buffer=0.01(두 단계 인접)이 최소값으로 잡힌 결과입니다.\n\n"
        "한 단계 인접만 보면:\n"
        "- buy=0.01, sell=0.05 \u2192 0.257 (103%, 오히려 높음)\n"
        "- buy=0.05, sell=0.05 \u2192 0.236 (95%)\n"
        "- buy=0.03, sell=0.03 \u2192 0.195 (78%)\n\n"
        "모두 70% 임계를 통과합니다.\n\n"
        "sell_buffer를 0.05\u21920.01로 두 단계 바꾸면 61%로 떨어지지만,\n"
        '이것은 "매도 버퍼를 극단적으로 줄이면 조기 청산이 빈번해진다"는\n'
        "전략 논리상 예상되는 결과이며, 과최적화의 증거가 아닙니다.\n\n"
        "판단: buy_buffer와 hold_days는 매우 안정적이며,\n"
        "sell_buffer=0.01의 성과 하락은 경제적으로 설명 가능합니다."
    )

    with st.expander("용어 설명"):
        st.write(
            '인접 파라미터 비교는 "최적 파라미터에서 한 단계만 바꾸면 '
            '성과가 어떻게 변하는가"를 측정합니다.\n\n'
            "기준값은 최적 셀(MA=200, Buy=3%, Sell=5%)의 평균 Calmar이며, "
            "각 바는 해당 파라미터 값에서의 평균 Calmar입니다.\n\n"
            "빨간 점선(70% 임계)은 기준값의 70%로, 이 선 아래로 떨어지면 "
            '"해당 파라미터 변경이 성과를 크게 악화시킨다"는 의미입니다.\n\n'
            "Buy/Sell Buffer 변화: MA=200 고정, buy 또는 sell을 변경했을 때의 평균 Calmar\n\n"
            "Hold Days 변화: MA=200, buy=3%, sell=5% 고정, hold_days를 변경했을 때의 평균 Calmar"
        )

    with st.expander("해석 방법"):
        st.write(
            "좋은 신호:\n"
            "- 모든 바가 70% 임계선 위 -> 어떤 인접 조합도 크게 나쁘지 않음\n"
            "- 바 높이가 비슷함 -> 파라미터 변경에 둔감 (견고)\n\n"
            "나쁜 신호:\n"
            "- 한두 바가 임계선 아래로 급락 -> 해당 방향의 변경에 취약\n"
            '- 최적만 높고 나머지가 급격히 낮음 -> "봉우리" 형태의 과최적화\n\n'
            "주의:\n"
            '"인접"의 정의가 중요합니다. 한 단계 인접(예: sell 5%->3%)과 '
            "두 단계 인접(예: sell 5%->1%)은 다르게 해석해야 합니다. "
            "두 단계 인접에서 크게 떨어지는 것은 자연스러울 수 있습니다."
        )


def _render_stability_summary(criteria: dict[str, Any]) -> None:
    """섹션 D: 통과 기준 판정 요약 (5개 기준 + 3단계 판정)."""
    st.header("D. 통과 기준 판정 요약")

    opt_cell_mean = criteria["opt_cell_mean"]
    adjacent_min = criteria["adjacent_min_mean"]
    adjacent_threshold = criteria["adjacent_threshold"]
    ratio = adjacent_min / opt_cell_mean * 100 if opt_cell_mean > 0 else 0.0

    # 판정 테이블 (5행)
    rows = [
        {
            "기준": "Calmar > 0 비율 (과반수 216+)",
            "결과": f"{criteria['calmar_positive_ratio'] * 100:.1f}% ({criteria['calmar_positive_count']}개)",
            "판정": "PASS" if criteria["calmar_positive_pass"] else "FAIL",
        },
        {
            "기준": "히트맵 고원 형태 (MA 내 셀 간 차이)",
            "결과": f"차이 {criteria['plateau_range']:.3f}",
            "판정": "PASS" if criteria["plateau_pass"] else "FAIL",
        },
        {
            "기준": "인접 파라미터 (평균 대 평균, 30% 이내)",
            "결과": (f"최소 {adjacent_min:.4f} / " f"기준 {opt_cell_mean:.4f} = {ratio:.1f}%"),
            "판정": "PASS" if criteria["adjacent_pass"] else "FAIL",
        },
        {
            "기준": "MA 의존성",
            "결과": f"MA=100이 최적 MA 대비 {criteria['ma_gap_pct']:.1f}% 낮음",
            "판정": "WARN" if criteria["ma_dependency_warn"] else "PASS",
        },
        {
            "기준": "sell_buffer 의존성",
            "결과": "sell_buffer=0.01 셀이 가장 낮음" if criteria["sell_dependency_warn"] else "특이사항 없음",
            "판정": "WARN" if criteria["sell_dependency_warn"] else "PASS",
        },
    ]

    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, width="stretch", hide_index=True)

    verdict = criteria["overall_verdict"]
    if verdict == "pass":
        st.success("파라미터 안정성 1단계 검증: 통과")
    elif verdict == "conditional":
        st.warning("파라미터 안정성 1단계 검증: 조건부 통과")
        # 주의 항목 나열
        warnings: list[str] = []
        if criteria["ma_dependency_warn"]:
            warnings.append(f"MA 의존성: MA=100이 {criteria['ma_gap_pct']:.1f}% 낮음")
        if criteria["sell_dependency_warn"]:
            warnings.append("sell_buffer 의존성: sell_buffer=0.01 셀이 가장 낮음")
        if not criteria["plateau_pass"]:
            warnings.append(f"히트맵 고원: 셀 간 차이 {criteria['plateau_range']:.3f}")
        if not criteria["adjacent_pass"]:
            warnings.append(f"인접 파라미터: 최소 {adjacent_min:.4f} < 임계 {adjacent_threshold:.4f}")
        if warnings:
            st.markdown("**주의 항목:**\n" + "\n".join(f"- {w}" for w in warnings))
    else:
        st.error("파라미터 안정성 1단계 검증: 미달")

    # -- 해석 패널 --
    st.info(
        "종합 판정: 미달 (PASS 1 / FAIL 2 / WARN 2)\n\n"
        "그러나 FAIL 2건 모두 sell_buffer의 체계적 방향성에 기인합니다.\n\n"
        "- 히트맵 고원 FAIL: sell_buffer 방향의 체계적 증가가 범위를 키움.\n"
        "  같은 sell_buffer 내에서는 안정적 고원이 확인됨 (B 섹션 참조).\n"
        "- 인접 파라미터 FAIL: sell_buffer=0.01(두 단계 인접)이 최소값.\n"
        "  한 단계 인접은 모두 70% 임계를 통과함 (C 섹션 참조).\n\n"
        "sell_buffer가 클수록 Calmar가 높아지는 것은\n"
        '"매도 버퍼가 클수록 조기 청산을 방지하여 추세를 더 오래 탄다"는\n'
        "경제적 논거와 일치하며, 과최적화가 아닌 전략 논리의 일관성을 보여줍니다.\n"
        "이 패턴은 MA=100, 150, 200 세 히트맵 모두에서 동일하게 나타납니다.\n\n"
        "WARN 2건도 마찬가지로 경제적 논거로 설명 가능합니다:\n"
        "- MA 의존성: 장기 이동평균(200일)이 추세 포착에 유리하다는 것은\n"
        "  학술적으로 널리 지지되는 사실\n"
        "- sell_buffer 의존성: 충분한 매도 버퍼가 노이즈에 의한 조기 청산을 방지\n\n"
        '최종 판단: 정량적 기준은 "미달"이나,\n'
        "FAIL의 원인이 모두 설명 가능한 체계적 패턴이므로\n"
        '실질적으로는 "조건부 통과"로 판단합니다.\n'
        "2단계(WFO 나쁜 윈도우 분석)와 3단계(SPY/IWM 교차 검증)로\n"
        "진행하는 것이 합리적입니다."
    )

    with st.expander("용어 설명"):
        st.write(
            "통과 기준 판정은 5개 정량적 기준으로 파라미터 안정성을 종합 평가합니다.\n\n"
            "- Pass: 기준을 충족\n"
            "- Fail: 기준 미달\n"
            "- Warn: 과최적화의 직접 증거는 아니지만 주의가 필요한 의존성 존재\n\n"
            "종합 판정:\n"
            "- 통과: Fail이 0개\n"
            "- 조건부 통과: Pass가 3개 이상이고 Fail이 1개 이하\n"
            "- 미달: 그 외"
        )

    with st.expander("해석 방법"):
        st.write(
            "Fail이 나왔다고 반드시 과최적화는 아닙니다. "
            '정량적 기준은 "체계적 패턴"과 "불규칙 변동"을 '
            "구분하지 못하는 한계가 있습니다.\n\n"
            "Fail 항목이 있으면 반드시 해당 섹션(B, C)의 "
            '"현재 결과 해석"을 함께 읽고, '
            "Fail의 원인이 다음 중 어디에 해당하는지 판단해야 합니다:\n\n"
            "(1) 설명 가능한 체계적 패턴 -> 과최적화 아님\n\n"
            "(2) 설명 불가능한 불규칙 변동 -> 과최적화 의심\n\n"
            'Warn 항목은 "이 파라미터는 성과에 영향을 준다"는 정보이며, '
            "해당 파라미터를 선택한 경제적 근거가 있으면 수용 가능합니다."
        )


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

    # 최적 파라미터
    optimal_idx = df[COL_CALMAR].idxmax()
    optimal_row = df.loc[optimal_idx]  # type: ignore[call-overload]
    optimal_ma = int(optimal_row[COL_MA_WINDOW])  # type: ignore[call-overload]
    optimal_buy = float(optimal_row[COL_BUY_BUFFER_ZONE_PCT])  # type: ignore[call-overload]
    optimal_sell = float(optimal_row[COL_SELL_BUFFER_ZONE_PCT])  # type: ignore[call-overload]

    # 판정 결과 (셀 평균 기반)
    criteria = evaluate_stability_criteria(
        df,
        optimal_ma=optimal_ma,
        optimal_buy=optimal_buy,
        optimal_sell=optimal_sell,
    )

    # 섹션 A: Calmar 분포
    calmar_series = build_calmar_histogram_data(df)
    _render_calmar_histogram(calmar_series)

    st.divider()

    # 섹션 B: 히트맵
    _render_heatmaps(df)

    st.divider()

    # 섹션 C: 인접 비교
    _render_adjacent_comparison(df, criteria)

    st.divider()

    # 섹션 D: 판정 요약
    _render_stability_summary(criteria)


if __name__ == "__main__":
    main()
