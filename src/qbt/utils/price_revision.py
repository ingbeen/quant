"""다시 받은 시세 ↔ 기존 시세 파일 판정

야후는 수정 종가를 요청마다 미세하게 다르게 주고, 배당 기록을 늦게 넣거나 넣었다가 빼기도 한다.
다시 받은 응답을 기존 파일과 견줘 셋으로 가른다 — 흔들림뿐(기존 행 그대로 + 새 날짜 행), 응답의 배당 · 분할 기록으로
설명되는 변화(응답으로 덮어씀), 그 밖(비정상 — 덮어쓸지는 사람이 정한다). 기준값의 근거는
docs/research/합성_시세_연장.md 결정 14.
"""

import math
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from qbt.common_constants import COL_CLOSE, COL_DATE, PRICE_COLUMNS, REQUIRED_COLUMNS

# 흔들림 상한(상대) — 관측 흔들림 최대 4.9e-6 의 4배, 가장 작은 배당(배당 ÷ 전날 종가) 5.9e-5 의 1/3 (2026-11-07)
# 기록과 맞출 때도 같은 상한으로 비율을 견줌 — 야후 배당 1,438건의 (1 + 계단) ÷ 기록 비율이 최대 2.1e-6 안
REVISION_NOISE_TOLERANCE: Final = 2e-5
MAX_ISSUE_LINES: Final = 5
RECENT_DIVIDEND_COUNT: Final = 3
_DATE_ISSUE_WEIGHT: Final = float("inf")  # 날짜 변화는 가격 변화보다 앞에 낸다


class RevisionKind(Enum):
    NEW = "새 파일"
    NOISE = "흔들림뿐"
    EXPLAINED = "기록으로 설명되는 변화"
    ABNORMAL = "비정상"


@dataclass(frozen=True)
class PriceEvents:
    """응답의 배당 · 분할 기록과 원시 종가 — 기준일로 잘라내기 전 전체 응답(수정 비율이 잘라낸 날의 배당까지 반영한다).

    dividends · splits 는 날짜(date) → 금액 · 배수(값이 있는 날만), raw_close 는 날짜 오름차순의 원시 종가다.
    """

    dividends: pd.Series
    splits: pd.Series
    raw_close: pd.Series


@dataclass(frozen=True)
class PriceRevision:
    """판정 결과. prices 는 이 판정대로 저장할 표 — 비정상이면 사람이 덮어쓰기로 정했을 때 저장할 응답이다."""

    kind: RevisionKind
    prices: pd.DataFrame
    issues: tuple[str, ...]  # 비정상 원인 줄 — 큰 것부터
    applied: tuple[str, ...]  # 기록으로 설명된 변화
    existing_end: date | None
    existing_rows: int
    response_end: date
    response_rows: int
    recent_dividends: tuple[tuple[date, float], ...]


@dataclass(frozen=True)
class _Issue:
    weight: float  # 줄 순서 — 변화의 크기
    text: str


@dataclass(frozen=True)
class _Event:
    day: date
    factor: float  # 그날 앞 가격에 곱해지는 조정 비율
    description: str


