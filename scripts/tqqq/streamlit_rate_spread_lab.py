"""TQQQ 금리-오차 관계 분석 연구용 앱

금리 환경과 시뮬레이션 오차의 관계를 시각화하여 spread 조정 전략 수립을 지원한다.

실행 명령어:
    poetry run streamlit run scripts/tqqq/streamlit_rate_spread_lab.py

주요 기능:
- Level 탭: 금리 수준 vs 월말 누적 signed 오차
- Delta 탭: 금리 변화 vs 오차 변화, Lag 효과, Rolling 상관
- 교차검증: de_m vs sum_daily_m 차이 분석

Fail-fast 정책:
- ValueError 발생 시 st.error() + st.stop()으로 즉시 중단
- 잘못된 차트/수치 표시 방지
"""

import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.analysis_helpers import (
    aggregate_monthly,
    calculate_daily_signed_log_diff,
)
from qbt.tqqq.constants import (
    COL_ACTUAL_DAILY_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_SIMUL_DAILY_RETURN,
    FFR_DATA_PATH,
    TQQQ_DAILY_COMPARISON_PATH,
)
from qbt.tqqq.data_loader import load_comparison_data, load_ffr_data


def get_file_mtime(path: Path) -> float:
    """
    파일의 수정 시간(mtime)을 반환한다.

    캐시 키에 mtime을 포함하여 최신 CSV 반영을 보장한다.

    Args:
        path: 파일 경로

    Returns:
        파일 수정 시간 (epoch timestamp)
    """
    return os.path.getmtime(path)


@st.cache_data(ttl=600)  # 10분 캐시
def load_daily_comparison(csv_path: Path, _mtime: float) -> pd.DataFrame:
    """
    일별 비교 CSV를 로드한다.

    Args:
        csv_path: CSV 파일 경로
        _mtime: 파일 수정 시간 (캐시 키, _ 접두사는 Streamlit 캐시 규칙)

    Returns:
        일별 비교 DataFrame

    Raises:
        ValueError: 파일 부재, 필수 컬럼 누락 등
    """
    return load_comparison_data(csv_path)


@st.cache_data(ttl=600)
def load_ffr(csv_path: Path, _mtime: float) -> pd.DataFrame:
    """
    금리(FFR) 월별 CSV를 로드한다.

    Args:
        csv_path: CSV 파일 경로
        _mtime: 파일 수정 시간 (캐시 키)

    Returns:
        FFR DataFrame (DATE: yyyy-mm 문자열, VALUE: 0~1 소수)

    Raises:
        ValueError: 파일 부재 등
    """
    return load_ffr_data(csv_path)


