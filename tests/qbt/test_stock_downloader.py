"""
stock_downloader 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 주식 데이터 유효성 검증이 정확히 작동하는가? (결측치, 0값, 음수, 급등락)
2. 정상 데이터가 검증을 통과하는가?
3. 시세 저장 함수가 반올림 → 검증 → 저장 순서를 지키는가? (검증에 걸리면 파일을 쓰지 않는다)
4. Yahoo Finance 다운로드 + 전처리 + 저장 파이프라인이 작동하는가?
5. 빈 데이터 반환 시 명확한 에러를 내는가?
6. 받을 마지막 날이 기본(그저께) · `--end`(뉴욕에서 그날 봉이 끝나기 전인 날은 뺀다)대로 정해지는가?
7. 수정 가격이 yfinance auto_adjust 와 같은 식으로 계산되는가?
8. 기존 파일과의 판정대로 저장하는가? (흔들림 → 기존 행 유지 · 설명되는 변화 → 덮어씀 · 비정상 → 쓰지 않음)

왜 중요한가요?
데이터 품질은 백테스트 결과의 신뢰성을 결정합니다.
다운로드 시 검증을 통과하지 못한 데이터는 즉시 거부되어야 합니다.
"""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME, REQUIRED_COLUMNS
from qbt.utils import stock_downloader
from qbt.utils.price_revision import PriceRevision, RevisionKind
from qbt.utils.stock_downloader import (
    COL_ADJ_CLOSE,
    COL_DIVIDENDS,
    COL_STOCK_SPLITS,
    StockDownload,
    adjust_prices,
    confirm_overwrites,
    download_stock_data,
    resolve_cutoff_date,
    save_stock_csv,
    validate_stock_data,
)

SEOUL = ZoneInfo("Asia/Seoul")
CUTOFF = date(2023, 12, 29)  # 대역 응답의 모든 날 뒤


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

    def test_duplicate_dates_detected(self):
        """
        목적: 받은 시세에 같은 날짜가 두 번 있으면 저장 전에 멈춤을 검증 — 저장하면 그 파일을 읽는 모든 실행이 멈춘다

        Given: 둘째 행의 날짜를 첫 행과 같게 바꾼 데이터
        When: validate_stock_data 호출
        Then: ValueError 발생 + "중복 날짜 발견" 메시지
        """
        # Given
        df = _make_valid_df()
        df.loc[1, COL_DATE] = df.loc[0, COL_DATE]

        # When & Then
        with pytest.raises(ValueError, match="중복 날짜 발견"):
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


