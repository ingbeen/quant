"""포트폴리오 백테스트 전략 테스트

핵심 계약/불변조건을 테스트로 고정한다.

Phase 0: 엔진(portfolio_strategy.py) 미구현으로 현재 import 오류가 발생한다 (RED).
Phase 1: 엔진 구현 후 전체 통과(GREEN)를 목표로 한다.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.portfolio_strategy import (  # pyright: ignore[reportPrivateUsage]
    _AssetState,
    _check_rebalancing_needed,
    _compute_portfolio_equity,
    _execute_rebalancing,
    _is_first_trading_day_of_month,
    _PortfolioPendingOrder,
    run_portfolio_backtest,
)
from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME

# ============================================================================
# 공통 헬퍼
# ============================================================================


def _make_stock_df(n_rows: int = 50, base_price: float = 100.0) -> pd.DataFrame:
    """테스트용 합성 주식 데이터를 생성한다.

    price 패턴:
    - 처음 10일: base_price (안정 구간, EMA 수렴)
    - 이후 n-10일: base_price * 1.10 (10% 상승, buy signal 트리거용)
    """
    start = date(2024, 1, 2)
    dates: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:  # 주말 건너뛰기
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)

    # 처음 10일 안정 → 이후 10% 상승 (buy signal 트리거)
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


def _make_stock_df_with_sell(n_rows: int = 60, base_price: float = 100.0) -> pd.DataFrame:
    """buy → sell 신호가 모두 포함된 합성 데이터를 생성한다.

    price 패턴:
    - 처음 10일: base_price (안정)
    - 다음 30일: base_price * 1.10 (buy signal 트리거)
    - 마지막 20일: base_price * 0.85 (sell signal 트리거)
    """
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


def _make_portfolio_config(
    asset_paths: dict[str, tuple[Path, Path]],
    result_dir: Path,
    *,
    target_weights: dict[str, float] | None = None,
    ma_window: int = 5,
    hold_days: int = 0,
    total_capital: float = 10_000_000.0,
) -> PortfolioConfig:
    """테스트용 PortfolioConfig를 생성한다.

    Args:
        asset_paths: {asset_id: (signal_path, trade_path)}
        result_dir: 결과 저장 디렉토리 (tmp_path)
        target_weights: {asset_id: weight} (기본값: 동일 비중 배분)
        ma_window: 이동평균 기간
        hold_days: 유지일수
        total_capital: 총 초기 자본금
    """
    if target_weights is None:
        equal_weight = 1.0 / len(asset_paths)
        target_weights = {aid: equal_weight for aid in asset_paths}

    slots = tuple(
        AssetSlotConfig(
            asset_id=aid,
            signal_data_path=signal_path,
            trade_data_path=trade_path,
            target_weight=target_weights.get(aid, 0.25),
        )
        for aid, (signal_path, trade_path) in asset_paths.items()
    )

    return PortfolioConfig(
        experiment_name="test_portfolio",
        display_name="Test Portfolio",
        asset_slots=slots,
        total_capital=total_capital,
        rebalance_threshold_rate=0.20,
        result_dir=result_dir,
        ma_window=ma_window,
        buy_buffer_zone_pct=0.03,
        sell_buffer_zone_pct=0.05,
        hold_days=hold_days,
        ma_type="ema",
    )


def _make_minimal_config(asset_id: str, target_weight: float) -> PortfolioConfig:
    """단일 자산 단위 테스트용 최소 PortfolioConfig를 생성한다."""
    return PortfolioConfig(
        experiment_name="test",
        display_name="Test",
        asset_slots=(AssetSlotConfig(asset_id, Path("dummy"), Path("dummy"), target_weight),),
        total_capital=100_000.0,
        rebalance_threshold_rate=0.20,
        result_dir=Path("."),
        ma_window=5,
        buy_buffer_zone_pct=0.03,
        sell_buffer_zone_pct=0.05,
        hold_days=0,
        ma_type="ema",
    )


# ============================================================================
# 테스트 클래스
# ============================================================================


class TestRebalancingTrigger:
    """상대 임계값 ±20% 경계 조건 테스트.

    핵심 계약: |actual/target - 1| > 0.20 이면 리밸런싱 트리거.
    경계값(정확히 0.20)에서는 트리거하지 않는다.
    """

    def test_no_trigger_at_boundary(self):
        """
        목적: actual/target - 1 = 0.20 (정확히 경계값)이면 트리거 없음 검증.

        Given: target_weight=0.30, actual_weight=0.36 → |0.36/0.30 - 1| = 0.20
        When:  _check_rebalancing_needed() 호출
        Then:  False 반환 (경계값 포함 미실행 정책)
        """
        # Given
        total_equity = 100_000.0
        asset_states = {"qqq": _AssetState(position=0, signal_state="buy", pending_order=None, hold_state=None)}
        equity_vals = {"qqq": 36_000.0}  # 36_000 / 100_000 = 0.36
        config = _make_minimal_config("qqq", target_weight=0.30)

        # When
        result = _check_rebalancing_needed(asset_states, equity_vals, total_equity, config)

        # Then
        assert result is False, "정확히 임계값(0.20)에서는 리밸런싱이 트리거되면 안 됨"

    def test_trigger_above_boundary(self):
        """
        목적: |actual/target - 1| > 0.20 이면 트리거 발생 검증.

        Given: target_weight=0.30, actual_weight=0.361 → |0.361/0.30 - 1| ≈ 0.203 > 0.20
        When:  _check_rebalancing_needed() 호출
        Then:  True 반환 (임계값 초과 → 트리거)
        """
        # Given
        total_equity = 100_000.0
        asset_states = {"qqq": _AssetState(position=0, signal_state="buy", pending_order=None, hold_state=None)}
        equity_vals = {"qqq": 36_100.0}  # 36_100 / 100_000 = 0.361
        config = _make_minimal_config("qqq", target_weight=0.30)

        # When
        result = _check_rebalancing_needed(asset_states, equity_vals, total_equity, config)

        # Then
        assert result is True, "임계값 초과(0.2033)에서는 리밸런싱이 트리거되어야 함"


class TestRebalancingExcludesSoldAssets:
    """매도 시그널 자산은 리밸런싱에서 제외되어야 한다.

    핵심 계약: signal_state == "sell" 자산은 리밸런싱 대상에서 제외.
    SPY가 매도 시그널 중이면 SPY pending_order는 생성되지 않는다.
    """

    def test_rebalancing_excludes_sold_assets(self):
        """
        목적: 매도 시그널 자산이 리밸런싱에서 제외됨을 검증.

        Given: SPY 시그널 = "sell" (포지션 0), QQQ 시그널 = "buy"
               QQQ 실제 비중 40% (타겟 30%, |0.40/0.30-1|=0.333 > 0.20 → 트리거)
        When:  _execute_rebalancing() 호출
        Then:  QQQ 매도 pending_order 생성 (40% → 30%로 축소)
               SPY pending_order는 None 유지 (매도 시그널 자산 제외)
        """
        # Given
        # QQQ: 40% (target 30%), SPY: 0% (signal=sell)
        asset_states = {
            "qqq": _AssetState(position=100, signal_state="buy", pending_order=None, hold_state=None),
            "spy": _AssetState(position=0, signal_state="sell", pending_order=None, hold_state=None),
        }
        equity_vals = {"qqq": 400_000.0, "spy": 0.0}
        shared_cash = 600_000.0  # 총 1_000_000

        config = PortfolioConfig(
            experiment_name="test",
            display_name="Test",
            asset_slots=(
                AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), 0.30),
                AssetSlotConfig("spy", Path("dummy"), Path("dummy"), 0.30),
            ),
            total_capital=1_000_000.0,
            rebalance_threshold_rate=0.20,
            result_dir=Path("."),
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
            ma_type="ema",
        )

        # When
        _execute_rebalancing(asset_states, equity_vals, config, shared_cash, date(2024, 1, 2))

        # Then
        # QQQ 과비중 → 매도 pending_order 생성
        assert asset_states["qqq"].pending_order is not None, "QQQ는 과비중이므로 매도 pending_order가 생성되어야 함"
        assert asset_states["qqq"].pending_order.order_type == "sell"

        # SPY는 매도 시그널 → 리밸런싱 제외 → pending_order 없음
        assert asset_states["spy"].pending_order is None, "SPY는 매도 시그널이므로 pending_order가 생성되면 안 됨"


class TestQQQTQQQSharedSignal:
    """QQQ와 TQQQ가 동일한 signal_data_path를 사용할 때 시그널이 공유되어야 한다.

    핵심 계약: signal_data_path가 동일한 자산은 동일 날짜에 같은 시그널을 발생시킨다.
    QQQ 매도 시 TQQQ도 같은 날 매도 pending_order가 생성된다.
    """

    def test_qqq_tqqq_shared_signal(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: QQQ/TQQQ 공유 시그널 메커니즘 검증.

        Given: QQQ AssetSlotConfig(signal_data_path=QQQ_PATH)
               TQQQ AssetSlotConfig(signal_data_path=QQQ_PATH) ← 동일 경로
               QQQ 데이터: buy → sell 전환 포함
        When:  run_portfolio_backtest() 실행
        Then:  QQQ와 TQQQ가 동일한 날짜에 exit (trades_df에 같은 exit_date)
               두 포지션 모두 청산되어 equity_df에서 QQQ/TQQQ 포지션 = 0
        """
        # Given: buy → sell 전환이 있는 데이터
        stock_df = _make_stock_df_with_sell(n_rows=60)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)
        tqqq_path = create_csv_file("TQQQ_synthetic_max.csv", stock_df)

        # QQQ와 TQQQ 모두 QQQ 데이터를 시그널 소스로 사용
        config = _make_portfolio_config(
            asset_paths={
                "qqq": (qqq_path, qqq_path),
                "tqqq": (qqq_path, tqqq_path),  # ← 시그널은 QQQ 경로 공유
            },
            result_dir=tmp_path,
            target_weights={"qqq": 0.50, "tqqq": 0.50},
            ma_window=5,
            hold_days=0,
        )

        # When
        result = run_portfolio_backtest(config)

        # Then
        trades = result.trades_df
        qqq_trades = trades[trades["asset_id"] == "qqq"]
        tqqq_trades = trades[trades["asset_id"] == "tqqq"]

        # 두 자산 모두 거래가 발생해야 함 (buy + sell)
        assert len(qqq_trades) > 0, "QQQ 거래 내역이 있어야 함"
        assert len(tqqq_trades) > 0, "TQQQ 거래 내역이 있어야 함"

        # 마지막 매도(exit)의 날짜가 동일해야 함 (공유 시그널로 동시 청산)
        qqq_last_exit = qqq_trades["exit_date"].max()
        tqqq_last_exit = tqqq_trades["exit_date"].max()
        assert qqq_last_exit == tqqq_last_exit, f"QQQ({qqq_last_exit})와 TQQQ({tqqq_last_exit})의 마지막 매도 날짜가 동일해야 함"


