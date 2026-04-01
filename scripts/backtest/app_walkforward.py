"""워크포워드 검증(WFO) 결과 시각화 대시보드

run_walkforward.py의 2-Mode(Dynamic/Fully Fixed) WFO 결과를
시각화하여 과최적화 검증 결과를 확인한다.
QQQ와 TQQQ를 나란히 비교하는 통합 뷰를 제공한다.

선행 스크립트:
    poetry run python scripts/backtest/run_walkforward.py

실행 명령어:
    poetry run streamlit run scripts/backtest/app_walkforward.py

화면 구성 (전략 통합 뷰):
- 모드별 요약 비교: 4열 테이블 (QQQ/TQQQ × Dynamic/Fixed)
- Stitched Equity 곡선: 좌우 배치 (좌=QQQ, 우=TQQQ)
- IS vs OOS 성과 비교: 좌우 배치 바차트
- 파라미터 추이: 서브플롯에 QQQ/TQQQ 오버레이
"""

import json
from datetime import date
from pathlib import Path
from typing import cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from lightweight_charts_v5 import lightweight_charts_v5_component  # type: ignore[import-untyped]
from plotly.subplots import make_subplots

from qbt.backtest.constants import (
    WALKFORWARD_DYNAMIC_FILENAME,
    WALKFORWARD_EQUITY_DYNAMIC_FILENAME,
    WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME,
    WALKFORWARD_FULLY_FIXED_FILENAME,
    WALKFORWARD_SUMMARY_FILENAME,
    WFO_WINDOWS_DYNAMIC_DIR,
    WFO_WINDOWS_FULLY_FIXED_DIR,
)
from qbt.common_constants import (
    BACKTEST_RESULTS_DIR,
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
)

# ============================================================
# 로컬 상수
# ============================================================

# 차트 높이
_CHART_HEIGHT = 500
_SUB_CHART_HEIGHT = 350

# 전략 표시명 매핑
_STRATEGY_DISPLAY_NAMES: dict[str, str] = {
    "buffer_zone_tqqq": "TQQQ",
    "buffer_zone_qqq": "QQQ",
}

# 전략별 차트 색상
_STRATEGY_COLORS: dict[str, str] = {
    "buffer_zone_qqq": "#1f77b4",
    "buffer_zone_tqqq": "#d62728",
}

# --- 윈도우 상세 차트 상수 ---
_WINDOW_CANDLE_HEIGHT = 500
_WINDOW_EQUITY_HEIGHT = 200
_WINDOW_DRAWDOWN_HEIGHT = 150
_WINDOW_ZOOM_LEVEL = 99999

# 차트 색상 (app_single_backtest.py 패턴)
_COLOR_UP = "rgb(38, 166, 154)"
_COLOR_DOWN = "rgb(239, 83, 80)"
_COLOR_MA_LINE = "rgba(255, 152, 0, 0.9)"
_COLOR_UPPER_BAND = "rgba(33, 150, 243, 0.6)"
_COLOR_LOWER_BAND = "rgba(244, 67, 54, 0.6)"
_COLOR_BUY_MARKER = "#26a69a"
_COLOR_SELL_MARKER = "#ef5350"
_COLOR_EQUITY_LINE = "rgba(33, 150, 243, 1)"
_COLOR_EQUITY_TOP = "rgba(33, 150, 243, 0.3)"
_COLOR_EQUITY_BOTTOM = "rgba(33, 150, 243, 0.05)"
_COLOR_DRAWDOWN_LINE = "rgba(244, 67, 54, 1)"
_COLOR_DRAWDOWN_TOP = "rgba(244, 67, 54, 0.3)"
_COLOR_DRAWDOWN_BOTTOM = "rgba(244, 67, 54, 0.05)"

# 지표 선택 옵션 매핑 (표시명 → (전략명, 모드 디렉토리명, WFO CSV 파일명))
_METRIC_OPTIONS: dict[str, tuple[str, str, str]] = {
    "QQQ Dynamic": ("buffer_zone_qqq", WFO_WINDOWS_DYNAMIC_DIR, WALKFORWARD_DYNAMIC_FILENAME),
    "QQQ Fixed": ("buffer_zone_qqq", WFO_WINDOWS_FULLY_FIXED_DIR, WALKFORWARD_FULLY_FIXED_FILENAME),
    "TQQQ Dynamic": ("buffer_zone_tqqq", WFO_WINDOWS_DYNAMIC_DIR, WALKFORWARD_DYNAMIC_FILENAME),
    "TQQQ Fixed": ("buffer_zone_tqqq", WFO_WINDOWS_FULLY_FIXED_DIR, WALKFORWARD_FULLY_FIXED_FILENAME),
}

# ============================================================
# 데이터 로딩 (캐시)
# ============================================================


def _discover_wfo_strategies() -> dict[str, Path]:
    """WFO 결과가 존재하는 전략 디렉토리를 탐색한다.

    Returns:
        전략명 → 디렉토리 경로 딕셔너리
    """
    results: dict[str, Path] = {}
    if not BACKTEST_RESULTS_DIR.exists():
        return results

    for sub_dir in sorted(BACKTEST_RESULTS_DIR.iterdir()):
        if sub_dir.is_dir() and (sub_dir / WALKFORWARD_SUMMARY_FILENAME).exists():
            results[sub_dir.name] = sub_dir

    return results


@st.cache_data
def _load_summary(result_dir_str: str) -> dict[str, object] | None:
    """walkforward_summary.json을 로드한다.

    Args:
        result_dir_str: 결과 디렉토리 경로 (문자열, 캐시 키용)

    Returns:
        요약 딕셔너리 또는 None
    """
    path = Path(result_dir_str) / WALKFORWARD_SUMMARY_FILENAME
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def _load_window_csv(result_dir_str: str, filename: str) -> pd.DataFrame | None:
    """윈도우 결과 CSV를 로드한다.

    Args:
        result_dir_str: 결과 디렉토리 경로 (문자열, 캐시 키용)
        filename: CSV 파일명

    Returns:
        DataFrame 또는 None
    """
    path = Path(result_dir_str) / filename
    if not path.exists():
        return None
    return pd.read_csv(path)


@st.cache_data
def _load_equity_csv(result_dir_str: str, filename: str) -> pd.DataFrame | None:
    """Stitched Equity CSV를 로드한다.

    Args:
        result_dir_str: 결과 디렉토리 경로 (문자열, 캐시 키용)
        filename: CSV 파일명

    Returns:
        DataFrame 또는 None
    """
    path = Path(result_dir_str) / filename
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
    return df


