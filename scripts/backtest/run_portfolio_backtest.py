"""포트폴리오 백테스트 실행 스크립트

포트폴리오 실험을 실행하고 결과를 저장한다.
--experiment 인자로 실행할 실험을 선택할 수 있다.

실행 명령어:
    poetry run python scripts/backtest/run_portfolio_backtest.py
    poetry run python scripts/backtest/run_portfolio_backtest.py --experiment portfolio_d1
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from qbt.backtest.analysis import (
    calculate_monthly_returns,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_yearly_returns,
)
from qbt.backtest.constants import (
    EQUITY_FILENAME,
    LEDGER_FILENAME,
    NETTING_FILENAME,
    SUMMARY_FILENAME,
    TRADES_FILENAME,
    ma_col_name,
    portfolio_signal_filename,
)
from qbt.backtest.csv_export import (
    add_buffer_zone_bands,
    add_ohlc_change_pct,
    prepare_trades_for_csv,
    remove_config_dependent_files,
    round_signal_for_csv,
)
from qbt.backtest.engines.portfolio_engine import compute_portfolio_effective_start_date, run_portfolio_backtest
from qbt.backtest.engines.portfolio_methods import account_target_weights, summarize_methods
from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS, get_portfolio_config
from qbt.backtest.portfolio_types import (
    PortfolioResult,
    asset_shares_col,
    list_position_keys,
    resolve_methods,
)
from qbt.backtest.portfolio_validation import validate_portfolio_result
from qbt.backtest.supplement_experiment import run_with_start_check
from qbt.common_constants import (
    COL_DATE,
    ROUND_CAPITAL,
    ROUND_PERCENT,
    ROUND_PRICE,
    ROUND_RATIO,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.formatting import Align, TableLogger

logger = get_logger(__name__)

_STATE_LOG_FILENAME = "state_log.csv"

# 포트폴리오 백테스트 최소 시작일 하한
# 각 실험의 effective_start_date가 이 날짜 이전이어도 이 날짜부터 실행한다
# (2005년 이전 데이터는 포트폴리오 비교 범위에서 제외). 설정에 min_start_date 가 있는 실험은 이 하한 대신 그 날짜에 시작한다.
DEFAULT_PORTFOLIO_START_DATE: date = date(2005, 1, 1)


def _find_last_entry_date(equity_df: pd.DataFrame, asset_id: str) -> str:
    """보유 주수가 마지막으로 0 → 양수로 바뀐 거래일을 반환한다 (미청산 포지션의 진입일).

    최종일에 보유 중인 자산에만 부른다 — 보유한 적이 없으면 바뀐 날이 없어 IndexError 로 멈춘다.

    Args:
        equity_df: 포트폴리오 에쿼티 DataFrame (Date, {asset_id}_shares 포함)
        asset_id: 자산 키

    Returns:
        entry_date 문자열 (YYYY-MM-DD)
    """
    shares = equity_df[asset_shares_col(asset_id)].astype(int)
    entered = (shares.shift(1, fill_value=0) == 0) & (shares > 0)
    return str(equity_df.loc[entered, COL_DATE].iloc[-1])


def _save_portfolio_results(result: PortfolioResult) -> None:
    """포트폴리오 백테스트 결과를 CSV/JSON 파일로 저장한다.

    저장 파일:
    - equity.csv: 합산 에쿼티 + 자산 키별 비중/시그널 + 리밸런싱 여부 (+ 매매법이 여럿이면 netting_savings)
    - trades.csv: 전 자산 거래 내역 + holding_days
    - signal_{자산 키}.csv: 자산 키별 시그널 (OHLCV + MA + 밴드 + 전일종가대비%)
    - state_log.csv: 거래일마다 엔진 내부 상태 (신호 · 의도 · 체결 · 보유)
    - summary.json: 전체 + 자산 키별 요약 지표 + 설정 파라미터 (+ 매매법이 여럿이면 per_method · netting · account_holdings · pnl_check)
    - ledger.csv · netting.csv: 매매법이 여럿일 때만 — 매매법별 장부, 종목 단위 상계 내역

    Args:
        result: PortfolioResult 컨테이너
    """
    result.config.result_dir.mkdir(parents=True, exist_ok=True)
    remove_config_dependent_files(result.config.result_dir)

    # 1. equity.csv 저장
    equity_path = result.config.result_dir / EQUITY_FILENAME
    equity_export = result.equity_df.copy()

    equity_round: dict[str, int] = {
        "equity": ROUND_CAPITAL,
        "cash": ROUND_CAPITAL,
        "drawdown_pct": ROUND_PERCENT,
    }
    if "netting_savings" in equity_export.columns:
        equity_round["netting_savings"] = ROUND_CAPITAL
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
    capital_cols = ["equity", "cash", "netting_savings"] + [c for c in equity_export.columns if c.endswith("_value")]
    for col in capital_cols + pnl_cols:
        if col in equity_export.columns:
            equity_export[col] = equity_export[col].astype(int)
    for col in [c for c in equity_export.columns if c.endswith("_shares")]:
        equity_export[col] = equity_export[col].astype(int)

    equity_export.to_csv(equity_path, index=False)
    logger.debug(f"에쿼티 데이터 저장 완료: {equity_path}")

    # 2. trades.csv 저장
    trades_path = result.config.result_dir / TRADES_FILENAME
    prepare_trades_for_csv(result.trades_df).to_csv(trades_path, index=False)
    logger.debug(f"거래 내역 저장 완료: {trades_path}")

    # 3. signal_{asset_id}.csv 저장 (자산별)
    # 자산 키 -> 슬롯 매핑 (밴드 계산 시 슬롯의 전략 파라미터 조회용, 비중이 바뀌는 매매법 자산은 None)
    key_infos = {info.key: info for info in list_position_keys(result.config)}
    for asset_result in result.per_asset:
        signal_path = result.config.result_dir / portfolio_signal_filename(asset_result.asset_id)

        # 4종 OHLC 전일대비% 사전 계산 (대시보드 SSoT)
        signal_export = add_ohlc_change_pct(asset_result.signal_df)

        # buffer_zone 자산은 upper_band / lower_band 컬럼 사전 계산 (대시보드 SSoT)
        slot = key_infos[asset_result.asset_id].slot
        if slot is not None and slot.strategy_id == "buffer_zone":
            signal_export = add_buffer_zone_bands(
                signal_export,
                ma_col_name(slot.ma_window),
                buy_buffer_zone_pct=slot.buy_buffer_zone_pct,
                sell_buffer_zone_pct=slot.sell_buffer_zone_pct,
            )

        round_signal_for_csv(signal_export).to_csv(signal_path, index=False)
        logger.debug(f"시그널 데이터 저장 완료: {signal_path} (asset_id={asset_result.asset_id})")

    # 4. state_log.csv 저장 (일별 엔진 내부 상태: 시그널/intent/체결/포지션)
    # 읽는 코드는 없지만 남긴다 — 리밸런싱 연구(docs/research/전략_검증_보고서.md 부록 L.5)가 이 파일을 근거물로 쓴다
    state_log_path = result.config.result_dir / _STATE_LOG_FILENAME
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
        state_log_export[col] = state_log_export[col].astype(int)
    for col in state_log_export.columns:
        if col.endswith("_shares") or col.endswith("_exec_shares"):
            state_log_export[col] = state_log_export[col].astype(int)
    state_log_export.to_csv(state_log_path, index=False)
    logger.debug(f"State Log 저장 완료: {state_log_path}")

    # 5. summary.json 저장
    summary_path = result.config.result_dir / SUMMARY_FILENAME
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
        "calmar": round(float(str(s["calmar"])), ROUND_RATIO),
        "sharpe_ratio": round(sharpe, ROUND_RATIO),
        "sortino_ratio": round(sortino, ROUND_RATIO),
        "total_trades": s["total_trades"],
        "start_date": str(s["start_date"]),
        "end_date": str(s["end_date"]),
    }

    # 자산별 요약
    per_asset_data: list[dict[str, Any]] = []
    target_weights = account_target_weights(result)
    final_row = result.equity_df.iloc[-1]
    for asset_result in result.per_asset:
        asset_id = asset_result.asset_id
        asset_entry: dict[str, Any] = {
            "asset_id": asset_id,
            "target_weight": round(target_weights[asset_id], ROUND_RATIO),
        }

        # 미청산 포지션(open_position): 최종일에 보유 중인 자산만 기록
        # 대시보드의 시그널 차트가 "Buy (보유중)" 마커로 표시하는 데 사용
        final_shares = int(final_row[asset_shares_col(asset_id)])
        if final_shares > 0:
            asset_entry["open_position"] = {
                "entry_date": _find_last_entry_date(result.equity_df, asset_id),
                "entry_price": round(float(final_row[f"{asset_id}_avg_price"]), ROUND_PRICE),
                "shares": final_shares,
            }

        per_asset_data.append(asset_entry)

    # 월별/연간 수익률 계산 (대시보드에서 히트맵 표시용)
    monthly_returns = calculate_monthly_returns(result.equity_df)
    yearly_returns = calculate_yearly_returns(result.equity_df)

    summary_data: dict[str, Any] = {
        "display_name": result.display_name,
        "portfolio_summary": portfolio_summary,
        "per_asset": per_asset_data,
        "portfolio_config": result.params_json,
        "monthly_returns": monthly_returns,
        "yearly_returns": yearly_returns,
    }

    # 매매법이 여럿이면 매매법 장부 · 상계 내역과 요약을 더한다 (하나면 장부 = 계좌라 내지 않는다)
    multi_method = len(resolve_methods(result.config)) > 1
    if multi_method:
        _save_ledger_and_netting(
            result, result.config.result_dir / LEDGER_FILENAME, result.config.result_dir / NETTING_FILENAME
        )
        summary_data.update(_round_method_summary(summarize_methods(result)))

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    logger.debug(f"요약 JSON 저장 완료: {summary_path}")


def _save_ledger_and_netting(result: PortfolioResult, ledger_path: Path, netting_path: Path) -> None:
    """매매법 장부(ledger.csv)와 종목 단위 상계 내역(netting.csv)을 저장한다."""
    ledger_export = result.ledger_df.copy()
    money_cols = ["equity", "cash", "pnl", "cost", "transfers"]
    ledger_export = ledger_export.round(
        {**{c: ROUND_CAPITAL for c in money_cols}, "share": ROUND_RATIO, "target_share": ROUND_RATIO}
    )
    for col in money_cols:
        ledger_export[col] = ledger_export[col].astype(int)
    ledger_export.to_csv(ledger_path, index=False)
    logger.debug(f"매매법 장부 저장 완료: {ledger_path}")

    netting_export = result.netting_df.copy()
    netting_export = netting_export.round({"open_price": ROUND_PRICE, "savings": ROUND_CAPITAL})
    netting_export["savings"] = netting_export["savings"].astype(int)
    netting_export.to_csv(netting_path, index=False)
    logger.debug(f"상계 내역 저장 완료: {netting_path} ({len(netting_export)}행)")


def _round_method_summary(method_summary: dict[str, Any]) -> dict[str, Any]:
    """summarize_methods 결과를 저장 자릿수로 반올림한다 (자본금 정수, 비율 4자리)."""
    per_method: list[dict[str, Any]] = []
    for item in method_summary["per_method"]:
        per_method.append(
            {
                **item,
                "target_share": round(item["target_share"], ROUND_RATIO),
                "final_share": round(item["final_share"], ROUND_RATIO),
                "final_equity": round(item["final_equity"]),
                "pnl": round(item["pnl"]),
                "realized_pnl": round(item["realized_pnl"]),
                "unrealized_pnl": round(item["unrealized_pnl"]),
                "cost": round(item["cost"]),
                "transfers": round(item["transfers"]),
                "assets": [{"asset_id": a["asset_id"], "pnl": round(a["pnl"])} for a in item["assets"]],
            }
        )
    netting = dict(method_summary["netting"])
    netting["savings_total"] = round(netting["savings_total"])
    holdings = [
        {**h, "value": round(h["value"]), "weight": round(h["weight"], ROUND_RATIO)}
        for h in method_summary["account_holdings"]
    ]
    pnl_check = {k: round(v) for k, v in method_summary["pnl_check"].items()}
    return {"per_method": per_method, "netting": netting, "account_holdings": holdings, "pnl_check": pnl_check}


def _print_summary(result: PortfolioResult) -> None:
    """포트폴리오 백테스트 결과 요약을 출력한다.

    Args:
        result: PortfolioResult 컨테이너
    """
    s = result.summary
    logger.debug("=" * 70)
    logger.debug(f"[{result.display_name}] 포트폴리오 백테스트 결과")
    logger.debug(f"  기간: {s['start_date']} ~ {s['end_date']}")
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
        ("자산", 16, Align.LEFT),
        ("비중", 8, Align.RIGHT),
        ("거래수", 8, Align.RIGHT),
    ]

    rows = []
    target_weights = account_target_weights(result)
    for asset_result in result.per_asset:
        target_weight = target_weights[asset_result.asset_id]
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
        choices=["all", *(c.experiment_name for c in PORTFOLIO_CONFIGS)],
        default="all",
        help="실행할 실험 (기본값: all)",
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
    # 실행 전에 한꺼번에 계산한다 — 시세 누락 같은 데이터 문제가 앞 실험의 결과 파일을 덮어쓴 뒤가 아니라 그 전에 드러난다.
    effective_start_dates = {c.experiment_name: compute_portfolio_effective_start_date(c) for c in target_configs}
    late_starts = [
        f"{c.experiment_name}(설정 {c.min_start_date}, 데이터 기준 {effective_start_dates[c.experiment_name]})"
        for c in target_configs
        if c.min_start_date is not None and effective_start_dates[c.experiment_name] > c.min_start_date
    ]
    if late_starts:
        raise ValueError(
            "설정의 시작일(min_start_date)보다 데이터가 늦게 시작하는 실험이 있습니다 — 그대로 돌리면 그리드 결과와 "
            f"기간이 달라집니다: {', '.join(late_starts)}. 시세를 다시 받았다면 supplement_experiment.py 의 묶음 시작일 "
            "상수(MAIN_START_DATE 등)를 다시 재고 run_supplement_grid.py · run_combo_grid.py 를 다시 돌린 뒤 실행하세요"
        )

    # 4. 실험별 실행
    for config in target_configs:
        raw_start_date = effective_start_dates[config.experiment_name]
        logger.debug("=" * 70)
        if config.min_start_date is None:
            # 자기 자산 조합의 공통 기간 + MA 워밍업 이후를 쓰되, 정책 하한으로 끌어올린다 (2005년 이전 데이터는 스킵)
            exp_start_date = max(raw_start_date, DEFAULT_PORTFOLIO_START_DATE)
            logger.debug(
                f"실험 시작: {config.experiment_name} ({config.display_name}) — "
                f"start_date={exp_start_date} (데이터 기준 {raw_start_date}, 하한 {DEFAULT_PORTFOLIO_START_DATE})"
            )
            result = run_portfolio_backtest(config, start_date=exp_start_date)
        else:
            # 설정이 시작일을 정한 실험(보완 전략 등록 실험)은 그리드와 같은 날 시작해야 숫자가 그리드 결과와 같다.
            # 데이터가 늦게 시작하는 경우는 위에서 실행 전에 멈추고, 여기서는 실제 첫 거래일이 그날인지 한 번 더 대조한다
            logger.debug(
                f"실험 시작: {config.experiment_name} ({config.display_name}) — "
                f"start_date={config.min_start_date} (설정의 min_start_date, 데이터 기준 {raw_start_date})"
            )
            result = run_with_start_check(config, config.min_start_date)
        _print_summary(result)

        # 정합성 자동 검증 -- 위반 시 결과 저장 후 스크립트 중지
        violations = validate_portfolio_result(result)
        _save_portfolio_results(result)
        logger.debug(f"{config.display_name} 결과 파일 저장 완료: {config.result_dir}")

        if violations:
            for v in violations:
                logger.error(f"  {v}")
            raise ValueError(f"[{config.experiment_name}] 정합성 검증 위반 {len(violations)}건 발견. " f"상세 내역은 위 로그를 확인하세요.")
        logger.debug(f"[{config.experiment_name}] 정합성 검증 통과 (모든 규칙 정상)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
