"""TQQQ 금리-오차 관계 분석 연구용 앱

금리 환경과 시뮬레이션 오차의 관계를 시각화하여 spread 조정 전략 수립을 지원한다.

실행 명령어:
    poetry run streamlit run scripts/tqqq/streamlit_rate_spread_lab.py

주요 기능:
- Level 탭: 금리 수준 vs 월말 누적 signed 오차
- Delta 탭: 금리 변화 vs 오차 변화, Lag 효과, Rolling 상관
- 교차검증: de_m vs sum_daily_m 차이 분석
- Softplus 동적 Spread 튜닝: 금리 수준에 따른 동적 spread 파라미터 최적화

CSV 저장:
- 서버 최초 기동 시 1회만 자동 저장 (st.cache_resource 사용)
- 브라우저 새로고침/새 세션에서는 재저장하지 않음
- Lag 선택 등 위젯 상호작용 시 재생성 방지

Fail-fast 정책:
- ValueError 발생 시 st.error() + st.stop()으로 즉시 중단
- 잘못된 차트/수치 표시 방지

사용자 경험:
- 모든 화면 텍스트 한글화 ("한글 (영문)" 형식)
- 명확한 레이블 및 설명 제공
"""

import threading
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.common_constants import DISPLAY_DATE, QQQ_DATA_PATH
from qbt.tqqq.analysis_helpers import (
    add_rate_change_lags,
    aggregate_monthly,
    build_model_dataset,
    calculate_daily_signed_log_diff,
    save_model_csv,
    save_monthly_features,
    save_summary_statistics,
    save_walkforward_results,
    save_walkforward_summary,
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
    DEFAULT_ROLLING_WINDOW,
    DEFAULT_TOP_N_CROSS_VALIDATION,
    DEFAULT_TRAIN_WINDOW_MONTHS,
    DISPLAY_ERROR_END_OF_MONTH_PCT,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    SOFTPLUS_GRID_STAGE1_A_RANGE,
    SOFTPLUS_GRID_STAGE1_A_STEP,
    SOFTPLUS_GRID_STAGE1_B_RANGE,
    SOFTPLUS_GRID_STAGE1_B_STEP,
    SOFTPLUS_GRID_STAGE2_A_DELTA,
    SOFTPLUS_GRID_STAGE2_A_STEP,
    SOFTPLUS_GRID_STAGE2_B_DELTA,
    SOFTPLUS_GRID_STAGE2_B_STEP,
    TQQQ_DAILY_COMPARISON_PATH,
    TQQQ_DATA_PATH,
    TQQQ_RATE_SPREAD_LAB_MODEL_PATH,
    TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH,
    TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH,
    TQQQ_WALKFORWARD_PATH,
    TQQQ_WALKFORWARD_SUMMARY_PATH,
    WALKFORWARD_LOCAL_REFINE_A_DELTA,
    WALKFORWARD_LOCAL_REFINE_A_STEP,
    WALKFORWARD_LOCAL_REFINE_B_DELTA,
    WALKFORWARD_LOCAL_REFINE_B_STEP,
)
from qbt.tqqq.data_loader import (
    load_comparison_data,
    load_expense_ratio_data,
    load_ffr_data,
)
from qbt.tqqq.simulation import find_optimal_softplus_params, run_walkforward_validation
from qbt.tqqq.visualization import create_delta_chart, create_level_chart
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata

# ============================================================
# Streamlit 앱 전용 상수 (이 파일에서만 사용)
# ============================================================

# --- 기본값 파라미터 ---
DEFAULT_HISTOGRAM_BINS = 30  # 히스토그램 기본 bins
DEFAULT_LAG_OPTIONS = [0, 1, 2]  # Delta 분석 lag 선택지 (개월)
DEFAULT_STREAMLIT_COLUMNS = 3  # 요약 통계 표시용 컬럼 개수

