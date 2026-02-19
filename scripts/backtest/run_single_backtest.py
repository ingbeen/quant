"""
단일 백테스트 실행 스크립트

이동평균선 교차 전략 백테스트 (EMA/Buy&Hold)
파라미터 우선순위: OVERRIDE 상수 → grid_results.csv 최적값 → DEFAULT 상수

실행 명령어:
    poetry run python scripts/backtest/run_single_backtest.py
"""

import json
import logging
import sys
from collections.abc import Mapping
from typing import Any

import pandas as pd

from qbt.backtest import (
    BufferStrategyParams,
    BuyAndHoldParams,
    add_single_moving_average,
    load_best_grid_params,
    run_buffer_strategy,
    run_buy_and_hold,
)
from qbt.backtest.constants import (
    DEFAULT_BUFFER_ZONE_PCT,
    DEFAULT_HOLD_DAYS,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MA_WINDOW,
    DEFAULT_RECENT_MONTHS,
)
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    EPSILON,
    GRID_RESULTS_PATH,
    META_JSON_PATH,
    QQQ_DATA_PATH,
    SINGLE_BACKTEST_EQUITY_PATH,
    SINGLE_BACKTEST_SIGNAL_PATH,
    SINGLE_BACKTEST_SUMMARY_PATH,
    SINGLE_BACKTEST_TRADES_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata

logger = get_logger(__name__)

# ============================================================
# 파라미터 오버라이드 (None = grid_results.csv 최적값 사용, 값 설정 = 수동)
# 폴백 체인: OVERRIDE → grid_results.csv 최적값 → DEFAULT
# ============================================================
OVERRIDE_MA_WINDOW: int | None = None
OVERRIDE_BUFFER_ZONE_PCT: float | None = None
OVERRIDE_HOLD_DAYS: int | None = None
OVERRIDE_RECENT_MONTHS: int | None = None

# MA 유형 (grid_search와 동일하게 EMA 사용)
MA_TYPE = "ema"


def print_summary(summary: Mapping[str, object], title: str, logger: logging.Logger) -> None:
    """
    요약 지표를 출력한다.

    Args:
        summary: 요약 지표 딕셔너리
        title: 출력 제목
        logger: 로거 인스턴스
    """
    logger.debug("=" * 60)
    logger.debug(f"[{title}]")
    logger.debug(f"  기간: {summary.get('start_date')} ~ {summary.get('end_date')}")
    logger.debug(f"  초기 자본: {summary['initial_capital']:,.0f}원")
    logger.debug(f"  최종 자본: {summary['final_capital']:,.0f}원")
    logger.debug(f"  총 수익률: {summary['total_return_pct']:.2f}%")
    logger.debug(f"  CAGR: {summary['cagr']:.2f}%")
    logger.debug(f"  MDD: {summary['mdd']:.2f}%")
    logger.debug(f"  총 거래 수: {summary['total_trades']}")
    if "win_rate" in summary:
        logger.debug(f"  승률: {summary['win_rate']:.1f}%")
        if "winning_trades" in summary:
            logger.debug(f"  승/패: {summary['winning_trades']}/{summary['losing_trades']}")
    logger.debug("=" * 60)


def _calculate_monthly_returns(equity_df: pd.DataFrame) -> list[dict[str, object]]:
    """
    에쿼티 데이터로부터 월별 수익률을 계산한다.

    Args:
        equity_df: 자본 곡선 DataFrame (Date, equity 컬럼 필수)

    Returns:
        월별 수익률 리스트 [{year, month, return_pct}, ...]
    """
    if equity_df.empty or len(equity_df) < 2:
        return []

    # 1. 에쿼티 데이터를 날짜 인덱스로 변환
    eq = equity_df[[COL_DATE, "equity"]].copy()
    eq[COL_DATE] = pd.to_datetime(eq[COL_DATE])
    eq = eq.set_index(COL_DATE)

    # 2. 월말 리샘플링
    monthly_equity = eq["equity"].resample("ME").last().dropna()
    if len(monthly_equity) < 2:
        return []

    # 3. 월간 수익률 계산 (%)
    monthly_returns = monthly_equity.pct_change().dropna() * 100

    # 4. 결과 리스트 생성
    dt_index = pd.DatetimeIndex(monthly_returns.index)
    result: list[dict[str, object]] = []
    for i in range(len(monthly_returns)):
        result.append(
            {
                "year": int(dt_index[i].year),
                "month": int(dt_index[i].month),
                "return_pct": round(float(monthly_returns.iloc[i]), 2),
            }
        )

    return result


