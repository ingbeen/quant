"""CSCV/PBO/DSR 과최적화 통계 검증 모듈

CSCV(Combinatorial Symmetric Cross-Validation) 기반 PBO와 DSR을 계산하여
파라미터 탐색 과정의 과최적화 위험을 통계적으로 검증한다.

핵심 기능:
- CSCV 분할 생성: C(S, S/2) 대칭 IS/OOS 조합 생성
- PBO (Probability of Backtest Overfitting): IS 최적 전략의 OOS 열위 확률
- DSR (Deflated Sharpe Ratio): 다중검정 보정 Sharpe 유의성 판정

참고 문헌:
- Bailey et al. (2017). "The Probability of Backtest Overfitting"
- Bailey & Lopez de Prado (2014). "The Deflated Sharpe Ratio"
"""

import math
import os
from itertools import combinations

import numpy as np
import pandas as pd

from qbt.backtest.constants import DEFAULT_CSCV_METRIC, DEFAULT_CSCV_N_BLOCKS
from qbt.backtest.types import CscvAnalysisResultDict, DsrResultDict, PboResultDict
from qbt.common_constants import ANNUAL_DAYS, EPSILON
from qbt.utils import get_logger
from qbt.utils.parallel_executor import WORKER_CACHE, execute_parallel, init_worker_cache

logger = get_logger(__name__)

# Sharpe Ratio 연간화에 사용하는 거래일 수
# ANNUAL_DAYS(365.25)는 CAGR용 달력일이므로, Sharpe에는 거래일(252) 사용
_TRADING_DAYS_PER_YEAR = 252


# ============================================================
# 수학 유틸리티 (scipy 대체)
# ============================================================


def _norm_cdf(x: float) -> float:
    """표준 정규 분포 누적분포함수.

    math.erf 기반으로 정확한 CDF를 계산한다.

    Args:
        x: 표준 정규 분포의 값

    Returns:
        P(Z <= x) 확률값 (0~1)
    """
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """표준 정규 분포 분위수 함수 (Inverse CDF).

    Acklam의 rational approximation을 사용한다.
    정밀도: 약 1e-9.

    Args:
        p: 확률값 (0 < p < 1)

    Returns:
        Phi^-1(p) 값

    Raises:
        ValueError: p가 0 이하 또는 1 이상인 경우
    """
    if p <= 0.0 or p >= 1.0:
        raise ValueError(f"p는 0과 1 사이여야 합니다 (exclusive): {p}")

    # Acklam's rational approximation 계수
    a1 = -3.969683028665376e01
    a2 = 2.209460984245205e02
    a3 = -2.759285104469687e02
    a4 = 1.383577518672690e02
    a5 = -3.066479806614716e01
    a6 = 2.506628277459239e00

    b1 = -5.447609879822406e01
    b2 = 1.615858368580409e02
    b3 = -1.556989798598866e02
    b4 = 6.680131188771972e01
    b5 = -1.328068155288572e01

    c1 = -7.784894002430293e-03
    c2 = -3.223964580411365e-01
    c3 = -2.400758277161838e00
    c4 = -2.549732539343734e00
    c5 = 4.374664141464968e00
    c6 = 2.938163982698783e00

    d1 = 7.784695709041462e-03
    d2 = 3.224671290700398e-01
    d3 = 2.445134137142996e00
    d4 = 3.754408661907416e00

    p_low = 0.02425
    p_high = 1.0 - p_low

    if p < p_low:
        # 하위 꼬리
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / (
            (((d1 * q + d2) * q + d3) * q + d4) * q + 1.0
        )
    elif p <= p_high:
        # 중심 영역
        q = p - 0.5
        r = q * q
        return (
            (((((a1 * r + a2) * r + a3) * r + a4) * r + a5) * r + a6)
            * q
            / (((((b1 * r + b2) * r + b3) * r + b4) * r + b5) * r + 1.0)
        )
    else:
        # 상위 꼬리
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c1 * q + c2) * q + c3) * q + c4) * q + c5) * q + c6) / (
            (((d1 * q + d2) * q + d3) * q + d4) * q + 1.0
        )


