"""버퍼존 세 줄 대시보드

투자자별 결과 표, 가운데 매도 폭을 옮긴 고원 차트, 자산 곡선, 매도 내역을 한 페이지에 보여 준다.
합격 · 불합격을 내지 않는다 — 결과의 모양을 보고 판단한다 (계산: buffer_zone_three_lines).

선행 스크립트:
    poetry run python scripts/backtest/run_buffer_zone_three_lines.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_buffer_zone_three_lines.py
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.backtest.buffer_zone_sensitivity import (
    CSV_ENCODING,
    DISPLAY_BH_CAGR,
    DISPLAY_BH_MDD,
    DISPLAY_CAGR,
    DISPLAY_END,
    DISPLAY_ENTRY_DATE,
    DISPLAY_EXIT_DATE,
    DISPLAY_LOSSES,
    DISPLAY_LOWEST,
    DISPLAY_MDD,
    DISPLAY_PNL,
    DISPLAY_START,
    DISPLAY_STATUS,
    DISPLAY_WINS,
    DISPLAY_WORST,
)
from qbt.backtest.buffer_zone_three_lines import (
    CHECK_COST_CAP,
    CHECK_PRE_BUBBLE,
    DISPLAY_BH_DOTCOM,
    DISPLAY_BH_FINAL,
    DISPLAY_BH_MULTIPLE,
    DISPLAY_CENTER,
    DISPLAY_DOTCOM,
    DISPLAY_EQUITY_DATE,
    DISPLAY_FINAL,
    DISPLAY_FIRST_BUY,
    DISPLAY_FROM_PEAK,
    DISPLAY_HELD_AT_PEAK,
    DISPLAY_INVESTOR,
    DISPLAY_LEVERAGE,
    DISPLAY_METHOD,
    DISPLAY_SELL_LINE,
    DISPLAY_THREE_MULTIPLE,
    DOTCOM_END_DATE,
    DOTCOM_PEAK_DATE,
    EQUITY_FILENAME,
    INVESTOR_2004,
    INVESTOR_DOTCOM,
    INVESTORS_FILENAME,
    MAIN_INVESTORS,
    METHOD_ONE,
    METHOD_THREE,
    PLATEAU_FILENAME,
    SELL_LINES,
    THREE_LINES_RESULTS_DIR,
    THREE_LINES_TRADES_FILENAME,
)

# ============================================================
# 로컬 상수
# ============================================================

_PLATEAU_HEIGHT = 280
_EQUITY_HEIGHT = 340

# 세 줄은 파랑, Buy & Hold 는 주황, 한 줄은 청록 — 어느 차트에서도 같은 색. 밝은 · 어두운 화면 모두 색 검증기 통과
_THREE_COLOR = "#2a78d6"
_BUY_AND_HOLD_COLOR = "#d95926"
_ONE_COLOR = "#1d9e75"
_MARKER_LINE_COLOR = "#898781"

_LEVERAGES = (1, 2, 3)

# 투자자별 시세 이름 — 차트 제목에서 무엇을 돌렸는지 바로 보이게 함
_PRICE_NAMES = {
    INVESTOR_2004: {1: "QQQ", 2: "QLD", 3: "TQQQ"},
    INVESTOR_DOTCOM: {1: "나스닥 100", 2: "나스닥 100 × 2 합성", 3: "나스닥 100 × 3 합성"},
}

_INVESTOR_NOTES = {
    INVESTOR_2004: "2004-01-02 부터 빈손으로 시작해 현재까지 이어서 한 사람입니다. 저장소의 QQQ · QLD · TQQQ 시세입니다. QLD · TQQQ 상장 전은 합성입니다.",
    INVESTOR_DOTCOM: (
        "나스닥 100 지수(^NDX)로 1986-07-16 부터 빈손으로 시작해 닷컴버블을 겪고 현재까지 이어서 한 사람입니다. "
        "2 · 3배는 지수에 지금 비용 모델을 입힌 합성이고, 그때는 없던 상품입니다."
    ),
}

_CHECK_NOTES = {
    CHECK_COST_CAP: "비용 모델이 금리 5.33% 까지만 맞춘 값이라, 금리가 더 높던 달의 가산금리를 1.6% 로 묶어 본 판입니다. 2000 ~ 2001 년에도 걸립니다.",
    CHECK_PRE_BUBBLE: (
        "1999-12-22 시가에 이미 들고 있었다고 본 판으로, 버블 직전에 들어간 사람의 결과입니다. "
        "1999 년 이전 금리는 쓰지 않지만 QLD · TQQQ 상장 전 구간은 같은 비용 모델의 합성입니다."
    ),
}

_LIMITS = (
    "한계: 1999 년 이전 2 · 3배의 비용은 가정입니다. 1985 ~ 1999 의 지수는 시가가 전일 종가와 같은 날이 많아 밤사이 갭이 안 보이고, "
    "손절 체결이 실제보다 좋게 나옵니다(1987-10-19 가 대표적입니다). 지수에는 배당이 없어 Buy & Hold 와 나스닥 100 합성에 불리하고, "
    "현금 이자 0 은 세 줄에 불리합니다. 한 번의 역사이고 끝난 거래가 적습니다."
)

_SUMMARY_COLUMNS = [
    DISPLAY_INVESTOR,
    DISPLAY_LEVERAGE,
    DISPLAY_START,
    DISPLAY_END,
    DISPLAY_FIRST_BUY,
    DISPLAY_HELD_AT_PEAK,
    DISPLAY_FINAL,
    DISPLAY_CAGR,
    DISPLAY_MDD,
    DISPLAY_DOTCOM,
    DISPLAY_WINS,
    DISPLAY_LOSSES,
    DISPLAY_WORST,
    DISPLAY_BH_FINAL,
    DISPLAY_BH_CAGR,
    DISPLAY_BH_MDD,
    DISPLAY_BH_DOTCOM,
]

# 화면에서만 쓰는 이름 — 저장 열 「손익(%)」이 무엇 대비인지 표 안에서 읽히게 함
_PNL_LABEL = "진입가 대비 손익(%)"

_TRADE_COLUMNS = [
    DISPLAY_SELL_LINE,
    DISPLAY_STATUS,
    DISPLAY_ENTRY_DATE,
    DISPLAY_EXIT_DATE,
    _PNL_LABEL,
    DISPLAY_FROM_PEAK,
    DISPLAY_LOWEST,
]


# ============================================================
# 데이터
# ============================================================


@st.cache_data
def _load_csv(path: Path, mtime: float) -> pd.DataFrame:
    """결과 CSV 를 읽는다. mtime 은 쓰지 않고 캐시 키로만 둔다 — 러너가 파일을 다시 만들면 새로 읽는다."""
    return pd.read_csv(path, encoding=CSV_ENCODING)


def _summary_table(investors: pd.DataFrame) -> pd.DataFrame:
    """요약 표. 보유 몫은 비어 있는 칸(2004 투자자)이 있어 소수로 읽힌 값을 정수로 되돌린다."""
    table = investors[_SUMMARY_COLUMNS].copy()
    table[DISPLAY_HELD_AT_PEAK] = table[DISPLAY_HELD_AT_PEAK].astype("Int64")
    return table


# ============================================================
# 차트 · 표
# ============================================================


def _plateau_figure(rows: pd.DataFrame, metric: str, buy_and_hold: str, title: str) -> go.Figure:
    """가운데 매도 폭별 세 줄 · 한 줄과 같은 구간 Buy & Hold 선을 그린다.

    Args:
        rows: 투자자 하나 · 배수 하나의 고원 행
        metric: 지표 열
        buy_and_hold: 같은 구간 Buy & Hold 열
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    three = rows[rows[DISPLAY_METHOD] == METHOD_THREE].sort_values(DISPLAY_CENTER)
    one = rows[rows[DISPLAY_METHOD] == METHOD_ONE].sort_values(DISPLAY_CENTER)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=three[DISPLAY_CENTER],
            y=three[metric],
            mode="lines+markers",
            name=METHOD_THREE,
            line={"color": _THREE_COLOR, "width": 2},
            marker={"size": 8},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=one[DISPLAY_CENTER],
            y=one[metric],
            mode="lines+markers",
            name=METHOD_ONE,
            line={"color": _ONE_COLOR, "width": 2},
            marker={"size": 8},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=three[DISPLAY_CENTER],
            y=three[buy_and_hold],
            mode="lines",
            name="Buy & Hold",
            line={"color": _BUY_AND_HOLD_COLOR, "width": 2, "dash": "dash"},
        )
    )
    fig.add_vline(x=SELL_LINES[1] * 100.0, line_width=1, line_color=_MARKER_LINE_COLOR)
    fig.update_layout(
        title=title,
        height=_PLATEAU_HEIGHT,
        hovermode="x unified",
        margin={"l": 50, "r": 20, "t": 50, "b": 40},
        xaxis_title=DISPLAY_CENTER,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.45, "x": 0},
    )
    return fig