def _get_display_name(strategy_name: str) -> str:
    """전략의 표시명을 반환한다."""
    return _STRATEGY_DISPLAY_NAMES.get(strategy_name, strategy_name)


# ============================================================
# 섹션 1: 모드별 요약 비교
# ============================================================


def _render_mode_summary(summaries: dict[str, dict[str, object]]) -> None:
    """모든 전략의 Dynamic vs Fully Fixed 핵심 지표를 4열 테이블로 비교한다."""
    st.header("모드별 요약 비교 (Dynamic vs Fully Fixed)")

    # 지표 목록 (표시명, JSON 키, 접미사)
    metrics: list[tuple[str, str, str]] = [
        ("Stitched CAGR", "stitched_cagr", "%"),
        ("Stitched MDD", "stitched_mdd", "%"),
        ("Stitched Calmar", "stitched_calmar", ""),
        ("OOS CAGR 평균", "oos_cagr_mean", "%"),
        ("OOS MDD 최악", "oos_mdd_worst", "%"),
        ("WFE Calmar Robust", "wfe_calmar_robust", ""),
        ("PC 최대", "profit_concentration_max", ""),
        ("OOS 총 거래수", "oos_trades_total", ""),
    ]

    # DataFrame 구성
    rows: list[dict[str, object]] = []
    for display_name, key, suffix in metrics:
        row: dict[str, object] = {"지표": display_name}
        for strat_name, summary in summaries.items():
            label = _get_display_name(strat_name)
            dynamic = summary.get("dynamic")
            fully_fixed = summary.get("fully_fixed")

            if isinstance(dynamic, dict):
                val = dynamic.get(key, "N/A")
                row[f"{label} Dynamic"] = f"{val}{suffix}" if val != "N/A" else "N/A"
            else:
                row[f"{label} Dynamic"] = "N/A"

            if isinstance(fully_fixed, dict):
                val = fully_fixed.get(key, "N/A")
                row[f"{label} Fixed"] = f"{val}{suffix}" if val != "N/A" else "N/A"
            else:
                row[f"{label} Fixed"] = "N/A"

        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")

    # VERBATIM
    st.markdown(
        r"""## 지표에 사용하는 용어에 대한 설명

- **Dynamic 모드**: 매 WFO 윈도우마다 IS(In-Sample) 구간에서 그리드 서치로 최적 파라미터를 새로 선택하는 방식
- **Fully Fixed 모드**: 첫 번째 윈도우의 IS 최적 파라미터를 모든 윈도우에 고정 적용하는 방식
- **Stitched Equity**: 각 윈도우의 OOS 구간을 연결하여 만든 연속 자본곡선
- **Stitched CAGR(%)**: Stitched Equity의 연환산 복리 수익률
- **Stitched MDD(%)**: Stitched Equity의 최대 낙폭 (음수가 클수록 큰 손실)
- **Stitched Calmar**: CAGR / |MDD| (높을수록 위험 대비 수익이 좋음)
- **OOS CAGR 평균(%)**: 전체 윈도우 OOS 구간 CAGR의 평균
- **OOS MDD 최악(%)**: 전체 윈도우 중 가장 큰 OOS 낙폭
- **WFE Calmar Robust**: IS Calmar > 0인 윈도우만 필터링한 WFE Calmar 중앙값 (이상치 제거)
- **PC 최대(Profit Concentration)**: 전체 수익 중 단일 윈도우가 기여한 최대 비중 (0\~1, 낮을수록 고르게 분산)
- **OOS 총 거래수**: 모든 OOS 윈도우에서 발생한 거래의 합계

## 지표를 해석하는 방법

- **Dynamic vs Fully Fixed 비교**: Dynamic이 Fully Fixed보다 현저히 좋다면 파라미터 적응이 유효한 것이고, 비슷하거나 나쁘다면 고정 파라미터로도 충분함을 시사합니다
- **Stitched Calmar**: 1 이상이면 위험 대비 수익이 양호, 0에 가까우면 수익 대비 손실이 크다는 의미
- **WFE Calmar Robust**: 1에 가까우면 IS 성과가 OOS에서도 유지됨을 의미 (과최적화 아님). 0 또는 음수면 IS 성과가 OOS에서 재현되지 않음 (과최적화 의심)
- **PC 최대**: 0.5 이상이면 수익이 특정 윈도우에 집중되어 있어 전략 안정성에 주의 필요

## 현재 지표 해석 & 판단(결과)

**QQQ** (현재 결과 기준):

- 한 줄 요약: **파라미터를 매번 바꾸든 처음 것을 고정하든 결과 차이는 크지 않습니다.** 고정 파라미터(4P)가 충분히 안정적입니다.
- Dynamic CAGR 11.33%와 Fixed CAGR 11.97%는 0.64%p 차이로 사실상 비슷합니다. Fixed가 오히려 약간 높은 것은 "파라미터를 바꾸지 않아도 된다"는 해석과 잘 맞습니다.
- WFE Calmar Robust가 Dynamic/Fixed 모두 0.93입니다. IS 성과의 약 93%가 OOS에서 재현된다는 뜻으로 양호한 수준입니다. 다만 이 지표 하나만으로 전략의 robustness를 강하게 주장하기보다는, 보조 검증 근거로 해석하는 것이 적절합니다.
- PC 최대 0.45는 0.5 미만으로 수익이 비교적 고르게 분산되어 있어 양호합니다.

**TQQQ** (현재 결과 기준):

- 한 줄 요약: **Dynamic과 Fixed의 상대 성과 차이는 작아 동적 재최적화의 가치는 낮습니다.** 다만 WFO 기준 OOS 재현성이 낮아 실전 기대치는 보수적으로 봐야 합니다.
- Dynamic CAGR 24.84%와 Fixed CAGR 26.27%는 Fixed가 약간 높습니다. 이 관계는 "동적으로 파라미터를 계속 바꾼다고 해서 더 좋아지지 않는다"는 해석과 일치합니다.
- WFE Calmar Robust는 Dynamic 0.19, Fixed 0.04로 매우 낮습니다. 이는 IS 성과의 19%(Dynamic) 또는 4%(Fixed)만 OOS에서 재현된다는 뜻으로, TQQQ는 stitched 성과와 별개로 OOS 재현성이 낮습니다.
- PC 최대 0.69는 0.5를 초과하여 수익이 특정 윈도우(W9, 2023~2025 AI 랠리)에 집중되어 있습니다. 레버리지 상품의 구조적 특성이 반영된 결과일 수 있으나, 특정 구간 의존성이 크다는 점에서 리스크 요인으로 해석해야 합니다."""
    )

    st.divider()