def prepare_monthly_data(
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
    # 주의: 이 함수는 ValueError를 raise할 수 있음 (1+r <= 0)
    daily_signed = calculate_daily_signed_log_diff(
        daily_return_real_pct=daily_df[COL_ACTUAL_DAILY_RETURN],
        daily_return_sim_pct=daily_df[COL_SIMUL_DAILY_RETURN],
    )

    # 2. 일별 데이터에 추가
    daily_with_signed = daily_df.copy()
    daily_with_signed["daily_signed"] = daily_signed

    # 3. 월별 집계 (aggregate_monthly는 e_m, de_m만 제공)
    # 주의: 이 함수는 ValueError를 raise할 수 있음 (커버리지 부족, 결과 부족 등)
    monthly = aggregate_monthly(
        daily_df=daily_with_signed,
        date_col=DISPLAY_DATE,
        signed_col=COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
        ffr_df=ffr_df,
        min_months_for_analysis=13,  # Rolling 12M 상관 계산 위해 최소 13개월
    )

    # 4. sum_daily_m 계산 (일일 증분의 월합)
    # aggregate_monthly에서 sum_daily_m은 placeholder(NA)이므로 여기서 계산
    date_col_data = pd.to_datetime(daily_with_signed[DISPLAY_DATE])
    daily_with_signed["month"] = date_col_data.dt.to_period("M")
    sum_daily_monthly = daily_with_signed.groupby("month", as_index=False)["daily_signed"].sum()
    # rename()의 타입 추론 문제 회피: 컬럼 직접 재할당
    sum_daily_monthly["sum_daily_m_calc"] = sum_daily_monthly["daily_signed"]
    sum_daily_monthly = sum_daily_monthly.drop(columns=["daily_signed"])

    # 5. monthly에 merge
    monthly = monthly.merge(sum_daily_monthly, on="month", how="left")

    # 6. sum_daily_m 업데이트 (기존 NA를 계산값으로 교체)
    monthly["sum_daily_m"] = monthly["sum_daily_m_calc"]
    monthly.drop(columns=["sum_daily_m_calc"], inplace=True)

    return monthly


def create_level_chart(
    monthly_df: pd.DataFrame,
    y_col: str,
    y_label: str,
) -> go.Figure:
    """
    Level 탭: 금리 수준 vs 오차 수준 산점도 및 시계열 라인 차트를 생성한다.

    Args:
        monthly_df: 월별 데이터
        y_col: y축 컬럼명 (e_m, de_m, sum_daily_m 중 하나)
        y_label: y축 레이블 (의미 설명 포함)

    Returns:
        Plotly Figure 객체
    """
    # 결측치 제거
    plot_df = monthly_df.dropna(subset=["rate_pct", y_col])

    # 서브플롯 생성: 위(산점도), 아래(시계열)
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("금리 수준 vs 오차 (산점도)", "시계열 추이"),
        row_heights=[0.5, 0.5],
        vertical_spacing=0.15,
    )

    # 1. 산점도: rate_pct vs y_col
    fig.add_trace(
        go.Scatter(
            x=plot_df["rate_pct"],
            y=plot_df[y_col],
            mode="markers",
            name="월별 데이터",
            marker={"color": "#1f77b4", "size": 8},
            hovertemplate="<b>금리</b>: %{x:.2f}%<br>" + f"<b>{y_label}</b>: %{{y:.2f}}%<br>" + "<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # 추세선 (OLS)
    # 간단한 1차 다항식 근사
    import numpy as np

    x = np.asarray(plot_df["rate_pct"].values, dtype=np.float64)
    y = np.asarray(plot_df[y_col].values, dtype=np.float64)
    if len(x) > 1:
        coef = np.polyfit(x, y, 1)
        trend_y = np.polyval(coef, x)
        fig.add_trace(
            go.Scatter(
                x=plot_df["rate_pct"],
                y=trend_y,
                mode="lines",
                name=f"추세선 (y={coef[0]:.2f}x+{coef[1]:.2f})",
                line={"color": "red", "dash": "dash"},
            ),
            row=1,
            col=1,
        )

    # 2. 시계열 라인: month vs rate_pct, y_col
    # month를 문자열로 변환 (Plotly x축 호환)
    plot_df_ts = plot_df.copy()
    plot_df_ts["month_str"] = plot_df_ts["month"].astype(str)

    fig.add_trace(
        go.Scatter(
            x=plot_df_ts["month_str"],
            y=plot_df_ts["rate_pct"],
            mode="lines",
            name="금리 수준",
            line={"color": "#2ca02c", "width": 2},
            yaxis="y3",
            hovertemplate="<b>월</b>: %{x}<br>" + "<b>금리</b>: %{y:.2f}%<br>" + "<extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=plot_df_ts["month_str"],
            y=plot_df_ts[y_col],
            mode="lines",
            name=y_label,
            line={"color": "#ff7f0e", "width": 2},
            yaxis="y4",
            hovertemplate="<b>월</b>: %{x}<br>" + f"<b>{y_label}</b>: %{{y:.2f}}%<br>" + "<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # 레이아웃 업데이트
    fig.update_xaxes(title_text="금리 수준 (%)", row=1, col=1)
    fig.update_yaxes(title_text=y_label, row=1, col=1)

    fig.update_xaxes(title_text="월", row=2, col=1)
    fig.update_yaxes(title_text="금리 (%)", row=2, col=1, secondary_y=False)

    # 이중 y축 설정 (시계열 차트)
    fig.update_layout(
        yaxis3={"overlaying": "y2", "side": "left", "title": "금리 (%)"},
        yaxis4={"overlaying": "y2", "side": "right", "title": y_label},
        height=800,
        hovermode="x unified",
    )

    return fig


def create_delta_chart(
    monthly_df: pd.DataFrame,
    y_col: str,
    y_label: str,
    lag: int,
) -> tuple[go.Figure, pd.DataFrame]:
    """
    Delta 탭: 금리 변화 vs 오차 변화 산점도 및 Rolling 상관을 생성한다.

    Args:
        monthly_df: 월별 데이터
        y_col: y축 컬럼명 (de_m 또는 sum_daily_m)
        y_label: y축 레이블
        lag: Lag 개월 수 (0, 1, 2)

    Returns:
        (Plotly Figure 객체, 유효 데이터 DataFrame)
    """
    # Lag 적용: dr_m을 k개월 shift
    df = monthly_df.copy()
    df["dr_shifted"] = df["dr_m"].shift(lag)

    # 결측치 제거 (dr_shifted와 y_col 모두 존재하는 행만)
    plot_df = df.dropna(subset=["dr_shifted", y_col])

    # 샘플 수
    n = len(plot_df)

    # 서브플롯 생성: 위(산점도), 아래(Rolling 12M 상관)
    from plotly.subplots import make_subplots

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=(
            f"금리 변화 (Lag {lag}) vs 오차 변화 (n={n})",
            "Rolling 12개월 상관",
        ),
        row_heights=[0.5, 0.5],
        vertical_spacing=0.15,
    )

    # 1. 산점도: dr_shifted vs y_col
    fig.add_trace(
        go.Scatter(
            x=plot_df["dr_shifted"],
            y=plot_df[y_col],
            mode="markers",
            name="월별 데이터",
            marker={"color": "#1f77b4", "size": 8},
            hovertemplate="<b>금리 변화 (Lag "
            + str(lag)
            + ")</b>: %{x:.2f}%p<br>"
            + f"<b>{y_label}</b>: %{{y:.2f}}%<br>"
            + "<extra></extra>",
        ),
        row=1,
        col=1,
    )

    # 추세선
    import numpy as np

    x = np.asarray(plot_df["dr_shifted"].values, dtype=np.float64)
    y = np.asarray(plot_df[y_col].values, dtype=np.float64)
    if len(x) > 1:
        coef = np.polyfit(x, y, 1)
        trend_y = np.polyval(coef, x)
        fig.add_trace(
            go.Scatter(
                x=plot_df["dr_shifted"],
                y=trend_y,
                mode="lines",
                name=f"추세선 (y={coef[0]:.2f}x+{coef[1]:.2f})",
                line={"color": "red", "dash": "dash"},
            ),
            row=1,
            col=1,
        )

    # 2. Rolling 12M 상관
    # 최소 12개월 필요
    if len(plot_df) >= 12:
        plot_df_sorted = plot_df.sort_values(by="month").reset_index(drop=True)
        rolling_corr = (
            plot_df_sorted[["dr_shifted", y_col]]
            .rolling(window=12)
            .corr()
            .iloc[0::2, -1]  # dr_shifted와 y_col의 상관만 추출
            .reset_index(drop=True)
        )

        # month 문자열 변환
        plot_df_sorted["month_str"] = plot_df_sorted["month"].astype(str)

        fig.add_trace(
            go.Scatter(
                x=plot_df_sorted["month_str"],
                y=rolling_corr,
                mode="lines+markers",
                name="Rolling 12M 상관",
                line={"color": "#2ca02c", "width": 2},
                hovertemplate="<b>월</b>: %{x}<br>" + "<b>상관</b>: %{y:.2f}<br>" + "<extra></extra>",
            ),
            row=2,
            col=1,
        )

        # 0 기준선
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row="2", col="1")
    else:
        # 데이터 부족 안내
        fig.add_annotation(
            text=f"Rolling 12M 상관 계산 불가 (샘플 수: {len(plot_df)}, 최소: 12)",
            xref="x2",
            yref="y2",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 14, "color": "red"},
            row=2,
            col=1,
        )

    # 레이아웃 업데이트
    fig.update_xaxes(title_text=f"금리 변화 (Lag {lag}, %p)", row=1, col=1)
    fig.update_yaxes(title_text=y_label, row=1, col=1)

    fig.update_xaxes(title_text="월", row=2, col=1)
    fig.update_yaxes(title_text="상관 계수", row=2, col=1)

    fig.update_layout(
        height=800,
        hovermode="x unified",
    )

    return fig, plot_df


def display_cross_validation(monthly_df: pd.DataFrame):
    """
    de_m vs sum_daily_m 교차검증 결과를 표시한다.

    둘이 거의 같아야 하지만, 반올림/결측/계산 방식 차이로 완전히 동일하지는 않다.

    Args:
        monthly_df: 월별 데이터 (de_m, sum_daily_m 포함)
    """
    st.subheader("교차검증: de_m vs sum_daily_m")

    st.markdown(
        """
        **목적**: 두 가지 방법으로 계산한 월간 오차 변화가 일치하는지 검증

        - `de_m`: 월말 누적 signed의 월간 변화 (diff)
        - `sum_daily_m`: 일일 증분 signed의 월합 (sum)

        **기대**: 거의 같아야 함 (완전 동일 X)

        **차이 원인**:
        1. 일일수익률 반올림 (CSV 저장 시 소수점 자릿수 제한)
        2. 거래일 결측 (일부 날짜 누락 가능성)
        3. 누적수익률 계산 방식 차이 (실제 데이터 vs 시뮬 계산 경로)
        """
    )

    # 결측치 제거
    valid_df = monthly_df.dropna(subset=["de_m", "sum_daily_m"])

    if len(valid_df) == 0:
        st.warning("교차검증 가능한 데이터가 없습니다.")
        return

    # 차이 계산
    valid_df = valid_df.copy()
    valid_df["diff"] = valid_df["de_m"] - valid_df["sum_daily_m"]

    # 통계
    max_diff = valid_df["diff"].abs().max()
    mean_diff = valid_df["diff"].abs().mean()
    std_diff = valid_df["diff"].std()

    st.metric(label="최대 절댓값 차이", value=f"{max_diff:.6f}%")
    st.metric(label="평균 절댓값 차이", value=f"{mean_diff:.6f}%")
    st.metric(label="표준편차", value=f"{std_diff:.6f}%")

    # 상위 5개 차이
    st.markdown("**차이가 큰 상위 5개월**:")
    top_diff = valid_df.nlargest(5, "diff", keep="all")[["month", "de_m", "sum_daily_m", "diff"]]
    st.dataframe(top_diff, hide_index=True)

    # 히스토그램
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=valid_df["diff"],
            nbinsx=30,
            name="차이 분포",
            marker={"color": "#9467bd"},
        )
    )
    fig.update_layout(
        title=f"de_m - sum_daily_m 차이 분포 (평균: {mean_diff:.6f}%, 표준편차: {std_diff:.6f}%)",
        xaxis_title="차이 (%)",
        yaxis_title="빈도",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True)


