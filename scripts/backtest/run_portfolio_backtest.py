"""포트폴리오 백테스트 실행 스크립트

7가지 포트폴리오 실험(A-1~A-3, B-1~B-3, C-1)을 실행하고 결과를 저장한다.
--experiment 인자로 실행할 실험을 선택할 수 있다.

실행 명령어:
    poetry run python scripts/backtest/run_portfolio_backtest.py
    poetry run python scripts/backtest/run_portfolio_backtest.py --experiment portfolio_a2
    poetry run python scripts/backtest/run_portfolio_backtest.py --experiment portfolio_c1
"""

import argparse
import json
import sys
from typing import Any

from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS, get_portfolio_config
from qbt.backtest.portfolio_strategy import compute_portfolio_effective_start_date, run_portfolio_backtest
from qbt.backtest.portfolio_types import PortfolioResult
from qbt.common_constants import (
    COL_CLOSE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    META_JSON_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# 실험 이름 → 설정 매핑
_CONFIG_MAP = {c.experiment_name: c for c in PORTFOLIO_CONFIGS}

# 반올림 규칙 (루트 CLAUDE.md §출력 데이터 반올림 규칙 참고)
_PRICE_ROUND = 6  # 가격 (OHLCV, MA, 밴드)
_EQUITY_ROUND = 0  # 자본금 (equity, cash, {asset_id}_value)
_PCT_ROUND = 2  # 백분율 (drawdown_pct, change_pct, cagr, mdd 등)
_RATIO_ROUND = 4  # 비율 0~1 ({asset_id}_weight)
_PNL_PCT_ROUND = 4  # pnl_pct


def _save_portfolio_results(result: PortfolioResult) -> None:
    """포트폴리오 백테스트 결과를 CSV/JSON 파일로 저장하고 메타데이터를 기록한다.

    저장 파일:
    - equity.csv: 합산 에쿼티 + 자산별 비중/시그널 + 리밸런싱 여부
    - trades.csv: 전 자산 거래 내역 + holding_days
    - signal_{asset_id}.csv: 자산별 시그널 (OHLCV + MA + 밴드 + 전일종가대비%)
    - summary.json: 전체 + 자산별 요약 지표 + 설정 파라미터

    Args:
        result: PortfolioResult 컨테이너
    """
    result.config.result_dir.mkdir(parents=True, exist_ok=True)

    # 1. equity.csv 저장
    equity_path = result.config.result_dir / "equity.csv"
    equity_export = result.equity_df.copy()

    equity_round: dict[str, int] = {
        "equity": _EQUITY_ROUND,
        "cash": _EQUITY_ROUND,
        "drawdown_pct": _PCT_ROUND,
    }
    for col in equity_export.columns:
        if col.endswith("_value"):
            equity_round[col] = _EQUITY_ROUND
        elif col.endswith("_weight"):
            equity_round[col] = _RATIO_ROUND

    equity_export = equity_export.round(equity_round)
    # int 변환 (자본금)
    for col in ["equity", "cash"] + [c for c in equity_export.columns if c.endswith("_value")]:
        if col in equity_export.columns:
            equity_export[col] = equity_export[col].astype(int)

    equity_export.to_csv(equity_path, index=False)
    logger.debug(f"에쿼티 데이터 저장 완료: {equity_path}")

    # 2. trades.csv 저장
    trades_path = result.config.result_dir / "trades.csv"
    if not result.trades_df.empty:
        trades_export = result.trades_df.copy()

        # holding_days 컬럼 추가
        if "entry_date" in trades_export.columns and "exit_date" in trades_export.columns:
            trades_export["holding_days"] = trades_export.apply(
                lambda row: (row["exit_date"] - row["entry_date"]).days, axis=1
            )

        trades_round: dict[str, int] = {}
        if "entry_price" in trades_export.columns:
            trades_round["entry_price"] = _PRICE_ROUND
        if "exit_price" in trades_export.columns:
            trades_round["exit_price"] = _PRICE_ROUND
        if "pnl" in trades_export.columns:
            trades_round["pnl"] = _EQUITY_ROUND
        if "pnl_pct" in trades_export.columns:
            trades_round["pnl_pct"] = _PNL_PCT_ROUND

        trades_export = trades_export.round(trades_round)
        if "pnl" in trades_export.columns:
            trades_export["pnl"] = trades_export["pnl"].astype(int)

        trades_export.to_csv(trades_path, index=False)
    else:
        result.trades_df.to_csv(trades_path, index=False)
    logger.debug(f"거래 내역 저장 완료: {trades_path}")

    # 3. signal_{asset_id}.csv 저장 (자산별)
    for asset_result in result.per_asset:
        signal_path = result.config.result_dir / f"signal_{asset_result.asset_id}.csv"
        signal_export = asset_result.signal_df.copy()

        # 전일종가대비% 계산 (저장 직전)
        if COL_CLOSE in signal_export.columns:
            signal_export["change_pct"] = signal_export[COL_CLOSE].pct_change() * 100

        signal_round: dict[str, int] = {}
        for col in [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]:
            if col in signal_export.columns:
                signal_round[col] = _PRICE_ROUND
        for col in signal_export.columns:
            if col.startswith("ma_") or col in ("upper_band", "lower_band"):
                signal_round[col] = _PRICE_ROUND
        if "change_pct" in signal_export.columns:
            signal_round["change_pct"] = _PCT_ROUND

        signal_export = signal_export.round(signal_round)
        signal_export.to_csv(signal_path, index=False)
        logger.debug(f"시그널 데이터 저장 완료: {signal_path} (asset_id={asset_result.asset_id})")

    # 4. summary.json 저장
    summary_path = result.config.result_dir / "summary.json"
    s = result.summary

    portfolio_summary: dict[str, Any] = {
        "initial_capital": round(float(str(s["initial_capital"]))),
        "final_capital": round(float(str(s["final_capital"]))),
        "total_return_pct": round(float(str(s["total_return_pct"])), _PCT_ROUND),
        "cagr": round(float(str(s["cagr"])), _PCT_ROUND),
        "mdd": round(float(str(s["mdd"])), _PCT_ROUND),
        "calmar": round(float(str(s["calmar"])), _PCT_ROUND),
        "total_trades": s["total_trades"],
        "start_date": str(s.get("start_date", "")),
        "end_date": str(s.get("end_date", "")),
    }

    # 자산별 요약
    per_asset_data: list[dict[str, Any]] = []
    for asset_result in result.per_asset:
        slot = next(
            (sl for sl in result.config.asset_slots if sl.asset_id == asset_result.asset_id),
            None,
        )
        asset_trades = asset_result.trades_df
        total_asset_trades = len(asset_trades)
        win_rate = 0.0
        if total_asset_trades > 0 and "pnl" in asset_trades.columns:
            win_rate = round(
                float((asset_trades["pnl"] > 0).sum()) / total_asset_trades * 100,
                _PCT_ROUND,
            )

        per_asset_data.append(
            {
                "asset_id": asset_result.asset_id,
                "target_weight": round(slot.target_weight, _RATIO_ROUND) if slot else 0.0,
                "total_trades": total_asset_trades,
                "win_rate": win_rate,
            }
        )

    summary_data: dict[str, Any] = {
        "display_name": result.display_name,
        "portfolio_summary": portfolio_summary,
        "per_asset": per_asset_data,
        "portfolio_config": result.params_json,
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    logger.debug(f"요약 JSON 저장 완료: {summary_path}")

    # 5. 메타데이터 저장
    metadata: dict[str, Any] = {
        "params": result.params_json,
        "results_summary": {
            "total_return_pct": portfolio_summary["total_return_pct"],
            "cagr": portfolio_summary["cagr"],
            "mdd": portfolio_summary["mdd"],
            "calmar": portfolio_summary["calmar"],
            "total_trades": portfolio_summary["total_trades"],
        },
        "output_files": {
            "equity_csv": str(equity_path),
            "trades_csv": str(trades_path),
            "summary_json": str(summary_path),
        },
    }
    save_metadata("portfolio_backtest", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")


def _print_summary(result: PortfolioResult) -> None:
    """포트폴리오 백테스트 결과 요약을 출력한다.

    Args:
        result: PortfolioResult 컨테이너
    """
    s = result.summary
    logger.debug("=" * 70)
    logger.debug(f"[{result.display_name}] 포트폴리오 백테스트 결과")
    logger.debug(f"  기간: {s.get('start_date')} ~ {s.get('end_date')}")
    logger.debug(f"  초기 자본: {s['initial_capital']:,.0f}원")
    logger.debug(f"  최종 자본: {s['final_capital']:,.0f}원")
    logger.debug(f"  총 수익률: {s['total_return_pct']:.2f}%")
    logger.debug(f"  CAGR: {s['cagr']:.2f}%")
    logger.debug(f"  MDD: {s['mdd']:.2f}%")
    logger.debug(f"  Calmar: {s['calmar']:.2f}")
    logger.debug(f"  총 거래 수: {s['total_trades']}")
    logger.debug("=" * 70)

    # 자산별 성과 테이블
    columns = [
        ("자산", 8, Align.LEFT),
        ("비중", 8, Align.RIGHT),
        ("거래수", 8, Align.RIGHT),
    ]

    rows = []
    for asset_result in result.per_asset:
        slot = next(
            (sl for sl in result.config.asset_slots if sl.asset_id == asset_result.asset_id),
            None,
        )
        target_weight = slot.target_weight if slot else 0.0
        total_trades = len(asset_result.trades_df)
        rows.append(
            [
                asset_result.asset_id,
                f"{target_weight:.1%}",
                str(total_trades),
            ]
        )

    table = TableLogger(columns, logger)
    table.print_table(rows, title="[자산별 거래 현황]")


@cli_exception_handler
def main() -> int:
    """메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 명령행 인자 파싱
    parser = argparse.ArgumentParser(description="포트폴리오 백테스트 실행 (A/B/C 시리즈)")
    parser.add_argument(
        "--experiment",
        choices=["all", *_CONFIG_MAP.keys()],
        default="all",
        help="실행할 실험 (기본값: all)",
    )
    args = parser.parse_args()

    # 2. 대상 실험 결정
    if args.experiment == "all":
        target_configs = list(PORTFOLIO_CONFIGS)
        logger.debug(f"전체 {len(target_configs)}개 실험 실행")
    else:
        target_configs = [get_portfolio_config(args.experiment)]
        logger.debug(f"단일 실험 실행: {args.experiment}")

    logger.debug(f"실험 목록: {[c.experiment_name for c in target_configs]}")

    # 3. 글로벌 시작일 계산 (전체 7개 PORTFOLIO_CONFIGS 기준)
    # 모든 실험이 동일한 기간에서 비교될 수 있도록 유효 시작일 중 가장 늦은 날짜 적용
    logger.debug("글로벌 시작일 계산 중 (전체 PORTFOLIO_CONFIGS 대상)...")
    effective_start_dates = [compute_portfolio_effective_start_date(cfg) for cfg in PORTFOLIO_CONFIGS]
    global_start_date = max(effective_start_dates)
    logger.debug(f"글로벌 시작일 결정: {global_start_date} (전체 {len(PORTFOLIO_CONFIGS)}개 실험 기준)")

    # 4. 실험별 실행 (글로벌 시작일 적용)
    for config in target_configs:
        logger.debug("=" * 70)
        logger.debug(f"실험 시작: {config.experiment_name} ({config.display_name})")
        result = run_portfolio_backtest(config, start_date=global_start_date)
        _print_summary(result)
        _save_portfolio_results(result)
        logger.debug(f"{config.display_name} 결과 파일 저장 완료: {config.result_dir}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
