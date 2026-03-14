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
- WFE 분포: 좌우 배치 바차트
"""

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from qbt.backtest.constants import (
    WALKFORWARD_DYNAMIC_FILENAME,
    WALKFORWARD_EQUITY_DYNAMIC_FILENAME,
    WALKFORWARD_EQUITY_FULLY_FIXED_FILENAME,
    WALKFORWARD_SUMMARY_FILENAME,
)
from qbt.common_constants import BACKTEST_RESULTS_DIR

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

**QQQ** (2026.03.14 기준):

- 한 줄 요약: **파라미터를 매번 바꾸든 처음 것을 고정하든 결과가 거의 같습니다.** 즉, 우리가 쓰고 있는 고정 파라미터(4P)가 충분히 안정적이라는 뜻입니다.
- 예시로 이해하기: Dynamic CAGR 11.7%와 Fixed CAGR 11.7%가 동일합니다. 마치 "시험 범위를 매번 새로 공부해도, 처음에 공부한 것만으로도 점수가 같다"는 것과 비슷합니다.
- WFE Calmar Robust가 2.09/2.04로, 연습(IS)에서 100점이면 본시험(OOS)에서 200점을 받은 셈입니다. 과최적화 걱정이 없습니다.
- PC 최대 0.44\~0.48은 수익이 특정 시기에 몰리지 않고 비교적 고르게 분산되었다는 의미입니다 (0.5 미만이면 양호).

**TQQQ** (2026.03.14 기준):

- 한 줄 요약: **파라미터를 매번 새로 최적화(Dynamic)하면 수익이 3배 높지만, 수익이 특정 시기에 쏠려 있어 "운이 좋았던 것"일 수 있습니다.**
- 예시로 이해하기: Dynamic은 연 21.4%, Fixed는 연 7.0%입니다. 하지만 Dynamic의 PC 최대가 0.70으로, 전체 수익의 70%가 단 하나의 구간(2009년 급반등)에서 나왔습니다. 이 구간을 빼면 성과가 크게 줄어들 수 있습니다.
- Fixed의 WFE Calmar Robust가 -0.91이라는 것은, 연습(IS)에서 좋았던 파라미터가 본시험(OOS)에서는 오히려 나빠졌다는 뜻입니다. 처음 정한 파라미터가 이후 시장 환경(금리인상, 코로나 등)에 맞지 않았기 때문입니다.
- 결론: TQQQ는 레버리지 특성상 QQQ보다 시장 환경 변화에 민감하며, 고정 파라미터만으로는 부족할 수 있습니다."""
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

**QQQ** (2026.03.14 기준):

- 한 줄 요약: **파란선(Dynamic)과 주황선(Fixed)이 거의 완벽하게 겹칩니다.** 이는 "파라미터를 매번 바꿔도 결과가 같다"는 뜻이므로, 우리의 고정 파라미터(4P)가 잘 작동하고 있다는 증거입니다.
- 그래프 읽는 법: 두 선이 함께 올라가고 함께 내려가며, 최종 도달점이 거의 동일합니다. 2020년 코로나 급락 구간에서 잠깐 차이가 생기지만 이후 다시 합쳐집니다.

**TQQQ** (2026.03.14 기준):

