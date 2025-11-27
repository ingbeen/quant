"""
QQQ 파라미터 그리드 탐색 실행 스크립트

파라미터 조합을 탐색하여 최적 전략을 찾습니다.
"""

import sys
from pathlib import Path

from qbt.backtest import run_grid_search
from qbt.backtest.config import (
    DEFAULT_DATA_FILE,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_LONG_WINDOW_LIST,
    DEFAULT_LOOKBACK_FOR_LOW_LIST,
    DEFAULT_SHORT_WINDOW_LIST,
    DEFAULT_STOP_LOSS_PCT_LIST,
)
from qbt.utils import load_and_validate_data, setup_logger
from qbt.utils.cli import format_cell

# 로거 설정
logger = setup_logger("run_grid_search", level="DEBUG")


def print_top_results(results_df, title: str, top_n: int = 10) -> None:
    """상위 결과를 출력한다."""
    # 컬럼 폭 정의
    col_rank = 6  # "순위" (4칸)
    col_ma = 6  # "MA" (2칸)
    col_short = 8  # "Short" (5칸)
    col_long = 8  # "Long" (4칸)
    col_stop = 8  # "손절%" (6칸)
    col_lookback = 10  # "Lookback" (8칸)
    col_return = 12  # "수익률" (6칸)
    col_cagr = 10  # "CAGR" (4칸)
    col_mdd = 10  # "MDD" (6칸)
    col_trades = 8  # "거래수" (6칸)
    col_winrate = 8  # "승률" (4칸)

    total_width = (
        col_rank
        + col_ma
        + col_short
        + col_long
        + col_stop
        + col_lookback
        + col_return
        + col_cagr
        + col_mdd
        + col_trades
        + col_winrate
    )

    logger.debug("=" * total_width)
    logger.debug(f"[{title}] 상위 {top_n}개 결과")
    logger.debug("=" * total_width)

    if results_df.empty:
        logger.debug("결과 없음")
        return

    # 헤더
    header = (
        format_cell("순위", col_rank, "right")
        + format_cell("MA", col_ma, "right")
        + format_cell("Short", col_short, "right")
        + format_cell("Long", col_long, "right")
        + format_cell("손절%", col_stop, "right")
        + format_cell("Lookback", col_lookback, "right")
        + format_cell("수익률", col_return, "right")
        + format_cell("CAGR", col_cagr, "right")
        + format_cell("MDD", col_mdd, "right")
        + format_cell("거래수", col_trades, "right")
        + format_cell("승률", col_winrate, "right")
    )
    logger.debug(header)
    logger.debug("-" * total_width)

    # 데이터 행
    for idx, row in results_df.head(top_n).iterrows():
        rank_str = str(idx + 1)
        ma_str = row["ma_type"].upper()
        short_str = str(row["short_window"])
        long_str = str(row["long_window"])
        stop_str = f"{row['stop_loss_pct'] * 100:.0f}%"
        lookback_str = str(row["lookback_for_low"])
        return_str = f"{row['total_return_pct']:.2f}%"
        cagr_str = f"{row['cagr']:.2f}%"
        mdd_str = f"{row['mdd']:.2f}%"
        trades_str = str(row["total_trades"])
        winrate_str = f"{row['win_rate']:.1f}%"

        line = (
            format_cell(rank_str, col_rank, "right")
            + format_cell(ma_str, col_ma, "right")
            + format_cell(short_str, col_short, "right")
            + format_cell(long_str, col_long, "right")
            + format_cell(stop_str, col_stop, "right")
            + format_cell(lookback_str, col_lookback, "right")
            + format_cell(return_str, col_return, "right")
            + format_cell(cagr_str, col_cagr, "right")
            + format_cell(mdd_str, col_mdd, "right")
            + format_cell(trades_str, col_trades, "right")
            + format_cell(winrate_str, col_winrate, "right")
        )
        logger.debug(line)

    logger.debug("=" * total_width)


