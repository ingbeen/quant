"""
매매 실행기

실제 매수/매도 실행, 수수료 계산, 포지션 관리를 담당합니다.
"""

import pandas as pd
from typing import Dict, Any, Optional, List, Union
import sys
from pathlib import Path

from qbt.strategies.base import Strategy
from qbt.types import ExecutionResult, ExecutionError, ExecutionSummary, ActionType


class TradeExecutor:
    """매매 실행 및 포지션 관리 클래스"""

    def __init__(self) -> None:
        """매매 실행기 초기화"""
        self.execution_log: List[ExecutionResult] = []

    def execute_buy(
        self,
        strategy: Strategy,
        ticker: str,
        price: float,
        quantity: float,
        date: str,
    ) -> Union[ExecutionResult, ExecutionError]:
        """
        매수 실행

        Args:
            strategy: 전략 인스턴스
            ticker: 주식 심볼
            price: 매수 가격
            quantity: 매수 수량
            date: 실행 날짜

        Returns:
            dict: 실행 결과
        """
        if quantity <= 0:
            return {
                "success": False,
                "error": "매수 수량은 0보다 커야 합니다.",
                "quantity": 0,
                "amount": 0,
                "commission": 0,
            }

        # 거래 금액 계산
        trade_amount = price * quantity

        # 수수료 계산 (0.1%)
        commission = strategy.calculate_commission(trade_amount)

        # 총 필요 금액 (거래금액 + 수수료)
        total_required = trade_amount + commission

        # 잔고 확인
        if strategy.capital < total_required:
            return {
                "success": False,
                "error": f"잔고 부족: 필요 ${total_required:.2f}, 보유 ${strategy.capital:.2f}",
                "quantity": 0,
                "amount": 0,
                "commission": 0,
            }

        # 매수 실행
        strategy.capital -= total_required
        current_position = strategy.positions.get(ticker, 0.0)
        strategy.positions[ticker] = current_position + quantity

        # 거래 기록 추가
        strategy.add_trade(
            ticker=ticker,
            action="BUY",
            date=date,
            price=price,
            quantity=quantity,
            commission=commission,
        )

        # 매수 실행 후 전략별 후처리
        strategy.on_buy_executed()

        # 실행 로그 기록
        execution_result: ExecutionResult = {
            "success": True,
            "action": "BUY",
            "ticker": ticker,
            "date": date,
            "price": price,
            "quantity": quantity,
            "amount": trade_amount,
            "commission": commission,
            "total_cost": total_required,
            "capital_after": strategy.capital,
            "position_after": strategy.positions.get(ticker, 0.0),
        }

        self.execution_log.append(execution_result)
        return execution_result

    def execute_sell(
        self,
        strategy: Strategy,
        ticker: str,
        price: float,
        quantity: Optional[float],
        date: str,
    ) -> Union[ExecutionResult, ExecutionError]:
        """
        매도 실행

        Args:
            strategy: 전략 인스턴스
            ticker: 주식 심볼
            price: 매도 가격
            quantity: 매도 수량 (None이면 전량 매도)
            date: 실행 날짜

        Returns:
            dict: 실행 결과
        """
        current_position = strategy.positions.get(ticker, 0.0)

        if current_position <= 0:
            return {
                "success": False,
                "error": "매도할 주식이 없습니다.",
                "quantity": 0,
                "amount": 0,
                "commission": 0,
            }

        # 매도 수량 결정 (None이면 전량 매도)
        if quantity is None:
            sell_quantity = current_position
        else:
            sell_quantity = min(quantity, current_position)

        if sell_quantity <= 0:
            return {
                "success": False,
                "error": "매도 수량은 0보다 커야 합니다.",
                "quantity": 0,
                "amount": 0,
                "commission": 0,
            }

        # 거래 금액 계산
        trade_amount = price * sell_quantity

        # 수수료 계산 (0.1%)
        commission = strategy.calculate_commission(trade_amount)

        # 실제 수령 금액 (거래금액 - 수수료)
        net_proceeds = trade_amount - commission

        # 매도 실행
        strategy.capital += net_proceeds
        strategy.positions[ticker] = current_position - sell_quantity

        # 포지션이 0이 되면 딕셔너리에서 제거
        if strategy.positions[ticker] <= 0.001:  # 부동소수점 오차 고려
            strategy.positions[ticker] = 0.0

        # 거래 기록 추가
        strategy.add_trade(
            ticker=ticker,
            action="SELL",
            date=date,
            price=price,
            quantity=sell_quantity,
            commission=commission,
        )

        # 실행 로그 기록
        execution_result: ExecutionResult = {
            "success": True,
            "action": "SELL",
            "ticker": ticker,
            "date": date,
            "price": price,
            "quantity": sell_quantity,
            "amount": trade_amount,
            "commission": commission,
            "total_cost": net_proceeds,  # SELL의 경우 total_cost는 net_proceeds와 동일
            "capital_after": strategy.capital,
            "position_after": strategy.positions.get(ticker, 0.0),
        }

        self.execution_log.append(execution_result)
        return execution_result

    def get_execution_log(self) -> List[ExecutionResult]:
        """실행 로그 반환"""
        return self.execution_log.copy()

    def clear_log(self) -> None:
        """실행 로그 초기화"""
        self.execution_log.clear()

    def get_execution_summary(self) -> ExecutionSummary:
        """실행 요약 정보 반환"""
        if not self.execution_log:
            return {
                "total_executions": 0,
                "buy_count": 0,
                "sell_count": 0,
                "total_commission": 0.0,
            }

        buy_count = sum(1 for log in self.execution_log if log["action"] == "BUY")
        sell_count = sum(1 for log in self.execution_log if log["action"] == "SELL")
        total_commission = sum(log["commission"] for log in self.execution_log)

        return {
            "total_executions": len(self.execution_log),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "total_commission": round(total_commission, 2),
        }