class TestSaveStockCsv:
    """시세 저장 함수 테스트 — 다운로더 · 대용 · 장기 대체 · TQQQ 합성이 같은 함수로 저장한다"""

    def test_rounds_prices_and_saves(self, tmp_path):
        """
        목적: 가격 열을 6자리로 반올림해 저장하고 원본은 바꾸지 않음을 검증

        Given: 소수점이 긴 가격의 정상 데이터
        When: save_stock_csv 호출 (상위 폴더가 없는 경로)
        Then: 폴더를 만들어 저장하고, 저장된 가격은 6자리 · 원본 DataFrame 은 그대로
        """
        # Given
        df = _make_valid_df(rows=2)
        df.loc[0, COL_OPEN] = 100.1234567
        path = tmp_path / "sub" / "TEST_max.csv"

        # When
        save_stock_csv(df, path)

        # Then
        saved = pd.read_csv(path)
        assert saved[COL_OPEN].iloc[0] == pytest.approx(100.123457, abs=1e-9)
        assert df.loc[0, COL_OPEN] == 100.1234567

    @pytest.mark.parametrize("check_price_spikes", [True, False])
    def test_missing_price_is_not_saved(self, tmp_path, check_price_spikes):
        """
        목적: 가격 결측이 있으면 급등락 검사 여부와 상관없이 저장하지 않고 멈춤을 검증 —
              TQQQ 합성처럼 급등락 검사를 끈 저장도 시세 표 검사는 한다

        Given: 종가 하나가 결측인 데이터
        When: save_stock_csv 호출
        Then: ValueError, 파일이 생기지 않음
        """
        # Given
        df = _make_valid_df()
        df.loc[2, COL_CLOSE] = np.nan
        path = tmp_path / "TEST_max.csv"

        # When & Then
        with pytest.raises(ValueError, match="결측치 발견"):
            save_stock_csv(df, path, check_price_spikes=check_price_spikes)
        assert not path.exists()

    def test_price_spike_blocks_save_by_default(self, tmp_path):
        """
        목적: 기본값은 급등락 검사까지 해서 하루 급등락이 있으면 저장하지 않음을 검증

        Given: 하루 약 94% 오르는 데이터
        When: save_stock_csv 호출 (기본값)
        Then: ValueError, 파일이 생기지 않음
        """
        # Given
        df = _make_valid_df()
        df.loc[1, COL_CLOSE] = 200.0
        path = tmp_path / "TEST_max.csv"

        # When & Then
        with pytest.raises(ValueError, match="급등락 감지"):
            save_stock_csv(df, path)
        assert not path.exists()

    def test_price_spike_saved_when_spike_check_off(self, tmp_path):
        """
        목적: 급등락 검사를 끄면 급등락이 있는 정상 합성 시세를 저장함을 검증 (3배 합성은 하루 50% 를 넘는 날이 있다)

        Given: 하루 약 94% 오르는 데이터
        When: save_stock_csv(check_price_spikes=False)
        Then: 저장된다
        """
        # Given
        df = _make_valid_df()
        df.loc[1, COL_CLOSE] = 200.0
        path = tmp_path / "TEST_max.csv"

        # When
        save_stock_csv(df, path, check_price_spikes=False)

        # Then
        assert pd.read_csv(path)[COL_CLOSE].iloc[1] == 200.0


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

    def _make_yfinance_df(
        self,
        adj_close: list[float] | None = None,
        dividends: list[float] | None = None,
    ) -> pd.DataFrame:
        """
        yfinance history(auto_adjust=False)가 반환하는 형식의 DataFrame을 생성한다.

        yfinance는 Date를 인덱스로 반환한다.
        최근 2일 필터링을 피하기 위해 과거 날짜를 사용한다.

        Args:
            adj_close: 수정 종가 (None 이면 원시 종가와 같다 — 배당 · 분할 없음)
            dividends: 날마다 배당 (None 이면 0)

        Returns:
            yfinance 형식의 DataFrame (Date가 인덱스)
        """
        dates = pd.to_datetime([date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)])
        closes = [103.0, 104.0, 105.0]
        df = pd.DataFrame(
            {
                COL_OPEN: [100.0, 101.0, 102.0],
                COL_HIGH: [105.0, 106.0, 107.0],
                COL_LOW: [99.0, 100.0, 101.0],
                COL_CLOSE: closes,
                COL_ADJ_CLOSE: adj_close if adj_close is not None else closes,
                COL_VOLUME: [1000000, 1100000, 1200000],
                COL_DIVIDENDS: dividends if dividends is not None else [0.0, 0.0, 0.0],
                COL_STOCK_SPLITS: [0.0, 0.0, 0.0],
            },
            index=dates,
        )
        df.index.name = COL_DATE
        return df

    def _save_existing(self, tmp_path: Path, rows: int) -> Path:
        """배당 · 분할 없는 대역 응답의 앞 rows 행을 기존 파일로 저장한다."""
        existing = self._make_yfinance_df().reset_index().iloc[:rows]
        existing[COL_DATE] = existing[COL_DATE].dt.date
        path = tmp_path / "TEST_max.csv"
        save_stock_csv(existing[REQUIRED_COLUMNS], path)
        return path

    def test_download_max_period(self, monkeypatch, tmp_path):
        """
        전체 기간 다운로드 테스트

        Given: yfinance가 정상 데이터를 반환하도록 모킹, 기존 파일 없음
        When: download_stock_data("TEST", 기준일) 호출
        Then:
          - CSV 파일이 생성됨 (판정 NEW)
          - 파일명이 TEST_max.csv
          - 데이터 행 수가 올바름
        """
        # Given: yfinance 모킹 + STOCK_DIR 패치
        mock_df = self._make_yfinance_df()
        self._mock_yfinance(monkeypatch, mock_df)
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        result = download_stock_data("TEST", CUTOFF)

        # Then
        assert result.revision.kind is RevisionKind.NEW
        csv_path = result.path
        assert csv_path.exists(), "CSV 파일이 생성되어야 합니다"
        assert csv_path.name == "TEST_max.csv", "파일명이 올바르지 않습니다"

        result_df = pd.read_csv(csv_path)
        assert len(result_df) == 3, "3행이 저장되어야 합니다"

    def test_rows_after_cutoff_are_excluded(self, monkeypatch, tmp_path):
        """
        목적: 받을 마지막 날 뒤의 행은 저장하지 않는다

        Given: 2023-01-02 ~ 01-04 응답, 기존 파일 없음
        When: download_stock_data("TEST", 2023-01-03)
        Then: 2행 저장, 마지막 날 2023-01-03
        """
        # Given
        self._mock_yfinance(monkeypatch, self._make_yfinance_df())
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        result = download_stock_data("TEST", date(2023, 1, 3))

        # Then
        saved = pd.read_csv(result.path)
        assert len(saved) == 2
        assert saved[COL_DATE].iloc[-1] == "2023-01-03"

    def test_noise_keeps_existing_rows(self, monkeypatch, tmp_path):
        """
        목적: 흔들림뿐이면 기존 파일의 행은 글자 그대로 두고 새 날짜 행만 붙인다

        Given: 기존 파일 2행, 응답 3행 = 수정 종가가 상대 +4e-6 흔들린 같은 시세
        When: download_stock_data
        Then: NOISE, 파일의 머리 · 기존 2행이 글자 그대로, 3행째가 붙는다
        """
        # Given
        path = self._save_existing(tmp_path, rows=2)
        before = path.read_text().splitlines()
        self._mock_yfinance(monkeypatch, self._make_yfinance_df(adj_close=[103.000412, 104.000416, 105.00042]))
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        result = download_stock_data("TEST", CUTOFF)

        # Then
        assert result.revision.kind is RevisionKind.NOISE
        after = path.read_text().splitlines()
        assert after[:3] == before
        assert len(after) == 4

    def test_explained_change_overwrites_file(self, monkeypatch, tmp_path):
        """
        목적: 응답의 배당 기록으로 설명되는 변화면 응답으로 덮어쓴다

        Given: 기존 파일 3행(배당 없음), 응답 = 2023-01-04 배당 $0.50 기록과 앞 2행에 (1 − 0.50 ÷ 104) 가 반영된 수정 종가
        When: download_stock_data
        Then: EXPLAINED, 파일 첫 행 종가 = 103 × (1 − 0.5 ÷ 104) (6자리)
        """
        # Given
        self._save_existing(tmp_path, rows=3)
        factor = 1 - 0.5 / 104.0
        self._mock_yfinance(
            monkeypatch,
            self._make_yfinance_df(adj_close=[103.0 * factor, 104.0 * factor, 105.0], dividends=[0.0, 0.0, 0.5]),
        )
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        result = download_stock_data("TEST", CUTOFF)

        # Then
        assert result.revision.kind is RevisionKind.EXPLAINED
        saved = pd.read_csv(result.path)
        assert saved[COL_CLOSE].iloc[0] == pytest.approx(round(103.0 * factor, 6), abs=1e-9)

    def test_abnormal_does_not_write_file(self, monkeypatch, tmp_path):
        """
        목적: 비정상이면 파일을 쓰지 않고, 덮어쓸 때 쓸 응답을 판정에 담는다

        Given: 기존 파일 3행, 응답 = 첫 행 수정 종가만 +0.4% (기록 없음)
        When: download_stock_data
        Then: ABNORMAL, 파일이 글자 그대로, 판정의 저장할 표 첫 행 종가 = 103 × 1.004
        """
        # Given
        path = self._save_existing(tmp_path, rows=3)
        before = path.read_text()
        self._mock_yfinance(monkeypatch, self._make_yfinance_df(adj_close=[103.0 * 1.004, 104.0, 105.0]))
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        result = download_stock_data("TEST", CUTOFF)

        # Then
        assert result.revision.kind is RevisionKind.ABNORMAL
        assert path.read_text() == before
        assert result.revision.prices[COL_CLOSE].iloc[0] == pytest.approx(103.0 * 1.004, abs=1e-9)

    def test_existing_end_after_cutoff_is_kept(self, monkeypatch, tmp_path):
        """
        목적: 기존 파일이 기준일보다 뒤까지 있으면 기존 끝날까지 견준다 — `--end` 로 받아 둔 끝 행을
              기본 기준(그저께)으로 다시 받을 때 「날짜가 사라졌다」로 오탐하지 않는다

        Given: 기존 파일 3행(~ 2023-01-04), 같은 응답, 기준일 2023-01-03
        When: download_stock_data
        Then: NOISE, 파일 3행 그대로
        """
        # Given
        path = self._save_existing(tmp_path, rows=3)
        before = path.read_text()
        self._mock_yfinance(monkeypatch, self._make_yfinance_df())
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        result = download_stock_data("TEST", date(2023, 1, 3))

        # Then
        assert result.revision.kind is RevisionKind.NOISE
        assert path.read_text() == before

    def test_missing_action_columns_raises(self, monkeypatch, tmp_path):
        """
        목적: 응답에 수정 종가 · 배당 · 분할 열이 없으면 판정할 수 없어 멈춘다

        Given: Dividends 열이 없는 응답
        When: download_stock_data
        Then: ValueError (열 이름 포함)
        """
        # Given
        self._mock_yfinance(monkeypatch, self._make_yfinance_df().drop(columns=[COL_DIVIDENDS]))
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When & Then
        with pytest.raises(ValueError, match=COL_DIVIDENDS):
            download_stock_data("TEST", CUTOFF)

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
            download_stock_data("INVALID_TICKER", CUTOFF)

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
                COL_ADJ_CLOSE: [103.1234567, 104.9876543],
                COL_VOLUME: [1000000, 1100000],
                COL_DIVIDENDS: [0.0, 0.0],
                COL_STOCK_SPLITS: [0.0, 0.0],
            },
            index=dates,
        )
        mock_df.index.name = COL_DATE
        self._mock_yfinance(monkeypatch, mock_df)
        monkeypatch.setattr("qbt.utils.stock_downloader.STOCK_DIR", tmp_path)

        # When
        csv_path = download_stock_data("TEST", CUTOFF).path

        # Then: 소수점 6자리로 라운딩 확인
        result_df = pd.read_csv(csv_path)
        assert result_df[COL_OPEN].iloc[0] == pytest.approx(100.123457, abs=1e-9)


