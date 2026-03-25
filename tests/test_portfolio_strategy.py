"""포트폴리오 백테스트 엔진 테스트

핵심 계약/불변조건을 테스트로 고정한다.
engines/portfolio_engine.py의 이중 트리거, 부분 매도, strategy_type 분기를 검증한다.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.engines.portfolio_engine import (  # pyright: ignore[reportPrivateUsage]
    _AssetState,
    _check_rebalancing_needed,
    _compute_portfolio_equity,
    _execute_rebalancing,
    _is_first_trading_day_of_month,
    _PortfolioPendingOrder,
    compute_portfolio_effective_start_date,
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
        ma_window: 이동평균 기간 (슬롯 레벨 파라미터로 전달)
        hold_days: 유지일수 (슬롯 레벨 파라미터로 전달)
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


def _make_minimal_config(asset_id: str, target_weight: float) -> PortfolioConfig:
    """단일 자산 단위 테스트용 최소 PortfolioConfig를 생성한다."""
    return PortfolioConfig(
        experiment_name="test",
        display_name="Test",
        asset_slots=(AssetSlotConfig(asset_id, Path("dummy"), Path("dummy"), target_weight),),
        total_capital=100_000.0,
        result_dir=Path("."),
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
        asset_states = {"qqq": _AssetState(position=0, signal_state="buy", pending_order=None)}
        equity_vals = {"qqq": 36_000.0}  # 36_000 / 100_000 = 0.36
        config = _make_minimal_config("qqq", target_weight=0.30)

        # When
        result = _check_rebalancing_needed(asset_states, equity_vals, total_equity, config, threshold=0.20)

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
        asset_states = {"qqq": _AssetState(position=0, signal_state="buy", pending_order=None)}
        equity_vals = {"qqq": 36_100.0}  # 36_100 / 100_000 = 0.361
        config = _make_minimal_config("qqq", target_weight=0.30)

        # When
        result = _check_rebalancing_needed(asset_states, equity_vals, total_equity, config, threshold=0.20)

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
            "qqq": _AssetState(position=100, signal_state="buy", pending_order=None),
            "spy": _AssetState(position=0, signal_state="sell", pending_order=None),
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
            result_dir=Path("."),
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
            "A": _AssetState(position=0, signal_state="buy", pending_order=None),
            "B": _AssetState(position=0, signal_state="buy", pending_order=None),
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
            result_dir=Path("."),
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
            "qqq": _AssetState(position=125, signal_state="buy", pending_order=None),
            "spy": _AssetState(position=100, signal_state="buy", pending_order=None),
            "gld": _AssetState(position=75, signal_state="buy", pending_order=None),
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
            result_dir=Path("."),
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
            result_dir=Path("."),
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
            result_dir=Path("."),
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


# ============================================================================
# Phase 0: start_date 파라미터 계약 + compute_portfolio_effective_start_date 계약
# ============================================================================


class TestStartDateConstraint:
    """run_portfolio_backtest()의 start_date 파라미터 계약 테스트.

    핵심 계약:
    - start_date가 주어지면 equity_df의 첫 날짜가 start_date 이상이어야 한다.
    - start_date=None이면 기존 동작과 동일하다 (자연 시작일 사용).
    """

    def test_start_date_filters_early_data(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: start_date가 주어지면 equity_df가 해당 날짜 이후부터 시작함을 검증.

        Given: 2024-01-02부터 시작하는 50행 데이터
               start_date = 2024-02-01 (데이터 중간 날짜)
        When:  run_portfolio_backtest(config, start_date=start_date) 실행
        Then:  equity_df의 첫 날짜 >= start_date
        """
        # Given: 충분히 긴 데이터 (MA 워밍업 포함)
        stock_df = _make_stock_df(n_rows=50)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)

        config = _make_portfolio_config(
            asset_paths={"qqq": (qqq_path, qqq_path)},
            result_dir=tmp_path,
            target_weights={"qqq": 1.0},
            ma_window=5,
        )

        # 데이터 자연 시작일 이후 날짜 지정
        natural_result = run_portfolio_backtest(config)
        natural_start = natural_result.equity_df[COL_DATE].iloc[0]

        # natural_start보다 늦은 날짜를 start_date로 지정
        constrained_start = natural_start + timedelta(days=5)

        # When
        result = run_portfolio_backtest(config, start_date=constrained_start)

        # Then: equity_df 첫 날짜 >= constrained_start
        first_date = result.equity_df[COL_DATE].iloc[0]
        assert first_date >= constrained_start, (
            f"start_date={constrained_start} 지정 시 equity_df 첫 날짜({first_date})가 " f"start_date 이상이어야 함"
        )

    def test_start_date_none_uses_natural_start(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: start_date=None이면 기존 동작(자연 시작일)과 동일함을 검증.

        Given: 단일 자산 포트폴리오 config
        When:  run_portfolio_backtest(config, start_date=None) 실행
        Then:  start_date 미전달 시와 equity_df 첫 날짜가 동일
        """
        # Given
        stock_df = _make_stock_df(n_rows=30)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)

        config = _make_portfolio_config(
            asset_paths={"qqq": (qqq_path, qqq_path)},
            result_dir=tmp_path,
            target_weights={"qqq": 1.0},
            ma_window=5,
        )

        # When
        result_no_date = run_portfolio_backtest(config)
        result_none = run_portfolio_backtest(config, start_date=None)

        # Then: 두 결과의 첫 날짜가 동일해야 함
        first_date_no = result_no_date.equity_df[COL_DATE].iloc[0]
        first_date_none = result_none.equity_df[COL_DATE].iloc[0]
        assert first_date_no == first_date_none, (
            f"start_date=None과 미전달 시 첫 날짜가 동일해야 함 " f"(미전달={first_date_no}, None={first_date_none})"
        )


class TestComputeEffectiveStartDate:
    """compute_portfolio_effective_start_date() 계약 테스트.

    핵심 계약:
    - 반환값이 date 객체이어야 한다.
    - 반환된 날짜가 MA 워밍업 완료 이후(데이터의 ma_window번째 이후)이어야 한다.
    """

    def test_returns_date_object(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: compute_portfolio_effective_start_date()가 date 객체를 반환함을 검증.

        Given: 단일 자산 포트폴리오 config
        When:  compute_portfolio_effective_start_date(config) 호출
        Then:  반환값이 datetime.date 인스턴스
        """
        # Given
        stock_df = _make_stock_df(n_rows=30)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)

        config = _make_portfolio_config(
            asset_paths={"qqq": (qqq_path, qqq_path)},
            result_dir=tmp_path,
            target_weights={"qqq": 1.0},
            ma_window=5,
        )

        # When
        result = compute_portfolio_effective_start_date(config)

        # Then
        assert isinstance(result, date), f"반환값이 date 객체이어야 함 (현재: {type(result)})"

    def test_effective_start_matches_backtest_start(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: compute_portfolio_effective_start_date()가 run_portfolio_backtest()의
              equity_df 첫 날짜와 동일함을 검증.

        Given: ma_window=5 (SMA, NaN 워밍업이 발생하는 유형) n_rows=20 데이터
        When:  compute_portfolio_effective_start_date(config) 호출
        Then:  반환 날짜 == run_portfolio_backtest()의 equity_df 첫 날짜
               SMA 사용 시 반환 날짜가 데이터 시작일보다 이후 (ma_window-1 행은 NaN)
        """
        # Given: SMA 타입 사용 (처음 window-1 행이 NaN → 워밍업 발생)
        stock_df = _make_stock_df(n_rows=20)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)
        data_start = stock_df[COL_DATE].iloc[0]

        # ma_type="sma"로 명시 (SMA는 처음 window-1행이 NaN → 워밍업 기간 명확)
        config = PortfolioConfig(
            experiment_name="test_sma",
            display_name="Test SMA",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="qqq",
                    signal_data_path=qqq_path,
                    trade_data_path=qqq_path,
                    target_weight=1.0,
                    ma_window=5,
                    ma_type="sma",  # SMA: 처음 4행(window-1=4)이 NaN
                ),
            ),
            total_capital=10_000_000.0,
            result_dir=tmp_path,
        )

        # When
        effective_start = compute_portfolio_effective_start_date(config)

        # Then 1: SMA 워밍업으로 유효 시작일이 데이터 시작일보다 이후이어야 함
        assert effective_start > data_start, f"SMA 워밍업으로 유효 시작일({effective_start})이 " f"데이터 시작일({data_start})보다 이후여야 함"

        # Then 2: run_portfolio_backtest()의 equity_df 첫 날짜와 일치해야 함 (핵심 계약)
        result = run_portfolio_backtest(config)
        backtest_start = result.equity_df[COL_DATE].iloc[0]
        assert effective_start == backtest_start, (
            f"compute_portfolio_effective_start_date({effective_start})와 "
            f"run_portfolio_backtest 첫 날짜({backtest_start})가 동일해야 함"
        )


# ============================================================================
# always_invested 기능 테스트
# ============================================================================


def _make_flat_price_df(n_rows: int = 20, price: float = 100.0) -> pd.DataFrame:
    """가격이 고정된 합성 주식 데이터를 생성한다.

    always_invested 테스트 목적:
    - buy_buffer=0.03 → upper_band = MA * 1.03 ≈ 103
    - price=100 → upper_band(103)을 절대 돌파하지 않음 → 버퍼존 매수 신호 없음
    - always_invested=True라면 신호 없이도 즉시 매수 가능
    """
    start = date(2024, 1, 2)
    dates: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)

    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [price - 0.1] * n_rows,
            COL_HIGH: [price + 0.1] * n_rows,
            COL_LOW: [price - 0.1] * n_rows,
            COL_CLOSE: [price] * n_rows,
            COL_VOLUME: [1_000_000] * n_rows,
        }
    )


def _make_sell_signal_df(n_rows: int = 20, initial_price: float = 100.0, drop_price: float = 80.0) -> pd.DataFrame:
    """초반 고가→후반 저가(매도 신호 구간)를 포함한 합성 데이터를 생성한다.

    - 처음 5행: initial_price (MA ≈ initial_price, lower_band = initial_price * 0.95 = 95)
    - 나머지: drop_price = 80 (lower_band 95 하향 돌파 → 버퍼존 매도 신호)
    """
    start = date(2024, 1, 2)
    dates: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)

    closes = [initial_price] * 5 + [drop_price] * (n_rows - 5)
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [c - 0.1 for c in closes],
            COL_HIGH: [c + 0.1 for c in closes],
            COL_LOW: [c - 0.1 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * n_rows,
        }
    )


class TestStrategyTypeBehavior:
    """strategy_type 동작 통합 테스트.

    검증 정책:
    1. strategy_type="buy_and_hold": 버퍼존 매수 신호 없이도 day 1에 즉시 매수
    2. strategy_type="buy_and_hold": 매도 신호 발생 시에도 포지션 유지
    3. strategy_type="buffer_zone"(기본값): 매수 신호 없으면 절대 매수하지 않음
    4. AssetSlotConfig 기본값: strategy_type="buffer_zone"
    """

    def test_buy_and_hold_buys_immediately(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: strategy_type="buy_and_hold" 자산이 버퍼존 매수 신호 없이도 즉시 매수됨을 검증.

        Given:
            - 가격 100 고정 → upper_band(103) 돌파 없음 → 버퍼존 매수 신호 없음
            - strategy_type="buy_and_hold" 자산 슬롯 (target_weight=1.0)

        When: run_portfolio_backtest() 실행

        Then:
            - 마지막 날 {asset_id}_value > 0 (즉시 매수 후 포지션 유지)
        """
        # Given: 가격 100 고정 (upper_band=103 돌파 없음 → 버퍼존 신호 없음)
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_always.csv", df)

        config_true = PortfolioConfig(
            experiment_name="test_always_true",
            display_name="Test Always True",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_a",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_type="buy_and_hold",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "always_true",
        )

        # When
        result = run_portfolio_backtest(config_true)

        # Then: 마지막 날 포지션 보유 (매수 신호 없어도 항상 투자)
        equity_df = result.equity_df
        last_value = float(equity_df["asset_a_value"].iloc[-1])
        assert last_value > 0, f"strategy_type='buy_and_hold' 자산은 마지막 날 포지션을 보유해야 함, 실제: {last_value}"

    def test_buffer_zone_does_not_buy_without_signal(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: strategy_type="buffer_zone"(기본값)이면 버퍼존 신호 없이 절대 매수하지 않음을 검증.

        Given:
            - 가격 100 고정 → upper_band(103) 돌파 없음 → 버퍼존 매수 신호 없음
            - strategy_type="buffer_zone" (기본 버퍼존 전략)

        When: run_portfolio_backtest() 실행

        Then:
            - 전체 기간 {asset_id}_value = 0 (매수 신호 없어서 포지션 없음)
            - trades_df가 비어있음
        """
        # Given: 동일 가격 데이터, strategy_type="buffer_zone"(기본값)
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_normal.csv", df)

        config_false = PortfolioConfig(
            experiment_name="test_always_false",
            display_name="Test Always False",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_b",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_type="buffer_zone",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "always_false",
        )

        # When
        result = run_portfolio_backtest(config_false)

        # Then: 전체 기간 포지션 없음
        equity_df = result.equity_df
        assert (equity_df["asset_b_value"] == 0).all(), "strategy_type='buffer_zone' 자산은 매수 신호 없이 포지션을 가지면 안 됨"
        assert result.trades_df.empty, "strategy_type='buffer_zone' 자산은 신호 없으면 거래가 없어야 함"

    def test_buy_and_hold_does_not_sell_on_signal(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: strategy_type="buy_and_hold" 자산이 매도 신호(하단 밴드 하향 돌파)에도 매도하지 않음을 검증.

        Given:
            - 처음 5행: 가격 100 (MA ≈ 100, lower_band = 95)
            - 이후 15행: 가격 80 (lower_band 95 하향 돌파 → 버퍼존 매도 신호 발생)
            - strategy_type="buy_and_hold"

        When: run_portfolio_backtest() 실행

        Then:
            - 마지막 날 {asset_id}_value > 0 (매도하지 않고 포지션 유지)
            - trades_df가 비어있음 (완료된 매도 거래 없음)
        """
        # Given: 초반 100 → 후반 80 (매도 신호 발생 구간)
        df = _make_sell_signal_df(n_rows=20, initial_price=100.0, drop_price=80.0)
        csv_path = create_csv_file("asset_sell_signal.csv", df)

        config = PortfolioConfig(
            experiment_name="test_no_sell",
            display_name="Test No Sell",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_c",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_type="buy_and_hold",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "no_sell",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then: 마지막 날 포지션 보유 (매도 신호 무시)
        equity_df = result.equity_df
        last_value = float(equity_df["asset_c_value"].iloc[-1])
        assert last_value > 0, f"strategy_type='buy_and_hold' 자산은 매도 신호에도 포지션을 유지해야 함, 실제: {last_value}"

        # 완료된 거래(entry + exit) 없음
        assert result.trades_df.empty, (
            f"strategy_type='buy_and_hold' 자산은 매도 기록이 없어야 함, " f"실제 거래 수: {len(result.trades_df)}"
        )

    def test_strategy_type_default_is_buffer_zone(self, tmp_path: Path) -> None:
        """
        목적: AssetSlotConfig.strategy_type 기본값이 "buffer_zone"임을 검증.

        Given: strategy_type 파라미터 없이 AssetSlotConfig 생성
        When:  AssetSlotConfig 인스턴스 생성
        Then:  strategy_type == "buffer_zone"
        """
        # Given/When: strategy_type 명시 없이 생성
        slot = AssetSlotConfig(
            asset_id="test",
            signal_data_path=tmp_path / "dummy.csv",
            trade_data_path=tmp_path / "dummy.csv",
            target_weight=0.50,
        )

        # Then: 기본값 "buffer_zone"
        assert (
            slot.strategy_type == "buffer_zone"
        ), f"AssetSlotConfig.strategy_type 기본값은 'buffer_zone'이어야 함, 실제: {slot.strategy_type}"

    def test_params_json_includes_strategy_type_flag(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: params_json에 strategy_type 필드가 포함됨을 검증.

        Given: strategy_type="buy_and_hold" 자산을 포함한 포트폴리오 config
        When:  run_portfolio_backtest() 실행
        Then:  result.params_json["assets"][0]["strategy_type"] == "buy_and_hold"
        """
        # Given
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_json.csv", df)

        config = PortfolioConfig(
            experiment_name="test_params_json",
            display_name="Test Params JSON",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_d",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_type="buy_and_hold",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "params_json",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then: params_json에 strategy_type 포함
        assets_json = result.params_json.get("assets", [])
        assert len(assets_json) == 1, "자산이 1개이어야 함"
        assert "strategy_type" in assets_json[0], "params_json[assets][0]에 strategy_type 키가 있어야 함"
        assert assets_json[0]["strategy_type"] == "buy_and_hold", (
            f"strategy_type='buy_and_hold'가 params_json에 반영되어야 함, " f"실제: {assets_json[0].get('strategy_type')}"
        )


# ============================================================================
# Phase 0: 새로운 계약 고정 (레드 허용)
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
        목적: _execute_rebalancing() 후 초과 자산의
              pending_order.rebalance_sell_amount == excess_value 검증.

        Given: QQQ 60%(target 40%), total_equity=1,000,000, shared_cash=400,000
               excess_value = 600,000 - 400,000 = 200,000
        When:  _execute_rebalancing() 호출
        Then:  QQQ pending_order.rebalance_sell_amount == 200,000 (초과분, 전량 아님)
        """
        # Given
        asset_states: dict[str, _AssetState] = {
            "qqq": _AssetState(position=150, signal_state="buy", pending_order=None),
        }
        equity_vals = {"qqq": 600_000.0}
        shared_cash = 400_000.0  # total = 1,000,000

        config = PortfolioConfig(
            experiment_name="test",
            display_name="Test",
            asset_slots=(AssetSlotConfig("qqq", Path("dummy"), Path("dummy"), 0.40),),
            total_capital=1_000_000.0,
            result_dir=Path("."),
        )

        # When
        _execute_rebalancing(asset_states, equity_vals, config, shared_cash, date(2024, 1, 2))

        # Then
        order = asset_states["qqq"].pending_order
        assert order is not None
        assert order.order_type == "sell"
        # rebalance_sell_amount = 600,000 - 400,000 = 200,000 (전량 아닌 초과분)
        assert order.rebalance_sell_amount == pytest.approx(200_000.0, rel=1e-6)  # type: ignore[attr-defined]

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


class TestDualTriggerThreshold:
    """이중 트리거 임계값 계약 테스트 (Phase 0: RED).

    핵심 계약:
    - MONTHLY_REBALANCE_THRESHOLD_RATE = 0.10 (월 첫날 임계값)
    - DAILY_REBALANCE_THRESHOLD_RATE = 0.20 (매일 임계값)
    - _check_rebalancing_needed()에 threshold 파라미터 지원
    - 10%~20% 편차 구간: 월 첫날에만 트리거, 일중에는 패스
    """

    def test_monthly_threshold_constants_exist(self) -> None:
        """
        목적: MONTHLY_REBALANCE_THRESHOLD_RATE, DAILY_REBALANCE_THRESHOLD_RATE 상수 존재 및 값 검증.

        Given: qbt.backtest.engines.portfolio_engine 모듈
        When:  두 상수 import
        Then:  MONTHLY_REBALANCE_THRESHOLD_RATE == 0.10
               DAILY_REBALANCE_THRESHOLD_RATE == 0.20
        """
        from qbt.backtest.engines.portfolio_engine import (
            DAILY_REBALANCE_THRESHOLD_RATE,
            MONTHLY_REBALANCE_THRESHOLD_RATE,
        )

        assert MONTHLY_REBALANCE_THRESHOLD_RATE == pytest.approx(0.10, abs=1e-9)
        assert DAILY_REBALANCE_THRESHOLD_RATE == pytest.approx(0.20, abs=1e-9)

    def test_check_rebalancing_monthly_threshold_triggers_at_11pct(self) -> None:
        """
        목적: threshold=0.10(월 첫날 임계값) 기준, 편차 11%에서 트리거됨을 검증.

        Given: target=0.30, actual=0.333 → |0.333/0.30 - 1| ≈ 0.11 > 0.10
               threshold=0.10 (MONTHLY_REBALANCE_THRESHOLD_RATE)
        When:  _check_rebalancing_needed(..., threshold=0.10)
        Then:  True (월 임계값 초과 → 트리거)
        """
        # Given
        asset_states: dict[str, _AssetState] = {"qqq": _AssetState(position=0, signal_state="buy", pending_order=None)}
        equity_vals = {"qqq": 33_300.0}  # 33.3% (target 30%, |33.3/30-1| ≈ 0.11)
        config = _make_minimal_config("qqq", target_weight=0.30)

        # When
        result = _check_rebalancing_needed(asset_states, equity_vals, 100_000.0, config, threshold=0.10)  # type: ignore[call-arg]

        # Then
        assert result is True, "편차 11% > 월 임계값 10%이면 트리거되어야 함"

    def test_check_rebalancing_daily_no_trigger_at_15pct(self) -> None:
        """
        목적: threshold=0.20(매일 임계값) 기준, 편차 15%에서 트리거 없음을 검증.

        Given: target=0.30, actual=0.345 → |0.345/0.30 - 1| = 0.15 < 0.20
               threshold=0.20 (DAILY_REBALANCE_THRESHOLD_RATE)
        When:  _check_rebalancing_needed(..., threshold=0.20)
        Then:  False (월 중간 임계값 미달 → 패스)
        """
        # Given
        asset_states: dict[str, _AssetState] = {"qqq": _AssetState(position=0, signal_state="buy", pending_order=None)}
        equity_vals = {"qqq": 34_500.0}  # 34.5% (target 30%, |34.5/30-1| = 0.15)
        config = _make_minimal_config("qqq", target_weight=0.30)

        # When
        result = _check_rebalancing_needed(asset_states, equity_vals, 100_000.0, config, threshold=0.20)  # type: ignore[call-arg]

        # Then
        assert result is False, "편차 15% < 매일 임계값 20%이면 트리거 없어야 함"

    def test_check_rebalancing_monthly_no_trigger_below_10pct(self) -> None:
        """
        목적: threshold=0.10(월 임계값) 기준, 편차 9%에서 트리거 없음을 검증.

        Given: target=0.30, actual=0.327 → |0.327/0.30 - 1| = 0.09 < 0.10
        When:  _check_rebalancing_needed(..., threshold=0.10)
        Then:  False (편차 < 월 임계값 → 패스)
        """
        # Given
        asset_states: dict[str, _AssetState] = {"qqq": _AssetState(position=0, signal_state="buy", pending_order=None)}
        equity_vals = {"qqq": 32_700.0}  # 32.7% (target 30%, |32.7/30-1| = 0.09)
        config = _make_minimal_config("qqq", target_weight=0.30)

        # When
        result = _check_rebalancing_needed(asset_states, equity_vals, 100_000.0, config, threshold=0.10)  # type: ignore[call-arg]

        # Then
        assert result is False, "편차 9% < 월 임계값 10%이면 트리거 없어야 함"


class TestStrategyType:
    """strategy_type 기능 계약 테스트 (Phase 0: RED).

    핵심 계약:
    1. AssetSlotConfig.strategy_type 기본값 == "buffer_zone"
    2. strategy_type="buy_and_hold": 버퍼존 신호 없이 즉시 매수
    3. strategy_type="buy_and_hold": 매도 신호에도 포지션 유지
    4. params_json에 strategy_type 키 포함
    """

    def test_strategy_type_default_is_buffer_zone(self) -> None:
        """
        목적: AssetSlotConfig.strategy_type 기본값이 "buffer_zone"임을 검증.

        Given: strategy_type 명시 없이 AssetSlotConfig 생성
        When:  .strategy_type 속성 조회
        Then:  "buffer_zone"
        """
        # Given/When
        slot = AssetSlotConfig(
            asset_id="test",
            signal_data_path=Path("dummy"),
            trade_data_path=Path("dummy"),
            target_weight=0.50,
        )

        # Then
        assert slot.strategy_type == "buffer_zone"  # type: ignore[attr-defined]

    def test_strategy_type_buy_and_hold_buys_immediately(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: strategy_type="buy_and_hold" 자산이 버퍼존 신호 없이 즉시 매수됨을 검증.

        Given: 가격 100 고정 → upper_band(103) 돌파 없음 → 버퍼존 매수 신호 없음
               strategy_type="buy_and_hold"
        When:  run_portfolio_backtest() 실행
        Then:  마지막 날 value > 0 (즉시 매수 후 포지션 유지)
        """
        # Given
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_bnh.csv", df)

        config = PortfolioConfig(
            experiment_name="test_bnh",
            display_name="Test B&H",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_bnh",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_type="buy_and_hold",  # type: ignore[call-arg]
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "bnh",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then
        last_value = float(result.equity_df["asset_bnh_value"].iloc[-1])
        assert last_value > 0, f"strategy_type='buy_and_hold' 자산은 즉시 매수되어야 함, 실제: {last_value}"

    def test_strategy_type_buy_and_hold_ignores_sell_signal(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: strategy_type="buy_and_hold" 자산이 매도 신호에도 포지션 유지됨을 검증.

        Given: 처음 5행 100 → 이후 80 (매도 신호 발생)
               strategy_type="buy_and_hold"
        When:  run_portfolio_backtest() 실행
        Then:  마지막 날 value > 0 (매도 신호 무시)
               trades_df 비어있음 (완료된 매도 거래 없음)
        """
        # Given
        df = _make_sell_signal_df(n_rows=20, initial_price=100.0, drop_price=80.0)
        csv_path = create_csv_file("asset_bnh_sell.csv", df)

        config = PortfolioConfig(
            experiment_name="test_bnh_sell",
            display_name="Test B&H Sell",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_bnh_s",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_type="buy_and_hold",  # type: ignore[call-arg]
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "bnh_sell",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then
        last_value = float(result.equity_df["asset_bnh_s_value"].iloc[-1])
        assert last_value > 0, "strategy_type='buy_and_hold' 자산은 매도 신호에도 포지션을 유지해야 함"
        assert result.trades_df.empty, "strategy_type='buy_and_hold' 자산은 완료된 매도 기록이 없어야 함"

    def test_params_json_includes_strategy_type(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: params_json에 strategy_type 필드가 포함됨을 검증.

        Given: strategy_type="buy_and_hold" 자산 포함 config
        When:  run_portfolio_backtest() 실행
        Then:  result.params_json["assets"][0]["strategy_type"] == "buy_and_hold"
        """
        # Given
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_pj.csv", df)

        config = PortfolioConfig(
            experiment_name="test_params_json_st",
            display_name="Test Params JSON ST",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_pj",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_type="buy_and_hold",  # type: ignore[call-arg]
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "params_json_st",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then
        assets_json = result.params_json.get("assets", [])
        assert len(assets_json) == 1
        assert "strategy_type" in assets_json[0], "params_json[assets][0]에 strategy_type 키가 있어야 함"
        assert assets_json[0]["strategy_type"] == "buy_and_hold"


# ============================================================================
# Phase 0: 버그 재현 테스트 (RED — 수정 전에는 실패해야 정상)
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


class TestCacheKeyWithDifferentMAParams:
    """signal cache key 충돌 방지 계약 테스트 (Phase 0 RED).

    핵심 계약:
    - 동일 signal_data_path를 공유하는 슬롯이 서로 다른 ma_window를 사용해도
      각자 올바른 MA 컬럼을 가진 signal_df를 사용해야 한다.
    - 수정 전에는 캐시 키가 경로만이므로 나중 슬롯이 잘못된 MA 컬럼을 참조 → 실패.
    """

    def test_same_path_different_ma_window_no_collision(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: 동일 signal_data_path + 다른 ma_window 슬롯이 각자 올바른 MA 컬럼 사용 검증.

        Given: 두 슬롯이 같은 qqq_path를 signal 소스로 공유하되
               슬롯 A는 ma_window=5, 슬롯 B는 ma_window=10 사용
        When:  run_portfolio_backtest() 실행
        Then:  예외 없이 완료, 각 슬롯이 자기 MA 컬럼(ma_5 / ma_10)을 사용

        RED 사유: 현재 캐시 키 = str(signal_data_path)만 사용 → 슬롯 A의 ma_5 계산 결과가
                  슬롯 B에 재사용 → 슬롯 B가 ma_10 컬럼을 찾지 못함 → KeyError 발생.
        """
        # Given: 두 슬롯 모두 같은 CSV를 signal 소스로 사용하되 ma_window가 다름
        stock_df = _make_stock_df(n_rows=30)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)

        config = PortfolioConfig(
            experiment_name="test_cache_collision",
            display_name="Test Cache Collision",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="slot_a",
                    signal_data_path=qqq_path,
                    trade_data_path=qqq_path,
                    target_weight=0.50,
                    ma_window=5,  # ma_5 컬럼
                ),
                AssetSlotConfig(
                    asset_id="slot_b",
                    signal_data_path=qqq_path,  # 동일 경로
                    trade_data_path=qqq_path,
                    target_weight=0.50,
                    ma_window=10,  # ma_10 컬럼 (현재 캐시 충돌 → 없는 컬럼 참조)
                ),
            ),
            total_capital=10_000_000.0,
            result_dir=tmp_path,
        )

        # When & Then: 예외 없이 실행 완료해야 함
        # 현재 버그: KeyError (ma_10 컬럼이 캐시된 signal_df에 없음)
        result = run_portfolio_backtest(config)
        assert result is not None, "캐시 키 충돌 없이 정상 실행되어야 함"
        assert isinstance(result.equity_df, pd.DataFrame)
        assert len(result.equity_df) > 0


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
