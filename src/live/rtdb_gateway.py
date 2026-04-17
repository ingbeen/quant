"""Firebase Realtime Database 게이트웨이.

live 도메인이 RTDB 를 드나드는 모든 경로를 한 모듈에 캡슐화한다. 모든 RTDB 호출은
호출자가 :class:`firebase_admin.App` 인스턴스를 명시적으로 전달하는 방식으로 동작한다
(의존성 주입). 테스트에서는 mock App 으로 격리하고, 실제 환경에서는
:func:`initialize_firebase_app` 으로 초기화한다.

지원 경로:

- ``/latest/portfolio``, ``/latest/signals``, ``/latest/pending_orders``
- ``/charts/prices/{asset_id}/meta``
- ``/charts/prices/{asset_id}/recent``
- ``/charts/prices/{asset_id}/archive/{YYYY}``
- ``/charts/equity/meta``
- ``/charts/equity/recent``
- ``/charts/equity/archive/{YYYY}``
- ``/history/fills/{YYYY-MM-DD}/{uuid}``
- ``/history/balance_adjusts/{YYYY-MM-DD}/{uuid}``
- ``/history/signals/{YYYY-MM-DD}/{asset_id}``
- ``/fills/inbox/{uuid}``, ``/balance_adjust/inbox/{uuid}``, ``/fill_dismiss/inbox/{uuid}``
- ``/device_tokens/{device_id}``
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, cast

import firebase_admin
from firebase_admin import credentials, db

from live.models import (
    ActualFill,
    BalanceAdjust,
    ChartMeta,
    ChartSeries,
    DailyResult,
    EquityChartMeta,
    EquityChartSeries,
    FillDismiss,
    LiveState,
    SignalDetection,
)
from qbt.backtest.constants import ROUND_RATIO
from qbt.utils.logger import get_logger

logger = get_logger(__name__)

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
    "fetch_pending_fill_dismisses",
    "mark_fill_dismisses_processed",
    "write_read_model",
    "write_chart_meta",
    "write_chart_recent",
    "write_chart_archive_year",
    "write_equity_meta",
    "write_equity_recent",
    "write_equity_archive_year",
    "write_history_fills",
    "write_history_balance_adjusts",
    "write_history_signals",
    "write_history_fills_raw",
    "write_history_balance_adjusts_raw",
    "write_history_signals_raw",
    "read_device_tokens",
    "remove_invalid_tokens",
    "delete_all_except_device_tokens",
]

_LATEST_PATH = "/latest"
_CHARTS_PATH = "/charts"
_HISTORY_PATH = "/history"
_FILLS_INBOX_PATH = "/fills/inbox"
_BALANCE_ADJUST_INBOX_PATH = "/balance_adjust/inbox"
_FILL_DISMISS_INBOX_PATH = "/fill_dismiss/inbox"
_DEVICE_TOKENS_PATH = "/device_tokens"
_CHART_PRICES_PATH = "/charts/prices"
_CHART_EQUITY_PATH = "/charts/equity"
_HISTORY_FILLS_PATH = "/history/fills"
_HISTORY_BALANCE_ADJUSTS_PATH = "/history/balance_adjusts"
_HISTORY_SIGNALS_PATH = "/history/signals"


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
        ValueError: ``new_shares`` / ``new_avg_price`` / ``new_entry_date`` /
            ``new_cash`` 네 필드가 모두 없거나 모두 null 일 때 (빈 보정 레코드는
            무효).
    """
    new_shares_raw = data.get("new_shares")
    new_avg_price_raw = data.get("new_avg_price")
    new_entry_date_raw = data.get("new_entry_date")
    new_cash_raw = data.get("new_cash")

    # 빈 문자열 진입일은 None 취급 (UI 에서 미입력 시 빈 문자열이 들어올 수 있음)
    if isinstance(new_entry_date_raw, str) and new_entry_date_raw.strip() == "":
        new_entry_date_raw = None

    if new_shares_raw is None and new_avg_price_raw is None and new_entry_date_raw is None and new_cash_raw is None:
        raise ValueError(
            f"balance_adjust 에 유효한 new_shares / new_avg_price / new_entry_date / new_cash 값이 없음 "
            f"(rtdb_key={rtdb_key!r})"
        )
    return BalanceAdjust(
        rtdb_key=rtdb_key,
        input_time_kst=str(data.get("input_time_kst", "")),
        reason=str(data.get("reason", "")),
        asset_id=data.get("asset_id"),
        new_shares=int(new_shares_raw) if new_shares_raw is not None else None,
        new_avg_price=float(new_avg_price_raw) if new_avg_price_raw is not None else None,
        new_entry_date=str(new_entry_date_raw) if new_entry_date_raw is not None else None,
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
# fill_dismiss RTDB 경로
# ============================================================================


def _dict_to_fill_dismiss(data: dict[str, Any], rtdb_key: str) -> FillDismiss:
    """RTDB ``/fill_dismiss/inbox/{uuid}`` dict → :class:`FillDismiss`.

    Raises:
        ValueError: ``asset_id`` 가 없거나 null 일 때.
    """
    asset_id = data.get("asset_id")
    if asset_id is None:
        raise ValueError(f"fill_dismiss 에 asset_id 필수 (rtdb_key={rtdb_key!r})")
    return FillDismiss(
        rtdb_key=rtdb_key,
        input_time_kst=str(data.get("input_time_kst", "")),
        asset_id=str(asset_id),
        reason=str(data.get("reason", "")),
    )


def fetch_pending_fill_dismisses(app: FirebaseAppLike) -> list[FillDismiss]:
    """RTDB ``/fill_dismiss/inbox`` 에서 ``processed=false`` 인 항목만 가져온다.

    Args:
        app: ``firebase_admin.App`` 인스턴스 (mock 가능).

    Returns:
        :class:`FillDismiss` 리스트. queue 가 비어있거나 존재하지 않으면 빈 리스트.
    """
    ref = _db_reference(app, _FILL_DISMISS_INBOX_PATH)
    raw = ref.get() or {}

    if not isinstance(raw, dict):
        return []

    dismisses: list[FillDismiss] = []
    for rtdb_key, data in raw.items():
        if not isinstance(data, dict):
            continue
        if data.get("processed", False):
            continue
        dismisses.append(_dict_to_fill_dismiss(data, rtdb_key))
    return dismisses


def mark_fill_dismisses_processed(app: FirebaseAppLike, keys: list[str]) -> None:
    """주어진 fill_dismiss ID 들을 ``processed=true`` 로 마킹한다."""
    for key in keys:
        ref = _db_reference(app, f"{_FILL_DISMISS_INBOX_PATH}/{key}")
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
        # drift_pct 는 프로젝트 네이밍 관례(`_pct` = 0~1 ratio) 를 따라 RTDB 에도
        # 0~1 ratio 그대로 저장한다. 앱 표시 시 × 100 변환은 앱 계층 책임.
        "drift_pct": round(result.drift_pct, ROUND_RATIO),
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


def write_chart_meta(app: FirebaseAppLike, meta_map: dict[str, ChartMeta]) -> None:
    """``/charts/prices/{asset_id}/meta`` 에 자산별 차트 메타를 덮어쓴다.

    앱은 차트 진입 시 이 메타를 먼저 읽어 recent / archive 로딩 전략을 결정한다.
    """
    for asset_id, meta in meta_map.items():
        payload = asdict(meta)
        _db_reference(app, f"{_CHART_PRICES_PATH}/{asset_id}/meta").set(payload)


def write_chart_recent(app: FirebaseAppLike, recent_map: dict[str, ChartSeries]) -> None:
    """``/charts/prices/{asset_id}/recent`` 에 자산별 최근 슬라이스를 덮어쓴다.

    앱이 차트 초기 진입 시 가장 먼저 로드하는 구간이다.
    """
    for asset_id, chart_series in recent_map.items():
        payload = asdict(chart_series)
        _db_reference(app, f"{_CHART_PRICES_PATH}/{asset_id}/recent").set(payload)


def write_chart_archive_year(
    app: FirebaseAppLike,
    year: int,
    year_map: dict[str, ChartSeries],
) -> None:
    """``/charts/prices/{asset_id}/archive/{YYYY}`` 에 자산별 연도 슬라이스를 덮어쓴다.

    Args:
        app: Firebase App.
        year: 4 자리 연도 (예: 2026).
        year_map: 자산 ID → 해당 연도 슬라이스.
    """
    for asset_id, chart_series in year_map.items():
        payload = asdict(chart_series)
        _db_reference(app, f"{_CHART_PRICES_PATH}/{asset_id}/archive/{year}").set(payload)


# ============================================================================
# equity 차트 쓰기 (/charts/equity/)
# ============================================================================


def write_equity_meta(app: FirebaseAppLike, meta: EquityChartMeta) -> None:
    """``/charts/equity/meta`` 에 equity 차트 메타를 덮어쓴다.

    앱은 차트 진입 시 이 메타를 먼저 읽어 recent / archive 로딩 전략을 결정한다.
    주가 차트(:func:`write_chart_meta`) 와 달리 포트폴리오 전체를 대상으로 하므로
    자산 반복 없이 단일 payload 를 쓴다.
    """
    _db_reference(app, f"{_CHART_EQUITY_PATH}/meta").set(asdict(meta))


def write_equity_recent(app: FirebaseAppLike, series: EquityChartSeries) -> None:
    """``/charts/equity/recent`` 에 equity 최근 슬라이스를 덮어쓴다.

    매 ``run-daily`` 실행마다 전체 재생성된다.
    """
    _db_reference(app, f"{_CHART_EQUITY_PATH}/recent").set(asdict(series))


def write_equity_archive_year(app: FirebaseAppLike, year: int, series: EquityChartSeries) -> None:
    """``/charts/equity/archive/{YYYY}`` 에 equity 연도 슬라이스를 덮어쓴다.

    daily runner 는 현재 연도만 매일 재생성하며, 과거 연도는 backfill CLI 로만 재생성.
    """
    _db_reference(app, f"{_CHART_EQUITY_PATH}/archive/{year}").set(asdict(series))


# ============================================================================
# history 미러 쓰기 (/history/{fills|balance_adjusts|signals}/)
# ============================================================================
#
# Git 정본 (history/user_trades.jsonl, balance_adjusts.jsonl, signals.jsonl) 의
# RTDB 미러. daily runner 가 매 실행마다 이번 실행에서 새로 반영된 fill /
# balance_adjust 만 기록하고, signals 는 당일 4 자산을 덮어쓴다. 영구 보존이며
# rolling 정리 / cleanup 은 없다 (Firebase Spark 한도 대비 충분).
#
# idempotency: 모든 쓰기는 ``set`` (덮어쓰기). 동일 날짜/UUID/asset_id 재호출 시
# 자연 수렴. 빈 리스트 입력은 RTDB 호출 없이 즉시 반환 (no-op).


def write_history_fills(app: FirebaseAppLike, fills: list[ActualFill], applied_at: str) -> None:
    """``/history/fills/{trade_date}/{rtdb_key}`` 에 신규 fill 을 미러 기록한다.

    Args:
        app: Firebase App 인스턴스.
        fills: 이번 실행에서 새로 적용된 ``ActualFill`` 목록 (이미 적용된 것은 제외).
        applied_at: 이번 run-daily 배치의 단일 KST ISO 8601 타임스탬프.

    payload 는 :class:`ActualFill` 의 dataclass 필드에서 ``rtdb_key`` 를 제거하고
    ``applied_at`` 을 추가한 dict. 날짜 폴더 키는 fill 의 ``trade_date`` (사용자
    입력 체결 일자). 빈 리스트 입력 시 RTDB 호출 없이 즉시 반환.
    """
    if not fills:
        return
    for fill in fills:
        payload = asdict(fill)
        payload.pop("rtdb_key", None)
        payload["applied_at"] = applied_at
        _db_reference(
            app,
            f"{_HISTORY_FILLS_PATH}/{fill.trade_date}/{fill.rtdb_key}",
        ).set(payload)


def write_history_balance_adjusts(
    app: FirebaseAppLike,
    adjusts: list[BalanceAdjust],
    applied_at: str,
) -> None:
    """``/history/balance_adjusts/{applied_at_date}/{rtdb_key}`` 에 신규 adjust 를 미러 기록한다.

    Args:
        app: Firebase App 인스턴스.
        adjusts: 이번 실행에서 새로 반영된 ``BalanceAdjust`` 목록.
        applied_at: 이번 run-daily 배치의 단일 KST ISO 8601 타임스탬프.

    폴더 키는 ``applied_at`` 의 날짜 부분 (``YYYY-MM-DD`` 슬라이스) 로, fill 과 달리
    "교체 시점" 기준이다. payload 는 :class:`BalanceAdjust` dataclass 필드에서
    ``rtdb_key`` 를 제거하고 ``applied_at`` 을 추가한 dict. 빈 리스트 입력 시 no-op.
    """
    if not adjusts:
        return
    applied_at_date = applied_at[:10]
    for adjust in adjusts:
        payload = asdict(adjust)
        payload.pop("rtdb_key", None)
        payload["applied_at"] = applied_at
        _db_reference(
            app,
            f"{_HISTORY_BALANCE_ADJUSTS_PATH}/{applied_at_date}/{adjust.rtdb_key}",
        ).set(payload)


def write_history_signals(
    app: FirebaseAppLike,
    execution_date: str,
    signals: dict[str, SignalDetection],
) -> None:
    """``/history/signals/{execution_date}/{asset_id}`` 에 당일 시그널 전체를 덮어쓴다.

    Args:
        app: Firebase App 인스턴스.
        execution_date: 당일 실행 날짜 (ISO 8601, ``result.execution_date``).
        signals: 자산 ID → :class:`SignalDetection` 매핑. 보통 4 자산 전체.

    fill / balance_adjust 와 달리 UUID 가 없다. 서버 결정론적 계산이고 자산당 하루
    1 건이 보장되므로 asset_id 를 자연 키로 사용한다. 매일 4 자산 전체를 덮어쓰므로
    idempotent.
    """
    for asset_id, signal in signals.items():
        payload = asdict(signal)
        _db_reference(
            app,
            f"{_HISTORY_SIGNALS_PATH}/{execution_date}/{asset_id}",
        ).set(payload)


def write_history_fills_raw(app: FirebaseAppLike, rows: list[dict[str, Any]]) -> None:
    """``backfill-history`` CLI 가 Git 정본 dict 줄을 그대로 RTDB 에 일괄 미러한다.

    Args:
        app: Firebase App 인스턴스.
        rows: ``user_trades.jsonl`` raw dict 리스트. 각 dict 는 ``rtdb_key`` 와
            ``trade_date`` 를 반드시 포함해야 한다 (호출자 보장).

    각 row 의 폴더 키는 ``trade_date``, 레코드 키는 ``rtdb_key``. 페이로드는 row 에서
    ``rtdb_key`` 를 제거한 dict (필드 누락 시 그대로 ``null`` 기록). 빈 리스트 입력 시 no-op.
    """
    if not rows:
        return
    for row in rows:
        payload = {k: v for k, v in row.items() if k != "rtdb_key"}
        _db_reference(
            app,
            f"{_HISTORY_FILLS_PATH}/{row['trade_date']}/{row['rtdb_key']}",
        ).set(payload)


def write_history_balance_adjusts_raw(app: FirebaseAppLike, rows: list[dict[str, Any]]) -> None:
    """``backfill-history`` CLI 가 dict 줄을 그대로 RTDB 에 일괄 미러한다.

    각 row 의 폴더 키는 ``applied_at[:10]``, 레코드 키는 ``rtdb_key``. 호출자가
    두 필드를 보장해야 한다. 빈 리스트 입력 시 no-op.
    """
    if not rows:
        return
    for row in rows:
        payload = {k: v for k, v in row.items() if k != "rtdb_key"}
        applied_at_date = str(row["applied_at"])[:10]
        _db_reference(
            app,
            f"{_HISTORY_BALANCE_ADJUSTS_PATH}/{applied_at_date}/{row['rtdb_key']}",
        ).set(payload)


def write_history_signals_raw(app: FirebaseAppLike, rows: list[dict[str, Any]]) -> None:
    """``backfill-history`` CLI 가 dict 줄을 그대로 RTDB 에 일괄 미러한다.

    각 row 의 폴더 키는 ``date``, 레코드 키는 ``asset_id``. 호출자가 두 필드를
    보장해야 한다. 페이로드는 row 에서 두 키를 제거한 dict. 빈 리스트 입력 시 no-op.
    """
    if not rows:
        return
    for row in rows:
        payload = {k: v for k, v in row.items() if k not in ("date", "asset_id")}
        _db_reference(
            app,
            f"{_HISTORY_SIGNALS_PATH}/{row['date']}/{row['asset_id']}",
        ).set(payload)


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


def delete_all_except_device_tokens(app: FirebaseAppLike) -> None:
    """RTDB 의 모든 데이터를 삭제한다 (``/device_tokens`` 는 유지).

    전체 초기화(reset) 시 사용한다. ``/device_tokens`` 는 기기별 FCM 토큰으로
    앱 재실행 시 자동 재등록되므로 삭제 대상에서 제외한다.
    """
    paths_to_delete = [
        _LATEST_PATH,
        _CHARTS_PATH,
        _HISTORY_PATH,
        _FILLS_INBOX_PATH,
        _BALANCE_ADJUST_INBOX_PATH,
        _FILL_DISMISS_INBOX_PATH,
    ]
    for path in paths_to_delete:
        _db_reference(app, path).delete()
