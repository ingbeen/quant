"""포트폴리오 State Log 정합성 규칙 테스트

run_portfolio_backtest()가 반환하는 state_log_df, equity_df, trades_df 사이의
정합성을 5개 규칙으로 검증한다.

규칙 1: 시그널-체결 1일 lag
규칙 2: 리밸런싱 후 비중 정합성
규칙 3: EXIT_ALL 후 주수 0
규칙 4: 현금 비음수
규칙 5: 에쿼티 등식 (equity = cash + sum(shares * close))
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.engines.portfolio_engine import run_portfolio_backtest
from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME

# ============================================================================
# 공통 헬퍼
# ============================================================================


def _make_stock_df_for_state_log(
    n_rows: int = 80,
    base_price: float = 100.0,
) -> pd.DataFrame:
    """buy -> hold -> sell 시그널이 모두 포함된 합성 데이터를 생성한다.

    price 패턴:
    - 처음 10일: base_price (안정, EMA 수렴)
    - 다음 40일: base_price * 1.12 (12% 상승, buy signal 트리거)
    - 마지막 30일: base_price * 0.82 (18% 하락, sell signal 트리거)

    이 패턴으로 buy -> sell 전환이 발생하여 EXIT_ALL, 리밸런싱,
    시그널-체결 lag을 모두 검증할 수 있다.
    """
    start = date(2024, 1, 2)
    dates: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)

    closes = [base_price] * 10 + [base_price * 1.12] * 40 + [base_price * 0.82] * (n_rows - 50)
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [c - 0.5 for c in closes],
            COL_HIGH: [c + 1.0 for c in closes],
            COL_LOW: [c - 1.0 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * n_rows,
        }
    )


def _make_portfolio_config_for_state_log(
    asset_paths: dict[str, tuple[Path, Path]],
    result_dir: Path,
    *,
    target_weights: dict[str, float] | None = None,
    ma_window: int = 5,
    hold_days: int = 0,
    total_capital: float = 10_000_000.0,
) -> PortfolioConfig:
    """테스트용 PortfolioConfig를 생성한다."""
    if target_weights is None:
        equal_weight = 1.0 / len(asset_paths)
        target_weights = {aid: equal_weight for aid in asset_paths}

    slots = tuple(
        AssetSlotConfig(
            asset_id=aid,
            signal_data_path=signal_path,
            trade_data_path=trade_path,
            target_weight=target_weights.get(aid, 0.25),
            ma_window=ma_window,
            hold_days=hold_days,
        )
        for aid, (signal_path, trade_path) in asset_paths.items()
    )

    return PortfolioConfig(
        experiment_name="test_state_log",
        display_name="Test State Log",
        asset_slots=slots,
        total_capital=total_capital,
        result_dir=result_dir,
    )


def _get_asset_ids(state_log_df: pd.DataFrame) -> list[str]:
    """state_log_df에서 자산 ID 목록을 추출한다.

    {asset_id}_close 컬럼을 기준으로 탐지한다.
    (_shares는 _exec_shares와 충돌하므로 _close 사용)
    """
    return [c.removesuffix("_close") for c in state_log_df.columns if c.endswith("_close")]


# ============================================================================
# 픽스처
# ============================================================================


@pytest.fixture
def portfolio_result_with_sell(tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
    """buy -> sell 전환이 포함된 포트폴리오 백테스트 결과를 반환한다.

    자산 2개 (asset_a, asset_b), 각각 50% 비중.
    시그널 패턴: 안정 -> 상승(buy) -> 하락(sell)
    ma_window=5, hold_days=0으로 빠른 시그널 발생.

    Returns:
        PortfolioResult (equity_df, trades_df, state_log_df 포함)
    """
    stock_df = _make_stock_df_for_state_log(n_rows=80)
    path_a = create_csv_file("ASSET_A_max.csv", stock_df)
    path_b = create_csv_file("ASSET_B_max.csv", stock_df)

    config = _make_portfolio_config_for_state_log(
        asset_paths={
            "asset_a": (path_a, path_a),
            "asset_b": (path_b, path_b),
        },
        result_dir=tmp_path,
        target_weights={"asset_a": 0.50, "asset_b": 0.50},
        ma_window=5,
        hold_days=0,
    )

    return run_portfolio_backtest(config)


# ============================================================================
# 규칙 4, 5: equity_df 기반 검증 (state_log 불필요, Phase 0에서 그린)
# ============================================================================


class TestCashNonNegative:
    """규칙 4: 모든 거래일에서 현금이 음수가 아니어야 한다.

    핵심 계약: 매수 시 비례 축소(scale_factor)로 음수 현금을 방지한다.
    """

    def test_cash_always_non_negative(self, portfolio_result_with_sell):  # type: ignore[no-untyped-def]
        """
        목적: 전체 기간 동안 현금이 음수가 되는 날이 없는지 검증.

        Given: buy -> sell 전환이 포함된 포트폴리오 결과
        When: equity_df의 모든 행에서 cash 값을 확인
        Then: 모든 행에서 cash >= 0
        """
        # Given
        equity_df = portfolio_result_with_sell.equity_df

        # When & Then
        negative_cash = equity_df[equity_df["cash"] < 0]
        assert negative_cash.empty, f"현금이 음수인 거래일이 {len(negative_cash)}건 존재: " f"{negative_cash['Date'].tolist()}"


class TestEquityEquation:
    """규칙 5: 에쿼티 = 현금 + 자산 평가액 합계.

    핵심 계약: equity = cash + sum(shares * close)
    equity_df에 기록된 값으로 등식을 매일 검증한다.
    """

    def test_equity_equals_cash_plus_asset_values(self, portfolio_result_with_sell):  # type: ignore[no-untyped-def]
        """
        목적: 매 거래일 에쿼티 등식이 성립하는지 검증.

        Given: buy -> sell 전환이 포함된 포트폴리오 결과
        When: 각 행에서 cash + sum({asset}_value) vs equity 비교
        Then: 부동소수점 허용오차 이내 일치 (abs=1.0)
        """
        # Given
        equity_df = portfolio_result_with_sell.equity_df
        value_cols = [c for c in equity_df.columns if c.endswith("_value")]

        # When & Then
        for i, row in equity_df.iterrows():
            computed = float(row["cash"]) + sum(float(row[vc]) for vc in value_cols)
            recorded = float(row["equity"])
            assert computed == pytest.approx(recorded, abs=1.0), (
                f"에쿼티 등식 불일치 (행 {i}, 날짜 {row['Date']}): "
                f"cash({row['cash']}) + values({computed - float(row['cash']):.0f}) = {computed:.0f} "
                f"!= equity({recorded:.0f})"
            )


# ============================================================================
# 규칙 1, 2, 3: state_log_df 기반 검증 (Phase 0에서 레드, Phase 1에서 그린)
# ============================================================================


class TestSignalExecutionOneDayLag:
    """규칙 1: 시그널-체결 1일 lag.

    핵심 계약: i일의 pending_intent != ""이면
    i+1일의 executed_intent가 동일해야 한다.
    (신호일 종가 판정 -> 익일 시가 체결)
    """

    def test_pending_intent_executed_next_day(self, portfolio_result_with_sell):  # type: ignore[no-untyped-def]
        """
        목적: pending intent가 다음 거래일에 정확히 체결되는지 검증.

        Given: buy -> sell 전환이 포함된 포트폴리오 결과의 state_log_df
        When: 각 자산별로 pending_intent가 있는 날의 다음날 executed_intent 확인
        Then: pending_intent == 다음날 executed_intent (마지막 날 제외)
        """
        # Given
        state_log_df = portfolio_result_with_sell.state_log_df
        assert not state_log_df.empty, "state_log_df가 비어있으면 안 됨"

        asset_ids = _get_asset_ids(state_log_df)
        assert len(asset_ids) > 0, "자산 ID가 1개 이상 있어야 함"

        # When & Then
        mismatches: list[str] = []
        for aid in asset_ids:
            pending_col = f"{aid}_pending_intent"
            executed_col = f"{aid}_executed_intent"
            assert pending_col in state_log_df.columns, f"{pending_col} 컬럼이 없음"
            assert executed_col in state_log_df.columns, f"{executed_col} 컬럼이 없음"

            for i in range(len(state_log_df) - 1):
                pending = str(state_log_df.iloc[i][pending_col])
                if pending and pending != "" and pending != "nan":
                    next_executed = str(state_log_df.iloc[i + 1][executed_col])
                    if pending != next_executed:
                        d = state_log_df.iloc[i]["Date"]
                        mismatches.append(f"{aid}: {d} pending={pending} -> " f"다음날 executed={next_executed}")

        assert len(mismatches) == 0, f"시그널-체결 1일 lag 불일치 {len(mismatches)}건:\n" + "\n".join(mismatches[:10])


class TestRebalanceWeightConsistency:
    """규칙 2: 리밸런싱 후 비중 정합성.

    핵심 계약: 리밸런싱 실행 후 보유 자산의 비중이
    목표 비중 대비 리밸런싱 임계값보다 작아야 한다.
    (정수 주식 수량 제약 + 슬리피지로 정확 일치는 불가)
    """

    def test_weight_deviation_within_threshold_after_rebalance(self, portfolio_result_with_sell):  # type: ignore[no-untyped-def]
        """
        목적: 리밸런싱 체결 후 비중 편차가 합리적 범위 내인지 검증.

        Given: buy -> sell 전환이 포함된 포트폴리오 결과의 state_log_df
        When: rebalanced == True인 행에서 보유 자산(shares > 0)의 비중 편차 확인
        Then: |actual_weight / target_weight - 1| < 리밸런싱 임계값 (0.10)
              (단, 소액 자산은 정수 주수 제약으로 편차가 클 수 있으므로 0.15로 완화)
        """
        # Given
        state_log_df = portfolio_result_with_sell.state_log_df
        assert not state_log_df.empty, "state_log_df가 비어있으면 안 됨"

        config = portfolio_result_with_sell.config
        target_weights = {slot.asset_id: slot.target_weight for slot in config.asset_slots}
        asset_ids = _get_asset_ids(state_log_df)

        # When: 리밸런싱 발생일 필터
        if "rebalanced" not in state_log_df.columns:
            pytest.skip("rebalanced 컬럼이 없어 리밸런싱 검증 불가")
            return

        reb_rows = state_log_df[state_log_df["rebalanced"] == True]  # noqa: E712
        if reb_rows.empty:
            # 리밸런싱이 발생하지 않았으면 검증 대상 없음 (통과)
            return

        # Then
        max_deviation_threshold = 0.15
        violations: list[str] = []
        for _, row in reb_rows.iterrows():
            for aid in asset_ids:
                shares_col = f"{aid}_shares"
                weight_col = f"{aid}_weight"
                target_w = target_weights.get(aid, 0)

                if target_w <= 0:
                    continue

                shares = int(row.get(shares_col, 0))
                if shares <= 0:
                    continue

                actual_w = float(row.get(weight_col, 0))
                deviation = abs(actual_w / target_w - 1.0)
                if deviation > max_deviation_threshold:
                    violations.append(
                        f"{row['Date']} {aid}: actual={actual_w:.4f}, "
                        f"target={target_w:.4f}, deviation={deviation:.4f}"
                    )

        assert len(violations) == 0, f"리밸런싱 후 비중 편차 초과 {len(violations)}건:\n" + "\n".join(violations[:10])


class TestExitAllSharesZero:
    """규칙 3: EXIT_ALL 체결 후 해당 자산 주수가 0이어야 한다.

    핵심 계약: EXIT_ALL intent가 체결되면 전량 매도이므로
    해당 자산의 shares가 0이어야 한다.
    """

    def test_shares_zero_after_exit_all(self, portfolio_result_with_sell):  # type: ignore[no-untyped-def]
        """
        목적: EXIT_ALL 체결 후 해당 자산 보유 수량이 0인지 검증.

        Given: buy -> sell 전환이 포함된 포트폴리오 결과의 state_log_df
        When: executed_intent == "EXIT_ALL"인 행에서 해당 자산의 shares 확인
        Then: 해당 자산의 shares == 0
        """
        # Given
        state_log_df = portfolio_result_with_sell.state_log_df
        assert not state_log_df.empty, "state_log_df가 비어있으면 안 됨"

        asset_ids = _get_asset_ids(state_log_df)

        # When & Then
        violations: list[str] = []
        for aid in asset_ids:
            executed_col = f"{aid}_executed_intent"
            shares_col = f"{aid}_shares"

            if executed_col not in state_log_df.columns:
                continue

            exit_all_rows = state_log_df[state_log_df[executed_col] == "EXIT_ALL"]
            for _, row in exit_all_rows.iterrows():
                shares = int(row.get(shares_col, -1))
                if shares != 0:
                    violations.append(f"{row['Date']} {aid}: EXIT_ALL 체결 후 shares={shares} (0이어야 함)")

        assert len(violations) == 0, f"EXIT_ALL 후 주수 비정상 {len(violations)}건:\n" + "\n".join(violations[:10])
