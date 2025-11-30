"""
버퍼존 전략 파라미터 그리드 탐색 실행 스크립트

버퍼존 전략의 파라미터 조합을 탐색하여 최적 전략을 찾습니다.
"""

import sys
from pathlib import Path

from qbt.backtest import run_grid_search
from qbt.backtest.config import (
    DEFAULT_BUFFER_ZONE_PCT_LIST,
    DEFAULT_DATA_FILE,
    DEFAULT_HOLD_DAYS_LIST,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MA_WINDOW_LIST,
    DEFAULT_RECENT_MONTHS_LIST,
)
from qbt.utils import setup_logger
from qbt.utils.data_loader import load_and_validate_data
from qbt.utils.formatting import Align, TableLogger

# 로거 설정
logger = setup_logger("run_grid_search", level="DEBUG")


def print_summary_stats(results_df) -> None:
    """결과 요약 통계를 출력한다."""
    title_width = 60

    logger.debug("=" * title_width)
    logger.debug("[요약 통계]")
    logger.debug("=" * title_width)

    if results_df.empty:
        logger.debug("결과 없음")
        return

    logger.debug(f"\n총 테스트 조합: {len(results_df)}개")

    logger.debug("\n수익률 통계:")
    logger.debug(
        f"  - 평균: {results_df['total_return_pct'].mean():.2f}%, "
        f"최대: {results_df['total_return_pct'].max():.2f}%, "
        f"최소: {results_df['total_return_pct'].min():.2f}%"
    )

    logger.debug("\nCAGR 통계:")
    logger.debug(f"  - 평균: {results_df['cagr'].mean():.2f}%, 최대: {results_df['cagr'].max():.2f}%")

    logger.debug("\nMDD 통계:")
    logger.debug(f"  - 평균: {results_df['mdd'].mean():.2f}%, 최악: {results_df['mdd'].min():.2f}%")

    # 양수 수익률 비율
    positive_returns = len(results_df[results_df["total_return_pct"] > 0])
    logger.debug(
        f"\n양수 수익률 조합: {positive_returns}/{len(results_df)} ({positive_returns / len(results_df) * 100:.1f}%)"
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
        logger.debug(f"  - ma_window: {DEFAULT_MA_WINDOW_LIST}")
        logger.debug(f"  - buffer_zone_pct: {DEFAULT_BUFFER_ZONE_PCT_LIST}")
        logger.debug(f"  - hold_days: {DEFAULT_HOLD_DAYS_LIST}")
        logger.debug(f"  - recent_months: {DEFAULT_RECENT_MONTHS_LIST}")

        results_df = run_grid_search(
            df=df,
            ma_window_list=DEFAULT_MA_WINDOW_LIST,
            buffer_zone_pct_list=DEFAULT_BUFFER_ZONE_PCT_LIST,
            hold_days_list=DEFAULT_HOLD_DAYS_LIST,
            recent_months_list=DEFAULT_RECENT_MONTHS_LIST,
            initial_capital=DEFAULT_INITIAL_CAPITAL,
        )

        # 3. 상위 결과 출력 (수익률 기준)
        columns = [
            ("순위", 6, Align.RIGHT),
            ("Window", 8, Align.RIGHT),
            ("Buffer%", 10, Align.RIGHT),
            ("Hold일", 8, Align.RIGHT),
            ("Recent월", 10, Align.RIGHT),
            ("수익률", 12, Align.RIGHT),
            ("CAGR", 10, Align.RIGHT),
            ("MDD", 10, Align.RIGHT),
            ("거래수", 8, Align.RIGHT),
            ("승률", 8, Align.RIGHT),
        ]

        top_n = 10
        rows = []
        for rank, (_, row) in enumerate(results_df.head(top_n).iterrows(), start=1):
            rows.append([
                str(rank),
                str(row["ma_window"]),
                f"{row['buffer_zone_pct'] * 100:.1f}%",
                f"{row['hold_days']}일",
                f"{row['recent_months']}월",
                f"{row['total_return_pct']:.2f}%",
                f"{row['cagr']:.2f}%",
                f"{row['mdd']:.2f}%",
                str(row["total_trades"]),
                f"{row['win_rate']:.1f}%",
            ])

        table = TableLogger(columns, logger)
        table.print_table(rows, title=f"[수익률 기준] 상위 {top_n}개 결과")

        # 4. CAGR 기준 정렬 후 출력
        results_by_cagr = results_df.sort_values(by="cagr", ascending=False).reset_index(drop=True)

        rows = []
        for rank, (_, row) in enumerate(results_by_cagr.head(top_n).iterrows(), start=1):
            rows.append([
                str(rank),
                str(row["ma_window"]),
                f"{row['buffer_zone_pct'] * 100:.1f}%",
                f"{row['hold_days']}일",
                f"{row['recent_months']}월",
                f"{row['total_return_pct']:.2f}%",
                f"{row['cagr']:.2f}%",
                f"{row['mdd']:.2f}%",
                str(row["total_trades"]),
                f"{row['win_rate']:.1f}%",
            ])

        table = TableLogger(columns, logger)
        table.print_table(rows, title=f"[CAGR 기준] 상위 {top_n}개 결과")

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
