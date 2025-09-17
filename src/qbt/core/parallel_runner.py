"""
병렬 백테스팅 실행기

여러 전략을 병렬로 실행하고 결과를 수집합니다.
"""

import pandas as pd
from typing import List, Dict, Any, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import sys
from pathlib import Path

from qbt.strategies.base import Strategy
from qbt.core.data_loader import DataLoader
from qbt.core.engine import BacktestEngine
from qbt.types import (
    BacktestResult,
    BacktestResultWithExcess,
    StrategyTaskData,
    FailedStrategy,
)


def run_single_strategy(strategy_data: StrategyTaskData) -> BacktestResult:
    """
    단일 전략 실행 함수 (병렬 처리용)

    Args:
        strategy_data: 전략 실행에 필요한 데이터

    Returns:
        BacktestResult: 백테스트 결과
    """
    try:
        # 전략 재생성 (pickle 직렬화 문제 해결)
        strategy_class = strategy_data["strategy_class"]
        strategy_args = strategy_data.get("strategy_args", {})
        strategy = strategy_class(**strategy_args)

        # 데이터 복사
        data = strategy_data["data"].copy()
        ticker = strategy_data["ticker"]

        # 백테스팅 엔진 생성 및 실행
        engine = BacktestEngine()
        result = engine.run_backtest(strategy, data, ticker)

        print(f"[PARALLEL] {strategy.name} 전략 완료")
        return result

    except Exception as e:
        print(f"[ERROR] 전략 실행 중 오류: {e}")
        # 에러 발생 시 기본 BacktestResult 구조로 반환
        raise Exception(f"Strategy execution failed: {e}")


