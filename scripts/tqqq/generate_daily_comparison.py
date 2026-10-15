"""
TQQQ 일별 비교 CSV 생성 스크립트

softplus 동적 스프레드 모델로 TQQQ를 시뮬레이션하고 실제 TQQQ 데이터와 일별로 비교하여
상세 검증 지표와 일별 비교 CSV를 생성한다.
모든 파라미터는 상수에서 정의됩니다.

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
    DEFAULT_LEVERAGE_MULTIPLIER,
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
    TQQQ_DAILY_COMPARISON_PATH,
    TQQQ_DATA_PATH,
)
from qbt.tqqq.data_loader import create_expense_dict, create_ffr_dict, load_monthly_data
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
    logger.debug("QQQ, TQQQ, FFR 및 Expense Ratio 데이터 로딩 시작")
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_monthly_data(FFR_DATA_PATH)
    expense_df = load_monthly_data(EXPENSE_RATIO_DATA_PATH)

    # 2. 겹치는 기간 추출
    qqq_overlap, tqqq_overlap = extract_overlap_period(qqq_df, tqqq_df)

    # 3. softplus 스프레드 맵 생성
    spread_map = build_monthly_spread_map(ffr_df, DEFAULT_SOFTPLUS_A, DEFAULT_SOFTPLUS_B)
    logger.debug(
        f"시뮬레이션 실행: leverage={DEFAULT_LEVERAGE_MULTIPLIER}, "
        f"softplus(a={DEFAULT_SOFTPLUS_A}, b={DEFAULT_SOFTPLUS_B})"
    )

    # 4. 시뮬레이션 실행
    initial_price = float(tqqq_overlap.iloc[0][COL_CLOSE])
    simulated_df = simulate(
        underlying_df=qqq_overlap,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
        initial_price=initial_price,
        ffr_dict=create_ffr_dict(ffr_df),
        expense_dict=create_expense_dict(expense_df),
        funding_spread=spread_map,
    )

    logger.debug("시뮬레이션 완료")

    # 5. 검증 지표 계산 및 일별 비교 CSV 생성
    TQQQ_DAILY_COMPARISON_PATH.parent.mkdir(exist_ok=True, parents=True)
    logger.debug(f"검증 지표 계산 및 일별 비교 CSV 생성: {TQQQ_DAILY_COMPARISON_PATH}")
    validation_results = calculate_validation_metrics(
        simulated_df=simulated_df,
        actual_df=tqqq_overlap,
        output_path=TQQQ_DAILY_COMPARISON_PATH,
    )

    daily_df = pd.read_csv(TQQQ_DAILY_COMPARISON_PATH)
    logger.debug(f"일별 비교 CSV 저장 완료: {len(daily_df):,}행")

    # 6. 결과 출력 (터미널)
    logger.debug("=" * 64)
    logger.debug("TQQQ 시뮬레이션 검증")
    logger.debug("=" * 64)
    logger.debug(f"검증 기간: {validation_results[KEY_OVERLAP_START]} ~ {validation_results[KEY_OVERLAP_END]}")
    logger.debug(f"총 일수: {validation_results[KEY_OVERLAP_DAYS]:,}일")
    logger.debug(f"레버리지: {DEFAULT_LEVERAGE_MULTIPLIER:.1f}배")
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

    logger.debug(f"일별 비교 CSV 저장 완료: {TQQQ_DAILY_COMPARISON_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
