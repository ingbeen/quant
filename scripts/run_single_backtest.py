"""
단일 백테스트 실행 스크립트

이동평균선 교차 전략 백테스트 (SMA/EMA/Buy&Hold)
CLI 인자로 파라미터를 지정합니다.
"""

import argparse
import logging
import sys

import pandas as pd

from qbt.backtest import (
    BufferStrategyParams,
    DataValidationError,
    add_single_moving_average,
    run_buffer_strategy,
    run_buy_and_hold,
)
from qbt.backtest.config import DEFAULT_DATA_FILE, DEFAULT_INITIAL_CAPITAL
from qbt.utils import setup_logger
from qbt.utils.data_loader import load_and_validate_data
from qbt.utils.formatting import Align, format_row

# 로거 설정
logger = setup_logger("run_single_backtest", level="DEBUG")


def print_summary(summary: dict, title: str, logger: logging.Logger) -> None:
    """
    요약 지표를 출력한다.

    Args:
        summary: 요약 지표 딕셔너리
        title: 출력 제목
        logger: 로거 인스턴스
    """
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
        if "winning_trades" in summary:
            logger.debug(f"  승/패: {summary['winning_trades']}/{summary['losing_trades']}")
    logger.debug("=" * 60)


def print_trades(trades_df: pd.DataFrame, title: str, logger: logging.Logger, max_rows: int = 10) -> None:
    """
    거래 내역을 출력한다.

    Args:
        trades_df: 거래 내역 DataFrame
        title: 출력 제목
        logger: 로거 인스턴스
        max_rows: 최대 출력 행 수
    """
    if trades_df.empty:
        logger.debug(f"[{title}] 거래 내역 없음")
        return

    # 컬럼 폭 정의 (터미널 칸 수 기준)
    col_entry_date = 12  # "진입일" (6칸) + YYYY-MM-DD
    col_exit_date = 12  # "청산일" (6칸) + YYYY-MM-DD
    col_entry_price = 12  # "진입가" (6칸) + 숫자
    col_exit_price = 12  # "청산가" (6칸) + 숫자
    col_pnl = 14  # "손익률" (6칸) + 숫자 + %
    col_reason = 16  # "사유" (4칸) + 텍스트

    # 전체 테이블 폭 계산 (들여쓰기 2칸 + 컬럼들)
    total_width = 2 + col_entry_date + col_exit_date + col_entry_price + col_exit_price + col_pnl + col_reason

    logger.debug("=" * total_width)
    logger.debug(f"[{title}] 거래 내역 (최근 {max_rows}건)")

    # 헤더 출력
    header = format_row(
        [
            ("진입일", col_entry_date, Align.LEFT),
            ("청산일", col_exit_date, Align.LEFT),
            ("진입가", col_entry_price, Align.RIGHT),
            ("청산가", col_exit_price, Align.RIGHT),
            ("손익률", col_pnl, Align.RIGHT),
            ("사유", col_reason, Align.RIGHT),
        ]
    )
    logger.debug(header)
    logger.debug("-" * total_width)

    # 데이터 행 출력
    for _, trade in trades_df.tail(max_rows).iterrows():
        entry_price_str = f"{trade['entry_price']:.2f}"
        exit_price_str = f"{trade['exit_price']:.2f}"
        pnl_str = f"{trade['pnl_pct'] * 100:+.2f}%"

        row = format_row(
            [
                (str(trade["entry_date"]), col_entry_date, Align.LEFT),
                (str(trade["exit_date"]), col_exit_date, Align.LEFT),
                (entry_price_str, col_entry_price, Align.RIGHT),
                (exit_price_str, col_exit_price, Align.RIGHT),
                (pnl_str, col_pnl, Align.RIGHT),
                (trade["exit_reason"], col_reason, Align.RIGHT),
            ]
        )
        logger.debug(row)

    logger.debug("=" * total_width)


def print_comparison_table(summaries: list[tuple[str, dict]], logger: logging.Logger) -> None:
    """
    전략 비교 테이블을 출력한다.

    Args:
        summaries: [(전략명, summary_dict), ...] 리스트
        logger: 로거 인스턴스
    """
    # 컬럼 폭 정의 (터미널 칸 수 기준)
    col_strategy = 20  # "전략" (4칸) + 여유
    col_return = 12  # "총수익률" (8칸) + 숫자
    col_cagr = 10  # "CAGR" (4칸) + 숫자
    col_mdd = 10  # "MDD" (6칸) + 숫자
    col_trades = 10  # "거래수" (6칸) + 숫자

    # 전체 테이블 폭 계산 (들여쓰기 2칸 + 컬럼들)
    total_width = 2 + col_strategy + col_return + col_cagr + col_mdd + col_trades

    logger.debug("=" * total_width)
    logger.debug("[전략 비교 요약]")

    # 헤더 출력
    header = format_row(
        [
            ("전략", col_strategy, Align.LEFT),
            ("총수익률", col_return, Align.RIGHT),
            ("CAGR", col_cagr, Align.RIGHT),
            ("MDD", col_mdd, Align.RIGHT),
            ("거래수", col_trades, Align.RIGHT),
        ]
    )
    logger.debug(header)
    logger.debug("-" * total_width)

    # 데이터 행 출력
    for name, summary in summaries:
        return_str = f"{summary['total_return_pct']:.2f}%"
        cagr_str = f"{summary['cagr']:.2f}%"
        mdd_str = f"{summary['mdd']:.2f}%"
        trades_str = str(summary["total_trades"])

        row = format_row(
            [
                (name, col_strategy, Align.LEFT),
                (return_str, col_return, Align.RIGHT),
                (cagr_str, col_cagr, Align.RIGHT),
                (mdd_str, col_mdd, Align.RIGHT),
                (trades_str, col_trades, Align.RIGHT),
            ]
        )
        logger.debug(row)

    logger.debug("=" * total_width)


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
        logger.debug("=" * 60)
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
