"""
TQQQ 시뮬레이션 파라미터 그리드 서치 스크립트

비용 모델 파라미터(funding spread, expense ratio)의 다양한 조합을 탐색하여
실제 TQQQ 데이터와 가장 유사한 시뮬레이션을 생성하는 최적 파라미터를 찾는다.
상위 전략을 CSV로 저장한다.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from qbt.synth import find_optimal_cost_model
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
        description="TQQQ 시뮬레이션 파라미터 그리드 서치",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            사용 예시:
            # 기본 범위로 그리드 서치
            poetry run python scripts/validate_tqqq_simulation.py

            # 탐색 범위 좁히기
            poetry run python scripts/validate_tqqq_simulation.py \\
              --spread-min 0.6 --spread-max 0.7 \\
              --expense-min 0.008 --expense-max 0.010
        """,
    )
    parser.add_argument(
        "--qqq-path",
        type=Path,
        default=Path("data/raw/QQQ_max.csv"),
        help="QQQ CSV 파일 경로 (기본값: data/raw/QQQ_max.csv)",
    )
    parser.add_argument(
        "--tqqq-path",
        type=Path,
        default=Path("data/raw/TQQQ_max.csv"),
        help="TQQQ CSV 파일 경로 (기본값: data/raw/TQQQ_max.csv)",
    )
    parser.add_argument(
        "--ffr-path",
        type=Path,
        default=Path("data/raw/federal_funds_rate_monthly.csv"),
        help="연방기금금리 CSV 파일 경로 (기본값: data/raw/federal_funds_rate_monthly.csv)",
    )
    parser.add_argument(
        "--leverage",
        type=float,
        default=3.0,
        help="레버리지 배수",
    )
    parser.add_argument(
        "--spread-min",
        type=float,
        default=0.4,
        help="funding spread 탐색 최소값",
    )
    parser.add_argument(
        "--spread-max",
        type=float,
        default=0.9,
        help="funding spread 탐색 최대값",
    )
    parser.add_argument(
        "--spread-step",
        type=float,
        default=0.05,
        help="funding spread 탐색 간격",
    )
    parser.add_argument(
        "--expense-min",
        type=float,
        default=0.007,
        help="expense ratio 탐색 최소값",
    )
    parser.add_argument(
        "--expense-max",
        type=float,
        default=0.011,
        help="expense ratio 탐색 최대값",
    )
    parser.add_argument(
        "--expense-step",
        type=float,
        default=0.001,
        help="expense ratio 탐색 간격",
    )

    args = parser.parse_args()

    try:
        # 1. 데이터 로드
        logger.debug("QQQ, TQQQ 및 FFR 데이터 로딩 시작")
        qqq_df = load_csv_data(args.qqq_path)
        tqqq_df = load_csv_data(args.tqqq_path)
        ffr_df = load_ffr_data(args.ffr_path)

        # 2. 비용 모델 캘리브레이션
        logger.debug(
            f"비용 모델 캘리브레이션 시작: "
            f"leverage={args.leverage}, "
            f"spread={args.spread_min}~{args.spread_max}% (step={args.spread_step}%), "
            f"expense={args.expense_min*100:.2f}~{args.expense_max*100:.2f}% "
            f"(step={args.expense_step*100:.2f}%)"
        )

        top_strategies = find_optimal_cost_model(
            underlying_df=qqq_df,
            actual_leveraged_df=tqqq_df,
            ffr_df=ffr_df,
            leverage=args.leverage,
            spread_range=(args.spread_min, args.spread_max),
            spread_step=args.spread_step,
            expense_range=(args.expense_min, args.expense_max),
            expense_step=args.expense_step,
        )

        # 3. 상위 전략 테이블 출력
        logger.debug("=" * 120)
        logger.debug("상위 전략")

        columns = [
            ("Rank", 6, Align.RIGHT),
            ("Spread(%)", 12, Align.RIGHT),
            ("Expense(%)", 12, Align.RIGHT),
            ("누적수익률상대차이(%)", 22, Align.RIGHT),
            ("누적수익률RMSE(%)", 18, Align.RIGHT),
        ]
        table = TableLogger(columns, logger, indent=2)

        rows = []
        for rank, strategy in enumerate(top_strategies, start=1):
            row = [
                str(rank),
                f"{strategy['funding_spread']:.2f}",
                f"{strategy['expense_ratio']*100:.2f}",
                f"{strategy['cumulative_return_relative_diff_pct']:.4f}",
                f"{strategy['rmse_cumulative_return']*100:.4f}",
            ]
            rows.append(row)

        table.print_table(rows)

        # 4. 결과 저장 (CSV) - 상위 전략
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        results_csv_path = results_dir / "tqqq_validation.csv"

        rows = []
        for rank, strategy in enumerate(top_strategies, start=1):
            row = {
                # 메타 정보 (7개)
                "rank": rank,
                "검증기간_시작": strategy["overlap_start"],
                "검증기간_종료": strategy["overlap_end"],
                "총일수": strategy["overlap_days"],
                "leverage": round(strategy["leverage"], 2),
                "funding_spread": round(strategy["funding_spread"], 2),
                "expense_ratio": round(strategy["expense_ratio"], 6),
                # 누적수익률/성과 (5개)
                "누적수익률_실제_pct": round(strategy["cumulative_return_actual"] * 100, 2),
                "누적수익률_시뮬레이션_pct": round(strategy["cumulative_return_simulated"] * 100, 2),
                "누적수익률_상대차이_pct": round(strategy["cumulative_return_relative_diff_pct"], 4),
                "누적수익률_RMSE_pct": round(strategy["rmse_cumulative_return"] * 100, 4),
                "누적수익률_최대오차_pct": round(strategy["max_error_cumulative_return"] * 100, 4),
                # 일별 가격 (2개)
                "일별가격_평균차이_pct": round(strategy["mean_price_diff_pct"], 4),
                "일별가격_최대차이_pct": round(strategy["max_price_diff_pct"], 4),
            }
            rows.append(row)

        results_df = pd.DataFrame(rows)
        results_df.to_csv(results_csv_path, index=False, encoding="utf-8-sig")
        logger.debug(f"검증 결과 저장: {results_csv_path} ({len(rows)}행)")

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
