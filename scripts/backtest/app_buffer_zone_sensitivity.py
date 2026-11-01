"""버퍼존 규칙 민감도 대시보드

매도 폭 · 매수 폭 · 이평선 기간 · 한달 길이를 하나씩 바꾼 결과와 규칙 조합, 값별 거래 목록을 보여 준다.
합격 · 불합격을 내지 않는다 — 결과의 모양을 보고 과최적화인지 판단한다 (계산: buffer_zone_sensitivity).

선행 스크립트:
    poetry run python scripts/backtest/run_buffer_zone_sensitivity.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_buffer_zone_sensitivity.py
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.backtest.buffer_zone_sensitivity import (
    BASE_SELL_PCTS,
    CELLS_FILENAME,
    CSV_ENCODING,
    DATASETS,
    DISPLAY_BASE_SELL,
    DISPLAY_BH_CAGR,
    DISPLAY_BH_MDD,
    DISPLAY_CAGR,
    DISPLAY_CAGR_DIFF,
    DISPLAY_CLOSED,
    DISPLAY_DATASET,
    DISPLAY_END,
    DISPLAY_ENTRY_DATE,
    DISPLAY_EXIT_DATE,
    DISPLAY_EXPERIMENT,
    DISPLAY_GROUP,
    DISPLAY_HELD,
    DISPLAY_LOSSES,
    DISPLAY_LOWEST,
    DISPLAY_MDD,
    DISPLAY_MDD_DIFF,
    DISPLAY_PNL,
    DISPLAY_RULE,
    DISPLAY_START,
    DISPLAY_STATUS,
    DISPLAY_VALUE,
    DISPLAY_WINS,
    DISPLAY_WORST,
    EXPERIMENT_BUY,
    EXPERIMENT_MA,
    EXPERIMENT_MONTH,
    EXPERIMENT_RULE,
    EXPERIMENT_SELL,
    GROUP_FULL,
    GROUP_SEEN,
    GROUP_UNSEEN,
    RULES_FILENAME,
    SENSITIVITY_RESULTS_DIR,
    TRADES_FILENAME,
)
from qbt.common_constants import EPSILON

# ============================================================
# 로컬 상수
# ============================================================

_CHART_HEIGHT = 300

# 전략은 파랑, Buy & Hold 는 주황 — 어느 실험 · 구간에서도 같은 색
_STRATEGY_COLOR = "#2a78d6"
_BUY_AND_HOLD_COLOR = "#d95926"
_MARKER_LINE_COLOR = "#898781"

_EXPERIMENTS = (EXPERIMENT_SELL, EXPERIMENT_BUY, EXPERIMENT_MA, EXPERIMENT_MONTH)
_PERCENT_EXPERIMENTS = (EXPERIMENT_SELL, EXPERIMENT_BUY)

# 차트에 세로선으로 표시하는 값 (값, 표시 문구)
_MARKED_VALUES: dict[str, tuple[tuple[float, str], ...]] = {
    EXPERIMENT_SELL: ((0.05, "5%"), (0.10, "10%")),
    EXPERIMENT_BUY: ((0.05, "5%"),),
    EXPERIMENT_MA: ((200, "200일"),),
    EXPERIMENT_MONTH: ((21, "21일"),),
}

_INDEX_LIMITS = (
    "지수라 배당이 빠져 있고 현금 이자는 0 입니다. "
    "^GSPC 1965 ~ 2004 와 ^NDX 1985 ~ 1999 는 시가가 전일 종가와 같은 날이 많아 체결이 실제보다 좋게 나옵니다. "
    "^IXIC 는 1984-10-10 까지 종가만 있어 손절선이 종가 최저입니다."
)

_GROUP_NOTES = {
    GROUP_SEEN: "매도 10% 와 눌림 제거는 이 구간의 결과를 보고 고른 값입니다. QLD · TQQQ 의 상장 전 구간은 합성 시세입니다.",
    GROUP_UNSEEN: f"후보 값을 고를 때 보지 않은 구간입니다. {_INDEX_LIMITS}",
    GROUP_FULL: ("안 본 구간에 후보를 고를 때 본 구간까지 합친 참고값입니다. 2009년 이후 상승장이 옛 폭락의 결과를 가릴 수 있습니다. " f"{_INDEX_LIMITS}"),
}

_TABLE_METRICS = [
    DISPLAY_CAGR,
    DISPLAY_MDD,
    DISPLAY_BH_CAGR,
    DISPLAY_BH_MDD,
    DISPLAY_CAGR_DIFF,
    DISPLAY_MDD_DIFF,
    DISPLAY_CLOSED,
    DISPLAY_WINS,
    DISPLAY_LOSSES,
    DISPLAY_WORST,
    DISPLAY_LOWEST,
    DISPLAY_HELD,
    DISPLAY_START,
    DISPLAY_END,
]

# 값을 사람이 읽는 문구로 바꾼 열 (화면 전용)
_VALUE_LABEL = "값 표시"


# ============================================================
# 데이터
# ============================================================


@st.cache_data
def _load_csv(path: Path, mtime: float) -> pd.DataFrame:
    """결과 CSV 를 읽는다. mtime 은 쓰지 않고 캐시 키로만 둔다 — 러너가 파일을 다시 만들면 새로 읽는다."""
    return pd.read_csv(path, encoding=CSV_ENCODING)


def _value_label(experiment: str, value: float) -> str:
    """실험 값을 표시 문구로 바꾼다. 예: (매도 폭, 0.075) -> '7.5%', (이평선 기간, 200) -> '200일'."""
    if experiment in _PERCENT_EXPERIMENTS:
        return f"{value * 100:g}%"
    return f"{value:g}일"


def _select_base(df: pd.DataFrame, experiment: str, base_sell: float) -> pd.DataFrame:
    """실험 행을 고른다. 매도 폭 실험은 기준 매도 폭이 없다."""
    rows = df[df[DISPLAY_EXPERIMENT] == experiment]
    if experiment == EXPERIMENT_SELL:
        return rows
    return rows[(rows[DISPLAY_BASE_SELL] - base_sell).abs() < EPSILON]


def _with_value_labels(df: pd.DataFrame) -> pd.DataFrame:
    """값 표시 열을 더한다. 규칙 조합의 값은 규칙 이름이라 그대로 쓴다."""
    labeled = df.copy()
    numeric = pd.to_numeric(labeled[DISPLAY_VALUE], errors="coerce")
    labeled[_VALUE_LABEL] = [
        str(raw) if experiment == EXPERIMENT_RULE else _value_label(str(experiment), float(value))
        for raw, value, experiment in zip(labeled[DISPLAY_VALUE], numeric, labeled[DISPLAY_EXPERIMENT], strict=True)
    ]
    return labeled


# ============================================================
# 차트 · 표
# ============================================================


def _line_figure(rows: pd.DataFrame, experiment: str, metric: str, buy_and_hold: str, title: str) -> go.Figure:
    """값별 지표 선과 같은 구간 Buy & Hold 선을 그린다.

    Args:
        rows: 데이터 하나 · 실험 하나의 행 (값 오름차순)
        experiment: 실험 이름
        metric: 지표 열
        buy_and_hold: 같은 구간 Buy & Hold 열
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    is_percent = experiment in _PERCENT_EXPERIMENTS
    scale = 100.0 if is_percent else 1.0
    x_values = rows[DISPLAY_VALUE].astype(float) * scale

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=rows[metric],
            mode="lines+markers",
            name="규칙",
            line={"color": _STRATEGY_COLOR, "width": 2},
            marker={"size": 8},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=rows[buy_and_hold],
            mode="lines",
            name="Buy & Hold",
            line={"color": _BUY_AND_HOLD_COLOR, "width": 2, "dash": "dash"},
        )
    )
    for value, label in _MARKED_VALUES[experiment]:
        fig.add_vline(
            x=value * scale,
            line_width=1,
            line_color=_MARKER_LINE_COLOR,
            annotation_text=label,
            annotation_position="top",
        )
    fig.update_layout(
        title=title,
        height=_CHART_HEIGHT,
        hovermode="x unified",
        margin={"l": 50, "r": 20, "t": 60, "b": 40},
        xaxis_title=f"{experiment} ({'%' if is_percent else '거래일' if experiment == EXPERIMENT_MONTH else '일'})",
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.35, "x": 0},
    )
    return fig


