"""포트폴리오 실험 설정 계약 테스트

portfolio_configs.py의 핵심 불변조건/정책을 테스트로 고정한다.

테스트 계약:
1. PORTFOLIO_CONFIGS 개수 > 0
2. 모든 config의 슬롯 매매법 target_weight 합 <= 1.0
3. 모든 config의 매매법 안에서 asset_id 중복 없음
4. D-1: QQQ 100% 전액 투자
5. Q-2: SPY/QQQ/GLD/TLT 전액 투자, GLD/TLT B&H
6. Q-2-2XS: SSO/QLD/GLD/TLT 전액 투자, GLD/TLT B&H (1x 합성 경로 사용)
7. get_portfolio_config 정상 조회 / 에러 처리
8. 운용안은 Q-2-2XS 단독이다 — 철회한 보완 전략 조합(부록 M)은 등록되지 않고, 시작일 하한(min_start_date)을 쓰는 등록 실험이 없다
9. QQQ B&H: QQQ 100% 매수 후 보유, 실험 시작일 하한(min_start_date) 없음 — 러너의 시작일 정책을 따른다
10. 모든 슬롯은 상장 전까지 늘린 합성 시세를 읽는다
"""

import pytest

from qbt.backtest.engines.portfolio_data import validate_portfolio_config
from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS, get_portfolio_config
from qbt.backtest.portfolio_types import AllocatorMethodConfig, SlotMethodConfig, resolve_methods
from qbt.common_constants import GLD_SYNTHETIC_DATA_PATH, QQQ_SYNTHETIC_DATA_PATH, TLT_SYNTHETIC_DATA_PATH

