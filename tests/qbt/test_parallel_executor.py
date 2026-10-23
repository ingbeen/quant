"""
병렬 처리 유틸리티 테스트

병렬 실행 기능 및 워커 캐시 구조를 검증한다.
"""

import logging
import time
from pathlib import Path

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


def _fail_first_or_leave_marker(index: int, marker_dir: Path) -> int:
    """index 0 은 바로 실패하고, 나머지는 잠깐 쉰 뒤 실행 흔적 파일을 남긴다"""
    if index == 0:
        raise RuntimeError("첫 작업 실패")
    time.sleep(0.2)
    (marker_dir / f"ran_{index}").touch()
    return index


@pytest.fixture
def executor_logs(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """병렬 실행기의 DEBUG 로그를 caplog 으로 잡는다.

    프로젝트 로거는 propagate=False 라 caplog 이 레코드를 받지 못한다. 테스트 중에만 True 로 바꾼다.
    """
    monkeypatch.setattr(logging.getLogger("qbt.utils.parallel_executor"), "propagate", True)
    caplog.set_level(logging.DEBUG, logger="qbt.utils.parallel_executor")
    return caplog


class TestExecuteParallel:
    """execute_parallel_with_kwargs 함수 테스트"""

    def test_basic_execution(self):
        """기본 병렬 실행이 정상 동작하는지 검증"""
        inputs = [{"x": x} for x in [1, 2, 3, 4, 5]]
        results = parallel_executor.execute_parallel_with_kwargs(_simple_multiply, inputs, max_workers=2)

        assert results == [2, 4, 6, 8, 10]

    def test_empty_inputs(self):
        """빈 입력에 대해 ValueError를 발생시키는지 검증"""
        with pytest.raises(ValueError, match="inputs가 비어있습니다"):
            parallel_executor.execute_parallel_with_kwargs(_simple_multiply, [], max_workers=2)

    def test_order_preservation(self):
        """
        입력 순서가 보장되는지 검증

        병렬 실행 시 as_completed 완료 순서와 무관하게
        원래 입력 순서대로 결과가 반환되는지 확인한다.
        테스트 실행 시간 단축을 위해 최소 파라미터 사용 (5개 입력, 2 workers).
        """
        inputs = [{"x": x} for x in range(5)]
        results = parallel_executor.execute_parallel_with_kwargs(_simple_multiply, inputs, max_workers=2)

        assert results == [x * 2 for x in range(5)]

    def test_failure_cancels_tasks_not_yet_handed_to_workers(self, tmp_path: Path):
        """
        목적: 작업 하나가 실패하면 아직 워커에 넘어가지 않은 작업을 돌리지 않고 예외를 전파하는지 검증
              — 남은 작업을 다 돌린 뒤 전파하면 그리드 수백 건이 실패 뒤에도 끝까지 돈다

        Given: 첫 작업은 바로 실패하고 나머지 5개는 0.2초 뒤 실행 흔적 파일을 남긴다 (워커 1개)
        When: execute_parallel_with_kwargs 실행
        Then: 첫 작업의 예외가 전파되고, 나머지 5개가 다 돌 만큼 기다려도 모두 실행되지는 않는다
        """
        # Given
        inputs = [{"index": i, "marker_dir": tmp_path} for i in range(6)]

        # When
        with pytest.raises(RuntimeError, match="첫 작업 실패"):
            parallel_executor.execute_parallel_with_kwargs(_fail_first_or_leave_marker, inputs, max_workers=1)

        # Then: 이미 워커에 넘어간 작업(워커 수 + 1 까지 미리 넘어간다)만 돈다.
        # 취소 없이 예외만 먼저 전파하는 구현은 나머지가 뒤에서 돌므로, 다 돌 시간을 준 뒤 센다
        time.sleep(1.5)
        assert len(list(tmp_path.glob("ran_*"))) < 5

    @pytest.mark.parametrize(("cpu_count", "expected_workers"), [(1, 1), (3, 2)])
    def test_default_max_workers_is_cpu_count_minus_one_at_least_one(
        self,
        monkeypatch: pytest.MonkeyPatch,
        executor_logs: pytest.LogCaptureFixture,
        cpu_count: int,
        expected_workers: int,
    ):
        """
        목적: max_workers 를 주지 않으면 워커 수가 「CPU 수 - 1, 최소 1」인지 검증
              — CPU 가 1개인 환경에서 0 이 되면 프로세스 풀이 ValueError 로 죽는다

        Given: CPU 수가 1 또는 3
        When: max_workers 없이 execute_parallel_with_kwargs 실행
        Then: 워커 수가 1 또는 2 이고 결과가 정상이다
        """
        # Given
        monkeypatch.setattr("os.cpu_count", lambda: cpu_count)

        # When
        results = parallel_executor.execute_parallel_with_kwargs(_simple_multiply, [{"x": 1}])

        # Then
        assert results == [2]
        start_logs = [r.message for r in executor_logs.records if "병렬 실행 시작" in r.message]
        assert len(start_logs) == 1
        assert f"워커 수: {expected_workers}," in start_logs[0]


class TestWorkerCache:
    """워커 캐시 구조 테스트"""

    def test_cache_initialization(self):
        """
        initializer(init_worker_cache)가 워커의 WORKER_CACHE를 올바르게 세팅하는지 검증
        """

        # 캐시 페이로드 준비
        test_df = pd.DataFrame({"A": [1, 2, 3]})
        cache_payload = {"df": test_df}

        # initializer를 사용한 병렬 실행
        inputs = [{"multiplier": 1}, {"multiplier": 2}]
        results = parallel_executor.execute_parallel_with_kwargs(
            _use_cached_df,
            inputs,
            max_workers=2,
            initializer=parallel_executor.init_worker_cache,
            initargs=(cache_payload,),
        )

        # 캐시된 df를 사용하여 계산된 결과 검증
        assert results == [3, 6]  # len(df)=3 * multiplier

    def test_reinit_drops_previous_entries(self, monkeypatch: pytest.MonkeyPatch):
        """
        목적: init_worker_cache 가 이전 항목을 지우고 새 페이로드만 남기는지 검증 — 같은 프로세스에서 다시 부르면
              (그리드 워커를 프로세스 안에서 직접 부르는 테스트) 앞 호출의 키가 남아 다른 데이터를 읽는다

        Given: WORKER_CACHE 에 앞 호출이 남긴 키가 있다
        When: 다른 페이로드로 init_worker_cache 를 프로세스 안에서 부른다
        Then: WORKER_CACHE 의 키가 새 페이로드의 키뿐이다
        """
        # Given — 이 테스트 전용 캐시로 바꿔 다른 테스트와 격리
        monkeypatch.setattr(parallel_executor, "WORKER_CACHE", {"stale": pd.DataFrame({"A": [1]})})
        new_df = pd.DataFrame({"A": [1, 2, 3, 4, 5]})

        # When
        parallel_executor.init_worker_cache({"df": new_df})

        # Then
        assert set(parallel_executor.WORKER_CACHE) == {"df"}
        assert parallel_executor.WORKER_CACHE["df"] is new_df


class TestLogProgress:
    """log_progress 파라미터 테스트"""

    def test_log_progress_false_suppresses_progress_logs(self, executor_logs: pytest.LogCaptureFixture):
        """
        log_progress=False 시 진행도 로그가 출력되지 않는지 검증

        Given: 5개 입력과 log_progress=False
        When: execute_parallel_with_kwargs 실행
        Then: "진행도:" 패턴의 로그가 출력되지 않음
              (시작/완료 로그는 여전히 출력됨)
        """
        # Given
        inputs = [{"x": x} for x in [1, 2, 3, 4, 5]]

        # When
        results = parallel_executor.execute_parallel_with_kwargs(
            _simple_multiply, inputs, max_workers=2, log_progress=False
        )

        # Then
        assert results == [2, 4, 6, 8, 10]
        progress_logs = [r.message for r in executor_logs.records if "진행도:" in r.message]
        assert len(progress_logs) == 0
        # 시작/완료 로그는 여전히 출력되는지 확인
        start_logs = [r.message for r in executor_logs.records if "병렬 실행 시작" in r.message]
        assert len(start_logs) == 1

    def test_log_progress_true_emits_progress_logs(self, executor_logs: pytest.LogCaptureFixture):
        """
        log_progress=True (기본값) 시 진행도 로그가 출력되는지 검증

        Given: 5개 입력과 log_progress=True (기본값)
        When: execute_parallel_with_kwargs 실행
        Then: "진행도:" 패턴의 로그가 1회 이상 출력됨
        """
        # Given
        inputs = [{"x": x} for x in [1, 2, 3, 4, 5]]

        # When
        results = parallel_executor.execute_parallel_with_kwargs(
            _simple_multiply, inputs, max_workers=2, log_progress=True
        )

        # Then
        assert results == [2, 4, 6, 8, 10]
        progress_logs = [r.message for r in executor_logs.records if "진행도:" in r.message]
        assert len(progress_logs) >= 1
