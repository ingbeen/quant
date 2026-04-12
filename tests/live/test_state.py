"""live.state — LiveState JSON 왕복 / applied_*_ids 원장 / 에러 매트릭스 테스트.

원칙:
- 파일 I/O 격리: tmp_path 사용
- 시간 고정: freezegun @freeze_time 사용
- 부동소수점: pytest.approx
- Given-When-Then 패턴
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from freezegun import freeze_time

from live import state as state_module
from live.constants import LIVE_PORTFOLIO_ID, SCHEMA_VERSION
from live.models import (
    AssetLiveState,
    BufferZoneState,
    HoldState,
    LiveState,
    PendingOrderDict,
)
from live.state import (
    cleanup_old_applied_ids,
    create_initial_state,
    load_applied_fill_ids,
    load_state,
    save_applied_fill_ids,
    save_state,
)

# ============================================================================
# create_initial_state
# ============================================================================


class TestCreateInitialState:
    def test_basic_fields(self):
        """Given: 자본금 1 억. When: 초기 상태 생성. Then: 필수 메타 필드 세팅."""
        # Given / When
        state = create_initial_state(100_000_000.0)

        # Then
        assert state.schema_version == SCHEMA_VERSION
        assert state.portfolio_id == LIVE_PORTFOLIO_ID
        assert state.last_signal_date is None
        assert state.last_model_execution_date is None
        assert state.last_rebalance_date is None
        assert state.created_at != ""
        assert state.updated_at != ""

    def test_uses_live_portfolio_asset_slots(self):
        """live 포트폴리오의 asset_id 가 그대로 반영되어야 한다."""
        state = create_initial_state(100_000_000.0)
        expected_asset_ids = {"sso", "qld", "gld", "tlt"}
        assert set(state.assets.keys()) == expected_asset_ids

    def test_shared_cash_equal_to_capital(self):
        """초기 model/actual 현금은 total_capital 과 동일."""
        state = create_initial_state(50_000_000.0)
        assert state.shared_cash_model == pytest.approx(50_000_000.0)
        assert state.shared_cash_actual == pytest.approx(50_000_000.0)

    def test_all_positions_are_zero(self):
        """초기 상태의 모든 자산은 model/actual 모두 0 포지션."""
        state = create_initial_state(100_000_000.0)
        for asset in state.assets.values():
            assert asset.model_shares == 0
            assert asset.model_avg_entry_price == pytest.approx(0.0)
            assert asset.model_entry_date is None
            assert asset.actual_shares == 0
            assert asset.actual_avg_entry_price == pytest.approx(0.0)
            assert asset.actual_entry_date is None
            assert asset.pending_order is None
            assert asset.signal_state == "sell"
            assert asset.entry_hold_days == 0
            assert asset.buffer_zone_state is None

    def test_portfolio_id_matches_constant(self):
        """portfolio_id 는 LIVE_PORTFOLIO_ID 상수와 일치."""
        state = create_initial_state(100_000_000.0)
        assert state.portfolio_id == LIVE_PORTFOLIO_ID

    def test_zero_capital_raises(self):
        """총 자본금 0 은 ValueError."""
        with pytest.raises(ValueError, match="total_capital"):
            create_initial_state(0.0)

    def test_negative_capital_raises(self):
        """음수 자본금은 ValueError."""
        with pytest.raises(ValueError, match="total_capital"):
            create_initial_state(-100.0)


# ============================================================================
# save_state / load_state 왕복
# ============================================================================


class TestSaveLoadRoundtrip:
    def test_preserves_all_fields(self, tmp_path: Path):
        """Given: create_initial_state → save → load. Then: 원본과 일치."""
        # Given
        original = create_initial_state(100_000_000.0)
        path = tmp_path / "live_state.json"

        # When
        save_state(original, path)
        loaded = load_state(path)

        # Then
        assert loaded.schema_version == original.schema_version
        assert loaded.portfolio_id == original.portfolio_id
        assert loaded.shared_cash_model == pytest.approx(original.shared_cash_model)
        assert loaded.shared_cash_actual == pytest.approx(original.shared_cash_actual)
        assert set(loaded.assets.keys()) == set(original.assets.keys())
        for asset_id, orig_asset in original.assets.items():
            loaded_asset = loaded.assets[asset_id]
            assert loaded_asset.asset_id == orig_asset.asset_id
            assert loaded_asset.model_shares == orig_asset.model_shares
            assert loaded_asset.actual_shares == orig_asset.actual_shares
            assert loaded_asset.signal_state == orig_asset.signal_state
            assert loaded_asset.pending_order == orig_asset.pending_order
            assert loaded_asset.buffer_zone_state == orig_asset.buffer_zone_state

    def test_roundtrip_with_pending_order(self, tmp_path: Path):
        """pending_order 가 있는 상태도 왕복 후 동일해야 한다."""
        # Given
        state = create_initial_state(100_000_000.0)
        pending: PendingOrderDict = {
            "asset_id": "sso",
            "intent_type": "ENTER_TO_TARGET",
            "signal_date": "2026-04-10",
            "current_amount": 0.0,
            "target_amount": 35_000_000.0,
            "delta_amount": 35_000_000.0,
            "target_weight": 0.35,
            "hold_days_used": 3,
            "reason": "buffer zone breakout",
        }
        state.assets["sso"].pending_order = pending
        path = tmp_path / "live_state.json"

        # When
        save_state(state, path)
        loaded = load_state(path)

        # Then
        assert loaded.assets["sso"].pending_order == pending

    def test_roundtrip_with_buffer_zone_state(self, tmp_path: Path):
        """BufferZoneState + HoldState (date 객체 포함) 왕복."""
        # Given
        state = create_initial_state(100_000_000.0)
        hold_state: HoldState = {
            "start_date": date(2026, 4, 1),
            "days_passed": 2,
            "buffer_pct": 0.03,
            "hold_days_required": 3,
        }
        state.assets["sso"].buffer_zone_state = BufferZoneState(
            prev_upper=425.0,
            prev_lower=395.0,
            hold_state=hold_state,
            last_buy_buffer_pct=0.03,
            last_hold_days_used=3,
        )
        path = tmp_path / "live_state.json"

        # When
        save_state(state, path)
        loaded = load_state(path)

        # Then
        bzs = loaded.assets["sso"].buffer_zone_state
        assert bzs is not None
        assert bzs.prev_upper == pytest.approx(425.0)
        assert bzs.prev_lower == pytest.approx(395.0)
        assert bzs.last_buy_buffer_pct == pytest.approx(0.03)
        assert bzs.last_hold_days_used == 3
        assert bzs.hold_state is not None
        # HoldState 의 start_date 는 문자열 또는 date 로 복원 (설계 결정: 문자열 유지 허용)
        assert bzs.hold_state["days_passed"] == 2
        assert bzs.hold_state["buffer_pct"] == pytest.approx(0.03)
        assert bzs.hold_state["hold_days_required"] == 3

    def test_save_creates_parent_directory(self, tmp_path: Path):
        """부모 디렉토리가 없어도 자동 생성되어야 한다."""
        state = create_initial_state(100_000_000.0)
        path = tmp_path / "subdir" / "nested" / "live_state.json"
        save_state(state, path)
        assert path.exists()


# ============================================================================
# 수동 작성 JSON → load → 필드 검증
# ============================================================================


# 수동으로 작성한 live_state.json 예시. 각 자산은 서로 다른 상태 조합을 표현한다.
_HANDCRAFTED_LIVE_STATE_JSON = """
{
  "schema_version": 3,
  "portfolio_id": "portfolio_q2_2xs",
  "last_signal_date": "2026-04-10",
  "last_model_execution_date": "2026-04-10",
  "last_rebalance_date": "2026-04-01",
  "shared_cash_model": 12345678.5,
  "shared_cash_actual": 12000000.0,
  "assets": {
    "sso": {
      "asset_id": "sso",
      "model_shares": 420,
      "model_avg_entry_price": 82.05,
      "model_entry_date": "2026-03-15",
      "actual_shares": 420,
      "actual_avg_entry_price": 82.05,
      "actual_entry_date": "2026-03-15",
      "pending_order": {
        "asset_id": "sso",
        "intent_type": "INCREASE_TO_TARGET",
        "signal_date": "2026-04-10",
        "current_amount": 34500.0,
        "target_amount": 35000000.0,
        "delta_amount": 500000.0,
        "target_weight": 0.35,
        "hold_days_used": 3,
        "reason": "buffer zone rebalance"
      },
      "signal_state": "buy",
      "entry_hold_days": 3,
      "buffer_zone_state": {
        "prev_upper": 82.5,
        "prev_lower": 76.0,
        "hold_state": {
          "start_date": "2026-04-08",
          "days_passed": 2,
          "buffer_pct": 0.03,
          "hold_days_required": 3
        },
        "last_buy_buffer_pct": 0.03,
        "last_hold_days_used": 3,
        "schema_version": 1
      }
    },
    "qld": {
      "asset_id": "qld",
      "model_shares": 380,
      "model_avg_entry_price": 92.0,
      "model_entry_date": "2026-02-20",
      "actual_shares": 378,
      "actual_avg_entry_price": 91.8,
      "actual_entry_date": "2026-02-20",
      "pending_order": null,
      "signal_state": "buy",
      "entry_hold_days": 0,
      "buffer_zone_state": {
        "prev_upper": 94.0,
        "prev_lower": 88.0,
        "hold_state": null,
        "last_buy_buffer_pct": 0.03,
        "last_hold_days_used": 0,
        "schema_version": 1
      }
    },
    "gld": {
      "asset_id": "gld",
      "model_shares": 80,
      "model_avg_entry_price": 185.5,
      "model_entry_date": "2026-01-05",
      "actual_shares": 80,
      "actual_avg_entry_price": 185.5,
      "actual_entry_date": "2026-01-05",
      "pending_order": null,
      "signal_state": "buy",
      "entry_hold_days": 0,
      "buffer_zone_state": null
    },
    "tlt": {
      "asset_id": "tlt",
      "model_shares": 0,
      "model_avg_entry_price": 0.0,
      "model_entry_date": null,
      "actual_shares": 0,
      "actual_avg_entry_price": 0.0,
      "actual_entry_date": null,
      "pending_order": null,
      "signal_state": "sell",
      "entry_hold_days": 0,
      "buffer_zone_state": null
    }
  },
  "created_at": "2025-12-01T09:00:00+09:00",
  "updated_at": "2026-04-10T18:00:00+09:00"
}
"""


class TestLoadFromHandcraftedJson:
    """사람이 손으로 작성한 live_state.json 을 ``load_state`` 가 역직렬화하는 계약."""

    def test_load_handcrafted_json_top_level_fields(self, tmp_path: Path):
        """Given 수동 JSON When load Then LiveState 최상위 필드 값 일치."""
        # Given
        path = tmp_path / "live_state.json"
        path.write_text(_HANDCRAFTED_LIVE_STATE_JSON, encoding="utf-8")

        # When
        state = load_state(path)

        # Then
        assert state.schema_version == 3
        assert state.portfolio_id == LIVE_PORTFOLIO_ID
        assert state.last_signal_date == "2026-04-10"
        assert state.last_model_execution_date == "2026-04-10"
        assert state.last_rebalance_date == "2026-04-01"
        assert state.shared_cash_model == pytest.approx(12345678.5)
        assert state.shared_cash_actual == pytest.approx(12000000.0)
        assert state.created_at == "2025-12-01T09:00:00+09:00"
        assert state.updated_at == "2026-04-10T18:00:00+09:00"
        assert set(state.assets.keys()) == {"sso", "qld", "gld", "tlt"}

    def test_load_handcrafted_json_sso_asset_with_pending_and_buffer_zone(self, tmp_path: Path):
        """Given sso 슬롯 When load Then pending_order + buffer_zone_state(hold_state 포함)."""
        # Given
        path = tmp_path / "live_state.json"
        path.write_text(_HANDCRAFTED_LIVE_STATE_JSON, encoding="utf-8")

        # When
        state = load_state(path)
        sso = state.assets["sso"]

        # Then: 기본 필드
        assert sso.asset_id == "sso"
        assert sso.model_shares == 420
        assert sso.model_avg_entry_price == pytest.approx(82.05)
        assert sso.model_entry_date == "2026-03-15"
        assert sso.actual_shares == 420
        assert sso.actual_avg_entry_price == pytest.approx(82.05)
        assert sso.actual_entry_date == "2026-03-15"
        assert sso.signal_state == "buy"
        assert sso.entry_hold_days == 3

        # Then: pending_order (TypedDict) 필드
        assert sso.pending_order is not None
        pending = sso.pending_order
        assert pending["asset_id"] == "sso"
        assert pending["intent_type"] == "INCREASE_TO_TARGET"
        assert pending["signal_date"] == "2026-04-10"
        assert pending["current_amount"] == pytest.approx(34500.0)
        assert pending["target_amount"] == pytest.approx(35000000.0)
        assert pending["delta_amount"] == pytest.approx(500000.0)
        assert pending["target_weight"] == pytest.approx(0.35)
        assert pending["hold_days_used"] == 3
        assert pending["reason"] == "buffer zone rebalance"
        assert "execute_on" not in pending  # 핵심 계약

        # Then: buffer_zone_state + hold_state
        assert sso.buffer_zone_state is not None
        bzs = sso.buffer_zone_state
        assert bzs.prev_upper == pytest.approx(82.5)
        assert bzs.prev_lower == pytest.approx(76.0)
        assert bzs.last_buy_buffer_pct == pytest.approx(0.03)
        assert bzs.last_hold_days_used == 3
        assert bzs.schema_version == 1
        assert bzs.hold_state is not None
        assert bzs.hold_state["start_date"] == "2026-04-08"
        assert bzs.hold_state["days_passed"] == 2
        assert bzs.hold_state["buffer_pct"] == pytest.approx(0.03)
        assert bzs.hold_state["hold_days_required"] == 3

    def test_load_handcrafted_json_qld_with_buffer_zone_no_hold_state(self, tmp_path: Path):
        """Given qld 슬롯 When load Then buffer_zone_state 있고 hold_state null, drift 상태 표현."""
        # Given
        path = tmp_path / "live_state.json"
        path.write_text(_HANDCRAFTED_LIVE_STATE_JSON, encoding="utf-8")

        # When
        qld = load_state(path).assets["qld"]

        # Then: drift 표현 (model 380 vs actual 378)
        assert qld.model_shares == 380
        assert qld.actual_shares == 378
        assert qld.model_avg_entry_price == pytest.approx(92.0)
        assert qld.actual_avg_entry_price == pytest.approx(91.8)
        assert qld.pending_order is None
        assert qld.signal_state == "buy"

        # Then: buffer_zone_state 존재하나 hold_state 는 null
        assert qld.buffer_zone_state is not None
        assert qld.buffer_zone_state.hold_state is None
        assert qld.buffer_zone_state.prev_upper == pytest.approx(94.0)
        assert qld.buffer_zone_state.prev_lower == pytest.approx(88.0)

    def test_load_handcrafted_json_gld_buy_and_hold_without_buffer_zone(self, tmp_path: Path):
        """Given gld 는 buy & hold When load Then buffer_zone_state 가 null."""
        path = tmp_path / "live_state.json"
        path.write_text(_HANDCRAFTED_LIVE_STATE_JSON, encoding="utf-8")

        gld = load_state(path).assets["gld"]
        assert gld.model_shares == 80
        assert gld.buffer_zone_state is None
        assert gld.pending_order is None

    def test_load_handcrafted_json_tlt_completely_empty(self, tmp_path: Path):
        """Given tlt 는 완전 초기 상태 When load Then 포지션 0, 모든 선택 필드 null."""
        path = tmp_path / "live_state.json"
        path.write_text(_HANDCRAFTED_LIVE_STATE_JSON, encoding="utf-8")

        tlt = load_state(path).assets["tlt"]
        assert tlt.model_shares == 0
        assert tlt.actual_shares == 0
        assert tlt.model_entry_date is None
        assert tlt.actual_entry_date is None
        assert tlt.pending_order is None
        assert tlt.buffer_zone_state is None
        assert tlt.entry_hold_days == 0

    def test_load_handcrafted_json_save_again_matches_original(self, tmp_path: Path):
        """Given 수동 JSON When load → save → load Then 2 회차도 동일."""
        # Given
        path = tmp_path / "live_state.json"
        path.write_text(_HANDCRAFTED_LIVE_STATE_JSON, encoding="utf-8")

        # When
        first = load_state(path)
        resave_path = tmp_path / "resaved.json"
        save_state(first, resave_path)
        second = load_state(resave_path)

        # Then: 두 번 로드한 결과가 동일
        assert second.schema_version == first.schema_version
        assert second.portfolio_id == first.portfolio_id
        assert second.shared_cash_model == pytest.approx(first.shared_cash_model)
        assert second.shared_cash_actual == pytest.approx(first.shared_cash_actual)
        for asset_id in ("sso", "qld", "gld", "tlt"):
            a1 = first.assets[asset_id]
            a2 = second.assets[asset_id]
            assert a2.model_shares == a1.model_shares
            assert a2.actual_shares == a1.actual_shares
            assert a2.pending_order == a1.pending_order
            assert a2.buffer_zone_state == a1.buffer_zone_state


# ============================================================================
# load_state 에러 매트릭스
# ============================================================================


class TestLoadStateErrors:
    def test_file_not_found_raises(self, tmp_path: Path):
        """Given 존재하지 않는 파일 When load Then FileNotFoundError 전파."""
        path = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            load_state(path)

    def test_invalid_json_raises_value_error(self, tmp_path: Path):
        """JSON 파싱 실패 → ValueError."""
        path = tmp_path / "live_state.json"
        path.write_text("this is not valid json {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="파싱"):
            load_state(path)

    def test_missing_required_field_raises(self, tmp_path: Path):
        """필수 필드 누락 → ValueError."""
        path = tmp_path / "live_state.json"
        path.write_text(
            json.dumps({"schema_version": SCHEMA_VERSION, "portfolio_id": "x"}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="필드"):
            load_state(path)

    def test_schema_version_mismatch_raises(self, tmp_path: Path):
        """schema_version 불일치 → ValueError."""
        # Given
        state = create_initial_state(100_000_000.0)
        path = tmp_path / "live_state.json"
        save_state(state, path)
        # 파일 내용 손상: schema_version 을 다른 값으로 변경
        data = json.loads(path.read_text(encoding="utf-8"))
        data["schema_version"] = 999
        path.write_text(json.dumps(data), encoding="utf-8")

        # When / Then
        with pytest.raises(ValueError, match="schema_version"):
            load_state(path)


# ============================================================================
# applied_fill_ids 저장 / 로드 / 정리
# ============================================================================


class TestAppliedFillIds:
    def test_save_load_roundtrip(self, tmp_path: Path):
        """Given applied_fill_ids dict When save → load Then 값 일치."""
        # Given
        ids = {
            "fill_a": "2026-04-01T10:00:00+09:00",
            "fill_b": "2026-04-02T11:30:00+09:00",
            "fill_c": "2026-04-03T12:45:00+09:00",
        }
        path = tmp_path / "applied_fill_ids.json"

        # When
        save_applied_fill_ids(ids, path)
        loaded = load_applied_fill_ids(path)

        # Then
        assert loaded == ids

    def test_load_nonexistent_returns_empty_dict(self, tmp_path: Path):
        """파일 없으면 빈 dict 반환 (초기 실행 대응)."""
        path = tmp_path / "applied_fill_ids.json"
        assert load_applied_fill_ids(path) == {}

    def test_load_invalid_json_raises(self, tmp_path: Path):
        """JSON 파싱 실패 → ValueError."""
        path = tmp_path / "applied_fill_ids.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="파싱"):
            load_applied_fill_ids(path)

    @freeze_time("2026-04-11 12:00:00", tz_offset=9)
    def test_cleanup_old_applied_ids_removes_old(self):
        """Given 90 일 초과 ID When cleanup Then 제거되고 최근 ID 는 유지."""
        # Given
        ids = {
            "very_old": "2025-10-01T10:00:00+09:00",  # 약 6 개월 전
            "exactly_90_days": "2026-01-11T10:00:00+09:00",  # 정확히 경계
            "recent": "2026-04-10T10:00:00+09:00",  # 어제
            "today": "2026-04-11T09:00:00+09:00",
        }

        # When
        result = cleanup_old_applied_ids(ids, max_age_days=90)

        # Then
        assert "very_old" not in result
        assert "recent" in result
        assert "today" in result

    @freeze_time("2026-04-11 12:00:00", tz_offset=9)
    def test_cleanup_old_applied_ids_keeps_recent(self):
        """최근 ID 는 유지되어야 한다."""
        ids = {
            "fill_1": "2026-04-10T10:00:00+09:00",
            "fill_2": "2026-04-11T09:00:00+09:00",
        }
        result = cleanup_old_applied_ids(ids, max_age_days=90)
        assert len(result) == 2

    @freeze_time("2026-04-11 12:00:00", tz_offset=9)
    def test_cleanup_default_max_age_is_90_days(self):
        """max_age_days 기본값은 90 일."""
        ids = {
            "old": "2025-10-01T10:00:00+09:00",
            "new": "2026-04-10T10:00:00+09:00",
        }
        result = cleanup_old_applied_ids(ids)  # default
        assert "new" in result
        assert "old" not in result

    def test_cleanup_does_not_mutate_input(self):
        """cleanup 함수는 원본 dict 를 변경하지 않아야 한다 (불변성)."""
        ids = {"a": "2026-04-01T00:00:00+09:00"}
        original_copy = dict(ids)
        _ = cleanup_old_applied_ids(ids, max_age_days=90)
        assert ids == original_copy

    def test_cleanup_corrupt_timestamp_raises(self):
        """Given 파손된 ISO 타임스탬프 When cleanup Then ValueError 전파 (fail-fast)."""
        ids = {"broken": "not-a-valid-iso-timestamp"}
        with pytest.raises(ValueError, match="타임스탬프 파싱 실패"):
            cleanup_old_applied_ids(ids, max_age_days=90)

    def test_save_applied_fill_ids_creates_parent_dir(self, tmp_path: Path):
        """applied_fill_ids 저장 시 부모 디렉토리 자동 생성."""
        path = tmp_path / "sub" / "dir" / "applied_fill_ids.json"
        save_applied_fill_ids({"a": "2026-04-11T00:00:00+09:00"}, path)
        assert path.exists()


# ============================================================================
# atomic save 검증
# ============================================================================


class TestAtomicSave:
    def test_save_state_leaves_no_temp_files(self, tmp_path: Path):
        """save 후 temp 파일이 남아있지 않아야 한다."""
        state = create_initial_state(100_000_000.0)
        path = tmp_path / "live_state.json"
        save_state(state, path)

        # 디렉토리에는 최종 파일만 존재
        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0] == path

    def test_save_overwrites_existing_file(self, tmp_path: Path):
        """기존 파일을 덮어쓸 수 있어야 한다."""
        state_1 = create_initial_state(100_000_000.0)
        state_2 = create_initial_state(200_000_000.0)
        path = tmp_path / "live_state.json"

        save_state(state_1, path)
        save_state(state_2, path)

        loaded = load_state(path)
        assert loaded.shared_cash_model == pytest.approx(200_000_000.0)


# ============================================================================
# 모듈 공개 심볼 smoke
# ============================================================================


class TestModuleSmoke:
    def test_all_public_symbols_accessible(self):
        expected = [
            "create_initial_state",
            "load_state",
            "save_state",
            "load_applied_fill_ids",
            "save_applied_fill_ids",
            "cleanup_old_applied_ids",
        ]
        for sym in expected:
            assert hasattr(state_module, sym), f"live.state 에 {sym} 이 없음"

    def test_live_state_returned_is_live_state_instance(self):
        """create_initial_state 반환 타입 검증."""
        state = create_initial_state(100_000_000.0)
        assert isinstance(state, LiveState)
        for asset in state.assets.values():
            assert isinstance(asset, AssetLiveState)
