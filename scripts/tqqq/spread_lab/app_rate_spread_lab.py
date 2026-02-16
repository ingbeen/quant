"""TQQQ 금리-오차 관계 분석 연구용 앱

금리 환경과 시뮬레이션 오차의 관계를 시각화하여 Softplus 동적 스프레드 모델의
검증 결과를 확인한다.

실행 명령어:
    poetry run streamlit run scripts/tqqq/spread_lab/app_rate_spread_lab.py

사전 준비:
    poetry run python scripts/tqqq/spread_lab/generate_rate_spread_lab.py

화면 구성 (단일 흐름):
- 금리-오차 관계 분석: 금리 수준 vs 월말 누적 오차 (핵심), 델타 분석, 교차검증
- Softplus 모델 튜닝 결과: 전체기간 최적 파라미터 (a, b)
- 과최적화 진단: 완전 고정 (a,b) 워크포워드 검증
- 상세 분석: 모델 도출 과정 (워크포워드, b고정, Spread 비교)

Fail-fast 정책:
- ValueError 발생 시 st.error() + st.stop()으로 즉시 중단
- 잘못된 차트/수치 표시 방지

사용자 경험:
- 모든 화면 텍스트 한글화 ("한글 (영문)" 형식)
- 명확한 레이블 및 설명 제공

관련 CLI 스크립트:
- softplus 튜닝: poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py
- 워크포워드 검증: poetry run python scripts/tqqq/spread_lab/validate_walkforward.py
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.analysis_helpers import (
    add_rate_change_lags,
    aggregate_monthly,
    calculate_daily_signed_log_diff,
)
from qbt.tqqq.constants import (
    COL_ACTUAL_DAILY_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DAILY_SIGNED,
    COL_DE_M,
    COL_E_M,
    COL_MONTH,
    COL_RATE_PCT,
    COL_SIMUL_DAILY_RETURN,
    COL_SUM_DAILY_M,
    DEFAULT_MIN_MONTHS_FOR_ANALYSIS,
    DEFAULT_TOP_N_CROSS_VALIDATION,
    DISPLAY_ERROR_END_OF_MONTH_PCT,
    FFR_DATA_PATH,
    LOOKUP_TUNING_CSV_PATH,
    LOOKUP_WALKFORWARD_PATH,
    LOOKUP_WALKFORWARD_SUMMARY_PATH,
    SOFTPLUS_SPREAD_SERIES_STATIC_PATH,
    SOFTPLUS_TUNING_CSV_PATH,
    TQQQ_DAILY_COMPARISON_PATH,
    TQQQ_WALKFORWARD_FIXED_AB_PATH,
    TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH,
    TQQQ_WALKFORWARD_FIXED_B_PATH,
    TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH,
    TQQQ_WALKFORWARD_PATH,
    TQQQ_WALKFORWARD_SUMMARY_PATH,
    WALKFORWARD_LOCAL_REFINE_A_DELTA,
    WALKFORWARD_LOCAL_REFINE_B_DELTA,
)
from qbt.tqqq.data_loader import (
    load_comparison_data,
    load_ffr_data,
)
from qbt.tqqq.visualization import (
    create_delta_scatter_chart,
    create_level_scatter_chart,
    create_level_timeseries_chart,
    create_rolling_correlation_chart,
)
from qbt.utils.logger import setup_logger

# ============================================================
# Streamlit 앱 전용 상수 (이 파일에서만 사용)
# ============================================================

# --- 기본값 파라미터 ---
DEFAULT_HISTOGRAM_BINS = 30  # 히스토그램 기본 bins
DEFAULT_LAG_OPTIONS = [0, 1, 2]  # Delta 분석 lag 선택지 (개월)
DEFAULT_STREAMLIT_COLUMNS = 3  # 요약 통계 표시용 컬럼 개수

# --- 튜닝 결과 CSV 컬럼명 ---
COL_A = "a"
COL_B = "b"
COL_RMSE_PCT = "rmse_pct"

# --- 출력용 한글 레이블 ---
DISPLAY_CHART_DIFF_DISTRIBUTION = "차이 분포"  # 히스토그램 차트명
DISPLAY_AXIS_DIFF_PCT = "차이 (%)"  # X축 레이블
DISPLAY_AXIS_FREQUENCY = "빈도"  # Y축 레이블
DISPLAY_DELTA_MONTHLY_PCT = "월간 변화 (%)"  # Delta 차트 y축

# --- 과최적화 진단 임계값 ---
DEFAULT_OVERFITTING_THRESHOLD_LOW = 0.5  # 약한 과최적화 경계 (%p)
DEFAULT_OVERFITTING_THRESHOLD_HIGH = 1.5  # 강한 과최적화 경계 (%p)

# ============================================================
# Logger 설정
# ============================================================
logger = setup_logger(__name__)

# ============================================================
# 데이터 빌드 (캐시)
# ============================================================


@st.cache_data
def build_artifacts(daily_path_str: str, ffr_path_str: str) -> pd.DataFrame:
    """
    일별 비교 데이터와 금리 데이터를 로드하고 월별로 집계한다.

    서버 기동 시 1회만 실행되며 이후 캐시 사용.
    파일 경로 문자열만 캐시 키로 사용하여 파일 변경을 무시한다.

    Args:
        daily_path_str: 일별 비교 CSV 파일 경로 (문자열)
        ffr_path_str: 금리 CSV 파일 경로 (문자열)

    Returns:
        월별 집계 DataFrame (month, e_m, de_m, sum_daily_m, rate_pct, dr_m 포함)

    Raises:
        ValueError: 파일 부재, 필수 컬럼 누락, 금리 커버리지 부족 등
    """
    # 1. 데이터 로드
    daily_df = load_comparison_data(Path(daily_path_str))
    ffr_df = load_ffr_data(Path(ffr_path_str))

    # 2. 월별 집계
    monthly_df = _prepare_monthly_data(daily_df, ffr_df)

    return monthly_df


def _prepare_monthly_data(
    daily_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    일별 데이터를 월별로 집계하고 금리 데이터와 매칭한다.

    처리 흐름:
        1. 일일 증분 signed 로그오차 계산
        2. 일별 데이터에 추가
        3. aggregate_monthly() 호출하여 월별 집계
        4. sum_daily_m 계산 (aggregate_monthly는 e_m, de_m만 제공)

    Args:
        daily_df: 일별 비교 데이터
        ffr_df: 금리 데이터

    Returns:
        월별 DataFrame (month, e_m, de_m, sum_daily_m, rate_pct, dr_m)

    Raises:
        ValueError: 필수 컬럼 누락, 금리 커버리지 부족, 월별 결과 부족 등
    """
    # 1. 일일 증분 signed 로그오차 계산
    daily_signed = calculate_daily_signed_log_diff(
        daily_return_real_pct=daily_df[COL_ACTUAL_DAILY_RETURN],
        daily_return_sim_pct=daily_df[COL_SIMUL_DAILY_RETURN],
    )

    # 2. 일별 데이터에 추가
    daily_with_signed = daily_df.copy()
    daily_with_signed[COL_DAILY_SIGNED] = daily_signed

    # 3. 월별 집계 (aggregate_monthly는 e_m, de_m만 제공)
    monthly = aggregate_monthly(
        daily_df=daily_with_signed,
        date_col=DISPLAY_DATE,
        signed_col=COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
        ffr_df=ffr_df,
        min_months_for_analysis=DEFAULT_MIN_MONTHS_FOR_ANALYSIS,
    )

    # 4. sum_daily_m 계산 (일일 증분의 월합)
    date_col_data = pd.to_datetime(daily_with_signed[DISPLAY_DATE])
    daily_with_signed[COL_MONTH] = date_col_data.dt.to_period("M")
    sum_daily_monthly = daily_with_signed.groupby(COL_MONTH, as_index=False)[COL_DAILY_SIGNED].sum()
    sum_daily_monthly[COL_SUM_DAILY_M] = sum_daily_monthly[COL_DAILY_SIGNED]
    sum_daily_monthly = sum_daily_monthly.drop(columns=[COL_DAILY_SIGNED])

    # 5. monthly에 merge하여 sum_daily_m 업데이트
    monthly = monthly.drop(columns=[COL_SUM_DAILY_M])
    monthly = monthly.merge(sum_daily_monthly, on=COL_MONTH, how="left")

    return monthly


# ============================================================
# UI 렌더링 함수
# ============================================================


def _render_intro():
    """타이틀, 스프레드 모델 변천사, 읽기 가이드를 렌더링한다."""
    st.title("TQQQ 금리-오차 관계 분석")
    st.markdown("금리 환경과 시뮬레이션 오차의 관계를 시각화하여 " "**Softplus 동적 스프레드 모델**의 검증 결과를 확인합니다.")

    # 스프레드 모델 변천사
    st.info(
        "**스프레드 모델 변천**\n\n"
        "- **초기**: 고정 스프레드 (0.0034 = 0.34%) "
        "— 금리 환경과 무관하게 일정한 비용\n"
        "- **현재**: Softplus 동적 스프레드 "
        "(spread = softplus(a + b × FFR%)) "
        "— 금리에 따라 비용이 자동 조정\n"
        "- **전환 이유**: 고정 스프레드는 고금리 구간에서 비용을 과소 반영하여 "
        "과대평가 편향이 발생했으며, 이 앱의 금리-오차 분석이 전환 근거가 됨"
    )

    # 읽기 가이드
    st.markdown(
        """## 이 화면 읽는 법

| 섹션 | 목적 | 중요도 |
|------|------|--------|
| **금리-오차 관계 분석** | 금리 수준/변화와 시뮬레이션 오차의 관계 파악 | 핵심 |
| **Softplus 모델 튜닝 결과** | 전체기간 최적 파라미터 (a, b) 확인 | 핵심 |
| **과최적화 진단** | 고정 파라미터가 미래에도 유효한지 검증 | 핵심 |
| **상세 분석 (모델 도출 과정)** | Softplus 모델 선택까지의 중간 검증 과정 | 참고 |"""
    )
    st.divider()