# --- 메타데이터 타입 ---
KEY_META_TYPE_RATE_SPREAD_LAB = "tqqq_rate_spread_lab"
KEY_META_TYPE_SOFTPLUS_TUNING = "tqqq_softplus_tuning"
KEY_META_TYPE_WALKFORWARD = "tqqq_walkforward"

# --- 세션 상태 키 (워크포워드) ---
KEY_SESSION_WALKFORWARD_RESULT = "walkforward_result"
KEY_SESSION_WALKFORWARD_RUNNING = "walkforward_running"

# --- Softplus 튜닝 모드 관련 ---
MODE_FIXED_SPREAD = "고정 Spread (기본)"
MODE_SOFTPLUS_DYNAMIC = "Softplus 동적 Spread"

# --- 세션 상태 키 ---
KEY_SESSION_TUNING_RESULT = "softplus_tuning_result"
KEY_SESSION_TUNING_RUNNING = "softplus_tuning_running"

# --- 출력용 한글 레이블 ---
DISPLAY_CHART_DIFF_DISTRIBUTION = "차이 분포"  # 히스토그램 차트명
DISPLAY_AXIS_DIFF_PCT = "차이 (%)"  # X축 레이블
DISPLAY_AXIS_FREQUENCY = "빈도"  # Y축 레이블
DISPLAY_DELTA_MONTHLY_PCT = "월간 변화 (%)"  # Delta 차트 y축

# ============================================================
# 저장 가드 및 데이터 빌드 (캐시)
# ============================================================


