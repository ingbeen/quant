"""포트폴리오 백테스트 결과 정합성 검증

PortfolioResult의 state_log_df, equity_df, ledger_df를 기반으로
7개 정합성 규칙을 검증한다. 위반 사항을 문자열 리스트로 반환한다.

규칙 1: 시그널-체결 1일 lag
규칙 2: 리밸런싱 후 비중 정합성 (매매법 자본 대비)
규칙 3: EXIT_ALL 후 주수 0
규칙 4: 현금 비음수 (계좌 · 매매법)
규칙 5: 에쿼티 등식 (equity = cash + sum(shares * close))
규칙 6: 장부 항등식 (Σ 매매법 자본 + 상계 절감 = 계좌 자본, Σ 매매법 손익 + 상계 절감 = 계좌 손익,
        매매법 자본 = 초기 몫 + 이전 누적 + 손익)
규칙 7: 매매법 사이 되돌리기 정합성 (장부 몫 = 매매법 자본 ÷ 매매법 자본 합, 판단일 장부로 다시 계산한 계획 이전과
        다음 거래일 실제 이전이 상한 규칙대로 맞음 · 판정이 없던 날은 이전 없음, 되돌리기 뒤 몫)
"""

from collections.abc import Mapping
from datetime import date

import pandas as pd

from qbt.backtest.engines.portfolio_rebalance import DEFAULT_REBALANCE_POLICY, is_last_trading_day_of_month
from qbt.backtest.portfolio_types import (
    ASSET_COL_SUFFIX_CLOSE,
    ASSET_COL_SUFFIX_VALUE,
    PortfolioConfig,
    PortfolioResult,
    SlotMethodConfig,
    asset_close_col,
    asset_executed_intent_col,
    asset_pending_intent_col,
    asset_shares_col,
    asset_weight_col,
    list_position_keys,
    resolve_methods,
)

# 리밸런싱 후 비중의 목표 대비 상대 편차 허용 임계값 (0.20 = 20%)
# 체결은 시가, 검증은 그날 종가 기준이라 하루치 가격 변동만큼의 편차는 정상이다.
# 리밸런싱 정책의 임계값(RebalancePolicy.threshold_rate)과는 별개의 검사 기준이며,
# tests/qbt/test_portfolio_validation.py 의 경계 테스트가 이 값을 고정한다.
_REBALANCE_WEIGHT_DEVIATION_THRESHOLD = 0.20

# 에쿼티 등식 허용 오차 (원)
_EQUITY_EQUATION_TOLERANCE = 1.0

# 그날 목표 비중으로 맞춘 체결 (규칙 2 의 매매법 단위 검사 대상)
_REBALANCE_INTENT_TYPES = ("REDUCE_TO_TARGET", "INCREASE_TO_TARGET")


def _get_asset_ids_from_state_log(state_log_df: pd.DataFrame) -> list[str]:
    """state_log_df에서 자산 ID 목록을 추출한다.

    {asset_id}_close 컬럼 기준으로 탐지한다.
    """
    return [c.removesuffix(ASSET_COL_SUFFIX_CLOSE) for c in state_log_df.columns if c.endswith(ASSET_COL_SUFFIX_CLOSE)]


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
        pending_col = asset_pending_intent_col(aid)
        executed_col = asset_executed_intent_col(aid)
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
    # asset_ids 는 state_log_df 컬럼에서 추출되었고 target_weights 는 동일 config 에서
    # 만들어졌으므로 두 키 집합은 일치한다. 따라서 .get default 는 dead branch.
    for _, row in reb_rows.iterrows():
        for aid in asset_ids:
            target_w = target_weights[aid]
            if target_w <= 0:
                continue
            shares = int(row[asset_shares_col(aid)])
            if shares <= 0:
                continue
            actual_w = float(row[asset_weight_col(aid)])
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
        executed_col = asset_executed_intent_col(aid)
        shares_col = asset_shares_col(aid)
        if executed_col not in state_log_df.columns:
            continue

        exit_rows = state_log_df[state_log_df[executed_col] == "EXIT_ALL"]
        # shares_col 은 state_log_df 가 항상 갖는 자산별 컬럼이다.
        for _, row in exit_rows.iterrows():
            shares = int(row[shares_col])
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
    value_cols = [c for c in equity_df.columns if c.endswith(ASSET_COL_SUFFIX_VALUE)]
    if not value_cols:
        raise RuntimeError(
            f"내부 불변조건 위반: equity_df에 자산 평가액 컬럼"
            f"('{ASSET_COL_SUFFIX_VALUE}' 접미사)이 하나도 없음 "
            f"(columns={list(equity_df.columns)}). "
            f"value_cols가 비면 sum=0.0으로 등식 검증이 우회되므로 즉시 중단한다."
        )
    violations: list[str] = []
    for _, row in equity_df.iterrows():
        computed = float(row["cash"]) + sum(float(row[vc]) for vc in value_cols)
        recorded = float(row["equity"])
        if abs(computed - recorded) > _EQUITY_EQUATION_TOLERANCE:
            violations.append(f"[규칙5] {row['Date']}: computed={computed:.0f} != equity={recorded:.0f}")
    return violations


