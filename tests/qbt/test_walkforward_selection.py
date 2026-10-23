"""WFO 파라미터 선택 및 WFE 요약 테스트

select_best_calmar_params()의 Calmar 기반 선택 계약과 모드 요약의 WFE Calmar Robust 를 검증한다.
윈도우마다 WFE 를 계산하는 run_walkforward 는 test_walkforward_schedule.py 가 지킨다.
"""

import pandas as pd
import pytest

from qbt.backtest.analysis import calculate_calmar
from qbt.backtest.walkforward import calculate_wfo_mode_summary, select_best_calmar_params
from qbt.common_constants import EPSILON

# 모드 요약에 넘기는 이어 붙인 자본곡선 요약 — 이 파일의 요약 테스트는 윈도우 통계만 본다
_STITCHED_SUMMARY: dict[str, object] = {"initial_capital": 10000.0, "cagr": 0.0, "mdd": -1.0, "calmar": 0.0}

# 윈도우 셋 — IS Calmar 0.5 · -0.2 · 0.3, wfe_calmar 1.06 · -1.25 · 1.3333, wfe_cagr 0.8 · -0.6667 · 0.6667 (두 지표 값이 서로 다름)
_THREE_WINDOWS: list[dict[str, object]] = [
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


class TestCalmarSelection:
    """Calmar 기준 최적 파라미터 선택 테스트."""

    def test_mdd_zero_with_positive_cagr_is_best(self):
        """
        목적: MDD=0이고 CAGR>0인 조합이 1위다 (그리드가 calculate_calmar 로 채운 Calmar 를 그대로 쓴다)

        Given: 그리드 서치 결과 DataFrame (MDD=0 + CAGR>0인 행 포함, calmar 는 calculate_calmar)
        When: select_best_calmar_params 호출
        Then: MDD=0 + CAGR>0인 행이 1위
        """
        # Given
        cagr = [5.0, 10.0, 3.0]
        mdd = [-20.0, 0.0, -10.0]
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150, 200],
                "buy_buffer_zone_pct": [0.03, 0.03, 0.03],
                "sell_buffer_zone_pct": [0.03, 0.03, 0.03],
                "hold_days": [0, 0, 0],
                "cagr": cagr,
                "mdd": mdd,
                "calmar": [calculate_calmar(c, m) for c, m in zip(cagr, mdd, strict=True)],
                "total_trades": [5, 3, 3],
                "win_rate": [60.0, 0.0, 66.7],
            }
        )

        # When
        best = select_best_calmar_params(grid_df)

        # Then — MDD=0 + CAGR>0인 ma_window=150이 선택됨
        assert best["ma_window"] == 150

    def test_tied_calmar_picks_earlier_row(self):
        """
        목적: Calmar 가 같으면 grid_df 에서 앞선 행을 고른다 (run_grid_search 가 안정 정렬이라 그리드 입력 순서)

        Given: Calmar 가 같은 두 행 (ma=150 이 앞)
        When: select_best_calmar_params 호출
        Then: 앞선 ma=150 이 선택됨
        """
        # Given
        grid_df = pd.DataFrame(
            {
                "ma_window": [150, 100],
                "buy_buffer_zone_pct": [0.03, 0.03],
                "sell_buffer_zone_pct": [0.03, 0.03],
                "hold_days": [0, 0],
                "cagr": [6.0, 6.0],
                "mdd": [-12.0, -12.0],
                "calmar": [0.5, 0.5],
                "total_trades": [3, 4],
                "win_rate": [0.0, 0.0],
            }
        )

        # When
        best = select_best_calmar_params(grid_df)

        # Then
        assert best["ma_window"] == 150

    def test_normal_calmar_selection(self):
        """
        목적: Calmar 가 가장 큰 행의 파라미터를 고른다

        Given: Calmar 가 0.5 · 0.6 · 0.267 인 행들
        When: select_best_calmar_params 호출
        Then: Calmar 0.6 행의 파라미터 넷이 반환됨
        """
        # Given
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150, 200],
                "buy_buffer_zone_pct": [0.03, 0.05, 0.01],
                "sell_buffer_zone_pct": [0.03, 0.01, 0.05],
                "hold_days": [0, 2, 5],
                "cagr": [10.0, 15.0, 8.0],
                "mdd": [-20.0, -25.0, -30.0],
                "calmar": [0.5, 0.6, 8.0 / 30.0],
                "total_trades": [5, 8, 3],
                "win_rate": [60.0, 62.5, 66.7],
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
        # Given
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150, 200],
                "buy_buffer_zone_pct": [0.03, 0.03, 0.03],
                "sell_buffer_zone_pct": [0.03, 0.03, 0.03],
                "hold_days": [0, 0, 0],
                "cagr": [20.0, 15.0, 8.0],
                "mdd": [-10.0, -25.0, -30.0],
                "calmar": [2.0, 0.6, 8.0 / 30.0],
                "total_trades": [2, 5, 3],
                "win_rate": [100.0, 60.0, 66.7],
            }
        )

        # When
        best = select_best_calmar_params(grid_df, min_trades=3)

        # Then — ma=100은 거래수 부족으로 탈락, ma=150이 선택
        assert best["ma_window"] == 150

    def test_min_trades_zero_keeps_all_rows(self):
        """
        목적: min_trades=0이면 거래수 0인 행도 후보다

        Given: Calmar 1위가 total_trades=0인 그리드 결과
        When: select_best_calmar_params(grid_df, min_trades=0) 호출
        Then: total_trades=0인 1위 행이 선택된다
        """
        # Given — ma=100이 calmar 1위, trades=0
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150],
                "buy_buffer_zone_pct": [0.03, 0.03],
                "sell_buffer_zone_pct": [0.03, 0.03],
                "hold_days": [0, 0],
                "cagr": [10.0, 5.0],
                "mdd": [0.0, -20.0],
                "calmar": [calculate_calmar(10.0, 0.0), 0.25],
                "total_trades": [0, 3],
                "win_rate": [0.0, 66.7],
            }
        )

        # When
        best = select_best_calmar_params(grid_df, min_trades=0)

        # Then
        assert best["ma_window"] == 100

    def test_min_trades_all_filtered_raises_value_error(self):
        """
        목적: 모든 행이 min_trades 미달인 경우 ValueError 발생 검증

        Given: 모든 행의 total_trades < min_trades
        When: select_best_calmar_params(grid_df, min_trades=5) 호출
        Then: ValueError 발생 (충족 파라미터 없음 메시지 포함)
        """
        # Given — 모든 행이 trades < 5
        grid_df = pd.DataFrame(
            {
                "ma_window": [100, 150, 200],
                "buy_buffer_zone_pct": [0.03, 0.03, 0.03],
                "sell_buffer_zone_pct": [0.03, 0.03, 0.03],
                "hold_days": [0, 0, 0],
                "cagr": [10.0, 15.0, 8.0],
                "mdd": [-20.0, -25.0, -30.0],
                "calmar": [0.5, 0.6, 8.0 / 30.0],
                "total_trades": [2, 3, 4],
                "win_rate": [50.0, 66.7, 75.0],
            }
        )

        # When/Then — min_trades=5를 충족하는 행이 없으므로 ValueError
        with pytest.raises(ValueError, match="충족 파라미터 없음"):
            select_best_calmar_params(grid_df, min_trades=5)


