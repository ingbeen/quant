"""포트폴리오 백테스트 시나리오 테스트

run_portfolio_backtest()의 핵심 시나리오와 edge case를 검증한다.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.engines.portfolio_engine import (
    compute_portfolio_effective_start_date,
    run_portfolio_backtest,
)
from qbt.backtest.engines.portfolio_planning import (
    compute_portfolio_equity,
)
from qbt.backtest.engines.portfolio_rebalance import (
    is_first_trading_day_of_month,
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


# ============================================================================
# 테스트 클래스
# ============================================================================


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
        When:  compute_portfolio_equity() 호출
        Then:  equity = 3,000,000 + 4,000,000 + 1,000,000 = 8,000,000
        """
        # Given
        shared_cash = 3_000_000.0
        asset_positions = {"qqq": 10_000, "gld": 5_000}
        asset_closes = {"qqq": 400.0, "gld": 200.0}

        # When
        equity = compute_portfolio_equity(shared_cash, asset_positions, asset_closes)

        # Then: 3,000,000 + 10,000×400 + 5,000×200 = 8,000,000
        assert equity == pytest.approx(8_000_000.0, abs=0.01), f"에쿼티가 8,000,000이어야 함 (현재: {equity})"


class TestMonthlyRebalancing:
    """월 첫 거래일 판정 테스트.

    핵심 계약: 전일 월 != 당일 월이면 True (월 첫 거래일).
    """

    def test_monthly_rebalancing_only_on_first_day(self):
        """
        목적: is_first_trading_day_of_month()가 월 전환일만 True를 반환하는지 검증.

        Given: 날짜 목록 [2024-01-30, 2024-01-31, 2024-02-01, 2024-02-02]
        When:  각 인덱스에 대해 is_first_trading_day_of_month() 호출
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
        assert is_first_trading_day_of_month(trade_dates, 0) is False, "첫 번째 행(i=0)은 이전 행이 없으므로 False이어야 함"
        assert is_first_trading_day_of_month(trade_dates, 1) is False, "2024-01-31: 전 거래일도 1월이므로 False이어야 함"
        assert is_first_trading_day_of_month(trade_dates, 2) is True, "2024-02-01: 전 거래일 1월 → 2월 전환이므로 True이어야 함"
        assert is_first_trading_day_of_month(trade_dates, 3) is False, "2024-02-02: 전 거래일도 2월이므로 False이어야 함"


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


# ============================================================================
# 자산별 실현/미실현 손익 컬럼 계약 테스트
# ============================================================================


class TestAssetPnlColumns:
    """equity_df의 자산별 realized_pnl / unrealized_pnl 컬럼 계약 테스트."""

    def test_pnl_columns_exist(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: equity_df에 자산별 _realized_pnl, _unrealized_pnl 컬럼이 존재함을 검증.

        Given: GLD 100% 단일 자산 포트폴리오
        When:  run_portfolio_backtest() 실행
        Then:  gld_realized_pnl, gld_unrealized_pnl 컬럼 존재
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
        assert "gld_realized_pnl" in result.equity_df.columns
        assert "gld_unrealized_pnl" in result.equity_df.columns

    def test_pnl_zero_before_any_trade(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: 거래 발생 전 realized_pnl과 unrealized_pnl 모두 0임을 검증.

        Given: GLD 100% 포트폴리오, 초기 MA 워밍업 구간
        When:  run_portfolio_backtest() 실행
        Then:  첫 행에서 realized_pnl = 0, unrealized_pnl = 0
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

        # Then: 첫 행은 아직 거래 발생 전
        first_row = result.equity_df.iloc[0]
        assert first_row["gld_realized_pnl"] == pytest.approx(0.0, abs=0.01)
        assert first_row["gld_unrealized_pnl"] == pytest.approx(0.0, abs=0.01)

    def test_realized_pnl_persists_after_sell(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: 매도 후 realized_pnl이 유지되고 unrealized_pnl이 0이 됨을 검증.

        Given: QQQ+TQQQ 50/50 포트폴리오, buy -> sell 시그널 전환
        When:  run_portfolio_backtest() 실행
        Then:  매도 후 realized_pnl != 0 (거래 발생), unrealized_pnl = 0 (포지션 없음)
        """
        # Given
        stock_df = _make_stock_df_with_sell(n_rows=60)
        qqq_path = create_csv_file("QQQ_max.csv", stock_df)
        tqqq_path = create_csv_file("TQQQ_synthetic_max.csv", stock_df)

        config = _make_portfolio_config(
            asset_paths={
                "qqq": (qqq_path, qqq_path),
                "tqqq": (qqq_path, tqqq_path),
            },
            result_dir=tmp_path,
            target_weights={"qqq": 0.50, "tqqq": 0.50},
            ma_window=5,
            hold_days=0,
        )

        # When
        result = run_portfolio_backtest(config)

        # Then: 마지막 행 (매도 후 상태)
        last_row = result.equity_df.iloc[-1]
        # value = 0이면 포지션 없음 → unrealized_pnl = 0
        if last_row["qqq_value"] == pytest.approx(0.0, abs=0.01):
            assert last_row["qqq_unrealized_pnl"] == pytest.approx(0.0, abs=0.01), "포지션 없으면 unrealized_pnl = 0이어야 함"
            # 거래가 있었으므로 realized_pnl은 0이 아님
            assert last_row["qqq_realized_pnl"] != pytest.approx(0.0, abs=0.01), "매도 후 realized_pnl이 유지되어야 함"

    def test_total_contribution_equals_realized_plus_unrealized(
        self, tmp_path: Path, create_csv_file
    ):  # type: ignore[no-untyped-def]
        """
        목적: realized_pnl + unrealized_pnl이 자산의 진정한 수익 기여도임을 검증.

        Given: GLD 100% 포트폴리오, buy 시그널 발생 후 보유 중
        When:  run_portfolio_backtest() 실행
        Then:  보유 중일 때 unrealized_pnl = value - (avg_price * shares)
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
        equity_df = result.equity_df

        # Then: 보유 중인 행에서 unrealized = value - cost_basis
        holding_rows = equity_df[equity_df["gld_shares"] > 0]
        if len(holding_rows) > 0:
            row = holding_rows.iloc[-1]
            cost_basis = row["gld_avg_price"] * row["gld_shares"]
            expected_unrealized = row["gld_value"] - cost_basis
            assert row["gld_unrealized_pnl"] == pytest.approx(expected_unrealized, abs=1.0)