# ============================================================
# 섹션 2: Stitched Equity 곡선
# ============================================================


def _render_stitched_equity(strategy_dirs: dict[str, Path]) -> None:
    """QQQ/TQQQ Stitched Equity 곡선을 좌우 서브플롯으로 비교한다."""
    st.header("Stitched Equity 곡선 비교")

    strategy_names = list(strategy_dirs.keys())
    n_strategies = len(strategy_names)

    fig = make_subplots(
        rows=1,
        cols=n_strategies,
        subplot_titles=[_get_display_name(s) for s in strategy_names],
        horizontal_spacing=0.06,
    )

    for col_idx, strat_name in enumerate(strategy_names, start=1):
        result_dir_str = str(strategy_dirs[strat_name])
        eq_dynamic = _load_equity_csv(result_dir_str, WALKFORWARD_EQUITY_DYNAMIC_FILENAME)
        eq_fixed = _load_equity_csv(result_dir_str, WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME)

        if eq_dynamic is None and eq_fixed is None:
            fig.add_annotation(
                text="데이터 없음",
                xref=f"x{col_idx}",
                yref=f"y{col_idx}",
                x=0.5,
                y=0.5,
                showarrow=False,
                font={"size": 16, "color": "gray"},
            )
            continue

        if eq_dynamic is not None:
            fig.add_trace(
                go.Scatter(
                    x=eq_dynamic["Date"],
                    y=eq_dynamic["equity"],
                    mode="lines",
                    name="Dynamic",
                    line={"color": "#1f77b4", "width": 1.5},
                    legendgroup="dynamic",
                    showlegend=(col_idx == 1),
                ),
                row=1,
                col=col_idx,
            )

        if eq_fixed is not None:
            fig.add_trace(
                go.Scatter(
                    x=eq_fixed["Date"],
                    y=eq_fixed["equity"],
                    mode="lines",
                    name="Fully Fixed",
                    line={"color": "#ff7f0e", "width": 1.5},
                    legendgroup="fixed",
                    showlegend=(col_idx == 1),
                ),
                row=1,
                col=col_idx,
            )

        fig.update_yaxes(title_text="Equity (원)", row=1, col=col_idx)

    fig.update_layout(
        title="Stitched Equity (OOS 구간 연결)",
        height=_CHART_HEIGHT,
        legend={"yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01},
    )
    for col_idx in range(1, n_strategies + 1):
        fig.update_xaxes(title_text="날짜", row=1, col=col_idx)

    st.plotly_chart(fig, width="stretch")

    # VERBATIM
    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **Stitched Equity**: 각 WFO 윈도우의 OOS(Out-of-Sample) 구간 자본곡선을 시간순으로 이어붙인 연속 곡선
- **Dynamic(파란색)**: 매 윈도우마다 IS에서 새로 최적화한 파라미터로 OOS를 실행한 결과
- **Fully Fixed(주황색)**: 첫 윈도우의 IS 최적 파라미터를 모든 OOS 구간에 고정 적용한 결과

## 지표를 해석하는 방법

- 두 곡선이 **비슷한 궤적**이면: 파라미터 변경의 효과가 작아 고정 파라미터로도 충분
- **Dynamic이 현저히 위에** 있으면: 파라미터 적응(re-optimization)이 유효
- **Fully Fixed가 위에** 있으면: Dynamic 모드에서 과최적화가 발생하여 오히려 성과 악화
- 큰 낙폭 구간이 있다면 해당 시기의 시장 상황(금융위기, 급락장 등)과 대조하여 해석

## 현재 지표 해석 & 판단(결과)

**QQQ** (현재 결과 기준):

- 한 줄 요약: **두 곡선의 큰 흐름은 유사하지만, 후반부 성과와 낙폭은 Fully Fixed가 더 낫습니다.**
- 파란선(Dynamic)과 주황선(Fully Fixed)은 방향 자체는 거의 비슷합니다. 다만 2020년 이후에는 Fixed가 위쪽에 위치하는 구간이 더 많고, 낙폭도 더 얕습니다.
- 따라서 이 차트의 핵심 메시지는 "둘이 완전히 같다"가 아니라 **"재최적화가 추가 가치를 만들지 못하고, Fixed가 오히려 더 유리하다"** 입니다.
- 이 차트는 QQQ의 고정 파라미터가 충분히 안정적이라는 점을 시각적으로 보여주는 자료로 해석합니다.

**TQQQ** (현재 결과 기준):

- 한 줄 요약: **Dynamic이 Fixed를 압도하지 못하며, 시각적으로도 Fully Fixed가 더 우세한 구간이 많습니다.**
- 레버리지 특성상 두 곡선 모두 변동 폭이 매우 크지만, 상승 국면과 회복 국면에서 Fixed가 더 높은 자본곡선을 유지하는 구간이 반복됩니다.
- 이 차트는 "적응형 최적화가 필요하다"기보다 **"동적으로 바꿔도 추가 이점이 없고, 오히려 Fixed가 더 낫다"** 는 쪽으로 읽는 것이 맞습니다.
- 다만 TQQQ는 곡선 자체가 몇 개 강한 랠리 구간에 크게 의존하므로, stitched 곡선이 높다고 해서 OOS 재현성까지 좋다고 해석하면 안 됩니다."""
    )

    st.divider()


# ============================================================
# 섹션 3: IS vs OOS 성과 비교
# ============================================================


def _render_is_vs_oos(strategy_dirs: dict[str, Path]) -> None:
    """윈도우별 IS vs OOS 성과를 좌우 서브플롯으로 비교한다."""
    st.header("윈도우별 IS vs OOS 성과 비교 (Dynamic)")

    strategy_names = list(strategy_dirs.keys())
    n_strategies = len(strategy_names)

    # (a) CAGR 비교
    fig_cagr = make_subplots(
        rows=1,
        cols=n_strategies,
        subplot_titles=[_get_display_name(s) for s in strategy_names],
        horizontal_spacing=0.06,
    )

    for col_idx, strat_name in enumerate(strategy_names, start=1):
        result_dir_str = str(strategy_dirs[strat_name])
        dynamic_df = _load_window_csv(result_dir_str, WALKFORWARD_DYNAMIC_FILENAME)

        if dynamic_df is None:
            continue

        window_labels = [
            f"W{row['window_idx']} ({row['oos_start'][:7]}~{row['oos_end'][:7]})" for _, row in dynamic_df.iterrows()
        ]

        fig_cagr.add_trace(
            go.Bar(
                x=window_labels,
                y=dynamic_df["is_cagr"],
                name="IS CAGR",
                marker_color="#2ca02c",
                opacity=0.7,
                legendgroup="is_cagr",
                showlegend=(col_idx == 1),
            ),
            row=1,
            col=col_idx,
        )
        fig_cagr.add_trace(
            go.Bar(
                x=window_labels,
                y=dynamic_df["oos_cagr"],
                name="OOS CAGR",
                marker_color="#d62728",
                opacity=0.7,
                legendgroup="oos_cagr",
                showlegend=(col_idx == 1),
            ),
            row=1,
            col=col_idx,
        )
        fig_cagr.update_yaxes(title_text="CAGR (%)", row=1, col=col_idx)

    fig_cagr.update_layout(
        title="윈도우별 CAGR 비교 (IS vs OOS)",
        barmode="group",
        height=_SUB_CHART_HEIGHT,
        legend={"yanchor": "top", "y": 0.99, "xanchor": "right", "x": 0.99},
    )
    st.plotly_chart(fig_cagr, width="stretch")

    # (b) Calmar 비교
    fig_calmar = make_subplots(
        rows=1,
        cols=n_strategies,
        subplot_titles=[_get_display_name(s) for s in strategy_names],
        horizontal_spacing=0.06,
    )

    for col_idx, strat_name in enumerate(strategy_names, start=1):
        result_dir_str = str(strategy_dirs[strat_name])
        dynamic_df = _load_window_csv(result_dir_str, WALKFORWARD_DYNAMIC_FILENAME)

        if dynamic_df is None:
            continue

        window_labels = [
            f"W{row['window_idx']} ({row['oos_start'][:7]}~{row['oos_end'][:7]})" for _, row in dynamic_df.iterrows()
        ]

        fig_calmar.add_trace(
            go.Bar(
                x=window_labels,
                y=dynamic_df["is_calmar"],
                name="IS Calmar",
                marker_color="#2ca02c",
                opacity=0.7,
                legendgroup="is_calmar",
                showlegend=(col_idx == 1),
            ),
            row=1,
            col=col_idx,
        )
        fig_calmar.add_trace(
            go.Bar(
                x=window_labels,
                y=dynamic_df["oos_calmar"],
                name="OOS Calmar",
                marker_color="#d62728",
                opacity=0.7,
                legendgroup="oos_calmar",
                showlegend=(col_idx == 1),
            ),
            row=1,
            col=col_idx,
        )
        fig_calmar.update_yaxes(title_text="Calmar", row=1, col=col_idx)

    fig_calmar.update_layout(
        title="윈도우별 Calmar 비교 (IS vs OOS)",
        barmode="group",
        height=_SUB_CHART_HEIGHT,
        legend={"yanchor": "top", "y": 0.99, "xanchor": "right", "x": 0.99},
    )
    st.plotly_chart(fig_calmar, width="stretch")

    # VERBATIM
    st.markdown(
        r"""## 지표에 사용하는 용어에 대한 설명

- **IS(In-Sample)**: 전략 파라미터를 최적화하는 데 사용한 과거 데이터 구간
- **OOS(Out-of-Sample)**: IS에서 선택한 파라미터를 적용하여 독립적으로 평가하는 미래 구간
- **IS 성과(초록 막대)**: IS 구간에서 그리드 서치 후, 최고 Calmar 파라미터의 단일 백테스트 성과
- **OOS 성과(빨간 막대)**: IS 최적 파라미터를 OOS 구간에 그대로 적용한 단일 백테스트 성과
- **CAGR(%)**: 연환산 복리 수익률 (높을수록 좋음)
- **Calmar**: CAGR / |MDD| (위험 대비 수익 효율)

## 지표를 해석하는 방법

- IS와 OOS 막대가 **비슷한 높이**: IS에서의 성과가 OOS에서도 재현 → 과최적화 아님
- IS가 높고 OOS가 **크게 낮음**: IS에서 과적합(overfitting)이 발생하여 OOS에서 성과 악화
- OOS가 **음수**: 해당 기간에 전략이 손실을 기록했음을 의미
- 특정 윈도우만 OOS가 극단적: 해당 시기의 시장 환경(금융위기 등)이 전략에 불리했을 가능성

## 현재 지표 해석 & 판단(결과)

**그래프 읽는 법**: 각 윈도우(W0~W10)마다 녹색(IS)과 빨간색(OOS) 막대가 나란히 서 있습니다. 녹색은 "연습 성적", 빨간색은 "본시험 성적"이라고 생각하면 됩니다. 빨간색이 녹색과 비슷하거나 높으면 과최적화 우려가 낮고, 빨간색이 훨씬 낮으면 IS에서만 좋고 OOS에서 무너지는 과최적화를 의심해야 합니다.

**QQQ** (현재 결과 기준):

- 일부 윈도우는 OOS 성과가 IS보다 강하고, 일부 윈도우는 OOS가 낮거나 음수입니다. 따라서 현재 패턴은 "전 구간에서 OOS가 더 좋다"기보다 **윈도우별 편차는 있으나 전체적으로는 버틸 만한 수준**으로 해석하는 것이 맞습니다.
- 초기 일부 윈도우의 부진은 존재하지만, 전체적으로 극단적인 IS→OOS 붕괴 패턴은 아닙니다.
- 이 섹션은 QQQ가 강하게 과최적화됐다는 증거는 아니라는 점을 보여주는 **보조 자료**로 해석합니다.

**TQQQ** (현재 결과 기준):

- 몇몇 윈도우는 OOS가 매우 강하지만, 다른 윈도우는 음수이거나 부진합니다. 따라서 현재 패턴은 **일부 강한 랠리 구간이 전체 stitched 성과를 끌어올리는 비대칭 구조**에 가깝습니다.
- 이 섹션이 보여주는 것은 높은 일반화 능력이라기보다, **TQQQ가 시장 국면에 매우 민감하고 레짐 의존성이 크다**는 점입니다.
- 따라서 TQQQ는 stitched 성과만 보고 낙관적으로 해석하면 안 되며, OOS 재현성은 보수적으로 봐야 합니다."""
    )

    st.divider()


# ============================================================
# 섹션 4: 파라미터 추이
# ============================================================


def _render_param_drift(summaries: dict[str, dict[str, object]]) -> None:
    """전략별 Dynamic 모드의 파라미터 변화를 오버레이하여 시각화한다."""
    st.header("파라미터 추이 (Dynamic 모드)")

    param_keys = [
        ("param_ma_windows", "MA Window"),
        ("param_buy_buffers", "Buy Buffer (%)"),
        ("param_sell_buffers", "Sell Buffer (%)"),
        ("param_hold_days", "Hold Days"),
    ]

    # 4개 서브플롯
    fig = make_subplots(
        rows=4,
        cols=1,
        subplot_titles=[label for _, label in param_keys],
        vertical_spacing=0.10,
    )

    strategy_names = list(summaries.keys())

    for i, (key, _label) in enumerate(param_keys, start=1):
        for strat_name in strategy_names:
            summary = summaries[strat_name]
            dynamic = summary.get("dynamic")
            if not isinstance(dynamic, dict):
                continue

            values = dynamic.get(key, [])
            if not isinstance(values, list) or len(values) == 0:
                continue

            x_labels = list(range(len(values)))

            # buy/sell buffer는 %로 표시
            if "buffer" in key.lower():
                y_values = [v * 100 for v in values]
            else:
                y_values = values

            color = _STRATEGY_COLORS.get(strat_name, "#333333")
            display = _get_display_name(strat_name)

            fig.add_trace(
                go.Scatter(
                    x=x_labels,
                    y=y_values,
                    mode="lines+markers",
                    name=display,
                    marker={"size": 7},
                    line={"color": color},
                    legendgroup=strat_name,
                    showlegend=(i == 1),
                ),
                row=i,
                col=1,
            )

    fig.update_layout(
        height=250 * 5,
        title_text="윈도우별 선택 파라미터 추이 (Dynamic)",
    )

    # X축 레이블 설정
    for i in range(1, 6):
        fig.update_xaxes(title_text="윈도우 인덱스", row=i, col=1)

    st.plotly_chart(fig, width="stretch")

    # VERBATIM
    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **MA Window**: 이동평균 기간 (예: 100, 150, 200일)
- **Buy Buffer(%)**: 매수 진입 허용 범위 (MA 상단 밴드). 값이 클수록 보수적 진입
- **Sell Buffer(%)**: 매도 청산 허용 범위 (MA 하단 밴드). 값이 클수록 보수적 청산
- **Hold Days**: 신호 확정까지 대기하는 유지조건 일수

## 지표를 해석하는 방법

- 파라미터가 윈도우마다 **크게 변동**: 최적 파라미터가 시장 환경에 민감 → 고정 파라미터 사용 시 주의 필요
- 파라미터가 **안정적으로 유지**: 특정 값 주위에 수렴 → 해당 값을 고정 파라미터로 사용해도 안전
- 특정 시점에서 **급격히 변화**: 시장 구조 변화(regime change)와 맞물릴 가능성
- Fully Fixed 모드는 파라미터가 항상 동일하므로 시각화 불필요 (모든 윈도우 동일값)

## 현재 지표 해석 & 판단(결과)

**그래프 읽는 법**: 선이 수평에 가까우면 "어떤 시기든 같은 파라미터가 최적"이라는 뜻이고, 위아래로 요동치면 "시기마다 최적 파라미터가 달라진다"는 뜻입니다. 선이 안정적일수록 고정 파라미터를 사용해도 안전합니다.

**QQQ** (현재 결과 기준):

- **MA Window = 200:** 전 윈도우에서 동일합니다.
- **Buy Buffer:** W1만 1%이고, 나머지는 3%입니다.
- **Sell Buffer = 5%:** 전 윈도우에서 동일합니다.
- **Hold Days:** 3 → 5 → 3으로 움직인 뒤 빠르게 3에 수렴합니다.
- 의미: 파라미터는 초반 노이즈 이후 현재 확정값(MA=200, buy=3%, sell=5%, hold=3)으로 자연스럽게 수렴합니다. 이는 **4P 동결 원칙의 근거**입니다.

**TQQQ** (현재 결과 기준):

- **MA Window:** 초기에 150 → 100 → 150으로 흔들린 뒤 150에 수렴합니다.
- **Buy Buffer = 3%:** 전 윈도우에서 동일합니다.
- **Sell Buffer:** W1만 1%이고, 나머지는 5%입니다.
- **Hold Days:** 5 → 0 → 5 이후, W3부터 3으로 수렴합니다.
- 의미: 시간이 지나며 파라미터 불안정성은 줄고, 고정값으로 수렴합니다. 다만 **파라미터 안정성은 동결 원칙의 근거일 뿐, TQQQ의 OOS 재현성이 높다는 뜻은 아닙니다.** 파라미터 안정성과 전략 성과 robustness는 분리해서 해석해야 합니다."""
    )

    st.divider()


