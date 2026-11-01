"""
버퍼존 규칙 민감도 실행 스크립트

매도 폭 · 매수 폭 · 이평선 기간 · 한달 길이를 하나씩 바꾼 결과와 규칙 조합을 저장한다.
합격 · 불합격을 내지 않는다 — 결과를 보고 과최적화인지 판단한다 (계산: buffer_zone_sensitivity).

선행: 시세 `^GSPC` · `^NDX` · `^IXIC` (docs/COMMANDS.md)

실행 명령어:
    poetry run python scripts/backtest/run_buffer_zone_sensitivity.py
"""

import sys
import time

import pandas as pd

from qbt.backtest.buffer_zone_sensitivity import (
    CELLS_FILENAME,
    CSV_ENCODING,
    DATASETS,
    DISPLAY_BH_CAGR,
    DISPLAY_BH_MDD,
    DISPLAY_CAGR,
    DISPLAY_CLOSED,
    DISPLAY_DATASET,
    DISPLAY_HELD,
    DISPLAY_MDD,
    DISPLAY_RULE,
    RULES_FILENAME,
    SENSITIVITY_RESULTS_DIR,
    TRADES_FILENAME,
    SensitivityTables,
    evaluate_dataset,
    round_for_csv,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.parallel_executor import execute_parallel_with_kwargs

logger = get_logger(__name__)


def _print_rule_table(rules_df: pd.DataFrame) -> None:
    """규칙 조합 표를 터미널에 출력한다.

    Args:
        rules_df: 반올림한 규칙 조합 표
    """
    columns = [
        ("데이터", 20, Align.LEFT),
        ("규칙", 26, Align.LEFT),
        ("연복리", 9, Align.RIGHT),
        ("최대 낙폭", 10, Align.RIGHT),
        ("끝난 거래", 10, Align.RIGHT),
        ("보유 날", 8, Align.RIGHT),
        ("B&H 연복리", 11, Align.RIGHT),
        ("B&H 낙폭", 10, Align.RIGHT),
    ]
    rows = [
        [
            str(row[DISPLAY_DATASET]),
            str(row[DISPLAY_RULE]),
            f"{row[DISPLAY_CAGR]:.2f}%",
            f"{row[DISPLAY_MDD]:.2f}%",
            str(row[DISPLAY_CLOSED]),
            f"{row[DISPLAY_HELD]:.1f}%",
            f"{row[DISPLAY_BH_CAGR]:.2f}%",
            f"{row[DISPLAY_BH_MDD]:.2f}%",
        ]
        for _, row in rules_df.iterrows()
    ]
    TableLogger(columns, logger).print_table(rows, title="[규칙 조합]")


@cli_exception_handler
def main() -> int:
    """메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 데이터별 병렬 실행 — 순차로는 9분 가까이 걸림
    started = time.perf_counter()
    results: list[SensitivityTables] = execute_parallel_with_kwargs(
        func=evaluate_dataset,
        inputs=[{"dataset": dataset, "price_df": load_stock_data(dataset.data_path)} for dataset in DATASETS],
    )
    logger.debug(f"실행 완료: 데이터 {len(results)}개, {time.perf_counter() - started:.1f}초")

    cells = [row for tables in results for row in tables.cells]
    rules = [row for tables in results for row in tables.rules]
    trades = [row for tables in results for row in tables.trades]

    # 2. 저장
    SENSITIVITY_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    rules_df = round_for_csv(pd.DataFrame(rules))
    for filename, df in (
        (CELLS_FILENAME, round_for_csv(pd.DataFrame(cells))),
        (RULES_FILENAME, rules_df),
        (TRADES_FILENAME, round_for_csv(pd.DataFrame(trades))),
    ):
        path = SENSITIVITY_RESULTS_DIR / filename
        df.to_csv(path, index=False, encoding=CSV_ENCODING)
        logger.debug(f"저장 완료: {path} ({len(df):,}행)")

    _print_rule_table(rules_df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
