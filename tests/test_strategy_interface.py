"""SignalStrategy Protocol 계약 테스트

BufferZoneStrategy, BuyAndHoldStrategy가 SignalStrategy Protocol을 준수하는지 검증한다.
check_buy/check_sell의 실제 동작 계약을 고정한다.
"""

from datetime import date

import pytest

from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.buy_and_hold import BuyAndHoldStrategy
from qbt.backtest.strategies.strategy_common import HoldState, SignalStrategy


class TestBufferZoneStrategyInterface:
    """BufferZoneStrategy 인터페이스 계약 테스트."""

    def test_check_buy_no_signal_when_below_band(self) -> None:
        """
        목적: 종가가 상단 밴드 아래일 때 매수 신호 없음 확인

        Given: BufferZoneStrategy 인스턴스, 종가 < 상단 밴드 조건
        When: check_buy를 호출할 때
        Then: (False, None) 반환
        """
        # Given
        strategy = BufferZoneStrategy()

        # When
        buy, hold_state = strategy.check_buy(
            prev_close=99.0,
            cur_close=100.0,
            prev_upper=102.0,
            cur_upper=102.0,
            hold_state=None,
            hold_days_required=0,
            current_date=date(2020, 1, 1),
            buy_buffer_pct=0.03,
        )

        # Then
        assert buy is False
        assert hold_state is None

    def test_check_buy_signal_on_breakout(self) -> None:
        """
        목적: 상향돌파 시 매수 신호 확인 (hold_days=0)

        Given: BufferZoneStrategy 인스턴스, 전일 <= 상단밴드 < 당일 조건
        When: check_buy를 호출할 때 (hold_days_required=0)
        Then: (True, None) 반환
        """
        # Given
        strategy = BufferZoneStrategy()

        # When: 전일 종가 <= 상단밴드, 당일 종가 > 상단밴드 (상향돌파)
        buy, hold_state = strategy.check_buy(
            prev_close=101.0,
            cur_close=103.0,
            prev_upper=102.0,
            cur_upper=102.0,
            hold_state=None,
            hold_days_required=0,
            current_date=date(2020, 1, 1),
            buy_buffer_pct=0.03,
        )

        # Then
        assert buy is True
        assert hold_state is None

    def test_check_buy_hold_days_state_machine_first_breakout(self) -> None:
        """
        목적: hold_days > 0 시 상태머신 동작 확인 (첫 돌파 후 대기)

        Given: BufferZoneStrategy 인스턴스, 첫 돌파 감지
        When: check_buy를 hold_days_required=3으로 호출
        Then: (False, HoldState) — 즉시 매수하지 않고 대기 상태 생성
        """
        # Given
        strategy = BufferZoneStrategy()

        # When: 상향돌파 감지, hold_days_required=3
        buy, hold_state = strategy.check_buy(
            prev_close=101.0,
            cur_close=103.0,
            prev_upper=102.0,
            cur_upper=102.0,
            hold_state=None,
            hold_days_required=3,
            current_date=date(2020, 1, 1),
            buy_buffer_pct=0.03,
        )

        # Then: 즉시 매수하지 않고 HoldState 생성
        assert buy is False
        assert hold_state is not None
        assert hold_state["hold_days_required"] == 3
        assert hold_state["days_passed"] == 0

    def test_check_buy_hold_days_state_machine_ongoing(self) -> None:
        """
        목적: hold_days 대기 중 유지 상태에서 days_passed 증가 확인

        Given: 대기 중인 HoldState (days_passed=1, hold_days_required=3)
        When: 상단밴드 위 유지 조건에서 check_buy 호출
        Then: (False, updated_hold_state) — days_passed=2
        """
        # Given
        strategy = BufferZoneStrategy()
        existing_hold_state: HoldState = {
            "start_date": __import__("datetime").date(2020, 1, 1),
            "days_passed": 1,
            "buffer_pct": 0.03,
            "hold_days_required": 3,
        }

        # When: 상단밴드 위 유지 (cur_close=103.0 > cur_upper=102.0)
        buy, updated_hold_state = strategy.check_buy(
            prev_close=103.0,
            cur_close=103.0,
            prev_upper=102.0,
            cur_upper=102.0,
            hold_state=existing_hold_state,
            hold_days_required=3,
            current_date=date(2020, 1, 2),
            buy_buffer_pct=0.03,
        )

        # Then: 아직 대기 중, days_passed 증가
        assert buy is False
        assert updated_hold_state is not None
        assert updated_hold_state["days_passed"] == 2

    def test_check_buy_hold_days_state_machine_trigger(self) -> None:
        """
        목적: hold_days 충족 시 매수 신호 발생 확인

        Given: 대기 중인 HoldState (days_passed=2, hold_days_required=3)
        When: 상단밴드 위 유지 조건에서 check_buy 호출 (마지막 날)
        Then: (True, None) — 매수 신호 발생
        """
        # Given
        strategy = BufferZoneStrategy()
        existing_hold_state: HoldState = {
            "start_date": __import__("datetime").date(2020, 1, 1),
            "days_passed": 2,
            "buffer_pct": 0.03,
            "hold_days_required": 3,
        }

        # When: days_passed(2) + 1 = 3 >= hold_days_required(3) → 매수
        buy, new_hold_state = strategy.check_buy(
            prev_close=103.0,
            cur_close=103.0,
            prev_upper=102.0,
            cur_upper=102.0,
            hold_state=existing_hold_state,
            hold_days_required=3,
            current_date=date(2020, 1, 3),
            buy_buffer_pct=0.03,
        )

        # Then: 매수 신호
        assert buy is True
        assert new_hold_state is None

    def test_check_buy_hold_days_state_machine_cancel(self) -> None:
        """
        목적: hold_days 대기 중 상단밴드 아래 이탈 시 상태 해제 확인

        Given: 대기 중인 HoldState
        When: 상단밴드 아래로 이탈 (cur_close <= cur_upper)
        Then: (False, None) — 상태 해제
        """
        # Given
        strategy = BufferZoneStrategy()
        existing_hold_state: HoldState = {
            "start_date": __import__("datetime").date(2020, 1, 1),
            "days_passed": 1,
            "buffer_pct": 0.03,
            "hold_days_required": 3,
        }

        # When: 상단밴드 아래 이탈 (cur_close=100.0 <= cur_upper=102.0)
        buy, new_hold_state = strategy.check_buy(
            prev_close=103.0,
            cur_close=100.0,
            prev_upper=102.0,
            cur_upper=102.0,
            hold_state=existing_hold_state,
            hold_days_required=3,
            current_date=date(2020, 1, 2),
            buy_buffer_pct=0.03,
        )

        # Then: 상태 해제
        assert buy is False
        assert new_hold_state is None

    def test_check_sell_signal_on_breakdown(self) -> None:
        """
        목적: 하향돌파 시 매도 신호 확인

        Given: BufferZoneStrategy 인스턴스, 전일 >= 하단밴드 > 당일 조건
        When: check_sell을 호출할 때
        Then: True 반환
        """
        # Given
        strategy = BufferZoneStrategy()

        # When: 전일 종가 >= 하단밴드, 당일 종가 < 하단밴드 (하향돌파)
        sell = strategy.check_sell(
            prev_close=99.0,
            cur_close=97.0,
            prev_lower=98.0,
            cur_lower=98.0,
        )

        # Then
        assert sell is True

    def test_check_sell_no_signal_when_above_band(self) -> None:
        """
        목적: 종가가 하단 밴드 위일 때 매도 신호 없음 확인

        Given: BufferZoneStrategy 인스턴스, 종가 > 하단 밴드 조건
        When: check_sell을 호출할 때
        Then: False 반환
        """
        # Given
        strategy = BufferZoneStrategy()

        # When
        sell = strategy.check_sell(
            prev_close=100.0,
            cur_close=100.0,
            prev_lower=98.0,
            cur_lower=98.0,
        )

        # Then
        assert sell is False

    def test_check_buy_first_breakout_start_date_is_current_date(self) -> None:
        """
        목적: 첫 돌파 감지 시 반환된 hold_state["start_date"]가 전달한 current_date와 일치하는지 검증
              (플레이스홀더 date.min 방지)

        Given: BufferZoneStrategy, 상향돌파 조건, current_date=date(2020, 6, 15)
        When: check_buy를 hold_days_required=3, current_date=date(2020,6,15), buy_buffer_pct=0.03으로 호출
        Then: hold_state["start_date"] == date(2020, 6, 15) (플레이스홀더 date.min이 아님)
        """
        # Given
        strategy = BufferZoneStrategy()
        current_date = date(2020, 6, 15)

        # When: 상향돌파 + hold_days > 0 → HoldState 생성
        buy, hold_state = strategy.check_buy(
            prev_close=101.0,
            cur_close=103.0,
            prev_upper=102.0,
            cur_upper=102.0,
            hold_state=None,
            hold_days_required=3,
            current_date=current_date,
            buy_buffer_pct=0.03,
        )

        # Then
        assert buy is False
        assert hold_state is not None
        assert hold_state["start_date"] == current_date  # date.min이 아닌 실제 날짜

    def test_check_buy_first_breakout_buffer_pct_is_correct(self) -> None:
        """
        목적: 첫 돌파 감지 시 반환된 hold_state["buffer_pct"]가 전달한 buy_buffer_pct와 일치하는지 검증
              (플레이스홀더 0.0 방지)

        Given: BufferZoneStrategy, 상향돌파 조건, buy_buffer_pct=0.03
        When: check_buy를 hold_days_required=3, current_date=date(2020,6,15), buy_buffer_pct=0.03으로 호출
        Then: hold_state["buffer_pct"] == 0.03 (플레이스홀더 0.0이 아님)
        """
        # Given
        strategy = BufferZoneStrategy()
        buy_buffer_pct = 0.03

        # When: 상향돌파 + hold_days > 0 → HoldState 생성
        buy, hold_state = strategy.check_buy(
            prev_close=101.0,
            cur_close=103.0,
            prev_upper=102.0,
            cur_upper=102.0,
            hold_state=None,
            hold_days_required=3,
            current_date=date(2020, 6, 15),
            buy_buffer_pct=buy_buffer_pct,
        )

        # Then
        assert buy is False
        assert hold_state is not None
        assert hold_state["buffer_pct"] == pytest.approx(buy_buffer_pct, abs=1e-12)