- 한 줄 요약: **파란선(Dynamic)이 주황선(Fixed)보다 약 7배 높은 곳에 도달합니다.** 파라미터를 시장 상황에 맞게 바꿔주는 것이 TQQQ에서는 큰 차이를 만든다는 뜻입니다.
- 그래프 읽는 법: 2015년 이전에는 두 선이 비슷하지만, 이후 Dynamic이 빠르게 상승하여 격차가 벌어집니다. 다만 Dynamic도 2020년 코로나 구간에서 -62%의 큰 낙폭을 겪었고, **높은 수익에는 높은 위험이 동반**됩니다.
- QQQ와 비교하면: QQQ는 두 곡선이 겹치지만 TQQQ는 크게 벌어집니다. 이는 레버리지 상품일수록 "어떤 파라미터를 쓰느냐"가 결과에 미치는 영향이 훨씬 크다는 것을 보여줍니다."""
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
- **CAGR(%)**: 연환산 복리 수익률 (높을수록 좋음)
- **Calmar**: CAGR / |MDD| (위험 대비 수익 효율)
- **윈도우(Window)**: WFO에서 IS + OOS를 하나의 단위로 묶은 시간 구간

## 지표를 해석하는 방법

- IS와 OOS 막대가 **비슷한 높이**: IS에서의 성과가 OOS에서도 재현 → 과최적화 아님
- IS가 높고 OOS가 **크게 낮음**: IS에서 과적합(overfitting)이 발생하여 OOS에서 성과 악화
- OOS가 **음수**: 해당 기간에 전략이 손실을 기록했음을 의미
- 특정 윈도우만 OOS가 극단적: 해당 시기의 시장 환경(금융위기 등)이 전략에 불리했을 가능성

## 현재 지표 해석 & 판단(결과)

**그래프 읽는 법**: 각 윈도우(W0\~W10)마다 녹색(IS)과 빨간색(OOS) 막대가 나란히 서 있습니다. 녹색은 "연습 성적", 빨간색은 "본시험 성적"이라고 생각하면 됩니다. 빨간색이 녹색과 비슷하거나 높으면 과최적화가 아닌 것이고, 빨간색이 훨씬 낮으면 "연습에서만 잘하고 실전에서 못하는" 과최적화를 의심해야 합니다.

**공통** (2026.03.14 기준):

- 연습(IS) 성적은 5\~20% CAGR로 꾸준한 반면, 본시험(OOS) 성적은 윈도우마다 들쭉날쭉합니다. 특히 **W2(2009-03\~2011-02)**는 금융위기 직후 급반등 구간이라 본시험 성적이 극단적으로 높습니다 (QQQ \~40%, TQQQ \~118%).
- 이것은 과최적화가 아니라, 보수적으로 설정된 파라미터가 강한 상승장을 만나 예상보다 좋은 결과를 낸 경우입니다.

**QQQ**:

- 대부분의 윈도우에서 빨간 막대(OOS)가 녹색 막대(IS)와 비슷하거나 더 높습니다. 이는 **"연습보다 본시험을 더 잘 봤다"**는 뜻으로, 과최적화 우려가 낮습니다.
- 예외: W1(2007\~2009 금융위기)과 W3(2011\~2013 횡보장)에서만 OOS가 부진합니다. 이 시기는 시장 자체가 어려웠던 구간입니다.

**TQQQ**:

- QQQ와 비슷한 패턴이지만, 레버리지 때문에 막대의 높낮이 차이가 훨씬 큽니다. 좋을 때는 +118%(W2)로 매우 좋지만, 나쁠 때는 -21%(W3)로 크게 나쁩니다.
- W1, W3, W5에서 OOS 손실이 발생하는데, 이 구간들은 모두 하락장이나 횡보장 시기입니다. **"TQQQ는 상승장에서 극적으로 좋고, 하락장에서 극적으로 나쁘다"**는 레버리지의 본질적 특성이 드러납니다."""
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
- **Recent Months**: 최근 청산 분석 기간 (0이면 동적 조정 비활성화)

## 지표를 해석하는 방법

- 파라미터가 윈도우마다 **크게 변동**: 최적 파라미터가 시장 환경에 민감 → 고정 파라미터 사용 시 주의 필요
- 파라미터가 **안정적으로 유지**: 특정 값 주위에 수렴 → 해당 값을 고정 파라미터로 사용해도 안전
- 특정 시점에서 **급격히 변화**: 시장 구조 변화(regime change)와 맞물릴 가능성
- Fully Fixed 모드는 파라미터가 항상 동일하므로 시각화 불필요 (모든 윈도우 동일값)

## 현재 지표 해석 & 판단(결과)

**그래프 읽는 법**: 선이 수평에 가까우면 "어떤 시기든 같은 파라미터가 최적"이라는 뜻이고, 위아래로 요동치면 "시기마다 최적 파라미터가 달라진다"는 뜻입니다. 선이 안정적일수록 고정 파라미터를 사용해도 안전합니다.

**QQQ** (2026.03.14 기준):

- 한 줄 요약: **대부분의 파라미터가 거의 수평선을 그립니다.** 즉, "언제 최적화하든 같은 답이 나온다"는 뜻입니다.
- 구체적으로: MA Window=200(파란선)과 Sell Buffer=5%는 11개 윈도우 전체에서 변하지 않습니다. Buy Buffer만 초반 1%에서 W4(2013년경) 이후 3%로 전환되었고, 그 뒤로 계속 3%를 유지합니다.
- 의미: 후반부 파라미터가 현재 우리가 쓰는 4P 확정값(MA=200, buy=3%, sell=5%, hold=3)과 거의 일치합니다. **"시간이 지나면서 자연스럽게 4P로 수렴했다"**는 것이 고정 파라미터의 타당성을 뒷받침합니다.

**TQQQ** (2026.03.14 기준):

