"""파라미터 고원 분석 스크립트

3개 실험 x 7개 자산 x 6개 값 = 126회 백테스트를 실행하여
sell_buffer, buy_buffer, ma_window 각 파라미터의 고원 형태를 확인한다.

실험 A: sell_buffer = [0.01, 0.03, 0.05, 0.07, 0.10, 0.15] (나머지 고정)
실험 B: buy_buffer = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10] (나머지 고정)
실험 C: ma_window  = [50, 100, 150, 200, 250, 300] (나머지 고정)

hold_days 고원 분석 스크립트와 동일한 방법론으로,
한 번에 1개 파라미터만 변경하고 나머지를 고정한다.
중간 결과(signal/equity/trades/summary) 파일은 저장하지 않고,
최종 집계 CSV 16종만 생성한다.

실행 명령어:
    poetry run python scripts/backtest/run_param_plateau.py
"""

import sys
from dataclasses import replace
from typing import Any

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.strategies.buffer_zone import (
    get_config,
    resolve_params_for_config,
)
from qbt.backtest.strategies.buffer_zone_helpers import run_buffer_strategy
from qbt.common_constants import BACKTEST_RESULTS_DIR
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import extract_overlap_period, load_stock_data
from qbt.utils.formatting import Align, TableLogger

logger = get_logger(__name__)

# ============================================================================
# 로컬 상수
# ============================================================================

# 결과 저장 경로
_RESULT_DIR = BACKTEST_RESULTS_DIR / "param_plateau"

# 자산별 설정 (config_name, 표시 레이블)
_ASSET_CONFIGS: list[tuple[str, str]] = [
    ("buffer_zone_qqq_4p", "QQQ"),
    ("buffer_zone_spy", "SPY"),
    ("buffer_zone_iwm", "IWM"),
    ("buffer_zone_efa", "EFA"),
    ("buffer_zone_eem", "EEM"),
    ("buffer_zone_gld", "GLD"),
    ("buffer_zone_tlt", "TLT"),
]

# 공통 고정값
_FIXED_HOLD_DAYS = 3
_FIXED_RECENT_MONTHS = 0

# 실험 A: sell_buffer 탐색
_SELL_BUFFER_VALUES: list[float] = [0.01, 0.03, 0.05, 0.07, 0.10, 0.15]

# 실험 B: buy_buffer 탐색
_BUY_BUFFER_VALUES: list[float] = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]

# 실험 C: ma_window 탐색
_MA_WINDOW_VALUES: list[int] = [50, 100, 150, 200, 250, 300]

# 실험 A, B 공통 MA
_FIXED_MA_WINDOW = 200

# 실험 A, C 공통 buy_buffer
_FIXED_BUY_BUFFER = 0.03

# 실험 B, C 공통 sell_buffer
_FIXED_SELL_BUFFER = 0.05

# 실험 메타 정보 (label, param_name, col_prefix, values)
_EXPERIMENT_META: list[tuple[str, str, str, list[float] | list[int]]] = [
    ("A", "sell_buffer", "sell", _SELL_BUFFER_VALUES),
    ("B", "buy_buffer", "buy", _BUY_BUFFER_VALUES),
    ("C", "ma_window", "ma", _MA_WINDOW_VALUES),
]

# 피벗 지표
_METRICS: list[tuple[str, str]] = [
    ("calmar", "Calmar"),
    ("cagr", "CAGR(%)"),
    ("mdd", "MDD(%)"),
    ("trades", "거래수"),
    ("win_rate", "승률(%)"),
]


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
        experiment: 실험 레이블 ("A", "B", "C")
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
        "win_rate": round(float(str(summary.get("win_rate", 0.0))), 2),
        "period_start": str(summary.get("start_date", "")),
        "period_end": str(summary.get("end_date", "")),
    }


def _format_col_header(prefix: str, value: float | int) -> str:
    """피벗 컬럼 헤더를 포맷한다.

    Args:
        prefix: 컬럼 접두사 ("sell", "buy", "ma")
        value: 파라미터 값

    Returns:
        포맷된 헤더 문자열 (예: "sell=0.05", "ma=200")
    """
    if isinstance(value, int):
        return f"{prefix}={value}"
    return f"{prefix}={value:.2f}"


# ============================================================================
# 핵심 실행
# ============================================================================