def _logit(p: float) -> float:
    """로짓 함수: log(p / (1 - p)).

    Args:
        p: 확률값 (0 < p < 1)

    Returns:
        logit(p)

    Raises:
        ValueError: p가 0 이하 또는 1 이상인 경우
    """
    if p <= 0.0 or p >= 1.0:
        raise ValueError(f"p는 0과 1 사이여야 합니다 (exclusive): {p}")
    return math.log(p / (1.0 - p))


# ============================================================
# 성과 지표 (블록 단위)
# ============================================================


def _compute_annualized_sharpe(daily_returns: np.ndarray) -> float:
    """일별 수익률 배열에서 연간화 Sharpe Ratio를 계산한다.

    SR = mean(r) / std(r) × sqrt(252)
    std=0이면 0.0 반환 (0으로 나누기 방지).

    Args:
        daily_returns: 일별 수익률 1D 배열

    Returns:
        연간화 Sharpe Ratio
    """
    if len(daily_returns) == 0:
        return 0.0

    std = float(np.std(daily_returns, ddof=0))
    if std < EPSILON:
        return 0.0

    mean = float(np.mean(daily_returns))
    return (mean / std) * math.sqrt(_TRADING_DAYS_PER_YEAR)


def _compute_calmar_from_returns(daily_returns: np.ndarray) -> float:
    """일별 수익률 배열에서 Calmar Ratio를 계산한다.

    equity curve를 복원하여 CAGR과 MDD를 계산한다.
    Calmar = CAGR / |MDD|.
    MDD=0이고 CAGR>0이면 1e10 반환.

    Args:
        daily_returns: 일별 수익률 1D 배열

    Returns:
        Calmar Ratio
    """
    if len(daily_returns) == 0:
        return 0.0

    # equity curve 복원 (초기값 1.0)
    equity = np.cumprod(1.0 + daily_returns)

    # CAGR 계산
    total_return = float(equity[-1])
    years = len(daily_returns) / ANNUAL_DAYS
    if years < EPSILON or total_return <= 0:
        return 0.0
    cagr = (total_return ** (1.0 / years) - 1.0) * 100.0  # 백분율

    # MDD 계산
    peak = np.maximum.accumulate(equity)
    safe_peak = np.where(peak < EPSILON, EPSILON, peak)
    drawdown = (equity - peak) / safe_peak
    mdd = float(np.min(drawdown)) * 100.0  # 백분율

    abs_mdd = abs(mdd)
    if abs_mdd < EPSILON:
        if cagr > 0:
            return 1e10
        return 0.0

    return cagr / abs_mdd


# ============================================================
# CSCV 분할 생성
# ============================================================


def generate_cscv_splits(
    n_blocks: int,
) -> list[tuple[list[int], list[int]]]:
    """C(n_blocks, n_blocks//2) IS/OOS 대칭 분할 조합을 생성한다.

    Args:
        n_blocks: 블록 수 (짝수, 2 이상)

    Returns:
        (is_block_indices, oos_block_indices) 튜플 리스트.
        각 IS가 n_blocks//2개 블록, OOS가 나머지.

    Raises:
        ValueError: n_blocks가 짝수가 아니거나 2 미만인 경우
    """
    if n_blocks < 2:
        raise ValueError(f"n_blocks는 2 이상이어야 합니다: {n_blocks}")
    if n_blocks % 2 != 0:
        raise ValueError(f"n_blocks는 짝수여야 합니다: {n_blocks}")

    half = n_blocks // 2
    all_indices = list(range(n_blocks))

    splits: list[tuple[list[int], list[int]]] = []
    for is_indices in combinations(all_indices, half):
        is_list = list(is_indices)
        oos_list = [i for i in all_indices if i not in is_indices]
        splits.append((is_list, oos_list))

    return splits


# ============================================================
# PBO 계산
# ============================================================


