"""백테스트 전략별 시각화 대시보드 (동적 탭)

buffer_zone.CONFIGS와 buy_and_hold.CONFIGS에 등록된 전략의
결과 폴더를 탐색하여 각 전략마다 독립된 탭에서 시각화를 제공한다.

선행 스크립트:
    poetry run python scripts/backtest/run_single_backtest.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_single_backtest.py
"""

import json
from pathlib import Path
from typing import Any, TypedDict, cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component

from qbt.backtest.constants import (
    COL_BUY_BUFFER_PCT,
    COL_ENTRY_DATE,
    COL_ENTRY_PRICE,
    COL_EXIT_DATE,
    COL_EXIT_PRICE,
    COL_HOLD_DAYS_USED,
    COL_HOLDING_DAYS,
    COL_PNL,
    COL_PNL_PCT,
    COL_SHARES,
    EQUITY_FILENAME,
    SIGNAL_FILENAME,
    SUMMARY_FILENAME,
    TRADES_FILENAME,
)
from qbt.backtest.dashboard_charts import (
    build_equity_panes,
    build_monthly_heatmap,
    build_price_pane,
    build_trade_markers,
    chart_component_args,
)
from qbt.backtest.strategies.buffer_zone import CONFIGS as BZ_CONFIGS
from qbt.backtest.strategies.buy_and_hold import CONFIGS as BH_CONFIGS
from qbt.common_constants import COL_DATE

# ============================================================
# 로컬 상수 (이 파일에서만 사용)
# ============================================================

# --- 거래 내역 한글 컬럼 매핑 ---
TRADE_COLUMN_RENAME = {
    COL_ENTRY_DATE: "진입일",
    COL_EXIT_DATE: "청산일",
    COL_ENTRY_PRICE: "진입가",
    COL_EXIT_PRICE: "청산가",
    COL_SHARES: "수량",
    COL_PNL: "손익금액",
    COL_PNL_PCT: "손익률",
    COL_BUY_BUFFER_PCT: "매수버퍼존",
    COL_HOLD_DAYS_USED: "유지일",
    COL_HOLDING_DAYS: "보유기간(일)",
}


# ============================================================
# 전략 데이터 타입
# ============================================================


class StrategyData(TypedDict):
    """자동 탐색된 전략 데이터 컨테이너."""

    strategy_name: str
    display_name: str
    result_dir: Path
    summary_data: dict[str, Any]
    signal_df: pd.DataFrame
    equity_df: pd.DataFrame
    trades_df: pd.DataFrame


# ============================================================
# 전략 자동 탐색
# ============================================================


@st.cache_data
def _load_csv(path: Path, mtime: float) -> pd.DataFrame:
    """CSV를 로드하고 날짜 컬럼을 파싱한다. mtime 은 쓰지 않고 캐시 키로만 둔다 — 러너가 파일을 다시 만들면 새로 읽는다."""
    df = pd.read_csv(path)
    if COL_DATE in df.columns:
        df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
    return df


@st.cache_data
def _load_json(path: Path, mtime: float) -> dict[str, Any]:
    """JSON 파일을 로드한다. mtime 은 쓰지 않고 캐시 키로만 둔다 — 러너가 파일을 다시 만들면 새로 읽는다."""
    with path.open("r", encoding="utf-8") as f:
        return cast(dict[str, Any], json.load(f))


