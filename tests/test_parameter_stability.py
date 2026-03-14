"""파라미터 고원 분석 모듈 테스트

고원 CSV 로딩, 고원 구간 탐지, 현재값 반환 함수를 검증한다.

테스트 대상:
- load_plateau_pivot: 피벗 CSV 로드
- get_current_value: 4P 확정 파라미터값 반환
- find_plateau_range: 고원 구간 탐지
- find_plateau_range_with_trade_filter: 거래 수 필터 적용 고원 구간 탐지
"""

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest


class TestLoadPlateauPivot:
    """피벗 CSV 로드 테스트."""

    def test_load_plateau_pivot_returns_dataframe(self, tmp_path: Path) -> None:
        """
        목적: 피벗 CSV 로드 후 DataFrame 반환 검증

        Given: param_plateau_hold_days_calmar.csv 파일 존재
        When: load_plateau_pivot("hold_days", "calmar") 호출
        Then: DataFrame 반환, index=자산, columns=파라미터값
        """
        from qbt.backtest.parameter_stability import load_plateau_pivot

        # Given: 피벗 CSV 생성
        pivot_df = pd.DataFrame(
            {"hold=0": [0.15, 0.12], "hold=3": [0.20, 0.18], "hold=5": [0.19, 0.17]},
            index=["QQQ", "SPY"],
        )
        csv_path = tmp_path / "param_plateau_hold_days_calmar.csv"
        pivot_df.to_csv(csv_path)

        # When
        with patch("qbt.backtest.parameter_stability._PLATEAU_DIR", tmp_path):
            result = load_plateau_pivot("hold_days", "calmar")

        # Then
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "hold=0" in result.columns
        assert "hold=3" in result.columns

    def test_load_plateau_pivot_raises_file_not_found(self, tmp_path: Path) -> None:
        """
        목적: CSV 파일 미존재 시 FileNotFoundError 발생 검증

        Given: 빈 디렉토리
        When: load_plateau_pivot("hold_days", "calmar") 호출
        Then: FileNotFoundError 발생
        """
        from qbt.backtest.parameter_stability import load_plateau_pivot

        # When / Then
        with patch("qbt.backtest.parameter_stability._PLATEAU_DIR", tmp_path):
            with pytest.raises(FileNotFoundError, match="고원 분석 결과"):
                load_plateau_pivot("hold_days", "calmar")


class TestGetCurrentValue:
    """현재 확정 파라미터값 반환 테스트."""

    def test_get_current_value_returns_correct_values(self) -> None:
        """
        목적: 4P 확정 파라미터값이 올바른지 검증

        Given: 확정 파라미터 (MA=200, buy=0.03, sell=0.05, hold=3)
        When: get_current_value() 호출
        Then: 각 파라미터의 확정값 반환
        """
        from qbt.backtest.parameter_stability import get_current_value

        # Then
        assert get_current_value("ma_window") == 200
        assert get_current_value("buy_buffer") == pytest.approx(0.03, abs=1e-12)
        assert get_current_value("sell_buffer") == pytest.approx(0.05, abs=1e-12)
        assert get_current_value("hold_days") == 3

    def test_get_current_value_raises_for_unknown(self) -> None:
        """
        목적: 알 수 없는 파라미터명에 ValueError 발생 검증

        Given: "unknown_param"이라는 파라미터명
        When: get_current_value("unknown_param") 호출
        Then: ValueError 발생
        """
        from qbt.backtest.parameter_stability import get_current_value

        # When / Then
        with pytest.raises(ValueError, match="알 수 없는 파라미터"):
            get_current_value("unknown_param")


class TestGetPlateauDir:
    """고원 분석 디렉토리 경로 반환 테스트."""

    def test_get_plateau_dir_returns_path(self) -> None:
        """
        목적: 고원 분석 결과 디렉토리 Path 반환 검증

        Given: 모듈 초기화 상태
        When: get_plateau_dir() 호출
        Then: Path 객체 반환, "param_plateau"로 끝남
        """
        from qbt.backtest.parameter_stability import get_plateau_dir

        # When
        result = get_plateau_dir()

        # Then
        assert isinstance(result, Path)
        assert result.name == "param_plateau"


