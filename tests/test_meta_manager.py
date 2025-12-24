"""
meta_manager 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 실행 메타데이터가 올바르게 저장되는가?
2. 타임스탬프가 정확히 기록되는가? (결정적 테스트)
3. MAX_HISTORY_COUNT를 초과하면 오래된 항목이 제거되는가?
4. 잘못된 csv_type을 거부하는가?

왜 중요한가요?
백테스트나 시뮬레이션의 실행 이력을 추적하면:
- 재현성: 같은 파라미터로 다시 실행 가능
- 디버깅: 어떤 설정으로 결과가 나왔는지 추적
- 변경 감지: 데이터나 코드 변경 시 영향 파악
"""

import json

import pytest
from freezegun import freeze_time

from qbt.common_constants import MAX_HISTORY_COUNT
from qbt.utils.meta_manager import save_metadata


class TestSaveMetadata:
    """메타데이터 저장 테스트 클래스"""

    @freeze_time("2023-06-15 14:30:00")
    def test_create_new_meta_file(self, mock_storage_paths):
        """
        meta.json 파일 새로 생성 테스트

        결정적 테스트: freezegun으로 시간을 고정하여 항상 같은 결과를 보장합니다.
        안정성: 파일이 없어도 자동 생성되어야 합니다.

        Given: meta.json 파일이 존재하지 않음 + 시간 고정
        When: save_metadata 호출
        Then:
          - meta.json 파일 생성됨
          - 타임스탬프가 고정된 시간으로 기록됨
          - metadata 내용이 정확히 저장됨
        """
        # Given: mock_storage_paths 픽스처로 이미 tmp_path 설정됨
        meta_path = mock_storage_paths["META_JSON_PATH"]
        assert not meta_path.exists(), "초기 상태에서는 meta.json이 없어야 합니다"

        csv_type = "grid_results"
        metadata = {"ticker": "AAPL", "start_date": "2020-01-01", "end_date": "2023-12-31", "total_combinations": 100}

        # When: 메타데이터 저장 (시간은 2023-06-15 14:30:00로 고정됨)
        save_metadata(csv_type, metadata)

        # Then: 파일 생성 확인
        assert meta_path.exists(), "meta.json 파일이 생성되어야 합니다"

        # 내용 검증
        with open(meta_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert csv_type in saved_data, f"'{csv_type}' 키가 있어야 합니다"
        assert len(saved_data[csv_type]) == 1, "첫 실행이므로 1개 항목만 있어야 합니다"

        entry = saved_data[csv_type][0]
        # 타임스탬프는 ISO 8601 형식 (예: "2023-06-15T14:30:00+09:00")
        # 타임존 변환 때문에 시간은 달라질 수 있으므로 날짜만 검증
        assert "2023-06-15" in entry["timestamp"], "freezegun으로 고정한 날짜가 포함되어야 합니다"
        assert entry["ticker"] == "AAPL"
        assert entry["total_combinations"] == 100

    @freeze_time("2023-07-01 10:00:00")
    def test_append_to_existing_meta(self, mock_storage_paths):
        """
        기존 meta.json에 추가 저장 테스트

        안정성: 기존 데이터를 보존하면서 새 항목을 추가해야 합니다.

        Given: meta.json에 이미 1개 항목 존재
        When: 같은 csv_type으로 다시 저장
        Then: 2개 항목으로 증가
        """
        # Given: 기존 데이터 생성
        meta_path = mock_storage_paths["META_JSON_PATH"]
        existing_data = {
            "grid_results": [{"timestamp": "2023-06-01 09:00:00", "ticker": "TSLA", "total_combinations": 50}]
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f)

        # When: 새 항목 추가
        new_metadata = {"ticker": "NVDA", "total_combinations": 75}
        save_metadata("grid_results", new_metadata)

        # Then: 2개 항목 확인
        with open(meta_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert len(saved_data["grid_results"]) == 2, "기존 1개 + 새로 추가 1개 = 2개"

        # 최신 항목 검증 (prepend 방식: 최신이 맨 앞)
        latest = saved_data["grid_results"][0]
        assert "2023-07-01" in latest["timestamp"], "최신 항목 날짜 확인"
        # 타임존 변환으로 시간이 달라질 수 있으므로 날짜만 검증
        assert latest["ticker"] == "NVDA"

        # 기존 항목 보존 확인 (뒤로 밀림)
        old = saved_data["grid_results"][1]
        assert old["ticker"] == "TSLA"

    @freeze_time("2023-08-01 12:00:00")
    def test_history_limit_enforcement(self, mock_storage_paths):
        """
        MAX_HISTORY_COUNT 초과 시 오래된 항목 제거 테스트

        안정성: 무한정 커지는 파일을 방지하여 성능과 관리성을 유지합니다.

        Given: 이미 MAX_HISTORY_COUNT개 항목 존재
        When: 1개 더 추가
        Then:
          - 가장 오래된 항목 제거됨
          - 전체 개수는 MAX_HISTORY_COUNT 유지
        """
        # Given: MAX_HISTORY_COUNT개 항목 생성 (현재 상수 값 확인 필요)
        meta_path = mock_storage_paths["META_JSON_PATH"]

        # 오래된 항목들 생성 (timestamp 오름차순)
        old_entries = [
            {"timestamp": f"2023-0{i+1}-01 10:00:00", "ticker": f"TICKER_{i}", "note": "old"}
            for i in range(MAX_HISTORY_COUNT)
        ]
        existing_data = {"grid_results": old_entries}
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f)

        # When: 새 항목 추가 (MAX_HISTORY_COUNT + 1번째)
        new_metadata = {"ticker": "NEW_TICKER", "note": "new"}
        save_metadata("grid_results", new_metadata)

        # Then: 여전히 MAX_HISTORY_COUNT개만 유지
        with open(meta_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        entries = saved_data["grid_results"]
        assert len(entries) == MAX_HISTORY_COUNT, f"최대 {MAX_HISTORY_COUNT}개만 유지해야 합니다"

        # prepend 방식: 최신(NEW_TICKER)이 맨 앞, 가장 오래된 것(마지막)이 잘림
        assert entries[0]["ticker"] == "NEW_TICKER", "최신 항목은 맨 앞"
        assert "2023-08-01" in entries[0]["timestamp"]

        # 가장 오래된 항목(TICKER_4, 마지막)이 제거되었는지 확인
        # MAX_HISTORY_COUNT=5이므로 TICKER_0~4가 있었고, 새로 추가되면 TICKER_4가 제거됨
        tickers = [e["ticker"] for e in entries]
        assert f"TICKER_{MAX_HISTORY_COUNT-1}" not in tickers, "가장 오래된 항목(마지막)은 제거되어야 합니다"

    def test_invalid_csv_type(self, mock_storage_paths):
        """
        잘못된 csv_type 거부 테스트

        안정성: 정의되지 않은 타입은 즉시 실패해야 오타나 버그를 조기에 발견합니다.

        Given: 유효하지 않은 csv_type
        When: save_metadata 호출
        Then: ValueError 발생
        """
        # Given
        invalid_type = "invalid_type_123"
        metadata = {"test": "data"}

        # When & Then
        with pytest.raises(ValueError) as exc_info:
            save_metadata(invalid_type, metadata)

        error_msg = str(exc_info.value)
        assert "유효하지 않은" in error_msg or "invalid" in error_msg.lower(), "csv_type이 잘못되었음을 명확히 알려야 합니다"

    @freeze_time("2023-09-01 08:00:00")
    def test_multiple_csv_types(self, mock_storage_paths):
        """
        여러 csv_type을 독립적으로 관리하는지 테스트

        안정성: grid_results와 tqqq_validation은 별도로 이력 관리되어야 합니다.

        Given: 빈 meta.json
        When: 서로 다른 csv_type으로 각각 저장
        Then: 각 타입별로 독립적인 리스트 생성
        """
        # When: 두 가지 타입 저장
        save_metadata("grid_results", {"test": "grid"})
        save_metadata("tqqq_validation", {"test": "tqqq"})

        # Then: 독립적인 키 확인
        meta_path = mock_storage_paths["META_JSON_PATH"]
        with open(meta_path, encoding="utf-8") as f:
            saved_data = json.load(f)

        assert "grid_results" in saved_data
        assert "tqqq_validation" in saved_data
        assert len(saved_data["grid_results"]) == 1
        assert len(saved_data["tqqq_validation"]) == 1

        # 내용 확인
        assert saved_data["grid_results"][0]["test"] == "grid"
        assert saved_data["tqqq_validation"][0]["test"] == "tqqq"