def _equity_figure(rows: pd.DataFrame, title: str) -> go.Figure:
    """세 줄과 Buy & Hold 의 자산 배수를 로그 축으로 그린다.

    Args:
        rows: 투자자 하나 · 배수 하나의 일별 자산 행
        title: 차트 제목

    Returns:
        Plotly Figure
    """
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=rows[DISPLAY_EQUITY_DATE],
            y=rows[DISPLAY_THREE_MULTIPLE],
            mode="lines",
            name=METHOD_THREE,
            line={"color": _THREE_COLOR, "width": 2},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=rows[DISPLAY_EQUITY_DATE],
            y=rows[DISPLAY_BH_MULTIPLE],
            mode="lines",
            name="Buy & Hold",
            line={"color": _BUY_AND_HOLD_COLOR, "width": 2},
        )
    )
    fig.update_layout(
        title=title,
        height=_EQUITY_HEIGHT,
        hovermode="x unified",
        margin={"l": 50, "r": 20, "t": 50, "b": 40},
        yaxis_type="log",
        yaxis_title="시작 = 1 (로그 축)",
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.25, "x": 0},
    )
    return fig


def _render_summary(investors: pd.DataFrame) -> None:
    """두 투자자의 결과 표와 접어 둔 대조 표를 그린다.

    Args:
        investors: 투자자 표
    """
    st.subheader("① 현재까지 이어서 했다면")
    st.caption(
        f"닷컴 구간은 {DOTCOM_PEAK_DATE} ~ {DOTCOM_END_DATE} 이고, 그 구간 안 고점 대비 낙폭입니다. "
        "닷컴 고점 날 보유 몫은 세 몫 중 그날 들고 있던 몫의 수입니다. 익절 · 손절은 몫별 매도 건수입니다. "
        "끝날이 다른 행을 견줄 때는 그 며칠의 등락이 최종 배수 차이에 섞입니다 — 레버리지만큼 크게 섞입니다."
    )
    main = investors[investors[DISPLAY_INVESTOR].isin(MAIN_INVESTORS)]
    st.dataframe(_summary_table(main), hide_index=True, width="stretch")

    with st.expander("대조 — 가정을 바꾸면 얼마나 달라지나"):
        for name, note in _CHECK_NOTES.items():
            st.markdown(f"**{name}**: {note}")
        checks = investors[investors[DISPLAY_INVESTOR].isin(tuple(_CHECK_NOTES))]
        st.dataframe(_summary_table(checks), hide_index=True, width="stretch")


