"""WFO 모드 요약 통계 테스트

calculate_wfo_mode_summary()의 OOS 통계, WFE, Profit Concentration, JSON 반올림을 검증한다.
"""

import pytest

from qbt.common_constants import EPSILON


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
        ]

        # When
        summary = calculate_wfo_mode_summary(results)

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
        summary = calculate_wfo_mode_summary(results, stitched_summary)

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
        summary = calculate_wfo_mode_summary(results, stitched_summary)

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