def _render_dataset_metrics(monthly_df: pd.DataFrame):
    """요약 통계를 표시한다."""
    col1, col2, col3 = st.columns(DEFAULT_STREAMLIT_COLUMNS)
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

    # VERBATIM #0: 데이터 로딩 및 월별 집계 설명
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
    try:
        scatter_fig = create_level_scatter_chart(monthly_df, COL_E_M, DISPLAY_ERROR_END_OF_MONTH_PCT)
        st.plotly_chart(scatter_fig, width="stretch")
    except Exception as e:
        st.error(f"산점도 차트 생성 실패:\n\n{str(e)}")

    # VERBATIM #1: 산점도 설명
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

- 반대로 **-로 커지는 경향**이면 비용을 과하게 잡았을 가능성이 있습니다.

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준으로 추세선이 **우상향**에 가깝습니다. → **금리 레벨이 높아질수록 월말 오차가 +쪽으로 치우칠 가능성**이 보입니다.
- 이 관찰이 **고정 스프레드(0.0034)에서 Softplus 동적 스프레드로 전환한 근거**가 되었습니다. 현재 데이터는 동적 스프레드 적용 후의 결과이며, 잔여 편향이 있는지 모니터링하는 용도로 활용합니다."""
    )

    st.divider()

    # 시계열
    try:
        ts_fig = create_level_timeseries_chart(monthly_df, COL_E_M, DISPLAY_ERROR_END_OF_MONTH_PCT)
        st.plotly_chart(ts_fig, width="stretch")
    except Exception as e:
        st.error(f"시계열 차트 생성 실패:\n\n{str(e)}")

    # VERBATIM #2: 시계열 추이 설명
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
3. 특정 시점(충격장/급변 구간)에서 오차가 "뚝" 튀는지

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준으로 **시기별로 오차의 중심이 달라지는(한쪽으로 치우쳤다가 돌아오는) 모습**이 보입니다.
- 이 패턴이 **금리 레벨에 따라 비용을 조정하는 Softplus 동적 스프레드 도입의 동기**가 되었습니다. 현재 데이터는 동적 스프레드 적용 후의 결과입니다."""
    )

    st.divider()


def _render_delta_section(monthly_df: pd.DataFrame):
    """Delta 분석 섹션을 렌더링한다 (산점도 + Rolling 상관 분리)."""
    with st.expander("고급 분석: 델타 (Delta - 금리 변화 vs 오차 변화)", expanded=False):
        y_col_delta = COL_DE_M
        y_label_delta = DISPLAY_DELTA_MONTHLY_PCT

        lag = st.selectbox("시차 (Lag, 개월):", options=DEFAULT_LAG_OPTIONS, index=0)

        try:
            # 델타 산점도
            delta_fig, valid_df = create_delta_scatter_chart(monthly_df, y_col_delta, y_label_delta, lag)
            st.plotly_chart(delta_fig, width="stretch")

            # VERBATIM #3: 델타 분석 설명
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
- 점들이 0 근처에 몰리고 추세가 약하면, 금리 변화량만으로 오차 변화를 설명하기 어렵습니다.

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준으로 델타 산점도는 강한 직선 관계라기보단 **흩어진 형태**에 가깝습니다.
- 오차를 설명하는 핵심은 "금리 변화(Δ)"보다는 **금리 수준(Level)** 쪽일 가능성이 더 크며, Lag 비교는 "보조 힌트"로 보는 게 안전합니다."""
            )

            st.divider()

            # Rolling 12개월 상관
            rolling_fig = create_rolling_correlation_chart(valid_df, y_col_delta)
            st.plotly_chart(rolling_fig, width="stretch")

            # VERBATIM #4: Rolling 12개월 상관 설명
            st.markdown(
                """## 지표에 사용하는 용어에 대한 설명

- **Rolling 12개월 상관**: 최근 12개월만 잘라 상관계수를 계속 계산한 것
- **상관계수**: +면 같이, -면 반대로, 0이면 뚜렷하지 않음

## 지표를 해석하는 방법

- 한 숫자(전체기간 상관)보다, 롤링은 **구간별로 관계가 바뀌는지** (국면 변화)를 보여줍니다.
- 상관이 오래 한 방향이면 "그 구간에서는 관계가 비교적 안정적"
- 상관이 자주 뒤집히면 "관계가 불안정 → 단일 규칙 적용 위험"

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준으로 상관이 구간별로 오르내리는 모습입니다.
- "금리-오차 관계"는 시기별로 강도가 달라질 수 있어, **동적 모델 + 워크포워드 같은 운영형 검증이 의미**가 있습니다."""
            )

        except ValueError as e:
            st.error(f"Delta 차트 생성 실패 (fail-fast):\n\n{str(e)}\n\n힌트: 데이터 부족 가능성")
        except Exception as e:
            st.error(f"예상치 못한 오류:\n\n{str(e)}")


def _render_cross_validation_section(monthly_df: pd.DataFrame):
    """교차검증 섹션을 렌더링한다."""
    with st.expander("고급 분석: 교차검증 (Cross Validation - de_m vs sum_daily_m)", expanded=False):
        try:
            _display_cross_validation(monthly_df)
        except Exception as e:
            st.error(f"교차검증 표시 실패:\n\n{str(e)}")


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

    # VERBATIM #5: 교차검증 설명
    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **de_m**: 월말 누적 오차(e_m)의 월간 변화(diff)
- **sum_daily_m**: 일일 오차 증분의 월합(sum)
- 두 방식은 계산 경로만 다르고 **거의 같아야 정상**입니다.

## 지표를 해석하는 방법

- 이 섹션은 "금리와의 관계"를 보기 전에 **오차 집계 로직이 일관적인지** 검증하는 안전장치입니다.
- max/mean abs diff가 매우 작으면 "집계 신뢰도 OK"

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준으로 diff가 매우 작은 수준으로 관리됩니다.
- 오차 계산/집계는 충분히 안정적이라, 이후 분석(델타/튜닝/워크포워드) 해석의 바닥이 튼튼한 편입니다."""
    )


# ============================================================
# Softplus 튜닝 결과 로드 및 표시 함수
# ============================================================


@st.cache_data
def _load_softplus_tuning_csv() -> pd.DataFrame | None:
    """
    Softplus 튜닝 결과 CSV를 로드한다.

    Returns:
        튜닝 결과 DataFrame 또는 None (파일 없음)
    """
    if not SOFTPLUS_TUNING_CSV_PATH.exists():
        return None
    return pd.read_csv(SOFTPLUS_TUNING_CSV_PATH)


@st.cache_data
def _load_static_spread_csv() -> pd.DataFrame | None:
    """
    정적 spread 시계열 CSV를 로드한다.

    Returns:
        정적 spread 시계열 DataFrame 또는 None (파일 없음)
    """
    if not SOFTPLUS_SPREAD_SERIES_STATIC_PATH.exists():
        return None
    return pd.read_csv(SOFTPLUS_SPREAD_SERIES_STATIC_PATH)


def _render_softplus_tuning_section() -> None:
    """Softplus 동적 Spread 파라미터 튜닝 결과 섹션을 렌더링한다."""
    st.header("Softplus 동적 Spread 파라미터 튜닝 결과")

    # CSV 파일 로드
    tuning_df = _load_softplus_tuning_csv()

    if tuning_df is None:
        st.warning(
            f"튜닝 결과 CSV 파일이 존재하지 않습니다.\n\n"
            f"파일 경로: `{SOFTPLUS_TUNING_CSV_PATH}`\n\n"
            f"**튜닝 실행 방법**:\n"
            f"```bash\n"
            f"poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py\n"
            f"```"
        )
    else:
        _display_tuning_result(tuning_df)

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