def _key_targets(config: PortfolioConfig) -> tuple[dict[str, str], dict[str, float | None]]:
    """자산 키별 (매매법, 고정 목표 비중). 비중이 바뀌는 매매법의 목표는 None — state_log 의 그날 값을 쓴다."""
    infos = list_position_keys(config)
    key_methods = {info.key: info.method_id for info in infos}
    fixed_targets = {info.key: (info.slot.target_weight if info.slot is not None else None) for info in infos}
    return key_methods, fixed_targets


def _check_method_rebalance_weight_consistency(
    state_log_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    key_methods: Mapping[str, str],
    fixed_targets: Mapping[str, float | None],
) -> list[str]:
    """규칙 2 (매매법 단위): 매매법이 리밸런싱한 날, 그날 목표로 맞춘(REDUCE/INCREASE 를 처리한) 자산의
    매매법 자본 대비 비중이 목표 허용 범위 이내인지.

    배분 규칙의 조정만 있던 날에는 바뀐 자산만 매매하므로, 매매하지 않은 자산의 월중 이탈은 검사하지 않는다.

    Args:
        state_log_df: 일별 상태 로그 (자산 키별 주수 · 종가 · 비중변동 매매법의 목표 비중)
        ledger_df: 매매법 장부 (날짜 × 매매법의 자본 · 리밸런싱 여부)
        key_methods: {자산 키: method_id}
        fixed_targets: {자산 키: 고정 목표 비중 | None(비중변동 — state_log 의 {키}_target_weight)}

    Returns:
        위반 메시지 리스트
    """
    violations: list[str] = []
    state_by_date = state_log_df.set_index("Date")
    rebalanced_rows = ledger_df[ledger_df["rebalanced"] == True]  # noqa: E712
    for _, ledger_row in rebalanced_rows.iterrows():
        current_date = ledger_row["Date"]
        method_id = str(ledger_row["method_id"])
        method_equity = float(ledger_row["equity"])
        state_row = state_by_date.loc[current_date]
        for key, key_method in key_methods.items():
            if key_method != method_id:
                continue
            if state_row[asset_executed_intent_col(key)] not in _REBALANCE_INTENT_TYPES:
                continue
            fixed = fixed_targets[key]
            target_w = fixed if fixed is not None else float(state_row[f"{key}_target_weight"])
            if target_w <= 0:
                continue
            shares = int(state_row[asset_shares_col(key)])
            if shares <= 0:
                continue
            actual_w = shares * float(state_row[asset_close_col(key)]) / method_equity
            deviation = abs(actual_w / target_w - 1.0)
            if deviation > _REBALANCE_WEIGHT_DEVIATION_THRESHOLD:
                violations.append(
                    f"[규칙2] {current_date} {key}: 매매법 자본 대비 actual={actual_w:.4f}, "
                    f"target={target_w:.4f}, deviation={deviation:.4f}"
                )
    return violations


def _check_method_cash_non_negative(ledger_df: pd.DataFrame) -> list[str]:
    """규칙 4 (매매법 단위): 어느 매매법 장부의 현금도 음수가 아니어야 한다."""
    negative = ledger_df[ledger_df["cash"] < 0]
    return [f"[규칙4] {row['Date']} {row['method_id']}: cash={row['cash']:.0f}" for _, row in negative.iterrows()]


