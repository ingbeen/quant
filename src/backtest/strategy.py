"""
Strategy Engine - 백테스팅 전략 엔진

기본 전략 클래스와 공통 기술적 지표들을 제공
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union, Tuple, Any
from decimal import Decimal
import pandas as pd
import numpy as np
from datetime import date
from dataclasses import dataclass


@dataclass
class Signal:
    """매매 신호"""
    date: date
    symbol: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    price: Decimal
    quantity: Optional[int] = None
    confidence: float = 1.0  # 신호 신뢰도 (0~1)
    reason: str = ""  # 신호 생성 이유


class TechnicalIndicators:
    """기술적 지표 계산 유틸리티"""
    
    @staticmethod
    def sma(prices: pd.Series, window: int) -> pd.Series:
        """단순 이동평균 (Simple Moving Average)"""
        return prices.rolling(window=window).mean()
    
    @staticmethod
    def ema(prices: pd.Series, window: int) -> pd.Series:
        """지수 이동평균 (Exponential Moving Average)"""
        return prices.ewm(span=window).mean()
    
    @staticmethod
    def rsi(prices: pd.Series, window: int = 14) -> pd.Series:
        """상대강도지수 (Relative Strength Index)"""
        delta = prices.diff()
        gain = delta.clip(lower=0).rolling(window=window).mean()
        loss = (-delta).clip(lower=0).rolling(window=window).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    @staticmethod
    def bollinger_bands(prices: pd.Series, window: int = 20, 
                       num_std: float = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """볼린저 밴드 (Bollinger Bands)"""
        sma = prices.rolling(window=window).mean()
        std = prices.rolling(window=window).std()
        
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        
        return upper_band, sma, lower_band
    
    @staticmethod
    def macd(prices: pd.Series, fast: int = 12, slow: int = 26, 
             signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD 지표"""
        ema_fast = TechnicalIndicators.ema(prices, fast)
        ema_slow = TechnicalIndicators.ema(prices, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series,
                   k_window: int = 14, d_window: int = 3) -> Tuple[pd.Series, pd.Series]:
        """스토캐스틱 오실레이터"""
        lowest_low = low.rolling(window=k_window).min()
        highest_high = high.rolling(window=k_window).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_window).mean()
        
        return k_percent, d_percent


class BaseStrategy(ABC):
    """기본 전략 클래스"""
    
    def __init__(self, name: str = "BaseStrategy"):
        self.name = name
        self.parameters: Dict = {}
        self.indicators: Dict[str, pd.Series] = {}
        self.data: Optional[pd.DataFrame] = None
        
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """매매 신호 생성 (구현 필수)"""
        pass
    
    def set_parameters(self, **kwargs: Any) -> None:
        """전략 파라미터 설정"""
        self.parameters.update(kwargs)
    
    def add_indicator(self, name: str, indicator: pd.Series) -> None:
        """기술적 지표 추가"""
        self.indicators[name] = indicator
    
    def prepare_data(self, data: pd.DataFrame) -> None:
        """데이터 전처리 및 지표 계산"""
        self.data = data.copy()
        self.calculate_indicators()
    
    def calculate_indicators(self) -> None:
        """기술적 지표 계산 (하위 클래스에서 오버라이드)"""
        pass
    
    def get_indicator(self, name: str) -> Optional[pd.Series]:
        """지표 조회"""
        return self.indicators.get(name)


class BuyAndHoldStrategy(BaseStrategy):
    """매수 후 보유 전략"""
    
    def __init__(self):
        super().__init__("BuyAndHold")
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        signals = []
        
        if not data.empty:
            # 첫 날에 매수 신호
            first_row = data.iloc[0]
            signals.append(Signal(
                date=pd.to_datetime(first_row['date']).date(),
                symbol=first_row.get('symbol', 'UNKNOWN'),
                action='BUY',
                price=Decimal(str(first_row['close'])),
                reason="Buy and Hold 전략"
            ))
        
        return signals


class SMAStrategy(BaseStrategy):
    """단순 이동평균 크로스 전략"""
    
    def __init__(self, short_window: int = 20, long_window: int = 50):
        super().__init__("SMA_Cross")
        self.set_parameters(short_window=short_window, long_window=long_window)
    
    def calculate_indicators(self) -> None:
        if self.data is None:
            return
        
        short_window = self.parameters.get('short_window', 20)
        long_window = self.parameters.get('long_window', 50)
        
        prices = self.data['close']
        
        self.add_indicator('SMA_short', TechnicalIndicators.sma(prices, short_window))
        self.add_indicator('SMA_long', TechnicalIndicators.sma(prices, long_window))
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        self.prepare_data(data)
        
        signals: List[Signal] = []
        sma_short = self.get_indicator('SMA_short')
        sma_long = self.get_indicator('SMA_long')
        
        if sma_short is None or sma_long is None:
            return signals
        
        # 크로스 포인트 찾기
        for i in range(1, len(data)):
            current_date = pd.to_datetime(data.iloc[i]['date']).date()
            current_price = Decimal(str(data.iloc[i]['close']))
            symbol = data.iloc[i].get('symbol', 'UNKNOWN')
            
            prev_short = float(sma_short.iloc[i-1])
            prev_long = float(sma_long.iloc[i-1])
            curr_short = float(sma_short.iloc[i])
            curr_long = float(sma_long.iloc[i])
            
            # 골든크로스 (매수)
            if prev_short <= prev_long and curr_short > curr_long:
                signals.append(Signal(
                    date=current_date,
                    symbol=symbol,
                    action='BUY',
                    price=current_price,
                    reason=f"골든크로스: SMA{self.parameters['short_window']} > SMA{self.parameters['long_window']}"
                ))
            
            # 데드크로스 (매도)
            elif prev_short >= prev_long and curr_short < curr_long:
                signals.append(Signal(
                    date=current_date,
                    symbol=symbol,
                    action='SELL',
                    price=current_price,
                    reason=f"데드크로스: SMA{self.parameters['short_window']} < SMA{self.parameters['long_window']}"
                ))
        
        return signals


