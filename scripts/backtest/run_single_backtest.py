"""
단일 백테스트 실행 스크립트

이동평균선 교차 전략 백테스트 (SMA/EMA/Buy&Hold)
모든 파라미터는 상수에서 정의됩니다.

실행 명령어:
    poetry run python scripts/backtest/run_single_backtest.py
"""

import logging
import sys

from qbt.backtest import (
    BufferStrategyParams,
    BuyAndHoldParams,
    add_single_moving_average,
    run_buffer_strategy,
    run_buy_and_hold,
)
from qbt.backtest.constants import (
    DEFAULT_BUFFER_ZONE_PCT,
    DEFAULT_HOLD_DAYS,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MA_WINDOW,
    DEFAULT_RECENT_MONTHS,
)
from qbt.common_constants import COL_DATE, QQQ_DATA_PATH
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.formatting import Align, TableLogger

logger = get_logger(__name__)


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


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    logger.debug("버퍼존 전략 백테스트 시작")
    logger.debug(
        f"파라미터: ma_window={DEFAULT_MA_WINDOW}, buffer_zone={DEFAULT_BUFFER_ZONE_PCT}, hold_days={DEFAULT_HOLD_DAYS}, recent_months={DEFAULT_RECENT_MONTHS}"
    )

    # 1. 데이터 로딩
    logger.debug(f"데이터 파일 경로: {QQQ_DATA_PATH}")
    df = load_stock_data(QQQ_DATA_PATH)

    logger.debug("=" * 60)
    logger.debug("데이터 로딩 완료")
    logger.debug(f"총 행 수: {len(df):,}")
    logger.debug(f"기간: {df[COL_DATE].min()} ~ {df[COL_DATE].max()}")
    logger.debug("=" * 60)

    # 2. 이동평균 계산
    df = add_single_moving_average(df, DEFAULT_MA_WINDOW)

    # 3. 전략 파라미터 설정
    params = BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=DEFAULT_MA_WINDOW,
        buffer_zone_pct=DEFAULT_BUFFER_ZONE_PCT,
        hold_days=DEFAULT_HOLD_DAYS,
        recent_months=DEFAULT_RECENT_MONTHS,
    )

    summaries = []

    # 4. 버퍼존 전략 실행
    logger.debug("=" * 60)
    logger.debug("버퍼존 전략 백테스트 실행")
    trades, _, summary = run_buffer_strategy(df, params)
    print_summary(summary, "버퍼존 전략 결과", logger)

    # 거래 내역 출력
    if not trades.empty:
        columns = [
            ("진입일", 12, Align.LEFT),
            ("청산일", 12, Align.LEFT),
            ("진입가", 12, Align.RIGHT),
            ("청산가", 12, Align.RIGHT),
            ("손익률", 14, Align.RIGHT),
            ("사유", 16, Align.RIGHT),
        ]

        max_rows = 10
        rows = []
        for _, trade in trades.tail(max_rows).iterrows():
            rows.append(
                [
                    str(trade["entry_date"]),
                    str(trade["exit_date"]),
                    f"{trade['entry_price']:.2f}",
                    f"{trade['exit_price']:.2f}",
                    f"{trade['pnl_pct'] * 100:+.2f}%",
                    trade["exit_reason"],
                ]
            )

        table = TableLogger(columns, logger)
        table.print_table(rows, title=f"[버퍼존 전략] 거래 내역 (최근 {max_rows}건)")
    else:
        logger.debug("[버퍼존 전략] 거래 내역 없음")

    summaries.append(("버퍼존 전략", summary))

    # 5. Buy & Hold 벤치마크 실행
    logger.debug("Buy & Hold 벤치마크 실행")
    params_bh = BuyAndHoldParams(initial_capital=DEFAULT_INITIAL_CAPITAL)
    _, summary_bh = run_buy_and_hold(df, params=params_bh)
    print_summary(summary_bh, "Buy & Hold 결과", logger)
    summaries.append(("Buy & Hold", summary_bh))

    # 6. 전략 비교 요약
    columns = [
        ("전략", 20, Align.LEFT),
        ("총수익률", 12, Align.RIGHT),
        ("CAGR", 10, Align.RIGHT),
        ("MDD", 10, Align.RIGHT),
        ("거래수", 10, Align.RIGHT),
    ]

    rows = []
    for name, summary in summaries:
        rows.append(
            [
                name,
                f"{summary['total_return_pct']:.2f}%",
                f"{summary['cagr']:.2f}%",
                f"{summary['mdd']:.2f}%",
                str(summary["total_trades"]),
            ]
        )

    table = TableLogger(columns, logger)
    table.print_table(rows, title="[전략 비교 요약]")

    return 0


if __name__ == "__main__":
    sys.exit(main())