def print_summary_stats(results_df) -> None:
    """결과 요약 통계를 출력한다."""
    # "요약 통계" = 8칸
    title_width = 60

    logger.debug("\n" + "=" * title_width)
    logger.debug("[요약 통계]")
    logger.debug("=" * title_width)

    if results_df.empty:
        logger.debug("결과 없음")
        return

    # SMA vs EMA 비교
    sma_results = results_df[results_df["ma_type"] == "sma"]
    ema_results = results_df[results_df["ma_type"] == "ema"]

    logger.debug(f"\n총 테스트 조합: {len(results_df)}개")
    logger.debug(f"  - SMA: {len(sma_results)}개")
    logger.debug(f"  - EMA: {len(ema_results)}개")

    logger.debug("\n수익률 통계:")
    logger.debug(
        f"  - 전체 평균: {results_df['total_return_pct'].mean():.2f}%, "
        f"최대: {results_df['total_return_pct'].max():.2f}%, "
        f"최소: {results_df['total_return_pct'].min():.2f}%"
    )
    logger.debug(
        f"  - SMA 평균: {sma_results['total_return_pct'].mean():.2f}%, "
        f"최대: {sma_results['total_return_pct'].max():.2f}%"
    )
    logger.debug(
        f"  - EMA 평균: {ema_results['total_return_pct'].mean():.2f}%, "
        f"최대: {ema_results['total_return_pct'].max():.2f}%"
    )

    logger.debug("\nCAGR 통계:")
    logger.debug(
        f"  - 전체 평균: {results_df['cagr'].mean():.2f}%, "
        f"최대: {results_df['cagr'].max():.2f}%"
    )

    logger.debug("\nMDD 통계:")
    logger.debug(
        f"  - 전체 평균: {results_df['mdd'].mean():.2f}%, "
        f"최악: {results_df['mdd'].min():.2f}%"
    )

    # 양수 수익률 비율
    positive_returns = len(results_df[results_df["total_return_pct"] > 0])
    logger.debug(
        f"\n양수 수익률 조합: {positive_returns}/{len(results_df)} "
        f"({positive_returns / len(results_df) * 100:.1f}%)"
    )

    logger.debug("=" * title_width)


def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    logger.debug("QQQ 파라미터 그리드 탐색 시작")

    try:
        # 1. 데이터 로딩 및 검증
        df = load_and_validate_data(DEFAULT_DATA_FILE, logger)
        if df is None:
            return 1

        # 2. 그리드 탐색 실행
        logger.debug("\n그리드 탐색 파라미터:")
        logger.debug(f"  - short_window: {DEFAULT_SHORT_WINDOW_LIST}")
        logger.debug(f"  - long_window: {DEFAULT_LONG_WINDOW_LIST}")
        logger.debug(f"  - stop_loss_pct: {DEFAULT_STOP_LOSS_PCT_LIST}")
        logger.debug(f"  - lookback_for_low: {DEFAULT_LOOKBACK_FOR_LOW_LIST}")

        results_df = run_grid_search(
            df=df,
            short_window_list=DEFAULT_SHORT_WINDOW_LIST,
            long_window_list=DEFAULT_LONG_WINDOW_LIST,
            stop_loss_pct_list=DEFAULT_STOP_LOSS_PCT_LIST,
            lookback_for_low_list=DEFAULT_LOOKBACK_FOR_LOW_LIST,
            initial_capital=DEFAULT_INITIAL_CAPITAL,
        )

        # 3. 상위 결과 출력
        print_top_results(results_df, "수익률 기준", top_n=10)

        # 4. CAGR 기준 정렬 후 출력
        results_by_cagr = results_df.sort_values(
            by="cagr", ascending=False
        ).reset_index(drop=True)
        print_top_results(results_by_cagr, "CAGR 기준", top_n=10)

        # 5. 요약 통계 출력
        print_summary_stats(results_df)

        # 6. 결과 저장
        output_path = Path("data/raw/grid_results.csv")
        results_df.to_csv(output_path, index=False)
        logger.debug(f"\n결과 저장 완료: {output_path}")

        return 0

    except Exception as e:
        logger.error(f"예기치 않은 오류: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
