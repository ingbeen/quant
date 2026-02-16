"""
룩업테이블 스프레드 모델 테스트

실현 스프레드 역산, 룩업테이블 생성, 스프레드 조회의 핵심 정책을 검증한다.

핵심 수식 (역산):
    시뮬레이션: leveraged_return = underlying_return * leverage - daily_cost
    daily_cost = ((ffr + spread) * (leverage - 1) + expense) / 252

    역산:
    daily_cost = underlying_return * leverage - leveraged_return
    annual_cost = daily_cost * 252
    spread = annual_cost / (leverage - 1) - ffr - expense / (leverage - 1)
"""

from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, TRADING_DAYS_PER_YEAR


class TestCalculateRealizedSpread:
    """실현 스프레드 역산 함수 테스트"""

    def test_known_spread_recovery(self):
        """
        목적: 알려진 스프레드로 시뮬레이션된 데이터에서 원래 스프레드를 역산할 수 있는지 검증

        Given: QQQ 수익률 1%, TQQQ가 leverage=3, FFR=5%, expense=0.95%, spread=0.5%로
               시뮬레이션된 수익률
        When: calculate_realized_spread()로 역산
        Then: 역산된 스프레드가 원래 0.5%와 일치
        """
        from qbt.tqqq.lookup_spread import calculate_realized_spread

        # Given
        leverage = 3.0
        ffr = 0.05  # 5%
        expense = 0.0095  # 0.95%
        known_spread = 0.005  # 0.5%

        # 일일 비용 계산 (시뮬레이션 수식 그대로)
        daily_cost = ((ffr + known_spread) * (leverage - 1) + expense) / TRADING_DAYS_PER_YEAR

        # QQQ 수익률과 TQQQ 수익률 생성
        qqq_return = 0.01  # 1%
        tqqq_return = qqq_return * leverage - daily_cost

        # 날짜별 데이터 구성 (2일: 첫날 기준가, 둘째날 수익률 발생)
        dates = [date(2023, 1, 2), date(2023, 1, 3)]
        qqq_close = [100.0, 100.0 * (1 + qqq_return)]
        tqqq_close = [50.0, 50.0 * (1 + tqqq_return)]

        qqq_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: qqq_close})
        tqqq_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: tqqq_close})

        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "VALUE": [ffr]})
        expense_df = pd.DataFrame({"DATE": ["2023-01"], "VALUE": [expense]})

        # When
        result = calculate_realized_spread(
            qqq_df=qqq_df,
            tqqq_df=tqqq_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            leverage=leverage,
        )

        # Then
        assert len(result) == 1  # 첫날은 pct_change가 NaN이므로 1개
        assert result.iloc[0]["realized_spread"] == pytest.approx(known_spread, abs=1e-10)

    def test_multiple_days_different_rates(self):
        """
        목적: 여러 날에 걸쳐 다른 금리에서도 스프레드 역산이 정확한지 검증

        Given: 2개월에 걸친 데이터, 월별로 다른 FFR
        When: calculate_realized_spread()
        Then: 각 날짜의 역산 스프레드가 원래 값과 일치
        """
        from qbt.tqqq.lookup_spread import calculate_realized_spread

        leverage = 3.0
        known_spread = 0.003  # 0.3%

        # 2개월 데이터 (1월, 2월)
        ffr_values = {"2023-01": 0.04, "2023-02": 0.05}
        expense_values = {"2023-01": 0.0095, "2023-02": 0.0088}

        dates = [date(2023, 1, 2), date(2023, 1, 3), date(2023, 2, 1), date(2023, 2, 2)]
        qqq_returns = [0.01, -0.005, 0.02]  # 3일의 수익률

        # QQQ 종가 생성
        qqq_close = [100.0]
        for r in qqq_returns:
            qqq_close.append(qqq_close[-1] * (1 + r))

        # TQQQ 종가 생성 (시뮬레이션 수식 적용)
        tqqq_close = [50.0]
        for i, r in enumerate(qqq_returns):
            d = dates[i + 1]
            month_key = f"{d.year:04d}-{d.month:02d}"
            ffr = ffr_values[month_key]
            expense = expense_values[month_key]
            daily_cost = ((ffr + known_spread) * (leverage - 1) + expense) / TRADING_DAYS_PER_YEAR
            tqqq_ret = r * leverage - daily_cost
            tqqq_close.append(tqqq_close[-1] * (1 + tqqq_ret))

        qqq_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: qqq_close})
        tqqq_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: tqqq_close})
        ffr_df = pd.DataFrame({"DATE": ["2023-01", "2023-02"], "VALUE": [0.04, 0.05]})
        expense_df = pd.DataFrame({"DATE": ["2023-01", "2023-02"], "VALUE": [0.0095, 0.0088]})

        # When
        result = calculate_realized_spread(
            qqq_df=qqq_df,
            tqqq_df=tqqq_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            leverage=leverage,
        )

        # Then
        assert len(result) == 3
        for _, row in result.iterrows():
            assert row["realized_spread"] == pytest.approx(known_spread, abs=1e-10)

    def test_output_contains_required_columns(self):
        """
        목적: 반환 DataFrame에 필수 컬럼이 포함되어 있는지 검증

        Given: 최소한의 유효 입력
        When: calculate_realized_spread()
        Then: date, month, ffr_pct, realized_spread 컬럼 존재
        """
        from qbt.tqqq.lookup_spread import calculate_realized_spread

        dates = [date(2023, 1, 2), date(2023, 1, 3)]
        qqq_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: [100.0, 101.0]})
        tqqq_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: [50.0, 52.0]})
        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "VALUE": [0.05]})
        expense_df = pd.DataFrame({"DATE": ["2023-01"], "VALUE": [0.0095]})

        result = calculate_realized_spread(
            qqq_df=qqq_df,
            tqqq_df=tqqq_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            leverage=3.0,
        )

        required_cols = {"date", "month", "ffr_pct", "realized_spread"}
        assert required_cols.issubset(set(result.columns))


