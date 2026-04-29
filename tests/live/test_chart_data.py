"""live.chart_data — meta + years/{YYYY} 2 분할 빌더 계약.

설계서 §8.2.5 에서 확정된 RTDB 구조를 테스트로 고정한다. 차트 시계열은
연도별 단일 슬라이스 (``years/{YYYY}``) 로만 구성된다.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from live import chart_data as chart_data_module
from live.chart_data import (
    build_chart_meta,
    build_chart_year_slice,
    build_chart_year_slices,
    build_equity_meta,
    build_equity_year_slice,
    build_equity_year_slices,
)
from live.models import ChartMeta, ChartSeries, EquityChartMeta, EquityChartSeries, UserTrade

# ============================================================================
# fixture
# ============================================================================


# ma_window=200 워밍업을 커버하기 위해 충분한 기간을 준비한다.
# 500 일 ≈ 1 년 4 개월 → 후반 연도는 워밍업이 끝난 영역.
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
            assert meta.ma_window > 0

    def test_years_contains_all_covered_years(self, state_dir_with_csvs: Path):
        """
        목적: years 는 CSV 가 포함하는 모든 연도를 빠짐없이 나열한다.

        Given: 2025-01-01 ~ 2025-01-01+499 일 CSV (2025, 2026 두 연도 포함)
        When:  build_chart_meta
        Then:  years == [2025, 2026]
        """
        meta_map = build_chart_meta(state_dir_with_csvs)
        for meta in meta_map.values():
            assert meta.years == [2025, 2026]

    def test_meta_has_no_recent_months_field(self, state_dir_with_csvs: Path):
        """
        목적: ChartMeta 는 recent_months 필드를 포함하지 않는다 (recent 슬라이스 폐지).
        """
        meta_map = build_chart_meta(state_dir_with_csvs)
        for meta in meta_map.values():
            assert not hasattr(meta, "recent_months")
            assert not hasattr(meta, "archive_years")


# ============================================================================
# build_chart_year_slice
# ============================================================================


class TestBuildChartYearSlice:
    def test_year_slice_contains_only_that_year(self, state_dir_with_csvs: Path):
        """
        목적: years/{YYYY} 슬라이스는 해당 연도 거래일만 포함한다.
        """
        year_map = build_chart_year_slice(state_dir_with_csvs, year=2025)
        for cs in year_map.values():
            assert isinstance(cs, ChartSeries)
            for d in cs.dates:
                assert date.fromisoformat(d).year == 2025

    def test_year_slice_length_consistency(self, state_dir_with_csvs: Path):
        year_map = build_chart_year_slice(state_dir_with_csvs, year=2025)
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
        year_map = build_chart_year_slice(state_dir_with_csvs, year=2099)
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
        y2025 = build_chart_year_slice(
            state_dir_with_csvs,
            user_trades=user_trades,
            year=2025,
        )
        y2026 = build_chart_year_slice(
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
        y2025 = build_chart_year_slice(state_dir_with_csvs, year=2025)
        for cs in y2025.values():
            assert cs.ma_value[0] is None

    def test_year_post_warmup_ma_is_computed(self, state_dir_with_csvs: Path):
        """
        목적: 2026 (후반 연도) 슬라이스는 워밍업이 끝난 영역이므로 MA 가 모두 채워진다.
        """
        y2026 = build_chart_year_slice(state_dir_with_csvs, year=2026)
        for cs in y2026.values():
            assert all(v is not None for v in cs.ma_value), "후반 연도 슬라이스는 워밍업을 지난 영역"

    def test_year_bands_above_below_ma(self, state_dir_with_csvs: Path):
        """
        목적: upper_band > ma_value > lower_band 가 항상 성립.
        """
        y2026 = build_chart_year_slice(state_dir_with_csvs, year=2026)
        for cs in y2026.values():
            for ema, upper, lower in zip(cs.ma_value, cs.upper_band, cs.lower_band, strict=True):
                assert ema is not None
                assert upper is not None and upper > ema
                assert lower is not None and lower < ema

    def test_year_user_markers_are_iso_date_strings(self, state_dir_with_csvs: Path):
        """
        목적: 마커는 인덱스가 아니라 ISO 날짜 문자열로 저장된다.
        """
        in_range = "2026-02-10"
        user_trades = {
            "sso": [
                UserTrade(date=in_range, direction="buy"),
            ]
        }
        year_map = build_chart_year_slice(
            state_dir_with_csvs,
            user_trades=user_trades,
            year=2026,
        )
        cs = year_map["sso"]
        assert cs.user_buys == [in_range]
        assert cs.user_sells == []
        for marker_list in (cs.user_buys, cs.user_sells, cs.buy_signals, cs.sell_signals):
            for value in marker_list:
                assert isinstance(value, str)
                date.fromisoformat(value)

    def test_year_signal_markers_are_iso_date_strings(self, state_dir_with_csvs: Path):
        in_range = "2026-03-05"
        signal_history: dict[str, list[tuple[str, str]]] = {
            "sso": [(in_range, "buy")],
        }
        year_map = build_chart_year_slice(
            state_dir_with_csvs,
            signal_history=signal_history,
            year=2026,
        )
        assert year_map["sso"].buy_signals == [in_range]


# ============================================================================
# build_chart_year_slices (복수 연도 일괄)
# ============================================================================


class TestBuildChartYearSlices:
    """``build_chart_year_slices`` 는 자산 frame 을 1 회 로드하고 연도별로 슬라이싱한다.

    단일 연도 함수를 N 회 호출하는 N+1 패턴을 회피하기 위한 일괄 빌더의 계약을
    고정한다.
    """

    def test_returns_dict_keyed_by_year(self, state_dir_with_csvs: Path):
        """
        목적: 입력 ``years`` 의 모든 연도가 결과 dict 의 키로 정확히 들어간다.
        """
        result = build_chart_year_slices(state_dir_with_csvs, years=[2025, 2026])
        assert set(result.keys()) == {2025, 2026}
        # 각 연도별로 4 자산이 모두 포함된다
        for year in (2025, 2026):
            assert set(result[year].keys()) == {"sso", "qld", "gld", "tlt"}
            for cs in result[year].values():
                assert isinstance(cs, ChartSeries)

    def test_single_year_call_matches_single_function(self, state_dir_with_csvs: Path):
        """
        목적: 복수 함수의 단일 연도 결과는 단일 함수의 결과와 동일해야 한다 (회귀 보호).
        """
        single = build_chart_year_slice(state_dir_with_csvs, year=2026)
        batch = build_chart_year_slices(state_dir_with_csvs, years=[2026])
        for asset_id in single:
            assert single[asset_id].dates == batch[2026][asset_id].dates
            assert single[asset_id].close == batch[2026][asset_id].close
            assert single[asset_id].ma_value == batch[2026][asset_id].ma_value
            assert single[asset_id].upper_band == batch[2026][asset_id].upper_band
            assert single[asset_id].lower_band == batch[2026][asset_id].lower_band

    def test_loads_each_asset_frame_only_once(self, state_dir_with_csvs: Path, monkeypatch: pytest.MonkeyPatch):
        """
        목적: N+1 회피의 핵심 — 자산별 ``_load_slot_frame`` 호출이 자산 수만큼 (= 4)
              만 발생하고, 연도 수에 비례해 늘어나지 않는다.

        Given: 4 자산 × 5 연도 입력.
        When:  build_chart_year_slices 호출.
        Then:  ``_load_slot_frame`` 호출 횟수 == 4 (자산 수). 5 × 4 = 20 이 아님.
        """
        load_count = {"n": 0}
        original = chart_data_module._load_slot_frame

        def _spy(state_dir, slot):  # noqa: ANN001, ANN202
            load_count["n"] += 1
            return original(state_dir, slot)

        monkeypatch.setattr(chart_data_module, "_load_slot_frame", _spy)

        years = [2025, 2026, 2099, 2100, 2101]  # 5 연도 (일부는 빈 슬라이스)
        build_chart_year_slices(state_dir_with_csvs, years=years)

        # 자산 수와 같아야 함 (= 4). 연도 수와 무관.
        assert load_count["n"] == 4, f"_load_slot_frame 이 {load_count['n']} 회 호출됨 (예상: 4)"

    def test_empty_years_returns_empty_dict(self, state_dir_with_csvs: Path):
        """빈 연도 리스트 → 빈 dict (no-op)."""
        result = build_chart_year_slices(state_dir_with_csvs, years=[])
        assert result == {}

    def test_year_without_data_returns_empty_slice(self, state_dir_with_csvs: Path):
        """CSV 가 포함하지 않는 연도 → 빈 배열 슬라이스 (에러 없음)."""
        result = build_chart_year_slices(state_dir_with_csvs, years=[2099])
        for cs in result[2099].values():
            assert cs.dates == []
            assert cs.close == []

    def test_markers_filtered_per_year(self, state_dir_with_csvs: Path):
        """
        목적: user_trades / signal_history 마커가 각 연도 범위에 맞게 필터링된다.
        """
        user_trades = {
            "sso": [
                UserTrade(date="2025-03-15", direction="buy"),
                UserTrade(date="2026-02-10", direction="sell"),
            ]
        }
        result = build_chart_year_slices(
            state_dir_with_csvs,
            years=[2025, 2026],
            user_trades=user_trades,
        )
        assert result[2025]["sso"].user_buys == ["2025-03-15"]
        assert result[2025]["sso"].user_sells == []
        assert result[2026]["sso"].user_buys == []
        assert result[2026]["sso"].user_sells == ["2026-02-10"]


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
        When:  build_chart_year_slice 호출.
        Then:  RuntimeError("내부 불변조건 위반") 발생.
        """
        # Given
        signal_history: dict[str, list[tuple[str, str]]] = {
            "sso": [("not-a-date", "buy")],
        }

        # When / Then
        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            build_chart_year_slice(
                state_dir_with_csvs,
                year=_last_date().year,
                signal_history=signal_history,
            )

    def test_user_trades_with_broken_iso_raises_value_error(self, state_dir_with_csvs: Path):
        """
        목적: user_trades 의 ISO 날짜가 파손되면 ValueError 로 즉시 실패한다.

        Given: user_trades 에 파싱 불가능한 문자열이 포함된다.
        When:  build_chart_year_slice 호출.
        Then:  ValueError 발생 (외부 입력 검증 실패).
        """
        # Given
        user_trades = {
            "sso": [UserTrade(date="bogus", direction="buy")],
        }

        # When / Then
        with pytest.raises(ValueError, match="user_trades"):
            build_chart_year_slice(
                state_dir_with_csvs,
                user_trades=user_trades,
                year=_last_date().year,
            )


