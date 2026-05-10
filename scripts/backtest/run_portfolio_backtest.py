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
from datetime import date
from typing import Any

import pandas as pd

from qbt.backtest.analysis import (
    calculate_benchmark_yearly_returns,
    calculate_monthly_returns,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_yearly_returns,
)
from qbt.backtest.constants import (
    ROUND_CAPITAL,
    ROUND_PERCENT,
    ROUND_PRICE,
    ROUND_RATIO,
)
from qbt.backtest.csv_export import (
    BUFFER_BAND_COLUMNS,
    OHLC_CHANGE_PCT_COLUMNS,
    add_buffer_zone_bands,
    add_ohlc_change_pct,
    prepare_trades_for_csv,
)
from qbt.backtest.engines.portfolio_engine import compute_portfolio_effective_start_date, run_portfolio_backtest
from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS, get_portfolio_config
from qbt.backtest.portfolio_types import (
    ASSET_COL_SUFFIX_WEIGHT,
    AssetSlotConfig,
    PortfolioResult,
    asset_shares_col,
    asset_value_col,
    asset_weight_col,
)
from qbt.backtest.portfolio_validation import validate_portfolio_result
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    META_JSON_PATH,
    PORTFOLIO_RESULTS_DIR,
    QQQ_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# 실험명 -> config 매핑
_CONFIG_MAP = {c.experiment_name: c for c in PORTFOLIO_CONFIGS}

# 포트폴리오 백테스트 최소 시작일 하한
# 각 실험의 effective_start_date가 이 날짜 이전이어도 이 날짜부터 실행한다
# (2005년 이전 데이터는 포트폴리오 비교 범위에서 제외).
DEFAULT_PORTFOLIO_START_DATE: date = date(2005, 1, 1)