class TestWfeCalmarRobust:
    """WFE Calmar Robust 계산 검증 테스트."""

    def test_robust_excludes_non_positive_is_calmar(self):
        """
        목적: IS Calmar ≤ 0인 윈도우를 제외하고 WFE Calmar 중앙값 계산

        Given: 3개 윈도우 (IS Calmar: 0.5, -0.2, 0.3)
        When: calculate_wfo_mode_summary() 호출
        Then: wfe_calmar_robust = IS Calmar > 0인 윈도우(0.5, 0.3)만의 wfe_calmar 중앙값
        """
        # Given — IS Calmar > 0: 윈도우 0, 2만 해당
        results = _THREE_WINDOWS

        # When
        summary = calculate_wfo_mode_summary(results, _STITCHED_SUMMARY, [10000.0] * len(results))

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
        summary = calculate_wfo_mode_summary(results, _STITCHED_SUMMARY, [10000.0] * len(results))

        # Then
        assert summary["wfe_calmar_robust"] == pytest.approx(0.0, abs=EPSILON)


class TestWfeMeanMedian:
    """모드 요약의 WFE 평균 · 중앙값 검증 테스트."""

    def test_mean_and_median_use_each_metric(self):
        """
        목적: wfe_calmar 평균 · 중앙값은 윈도우의 wfe_calmar 로, wfe_cagr 평균 · 중앙값은 wfe_cagr 로 계산하는지 검증
              (두 지표의 윈도우 값이 서로 달라 지표를 뒤바꾸거나 평균 · 중앙값을 바꾸면 갈린다)

        Given: _THREE_WINDOWS (wfe_calmar 1.06 · -1.25 · 1.3333, wfe_cagr 0.8 · -0.6667 · 0.6667)
        When: calculate_wfo_mode_summary() 호출
        Then: wfe_calmar 평균 (1.06 - 1.25 + 1.3333) / 3 · 중앙값 1.06, wfe_cagr 평균 (0.8 - 0.6667 + 0.6667) / 3 · 중앙값 0.6667
        """
        # When
        summary = calculate_wfo_mode_summary(_THREE_WINDOWS, _STITCHED_SUMMARY, [10000.0] * len(_THREE_WINDOWS))

        # Then
        assert summary["wfe_calmar_mean"] == pytest.approx((1.06 - 1.25 + 1.3333) / 3, abs=EPSILON)
        assert summary["wfe_calmar_median"] == pytest.approx(1.06, abs=EPSILON)
        assert summary["wfe_cagr_mean"] == pytest.approx((0.8 - 0.6667 + 0.6667) / 3, abs=EPSILON)
        assert summary["wfe_cagr_median"] == pytest.approx(0.6667, abs=EPSILON)
