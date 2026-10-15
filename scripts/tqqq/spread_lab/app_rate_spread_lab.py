"""TQQQ 금리-오차 관계 분석 연구용 앱

금리 환경과 시뮬레이션 오차의 관계를 시각화하여 Softplus 동적 스프레드 모델의
검증 결과를 확인한다.

실행 명령어:
    poetry run streamlit run scripts/tqqq/spread_lab/app_rate_spread_lab.py

화면 구성 (단일 흐름):
- 금리-오차 관계 분석: 금리 수준 vs 월말 누적 오차 (핵심), 델타 분석, 교차검증
- Softplus 모델 튜닝 결과: 전체기간 최적 파라미터 (a, b)
- 워크포워드 RMSE 비교: 완전 고정 · b 고정 · 동적 워크포워드의 이어 붙인(stitched) RMSE
- 상세 분석: 모델 도출 과정 (워크포워드, b고정, Spread 비교)

RMSE 차이로 과최적화를 판정하지 않고 수치와 잰 기간만 보인다 — 튜닝의 최적 RMSE 는 전체기간,
워크포워드의 이어 붙인 RMSE 는 테스트 구간에서 잰 값이라 기간이 다르고, 완전 고정의 a · b 와
b 고정의 b 는 테스트 구간까지 본 전체기간 튜닝값이라 아웃오브샘플 검증이 아니다.

튜닝 · 워크포워드 결과 CSV(`storage/results/tqqq/spread_lab/`)는 git 이 추적하고,
그 CSV 를 만드는 스크립트는 이 저장소에 없다 — 커밋 `c81690b^` 에서 되살린다.

Fail-fast 정책:
- ValueError 발생 시 st.error() + st.stop()으로 즉시 중단
- 잘못된 차트/수치 표시 방지

사용자 경험:
- 모든 화면 텍스트 한글화 ("한글 (영문)" 형식)
- 명확한 레이블 및 설명 제공
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.common_constants import TQQQ_RESULTS_DIR
from qbt.tqqq.constants import (
    COL_DE_M,
    COL_E_M,
    COL_MONTH,
    COL_RATE_PCT,
    COL_SUM_DAILY_M,
    FFR_DATA_PATH,
    ROLLING_CORR_WINDOW_MONTHS,
    TQQQ_DAILY_COMPARISON_PATH,
)
from qbt.tqqq.data_loader import (
    load_comparison_data,
    load_monthly_data,
)
from qbt.tqqq.spread_lab_helpers import prepare_monthly_data
from qbt.tqqq.visualization import (
    create_delta_scatter_chart,
    create_level_scatter_chart,
    create_level_timeseries_chart,
    create_rolling_correlation_chart,
)

# ============================================================
# Streamlit 앱 전용 상수 (이 파일에서만 사용)
# ============================================================

# --- 결과 파일 경로 (spread_lab 하위폴더) ---
SPREAD_LAB_DIR = TQQQ_RESULTS_DIR / "spread_lab"
SOFTPLUS_TUNING_CSV_PATH = SPREAD_LAB_DIR / "tqqq_softplus_tuning.csv"
SOFTPLUS_SPREAD_SERIES_STATIC_PATH = SPREAD_LAB_DIR / "tqqq_softplus_spread_series_static.csv"
TQQQ_WALKFORWARD_PATH = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward.csv"
TQQQ_WALKFORWARD_SUMMARY_PATH = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_summary.csv"
TQQQ_WALKFORWARD_FIXED_B_PATH = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_fixed_b.csv"
TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_fixed_b_summary.csv"
TQQQ_WALKFORWARD_FIXED_AB_PATH = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_fixed_ab.csv"
TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH = SPREAD_LAB_DIR / "tqqq_rate_spread_lab_walkforward_fixed_ab_summary.csv"

# --- 튜닝 결과 CSV 컬럼 ---
COL_A = "a"  # softplus 파라미터 a
COL_B = "b"  # softplus 파라미터 b
COL_RMSE_PCT = "rmse_pct"  # RMSE (%)

# --- 기본값 파라미터 ---
DEFAULT_TOP_N_CROSS_VALIDATION = 5  # 교차검증 상위 표시 개수
DEFAULT_HISTOGRAM_BINS = 30  # 히스토그램 기본 bins
DEFAULT_LAG_OPTIONS = [0, 1, 2]  # Delta 분석 lag 선택지 (개월)

# --- 출력용 한글 레이블 ---
DISPLAY_ERROR_END_OF_MONTH_PCT = "월말 누적 오차 (%)"  # Level 차트 y축
DISPLAY_CHART_DIFF_DISTRIBUTION = "차이 분포"  # 히스토그램 차트명
DISPLAY_AXIS_DIFF_PCT = "차이 (%)"  # X축 레이블
DISPLAY_AXIS_FREQUENCY = "빈도"  # Y축 레이블
DISPLAY_DELTA_MONTHLY_PCT = "월간 변화 (%)"  # Delta 차트 y축

# ============================================================
# 데이터 로드 (캐시)
# ============================================================


@st.cache_data
def build_artifacts(daily_path: Path, daily_mtime: float, ffr_path: Path, ffr_mtime: float) -> pd.DataFrame:
    """
    일별 비교 데이터와 금리 데이터를 로드하고 월별로 집계한다.

    수정 시각 둘은 본문에서 쓰지 않고 캐시 키로만 둔다 — 일별 비교 CSV 나 금리 파일을 다시 만들면 새로 집계한다.
    이름이 밑줄로 시작하면 Streamlit 이 캐시 키에서 빼므로 밑줄을 붙이지 않는다.

    Returns:
        월별 집계 DataFrame (month, e_m, de_m, rate_pct, dr_m, sum_daily_m)

    Raises:
        ValueError: 필수 컬럼 누락, 금리 커버리지 부족 등
    """
    daily_df = load_comparison_data(daily_path)
    ffr_df = load_monthly_data(ffr_path)
    return prepare_monthly_data(daily_df, ffr_df)


@st.cache_data
def _read_csv(path: Path, mtime: float) -> pd.DataFrame:
    """결과 CSV 를 읽는다. 수정 시각은 캐시 키로만 둔다(build_artifacts 와 같은 이유)."""
    return pd.read_csv(path)


def _load_csv(path: Path) -> pd.DataFrame:
    return _read_csv(path, path.stat().st_mtime)


def _load_summary(path: Path) -> dict[str, float]:
    """워크포워드 요약 CSV(metric, value 열)를 지표 이름 → 값 딕셔너리로 읽는다."""
    summary_df = _load_csv(path)
    return dict(zip(summary_df["metric"], summary_df["value"].astype(float), strict=True))


def _common_test_period(*result_dfs: pd.DataFrame) -> tuple[str, str]:
    """
    워크포워드 결과들의 공통 테스트 구간 (첫 월, 끝 월)을 돌려준다.

    화면이 이어 붙인 RMSE 들을 「같은 테스트 구간에서 잰 값」으로 나란히 보이므로, 테스트 월이 하나라도
    다르면 그 설명이 거짓이 된다 — 그때는 멈춘다.

    Raises:
        ValueError: 결과들의 테스트 월 목록이 서로 다를 때
    """
    month_lists = {tuple(df["test_month"]) for df in result_dfs}
    if len(month_lists) != 1:
        raise ValueError("워크포워드 결과 CSV 들의 테스트 월이 서로 다릅니다 — " "같은 테스트 구간으로 다시 만들어야 이어 붙인 RMSE 를 나란히 볼 수 있습니다")
    months = month_lists.pop()
    return str(min(months)), str(max(months))


# ============================================================
# UI 렌더링 함수
# ============================================================


def _render_intro():
    """타이틀과 읽기 가이드를 렌더링한다."""
    st.title("TQQQ 금리-오차 관계 분석")
    st.markdown("금리 환경과 시뮬레이션 오차의 관계를 시각화하여 " "**Softplus 동적 스프레드 모델**의 검증 결과를 확인합니다.")

    # 읽기 가이드
    st.markdown(
        """## 이 화면 읽는 법