class TestFindPlateauRange:
    """고원 구간 탐지 테스트."""

    def test_find_plateau_range_returns_range(self) -> None:
        """
        목적: 최대값 대비 90% 이상인 연속 범위 탐지 검증

        Given: [0.10, 0.19, 0.20, 0.19, 0.12] 값의 Series (인덱스 0~4)
        When: find_plateau_range(series, threshold_ratio=0.9) 호출
        Then: (1.0, 3.0) 반환 (인덱스 1, 2, 3이 0.20 * 0.9 = 0.18 이상)
        """
        from qbt.backtest.parameter_stability import find_plateau_range

        # Given: 0.19, 0.20, 0.19는 모두 threshold(0.18) 이상
        series = pd.Series([0.10, 0.19, 0.20, 0.19, 0.12], index=[0, 1, 2, 3, 4])

        # When
        result = find_plateau_range(series, threshold_ratio=0.9)

        # Then
        assert result is not None
        assert result == pytest.approx((1.0, 3.0), abs=1e-12)

    def test_find_plateau_range_returns_none_for_empty(self) -> None:
        """
        목적: 빈 Series에 대해 None 반환 검증

        Given: 빈 Series
        When: find_plateau_range(series) 호출
        Then: None 반환
        """
        from qbt.backtest.parameter_stability import find_plateau_range

        # Given
        series = pd.Series([], dtype=float)

        # When
        result = find_plateau_range(series)

        # Then
        assert result is None

    def test_find_plateau_range_returns_none_for_all_negative(self) -> None:
        """
        목적: 모든 값이 0 이하일 때 None 반환 검증

        Given: 모든 값이 음수인 Series
        When: find_plateau_range(series) 호출
        Then: None 반환
        """
        from qbt.backtest.parameter_stability import find_plateau_range

        # Given
        series = pd.Series([-0.1, -0.2, -0.3], index=[0, 1, 2])

        # When
        result = find_plateau_range(series)

        # Then
        assert result is None

    def test_find_plateau_range_single_peak(self) -> None:
        """
        목적: 단일 피크에서 단일 포인트 고원 반환 검증

        Given: [0.01, 0.50, 0.01] (중앙만 높음)
        When: find_plateau_range(series, threshold_ratio=0.9) 호출
        Then: (1.0, 1.0) 반환 (인덱스 1만 해당)
        """
        from qbt.backtest.parameter_stability import find_plateau_range

        # Given
        series = pd.Series([0.01, 0.50, 0.01], index=[0, 1, 2])

        # When
        result = find_plateau_range(series, threshold_ratio=0.9)

        # Then
        assert result is not None
        assert result == pytest.approx((1.0, 1.0), abs=1e-12)

    def test_find_plateau_range_custom_threshold(self) -> None:
        """
        목적: threshold_ratio 변경 시 고원 구간 변화 검증

        Given: [0.10, 0.16, 0.20, 0.16, 0.12] (인덱스 0~4)
        When: find_plateau_range(series, threshold_ratio=0.75) 호출
        Then: 0.20 * 0.75 = 0.15 이상인 범위 (1.0, 3.0) 반환
        """
        from qbt.backtest.parameter_stability import find_plateau_range

        # Given: 0.16, 0.20, 0.16은 모두 threshold(0.15) 이상
        series = pd.Series([0.10, 0.16, 0.20, 0.16, 0.12], index=[0, 1, 2, 3, 4])

        # When
        result = find_plateau_range(series, threshold_ratio=0.75)

        # Then
        assert result is not None
        assert result == pytest.approx((1.0, 3.0), abs=1e-12)

    def test_find_plateau_range_all_above_threshold(self) -> None:
        """
        목적: 모든 값이 threshold 이상일 때 전체 범위 반환 검증

        Given: [0.20, 0.19, 0.19] (모두 0.20 * 0.9 = 0.18 초과)
        When: find_plateau_range(series, threshold_ratio=0.9) 호출
        Then: (0.0, 2.0) 반환 (전체 범위)
        """
        from qbt.backtest.parameter_stability import find_plateau_range

        # Given: 모든 값이 threshold(0.18) 초과
        series = pd.Series([0.20, 0.19, 0.19], index=[0, 1, 2])

        # When
        result = find_plateau_range(series, threshold_ratio=0.9)

        # Then
        assert result is not None
        assert result == pytest.approx((0.0, 2.0), abs=1e-12)


