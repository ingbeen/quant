"""포트폴리오 체결 로직 테스트

SELL→BUY 순 체결, 부분 매도 인바리언트, 리밸런싱 체결 계약을 검증한다.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.engines.portfolio_engine import (
    OrderIntent,
    run_portfolio_backtest,
)
from qbt.backtest.engines.portfolio_execution import (
    ExecutionResult,
    execute_orders,
)
from qbt.backtest.engines.portfolio_planning import (
    ProjectedPortfolio,
)
from qbt.backtest.engines.portfolio_rebalance import (
    RebalancePolicy,
)
from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME

# ============================================================================
# 공통 헬퍼
# ============================================================================


def _make_diverge_stock_dfs(
    n_rows: int = 55,
) -> tuple[list[float], list[float], list["date"]]:
    """리밸런싱 트리거 시나리오용 합성 데이터 값 생성.

    QQQ는 급등(편차 >20%), GLD는 안정 유지.
    패턴:
    - 처음 10일: 100.0 (MA 수렴)
    - 다음 15일: 110.0 (buy signal 트리거)
    - 이후 30일: QQQ=200.0 (급등), GLD=110.0 (유지)
    """
    start = date(2024, 1, 2)
    dates_list: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates_list.append(current)
        current += timedelta(days=1)

    qqq_closes = [100.0] * 10 + [110.0] * 15 + [200.0] * (n_rows - 25)
    gld_closes = [100.0] * 10 + [110.0] * (n_rows - 10)
    return qqq_closes, gld_closes, dates_list


def _make_df_from_closes(closes: list[float], dates: list["date"]) -> "pd.DataFrame":
    """종가 목록과 날짜 목록으로 DataFrame을 생성한다."""
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [c - 0.5 for c in closes],
            COL_HIGH: [c + 1.0 for c in closes],
            COL_LOW: [c - 1.0 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * len(closes),
        }
    )


def _make_stock_df_with_sell(n_rows: int = 60, base_price: float = 100.0) -> pd.DataFrame:
    """buy → sell 신호가 모두 포함된 합성 데이터를 생성한다."""
    start = date(2024, 1, 2)
    dates: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)

    closes = [base_price] * 10 + [base_price * 1.10] * 30 + [base_price * 0.85] * (n_rows - 40)
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


def _make_stock_df(n_rows: int = 50, base_price: float = 100.0) -> pd.DataFrame:
    """테스트용 합성 주식 데이터를 생성한다."""
    start = date(2024, 1, 2)
    dates: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)

    closes = [base_price] * 10 + [base_price * 1.10] * (n_rows - 10)
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


def _make_portfolio_config(
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
        experiment_name="test_portfolio",
        display_name="Test Portfolio",
        asset_slots=slots,
        total_capital=total_capital,
        result_dir=result_dir,
    )


# ============================================================================
# 테스트 클래스
# ============================================================================


class TestPartialSellInvariant:
    """리밸런싱 부분 매도 인바리언트 테스트 (Phase 0: RED).

    핵심 계약:
    - 리밸런싱 매도 시 rebalance_sell_amount = excess_value (> 0.0) — 부분 매도
    - 리밸런싱 후 초과 자산의 position > 0 유지 (전량 매도 금지)
    - 신호 기반 매도는 여전히 전량 매도 (변경 없음)
    """

    def test_rebalancing_sell_sets_rebalance_sell_amount(self) -> None:
        """
        목적: _build_rebalance_intents() 후 초과 자산의
              REDUCE_TO_TARGET.delta_amount == -excess_value 검증.

        Given: QQQ 60%(target 40%), total_equity=1,000,000
               excess_value = 600,000 - 400,000 = 200,000
        When:  _build_rebalance_intents() 호출
        Then:  QQQ REDUCE_TO_TARGET.delta_amount == -200,000 (초과분, 전량 아님)
        """
        # Given
        projected = ProjectedPortfolio(
            projected_amounts={"qqq": 600_000.0},
            projected_cash=400_000.0,
            active_assets={"qqq"},
        )
        slot_dict = {
            "qqq": AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), target_weight=0.40),
        }
        total_equity = 1_000_000.0

        # When: QQQ 60% vs target 40% → 50% 편차 > 10% → build_rebalance_intents 직접 호출
        policy = RebalancePolicy(monthly_threshold_rate=0.10, daily_threshold_rate=0.20)
        result = policy.build_rebalance_intents(projected, slot_dict, total_equity, current_date=date(2024, 1, 2))

        # Then: REDUCE_TO_TARGET, delta_amount = 400,000 - 600,000 = -200,000 (전량 아닌 초과분)
        assert "qqq" in result
        assert result["qqq"].intent_type == "REDUCE_TO_TARGET"
        assert result["qqq"].delta_amount == pytest.approx(-200_000.0, rel=1e-6)

    def test_rebalancing_position_remains_after_partial_sell(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: 리밸런싱 매도 후 익일(체결일)에 초과 자산 qqq_value > 0 유지 검증 (전량 매도 금지).

        Given: QQQ 50% / GLD 50% 포트폴리오
               QQQ가 대폭 상승 (편차 >20%) → 첫 월 거래일에 리밸런싱 트리거
        When:  run_portfolio_backtest() 실행
        Then:  리밸런싱 트리거 익일 qqq_value > 0 (부분 매도로 포지션 유지)
        """
        # Given: QQQ 100→110 (buy signal) → 200 (편차 유발), GLD 100→110 (유지)
        n = 55
        start = date(2024, 1, 2)
        dates_list: list[date] = []
        current = start
        for _ in range(n):
            while current.weekday() >= 5:
                current += timedelta(days=1)
            dates_list.append(current)
            current += timedelta(days=1)

        qqq_closes = [100.0] * 10 + [110.0] * 15 + [200.0] * 30
        gld_closes = [100.0] * 10 + [110.0] * 45

        def _make_df(closes: list[float]) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    COL_DATE: dates_list,
                    COL_OPEN: [c - 0.5 for c in closes],
                    COL_HIGH: [c + 1.0 for c in closes],
                    COL_LOW: [c - 1.0 for c in closes],
                    COL_CLOSE: closes,
                    COL_VOLUME: [1_000_000] * n,
                }
            )

        qqq_path = create_csv_file("QQQ_max.csv", _make_df(qqq_closes))
        gld_path = create_csv_file("GLD_max.csv", _make_df(gld_closes))

        config = _make_portfolio_config(
            asset_paths={"qqq": (qqq_path, qqq_path), "gld": (gld_path, gld_path)},
            result_dir=tmp_path,
            target_weights={"qqq": 0.50, "gld": 0.50},
            ma_window=5,
            hold_days=0,
        )

        # When
        result = run_portfolio_backtest(config)
        equity_df = result.equity_df

        # 리밸런싱이 발생했는지 확인 (편차 >20% 이므로 반드시 발생해야 함)
        rebalanced_rows = equity_df[equity_df["rebalanced"] == True]  # noqa: E712
        assert len(rebalanced_rows) > 0, "QQQ 편차 >20%이므로 리밸런싱이 발생해야 함"

        # Then: 리밸런싱 체결일(rebalanced=True인 날) qqq_value > 0 (부분 매도로 포지션 유지)
        first_rebalance_idx = int(rebalanced_rows.index[0])

        rebalanced_qqq_value = float(equity_df.iloc[first_rebalance_idx]["qqq_value"])
        assert rebalanced_qqq_value > 0, (
            f"리밸런싱 매도 후 QQQ position이 유지되어야 함 (부분 매도). " f"실제 qqq_value={rebalanced_qqq_value}"
        )

    def test_signal_sell_still_full_sell(self, tmp_path: Path, create_csv_file) -> None:  # type: ignore[no-untyped-def]
        """
        목적: 신호 기반 매도는 여전히 전량 매도임을 검증 (변경 없음).

        Given: buy → sell 신호가 있는 데이터 (단일 자산 100%)
        When:  run_portfolio_backtest() 실행
        Then:  마지막 날 qqq_value == 0 (전량 매도 유지)
        """
        # Given
        stock_df = _make_stock_df_with_sell(n_rows=60)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)

        config = _make_portfolio_config(
            asset_paths={"qqq": (qqq_path, qqq_path)},
            result_dir=tmp_path,
            target_weights={"qqq": 1.0},
            ma_window=5,
        )

        # When
        result = run_portfolio_backtest(config)

        # Then: 마지막 날 포지션 = 0 (신호 기반 전량 매도 유지)
        last_row = result.equity_df.iloc[-1]
        assert last_row["qqq_value"] == pytest.approx(0.0, abs=0.01), "신호 기반 매도 후 포지션은 0이어야 함"


