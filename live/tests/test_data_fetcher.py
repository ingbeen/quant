"""live.data_fetcher yfinance 수집 및 CSV 누적 append 계약을 검증한다."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from live.data_fetcher import (
    append_today_to_csv,
    fetch_recent_ohlc,
    load_csv,
    rebuild_full_csv,
)

# ============================================================================
# 헬퍼
# ============================================================================


def _make_yfinance_like_df(
    dates: list[str],
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    closes: list[float] | None = None,
    volumes: list[int] | None = None,
) -> pd.DataFrame:
    """yfinance.Ticker.history() 가 반환하는 것과 동일한 포맷의 DataFrame 을 만든다.

    - 인덱스: ``DatetimeIndex``
    - 컬럼: Open / High / Low / Close / Volume (+ 실제는 추가 컬럼도 있지만 테스트는 무시)
    """
    n = len(dates)
    if opens is None:
        opens = [100.0 + i for i in range(n)]
    if highs is None:
        highs = [101.0 + i for i in range(n)]
    if lows is None:
        lows = [99.0 + i for i in range(n)]
    if closes is None:
        closes = [100.5 + i for i in range(n)]
    if volumes is None:
        volumes = [1000000 + i * 1000 for i in range(n)]

    idx = pd.DatetimeIndex(pd.to_datetime(dates))
    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
            "Dividends": [0.0] * n,
            "Stock Splits": [0.0] * n,
        },
        index=idx,
    )


class _FakeYfTicker:
    """`yfinance.Ticker` 를 대체하는 mock 클래스.

    `history(period=..., start=..., end=...)` 호출 시 미리 설정한 DataFrame 을 반환.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df
        self.last_kwargs: dict[str, Any] = {}

    def history(self, **kwargs: Any) -> pd.DataFrame:
        self.last_kwargs = kwargs
        return self._df.copy()


