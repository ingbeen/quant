"""분할 매수매도 오케스트레이터 모듈

3개 트랜치(ma250/ma200/ma150)를 독립 실행 후 결과를 조합하는
오케스트레이터 패턴 구현.

기존 run_buffer_strategy()를 블랙박스로 호출하며, 기존 코드 무변경 원칙을 준수한다.

포함 내용:
- DataClasses: SplitTrancheConfig, SplitStrategyConfig, SplitTrancheResult, SplitStrategyResult
- 설정 리스트: SPLIT_CONFIGS
- 핵심 함수: run_split_backtest
- 헬퍼 함수: _combine_equity, _combine_trades, _calculate_combined_summary, _build_params_json
- 팩토리 함수: create_split_runner

설계 근거: docs/tranche_architecture.md, docs/tranche_final_recommendation.md
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average, calculate_summary
from qbt.backtest.constants import (
    SPLIT_TRANCHE_IDS,
    SPLIT_TRANCHE_MA_WINDOWS,
    SPLIT_TRANCHE_WEIGHTS,
)
from qbt.backtest.strategies.buffer_zone import BufferZoneConfig
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    BufferStrategyResultDict,
    run_buffer_strategy,
)
from qbt.backtest.types import SummaryDict
from qbt.common_constants import (
    BUFFER_ZONE_QQQ_RESULTS_DIR,
    BUFFER_ZONE_TQQQ_RESULTS_DIR,
    COL_DATE,
    QQQ_DATA_PATH,
    SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR,
    SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)


# ============================================================================
# 데이터 클래스
# ============================================================================


@dataclass(frozen=True)
class SplitTrancheConfig:
    """분할 매수매도 트랜치별 설정."""

    tranche_id: str  # "ma250", "ma200", "ma150"
    weight: float  # 0.33, 0.34, 0.33
    ma_window: int  # 250, 200, 150


@dataclass(frozen=True)
class SplitStrategyConfig:
    """분할 매수매도 전략 설정."""

    strategy_name: str  # "split_buffer_zone_tqqq"
    display_name: str  # "분할 버퍼존 (TQQQ)"
    base_config: BufferZoneConfig  # 기존 자산 설정 (데이터 경로, 4P 파라미터)
    total_capital: float  # 총 자본금
    tranches: tuple[SplitTrancheConfig, ...]  # 트랜치별 설정 (frozen 지원)
    result_dir: Path  # 결과 저장 디렉토리


@dataclass
class SplitTrancheResult:
    """트랜치별 백테스트 결과."""

    tranche_id: str
    config: SplitTrancheConfig
    trades_df: pd.DataFrame
    equity_df: pd.DataFrame
    summary: BufferStrategyResultDict


@dataclass
class SplitStrategyResult:
    """분할 매수매도 전체 결과."""

    strategy_name: str
    display_name: str
    combined_equity_df: pd.DataFrame  # 합산 에쿼티 (시각화 메인)
    combined_trades_df: pd.DataFrame  # 전체 거래 (tranche_id 포함)
    combined_summary: SummaryDict  # 분할 레벨 성과 지표
    per_tranche: list[SplitTrancheResult]  # 트랜치별 결과
    config: SplitStrategyConfig  # 원본 설정 (재현성)
    params_json: dict[str, Any]  # JSON 저장용
    signal_df: pd.DataFrame  # 시그널 데이터 (OHLCV + MA, 시각화용)


# ============================================================================
# 기본 트랜치 설정 생성
# ============================================================================


def _build_default_tranches() -> tuple[SplitTrancheConfig, ...]:
    """기본 트랜치 설정을 생성한다.

    constants.py의 SPLIT_TRANCHE_* 상수를 기반으로
    SplitTrancheConfig 튜플을 생성한다.

    Returns:
        tuple: 기본 트랜치 설정 (ma250/ma200/ma150)
    """
    return tuple(
        SplitTrancheConfig(
            tranche_id=tranche_id,
            weight=weight,
            ma_window=ma_window,
        )
        for tranche_id, weight, ma_window in zip(
            SPLIT_TRANCHE_IDS,
            SPLIT_TRANCHE_WEIGHTS,
            SPLIT_TRANCHE_MA_WINDOWS,
            strict=True,
        )
    )


_DEFAULT_TRANCHES = _build_default_tranches()


# ============================================================================
# base_config 참조용 BufferZoneConfig
# ============================================================================

_TQQQ_BASE_CONFIG = BufferZoneConfig(
    strategy_name="buffer_zone_tqqq",
    display_name="버퍼존 전략 (TQQQ)",
    signal_data_path=QQQ_DATA_PATH,
    trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
    result_dir=BUFFER_ZONE_TQQQ_RESULTS_DIR,
)

_QQQ_BASE_CONFIG = BufferZoneConfig(
    strategy_name="buffer_zone_qqq",
    display_name="버퍼존 전략 (QQQ)",
    signal_data_path=QQQ_DATA_PATH,
    trade_data_path=QQQ_DATA_PATH,
    result_dir=BUFFER_ZONE_QQQ_RESULTS_DIR,
)


# ============================================================================
# SPLIT_CONFIGS 리스트
# ============================================================================

SPLIT_CONFIGS: list[SplitStrategyConfig] = [
    SplitStrategyConfig(
        strategy_name="split_buffer_zone_tqqq",
        display_name="분할 버퍼존 (TQQQ)",
        base_config=_TQQQ_BASE_CONFIG,
        total_capital=10_000_000.0,
        tranches=_DEFAULT_TRANCHES,
        result_dir=SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR,
    ),
    SplitStrategyConfig(
        strategy_name="split_buffer_zone_qqq",
        display_name="분할 버퍼존 (QQQ)",
        base_config=_QQQ_BASE_CONFIG,
        total_capital=10_000_000.0,
        tranches=_DEFAULT_TRANCHES,
        result_dir=SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR,
    ),
]


# ============================================================================
# 헬퍼 함수
# ============================================================================


def _combine_equity(
    tranche_results: list[SplitTrancheResult],
) -> pd.DataFrame:
    """트랜치별 에쿼티를 합산하여 시각화용 DataFrame을 생성한다.

    날짜 기준 outer merge로 트랜치별 에쿼티를 합산하고,
    active_tranches(보유 트랜치 수), avg_entry_price(가중 평균 진입가)를 계산한다.

    Args:
        tranche_results: 트랜치별 백테스트 결과 리스트

    Returns:
        pd.DataFrame: 합산 에쿼티 DataFrame
            Date, equity, active_tranches, avg_entry_price,
            {tranche_id}_equity, {tranche_id}_position
    """
    # 1. 날짜 기준 merge를 위한 기본 DataFrame
    combined: pd.DataFrame | None = None

    for tr in tranche_results:
        tid = tr.tranche_id
        eq = tr.equity_df[[COL_DATE, "equity", "position"]].copy()
        eq = eq.rename(
            columns={
                "equity": f"{tid}_equity",
                "position": f"{tid}_position",
            }
        )

        if combined is None:
            combined = eq
        else:
            combined = pd.merge(combined, eq, on=COL_DATE, how="outer")

    assert combined is not None, "트랜치 결과가 비어있음"

    # 2. 날짜순 정렬 및 NaN 처리
    combined = combined.sort_values(COL_DATE).reset_index(drop=True)

    # 3. 트랜치별 equity/position NaN 채우기
    equity_cols = []
    position_cols = []
    for tr in tranche_results:
        tid = tr.tranche_id
        eq_col = f"{tid}_equity"
        pos_col = f"{tid}_position"
        equity_cols.append(eq_col)
        position_cols.append(pos_col)

        # NaN인 날짜는 해당 트랜치가 아직 시작 안 된 날
        # 초기 자본을 forward fill (equity)
        # position은 0으로 채움
        combined[eq_col] = combined[eq_col].ffill()
        # 첫 행도 NaN일 수 있음 → 트랜치 초기 자본으로 채움
        combined[eq_col] = combined[eq_col].fillna(tr.config.weight * 0)
        combined[pos_col] = combined[pos_col].fillna(0).astype(int)

    # 4. 합산 equity
    combined["equity"] = combined[equity_cols].sum(axis=1)

    # 5. active_tranches 계산
    combined["active_tranches"] = combined[position_cols].gt(0).sum(axis=1).astype(int)

    # 6. avg_entry_price 계산
    # 각 트랜치의 현재 entry_price를 trades_df에서 추출
    avg_prices: list[float | None] = []
    for i in range(len(combined)):
        row = combined.iloc[i]
        current_date = row[COL_DATE]
        weighted_sum = 0.0
        total_shares = 0

        for tr in tranche_results:
            tid = tr.tranche_id
            pos_col = f"{tid}_position"
            position = int(row[pos_col])

            if position > 0:
                # trades_df에서 가장 최근 매수 기록의 entry_price 추출
                entry_price = _get_latest_entry_price(tr.trades_df, tr.equity_df, current_date)
                if entry_price is not None:
                    weighted_sum += entry_price * position
                    total_shares += position

        if total_shares > 0:
            avg_prices.append(weighted_sum / total_shares)
        else:
            avg_prices.append(None)

    combined["avg_entry_price"] = avg_prices

    # 7. 컬럼 순서 정리
    base_cols = [COL_DATE, "equity", "active_tranches", "avg_entry_price"]
    extra_cols = []
    for tr in tranche_results:
        extra_cols.append(f"{tr.tranche_id}_equity")
        extra_cols.append(f"{tr.tranche_id}_position")
    combined = combined[base_cols + extra_cols]

    return combined


def _get_latest_entry_price(
    trades_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    current_date: object,
) -> float | None:
    """트랜치의 현재 보유 포지션에 대한 entry_price를 반환한다.

    trades_df에서 entry_date <= current_date인 매수 기록 중
    아직 청산되지 않은(exit_date > current_date이거나 미청산) 기록의 entry_price를 반환한다.
    trades_df가 비어있으면 summary의 open_position에서 추출한다.

    Args:
        trades_df: 해당 트랜치의 거래 기록
        equity_df: 해당 트랜치의 에쿼티 기록
        current_date: 현재 날짜

    Returns:
        float | None: 현재 보유 포지션의 진입가 (없으면 None)
    """
    if trades_df.empty:
        return None

    # 1. 아직 청산되지 않은 거래: entry_date <= current_date < exit_date는 해당 없음
    #    (exit_date가 있는 거래는 청산 완료)
    # 2. 마지막 거래 기준: 가장 최근에 entry_date <= current_date인 거래
    #    → 이 거래의 exit_date > current_date이면 아직 보유 중
    eligible = trades_df[trades_df["entry_date"] <= current_date]
    if eligible.empty:
        return None

    last_trade = eligible.iloc[-1]

    # exit_date가 current_date 이후이면 아직 보유 중 → entry_price 반환
    if last_trade["exit_date"] > current_date:
        return float(last_trade["entry_price"])

    # 모든 거래가 청산 완료 → 미청산 포지션(summary.open_position) 케이스
    # equity_df의 마지막 행에서 position > 0이면 미청산 포지션
    # 이 경우 trades_df에는 해당 거래가 없으므로 별도 처리 필요
    return None


def _combine_trades(
    tranche_results: list[SplitTrancheResult],
) -> pd.DataFrame:
    """트랜치별 거래를 합산하여 태깅된 DataFrame을 생성한다.

    기존 TradeRecord 컬럼 + tranche_id, tranche_seq, ma_window 컬럼을 추가한다.
    entry_date 오름차순 → tranche_id 오름차순으로 정렬한다.

    Args:
        tranche_results: 트랜치별 백테스트 결과 리스트

    Returns:
        pd.DataFrame: 전체 거래 DataFrame (빈 DataFrame 가능)
    """
    all_trades: list[pd.DataFrame] = []

    for tr in tranche_results:
        if tr.trades_df.empty:
            continue

        trades_copy = tr.trades_df.copy()
        trades_copy["tranche_id"] = tr.tranche_id
        trades_copy["tranche_seq"] = range(1, len(trades_copy) + 1)
        trades_copy["ma_window"] = tr.config.ma_window
        all_trades.append(trades_copy)

    if not all_trades:
        return pd.DataFrame()

    combined = pd.concat(all_trades, ignore_index=True)
    combined = combined.sort_values(["entry_date", "tranche_id"]).reset_index(drop=True)

    return combined


def _calculate_combined_summary(
    combined_equity_df: pd.DataFrame,
    combined_trades_df: pd.DataFrame,
    total_capital: float,
    tranche_results: list[SplitTrancheResult],
) -> SummaryDict:
    """합산 에쿼티로부터 분할 레벨 요약 지표를 계산한다.

    calculate_summary()를 재사용하고, 미청산 포지션 수를 별도 계산한다.

    Args:
        combined_equity_df: 합산 에쿼티 DataFrame
        combined_trades_df: 합산 거래 DataFrame
        total_capital: 총 자본금
        tranche_results: 트랜치별 결과 (미청산 포지션 확인용)

    Returns:
        SummaryDict: 분할 레벨 성과 지표
    """
    # 1. calculate_summary()용 equity_df 준비 (Date, equity 컬럼만 필요)
    equity_for_summary = combined_equity_df[[COL_DATE, "equity"]].copy()

    # 2. calculate_summary() 호출
    summary = calculate_summary(combined_trades_df, equity_for_summary, total_capital)

    return summary


def _build_params_json(
    config: SplitStrategyConfig,
) -> dict[str, Any]:
    """JSON 저장용 파라미터 딕셔너리를 생성한다.

    Args:
        config: 분할 매수매도 전략 설정

    Returns:
        dict: JSON 저장용 파라미터
    """
    tranches_info: list[dict[str, Any]] = []
    for tranche in config.tranches:
        info: dict[str, Any] = {
            "tranche_id": tranche.tranche_id,
            "ma_window": tranche.ma_window,
            "weight": tranche.weight,
            "initial_capital": round(config.total_capital * tranche.weight),
        }
        tranches_info.append(info)

    return {
        "total_capital": round(config.total_capital),
        "buy_buffer_zone_pct": config.base_config.buy_buffer_zone_pct,
        "sell_buffer_zone_pct": config.base_config.sell_buffer_zone_pct,
        "hold_days": config.base_config.hold_days,
        "ma_type": config.base_config.ma_type,
        "tranches": tranches_info,
    }


# ============================================================================
# 핵심 함수
# ============================================================================


def run_split_backtest(config: SplitStrategyConfig) -> SplitStrategyResult:
    """분할 매수매도 백테스트를 실행한다.

    처리 흐름:
    1. 입력 검증 (가중치 합, 트랜치 설정)
    2. 데이터 로딩 (1회만) — base_config의 경로 사용
    3. 모든 트랜치 MA 사전 계산 (signal_df에 add_single_moving_average N회)
    4. 트랜치별 독립 실행
    5. 결과 조합 → SplitStrategyResult 반환

    Args:
        config: 분할 매수매도 전략 설정

    Returns:
        SplitStrategyResult: 분할 매수매도 결과

    Raises:
        ValueError: 가중치 합이 1.0이 아니거나 트랜치 설정이 유효하지 않은 경우
    """
    # 1. 입력 검증
    weight_sum = sum(t.weight for t in config.tranches)
    if abs(weight_sum - 1.0) > 0.01:
        raise ValueError(f"트랜치 가중치 합이 1.0이 아닙니다: {weight_sum}")

    tranche_ids = [t.tranche_id for t in config.tranches]
    if len(tranche_ids) != len(set(tranche_ids)):
        raise ValueError(f"중복된 트랜치 ID가 존재합니다: {tranche_ids}")

    logger.debug(f"분할 매수매도 실행 시작: {config.strategy_name}, " f"트랜치={[t.tranche_id for t in config.tranches]}")

    # 2. 데이터 로딩 (1회만)
    bc = config.base_config
    if bc.signal_data_path == bc.trade_data_path:
        trade_df = load_stock_data(bc.trade_data_path)
        signal_df = trade_df.copy()
    else:
        signal_df = load_stock_data(bc.signal_data_path)
        trade_df = load_stock_data(bc.trade_data_path)
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    logger.debug(f"데이터 로딩 완료: {len(signal_df)}행")

    # 3. 모든 트랜치 MA 사전 계산
    for tranche in config.tranches:
        ma_col = f"ma_{tranche.ma_window}"
        if ma_col not in signal_df.columns:
            signal_df = add_single_moving_average(signal_df, tranche.ma_window, ma_type=bc.ma_type)

    # 4. 트랜치별 독립 실행
    tranche_results: list[SplitTrancheResult] = []

    for tranche in config.tranches:
        capital = config.total_capital * tranche.weight
        params = BufferStrategyParams(
            initial_capital=capital,
            ma_window=tranche.ma_window,
            buy_buffer_zone_pct=bc.buy_buffer_zone_pct,
            sell_buffer_zone_pct=bc.sell_buffer_zone_pct,
            hold_days=bc.hold_days,
        )

        trades_df_t, equity_df_t, summary_t = run_buffer_strategy(
            signal_df,
            trade_df,
            params,
            strategy_name=f"{config.strategy_name}_{tranche.tranche_id}",
        )

        tranche_result = SplitTrancheResult(
            tranche_id=tranche.tranche_id,
            config=tranche,
            trades_df=trades_df_t,
            equity_df=equity_df_t,
            summary=summary_t,
        )
        tranche_results.append(tranche_result)

        logger.debug(
            f"트랜치 {tranche.tranche_id} 완료: "
            f"거래={summary_t['total_trades']}, "
            f"수익률={summary_t['total_return_pct']:.2f}%"
        )

    # 5. 결과 조합
    combined_equity_df = _combine_equity(tranche_results)
    combined_trades_df = _combine_trades(tranche_results)
    combined_summary = _calculate_combined_summary(
        combined_equity_df,
        combined_trades_df,
        config.total_capital,
        tranche_results,
    )
    params_json = _build_params_json(config)

    logger.debug(f"분할 매수매도 완료: {config.strategy_name}, " f"합산 수익률={combined_summary['total_return_pct']:.2f}%")

    return SplitStrategyResult(
        strategy_name=config.strategy_name,
        display_name=config.display_name,
        combined_equity_df=combined_equity_df,
        combined_trades_df=combined_trades_df,
        combined_summary=combined_summary,
        per_tranche=tranche_results,
        config=config,
        params_json=params_json,
        signal_df=signal_df,
    )


# ============================================================================
# 팩토리 함수
# ============================================================================


def create_split_runner(
    config: SplitStrategyConfig,
) -> Callable[[], SplitStrategyResult]:
    """SplitStrategyConfig에 대한 실행 함수를 생성한다.

    Args:
        config: 분할 매수매도 전략 설정

    Returns:
        Callable: 인자 없이 호출 가능한 실행 함수
    """

    def run() -> SplitStrategyResult:
        return run_split_backtest(config)

    return run
