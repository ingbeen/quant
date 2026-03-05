"""파라미터 안정성 분석 모듈 테스트

overfitting_analysis_report.md 11.2절 "1단계: 파라미터 안정성 확인"의
데이터 가공 로직과 판정 기준을 검증한다.

테스트 대상:
- grid_results.csv 로드 및 컬럼명 변환
- Calmar 히스토그램 데이터 추출
- MA별 buy_buffer x sell_buffer 히트맵 집계
- 인접 파라미터 비교 데이터 생성
- 안정성 통과 기준 판정
"""

from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.constants import (
    COL_BUY_BUFFER_ZONE_PCT,
    COL_CAGR,
    COL_CALMAR,
    COL_FINAL_CAPITAL,
    COL_HOLD_DAYS,
    COL_MA_WINDOW,
    COL_MDD,
    COL_RECENT_MONTHS,
    COL_SELL_BUFFER_ZONE_PCT,
    COL_TOTAL_RETURN_PCT,
    COL_TOTAL_TRADES,
    COL_WIN_RATE,
    DISPLAY_BUY_BUFFER_ZONE,
    DISPLAY_CAGR,
    DISPLAY_CALMAR,
    DISPLAY_FINAL_CAPITAL,
    DISPLAY_HOLD_DAYS,
    DISPLAY_MA_WINDOW,
    DISPLAY_MDD,
    DISPLAY_RECENT_MONTHS,
    DISPLAY_SELL_BUFFER_ZONE,
    DISPLAY_TOTAL_RETURN,
    DISPLAY_TOTAL_TRADES,
    DISPLAY_WIN_RATE,
)


def _build_grid_df() -> pd.DataFrame:
    """테스트용 그리드 서치 결과 DataFrame 생성 (내부 COL_* 컬럼명).

    3(MA) x 3(buy) x 3(sell) x 4(hold) x 4(recent) = 432개 조합.
    Calmar는 0.05 ~ 0.30 범위에서 결정론적으로 생성한다.
    """
    ma_list = [100, 150, 200]
    buy_list = [0.01, 0.03, 0.05]
    sell_list = [0.01, 0.03, 0.05]
    hold_list = [0, 2, 3, 5]
    recent_list = [0, 4, 8, 12]

    rows = []
    idx = 0
    for ma in ma_list:
        for buy in buy_list:
            for sell in sell_list:
                for hold in hold_list:
                    for recent in recent_list:
                        # Calmar: MA=200, buy=0.03, sell=0.05 부근이 높도록 설계
                        calmar = 0.10 + 0.05 * (ma / 200) + 0.03 * (sell / 0.05) + 0.01 * (buy / 0.03)
                        # hold=3, recent=0일 때 약간 더 높게
                        if hold == 3:
                            calmar += 0.02
                        if recent == 0:
                            calmar += 0.01
                        cagr = calmar * 30.0
                        mdd = -cagr / calmar if calmar > 0 else -30.0
                        rows.append(
                            {
                                COL_MA_WINDOW: ma,
                                COL_BUY_BUFFER_ZONE_PCT: buy,
                                COL_SELL_BUFFER_ZONE_PCT: sell,
                                COL_HOLD_DAYS: hold,
                                COL_RECENT_MONTHS: recent,
                                COL_TOTAL_RETURN_PCT: cagr * 10,
                                COL_CAGR: cagr,
                                COL_MDD: mdd,
                                COL_CALMAR: calmar,
                                COL_TOTAL_TRADES: 10 + idx % 5,
                                COL_WIN_RATE: 60.0 + (idx % 20),
                                COL_FINAL_CAPITAL: 10_000_000 + cagr * 100_000,
                            }
                        )
                        idx += 1
    return pd.DataFrame(rows)


