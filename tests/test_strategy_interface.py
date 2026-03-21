"""SignalStrategy Protocol 계약 테스트

새 인터페이스 기준:
- check_buy(signal_df, i, current_date) -> bool
- check_sell(signal_df, i) -> bool
- get_buy_meta() -> dict[str, float | int]
- BufferZoneStrategy: stateful, 생성자 (ma_col, buy_buffer_pct, sell_buffer_pct, hold_days)
- BuyAndHoldStrategy: stateless, 파라미터 없는 생성자
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldStrategy
from qbt.backtest.strategies.strategy_common import SignalStrategy


# ============================================================================
# 테스트용 샘플 DataFrame 생성 헬퍼
# ============================================================================


def _make_signal_df() -> pd.DataFrame:
    """기본 signal DataFrame 생성 (5일, ma_200 포함).

    MA=98.0, upper_band = 98 * (1 + 0.03) = 100.94, lower_band = 98 * (1 - 0.05) = 93.1

    - i=0: Close=100.0 (below upper=100.94 → 상향돌파 없음)
    - i=1: Close=101.5 (above upper=100.94 → i=0→i=1 상향돌파)
    - i=2: Close=101.5 (above upper, 유지)
    - i=3: Close=92.0  (below lower=93.1 → i=2→i=3 하향돌파)
    - i=4: Close=92.0  (below lower)
    """
    return pd.DataFrame(
        {
            "Date": [date(2020, 1, d) for d in range(1, 6)],
            "Close": [100.0, 101.5, 101.5, 92.0, 92.0],
            "ma_200": [98.0, 98.0, 98.0, 98.0, 98.0],
        }
    )


# ============================================================================
# BufferZoneStrategy 테스트 (새 인터페이스)
# ============================================================================


class TestBufferZoneStrategyInterface:
    """BufferZoneStrategy 새 인터페이스 계약 테스트 (stateful, 생성자 파라미터)."""

    def test_check_buy_i0_always_false(self) -> None:
        """
        목적: i=0 (최초 호출)에서 check_buy는 항상 False를 반환해야 함

        Given: BufferZoneStrategy("ma_200", 0.03, 0.05, 0), signal_df (5행)
        When: check_buy(signal_df, 0, current_date) 호출
        Then: False 반환 (초기화만 수행, 신호 없음)
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        result = strategy.check_buy(signal_df, 0, date(2020, 1, 1))

        assert result is False

    def test_check_buy_i1_breakout_returns_true(self) -> None:
        """
        목적: i=1에서 상향돌파 조건 충족 시 check_buy → True 반환

        Given: BufferZoneStrategy("ma_200", 0.03, 0.05, hold_days=0)
               i=0 Close=100.0 <= upper=100.94, i=1 Close=101.5 > upper=100.94
        When: check_buy(signal_df, 0) → 초기화, check_buy(signal_df, 1) → 돌파 감지
        Then: True 반환
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        strategy.check_buy(signal_df, 0, date(2020, 1, 1))  # 초기화
        result = strategy.check_buy(signal_df, 1, date(2020, 1, 2))

        assert result is True

    def test_check_buy_no_breakout_returns_false(self) -> None:
        """
        목적: 상향돌파 조건 미충족 시 check_buy → False 반환

        Given: Close가 upper_band 아래인 signal_df
               MA=98.0, upper=100.94, Close=[99.0, 100.0] (모두 upper 이하)
        When: check_buy(df, 0) → 초기화, check_buy(df, 1)
        Then: False 반환
        """
        df = pd.DataFrame(
            {
                "Date": [date(2020, 1, 1), date(2020, 1, 2)],
                "Close": [99.0, 100.0],  # upper=100.94이므로 100.0 < 100.94
                "ma_200": [98.0, 98.0],
            }
        )
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        strategy.check_buy(df, 0, date(2020, 1, 1))
        result = strategy.check_buy(df, 1, date(2020, 1, 2))

        assert result is False

    def test_check_sell_i0_always_false(self) -> None:
        """
        목적: i=0 (최초 호출)에서 check_sell은 항상 False를 반환해야 함

        Given: BufferZoneStrategy("ma_200", 0.03, 0.05, 0), signal_df
        When: check_sell(signal_df, 0) 호출
        Then: False 반환 (초기화만 수행)
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        result = strategy.check_sell(signal_df, 0)

        assert result is False

    def test_check_sell_breakdown_returns_true(self) -> None:
        """
        목적: 하향돌파 조건 충족 시 check_sell → True 반환

        Given: i=2 Close=101.5 >= lower=93.1, i=3 Close=92.0 < lower=93.1 → 하향돌파
        When: check_sell(signal_df, 2) → 초기화, check_sell(signal_df, 3)
        Then: True 반환
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        strategy.check_sell(signal_df, 2)  # 초기화 (prev = i=1 기준)
        result = strategy.check_sell(signal_df, 3)

        assert result is True

    def test_check_sell_no_breakdown_returns_false(self) -> None:
        """
        목적: 하향돌파 조건 미충족 시 check_sell → False 반환

        Given: Close가 lower_band 위인 signal_df
               MA=98.0, lower=93.1, Close=[100.0, 99.0] (모두 lower 위)
        When: check_sell(df, 0) → 초기화, check_sell(df, 1)
        Then: False 반환
        """
        df = pd.DataFrame(
            {
                "Date": [date(2020, 1, 1), date(2020, 1, 2)],
                "Close": [100.0, 99.0],  # lower=93.1이므로 99.0 > 93.1
                "ma_200": [98.0, 98.0],
            }
        )
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        strategy.check_sell(df, 0)
        result = strategy.check_sell(df, 1)

        assert result is False

    def test_get_buy_meta_after_buy_signal_has_required_keys(self) -> None:
        """
        목적: check_buy → True 직후 get_buy_meta()가 올바른 키를 반환하는지 검증

        Given: BufferZoneStrategy, 상향돌파 조건 (i=0 초기화, i=1 돌파)
        When: check_buy(i=1) → True, get_buy_meta()
        Then: dict 반환, "buy_buffer_pct"와 "hold_days_used" 키 존재
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        strategy.check_buy(signal_df, 0, date(2020, 1, 1))
        strategy.check_buy(signal_df, 1, date(2020, 1, 2))  # True
        meta = strategy.get_buy_meta()

        assert isinstance(meta, dict)
        assert "buy_buffer_pct" in meta
        assert "hold_days_used" in meta

    def test_get_buy_meta_buy_buffer_pct_value(self) -> None:
        """
        목적: get_buy_meta()["buy_buffer_pct"]가 생성자에서 전달한 buy_buffer_pct와 일치하는지 검증

        Given: BufferZoneStrategy("ma_200", 0.03, 0.05, 0), 상향돌파
        When: check_buy → True, get_buy_meta()
        Then: meta["buy_buffer_pct"] == 0.03
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        strategy.check_buy(signal_df, 0, date(2020, 1, 1))
        strategy.check_buy(signal_df, 1, date(2020, 1, 2))
        meta = strategy.get_buy_meta()

        assert meta["buy_buffer_pct"] == pytest.approx(0.03, abs=1e-12)

    def test_hold_days_i0_returns_false(self) -> None:
        """
        목적: hold_days > 0일 때도 i=0은 False 반환

        Given: BufferZoneStrategy("ma_200", 0.03, 0.05, hold_days=3), i=0
        When: check_buy(signal_df, 0, date) 호출
        Then: False 반환
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 3)

        result = strategy.check_buy(signal_df, 0, date(2020, 1, 1))

        assert result is False

    def test_hold_days_breakout_returns_false_first(self) -> None:
        """
        목적: hold_days=3일 때 상향돌파 시 즉시 매수 아닌 False 반환 (대기 상태 진입)

        Given: BufferZoneStrategy("ma_200", 0.03, 0.05, hold_days=3), 상향돌파 조건
        When: check_buy(i=0) → 초기화, check_buy(i=1) → 상향돌파
        Then: False 반환 (hold_days 충족 전)
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 3)

        strategy.check_buy(signal_df, 0, date(2020, 1, 1))
        result = strategy.check_buy(signal_df, 1, date(2020, 1, 2))

        assert result is False

    def test_state_shared_between_check_buy_and_check_sell(self) -> None:
        """
        목적: check_buy와 check_sell이 내부 _prev 상태를 공유하는지 검증
              (check_buy i=0 초기화 후 check_sell 호출 시 재초기화 없이 동작)

        Given: BufferZoneStrategy, check_buy(i=0) 후 check_sell(i=1) 호출
        When: check_buy(i=0) → _prev 초기화, check_sell(i=1)
        Then: check_sell(i=1)이 (prev=row[0], cur=row[1]) 기준으로 판단하여 False 반환
              (Close[1]=101.5 > lower=93.1 → 하향돌파 없음)
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        strategy.check_buy(signal_df, 0, date(2020, 1, 1))  # _prev 초기화
        result = strategy.check_sell(signal_df, 1)  # i=1: 하향돌파 없음

        assert result is False


