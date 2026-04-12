"""live.chart_data ``build_chart_series`` 계약을 검증한다."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from live.chart_data import build_chart_series
from live.models import ChartSeries, UserTrade

# ============================================================================
# fixture
# ============================================================================


def _make_trade_csv(path: Path, n_days: int = 250, base_close: float = 100.0) -> None:
    """trade CSV 를 생성한다 (live 포트폴리오 trade_data_path 형식)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    start = date(2025, 1, 1)
    rows = []
    for i in range(n_days):
        d = start + timedelta(days=i)
        c = base_close + (i * 0.1)
        rows.append(
            {
                "Date": d,
                "Open": c - 0.2,
                "High": c + 0.5,
                "Low": c - 0.5,
                "Close": c,
                "Volume": 1_000_000,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


@pytest.fixture
def state_dir_with_csvs(tmp_path: Path) -> Path:
    """tmp_path 에 live 포트폴리오 자산 trade CSV 를 준비한다."""
    stock_dir = tmp_path / "data" / "stock"
    for ticker, base in (
        ("SSO", 80.0),
        ("QLD", 85.0),
        ("GLD", 180.0),
        ("TLT", 95.0),
    ):
        _make_trade_csv(stock_dir / f"{ticker}.csv", n_days=250, base_close=base)
    return tmp_path


class TestBuildChartSeriesLengths:
    def test_dates_close_ema_lengths_match(self, state_dir_with_csvs: Path):
        """Given 연단위 CSV When build_chart_series Then 각 시리즈 길이가 일치한다."""
        series = build_chart_series(state_dir_with_csvs)

        assert set(series.keys()) == {"sso", "qld", "gld", "tlt"}
        for cs in series.values():
            assert isinstance(cs, ChartSeries)
            n = len(cs.dates)
            assert n == 250
            assert len(cs.close) == n
            assert len(cs.ma_value) == n
            assert len(cs.upper_band) == n
            assert len(cs.lower_band) == n


class TestBuildChartSeriesUserMarkers:
    def test_user_trades_indices_within_range(self, state_dir_with_csvs: Path):
        """Given 사용자 체결 마커 When build Then 인덱스가 dates 범위 내."""
        marker_dates = [date(2025, 4, 1), date(2025, 6, 15)]
        user_trades = {
            "sso": [
                UserTrade(date=marker_dates[0].isoformat(), direction="buy"),
                UserTrade(date=marker_dates[1].isoformat(), direction="sell"),
            ]
        }
        series = build_chart_series(state_dir_with_csvs, user_trades=user_trades)
        cs = series["sso"]
        n = len(cs.dates)

        for idx in cs.user_buys + cs.user_sells:
            assert 0 <= idx < n

        assert len(cs.user_buys) == 1
        assert len(cs.user_sells) == 1

    def test_unknown_user_trade_date_is_skipped(self, state_dir_with_csvs: Path):
        """존재하지 않는 날짜는 무시."""
        user_trades = {
            "sso": [UserTrade(date="2050-01-01", direction="buy")],
        }
        series = build_chart_series(state_dir_with_csvs, user_trades=user_trades)
        assert series["sso"].user_buys == []

    def test_no_user_trades_returns_empty_lists(self, state_dir_with_csvs: Path):
        series = build_chart_series(state_dir_with_csvs)
        for cs in series.values():
            assert cs.user_buys == []
            assert cs.user_sells == []


class TestBuildChartSeriesEmaWarmup:
    def test_first_199_days_ema_is_none(self, state_dir_with_csvs: Path):
        """Given 짧은 구간 When build Then 이동평균 워밍업 구간은 None 으로 채워진다."""
        series = build_chart_series(state_dir_with_csvs)
        for cs in series.values():
            first_199 = cs.ma_value[:199]
            assert any(v is None for v in first_199), "이동평균 워밍업은 None 으로 표현되어야 함"

            if len(cs.ma_value) > 200:
                assert cs.ma_value[200] is not None


class TestBuildChartSeriesBands:
    def test_upper_band_greater_than_ema(self, state_dir_with_csvs: Path):
        series = build_chart_series(state_dir_with_csvs)
        for cs in series.values():
            for ema, upper, lower in zip(cs.ma_value, cs.upper_band, cs.lower_band, strict=True):
                if ema is None:
                    assert upper is None
                    assert lower is None
                else:
                    assert upper is not None and upper > ema
                    assert lower is not None and lower < ema


class TestBuildChartSeriesDates:
    def test_dates_are_iso_strings(self, state_dir_with_csvs: Path):
        series = build_chart_series(state_dir_with_csvs)
        for cs in series.values():
            for d in cs.dates:
                assert isinstance(d, str)
                # ISO 8601 형식이면 fromisoformat 로 파싱 가능
                date.fromisoformat(d)


# ============================================================================
# signal_history 로 buy_signals / sell_signals 채우기
# ============================================================================


class TestBuildChartSeriesSignalMarkers:
    def test_no_signal_history_returns_empty_lists(self, state_dir_with_csvs: Path):
        """Given signal_history 인자 없음 When build Then buy/sell_signals 는 빈 리스트."""
        series = build_chart_series(state_dir_with_csvs)
        for cs in series.values():
            assert cs.buy_signals == []
            assert cs.sell_signals == []

    def test_signal_history_fills_buy_sell_indices(self, state_dir_with_csvs: Path):
        """Given 과거 신호 이력 When build Then dates 의 올바른 인덱스로 변환."""
        signal_history: dict[str, list[tuple[str, str]]] = {
            "sso": [
                ("2025-04-01", "buy"),  # 존재하는 날짜
                ("2025-06-15", "sell"),  # 존재하는 날짜
                ("2025-06-16", "none"),  # none 은 마커 없음
                ("2050-01-01", "buy"),  # dates 범위 밖 — skip
            ],
        }
        series = build_chart_series(state_dir_with_csvs, signal_history=signal_history)
        cs = series["sso"]
        n = len(cs.dates)

        assert len(cs.buy_signals) == 1
        assert len(cs.sell_signals) == 1
        for idx in cs.buy_signals + cs.sell_signals:
            assert 0 <= idx < n
        # dates 에서 해당 인덱스가 signal_history 의 날짜와 일치
        assert cs.dates[cs.buy_signals[0]] == "2025-04-01"
        assert cs.dates[cs.sell_signals[0]] == "2025-06-15"

    def test_signal_history_for_other_assets_isolated(self, state_dir_with_csvs: Path):
        """Given 한 자산에만 signal_history 전달 When build Then 다른 자산 영향 없음."""
        signal_history = {"gld": [("2025-04-01", "buy")]}
        series = build_chart_series(state_dir_with_csvs, signal_history=signal_history)

        assert len(series["gld"].buy_signals) == 1
        assert series["sso"].buy_signals == []
        assert series["qld"].buy_signals == []
        assert series["tlt"].buy_signals == []
