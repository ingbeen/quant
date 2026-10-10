"""포트폴리오 백테스트 시나리오 테스트

run_portfolio_backtest()의 핵심 시나리오와 edge case를 검증한다.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.backtest.engines.portfolio_engine import (
    compute_portfolio_effective_start_date,
    run_portfolio_backtest,
)
from qbt.backtest.engines.portfolio_planning import (
    compute_portfolio_equity,
)
from qbt.backtest.engines.portfolio_rebalance import (
    is_last_trading_day_of_month,
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

    def test_qqq_tqqq_shared_signal(self, tmp_path: Path, create_csv_file):
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


class TestMonthEndRebalanceCheckDay:
    """리밸런싱 판단일(월 마지막 거래일) 판정 테스트.

    핵심 계약: 다음 거래일의 월이 바뀌면 True (그 달의 마지막 거래일).
    다음 거래일이 없는 마지막 행은 체결할 날이 없으므로 False.
    """

    def test_true_only_on_last_trading_day_of_month(self):
        """
        목적: is_last_trading_day_of_month()가 달의 마지막 거래일만 True를 반환하는지 검증.

        Given: 날짜 목록 [2024-01-30, 2024-01-31, 2024-02-01, 2024-02-02]
        When:  인덱스 0 ~ 2 에 대해 is_last_trading_day_of_month() 호출
        Then:  인덱스 0 (2024-01-30) → False (다음 거래일도 1월)
               인덱스 1 (2024-01-31) → True  (다음 거래일이 2월)
               인덱스 2 (2024-02-01) → False (다음 거래일도 2월)
        """
        # Given
        trade_dates = [
            date(2024, 1, 30),
            date(2024, 1, 31),
            date(2024, 2, 1),
            date(2024, 2, 2),
        ]

        # When & Then
        assert is_last_trading_day_of_month(trade_dates, 0) is False, "2024-01-30: 다음 거래일도 1월이므로 False이어야 함"
        assert is_last_trading_day_of_month(trade_dates, 1) is True, "2024-01-31: 다음 거래일이 2월이므로 True이어야 함"
        assert is_last_trading_day_of_month(trade_dates, 2) is False, "2024-02-01: 다음 거래일도 2월이므로 False이어야 함"

    def test_last_row_is_false(self):
        """
        목적: 데이터의 마지막 행은 달력상 월말이어도 False 임을 검증 (체결할 다음 거래일이 없다).

        Given: 날짜 목록 [2024-01-30, 2024-01-31] (1월 31일에서 데이터 종료)
        When:  마지막 인덱스 1 에 대해 is_last_trading_day_of_month() 호출
        Then:  False
        """
        # Given
        trade_dates = [date(2024, 1, 30), date(2024, 1, 31)]

        # When & Then
        assert is_last_trading_day_of_month(trade_dates, 1) is False, "마지막 행은 다음 거래일이 없으므로 False이어야 함"

    def test_true_when_next_row_is_same_month_of_later_year(self):
        """
        목적: 데이터가 비어 이웃한 두 거래일이 정확히 12개월 떨어져도 판단일을 놓치지 않음을 검증
              (월만 비교하면 같은 3월로 보여 False 가 된다).

        Given: 날짜 목록 [2008-03-28, 2008-03-31, 2009-03-02]
        When:  인덱스 1 (2008-03-31) 에 대해 is_last_trading_day_of_month() 호출
        Then:  True (다음 거래일이 다른 해의 3월)
        """
        # Given
        trade_dates = [date(2008, 3, 28), date(2008, 3, 31), date(2009, 3, 2)]

        # When & Then
        assert is_last_trading_day_of_month(trade_dates, 1) is True, "2008-03-31 다음 거래일이 2009-03 이므로 True이어야 함"

    @pytest.mark.parametrize("index", [-1, 3])
    def test_out_of_range_index_raises(self, index: int):
        """
        목적: 범위 밖 인덱스를 조용히 False 로 처리하지 않고 ValueError 로 알림을 검증.

        Given: 날짜 3개
        When:  인덱스 -1 또는 3(길이) 으로 호출
        Then:  ValueError
        """
        # Given
        trade_dates = [date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 1)]

        # When & Then
        with pytest.raises(ValueError, match="인덱스"):
            is_last_trading_day_of_month(trade_dates, index)


def _make_jump_df(jump_date: date, price_before: float, price_after: float) -> pd.DataFrame:
    """2024-01-02 ~ 2024-02-29 평일 데이터. jump_date 부터 시가·종가가 price_after 로 바뀐다."""
    dates: list[date] = []
    current = date(2024, 1, 2)
    while current <= date(2024, 2, 29):
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)

    closes = [price_after if d >= jump_date else price_before for d in dates]
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: closes,
            COL_HIGH: [c + 1.0 for c in closes],
            COL_LOW: [c - 1.0 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * len(dates),
        }
    )


class TestMonthEndRebalanceSchedule:
    """엔진의 리밸런싱 시점 계약 테스트.

    핵심 계약: 리밸런싱은 월 마지막 거래일 종가로 판단해 다음 거래일 시가에 체결한다.
    월중에는 편차가 아무리 커도 리밸런싱하지 않는다 (평일 긴급 리밸런싱 없음).

    시나리오: 보유(B&H) 자산 a·b 50:50. a 가 2024-01-15 시가부터 100 → 160 (+60%).
    a 비중 ≈ 0.8 / 1.3 = 0.615, 목표 대비 상대 편차 ≈ 23% — 판단 임계값 10% 의 두 배를 넘는 큰 이탈.
    """

    def _run(self, tmp_path: Path, create_csv_file, a_price_after: float = 160.0):
        a_path = create_csv_file("A_max.csv", _make_jump_df(date(2024, 1, 15), 100.0, a_price_after))
        b_path = create_csv_file("B_max.csv", _make_jump_df(date(2024, 1, 15), 100.0, 100.0))
        config = PortfolioConfig(
            experiment_name="test_month_end",
            display_name="Test Month End",
            asset_slots=(
                AssetSlotConfig("a", a_path, a_path, target_weight=0.50, strategy_id="buy_and_hold"),
                AssetSlotConfig("b", b_path, b_path, target_weight=0.50, strategy_id="buy_and_hold"),
            ),
            total_capital=10_000_000.0,
            result_dir=tmp_path,
        )
        return run_portfolio_backtest(config)

    def test_rebalances_only_on_next_day_after_month_end(self, tmp_path: Path, create_csv_file):
        """
        목적: 월중 편차가 20% 를 넘어도 그 달에는 리밸런싱하지 않고,
              월 마지막 거래일(2024-01-31) 판단 → 다음 거래일(2024-02-01) 한 번만 체결됨을 검증.

        Given: a 가 2024-01-15 에 +60% (상대 편차 약 23%)
        When:  run_portfolio_backtest() 실행
        Then:  rebalanced=True 인 날짜 == [2024-02-01]
        """
        # When
        result = self._run(tmp_path, create_csv_file)

        # Then
        equity_df = result.equity_df
        rebalanced_dates = list(equity_df.loc[equity_df["rebalanced"], COL_DATE])
        assert rebalanced_dates == [date(2024, 2, 1)], f"리밸런싱은 2024-02-01 하루뿐이어야 함 (실제: {rebalanced_dates})"

    def test_no_rebalance_on_month_end_within_threshold(self, tmp_path: Path, create_csv_file):
        """
        목적: 판단일이어도 편차가 임계값 10% 이하이면 리밸런싱하지 않음을 엔진 수준에서 검증
              (판단일마다 무조건 맞추는 규칙과 구분된다).

        Given: a 가 2024-01-15 에 +15% → a 비중 ≈ 0.575 / 1.075 = 0.535, 상대 편차 ≈ 7%
        When:  run_portfolio_backtest() 실행
        Then:  rebalanced=True 인 날이 없다
        """
        # When
        result = self._run(tmp_path, create_csv_file, a_price_after=115.0)

        # Then
        equity_df = result.equity_df
        rebalanced_dates = list(equity_df.loc[equity_df["rebalanced"], COL_DATE])
        assert rebalanced_dates == [], f"편차 7% 는 임계값 10% 이하이므로 리밸런싱이 없어야 함 (실제: {rebalanced_dates})"

    def test_check_day_logged_on_month_end(self, tmp_path: Path, create_csv_file):
        """
        목적: state_log 의 판단일 컬럼이 월 마지막 거래일에만 True 임을 검증.

        Given: 2024-01-02 ~ 2024-02-29 데이터 (2024-02-29 는 데이터 마지막 행)
        When:  run_portfolio_backtest() 실행
        Then:  is_month_end=True 인 날짜 == [2024-01-31]
        """
        # When
        result = self._run(tmp_path, create_csv_file)

        # Then
        state_log_df = result.state_log_df
        check_days = list(state_log_df.loc[state_log_df["is_month_end"], COL_DATE])
        assert check_days == [date(2024, 1, 31)], f"판단일은 2024-01-31 하루뿐이어야 함 (실제: {check_days})"

    def test_rebalance_sell_executes_at_next_day_open(self, tmp_path: Path, create_csv_file):
        """
        목적: 리밸런싱 매도가 판단 다음 거래일 시가 × (1 - 슬리피지)로 체결됨을 검증.

        Given: a 의 2024-02-01 시가 = 160
        When:  run_portfolio_backtest() 실행
        Then:  a 의 REDUCE 매도 체결가 == 160 × (1 - SLIPPAGE_RATE), 체결일 2024-02-01
        """
        # When
        result = self._run(tmp_path, create_csv_file)

        # Then
        trades_df = result.trades_df
        a_sells = trades_df[(trades_df["asset_id"] == "a") & (trades_df["trade_type"] == "rebalance")]
        assert len(a_sells) == 1, f"a 의 리밸런싱 매도는 1건이어야 함 (실제: {len(a_sells)})"
        assert a_sells["exit_date"].iloc[0] == date(2024, 2, 1)
        assert a_sells["exit_price"].iloc[0] == pytest.approx(160.0 * (1 - SLIPPAGE_RATE), abs=1e-6)


class TestEnteringAssetOnCheckDay:
    """판단일에 진입 신호가 난 자산의 엔진 수준 계약 (전략_검증_보고서 부록 L.5).

    핵심 계약: 진입 자산은 리밸런싱 편차 판정에서 빠진다. 남은 자산의 편차가 10% 이하면
    진입 자산만 사고, 10% 를 넘으면 진입 자산까지 보유 자산 전부를 맞춘다.

    시나리오: 버퍼존 자산 a(MA5, hold_days 0) 50% · 보유 자산 b 50%.
    a 는 2024-01-31(월 마지막 거래일) 종가에 100 → 110 으로 뛰어 매수 신호가 난다
    (MA5 = 102, 상단 밴드 105.06 돌파). b 는 2024-01-15 부터 b_price_after 로 바뀐다.
    """

    def _run(self, tmp_path: Path, create_csv_file, b_price_after: float):
        a_path = create_csv_file("A_max.csv", _make_jump_df(date(2024, 1, 31), 100.0, 110.0))
        b_path = create_csv_file("B_max.csv", _make_jump_df(date(2024, 1, 15), 100.0, b_price_after))
        config = PortfolioConfig(
            experiment_name="test_entering_on_check_day",
            display_name="Test Entering On Check Day",
            asset_slots=(
                AssetSlotConfig("a", a_path, a_path, target_weight=0.50, ma_window=5, hold_days=0),
                AssetSlotConfig("b", b_path, b_path, target_weight=0.50, strategy_id="buy_and_hold"),
            ),
            total_capital=10_000_000.0,
            result_dir=tmp_path,
        )
        return run_portfolio_backtest(config)

    def _shares_on(self, result, asset_id: str, d: date) -> int:
        equity_df = result.equity_df
        return int(equity_df.loc[equity_df[COL_DATE] == d, f"{asset_id}_shares"].iloc[0])

    def test_only_entering_asset_trades_when_others_within_threshold(self, tmp_path: Path, create_csv_file):
        """
        목적: 남은 자산의 편차가 0 보다 크고 10% 이하면 판단일 진입이 리밸런싱을 일으키지 않음을 검증.

        Given: b 가 +5% → b 비중 ≈ 0.5114, 상대 편차 ≈ 2.3% (0 이 아니어야 지금 코드에서 b 주문이 생긴다)
        When:  run_portfolio_backtest() 실행
        Then:  리밸런싱한 날이 없고, 2024-02-01 에 a 만 매수되며 b 주수는 그대로다
        """
        # When
        result = self._run(tmp_path, create_csv_file, b_price_after=105.0)

        # Then
        equity_df = result.equity_df
        rebalanced_dates = list(equity_df.loc[equity_df["rebalanced"], COL_DATE])
        assert rebalanced_dates == [], f"진입 자산만으로는 리밸런싱이 없어야 함 (실제: {rebalanced_dates})"
        assert self._shares_on(result, "a", date(2024, 2, 1)) > 0, "a 는 2024-02-01 시가에 진입해야 함"
        assert self._shares_on(result, "b", date(2024, 2, 1)) == self._shares_on(
            result, "b", date(2024, 1, 31)
        ), "b 는 편차 10% 이하이므로 주수가 그대로여야 함"

    def test_all_assets_rebalanced_when_other_exceeds_threshold(self, tmp_path: Path, create_csv_file):
        """
        목적: 남은 자산의 편차가 10% 를 넘으면 진입 자산과 함께 보유 자산도 맞춰짐을 검증.

        Given: b 가 +30% → b 비중 ≈ 0.5645, 상대 편차 ≈ 12.9%
        When:  run_portfolio_backtest() 실행
        Then:  2024-02-01 하루 리밸런싱, a 진입, b 주수 감소
        """
        # When
        result = self._run(tmp_path, create_csv_file, b_price_after=130.0)

        # Then
        equity_df = result.equity_df
        rebalanced_dates = list(equity_df.loc[equity_df["rebalanced"], COL_DATE])
        assert rebalanced_dates == [date(2024, 2, 1)], f"리밸런싱은 2024-02-01 하루여야 함 (실제: {rebalanced_dates})"
        assert self._shares_on(result, "a", date(2024, 2, 1)) > 0, "a 는 2024-02-01 시가에 진입해야 함"
        assert self._shares_on(result, "b", date(2024, 2, 1)) < self._shares_on(
            result, "b", date(2024, 1, 31)
        ), "b 는 편차 12.9% 이므로 줄여야 함"


class TestB1CashBuffer:
    """B-1 포트폴리오 초기 현금 버퍼 테스트.

    핵심 계약: target_weight 합이 1.0 미만이면 잔여분이 현금으로 유지된다.
    """

    def test_b1_initial_cash_stays_uninvested(self, tmp_path: Path, create_csv_file):
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
# 엣지 케이스 테스트
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

    def test_no_overlap_period(self, tmp_path: Path, create_csv_file):
        """
        목적: 자산 간 공통 기간 없음 시 ValueError 발생 검증.

        Given: 자산 A: 2024-01 데이터, 자산 B: 2025-01 데이터 (겹침 없음)
        When:  run_portfolio_backtest() 호출
        Then:  ValueError 발생
        """
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

    def test_single_asset_portfolio(self, tmp_path: Path, create_csv_file):
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

    def test_c1_full_cash_on_sell(self, tmp_path: Path, create_csv_file):
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
# start_date 파라미터 계약 + compute_portfolio_effective_start_date 계약
# ============================================================================


class TestStartDateConstraint:
    """run_portfolio_backtest()의 start_date 파라미터 계약 테스트.

    핵심 계약:
    - start_date가 주어지면 equity_df의 첫 날짜가 start_date 이상이어야 한다.
    - start_date=None이면 기존 동작과 동일하다 (자연 시작일 사용).
    """

    def test_start_date_filters_early_data(self, tmp_path: Path, create_csv_file):
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

    def test_start_date_none_uses_natural_start(self, tmp_path: Path, create_csv_file):
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

    def test_returns_date_object(self, tmp_path: Path, create_csv_file):
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

    def test_effective_start_matches_backtest_start(self, tmp_path: Path, create_csv_file):
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

        config = PortfolioConfig(
            experiment_name="test_sma",
            display_name="Test SMA",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="qqq",
                    signal_data_path=qqq_path,
                    trade_data_path=qqq_path,
                    target_weight=1.0,
                    ma_window=5,  # 처음 4행(window-1=4)이 NaN
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
    """signal cache key 충돌 방지 계약 테스트.

    핵심 계약:
    - 동일 signal_data_path를 공유하는 슬롯이 서로 다른 ma_window를 사용해도
      각자 올바른 MA 컬럼을 가진 signal_df를 사용해야 한다.
    - 따라서 캐시 키는 경로만이 아니라 ma_window까지 포함해야 한다.
    """

    def test_same_path_different_ma_window_no_collision(self, tmp_path: Path, create_csv_file) -> None:
        """
        목적: 동일 signal_data_path + 다른 ma_window 슬롯이 각자 올바른 MA 컬럼 사용 검증.

        Given: 두 슬롯이 같은 qqq_path를 signal 소스로 공유하되
               슬롯 A는 ma_window=5, 슬롯 B는 ma_window=10 사용
        When:  run_portfolio_backtest() 실행
        Then:  예외 없이 완료, 각 슬롯이 자기 MA 컬럼(ma_5 / ma_10)을 사용
               (캐시 키가 경로만이면 슬롯 B가 ma_10 컬럼을 찾지 못해 KeyError가 난다)
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
        # 캐시 키가 경로만이면 ma_10 컬럼이 없어 KeyError가 난다
        result = run_portfolio_backtest(config)
        assert result is not None, "캐시 키 충돌 없이 정상 실행되어야 함"
        assert isinstance(result.equity_df, pd.DataFrame)
        assert len(result.equity_df) > 0


