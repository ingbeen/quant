"""WFO 파라미터 스케줄 및 실행 테스트

build_params_schedule()과 run_walkforward()의 핵심 계약을 검증한다.
"""

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL
from qbt.backtest.engines.backtest_engine import run_buffer_strategy
from qbt.backtest.strategies.buffer_zone import BufferStrategyParams, BufferZoneStrategy
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


def _make_trend_and_oscillating_df(
    n_is: int,
    n_oos: int,
    is_base_price: float = 100.0,
    is_daily_return: float = 0.001,
    oos_center: float = 60.0,
    oos_amplitude: float = 10.0,
) -> pd.DataFrame:
    """EMA 연속성 테스트용 데이터를 생성한다.

    IS 구간은 단조 상승 추세, OOS 구간은 낮은 가격대에서 정현파로 진동한다.
    전체 히스토리 EMA와 OOS-리셋 EMA가 크게 달라지도록 설계되어 있다.

    Args:
        n_is: IS 구간 거래일 수
        n_oos: OOS 구간 거래일 수
        is_base_price: IS 구간 시작 가격
        is_daily_return: IS 구간 일일 수익률 (기본 0.1%)
        oos_center: OOS 구간 진동 중심 가격
        oos_amplitude: OOS 구간 진동 진폭

    Returns:
        IS(상승) + OOS(진동) OHLCV DataFrame
    """
    dates: list[date] = []
    prices: list[float] = []
    p = is_base_price
    d = date(2000, 1, 3)
    for i in range(n_is + n_oos):
        while d.weekday() >= 5:
            d = d + timedelta(days=1)
        dates.append(d)
        if i < n_is:
            prices.append(round(p, 6))
            p *= 1 + is_daily_return
        else:
            oos_i = i - n_is
            prices.append(round(oos_center + oos_amplitude * math.sin(oos_i * 0.4), 6))
        d = d + timedelta(days=1)

    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [round(px * 0.999, 6) for px in prices],
            COL_HIGH: [round(px * 1.01, 6) for px in prices],
            COL_LOW: [round(px * 0.99, 6) for px in prices],
            COL_CLOSE: prices,
            COL_VOLUME: [1_000_000] * len(prices),
        }
    )


