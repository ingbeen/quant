"""파라미터 고원 분석 통합 스크립트

파라미터(hold_days, sell_buffer, buy_buffer, ma_window)별 다자산의
고원(plateau) 형태를 확인한다.

각 실험에서 1개 파라미터만 변경하고 나머지를 4P 확정값으로 고정한다.
중간 결과(signal/equity/trades/summary) 파일은 저장하지 않고,
최종 집계 CSV만 생성한다.

실행 명령어:
    poetry run python scripts/backtest/run_param_plateau_all.py
    poetry run python scripts/backtest/run_param_plateau_all.py --experiment hold_days
    poetry run python scripts/backtest/run_param_plateau_all.py --experiment sell_buffer
"""

import argparse
import sys
from dataclasses import replace
from typing import Any

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import (
    FIXED_4P_BUY_BUFFER_ZONE_PCT,
    FIXED_4P_HOLD_DAYS,
    FIXED_4P_MA_WINDOW,
    FIXED_4P_SELL_BUFFER_ZONE_PCT,
)
from qbt.backtest.engines.backtest_engine import run_buffer_strategy
from qbt.backtest.strategies.buffer_zone import (
    get_config,
    resolve_params_for_config,
)
from qbt.common_constants import BACKTEST_RESULTS_DIR
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import extract_overlap_period, load_stock_data
from qbt.utils.formatting import Align, TableLogger

logger = get_logger(__name__)

# ============================================================================
# 로컬 상수
# ============================================================================

# 결과 저장 경로 (hold_days 결과도 이 디렉토리로 통합)
_RESULT_DIR = BACKTEST_RESULTS_DIR / "param_plateau"

# 자산별 설정 (config_name, 표시 레이블)
_ASSET_CONFIGS: list[tuple[str, str]] = [
    ("buffer_zone_qqq", "QQQ"),
    ("buffer_zone_spy", "SPY"),
    ("buffer_zone_iwm", "IWM"),
    ("buffer_zone_efa", "EFA"),
    ("buffer_zone_eem", "EEM"),
    ("buffer_zone_gld", "GLD"),
    ("buffer_zone_tlt", "TLT"),
]


# 실험별 탐색 값
_HOLD_DAYS_VALUES: list[int] = [0, 1, 2, 3, 4, 5, 7, 10]
_SELL_BUFFER_VALUES: list[float] = [0.01, 0.03, 0.05, 0.07, 0.10, 0.15]
_BUY_BUFFER_VALUES: list[float] = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]
_MA_WINDOW_VALUES: list[int] = [50, 100, 150, 200, 250, 300]

# 실험 메타 정보 (experiment_name, param_name, col_prefix, values)
_EXPERIMENT_META: list[tuple[str, str, str, list[float] | list[int]]] = [
    ("hold_days", "hold_days", "hold", _HOLD_DAYS_VALUES),
    ("sell_buffer", "sell_buffer", "sell", _SELL_BUFFER_VALUES),
    ("buy_buffer", "buy_buffer", "buy", _BUY_BUFFER_VALUES),
    ("ma_window", "ma_window", "ma", _MA_WINDOW_VALUES),
]

# 피벗 지표
_METRICS: list[tuple[str, str]] = [
    ("calmar", "Calmar"),
    ("cagr", "CAGR(%)"),
    ("mdd", "MDD(%)"),
    ("trades", "거래수"),
]

# --experiment 인자 유효값
_VALID_EXPERIMENTS = {"all", "hold_days", "sell_buffer", "buy_buffer", "ma_window"}


# ============================================================================
# 헬퍼 함수
# ============================================================================