# ============================================================================
# BuyAndHoldStrategy 테스트 (새 인터페이스)
# ============================================================================


class TestBuyAndHoldStrategyInterface:
    """BuyAndHoldStrategy 새 인터페이스 계약 테스트 (stateless, 파라미터 없는 생성자)."""

    def test_check_buy_always_true_i0(self) -> None:
        """
        목적: i=0에서도 check_buy → True 반환 (B&H는 항상 즉시 매수)

        Given: BuyAndHoldStrategy(), 임의 signal_df
        When: check_buy(signal_df, 0, current_date) 호출
        Then: True 반환
        """
        signal_df = pd.DataFrame({"Date": [date(2020, 1, 1)], "Close": [100.0]})
        strategy = BuyAndHoldStrategy()

        result = strategy.check_buy(signal_df, 0, date(2020, 1, 1))

        assert result is True

    def test_check_buy_always_true_any_i(self) -> None:
        """
        목적: 임의 i에서 check_buy → True 반환

        Given: BuyAndHoldStrategy(), 5행 signal_df
        When: check_buy(signal_df, 3, date) 호출
        Then: True 반환
        """
        signal_df = pd.DataFrame(
            {
                "Date": [date(2020, 1, d) for d in range(1, 6)],
                "Close": [100.0, 101.0, 99.0, 98.0, 97.0],
            }
        )
        strategy = BuyAndHoldStrategy()

        result = strategy.check_buy(signal_df, 3, date(2020, 1, 4))

        assert result is True

    def test_check_sell_always_false(self) -> None:
        """
        목적: check_sell → 항상 False 반환

        Given: BuyAndHoldStrategy(), 임의 i
        When: check_sell(signal_df, i) 호출
        Then: False 반환
        """
        signal_df = pd.DataFrame(
            {
                "Date": [date(2020, 1, d) for d in range(1, 3)],
                "Close": [100.0, 90.0],
            }
        )
        strategy = BuyAndHoldStrategy()

        result = strategy.check_sell(signal_df, 1)

        assert result is False

    def test_get_buy_meta_returns_empty_dict(self) -> None:
        """
        목적: get_buy_meta() → 빈 dict 반환

        Given: BuyAndHoldStrategy()
        When: check_buy 후 get_buy_meta() 호출
        Then: {} 반환
        """
        signal_df = pd.DataFrame({"Date": [date(2020, 1, 1)], "Close": [100.0]})
        strategy = BuyAndHoldStrategy()

        strategy.check_buy(signal_df, 0, date(2020, 1, 1))
        meta = strategy.get_buy_meta()

        assert meta == {}


