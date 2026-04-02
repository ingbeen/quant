"""엔진 공통 모듈(engine_common.py) 계약 테스트

execute_buy_order, execute_sell_order, create_trade_record, record_equity 함수의 계약을 고정한다.
"""

from datetime import date

import pytest

from qbt.backtest.engines.engine_common import (
    create_trade_record,
    execute_sell_order,
)


class TestExecuteSellOrder:
    """execute_sell_order 계약 테스트.

    순수 계산 함수 시그니처: execute_sell_order(open_price, shares_to_sell, entry_price)
    -> (sell_price, proceeds, pnl, pnl_pct)
    """

    def test_execute_sell_order_pnl_calculation(self) -> None:
        """
        목적: 매도 체결 후 pnl 계산 정확성 확인 (슬리피지 적용)

        Given: 진입가 95.0, 시가 100.0, 10주
        When: execute_sell_order(100.0, 10, 95.0) 호출 (슬리피지 -0.3%)
        Then: 매도가 = 100.0 * (1 - 0.003) = 99.7, pnl = (99.7 - 95.0) * 10 = 47.0
        """
        # When
        sell_price, proceeds, pnl, pnl_pct = execute_sell_order(100.0, 10, 95.0)

        # Then: 슬리피지 적용 매도가 = 100.0 * (1 - 0.003) = 99.7
        assert sell_price == pytest.approx(99.7, abs=1e-6)
        assert pnl == pytest.approx((99.7 - 95.0) * 10, abs=0.01)

    def test_execute_sell_order_proceeds(self) -> None:
        """
        목적: 매도 대금이 shares * sell_price와 일치하는지 검증

        Given: 시가 100.0, 10주, 진입가 95.0
        When: execute_sell_order 호출
        Then: proceeds = 10 * sell_price
        """
        # When
        sell_price, proceeds, _, _ = execute_sell_order(100.0, 10, 95.0)

        # Then
        assert proceeds == pytest.approx(10 * sell_price, abs=0.01)

    def test_create_trade_record_preserves_hold_days(self) -> None:
        """
        목적: create_trade_record에 hold_days_used를 전달하면
              반환된 trade_record["hold_days_used"]에 그 값이 그대로 담기는지 검증

        Given: hold_days_used=5
        When: create_trade_record(..., hold_days_used=5) 호출
        Then: trade_record["hold_days_used"] == 5
        """
        # When
        trade_record = create_trade_record(
            entry_date=date(2020, 1, 5),
            exit_date=date(2020, 1, 11),
            entry_price=95.0,
            exit_price=99.7,
            shares=10,
            pnl=47.0,
            pnl_pct=0.0495,
            buy_buffer_pct=0.03,
            hold_days_used=5,
        )

        # Then
        assert trade_record["hold_days_used"] == 5


class TestExecuteBuyOrderPure:
    """execute_buy_order 순수 계산 함수 계약 테스트.

    Phase 2에서 함수 시그니처가 변경된 후 GREEN으로 전환된다.
    변경 후 시그니처: execute_buy_order(open_price, amount) -> (shares, buy_price, cost)
    """

    def test_execute_buy_order_pure_calculation(self) -> None:
        """
        목적: 순수 계산 함수가 올바른 (shares, buy_price, cost) 튜플을 반환하는지 검증

        Given: open_price=100.0, amount=10000.0
        When: execute_buy_order(100.0, 10000.0) 호출
        Then: buy_price = 100 * 1.003 = 100.3
              shares = int(10000 / 100.3) = 99
              cost = 99 * 100.3 = 9929.7
        """
        from qbt.backtest.engines.engine_common import execute_buy_order

        # When
        shares, buy_price, cost = execute_buy_order(100.0, 10000.0)

        # Then
        assert buy_price == pytest.approx(100.3, abs=1e-6), "슬리피지 +0.3% 적용"
        expected_shares = int(10000.0 / 100.3)
        assert shares == expected_shares, f"체결 수량 = int(10000 / 100.3) = {expected_shares}"
        assert cost == pytest.approx(shares * buy_price, abs=1e-6), "총 비용 = shares * buy_price"

    def test_execute_buy_order_insufficient_funds(self) -> None:
        """
        목적: 금액이 buy_price보다 작을 때 shares=0, cost=0.0 반환

        Given: open_price=1000.0, amount=50.0 (1주도 못 삼)
        When: execute_buy_order 호출
        Then: shares=0, cost=0.0
        """
        from qbt.backtest.engines.engine_common import execute_buy_order

        # When
        shares, buy_price, cost = execute_buy_order(1000.0, 50.0)

        # Then
        assert shares == 0
        assert cost == 0.0
        assert buy_price > 0, "buy_price는 항상 양수 (슬리피지 적용)"