# ============================================================
# 섹션 5: 윈도우별 상세 차트 (캔들 + Buy/Sell 마커)
# ============================================================


@st.cache_data
def _load_window_csv_detail(path_str: str) -> pd.DataFrame | None:
    """윈도우별 상세 CSV를 로드한다.

    Args:
        path_str: CSV 파일 경로 (문자열, 캐시 키용)

    Returns:
        DataFrame 또는 None
    """
    path = Path(path_str)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if COL_DATE in df.columns:
        df[COL_DATE] = pd.to_datetime(df[COL_DATE]).dt.date
    return df


def _detect_window_ma_col(signal_df: pd.DataFrame) -> str | None:
    """signal_df에서 ma_* 컬럼을 찾아 반환한다."""
    for col in signal_df.columns:
        if col.startswith("ma_"):
            return col
    return None


def _build_wfo_candle_data(
    signal_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    ma_col: str | None,
) -> list[dict[str, object]]:
    """signal_df를 lightweight-charts 캔들스틱 데이터로 변환한다."""
    has_upper = "upper_band" in equity_df.columns
    has_lower = "lower_band" in equity_df.columns
    has_equity = "equity" in equity_df.columns
    has_dd = "drawdown_pct" in equity_df.columns

    equity_map: dict[date, dict[str, float]] = {}
    for row in equity_df.itertuples(index=False):
        d: date = getattr(row, COL_DATE)
        entry: dict[str, float] = {}
        if has_upper and pd.notna(row.upper_band):
            entry["upper"] = float(cast(float, row.upper_band))
        if has_lower and pd.notna(row.lower_band):
            entry["lower"] = float(cast(float, row.lower_band))
        if has_equity and pd.notna(row.equity):
            entry["equity"] = float(cast(float, row.equity))
        if has_dd and pd.notna(row.drawdown_pct):
            entry["dd"] = float(cast(float, row.drawdown_pct))
        if entry:
            equity_map[d] = entry

    prev_close = signal_df[COL_CLOSE].shift(1)

    candle_data: list[dict[str, object]] = []
    for i, row in enumerate(signal_df.itertuples(index=False)):
        d = getattr(row, COL_DATE)
        open_val = float(getattr(row, COL_OPEN))
        high_val = float(getattr(row, COL_HIGH))
        low_val = float(getattr(row, COL_LOW))
        close_val = float(getattr(row, COL_CLOSE))

        candle_entry: dict[str, object] = {
            "time": d.strftime("%Y-%m-%d"),
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
        }

        cv: dict[str, str] = {}
        cv["open"] = f"{open_val:.2f}"
        cv["high"] = f"{high_val:.2f}"
        cv["low"] = f"{low_val:.2f}"
        cv["close"] = f"{close_val:.2f}"

        pc = prev_close.iloc[i]
        if pd.notna(pc) and pc != 0:
            pc_float = float(pc)
            cv["close_pct"] = f"{(close_val / pc_float - 1) * 100:+.2f}"

        if ma_col and ma_col in signal_df.columns:
            ma_val = getattr(row, ma_col)
            if pd.notna(ma_val):
                cv["ma"] = f"{ma_val:.2f}"

        if d in equity_map:
            eq_data = equity_map[d]
            if "upper" in eq_data:
                cv["upper"] = f"{eq_data['upper']:.2f}"
            if "lower" in eq_data:
                cv["lower"] = f"{eq_data['lower']:.2f}"
            if "equity" in eq_data:
                cv["equity"] = f"{int(eq_data['equity']):,}"
            if "dd" in eq_data:
                cv["dd"] = f"{eq_data['dd']:.2f}"

        if cv:
            candle_entry["customValues"] = cv

        candle_data.append(candle_entry)

    return candle_data