def _render_trades(
    trades: pd.DataFrame,
    experiment: str,
    labels: list[str],
    default_labels: list[str],
    datasets: list[str],
    key: str,
) -> None:
    """값을 골라 거래 목록을 나란히 본다 — 값이 바뀔 때 어느 거래가 바뀌는지 보는 자리.

    Args:
        trades: 값 표시 열이 있는 그 실험의 거래 행
        experiment: 실험 이름
        labels: 고를 수 있는 값 (표시 순서)
        default_labels: 처음 고른 값
        datasets: 고를 수 있는 데이터
        key: 위젯 키 접두사
    """
    col_data, col_values = st.columns([1, 2])
    with col_data:
        dataset = st.selectbox("데이터", datasets, key=f"{key}_dataset")
    with col_values:
        chosen = st.multiselect(experiment, labels, default=default_labels, key=f"{key}_values")

    order = {label: position for position, label in enumerate(labels)}
    rows = trades[(trades[DISPLAY_DATASET] == dataset) & (trades[_VALUE_LABEL].isin(chosen))]
    rows = rows.assign(_order=rows[_VALUE_LABEL].map(order)).sort_values(["_order", DISPLAY_ENTRY_DATE])
    table = rows[[_VALUE_LABEL, DISPLAY_STATUS, DISPLAY_ENTRY_DATE, DISPLAY_EXIT_DATE, DISPLAY_PNL, DISPLAY_LOWEST]]
    st.dataframe(table.rename(columns={_VALUE_LABEL: experiment}), hide_index=True, width="stretch")