- 중요한 오해 방지: "저금리면 a만 쓰고 b는 안 쓴다"가 아니라 **항상 a와 b 둘 다 사용**하고, 다만 금리 레벨에 따라 "영향 비중"이 달라집니다.

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준으로 최적값이 **a=-6.10, b=0.37, RMSE=1.0467%** 형태로 제시됩니다.
- "고금리에서 비용을 더 얹는(b>0)" 구조가 전체기간 추적 오차를 줄이는 데 유리하게 작동한 결과로 해석할 수 있습니다."""
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
            "- **b 고정 워크포워드**: b를 고정하고 a만 최적화하여 과최적화 진단\n"
            "- **Spread 비교**: 고정 파라미터 vs 워크포워드 파라미터의 차이 시각화\n\n"
            "최종 결론은 위의 **과최적화 진단** 섹션을 참고하세요."
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

    # 상위 결과 테이블
    with st.expander("상위 10개 후보 결과", expanded=True):
        top_10 = tuning_df.head(10).copy()
        top_10.index = pd.Index(range(1, len(top_10) + 1), name="순위")
        top_10.columns = ["a", "b", "RMSE (%)"]
        st.dataframe(top_10, width="stretch")


# ============================================================
# 워크포워드 검증 결과 로드 및 표시 함수
# ============================================================


# ============================================================
# b 고정 워크포워드 검증 결과 로드 및 표시 함수
# ============================================================


@st.cache_data
def _load_walkforward_fixed_b_csv() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """
    b 고정 워크포워드 검증 결과 CSV를 로드한다.

    Returns:
        (result_df, summary_df) 튜플 또는 (None, None) (파일 없음)
    """
    if not TQQQ_WALKFORWARD_FIXED_B_PATH.exists() or not TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH.exists():
        return None, None

    result_df = pd.read_csv(TQQQ_WALKFORWARD_FIXED_B_PATH)
    summary_df = pd.read_csv(TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH)

    return result_df, summary_df


def _render_walkforward_fixed_b_section() -> None:
    """b 고정 워크포워드 검증 결과 섹션을 렌더링한다 (과최적화 진단)."""
    st.header("b 고정 워크포워드 검증 (과최적화 진단)")

    # b 고정 워크포워드 CSV 로드
    fb_result_df, fb_summary_df = _load_walkforward_fixed_b_csv()

    if fb_result_df is None or fb_summary_df is None:
        st.warning(
            f"b 고정 워크포워드 검증 결과 CSV 파일이 존재하지 않습니다.\n\n"
            f"파일 경로:\n"
            f"- `{TQQQ_WALKFORWARD_FIXED_B_PATH}`\n"
            f"- `{TQQQ_WALKFORWARD_FIXED_B_SUMMARY_PATH}`\n\n"
            f"**검증 실행 방법**:\n"
            f"```bash\n"
            f"poetry run python scripts/tqqq/spread_lab/validate_walkforward_fixed_b.py\n"
            f"```"
        )
        return

    # summary를 딕셔너리로 변환
    fb_summary = dict(zip(fb_summary_df["metric"], fb_summary_df["value"], strict=False))

    # 기존 동적 워크포워드 데이터도 로드
    dyn_result_df, dyn_summary_df = _load_walkforward_csv()
    dyn_summary: dict[str, float] | None = None
    if dyn_summary_df is not None:
        dyn_summary = dict(zip(dyn_summary_df["metric"], dyn_summary_df["value"], strict=False))

    # 정적 RMSE
    tuning_df = _load_softplus_tuning_csv()
    static_rmse: float | None = None
    if tuning_df is not None and len(tuning_df) > 0:
        static_rmse = float(tuning_df.iloc[0][COL_RMSE_PCT])

    # 고정 b 값
    fixed_b_value = fb_summary["b_mean"]

    # --- 3-metric RMSE 비교 ---
    st.subheader("RMSE 3자 비교 (정적 vs 동적 WF vs b고정 WF)")

    col1, col2, col3 = st.columns(3)

    with col1:
        if static_rmse is not None:
            st.metric(label="정적 RMSE (%)\n(전체기간 최적 a,b)", value=f"{static_rmse:.4f}")
        else:
            st.metric(label="정적 RMSE (%)", value="N/A")

    with col2:
        dyn_stitched = dyn_summary.get("stitched_rmse") if dyn_summary else None
        if dyn_stitched is not None:
            st.metric(label="동적 WF stitched RMSE (%)\n(a,b 모두 최적화)", value=f"{dyn_stitched:.4f}")
        else:
            st.metric(label="동적 WF stitched RMSE (%)", value="N/A")

    with col3:
        fb_stitched: float | None = fb_summary.get("stitched_rmse")  # type: ignore[assignment]
        if fb_stitched is not None:
            st.metric(
                label=f"b고정 WF stitched RMSE (%)\n(b={fixed_b_value:.4f} 고정, a만 최적화)",
                value=f"{fb_stitched:.4f}",
            )
        else:
            st.metric(label="b고정 WF stitched RMSE (%)", value="N/A")

    # --- 해석 결과 ---
    _render_fixed_b_interpretation(static_rmse, dyn_stitched, fb_stitched, fixed_b_value)

    # --- a 파라미터 안정성 비교 ---
    st.subheader("파라미터 안정성 비교")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**동적 워크포워드 (a, b 모두 최적화)**")
        if dyn_summary:
            st.write(f"- a 평균: {dyn_summary['a_mean']:.4f}")
            st.write(f"- a 표준편차: {dyn_summary['a_std']:.4f}")
            st.write(f"- b 평균: {dyn_summary['b_mean']:.4f}")
            st.write(f"- b 표준편차: {dyn_summary['b_std']:.4f}")
        else:
            st.info("동적 워크포워드 데이터 없음")

    with col2:
        st.markdown(f"**b 고정 워크포워드 (b={fixed_b_value:.4f} 고정)**")
        st.write(f"- a 평균: {fb_summary['a_mean']:.4f}")
        st.write(f"- a 표준편차: {fb_summary['a_std']:.4f}")
        st.write(f"- b 고정값: {fixed_b_value:.4f}")
        st.write(f"- b 표준편차: {fb_summary['b_std']:.4f} (0에 가까워야 정상)")

    # --- 테스트 RMSE 추이 비교 차트 ---
    with st.expander("테스트 RMSE 추이 비교 (동적 vs b고정)", expanded=True):
        fig_rmse = go.Figure()

        # 동적 워크포워드
        if dyn_result_df is not None:
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
                name=f"b고정 WF (b={fixed_b_value:.2f})",
                line={"color": "blue", "width": 1.5},
                opacity=0.7,
            )
        )

        fig_rmse.update_layout(
            title="월별 테스트 RMSE 추이 비교",
            xaxis_title="테스트 월",
            yaxis_title="RMSE (%)",
            height=400,
            legend={"yanchor": "top", "y": 0.99, "xanchor": "left", "x": 0.01},
        )
        st.plotly_chart(fig_rmse, width="stretch")

    # --- VERBATIM 설명 ---
    st.markdown(
        f"""## 지표에 사용하는 용어에 대한 설명

- **정적 RMSE**: 전체 기간 데이터로 1회 튜닝한 고정 (a, b)로, 전체 기간을 연속 시뮬레이션하여 산출한 RMSE
- **동적 WF stitched RMSE**: 매월 (a, b) 모두 최적화한 워크포워드를 연속으로 붙인 RMSE
- **b고정 WF stitched RMSE**: b를 전체기간 최적값({fixed_b_value:.4f})으로 고정하고, a만 매월 최적화한 워크포워드의 연속 RMSE

## 지표를 해석하는 방법

