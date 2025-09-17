"""
백테스팅 엔진

단일 전략의 백테스트 실행을 담당합니다.
"""

import pandas as pd
from typing import Dict, Any, Optional, List, NamedTuple
from datetime import datetime
import sys
from pathlib import Path

from qbt.strategies.base import Strategy
from qbt.core.executor import TradeExecutor


class TradeSignal(NamedTuple):
    """거래 신호 데이터 클래스"""

    action: str  # "BUY" 또는 "SELL"
    ticker: str
    signal_date: str  # 신호 생성일 (종가 기준 판단)
    execution_date: str  # 실행일 (다음날 시가)
    signal_price: float  # 신호 생성 시점의 종가
    execution_price: float  # 실제 실행 가격 (다음날 시가)
    quantity: Optional[float] = None  # 매수 수량 (매도는 None이면 전량)


class BacktestEngine:
    """백테스팅 실행 엔진"""

    def __init__(self) -> None:
        """백테스팅 엔진 초기화"""
        self.executor = TradeExecutor()
        self.pending_signals: List[TradeSignal] = []

    def run_backtest(
        self, strategy: Strategy, data: pd.DataFrame, ticker: str = "QQQ"
    ) -> Dict[str, Any]:
        """
        단일 전략의 백테스트 실행

        Args:
            strategy: 실행할 전략
            data: 주가 데이터
            ticker: 주식 심볼

        Returns:
            dict: 백테스트 결과
        """
        print(f"[ENGINE] {strategy.name} 전략 백테스트 시작...")

        # 전략 초기화
        strategy.reset()
        self.executor.clear_log()
        self.pending_signals.clear()

        # 데이터 검증
        if data.empty:
            raise ValueError("백테스트할 데이터가 없습니다.")

        # 데이터 정렬 (날짜순)
        data = data.sort_values("date").reset_index(drop=True)

        # 일별 데이터 순회
        for idx, (_, row) in enumerate(data.iterrows()):
            current_date = row["date"].strftime("%Y-%m-%d")

            # 시리즈 객체 생성 (전략에서 사용)
            data_series = pd.Series(
                {
                    "ticker": ticker,
                    "date": current_date,
                    "open": row["open"],
                    "close": row["close"],
                    "volume": row["volume"],
                }
            )

            # 1. 먼저 이전 날짜의 신호들을 실행 (다음날 시가로 실행)
            self._execute_pending_signals(strategy, current_date, row["open"])

            # 2. 종가 기준으로 새로운 신호 생성
            next_execution_date = self._get_next_trading_date(data, idx)

            # 매도 조건 확인 (매수보다 먼저 체크)
            if strategy.check_sell_condition(data_series, current_date):
                current_position = strategy.get_current_position(ticker)
                if current_position > 0 and next_execution_date:
                    # 매도 신호 생성 (다음날 실행 예약)
                    signal = TradeSignal(
                        action="SELL",
                        ticker=ticker,
                        signal_date=current_date,
                        execution_date=next_execution_date,
                        signal_price=row["close"],
                        execution_price=0.0,  # 실행 시 업데이트
                        quantity=None,  # 전량 매도
                    )
                    self.pending_signals.append(signal)
                    print(
                        f"[SELL SIGNAL] {current_date}: {current_position:.2f}주 매도 신호 생성 @ ${row['close']:.2f}"
                    )

            # 매수 조건 확인
            if strategy.check_buy_condition(data_series, current_date):
                if next_execution_date:
                    position_size = strategy.calculate_position_size(
                        data_series, current_date
                    )
                    if position_size > 0:
                        # 매수 신호 생성 (다음날 실행 예약)
                        signal = TradeSignal(
                            action="BUY",
                            ticker=ticker,
                            signal_date=current_date,
                            execution_date=next_execution_date,
                            signal_price=row["close"],
                            execution_price=0.0,  # 실행 시 업데이트
                            quantity=position_size,
                        )
                        self.pending_signals.append(signal)
                        print(
                            f"[BUY SIGNAL] {current_date}: {position_size:.2f}주 매수 신호 생성 @ ${row['close']:.2f}"
                        )

            # 일별 포트폴리오 가치 계산
            portfolio_value = strategy.get_portfolio_value(ticker, row["close"])
            strategy.portfolio_values.append(portfolio_value)

        # 마지막 날의 신호들 처리 (마지막 날 종가로 실행)
        if self.pending_signals:
            final_date = data.iloc[-1]["date"].strftime("%Y-%m-%d")
            final_price = data.iloc[-1]["close"]
            self._execute_pending_signals(strategy, final_date, final_price)

        # 백테스트 종료 시 남은 포지션은 마지막 종가로 평가

        # 결과 계산
        results = self._calculate_results(strategy, data, ticker)

        print(f"[ENGINE] {strategy.name} 전략 백테스트 완료")
        return results

    def _get_next_trading_date(self, data: pd.DataFrame, current_idx: int) -> Optional[str]:
        """
        다음 거래일 반환

        Args:
            data: 전체 데이터
            current_idx: 현재 인덱스

        Returns:
            str: 다음 거래일 (없으면 None)
        """
        if current_idx + 1 < len(data):
            return data.iloc[current_idx + 1]["date"].strftime("%Y-%m-%d")
        return None

    def _execute_pending_signals(
        self, strategy: Strategy, execution_date: str, execution_price: float
    ) -> None:
        """
        대기 중인 신호들을 실행

        Args:
            strategy: 전략 인스턴스
            execution_date: 실행 날짜
            execution_price: 실행 가격 (시가)
        """
        # 오늘 실행할 신호들 필터링
        signals_to_execute = [
            signal
            for signal in self.pending_signals
            if signal.execution_date == execution_date
        ]

        # 신호 실행
        for signal in signals_to_execute:
            if signal.action == "SELL":
                result = self.executor.execute_sell(
                    strategy=strategy,
                    ticker=signal.ticker,
                    price=execution_price,
                    quantity=signal.quantity,
                    date=execution_date,
                )
                if result["success"]:
                    print(
                        f"[SELL EXECUTED] {execution_date}: {result['quantity']:.2f}주 @ ${result['price']:.2f} "
                        f"(신호일: {signal.signal_date} @ ${signal.signal_price:.2f})"
                    )

            elif signal.action == "BUY" and signal.quantity is not None:
                result = self.executor.execute_buy(
                    strategy=strategy,
                    ticker=signal.ticker,
                    price=execution_price,
                    quantity=signal.quantity,
                    date=execution_date,
                )
                if result["success"]:
                    print(
                        f"[BUY EXECUTED] {execution_date}: {result['quantity']:.2f}주 @ ${result['price']:.2f} "
                        f"(신호일: {signal.signal_date} @ ${signal.signal_price:.2f})"
                    )

        # 실행된 신호들 제거
        self.pending_signals = [
            signal
            for signal in self.pending_signals
            if signal.execution_date != execution_date
        ]

    def _calculate_results(
        self, strategy: Strategy, data: pd.DataFrame, ticker: str
    ) -> Dict[str, Any]:
        """백테스트 결과 계산"""

        # 기본 정보
        start_date = data.iloc[0]["date"].strftime("%Y-%m-%d")
        end_date = data.iloc[-1]["date"].strftime("%Y-%m-%d")

        # 최종 포트폴리오 가치
        final_value = (
            strategy.portfolio_values[-1]
            if strategy.portfolio_values
            else strategy.initial_capital
        )

        # 총 수익률 계산
        total_return = (
            final_value - strategy.initial_capital
        ) / strategy.initial_capital

        # 일별 수익률 계산
        daily_returns = []
        if len(strategy.portfolio_values) > 1:
            for i in range(1, len(strategy.portfolio_values)):
                daily_return = (
                    strategy.portfolio_values[i] - strategy.portfolio_values[i - 1]
                ) / strategy.portfolio_values[i - 1]
                daily_returns.append(daily_return)

        # 거래 통계
        total_trades = len(strategy.trades)
        buy_trades = [trade for trade in strategy.trades if trade["action"] == "BUY"]
        sell_trades = [trade for trade in strategy.trades if trade["action"] == "SELL"]

        # 승률 계산 (단순화: 매도 거래 중 이익을 본 거래의 비율)
        win_rate = 0.0
        if sell_trades:
            profitable_trades = 0
            for sell_trade in sell_trades:
                # 해당 매도와 연관된 매수 찾기 (단순화: 가장 최근 매수)
                buy_trade = None
                for buy in reversed(buy_trades):
                    if buy["date"] <= sell_trade["date"]:
                        buy_trade = buy
                        break

                if buy_trade and sell_trade["price"] > buy_trade["price"]:
                    profitable_trades += 1

            win_rate = profitable_trades / len(sell_trades)

        # 총 수수료
        total_commission = sum(trade["commission"] for trade in strategy.trades)

        # 결과 딕셔너리 구성
        results = {
            "strategy_name": strategy.name,
            "ticker": ticker,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": strategy.initial_capital,
            "final_value": round(final_value, 2),
            "total_return": round(total_return, 4),
            "total_return_pct": round(total_return * 100, 2),
            "trades": strategy.trades.copy(),
            "daily_returns": daily_returns,
            "portfolio_values": strategy.portfolio_values.copy(),
            "num_trades": total_trades,
            "num_buy_trades": len(buy_trades),
            "num_sell_trades": len(sell_trades),
            "win_rate": round(win_rate, 4),
            "win_rate_pct": round(win_rate * 100, 2),
            "total_commission": round(total_commission, 2),
            "is_benchmark": strategy.is_benchmark,
        }

        return results

    def get_executor_summary(self) -> Dict[str, Any]:
        """실행기 요약 정보 반환"""
        return self.executor.get_execution_summary()