# ============================================================================
# SignalStrategy Protocol 준수 확인 테스트
# ============================================================================


class TestSignalStrategyProtocol:
    """SignalStrategy Protocol 준수 확인 테스트."""

    def test_buffer_zone_strategy_is_signal_strategy(self) -> None:
        """
        목적: BufferZoneStrategy가 SignalStrategy Protocol을 준수하는지 확인

        Given: BufferZoneStrategy("ma_200", 0.03, 0.05, 0) 인스턴스
        When: isinstance(strategy, SignalStrategy) 확인
        Then: True 반환
        """
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        assert isinstance(strategy, SignalStrategy)

    def test_buy_and_hold_strategy_is_signal_strategy(self) -> None:
        """
        목적: BuyAndHoldStrategy가 SignalStrategy Protocol을 준수하는지 확인

        Given: BuyAndHoldStrategy() 인스턴스
        When: isinstance(strategy, SignalStrategy) 확인
        Then: True 반환
        """
        strategy = BuyAndHoldStrategy()

        assert isinstance(strategy, SignalStrategy)

    def test_buffer_zone_check_buy_returns_bool(self) -> None:
        """
        목적: BufferZoneStrategy.check_buy()의 반환 타입이 bool인지 확인
              (이전 인터페이스: tuple[bool, HoldState | None] 반환 → 새 인터페이스: bool)

        Given: BufferZoneStrategy("ma_200", 0.03, 0.05, 0), signal_df
        When: check_buy(signal_df, 0, date) 호출
        Then: 반환값이 bool 타입
        """
        signal_df = _make_signal_df()
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 0)

        result = strategy.check_buy(signal_df, 0, date(2020, 1, 1))

        assert isinstance(result, bool)

    def test_buy_and_hold_check_buy_returns_bool(self) -> None:
        """
        목적: BuyAndHoldStrategy.check_buy()의 반환 타입이 bool인지 확인

        Given: BuyAndHoldStrategy(), signal_df
        When: check_buy(signal_df, 0, date) 호출
        Then: 반환값이 bool 타입 (tuple 아님)
        """
        signal_df = pd.DataFrame({"Date": [date(2020, 1, 1)], "Close": [100.0]})
        strategy = BuyAndHoldStrategy()

        result = strategy.check_buy(signal_df, 0, date(2020, 1, 1))

        assert isinstance(result, bool)
        assert result is True