def _run_all_experiments() -> pd.DataFrame:
    """126회 백테스트를 실행하고 결과를 DataFrame으로 반환한다.

    자산별로 데이터 로딩을 1회 수행한 뒤, 3개 실험을 순차 실행한다.
    실험 A/B: MA=200 1회 계산 후 재사용.
    실험 C: ma_window 값마다 MA 재계산.

    Returns:
        126행의 결과 DataFrame
    """
    results: list[dict[str, Any]] = []

    for config_name, asset_label in _ASSET_CONFIGS:
        base_config = get_config(config_name)

        # 1. 자산별 데이터 로딩 (1회)
        if base_config.signal_data_path == base_config.trade_data_path:
            trade_df = load_stock_data(base_config.trade_data_path)
            signal_df = trade_df.copy()
        else:
            signal_df = load_stock_data(base_config.signal_data_path)
            trade_df = load_stock_data(base_config.trade_data_path)
            signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

        # 2. 실험 A, B 공통: MA=200 계산 (1회)
        signal_ma200 = add_single_moving_average(signal_df, _FIXED_MA_WINDOW, ma_type="ema")

        logger.debug(f"[{asset_label}] 데이터 로딩 완료: {len(signal_df)}행")

        # 3. 실험 A: sell_buffer 변경
        for sell_val in _SELL_BUFFER_VALUES:
            config = replace(
                base_config,
                override_ma_window=_FIXED_MA_WINDOW,
                override_buy_buffer_zone_pct=_FIXED_BUY_BUFFER,
                override_sell_buffer_zone_pct=sell_val,
                override_hold_days=_FIXED_HOLD_DAYS,
                override_recent_months=_FIXED_RECENT_MONTHS,
            )
            params, _ = resolve_params_for_config(config)
            _, _, summary = run_buffer_strategy(
                signal_ma200,
                trade_df,
                params,
                log_trades=False,
                strategy_name=config.strategy_name,
            )
            results.append(_build_row("A", "sell_buffer", sell_val, asset_label, summary))
            logger.debug(
                f"  A sell={sell_val:.2f}: " f"Calmar={summary['calmar']:.2f}, " f"CAGR={summary['cagr']:.2f}%"
            )

        # 4. 실험 B: buy_buffer 변경
        for buy_val in _BUY_BUFFER_VALUES:
            config = replace(
                base_config,
                override_ma_window=_FIXED_MA_WINDOW,
                override_buy_buffer_zone_pct=buy_val,
                override_sell_buffer_zone_pct=_FIXED_SELL_BUFFER,
                override_hold_days=_FIXED_HOLD_DAYS,
                override_recent_months=_FIXED_RECENT_MONTHS,
            )
            params, _ = resolve_params_for_config(config)
            _, _, summary = run_buffer_strategy(
                signal_ma200,
                trade_df,
                params,
                log_trades=False,
                strategy_name=config.strategy_name,
            )
            results.append(_build_row("B", "buy_buffer", buy_val, asset_label, summary))
            logger.debug(f"  B buy={buy_val:.2f}: " f"Calmar={summary['calmar']:.2f}, " f"CAGR={summary['cagr']:.2f}%")

        # 5. 실험 C: ma_window 변경 (MA 재계산 필요)
        for ma_val in _MA_WINDOW_VALUES:
            signal_with_ma = add_single_moving_average(signal_df, ma_val, ma_type="ema")
            config = replace(
                base_config,
                override_ma_window=ma_val,
                override_buy_buffer_zone_pct=_FIXED_BUY_BUFFER,
                override_sell_buffer_zone_pct=_FIXED_SELL_BUFFER,
                override_hold_days=_FIXED_HOLD_DAYS,
                override_recent_months=_FIXED_RECENT_MONTHS,
            )
            params, _ = resolve_params_for_config(config)
            _, _, summary = run_buffer_strategy(
                signal_with_ma,
                trade_df,
                params,
                log_trades=False,
                strategy_name=config.strategy_name,
            )
            results.append(_build_row("C", "ma_window", ma_val, asset_label, summary))
            logger.debug(f"  C ma={ma_val}: " f"Calmar={summary['calmar']:.2f}, " f"CAGR={summary['cagr']:.2f}%")

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
        detail_df: 126행 상세 결과 DataFrame
        experiment: 실험 레이블 ("A", "B", "C")
        col_prefix: 컬럼 접두사 ("sell", "buy", "ma")
        param_values: 파라미터 탐색 값 목록 (순서 보장용)
        metric: 피벗할 컬럼명 (calmar, cagr, mdd, trades, win_rate)
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


def _save_results(detail_df: pd.DataFrame) -> None:
    """결과 CSV 파일 16종을 저장한다.

    Args:
        detail_df: 126행 상세 결과 DataFrame
    """
    _RESULT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 상세 테이블 (126행)
    detail_path = _RESULT_DIR / "param_plateau_all_detail.csv"
    detail_df.to_csv(detail_path, index=False)
    logger.debug(f"저장 완료: {detail_path}")

    # 2. 피벗 테이블 15종 (3실험 x 5지표)
    for exp_label, param_name, col_prefix, param_values in _EXPERIMENT_META:
        for metric_key, _ in _METRICS:
            filename = f"param_plateau_{param_name}_{metric_key}.csv"
            _save_pivot_csv(
                detail_df,
                exp_label,
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
        detail_df: 126행 상세 결과 DataFrame
        experiment: 실험 레이블
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


@cli_exception_handler
def main() -> int:
    """메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    total_runs = len(_ASSET_CONFIGS) * (len(_SELL_BUFFER_VALUES) + len(_BUY_BUFFER_VALUES) + len(_MA_WINDOW_VALUES))
    logger.debug("파라미터 고원 분석 시작")
    logger.debug(f"자산: {len(_ASSET_CONFIGS)}개, 실험: 3개 (A/B/C)")
    logger.debug(f"총 실행 횟수: {total_runs}회")

    # 1. 126회 백테스트 실행
    detail_df = _run_all_experiments()

    # 2. CSV 저장
    _save_results(detail_df)

    # 3. 터미널 출력 (3실험 x 5지표 = 15개 테이블)
    for exp_label, param_name, col_prefix, param_values in _EXPERIMENT_META:
        for metric_key, metric_title in _METRICS:
            title = f"[실험 {exp_label}: {param_name} - {metric_title}]"
            _print_pivot_table(
                detail_df,
                exp_label,
                col_prefix,
                param_values,
                metric_key,
                title,
            )

    logger.debug(f"결과 저장 위치: {_RESULT_DIR}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
