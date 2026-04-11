"""영구 히스토리 저장 (qbt-live-state/history/).

설계서 10.1 "Git 정본" — 모든 히스토리 **영구 보존**. 자동 정리 없음.

3 종 파일:

- ``history/daily/{YYYY-MM-DD}.json`` — 일별 상세 로그 (덮어쓰기 가능)
- ``history/summary.jsonl`` — 일별 요약 (1 줄당 1 일, append-only)
- ``history/user_trades.jsonl`` — 사용자 체결 입력 누적 (append-only)

JSONL append 정책:

- 같은 날짜 / 같은 trade 가 두 번 호출되어도 **덮어쓰지 않고 줄을 추가**한다.
- 호출자가 idempotency 를 보장해야 한다 (Step 8 ``apply_fills_idempotent`` 참고).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = [
    "save_daily_log",
    "append_summary",
    "append_user_trade",
]

_DAILY_SUBDIR = "daily"
_SUMMARY_FILENAME = "summary.jsonl"
_USER_TRADES_FILENAME = "user_trades.jsonl"


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
    target = history_dir / _DAILY_SUBDIR / f"{date_iso}.json"
    _ensure_dir(target)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return target


def append_summary(summary: dict[str, Any], history_dir: Path) -> None:
    """일별 요약 1 줄을 ``history/summary.jsonl`` 에 append 한다.

    같은 날짜로 두 번 호출되어도 덮어쓰지 않고 줄을 추가한다 (T-15.4).
    """
    target = history_dir / _SUMMARY_FILENAME
    _ensure_dir(target)
    line = json.dumps(summary, ensure_ascii=False, default=str)
    with target.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")


def append_user_trade(trade: dict[str, Any], history_dir: Path) -> None:
    """사용자 체결 1 줄을 ``history/user_trades.jsonl`` 에 append 한다."""
    target = history_dir / _USER_TRADES_FILENAME
    _ensure_dir(target)
    line = json.dumps(trade, ensure_ascii=False, default=str)
    with target.open("a", encoding="utf-8") as fp:
        fp.write(line + "\n")
