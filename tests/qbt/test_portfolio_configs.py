"""포트폴리오 실험 설정 계약 테스트

portfolio_configs.py의 핵심 불변조건/정책을 테스트로 고정한다.

테스트 계약:
1. PORTFOLIO_CONFIGS 개수 > 0
2. 모든 config의 슬롯 매매법 target_weight 합 <= 1.0
3. 모든 config의 매매법 안에서 asset_id 중복 없음
4. D-1: QQQ 100% 전액 투자
5. Q-2: SPY/QQQ/GLD/TLT 전액 투자, GLD/TLT B&H
6. Q-2-2XS: SSO/QLD/GLD/TLT 전액 투자, GLD/TLT B&H (1x 경로 사용)
7. get_portfolio_config 정상 조회 / 에러 처리
8. 보완 전략 등록 실험: 채택 조합(매매법 3개 0.8 / 0.1 / 0.1)이
   그리드와 같은 구성 함수 · 같은 시작일 하한(주 비교 시작일)으로 등록, 채택 전 25% 등록 넷은 없음
9. QQQ B&H: QQQ 100% 매수 후 보유, 시작일 하한 없음(기존 실험과 같은 시작일 정책)
"""

import pytest

from qbt.backtest.engines.portfolio_data import validate_portfolio_config
from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS, get_portfolio_config
from qbt.backtest.portfolio_types import SlotMethodConfig, resolve_methods
from qbt.backtest.supplement_experiment import (
    MAIN_START_DATE,
    VARIANT_SPLICED,
    build_combo_config,
)


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
            for method in resolve_methods(config):
                if not isinstance(method, SlotMethodConfig):
                    continue
                total = sum(slot.target_weight for slot in method.asset_slots)
                assert (
                    total <= 1.0 + 1e-9
                ), f"{config.experiment_name}.{method.method_id}: target_weight 합이 1.0을 초과했습니다 ({total:.6f})"

    def test_all_portfolio_configs_no_duplicate_asset_ids(self) -> None:
        """
        목적: 모든 config에서 asset_id가 중복되지 않아야 한다.

        Given: PORTFOLIO_CONFIGS의 각 config
        When:  asset_id 목록을 set()으로 변환
        Then:  set의 크기 == 리스트의 크기 (중복 없음)
        """
        for config in PORTFOLIO_CONFIGS:
            for method in resolve_methods(config):
                if isinstance(method, SlotMethodConfig):
                    asset_ids = [slot.asset_id for slot in method.asset_slots]
                else:
                    asset_ids = [asset.asset_id for asset in method.assets]
                assert len(set(asset_ids)) == len(
                    asset_ids
                ), f"{config.experiment_name}: asset_id 중복이 있습니다: {asset_ids}"

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


class TestQqqBuyAndHoldConfig:
    """QQQ B&H (매매 규칙 없는 기준점) 설정 계약 테스트."""

    def test_qqq_bh_holds_qqq_without_trading_rule(self) -> None:
        """
        목적: QQQ B&H 는 QQQ 100% 를 사서 보유만 하고, 기존 실험과 같은 시작일 정책(실험 하한 없음)을 따른다.

        Given: portfolio_qqq_bh 설정
        When:  슬롯 · 전략 · 시작일 하한을 확인한다
        Then:  슬롯은 qqq 하나(목표 1.0, buy_and_hold), 신호 · 매매 경로 모두 QQQ, min_start_date 없음, 설정 검증 통과
        """
        from qbt.common_constants import QQQ_DATA_PATH

        # Given
        config = get_portfolio_config("portfolio_qqq_bh")

        # When
        slots = config.asset_slots

        # Then
        assert [(slot.asset_id, slot.strategy_id) for slot in slots] == [("qqq", "buy_and_hold")]
        assert slots[0].target_weight == pytest.approx(1.0, abs=1e-12)
        assert slots[0].signal_data_path == QQQ_DATA_PATH
        assert slots[0].trade_data_path == QQQ_DATA_PATH
        assert config.min_start_date is None
        validate_portfolio_config(config)


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


class TestSupplementConfigs:
    """보완 전략 등록 실험 (채택 조합 Q-2-2XS 80% + HAA 10% + 로테이션 10%, 설계서 D75) 계약 테스트."""

    def test_adopted_combo_is_registered_as_grid_built(self) -> None:
        """
        목적: 채택 조합이 조합 그리드와 같은 구성 함수 · 같은 시작일 하한으로 등록돼 대시보드 숫자가 그리드와 같다.

        Given: 등록 실험 portfolio_q2_2xs_haa10_rotation10
        When:  get_portfolio_config 로 조회한다
        Then:  build_combo_config(10, 10, 이어 붙인 판, 주 비교 시작일)과 같은 설정, 매매법 (q2_2xs 0.8 · haa 0.1 · rotation 0.1),
               설정 검증 통과
        """
        # Given
        q2_2xs = get_portfolio_config("portfolio_q2_2xs")

        # When
        config = get_portfolio_config("portfolio_q2_2xs_haa10_rotation10")
        methods = resolve_methods(config)

        # Then
        assert config == build_combo_config(q2_2xs.asset_slots, 10, 10, VARIANT_SPLICED, MAIN_START_DATE)
        assert [m.method_id for m in methods] == ["q2_2xs", "haa", "rotation"]
        assert [m.target_weight for m in methods] == pytest.approx([0.8, 0.1, 0.1], abs=1e-12)
        validate_portfolio_config(config)

    def test_only_supplement_configs_have_start_date_floor(self) -> None:
        """
        목적: 시작일 하한 칸은 보완 전략 등록 실험만 쓴다 — 기존 실험의 시작일이 바뀌지 않는다.

        Given: PORTFOLIO_CONFIGS
        When:  min_start_date 가 있는 실험을 고른다
        Then:  채택 조합뿐
        """
        names = {c.experiment_name for c in PORTFOLIO_CONFIGS if c.min_start_date is not None}
        assert names == {"portfolio_q2_2xs_haa10_rotation10"}

    @pytest.mark.parametrize("name", [f"portfolio_q2_2xs_{c}25" for c in ("shy", "gold", "haa", "rotation")])
    def test_pre_adoption_25pct_experiments_are_not_registered(self, name: str) -> None:
        """
        목적: 채택 전 25% 등록 넷은 공식 목록에 없다 — 채택하지 않은 보완 전략 등록은 지운다(D52).

        Given: 채택 전 등록 실험 이름
        When:  get_portfolio_config 로 조회한다
        Then:  ValueError
        """
        with pytest.raises(ValueError, match=name):
            get_portfolio_config(name)


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