def _save_results(
    signal_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    summary: Mapping[str, object],
    ma_window: int,
    buffer_zone_pct: float,
    hold_days: int,
    recent_months: int,
    ma_window_source: str,
    bz_source: str,
    hd_source: str,
    rm_source: str,
) -> None:
    """
    백테스트 결과를 CSV/JSON 파일로 저장한다.

    Args:
        signal_df: 시그널 DataFrame (OHLC + MA)
        equity_df: 에쿼티 DataFrame
        trades_df: 거래 내역 DataFrame
        summary: 요약 지표 딕셔너리
        ma_window: 이동평균 기간
        buffer_zone_pct: 버퍼존 비율
        hold_days: 유지일
        recent_months: 조정기간
        ma_window_source: ma_window 출처
        bz_source: buffer_zone_pct 출처
        hd_source: hold_days 출처
        rm_source: recent_months 출처
    """
    # 결과 디렉토리 생성
    SINGLE_BACKTEST_SIGNAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 1. signal CSV 저장 (OHLC + MA + change_pct)
    signal_export = signal_df.copy()
    signal_export["change_pct"] = signal_export[COL_CLOSE].pct_change() * 100
    ma_col = f"ma_{ma_window}"
    signal_export = signal_export.round(
        {
            COL_OPEN: 2,
            COL_HIGH: 2,
            COL_LOW: 2,
            COL_CLOSE: 2,
            ma_col: 2,
            "change_pct": 2,
        }
    )
    signal_export.to_csv(SINGLE_BACKTEST_SIGNAL_PATH, index=False)
    logger.debug(f"시그널 데이터 저장 완료: {SINGLE_BACKTEST_SIGNAL_PATH}")

    # 2. equity CSV 저장 (equity + bands + drawdown_pct)
    equity_export = equity_df.copy()
    equity_series = equity_export["equity"].astype(float)
    peak = equity_series.cummax()
    safe_peak = peak.replace(0, EPSILON)
    equity_export["drawdown_pct"] = (equity_series - peak) / safe_peak * 100
    equity_export = equity_export.round(
        {
            "equity": 0,
            "buffer_zone_pct": 4,
            "upper_band": 2,
            "lower_band": 2,
            "drawdown_pct": 2,
        }
    )
    equity_export["equity"] = equity_export["equity"].astype(int)
    equity_export.to_csv(SINGLE_BACKTEST_EQUITY_PATH, index=False)
    logger.debug(f"에쿼티 데이터 저장 완료: {SINGLE_BACKTEST_EQUITY_PATH}")

    # 3. trades CSV 저장 (거래 내역 + holding_days)
    if not trades_df.empty:
        trades_export = trades_df.copy()
        trades_export["holding_days"] = trades_export.apply(
            lambda row: (row["exit_date"] - row["entry_date"]).days, axis=1
        )
        trades_export = trades_export.round(
            {
                "entry_price": 6,
                "exit_price": 6,
                "pnl": 0,
                "pnl_pct": 4,
                "buffer_zone_pct": 4,
            }
        )
        trades_export["pnl"] = trades_export["pnl"].astype(int)
        trades_export.to_csv(SINGLE_BACKTEST_TRADES_PATH, index=False)
    else:
        trades_df.to_csv(SINGLE_BACKTEST_TRADES_PATH, index=False)
    logger.debug(f"거래 내역 저장 완료: {SINGLE_BACKTEST_TRADES_PATH}")

    # 4. summary JSON 저장
    monthly_returns = _calculate_monthly_returns(equity_df)

    summary_data: dict[str, Any] = {
        "summary": {
            "initial_capital": round(float(str(summary["initial_capital"]))),
            "final_capital": round(float(str(summary["final_capital"]))),
            "total_return_pct": round(float(str(summary["total_return_pct"])), 2),
            "cagr": round(float(str(summary["cagr"])), 2),
            "mdd": round(float(str(summary["mdd"])), 2),
            "total_trades": summary["total_trades"],
            "winning_trades": summary["winning_trades"],
            "losing_trades": summary["losing_trades"],
            "win_rate": round(float(str(summary["win_rate"])), 2),
            "start_date": summary.get("start_date", ""),
            "end_date": summary.get("end_date", ""),
        },
        "params": {
            "ma_window": ma_window,
            "ma_type": MA_TYPE,
            "buffer_zone_pct": round(buffer_zone_pct, 4),
            "hold_days": hold_days,
            "recent_months": recent_months,
            "initial_capital": round(DEFAULT_INITIAL_CAPITAL),
            "param_source": {
                "ma_window": ma_window_source,
                "buffer_zone_pct": bz_source,
                "hold_days": hd_source,
                "recent_months": rm_source,
            },
        },
        "monthly_returns": monthly_returns,
        "data_info": {
            "signal_path": str(QQQ_DATA_PATH),
            "trade_path": str(TQQQ_SYNTHETIC_DATA_PATH),
        },
    }

    with SINGLE_BACKTEST_SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    logger.debug(f"요약 JSON 저장 완료: {SINGLE_BACKTEST_SUMMARY_PATH}")

    # 5. 메타데이터 저장
    metadata: dict[str, Any] = {
        "params": {
            "ma_window": ma_window,
            "ma_type": MA_TYPE,
            "buffer_zone_pct": round(buffer_zone_pct, 4),
            "hold_days": hold_days,
            "recent_months": recent_months,
            "initial_capital": round(DEFAULT_INITIAL_CAPITAL, 2),
        },
        "results_summary": {
            "total_return_pct": round(float(str(summary["total_return_pct"])), 2),
            "cagr": round(float(str(summary["cagr"])), 2),
            "mdd": round(float(str(summary["mdd"])), 2),
            "total_trades": int(str(summary["total_trades"])),
            "win_rate": round(float(str(summary["win_rate"])), 2),
        },
        "output_files": {
            "signal_csv": str(SINGLE_BACKTEST_SIGNAL_PATH),
            "equity_csv": str(SINGLE_BACKTEST_EQUITY_PATH),
            "trades_csv": str(SINGLE_BACKTEST_TRADES_PATH),
            "summary_json": str(SINGLE_BACKTEST_SUMMARY_PATH),
        },
    }
    save_metadata("single_backtest", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")


@cli_exception_handler
def main() -> int:
    """
    메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 파라미터 결정 (폴백 체인: OVERRIDE → grid_best → DEFAULT)
    grid_params = load_best_grid_params(GRID_RESULTS_PATH)

    if grid_params is not None:
        logger.debug(f"grid_results.csv 최적값 로드 완료: {GRID_RESULTS_PATH}")
    else:
        logger.debug("grid_results.csv 없음, DEFAULT 상수 사용")

    # 1-1. ma_window
    if OVERRIDE_MA_WINDOW is not None:
        ma_window = OVERRIDE_MA_WINDOW
        ma_window_source = "OVERRIDE"
    elif grid_params is not None:
        ma_window = grid_params["ma_window"]
        ma_window_source = "grid_best"
    else:
        ma_window = DEFAULT_MA_WINDOW
        ma_window_source = "DEFAULT"

    # 1-2. buffer_zone_pct
    if OVERRIDE_BUFFER_ZONE_PCT is not None:
        buffer_zone_pct = OVERRIDE_BUFFER_ZONE_PCT
        bz_source = "OVERRIDE"
    elif grid_params is not None:
        buffer_zone_pct = grid_params["buffer_zone_pct"]
        bz_source = "grid_best"
    else:
        buffer_zone_pct = DEFAULT_BUFFER_ZONE_PCT
        bz_source = "DEFAULT"

    # 1-3. hold_days
    if OVERRIDE_HOLD_DAYS is not None:
        hold_days = OVERRIDE_HOLD_DAYS
        hd_source = "OVERRIDE"
    elif grid_params is not None:
        hold_days = grid_params["hold_days"]
        hd_source = "grid_best"
    else:
        hold_days = DEFAULT_HOLD_DAYS
        hd_source = "DEFAULT"

    # 1-4. recent_months
    if OVERRIDE_RECENT_MONTHS is not None:
        recent_months = OVERRIDE_RECENT_MONTHS
        rm_source = "OVERRIDE"
    elif grid_params is not None:
        recent_months = grid_params["recent_months"]
        rm_source = "grid_best"
    else:
        recent_months = DEFAULT_RECENT_MONTHS
        rm_source = "DEFAULT"

    logger.debug("버퍼존 전략 백테스트 시작")
    logger.debug(
        f"파라미터: ma_window={ma_window} ({ma_window_source}), "
        f"buffer_zone={buffer_zone_pct} ({bz_source}), "
        f"hold_days={hold_days} ({hd_source}), "
        f"recent_months={recent_months} ({rm_source})"
    )

    # 2. 데이터 로딩 (QQQ: 시그널, TQQQ: 매매)
    logger.debug(f"시그널 데이터: {QQQ_DATA_PATH}")
    logger.debug(f"매매 데이터: {TQQQ_SYNTHETIC_DATA_PATH}")
    signal_df = load_stock_data(QQQ_DATA_PATH)
    trade_df = load_stock_data(TQQQ_SYNTHETIC_DATA_PATH)

    logger.debug("=" * 60)
    logger.debug("데이터 로딩 완료")
    logger.debug(f"시그널(QQQ) 행 수: {len(signal_df):,}, 기간: {signal_df[COL_DATE].min()} ~ {signal_df[COL_DATE].max()}")
    logger.debug(f"매매(TQQQ) 행 수: {len(trade_df):,}, 기간: {trade_df[COL_DATE].min()} ~ {trade_df[COL_DATE].max()}")
    logger.debug("=" * 60)

    # 3. 날짜 기준 정렬 (겹치는 기간만 사용)
    common_dates = set(signal_df[COL_DATE]) & set(trade_df[COL_DATE])
    signal_df = signal_df[signal_df[COL_DATE].isin(common_dates)].reset_index(drop=True)
    trade_df = trade_df[trade_df[COL_DATE].isin(common_dates)].reset_index(drop=True)
    logger.debug(f"공통 기간: {len(signal_df):,}행")

    # 4. 이동평균 계산 (signal_df에만, grid_search와 동일하게 EMA 사용)
    signal_df = add_single_moving_average(signal_df, ma_window, ma_type=MA_TYPE)

    # 5. 전략 파라미터 설정
    params = BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=ma_window,
        buffer_zone_pct=buffer_zone_pct,
        hold_days=hold_days,
        recent_months=recent_months,
    )

    summaries = []

    # 6. 버퍼존 전략 실행 (QQQ 시그널 + TQQQ 매매)
    logger.debug("=" * 60)
    logger.debug("버퍼존 전략 백테스트 실행 (QQQ 시그널 + TQQQ 매매)")
    trades, equity_df, summary = run_buffer_strategy(signal_df, trade_df, params)
    print_summary(summary, "버퍼존 전략 결과", logger)

    # 거래 내역 출력
    if not trades.empty:
        columns = [
            ("진입일", 12, Align.LEFT),
            ("청산일", 12, Align.LEFT),
            ("진입가", 12, Align.RIGHT),
            ("청산가", 12, Align.RIGHT),
            ("손익률", 14, Align.RIGHT),
        ]

        max_rows = 10
        rows = []
        for _, trade in trades.tail(max_rows).iterrows():
            rows.append(
                [
                    str(trade["entry_date"]),
                    str(trade["exit_date"]),
                    f"{trade['entry_price']:.2f}",
                    f"{trade['exit_price']:.2f}",
                    f"{trade['pnl_pct'] * 100:+.2f}%",
                ]
            )

        table = TableLogger(columns, logger)
        table.print_table(rows, title=f"[버퍼존 전략] 거래 내역 (최근 {max_rows}건)")
    else:
        logger.debug("[버퍼존 전략] 거래 내역 없음")

    summaries.append(("버퍼존 전략", summary))

    # 7. Buy & Hold 벤치마크 실행 (TQQQ 기준)
    logger.debug("Buy & Hold 벤치마크 실행 (TQQQ)")
    params_bh = BuyAndHoldParams(initial_capital=DEFAULT_INITIAL_CAPITAL)
    _, summary_bh = run_buy_and_hold(signal_df, trade_df, params=params_bh)
    print_summary(summary_bh, "Buy & Hold 결과", logger)
    summaries.append(("Buy & Hold", summary_bh))

    # 8. 전략 비교 요약
    columns = [
        ("전략", 20, Align.LEFT),
        ("총수익률", 12, Align.RIGHT),
        ("CAGR", 10, Align.RIGHT),
        ("MDD", 10, Align.RIGHT),
        ("거래수", 10, Align.RIGHT),
    ]

    rows = []
    for name, summary in summaries:
        rows.append(
            [
                name,
                f"{summary['total_return_pct']:.2f}%",
                f"{summary['cagr']:.2f}%",
                f"{summary['mdd']:.2f}%",
                str(summary["total_trades"]),
            ]
        )

    table = TableLogger(columns, logger)
    table.print_table(rows, title="[전략 비교 요약]")

    # 9. 결과 파일 저장 (대시보드용)
    buffer_summary = summaries[0][1]
    _save_results(
        signal_df=signal_df,
        equity_df=equity_df,
        trades_df=trades,
        summary=buffer_summary,
        ma_window=ma_window,
        buffer_zone_pct=buffer_zone_pct,
        hold_days=hold_days,
        recent_months=recent_months,
        ma_window_source=ma_window_source,
        bz_source=bz_source,
        hd_source=hd_source,
        rm_source=rm_source,
    )
    logger.debug("결과 파일 저장 완료")

    return 0


if __name__ == "__main__":
    sys.exit(main())
