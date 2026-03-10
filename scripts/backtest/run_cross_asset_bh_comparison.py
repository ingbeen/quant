"""
Cross-Asset Buy & Hold 벤치마크 비교 스크립트

7개 자산(QQQ, SPY, IWM, EFA, EEM, GLD, TLT)의 Buy & Hold 백테스트를 실행하고,
기존 버퍼존 전략 결과와 비교 테이블을 생성한다.

산출물:
    - cross_asset_bh_comparison.csv: 전략 vs B&H 비교 테이블
    - cross_asset_bh_detail.csv: B&H 상세 결과
    - 각 자산별 B&H 결과 (signal.csv, equity.csv, trades.csv, summary.json)

실행 명령어:
    poetry run python scripts/backtest/run_cross_asset_bh_comparison.py
"""

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from qbt.backtest.analysis import calculate_monthly_returns
from qbt.backtest.strategies import buy_and_hold
from qbt.backtest.types import SingleBacktestResult
from qbt.common_constants import (
    BACKTEST_RESULTS_DIR,
    BUFFER_ZONE_EEM_RESULTS_DIR,
    BUFFER_ZONE_EFA_RESULTS_DIR,
    BUFFER_ZONE_GLD_RESULTS_DIR,
    BUFFER_ZONE_IWM_RESULTS_DIR,
    BUFFER_ZONE_QQQ_RESULTS_DIR,
    BUFFER_ZONE_SPY_RESULTS_DIR,
    BUFFER_ZONE_TLT_RESULTS_DIR,
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    EPSILON,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)


# ============================================================================
# 비교 대상 정의
# ============================================================================

# 티커 → 버퍼존 전략 결과 디렉토리 매핑
_STRATEGY_DIR_MAP: dict[str, Path] = {
    "QQQ": BUFFER_ZONE_QQQ_RESULTS_DIR,
    "SPY": BUFFER_ZONE_SPY_RESULTS_DIR,
    "IWM": BUFFER_ZONE_IWM_RESULTS_DIR,
    "EFA": BUFFER_ZONE_EFA_RESULTS_DIR,
    "EEM": BUFFER_ZONE_EEM_RESULTS_DIR,
    "GLD": BUFFER_ZONE_GLD_RESULTS_DIR,
    "TLT": BUFFER_ZONE_TLT_RESULTS_DIR,
}

# 비교 대상 7개 자산 (순서 고정)
_TARGET_TICKERS = ["QQQ", "SPY", "IWM", "EFA", "EEM", "GLD", "TLT"]


# ============================================================================
# B&H 결과 저장 함수
# ============================================================================


def _save_bh_results(result: SingleBacktestResult) -> None:
    """
    B&H 백테스트 결과를 CSV/JSON으로 저장한다.

    signal.csv, equity.csv, trades.csv, summary.json을 저장한다.

    Args:
        result: B&H 백테스트 결과 컨테이너
    """
    result.result_dir.mkdir(parents=True, exist_ok=True)

    # 1. signal.csv
    signal_export = result.signal_df.copy()
    signal_export["change_pct"] = signal_export[COL_CLOSE].pct_change() * 100
    signal_round: dict[str, int] = {"change_pct": 2}
    for col in [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]:
        if col in signal_export.columns:
            signal_round[col] = 6
    signal_export = signal_export.round(signal_round)
    signal_export.to_csv(result.result_dir / "signal.csv", index=False)

    # 2. equity.csv
    equity_export = result.equity_df.copy()
    equity_series = equity_export["equity"].astype(float)
    peak = equity_series.cummax()
    safe_peak = peak.replace(0, EPSILON)
    equity_export["drawdown_pct"] = (equity_series - peak) / safe_peak * 100
    equity_round: dict[str, int] = {"equity": 0, "drawdown_pct": 2}
    equity_export = equity_export.round(equity_round)
    equity_export["equity"] = equity_export["equity"].astype(int)
    equity_export.to_csv(result.result_dir / "equity.csv", index=False)

    # 3. trades.csv (B&H는 빈 DataFrame)
    result.trades_df.to_csv(result.result_dir / "trades.csv", index=False)

    # 4. summary.json
    monthly_returns = calculate_monthly_returns(result.equity_df)
    summary_dict: dict[str, Any] = {
        "initial_capital": round(float(str(result.summary["initial_capital"]))),
        "final_capital": round(float(str(result.summary["final_capital"]))),
        "total_return_pct": round(float(str(result.summary["total_return_pct"])), 2),
        "cagr": round(float(str(result.summary["cagr"])), 2),
        "mdd": round(float(str(result.summary["mdd"])), 2),
        "calmar": round(float(str(result.summary["calmar"])), 2),
        "total_trades": result.summary["total_trades"],
        "winning_trades": result.summary.get("winning_trades", 0),
        "losing_trades": result.summary.get("losing_trades", 0),
        "win_rate": round(float(str(result.summary.get("win_rate", 0.0))), 2),
        "start_date": result.summary.get("start_date", ""),
        "end_date": result.summary.get("end_date", ""),
    }

    open_position_raw = result.summary.get("open_position")
    if open_position_raw is not None and isinstance(open_position_raw, dict):
        summary_dict["open_position"] = {
            "entry_date": str(open_position_raw["entry_date"]),
            "entry_price": round(float(str(open_position_raw["entry_price"])), 6),
            "shares": int(str(open_position_raw["shares"])),
        }

    summary_data: dict[str, Any] = {
        "display_name": result.display_name,
        "summary": summary_dict,
        "params": result.params_json,
        "monthly_returns": monthly_returns,
        "regime_summaries": [],
        "data_info": result.data_info,
    }

    summary_path = result.result_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    logger.debug(f"B&H 결과 저장 완료: {result.result_dir}")


