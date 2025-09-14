"""
QBT (Quant BackTest) - 주식 백테스팅 프레임워크

DuckDB를 데이터 캐싱에, CSV를 Git을 통한 데이터 공유에 사용하는
Python 퀀트 금융 주식 데이터 처리 프로젝트입니다.
"""

from .core.data_loader import DataLoader
from .core.executor import TradeExecutor
from .core.engine import BacktestEngine
from .core.parallel_runner import ParallelRunner

__version__ = "0.1.0"
__all__ = [
    "DataLoader",
    "TradeExecutor",
    "BacktestEngine",
    "ParallelRunner"
]