class TestResolveCutoffDate:
    """받을 마지막 날 — 인자 없으면 그저께, `--end` 는 뉴욕에서 그날 봉이 끝나기 전인 날을 뺀다"""

    def test_default_is_two_days_before_today(self):
        """
        목적: `--end` 가 없으면 실행한 날(현지)에서 2일 전까지 — 지금까지의 기준 그대로

        Given: 지금 2026-11-07 20:00 KST
        When: resolve_cutoff_date(None, 지금)
        Then: 2026-11-05
        """
        # Given
        now = datetime(2026, 11, 7, 20, 0, tzinfo=SEOUL)

        # When & Then
        assert resolve_cutoff_date(None, now) == date(2026, 11, 5)

    def test_past_end_date_is_kept(self):
        """
        목적: 이미 마감된 날을 주면 그날까지

        Given: 지금 2026-11-07 20:00 KST, --end 2026-11-03
        When: resolve_cutoff_date
        Then: 2026-11-03
        """
        # Given
        now = datetime(2026, 11, 7, 20, 0, tzinfo=SEOUL)

        # When & Then
        assert resolve_cutoff_date(date(2026, 11, 3), now) == date(2026, 11, 3)

    @pytest.mark.parametrize(
        ("utc_now", "expected"),
        [
            (datetime(2026, 11, 6, 21, 30, tzinfo=UTC), date(2026, 11, 5)),  # 뉴욕 16:30 EST — 주식은 끝, 금 선물은 거래 중
            (datetime(2026, 11, 6, 22, 59, tzinfo=UTC), date(2026, 11, 5)),  # 뉴욕 17:59 EST — 그날 봉이 끝나기 전
            (datetime(2026, 11, 6, 23, 0, tzinfo=UTC), date(2026, 11, 6)),  # 뉴욕 18:00 EST — 그날 봉이 다 끝남
            (datetime(2026, 7, 1, 21, 59, tzinfo=UTC), date(2026, 6, 30)),  # 뉴욕 17:59 EDT — 서머타임, 끝나기 전
            (datetime(2026, 7, 1, 22, 0, tzinfo=UTC), date(2026, 7, 1)),  # 뉴욕 18:00 EDT — 서머타임, 다 끝남
        ],
    )
    def test_today_is_capped_by_new_york_day_end(self, utc_now, expected):
        """
        목적: 한국에서 `--end` 에 오늘을 주면 뉴욕에서 그날 봉이 다 끝난 마지막 날까지 — 거래 중인 봉을 저장하지 않는다.
              주식이 끝난 뒤에도 금 선물(GC=F)은 거래 중이라 그 사이는 뺀다. 서머타임 경계도 시간대 자료로 맞게 가른다

        Given: 한국 시각으로 바꾼 지금, --end = 그 한국 날짜(오늘)
        When: resolve_cutoff_date
        Then: 뉴욕 18:00 전이면 뉴욕 어제, 이후면 뉴욕 오늘
        """
        # Given
        now = utc_now.astimezone(SEOUL)

        # When & Then
        assert resolve_cutoff_date(now.date(), now) == expected

    def test_future_end_date_raises(self):
        """
        목적: 오늘보다 뒤의 날은 받을 수 없어 멈춘다 — 오타를 조용히 오늘로 바꾸지 않는다

        Given: 지금 2026-11-07 20:00 KST, --end 2026-11-08
        When: resolve_cutoff_date
        Then: ValueError (「오늘」 포함)
        """
        # Given
        now = datetime(2026, 11, 7, 20, 0, tzinfo=SEOUL)

        # When & Then
        with pytest.raises(ValueError, match="오늘"):
            resolve_cutoff_date(date(2026, 11, 8), now)

    def test_naive_now_raises(self):
        """
        목적: 시간대 없는 시각은 뉴욕 마감을 가를 수 없어 멈춘다

        Given: 시간대 없는 지금
        When: resolve_cutoff_date
        Then: ValueError (「시간대」 포함)
        """
        # When & Then
        with pytest.raises(ValueError, match="시간대"):
            resolve_cutoff_date(None, datetime(2026, 11, 7, 20, 0))

    def test_missing_new_york_zone_raises_with_guidance(self, monkeypatch):
        """
        목적: 뉴욕 시간대 자료가 없는 컴퓨터에서는 무엇을 설치할지 알리고 멈춘다

        Given: ZoneInfo 가 ZoneInfoNotFoundError 를 내도록 바꿈
        When: resolve_cutoff_date(--end 있음)
        Then: ZoneInfoNotFoundError (「뉴욕 시간대」 · 「tzdata」 포함)
        """

        # Given
        def missing_zone(_key: str) -> ZoneInfo:
            raise ZoneInfoNotFoundError("없음")

        monkeypatch.setattr(stock_downloader, "ZoneInfo", missing_zone)
        now = datetime(2026, 11, 7, 20, 0, tzinfo=SEOUL)

        # When & Then
        with pytest.raises(ZoneInfoNotFoundError, match="뉴욕 시간대.*tzdata"):
            resolve_cutoff_date(date(2026, 11, 6), now)


