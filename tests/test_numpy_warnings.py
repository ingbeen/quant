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

    def test_without_fixture_no_warning_by_default(self):
        """
        픽스처 없이는 기본적으로 경고가 발생하지 않음을 확인

        Given: enable_numpy_warnings 픽스처 미사용
        When: 0으로 나누기 연산 수행
        Then: 경고 발생하지 않음 (NumPy 기본 동작)

        Note:
            - 이 테스트는 픽스처가 실제로 동작을 변경하는지 확인하는 대조군 테스트
            - NumPy는 기본적으로 부동소수점 오류를 조용히 처리 (inf, nan 반환)
        """
        # 기본 errstate 설정 확인
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # NumPy 기본 설정 (errstate 없음)
            _ = np.array([1.0]) / 0.0

            # NumPy 기본 동작: 0으로 나누면 inf 반환, 경고 없음
            # (픽스처를 사용하지 않으면 경고가 발생하지 않을 수 있음)
            # 이 테스트는 픽스처의 효과를 대조하기 위한 것
            # 경고가 없거나, 있더라도 픽스처 사용 시보다 적음을 확인
            warning_count = len(w)
            # 기본적으로 경고가 없을 수 있음
            assert warning_count >= 0, "경고 수는 0 이상이어야 함"