def _build_row(
    experiment: str,
    param_name: str,
    param_value: float | int,
    asset_label: str,
    summary: Any,
) -> dict[str, Any]:
    """결과 행을 생성한다.

    Args:
        experiment: 실험명 ("hold_days", "sell_buffer", "buy_buffer", "ma_window")
        param_name: 파라미터명
        param_value: 파라미터 값
        asset_label: 자산 표시 레이블
        summary: 백테스트 성과 요약

    Returns:
        결과 행 딕셔너리
    """
    return {
        "experiment": experiment,
        "param_name": param_name,
        "param_value": param_value,
        "asset": asset_label,
        "cagr": round(float(str(summary["cagr"])), 2),
        "mdd": round(float(str(summary["mdd"])), 2),
        "calmar": round(float(str(summary["calmar"])), 2),
        "trades": int(str(summary["total_trades"])),
        "period_start": str(summary.get("start_date", "")),
        "period_end": str(summary.get("end_date", "")),
    }


def _format_col_header(prefix: str, value: float | int) -> str:
    """피벗 컬럼 헤더를 포맷한다.

    Args:
        prefix: 컬럼 접두사 ("hold", "sell", "buy", "ma")
        value: 파라미터 값

    Returns:
        포맷된 헤더 문자열 (예: "sell=0.05", "ma=200", "hold=3")
    """
    if isinstance(value, int):
        return f"{prefix}={value}"
    return f"{prefix}={value:.2f}"


# ============================================================================
# 핵심 실행
# ============================================================================


