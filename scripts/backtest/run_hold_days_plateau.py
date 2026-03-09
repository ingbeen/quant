"""hold_days 고원 분석 스크립트

7개 자산 x 8개 hold_days = 56회 백테스트를 실행하여
Calmar 곡선의 고원(plateau) 형태를 확인한다.

기존 버퍼존 전략 엔진을 그대로 사용하되,
hold_days만 변경하며 반복 실행하는 래퍼 스크립트이다.
중간 결과(signal/equity/trades/summary) 파일은 저장하지 않고,
최종 집계 CSV 6종만 생성한다.

실행 명령어:
    poetry run python scripts/backtest/run_hold_days_plateau.py
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
_RESULT_DIR = BACKTEST_RESULTS_DIR / "hold_days_plateau"

# hold_days 탐색 값
_HOLD_DAYS_VALUES = [0, 1, 2, 3, 4, 5, 7, 10]

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


# ============================================================================
# 핵심 실행
# ============================================================================


def _run_all_experiments() -> pd.DataFrame:
    """56회 백테스트를 실행하고 결과를 DataFrame으로 반환한다.

    자산별로 데이터 로딩과 MA 계산을 1회만 수행한 뒤,
    8개 hold_days에 대해 전략을 반복 실행하여 summary만 수집한다.

    Returns:
        56행의 결과 DataFrame (asset, hold_days, cagr, mdd, calmar, trades, win_rate, period_start, period_end)
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

        # 2. MA 계산 (1회 - hold_days와 무관, 항상 EMA 200)
        signal_with_ma = add_single_moving_average(signal_df, 200, ma_type="ema")

        logger.debug(f"[{asset_label}] 데이터 로딩 완료: {len(signal_with_ma)}행")

        # 3. hold_days별 전략 실행
        for hold_days in _HOLD_DAYS_VALUES:
            config = replace(base_config, override_hold_days=hold_days)
            params, _ = resolve_params_for_config(config)

            _, _, summary = run_buffer_strategy(
                signal_with_ma,
                trade_df,
                params,
                log_trades=False,
                strategy_name=config.strategy_name,
            )

            results.append(
                {
                    "asset": asset_label,
                    "hold_days": hold_days,
                    "cagr": round(float(str(summary["cagr"])), 2),
                    "mdd": round(float(str(summary["mdd"])), 2),
                    "calmar": round(float(str(summary["calmar"])), 2),
                    "trades": int(str(summary["total_trades"])),
                    "win_rate": round(float(str(summary.get("win_rate", 0.0))), 2),
                    "period_start": str(summary.get("start_date", "")),
                    "period_end": str(summary.get("end_date", "")),
                }
            )

            logger.debug(
                f"  hold={hold_days}: "
                f"Calmar={summary['calmar']:.2f}, "
                f"CAGR={summary['cagr']:.2f}%, "
                f"MDD={summary['mdd']:.2f}%"
            )

    return pd.DataFrame(results)


# ============================================================================
# 결과 저장
# ============================================================================


def _save_pivot_csv(detail_df: pd.DataFrame, metric: str, filename: str) -> None:
    """메트릭별 피벗 테이블을 CSV로 저장한다.

    Args:
        detail_df: 56행 상세 결과 DataFrame
        metric: 피벗할 컬럼명 (calmar, cagr, mdd, trades, win_rate)
        filename: 저장할 파일명
    """
    pivot = detail_df.pivot(index="asset", columns="hold_days", values=metric)

    # 자산 순서 보장
    asset_order = [label for _, label in _ASSET_CONFIGS]
    pivot = pivot.reindex(asset_order)

    # 컬럼명 변환 (0 -> "hold=0")
    pivot.columns = [f"hold={h}" for h in pivot.columns]

    path = _RESULT_DIR / filename
    pivot.to_csv(path)
    logger.debug(f"저장 완료: {path}")


def _save_results(detail_df: pd.DataFrame) -> None:
    """결과 CSV 파일 6종을 저장한다.

    Args:
        detail_df: 56행 상세 결과 DataFrame
    """
    _RESULT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 상세 테이블 (56행)
    detail_path = _RESULT_DIR / "hold_days_plateau_analysis_detail.csv"
    detail_df.to_csv(detail_path, index=False)
    logger.debug(f"저장 완료: {detail_path}")

    # 2. 피벗 테이블 5종
    _save_pivot_csv(detail_df, "calmar", "hold_days_plateau_analysis_calmar.csv")
    _save_pivot_csv(detail_df, "cagr", "hold_days_plateau_analysis_cagr.csv")
    _save_pivot_csv(detail_df, "mdd", "hold_days_plateau_analysis_mdd.csv")
    _save_pivot_csv(detail_df, "trades", "hold_days_plateau_analysis_trades.csv")
    _save_pivot_csv(detail_df, "win_rate", "hold_days_plateau_analysis_winrate.csv")


# ============================================================================
# 터미널 출력
# ============================================================================


def _print_pivot_table(detail_df: pd.DataFrame, metric: str, title: str) -> None:
    """피벗 테이블을 터미널에 출력한다.

    Args:
        detail_df: 56행 상세 결과 DataFrame
        metric: 출력할 컬럼명
        title: 테이블 제목
    """
    pivot = detail_df.pivot(index="asset", columns="hold_days", values=metric)
    asset_order = [label for _, label in _ASSET_CONFIGS]
    pivot = pivot.reindex(asset_order)

    columns: list[tuple[str, int, Align]] = [("자산", 6, Align.LEFT)]
    for h in _HOLD_DAYS_VALUES:
        columns.append((f"h={h}", 8, Align.RIGHT))

    rows: list[list[str]] = []
    for asset in asset_order:
        row = [asset]
        for h in _HOLD_DAYS_VALUES:
            val = float(str(pivot.loc[asset, h]))
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
    logger.debug("hold_days 고원 분석 시작")
    logger.debug(f"자산: {len(_ASSET_CONFIGS)}개, hold_days: {_HOLD_DAYS_VALUES}")
    logger.debug(f"총 실행 횟수: {len(_ASSET_CONFIGS) * len(_HOLD_DAYS_VALUES)}회")

    # 1. 56회 백테스트 실행
    detail_df = _run_all_experiments()

    # 2. CSV 저장
    _save_results(detail_df)

    # 3. 터미널 출력
    _print_pivot_table(detail_df, "calmar", "[Calmar 비교]")
    _print_pivot_table(detail_df, "cagr", "[CAGR(%) 비교]")
    _print_pivot_table(detail_df, "mdd", "[MDD(%) 비교]")
    _print_pivot_table(detail_df, "trades", "[거래수 비교]")
    _print_pivot_table(detail_df, "win_rate", "[승률(%) 비교]")

    logger.debug(f"결과 저장 위치: {_RESULT_DIR}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
