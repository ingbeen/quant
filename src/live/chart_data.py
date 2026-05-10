"""차트 시계열 빌더 (앱 차트 화면용, meta + years/{YYYY} 2 분할).

앱이 메타에서 존재 연도 목록을 읽고 필요한 연도 슬라이스를 그때그때 로드하도록
연도 단위로 데이터를 생성한다. 실제 RTDB 쓰기는 :mod:`live.rtdb_gateway` 의
``write_chart_meta`` / ``write_chart_year_slice`` 가 수행한다.

본 모듈은 순수 데이터 변환만 담당한다.

원칙:

- 데이터 소스: ``{state_dir}/data/stock/{TICKER}.csv``
- MA / 밴드는 QBT 의 :func:`add_single_moving_average` 재사용 (SSoT)
- 이동평균 워밍업 구간(``slot.ma_window - 1`` 개 인덱스) 은 ``None``
- 마커는 ISO 8601 날짜 문자열 (``list[str]``). 연도 슬라이스 분할에 독립적.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any, Final, Literal

from live.constants import (
    HISTORY_SUMMARY_FILENAME,
    extract_ticker_from_path,
    get_live_portfolio_config,
    live_csv_path,
)
from live.data_fetcher import load_csv
from live.models import ChartMeta, ChartSeries, EquityChartMeta, EquityChartSeries, UserTrade
from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import ROUND_CAPITAL, ROUND_PRICE
from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.common_constants import COL_CLOSE, COL_DATE

__all__ = [
    "build_chart_meta",
    "build_chart_year_slice",
    "build_chart_year_slices",
    "build_chart_meta_and_year_slices",
    "build_equity_meta",
    "build_equity_year_slice",
    "build_equity_year_slices",
]


# 마커 출처 식별자 (예외 타입 / 분기 결정에 사용).
# Literal 타입은 그대로 유지하여 호출부의 정적 검사를 보존하면서, 비교 / 메시지에는
# 본 모듈 상수를 사용해 문자열 중복을 제거한다.
SOURCE_KIND_SIGNAL_HISTORY: Final[Literal["signal_history"]] = "signal_history"
SOURCE_KIND_USER_TRADES: Final[Literal["user_trades"]] = "user_trades"


# ============================================================================
# 내부 헬퍼
# ============================================================================


def _ticker_for_chart(slot: AssetSlotConfig) -> str:
    """차트는 trade_data_path 의 티커를 우선 사용 (실제 보유 자산 가격)."""
    return extract_ticker_from_path(slot.trade_data_path)


def _to_optional_float_list(values: list[Any], decimals: int = ROUND_PRICE) -> list[float | None]:
    """NaN → None 변환 + 가격 반올림을 포함한 리스트화."""
    out: list[float | None] = []
    for v in values:
        if v is None:
            out.append(None)
        elif isinstance(v, float) and math.isnan(v):
            out.append(None)
        else:
            out.append(round(float(v), decimals))
    return out


def _load_slot_frame(state_dir: Path, slot: AssetSlotConfig) -> tuple[list[date], list[float], list[float | None]]:
    """자산 CSV 를 로드하여 (dates, close, ma_value) 를 반환한다.

    close 는 CSV 의 원본 값이므로 항상 값을 가진다 (`list[float]`).
    MA 는 QBT 의 ``add_single_moving_average`` 로 계산되며, 워밍업 구간
    (``ma_window - 1`` 개) 은 ``None`` 으로 마스킹된다.
    """
    ticker = _ticker_for_chart(slot)
    csv_path = live_csv_path(state_dir, ticker)
    df = load_csv(csv_path)

    df = add_single_moving_average(df, window=slot.ma_window, ma_type=slot.ma_type)
    ma_col = f"ma_{slot.ma_window}"

    dates: list[date] = list(df[COL_DATE].tolist())
    close_list = [round(float(c), ROUND_PRICE) for c in df[COL_CLOSE].tolist()]
    raw_ma = _to_optional_float_list(df[ma_col].tolist())

    warmup = slot.ma_window - 1
    ma_list: list[float | None] = [None] * min(warmup, len(raw_ma)) + raw_ma[warmup:]

    return dates, close_list, ma_list


def _compute_bands(
    ma_list: list[float | None],
    buy_buffer_pct: float,
    sell_buffer_pct: float,
) -> tuple[list[float | None], list[float | None]]:
    """MA 배열에서 buffer 밴드 쌍을 계산한다. MA 가 None 이면 밴드도 None."""
    upper: list[float | None] = []
    lower: list[float | None] = []
    for ma in ma_list:
        if ma is None:
            upper.append(None)
            lower.append(None)
        else:
            upper.append(round(ma * (1.0 + buy_buffer_pct), ROUND_PRICE))
            lower.append(round(ma * (1.0 - sell_buffer_pct), ROUND_PRICE))
    return upper, lower


def _slice_range(dates: list[date], start: date, end: date) -> tuple[int, int]:
    """dates 배열에서 [start, end] (양쪽 inclusive) 범위 인덱스 [lo, hi) 를 반환한다."""
    lo = 0
    hi = len(dates)
    while lo < len(dates) and dates[lo] < start:
        lo += 1
    while hi > 0 and dates[hi - 1] > end:
        hi -= 1
    if hi < lo:
        hi = lo
    return lo, hi


def _filter_markers_in_range(
    markers: list[tuple[str, str]] | list[str],
    *,
    start: date,
    end: date,
    source_kind: Literal["signal_history", "user_trades"],
    predicate: str | None = None,
) -> list[str]:
    """마커 목록에서 [start, end] 범위 내 항목만 ISO 날짜 문자열로 반환.

    ISO 날짜 파싱 실패는 소스별로 다르게 처리한다 (루트 CLAUDE.md
    "불가능 값 처리" 원칙 및 live CLAUDE.md "즉시 실패" 원칙 준수):

    - ``signal_history`` 는 live 시스템 내부(:func:`live.history.append_signal_history`)
      에서 생성되므로 파싱 실패는 **내부 불변조건 위반** → :class:`RuntimeError`.
    - ``user_trades`` 는 앱이 RTDB 로 입력한 **외부 데이터** 이므로 파싱 실패는
      입력 검증 실패 → :class:`ValueError`.

    Args:
        markers: ``list[(date_iso, state)]`` (signal_history) 또는
            ``list[str]`` (user_trades 의 날짜만 추출된 목록).
        start / end: 필터 범위 (양쪽 inclusive).
        source_kind: 마커의 출처. 예외 타입 결정에 사용된다.
        predicate: signal_history 의 경우 ``"buy"`` / ``"sell"`` 필터. None 이면 전체.

    Raises:
        RuntimeError: ``source_kind="signal_history"`` 이고 ISO 파싱 실패 시.
        ValueError: ``source_kind="user_trades"`` 이고 ISO 파싱 실패 시.
    """
    out: list[str] = []
    for entry in markers:
        if isinstance(entry, tuple):
            iso, state = entry
            if predicate is not None and state != predicate:
                continue
        else:
            iso = entry
        try:
            d = date.fromisoformat(iso)
        except ValueError as exc:
            if source_kind == SOURCE_KIND_SIGNAL_HISTORY:
                raise RuntimeError(f"내부 불변조건 위반: signal_history 의 ISO 날짜 파싱 실패 — iso={iso!r}") from exc
            raise ValueError(f"user_trades 의 ISO 날짜 형식이 잘못되었다 — iso={iso!r}") from exc
        if start <= d <= end:
            out.append(iso)
    return out


def _build_slice(
    slot: AssetSlotConfig,
    dates: list[date],
    close_list: list[float],
    ma_list: list[float | None],
    *,
    start: date,
    end: date,
    asset_user_trades: list[UserTrade],
    asset_signal_history: list[tuple[str, str]],
) -> ChartSeries:
    """[start, end] 구간 슬라이스를 ChartSeries 로 빌드.

    마커 4 종은 ISO 날짜 문자열 리스트로 저장된다.
    """
    lo, hi = _slice_range(dates, start, end)

    sliced_dates = [d.isoformat() for d in dates[lo:hi]]
    sliced_close = close_list[lo:hi]
    sliced_ma = ma_list[lo:hi]
    upper, lower = _compute_bands(sliced_ma, slot.buy_buffer_zone_pct, slot.sell_buffer_zone_pct)

    user_buys = _filter_markers_in_range(
        [t.date for t in asset_user_trades if t.direction == "buy"],
        start=start,
        end=end,
        source_kind=SOURCE_KIND_USER_TRADES,
    )
    user_sells = _filter_markers_in_range(
        [t.date for t in asset_user_trades if t.direction == "sell"],
        start=start,
        end=end,
        source_kind=SOURCE_KIND_USER_TRADES,
    )
    buy_signals = _filter_markers_in_range(
        asset_signal_history,
        start=start,
        end=end,
        source_kind=SOURCE_KIND_SIGNAL_HISTORY,
        predicate="buy",
    )
    sell_signals = _filter_markers_in_range(
        asset_signal_history,
        start=start,
        end=end,
        source_kind=SOURCE_KIND_SIGNAL_HISTORY,
        predicate="sell",
    )

    return ChartSeries(
        dates=sliced_dates,
        close=sliced_close,
        ma_value=sliced_ma,
        upper_band=upper,
        lower_band=lower,
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        user_buys=user_buys,
        user_sells=user_sells,
    )


# ============================================================================
# 공개 빌더
# ============================================================================


def build_chart_meta(state_dir: Path) -> dict[str, ChartMeta]:
    """자산별 :class:`ChartMeta` 를 생성한다.

    CSV 를 1 회 훑어 first/last 날짜와 존재하는 연도 목록을 계산한다.

    Args:
        state_dir: 정본 워크스페이스 디렉토리 (CSV 위치).

    Returns:
        ``{asset_id: ChartMeta}``.
    """
    config = get_live_portfolio_config()
    meta_map: dict[str, ChartMeta] = {}

    for slot in config.asset_slots:
        dates, _close, _ma = _load_slot_frame(state_dir, slot)
        if not dates:
            raise RuntimeError(f"내부 불변조건 위반: 자산 {slot.asset_id!r} CSV 가 비어 있음 (chart meta 생성 불가)")
        first = dates[0]
        last = dates[-1]
        years_set: set[int] = {d.year for d in dates}
        years = sorted(years_set)

        meta_map[slot.asset_id] = ChartMeta(
            first_date=first.isoformat(),
            last_date=last.isoformat(),
            ma_window=slot.ma_window,
            years=years,
        )

    return meta_map


def build_chart_year_slice(
    state_dir: Path,
    year: int,
    user_trades: dict[str, list[UserTrade]] | None = None,
    signal_history: dict[str, list[tuple[str, str]]] | None = None,
) -> dict[str, ChartSeries]:
    """자산별 특정 연도 :class:`ChartSeries` 슬라이스를 생성한다 (단일 연도).

    매 호출마다 자산별 CSV 를 로드하고 MA 를 재계산하므로, **여러 연도를 일괄
    생성할 때는** :func:`build_chart_year_slices` 를 사용하라 (자산 frame 을 1회만
    로드). 본 함수는 ``run-daily`` 가 현재 연도 1개만 갱신하는 등 단일 호출 케이스
    전용이다.

    해당 연도에 거래일이 하나도 없으면 모든 배열이 빈 슬라이스가 반환된다.

    Args:
        state_dir: 정본 워크스페이스 디렉토리.
        year: 슬라이스할 연도 (예: 2025).
        user_trades: 자산 ID → 사용자 체결 마커 리스트 (선택).
        signal_history: 자산 ID → ``(date_iso, state)`` 튜플 리스트 (선택).

    Returns:
        ``{asset_id: ChartSeries}``.
    """
    user_trades = user_trades or {}
    signal_history = signal_history or {}
    config = get_live_portfolio_config()

    start = date(year, 1, 1)
    end = date(year, 12, 31)

    slice_map: dict[str, ChartSeries] = {}

    for slot in config.asset_slots:
        dates, close_list, ma_list = _load_slot_frame(state_dir, slot)
        if not dates:
            raise RuntimeError(f"내부 불변조건 위반: 자산 {slot.asset_id!r} CSV 가 비어 있음 (chart year slice 생성 불가)")

        slice_map[slot.asset_id] = _build_slice(
            slot,
            dates,
            close_list,
            ma_list,
            start=start,
            end=end,
            asset_user_trades=user_trades.get(slot.asset_id, []),
            asset_signal_history=signal_history.get(slot.asset_id, []),
        )

    return slice_map


def build_chart_meta_and_year_slices(
    state_dir: Path,
    years: list[int] | None = None,
    user_trades: dict[str, list[UserTrade]] | None = None,
    signal_history: dict[str, list[tuple[str, str]]] | None = None,
) -> tuple[dict[str, ChartMeta], dict[int, dict[str, ChartSeries]]]:
    """``meta_map`` 과 연도 슬라이스를 한 번에 생성한다 (자산 frame 1 회 로드).

    `build_chart_meta` + `build_chart_year_slices` 를 따로 호출하면 자산 CSV 가
    각각 1 번씩 총 2 번 로드된다. 본 함수는 자산 frame 을 **자산당 정확히 1 회만**
    로드하고, meta 와 연도 슬라이스를 동시에 빌드한다. ``run-daily`` /
    ``reset`` / ``backfill-chart-years`` 의 차트 재생성 단계에서 사용한다.

    Args:
        state_dir: 정본 워크스페이스 디렉토리.
        years: 슬라이싱할 연도 리스트.

            - ``None`` (기본): meta 를 만든 뒤 자산별 ``meta.years`` 의 합집합을 자동
              사용. ``reset`` / ``backfill --target=all`` 처럼 "모든 가능 연도"를
              슬라이스할 때 사용한다 (자산 frame 1 회 로드 보장).
            - 빈 리스트: meta 만 만들고 슬라이스는 빈 dict 반환.
            - 명시 리스트: 해당 연도들만 슬라이스 (``run-daily`` 의 단일 연도 등).
        user_trades: 자산 ID → 사용자 체결 마커 리스트 (선택).
        signal_history: 자산 ID → ``(date_iso, state)`` 튜플 리스트 (선택).

    Returns:
        ``(meta_map, slices_map)`` 튜플:

        - ``meta_map``: ``{asset_id: ChartMeta}``
        - ``slices_map``: ``{year: {asset_id: ChartSeries}}``.
    """
    user_trades = user_trades or {}
    signal_history = signal_history or {}
    config = get_live_portfolio_config()

    # 자산별 frame 을 1 회만 로드 (CSV + MA 계산)
    asset_frames: dict[str, tuple[AssetSlotConfig, list[date], list[float], list[float | None]]] = {}
    for slot in config.asset_slots:
        dates, close_list, ma_list = _load_slot_frame(state_dir, slot)
        if not dates:
            raise RuntimeError(f"내부 불변조건 위반: 자산 {slot.asset_id!r} CSV 가 비어 있음 (chart meta+slices 생성 불가)")
        asset_frames[slot.asset_id] = (slot, dates, close_list, ma_list)

    # meta 빌드 (frame 재사용)
    meta_map: dict[str, ChartMeta] = {}
    for asset_id, (slot, dates, _close, _ma) in asset_frames.items():
        first = dates[0]
        last = dates[-1]
        years_set: set[int] = {d.year for d in dates}
        meta_map[asset_id] = ChartMeta(
            first_date=first.isoformat(),
            last_date=last.isoformat(),
            ma_window=slot.ma_window,
            years=sorted(years_set),
        )

    # years 가 None 이면 자산별 meta.years 의 합집합을 자동 사용 (reset / backfill 전체 모드)
    if years is None:
        union_years: set[int] = set()
        for meta in meta_map.values():
            union_years.update(meta.years)
        target_years = sorted(union_years)
    else:
        target_years = years

    # 연도별 슬라이스 빌드 (frame 재사용)
    slices_map: dict[int, dict[str, ChartSeries]] = {}
    for year in target_years:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        slice_map: dict[str, ChartSeries] = {}
        for asset_id, (slot, dates, close_list, ma_list) in asset_frames.items():
            slice_map[asset_id] = _build_slice(
                slot,
                dates,
                close_list,
                ma_list,
                start=start,
                end=end,
                asset_user_trades=user_trades.get(asset_id, []),
                asset_signal_history=signal_history.get(asset_id, []),
            )
        slices_map[year] = slice_map

    return meta_map, slices_map


def build_chart_year_slices(
    state_dir: Path,
    years: list[int],
    user_trades: dict[str, list[UserTrade]] | None = None,
    signal_history: dict[str, list[tuple[str, str]]] | None = None,
) -> dict[int, dict[str, ChartSeries]]:
    """**여러 연도** 의 자산별 :class:`ChartSeries` 슬라이스를 일괄 생성한다.

    자산별 CSV 로드 + MA 계산을 **자산당 1회** 만 수행하고, 각 연도별로 메모리
    내에서 슬라이싱한다. ``reset`` / ``backfill-chart-years`` 처럼 N 개 연도를
    한 번에 재생성할 때 사용한다.

    빈 ``years`` 리스트는 빈 dict 를 반환한다 (no-op). 해당 연도에 거래일이
    하나도 없는 경우 그 연도 슬라이스는 빈 배열로 채워진다.

    Args:
        state_dir: 정본 워크스페이스 디렉토리.
        years: 슬라이싱할 연도 리스트 (정렬 권장).
        user_trades: 자산 ID → 사용자 체결 마커 리스트 (선택).
        signal_history: 자산 ID → ``(date_iso, state)`` 튜플 리스트 (선택).

    Returns:
        ``{year: {asset_id: ChartSeries}}``. 입력 ``years`` 의 모든 연도가 키로 포함된다.
    """
    user_trades = user_trades or {}
    signal_history = signal_history or {}
    config = get_live_portfolio_config()

    if not years:
        return {}

    # 자산별 frame 을 1 회만 로드 (CSV + MA 계산)
    asset_frames: dict[str, tuple[AssetSlotConfig, list[date], list[float], list[float | None]]] = {}
    for slot in config.asset_slots:
        dates, close_list, ma_list = _load_slot_frame(state_dir, slot)
        if not dates:
            raise RuntimeError(f"내부 불변조건 위반: 자산 {slot.asset_id!r} CSV 가 비어 있음 (chart year slices 생성 불가)")
        asset_frames[slot.asset_id] = (slot, dates, close_list, ma_list)

    # 연도별로 메모리 내 슬라이싱
    result: dict[int, dict[str, ChartSeries]] = {}
    for year in years:
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        slice_map: dict[str, ChartSeries] = {}
        for asset_id, (slot, dates, close_list, ma_list) in asset_frames.items():
            slice_map[asset_id] = _build_slice(
                slot,
                dates,
                close_list,
                ma_list,
                start=start,
                end=end,
                asset_user_trades=user_trades.get(asset_id, []),
                asset_signal_history=signal_history.get(asset_id, []),
            )
        result[year] = slice_map

    return result


# ============================================================================
# equity 차트 빌더 (/charts/equity/)
# ============================================================================


def _load_summary_rows(history_dir: Path) -> list[dict[str, Any]]:
    """``history/summary.jsonl`` 을 로드하여 날짜 오름차순 dict 리스트 반환.

    파일이 없거나 비어 있으면 :class:`RuntimeError` 전파 — daily runner 는 본 함수
    호출 시점에 당일 1 줄이 이미 append 되어 있음을 전제한다 (run-daily 의
    ``_persist_history`` → ``_publish_to_rtdb`` 순서).

    Raises:
        RuntimeError:
            - ``summary.jsonl`` 이 없거나 비어 있을 때 (내부 불변조건 위반).
            - JSONL 파싱 실패 시 (손상된 파일).
    """
    target = history_dir / HISTORY_SUMMARY_FILENAME
    if not target.exists():
        raise RuntimeError(f"내부 불변조건 위반: equity 차트 빌더 호출 시 {target} 가 없음 " "(run-daily 순서상 _persist_history 가 선행되어야 함)")

    content = target.read_text(encoding="utf-8").strip()
    if not content:
        raise RuntimeError(f"내부 불변조건 위반: {target} 가 비어 있음 (equity 차트 생성 불가)")

    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"손상된 JSONL (summary, {line_no}행): {exc}") from exc

    rows.sort(key=lambda r: str(r["date"]))
    return rows


def _equity_series_from_rows(rows: list[dict[str, Any]]) -> EquityChartSeries:
    """summary 로우 리스트를 :class:`EquityChartSeries` 로 변환 (반올림 포함).

    summary.jsonl 의 ``drift_pct`` 컬럼은 GCS 정본의 영구 누적 데이터이며
    equity 차트 시계열에는 포함하지 않는다 (앱 미사용 — drift 스칼라는
    ``/latest/portfolio.drift_pct`` 에서 노출).
    """
    dates: list[str] = []
    model_equity: list[float] = []
    actual_equity: list[float] = []
    for row in rows:
        dates.append(str(row["date"]))
        model_equity.append(round(float(row["model_equity"]), ROUND_CAPITAL))
        actual_equity.append(round(float(row["actual_equity"]), ROUND_CAPITAL))
    return EquityChartSeries(
        dates=dates,
        model_equity=model_equity,
        actual_equity=actual_equity,
    )


def build_equity_meta(state_dir: Path) -> EquityChartMeta:
    """`history/summary.jsonl` 전체를 읽어 :class:`EquityChartMeta` 를 생성한다.

    Args:
        state_dir: 정본 워크스페이스 디렉토리 (``history/`` 하위).

    Returns:
        :class:`EquityChartMeta` 인스턴스.
    """
    rows = _load_summary_rows(state_dir / "history")
    first = str(rows[0]["date"])
    last = str(rows[-1]["date"])
    years = sorted({date.fromisoformat(str(r["date"])).year for r in rows})
    return EquityChartMeta(
        first_date=first,
        last_date=last,
        years=years,
    )


def build_equity_year_slice(state_dir: Path, year: int) -> EquityChartSeries:
    """특정 연도 equity 슬라이스를 생성한다 (단일 연도).

    매 호출마다 ``summary.jsonl`` 을 다시 파싱하므로, **여러 연도를 일괄 생성할 때**
    는 :func:`build_equity_year_slices` 를 사용하라 (1회 파싱). 본 함수는
    ``run-daily`` 가 현재 연도 1개만 갱신하는 단일 호출 케이스 전용이다.

    해당 연도에 summary 로우가 하나도 없으면 모든 배열이 빈 슬라이스가 반환된다.

    Args:
        state_dir: 정본 워크스페이스 디렉토리.
        year: 슬라이스할 연도 (예: 2025).

    Returns:
        :class:`EquityChartSeries` 인스턴스.
    """
    rows = _load_summary_rows(state_dir / "history")
    filtered = [r for r in rows if date.fromisoformat(str(r["date"])).year == year]
    return _equity_series_from_rows(filtered)


def build_equity_year_slices(state_dir: Path, years: list[int]) -> dict[int, EquityChartSeries]:
    """**여러 연도** 의 equity :class:`EquityChartSeries` 슬라이스를 일괄 생성한다.

    ``summary.jsonl`` 을 1 회만 파싱하고, 각 연도별로 메모리 내에서 필터링한다.
    ``reset`` / ``backfill-chart-years`` 처럼 N 개 연도를 한 번에 재생성할 때
    사용한다.

    빈 ``years`` 리스트는 빈 dict 를 반환한다 (no-op). 해당 연도에 summary 로우가
    하나도 없는 경우 그 연도 슬라이스는 빈 배열로 채워진다.

    Args:
        state_dir: 정본 워크스페이스 디렉토리.
        years: 슬라이싱할 연도 리스트.

    Returns:
        ``{year: EquityChartSeries}``. 입력 ``years`` 의 모든 연도가 키로 포함된다.
    """
    if not years:
        return {}
    rows = _load_summary_rows(state_dir / "history")
    result: dict[int, EquityChartSeries] = {}
    for year in years:
        filtered = [r for r in rows if date.fromisoformat(str(r["date"])).year == year]
        result[year] = _equity_series_from_rows(filtered)
    return result
