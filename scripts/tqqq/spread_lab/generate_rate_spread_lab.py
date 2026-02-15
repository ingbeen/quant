"""
TQQQ Rate Spread Lab CSV 생성 스크립트

일별 비교 데이터와 금리 데이터를 로드하여 월별 집계 후
금리-오차 관계 분석용 CSV 3개를 생성한다.
모든 파라미터는 상수에서 정의됩니다.

실행 명령어:
    poetry run python scripts/tqqq/spread_lab/generate_rate_spread_lab.py

출력:
    - storage/results/spread_lab/tqqq_rate_spread_lab_monthly.csv (월별 피처)
    - storage/results/spread_lab/tqqq_rate_spread_lab_summary.csv (요약 통계)
    - storage/results/spread_lab/tqqq_rate_spread_lab_model.csv (모델용, 조건부)
"""

import sys
from pathlib import Path

import pandas as pd

from qbt.common_constants import DISPLAY_DATE
from qbt.tqqq.analysis_helpers import (
    add_rate_change_lags,
    aggregate_monthly,
    build_model_dataset,
    calculate_daily_signed_log_diff,
    save_model_csv,
    save_monthly_features,
    save_summary_statistics,
)
from qbt.tqqq.constants import (
    COL_ACTUAL_DAILY_RETURN,
    COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
    COL_DAILY_SIGNED,
    COL_MONTH,
    COL_SIMUL_DAILY_RETURN,
    COL_SUM_DAILY_M,
    DEFAULT_MIN_MONTHS_FOR_ANALYSIS,
    DEFAULT_ROLLING_WINDOW,
    FFR_DATA_PATH,
    TQQQ_DAILY_COMPARISON_PATH,
    TQQQ_RATE_SPREAD_LAB_MODEL_PATH,
    TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH,
    TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH,
)
from qbt.tqqq.data_loader import load_comparison_data, load_ffr_data
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# ============================================================
# 메타데이터 타입 상수
# ============================================================
KEY_META_TYPE_RATE_SPREAD_LAB = "tqqq_rate_spread_lab"


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


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 데이터 로드
    logger.debug("일별 비교 데이터 및 금리 데이터 로딩 시작")
    daily_df = load_comparison_data(Path(TQQQ_DAILY_COMPARISON_PATH))
    ffr_df = load_ffr_data(Path(FFR_DATA_PATH))
    logger.debug(f"일별 비교 데이터: {len(daily_df):,}행, 금리 데이터: {len(ffr_df):,}행")

    # 2. 월별 집계
    logger.debug("월별 집계 시작")
    monthly_df = _prepare_monthly_data(daily_df, ffr_df)
    logger.debug(f"월별 집계 완료: {len(monthly_df):,}개월")

    # 3. lag 컬럼 추가
    monthly_df = add_rate_change_lags(monthly_df)

    # 4. CSV 저장
    logger.debug("CSV 파일 저장 시작")

    # 4-1. 월별 피처 CSV 저장
    save_monthly_features(monthly_df, TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH)
    logger.debug(f"월별 피처 CSV 저장 완료: {TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH}")

    # 4-2. 요약 통계 CSV 저장
    save_summary_statistics(monthly_df, TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH)
    logger.debug(f"요약 통계 CSV 저장 완료: {TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH}")

    # 4-3. 모델용 CSV 저장 (rolling 데이터가 window 미만인 경우 예외 발생)
    model_saved = False
    try:
        model_df = build_model_dataset(monthly_df, window=DEFAULT_ROLLING_WINDOW)
        save_model_csv(model_df, TQQQ_RATE_SPREAD_LAB_MODEL_PATH)
        logger.debug(f"모델용 CSV 저장 완료: {TQQQ_RATE_SPREAD_LAB_MODEL_PATH}")
        model_saved = True
    except ValueError as e:
        logger.warning(f"모델용 CSV 저장 실패 (데이터 부족): {e}")

    # 5. 메타데이터 저장
    output_files: dict[str, str] = {
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
    logger.debug("메타데이터 저장 완료: storage/results/meta.json")

    # 6. 결과 출력 (터미널)
    logger.debug("=" * 64)
    logger.debug("TQQQ Rate Spread Lab CSV 생성 완료")
    logger.debug("=" * 64)
    logger.debug(f"분석 기간: {monthly_df[COL_MONTH].min()} ~ {monthly_df[COL_MONTH].max()}")
    logger.debug(f"총 개월 수: {len(monthly_df):,}개월")
    logger.debug("-" * 64)
    logger.debug("저장된 파일:")
    logger.debug(f"  - 월별 피처: {TQQQ_RATE_SPREAD_LAB_MONTHLY_PATH}")
    logger.debug(f"  - 요약 통계: {TQQQ_RATE_SPREAD_LAB_SUMMARY_PATH}")
    if model_saved:
        logger.debug(f"  - 모델용: {TQQQ_RATE_SPREAD_LAB_MODEL_PATH}")
    else:
        logger.debug("  - 모델용: 저장 실패 (데이터 부족)")
    logger.debug("-" * 64)

    return 0


if __name__ == "__main__":
    sys.exit(main())