def _discover_strategies() -> list[StrategyData]:
    """CONFIGS에 등록된 전략의 결과 폴더를 탐색하여 전략 데이터를 로드한다.

    buffer_zone.CONFIGS와 buy_and_hold.CONFIGS의 result_dir을 순회하며,
    summary.json이 존재하는 전략만 로드한다.

    Returns:
        전략 데이터 리스트 (CONFIGS 등록 순서)
    """
    # CONFIGS에서 (strategy_name, result_dir) 수집
    config_dirs: list[tuple[str, Path]] = []
    for cfg in BZ_CONFIGS:
        config_dirs.append((cfg.strategy_name, cfg.result_dir))
    for cfg in BH_CONFIGS:
        config_dirs.append((cfg.strategy_name, cfg.result_dir))

    strategies: list[StrategyData] = []

    for strategy_name, result_dir in config_dirs:
        summary_path = result_dir / SUMMARY_FILENAME
        signal_path = result_dir / SIGNAL_FILENAME
        equity_path = result_dir / EQUITY_FILENAME
        trades_path = result_dir / TRADES_FILENAME

        # summary.json, signal.csv, equity.csv 필수
        if not summary_path.exists() or not signal_path.exists() or not equity_path.exists():
            continue

        summary_data = _load_json(summary_path, summary_path.stat().st_mtime)
        signal_df = _load_csv(signal_path, signal_path.stat().st_mtime)
        equity_df = _load_csv(equity_path, equity_path.stat().st_mtime)

        # trades는 선택 (Buy & Hold는 헤더만 있다)
        if trades_path.exists():
            trades_df = _load_csv(trades_path, trades_path.stat().st_mtime)
            if not trades_df.empty and COL_ENTRY_DATE in trades_df.columns:
                trades_df[COL_ENTRY_DATE] = pd.to_datetime(trades_df[COL_ENTRY_DATE]).dt.date
            if not trades_df.empty and COL_EXIT_DATE in trades_df.columns:
                trades_df[COL_EXIT_DATE] = pd.to_datetime(trades_df[COL_EXIT_DATE]).dt.date
        else:
            trades_df = pd.DataFrame()

        # display_name 필수 검증
        display_name = summary_data.get("display_name", "")
        if not display_name:
            raise ValueError(f"summary.json에 display_name이 없습니다: {summary_path}. " "run_single_backtest.py를 재실행하세요.")

        strategies.append(
            StrategyData(
                strategy_name=strategy_name,
                display_name=display_name,
                result_dir=result_dir,
                summary_data=summary_data,
                signal_df=signal_df,
                equity_df=equity_df,
                trades_df=trades_df,
            )
        )

    return strategies


# ============================================================
# 차트 렌더링 함수
# ============================================================


def _render_main_chart(
    strategy: StrategyData,
    chart_key: str,
) -> None:
    """메인 차트 — 캔들(이동평균 · 밴드 · 거래 마커) + 에쿼티 + 드로우다운.

    밴드와 툴팁의 에쿼티 · 드로우다운은 에쿼티 표에서 읽는다(매수 후 보유는 밴드가 없다).
    """
    open_position = strategy["summary_data"]["summary"].get("open_position")
    markers = build_trade_markers(
        strategy["trades_df"],
        open_entry_date=None if open_position is None else str(open_position["entry_date"]),
    )
    panes = [
        build_price_pane(strategy["signal_df"], strategy["equity_df"], markers, title=strategy["display_name"]),
        *build_equity_panes(strategy["equity_df"]),
    ]
    lightweight_charts_v5_component(
        **chart_component_args(panes, name=f"chart_{chart_key}", key=f"main_chart_{chart_key}")
    )


def _render_holding_period_histogram(trades_df: pd.DataFrame, *, chart_key: str) -> None:
    """포지션 보유 기간 분포 히스토그램을 Plotly로 렌더링한다 (거래가 있는 전략만 부른다)."""
    holding_days = trades_df[COL_HOLDING_DAYS].tolist()

    fig = go.Figure(
        data=go.Histogram(
            x=holding_days,
            nbinsx=min(30, max(5, len(holding_days))),
            marker_color="rgba(33, 150, 243, 0.7)",
            marker_line={"color": "rgba(33, 150, 243, 1)", "width": 1},
            hovertemplate="보유기간: %{x}일<br>빈도: %{y}<extra></extra>",
        )
    )

    fig.update_layout(
        xaxis_title="보유 기간 (일)",
        yaxis_title="빈도",
        height=300,
        bargap=0.05,
        margin={"l": 60, "r": 40, "t": 30, "b": 60},
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font={"color": "#D1D4DC"},
        xaxis={"gridcolor": "#1e222d"},
        yaxis={"gridcolor": "#1e222d"},
    )

    st.plotly_chart(fig, width="stretch", key=chart_key)


# ============================================================
# 전략 탭 렌더링
# ============================================================


def _style_pnl_rows(row: pd.Series) -> list[str]:
    """손익률 기반 행별 배경색을 반환한다.

    수익 거래는 옅은 초록, 손실 거래는 옅은 빨강 배경을 적용한다.
    """
    pnl = row[TRADE_COLUMN_RENAME[COL_PNL_PCT]]
    if pnl > 0:
        return ["background-color: rgba(38, 166, 154, 0.15)"] * len(row)
    elif pnl < 0:
        return ["background-color: rgba(239, 83, 80, 0.15)"] * len(row)
    return [""] * len(row)