- **b고정 WF < 동적 WF**: b를 자유롭게 튜닝하는 것이 오히려 성능을 악화 → **b의 과최적화 확인**
- **b고정 WF < 정적 RMSE**: b 고정 + a만 동적 조정으로도 정적 모델 대비 개선 효과 있음 → **a의 동적 조정은 유효**
- **b고정 WF > 정적 RMSE**: a만 동적 조정해도 정적보다 나쁨 → 동적 모델 자체의 부가가치가 없을 수 있음"""
    )


def _render_fixed_b_interpretation(
    static_rmse: float | None,
    dyn_stitched: float | None,
    fb_stitched: float | None,
    fixed_b_value: float,
) -> None:
    """
    b 고정 워크포워드 RMSE 해석 결과를 표시한다.

    Args:
        static_rmse: 정적 RMSE (%) 또는 None
        dyn_stitched: 동적 워크포워드 stitched RMSE (%) 또는 None
        fb_stitched: b고정 워크포워드 stitched RMSE (%) 또는 None
        fixed_b_value: 고정된 b 값
    """
    st.markdown("## 현재 지표 해석 & 판단(결과)")

    if fb_stitched is None:
        st.info("b고정 워크포워드 RMSE를 산출할 수 없어 비교 판단이 불가합니다.")
        return

    findings = []

    # 1. b 고정 vs 동적 비교 (과최적화 진단 핵심)
    if dyn_stitched is not None:
        if fb_stitched < dyn_stitched:
            diff = dyn_stitched - fb_stitched
            findings.append(
                f"- **b고정 WF({fb_stitched:.4f}%) < 동적 WF({dyn_stitched:.4f}%)** "
                f"→ b를 고정하는 것이 **{diff:.4f}%p 더 낮아** b의 과최적화가 확인됩니다.\n"
                f"  - b를 자유롭게 튜닝하면 매월 노이즈에 반응하여 누적 오차가 커집니다."
            )
        elif fb_stitched > dyn_stitched:
            diff = fb_stitched - dyn_stitched
            findings.append(
                f"- **b고정 WF({fb_stitched:.4f}%) > 동적 WF({dyn_stitched:.4f}%)** "
                f"→ 동적 (a,b)가 **{diff:.4f}%p 더 낮아** b의 과최적화는 아닙니다.\n"
                f"  - b의 시간 변동이 실제 성능 개선에 기여하고 있습니다."
            )
        else:
            findings.append(f"- **b고정 WF({fb_stitched:.4f}%) ≈ 동적 WF({dyn_stitched:.4f}%)** " f"→ b 최적화의 영향이 미미합니다.")

    # 2. b 고정 vs 정적 비교 (a 동적 조정의 부가가치)
    if static_rmse is not None:
        if fb_stitched < static_rmse:
            diff = static_rmse - fb_stitched
            findings.append(
                f"- **b고정 WF({fb_stitched:.4f}%) < 정적({static_rmse:.4f}%)** "
                f"→ a만 동적으로 조정해도 정적 대비 **{diff:.4f}%p 개선** → a의 동적 조정은 유효합니다."
            )
        else:
            diff = fb_stitched - static_rmse
            findings.append(
                f"- **b고정 WF({fb_stitched:.4f}%) >= 정적({static_rmse:.4f}%)** "
                f"→ a만 동적 조정해도 정적보다 나쁨({diff:.4f}%p) → "
                f"현재로서는 전체기간 고정 (a={fixed_b_value:.4f} 포함) 정적 모델이 더 안정적입니다."
            )

    for finding in findings:
        st.markdown(finding)


# ============================================================
# 완전 고정 (a,b) 과최적화 진단 섹션
# ============================================================


@st.cache_data
def _load_walkforward_fixed_ab_csv() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """
    완전 고정 (a,b) 워크포워드 검증 결과 CSV를 로드한다.

    Returns:
        (result_df, summary_df) 튜플 또는 (None, None) (파일 없음)
    """
    if not TQQQ_WALKFORWARD_FIXED_AB_PATH.exists() or not TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH.exists():
        return None, None

    result_df = pd.read_csv(TQQQ_WALKFORWARD_FIXED_AB_PATH)
    summary_df = pd.read_csv(TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH)

    return result_df, summary_df


def _render_overfitting_interpretation(
    static_rmse: float | None,
    fab_stitched: float | None,
    dyn_stitched: float | None,
    fb_stitched: float | None,
    low_rate_rmse: float | None,
    high_rate_rmse: float | None,
    rate_boundary: float | None,
) -> None:
    """
    과최적화 진단 섹션의 수치 기반 해석 결과를 표시한다.

    Args:
        static_rmse: 정적 RMSE (%) 또는 None
        fab_stitched: 완전 고정 WF stitched RMSE (%) 또는 None
        dyn_stitched: 동적 WF stitched RMSE (%) 또는 None
        fb_stitched: b고정 WF stitched RMSE (%) 또는 None
        low_rate_rmse: 저금리 구간 RMSE (%) 또는 None
        high_rate_rmse: 고금리 구간 RMSE (%) 또는 None
        rate_boundary: 금리 구간 경계값 (%) 또는 None
    """
    st.markdown("## 현재 지표 해석 & 판단(결과)")

    if fab_stitched is None or static_rmse is None:
        st.info("완전 고정 WF RMSE 또는 정적 RMSE를 산출할 수 없어 비교 판단이 불가합니다.")
        return

    findings: list[str] = []

    # 1. 인샘플 vs 아웃오브샘플 격차
    gap = fab_stitched - static_rmse
    if gap < DEFAULT_OVERFITTING_THRESHOLD_LOW:
        findings.append(
            f"- **인샘플-아웃오브샘플 격차: {gap:.4f}%p** (< {DEFAULT_OVERFITTING_THRESHOLD_LOW}%p) "
            f"→ 전체기간 최적 (a,b) 파라미터가 **잘 일반화**되고 있습니다. 과최적화 아님."
        )
    elif gap < DEFAULT_OVERFITTING_THRESHOLD_HIGH:
        findings.append(
            f"- **인샘플-아웃오브샘플 격차: {gap:.4f}%p** ({DEFAULT_OVERFITTING_THRESHOLD_LOW}~{DEFAULT_OVERFITTING_THRESHOLD_HIGH}%p) "
            f"→ **약한 과최적화** 가능성. 실용적 범위이지만 모니터링이 필요합니다."
        )
    else:
        findings.append(
            f"- **인샘플-아웃오브샘플 격차: {gap:.4f}%p** (> {DEFAULT_OVERFITTING_THRESHOLD_HIGH}%p) "
            f"→ **과최적화 의심**. 다른 접근(동적 모델 등) 검토가 필요합니다."
        )

    # 2. 3종 비교 (완전 고정 vs 동적 vs b고정)
    if dyn_stitched is not None and fb_stitched is not None:
        if fab_stitched < fb_stitched < dyn_stitched:
            findings.append(
                f"- **RMSE 순서: 완전 고정({fab_stitched:.4f}%) < b고정({fb_stitched:.4f}%) < 동적({dyn_stitched:.4f}%)** "
                f"→ 파라미터 자유도가 높을수록 과최적화되기 쉬움을 확인. "
                f"전체기간 고정 모델이 연속 운용에 가장 안정적입니다."
            )
        elif fab_stitched < dyn_stitched:
            findings.append(
                f"- **완전 고정({fab_stitched:.4f}%) < 동적({dyn_stitched:.4f}%)** " f"→ 매월 재최적화보다 고정 파라미터가 연속 운용에서 더 안정적입니다."
            )

    # 3. 금리 구간별 RMSE 분석
    if low_rate_rmse is not None and high_rate_rmse is not None:
        boundary_str = f"{rate_boundary:.0f}" if rate_boundary is not None else "2"
        diff = high_rate_rmse - low_rate_rmse
        if diff > 0:
            findings.append(
                f"- **금리 구간별 RMSE: 저금리({low_rate_rmse:.4f}%) < 고금리({high_rate_rmse:.4f}%)** "
                f"(차이: {diff:.4f}%p) "
                f"→ 고금리({boundary_str}%+) 구간에서 추적 오차가 더 크며, "
                f"고정 모델의 비용 반영이 고금리에서 상대적으로 부족할 수 있습니다."
            )
        else:
            findings.append(
                f"- **금리 구간별 RMSE: 저금리({low_rate_rmse:.4f}%) >= 고금리({high_rate_rmse:.4f}%)** "
                f"→ 금리 구간에 따른 추적 오차 편차가 크지 않아, "
                f"고정 모델이 금리 환경 전반에 걸쳐 균형 잡힌 성능을 보입니다."
            )

    for finding in findings:
        st.markdown(finding)


def _render_overfitting_diagnosis_section() -> None:
    """완전 고정 (a,b) 과최적화 진단 섹션을 렌더링한다."""
    st.header("과최적화 진단 (완전 고정 a,b)")

    # CSV 로드
    fab_result_df, fab_summary_df = _load_walkforward_fixed_ab_csv()

    if fab_result_df is None or fab_summary_df is None:
        st.warning(
            f"완전 고정 (a,b) 워크포워드 검증 결과 CSV 파일이 존재하지 않습니다.\n\n"
            f"파일 경로:\n"
            f"- `{TQQQ_WALKFORWARD_FIXED_AB_PATH}`\n"
            f"- `{TQQQ_WALKFORWARD_FIXED_AB_SUMMARY_PATH}`\n\n"
            f"**검증 실행 방법**:\n"
            f"```bash\n"
            f"poetry run python scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py\n"
            f"```"
        )
        return

    # summary를 딕셔너리로 변환
    fab_summary = dict(zip(fab_summary_df["metric"], fab_summary_df["value"], strict=False))

    # 기존 데이터 로드
    dyn_result_df, dyn_summary_df = _load_walkforward_csv()
    dyn_summary: dict[str, float] | None = None
    if dyn_summary_df is not None:
        dyn_summary = dict(zip(dyn_summary_df["metric"], dyn_summary_df["value"], strict=False))

    fb_result_df, fb_summary_df = _load_walkforward_fixed_b_csv()
    fb_summary: dict[str, float] | None = None
    if fb_summary_df is not None:
        fb_summary = dict(zip(fb_summary_df["metric"], fb_summary_df["value"], strict=False))

    # 정적 RMSE
    tuning_df = _load_softplus_tuning_csv()
    static_rmse: float | None = None
    if tuning_df is not None and len(tuning_df) > 0:
        static_rmse = float(tuning_df.iloc[0][COL_RMSE_PCT])

    # --- RMSE 4자 비교 ---
    st.subheader("RMSE 4자 비교 (인샘플 vs 아웃오브샘플)")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if static_rmse is not None:
            st.metric(label="정적 RMSE (%)\n(인샘플)", value=f"{static_rmse:.4f}")
        else:
            st.metric(label="정적 RMSE (%)", value="N/A")

    with col2:
        fab_stitched: float | None = fab_summary.get("stitched_rmse")  # type: ignore[assignment]
        if fab_stitched is not None:
            st.metric(
                label="완전 고정 WF stitched RMSE (%)\n(아웃오브샘플)",
                value=f"{fab_stitched:.4f}",
            )
        else:
            st.metric(label="완전 고정 WF stitched RMSE (%)", value="N/A")

    with col3:
        dyn_stitched = dyn_summary.get("stitched_rmse") if dyn_summary else None
        if dyn_stitched is not None:
            st.metric(label="동적 WF stitched RMSE (%)\n(a,b 모두 최적화)", value=f"{dyn_stitched:.4f}")
        else:
            st.metric(label="동적 WF stitched RMSE (%)", value="N/A")

    with col4:
        fb_stitched: float | None = fb_summary.get("stitched_rmse") if fb_summary else None  # type: ignore[assignment]
        if fb_stitched is not None:
            st.metric(label="b고정 WF stitched RMSE (%)\n(b 고정, a만 최적화)", value=f"{fb_stitched:.4f}")
        else:
            st.metric(label="b고정 WF stitched RMSE (%)", value="N/A")

    # --- 과최적화 판단 로직 ---
    if fab_stitched is not None and static_rmse is not None:
        gap = fab_stitched - static_rmse
        st.subheader("과최적화 판단")

        if gap < DEFAULT_OVERFITTING_THRESHOLD_LOW:
            st.success(
                f"인샘플-아웃오브샘플 격차: **{gap:.4f}%p** (< {DEFAULT_OVERFITTING_THRESHOLD_LOW}%p)\n\n"
                f"**판단: 과최적화 아님** - 전체기간 최적 (a,b) 파라미터가 잘 일반화되고 있습니다."
            )
        elif gap < DEFAULT_OVERFITTING_THRESHOLD_HIGH:
            st.warning(
                f"인샘플-아웃오브샘플 격차: **{gap:.4f}%p** ({DEFAULT_OVERFITTING_THRESHOLD_LOW}~{DEFAULT_OVERFITTING_THRESHOLD_HIGH}%p)\n\n"
                f"**판단: 약한 과최적화** - 실용적 범위이지만 모니터링이 필요합니다."
            )
        else:
            st.error(
                f"인샘플-아웃오브샘플 격차: **{gap:.4f}%p** (> {DEFAULT_OVERFITTING_THRESHOLD_HIGH}%p)\n\n"
                f"**판단: 과최적화 의심** - 다른 접근(동적 모델 등) 검토가 필요합니다."
            )

    # --- 금리 구간별 RMSE 비교 ---
    st.subheader("금리 구간별 RMSE 분해")

    # summary CSV에서 금리 구간별 RMSE 로드
    rate_boundary: float | None = fab_summary.get("rate_boundary_pct")  # type: ignore[assignment]
    low_rate_rmse: float | None = fab_summary.get("low_rate_rmse")  # type: ignore[assignment]
    high_rate_rmse: float | None = fab_summary.get("high_rate_rmse")  # type: ignore[assignment]
    low_rate_days: int | None = fab_summary.get("low_rate_days")  # type: ignore[assignment]
    high_rate_days: int | None = fab_summary.get("high_rate_days")  # type: ignore[assignment]

    boundary_label = f"{rate_boundary:.0f}" if rate_boundary is not None else "2"

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**저금리 (0~{boundary_label}%)**")
        if low_rate_rmse is not None:
            st.metric(label="저금리 구간 RMSE (%)", value=f"{low_rate_rmse:.4f}")
            if low_rate_days is not None:
                st.caption(f"거래일 수: {int(low_rate_days):,}일")
        else:
            st.info(
                "금리 구간별 RMSE가 summary CSV에 없습니다.\n\n"
                "스크립트를 재실행하세요:\n"
                "`poetry run python scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py`"
            )

    with col2:
        st.markdown(f"**고금리 ({boundary_label}%+)**")
        if high_rate_rmse is not None:
            st.metric(label="고금리 구간 RMSE (%)", value=f"{high_rate_rmse:.4f}")
            if high_rate_days is not None:
                st.caption(f"거래일 수: {int(high_rate_days):,}일")
        else:
            st.info(
                "금리 구간별 RMSE가 summary CSV에 없습니다.\n\n"
                "스크립트를 재실행하세요:\n"
                "`poetry run python scripts/tqqq/spread_lab/validate_walkforward_fixed_ab.py`"
            )

    # --- 월별 테스트 RMSE 추이 차트 ---
    with st.expander("테스트 RMSE 추이 비교 (동적 vs b고정 vs 완전 고정)", expanded=True):
        fig_rmse = go.Figure()

        # 동적 워크포워드
        if dyn_result_df is not None:
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
        if fb_result_df is not None:
            fb_fixed_b_value = fb_summary.get("b_mean", 0) if fb_summary else 0
            fig_rmse.add_trace(
                go.Scatter(
                    x=fb_result_df["test_month"],
                    y=fb_result_df["test_rmse_pct"],
                    mode="lines",
                    name=f"b고정 WF (b={fb_fixed_b_value:.2f})",
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

    # --- VERBATIM 설명 ---
    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **정적 RMSE (인샘플)**: 전체 기간 데이터로 1회 튜닝한 고정 (a, b)로 전체 기간을 시뮬레이션한 RMSE. 미래 데이터를 포함하여 튜닝했으므로 인샘플 성격.
- **완전 고정 WF stitched RMSE (아웃오브샘플)**: 위와 동일한 고정 (a, b)를 테스트 기간에만 적용하여 연속 시뮬레이션한 RMSE. 파라미터 재최적화 없이 적용하므로 아웃오브샘플 성격.
- **동적 WF stitched RMSE**: 매월 (a, b) 모두 최적화한 워크포워드의 연속 RMSE
- **b고정 WF stitched RMSE**: b를 전체기간 최적값으로 고정하고 a만 매월 최적화한 워크포워드의 연속 RMSE

## 지표를 해석하는 방법

- **인샘플-아웃오브샘플 격차** = 완전 고정 WF RMSE - 정적 RMSE
  - 격차가 작으면 파라미터가 잘 일반화됨 (과최적화 아님)
  - 격차가 크면 전체기간 데이터에 과적합된 파라미터 (과최적화 의심)
- **3종 비교**: 동적 > b고정 > 완전 고정 순이면 파라미터 자유도가 높을수록 과최적화되기 쉬움을 시사"""
    )

    # 수치 기반 동적 분석 결과
    _render_overfitting_interpretation(
        static_rmse=static_rmse,
        fab_stitched=fab_stitched,
        dyn_stitched=dyn_stitched,
        fb_stitched=fb_stitched,
        low_rate_rmse=low_rate_rmse,
        high_rate_rmse=high_rate_rmse,
        rate_boundary=rate_boundary,
    )


