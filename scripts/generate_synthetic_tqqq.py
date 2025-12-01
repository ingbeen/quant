"""
합성 TQQQ 데이터 생성 스크립트

QQQ 데이터로부터 TQQQ 데이터를 시뮬레이션하여 생성한다.
검증 스크립트에서 찾은 최적 multiplier를 사용하여 2001년부터의 데이터를 생성한다.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from qbt.synth import simulate_leveraged_etf
from qbt.utils import setup_logger

# 로거 설정
logger = setup_logger("generate_synthetic_tqqq", level="DEBUG")


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
        description="QQQ 데이터로부터 합성 TQQQ 데이터 생성",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            사용 예시:
            # 기본 파라미터로 생성
            poetry run python scripts/generate_synthetic_tqqq.py --start-date 2001-01-01 --multiplier 2.96

            # 모든 파라미터 지정
            poetry run python scripts/generate_synthetic_tqqq.py \\
                --start-date 2001-01-01 \\
                --multiplier 2.96 \\
                --initial-price 100.0 \\
                --output data/raw/TQQQ_synthetic_2001-01-01_max.csv
        """,
    )
    parser.add_argument(
        "--qqq-path",
        type=Path,
        default=Path("data/raw/QQQ_max.csv"),
        help="QQQ CSV 파일 경로 (기본값: data/raw/QQQ_max.csv)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="시작 날짜 (YYYY-MM-DD 형식, 예: 2001-01-01)",
    )
    parser.add_argument(
        "--multiplier",
        type=float,
        required=True,
        help="레버리지 배수 (예: 2.96)",
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
        "--initial-price",
        type=float,
        default=100.0,
        help="초기 가격 (기본값: 100.0)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/TQQQ_synthetic_2001-01-01_max.csv"),
        help="출력 CSV 파일 경로 (기본값: data/raw/TQQQ_synthetic_2001-01-01_max.csv)",
    )

    args = parser.parse_args()

    try:
        # 1. 시작 날짜 파싱
        try:
            start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"날짜 형식이 올바르지 않습니다 (YYYY-MM-DD 필요): {args.start_date}") from e

        logger.debug("합성 TQQQ 데이터 생성 시작")
        logger.debug(
            f"파라미터: multiplier={args.multiplier}, expense_ratio={args.expense_ratio}, initial_price={args.initial_price}"
        )
        logger.debug(f"시작 날짜: {start_date}")

        # 2. QQQ 및 FFR 데이터 로드
        qqq_df = load_csv_data(args.qqq_path)
        ffr_df = load_ffr_data(args.ffr_path)

        # 3. 시작 날짜 이후 데이터만 필터링
        qqq_filtered = qqq_df[qqq_df["Date"] >= start_date].copy()

        if qqq_filtered.empty:
            raise ValueError(
                f"시작 날짜 {start_date} 이후의 QQQ 데이터가 없습니다. QQQ 데이터 범위: {qqq_df['Date'].min()} ~ {qqq_df['Date'].max()}"
            )

        logger.debug(
            f"QQQ 데이터 필터링: {len(qqq_filtered):,}행 ({qqq_filtered['Date'].min()} ~ {qqq_filtered['Date'].max()})"
        )

        # 4. TQQQ 시뮬레이션 실행
        logger.debug("TQQQ 시뮬레이션 실행 중...")
        synthetic_tqqq = simulate_leveraged_etf(
            underlying_df=qqq_filtered,
            leverage=args.multiplier,
            expense_ratio=args.expense_ratio,
            initial_price=args.initial_price,
            ffr_df=ffr_df,
        )

        logger.debug(f"시뮬레이션 완료: {len(synthetic_tqqq):,}행")

        # 5. 출력 디렉토리 생성
        args.output.parent.mkdir(parents=True, exist_ok=True)

        # 6. CSV 저장
        synthetic_tqqq.to_csv(args.output, index=False)
        logger.debug(f"합성 TQQQ 데이터 저장 완료: {args.output}")
        logger.debug(f"기간: {synthetic_tqqq['Date'].min()} ~ {synthetic_tqqq['Date'].max()}")
        logger.debug(f"행 수: {len(synthetic_tqqq):,}")
        logger.debug(f"초기 가격: {synthetic_tqqq.iloc[0]['Close']:.2f}")
        logger.debug(f"최종 가격: {synthetic_tqqq.iloc[-1]['Close']:.2f}")

        # 7. 누적 수익률 계산
        initial_close = synthetic_tqqq.iloc[0]["Close"]
        final_close = synthetic_tqqq.iloc[-1]["Close"]
        cumulative_return = (final_close / initial_close - 1) * 100

        logger.debug(f"누적 수익률: {cumulative_return:+.2f}%")

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
