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

# 로거 설정
logger = setup_logger("run_grid_search", level="DEBUG")


def print_top_results(results_df, title: str, top_n: int = 10) -> None:
    """상위 결과를 출력한다."""
    logger.debug("=" * 80)
    logger.debug(f"[{title}] 상위 {top_n}개 결과")
    logger.debug("=" * 80)

    if results_df.empty:
        logger.debug("결과 없음")
        return

    header = (
        f"{'순위':>4} {'MA':>4} {'Short':>6} {'Long':>6} "
        f"{'손절%':>6} {'Lookback':>8} {'수익률':>10} {'CAGR':>8} "
        f"{'MDD':>8} {'거래수':>6} {'승률':>6}"
    )
    logger.debug(header)
    logger.debug("-" * 80)

    for idx, row in results_df.head(top_n).iterrows():
        line = (
            f"{idx + 1:>4} {row['ma_type'].upper():>4} "
            f"{row['short_window']:>6} {row['long_window']:>6} "
            f"{row['stop_loss_pct'] * 100:>5.0f}% {row['lookback_for_low']:>8} "
            f"{row['total_return_pct']:>9.2f}% {row['cagr']:>7.2f}% "
            f"{row['mdd']:>7.2f}% {row['total_trades']:>6} "
            f"{row['win_rate']:>5.1f}%"
        )
        logger.debug(line)

    logger.debug("=" * 80)


def print_summary_stats(results_df) -> None:
    """결과 요약 통계를 출력한다."""
    logger.debug("\n" + "=" * 80)
    logger.debug("[요약 통계]")
    logger.debug("=" * 80)

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

    logger.debug("=" * 80)


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
