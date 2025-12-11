"""
합성 TQQQ 데이터 생성 스크립트

QQQ 데이터로부터 TQQQ 데이터를 시뮬레이션하여 생성한다.
검증 스크립트에서 찾은 최적 multiplier를 사용하여 1999년부터의 데이터를 생성한다.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from qbt.common_constants import COL_CLOSE, COL_DATE, PRICE_COLUMNS
from qbt.config import FFR_DATA_PATH, QQQ_DATA_PATH, TQQQ_SYNTHETIC_PATH
from qbt.synth import simulate_leveraged_etf
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_ffr_data, load_stock_data

logger = get_logger(__name__)


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    parser = argparse.ArgumentParser(
        description="QQQ 데이터로부터 합성 TQQQ 데이터 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            사용 예시:
            # 기본 파라미터로 생성 (start-date=1999-03-10, multiplier=3.0, spread=0.5%%, expense=0.8%%)
            poetry run python scripts/tqqq/generate_synthetic_tqqq.py

            # 일부 파라미터만 지정
            poetry run python scripts/tqqq/generate_synthetic_tqqq.py --start-date 2010-01-01

            # 모든 파라미터 지정
            poetry run python scripts/tqqq/generate_synthetic_tqqq.py \\
                --start-date 1999-03-10 \\
                --multiplier 3.0 \\
                --funding-spread 0.5 \\
                --expense-ratio 0.009 \\
                --initial-price 100.0 \\
                --output data/raw/TQQQ_synthetic_1999-03-10_max.csv
        """,
    )
    parser.add_argument(
        "--qqq-path",
        type=Path,
        default=QQQ_DATA_PATH,
        help="QQQ CSV 파일 경로",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="1999-03-10",
        help="시작 날짜 (YYYY-MM-DD 형식)",
    )
    parser.add_argument(
        "--multiplier",
        type=float,
        default=3.0,
        help="레버리지 배수",
    )
    parser.add_argument(
        "--expense-ratio",
        type=float,
        default=0.008,
        help="연간 비용 비율",
    )
    parser.add_argument(
        "--funding-spread",
        type=float,
        default=0.5,
        help="펀딩 스프레드 (%%)",
    )
    parser.add_argument(
        "--ffr-path",
        type=Path,
        default=FFR_DATA_PATH,
        help="연방기금금리 CSV 파일 경로",
    )
    parser.add_argument(
        "--initial-price",
        type=float,
        default=200.0,
        help="초기 가격",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=TQQQ_SYNTHETIC_PATH,
        help="출력 CSV 파일 경로",
    )

    args = parser.parse_args()

    # 1. 시작 날짜 파싱
    try:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    except ValueError as e:
        raise ValueError(f"날짜 형식이 올바르지 않습니다 (YYYY-MM-DD 필요): {args.start_date}") from e

    logger.debug("합성 TQQQ 데이터 생성 시작")
    logger.debug(
        f"파라미터: multiplier={args.multiplier}, expense_ratio={args.expense_ratio}, "
        f"funding_spread={args.funding_spread}, initial_price={args.initial_price}"
    )
    logger.debug(f"시작 날짜: {start_date}")

    # 2. QQQ 및 FFR 데이터 로드
    qqq_df = load_stock_data(args.qqq_path)
    ffr_df = load_ffr_data(args.ffr_path)

    # 3. 시작 날짜 이후 데이터만 필터링
    qqq_filtered = qqq_df[qqq_df[COL_DATE] >= start_date].copy()

    if qqq_filtered.empty:
        raise ValueError(
            f"시작 날짜 {start_date} 이후의 QQQ 데이터가 없습니다. QQQ 데이터 범위: {qqq_df[COL_DATE].min()} ~ {qqq_df[COL_DATE].max()}"
        )

    logger.debug(
        f"QQQ 데이터 필터링: {len(qqq_filtered):,}행 ({qqq_filtered[COL_DATE].min()} ~ {qqq_filtered[COL_DATE].max()})"
    )

    # 4. TQQQ 시뮬레이션 실행
    logger.debug("TQQQ 시뮬레이션 실행 중...")
    synthetic_tqqq = simulate_leveraged_etf(
        underlying_df=qqq_filtered,
        leverage=args.multiplier,
        expense_ratio=args.expense_ratio,
        initial_price=args.initial_price,
        ffr_df=ffr_df,
        funding_spread=args.funding_spread,
    )

    logger.debug(f"시뮬레이션 완료: {len(synthetic_tqqq):,}행")

    # 5. 출력 디렉토리 생성
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # 6. CSV 저장 (가격 컬럼 소수점 6자리 라운딩)
    for col in PRICE_COLUMNS:
        if col in synthetic_tqqq.columns:
            synthetic_tqqq[col] = synthetic_tqqq[col].round(6)

    synthetic_tqqq.to_csv(args.output, index=False)
    logger.debug(f"합성 TQQQ 데이터 저장 완료: {args.output}")
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