class TestCashPartialFill:
    """현금 부족 시 비례 배분 리밸런싱 테스트.

    핵심 계약: 매수 필요액 > 가용 현금이면 scale_factor를 적용하여 비례 축소.
    """

    def test_cash_partial_fill_on_rebalancing(self):
        """
        목적: 가용 현금 < 매수 필요액 시 scale_factor 비례 축소 검증.

        Given: 두 매수 자산, 각각 1,500,000 매수 필요 → 총 3,000,000
               가용 현금 = 2,000,000 (< 3,000,000)
        When:  _execute_rebalancing() 호출
        Then:  scale_factor = 2,000,000 / 3,000,000 ≈ 0.667
               각 매수 자산 pending_order.capital = 1,500,000 × 0.667 = 1,000,000
               두 pending_order.capital 합계 = 2,000,000 (가용 현금 소진)
        """
        # Given: 두 자산 모두 포지션 없음 (각각 target 50%, 현재 0%)
        asset_states = {
            "A": _AssetState(position=0, signal_state="buy", pending_order=None, hold_state=None),
            "B": _AssetState(position=0, signal_state="buy", pending_order=None, hold_state=None),
        }
        equity_vals = {"A": 0.0, "B": 0.0}
        shared_cash = 2_000_000.0  # 가용 현금 (< 총 매수 필요 3,000,000)

        config = PortfolioConfig(
            experiment_name="test",
            display_name="Test",
            asset_slots=(
                AssetSlotConfig("A", Path("dummy"), Path("dummy"), 0.50),
                AssetSlotConfig("B", Path("dummy"), Path("dummy"), 0.50),
            ),
            total_capital=3_000_000.0,
            rebalance_threshold_rate=0.20,
            result_dir=Path("."),
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
            ma_type="ema",
        )

        # When
        _execute_rebalancing(asset_states, equity_vals, config, shared_cash, date(2024, 1, 2))

        # Then
        a_order = asset_states["A"].pending_order
        b_order = asset_states["B"].pending_order

        assert a_order is not None, "자산 A에 매수 pending_order가 생성되어야 함"
        assert b_order is not None, "자산 B에 매수 pending_order가 생성되어야 함"
        assert a_order.order_type == "buy"
        assert b_order.order_type == "buy"

        # scale_factor = 2,000,000 / 3,000,000 = 2/3
        # 각 자산 capital = 1,500,000 × 2/3 = 1,000,000
        assert a_order.capital == pytest.approx(
            1_000_000.0, rel=1e-6
        ), f"A의 매수 자본이 1,000,000이어야 함 (현재: {a_order.capital})"
        assert b_order.capital == pytest.approx(
            1_000_000.0, rel=1e-6
        ), f"B의 매수 자본이 1,000,000이어야 함 (현재: {b_order.capital})"

        # 두 pending_order capital 합 = 가용 현금
        total_pending = a_order.capital + b_order.capital
        assert total_pending == pytest.approx(
            2_000_000.0, rel=1e-6
        ), f"두 매수 capital 합이 가용 현금(2,000,000)과 같아야 함 (현재: {total_pending})"