def _build_execution_comparison_df(
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
) -> pd.DataFrame:
    """모든 체결일의 전후 비교 데이터를 생성한다.

    trades_df에서 체결 발생일(exit_date)을 추출하고, equity_df에서
    자산별 전일/당일 보유수, 비중, 평가액 변화를 계산한다.

    Args:
        equity_df: 포트폴리오 에쿼티 DataFrame (Date, equity, cash, {asset}_shares 등)
        trades_df: 포트폴리오 거래 내역 DataFrame (체결일 목록 추출용, exit_date 필수)

    Returns:
        체결 전후 비교 DataFrame (date x asset_id 행). 거래가 없으면 빈 DataFrame.
    """
    if trades_df.empty or "exit_date" not in trades_df.columns:
        return pd.DataFrame()

    # 1. 자산 ID 추출 (weight 컬럼 기반)
    asset_ids = [
        c.removesuffix(ASSET_COL_SUFFIX_WEIGHT) for c in equity_df.columns if c.endswith(ASSET_COL_SUFFIX_WEIGHT)
    ]
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

        # 4. 자산별 행
        for asset_id in asset_ids:
            shares_col = asset_shares_col(asset_id)
            weight_col = asset_weight_col(asset_id)
            value_col = asset_value_col(asset_id)

            # 포트폴리오 엔진이 자산별 컬럼(_shares/_weight/_value)을 항상 생성하므로
            # 컬럼 존재 여부 분기와 .get() default 는 dead branch 다.
            pre_shares = int(prev_row[shares_col])
            post_shares = int(current_row[shares_col])
            pre_weight = float(prev_row[weight_col]) * 100
            post_weight = float(current_row[weight_col]) * 100
            pre_value = int(prev_row[value_col])
            post_value = int(current_row[value_col])

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
                    "rebalance_reason": rebalance_reason,
                }
            )

        # 5. 현금 행 — equity / cash 컬럼은 포트폴리오 엔진이 항상 생성한다.
        # equity > 0 은 비레버리지 포트폴리오의 불변조건이다 (소멸 불가).
        pre_cash = int(prev_row["cash"])
        post_cash = int(current_row["cash"])
        pre_equity_val = int(prev_row["equity"])
        post_equity_val = int(current_row["equity"])
        if pre_equity_val <= 0 or post_equity_val <= 0:
            raise RuntimeError(
                f"내부 불변조건 위반: equity <= 0 (date={date_str}, " f"pre={pre_equity_val}, post={post_equity_val})"
            )

        rows.append(
            {
                "date": date_str,
                "asset_id": "cash",
                "pre_shares": 0,
                "post_shares": 0,
                "pre_weight_pct": round(pre_cash / pre_equity_val * 100, ROUND_PERCENT),
                "post_weight_pct": round(post_cash / post_equity_val * 100, ROUND_PERCENT),
                "pre_value": pre_cash,
                "post_value": post_cash,
                "delta_shares": 0,
                "delta_value": post_cash - pre_cash,
                "rebalance_reason": rebalance_reason,
            }
        )

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _save_benchmark_qqq_json(start_date: Any) -> None:
    """QQQ 벤치마크의 연간 복리 수익률을 산출해 포트폴리오 결과 디렉토리에 저장한다.

    실험별로 백테스트 시작일이 달라질 수 있으므로, 전체 실험 중 가장 이른 유효
    시작일(min) 기준으로 한 번만 계산하여 공유 JSON 하나
    (`storage/results/portfolio/benchmark_qqq.json`)를 생성한다. 대시보드는
    연도별 inner join으로 각 실험 기간과 공통되는 연도만 비교하므로,
    가장 이른 시작일 기준으로 연간 수익률을 생성해도 실험별 비교에 문제가 없다.
    종료일은 QQQ 데이터의 마지막 날짜를 사용한다.

    Args:
        start_date: QQQ 연간 수익률 계산 시작일 (전체 실험 중 가장 이른 유효 시작일)
    """
    PORTFOLIO_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    qqq_df = load_stock_data(QQQ_DATA_PATH)
    end_date = qqq_df[COL_DATE].max()

    yearly = calculate_benchmark_yearly_returns(qqq_df, start_date, end_date)

    benchmark_data: dict[str, Any] = {
        "ticker": "QQQ",
        "start_date": str(start_date),
        "end_date": str(end_date),
        "yearly_returns": yearly,
    }

    benchmark_path = PORTFOLIO_RESULTS_DIR / "benchmark_qqq.json"
    with benchmark_path.open("w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)
    logger.debug(f"QQQ 벤치마크 연간 수익률 저장 완료: {benchmark_path}")


def _find_last_entry_date(equity_df: pd.DataFrame, asset_id: str) -> str | None:
    """자산의 shares가 마지막으로 0 → 양수로 전환된 거래일을 반환한다.

    미청산 포지션의 entry_date 파생용. shares 컬럼이 없거나 모든 값이 0이면 None.
    shares가 한 번도 0이 되지 않고 시작부터 양수인 경우(예: buy_and_hold)에는
    첫 번째 양수 행의 Date를 폴백으로 반환한다.

    Args:
        equity_df: 포트폴리오 에쿼티 DataFrame (Date, {asset_id}_shares 포함)
        asset_id: 자산 식별자

    Returns:
        entry_date 문자열 (YYYY-MM-DD) 또는 None
    """
    shares_col = asset_shares_col(asset_id)
    if shares_col not in equity_df.columns or equity_df.empty:
        return None

    shares = equity_df[shares_col].astype(int)
    if (shares <= 0).all():
        return None

    prev = shares.shift(1).fillna(0).astype(int)
    transition_mask = (prev == 0) & (shares > 0)
    if transition_mask.any():
        entry_row = equity_df.loc[transition_mask].iloc[-1]
        return str(entry_row[COL_DATE])

    # 폴백: 시작부터 양수인 경우 첫 행 Date
    first_positive_mask = shares > 0
    if first_positive_mask.any():
        first_row = equity_df.loc[first_positive_mask].iloc[0]
        return str(first_row[COL_DATE])

    return None


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
        elif col.endswith("_realized_pnl") or col.endswith("_unrealized_pnl") or col.endswith("_contribution"):
            equity_round[col] = ROUND_CAPITAL

    equity_export = equity_export.round(equity_round)
    # int 변환 (자본금 + 보유 주수 + 손익 + 기여도)
    pnl_cols = [
        c
        for c in equity_export.columns
        if c.endswith("_realized_pnl") or c.endswith("_unrealized_pnl") or c.endswith("_contribution")
    ]
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
    # asset_id -> AssetSlotConfig 매핑 (밴드 계산 시 슬롯의 전략 파라미터 조회용)
    slot_by_asset: dict[str, AssetSlotConfig] = {slot.asset_id: slot for slot in result.config.asset_slots}
    for asset_result in result.per_asset:
        signal_path = result.config.result_dir / f"signal_{asset_result.asset_id}.csv"

        # 4종 OHLC 전일대비% 사전 계산 (대시보드 SSoT)
        signal_export = add_ohlc_change_pct(asset_result.signal_df)

        # buffer_zone 자산은 upper_band / lower_band 컬럼 사전 계산 (대시보드 SSoT)
        slot = slot_by_asset[asset_result.asset_id]
        if slot.strategy_id == "buffer_zone":
            ma_col = f"ma_{slot.ma_window}"
            signal_export = add_buffer_zone_bands(
                signal_export,
                ma_col,
                buy_buffer_zone_pct=slot.buy_buffer_zone_pct,
                sell_buffer_zone_pct=slot.sell_buffer_zone_pct,
            )

        signal_round: dict[str, int] = {col: ROUND_PERCENT for col in OHLC_CHANGE_PCT_COLUMNS}
        for col in [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]:
            if col in signal_export.columns:
                signal_round[col] = ROUND_PRICE
        for col in signal_export.columns:
            if col.startswith("ma_") or col in BUFFER_BAND_COLUMNS:
                signal_round[col] = ROUND_PRICE

        signal_export = signal_export.round(signal_round)
        signal_export.to_csv(signal_path, index=False)
        logger.debug(f"시그널 데이터 저장 완료: {signal_path} (asset_id={asset_result.asset_id})")

    # 4. execution_comparison.csv 저장
    comparison_df = _build_execution_comparison_df(result.equity_df, result.trades_df)
    comparison_path = result.config.result_dir / "execution_comparison.csv"
    if not comparison_df.empty:
        comparison_df.to_csv(comparison_path, index=False)
        logger.debug(f"체결 전후 비교 데이터 저장 완료: {comparison_path}")

    # 4-1. state_log.csv 저장 (일별 엔진 내부 상태: 시그널/intent/체결/포지션)
    state_log_path = result.config.result_dir / "state_log.csv"
    if not result.state_log_df.empty:
        state_log_export = result.state_log_df.copy()
        # 반올림 규칙 적용
        state_log_round: dict[str, int] = {
            "equity": ROUND_CAPITAL,
            "cash": ROUND_CAPITAL,
        }
        for col in state_log_export.columns:
            if col.endswith("_close") or col.endswith("_exec_price"):
                state_log_round[col] = ROUND_PRICE
            elif col.endswith("_weight"):
                state_log_round[col] = ROUND_RATIO
            elif col.endswith("_pending_delta"):
                state_log_round[col] = ROUND_CAPITAL
        state_log_export = state_log_export.round(state_log_round)
        # int 변환 (자본금, 보유 수량, 체결 수량)
        for col in ["equity", "cash"]:
            if col in state_log_export.columns:
                state_log_export[col] = state_log_export[col].astype(int)
        for col in state_log_export.columns:
            if col.endswith("_shares") or col.endswith("_exec_shares"):
                state_log_export[col] = state_log_export[col].astype(int)
        state_log_export.to_csv(state_log_path, index=False)
        logger.debug(f"State Log 저장 완료: {state_log_path}")

    # 5. summary.json 저장
    summary_path = result.config.result_dir / "summary.json"
    s = result.summary

    # Sharpe/Sortino: 일별 수익률 기반 연율화 리스크 조정 지표 (rf=0 기준)
    sharpe = calculate_sharpe_ratio(result.equity_df)
    sortino = calculate_sortino_ratio(result.equity_df)

    portfolio_summary: dict[str, Any] = {
        "initial_capital": round(float(str(s["initial_capital"]))),
        "final_capital": round(float(str(s["final_capital"]))),
        "total_return_pct": round(float(str(s["total_return_pct"])), ROUND_PERCENT),
        "cagr": round(float(str(s["cagr"])), ROUND_PERCENT),
        "mdd": round(float(str(s["mdd"])), ROUND_PERCENT),
        "calmar": round(float(str(s["calmar"])), ROUND_PERCENT),
        "sharpe_ratio": round(sharpe, ROUND_PERCENT),
        "sortino_ratio": round(sortino, ROUND_PERCENT),
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
        shares_col = asset_shares_col(asset_result.asset_id)
        avg_price_col = f"{asset_result.asset_id}_avg_price"
        if shares_col in result.equity_df.columns and not result.equity_df.empty:
            final_shares = int(result.equity_df[shares_col].iloc[-1])
        if avg_price_col in result.equity_df.columns and not result.equity_df.empty:
            final_avg_price = round(float(result.equity_df[avg_price_col].iloc[-1]), ROUND_PRICE)

        asset_entry: dict[str, Any] = {
            "asset_id": asset_result.asset_id,
            "target_weight": round(slot.target_weight, ROUND_RATIO) if slot else 0.0,
            "total_trades": total_asset_trades,
            "win_rate": win_rate,
            "final_shares": final_shares,
            "final_avg_price": final_avg_price,
        }

        # 미청산 포지션(open_position): final_shares > 0 인 자산만 기록
        # 대시보드의 시그널 차트가 "Buy $XX.X (보유중)" 마커로 표시하는 데 사용
        if final_shares > 0:
            entry_date = _find_last_entry_date(result.equity_df, asset_result.asset_id)
            if entry_date is not None:
                asset_entry["open_position"] = {
                    "entry_date": entry_date,
                    "entry_price": final_avg_price,
                    "shares": final_shares,
                }

        per_asset_data.append(asset_entry)

    # 월별/연간 수익률 계산 (대시보드에서 히트맵 표시용)
    monthly_returns = calculate_monthly_returns(result.equity_df)
    yearly_returns = calculate_yearly_returns(monthly_returns)

    summary_data: dict[str, Any] = {
        "display_name": result.display_name,
        "portfolio_summary": portfolio_summary,
        "per_asset": per_asset_data,
        "portfolio_config": result.params_json,
        "monthly_returns": monthly_returns,
        "yearly_returns": yearly_returns,
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
            "state_log_csv": str(state_log_path),
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
        choices=["all", *_CONFIG_MAP.keys()],
        default="all",
        help="실행할 실험 (기본값: all, 활성 실험만 선택 가능)",
    )
    args = parser.parse_args()

    # 2. 대상 실험 결정
    if args.experiment == "all":
        target_configs = list(PORTFOLIO_CONFIGS)
        logger.debug(f"전체 실험 {len(target_configs)}개 실행")
    else:
        target_configs = [get_portfolio_config(args.experiment)]
        logger.debug(f"단일 실험 실행: {args.experiment}")

    logger.debug(f"실험 목록: {[c.experiment_name for c in target_configs]}")

    # 3. 실험별 유효 시작일 계산
    # 각 실험은 자기 자산 조합의 공통 기간 + MA 워밍업 이후를 사용하되,
    # 정책 하한인 DEFAULT_PORTFOLIO_START_DATE로 끌어올린다 (2005년 이전 데이터는 스킵).
    # QQQ 벤치마크 JSON은 전체 실험 중 가장 이른 시작일(min)에 동일 하한을 적용하여
    # 공유 파일로 저장한다. 대시보드는 연도별 inner join으로 각 실험 기간에 공통되는
    # 연도만 비교하므로 별도 분리 저장이 불필요하다.
    logger.debug("실험별 유효 시작일 계산 중...")
    effective_start_dates: dict[str, date] = {
        cfg.experiment_name: compute_portfolio_effective_start_date(cfg) for cfg in PORTFOLIO_CONFIGS
    }
    min_effective = min(effective_start_dates.values())
    benchmark_start_date = max(min_effective, DEFAULT_PORTFOLIO_START_DATE)
    logger.debug(f"실험별 유효 시작일(데이터 기준): {effective_start_dates}")
    logger.debug(f"정책 하한: {DEFAULT_PORTFOLIO_START_DATE}")
    logger.debug(f"QQQ 벤치마크 기준 시작일: {benchmark_start_date} (min(effective)={min_effective}, 하한 적용 후)")

    # 3-1. QQQ 벤치마크 연간 수익률 JSON 생성 (하한 적용된 최소 시작일 기준 공유)
    _save_benchmark_qqq_json(benchmark_start_date)

    # 4. 실험별 실행 (각 실험의 고유 시작일 + 정책 하한 적용)
    for config in target_configs:
        raw_start_date = effective_start_dates[config.experiment_name]
        exp_start_date = max(raw_start_date, DEFAULT_PORTFOLIO_START_DATE)
        logger.debug("=" * 70)
        logger.debug(
            f"실험 시작: {config.experiment_name} ({config.display_name}) — "
            f"start_date={exp_start_date} (데이터 기준 {raw_start_date}, 하한 {DEFAULT_PORTFOLIO_START_DATE})"
        )
        result = run_portfolio_backtest(config, start_date=exp_start_date)
        _print_summary(result)

        # 정합성 자동 검증 (5개 규칙) -- 위반 시 결과 저장 후 스크립트 중지
        violations = validate_portfolio_result(result)
        _save_portfolio_results(result)
        logger.debug(f"{config.display_name} 결과 파일 저장 완료: {config.result_dir}")

        if violations:
            for v in violations:
                logger.error(f"  {v}")
            raise ValueError(f"[{config.experiment_name}] 정합성 검증 위반 {len(violations)}건 발견. " f"상세 내역은 위 로그를 확인하세요.")
        logger.debug(f"[{config.experiment_name}] 정합성 검증 통과 (5개 규칙 모두 정상)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