def calculate_pbo(
    returns_matrix: np.ndarray,
    n_blocks: int = DEFAULT_CSCV_N_BLOCKS,
    metric: str = "sharpe",
) -> PboResultDict:
    """CSCV 기반 PBO (Probability of Backtest Overfitting)를 계산한다.

    알고리즘 (Bailey et al. 2017):
    1. returns_matrix를 n_blocks개 블록으로 시간순 분할
    2. C(n_blocks, n_blocks//2) 조합 각각에서:
       a. IS 블록 연결 → 각 전략의 metric 계산 → IS 최적(n*) 선택
       b. OOS 블록 연결 → n*의 OOS metric 상대 랭크 계산
       c. lambda = logit(rank)
    3. PBO = (rank <= 0.5인 비율)

    Args:
        returns_matrix: (T, N) 일별 수익률 행렬.
            T = 거래일 수, N = 파라미터 조합 수.
        n_blocks: 블록 수 (짝수)
        metric: "sharpe" 또는 "calmar"

    Returns:
        PboResultDict

    Raises:
        ValueError: 유효하지 않은 n_blocks 또는 metric인 경우
    """
    if metric not in ("sharpe", "calmar"):
        raise ValueError(f"metric은 'sharpe' 또는 'calmar'이어야 합니다: {metric}")

    t_rows, n_strategies = returns_matrix.shape

    # 성과 지표 함수 선택
    if metric == "sharpe":
        metric_func = _compute_annualized_sharpe
    else:
        metric_func = _compute_calmar_from_returns

    # 1. 블록 분할 (시간순, 동일 크기)
    block_size = t_rows // n_blocks
    blocks: list[np.ndarray] = []
    for i in range(n_blocks):
        start = i * block_size
        # 마지막 블록은 나머지를 포함
        end = (i + 1) * block_size if i < n_blocks - 1 else t_rows
        blocks.append(returns_matrix[start:end, :])

    # 2. CSCV 분할 생성
    splits = generate_cscv_splits(n_blocks)

    # 3. 각 분할에서 PBO 계산
    logit_lambdas: list[float] = []
    overfit_count = 0  # IS 최적이 OOS에서 중간 이하인 횟수

    for is_indices, oos_indices in splits:
        # IS/OOS 블록 연결
        is_returns = np.vstack([blocks[i] for i in is_indices])
        oos_returns = np.vstack([blocks[i] for i in oos_indices])

        # IS: 각 전략의 성과 지표 계산
        is_metrics = np.array([metric_func(is_returns[:, j]) for j in range(n_strategies)])

        # IS 최적 전략 인덱스
        best_is_idx = int(np.argmax(is_metrics))

        # OOS: 모든 전략의 성과 지표 계산
        oos_metrics = np.array([metric_func(oos_returns[:, j]) for j in range(n_strategies)])

        # OOS에서 IS 최적 전략의 상대 랭크 계산
        # rank = (IS 최적보다 OOS 성과가 나은 전략 수) / N
        # rank=0 → IS 최적이 OOS에서도 1위 (좋음)
        # rank>0.5 → IS 최적이 OOS에서 중간 이하 (과최적화)
        best_oos_metric = oos_metrics[best_is_idx]
        n_better = int(np.sum(oos_metrics > best_oos_metric))
        rank = n_better / n_strategies

        # PBO 기여: IS 최적이 OOS에서 중간 이하면 과최적화 신호
        if rank > 0.5:
            overfit_count += 1

        # logit 계산 (경계값 클리핑)
        clipped_rank = max(EPSILON, min(1.0 - EPSILON, rank))
        logit_lambdas.append(_logit(clipped_rank))

    # 4. PBO = IS 최적이 OOS에서 중간 이하인 비율
    n_splits = len(splits)
    pbo = overfit_count / n_splits if n_splits > 0 else 0.0

    logger.debug(
        f"PBO 계산 완료: PBO={pbo:.4f}, metric={metric}, "
        f"n_blocks={n_blocks}, n_splits={n_splits}, "
        f"overfit_count={overfit_count}"
    )

    return {
        "pbo": pbo,
        "n_splits": n_splits,
        "n_blocks": n_blocks,
        "logit_lambdas": logit_lambdas,
        "rank_below_median": overfit_count,
        "metric": metric,
    }


# ============================================================
# DSR 계산
# ============================================================