def main():
    """Streamlit 앱 메인 함수"""
    try:
        # 페이지 설정
        st.set_page_config(
            page_title="TQQQ 금리-오차 관계 분석 (연구용)",
            page_icon=":bar_chart:",
            layout="wide",
        )

        # 타이틀
        st.title("TQQQ 금리-오차 관계 분석 (연구용)")
        st.markdown(
            """
            금리 환경과 시뮬레이션 오차의 관계를 시각화하여 **spread 조정 전략** 수립을 지원합니다.

            **주요 기능**:
            - **Level 탭**: 금리 수준 vs 월말 누적 signed 오차
            - **Delta 탭**: 금리 변화 vs 오차 변화, Lag 효과, Rolling 상관
            - **교차검증**: de_m vs sum_daily_m 일치 여부 확인
            """
        )

        st.divider()

        # 데이터 로드
        st.header("데이터 로딩")

        try:
            daily_mtime = get_file_mtime(TQQQ_DAILY_COMPARISON_PATH)
            ffr_mtime = get_file_mtime(FFR_DATA_PATH)

            daily_df = load_daily_comparison(TQQQ_DAILY_COMPARISON_PATH, daily_mtime)
            ffr_df = load_ffr(FFR_DATA_PATH, ffr_mtime)

            st.success(f"✅ 일별 비교 데이터 로드 완료: {len(daily_df):,}행")
            st.success(f"✅ 금리 데이터 로드 완료: {len(ffr_df):,}행")

        except Exception as e:
            st.error(f"❌ 데이터 로딩 실패:\n\n{str(e)}\n\n💡 힌트: CSV 파일 경로 및 형식 확인")
            st.stop()

        # 월별 데이터 준비
        st.header("월별 데이터 준비")

        try:
            monthly_df = prepare_monthly_data(daily_df, ffr_df)
            st.success(f"✅ 월별 집계 완료: {len(monthly_df):,}개월")

            # 요약 통계
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    label="분석 기간",
                    value=f"{monthly_df['month'].min()} ~ {monthly_df['month'].max()}",
                )
            with col2:
                rate_min = monthly_df["rate_pct"].min()
                rate_max = monthly_df["rate_pct"].max()
                st.metric(label="금리 범위", value=f"{rate_min:.2f}% ~ {rate_max:.2f}%")
            with col3:
                e_min = monthly_df["e_m"].min()
                e_max = monthly_df["e_m"].max()
                st.metric(label="월말 오차 범위", value=f"{e_min:.2f}% ~ {e_max:.2f}%")

        except ValueError as e:
            st.error(f"❌ 월별 집계 실패 (fail-fast):\n\n{str(e)}\n\n💡 힌트: 데이터 기간/형식 확인")
            st.stop()
        except Exception as e:
            st.error(f"❌ 예상치 못한 오류:\n\n{str(e)}")
            st.stop()

        st.divider()

        # 탭 구성
        tab1, tab2, tab3 = st.tabs(["📈 Level 분석", "📊 Delta 분석", "✅ 교차검증"])

        # === Level 탭 ===
        with tab1:
            st.header("Level 분석: 금리 수준 vs 오차")

            st.markdown(
                """
                **목적**: 금리 수준에 따라 오차가 체계적으로 변하는지 확인

                **y축 선택**:
                - `e_m` (월말 누적 signed, 기본): 해당 월 말 시점의 누적 오차
                - `de_m` (월간 변화): 해당 월의 오차 증감
                - `sum_daily_m` (일일 증분 월합): 일일 오차의 월간 누적
                """
            )

            # y축 선택
            y_option = st.radio(
                "y축 선택:",
                options=["e_m (월말 누적 signed)", "de_m (월간 변화)", "sum_daily_m (일일 증분 월합)"],
                index=0,
            )

            if "e_m" in y_option:
                y_col = "e_m"
                y_label = "월말 누적 signed (%)"
                y_caption = "해당 월 마지막 거래일의 누적 오차"
            elif "de_m" in y_option:
                y_col = "de_m"
                y_label = "월간 변화 (%)"
                y_caption = "전월 대비 오차 증감"
            else:
                y_col = "sum_daily_m"
                y_label = "일일 증분 월합 (%)"
                y_caption = "해당 월 일일 오차의 합계"

            st.caption(f"**y축 의미**: {y_caption}")

            # 차트 생성
            try:
                level_fig = create_level_chart(monthly_df, y_col, y_label)
                st.plotly_chart(level_fig, use_container_width=True)
            except Exception as e:
                st.error(f"❌ Level 차트 생성 실패:\n\n{str(e)}")

        # === Delta 탭 ===
        with tab2:
            st.header("Delta 분석: 금리 변화 vs 오차 변화")

            st.markdown(
                """
                **목적**: 금리 변화와 오차 변화의 관계 및 Lag 효과 확인

                **Lag 옵션**:
                - Lag 0: 동월 금리 변화 vs 오차 변화
                - Lag 1: 전월 금리 변화 vs 당월 오차 변화
                - Lag 2: 2개월 전 금리 변화 vs 당월 오차 변화
                """
            )

            # y축 선택
            y_option_delta = st.radio(
                "y축 선택:",
                options=["de_m (월간 변화)", "sum_daily_m (일일 증분 월합)"],
                index=0,
                key="delta_y",
            )

            if "de_m" in y_option_delta:
                y_col_delta = "de_m"
                y_label_delta = "월간 변화 (%)"
            else:
                y_col_delta = "sum_daily_m"
                y_label_delta = "일일 증분 월합 (%)"

            # Lag 선택
            lag = st.selectbox("Lag (개월):", options=[0, 1, 2], index=0)

            # 차트 생성
            try:
                delta_fig, valid_df = create_delta_chart(monthly_df, y_col_delta, y_label_delta, lag)
                st.plotly_chart(delta_fig, use_container_width=True)

                # 샘플 수 및 상관 안내
                st.info(
                    f"""
                    **샘플 수**: {len(valid_df)}개월

                    **상관 해석 주의점**:
                    - 상관이 높다고 인과관계를 의미하지 않음
                    - 다른 요인(변동성, 레버리지 리밸런싱 등)도 영향 가능
                    - Lag 효과는 금리 정책 시차를 반영할 수 있음
                    """
                )

            except ValueError as e:
                st.error(f"❌ Delta 차트 생성 실패 (fail-fast):\n\n{str(e)}\n\n💡 힌트: 데이터 부족 가능성")
                st.stop()
            except Exception as e:
                st.error(f"❌ 예상치 못한 오류:\n\n{str(e)}")

        # === 교차검증 탭 ===
        with tab3:
            try:
                display_cross_validation(monthly_df)
            except Exception as e:
                st.error(f"❌ 교차검증 표시 실패:\n\n{str(e)}")

        st.divider()

        # 푸터
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - TQQQ 금리-오차 관계 분석 (연구용)")

    except Exception as e:
        st.error("❌ 애플리케이션 실행 중 예상치 못한 오류 발생:")
        st.exception(e)
        st.stop()


if __name__ == "__main__":
    main()