# ============================================================================
# 자산별 실현/미실현 손익 컬럼 계약 테스트
# ============================================================================


class TestAssetPnlColumns:
    """equity_df의 자산별 realized_pnl / unrealized_pnl 컬럼 계약 테스트."""

    def test_pnl_columns_exist(self, tmp_path: Path, create_csv_file):
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

    def test_pnl_zero_before_any_trade(self, tmp_path: Path, create_csv_file):
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

    def test_realized_pnl_persists_after_sell(self, tmp_path: Path, create_csv_file):
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

    def test_total_contribution_equals_realized_plus_unrealized(self, tmp_path: Path, create_csv_file):
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


class TestPortfolioHoldingViewColumns:
    """포트폴리오 엔진이 equity_df에 보유 현황 파생 컬럼을 포함하는지 검증.

    파생 컬럼:
    - {asset_id}_current_price: shares > 0이면 value/shares, 아니면 0.0
    - {asset_id}_return_pct: avg_price > 0 and shares > 0이면 (current/avg - 1)*100, 아니면 0.0
    - total_pnl: equity - initial_capital
    - total_return_pct: total_pnl/initial_capital * 100

    이전에는 app_portfolio_backtest.py가 직접 계산했으나, 단일 진실 공급원 확립을 위해
    엔진(build_combined_equity)에서 산출한다.
    """

    def test_equity_df_has_derived_holding_view_columns(self, tmp_path: Path, create_csv_file):
        """
        목적: equity_df에 4종 파생 컬럼이 모든 자산에 대해 존재함을 검증.

        Given: GLD 단일 자산 포트폴리오
        When:  run_portfolio_backtest 실행
        Then:  gld_current_price, gld_return_pct, total_pnl, total_return_pct 컬럼 존재
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

        # Then
        assert "gld_current_price" in equity_df.columns, "{aid}_current_price 컬럼이 존재해야 함"
        assert "gld_return_pct" in equity_df.columns, "{aid}_return_pct 컬럼이 존재해야 함"
        assert "total_pnl" in equity_df.columns, "total_pnl 컬럼이 존재해야 함"
        assert "total_return_pct" in equity_df.columns, "total_return_pct 컬럼이 존재해야 함"

    def test_current_price_equals_value_div_shares_when_holding(self, tmp_path: Path, create_csv_file):
        """
        목적: shares > 0인 행에서 current_price * shares == value 등식 검증.

        Given: 보유가 발생한 단일 자산 포트폴리오
        When:  파생 컬럼 계산 후
        Then:  모든 보유 행에서 current_price * shares ≈ value
               (shares > 0이고 avg_price > 0이면 return_pct = (current/avg - 1)*100)
        """
        stock_df = _make_stock_df(n_rows=30)
        gld_path = create_csv_file("GLD_max.csv", stock_df)
        config = _make_portfolio_config(
            asset_paths={"gld": (gld_path, gld_path)},
            result_dir=tmp_path,
            target_weights={"gld": 1.0},
            ma_window=5,
        )

        result = run_portfolio_backtest(config)
        equity_df = result.equity_df
        holding_rows = equity_df[equity_df["gld_shares"] > 0]

        # 보유 행이 최소 1개는 있어야 한다 (이 시나리오에서)
        assert len(holding_rows) > 0, "테스트 시나리오에서 보유 행이 발생해야 함"

        for _, row in holding_rows.iterrows():
            # current_price * shares == value
            assert row["gld_current_price"] * row["gld_shares"] == pytest.approx(row["gld_value"], abs=0.01)
            # return_pct = (current_price / avg_price - 1) * 100
            if row["gld_avg_price"] > 0:
                expected_return = (row["gld_current_price"] / row["gld_avg_price"] - 1) * 100
                assert row["gld_return_pct"] == pytest.approx(expected_return, abs=0.1)

    def test_current_price_zero_when_no_position(self, tmp_path: Path, create_csv_file):
        """
        목적: shares == 0인 행에서 current_price 와 return_pct가 0.0임을 검증.

        Given: 매수 신호 발생 전(초기) 행이 존재하는 포트폴리오
        When:  파생 컬럼 계산 후
        Then:  shares == 0인 행에서 current_price == 0.0 and return_pct == 0.0
        """
        stock_df = _make_stock_df(n_rows=30)
        gld_path = create_csv_file("GLD_max.csv", stock_df)
        config = _make_portfolio_config(
            asset_paths={"gld": (gld_path, gld_path)},
            result_dir=tmp_path,
            target_weights={"gld": 1.0},
            ma_window=5,
        )

        result = run_portfolio_backtest(config)
        equity_df = result.equity_df
        non_holding_rows = equity_df[equity_df["gld_shares"] == 0]

        # 매수 신호 전에는 shares == 0인 행이 존재해야 한다
        assert len(non_holding_rows) > 0, "매수 신호 발생 전 보유 없음 행이 존재해야 함"

        for _, row in non_holding_rows.iterrows():
            assert row["gld_current_price"] == pytest.approx(0.0, abs=1e-12)
            assert row["gld_return_pct"] == pytest.approx(0.0, abs=1e-12)

    def test_total_pnl_and_return_pct(self, tmp_path: Path, create_csv_file):
        """
        목적: total_pnl과 total_return_pct가 equity와 initial_capital로부터 정확히 산출됨을 검증.

        Given: total_capital이 명시된 포트폴리오
        When:  파생 컬럼 계산 후
        Then:  total_pnl == equity - initial_capital
               total_return_pct == total_pnl / initial_capital * 100
        """
        stock_df = _make_stock_df(n_rows=30)
        gld_path = create_csv_file("GLD_max.csv", stock_df)
        config = _make_portfolio_config(
            asset_paths={"gld": (gld_path, gld_path)},
            result_dir=tmp_path,
            target_weights={"gld": 1.0},
            ma_window=5,
            total_capital=10_000_000.0,
        )

        result = run_portfolio_backtest(config)
        equity_df = result.equity_df
        initial_capital = config.total_capital

        for _, row in equity_df.iterrows():
            expected_pnl = row["equity"] - initial_capital
            expected_return_pct = (expected_pnl / initial_capital) * 100
            assert row["total_pnl"] == pytest.approx(expected_pnl, abs=0.5)
            assert row["total_return_pct"] == pytest.approx(expected_return_pct, abs=0.1)

    def test_contribution_column_equals_realized_plus_unrealized(self, tmp_path: Path, create_csv_file):
        """
        목적: equity_df의 {asset_id}_contribution 컬럼이 realized_pnl + unrealized_pnl과 일치함을 검증.

        Given: GLD 단일 자산 포트폴리오
        When:  run_portfolio_backtest 실행
        Then:  모든 행에서 gld_contribution == gld_realized_pnl + gld_unrealized_pnl
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

        # Then
        assert "gld_contribution" in equity_df.columns
        for _, row in equity_df.iterrows():
            expected = row["gld_realized_pnl"] + row["gld_unrealized_pnl"]
            assert row["gld_contribution"] == pytest.approx(expected, abs=1e-9)