def _build_display_csv_df() -> pd.DataFrame:
    """테스트용 CSV 파일에 저장할 DISPLAY 컬럼명 DataFrame.

    _build_grid_df()의 결과를 DISPLAY 컬럼명으로 변환한다.
    """
    df = _build_grid_df()
    return df.rename(
        columns={
            COL_MA_WINDOW: DISPLAY_MA_WINDOW,
            COL_BUY_BUFFER_ZONE_PCT: DISPLAY_BUY_BUFFER_ZONE,
            COL_SELL_BUFFER_ZONE_PCT: DISPLAY_SELL_BUFFER_ZONE,
            COL_HOLD_DAYS: DISPLAY_HOLD_DAYS,
            COL_RECENT_MONTHS: DISPLAY_RECENT_MONTHS,
            COL_TOTAL_RETURN_PCT: DISPLAY_TOTAL_RETURN,
            COL_CAGR: DISPLAY_CAGR,
            COL_MDD: DISPLAY_MDD,
            COL_CALMAR: DISPLAY_CALMAR,
            COL_TOTAL_TRADES: DISPLAY_TOTAL_TRADES,
            COL_WIN_RATE: DISPLAY_WIN_RATE,
            COL_FINAL_CAPITAL: DISPLAY_FINAL_CAPITAL,
        }
    )


class TestLoadGridResults:
    """grid_results.csv 로드 및 컬럼명 변환 테스트."""

    def test_load_grid_results_returns_dataframe(self, tmp_path: Path) -> None:
        """
        목적: CSV 로드 후 DISPLAY -> COL 컬럼명 변환 검증

        Given: DISPLAY 컬럼명을 가진 grid_results.csv
        When: load_grid_results() 호출
        Then: COL_* 내부 컬럼명으로 변환된 DataFrame 반환
        """
        from qbt.backtest.parameter_stability import load_grid_results

        # Given
        csv_path = tmp_path / "grid_results.csv"
        display_df = _build_display_csv_df()
        display_df.to_csv(csv_path, index=False)

        # When
        result = load_grid_results(csv_path)

        # Then
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 432
        assert COL_MA_WINDOW in result.columns
        assert COL_BUY_BUFFER_ZONE_PCT in result.columns
        assert COL_SELL_BUFFER_ZONE_PCT in result.columns
        assert COL_CALMAR in result.columns
        assert COL_CAGR in result.columns
        assert COL_MDD in result.columns

    def test_load_grid_results_validates_required_columns(self, tmp_path: Path) -> None:
        """
        목적: 필수 컬럼 미존재 시 ValueError 발생 검증

        Given: 일부 컬럼만 존재하는 CSV 파일
        When: load_grid_results() 호출
        Then: ValueError 발생
        """
        from qbt.backtest.parameter_stability import load_grid_results

        # Given
        csv_path = tmp_path / "bad_grid.csv"
        bad_df = pd.DataFrame({"col_a": [1], "col_b": [2]})
        bad_df.to_csv(csv_path, index=False)

        # When / Then
        with pytest.raises(ValueError, match="필수 컬럼"):
            load_grid_results(csv_path)


class TestBuildCalmarHistogramData:
    """Calmar 히스토그램 데이터 추출 테스트."""

    def test_build_calmar_histogram_data_returns_all_432(self) -> None:
        """
        목적: 히스토그램 데이터가 전체 행 수(432)와 동일한지 검증

        Given: 432개 조합의 그리드 서치 결과
        When: build_calmar_histogram_data() 호출
        Then: 432개의 Calmar 값 Series 반환
        """
        from qbt.backtest.parameter_stability import build_calmar_histogram_data

        # Given
        df = _build_grid_df()

        # When
        result = build_calmar_histogram_data(df)

        # Then
        assert isinstance(result, pd.Series)
        assert len(result) == 432