def _render_plateau(plateau: pd.DataFrame, investor: str) -> None:
    """고원 차트 — 배수마다 연복리와 최대 낙폭.

    Args:
        plateau: 고른 투자자의 고원 행
        investor: 투자자 이름
    """
    st.subheader("② 고원이 있는가")
    st.caption(
        "고원은 값을 옆으로 옮겨도 결과가 비슷한 평평한 구간입니다. 가로축은 세 몫 가운데 매도선의 기본 폭이고, 세 줄은 그 값 ±2.5%, 한 줄은 그 값 하나입니다. "
        "세로선이 지금 값 10% 입니다. 폭은 배수만큼 넓어집니다(2배면 두 배). 선이 평평할수록 값을 잘못 골라도 결과가 크게 달라지지 않습니다."
    )
    for metric, buy_and_hold, label in (
        (DISPLAY_CAGR, DISPLAY_BH_CAGR, "연복리(%)"),
        (DISPLAY_MDD, DISPLAY_BH_MDD, "최대 낙폭(%)"),
    ):
        for column, leverage in zip(st.columns(len(_LEVERAGES)), _LEVERAGES, strict=True):
            with column:
                rows = plateau[plateau[DISPLAY_LEVERAGE] == leverage]
                title = f"{_PRICE_NAMES[investor][leverage]} — {label}"
                st.plotly_chart(
                    _plateau_figure(rows, metric, buy_and_hold, title),
                    width="stretch",
                    key=f"plateau_{investor}_{leverage}_{metric}",
                )


