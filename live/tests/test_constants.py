"""live.constants 상수 및 헬퍼 함수 계약 테스트.

테스트 철학 (tests/CLAUDE.md 참고):
- Given-When-Then 패턴
- 외부 네트워크 호출 없음
- QBT 코어 PORTFOLIO_CONFIGS 와의 SSoT 정합 검증
"""

from __future__ import annotations

from pathlib import Path

import pytest

from live import constants
from live.constants import (
    APPLIED_FILL_IDS_MAX_AGE_DAYS,
    DEFAULT_APPLIED_FILL_IDS_FILENAME,
    DEFAULT_DATA_STOCK_SUBDIR,
    DEFAULT_LIVE_STATE_DIR,
    DEFAULT_LIVE_STATE_FILENAME,
    DRIFT_CORRECTION_RATIO,
    DRIFT_WARNING_RATIO,
    KST_TZ_NAME,
    LIVE_PORTFOLIO_ID,
    SCHEMA_VERSION,
    build_signal_trade_map,
    get_live_portfolio_config,
)


class TestLivePortfolioId:
    """LIVE_PORTFOLIO_ID 는 QBT 코어 PORTFOLIO_CONFIGS 에 실제 존재하는 실험명이어야 한다."""

    def test_live_portfolio_id_is_q2_2xs(self):
        """설계서 0 장: Q-2-2XS 전략을 기본으로 한다."""
        assert LIVE_PORTFOLIO_ID == "portfolio_q2_2xs"

    def test_live_portfolio_id_exists_in_qbt_core(self):
        """LIVE_PORTFOLIO_ID 가 QBT PORTFOLIO_CONFIGS 에 존재해야 한다 (SSoT)."""
        from qbt.backtest.portfolio_configs import get_portfolio_config

        # Given / When
        config = get_portfolio_config(LIVE_PORTFOLIO_ID)

        # Then
        assert config.experiment_name == LIVE_PORTFOLIO_ID

    def test_get_live_portfolio_config_returns_q2_2xs(self):
        """헬퍼 get_live_portfolio_config 이 Q-2-2XS config 를 반환."""
        config = get_live_portfolio_config()
        assert config.experiment_name == "portfolio_q2_2xs"
        assert len(config.asset_slots) == 4


class TestDriftThresholds:
    """DRIFT 임계값은 0~1 비율이며 warning < correction 이어야 한다."""

    def test_warning_ratio_is_3_percent(self):
        """설계서 14장: 3% 이상은 주의 (0~3% 정상, 3~5% 주의)."""
        assert DRIFT_WARNING_RATIO == pytest.approx(0.03)

    def test_correction_ratio_is_5_percent(self):
        """설계서 14장: 5% 이상은 보정 필요."""
        assert DRIFT_CORRECTION_RATIO == pytest.approx(0.05)

    def test_warning_less_than_correction(self):
        """경고 임계값은 보정 임계값보다 작아야 한다."""
        assert DRIFT_WARNING_RATIO < DRIFT_CORRECTION_RATIO

    def test_both_ratios_are_in_zero_to_one_range(self):
        """CLAUDE.md 비율 표기 규칙: 0~1 소수."""
        assert 0.0 <= DRIFT_WARNING_RATIO <= 1.0
        assert 0.0 <= DRIFT_CORRECTION_RATIO <= 1.0


class TestDefaultPaths:
    """경로 상수는 모두 pathlib.Path 이어야 한다 (CLAUDE.md 필수 규칙)."""

    def test_default_live_state_dir_is_path(self):
        assert isinstance(DEFAULT_LIVE_STATE_DIR, Path)

    def test_default_data_stock_subdir_is_path(self):
        assert isinstance(DEFAULT_DATA_STOCK_SUBDIR, Path)

    def test_default_live_state_dir_points_to_qbt_live_state(self):
        """기본 경로는 'qbt-live-state' 이어야 한다 (설계서 1.3)."""
        assert DEFAULT_LIVE_STATE_DIR == Path("qbt-live-state")

    def test_data_stock_subdir_is_relative(self):
        """data/stock 서브디렉토리."""
        assert DEFAULT_DATA_STOCK_SUBDIR == Path("data/stock")

    def test_default_filenames_are_strings(self):
        assert isinstance(DEFAULT_LIVE_STATE_FILENAME, str)
        assert isinstance(DEFAULT_APPLIED_FILL_IDS_FILENAME, str)
        assert DEFAULT_LIVE_STATE_FILENAME == "live_state.json"
        assert DEFAULT_APPLIED_FILL_IDS_FILENAME == "applied_fill_ids.json"


class TestAppliedFillIdsMaxAge:
    def test_max_age_days_is_ninety(self):
        """설계서 6.2: applied_fill_ids 는 90일 초과 자동 정리."""
        assert APPLIED_FILL_IDS_MAX_AGE_DAYS == 90


class TestSchemaVersion:
    def test_schema_version_is_two(self):
        """schema_version v2 = signal_state 값 집합 {buy, sell, none}."""
        assert SCHEMA_VERSION == 2


class TestKstTzName:
    def test_kst_tz_name(self):
        """설계서 12장: timezone 은 Asia/Seoul."""
        assert KST_TZ_NAME == "Asia/Seoul"


class TestBuildSignalTradeMap:
    """build_signal_trade_map 은 QBT 코어 Q-2-2XS 슬롯에서 signal→trade 매핑을 빌드한다.

    SSoT 원칙: 포트폴리오 구성이 QBT 코어에서 변경되면 live 도 자동 반영.
    """

    def test_returns_dict(self):
        result = build_signal_trade_map()
        assert isinstance(result, dict)

    def test_q2_2xs_mapping_is_correct(self):
        """Q-2-2XS 는 SPY→SSO, QQQ→QLD, GLD→GLD, TLT→TLT 매핑.

        Given: LIVE_PORTFOLIO_ID = portfolio_q2_2xs
        When : build_signal_trade_map() 호출
        Then : 4 개 매핑이 설계서와 일치
        """
        # Given / When
        mapping = build_signal_trade_map()

        # Then
        assert mapping["SPY"] == "SSO"
        assert mapping["QQQ"] == "QLD"
        assert mapping["GLD"] == "GLD"
        assert mapping["TLT"] == "TLT"
        assert len(mapping) == 4

    def test_returned_map_is_independent_copy(self):
        """반환된 dict 수정이 다음 호출에 영향을 주면 안 된다."""
        # Given
        first = build_signal_trade_map()
        first["HACK"] = "HACKED"

        # When
        second = build_signal_trade_map()

        # Then
        assert "HACK" not in second


class TestModuleSmoke:
    """live.constants 모듈의 공개 심볼이 모두 import 가능한지 smoke 테스트."""

    def test_all_public_symbols_accessible(self):
        expected_symbols = [
            "LIVE_PORTFOLIO_ID",
            "DRIFT_WARNING_RATIO",
            "DRIFT_CORRECTION_RATIO",
            "APPLIED_FILL_IDS_MAX_AGE_DAYS",
            "DEFAULT_LIVE_STATE_DIR",
            "DEFAULT_DATA_STOCK_SUBDIR",
            "DEFAULT_LIVE_STATE_FILENAME",
            "DEFAULT_APPLIED_FILL_IDS_FILENAME",
            "SCHEMA_VERSION",
            "KST_TZ_NAME",
            "build_signal_trade_map",
            "get_live_portfolio_config",
        ]
        for sym in expected_symbols:
            assert hasattr(constants, sym), f"live.constants 에 {sym} 이 없음"