| 섹션 | 목적 | 중요도 |
|------|------|--------|
| **금리-오차 관계 분석** | 금리 수준/변화와 시뮬레이션 오차의 관계 파악 | 핵심 |
| **Softplus 모델 튜닝 결과** | 전체기간 최적 파라미터 (a, b) 확인 | 핵심 |
| **워크포워드 RMSE 비교** | 완전 고정 · b 고정 · 동적 워크포워드가 같은 테스트 구간에서 낸 RMSE 확인 | 핵심 |
| **상세 분석 (모델 도출 과정)** | Softplus 모델 선택까지의 중간 검증 과정 | 참고 |"""
    )
    st.divider()


def _render_dataset_metrics(monthly_df: pd.DataFrame):
    """요약 통계를 표시한다."""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="분석 기간 (Period)",
            value=f"{monthly_df[COL_MONTH].min()} ~ {monthly_df[COL_MONTH].max()}",
        )
    with col2:
        rate_min = monthly_df[COL_RATE_PCT].min()
        rate_max = monthly_df[COL_RATE_PCT].max()
        st.metric(label="금리 범위 (Rate Range, %)", value=f"{rate_min:.2f}% ~ {rate_max:.2f}%")
    with col3:
        e_min = monthly_df[COL_E_M].min()
        e_max = monthly_df[COL_E_M].max()
        st.metric(label="월말 오차 범위 (End-of-Month Error, %)", value=f"{e_min:.2f}% ~ {e_max:.2f}%")

    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **월별 집계**: 매일 데이터를 "월 단위"로 요약해서 보는 방식
- **분석 기간(Period)**: 분석에 포함된 시작 월 ~ 종료 월
- **금리 범위(Rate Range, %)**: 분석 기간 동안의 FFR(연방기금금리) 최소~최대
- **월말 오차 범위(End-of-Month Error, %)**: 월말 기준 오차(e_m)의 최소~최대"""
    )


def _render_level_section(monthly_df: pd.DataFrame):
    """Level 분석 섹션을 렌더링한다 (산점도 + 시계열 분리)."""
    st.header("금리 수준 vs 월말 누적 오차 (핵심)")

    # 산점도
    scatter_fig = create_level_scatter_chart(monthly_df, COL_E_M, DISPLAY_ERROR_END_OF_MONTH_PCT)
    st.plotly_chart(scatter_fig, width="stretch")

    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **금리 수준(rate_pct)**: FFR(%)
- **월말 누적 오차(e_m, %)**: 해당 월 마지막 거래일의 "시뮬 - 실제" 차이(%)
  - **양수(+)**: 시뮬레이션이 실제보다 더 좋게 나옴 (과대평가)
  - **음수(-)**: 시뮬레이션이 실제보다 더 나쁘게 나옴 (과소평가)

- **추세선**: 점들이 전체적으로 어느 방향으로 치우치는지 보여주는 선

## 지표를 해석하는 방법

- 금리가 높아질수록 e_m이 **+로 커지는 경향**이면:
  - 고금리에서 시뮬레이션이 실제보다 **좋게** 나오는 편
  - 흔한 원인: 고금리에서 **비용(조달비용/스프레드)을 실제보다 낮게 잡았을 가능성**

