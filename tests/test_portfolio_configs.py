"""포트폴리오 실험 설정 계약 테스트

portfolio_configs.py의 핵심 불변조건/정책을 테스트로 고정한다.

테스트 계약:
1. PORTFOLIO_CONFIGS 개수 == 31 (A=3, B=3, C=1, D=2, E=5, F=10, G=4, H=3)
2. 모든 config의 target_weight 합 <= 1.0
3. 모든 config에서 asset_id 중복 없음
4. A 시리즈(a1/a2/a3)에 TQQQ 없음
5. B/C/D 시리즈의 TQQQ signal_data_path == QQQ_DATA_PATH
6. C-1: QQQ 50% + TQQQ 50% (전액 투자)
7. B-1: target_weight 합 == 0.86 (현금 버퍼 14%)
8. get_portfolio_config("portfolio_a2") 정상 조회
9. get_portfolio_config("nonexistent") → ValueError
10. D-1: QQQ 100% 전액 투자 (TQQQ 없음)
11. D-2: TQQQ 100% 전액 투자 (QQQ 시그널 사용)
12. DEFAULT_PORTFOLIO_EXPERIMENTS 불변조건 (12개, 모두 PORTFOLIO_CONFIGS에 존재)
13. F-5~F-7H: target_weight 합 == 1.0, TQQQ QQQ 시그널, H 변형은 GLD/TLT B&H
"""

import pytest

from qbt.backtest.constants import DEFAULT_PORTFOLIO_EXPERIMENTS
from qbt.backtest.portfolio_configs import PORTFOLIO_CONFIGS, get_portfolio_config
from qbt.common_constants import QQQ_DATA_PATH


class TestPortfolioConfigsList:
    """PORTFOLIO_CONFIGS 리스트 불변조건 테스트."""

    def test_portfolio_configs_count(self) -> None:
        """
        목적: PORTFOLIO_CONFIGS에 정확히 31개의 실험이 정의되어 있어야 한다.
              A 3개 + B 3개 + C 1개 + D 2개 + E 5개 + F 10개 + G 4개 + H 3개 = 31개

        Given: PORTFOLIO_CONFIGS 리스트
        When:  길이를 확인
        Then:  31개
        """
        # When
        count = len(PORTFOLIO_CONFIGS)

        # Then
        assert count == 31

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

    def test_b_c_d_series_tqqq_signal_is_qqq(self) -> None:
        """
        목적: B/C/D 시리즈의 TQQQ 자산은 QQQ 데이터로 시그널을 생성해야 한다.

        Given: portfolio_b1/b2/b3/c1/d2 설정
        When:  TQQQ AssetSlotConfig의 signal_data_path 확인
        Then:  tqqq_slot.signal_data_path == QQQ_DATA_PATH (각 config)
        """
        bcd_series_names = {
            "portfolio_b1",
            "portfolio_b2",
            "portfolio_b3",
            "portfolio_c1",
            "portfolio_d2",
        }

        for config in PORTFOLIO_CONFIGS:
            if config.experiment_name not in bcd_series_names:
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


class TestDSeriesConfigs:
    """D 시리즈 (d1/d2) 설정 계약 테스트."""

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

    def test_d2_full_investment_tqqq_only(self) -> None:
        """
        목적: D-2는 TQQQ 100%로 전액 투자해야 하며 asset_ids == {"tqqq"}이어야 한다.

        Given: portfolio_d2 설정 (TQQQ 100%)
        When:  target_weight 합산 및 asset_id 확인
        Then:  합 == 1.0, asset_ids == {"tqqq"}
        """
        # Given
        config = get_portfolio_config("portfolio_d2")

        # When
        total = sum(slot.target_weight for slot in config.asset_slots)
        asset_ids = {slot.asset_id for slot in config.asset_slots}

        # Then
        assert total == pytest.approx(1.0, abs=1e-9)
        assert asset_ids == {"tqqq"}

    def test_d2_tqqq_signal_is_qqq(self) -> None:
        """
        목적: D-2의 TQQQ 자산은 QQQ 데이터로 시그널을 생성해야 한다.

        Given: portfolio_d2 설정
        When:  TQQQ AssetSlotConfig의 signal_data_path 확인
        Then:  signal_data_path == QQQ_DATA_PATH
        """
        # Given
        config = get_portfolio_config("portfolio_d2")

        # When
        tqqq_slot = next(slot for slot in config.asset_slots if slot.asset_id == "tqqq")

        # Then
        assert (
            tqqq_slot.signal_data_path == QQQ_DATA_PATH
        ), f"D-2 TQQQ signal_data_path가 QQQ_DATA_PATH가 아닙니다: {tqqq_slot.signal_data_path}"