def _check_ledger_identities(
    equity_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    total_capital: float,
    initial_shares: Mapping[str, float],
) -> list[str]:
    """규칙 6: 매매법 장부와 계좌가 맞는지 매일 검증한다.

    - Σ 매매법 자본 + 상계 절감 = 계좌 자본
    - Σ 매매법 손익 + 상계 절감 = 계좌 자본 − 초기 자본
    - 매매법 자본 = 초기 몫 + 이전 누적 + 손익

    Args:
        equity_df: 계좌 에쿼티 (netting_savings 열이 없으면 상계 절감 0)
        ledger_df: 매매법 장부
        total_capital: 초기 자본
        initial_shares: {method_id: 계좌 대비 목표 몫} — 초기 몫 = 초기 자본 × 목표 몫

    Returns:
        위반 메시지 리스트
    """
    violations: list[str] = []
    grouped = ledger_df.groupby("Date", sort=False)
    equity_by_date = {d: float(v) for d, v in grouped["equity"].sum().items()}
    pnl_by_date = {d: float(v) for d, v in grouped["pnl"].sum().items()}
    for _, row in equity_df.iterrows():
        current_date: date = row["Date"]
        savings = float(row["netting_savings"]) if "netting_savings" in equity_df.columns else 0.0
        account_equity = float(row["equity"])
        methods_equity = equity_by_date[current_date]
        methods_pnl = pnl_by_date[current_date]
        if abs(methods_equity + savings - account_equity) > _EQUITY_EQUATION_TOLERANCE:
            violations.append(
                f"[규칙6] {current_date}: Σ 매매법 자본 + 상계 절감 = {methods_equity + savings:.0f} != 계좌 자본 {account_equity:.0f}"
            )
        if abs(methods_pnl + savings - (account_equity - total_capital)) > _EQUITY_EQUATION_TOLERANCE:
            violations.append(
                f"[규칙6] {current_date}: Σ 매매법 손익 + 상계 절감 = {methods_pnl + savings:.0f} "
                f"!= 계좌 손익 {account_equity - total_capital:.0f}"
            )

    for _, row in ledger_df.iterrows():
        method_id = str(row["method_id"])
        expected = total_capital * initial_shares[method_id] + float(row["transfers"]) + float(row["pnl"])
        if abs(float(row["equity"]) - expected) > _EQUITY_EQUATION_TOLERANCE:
            violations.append(
                f"[규칙6] {row['Date']} {method_id}: 매매법 자본 {float(row['equity']):.0f} "
                f"!= 초기 몫 + 이전 + 손익 {expected:.0f}"
            )
    return violations


def _check_capped_transfer(
    execution_date: date,
    planned: Mapping[str, float],
    moved: Mapping[str, float],
    cash: Mapping[str, float],
) -> list[str]:
    """체결일의 매매법 사이 이전이 계획과 상한 규칙(engines.portfolio_methods.cap_transfers)대로인지.

    내주는 쪽은 0 부터 계획액까지 낸다. 매도 뒤 현금이 계획보다 적을 때만 덜 내고, 그때는 가진 현금을 다 내므로
    그날 매수도 못 해 그날 끝 현금이 0 이다. 받는 쪽은 내준 합을 계획 비율대로 나눠 받는다.

    Args:
        execution_date: 체결일
        planned: {method_id: 계획 이전액 (+ 받음, − 내줌)}
        moved: {method_id: 그날 실제 이전액 (이전 누적의 변화)}
        cash: {method_id: 그날 끝 장부 현금}

    Returns:
        위반 메시지 리스트
    """
    violations: list[str] = []
    given = 0.0
    for method_id, plan in planned.items():
        if plan >= 0:
            continue
        amount = moved[method_id]
        if not plan - _EQUITY_EQUATION_TOLERANCE <= amount <= _EQUITY_EQUATION_TOLERANCE:
            violations.append(f"[규칙7] {execution_date} {method_id}: 내준 이전 {amount:.0f} 이 0 과 계획 {plan:.0f} 사이가 아님")
        elif amount > plan + _EQUITY_EQUATION_TOLERANCE and not cash[method_id] <= _EQUITY_EQUATION_TOLERANCE:
            violations.append(
                f"[규칙7] {execution_date} {method_id}: 계획 {plan:.0f} 보다 적게({amount:.0f}) 냈는데 "
                f"현금 {cash[method_id]:.0f} 이 남음"
            )
        given -= amount

    requested = sum(plan for plan in planned.values() if plan > 0)
    for method_id, plan in planned.items():
        if plan < 0:
            continue
        expected = given * plan / requested if plan > 0 else 0.0
        if not abs(moved[method_id] - expected) <= _EQUITY_EQUATION_TOLERANCE:
            violations.append(
                f"[규칙7] {execution_date} {method_id}: 받은 이전 {moved[method_id]:.0f} " f"!= 내준 합 × 계획 비율 {expected:.0f}"
            )
    return violations


