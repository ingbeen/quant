"""
QQQ 워킹 포워드 테스트 실행 스크립트

과거 기간에서 최적 파라미터를 선택하고, 다음 기간에 적용합니다.
"""

import argparse
import sys

from qbt.backtest import run_buy_and_hold, run_walkforward
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
logger = setup_logger("run_walkforward", level="DEBUG")


def parse_args():
    """CLI 인자를 파싱한다."""
    parser = argparse.ArgumentParser(
        description="워킹 포워드 테스트 실행",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 기본 설정 (5년 학습, 1년 테스트, CAGR 기준)
  poetry run python scripts/run_walkforward.py --train 5 --test 1 --metric cagr

  # 3년 학습, 1년 테스트, MDD 기준 최적화
  poetry run python scripts/run_walkforward.py --train 3 --test 1 --metric mdd
        """,
    )

    parser.add_argument(
        "--train",
        type=int,
        required=True,
        help="학습 기간 (년, 예: 5)",
    )
    parser.add_argument(
        "--test",
        type=int,
        required=True,
        help="테스트 기간 (년, 예: 1)",
    )
    parser.add_argument(
        "--metric",
        choices=["cagr", "total_return_pct", "mdd"],
        required=True,
        help="최적 파라미터 선택 기준",
    )

    return parser.parse_args()


def print_window_results(results_df) -> None:
    """구간별 결과를 출력한다."""
    # 컬럼 폭 정의
    col_window = 8  # "윈도우" (6칸)
    col_train = 26  # "Train 기간" (20칸)
    col_test = 26  # "Test 기간" (18칸)
    col_ma = 6  # "MA" (2칸)
    col_short = 8  # "Short" (5칸)
    col_long = 8  # "Long" (4칸)
    col_return = 14  # "Test수익률" (20칸)
    col_mdd = 14  # "Test MDD" (16칸)

    total_width = (
        col_window
        + col_train
        + col_test
        + col_ma
        + col_short
        + col_long
        + col_return
        + col_mdd
    )

    logger.debug("=" * total_width)
    logger.debug("[구간별 워킹 포워드 결과]")
    logger.debug("=" * total_width)

    if results_df.empty:
        logger.debug("결과 없음")
        return

    # 헤더
    header = (
        format_cell("윈도우", col_window, "right")
        + format_cell("Train 기간", col_train, "right")
        + format_cell("Test 기간", col_test, "right")
        + format_cell("MA", col_ma, "right")
        + format_cell("Short", col_short, "right")
        + format_cell("Long", col_long, "right")
        + format_cell("Test수익률", col_return, "right")
        + format_cell("Test MDD", col_mdd, "right")
    )
    logger.debug(header)
    logger.debug("-" * total_width)

    # 데이터 행
    for _, row in results_df.iterrows():
        window_str = str(row["window_idx"])
        train_period = f"{row['train_start']} ~ {row['train_end']}"
        test_period = f"{row['test_start']} ~ {row['test_end']}"
        ma_str = row["best_ma_type"].upper()
        short_str = str(row["best_short_window"])
        long_str = str(row["best_long_window"])
        return_str = f"{row['test_return_pct']:.2f}%"
        mdd_str = f"{row['test_mdd']:.2f}%"

        line = (
            format_cell(window_str, col_window, "right")
            + format_cell(train_period, col_train, "right")
            + format_cell(test_period, col_test, "right")
            + format_cell(ma_str, col_ma, "right")
            + format_cell(short_str, col_short, "right")
            + format_cell(long_str, col_long, "right")
            + format_cell(return_str, col_return, "right")
            + format_cell(mdd_str, col_mdd, "right")
        )
        logger.debug(line)

    logger.debug("=" * total_width)


def print_summary(wf_summary: dict, bh_summary: dict) -> None:
    """요약 지표를 출력한다."""
    logger.debug("=" * 60)
    logger.debug("[전체 요약]")
    logger.debug("=" * 60)

    logger.debug("\n워킹 포워드 테스트:")
    logger.debug(f"  - 총 윈도우: {wf_summary.get('total_windows', 0)}개")
    logger.debug(f"  - 학습 기간: {wf_summary.get('train_years', 0)}년")
    logger.debug(f"  - 테스트 기간: {wf_summary.get('test_years', 0)}년")
    logger.debug(f"  - 선택 기준: {wf_summary.get('selection_metric', 'N/A')}")
    logger.debug(f"  - 초기 자본: {wf_summary['initial_capital']:,.0f}원")
    logger.debug(f"  - 최종 자본: {wf_summary['final_capital']:,.0f}원")
    logger.debug(f"  - 총 수익률: {wf_summary['total_return_pct']:.2f}%")
    logger.debug(f"  - CAGR: {wf_summary['cagr']:.2f}%")
    logger.debug(f"  - MDD: {wf_summary['mdd']:.2f}%")
    if "avg_test_return_pct" in wf_summary:
        logger.debug(f"  - 평균 Test 수익률: {wf_summary['avg_test_return_pct']:.2f}%")

    logger.debug("\nBuy & Hold 벤치마크:")
    logger.debug(f"  - 초기 자본: {bh_summary['initial_capital']:,.0f}원")
    logger.debug(f"  - 최종 자본: {bh_summary['final_capital']:,.0f}원")
    logger.debug(f"  - 총 수익률: {bh_summary['total_return_pct']:.2f}%")
    logger.debug(f"  - CAGR: {bh_summary['cagr']:.2f}%")
    logger.debug(f"  - MDD: {bh_summary['mdd']:.2f}%")

    logger.debug("\n비교:")
    return_diff = wf_summary["total_return_pct"] - bh_summary["total_return_pct"]
    cagr_diff = wf_summary["cagr"] - bh_summary["cagr"]
    logger.debug(f"  - 수익률 차이: {return_diff:+.2f}%p")
    logger.debug(f"  - CAGR 차이: {cagr_diff:+.2f}%p")
    logger.debug("=" * 60)


def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    args = parse_args()

    logger.debug(
        f"워킹 포워드 테스트 시작: train={args.train}년, test={args.test}년, "
        f"metric={args.metric}"
    )

    try:
        # 1. 데이터 로딩 및 검증
        df = load_and_validate_data(DEFAULT_DATA_FILE, logger)
        if df is None:
            return 1

        # 2. 워킹 포워드 테스트 실행
        logger.debug("\n그리드 탐색 파라미터:")
        logger.debug(f"  - short_window: {DEFAULT_SHORT_WINDOW_LIST}")
        logger.debug(f"  - long_window: {DEFAULT_LONG_WINDOW_LIST}")
        logger.debug(f"  - stop_loss_pct: {DEFAULT_STOP_LOSS_PCT_LIST}")
        logger.debug(f"  - lookback_for_low: {DEFAULT_LOOKBACK_FOR_LOW_LIST}")

        wf_results_df, wf_equity_df, wf_summary = run_walkforward(
            df=df,
            short_window_list=DEFAULT_SHORT_WINDOW_LIST,
            long_window_list=DEFAULT_LONG_WINDOW_LIST,
            stop_loss_pct_list=DEFAULT_STOP_LOSS_PCT_LIST,
            lookback_for_low_list=DEFAULT_LOOKBACK_FOR_LOW_LIST,
            train_years=args.train,
            test_years=args.test,
            initial_capital=DEFAULT_INITIAL_CAPITAL,
            selection_metric=args.metric,
        )

        # 3. Buy & Hold 벤치마크 실행
        _, bh_summary = run_buy_and_hold(df, initial_capital=DEFAULT_INITIAL_CAPITAL)

        # 4. 결과 출력
        print_window_results(wf_results_df)
        print_summary(wf_summary, bh_summary)

        # 5. 결과 저장
        output_path = DEFAULT_DATA_FILE.parent / "walkforward_results.csv"
        wf_results_df.to_csv(output_path, index=False)
        logger.debug(f"\n결과 저장 완료: {output_path}")

        return 0

    except ValueError as e:
        logger.error(f"값 오류: {e}")
        return 1

    except Exception as e:
        logger.error(f"예기치 않은 오류: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
