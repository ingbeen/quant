"""
Portfolio Manager - 포트폴리오 관리 클래스

포지션 관리, 매수/매도 실행, 수수료 계산 등을 담당
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import pandas as pd


@dataclass
class Transaction:
    """거래 기록"""
    date: date
    symbol: str
    side: str  # 'BUY' or 'SELL'
    quantity: int
    price: Decimal
    commission: Decimal = Decimal('0')
    total_cost: Decimal = field(init=False)
    
    def __post_init__(self) -> None:
        self.total_cost = (self.quantity * self.price) + self.commission


@dataclass 
class Position:
    """포지션 정보"""
    symbol: str
    quantity: int = 0
    avg_price: Decimal = Decimal('0')
    total_cost: Decimal = Decimal('0')
    
    def add_shares(self, quantity: int, price: Decimal, commission: Decimal = Decimal('0')) -> None:
        """주식 추가 (매수)"""
        if self.quantity == 0:
            # 첫 매수
            self.quantity = quantity
            self.avg_price = price
            self.total_cost = (quantity * price) + commission
        else:
            # 추가 매수 - 평균단가 계산
            new_total_cost = self.total_cost + (quantity * price) + commission
            new_quantity = self.quantity + quantity
            self.avg_price = new_total_cost / new_quantity
            self.quantity = new_quantity
            self.total_cost = new_total_cost
    
    def remove_shares(self, quantity: int, price: Decimal, commission: Decimal = Decimal('0')) -> Decimal:
        """주식 제거 (매도) - 손익 반환"""
        if quantity > self.quantity:
            raise ValueError(f"매도 수량 {quantity}가 보유 수량 {self.quantity}를 초과합니다")
        
        # 매도 손익 계산
        sell_proceeds = (quantity * price) - commission
        cost_basis = quantity * self.avg_price
        realized_pnl = sell_proceeds - cost_basis
        
        # 포지션 업데이트
        self.quantity -= quantity
        if self.quantity == 0:
            self.total_cost = Decimal('0')
            self.avg_price = Decimal('0')
        else:
            self.total_cost -= cost_basis
        
        return realized_pnl
    
    def get_market_value(self, current_price: Decimal) -> Decimal:
        """현재 시장가치"""
        return self.quantity * current_price
    
    def get_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """미실현 손익"""
        if self.quantity == 0:
            return Decimal('0')
        return self.get_market_value(current_price) - self.total_cost


class Portfolio:
    """포트폴리오 관리자"""
    
    def __init__(self, initial_cash: Decimal = Decimal('100000'), 
                 commission_rate: Decimal = Decimal('0.001')):
        """
        Args:
            initial_cash: 초기 현금
            commission_rate: 수수료율 (기본 0.1%)
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        
        self.positions: Dict[str, Position] = {}
        self.transactions: List[Transaction] = []
        self.daily_values: List[dict] = []
        
    def _calculate_commission(self, quantity: int, price: Decimal) -> Decimal:
        """수수료 계산"""
        trade_value = quantity * price
        commission = trade_value * self.commission_rate
        return commission.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def buy(self, symbol: str, quantity: int, price: Decimal, 
            trade_date: Optional[date] = None) -> bool:
        """매수 주문"""
        if trade_date is None:
            trade_date = date.today()
            
        commission = self._calculate_commission(quantity, price)
        total_cost = (quantity * price) + commission
        
        # 현금 부족 검사
        if total_cost > self.cash:
            return False
        
        # 현금 차감
        self.cash -= total_cost
        
        # 포지션 업데이트
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol)
        
        self.positions[symbol].add_shares(quantity, price, commission)
        
        # 거래 기록
        transaction = Transaction(
            date=trade_date,
            symbol=symbol,
            side='BUY',
            quantity=quantity,
            price=price,
            commission=commission
        )
        self.transactions.append(transaction)
        
        return True
    
    def sell(self, symbol: str, quantity: int, price: Decimal,
             trade_date: Optional[date] = None) -> bool:
        """매도 주문"""
        if trade_date is None:
            trade_date = date.today()
            
        # 포지션 확인
        if symbol not in self.positions or self.positions[symbol].quantity < quantity:
            return False
        
        commission = self._calculate_commission(quantity, price)
        proceeds = (quantity * price) - commission
        
        # 현금 증가
        self.cash += proceeds
        
        # 포지션 업데이트 및 손익 실현
        realized_pnl = self.positions[symbol].remove_shares(quantity, price, commission)
        
        # 빈 포지션 제거
        if self.positions[symbol].quantity == 0:
            del self.positions[symbol]
        
        # 거래 기록
        transaction = Transaction(
            date=trade_date,
            symbol=symbol,
            side='SELL',
            quantity=quantity,
            price=price,
            commission=commission
        )
        self.transactions.append(transaction)
        
        return True
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """포지션 조회"""
        return self.positions.get(symbol)
    
    def get_portfolio_value(self, current_prices: Dict[str, Decimal]) -> Decimal:
        """포트폴리오 총 가치"""
        total_value = self.cash
        
        for symbol, position in self.positions.items():
            if symbol in current_prices:
                total_value += position.get_market_value(current_prices[symbol])
        
        return total_value
    
    def get_positions_summary(self, current_prices: Dict[str, Decimal]) -> pd.DataFrame:
        """포지션 요약"""
        if not self.positions:
            return pd.DataFrame()
        
        positions_data = []
        for symbol, position in self.positions.items():
            current_price = current_prices.get(symbol, Decimal('0'))
            market_value = position.get_market_value(current_price)
            unrealized_pnl = position.get_unrealized_pnl(current_price)
            
            positions_data.append({
                'Symbol': symbol,
                'Quantity': position.quantity,
                'Avg_Price': float(position.avg_price),
                'Current_Price': float(current_price),
                'Market_Value': float(market_value),
                'Cost_Basis': float(position.total_cost),
                'Unrealized_PnL': float(unrealized_pnl),
                'Return_Pct': float(unrealized_pnl / position.total_cost * 100) if position.total_cost > 0 else 0
            })
        
        return pd.DataFrame(positions_data)
    
    def get_transactions_df(self) -> pd.DataFrame:
        """거래 내역 DataFrame"""
        if not self.transactions:
            return pd.DataFrame()
        
        transactions_data = []
        for tx in self.transactions:
            transactions_data.append({
                'Date': tx.date,
                'Symbol': tx.symbol,
                'Side': tx.side,
                'Quantity': tx.quantity,
                'Price': float(tx.price),
                'Commission': float(tx.commission),
                'Total_Cost': float(tx.total_cost)
            })
        
        return pd.DataFrame(transactions_data)
    
    def record_daily_value(self, date: date, current_prices: Dict[str, Decimal]) -> None:
        """일별 포트폴리오 가치 기록"""
        portfolio_value = self.get_portfolio_value(current_prices)
        
        self.daily_values.append({
            'date': date,
            'cash': float(self.cash),
            'portfolio_value': float(portfolio_value),
            'positions_count': len(self.positions)
        })
    
    def get_performance_summary(self) -> dict:
        """성과 요약"""
        if not self.daily_values:
            return {}
        
        df = pd.DataFrame(self.daily_values)
        
        initial_value = float(self.initial_cash)
        current_value = df['portfolio_value'].iloc[-1]
        
        total_return = (current_value - initial_value) / initial_value
        
        # 일별 수익률 계산
        df['daily_return'] = df['portfolio_value'].pct_change()
        
        return {
            'initial_value': initial_value,
            'current_value': current_value,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'daily_returns_std': df['daily_return'].std(),
            'max_value': df['portfolio_value'].max(),
            'min_value': df['portfolio_value'].min(),
            'trading_days': len(df)
        }
    
    def reset(self) -> None:
        """포트폴리오 초기화"""
        self.cash = self.initial_cash
        self.positions.clear()
        self.transactions.clear()
        self.daily_values.clear()