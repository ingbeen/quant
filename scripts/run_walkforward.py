"""
QQQ 워킹 포워드 테스트 실행 스크립트

5단계: 워킹 포워드 테스트
"""

import argparse
import sys

from qbt.backtest import (
    DataValidationError,
    load_data,
    run_buy_and_hold,
    run_walkforward,
    validate_data,
)
from qbt.backtest.config import (
    DEFAULT_DATA_FILE,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_LONG_WINDOW_LIST,
    DEFAULT_LOOKBACK_FOR_LOW_LIST,
    DEFAULT_SHORT_WINDOW_LIST,
    DEFAULT_STOP_LOSS_PCT_LIST,
)
from qbt.utils import setup_logger

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
    logger.debug("=" * 100)
    logger.debug("[구간별 워킹 포워드 결과]")
    logger.debug("=" * 100)

    if results_df.empty:
        logger.debug("결과 없음")
        return

    header = (
        f"{'윈도우':>6} {'Train 기간':>24} {'Test 기간':>24} "
        f"{'MA':>4} {'Short':>6} {'Long':>6} {'Test수익률':>10} {'Test MDD':>10}"
    )
    logger.debug(header)
    logger.debug("-" * 100)

    for _, row in results_df.iterrows():
        train_period = f"{row['train_start']} ~ {row['train_end']}"
        test_period = f"{row['test_start']} ~ {row['test_end']}"
        line = (
            f"{row['window_idx']:>6} {train_period:>24} {test_period:>24} "
            f"{row['best_ma_type'].upper():>4} {row['best_short_window']:>6} "
            f"{row['best_long_window']:>6} {row['test_return_pct']:>9.2f}% "
            f"{row['test_mdd']:>9.2f}%"
        )
        logger.debug(line)

    logger.debug("=" * 100)


def print_summary(wf_summary: dict, bh_summary: dict) -> None:
    """요약 지표를 출력한다."""
    logger.debug("\n" + "=" * 60)
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

        # 4. 워킹 포워드 테스트 실행
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

        # 5. Buy & Hold 벤치마크 실행
        _, bh_summary = run_buy_and_hold(df, initial_capital=DEFAULT_INITIAL_CAPITAL)

        # 6. 결과 출력
        print_window_results(wf_results_df)
        print_summary(wf_summary, bh_summary)

        # 7. 결과 저장
        output_path = DEFAULT_DATA_FILE.parent / "walkforward_results.csv"
        wf_results_df.to_csv(output_path, index=False)
        logger.debug(f"\n결과 저장 완료: {output_path}")

        return 0

    except FileNotFoundError as e:
        logger.error(f"파일 오류: {e}")
        return 1

    except DataValidationError as e:
        logger.error(f"데이터 검증 실패: {e}")
        return 1

    except ValueError as e:
        logger.error(f"값 오류: {e}")
        return 1

    except Exception as e:
        logger.error(f"예기치 않은 오류: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
