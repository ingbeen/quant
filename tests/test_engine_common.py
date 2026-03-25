"""엔진 공통 모듈(engine_common.py) 계약 테스트

execute_buy_order, execute_sell_order, record_equity 함수의 계약을 고정한다.
"""

from datetime import date

import pytest

from qbt.backtest.engines.engine_common import PendingOrder, execute_sell_order


class TestExecuteSellOrder:
    """execute_sell_order 계약 테스트."""

    def test_execute_sell_order_hold_days_used_param(self) -> None:
        """
        목적: execute_sell_order에 hold_days_used 파라미터를 전달하면
              반환된 trade_record["hold_days_used"]에 그 값이 그대로 담기는지 검증
              (암묵적 0 하드코딩 제거 후 명시적 전달 계약)

        Given: 유효한 매도 주문과 포지션 정보, hold_days_used=5
        When: execute_sell_order(..., hold_days_used=5) 호출
        Then: trade_record["hold_days_used"] == 5
        """
        # Given
        order = PendingOrder(
            order_type="sell",
            signal_date=date(2020, 1, 10),
        )
        open_price = 100.0
        execute_date = date(2020, 1, 11)
        capital = 0.0
        position = 10
        entry_price = 95.0
        entry_date = date(2020, 1, 5)
        hold_days_used = 5

        # When
        new_position, new_capital, trade_record = execute_sell_order(
            order=order,
            open_price=open_price,
            execute_date=execute_date,
            capital=capital,
            position=position,
            entry_price=entry_price,
            entry_date=entry_date,
            hold_days_used=hold_days_used,
        )

        # Then
        assert trade_record["hold_days_used"] == 5

    def test_execute_sell_order_returns_zero_position(self) -> None:
        """
        목적: 매도 후 포지션이 0으로 초기화되는지 확인

        Given: 포지션 10주 보유 상태
        When: execute_sell_order 호출
        Then: new_position == 0
        """
        # Given
        order = PendingOrder(
            order_type="sell",
            signal_date=date(2020, 1, 10),
        )

        # When
        new_position, new_capital, trade_record = execute_sell_order(
            order=order,
            open_price=100.0,
            execute_date=date(2020, 1, 11),
            capital=0.0,
            position=10,
            entry_price=95.0,
            entry_date=date(2020, 1, 5),
            hold_days_used=3,
        )

        # Then
        assert new_position == 0

    def test_execute_sell_order_pnl_calculation(self) -> None:
        """
        목적: 매도 체결 후 pnl 계산 정확성 확인 (슬리피지 적용)

        Given: 진입가 95.0, 시가 100.0, 10주
        When: execute_sell_order 호출 (슬리피지 -0.3%)
        Then: 매도가 = 100.0 * (1 - 0.003) = 99.7, pnl = (99.7 - 95.0) * 10 = 47.0
        """
        # Given
        order = PendingOrder(
            order_type="sell",
            signal_date=date(2020, 1, 10),
        )

        # When
        _, _, trade_record = execute_sell_order(
            order=order,
            open_price=100.0,
            execute_date=date(2020, 1, 11),
            capital=0.0,
            position=10,
            entry_price=95.0,
            entry_date=date(2020, 1, 5),
            hold_days_used=3,
        )

        # Then: 슬리피지 적용 매도가 = 100.0 * (1 - 0.003) = 99.7
        assert trade_record["exit_price"] == pytest.approx(99.7, abs=1e-6)
        assert trade_record["pnl"] == pytest.approx((99.7 - 95.0) * 10, abs=0.01)