class TestDefaultPortfolioExperiments:
    """DEFAULT_PORTFOLIO_EXPERIMENTS 불변조건 테스트."""

    def test_default_portfolio_experiments_count(self) -> None:
        """
        목적: DEFAULT_PORTFOLIO_EXPERIMENTS에 정확히 8개의 활성 실험이 정의되어 있어야 한다.

        Given: DEFAULT_PORTFOLIO_EXPERIMENTS 리스트
        When:  길이를 확인
        Then:  8개
        """
        assert len(DEFAULT_PORTFOLIO_EXPERIMENTS) == 8

    def test_default_portfolio_experiments_all_exist_in_configs(self) -> None:
        """
        목적: DEFAULT_PORTFOLIO_EXPERIMENTS의 모든 실험명이 PORTFOLIO_CONFIGS에 존재해야 한다.

        Given: DEFAULT_PORTFOLIO_EXPERIMENTS 리스트
        When:  각 실험명이 PORTFOLIO_CONFIGS에 존재하는지 확인
        Then:  모든 실험명이 존재
        """
        config_names = {c.experiment_name for c in PORTFOLIO_CONFIGS}
        for exp_name in DEFAULT_PORTFOLIO_EXPERIMENTS:
            assert exp_name in config_names, f"{exp_name}이 PORTFOLIO_CONFIGS에 없습니다. " f"사용 가능: {sorted(config_names)}"

    def test_default_portfolio_experiments_no_duplicates(self) -> None:
        """
        목적: DEFAULT_PORTFOLIO_EXPERIMENTS에 중복된 실험명이 없어야 한다.

        Given: DEFAULT_PORTFOLIO_EXPERIMENTS 리스트
        When:  set으로 변환하여 크기 비교
        Then:  set 크기 == 리스트 크기
        """
        assert len(set(DEFAULT_PORTFOLIO_EXPERIMENTS)) == len(DEFAULT_PORTFOLIO_EXPERIMENTS)