- 반대로 **-로 커지는 경향**이면 비용을 과하게 잡았을 가능성이 있습니다."""
    )

    st.divider()

    # 시계열
    ts_fig = create_level_timeseries_chart(monthly_df, COL_E_M, DISPLAY_ERROR_END_OF_MONTH_PCT)
    st.plotly_chart(ts_fig, width="stretch")

    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **시계열(Time Series)**: 시간 순서대로 값이 어떻게 변했는지 보는 그래프
- 일반적으로:
  - (선1) **금리(FFR)** 흐름
  - (선2) **월말 오차(e_m)** 흐름
    을 "시간축"에 함께 놓고 봅니다.

## 지표를 해석하는 방법

산점도는 "전체 관계(경향)"를, 시계열은 "언제부터/어느 구간에서"를 잘 보여줘요.

초보자 체크리스트 3개:

1. 금리가 **높아진 시기**에 오차가 **+쪽으로 오래 머무는지**
2. 금리가 **낮은 시기**에 오차가 **-쪽으로 오래 머무는지**
3. 특정 시점(충격장/급변 구간)에서 오차가 "뚝" 튀는지"""
    )

    st.divider()


def _render_delta_section(monthly_df: pd.DataFrame):
    """Delta 분석 섹션을 렌더링한다 (산점도 + Rolling 상관 분리)."""
    with st.expander("고급 분석: 델타 (Delta - 금리 변화 vs 오차 변화)", expanded=False):
        y_col_delta = COL_DE_M
        y_label_delta = DISPLAY_DELTA_MONTHLY_PCT

        lag = st.selectbox("시차 (Lag, 개월):", options=DEFAULT_LAG_OPTIONS, index=0)

        # 델타 산점도
        delta_fig, valid_df = create_delta_scatter_chart(monthly_df, y_col_delta, y_label_delta, lag)
        st.plotly_chart(delta_fig, width="stretch")

        st.markdown(
            """## 지표에 사용하는 용어에 대한 설명

- **금리 변화(dr_m)**: 전월 대비 금리 변화량
- **오차 변화(de_m)**: 전월 대비 월말 오차 변화량
- **Lag(시차)**:
  - Lag 0: 같은 달 변화량끼리 비교
  - Lag 1: 전월 금리 변화가 당월 오차 변화에 영향을 주는지
  - Lag 2: 2개월 늦게 반영되는지

## 지표를 해석하는 방법

- 델타 분석은 "금리 **수준**"이 아니라 "금리의 **변화 방향/속도**"가 오차 변화와 연결되는지 봅니다.
- 점들이 0 근처에 몰리고 추세가 약하면, 금리 변화량만으로 오차 변화를 설명하기 어렵습니다."""
        )

        st.divider()

        # Rolling 상관
        rolling_fig = create_rolling_correlation_chart(valid_df, y_col_delta)
        st.plotly_chart(rolling_fig, width="stretch")

        st.markdown(
            f"""## 지표에 사용하는 용어에 대한 설명

- **Rolling {ROLLING_CORR_WINDOW_MONTHS}개월 상관**: 최근 {ROLLING_CORR_WINDOW_MONTHS}개월만 잘라 상관계수를 계속 계산한 것
- **상관계수**: +면 같이, -면 반대로, 0이면 뚜렷하지 않음

## 지표를 해석하는 방법

- 한 숫자(전체기간 상관)보다, 롤링은 **구간별로 관계가 바뀌는지** (국면 변화)를 보여줍니다.
- 상관이 오래 한 방향이면 "그 구간에서는 관계가 비교적 안정적"
- 상관이 자주 뒤집히면 "관계가 불안정 → 단일 규칙 적용 위험\""""
        )


def _render_cross_validation_section(monthly_df: pd.DataFrame):
    """교차검증 섹션을 렌더링한다."""
    with st.expander("고급 분석: 교차검증 (Cross Validation - de_m vs sum_daily_m)", expanded=False):
        _display_cross_validation(monthly_df)


def _display_cross_validation(monthly_df: pd.DataFrame):
    """
    de_m vs sum_daily_m 교차검증 결과를 표시한다.

    둘이 거의 같아야 하지만, 반올림/결측/계산 방식 차이로 완전히 동일하지는 않다.

    Args:
        monthly_df: 월별 데이터 (de_m, sum_daily_m 포함)
    """
    st.subheader("교차검증 (Cross Validation): de_m vs sum_daily_m")

    valid_df = monthly_df.dropna(subset=[COL_DE_M, COL_SUM_DAILY_M])

    if len(valid_df) == 0:
        st.warning("교차검증 가능한 데이터가 없습니다.")
        return

    col_diff = "diff"
    col_abs_diff = "abs_diff"

    valid_df = valid_df.copy()
    valid_df[col_diff] = valid_df[COL_DE_M] - valid_df[COL_SUM_DAILY_M]

    max_diff = valid_df[col_diff].abs().max()
    mean_diff = valid_df[col_diff].abs().mean()
    std_diff = valid_df[col_diff].std()

    st.metric(label="최대 절댓값 차이 (Max Abs Diff)", value=f"{max_diff:.6f}%")
    st.metric(label="평균 절댓값 차이 (Mean Abs Diff)", value=f"{mean_diff:.6f}%")
    st.metric(label="표준편차 (Std Dev)", value=f"{std_diff:.6f}%")

    st.markdown("**|diff| 상위 5개월 (Top 5 Months with Largest |diff|)**:")
    valid_df_sorted = valid_df.copy()
    valid_df_sorted[col_abs_diff] = valid_df_sorted[col_diff].abs()
    top_diff_abs = valid_df_sorted.nlargest(DEFAULT_TOP_N_CROSS_VALIDATION, col_abs_diff, keep="all")[
        [COL_MONTH, COL_DE_M, COL_SUM_DAILY_M, col_diff, col_abs_diff]
    ]
    st.dataframe(top_diff_abs, hide_index=True)

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=valid_df[col_diff],
            nbinsx=DEFAULT_HISTOGRAM_BINS,
            name=DISPLAY_CHART_DIFF_DISTRIBUTION,
            marker={"color": "#9467bd"},
        )
    )
    fig.update_layout(
        title=f"de_m - sum_daily_m 차이 분포 (평균: {mean_diff:.6f}%, 표준편차: {std_diff:.6f}%)",
        xaxis_title=DISPLAY_AXIS_DIFF_PCT,
        yaxis_title=DISPLAY_AXIS_FREQUENCY,
        height=400,
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **de_m**: 월말 누적 오차(e_m)의 월간 변화(diff)
- **sum_daily_m**: 일일 오차 증분의 월합(sum)
- 두 방식은 계산 경로만 다르고 **거의 같아야 정상**입니다.

## 지표를 해석하는 방법

- 이 섹션은 "금리와의 관계"를 보기 전에 **오차 집계 로직이 일관적인지** 검증하는 안전장치입니다.
- max/mean abs diff가 매우 작으면 "집계 신뢰도 OK\""""
    )


