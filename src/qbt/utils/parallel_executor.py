"""병렬 처리 유틸리티 모듈

ProcessPoolExecutor를 사용하여 CPU 집약적 작업을 병렬로 실행한다.
"""

import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

from qbt.utils import get_logger

logger = get_logger(__name__)


def _unwrap_kwargs(args: tuple[Callable, dict[str, Any]]) -> Any:
    """
    (함수, kwargs 딕셔너리) 튜플을 받아 함수를 호출한다.

    ProcessPoolExecutor에서 pickle 가능하도록 모듈 레벨에 정의한다.

    Args:
        args: (func, kwargs_dict) 튜플
            - func: 호출할 함수
            - kwargs_dict: 키워드 인자 딕셔너리

    Returns:
        함수 호출 결과
    """
    func, kwargs_dict = args
    return func(**kwargs_dict)


def execute_parallel(
    func: Callable,
    inputs: list[Any],
    max_workers: int | None = None,
) -> list[Any]:
    """
    CPU 집약적 함수를 여러 입력에 대해 병렬로 실행한다.

    ProcessPoolExecutor를 사용하여 함수를 병렬로 실행하고,
    모든 작업이 완료될 때까지 대기한 후 입력 순서대로 정렬된 결과를 반환한다.

    Args:
        func: 병렬로 실행할 함수 (단일 인자를 받아야 함)
        inputs: 함수에 전달할 입력 리스트
        max_workers: 최대 워커 수 (None이면 CPU 코어 수 - 1)

    Returns:
        입력 순서대로 정렬된 결과 리스트

    Raises:
        ValueError: inputs가 비어있을 때
        Exception: 작업 중 발생한 예외 (첫 번째 예외만 전파)

    Example:
        >>> def heavy_computation(x: int) -> int:
        ...     return x ** 2
        >>> inputs = [1, 2, 3, 4, 5]
        >>> results = execute_parallel(heavy_computation, inputs, max_workers=2)
        >>> print(results)  # [1, 4, 9, 16, 25]

    Note:
        - Windows 환경에서는 호출하는 스크립트에서 `if __name__ == "__main__"`으로 보호해야 함
        - func는 pickle 가능해야 함 (람다 함수는 사용 불가)
        - 각 워커는 독립적인 프로세스에서 실행되므로 전역 상태를 공유하지 않음
    """
    # 1. 입력 검증
    if not inputs:
        raise ValueError("inputs가 비어있습니다")

    # 2. max_workers 기본값 설정 (CPU 코어 수 - 1, 최소 1)
    if max_workers is None:
        cpu_count = os.cpu_count() or 1
        max_workers = max(1, cpu_count - 1)

    logger.debug(
        f"병렬 실행 시작 - 작업 수: {len(inputs)}, 워커 수: {max_workers}, " f"함수: {func.__module__}.{func.__name__}"
    )

    # 3. 병렬 실행
    # (입력 인덱스, 결과) 쌍을 저장하여 나중에 순서를 복원
    results_with_index: list[tuple[int, Any]] = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # 각 입력에 대해 future 생성 (인덱스와 함께 제출)
        future_to_index = {executor.submit(func, input_data): idx for idx, input_data in enumerate(inputs)}

        # 완료되는 대로 결과 수집
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                result = future.result()
                results_with_index.append((idx, result))

                # 진행도 로깅 (매 10개마다)
                completed_count = len(results_with_index)
                if completed_count % 10 == 0 or completed_count == len(inputs):
                    progress_pct = (completed_count / len(inputs)) * 100
                    logger.debug(f"진행도: {completed_count}/{len(inputs)} ({progress_pct:.1f}%)")

            except Exception as e:
                logger.debug(f"작업 {idx + 1}/{len(inputs)} 실패: {e}")
                raise

    # 4. 입력 순서대로 정렬
    results_with_index.sort(key=lambda x: x[0])
    results = [result for _, result in results_with_index]

    logger.debug(f"병렬 실행 완료 - 총 {len(results)}개 작업 성공")

    return results


def execute_parallel_with_kwargs(
    func: Callable,
    inputs: list[dict[str, Any]],
    max_workers: int | None = None,
) -> list[Any]:
    """
    CPU 집약적 함수를 여러 입력에 대해 병렬로 실행한다. (키워드 인자 지원)

    각 입력을 딕셔너리로 받아 **kwargs 형태로 함수에 전달한다.
    나머지 동작은 execute_parallel과 동일하다.

    Args:
        func: 병렬로 실행할 함수 (키워드 인자를 받아야 함)
        inputs: 함수에 전달할 키워드 인자 딕셔너리 리스트
        max_workers: 최대 워커 수 (None이면 CPU 코어 수 - 1)

    Returns:
        입력 순서대로 정렬된 결과 리스트

    Raises:
        ValueError: inputs가 비어있을 때
        Exception: 작업 중 발생한 예외 (첫 번째 예외만 전파)

    Example:
        >>> def compute(a: int, b: int) -> int:
        ...     return a + b
        >>> inputs = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        >>> results = execute_parallel_with_kwargs(compute, inputs, max_workers=2)
        >>> print(results)  # [3, 7]

    Note:
        - Windows 환경에서는 호출하는 스크립트에서 `if __name__ == "__main__"`으로 보호해야 함
        - func와 inputs의 모든 객체는 pickle 가능해야 함
        - 각 워커는 독립적인 프로세스에서 실행되므로 전역 상태를 공유하지 않음
    """
    # (func, kwargs) 튜플 리스트 생성
    unwrap_inputs = [(func, kwargs_dict) for kwargs_dict in inputs]

    # 모듈 레벨 _unwrap_kwargs 함수 사용 (pickle 가능)
    return execute_parallel(_unwrap_kwargs, unwrap_inputs, max_workers)
