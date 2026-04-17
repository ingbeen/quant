"""영구 히스토리 저장 (qbt-live-state/history/).

Git 정본 원장 — 모든 히스토리는 **영구 보존** 된다. 자동 정리는 하지 않는다.

파일 종류 (상수는 :mod:`live.constants` 참조):

- ``history/daily/{YYYY-MM-DD}.json`` — 일별 상세 로그 (덮어쓰기 가능)
- ``history/states/{YYYY-MM-DD}.json`` — 일별 ``live_state.json`` 전체 스냅샷
  (덮어쓰기 가능). ``run-daily`` 종료 시점의 LiveState 를 날짜 키 파일로 보존하며,
  저장 로직은 :func:`live.state.save_state_snapshot` 이 담당한다.
- ``history/summary.jsonl`` — 일별 요약 (1 줄당 1 일, append-only)
- ``history/user_trades.jsonl`` — 사용자 체결 입력 누적 (append-only, 차트 마커)
- ``history/signals.jsonl`` — 자산별 신호 이력 누적 (append-only, 차트 마커)
- ``history/balance_adjusts.jsonl`` — 자산 직접 보정 audit (append-only)

JSONL append 정책:

- 같은 날짜 / 같은 trade 가 두 번 호출되어도 **덮어쓰지 않고 줄을 추가**한다.
- 호출자가 idempotency 를 보장해야 한다 (:func:`live.drift.apply_fills_idempotent`).

확장 스키마 (RTDB ``/history/`` 미러를 위한 정보량 동등화):

- ``user_trades.jsonl``: 차트 마커용 ``asset_id`` / ``date`` / ``direction`` 외에
  ``actual_price`` / ``actual_shares`` / ``trade_date`` / ``input_time_kst`` /
  ``memo`` / ``reason`` / ``rtdb_key`` / ``applied_at`` 을 함께 기록한다.
- ``balance_adjusts.jsonl``: 기존 필드 + ``applied_at``.
- ``signals.jsonl``: 기존 ``date`` / ``asset_id`` / ``state`` 외에 ``close`` /
  ``ma_value`` / ``ma_distance_pct`` / ``upper_band`` / ``lower_band``.

raw 로더 (:func:`load_user_trades_raw` / :func:`load_balance_adjusts_raw` /
:func:`load_signal_history_raw`) 는 dict 그대로 반환하여 ``backfill-history`` CLI
가 RTDB 페이로드로 그대로 사용할 수 있게 한다. 차트 마커 빌더 전용 로더
(:func:`load_user_trades` / :func:`load_signal_history`) 는 새 필드를 무시하고
기존 필드만 추출한다 (호환).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from live.constants import (
    HISTORY_BALANCE_ADJUSTS_FILENAME,
    HISTORY_DAILY_SUBDIR,
    HISTORY_FILL_DISMISSES_FILENAME,
    HISTORY_SIGNALS_FILENAME,
    HISTORY_SUMMARY_FILENAME,
    HISTORY_USER_TRADES_FILENAME,
)
from live.models import UserTrade

__all__ = [
    "save_daily_log",
    "append_summary",
    "append_user_trade",
    "append_signal_history",
    "append_balance_adjust",
    "append_fill_dismiss",
    "load_user_trades",
    "load_signal_history",
    "load_user_trades_raw",
    "load_balance_adjusts_raw",
    "load_signal_history_raw",
]


def _ensure_dir(path: Path) -> None:
    """부모 디렉토리 자동 생성."""
    path.parent.mkdir(parents=True, exist_ok=True)


def save_daily_log(date_iso: str, payload: dict[str, Any], history_dir: Path) -> Path:
    """일별 상세 로그를 ``history/daily/{date_iso}.json`` 으로 저장한다.

    같은 날짜로 두 번 호출되면 덮어쓴다 (일별 상세는 하루 1개 정본).

    Args:
        date_iso: ISO 8601 날짜 문자열 (예: "2026-04-10").
        payload: 저장할 dict.
        history_dir: ``qbt-live-state/history`` 경로.

    Returns:
        저장된 파일 경로.
    """
    target = history_dir / HISTORY_DAILY_SUBDIR / f"{date_iso}.json"
    _ensure_dir(target)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return target


def append_summary(summary: dict[str, Any], history_dir: Path) -> None:
    """일별 요약 1 줄을 ``history/summary.jsonl`` 에 append 한다.

    같은 날짜로 두 번 호출되어도 덮어쓰지 않고 줄을 추가한다.
    """
    target = history_dir / HISTORY_SUMMARY_FILENAME
    _ensure_dir(target)
    line = json.dumps(summary, ensure_ascii=False, default=str)
    with target.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def append_user_trade(trade: dict[str, Any], history_dir: Path) -> None:
    """사용자 체결 1 줄을 ``history/user_trades.jsonl`` 에 append 한다."""
    target = history_dir / HISTORY_USER_TRADES_FILENAME
    _ensure_dir(target)
    line = json.dumps(trade, ensure_ascii=False, default=str)
    with target.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def append_balance_adjust(adjust: dict[str, Any], history_dir: Path) -> None:
    """자산 보정 1 줄을 ``history/balance_adjusts.jsonl`` 에 audit 용 append 한다.

    차트 마커 대상이 아닌 audit / 디버깅 전용 로그.
    """
    target = history_dir / HISTORY_BALANCE_ADJUSTS_FILENAME
    _ensure_dir(target)
    line = json.dumps(adjust, ensure_ascii=False, default=str)
    with target.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def append_fill_dismiss(dismiss: dict[str, Any], history_dir: Path) -> None:
    """체결 스킵 1 줄을 ``history/fill_dismisses.jsonl`` 에 audit 용 append 한다."""
    target = history_dir / HISTORY_FILL_DISMISSES_FILENAME
    _ensure_dir(target)
    line = json.dumps(dismiss, ensure_ascii=False, default=str)
    with target.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def load_user_trades(history_dir: Path) -> dict[str, list[UserTrade]]:
    """``history/user_trades.jsonl`` 을 로드하여 자산 ID 별 ``UserTrade`` 목록 반환.

    파일이 존재하지 않으면 빈 dict 반환. 차트 빌더 (:func:`live.chart_data.build_chart_series`)
    가 사용자 체결 마커를 표시하기 위해 호출한다.

    JSONL 각 줄의 스키마: ``{"asset_id": str, "date": str, "direction": "buy"|"sell"}``.
    ``UserTrade`` dataclass 자체에는 ``asset_id`` 필드가 없으므로 dict 의 key 로 사용한다.

    Args:
        history_dir: ``qbt-live-state/history`` 경로.

    Returns:
        ``{asset_id: [UserTrade, ...]}`` — 각 자산에 대한 체결 이력.
    """
    target = history_dir / HISTORY_USER_TRADES_FILENAME
    result: dict[str, list[UserTrade]] = {}
    if not target.exists():
        return result

    content = target.read_text(encoding="utf-8").strip()
    if not content:
        return result

    for line_no, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"손상된 JSONL (user_trades, {line_no}행): {exc}") from exc
        asset_id = payload["asset_id"]
        trade = UserTrade(
            date=payload["date"],
            direction=payload["direction"],
        )
        result.setdefault(asset_id, []).append(trade)
    return result


def append_signal_history(entries: list[dict[str, Any]], history_dir: Path) -> None:
    """신호 이력 여러 줄을 ``history/signals.jsonl`` 에 append 한다.

    매 ``run-daily`` 실행마다 자산별 신호 상태 (``buy``/``sell``/``hold``) 를 기록.
    차트 빌더가 이 파일을 읽어 ``buy_signals`` / ``sell_signals`` 인덱스를 채운다.

    Args:
        entries: 각 원소는 ``{"date": "YYYY-MM-DD", "asset_id": str, "state": str}``
            형태의 dict.
        history_dir: ``qbt-live-state/history`` 경로.
    """
    if not entries:
        return
    target = history_dir / HISTORY_SIGNALS_FILENAME
    _ensure_dir(target)
    with target.open("a", encoding="utf-8") as fp:
        for entry in entries:
            line = json.dumps(entry, ensure_ascii=False, default=str)
            fp.write(line + "\n")


def load_signal_history(history_dir: Path) -> dict[str, list[tuple[str, str]]]:
    """``history/signals.jsonl`` 을 로드하여 자산 ID 별 ``(date, state)`` 튜플 목록 반환.

    파일이 존재하지 않으면 빈 dict 반환. 차트 빌더가 ``buy_signals`` / ``sell_signals``
    인덱스를 채우기 위해 호출한다.

    Args:
        history_dir: ``qbt-live-state/history`` 경로.

    Returns:
        ``{asset_id: [(date_iso, state), ...]}``.
    """
    target = history_dir / HISTORY_SIGNALS_FILENAME
    result: dict[str, list[tuple[str, str]]] = {}
    if not target.exists():
        return result

    content = target.read_text(encoding="utf-8").strip()
    if not content:
        return result

    for line_no, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"손상된 JSONL (signals, {line_no}행): {exc}") from exc
        asset_id = payload["asset_id"]
        result.setdefault(asset_id, []).append((payload["date"], payload["state"]))
    return result


def _load_jsonl_raw(target: Path, label: str) -> list[dict[str, Any]]:
    """JSONL 파일을 dict 리스트 그대로 로드한다 (필드 가공 없음).

    Args:
        target: 로드할 JSONL 파일 경로.
        label: 손상 시 에러 메시지에 포함할 식별자 (예: ``"user_trades"``).

    Returns:
        파일이 없거나 비어 있으면 빈 리스트. 그 외에는 각 줄을 ``json.loads`` 한
        dict 의 리스트.

    Raises:
        RuntimeError: JSONL 파싱 실패 시 (다른 raw 로더와 동일 패턴, 자동 복구 금지).
    """
    if not target.exists():
        return []

    content = target.read_text(encoding="utf-8").strip()
    if not content:
        return []

    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"손상된 JSONL ({label}, {line_no}행): {exc}") from exc
        rows.append(payload)
    return rows


def load_user_trades_raw(history_dir: Path) -> list[dict[str, Any]]:
    """``history/user_trades.jsonl`` 의 모든 줄을 dict 리스트로 반환.

    ``backfill-history`` CLI 가 RTDB ``/history/fills/`` 에 그대로 미러하기 위한
    원본 페이로드 로더. :func:`load_user_trades` 와 달리 가공 없이 모든 필드를
    보존한다.
    """
    return _load_jsonl_raw(history_dir / HISTORY_USER_TRADES_FILENAME, "user_trades")


def load_balance_adjusts_raw(history_dir: Path) -> list[dict[str, Any]]:
    """``history/balance_adjusts.jsonl`` 의 모든 줄을 dict 리스트로 반환.

    ``backfill-history`` CLI 가 RTDB ``/history/balance_adjusts/`` 에 미러하기
    위한 원본 페이로드 로더.
    """
    return _load_jsonl_raw(history_dir / HISTORY_BALANCE_ADJUSTS_FILENAME, "balance_adjusts")


def load_signal_history_raw(history_dir: Path) -> list[dict[str, Any]]:
    """``history/signals.jsonl`` 의 모든 줄을 dict 리스트로 반환.

    ``backfill-history`` CLI 가 RTDB ``/history/signals/`` 에 미러하기 위한 원본
    페이로드 로더.
    """
    return _load_jsonl_raw(history_dir / HISTORY_SIGNALS_FILENAME, "signals")
