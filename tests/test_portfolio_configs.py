"""포트폴리오 실험 설정 계약 테스트

portfolio_configs.py의 핵심 불변조건/정책을 테스트로 고정한다.

테스트 계약:
1. PORTFOLIO_CONFIGS 개수 == 7
2. 모든 config의 target_weight 합 <= 1.0
3. 모든 config에서 asset_id 중복 없음
4. A 시리즈(a1/a2/a3)에 TQQQ 없음
5. B/C 시리즈의 TQQQ signal_data_path == QQQ_DATA_PATH
6. C-1: QQQ 50% + TQQQ 50% (전액 투자)
7. B-1: target_weight 합 == 0.86 (현금 버퍼 14%)
8. get_portfolio_config("portfolio_a2") 정상 조회
9. get_portfolio_config("nonexistent") → ValueError
"""

import pytest

from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS, get_portfolio_config
from qbt.common_constants import QQQ_DATA_PATH


class TestPortfolioConfigsList:
    """PORTFOLIO_CONFIGS 리스트 불변조건 테스트."""

    def test_portfolio_configs_count(self) -> None:
        """
        목적: PORTFOLIO_CONFIGS에 정확히 7개의 실험이 정의되어 있어야 한다.

        Given: PORTFOLIO_CONFIGS 리스트
        When:  길이를 확인
        Then:  7개
        """
        # When
        count = len(PORTFOLIO_CONFIGS)

        # Then
        assert count == 7

    def test_all_portfolio_configs_target_weights_valid(self) -> None:
        """
        목적: 모든 config의 target_weight 합이 1.0을 초과하지 않아야 한다 (현금 버퍼 허용).

        Given: PORTFOLIO_CONFIGS의 각 config
        When:  target_weight 합산
        Then:  모든 config에서 합 <= 1.0
        """
        for config in PORTFOLIO_CONFIGS:
            total = sum(slot.target_weight for slot in config.asset_slots)
            assert total <= 1.0 + 1e-9, f"{config.experiment_name}: target_weight 합이 1.0을 초과했습니다 ({total:.6f})"

    def test_all_portfolio_configs_no_duplicate_asset_ids(self) -> None:
        """
        목적: 모든 config에서 asset_id가 중복되지 않아야 한다.

        Given: PORTFOLIO_CONFIGS의 각 config
        When:  asset_id 목록을 set()으로 변환
        Then:  set의 크기 == 리스트의 크기 (중복 없음)
        """
        for config in PORTFOLIO_CONFIGS:
            asset_ids = [slot.asset_id for slot in config.asset_slots]
            unique_ids = set(asset_ids)
            assert len(unique_ids) == len(asset_ids), f"{config.experiment_name}: asset_id 중복이 있습니다: {asset_ids}"


class TestASeriesConfigs:
    """A 시리즈 (a1/a2/a3) 설정 계약 테스트."""

    def test_a_series_no_tqqq(self) -> None:
        """
        목적: A 시리즈(portfolio_a1/a2/a3)에는 TQQQ 자산이 없어야 한다.

        Given: experiment_name이 "portfolio_a1", "portfolio_a2", "portfolio_a3"인 config
        When:  asset_id 목록 확인
        Then:  "tqqq" not in asset_ids (각 config)
        """
        a_series_names = {"portfolio_a1", "portfolio_a2", "portfolio_a3"}

        for config in PORTFOLIO_CONFIGS:
            if config.experiment_name not in a_series_names:
                continue
            asset_ids = {slot.asset_id for slot in config.asset_slots}
            assert "tqqq" not in asset_ids, (
                f"{config.experiment_name}: A 시리즈에 TQQQ가 있으면 안 됩니다. " f"asset_ids={asset_ids}"
            )


class TestBCSeriesConfigs:
    """B/C 시리즈 설정 계약 테스트."""

    def test_b_c_series_tqqq_signal_is_qqq(self) -> None:
        """
        목적: B/C 시리즈의 TQQQ 자산은 QQQ 데이터로 시그널을 생성해야 한다.

        Given: portfolio_b1/b2/b3/c1 설정
        When:  TQQQ AssetSlotConfig의 signal_data_path 확인
        Then:  tqqq_slot.signal_data_path == QQQ_DATA_PATH (각 config)
        """
        bc_series_names = {"portfolio_b1", "portfolio_b2", "portfolio_b3", "portfolio_c1"}

        for config in PORTFOLIO_CONFIGS:
            if config.experiment_name not in bc_series_names:
                continue
            for slot in config.asset_slots:
                if slot.asset_id == "tqqq":
                    assert slot.signal_data_path == QQQ_DATA_PATH, (
                        f"{config.experiment_name}: TQQQ signal_data_path가 QQQ_DATA_PATH가 아닙니다. "
                        f"signal_data_path={slot.signal_data_path}"
                    )

    def test_c1_full_investment(self) -> None:
        """
        목적: C-1은 QQQ 50% + TQQQ 50%로 전액 투자해야 한다.

        Given: portfolio_c1 설정 (QQQ 50% + TQQQ 50%)
        When:  target_weight 합산 및 asset_id 확인
        Then:  합 == 1.0, asset_ids == {"qqq", "tqqq"}
        """
        # Given
        config = get_portfolio_config("portfolio_c1")

        # When
        total = sum(slot.target_weight for slot in config.asset_slots)
        asset_ids = {slot.asset_id for slot in config.asset_slots}

        # Then
        assert total == pytest.approx(1.0, abs=1e-9)
        assert asset_ids == {"qqq", "tqqq"}

    def test_b1_cash_buffer(self) -> None:
        """
        목적: B-1은 QQQ 19.5% + TQQQ 7% + SPY 19.5% + GLD 40% = 86% 투자로
              현금 14%를 자동 확보해야 한다.

        Given: portfolio_b1 설정
        When:  target_weight 합산
        Then:  합 == pytest.approx(0.86, abs=1e-9)
        """
        # Given
        config = get_portfolio_config("portfolio_b1")

        # When
        total = sum(slot.target_weight for slot in config.asset_slots)

        # Then
        assert total == pytest.approx(0.86, abs=1e-9)


class TestGetPortfolioConfig:
    """get_portfolio_config() 함수 계약 테스트."""

    def test_get_portfolio_config_returns_correct(self) -> None:
        """
        목적: get_portfolio_config()는 experiment_name이 일치하는 config를 반환해야 한다.

        When:  get_portfolio_config("portfolio_a2") 호출
        Then:  반환된 config.experiment_name == "portfolio_a2"
               반환된 config.display_name이 비어있지 않음
        """
        # When
        config = get_portfolio_config("portfolio_a2")

        # Then
        assert config.experiment_name == "portfolio_a2"
        assert len(config.display_name) > 0

    def test_get_portfolio_config_invalid_name(self) -> None:
        """
        목적: 존재하지 않는 이름으로 조회하면 ValueError가 발생해야 한다.

        When:  get_portfolio_config("nonexistent") 호출
        Then:  ValueError 발생 (match="nonexistent")
        """
        with pytest.raises(ValueError, match="nonexistent"):
            get_portfolio_config("nonexistent")