class TestPortfolioEquityFormula:
    """에쿼티 산식 검증.

    핵심 계약: equity = shared_cash + Σ(position × close)
    """

    def test_portfolio_equity_formula(self):
        """
        목적: 에쿼티가 올바른 산식으로 계산되어야 함.

        Given: shared_cash=3,000,000
               QQQ 10,000주 × close=400.0
               GLD 5,000주 × close=200.0
        When:  _compute_portfolio_equity() 호출
        Then:  equity = 3,000,000 + 4,000,000 + 1,000,000 = 8,000,000
        """
        # Given
        shared_cash = 3_000_000.0
        asset_positions = {"qqq": 10_000, "gld": 5_000}
        asset_closes = {"qqq": 400.0, "gld": 200.0}

        # When
        equity = _compute_portfolio_equity(shared_cash, asset_positions, asset_closes)

        # Then: 3,000,000 + 10,000×400 + 5,000×200 = 8,000,000
        assert equity == pytest.approx(8_000_000.0, abs=0.01), f"에쿼티가 8,000,000이어야 함 (현재: {equity})"


class TestMonthlyRebalancing:
    """월 첫 거래일 판정 테스트.

    핵심 계약: 전일 월 != 당일 월이면 True (월 첫 거래일).
    """

    def test_monthly_rebalancing_only_on_first_day(self):
        """
        목적: _is_first_trading_day_of_month()가 월 전환일만 True를 반환하는지 검증.

        Given: 날짜 목록 [2024-01-30, 2024-01-31, 2024-02-01, 2024-02-02]
        When:  각 인덱스에 대해 _is_first_trading_day_of_month() 호출
        Then:  인덱스 0 (2024-01-30) → False (첫 번째 행, 이전 날 없음)
               인덱스 1 (2024-01-31) → False (전 거래일 1월)
               인덱스 2 (2024-02-01) → True  (전 거래일 1월 → 2월로 전환)
               인덱스 3 (2024-02-02) → False (전 거래일 2월)
        """
        # Given
        trade_dates = [
            date(2024, 1, 30),
            date(2024, 1, 31),
            date(2024, 2, 1),
            date(2024, 2, 2),
        ]

        # When & Then
        assert _is_first_trading_day_of_month(trade_dates, 0) is False, "첫 번째 행(i=0)은 이전 행이 없으므로 False이어야 함"
        assert _is_first_trading_day_of_month(trade_dates, 1) is False, "2024-01-31: 전 거래일도 1월이므로 False이어야 함"
        assert _is_first_trading_day_of_month(trade_dates, 2) is True, "2024-02-01: 전 거래일 1월 → 2월 전환이므로 True이어야 함"
        assert _is_first_trading_day_of_month(trade_dates, 3) is False, "2024-02-02: 전 거래일도 2월이므로 False이어야 함"


