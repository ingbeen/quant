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
    load_data,
    run_buy_and_hold,
    run_strategy,
    validate_data,
)
from qbt.backtest.config import DEFAULT_DATA_FILE, DEFAULT_INITIAL_CAPITAL
from qbt.utils import setup_logger

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


def print_summary(summary: dict, title: str) -> None:
    """요약 지표를 출력한다."""
    logger.debug("=" * 60)
    logger.debug(f"[{title}]")
    logger.debug(f"  기간: {summary.get('start_date')} ~ {summary.get('end_date')}")
    logger.debug(f"  초기 자본: {summary['initial_capital']:,.0f}원")
    logger.debug(f"  최종 자본: {summary['final_capital']:,.0f}원")
    logger.debug(f"  총 수익률: {summary['total_return_pct']:.2f}%")
    logger.debug(f"  CAGR: {summary['cagr']:.2f}%")
    logger.debug(f"  MDD: {summary['mdd']:.2f}%")
    logger.debug(f"  총 거래 수: {summary['total_trades']}")
    if "win_rate" in summary:
        logger.debug(f"  승률: {summary['win_rate']:.1f}%")
        logger.debug(f"  승/패: {summary['winning_trades']}/{summary['losing_trades']}")
    logger.debug("=" * 60)


def print_trades(trades_df, title: str, max_rows: int = 10) -> None:
    """거래 내역을 출력한다."""
    if trades_df.empty:
        logger.debug(f"[{title}] 거래 내역 없음")
        return

    logger.debug(f"[{title}] 거래 내역 (최근 {max_rows}건):")
    for _, trade in trades_df.tail(max_rows).iterrows():
        logger.debug(
            f"  {trade['entry_date']} -> {trade['exit_date']} | "
            f"진입: {trade['entry_price']:.2f} | "
            f"청산: {trade['exit_price']:.2f} | "
            f"손익률: {trade['pnl_pct'] * 100:+.2f}% | "
            f"사유: {trade['exit_reason']}"
        )


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
        # 1. 데이터 로딩
        logger.debug(f"데이터 파일 경로: {DEFAULT_DATA_FILE}")
        df = load_data(DEFAULT_DATA_FILE)

        # 2. 데이터 유효성 검증
        validate_data(df)

        # 3. 데이터 요약 정보 출력
        logger.debug("=" * 60)
        logger.debug("데이터 로딩 및 검증 완료")
        logger.debug(f"총 행 수: {len(df):,}")
        logger.debug(f"기간: {df['Date'].min()} ~ {df['Date'].max()}")
        logger.debug("=" * 60)

        # 4. 이동평균 계산
        df = add_moving_averages(df, args.short, args.long)

        # 5. 전략 파라미터 설정
        params = StrategyParams(
            short_window=args.short,
            long_window=args.long,
            stop_loss_pct=args.stop_loss,
            lookback_for_low=args.lookback,
            initial_capital=DEFAULT_INITIAL_CAPITAL,
        )

        summaries = []

        # 6. SMA 전략 실행
        if args.ma_type is None or args.ma_type == "sma":
            logger.debug("\n" + "=" * 60)
            logger.debug("SMA 전략 백테스트 실행")
            trades_sma, _, summary_sma = run_strategy(df, params, ma_type="sma")
            print_summary(summary_sma, "SMA 전략 결과")
            print_trades(trades_sma, "SMA 전략")
            summaries.append(("SMA", summary_sma))

        # 7. EMA 전략 실행
        if args.ma_type is None or args.ma_type == "ema":
            logger.debug("\n" + "=" * 60)
            logger.debug("EMA 전략 백테스트 실행")
            trades_ema, _, summary_ema = run_strategy(df, params, ma_type="ema")
            print_summary(summary_ema, "EMA 전략 결과")
            print_trades(trades_ema, "EMA 전략")
            summaries.append(("EMA", summary_ema))

        # 8. Buy & Hold 벤치마크 실행
        logger.debug("\n" + "=" * 60)
        logger.debug("Buy & Hold 벤치마크 실행")
        _, summary_bh = run_buy_and_hold(df, initial_capital=DEFAULT_INITIAL_CAPITAL)
        print_summary(summary_bh, "Buy & Hold 결과")
        summaries.append(("Buy & Hold", summary_bh))

        # 9. 전략 비교 요약
        logger.debug("\n" + "=" * 60)
        logger.debug("[전략 비교 요약]")
        logger.debug(
            f"  {'전략':<15} {'총수익률':>10} {'CAGR':>10} {'MDD':>10} {'거래수':>8}"
        )
        logger.debug("-" * 60)
        for name, summary in summaries:
            logger.debug(
                f"  {name:<15} {summary['total_return_pct']:>9.2f}% "
                f"{summary['cagr']:>9.2f}% {summary['mdd']:>9.2f}% "
                f"{summary['total_trades']:>8}"
            )
        logger.debug("=" * 60)

        return 0

    except FileNotFoundError as e:
        logger.error(f"파일 오류: {e}")
        return 1

    except DataValidationError as e:
        logger.error(f"데이터 검증 실패: {e}")
        return 1

    except Exception as e:
        logger.error(f"예기치 않은 오류: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
