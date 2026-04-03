"""포트폴리오 백테스트 실행 스크립트

포트폴리오 실험을 실행하고 결과를 저장한다.
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

import pandas as pd

from qbt.backtest.constants import (
    DEFAULT_PORTFOLIO_EXPERIMENTS,
    ROUND_CAPITAL,
    ROUND_PERCENT,
    ROUND_PRICE,
    ROUND_RATIO,
)
from qbt.backtest.csv_export import calculate_change_pct, prepare_trades_for_csv
from qbt.backtest.engines.portfolio_engine import compute_portfolio_effective_start_date, run_portfolio_backtest
from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS, get_portfolio_config
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

# 활성 실험만 포함하는 매핑 (DEFAULT_PORTFOLIO_EXPERIMENTS 필터)
_ACTIVE_CONFIG_MAP = {
    c.experiment_name: c for c in PORTFOLIO_CONFIGS if c.experiment_name in DEFAULT_PORTFOLIO_EXPERIMENTS
}


def _build_execution_comparison_df(
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> pd.DataFrame:
    """모든 체결일의 전후 비교 데이터를 생성한다.

    equity_df와 trades_df를 교차 참조하여, 체결 발생일(exit_date)마다
    자산별 전일/당일 보유수, 비중, 평가액 변화를 계산한다.

    Args:
        equity_df: 포트폴리오 에쿼티 DataFrame (Date, equity, cash, {asset}_shares 등)
        trades_df: 포트폴리오 거래 내역 DataFrame (exit_date, asset_id, trade_type, shares 등)

    Returns:
        체결 전후 비교 DataFrame (date x asset_id 행). 거래가 없으면 빈 DataFrame.
    """
    if trades_df.empty or "exit_date" not in trades_df.columns:
        return pd.DataFrame()

    # 1. 자산 ID 추출 (weight 컬럼 기반)
    asset_ids = [c.removesuffix("_weight") for c in equity_df.columns if c.endswith("_weight")]
    if not asset_ids:
        return pd.DataFrame()

    # 2. 체결 발생일 목록 (exit_date 기준)
    trade_dates = sorted(trades_df["exit_date"].dropna().unique())
    if not trade_dates:
        return pd.DataFrame()

    # 3. 날짜 -> 인덱스 매핑 (빠른 조회용)
    date_to_idx: dict[Any, int] = {}
    for i, d in enumerate(equity_df["Date"]):
        date_to_idx[d] = i

    rows: list[dict[str, Any]] = []
    for trade_date in trade_dates:
        current_idx = date_to_idx.get(trade_date)
        if current_idx is None:
            continue

        current_row = equity_df.iloc[current_idx]
        prev_row = equity_df.iloc[current_idx - 1] if current_idx > 0 else current_row

        date_str = str(trade_date)

        # 리밸런싱 사유
        rebalance_reason = ""
        if "rebalance_reason" in equity_df.columns:
            val = current_row.get("rebalance_reason")
            if pd.notna(val):
                rebalance_reason = str(val)

        # 해당일 거래 내역
        day_trades = trades_df[trades_df["exit_date"] == trade_date]

        # 4. 자산별 행
        for asset_id in asset_ids:
            shares_col = f"{asset_id}_shares"
            weight_col = f"{asset_id}_weight"
            value_col = f"{asset_id}_value"

            pre_shares = int(prev_row.get(shares_col, 0)) if shares_col in equity_df.columns else 0
            post_shares = int(current_row.get(shares_col, 0)) if shares_col in equity_df.columns else 0
            pre_weight = float(prev_row.get(weight_col, 0)) * 100 if weight_col in equity_df.columns else 0.0
            post_weight = float(current_row.get(weight_col, 0)) * 100 if weight_col in equity_df.columns else 0.0
            pre_value = int(prev_row.get(value_col, 0)) if value_col in equity_df.columns else 0
            post_value = int(current_row.get(value_col, 0)) if value_col in equity_df.columns else 0

            # 거래 내역 텍스트
            trade_info = ""
            if "asset_id" in day_trades.columns:
                asset_day_trades = day_trades[day_trades["asset_id"] == asset_id]
                for _, t in asset_day_trades.iterrows():
                    tt = str(t.get("trade_type", ""))
                    s = int(t.get("shares", 0))
                    label = "매도" if tt == "signal" else "리밸런싱"
                    trade_info += f"{label} {s}주 "
                trade_info = trade_info.strip()

            rows.append(
                {
                    "date": date_str,
                    "asset_id": asset_id,
                    "pre_shares": pre_shares,
                    "post_shares": post_shares,
                    "pre_weight_pct": round(pre_weight, ROUND_PERCENT),
                    "post_weight_pct": round(post_weight, ROUND_PERCENT),
                    "pre_value": pre_value,
                    "post_value": post_value,
                    "delta_shares": post_shares - pre_shares,
                    "delta_value": post_value - pre_value,
                    "trade_info": trade_info,
                    "rebalance_reason": rebalance_reason,
                }
            )

        # 5. 현금 행
        pre_cash = int(prev_row.get("cash", 0))
        post_cash = int(current_row.get("cash", 0))
        pre_equity_val = int(prev_row.get("equity", 1))
        post_equity_val = int(current_row.get("equity", 1))

        rows.append(
            {
                "date": date_str,
                "asset_id": "cash",
                "pre_shares": 0,
                "post_shares": 0,
                "pre_weight_pct": round(pre_cash / pre_equity_val * 100 if pre_equity_val > 0 else 0.0, ROUND_PERCENT),
                "post_weight_pct": round(
                    post_cash / post_equity_val * 100 if post_equity_val > 0 else 0.0, ROUND_PERCENT
                ),
                "pre_value": pre_cash,
                "post_value": post_cash,
                "delta_shares": 0,
                "delta_value": post_cash - pre_cash,
                "trade_info": "",
                "rebalance_reason": rebalance_reason,
            }
        )

    return pd.DataFrame(rows) if rows else pd.DataFrame()


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
        "equity": ROUND_CAPITAL,
        "cash": ROUND_CAPITAL,
        "drawdown_pct": ROUND_PERCENT,
    }
    for col in equity_export.columns:
        if col.endswith("_value"):
            equity_round[col] = ROUND_CAPITAL
        elif col.endswith("_weight"):
            equity_round[col] = ROUND_RATIO
        elif col.endswith("_avg_price"):
            equity_round[col] = ROUND_PRICE
        elif col.endswith("_realized_pnl") or col.endswith("_unrealized_pnl"):
            equity_round[col] = ROUND_CAPITAL

    equity_export = equity_export.round(equity_round)
    # int 변환 (자본금 + 보유 주수 + 손익)
    pnl_cols = [c for c in equity_export.columns if c.endswith("_realized_pnl") or c.endswith("_unrealized_pnl")]
    for col in ["equity", "cash"] + [c for c in equity_export.columns if c.endswith("_value")] + pnl_cols:
        if col in equity_export.columns:
            equity_export[col] = equity_export[col].astype(int)
    for col in [c for c in equity_export.columns if c.endswith("_shares")]:
        equity_export[col] = equity_export[col].astype(int)

    equity_export.to_csv(equity_path, index=False)
    logger.debug(f"에쿼티 데이터 저장 완료: {equity_path}")

    # 2. trades.csv 저장
    trades_path = result.config.result_dir / "trades.csv"
    prepare_trades_for_csv(result.trades_df).to_csv(trades_path, index=False)
    logger.debug(f"거래 내역 저장 완료: {trades_path}")

    # 3. signal_{asset_id}.csv 저장 (자산별)
    for asset_result in result.per_asset:
        signal_path = result.config.result_dir / f"signal_{asset_result.asset_id}.csv"
        signal_export = asset_result.signal_df.copy()

        # 전일종가대비% 계산 (저장 직전)
        if COL_CLOSE in signal_export.columns:
            signal_export["change_pct"] = calculate_change_pct(signal_export)

        signal_round: dict[str, int] = {}
        for col in [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]:
            if col in signal_export.columns:
                signal_round[col] = ROUND_PRICE
        for col in signal_export.columns:
            if col.startswith("ma_") or col in ("upper_band", "lower_band"):
                signal_round[col] = ROUND_PRICE
        if "change_pct" in signal_export.columns:
            signal_round["change_pct"] = ROUND_PERCENT

        signal_export = signal_export.round(signal_round)
        signal_export.to_csv(signal_path, index=False)
        logger.debug(f"시그널 데이터 저장 완료: {signal_path} (asset_id={asset_result.asset_id})")

    # 4. execution_comparison.csv 저장
    comparison_df = _build_execution_comparison_df(result.equity_df, result.trades_df)
    comparison_path = result.config.result_dir / "execution_comparison.csv"
    if not comparison_df.empty:
        comparison_df.to_csv(comparison_path, index=False)
        logger.debug(f"체결 전후 비교 데이터 저장 완료: {comparison_path}")

    # 5. summary.json 저장
    summary_path = result.config.result_dir / "summary.json"
    s = result.summary

    portfolio_summary: dict[str, Any] = {
        "initial_capital": round(float(str(s["initial_capital"]))),
        "final_capital": round(float(str(s["final_capital"]))),
        "total_return_pct": round(float(str(s["total_return_pct"])), ROUND_PERCENT),
        "cagr": round(float(str(s["cagr"])), ROUND_PERCENT),
        "mdd": round(float(str(s["mdd"])), ROUND_PERCENT),
        "calmar": round(float(str(s["calmar"])), ROUND_PERCENT),
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
                ROUND_PERCENT,
            )

        # 최종일 기준 보유 정보 (equity_df에서 추출)
        final_shares = 0
        final_avg_price = 0.0
        shares_col = f"{asset_result.asset_id}_shares"
        avg_price_col = f"{asset_result.asset_id}_avg_price"
        if shares_col in result.equity_df.columns and not result.equity_df.empty:
            final_shares = int(result.equity_df[shares_col].iloc[-1])
        if avg_price_col in result.equity_df.columns and not result.equity_df.empty:
            final_avg_price = round(float(result.equity_df[avg_price_col].iloc[-1]), ROUND_PRICE)

        per_asset_data.append(
            {
                "asset_id": asset_result.asset_id,
                "target_weight": round(slot.target_weight, ROUND_RATIO) if slot else 0.0,
                "total_trades": total_asset_trades,
                "win_rate": win_rate,
                "final_shares": final_shares,
                "final_avg_price": final_avg_price,
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

    # 6. 메타데이터 저장
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
            "execution_comparison_csv": str(comparison_path),
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
    parser = argparse.ArgumentParser(description="포트폴리오 백테스트 실행")
    parser.add_argument(
        "--experiment",
        choices=["all", *_ACTIVE_CONFIG_MAP.keys()],
        default="all",
        help="실행할 실험 (기본값: all, 활성 실험만 선택 가능)",
    )
    args = parser.parse_args()

    # 2. 대상 실험 결정 (활성 실험 기준)
    active_configs = [c for c in PORTFOLIO_CONFIGS if c.experiment_name in DEFAULT_PORTFOLIO_EXPERIMENTS]

    if args.experiment == "all":
        target_configs = list(active_configs)
        logger.debug(f"활성 실험 {len(target_configs)}개 실행")
    else:
        target_configs = [get_portfolio_config(args.experiment)]
        logger.debug(f"단일 실험 실행: {args.experiment}")

    logger.debug(f"실험 목록: {[c.experiment_name for c in target_configs]}")

    # 3. 글로벌 시작일 계산 (활성 실험 기준)
    # 활성 실험이 동일한 기간에서 비교될 수 있도록 유효 시작일 중 가장 늦은 날짜 적용
    logger.debug("글로벌 시작일 계산 중 (활성 실험 대상)...")
    effective_start_dates = [compute_portfolio_effective_start_date(cfg) for cfg in active_configs]
    global_start_date = max(effective_start_dates)
    logger.debug(f"글로벌 시작일 결정: {global_start_date} (활성 {len(active_configs)}개 실험 기준)")

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
