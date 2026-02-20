"""
합성+실제 TQQQ 병합 데이터 생성 스크립트

QQQ 전체 기간을 SoftPlus 동적 스프레드 모델로 시뮬레이션하고,
합성 구간(1999~2010)과 실제 TQQQ(2010~)를 가격 스케일링 후 병합하여
완전한 TQQQ 시계열을 생성한다.

핵심 흐름:
1. QQQ 전체 기간 시뮬레이션 (softplus 동적 스프레드)
2. 접합점(실제 TQQQ 첫 거래일)에서 가격 스케일링
3. 합성 구간 + 실제 TQQQ 병합
4. TQQQ_synthetic_max.csv 저장 + 메타데이터 기록

실행 명령어:
    poetry run python scripts/tqqq/generate_synthetic.py
"""

import sys

import pandas as pd

from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    PRICE_COLUMNS,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.tqqq import build_monthly_spread_map, simulate
from qbt.tqqq.constants import (
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_PRE_LISTING_EXPENSE_RATIO,
    DEFAULT_SOFTPLUS_A,
    DEFAULT_SOFTPLUS_B,
    DEFAULT_SYNTHETIC_INITIAL_PRICE,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    TQQQ_DATA_PATH,
)
from qbt.tqqq.data_loader import (
    create_expense_dict,
    load_expense_ratio_data,
    load_ffr_data,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)


def _build_extended_expense_dict(expense_df: pd.DataFrame) -> dict[str, float]:
    """
    운용비율 딕셔너리를 생성하고, 1999-01부터 실제 데이터 시작 전까지 고정값으로 확장한다.

    TQQQ 실제 운용비율 데이터는 2010-02부터 존재하므로,
    1999-01 ~ 2010-01 구간에 DEFAULT_PRE_LISTING_EXPENSE_RATIO를 적용한다.

    Args:
        expense_df: Expense Ratio DataFrame (DATE: str (yyyy-mm), VALUE: float)

    Returns:
        1999-01부터 커버하는 확장된 expense 딕셔너리
    """
    # 1. 기존 expense_df를 딕셔너리로 변환
    expense_dict = create_expense_dict(expense_df)

    # 2. 최초 월 확인
    earliest_month = min(expense_dict.keys())
    earliest_year, earliest_month_num = map(int, earliest_month.split("-"))

    # 3. 1999-01 ~ 최초 월 직전까지 고정값 채우기
    fill_year = 1999
    fill_month = 1

    while True:
        fill_key = f"{fill_year:04d}-{fill_month:02d}"

        # 최초 월에 도달하면 종료
        if fill_year > earliest_year or (fill_year == earliest_year and fill_month >= earliest_month_num):
            break

        expense_dict[fill_key] = DEFAULT_PRE_LISTING_EXPENSE_RATIO

        # 다음 월로 이동
        fill_month += 1
        if fill_month > 12:
            fill_month = 1
            fill_year += 1

    return expense_dict


