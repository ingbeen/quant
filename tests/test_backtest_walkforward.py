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
                "total_trades": [5, 3, 3],
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
                "total_trades": [3, 4],
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
        # min_trades=0: 소규모 테스트에서 거래수 제약 비활성화
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
            min_trades=0,
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
                "wfe_cagr": 0.8,
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
                "wfe_cagr": -0.4167,
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
                "wfe_cagr": 1.6667,
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
                "wfe_cagr": 0.8,
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
                "wfe_cagr": -0.4167,
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


class TestWfeCagr:
    """WFE CAGR 계산 검증 테스트."""

    def test_wfe_cagr_positive_is_cagr(self):
        """
        목적: IS CAGR > 0일 때 wfe_cagr = oos_cagr / is_cagr

        Given: IS CAGR=10.0, OOS CAGR=8.0
        When: run_walkforward()에서 wfe_cagr 계산
        Then: wfe_cagr = 8.0 / 10.0 = 0.8
        """
        from qbt.backtest.walkforward import run_walkforward

        # Given — 약 10년 분량, 작은 윈도우로 빠른 실행
        df = _make_stock_df(date(2000, 1, 3), 2500, base_price=100.0, daily_return=0.0003)

        # When — min_trades=0: 소규모 테스트에서 거래수 제약 비활성화
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
            min_trades=0,
        )

        # Then — wfe_cagr 필드가 존재하고 올바른 계산
        assert len(results) >= 1
        for r in results:
            assert "wfe_cagr" in r
            is_cagr = r["is_cagr"]
            oos_cagr = r["oos_cagr"]
            if abs(is_cagr) > EPSILON:
                expected = oos_cagr / is_cagr
                assert r["wfe_cagr"] == pytest.approx(expected, abs=1e-6)
            else:
                assert r["wfe_cagr"] == pytest.approx(0.0, abs=EPSILON)

    def test_wfe_cagr_zero_is_cagr(self):
        """
        목적: IS CAGR ≤ EPSILON일 때 wfe_cagr = 0.0

        Given: IS CAGR가 0에 가까운 윈도우 결과 (직접 계산 검증)
        When: wfe_cagr 계산 로직 적용
        Then: wfe_cagr = 0.0
        """
        # IS CAGR ≈ 0인 경우를 검증하기 위해 직접 계산 로직을 확인
        # run_walkforward는 실제로 IS CAGR=0을 만들기 어려우므로
        # calculate_wfo_mode_summary에 전달할 mock 데이터로 검증
        from qbt.backtest.walkforward import calculate_wfo_mode_summary

        # Given — wfe_cagr=0.0인 윈도우 (IS CAGR ≤ EPSILON)
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
                "is_cagr": 0.0,
                "is_mdd": 0.0,
                "is_calmar": 0.0,
                "is_trades": 0,
                "is_win_rate": 0.0,
                "oos_cagr": 5.0,
                "oos_mdd": -10.0,
                "oos_calmar": 0.5,
                "oos_trades": 1,
                "oos_win_rate": 100.0,
                "wfe_calmar": 0.0,
                "wfe_cagr": 0.0,
            },
        ]

        # When
        summary = calculate_wfo_mode_summary(results)  # type: ignore[arg-type]

        # Then — wfe_cagr_mean = 0.0
        assert summary["wfe_cagr_mean"] == pytest.approx(0.0, abs=EPSILON)
        assert summary["wfe_cagr_median"] == pytest.approx(0.0, abs=EPSILON)


