"""
stock_downloader 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 주식 데이터 유효성 검증이 정확히 작동하는가? (결측치, 0값, 음수, 급등락)
2. 정상 데이터가 검증을 통과하는가?
3. Yahoo Finance 다운로드 + 전처리 + 저장 파이프라인이 작동하는가?
4. 빈 데이터 반환 시 명확한 에러를 내는가?

왜 중요한가요?
데이터 품질은 백테스트 결과의 신뢰성을 결정합니다.
다운로드 시 검증을 통과하지 못한 데이터는 즉시 거부되어야 합니다.
"""

from datetime import date, timedelta
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME
from qbt.utils.stock_downloader import download_stock_data, validate_stock_data


def _make_valid_df(rows: int = 5) -> pd.DataFrame:
    """
    테스트용 정상 주식 데이터 DataFrame을 생성한다.

    Args:
        rows: 행 수

    Returns:
        유효한 주식 데이터 DataFrame
    """
    base_date = date(2023, 1, 2)
    dates = [base_date + timedelta(days=i) for i in range(rows)]
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [100.0 + i for i in range(rows)],
            COL_HIGH: [105.0 + i for i in range(rows)],
            COL_LOW: [99.0 + i for i in range(rows)],
            COL_CLOSE: [103.0 + i for i in range(rows)],
            COL_VOLUME: [1000000 + i * 100000 for i in range(rows)],
        }
    )


class TestValidateStockData:
    """주식 데이터 유효성 검증 테스트"""

    def test_valid_data_passes(self):
        """
        정상 데이터 검증 통과 테스트

        Given: 결측치, 0값, 음수, 급등락 없는 정상 데이터
        When: validate_stock_data 호출
        Then: 예외 없이 정상 완료
        """
        # Given
        df = _make_valid_df()

        # When & Then: 예외 없이 통과
        validate_stock_data(df)

    def test_null_values_detected(self):
        """
        결측치(NaN) 검출 테스트

        Given: Open 컬럼에 NaN이 포함된 데이터
        When: validate_stock_data 호출
        Then: ValueError 발생 + "결측치 발견" 메시지
        """
        # Given
        df = _make_valid_df()
        df.loc[1, COL_OPEN] = np.nan

        # When & Then
        with pytest.raises(ValueError, match="결측치 발견"):
            validate_stock_data(df)

    def test_zero_values_detected(self):
        """
        0값 검출 테스트

        Given: Close 컬럼에 0값이 포함된 데이터
        When: validate_stock_data 호출
        Then: ValueError 발생 + "0 값 발견" 메시지
        """
        # Given
        df = _make_valid_df()
        df.loc[2, COL_CLOSE] = 0

        # When & Then
        with pytest.raises(ValueError, match="0 값 발견"):
            validate_stock_data(df)

    def test_negative_values_detected(self):
        """
        음수값 검출 테스트

        Given: High 컬럼에 음수값이 포함된 데이터
        When: validate_stock_data 호출
        Then: ValueError 발생 + "음수 값 발견" 메시지
        """
        # Given
        df = _make_valid_df()
        df.loc[0, COL_HIGH] = -1.0

        # When & Then
        with pytest.raises(ValueError, match="음수 값 발견"):
            validate_stock_data(df)

    def test_extreme_price_change_detected(self):
        """
        급등락 검출 테스트 (DEFAULT_PRICE_CHANGE_THRESHOLD 초과)

        Given: Close 컬럼에서 전일 대비 50% 이상 급등하는 데이터
        When: validate_stock_data 호출
        Then: ValueError 발생 + "급등락 감지" 메시지
        """
        # Given: 103 -> 200 (약 94% 상승)
        df = _make_valid_df()
        df.loc[1, COL_CLOSE] = 200.0

        # When & Then
        with pytest.raises(ValueError, match="급등락 감지"):
            validate_stock_data(df)

    def test_moderate_price_change_passes(self):
        """
        임계값 이하의 가격 변동은 검증 통과

        Given: Close 컬럼에서 전일 대비 10% 상승하는 데이터
        When: validate_stock_data 호출
        Then: 예외 없이 통과 (50% 미만이므로)
        """
        # Given: 103 -> 113.3 (약 10% 상승)
        df = _make_valid_df()
        df.loc[1, COL_CLOSE] = 113.3

        # When & Then: 예외 없이 통과
        validate_stock_data(df)

    def test_single_row_passes(self):
        """
        단일 행 데이터 검증 통과 테스트

        Given: 1행짜리 정상 데이터 (pct_change가 NaN이 됨)
        When: validate_stock_data 호출
        Then: 예외 없이 통과 (첫 행 NaN은 무시)
        """
        # Given
        df = _make_valid_df(rows=1)

        # When & Then
        validate_stock_data(df)