class TestBuildLookupTable:
    """금리 구간별 룩업테이블 생성 테스트"""

    def test_mean_aggregation(self):
        """
        목적: 금리 구간별 평균 스프레드가 올바르게 계산되는지 검증

        Given: 금리 0~1% 구간에 스프레드 [0.002, 0.004], 1~2% 구간에 [0.006]
        When: build_lookup_table(bin_width_pct=1.0, stat_func="mean")
        Then: 0~1% 구간 평균 = 0.003, 1~2% 구간 = 0.006
        """
        from qbt.tqqq.lookup_spread import build_lookup_table

        # Given
        realized_df = pd.DataFrame(
            {
                "ffr_pct": [0.3, 0.8, 1.5],
                "realized_spread": [0.002, 0.004, 0.006],
            }
        )

        # When
        table = build_lookup_table(realized_df, bin_width_pct=1.0, stat_func="mean")

        # Then: 구간 [0, 1) -> 중앙 0.5, 구간 [1, 2) -> 중앙 1.5
        assert table[0.5] == pytest.approx(0.003, abs=1e-10)
        assert table[1.5] == pytest.approx(0.006, abs=1e-10)

    def test_median_aggregation(self):
        """
        목적: 금리 구간별 중앙값 스프레드가 올바르게 계산되는지 검증

        Given: 금리 0~1% 구간에 스프레드 [0.001, 0.003, 0.010] (이상치 포함)
        When: build_lookup_table(bin_width_pct=1.0, stat_func="median")
        Then: 중앙값 = 0.003 (이상치 0.010에 강건)
        """
        from qbt.tqqq.lookup_spread import build_lookup_table

        realized_df = pd.DataFrame(
            {
                "ffr_pct": [0.2, 0.5, 0.8],
                "realized_spread": [0.001, 0.003, 0.010],
            }
        )

        table = build_lookup_table(realized_df, bin_width_pct=1.0, stat_func="median")

        assert table[0.5] == pytest.approx(0.003, abs=1e-10)

    def test_different_bin_widths(self):
        """
        목적: 구간 폭에 따라 테이블 크기가 달라지는지 검증

        Given: 금리 0~3% 범위의 데이터
        When: bin_width_pct=0.5 vs bin_width_pct=1.0
        Then: 0.5% 구간이 더 많은 키를 생성
        """
        from qbt.tqqq.lookup_spread import build_lookup_table

        realized_df = pd.DataFrame(
            {
                "ffr_pct": [0.2, 0.7, 1.2, 1.8, 2.3, 2.8],
                "realized_spread": [0.001, 0.002, 0.003, 0.004, 0.005, 0.006],
            }
        )

        table_05 = build_lookup_table(realized_df, bin_width_pct=0.5, stat_func="mean")
        table_10 = build_lookup_table(realized_df, bin_width_pct=1.0, stat_func="mean")

        assert len(table_05) > len(table_10)

    def test_invalid_stat_func_raises(self):
        """
        목적: 지원하지 않는 통계량 지정 시 예외 발생 검증

        Given: stat_func="mode" (지원 안 함)
        When: build_lookup_table()
        Then: ValueError 발생
        """
        from qbt.tqqq.lookup_spread import build_lookup_table

        realized_df = pd.DataFrame({"ffr_pct": [0.5], "realized_spread": [0.003]})

        with pytest.raises(ValueError, match="stat_func"):
            build_lookup_table(realized_df, bin_width_pct=1.0, stat_func="mode")