class TestAdjustPrices:
    """수정 가격 — yfinance auto_adjust 와 같은 식"""

    def test_scales_open_high_low_by_adj_close_ratio(self):
        """
        목적: 시가 · 고가 · 저가 × (수정 종가 ÷ 원시 종가), 종가 = 수정 종가, 거래량 그대로 — auto_adjust=True 로 받던 값과 같다

        Given: 원시 시가 101 · 고가 102 · 저가 99 · 종가 100, 수정 종가 98, 거래량 5000
        When: adjust_prices
        Then: 열 = REQUIRED_COLUMNS, 시가 98.98 · 고가 99.96 · 저가 97.02 · 종가 98.0 · 거래량 5000 (손 계산)
        """
        # Given
        raw = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 2)],
                COL_OPEN: [101.0],
                COL_HIGH: [102.0],
                COL_LOW: [99.0],
                COL_CLOSE: [100.0],
                COL_ADJ_CLOSE: [98.0],
                COL_VOLUME: [5000],
                COL_DIVIDENDS: [0.0],
                COL_STOCK_SPLITS: [0.0],
            }
        )

        # When
        adjusted = adjust_prices(raw)

        # Then
        assert list(adjusted.columns) == REQUIRED_COLUMNS
        row = adjusted.iloc[0]
        assert row[COL_OPEN] == pytest.approx(98.98, abs=1e-12)
        assert row[COL_HIGH] == pytest.approx(99.96, abs=1e-12)
        assert row[COL_LOW] == pytest.approx(97.02, abs=1e-12)
        assert row[COL_CLOSE] == 98.0
        assert row[COL_VOLUME] == 5000


