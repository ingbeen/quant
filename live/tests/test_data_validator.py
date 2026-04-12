"""live.data_validator OHLC / 종가 / 거래일 gap 검증 계약을 고정한다."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from live.data_validator import (
    validate_date_gap,
    validate_ohlc_logic,
    validate_prev_close,
)


@pytest.fixture(scope="module")
def nyse_calendar():
    """NYSE 거래소 달력 (exchange_calendars). 모듈 스코프로 재사용."""
    import exchange_calendars as xcals

    return xcals.get_calendar("XNYS")


def _make_ohlc_row(
    open_: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.5,
) -> pd.Series:
    return pd.Series({"Open": open_, "High": high, "Low": low, "Close": close})


# ============================================================================
# validate_ohlc_logic
# ============================================================================


class TestValidateOhlcLogic:
    def test_normal_ohlc_returns_empty(self):
        """Given 정상 OHLC When 검증 Then 에러 없음."""
        row = _make_ohlc_row(open_=100.0, high=101.0, low=99.0, close=100.5)
        assert validate_ohlc_logic(row) == []

    def test_high_less_than_low_raises(self):
        """Given High < Low When 검증 Then 에러."""
        row = _make_ohlc_row(open_=100.0, high=98.0, low=99.0, close=99.5)
        errors = validate_ohlc_logic(row)
        assert len(errors) >= 1
        assert any("High" in msg and "Low" in msg for msg in errors)

    def test_close_zero_raises(self):
        """Given Close = 0 When 검증 Then 에러."""
        row = _make_ohlc_row(close=0.0)
        errors = validate_ohlc_logic(row)
        assert len(errors) >= 1
        assert any("Close" in msg for msg in errors)

    def test_close_negative_raises(self):
        """Given Close = -5 When 검증 Then 에러."""
        row = _make_ohlc_row(close=-5.0)
        errors = validate_ohlc_logic(row)
        assert len(errors) >= 1

    def test_open_zero_raises(self):
        row = _make_ohlc_row(open_=0.0)
        assert len(validate_ohlc_logic(row)) >= 1

    def test_high_zero_raises(self):
        row = _make_ohlc_row(high=0.0)
        assert len(validate_ohlc_logic(row)) >= 1

    def test_low_negative_raises(self):
        row = _make_ohlc_row(low=-1.0)
        assert len(validate_ohlc_logic(row)) >= 1

    def test_close_outside_high_low_range_raises(self):
        """Close 가 High~Low 범위 밖이면 에러 (내부 논리)."""
        row = _make_ohlc_row(open_=100.0, high=101.0, low=99.0, close=105.0)
        errors = validate_ohlc_logic(row)
        assert len(errors) >= 1

    def test_equal_high_low_is_acceptable(self):
        """High == Low (변동 없음) 는 허용."""
        row = _make_ohlc_row(open_=100.0, high=100.0, low=100.0, close=100.0)
        assert validate_ohlc_logic(row) == []


# ============================================================================
# validate_prev_close
# ============================================================================


class TestValidatePrevClose:
    def test_half_value_difference_raises(self):
        """Given CSV 580 vs yf 290 (50% 차이) When 검증 Then 에러."""
        errors = validate_prev_close(csv_close=580.0, yf_close=290.0)
        assert len(errors) >= 1
        assert any("종가" in msg or "close" in msg.lower() for msg in errors)

    def test_tiny_difference_is_ok(self):
        """Given CSV 580 vs yf 579.5 (0.09% 차이) When 검증 Then 에러 없음."""
        errors = validate_prev_close(csv_close=580.0, yf_close=579.5)
        assert errors == []

    def test_one_percent_exactly_is_boundary(self):
        """정확히 1% 차이는 경계값 — 1% 미만만 허용."""
        # 1% 정확히: csv=100, yf=101 → 1% 차이 → 에러 (>= 1%)
        errors = validate_prev_close(csv_close=100.0, yf_close=101.0)
        assert len(errors) >= 1

    def test_just_under_one_percent_ok(self):
        """0.99% 차이는 허용."""
        errors = validate_prev_close(csv_close=100.0, yf_close=100.99)
        assert errors == []

    def test_zero_csv_close_raises(self):
        """분모 0 방지 — csv_close <= 0 → 에러."""
        errors = validate_prev_close(csv_close=0.0, yf_close=100.0)
        assert len(errors) >= 1

    def test_negative_csv_close_raises(self):
        errors = validate_prev_close(csv_close=-10.0, yf_close=100.0)
        assert len(errors) >= 1

    def test_identical_values_ok(self):
        errors = validate_prev_close(csv_close=500.0, yf_close=500.0)
        assert errors == []


# ============================================================================
# validate_date_gap
# ============================================================================


class TestValidateDateGap:
    def test_fri_to_mon_no_gap(self, nyse_calendar):
        """Given 금요일 → 월요일 When 검증 Then 에러 없음."""
        # 2026-04-10 (금) → 2026-04-13 (월)
        csv_last = date(2026, 4, 10)
        today = date(2026, 4, 13)
        errors = validate_date_gap(csv_last, today, nyse_calendar)
        assert errors == []

    def test_missing_trading_day_raises(self, nyse_calendar):
        """Given 거래일 누락 When 검증 Then 에러."""
        csv_last = date(2026, 4, 6)  # 월
        today = date(2026, 4, 10)  # 금
        errors = validate_date_gap(csv_last, today, nyse_calendar)
        assert len(errors) >= 1
        assert any("거래일" in msg or "누락" in msg for msg in errors)

    def test_same_day_no_gap(self, nyse_calendar):
        """csv_last == today 인 경우는 gap 없음 (오늘 데이터는 still pending)."""
        csv_last = date(2026, 4, 10)
        today = date(2026, 4, 10)
        errors = validate_date_gap(csv_last, today, nyse_calendar)
        assert errors == []

    def test_consecutive_trading_days_no_gap(self, nyse_calendar):
        """월 → 화 연속."""
        csv_last = date(2026, 4, 6)
        today = date(2026, 4, 7)
        errors = validate_date_gap(csv_last, today, nyse_calendar)
        assert errors == []

    def test_weekend_only_gap_no_error(self, nyse_calendar):
        """금 → 다음 금, 주말만 있으면 거래일 누락 아님... 은 아니다.
        월/화/수/목이 모두 거래일이라면 누락. 주말만 건너뛴 경우만 허용.
        """
        # 2026-04-10 (금) → 2026-04-17 (금): 월/화/수/목 4 거래일 누락
        csv_last = date(2026, 4, 10)
        today = date(2026, 4, 17)
        errors = validate_date_gap(csv_last, today, nyse_calendar)
        assert len(errors) >= 1

    def test_csv_last_after_today_is_noop(self, nyse_calendar):
        """csv_last > today 인 이상 상황: 누락은 없으나 방어적으로 에러 없음."""
        csv_last = date(2026, 4, 13)
        today = date(2026, 4, 10)
        errors = validate_date_gap(csv_last, today, nyse_calendar)
        assert errors == []