- 한 줄 요약: **파라미터가 QQQ보다 훨씬 많이 변동합니다.** 시장 환경에 따라 "최적의 답"이 달라진다는 뜻입니다.
- 구체적으로: MA Window가 100→200→150(빨간선)으로 오르내리고, Sell Buffer는 1%→3%→5%로 단계적으로 상승합니다. 하나의 값에 수렴하지 않고 계속 바뀌고 있습니다.
- 의미: 이것이 앞서 본 "Dynamic과 Fixed의 성과 차이가 큰 이유"입니다. 시장 환경이 바뀔 때마다 최적 파라미터도 바뀌기 때문에, 처음 정한 값을 고정하면 성과가 떨어집니다. **레버리지 상품은 비레버리지보다 파라미터 변화에 민감합니다.**"""
    )

    st.divider()


# ============================================================
# 섹션 5: WFE 분포 (헬퍼)
# ============================================================

# Y축 클리핑 범위 (이 범위를 벗어나는 값은 막대를 잘라내고 실제값을 주석으로 표시)
_WFE_Y_CLIP_MIN = -10
_WFE_Y_CLIP_MAX = 10


def _build_wfe_chart(
    strategy_dirs: dict[str, Path],
    strategy_names: list[str],
    n_strategies: int,
    wfe_col: str,
    y_axis_label: str,
) -> go.Figure:
    """WFE 바차트를 생성한다. 극단값은 Y축 범위를 클리핑하고 주석으로 실제값을 표시한다.

    Args:
        strategy_dirs: 전략명 → 디렉토리 경로
        strategy_names: 전략명 리스트
        n_strategies: 전략 수
        wfe_col: WFE 컬럼명 (wfe_calmar 또는 wfe_cagr)
        y_axis_label: Y축 레이블

    Returns:
        Plotly Figure
    """
    fig = make_subplots(
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

        window_labels = [f"W{idx}" for idx in dynamic_df["window_idx"]]
        raw_values = dynamic_df[wfe_col].tolist()

        # 클리핑된 Y값 (차트 표시용)
        clipped_values = [max(_WFE_Y_CLIP_MIN, min(_WFE_Y_CLIP_MAX, v)) for v in raw_values]
        colors = ["#2ca02c" if v >= 0 else "#d62728" for v in raw_values]

        fig.add_trace(
            go.Bar(
                x=window_labels,
                y=clipped_values,
                name=y_axis_label,
                marker_color=colors,
                showlegend=False,
            ),
            row=1,
            col=col_idx,
        )

        # 클리핑된 막대에 실제값 주석 표시
        for label, raw_v, clipped_v in zip(window_labels, raw_values, clipped_values, strict=True):
            if raw_v != clipped_v:
                is_negative = raw_v < _WFE_Y_CLIP_MIN
                fig.add_annotation(
                    x=label,
                    y=clipped_v,
                    text=f"<b>{raw_v:.1f}</b>",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    ax=0,
                    ay=30 if is_negative else -30,
                    font={"size": 12, "color": "#d62728" if raw_v < 0 else "#2ca02c"},
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="#d62728" if raw_v < 0 else "#2ca02c",
                    borderwidth=1,
                    row=1,
                    col=col_idx,
                )

        # 기준선
        fig.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1, row=1, col=col_idx)
        fig.add_hline(
            y=1,
            line_dash="dot",
            line_color="blue",
            line_width=1,
            row=1,
            col=col_idx,
        )
        fig.update_yaxes(
            title_text=y_axis_label,
            range=[_WFE_Y_CLIP_MIN - 2, _WFE_Y_CLIP_MAX + 2],
            row=1,
            col=col_idx,
        )

    fig.update_layout(height=_SUB_CHART_HEIGHT)
    return fig


# ============================================================
# 섹션 5: WFE 분포
# ============================================================


def _render_wfe_distribution(strategy_dirs: dict[str, Path]) -> None:
    """WFE 분포를 좌우 서브플롯으로 비교한다."""
    st.header("WFE 분포 (Dynamic 모드)")

    strategy_names = list(strategy_dirs.keys())
    n_strategies = len(strategy_names)

    # WFE Calmar 바차트
    fig_wfe_calmar = _build_wfe_chart(strategy_dirs, strategy_names, n_strategies, "wfe_calmar", "WFE Calmar")
    fig_wfe_calmar.update_layout(
        title="윈도우별 WFE Calmar (OOS Calmar / IS Calmar)",
    )
    st.plotly_chart(fig_wfe_calmar, width="stretch")

    # WFE CAGR 바차트
    fig_wfe_cagr = _build_wfe_chart(strategy_dirs, strategy_names, n_strategies, "wfe_cagr", "WFE CAGR")
    fig_wfe_cagr.update_layout(
        title="윈도우별 WFE CAGR (OOS CAGR / IS CAGR)",
    )
    st.plotly_chart(fig_wfe_cagr, width="stretch")

    # VERBATIM
    st.markdown(
        r"""## 지표에 사용하는 용어에 대한 설명

