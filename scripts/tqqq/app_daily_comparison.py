"""레버리지 ETF 시뮬레이션 일별 비교 대시보드

TQQQ · QLD 의 일별 비교 CSV 데이터를 Streamlit + Plotly로 시각화한다.

실행 명령어:
    poetry run streamlit run scripts/tqqq/app_daily_comparison.py
"""

from pathlib import Path
from typing import Final

import streamlit as st

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.constants import (
    COL_ACTUAL_CLOSE,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_SIMUL_CLOSE,
    DAILY_COMPARISON_PRICES,
    DAILY_COMPARISON_TARGETS,
    EXPENSE_RATIO_DATA_PATH,
)
from qbt.tqqq.data_loader import load_comparison_data
from qbt.tqqq.visualization import (
    create_cumulative_return_diff_chart,
    create_daily_return_diff_histogram,
    create_price_comparison_chart,
)

DEFAULT_PRICE_KIND: Final = "종가"


@st.cache_data
def load_data(csv_path: Path, mtime: float):
    """
    데이터를 로드하고 캐싱한다.

    Args:
        csv_path: CSV 파일 경로
        mtime: 파일 수정 시각. 본문에서 쓰지 않고 캐시 키로만 둔다 — CSV 를 다시 만들면 새로 읽는다.
            이름이 밑줄로 시작하면 Streamlit 이 캐시 키에서 빼므로 밑줄을 붙이지 않는다

    Returns:
        로드된 DataFrame
    """
    return load_comparison_data(csv_path)


def main() -> None:
    """Streamlit 앱 메인 함수"""
    # 페이지 설정
    st.set_page_config(
        page_title="레버리지 ETF 시뮬레이션 일별 비교 대시보드",
        page_icon=":chart_with_upwards_trend:",
        layout="wide",
    )

    # 타이틀
    st.title("레버리지 ETF 시뮬레이션 일별 비교 대시보드")

    # 상품 선택
    csv_paths = {name: path for name, _, _, path in DAILY_COMPARISON_TARGETS}
    product_name = st.radio("상품", list(csv_paths), horizontal=True)
    csv_path = csv_paths[product_name]

    st.markdown(
        f"""
        이 대시보드는 레버리지 ETF 시뮬레이션 결과를 실제 {product_name} 데이터와 비교하여 검증합니다.
        - **데이터 소스**: `{csv_path.name}`
        - **비용 모델**: 운용보수(`{EXPENSE_RATIO_DATA_PATH.name}`)와 스프레드는 두 상품 모두 TQQQ 기준입니다.
          QLD 의 실제 운용보수와는 다를 수 있습니다
        - **시각화**: Plotly 인터랙티브 차트 (확대/축소, 범례 토글, 툴팁 지원)
        """
    )

    # 데이터 로드
    df = load_data(csv_path, csv_path.stat().st_mtime)

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
    price_kinds = list(DAILY_COMPARISON_PRICES)
    price_kind = st.radio("가격 종류", price_kinds, index=price_kinds.index(DEFAULT_PRICE_KIND), horizontal=True)
    st.markdown(
        f"""
        실제 {product_name} {price_kind}와 시뮬레이션 {price_kind}를 비교합니다.
        두 선이 가까울수록 시뮬레이션 정확도가 높습니다.
        - 시뮬레이션의 시가 · 고가 · 저가는 전날 시뮬 종가에서 기초 자산(QQQ)의 그날 움직임을 배율로 키운 값입니다
        - 실물은 장중 호가가 펀드 가치와 벌어질 수 있어 고가 · 저가는 시가 · 종가보다 차이가 큽니다
        """
    )
    price_chart = create_price_comparison_chart(df, product_name, price_kind)
    st.plotly_chart(price_chart, width="stretch")

    st.divider()

    # Section 2: 일일수익률 절대차이 히스토그램
    st.header("2. 일일수익률 절대차이 분포")
    st.markdown(
        """
        일일수익률의 절대차이 |실제 - 시뮬레이션| 가 어떻게 분포하는지 보여줍니다.
        값이 0 쪽에 몰려 있을수록(평균과 분산이 작을수록) 시뮬레이션이 정확합니다.
        """
    )
    histogram = create_daily_return_diff_histogram(df)
    st.plotly_chart(histogram, width="stretch")

    st.divider()

    # Section 3: 누적배수 로그차이 차트 (signed)
    st.header("3. 누적배수 로그차이 추이 (signed, 방향성 포함)")
    st.markdown(
        """
        시간에 따른 누적배수 로그차이를 추적합니다 (signed 버전).
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
    st.caption("QBT (Quant BackTest) - 레버리지 ETF 시뮬레이션 일별 비교 대시보드")


if __name__ == "__main__":
    main()