def _check_method_transfers(
    ledger_df: pd.DataFrame,
    target_shares: Mapping[str, float],
    threshold_rate: float,
) -> list[str]:
    """규칙 7 (이전): 판단일 장부로 매매법 사이 판정과 계획 이전액을 다시 계산해, 다음 거래일의 실제 이전
    (이전 누적의 변화)이 계획과 상한 규칙대로인지 본다. 판정이 임계값을 넘은 판단일의 다음 거래일이 아니면 이전이
    없어야 한다. 판정에 쓰는 장부 몫 열은 먼저 매일 대조한다.

    「이전이 있었나」만 보면 상한이 이전을 정당하게 0 으로 깎은 날(소액 계좌)을 위반으로 잡고, 0 이 아닌 아주 작은
    이전 결함은 통과시킨다. 사유("methods")로 보면 이전이 통째로 빠져도 내주는 쪽이 자기 종목을 팔면 사유가 남는다.

    Args:
        ledger_df: 매매법 장부
        target_shares: {method_id: 계좌 대비 목표 몫} (설정 값 — 장부의 target_share 열을 믿지 않는다)
        threshold_rate: 엔진이 매매법 사이 판정에 쓰는 상대 편차 임계값

    Returns:
        위반 메시지 리스트
    """
    violations: list[str] = []
    rows = ledger_df.assign(
        method_total=ledger_df.groupby("Date", sort=False)["equity"].transform("sum"),
        moved=ledger_df.groupby("method_id", sort=False)["transfers"].diff().fillna(ledger_df["transfers"]),
    )
    for _, row in rows.iterrows():
        share = float(row["share"])
        total = float(row["method_total"])
        equity = float(row["equity"])
        if not abs(share * total - equity) <= _EQUITY_EQUATION_TOLERANCE:
            violations.append(
                f"[규칙7] {row['Date']} {row['method_id']}: 장부 몫 {share:.4f} × 매매법 자본 합 {total:.0f} "
                f"!= 매매법 자본 {equity:.0f}"
            )

    # 판정은 엔진이 쓴 값과 같은 장부 몫으로, 계획액은 엔진과 같은 식(자본 합 × 목표 몫 − 자본)으로 다시 계산한다
    dates: list[date] = list(ledger_df["Date"].drop_duplicates())
    plans: dict[date, dict[str, float]] = {}
    for i, decision_date in enumerate(dates):
        if not is_last_trading_day_of_month(dates, i):
            continue
        day = rows[rows["Date"] == decision_date]
        if any(
            abs(float(r["share"]) / target_shares[str(r["method_id"])] - 1.0) > threshold_rate
            for _, r in day.iterrows()
        ):
            plans[dates[i + 1]] = {
                str(r["method_id"]): float(r["method_total"]) * target_shares[str(r["method_id"])] - float(r["equity"])
                for _, r in day.iterrows()
            }

    for execution_date, planned in plans.items():
        day = rows[rows["Date"] == execution_date]
        moved = {str(r["method_id"]): float(r["moved"]) for _, r in day.iterrows()}
        cash = {str(r["method_id"]): float(r["cash"]) for _, r in day.iterrows()}
        violations.extend(_check_capped_transfer(execution_date, planned, moved, cash))

    unplanned = rows[(rows["moved"] != 0.0) & ~rows["Date"].isin(list(plans))]
    for _, row in unplanned.iterrows():
        violations.append(
            f"[규칙7] {row['Date']} {row['method_id']}: 매매법 사이 이전 {float(row['moved']):.0f} 이 있는데 "
            f"직전 거래일이 판정을 넘은 판단일이 아님"
        )
    return violations


