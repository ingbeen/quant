"""ATR 비교 실험 모듈 테스트

ATR(14,3.0) vs ATR(22,3.0) OOS 비교 실험의 비즈니스 로직을 검증한다.
- TestBuildWindowComparison: 윈도우별 비교 DataFrame 구성
- TestBuildComparisonSummary: 요약 통계 생성
- TestRunSingleAtrConfig: 소규모 통합 테스트 (축소 WFO)
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.atr_comparison import (
    AtrComparisonResultDict,
    build_comparison_summary,
    build_window_comparison,
    run_single_atr_config,
)
from qbt.backtest.types import WfoModeSummaryDict, WfoWindowResultDict
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    EPSILON,
)


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
    from datetime import timedelta

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
    oos_cagr: float,
    oos_mdd: float,
    oos_calmar: float,
    oos_trades: int,
    oos_win_rate: float,
    atr_period: int = 14,
    atr_multiplier: float = 3.0,
) -> WfoWindowResultDict:
    """테스트용 WFO 윈도우 결과를 생성한다."""
    return {
        "window_idx": idx,
        "is_start": "2000-01-01",
        "is_end": "2005-12-31",
        "oos_start": f"200{6 + idx * 2}-01-01",
        "oos_end": f"200{7 + idx * 2}-12-31",
        "best_ma_window": 100,
        "best_buy_buffer_zone_pct": 0.03,
        "best_sell_buffer_zone_pct": 0.03,
        "best_hold_days": 0,
        "best_recent_months": 0,
        "best_atr_period": atr_period,
        "best_atr_multiplier": atr_multiplier,
        "is_cagr": 10.0,
        "is_mdd": -20.0,
        "is_calmar": 0.5,
        "is_trades": 5,
        "is_win_rate": 60.0,
        "oos_cagr": oos_cagr,
        "oos_mdd": oos_mdd,
        "oos_calmar": oos_calmar,
        "oos_trades": oos_trades,
        "oos_win_rate": oos_win_rate,
        "wfe_calmar": oos_calmar / 0.5 if abs(0.5) > EPSILON else 0.0,
        "wfe_cagr": oos_cagr / 10.0,
    }


def _make_atr_comparison_result(
    atr_period: int,
    atr_multiplier: float,
    window_results: list[WfoWindowResultDict],
    stitched_cagr: float = 12.0,
    stitched_mdd: float = -18.0,
    stitched_calmar: float = 0.67,
    stitched_total_return_pct: float = 120.0,
) -> AtrComparisonResultDict:
    """테스트용 ATR 비교 결과를 생성한다."""
    mode_summary: WfoModeSummaryDict = {
        "n_windows": len(window_results),
        "oos_cagr_mean": sum(wr["oos_cagr"] for wr in window_results) / len(window_results),
        "oos_cagr_std": 0.0,
        "oos_mdd_mean": sum(wr["oos_mdd"] for wr in window_results) / len(window_results),
        "oos_mdd_worst": min(wr["oos_mdd"] for wr in window_results),
        "oos_calmar_mean": sum(wr["oos_calmar"] for wr in window_results) / len(window_results),
        "oos_calmar_std": 0.0,
        "oos_trades_total": sum(wr["oos_trades"] for wr in window_results),
        "oos_win_rate_mean": sum(wr["oos_win_rate"] for wr in window_results) / len(window_results),
        "wfe_calmar_mean": 0.0,
        "wfe_calmar_median": 0.0,
        "wfe_cagr_mean": 0.0,
        "wfe_cagr_median": 0.0,
        "gap_calmar_median": 0.0,
        "wfe_calmar_robust": 0.0,
        "profit_concentration_max": 0.0,
        "profit_concentration_window_idx": 0,
        "param_ma_windows": [wr["best_ma_window"] for wr in window_results],
        "param_buy_buffers": [wr["best_buy_buffer_zone_pct"] for wr in window_results],
        "param_sell_buffers": [wr["best_sell_buffer_zone_pct"] for wr in window_results],
        "param_hold_days": [wr["best_hold_days"] for wr in window_results],
        "param_recent_months": [wr["best_recent_months"] for wr in window_results],
        "stitched_cagr": stitched_cagr,
        "stitched_mdd": stitched_mdd,
        "stitched_calmar": stitched_calmar,
        "stitched_total_return_pct": stitched_total_return_pct,
    }

    return {
        "atr_period": atr_period,
        "atr_multiplier": atr_multiplier,
        "window_results": window_results,
        "mode_summary": mode_summary,
    }


class TestBuildWindowComparison:
    """build_window_comparison() 함수 테스트."""

    def test_window_count_mismatch_raises_value_error(self):
        """
        목적: 두 ATR 설정의 윈도우 수가 다르면 ValueError 발생

        Given: config_a에 3개 윈도우, config_b에 2개 윈도우
        When: build_window_comparison() 호출
        Then: ValueError 발생 (윈도우 수 불일치 메시지)
        """
        # Given
        windows_a = [_make_wfo_window_result(i, 10.0, -15.0, 0.67, 3, 60.0, atr_period=14) for i in range(3)]
        windows_b = [_make_wfo_window_result(i, 8.0, -12.0, 0.67, 2, 50.0, atr_period=22) for i in range(2)]

        config_a = _make_atr_comparison_result(14, 3.0, windows_a)
        config_b = _make_atr_comparison_result(22, 3.0, windows_b)

        # When/Then
        with pytest.raises(ValueError, match="윈도우 수"):
            build_window_comparison(config_a, config_b)

    def test_difference_calculation(self):
        """
        목적: 윈도우별 차이 계산(A - B)이 올바른지 검증

        Given: config_a(CAGR=10), config_b(CAGR=8) 각 2개 윈도우
        When: build_window_comparison() 호출
        Then: diff_oos_cagr = 10 - 8 = 2 (각 윈도우)
        """
        # Given
        windows_a = [
            _make_wfo_window_result(0, 10.0, -15.0, 0.67, 3, 60.0, atr_period=14),
            _make_wfo_window_result(1, 12.0, -20.0, 0.60, 4, 75.0, atr_period=14),
        ]
        windows_b = [
            _make_wfo_window_result(0, 8.0, -12.0, 0.67, 2, 50.0, atr_period=22),
            _make_wfo_window_result(1, 6.0, -25.0, 0.24, 3, 33.3, atr_period=22),
        ]

        config_a = _make_atr_comparison_result(14, 3.0, windows_a)
        config_b = _make_atr_comparison_result(22, 3.0, windows_b)

        # When
        comparison_df = build_window_comparison(config_a, config_b)

        # Then
        assert len(comparison_df) == 2
        # 윈도우 0: diff_oos_cagr = 10.0 - 8.0 = 2.0
        assert comparison_df.iloc[0]["diff_oos_cagr"] == pytest.approx(2.0, abs=0.01)
        # 윈도우 1: diff_oos_cagr = 12.0 - 6.0 = 6.0
        assert comparison_df.iloc[1]["diff_oos_cagr"] == pytest.approx(6.0, abs=0.01)

    def test_row_structure(self):
        """
        목적: 비교 DataFrame의 행 구조(컬럼)가 올바른지 검증

        Given: 각 1개 윈도우를 가진 두 ATR 설정
        When: build_window_comparison() 호출
        Then: 필수 컬럼(window_idx, a_oos_*, b_oos_*, diff_oos_*) 존재
        """
        # Given
        windows_a = [
            _make_wfo_window_result(0, 10.0, -15.0, 0.67, 3, 60.0, atr_period=14),
        ]
        windows_b = [
            _make_wfo_window_result(0, 8.0, -12.0, 0.67, 2, 50.0, atr_period=22),
        ]

        config_a = _make_atr_comparison_result(14, 3.0, windows_a)
        config_b = _make_atr_comparison_result(22, 3.0, windows_b)

        # When
        comparison_df = build_window_comparison(config_a, config_b)

        # Then — 필수 컬럼 존재 검증
        required_cols = [
            "window_idx",
            "oos_start",
            "oos_end",
            "a_oos_cagr",
            "a_oos_mdd",
            "a_oos_calmar",
            "b_oos_cagr",
            "b_oos_mdd",
            "b_oos_calmar",
            "diff_oos_cagr",
            "diff_oos_mdd",
            "diff_oos_calmar",
        ]
        for col in required_cols:
            assert col in comparison_df.columns, f"필수 컬럼 누락: {col}"


class TestBuildComparisonSummary:
    """build_comparison_summary() 함수 테스트."""

    def test_wins_count(self):
        """
        목적: 우위 카운트(wins)가 올바르게 계산되는지 검증

        Given: config_a가 CAGR/Calmar 모두 우위인 2개 윈도우
        When: build_comparison_summary() 호출
        Then: a_wins_cagr=2, a_wins_calmar=2
        """
        # Given
        windows_a = [
            _make_wfo_window_result(0, 15.0, -10.0, 1.50, 4, 75.0, atr_period=14),
            _make_wfo_window_result(1, 12.0, -8.0, 1.50, 3, 66.7, atr_period=14),
        ]
        windows_b = [
            _make_wfo_window_result(0, 8.0, -15.0, 0.53, 2, 50.0, atr_period=22),
            _make_wfo_window_result(1, 6.0, -12.0, 0.50, 2, 50.0, atr_period=22),
        ]

        config_a = _make_atr_comparison_result(14, 3.0, windows_a, stitched_cagr=14.0)
        config_b = _make_atr_comparison_result(22, 3.0, windows_b, stitched_cagr=7.0)

        comparison_df = build_window_comparison(config_a, config_b)

        # When
        summary = build_comparison_summary(config_a, config_b, comparison_df)

        # Then
        assert summary["a_wins_cagr"] == 2
        assert summary["b_wins_cagr"] == 0
        assert summary["a_wins_calmar"] == 2
        assert summary["b_wins_calmar"] == 0

    def test_required_fields(self):
        """
        목적: 요약 딕셔너리에 필수 필드가 모두 존재하는지 검증

        Given: 2개 윈도우의 비교 데이터
        When: build_comparison_summary() 호출
        Then: 필수 키(a/b 설정, stitched 지표, wins, diff 통계) 존재
        """
        # Given
        windows_a = [
            _make_wfo_window_result(0, 10.0, -15.0, 0.67, 3, 60.0, atr_period=14),
        ]
        windows_b = [
            _make_wfo_window_result(0, 8.0, -12.0, 0.67, 2, 50.0, atr_period=22),
        ]

        config_a = _make_atr_comparison_result(14, 3.0, windows_a)
        config_b = _make_atr_comparison_result(22, 3.0, windows_b)

        comparison_df = build_window_comparison(config_a, config_b)

        # When
        summary = build_comparison_summary(config_a, config_b, comparison_df)

        # Then — 필수 키 존재
        required_keys = [
            "a_atr_period",
            "a_atr_multiplier",
            "b_atr_period",
            "b_atr_multiplier",
            "n_windows",
            "a_stitched_cagr",
            "a_stitched_mdd",
            "a_stitched_calmar",
            "b_stitched_cagr",
            "b_stitched_mdd",
            "b_stitched_calmar",
            "a_wins_cagr",
            "b_wins_cagr",
            "a_wins_calmar",
            "b_wins_calmar",
            "diff_cagr_mean",
            "diff_cagr_median",
            "diff_calmar_mean",
            "diff_calmar_median",
        ]
        for key in required_keys:
            assert key in summary, f"필수 키 누락: {key}"

    def test_diff_mean_and_median(self):
        """
        목적: 차이 평균/중앙값 계산이 올바른지 검증

        Given: diff_oos_cagr = [2.0, 6.0]인 비교 데이터
        When: build_comparison_summary() 호출
        Then: diff_cagr_mean=4.0, diff_cagr_median=4.0
        """
        # Given
        windows_a = [
            _make_wfo_window_result(0, 10.0, -15.0, 0.67, 3, 60.0, atr_period=14),
            _make_wfo_window_result(1, 12.0, -20.0, 0.60, 4, 75.0, atr_period=14),
        ]
        windows_b = [
            _make_wfo_window_result(0, 8.0, -12.0, 0.67, 2, 50.0, atr_period=22),
            _make_wfo_window_result(1, 6.0, -25.0, 0.24, 3, 33.3, atr_period=22),
        ]

        config_a = _make_atr_comparison_result(14, 3.0, windows_a)
        config_b = _make_atr_comparison_result(22, 3.0, windows_b)

        comparison_df = build_window_comparison(config_a, config_b)

        # When
        summary = build_comparison_summary(config_a, config_b, comparison_df)

        # Then — diff_cagr = [2.0, 6.0] → mean=4.0, median=4.0
        assert summary["diff_cagr_mean"] == pytest.approx(4.0, abs=0.1)
        assert summary["diff_cagr_median"] == pytest.approx(4.0, abs=0.1)


class TestRunSingleAtrConfig:
    """run_single_atr_config() 소규모 통합 테스트."""

    def test_returns_correct_structure(self):
        """
        목적: 축소 WFO 설정으로 반환 구조가 올바른지 검증

        Given: 약 5년 분량의 테스트 데이터 (IS=6개월, OOS=3개월)
        When: run_single_atr_config(atr_period=14, atr_multiplier=3.0) 호출
        Then: AtrComparisonResultDict 구조 반환 (window_results, mode_summary)
        """
        # Given — 약 5년 분량 (1250 거래일)
        df = _make_stock_df(date(2000, 1, 3), 1250, base_price=100.0, daily_return=0.0005)

        # When — 축소 WFO 설정 (빠른 실행)
        result = run_single_atr_config(
            signal_df=df,
            trade_df=df,
            atr_period=14,
            atr_multiplier=3.0,
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
        assert result["atr_period"] == 14
        assert result["atr_multiplier"] == pytest.approx(3.0, abs=EPSILON)
        assert len(result["window_results"]) >= 1

        # mode_summary 필수 키 검증
        mode_summary = result["mode_summary"]
        assert "n_windows" in mode_summary
        assert "oos_cagr_mean" in mode_summary
        assert "stitched_cagr" in mode_summary
        assert "stitched_mdd" in mode_summary