class TestDownloadStockData:
    """주식 데이터 다운로드 테스트 (yfinance 모킹)"""

    def _mock_yfinance(self, monkeypatch, mock_df: pd.DataFrame) -> None:
        """
        yfinance Ticker.history()를 모킹한다.

        Args:
            monkeypatch: pytest monkeypatch 픽스처
            mock_df: history()가 반환할 DataFrame (인덱스에 Date 포함)
        """
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = mock_df
        monkeypatch.setattr("qbt.utils.stock_downloader.yf.Ticker", lambda _: mock_ticker)

    def _make_yfinance_df(self) -> pd.DataFrame:
        """
        yfinance history()가 반환하는 형식의 DataFrame을 생성한다.

        yfinance는 Date를 인덱스로 반환한다.
        최근 2일 필터링을 피하기 위해 과거 날짜를 사용한다.

        Returns:
            yfinance 형식의 DataFrame (Date가 인덱스)
        """
        dates = pd.to_datetime([date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)])
        df = pd.DataFrame(
            {
                COL_OPEN: [100.0, 101.0, 102.0],
                COL_HIGH: [105.0, 106.0, 107.0],
                COL_LOW: [99.0, 100.0, 101.0],
                COL_CLOSE: [103.0, 104.0, 105.0],
                COL_VOLUME: [1000000, 1100000, 1200000],
            },
            index=dates,
        )
        df.index.name = COL_DATE
        return df

    def test_download_max_period(self, monkeypatch, tmp_path):
        """
        전체 기간 다운로드 테스트

        Given: yfinance가 정상 데이터를 반환하도록 모킹
        When: download_stock_data("TEST") 호출
        Then:
          - CSV 파일이 생성됨
          - 파일명이 TEST_max.csv
          - 데이터 행 수가 올바름
        """
        # Given: yfinance 모킹 + STOCK_DIR 패치
        mock_df = self._make_yfinance_df()
        self._mock_yfinance(monkeypatch, mock_df)
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        csv_path = download_stock_data("TEST")

        # Then
        assert csv_path.exists(), "CSV 파일이 생성되어야 합니다"
        assert csv_path.name == "TEST_max.csv", "파일명이 올바르지 않습니다"

        result_df = pd.read_csv(csv_path)
        assert len(result_df) == 3, "3행이 저장되어야 합니다"

    def test_download_with_start_date(self, monkeypatch, tmp_path):
        """
        시작 날짜 지정 다운로드 테스트

        Given: yfinance가 정상 데이터를 반환하도록 모킹
        When: download_stock_data("TEST", start_date="2023-01-01") 호출
        Then: 파일명이 TEST_2023-01-01_latest.csv
        """
        # Given
        mock_df = self._make_yfinance_df()
        self._mock_yfinance(monkeypatch, mock_df)
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        csv_path = download_stock_data("TEST", start_date="2023-01-01")

        # Then
        assert csv_path.name == "TEST_2023-01-01_latest.csv"

    def test_download_with_date_range(self, monkeypatch, tmp_path):
        """
        기간 지정 다운로드 테스트

        Given: yfinance가 정상 데이터를 반환하도록 모킹
        When: download_stock_data("TEST", start_date="2023-01-01", end_date="2023-12-31") 호출
        Then: 파일명이 TEST_2023-01-01_2023-12-31.csv
        """
        # Given
        mock_df = self._make_yfinance_df()
        self._mock_yfinance(monkeypatch, mock_df)
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        csv_path = download_stock_data("TEST", start_date="2023-01-01", end_date="2023-12-31")

        # Then
        assert csv_path.name == "TEST_2023-01-01_2023-12-31.csv"

    def test_empty_data_raises_error(self, monkeypatch, tmp_path):
        """
        빈 데이터 반환 시 에러 발생 테스트

        Given: yfinance가 빈 DataFrame을 반환하도록 모킹
        When: download_stock_data 호출
        Then: ValueError 발생 + "데이터를 찾을 수 없습니다" 메시지
        """
        # Given: 빈 DataFrame 반환
        empty_df = pd.DataFrame()
        self._mock_yfinance(monkeypatch, empty_df)
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When & Then
        with pytest.raises(ValueError, match="데이터를 찾을 수 없습니다"):
            download_stock_data("INVALID_TICKER")

    def test_price_rounding(self, monkeypatch, tmp_path):
        """
        가격 컬럼 소수점 6자리 라운딩 검증

        Given: 소수점이 긴 가격 데이터
        When: download_stock_data 호출
        Then: 저장된 CSV의 가격이 소수점 6자리로 라운딩됨
        """
        # Given: 소수점이 긴 데이터
        dates = pd.to_datetime([date(2023, 1, 2), date(2023, 1, 3)])
        mock_df = pd.DataFrame(
            {
                COL_OPEN: [100.1234567, 101.9876543],
                COL_HIGH: [105.1234567, 106.9876543],
                COL_LOW: [99.1234567, 100.9876543],
                COL_CLOSE: [103.1234567, 104.9876543],
                COL_VOLUME: [1000000, 1100000],
            },
            index=dates,
        )
        mock_df.index.name = COL_DATE
        self._mock_yfinance(monkeypatch, mock_df)
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        csv_path = download_stock_data("TEST")

        # Then: 소수점 6자리로 라운딩 확인
        result_df = pd.read_csv(csv_path)
        assert result_df[COL_OPEN].iloc[0] == pytest.approx(100.123457, abs=1e-6)
