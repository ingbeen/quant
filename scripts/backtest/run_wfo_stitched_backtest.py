"""WFO Stitched 백테스트 결과를 대시보드 호환 형식으로 저장한다.

run_walkforward.py 실행 결과(walkforward_dynamic.csv)를 읽어
params_schedule 기반으로 OOS 구간 전체를 1회 실행하고,
app_single_backtest.py 대시보드에서 시각화할 수 있는 형식으로 저장한다.

선행 스크립트:
    poetry run python scripts/backtest/run_walkforward.py --strategy buffer_zone_atr_tqqq

실행 명령어:
    poetry run python scripts/backtest/run_wfo_stitched_backtest.py
"""

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from qbt.backtest.analysis import (
    add_single_moving_average,
    calculate_monthly_returns,
    calculate_summary,
)
from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    WALKFORWARD_DYNAMIC_FILENAME,
)
from qbt.backtest.strategies.buffer_zone_helpers import run_buffer_strategy
from qbt.backtest.walkforward import build_params_schedule, load_wfo_results_from_csv
from qbt.common_constants import (
    BACKTEST_RESULTS_DIR,
    BUFFER_ZONE_ATR_TQQQ_RESULTS_DIR,
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
from qbt.utils.data_loader import extract_overlap_period, load_stock_data
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# WFO Stitched 전략 식별 상수
STRATEGY_NAME = "buffer_zone_atr_tqqq_wfo"
DISPLAY_NAME = "버퍼존 전략 ATR WFO (TQQQ)"

# 결과 저장 디렉토리
RESULT_DIR = BACKTEST_RESULTS_DIR / STRATEGY_NAME

# 대시보드 signal.csv에 표시할 MA 컬럼 (11개 윈도우 중 10개가 MA=200)
DEFAULT_SIGNAL_MA_WINDOW = 200


def _save_signal_csv(signal_df: pd.DataFrame, result_dir: Path) -> Path:
    """시그널 데이터를 CSV로 저장한다 (OHLC + MA + change_pct).

    Args:
        signal_df: OOS 구간 시그널 DataFrame (ma_200 컬럼 포함)
        result_dir: 결과 저장 디렉토리

    Returns:
        저장된 CSV 파일 경로
    """
    signal_path = result_dir / "signal.csv"

    signal_export = signal_df.copy()
    signal_export["change_pct"] = signal_export[COL_CLOSE].pct_change() * 100

    # 반올림 규칙: 가격/MA → 6자리, change_pct → 2자리
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
    return signal_path


def _save_equity_csv(equity_df: pd.DataFrame, result_dir: Path) -> Path:
    """에쿼티 데이터를 CSV로 저장한다 (equity + drawdown_pct + 밴드).

    Args:
        equity_df: 에쿼티 DataFrame
        result_dir: 결과 저장 디렉토리

    Returns:
        저장된 CSV 파일 경로
    """
    equity_path = result_dir / "equity.csv"

    equity_export = equity_df.copy()

    # drawdown_pct 계산 (단일 백테스트와 동일)
    equity_series = equity_export["equity"].astype(float)
    peak = equity_series.cummax()
    safe_peak = peak.replace(0, EPSILON)
    equity_export["drawdown_pct"] = (equity_series - peak) / safe_peak * 100

    # 반올림 규칙: equity → 0자리, drawdown_pct → 2자리, buffer → 4자리, band → 6자리
    equity_round: dict[str, int] = {"equity": 0, "drawdown_pct": 2}
    if "buy_buffer_pct" in equity_export.columns:
        equity_round["buy_buffer_pct"] = 4
    if "sell_buffer_pct" in equity_export.columns:
        equity_round["sell_buffer_pct"] = 4
    if "upper_band" in equity_export.columns:
        equity_round["upper_band"] = 6
    if "lower_band" in equity_export.columns:
        equity_round["lower_band"] = 6

    equity_export = equity_export.round(equity_round)
    equity_export["equity"] = equity_export["equity"].astype(int)
    equity_export.to_csv(equity_path, index=False)
    logger.debug(f"에쿼티 데이터 저장 완료: {equity_path}")
    return equity_path


def _save_trades_csv(trades_df: pd.DataFrame, result_dir: Path) -> Path:
    """거래 내역을 CSV로 저장한다 (거래 내역 + holding_days).

    Args:
        trades_df: 거래 내역 DataFrame
        result_dir: 결과 저장 디렉토리

    Returns:
        저장된 CSV 파일 경로
    """
    trades_path = result_dir / "trades.csv"

    if not trades_df.empty:
        trades_export = trades_df.copy()
        if "entry_date" in trades_export.columns and "exit_date" in trades_export.columns:
            trades_export["holding_days"] = trades_export.apply(
                lambda row: (row["exit_date"] - row["entry_date"]).days, axis=1
            )

        # 반올림 규칙: 가격 → 6자리, pnl → 0자리, 비율 → 4자리
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
        trades_df.to_csv(trades_path, index=False)

    logger.debug(f"거래 내역 저장 완료: {trades_path}")
    return trades_path


def _save_summary_json(
    summary: dict[str, object],
    equity_df: pd.DataFrame,
    window_results: list[dict[str, object]],
    result_dir: Path,
) -> Path:
    """요약 지표를 JSON으로 저장한다.

    Args:
        summary: calculate_summary() 반환 결과
        equity_df: 에쿼티 DataFrame (월별 수익률 계산용)
        window_results: WFO 윈도우 결과 리스트
        result_dir: 결과 저장 디렉토리

    Returns:
        저장된 JSON 파일 경로
    """
    summary_path = result_dir / "summary.json"

    # 1. 성과 지표 반올림
    summary_dict: dict[str, Any] = {
        "initial_capital": round(float(str(summary["initial_capital"]))),
        "final_capital": round(float(str(summary["final_capital"]))),
        "total_return_pct": round(float(str(summary["total_return_pct"])), 2),
        "cagr": round(float(str(summary["cagr"])), 2),
        "mdd": round(float(str(summary["mdd"])), 2),
        "total_trades": summary["total_trades"],
        "winning_trades": summary.get("winning_trades", 0),
        "losing_trades": summary.get("losing_trades", 0),
        "win_rate": round(float(str(summary.get("win_rate", 0.0))), 2),
        "start_date": summary.get("start_date", ""),
        "end_date": summary.get("end_date", ""),
    }

    # 2. 미청산 포지션 정보 (있는 경우에만 저장)
    open_position_raw = summary.get("open_position")
    if open_position_raw is not None and isinstance(open_position_raw, dict):
        summary_dict["open_position"] = {
            "entry_date": str(open_position_raw["entry_date"]),
            "entry_price": round(float(str(open_position_raw["entry_price"])), 6),
            "shares": int(str(open_position_raw["shares"])),
        }

    # 3. WFO 메타 정보 (params)
    last_window = window_results[-1]
    latest_params: dict[str, Any] = {
        "ma_window": last_window["best_ma_window"],
        "buy_buffer_zone_pct": last_window["best_buy_buffer_zone_pct"],
        "sell_buffer_zone_pct": last_window["best_sell_buffer_zone_pct"],
        "hold_days": last_window["best_hold_days"],
        "recent_months": last_window["best_recent_months"],
    }
    if "best_atr_period" in last_window:
        latest_params["atr_period"] = last_window["best_atr_period"]
    if "best_atr_multiplier" in last_window:
        latest_params["atr_multiplier"] = last_window["best_atr_multiplier"]

    params: dict[str, Any] = {
        "wfo_mode": "dynamic",
        "n_windows": len(window_results),
        "oos_start": str(window_results[0]["oos_start"]),
        "oos_end": str(window_results[-1]["oos_end"]),
        "source_csv": WALKFORWARD_DYNAMIC_FILENAME,
        "latest_window_params": latest_params,
    }

    # 4. 월별 수익률
    monthly_returns = calculate_monthly_returns(equity_df)

    # 5. 데이터 정보
    data_info: dict[str, str] = {
        "signal_ticker": "QQQ",
        "trade_ticker": "TQQQ_synthetic",
        "start_date": str(summary.get("start_date", "")),
        "end_date": str(summary.get("end_date", "")),
        "total_days": str(len(equity_df)),
    }

    # 6. JSON 구성
    summary_data: dict[str, Any] = {
        "display_name": DISPLAY_NAME,
        "summary": summary_dict,
        "params": params,
        "monthly_returns": monthly_returns,
        "data_info": data_info,
    }

    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    logger.debug(f"요약 JSON 저장 완료: {summary_path}")
    return summary_path


@cli_exception_handler
def main() -> int:
    """메인 실행 함수."""
    # 1. WFO 결과 CSV 로딩
    wfo_csv_path = BUFFER_ZONE_ATR_TQQQ_RESULTS_DIR / WALKFORWARD_DYNAMIC_FILENAME
    logger.debug(f"WFO 결과 CSV 로딩: {wfo_csv_path}")
    window_results = load_wfo_results_from_csv(wfo_csv_path)
    logger.debug(f"WFO 윈도우 {len(window_results)}개 로딩 완료")

    # 2. params_schedule 구축
    initial_params, schedule = build_params_schedule(window_results)
    logger.debug(f"params_schedule 구축 완료: 초기 MA={initial_params.ma_window}, " f"전환 {len(schedule)}회")

    # 3. OOS 범위 추출
    first_oos_start = date.fromisoformat(str(window_results[0]["oos_start"]))
    last_oos_end = date.fromisoformat(str(window_results[-1]["oos_end"]))
    logger.debug(f"OOS 범위: {first_oos_start} ~ {last_oos_end}")

    # 4. 데이터 로딩
    signal_df = load_stock_data(QQQ_DATA_PATH)
    trade_df = load_stock_data(TQQQ_SYNTHETIC_DATA_PATH)
    signal_df, trade_df = extract_overlap_period(signal_df, trade_df)
    logger.debug(f"데이터 로딩 완료: {signal_df[COL_DATE].min()} ~ {signal_df[COL_DATE].max()}, " f"{len(signal_df)}행")

    # 5. OOS 범위로 필터링
    oos_mask = (signal_df[COL_DATE] >= first_oos_start) & (signal_df[COL_DATE] <= last_oos_end)
    oos_signal = signal_df[oos_mask].reset_index(drop=True)
    oos_trade = trade_df[oos_mask].reset_index(drop=True)
    logger.debug(f"OOS 데이터: {len(oos_signal)}행")

    # 6. 모든 MA 윈도우 사전 계산
    all_ma_windows = {initial_params.ma_window}
    for p in schedule.values():
        all_ma_windows.add(p.ma_window)

    for window in all_ma_windows:
        oos_signal = add_single_moving_average(oos_signal, window, ma_type="ema")

    # 7. signal.csv용 ma_200 컬럼 확인 (없으면 추가)
    ma_col = f"ma_{DEFAULT_SIGNAL_MA_WINDOW}"
    if ma_col not in oos_signal.columns:
        oos_signal = add_single_moving_average(oos_signal, DEFAULT_SIGNAL_MA_WINDOW, ma_type="ema")

    # 8. run_buffer_strategy 실행
    trades_df, equity_df, strategy_summary = run_buffer_strategy(
        oos_signal,
        oos_trade,
        initial_params,
        log_trades=False,
        params_schedule=schedule,
    )

    # 9. calculate_summary로 성과 지표 계산
    summary = calculate_summary(trades_df, equity_df, DEFAULT_INITIAL_CAPITAL)

    # 미청산 포지션 정보 전달 (strategy_summary에서)
    if "open_position" in strategy_summary:
        summary["open_position"] = strategy_summary["open_position"]  # type: ignore[literal-required]

    logger.debug(f"백테스트 완료: CAGR={summary['cagr']:.2f}%, MDD={summary['mdd']:.2f}%, " f"거래수={summary['total_trades']}")

    # 10. 결과 저장
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    signal_path = _save_signal_csv(oos_signal, RESULT_DIR)
    equity_path = _save_equity_csv(equity_df, RESULT_DIR)
    trades_path = _save_trades_csv(trades_df, RESULT_DIR)
    summary_path = _save_summary_json(summary, equity_df, window_results, RESULT_DIR)  # type: ignore[arg-type]

    # 11. 메타데이터 저장
    metadata: dict[str, Any] = {
        "strategy": STRATEGY_NAME,
        "display_name": DISPLAY_NAME,
        "wfo_mode": "dynamic",
        "n_windows": len(window_results),
        "results_summary": {
            "total_return_pct": round(float(str(summary["total_return_pct"])), 2),
            "cagr": round(float(str(summary["cagr"])), 2),
            "mdd": round(float(str(summary["mdd"])), 2),
            "total_trades": int(str(summary["total_trades"])),
            "win_rate": round(float(str(summary.get("win_rate", 0.0))), 2),
        },
        "output_files": {
            "signal_csv": str(signal_path),
            "equity_csv": str(equity_path),
            "trades_csv": str(trades_path),
            "summary_json": str(summary_path),
        },
    }
    save_metadata("wfo_stitched_backtest", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")

    # 12. 요약 출력
    logger.debug("=" * 60)
    logger.debug(f"[{DISPLAY_NAME}] WFO Stitched 백테스트 완료")
    logger.debug(f"  기간: {summary.get('start_date')} ~ {summary.get('end_date')}")
    logger.debug(f"  초기 자본: {summary['initial_capital']:,.0f}원")
    logger.debug(f"  최종 자본: {summary['final_capital']:,.0f}원")
    logger.debug(f"  총 수익률: {summary['total_return_pct']:.2f}%")
    logger.debug(f"  CAGR: {summary['cagr']:.2f}%")
    logger.debug(f"  MDD: {summary['mdd']:.2f}%")
    logger.debug(f"  총 거래수: {summary['total_trades']}")
    logger.debug(f"  승률: {summary.get('win_rate', 0.0):.1f}%")
    logger.debug(f"  결과 디렉토리: {RESULT_DIR}")
    logger.debug("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
