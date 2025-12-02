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
    find_optimal_cost_model,
    generate_daily_comparison_csv,
    simulate_leveraged_etf,
    validate_simulation,
)
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
        default=0.02,
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
        default=0.0002,
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

        best_strategy, top_strategies = find_optimal_cost_model(
            underlying_df=qqq_df,
            actual_leveraged_df=tqqq_df,
            ffr_df=ffr_df,
            leverage=args.leverage,
            spread_range=(args.spread_min, args.spread_max),
            spread_step=args.spread_step,
            expense_range=(args.expense_min, args.expense_max),
            expense_step=args.expense_step,
        )

        logger.debug(
            f"최적 전략 발견: "
            f"spread={best_strategy['funding_spread']:.2f}%, "
            f"expense={best_strategy['expense_ratio']*100:.2f}%, "
            f"score={best_strategy['score']:.6f}"
        )

        # 3. 상위 10개 전략 테이블 출력
        logger.debug("=" * 120)
        logger.debug("상위 10개 전략")
        logger.debug("=" * 120)

        columns = [
            ("Rank", 6, Align.RIGHT),
            ("Spread(%)", 12, Align.RIGHT),
            ("Expense(%)", 12, Align.RIGHT),
            ("Score", 10, Align.RIGHT),
            ("상관계수", 12, Align.RIGHT),
            ("RMSE(%)", 10, Align.RIGHT),
            ("최종가격차이(%)", 16, Align.RIGHT),
            ("누적수익률차이(%)", 18, Align.RIGHT),
        ]
        table = TableLogger(columns, logger, indent=2)

        rows = []
        for rank, strategy in enumerate(top_strategies, start=1):
            row = [
                str(rank),
                f"{strategy['funding_spread']:.2f}",
                f"{strategy['expense_ratio']*100:.2f}",
                f"{strategy['score']:.6f}",
                f"{strategy['correlation']:.6f}",
                f"{strategy['rmse_daily_return']*100:.4f}",
                f"{strategy['final_price_diff_pct']:+.4f}",
                f"{strategy['cumulative_return_relative_diff_pct']:.4f}",
            ]
            rows.append(row)

        table.print_table(rows)

        logger.debug("=" * 120)

        # 4. best_strategy로 시뮬레이션 재실행
        logger.debug("최적 전략으로 전체 기간 시뮬레이션 실행")

        # 겹치는 기간 추출
        qqq_dates = set(qqq_df["Date"])
        tqqq_dates = set(tqqq_df["Date"])
        overlap_dates = sorted(qqq_dates & tqqq_dates)

        qqq_overlap = qqq_df[qqq_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)
        tqqq_overlap = tqqq_df[tqqq_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)

        initial_price = float(tqqq_overlap.iloc[0]["Close"])

        simulated_df = simulate_leveraged_etf(
            underlying_df=qqq_overlap,
            leverage=best_strategy["leverage"],
            expense_ratio=best_strategy["expense_ratio"],
            initial_price=initial_price,
            ffr_df=ffr_df,
            funding_spread=best_strategy["funding_spread"],
        )

        # 5. 검증 지표 계산
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
        logger.debug(f"레버리지: {best_strategy['leverage']:.1f}배")
        logger.debug(f"Funding Spread: {best_strategy['funding_spread']:.2f}%")
        logger.debug(f"Expense Ratio: {best_strategy['expense_ratio']*100:.2f}%")
        logger.debug(f"전략 Score: {best_strategy['score']:.6f}")
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
        logger.debug(f"    RMSE: {validation_results['rmse_daily_return']*100:.4f}%")

        # 로그가격 관련
        logger.debug("  [로그가격]")
        logger.debug(f"    RMSE: {validation_results['rmse_log_price']:.6f}")
        logger.debug(f"    최대 오차: {validation_results['max_error_log_price']:.6f}")

        # 누적수익률 관련
        logger.debug("  [누적수익률]")
        logger.debug(f"    실제: +{validation_results['cumulative_return_actual']*100:.1f}%")
        logger.debug(f"    시뮬: +{validation_results['cumulative_return_simulated']*100:.1f}%")
        logger.debug(
            f"    차이: {validation_results['cumulative_return_diff_pct']:+.1f}%p "
            f"(실제 대비 {validation_results['cumulative_return_relative_diff_pct']:.2f}% 상대 차이)"
        )
        logger.debug(f"    RMSE: {validation_results['rmse_cumulative_return']*100:.4f}%")
        logger.debug(f"    최대 오차: {validation_results['max_error_cumulative_return']*100:.4f}%")

        # 가격 관련
        logger.debug("  [가격]")
        logger.debug(f"    최종 가격 차이: {validation_results['final_price_diff_pct']:+.2f}%")
        logger.debug(f"    일별 평균 차이: {validation_results['mean_price_diff_pct']:.4f}%")
        logger.debug(f"    일별 최대 차이: {validation_results['max_price_diff_pct']:.4f}%")

        # 품질 검증 (상대 오차 기준)
        if validation_results["correlation"] < 0.95:
            logger.warning(f"상관계수가 낮습니다: {validation_results['correlation']:.4f} (권장: 0.95 이상)")

        cum_rel_diff_pct = validation_results["cumulative_return_relative_diff_pct"]
        if cum_rel_diff_pct > 20:
            logger.warning(f"누적 수익률 상대 차이가 큽니다: {cum_rel_diff_pct:.2f}% (권장: ±20% 이내)")

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
        ]
        summary_table = TableLogger(columns, logger, indent=2)

        rows = [
            [
                "일일수익률 차이 절대값 (%)",
                f"{daily_df['일일수익률_차이'].abs().mean():.4f}",
                f"{daily_df['일일수익률_차이'].abs().max():.4f}",
            ],
            [
                "가격 차이 비율 (%)",
                f"{daily_df['가격_차이_비율'].abs().mean():.4f}",
                f"{daily_df['가격_차이_비율'].abs().max():.4f}",
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

        corr = validation_results["correlation"]
        rmse_pct = validation_results["rmse_daily_return"] * 100
        final_diff = validation_results["final_price_diff_pct"]
        rel_cum_diff = validation_results["cumulative_return_relative_diff_pct"]
        years = validation_results["overlap_days"] / 252

        # 상관계수 해석
        if corr >= 0.999:
            corr_desc = "거의 완벽하게 따라갑니다"
        elif corr >= 0.99:
            corr_desc = "매우 정확하게 추종합니다"
        elif corr >= 0.95:
            corr_desc = "양호하게 추종합니다"
        else:
            corr_desc = "추종 정확도가 다소 낮습니다"

        logger.debug(f"- 일일 수익률 상관계수 {corr:.4f}로, 실제 TQQQ의 일간 움직임을 {corr_desc}.")
        logger.debug(f"- 일일 수익률 RMSE는 {rmse_pct:.2f}%입니다.")

        # 최종 가격 차이 해석
        if abs(final_diff) < 1:
            final_desc = "거의 동일한 수준"
        elif abs(final_diff) < 5:
            final_desc = "매우 근접한 수준"
        else:
            final_desc = "양호한 수준"

        logger.debug(f"- 최종 가격 차이는 {final_diff:+.2f}%로, {years:.1f}년 이상 기간 동안 {final_desc}입니다.")

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

        # 6. 결과 저장 (CSV) - 상위 10개 전략
        results_csv_path = results_dir / "tqqq_validation.csv"

        rows = []
        for rank, strategy in enumerate(top_strategies, start=1):
            row = {
                # 기본 정보
                "rank": rank,
                "검증일": pd.Timestamp.now().date(),
                "검증기간_시작": strategy["overlap_start"],
                "검증기간_종료": strategy["overlap_end"],
                "총일수": strategy["overlap_days"],
                # 전략 파라미터
                "leverage": round(strategy["leverage"], 2),
                "funding_spread": round(strategy["funding_spread"], 2),
                "expense_ratio": round(strategy["expense_ratio"], 6),
                "strategy_score": round(strategy["score"], 6),
                # 일일 수익률 지표
                "일일수익률_상관계수": round(strategy["correlation"], 6),
                "일일수익률_평균차이_pct": round(strategy["mean_return_diff"] * 100, 4),
                "일일수익률_표준편차차이_pct": round(strategy["std_return_diff"] * 100, 4),
                "일일수익률_MAE_pct": round(strategy["mean_return_diff_abs"] * 100, 4),
                "일일수익률_최대오차_pct": round(strategy["max_return_diff_abs"] * 100, 4),
                "일일수익률_RMSE_pct": round(strategy["rmse_daily_return"] * 100, 4),
                # 로그가격 지표
                "로그가격_RMSE": round(strategy["rmse_log_price"], 6),
                "로그가격_최대오차": round(strategy["max_error_log_price"], 6),
                # 누적수익률 지표
                "누적수익률_실제_pct": round(strategy["cumulative_return_actual"] * 100, 2),
                "누적수익률_시뮬레이션_pct": round(strategy["cumulative_return_simulated"] * 100, 2),
                "누적수익률_차이_pct": round(strategy["cumulative_return_diff_pct"], 2),
                "누적수익률_상대차이_pct": round(strategy["cumulative_return_relative_diff_pct"], 4),
                "누적수익률_RMSE_pct": round(strategy["rmse_cumulative_return"] * 100, 4),
                "누적수익률_최대오차_pct": round(strategy["max_error_cumulative_return"] * 100, 4),
                # 가격 지표
                "최종가격_차이_pct": round(strategy["final_price_diff_pct"], 4),
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