class TestBuyAndHoldStrategyInterface:
    """BuyAndHoldStrategy 인터페이스 계약 테스트."""

    def test_check_buy_always_true(self) -> None:
        """
        목적: 어떤 조건에서도 항상 (True, None) 반환 확인

        Given: BuyAndHoldStrategy 인스턴스, 임의 입력값
        When: check_buy를 호출할 때
        Then: (True, None) 반환
        """
        # Given
        strategy = BuyAndHoldStrategy()

        # When: 밴드 아래 종가 (버퍼존이라면 매수 신호 없음)
        buy, hold_state = strategy.check_buy(
            prev_close=99.0,
            cur_close=100.0,
            prev_upper=105.0,
            cur_upper=105.0,
            hold_state=None,
            hold_days_required=0,
            current_date=date(2020, 1, 1),
            buy_buffer_pct=0.03,
        )

        # Then: B&H는 항상 매수
        assert buy is True
        assert hold_state is None

    def test_check_buy_always_true_with_hold_days(self) -> None:
        """
        목적: hold_days_required > 0 이어도 항상 (True, None) 반환 확인

        Given: BuyAndHoldStrategy 인스턴스
        When: check_buy를 hold_days_required=3으로 호출할 때
        Then: (True, None) 반환 (hold_days 무시)
        """
        # Given
        strategy = BuyAndHoldStrategy()

        # When
        buy, hold_state = strategy.check_buy(
            prev_close=99.0,
            cur_close=100.0,
            prev_upper=105.0,
            cur_upper=105.0,
            hold_state=None,
            hold_days_required=3,
            current_date=date(2020, 1, 1),
            buy_buffer_pct=0.03,
        )

        # Then
        assert buy is True
        assert hold_state is None

    def test_check_sell_always_false(self) -> None:
        """
        목적: 어떤 조건에서도 항상 False 반환 확인 (하향돌파 조건이어도)

        Given: BuyAndHoldStrategy 인스턴스, 하향돌파 조건
        When: check_sell을 호출할 때
        Then: False 반환
        """
        # Given
        strategy = BuyAndHoldStrategy()

        # When: 하향돌파 조건 (버퍼존이라면 매도 신호)
        sell = strategy.check_sell(
            prev_close=99.0,
            cur_close=97.0,
            prev_lower=98.0,
            cur_lower=98.0,
        )

        # Then: B&H는 절대 매도 안 함
        assert sell is False