def calculate_dsr(
    daily_returns: np.ndarray,
    n_trials: int,
) -> DsrResultDict:
    """Deflated Sharpe Ratio를 계산한다.

    Bailey & Lopez de Prado (2014) 방법론.
    다중검정 보정 + 왜도/첨도를 반영하여 Sharpe의 통계적 유의성을 판정한다.

    수식:
        Z = (SR_observed - E[SR_max]) / sigma_SR
        sigma_SR^2 = (1 - skew*SR + (kurt-1)/4 * SR^2) / T
        E[SR_max] ≈ sqrt(V_SR) * [gamma * Phi^-1(1-1/N) + (1-gamma) * Phi^-1(1-e^-1/N)]
        DSR = Phi(Z)

    Args:
        daily_returns: IS 최적 전략의 일별 수익률 배열
        n_trials: 시행 수 (파라미터 조합 수 N)

    Returns:
        DsrResultDict
    """
    t = len(daily_returns)

    # 빈 배열 또는 표준편차=0 방어
    if t < 2:
        return {
            "dsr": 0.0,
            "sr_observed": 0.0,
            "sr_benchmark": 0.0,
            "z_score": 0.0,
            "n_trials": n_trials,
            "t_observations": t,
        }

    std = float(np.std(daily_returns, ddof=0))
    if std < EPSILON:
        return {
            "dsr": 0.0,
            "sr_observed": 0.0,
            "sr_benchmark": 0.0,
            "z_score": 0.0,
            "n_trials": n_trials,
            "t_observations": t,
        }

    # 1. 관측 Sharpe Ratio (연간화하지 않은 원시 SR)
    # DSR 공식에서 SR은 일별 기준으로 사용
    mean = float(np.mean(daily_returns))
    sr_daily = mean / std

    # 연간화 SR (보고용)
    sr_annualized = sr_daily * math.sqrt(ANNUAL_DAYS)

    # 2. 왜도, 첨도 (Fisher 기준)
    skewness = float(np.mean(((daily_returns - mean) / std) ** 3))
    kurtosis = float(np.mean(((daily_returns - mean) / std) ** 4))

    # 3. Sharpe Ratio 분산
    # sigma_SR^2 = (1 - skew*SR + (kurt-1)/4 * SR^2) / T
    sr_var = (1.0 - skewness * sr_daily + (kurtosis - 1.0) / 4.0 * sr_daily**2) / t
    sr_std = math.sqrt(max(sr_var, 0.0))

    # 4. E[SR_max]: 다중 시행 보정 (null hypothesis 하에서의 기대 최대 SR)
    # E[SR_max] ≈ sqrt(V_SR) * [gamma * Phi^-1(1-1/N) + (1-gamma) * Phi^-1(1-e^-1/N)]
    euler_gamma = 0.5772156649015329  # Euler-Mascheroni 상수

    if n_trials <= 1:
        e_sr_max = 0.0
    else:
        # Phi^-1(1 - 1/N)
        p1 = 1.0 - 1.0 / n_trials
        p1 = max(EPSILON, min(1.0 - EPSILON, p1))
        z1 = _norm_ppf(p1)

        # Phi^-1(1 - e^-1 / N)
        p2 = 1.0 - math.exp(-1.0) / n_trials
        p2 = max(EPSILON, min(1.0 - EPSILON, p2))
        z2 = _norm_ppf(p2)

        e_sr_max = sr_std * (euler_gamma * z1 + (1.0 - euler_gamma) * z2)

    # 연간화 기준 E[SR_max]
    e_sr_max_annualized = e_sr_max * math.sqrt(ANNUAL_DAYS)

    # 5. Z-score 및 DSR
    if sr_std < EPSILON:
        z_score = 0.0
        dsr = 0.0
    else:
        z_score = (sr_daily - e_sr_max) / sr_std
        dsr = _norm_cdf(z_score)

    logger.debug(
        f"DSR 계산 완료: DSR={dsr:.4f}, SR_observed={sr_annualized:.4f}, "
        f"SR_benchmark={e_sr_max_annualized:.4f}, Z={z_score:.4f}, "
        f"n_trials={n_trials}, T={t}"
    )

    return {
        "dsr": dsr,
        "sr_observed": sr_annualized,
        "sr_benchmark": e_sr_max_annualized,
        "z_score": z_score,
        "n_trials": n_trials,
        "t_observations": t,
    }


# ============================================================
# 수익률 행렬 구축 (병렬 처리)
# ============================================================


