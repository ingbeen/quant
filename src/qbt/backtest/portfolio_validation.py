"""포트폴리오 백테스트 결과 정합성 검증

PortfolioResult의 state_log_df, equity_df를 기반으로
5개 정합성 규칙을 검증한다. 위반 사항을 문자열 리스트로 반환한다.

규칙 1: 시그널-체결 1일 lag
규칙 2: 리밸런싱 후 비중 정합성
규칙 3: EXIT_ALL 후 주수 0
규칙 4: 현금 비음수
규칙 5: 에쿼티 등식 (equity = cash + sum(shares * close))
"""

import pandas as pd

from qbt.backtest.engines.portfolio_rebalance import DEFAULT_REBALANCE_POLICY
from qbt.backtest.portfolio_types import PortfolioResult

# 리밸런싱 후 비중 편차 허용 임계값: 매일 긴급 트리거와 동일
# (체결은 시가, 검증은 종가 기준이므로 긴급 트리거 이하 편차는 시스템이 허용하는 범위)
_REBALANCE_WEIGHT_DEVIATION_THRESHOLD = DEFAULT_REBALANCE_POLICY.daily_threshold_rate

# 에쿼티 등식 허용 오차 (원)
_EQUITY_EQUATION_TOLERANCE = 1.0


def _get_asset_ids_from_state_log(state_log_df: pd.DataFrame) -> list[str]:
    """state_log_df에서 자산 ID 목록을 추출한다.

    {asset_id}_close 컬럼 기준으로 탐지한다.
    """
    return [c.removesuffix("_close") for c in state_log_df.columns if c.endswith("_close")]


def _check_signal_execution_lag(
    state_log_df: pd.DataFrame,
    asset_ids: list[str],
) -> list[str]:
    """규칙 1: pending intent가 다음 거래일에 정확히 체결되는지 검증한다.

    Args:
        state_log_df: 일별 상태 로그
        asset_ids: 자산 ID 목록

    Returns:
        위반 메시지 리스트 (빈 리스트 = 통과)
    """
    violations: list[str] = []
    for aid in asset_ids:
        pending_col = f"{aid}_pending_intent"
        executed_col = f"{aid}_executed_intent"
        if pending_col not in state_log_df.columns or executed_col not in state_log_df.columns:
            continue

        for i in range(len(state_log_df) - 1):
            pending = str(state_log_df.iloc[i][pending_col])
            if not pending or pending == "" or pending == "nan":
                continue
            next_executed = str(state_log_df.iloc[i + 1][executed_col])
            if pending != next_executed:
                d = state_log_df.iloc[i]["Date"]
                violations.append(f"[규칙1] {aid}: {d} pending={pending} -> 다음날 executed={next_executed}")
    return violations


def _check_rebalance_weight_consistency(
    state_log_df: pd.DataFrame,
    asset_ids: list[str],
    target_weights: dict[str, float],
) -> list[str]:
    """규칙 2: 리밸런싱 후 비중이 목표 대비 허용 범위 이내인지 검증한다.

    Args:
        state_log_df: 일별 상태 로그
        asset_ids: 자산 ID 목록
        target_weights: {asset_id: target_weight}

    Returns:
        위반 메시지 리스트
    """
    violations: list[str] = []
    if "rebalanced" not in state_log_df.columns:
        return violations

    reb_rows = state_log_df[state_log_df["rebalanced"] == True]  # noqa: E712
    for _, row in reb_rows.iterrows():
        for aid in asset_ids:
            target_w = target_weights.get(aid, 0)
            if target_w <= 0:
                continue
            shares = int(row.get(f"{aid}_shares", 0))
            if shares <= 0:
                continue
            actual_w = float(row.get(f"{aid}_weight", 0))
            deviation = abs(actual_w / target_w - 1.0)
            if deviation > _REBALANCE_WEIGHT_DEVIATION_THRESHOLD:
                violations.append(
                    f"[규칙2] {row['Date']} {aid}: actual={actual_w:.4f}, "
                    f"target={target_w:.4f}, deviation={deviation:.4f}"
                )
    return violations


def _check_exit_all_shares_zero(
    state_log_df: pd.DataFrame,
    asset_ids: list[str],
) -> list[str]:
    """규칙 3: EXIT_ALL 체결 후 해당 자산 주수가 0인지 검증한다.

    Args:
        state_log_df: 일별 상태 로그
        asset_ids: 자산 ID 목록

    Returns:
        위반 메시지 리스트
    """
    violations: list[str] = []
    for aid in asset_ids:
        executed_col = f"{aid}_executed_intent"
        shares_col = f"{aid}_shares"
        if executed_col not in state_log_df.columns:
            continue

        exit_rows = state_log_df[state_log_df[executed_col] == "EXIT_ALL"]
        for _, row in exit_rows.iterrows():
            shares = int(row.get(shares_col, -1))
            if shares != 0:
                violations.append(f"[규칙3] {row['Date']} {aid}: EXIT_ALL 후 shares={shares}")
    return violations


def _check_cash_non_negative(equity_df: pd.DataFrame) -> list[str]:
    """규칙 4: 모든 거래일에서 현금이 음수가 아닌지 검증한다.

    Args:
        equity_df: 에쿼티 DataFrame

    Returns:
        위반 메시지 리스트
    """
    negative = equity_df[equity_df["cash"] < 0]
    if negative.empty:
        return []
    return [f"[규칙4] {row['Date']}: cash={row['cash']:.0f}" for _, row in negative.iterrows()]


def _check_equity_equation(equity_df: pd.DataFrame) -> list[str]:
    """규칙 5: 에쿼티 = 현금 + 자산 평가액 합계 등식을 검증한다.

    Args:
        equity_df: 에쿼티 DataFrame

    Returns:
        위반 메시지 리스트
    """
    value_cols = [c for c in equity_df.columns if c.endswith("_value")]
    violations: list[str] = []
    for _, row in equity_df.iterrows():
        computed = float(row["cash"]) + sum(float(row[vc]) for vc in value_cols)
        recorded = float(row["equity"])
        if abs(computed - recorded) > _EQUITY_EQUATION_TOLERANCE:
            violations.append(f"[규칙5] {row['Date']}: computed={computed:.0f} != equity={recorded:.0f}")
    return violations


def validate_portfolio_result(result: PortfolioResult) -> list[str]:
    """PortfolioResult에 대해 5개 정합성 규칙을 검증한다.

    Args:
        result: 포트폴리오 백테스트 결과

    Returns:
        위반 메시지 리스트 (빈 리스트 = 전부 통과)
    """
    violations: list[str] = []

    equity_df = result.equity_df
    state_log_df = result.state_log_df

    # 규칙 4, 5: equity_df 기반 (state_log 없어도 검증 가능)
    violations.extend(_check_cash_non_negative(equity_df))
    violations.extend(_check_equity_equation(equity_df))

    # 규칙 1, 2, 3: state_log_df 기반
    if state_log_df.empty:
        return violations

    asset_ids = _get_asset_ids_from_state_log(state_log_df)
    target_weights = {slot.asset_id: slot.target_weight for slot in result.config.asset_slots}

    violations.extend(_check_signal_execution_lag(state_log_df, asset_ids))
    violations.extend(_check_rebalance_weight_consistency(state_log_df, asset_ids, target_weights))
    violations.extend(_check_exit_all_shares_zero(state_log_df, asset_ids))

    return violations