def _render_equity(equity: pd.DataFrame, investor: str) -> None:
    """자산 곡선.

    Args:
        equity: 고른 투자자의 일별 자산 행
        investor: 투자자 이름
    """
    st.subheader("③ 자산 곡선")
    for column, leverage in zip(st.columns(len(_LEVERAGES)), _LEVERAGES, strict=True):
        with column:
            rows = equity[equity[DISPLAY_LEVERAGE] == leverage]
            st.plotly_chart(
                _equity_figure(rows, _PRICE_NAMES[investor][leverage]),
                width="stretch",
                key=f"equity_{investor}_{leverage}",
            )


def _render_trades(trades: pd.DataFrame, investor: str) -> None:
    """매도 내역 — 배수별 탭. 보유 중인 몫은 마지막 종가로 평가한 값이다.

    Args:
        trades: 고른 투자자의 거래 행
        investor: 투자자 이름
    """
    st.subheader("④ 매도 내역")
    st.caption(
        "낙폭이 깊어도 산 값보다 높게 팔았으면 번 거래입니다. 보유 중 고점 대비가 크게 마이너스여도 진입가 대비 손익이 플러스면 익절입니다. "
        "몫은 매도선으로 구분합니다. 같은 날 사고 판 몫은 세 몫이 같은 값으로 따로 나옵니다."
    )
    labels = [f"{_PRICE_NAMES[investor][leverage]}" for leverage in _LEVERAGES]
    for tab, leverage in zip(st.tabs(labels), _LEVERAGES, strict=True):
        with tab:
            rows = trades[trades[DISPLAY_LEVERAGE] == leverage]
            rows = rows.rename(columns={DISPLAY_PNL: _PNL_LABEL}).sort_values([DISPLAY_ENTRY_DATE, DISPLAY_SELL_LINE])
            st.dataframe(rows[_TRADE_COLUMNS], hide_index=True, width="stretch")


# ============================================================
# 메인
# ============================================================


def main() -> None:
    """Streamlit 앱 메인 함수."""
    st.set_page_config(page_title="버퍼존 세 줄", layout="wide")
    st.title("버퍼존 세 줄")
    st.markdown(
        "돈을 3등분해 사는 규칙은 같게 두고, 파는 선만 이동평균 아래 7.5 · 10 · 12.5% 로 다르게 둔 규칙입니다(2 · 3배는 폭도 그 배수). "
        "팔린 몫만 다음 돌파 때 다시 삽니다. 합격 · 불합격은 없습니다."
    )

    paths = [
        THREE_LINES_RESULTS_DIR / name
        for name in (INVESTORS_FILENAME, THREE_LINES_TRADES_FILENAME, PLATEAU_FILENAME, EQUITY_FILENAME)
    ]
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        st.warning(
            f"결과 파일이 없습니다: {', '.join(missing)}. "
            "먼저 `poetry run python scripts/backtest/run_buffer_zone_three_lines.py` 를 실행하세요."
        )
        return

    investors, trades, plateau, equity = (_load_csv(path, path.stat().st_mtime) for path in paths)

    investor = st.radio("투자자 (② · ③ · ④ 에 적용)", MAIN_INVESTORS, horizontal=True)
    st.caption(_INVESTOR_NOTES[investor])

    _render_summary(investors)
    _render_plateau(plateau[plateau[DISPLAY_INVESTOR] == investor], investor)
    _render_equity(equity[equity[DISPLAY_INVESTOR] == investor], investor)
    _render_trades(trades[trades[DISPLAY_INVESTOR] == investor], investor)

    st.caption(_LIMITS)


if __name__ == "__main__":
    main()
