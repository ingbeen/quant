"""LiveState JSON 직렬화/역직렬화 및 applied_fill_ids 관리.

``live_state.json`` 원장의 직렬화/역직렬화를 담당한다. 모든 I/O 는 ``pathlib.Path`` 기반이며
파일 저장은 ``temp → os.replace`` 패턴으로 원자적(atomic)으로 수행된다.

주요 함수:

- :func:`create_initial_state` — 초기 LiveState 생성 (QBT ``PORTFOLIO_CONFIGS`` SSoT 재사용)
- :func:`load_state`, :func:`save_state` — LiveState JSON 왕복
- :func:`load_applied_fill_ids`, :func:`save_applied_fill_ids` — idempotency 원장
- :func:`cleanup_old_fill_ids` — 90 일 초과 fill ID 정리

applied_fill_ids 포맷 (D1 결정):
    ``dict[str, str]`` — 키는 fill ID (``ActualFill.rtdb_key``), 값은 ISO 8601 KST
    타임스탬프. ``cleanup_old_fill_ids`` 가 타임스탬프를 기반으로 나이를 판단한다.

에러 처리:

- 파일 없음 → :exc:`FileNotFoundError` 전파 (호출자가 초기화 여부 결정)
- JSON 파싱 실패 → :exc:`ValueError` ("live_state.json 파싱 실패: ...")
- 필수 필드 누락 → :exc:`ValueError` ("live_state.json 필드 누락: ...")
- schema_version 불일치 → :exc:`ValueError`
- 입력 파라미터 오류 → :exc:`ValueError` (예: total_capital <= 0)
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from live.constants import (
    APPLIED_FILL_IDS_MAX_AGE_DAYS,
    KST_TZ_NAME,
    LIVE_PORTFOLIO_ID,
    SCHEMA_VERSION,
    get_live_portfolio_config,
)
from live.models import (
    AssetLiveState,
    BufferZoneState,
    HoldState,
    IntentTypeLiteral,
    LiveState,
    PendingOrderDict,
)

__all__ = [
    "create_initial_state",
    "load_state",
    "save_state",
    "load_applied_fill_ids",
    "save_applied_fill_ids",
    "load_applied_balance_adjust_ids",
    "save_applied_balance_adjust_ids",
    "cleanup_old_fill_ids",
]


# ============================================================================
# 내부 헬퍼 — 타임스탬프 및 파일 I/O
# ============================================================================

_KST = timezone(timedelta(hours=9))  # Asia/Seoul 고정 오프셋


def _now_kst_iso() -> str:
    """현재 시각을 KST ISO 8601 문자열로 반환한다.

    예: ``"2026-04-11T12:35:22+09:00"``
    """
    return datetime.now(_KST).replace(microsecond=0).isoformat()


def _atomic_write_text(path: Path, content: str) -> None:
    """파일을 원자적으로 저장한다.

    임시 파일에 쓴 뒤 ``os.replace`` 로 목적지에 교체한다. 저장 도중 프로세스가
    중단되어도 원본 파일이 손상되지 않는다. 부모 디렉토리는 필요 시 자동 생성.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{uuid.uuid4().hex}")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def _json_default(obj: Any) -> Any:
    """JSON encoder 의 fallback. ``date`` / ``datetime`` 을 ISO 문자열로 변환."""
    if isinstance(obj, date | datetime):
        return obj.isoformat()
    raise TypeError(f"JSON 직렬화 불가 타입: {type(obj).__name__}")


# ============================================================================
# 초기 상태 생성
# ============================================================================