def _load_asset_data(
    config_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """자산별 데이터를 로딩한다.

    Args:
        config_name: 버퍼존 config 이름

    Returns:
        (signal_df, trade_df) 튜플
    """
    base_config = get_config(config_name)

    if base_config.signal_data_path == base_config.trade_data_path:
        trade_df = load_stock_data(base_config.trade_data_path)
        signal_df = trade_df.copy()
    else:
        signal_df = load_stock_data(base_config.signal_data_path)
        trade_df = load_stock_data(base_config.trade_data_path)
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    return signal_df, trade_df


def _run_experiments(selected_experiments: list[str]) -> pd.DataFrame:
    """선택된 실험들을 실행하고 결과를 DataFrame으로 반환한다.

    자산별로 데이터 로딩과 MA 계산을 최소화한다.

    Args:
        selected_experiments: 실행할 실험 이름 리스트

    Returns:
        결과 DataFrame
    """
    results: list[dict[str, Any]] = []

    for config_name, asset_label in _ASSET_CONFIGS:
        signal_df, trade_df = _load_asset_data(config_name)
        base_config = get_config(config_name)

        # MA=200 사전 계산 (hold_days, sell_buffer, buy_buffer 실험용)
        signal_ma200 = add_single_moving_average(signal_df, FIXED_4P_MA_WINDOW, ma_type="ema")

        logger.debug(f"[{asset_label}] 데이터 로딩 완료: {len(signal_df)}행")

        # 실험 1: hold_days
        if "hold_days" in selected_experiments:
            for hold_val in _HOLD_DAYS_VALUES:
                config = replace(
                    base_config,
                    ma_window=FIXED_4P_MA_WINDOW,
                    buy_buffer_zone_pct=FIXED_4P_BUY_BUFFER_ZONE_PCT,
                    sell_buffer_zone_pct=FIXED_4P_SELL_BUFFER_ZONE_PCT,
                    hold_days=hold_val,
                )
                params = resolve_params_for_config(config)
                _, _, summary = run_buffer_strategy(
                    signal_ma200,
                    trade_df,
                    params,
                    log_trades=False,
                    strategy_name=config.strategy_name,
                )
                results.append(_build_row("hold_days", "hold_days", hold_val, asset_label, summary))
                logger.debug(f"  hold={hold_val}: " f"Calmar={summary['calmar']:.2f}, " f"CAGR={summary['cagr']:.2f}%")

        # 실험 2: sell_buffer
        if "sell_buffer" in selected_experiments:
            for sell_val in _SELL_BUFFER_VALUES:
                config = replace(
                    base_config,
                    ma_window=FIXED_4P_MA_WINDOW,
                    buy_buffer_zone_pct=FIXED_4P_BUY_BUFFER_ZONE_PCT,
                    sell_buffer_zone_pct=sell_val,
                    hold_days=FIXED_4P_HOLD_DAYS,
                )
                params = resolve_params_for_config(config)
                _, _, summary = run_buffer_strategy(
                    signal_ma200,
                    trade_df,
                    params,
                    log_trades=False,
                    strategy_name=config.strategy_name,
                )
                results.append(_build_row("sell_buffer", "sell_buffer", sell_val, asset_label, summary))
                logger.debug(
                    f"  sell={sell_val:.2f}: " f"Calmar={summary['calmar']:.2f}, " f"CAGR={summary['cagr']:.2f}%"
                )

        # 실험 3: buy_buffer
        if "buy_buffer" in selected_experiments:
            for buy_val in _BUY_BUFFER_VALUES:
                config = replace(
                    base_config,
                    ma_window=FIXED_4P_MA_WINDOW,
                    buy_buffer_zone_pct=buy_val,
                    sell_buffer_zone_pct=FIXED_4P_SELL_BUFFER_ZONE_PCT,
                    hold_days=FIXED_4P_HOLD_DAYS,
                )
                params = resolve_params_for_config(config)
                _, _, summary = run_buffer_strategy(
                    signal_ma200,
                    trade_df,
                    params,
                    log_trades=False,
                    strategy_name=config.strategy_name,
                )
                results.append(_build_row("buy_buffer", "buy_buffer", buy_val, asset_label, summary))
                logger.debug(
                    f"  buy={buy_val:.2f}: " f"Calmar={summary['calmar']:.2f}, " f"CAGR={summary['cagr']:.2f}%"
                )

        # 실험 4: ma_window (MA 재계산 필요)
        if "ma_window" in selected_experiments:
            for ma_val in _MA_WINDOW_VALUES:
                signal_with_ma = add_single_moving_average(signal_df, ma_val, ma_type="ema")
                config = replace(
                    base_config,
                    ma_window=ma_val,
                    buy_buffer_zone_pct=FIXED_4P_BUY_BUFFER_ZONE_PCT,
                    sell_buffer_zone_pct=FIXED_4P_SELL_BUFFER_ZONE_PCT,
                    hold_days=FIXED_4P_HOLD_DAYS,
                )
                params = resolve_params_for_config(config)
                _, _, summary = run_buffer_strategy(
                    signal_with_ma,
                    trade_df,
                    params,
                    log_trades=False,
                    strategy_name=config.strategy_name,
                )
                results.append(_build_row("ma_window", "ma_window", ma_val, asset_label, summary))
                logger.debug(f"  ma={ma_val}: " f"Calmar={summary['calmar']:.2f}, " f"CAGR={summary['cagr']:.2f}%")

    return pd.DataFrame(results)


# ============================================================================
# 결과 저장
# ============================================================================


def _save_pivot_csv(
    detail_df: pd.DataFrame,
    experiment: str,
    col_prefix: str,
    param_values: list[float] | list[int],
    metric: str,
    filename: str,
) -> None:
    """실험별 메트릭 피벗 테이블을 CSV로 저장한다.

    Args:
        detail_df: 상세 결과 DataFrame
        experiment: 실험명
        col_prefix: 컬럼 접두사
        param_values: 파라미터 탐색 값 목록
        metric: 피벗할 컬럼명
        filename: 저장할 파일명
    """
    exp_df = detail_df[detail_df["experiment"] == experiment]
    pivot = exp_df.pivot(index="asset", columns="param_value", values=metric)

    # 자산 순서 보장
    asset_order = [label for _, label in _ASSET_CONFIGS]
    pivot = pivot.reindex(asset_order)

    # 컬럼 순서 보장 및 헤더 포맷
    pivot = pivot.reindex(columns=param_values)
    pivot.columns = [_format_col_header(col_prefix, v) for v in param_values]

    path = _RESULT_DIR / filename
    pivot.to_csv(path)
    logger.debug(f"저장 완료: {path}")


def _save_results(detail_df: pd.DataFrame, selected_experiments: list[str]) -> None:
    """결과 CSV 파일을 저장한다.

    Args:
        detail_df: 상세 결과 DataFrame
        selected_experiments: 실행한 실험 이름 리스트
    """
    _RESULT_DIR.mkdir(parents=True, exist_ok=True)

    # 피벗 테이블 (실험 x 지표)
    for exp_name, param_name, col_prefix, param_values in _EXPERIMENT_META:
        if exp_name not in selected_experiments:
            continue
        for metric_key, _ in _METRICS:
            filename = f"param_plateau_{param_name}_{metric_key}.csv"
            _save_pivot_csv(
                detail_df,
                exp_name,
                col_prefix,
                param_values,
                metric_key,
                filename,
            )


# ============================================================================
# 터미널 출력
# ============================================================================


def _print_pivot_table(
    detail_df: pd.DataFrame,
    experiment: str,
    col_prefix: str,
    param_values: list[float] | list[int],
    metric: str,
    title: str,
) -> None:
    """피벗 테이블을 터미널에 출력한다.

    Args:
        detail_df: 상세 결과 DataFrame
        experiment: 실험명
        col_prefix: 컬럼 접두사
        param_values: 파라미터 탐색 값 목록
        metric: 출력할 컬럼명
        title: 테이블 제목
    """
    exp_df = detail_df[detail_df["experiment"] == experiment]
    pivot = exp_df.pivot(index="asset", columns="param_value", values=metric)
    asset_order = [label for _, label in _ASSET_CONFIGS]
    pivot = pivot.reindex(asset_order)
    pivot = pivot.reindex(columns=param_values)

    columns: list[tuple[str, int, Align]] = [("자산", 6, Align.LEFT)]
    for v in param_values:
        header = _format_col_header(col_prefix, v)
        columns.append((header, 10, Align.RIGHT))

    rows: list[list[str]] = []
    for i, asset in enumerate(asset_order):
        row = [asset]
        for j in range(len(param_values)):
            val = float(str(pivot.iloc[i, j]))
            if metric == "trades":
                row.append(str(int(val)))
            else:
                row.append(f"{val:.2f}")
        rows.append(row)

    table = TableLogger(columns, logger)
    table.print_table(rows, title=title)


# ============================================================================
# 메인
# ============================================================================


def _parse_args() -> argparse.Namespace:
    """명령행 인자를 파싱한다.

    Returns:
        파싱된 인자 Namespace
    """
    parser = argparse.ArgumentParser(description="파라미터 고원 분석 통합 스크립트")
    parser.add_argument(
        "--experiment",
        type=str,
        default="all",
        choices=sorted(_VALID_EXPERIMENTS),
        help="실행할 실험 (기본: all)",
    )
    return parser.parse_args()


@cli_exception_handler
def main() -> int:
    """메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    args = _parse_args()

    # 실행할 실험 결정
    if args.experiment == "all":
        selected_experiments = [name for name, _, _, _ in _EXPERIMENT_META]
    else:
        selected_experiments = [args.experiment]

    # 총 실행 횟수 계산
    total_runs = 0
    for exp_name, _, _, param_values in _EXPERIMENT_META:
        if exp_name in selected_experiments:
            total_runs += len(_ASSET_CONFIGS) * len(param_values)

    logger.debug("파라미터 고원 분석 시작")
    logger.debug(f"자산: {len(_ASSET_CONFIGS)}개, 실험: {selected_experiments}")
    logger.debug(f"총 실행 횟수: {total_runs}회")

    # 1. 백테스트 실행
    detail_df = _run_experiments(selected_experiments)

    # 2. CSV 저장
    _save_results(detail_df, selected_experiments)

    # 3. 터미널 출력
    for exp_name, param_name, col_prefix, param_values in _EXPERIMENT_META:
        if exp_name not in selected_experiments:
            continue
        for metric_key, metric_title in _METRICS:
            title = f"[{param_name} - {metric_title}]"
            _print_pivot_table(
                detail_df,
                exp_name,
                col_prefix,
                param_values,
                metric_key,
                title,
            )

    logger.debug(f"결과 저장 위치: {_RESULT_DIR}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
