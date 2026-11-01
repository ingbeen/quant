"""
버퍼존 세 줄 실행 스크립트

돈을 3등분해 매도선만 다르게 둔 규칙을 투자자별로 돌려 요약 · 매도 내역 · 고원 · 일별 자산을 저장한다.
합격 · 불합격을 내지 않는다 (계산: buffer_zone_three_lines). 닷컴 경험 투자자의 2 · 3배는 여기서 메모리로 합성한다.

선행: 시세 `^NDX` · TQQQ · QLD 합성, storage/etc 의 금리 · 운용비율 파일 (docs/COMMANDS.md)

실행 명령어:
    poetry run python scripts/backtest/run_buffer_zone_three_lines.py
"""

import sys
import time

import pandas as pd

from qbt.backtest.buffer_zone_sensitivity import (
    CSV_ENCODING,
    DISPLAY_BH_CAGR,
    DISPLAY_BH_MDD,
    DISPLAY_CAGR,
    DISPLAY_CLOSED,
    DISPLAY_MDD,
)
from qbt.backtest.buffer_zone_three_lines import (
    CASES,
    DISPLAY_BH_FINAL,
    DISPLAY_DOTCOM,
    DISPLAY_FINAL,
    DISPLAY_FIRST_BUY,
    DISPLAY_INVESTOR,
    DISPLAY_LEVERAGE,
    EQUITY_FILENAME,
    INVESTORS_FILENAME,
    PLATEAU_FILENAME,
    THREE_LINES_RESULTS_DIR,
    THREE_LINES_TRADES_FILENAME,
    ThreeLinesCase,
    ThreeLinesTables,
    evaluate_case,
    round_three_lines_csv,
)
from qbt.tqqq.constants import (
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    FFR_PRE1999_DATA_PATH,
    LONG_HISTORY_SPREAD_CAP,
)
from qbt.tqqq.data_loader import load_monthly_data
from qbt.tqqq.simulation import simulate_long_history
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.parallel_executor import execute_parallel_with_kwargs

logger = get_logger(__name__)


def _load_price(case: ThreeLinesCase, ffr_df: pd.DataFrame, expense_df: pd.DataFrame) -> pd.DataFrame:
    """판의 시세. 합성 판은 지금 비용 모델로 만들고, 비용 상한 판만 가산금리를 깎는다.

    Args:
        case: 투자자와 배수
        ffr_df: 시세 전 구간을 덮는 월별 금리
        expense_df: 월별 운용비율

    Returns:
        시세 표
    """
    price_df = load_stock_data(case.data_path)
    if not case.synthetic:
        return price_df
    spread_cap = LONG_HISTORY_SPREAD_CAP if case.capped_cost else None
    return simulate_long_history(price_df, float(case.leverage), ffr_df, expense_df, spread_cap=spread_cap)


def _print_investor_table(investors_df: pd.DataFrame) -> None:
    """투자자별 결과를 터미널에 출력한다.

    Args:
        investors_df: 반올림한 투자자 표
    """
    columns = [
        ("투자자", 24, Align.LEFT),
        ("배수", 6, Align.RIGHT),
        ("첫 매수", 12, Align.RIGHT),
        ("최종", 11, Align.RIGHT),
        ("연복리", 9, Align.RIGHT),
        ("최대 낙폭", 10, Align.RIGHT),
        ("닷컴 낙폭", 10, Align.RIGHT),
        ("끝난 거래", 10, Align.RIGHT),
        ("B&H 최종", 11, Align.RIGHT),
        ("B&H 연복리", 11, Align.RIGHT),
        ("B&H 낙폭", 10, Align.RIGHT),
    ]
    rows = [
        [
            str(row[DISPLAY_INVESTOR]),
            f"{row[DISPLAY_LEVERAGE]}배",
            str(row[DISPLAY_FIRST_BUY]),
            f"{row[DISPLAY_FINAL]:.1f}배",
            f"{row[DISPLAY_CAGR]:.2f}%",
            f"{row[DISPLAY_MDD]:.2f}%",
            "—" if pd.isna(row[DISPLAY_DOTCOM]) else f"{row[DISPLAY_DOTCOM]:.2f}%",
            str(row[DISPLAY_CLOSED]),
            f"{row[DISPLAY_BH_FINAL]:.1f}배",
            f"{row[DISPLAY_BH_CAGR]:.2f}%",
            f"{row[DISPLAY_BH_MDD]:.2f}%",
        ]
        for _, row in investors_df.iterrows()
    ]
    TableLogger(columns, logger).print_table(rows, title="[투자자별 결과]")


@cli_exception_handler
def main() -> int:
    """메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 시세 준비 — 금리 두 파일은 겹치는 달이 없고, 겹치면 월별 딕셔너리를 만들 때 멈춤
    ffr_df = pd.concat(
        [load_monthly_data(FFR_PRE1999_DATA_PATH), load_monthly_data(FFR_DATA_PATH)],
        ignore_index=True,
    )
    expense_df = load_monthly_data(EXPENSE_RATIO_DATA_PATH)
    inputs = [{"case": case, "price_df": _load_price(case, ffr_df, expense_df)} for case in CASES]

    # 2. 판별 병렬 실행 — 고원이 있는 판은 백테스트 수십 번이라 순차로는 2분을 넘음
    started = time.perf_counter()
    results: list[ThreeLinesTables] = execute_parallel_with_kwargs(func=evaluate_case, inputs=inputs)
    logger.debug(f"실행 완료: 판 {len(results)}개, {time.perf_counter() - started:.1f}초")

    # 3. 저장
    investors_df = round_three_lines_csv(pd.DataFrame([tables.investor_row for tables in results]))
    equities = [tables.equity for tables in results if not tables.equity.empty]
    THREE_LINES_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for filename, df in (
        (INVESTORS_FILENAME, investors_df),
        (THREE_LINES_TRADES_FILENAME, round_three_lines_csv(pd.DataFrame([r for t in results for r in t.trades]))),
        (PLATEAU_FILENAME, round_three_lines_csv(pd.DataFrame([r for t in results for r in t.plateau]))),
        (EQUITY_FILENAME, round_three_lines_csv(pd.concat(equities, ignore_index=True))),
    ):
        path = THREE_LINES_RESULTS_DIR / filename
        df.to_csv(path, index=False, encoding=CSV_ENCODING)
        logger.debug(f"저장 완료: {path} ({len(df):,}행)")

    _print_investor_table(investors_df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
