"""CLI 스크립트 공통 헬퍼 함수

CLI 스크립트에서 공통으로 사용하는 예외 처리 데코레이터를 제공한다.
"""

import inspect
import logging
from functools import wraps
from typing import Callable

from qbt.backtest.exceptions import DataValidationError

# 예외 타입별 로깅 설정 (모든 예외에 exc_info=True 적용)
EXCEPTION_HANDLERS = {
    DataValidationError: {
        "message_format": "데이터 검증 실패: {error}",
        "exc_info": True,
    },
    FileNotFoundError: {
        "message_format": "파일 오류: {error}",
        "exc_info": True,
    },
    ValueError: {
        "message_format": "입력값 오류: {error}",
        "exc_info": True,
    },
    Exception: {
        "message_format": "예기치 않은 오류: {error}",
        "exc_info": True,
    },
}


def cli_exception_handler(func: Callable[[], int]) -> Callable[[], int]:
    """
    CLI main() 함수의 예외를 일관되게 처리하는 데코레이터.

    모든 예외를 캐치하여 적절한 에러 로그를 남기고 실패 코드(1)를 반환한다.
    로거는 함수가 정의된 모듈의 최상위 'logger' 변수를 자동으로 감지한다.
    모든 예외 타입에 대해 스택 트레이스(exc_info=True)를 포함하여 로깅한다.

    사용 예시:
        @cli_exception_handler
        def main() -> int:
            # 비즈니스 로직
            return 0

    Args:
        func: CLI의 main() 함수 (반환값: 0=성공, 1=실패)

    Returns:
        래핑된 함수
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> int:
        # 1. 로거 자동 감지
        module = inspect.getmodule(func)
        logger = getattr(module, "logger", None)

        if logger is None:
            # 폴백: 기본 로거 사용
            logger = logging.getLogger(__name__)
            logger.warning("모듈에 logger가 정의되지 않았습니다. 기본 로거를 사용합니다.")

        try:
            # 2. 원본 함수 실행
            return func(*args, **kwargs)

        except Exception as e:
            # 3. 예외 타입별 핸들러 검색 (가장 구체적인 타입부터)
            for exc_type, handler_config in EXCEPTION_HANDLERS.items():
                if isinstance(e, exc_type):
                    # 4. 에러 로깅
                    message = handler_config["message_format"].format(error=e)
                    logger.error(message, exc_info=handler_config["exc_info"])

                    # 5. 실패 코드 반환
                    return 1

            # 6. 폴백 (도달하지 않아야 함)
            logger.error(f"처리되지 않은 예외: {e}", exc_info=True)
            return 1

    return wrapper
