"""
Position Sizer 모듈

다양한 포지션 사이징 전략을 제공합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd


class PositionSizer(ABC):
    """포지션 사이징 추상 기본 클래스"""

    @abstractmethod
    def calculate_position_size(
        self,
        available_capital: float,
        current_price: float,
        commission_rate: float,
        portfolio_value: Optional[float] = None,
        **kwargs,
    ) -> float:
        """
        포지션 크기 계산

        Args:
            available_capital: 사용 가능한 자본금
            current_price: 현재 주가
            commission_rate: 수수료율
            portfolio_value: 전체 포트폴리오 가치 (일부 전략에서 사용)
            **kwargs: 추가 파라미터

        Returns:
            float: 매수할 주식 수량
        """
        pass


class MaxCapitalSizer(PositionSizer):
    """수수료를 고려하여 최대한 매수하는 포지션 사이저"""

    def calculate_position_size(
        self,
        available_capital: float,
        current_price: float,
        commission_rate: float,
        portfolio_value: Optional[float] = None,
        **kwargs,
    ) -> float:
        """
        수수료를 고려한 최대 매수 수량 계산

        Args:
            available_capital: 사용 가능한 자본금
            current_price: 현재 주가
            commission_rate: 수수료율
            portfolio_value: 사용하지 않음
            **kwargs: 추가 파라미터

        Returns:
            float: 매수할 주식 수량
        """
        if available_capital <= 0 or current_price <= 0:
            return 0.0

        # 수수료를 고려한 실제 사용 가능 금액
        effective_capital = available_capital / (1 + commission_rate)
        quantity = int(effective_capital / current_price)
        return float(quantity)


class CashPercentSizer(PositionSizer):
    """현재 현금의 일정 비율로 매수하는 포지션 사이저"""

    def __init__(self, percent: float = 1.0):
        """
        초기화

        Args:
            percent: 현금 대비 사용 비율 (0.0 ~ 1.0)
        """
        if not 0.0 <= percent <= 1.0:
            raise ValueError("percent는 0.0과 1.0 사이의 값이어야 합니다.")
        self.percent = percent

    def calculate_position_size(
        self,
        available_capital: float,
        current_price: float,
        commission_rate: float,
        portfolio_value: Optional[float] = None,
        **kwargs,
    ) -> float:
        """
        현금의 일정 비율로 매수할 수량 계산

        Args:
            available_capital: 사용 가능한 자본금
            current_price: 현재 주가
            commission_rate: 수수료율
            portfolio_value: 사용하지 않음
            **kwargs: 추가 파라미터

        Returns:
            float: 매수할 주식 수량
        """
        if available_capital <= 0 or current_price <= 0:
            return 0.0

        # 현금의 지정된 비율만 사용
        target_amount = available_capital * self.percent
        effective_capital = target_amount / (1 + commission_rate)
        quantity = int(effective_capital / current_price)
        return float(quantity)


class PortfolioPercentSizer(PositionSizer):
    """전체 포트폴리오 가치의 일정 비율로 매수하는 포지션 사이저"""

    def __init__(self, percent: float = 1.0):
        """
        초기화

        Args:
            percent: 포트폴리오 대비 사용 비율 (0.0 ~ 1.0)
        """
        if not 0.0 <= percent <= 1.0:
            raise ValueError("percent는 0.0과 1.0 사이의 값이어야 합니다.")
        self.percent = percent

    def calculate_position_size(
        self,
        available_capital: float,
        current_price: float,
        commission_rate: float,
        portfolio_value: Optional[float] = None,
        **kwargs,
    ) -> float:
        """
        포트폴리오 가치의 일정 비율로 매수할 수량 계산

        Args:
            available_capital: 사용 가능한 자본금
            current_price: 현재 주가
            commission_rate: 수수료율
            portfolio_value: 전체 포트폴리오 가치
            **kwargs: 추가 파라미터

        Returns:
            float: 매수할 주식 수량
        """
        if available_capital <= 0 or current_price <= 0:
            return 0.0

        # 포트폴리오 가치가 제공되지 않으면 현금 잔고를 사용
        if portfolio_value is None:
            portfolio_value = available_capital

        # 포트폴리오의 지정된 비율만큼 목표 금액 설정
        target_amount = portfolio_value * self.percent

        # 사용 가능한 현금을 넘지 않도록 제한
        target_amount = min(target_amount, available_capital)

        effective_capital = target_amount / (1 + commission_rate)
        quantity = int(effective_capital / current_price)
        return float(quantity)


class FixedAmountSizer(PositionSizer):
    """고정 금액으로 매수하는 포지션 사이저"""

    def __init__(self, amount: float):
        """
        초기화

        Args:
            amount: 고정 매수 금액
        """
        if amount <= 0:
            raise ValueError("amount는 0보다 큰 값이어야 합니다.")
        self.amount = amount

    def calculate_position_size(
        self,
        available_capital: float,
        current_price: float,
        commission_rate: float,
        portfolio_value: Optional[float] = None,
        **kwargs,
    ) -> float:
        """
        고정 금액으로 매수할 수량 계산

        Args:
            available_capital: 사용 가능한 자본금
            current_price: 현재 주가
            commission_rate: 수수료율
            portfolio_value: 사용하지 않음
            **kwargs: 추가 파라미터

        Returns:
            float: 매수할 주식 수량
        """
        if available_capital <= 0 or current_price <= 0:
            return 0.0

        # 고정 금액이 사용 가능한 자본을 넘지 않도록 제한
        target_amount = min(self.amount, available_capital)
        effective_capital = target_amount / (1 + commission_rate)
        quantity = int(effective_capital / current_price)
        return float(quantity)