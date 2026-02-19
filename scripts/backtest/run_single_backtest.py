"""
단일 백테스트 실행 스크립트

전략별 백테스트를 실행하고 결과를 저장한다.
--strategy 인자로 실행할 전략을 선택할 수 있다.

실행 명령어:
    poetry run python scripts/backtest/run_single_backtest.py
    poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone
    poetry run python scripts/backtest/run_single_backtest.py --strategy buy_and_hold
"""

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from typing import Any

import pandas as pd

from qbt.backtest.strategies import buffer_zone, buy_and_hold
from qbt.backtest.types import SingleBacktestResult
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    EPSILON,
    META_JSON_PATH,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# 전략 레지스트리
STRATEGY_RUNNERS: dict[str, Callable[[pd.DataFrame, pd.DataFrame], SingleBacktestResult]] = {
    buffer_zone.STRATEGY_NAME: buffer_zone.run_single,
    buy_and_hold.STRATEGY_NAME: buy_and_hold.run_single,
}


def print_summary(summary: Mapping[str, object], title: str) -> None:
    """
    요약 지표를 출력한다.

    Args:
        summary: 요약 지표 딕셔너리
        title: 출력 제목
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


def _calculate_monthly_returns(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """
    에쿼티 데이터로부터 월별 수익률을 계산한다.

    Args:
        equity_df: 자본 곡선 DataFrame (Date, equity 컬럼 필수)

    Returns:
        월별 수익률 리스트 [{year, month, return_pct}, ...]
    """
    if equity_df.empty or len(equity_df) < 2:
        return []

    # 1. 에쿼티 데이터를 날짜 인덱스로 변환
    eq = equity_df[[COL_DATE, "equity"]].copy()
    eq[COL_DATE] = pd.to_datetime(eq[COL_DATE])
    eq = eq.set_index(COL_DATE)

    # 2. 월말 리샘플링
    monthly_equity = eq["equity"].resample("ME").last().dropna()
    if len(monthly_equity) < 2:
        return []

    # 3. 월간 수익률 계산 (%)
    monthly_returns = monthly_equity.pct_change().dropna() * 100

    # 4. 결과 리스트 생성
    dt_index = pd.DatetimeIndex(monthly_returns.index)
    result: list[dict[str, object]] = []
    for i in range(len(monthly_returns)):
        result.append(
            {
                "year": int(dt_index[i].year),
                "month": int(dt_index[i].month),
                "return_pct": round(float(monthly_returns.iloc[i]), 2),
            }
        )

    return result


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    QQQ, TQQQ 데이터를 로딩하고 공통 날짜로 정렬한다.

    Returns:
        tuple: (signal_df, trade_df)
    """
    logger.debug(f"시그널 데이터: {QQQ_DATA_PATH}")
    logger.debug(f"매매 데이터: {TQQQ_SYNTHETIC_DATA_PATH}")
    signal_df = load_stock_data(QQQ_DATA_PATH)
    trade_df = load_stock_data(TQQQ_SYNTHETIC_DATA_PATH)

    logger.debug("=" * 60)
    logger.debug("데이터 로딩 완료")
    logger.debug(f"시그널(QQQ) 행 수: {len(signal_df):,}, 기간: {signal_df[COL_DATE].min()} ~ {signal_df[COL_DATE].max()}")
    logger.debug(f"매매(TQQQ) 행 수: {len(trade_df):,}, 기간: {trade_df[COL_DATE].min()} ~ {trade_df[COL_DATE].max()}")
    logger.debug("=" * 60)

    # 공통 날짜로 정렬
    common_dates = set(signal_df[COL_DATE]) & set(trade_df[COL_DATE])
    signal_df = signal_df[signal_df[COL_DATE].isin(common_dates)].reset_index(drop=True)
    trade_df = trade_df[trade_df[COL_DATE].isin(common_dates)].reset_index(drop=True)
    logger.debug(f"공통 기간: {len(signal_df):,}행")

    return signal_df, trade_df


