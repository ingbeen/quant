"""CLI 유틸리티 모듈

스크립트에서 공통으로 사용하는 데이터 로딩, 출력 포맷팅 함수를 제공한다.
"""

from logging import Logger
from pathlib import Path

import pandas as pd


def load_and_validate_data(data_path: Path, logger: Logger) -> pd.DataFrame | None:
    """
    데이터를 로드하고 검증한다.

    Args:
        data_path: 데이터 파일 경로
        logger: 로거 인스턴스

    Returns:
        검증된 DataFrame, 실패 시 None
    """
    # 순환 임포트 방지를 위해 함수 내부에서 import
    from qbt.backtest.data import load_data, validate_data
    from qbt.backtest.exceptions import DataValidationError

    try:
        logger.debug(f"데이터 파일 경로: {data_path}")
        df = load_data(data_path)
        validate_data(df)

        logger.debug("=" * 60)
        logger.debug("데이터 로딩 및 검증 완료")
        logger.debug(f"총 행 수: {len(df):,}")
        logger.debug(f"기간: {df['Date'].min()} ~ {df['Date'].max()}")
        logger.debug("=" * 60)

        return df

    except FileNotFoundError as e:
        logger.error(f"파일 오류: {e}")
        return None

    except DataValidationError as e:
        logger.error(f"데이터 검증 실패: {e}")
        return None


def print_summary(summary: dict, title: str, logger: Logger) -> None:
    """
    요약 지표를 출력한다.

    Args:
        summary: 요약 지표 딕셔너리
        title: 출력 제목
        logger: 로거 인스턴스
    """
    logger.debug("=" * 60)
    logger.debug(f"[{title}]")
    logger.debug(f"  기간: {summary.get('start_date')} ~ {summary.get('end_date')}")
    logger.debug(f"  초기 자본: {summary['initial_capital']:,.0f}원")
    logger.debug(f"  최종 자본: {summary['final_capital']:,.0f}원")
    logger.debug(f"  총 수익률: {summary['total_return_pct']:.2f}%")
    logger.debug(f"  CAGR: {summary['cagr']:.2f}%")
    logger.debug(f"  MDD: {summary['mdd']:.2f}%")
    logger.debug(f"  총 거래 수: {summary['total_trades']}")
    if "win_rate" in summary:
        logger.debug(f"  승률: {summary['win_rate']:.1f}%")
        if "winning_trades" in summary:
            logger.debug(
                f"  승/패: {summary['winning_trades']}/{summary['losing_trades']}"
            )
    logger.debug("=" * 60)


def print_trades(trades_df: pd.DataFrame, title: str, logger: Logger, max_rows: int = 10) -> None:
    """
    거래 내역을 출력한다.

    Args:
        trades_df: 거래 내역 DataFrame
        title: 출력 제목
        logger: 로거 인스턴스
        max_rows: 최대 출력 행 수
    """
    if trades_df.empty:
        logger.debug(f"[{title}] 거래 내역 없음")
        return

    logger.debug(f"[{title}] 거래 내역 (최근 {max_rows}건):")
    for _, trade in trades_df.tail(max_rows).iterrows():
        logger.debug(
            f"  {trade['entry_date']} -> {trade['exit_date']} | "
            f"진입: {trade['entry_price']:.2f} | "
            f"청산: {trade['exit_price']:.2f} | "
            f"손익률: {trade['pnl_pct'] * 100:+.2f}% | "
            f"사유: {trade['exit_reason']}"
        )


def print_comparison_table(summaries: list[tuple[str, dict]], logger: Logger) -> None:
    """
    전략 비교 테이블을 출력한다.

    Args:
        summaries: [(전략명, summary_dict), ...] 리스트
        logger: 로거 인스턴스
    """
    logger.debug("\n" + "=" * 60)
    logger.debug("[전략 비교 요약]")
    logger.debug(
        f"  {'전략':<15} {'총수익률':>10} {'CAGR':>10} {'MDD':>10} {'거래수':>8}"
    )
    logger.debug("-" * 60)
    for name, summary in summaries:
        logger.debug(
            f"  {name:<15} {summary['total_return_pct']:>9.2f}% "
            f"{summary['cagr']:>9.2f}% {summary['mdd']:>9.2f}% "
            f"{summary['total_trades']:>8}"
        )
    logger.debug("=" * 60)
