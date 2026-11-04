"""TQQQ 시뮬레이션 출력 테스트

합성 시세를 만드는 상품 표(배율 · 실물 시세 · 합성 파일)의 계약을 검증한다.
"""

from qbt.tqqq.constants import (
    DAILY_COMPARISON_TARGETS,
    SYNTHETIC_DATA_PATHS,
)


class TestDailyComparisonTargets:
    """일별 비교 상품 표의 계약 테스트"""

    def test_leverage_by_product(self):
        """
        목적: 상품별 배율을 숫자로 고정한다 — 배율이 틀리면 합성 시세가 에러 없이 다른 배수로 만들어진다

        Given: 일별 비교 상품 표
        When: 이름별 배율을 모은다
        Then: TQQQ 3배, QLD 2배
        """
        # When
        leverage_by_name = {name: leverage for name, _, leverage in DAILY_COMPARISON_TARGETS}

        # Then
        assert leverage_by_name == {"TQQQ": 3.0, "QLD": 2.0}

    def test_files_by_product(self):
        """
        목적: 상품별 실물 시세를 고정한다 — 실물이 바뀌면 다른 상품의 실물에 이어 붙인 합성이 에러 없이 나간다

        Given: 일별 비교 상품 표
        When: 이름별 실물 시세 파일 이름을 모은다
        Then: 상품마다 자기 실물 시세다
        """
        # When
        files_by_name = {name: actual.name for name, actual, _ in DAILY_COMPARISON_TARGETS}

        # Then
        assert files_by_name == {"TQQQ": "TQQQ_max.csv", "QLD": "QLD_max.csv"}

    def test_synthetic_file_by_product(self):
        """
        목적: 상품마다 자기 합성 파일에 저장됨을 고정한다 — 경로가 겹치면 전략이 읽는 TQQQ 합성이
              2배 시세로 에러 없이 덮인다. 합성 스크립트는 이 표와 상품 표로 돌고 테스트가 스크립트에 닿지 않는다

        Given: 합성 파일 표와 일별 비교 상품 표
        When: 상품 표의 이름으로 합성 파일을 찾는다
        Then: 상품마다 자기 파일이고, 상품 표의 모든 이름이 있다
        """
        # When
        files_by_name = {name: SYNTHETIC_DATA_PATHS[name].name for name, _, _ in DAILY_COMPARISON_TARGETS}

        # Then
        assert files_by_name == {"TQQQ": "TQQQ_synthetic_max.csv", "QLD": "QLD_synthetic_max.csv"}
