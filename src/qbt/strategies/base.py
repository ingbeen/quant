"""
추상 기본 전략 클래스

모든 투자 전략의 기본이 되는 추상 클래스를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd


class Strategy(ABC):
    """모든 투자 전략의 기본 추상 클래스"""

    def __init__(self, name: str, initial_capital: float = 10000.0):
        """
        전략 초기화

        Args:
            name: 전략 이름
            initial_capital: 초기 자본금 (기본값: $10,000)
        """
        self.name = name
        self.initial_capital = initial_capital
        self.capital = initial_capital  # 현재 현금 잔고

        # 거래 기록
        self.trades: List[Dict[str, Any]] = []

        # 일별 포트폴리오 가치
        self.portfolio_values: List[float] = []

        # 현재 포지션 (주식 보유량)
        self.positions: Dict[str, float] = {}

        # 수수료율 (매수/매도시 각각 0.1%)
        self.commission_rate = 0.001

        # 백테스트 시작 여부
        self._backtest_started = False

    @abstractmethod
    def check_buy_condition(self, data: pd.Series, current_date: str) -> bool:
        """
        매수 조건 확인

        Args:
            data: 현재 일자의 주가 데이터
            current_date: 현재 날짜

        Returns:
            bool: 매수 조건 충족 시 True
        """
        pass

    @abstractmethod
    def check_sell_condition(self, data: pd.Series, current_date: str) -> bool:
        """
        매도 조건 확인

        Args:
            data: 현재 일자의 주가 데이터
            current_date: 현재 날짜

        Returns:
            bool: 매도 조건 충족 시 True
        """
        pass

    @abstractmethod
    def calculate_position_size(self, data: pd.Series, current_date: str) -> float:
        """
        포지션 크기 계산 (매수할 주식 수량)

        Args:
            data: 현재 일자의 주가 데이터
            current_date: 현재 날짜

        Returns:
            float: 매수할 주식 수량
        """
        pass

    def get_current_position(self, ticker: str) -> float:
        """현재 보유 주식 수량 반환"""
        return self.positions.get(ticker, 0.0)

    def calculate_commission(self, amount: float) -> float:
        """수수료 계산"""
        return amount * self.commission_rate

    def get_portfolio_value(self, ticker: str, current_price: float) -> float:
        """현재 포트폴리오 총 가치 계산"""
        stock_value = self.positions.get(ticker, 0.0) * current_price
        return self.capital + stock_value

    def add_trade(
        self,
        ticker: str,
        action: str,
        date: str,
        price: float,
        quantity: float,
        commission: float,
    ):
        """거래 기록 추가"""
        trade = {
            "ticker": ticker,
            "action": action,
            "date": date,
            "price": price,
            "quantity": quantity,
            "amount": price * quantity,
            "commission": commission,
            "capital_after": self.capital,
            "position_after": self.positions.get(ticker, 0.0),
        }
        self.trades.append(trade)

    def on_buy_executed(self):
        """
        매수 실행 후 호출되는 메서드

        하위 클래스에서 필요한 경우 오버라이드하여 사용
        """
        pass

    def reset(self):
        """전략 상태 초기화"""
        self.capital = self.initial_capital
        self.trades.clear()
        self.portfolio_values.clear()
        self.positions.clear()
        self._backtest_started = False
