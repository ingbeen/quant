"""CLI 유틸리티 모듈

스크립트에서 공통으로 사용하는 데이터 로딩, 출력 포맷팅 함수를 제공한다.
"""

from logging import Logger
from pathlib import Path

import pandas as pd


def get_display_width(text: str) -> int:
    """
    문자열의 실제 터미널 출력 폭을 계산한다.

    한글, 한자 등 동아시아 문자는 2칸, 영문/숫자/기호는 1칸으로 계산한다.

    Args:
        text: 폭을 계산할 문자열

    Returns:
        터미널에서 차지하는 실제 폭 (칸 수)
    """
    width = 0
    for char in text:
        # 한글, 한자 등 동아시아 문자는 2칸
        if ord(char) > 0x1100:
            width += 2
        else:
            width += 1
    return width


def format_cell(text: str, width: int, align: str = "left") -> str:
    """
    터미널 폭을 고려하여 문자열을 정렬한다.

    한글과 영문이 섞인 문자열도 올바르게 정렬한다.

    Args:
        text: 정렬할 문자열
        width: 목표 폭 (칸 수)
        align: 정렬 방향 ("left", "right", "center")

    Returns:
        정렬된 문자열
    """
    text_str = str(text)
    current_width = get_display_width(text_str)
    padding = width - current_width

    if padding <= 0:
        return text_str

    if align == "left":
        return text_str + " " * padding
    elif align == "right":
        return " " * padding + text_str
    else:  # center
        left_pad = padding // 2
        right_pad = padding - left_pad
        return " " * left_pad + text_str + " " * right_pad


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
            logger.debug(f"  승/패: {summary['winning_trades']}/{summary['losing_trades']}")
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

    # 컬럼 폭 정의 (터미널 칸 수 기준)
    col_entry_date = 12  # "진입일" (6칸) + YYYY-MM-DD
    col_exit_date = 12  # "청산일" (6칸) + YYYY-MM-DD
    col_entry_price = 12  # "진입가" (6칸) + 숫자
    col_exit_price = 12  # "청산가" (6칸) + 숫자
    col_pnl = 14  # "손익률" (6칸) + 숫자 + %
    col_reason = 16  # "사유" (4칸) + 텍스트

    # 전체 테이블 폭 계산 (들여쓰기 2칸 + 컬럼들)
    total_width = 2 + col_entry_date + col_exit_date + col_entry_price + col_exit_price + col_pnl + col_reason

    logger.debug("=" * total_width)
    logger.debug(f"[{title}] 거래 내역 (최근 {max_rows}건)")

    # 헤더 출력
    header = (
        "  "
        + format_cell("진입일", col_entry_date, "left")
        + format_cell("청산일", col_exit_date, "left")
        + format_cell("진입가", col_entry_price, "right")
        + format_cell("청산가", col_exit_price, "right")
        + format_cell("손익률", col_pnl, "right")
        + format_cell("사유", col_reason, "right")
    )
    logger.debug(header)
    logger.debug("-" * total_width)

    # 데이터 행 출력
    for _, trade in trades_df.tail(max_rows).iterrows():
        entry_price_str = f"{trade['entry_price']:.2f}"
        exit_price_str = f"{trade['exit_price']:.2f}"
        pnl_str = f"{trade['pnl_pct'] * 100:+.2f}%"

        row = (
            "  "
            + format_cell(str(trade["entry_date"]), col_entry_date, "left")
            + format_cell(str(trade["exit_date"]), col_exit_date, "left")
            + format_cell(entry_price_str, col_entry_price, "right")
            + format_cell(exit_price_str, col_exit_price, "right")
            + format_cell(pnl_str, col_pnl, "right")
            + format_cell(trade["exit_reason"], col_reason, "right")
        )
        logger.debug(row)

    logger.debug("=" * total_width)


def print_comparison_table(summaries: list[tuple[str, dict]], logger: Logger) -> None:
    """
    전략 비교 테이블을 출력한다.

    Args:
        summaries: [(전략명, summary_dict), ...] 리스트
        logger: 로거 인스턴스
    """
    # 컬럼 폭 정의 (터미널 칸 수 기준)
    col_strategy = 20  # "전략" (4칸) + 여유
    col_return = 12  # "총수익률" (8칸) + 숫자
    col_cagr = 10  # "CAGR" (4칸) + 숫자
    col_mdd = 10  # "MDD" (6칸) + 숫자
    col_trades = 10  # "거래수" (6칸) + 숫자

    # 전체 테이블 폭 계산 (들여쓰기 2칸 + 컬럼들)
    total_width = 2 + col_strategy + col_return + col_cagr + col_mdd + col_trades

    logger.debug("=" * total_width)
    logger.debug("[전략 비교 요약]")

    # 헤더 출력
    header = (
        "  "
        + format_cell("전략", col_strategy, "left")
        + format_cell("총수익률", col_return, "right")
        + format_cell("CAGR", col_cagr, "right")
        + format_cell("MDD", col_mdd, "right")
        + format_cell("거래수", col_trades, "right")
    )
    logger.debug(header)
    logger.debug("-" * total_width)

    # 데이터 행 출력
    for name, summary in summaries:
        return_str = f"{summary['total_return_pct']:.2f}%"
        cagr_str = f"{summary['cagr']:.2f}%"
        mdd_str = f"{summary['mdd']:.2f}%"
        trades_str = str(summary["total_trades"])

        row = (
            "  "
            + format_cell(name, col_strategy, "left")
            + format_cell(return_str, col_return, "right")
            + format_cell(cagr_str, col_cagr, "right")
            + format_cell(mdd_str, col_mdd, "right")
            + format_cell(trades_str, col_trades, "right")
        )
        logger.debug(row)

    logger.debug("=" * total_width)