def create_initial_state(total_capital: float) -> LiveState:
    """초기 LiveState 를 생성한다.

    QBT 코어 ``PORTFOLIO_CONFIGS[LIVE_PORTFOLIO_ID]`` 의 자산 슬롯을 기반으로 각
    자산을 0 포지션으로 초기화한다. model / actual 현금은 모두 ``total_capital`` 로
    동일하게 세팅된다.

    Args:
        total_capital: 초기 자본금 (원). 반드시 양수.

    Returns:
        초기 ``LiveState`` 인스턴스.

    Raises:
        ValueError: ``total_capital`` 이 0 이하일 때.
    """
    if total_capital <= 0:
        raise ValueError(f"total_capital 은 양수여야 한다. 입력: {total_capital}")

    config = get_live_portfolio_config()
    now = _now_kst_iso()

    assets: dict[str, AssetLiveState] = {}
    for slot in config.asset_slots:
        assets[slot.asset_id] = AssetLiveState(
            asset_id=slot.asset_id,
            model_shares=0,
            model_avg_entry_price=0.0,
            model_entry_date=None,
            actual_shares=0,
            actual_avg_entry_price=0.0,
            actual_entry_date=None,
            pending_order=None,
            signal_state="hold",
            entry_hold_days=0,
            buffer_zone_state=None,
        )

    return LiveState(
        schema_version=SCHEMA_VERSION,
        portfolio_id=LIVE_PORTFOLIO_ID,
        last_signal_date=None,
        last_model_execution_date=None,
        last_rebalance_date=None,
        shared_cash_model=float(total_capital),
        shared_cash_actual=float(total_capital),
        assets=assets,
        created_at=now,
        updated_at=now,
    )


# ============================================================================
# LiveState 저장 / 로드
# ============================================================================


def save_state(state: LiveState, path: Path) -> None:
    """LiveState 를 JSON 으로 저장한다 (atomic).

    Args:
        state: 저장할 ``LiveState``.
        path: 대상 경로 (파일명 포함).
    """
    data = asdict(state)
    content = json.dumps(data, indent=2, ensure_ascii=False, default=_json_default)
    _atomic_write_text(path, content)


def load_state(path: Path) -> LiveState:
    """JSON 파일에서 LiveState 를 복원한다.

    Args:
        path: JSON 파일 경로.

    Returns:
        ``LiveState`` 인스턴스.

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때.
        ValueError: JSON 파싱 실패 / 필수 필드 누락 / schema_version 불일치.
    """
    if not path.exists():
        raise FileNotFoundError(f"live_state.json 이 존재하지 않음: {path}")

    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"live_state.json 파싱 실패: {path} ({exc})") from exc

    if not isinstance(data, dict):
        raise ValueError(f"live_state.json 루트는 dict 이어야 함: {type(data).__name__}")

    return _live_state_from_dict(data)


# ============================================================================
# 역직렬화 헬퍼
# ============================================================================

_LIVE_STATE_REQUIRED_FIELDS = (
    "schema_version",
    "portfolio_id",
    "last_signal_date",
    "last_model_execution_date",
    "last_rebalance_date",
    "shared_cash_model",
    "shared_cash_actual",
    "assets",
    "created_at",
    "updated_at",
)

_ASSET_REQUIRED_FIELDS = (
    "asset_id",
    "model_shares",
    "model_avg_entry_price",
    "model_entry_date",
    "actual_shares",
    "actual_avg_entry_price",
    "actual_entry_date",
    "pending_order",
    "signal_state",
    "entry_hold_days",
    "buffer_zone_state",
)


def _live_state_from_dict(data: dict[str, Any]) -> LiveState:
    """dict → LiveState. 필수 필드 누락 및 schema_version 을 검증."""
    for field_name in _LIVE_STATE_REQUIRED_FIELDS:
        if field_name not in data:
            raise ValueError(f"live_state.json 필드 누락: {field_name}")

    schema_version = data["schema_version"]
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"live_state.json schema_version 불일치. 기대: {SCHEMA_VERSION}, 실제: {schema_version}")

    raw_assets = data["assets"]
    if not isinstance(raw_assets, dict):
        raise ValueError(f"live_state.json assets 는 dict 이어야 함: {type(raw_assets).__name__}")

    assets: dict[str, AssetLiveState] = {}
    for asset_id, asset_data in raw_assets.items():
        if not isinstance(asset_data, dict):
            raise ValueError(f"assets.{asset_id} 는 dict 이어야 함")
        assets[asset_id] = _asset_live_state_from_dict(asset_data)

    return LiveState(
        schema_version=int(schema_version),
        portfolio_id=str(data["portfolio_id"]),
        last_signal_date=data["last_signal_date"],
        last_model_execution_date=data["last_model_execution_date"],
        last_rebalance_date=data["last_rebalance_date"],
        shared_cash_model=float(data["shared_cash_model"]),
        shared_cash_actual=float(data["shared_cash_actual"]),
        assets=assets,
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
    )


