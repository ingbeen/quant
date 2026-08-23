"""포트폴리오 실험 설정 계약 테스트

portfolio_configs.py의 핵심 불변조건/정책을 테스트로 고정한다.

테스트 계약:
1. PORTFOLIO_CONFIGS 개수 > 0
2. 모든 config의 target_weight 합 <= 1.0
3. 모든 config에서 asset_id 중복 없음
4. D-1: QQQ 100% 전액 투자
5. Q-2: SPY/QQQ/GLD/TLT 전액 투자, GLD/TLT B&H
6. Q-2-2XS: SSO/QLD/GLD/TLT 전액 투자, GLD/TLT B&H (1x 경로 사용)
7. Q-2-2XS-CASH: SSO/QLD만 보유, target_weight 합 0.70 (잔여 30% 현금)
8. Q-2-2XS-FULL: SSO/QLD 각 50% 전액 투자
9. Q-2-2XS 계열 3종의 주식 슬롯 타이밍 파라미터 동일
10. get_portfolio_config 정상 조회 / 에러 처리
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

    def test_q2_2xs_cash_leaves_cash_buffer(self) -> None:
        """
        목적: Q-2-2XS-CASH는 target_weight 합이 0.70이어야 한다 (잔여 30% 현금 유지).

        Given: portfolio_q2_2xs_cash 설정
        When:  target_weight 합산
        Then:  합 == 0.70
        """
        config = get_portfolio_config("portfolio_q2_2xs_cash")
        total = sum(slot.target_weight for slot in config.asset_slots)
        assert total == pytest.approx(0.70, abs=1e-9)

    def test_q2_2xs_cash_stock_slots_only(self) -> None:
        """
        목적: Q-2-2XS-CASH는 방어자산 없이 SSO/QLD 주식 슬롯만 가져야 한다.

        Given: portfolio_q2_2xs_cash 설정
        When:  asset_id 집합 및 각 슬롯의 target_weight/strategy_id 확인
        Then:  asset_ids == {"sso", "qld"}, 각 슬롯 0.35, 모두 buffer_zone
        """
        config = get_portfolio_config("portfolio_q2_2xs_cash")
        asset_ids = {slot.asset_id for slot in config.asset_slots}

        assert asset_ids == {"sso", "qld"}
        for slot in config.asset_slots:
            assert slot.target_weight == pytest.approx(0.35, abs=1e-9), f"{slot.asset_id}: target_weight가 0.35가 아닙니다"
            assert slot.strategy_id == "buffer_zone", f"{slot.asset_id}: strategy_id가 buffer_zone이 아닙니다"

    def test_q2_2xs_cash_signal_trade_paths(self) -> None:
        """
        목적: Q-2-2XS-CASH는 기존 Q-2-2XS와 동일한 시그널/매매 경로를 사용해야 한다.

        Given: portfolio_q2_2xs_cash 설정
        When:  SSO/QLD 슬롯의 signal_data_path, trade_data_path 확인
        Then:  SSO는 SPY 시그널 + SSO 매매, QLD는 QQQ 시그널 + QLD 매매
        """
        from qbt.common_constants import QLD_DATA_PATH, QQQ_DATA_PATH, SPY_DATA_PATH, SSO_DATA_PATH

        config = get_portfolio_config("portfolio_q2_2xs_cash")
        sso_slot = next(s for s in config.asset_slots if s.asset_id == "sso")
        qld_slot = next(s for s in config.asset_slots if s.asset_id == "qld")

        assert sso_slot.signal_data_path == SPY_DATA_PATH
        assert sso_slot.trade_data_path == SSO_DATA_PATH
        assert qld_slot.signal_data_path == QQQ_DATA_PATH
        assert qld_slot.trade_data_path == QLD_DATA_PATH

    def test_q2_2xs_full_investment_stock_only(self) -> None:
        """
        목적: Q-2-2XS-FULL은 SSO/QLD 각 50%로 전액 투자해야 한다.

        Given: portfolio_q2_2xs_full 설정
        When:  target_weight 합산 및 각 슬롯 확인
        Then:  합 == 1.0, asset_ids == {"sso", "qld"}, 각 슬롯 0.50, 모두 buffer_zone
        """
        config = get_portfolio_config("portfolio_q2_2xs_full")
        total = sum(slot.target_weight for slot in config.asset_slots)
        asset_ids = {slot.asset_id for slot in config.asset_slots}

        assert total == pytest.approx(1.0, abs=1e-9)
        assert asset_ids == {"sso", "qld"}
        for slot in config.asset_slots:
            assert slot.target_weight == pytest.approx(0.50, abs=1e-9), f"{slot.asset_id}: target_weight가 0.50이 아닙니다"
            assert slot.strategy_id == "buffer_zone", f"{slot.asset_id}: strategy_id가 buffer_zone이 아닙니다"

    def test_q2_2xs_full_signal_trade_paths(self) -> None:
        """
        목적: Q-2-2XS-FULL은 기존 Q-2-2XS와 동일한 시그널/매매 경로를 사용해야 한다.

        Given: portfolio_q2_2xs_full 설정
        When:  SSO/QLD 슬롯의 signal_data_path, trade_data_path 확인
        Then:  SSO는 SPY 시그널 + SSO 매매, QLD는 QQQ 시그널 + QLD 매매
        """
        from qbt.common_constants import QLD_DATA_PATH, QQQ_DATA_PATH, SPY_DATA_PATH, SSO_DATA_PATH

        config = get_portfolio_config("portfolio_q2_2xs_full")
        sso_slot = next(s for s in config.asset_slots if s.asset_id == "sso")
        qld_slot = next(s for s in config.asset_slots if s.asset_id == "qld")

        assert sso_slot.signal_data_path == SPY_DATA_PATH
        assert sso_slot.trade_data_path == SSO_DATA_PATH
        assert qld_slot.signal_data_path == QQQ_DATA_PATH
        assert qld_slot.trade_data_path == QLD_DATA_PATH

    def test_q2_2xs_series_share_identical_timing_params(self) -> None:
        """
        목적: Q-2-2XS 계열 3종은 주식 슬롯의 타이밍 파라미터가 모두 동일해야 한다.

        방어자산 대체 효과만 분리 측정하려면 주식 매매 타이밍이 세 실험에서 같아야 한다.
        파라미터가 갈리면 방어자산 효과와 타이밍 효과가 섞여 비교가 성립하지 않는다.

        Given: portfolio_q2_2xs / portfolio_q2_2xs_cash / portfolio_q2_2xs_full 설정
        When:  SSO/QLD 슬롯의 ma_window, 버퍼존 비율, hold_days, ma_type 수집
        Then:  자산별로 세 실험의 값이 모두 일치
        """
        experiment_names = ("portfolio_q2_2xs", "portfolio_q2_2xs_cash", "portfolio_q2_2xs_full")
        baseline: dict[str, tuple[int, float, float, int, str]] = {}

        for experiment_name in experiment_names:
            config = get_portfolio_config(experiment_name)
            for slot in config.asset_slots:
                if slot.asset_id not in ("sso", "qld"):
                    continue
                params = (
                    slot.ma_window,
                    slot.buy_buffer_zone_pct,
                    slot.sell_buffer_zone_pct,
                    slot.hold_days,
                    slot.ma_type,
                )
                if slot.asset_id not in baseline:
                    baseline[slot.asset_id] = params
                assert params == baseline[slot.asset_id], (
                    f"{experiment_name}/{slot.asset_id}: 타이밍 파라미터가 다른 실험과 다릅니다 "
                    f"({params} != {baseline[slot.asset_id]})"
                )

        assert set(baseline.keys()) == {"sso", "qld"}


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