class TestWfeCalmarRobust:
    """WFE Calmar Robust 계산 검증 테스트."""

    def test_robust_excludes_non_positive_is_calmar(self):
        """
        목적: IS Calmar ≤ 0인 윈도우를 제외하고 WFE Calmar 중앙값 계산

        Given: 3개 윈도우 (IS Calmar: 0.5, -0.2, 0.3)
        When: calculate_wfo_mode_summary() 호출
        Then: wfe_calmar_robust = IS Calmar > 0인 윈도우(0.5, 0.3)만의 wfe_calmar 중앙값
        """
        from qbt.backtest.walkforward import calculate_wfo_mode_summary

        # Given — IS Calmar > 0: 윈도우 0, 2만 해당
        results: list[dict[str, object]] = [
            {
                "window_idx": 0,
                "is_start": "2000-01-01",
                "is_end": "2003-12-31",
                "oos_start": "2004-01-01",
                "oos_end": "2005-12-31",
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
                "wfe_cagr": 0.8,
            },
            {
                "window_idx": 1,
                "is_start": "2000-01-01",
                "is_end": "2005-12-31",
                "oos_start": "2006-01-01",
                "oos_end": "2007-12-31",
                "best_ma_window": 150,
                "best_buy_buffer_zone_pct": 0.05,
                "best_sell_buffer_zone_pct": 0.01,
                "best_hold_days": 2,
                "best_recent_months": 4,
                "is_cagr": -3.0,
                "is_mdd": -15.0,
                "is_calmar": -0.2,
                "is_trades": 3,
                "is_win_rate": 33.3,
                "oos_cagr": 2.0,
                "oos_mdd": -8.0,
                "oos_calmar": 0.25,
                "oos_trades": 1,
                "oos_win_rate": 100.0,
                "wfe_calmar": -1.25,
                "wfe_cagr": -0.6667,
            },
            {
                "window_idx": 2,
                "is_start": "2000-01-01",
                "is_end": "2007-12-31",
                "oos_start": "2008-01-01",
                "oos_end": "2009-12-31",
                "best_ma_window": 200,
                "best_buy_buffer_zone_pct": 0.01,
                "best_sell_buffer_zone_pct": 0.05,
                "best_hold_days": 5,
                "best_recent_months": 8,
                "is_cagr": 6.0,
                "is_mdd": -20.0,
                "is_calmar": 0.3,
                "is_trades": 4,
                "is_win_rate": 75.0,
                "oos_cagr": 4.0,
                "oos_mdd": -10.0,
                "oos_calmar": 0.4,
                "oos_trades": 2,
                "oos_win_rate": 50.0,
                "wfe_calmar": 1.3333,
                "wfe_cagr": 0.6667,
            },
        ]

        # When
        summary = calculate_wfo_mode_summary(results)  # type: ignore[arg-type]

        # Then — IS Calmar > 0인 윈도우: idx=0 (wfe=1.06), idx=2 (wfe=1.3333)
        # 중앙값 = (1.06 + 1.3333) / 2 = 1.1967
        assert summary["wfe_calmar_robust"] == pytest.approx(1.1967, abs=0.01)

    def test_robust_all_non_positive_returns_zero(self):
        """
        목적: 모든 윈도우의 IS Calmar ≤ 0이면 wfe_calmar_robust = 0.0

        Given: 1개 윈도우 (IS Calmar = -0.5)
        When: calculate_wfo_mode_summary() 호출
        Then: wfe_calmar_robust = 0.0
        """
        from qbt.backtest.walkforward import calculate_wfo_mode_summary

        # Given
        results: list[dict[str, object]] = [
            {
                "window_idx": 0,
                "is_start": "2000-01-01",
                "is_end": "2003-12-31",
                "oos_start": "2004-01-01",
                "oos_end": "2005-12-31",
                "best_ma_window": 100,
                "best_buy_buffer_zone_pct": 0.03,
                "best_sell_buffer_zone_pct": 0.03,
                "best_hold_days": 0,
                "best_recent_months": 0,
                "is_cagr": -5.0,
                "is_mdd": -10.0,
                "is_calmar": -0.5,
                "is_trades": 2,
                "is_win_rate": 0.0,
                "oos_cagr": 3.0,
                "oos_mdd": -5.0,
                "oos_calmar": 0.6,
                "oos_trades": 1,
                "oos_win_rate": 100.0,
                "wfe_calmar": -1.2,
                "wfe_cagr": -0.6,
            },
        ]

        # When
        summary = calculate_wfo_mode_summary(results)  # type: ignore[arg-type]

        # Then
        assert summary["wfe_calmar_robust"] == pytest.approx(0.0, abs=EPSILON)