# ============================================================
# Softplus 튜닝 결과 표시 함수
# ============================================================


def _render_softplus_tuning_section() -> None:
    """Softplus 동적 Spread 파라미터 튜닝 결과 섹션을 렌더링한다."""
    st.header("Softplus 동적 Spread 파라미터 튜닝 결과")

    _display_tuning_result(_load_csv(SOFTPLUS_TUNING_CSV_PATH))

    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- 모델: **spread = softplus(a + b \\* ffr_pct)**
- **a(절편)**: 기본 바닥값 성격(금리가 낮을 때 상대적으로 더 중요)
- **b(기울기)**: 금리 민감도 성격(금리가 높을수록 영향이 커짐)
- **softplus**: spread가 음수가 되지 않도록 하는 함수(항상 양수)
- **베스트(a,b)의 기준**: 후보 조합 중 **RMSE(%)를 최소**로 만드는 조합
(월말 누적오차 한 점이 아니라, "기간 전체의 추적 오차"를 점수로 봅니다.)

## 지표를 해석하는 방법

- 금리가 낮으면 **ffr_pct가 작아서 b \\* ffr_pct 항이 작고 → a의 영향이 상대적으로 더 큼**
- 금리가 높으면 **b \\* ffr_pct가 커져서 → b(기울기)의 영향이 크게 나타남**