def _render_spread_comparison_section() -> None:
    """
    고정 vs 워크포워드 spread 비교 시각화 섹션을 렌더링한다.

    정적 CSV와 워크포워드 CSV를 로드하여 두 가지 차트를 표시한다:
    1. 월별 spread 시계열 라인차트 (정적 spread_global + 워크포워드 spread_test)
    2. FFR vs spread 산점도 (정적 + 워크포워드)

    파일이 없으면 st.warning 표시 후 리턴한다.
    """
    st.header("Spread 비교: 고정 vs 워크포워드")

    # 데이터 로드
    static_df = _load_static_spread_csv()
    wf_result_df, _ = _load_walkforward_csv()

    if static_df is None:
        st.warning(
            f"정적 spread 시계열 CSV 파일이 존재하지 않습니다.\n\n"
            f"파일 경로: `{SOFTPLUS_SPREAD_SERIES_STATIC_PATH}`\n\n"
            f"**생성 방법**:\n"
            f"```bash\n"
            f"poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py\n"
            f"```"
        )
        return

    if wf_result_df is None:
        st.warning(
            f"워크포워드 결과 CSV 파일이 존재하지 않습니다.\n\n"
            f"파일 경로: `{TQQQ_WALKFORWARD_PATH}`\n\n"
            f"**생성 방법**:\n"
            f"```bash\n"
            f"poetry run python scripts/tqqq/spread_lab/validate_walkforward.py\n"
            f"```"
        )
        return

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
    if "ffr_pct_test" in wf_result_df.columns and "spread_test" in wf_result_df.columns:
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

    # VERBATIM: Spread 비교 섹션 설명
    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **정적 spread**: 전체 기간 데이터로 1회 튜닝한 고정 (a, b)로 계산한 spread
  - 매월 동일한 (a, b)를 적용하므로 spread 변동은 FFR 변화에만 의존
- **워크포워드 spread**: 매월 직전 60개월 학습으로 구한 (a_best, b_best)로 계산한 spread
  - 매월 (a, b)가 달라지므로, FFR 변화 + 파라미터 변화 두 요인이 작용

## 지표를 해석하는 방법

- **시계열 라인차트**:
  - 두 라인이 거의 겹치면: 워크포워드가 전체기간 최적과 비슷한 파라미터를 선택 → 안정적
  - 두 라인이 벌어지는 구간: 해당 시기에 국면이 바뀌어 워크포워드가 다른 (a, b)를 선택
- **산점도**:
  - 같은 FFR(%)에서 두 점이 가까우면 파라미터 차이가 작음
  - 같은 FFR(%)에서 두 점이 벌어지면 워크포워드가 해당 금리 구간에서 다른 비용 모델을 학습

## 현재 지표 해석 & 판단(결과)

- 두 라인이 대체로 비슷하게 움직이면, 전체기간 최적 파라미터가 시기별로도 무난하게 통한다는 의미입니다.
- 벌어지는 구간을 중심으로 국면 변화(금리 급변, 변동성 충격 등)를 점검하면 모델 개선 힌트를 얻을 수 있습니다."""
    )


@st.cache_data
def _load_walkforward_csv() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """
    워크포워드 검증 결과 CSV를 로드한다.

    Returns:
        (result_df, summary_df) 튜플 또는 (None, None) (파일 없음)
    """
    if not TQQQ_WALKFORWARD_PATH.exists() or not TQQQ_WALKFORWARD_SUMMARY_PATH.exists():
        return None, None

    result_df = pd.read_csv(TQQQ_WALKFORWARD_PATH)
    summary_df = pd.read_csv(TQQQ_WALKFORWARD_SUMMARY_PATH)

    # summary를 딕셔너리로 변환
    return result_df, summary_df


def _render_walkforward_section() -> None:
    """워크포워드 검증 결과 섹션을 렌더링한다."""
    st.header("워크포워드 검증 (파라미터 안정성)")

    # CSV 파일 로드
    result_df, summary_df = _load_walkforward_csv()

    if result_df is None or summary_df is None:
        st.warning(
            f"워크포워드 검증 결과 CSV 파일이 존재하지 않습니다.\n\n"
            f"파일 경로:\n"
            f"- `{TQQQ_WALKFORWARD_PATH}`\n"
            f"- `{TQQQ_WALKFORWARD_SUMMARY_PATH}`\n\n"
            f"**검증 실행 방법**:\n"
            f"```bash\n"
            f"poetry run python scripts/tqqq/spread_lab/validate_walkforward.py\n"
            f"```\n\n"
            f"**주의**: 워크포워드 검증은 시간이 오래 걸릴 수 있습니다 (약 30-60분)."
        )
    else:
        _display_walkforward_result(result_df, summary_df)


def _render_rmse_comparison(summary: dict[str, float]) -> None:
    """
    정적 RMSE vs 연속 워크포워드 RMSE를 비교 표시한다.

    동일한 누적배수 로그차이 RMSE 수식을 사용하여 정합성 있는 비교를 제공한다.
    - 정적 RMSE: 전체기간 최적 (a, b)로 전체 기간 연속 시뮬레이션한 결과
    - 연속 워크포워드 RMSE: 워크포워드 결과를 연속으로 붙여 시뮬레이션한 결과
    - 월별 리셋 평균 RMSE: 매월 실제 가격으로 리셋하여 계산한 평균 (참고용)

    Args:
        summary: 워크포워드 요약 딕셔너리 (test_rmse_mean 등)
    """
    st.subheader("RMSE 정합 비교 (동일 수식 기준)")

    # 정적 RMSE 로드
    tuning_df = _load_softplus_tuning_csv()
    static_rmse: float | None = None
    if tuning_df is not None and len(tuning_df) > 0:
        static_rmse = float(tuning_df.iloc[0][COL_RMSE_PCT])

    # 연속 워크포워드 RMSE (summary CSV에서 읽기)
    stitched_rmse: float | None = summary.get("stitched_rmse")  # type: ignore[assignment]

    # 3개 지표 표시
    col1, col2, col3 = st.columns(3)

    with col1:
        if static_rmse is not None:
            st.metric(label="정적 RMSE (%) (전체기간 최적 a,b)", value=f"{static_rmse:.4f}")
        else:
            st.metric(label="정적 RMSE (%)", value="N/A")

    with col2:
        if stitched_rmse is not None:
            st.metric(label="연속 워크포워드 RMSE (%)", value=f"{stitched_rmse:.4f}")
        else:
            st.metric(label="연속 워크포워드 RMSE (%)", value="N/A")
            st.caption("데이터 부족으로 계산 불가")

    with col3:
        st.metric(
            label="월별 리셋 평균 RMSE (%) (참고)",
            value=f"{summary['test_rmse_mean']:.4f}",
        )

    # 용어 설명 + 해석 방법
    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **정적 RMSE**: 전체 기간 데이터로 1회 튜닝한 고정 (a, b)로, **전체 기간을 연속 시뮬레이션**하여 산출한 RMSE
- **연속 워크포워드 RMSE**: 워크포워드로 매월 선택된 spread를 **리셋 없이 연속으로 붙여** 시뮬레이션한 RMSE
  - 정적 RMSE와 **동일한 누적배수 로그차이 수식**을 사용하므로 1:1 비교 가능
- **월별 리셋 평균 RMSE**: 매월 실제 가격으로 시작점을 리셋한 뒤 1개월씩 RMSE를 구해 평균낸 값
  - 장기 누적 오차가 상쇄되므로 값이 작게 나옴 → 정적 RMSE와 직접 비교하면 오해 소지

## 지표를 해석하는 방법

- **정적 RMSE > 연속 워크포워드 RMSE**이면: 워크포워드가 연속 시뮬에서도 정적보다 우수 → 동적 spread의 실질적 개선 효과
- **정적 RMSE ≈ 연속 워크포워드 RMSE**이면: 워크포워드가 정적과 비슷 → 추가 복잡성 대비 이득이 크지 않음
- **정적 RMSE < 연속 워크포워드 RMSE**이면: 워크포워드가 과적합 가능성 → 파라미터 변동이 오히려 성능 저하"""
    )

    # 현재 지표 해석 (동적 생성)
    _render_rmse_interpretation(static_rmse, stitched_rmse, summary["test_rmse_mean"])

    st.divider()