class RSIStrategy(BaseStrategy):
    """RSI 과매수/과매도 전략"""
    
    def __init__(self, rsi_window: int = 14, oversold: float = 30, overbought: float = 70):
        super().__init__("RSI")
        self.set_parameters(
            rsi_window=rsi_window, 
            oversold=oversold, 
            overbought=overbought
        )
    
    def calculate_indicators(self) -> None:
        if self.data is None:
            return
        
        prices = self.data['close']
        rsi_window = self.parameters.get('rsi_window', 14)
        
        self.add_indicator('RSI', TechnicalIndicators.rsi(prices, rsi_window))
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        self.prepare_data(data)
        
        signals: List[Signal] = []
        rsi = self.get_indicator('RSI')
        
        if rsi is None:
            return signals
        
        oversold = self.parameters.get('oversold', 30)
        overbought = self.parameters.get('overbought', 70)
        
        for i in range(1, len(data)):
            current_date = pd.to_datetime(data.iloc[i]['date']).date()
            current_price = Decimal(str(data.iloc[i]['close']))
            symbol = data.iloc[i].get('symbol', 'UNKNOWN')
            
            current_rsi = rsi.iloc[i]
            
            if pd.isna(current_rsi):
                continue
            
            # 과매도에서 반등 (매수)
            if current_rsi < oversold:
                signals.append(Signal(
                    date=current_date,
                    symbol=symbol,
                    action='BUY',
                    price=current_price,
                    confidence=min((oversold - current_rsi) / oversold, 1.0),
                    reason=f"RSI 과매도: {current_rsi:.2f}"
                ))
            
            # 과매수 (매도)
            elif current_rsi > overbought:
                signals.append(Signal(
                    date=current_date,
                    symbol=symbol,
                    action='SELL',
                    price=current_price,
                    confidence=min((current_rsi - overbought) / (100 - overbought), 1.0),
                    reason=f"RSI 과매수: {current_rsi:.2f}"
                ))
        
        return signals


class BollingerBandsStrategy(BaseStrategy):
    """볼린저 밴드 전략"""
    
    def __init__(self, bb_window: int = 20, num_std: float = 2.0):
        super().__init__("BollingerBands")
        self.set_parameters(bb_window=bb_window, num_std=num_std)
    
    def calculate_indicators(self) -> None:
        if self.data is None:
            return
        
        prices = self.data['close']
        bb_window = self.parameters.get('bb_window', 20)
        num_std = self.parameters.get('num_std', 2.0)
        
        upper, middle, lower = TechnicalIndicators.bollinger_bands(prices, bb_window, num_std)
        
        self.add_indicator('BB_upper', upper)
        self.add_indicator('BB_middle', middle)
        self.add_indicator('BB_lower', lower)
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        self.prepare_data(data)
        
        signals: List[Signal] = []
        bb_upper = self.get_indicator('BB_upper')
        bb_lower = self.get_indicator('BB_lower')
        
        if bb_upper is None or bb_lower is None:
            return signals
        
        for i in range(len(data)):
            current_date = pd.to_datetime(data.iloc[i]['date']).date()
            current_price = Decimal(str(data.iloc[i]['close']))
            symbol = data.iloc[i].get('symbol', 'UNKNOWN')
            
            price_float = float(current_price)
            upper_band = bb_upper.iloc[i]
            lower_band = bb_lower.iloc[i]
            
            if pd.isna(upper_band) or pd.isna(lower_band):
                continue
            
            # 하단 밴드 터치 (매수)
            if price_float <= lower_band:
                signals.append(Signal(
                    date=current_date,
                    symbol=symbol,
                    action='BUY',
                    price=current_price,
                    reason=f"볼린저밴드 하단 터치: {price_float:.2f} <= {lower_band:.2f}"
                ))
            
            # 상단 밴드 터치 (매도)
            elif price_float >= upper_band:
                signals.append(Signal(
                    date=current_date,
                    symbol=symbol,
                    action='SELL',
                    price=current_price,
                    reason=f"볼린저밴드 상단 터치: {price_float:.2f} >= {upper_band:.2f}"
                ))
        
        return signals