- 중요한 오해 방지: "저금리면 a만 쓰고 b는 안 쓴다"가 아니라 **항상 a와 b 둘 다 사용**하고, 다만 금리 레벨에 따라 "영향 비중"이 달라집니다."""
    )


def _render_detailed_analysis_section() -> None:
    """상세 분석 섹션 (모델 도출 과정)을 렌더링한다."""
    with st.expander(
        "상세 분석: 모델 도출 과정 (워크포워드, b고정, Spread 비교)",
        expanded=False,
    ):
        st.info(
            "아래 섹션들은 Softplus 동적 스프레드 모델을 도출하고 검증하는 과정에서 "
            "수행한 중간 분석입니다.\n\n"
            "- **워크포워드 검증**: 파라미터가 시간에 따라 안정적인지 확인\n"
            "- **b 고정 워크포워드**: b를 전체기간 최적값으로 고정하고 a만 매월 최적화\n"
            "- **Spread 비교**: 고정 파라미터 vs 워크포워드 파라미터의 차이 시각화"
        )
        _render_walkforward_section()
        st.divider()
        _render_walkforward_fixed_b_section()
        st.divider()
        _render_spread_comparison_section()


def _display_tuning_result(tuning_df: pd.DataFrame) -> None:
    """
    튜닝 결과를 표시한다.

    Args:
        tuning_df: 튜닝 결과 DataFrame (a, b, rmse_pct 컬럼)
    """
    st.subheader("튜닝 결과")

    # 최적 파라미터 (첫 번째 행)
    best_row = tuning_df.iloc[0]

    # 핵심 결과 표시
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(label="최적 a (절편)", value=f"{best_row[COL_A]:.4f}")

    with col2:
        st.metric(label="최적 b (기울기)", value=f"{best_row[COL_B]:.4f}")

    with col3:
        st.metric(label="최적 RMSE (%)", value=f"{best_row[COL_RMSE_PCT]:.4f}")

    # 튜닝과 정적 spread 시계열은 같은 기간(QQQ · TQQQ 겹침 구간)으로 만들었다
    static_months = _load_csv(SOFTPLUS_SPREAD_SERIES_STATIC_PATH)["month"]
    st.caption(
        f"최적 RMSE 는 튜닝 전체기간({static_months.min()} ~ {static_months.max()})에서 잰 값입니다 — "
        "아래 워크포워드의 이어 붙인 RMSE(테스트 구간)와 잰 기간이 달라 직접 비교하지 않습니다."
    )

    # 상위 결과 테이블
    with st.expander("상위 10개 후보 결과", expanded=True):
        top_10 = tuning_df.head(10).copy()
        top_10.index = pd.Index(range(1, len(top_10) + 1), name="순위")
        top_10.columns = ["a", "b", "RMSE (%)"]
        st.dataframe(top_10, width="stretch")


# ============================================================
# 워크포워드 RMSE 비교 섹션
# ============================================================


def _render_walkforward_rmse_section() -> None:
    """완전 고정 · b 고정 · 동적 워크포워드의 이어 붙인 RMSE 와 월별 테스트 RMSE 를 렌더링한다."""
    st.header("워크포워드 RMSE 비교 (완전 고정 · b 고정 · 동적)")

    fab_result_df = _load_csv(TQQQ_WALKFORWARD_FIXED_AB_PATH)
    fb_result_df = _load_csv(TQQQ_WALKFORWARD_FIXED_B_PATH)
    dyn_result_df = _load_csv(TQQQ_WALKFORWARD_PATH)
    fab_summary = _load_summary(TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH)
    fb_summary = _load_summary(TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH)
    dyn_summary = _load_summary(TQQQ_WALKFORWARD_SUMMARY_PATH)
    test_start, test_end = _common_test_period(fab_result_df, fb_result_df, dyn_result_df)

    # --- 이어 붙인 RMSE ---
    st.subheader("이어 붙인 RMSE (Stitched RMSE)")
    st.caption(f"세 값 모두 같은 테스트 구간({test_start} ~ {test_end})에서 잰 값입니다.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="완전 고정 WF stitched RMSE (%)\n(a,b 전체기간 최적값 고정)",
            value=f"{fab_summary['stitched_rmse']:.4f}",
        )

    with col2:
        st.metric(label="동적 WF stitched RMSE (%)\n(a,b 모두 최적화)", value=f"{dyn_summary['stitched_rmse']:.4f}")

    with col3:
        st.metric(label="b고정 WF stitched RMSE (%)\n(b 고정, a만 최적화)", value=f"{fb_summary['stitched_rmse']:.4f}")

    # --- 금리 구간별 RMSE 비교 ---
    st.subheader("금리 구간별 RMSE 분해 (완전 고정 WF)")

    boundary_label = f"{fab_summary['rate_boundary_pct']:.0f}"

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**저금리 (0~{boundary_label}%)**")
        st.metric(label="저금리 구간 RMSE (%)", value=f"{fab_summary['low_rate_rmse']:.4f}")
        st.caption(f"거래일 수: {int(fab_summary['low_rate_days']):,}일")

    with col2:
        st.markdown(f"**고금리 ({boundary_label}%+)**")
        st.metric(label="고금리 구간 RMSE (%)", value=f"{fab_summary['high_rate_rmse']:.4f}")
        st.caption(f"거래일 수: {int(fab_summary['high_rate_days']):,}일")

    # --- 월별 테스트 RMSE 추이 차트 ---
    with st.expander("테스트 RMSE 추이 비교 (동적 vs b고정 vs 완전 고정)", expanded=True):
        fig_rmse = go.Figure()

        # 동적 워크포워드
        fig_rmse.add_trace(
            go.Scatter(
                x=dyn_result_df["test_month"],
                y=dyn_result_df["test_rmse_pct"],
                mode="lines",
                name="동적 WF (a,b 최적화)",
                line={"color": "red", "width": 1.5},
                opacity=0.7,
            )
        )

        # b 고정 워크포워드
        fig_rmse.add_trace(
            go.Scatter(
                x=fb_result_df["test_month"],
                y=fb_result_df["test_rmse_pct"],
                mode="lines",
                name=f"b고정 WF (b={fb_summary['b_mean']:.2f})",
                line={"color": "blue", "width": 1.5},
                opacity=0.7,
            )
        )

        # 완전 고정 워크포워드
        fig_rmse.add_trace(
            go.Scatter(
                x=fab_result_df["test_month"],
                y=fab_result_df["test_rmse_pct"],
                mode="lines",
                name="완전 고정 WF (a,b 고정)",
                line={"color": "green", "width": 1.5},
                opacity=0.7,
            )
        )

        fig_rmse.update_layout(
            title="월별 테스트 RMSE 추이 비교 (3종)",
            xaxis_title="테스트 월",
            yaxis_title="RMSE (%)",
            height=400,
            legend={"yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01},
        )
        st.plotly_chart(fig_rmse, width="stretch")

    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **완전 고정 WF stitched RMSE**: 전체기간 튜닝으로 고른 (a, b)를 매월 그대로 쓰고 테스트 구간을 연속 시뮬레이션한 RMSE
- **동적 WF stitched RMSE**: 매월 (a, b) 모두 최적화한 워크포워드의 연속 RMSE
- **b고정 WF stitched RMSE**: b를 전체기간 최적값으로 고정하고 a만 매월 최적화한 워크포워드의 연속 RMSE
- **금리 구간별 RMSE**: 완전 고정 WF 의 테스트 거래일을 그날 금리로 저금리 · 고금리로 나눠 잰 RMSE

## 지표를 해석하는 방법

- 세 값은 같은 테스트 구간에서 잰 RMSE 라 나란히 볼 수 있습니다. 다만 완전 고정의 a · b 와 b 고정의 b 는 테스트 구간까지 포함한 전체기간 튜닝값이라, 셋의 차이를 아웃오브샘플 성능 차이로 읽지 않습니다.
- 튜닝 결과의 최적 RMSE 는 전체기간에서 잰 값이라 이 셋과 직접 비교하지 않습니다."""
    )


# ============================================================
# 상세 분석: 워크포워드 · b 고정 · Spread 비교
# ============================================================


