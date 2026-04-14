"""Firebase Realtime Database 게이트웨이.

live 도메인이 RTDB 를 드나드는 모든 경로를 한 모듈에 캡슐화한다. 모든 RTDB 호출은
호출자가 :class:`firebase_admin.App` 인스턴스를 명시적으로 전달하는 방식으로 동작한다
(의존성 주입). 테스트에서는 mock App 으로 격리하고, 실제 환경에서는
:func:`initialize_firebase_app` 으로 초기화한다.

지원 경로:

- ``/latest/portfolio``, ``/latest/signals``, ``/latest/pending_orders``
- ``/latest/chart_data/{asset_id}``
- ``/history/summary/`` (rolling window — :func:`prune_history_summary`)
- ``/fills/inbox/{uuid}``, ``/balance_adjust/inbox/{uuid}``
- ``/device_tokens/{device_id}``
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import firebase_admin
from firebase_admin import credentials, db

from live.models import ActualFill, BalanceAdjust, ChartSeries, DailyResult, LiveState
from qbt.backtest.constants import ROUND_PERCENT

# Firebase Admin SDK 의 ``App`` 객체는 테스트에서 mock 으로 주입되는 경우가 많아
# 정적 타입을 ``Any`` 로 유지한다. 런타임에는 :func:`initialize_firebase_app` 가
# 실제 ``firebase_admin.App`` 을 반환한다.
type FirebaseAppLike = Any

__all__ = [
    "initialize_firebase_app",
    "fetch_unprocessed_fills",
    "mark_fills_processed",
    "fetch_pending_balance_adjusts",
    "mark_balance_adjusts_processed",
    "write_read_model",
    "write_chart_data",
    "prune_history_summary",
    "read_device_tokens",
    "remove_invalid_tokens",
]

_LATEST_PATH = "/latest"
_FILLS_INBOX_PATH = "/fills/inbox"
_BALANCE_ADJUST_INBOX_PATH = "/balance_adjust/inbox"
_DEVICE_TOKENS_PATH = "/device_tokens"
_HISTORY_SUMMARY_PATH = "/history/summary"
_CHART_DATA_PATH = "/latest/chart_data"


def initialize_firebase_app(credentials_path: Path, db_url: str) -> FirebaseAppLike:
    """Firebase Admin SDK 를 초기화한다.

    Args:
        credentials_path: 서비스 계정 JSON 경로.
        db_url: RTDB URL (예: ``https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app``).

    Returns:
        ``firebase_admin.App`` 인스턴스.
    """
    cred = credentials.Certificate(str(credentials_path))
    return firebase_admin.initialize_app(cred, {"databaseURL": db_url})


def _db_reference(app: FirebaseAppLike, path: str) -> Any:
    """``firebase_admin.db.reference`` 얇은 래퍼."""
    return db.reference(path, app=app)


# ============================================================================
# fills (앱 → daily runner)
# ============================================================================


_FILL_REQUIRED_FIELDS = ("asset_id", "direction", "actual_price", "actual_shares", "trade_date", "input_time_kst")


_VALID_FILL_DIRECTIONS = frozenset({"buy", "sell"})


def _dict_to_actual_fill(data: dict[str, Any], rtdb_key: str) -> ActualFill:
    """RTDB ``/fills/inbox/{uuid}`` 의 dict 를 :class:`ActualFill` 로 변환.

    Raises:
        ValueError: 필수 필드 누락 또는 direction 값이 유효하지 않을 때.
    """
    missing = [f for f in _FILL_REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(f"fill 필수 필드 누락: {missing} (rtdb_key={rtdb_key!r})")

    direction_raw = str(data["direction"])
    if direction_raw not in _VALID_FILL_DIRECTIONS:
        raise ValueError(
            f"fill direction 값이 유효하지 않음: {direction_raw!r} "
            f"(허용: {sorted(_VALID_FILL_DIRECTIONS)}, rtdb_key={rtdb_key!r})"
        )

    return ActualFill(
        asset_id=str(data["asset_id"]),
        direction=cast(Literal["buy", "sell"], direction_raw),
        actual_price=float(data["actual_price"]),
        actual_shares=int(data["actual_shares"]),
        trade_date=str(data["trade_date"]),
        input_time_kst=str(data["input_time_kst"]),
        memo=data.get("memo"),
        rtdb_key=rtdb_key,
        reason=str(data.get("reason", "")),
    )


def fetch_unprocessed_fills(app: FirebaseAppLike) -> list[ActualFill]:
    """RTDB ``/fills/inbox`` 에서 ``processed=false`` 인 fill 만 가져온다.

    Args:
        app: ``firebase_admin.App`` 인스턴스 (mock 가능).

    Returns:
        ActualFill 리스트.
    """
    ref = _db_reference(app, _FILLS_INBOX_PATH)
    raw = ref.get() or {}

    if not isinstance(raw, dict):
        return []

    fills: list[ActualFill] = []
    for rtdb_key, data in raw.items():
        if not isinstance(data, dict):
            continue
        if data.get("processed", False):
            continue
        fills.append(_dict_to_actual_fill(data, rtdb_key))
    return fills


def mark_fills_processed(app: FirebaseAppLike, keys: list[str]) -> None:
    """주어진 fill ID 들을 ``processed=true`` 로 마킹한다.

    Args:
        app: ``firebase_admin.App`` 인스턴스.
        keys: ``/fills/inbox/`` 하위의 RTDB 키 목록.
    """
    for key in keys:
        ref = _db_reference(app, f"{_FILLS_INBOX_PATH}/{key}")
        ref.update({"processed": True})


# ============================================================================
# balance_adjust (앱 → daily runner) — 자산 직접 보정
# ============================================================================


def _dict_to_balance_adjust(data: dict[str, Any], rtdb_key: str) -> BalanceAdjust:
    """RTDB ``/balance_adjust/inbox/{uuid}`` dict → :class:`BalanceAdjust`.

    Raises:
        ValueError: ``new_shares`` 와 ``new_cash`` 값이 둘 다 없거나 둘 다 null 일 때.
    """
    new_shares_raw = data.get("new_shares")
    new_cash_raw = data.get("new_cash")
    if new_shares_raw is None and new_cash_raw is None:
        raise ValueError(f"balance_adjust 에 유효한 new_shares / new_cash 값이 없음 (rtdb_key={rtdb_key!r})")
    return BalanceAdjust(
        rtdb_key=rtdb_key,
        input_time_kst=str(data.get("input_time_kst", "")),
        reason=str(data.get("reason", "")),
        asset_id=data.get("asset_id"),
        new_shares=int(new_shares_raw) if new_shares_raw is not None else None,
        new_cash=float(new_cash_raw) if new_cash_raw is not None else None,
    )


def fetch_pending_balance_adjusts(app: FirebaseAppLike) -> list[BalanceAdjust]:
    """RTDB ``/balance_adjust/inbox`` 에서 ``processed=false`` 인 항목만 가져온다.

    자산 직접 수정 경로: 앱이 queue 에 쓰고 daily runner 가 읽어 처리한다.

    Args:
        app: ``firebase_admin.App`` 인스턴스 (mock 가능).

    Returns:
        :class:`BalanceAdjust` 리스트. queue 가 비어있거나 존재하지 않으면 빈 리스트.
    """
    ref = _db_reference(app, _BALANCE_ADJUST_INBOX_PATH)
    raw = ref.get() or {}

    if not isinstance(raw, dict):
        return []

    adjusts: list[BalanceAdjust] = []
    for rtdb_key, data in raw.items():
        if not isinstance(data, dict):
            continue
        if data.get("processed", False):
            continue
        adjusts.append(_dict_to_balance_adjust(data, rtdb_key))
    return adjusts


def mark_balance_adjusts_processed(app: FirebaseAppLike, keys: list[str]) -> None:
    """주어진 balance_adjust ID 들을 ``processed=true`` 로 마킹한다."""
    for key in keys:
        ref = _db_reference(app, f"{_BALANCE_ADJUST_INBOX_PATH}/{key}")
        ref.update({"processed": True})


# ============================================================================
# read model (daily runner → 앱)
# ============================================================================


def write_read_model(app: FirebaseAppLike, state: LiveState, result: DailyResult) -> None:
    """``/latest/*`` 에 read model (포트폴리오 / 시그널 / pending) 을 기록한다.

    drift 스칼라 값 (``drift_pct`` / ``model_equity`` / ``actual_equity``) 은
    ``/latest/portfolio`` 에 포함되어 있으므로 별도 ``/latest/drift`` 경로는
    사용하지 않는다.

    Args:
        app: Firebase App 인스턴스.
        state: 현재 LiveState (실행 후 상태).
        result: 당일 DailyResult.
    """
    portfolio_payload = {
        "execution_date": result.execution_date,
        "model_equity": result.model_equity,
        "actual_equity": result.actual_equity,
        "drift_pct": round(result.drift_pct * 100, ROUND_PERCENT),
        "shared_cash_model": state.shared_cash_model,
        "shared_cash_actual": state.shared_cash_actual,
        "assets": {
            aid: {
                "model_shares": asset.model_shares,
                "actual_shares": asset.actual_shares,
                "signal_state": asset.signal_state,
            }
            for aid, asset in state.assets.items()
        },
    }
    _db_reference(app, f"{_LATEST_PATH}/portfolio").set(portfolio_payload)

    signals_payload = {
        aid: {
            "state": sig.state,
            "close": sig.close,
            "ma_value": sig.ma_value,
            "ma_distance_pct": sig.ma_distance_pct,
            "upper_band": sig.upper_band,
            "lower_band": sig.lower_band,
        }
        for aid, sig in result.signals.items()
    }
    _db_reference(app, f"{_LATEST_PATH}/signals").set(signals_payload)

    pending_payload = {
        aid: dict(asset.pending_order) for aid, asset in state.assets.items() if asset.pending_order is not None
    }
    _db_reference(app, f"{_LATEST_PATH}/pending_orders").set(pending_payload)

    # 일일 요약은 history/summary 에도 누적 (rolling window 는 prune_history_summary 로 정리)
    _db_reference(app, f"{_HISTORY_SUMMARY_PATH}/{result.execution_date}").set(
        {
            "execution_date": result.execution_date,
            "model_equity": result.model_equity,
            "actual_equity": result.actual_equity,
            "drift_pct": round(result.drift_pct * 100, ROUND_PERCENT),
        }
    )


def prune_history_summary(app: FirebaseAppLike, retention_days: int, today: date) -> None:
    """``/history/summary/{YYYY-MM-DD}`` 에서 retention 초과 키를 삭제한다.

    RTDB 쪽 history summary 는 앱 홈 탭의 rolling cache 이며, 전체 정본은
    Git ``history/summary.jsonl`` 이다. 이 함수는 ``today - retention_days``
    **미만** 인 날짜 키를 삭제하여 용량 누수를 방지한다.

    Args:
        app: Firebase App 인스턴스.
        retention_days: 유지할 최대 일수 (이 일수를 초과한 과거 키는 삭제).
        today: 기준 날짜. daily runner 의 ``execution_date`` 를 그대로 전달하여
            backfill / historical 재실행 시에도 retention 창이 그 날짜 기준으로
            움직이게 한다.

    동작:

    - ``/history/summary`` 가 없거나 dict 가 아니면 no-op.
    - 날짜 포맷이 ISO 8601 이 아닌 키는 건너뛴다 (파손 키 보호).
    - retention 경계일 자체도 삭제 대상이다 (미만 기준: cutoff = today - retention_days,
      `date_key < cutoff` 이면 삭제).
    """
    ref = _db_reference(app, _HISTORY_SUMMARY_PATH)
    raw = ref.get()
    if not isinstance(raw, dict):
        return

    cutoff = today - timedelta(days=retention_days)
    for date_key in list(raw.keys()):
        try:
            entry_date = date.fromisoformat(str(date_key))
        except ValueError:
            continue
        if entry_date < cutoff:
            _db_reference(app, f"{_HISTORY_SUMMARY_PATH}/{date_key}").delete()


def write_chart_data(app: FirebaseAppLike, series: dict[str, ChartSeries]) -> None:
    """``/latest/chart_data/{asset_id}`` 에 자산별 시계열 덮어쓰기."""
    for asset_id, chart_series in series.items():
        payload = asdict(chart_series)
        _db_reference(app, f"{_CHART_DATA_PATH}/{asset_id}").set(payload)


# ============================================================================
# device tokens (FCM)
# ============================================================================


def read_device_tokens(app: FirebaseAppLike) -> list[str]:
    """RTDB ``/device_tokens`` 에서 등록된 FCM 토큰 리스트 반환."""
    ref = _db_reference(app, _DEVICE_TOKENS_PATH)
    raw = ref.get() or {}

    if not isinstance(raw, dict):
        return []

    tokens: list[str] = []
    for value in raw.values():
        if isinstance(value, str):
            tokens.append(value)
        elif isinstance(value, dict) and "token" in value:
            tokens.append(str(value["token"]))
    return tokens


def remove_invalid_tokens(app: FirebaseAppLike, tokens: list[str]) -> None:
    """유효하지 않은(만료/등록 해제된) FCM 토큰을 RTDB 에서 삭제한다.

    매칭 방식: ``/device_tokens`` 하위의 모든 항목을 순회하여 값 또는 ``token`` 필드가
    ``tokens`` 에 포함되면 해당 device_id 를 삭제.
    """
    if not tokens:
        return

    invalid_set = set(tokens)
    ref = _db_reference(app, _DEVICE_TOKENS_PATH)
    raw = ref.get() or {}
    if not isinstance(raw, dict):
        return

    for device_id, value in raw.items():
        token: str | None = None
        if isinstance(value, str):
            token = value
        elif isinstance(value, dict):
            token = str(value.get("token", ""))
        if token and token in invalid_set:
            _db_reference(app, f"{_DEVICE_TOKENS_PATH}/{device_id}").delete()
