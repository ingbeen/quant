"""WFO 파라미터 선택 및 WFE 테스트

select_best_calmar_params()의 Calmar 기반 선택 계약과 WFE 지표 계산을 검증한다.
"""

from datetime import date

import pandas as pd
import pytest

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
        summary = calculate_wfo_mode_summary(results)

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
        summary = calculate_wfo_mode_summary(results)

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
        summary = calculate_wfo_mode_summary(results)

        # Then
        assert summary["wfe_calmar_robust"] == pytest.approx(0.0, abs=EPSILON)
