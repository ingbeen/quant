"""버퍼존 필드 및 밴드 분리 계약 테스트

buy_buffer_zone_pct 필드 계약과 upper/lower 밴드 분리 불변조건을 검증한다.
"""

import pytest

from qbt.backtest.strategies.buffer_zone import BufferStrategyParams


class TestBuyBufferZonePctField:
    """BufferStrategyParams에 buy_buffer_zone_pct 및 sell_buffer_zone_pct 필드 존재 테스트."""

    def test_params_has_buy_buffer_zone_pct(self):
        """
        BufferStrategyParams에 buy_buffer_zone_pct 필드가 존재해야 한다.

        Given: buy_buffer_zone_pct 파라미터로 생성
        When: 필드 접근
        Then: AttributeError 없이 접근 가능
        """
        # When & Then: buy_buffer_zone_pct로 생성 가능해야 함
        params = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.04,
            hold_days=0,
            initial_capital=10000.0,
        )
        assert params.buy_buffer_zone_pct == 0.03, "buy_buffer_zone_pct가 0.03이어야 함"
        assert params.sell_buffer_zone_pct == 0.04, "sell_buffer_zone_pct가 0.04이어야 함"

    def test_params_has_sell_buffer_zone_pct(self):
        """
        BufferStrategyParams에 sell_buffer_zone_pct 필드가 존재해야 한다.

        Given: sell_buffer_zone_pct 파라미터로 생성
        When: 필드 접근
        Then: AttributeError 없이 접근 가능하고 값이 정확함
        """
        # When & Then
        params = BufferStrategyParams(
            ma_window=10,
            buy_buffer_zone_pct=0.02,
            sell_buffer_zone_pct=0.05,
            hold_days=1,
            initial_capital=50000.0,
        )
        assert params.sell_buffer_zone_pct == 0.05, "sell_buffer_zone_pct가 0.05이어야 함"


class TestBufferStrategyParamsFrozen:
    """BufferStrategyParams frozen 불변성 계약 테스트.

    핵심 계약: BufferStrategyParams는 frozen=True dataclass이므로
    생성 후 필드 변경이 불가능해야 한다.
    """

    def test_frozen_prevents_field_modification(self):
        """
        목적: frozen=True로 인해 필드 변경이 불가능함을 검증

        Given: BufferStrategyParams 인스턴스 생성
        When: ma_window 필드 변경 시도
        Then: FrozenInstanceError 또는 AttributeError 발생
        """
        # Given
        params = BufferStrategyParams(
            initial_capital=10_000_000.0,
            ma_window=200,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=3,
        )

        # When & Then: frozen이므로 속성 변경 시 예외 발생
        with pytest.raises((AttributeError, Exception)):
            params.ma_window = 100  # type: ignore[misc]

    def test_frozen_prevents_hold_days_modification(self):
        """
        목적: hold_days 필드도 변경 불가능함을 검증

        Given: BufferStrategyParams 인스턴스 생성
        When: hold_days 필드 변경 시도
        Then: FrozenInstanceError 또는 AttributeError 발생
        """
        # Given
        params = BufferStrategyParams(
            initial_capital=10_000_000.0,
            ma_window=200,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=3,
        )

        # When & Then
        with pytest.raises((AttributeError, Exception)):
            params.hold_days = 5  # type: ignore[misc]


class TestUpperLowerBandSeparation:
    """upper_band/lower_band 밴드 계약 테스트

    핵심 계약:
    - lower_band는 항상 sell_buffer_zone_pct 기준으로 고정
    - upper_band는 buy_buffer_zone_pct 기준으로 계산
    """

    def test_lower_band_fixed_before_sell(self):
        """
        lower_band = MA × (1 - sell_buffer_pct) 계약 검증

        Given:
          - sell_buffer_zone_pct=0.04, buy_buffer_zone_pct=0.03
          - ma_value=100.0
        When: compute_bands() 호출
        Then:
          - lower_band = 100.0 × (1 - 0.04) = 96.0
          - upper_band = 100.0 × (1 + 0.03) = 103.0
        """
        from qbt.backtest.strategies.buffer_zone_helpers import compute_bands

        # Given
        ma_value = 100.0
        buy_buffer_pct = 0.03
        sell_buffer_pct = 0.04

        # When
        upper_band, lower_band = compute_bands(ma_value, buy_buffer_pct, sell_buffer_pct)

        # Then
        assert upper_band == pytest.approx(
            103.0, abs=1e-6
        ), f"upper_band = MA × (1 + buy_pct). 기대: 103.0, 실제: {upper_band}"
        assert lower_band == pytest.approx(
            96.0, abs=1e-6
        ), f"lower_band = MA × (1 - sell_pct). 기대: 96.0, 실제: {lower_band}"

    def test_lower_band_same_before_and_after_sell(self):
        """
        lower_band와 upper_band가 버퍼 비율에만 의존하는지 검증

        핵심 계약: lower_band = MA × (1 - sell_buffer_pct), 항상 sell_pct에만 의존

        Given:
          - sell_buffer_zone_pct=0.04, buy_buffer_zone_pct=0.03
          - 다양한 MA값에 대해 검증
        When: compute_bands() 호출
        Then: lower_band / MA = (1 - sell_buffer_pct) 일정
        """
        from qbt.backtest.strategies.buffer_zone_helpers import compute_bands

        buy_pct = 0.03
        sell_pct = 0.04

        # 다양한 MA 값에서 비율이 일정한지 검증
        for ma in [50.0, 100.0, 200.0, 300.0]:
            upper, lower = compute_bands(ma, buy_pct, sell_pct)
            assert upper == pytest.approx(ma * (1 + buy_pct), abs=1e-6), f"upper_band 비율 불일치 (MA={ma})"
            assert lower == pytest.approx(ma * (1 - sell_pct), abs=1e-6), f"lower_band 비율 불일치 (MA={ma})"