class TestExecuteSellOrderPure:
    """execute_sell_order 순수 계산 함수 계약 테스트.

    Phase 2에서 함수 시그니처가 변경된 후 GREEN으로 전환된다.
    변경 후 시그니처: execute_sell_order(open_price, shares_to_sell, entry_price)
                      -> (sell_price, proceeds, pnl, pnl_pct)
    """

    def test_execute_sell_order_pure_calculation(self) -> None:
        """
        목적: 순수 계산 함수가 올바른 (sell_price, proceeds, pnl, pnl_pct) 반환

        Given: open_price=100.0, shares_to_sell=10, entry_price=95.0
        When: execute_sell_order(100.0, 10, 95.0) 호출
        Then: sell_price = 100 * 0.997 = 99.7
              proceeds = 10 * 99.7 = 997.0
              pnl = (99.7 - 95.0) * 10 = 47.0
              pnl_pct = (99.7 - 95.0) / 95.0
        """
        from qbt.backtest.engines.engine_common import execute_sell_order

        # When
        sell_price, proceeds, pnl, pnl_pct = execute_sell_order(100.0, 10, 95.0)

        # Then
        assert sell_price == pytest.approx(99.7, abs=1e-6), "슬리피지 -0.3% 적용"
        assert proceeds == pytest.approx(10 * 99.7, abs=0.01), "매도 대금 = shares * sell_price"
        assert pnl == pytest.approx((99.7 - 95.0) * 10, abs=0.01), "손익 = (sell-entry) * shares"
        assert pnl_pct == pytest.approx((99.7 - 95.0) / 95.0, abs=1e-6), "손익률 = (sell-entry) / entry"

    def test_execute_sell_order_partial_sell(self) -> None:
        """
        목적: 부분 매도 시 정확한 계산 검증 (포트폴리오 REDUCE_TO_TARGET용)

        Given: open_price=100.0, shares_to_sell=5 (전체 포지션의 일부), entry_price=90.0
        When: execute_sell_order(100.0, 5, 90.0) 호출
        Then: pnl = (sell_price - 90.0) * 5, proceeds = 5 * sell_price
        """
        from qbt.backtest.engines.engine_common import execute_sell_order

        # When
        sell_price, proceeds, pnl, pnl_pct = execute_sell_order(100.0, 5, 90.0)

        # Then
        assert proceeds == pytest.approx(5 * sell_price, abs=0.01)
        assert pnl == pytest.approx((sell_price - 90.0) * 5, abs=0.01)
        assert pnl_pct == pytest.approx((sell_price - 90.0) / 90.0, abs=1e-6)

    def test_pnl_pct_no_epsilon_in_denominator(self) -> None:
        """
        목적: pnl_pct 분모에 EPSILON이 없음을 확인 (리포트 2-1 통일)

        정책: pnl_pct = (sell_price - entry_price) / entry_price
              entry_price가 0인 것은 비정상 상태이므로 EPSILON 방어 불필요

        Given: entry_price=100.0 (정확한 값)
        When: execute_sell_order 호출
        Then: pnl_pct == (sell_price - 100.0) / 100.0 (EPSILON 없이)
        """
        from qbt.backtest.engines.engine_common import execute_sell_order

        # When
        sell_price, _, _, pnl_pct = execute_sell_order(100.0, 10, 100.0)

        # Then: 정확한 나눗셈 (EPSILON 없음)
        expected_pnl_pct = (sell_price - 100.0) / 100.0
        assert pnl_pct == pytest.approx(
            expected_pnl_pct, abs=1e-12
        ), "pnl_pct는 (sell-entry)/entry 정확히 일치해야 함 (EPSILON 없음)"


class TestCreateTradeRecord:
    """create_trade_record 헬퍼 함수 계약 테스트."""

    def test_create_trade_record_returns_valid_typed_dict(self) -> None:
        """
        목적: create_trade_record가 올바른 TradeRecord TypedDict를 반환하는지 검증

        Given: 유효한 거래 정보
        When: create_trade_record 호출
        Then: 모든 필드가 올바른 값으로 설정된 TradeRecord 반환
        """
        from qbt.backtest.engines.engine_common import create_trade_record

        # When
        record = create_trade_record(
            entry_date=date(2020, 1, 5),
            exit_date=date(2020, 1, 11),
            entry_price=95.0,
            exit_price=99.7,
            shares=10,
            pnl=47.0,
            pnl_pct=0.0495,
            buy_buffer_pct=0.03,
            hold_days_used=3,
        )

        # Then
        assert record["entry_date"] == date(2020, 1, 5)
        assert record["exit_date"] == date(2020, 1, 11)
        assert record["entry_price"] == 95.0
        assert record["exit_price"] == 99.7
        assert record["shares"] == 10
        assert record["pnl"] == pytest.approx(47.0, abs=0.01)
        assert record["pnl_pct"] == pytest.approx(0.0495, abs=1e-6)
        assert record["buy_buffer_pct"] == pytest.approx(0.03, abs=1e-6)
        assert record["hold_days_used"] == 3

    def test_create_trade_record_default_values(self) -> None:
        """
        목적: buy_buffer_pct, hold_days_used 기본값 검증 (B&H 전략용)

        Given: buy_buffer_pct, hold_days_used 생략
        When: create_trade_record 호출
        Then: buy_buffer_pct=0.0, hold_days_used=0
        """
        from qbt.backtest.engines.engine_common import create_trade_record

        # When
        record = create_trade_record(
            entry_date=date(2020, 1, 1),
            exit_date=date(2020, 2, 1),
            entry_price=100.0,
            exit_price=110.0,
            shares=5,
            pnl=50.0,
            pnl_pct=0.1,
        )

        # Then
        assert record["buy_buffer_pct"] == 0.0
        assert record["hold_days_used"] == 0
