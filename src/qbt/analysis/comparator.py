"""
전략 비교 분석

여러 전략의 성과를 비교하고 분석합니다.
(현재는 구조만 구현하고 실제 비교 메서드는 주석 처리)
"""

from typing import Dict, Any, List, Optional
import pandas as pd
from .metrics import PerformanceMetrics
from qbt.types import BacktestResultWithExcess, ComparisonResult, StrategyComparison


class StrategyComparator:
    """전략 비교 분석 클래스"""

    def __init__(
        self,
        results: Dict[str, BacktestResultWithExcess],
        benchmark_name: Optional[str] = None,
    ):
        """
        전략 비교기 초기화

        Args:
            results: 전략별 백테스팅 결과
            benchmark_name: 벤치마크로 사용할 전략 이름 (None이면 자동 탐지)
        """
        self.results = results

        # 벤치마크 이름이 제공되지 않으면 자동으로 탐지
        if benchmark_name is None:
            self.benchmark_name = self._find_benchmark_name()
        else:
            self.benchmark_name = benchmark_name

        self.benchmark = results.get(self.benchmark_name) if self.benchmark_name else None

        if self.benchmark is None:
            print(f"[WARNING] 벤치마크 '{self.benchmark_name}'를 찾을 수 없습니다.")

    def _find_benchmark_name(self) -> Optional[str]:
        """
        벤치마크 전략 이름을 자동으로 찾기

        Returns:
            Optional[str]: 벤치마크 전략 이름
        """
        for name, result in self.results.items():
            if result["is_benchmark"]:
                return name

        # 벤치마크를 찾지 못한 경우 None 반환
        return None

    # def compare_returns(self) -> pd.DataFrame:
    #     """전략별 수익률 비교 테이블 생성"""
    #     comparison_data = []
    #
    #     for strategy_name, result in self.results.items():
    #         metrics = PerformanceMetrics(result)
    #
    #         data_row = {
    #             'Strategy': strategy_name,
    #             'Total_Return_Pct': result.get('total_return_pct', 0.0),
    #             'Excess_Return_Pct': result.get('excess_return_pct', 0.0),
    #             'Num_Trades': result.get('num_trades', 0),
    #             'Win_Rate_Pct': result.get('win_rate_pct', 0.0),
    #             'Total_Commission': result.get('total_commission', 0.0),
    #             'Is_Benchmark': result.get('is_benchmark', False)
    #         }
    #
    #         comparison_data.append(data_row)
    #
    #     df = pd.DataFrame(comparison_data)
    #
    #     # 벤치마크를 첫 번째로, 나머지는 수익률 순으로 정렬
    #     benchmark_rows = df[df['Is_Benchmark'] == True]
    #     other_rows = df[df['Is_Benchmark'] == False].sort_values(
    #         'Total_Return_Pct', ascending=False
    #     )
    #
    #     result_df = pd.concat([benchmark_rows, other_rows], ignore_index=True)
    #     return result_df

    # def compare_vs_benchmark(self) -> Dict[str, Any]:
    #     """벤치마크 대비 성과 비교"""
    #     if self.benchmark is None:
    #         return {"error": "벤치마크를 찾을 수 없습니다."}
    #
    #     benchmark_return = self.benchmark.get('total_return', 0.0)
    #     benchmark_trades = self.benchmark.get('num_trades', 0)
    #
    #     comparisons = {}
    #
    #     for strategy_name, result in self.results.items():
    #         if strategy_name == self.benchmark_name:
    #             continue
    #
    #         strategy_return = result.get('total_return', 0.0)
    #         strategy_trades = result.get('num_trades', 0)
    #
    #         excess_return = strategy_return - benchmark_return
    #         return_ratio = strategy_return / benchmark_return if benchmark_return != 0 else 0
    #
    #         comparisons[strategy_name] = {
    #             'excess_return': excess_return,
    #             'excess_return_pct': excess_return * 100,
    #             'return_ratio': return_ratio,
    #             'outperformed': excess_return > 0,
    #             'trade_difference': strategy_trades - benchmark_trades
    #         }
    #
    #     return {
    #         'benchmark_name': self.benchmark_name,
    #         'benchmark_return_pct': benchmark_return * 100,
    #         'benchmark_trades': benchmark_trades,
    #         'comparisons': comparisons
    #     }

    # def compare_risk_metrics(self) -> pd.DataFrame:
    #     """위험 지표 비교"""
    #     risk_data = []
    #
    #     for strategy_name, result in self.results.items():
    #         metrics = PerformanceMetrics(result)
    #
    #         data_row = {
    #             'Strategy': strategy_name,
    #             'Total_Return_Pct': result.get('total_return_pct', 0.0),
    #             'Max_Drawdown_Pct': 0.0,  # metrics.calculate_mdd() * 100,
    #             'Sharpe_Ratio': 0.0,      # metrics.calculate_sharpe(),
    #             'Profit_Factor': 0.0,     # metrics.calculate_profit_factor(),
    #             'CAGR_Pct': 0.0,         # metrics.calculate_cagr() * 100,
    #             'Win_Rate_Pct': result.get('win_rate_pct', 0.0)
    #         }
    #
    #         risk_data.append(data_row)
    #
    #     df = pd.DataFrame(risk_data)
    #     return df.sort_values('Sharpe_Ratio', ascending=False)

    def get_basic_comparison(self) -> ComparisonResult:
        """기본 비교 정보 반환"""
        strategies_info: Dict[str, StrategyComparison] = {}

        for strategy_name, result in self.results.items():
            strategies_info[strategy_name] = {
                "total_return_pct": result["total_return_pct"],
                "num_trades": result["num_trades"],
                "win_rate_pct": result["win_rate_pct"],
                "total_commission": result["total_commission"],
                "excess_return_pct": result["excess_return_pct"],
                "is_benchmark": result["is_benchmark"],
            }

        return {
            "benchmark_name": self.benchmark_name,
            "num_strategies": len(self.results),
            "strategies": strategies_info,
        }