# ============================================================================
# 전략 결과 로딩
# ============================================================================


def _load_strategy_summary(strategy_dir: Path) -> dict[str, Any] | None:
    """
    버퍼존 전략의 summary.json에서 성과 지표를 로드한다.

    Args:
        strategy_dir: 전략 결과 디렉토리

    Returns:
        summary 딕셔너리 (없으면 None)
    """
    summary_path = strategy_dir / "summary.json"
    if not summary_path.exists():
        logger.debug(f"전략 summary.json 없음: {summary_path}")
        return None

    with summary_path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    return data.get("summary", None)


# ============================================================================
# 비교 테이블 생성
# ============================================================================


def _extract_ticker(strategy_name: str) -> str:
    """strategy_name에서 티커를 추출한다 (예: buy_and_hold_qqq → QQQ)."""
    return strategy_name.replace("buy_and_hold_", "").upper()


def _calculate_calmar_advantage(strategy_calmar: float, bh_calmar: float) -> str:
    """
    Calmar 우위를 계산한다.

    (strategy_calmar / bh_calmar - 1) * 100으로 계산하며,
    B&H Calmar가 0 이하이면 "N/A"를 반환한다.

    Args:
        strategy_calmar: 전략의 Calmar 비율
        bh_calmar: B&H의 Calmar 비율

    Returns:
        Calmar 우위 문자열 (예: "150.0" 또는 "N/A")
    """
    if bh_calmar <= 0:
        return "N/A"
    advantage = (strategy_calmar / bh_calmar - 1) * 100
    return f"{advantage:.1f}"