class TestBuildHeatmapData:
    """MA별 buy_buffer x sell_buffer 히트맵 집계 테스트."""

    def test_build_heatmap_data_filters_by_ma(self) -> None:
        """
        목적: MA=200 필터링 시 정확히 144개 행 기반 집계 검증

        Given: 432개 전체 그리드 결과
        When: build_heatmap_data(df, ma_window=200) 호출
        Then: 3(buy) x 3(sell) = 9셀 피벗 반환 (각 셀은 16개 조합의 집계)
        """
        from qbt.backtest.parameter_stability import build_heatmap_data

        # Given
        df = _build_grid_df()

        # When
        result = build_heatmap_data(df, ma_window=200)

        # Then
        # 3(buy) x 3(sell) = 9개 행 (long format) 또는 피벗된 형태
        assert len(result) == 9

    def test_build_heatmap_data_aggregates_mean_and_min(self) -> None:
        """
        목적: buy_buffer x sell_buffer별 평균/최소 Calmar 집계 검증

        Given: MA=200 필터링된 데이터
        When: build_heatmap_data(df, ma_window=200) 호출
        Then: calmar_mean과 calmar_min 컬럼 존재, calmar_min <= calmar_mean
        """
        from qbt.backtest.parameter_stability import build_heatmap_data

        # Given
        df = _build_grid_df()

        # When
        result = build_heatmap_data(df, ma_window=200)

        # Then
        assert "calmar_mean" in result.columns
        assert "calmar_min" in result.columns
        # 모든 셀에서 최소값이 평균값 이하
        assert (result["calmar_min"] <= result["calmar_mean"] + 1e-12).all()

    def test_build_heatmap_data_includes_cagr_mdd(self) -> None:
        """
        목적: 집계 결과에 CAGR 평균, MDD 평균 포함 검증

        Given: MA=200 필터링된 데이터
        When: build_heatmap_data(df, ma_window=200) 호출
        Then: cagr_mean과 mdd_mean 컬럼 존재
        """
        from qbt.backtest.parameter_stability import build_heatmap_data

        # Given
        df = _build_grid_df()

        # When
        result = build_heatmap_data(df, ma_window=200)

        # Then
        assert "cagr_mean" in result.columns
        assert "mdd_mean" in result.columns


class TestBuildAdjacentComparison:
    """인접 파라미터 비교 데이터 생성 테스트."""

    def test_build_adjacent_comparison_returns_optimal_and_neighbors(self) -> None:
        """
        목적: 최적 파라미터 기준 인접 조합 비교 데이터 반환 검증

        Given: 432개 그리드 결과, 최적 파라미터 (MA=200, buy=0.03, sell=0.05)
        When: build_adjacent_comparison() 호출
        Then: 비교 테이블에 최적 + 인접 조합 포함
        """
        from qbt.backtest.parameter_stability import build_adjacent_comparison

        # Given
        df = _build_grid_df()

        # When
        result = build_adjacent_comparison(df, optimal_ma=200, optimal_buy=0.03, optimal_sell=0.05)

        # Then
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        # 비교 테이블에 파라미터 변경 정보와 Calmar 포함
        assert "calmar_mean" in result.columns

    def test_build_adjacent_comparison_includes_hold_days_axis(self) -> None:
        """
        목적: hold_days 축 변화에 따른 Calmar 포함 검증

        Given: 432개 그리드 결과
        When: build_adjacent_comparison() 호출
        Then: hold_days 변화에 따른 비교 행 포함
        """
        from qbt.backtest.parameter_stability import build_adjacent_comparison

        # Given
        df = _build_grid_df()

        # When
        result = build_adjacent_comparison(df, optimal_ma=200, optimal_buy=0.03, optimal_sell=0.05)

        # Then
        # hold_days 축이 포함되어야 함
        assert "axis" in result.columns
        hold_rows = result[result["axis"] == "hold_days"]
        assert len(hold_rows) > 0


class TestEvaluateStabilityCriteria:
    """보고서 11.2절 통과 기준 평가 테스트."""

    def test_evaluate_stability_criteria(self) -> None:
        """
        목적: Calmar>0 비율, 인접 30% 이내 판정 함수 검증

        Given: 모든 Calmar > 0인 432개 데이터, 최적 Calmar 값
        When: evaluate_stability_criteria() 호출
        Then: Calmar>0 비율 100%, 통과 판정 포함
        """
        from qbt.backtest.parameter_stability import evaluate_stability_criteria

        # Given
        df = _build_grid_df()
        # 최적 Calmar 값 찾기
        optimal_calmar = df[COL_CALMAR].max()

        # When
        result = evaluate_stability_criteria(
            df,
            optimal_calmar=optimal_calmar,
            optimal_ma=200,
            optimal_buy=0.03,
            optimal_sell=0.05,
        )

        # Then
        assert isinstance(result, dict)
        # Calmar > 0 비율 관련
        assert "calmar_positive_ratio" in result
        assert "calmar_positive_pass" in result
        assert result["calmar_positive_ratio"] == pytest.approx(1.0, abs=1e-12)
        assert result["calmar_positive_pass"] is True

        # 인접 파라미터 30% 이내 관련
        assert "adjacent_within_threshold" in result
        assert "adjacent_pass" in result

        # 전체 통과 여부
        assert "overall_pass" in result