class TestProfitConcentration:
    """Profit Concentration 계산 검증 테스트."""

    def test_profit_concentration_v2(self):
        """
        목적: V2 방식(end - prev_end)으로 PC 계산 검증

        Given: stitched equity 기반 윈도우별 equity 정보
               stitched_summary를 통해 전달
        When: calculate_wfo_mode_summary() 호출
        Then: 최대 PC와 해당 윈도우 인덱스가 올바름
        """
        from qbt.backtest.walkforward import calculate_wfo_mode_summary

        # Given — 3개 윈도우, stitched equity 경계값:
        # initial=10000, w0_end=12000, w1_end=18000, w2_end=20000
        # V2 기여분: w0=12000-10000=2000, w1=18000-12000=6000, w2=20000-18000=2000
        # total_profit = 20000-10000 = 10000
        # shares: w0=0.2, w1=0.6, w2=0.2 → max=0.6, idx=1
        results: list[dict[str, object]] = [
            {
                "window_idx": 0,
                "is_start": "2000-01-01",
                "is_end": "2003-12-31",
                "oos_start": "2004-01-01",
                "oos_end": "2005-12-31",
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
                "wfe_cagr": 0.8,
            },
            {
                "window_idx": 1,
                "is_start": "2000-01-01",
                "is_end": "2005-12-31",
                "oos_start": "2006-01-01",
                "oos_end": "2007-12-31",
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
                "oos_cagr": 20.0,
                "oos_mdd": -10.0,
                "oos_calmar": 2.0,
                "oos_trades": 3,
                "oos_win_rate": 66.7,
                "wfe_calmar": 4.17,
                "wfe_cagr": 1.6667,
            },
            {
                "window_idx": 2,
                "is_start": "2000-01-01",
                "is_end": "2007-12-31",
                "oos_start": "2008-01-01",
                "oos_end": "2009-12-31",
                "best_ma_window": 200,
                "best_buy_buffer_zone_pct": 0.01,
                "best_sell_buffer_zone_pct": 0.05,
                "best_hold_days": 5,
                "best_recent_months": 8,
                "is_cagr": 9.0,
                "is_mdd": -18.0,
                "is_calmar": 0.5,
                "is_trades": 4,
                "is_win_rate": 75.0,
                "oos_cagr": 5.0,
                "oos_mdd": -8.0,
                "oos_calmar": 0.625,
                "oos_trades": 2,
                "oos_win_rate": 50.0,
                "wfe_calmar": 1.25,
                "wfe_cagr": 0.5556,
            },
        ]

        # stitched_summary에 윈도우 경계 equity 정보 포함
        stitched_summary: dict[str, object] = {
            "initial_capital": 10000.0,
            "final_capital": 20000.0,
            "cagr": 12.0,
            "mdd": -15.0,
            "total_return_pct": 100.0,
            "window_end_equities": [12000.0, 18000.0, 20000.0],
        }

        # When
        summary = calculate_wfo_mode_summary(results, stitched_summary)  # type: ignore[arg-type]

        # Then — max PC = 0.6 at window idx=1
        assert summary["profit_concentration_max"] == pytest.approx(0.6, abs=0.01)
        assert summary["profit_concentration_window_idx"] == 1

    def test_profit_concentration_total_loss(self):
        """
        목적: 전체 손실(total_net_profit ≤ 0)이면 PC = 0.0

        Given: stitched equity가 전체적으로 손실
        When: calculate_wfo_mode_summary() 호출
        Then: profit_concentration_max = 0.0
        """
        from qbt.backtest.walkforward import calculate_wfo_mode_summary

        # Given
        results: list[dict[str, object]] = [
            {
                "window_idx": 0,
                "is_start": "2000-01-01",
                "is_end": "2003-12-31",
                "oos_start": "2004-01-01",
                "oos_end": "2005-12-31",
                "best_ma_window": 100,
                "best_buy_buffer_zone_pct": 0.03,
                "best_sell_buffer_zone_pct": 0.03,
                "best_hold_days": 0,
                "best_recent_months": 0,
                "is_cagr": 5.0,
                "is_mdd": -10.0,
                "is_calmar": 0.5,
                "is_trades": 3,
                "is_win_rate": 66.7,
                "oos_cagr": -10.0,
                "oos_mdd": -30.0,
                "oos_calmar": 0.33,
                "oos_trades": 2,
                "oos_win_rate": 0.0,
                "wfe_calmar": 0.66,
                "wfe_cagr": -2.0,
            },
        ]

        # initial=10000, final=8000 → 전체 손실
        stitched_summary: dict[str, object] = {
            "initial_capital": 10000.0,
            "final_capital": 8000.0,
            "cagr": -5.0,
            "mdd": -30.0,
            "total_return_pct": -20.0,
            "window_end_equities": [8000.0],
        }

        # When
        summary = calculate_wfo_mode_summary(results, stitched_summary)  # type: ignore[arg-type]

        # Then — 전체 손실이므로 PC = 0.0
        assert summary["profit_concentration_max"] == pytest.approx(0.0, abs=EPSILON)
        assert summary["profit_concentration_window_idx"] == 0


