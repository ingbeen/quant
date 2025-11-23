"""백테스트 예외 정의 모듈"""


class DataValidationError(Exception):
    """
    데이터 유효성 검증 실패 시 발생하는 예외.

    결측치, 음수, 0 값, 급등락 등 데이터 이상이 감지되었을 때 발생한다.
    """

    pass