def _render_walkforward_fixed_b_section() -> None:
    """b 고정 워크포워드의 파라미터 안정성을 동적 워크포워드와 나란히 렌더링한다."""
    st.header("b 고정 워크포워드 검증 (b = 전체기간 최적값)")

    fb_summary = _load_summary(TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH)
    dyn_summary = _load_summary(TQQQ_WALKFORWARD_SUMMARY_PATH)

    # 고정 b 값
    fixed_b_value = fb_summary["b_mean"]

    # --- a 파라미터 안정성 비교 ---
    st.subheader("파라미터 안정성 비교")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**동적 워크포워드 (a, b 모두 최적화)**")
        st.write(f"- a 평균: {dyn_summary['a_mean']:.4f}")
        st.write(f"- a 표준편차: {dyn_summary['a_std']:.4f}")
        st.write(f"- b 평균: {dyn_summary['b_mean']:.4f}")
        st.write(f"- b 표준편차: {dyn_summary['b_std']:.4f}")

    with col2:
        st.markdown(f"**b 고정 워크포워드 (b={fixed_b_value:.4f} 고정)**")
        st.write(f"- a 평균: {fb_summary['a_mean']:.4f}")
        st.write(f"- a 표준편차: {fb_summary['a_std']:.4f}")
        st.write(f"- b 고정값: {fixed_b_value:.4f}")
        st.write(f"- b 표준편차: {fb_summary['b_std']:.4f} (0에 가까워야 정상)")

    st.markdown(
        f"""## 지표에 사용하는 용어에 대한 설명

- **b 고정 워크포워드**: b를 전체기간 최적값({fixed_b_value:.4f})으로 고정하고, a만 매월 최적화한 워크포워드
- 이어 붙인 RMSE 와 월별 테스트 RMSE 추이는 위 「워크포워드 RMSE 비교」 섹션에 있습니다."""
    )