# ============================================================================
# equity 차트 빌더
# ============================================================================


def _write_summary_jsonl(state_dir: Path, rows: list[dict[str, object]]) -> None:
    """``history/summary.jsonl`` 파일을 생성하여 equity 빌더 fixture 역할.

    실제 ``history.append_summary`` 와 동일한 포맷 (date / model_equity /
    actual_equity / drift_pct 4 컬럼) 을 줄 단위로 작성한다. ``drift_pct`` 는
    Git 정본의 영구 누적 컬럼이며 equity 빌더가 이 컬럼을 무시하고 RTDB
    페이로드에는 싣지 않는 것이 본 테스트의 핵심 검증 대상이다.
    """
    import json

    history_dir = state_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    target = history_dir / "summary.jsonl"
    with target.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")


class TestBuildEquityMeta:
    def test_meta_reflects_first_last_years(self, tmp_path: Path):
        """
        목적: build_equity_meta 가 summary.jsonl 의 첫/마지막 날짜와 연도 집합을
              올바르게 계산한다.

        Given: 2024-01-02, 2024-12-31, 2025-03-15, 2026-04-10 네 줄짜리 summary.
        When:  build_equity_meta 호출.
        Then:  first_date/last_date 가 각각 시작/끝 날짜, years 오름차순.
        """
        # Given
        rows = [
            {"date": "2024-01-02", "model_equity": 10_000_000, "actual_equity": 10_000_000, "drift_pct": 0.0},
            {"date": "2024-12-31", "model_equity": 10_500_000, "actual_equity": 10_400_000, "drift_pct": 0.0095},
            {"date": "2025-03-15", "model_equity": 11_000_000, "actual_equity": 10_900_000, "drift_pct": 0.0091},
            {"date": "2026-04-10", "model_equity": 12_345_678, "actual_equity": 12_300_000, "drift_pct": 0.0037},
        ]
        _write_summary_jsonl(tmp_path, rows)

        # When
        meta = build_equity_meta(tmp_path)

        # Then
        assert isinstance(meta, EquityChartMeta)
        assert meta.first_date == "2024-01-02"
        assert meta.last_date == "2026-04-10"
        assert meta.years == [2024, 2025, 2026]
        assert not hasattr(meta, "recent_months")
        assert not hasattr(meta, "archive_years")

    def test_missing_summary_raises_runtime_error(self, tmp_path: Path):
        """
        목적: summary.jsonl 이 없을 때 RuntimeError 전파 (내부 불변조건 위반).
        """
        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            build_equity_meta(tmp_path)

    def test_empty_summary_raises_runtime_error(self, tmp_path: Path):
        """
        목적: summary.jsonl 이 존재하지만 비어 있을 때 RuntimeError 전파.
        """
        # Given — 빈 파일 생성
        history_dir = tmp_path / "history"
        history_dir.mkdir(parents=True)
        (history_dir / "summary.jsonl").write_text("", encoding="utf-8")

        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            build_equity_meta(tmp_path)

    def test_corrupted_jsonl_raises_runtime_error(self, tmp_path: Path):
        """
        목적: JSONL 파싱 실패 시 RuntimeError("손상된 JSONL ...") 전파.
        """
        # Given — 유효 1 줄 + 파손 1 줄
        history_dir = tmp_path / "history"
        history_dir.mkdir(parents=True)
        (history_dir / "summary.jsonl").write_text(
            '{"date":"2026-04-10","model_equity":1,"actual_equity":1,"drift_pct":0}\n' "not a json line\n",
            encoding="utf-8",
        )

        with pytest.raises(RuntimeError, match="손상된 JSONL"):
            build_equity_meta(tmp_path)


