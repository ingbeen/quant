"""
백테스팅 엔진

단일 전략의 백테스트 실행을 담당합니다.
"""

import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가 (상대 임포트 문제 해결)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from strategies.base import BaseStrategy
from backtesting.executor import TradeExecutor


class BacktestEngine:
    """백테스팅 실행 엔진"""

    def __init__(self):
        """백테스팅 엔진 초기화"""
        self.executor = TradeExecutor()

    def run_backtest(self, strategy: BaseStrategy, data: pd.DataFrame,
                     ticker: str = "QQQ") -> Dict[str, Any]:
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

        # 데이터 검증
        if data.empty:
            raise ValueError("백테스트할 데이터가 없습니다.")

        # 데이터 정렬 (날짜순)
        data = data.sort_values('date').reset_index(drop=True)

        # 일별 데이터 순회
        for idx, row in data.iterrows():
            current_date = row['date'].strftime('%Y-%m-%d')

            # 시리즈 객체 생성 (전략에서 사용)
            data_series = pd.Series({
                'ticker': ticker,
                'date': current_date,
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'adj_close': row['adj_close'],
                'volume': row['volume']
            })

            # 매도 조건 확인 (매수보다 먼저 체크)
            if strategy.check_sell_condition(data_series, current_date):
                current_position = strategy.get_current_position(ticker)
                if current_position > 0:
                    # 전량 매도
                    result = self.executor.execute_sell(
                        strategy=strategy,
                        ticker=ticker,
                        price=row['close'],
                        quantity=None,  # 전량 매도
                        date=current_date
                    )
                    if result["success"]:
                        print(f"[SELL] {current_date}: {result['quantity']:.2f}주 @ ${result['price']:.2f}")

            # 매수 조건 확인
            if strategy.check_buy_condition(data_series, current_date):
                position_size = strategy.calculate_position_size(data_series, current_date)
                if position_size > 0:
                    result = self.executor.execute_buy(
                        strategy=strategy,
                        ticker=ticker,
                        price=row['close'],
                        quantity=position_size,
                        date=current_date
                    )
                    if result["success"]:
                        print(f"[BUY] {current_date}: {result['quantity']:.2f}주 @ ${result['price']:.2f}")

            # 일별 포트폴리오 가치 계산
            portfolio_value = strategy.get_portfolio_value(ticker, row['close'])
            strategy.portfolio_values.append(portfolio_value)

        # 백테스트 종료 시 남은 포지션 정리 (선택사항)
        final_position = strategy.get_current_position(ticker)
        if final_position > 0:
            final_date = data.iloc[-1]['date'].strftime('%Y-%m-%d')
            final_price = data.iloc[-1]['close']

            result = self.executor.execute_sell(
                strategy=strategy,
                ticker=ticker,
                price=final_price,
                quantity=None,  # 전량 매도
                date=final_date
            )
            if result["success"]:
                print(f"[FINAL SELL] {final_date}: {result['quantity']:.2f}주 @ ${result['price']:.2f}")

        # 결과 계산
        results = self._calculate_results(strategy, data, ticker)

        print(f"[ENGINE] {strategy.name} 전략 백테스트 완료")
        return results

    def _calculate_results(self, strategy: BaseStrategy, data: pd.DataFrame,
                          ticker: str) -> Dict[str, Any]:
        """백테스트 결과 계산"""

        # 기본 정보
        start_date = data.iloc[0]['date'].strftime('%Y-%m-%d')
        end_date = data.iloc[-1]['date'].strftime('%Y-%m-%d')

        # 최종 포트폴리오 가치
        final_value = strategy.portfolio_values[-1] if strategy.portfolio_values else strategy.initial_capital

        # 총 수익률 계산
        total_return = (final_value - strategy.initial_capital) / strategy.initial_capital

        # 일별 수익률 계산
        daily_returns = []
        if len(strategy.portfolio_values) > 1:
            for i in range(1, len(strategy.portfolio_values)):
                daily_return = (strategy.portfolio_values[i] - strategy.portfolio_values[i-1]) / strategy.portfolio_values[i-1]
                daily_returns.append(daily_return)

        # 거래 통계
        total_trades = len(strategy.trades)
        buy_trades = [trade for trade in strategy.trades if trade['action'] == 'BUY']
        sell_trades = [trade for trade in strategy.trades if trade['action'] == 'SELL']

        # 승률 계산 (단순화: 매도 거래 중 이익을 본 거래의 비율)
        win_rate = 0.0
        if sell_trades:
            profitable_trades = 0
            for sell_trade in sell_trades:
                # 해당 매도와 연관된 매수 찾기 (단순화: 가장 최근 매수)
                buy_trade = None
                for buy in reversed(buy_trades):
                    if buy['date'] <= sell_trade['date']:
                        buy_trade = buy
                        break

                if buy_trade and sell_trade['price'] > buy_trade['price']:
                    profitable_trades += 1

            win_rate = profitable_trades / len(sell_trades)

        # 총 수수료
        total_commission = sum(trade['commission'] for trade in strategy.trades)

        # 결과 딕셔너리 구성
        results = {
            'strategy_name': strategy.name,
            'ticker': ticker,
            'start_date': start_date,
            'end_date': end_date,
            'initial_capital': strategy.initial_capital,
            'final_value': round(final_value, 2),
            'total_return': round(total_return, 4),
            'total_return_pct': round(total_return * 100, 2),
            'trades': strategy.trades.copy(),
            'daily_returns': daily_returns,
            'portfolio_values': strategy.portfolio_values.copy(),
            'num_trades': total_trades,
            'num_buy_trades': len(buy_trades),
            'num_sell_trades': len(sell_trades),
            'win_rate': round(win_rate, 4),
            'win_rate_pct': round(win_rate * 100, 2),
            'total_commission': round(total_commission, 2),
            'is_benchmark': strategy.name == "BuyAndHold"
        }

        return results

    def get_executor_summary(self) -> Dict[str, Any]:
        """실행기 요약 정보 반환"""
        return self.executor.get_execution_summary()