- **WFE(Walk-Forward Efficiency)**: OOS 성과 / IS 성과 비율
  - **WFE Calmar**: OOS Calmar / IS Calmar
  - **WFE CAGR**: OOS CAGR / IS CAGR
- **WFE = 1**: IS 성과가 OOS에서 100% 재현됨 (이상적)
- **WFE > 0**: OOS에서도 같은 방향의 성과 (양수면 양수, 음수면 음수)
- **WFE < 0**: IS와 OOS의 성과 방향이 반대 (IS에서 좋았지만 OOS에서 나쁨, 또는 그 반대)

## 지표를 해석하는 방법

- **WFE가 0\~1 사이에 집중**: IS 성과의 일부가 OOS에서 재현 → 과최적화가 심하지 않음
- **WFE가 대부분 음수**: IS에서의 최적화가 OOS에서 통하지 않음 → 과최적화 가능성
- **WFE의 크기보다 부호(양/음)가 중요**: 양수가 많을수록 전략의 일반화 능력이 높음
- **극단적인 WFE값** (예: -1000): IS Calmar이 0에 가까워 비율이 폭발한 경우이므로 수치 자체보다 해당 윈도우의 IS/OOS 성과를 직접 확인할 것

## 현재 지표 해석 & 판단(결과)

**그래프 읽는 법**: 녹색 막대(양수)는 "연습(IS)에서 잘했고 본시험(OOS)에서도 잘한" 윈도우, 빨간 막대(음수)는 "연습과 본시험 결과가 반대인" 윈도우입니다. 녹색이 많을수록 전략이 실전에서도 잘 작동한다는 뜻입니다. 파란 점선(WFE=1)은 "연습 성적 = 본시험 성적"인 이상적 기준선입니다.

**QQQ** (2026.03.14 기준):

- 한 줄 요약: **11개 윈도우 중 8개가 녹색(양수)으로, 전략이 실전에서도 대체로 잘 작동합니다.**
- 주의할 점: W2와 W4가 극단적으로 높은데, 이것은 "연습에서 간신히 합격했는데 본시험에서 만점을 받은" 특수한 경우입니다. 비율이 폭발한 것이지 전략이 특별히 좋다는 뜻은 아닙니다.
- WFE Robust 2.09는 이런 극단값을 제거하고 봐도 양호하다는 의미입니다. 과최적화 걱정이 없습니다.

**TQQQ** (2026.03.14 기준):

- 한 줄 요약: **W0\~W3(2005\~2013)이 모두 음수(빨간색)로 QQQ와 극단적으로 다르지만, 이것은 3x 레버리지 특성 때문이며 W4 이후 개선됩니다.**
- W0\~W3이 나쁜 이유 (3가지):
  - (1) **변동성 드래그**: 3x 일별 레버리지는 하락장/횡보장에서 변동성 드래그(volatility decay)가 원금을 갉아먹습니다. 같은 구간에서 QQQ MDD가 -23%인데 TQQQ는 -57%까지 확대됩니다.
  - (2) **파라미터 불안정**: QQQ는 전 구간 MA=200으로 안정적이지만, TQQQ는 IS 구간에 닷컴 버블(-85% MDD)이 포함되어 optimizer가 빠른 MA(100)를 선택했고, 이 파라미터가 OOS에서 통하지 않았습니다.
  - (3) **IS 자체가 처참**: TQQQ의 IS MDD가 -78%\~-85%라 "최적" 파라미터의 Calmar 자체가 매우 낮습니다(0.04, -0.002 등). 거의 0에 가까운 IS Calmar으로 나누니 WFE가 극단적으로 폭발합니다.
- W4 이후 개선: IS 데이터가 더 많은 시장 사이클을 포함하면서 optimizer가 robust한 파라미터(MA=200)를 선택하게 되어 녹색(양수)이 늘어납니다.
- W2 극단값(-1832): IS Calmar이 -0.0017(거의 0)이라 비율이 폭발한 수학적 특이값이므로 수치 자체에 의미가 없습니다. (차트에서는 클리핑 처리되며 막대 위에 실제값이 표시됩니다.)
- WFE Robust 0.94: 극단값을 제거하면 연습 성적의 약 94%가 본시험에서 재현되어 비교적 양호합니다."""
    )


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
| **WFE 분포** | Walk-Forward Efficiency 분포 확인 | 참고 |"""
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
    _render_wfe_distribution(strategy_dirs)


if __name__ == "__main__":
    main()
