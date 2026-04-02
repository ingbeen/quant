"""백테스트 CSV 저장 유틸리티 테스트

이 파일은 무엇을 검증하나요?
1. prepare_trades_for_csv(): holding_days 계산, 반올림, 정수 변환
2. calculate_change_pct(): 전일대비 변동률(%) 계산

왜 중요한가요?
trades CSV 저장 로직이 3개 스크립트에 중복되어 있었으며,
공용 함수로 추출한 뒤 동일한 동작을 보장해야 합니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.constants import ROUND_CAPITAL, ROUND_PRICE, ROUND_RATIO
from qbt.backtest.csv_export import calculate_change_pct, prepare_trades_for_csv


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


class TestCalculateChangePct:
    """calculate_change_pct 함수 테스트"""

    def test_basic_change_pct(self):
        """
        목적: 전일대비 변동률이 정확히 계산됨을 검증

        Given: 종가 [100, 110, 99]
        When: calculate_change_pct 호출
        Then: [NaN, 10.0, -10.0]
        """
        # Given
        df = pd.DataFrame({"Close": [100.0, 110.0, 99.0]})

        # When
        result = calculate_change_pct(df)

        # Then
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == pytest.approx(10.0, abs=0.01)
        assert result.iloc[2] == pytest.approx(-10.0, abs=0.01)

    def test_custom_close_column(self):
        """
        목적: 사용자 정의 종가 컬럼명이 작동함을 검증

        Given: "price" 컬럼으로 종가 데이터
        When: calculate_change_pct(df, close_col="price") 호출
        Then: 정상 계산
        """
        # Given
        df = pd.DataFrame({"price": [100.0, 105.0]})

        # When
        result = calculate_change_pct(df, close_col="price")

        # Then
        assert result.iloc[1] == pytest.approx(5.0, abs=0.01)