def _render_rmse_interpretation(
    static_rmse: float | None,
    stitched_rmse: float | None,
    monthly_reset_rmse: float,
) -> None:
    """
    현재 RMSE 수치를 기반으로 해석 결과를 표시한다.

    정적 RMSE와 연속 워크포워드 RMSE의 대소 관계에 따라
    동적 spread 전략의 유효성을 판단하는 텍스트를 생성한다.

    Args:
        static_rmse: 정적 RMSE (%) 또는 None
        stitched_rmse: 연속 워크포워드 RMSE (%) 또는 None
        monthly_reset_rmse: 월별 리셋 평균 RMSE (%)
    """
    st.markdown("## 현재 지표 해석 & 판단(결과)")

    if static_rmse is None or stitched_rmse is None:
        st.info("정적 RMSE 또는 연속 워크포워드 RMSE를 산출할 수 없어 비교 판단이 불가합니다.")
        return

    # 대소 관계 판단
    if static_rmse > stitched_rmse:
        # 워크포워드 우수
        diff = static_rmse - stitched_rmse
        st.markdown(
            f"- **정적 RMSE({static_rmse:.4f}%) > 연속 워크포워드 RMSE({stitched_rmse:.4f}%)** "
            f"→ 워크포워드가 정적보다 **{diff:.4f}%p 낮아** 연속 시뮬에서도 우수합니다.\n"
            f"- 동적 spread 전략이 실제 연속 운용에서도 정적 모델 대비 개선 효과가 있음을 의미합니다.\n"
            f"- 월별 리셋 평균 RMSE({monthly_reset_rmse:.4f}%)가 낮은 것이 단순 리셋 효과가 아닌, "
            f"실제 경로 추적 성능 개선임이 확인됩니다."
        )
    elif static_rmse < stitched_rmse:
        # 워크포워드 열등 → 과적합 가능성
        diff = stitched_rmse - static_rmse
        st.markdown(
            f"- **정적 RMSE({static_rmse:.4f}%) < 연속 워크포워드 RMSE({stitched_rmse:.4f}%)** "
            f"→ 워크포워드가 정적보다 **{diff:.4f}%p 높아** 과적합 가능성이 있습니다.\n"
            f"- 월별로 (a, b)를 변경하는 것이 오히려 누적 오차를 키우고 있습니다.\n"
            f"- 월별 리셋 평균 RMSE({monthly_reset_rmse:.4f}%)가 낮게 보이는 것은 "
            f"매월 시작가격을 리셋하여 누적 오차가 상쇄되기 때문입니다.\n"
            f"- 현재로서는 **전체기간 고정 (a, b)를 사용하는 정적 모델이 연속 운용에 더 안정적**입니다."
        )
    else:
        # 동일
        st.markdown(
            f"- **정적 RMSE({static_rmse:.4f}%) ≈ 연속 워크포워드 RMSE({stitched_rmse:.4f}%)** "
            f"→ 두 방식의 성능이 유사합니다.\n"
            f"- 워크포워드의 추가 복잡성 대비 실질적 이득이 크지 않습니다."
        )


