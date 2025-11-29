"""
단일 백테스트 실행 스크립트

이동평균선 교차 전략 백테스트 (SMA/EMA/Buy&Hold)
CLI 인자로 파라미터를 지정합니다.
"""

import argparse
import sys

from qbt.backtest import (
    BufferStrategyParams,
    DataValidationError,
    add_single_moving_average,
    run_buffer_strategy,
    run_buy_and_hold,
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
        description="버퍼존 전략 백테스트",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  # 버퍼존만 모드 (유지조건 없음)
  poetry run python scripts/run_single_backtest.py \\
      --buffer-zone 0.01 --hold-days 0 --recent-months 6

  # 버퍼존 + 유지조건 1일
  poetry run python scripts/run_single_backtest.py \\
      --buffer-zone 0.01 --hold-days 1 --recent-months 6

  # 200일 SMA (기본값) 대신 100일 SMA 사용
  poetry run python scripts/run_single_backtest.py \\
      --ma-window 100 --buffer-zone 0.02 --hold-days 2
        """,
    )
    parser.add_argument(
        "--ma-window",
        type=int,
        default=200,
        help="이동평균 기간 (기본값: 200)",
    )
    parser.add_argument(
        "--buffer-zone",
        type=float,
        required=True,
        help="초기 버퍼존 비율 (예: 0.01 = 1%%)",
    )
    parser.add_argument(
        "--hold-days",
        type=int,
        default=1,
        help="초기 유지조건 일수 (0이면 버퍼존만 모드, 기본값: 1)",
    )
    parser.add_argument(
        "--recent-months",
        type=int,
        default=6,
        help="최근 매수 기간 (개월, 기본값: 6)",
    )
    return parser.parse_args()


def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    args = parse_args()

    logger.debug("버퍼존 전략 백테스트 시작")
    logger.debug(
        f"파라미터: ma_window={args.ma_window}, buffer_zone={args.buffer_zone}, "
        f"hold_days={args.hold_days}, recent_months={args.recent_months}"
    )

    try:
        # 1. 데이터 로딩 및 검증
        df = load_and_validate_data(DEFAULT_DATA_FILE, logger)
        if df is None:
            return 1

        # 2. 이동평균 계산
        df = add_single_moving_average(df, args.ma_window)

        # 3. 전략 파라미터 설정
        params = BufferStrategyParams(
            ma_window=args.ma_window,
            buffer_zone_pct=args.buffer_zone,
            hold_days=args.hold_days,
            recent_months=args.recent_months,
            initial_capital=DEFAULT_INITIAL_CAPITAL,
        )

        summaries = []

        # 4. 버퍼존 전략 실행
        logger.debug("=" * 60)
        logger.debug("버퍼존 전략 백테스트 실행")
        trades, _, summary = run_buffer_strategy(df, params)
        print_summary(summary, "버퍼존 전략 결과", logger)
        print_trades(trades, "버퍼존 전략", logger)
        summaries.append(("버퍼존 전략", summary))

        # 5. Buy & Hold 벤치마크 실행
        logger.debug( "=" * 60)
        logger.debug("Buy & Hold 벤치마크 실행")
        _, summary_bh = run_buy_and_hold(df, initial_capital=DEFAULT_INITIAL_CAPITAL)
        print_summary(summary_bh, "Buy & Hold 결과", logger)
        summaries.append(("Buy & Hold", summary_bh))

        # 6. 전략 비교 요약
        print_comparison_table(summaries, logger)

        return 0

    except DataValidationError as e:
        logger.error(f"데이터 검증 실패: {e}")
        return 1

    except ValueError as e:
        logger.error(f"파라미터 검증 실패: {e}")
        return 1

    except Exception as e:
        logger.error(f"예기치 않은 오류: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