class TestBuildEquityYearSlice:
    def test_year_slice_filters_by_year(self, tmp_path: Path):
        """
        목적: build_equity_year_slice 가 해당 연도의 로우만 포함한다.

        Given: 2024 / 2025 / 2026 세 해에 걸친 summary.
        When:  year=2025 로 호출.
        Then:  dates 의 연도가 전부 2025, 갯수 = 입력의 2025 로우 수.
        """
        # Given
        rows = [
            {"date": "2024-12-31", "model_equity": 10_000_000, "actual_equity": 10_000_000, "drift_pct": 0.0},
            {"date": "2025-01-02", "model_equity": 10_100_000, "actual_equity": 10_080_000, "drift_pct": 0.002},
            {"date": "2025-06-15", "model_equity": 10_500_000, "actual_equity": 10_400_000, "drift_pct": 0.0095},
            {"date": "2025-12-30", "model_equity": 11_000_000, "actual_equity": 10_950_000, "drift_pct": 0.0045},
            {"date": "2026-04-10", "model_equity": 12_000_000, "actual_equity": 12_000_000, "drift_pct": 0.0},
        ]
        _write_summary_jsonl(tmp_path, rows)

        # When
        series = build_equity_year_slice(tmp_path, year=2025)

        # Then
        assert isinstance(series, EquityChartSeries)
        assert series.dates == ["2025-01-02", "2025-06-15", "2025-12-30"]
        assert all(d.startswith("2025-") for d in series.dates)
        assert len(series.model_equity) == 3
        # drift_pct 시계열은 EquityChartSeries 에 포함되지 않는다 (앱 미사용으로 제거).
        assert not hasattr(series, "drift_pct")

    def test_year_slice_rounding_rules(self, tmp_path: Path):
        """
        목적: equity 는 자본금(ROUND_CAPITAL=0) 반올림. summary.jsonl 의
              drift_pct 컬럼은 equity 빌더가 무시하므로 EquityChartSeries 에
              나타나지 않는다.

        Given: 소수점이 있는 equity + Git 정본 컬럼인 drift_pct (무시 대상).
        When:  build_equity_year_slice 호출.
        Then:  equity 는 정수 값, EquityChartSeries 에 drift_pct 속성 없음.
        """
        # Given — banker's rounding 경계가 아닌 값으로 구성한다.
        rows = [
            {
                "date": "2026-04-09",
                "model_equity": 12_345_678.789,  # → 12_345_679
                "actual_equity": 12_300_000.2,  # → 12_300_000
                "drift_pct": 0.00374999,
            },
            {
                "date": "2026-04-10",
                "model_equity": 12_400_000.0,  # → 12_400_000
                "actual_equity": 12_350_001.6,  # → 12_350_002
                "drift_pct": 0.00419999,
            },
        ]
        _write_summary_jsonl(tmp_path, rows)

        # When
        series = build_equity_year_slice(tmp_path, year=2026)

        # Then — equity 는 정수 (ROUND_CAPITAL=0), drift_pct 시계열은 미포함
        assert series.model_equity == [12_345_679, 12_400_000]
        assert series.actual_equity == [12_300_000, 12_350_002]
        assert not hasattr(series, "drift_pct")

    def test_year_slice_empty_year_returns_empty_series(self, tmp_path: Path):
        """
        목적: 해당 연도에 로우가 없으면 모든 배열이 비어 있다 (에러 없음).
        """
        # Given
        rows = [
            {"date": "2024-12-31", "model_equity": 10_000_000, "actual_equity": 10_000_000, "drift_pct": 0.0},
            {"date": "2026-04-10", "model_equity": 12_000_000, "actual_equity": 12_000_000, "drift_pct": 0.0},
        ]
        _write_summary_jsonl(tmp_path, rows)

        # When
        series = build_equity_year_slice(tmp_path, year=2025)

        # Then
        assert series.dates == []
        assert series.model_equity == []
        assert series.actual_equity == []
        # drift_pct 시계열은 EquityChartSeries 에 포함되지 않는다 (앱 미사용으로 제거).
        assert not hasattr(series, "drift_pct")