def generate_param_combinations(
    ma_window_list: list[int],
    buy_buffer_zone_pct_list: list[float],
    sell_buffer_zone_pct_list: list[float],
    hold_days_list: list[int],
    recent_months_list: list[int],
    initial_capital: float,
    atr_period_list: list[int] | None = None,
    atr_multiplier_list: list[float] | None = None,
) -> list[dict[str, object]]:
    """파라미터 리스트에서 모든 조합의 BufferStrategyParams를 생성한다.

    기존 run_grid_search()의 조합 생성 로직을 분리하여 재사용한다.

    Args:
        ma_window_list: 이동평균 기간 목록
        buy_buffer_zone_pct_list: 매수 버퍼존 비율 목록
        sell_buffer_zone_pct_list: 매도 버퍼존 비율 목록
        hold_days_list: 유지조건 일수 목록
        recent_months_list: 최근 청산 기간 목록
        initial_capital: 초기 자본금
        atr_period_list: ATR 기간 목록 (None이면 ATR 미사용)
        atr_multiplier_list: ATR 배수 목록 (None이면 ATR 미사용)

    Returns:
        {"params": BufferStrategyParams} 딕셔너리 리스트
    """
    from qbt.backtest.strategies.buffer_zone_helpers import BufferStrategyParams

    atr_combos: list[tuple[int | None, float | None]]
    if atr_period_list is not None and atr_multiplier_list is not None:
        atr_combos = [(p, m) for p in atr_period_list for m in atr_multiplier_list]
    else:
        atr_combos = [(None, None)]

    param_combinations: list[dict[str, object]] = []
    for ma_window in ma_window_list:
        for buy_buffer_zone_pct in buy_buffer_zone_pct_list:
            for sell_buffer_zone_pct in sell_buffer_zone_pct_list:
                for hold_days in hold_days_list:
                    for recent_months in recent_months_list:
                        for atr_period, atr_multiplier in atr_combos:
                            param_combinations.append(
                                {
                                    "params": BufferStrategyParams(
                                        ma_window=ma_window,
                                        buy_buffer_zone_pct=buy_buffer_zone_pct,
                                        sell_buffer_zone_pct=sell_buffer_zone_pct,
                                        hold_days=hold_days,
                                        recent_months=recent_months,
                                        initial_capital=initial_capital,
                                        atr_period=atr_period,
                                        atr_multiplier=atr_multiplier,
                                    ),
                                }
                            )

    return param_combinations


def _run_strategy_for_cscv(
    params_dict: dict[str, object],
) -> np.ndarray:
    """단일 파라미터 조합에 대해 전략을 실행하고 일별 수익률을 반환한다.

    WORKER_CACHE에서 signal_df, trade_df를 조회하여 전략을 실행한다.
    equity curve에서 일별 수익률을 계산한다.

    Args:
        params_dict: {"params": BufferStrategyParams} 딕셔너리

    Returns:
        일별 수익률 1D ndarray
    """
    from qbt.backtest.strategies.buffer_zone_helpers import (
        BufferStrategyParams,
        run_buffer_strategy,
    )

    signal_df: pd.DataFrame = WORKER_CACHE["signal_df"]
    trade_df: pd.DataFrame = WORKER_CACHE["trade_df"]
    params: BufferStrategyParams = params_dict["params"]  # type: ignore[assignment]

    # 전략 실행 (로그 출력 비활성화)
    _, equity_df, _ = run_buffer_strategy(signal_df, trade_df, params, log_trades=False)

    # equity curve에서 일별 수익률 계산
    equity_series: np.ndarray = np.asarray(equity_df["equity"].values, dtype=np.float64)
    if len(equity_series) < 2:
        return np.array([], dtype=np.float64)

    # daily_return = (equity[t] - equity[t-1]) / equity[t-1]
    daily_returns: np.ndarray = np.diff(equity_series) / equity_series[:-1]
    return daily_returns


