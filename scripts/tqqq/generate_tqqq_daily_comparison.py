"""
TQQQ 일별 비교 CSV 생성 스크립트

지정된 파라미터로 TQQQ를 시뮬레이션하고 실제 TQQQ 데이터와 일별로 비교하여
상세 검증 지표와 일별 비교 CSV를 생성한다.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from qbt.config import FFR_DATA_PATH, QQQ_DATA_PATH, TQQQ_DAILY_COMPARISON_PATH, TQQQ_DATA_PATH
from qbt.synth import generate_daily_comparison_csv, simulate_leveraged_etf, validate_simulation
from qbt.utils import get_logger
from qbt.utils.formatting import Align, TableLogger

logger = get_logger(__name__)


def load_csv_data(path: Path) -> pd.DataFrame:
    """
    CSV 파일을 로드하고 Date 컬럼을 date 타입으로 변환한다.

    Args:
        path: CSV 파일 경로

    Returns:
        로드된 DataFrame

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
    """
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    logger.debug(f"데이터 로딩: {path}")
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    logger.debug(f"로드 완료: {len(df):,}행, 기간 {df['Date'].min()} ~ {df['Date'].max()}")

    return df


def load_ffr_data(path: Path) -> pd.DataFrame:
    """
    연방기금금리 월별 데이터를 로드한다.

    Args:
        path: CSV 파일 경로

    Returns:
        FFR DataFrame (DATE: Timestamp, FFR: float)

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
    """
    if not path.exists():
        raise FileNotFoundError(f"FFR 파일을 찾을 수 없습니다: {path}")

    logger.debug(f"FFR 데이터 로딩: {path}")
    df = pd.read_csv(path)
    df["DATE"] = pd.to_datetime(df["DATE"])
    df.rename(columns={"VALUE": "FFR"}, inplace=True)

    logger.debug(f"FFR 로드 완료: {len(df)}개월, 범위 {df['DATE'].min()} ~ {df['DATE'].max()}")

    return df


def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    parser = argparse.ArgumentParser(
        description="TQQQ 일별 비교 CSV 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            사용 예시:
            # 기본 파라미터로 일별 비교 생성
            poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py

            # 특정 파라미터로 일별 비교 생성
            poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py \\
              --funding-spread 0.65 \\
              --expense-ratio 0.009

            # 출력 파일 경로 지정
            poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py \\
              --output results/tqqq_daily_custom.csv
        """,
    )
    parser.add_argument(
        "--qqq-path",
        type=Path,
        default=QQQ_DATA_PATH,
        help="QQQ CSV 파일 경로",
    )
    parser.add_argument(
        "--tqqq-path",
        type=Path,
        default=TQQQ_DATA_PATH,
        help="TQQQ CSV 파일 경로",
    )
    parser.add_argument(
        "--ffr-path",
        type=Path,
        default=FFR_DATA_PATH,
        help="연방기금금리 CSV 파일 경로",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=3.0,
        help="레버리지 배수",
    )
    parser.add_argument(
        "--funding-spread",
        type=float,
        default=0.5,
        help="펀딩 스프레드 (%%)",
    )
    parser.add_argument(
        "--expense-ratio",
        type=float,
        default=0.008,
        help="연간 비용 비율",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=TQQQ_DAILY_COMPARISON_PATH,
        help="출력 CSV 파일 경로",
    )

    args = parser.parse_args()

    try:
        # 1. 데이터 로드
        logger.debug("QQQ, TQQQ 및 FFR 데이터 로딩 시작")
        qqq_df = load_csv_data(args.qqq_path)
        tqqq_df = load_csv_data(args.tqqq_path)
        ffr_df = load_ffr_data(args.ffr_path)

        # 2. 겹치는 기간 추출
        logger.debug("겹치는 기간 추출")
        qqq_dates = set(qqq_df["Date"])
        tqqq_dates = set(tqqq_df["Date"])
        overlap_dates = sorted(qqq_dates & tqqq_dates)

        if not overlap_dates:
            raise ValueError("QQQ와 TQQQ 간 겹치는 기간이 없습니다")

        qqq_overlap = qqq_df[qqq_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)
        tqqq_overlap = tqqq_df[tqqq_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)

        logger.debug(f"겹치는 기간: {overlap_dates[0]} ~ {overlap_dates[-1]} ({len(overlap_dates):,}일)")

        # 3. 시뮬레이션 실행
        logger.debug(
            f"시뮬레이션 실행: leverage={args.leverage}, "
            f"funding_spread={args.funding_spread}%, "
            f"expense_ratio={args.expense_ratio*100:.2f}%"
        )

        initial_price = float(tqqq_overlap.iloc[0]["Close"])
        simulated_df = simulate_leveraged_etf(
            underlying_df=qqq_overlap,
            leverage=args.leverage,
            expense_ratio=args.expense_ratio,
            initial_price=initial_price,
            ffr_df=ffr_df,
            funding_spread=args.funding_spread,
        )

        logger.debug("시뮬레이션 완료")

        # 4. 검증 지표 계산
        logger.debug("검증 지표 계산")
        validation_results = validate_simulation(
            simulated_df=simulated_df,
            actual_df=tqqq_overlap,
        )

        # 5. 일별 비교 CSV 생성
        args.output.parent.mkdir(exist_ok=True, parents=True)
        logger.debug(f"일별 비교 CSV 생성: {args.output}")
        generate_daily_comparison_csv(
            simulated_df=simulated_df,
            actual_df=tqqq_overlap,
            output_path=args.output,
        )

        daily_df = pd.read_csv(args.output)
        logger.debug(f"일별 비교 CSV 저장 완료: {len(daily_df):,}행")

        # 6. 결과 출력 (터미널)
        logger.debug("=" * 64)
        logger.debug("TQQQ 시뮬레이션 검증")
        logger.debug("=" * 64)
        logger.debug(f"검증 기간: {validation_results['overlap_start']} ~ {validation_results['overlap_end']}")
        logger.debug(f"총 일수: {validation_results['overlap_days']:,}일")
        logger.debug(f"레버리지: {args.leverage:.1f}배")
        logger.debug(f"Funding Spread: {args.funding_spread:.2f}%")
        logger.debug(f"Expense Ratio: {args.expense_ratio*100:.2f}%")

        logger.debug("-" * 64)
        logger.debug("검증 지표")
        logger.debug("-" * 64)

        # 누적수익률 관련
        logger.debug("  [누적수익률]")
        logger.debug(f"    실제: +{validation_results['cumulative_return_actual']*100:.1f}%")
        logger.debug(f"    시뮬: +{validation_results['cumulative_return_simulated']*100:.1f}%")
        logger.debug(f"    상대 차이: {validation_results['cumulative_return_relative_diff_pct']:.2f}%")
        logger.debug(f"    RMSE: {validation_results['rmse_cumulative_return']*100:.4f}%")
        logger.debug(f"    최대 오차: {validation_results['max_error_cumulative_return']*100:.4f}%")

        # 품질 검증
        cum_rel_diff_pct = validation_results["cumulative_return_relative_diff_pct"]
        if cum_rel_diff_pct > 20:
            logger.warning(f"누적 수익률 상대 차이가 큽니다: {cum_rel_diff_pct:.2f}% (권장: ±20% 이내)")

        # 일별 비교 요약 통계
        logger.debug("-" * 64)
        logger.debug("일별 비교 요약 통계")
        logger.debug("-" * 64)

        columns = [
            ("지표", 30, Align.LEFT),
            ("평균", 12, Align.RIGHT),
            ("최대", 12, Align.RIGHT),
        ]
        summary_table = TableLogger(columns, logger, indent=2)

        rows = [
            [
                "일일수익률 차이 (%)",
                f"{daily_df['일일수익률_차이'].mean():.4f}",
                f"{daily_df['일일수익률_차이'].max():.4f}",
            ],
            [
                "누적수익률 차이 (%)",
                f"{daily_df['누적수익률_차이'].abs().mean():.2f}",
                f"{daily_df['누적수익률_차이'].abs().max():.2f}",
            ],
        ]

        summary_table.print_table(rows)

        # 문장형 요약
        logger.debug("-" * 64)
        logger.debug("[요약]")
        logger.debug("-" * 64)

        rel_cum_diff = validation_results["cumulative_return_relative_diff_pct"]

        # 누적 수익률 상대 차이 해석
        if rel_cum_diff < 1:
            cum_desc = "거의 완전히 일치"
        elif rel_cum_diff < 5:
            cum_desc = "매우 근접"
        elif rel_cum_diff < 20:
            cum_desc = "양호하게 일치"
        else:
            cum_desc = "다소 차이 존재"

        logger.debug(f"- 누적 수익률 상대 차이는 {rel_cum_diff:.2f}%로, 장기 성과도 {cum_desc}합니다.")
        logger.debug("-" * 64)

        logger.debug("=" * 64)
        logger.debug(f"일별 비교 CSV 저장 완료: {args.output}")

        return 0

    except FileNotFoundError as e:
        logger.error(f"파일 오류: {e}")
        return 1

    except ValueError as e:
        logger.error(f"입력값 오류: {e}")
        return 1

    except Exception as e:
        logger.error(f"예기치 않은 오류: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