def _display_walkforward_result(result_df: pd.DataFrame, summary_df: pd.DataFrame) -> None:
    """
    워크포워드 검증 결과를 표시한다.

    Args:
        result_df: 워크포워드 결과 DataFrame
        summary_df: 워크포워드 요약 DataFrame (metric, value 컬럼)
    """
    st.subheader("워크포워드 검증 결과")

    # summary_df를 딕셔너리로 변환
    summary = dict(zip(summary_df["metric"], summary_df["value"], strict=False))

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

    # RMSE 비교: 정적 vs 연속 워크포워드
    _render_rmse_comparison(summary)

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
            """## 지표에 사용하는 용어에 대한 설명

- **워크포워드(rolling)**: 과거 60개월로 (a,b)를 고른 뒤 → "다음 1개월"에서 성능(RMSE)을 보는 걸 매달 반복
- 워크포워드의 목적(한 줄): **"최적의 a,b를 찾는 방법(튜닝 절차)이 미래에서도 잘 통하나?" + "그 과정이 얼마나 안정적이냐?"**

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준 test RMSE의 평균/중앙값이 낮게 유지되는 편이며, 일부 구간에 스파이크가 보입니다.
- "튜닝 절차는 대체로 미래에서도 통하지만, 특정 국면에서는 성능이 튈 수 있다"는 전형적인 결론을 낼 수 있습니다.
- 실전 적용 시엔 스파이크 구간을 따로 분석하거나 리스크 관리 규칙(보수적 상한 등)을 고려하는 게 안전합니다."""
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

        # VERBATIM #8: (a, b) 추이 차트 설명
        st.markdown(
            """## 용어 설명

- **a, b 파라미터 추이**: 각 테스트 월 직전에, 과거 60개월 학습으로 선택된 "그 달의 최적값"의 시간 흐름

## 해석 방법 (중복 최소화)

- 여기서 보는 포인트는 "값이 크냐 작냐"보다 **얼마나 일정하게 유지되냐** (안정성)입니다.
- 체크리스트:
  1. 완만한가? (안정적)
  2. 계단처럼 튀는 구간이 있는가? (국면 변화/충격 가능성)
  3. 특히 b가 출렁이면 "고금리 민감도"가 시기별로 달라졌다는 뜻일 수 있음

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준 a는 비교적 완만한 편이고, b는 상대적으로 변동이 있는 편으로 읽힙니다.
- "기본 바닥값(a)보다, 금리 민감도(b)가 국면 따라 조정될 여지가 더 크다"는 방향의 해석이 가능합니다."""
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

        # VERBATIM #9: 테스트 RMSE 추이 설명
        st.markdown(
            """## 용어 설명

- **test_rmse_pct**: 테스트 1개월 동안 "실제 TQQQ 가격 경로 vs 시뮬 가격 경로"가 얼마나 가까웠는지의 점수
  - 낮을수록 "잘 따라감"

## 해석 방법

- 체크리스트:
  1. 대부분 낮게 유지 → "꾸준히 잘 맞는 편"
  2. 스파이크(튀는 달) 존재 → 그 달은 충격/급변/모델 한계 구간일 수 있음

- 스파이크 달은 "버려야 할 달"이 아니라, **리스크 구간을 알려주는 힌트**입니다.

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준 전반적으로 낮은 구간이 많고, 일부 스파이크가 보입니다.
- 절차 자체는 유효하지만, 스파이크 달을 따로 찾아 원인 분석(변동성 급등 등)을 하면 운영 안정성이 올라갑니다."""
        )

    # 전체 결과 테이블
    with st.expander("전체 결과 테이블", expanded=False):
        st.dataframe(result_df, width="stretch")

        # VERBATIM #10: 전체 결과 테이블 설명
        st.markdown(
            f"""## 용어 설명

- 테이블의 한 행 = "한 테스트 월"의 기록
- 핵심 컬럼:
  - **train_start/train_end**: 학습 60개월 범위
  - **test_month**: 테스트 1개월
  - **a_best, b_best**: 그 달의 학습(60개월)에서 RMSE를 최소화한 값
  - **train_rmse_pct (학습 RMSE)**:
    - 과거 60개월(학습 구간) 데이터를 사용해 시뮬레이션했을 때의 추적 오차(RMSE)
    - "이미 본 데이터"로 계산하므로 대체로 낮게 나옴
    - 이 값이 높으면 모델이 학습 데이터조차 잘 설명하지 못한다는 뜻
  - **test_rmse_pct (테스트 RMSE)**:
    - 학습에 사용하지 않은 "다음 1개월" 데이터에서의 추적 오차(RMSE)
    - "처음 보는 데이터"로 계산하므로 학습 RMSE보다 보통 높게 나옴
    - 이 값이 낮을수록 모델이 미래에도 잘 통한다는 의미
  - **train vs test 차이가 중요한 이유**:
    - train RMSE는 낮은데 test RMSE만 높으면 → 과최적화 (학습 데이터에만 잘 맞춤)
    - 둘 다 비슷하면 → 모델이 안정적으로 일반화됨
  - **search_mode**: full grid인지 local refine인지
    - **full grid(전체 탐색)**
      - a와 b를 **넓은 범위**로 펼쳐 가능한 조합을 폭넓게 검사
      - 장점: 정답이 어디 있을지 몰라도 놓칠 확률이 낮음
      - 단점: 느림

    - **local refine(주변 미세조정)**
      - **이미 직전 달에 찾은 최적값(a_prev, b_prev)** 이 있으니, 그 주변(예: a는 ±{WALKFORWARD_LOCAL_REFINE_A_DELTA}, b는 ±{WALKFORWARD_LOCAL_REFINE_B_DELTA} 같은 좁은 범위)만 다시 탐색해서 "조금 더 좋은 값"을 찾는 방식
      - 장점: 빠르고, 파라미터가 매달 멀리 점프하는 걸 줄여 **운영이 안정적**
      - 단점: 국면이 크게 바뀌어 정답이 멀리 이동한 달이면 더 좋은 해를 놓칠 수 있음

## 해석 방법

초보자용 3단계 워크플로우:

1. **test_rmse_pct가 튄 달** (스파이크)을 먼저 찾기
2. 그 달의 행에서 **a_best/b_best가 갑자기 점프했는지**, **train-test 괴리가 큰지** 보기
3. 그 달이 **full grid였는지 / local refine였는지** 확인
   - local refine였는데 크게 틀리면 "정답이 멀리 이동했는데 주변만 찾았을 가능성" 같은 가설을 세우기 쉬워요.

## 현재 지표 해석 & 판단(결과)

- 2026.02.08 기준 전체 결과 테이블이 제공되므로, 차트에서 발견한 "이상 구간"을 **테이블로 역추적**할 수 있습니다.
- 운영 관점에서는 "스파이크 달"을 중심으로 테이블을 보는 게 가장 효율적입니다."""
        )


# ============================================================
# 모드별 렌더링 함수
# ============================================================


def _render_softplus_mode(monthly_df: pd.DataFrame) -> None:
    """Softplus 모델 모드의 전체 콘텐츠를 렌더링한다."""
    # A. 금리-오차 관계 분석
    _render_level_section(monthly_df)
    _render_delta_section(monthly_df)
    _render_cross_validation_section(monthly_df)

    st.divider()

    # B. Softplus 모델 튜닝 결과
    _render_softplus_tuning_section()

    st.divider()

    # C. 과최적화 진단
    _render_overfitting_diagnosis_section()

    st.divider()

    # D. 상세 분석 (모델 도출 과정)
    _render_detailed_analysis_section()


def _render_lookup_mode() -> None:
    """룩업테이블 모델 모드의 전체 콘텐츠를 렌더링한다."""
    st.header("룩업테이블 스프레드 모델")
    st.markdown("실현 스프레드를 역산하여 금리 구간별로 집계한 룩업테이블 모델의 검증 결과입니다.\n\n" "softplus처럼 함수 형태를 가정하지 않고, 관측된 스프레드를 직접 사용합니다.")

    # 1. 인샘플 튜닝 결과
    _render_lookup_tuning_section()

    st.divider()

    # 2. 워크포워드 검증 결과
    _render_lookup_walkforward_section()

    st.divider()

    # 3. 과적합 진단 (인샘플 vs 워크포워드)
    _render_lookup_overfitting_section()


def _render_lookup_tuning_section() -> None:
    """룩업테이블 인샘플 튜닝 결과를 렌더링한다."""
    st.subheader("인샘플 최적화 결과 (6가지 조합)")

    tuning_path = Path(LOOKUP_TUNING_CSV_PATH)
    if not tuning_path.exists():
        st.warning("인샘플 튜닝 결과가 없습니다.\n\n" "먼저 실행: `poetry run python scripts/tqqq/spread_lab/tune_lookup_params.py`")
        return

    tuning_df = pd.read_csv(tuning_path)

    if tuning_df.empty:
        st.info("튜닝 결과가 비어있습니다.")
        return

    # 최적 조합 표시
    best = tuning_df.iloc[0]
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="최적 구간 폭 (%)", value=f"{best['bin_width_pct']}")
    with col2:
        st.metric(label="최적 통계량", value=str(best["stat_func"]))
    with col3:
        st.metric(label="인샘플 RMSE (%)", value=f"{best['rmse_pct']:.4f}")

    # 전체 결과 테이블
    st.dataframe(tuning_df, width="stretch")

    # 바 차트
    fig = go.Figure()
    labels = [f"{row['bin_width_pct']}% / {row['stat_func']}" for _, row in tuning_df.iterrows()]
    fig.add_trace(
        go.Bar(
            x=labels,
            y=tuning_df["rmse_pct"],
            marker_color=["#2196F3" if i == 0 else "#90CAF9" for i in range(len(tuning_df))],
        )
    )
    fig.update_layout(
        title="조합별 인샘플 RMSE 비교",
        xaxis_title="구간 폭 / 통계량",
        yaxis_title="RMSE (%)",
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **룩업테이블 스프레드 모델**: softplus 같은 수식을 가정하지 않고, 실제 TQQQ 수익률에서 스프레드를 역산하여 금리 구간별로 집계한 비모수(non-parametric) 모델
- **실현 스프레드(realized spread)**: QQQ 수익률 × 3배와 실제 TQQQ 수익률의 차이에서 운용비용을 제거하여 역산한 자금조달 비용
- **구간 폭(bin_width_pct, %)**: 금리를 몇 %p 단위로 나눌지 결정하는 값 (예: 2%면 0~2%, 2~4%, ...)
- **통계량(stat_func)**: 구간 내 스프레드 데이터를 하나의 대표값으로 요약하는 방식
  - **mean**: 산술평균 (전체 분포 반영, 이상치에 민감)
  - **median**: 중앙값 (이상치에 강건)
- **n_bins**: 해당 조합에서 실제로 생성된 금리 구간 수 (구간 폭이 넓을수록 적어짐)
- **인샘플 RMSE(%)**: 전체 기간 데이터로 룩업테이블을 만들었을 때의 경로 추적 오차 (낮을수록 잘 재현)
- **6가지 조합**: 3가지 구간 폭(0.5%, 1%, 2%) × 2가지 통계량(mean, median) = 6가지

## 지표를 해석하는 방법

- **RMSE가 낮을수록** 전체 기간에서 실제 TQQQ 가격 경로를 잘 재현한 조합
- **구간 폭(bin_width_pct)** 선택의 트레이드오프:
  - 넓은 구간(2%): 빈당 데이터 포인트가 많아 안정적이지만, 금리 세분화 능력이 떨어짐
  - 좁은 구간(0.5%): 금리에 민감하게 반응하지만, 빈당 데이터가 적어 노이즈에 취약
- **통계량(stat_func)** 선택의 트레이드오프:
  - median: 이상치(급등락 시점)에 강건하지만, 극단적 비용 구간을 무시할 수 있음
  - mean: 전체 분포를 반영하지만, 이상치에 의해 끌림(skew)
- **n_bins가 적을수록** 모델이 단순하여 일반화 가능성이 높고, 많을수록 세밀하지만 과적합 위험 증가

## 현재 지표 해석 & 판단(결과)

- 2026.02.16 기준 최적 조합은 **구간 폭 2.0%, 통계량 median, RMSE 2.1128%**
- 넓은 구간(2%) + 중앙값(median)이 가장 낮은 RMSE → 이상치에 강건한 조합이 유리함을 시사
- median이 mean보다 일관되게 낮은 RMSE → 스프레드 분포에 이상치(급등락 시점)가 존재할 가능성
- 구간이 좁아질수록(0.5%, 1%) RMSE 증가 → 빈당 데이터 부족으로 노이즈가 커지는 현상
- n_bins가 3개(2% 구간)로, 모델이 매우 단순하여 과적합 위험은 낮은 대신 금리 세분화 능력은 제한적"""
    )


def _render_lookup_walkforward_section() -> None:
    """룩업테이블 워크포워드 검증 결과를 렌더링한다."""
    st.subheader("워크포워드 검증 결과")

    wf_path = Path(LOOKUP_WALKFORWARD_PATH)
    summary_path = Path(LOOKUP_WALKFORWARD_SUMMARY_PATH)

    if not wf_path.exists() or not summary_path.exists():
        st.warning(
            "워크포워드 결과가 없습니다.\n\n" "먼저 실행: `poetry run python scripts/tqqq/spread_lab/validate_walkforward_lookup.py`"
        )
        return

    result_df = pd.read_csv(wf_path)
    summary_df = pd.read_csv(summary_path)

    if result_df.empty or summary_df.empty:
        st.info("워크포워드 결과가 비어있습니다.")
        return

    summary = dict(zip(summary_df["metric"], summary_df["value"], strict=False))

    # 요약 지표
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        stitched = summary.get("stitched_rmse")
        if stitched is not None:
            st.metric(label="Stitched RMSE (%)", value=f"{float(stitched):.4f}")
        else:
            st.metric(label="Stitched RMSE (%)", value="N/A")
    with col2:
        st.metric(label="월별 RMSE 평균 (%)", value=f"{float(summary.get('test_rmse_mean', 0)):.4f}")
    with col3:
        st.metric(label="월별 RMSE 중앙값 (%)", value=f"{float(summary.get('test_rmse_median', 0)):.4f}")
    with col4:
        st.metric(label="테스트 월수", value=f"{int(float(summary.get('n_test_months', 0)))}")

    # 월별 테스트 RMSE 시계열
    if "test_month" in result_df.columns and "test_rmse_pct" in result_df.columns:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=result_df["test_month"],
                y=result_df["test_rmse_pct"],
                mode="lines+markers",
                name="월별 테스트 RMSE",
                marker={"size": 3},
            )
        )
        fig.update_layout(
            title="월별 테스트 RMSE 추이",
            xaxis_title="테스트 월",
            yaxis_title="RMSE (%)",
        )
        st.plotly_chart(fig, width="stretch")

    # 결과 테이블
    with st.expander("워크포워드 상세 결과", expanded=False):
        st.dataframe(result_df, width="stretch")

    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **워크포워드(rolling)**: 과거 60개월로 룩업테이블을 만든 뒤 → "다음 1개월"에서 성능(RMSE)을 보는 걸 매달 반복
- 워크포워드의 목적(한 줄): **"인샘플에서 선택한 구간 폭·통계량 조합이 미래에서도 잘 통하나?" + "그 과정이 얼마나 안정적이냐?"**
- **Stitched RMSE(%)**: 각 테스트 1개월의 시뮬레이션 경로를 이어 붙여 전체 기간으로 계산한 RMSE (인샘플 RMSE와 직접 비교 가능)
- **월별 RMSE 평균(%)**: 개별 테스트 월의 RMSE를 산술평균한 값
- **월별 RMSE 중앙값(%)**: 개별 테스트 월의 RMSE를 중앙값으로 본 값 (스파이크에 덜 민감)
- **테스트 월수**: 워크포워드가 수행된 총 월 수 (60개월 학습 후 시작)

### 상세 결과 테이블 컬럼

- **train_start / train_end**: 학습 60개월 범위 (이 기간의 QQQ/TQQQ 데이터로 룩업테이블 생성)
- **test_month**: 테스트 1개월 (학습에 사용하지 않은 "다음 달")
- **bin_width_pct, stat_func**: 인샘플 최적화에서 선택된 구간 폭과 통계량 (모든 행에서 동일)
- **test_rmse_pct**: 테스트 1개월의 경로 추적 오차 (낮을수록 "잘 따라감")
- **n_train_days, n_test_days**: 학습/테스트 기간의 거래일 수
- **n_bins**: 해당 학습 구간에서 생성된 룩업테이블 구간 수
- **ffr_pct_test**: 해당 테스트 월의 FFR 금리 수준(%)
- **spread_test**: 해당 테스트 월에 룩업테이블에서 조회된 스프레드 값

## 지표를 해석하는 방법

- **Stitched RMSE ≈ 인샘플 RMSE** → 모델이 미래에도 잘 통함 (과적합 없음)
- **Stitched RMSE >> 인샘플 RMSE** → 인샘플에서만 잘 맞고 미래에서 성능 하락 (과적합 의심)
- **월별 RMSE 중앙값 < 평균** → 일부 스파이크 달이 평균을 끌어올린 것 (대부분의 달은 양호)
- **시계열에서 스파이크** → 해당 구간은 시장 충격(급등락) 또는 모델 한계 구간
  - 스파이크 달은 "버려야 할 달"이 아니라, **리스크 구간을 알려주는 힌트**
- **n_bins가 시간에 따라 변하면** → 학습 데이터의 금리 분포가 달라지고 있다는 의미
- **ffr_pct_test**: 해당 월의 금리 환경을 보여주어, 고금리/저금리 시기별 성능 차이 분석에 활용
- **spread_test**: 룩업테이블에서 조회된 스프레드로, 값이 음수이면 빈 구간에서 fallback이 적용된 것

## 현재 지표 해석 & 판단(결과)

- 2026.02.16 기준 Stitched RMSE 2.2346%로, 인샘플 2.1128% 대비 격차가 0.12%p 수준으로 매우 작습니다.
- 월별 RMSE 중앙값(0.1020%)이 평균(0.1279%)보다 낮아, 일부 스파이크 달이 평균을 끌어올린 구조입니다.
- 2020년 부근 스파이크는 COVID-19 시기의 급등락으로 인한 모델 한계 구간으로 해석됩니다.
- 대부분의 달이 0.2% 이하로 안정적이어서, 워크포워드 절차 자체는 유효합니다.
- 테스트 월수 131개월로 충분한 검증 기간을 확보하고 있습니다."""
    )


