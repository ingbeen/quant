"""백테스트 CSV 저장 유틸리티 테스트

이 파일은 무엇을 검증하나요?
1. prepare_trades_for_csv(): holding_days 계산, 반올림, 정수 변환
2. add_ohlc_change_pct(): OHLC 4종 전일대비 변동률(%) 계산
3. add_buffer_zone_bands(): buffer_zone 전략의 upper/lower 밴드 컬럼 추가
4. enrich_equity_with_bands(): 에쿼티에 그날의 밴드 · 버퍼 비율 붙이기
5. round_signal_for_csv(): 시그널 CSV 저장 자릿수
6. remove_config_dependent_files(): 포트폴리오 결과 폴더의 구성 의존 파일 지우기

왜 중요한가요?
trades CSV / signal CSV 저장 로직이 여러 스크립트에 중복되어 있었으며,
공용 함수로 추출한 뒤 동일한 동작을 보장해야 합니다.
또한 대시보드(`scripts/backtest/app_*.py`)가 직접 도메인 연산을 수행하지 않도록,
CSV 저장 단계에서 사전 계산하는 SSoT를 유지하는 것이 핵심입니다.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from qbt.backtest.constants import (
    EQUITY_FILENAME,
    LEDGER_FILENAME,
    NETTING_FILENAME,
    SUMMARY_FILENAME,
    TRADES_FILENAME,
    portfolio_signal_filename,
)
from qbt.backtest.csv_export import (
    BUFFER_BAND_COLUMNS,
    OHLC_CHANGE_PCT_COLUMNS,
    add_buffer_zone_bands,
    add_ohlc_change_pct,
    enrich_equity_with_bands,
    prepare_trades_for_csv,
    remove_config_dependent_files,
    round_signal_for_csv,
)
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    ROUND_CAPITAL,
    ROUND_PERCENT,
    ROUND_PRICE,
    ROUND_RATIO,
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

    def test_empty_trades_get_same_columns_as_traded_result(self):
        """
        목적: 행이 없는 거래 표도 거래가 있는 표와 같은 열로 변환됨을 검증 —
              열이 다르면 거래가 없는 결과의 CSV 만 헤더가 달라지거나 헤더 없는 빈 파일이 된다

        Given: 열만 있고 행이 없는 trades
        When: prepare_trades_for_csv 호출
        Then: 빈 표이고, 열은 입력 열 뒤에 holding_days 가 붙는다
        """
        # Given
        trades = pd.DataFrame(columns=["entry_date", "exit_date", "pnl", "order_amount"])

        # When
        result = prepare_trades_for_csv(trades)

        # Then
        assert result.empty
        assert list(result.columns) == ["entry_date", "exit_date", "pnl", "order_amount", "holding_days"]

    def test_missing_entry_exit_columns_raise(self):
        """
        목적: 진입 · 청산 날짜 열이 없으면 보유 기간 열 없이 넘어가지 않고 멈춤을 검증 — 두 엔진의 거래 표는 늘 그 열을 갖는다

        Given: exit_date 열이 없는 trades
        When: prepare_trades_for_csv 호출
        Then: KeyError
        """
        # Given
        trades = pd.DataFrame({"entry_date": [date(2023, 1, 2)], "pnl": [1000.0]})

        # When & Then
        with pytest.raises(KeyError, match="exit_date"):
            prepare_trades_for_csv(trades)

    def test_order_amount_rounded_to_int(self):
        """
        목적: 포트폴리오 거래의 체결 금액(order_amount)이 자본금 자릿수(ROUND_CAPITAL)로 반올림된 정수가 됨을 검증

        Given: order_amount=1234567.891
        When: prepare_trades_for_csv 호출
        Then: 1234568, 정수형
        """
        # Given
        trades = pd.DataFrame(
            {
                "entry_date": [date(2023, 1, 2)],
                "exit_date": [date(2023, 1, 5)],
                "pnl": [1000.0],
                "order_amount": [1234567.891],
            }
        )

        # When
        result = prepare_trades_for_csv(trades)

        # Then
        assert result.iloc[0]["order_amount"] == 1234568
        assert isinstance(result.iloc[0]["order_amount"], int | np.integer)

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


class TestEnrichEquityWithBands:
    """enrich_equity_with_bands 함수 테스트"""

    def test_bands_and_buffers_joined_by_date(self):
        """
        목적: 그날 이동평균으로 만든 밴드와 버퍼 비율이 에쿼티 행에 날짜로 붙는다

        Given: 이동평균이 날마다 다른 시그널 2행과 같은 날짜의 에쿼티 2행
        When: enrich_equity_with_bands 호출
        Then: 날짜마다 upper/lower = 그날 ma × (1 ± buffer), 버퍼 비율 열은 입력값, 이동평균 열은 붙지 않는다
        """
        # Given
        dates = [date(2023, 1, 2), date(2023, 1, 3)]
        signal_df = pd.DataFrame({COL_DATE: dates, "ma_200": [100.0, 200.0]})
        equity_df = pd.DataFrame({COL_DATE: dates, "equity": [1000.0, 1100.0]})

        # When
        result = enrich_equity_with_bands(equity_df, signal_df, "ma_200", 0.03, 0.05)

        # Then
        assert result["upper_band"].tolist() == pytest.approx([103.0, 206.0], abs=1e-9)
        assert result["lower_band"].tolist() == pytest.approx([95.0, 190.0], abs=1e-9)
        assert result["buy_buffer_pct"].tolist() == [0.03, 0.03]
        assert result["sell_buffer_pct"].tolist() == [0.05, 0.05]
        assert "ma_200" not in result.columns


class TestRoundSignalForCsv:
    """round_signal_for_csv 함수 테스트"""

    def test_price_and_pct_columns_use_their_digits(self):
        """
        목적: 가격 · 이동평균 · 밴드는 ROUND_PRICE, 전일대비%는 ROUND_PERCENT 자릿수로 저장된다

        Given: 자릿수가 넘치는 OHLC · 이동평균 · 밴드 · 전일대비% 열과 Volume
        When: round_signal_for_csv 호출
        Then: 열마다 정해진 자릿수로 반올림되고 Volume 은 그대로다
        """
        # Given
        value = 1.234567891
        price_cols = [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, "ma_200", *BUFFER_BAND_COLUMNS]
        df = pd.DataFrame({**{col: [value] for col in [*price_cols, *OHLC_CHANGE_PCT_COLUMNS]}, "Volume": [123]})

        # When
        result = round_signal_for_csv(df)

        # Then
        for col in price_cols:
            assert result.iloc[0][col] == pytest.approx(round(value, ROUND_PRICE), abs=1e-12), col
        for col in OHLC_CHANGE_PCT_COLUMNS:
            assert result.iloc[0][col] == pytest.approx(round(value, ROUND_PERCENT), abs=1e-12), col
        assert result.iloc[0]["Volume"] == 123


class TestRemoveConfigDependentFiles:
    """remove_config_dependent_files 함수 테스트"""

    def test_removes_only_config_dependent_files(self, tmp_path: Path):
        """
        목적: 구성에 따라 생기는 파일(자산 키별 시그널 · 장부 · 상계 내역)만 지우고 나머지 결과 파일은 둔다 —
              구성이 바뀐 실험을 다시 저장할 때 지금 없는 자산 · 매매법의 파일이 남으면 대시보드가 그대로 그린다

        Given: 자산 키 둘(매매법 하나 · 여럿인 실험의 모양)의 시그널 파일, 장부 · 상계 내역, 늘 다시 쓰는 결과 파일 넷
        When: remove_config_dependent_files 호출
        Then: 시그널 · 장부 · 상계 내역만 지워지고 나머지 넷은 남는다
        """
        # Given
        stale = [
            portfolio_signal_filename("qqq"),
            portfolio_signal_filename("q2_2xs.sso"),
            LEDGER_FILENAME,
            NETTING_FILENAME,
        ]
        kept = [EQUITY_FILENAME, TRADES_FILENAME, SUMMARY_FILENAME, "state_log.csv"]
        for name in [*stale, *kept]:
            (tmp_path / name).write_text("x", encoding="utf-8")

        # When
        remove_config_dependent_files(tmp_path)

        # Then
        assert sorted(p.name for p in tmp_path.iterdir()) == sorted(kept)

    def test_first_save_without_files_is_fine(self, tmp_path: Path):
        """
        목적: 처음 저장하는 폴더(지울 파일이 없음)에서도 멈추지 않는다

        Given: 빈 폴더
        When: remove_config_dependent_files 호출
        Then: 예외 없이 폴더가 그대로 비어 있다
        """
        # When
        remove_config_dependent_files(tmp_path)

        # Then
        assert list(tmp_path.iterdir()) == []