def _build_wfo_line_data(df: pd.DataFrame, col: str) -> list[dict[str, object]]:
    """DataFrame의 특정 컬럼에서 Line 시리즈 데이터를 생성한다."""
    data: list[dict[str, object]] = []
    for row in df.itertuples(index=False):
        val = getattr(row, col)
        if pd.notna(val):
            d: date = getattr(row, COL_DATE)
            data.append({"time": d.strftime("%Y-%m-%d"), "value": float(val)})
    return data


def _build_wfo_markers(
    trades_df: pd.DataFrame,
    oos_start_str: str,
) -> list[dict[str, object]]:
    """trades_df에서 Buy/Sell 마커를 생성하고, OOS 시작일 경계 마커를 추가한다."""
    markers: list[dict[str, object]] = []

    # OOS 시작일 경계 마커
    markers.append(
        {
            "time": oos_start_str,
            "position": "aboveBar",
            "color": "#ffeb3b",
            "shape": "square",
            "text": "OOS Start",
            "size": 2,
        }
    )

    if trades_df.empty or "entry_date" not in trades_df.columns:
        return markers

    for trade in trades_df.itertuples(index=False):
        entry_d = cast(date, trade.entry_date)
        markers.append(
            {
                "time": entry_d.strftime("%Y-%m-%d"),
                "position": "belowBar",
                "color": _COLOR_BUY_MARKER,
                "shape": "arrowUp",
                "text": f"Buy ${trade.entry_price:.1f}",
                "size": 2,
            }
        )
        exit_d = cast(date, trade.exit_date)
        pnl_pct = cast(float, trade.pnl_pct) * 100
        markers.append(
            {
                "time": exit_d.strftime("%Y-%m-%d"),
                "position": "aboveBar",
                "color": _COLOR_SELL_MARKER,
                "shape": "arrowDown",
                "text": f"Sell {pnl_pct:+.1f}%",
                "size": 2,
            }
        )

    return markers


