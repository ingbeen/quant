"""Expanding vs Rolling WFO 비교 실험 테스트

build_window_comparison, build_comparison_summary 유닛 테스트 및
run_single_wfo_mode 통합 테스트를 포함한다.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from qbt.backtest.types import WfoModeSummaryDict, WfoWindowResultDict
from qbt.backtest.wfo_comparison import (
    WfoComparisonResultDict,
    build_comparison_summary,
    build_window_comparison,
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
            d = d + timedelta(days=1)
        dates.append(d)
        prices.append(current)
        current = current * (1 + daily_return)
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


def _make_wfo_window_result(
    idx: int,
    is_start: str,
    oos_cagr: float,
    oos_mdd: float,
    oos_calmar: float,
    oos_trades: int,
    oos_win_rate: float = 50.0,
) -> WfoWindowResultDict:
    """테스트용 WFO 윈도우 결과를 생성한다.

    Args:
        idx: 윈도우 인덱스
        is_start: IS 시작일 문자열
        oos_cagr: OOS CAGR
        oos_mdd: OOS MDD
        oos_calmar: OOS Calmar
        oos_trades: OOS 거래수
        oos_win_rate: OOS 승률

    Returns:
        WfoWindowResultDict
    """
    return {
        "window_idx": idx,
        "is_start": is_start,
        "is_end": "2005-12-31",
        "oos_start": f"200{6 + idx * 2}-01-01",
        "oos_end": f"200{7 + idx * 2}-12-31",
        "best_ma_window": 200,
        "best_buy_buffer_zone_pct": 0.03,
        "best_sell_buffer_zone_pct": 0.03,
        "best_hold_days": 0,
        "best_recent_months": 0,
        "is_cagr": 10.0,
        "is_mdd": -15.0,
        "is_calmar": 0.67,
        "is_trades": 5,
        "is_win_rate": 60.0,
        "oos_cagr": oos_cagr,
        "oos_mdd": oos_mdd,
        "oos_calmar": oos_calmar,
        "oos_trades": oos_trades,
        "oos_win_rate": oos_win_rate,
        "wfe_calmar": oos_calmar / 0.67 if abs(0.67) > EPSILON else 0.0,
        "wfe_cagr": oos_cagr / 10.0,
    }


def _make_mode_summary(
    n_windows: int = 3,
    stitched_cagr: float = 12.0,
    stitched_mdd: float = -20.0,
    stitched_calmar: float = 0.6,
    oos_cagr_mean: float = 10.0,
    oos_calmar_mean: float = 0.5,
) -> WfoModeSummaryDict:
    """테스트용 모드 요약을 생성한다."""
    return {
        "n_windows": n_windows,
        "oos_cagr_mean": oos_cagr_mean,
        "oos_cagr_std": 5.0,
        "oos_mdd_mean": -15.0,
        "oos_mdd_worst": -30.0,
        "oos_calmar_mean": oos_calmar_mean,
        "oos_calmar_std": 0.2,
        "oos_trades_total": 15,
        "oos_win_rate_mean": 55.0,
        "wfe_calmar_mean": 0.8,
        "wfe_calmar_median": 0.75,
        "wfe_cagr_mean": 0.7,
        "wfe_cagr_median": 0.65,
        "gap_calmar_median": -0.1,
        "wfe_calmar_robust": 0.85,
        "profit_concentration_max": 0.4,
        "profit_concentration_window_idx": 1,
        "param_ma_windows": [200] * n_windows,
        "param_buy_buffers": [0.03] * n_windows,
        "param_sell_buffers": [0.03] * n_windows,
        "param_hold_days": [0] * n_windows,
        "param_recent_months": [0] * n_windows,
        "stitched_cagr": stitched_cagr,
        "stitched_mdd": stitched_mdd,
        "stitched_calmar": stitched_calmar,
        "stitched_total_return_pct": 150.0,
    }


def _make_comparison_result(
    window_type: str,
    rolling_is_months: int | None,
    window_results: list[WfoWindowResultDict],
    mode_summary: WfoModeSummaryDict,
) -> WfoComparisonResultDict:
    """테스트용 비교 결과를 생성한다."""
    return {
        "window_type": window_type,
        "rolling_is_months": rolling_is_months,
        "window_results": window_results,
        "mode_summary": mode_summary,
    }


class TestBuildWindowComparison:
    """build_window_comparison() 함수 테스트."""

    def test_window_count_mismatch_raises_value_error(self):
        """
        목적: 두 모드의 윈도우 수가 다르면 ValueError 발생

        Given: Expanding 3개 윈도우, Rolling 2개 윈도우
        When: build_window_comparison() 호출
        Then: ValueError 발생
        """
        # Given
        exp_results = [_make_wfo_window_result(i, "1999-03-01", 10.0, -15.0, 0.67, 3) for i in range(3)]
        roll_results = [_make_wfo_window_result(i, "2002-03-01", 8.0, -18.0, 0.44, 2) for i in range(2)]

        expanding = _make_comparison_result("expanding", None, exp_results, _make_mode_summary())
        rolling = _make_comparison_result("rolling", 120, roll_results, _make_mode_summary())

        # When/Then
        with pytest.raises(ValueError, match="윈도우 수 불일치"):
            build_window_comparison(expanding, rolling)

    def test_difference_calculation(self):
        """
        목적: 차이 계산(Expanding - Rolling)이 올바른지 검증

        Given: 2개 윈도우, Expanding CAGR=[10, 5], Rolling CAGR=[8, 7]
        When: build_window_comparison() 호출
        Then: diff_oos_cagr = [2, -2]
        """
        # Given
        exp_results = [
            _make_wfo_window_result(0, "1999-03-01", 10.0, -15.0, 0.67, 3),
            _make_wfo_window_result(1, "1999-03-01", 5.0, -20.0, 0.25, 2),
        ]
        roll_results = [
            _make_wfo_window_result(0, "1999-03-01", 8.0, -18.0, 0.44, 3),
            _make_wfo_window_result(1, "2002-03-01", 7.0, -12.0, 0.58, 4),
        ]

        expanding = _make_comparison_result("expanding", None, exp_results, _make_mode_summary(n_windows=2))
        rolling = _make_comparison_result("rolling", 120, roll_results, _make_mode_summary(n_windows=2))

        # When
        df = build_window_comparison(expanding, rolling)

        # Then
        assert len(df) == 2
        assert df.iloc[0]["diff_oos_cagr"] == pytest.approx(2.0, abs=0.01)
        assert df.iloc[1]["diff_oos_cagr"] == pytest.approx(-2.0, abs=0.01)

    def test_is_identical_flag(self):
        """
        목적: IS가 동일한 윈도우와 다른 윈도우의 is_identical 플래그 검증

        Given: 2개 윈도우, 1번째 동일 IS, 2번째 다른 IS
        When: build_window_comparison() 호출
        Then: is_identical = [True, False]
        """
        # Given
        exp_results = [
            _make_wfo_window_result(0, "1999-03-01", 10.0, -15.0, 0.67, 3),
            _make_wfo_window_result(1, "1999-03-01", 5.0, -20.0, 0.25, 2),
        ]
        roll_results = [
            _make_wfo_window_result(0, "1999-03-01", 8.0, -18.0, 0.44, 3),
            _make_wfo_window_result(1, "2002-03-01", 7.0, -12.0, 0.58, 4),
        ]

        expanding = _make_comparison_result("expanding", None, exp_results, _make_mode_summary(n_windows=2))
        rolling = _make_comparison_result("rolling", 120, roll_results, _make_mode_summary(n_windows=2))

        # When
        df = build_window_comparison(expanding, rolling)

        # Then
        assert bool(df.iloc[0]["is_identical"]) is True
        assert bool(df.iloc[1]["is_identical"]) is False

    def test_row_structure(self):
        """
        목적: 결과 DataFrame의 컬럼 구조를 검증

        Given: 1개 윈도우의 비교 결과
        When: build_window_comparison() 호출
        Then: 필수 컬럼 17개가 모두 존재
        """
        # Given
        exp_results = [_make_wfo_window_result(0, "1999-03-01", 10.0, -15.0, 0.67, 3)]
        roll_results = [_make_wfo_window_result(0, "1999-03-01", 8.0, -18.0, 0.44, 2)]

        expanding = _make_comparison_result("expanding", None, exp_results, _make_mode_summary(n_windows=1))
        rolling = _make_comparison_result("rolling", 120, roll_results, _make_mode_summary(n_windows=1))

        # When
        df = build_window_comparison(expanding, rolling)

        # Then
        required_columns = {
            "window_idx",
            "oos_start",
            "oos_end",
            "expanding_is_start",
            "rolling_is_start",
            "is_identical",
            "exp_oos_cagr",
            "exp_oos_mdd",
            "exp_oos_calmar",
            "exp_oos_trades",
            "roll_oos_cagr",
            "roll_oos_mdd",
            "roll_oos_calmar",
            "roll_oos_trades",
            "diff_oos_cagr",
            "diff_oos_mdd",
            "diff_oos_calmar",
        }
        assert required_columns.issubset(set(df.columns))


class TestBuildComparisonSummary:
    """build_comparison_summary() 함수 테스트."""

    def test_wins_count(self):
        """
        목적: Expanding/Rolling 우위 카운트가 올바른지 검증

        Given: 2개 윈도우, Expanding CAGR이 모두 우위
        When: build_comparison_summary() 호출
        Then: exp_wins_cagr=2, roll_wins_cagr=0
        """
        # Given
        exp_results = [
            _make_wfo_window_result(0, "1999-03-01", 10.0, -15.0, 0.67, 3),
            _make_wfo_window_result(1, "1999-03-01", 8.0, -12.0, 0.67, 2),
        ]
        roll_results = [
            _make_wfo_window_result(0, "1999-03-01", 5.0, -20.0, 0.25, 3),
            _make_wfo_window_result(1, "2002-03-01", 3.0, -18.0, 0.17, 2),
        ]

        expanding = _make_comparison_result("expanding", None, exp_results, _make_mode_summary(n_windows=2))
        rolling = _make_comparison_result("rolling", 120, roll_results, _make_mode_summary(n_windows=2))

        comparison_df = build_window_comparison(expanding, rolling)

        # When
        summary = build_comparison_summary(expanding, rolling, comparison_df)

        # Then
        assert summary["exp_wins_cagr"] == 2
        assert summary["roll_wins_cagr"] == 0

    def test_required_fields(self):
        """
        목적: 요약에 필수 필드가 모두 존재하는지 검증

        Given: 2개 윈도우의 비교 결과
        When: build_comparison_summary() 호출
        Then: 필수 키 22개 이상 존재
        """
        # Given
        exp_results = [
            _make_wfo_window_result(0, "1999-03-01", 10.0, -15.0, 0.67, 3),
            _make_wfo_window_result(1, "1999-03-01", 5.0, -20.0, 0.25, 2),
        ]
        roll_results = [
            _make_wfo_window_result(0, "1999-03-01", 8.0, -18.0, 0.44, 3),
            _make_wfo_window_result(1, "2002-03-01", 7.0, -12.0, 0.58, 4),
        ]

        expanding = _make_comparison_result("expanding", None, exp_results, _make_mode_summary(n_windows=2))
        rolling = _make_comparison_result("rolling", 120, roll_results, _make_mode_summary(n_windows=2))

        comparison_df = build_window_comparison(expanding, rolling)

        # When
        summary = build_comparison_summary(expanding, rolling, comparison_df)

        # Then
        required_keys = {
            "rolling_is_months",
            "n_windows",
            "n_identical",
            "n_diverged",
            "exp_stitched_cagr",
            "exp_stitched_mdd",
            "exp_stitched_calmar",
            "roll_stitched_cagr",
            "roll_stitched_mdd",
            "roll_stitched_calmar",
            "exp_wins_cagr",
            "roll_wins_cagr",
            "exp_wins_calmar",
            "roll_wins_calmar",
            "diff_cagr_mean",
            "diff_cagr_median",
            "diff_calmar_mean",
            "diff_calmar_median",
            "diverged_diff_cagr_mean",
            "diverged_diff_calmar_mean",
            "exp_oos_cagr_mean",
            "roll_oos_cagr_mean",
        }
        assert required_keys.issubset(set(summary.keys()))

    def test_diff_mean_and_median(self):
        """
        목적: 차이 통계(평균, 중앙값)가 올바른지 검증

        Given: 2개 윈도우, diff_cagr = [2.0, 6.0]
        When: build_comparison_summary() 호출
        Then: diff_cagr_mean = 4.0, diff_cagr_median = 4.0
        """
        # Given
        exp_results = [
            _make_wfo_window_result(0, "1999-03-01", 10.0, -15.0, 0.67, 3),
            _make_wfo_window_result(1, "1999-03-01", 12.0, -20.0, 0.60, 2),
        ]
        roll_results = [
            _make_wfo_window_result(0, "1999-03-01", 8.0, -18.0, 0.44, 3),
            _make_wfo_window_result(1, "2002-03-01", 6.0, -15.0, 0.40, 2),
        ]

        expanding = _make_comparison_result("expanding", None, exp_results, _make_mode_summary(n_windows=2))
        rolling = _make_comparison_result("rolling", 120, roll_results, _make_mode_summary(n_windows=2))

        comparison_df = build_window_comparison(expanding, rolling)

        # When
        summary = build_comparison_summary(expanding, rolling, comparison_df)

        # Then — diff = [10-8, 12-6] = [2.0, 6.0]
        assert summary["diff_cagr_mean"] == pytest.approx(4.0, abs=0.01)
        assert summary["diff_cagr_median"] == pytest.approx(4.0, abs=0.01)

    def test_identical_and_diverged_counts(self):
        """
        목적: n_identical, n_diverged 카운트가 올바른지 검증

        Given: 3개 윈도우 중 1개 동일, 2개 분기
        When: build_comparison_summary() 호출
        Then: n_identical=1, n_diverged=2
        """
        # Given
        exp_results = [
            _make_wfo_window_result(0, "1999-03-01", 10.0, -15.0, 0.67, 3),
            _make_wfo_window_result(1, "1999-03-01", 8.0, -20.0, 0.40, 2),
            _make_wfo_window_result(2, "1999-03-01", 5.0, -12.0, 0.42, 2),
        ]
        roll_results = [
            _make_wfo_window_result(0, "1999-03-01", 9.0, -16.0, 0.56, 3),
            _make_wfo_window_result(1, "2002-03-01", 7.0, -18.0, 0.39, 2),
            _make_wfo_window_result(2, "2004-03-01", 6.0, -14.0, 0.43, 3),
        ]

        expanding = _make_comparison_result("expanding", None, exp_results, _make_mode_summary(n_windows=3))
        rolling = _make_comparison_result("rolling", 120, roll_results, _make_mode_summary(n_windows=3))

        comparison_df = build_window_comparison(expanding, rolling)

        # When
        summary = build_comparison_summary(expanding, rolling, comparison_df)

        # Then
        assert summary["n_identical"] == 1
        assert summary["n_diverged"] == 2


class TestRunSingleWfoMode:
    """run_single_wfo_mode() 통합 테스트 (소규모 데이터)."""

    def test_returns_correct_structure(self):
        """
        목적: 소규모 데이터로 run_single_wfo_mode()가 올바른 구조를 반환하는지 검증

        Given: 약 5년 분량의 주식 데이터 (IS=6개월, OOS=3개월로 축소)
        When: run_single_wfo_mode(rolling_is_months=None) 실행
        Then: 결과에 window_type, rolling_is_months, window_results, mode_summary 존재
        """
        from qbt.backtest.wfo_comparison import run_single_wfo_mode

        # Given — 약 5년 분량 (1250 거래일)
        df = _make_stock_df(date(2000, 1, 3), 1250, base_price=100.0, daily_return=0.0003)

        # When — Expanding 모드, 소규모 파라미터로 빠른 실행
        result = run_single_wfo_mode(
            signal_df=df,
            trade_df=df,
            rolling_is_months=None,
            initial_is_months=6,
            oos_months=3,
            ma_window_list=[50],
            buy_buffer_zone_pct_list=[0.03],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0],
            recent_months_list=[0],
            min_trades=0,
        )

        # Then — 구조 검증
        assert result["window_type"] == "expanding"
        assert result["rolling_is_months"] is None
        assert len(result["window_results"]) >= 1
        assert "stitched_cagr" in result["mode_summary"]

    def test_rolling_mode_returns_correct_structure(self):
        """
        목적: Rolling 모드도 올바른 구조를 반환하는지 검증

        Given: 약 5년 분량의 주식 데이터
        When: run_single_wfo_mode(rolling_is_months=12) 실행
        Then: window_type="rolling", rolling_is_months=12
        """
        from qbt.backtest.wfo_comparison import run_single_wfo_mode

        # Given
        df = _make_stock_df(date(2000, 1, 3), 1250, base_price=100.0, daily_return=0.0003)

        # When — Rolling 모드 (12개월 IS 제한)
        result = run_single_wfo_mode(
            signal_df=df,
            trade_df=df,
            rolling_is_months=12,
            initial_is_months=6,
            oos_months=3,
            ma_window_list=[50],
            buy_buffer_zone_pct_list=[0.03],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0],
            recent_months_list=[0],
            min_trades=0,
        )

        # Then — 구조 검증
        assert result["window_type"] == "rolling"
        assert result["rolling_is_months"] == 12
        assert len(result["window_results"]) >= 1
        assert "stitched_cagr" in result["mode_summary"]
