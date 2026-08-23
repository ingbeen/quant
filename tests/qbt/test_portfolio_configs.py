"""포트폴리오 실험 설정 계약 테스트

portfolio_configs.py의 핵심 불변조건/정책을 테스트로 고정한다.

테스트 계약:
1. PORTFOLIO_CONFIGS 개수 > 0
2. 모든 config의 target_weight 합 <= 1.0
3. 모든 config에서 asset_id 중복 없음
4. D-1: QQQ 100% 전액 투자
5. Q-2: SPY/QQQ/GLD/TLT 전액 투자, GLD/TLT B&H
6. Q-2-2XS: SSO/QLD/GLD/TLT 전액 투자, GLD/TLT B&H (1x 경로 사용)
7. get_portfolio_config 정상 조회 / 에러 처리
"""

import pytest

from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS, get_portfolio_config


class TestPortfolioConfigsList:
    """PORTFOLIO_CONFIGS 리스트 불변조건 테스트."""

    def test_portfolio_configs_not_empty(self) -> None:
        """
        목적: PORTFOLIO_CONFIGS가 비어있지 않아야 한다.

        Given: PORTFOLIO_CONFIGS 리스트
        When:  길이를 확인
        Then:  비어있지 않아야 함
        """
        assert len(PORTFOLIO_CONFIGS) > 0

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

    def test_all_experiment_names_unique(self) -> None:
        """
        목적: 모든 config의 experiment_name이 고유해야 한다.

        Given: PORTFOLIO_CONFIGS 리스트
        When:  experiment_name 중복 확인
        Then:  중복 없음
        """
        names = [c.experiment_name for c in PORTFOLIO_CONFIGS]
        assert len(names) == len(set(names)), f"experiment_name 중복 발견: {names}"


class TestDSeriesConfigs:
    """D 시리즈 설정 계약 테스트."""

    def test_d1_full_investment_qqq_only(self) -> None:
        """
        목적: D-1은 QQQ 100%로 전액 투자해야 하며 TQQQ가 없어야 한다.

        Given: portfolio_d1 설정 (QQQ 100%)
        When:  target_weight 합산 및 asset_id 확인
        Then:  합 == 1.0, asset_ids == {"qqq"}, "tqqq" 없음
        """
        # Given
        config = get_portfolio_config("portfolio_d1")

        # When
        total = sum(slot.target_weight for slot in config.asset_slots)
        asset_ids = {slot.asset_id for slot in config.asset_slots}

        # Then
        assert total == pytest.approx(1.0, abs=1e-9)
        assert asset_ids == {"qqq"}
        assert "tqqq" not in asset_ids


class TestQSeriesConfigs:
    """Q 시리즈 설정 계약 테스트."""

    def test_q2_full_investment(self) -> None:
        """
        목적: Q-2는 전액 투자(target_weight 합 == 1.0)이어야 한다.

        Given: portfolio_q2 설정
        When:  target_weight 합산
        Then:  합 == 1.0
        """
        config = get_portfolio_config("portfolio_q2")
        total = sum(slot.target_weight for slot in config.asset_slots)
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_q2_gld_tlt_buy_and_hold(self) -> None:
        """
        목적: Q-2는 GLD/TLT가 B&H이어야 한다.

        Given: portfolio_q2 설정
        When:  GLD/TLT slot의 strategy_id 확인
        Then:  strategy_id == "buy_and_hold"
        """
        config = get_portfolio_config("portfolio_q2")
        for slot in config.asset_slots:
            if slot.asset_id in ("gld", "tlt"):
                assert slot.strategy_id == "buy_and_hold", f"{slot.asset_id}: strategy_id가 buy_and_hold가 아닙니다"

    def test_q2_2xs_full_investment(self) -> None:
        """
        목적: Q-2-2XS는 전액 투자(target_weight 합 == 1.0)이어야 한다.

        Given: portfolio_q2_2xs 설정
        When:  target_weight 합산
        Then:  합 == 1.0
        """
        config = get_portfolio_config("portfolio_q2_2xs")
        total = sum(slot.target_weight for slot in config.asset_slots)
        assert total == pytest.approx(1.0, abs=1e-9)

    def test_q2_2xs_gld_tlt_buy_and_hold(self) -> None:
        """
        목적: Q-2-2XS는 GLD/TLT가 1x B&H이어야 한다.

        Given: portfolio_q2_2xs 설정
        When:  GLD/TLT slot 확인
        Then:  strategy_id == "buy_and_hold", trade_data_path가 1x 경로
        """
        from qbt.common_constants import GLD_DATA_PATH, TLT_DATA_PATH

        config = get_portfolio_config("portfolio_q2_2xs")
        for slot in config.asset_slots:
            if slot.asset_id in ("gld", "tlt"):
                assert slot.strategy_id == "buy_and_hold", f"{slot.asset_id}: strategy_id가 buy_and_hold가 아닙니다"
        # GLD/TLT는 1x 경로 사용
        gld_slot = next(s for s in config.asset_slots if s.asset_id == "gld")
        tlt_slot = next(s for s in config.asset_slots if s.asset_id == "tlt")
        assert gld_slot.trade_data_path == GLD_DATA_PATH
        assert tlt_slot.trade_data_path == TLT_DATA_PATH


class TestGetPortfolioConfig:
    """get_portfolio_config() 함수 계약 테스트."""

    def test_get_portfolio_config_returns_correct(self) -> None:
        """
        목적: get_portfolio_config()는 experiment_name이 일치하는 config를 반환해야 한다.

        When:  get_portfolio_config("portfolio_d1") 호출
        Then:  반환된 config.experiment_name == "portfolio_d1"
               반환된 config.display_name이 비어있지 않음
        """
        # When
        config = get_portfolio_config("portfolio_d1")

        # Then
        assert config.experiment_name == "portfolio_d1"
        assert len(config.display_name) > 0

    def test_get_portfolio_config_invalid_name(self) -> None:
        """
        목적: 존재하지 않는 이름으로 조회하면 ValueError가 발생해야 한다.

        When:  get_portfolio_config("nonexistent") 호출
        Then:  ValueError 발생 (match="nonexistent")
        """
        with pytest.raises(ValueError, match="nonexistent"):
            get_portfolio_config("nonexistent")
