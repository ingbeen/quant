"""
Backtesting Engine - 백테스트 실행 엔진

전략, 포트폴리오, 데이터를 연결하여 백테스트를 실행
"""

from typing import Dict, List, Optional
from datetime import date
from decimal import Decimal
import pandas as pd
from dataclasses import dataclass, field

from .portfolio import Portfolio
from .strategy import BaseStrategy, Signal
from .data_handler import DataHandler


@dataclass
class BacktestConfig:
    """백테스트 설정"""

    initial_cash: Decimal = Decimal("100000")
    commission_rate: Decimal = Decimal("0.001")  # 0.1%
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    position_size_type: str = "percent"  # 'percent', 'fixed', 'equal_weight'
    position_size_value: float = 0.95  # 95% 투자 또는 고정 금액
    max_positions: int = 5  # 최대 동시 보유 종목 수
    rebalance_frequency: str = "signal"  # 'signal', 'daily', 'weekly', 'monthly'


@dataclass
class BacktestResult:
    """백테스트 결과"""

    config: BacktestConfig
    portfolio_history: List[dict] = field(default_factory=list)
    transactions: List[dict] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)
    executed_signals: List[Signal] = field(default_factory=list)
    metrics: Dict = field(default_factory=dict)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    total_days: int = 0


class BacktestEngine:
    """백테스트 실행 엔진"""

    def __init__(self, data_handler: DataHandler):
        """
        Args:
            data_handler: 데이터 핸들러 인스턴스
        """
        self.data_handler = data_handler

    def run_backtest(
        self,
        strategy: BaseStrategy,
        symbol: str,
        config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:
        """
        단일 종목 백테스트 실행

        Args:
            strategy: 백테스트 전략
            symbol: 대상 종목
            config: 백테스트 설정

        Returns:
            백테스트 결과
        """
        if config is None:
            config = BacktestConfig()

        # 데이터 로드
        data = self.data_handler.load_stock_data(
            symbol=symbol, start_date=config.start_date, end_date=config.end_date
        )

        if data.empty:
            raise ValueError(f"데이터를 로드할 수 없습니다: {symbol}")

        # 포트폴리오 초기화
        portfolio = Portfolio(
            initial_cash=config.initial_cash, commission_rate=config.commission_rate
        )

        # 백테스트 결과 초기화
        result = BacktestResult(config=config)
        result.start_date = data["date"].min().date()
        result.end_date = data["date"].max().date()
        result.total_days = len(data)

        print(f"[INFO] 백테스트 시작: {strategy.name}")
        print(f"[INFO] 종목: {symbol}")
        print(
            f"[INFO] 기간: {result.start_date} ~ {result.end_date} ({result.total_days}일)"
        )
        print(f"[INFO] 초기 자금: ${config.initial_cash:,}")

        # 신호 생성
        signals = strategy.generate_signals(data)
        result.signals = signals

        print(f"[INFO] 생성된 신호: {len(signals)}개")

        # 일별 백테스트 실행
        current_position = 0

        for idx, row in data.iterrows():
            current_date = row["date"].date()
            current_price = Decimal(str(row["close"]))

            # 해당 날짜의 신호 확인
            day_signals = [s for s in signals if s.date == current_date]

            for signal in day_signals:
                executed = self._execute_signal(
                    signal=signal,
                    portfolio=portfolio,
                    current_price=current_price,
                    config=config,
                    current_position=current_position,
                )

                if executed:
                    result.executed_signals.append(signal)
                    if signal.action == "BUY":
                        current_position += signal.quantity or 0
                    elif signal.action == "SELL":
                        current_position -= signal.quantity or 0

            # 일별 포트폴리오 가치 기록
            portfolio.record_daily_value(current_date, {symbol: current_price})

        # 거래 내역 저장
        result.transactions = portfolio.get_transactions_df().to_dict("records")
        result.portfolio_history = portfolio.daily_values

        print(f"[SUCCESS] 백테스트 완료!")
        print(f"[INFO] 총 거래 횟수: {len(result.executed_signals)}")
        print(
            f"[INFO] 실행된 신호: 매수 {len([s for s in result.executed_signals if s.action == 'BUY'])}개, "
            f"매도 {len([s for s in result.executed_signals if s.action == 'SELL'])}개"
        )

        return result

    def _execute_signal(
        self,
        signal: Signal,
        portfolio: Portfolio,
        current_price: Decimal,
        config: BacktestConfig,
        current_position: int = 0,
    ) -> bool:
        """
        신호 실행

        Returns:
            실행 성공 여부
        """
        if signal.action == "BUY":
            return self._execute_buy_signal(signal, portfolio, config)
        elif signal.action == "SELL":
            return self._execute_sell_signal(
                signal, portfolio, config, current_position
            )
        else:  # HOLD
            return False

    def _execute_buy_signal(
        self, signal: Signal, portfolio: Portfolio, config: BacktestConfig
    ) -> bool:
        """매수 신호 실행"""

        # 수량 계산
        if signal.quantity:
            quantity = signal.quantity
        else:
            quantity = self._calculate_position_size(
                signal.price, portfolio.cash, config
            )

        if quantity <= 0:
            return False

        # 실제 매수 실행
        success = portfolio.buy(
            symbol=signal.symbol,
            quantity=quantity,
            price=signal.price,
            trade_date=signal.date,
        )

        if success:
            signal.quantity = quantity

        return success

    def _execute_sell_signal(
        self,
        signal: Signal,
        portfolio: Portfolio,
        config: BacktestConfig,
        current_position: int,
    ) -> bool:
        """매도 신호 실행"""

        position = portfolio.get_position(signal.symbol)
        if not position or position.quantity <= 0:
            return False

        # 수량 계산
        if signal.quantity:
            quantity = min(signal.quantity, position.quantity)
        else:
            quantity = position.quantity  # 전량 매도

        if quantity <= 0:
            return False

        # 실제 매도 실행
        success = portfolio.sell(
            symbol=signal.symbol,
            quantity=quantity,
            price=signal.price,
            trade_date=signal.date,
        )

        if success:
            signal.quantity = quantity

        return success

    def _calculate_position_size(
        self, price: Decimal, available_cash: Decimal, config: BacktestConfig
    ) -> int:
        """포지션 크기 계산"""

        if config.position_size_type == "percent":
            # 사용 가능 현금의 일정 비율
            target_amount = available_cash * Decimal(str(config.position_size_value))

        elif config.position_size_type == "fixed":
            # 고정 금액
            target_amount = Decimal(str(config.position_size_value))
            target_amount = min(target_amount, available_cash)

        else:  # equal_weight
            # 동일 비중 (최대 포지션 수로 나누어)
            target_amount = available_cash / config.max_positions

        # 수수료 고려
        commission_rate = config.commission_rate
        effective_price = price * (1 + commission_rate)

        quantity = int(target_amount / effective_price)

        return max(0, quantity)

    def run_multi_symbol_backtest(
        self,
        strategy: BaseStrategy,
        symbols: List[str],
        config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:
        """
        다중 종목 백테스트 실행

        Args:
            strategy: 백테스트 전략
            symbols: 대상 종목들
            config: 백테스트 설정

        Returns:
            백테스트 결과
        """
        if config is None:
            config = BacktestConfig()

        print(f"[INFO] 다중 종목 백테스트 시작: {strategy.name}")
        print(f"[INFO] 종목 수: {len(symbols)}")

        # 모든 종목의 데이터를 통합 로드
        all_data = []
        for symbol in symbols:
            data = self.data_handler.load_stock_data(
                symbol=symbol, start_date=config.start_date, end_date=config.end_date
            )
            if not data.empty:
                data["symbol"] = symbol
                all_data.append(data)

        if not all_data:
            raise ValueError("로드할 수 있는 데이터가 없습니다")

        # 데이터 병합 및 정렬
        combined_data = pd.concat(all_data, ignore_index=True)
        combined_data = combined_data.sort_values(["date", "symbol"])

        # 포트폴리오 초기화
        portfolio = Portfolio(
            initial_cash=config.initial_cash, commission_rate=config.commission_rate
        )

        # 백테스트 결과 초기화
        result = BacktestResult(config=config)
        result.start_date = combined_data["date"].min().date()
        result.end_date = combined_data["date"].max().date()

        # 각 종목별로 신호 생성
        all_signals = []
        for symbol in symbols:
            symbol_data = combined_data[combined_data["symbol"] == symbol].copy()
            if not symbol_data.empty:
                signals = strategy.generate_signals(symbol_data)
                all_signals.extend(signals)

        # 날짜순으로 신호 정렬
        all_signals.sort(key=lambda x: x.date)
        result.signals = all_signals

        print(f"[INFO] 생성된 신호: {len(all_signals)}개")

        # 날짜별 백테스트 실행
        unique_dates = sorted(combined_data["date"].dt.date.unique())

        for current_date in unique_dates:
            # 해당 날짜의 가격 정보
            day_data = combined_data[combined_data["date"].dt.date == current_date]
            current_prices = {
                row["symbol"]: Decimal(str(row["close"]))
                for _, row in day_data.iterrows()
            }

            # 해당 날짜의 신호 실행
            day_signals = [s for s in all_signals if s.date == current_date]

            for signal in day_signals:
                if signal.symbol in current_prices:
                    executed = self._execute_signal(
                        signal=signal,
                        portfolio=portfolio,
                        current_price=current_prices[signal.symbol],
                        config=config,
                    )

                    if executed:
                        result.executed_signals.append(signal)

            # 일별 포트폴리오 가치 기록
            portfolio.record_daily_value(current_date, current_prices)

        # 거래 내역 저장
        result.transactions = portfolio.get_transactions_df().to_dict("records")
        result.portfolio_history = portfolio.daily_values

        print(f"[SUCCESS] 다중 종목 백테스트 완료!")
        print(f"[INFO] 총 거래 횟수: {len(result.executed_signals)}")

        return result