def _render_experiment(
    cells: pd.DataFrame,
    trades: pd.DataFrame,
    experiment: str,
    base_sell: float,
    datasets: list[str],
) -> None:
    """실험 하나의 차트 · 표 · 거래 목록을 그린다.

    Args:
        cells: 값 표시 열이 있는 칸 표
        trades: 값 표시 열이 있는 거래 표
        experiment: 실험 이름
        base_sell: 기준 매도 폭 (매도 폭 실험에는 쓰지 않는다)
        datasets: 고른 묶음의 데이터 이름
    """
    rows = _select_base(cells, experiment, base_sell)

    for dataset in datasets:
        dataset_rows = rows[rows[DISPLAY_DATASET] == dataset].sort_values(DISPLAY_VALUE)
        col_cagr, col_mdd = st.columns(2)
        with col_cagr:
            title = f"{dataset} — 연복리(%)"
            fig = _line_figure(dataset_rows, experiment, DISPLAY_CAGR, DISPLAY_BH_CAGR, title)
            st.plotly_chart(fig, width="stretch", key=f"{experiment}_{dataset}_cagr")
        with col_mdd:
            title = f"{dataset} — 최대 낙폭(%)"
            fig = _line_figure(dataset_rows, experiment, DISPLAY_MDD, DISPLAY_BH_MDD, title)
            st.plotly_chart(fig, width="stretch", key=f"{experiment}_{dataset}_mdd")

    with st.expander("표로 보기"):
        in_group = rows[rows[DISPLAY_DATASET].isin(datasets)]
        table = in_group[[DISPLAY_DATASET, _VALUE_LABEL, *_TABLE_METRICS]]
        st.dataframe(table.rename(columns={_VALUE_LABEL: experiment}), hide_index=True, width="stretch")

    st.subheader("값별 거래 목록")
    first_dataset = rows[rows[DISPLAY_DATASET] == datasets[0]].sort_values(DISPLAY_VALUE)
    labels = [str(label) for label in first_dataset[_VALUE_LABEL]]
    marked = [_value_label(experiment, value) for value, _ in _MARKED_VALUES[experiment]]
    # 값 표에 없는 기본값을 넘기면 Streamlit 이 예외 → 값 표를 바꿔도 탭이 열리게 걸러 냄
    defaults = [label for label in marked if label in labels]
    _render_trades(_select_base(trades, experiment, base_sell), experiment, labels, defaults, datasets, experiment)