class TestSignalStrategyProtocol:
    """SignalStrategy Protocol 준수 확인 테스트."""

    def test_buffer_zone_strategy_is_signal_strategy(self) -> None:
        """
        목적: BufferZoneStrategy가 SignalStrategy Protocol을 준수하는지 확인

        Given: BufferZoneStrategy 인스턴스
        When: isinstance(strategy, SignalStrategy) 확인
        Then: True 반환 (Protocol 구조적 준수)
        """
        # Given
        strategy = BufferZoneStrategy()

        # When / Then
        assert isinstance(strategy, SignalStrategy)

    def test_buy_and_hold_strategy_is_signal_strategy(self) -> None:
        """
        목적: BuyAndHoldStrategy가 SignalStrategy Protocol을 준수하는지 확인

        Given: BuyAndHoldStrategy 인스턴스
        When: isinstance(strategy, SignalStrategy) 확인
        Then: True 반환 (Protocol 구조적 준수)
        """
        # Given
        strategy = BuyAndHoldStrategy()

        # When / Then
        assert isinstance(strategy, SignalStrategy)

    def test_day0_check_buy_pattern_bah_returns_true(self) -> None:
        """
        목적: day 0 패턴 (prev==cur, 상단밴드 아래) 호출 시 B&H는 True 반환 확인

        Given: BuyAndHoldStrategy 인스턴스
        When: prev==cur 데이터로 check_buy를 호출할 때
        Then: (True, None) 반환 (B&H는 항상 매수)
        """
        # Given
        strategy = BuyAndHoldStrategy()

        # When
        buy, hold_state = strategy.check_buy(
            prev_close=100.0,
            cur_close=100.0,  # prev == cur (day 0 패턴)
            prev_upper=103.0,
            cur_upper=103.0,
            hold_state=None,
            hold_days_required=0,
            current_date=date(2020, 1, 1),
            buy_buffer_pct=0.03,
        )

        # Then
        assert buy is True
        assert hold_state is None

    def test_day0_check_buy_pattern_buffer_zone_returns_false(self) -> None:
        """
        목적: day 0 패턴 (prev==cur, 상단밴드 조건 불성립) 호출 시 BufferZone은 False 반환 확인

        Given: BufferZoneStrategy 인스턴스
        When: prev==cur 데이터로 check_buy를 호출할 때 (cur_close < cur_upper)
        Then: (False, None) 반환 (상향돌파 조건 불성립)
        """
        # Given
        strategy = BufferZoneStrategy()

        # When: prev_close == cur_close == 100.0, upper_band == 103.0
        # 상향돌파 조건: prev_close <= prev_upper AND cur_close > cur_upper
        # 100 <= 103 이고 100 > 103이 False → 상향돌파 불성립
        buy, hold_state = strategy.check_buy(
            prev_close=100.0,
            cur_close=100.0,
            prev_upper=103.0,
            cur_upper=103.0,
            hold_state=None,
            hold_days_required=0,
            current_date=date(2020, 1, 1),
            buy_buffer_pct=0.03,
        )

        # Then
        assert buy is False
        assert hold_state is None
