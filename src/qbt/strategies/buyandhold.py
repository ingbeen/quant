"""
Buy & Hold 전략

첫날 전액 매수 후 보유만 하는 벤치마크 전략입니다.
"""

import pandas as pd
from .base import Strategy


class BuyAndHoldStrategy(Strategy):
    """Buy & Hold 전략 - 벤치마크용"""

    def __init__(self):
        super().__init__(name="BuyAndHold")
        self._initial_buy_done = False

    def check_buy_condition(self, data: pd.Series, current_date: str) -> bool:
        """
        매수 조건: 백테스트 시작 첫날에만 매수

        Args:
            data: 현재 일자의 주가 데이터
            current_date: 현재 날짜

        Returns:
            bool: 첫날이면 True, 그 외는 False
        """
        return not self._initial_buy_done

    def check_sell_condition(self, data: pd.Series, current_date: str) -> bool:
        """
        매도 조건: Buy & Hold는 중간에 매도하지 않음

        Args:
            data: 현재 일자의 주가 데이터
            current_date: 현재 날짜

        Returns:
            bool: 항상 False (매도하지 않음)
        """
        return False

    def calculate_position_size(self, data: pd.Series, current_date: str) -> float:
        """
        포지션 크기: 첫날 전액 매수

        Args:
            data: 현재 일자의 주가 데이터
            current_date: 현재 날짜

        Returns:
            float: 매수할 주식 수량 (전액 매수)
        """
        if not self._initial_buy_done:
            current_price = data["close"]
            # 수수료를 제외한 금액으로 최대한 매수
            available_amount = self.capital / (1 + self.commission_rate)
            quantity = int(available_amount / current_price)
            return float(quantity)
        return 0.0

    def on_buy_executed(self):
        """매수 실행 후 호출되는 메서드"""
        self._initial_buy_done = True

    def reset(self):
        """전략 상태 초기화"""
        super().reset()
        self._initial_buy_done = False