def judge_revision(
    existing: pd.DataFrame | None,
    response: pd.DataFrame,
    events: PriceEvents,
    *,
    price_decimals: int,
) -> PriceRevision:
    """
    다시 받은 응답을 기존 시세와 견줘 가른다.

    Args:
        existing: 기존 파일 (load_stock_data 모양 — 날짜 오름차순, 가격은 price_decimals 자리). 없으면 None
        response: 받은 시세 (REQUIRED_COLUMNS, 날짜 오름차순, 기준일까지)
        events: 같은 응답의 배당 · 분할 기록과 원시 종가
        price_decimals: 기존 파일 가격의 자릿수 — 반올림 오차는 변화로 보지 않는다

    Returns:
        PriceRevision

    Raises:
        ValueError: 응답이나 기존 파일이 비었을 때
    """
    if response.empty:
        raise ValueError("받은 시세가 비어 있습니다 — 판정할 수 없습니다")
    if existing is not None and existing.empty:
        raise ValueError("기존 시세 파일에 행이 없습니다 — 그 파일을 지우고 다시 받으세요")
    response = response.reset_index(drop=True)
    recent = _recent_dividends(events.dividends)
    response_end: date = response[COL_DATE].iloc[-1]

    if existing is None:
        return PriceRevision(
            kind=RevisionKind.NEW,
            prices=response,
            issues=(),
            applied=(),
            existing_end=None,
            existing_rows=0,
            response_end=response_end,
            response_rows=len(response),
            recent_dividends=recent,
        )

    existing = existing.reset_index(drop=True)
    existing_end: date = existing[COL_DATE].iloc[-1]
    known = response[response[COL_DATE] <= existing_end]
    new_rows = response[response[COL_DATE] > existing_end]

    issues = _date_issues(existing[COL_DATE], known[COL_DATE])
    pair = existing[[COL_DATE, *PRICE_COLUMNS]].merge(
        known[[COL_DATE, *PRICE_COLUMNS]], on=COL_DATE, suffixes=("_e", "_r")
    )
    stored = pair[[f"{col}_e" for col in PRICE_COLUMNS]].to_numpy(dtype=float)
    received = pair[[f"{col}_r" for col in PRICE_COLUMNS]].to_numpy(dtype=float)
    half_unit = 0.5 * 10.0**-price_decimals

    def revision(kind: RevisionKind, prices: pd.DataFrame, found: list[_Issue], applied: list[str]) -> PriceRevision:
        ordered = sorted(found, key=lambda issue: -issue.weight)
        return PriceRevision(
            kind=kind,
            prices=prices,
            issues=tuple(issue.text for issue in ordered),
            applied=tuple(applied),
            existing_end=existing_end,
            existing_rows=len(existing),
            response_end=response_end,
            response_rows=len(response),
            recent_dividends=recent,
        )

    if not issues and _within_noise(stored, received, half_unit):
        kept = pd.concat([existing[REQUIRED_COLUMNS], new_rows[REQUIRED_COLUMNS]], ignore_index=True)
        return revision(RevisionKind.NOISE, kept, [], [])

    dates = list(pair[COL_DATE])
    price_issues, applied = _price_issues(dates, stored, received, events, half_unit)
    issues += price_issues
    # 흔들림 상한은 넘었는데 맞춘 기록도 잡힌 원인도 없음 → 설명되지 않은 변화라 덮어쓰지 않음
    if not issues and not applied:
        issues.append(_unrecorded_small_change(dates, stored, received, half_unit))
    kind = RevisionKind.ABNORMAL if issues else RevisionKind.EXPLAINED
    return revision(kind, response, issues, applied)


def _within_noise(stored: np.ndarray, received: np.ndarray, half_unit: float) -> bool:
    # 기존 값은 반올림돼 저장돼 참값과 반 단위까지 다름 → 상한에 반 단위를 더함
    return bool(np.all(np.abs(received - stored) <= REVISION_NOISE_TOLERANCE * np.abs(stored) + half_unit))


def _date_issues(existing_dates: pd.Series, known_dates: pd.Series) -> list[_Issue]:
    stored = set(existing_dates)
    received = set(known_dates)
    first: date = existing_dates.iloc[0]
    missing = sorted(stored - received)
    added = sorted(received - stored)
    before = [day for day in added if day < first]
    inside = [day for day in added if day > first]
    issues: list[_Issue] = []
    if missing:
        issues.append(_Issue(_DATE_ISSUE_WEIGHT, f"기존 날짜 {len(missing):,}개가 응답에 없음 — {_span(missing)}"))
    if inside:
        issues.append(_Issue(_DATE_ISSUE_WEIGHT, f"기존 기간 안에 새 날짜 {len(inside):,}개 — {_span(inside)}"))
    if before:
        issues.append(_Issue(_DATE_ISSUE_WEIGHT, f"기존 첫날({first}) 앞에 날짜 {len(before):,}개가 생김 — {_span(before)}"))
    return issues


def _span(days: Sequence[date]) -> str:
    return str(days[0]) if len(days) == 1 else f"{days[0]} ~ {days[-1]}"


def _row_span(dates: list[date], rows: np.ndarray) -> str:
    return _span([dates[rows[0]], dates[rows[-1]]]) if rows.size > 1 else str(dates[rows[0]])


def _unrecorded_small_change(dates: list[date], stored: np.ndarray, received: np.ndarray, half_unit: float) -> _Issue:
    beyond = np.abs(received - stored) > REVISION_NOISE_TOLERANCE * np.abs(stored) + half_unit
    rows = np.flatnonzero(beyond.any(axis=1))
    if rows.size == 0:
        raise RuntimeError("내부 불변조건 위반: 흔들림 상한을 넘은 값이 없는데 흔들림 판정을 지나왔습니다")
    deviation = received / stored - 1
    worst = float(deviation.flat[np.argmax(np.where(beyond, np.abs(deviation), 0.0))])
    return _Issue(
        abs(worst),
        f"기록 없는 작은 변화 — {rows.size:,}행이 흔들림 상한을 넘음, 가장 큰 차 {worst:+.4%} ({_row_span(dates, rows)})",
    )


