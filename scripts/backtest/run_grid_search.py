"""
버퍼존 전략 파라미터 그리드 탐색 실행 스크립트

버퍼존 전략의 파라미터 조합을 탐색하여 최적 전략을 찾습니다.

실행 명령어:
    poetry run python scripts/backtest/run_grid_search.py
"""

import sys

from qbt.backtest import run_grid_search
from qbt.backtest.constants import (
    COL_GRID_BUFFER_ZONE_PCT,
    COL_GRID_CAGR,
    COL_GRID_DISPLAY_BUFFER_ZONE,
    COL_GRID_DISPLAY_CAGR,
    COL_GRID_DISPLAY_FINAL_CAPITAL,
    COL_GRID_DISPLAY_HOLD_DAYS,
    COL_GRID_DISPLAY_MA_WINDOW,
    COL_GRID_DISPLAY_MDD,
    COL_GRID_DISPLAY_RECENT_MONTHS,
    COL_GRID_DISPLAY_TOTAL_RETURN,
    COL_GRID_DISPLAY_TOTAL_TRADES,
    COL_GRID_DISPLAY_WIN_RATE,
    COL_GRID_HOLD_DAYS,
    COL_GRID_MA_WINDOW,
    COL_GRID_MDD,
    COL_GRID_RECENT_MONTHS,
    COL_GRID_TOTAL_RETURN_PCT,
    COL_GRID_TOTAL_TRADES,
    COL_GRID_WIN_RATE,
    DEFAULT_BUFFER_ZONE_PCT_LIST,
    DEFAULT_HOLD_DAYS_LIST,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MA_WINDOW_LIST,
    DEFAULT_RECENT_MONTHS_LIST,
    GRID_COLUMN_MAPPING,
)
from qbt.common_constants import COL_DATE, GRID_RESULTS_PATH, QQQ_DATA_PATH
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.formatting import Align, TableLogger

logger = get_logger(__name__)


def print_summary_stats(results_df) -> None:
    """결과 요약 통계를 출력한다."""
    title_width = 60

    logger.debug("=" * title_width)
    logger.debug("[요약 통계]")
    logger.debug("=" * title_width)

    if results_df.empty:
        logger.debug("결과 없음")
        return

    logger.debug(f"총 테스트 조합: {len(results_df)}개")

    logger.debug(
        "수익률 통계:"
        f"  - 평균: {results_df[COL_GRID_TOTAL_RETURN_PCT].mean():.2f}%, "
        f"최대: {results_df[COL_GRID_TOTAL_RETURN_PCT].max():.2f}%, "
        f"최소: {results_df[COL_GRID_TOTAL_RETURN_PCT].min():.2f}%"
    )
    logger.debug(
        f"CAGR 통계: 평균: {results_df[COL_GRID_CAGR].mean():.2f}%, 최대: {results_df[COL_GRID_CAGR].max():.2f}%"
    )
    logger.debug(f"MDD 통계: 평균: {results_df[COL_GRID_MDD].mean():.2f}%, 최악: {results_df[COL_GRID_MDD].min():.2f}%")

    # 양수 수익률 비율
    positive_returns = len(results_df[results_df[COL_GRID_TOTAL_RETURN_PCT] > 0])
    logger.debug(
        f"양수 수익률 조합: {positive_returns}/{len(results_df)} ({positive_returns / len(results_df) * 100:.1f}%)"
    )

    logger.debug("=" * title_width)


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    logger.debug("QQQ 파라미터 그리드 탐색 시작")

    # 1. 데이터 로딩
    logger.debug(f"데이터 파일 경로: {QQQ_DATA_PATH}")
    df = load_stock_data(QQQ_DATA_PATH)

    logger.debug("=" * 60)
    logger.debug("데이터 로딩 완료")
    logger.debug(f"총 행 수: {len(df):,}")
    logger.debug(f"기간: {df[COL_DATE].min()} ~ {df[COL_DATE].max()}")
    logger.debug("=" * 60)

    # 2. 그리드 탐색 실행
    logger.debug("그리드 탐색 파라미터:")
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

    # 3. CAGR 기준 정렬
    results_df = results_df.sort_values(by=COL_GRID_CAGR, ascending=False).reset_index(drop=True)

    # 4. 상위 결과 출력
    columns = [
        ("순위", 6, Align.RIGHT),
        (COL_GRID_DISPLAY_MA_WINDOW, 10, Align.RIGHT),
        (COL_GRID_DISPLAY_BUFFER_ZONE, 10, Align.RIGHT),
        (COL_GRID_DISPLAY_HOLD_DAYS, 8, Align.RIGHT),
        (COL_GRID_DISPLAY_RECENT_MONTHS, 10, Align.RIGHT),
        (COL_GRID_DISPLAY_TOTAL_RETURN, 12, Align.RIGHT),
        (COL_GRID_DISPLAY_CAGR, 10, Align.RIGHT),
        (COL_GRID_DISPLAY_MDD, 10, Align.RIGHT),
        (COL_GRID_DISPLAY_TOTAL_TRADES, 8, Align.RIGHT),
        (COL_GRID_DISPLAY_WIN_RATE, 8, Align.RIGHT),
    ]

    top_n = 10
    rows = []
    for rank, (_, row) in enumerate(results_df.head(top_n).iterrows(), start=1):
        rows.append(
            [
                str(rank),
                str(row[COL_GRID_MA_WINDOW]),
                f"{row[COL_GRID_BUFFER_ZONE_PCT] * 100:.1f}%",
                f"{row[COL_GRID_HOLD_DAYS]}일",
                f"{row[COL_GRID_RECENT_MONTHS]}월",
                f"{row[COL_GRID_TOTAL_RETURN_PCT]:.2f}%",
                f"{row[COL_GRID_CAGR]:.2f}%",
                f"{row[COL_GRID_MDD]:.2f}%",
                str(row[COL_GRID_TOTAL_TRADES]),
                f"{row[COL_GRID_WIN_RATE]:.1f}%",
            ]
        )

    table = TableLogger(columns, logger)
    table.print_table(rows, title=f"상위 {top_n}개 결과 (CAGR 기준)")

    # 5. 요약 통계 출력
    print_summary_stats(results_df)

    # 6. 결과 저장
    GRID_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)

    # CSV 저장용 DataFrame 준비 (컬럼명 한글화 + 소수점 제한)
    results_df_export = results_df.rename(columns=GRID_COLUMN_MAPPING)
    results_df_export = results_df_export.round(
        {
            COL_GRID_DISPLAY_BUFFER_ZONE: 4,  # 0.0500
            COL_GRID_DISPLAY_TOTAL_RETURN: 2,  # 1551.43
            COL_GRID_DISPLAY_CAGR: 2,  # 11.05
            COL_GRID_DISPLAY_MDD: 2,  # -42.83
            COL_GRID_DISPLAY_WIN_RATE: 2,  # 80.00
            COL_GRID_DISPLAY_FINAL_CAPITAL: 2,  # 165143072.86
        }
    )

    results_df_export.to_csv(GRID_RESULTS_PATH, index=False)
    logger.debug(f"결과 저장 완료: {GRID_RESULTS_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
