"""
합성 TQQQ 데이터 생성 스크립트

QQQ 데이터로부터 TQQQ 데이터를 시뮬레이션하여 생성한다.
QQQ의 가장 빠른 시작일부터 데이터를 생성하며, 모든 파라미터는 상수에서 정의됩니다.

실행 명령어:
    poetry run python scripts/tqqq/generate_synthetic_tqqq.py
"""

import sys

from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    PRICE_COLUMNS,
    QQQ_DATA_PATH,
)
from qbt.tqqq import simulate
from qbt.tqqq.constants import (
    DEFAULT_FUNDING_SPREAD,
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_SYNTHETIC_INITIAL_PRICE,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    TQQQ_SYNTHETIC_PATH,
)
from qbt.tqqq.data_loader import load_expense_ratio_data, load_ffr_data
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    logger.debug("합성 TQQQ 데이터 생성 시작")
    logger.debug(
        f"파라미터: multiplier={DEFAULT_LEVERAGE_MULTIPLIER}, "
        f"funding_spread={DEFAULT_FUNDING_SPREAD:.4f}, initial_price={DEFAULT_SYNTHETIC_INITIAL_PRICE}"
    )

    # 1. QQQ, FFR 및 Expense Ratio 데이터 로드
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)

    # 2. QQQ의 시작 날짜 자동 감지
    start_date = qqq_df[COL_DATE].min()
    logger.debug(f"QQQ 시작 날짜 자동 감지: {start_date}")

    # 3. 전체 QQQ 데이터 사용
    qqq_filtered = qqq_df.copy()

    logger.debug(f"QQQ 데이터: {len(qqq_filtered):,}행 ({qqq_filtered[COL_DATE].min()} ~ {qqq_filtered[COL_DATE].max()})")

    # 4. TQQQ 시뮬레이션 실행
    logger.debug("TQQQ 시뮬레이션 실행 중...")
    synthetic_tqqq = simulate(
        underlying_df=qqq_filtered,
        leverage=DEFAULT_LEVERAGE_MULTIPLIER,
        initial_price=DEFAULT_SYNTHETIC_INITIAL_PRICE,
        ffr_df=ffr_df,
        expense_df=expense_df,
        funding_spread=DEFAULT_FUNDING_SPREAD,
    )

    logger.debug(f"시뮬레이션 완료: {len(synthetic_tqqq):,}행")

    # 5. 출력 디렉토리 생성
    TQQQ_SYNTHETIC_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 6. CSV 저장 (가격 컬럼 소수점 6자리 라운딩)
    for col in PRICE_COLUMNS:
        if col in synthetic_tqqq.columns:
            synthetic_tqqq[col] = synthetic_tqqq[col].round(6)

    synthetic_tqqq.to_csv(TQQQ_SYNTHETIC_PATH, index=False)
    logger.debug(f"합성 TQQQ 데이터 저장 완료: {TQQQ_SYNTHETIC_PATH}")
    logger.debug(f"기간: {synthetic_tqqq[COL_DATE].min()} ~ {synthetic_tqqq[COL_DATE].max()}")
    logger.debug(f"행 수: {len(synthetic_tqqq):,}")
    logger.debug(f"초기 가격: {synthetic_tqqq.iloc[0][COL_CLOSE]:.2f}")
    logger.debug(f"최종 가격: {synthetic_tqqq.iloc[-1][COL_CLOSE]:.2f}")
    logger.debug(f"최소가: {synthetic_tqqq[COL_CLOSE].min():.2f}")
    logger.debug(f"최대가: {synthetic_tqqq[COL_CLOSE].max():.2f}")

    # 7. 누적 수익률 계산
    initial_close = synthetic_tqqq.iloc[0][COL_CLOSE]
    final_close = synthetic_tqqq.iloc[-1][COL_CLOSE]
    cumulative_return = (final_close / initial_close - 1) * 100

    logger.debug(f"누적 수익률: {cumulative_return:+.2f}%")

    return 0


if __name__ == "__main__":
    sys.exit(main())