@cli_exception_handler
def main() -> int:
    """
    합성+실제 TQQQ 병합 데이터 생성.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    logger.debug("합성+실제 TQQQ 병합 데이터 생성 시작")
    logger.debug(
        f"파라미터: multiplier={DEFAULT_LEVERAGE_MULTIPLIER}, "
        f"softplus(a={DEFAULT_SOFTPLUS_A}, b={DEFAULT_SOFTPLUS_B}), "
        f"initial_price={DEFAULT_SYNTHETIC_INITIAL_PRICE}"
    )

    # 1. 데이터 로드: QQQ, TQQQ(실제), FFR, Expense Ratio
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)

    logger.debug(f"QQQ: {len(qqq_df):,}행 ({qqq_df[COL_DATE].min()} ~ {qqq_df[COL_DATE].max()})")
    logger.debug(f"TQQQ(실제): {len(tqqq_df):,}행 ({tqqq_df[COL_DATE].min()} ~ {tqqq_df[COL_DATE].max()})")

    # 2. SoftPlus 스프레드 맵 생성
    spread_map = build_monthly_spread_map(ffr_df, a=DEFAULT_SOFTPLUS_A, b=DEFAULT_SOFTPLUS_B)
    logger.debug(f"SoftPlus 스프레드 맵 생성 완료: {len(spread_map)}개월")

    # 3. expense_dict 확장 (1999-01 ~ expense_df 최초월 직전까지 고정값 채우기)
    extended_expense_dict = _build_extended_expense_dict(expense_df)
    logger.debug(
        f"확장된 expense_dict: {len(extended_expense_dict)}개월 "
        f"({min(extended_expense_dict.keys())} ~ {max(extended_expense_dict.keys())})"
    )

    # 4. simulate() 실행 (QQQ 전체 기간, softplus spread + 확장된 expense_dict)
    logger.debug("TQQQ 시뮬레이션 실행 중...")
    synthetic_df = simulate(
        underlying_df=qqq_df,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
        initial_price=DEFAULT_SYNTHETIC_INITIAL_PRICE,
        ffr_df=ffr_df,
        expense_df=expense_df,
        expense_dict=extended_expense_dict,
        funding_spread=spread_map,
    )
    logger.debug(f"시뮬레이션 완료: {len(synthetic_df):,}행")

    # 5. 접합점 계산
    overlap_date = tqqq_df[COL_DATE].min()
    logger.debug(f"접합점(실제 TQQQ 첫 거래일): {overlap_date}")

    synthetic_overlap_rows = synthetic_df[synthetic_df[COL_DATE] == overlap_date]
    actual_overlap_rows = tqqq_df[tqqq_df[COL_DATE] == overlap_date]
    synthetic_at_overlap = float(synthetic_overlap_rows.iloc[0][COL_CLOSE])
    actual_at_overlap = float(actual_overlap_rows.iloc[0][COL_CLOSE])
    scale_factor = actual_at_overlap / synthetic_at_overlap

    logger.debug(f"시뮬레이션 접합점 종가: {synthetic_at_overlap:.6f}")
    logger.debug(f"실제 TQQQ 접합점 종가: {actual_at_overlap:.6f}")
    logger.debug(f"스케일 팩터: {scale_factor:.6f}")

    # 6. 합성 구간 스케일링 (접합일 이전 구간)
    synthetic_before = synthetic_df[synthetic_df[COL_DATE] < overlap_date].copy()
    for col in PRICE_COLUMNS:
        if col in synthetic_before.columns:
            synthetic_before[col] = synthetic_before[col] * scale_factor

    # 7. 병합: 스케일링된 합성(< overlap_date) + 실제 TQQQ(>= overlap_date)
    actual_from_overlap = tqqq_df[tqqq_df[COL_DATE] >= overlap_date].copy()
    merged_df: pd.DataFrame = pd.concat([synthetic_before, actual_from_overlap], ignore_index=True)
    merged_df = merged_df.sort_values(COL_DATE).reset_index(drop=True)

    logger.debug(f"병합 완료: {len(merged_df):,}행 ({merged_df[COL_DATE].min()} ~ {merged_df[COL_DATE].max()})")
    logger.debug(f"  합성 구간: {len(synthetic_before):,}행 (~ {overlap_date} 이전)")
    logger.debug(f"  실제 구간: {len(actual_from_overlap):,}행 ({overlap_date} ~)")

    # 8. CSV 저장 (가격 컬럼 소수점 6자리 라운딩)
    TQQQ_SYNTHETIC_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    for col in PRICE_COLUMNS:
        if col in merged_df.columns:
            merged_df[col] = merged_df[col].round(6)

    merged_df.to_csv(TQQQ_SYNTHETIC_DATA_PATH, index=False)
    logger.debug(f"병합 데이터 저장 완료: {TQQQ_SYNTHETIC_DATA_PATH}")

    # 9. 결과 요약 출력
    initial_close = float(merged_df.iloc[0][COL_CLOSE])
    final_close = float(merged_df.iloc[-1][COL_CLOSE])
    cumulative_return_pct = (final_close / initial_close - 1) * 100

    logger.debug(f"초기 가격: {initial_close:.6f}")
    logger.debug(f"최종 가격: {final_close:.6f}")
    logger.debug(f"누적 수익률: {cumulative_return_pct:+.2f}%")

    # 10. 메타데이터 저장
    synthetic_end_date = synthetic_before[COL_DATE].max()
    actual_end_date = actual_from_overlap[COL_DATE].max()
    file_size_bytes = TQQQ_SYNTHETIC_DATA_PATH.stat().st_size

    metadata = {
        "execution_params": {
            "leverage": DEFAULT_LEVERAGE_MULTIPLIER,
            "funding_spread_mode": "softplus",
            "softplus_a": DEFAULT_SOFTPLUS_A,
            "softplus_b": DEFAULT_SOFTPLUS_B,
            "pre_listing_expense_ratio": DEFAULT_PRE_LISTING_EXPENSE_RATIO,
        },
        "synthetic_period": {
            "start_date": str(merged_df[COL_DATE].min()),
            "end_date": str(synthetic_end_date),
            "total_days": len(synthetic_before),
            "scale_factor": round(scale_factor, 6),
        },
        "actual_period": {
            "start_date": str(overlap_date),
            "end_date": str(actual_end_date),
            "total_days": len(actual_from_overlap),
        },
        "merged_summary": {
            "total_days": len(merged_df),
            "initial_price": round(initial_close, 6),
            "final_price": round(final_close, 6),
            "cumulative_return_pct": round(cumulative_return_pct, 2),
        },
        "csv_info": {
            "path": str(TQQQ_SYNTHETIC_DATA_PATH),
            "row_count": len(merged_df),
            "file_size_bytes": file_size_bytes,
        },
    }
    save_metadata("tqqq_synthetic", metadata)
    logger.debug("메타데이터 저장 완료")

    return 0


if __name__ == "__main__":
    sys.exit(main())