def _price_issues(
    dates: list[date],
    stored: np.ndarray,
    received: np.ndarray,
    events: PriceEvents,
    half_unit: float,
) -> tuple[list[_Issue], list[str]]:
    """겹친 날짜의 가격 변화를 기록과 맞춘다 — (비정상 원인, 기록으로 설명된 변화)."""
    if not dates:
        return [], []
    ratio = received / stored
    floor = half_unit / stored  # 기존 값 반올림 오차의 상대 크기
    close = PRICE_COLUMNS.index(COL_CLOSE)
    raw_dates: list[date] = list(events.raw_close.index)
    raw_values = events.raw_close.to_numpy(dtype=float)

    issues: list[_Issue] = []
    column_issue = _column_mismatch_issue(dates, ratio, floor, close)
    if column_issue is not None:
        issues.append(column_issue)

    close_ratio = ratio[:, close]
    close_floor = floor[:, close]
    step_issues, matched_rows, applied = _step_issues(dates, close_ratio, close_floor, events, raw_dates, raw_values)
    issues += step_issues
    tail_issue, tail_applied = _tail_issue(dates, close_ratio[-1], close_floor[-1], events, raw_dates, raw_values)
    if tail_issue is not None:
        issues.append(tail_issue)
    applied += tail_applied

    if not issues:
        drift_issue = _drift_issue(dates, close_ratio, close_floor, matched_rows)
        if drift_issue is not None:
            issues.append(drift_issue)
    return issues, applied


def _column_mismatch_issue(dates: list[date], ratio: np.ndarray, floor: np.ndarray, close: int) -> _Issue | None:
    # 조정은 한 행의 네 가격에 같은 비율로 걸림 → 비율이 열마다 다르면 봉 자체가 바뀐 것
    others = [i for i in range(len(PRICE_COLUMNS)) if i != close]
    deviation = ratio[:, others] / ratio[:, [close]] - 1
    allowed = REVISION_NOISE_TOLERANCE + floor[:, others] + floor[:, [close]]
    bad = np.abs(deviation) > allowed
    rows = np.flatnonzero(bad.any(axis=1))
    if rows.size == 0:
        return None
    worst = float(deviation.flat[np.argmax(np.abs(np.where(bad, deviation, 0.0)))])
    return _Issue(
        abs(worst),
        f"{rows.size:,}행에서 시가 · 고가 · 저가가 종가와 다르게 바뀜 — 가장 큰 차 {worst:+.3%} ({_row_span(dates, rows)})",
    )


def _step_issues(
    dates: list[date],
    close_ratio: np.ndarray,
    close_floor: np.ndarray,
    events: PriceEvents,
    raw_dates: list[date],
    raw_values: np.ndarray,
) -> tuple[list[_Issue], set[int], list[str]]:
    """이웃한 두 날 사이 종가 비율의 계단을 그 사이 기록과 맞춘다 — (비정상 원인, 기록과 맞은 행, 설명된 변화)."""
    steps = close_ratio[:-1] / close_ratio[1:] - 1  # steps[k]: dates[k] 와 dates[k + 1] 사이
    allowed = REVISION_NOISE_TOLERANCE + close_floor[:-1] + close_floor[1:]
    recorded = _events_by_row(dates, _records(events, raw_dates, raw_values, after=dates[0], until=dates[-1]))

    issues: list[_Issue] = []
    matched_rows: set[int] = set()
    applied: list[str] = []
    for k in np.flatnonzero(np.abs(steps) > allowed):
        row = int(k) + 1
        step = float(steps[k])
        day = dates[row]
        prefix = f"{day} 이전 {row:,}행 {step:+.3%}"
        record = recorded.get(row)
        if record is None:
            issues.append(_Issue(abs(step), f"{prefix} — {_unrecorded_cause(step, day, raw_dates, raw_values)}"))
            continue
        factor, description = record
        if not _usable(factor):
            issues.append(_Issue(abs(step), f"{prefix} — 조정 비율을 셀 수 없는 기록 (응답 기록: {description})"))
            continue
        # 크기에 비례한 허용은 분할(1 ÷ 배수) 같은 큰 기록에 다른 변화를 함께 묻힘 → 비율로 견줌
        if abs((1 + step) / factor - 1) <= float(allowed[k]):
            matched_rows.add(row)
            applied.append(f"{description} — {day} 이전 {row:,}행 {step:+.3%}")
        else:
            issues.append(_Issue(abs(step), f"{prefix} — 기록대로면 {factor - 1:+.3%} (응답 기록: {description})"))
    return issues, matched_rows, applied