def _render_lookup_overfitting_section() -> None:
    """룩업테이블 과적합 진단 (인샘플 vs 워크포워드)을 렌더링한다."""
    st.subheader("과적합 진단 (인샘플 vs 워크포워드)")

    # 인샘플 RMSE 로드
    tuning_path = Path(LOOKUP_TUNING_CSV_PATH)
    summary_path = Path(LOOKUP_WALKFORWARD_SUMMARY_PATH)

    if not tuning_path.exists() or not summary_path.exists():
        st.info("인샘플 및 워크포워드 결과가 모두 필요합니다.")
        return

    tuning_df = pd.read_csv(tuning_path)
    summary_df = pd.read_csv(summary_path)

    if tuning_df.empty or summary_df.empty:
        st.info("결과가 비어있습니다.")
        return

    insample_rmse = float(tuning_df.iloc[0]["rmse_pct"])
    summary = dict(zip(summary_df["metric"], summary_df["value"], strict=False))
    stitched_rmse = summary.get("stitched_rmse")

    if stitched_rmse is None:
        st.info("stitched RMSE를 산출할 수 없습니다.")
        return

    stitched_rmse = float(stitched_rmse)
    gap = stitched_rmse - insample_rmse

    # RMSE 비교
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="인샘플 RMSE (%)", value=f"{insample_rmse:.4f}")
    with col2:
        st.metric(label="워크포워드 Stitched RMSE (%)", value=f"{stitched_rmse:.4f}")
    with col3:
        st.metric(label="격차 (%p)", value=f"{gap:.4f}")

    # 판정
    if gap < 0.5:
        st.success(f"인샘플-아웃오브샘플 격차: **{gap:.4f}%p** (< 0.5%p)\n\n" f"**판단: 과적합 위험 낮음** - 룩업테이블 파라미터가 잘 일반화되고 있습니다.")
    elif gap < 1.5:
        st.warning(f"인샘플-아웃오브샘플 격차: **{gap:.4f}%p** (0.5~1.5%p)\n\n" f"**판단: 약한 과적합** - 실용적 범위이지만 모니터링이 필요합니다.")
    else:
        st.error(f"인샘플-아웃오브샘플 격차: **{gap:.4f}%p** (> 1.5%p)\n\n" f"**판단: 과적합 의심** - 다른 접근 검토가 필요합니다.")

    # 비교 바 차트
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=["인샘플", "워크포워드 (Stitched)"],
            y=[insample_rmse, stitched_rmse],
            marker_color=["#4CAF50", "#FF5722"],
            text=[f"{insample_rmse:.4f}%", f"{stitched_rmse:.4f}%"],
            textposition="auto",
        )
    )
    fig.update_layout(
        title="인샘플 vs 워크포워드 RMSE 비교",
        yaxis_title="RMSE (%)",
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown(
        """## 지표에 사용하는 용어에 대한 설명

- **인샘플 RMSE(%)**: 전체 기간 데이터로 최적 조합(구간 폭·통계량)을 선택했을 때의 경로 추적 오차. "이미 본 데이터"를 사용하므로 대체로 낮게 나옴
- **워크포워드 Stitched RMSE(%)**: 매달 과거 60개월로만 학습하고 미래 1개월을 이어붙인 RMSE. "처음 보는 데이터"로 계산하므로 인샘플보다 보통 높게 나옴
- **격차(%p)**: Stitched RMSE - 인샘플 RMSE. 과적합 정도를 수치화한 값
- **과적합(overfitting)**: 학습 데이터에만 잘 맞고 미래 데이터에서 성능이 떨어지는 현상. 격차가 클수록 과적합 의심

## 지표를 해석하는 방법

- **격차 < 0.5%p**: 과적합 위험 낮음 → 인샘플에서 선택한 조합이 미래에도 잘 통함
- **격차 0.5~1.5%p**: 약한 과적합 → 실용적 범위이지만 정기적 모니터링 필요
- **격차 > 1.5%p**: 과적합 의심 → 다른 접근(더 넓은 구간 폭, 더 단순한 모델) 검토 필요

- 주의: 격차가 작아도 **절대 RMSE 수준**이 높으면 모델 자체의 설명력이 부족한 것
  - 격차가 작다 = "과적합은 없다" (일반화 잘 됨)
  - 격차가 작다 ≠ "좋은 모델이다" (절대 정확도는 별개 문제)
- softplus 모델과 절대 RMSE를 비교하여 **어떤 모델이 실제 TQQQ를 더 잘 재현하는지** 판단 가능

## 현재 지표 해석 & 판단(결과)

- 2026.02.16 기준 격차 **0.1218%p** (< 0.5%p) → **과적합 위험 낮음**. 룩업테이블 조합(2% / median)이 미래에서도 안정적으로 일반화되고 있습니다.
- 다만 절대 RMSE 수준(인샘플 2.1128%, Stitched 2.2346%)은 softplus 모델(~1.05%)보다 약 2배 높습니다.
- 이는 룩업테이블 모델이 비모수(non-parametric) 기준선(baseline)으로서, **"수식 없이 관측값만으로 어디까지 설명 가능한가"**를 보여주는 역할을 합니다.
- softplus 모델의 RMSE가 룩업테이블보다 낮으면서 과적합도 적다면, **softplus의 함수 형태 가정이 유효하다는 증거**로 해석할 수 있습니다."""
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
            st.divider()
            model_mode = st.radio(
                "스프레드 모델 선택",
                ("Softplus 모델", "룩업테이블 모델"),
            )

        # 타이틀, 히스토리, 읽기 가이드
        _render_intro()

        # 데이터 로딩 및 월별 집계
        st.header("데이터 로딩 및 월별 집계")

        try:
            # 1. 월별 데이터 빌드 (캐시됨)
            monthly_df = build_artifacts(
                str(TQQQ_DAILY_COMPARISON_PATH),
                str(FFR_DATA_PATH),
            )
            st.success(f"월별 집계 완료: {len(monthly_df):,}개월")

            # 2. 파생 컬럼 추가 (lag 1, 2) - analysis_helpers 함수 사용
            monthly_df = add_rate_change_lags(monthly_df)

            # 3. 요약 통계 표시
            _render_dataset_metrics(monthly_df)

        except ValueError as e:
            st.error(f"월별 집계 실패 (fail-fast):\n\n{str(e)}\n\n힌트: 데이터 기간/형식 확인")
            st.stop()
        except Exception as e:
            st.error(f"예상치 못한 오류:\n\n{str(e)}")
            st.stop()

        st.divider()

        if model_mode == "Softplus 모델":
            _render_softplus_mode(monthly_df)
        else:
            _render_lookup_mode()

        # 푸터
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - TQQQ 금리-오차 관계 분석 (연구용)")

    except Exception as e:
        st.error("애플리케이션 실행 중 예상치 못한 오류 발생:")
        st.exception(e)
        st.stop()


if __name__ == "__main__":
    main()
