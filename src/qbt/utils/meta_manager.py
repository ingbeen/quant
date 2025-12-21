"""
실행 메타데이터 관리 모듈

CSV 결과 파일의 메타데이터를 JSON으로 관리하고,
최근 N개 이력을 순환 저장한다.
"""

import json
from datetime import datetime, timezone
from typing import Any, overload

from qbt.common_constants import MAX_HISTORY_COUNT, META_JSON_PATH

# 타입 정의
MetaDict = dict[str, Any]
HistoryList = list[MetaDict]
FullMetaJson = dict[str, HistoryList]

# 허용된 CSV 타입
VALID_CSV_TYPES = {"grid_results", "tqqq_validation", "tqqq_daily_comparison"}


def _load_full_metadata() -> FullMetaJson:
    """
    meta.json 전체를 로드한다.

    Returns:
        전체 메타데이터 dict (파일 없으면 빈 dict)
    """
    # 파일 없으면 빈 dict 반환
    if not META_JSON_PATH.exists():
        return {}

    # JSON 파싱
    with META_JSON_PATH.open("r", encoding="utf-8") as f:
        full_meta: FullMetaJson = json.load(f)

    return full_meta


def _rotate_history(history: HistoryList, new_entry: MetaDict) -> HistoryList:
    """
    이력 리스트에 새 항목을 추가하고 최대 개수를 유지한다.

    Args:
        history: 기존 이력 리스트
        new_entry: 새로 추가할 항목

    Returns:
        업데이트된 이력 (최대 MAX_HISTORY_COUNT개, 최신순 정렬)
    """
    # 맨 앞에 새 항목 추가
    updated = [new_entry] + history

    # 최대 개수만 유지
    return updated[:MAX_HISTORY_COUNT]


def _add_timestamp(metadata: MetaDict) -> MetaDict:
    """
    메타데이터에 ISO 8601 타임스탬프를 추가한다.

    Args:
        metadata: 원본 메타데이터

    Returns:
        타임스탬프가 추가된 메타데이터 (원본 변경 없음)
    """
    # 원본 변경 방지 (복사)
    result = metadata.copy()

    # KST 타임스탬프 추가
    now = datetime.now(timezone.utc).astimezone()
    result["timestamp"] = now.isoformat(timespec="seconds")

    return result


def save_metadata(csv_type: str, metadata: MetaDict) -> None:
    """
    메타데이터를 meta.json에 저장한다.

    최근 N개 이력만 유지하는 순환 저장 방식을 사용한다.
    타임스탬프는 자동으로 추가된다.

    Args:
        csv_type: CSV 타입 ("grid_results", "tqqq_validation", "tqqq_daily_comparison")
        metadata: 저장할 메타데이터 (타임스탬프 자동 추가)

    Raises:
        ValueError: csv_type이 유효하지 않은 경우
    """
    # 1. csv_type 검증
    if csv_type not in VALID_CSV_TYPES:
        raise ValueError(
            f"유효하지 않은 csv_type: {csv_type}. " f"허용된 값: {VALID_CSV_TYPES}"
        )

    # 2. 기존 meta.json 로드
    full_meta = _load_full_metadata()

    # 3. 타임스탬프 추가
    metadata_with_ts = _add_timestamp(metadata)

    # 4. 해당 타입의 이력 가져오기
    history: HistoryList = full_meta.get(csv_type, [])

    # 5. 최근 N개만 유지
    updated_history = _rotate_history(history, metadata_with_ts)

    # 6. 전체 dict 업데이트
    full_meta[csv_type] = updated_history

    # 7. meta.json 저장
    META_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with META_JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(full_meta, f, indent=2, ensure_ascii=False)


@overload
def load_metadata(csv_type: None = None) -> FullMetaJson: ...


@overload
def load_metadata(csv_type: str) -> HistoryList: ...


def load_metadata(csv_type: str | None = None) -> FullMetaJson | HistoryList:
    """
    meta.json에서 메타데이터를 읽어온다.

    Args:
        csv_type: 특정 CSV 타입만 조회 (None이면 전체 반환)

    Returns:
        csv_type이 None이면 전체 dict, 아니면 해당 타입의 이력 list
    """
    full_meta = _load_full_metadata()

    # csv_type 지정 시 해당 키만 반환
    if csv_type is not None:
        return full_meta.get(csv_type, [])

    return full_meta