class TestRebalancingTopUpBuy:
    """리밸런싱 추가매수 체결 계약 테스트 (Phase 0 RED).

    핵심 계약:
    - 리밸런싱으로 생성된 buy pending_order는 position > 0인 자산에도 체결되어야 한다.
    - 체결 완료 후 position이 실제로 증가해야 한다.
    - 수정 전에는 position == 0 조건 때문에 미체결 → 테스트 실패.
    """

    def test_top_up_buy_executes_when_position_exists(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: 이미 보유 중인(position > 0) 자산에 리밸런싱 추가매수가 실제로 체결됨을 검증.

        Given: QQQ/GLD 각 50% 포트폴리오, QQQ 급등으로 편차 >20% → 리밸런싱 트리거
               GLD는 이미 보유 중 (position > 0)
        When:  run_portfolio_backtest() 실행
        Then:  rebalanced=True인 날(체결 완료일)에 GLD value가 전날보다 증가해야 함
               (GLD 가격 고정 → value 증가 = 추가매수 체결 완료)

        RED 사유: 현재 체결 루프에 `if state.position == 0:` 조건이 있어
                  position > 0이면 리밸런싱 buy pending_order가 체결되지 않음.
        """
        # Given
        qqq_closes, gld_closes, dates_list = _make_diverge_stock_dfs(n_rows=55)
        qqq_path = create_csv_file("QQQ_max.csv", _make_df_from_closes(qqq_closes, dates_list))
        gld_path = create_csv_file("GLD_max.csv", _make_df_from_closes(gld_closes, dates_list))

        config = _make_portfolio_config(
            asset_paths={"qqq": (qqq_path, qqq_path), "gld": (gld_path, gld_path)},
            result_dir=tmp_path,
            target_weights={"qqq": 0.50, "gld": 0.50},
            ma_window=5,
            hold_days=0,
        )

        # When
        result = run_portfolio_backtest(config)
        equity_df = result.equity_df

        # 리밸런싱이 발생했는지 확인
        rebalanced_rows = equity_df[equity_df["rebalanced"] == True]  # noqa: E712
        assert len(rebalanced_rows) > 0, "QQQ 급등 편차 >20%이므로 리밸런싱이 발생해야 함"

        # Then: rebalanced=True인 날(수정 후: 체결 완료일)에 GLD value가 전날보다 증가해야 함
        # GLD 가격은 110.0으로 고정 → value 증가 = position(수량) 증가 = 추가매수 체결 완료
        first_reb_idx = int(rebalanced_rows.index[0])
        assert first_reb_idx > 0, "리밸런싱 발생 전에 최소 1일 이상의 데이터가 있어야 함"

        gld_value_before = float(equity_df.iloc[first_reb_idx - 1]["gld_value"])
        gld_value_on_reb = float(equity_df.iloc[first_reb_idx]["gld_value"])

        assert gld_value_on_reb > gld_value_before, (
            f"rebalanced=True인 날은 체결 완료일이므로 GLD 추가매수가 체결되어야 함. "
            f"이전: {gld_value_before:.0f}, 리밸런싱일: {gld_value_on_reb:.0f}. "
            f"현재 버그: position > 0인 자산의 리밸런싱 buy가 체결되지 않음"
        )


class TestWeightRecoveryAfterRebalancing:
    """리밸런싱 후 과소 자산 비중 회복 계약 테스트 (Phase 0 RED).

    핵심 계약:
    - 리밸런싱 완료 후 과소 비중 자산의 weight가 리밸런싱 전보다 증가해야 한다.
    - 과대 자산은 매도 체결, 과소 자산은 추가매수 체결이 모두 이루어져야 한다.
    - 수정 전에는 과소 자산 추가매수가 미체결 → weight 회복 안 됨 → 테스트 실패.
    """

    def test_underweight_asset_weight_increases_after_rebalancing(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: 리밸런싱 후 과소 비중(GLD) weight가 실제로 증가함을 검증.

        Given: QQQ/GLD 각 50% 포트폴리오, QQQ 급등으로 GLD 과소 비중 형성
        When:  run_portfolio_backtest() 실행
        Then:  리밸런싱 체결 완료 후 GLD weight가 리밸런싱 트리거 직전보다 증가해야 함

        RED 사유: 현재 버그로 GLD 추가매수가 체결되지 않아 weight가 회복되지 않음.
        """
        # Given
        qqq_closes, gld_closes, dates_list = _make_diverge_stock_dfs(n_rows=55)
        qqq_path = create_csv_file("QQQ_max.csv", _make_df_from_closes(qqq_closes, dates_list))
        gld_path = create_csv_file("GLD_max.csv", _make_df_from_closes(gld_closes, dates_list))

        config = _make_portfolio_config(
            asset_paths={"qqq": (qqq_path, qqq_path), "gld": (gld_path, gld_path)},
            result_dir=tmp_path,
            target_weights={"qqq": 0.50, "gld": 0.50},
            ma_window=5,
            hold_days=0,
        )

        # When
        result = run_portfolio_backtest(config)
        equity_df = result.equity_df

        # 리밸런싱 발생일 확인
        rebalanced_rows = equity_df[equity_df["rebalanced"] == True]  # noqa: E712
        assert len(rebalanced_rows) > 0, "QQQ 급등 편차 >20%이므로 리밸런싱이 발생해야 함"

        first_reb_idx = int(rebalanced_rows.index[0])
        assert first_reb_idx > 0

        # 리밸런싱 트리거 직전 GLD weight (과소 비중)
        gld_weight_before = float(equity_df.iloc[first_reb_idx - 1]["gld_weight"])
        # 리밸런싱 체결 완료일(수정 후: rebalanced=True 날) GLD weight
        gld_weight_on_reb = float(equity_df.iloc[first_reb_idx]["gld_weight"])

        # Then: 체결 완료 후 GLD weight가 회복되어야 함 (과소 → 더 큰 비중)
        assert gld_weight_on_reb > gld_weight_before, (
            f"리밸런싱 체결 완료 후 GLD weight가 증가해야 함. "
            f"직전: {gld_weight_before:.4f}, 체결일: {gld_weight_on_reb:.4f}. "
            f"현재 버그: 추가매수 미체결로 weight 회복 안 됨"
        )


class TestRebalancedColumnMeaning:
    """rebalanced 컬럼 의미 계약 테스트 (Phase 0 RED).

    핵심 계약:
    - rebalanced=True는 리밸런싱 주문이 "실제 체결 완료된 날"에 기록되어야 한다.
    - pending_order 생성일(트리거일)에는 rebalanced=False이어야 한다.
    - 수정 전에는 pending 생성일에 True → 체결 완료일과 1일 어긋남 → 테스트 실패.
    """

    def test_rebalanced_true_on_execution_day_not_pending_day(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: rebalanced=True가 체결 완료일(pending 생성일 +1)에 기록됨을 검증.

        Given: QQQ/GLD 50:50 포트폴리오, QQQ 급등 → 리밸런싱 트리거
        When:  run_portfolio_backtest() 실행
        Then:  rebalanced=True인 날에 실제 포지션 변화(QQQ value 감소 또는 GLD value 증가)가 있어야 함
               즉, 체결 없는 날(pending 생성만)에는 rebalanced=True가 기록되지 않아야 함

        RED 사유: 현재 rebalanced=True가 pending 생성일(체결 전날)에 기록되므로,
                  그 날은 실제 포지션 변화가 없음 → 검증 실패.
        """
        # Given
        qqq_closes, gld_closes, dates_list = _make_diverge_stock_dfs(n_rows=55)
        qqq_path = create_csv_file("QQQ_max.csv", _make_df_from_closes(qqq_closes, dates_list))
        gld_path = create_csv_file("GLD_max.csv", _make_df_from_closes(gld_closes, dates_list))

        config = _make_portfolio_config(
            asset_paths={"qqq": (qqq_path, qqq_path), "gld": (gld_path, gld_path)},
            result_dir=tmp_path,
            target_weights={"qqq": 0.50, "gld": 0.50},
            ma_window=5,
            hold_days=0,
        )

        # When
        result = run_portfolio_backtest(config)
        equity_df = result.equity_df

        # 리밸런싱 발생 확인
        rebalanced_rows = equity_df[equity_df["rebalanced"] == True]  # noqa: E712
        assert len(rebalanced_rows) > 0, "리밸런싱이 발생해야 함"

        # Then: rebalanced=True인 날에 실제로 체결(포지션 변화)이 있어야 함
        # QQQ 가격=200(고정), GLD 가격=110(고정) 구간에서:
        # QQQ 매도 체결 → qqq_value 감소
        # GLD 매수 체결 → gld_value 증가
        first_reb_idx = int(rebalanced_rows.index[0])
        assert first_reb_idx > 0

        qqq_value_before = float(equity_df.iloc[first_reb_idx - 1]["qqq_value"])
        qqq_value_on_reb = float(equity_df.iloc[first_reb_idx]["qqq_value"])
        gld_value_before = float(equity_df.iloc[first_reb_idx - 1]["gld_value"])
        gld_value_on_reb = float(equity_df.iloc[first_reb_idx]["gld_value"])

        # 체결 완료일이면 QQQ 매도(value 감소) 또는 GLD 매수(value 증가) 중 하나라도 발생해야 함
        qqq_sold = qqq_value_on_reb < qqq_value_before - 1.0
        gld_bought = gld_value_on_reb > gld_value_before + 1.0
        assert qqq_sold or gld_bought, (
            f"rebalanced=True인 날은 체결 완료일이므로 포지션 변화가 있어야 함. "
            f"QQQ value: {qqq_value_before:.0f} → {qqq_value_on_reb:.0f}, "
            f"GLD value: {gld_value_before:.0f} → {gld_value_on_reb:.0f}. "
            f"현재 버그: rebalanced=True가 pending 생성일(체결 전날)에 기록됨"
        )

    def test_initial_entry_not_marked_as_rebalanced(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: 초기 진입(첫 매수 체결일)이 rebalanced=True로 잘못 기록되지 않음을 검증.

        Given: 단일 자산 100% 포트폴리오, buy signal 발생 후 초기 진입
        When:  run_portfolio_backtest() 실행
        Then:  첫 매수 체결일에 rebalanced=False
               (초기 진입은 리밸런싱이 아니므로 rebalanced 표시 금지)
        """
        # Given: buy → 유지 데이터 (sell 없음)
        stock_df = _make_stock_df(n_rows=30)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)

        config = _make_portfolio_config(
            asset_paths={"qqq": (qqq_path, qqq_path)},
            result_dir=tmp_path,
            target_weights={"qqq": 1.0},
            ma_window=5,
            hold_days=0,
        )

        # When
        result = run_portfolio_backtest(config)
        equity_df = result.equity_df

        # 포지션이 처음으로 생기는 날 = equity_df에서 qqq_value가 처음으로 > 0이 되는 날
        # 포트폴리오 거래 기록은 매도 체결 시에만 생성되므로 equity_df로 검증
        assert (equity_df["qqq_value"] > 0).any(), "최소 1일 이상 QQQ 포지션이 있어야 함"
        first_invested_idx = int((equity_df["qqq_value"] > 0).idxmax())

        # Then: 첫 매수 체결일은 리밸런싱이 아님
        rebalanced_on_entry = equity_df.iloc[first_invested_idx]["rebalanced"]
        assert rebalanced_on_entry is False or rebalanced_on_entry == False, (  # noqa: E712
            f"초기 진입 체결일({equity_df.iloc[first_invested_idx][COL_DATE]})에 " f"rebalanced=True가 기록되면 안 됨"
        )


# ============================================================================
# Phase 0: execute_orders 계약 고정 (레드 허용)
# ============================================================================


class TestExecuteOrders:
    """execute_orders() 계약 테스트 (Phase 0: RED).

    핵심 계약:
    1. SELL이 BUY보다 먼저 체결되어 sell_proceeds가 available_cash에 반영됨
    2. BUY 총 비용이 available_cash를 초과하면 자산별 BUY amount를 동일 비율로 축소
    3. BUY 총 비용이 available_cash 이하이면 scale 없이 원래 shares로 체결
    4. EXIT_ALL → position = 0, entry_price/date 초기화
    5. REDUCE_TO_TARGET → position이 delta_amount 기준 수량만큼 감소 (부분 매도)
    6. ENTER_TO_TARGET → 신규 position, entry_price/date 기록
    7. INCREASE_TO_TARGET → 기존 position에 추가, 가중평균 entry_price 업데이트
    """

    def test_sell_proceeds_increase_available_cash(self) -> None:
        """
        목적: EXIT_ALL 체결 후 sell_proceeds만큼 updated_cash가 증가함을 검증.

        Given: current_cash=0, QQQ 100주 보유, open_price=100.0
               EXIT_ALL intent (전량 매도)
        When:  execute_orders() 호출
        Then:  updated_cash = 100주 × 100.0 × (1 - SLIPPAGE_RATE)
               updated_positions["qqq"] = 0
        """
        from qbt.backtest.constants import SLIPPAGE_RATE

        # Given
        current_date = date(2024, 3, 1)
        order_intents: dict[str, OrderIntent] = {
            "qqq": OrderIntent(
                asset_id="qqq",
                intent_type="EXIT_ALL",
                current_amount=10_000.0,
                target_amount=0.0,
                delta_amount=-10_000.0,
                target_weight=0.0,
                reason="signal sell",
            )
        }
        open_prices = {"qqq": 100.0}
        current_positions = {"qqq": 100}
        current_cash = 0.0
        entry_prices = {"qqq": 90.0}
        entry_dates: dict[str, date | None] = {"qqq": date(2024, 1, 1)}
        entry_hold_days = {"qqq": 3}

        # When
        result = execute_orders(
            order_intents=order_intents,
            open_prices=open_prices,
            current_positions=current_positions,
            current_cash=current_cash,
            entry_prices=entry_prices,
            entry_dates=entry_dates,
            entry_hold_days=entry_hold_days,
            current_date=current_date,
        )

        # Then
        assert isinstance(result, ExecutionResult), "execute_orders는 ExecutionResult를 반환해야 함"
        expected_sell_price = 100.0 * (1.0 - SLIPPAGE_RATE)
        expected_cash = 100 * expected_sell_price
        assert result.updated_cash == pytest.approx(
            expected_cash, rel=1e-6
        ), f"EXIT_ALL 후 updated_cash가 sell_proceeds와 일치해야 함 (기대: {expected_cash:.2f}, 실제: {result.updated_cash:.2f})"
        assert result.updated_positions["qqq"] == 0, "EXIT_ALL 후 position = 0이어야 함"

    def test_sell_proceeds_used_for_subsequent_buy(self) -> None:
        """
        목적: SELL 체결 후 확보된 현금이 BUY에 활용됨을 검증.

        Given: current_cash=0, QQQ 100주 보유 (EXIT_ALL intent)
               SPY ENTER_TO_TARGET intent (delta_amount=9,700)
               open_price=100.0 (QQQ sell → 100 × 99.7 = 9,970 현금 확보)
               SPY open_price=97.0 (9,700 / (97.0 × 1.003) = ~99주 매수 가능)
        When:  execute_orders() 호출
        Then:  updated_positions["spy"] > 0 (SELL 확보 현금으로 BUY 가능)
               updated_positions["qqq"] = 0
        """
        from qbt.backtest.constants import SLIPPAGE_RATE

        # Given: QQQ 매도 후 약 9,970 현금 확보 → SPY 매수 capital=9,700 < 9,970 → 충분
        current_date = date(2024, 3, 1)
        order_intents: dict[str, OrderIntent] = {
            "qqq": OrderIntent(
                asset_id="qqq",
                intent_type="EXIT_ALL",
                current_amount=10_000.0,
                target_amount=0.0,
                delta_amount=-10_000.0,
                target_weight=0.0,
                reason="signal sell",
            ),
            "spy": OrderIntent(
                asset_id="spy",
                intent_type="ENTER_TO_TARGET",
                current_amount=0.0,
                target_amount=9_700.0,
                delta_amount=9_700.0,
                target_weight=0.50,
                reason="signal buy",
                hold_days_used=0,
            ),
        }
        open_prices = {"qqq": 100.0, "spy": 97.0}
        current_positions = {"qqq": 100, "spy": 0}
        current_cash = 0.0
        entry_prices = {"qqq": 90.0, "spy": 0.0}
        entry_dates: dict[str, date | None] = {"qqq": date(2024, 1, 1), "spy": None}
        entry_hold_days = {"qqq": 3, "spy": 0}

        # When
        result = execute_orders(
            order_intents=order_intents,
            open_prices=open_prices,
            current_positions=current_positions,
            current_cash=current_cash,
            entry_prices=entry_prices,
            entry_dates=entry_dates,
            entry_hold_days=entry_hold_days,
            current_date=current_date,
        )

        # Then: SELL 후 확보된 현금(~9,970)으로 SPY BUY(9,700) 가능 → SPY 포지션 > 0
        expected_qqq_sell = 100 * 100.0 * (1.0 - SLIPPAGE_RATE)  # ~9,970
        assert expected_qqq_sell > 9_700.0, "테스트 전제: QQQ sell proceeds가 SPY buy보다 커야 함"
        assert result.updated_positions["qqq"] == 0, "QQQ EXIT_ALL 후 position = 0이어야 함"
        assert result.updated_positions["spy"] > 0, "SELL proceeds로 SPY BUY가 가능해야 함"

    def test_buy_sufficient_cash_no_scaling(self) -> None:
        """
        목적: available_cash가 충분할 때 scale 없이 원래 shares로 체결됨을 검증.

        Given: current_cash=10,000, ENTER_TO_TARGET delta_amount=5,000
               open_price=50.0 → buy_price=50.15 → raw_shares=floor(5000/50.15)=99주
               available_cash(10,000) > raw_cost(99×50.15=4,964.85) → scale 불필요
        When:  execute_orders() 호출
        Then:  updated_positions["qqq"] = 99 (scale 없음)
               updated_cash = 10,000 - 99 × 50.15
        """
        from qbt.backtest.constants import SLIPPAGE_RATE

        # Given
        current_date = date(2024, 3, 1)
        open_price = 50.0
        buy_price = open_price * (1.0 + SLIPPAGE_RATE)
        delta_amount = 5_000.0
        expected_raw_shares = int(delta_amount / buy_price)  # 99

        order_intents: dict[str, OrderIntent] = {
            "qqq": OrderIntent(
                asset_id="qqq",
                intent_type="ENTER_TO_TARGET",
                current_amount=0.0,
                target_amount=delta_amount,
                delta_amount=delta_amount,
                target_weight=0.50,
                reason="signal buy",
                hold_days_used=0,
            )
        }
        open_prices = {"qqq": open_price}
        current_positions = {"qqq": 0}
        current_cash = 10_000.0

        # When
        result = execute_orders(
            order_intents=order_intents,
            open_prices=open_prices,
            current_positions=current_positions,
            current_cash=current_cash,
            entry_prices={"qqq": 0.0},
            entry_dates={"qqq": None},
            entry_hold_days={"qqq": 0},
            current_date=current_date,
        )

        # Then: scale 없이 raw_shares 그대로 체결
        assert (
            result.updated_positions["qqq"] == expected_raw_shares
        ), f"충분한 현금: scale 없이 raw_shares({expected_raw_shares})로 체결되어야 함, 실제: {result.updated_positions['qqq']}"
        expected_cash = current_cash - expected_raw_shares * buy_price
        assert result.updated_cash == pytest.approx(
            expected_cash, rel=1e-6
        ), f"updated_cash가 cost만큼 감소해야 함 (기대: {expected_cash:.2f}, 실제: {result.updated_cash:.2f})"

    def test_buy_cash_shortage_proportional_scaling(self) -> None:
        """
        목적: total_raw_cost > available_cash이면 자산별 BUY amount를 동일 비율로 축소한 뒤
              shares를 계산함을 검증.

        Given: current_cash=5,000
               QQQ ENTER_TO_TARGET delta_amount=4,000, open_price=100.0
               SPY ENTER_TO_TARGET delta_amount=4,000, open_price=100.0
               raw_shares 각 약 39주, raw_cost 각 약 3,912 → total_raw_cost ≈ 7,824
               scale_factor = 5,000 / 7,824 ≈ 0.639
        When:  execute_orders() 호출
        Then:  두 자산의 shares가 scale 없는 경우보다 작음 (비례 축소됨)
               updated_cash >= 0 (음수 현금 없음)
               두 자산의 shares 비율이 거의 동일 (동일 price → 동일 scale)
        """
        from qbt.backtest.constants import SLIPPAGE_RATE

        # Given
        current_date = date(2024, 3, 1)
        open_price = 100.0
        buy_price = open_price * (1.0 + SLIPPAGE_RATE)
        delta_amount = 4_000.0
        raw_shares = int(delta_amount / buy_price)  # ~39주
        raw_cost_each = raw_shares * buy_price
        total_raw_cost = raw_cost_each * 2  # 두 자산

        current_cash = 5_000.0
        assert total_raw_cost > current_cash, "테스트 전제: total_raw_cost > available_cash이어야 함"

        order_intents: dict[str, OrderIntent] = {
            "qqq": OrderIntent(
                asset_id="qqq",
                intent_type="ENTER_TO_TARGET",
                current_amount=0.0,
                target_amount=delta_amount,
                delta_amount=delta_amount,
                target_weight=0.40,
                reason="signal buy",
                hold_days_used=0,
            ),
            "spy": OrderIntent(
                asset_id="spy",
                intent_type="ENTER_TO_TARGET",
                current_amount=0.0,
                target_amount=delta_amount,
                delta_amount=delta_amount,
                target_weight=0.40,
                reason="signal buy",
                hold_days_used=0,
            ),
        }
        open_prices = {"qqq": open_price, "spy": open_price}
        current_positions = {"qqq": 0, "spy": 0}

        # When
        result = execute_orders(
            order_intents=order_intents,
            open_prices=open_prices,
            current_positions=current_positions,
            current_cash=current_cash,
            entry_prices={"qqq": 0.0, "spy": 0.0},
            entry_dates={"qqq": None, "spy": None},
            entry_hold_days={"qqq": 0, "spy": 0},
            current_date=current_date,
        )

        # Then 1: 비례 축소 → raw_shares보다 작음
        assert (
            result.updated_positions["qqq"] < raw_shares
        ), f"현금 부족 시 QQQ shares가 raw_shares({raw_shares})보다 작아야 함, 실제: {result.updated_positions['qqq']}"
        assert (
            result.updated_positions["spy"] < raw_shares
        ), f"현금 부족 시 SPY shares가 raw_shares({raw_shares})보다 작아야 함, 실제: {result.updated_positions['spy']}"

        # Then 2: 음수 현금 없음
        assert result.updated_cash >= 0.0, f"비례 축소 후 updated_cash >= 0이어야 함, 실제: {result.updated_cash:.2f}"

        # Then 3: 동일 가격 + 동일 delta_amount → 동일 비율 축소 → shares가 동일
        assert result.updated_positions["qqq"] == result.updated_positions["spy"], (
            f"동일 조건의 두 자산은 동일한 shares로 체결되어야 함 "
            f"(QQQ: {result.updated_positions['qqq']}, SPY: {result.updated_positions['spy']})"
        )

    def test_exit_all_clears_position_and_entry_info(self) -> None:
        """
        목적: EXIT_ALL 체결 후 position=0, entry_price/date가 초기화됨을 검증.

        Given: QQQ 50주 보유, entry_price=90.0, entry_date=2024-01-01
               EXIT_ALL intent
        When:  execute_orders() 호출
        Then:  updated_positions["qqq"] = 0
               updated_entry_prices["qqq"] = 0.0
               updated_entry_dates["qqq"] = None
        """
        # Given
        current_date = date(2024, 3, 1)
        order_intents: dict[str, OrderIntent] = {
            "qqq": OrderIntent(
                asset_id="qqq",
                intent_type="EXIT_ALL",
                current_amount=5_000.0,
                target_amount=0.0,
                delta_amount=-5_000.0,
                target_weight=0.0,
                reason="signal sell",
            )
        }
        open_prices = {"qqq": 102.0}
        current_positions = {"qqq": 50}
        current_cash = 0.0
        entry_prices = {"qqq": 90.0}
        entry_dates: dict[str, date | None] = {"qqq": date(2024, 1, 1)}
        entry_hold_days = {"qqq": 3}

        # When
        result = execute_orders(
            order_intents=order_intents,
            open_prices=open_prices,
            current_positions=current_positions,
            current_cash=current_cash,
            entry_prices=entry_prices,
            entry_dates=entry_dates,
            entry_hold_days=entry_hold_days,
            current_date=current_date,
        )

        # Then
        assert result.updated_positions["qqq"] == 0, "EXIT_ALL 후 position = 0이어야 함"
        assert result.updated_entry_prices["qqq"] == pytest.approx(
            0.0, abs=1e-9
        ), "EXIT_ALL 후 entry_price가 0.0으로 초기화되어야 함"
        assert result.updated_entry_dates["qqq"] is None, "EXIT_ALL 후 entry_date가 None으로 초기화되어야 함"

    def test_reduce_to_target_partial_position(self) -> None:
        """
        목적: REDUCE_TO_TARGET이 delta_amount 기준 수량만 매도함을 검증 (부분 매도).

        Given: QQQ 100주 보유, open_price=100.0
               REDUCE_TO_TARGET delta_amount=-3,000 (약 30주 매도)
        When:  execute_orders() 호출
        Then:  매도된 수량 = floor(3,000 / sell_price) = floor(3,000 / 99.7) = 30주
               updated_positions["qqq"] = 100 - 30 = 70주 (부분 매도)
        """
        from qbt.backtest.constants import SLIPPAGE_RATE

        # Given
        current_date = date(2024, 3, 1)
        open_price = 100.0
        sell_price = open_price * (1.0 - SLIPPAGE_RATE)
        reduce_amount = 3_000.0
        expected_shares_sold = int(reduce_amount / sell_price)  # floor(3000/99.7) = 30

        order_intents: dict[str, OrderIntent] = {
            "qqq": OrderIntent(
                asset_id="qqq",
                intent_type="REDUCE_TO_TARGET",
                current_amount=10_000.0,
                target_amount=7_000.0,
                delta_amount=-reduce_amount,
                target_weight=0.40,
                reason="rebalance",
            )
        }
        open_prices = {"qqq": open_price}
        current_positions = {"qqq": 100}
        current_cash = 0.0

        # When
        result = execute_orders(
            order_intents=order_intents,
            open_prices=open_prices,
            current_positions=current_positions,
            current_cash=current_cash,
            entry_prices={"qqq": 80.0},
            entry_dates={"qqq": date(2024, 1, 1)},
            entry_hold_days={"qqq": 0},
            current_date=current_date,
        )

        # Then: 부분 매도 (전량이 아님)
        expected_remaining = 100 - expected_shares_sold
        assert (
            result.updated_positions["qqq"] == expected_remaining
        ), f"REDUCE_TO_TARGET 후 잔여 수량이 {expected_remaining}이어야 함, 실제: {result.updated_positions['qqq']}"
        assert result.updated_positions["qqq"] > 0, "REDUCE_TO_TARGET은 부분 매도이므로 position이 남아야 함"

    def test_enter_to_target_records_entry_info(self) -> None:
        """
        목적: ENTER_TO_TARGET 체결 후 entry_price/date/hold_days가 기록됨을 검증.

        Given: QQQ position=0, ENTER_TO_TARGET delta_amount=5,000, open_price=50.0
               hold_days_used=3
        When:  execute_orders() 호출
        Then:  updated_positions["qqq"] > 0
               updated_entry_prices["qqq"] = buy_price (체결가)
               updated_entry_dates["qqq"] = current_date
               updated_entry_hold_days["qqq"] = 3
        """
        from qbt.backtest.constants import SLIPPAGE_RATE

        # Given
        current_date = date(2024, 3, 1)
        open_price = 50.0
        buy_price = open_price * (1.0 + SLIPPAGE_RATE)

        order_intents: dict[str, OrderIntent] = {
            "qqq": OrderIntent(
                asset_id="qqq",
                intent_type="ENTER_TO_TARGET",
                current_amount=0.0,
                target_amount=5_000.0,
                delta_amount=5_000.0,
                target_weight=0.50,
                reason="signal buy",
                hold_days_used=3,
            )
        }
        open_prices = {"qqq": open_price}
        current_positions = {"qqq": 0}
        current_cash = 10_000.0

        # When
        result = execute_orders(
            order_intents=order_intents,
            open_prices=open_prices,
            current_positions=current_positions,
            current_cash=current_cash,
            entry_prices={"qqq": 0.0},
            entry_dates={"qqq": None},
            entry_hold_days={"qqq": 0},
            current_date=current_date,
        )

        # Then
        assert result.updated_positions["qqq"] > 0, "ENTER_TO_TARGET 후 position > 0이어야 함"
        assert result.updated_entry_prices["qqq"] == pytest.approx(
            buy_price, rel=1e-6
        ), f"entry_price가 buy_price({buy_price:.4f})로 기록되어야 함, 실제: {result.updated_entry_prices['qqq']:.4f}"
        assert (
            result.updated_entry_dates["qqq"] == current_date
        ), f"entry_date가 current_date({current_date})로 기록되어야 함, 실제: {result.updated_entry_dates['qqq']}"
        assert (
            result.updated_entry_hold_days["qqq"] == 3
        ), f"entry_hold_days가 hold_days_used(3)로 기록되어야 함, 실제: {result.updated_entry_hold_days['qqq']}"

    def test_increase_to_target_weighted_avg_entry_price(self) -> None:
        """
        목적: INCREASE_TO_TARGET 체결 후 entry_price가 가중평균으로 업데이트됨을 검증.

        Given: QQQ 100주 보유, entry_price=80.0
               INCREASE_TO_TARGET delta_amount=2,000, open_price=100.0
               buy_price = 100.3 → shares = floor(2000/100.3) = 19주
               새 entry_price = (80×100 + 100.3×19) / 119
        When:  execute_orders() 호출
        Then:  updated_positions["qqq"] = 119
               updated_entry_prices["qqq"] = (80×100 + buy_price×19) / 119
        """
        from qbt.backtest.constants import SLIPPAGE_RATE

        # Given
        current_date = date(2024, 3, 1)
        open_price = 100.0
        buy_price = open_price * (1.0 + SLIPPAGE_RATE)
        delta_amount = 2_000.0
        new_shares = int(delta_amount / buy_price)  # floor(2000/100.3) = 19

        prev_position = 100
        prev_entry_price = 80.0

        order_intents: dict[str, OrderIntent] = {
            "qqq": OrderIntent(
                asset_id="qqq",
                intent_type="INCREASE_TO_TARGET",
                current_amount=10_000.0,
                target_amount=12_000.0,
                delta_amount=delta_amount,
                target_weight=0.60,
                reason="rebalance",
            )
        }
        open_prices = {"qqq": open_price}
        current_positions = {"qqq": prev_position}
        current_cash = 5_000.0

        # When
        result = execute_orders(
            order_intents=order_intents,
            open_prices=open_prices,
            current_positions=current_positions,
            current_cash=current_cash,
            entry_prices={"qqq": prev_entry_price},
            entry_dates={"qqq": date(2024, 1, 1)},
            entry_hold_days={"qqq": 0},
            current_date=current_date,
        )

        # Then
        expected_total_shares = prev_position + new_shares
        expected_entry_price = (prev_entry_price * prev_position + buy_price * new_shares) / expected_total_shares

        assert (
            result.updated_positions["qqq"] == expected_total_shares
        ), f"INCREASE_TO_TARGET 후 총 수량이 {expected_total_shares}이어야 함, 실제: {result.updated_positions['qqq']}"
        assert result.updated_entry_prices["qqq"] == pytest.approx(expected_entry_price, rel=1e-6), (
            f"INCREASE_TO_TARGET 후 entry_price가 가중평균({expected_entry_price:.4f})이어야 함, "
            f"실제: {result.updated_entry_prices['qqq']:.4f}"
        )
