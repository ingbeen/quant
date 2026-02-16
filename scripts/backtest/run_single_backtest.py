"""
단일 백테스트 실행 스크립트

이동평균선 교차 전략 백테스트 (SMA/EMA/Buy&Hold)
파라미터 우선순위: OVERRIDE 상수 → grid_results.csv 최적값 → DEFAULT 상수

실행 명령어:
    poetry run python scripts/backtest/run_single_backtest.py
"""

import logging
import sys
from collections.abc import Mapping

from qbt.backtest import (
    BufferStrategyParams,
    BuyAndHoldParams,
    add_single_moving_average,
    load_best_grid_params,
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
from qbt.common_constants import COL_DATE, GRID_RESULTS_PATH, QQQ_DATA_PATH, TQQQ_SYNTHETIC_DATA_PATH
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.formatting import Align, TableLogger

logger = get_logger(__name__)

# ============================================================
# 파라미터 오버라이드 (None = grid_results.csv 최적값 사용, 값 설정 = 수동)
# 폴백 체인: OVERRIDE → grid_results.csv 최적값 → DEFAULT
# ============================================================
OVERRIDE_MA_WINDOW: int | None = None
OVERRIDE_BUFFER_ZONE_PCT: float | None = None
OVERRIDE_HOLD_DAYS: int | None = None
OVERRIDE_RECENT_MONTHS: int | None = None


def print_summary(summary: Mapping[str, object], title: str, logger: logging.Logger) -> None:
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
    # 1. 파라미터 결정 (폴백 체인: OVERRIDE → grid_best → DEFAULT)
    grid_params = load_best_grid_params(GRID_RESULTS_PATH)

    if grid_params is not None:
        logger.debug(f"grid_results.csv 최적값 로드 완료: {GRID_RESULTS_PATH}")
    else:
        logger.debug("grid_results.csv 없음, DEFAULT 상수 사용")

    # 1-1. ma_window
    if OVERRIDE_MA_WINDOW is not None:
        ma_window = OVERRIDE_MA_WINDOW
        ma_window_source = "OVERRIDE"
    elif grid_params is not None:
        ma_window = grid_params["ma_window"]
        ma_window_source = "grid_best"
    else:
        ma_window = DEFAULT_MA_WINDOW
        ma_window_source = "DEFAULT"

    # 1-2. buffer_zone_pct
    if OVERRIDE_BUFFER_ZONE_PCT is not None:
        buffer_zone_pct = OVERRIDE_BUFFER_ZONE_PCT
        bz_source = "OVERRIDE"
    elif grid_params is not None:
        buffer_zone_pct = grid_params["buffer_zone_pct"]
        bz_source = "grid_best"
    else:
        buffer_zone_pct = DEFAULT_BUFFER_ZONE_PCT
        bz_source = "DEFAULT"

    # 1-3. hold_days
    if OVERRIDE_HOLD_DAYS is not None:
        hold_days = OVERRIDE_HOLD_DAYS
        hd_source = "OVERRIDE"
    elif grid_params is not None:
        hold_days = grid_params["hold_days"]
        hd_source = "grid_best"
    else:
        hold_days = DEFAULT_HOLD_DAYS
        hd_source = "DEFAULT"

    # 1-4. recent_months
    if OVERRIDE_RECENT_MONTHS is not None:
        recent_months = OVERRIDE_RECENT_MONTHS
        rm_source = "OVERRIDE"
    elif grid_params is not None:
        recent_months = grid_params["recent_months"]
        rm_source = "grid_best"
    else:
        recent_months = DEFAULT_RECENT_MONTHS
        rm_source = "DEFAULT"

    logger.debug("버퍼존 전략 백테스트 시작")
    logger.debug(
        f"파라미터: ma_window={ma_window} ({ma_window_source}), "
        f"buffer_zone={buffer_zone_pct} ({bz_source}), "
        f"hold_days={hold_days} ({hd_source}), "
        f"recent_months={recent_months} ({rm_source})"
    )

    # 2. 데이터 로딩 (QQQ: 시그널, TQQQ: 매매)
    logger.debug(f"시그널 데이터: {QQQ_DATA_PATH}")
    logger.debug(f"매매 데이터: {TQQQ_SYNTHETIC_DATA_PATH}")
    signal_df = load_stock_data(QQQ_DATA_PATH)
    trade_df = load_stock_data(TQQQ_SYNTHETIC_DATA_PATH)

    logger.debug("=" * 60)
    logger.debug("데이터 로딩 완료")
    logger.debug(f"시그널(QQQ) 행 수: {len(signal_df):,}, 기간: {signal_df[COL_DATE].min()} ~ {signal_df[COL_DATE].max()}")
    logger.debug(f"매매(TQQQ) 행 수: {len(trade_df):,}, 기간: {trade_df[COL_DATE].min()} ~ {trade_df[COL_DATE].max()}")
    logger.debug("=" * 60)

    # 3. 날짜 기준 정렬 (겹치는 기간만 사용)
    common_dates = set(signal_df[COL_DATE]) & set(trade_df[COL_DATE])
    signal_df = signal_df[signal_df[COL_DATE].isin(common_dates)].reset_index(drop=True)
    trade_df = trade_df[trade_df[COL_DATE].isin(common_dates)].reset_index(drop=True)
    logger.debug(f"공통 기간: {len(signal_df):,}행")

    # 4. 이동평균 계산 (signal_df에만)
    signal_df = add_single_moving_average(signal_df, ma_window)

    # 5. 전략 파라미터 설정
    params = BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=ma_window,
        buffer_zone_pct=buffer_zone_pct,
        hold_days=hold_days,
        recent_months=recent_months,
    )

    summaries = []

    # 6. 버퍼존 전략 실행 (QQQ 시그널 + TQQQ 매매)
    logger.debug("=" * 60)
    logger.debug("버퍼존 전략 백테스트 실행 (QQQ 시그널 + TQQQ 매매)")
    trades, _, summary = run_buffer_strategy(signal_df, trade_df, params)
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

    # 7. Buy & Hold 벤치마크 실행 (TQQQ 기준)
    logger.debug("Buy & Hold 벤치마크 실행 (TQQQ)")
    params_bh = BuyAndHoldParams(initial_capital=DEFAULT_INITIAL_CAPITAL)
    _, summary_bh = run_buy_and_hold(signal_df, trade_df, params=params_bh)
    print_summary(summary_bh, "Buy & Hold 결과", logger)
    summaries.append(("Buy & Hold", summary_bh))

    # 8. 전략 비교 요약
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