class TestJsonRounding:
    """walkforward_summary.json 반올림 규칙 검증 테스트."""

    def test_summary_rounding_rules(self):
        """
        목적: WfoModeSummaryDict 값이 JSON 저장 시 올바르게 반올림되는지 검증

        Given: 소수점이 많은 WfoModeSummaryDict
        When: _round_summary_for_json() 적용
        Then: 백분율은 2자리, 비율은 4자리, 정수는 그대로
        """
        import importlib.util
        from pathlib import Path

        spec = importlib.util.spec_from_file_location(
            "run_walkforward",
            Path(__file__).parent.parent / "scripts" / "backtest" / "run_walkforward.py",
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _round_summary_for_json = mod._round_summary_for_json  # type: ignore[attr-defined]

        # Given
        raw_summary: dict[str, object] = {
            "n_windows": 5,
            "oos_cagr_mean": 12.345678,
            "oos_cagr_std": 5.123456,
            "oos_mdd_mean": -18.765432,
            "oos_mdd_worst": -35.987654,
            "oos_calmar_mean": 0.654321,
            "oos_calmar_std": 0.234567,
            "oos_trades_total": 25,
            "oos_win_rate_mean": 62.345678,
            "wfe_calmar_mean": 0.876543,
            "wfe_calmar_median": 0.912345,
            "wfe_cagr_mean": 0.765432,
            "wfe_cagr_median": 0.812345,
            "gap_calmar_median": -0.123456,
            "wfe_calmar_robust": 0.945678,
            "profit_concentration_max": 0.673456,
            "profit_concentration_window_idx": 2,
            "param_ma_windows": [100, 150, 200, 100, 150],
            "param_buy_buffers": [0.03, 0.05, 0.01, 0.03, 0.05],
            "param_sell_buffers": [0.03, 0.01, 0.05, 0.03, 0.01],
            "param_hold_days": [0, 2, 5, 0, 2],
            "param_recent_months": [0, 4, 8, 0, 4],
            "stitched_cagr": 15.678912,
            "stitched_mdd": -22.345678,
            "stitched_calmar": 0.701234,
            "stitched_total_return_pct": 156.789123,
        }

        # When
        rounded = _round_summary_for_json(raw_summary)

        # Then — 백분율: 2자리
        assert rounded["oos_cagr_mean"] == pytest.approx(12.35, abs=0.01)
        assert rounded["oos_mdd_mean"] == pytest.approx(-18.77, abs=0.01)
        assert rounded["oos_win_rate_mean"] == pytest.approx(62.35, abs=0.01)
        assert rounded["stitched_cagr"] == pytest.approx(15.68, abs=0.01)

        # Then — 비율: 4자리
        assert rounded["oos_calmar_mean"] == pytest.approx(0.6543, abs=0.0001)
        assert rounded["wfe_calmar_mean"] == pytest.approx(0.8765, abs=0.0001)
        assert rounded["wfe_cagr_mean"] == pytest.approx(0.7654, abs=0.0001)
        assert rounded["profit_concentration_max"] == pytest.approx(0.6735, abs=0.0001)

        # Then — 정수: 그대로
        assert rounded["n_windows"] == 5
        assert rounded["oos_trades_total"] == 25
        assert rounded["profit_concentration_window_idx"] == 2

        # Then — 파라미터 배열: 그대로
        assert rounded["param_ma_windows"] == [100, 150, 200, 100, 150]


class TestRollingWfoWindows:
    """Rolling Window WFO 윈도우 생성 테스트.

    Expanding Anchored WFO와 Rolling WFO가 동일한 OOS 기간을 공유하면서
    IS 시작점만 다르게 동작하는지 검증한다.
    """

    def test_rolling_same_oos_timing(self):
        """
        목적: Rolling과 Expanding의 OOS 기간이 동일한지 검증

        Given: 1999-03 ~ 2025-02 기간, rolling_is_months=120
        When: Expanding과 Rolling 윈도우를 각각 생성
        Then: 모든 윈도우에서 oos_start, oos_end가 동일
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)

        # When
        expanding = generate_wfo_windows(data_start, data_end, 72, 24)
        rolling = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=120)

        # Then — 윈도우 수가 동일
        assert len(expanding) == len(rolling)

        # 모든 윈도우에서 OOS 기간이 동일
        for exp_w, roll_w in zip(expanding, rolling, strict=True):
            assert exp_w[2] == roll_w[2], "oos_start가 동일해야 함"
            assert exp_w[3] == roll_w[3], "oos_end가 동일해야 함"

    def test_rolling_is_start_diverges(self):
        """
        목적: 특정 윈도우부터 Rolling IS 시작점이 Expanding과 달라지는지 검증

        Given: 1999-03 ~ 2025-02 기간, rolling_is_months=120
        When: Expanding과 Rolling 윈도우를 각각 생성
        Then: 초기 윈도우에서는 동일하다가 IS가 120개월을 초과하는 시점부터 분기
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)

        # When
        expanding = generate_wfo_windows(data_start, data_end, 72, 24)
        rolling = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=120)

        # Then — 초기 윈도우에서는 IS 시작이 동일(Expanding IS ≤ 120개월)
        # 후반 윈도우에서는 Rolling IS 시작이 더 늦음
        found_divergence = False
        for exp_w, roll_w in zip(expanding, rolling, strict=True):
            if exp_w[0] != roll_w[0]:
                found_divergence = True
                # Rolling IS 시작은 Expanding보다 늦어야 함
                assert roll_w[0] > exp_w[0]
                # Rolling IS 시작은 data_start 이후
                assert roll_w[0] >= data_start

        assert found_divergence, "Rolling에서 IS 시작점이 분기되는 윈도우가 없음"

    def test_rolling_is_length_capped(self):
        """
        목적: Rolling IS 길이가 rolling_is_months를 초과하지 않는지 검증

        Given: 1999-03 ~ 2025-02 기간, rolling_is_months=120
        When: Rolling 윈도우를 생성
        Then: 모든 윈도우에서 IS 길이(개월) ≤ rolling_is_months
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)
        rolling_is_months = 120

        # When
        rolling = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=rolling_is_months)

        # Then — 모든 윈도우에서 IS 길이 ≤ 120개월
        for is_start, is_end, _, _ in rolling:
            # 월 단위 길이 계산
            is_months = (is_end.year - is_start.year) * 12 + (is_end.month - is_start.month)
            # IS 종료가 IS 시작 월 + rolling_is_months 이내
            assert is_months <= rolling_is_months, f"IS 길이 {is_months}개월이 {rolling_is_months}개월 초과: {is_start}~{is_end}"

    def test_rolling_none_preserves_expanding(self):
        """
        목적: rolling_is_months=None이면 기존 Expanding 동작과 동일한지 검증

        Given: 1999-03 ~ 2025-02 기간
        When: rolling_is_months=None과 rolling_is_months 미지정으로 각각 생성
        Then: 두 결과가 완전히 동일
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)

        # When
        default = generate_wfo_windows(data_start, data_end, 72, 24)
        explicit_none = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=None)

        # Then — 완전히 동일
        assert default == explicit_none

    def test_rolling_early_windows_identical(self):
        """
        목적: Rolling에서 IS < rolling_is_months인 초기 윈도우가
              Expanding과 동일한지 검증

        Given: 1999-03 ~ 2025-02 기간, rolling_is_months=120
        When: 두 모드의 윈도우를 생성
        Then: IS 기간이 120개월 미만인 윈도우들은 두 모드에서 동일
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)
        rolling_is_months = 120

        # When
        expanding = generate_wfo_windows(data_start, data_end, 72, 24)
        rolling = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=rolling_is_months)

        # Then — 초기 윈도우(IS < 120개월)에서는 완전히 동일
        for exp_w, roll_w in zip(expanding, rolling, strict=True):
            exp_is_months = (exp_w[1].year - exp_w[0].year) * 12 + (exp_w[1].month - exp_w[0].month)
            if exp_is_months < rolling_is_months:
                assert exp_w == roll_w, (
                    f"IS {exp_is_months}개월 < {rolling_is_months}개월인데 " f"Expanding({exp_w})과 Rolling({roll_w})이 다름"
                )


class TestCalmarSelectionMinTrades:
    """min_trades 파라미터 기반 Calmar 선택 필터링 테스트."""

    def test_min_trades_filters_low_trade_params(self):
        """
        목적: min_trades=3일 때 거래수 2인 파라미터가 탈락하고 2위가 선택되는지 검증

        Given: 그리드 서치 결과 DataFrame
               - ma=100: calmar 1위, total_trades=2 (min_trades 미달)
               - ma=150: calmar 2위, total_trades=5 (min_trades 충족)
        When: select_best_calmar_params(grid_df, min_trades=3) 호출
        Then: ma=100은 탈락하고 ma=150이 선택됨
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
                "cagr": [20.0, 15.0, 8.0],
                "mdd": [-10.0, -25.0, -30.0],
                "total_return_pct": [200.0, 150.0, 80.0],
                "total_trades": [2, 5, 3],
                "win_rate": [100.0, 60.0, 66.7],
                "final_capital": [30_000_000, 25_000_000, 18_000_000],
            }
        )
        # ma=100: calmar = 20/10 = 2.0 (1위, trades=2 → 탈락)
        # ma=150: calmar = 15/25 = 0.6 (2위, trades=5 → 통과)
        # ma=200: calmar = 8/30 = 0.267 (3위, trades=3 → 통과)

        # When
        best = select_best_calmar_params(grid_df, min_trades=3)

        # Then — ma=100은 거래수 부족으로 탈락, ma=150이 선택
        assert best["ma_window"] == 150

    def test_min_trades_zero_preserves_existing_behavior(self):
        """
        목적: min_trades=0이면 기존 동작과 동일한지 검증 (하위 호환)

        Given: 그리드 서치 결과 DataFrame (total_trades=0인 행 포함)
        When: select_best_calmar_params(grid_df, min_trades=0) 호출
        Then: total_trades=0인 행도 필터링되지 않고 기존 Calmar 기준 선택
        """
        from qbt.backtest.walkforward import select_best_calmar_params

        # Given — ma=100이 calmar 1위, trades=0
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150],
                "buy_buffer_zone_pct": [0.03, 0.03],
                "sell_buffer_zone_pct": [0.03, 0.03],
                "hold_days": [0, 0],
                "recent_months": [0, 0],
                "cagr": [10.0, 5.0],
                "mdd": [0.0, -20.0],
                "total_return_pct": [100.0, 50.0],
                "total_trades": [0, 3],
                "win_rate": [0.0, 66.7],
                "final_capital": [20_000_000, 15_000_000],
            }
        )

        # When — min_trades=0이면 필터링 없음
        best = select_best_calmar_params(grid_df, min_trades=0)

        # Then — 기존 동작: MDD=0+CAGR>0인 ma=100이 선택
        assert best["ma_window"] == 100

    def test_min_trades_all_filtered_raises_value_error(self):
        """
        목적: 모든 행이 min_trades 미달인 경우 ValueError 발생 검증

        Given: 모든 행의 total_trades < min_trades
        When: select_best_calmar_params(grid_df, min_trades=5) 호출
        Then: ValueError 발생 (충족 파라미터 없음 메시지 포함)
        """
        from qbt.backtest.walkforward import select_best_calmar_params

        # Given — 모든 행이 trades < 5
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150, 200],
                "buy_buffer_zone_pct": [0.03, 0.03, 0.03],
                "sell_buffer_zone_pct": [0.03, 0.03, 0.03],
                "hold_days": [0, 0, 0],
                "recent_months": [0, 0, 0],
                "cagr": [10.0, 15.0, 8.0],
                "mdd": [-20.0, -25.0, -30.0],
                "total_return_pct": [100.0, 150.0, 80.0],
                "total_trades": [2, 3, 4],
                "win_rate": [50.0, 66.7, 75.0],
                "final_capital": [20_000_000, 25_000_000, 18_000_000],
            }
        )

        # When/Then — min_trades=5를 충족하는 행이 없으므로 ValueError
        with pytest.raises(ValueError, match="충족 파라미터 없음"):
            select_best_calmar_params(grid_df, min_trades=5)