def _download_with_kind(tmp_path: Path, ticker: str, kind: RevisionKind) -> StockDownload:
    """기존 파일(종가 103 · 104)과, 덮어쓰면 저장될 응답(종가 110 · 111)을 가진 판정."""
    path = tmp_path / f"{ticker}_max.csv"
    existing = _make_valid_df(rows=2)
    save_stock_csv(existing, path)
    response = existing.copy()
    response[COL_CLOSE] = [110.0, 111.0]
    revision = PriceRevision(
        kind=kind,
        prices=response,
        issues=("사건",),
        applied=(),
        existing_end=existing[COL_DATE].iloc[-1],
        existing_rows=2,
        response_end=response[COL_DATE].iloc[-1],
        response_rows=2,
        recent_dividends=(),
    )
    return StockDownload(ticker=ticker, path=path, revision=revision)


class TestConfirmOverwrites:
    """비정상 종목의 덮어쓰기 동의 — 사용자가 y 라고 답한 종목만 저장한다"""

    @pytest.mark.parametrize(
        ("answer", "overwritten"),
        [("y\n", True), ("Y\n", True), (" y \n", True), ("yes\n", False), ("n\n", False), ("\n", False), ("", False)],
    )
    def test_only_y_overwrites(self, tmp_path: Path, answer: str, overwritten: bool) -> None:
        """
        목적: 답이 y · Y(앞뒤 공백 무시)일 때만 응답으로 덮어쓴다 — yes · 빈 답(Enter) · EOF(빈 문자열)는 그대로 둔다

        Given: 비정상 판정 1종목, 정해진 답을 돌려주는 ask
        When: confirm_overwrites
        Then: 묻지 못한 것이 아니므로 False, 파일이 바뀐 여부 = overwritten
        """
        # Given
        download = _download_with_kind(tmp_path, "TEST", RevisionKind.ABNORMAL)
        before = download.path.read_text()

        # When
        unanswered = confirm_overwrites([download], lambda _question: answer)

        # Then
        assert unanswered is False
        assert (download.path.read_text() != before) is overwritten

    def test_no_terminal_does_not_ask_or_write(self, tmp_path: Path) -> None:
        """
        목적: 터미널이 아니면(ask 없음) 묻지 않고 아무것도 덮어쓰지 않는다 — 동의 없이 덮어쓰지 않는 관문

        Given: 비정상 판정 2종목, ask = None
        When: confirm_overwrites
        Then: True(묻지 못함), 두 파일 모두 그대로
        """
        # Given
        downloads = [_download_with_kind(tmp_path, ticker, RevisionKind.ABNORMAL) for ticker in ("AAA", "BBB")]
        before = [download.path.read_text() for download in downloads]

        # When
        unanswered = confirm_overwrites(downloads, None)

        # Then
        assert unanswered is True
        assert [download.path.read_text() for download in downloads] == before

    def test_asks_each_ticker_and_applies_each_answer(self, tmp_path: Path) -> None:
        """
        목적: 종목마다 따로 묻고 그 종목의 답만 따른다

        Given: 비정상 판정 AAA · BBB, AAA 에는 y · BBB 에는 n 을 답하는 ask
        When: confirm_overwrites
        Then: 질문 2개가 AAA · BBB 순서, AAA 만 바뀜
        """
        # Given
        downloads = [_download_with_kind(tmp_path, ticker, RevisionKind.ABNORMAL) for ticker in ("AAA", "BBB")]
        before = [download.path.read_text() for download in downloads]
        questions: list[str] = []

        def ask(question: str) -> str:
            questions.append(question)
            return "y\n" if question.startswith("AAA") else "n\n"

        # When
        confirm_overwrites(downloads, ask)

        # Then
        assert [question.split(" ")[0] for question in questions] == ["AAA", "BBB"]
        assert downloads[0].path.read_text() != before[0]
        assert downloads[1].path.read_text() == before[1]

    def test_rejects_non_abnormal(self, tmp_path: Path) -> None:
        """
        목적: 비정상이 아닌 종목은 묻는 대상이 아니라 멈춘다 — 이미 저장된 종목을 다시 덮어쓰게 하지 않는다

        Given: 흔들림 판정 1종목
        When: confirm_overwrites
        Then: ValueError (「비정상」 포함)
        """
        # Given
        download = _download_with_kind(tmp_path, "TEST", RevisionKind.NOISE)

        # When & Then
        with pytest.raises(ValueError, match="비정상"):
            confirm_overwrites([download], lambda _question: "y\n")
