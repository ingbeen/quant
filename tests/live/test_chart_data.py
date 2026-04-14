"""live.chart_data — meta + recent + archive/{YYYY} 3 분할 빌더 계약.

설계서 §8.2.5 에서 확정된 새 RTDB 구조를 테스트로 고정한다. 과거의 단일
``build_chart_series`` 는 제거되었고 3 개의 빌더로 대체된다.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from live.chart_data import (
    build_chart_archive_year,
    build_chart_meta,
    build_chart_recent,
)
from live.constants import CHART_RECENT_MONTHS
from live.models import ChartMeta, ChartSeries, UserTrade

# ============================================================================
# fixture
# ============================================================================


# ma_window=200 + CHART_RECENT_MONTHS=6 을 커버하기 위해 충분한 기간을 준비한다.
# 500 일 ≈ 1 년 4 개월 → 워밍업 구간을 지나 최근 6 개월이 모두 MA 계산 가능 영역.
_FIXTURE_DAYS = 500
_FIXTURE_START = date(2025, 1, 1)


def _make_trade_csv(path: Path, base_close: float = 100.0, n_days: int = _FIXTURE_DAYS) -> None:
    """trade CSV 를 생성한다 (live 포트폴리오 trade_data_path 형식)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(n_days):
        d = _FIXTURE_START + timedelta(days=i)
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
        _make_trade_csv(stock_dir / f"{ticker}.csv", base_close=base)
    return tmp_path


def _last_date() -> date:
    return _FIXTURE_START + timedelta(days=_FIXTURE_DAYS - 1)


# ============================================================================
# build_chart_meta
# ============================================================================


class TestBuildChartMeta:
    def test_returns_meta_per_asset(self, state_dir_with_csvs: Path):
        """
        목적: live 포트폴리오 전체 자산에 대해 ChartMeta 가 생성된다.

        Given: 4 자산 CSV
        When:  build_chart_meta
        Then:  asset_id 별로 ChartMeta 반환, first/last 날짜 정확.
        """
        meta_map = build_chart_meta(state_dir_with_csvs)

        assert set(meta_map.keys()) == {"sso", "qld", "gld", "tlt"}
        for meta in meta_map.values():
            assert isinstance(meta, ChartMeta)
            assert meta.first_date == _FIXTURE_START.isoformat()
            assert meta.last_date == _last_date().isoformat()
            assert meta.recent_months == CHART_RECENT_MONTHS
            assert meta.ma_window > 0

    def test_archive_years_contains_all_covered_years(self, state_dir_with_csvs: Path):
        """
        목적: archive_years 는 CSV 가 포함하는 모든 연도를 빠짐없이 나열한다.

        Given: 2025-01-01 ~ 2025-01-01+499 일 CSV (2025, 2026 두 연도 포함)
        When:  build_chart_meta
        Then:  archive_years == [2025, 2026]
        """
        meta_map = build_chart_meta(state_dir_with_csvs)
        for meta in meta_map.values():
            assert meta.archive_years == [2025, 2026]


# ============================================================================
# build_chart_recent
# ============================================================================