class ParallelRunner:
    """병렬 백테스팅 실행기"""

    def __init__(self, max_workers: Optional[int] = None):
        """
        병렬 실행기 초기화

        Args:
            max_workers: 최대 워커 프로세스 수 (기본값: CPU 코어 수)
        """
        self.max_workers = max_workers or mp.cpu_count()
        print(f"[PARALLEL] 병렬 처리 워커 수: {self.max_workers}")

    def run_strategies(
        self, strategies: List[Strategy], data: pd.DataFrame, ticker: str = "QQQ"
    ) -> Dict[str, BacktestResultWithExcess]:
        """
        여러 전략을 병렬로 실행

        Args:
            strategies: 실행할 전략 리스트
            data: 주가 데이터
            ticker: 주식 심볼

        Returns:
            Dict[str, BacktestResultWithExcess]: 전략별 백테스트 결과
        """
        print(f"[PARALLEL] {len(strategies)}개 전략 병렬 실행 시작...")

        # 데이터 검증
        if data.empty:
            raise ValueError("백테스트할 데이터가 없습니다.")

        # 병렬 실행을 위한 데이터 준비
        strategy_tasks: List[StrategyTaskData] = []
        for strategy in strategies:
            task_data: StrategyTaskData = {
                "strategy_class": strategy.__class__,
                "strategy_args": {"is_benchmark": strategy.is_benchmark},
                "strategy_name": strategy.name,
                "data": data.copy(),  # 각 프로세스에 데이터 복사본 전달
                "ticker": ticker,
            }
            strategy_tasks.append(task_data)

        # 병렬 실행
        results: Dict[str, BacktestResult] = {}
        failed_strategies: List[FailedStrategy] = []

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # 작업 제출
            future_to_strategy = {
                executor.submit(run_single_strategy, task): task["strategy_name"]
                for task in strategy_tasks
            }

            # 결과 수집
            for future in as_completed(future_to_strategy):
                strategy_name = future_to_strategy[future]
                try:
                    result = future.result()
                    results[strategy_name] = result
                except Exception as e:
                    failed_strategies.append(
                        {"strategy": strategy_name, "error": str(e)}
                    )

        # 실패한 전략 로그
        if failed_strategies:
            print(f"[WARNING] {len(failed_strategies)}개 전략 실행 실패:")
            for failed in failed_strategies:
                print(f"  - {failed['strategy']}: {failed['error']}")

        # 벤치마크 대비 초과 수익률 계산
        results_with_benchmark = self._calculate_excess_returns(results)

        print(f"[PARALLEL] 병렬 실행 완료: {len(results)}개 전략 성공")
        return results_with_benchmark

    def _calculate_excess_returns(
        self, results: Dict[str, BacktestResult]
    ) -> Dict[str, BacktestResultWithExcess]:
        """
        벤치마크 대비 초과 수익률 계산

        Args:
            results: 전략별 백테스트 결과

        Returns:
            Dict[str, BacktestResultWithExcess]: 초과 수익률이 추가된 결과
        """
        # 벤치마크 찾기
        benchmark_result = None
        benchmark_name = None

        for name, result in results.items():
            if result.get("is_benchmark", False):
                benchmark_result = result
                benchmark_name = str(name)
                break

        if benchmark_result is None:
            print("[WARNING] 벤치마크 전략을 찾을 수 없습니다.")
            # 벤치마크가 없는 경우에도 excess_return 필드를 추가
            updated_results: Dict[str, BacktestResultWithExcess] = {}
            for name, result in results.items():
                updated_result: BacktestResultWithExcess = {
                    **result,
                    "excess_return": 0.0,
                    "excess_return_pct": 0.0,
                }
                updated_results[name] = updated_result
            return updated_results

        benchmark_return = benchmark_result["total_return"]
        print(f"[BENCHMARK] {benchmark_name} 수익률: {benchmark_return:.2%}")

        # 각 전략에 초과 수익률 추가
        final_results: Dict[str, BacktestResultWithExcess] = {}
        for name, result in results.items():
            # BacktestResult를 BacktestResultWithExcess로 변환
            final_result: BacktestResultWithExcess = {
                **result,  # 기존 BacktestResult 모든 필드 복사
                "excess_return": 0.0,
                "excess_return_pct": 0.0,
            }

            if str(name) != benchmark_name:
                strategy_return = result["total_return"]
                excess_return = strategy_return - benchmark_return
                final_result["excess_return"] = round(excess_return, 4)
                final_result["excess_return_pct"] = round(excess_return * 100, 2)
                print(f"[EXCESS] {name} 초과수익률: {excess_return:.2%}")

            final_results[name] = final_result

        return final_results

    def print_summary(self, results: Dict[str, BacktestResultWithExcess]) -> None:
        """결과 요약 출력"""
        if not results:
            print("[SUMMARY] 실행된 전략이 없습니다.")
            return

        print("\n" + "=" * 60)
        print(" 백테스팅 결과 요약")
        print("=" * 60)

        # 벤치마크 먼저 표시
        benchmark_name = None
        for name, result in results.items():
            if result.get("is_benchmark", False):
                benchmark_name = name
                self._print_strategy_summary(name, result, is_benchmark=True)
                break

        print("-" * 60)

        # 나머지 전략들
        for name, result in results.items():
            if not result.get("is_benchmark", False):
                self._print_strategy_summary(name, result, is_benchmark=False)

        print("=" * 60)

    def _print_strategy_summary(
        self, name: str, result: BacktestResultWithExcess, is_benchmark: bool = False
    ) -> None:
        """개별 전략 요약 출력"""
        prefix = "[벤치마크]" if is_benchmark else "[전략]"

        print(f"{prefix} {name}")
        print(f"  수익률: {result['total_return_pct']:.2f}%")
        print(f"  거래횟수: {result['num_trades']}회")
        print(f"  승률: {result['win_rate_pct']:.1f}%")
        print(f"  총 수수료: ${result['total_commission']:.2f}")

        if not is_benchmark and "excess_return_pct" in result:
            excess_sign = "+" if result["excess_return_pct"] >= 0 else ""
            print(f"  초과수익률: {excess_sign}{result['excess_return_pct']:.2f}%")

        print()
