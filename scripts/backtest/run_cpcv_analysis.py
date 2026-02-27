"""
CSCV/PBO/DSR 과최적화 통계 검증 실행 스크립트

버퍼존 전략의 파라미터 탐색 과정에서 과최적화 위험을 통계적으로 검증합니다.
--strategy 인자로 실행할 전략을 선택할 수 있습니다 (기본값: all).

실행 명령어:
    poetry run python scripts/backtest/run_cpcv_analysis.py
    poetry run python scripts/backtest/run_cpcv_analysis.py --strategy buffer_zone_atr_tqqq
    poetry run python scripts/backtest/run_cpcv_analysis.py --strategy buffer_zone_tqqq
    poetry run python scripts/backtest/run_cpcv_analysis.py --strategy buffer_zone_qqq
"""

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import (
    CSCV_ANALYSIS_FILENAME,
    CSCV_LOGIT_LAMBDAS_FILENAME,
    DEFAULT_CSCV_METRIC,
    DEFAULT_CSCV_N_BLOCKS,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_WFO_ATR_MULTIPLIER_LIST,
    DEFAULT_WFO_ATR_PERIOD_LIST,
    DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST,
    DEFAULT_WFO_HOLD_DAYS_LIST,
    DEFAULT_WFO_MA_WINDOW_LIST,
    DEFAULT_WFO_RECENT_MONTHS_LIST,
    DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST,
    SLIPPAGE_RATE,
)
from qbt.backtest.cpcv import generate_param_combinations, run_cscv_analysis
from qbt.backtest.strategies import buffer_zone_atr_tqqq, buffer_zone_qqq, buffer_zone_tqqq
from qbt.backtest.types import CscvAnalysisResultDict
from qbt.common_constants import (
    COL_DATE,
    META_JSON_PATH,
    QQQ_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import extract_overlap_period, load_stock_data
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# 전략별 설정 매핑
STRATEGY_CONFIG: dict[str, dict[str, Path | list[int] | list[float] | None]] = {
    buffer_zone_tqqq.STRATEGY_NAME: {
        "signal_path": QQQ_DATA_PATH,
        "trade_path": TQQQ_SYNTHETIC_DATA_PATH,
        "result_dir": buffer_zone_tqqq.GRID_RESULTS_PATH.parent,
        "atr_period_list": None,
        "atr_multiplier_list": None,
    },
    buffer_zone_qqq.STRATEGY_NAME: {
        "signal_path": QQQ_DATA_PATH,
        "trade_path": QQQ_DATA_PATH,
        "result_dir": buffer_zone_qqq.GRID_RESULTS_PATH.parent,
        "atr_period_list": None,
        "atr_multiplier_list": None,
    },
    buffer_zone_atr_tqqq.STRATEGY_NAME: {
        "signal_path": QQQ_DATA_PATH,
        "trade_path": TQQQ_SYNTHETIC_DATA_PATH,
        "result_dir": buffer_zone_atr_tqqq.GRID_RESULTS_PATH.parent,
        "atr_period_list": DEFAULT_WFO_ATR_PERIOD_LIST,
        "atr_multiplier_list": DEFAULT_WFO_ATR_MULTIPLIER_LIST,
    },
}


def _load_data(strategy_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """전략에 맞는 데이터를 로딩한다.

    Args:
        strategy_name: 전략 이름

    Returns:
        (signal_df, trade_df) 튜플
    """
    config = STRATEGY_CONFIG[strategy_name]
    signal_path: Path = config["signal_path"]  # type: ignore[assignment]
    trade_path: Path = config["trade_path"]  # type: ignore[assignment]

    signal_df = load_stock_data(signal_path)

    if signal_path == trade_path:
        trade_df = signal_df.copy()
    else:
        trade_df = load_stock_data(trade_path)
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    return signal_df, trade_df


def _save_results(
    result: CscvAnalysisResultDict,
    result_dir: Path,
    logit_lambdas: list[float],
) -> tuple[Path, Path]:
    """분석 결과를 JSON과 CSV로 저장한다.

    Args:
        result: CscvAnalysisResultDict
        result_dir: 결과 저장 디렉토리
        logit_lambdas: PBO의 logit lambda 분포

    Returns:
        (json_path, csv_path) 튜플
    """
    result_dir.mkdir(parents=True, exist_ok=True)

    # 1. JSON 저장
    json_path = result_dir / CSCV_ANALYSIS_FILENAME
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # 2. logit lambda CSV 저장
    csv_path = result_dir / CSCV_LOGIT_LAMBDAS_FILENAME
    lambda_df = pd.DataFrame({"logit_lambda": logit_lambdas})
    lambda_df = lambda_df.round({"logit_lambda": 6})
    lambda_df.to_csv(csv_path, index=False)

    return json_path, csv_path


@cli_exception_handler
def main() -> int:
    """메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. argparse
    parser = argparse.ArgumentParser(description="CSCV/PBO/DSR 과최적화 통계 검증")
    parser.add_argument(
        "--strategy",
        choices=["all", *STRATEGY_CONFIG.keys()],
        default="all",
        help="실행할 전략 (기본값: all)",
    )
    args = parser.parse_args()

    # 2. 전략 목록 결정
    if args.strategy == "all":
        strategy_names = list(STRATEGY_CONFIG.keys())
    else:
        strategy_names = [args.strategy]

    logger.debug(f"실행 전략: {strategy_names}")

    # 3. 전략별 CSCV 분석 실행
    for strategy_name in strategy_names:
        config = STRATEGY_CONFIG[strategy_name]
        result_dir: Path = config["result_dir"]  # type: ignore[assignment]
        atr_period_list: list[int] | None = config["atr_period_list"]  # type: ignore[assignment]
        atr_multiplier_list: list[float] | None = config["atr_multiplier_list"]  # type: ignore[assignment]

        logger.debug("=" * 60)
        logger.debug(f"[{strategy_name}] CSCV/PBO/DSR 분석 시작")
        start_time = time.time()

        # 3-1. 데이터 로딩
        signal_df, trade_df = _load_data(strategy_name)
        logger.debug(
            f"데이터 로딩 완료: " f"기간 {signal_df[COL_DATE].min()} ~ {signal_df[COL_DATE].max()}, " f"거래일 {len(signal_df)}일"
        )

        # 3-2. 파라미터 조합 생성
        param_combinations = generate_param_combinations(
            ma_window_list=DEFAULT_WFO_MA_WINDOW_LIST,
            buy_buffer_zone_pct_list=DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST,
            sell_buffer_zone_pct_list=DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST,
            hold_days_list=DEFAULT_WFO_HOLD_DAYS_LIST,
            recent_months_list=DEFAULT_WFO_RECENT_MONTHS_LIST,
            initial_capital=DEFAULT_INITIAL_CAPITAL,
            atr_period_list=atr_period_list,
            atr_multiplier_list=atr_multiplier_list,
        )
        logger.debug(f"파라미터 조합 수: {len(param_combinations)}개")

        # 3-3. MA 사전 계산
        signal_df = signal_df.copy()
        for window in DEFAULT_WFO_MA_WINDOW_LIST:
            signal_df = add_single_moving_average(signal_df, window, ma_type="ema")
        logger.debug(f"이동평균 사전 계산 완료 (EMA): {sorted(DEFAULT_WFO_MA_WINDOW_LIST)}")

        # 3-4. CSCV 분석 실행
        result = run_cscv_analysis(
            signal_df=signal_df,
            trade_df=trade_df,
            param_combinations=param_combinations,
            strategy_name=strategy_name,
            n_blocks=DEFAULT_CSCV_N_BLOCKS,
            metric=DEFAULT_CSCV_METRIC,
        )

        elapsed = time.time() - start_time

        # 3-5. 결과 출력
        columns = [
            ("지표", 24, Align.LEFT),
            ("값", 16, Align.RIGHT),
        ]

        pbo_sharpe = result["pbo_sharpe"]
        dsr = result["dsr"]

        rows = [
            ["파라미터 조합 수", f"{result['n_param_combinations']}개"],
            ["관측 거래일 수", f"{result['t_observations']}일"],
            ["CSCV 블록 수", f"{pbo_sharpe['n_blocks']}"],
            ["CSCV 분할 수", f"{pbo_sharpe['n_splits']}"],
            ["PBO (Sharpe)", f"{pbo_sharpe['pbo']:.4f}"],
            ["PBO 판정", "과최적화 위험" if pbo_sharpe["pbo"] >= 0.5 else "양호"],
            ["DSR", f"{dsr['dsr']:.4f}"],
            ["DSR 판정", "유의" if dsr["dsr"] > 0.95 else "비유의"],
            ["관측 Sharpe (연간화)", f"{dsr['sr_observed']:.4f}"],
            ["기대 최대 Sharpe", f"{dsr['sr_benchmark']:.4f}"],
            ["Z-score", f"{dsr['z_score']:.4f}"],
            ["IS 최적 Sharpe", f"{result['best_is_sharpe']:.4f}"],
            ["실행 시간", f"{elapsed:.1f}초"],
        ]

        table = TableLogger(columns, logger)
        table.print_table(rows, title=f"[{strategy_name}] CSCV/PBO/DSR 분석 결과")

        # 3-6. 결과 저장
        logit_lambdas = pbo_sharpe["logit_lambdas"]
        json_path, csv_path = _save_results(result, result_dir, logit_lambdas)
        logger.debug(f"결과 저장 완료: {json_path}")
        logger.debug(f"Logit lambda CSV 저장 완료: {csv_path}")

        # 3-7. 메타데이터 저장
        metadata = {
            "strategy": strategy_name,
            "execution_params": {
                "n_blocks": DEFAULT_CSCV_N_BLOCKS,
                "metric": DEFAULT_CSCV_METRIC,
                "ma_window_list": DEFAULT_WFO_MA_WINDOW_LIST,
                "buy_buffer_zone_pct_list": [round(x, 4) for x in DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST],
                "sell_buffer_zone_pct_list": [round(x, 4) for x in DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST],
                "hold_days_list": DEFAULT_WFO_HOLD_DAYS_LIST,
                "recent_months_list": DEFAULT_WFO_RECENT_MONTHS_LIST,
                "initial_capital": round(DEFAULT_INITIAL_CAPITAL, 2),
                "slippage_rate": round(SLIPPAGE_RATE, 4),
            },
            "data_period": {
                "start_date": str(signal_df[COL_DATE].min()),
                "end_date": str(signal_df[COL_DATE].max()),
                "total_days": len(signal_df),
            },
            "results_summary": {
                "n_param_combinations": result["n_param_combinations"],
                "t_observations": result["t_observations"],
                "pbo_sharpe": round(pbo_sharpe["pbo"], 4),
                "dsr": round(dsr["dsr"], 4),
                "sr_observed": round(dsr["sr_observed"], 4),
                "sr_benchmark": round(dsr["sr_benchmark"], 4),
                "best_is_sharpe": result["best_is_sharpe"],
            },
            "elapsed_seconds": round(elapsed, 1),
        }

        save_metadata("cscv_analysis", metadata)
        logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
