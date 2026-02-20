"""
data_loader 모듈 테스트

이 파일은 무엇을 검증하나요?
1. CSV 파일에서 데이터를 정확히 로드하는가?
2. 필수 컬럼이 없으면 즉시 실패하는가?
3. 날짜가 올바르게 파싱되고 정렬되는가?
4. 중복 날짜가 제거되고 경고 로그가 찍히는가?
5. 파일이 없을 때 명확한 에러를 내는가?
6. 두 DataFrame의 겹치는 기간이 정확히 추출되는가?

왜 중요한가요?
백테스트의 모든 결과는 입력 데이터에 의존합니다.
잘못된 데이터(정렬 안 됨, 중복, 누락)는 잘못된 매매 신호를 만들고,
결과적으로 신뢰할 수 없는 백테스트 결과를 초래합니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE
from qbt.utils.data_loader import extract_overlap_period, load_stock_data


class TestLoadStockData:
    """주식 데이터 로딩 테스트 클래스"""

    def test_normal_load(self, tmp_path, sample_stock_df):
        """
        정상적인 주식 데이터 로딩 테스트

        데이터 신뢰성: 기본 흐름이 정확히 작동해야 모든 후속 분석이 가능합니다.

        Given: 올바른 스키마의 CSV 파일
        When: load_stock_data 호출
        Then:
          - DataFrame이 반환됨
          - 필수 컬럼 모두 존재
          - Date가 datetime.date 타입
          - 날짜 오름차순 정렬
        """
        # Given: CSV 파일 생성
        csv_path = tmp_path / "AAPL_max.csv"
        sample_stock_df.to_csv(csv_path, index=False)

        # When: 데이터 로딩
        df = load_stock_data(csv_path)

        # Then: 스키마 검증
        assert isinstance(df, pd.DataFrame), "반환값은 DataFrame이어야 합니다"
        assert len(df) == 3, "행 수가 일치해야 합니다"

        # 필수 컬럼 존재 확인
        required = ["Date", "Open", "High", "Low", "Close", "Volume"]
        for col in required:
            assert col in df.columns, f"필수 컬럼 '{col}'이 없습니다"

        # 날짜 타입 확인 (이게 중요! datetime이 아니라 date여야 함)
        assert all(isinstance(d, date) for d in df["Date"]), "Date 컬럼은 datetime.date 타입이어야 합니다"

        # 정렬 확인
        dates = df["Date"].tolist()
        assert dates == sorted(dates), "날짜가 오름차순 정렬되어야 합니다"

    def test_file_not_found(self, tmp_path):
        """
        존재하지 않는 파일 처리 테스트

        안정성: 파일 부재 시 명확한 에러로 조기 실패해야 디버깅이 쉽습니다.

        Given: 존재하지 않는 파일 경로
        When: load_stock_data 호출
        Then: FileNotFoundError 발생
        """
        # Given: 존재하지 않는 경로
        non_existent_path = tmp_path / "no_such_file.csv"

        # When & Then: 예외 발생 확인
        with pytest.raises(FileNotFoundError) as exc_info:
            load_stock_data(non_existent_path)

        # 예외 메시지 확인 (실제 메시지: "파일을 찾을 수 없습니다")
        assert "찾을 수 없습니다" in str(exc_info.value), "에러 메시지가 명확해야 합니다"

    def test_missing_required_columns(self, tmp_path):
        """
        필수 컬럼 누락 시 실패 테스트

        데이터 신뢰성: 스키마가 깨진 데이터는 즉시 거부해야 합니다.

        Given: Close 컬럼이 없는 CSV
        When: load_stock_data 호출
        Then: ValueError 발생 + 누락 컬럼명 포함
        """
        # Given: Close 컬럼 제거
        incomplete_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 2)],
                "Open": [100.0],
                "High": [105.0],
                "Low": [99.0],
                "Volume": [1000000],
                # Close 컬럼 의도적으로 누락
            }
        )
        csv_path = tmp_path / "incomplete.csv"
        incomplete_df.to_csv(csv_path, index=False)

        # When & Then
        with pytest.raises(ValueError) as exc_info:
            load_stock_data(csv_path)

        error_msg = str(exc_info.value)
        assert "필수 컬럼" in error_msg, "에러 메시지에 '필수 컬럼'이 포함되어야 합니다"
        assert "Close" in error_msg, "누락된 컬럼명이 에러 메시지에 있어야 합니다"

    def test_duplicate_dates_removed(self, tmp_path, caplog, monkeypatch):
        """
        중복 날짜 제거 및 경고 로그 테스트

        데이터 신뢰성: 중복 날짜는 백테스트 로직을 망가뜨릴 수 있습니다.
        첫 번째 값만 유지하고, 사용자에게 경고해야 합니다.

        Given: 같은 날짜가 2번 나오는 CSV
        When: load_stock_data 호출
        Then:
          - 중복 제거되어 행 수 감소
          - WARNING 로그 발생 ("중복 날짜" 메시지 포함)
          - 첫 번째 값 유지 확인
        """
        import logging

        # 프로젝트 로거는 propagate=False로 설정되어 caplog이 캡처하지 못함
        # 테스트 중에만 propagate=True로 임시 변경
        target_logger = logging.getLogger("qbt.utils.data_loader")
        monkeypatch.setattr(target_logger, "propagate", True)

        # Given: 중복 날짜 데이터
        dup_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 2), date(2023, 1, 2), date(2023, 1, 3)],
                "Open": [100.0, 999.0, 102.0],  # 두 번째 행은 999로 다르게
                "High": [105.0, 999.0, 107.0],
                "Low": [99.0, 999.0, 101.0],
                "Close": [103.0, 999.0, 105.0],
                "Volume": [1000000, 9999999, 1200000],
            }
        )
        csv_path = tmp_path / "duplicate.csv"
        dup_df.to_csv(csv_path, index=False)

        # When: 로그 캡처하면서 로딩
        with caplog.at_level(logging.WARNING, logger="qbt.utils.data_loader"):
            df = load_stock_data(csv_path)

        # Then: 중복 제거 확인
        assert len(df) == 2, "중복 날짜 제거 후 2행이어야 합니다"

        # 첫 번째 값(100.0)이 유지되었는지 확인 (999.0이면 잘못됨)
        first_row = df[df["Date"] == date(2023, 1, 2)].iloc[0]
        assert first_row["Open"] == 100.0, "중복 시 첫 번째 값을 유지해야 합니다"

        # 경고 로그 검증: "중복 날짜" 메시지가 WARNING 레벨로 출력되었는지 확인
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("중복 날짜" in msg for msg in warning_messages), f"'중복 날짜' 경고 로그가 출력되어야 합니다. 캡처된 경고: {warning_messages}"

    def test_date_sorting(self, tmp_path):
        """
        날짜 정렬 테스트

        데이터 신뢰성: 백테스트는 시간 순서대로 진행되어야 합니다.
        역순 데이터는 자동 정렬되어야 합니다.

        Given: 날짜가 역순인 CSV
        When: load_stock_data 호출
        Then: 오름차순 정렬됨
        """
        # Given: 역순 데이터
        reversed_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 4), date(2023, 1, 2), date(2023, 1, 3)],
                "Open": [102.0, 100.0, 101.0],
                "High": [107.0, 105.0, 106.0],
                "Low": [101.0, 99.0, 100.0],
                "Close": [105.0, 103.0, 104.0],
                "Volume": [1200000, 1000000, 1100000],
            }
        )
        csv_path = tmp_path / "reversed.csv"
        reversed_df.to_csv(csv_path, index=False)

        # When
        df = load_stock_data(csv_path)

        # Then
        expected_dates = [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)]
        actual_dates = df["Date"].tolist()
        assert actual_dates == expected_dates, f"날짜가 정렬되어야 합니다. 기대: {expected_dates}, 실제: {actual_dates}"


class TestExtractOverlapPeriod:
    """겹치는 기간 추출 테스트"""

    def test_normal_overlap(self):
        """
        정상적인 겹치는 기간 추출 테스트

        데이터 신뢰성: 실제 데이터와 시뮬레이션 비교 시 같은 기간만 사용해야 합니다.

        Given:
          - simulated: 2023-01-01 ~ 2023-12-31
          - actual: 2023-06-01 ~ 2024-06-30
        When: extract_overlap_period
        Then: 2023-06-01 ~ 2023-12-31만 반환
        """
        # Given
        simulated_df = pd.DataFrame(
            {COL_DATE: pd.date_range(date(2023, 1, 1), date(2023, 12, 31), freq="D"), "Simulated_Close": range(365)}
        )

        actual_df = pd.DataFrame(
            {COL_DATE: pd.date_range(date(2023, 6, 1), date(2024, 6, 30), freq="D"), "Actual_Close": range(396)}
        )

        # When
        overlap_sim, overlap_actual = extract_overlap_period(simulated_df, actual_df)

        # Then: 2023-06-01 ~ 2023-12-31
        assert overlap_sim[COL_DATE].min() == pd.Timestamp(date(2023, 6, 1))
        assert overlap_sim[COL_DATE].max() == pd.Timestamp(date(2023, 12, 31))

        assert len(overlap_sim) == len(overlap_actual), "겹치는 기간의 행 수는 같아야 합니다"

    def test_no_overlap(self):
        """
        겹치는 기간이 없을 때 테스트

        안정성: 겹치는 날짜가 없으면 ValueError 발생

        Given: 완전히 다른 기간
        When: extract_overlap_period
        Then: ValueError
        """
        # Given
        simulated_df = pd.DataFrame({COL_DATE: [date(2020, 1, 1), date(2020, 1, 2)], COL_CLOSE: [100, 101]})

        actual_df = pd.DataFrame({COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)], COL_CLOSE: [200, 201]})

        # When & Then: ValueError 발생
        with pytest.raises(ValueError) as exc_info:
            extract_overlap_period(simulated_df, actual_df)

        assert "겹치는 기간이 없습니다" in str(exc_info.value)
