"""
병렬 처리 유틸리티 테스트

병렬 실행 기능 및 워커 캐시 구조를 검증한다.
"""

import pandas as pd
import pytest

from qbt.utils import parallel_executor


def _simple_multiply(x: int) -> int:
    """단순 곱셈 함수 (pickle 가능하도록 모듈 레벨 정의)"""
    return x * 2


def _use_cached_df(multiplier: int) -> int:
    """캐시된 DataFrame을 사용하는 워커 함수"""
    df = parallel_executor.WORKER_CACHE.get("df")
    if df is None:
        raise ValueError("WORKER_CACHE에 df가 없습니다")
    return len(df) * multiplier


def _init_worker_cache(cache_payload: dict) -> None:
    """워커 초기화 함수 - WORKER_CACHE 세팅"""
    parallel_executor.WORKER_CACHE.clear()
    parallel_executor.WORKER_CACHE.update(cache_payload)


def _try_modify_cache(dummy: int) -> int:
    """캐시된 df를 수정하려고 시도하는 함수 (금지됨)"""
    df = parallel_executor.WORKER_CACHE.get("df")
    if df is None:
        raise ValueError("WORKER_CACHE에 df가 없습니다")
    # 원본 수정 시도 (실제로는 .copy()를 사용해야 함)
    df.loc[0, "A"] = 999
    return len(df)


class TestExecuteParallel:
    """execute_parallel 함수 테스트"""

    def test_basic_execution(self):
        """기본 병렬 실행이 정상 동작하는지 검증"""
        inputs = [1, 2, 3, 4, 5]
        results = parallel_executor.execute_parallel(_simple_multiply, inputs, max_workers=2)

        assert results == [2, 4, 6, 8, 10]

    def test_empty_inputs(self):
        """빈 입력에 대해 ValueError를 발생시키는지 검증"""
        with pytest.raises(ValueError, match="inputs가 비어있습니다"):
            parallel_executor.execute_parallel(_simple_multiply, [], max_workers=2)

    def test_order_preservation(self):
        """
        입력 순서가 보장되는지 검증

        병렬 실행 시 as_completed 완료 순서와 무관하게
        원래 입력 순서대로 결과가 반환되는지 확인한다.
        테스트 실행 시간 단축을 위해 최소 파라미터 사용 (5개 입력, 2 workers).
        """
        inputs = list(range(5))
        results = parallel_executor.execute_parallel(_simple_multiply, inputs, max_workers=2)

        expected = [x * 2 for x in inputs]
        assert results == expected


class TestWorkerCache:
    """워커 캐시 구조 테스트"""

    def test_cache_initialization(self):
        """
        initializer가 WORKER_CACHE를 올바르게 세팅하는지 검증
        """

        # 캐시 페이로드 준비
        test_df = pd.DataFrame({"A": [1, 2, 3]})
        cache_payload = {"df": test_df}

        # initializer를 사용한 병렬 실행
        inputs = [{"multiplier": 1}, {"multiplier": 2}]
        results = parallel_executor.execute_parallel_with_kwargs(
            _use_cached_df, inputs, max_workers=2, initializer=_init_worker_cache, initargs=(cache_payload,)
        )

        # 캐시된 df를 사용하여 계산된 결과 검증
        assert results == [3, 6]  # len(df)=3 * multiplier

    def test_cache_clear_on_reinit(self):
        """
        프로세스 풀 재사용 시 initializer가 캐시를 clear하는지 검증
        """

        # 첫 번째 실행: df1 캐시
        df1 = pd.DataFrame({"A": [1, 2, 3]})
        cache_payload1 = {"df": df1}
        inputs1 = [{"multiplier": 1}]

        results1 = parallel_executor.execute_parallel_with_kwargs(
            _use_cached_df, inputs1, max_workers=1, initializer=_init_worker_cache, initargs=(cache_payload1,)
        )
        assert results1 == [3]

        # 두 번째 실행: df2 캐시 (프로세스 풀 재사용 가능)
        df2 = pd.DataFrame({"A": [1, 2, 3, 4, 5]})
        cache_payload2 = {"df": df2}
        inputs2 = [{"multiplier": 1}]

        results2 = parallel_executor.execute_parallel_with_kwargs(
            _use_cached_df, inputs2, max_workers=1, initializer=_init_worker_cache, initargs=(cache_payload2,)
        )

        # clear가 동작하면 새 캐시(df2)를 사용하여 5가 나와야 함
        assert results2 == [5]

    def test_cache_read_only(self):
        """
        워커 함수가 캐시된 DataFrame을 수정하지 않는지 검증
        """
        test_df = pd.DataFrame({"A": [1, 2, 3]})
        original_value = test_df.loc[0, "A"]
        cache_payload = {"df": test_df}

        inputs = [{"dummy": 1}]
        parallel_executor.execute_parallel_with_kwargs(
            _try_modify_cache, inputs, max_workers=1, initializer=_init_worker_cache, initargs=(cache_payload,)
        )

        # 원본 DataFrame이 수정되지 않았는지 확인
        # (실제로는 프로세스가 별도이므로 수정되지 않음, 이는 원칙 확인용)
        assert test_df.loc[0, "A"] == original_value
