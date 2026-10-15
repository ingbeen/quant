"""
합성+실제 TQQQ 병합 데이터 생성 스크립트

QQQ 전체 기간을 SoftPlus 동적 스프레드 모델로 시뮬레이션하고,
실제 TQQQ 첫 거래일 앞은 합성 구간(가격을 그날 종가 비율로 맞춤), 그날부터는 실제 TQQQ 로 이어 붙여
완전한 TQQQ 시계열을 생성한다.

핵심 흐름:
1. QQQ 전체 기간 시뮬레이션 (softplus 동적 스프레드)
2. 실제 TQQQ 첫 거래일에서 이어 붙이기 (qbt.utils.proxy_series.splice_proxy)
3. TQQQ_synthetic_max.csv 저장

실행 명령어:
    poetry run python scripts/tqqq/generate_synthetic.py
"""

import sys

from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.tqqq import build_monthly_spread_map, simulate
from qbt.tqqq.constants import (
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_SOFTPLUS_A,
    DEFAULT_SOFTPLUS_B,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    TQQQ_DATA_PATH,
)
from qbt.tqqq.data_loader import (
    build_extended_expense_dict,
    create_ffr_dict,
    load_monthly_data,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.proxy_series import splice_proxy
from qbt.utils.stock_downloader import save_stock_csv

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """
    합성+실제 TQQQ 병합 데이터 생성.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    logger.debug("합성+실제 TQQQ 병합 데이터 생성 시작")
    logger.debug(
        f"파라미터: multiplier={DEFAULT_LEVERAGE_MULTIPLIER}, softplus(a={DEFAULT_SOFTPLUS_A}, b={DEFAULT_SOFTPLUS_B})"
    )

    # 1. 데이터 로드: QQQ, TQQQ(실제), FFR, Expense Ratio
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    tqqq_df = load_stock_data(TQQQ_DATA_PATH)
    ffr_df = load_monthly_data(FFR_DATA_PATH)
    expense_df = load_monthly_data(EXPENSE_RATIO_DATA_PATH)

    logger.debug(f"QQQ: {len(qqq_df):,}행 ({qqq_df[COL_DATE].min()} ~ {qqq_df[COL_DATE].max()})")
    logger.debug(f"TQQQ(실제): {len(tqqq_df):,}행 ({tqqq_df[COL_DATE].min()} ~ {tqqq_df[COL_DATE].max()})")

    # 2. SoftPlus 스프레드 맵 생성
    spread_map = build_monthly_spread_map(ffr_df, a=DEFAULT_SOFTPLUS_A, b=DEFAULT_SOFTPLUS_B)
    logger.debug(f"SoftPlus 스프레드 맵 생성 완료: {len(spread_map)}개월")

    # 3. expense_dict 확장 (1999-01 ~ expense_df 최초월 직전까지 고정값 채우기)
    extended_expense_dict = build_extended_expense_dict(expense_df)
    logger.debug(
        f"확장된 expense_dict: {len(extended_expense_dict)}개월 "
        f"({min(extended_expense_dict.keys())} ~ {max(extended_expense_dict.keys())})"
    )

    # 4. simulate() 실행 (QQQ 전체 기간). 가격 수준은 이어 붙일 때 실제 TQQQ 첫 거래일 종가로 다시 맞추므로
    # 시작 가격은 결과에 남지 않는다
    logger.debug("TQQQ 시뮬레이션 실행 중...")
    synthetic_df = simulate(
        underlying_df=qqq_df,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
        initial_price=1.0,
        ffr_dict=create_ffr_dict(ffr_df),
        expense_dict=extended_expense_dict,
        funding_spread=spread_map,
    )
    logger.debug(f"시뮬레이션 완료: {len(synthetic_df):,}행")

    # 5. 실제 TQQQ 첫 거래일 앞은 합성, 그날부터는 실제 행 그대로
    merged_df = splice_proxy(synthetic_df, tqqq_df)
    logger.debug(f"병합 완료: {len(merged_df):,}행 (이어 붙인 날: 실제 TQQQ 첫 거래일 {tqqq_df[COL_DATE].iloc[0]})")

    # 6. CSV 저장 — 다운로더의 급등락 검사는 쓰지 않는다(3배 합성은 하루 50% 를 넘는 날이 있다, 2001-01-03)
    save_stock_csv(merged_df, TQQQ_SYNTHETIC_DATA_PATH, check_price_spikes=False)

    # 7. 결과 요약 출력
    initial_close = float(merged_df.iloc[0][COL_CLOSE])
    final_close = float(merged_df.iloc[-1][COL_CLOSE])
    cumulative_return_pct = (final_close / initial_close - 1) * 100

    logger.debug(f"초기 가격: {initial_close:.6f}")
    logger.debug(f"최종 가격: {final_close:.6f}")
    logger.debug(f"누적 수익률: {cumulative_return_pct:+.2f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
