"""STRATEGY_REGISTRY 계약 테스트

strategy_registry.py의 핵심 계약/불변조건을 테스트로 고정한다.

테스트 계약:
1. STRATEGY_REGISTRY에 "buffer_zone", "buy_and_hold" 키가 존재한다.
2. create_strategy(slot): buffer_zone → BufferZoneStrategy, buy_and_hold → BuyAndHoldStrategy 반환
3. prepare_signal_df(df, slot): buffer_zone → MA 컬럼 추가, buy_and_hold → 원본 반환
4. get_warmup_periods(slot): buffer_zone → slot.ma_window, buy_and_hold → 0
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldStrategy
from qbt.backtest.strategy_registry import STRATEGY_REGISTRY
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME

# ============================================================================
# 헬퍼 함수
# ============================================================================


def _make_slot(ma_window: int = 10) -> AssetSlotConfig:
    """테스트용 AssetSlotConfig를 생성한다.

    strategy_id/strategy_type 필드는 registry lookup이 아니라
    직접 spec을 선택하는 방식으로 테스트하므로 여기서 명시하지 않는다.
    """
    return AssetSlotConfig(
        asset_id="qqq",
        signal_data_path=Path("dummy.csv"),
        trade_data_path=Path("dummy.csv"),
        target_weight=0.50,
        ma_window=ma_window,
    )


def _make_stock_df(n_rows: int = 30) -> pd.DataFrame:
    """테스트용 합성 주식 데이터를 생성한다."""
    start = date(2024, 1, 2)
    dates: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)

    closes = [100.0 + i * 0.5 for i in range(n_rows)]
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [c - 0.5 for c in closes],
            COL_HIGH: [c + 1.0 for c in closes],
            COL_LOW: [c - 1.0 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * n_rows,
        }
    )


# ============================================================================
# TestStrategyRegistryKeys
# ============================================================================


class TestStrategyRegistryKeys:
    """STRATEGY_REGISTRY 키 존재 계약 테스트."""

    def test_buffer_zone_key_exists(self) -> None:
        """
        목적: STRATEGY_REGISTRY에 "buffer_zone" 키가 존재해야 한다.

        Given: STRATEGY_REGISTRY 딕셔너리
        When:  "buffer_zone" 키 조회
        Then:  None이 아님 (키 존재)
        """
        # When & Then
        assert "buffer_zone" in STRATEGY_REGISTRY, "'buffer_zone' 키가 STRATEGY_REGISTRY에 없습니다."

    def test_buy_and_hold_key_exists(self) -> None:
        """
        목적: STRATEGY_REGISTRY에 "buy_and_hold" 키가 존재해야 한다.

        Given: STRATEGY_REGISTRY 딕셔너리
        When:  "buy_and_hold" 키 조회
        Then:  None이 아님 (키 존재)
        """
        # When & Then
        assert "buy_and_hold" in STRATEGY_REGISTRY, "'buy_and_hold' 키가 STRATEGY_REGISTRY에 없습니다."

    def test_registry_has_exactly_two_entries(self) -> None:
        """
        목적: STRATEGY_REGISTRY에는 현재 두 전략만 등록되어야 한다.

        Given: STRATEGY_REGISTRY 딕셔너리
        When:  길이 확인
        Then:  2개
        """
        # When & Then
        assert len(STRATEGY_REGISTRY) == 2, f"STRATEGY_REGISTRY에 2개의 항목이 있어야 합니다. 실제: {len(STRATEGY_REGISTRY)}"


# ============================================================================
# TestStrategySpecCreateStrategy
# ============================================================================


class TestStrategySpecCreateStrategy:
    """StrategySpec.create_strategy() 계약 테스트."""

    def test_buffer_zone_creates_buffer_zone_strategy(self) -> None:
        """
        목적: buffer_zone spec의 create_strategy()가 BufferZoneStrategy를 반환해야 한다.

        Given: STRATEGY_REGISTRY["buffer_zone"] spec
               buffer_zone AssetSlotConfig
        When:  spec.create_strategy(slot) 호출
        Then:  반환값이 BufferZoneStrategy 인스턴스
        """
        # Given
        spec = STRATEGY_REGISTRY["buffer_zone"]
        slot = _make_slot(ma_window=10)

        # When
        strategy = spec.create_strategy(slot)

        # Then
        assert isinstance(
            strategy, BufferZoneStrategy
        ), f"buffer_zone spec.create_strategy()는 BufferZoneStrategy를 반환해야 합니다. 실제: {type(strategy)}"

    def test_buffer_zone_strategy_implements_signal_strategy_protocol(self) -> None:
        """
        목적: create_strategy()가 SignalStrategy Protocol을 구현한 객체를 반환해야 한다.

        Given: STRATEGY_REGISTRY["buffer_zone"] spec
        When:  spec.create_strategy(slot) 호출
        Then:  check_buy, check_sell, get_buy_meta 속성이 존재함
        """
        # Given
        spec = STRATEGY_REGISTRY["buffer_zone"]
        slot = _make_slot(ma_window=10)

        # When
        strategy = spec.create_strategy(slot)

        # Then: SignalStrategy Protocol 필수 메서드 존재 확인
        assert hasattr(strategy, "check_buy"), "SignalStrategy.check_buy 메서드가 없습니다."
        assert hasattr(strategy, "check_sell"), "SignalStrategy.check_sell 메서드가 없습니다."
        assert hasattr(strategy, "get_buy_meta"), "SignalStrategy.get_buy_meta 메서드가 없습니다."

    def test_buy_and_hold_creates_buy_and_hold_strategy(self) -> None:
        """
        목적: buy_and_hold spec의 create_strategy()가 BuyAndHoldStrategy를 반환해야 한다.

        Given: STRATEGY_REGISTRY["buy_and_hold"] spec
               buy_and_hold AssetSlotConfig
        When:  spec.create_strategy(slot) 호출
        Then:  반환값이 BuyAndHoldStrategy 인스턴스
        """
        # Given
        spec = STRATEGY_REGISTRY["buy_and_hold"]
        slot = _make_slot()

        # When
        strategy = spec.create_strategy(slot)

        # Then
        assert isinstance(
            strategy, BuyAndHoldStrategy
        ), f"buy_and_hold spec.create_strategy()는 BuyAndHoldStrategy를 반환해야 합니다. 실제: {type(strategy)}"

    def test_buy_and_hold_strategy_implements_signal_strategy_protocol(self) -> None:
        """
        목적: buy_and_hold create_strategy()도 SignalStrategy Protocol을 구현해야 한다.

        Given: STRATEGY_REGISTRY["buy_and_hold"] spec
        When:  spec.create_strategy(slot) 호출
        Then:  check_buy, check_sell, get_buy_meta 속성이 존재함
        """
        # Given
        spec = STRATEGY_REGISTRY["buy_and_hold"]
        slot = _make_slot()

        # When
        strategy = spec.create_strategy(slot)

        # Then
        assert hasattr(strategy, "check_buy"), "SignalStrategy.check_buy 메서드가 없습니다."
        assert hasattr(strategy, "check_sell"), "SignalStrategy.check_sell 메서드가 없습니다."
        assert hasattr(strategy, "get_buy_meta"), "SignalStrategy.get_buy_meta 메서드가 없습니다."


# ============================================================================
# TestStrategySpecPrepareSignalDf
# ============================================================================


class TestStrategySpecPrepareSignalDf:
    """StrategySpec.prepare_signal_df() 계약 테스트."""

    def test_buffer_zone_adds_ma_column(self) -> None:
        """
        목적: buffer_zone spec의 prepare_signal_df()가 ma_{ma_window} 컬럼을 추가해야 한다.

        Given: STRATEGY_REGISTRY["buffer_zone"] spec
               ma_window=10 AssetSlotConfig
               MA 컬럼이 없는 원본 DataFrame
        When:  spec.prepare_signal_df(df, slot) 호출
        Then:  반환 DataFrame에 "ma_10" 컬럼이 존재함
        """
        # Given
        spec = STRATEGY_REGISTRY["buffer_zone"]
        slot = _make_slot(ma_window=10)
        df = _make_stock_df(n_rows=30)

        assert "ma_10" not in df.columns, "사전조건: 원본 df에 MA 컬럼이 없어야 합니다."

        # When
        result_df = spec.prepare_signal_df(df, slot)

        # Then
        assert "ma_10" in result_df.columns, "buffer_zone prepare_signal_df()는 'ma_10' 컬럼을 추가해야 합니다."

    def test_buffer_zone_ma_column_name_matches_ma_window(self) -> None:
        """
        목적: 추가되는 MA 컬럼명이 ma_{ma_window} 형식이어야 한다.

        Given: ma_window=20 buffer_zone slot
        When:  prepare_signal_df() 호출
        Then:  "ma_20" 컬럼 존재
        """
        # Given
        spec = STRATEGY_REGISTRY["buffer_zone"]
        slot = _make_slot(ma_window=20)
        df = _make_stock_df(n_rows=30)

        # When
        result_df = spec.prepare_signal_df(df, slot)

        # Then
        assert "ma_20" in result_df.columns, "ma_window=20이면 'ma_20' 컬럼이 있어야 합니다."

    def test_buffer_zone_does_not_modify_original_df(self) -> None:
        """
        목적: prepare_signal_df()가 원본 DataFrame을 변경하지 않아야 한다 (데이터 불변성).

        Given: MA 컬럼이 없는 원본 DataFrame
        When:  spec.prepare_signal_df(df, slot) 호출
        Then:  원본 df에 MA 컬럼이 추가되지 않음
        """
        # Given
        spec = STRATEGY_REGISTRY["buffer_zone"]
        slot = _make_slot(ma_window=10)
        df = _make_stock_df(n_rows=30)
        original_columns = set(df.columns)

        # When
        spec.prepare_signal_df(df, slot)

        # Then
        assert set(df.columns) == original_columns, "prepare_signal_df()가 원본 DataFrame을 변경하면 안 됩니다."

    def test_buy_and_hold_returns_same_columns(self) -> None:
        """
        목적: buy_and_hold spec의 prepare_signal_df()가 컬럼을 추가하지 않아야 한다.

        Given: STRATEGY_REGISTRY["buy_and_hold"] spec
               원본 DataFrame
        When:  spec.prepare_signal_df(df, slot) 호출
        Then:  반환 DataFrame의 컬럼이 원본과 동일함
        """
        # Given
        spec = STRATEGY_REGISTRY["buy_and_hold"]
        slot = _make_slot()
        df = _make_stock_df(n_rows=30)
        original_columns = set(df.columns)

        # When
        result_df = spec.prepare_signal_df(df, slot)

        # Then
        assert set(result_df.columns) == original_columns, (
            "buy_and_hold prepare_signal_df()는 컬럼을 추가하면 안 됩니다. " f"원본: {original_columns}, 반환: {set(result_df.columns)}"
        )

    def test_buy_and_hold_returns_same_length(self) -> None:
        """
        목적: buy_and_hold prepare_signal_df()가 행 수를 변경하지 않아야 한다.

        Given: 30행짜리 DataFrame
        When:  spec.prepare_signal_df(df, slot) 호출
        Then:  반환 DataFrame도 30행
        """
        # Given
        spec = STRATEGY_REGISTRY["buy_and_hold"]
        slot = _make_slot()
        df = _make_stock_df(n_rows=30)

        # When
        result_df = spec.prepare_signal_df(df, slot)

        # Then
        assert len(result_df) == 30, f"buy_and_hold prepare_signal_df()는 행 수를 유지해야 합니다. 실제: {len(result_df)}"


# ============================================================================
# TestStrategySpecGetWarmupPeriods
# ============================================================================


class TestStrategySpecGetWarmupPeriods:
    """StrategySpec.get_warmup_periods() 계약 테스트."""

    def test_buffer_zone_returns_ma_window(self) -> None:
        """
        목적: buffer_zone spec의 get_warmup_periods()가 slot.ma_window를 반환해야 한다.

        Given: STRATEGY_REGISTRY["buffer_zone"] spec
               ma_window=10 AssetSlotConfig
        When:  spec.get_warmup_periods(slot) 호출
        Then:  반환값 == 10
        """
        # Given
        spec = STRATEGY_REGISTRY["buffer_zone"]
        slot = _make_slot(ma_window=10)

        # When
        warmup = spec.get_warmup_periods(slot)

        # Then
        assert warmup == 10, f"buffer_zone get_warmup_periods()는 ma_window(10)를 반환해야 합니다. 실제: {warmup}"

    def test_buffer_zone_warmup_matches_different_ma_windows(self) -> None:
        """
        목적: get_warmup_periods()가 ma_window 값에 따라 달라져야 한다.

        Given: ma_window=200 buffer_zone slot
        When:  get_warmup_periods() 호출
        Then:  200 반환
        """
        # Given
        spec = STRATEGY_REGISTRY["buffer_zone"]
        slot = _make_slot(ma_window=200)

        # When
        warmup = spec.get_warmup_periods(slot)

        # Then
        assert warmup == 200, f"buffer_zone get_warmup_periods()는 ma_window(200)를 반환해야 합니다. 실제: {warmup}"

    def test_buy_and_hold_returns_zero(self) -> None:
        """
        목적: buy_and_hold spec의 get_warmup_periods()가 0을 반환해야 한다.

        Given: STRATEGY_REGISTRY["buy_and_hold"] spec
               buy_and_hold AssetSlotConfig
        When:  spec.get_warmup_periods(slot) 호출
        Then:  반환값 == 0
        """
        # Given
        spec = STRATEGY_REGISTRY["buy_and_hold"]
        slot = _make_slot()

        # When
        warmup = spec.get_warmup_periods(slot)

        # Then
        assert warmup == 0, f"buy_and_hold get_warmup_periods()는 0을 반환해야 합니다. 실제: {warmup}"

    def test_buy_and_hold_warmup_zero_regardless_of_ma_window(self) -> None:
        """
        목적: buy_and_hold는 ma_window 값과 무관하게 0을 반환해야 한다.

        Given: ma_window=200 buy_and_hold slot (ma_window는 사실상 무시됨)
        When:  get_warmup_periods() 호출
        Then:  0 반환
        """
        # Given
        spec = STRATEGY_REGISTRY["buy_and_hold"]
        slot = _make_slot(ma_window=200)

        # When
        warmup = spec.get_warmup_periods(slot)

        # Then
        assert warmup == 0, f"buy_and_hold get_warmup_periods()는 항상 0이어야 합니다. 실제: {warmup}"