def _check_method_shares_after_transfer(
    state_log_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    key_methods: Mapping[str, str],
) -> list[str]:
    """규칙 7 (되돌리기 뒤 몫): 매매법 사이 되돌리기가 체결된 날, 체결 뒤 매매법 몫이 목표 대비 허용 범위 이내인지.

    몫은 체결 뒤 주수 · 현금을 «판단일 종가»(계획이 쓴 가격)로 평가해 계산한다. 체결일 종가로 재면 밤사이 ·
    장중 가격 변동만으로 몫이 벌어져, 이전이 정상이어도 위반이 나고 러너가 멈춘다. 남는 차이는 정수 주 ·
    비용 · 매도 대금 부족에 따른 이전 축소뿐이다. 허용 범위는 규칙 2 와 같은 상대 편차다.
    """
    violations: list[str] = []
    rows = ledger_df[ledger_df["rebalance_reason"] == "methods"]
    if rows.empty:
        return violations
    dates = list(state_log_df["Date"])
    position_of = {d: idx for idx, d in enumerate(dates)}
    for execution_date, day_rows in rows.groupby("Date", sort=False):
        idx = position_of[execution_date]
        if idx == 0:
            raise RuntimeError(f"내부 불변조건 위반: 매매법 사이 되돌리기 체결일이 첫 거래일이다 (date={execution_date})")
        executed = state_log_df.iloc[idx]
        decision = state_log_df.iloc[idx - 1]
        valued: dict[str, float] = {}
        for _, row in ledger_df[ledger_df["Date"] == execution_date].iterrows():
            method_id = str(row["method_id"])
            holdings = sum(
                int(executed[asset_shares_col(key)]) * float(decision[asset_close_col(key)])
                for key, key_method in key_methods.items()
                if key_method == method_id
            )
            valued[method_id] = float(row["cash"]) + holdings
        total = sum(valued.values())
        for _, row in day_rows.iterrows():
            method_id = str(row["method_id"])
            share = valued[method_id] / total
            deviation = abs(share / float(row["target_share"]) - 1.0)
            if deviation > _REBALANCE_WEIGHT_DEVIATION_THRESHOLD:
                violations.append(
                    f"[규칙7] {execution_date} {method_id}: 판단일 종가 평가 share={share:.4f}, "
                    f"target={float(row['target_share']):.4f}, deviation={deviation:.4f}"
                )
    return violations


def validate_portfolio_result(result: PortfolioResult) -> list[str]:
    """PortfolioResult에 대해 7개 정합성 규칙을 검증한다.

    Args:
        result: 포트폴리오 백테스트 결과

    Returns:
        위반 메시지 리스트 (빈 리스트 = 전부 통과)
    """
    violations: list[str] = []

    equity_df = result.equity_df
    state_log_df = result.state_log_df
    ledger_df = result.ledger_df
    methods = resolve_methods(result.config)
    key_methods, fixed_targets = _key_targets(result.config)

    # 규칙 4, 5: equity_df 기반 (state_log 없어도 검증 가능)
    violations.extend(_check_cash_non_negative(equity_df))
    violations.extend(_check_equity_equation(equity_df))

    # 규칙 4(매매법), 6, 7(이전): 장부 기반. 엔진은 매매법이 하나여도 장부를 만든다 — 비어 있으면 검사를 건너뛰지 않고 멈춘다
    if ledger_df.empty:
        raise RuntimeError(
            f"내부 불변조건 위반: ledger_df 가 비어 있음 (experiment_name={result.config.experiment_name}). "
            f"장부 없이는 매매법 규칙(4 · 6 · 7, 매매법이 여럿이면 2)을 검사할 수 없다"
        )
    violations.extend(_check_method_cash_non_negative(ledger_df))
    target_shares = {method.method_id: method.target_weight for method in methods}
    violations.extend(_check_ledger_identities(equity_df, ledger_df, result.config.total_capital, target_shares))
    violations.extend(_check_method_transfers(ledger_df, target_shares, DEFAULT_REBALANCE_POLICY.threshold_rate))

    # 규칙 1, 2, 3, 7(되돌리기 뒤 몫): state_log_df 기반
    if state_log_df.empty:
        return violations

    asset_ids = _get_asset_ids_from_state_log(state_log_df)

    violations.extend(_check_signal_execution_lag(state_log_df, asset_ids))
    violations.extend(_check_method_shares_after_transfer(state_log_df, ledger_df, key_methods))
    single_slot_method = len(methods) == 1 and isinstance(methods[0], SlotMethodConfig)
    if single_slot_method:
        # 매매법 하나면 계좌 비중 = 매매법 비중 — 기존 계좌 단위 검사를 그대로 쓴다
        fixed = {key: target for key, target in fixed_targets.items() if target is not None}
        violations.extend(_check_rebalance_weight_consistency(state_log_df, asset_ids, fixed))
    else:
        violations.extend(
            _check_method_rebalance_weight_consistency(state_log_df, ledger_df, key_methods, fixed_targets)
        )
    violations.extend(_check_exit_all_shares_zero(state_log_df, asset_ids))

    return violations
