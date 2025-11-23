"""
단일 백테스트 실행 스크립트

이동평균선 교차 전략 백테스트 (SMA/EMA/Buy&Hold)
CLI 인자로 파라미터를 지정합니다.
"""

import argparse
import sys

from qbt.backtest import (
    DataValidationError,
    StrategyParams,
    add_moving_averages,
    run_buy_and_hold,
    run_strategy,
)
from qbt.backtest.config import DEFAULT_DATA_FILE, DEFAULT_INITIAL_CAPITAL
from qbt.utils import (
    load_and_validate_data,
    print_comparison_table,
    print_summary,
    print_trades,
    setup_logger,
)

# 로거 설정
logger = setup_logger("run_single_backtest", level="DEBUG")


def parse_args():
    """CLI 인자를 파싱한다."""
    parser = argparse.ArgumentParser(
        description="이동평균선 교차 백테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # SMA + EMA + Buy&Hold 비교
  poetry run python scripts/run_single_backtest.py \\
      --short 20 --long 50 --stop-loss 0.10 --lookback 20

  # 그리드 서치 최적 파라미터 적용
  poetry run python scripts/run_single_backtest.py \\
      --short 20 --long 200 --stop-loss 0.05 --lookback 20

  # EMA 전략만 실행
  poetry run python scripts/run_single_backtest.py \\
      --short 20 --long 200 --stop-loss 0.05 --lookback 20 --ma-type ema
        """,
    )
    parser.add_argument(
        "--short",
        type=int,
        required=True,
        help="단기 이동평균 기간",
    )
    parser.add_argument(
        "--long",
        type=int,
        required=True,
        help="장기 이동평균 기간",
    )
    parser.add_argument(
        "--stop-loss",
        type=float,
        required=True,
        help="손절 비율 (예: 0.10)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        required=True,
        help="최근 저점 탐색 기간",
    )
    parser.add_argument(
        "--ma-type",
        choices=["sma", "ema"],
        default=None,
        help="이동평균 유형 (미지정 시 둘 다 실행)",
    )
    return parser.parse_args()


def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    args = parse_args()

    logger.debug("QQQ 백테스트 실행 시작")
    logger.debug(
        f"파라미터: short={args.short}, long={args.long}, "
        f"stop_loss={args.stop_loss}, lookback={args.lookback}, "
        f"ma_type={args.ma_type or 'sma+ema'}"
    )

    try:
        # 1. 데이터 로딩 및 검증
        df = load_and_validate_data(DEFAULT_DATA_FILE, logger)
        if df is None:
            return 1

        # 2. 이동평균 계산
        df = add_moving_averages(df, args.short, args.long)

        # 3. 전략 파라미터 설정
        params = StrategyParams(
            short_window=args.short,
            long_window=args.long,
            stop_loss_pct=args.stop_loss,
            lookback_for_low=args.lookback,
            initial_capital=DEFAULT_INITIAL_CAPITAL,
        )

        summaries = []

        # 4. SMA 전략 실행
        if args.ma_type is None or args.ma_type == "sma":
            logger.debug("\n" + "=" * 60)
            logger.debug("SMA 전략 백테스트 실행")
            trades_sma, _, summary_sma = run_strategy(df, params, ma_type="sma")
            print_summary(summary_sma, "SMA 전략 결과", logger)
            print_trades(trades_sma, "SMA 전략", logger)
            summaries.append(("SMA", summary_sma))

        # 5. EMA 전략 실행
        if args.ma_type is None or args.ma_type == "ema":
            logger.debug("\n" + "=" * 60)
            logger.debug("EMA 전략 백테스트 실행")
            trades_ema, _, summary_ema = run_strategy(df, params, ma_type="ema")
            print_summary(summary_ema, "EMA 전략 결과", logger)
            print_trades(trades_ema, "EMA 전략", logger)
            summaries.append(("EMA", summary_ema))

        # 6. Buy & Hold 벤치마크 실행
        logger.debug("\n" + "=" * 60)
        logger.debug("Buy & Hold 벤치마크 실행")
        _, summary_bh = run_buy_and_hold(df, initial_capital=DEFAULT_INITIAL_CAPITAL)
        print_summary(summary_bh, "Buy & Hold 결과", logger)
        summaries.append(("Buy & Hold", summary_bh))

        # 7. 전략 비교 요약
        print_comparison_table(summaries, logger)

        return 0

    except DataValidationError as e:
        logger.error(f"데이터 검증 실패: {e}")
        return 1

    except Exception as e:
        logger.error(f"예기치 않은 오류: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
