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

from datetime import date
from pathlib import Path

import pandas as pd
import pytest


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
            "Date": [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [103.0, 104.0, 105.0],
            "Volume": [1000000, 1100000, 1200000],
        }
    )


@pytest.fixture
def sample_ffr_df():
    """
    연방기금금리(FFR) 데이터 픽스처

    TQQQ 시뮬레이션에서 차입 비용 계산에 사용되는 데이터입니다.

    Returns:
        pd.DataFrame: DATE(yyyy-mm 문자열), FFR(금리 % float) 컬럼
    """
    return pd.DataFrame({"DATE": ["2023-01", "2023-02", "2023-03"], "FFR": [4.5, 4.6, 4.7]})


@pytest.fixture
def create_csv_file(tmp_path):
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
def mock_storage_paths(tmp_path, monkeypatch):
    """
    storage 경로를 테스트 임시 디렉토리로 변경하는 픽스처

    왜 필요한가요?
    - 실제 프로덕션 데이터를 건드리면 안 됨
    - 테스트는 격리된 환경에서 실행되어야 함

    사용 방법:
        이 픽스처를 테스트 함수 인자로 받으면 자동으로
        common_constants의 경로들이 tmp_path로 변경됩니다.

    Returns:
        dict: 변경된 경로들 {'STOCK_DIR': Path, 'ETC_DIR': Path, ...}
    """
    # 임시 디렉토리 구조 생성
    stock_dir = tmp_path / "stock"
    etc_dir = tmp_path / "etc"
    results_dir = tmp_path / "results"

    stock_dir.mkdir()
    etc_dir.mkdir()
    results_dir.mkdir()

    # common_constants 모듈의 경로 상수들을 임시 경로로 변경
    from qbt import common_constants
    from qbt.utils import meta_manager

    meta_json_path = results_dir / "meta.json"

    monkeypatch.setattr(common_constants, "STOCK_DIR", stock_dir)
    monkeypatch.setattr(common_constants, "ETC_DIR", etc_dir)
    monkeypatch.setattr(common_constants, "RESULTS_DIR", results_dir)
    monkeypatch.setattr(common_constants, "META_JSON_PATH", meta_json_path)

    # meta_manager 모듈도 패치 (모듈 로드 시점에 임포트한 값)
    monkeypatch.setattr(meta_manager, "META_JSON_PATH", meta_json_path)

    return {"STOCK_DIR": stock_dir, "ETC_DIR": etc_dir, "RESULTS_DIR": results_dir, "META_JSON_PATH": meta_json_path}
