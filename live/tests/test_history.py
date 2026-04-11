"""live.history — 영구 히스토리 저장 테스트.

TODO T-15.1 ~ T-15.4 시나리오 고정.
"""

from __future__ import annotations

import json
from pathlib import Path

from live.history import append_summary, append_user_trade, save_daily_log

# ============================================================================
# T-15.1: save_daily_log
# ============================================================================


class TestSaveDailyLog:
    def test_creates_json_file_t_15_1(self, tmp_path: Path):
        """T-15.1: save_daily_log → JSON 파일 생성 확인."""
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
# T-15.2: append_summary
# ============================================================================


class TestAppendSummary:
    def test_appends_one_jsonl_line_t_15_2(self, tmp_path: Path):
        """T-15.2: append_summary → JSONL 1행 추가."""
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
# T-15.3: append_user_trade
# ============================================================================


class TestAppendUserTrade:
    def test_appends_one_jsonl_line_t_15_3(self, tmp_path: Path):
        """T-15.3: append_user_trade → JSONL 1행 추가."""
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
# T-15.4: 같은 날짜 2번 append → 2행
# ============================================================================


class TestJsonlAppendAccumulates:
    def test_two_appends_summary_result_in_two_lines_t_15_4(self, tmp_path: Path):
        """T-15.4: 같은 날짜로 2 번 append → 2 행 (덮어쓰기 아님)."""
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