def _render_rules(rules: pd.DataFrame, trades: pd.DataFrame, datasets: list[str]) -> None:
    """규칙 조합 표와 그 거래 목록을 그린다.

    Args:
        rules: 규칙 조합 표
        trades: 값 표시 열이 있는 거래 표
        datasets: 고른 묶음의 데이터 이름
    """
    st.subheader("규칙 조합")
    st.caption("눌림은 돌파 뒤 한달이 지나도 종가가 매수선 아래로 올 때까지 기다리는 조건입니다. 폭은 기본폭 × 레버리지 배수입니다.")
    in_group = rules[rules[DISPLAY_DATASET].isin(datasets)]
    st.dataframe(in_group[[DISPLAY_DATASET, DISPLAY_RULE, *_TABLE_METRICS]], hide_index=True, width="stretch")

    rule_names = [str(name) for name in in_group[DISPLAY_RULE].drop_duplicates()]
    with st.expander("규칙 조합의 거래 목록"):
        _render_trades(
            trades[trades[DISPLAY_EXPERIMENT] == EXPERIMENT_RULE], "규칙", rule_names, rule_names, datasets, "rules"
        )


# ============================================================
# 메인
# ============================================================


def main() -> None:
    """Streamlit 앱 메인 함수."""
    st.set_page_config(page_title="버퍼존 규칙 민감도", layout="wide")
    st.title("버퍼존 규칙 민감도")
    st.markdown(
        "값을 하나씩 바꾼 결과입니다. 합격 · 불합격은 없습니다. 볼 것: "
        "① 옆 값으로 옮겨도 부드럽게 변하는가, 계단처럼 뛰는가 "
        "② 차이가 몇 건의 거래에서 나오는가 "
        "③ 안 본 구간에서도 같은 모양인가 "
        "④ 1 · 2 · 3배와 S&P 500 에서 같은 모양인가 "
        "⑤ 결과를 보고 고른 값인가"
    )

    paths = [SENSITIVITY_RESULTS_DIR / name for name in (CELLS_FILENAME, RULES_FILENAME, TRADES_FILENAME)]
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        st.warning(
            f"결과 파일이 없습니다: {', '.join(missing)}. "
            "먼저 `poetry run python scripts/backtest/run_buffer_zone_sensitivity.py` 를 실행하세요."
        )
        return

    cells, rules, trades = (_load_csv(path, path.stat().st_mtime) for path in paths)
    cells = _with_value_labels(cells)
    trades = _with_value_labels(trades)

    col_group, col_base = st.columns(2)
    with col_group:
        group = st.radio("구간", (GROUP_SEEN, GROUP_UNSEEN, GROUP_FULL), horizontal=True)
    with col_base:
        base_sell = st.radio(
            "기준 매도 폭 (매수 폭 · 이평선 기간 · 한달 길이 실험의 고정값)",
            BASE_SELL_PCTS,
            format_func=lambda value: f"{value * 100:g}%",
            horizontal=True,
        )
    st.caption(_GROUP_NOTES[group])

    datasets = [dataset.label for dataset in DATASETS if dataset.group == group]
    _render_rules(rules, trades, datasets)

    st.subheader("값을 하나씩 바꾼 결과")
    st.caption(
        "네 실험의 고정값은 눌림 제거 · 이동평균 200일 · 한달 21거래일 · 매수 5% 입니다. " "V2 는 눌림이 있는 규칙이라 이 차트의 5% 점과 다르고, 위 규칙 조합 표에 있습니다."
    )
    for tab, experiment in zip(st.tabs(list(_EXPERIMENTS)), _EXPERIMENTS, strict=True):
        with tab:
            _render_experiment(cells[cells[DISPLAY_GROUP] == group], trades, experiment, base_sell, datasets)


if __name__ == "__main__":
    main()