def _patch_yf_ticker(monkeypatch: pytest.MonkeyPatch, df: pd.DataFrame) -> _FakeYfTicker:
    """`live.data_fetcher` 모듈이 import 한 `yf.Ticker` 를 교체한다.

    반환값으로 마지막 호출 인자를 추적할 수 있는 fake ticker 가 돌아온다.
    """
    fake = _FakeYfTicker(df)

    def _factory(ticker: str) -> _FakeYfTicker:
        return fake

    from live import data_fetcher as module

    monkeypatch.setattr(module.yf, "Ticker", _factory)
    return fake


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    """QBT 포맷으로 CSV 저장 (Date 는 문자열)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def _make_qbt_csv_df(dates: list[str]) -> pd.DataFrame:
    """QBT CSV 포맷과 동일한 DataFrame 생성 (Date 컬럼 = 문자열)."""
    n = len(dates)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0 + i for i in range(n)],
            "High": [101.0 + i for i in range(n)],
            "Low": [99.0 + i for i in range(n)],
            "Close": [100.5 + i for i in range(n)],
            "Volume": [1000000 + i * 1000 for i in range(n)],
        }
    )


# ============================================================================
# fetch_recent_ohlc
# ============================================================================


class TestFetchRecentOhlc:
    def test_returns_dataframe_with_required_columns(self, monkeypatch):
        """yfinance 응답을 받아 QBT 표준 컬럼으로 변환한다."""
        raw = _make_yfinance_like_df(dates=["2026-04-07", "2026-04-08", "2026-04-09", "2026-04-10", "2026-04-11"])
        _patch_yf_ticker(monkeypatch, raw)

        result = fetch_recent_ohlc("SPY", days=5)

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
        assert len(result) == 5

    def test_date_column_is_date_objects(self, monkeypatch):
        """Date 컬럼은 datetime.date 객체 (pandas Timestamp 가 아닌)."""
        raw = _make_yfinance_like_df(dates=["2026-04-10", "2026-04-11"])
        _patch_yf_ticker(monkeypatch, raw)

        result = fetch_recent_ohlc("SPY", days=2)

        assert all(isinstance(d, date) for d in result["Date"])

    def test_empty_yfinance_response_raises(self, monkeypatch):
        """yfinance 가 빈 DataFrame 반환 시 ValueError."""
        empty = pd.DataFrame(
            columns=["Open", "High", "Low", "Close", "Volume"],
            index=pd.DatetimeIndex([], name="Date"),
        )
        _patch_yf_ticker(monkeypatch, empty)

        with pytest.raises(ValueError, match="yfinance"):
            fetch_recent_ohlc("SPY", days=5)

    def test_prices_rounded_to_6_decimals(self, monkeypatch):
        """가격 컬럼은 6자리 반올림 (출력 데이터 규칙)."""
        raw = _make_yfinance_like_df(
            dates=["2026-04-10"],
            opens=[100.1234567890],
            highs=[101.9876543210],
            lows=[99.111111111],
            closes=[100.5555555555],
        )
        _patch_yf_ticker(monkeypatch, raw)

        result = fetch_recent_ohlc("SPY", days=1)

        assert result["Open"].iloc[0] == pytest.approx(100.123457)
        assert result["High"].iloc[0] == pytest.approx(101.987654)
        assert result["Low"].iloc[0] == pytest.approx(99.111111)
        assert result["Close"].iloc[0] == pytest.approx(100.555556)

    def test_does_not_filter_recent_two_days(self, monkeypatch):
        """live 는 QBT 와 달리 최근 2일을 필터하지 않는다 (매일 실행 특성).

        오늘 날짜가 포함된 데이터를 반환해도 필터링 없이 그대로 전달되어야 한다.
        """
        raw = _make_yfinance_like_df(dates=["2026-04-09", "2026-04-10", "2026-04-11"])
        _patch_yf_ticker(monkeypatch, raw)

        result = fetch_recent_ohlc("SPY", days=3)

        # 3일 모두 유지되어야 한다 (2일 필터 없음)
        assert len(result) == 3

    def test_sorted_by_date_ascending(self, monkeypatch):
        """결과는 Date 오름차순 정렬."""
        raw = _make_yfinance_like_df(dates=["2026-04-11", "2026-04-09", "2026-04-10"])  # 의도적 비순서
        _patch_yf_ticker(monkeypatch, raw)

        result = fetch_recent_ohlc("SPY", days=3)

        dates_list = list(result["Date"])
        assert dates_list == sorted(dates_list)

    def test_passes_period_kwarg_to_yfinance(self, monkeypatch):
        """yfinance 에 전달되는 period 는 'Nd' 형태."""
        raw = _make_yfinance_like_df(dates=["2026-04-11"])
        fake = _patch_yf_ticker(monkeypatch, raw)

        fetch_recent_ohlc("SPY", days=7)

        assert fake.last_kwargs.get("period") == "7d"


# ============================================================================
# append_today_to_csv
# ============================================================================


class TestAppendTodayToCsv:
    def _make_today_row(self, date_str: str = "2026-04-11") -> pd.DataFrame:
        """append 대상 1행 DataFrame."""
        return pd.DataFrame(
            {
                "Date": [date.fromisoformat(date_str)],
                "Open": [105.0],
                "High": [106.0],
                "Low": [104.5],
                "Close": [105.5],
                "Volume": [2000000],
            }
        )

    def test_append_to_csv_with_3_rows_results_in_4(self, tmp_path: Path):
        """Given 3 행 CSV When append Then 4 행."""
        # Given: 3행 CSV
        existing = _make_qbt_csv_df(["2026-04-08", "2026-04-09", "2026-04-10"])
        csv_path = tmp_path / "SPY.csv"
        _write_csv(csv_path, existing)

        # When: 새 행 append
        append_today_to_csv(csv_path, self._make_today_row("2026-04-11"))

        # Then
        loaded = load_csv(csv_path)
        assert len(loaded) == 4
        assert loaded["Date"].iloc[-1] == date(2026, 4, 11)
        assert loaded["Close"].iloc[-1] == pytest.approx(105.5)

    def test_append_same_date_is_noop(self, tmp_path: Path):
        """Given 같은 날짜 이미 존재 When append Then 행수 변화 없음 (중복 방지)."""
        # Given: 같은 날짜를 포함한 CSV
        existing = _make_qbt_csv_df(["2026-04-09", "2026-04-10", "2026-04-11"])
        csv_path = tmp_path / "SPY.csv"
        _write_csv(csv_path, existing)
        initial_count = len(load_csv(csv_path))

        # When: 같은 날짜 row 재 append
        append_today_to_csv(csv_path, self._make_today_row("2026-04-11"))

        # Then: 행수 동일
        loaded = load_csv(csv_path)
        assert len(loaded) == initial_count
        # 기존 데이터가 덮어쓰이지 않았는지 확인 (첫 번째 값 유지)
        last_close = loaded[loaded["Date"] == date(2026, 4, 11)]["Close"].iloc[0]
        assert last_close == pytest.approx(102.5)  # 기존 값 (100.5 + 2)

    def test_append_to_nonexistent_file(self, tmp_path: Path):
        """Given 파일 없음 When append Then 새 파일 생성 (1 행)."""
        csv_path = tmp_path / "SPY.csv"
        assert not csv_path.exists()

        append_today_to_csv(csv_path, self._make_today_row("2026-04-11"))

        assert csv_path.exists()
        loaded = load_csv(csv_path)
        assert len(loaded) == 1
        assert loaded["Date"].iloc[0] == date(2026, 4, 11)

    def test_append_creates_parent_directory(self, tmp_path: Path):
        """부모 디렉토리가 없으면 자동 생성."""
        csv_path = tmp_path / "nested" / "sub" / "SPY.csv"
        append_today_to_csv(csv_path, self._make_today_row("2026-04-11"))
        assert csv_path.exists()

    def test_append_sorts_by_date(self, tmp_path: Path):
        """기존 데이터와 새 행이 역순이어도 저장 시 정렬된다."""
        # Given: 최신 날짜 CSV (2026-04-12)
        existing = _make_qbt_csv_df(["2026-04-12"])
        csv_path = tmp_path / "SPY.csv"
        _write_csv(csv_path, existing)

        # When: 과거 날짜 append (정상 상황은 아니지만 방어)
        append_today_to_csv(csv_path, self._make_today_row("2026-04-10"))

        # Then: 정렬되어 저장
        loaded = load_csv(csv_path)
        assert list(loaded["Date"]) == sorted(loaded["Date"])

    def test_append_rounds_prices(self, tmp_path: Path):
        """append 되는 가격은 6자리 반올림."""
        existing = _make_qbt_csv_df(["2026-04-10"])
        csv_path = tmp_path / "SPY.csv"
        _write_csv(csv_path, existing)

        row = pd.DataFrame(
            {
                "Date": [date(2026, 4, 11)],
                "Open": [105.1234567890],
                "High": [106.0],
                "Low": [104.0],
                "Close": [105.9876543210],
                "Volume": [2000000],
            }
        )
        append_today_to_csv(csv_path, row)

        loaded = load_csv(csv_path)
        new_row = loaded[loaded["Date"] == date(2026, 4, 11)]
        assert new_row["Open"].iloc[0] == pytest.approx(105.123457)
        assert new_row["Close"].iloc[0] == pytest.approx(105.987654)

    def test_append_rejects_multi_row_input(self, tmp_path: Path):
        """today_row 는 1 행이어야 한다. 다행 입력은 ValueError."""
        csv_path = tmp_path / "SPY.csv"
        multi_row = pd.DataFrame(
            {
                "Date": [date(2026, 4, 10), date(2026, 4, 11)],
                "Open": [100.0, 101.0],
                "High": [101.0, 102.0],
                "Low": [99.0, 100.0],
                "Close": [100.5, 101.5],
                "Volume": [1000, 1100],
            }
        )
        with pytest.raises(ValueError, match="1 행"):
            append_today_to_csv(csv_path, multi_row)


# ============================================================================
# load_csv
# ============================================================================


class TestLoadCsv:
    def test_load_csv_compatible_with_qbt_load_stock_data(self, tmp_path: Path):
        """Given 동일 CSV When live.load_csv 와 QBT load_stock_data 호출 Then 결과 일치."""
        from qbt.utils.data_loader import load_stock_data

        # Given
        df = _make_qbt_csv_df(["2026-04-08", "2026-04-09", "2026-04-10"])
        csv_path = tmp_path / "SPY.csv"
        _write_csv(csv_path, df)

        # When
        live_result = load_csv(csv_path)
        qbt_result = load_stock_data(csv_path)

        # Then: 완전 동일
        pd.testing.assert_frame_equal(live_result, qbt_result)

    def test_load_csv_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_csv(tmp_path / "nonexistent.csv")

    def test_load_csv_missing_column_raises(self, tmp_path: Path):
        """QBT load_stock_data 가 REQUIRED_COLUMNS 부족 시 ValueError."""
        df = pd.DataFrame({"Date": ["2026-04-10"], "Close": [100.0]})
        csv_path = tmp_path / "SPY.csv"
        _write_csv(csv_path, df)

        with pytest.raises(ValueError, match="필수 컬럼"):
            load_csv(csv_path)


# ============================================================================
# rebuild_full_csv
# ============================================================================


class TestRebuildFullCsv:
    def test_rebuild_overwrites_existing_file(self, monkeypatch, tmp_path: Path):
        """기존 CSV 가 있으면 덮어쓰기."""
        # Given: 기존 파일 (2행)
        old = _make_qbt_csv_df(["2026-01-01", "2026-01-02"])
        csv_path = tmp_path / "SPY.csv"
        _write_csv(csv_path, old)

        # yfinance mock: 전체 기간 5행
        raw = _make_yfinance_like_df(
            dates=[
                "2026-03-07",
                "2026-03-08",
                "2026-03-09",
                "2026-03-10",
                "2026-03-11",
            ]
        )
        _patch_yf_ticker(monkeypatch, raw)

        # When
        rebuild_full_csv("SPY", csv_path, period="max")

        # Then: 새 데이터로 완전 교체
        loaded = load_csv(csv_path)
        assert len(loaded) == 5
        assert loaded["Date"].iloc[0] == date(2026, 3, 7)

    def test_rebuild_creates_parent_directory(self, monkeypatch, tmp_path: Path):
        """부모 디렉토리가 없어도 자동 생성."""
        raw = _make_yfinance_like_df(dates=["2026-04-11"])
        _patch_yf_ticker(monkeypatch, raw)

        csv_path = tmp_path / "nested" / "sub" / "SPY.csv"
        rebuild_full_csv("SPY", csv_path, period="max")

        assert csv_path.exists()

    def test_rebuild_passes_period_to_yfinance(self, monkeypatch, tmp_path: Path):
        """period 인자가 yfinance 로 그대로 전달된다."""
        raw = _make_yfinance_like_df(dates=["2026-04-11"])
        fake = _patch_yf_ticker(monkeypatch, raw)

        rebuild_full_csv("SPY", tmp_path / "SPY.csv", period="6mo")

        assert fake.last_kwargs.get("period") == "6mo"

    def test_rebuild_empty_yfinance_raises(self, monkeypatch, tmp_path: Path):
        """yfinance 빈 응답 → ValueError."""
        empty = pd.DataFrame(
            columns=["Open", "High", "Low", "Close", "Volume"],
            index=pd.DatetimeIndex([], name="Date"),
        )
        _patch_yf_ticker(monkeypatch, empty)

        with pytest.raises(ValueError, match="yfinance"):
            rebuild_full_csv("SPY", tmp_path / "SPY.csv", period="max")

    def test_rebuild_saves_required_columns_only(self, monkeypatch, tmp_path: Path):
        """저장되는 CSV 는 REQUIRED_COLUMNS 만 포함 (Dividends/Stock Splits 제외)."""
        raw = _make_yfinance_like_df(dates=["2026-04-11"])
        _patch_yf_ticker(monkeypatch, raw)

        csv_path = tmp_path / "SPY.csv"
        rebuild_full_csv("SPY", csv_path, period="max")

        loaded = load_csv(csv_path)
        assert list(loaded.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]