def _unrecorded_cause(step: float, day: date, raw_dates: list[date], raw_values: np.ndarray) -> str:
    # 관측은 두 파일의 상대 크기뿐 — 어느 쪽에 조정이 있는지 · 원인이 배당인지는 모름 → 추정으로만 적음
    if step <= 0:
        return "그날 앞에서 응답 가격이 기존보다 낮음 · 응답에 그날 배당 · 분할 기록 없음"
    # 기록이 빠진 배당은 그날 앞 가격을 1 ÷ (1 − 배당 ÷ 전날 종가) 배로 올림 → 배당 = 전날 종가 × s ÷ (1 + s)
    previous = _previous_close(day, raw_dates, raw_values)
    amount = f"약 ${previous * step / (1 + step):.3f}" if previous is not None else "(전날 종가 없음)"
    return f"그날 앞에서 기존 가격이 응답보다 낮음(빠진 배당이라면 {amount}) · 응답에 그날 배당 · 분할 기록 없음"


def _tail_issue(
    dates: list[date],
    tail_ratio: float,
    tail_floor: float,
    events: PriceEvents,
    raw_dates: list[date],
    raw_values: np.ndarray,
) -> tuple[_Issue | None, list[str]]:
    """기존 끝날의 종가 비율을 그 뒤 기록과 맞춘다 — (비정상 원인, 설명된 변화)."""
    last = dates[-1]
    later = _records(events, raw_dates, raw_values, after=last)
    allowed = REVISION_NOISE_TOLERANCE + float(tail_floor)
    # 앞쪽 몇 건은 기존 파일이 잘라낸 날의 배당으로 이미 반영했을 수 있음 → 앞에서부터 빼 보며 맞춤
    for skipped in range(len(later) + 1):
        rest = later[skipped:]
        expected = float(np.prod([event.factor for event in rest])) if rest else 1.0
        if _usable(expected) and abs(tail_ratio / expected - 1) <= allowed:
            return None, [f"{event.description} — 기존 끝날 {last} 뒤" for event in rest]
    later_text = " · ".join(event.description for event in later) if later else "없음"
    change = float(tail_ratio) - 1
    return _Issue(abs(change), f"기존 끝날 {last} 까지 {len(dates):,}행 {change:+.3%} — 기존 끝날 뒤 응답 기록 {later_text}"), []


def _drift_issue(
    dates: list[date], close_ratio: np.ndarray, close_floor: np.ndarray, matched_rows: set[int]
) -> _Issue | None:
    # 기록과 맞은 계단만으로 끝날부터 비율을 다시 쌓음 → 실제 비율과 다르면 상한 아래 계단이 쌓인 것
    rebuilt = np.empty_like(close_ratio)
    rebuilt[-1] = close_ratio[-1]
    for row in range(len(close_ratio) - 1, 0, -1):
        step = close_ratio[row - 1] / close_ratio[row] if row in matched_rows else 1.0
        rebuilt[row - 1] = rebuilt[row] * step
    deviation = close_ratio / rebuilt - 1
    allowed = REVISION_NOISE_TOLERANCE + close_floor + close_floor[-1]
    bad = np.flatnonzero(np.abs(deviation) > allowed)
    if bad.size == 0:
        return None
    worst = int(bad[np.argmax(np.abs(deviation[bad]))])
    return _Issue(
        abs(float(deviation[worst])),
        f"작은 변화가 쌓임 — {_row_span(dates, bad)} 에서 최대 {float(deviation[worst]):+.3%}",
    )


