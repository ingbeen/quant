"""
계절성 전략

11월-4월 매수, 5월-10월 매도하는 계절성 전략입니다.
"Sell in May and go away" 전략을 구현합니다.
"""

import pandas as pd
from datetime import datetime
from .base import BaseStrategy


class SeasonalStrategy(BaseStrategy):
    """계절성 전략 - 11월-4월 매수, 5월-10월 매도"""

    def __init__(self):
        super().__init__(name="Seasonal")

    def _is_buy_season(self, date_str: str) -> bool:
        """
        매수 시즌인지 확인 (11월-4월)

        Args:
            date_str: 날짜 문자열

        Returns:
            bool: 매수 시즌이면 True
        """
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            month = date.month
            # 11월, 12월, 1월, 2월, 3월, 4월이 매수 시즌
            return month in [11, 12, 1, 2, 3, 4]
        except (ValueError, AttributeError):
            return False

    def _is_sell_season(self, date_str: str) -> bool:
        """
        매도 시즌인지 확인 (5월-10월)

        Args:
            date_str: 날짜 문자열

        Returns:
            bool: 매도 시즌이면 True
        """
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            month = date.month
            # 5월, 6월, 7월, 8월, 9월, 10월이 매도 시즌
            return month in [5, 6, 7, 8, 9, 10]
        except (ValueError, AttributeError):
            return False

    def _is_month_start(self, date_str: str) -> bool:
        """
        월초인지 확인 (매매 신호는 월 단위로 생성)

        Args:
            date_str: 날짜 문자열

        Returns:
            bool: 해당 월의 첫 거래일이면 True
        """
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            return date.day <= 7  # 매월 1-7일을 월초로 간주
        except (ValueError, AttributeError):
            return False

    def check_buy_condition(self, data: pd.Series, current_date: str) -> bool:
        """
        매수 조건: 매수 시즌(11-4월)이고 월초이며 현재 포지션이 없을 때

        Args:
            data: 현재 일자의 주가 데이터
            current_date: 현재 날짜

        Returns:
            bool: 매수 조건 충족 시 True
        """
        ticker = data.get("ticker", "QQQ")  # 기본값으로 QQQ 사용
        current_position = self.get_current_position(ticker)

        return (
            self._is_buy_season(current_date)
            and self._is_month_start(current_date)
            and current_position == 0.0
            and self.capital > 1000
        )  # 최소 $1000 이상 현금 보유 시에만 매수

    def check_sell_condition(self, data: pd.Series, current_date: str) -> bool:
        """
        매도 조건: 매도 시즌(5-10월)이고 월초이며 현재 포지션이 있을 때

        Args:
            data: 현재 일자의 주가 데이터
            current_date: 현재 날짜

        Returns:
            bool: 매도 조건 충족 시 True
        """
        ticker = data.get("ticker", "QQQ")  # 기본값으로 QQQ 사용
        current_position = self.get_current_position(ticker)

        return (
            self._is_sell_season(current_date)
            and self._is_month_start(current_date)
            and current_position > 0.0
        )

    def calculate_position_size(self, data: pd.Series, current_date: str) -> float:
        """
        포지션 크기: 현재 현금의 95%로 매수 (5%는 현금으로 보유)

        Args:
            data: 현재 일자의 주가 데이터
            current_date: 현재 날짜

        Returns:
            float: 매수할 주식 수량
        """
        current_price = data["close"]
        # 현금의 95%로 매수 (수수료 고려)
        available_amount = self.capital * 0.95 / (1 + self.commission_rate)
        quantity = int(available_amount / current_price)
        return float(quantity)