def _asset_live_state_from_dict(data: dict[str, Any]) -> AssetLiveState:
    """dict → AssetLiveState."""
    for field_name in _ASSET_REQUIRED_FIELDS:
        if field_name not in data:
            raise ValueError(f"AssetLiveState 필드 누락: {field_name}")

    pending_raw = data["pending_order"]
    pending: PendingOrderDict | None = None if pending_raw is None else _pending_order_from_dict(pending_raw)

    bzs_raw = data["buffer_zone_state"]
    bzs: BufferZoneState | None = None if bzs_raw is None else _buffer_zone_state_from_dict(bzs_raw)

    return AssetLiveState(
        asset_id=str(data["asset_id"]),
        model_shares=int(data["model_shares"]),
        model_avg_entry_price=float(data["model_avg_entry_price"]),
        model_entry_date=data["model_entry_date"],
        actual_shares=int(data["actual_shares"]),
        actual_avg_entry_price=float(data["actual_avg_entry_price"]),
        actual_entry_date=data["actual_entry_date"],
        pending_order=pending,
        signal_state=str(data["signal_state"]),
        entry_hold_days=int(data["entry_hold_days"]),
        buffer_zone_state=bzs,
    )


_VALID_INTENT_TYPES: frozenset[str] = frozenset(
    ("EXIT_ALL", "ENTER_TO_TARGET", "REDUCE_TO_TARGET", "INCREASE_TO_TARGET")
)


def _pending_order_from_dict(data: dict[str, Any]) -> PendingOrderDict:
    """dict → PendingOrderDict. TypedDict 이므로 dict 를 그대로 반환하되 키 검증."""
    required = (
        "asset_id",
        "intent_type",
        "signal_date",
        "current_amount",
        "target_amount",
        "delta_amount",
        "target_weight",
        "hold_days_used",
        "reason",
    )
    for key in required:
        if key not in data:
            raise ValueError(f"PendingOrderDict 필드 누락: {key}")

    intent_type_raw = str(data["intent_type"])
    if intent_type_raw not in _VALID_INTENT_TYPES:
        raise ValueError(
            f"PendingOrderDict intent_type 값이 유효하지 않음: {intent_type_raw!r} " f"(허용: {sorted(_VALID_INTENT_TYPES)})"
        )
    intent_type: IntentTypeLiteral = cast("IntentTypeLiteral", intent_type_raw)

    pending: PendingOrderDict = {
        "asset_id": str(data["asset_id"]),
        "intent_type": intent_type,
        "signal_date": str(data["signal_date"]),
        "current_amount": float(data["current_amount"]),
        "target_amount": float(data["target_amount"]),
        "delta_amount": float(data["delta_amount"]),
        "target_weight": float(data["target_weight"]),
        "hold_days_used": int(data["hold_days_used"]),
        "reason": str(data["reason"]),
    }
    return pending


def _buffer_zone_state_from_dict(data: dict[str, Any]) -> BufferZoneState:
    """dict → BufferZoneState. hold_state 는 TypedDict 이므로 dict 로 복원."""
    required = (
        "prev_upper",
        "prev_lower",
        "hold_state",
        "last_buy_buffer_pct",
        "last_hold_days_used",
        "schema_version",
    )
    for key in required:
        if key not in data:
            raise ValueError(f"BufferZoneState 필드 누락: {key}")

    hold_state_raw = data["hold_state"]
    hold_state: HoldState | None
    if hold_state_raw is None:
        hold_state = None
    else:
        if not isinstance(hold_state_raw, dict):
            raise ValueError("BufferZoneState.hold_state 는 dict 또는 null 이어야 함")
        hold_state = {
            "start_date": hold_state_raw["start_date"],
            "days_passed": int(hold_state_raw["days_passed"]),
            "buffer_pct": float(hold_state_raw["buffer_pct"]),
            "hold_days_required": int(hold_state_raw["hold_days_required"]),
        }

    return BufferZoneState(
        prev_upper=None if data["prev_upper"] is None else float(data["prev_upper"]),
        prev_lower=None if data["prev_lower"] is None else float(data["prev_lower"]),
        hold_state=hold_state,
        last_buy_buffer_pct=float(data["last_buy_buffer_pct"]),
        last_hold_days_used=int(data["last_hold_days_used"]),
        schema_version=int(data["schema_version"]),
    )