def _build_wfo_equity_data(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """에쿼티 곡선 데이터를 Area 시리즈용으로 변환한다."""
    data: list[dict[str, object]] = []
    for row in equity_df.itertuples(index=False):
        d: date = getattr(row, COL_DATE)
        data.append({"time": d.strftime("%Y-%m-%d"), "value": float(cast(float, row.equity))})
    return data


def _build_wfo_drawdown_data(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """드로우다운 Area 시리즈 데이터를 생성한다."""
    data: list[dict[str, object]] = []
    if "drawdown_pct" not in equity_df.columns:
        return data
    for row in equity_df.itertuples(index=False):
        d: date = getattr(row, COL_DATE)
        data.append({"time": d.strftime("%Y-%m-%d"), "value": float(cast(float, row.drawdown_pct))})
    return data


def _render_window_detail(strategy_dirs: dict[str, Path]) -> None:
    """윈도우별 상세 캔들차트 섹션을 렌더링한다."""
    st.header("윈도우별 상세 차트 (IS + OOS)")

    st.markdown(
        """각 WFO 윈도우의 IS(In-Sample) + OOS(Out-of-Sample) 전체 구간을
캔들차트로 확인합니다. 매수/매도 시점, MA선, 밴드, 에쿼티, 드로우다운을
시각적으로 검증할 수 있습니다."""
    )

    # 1. 지표 선택 (유효한 것만 필터)
    available_metrics: list[str] = []
    for metric_label, (strat_name, mode_dir, _wfo_csv) in _METRIC_OPTIONS.items():
        if strat_name in strategy_dirs:
            window_dir = strategy_dirs[strat_name] / mode_dir
            if window_dir.exists():
                available_metrics.append(metric_label)

    if not available_metrics:
        st.warning("윈도우별 상세 데이터가 존재하지 않습니다.\n\n" "`run_walkforward.py`를 재실행하여 윈도우별 CSV를 생성하세요.")
        return

    selected_metric = st.selectbox(
        "지표 선택",
        available_metrics,
        key="wfo_metric_select",
    )

    if selected_metric is None:
        return

    strat_name, mode_dir, wfo_csv_filename = _METRIC_OPTIONS[selected_metric]
    result_dir = strategy_dirs[strat_name]
    window_dir = result_dir / mode_dir

    # 2. WFO 윈도우 정보 로드 (날짜 범위용)
    wfo_df = _load_window_csv(str(result_dir), wfo_csv_filename)
    if wfo_df is None or wfo_df.empty:
        st.warning("WFO 결과 CSV를 로드할 수 없습니다.")
        return

    # 3. 윈도우 선택
    window_labels: list[str] = []
    for _, row in wfo_df.iterrows():
        is_start = str(row["is_start"])[:7]
        is_end = str(row["is_end"])[:7]
        oos_start = str(row["oos_start"])[:7]
        oos_end = str(row["oos_end"])[:7]
        label = f"W{row['window_idx']}  (IS: {is_start}~{is_end}, OOS: {oos_start}~{oos_end})"
        window_labels.append(label)

    selected_window_label = st.selectbox(
        "윈도우 선택",
        window_labels,
        key="wfo_window_select",
    )

    if selected_window_label is None:
        return

    selected_idx = window_labels.index(selected_window_label)
    window_row = wfo_df.iloc[selected_idx]

    # 4. 윈도우별 CSV 로드
    idx = int(window_row["window_idx"])
    signal_df = _load_window_csv_detail(str(window_dir / f"w{idx:02d}_signal.csv"))
    equity_df = _load_window_csv_detail(str(window_dir / f"w{idx:02d}_equity.csv"))
    trades_df = _load_window_csv_detail(str(window_dir / f"w{idx:02d}_trades.csv"))

    if signal_df is None or equity_df is None:
        st.warning(f"W{idx} 상세 데이터를 찾을 수 없습니다. `run_walkforward.py`를 재실행하세요.")
        return

    if trades_df is None:
        trades_df = pd.DataFrame()

    # 5. 파라미터 + 성과 요약 (metric 카드)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("MA Window", int(window_row["best_ma_window"]))
    col2.metric("Buy Buffer", f"{window_row['best_buy_buffer_zone_pct'] * 100:.1f}%")
    col3.metric("Sell Buffer", f"{window_row['best_sell_buffer_zone_pct'] * 100:.1f}%")
    col4.metric("Hold Days", int(window_row["best_hold_days"]))

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("IS CAGR", f"{window_row['is_cagr']:.2f}%")
    col6.metric("IS MDD", f"{window_row['is_mdd']:.2f}%")
    col7.metric("OOS CAGR", f"{window_row['oos_cagr']:.2f}%")
    col8.metric("OOS MDD", f"{window_row['oos_mdd']:.2f}%")

    # 6. 차트 렌더링
    ma_col = _detect_window_ma_col(signal_df)
    oos_start_str = str(window_row["oos_start"])[:10]

    candle_data = _build_wfo_candle_data(signal_df, equity_df, ma_col)
    equity_data = _build_wfo_equity_data(equity_df)
    dd_data = _build_wfo_drawdown_data(equity_df)

    chart_theme = {
        "layout": {
            "background": {"color": "#131722"},
            "textColor": "#D1D4DC",
            "fontFamily": "Arial",
            "fontSize": 12,
        },
        "grid": {
            "vertLines": {"color": "#1e222d", "visible": True},
            "horzLines": {"color": "#1e222d", "visible": True},
        },
        "crosshair": {
            "mode": 0,
            "vertLine": {"color": "rgba(255, 255, 255, 0.3)", "style": 2},
            "horzLine": {"color": "rgba(255, 255, 255, 0.3)", "style": 2},
        },
        "timeScale": {"minBarSpacing": 0.2},
        "localization": {"dateFormat": "yyyy-MM-dd"},
    }

    # Pane 1: 캔들 + MA + 밴드 + 마커
    candle_series: dict[str, object] = {
        "type": "Candlestick",
        "data": candle_data,
        "options": {
            "upColor": _COLOR_UP,
            "downColor": _COLOR_DOWN,
            "borderVisible": False,
            "wickUpColor": _COLOR_UP,
            "wickDownColor": _COLOR_DOWN,
            "priceLineVisible": False,
        },
    }

    markers = _build_wfo_markers(trades_df, oos_start_str)
    if markers:
        candle_series["markers"] = markers

    pane1_series: list[dict[str, object]] = [candle_series]

    # MA 오버레이
    if ma_col:
        ma_data = _build_wfo_line_data(signal_df, ma_col)
        if ma_data:
            pane1_series.append(
                {
                    "type": "Line",
                    "data": ma_data,
                    "options": {
                        "color": _COLOR_MA_LINE,
                        "lineWidth": 2,
                        "priceLineVisible": False,
                        "lastValueVisible": False,
                        "crosshairMarkerVisible": False,
                    },
                }
            )

    # 밴드 오버레이
    if "upper_band" in equity_df.columns:
        upper_data = _build_wfo_line_data(equity_df, "upper_band")
        if upper_data:
            pane1_series.append(
                {
                    "type": "Line",
                    "data": upper_data,
                    "options": {
                        "color": _COLOR_UPPER_BAND,
                        "lineWidth": 2,
                        "lineStyle": 2,
                        "priceLineVisible": False,
                        "lastValueVisible": False,
                        "crosshairMarkerVisible": False,
                    },
                }
            )

    if "lower_band" in equity_df.columns:
        lower_data = _build_wfo_line_data(equity_df, "lower_band")
        if lower_data:
            pane1_series.append(
                {
                    "type": "Line",
                    "data": lower_data,
                    "options": {
                        "color": _COLOR_LOWER_BAND,
                        "lineWidth": 2,
                        "lineStyle": 2,
                        "priceLineVisible": False,
                        "lastValueVisible": False,
                        "crosshairMarkerVisible": False,
                    },
                }
            )

    chart_title = f"{selected_metric} — W{idx}"

    pane1 = {
        "chart": chart_theme,
        "series": pane1_series,
        "height": _WINDOW_CANDLE_HEIGHT,
        "title": chart_title,
    }

    # Pane 2: 에쿼티
    pane2 = {
        "chart": chart_theme,
        "series": [
            {
                "type": "Area",
                "data": equity_data,
                "options": {
                    "lineColor": _COLOR_EQUITY_LINE,
                    "topColor": _COLOR_EQUITY_TOP,
                    "bottomColor": _COLOR_EQUITY_BOTTOM,
                    "lineWidth": 2,
                    "priceLineVisible": False,
                    "priceFormat": {"type": "price", "precision": 0, "minMove": 1},
                },
            }
        ],
        "height": _WINDOW_EQUITY_HEIGHT,
        "title": "에쿼티 (원)",
    }

    # Pane 3: 드로우다운
    pane3 = {
        "chart": chart_theme,
        "series": [
            {
                "type": "Area",
                "data": dd_data,
                "options": {
                    "lineColor": _COLOR_DRAWDOWN_LINE,
                    "topColor": _COLOR_DRAWDOWN_TOP,
                    "bottomColor": _COLOR_DRAWDOWN_BOTTOM,
                    "lineWidth": 2,
                    "priceLineVisible": False,
                    "priceFormat": {"type": "price", "precision": 2, "minMove": 0.01},
                    "invertFilledArea": True,
                    "fixedMaxValue": 0,
                },
            }
        ],
        "height": _WINDOW_DRAWDOWN_HEIGHT,
        "title": "드로우다운 (%)",
    }

    total_height = _WINDOW_CANDLE_HEIGHT + _WINDOW_EQUITY_HEIGHT + _WINDOW_DRAWDOWN_HEIGHT
    lightweight_charts_v5_component(
        name=f"wfo_window_{selected_metric}_{idx}",
        charts=[pane1, pane2, pane3],
        height=total_height,
        zoom_level=_WINDOW_ZOOM_LEVEL,
        scroll_padding=60,
        key=f"wfo_detail_{selected_metric}_{idx}",
    )

    st.divider()


# ============================================================
# 메인
# ============================================================


def main() -> None:
    """Streamlit 앱 메인 함수."""
    st.set_page_config(
        page_title="WFO 결과 시각화 대시보드",
        layout="wide",
    )

    st.title("WFO 결과 시각화 대시보드")
    st.markdown("워크포워드 검증(Walk-Forward Optimization) 2-Mode(Dynamic / Fully Fixed) 결과를 " "QQQ와 TQQQ를 나란히 비교합니다.")

    # 읽기 가이드
    st.markdown(
        """## 이 화면 읽는 법

| 섹션 | 목적 | 중요도 |
|------|------|--------|
| **모드별 요약 비교** | Dynamic vs Fully Fixed 핵심 지표 한눈에 비교 | 핵심 |
| **Stitched Equity 곡선** | 두 모드의 자본곡선 시각 비교 | 핵심 |
| **IS vs OOS 성과 비교** | 윈도우별 과최적화 정도 확인 | 핵심 |
| **파라미터 추이** | 최적 파라미터의 시간 안정성 확인 | 참고 |
| **윈도우별 상세 차트** | 윈도우별 Buy/Sell 마커 시각 검증 | 검증 |"""
    )

    with st.expander("WFO 기본 개념 (펼쳐서 보기)"):
        st.markdown(
            r"""### WFO(Walk-Forward Optimization)란?

과거 데이터(IS)에서 최적 파라미터를 찾고, 미래 데이터(OOS)에서 그 파라미터가 실제로 통하는지 검증하는 방법입니다.

- **IS(In-Sample)**: 그리드 서치로 최적 파라미터를 **찾는** 구간 (연습)
- **OOS(Out-of-Sample)**: IS에서 찾은 파라미터를 **그대로 적용**하는 구간 (본시험)
- **같은 윈도우 내에서 IS와 OOS는 동일한 파라미터를 사용**합니다. 파라미터가 바뀌는 것은 윈도우 간(Dynamic 모드에서 W0 → W1 → W2 …)입니다.
- **Dynamic 모드**: 매 윈도우마다 IS에서 파라미터를 새로 최적화
- **Fully Fixed 모드**: 첫 번째 윈도우(W0)의 IS 최적 파라미터를 모든 윈도우에 고정 적용

### Expanding Anchored Window 방식

IS 시작점은 데이터 최초(1999-03)로 고정, IS 종료점이 매 윈도우마다 2년씩 확장됩니다.
후반 윈도우일수록 IS에 더 많은 시장 사이클이 포함되어 파라미터 선택이 안정화됩니다.

| W | IS 기간 | IS 길이 | OOS 기간 | OOS 길이 |
|---|---------|---------|----------|----------|
| W0 | 1999-03 \~ 2005-02 | 약 6년 | 2005-03 \~ 2007-02 | 2년 |
| W1 | 1999-03 \~ 2007-02 | 약 8년 | 2007-03 \~ 2009-02 | 2년 |
| W2 | 1999-03 \~ 2009-02 | 약 10년 | 2009-03 \~ 2011-02 | 2년 |
| W3 | 1999-03 \~ 2011-02 | 약 12년 | 2011-03 \~ 2013-02 | 2년 |
| W4 | 1999-03 \~ 2013-02 | 약 14년 | 2013-03 \~ 2015-02 | 2년 |
| W5 | 1999-03 \~ 2015-02 | 약 16년 | 2015-03 \~ 2017-02 | 2년 |
| W6 | 1999-03 \~ 2017-02 | 약 18년 | 2017-03 \~ 2019-02 | 2년 |
| W7 | 1999-03 \~ 2019-02 | 약 20년 | 2019-03 \~ 2021-02 | 2년 |
| W8 | 1999-03 \~ 2021-02 | 약 22년 | 2021-03 \~ 2023-02 | 2년 |
| W9 | 1999-03 \~ 2023-02 | 약 24년 | 2023-03 \~ 2025-02 | 2년 |
| W10 | 1999-03 \~ 2025-02 | 약 26년 | 2025-03 \~ 2026-03 | 약 1년 |"""
        )

    st.divider()

    # 전략 탐색
    strategy_dirs = _discover_wfo_strategies()

    if not strategy_dirs:
        st.error(
            "WFO 결과가 존재하는 전략이 없습니다.\n\n"
            "먼저 워크포워드 검증을 실행하세요:\n"
            "```bash\n"
            "poetry run python scripts/backtest/run_walkforward.py\n"
            "```"
        )
        st.stop()
        return

    # 전략별 요약 로드
    summaries: dict[str, dict[str, object]] = {}
    for strat_name, result_dir in strategy_dirs.items():
        summary = _load_summary(str(result_dir))
        if summary is not None:
            summaries[strat_name] = summary

    if not summaries:
        st.error("요약 데이터를 로드할 수 없습니다.")
        st.stop()
        return

    # 5개 섹션 순서대로 렌더링 (통합 뷰)
    _render_mode_summary(summaries)
    _render_stitched_equity(strategy_dirs)
    _render_is_vs_oos(strategy_dirs)
    _render_param_drift(summaries)
    _render_window_detail(strategy_dirs)


if __name__ == "__main__":
    main()