from helpers import ONE_TIMES_SIGNAL_OF


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
        목적: QQQ B&H 는 QQQ 100% 를 사서 보유만 하고, 실험 시작일 하한(min_start_date) 없이 러너의 시작일 정책을 따른다.

        Given: portfolio_qqq_bh 설정
        When:  슬롯 · 전략 · 시작일 하한을 확인한다
        Then:  슬롯은 qqq 하나(목표 1.0, buy_and_hold), 신호 · 매매 경로 모두 QQQ 합성, min_start_date 없음, 설정 검증 통과
        """
        # Given
        config = get_portfolio_config("portfolio_qqq_bh")

        # When
        slots = config.asset_slots

        # Then
        assert [(slot.asset_id, slot.strategy_id) for slot in slots] == [("qqq", "buy_and_hold")]
        assert slots[0].target_weight == pytest.approx(1.0, abs=1e-12)
        assert slots[0].signal_data_path == QQQ_SYNTHETIC_DATA_PATH
        assert slots[0].trade_data_path == QQQ_SYNTHETIC_DATA_PATH
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
        Then:  strategy_id == "buy_and_hold", trade_data_path가 1x 합성 경로
        """
        config = get_portfolio_config("portfolio_q2_2xs")
        for slot in config.asset_slots:
            if slot.asset_id in ("gld", "tlt"):
                assert slot.strategy_id == "buy_and_hold", f"{slot.asset_id}: strategy_id가 buy_and_hold가 아닙니다"
        # GLD/TLT는 1x 합성 경로 사용
        gld_slot = next(s for s in config.asset_slots if s.asset_id == "gld")
        tlt_slot = next(s for s in config.asset_slots if s.asset_id == "tlt")
        assert gld_slot.trade_data_path == GLD_SYNTHETIC_DATA_PATH
        assert tlt_slot.trade_data_path == TLT_SYNTHETIC_DATA_PATH

    def test_all_slots_read_synthetic_prices(self) -> None:
        """
        목적: 모든 실험의 슬롯은 상장 전까지 늘린 합성 시세를 읽는다 — 실물 파일이 하나라도 섞이면 포트폴리오 시작일이
              그 상장일로 줄어든다 (사용자 결정 2026-11-05, docs/research/합성_시세_연장.md 결정 10)

        Given: PORTFOLIO_CONFIGS
        When:  실험 · 매매법 · 자산마다 신호 · 매매 경로를 모은다 (배분 규칙 매매법이면 매매 시세와 신호용 시세)
        Then:  모두 `_synthetic_max.csv`
        """
        # When — 목록으로 모음: 자산과 신호용 시세의 id 가 같아도 서로 덮어쓰지 않음
        paths: list[tuple[str, str, str, str]] = []
        for config in PORTFOLIO_CONFIGS:
            for method in resolve_methods(config):
                if isinstance(method, SlotMethodConfig):
                    for slot in method.asset_slots:
                        for path in (slot.signal_data_path, slot.trade_data_path):
                            paths.append((config.experiment_name, method.method_id, slot.asset_id, path.name))
                else:
                    for asset in method.assets:
                        paths.append(
                            (config.experiment_name, method.method_id, asset.asset_id, asset.trade_data_path.name)
                        )
                    for series in method.signal_series:
                        paths.append(
                            (config.experiment_name, method.method_id, series.series_id, series.data_path.name)
                        )

        # Then
        not_synthetic = [entry for entry in paths if not entry[-1].endswith("_synthetic_max.csv")]
        assert not_synthetic == []

    def test_each_slot_trades_its_asset_on_one_times_signal(self) -> None:
        """
        목적: 슬롯마다 자산 id 의 티커를 매매하고, 신호는 그 지수의 1배 합성이다 — 운용 포트폴리오 Q-2-2XS 의 SSO · QLD
              짝을 잘못 바꾸면 다른 상품 · 다른 지수로 사고판 결과가 에러 없이 나온다 (quant-notify 가 이 설정을 옮겨 적는다)

        Given: PORTFOLIO_CONFIGS, 매매 합성 → 그 지수의 1배 합성 표
        When:  슬롯마다 매매 파일을 자산 id 와, 신호를 그 표와 견준다
        Then:  어긋난 슬롯 없음
        """
        # When
        mismatched = [
            (config.experiment_name, slot.asset_id, slot.signal_data_path.name, slot.trade_data_path.name)
            for config in PORTFOLIO_CONFIGS
            for method in resolve_methods(config)
            if isinstance(method, SlotMethodConfig)
            for slot in method.asset_slots
            if slot.trade_data_path.name != f"{slot.asset_id.upper()}_synthetic_max.csv"
            or ONE_TIMES_SIGNAL_OF.get(slot.trade_data_path) != slot.signal_data_path
        ]

        # Then
        assert mismatched == []

    def test_each_allocator_asset_trades_its_asset(self) -> None:
        """
        목적: 배분 규칙 매매법의 자산마다 자산 id 의 티커를 매매한다 — 짝을 잘못 지으면 다른 상품으로 사고판 결과가
              그 자산 이름으로 에러 없이 나온다 (배분 규칙은 매매 시세로 판단해 신호 짝은 없다)

        Given: PORTFOLIO_CONFIGS
        When:  배분 규칙 매매법의 자산마다 매매 파일을 자산 id 와 견준다
        Then:  어긋난 자산 없음
        """
        # When
        mismatched = [
            (config.experiment_name, method.method_id, asset.asset_id, asset.trade_data_path.name)
            for config in PORTFOLIO_CONFIGS
            for method in resolve_methods(config)
            if isinstance(method, AllocatorMethodConfig)
            for asset in method.assets
            if asset.trade_data_path.name != f"{asset.asset_id.upper()}_synthetic_max.csv"
        ]

        # Then
        assert mismatched == []


class TestWithdrawnSupplementConfigs:
    """보완 전략 조합 철회 (사용자 결정 2026-11-04, 부록 O) 계약 테스트."""

    @pytest.mark.parametrize(
        "name",
        ["portfolio_q2_2xs_haa10_rotation10", *(f"portfolio_q2_2xs_{c}25" for c in ("shy", "gold", "haa", "rotation"))],
    )
    def test_supplement_experiments_are_not_registered(self, name: str) -> None:
        """
        목적: 철회한 채택 조합과 채택 전 25% 등록 넷은 공식 목록에 없다.

        Given: 보완 전략 등록 실험 이름
        When:  get_portfolio_config 로 조회한다
        Then:  ValueError
        """
        with pytest.raises(ValueError, match=name):
            get_portfolio_config(name)

    def test_no_config_has_start_date_floor(self) -> None:
        """
        목적: 시작일 하한 칸을 쓰는 등록 실험이 없다 — 모든 실험이 러너의 시작일 정책을 따른다.

        Given: PORTFOLIO_CONFIGS
        When:  min_start_date 가 있는 실험을 고른다
        Then:  없음
        """
        names = {c.experiment_name for c in PORTFOLIO_CONFIGS if c.min_start_date is not None}
        assert names == set()


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