class TestLookupSpreadFromTable:
    """스프레드 조회 테스트"""

    def test_exact_bin_lookup(self):
        """
        목적: 정확한 구간에 속하는 금리값에서 올바른 스프레드 반환 검증

        Given: 0~1% 구간 스프레드 0.003, 1~2% 구간 스프레드 0.005
        When: ffr_pct=0.5 조회
        Then: 0.003 반환
        """
        from qbt.tqqq.lookup_spread import lookup_spread_from_table

        table = {0.5: 0.003, 1.5: 0.005}

        result = lookup_spread_from_table(ffr_pct=0.5, lookup_table=table, bin_width_pct=1.0)
        assert result == pytest.approx(0.003, abs=1e-10)

    def test_boundary_lookup(self):
        """
        목적: 구간 경계에서 올바르게 분류되는지 검증

        Given: 구간 폭 1.0%, 테이블 {0.5: 0.003, 1.5: 0.005}
        When: ffr_pct=1.0 (1~2% 구간에 속해야 함)
        Then: 0.005 반환
        """
        from qbt.tqqq.lookup_spread import lookup_spread_from_table

        table = {0.5: 0.003, 1.5: 0.005}

        result = lookup_spread_from_table(ffr_pct=1.0, lookup_table=table, bin_width_pct=1.0)
        assert result == pytest.approx(0.005, abs=1e-10)

    def test_empty_bin_nearest_fallback(self):
        """
        목적: 빈 구간(테이블에 없는 구간)에서 인접 구간 값으로 fallback하는지 검증

        Given: 구간 0.5(0~1%)와 2.5(2~3%)만 있고 1.5(1~2%)는 없음
        When: ffr_pct=1.2 조회 (1~2% 구간, 빈 구간)
        Then: 가장 가까운 구간(0.5)의 스프레드 반환
        """
        from qbt.tqqq.lookup_spread import lookup_spread_from_table

        table = {0.5: 0.003, 2.5: 0.007}

        result = lookup_spread_from_table(ffr_pct=1.2, lookup_table=table, bin_width_pct=1.0)
        # 1.2의 구간 중앙 = 1.5, 0.5까지 거리 1.0 vs 2.5까지 거리 1.0 → 가까운 쪽(0.5) 선택
        assert result == pytest.approx(0.003, abs=1e-10)

    def test_empty_table_raises(self):
        """
        목적: 빈 테이블에서 조회 시 예외 발생 검증

        Given: 빈 룩업테이블
        When: lookup_spread_from_table()
        Then: ValueError 발생
        """
        from qbt.tqqq.lookup_spread import lookup_spread_from_table

        with pytest.raises(ValueError, match="비어"):
            lookup_spread_from_table(ffr_pct=1.0, lookup_table={}, bin_width_pct=1.0)


class TestBuildMonthlySpreadMapFromLookup:
    """월별 스프레드 맵 생성 테스트"""

    def test_monthly_map_structure(self):
        """
        목적: FundingSpreadSpec dict 형태로 올바른 월별 맵이 생성되는지 검증

        Given: FFR 데이터 3개월, 룩업테이블
        When: build_monthly_spread_map_from_lookup()
        Then: dict[str, float] 형태, 키는 "YYYY-MM", 값은 스프레드
        """
        from qbt.tqqq.lookup_spread import build_monthly_spread_map_from_lookup

        ffr_df = pd.DataFrame({"DATE": ["2023-01", "2023-02", "2023-03"], "VALUE": [0.04, 0.045, 0.05]})
        table = {0.5: 0.002, 1.5: 0.003, 2.5: 0.004, 3.5: 0.005, 4.5: 0.006}

        result = build_monthly_spread_map_from_lookup(ffr_df=ffr_df, lookup_table=table, bin_width_pct=1.0)

        assert isinstance(result, dict)
        assert len(result) == 3
        assert "2023-01" in result
        assert "2023-02" in result
        assert "2023-03" in result
        # FFR 4% → ffr_pct=4.0 → 구간 중앙 4.5 → 스프레드 0.006
        assert result["2023-01"] == pytest.approx(0.006, abs=1e-10)

    def test_spread_values_positive(self):
        """
        목적: 생성된 모든 스프레드 값이 양수인지 검증

        Given: 유효한 FFR 데이터와 룩업테이블
        When: build_monthly_spread_map_from_lookup()
        Then: 모든 스프레드 값 > 0
        """
        from qbt.tqqq.lookup_spread import build_monthly_spread_map_from_lookup

        ffr_df = pd.DataFrame({"DATE": ["2023-01", "2023-02"], "VALUE": [0.01, 0.05]})
        table = {0.5: 0.002, 1.5: 0.003, 4.5: 0.006, 5.5: 0.008}

        result = build_monthly_spread_map_from_lookup(ffr_df=ffr_df, lookup_table=table, bin_width_pct=1.0)

        for spread_val in result.values():
            assert spread_val > 0