class TestBuildChartRecent:
    def test_recent_slice_length_matches_months(self, state_dir_with_csvs: Path):
        """
        목적: recent 는 CHART_RECENT_MONTHS 개월 이내 거래일만 포함한다.

        Given: 500 일 CSV (마지막 날 = 2026-05-15 근사)
        When:  build_chart_recent (months=CHART_RECENT_MONTHS)
        Then:  dates 배열의 첫 날짜 >= last_date - 6 개월, 값 배열 길이 일치.
        """
        recent_map = build_chart_recent(state_dir_with_csvs, months=CHART_RECENT_MONTHS)
        last_day = _last_date()

        # 대략 6 개월 = 180 일 여유 범위로 근사 검증 (달력 기반은 구현에 맡김)
        lower_bound = last_day - timedelta(days=31 * CHART_RECENT_MONTHS + 5)

        for cs in recent_map.values():
            assert isinstance(cs, ChartSeries)
            n = len(cs.dates)
            assert n > 0
            assert len(cs.close) == n
            assert len(cs.ma_value) == n
            assert len(cs.upper_band) == n
            assert len(cs.lower_band) == n

            first = date.fromisoformat(cs.dates[0])
            assert first >= lower_bound
            assert date.fromisoformat(cs.dates[-1]) == last_day

    def test_recent_ma_is_computed_past_warmup(self, state_dir_with_csvs: Path):
        """
        목적: recent 는 500 일 CSV 의 후반부를 자르므로 MA 값이 모두 채워져 있다.

        Given: 500 일 CSV (ma_window=200), recent=6 개월 (~180 일, 후반부)
        When:  build_chart_recent
        Then:  ma_value 에 None 이 섞여 있지 않다 (워밍업 이미 종료).
        """
        recent_map = build_chart_recent(state_dir_with_csvs, months=CHART_RECENT_MONTHS)
        for cs in recent_map.values():
            assert all(v is not None for v in cs.ma_value), "recent slice 는 워밍업을 지난 영역"

    def test_recent_bands_above_below_ma(self, state_dir_with_csvs: Path):
        recent_map = build_chart_recent(state_dir_with_csvs, months=CHART_RECENT_MONTHS)
        for cs in recent_map.values():
            for ema, upper, lower in zip(cs.ma_value, cs.upper_band, cs.lower_band, strict=True):
                assert ema is not None
                assert upper is not None and upper > ema
                assert lower is not None and lower < ema

    def test_recent_user_markers_are_iso_date_strings(self, state_dir_with_csvs: Path):
        """
        목적: 마커는 인덱스가 아니라 ISO 날짜 문자열로 저장된다.

        Given: recent 범위 내 날짜의 user_trades
        When:  build_chart_recent
        Then:  user_buys / user_sells 는 list[str] 이며 ISO 날짜 형식.
        """
        in_range = (_last_date() - timedelta(days=10)).isoformat()
        user_trades = {
            "sso": [
                UserTrade(date=in_range, direction="buy"),
            ]
        }
        recent_map = build_chart_recent(
            state_dir_with_csvs,
            user_trades=user_trades,
            months=CHART_RECENT_MONTHS,
        )
        cs = recent_map["sso"]
        assert cs.user_buys == [in_range]
        assert cs.user_sells == []
        for marker_list in (cs.user_buys, cs.user_sells, cs.buy_signals, cs.sell_signals):
            for value in marker_list:
                assert isinstance(value, str)
                date.fromisoformat(value)

    def test_recent_user_markers_outside_range_excluded(self, state_dir_with_csvs: Path):
        """
        목적: recent 범위 밖(너무 오래된) user_trades 는 recent 에 포함되지 않는다.
        """
        long_ago = (_last_date() - timedelta(days=365)).isoformat()  # 1 년 전 → recent 밖
        user_trades = {
            "sso": [UserTrade(date=long_ago, direction="buy")],
        }
        recent_map = build_chart_recent(
            state_dir_with_csvs,
            user_trades=user_trades,
            months=CHART_RECENT_MONTHS,
        )
        assert recent_map["sso"].user_buys == []

    def test_recent_signal_markers_are_iso_date_strings(self, state_dir_with_csvs: Path):
        in_range = (_last_date() - timedelta(days=5)).isoformat()
        signal_history: dict[str, list[tuple[str, str]]] = {
            "sso": [(in_range, "buy")],
        }
        recent_map = build_chart_recent(
            state_dir_with_csvs,
            signal_history=signal_history,
            months=CHART_RECENT_MONTHS,
        )
        assert recent_map["sso"].buy_signals == [in_range]


# ============================================================================
# build_chart_archive_year
# ============================================================================


class TestBuildChartArchiveYear:
    def test_year_slice_contains_only_that_year(self, state_dir_with_csvs: Path):
        """
        목적: archive/{YYYY} 슬라이스는 해당 연도 거래일만 포함한다.
        """
        year_map = build_chart_archive_year(state_dir_with_csvs, year=2025)
        for cs in year_map.values():
            assert isinstance(cs, ChartSeries)
            for d in cs.dates:
                assert date.fromisoformat(d).year == 2025

    def test_year_slice_length_consistency(self, state_dir_with_csvs: Path):
        year_map = build_chart_archive_year(state_dir_with_csvs, year=2025)
        for cs in year_map.values():
            n = len(cs.dates)
            assert n > 0
            assert len(cs.close) == n
            assert len(cs.ma_value) == n
            assert len(cs.upper_band) == n
            assert len(cs.lower_band) == n

    def test_year_without_data_returns_empty_slices(self, state_dir_with_csvs: Path):
        """
        목적: CSV 가 포함하지 않는 연도를 요청하면 빈 슬라이스가 반환된다.
        """
        year_map = build_chart_archive_year(state_dir_with_csvs, year=2099)
        for cs in year_map.values():
            assert cs.dates == []
            assert cs.close == []
            assert cs.ma_value == []
            assert cs.buy_signals == []

    def test_year_markers_filtered_to_year_scope(self, state_dir_with_csvs: Path):
        """
        목적: 자산 user_trades 마커가 여러 연도에 걸쳐 있으면 해당 연도 것만 남는다.
        """
        user_trades = {
            "sso": [
                UserTrade(date="2025-03-15", direction="buy"),
                UserTrade(date="2026-02-10", direction="sell"),
            ]
        }
        y2025 = build_chart_archive_year(
            state_dir_with_csvs,
            user_trades=user_trades,
            year=2025,
        )
        y2026 = build_chart_archive_year(
            state_dir_with_csvs,
            user_trades=user_trades,
            year=2026,
        )

        assert y2025["sso"].user_buys == ["2025-03-15"]
        assert y2025["sso"].user_sells == []
        assert y2026["sso"].user_buys == []
        assert y2026["sso"].user_sells == ["2026-02-10"]

    def test_year_warmup_region_marked_none(self, state_dir_with_csvs: Path):
        """
        목적: 2025 슬라이스는 CSV 시작부터이므로 초기 워밍업 구간 (< ma_window - 1) 은 None.
        """
        y2025 = build_chart_archive_year(state_dir_with_csvs, year=2025)
        for cs in y2025.values():
            assert cs.ma_value[0] is None


