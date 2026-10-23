"""
테스트 공통 픽스처 모듈

이 파일은 pytest가 자동으로 로드하는 설정 파일입니다.
모든 테스트에서 공유하는 픽스처(테스트 데이터 생성 함수)를 정의합니다.

픽스처를 사용하는 이유:
1. 코드 재사용: 여러 테스트에서 같은 준비 코드 공유
2. 가독성: 테스트 함수가 "무엇을 검증하는지"에 집중
3. 격리성: 각 테스트마다 독립적인 데이터 생성
4. 자동 정리: tmp_path 같은 픽스처는 테스트 후 자동 삭제
"""

import os
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME

# 그리드 서치 워커(spawn 프로세스)는 pytest.ini 경고 필터 미적용 → 환경 변수로 물려줘 워커의 수치 경고도 실패로
os.environ["PYTHONWARNINGS"] = "error::RuntimeWarning"


@pytest.fixture
def sample_stock_df():
    """
    기본 주식 데이터 DataFrame 픽스처

    왜 픽스처로 만드나요?
    - 여러 테스트에서 동일한 구조의 데이터가 필요
    - 각 테스트는 독립적인 복사본을 받아야 함 (상호 영향 없음)

    Returns:
        pd.DataFrame: Date, Open, High, Low, Close, Volume 컬럼
    """
    return pd.DataFrame(
        {
            COL_DATE: [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
            COL_OPEN: [100.0, 101.0, 102.0],
            COL_HIGH: [105.0, 106.0, 107.0],
            COL_LOW: [99.0, 100.0, 101.0],
            COL_CLOSE: [103.0, 104.0, 105.0],
            COL_VOLUME: [1000000, 1100000, 1200000],
        }
    )


@pytest.fixture
def sample_ffr_df():
    """
    연방기금금리(FFR) 데이터 픽스처

    TQQQ 시뮬레이션에서 차입 비용 계산에 사용되는 데이터입니다.

    Returns:
        pd.DataFrame: DATE(yyyy-mm 문자열), VALUE(0~1 비율, 예: 0.045 = 4.5%) 컬럼

    Note: 원본 CSV 스키마("DATE", "VALUE")를 리터럴로 유지하여 외부 데이터 형식 회귀 탐지
    """
    return pd.DataFrame({"DATE": ["2023-01", "2023-02", "2023-03"], "VALUE": [0.045, 0.046, 0.047]})


@pytest.fixture
def sample_expense_df():
    """
    운용비율(Expense Ratio) 데이터 픽스처

    TQQQ 시뮬레이션에서 운용비용 계산에 사용되는 데이터입니다.

    Returns:
        pd.DataFrame: DATE(yyyy-mm 문자열), VALUE(연 운용비율, 0~1 소수) 컬럼

    Note: 원본 CSV 스키마("DATE", "VALUE")를 리터럴로 유지하여 외부 데이터 형식 회귀 탐지
    """
    return pd.DataFrame({"DATE": ["2023-01", "2023-02", "2023-03"], "VALUE": [0.0095, 0.0095, 0.0088]})


@pytest.fixture
def create_csv_file(tmp_path: Path):
    """
    CSV 파일 생성 헬퍼 픽스처 (팩토리 패턴)

    왜 함수를 반환하나요?
    - 테스트마다 다른 파일명/내용으로 여러 CSV 생성 가능
    - 픽스처 하나로 유연한 테스트 데이터 준비

    사용 예시:
        csv_path = create_csv_file("test.csv", sample_df)

    Args:
        tmp_path: pytest 기본 제공 픽스처 (테스트별 임시 디렉토리)

    Returns:
        function: (filename, df) -> Path
    """

    def _create_csv(filename: str, df: pd.DataFrame) -> Path:
        """
        실제 CSV 파일 생성 함수

        Args:
            filename: 파일명 (예: "AAPL_max.csv")
            df: 저장할 DataFrame

        Returns:
            Path: 생성된 CSV 파일 경로
        """
        csv_path = tmp_path / filename
        df.to_csv(csv_path, index=False)
        return csv_path

    return _create_csv


@pytest.fixture
def integration_stock_df():
    """
    통합 테스트용 주식 데이터 DataFrame 픽스처 (~25행)

    왜 별도 픽스처가 필요한가?
    - sample_stock_df는 3행이라 MA 계산에 부족
    - 이동평균 window=5 기준 최소 5행 이상, 버퍼존 전략 실행에는 충분한 데이터 필요
    - 25 영업일 = 약 1개월 분량, 파이프라인 연결 테스트에 적합

    Returns:
        pd.DataFrame: 25행, OHLCV + Date 컬럼 (미세한 등락 포함)
    """
    # 2023-01-02 ~ 2023-02-03 (25 영업일, 주말 건너뛰기)
    dates = []
    day = 2
    month = 1
    for _ in range(25):
        dates.append(date(2023, month, day))
        day += 1
        weekday = dates[-1].weekday()
        if weekday == 4:  # 금요일 -> 월요일
            day += 2
        if day > 28:
            day = 1
            month += 1

    # 가격: 100에서 시작, 미세 등락
    base_prices = [
        100.0,
        101.2,
        99.8,
        102.5,
        101.0,
        103.1,
        102.0,
        104.5,
        103.2,
        105.0,
        104.0,
        106.2,
        105.5,
        103.8,
        107.0,
        106.0,
        108.5,
        107.2,
        109.0,
        108.0,
        110.5,
        109.0,
        111.2,
        110.0,
        112.5,
    ]

    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [p - 0.5 for p in base_prices],
            COL_HIGH: [p + 1.5 for p in base_prices],
            COL_LOW: [p - 1.5 for p in base_prices],
            COL_CLOSE: base_prices,
            COL_VOLUME: [1000000 + i * 10000 for i in range(25)],
        }
    )