@st.cache_resource
def _save_guard():
    """
    서버 런 동안 유지되는 저장 가드 객체를 반환한다.

    반환 구조:
        - saved: bool (저장 완료 여부, 초기값 False)
        - lock: threading.Lock (동시 접근 방지)

    Returns:
        저장 가드 딕셔너리 (서버 런 동안 단일 인스턴스 유지)
    """
    return {"saved": False, "lock": threading.Lock()}


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
    """타이틀 및 설명을 렌더링한다."""
    st.title("TQQQ 금리-오차 관계 분석")
    st.markdown(
        """
        금리 환경과 시뮬레이션 오차의 관계를 시각화하여 **스프레드 조정 전략 (Spread Adjustment Strategy)** 수립을 지원합니다.

        **화면 구성**:
        - **핵심**: 금리 수준 vs 월말 누적 오차 (기본 표시)
        - **고급**: 델타 분석 (Delta Analysis), 교차검증 (Cross Validation) (클릭하여 열기)
        """
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


def _render_level_section(monthly_df: pd.DataFrame):
    """Level 분석 섹션을 렌더링한다."""
    st.header("금리 수준 vs 월말 누적 오차 (핵심)")

    st.markdown(
        """
        **용어 설명**:
        - **금리 수준 (Rate Level, rate_pct)**: 연방기금금리 (Federal Funds Rate, FFR, %)
        - **월말 누적 오차 (End-of-Month Error, e_m)**: 해당 월 마지막 거래일의 시뮬레이션 오차 (%)

        **부호 해석**:
        - **오차 (+)**: 시뮬레이션이 실제보다 **과대** 평가
        - **오차 (-)**: 시뮬레이션이 실제보다 **과소** 평가

        **해석 예시**:
        - 금리가 높을수록 월말 누적 오차 (e_m)가 +로 커지면 -> 고금리 구간에서 시뮬레이션 과대 평가 -> 비용 (조달비용) 가정이 낮았을 가능성
        - 반대로 -로 커지면 -> 비용 가정이 높았을 가능성
        - **주의**: 상관관계가 인과관계를 의미하지 않음

        ---
        """
    )

    try:
        level_fig = create_level_chart(monthly_df, COL_E_M, DISPLAY_ERROR_END_OF_MONTH_PCT)
        st.plotly_chart(level_fig, width="stretch")
    except Exception as e:
        st.error(f"Level 차트 생성 실패:\n\n{str(e)}")

    st.divider()


def _render_delta_section(monthly_df: pd.DataFrame):
    """Delta 분석 섹션을 렌더링한다."""
    with st.expander("고급 분석: 델타 (Delta - 금리 변화 vs 오차 변화)", expanded=False):
        st.markdown(
            """
            **목적**: 금리 변화와 오차 변화의 관계 및 시차 효과 (Lag Effect) 확인

            **시차 옵션 (Lag Options)**:
            - 시차 0 (Lag 0): 동월 금리 변화 vs 당월 오차 변화
            - 시차 1 (Lag 1): 전월 금리 변화 vs 당월 오차 변화 (1개월 시차)
            - 시차 2 (Lag 2): 2개월 전 금리 변화 vs 당월 오차 변화 (2개월 시차)
            """
        )

        y_col_delta = COL_DE_M
        y_label_delta = DISPLAY_DELTA_MONTHLY_PCT

        lag = st.selectbox("시차 (Lag, 개월):", options=DEFAULT_LAG_OPTIONS, index=0)

        try:
            delta_fig, valid_df = create_delta_chart(monthly_df, y_col_delta, y_label_delta, lag)
            st.plotly_chart(delta_fig, width="stretch")

            st.info(
                f"""
                **샘플 수 (Sample Size)**: {len(valid_df)}개월

                **상관 해석 주의점 (Correlation Interpretation)**:
                - 상관이 높다고 인과관계를 의미하지 않음
                - 다른 요인 (변동성, 레버리지 리밸런싱 등)도 영향 가능
                - 시차 효과 (Lag Effect)는 금리 정책 시차를 반영할 수 있음
                """
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

    st.markdown(
        """
        **목적**: 두 가지 방법으로 계산한 월간 오차 변화가 일치하는지 검증

        - `de_m`: 월말 누적 signed의 월간 변화 (Difference, diff)
        - `sum_daily_m`: 일일 증분 signed의 월합 (Sum of Daily, sum)

        **기대**: 거의 같아야 함 (완전 동일 X)

        **차이 원인 (Difference Causes)**:
        1. 일일수익률 반올림 (CSV 저장 시 소수점 자릿수 제한)
        2. 거래일 결측 (일부 날짜 누락 가능성)
        3. 누적수익률 계산 방식 차이 (실제 데이터 vs 시뮬레이션 계산 경로)
        """
    )

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


# ============================================================
# CSV 저장 함수
# ============================================================


def _save_outputs_once(monthly_df: pd.DataFrame):
    """
    CSV 파일들을 1회만 저장한다 (저장 가드 사용).

    저장 대상:
        1. 월별 피처 CSV (한글 헤더)
        2. 요약 통계 CSV (한글 헤더)
        3. 모델용 CSV (영문 헤더, schema_version 포함)
        4. meta.json 실행 이력

    Args:
        monthly_df: 월별 데이터 (lag 컬럼 포함)

    Returns:
        저장 성공 여부
    """
    guard = _save_guard()
    with guard["lock"]:
        if guard["saved"]:
            return True

        try:
            # 1. 월별 피처 CSV 저장
            save_monthly_features(monthly_df, TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH)

            # 2. 요약 통계 CSV 저장
            save_summary_statistics(monthly_df, TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH)

            # 3. 모델용 CSV 저장
            # rolling 데이터가 window 미만인 경우 예외 발생할 수 있음
            try:
                model_df = build_model_dataset(monthly_df, window=DEFAULT_ROLLING_WINDOW)
                save_model_csv(model_df, TQQQ_RATE_SPREAD_LAB_MODEL_PATH)
                model_saved = True
            except ValueError as e:
                st.warning(f"모델용 CSV 저장 실패 (데이터 부족):\n\n{str(e)}")
                model_saved = False

            # 4. meta.json 실행 이력 저장
            output_files = {
                "monthly_csv": str(TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH),
                "summary_csv": str(TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH),
            }
            if model_saved:
                output_files["model_csv"] = str(TQQQ_RATE_SPREAD_LAB_MODEL_PATH)

            metadata = {
                "input_files": {
                    "daily_comparison": str(TQQQ_DAILY_COMPARISON_PATH),
                    "ffr_data": str(FFR_DATA_PATH),
                },
                "output_files": output_files,
                "analysis_period": {
                    "month_min": str(monthly_df[COL_MONTH].min()),
                    "month_max": str(monthly_df[COL_MONTH].max()),
                    "total_months": len(monthly_df),
                },
            }
            save_metadata(KEY_META_TYPE_RATE_SPREAD_LAB, metadata)

            guard["saved"] = True

            # 성공 메시지
            saved_files = [
                TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH.name,
                TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH.name,
            ]
            if model_saved:
                saved_files.append(TQQQ_RATE_SPREAD_LAB_MODEL_PATH.name)
            st.success("결과 CSV 저장 완료 (서버 런 1회):\n- " + "\n- ".join(saved_files))
            return True

        except Exception as e:
            st.warning(f"CSV 저장 실패 (계속 진행):\n\n{str(e)}")
            return False


# ============================================================
# Softplus 튜닝 관련 함수
# ============================================================


@st.cache_data(show_spinner=False)
def _load_tuning_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Softplus 튜닝에 필요한 데이터를 로드한다.

    캐시되므로 서버 런 동안 1회만 로드된다.

    Returns:
        (qqq_df, tqqq_df, ffr_df, expense_df) 튜플
    """
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)
    return qqq_df, tqqq_df, ffr_df, expense_df


def _run_softplus_tuning() -> dict | None:
    """
    Softplus 파라미터 2-stage grid search 튜닝을 실행한다.

    진행 상황을 progress bar로 표시하며, 완료 후 결과를 세션 상태에 저장한다.

    Returns:
        튜닝 결과 딕셔너리 또는 None (실패 시)
    """
    try:
        # 데이터 로드 (캐시됨)
        with st.spinner("데이터 로딩 중..."):
            qqq_df, tqqq_df, ffr_df, expense_df = _load_tuning_data()

        # 튜닝 실행 (시간이 오래 걸릴 수 있음)
        progress_bar = st.progress(0, text="Stage 1: 조대 그리드 탐색 시작...")

        # Stage 1 조합 수 계산 (사전 정보 표시용)
        a_count_s1 = (
            int((SOFTPLUS_GRID_STAGE1_A_RANGE[1] - SOFTPLUS_GRID_STAGE1_A_RANGE[0]) / SOFTPLUS_GRID_STAGE1_A_STEP) + 1
        )
        b_count_s1 = (
            int((SOFTPLUS_GRID_STAGE1_B_RANGE[1] - SOFTPLUS_GRID_STAGE1_B_RANGE[0]) / SOFTPLUS_GRID_STAGE1_B_STEP) + 1
        )
        total_s1 = a_count_s1 * b_count_s1

        # Stage 2 조합 수 계산
        a_count_s2 = int(2 * SOFTPLUS_GRID_STAGE2_A_DELTA / SOFTPLUS_GRID_STAGE2_A_STEP) + 1
        b_count_s2 = int(2 * SOFTPLUS_GRID_STAGE2_B_DELTA / SOFTPLUS_GRID_STAGE2_B_STEP) + 1
        total_s2 = a_count_s2 * b_count_s2

        progress_bar.progress(10, text=f"Stage 1: {total_s1}개 조합 탐색 중... (약 1-2분 소요)")

        # 튜닝 실행
        a_best, b_best, best_rmse, all_candidates = find_optimal_softplus_params(
            underlying_df=qqq_df,
            actual_leveraged_df=tqqq_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
        )

        progress_bar.progress(100, text="튜닝 완료!")

        # 결과 저장
        result = {
            "a_best": a_best,
            "b_best": b_best,
            "best_rmse": best_rmse,
            "all_candidates": all_candidates,
            "stage1_count": total_s1,
            "stage2_count": total_s2,
        }

        # meta.json에 기록
        _save_softplus_tuning_metadata(result)

        return result

    except Exception as e:
        st.error(f"튜닝 실행 실패:\n\n{str(e)}")
        return None


def _save_softplus_tuning_metadata(result: dict) -> None:
    """
    Softplus 튜닝 결과를 meta.json에 기록한다.

    Args:
        result: 튜닝 결과 딕셔너리
    """
    metadata = {
        "funding_spread_mode": "softplus_ffr_monthly",
        "softplus_a": result["a_best"],
        "softplus_b": result["b_best"],
        "ffr_scale": "pct",
        "objective": "cumul_multiple_log_diff_rmse_pct",
        "best_rmse_pct": result["best_rmse"],
        "grid_settings": {
            "stage1": {
                "a_range": list(SOFTPLUS_GRID_STAGE1_A_RANGE),
                "a_step": SOFTPLUS_GRID_STAGE1_A_STEP,
                "b_range": list(SOFTPLUS_GRID_STAGE1_B_RANGE),
                "b_step": SOFTPLUS_GRID_STAGE1_B_STEP,
                "combinations": result["stage1_count"],
            },
            "stage2": {
                "a_delta": SOFTPLUS_GRID_STAGE2_A_DELTA,
                "a_step": SOFTPLUS_GRID_STAGE2_A_STEP,
                "b_delta": SOFTPLUS_GRID_STAGE2_B_DELTA,
                "b_step": SOFTPLUS_GRID_STAGE2_B_STEP,
                "combinations": result["stage2_count"],
            },
        },
        "input_files": {
            "qqq_data": str(QQQ_DATA_PATH),
            "tqqq_data": str(TQQQ_DATA_PATH),
            "ffr_data": str(FFR_DATA_PATH),
            "expense_data": str(EXPENSE_RATIO_DATA_PATH),
        },
        "output_files": {
            "monthly_csv": str(TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH),
            "summary_csv": str(TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH),
            "model_csv": str(TQQQ_RATE_SPREAD_LAB_MODEL_PATH),
        },
    }
    save_metadata(KEY_META_TYPE_SOFTPLUS_TUNING, metadata)


def _render_softplus_section() -> None:
    """Softplus 동적 Spread 튜닝 섹션을 렌더링한다."""
    st.header("Softplus 동적 Spread 파라미터 튜닝")

    st.markdown(
        """
        **목적**: 금리 수준에 따라 funding spread를 동적으로 조정하는 softplus 모델의 최적 파라미터 (a, b)를 탐색합니다.

        **수식**: `spread = softplus(a + b * ffr_pct)`

        - `ffr_pct`: 연방기금금리 (%, 예: 5.0 = 5%)
        - `a`: 절편 파라미터 (음수일 때 저금리 구간 spread 감소)
        - `b`: 기울기 파라미터 (양수일 때 고금리 구간 spread 증가)
        - `softplus(x)`: log(1 + exp(x)), 항상 양수 반환

        **탐색 방법**: 2-Stage Grid Search (조대 탐색 -> 정밀 탐색)

        **목적함수**: `cumul_multiple_log_diff_rmse_pct` 최소화 (추적 오차 RMSE)

        ---
        """
    )

    # Grid search 파라미터 표시
    with st.expander("Grid Search 파라미터 (참고)", expanded=False):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Stage 1 (조대 그리드)**")
            st.write(
                f"- a: [{SOFTPLUS_GRID_STAGE1_A_RANGE[0]}, {SOFTPLUS_GRID_STAGE1_A_RANGE[1]}], step={SOFTPLUS_GRID_STAGE1_A_STEP}"
            )
            st.write(
                f"- b: [{SOFTPLUS_GRID_STAGE1_B_RANGE[0]}, {SOFTPLUS_GRID_STAGE1_B_RANGE[1]}], step={SOFTPLUS_GRID_STAGE1_B_STEP}"
            )

        with col2:
            st.markdown("**Stage 2 (정밀 그리드)**")
            st.write(
                f"- a: [a* - {SOFTPLUS_GRID_STAGE2_A_DELTA}, a* + {SOFTPLUS_GRID_STAGE2_A_DELTA}], step={SOFTPLUS_GRID_STAGE2_A_STEP}"
            )
            st.write(
                f"- b: [b* - {SOFTPLUS_GRID_STAGE2_B_DELTA}, b* + {SOFTPLUS_GRID_STAGE2_B_DELTA}], step={SOFTPLUS_GRID_STAGE2_B_STEP}"
            )

    st.divider()

    # 세션 상태에서 이전 결과 확인
    if KEY_SESSION_TUNING_RESULT in st.session_state:
        _display_tuning_result(st.session_state[KEY_SESSION_TUNING_RESULT])
        st.divider()

    # 튜닝 실행 버튼
    if st.button("(a, b) 글로벌 튜닝 실행", type="primary", use_container_width=True):
        result = _run_softplus_tuning()
        if result is not None:
            st.session_state[KEY_SESSION_TUNING_RESULT] = result
            st.rerun()

    # 워크포워드 검증 섹션 (항상 표시)
    st.divider()
    _render_walkforward_section()


def _display_tuning_result(result: dict) -> None:
    """
    튜닝 결과를 표시한다.

    Args:
        result: 튜닝 결과 딕셔너리
    """
    st.subheader("튜닝 결과")

    # 핵심 결과 표시
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(label="최적 a (절편)", value=f"{result['a_best']:.4f}")

    with col2:
        st.metric(label="최적 b (기울기)", value=f"{result['b_best']:.4f}")

    with col3:
        st.metric(label="최적 RMSE (%)", value=f"{result['best_rmse']:.4f}")

    st.success(
        f"최적 파라미터: a = {result['a_best']:.4f}, b = {result['b_best']:.4f}\n\n" f"추적 오차 RMSE: {result['best_rmse']:.4f}%"
    )

    # 상위 결과 테이블
    with st.expander("상위 10개 후보 결과", expanded=True):
        # all_candidates에서 상위 10개 추출
        candidates = result["all_candidates"]
        candidates_sorted = sorted(candidates, key=lambda x: x[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE])
        top_10 = candidates_sorted[:10]

        # DataFrame으로 변환
        top_df = pd.DataFrame(
            [
                {
                    "a": c["a"],
                    "b": c["b"],
                    "RMSE (%)": c[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE],
                }
                for c in top_10
            ]
        )
        top_df.index = pd.Index(range(1, len(top_df) + 1), name="순위")

        st.dataframe(top_df, use_container_width=True)

    # 메타 정보
    st.info(
        f"탐색 조합 수: Stage 1 = {result['stage1_count']}개, Stage 2 = {result['stage2_count']}개\n\n"
        f"결과가 meta.json에 저장되었습니다."
    )


# ============================================================
# 워크포워드 검증 관련 함수
# ============================================================


def _run_walkforward_validation() -> dict | None:
    """
    워크포워드 검증을 실행한다.

    60개월 Train, 1개월 Test 워크포워드 검증을 수행하고, CSV 파일을 저장한다.

    Returns:
        워크포워드 결과 딕셔너리 또는 None (실패 시)
    """
    try:
        # 데이터 로드 (캐시됨)
        with st.spinner("데이터 로딩 중..."):
            qqq_df, tqqq_df, ffr_df, expense_df = _load_tuning_data()

        # 워크포워드 실행 (시간이 오래 걸릴 수 있음)
        progress_bar = st.progress(0, text="워크포워드 검증 시작 중...")

        # 예상 테스트 월 수 계산 (사전 정보 표시용)
        # 전체 기간에서 train 기간을 뺀 월 수
        progress_bar.progress(5, text="워크포워드 검증 실행 중... (60개월 학습, 1개월 테스트)")

        # 워크포워드 실행
        result_df, summary = run_walkforward_validation(
            underlying_df=qqq_df,
            actual_df=tqqq_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            train_window_months=DEFAULT_TRAIN_WINDOW_MONTHS,
        )

        progress_bar.progress(90, text="CSV 파일 저장 중...")

        # CSV 저장
        save_walkforward_results(result_df, TQQQ_WALKFORWARD_PATH)
        save_walkforward_summary(summary, TQQQ_WALKFORWARD_SUMMARY_PATH)

        progress_bar.progress(100, text="워크포워드 검증 완료!")

        # 결과 저장
        result = {
            "result_df": result_df,
            "summary": summary,
        }

        # meta.json에 기록
        _save_walkforward_metadata(result)

        return result

    except Exception as e:
        st.error(f"워크포워드 검증 실행 실패:\n\n{str(e)}")
        return None


def _save_walkforward_metadata(result: dict) -> None:
    """
    워크포워드 검증 결과를 meta.json에 기록한다.

    Args:
        result: 워크포워드 결과 딕셔너리
    """
    summary = result["summary"]
    metadata = {
        "funding_spread_mode": "softplus_ffr_monthly",
        "walkforward_settings": {
            "train_window_months": DEFAULT_TRAIN_WINDOW_MONTHS,
            "test_step_months": 1,
            "test_month_ffr_usage": "same_month",
        },
        "tuning_policy": {
            "first_window": "full_grid_2stage",
            "subsequent_windows": "local_refine",
            "local_refine_a_delta": WALKFORWARD_LOCAL_REFINE_A_DELTA,
            "local_refine_a_step": WALKFORWARD_LOCAL_REFINE_A_STEP,
            "local_refine_b_delta": WALKFORWARD_LOCAL_REFINE_B_DELTA,
            "local_refine_b_step": WALKFORWARD_LOCAL_REFINE_B_STEP,
        },
        "summary": {
            "test_rmse_mean": summary["test_rmse_mean"],
            "test_rmse_median": summary["test_rmse_median"],
            "test_rmse_std": summary["test_rmse_std"],
            "a_mean": summary["a_mean"],
            "a_std": summary["a_std"],
            "b_mean": summary["b_mean"],
            "b_std": summary["b_std"],
            "n_test_months": summary["n_test_months"],
        },
        "input_files": {
            "qqq_data": str(QQQ_DATA_PATH),
            "tqqq_data": str(TQQQ_DATA_PATH),
            "ffr_data": str(FFR_DATA_PATH),
            "expense_data": str(EXPENSE_RATIO_DATA_PATH),
        },
        "output_files": {
            "walkforward_csv": str(TQQQ_WALKFORWARD_PATH),
            "walkforward_summary_csv": str(TQQQ_WALKFORWARD_SUMMARY_PATH),
        },
    }
    save_metadata(KEY_META_TYPE_WALKFORWARD, metadata)


def _display_walkforward_result(result: dict) -> None:
    """
    워크포워드 검증 결과를 표시한다.

    Args:
        result: 워크포워드 결과 딕셔너리
    """
    st.subheader("워크포워드 검증 결과")

    result_df = result["result_df"]
    summary = result["summary"]

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
            st.write(f"- 테스트 월 수: {summary['n_test_months']}개월")

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
        st.plotly_chart(fig_a, use_container_width=True)

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
        st.plotly_chart(fig_b, use_container_width=True)

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
        st.plotly_chart(fig_rmse, use_container_width=True)

    # 전체 결과 테이블
    with st.expander("전체 결과 테이블", expanded=False):
        st.dataframe(result_df, use_container_width=True)

    # 메타 정보
    st.info(
        f"워크포워드 검증 완료: {summary['n_test_months']}개월 테스트\n\n"
        f"결과가 다음 파일에 저장되었습니다:\n"
        f"- {TQQQ_WALKFORWARD_PATH}\n"
        f"- {TQQQ_WALKFORWARD_SUMMARY_PATH}"
    )


def _render_walkforward_section() -> None:
    """워크포워드 검증 섹션을 렌더링한다."""
    st.header("워크포워드 검증 (파라미터 안정성)")

    st.markdown(
        f"""
        **목적**: 글로벌 최적 (a, b) 파라미터가 미래 데이터에도 안정적으로 작동하는지 검증합니다.

        **방법**: 워크포워드 (Rolling Window) 검증
        - 학습 기간: {DEFAULT_TRAIN_WINDOW_MONTHS}개월 (5년)
        - 테스트 기간: 1개월
        - 첫 구간: 2-stage grid search (글로벌 탐색)
        - 이후 구간: local refine (직전 월 최적값 주변 탐색)

        **Local Refine 범위**:
        - a: [a_prev - {WALKFORWARD_LOCAL_REFINE_A_DELTA}, a_prev + {WALKFORWARD_LOCAL_REFINE_A_DELTA}], step = {WALKFORWARD_LOCAL_REFINE_A_STEP}
        - b: [b_prev - {WALKFORWARD_LOCAL_REFINE_B_DELTA}, b_prev + {WALKFORWARD_LOCAL_REFINE_B_DELTA}], step = {WALKFORWARD_LOCAL_REFINE_B_STEP}

        **주의**: 워크포워드 검증은 시간이 오래 걸릴 수 있습니다 (약 30-60분).

        ---
        """
    )

    # 세션 상태에서 이전 결과 확인
    if KEY_SESSION_WALKFORWARD_RESULT in st.session_state:
        _display_walkforward_result(st.session_state[KEY_SESSION_WALKFORWARD_RESULT])
        st.divider()

    # 워크포워드 실행 버튼
    if st.button("워크포워드 검증 실행", type="secondary", use_container_width=True):
        result = _run_walkforward_validation()
        if result is not None:
            st.session_state[KEY_SESSION_WALKFORWARD_RESULT] = result
            st.rerun()


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

        # 사이드바 - 모드 선택
        with st.sidebar:
            st.header("분석 모드 선택")
            analysis_mode = st.radio(
                "분석 모드를 선택하세요:",
                options=[MODE_FIXED_SPREAD, MODE_SOFTPLUS_DYNAMIC],
                index=0,
                help="고정 Spread: 기존 분석 (금리-오차 관계 시각화)\n\nSoftplus 동적: 최적 (a, b) 파라미터 탐색",
            )
            st.divider()
            st.caption("QBT (Quant BackTest)")

        # 타이틀 및 설명
        _render_intro()

        # 모드에 따른 분기
        if analysis_mode == MODE_SOFTPLUS_DYNAMIC:
            # Softplus 동적 Spread 모드
            _render_softplus_section()
        else:
            # 고정 Spread 모드 (기본)
            # 데이터 로드 및 월별 집계
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

                # 3. CSV 자동 저장 (서버 런 동안 1회만)
                _save_outputs_once(monthly_df)

                # 4. 요약 통계 표시
                _render_dataset_metrics(monthly_df)

            except ValueError as e:
                st.error(f"월별 집계 실패 (fail-fast):\n\n{str(e)}\n\n힌트: 데이터 기간/형식 확인")
                st.stop()
            except Exception as e:
                st.error(f"예상치 못한 오류:\n\n{str(e)}")
                st.stop()

            st.divider()

            # Level 분석 (핵심)
            _render_level_section(monthly_df)

            # Delta 분석 (고급)
            _render_delta_section(monthly_df)

            # 교차검증 (고급)
            _render_cross_validation_section(monthly_df)

        # 푸터
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - TQQQ 금리-오차 관계 분석 (연구용)")

    except Exception as e:
        st.error("애플리케이션 실행 중 예상치 못한 오류 발생:")
        st.exception(e)
        st.stop()


if __name__ == "__main__":
    main()