def _render_spread_comparison_section() -> None:
    """
    고정 vs 워크포워드 spread 비교 시각화 섹션을 렌더링한다.

    정적 CSV와 워크포워드 CSV를 로드하여 두 가지 차트를 표시한다:
    1. 월별 spread 시계열 라인차트 (정적 spread_global + 워크포워드 spread_test)
    2. FFR vs spread 산점도 (정적 + 워크포워드)
    """
    st.header("Spread 비교: 고정 vs 워크포워드")

    # 데이터 로드
    static_df = _load_csv(SOFTPLUS_SPREAD_SERIES_STATIC_PATH)
    wf_result_df = _load_csv(TQQQ_WALKFORWARD_PATH)
    train_months = int(_load_summary(TQQQ_WALKFORWARD_SUMMARY_PATH)["train_window_months"])

    # 차트 1: 월별 spread 시계열 라인차트
    fig_ts = go.Figure()

    # 정적 spread (전체 기간)
    fig_ts.add_trace(
        go.Scatter(
            x=static_df["month"],
            y=static_df["spread_global"],
            mode="lines",
            name="정적 spread (전체기간 최적 a,b)",
            line={"color": "blue", "width": 2},
        )
    )

    # 워크포워드 spread (테스트 월만)
    fig_ts.add_trace(
        go.Scatter(
            x=wf_result_df["test_month"],
            y=wf_result_df["spread_test"],
            mode="lines+markers",
            name="워크포워드 spread (월별 최적 a,b)",
            line={"color": "red", "width": 2},
            marker={"size": 4},
        )
    )

    fig_ts.update_layout(
        title="월별 Spread 시계열 비교 (고정 vs 워크포워드)",
        xaxis_title="월",
        yaxis_title="Spread",
        height=400,
        legend={"yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01},
    )
    st.plotly_chart(fig_ts, width="stretch")

    # 차트 2: FFR vs spread 산점도
    fig_scatter = go.Figure()

    # 정적
    fig_scatter.add_trace(
        go.Scatter(
            x=static_df["ffr_pct"],
            y=static_df["spread_global"],
            mode="markers",
            name="정적 (전체기간 최적 a,b)",
            marker={"color": "blue", "size": 6, "opacity": 0.6},
        )
    )

    # 워크포워드
    fig_scatter.add_trace(
        go.Scatter(
            x=wf_result_df["ffr_pct_test"],
            y=wf_result_df["spread_test"],
            mode="markers",
            name="워크포워드 (월별 최적 a,b)",
            marker={"color": "red", "size": 6, "symbol": "diamond", "opacity": 0.6},
        )
    )

    fig_scatter.update_layout(
        title="FFR(%) vs Spread 산점도 (고정 vs 워크포워드)",
        xaxis_title="FFR (%)",
        yaxis_title="Spread",
        height=400,
        legend={"yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01},
    )
    st.plotly_chart(fig_scatter, width="stretch")

    st.markdown(
        f"""## 지표에 사용하는 용어에 대한 설명

- **정적 spread**: 전체 기간 데이터로 1회 튜닝한 고정 (a, b)로 계산한 spread
  - 매월 동일한 (a, b)를 적용하므로 spread 변동은 FFR 변화에만 의존
- **워크포워드 spread**: 매월 직전 {train_months}개월 학습으로 구한 (a_best, b_best)로 계산한 spread
  - 매월 (a, b)가 달라지므로, FFR 변화 + 파라미터 변화 두 요인이 작용

## 지표를 해석하는 방법

- **시계열 라인차트**:
  - 두 라인이 거의 겹치면: 워크포워드가 전체기간 최적과 비슷한 파라미터를 선택 → 안정적
  - 두 라인이 벌어지는 구간: 해당 시기에 국면이 바뀌어 워크포워드가 다른 (a, b)를 선택
- **산점도**:
  - 같은 FFR(%)에서 두 점이 가까우면 파라미터 차이가 작음
  - 같은 FFR(%)에서 두 점이 벌어지면 워크포워드가 해당 금리 구간에서 다른 비용 모델을 학습"""
    )


def _render_walkforward_section() -> None:
    """워크포워드 검증 결과 섹션을 렌더링한다."""
    st.header("워크포워드 검증 (파라미터 안정성)")

    _display_walkforward_result(_load_csv(TQQQ_WALKFORWARD_PATH), _load_summary(TQQQ_WALKFORWARD_SUMMARY_PATH))


def _display_walkforward_result(result_df: pd.DataFrame, summary: dict[str, float]) -> None:
    """
    워크포워드 검증 결과를 표시한다.

    Args:
        result_df: 워크포워드 결과 DataFrame
        summary: 워크포워드 요약 (지표 이름 → 값)
    """
    st.subheader("워크포워드 검증 결과")

    train_months = int(summary["train_window_months"])

    # 핵심 요약 지표
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(label="테스트 RMSE 평균 (%)", value=f"{summary['test_rmse_mean']:.4f}")

    with col2:
        st.metric(label="테스트 RMSE 중앙값 (%)", value=f"{summary['test_rmse_median']:.4f}")

    with col3:
        st.metric(label="a 평균 (std)", value=f"{summary['a_mean']:.2f} ({summary['a_std']:.2f})")

    with col4:
        st.metric(label="b 평균 (std)", value=f"{summary['b_mean']:.2f} ({summary['b_std']:.2f})")

    # 상세 요약
    with st.expander("상세 요약 통계", expanded=True):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**테스트 RMSE 통계**")
            st.write(f"- 평균: {summary['test_rmse_mean']:.4f}%")
            st.write(f"- 중앙값: {summary['test_rmse_median']:.4f}%")
            st.write(f"- 표준편차: {summary['test_rmse_std']:.4f}%")
            st.write(f"- 최솟값: {summary['test_rmse_min']:.4f}%")
            st.write(f"- 최댓값: {summary['test_rmse_max']:.4f}%")

        with col2:
            st.markdown("**파라미터 안정성**")
            st.write(f"- a 평균: {summary['a_mean']:.4f}")
            st.write(f"- a 표준편차: {summary['a_std']:.4f}")
            st.write(f"- b 평균: {summary['b_mean']:.4f}")
            st.write(f"- b 표준편차: {summary['b_std']:.4f}")
            st.write(f"- 테스트 월 수: {int(summary['n_test_months'])}개월")

        st.markdown(
            f"""## 지표에 사용하는 용어에 대한 설명

- **워크포워드(rolling)**: 과거 {train_months}개월로 (a,b)를 고른 뒤 → "다음 1개월"에서 성능(RMSE)을 보는 걸 매달 반복
- 워크포워드의 목적(한 줄): **"최적의 a,b를 찾는 방법(튜닝 절차)이 미래에서도 잘 통하나?" + "그 과정이 얼마나 안정적이냐?"**
- **테스트 RMSE 평균 · 중앙값**: 매월 실제 가격으로 시작점을 리셋한 뒤 1개월씩 잰 RMSE 의 평균 · 중앙값
  - 장기 누적 오차가 상쇄되어 값이 작게 나오므로, 리셋 없이 연속으로 잰 이어 붙인 RMSE 와 직접 비교하지 않습니다"""
        )

    # (a, b) 추이 차트
    with st.expander("(a, b) 파라미터 추이 차트", expanded=True):
        # a 파라미터 추이
        fig_a = go.Figure()
        fig_a.add_trace(
            go.Scatter(
                x=result_df["test_month"],
                y=result_df["a_best"],
                mode="lines+markers",
                name="a",
                line={"color": "blue"},
            )
        )
        fig_a.update_layout(
            title="a 파라미터 추이 (월별)",
            xaxis_title="테스트 월",
            yaxis_title="a 값",
            height=300,
        )
        st.plotly_chart(fig_a, width="stretch")

        # b 파라미터 추이
        fig_b = go.Figure()
        fig_b.add_trace(
            go.Scatter(
                x=result_df["test_month"],
                y=result_df["b_best"],
                mode="lines+markers",
                name="b",
                line={"color": "green"},
            )
        )
        fig_b.update_layout(
            title="b 파라미터 추이 (월별)",
            xaxis_title="테스트 월",
            yaxis_title="b 값",
            height=300,
        )
        st.plotly_chart(fig_b, width="stretch")

        st.markdown(
            f"""## 용어 설명

- **a, b 파라미터 추이**: 각 테스트 월 직전에, 과거 {train_months}개월 학습으로 선택된 "그 달의 최적값"의 시간 흐름

## 해석 방법 (중복 최소화)

- 여기서 보는 포인트는 "값이 크냐 작냐"보다 **얼마나 일정하게 유지되냐** (안정성)입니다.
- 체크리스트:
  1. 완만한가? (안정적)
  2. 계단처럼 튀는 구간이 있는가? (국면 변화/충격 가능성)
  3. 특히 b가 출렁이면 "고금리 민감도"가 시기별로 달라졌다는 뜻일 수 있음"""
        )

    # 테스트 RMSE 추이 차트
    with st.expander("테스트 RMSE 추이 차트", expanded=False):
        fig_rmse = go.Figure()
        fig_rmse.add_trace(
            go.Scatter(
                x=result_df["test_month"],
                y=result_df["test_rmse_pct"],
                mode="lines+markers",
                name="Test RMSE",
                line={"color": "red"},
            )
        )
        fig_rmse.update_layout(
            title="테스트 RMSE 추이 (월별)",
            xaxis_title="테스트 월",
            yaxis_title="RMSE (%)",
            height=300,
        )
        st.plotly_chart(fig_rmse, width="stretch")

        st.markdown(
            """## 용어 설명

- **test_rmse_pct**: 테스트 1개월 동안 "실제 TQQQ 가격 경로 vs 시뮬 가격 경로"가 얼마나 가까웠는지의 점수
  - 낮을수록 "잘 따라감"

## 해석 방법

- 체크리스트:
  1. 대부분 낮게 유지 → "꾸준히 잘 맞는 편"
  2. 스파이크(튀는 달) 존재 → 그 달은 충격/급변/모델 한계 구간일 수 있음

- 스파이크 달은 "버려야 할 달"이 아니라, **리스크 구간을 알려주는 힌트**입니다."""
        )

    # 전체 결과 테이블
    with st.expander("전체 결과 테이블", expanded=False):
        st.dataframe(result_df, width="stretch")

        st.markdown(
            f"""## 용어 설명

- 테이블의 한 행 = "한 테스트 월"의 기록
- 핵심 컬럼:
  - **train_start/train_end**: 학습 {train_months}개월 범위
  - **test_month**: 테스트 1개월
  - **a_best, b_best**: 그 달의 학습({train_months}개월)에서 RMSE를 최소화한 값
  - **train_rmse_pct (학습 RMSE)**:
    - 과거 {train_months}개월(학습 구간) 전체를 시뮬레이션해 잰 추적 오차(RMSE)
    - 이 값이 높으면 모델이 학습 데이터조차 잘 설명하지 못한다는 뜻
  - **test_rmse_pct (테스트 RMSE)**:
    - 학습에 사용하지 않은 "다음 1개월"을 그달 첫 거래일의 실제 가격에서 다시 시작해 잰 추적 오차(RMSE)
    - 이 값이 낮을수록 모델이 미래에도 잘 통한다는 의미
  - **train 과 test 를 견주지 않는 이유**:
    - 학습 RMSE 는 {train_months}개월, 테스트 RMSE 는 1개월을 잰 값이라 오차가 쌓이는 길이가 달라 테스트 쪽이 대개 더 작게 나옵니다 — 두 값의 차이로 과최적화를 판단하지 않습니다
  - **search_mode**: full grid인지 local refine인지
    - **full grid(전체 탐색)**
      - a와 b를 **넓은 범위**로 펼쳐 가능한 조합을 폭넓게 검사
      - 장점: 정답이 어디 있을지 몰라도 놓칠 확률이 낮음
      - 단점: 느림

    - **local refine(주변 미세조정)**
      - **이미 직전 달에 찾은 최적값(a_prev, b_prev)** 이 있으니, 그 주변의 좁은 범위만 다시 탐색해서 "조금 더 좋은 값"을 찾는 방식
      - 장점: 빠르고, 파라미터가 매달 멀리 점프하는 걸 줄여 **운영이 안정적**
      - 단점: 국면이 크게 바뀌어 정답이 멀리 이동한 달이면 더 좋은 해를 놓칠 수 있음

## 해석 방법

초보자용 3단계 워크플로우:

1. **test_rmse_pct가 튄 달** (스파이크)을 먼저 찾기
2. 그 달의 행에서 **a_best/b_best가 갑자기 점프했는지** 보기
3. 그 달이 **full grid였는지 / local refine였는지** 확인
   - local refine였는데 크게 틀리면 "정답이 멀리 이동했는데 주변만 찾았을 가능성" 같은 가설을 세우기 쉬워요."""
        )


# ============================================================
# 메인 함수
# ============================================================


def main():
    """Streamlit 앱 메인 함수"""
    try:
        # 페이지 설정
        st.set_page_config(
            page_title="TQQQ 금리-오차 관계 분석 (연구용)",
            page_icon=":bar_chart:",
            layout="wide",
        )

        # 사이드바
        with st.sidebar:
            st.header("TQQQ 금리-오차 분석")
            st.caption("QBT (Quant BackTest)")

        # 타이틀, 읽기 가이드
        _render_intro()

        # 데이터 로딩 및 월별 집계
        st.header("데이터 로딩 및 월별 집계")

        try:
            # 1. 월별 데이터 빌드 (캐시됨)
            monthly_df = build_artifacts(
                TQQQ_DAILY_COMPARISON_PATH,
                TQQQ_DAILY_COMPARISON_PATH.stat().st_mtime,
                FFR_DATA_PATH,
                FFR_DATA_PATH.stat().st_mtime,
            )
            st.success(f"월별 집계 완료: {len(monthly_df):,}개월")

            # 2. 요약 통계 표시
            _render_dataset_metrics(monthly_df)

        except ValueError as e:
            st.error(f"월별 집계 실패 (fail-fast):\n\n{str(e)}\n\n힌트: 데이터 기간/형식 확인")
            st.stop()
        except Exception as e:
            st.error(f"예상치 못한 오류:\n\n{str(e)}")
            st.stop()

        st.divider()

        # A. 금리-오차 관계 분석
        _render_level_section(monthly_df)
        _render_delta_section(monthly_df)
        _render_cross_validation_section(monthly_df)

        st.divider()

        # B. Softplus 모델 튜닝 결과
        _render_softplus_tuning_section()

        st.divider()

        # C. 워크포워드 RMSE 비교
        _render_walkforward_rmse_section()

        st.divider()

        # D. 상세 분석 (모델 도출 과정)
        _render_detailed_analysis_section()

        # 푸터
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - TQQQ 금리-오차 관계 분석 (연구용)")

    except Exception as e:
        st.error("애플리케이션 실행 중 예상치 못한 오류 발생:")
        st.exception(e)
        st.stop()


if __name__ == "__main__":
    main()
