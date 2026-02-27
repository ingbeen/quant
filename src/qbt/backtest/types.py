"""
백테스트 도메인 공통 TypedDict 정의

백테스트 도메인에서 공통으로 사용하는 딕셔너리 구조를 타입으로 정의한다.
- 미청산 포지션 (OpenPositionDict)
- 성과 요약 (SummaryDict)
- 최적 파라미터 (BestGridParams)
- 공통 결과 컨테이너 (SingleBacktestResult)
- WFO 윈도우 결과 (WfoWindowResultDict)
- WFO 모드 요약 (WfoModeSummaryDict)
- CSCV/PBO/DSR 과최적화 검증 (PboResultDict, DsrResultDict, CscvAnalysisResultDict)

전략 전용 타입은 각 전략 모듈에 정의한다:
- buffer_zone_helpers.py: BufferStrategyResultDict, EquityRecord, TradeRecord, HoldState, GridSearchResult
- buy_and_hold.py: BuyAndHoldConfig, BuyAndHoldParams
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NotRequired, TypedDict

import pandas as pd


class OpenPositionDict(TypedDict):
    """미청산 포지션 정보.

    백테스트 종료 시 보유 중인 포지션의 진입 정보를 담는다.
    summary에 포함되어 summary.json에 저장되며,
    대시보드에서 Feature Detection으로 Buy 마커를 생성한다.
    """

    entry_date: str  # ISO format "YYYY-MM-DD"
    entry_price: float  # 진입가 (슬리피지 반영, 소수점 6자리)
    shares: int  # 보유 수량


class SummaryDict(TypedDict):
    """calculate_summary() 반환 타입.

    성과 지표 요약 딕셔너리.
    equity_df가 비어있는 경우 start_date/end_date가 포함되지 않으므로 NotRequired.
    open_position은 백테스트 종료 시 보유 중인 포지션이 있을 때만 포함된다.
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
    open_position: NotRequired[OpenPositionDict]


class BestGridParams(TypedDict):
    """load_best_grid_params() 반환 타입.

    grid_results.csv에서 CAGR 1위 파라미터 5개를 담는다.
    """

    ma_window: int
    buy_buffer_zone_pct: float
    sell_buffer_zone_pct: float
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


class WfoWindowResultDict(TypedDict):
    """워크포워드 윈도우별 IS/OOS 결과.

    각 윈도우의 IS 최적화 결과와 OOS 독립 평가 결과를 담는다.
    """

    window_idx: int  # 윈도우 인덱스 (0-based)
    is_start: str  # IS 시작일 (ISO format)
    is_end: str  # IS 종료일 (ISO format)
    oos_start: str  # OOS 시작일 (ISO format)
    oos_end: str  # OOS 종료일 (ISO format)
    # IS 최적 파라미터 5개 + ATR 2개 (선택적)
    best_ma_window: int
    best_buy_buffer_zone_pct: float
    best_sell_buffer_zone_pct: float
    best_hold_days: int
    best_recent_months: int
    best_atr_period: NotRequired[int]  # ATR 전략에서만 포함
    best_atr_multiplier: NotRequired[float]  # ATR 전략에서만 포함
    # IS 성과 지표
    is_cagr: float
    is_mdd: float
    is_calmar: float
    is_trades: int
    is_win_rate: float
    # OOS 성과 지표
    oos_cagr: float
    oos_mdd: float
    oos_calmar: float
    oos_trades: int
    oos_win_rate: float
    # WFE (Walk-Forward Efficiency)
    wfe_calmar: float  # OOS Calmar / IS Calmar
    wfe_cagr: float  # OOS CAGR / IS CAGR


class WfoModeSummaryDict(TypedDict):
    """WFO 모드별 요약 통계.

    동적/sell_fixed/fully_fixed 각 모드의 OOS 성과 통합 요약.
    """

    n_windows: int  # 총 윈도우 수
    # OOS 통계
    oos_cagr_mean: float
    oos_cagr_std: float
    oos_mdd_mean: float
    oos_mdd_worst: float  # 가장 낮은 MDD (가장 큰 낙폭)
    oos_calmar_mean: float
    oos_calmar_std: float
    oos_trades_total: int
    oos_win_rate_mean: float
    # WFE 통계
    wfe_calmar_mean: float
    wfe_calmar_median: float
    wfe_cagr_mean: float  # CAGR 기반 WFE 평균
    wfe_cagr_median: float  # CAGR 기반 WFE 중앙값
    gap_calmar_median: float  # OOS Calmar - IS Calmar 중앙값
    wfe_calmar_robust: float  # IS Calmar > 0인 윈도우만 집계한 WFE Calmar 중앙값
    # Profit Concentration
    profit_concentration_max: float  # 최대 Profit Concentration (0~1)
    profit_concentration_window_idx: int  # 최대 PC가 발생한 윈도우 인덱스
    # 파라미터 안정성 진단용 (윈도우별 선택된 파라미터 값 리스트)
    param_ma_windows: list[int]
    param_buy_buffers: list[float]
    param_sell_buffers: list[float]
    param_hold_days: list[int]
    param_recent_months: list[int]
    # Stitched Equity 지표 (선택적)
    stitched_cagr: NotRequired[float]
    stitched_mdd: NotRequired[float]
    stitched_calmar: NotRequired[float]
    stitched_total_return_pct: NotRequired[float]


class PboResultDict(TypedDict):
    """PBO (Probability of Backtest Overfitting) 계산 결과.

    CSCV (Combinatorial Symmetric Cross-Validation) 기반으로
    IS 최적 전략이 OOS에서 중간(median) 이하로 떨어지는 비율을 측정한다.
    Bailey et al. (2017) 방법론.
    """

    pbo: float  # Probability of Backtest Overfitting (0~1)
    n_splits: int  # C(S, S/2) 조합 수
    n_blocks: int  # S (블록 수)
    logit_lambdas: list[float]  # 각 split의 logit(rank)
    rank_below_median: int  # rank <= 0.5인 횟수
    metric: str  # "sharpe" 또는 "calmar"


class DsrResultDict(TypedDict):
    """DSR (Deflated Sharpe Ratio) 계산 결과.

    다중검정 보정 + 왜도/첨도를 반영하여 Sharpe Ratio의
    통계적 유의성을 판정한다.
    Bailey & Lopez de Prado (2014) 방법론.
    """

    dsr: float  # Deflated Sharpe Ratio (0~1, 확률값)
    sr_observed: float  # 관측된 연간화 Sharpe Ratio
    sr_benchmark: float  # E[SR_max] (다중 시행 보정 기대값)
    z_score: float  # 표준화된 테스트 통계량
    n_trials: int  # 시행 수 (파라미터 조합 수)
    t_observations: int  # 관측 수 (시계열 길이)


class CscvAnalysisResultDict(TypedDict):
    """CSCV 통합 분석 결과.

    PBO(Sharpe 기반) + DSR을 하나의 딕셔너리에 담는다.
    Calmar 기반 PBO는 선택적으로 포함될 수 있다.
    """

    strategy: str  # 전략명
    n_param_combinations: int  # 파라미터 조합 수
    t_observations: int  # 시계열 길이 (거래일 수)
    pbo_sharpe: PboResultDict  # Sharpe 기반 PBO 결과
    pbo_calmar: NotRequired[PboResultDict]  # Calmar 기반 PBO (선택)
    dsr: DsrResultDict  # DSR 결과
    best_is_sharpe: float  # 전체기간 IS 최적 Sharpe