def _save_results(result: SingleBacktestResult) -> None:
    """
    백테스트 결과를 CSV/JSON 파일로 저장한다.

    컬럼 감지 기반 반올림:
    - 가격 (OHLC, MA, 밴드): 6자리
    - 자본금 (equity, pnl): 정수
    - 백분율 (change_pct, drawdown_pct): 2자리
    - 비율 (pnl_pct, buffer_zone_pct): 4자리

    Args:
        result: SingleBacktestResult 컨테이너
    """
    # 결과 디렉토리 생성
    result.result_dir.mkdir(parents=True, exist_ok=True)

    signal_path = result.result_dir / "signal.csv"
    equity_path = result.result_dir / "equity.csv"
    trades_path = result.result_dir / "trades.csv"
    summary_path = result.result_dir / "summary.json"

    # 1. signal CSV 저장 (OHLC + MA + change_pct)
    signal_export = result.signal_df.copy()
    signal_export["change_pct"] = signal_export[COL_CLOSE].pct_change() * 100

    # 컬럼 감지 기반 반올림 (가격 6자리, MA 6자리, % 2자리)
    signal_round: dict[str, int] = {"change_pct": 2}
    for col in [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]:
        if col in signal_export.columns:
            signal_round[col] = 6
    for col in signal_export.columns:
        if col.startswith("ma_"):
            signal_round[col] = 6

    signal_export = signal_export.round(signal_round)
    signal_export.to_csv(signal_path, index=False)
    logger.debug(f"시그널 데이터 저장 완료: {signal_path}")

    # 2. equity CSV 저장 (equity + drawdown_pct + 전략별 컬럼)
    equity_export = result.equity_df.copy()
    equity_series = equity_export["equity"].astype(float)
    peak = equity_series.cummax()
    safe_peak = peak.replace(0, EPSILON)
    equity_export["drawdown_pct"] = (equity_series - peak) / safe_peak * 100

    # 컬럼 감지 기반 반올림 (equity 정수, 밴드 6자리, 비율 4자리)
    equity_round: dict[str, int] = {"equity": 0, "drawdown_pct": 2}
    if "buffer_zone_pct" in equity_export.columns:
        equity_round["buffer_zone_pct"] = 4
    if "upper_band" in equity_export.columns:
        equity_round["upper_band"] = 6
    if "lower_band" in equity_export.columns:
        equity_round["lower_band"] = 6

    equity_export = equity_export.round(equity_round)
    equity_export["equity"] = equity_export["equity"].astype(int)
    equity_export.to_csv(equity_path, index=False)
    logger.debug(f"에쿼티 데이터 저장 완료: {equity_path}")

    # 3. trades CSV 저장 (거래 내역 + holding_days)
    if not result.trades_df.empty:
        trades_export = result.trades_df.copy()
        # holding_days 추가 (entry_date/exit_date 존재 시)
        if "entry_date" in trades_export.columns and "exit_date" in trades_export.columns:
            trades_export["holding_days"] = trades_export.apply(
                lambda row: (row["exit_date"] - row["entry_date"]).days, axis=1
            )
        # 컬럼 감지 기반 반올림
        trades_round: dict[str, int] = {}
        if "entry_price" in trades_export.columns:
            trades_round["entry_price"] = 6
        if "exit_price" in trades_export.columns:
            trades_round["exit_price"] = 6
        if "pnl" in trades_export.columns:
            trades_round["pnl"] = 0
        if "pnl_pct" in trades_export.columns:
            trades_round["pnl_pct"] = 4
        if "buffer_zone_pct" in trades_export.columns:
            trades_round["buffer_zone_pct"] = 4

        trades_export = trades_export.round(trades_round)
        if "pnl" in trades_export.columns:
            trades_export["pnl"] = trades_export["pnl"].astype(int)
        trades_export.to_csv(trades_path, index=False)
    else:
        result.trades_df.to_csv(trades_path, index=False)
    logger.debug(f"거래 내역 저장 완료: {trades_path}")

    # 4. summary JSON 저장
    monthly_returns = _calculate_monthly_returns(result.equity_df)

    summary_data: dict[str, Any] = {
        "summary": {
            "initial_capital": round(float(str(result.summary["initial_capital"]))),
            "final_capital": round(float(str(result.summary["final_capital"]))),
            "total_return_pct": round(float(str(result.summary["total_return_pct"])), 2),
            "cagr": round(float(str(result.summary["cagr"])), 2),
            "mdd": round(float(str(result.summary["mdd"])), 2),
            "total_trades": result.summary["total_trades"],
            "winning_trades": result.summary.get("winning_trades", 0),
            "losing_trades": result.summary.get("losing_trades", 0),
            "win_rate": round(float(str(result.summary["win_rate"])), 2),
            "start_date": result.summary.get("start_date", ""),
            "end_date": result.summary.get("end_date", ""),
        },
        "params": result.params_json,
        "monthly_returns": monthly_returns,
        "data_info": {
            "signal_path": str(QQQ_DATA_PATH),
            "trade_path": str(TQQQ_SYNTHETIC_DATA_PATH),
        },
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    logger.debug(f"요약 JSON 저장 완료: {summary_path}")

    # 5. 메타데이터 저장
    metadata: dict[str, Any] = {
        "params": result.params_json,
        "results_summary": {
            "total_return_pct": round(float(str(result.summary["total_return_pct"])), 2),
            "cagr": round(float(str(result.summary["cagr"])), 2),
            "mdd": round(float(str(result.summary["mdd"])), 2),
            "total_trades": int(str(result.summary["total_trades"])),
            "win_rate": round(float(str(result.summary["win_rate"])), 2),
        },
        "output_files": {
            "signal_csv": str(signal_path),
            "equity_csv": str(equity_path),
            "trades_csv": str(trades_path),
            "summary_json": str(summary_path),
        },
    }
    save_metadata("single_backtest", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")


def _print_trades_table(result: SingleBacktestResult) -> None:
    """
    거래 내역 테이블을 출력한다.

    Args:
        result: SingleBacktestResult 컨테이너
    """
    if not result.trades_df.empty:
        columns = [
            ("진입일", 12, Align.LEFT),
            ("청산일", 12, Align.LEFT),
            ("진입가", 12, Align.RIGHT),
            ("청산가", 12, Align.RIGHT),
            ("손익률", 14, Align.RIGHT),
        ]

        max_rows = 10
        rows = []
        for _, trade in result.trades_df.tail(max_rows).iterrows():
            rows.append(
                [
                    str(trade["entry_date"]),
                    str(trade["exit_date"]),
                    f"{trade['entry_price']:.6f}",
                    f"{trade['exit_price']:.6f}",
                    f"{trade['pnl_pct'] * 100:+.2f}%",
                ]
            )

        table = TableLogger(columns, logger)
        table.print_table(rows, title=f"[{result.display_name}] 거래 내역 (최근 {max_rows}건)")
    else:
        logger.debug(f"[{result.display_name}] 거래 내역 없음")


def _print_comparison_table(results: list[SingleBacktestResult]) -> None:
    """
    전략 비교 요약 테이블을 출력한다.

    Args:
        results: SingleBacktestResult 리스트 (2개 이상일 때만 출력)
    """
    if len(results) < 2:
        return

    columns = [
        ("전략", 20, Align.LEFT),
        ("총수익률", 12, Align.RIGHT),
        ("CAGR", 10, Align.RIGHT),
        ("MDD", 10, Align.RIGHT),
        ("거래수", 10, Align.RIGHT),
    ]

    rows = []
    for result in results:
        rows.append(
            [
                result.display_name,
                f"{result.summary['total_return_pct']:.2f}%",
                f"{result.summary['cagr']:.2f}%",
                f"{result.summary['mdd']:.2f}%",
                str(result.summary["total_trades"]),
            ]
        )

    table = TableLogger(columns, logger)
    table.print_table(rows, title="[전략 비교 요약]")


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. argparse로 --strategy 파싱
    parser = argparse.ArgumentParser(description="단일 백테스트 실행")
    parser.add_argument(
        "--strategy",
        choices=["all", *STRATEGY_RUNNERS.keys()],
        default="all",
        help="실행할 전략 (기본값: all)",
    )
    args = parser.parse_args()

    # 2. 데이터 로딩
    signal_df, trade_df = _load_data()

    # 3. 전략 목록 결정
    if args.strategy == "all":
        strategy_names = list(STRATEGY_RUNNERS.keys())
    else:
        strategy_names = [args.strategy]

    logger.debug(f"실행 전략: {strategy_names}")

    # 4. 전략별 실행
    results: list[SingleBacktestResult] = []
    for name in strategy_names:
        logger.debug("=" * 60)
        result = STRATEGY_RUNNERS[name](signal_df.copy(), trade_df.copy())
        print_summary(result.summary, result.display_name)
        _print_trades_table(result)
        _save_results(result)
        results.append(result)
        logger.debug(f"{result.display_name} 결과 파일 저장 완료")

    # 5. 비교 테이블 출력 (2개 이상 시)
    _print_comparison_table(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
