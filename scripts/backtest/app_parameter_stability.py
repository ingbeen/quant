"""파라미터 고원 시각화 대시보드

4개 파라미터(ma_window, buy_buffer, sell_buffer, hold_days)의
고원 분석 결과를 시각화한다.

각 탭에서 7자산의 Calmar 라인차트를 표시하고,
확정값 마커와 고원 구간 하이라이트를 제공한다.

선행 스크립트:
    poetry run python scripts/backtest/run_param_plateau_all.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_parameter_stability.py
"""

from typing import cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.backtest.parameter_stability import (
    find_plateau_range,
    find_plateau_range_with_trade_filter,
    get_current_value,
    load_plateau_pivot,
)

# ============================================================
# 로컬 상수
# ============================================================

# 탭 구성 (param_name, 표시명)
_TABS: list[tuple[str, str]] = [
    ("ma_window", "MA Window"),
    ("buy_buffer", "Buy Buffer"),
    ("sell_buffer", "Sell Buffer"),
    ("hold_days", "Hold Days"),
]

# 차트 높이
_CHART_HEIGHT = 450
_SUB_CHART_HEIGHT = 350

# 고원 구간 배경색
_PLATEAU_BG_COLOR = "rgba(144, 238, 144, 0.15)"

# Sell Buffer 거래 수 필터 기준
_SELL_BUFFER_MIN_TRADES = 5


def _render_line_chart(
    param_name: str,
    metric: str,
    title: str,
    height: int = _CHART_HEIGHT,
    show_plateau: bool = True,
    show_current: bool = True,
    trade_filter_min_trades: int | None = None,
) -> None:
    """라인차트를 렌더링한다.

    Args:
        param_name: 파라미터명
        metric: 지표명
        title: 차트 제목
        height: 차트 높이
        show_plateau: 고원 구간 하이라이트 표시 여부
        show_current: 현재 확정값 마커 표시 여부
        trade_filter_min_trades: 거래 수 필터 기준 (설정 시 해당 미만 파라미터를 고원 탐지에서 제외)
    """
    try:
        pivot = load_plateau_pivot(param_name, metric)
    except FileNotFoundError:
        st.warning(f"{param_name} - {metric} 데이터가 없습니다.")
        return

    fig = go.Figure()

    # 컬럼명에서 숫자 추출 (예: "hold=3" -> 3, "sell=0.05" -> 0.05)
    x_values: list[float] = []
    for col in pivot.columns:
        val_str = col.split("=")[1]
        x_values.append(float(val_str))

    # 7자산 각각 라인 추가
    for asset in pivot.index:
        y_values = [float(v) for v in pivot.loc[asset].values]
        fig.add_trace(
            go.Scatter(
                x=x_values,
                y=y_values,
                mode="lines+markers",
                name=str(asset),
                marker={"size": 5},
            )
        )

    # 현재 확정값 수직 점선
    if show_current:
        current_val = get_current_value(param_name)
        fig.add_vline(
            x=float(current_val),
            line_dash="dash",
            line_color="red",
            annotation_text=f"확정: {current_val}",
            annotation_position="top right",
        )

    # 고원 구간 하이라이트 (QQQ 기준)
    if show_plateau and "QQQ" in pivot.index:
        qqq_row = pivot.loc["QQQ"]
        # pivot.loc[]은 Series | DataFrame 반환 가능하지만, 단일 행이므로 Series
        assert isinstance(qqq_row, pd.Series)
        qqq_series = cast("pd.Series[float]", qqq_row)
        qqq_series.index = cast("pd.Index", x_values)

        if trade_filter_min_trades is not None:
            # 거래 수 필터 적용 (sell_buffer 등 저거래 파라미터 제외)
            try:
                trades_pivot = load_plateau_pivot(param_name, "trades")
                trades_row = trades_pivot.loc["QQQ"]
                assert isinstance(trades_row, pd.Series)
                trades_series = cast("pd.Series[float]", trades_row)
                trades_series.index = cast("pd.Index", x_values)
                plateau, _excluded = find_plateau_range_with_trade_filter(
                    qqq_series,
                    trades_series,
                    min_trades=trade_filter_min_trades,
                )
            except (FileNotFoundError, KeyError):
                plateau = find_plateau_range(qqq_series)
            annotation_label = "고원 구간 (80%, 저거래 제외)"
        else:
            plateau = find_plateau_range(qqq_series)
            annotation_label = "고원 구간 (80%)"

        if plateau is not None:
            fig.add_vrect(
                x0=plateau[0],
                x1=plateau[1],
                fillcolor=_PLATEAU_BG_COLOR,
                line_width=0,
                annotation_text=annotation_label,
                annotation_position="top left",
            )

    fig.update_layout(
        title=title,
        xaxis_title=param_name,
        yaxis_title=metric.upper(),
        height=height,
        legend={"yanchor": "top", "y": 0.99, "xanchor": "right", "x": 0.99},
    )
    st.plotly_chart(fig, width="stretch")


def _render_tab(param_name: str, display_name: str) -> None:
    """단일 탭의 내용을 렌더링한다.

    Args:
        param_name: 파라미터명
        display_name: 탭 표시명
    """
    st.header(f"{display_name} 고원 분석")

    current = get_current_value(param_name)
    st.markdown(f"**확정값**: {current}")

    # 메인: Calmar 라인차트
    trade_filter = _SELL_BUFFER_MIN_TRADES if param_name == "sell_buffer" else None
    _render_line_chart(
        param_name,
        "calmar",
        f"{display_name} - Calmar",
        trade_filter_min_trades=trade_filter,
    )

    # sell_buffer: 거래 수 필터 적용 안내
    if param_name == "sell_buffer":
        st.caption(f"거래 수 {_SELL_BUFFER_MIN_TRADES}회 미만인 파라미터(예: sell=0.15)는 " "사실상 Buy & Hold와 동일하여 고원 탐지 대상에서 제외됩니다.")

    # 보조: CAGR, MDD (접을 수 있는 expander)
    with st.expander("보조 지표 (CAGR, MDD)", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            _render_line_chart(
                param_name,
                "cagr",
                f"{display_name} - CAGR(%)",
                height=_SUB_CHART_HEIGHT,
                show_plateau=False,
                show_current=True,
            )
        with col2:
            _render_line_chart(
                param_name,
                "mdd",
                f"{display_name} - MDD(%)",
                height=_SUB_CHART_HEIGHT,
                show_plateau=False,
                show_current=True,
            )

    # 거래 수 라인차트
    with st.expander("거래 수", expanded=True):
        _render_line_chart(
            param_name,
            "trades",
            f"{display_name} - 거래 수",
            height=_SUB_CHART_HEIGHT,
            show_plateau=False,
            show_current=True,
        )


def main() -> None:
    """Streamlit 앱 메인 함수."""
    st.set_page_config(
        page_title="파라미터 고원 시각화 대시보드",
        layout="wide",
    )

    st.title("파라미터 고원 시각화 대시보드")
    st.markdown("4P 확정 파라미터(MA=200, buy=3%, sell=5%, hold=3) 기준 고원 분석")

    # 탭 생성
    tab_names = [display for _, display in _TABS]
    tabs = st.tabs(tab_names)

    for i, (param_name, display_name) in enumerate(_TABS):
        with tabs[i]:
            _render_tab(param_name, display_name)


if __name__ == "__main__":
    main()
