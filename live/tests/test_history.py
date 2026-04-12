"""live.history 영구 히스토리 저장/로드 계약을 검증한다."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from live.history import (
    append_balance_adjust,
    append_signal_history,
    append_summary,
    append_user_trade,
    load_signal_history,
    load_user_trades,
    save_daily_log,
)
from live.models import UserTrade

# ============================================================================
# save_daily_log
# ============================================================================


class TestSaveDailyLog:
    def test_creates_json_file(self, tmp_path: Path):
        """Given save_daily_log 호출 When 실행 Then JSON 파일 생성."""
        payload = {"execution_date": "2026-04-10", "model_equity": 100_000_000.0}
        path = save_daily_log("2026-04-10", payload, tmp_path)

        assert path.exists()
        assert path.name == "2026-04-10.json"
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["execution_date"] == "2026-04-10"
        assert loaded["model_equity"] == 100_000_000.0

    def test_creates_parent_directory(self, tmp_path: Path):
        nested = tmp_path / "subdir" / "history"
        save_daily_log("2026-04-10", {}, nested)
        assert (nested / "daily" / "2026-04-10.json").exists()

    def test_same_date_overwrites(self, tmp_path: Path):
        """save_daily_log 는 같은 날짜로 두 번 호출되면 **덮어쓴다** (일별 상세 1개 정본)."""
        save_daily_log("2026-04-10", {"v": 1}, tmp_path)
        path = save_daily_log("2026-04-10", {"v": 2}, tmp_path)

        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["v"] == 2  # 덮어쓰기


# ============================================================================
# append_summary
# ============================================================================


class TestAppendSummary:
    def test_appends_one_jsonl_line(self, tmp_path: Path):
        """Given append_summary 호출 When 실행 Then JSONL 1행 추가."""
        append_summary({"date": "2026-04-10", "equity": 100_000_000.0}, tmp_path)

        target = tmp_path / "summary.jsonl"
        assert target.exists()
        lines = target.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["date"] == "2026-04-10"

    def test_creates_parent_directory(self, tmp_path: Path):
        nested = tmp_path / "deep" / "history"
        append_summary({"v": 1}, nested)
        assert (nested / "summary.jsonl").exists()


# ============================================================================
# append_user_trade
# ============================================================================


class TestAppendUserTrade:
    def test_appends_one_jsonl_line(self, tmp_path: Path):
        """Given append_user_trade 호출 When 실행 Then JSONL 1행 추가."""
        append_user_trade(
            {
                "asset_id": "sso",
                "direction": "buy",
                "actual_price": 82.05,
                "actual_shares": 420,
                "trade_date": "2026-04-10",
            },
            tmp_path,
        )

        target = tmp_path / "user_trades.jsonl"
        assert target.exists()
        lines = target.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["asset_id"] == "sso"
        assert parsed["actual_shares"] == 420


# ============================================================================
# append-only 누적 정책
# ============================================================================


class TestJsonlAppendAccumulates:
    def test_two_appends_summary_result_in_two_lines(self, tmp_path: Path):
        """Given 같은 날짜로 2 번 append When 실행 Then 2 행 (덮어쓰기 아님)."""
        append_summary({"date": "2026-04-10", "v": 1}, tmp_path)
        append_summary({"date": "2026-04-10", "v": 2}, tmp_path)

        lines = (tmp_path / "summary.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["v"] == 1
        assert json.loads(lines[1])["v"] == 2

    def test_two_appends_user_trade_result_in_two_lines(self, tmp_path: Path):
        """append_user_trade 도 동일 정책 (append-only)."""
        trade = {"asset_id": "sso", "direction": "buy", "actual_shares": 100}
        append_user_trade(trade, tmp_path)
        append_user_trade(trade, tmp_path)

        lines = (tmp_path / "user_trades.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_summary_and_user_trades_are_separate_files(self, tmp_path: Path):
        append_summary({"v": 1}, tmp_path)
        append_user_trade({"a": 2}, tmp_path)

        assert (tmp_path / "summary.jsonl").exists()
        assert (tmp_path / "user_trades.jsonl").exists()

    def test_three_summaries_three_lines(self, tmp_path: Path):
        for i in range(3):
            append_summary({"i": i}, tmp_path)

        lines = (tmp_path / "summary.jsonl").read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3


# ============================================================================
# 추가 sanity
# ============================================================================


class TestEncoding:
    def test_korean_characters_preserved(self, tmp_path: Path):
        """한글 메시지가 ensure_ascii=False 로 그대로 저장됨."""
        append_summary({"메모": "리밸런싱 발생"}, tmp_path)

        content = (tmp_path / "summary.jsonl").read_text(encoding="utf-8")
        assert "리밸런싱 발생" in content

    def test_date_object_serialized_via_default(self, tmp_path: Path):
        """date 객체도 default=str 로 ISO 문자열 변환됨."""
        from datetime import date

        append_summary({"date": date(2026, 4, 10)}, tmp_path)

        content = (tmp_path / "summary.jsonl").read_text(encoding="utf-8")
        assert "2026-04-10" in content


# ============================================================================
# signal history (append + load)
# ============================================================================


class TestSignalHistory:
    def test_append_creates_file_and_lines(self, tmp_path: Path):
        """Given 신호 entry 여러 개 When append Then signals.jsonl 에 줄 수 맞춤."""
        entries = [
            {"date": "2026-04-10", "asset_id": "sso", "state": "none"},
            {"date": "2026-04-10", "asset_id": "gld", "state": "buy"},
        ]
        append_signal_history(entries, tmp_path)

        path = tmp_path / "signals.jsonl"
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2

    def test_append_empty_list_is_noop(self, tmp_path: Path):
        """Given 빈 list When append Then 파일 생성되지 않음."""
        append_signal_history([], tmp_path)
        assert not (tmp_path / "signals.jsonl").exists()

    def test_load_returns_empty_when_missing(self, tmp_path: Path):
        """Given 파일 없음 When load Then 빈 dict 반환."""
        result = load_signal_history(tmp_path)
        assert result == {}

    def test_load_parses_by_asset(self, tmp_path: Path):
        """Given 여러 날짜 / 여러 자산 When load Then 자산별 그룹핑."""
        entries = [
            {"date": "2026-04-08", "asset_id": "sso", "state": "none"},
            {"date": "2026-04-09", "asset_id": "sso", "state": "buy"},
            {"date": "2026-04-09", "asset_id": "gld", "state": "sell"},
            {"date": "2026-04-10", "asset_id": "gld", "state": "buy"},
        ]
        append_signal_history(entries, tmp_path)

        result = load_signal_history(tmp_path)
        assert set(result.keys()) == {"sso", "gld"}
        assert result["sso"] == [("2026-04-08", "none"), ("2026-04-09", "buy")]
        assert result["gld"] == [("2026-04-09", "sell"), ("2026-04-10", "buy")]

    def test_append_only_does_not_overwrite(self, tmp_path: Path):
        """Given 2 번 append When 두 번째 호출 Then 이전 줄 유지 + 새 줄 추가."""
        append_signal_history([{"date": "2026-04-09", "asset_id": "sso", "state": "none"}], tmp_path)
        append_signal_history([{"date": "2026-04-10", "asset_id": "sso", "state": "buy"}], tmp_path)

        result = load_signal_history(tmp_path)
        assert result["sso"] == [("2026-04-09", "none"), ("2026-04-10", "buy")]


# ============================================================================
# user_trades load
# ============================================================================


class TestLoadUserTrades:
    def test_load_returns_empty_when_missing(self, tmp_path: Path):
        result = load_user_trades(tmp_path)
        assert result == {}

    def test_load_parses_by_asset(self, tmp_path: Path):
        """Given append_user_trade 로 3 건 쓴 후 When load Then 자산별 UserTrade 목록."""
        append_user_trade({"asset_id": "sso", "direction": "buy", "date": "2026-04-10"}, tmp_path)
        append_user_trade({"asset_id": "sso", "direction": "sell", "date": "2026-04-11"}, tmp_path)
        append_user_trade({"asset_id": "gld", "direction": "buy", "date": "2026-04-10"}, tmp_path)

        result = load_user_trades(tmp_path)
        assert set(result.keys()) == {"sso", "gld"}
        assert len(result["sso"]) == 2
        assert len(result["gld"]) == 1

        sso_first = result["sso"][0]
        assert isinstance(sso_first, UserTrade)
        assert sso_first.direction == "buy"
        assert sso_first.date == "2026-04-10"


# ============================================================================
# balance_adjust audit append
# ============================================================================


class TestAppendBalanceAdjust:
    def test_append_creates_file_and_line(self, tmp_path: Path):
        append_balance_adjust(
            {
                "rtdb_key": "adj_001",
                "asset_id": "sso",
                "new_shares": 420,
                "new_cash": None,
                "reason": "test",
                "input_time_kst": "2026-04-10T20:00:00+09:00",
            },
            tmp_path,
        )
        path = tmp_path / "balance_adjusts.jsonl"
        assert path.exists()
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        assert "adj_001" in lines[0]
        assert '"asset_id": "sso"' in lines[0]

    def test_append_only_accumulates(self, tmp_path: Path):
        append_balance_adjust({"rtdb_key": "a1", "reason": "r1"}, tmp_path)
        append_balance_adjust({"rtdb_key": "a2", "reason": "r2"}, tmp_path)

        path = tmp_path / "balance_adjusts.jsonl"
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert "a1" in lines[0]
        assert "a2" in lines[1]


# ============================================================================
# JSONL 손상 → RuntimeError (데이터 무결성)
# ============================================================================


class TestLoadCorruptedJsonlFailFast:
    """JSONL 파일에 손상된 행이 있으면 RuntimeError 로 즉시 중단한다."""

    def test_user_trades_corrupted_raises_runtime_error(self, tmp_path: Path):
        """Given user_trades.jsonl 에 유효하지 않은 JSON 행 When load Then RuntimeError."""
        path = tmp_path / "user_trades.jsonl"
        path.write_text(
            '{"asset_id":"sso","direction":"buy","date":"2026-04-10"}\n'
            "NOT_VALID_JSON\n"
            '{"asset_id":"gld","direction":"sell","date":"2026-04-11"}\n',
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="손상된 JSONL"):
            load_user_trades(tmp_path)

    def test_signal_history_corrupted_raises_runtime_error(self, tmp_path: Path):
        """Given signals.jsonl 에 유효하지 않은 JSON 행 When load Then RuntimeError."""
        path = tmp_path / "signals.jsonl"
        path.write_text(
            '{"date":"2026-04-10","asset_id":"sso","state":"buy"}\n'
            "{broken_json\n"
            '{"date":"2026-04-11","asset_id":"gld","state":"sell"}\n',
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="손상된 JSONL"):
            load_signal_history(tmp_path)
