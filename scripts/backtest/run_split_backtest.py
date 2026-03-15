"""분할 매수매도 백테스트 실행 스크립트

3개 트랜치(ma250/ma200/ma150)를 독립 실행 후 결과를 조합하여 저장한다.
--strategy 인자로 실행할 전략을 선택할 수 있다.

실행 명령어:
    poetry run python scripts/backtest/run_split_backtest.py
    poetry run python scripts/backtest/run_split_backtest.py --strategy split_buffer_zone_tqqq
    poetry run python scripts/backtest/run_split_backtest.py --strategy split_buffer_zone_qqq
"""

import argparse
import json
import sys
from typing import Any

from qbt.backtest.split_strategy import (
    SPLIT_CONFIGS,
    SplitStrategyResult,
    run_split_backtest,
)
from qbt.common_constants import (
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    EPSILON,
    META_JSON_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# 전략 이름 → 설정 매핑
_CONFIG_MAP = {c.strategy_name: c for c in SPLIT_CONFIGS}


def _save_signal_csv(result: SplitStrategyResult) -> None:
    """분할 전략의 시그널 데이터를 CSV로 저장한다.

    3개 MA(ma_250/200/150) + 6개 밴드(upper/lower × 3) + 전일종가대비%를 포함한다.
    밴드 계산: upper = ma × (1 + buy_buffer_zone_pct), lower = ma × (1 - sell_buffer_zone_pct)

    Args:
        result: SplitStrategyResult 컨테이너
    """
    signal_path = result.config.result_dir / "signal.csv"
    signal_export = result.signal_df.copy()

    bc = result.config.base_config
    buy_pct = bc.buy_buffer_zone_pct
    sell_pct = bc.sell_buffer_zone_pct

    # 트랜치별 밴드 계산
    for tranche in result.config.tranches:
        ma_col = f"ma_{tranche.ma_window}"
        if ma_col in signal_export.columns:
            signal_export[f"upper_band_{tranche.ma_window}"] = signal_export[ma_col] * (1 + buy_pct)
            signal_export[f"lower_band_{tranche.ma_window}"] = signal_export[ma_col] * (1 - sell_pct)

    # 전일종가대비%
    signal_export["change_pct"] = signal_export[COL_CLOSE].pct_change() * 100

    # 반올림 규칙
    signal_round: dict[str, int] = {"change_pct": 2}
    for col in [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]:
        if col in signal_export.columns:
            signal_round[col] = 6
    for col in signal_export.columns:
        if col.startswith("ma_") or col.startswith("upper_band_") or col.startswith("lower_band_"):
            signal_round[col] = 6

    signal_export = signal_export.round(signal_round)
    signal_export.to_csv(signal_path, index=False)
    logger.debug(f"시그널 데이터 저장 완료: {signal_path}")


def _save_split_results(result: SplitStrategyResult) -> None:
    """분할 매수매도 결과를 CSV/JSON 파일로 저장하고 메타데이터를 기록한다.

    Args:
        result: SplitStrategyResult 컨테이너
    """
    result.config.result_dir.mkdir(parents=True, exist_ok=True)

    # 0. signal.csv 저장
    _save_signal_csv(result)

    # 1. equity.csv 저장 (반올림 적용)
    equity_path = result.config.result_dir / "equity.csv"
    equity_export = result.combined_equity_df.copy()

    equity_round: dict[str, int] = {"equity": 0}
    for col in equity_export.columns:
        if col.endswith("_equity"):
            equity_round[col] = 0

    # drawdown_pct 추가
    equity_series = equity_export["equity"].astype(float)
    peak = equity_series.cummax()
    safe_peak = peak.replace(0, EPSILON)
    equity_export["drawdown_pct"] = (equity_series - peak) / safe_peak * 100
    equity_round["drawdown_pct"] = 2

    equity_export = equity_export.round(equity_round)
    equity_export["equity"] = equity_export["equity"].astype(int)
    for col in equity_export.columns:
        if col.endswith("_equity"):
            equity_export[col] = equity_export[col].astype(int)

    equity_export.to_csv(equity_path, index=False)
    logger.debug(f"에쿼티 데이터 저장 완료: {equity_path}")

    # 2. trades.csv 저장 (반올림 적용)
    trades_path = result.config.result_dir / "trades.csv"
    if not result.combined_trades_df.empty:
        trades_export = result.combined_trades_df.copy()
        if "entry_date" in trades_export.columns and "exit_date" in trades_export.columns:
            trades_export["holding_days"] = trades_export.apply(
                lambda row: (row["exit_date"] - row["entry_date"]).days, axis=1
            )
        trades_round: dict[str, int] = {}
        if "entry_price" in trades_export.columns:
            trades_round["entry_price"] = 6
        if "exit_price" in trades_export.columns:
            trades_round["exit_price"] = 6
        if "pnl" in trades_export.columns:
            trades_round["pnl"] = 0
        if "pnl_pct" in trades_export.columns:
            trades_round["pnl_pct"] = 4
        if "buy_buffer_pct" in trades_export.columns:
            trades_round["buy_buffer_pct"] = 4

        trades_export = trades_export.round(trades_round)
        if "pnl" in trades_export.columns:
            trades_export["pnl"] = trades_export["pnl"].astype(int)
        trades_export.to_csv(trades_path, index=False)
    else:
        result.combined_trades_df.to_csv(trades_path, index=False)
    logger.debug(f"거래 내역 저장 완료: {trades_path}")

    # 3. summary.json 저장
    summary_path = result.config.result_dir / "summary.json"

    # 합산 레벨 요약 반올림
    cs = result.combined_summary
    split_summary: dict[str, Any] = {
        "initial_capital": round(float(str(cs["initial_capital"]))),
        "final_capital": round(float(str(cs["final_capital"]))),
        "total_return_pct": round(float(str(cs["total_return_pct"])), 2),
        "cagr": round(float(str(cs["cagr"])), 2),
        "mdd": round(float(str(cs["mdd"])), 2),
        "calmar": round(float(str(cs["calmar"])), 2),
        "total_trades": cs["total_trades"],
        "active_open_positions": sum(1 for tr in result.per_tranche if "open_position" in tr.summary),
    }

    # 트랜치별 요약
    tranches_data: list[dict[str, Any]] = []
    for tr in result.per_tranche:
        t_data: dict[str, Any] = {
            "tranche_id": tr.tranche_id,
            "ma_window": tr.config.ma_window,
            "weight": tr.config.weight,
            "initial_capital": round(float(str(tr.summary["initial_capital"]))),
            "summary": {
                "final_capital": round(float(str(tr.summary["final_capital"]))),
                "total_return_pct": round(float(str(tr.summary["total_return_pct"])), 2),
                "cagr": round(float(str(tr.summary["cagr"])), 2),
                "mdd": round(float(str(tr.summary["mdd"])), 2),
                "calmar": round(float(str(tr.summary["calmar"])), 2),
                "total_trades": tr.summary["total_trades"],
                "win_rate": round(float(str(tr.summary["win_rate"])), 2),
            },
        }

        # 미청산 포지션 정보
        if "open_position" in tr.summary:
            op = tr.summary["open_position"]
            t_data["open_position"] = {
                "entry_date": str(op["entry_date"]),
                "entry_price": round(float(str(op["entry_price"])), 6),
                "shares": int(str(op["shares"])),
            }

        tranches_data.append(t_data)

    summary_data: dict[str, Any] = {
        "display_name": result.display_name,
        "split_summary": split_summary,
        "tranches": tranches_data,
        "split_config": result.params_json,
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    logger.debug(f"요약 JSON 저장 완료: {summary_path}")

    # 4. 메타데이터 저장
    metadata: dict[str, Any] = {
        "params": result.params_json,
        "results_summary": {
            "total_return_pct": split_summary["total_return_pct"],
            "cagr": split_summary["cagr"],
            "mdd": split_summary["mdd"],
            "calmar": split_summary["calmar"],
            "total_trades": split_summary["total_trades"],
            "active_open_positions": split_summary["active_open_positions"],
        },
        "output_files": {
            "equity_csv": str(equity_path),
            "trades_csv": str(trades_path),
            "summary_json": str(summary_path),
        },
    }
    save_metadata("split_backtest", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")


def _print_summary(result: SplitStrategyResult) -> None:
    """분할 매수매도 결과 요약을 출력한다.

    Args:
        result: SplitStrategyResult 컨테이너
    """
    cs = result.combined_summary
    logger.debug("=" * 60)
    logger.debug(f"[{result.display_name}] 분할 매수매도 결과")
    logger.debug(f"  기간: {cs.get('start_date')} ~ {cs.get('end_date')}")
    logger.debug(f"  초기 자본: {cs['initial_capital']:,.0f}원")
    logger.debug(f"  최종 자본: {cs['final_capital']:,.0f}원")
    logger.debug(f"  총 수익률: {cs['total_return_pct']:.2f}%")
    logger.debug(f"  CAGR: {cs['cagr']:.2f}%")
    logger.debug(f"  MDD: {cs['mdd']:.2f}%")
    logger.debug(f"  Calmar: {cs['calmar']:.2f}")
    logger.debug(f"  총 거래 수: {cs['total_trades']}")
    logger.debug("=" * 60)

    # 트랜치별 요약 테이블
    columns = [
        ("트랜치", 10, Align.LEFT),
        ("MA", 6, Align.RIGHT),
        ("가중치", 8, Align.RIGHT),
        ("수익률", 12, Align.RIGHT),
        ("CAGR", 10, Align.RIGHT),
        ("MDD", 10, Align.RIGHT),
        ("Calmar", 10, Align.RIGHT),
        ("거래수", 8, Align.RIGHT),
    ]

    rows = []
    for tr in result.per_tranche:
        rows.append(
            [
                tr.tranche_id,
                str(tr.config.ma_window),
                f"{tr.config.weight:.0%}",
                f"{tr.summary['total_return_pct']:.2f}%",
                f"{tr.summary['cagr']:.2f}%",
                f"{tr.summary['mdd']:.2f}%",
                f"{tr.summary['calmar']:.2f}",
                str(tr.summary["total_trades"]),
            ]
        )

    table = TableLogger(columns, logger)
    table.print_table(rows, title="[트랜치별 성과 요약]")


@cli_exception_handler
def main() -> int:
    """메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 명령행 인자 파싱
    parser = argparse.ArgumentParser(description="분할 매수매도 백테스트 실행")
    parser.add_argument(
        "--strategy",
        choices=["all", *_CONFIG_MAP.keys()],
        default="all",
        help="실행할 전략 (기본값: all)",
    )
    args = parser.parse_args()

    # 2. 대상 전략 결정
    if args.strategy == "all":
        target_configs = list(SPLIT_CONFIGS)
    else:
        target_configs = [_CONFIG_MAP[args.strategy]]

    logger.debug(f"실행 전략: {[c.strategy_name for c in target_configs]}")

    # 3. 전략별 실행
    for config in target_configs:
        logger.debug("=" * 60)
        result = run_split_backtest(config)
        _print_summary(result)
        _save_split_results(result)
        logger.debug(f"{result.display_name} 결과 파일 저장 완료")

    return 0


if __name__ == "__main__":
    sys.exit(main())