# ============================================================================
# applied_fill_ids 관리
# ============================================================================


def _save_applied_ids(ids: dict[str, str], path: Path) -> None:
    """applied_*_ids 원장을 JSON 으로 저장하는 공용 구현 (atomic)."""
    content = json.dumps(ids, indent=2, ensure_ascii=False, sort_keys=True)
    _atomic_write_text(path, content)


def _load_applied_ids(path: Path, label: str) -> dict[str, str]:
    """applied_*_ids 원장을 로드하는 공용 구현. 존재하지 않으면 빈 dict."""
    if not path.exists():
        return {}

    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} 파싱 실패: {path} ({exc})") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{label} 루트는 dict 이어야 함: {type(data).__name__}")

    return {str(k): str(v) for k, v in data.items()}


def save_applied_fill_ids(ids: dict[str, str], path: Path) -> None:
    """applied_fill_ids 원장을 JSON 으로 저장한다 (atomic)."""
    _save_applied_ids(ids, path)


def load_applied_fill_ids(path: Path) -> dict[str, str]:
    """applied_fill_ids 를 로드한다. 파일이 없으면 빈 dict."""
    return _load_applied_ids(path, "applied_fill_ids.json")


def save_applied_balance_adjust_ids(ids: dict[str, str], path: Path) -> None:
    """applied_balance_adjust_ids 원장을 JSON 으로 저장한다 (atomic)."""
    _save_applied_ids(ids, path)


def load_applied_balance_adjust_ids(path: Path) -> dict[str, str]:
    """applied_balance_adjust_ids 를 로드한다. 파일이 없으면 빈 dict."""
    return _load_applied_ids(path, "applied_balance_adjust_ids.json")


def cleanup_old_fill_ids(ids: dict[str, str], max_age_days: int = APPLIED_FILL_IDS_MAX_AGE_DAYS) -> dict[str, str]:
    """지정 일수 이상 경과한 fill ID 를 제거한 새 dict 를 반환한다.

    현재 시각(KST) 기준으로 각 ID 의 타임스탬프와 비교하며, 파싱 불가능한
    타임스탬프를 가진 ID 는 보수적으로 유지한다 (datetime 포맷 이슈로 데이터를
    잃지 않도록).

    Args:
        ids: 현재 applied_fill_ids 매핑.
        max_age_days: 이 값 이상 경과한 ID 를 제거 (기본 ``APPLIED_FILL_IDS_MAX_AGE_DAYS``).

    Returns:
        정리된 새 dict (입력 ``ids`` 는 변경되지 않음).
    """
    if max_age_days <= 0:
        raise ValueError(f"max_age_days 는 양수여야 한다. 입력: {max_age_days}")

    now = datetime.now(_KST)
    cutoff = now - timedelta(days=max_age_days)
    result: dict[str, str] = {}
    for fill_id, iso_ts in ids.items():
        try:
            ts = datetime.fromisoformat(iso_ts)
        except ValueError:
            # 파싱 실패 시 보수적으로 유지
            result[fill_id] = iso_ts
            continue
        if ts >= cutoff:
            result[fill_id] = iso_ts
    return result


# 모듈 임포트 시점에서 사용하지 않는 심볼이 있더라도 명시적으로 export 목록에 포함한다.
_ = KST_TZ_NAME  # 향후 로깅/메시지에서 재사용 가능하도록 import 유지
