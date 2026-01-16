"""
NumPy errstate 픽스처 테스트 모듈

enable_numpy_warnings 픽스처가 부동소수점 오류를 올바르게 감지하는지 검증합니다.
"""

import warnings

import numpy as np


class TestEnableNumpyWarnings:
    """enable_numpy_warnings 픽스처 동작 검증 테스트"""

    def test_division_by_zero_warning_is_raised(self, enable_numpy_warnings):
        """
        0으로 나누기 시 경고 발생 확인

        Given: enable_numpy_warnings 픽스처 활성화
        When: 0으로 나누기 연산 수행
        Then: RuntimeWarning 발생
        """
        # 경고를 캡처하여 검증
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # 0으로 나누기 (부동소수점 오류 발생)
            _ = np.array([1.0]) / 0.0

            # RuntimeWarning이 발생했는지 확인
            assert len(w) > 0, "0으로 나누기 시 경고가 발생해야 함"
            assert issubclass(w[-1].category, RuntimeWarning), "RuntimeWarning이어야 함"
            assert "divide" in str(w[-1].message).lower(), "divide 관련 경고여야 함"

    def test_invalid_operation_warning_is_raised(self, enable_numpy_warnings):
        """
        유효하지 않은 연산 시 경고 발생 확인

        Given: enable_numpy_warnings 픽스처 활성화
        When: sqrt(-1) 같은 유효하지 않은 연산 수행
        Then: RuntimeWarning 발생
        """
        # 경고를 캡처하여 검증
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # 음수의 제곱근 (유효하지 않은 연산)
            _ = np.sqrt(-1.0)

            # RuntimeWarning이 발생했는지 확인
            assert len(w) > 0, "유효하지 않은 연산 시 경고가 발생해야 함"
            assert issubclass(w[-1].category, RuntimeWarning), "RuntimeWarning이어야 함"
            assert "invalid" in str(w[-1].message).lower(), "invalid 관련 경고여야 함"

    def test_overflow_warning_is_raised(self, enable_numpy_warnings):
        """
        오버플로우 시 경고 발생 확인

        Given: enable_numpy_warnings 픽스처 활성화
        When: 매우 큰 수 연산으로 오버플로우 발생
        Then: RuntimeWarning 발생
        """
        # 경고를 캡처하여 검증
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # 오버플로우 발생 (매우 큰 수의 지수 연산)
            _ = np.exp(1000.0)

            # RuntimeWarning이 발생했는지 확인
            assert len(w) > 0, "오버플로우 시 경고가 발생해야 함"
            assert issubclass(w[-1].category, RuntimeWarning), "RuntimeWarning이어야 함"
            assert "overflow" in str(w[-1].message).lower(), "overflow 관련 경고여야 함"