class TestFindPlateauRangeWithTradeFilter:
    """거래 수 필터 적용 고원 구간 탐지 테스트."""

    def test_filters_low_trade_params(self) -> None:
        """
        목적: 거래 수 부족 파라미터 제외 후 고원이 올바른 위치에 탐지되는지 검증

        Given: sell=0.15가 최고 Calmar이나 거래 수 4회 (min_trades=5 미만)
        When: find_plateau_range_with_trade_filter() 호출
        Then: sell=0.15 제외, sell=0.05 기준 고원 탐지
        """
        from qbt.backtest.parameter_stability import find_plateau_range_with_trade_filter

        # Given: sell=0.15는 Calmar 최고(0.36)이나 거래 수 4회
        metric = pd.Series(
            [0.20, 0.24, 0.30, 0.22, 0.23, 0.36],
            index=[0.01, 0.03, 0.05, 0.07, 0.10, 0.15],
        )
        trades = pd.Series(
            [27, 21, 14, 13, 8, 4],
            index=[0.01, 0.03, 0.05, 0.07, 0.10, 0.15],
        )

        # When
        plateau, excluded = find_plateau_range_with_trade_filter(metric, trades, min_trades=5, threshold_ratio=0.9)

        # Then: sell=0.15 제외, 나머지 max=0.30 (sell=0.05)
        assert excluded == pytest.approx([0.15], abs=1e-12)
        assert plateau is not None
        assert plateau == pytest.approx((0.05, 0.05), abs=1e-12)

    def test_all_filtered_returns_none(self) -> None:
        """
        목적: 모든 파라미터가 필터링되면 None 반환 검증

        Given: 모든 파라미터의 거래 수가 min_trades 미만
        When: find_plateau_range_with_trade_filter() 호출
        Then: plateau=None, 전체 인덱스 제외
        """
        from qbt.backtest.parameter_stability import find_plateau_range_with_trade_filter

        # Given
        metric = pd.Series([0.20, 0.30], index=[0.05, 0.10])
        trades = pd.Series([2, 3], index=[0.05, 0.10])

        # When
        plateau, excluded = find_plateau_range_with_trade_filter(metric, trades, min_trades=5)

        # Then
        assert plateau is None
        assert excluded == pytest.approx([0.05, 0.10], abs=1e-12)

    def test_no_filtering_when_all_sufficient(self) -> None:
        """
        목적: 모든 거래 수가 충분하면 기존 find_plateau_range와 동일 결과 검증

        Given: 모든 파라미터의 거래 수가 min_trades 이상
        When: find_plateau_range_with_trade_filter() 호출
        Then: excluded=[], find_plateau_range와 동일 결과
        """
        from qbt.backtest.parameter_stability import (
            find_plateau_range,
            find_plateau_range_with_trade_filter,
        )

        # Given
        metric = pd.Series([0.10, 0.19, 0.20, 0.19], index=[1, 2, 3, 4])
        trades = pd.Series([20, 15, 10, 8], index=[1, 2, 3, 4])

        # When
        plateau, excluded = find_plateau_range_with_trade_filter(metric, trades, min_trades=5, threshold_ratio=0.9)
        expected = find_plateau_range(metric, threshold_ratio=0.9)

        # Then
        assert excluded == []
        assert plateau == expected
