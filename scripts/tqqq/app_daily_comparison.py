"""TQQQ 시뮬레이션 일별 비교 대시보드

일별 비교 CSV 데이터를 Streamlit + Plotly로 시각화한다.

실행 명령어:
    poetry run streamlit run scripts/tqqq/app_daily_comparison.py
"""

import os
from pathlib import Path

import streamlit as st

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_SIMUL_CLOSE,
    TQQQ_DAILY_COMPARISON_PATH,
)
from qbt.tqqq.data_loader import load_comparison_data
from qbt.tqqq.visualization import (
    create_cumulative_return_diff_chart,
    create_daily_return_diff_histogram,
    create_price_comparison_chart,
)


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
def load_data(csv_path: Path, _mtime: float):
    """
    데이터를 로드하고 캐싱한다.

    Args:
        csv_path: CSV 파일 경로
        _mtime: 파일 수정 시간 (캐시 키, _ 접두사는 Streamlit 캐시 규칙)

    Returns:
        로드된 DataFrame
    """
    return load_comparison_data(csv_path)


def main():
    """Streamlit 앱 메인 함수"""
    try:
        # 페이지 설정
        st.set_page_config(
            page_title="TQQQ 시뮬레이션 일별 비교 대시보드",
            page_icon=":chart_with_upwards_trend:",
            layout="wide",
        )

        # 타이틀
        st.title("TQQQ 시뮬레이션 일별 비교 대시보드")
        st.markdown(
            """
            이 대시보드는 레버리지 ETF 시뮬레이션 결과를 실제 TQQQ 데이터와 비교하여 검증합니다.
            - **데이터 소스**: `tqqq_daily_comparison.csv`
            - **시각화**: Plotly 인터랙티브 차트 (확대/축소, 범례 토글, 툴팁 지원)
            """
        )

        # 데이터 로드
        csv_path = TQQQ_DAILY_COMPARISON_PATH
        mtime = get_file_mtime(csv_path)
        df = load_data(csv_path, mtime)

        # 요약 지표
        st.header("요약 지표")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="검증 기간",
                value=f"{len(df):,}일",
                delta=f"{df[DISPLAY_DATE].min().strftime('%Y-%m-%d')} ~ {df[DISPLAY_DATE].max().strftime('%Y-%m-%d')}",
            )

        with col2:
            final_actual = df[COL_ACTUAL_CLOSE].iloc[-1]
            final_simul = df[COL_SIMUL_CLOSE].iloc[-1]
            price_diff_pct = ((final_simul - final_actual) / final_actual) * 100
            st.metric(label="최종 종가 (실제)", value=f"${final_actual:.2f}", delta=None)

        with col3:
            st.metric(label="최종 종가 (시뮬)", value=f"${final_simul:.2f}", delta=f"{price_diff_pct:+.2f}%")

        with col4:
            final_log_diff = df[COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED].iloc[-1]
            st.metric(label="최종 누적배수 로그차이 (signed)", value=f"{final_log_diff:+.2f}%")

        st.divider()

        # Section 1: 가격 비교 차트
        st.header("1. 가격 비교: 실제 vs 시뮬레이션")
        st.markdown(
            """
            실제 TQQQ 종가와 시뮬레이션 종가를 비교합니다.
            두 선이 가까울수록 시뮬레이션 정확도가 높습니다.
            """
        )
        price_chart = create_price_comparison_chart(df)
        st.plotly_chart(price_chart, width="stretch")

        st.divider()

        # Section 2: 일일수익률 차이 히스토그램
        st.header("2. 일일수익률 차이 분포")
        st.markdown(
            """
            일일수익률의 차이(실제 - 시뮬레이션)가 얼마나 분산되어 있는지 보여줍니다.
            평균이 0에 가깝고 분산이 작을수록 시뮬레이션이 정확합니다.
            """
        )
        histogram = create_daily_return_diff_histogram(df)
        st.plotly_chart(histogram, width="stretch")

        st.divider()

        # Section 3: 누적수익률 차이 차트 (signed)
        st.header("3. 누적수익률 차이 추이 (signed, 방향성 포함)")
        st.markdown(
            """
            시간에 따른 누적수익률 차이를 추적합니다 (signed 버전).
            - **양수**: 시뮬레이션이 실제보다 높음
            - **음수**: 시뮬레이션이 실제보다 낮음
            - **0에 가까움**: 거의 일치

            0 기준선에 가까울수록 장기 성과가 실제 데이터와 일치합니다.
            """
        )
        cumulative_chart = create_cumulative_return_diff_chart(df)
        st.plotly_chart(cumulative_chart, width="stretch")

        st.divider()

        # 푸터
        st.markdown("---")
        st.caption("QBT (Quant BackTest) - TQQQ 시뮬레이션 일별 비교 대시보드")

    except Exception as e:
        st.error("애플리케이션 실행 중 오류가 발생했습니다:")
        st.exception(e)
        return


if __name__ == "__main__":
    main()
