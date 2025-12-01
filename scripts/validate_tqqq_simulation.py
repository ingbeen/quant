"""
TQQQ 시뮬레이션 검증 스크립트

QQQ 데이터로부터 TQQQ를 시뮬레이션하고 실제 TQQQ 데이터와 비교하여
최적 파라미터를 탐색하고 검증 지표를 출력한다.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from qbt.synth import (
    find_optimal_multiplier,
    generate_daily_comparison_csv,
    simulate_leveraged_etf,
    validate_simulation,
)
from qbt.utils import setup_logger
from qbt.utils.formatting import Align, TableLogger

# 로거 설정
logger = setup_logger("validate_tqqq_simulation", level="DEBUG")


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
        description="TQQQ 시뮬레이션 검증 및 최적 파라미터 탐색",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            사용 예시:
            # 기본 파라미터로 검증
            poetry run python scripts/validate_tqqq_simulation.py

            # 탐색 범위 지정
            poetry run python scripts/validate_tqqq_simulation.py --search-min 2.9 --search-max 3.1
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
        "--expense-ratio",
        type=float,
        default=0.009,
        help="연간 비용 비율 (기본값: 0.009 = 0.9%%)",
    )
    parser.add_argument(
        "--ffr-path",
        type=Path,
        default=Path("data/raw/federal_funds_rate_monthly.csv"),
        help="연방기금금리 CSV 파일 경로 (기본값: data/raw/federal_funds_rate_monthly.csv)",
    )
    parser.add_argument(
        "--search-min",
        type=float,
        default=2.8,
        help="탐색 범위 최소값 (기본값: 2.8)",
    )
    parser.add_argument(
        "--search-max",
        type=float,
        default=3.2,
        help="탐색 범위 최대값 (기본값: 3.2)",
    )
    parser.add_argument(
        "--search-step",
        type=float,
        default=0.01,
        help="탐색 간격 (기본값: 0.01)",
    )

    args = parser.parse_args()

    try:
        # 1. 데이터 로드
        logger.debug("QQQ, TQQQ 및 FFR 데이터 로딩 시작")
        qqq_df = load_csv_data(args.qqq_path)
        tqqq_df = load_csv_data(args.tqqq_path)
        ffr_df = load_ffr_data(args.ffr_path)

        # 2. 최적 multiplier 탐색
        logger.debug(f"최적 multiplier 탐색 시작: 범위 {args.search_min}~{args.search_max}, 간격 {args.search_step}")
        optimal_multiplier, _ = find_optimal_multiplier(
            underlying_df=qqq_df,
            actual_leveraged_df=tqqq_df,
            ffr_df=ffr_df,
            expense_ratio=args.expense_ratio,
            search_range=(args.search_min, args.search_max),
            search_step=args.search_step,
        )

        if optimal_multiplier is None:
            raise ValueError("최적 multiplier를 찾을 수 없습니다")

        # 타입 체커를 위한 assert (이미 위에서 None 체크 완료)
        assert optimal_multiplier is not None

        logger.debug(f"최적 multiplier 발견: {optimal_multiplier:.2f}")

        # 3. 최적 multiplier로 시뮬레이션 재실행
        logger.debug("최적 multiplier로 전체 기간 시뮬레이션 실행")

        # 겹치는 기간 추출
        qqq_dates = set(qqq_df["Date"])
        tqqq_dates = set(tqqq_df["Date"])
        overlap_dates = sorted(qqq_dates & tqqq_dates)

        qqq_overlap = qqq_df[qqq_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)
        tqqq_overlap = tqqq_df[tqqq_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)

        initial_price = float(tqqq_overlap.iloc[0]["Close"])

        simulated_df = simulate_leveraged_etf(
            underlying_df=qqq_overlap,
            leverage=optimal_multiplier,
            expense_ratio=args.expense_ratio,
            initial_price=initial_price,
            ffr_df=ffr_df,
        )

        # 4. 검증 지표 계산
        logger.debug("검증 지표 계산")
        validation_results = validate_simulation(
            simulated_df=simulated_df,
            actual_df=tqqq_overlap,
        )

        # 4-1. 일별 비교 CSV 생성
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)

        daily_csv_path = results_dir / "tqqq_daily_comparison.csv"
        logger.debug(f"일별 비교 CSV 생성: {daily_csv_path}")
        generate_daily_comparison_csv(
            simulated_df=simulated_df,
            actual_df=tqqq_overlap,
            output_path=daily_csv_path,
        )

        daily_df = pd.read_csv(daily_csv_path)
        logger.debug(f"일별 비교 CSV 저장 완료: {len(daily_df):,}행")

        # 5. 결과 출력 (터미널)
        logger.debug("=" * 64)
        logger.debug("TQQQ 시뮬레이션 검증")
        logger.debug("=" * 64)
        logger.debug(f"검증 기간: {validation_results['overlap_start']} ~ {validation_results['overlap_end']}")
        logger.debug(f"총 일수: {validation_results['overlap_days']:,}일")
        logger.debug(f"최적 multiplier: {optimal_multiplier:.2f}")
        logger.debug("-" * 64)

        # 수익률 비교 테이블
        logger.debug("수익률 비교")
        logger.debug("-" * 64)

        # 일일 수익률 계산
        sim_daily_returns = simulated_df["Close"].pct_change().dropna()
        actual_daily_returns = tqqq_overlap["Close"].pct_change().dropna()

        columns = [
            ("구분", 20, Align.LEFT),
            ("누적 수익률", 16, Align.RIGHT),
            ("일일 평균", 14, Align.RIGHT),
            ("일일 표준편차", 16, Align.RIGHT),
        ]
        table = TableLogger(columns, logger, indent=2)

        rows = [
            [
                "실제 TQQQ",
                f"+{validation_results['cumulative_return_actual']*100:.1f}%",
                f"{actual_daily_returns.mean()*100:.2f}%",
                f"{actual_daily_returns.std()*100:.2f}%",
            ],
            [
                "시뮬레이션",
                f"+{validation_results['cumulative_return_simulated']*100:.1f}%",
                f"{sim_daily_returns.mean()*100:.2f}%",
                f"{sim_daily_returns.std()*100:.2f}%",
            ],
            [
                "차이",
                f"{validation_results['cumulative_return_diff_pct']:+.1f}%p",
                f"{validation_results['mean_return_diff']*100:+.2f}%p",
                f"{validation_results['std_return_diff']*100:+.2f}%p",
            ],
        ]

        table.print_table(rows)

        logger.debug("-" * 64)
        logger.debug("검증 지표")
        logger.debug("-" * 64)

        # 일일 수익률 관련
        logger.debug("  [일일 수익률]")
        logger.debug(f"    상관계수: {validation_results['correlation']:.4f}")
        logger.debug(f"    평균 차이: {validation_results['mean_return_diff']*100:.4f}%")
        logger.debug(f"    MAE: {validation_results['mean_return_diff_abs']*100:.4f}%")
        logger.debug(f"    최대 오차: {validation_results['max_return_diff_abs']*100:.4f}%")
        logger.debug(f"    MSE: {validation_results['mse_daily_return']:.8f}")
        logger.debug(f"    RMSE: {validation_results['rmse_daily_return']*100:.4f}%")

        # 로그가격 관련
        logger.debug("  [로그가격]")
        logger.debug(f"    RMSE: {validation_results['rmse_log_price']:.6f}")
        logger.debug(f"    최대 오차: {validation_results['max_error_log_price']:.6f}")

        # 누적수익률 관련
        logger.debug("  [누적수익률]")
        logger.debug(f"    실제: +{validation_results['cumulative_return_actual']*100:.1f}%")
        logger.debug(f"    시뮬: +{validation_results['cumulative_return_simulated']*100:.1f}%")
        logger.debug(f"    차이: {validation_results['cumulative_return_diff_pct']:+.1f}%p")
        logger.debug(f"    RMSE: {validation_results['rmse_cumulative_return']*100:.4f}%")
        logger.debug(f"    최대 오차: {validation_results['max_error_cumulative_return']*100:.4f}%")

        # 가격 관련
        logger.debug("  [가격]")
        logger.debug(f"    최종 가격 차이: {validation_results['final_price_diff_pct']:+.2f}%")
        logger.debug(f"    일별 평균 차이: {validation_results['mean_price_diff_pct']:.4f}%")
        logger.debug(f"    일별 최대 차이: {validation_results['max_price_diff_pct']:.4f}%")

        # 품질 검증
        if validation_results["correlation"] < 0.95:
            logger.warning(f"상관계수가 낮습니다: {validation_results['correlation']:.4f} (권장: 0.95 이상)")

        if abs(validation_results["cumulative_return_diff_pct"]) > 20:
            logger.warning(
                f"누적 수익률 차이가 큽니다: {validation_results['cumulative_return_diff_pct']:.1f}%p (권장: ±20%p 이내)"
            )

        if abs(validation_results["final_price_diff_pct"]) > 10:
            logger.warning(
                f"최종 가격 차이가 큽니다: {validation_results['final_price_diff_pct']:+.2f}% (권장: ±10% 이내)"
            )

        # 일별 비교 요약 통계
        logger.debug("-" * 64)
        logger.debug("일별 비교 요약 통계")
        logger.debug("-" * 64)

        columns = [
            ("지표", 30, Align.LEFT),
            ("평균", 12, Align.RIGHT),
            ("최대", 12, Align.RIGHT),
            ("최소", 12, Align.RIGHT),
        ]
        summary_table = TableLogger(columns, logger, indent=2)

        rows = [
            [
                "일일수익률 차이 절대값 (%)",
                f"{daily_df['일일수익률_차이_절대값'].mean():.4f}",
                f"{daily_df['일일수익률_차이_절대값'].max():.4f}",
                f"{daily_df['일일수익률_차이_절대값'].min():.4f}",
            ],
            [
                "가격 차이 비율 (%)",
                f"{daily_df['가격_차이_비율'].abs().mean():.4f}",
                f"{daily_df['가격_차이_비율'].abs().max():.4f}",
                f"{daily_df['가격_차이_비율'].abs().min():.4f}",
            ],
            [
                "로그가격 차이",
                f"{daily_df['로그가격_차이'].abs().mean():.6f}",
                f"{daily_df['로그가격_차이'].abs().max():.6f}",
                f"{daily_df['로그가격_차이'].abs().min():.6f}",
            ],
            [
                "누적수익률 차이 (%)",
                f"{daily_df['누적수익률_차이'].abs().mean():.2f}",
                f"{daily_df['누적수익률_차이'].abs().max():.2f}",
                f"{daily_df['누적수익률_차이'].abs().min():.2f}",
            ],
        ]

        summary_table.print_table(rows)

        logger.debug("=" * 64)

        # 6. 결과 저장 (CSV)
        results_csv_path = results_dir / "tqqq_validation.csv"
        results_data = {
            # 기본 정보
            "검증일": [pd.Timestamp.now().date()],
            "검증기간_시작": [validation_results["overlap_start"]],
            "검증기간_종료": [validation_results["overlap_end"]],
            "총일수": [validation_results["overlap_days"]],
            "최적_multiplier": [round(optimal_multiplier, 4)],
            "expense_ratio": [round(args.expense_ratio, 6)],
            # 일일 수익률 지표
            "일일수익률_상관계수": [round(validation_results["correlation"], 6)],
            "일일수익률_평균차이_pct": [round(validation_results["mean_return_diff"] * 100, 4)],
            "일일수익률_표준편차차이_pct": [round(validation_results["std_return_diff"] * 100, 4)],
            "일일수익률_MAE_pct": [round(validation_results["mean_return_diff_abs"] * 100, 4)],
            "일일수익률_최대오차_pct": [round(validation_results["max_return_diff_abs"] * 100, 4)],
            "일일수익률_MSE": [round(validation_results["mse_daily_return"], 8)],
            "일일수익률_RMSE_pct": [round(validation_results["rmse_daily_return"] * 100, 4)],
            # 로그가격 지표
            "로그가격_RMSE": [round(validation_results["rmse_log_price"], 6)],
            "로그가격_최대오차": [round(validation_results["max_error_log_price"], 6)],
            # 누적수익률 지표
            "누적수익률_실제_pct": [round(validation_results["cumulative_return_actual"] * 100, 2)],
            "누적수익률_시뮬레이션_pct": [round(validation_results["cumulative_return_simulated"] * 100, 2)],
            "누적수익률_차이_pct": [round(validation_results["cumulative_return_diff_pct"], 2)],
            "누적수익률_RMSE_pct": [round(validation_results["rmse_cumulative_return"] * 100, 4)],
            "누적수익률_최대오차_pct": [round(validation_results["max_error_cumulative_return"] * 100, 4)],
            # 가격 지표
            "최종가격_차이_pct": [round(validation_results["final_price_diff_pct"], 4)],
            "일별가격_평균차이_pct": [round(validation_results["mean_price_diff_pct"], 4)],
            "일별가격_최대차이_pct": [round(validation_results["max_price_diff_pct"], 4)],
        }

        results_df = pd.DataFrame(results_data)
        results_df.to_csv(results_csv_path, index=False, encoding="utf-8-sig")
        logger.debug(f"검증 결과 저장: {results_csv_path}")

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
