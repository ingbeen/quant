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
from qbt.backtest.engines.backtest_engine import prepare_common_period, run_buffer_strategy
from qbt.backtest.parameter_stability import get_plateau_dir, plateau_csv_path
from qbt.backtest.strategies.buffer_zone import (
    get_config,
    resolve_params_for_config,
)
from qbt.backtest.types import SummaryDict
from qbt.common_constants import ROUND_PERCENT, ROUND_RATIO
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_signal_trade_pair
from qbt.utils.formatting import Align, TableLogger

logger = get_logger(__name__)

# ============================================================================
# 로컬 상수
# ============================================================================

# 자산별 설정 (config_name, 표시 레이블)
_ASSET_CONFIGS: list[tuple[str, str]] = [
    ("buffer_zone_qqq", "QQQ"),
    ("buffer_zone_spy", "SPY"),
    ("buffer_zone_gld", "GLD"),
    ("buffer_zone_tlt", "TLT"),
    ("buffer_zone_ugl", "UGL"),
    ("buffer_zone_ubt", "UBT"),
]


# 실험별 탐색 값
_HOLD_DAYS_VALUES: list[int] = [0, 1, 2, 3, 4, 5, 7, 10]
_SELL_BUFFER_VALUES: list[float] = [0.01, 0.03, 0.05, 0.07, 0.10, 0.15]
_BUY_BUFFER_VALUES: list[float] = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]
_MA_WINDOW_VALUES: list[int] = [50, 100, 150, 200, 250, 300]

# 실험 (실험 이름 = 결과 파일의 파라미터 이름, 바꾸는 설정 칸, 피벗 헤더 접두사, 탐색 값)
_EXPERIMENTS: list[tuple[str, str, str, list[float] | list[int]]] = [
    ("hold_days", "hold_days", "hold", _HOLD_DAYS_VALUES),
    ("sell_buffer", "sell_buffer_zone_pct", "sell", _SELL_BUFFER_VALUES),
    ("buy_buffer", "buy_buffer_zone_pct", "buy", _BUY_BUFFER_VALUES),
    ("ma_window", "ma_window", "ma", _MA_WINDOW_VALUES),
]

# 피벗 지표
_METRICS: list[tuple[str, str]] = [
    ("calmar", "Calmar"),
    ("cagr", "CAGR(%)"),
    ("mdd", "MDD(%)"),
    ("trades", "거래수"),
]


# ============================================================================
# 헬퍼 함수
# ============================================================================