class TestB1CashBuffer:
    """B-1 포트폴리오 초기 현금 버퍼 테스트.

    핵심 계약: target_weight 합이 1.0 미만이면 잔여분이 현금으로 유지된다.
    """

    def test_b1_initial_cash_stays_uninvested(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: B-1 포트폴리오에서 target_weight 합 = 0.86 → 14% 현금 유지 검증.

        Given: B-1 config (QQQ 19.5%, TQQQ 7%, SPY 19.5%, GLD 40%)
               target_weight 합 = 0.86 (현금 14% 자연 발생)
               전 자산 동일 상승 데이터 (buy signal 발생)
        When:  run_portfolio_backtest() 실행
        Then:  최초 매수 이후 shared_cash ≈ total_capital × 0.14
               투자된 총액 ≈ total_capital × 0.86
        """
        # Given: 모든 자산에 동일한 상승 데이터 사용 (buy signal 트리거)
        stock_df = _make_stock_df(n_rows=30)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)
        spy_path = create_csv_file("SPY_max.csv", stock_df)
        gld_path = create_csv_file("GLD_max.csv", stock_df)
        tqqq_path = create_csv_file("TQQQ_synthetic_max.csv", stock_df)

        total_capital = 10_000_000.0
        config = _make_portfolio_config(
            asset_paths={
                "qqq": (qqq_path, qqq_path),
                "tqqq": (qqq_path, tqqq_path),  # TQQQ는 QQQ 시그널 공유
                "spy": (spy_path, spy_path),
                "gld": (gld_path, gld_path),
            },
            result_dir=tmp_path,
            target_weights={
                "qqq": 0.195,
                "tqqq": 0.07,
                "spy": 0.195,
                "gld": 0.40,
            },  # 합 = 0.86
            ma_window=5,
            hold_days=0,
            total_capital=total_capital,
        )

        # When
        result = run_portfolio_backtest(config)

        # Then: 모든 buy signal이 실행된 이후 날짜의 cash 확인
        # equity_df에서 모든 자산이 투자된 이후 행을 찾아 cash 검증
        equity_df = result.equity_df
        # 4개 자산 모두 포지션이 있는 첫 번째 날
        invested_rows = equity_df[
            (equity_df.get("qqq_value", pd.Series([0.0])) > 0)
            & (equity_df.get("spy_value", pd.Series([0.0])) > 0)
            & (equity_df.get("gld_value", pd.Series([0.0])) > 0)
        ]
        assert len(invested_rows) > 0, "4개 자산 모두 투자된 날이 존재해야 함"

        # 최초 완전투자 이후 cash ≈ total_capital × 0.14
        first_invested_cash = invested_rows["cash"].iloc[0]
        expected_cash = total_capital * 0.14
        assert first_invested_cash == pytest.approx(
            expected_cash, rel=0.05
        ), f"초기 현금이 total × 14% ≈ {expected_cash:,.0f}이어야 함 (현재: {first_invested_cash:,.0f})"


class TestRebalancingOrder:
    """리밸런싱 순서 검증 — 매도 먼저, 매도 대금으로 매수.

    핵심 계약: shared_cash=0이어도 매도 예상 대금을 매수 자본으로 활용할 수 있다.
    """

    def test_rebalancing_sell_before_buy(self):
        """
        목적: 리밸런싱 시 매도 pending_order가 먼저 생성되고, 그 예상 대금으로 매수됨을 검증.

        Given: QQQ 과비중(50%, target 40%), GLD 과소비중(30%, target 40%)
               shared_cash = 0 (매도 대금 없이는 매수 불가한 상태)
               total_equity = 1,000,000
        When:  _execute_rebalancing() 호출
        Then:  QQQ 매도 pending_order 생성 (100,000 감소 필요)
               GLD 매수 pending_order 생성 (100,000 증가 필요)
               GLD buy capital = estimated QQQ sell proceeds ≈ 100,000
        """
        # Given
        # QQQ: 50% (target 40%), SPY: 20% (target 20%, 변화 없음), GLD: 30% (target 40%)
        asset_states = {
            "qqq": _AssetState(position=125, signal_state="buy", pending_order=None, hold_state=None),
            "spy": _AssetState(position=100, signal_state="buy", pending_order=None, hold_state=None),
            "gld": _AssetState(position=75, signal_state="buy", pending_order=None, hold_state=None),
        }
        equity_vals = {
            "qqq": 500_000.0,  # 50% (target 40%) → 과비중 → 매도
            "spy": 200_000.0,  # 20% (target 20%) → 유지
            "gld": 300_000.0,  # 30% (target 40%) → 과소비중 → 매수
        }
        shared_cash = 0.0  # 현금 없음

        config = PortfolioConfig(
            experiment_name="test",
            display_name="Test",
            asset_slots=(
                AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), 0.40),
                AssetSlotConfig("spy", Path("dummy"), Path("dummy"), 0.20),
                AssetSlotConfig("gld", Path("dummy"), Path("dummy"), 0.40),
            ),
            total_capital=1_000_000.0,
            rebalance_threshold_rate=0.20,
            result_dir=Path("."),
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
            ma_type="ema",
        )

        # When
        _execute_rebalancing(asset_states, equity_vals, config, shared_cash, date(2024, 1, 2))

        # Then
        qqq_order = asset_states["qqq"].pending_order
        spy_order = asset_states["spy"].pending_order
        gld_order = asset_states["gld"].pending_order

        # QQQ 과비중 → 매도 pending_order
        assert qqq_order is not None, "QQQ 과비중이므로 매도 pending_order가 생성되어야 함"
        assert qqq_order.order_type == "sell"

        # SPY 정확히 target → pending_order 없음
        assert spy_order is None, "SPY는 정확히 target 비중이므로 pending_order가 없어야 함"

        # GLD 과소비중 + QQQ 매도 예상 대금 → 매수 pending_order
        assert gld_order is not None, "GLD 과소비중이므로 매수 pending_order가 생성되어야 함"
        assert gld_order.order_type == "buy"

        # GLD 매수 자본 = 예상 QQQ 매도 대금 ≈ 100,000 (shared_cash=0이므로)
        expected_gld_buy = 100_000.0  # QQQ 500k → 400k 축소 → 100k 매도 대금
        assert gld_order.capital == pytest.approx(
            expected_gld_buy, rel=0.01
        ), f"GLD 매수 자본이 QQQ 매도 예상 대금({expected_gld_buy:,.0f})과 같아야 함 (현재: {gld_order.capital:,.0f})"


# ============================================================================
# Phase 2: 엣지 케이스 테스트
# ============================================================================


class TestInvalidConfig:
    """잘못된 설정 검증 테스트."""

    def test_invalid_config_weight_sum_exceeds_one(self):
        """
        목적: target_weight 합이 1.0 초과 시 ValueError 발생 검증.

        Given: 두 자산, 각각 target_weight=0.60 → 합 = 1.20 > 1.0
        When:  run_portfolio_backtest() 호출
        Then:  ValueError 발생
        """
        # Given
        config = PortfolioConfig(
            experiment_name="test",
            display_name="Test",
            asset_slots=(
                AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), 0.60),
                AssetSlotConfig("spy", Path("dummy"), Path("dummy"), 0.60),
            ),
            total_capital=10_000_000.0,
            rebalance_threshold_rate=0.20,
            result_dir=Path("."),
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
            ma_type="ema",
        )

        # When & Then
        with pytest.raises(ValueError, match="target_weight"):
            run_portfolio_backtest(config)

    def test_invalid_config_duplicate_asset_id(self):
        """
        목적: asset_id 중복 시 ValueError 발생 검증.

        Given: asset_id="qqq"가 두 번 등장
        When:  run_portfolio_backtest() 호출
        Then:  ValueError 발생
        """
        # Given
        config = PortfolioConfig(
            experiment_name="test",
            display_name="Test",
            asset_slots=(
                AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), 0.30),
                AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), 0.30),  # 중복
            ),
            total_capital=10_000_000.0,
            rebalance_threshold_rate=0.20,
            result_dir=Path("."),
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
            ma_type="ema",
        )

        # When & Then
        with pytest.raises(ValueError, match="asset_id"):
            run_portfolio_backtest(config)


class TestNoOverlapPeriod:
    """공통 기간 없음 오류 테스트."""

    def test_no_overlap_period(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: 자산 간 공통 기간 없음 시 ValueError 발생 검증.

        Given: 자산 A: 2024-01 데이터, 자산 B: 2025-01 데이터 (겹침 없음)
        When:  run_portfolio_backtest() 호출
        Then:  ValueError 발생
        """
        from datetime import timedelta

        # Given: 날짜가 겹치지 않는 두 개의 데이터셋
        start_a = date(2024, 1, 2)
        dates_a: list[date] = []
        current = start_a
        for _ in range(10):
            while current.weekday() >= 5:
                current += timedelta(days=1)
            dates_a.append(current)
            current += timedelta(days=1)

        start_b = date(2025, 6, 2)
        dates_b: list[date] = []
        current = start_b
        for _ in range(10):
            while current.weekday() >= 5:
                current += timedelta(days=1)
            dates_b.append(current)
            current += timedelta(days=1)

        df_a = pd.DataFrame(
            {
                COL_DATE: dates_a,
                COL_OPEN: [100.0] * 10,
                COL_HIGH: [101.0] * 10,
                COL_LOW: [99.0] * 10,
                COL_CLOSE: [100.0] * 10,
                COL_VOLUME: [1_000_000] * 10,
            }
        )
        df_b = pd.DataFrame(
            {
                COL_DATE: dates_b,
                COL_OPEN: [200.0] * 10,
                COL_HIGH: [201.0] * 10,
                COL_LOW: [199.0] * 10,
                COL_CLOSE: [200.0] * 10,
                COL_VOLUME: [1_000_000] * 10,
            }
        )
        path_a = create_csv_file("asset_a.csv", df_a)
        path_b = create_csv_file("asset_b.csv", df_b)

        config = _make_portfolio_config(
            asset_paths={"a": (path_a, path_a), "b": (path_b, path_b)},
            result_dir=tmp_path,
            target_weights={"a": 0.50, "b": 0.50},
        )

        # When & Then
        with pytest.raises(ValueError):
            run_portfolio_backtest(config)


class TestSingleAssetPortfolio:
    """단일 자산 포트폴리오 정상 동작 테스트."""

    def test_single_asset_portfolio(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: 자산 1개 포트폴리오가 오류 없이 실행되어야 함.

        Given: GLD 100% 단일 자산 포트폴리오
        When:  run_portfolio_backtest() 실행
        Then:  PortfolioResult 반환, equity_df 존재, 오류 없음
        """
        # Given
        stock_df = _make_stock_df(n_rows=30)
        gld_path = create_csv_file("GLD_max.csv", stock_df)

        config = _make_portfolio_config(
            asset_paths={"gld": (gld_path, gld_path)},
            result_dir=tmp_path,
            target_weights={"gld": 1.0},
            ma_window=5,
        )

        # When
        result = run_portfolio_backtest(config)

        # Then
        assert result is not None
        assert isinstance(result.equity_df, pd.DataFrame)
        assert len(result.equity_df) > 0
        assert "equity" in result.equity_df.columns
        assert "cash" in result.equity_df.columns
        assert "gld_value" in result.equity_df.columns


class TestNoRebalancingAfterJustRebalanced:
    """리밸런싱 직후 같은 월에 재트리거 없음 테스트."""

    def test_rebalancing_not_triggered_after_just_rebalanced(self):
        """
        목적: 리밸런싱 직후 동일 자산이 여전히 임계값 내에 있으면 재트리거 없음.

        Given: 리밸런싱 실행 후 asset_states에 pending_order가 설정됨
               (pending_order 존재 = 이미 리밸런싱 중)
        When:  _check_rebalancing_needed() 호출
        Then:  pending_order가 있는 자산은 이미 조정 중이므로 정상 False 반환
               (pending_order 있는 경우는 _execute_rebalancing이 건너뜀)

        설계 참고: pending_order가 이미 있는 자산은 _execute_rebalancing에서
        new pending_order를 생성하지 않는다 (if pending_order is None 조건).
        """
        # Given: QQQ에 이미 pending_order 존재 (리밸런싱 중)
        existing_order = _PortfolioPendingOrder(order_type="sell", signal_date=date(2024, 1, 2), capital=0.0)
        asset_states = {
            "qqq": _AssetState(
                position=100,
                signal_state="buy",
                pending_order=existing_order,  # 이미 pending
                hold_state=None,
            )
        }
        equity_vals = {"qqq": 40_000.0}  # 40% (target 30%, 초과)
        config = _make_minimal_config("qqq", target_weight=0.30)

        # When: _execute_rebalancing 호출해도 pending_order 덮어쓰지 않음
        _execute_rebalancing(asset_states, equity_vals, config, 60_000.0, date(2024, 1, 5))

        # Then: 기존 pending_order가 유지됨 (덮어쓰기 없음)
        assert (
            asset_states["qqq"].pending_order is existing_order
        ), "이미 pending_order가 있는 자산은 새로운 pending_order로 덮어쓰지 않아야 함"


class TestC1FullCashOnSell:
    """C-1 포트폴리오 매도 시 전액 현금화 테스트."""

    def test_c1_full_cash_on_sell(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: QQQ+TQQQ 전량 매도 후 shared_cash ≈ total_capital 검증.

        Given: C-1 (QQQ 50% + TQQQ 50%), 전액 매수 후 sell signal 발생
        When:  run_portfolio_backtest() 실행 (buy → sell 전환 포함)
        Then:  sell signal 이후 gld_value, qqq_value = 0
               shared_cash가 total_capital 근방으로 복귀 (슬리피지 제외)
        """
        # Given: buy → sell 전환 데이터
        stock_df = _make_stock_df_with_sell(n_rows=60)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)
        tqqq_path = create_csv_file("TQQQ_synthetic_max.csv", stock_df)

        total_capital = 10_000_000.0
        config = _make_portfolio_config(
            asset_paths={
                "qqq": (qqq_path, qqq_path),
                "tqqq": (qqq_path, tqqq_path),  # 시그널 공유
            },
            result_dir=tmp_path,
            target_weights={"qqq": 0.50, "tqqq": 0.50},
            ma_window=5,
            hold_days=0,
            total_capital=total_capital,
        )

        # When
        result = run_portfolio_backtest(config)

        # Then: 마지막 행에서 두 자산 모두 포지션 = 0 (전액 현금화)
        last_row = result.equity_df.iloc[-1]
        assert last_row["qqq_value"] == pytest.approx(0.0, abs=0.01), "QQQ 매도 후 value = 0이어야 함"
        assert last_row["tqqq_value"] == pytest.approx(0.0, abs=0.01), "TQQQ 매도 후 value = 0이어야 함"

        # 매도 후 equity = cash (포지션 없으므로 전액 현금)
        assert last_row["equity"] == pytest.approx(last_row["cash"], abs=0.01), "매도 후 equity와 cash가 같아야 함 (전액 현금화)"

        # trades_df에 두 자산의 거래가 각각 존재해야 함
        trades = result.trades_df
        assert len(trades[trades["asset_id"] == "qqq"]) > 0, "QQQ 거래 내역이 있어야 함"
        assert len(trades[trades["asset_id"] == "tqqq"]) > 0, "TQQQ 거래 내역이 있어야 함"
