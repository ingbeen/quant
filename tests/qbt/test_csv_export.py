"""백테스트 CSV 저장 유틸리티 테스트

이 파일은 무엇을 검증하나요?
1. prepare_trades_for_csv(): holding_days 계산, 반올림, 정수 변환
2. add_ohlc_change_pct(): OHLC 4종 전일대비 변동률(%) 계산
3. add_buffer_zone_bands(): buffer_zone 전략의 upper/lower 밴드 컬럼 추가

왜 중요한가요?
trades CSV / signal CSV 저장 로직이 여러 스크립트에 중복되어 있었으며,
공용 함수로 추출한 뒤 동일한 동작을 보장해야 합니다.
또한 대시보드(`scripts/backtest/app_*.py`)가 직접 도메인 연산을 수행하지 않도록,
CSV 저장 단계에서 사전 계산하는 SSoT를 유지하는 것이 핵심입니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.constants import ROUND_CAPITAL, ROUND_PRICE, ROUND_RATIO
from qbt.backtest.csv_export import (
    BUFFER_BAND_COLUMNS,
    OHLC_CHANGE_PCT_COLUMNS,
    add_buffer_zone_bands,
    add_ohlc_change_pct,
    prepare_trades_for_csv,
)


class TestPrepareTradeCsv:
    """prepare_trades_for_csv 함수 테스트"""

    def test_holding_days_calculated(self):
        """
        목적: entry_date/exit_date로부터 holding_days가 정확히 계산됨을 검증

        Given: entry_date=2023-01-02, exit_date=2023-01-05 (3일 차이)
        When: prepare_trades_for_csv 호출
        Then: holding_days=3
        """
        # Given
        trades = pd.DataFrame(
            {
                "entry_date": [date(2023, 1, 2)],
                "exit_date": [date(2023, 1, 5)],
                "entry_price": [100.123456789],
                "exit_price": [105.987654321],
                "pnl": [5864.123],
                "pnl_pct": [0.058641],
            }
        )

        # When
        result = prepare_trades_for_csv(trades)

        # Then
        assert "holding_days" in result.columns
        assert result.iloc[0]["holding_days"] == 3

    def test_rounding_applied(self):
        """
        목적: ROUND_* 상수에 따라 반올림이 적용됨을 검증

        Given: 소수점이 많은 가격/금액 데이터
        When: prepare_trades_for_csv 호출
        Then: entry_price -> ROUND_PRICE, pnl -> ROUND_CAPITAL, pnl_pct -> ROUND_RATIO
        """
        # Given
        trades = pd.DataFrame(
            {
                "entry_date": [date(2023, 1, 2)],
                "exit_date": [date(2023, 1, 5)],
                "entry_price": [100.123456789],
                "exit_price": [105.987654321],
                "pnl": [5864.567],
                "pnl_pct": [0.058641234],
            }
        )

        # When
        result = prepare_trades_for_csv(trades)

        # Then
        assert result.iloc[0]["entry_price"] == pytest.approx(round(100.123456789, ROUND_PRICE), abs=1e-8)
        assert result.iloc[0]["exit_price"] == pytest.approx(round(105.987654321, ROUND_PRICE), abs=1e-8)
        assert result.iloc[0]["pnl_pct"] == pytest.approx(round(0.058641234, ROUND_RATIO), abs=1e-8)

    def test_pnl_int_conversion(self):
        """
        목적: pnl 컬럼이 정수로 변환됨을 검증

        Given: pnl=5864.567
        When: prepare_trades_for_csv 호출
        Then: pnl은 정수형 (ROUND_CAPITAL=0이므로 5865 반올림 후 int)
        """
        # Given
        trades = pd.DataFrame(
            {
                "entry_date": [date(2023, 1, 2)],
                "exit_date": [date(2023, 1, 5)],
                "pnl": [5864.567],
            }
        )

        # When
        result = prepare_trades_for_csv(trades)

        # Then
        assert result.iloc[0]["pnl"] == round(5864.567, ROUND_CAPITAL)
        import numpy as np

        assert isinstance(result.iloc[0]["pnl"], int | np.integer)

    def test_empty_dataframe_returns_empty(self):
        """
        목적: 빈 DataFrame 입력 시 빈 DataFrame 반환을 검증

        Given: 빈 trades DataFrame
        When: prepare_trades_for_csv 호출
        Then: 빈 DataFrame 반환 (에러 없음)
        """
        # Given
        trades = pd.DataFrame(columns=["entry_date", "exit_date", "pnl"])

        # When
        result = prepare_trades_for_csv(trades)

        # Then
        assert result.empty

    def test_original_not_modified(self):
        """
        목적: 원본 DataFrame이 변경되지 않음을 검증 (데이터 불변성)

        Given: trades DataFrame
        When: prepare_trades_for_csv 호출
        Then: 원본 trades에 holding_days 컬럼 없음
        """
        # Given
        trades = pd.DataFrame(
            {
                "entry_date": [date(2023, 1, 2)],
                "exit_date": [date(2023, 1, 5)],
                "pnl": [1000.0],
            }
        )

        # When
        prepare_trades_for_csv(trades)

        # Then
        assert "holding_days" not in trades.columns

    def test_buy_buffer_pct_rounded(self):
        """
        목적: buy_buffer_pct 컬럼이 ROUND_RATIO로 반올림됨을 검증

        Given: buy_buffer_pct가 포함된 trades
        When: prepare_trades_for_csv 호출
        Then: buy_buffer_pct가 ROUND_RATIO 자릿수로 반올림
        """
        # Given
        trades = pd.DataFrame(
            {
                "entry_date": [date(2023, 1, 2)],
                "exit_date": [date(2023, 1, 5)],
                "pnl": [1000.0],
                "buy_buffer_pct": [0.030123456],
            }
        )

        # When
        result = prepare_trades_for_csv(trades)

        # Then
        assert result.iloc[0]["buy_buffer_pct"] == pytest.approx(round(0.030123456, ROUND_RATIO), abs=1e-8)


class TestAddOhlcChangePct:
    """add_ohlc_change_pct 함수 테스트"""

    def test_four_columns_added(self):
        """
        목적: open/high/low/close 4종 % 컬럼이 모두 추가됨을 검증

        Given: 정상 OHLC DataFrame
        When: add_ohlc_change_pct 호출
        Then: 4종 컬럼이 모두 존재
        """
        # Given
        df = pd.DataFrame(
            {
                "Open": [100.0, 102.0],
                "High": [101.0, 103.0],
                "Low": [99.0, 101.0],
                "Close": [100.0, 102.0],
            }
        )

        # When
        result = add_ohlc_change_pct(df)

        # Then
        for col in OHLC_CHANGE_PCT_COLUMNS:
            assert col in result.columns

    def test_first_row_is_nan(self):
        """
        목적: 첫 행은 비교 대상이 없어 NaN이 됨을 검증

        Given: 2행 OHLC DataFrame
        When: add_ohlc_change_pct 호출
        Then: 첫 행 4종 % 모두 NaN
        """
        # Given
        df = pd.DataFrame(
            {
                "Open": [100.0, 102.0],
                "High": [101.0, 103.0],
                "Low": [99.0, 101.0],
                "Close": [100.0, 102.0],
            }
        )

        # When
        result = add_ohlc_change_pct(df)

        # Then
        for col in OHLC_CHANGE_PCT_COLUMNS:
            assert pd.isna(result.iloc[0][col])

    def test_close_pct_matches_pct_change(self):
        """
        목적: close_pct가 종가 기준 전일대비 변동률과 일치함을 검증

        Given: 종가 [100, 110, 99] → 변동률 [NaN, +10%, -10%]
        When: add_ohlc_change_pct 호출
        Then: close_pct가 [NaN, 10.0, -10.0]
        """
        # Given
        df = pd.DataFrame(
            {
                "Open": [100.0, 110.0, 99.0],
                "High": [100.0, 110.0, 99.0],
                "Low": [100.0, 110.0, 99.0],
                "Close": [100.0, 110.0, 99.0],
            }
        )

        # When
        result = add_ohlc_change_pct(df)

        # Then
        assert result.iloc[1]["close_pct"] == pytest.approx(10.0, abs=1e-6)
        assert result.iloc[2]["close_pct"] == pytest.approx(-10.0, abs=1e-6)

    def test_open_high_low_pct_use_prev_close(self):
        """
        목적: open/high/low %도 동일한 전일 종가를 분모로 사용함을 검증

        Given: 첫날 종가=100, 둘째날 OHLC=(105, 110, 95, 102)
        When: add_ohlc_change_pct 호출
        Then: 둘째날 4종 %가 (5%, 10%, -5%, 2%)
        """
        # Given
        df = pd.DataFrame(
            {
                "Open": [100.0, 105.0],
                "High": [100.0, 110.0],
                "Low": [100.0, 95.0],
                "Close": [100.0, 102.0],
            }
        )

        # When
        result = add_ohlc_change_pct(df)

        # Then
        assert result.iloc[1]["open_pct"] == pytest.approx(5.0, abs=1e-6)
        assert result.iloc[1]["high_pct"] == pytest.approx(10.0, abs=1e-6)
        assert result.iloc[1]["low_pct"] == pytest.approx(-5.0, abs=1e-6)
        assert result.iloc[1]["close_pct"] == pytest.approx(2.0, abs=1e-6)

    def test_empty_dataframe_returns_empty_with_columns(self):
        """
        목적: 빈 DataFrame 입력 시 컬럼만 추가된 빈 DataFrame을 반환함을 검증

        Given: 빈 OHLC DataFrame
        When: add_ohlc_change_pct 호출
        Then: empty=True + 4종 % 컬럼 존재
        """
        # Given
        df = pd.DataFrame(columns=["Open", "High", "Low", "Close"])

        # When
        result = add_ohlc_change_pct(df)

        # Then
        assert result.empty
        for col in OHLC_CHANGE_PCT_COLUMNS:
            assert col in result.columns

    def test_missing_column_raises(self):
        """
        목적: 필수 OHLC 컬럼이 누락되면 ValueError 발생을 검증

        Given: Close 컬럼이 누락된 DataFrame
        When: add_ohlc_change_pct 호출
        Then: ValueError 발생
        """
        # Given
        df = pd.DataFrame({"Open": [100.0], "High": [101.0], "Low": [99.0]})

        # When / Then
        with pytest.raises(ValueError, match="필수 컬럼"):
            add_ohlc_change_pct(df)

    def test_original_not_modified(self):
        """
        목적: 원본 DataFrame이 변경되지 않음을 검증 (데이터 불변성)

        Given: OHLC DataFrame
        When: add_ohlc_change_pct 호출
        Then: 원본에 % 컬럼이 추가되지 않음
        """
        # Given
        df = pd.DataFrame(
            {
                "Open": [100.0, 102.0],
                "High": [101.0, 103.0],
                "Low": [99.0, 101.0],
                "Close": [100.0, 102.0],
            }
        )

        # When
        add_ohlc_change_pct(df)

        # Then
        for col in OHLC_CHANGE_PCT_COLUMNS:
            assert col not in df.columns


class TestAddBufferZoneBands:
    """add_buffer_zone_bands 함수 테스트"""

    def test_bands_calculated(self):
        """
        목적: 산식 (ma * (1 ± buffer))이 정확히 적용됨을 검증

        Given: ma_200=100, buy_buffer=0.03, sell_buffer=0.05
        When: add_buffer_zone_bands 호출
        Then: upper_band=103, lower_band=95
        """
        # Given
        df = pd.DataFrame({"Close": [100.0], "ma_200": [100.0]})

        # When
        result = add_buffer_zone_bands(df, "ma_200", buy_buffer_zone_pct=0.03, sell_buffer_zone_pct=0.05)

        # Then
        assert result.iloc[0]["upper_band"] == pytest.approx(103.0, abs=1e-9)
        assert result.iloc[0]["lower_band"] == pytest.approx(95.0, abs=1e-9)

    def test_band_columns_present(self):
        """
        목적: BUFFER_BAND_COLUMNS 상수와 컬럼명이 일치함을 검증

        Given: ma 컬럼 포함 DataFrame
        When: add_buffer_zone_bands 호출
        Then: BUFFER_BAND_COLUMNS의 모든 컬럼이 존재
        """
        # Given
        df = pd.DataFrame({"Close": [100.0], "ma_200": [100.0]})

        # When
        result = add_buffer_zone_bands(df, "ma_200", 0.03, 0.05)

        # Then
        for col in BUFFER_BAND_COLUMNS:
            assert col in result.columns

    def test_missing_ma_col_raises(self):
        """
        목적: ma_col이 DataFrame에 없으면 ValueError 발생을 검증

        Given: ma_200 컬럼이 없는 DataFrame
        When: add_buffer_zone_bands 호출
        Then: ValueError 발생
        """
        # Given
        df = pd.DataFrame({"Close": [100.0]})

        # When / Then
        with pytest.raises(ValueError, match="ma_col"):
            add_buffer_zone_bands(df, "ma_200", 0.03, 0.05)

    def test_original_not_modified(self):
        """
        목적: 원본 DataFrame이 변경되지 않음을 검증 (데이터 불변성)

        Given: ma 컬럼 포함 DataFrame
        When: add_buffer_zone_bands 호출
        Then: 원본에 밴드 컬럼이 추가되지 않음
        """
        # Given
        df = pd.DataFrame({"Close": [100.0], "ma_200": [100.0]})

        # When
        add_buffer_zone_bands(df, "ma_200", 0.03, 0.05)

        # Then
        for col in BUFFER_BAND_COLUMNS:
            assert col not in df.columns