class TestBuildEquityYearSlices:
    """``build_equity_year_slices`` 는 ``summary.jsonl`` 을 1 회 파싱하고 연도별로 필터링한다."""

    def test_returns_dict_keyed_by_year(self, tmp_path: Path):
        """입력 ``years`` 의 모든 연도가 결과 dict 의 키로 들어간다."""
        rows = [
            {"date": "2024-12-31", "model_equity": 10_000_000, "actual_equity": 10_000_000, "drift_pct": 0.0},
            {"date": "2025-06-15", "model_equity": 10_500_000, "actual_equity": 10_400_000, "drift_pct": 0.0095},
            {"date": "2026-04-10", "model_equity": 12_000_000, "actual_equity": 12_000_000, "drift_pct": 0.0},
        ]
        _write_summary_jsonl(tmp_path, rows)

        result = build_equity_year_slices(tmp_path, years=[2024, 2025, 2026])

        assert set(result.keys()) == {2024, 2025, 2026}
        for series in result.values():
            assert isinstance(series, EquityChartSeries)

    def test_single_year_call_matches_single_function(self, tmp_path: Path):
        """복수 함수의 단일 연도 결과는 단일 함수의 결과와 동일해야 한다."""
        rows = [
            {"date": "2025-01-02", "model_equity": 10_100_000, "actual_equity": 10_080_000, "drift_pct": 0.002},
            {"date": "2025-06-15", "model_equity": 10_500_000, "actual_equity": 10_400_000, "drift_pct": 0.0095},
        ]
        _write_summary_jsonl(tmp_path, rows)

        single = build_equity_year_slice(tmp_path, year=2025)
        batch = build_equity_year_slices(tmp_path, years=[2025])

        assert single.dates == batch[2025].dates
        assert single.model_equity == batch[2025].model_equity
        assert single.actual_equity == batch[2025].actual_equity

    def test_loads_summary_only_once(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """
        목적: N+1 회피 — ``_load_summary_rows`` 가 연도 수와 무관하게 정확히 1 회만 호출된다.
        """
        rows = [
            {"date": "2024-12-31", "model_equity": 10_000_000, "actual_equity": 10_000_000, "drift_pct": 0.0},
            {"date": "2025-06-15", "model_equity": 10_500_000, "actual_equity": 10_400_000, "drift_pct": 0.0095},
            {"date": "2026-04-10", "model_equity": 12_000_000, "actual_equity": 12_000_000, "drift_pct": 0.0},
        ]
        _write_summary_jsonl(tmp_path, rows)

        load_count = {"n": 0}
        original = chart_data_module._load_summary_rows

        def _spy(history_dir):  # noqa: ANN001, ANN202
            load_count["n"] += 1
            return original(history_dir)

        monkeypatch.setattr(chart_data_module, "_load_summary_rows", _spy)

        build_equity_year_slices(tmp_path, years=[2024, 2025, 2026])

        assert load_count["n"] == 1, f"_load_summary_rows 가 {load_count['n']} 회 호출됨 (예상: 1)"

    def test_empty_years_returns_empty_dict(self, tmp_path: Path):
        """빈 연도 리스트 → 빈 dict (no-op). summary.jsonl 부재여도 에러 없음."""
        # summary.jsonl 이 없어도 빈 입력은 즉시 빈 dict 반환
        result = build_equity_year_slices(tmp_path, years=[])
        assert result == {}

    def test_year_without_data_returns_empty_slice(self, tmp_path: Path):
        """summary 에 해당 연도가 없으면 빈 슬라이스 반환."""
        rows = [
            {"date": "2024-12-31", "model_equity": 10_000_000, "actual_equity": 10_000_000, "drift_pct": 0.0},
        ]
        _write_summary_jsonl(tmp_path, rows)

        result = build_equity_year_slices(tmp_path, years=[2025])

        assert result[2025].dates == []
        assert result[2025].model_equity == []
        assert result[2025].actual_equity == []