def build_returns_matrix(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    param_combinations: list[dict[str, object]],
) -> np.ndarray:
    """병렬 실행으로 수익률 행렬 (T, N)을 구축한다.

    Args:
        signal_df: 시그널용 DataFrame (MA 사전 계산 완료)
        trade_df: 매매용 DataFrame
        param_combinations: generate_param_combinations() 결과

    Returns:
        (T, N) 일별 수익률 행렬. T = 거래일 수, N = 파라미터 조합 수.

    Raises:
        ValueError: param_combinations가 비어있거나 수익률 길이가 불일치하는 경우
    """
    if not param_combinations:
        raise ValueError("param_combinations가 비어있습니다")

    n_strategies = len(param_combinations)
    logger.debug(f"수익률 행렬 구축 시작: {n_strategies}개 조합 병렬 실행")

    # 병렬 실행 (signal_df, trade_df를 워커 캐시에 저장)
    raw_count = os.cpu_count()
    cpu_count = raw_count - 1 if raw_count is not None else None

    results: list[np.ndarray] = execute_parallel(
        func=_run_strategy_for_cscv,
        inputs=param_combinations,
        max_workers=cpu_count,
        initializer=init_worker_cache,
        initargs=({"signal_df": signal_df, "trade_df": trade_df},),
    )

    # 모든 결과의 길이 확인 (동일해야 함)
    lengths = [len(r) for r in results]
    if len(set(lengths)) != 1:
        raise ValueError(f"수익률 배열 길이 불일치: min={min(lengths)}, max={max(lengths)}")

    t_rows = lengths[0]
    logger.debug(f"수익률 행렬 구축 완료: ({t_rows}, {n_strategies})")

    # (T, N) 행렬 합성
    returns_matrix = np.column_stack(results)
    return returns_matrix


# ============================================================
# 통합 분석 오케스트레이션
# ============================================================


def run_cscv_analysis(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    param_combinations: list[dict[str, object]],
    strategy_name: str,
    n_blocks: int = DEFAULT_CSCV_N_BLOCKS,
    metric: str = DEFAULT_CSCV_METRIC,
) -> CscvAnalysisResultDict:
    """CSCV 분석 전체 파이프라인을 실행한다.

    1. 수익률 행렬 구축 (병렬)
    2. PBO (Sharpe 기반) 계산
    3. DSR 계산
    4. 결과 통합

    Args:
        signal_df: 시그널용 DataFrame (MA 사전 계산 완료)
        trade_df: 매매용 DataFrame
        param_combinations: generate_param_combinations() 결과
        strategy_name: 전략명
        n_blocks: CSCV 블록 수
        metric: PBO 성과 지표 ("sharpe" 또는 "calmar")

    Returns:
        CscvAnalysisResultDict
    """
    n_strategies = len(param_combinations)
    logger.debug(
        f"CSCV 분석 시작: strategy={strategy_name}, " f"n_combinations={n_strategies}, n_blocks={n_blocks}, metric={metric}"
    )

    # 1. 수익률 행렬 구축
    returns_matrix = build_returns_matrix(signal_df, trade_df, param_combinations)
    t_rows = returns_matrix.shape[0]

    # 2. PBO (Sharpe 기반) 계산
    pbo_sharpe = calculate_pbo(returns_matrix, n_blocks=n_blocks, metric="sharpe")

    # 3. PBO (Calmar 기반) - metric이 calmar이면 추가 계산
    pbo_calmar: PboResultDict | None = None
    if metric == "calmar":
        pbo_calmar = calculate_pbo(returns_matrix, n_blocks=n_blocks, metric="calmar")

    # 4. DSR 계산: 전체기간 Sharpe 최적 전략의 일별 수익률 사용
    all_sharpes = np.array([_compute_annualized_sharpe(returns_matrix[:, j]) for j in range(n_strategies)])
    best_is_idx = int(np.argmax(all_sharpes))
    best_is_sharpe = float(all_sharpes[best_is_idx])
    best_daily_returns = returns_matrix[:, best_is_idx]

    dsr_result = calculate_dsr(best_daily_returns, n_trials=n_strategies)

    logger.debug(
        f"CSCV 분석 완료: PBO(sharpe)={pbo_sharpe['pbo']:.4f}, "
        f"DSR={dsr_result['dsr']:.4f}, best_SR={best_is_sharpe:.4f}"
    )

    result: CscvAnalysisResultDict = {
        "strategy": strategy_name,
        "n_param_combinations": n_strategies,
        "t_observations": t_rows,
        "pbo_sharpe": pbo_sharpe,
        "dsr": dsr_result,
        "best_is_sharpe": round(best_is_sharpe, 4),
    }

    if pbo_calmar is not None:
        result["pbo_calmar"] = pbo_calmar

    return result