# ============================================================================
# recent ↔ archive 중복 허용 정책
# ============================================================================


class TestRecentArchiveOverlap:
    def test_recent_and_archive_of_current_year_share_overlap(self, state_dir_with_csvs: Path):
        """
        목적: recent 와 archive/{현재_연도} 는 경계에서 구간이 중복되어도 OK.

        Given: 같은 CSV 에서 recent + archive 빌드
        When:  양쪽의 dates 를 비교
        Then:  교집합이 비어있지 않다 (중복 허용 정책의 존재 증명).
        """
        recent_map = build_chart_recent(state_dir_with_csvs, months=CHART_RECENT_MONTHS)
        current_year = _last_date().year
        year_map = build_chart_archive_year(state_dir_with_csvs, year=current_year)

        for asset_id in recent_map:
            recent_dates = set(recent_map[asset_id].dates)
            year_dates = set(year_map[asset_id].dates)
            overlap = recent_dates & year_dates
            assert len(overlap) > 0, "recent 와 archive/{현재_연도} 는 경계에서 교집합이 있어야 한다"


# ============================================================================
# 마커 ISO 파싱 실패 정책 (루트 CLAUDE.md "불가능 값 처리")
# ============================================================================


class TestMarkerDateParsingFailures:
    """``_filter_markers_in_range`` 가 ISO 파싱 실패를 소스별로 다르게 처리한다.

    - signal_history 는 live 시스템이 내부 생성하므로 파싱 실패는 내부 불변조건
      위반 → ``RuntimeError``.
    - user_trades 는 앱이 RTDB 로 입력하는 외부 데이터이므로 파싱 실패는
      입력 검증 실패 → ``ValueError``.
    """

    def test_signal_history_with_broken_iso_raises_runtime_error(self, state_dir_with_csvs: Path):
        """
        목적: signal_history 의 ISO 날짜가 파손되면 RuntimeError 로 즉시 실패한다.

        Given: signal_history 에 파싱 불가능한 문자열이 포함된다.
        When:  build_chart_recent 호출.
        Then:  RuntimeError("내부 불변조건 위반") 발생.
        """
        # Given
        signal_history: dict[str, list[tuple[str, str]]] = {
            "sso": [("not-a-date", "buy")],
        }

        # When / Then
        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            build_chart_recent(
                state_dir_with_csvs,
                signal_history=signal_history,
                months=CHART_RECENT_MONTHS,
            )

    def test_user_trades_with_broken_iso_raises_value_error(self, state_dir_with_csvs: Path):
        """
        목적: user_trades 의 ISO 날짜가 파손되면 ValueError 로 즉시 실패한다.

        Given: user_trades 에 파싱 불가능한 문자열이 포함된다.
        When:  build_chart_recent 호출.
        Then:  ValueError 발생 (외부 입력 검증 실패).
        """
        # Given
        user_trades = {
            "sso": [UserTrade(date="bogus", direction="buy")],
        }

        # When / Then
        with pytest.raises(ValueError, match="user_trades"):
            build_chart_recent(
                state_dir_with_csvs,
                user_trades=user_trades,
                months=CHART_RECENT_MONTHS,
            )

    def test_archive_year_signal_history_broken_iso_raises_runtime_error(self, state_dir_with_csvs: Path):
        """
        목적: archive_year 경로에서도 signal_history 파손 시 RuntimeError 로 실패한다.
        """
        signal_history: dict[str, list[tuple[str, str]]] = {
            "sso": [("broken-iso", "sell")],
        }

        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            build_chart_archive_year(
                state_dir_with_csvs,
                year=_last_date().year,
                signal_history=signal_history,
            )
