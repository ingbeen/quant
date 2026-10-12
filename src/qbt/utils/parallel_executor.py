"""병렬 처리 유틸리티 모듈

ProcessPoolExecutor를 사용하여 CPU 집약적 작업을 병렬로 실행한다.
"""

import multiprocessing
import os
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from typing import Any

from qbt.utils.logger import get_logger

logger = get_logger(__name__)

# 워커 프로세스별 캐시 저장소
# 병렬 실행 시 큰 DataFrame을 작업마다 전달하지 않고, 워커당 1회만 세팅
WORKER_CACHE: dict[str, Any] = {}


def init_worker_cache(cache_payload: dict[str, Any]) -> None:
    """
    워커 프로세스 초기화 함수.

    WORKER_CACHE를 초기화하고 전달받은 데이터를 캐싱한다.
    병렬 실행 시 큰 DataFrame을 작업마다 전달하지 않고, 워커당 1회만 세팅한다.

    이 함수는 ProcessPoolExecutor의 initializer 인자로 사용되며,
    각 워커 프로세스가 시작될 때 자동으로 호출된다.

    Args:
        cache_payload: 캐시할 데이터 딕셔너리
            - 키: 캐시 항목 이름 (예: "signal_df", "trade_df")
            - 값: 캐시할 데이터 (주로 DataFrame)

    Note:
        - 이 함수는 pickle 가능하도록 모듈 최상위 레벨에 정의되어야 함
        - WORKER_CACHE는 워커 프로세스 전역 변수이므로, 워커 함수에서 직접 참조 가능
        - 워커 프로세스마다 독립적인 WORKER_CACHE를 가지므로 서로 간섭하지 않음
    """
    WORKER_CACHE.clear()
    WORKER_CACHE.update(cache_payload)


def _should_log_progress(
    completed_count: int,
    total_count: int,
    last_logged_percentage: int,
) -> tuple[bool, int]:
    """
    진행도 로그 출력 여부를 결정한다.

    다음 조건 중 하나라도 만족하면 로그를 출력한다:
    1. 첫 번째 작업 완료
    2. 마지막 작업 완료
    3. 10% 경계를 넘었을 때 (10%, 20%, ..., 90%)

    Args:
        completed_count: 완료된 작업 수
        total_count: 전체 작업 수
        last_logged_percentage: 마지막으로 로그를 출력한 퍼센트 (0-100)

    Returns:
        (출력 여부, 현재 퍼센트) 튜플
    """
    current_percentage = int((completed_count / total_count) * 100)

    # 1. 첫 번째 작업 완료
    if completed_count == 1:
        return (True, current_percentage)

    # 2. 마지막 작업 완료
    if completed_count == total_count:
        return (True, current_percentage)

    # 3. 10% 경계를 넘었을 때
    last_decile = last_logged_percentage // 10
    current_decile = current_percentage // 10
    if current_decile > last_decile:
        return (True, current_percentage)

    return (False, current_percentage)


def execute_parallel_with_kwargs(
    func: Callable[..., Any],
    inputs: list[dict[str, Any]],
    max_workers: int | None = None,
    initializer: Callable[..., None] | None = None,
    initargs: tuple[Any, ...] | None = None,
    log_progress: bool = True,
) -> list[Any]:
    """
    CPU 집약적 함수를 여러 입력에 대해 병렬로 실행한다.

    각 입력 딕셔너리를 **kwargs 로 함수에 전달하고, 모든 작업이 끝나면 입력 순서대로 정렬된 결과를 반환한다.
    작업 하나가 예외를 내면 아직 워커에 넘어가지 않은 작업을 취소하고, 이미 넘어간 작업이 끝나면 그 예외를 전파한다.

    Args:
        func: 병렬로 실행할 함수 (키워드 인자를 받아야 함)
        inputs: 함수에 전달할 키워드 인자 딕셔너리 리스트
        max_workers: 최대 워커 수 (None이면 CPU 수 - 1, 최소 1)
        initializer: 워커 프로세스 초기화 함수 (WORKER_CACHE 세팅용)
        initargs: initializer에 전달할 인자 튜플 (cache_payload,)
        log_progress: 진행도 로깅 출력 여부 (기본값: True)
            - True: 첫 번째, 마지막, 10% 경계마다 진행도 로그 출력
            - False: 진행도 로그 미출력 (시작/완료 로그는 출력)

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
        - 호출하는 스크립트는 `if __name__ == "__main__"`으로 보호해야 함 (워커를 spawn 으로 띄운다)
        - func와 inputs의 모든 객체는 pickle 가능해야 함 (람다 함수는 사용 불가)
        - 각 워커는 독립적인 프로세스에서 실행되므로 전역 상태를 공유하지 않음
        - initializer를 사용하면 큰 데이터를 작업마다 전달하지 않고 워커당 1회만 세팅 가능
    """
    # 1. 입력 검증
    if not inputs:
        raise ValueError("inputs가 비어있습니다")

    # 2. max_workers 기본값 설정
    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 1) - 1)

    logger.debug(f"병렬 실행 시작 - 작업 수: {len(inputs)}, 워커 수: {max_workers}, " f"함수: {func.__module__}.{func.__name__}")

    # 3. 병렬 실행
    # (입력 인덱스, 결과) 쌍을 저장하여 나중에 순서를 복원
    results_with_index: list[tuple[int, Any]] = []
    last_logged_percentage = 0

    # spawn 컨텍스트 사용: fork() 는 멀티스레드 환경에서 데드락 위험이 있어(DeprecationWarning)
    # 어느 OS 에서든 새 인터프리터를 띄우는 spawn 으로 통일한다
    mp_context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=max_workers, mp_context=mp_context, initializer=initializer, initargs=initargs or ()
    ) as executor:
        future_to_index: dict[Future[Any], int] = {
            executor.submit(func, **kwargs): idx for idx, kwargs in enumerate(inputs)
        }

        # 완료되는 대로 결과 수집
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                result: Any = future.result()
                results_with_index.append((idx, result))

                # 진행도 로깅 (첫 번째, 마지막, 10% 경계마다)
                if log_progress:
                    completed_count = len(results_with_index)
                    should_log, current_pct = _should_log_progress(completed_count, len(inputs), last_logged_percentage)
                    if should_log:
                        logger.debug(f"진행도: {completed_count}/{len(inputs)} ({current_pct}%)")
                        last_logged_percentage = current_pct

            except Exception as e:
                logger.debug(f"작업 {idx + 1}/{len(inputs)} 실패: {e}")
                # 아직 워커에 넘어가지 않은 작업을 취소한다 — 그대로 raise 하면 with 블록이 남은 작업을 모두 돌린다.
                # wait=False 로 두지 않는다: with 블록의 종료가 취소 요청을 되돌려 남은 작업이 뒤에서 전부 돈다
                executor.shutdown(cancel_futures=True)
                raise

    # 4. 입력 순서대로 정렬
    results_with_index.sort(key=lambda x: x[0])
    results = [result for _, result in results_with_index]

    logger.debug(f"병렬 실행 완료 - 총 {len(results)}개 작업 성공")

    return results