class TestEmaContiniuty:
    """EMA 연속성 인바리언트 테스트.

    핵심 인바리언트:
    "OOS 구간의 EMA 값은 전체 히스토리 기반으로 계산된 EMA를 해당 구간만 잘랐을 때의 값과 동일해야 한다."

    현재 구현은 이 인바리언트를 위반한다 (Phase 0에서 FAILED 확인).
    """

    def test_oos_ema_matches_full_history_ema(self):
        """
        목적: run_walkforward() OOS 평가의 EMA가 전체 히스토리 기반 EMA와 일치함을 검증

        Given: IS 상승(~220) + OOS 진동(60±10) 데이터.
               전체 히스토리 EMA는 OOS 기간에 ~200+를 유지하여 OOS 가격과 크게 달라진다.
        When:
          1) raw_df로 run_walkforward() 실행 — 현재 구현은 OOS에서 EMA를 리셋한다
          2) 전체 히스토리 MA를 미리 계산한 full_df_with_ma로 run_walkforward() 실행
             — MA 컬럼이 이미 있으므로 OOS 슬라이스가 전체 히스토리 EMA를 유지한다
        Then: 두 실행의 첫 번째 OOS 윈도우 oos_calmar가 동일해야 한다.
              현재 구현에서는 OOS EMA 리셋으로 결과가 달라지므로 이 테스트가 실패한다.
        """
        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.walkforward import run_walkforward

        # Given — IS 상승(800 거래일, 100→222) + OOS 진동(300 거래일, 60±10)
        n_is = 800
        raw_df = _make_trend_and_oscillating_df(n_is=n_is, n_oos=300)
        ma_window = 100

        # 전체 히스토리 MA 사전 계산 (두 번째 실행에서 OOS 슬라이스에 포함됨)
        full_df_with_ma = add_single_moving_average(raw_df.copy(), ma_window, ma_type="ema")

        wfo_kwargs: dict[str, object] = {
            "trade_df": raw_df,
            "ma_window_list": [ma_window],
            "buy_buffer_zone_pct_list": [0.03],
            "sell_buffer_zone_pct_list": [0.03],
            "hold_days_list": [0],
            "initial_is_months": 38,  # ~800 거래일 → IS가 상승 구간 전체를 포함
            "oos_months": 6,
            "min_trades": 0,
        }

        # When — 두 가지 실행
        # 실행 1: raw_df (MA 미포함) — 현재 구현은 OOS에서 EMA 리셋 발생
        results_raw = run_walkforward(signal_df=raw_df, **wfo_kwargs)  # type: ignore[arg-type]

        # 실행 2: full_df_with_ma (MA 포함) — OOS 슬라이스에 전체 히스토리 EMA가 담긴다
        results_with_ma = run_walkforward(signal_df=full_df_with_ma, **wfo_kwargs)  # type: ignore[arg-type]

        # Then — 두 실행의 첫 번째 OOS 윈도우 oos_calmar가 동일해야 한다
        assert len(results_raw) >= 1
        assert len(results_with_ma) >= 1
        first_raw = results_raw[0]
        first_with_ma = results_with_ma[0]
        assert first_raw["oos_calmar"] == pytest.approx(first_with_ma["oos_calmar"], abs=0.01)

    def test_stitched_equity_ema_matches_full_history_ema(self):
        """
        목적: _run_stitched_equity() stitched 자본곡선의 EMA가 전체 히스토리 기반 EMA와 일치함을 검증

        Given: IS 상승(800 거래일) + OOS 진동(300 거래일) 데이터 + 1개 윈도우 결과
        When:
          - _run_stitched_equity(raw_df, ...) 실행 → OOS에서 EMA를 리셋하여 stitched 자본곡선 생성
          - 전체 히스토리 EMA 기반 참조 실행 → OOS에서 거래 없음 (EMA가 OOS 가격과 크게 달라서)
        Then: stitched CAGR과 참조 CAGR이 동일해야 한다.
              현재 구현에서는 OOS EMA 리셋으로 결과가 달라지므로 이 테스트가 실패한다.
        """
        import importlib.util
        from pathlib import Path

        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL
        from qbt.backtest.engines.backtest_engine import run_backtest
        from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy

        # Given
        n_is = 800
        raw_df = _make_trend_and_oscillating_df(n_is=n_is, n_oos=300)
        ma_window = 100
        ma_col = f"ma_{ma_window}"

        oos_start_date = raw_df.iloc[n_is][COL_DATE]
        oos_end_date = raw_df.iloc[-1][COL_DATE]

        # WFO 1개 윈도우 결과 (파라미터 스케줄 구성에 필요한 최소 구조)
        window_results = [
            {
                "window_idx": 0,
                "is_start": str(raw_df.iloc[0][COL_DATE]),
                "is_end": str(raw_df.iloc[n_is - 1][COL_DATE]),
                "oos_start": str(oos_start_date),
                "oos_end": str(oos_end_date),
                "best_ma_window": ma_window,
                "best_buy_buffer_zone_pct": 0.03,
                "best_sell_buffer_zone_pct": 0.03,
                "best_hold_days": 0,
                "is_cagr": 10.0,
                "is_mdd": -5.0,
                "is_calmar": 2.0,
                "is_trades": 10,
                "is_win_rate": 60.0,
                "oos_cagr": 5.0,
                "oos_mdd": -3.0,
                "oos_calmar": 1.67,
                "oos_trades": 5,
                "oos_win_rate": 60.0,
                "wfe_calmar": 0.83,
                "wfe_cagr": 0.5,
            }
        ]

        # 참조: 전체 히스토리 EMA 기반 OOS 백테스트
        full_df_with_ma = add_single_moving_average(raw_df.copy(), ma_window, ma_type="ema")
        oos_mask = (raw_df[COL_DATE] >= oos_start_date) & (raw_df[COL_DATE] <= oos_end_date)
        oos_signal_ref = full_df_with_ma[oos_mask].reset_index(drop=True)
        oos_trade_ref = raw_df[oos_mask].reset_index(drop=True)

        ref_strategy = BufferZoneStrategy(
            ma_col=ma_col,
            buy_buffer_pct=0.03,
            sell_buffer_pct=0.03,
            hold_days=0,
        )
        _, _, ref_summary = run_backtest(
            ref_strategy,
            oos_signal_ref,
            oos_trade_ref,
            DEFAULT_INITIAL_CAPITAL,
            log_trades=False,
        )
        ref_cagr = float(ref_summary["cagr"])

        # _run_stitched_equity를 importlib으로 동적 로딩 (scripts/ 패키지 미구성)
        script_path = Path(__file__).parent.parent / "scripts" / "backtest" / "run_walkforward.py"
        spec = importlib.util.spec_from_file_location("run_walkforward_script", script_path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _run_stitched_equity = mod._run_stitched_equity

        # When — _run_stitched_equity 실행 (raw_df: MA 미포함)
        _, stitched_summary = _run_stitched_equity(
            raw_df,
            raw_df,
            window_results,
            DEFAULT_INITIAL_CAPITAL,
        )
        stitched_cagr = float(stitched_summary["cagr"])

        # Then — stitched CAGR과 참조 CAGR이 동일해야 한다
        assert stitched_cagr == pytest.approx(ref_cagr, abs=1.0)


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
        )

        # 전환점에서 MA 100 BufferZoneStrategy로 변경
        switch_date = df.iloc[250][COL_DATE]
        params_schedule = {
            switch_date: BufferZoneStrategy(
                ma_col="ma_100",
                buy_buffer_pct=0.05,
                sell_buffer_pct=0.01,
                hold_days=2,
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
        목적: MA 윈도우 변경 시 새 BufferZoneStrategy로 전환됨을 검증

        Given: MA 50 → MA 100으로 전환하는 schedule
        When: run_buffer_strategy 실행
        Then: 에러 없이 실행 완료, equity_df에 전환점 이후 행이 존재
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
        )

        switch_date = df.iloc[300][COL_DATE]
        # params_schedule: BufferZoneStrategy 객체로 직접 지정
        params_schedule = {
            switch_date: BufferZoneStrategy(
                ma_col="ma_100",
                buy_buffer_pct=0.05,
                sell_buffer_pct=0.05,
                hold_days=0,
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

        # Then — 전환점 이후 행이 존재하고 정상 실행됨을 검증
        # (equity_df에 band 컬럼은 없음: band enrichment는 runners.py 레이어에서 수행)
        after_switch = equity_df[equity_df[COL_DATE] >= switch_date]
        assert len(after_switch) > 0
        assert "equity" in equity_df.columns
        assert "position" in equity_df.columns


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
        initial_strategy, schedule = build_params_schedule(results)

        # Then — initial_strategy는 첫 윈도우 기반 BufferZoneStrategy
        # _ma_col, _buy_buffer_pct는 private 속성이지만 파라미터 계약 검증용으로 접근
        assert initial_strategy._ma_col == "ma_100"  # type: ignore[attr-defined]
        assert initial_strategy._buy_buffer_pct == pytest.approx(0.03, abs=EPSILON)  # type: ignore[attr-defined]

        # schedule 키는 2번째, 3번째 윈도우의 oos_start
        assert len(schedule) == 2
        assert date(2008, 1, 1) in schedule
        assert date(2010, 1, 1) in schedule

        # 2번째 윈도우 파라미터 검증
        assert schedule[date(2008, 1, 1)]._ma_col == "ma_150"  # type: ignore[attr-defined]
        assert schedule[date(2008, 1, 1)]._buy_buffer_pct == pytest.approx(0.05, abs=EPSILON)  # type: ignore[attr-defined]

        # 3번째 윈도우 파라미터 검증
        assert schedule[date(2010, 1, 1)]._ma_col == "ma_200"  # type: ignore[attr-defined]
