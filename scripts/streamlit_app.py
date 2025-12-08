"""TQQQ 시뮬레이션 검증 대시보드

일별 비교 CSV 데이터를 Streamlit + Plotly로 시각화한다.
"""

from pathlib import Path

import streamlit as st

from qbt.visualization import (
    create_cumulative_return_diff_chart,
    create_daily_return_diff_histogram,
    create_price_comparison_chart,
    load_comparison_data,
)


@st.cache_data
def load_data(csv_path: Path):
    """
    데이터를 로드하고 캐싱한다.

    Args:
        csv_path: CSV 파일 경로

    Returns:
        로드된 DataFrame
    """
    return load_comparison_data(csv_path)


def main():
    """Streamlit 앱 메인 함수"""
    # 페이지 설정
    st.set_page_config(
        page_title="TQQQ 시뮬레이션 검증 대시보드",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )

    # 타이틀
    st.title("TQQQ 시뮬레이션 검증 대시보드")
    st.markdown(
        """
        이 대시보드는 레버리지 ETF 시뮬레이션 결과를 실제 TQQQ 데이터와 비교하여 검증합니다.
        - **데이터 소스**: `results/tqqq_daily_comparison.csv`
        - **시각화**: Plotly 인터랙티브 차트 (확대/축소, 범례 토글, 툴팁 지원)
        """
    )

    # 데이터 로드
    csv_path = Path("results/tqqq_daily_comparison.csv")

    try:
        df = load_data(csv_path)
    except FileNotFoundError:
        st.error(f"데이터 파일을 찾을 수 없습니다: {csv_path}")
        st.info(
            "먼저 다음 명령어를 실행하여 일별 비교 데이터를 생성하세요:\n\n"
            "```bash\n"
            "poetry run python scripts/generate_tqqq_daily_comparison.py\n"
            "```"
        )
        return
    except ValueError as e:
        st.error(f"데이터 검증 오류: {e}")
        return
    except Exception as e:
        st.error(f"예기치 않은 오류: {e}")
        return

    # 요약 지표
    st.header("요약 지표")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="검증 기간",
            value=f"{len(df):,}일",
            delta=f"{df['날짜'].min().strftime('%Y-%m-%d')} ~ {df['날짜'].max().strftime('%Y-%m-%d')}",
        )

    with col2:
        final_actual = df["실제_종가"].iloc[-1]
        final_simul = df["시뮬_종가"].iloc[-1]
        price_diff_pct = ((final_simul - final_actual) / final_actual) * 100
        st.metric(label="최종 종가 (실제)", value=f"${final_actual:.2f}", delta=None)

    with col3:
        st.metric(label="최종 종가 (시뮬)", value=f"${final_simul:.2f}", delta=f"{price_diff_pct:+.2f}%")

    with col4:
        final_cum_diff = df["누적수익률_차이"].iloc[-1]
        st.metric(label="최종 누적수익률 차이", value=f"{final_cum_diff:.2f}%")

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

    # Section 3: 누적수익률 차이 차트
    st.header("3. 누적수익률 차이 추이")
    st.markdown(
        """
        시간에 따른 누적수익률 차이를 추적합니다.
        0 기준선에 가까울수록 장기 성과가 실제 데이터와 일치합니다.
        """
    )
    cumulative_chart = create_cumulative_return_diff_chart(df)
    st.plotly_chart(cumulative_chart, width="stretch")

    st.divider()

    # 푸터
    st.markdown("---")
    st.caption("QBT (Quant BackTest) - TQQQ 시뮬레이션 검증 대시보드")


if __name__ == "__main__":
    main()
