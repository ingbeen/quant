"""
레버리지 ETF 일별 비교 CSV 생성 스크립트

softplus 동적 스프레드 모델로 TQQQ · QLD 를 시뮬레이션하고 실제 시세와 일별로 비교하여
상세 검증 지표와 상품별 일별 비교 CSV 를 생성한다.
모든 파라미터는 상수에서 정의됩니다.

운용보수와 스프레드는 두 상품 모두 TQQQ 기준이다 — QLD 는 대체 시세(QLD_proxy_max.csv)와 같은 입력으로 검증한다.

실행 명령어:
    poetry run python scripts/tqqq/generate_daily_comparison.py
"""

import sys

import pandas as pd

from qbt.common_constants import COL_CLOSE, QQQ_DATA_PATH
from qbt.tqqq import (
    build_monthly_spread_map,
    calculate_validation_metrics,
    simulate,
)
from qbt.tqqq.constants import (
    COL_ACTUAL_CUMUL_RETURN,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_SIMUL_CUMUL_RETURN,
    DAILY_COMPARISON_TARGETS,
    DEFAULT_SOFTPLUS_A,
    DEFAULT_SOFTPLUS_B,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN,
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    KEY_CUMULATIVE_RETURN_ACTUAL,
    KEY_CUMULATIVE_RETURN_SIMULATED,
    KEY_OVERLAP_DAYS,
    KEY_OVERLAP_END,
    KEY_OVERLAP_START,
)
from qbt.tqqq.data_loader import build_extended_expense_dict, create_ffr_dict, load_monthly_data
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 데이터 로드
    logger.debug("QQQ, FFR 및 Expense Ratio 데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    ffr_df = load_monthly_data(FFR_DATA_PATH)
    expense_df = load_monthly_data(EXPENSE_RATIO_DATA_PATH)

    # 2. softplus 스프레드 맵과 월별 값 생성
    spread_map = build_monthly_spread_map(ffr_df, DEFAULT_SOFTPLUS_A, DEFAULT_SOFTPLUS_B)
    ffr_dict = create_ffr_dict(ffr_df)
    # QLD 는 운용보수 파일 시작(2010-02)보다 먼저 상장 → 그 앞 구간을 고정값으로 확장
    expense_dict = build_extended_expense_dict(expense_df)

    for product_name, actual_path, leverage, output_path in DAILY_COMPARISON_TARGETS:
        # 3. 겹치는 기간 추출
        actual_df = load_stock_data(actual_path)
        underlying_overlap, actual_overlap = extract_overlap_period(qqq_df, actual_df)

        logger.debug(
            f"{product_name} 시뮬레이션 실행: leverage={leverage}, "
            f"softplus(a={DEFAULT_SOFTPLUS_A}, b={DEFAULT_SOFTPLUS_B})"
        )

        # 4. 시뮬레이션 실행
        initial_price = float(actual_overlap.iloc[0][COL_CLOSE])
        simulated_df = simulate(
            underlying_df=underlying_overlap,
            leverage=leverage,
            initial_price=initial_price,
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=spread_map,
        )

        logger.debug("시뮬레이션 완료")

        # 5. 검증 지표 계산 및 일별 비교 CSV 생성
        output_path.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"검증 지표 계산 및 일별 비교 CSV 생성: {output_path}")
        validation_results = calculate_validation_metrics(
            simulated_df=simulated_df,
            actual_df=actual_overlap,
            output_path=output_path,
        )

        daily_df = pd.read_csv(output_path)
        logger.debug(f"일별 비교 CSV 저장 완료: {len(daily_df):,}행")

        # 6. 결과 출력 (터미널)
        logger.debug("=" * 64)
        logger.debug(f"{product_name} 시뮬레이션 검증")
        logger.debug("=" * 64)
        logger.debug(f"검증 기간: {validation_results[KEY_OVERLAP_START]} ~ {validation_results[KEY_OVERLAP_END]}")
        logger.debug(f"총 일수: {validation_results[KEY_OVERLAP_DAYS]:,}일")
        logger.debug(f"레버리지: {leverage:.1f}배")
        logger.debug(f"비용 모델: softplus(a={DEFAULT_SOFTPLUS_A}, b={DEFAULT_SOFTPLUS_B})")

        logger.debug("-" * 64)
        logger.debug("검증 지표")
        logger.debug("-" * 64)

        # 누적수익률 관련
        logger.debug(f"{COL_ACTUAL_CUMUL_RETURN}: {validation_results[KEY_CUMULATIVE_RETURN_ACTUAL]*100:+.1f}%")
        logger.debug(f"{COL_SIMUL_CUMUL_RETURN}: {validation_results[KEY_CUMULATIVE_RETURN_SIMULATED]*100:+.1f}%")
        logger.debug(f"누적배수로그차이_RMSE(%): {validation_results[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE]:.4f}%")
        logger.debug(f"누적배수로그차이_평균(%): {validation_results[KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN]:.2f}%")
        logger.debug(f"누적배수로그차이_최대(%): {validation_results[KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX]:.4f}%")
        logger.debug(f"일일수익률_절대차이 평균: {daily_df[COL_DAILY_RETURN_ABS_DIFF].mean():.4f}%")
        logger.debug(f"일일수익률_절대차이 최대: {daily_df[COL_DAILY_RETURN_ABS_DIFF].max():.4f}%")

        logger.debug("-" * 64)

        logger.debug(f"일별 비교 CSV 저장 완료: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