def _build_comparison_table(
    bh_results: dict[str, SingleBacktestResult],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    B&H 결과와 전략 결과를 병합하여 비교 테이블 데이터를 생성한다.

    Args:
        bh_results: 티커 → B&H 결과 매핑

    Returns:
        tuple: (comparison_rows, detail_rows)
    """
    comparison_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    for ticker in _TARGET_TICKERS:
        result = bh_results[ticker]

        bh_cagr = round(float(str(result.summary["cagr"])), 2)
        bh_mdd = round(float(str(result.summary["mdd"])), 2)
        bh_calmar = round(float(str(result.summary["calmar"])), 2)

        # B&H 상세 행
        detail_rows.append(
            {
                "asset": ticker,
                "cagr": bh_cagr,
                "mdd": bh_mdd,
                "calmar": bh_calmar,
                "period_start": result.summary.get("start_date", ""),
                "period_end": result.summary.get("end_date", ""),
                "total_return_pct": round(float(str(result.summary["total_return_pct"])), 2),
                "final_capital": round(float(str(result.summary["final_capital"]))),
            }
        )

        # 전략 summary 로드
        strategy_dir = _STRATEGY_DIR_MAP[ticker]
        strategy_summary = _load_strategy_summary(strategy_dir)

        if strategy_summary:
            s_cagr = round(float(str(strategy_summary["cagr"])), 2)
            s_mdd = round(float(str(strategy_summary["mdd"])), 2)
            s_calmar = round(float(str(strategy_summary["calmar"])), 2)
        else:
            logger.debug(f"{ticker}: 버퍼존 전략 결과 없음 (0으로 대체)")
            s_cagr = 0.0
            s_mdd = 0.0
            s_calmar = 0.0

        calmar_adv = _calculate_calmar_advantage(s_calmar, bh_calmar)

        comparison_rows.append(
            {
                "asset": ticker,
                "strategy_cagr": s_cagr,
                "strategy_mdd": s_mdd,
                "strategy_calmar": s_calmar,
                "bh_cagr": bh_cagr,
                "bh_mdd": bh_mdd,
                "bh_calmar": bh_calmar,
                "calmar_advantage_pct": calmar_adv,
            }
        )

    return comparison_rows, detail_rows


def _save_comparison_csvs(
    comparison_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
) -> tuple[Path, Path]:
    """
    비교 테이블과 상세 테이블을 CSV로 저장한다.

    Args:
        comparison_rows: 비교 테이블 행 리스트
        detail_rows: B&H 상세 테이블 행 리스트

    Returns:
        tuple: (비교 CSV 경로, 상세 CSV 경로)
    """
    comparison_path = BACKTEST_RESULTS_DIR / "cross_asset_bh_comparison.csv"
    detail_path = BACKTEST_RESULTS_DIR / "cross_asset_bh_detail.csv"

    pd.DataFrame(comparison_rows).to_csv(comparison_path, index=False)
    pd.DataFrame(detail_rows).to_csv(detail_path, index=False)

    logger.debug(f"비교 테이블 저장: {comparison_path}")
    logger.debug(f"B&H 상세 테이블 저장: {detail_path}")

    return comparison_path, detail_path


def _print_comparison_table(comparison_rows: list[dict[str, Any]]) -> None:
    """
    비교 테이블을 터미널에 출력한다.

    Args:
        comparison_rows: 비교 테이블 행 리스트
    """
    columns = [
        ("자산", 8, Align.LEFT),
        ("전략CAGR", 12, Align.RIGHT),
        ("전략MDD", 12, Align.RIGHT),
        ("전략Calmar", 13, Align.RIGHT),
        ("B&H CAGR", 12, Align.RIGHT),
        ("B&H MDD", 12, Align.RIGHT),
        ("B&H Calmar", 12, Align.RIGHT),
        ("Calmar우위", 13, Align.RIGHT),
    ]

    rows = []
    for row in comparison_rows:
        calmar_adv_str = row["calmar_advantage_pct"]
        if calmar_adv_str != "N/A":
            calmar_adv_str = f"{calmar_adv_str}%"

        rows.append(
            [
                row["asset"],
                f"{row['strategy_cagr']:.2f}%",
                f"{row['strategy_mdd']:.2f}%",
                f"{row['strategy_calmar']:.2f}",
                f"{row['bh_cagr']:.2f}%",
                f"{row['bh_mdd']:.2f}%",
                f"{row['bh_calmar']:.2f}",
                calmar_adv_str,
            ]
        )

    table = TableLogger(columns, logger)
    table.print_table(rows, title="[Cross-Asset] 전략 vs Buy & Hold 비교")


def _print_detail_table(detail_rows: list[dict[str, Any]]) -> None:
    """
    B&H 상세 테이블을 터미널에 출력한다.

    Args:
        detail_rows: B&H 상세 테이블 행 리스트
    """
    columns = [
        ("자산", 8, Align.LEFT),
        ("CAGR", 10, Align.RIGHT),
        ("MDD", 10, Align.RIGHT),
        ("Calmar", 10, Align.RIGHT),
        ("시작일", 14, Align.LEFT),
        ("종료일", 14, Align.LEFT),
        ("총수익률", 14, Align.RIGHT),
        ("최종자본", 16, Align.RIGHT),
    ]

    rows = []
    for row in detail_rows:
        rows.append(
            [
                row["asset"],
                f"{row['cagr']:.2f}%",
                f"{row['mdd']:.2f}%",
                f"{row['calmar']:.2f}",
                str(row["period_start"]),
                str(row["period_end"]),
                f"{row['total_return_pct']:.2f}%",
                f"{row['final_capital']:,.0f}",
            ]
        )

    table = TableLogger(columns, logger)
    table.print_table(rows, title="[Cross-Asset] Buy & Hold 상세 결과")


# ============================================================================
# 메인 실행
# ============================================================================


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    logger.debug("Cross-Asset Buy & Hold 벤치마크 비교 시작")

    # 1. B&H config에서 대상 자산 필터링
    target_configs = [
        config for config in buy_and_hold.CONFIGS if _extract_ticker(config.strategy_name) in _TARGET_TICKERS
    ]

    if len(target_configs) != len(_TARGET_TICKERS):
        found = {_extract_ticker(c.strategy_name) for c in target_configs}
        missing = set(_TARGET_TICKERS) - found
        raise ValueError(f"B&H CONFIGS에서 누락된 자산: {missing}")

    # 2. 7개 자산 B&H 실행 및 저장
    bh_results: dict[str, SingleBacktestResult] = {}
    for config in target_configs:
        ticker = _extract_ticker(config.strategy_name)
        logger.debug(f"B&H 실행 중: {ticker}")

        runner = buy_and_hold.create_runner(config)
        result = runner()
        _save_bh_results(result)

        bh_results[ticker] = result
        logger.debug(
            f"  {ticker} B&H: CAGR={result.summary['cagr']:.2f}%, "
            f"MDD={result.summary['mdd']:.2f}%, "
            f"Calmar={result.summary['calmar']:.2f}"
        )

    # 3. 비교 테이블 구성
    comparison_rows, detail_rows = _build_comparison_table(bh_results)

    # 4. CSV 저장
    comparison_path, detail_path = _save_comparison_csvs(comparison_rows, detail_rows)

    # 5. 터미널 출력
    _print_detail_table(detail_rows)
    _print_comparison_table(comparison_rows)

    # 6. 메타데이터 저장
    metadata: dict[str, Any] = {
        "assets": _TARGET_TICKERS,
        "output_files": {
            "comparison_csv": str(comparison_path),
            "detail_csv": str(detail_path),
        },
    }
    save_metadata("cross_asset_bh_comparison", metadata)

    logger.debug("Cross-Asset Buy & Hold 벤치마크 비교 완료")

    return 0


if __name__ == "__main__":
    sys.exit(main())
