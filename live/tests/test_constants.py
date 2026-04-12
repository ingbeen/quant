"""live.constants 상수 및 헬퍼 함수 계약을 검증한다."""

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

    def test_live_portfolio_id_is_calibrated(self):
        """Given LIVE_PORTFOLIO_ID Then 고정된 calibration 값과 일치한다."""
        # 이 테스트는 LIVE_PORTFOLIO_ID 변경 시 명시적 승인을 강제하기 위한 calibration lock 이다.
        assert LIVE_PORTFOLIO_ID == "portfolio_q2_2xs"

    def test_live_portfolio_id_exists_in_qbt_core(self):
        """LIVE_PORTFOLIO_ID 가 QBT PORTFOLIO_CONFIGS 에 존재해야 한다 (SSoT)."""
        from qbt.backtest.portfolio_configs import get_portfolio_config

        # Given / When
        config = get_portfolio_config(LIVE_PORTFOLIO_ID)

        # Then
        assert config.experiment_name == LIVE_PORTFOLIO_ID

    def test_get_live_portfolio_config_returns_live_portfolio(self):
        """Given get_live_portfolio_config When 호출 Then live 포트폴리오 config 반환."""
        config = get_live_portfolio_config()
        assert config.experiment_name == LIVE_PORTFOLIO_ID
        assert len(config.asset_slots) == 4


class TestDriftThresholds:
    """DRIFT 임계값은 0~1 비율이며 warning < correction 이어야 한다."""

    def test_warning_ratio_is_3_percent(self):
        """DRIFT_WARNING_RATIO 는 3% (주의 임계값)."""
        assert DRIFT_WARNING_RATIO == pytest.approx(0.03)

    def test_correction_ratio_is_5_percent(self):
        """DRIFT_CORRECTION_RATIO 는 5% (보정 필요 임계값)."""
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
        """DEFAULT_LIVE_STATE_DIR 은 'qbt-live-state' 디렉토리명이어야 한다."""
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
        """applied_fill_ids 는 90일 초과 시 자동 정리 주기를 가진다."""
        assert APPLIED_FILL_IDS_MAX_AGE_DAYS == 90


class TestSchemaVersion:
    def test_schema_version_is_three(self):
        """schema_version v3 = AssetLiveState.signal_state {buy, sell} QBT 동일."""
        assert SCHEMA_VERSION == 3


class TestKstTzName:
    def test_kst_tz_name(self):
        """KST 타임존 이름은 Asia/Seoul 이어야 한다."""
        assert KST_TZ_NAME == "Asia/Seoul"


class TestBuildSignalTradeMap:
    """build_signal_trade_map 은 QBT 코어 포트폴리오 슬롯에서 signal→trade 매핑을 빌드한다."""

    def test_returns_dict(self):
        result = build_signal_trade_map()
        assert isinstance(result, dict)

    def test_mapping_is_correct_calibration(self):
        """Given LIVE_PORTFOLIO_ID When build_signal_trade_map Then calibration 매핑과 일치."""
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