def _build_row(
    experiment: str,
    param_value: float | int,
    asset_label: str,
    summary: SummaryDict,
) -> dict[str, Any]:
    """결과 행을 생성한다.

    Args:
        experiment: 실험명 ("hold_days", "sell_buffer", "buy_buffer", "ma_window")
        param_value: 파라미터 값
        asset_label: 자산 표시 레이블
        summary: 백테스트 성과 요약

    Returns:
        결과 행 딕셔너리
    """
    return {
        "experiment": experiment,
        "param_value": param_value,
        "asset": asset_label,
        "cagr": round(summary["cagr"], ROUND_PERCENT),
        "mdd": round(summary["mdd"], ROUND_PERCENT),
        "calmar": round(summary["calmar"], ROUND_RATIO),
        "trades": summary["total_trades"],
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


def _run_experiments(selected_experiments: list[tuple[str, str, str, list[float] | list[int]]]) -> pd.DataFrame:
    """선택된 실험들을 실행하고 결과를 DataFrame으로 반환한다.

    자산별로 데이터 로딩과 MA 계산을 최소화한다.

    Args:
        selected_experiments: 실행할 실험 (`_EXPERIMENTS` 의 항목)

    Returns:
        결과 DataFrame
    """
    results: list[dict[str, Any]] = []

    for config_name, asset_label in _ASSET_CONFIGS:
        base_config = get_config(config_name)
        signal_df, trade_df = load_signal_trade_pair(base_config.signal_data_path, base_config.trade_data_path)
        fixed_4p_config = replace(
            base_config,
            ma_window=FIXED_4P_MA_WINDOW,
            buy_buffer_zone_pct=FIXED_4P_BUY_BUFFER_ZONE_PCT,
            sell_buffer_zone_pct=FIXED_4P_SELL_BUFFER_ZONE_PCT,
            hold_days=FIXED_4P_HOLD_DAYS,
        )

        # 4P 이동평균 사전 계산 (hold_days, sell_buffer, buy_buffer 실험용)
        signal_ma_4p = add_single_moving_average(signal_df, FIXED_4P_MA_WINDOW)

        logger.debug(f"[{asset_label}] 데이터 로딩 완료: {len(signal_df)}행")

        for experiment, config_field, _, values in selected_experiments:
            if config_field == "ma_window":
                # 모든 이동평균 값을 같은 기간으로 평가한다
                exp_signal, exp_trade = prepare_common_period(signal_df, trade_df, values)
            else:
                exp_signal, exp_trade = signal_ma_4p, trade_df

            for value in values:
                params = resolve_params_for_config(replace(fixed_4p_config, **{config_field: value}))
                _, _, summary = run_buffer_strategy(
                    exp_signal,
                    exp_trade,
                    params,
                    log_trades=False,
                    strategy_name=config_name,
                )
                results.append(_build_row(experiment, value, asset_label, summary))
                logger.debug(f"  {experiment}={value}: Calmar={summary['calmar']:.2f}, CAGR={summary['cagr']:.2f}%")

    return pd.DataFrame(results)


def _pivot(
    detail_df: pd.DataFrame,
    experiment: str,
    col_prefix: str,
    param_values: list[float] | list[int],
    metric: str,
) -> pd.DataFrame:
    """실험 하나 · 지표 하나의 피벗(행 = 자산, 열 = 파라미터 값)을 만든다.

    Args:
        detail_df: 상세 결과 DataFrame
        experiment: 실험명
        col_prefix: 컬럼 접두사
        param_values: 파라미터 탐색 값 목록
        metric: 피벗할 컬럼명

    Returns:
        자산 순서 · 값 순서를 고정하고 열 머리를 `접두사=값` 으로 바꾼 피벗
    """
    exp_df = detail_df[detail_df["experiment"] == experiment]
    pivot = exp_df.pivot(index="asset", columns="param_value", values=metric)
    pivot = pivot.reindex([label for _, label in _ASSET_CONFIGS])
    pivot = pivot.reindex(columns=param_values)
    pivot.columns = [_format_col_header(col_prefix, v) for v in param_values]
    return pivot


# ============================================================================
# 터미널 출력
# ============================================================================


def _print_pivot_table(pivot: pd.DataFrame, metric: str, title: str) -> None:
    """피벗 테이블을 터미널에 출력한다.

    Args:
        pivot: `_pivot` 결과
        metric: 지표명 (거래수만 정수로 출력)
        title: 테이블 제목
    """
    columns: list[tuple[str, int, Align]] = [("자산", 6, Align.LEFT)]
    columns.extend((str(header), 10, Align.RIGHT) for header in pivot.columns)

    rows: list[list[str]] = []
    for asset, values in pivot.iterrows():
        row = [str(asset)]
        for value in values:
            val = float(str(value))
            row.append(str(int(val)) if metric == "trades" else f"{val:.2f}")
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
        choices=["all", *(name for name, _, _, _ in _EXPERIMENTS)],
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
    selected_experiments = [exp for exp in _EXPERIMENTS if args.experiment in ("all", exp[0])]

    total_runs = len(_ASSET_CONFIGS) * sum(len(values) for _, _, _, values in selected_experiments)

    logger.debug("파라미터 고원 분석 시작")
    logger.debug(f"자산: {len(_ASSET_CONFIGS)}개, 실험: {[name for name, _, _, _ in selected_experiments]}")
    logger.debug(f"총 실행 횟수: {total_runs}회")

    # 1. 백테스트 실행
    detail_df = _run_experiments(selected_experiments)

    # 2. 피벗 (실험 x 지표)
    pivots = {
        (experiment, metric): _pivot(detail_df, experiment, col_prefix, values, metric)
        for experiment, _, col_prefix, values in selected_experiments
        for metric, _ in _METRICS
    }

    # 3. CSV 저장
    get_plateau_dir().mkdir(parents=True, exist_ok=True)
    for (experiment, metric), pivot in pivots.items():
        path = plateau_csv_path(experiment, metric)
        pivot.to_csv(path)
        logger.debug(f"저장 완료: {path}")

    # 4. 터미널 출력
    metric_titles = dict(_METRICS)
    for (experiment, metric), pivot in pivots.items():
        _print_pivot_table(pivot, metric, f"[{experiment} - {metric_titles[metric]}]")

    logger.debug(f"결과 저장 위치: {get_plateau_dir()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