class TestFSeriesExtension:
    """F-5~F-7H 설정 계약 테스트."""

    _F_SERIES_BZ = ["portfolio_f5", "portfolio_f6", "portfolio_f7"]
    _F_SERIES_BH = ["portfolio_f5h", "portfolio_f6h", "portfolio_f7h"]

    def test_f5_to_f7_full_investment(self) -> None:
        """
        목적: F-5~F-7(BZ) 실험은 전액 투자(target_weight 합 == 1.0)이어야 한다.

        Given: portfolio_f5, portfolio_f6, portfolio_f7 설정
        When:  target_weight 합산
        Then:  각각 합 == 1.0
        """
        for name in self._F_SERIES_BZ:
            config = get_portfolio_config(name)
            total = sum(slot.target_weight for slot in config.asset_slots)
            assert total == pytest.approx(1.0, abs=1e-9), f"{name}: target_weight 합이 1.0이 아닙니다 ({total})"

    def test_f5h_to_f7h_full_investment(self) -> None:
        """
        목적: F-5H~F-7H(B&H) 실험은 전액 투자(target_weight 합 == 1.0)이어야 한다.

        Given: portfolio_f5h, portfolio_f6h, portfolio_f7h 설정
        When:  target_weight 합산
        Then:  각각 합 == 1.0
        """
        for name in self._F_SERIES_BH:
            config = get_portfolio_config(name)
            total = sum(slot.target_weight for slot in config.asset_slots)
            assert total == pytest.approx(1.0, abs=1e-9), f"{name}: target_weight 합이 1.0이 아닙니다 ({total})"

    def test_f5_to_f7_tqqq_signal_is_qqq(self) -> None:
        """
        목적: F-5~F-7H의 TQQQ는 QQQ 시그널을 사용해야 한다.

        Given: F-5~F-7H 전체 설정
        When:  TQQQ slot의 signal_data_path 확인
        Then:  signal_data_path == QQQ_DATA_PATH
        """
        all_f = self._F_SERIES_BZ + self._F_SERIES_BH
        for name in all_f:
            config = get_portfolio_config(name)
            tqqq_slot = next(s for s in config.asset_slots if s.asset_id == "tqqq")
            assert tqqq_slot.signal_data_path == QQQ_DATA_PATH, f"{name}: TQQQ signal_data_path가 QQQ_DATA_PATH가 아닙니다"

    def test_f_bz_all_buffer_zone_strategy(self) -> None:
        """
        목적: F-5/F-6/F-7(BZ)은 모든 자산이 버퍼존 전략(기본값)을 사용해야 한다.

        Given: portfolio_f5, portfolio_f6, portfolio_f7 설정
        When:  각 slot의 strategy_id 확인
        Then:  모두 "buffer_zone" (기본값)
        """
        for name in self._F_SERIES_BZ:
            config = get_portfolio_config(name)
            for slot in config.asset_slots:
                assert (
                    slot.strategy_id == "buffer_zone"
                ), f"{name}/{slot.asset_id}: strategy_id가 buffer_zone이 아닙니다 ({slot.strategy_id})"

    def test_f_bh_gld_tlt_buy_and_hold(self) -> None:
        """
        목적: F-5H/F-6H/F-7H는 GLD/TLT만 B&H이고, SPY/TQQQ는 버퍼존이어야 한다.

        Given: portfolio_f5h, portfolio_f6h, portfolio_f7h 설정
        When:  각 slot의 strategy_id 확인
        Then:  GLD/TLT → "buy_and_hold", SPY/TQQQ → "buffer_zone"
        """
        for name in self._F_SERIES_BH:
            config = get_portfolio_config(name)
            for slot in config.asset_slots:
                if slot.asset_id in ("gld", "tlt"):
                    assert (
                        slot.strategy_id == "buy_and_hold"
                    ), f"{name}/{slot.asset_id}: strategy_id가 buy_and_hold가 아닙니다"
                else:
                    assert slot.strategy_id == "buffer_zone", f"{name}/{slot.asset_id}: strategy_id가 buffer_zone이 아닙니다"

    def test_f_pairs_same_weights(self) -> None:
        """
        목적: BZ/B&H 쌍(F-5/F-5H, F-6/F-6H, F-7/F-7H)은 동일한 비중을 가져야 한다.

        Given: BZ/B&H 쌍 설정
        When:  각 쌍의 자산별 target_weight 비교
        Then:  동일
        """
        pairs = [
            ("portfolio_f5", "portfolio_f5h"),
            ("portfolio_f6", "portfolio_f6h"),
            ("portfolio_f7", "portfolio_f7h"),
        ]
        for bz_name, bh_name in pairs:
            bz_config = get_portfolio_config(bz_name)
            bh_config = get_portfolio_config(bh_name)

            bz_weights = {s.asset_id: s.target_weight for s in bz_config.asset_slots}
            bh_weights = {s.asset_id: s.target_weight for s in bh_config.asset_slots}

            assert bz_weights == bh_weights, f"{bz_name}/{bh_name}: 비중이 다릅니다. BZ={bz_weights}, BH={bh_weights}"


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
