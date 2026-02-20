"""
백테스트 도메인 공통 TypedDict 정의

백테스트 도메인에서 공통으로 사용하는 딕셔너리 구조를 타입으로 정의한다.
- 성과 요약 (SummaryDict)
- 최적 파라미터 (BestGridParams)
- 공통 결과 컨테이너 (SingleBacktestResult)

전략 전용 타입은 각 전략 모듈에 정의한다:
- buffer_zone_helpers.py: BufferStrategyResultDict, EquityRecord, TradeRecord, HoldState, GridSearchResult
- buy_and_hold.py: BuyAndHoldConfig, BuyAndHoldParams
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import pandas as pd


class SummaryDict(TypedDict):
    """calculate_summary() 반환 타입.

    성과 지표 요약 딕셔너리.
    equity_df가 비어있는 경우 start_date/end_date가 포함되지 않으므로 NotRequired.
    """

    initial_capital: float
    final_capital: float
    total_return: float
    total_return_pct: float
    cagr: float
    mdd: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    start_date: NotRequired[str]
    end_date: NotRequired[str]


class BestGridParams(TypedDict):
    """load_best_grid_params() 반환 타입.

    grid_results.csv에서 CAGR 1위 파라미터 4개를 담는다.
    """

    ma_window: int
    buffer_zone_pct: float
    hold_days: int
    recent_months: int


@dataclass
class SingleBacktestResult:
    """run_single() 반환 타입.

    각 전략의 run_single() 함수가 공통으로 반환하는 결과 컨테이너.
    signal_df, equity_df, trades_df는 반올림 전 원시 데이터이며,
    저장 직전에 스크립트에서 반올림 처리한다.
    """

    strategy_name: str  # "buffer_zone", "buy_and_hold_qqq", "buy_and_hold_tqqq"
    display_name: str  # "버퍼존 전략", "Buy & Hold (QQQ)", "Buy & Hold (TQQQ)"
    signal_df: pd.DataFrame  # 저장용 시그널 데이터 (raw)
    equity_df: pd.DataFrame  # 에쿼티 데이터 (raw)
    trades_df: pd.DataFrame  # 거래 내역 (빈 DataFrame 가능)
    summary: Mapping[str, object]  # 요약 지표
    params_json: dict[str, Any]  # JSON 저장용 전략 파라미터
    result_dir: Path  # 결과 저장 디렉토리
    data_info: dict[str, str]  # 데이터 소스 경로 정보 (signal_path, trade_path)
