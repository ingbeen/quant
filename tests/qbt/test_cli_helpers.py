"""cli_helpers.py 모듈 테스트

CLI 예외 처리 데코레이터의 계약을 검증한다.

테스트 대상:
- cli_exception_handler: CLI main() 함수의 예외 처리 데코레이터
"""

import logging

from qbt.utils.cli_helpers import cli_exception_handler


class TestCliExceptionHandler:
    """cli_exception_handler 데코레이터 테스트

    목적: 예외 처리, 로거 자동 감지, 종료 코드 반환 계약 검증
    """

    def test_normal_execution_returns_zero(self):
        """
        정상 실행 시 함수의 반환값(0)을 그대로 반환한다.

        Given: 정상 실행되는 함수
        When: @cli_exception_handler 데코레이터 적용 후 실행
        Then: 함수의 반환값 0을 반환
        """

        # Given
        @cli_exception_handler
        def main() -> int:
            return 0

        # When
        result = main()

        # Then
        assert result == 0

    def test_file_not_found_error_returns_one(self, caplog):
        """
        FileNotFoundError 발생 시 종료 코드 1을 반환한다.

        Given: FileNotFoundError를 발생시키는 함수
        When: @cli_exception_handler 데코레이터 적용 후 실행
        Then: 종료 코드 1 반환, 에러 로그 출력
        """

        # Given
        @cli_exception_handler
        def main() -> int:
            raise FileNotFoundError("파일을 찾을 수 없습니다")

        # When
        with caplog.at_level(logging.ERROR):
            result = main()

        # Then
        assert result == 1
        # 에러 로그 확인
        assert any("예외 발생" in record.message for record in caplog.records)

    def test_value_error_returns_one(self, caplog):
        """
        ValueError 발생 시 종료 코드 1을 반환한다.

        Given: ValueError를 발생시키는 함수
        When: @cli_exception_handler 데코레이터 적용 후 실행
        Then: 종료 코드 1 반환, 에러 로그 출력
        """

        # Given
        @cli_exception_handler
        def main() -> int:
            raise ValueError("잘못된 값입니다")

        # When
        with caplog.at_level(logging.ERROR):
            result = main()

        # Then
        assert result == 1
        assert any("예외 발생" in record.message for record in caplog.records)

    def test_generic_exception_returns_one(self, caplog):
        """
        일반 Exception 발생 시 종료 코드 1을 반환한다.

        Given: Exception을 발생시키는 함수
        When: @cli_exception_handler 데코레이터 적용 후 실행
        Then: 종료 코드 1 반환, 에러 로그 출력
        """

        # Given
        @cli_exception_handler
        def main() -> int:
            raise Exception("일반 예외")

        # When
        with caplog.at_level(logging.ERROR):
            result = main()

        # Then
        assert result == 1
        assert any("예외 발생" in record.message for record in caplog.records)

    def test_fallback_logger_when_module_has_no_logger(self, caplog):
        """
        모듈에 logger가 없으면 폴백 로거를 사용한다.

        Given: logger 변수가 없는 모듈의 함수
        When: @cli_exception_handler 데코레이터 적용 후 예외 발생
        Then: 폴백 로거 사용, WARNING/ERROR 메시지 출력
        """

        # Given
        @cli_exception_handler
        def main() -> int:
            raise ValueError("테스트 예외")

        # When
        # WARNING과 ERROR 레벨 모두 캡처
        with caplog.at_level(logging.WARNING):
            result = main()

        # Then
        assert result == 1
        # WARNING 또는 ERROR 로그 확인
        assert len(caplog.records) > 0

    def test_exception_info_logged(self, caplog):
        """
        예외 발생 시 스택 트레이스가 로그에 포함된다.

        Given: 예외를 발생시키는 함수
        When: @cli_exception_handler 데코레이터 적용 후 실행
        Then: 로그에 스택 트레이스 포함 (exc_info=True)
        """

        # Given
        @cli_exception_handler
        def main() -> int:
            raise RuntimeError("런타임 에러 테스트")

        # When
        with caplog.at_level(logging.ERROR):
            result = main()

        # Then
        assert result == 1
        # exc_info=True로 인해 exc_info가 로그 레코드에 포함됨
        assert any(record.exc_info is not None for record in caplog.records)

    def test_decorator_preserves_function_metadata(self):
        """
        데코레이터가 원본 함수의 메타데이터를 보존한다.

        Given: 독스트링과 이름이 있는 함수
        When: @cli_exception_handler 데코레이터 적용
        Then: 함수명과 독스트링 보존 (@wraps 동작 확인)
        """

        # Given
        @cli_exception_handler
        def test_function() -> int:
            """테스트 함수 독스트링"""
            return 0

        # When & Then
        # @wraps(func)가 동작하면 함수명과 독스트링이 보존됨
        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "테스트 함수 독스트링"