def _records(
    events: PriceEvents,
    raw_dates: list[date],
    raw_values: np.ndarray,
    *,
    after: date,
    until: date | None = None,
) -> list[_Event]:
    """after < 날짜 ≤ until 인 배당 · 분할 기록 (날짜순). 배당의 조정 비율은 1 − 배당 ÷ 전날 원시 종가, 분할은 1 ÷ 배수."""

    def in_range(day: date) -> bool:
        return day > after and (until is None or day <= until)

    found: list[_Event] = []
    dividend_days: list[date] = list(events.dividends.index)
    for day, amount in zip(dividend_days, events.dividends.to_numpy(dtype=float), strict=True):
        if not in_range(day):
            continue
        previous = _previous_close(day, raw_dates, raw_values)
        # 응답 첫날의 배당은 앞 행이 없어 어느 가격도 바꾸지 않음
        if previous is not None:
            factor = 1 - float(amount) / previous if previous > 0 else math.nan
            found.append(_Event(day, factor, f"{day} 배당 ${float(amount):.3f}"))
    split_days: list[date] = list(events.splits.index)
    for day, ratio in zip(split_days, events.splits.to_numpy(dtype=float), strict=True):
        if in_range(day):
            found.append(_Event(day, 1 / float(ratio) if ratio > 0 else math.nan, f"{day} 분할 {float(ratio):g}배"))
    return sorted(found, key=lambda event: event.day)


def _usable(factor: float) -> bool:
    # 배당 ≥ 전날 종가 · 분할 배수 0 또는 무한(야후 분모 0)이면 0 · 무한 · nan → 어떤 계단도 설명하지 못함
    return math.isfinite(factor) and factor > 0


def _events_by_row(dates: list[date], events: list[_Event]) -> dict[int, tuple[float, str]]:
    """겹친 날짜의 행마다 (그 행과 앞 행 사이 기록들의 조정 비율 곱, 설명)."""
    by_row: dict[int, tuple[float, list[str]]] = {}
    for event in events:
        row = bisect_left(dates, event.day)  # 기록 날짜 이후의 첫 행 — 휴장일 기록도 다음 거래일에 걸린다
        factor, descriptions = by_row.get(row, (1.0, []))
        by_row[row] = (factor * event.factor, [*descriptions, event.description])
    return {row: (factor, " · ".join(descriptions)) for row, (factor, descriptions) in by_row.items()}


def _previous_close(day: date, raw_dates: list[date], raw_values: np.ndarray) -> float | None:
    position = bisect_left(raw_dates, day)
    return float(raw_values[position - 1]) if position > 0 else None


def _recent_dividends(dividends: pd.Series) -> tuple[tuple[date, float], ...]:
    latest = dividends.sort_index().iloc[-RECENT_DIVIDEND_COUNT:]
    days: list[date] = list(latest.index)
    return tuple((day, float(amount)) for day, amount in zip(days, latest.to_numpy(dtype=float), strict=True))


def format_abnormal_block(
    entries: Sequence[tuple[str, Path, PriceRevision]],
    *,
    run_at: datetime,
    cutoff_date: date,
    yfinance_version: str,
) -> str:
    """
    비정상 종목의 원인 블록 — 사용자가 그대로 AI 에 붙여 판단을 받는다.

    Args:
        entries: (티커, 파일 경로, 비정상 판정)
        run_at: 실행 시각 (시간대 포함)
        cutoff_date: 받을 마지막 날
        yfinance_version: 받은 yfinance 버전
    """
    lines = [
        "[download_data 비정상 판정 — 이 블록을 그대로 AI 에 붙여 판단을 받으세요]",
        f"실행 {run_at:%Y-%m-%d %H:%M} {run_at.tzname()} · 기준일 {cutoff_date} · yfinance {yfinance_version}",
        "판단 요청: 아래 변화가 야후 쪽 오류인지 실제 정정인지, 이번 응답으로 덮어써도 되는지",
    ]
    for ticker, path, revision in entries:
        lines.append("")
        lines.append(
            f"{ticker} — {path} (기존 ~ {revision.existing_end} {revision.existing_rows:,}행 · "
            f"응답 ~ {revision.response_end} {revision.response_rows:,}행)"
        )
        lines += [f"  - {issue}" for issue in revision.issues[:MAX_ISSUE_LINES]]
        if len(revision.issues) > MAX_ISSUE_LINES:
            lines.append(f"  - 외 {len(revision.issues) - MAX_ISSUE_LINES:,}건")
        if revision.recent_dividends:
            recent = " · ".join(f"{day} ${amount:.3f}" for day, amount in revision.recent_dividends)
            lines.append(f"  - 응답의 최근 배당: {recent}")
        else:
            lines.append("  - 응답에 배당 기록 없음")
        lines.append("  y = 응답으로 덮어씀(위 변화가 저장됨) · N = 기존 파일 그대로(새 날짜도 붙지 않음)")
    return "\n".join(lines)