def _render_strategy_tab(strategy: StrategyData) -> None:
    """하나의 전략 탭 내부를 렌더링한다."""
    summary_data = strategy["summary_data"]
    summary = summary_data["summary"]
    params = summary_data["params"]
    monthly_returns: list[dict[str, Any]] = summary_data["monthly_returns"]
    yearly_returns: list[dict[str, Any]] = summary_data["yearly_returns"]
    trades_df = strategy["trades_df"]
    has_trades = not trades_df.empty

    # ---- 요약 지표 ----
    st.header("요약 지표")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("총 수익률", f"{summary['total_return_pct']:.2f}%")
    with col2:
        st.metric("CAGR", f"{summary['cagr']:.2f}%")
    with col3:
        st.metric("MDD", f"{summary['mdd']:.2f}%")
    with col4:
        st.metric("Calmar", f"{summary['calmar']:.2f}")
    with col5:
        total_trades = int(summary["total_trades"])
        win_rate = float(summary["win_rate"])
        st.metric("거래수 / 승률", f"{total_trades}회 / {win_rate:.1f}%")

    st.divider()

    # ---- Section 1: 메인 차트 ----
    st.header("1. 메인 차트")
    _render_main_chart(strategy, strategy["strategy_name"])

    st.divider()

    # ---- Section 2: 전체 거래 상세 내역 ----
    st.header("2. 전체 거래 상세 내역")
    if has_trades:
        display_df = trades_df.copy()
        display_df[COL_PNL_PCT] = display_df[COL_PNL_PCT] * 100
        display_df = display_df.rename(columns=TRADE_COLUMN_RENAME)
        styled_df = display_df.style.apply(_style_pnl_rows, axis=1)
        st.dataframe(styled_df, width="stretch")
        st.caption(f"총 {len(trades_df)}건의 거래")
    else:
        st.info("이 전략에서는 거래 내역이 없습니다.")

    st.divider()

    # ---- Section 3: 사용 파라미터 ----
    st.header("3. 사용 파라미터")
    st.json(params)

    st.divider()

    # ---- Section 4: 월별 수익률 히트맵 ----
    st.header("4. 월별/연도별 수익률 히트맵")
    st.markdown("에쿼티 기준 월간 수익률을 연도별로 비교합니다.")
    strategy_name = strategy["strategy_name"]
    st.plotly_chart(
        build_monthly_heatmap(monthly_returns, yearly_returns), width="stretch", key=f"heatmap_{strategy_name}"
    )

    st.divider()

    # ---- Section 5: 포지션 보유 기간 분포 ----
    st.header("5. 포지션 보유 기간 분포")
    if has_trades:
        st.markdown("각 거래의 진입~청산 기간(일) 분포를 보여줍니다.")
        _render_holding_period_histogram(trades_df, chart_key=f"histogram_{strategy_name}")
    else:
        st.info("이 전략에서는 보유 기간 분포를 표시할 수 없습니다.")


# ============================================================
# 메인 앱
# ============================================================


def main() -> None:
    """Streamlit 앱 메인 함수."""
    st.set_page_config(
        page_title="백테스트 전략 대시보드",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )

    st.title("백테스트 전략 대시보드")
    st.markdown("전략별 백테스트 결과를 시각화합니다. 전략이 추가되면 자동으로 탭이 생성됩니다.")

    # ---- 전략 자동 탐색 ----
    strategies = _discover_strategies()

    if not strategies:
        st.warning(
            "결과 파일이 없습니다. 먼저 백테스트를 실행해주세요:\n\n" "```\npoetry run python scripts/backtest/run_single_backtest.py\n```"
        )
        st.stop()

    # ---- 동적 탭 생성 ----
    tab_labels = [s["display_name"] for s in strategies]
    tabs = st.tabs(tab_labels)

    for tab, strategy in zip(tabs, strategies, strict=True):
        with tab:
            _render_strategy_tab(strategy)

    # ---- 푸터 ----
    st.markdown("---")
    st.caption("QBT (Quant BackTest) - 백테스트 전략 대시보드")


if __name__ == "__main__":
    main()
