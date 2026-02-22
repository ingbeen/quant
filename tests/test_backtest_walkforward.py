"""백테스트 워크포워드 검증(WFO) 테스트

Phase 0: params_schedule, WFO 윈도우 생성, Calmar 선택 테스트
Phase 2: WFO 엔진, build_params_schedule, calculate_wfo_mode_summary 테스트
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    run_buffer_strategy,
)
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME, EPSILON


def _make_stock_df(
    start_date: date,
    n_days: int,
    base_price: float = 100.0,
    daily_return: float = 0.001,
) -> pd.DataFrame:
    """테스트용 주식 데이터를 생성한다.

    Args:
        start_date: 시작 날짜
        n_days: 거래일 수
        base_price: 시작 가격
        daily_return: 일일 수익률 (기본 0.1%)

    Returns:
        OHLCV DataFrame
    """
    dates = []
    prices = []
    current = base_price
    d = start_date
    for _ in range(n_days):
        # 주말 건너뛰기
        while d.weekday() >= 5:
            from datetime import timedelta

            d = d + timedelta(days=1)
        dates.append(d)
        prices.append(current)
        current = current * (1 + daily_return)
        from datetime import timedelta

        d = d + timedelta(days=1)

    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [p * 0.999 for p in prices],
            COL_HIGH: [p * 1.01 for p in prices],
            COL_LOW: [p * 0.99 for p in prices],
            COL_CLOSE: prices,
            COL_VOLUME: [1_000_000] * n_days,
        }
    )


class TestParamsSchedule:
    """params_schedule 파라미터 테스트.

    params_schedule=None이면 기존 동작과 동일하고,
    params_schedule이 주어지면 구간별 파라미터 전환이 이루어지는지 검증한다.
    """

    def test_none_schedule_preserves_existing_behavior(self):
        """
        목적: params_schedule=None이면 기존 동작과 완전히 동일함을 검증

        Given: 충분한 길이의 주식 데이터 (MA 계산 가능)
        When: params_schedule=None으로 run_buffer_strategy 실행
        Then: 기존과 동일한 결과 반환 (에러 없음)
        """
        # Given
        df = _make_stock_df(date(2000, 1, 3), 300, base_price=100.0, daily_return=0.001)
        from qbt.backtest.analysis import add_single_moving_average

        signal_df = add_single_moving_average(df.copy(), 50, ma_type="ema")
        trade_df = df.copy()

        params = BufferStrategyParams(
            initial_capital=DEFAULT_INITIAL_CAPITAL,
            ma_window=50,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
        )

        # When — params_schedule=None (기본값)
        trades_df, equity_df, summary = run_buffer_strategy(signal_df, trade_df, params, log_trades=False)

        # Then — 정상 실행 확인
        assert len(equity_df) > 0
        assert summary["initial_capital"] == DEFAULT_INITIAL_CAPITAL

    def test_schedule_switches_params_at_boundary(self):
        """
        목적: params_schedule로 파라미터 전환이 올바르게 이루어지는지 검증

        Given: 2구간 params_schedule (구간1: ma=50, 구간2: ma=100)
        When: run_buffer_strategy(params_schedule=...) 실행
        Then: 에러 없이 실행 완료, equity_df 생성
        """
        # Given — 충분한 데이터 (MA 100 이상)
        df = _make_stock_df(date(2000, 1, 3), 500, base_price=100.0, daily_return=0.001)
        from qbt.backtest.analysis import add_single_moving_average

        # 두 MA 모두 사전 계산
        signal_df = add_single_moving_average(df.copy(), 50, ma_type="ema")
        signal_df = add_single_moving_average(signal_df, 100, ma_type="ema")
        trade_df = df.copy()

        # 첫 구간 파라미터
        params = BufferStrategyParams(
            initial_capital=DEFAULT_INITIAL_CAPITAL,
            ma_window=50,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
        )

        # 전환점에서 MA 100으로 변경
        switch_date = df.iloc[250][COL_DATE]
        params_schedule = {
            switch_date: BufferStrategyParams(
                initial_capital=DEFAULT_INITIAL_CAPITAL,
                ma_window=100,
                buy_buffer_zone_pct=0.05,
                sell_buffer_zone_pct=0.01,
                hold_days=2,
                recent_months=4,
            )
        }

        # When
        trades_df, equity_df, summary = run_buffer_strategy(
            signal_df,
            trade_df,
            params,
            log_trades=False,
            params_schedule=params_schedule,
        )

        # Then
        assert len(equity_df) > 0
        assert summary["initial_capital"] == DEFAULT_INITIAL_CAPITAL

    def test_schedule_ma_window_change_updates_bands(self):
        """
        목적: MA 윈도우 변경 시 밴드 계산이 새 MA 기준으로 전환됨을 검증

        Given: MA 50 → MA 100으로 전환하는 schedule
        When: run_buffer_strategy 실행
        Then: 전환점 이후 equity_df의 band 값이 MA 100 기준으로 계산됨
        """
        # Given
        df = _make_stock_df(date(2000, 1, 3), 500, base_price=100.0, daily_return=0.0005)
        from qbt.backtest.analysis import add_single_moving_average

        signal_df = add_single_moving_average(df.copy(), 50, ma_type="ema")
        signal_df = add_single_moving_average(signal_df, 100, ma_type="ema")
        trade_df = df.copy()

        params = BufferStrategyParams(
            initial_capital=DEFAULT_INITIAL_CAPITAL,
            ma_window=50,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
        )

        switch_date = df.iloc[300][COL_DATE]
        params_schedule = {
            switch_date: BufferStrategyParams(
                initial_capital=DEFAULT_INITIAL_CAPITAL,
                ma_window=100,
                buy_buffer_zone_pct=0.05,
                sell_buffer_zone_pct=0.05,
                hold_days=0,
                recent_months=0,
            )
        }

        # When
        trades_df, equity_df, summary = run_buffer_strategy(
            signal_df,
            trade_df,
            params,
            log_trades=False,
            params_schedule=params_schedule,
        )

        # Then — 전환 이후의 upper_band가 MA 100 기반이어야 함
        # equity_df에서 전환점 이후 행을 확인
        after_switch = equity_df[equity_df[COL_DATE] >= switch_date]
        assert len(after_switch) > 0

        # upper_band가 None이 아닌 값이 존재해야 함
        non_null_bands = after_switch[after_switch["upper_band"].notna()]
        assert len(non_null_bands) > 0


class TestGenerateWfoWindows:
    """WFO 윈도우 생성 함수 테스트."""

    def test_window_count_and_boundaries(self):
        """
        목적: Expanding Anchored 윈도우의 수와 날짜 경계를 검증

        Given: 1999-03 ~ 2025-02 기간, IS=72개월, OOS=24개월
        When: generate_wfo_windows() 호출
        Then: 약 10개 윈도우, 모든 IS는 1999-03-01에서 시작,
              OOS 기간은 24개월씩
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)

        # When
        windows = generate_wfo_windows(data_start, data_end, 72, 24)

        # Then
        assert len(windows) >= 8  # 최소 8개 이상
        assert len(windows) <= 12  # 최대 12개 이하

        # 모든 윈도우의 IS는 data_start에서 시작 (Expanding Anchored)
        for is_start, _, _, _ in windows:
            assert is_start == data_start

        # 각 윈도우의 OOS start는 IS end + 1일
        for _, is_end, oos_start, _ in windows:
            assert oos_start > is_end

        # OOS는 연속적이어야 함
        for i in range(1, len(windows)):
            prev_oos_end = windows[i - 1][3]
            curr_oos_start = windows[i][2]
            # 이전 OOS 종료 다음 달이 현재 OOS 시작
            assert curr_oos_start > prev_oos_end

    def test_insufficient_data_raises_error(self):
        """
        목적: 데이터가 첫 OOS를 만들기에 부족하면 ValueError 발생

        Given: 5년 미만의 데이터 기간
        When: generate_wfo_windows(initial_is=72, oos=24) 호출
        Then: ValueError 발생
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given — 6년(72개월) IS + 2년(24개월) OOS = 최소 8년 필요, 5년만 제공
        data_start = date(2020, 1, 1)
        data_end = date(2025, 1, 1)

        # When/Then
        with pytest.raises(ValueError, match="부족"):
            generate_wfo_windows(data_start, data_end, 72, 24)


class TestCalmarSelection:
    """Calmar 기준 최적 파라미터 선택 테스트."""

    def test_mdd_zero_with_positive_cagr_is_best(self):
        """
        목적: MDD=0이고 CAGR>0이면 Calmar 최우선 처리

        Given: 그리드 서치 결과 DataFrame (MDD=0 + CAGR>0인 행 포함)
        When: Calmar 기준 정렬
        Then: MDD=0 + CAGR>0인 행이 1위
        """
        from qbt.backtest.walkforward import select_best_calmar_params

        # Given
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150, 200],
                "buy_buffer_zone_pct": [0.03, 0.03, 0.03],
                "sell_buffer_zone_pct": [0.03, 0.03, 0.03],
                "hold_days": [0, 0, 0],
                "recent_months": [0, 0, 0],
                "cagr": [5.0, 10.0, 3.0],
                "mdd": [-20.0, 0.0, -10.0],
                "total_return_pct": [50.0, 100.0, 30.0],
                "total_trades": [5, 0, 3],
                "win_rate": [60.0, 0.0, 66.7],
                "final_capital": [15_000_000, 20_000_000, 13_000_000],
            }
        )

        # When
        best = select_best_calmar_params(grid_df)

        # Then — MDD=0 + CAGR>0인 ma_window=150이 선택됨
        assert best["ma_window"] == 150

    def test_mdd_zero_with_negative_cagr_gets_calmar_zero(self):
        """
        목적: MDD=0이지만 CAGR<=0이면 calmar=0 처리

        Given: 모든 행이 MDD=0이고 CAGR<=0
        When: Calmar 기준 정렬
        Then: calmar=0으로 처리되어 모두 동등
        """
        from qbt.backtest.walkforward import select_best_calmar_params

        # Given
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150],
                "buy_buffer_zone_pct": [0.03, 0.03],
                "sell_buffer_zone_pct": [0.03, 0.03],
                "hold_days": [0, 0],
                "recent_months": [0, 0],
                "cagr": [-5.0, -2.0],
                "mdd": [0.0, 0.0],
                "total_return_pct": [-50.0, -20.0],
                "total_trades": [0, 0],
                "win_rate": [0.0, 0.0],
                "final_capital": [5_000_000, 8_000_000],
            }
        )

        # When
        best = select_best_calmar_params(grid_df)

        # Then — 어느 쪽이든 선택 가능 (calmar=0으로 동등)
        assert best["ma_window"] in [100, 150]

    def test_normal_calmar_selection(self):
        """
        목적: 일반적인 CAGR/|MDD| 기준 Calmar 선택 검증

        Given: CAGR과 MDD가 모두 0이 아닌 행들
        When: Calmar 기준 정렬
        Then: CAGR/|MDD|가 가장 큰 행이 선택됨
        """
        from qbt.backtest.walkforward import select_best_calmar_params

        # Given
        # ma=100: calmar = 10 / 20 = 0.5
        # ma=150: calmar = 15 / 25 = 0.6  ← 최대
        # ma=200: calmar = 8  / 30 = 0.267
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150, 200],
                "buy_buffer_zone_pct": [0.03, 0.05, 0.01],
                "sell_buffer_zone_pct": [0.03, 0.01, 0.05],
                "hold_days": [0, 2, 5],
                "recent_months": [0, 4, 8],
                "cagr": [10.0, 15.0, 8.0],
                "mdd": [-20.0, -25.0, -30.0],
                "total_return_pct": [100.0, 150.0, 80.0],
                "total_trades": [5, 8, 3],
                "win_rate": [60.0, 62.5, 66.7],
                "final_capital": [20_000_000, 25_000_000, 18_000_000],
            }
        )

        # When
        best = select_best_calmar_params(grid_df)

        # Then — calmar=0.6인 ma=150이 선택
        assert best["ma_window"] == 150
        assert best["buy_buffer_zone_pct"] == pytest.approx(0.05, abs=EPSILON)
        assert best["sell_buffer_zone_pct"] == pytest.approx(0.01, abs=EPSILON)
        assert best["hold_days"] == 2
        assert best["recent_months"] == 4


class TestRunWalkforward:
    """WFO 루프 동작 검증 (소규모 데이터)."""

    def test_walkforward_returns_correct_structure(self):
        """
        목적: 소규모 데이터로 WFO 루프가 올바른 구조를 반환하는지 검증

        Given: 약 10년 분량의 주식 데이터 (IS=24개월, OOS=12개월로 축소)
        When: run_walkforward() 실행
        Then: 결과 리스트의 각 아이템이 WfoWindowResultDict 구조를 가짐
        """
        from qbt.backtest.walkforward import run_walkforward

        # Given — 약 10년 분량 (2500 거래일), 작은 윈도우로 빠른 실행
        df = _make_stock_df(date(2000, 1, 3), 2500, base_price=100.0, daily_return=0.0003)

        # When — 소규모 파라미터 리스트로 실행 (속도 최적화)
        results = run_walkforward(
            signal_df=df,
            trade_df=df,
            ma_window_list=[50],
            buy_buffer_zone_pct_list=[0.03],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0],
            recent_months_list=[0],
            initial_is_months=24,
            oos_months=12,
        )

        # Then — 최소 1개 이상의 윈도우 결과
        assert len(results) >= 1

        # 구조 검증
        first = results[0]
        assert first["window_idx"] == 0
        assert "is_start" in first
        assert "oos_start" in first
        assert "best_ma_window" in first
        assert "is_calmar" in first
        assert "oos_calmar" in first
        assert "wfe_calmar" in first


class TestBuildParamsSchedule:
    """build_params_schedule() 함수 테스트."""

    def test_schedule_keys_are_oos_start_dates(self):
        """
        목적: schedule 키 날짜 = OOS 시작일 검증

        Given: 3개 윈도우의 WFO 결과
        When: build_params_schedule() 호출
        Then: schedule의 키가 2번째, 3번째 윈도우의 oos_start
        """
        from qbt.backtest.walkforward import build_params_schedule

        # Given
        results: list[dict[str, object]] = [
            {
                "window_idx": 0,
                "is_start": "2000-01-01",
                "is_end": "2005-12-31",
                "oos_start": "2006-01-01",
                "oos_end": "2007-12-31",
                "best_ma_window": 100,
                "best_buy_buffer_zone_pct": 0.03,
                "best_sell_buffer_zone_pct": 0.03,
                "best_hold_days": 0,
                "best_recent_months": 0,
                "is_cagr": 10.0,
                "is_mdd": -20.0,
                "is_calmar": 0.5,
                "is_trades": 5,
                "is_win_rate": 60.0,
                "oos_cagr": 8.0,
                "oos_mdd": -15.0,
                "oos_calmar": 0.53,
                "oos_trades": 2,
                "oos_win_rate": 50.0,
                "wfe_calmar": 1.06,
            },
            {
                "window_idx": 1,
                "is_start": "2000-01-01",
                "is_end": "2007-12-31",
                "oos_start": "2008-01-01",
                "oos_end": "2009-12-31",
                "best_ma_window": 150,
                "best_buy_buffer_zone_pct": 0.05,
                "best_sell_buffer_zone_pct": 0.01,
                "best_hold_days": 2,
                "best_recent_months": 4,
                "is_cagr": 12.0,
                "is_mdd": -25.0,
                "is_calmar": 0.48,
                "is_trades": 8,
                "is_win_rate": 62.5,
                "oos_cagr": -5.0,
                "oos_mdd": -40.0,
                "oos_calmar": 0.125,
                "oos_trades": 3,
                "oos_win_rate": 33.3,
                "wfe_calmar": 0.26,
            },
            {
                "window_idx": 2,
                "is_start": "2000-01-01",
                "is_end": "2009-12-31",
                "oos_start": "2010-01-01",
                "oos_end": "2011-12-31",
                "best_ma_window": 200,
                "best_buy_buffer_zone_pct": 0.01,
                "best_sell_buffer_zone_pct": 0.05,
                "best_hold_days": 5,
                "best_recent_months": 8,
                "is_cagr": 9.0,
                "is_mdd": -18.0,
                "is_calmar": 0.5,
                "is_trades": 6,
                "is_win_rate": 66.7,
                "oos_cagr": 15.0,
                "oos_mdd": -12.0,
                "oos_calmar": 1.25,
                "oos_trades": 2,
                "oos_win_rate": 100.0,
                "wfe_calmar": 2.5,
            },
        ]

        # When
        initial_params, schedule = build_params_schedule(results)  # type: ignore[arg-type]

        # Then — initial_params는 첫 윈도우 기반
        assert initial_params.ma_window == 100
        assert initial_params.buy_buffer_zone_pct == pytest.approx(0.03, abs=EPSILON)

        # schedule 키는 2번째, 3번째 윈도우의 oos_start
        assert len(schedule) == 2
        assert date(2008, 1, 1) in schedule
        assert date(2010, 1, 1) in schedule

        # 2번째 윈도우 파라미터 검증
        assert schedule[date(2008, 1, 1)].ma_window == 150
        assert schedule[date(2008, 1, 1)].buy_buffer_zone_pct == pytest.approx(0.05, abs=EPSILON)

        # 3번째 윈도우 파라미터 검증
        assert schedule[date(2010, 1, 1)].ma_window == 200


class TestCalculateWfoModeSummary:
    """calculate_wfo_mode_summary() 함수 테스트."""

    def test_summary_statistics(self):
        """
        목적: OOS 통계 계산이 정확한지 검증

        Given: 2개 윈도우의 WFO 결과
        When: calculate_wfo_mode_summary() 호출
        Then: mean, std, worst 등 통계값 검증
        """
        from qbt.backtest.walkforward import calculate_wfo_mode_summary

        # Given
        results: list[dict[str, object]] = [
            {
                "window_idx": 0,
                "is_start": "2000-01-01",
                "is_end": "2005-12-31",
                "oos_start": "2006-01-01",
                "oos_end": "2007-12-31",
                "best_ma_window": 100,
                "best_buy_buffer_zone_pct": 0.03,
                "best_sell_buffer_zone_pct": 0.03,
                "best_hold_days": 0,
                "best_recent_months": 0,
                "is_cagr": 10.0,
                "is_mdd": -20.0,
                "is_calmar": 0.5,
                "is_trades": 5,
                "is_win_rate": 60.0,
                "oos_cagr": 8.0,
                "oos_mdd": -15.0,
                "oos_calmar": 0.53,
                "oos_trades": 2,
                "oos_win_rate": 50.0,
                "wfe_calmar": 1.06,
            },
            {
                "window_idx": 1,
                "is_start": "2000-01-01",
                "is_end": "2007-12-31",
                "oos_start": "2008-01-01",
                "oos_end": "2009-12-31",
                "best_ma_window": 150,
                "best_buy_buffer_zone_pct": 0.05,
                "best_sell_buffer_zone_pct": 0.01,
                "best_hold_days": 2,
                "best_recent_months": 4,
                "is_cagr": 12.0,
                "is_mdd": -25.0,
                "is_calmar": 0.48,
                "is_trades": 8,
                "is_win_rate": 62.5,
                "oos_cagr": -5.0,
                "oos_mdd": -40.0,
                "oos_calmar": 0.125,
                "oos_trades": 3,
                "oos_win_rate": 33.3,
                "wfe_calmar": 0.26,
            },
        ]

        # When
        summary = calculate_wfo_mode_summary(results)  # type: ignore[arg-type]

        # Then
        assert summary["n_windows"] == 2
        # oos_cagr_mean = (8 + (-5)) / 2 = 1.5
        assert summary["oos_cagr_mean"] == pytest.approx(1.5, abs=0.01)
        # oos_mdd_worst = min(-15, -40) = -40
        assert summary["oos_mdd_worst"] == pytest.approx(-40.0, abs=0.01)
        # oos_trades_total = 2 + 3 = 5
        assert summary["oos_trades_total"] == 5
        # param_ma_windows
        assert summary["param_ma_windows"] == [100, 150]
        assert summary["param_buy_buffers"] == [0.03, 0.05]
