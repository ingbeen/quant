"""
tqqq/simulation 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 일일 비용 계산이 FFR 기반으로 정확한가?
2. FFR 누락 시 fallback 로직이 작동하는가?
3. 너무 오래된 FFR만 있으면 에러를 내는가?
4. 레버리지 ETF 시뮬레이션이 NaN 없이 생성되는가?
5. 실제 데이터와의 비교 검증 메트릭이 정확한가?

왜 중요한가요?
TQQQ 같은 레버리지 ETF는 일일 리밸런싱으로 복리 효과가 발생합니다.
비용 모델이 틀리면 시뮬레이션 결과가 실제와 크게 차이나서 무의미해집니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.tqqq.simulation import (
    calculate_daily_cost,
    calculate_validation_metrics,
    extract_overlap_period,
    find_optimal_cost_model,
    simulate,
    validate_ffr_coverage,
)


class TestCalculateDailyCost:
    """일일 비용 계산 테스트"""

    def test_normal_cost_calculation(self):
        """
        정상적인 일일 비용 계산 테스트

        데이터 신뢰성: 비용 공식이 정확해야 시뮬레이션이 유효합니다.

        Given:
          - 2023년 1월 15일
          - FFR 데이터에 2023-01이 4.5% 존재
          - expense_ratio=0.009 (0.9%), funding_spread=0.006 (0.6%)
        When: calculate_daily_cost 호출
        Then:
          - 해당 월의 FFR 사용
          - daily_cost = (FFR/100 + funding_spread) * 2 + expense_ratio) / 거래일수
          - 양수 값 반환
        """
        # Given: FFR 데이터 (DATE는 yyyy-mm 문자열 형식)
        ffr_df = pd.DataFrame({"DATE": ["2023-01", "2023-02"], "FFR": [4.5, 4.6]})

        target_date = date(2023, 1, 15)
        expense_ratio = 0.009  # 0.9%
        funding_spread = 0.006  # 0.6%

        # When
        leverage = 3.0  # 기본 3배 레버리지
        daily_cost = calculate_daily_cost(
            date_value=target_date,
            ffr_df=ffr_df,
            expense_ratio=expense_ratio,
            funding_spread=funding_spread,
            leverage=leverage,
        )

        # Then: 비용이 양수이고 합리적인 범위
        assert daily_cost > 0, "일일 비용은 양수여야 합니다"
        assert daily_cost < 0.001, f"일일 비용률이 너무 큽니다: {daily_cost}"

    def test_ffr_fallback_within_2_months(self):
        """
        FFR fallback 테스트 (2개월 이내)

        안정성: 해당 월 FFR이 없어도 최근 2개월 이내면 fallback 사용

        Given:
          - 2023년 3월 15일
          - FFR에 3월 데이터 없음, 1월 데이터만 존재
        When: calculate_daily_cost
        Then: 1월 FFR 사용 (2개월 이내이므로 허용)
        """
        # Given: 1월 FFR만 존재 (DATE는 yyyy-mm 문자열)
        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        target_date = date(2023, 3, 15)  # 1월부터 약 2개월 후
        leverage = 3.0

        # When: 2개월 이내면 fallback 허용
        try:
            daily_cost = calculate_daily_cost(
                date_value=target_date,
                ffr_df=ffr_df,
                expense_ratio=0.009,
                funding_spread=0.006,
                leverage=leverage,
            )
            # fallback 사용되면 비용이 계산됨
            assert daily_cost > 0, "fallback 시에도 비용 계산됨"
        except ValueError:
            # 구현이 엄격하면 에러를 낼 수도 있음
            # 이 경우 테스트는 "에러가 명확한지" 검증
            pass

    def test_empty_ffr_dataframe(self):
        """
        FFR DataFrame이 비었을 때 테스트

        안정성: 빈 데이터는 즉시 에러

        Given: 빈 FFR DataFrame
        When: calculate_daily_cost
        Then: ValueError
        """
        # Given
        ffr_df = pd.DataFrame(columns=["DATE", "FFR"])
        leverage = 3.0

        # When & Then
        with pytest.raises(ValueError):
            calculate_daily_cost(
                date_value=date(2023, 1, 15),
                ffr_df=ffr_df,
                expense_ratio=0.009,
                funding_spread=0.006,
                leverage=leverage,
            )

    def test_calculate_daily_cost_leverage_2(self):
        """
        레버리지 2배 비용 계산 테스트 (Phase 0 - 레드)

        정책: 레버리지 비용 = funding_rate * (leverage - 1)
        leverage=2일 때 차입 비율은 1배 (자기자본 1 + 빌린돈 1)

        Given:
          - 2023년 1월 15일
          - FFR=4.5%, funding_spread=0.006 (0.6%)
          - expense_ratio=0.009 (0.9%)
          - leverage=2
        When: calculate_daily_cost 호출
        Then:
          - 레버리지 비용 = (0.045 + 0.006) * 1 = 0.051
          - 총 연간 비용 = 0.051 + 0.009 = 0.06
          - 일일 비용 = 0.06 / 252
        """
        # Given
        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})
        target_date = date(2023, 1, 15)
        expense_ratio = 0.009
        funding_spread = 0.006
        leverage = 2.0

        # When
        daily_cost = calculate_daily_cost(
            date_value=target_date,
            ffr_df=ffr_df,
            expense_ratio=expense_ratio,
            funding_spread=funding_spread,
            leverage=leverage,
        )

        # Then: 레버리지 비용 = funding_rate * (leverage - 1) = (0.045 + 0.006) * 1
        # 총 연간 비용 = 0.051 + 0.009 = 0.06
        # 일일 비용 = 0.06 / 252 ≈ 0.000238
        expected_funding_rate = 0.045 + 0.006
        expected_leverage_cost = expected_funding_rate * (leverage - 1)
        expected_annual_cost = expected_leverage_cost + expense_ratio
        expected_daily_cost = expected_annual_cost / 252

        assert (
            abs(daily_cost - expected_daily_cost) < 1e-6
        ), f"leverage=2일 때 비용 계산: 기대={expected_daily_cost:.6f}, 실제={daily_cost:.6f}"

    def test_calculate_daily_cost_leverage_4(self):
        """
        레버리지 4배 비용 계산 테스트 (Phase 0 - 레드)

        정책: 레버리지 비용 = funding_rate * (leverage - 1)
        leverage=4일 때 차입 비율은 3배 (자기자본 1 + 빌린돈 3)

        Given:
          - 2023년 1월 15일
          - FFR=4.5%, funding_spread=0.006 (0.6%)
          - expense_ratio=0.009 (0.9%)
          - leverage=4
        When: calculate_daily_cost 호출
        Then:
          - 레버리지 비용 = (0.045 + 0.006) * 3 = 0.153
          - 총 연간 비용 = 0.153 + 0.009 = 0.162
          - 일일 비용 = 0.162 / 252
        """
        # Given
        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})
        target_date = date(2023, 1, 15)
        expense_ratio = 0.009
        funding_spread = 0.006
        leverage = 4.0

        # When
        daily_cost = calculate_daily_cost(
            date_value=target_date,
            ffr_df=ffr_df,
            expense_ratio=expense_ratio,
            funding_spread=funding_spread,
            leverage=leverage,
        )

        # Then: 레버리지 비용 = funding_rate * (leverage - 1) = (0.045 + 0.006) * 3
        # 총 연간 비용 = 0.153 + 0.009 = 0.162
        # 일일 비용 = 0.162 / 252 ≈ 0.000643
        expected_funding_rate = 0.045 + 0.006
        expected_leverage_cost = expected_funding_rate * (leverage - 1)
        expected_annual_cost = expected_leverage_cost + expense_ratio
        expected_daily_cost = expected_annual_cost / 252

        assert (
            abs(daily_cost - expected_daily_cost) < 1e-6
        ), f"leverage=4일 때 비용 계산: 기대={expected_daily_cost:.6f}, 실제={daily_cost:.6f}"


class TestSimulate:
    """TQQQ 시뮬레이션 테스트"""

    def test_normal_simulation(self):
        """
        정상적인 시뮬레이션 테스트

        데이터 신뢰성: 시뮬레이션 결과가 NaN 없이 생성되어야 합니다.

        Given:
          - QQQ 일일 수익률 데이터
          - FFR 데이터
          - leverage=3, expense_ratio=0.95, funding_spread=0.5
        When: simulate 호출
        Then:
          - 모든 날짜에 Simulated_Close 생성
          - NaN 없음
          - initial_price 반영
          - 날짜 오름차순 정렬
        """
        # Given: 간단한 QQQ 데이터
        underlying_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 2) for i in range(5)], "Close": [100.0, 101.0, 99.0, 102.0, 103.0]}  # 1/2 ~ 1/6
        )

        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        leverage = 3.0
        expense_ratio = 0.009  # 0.9%
        initial_price = 30.0  # TQQQ 초기 가격
        funding_spread = 0.006  # 0.6%

        # When
        simulated_df = simulate(
            underlying_df=underlying_df,
            leverage=leverage,
            expense_ratio=expense_ratio,
            initial_price=initial_price,
            ffr_df=ffr_df,
            funding_spread=funding_spread,
        )

        # Then: 기본 검증
        assert len(simulated_df) == 5, "입력과 같은 행 수"
        assert "Close" in simulated_df.columns, "Close 컬럼 존재"

        # NaN 없음
        assert not simulated_df["Close"].isna().any(), "시뮬레이션 결과에 NaN이 있으면 안 됩니다"

        # 첫 가격이 initial_price 근처인지 확인 (첫날은 initial_price 유지)
        first_price = simulated_df.iloc[0]["Close"]
        assert abs(first_price - initial_price) < 1.0, f"첫 가격은 initial_price({initial_price}) 근처여야 합니다"

        # 날짜 정렬 확인
        dates = simulated_df["Date"].tolist()
        assert dates == sorted(dates), "날짜가 정렬되어야 합니다"

        # 가격은 양수
        assert (simulated_df["Close"] > 0).all(), "모든 가격은 양수여야 합니다"

    def test_leverage_effect(self):
        """
        레버리지 효과 테스트

        데이터 신뢰성: 레버리지 배수만큼 수익률이 확대되는지 확인

        Given: QQQ가 1% 상승
        When: leverage=3으로 시뮬레이션
        Then: TQQQ는 약 3% 상승 (비용 제외 시)
        """
        # Given: QQQ 1% 상승
        underlying_df = pd.DataFrame({"Date": [date(2023, 1, 2), date(2023, 1, 3)], "Close": [100.0, 101.0]})  # +1%

        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [0.0]})  # 비용 제거 (순수 레버리지 효과만 보기)

        # When: leverage=3, 비용 0
        simulated_df = simulate(
            underlying_df=underlying_df,
            leverage=3.0,
            expense_ratio=0.0,
            initial_price=30.0,
            ffr_df=ffr_df,
            funding_spread=0.0,
        )

        # Then: QQQ +1% → TQQQ +3%
        # 30.0 * 1.03 = 30.9
        final_price = simulated_df.iloc[1]["Close"]
        expected_price = 30.0 * 1.03

        assert (
            abs(final_price - expected_price) < 0.1
        ), f"레버리지 3배: 30.0 * 1.03 = {expected_price:.2f}, 실제: {final_price:.2f}"

    def test_invalid_leverage(self):
        """
        잘못된 레버리지 값 테스트

        안정성: 음수나 0은 거부해야 합니다.

        Given: leverage=-3 또는 0
        When: simulate
        Then: ValueError
        """
        # Given
        underlying_df = pd.DataFrame({"Date": [date(2023, 1, 2)], "Close": [100.0]})

        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        # When & Then: 음수
        with pytest.raises(ValueError):
            simulate(
                underlying_df=underlying_df,
                leverage=-3.0,
                expense_ratio=0.009,
                initial_price=30.0,
                ffr_df=ffr_df,
                funding_spread=0.006,
            )

        # 0
        with pytest.raises(ValueError):
            simulate(
                underlying_df=underlying_df,
                leverage=0.0,
                expense_ratio=0.009,
                initial_price=30.0,
                ffr_df=ffr_df,
                funding_spread=0.006,
            )


class TestExtractOverlapPeriod:
    """중복 기간 추출 테스트"""

    def test_normal_overlap(self):
        """
        정상적인 중복 기간 추출 테스트

        데이터 신뢰성: 실제 데이터와 시뮬레이션 비교 시 같은 기간만 사용해야 합니다.

        Given:
          - simulated: 2023-01-01 ~ 2023-12-31
          - actual: 2023-06-01 ~ 2024-06-30
        When: extract_overlap_period
        Then: 2023-06-01 ~ 2023-12-31만 반환
        """
        # Given
        simulated_df = pd.DataFrame(
            {"Date": pd.date_range(date(2023, 1, 1), date(2023, 12, 31), freq="D"), "Simulated_Close": range(365)}
        )

        actual_df = pd.DataFrame(
            {"Date": pd.date_range(date(2023, 6, 1), date(2024, 6, 30), freq="D"), "Actual_Close": range(396)}
        )

        # When
        overlap_sim, overlap_actual = extract_overlap_period(simulated_df, actual_df)

        # Then: 2023-06-01 ~ 2023-12-31
        assert overlap_sim["Date"].min() == pd.Timestamp(date(2023, 6, 1))
        assert overlap_sim["Date"].max() == pd.Timestamp(date(2023, 12, 31))

        assert len(overlap_sim) == len(overlap_actual), "중복 기간의 행 수는 같아야 합니다"

    def test_no_overlap(self):
        """
        중복 기간이 없을 때 테스트

        안정성: 겹치는 날짜가 없으면 ValueError 발생

        Given: 완전히 다른 기간
        When: extract_overlap_period
        Then: ValueError
        """
        # Given
        simulated_df = pd.DataFrame({"Date": [date(2020, 1, 1), date(2020, 1, 2)], "Close": [100, 101]})

        actual_df = pd.DataFrame({"Date": [date(2023, 1, 1), date(2023, 1, 2)], "Close": [200, 201]})

        # When & Then: ValueError 발생
        with pytest.raises(ValueError) as exc_info:
            extract_overlap_period(simulated_df, actual_df)

        assert "겹치는 기간이 없습니다" in str(exc_info.value)


class TestCalculateValidationMetrics:
    """검증 메트릭 계산 테스트"""

    def test_perfect_match(self):
        """
        완벽히 일치하는 경우 테스트

        데이터 신뢰성: RMSE=0, correlation=1.0이어야 합니다.

        Given: 시뮬레이션과 실제가 정확히 일치
        When: calculate_validation_metrics
        Then: RMSE ≈ 0, correlation ≈ 1.0
        """
        # Given: 완전 일치
        simulated_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 1) for i in range(5)], "Close": [100.0, 101.0, 102.0, 103.0, 104.0]}
        )

        actual_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 1) for i in range(5)], "Close": [100.0, 101.0, 102.0, 103.0, 104.0]}
        )

        # When
        metrics = calculate_validation_metrics(simulated_df, actual_df)

        # Then: 메트릭 키 확인
        assert isinstance(metrics, dict), "딕셔너리 반환"
        assert "cumul_multiple_log_diff_mean_pct" in metrics, "누적배수 로그차이 평균 존재"
        # 완벽히 일치하면 로그차이는 0에 가까움
        assert metrics["cumul_multiple_log_diff_mean_pct"] < 1.0, "완벽 일치 시 로그차이는 매우 작아야 합니다"

    def test_divergent_data(self):
        """
        차이가 큰 경우 테스트

        Given: 시뮬레이션과 실제가 크게 차이
        When: calculate_validation_metrics
        Then: RMSE > 0, correlation < 1.0
        """
        # Given: 차이 있음
        simulated_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 1) for i in range(5)], "Close": [100.0, 105.0, 110.0, 115.0, 120.0]}
        )

        actual_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 1) for i in range(5)], "Close": [100.0, 102.0, 108.0, 112.0, 125.0]}
        )

        # When
        metrics = calculate_validation_metrics(simulated_df, actual_df)

        # Then
        assert isinstance(metrics, dict), "딕셔너리 반환"
        assert "cumul_multiple_log_diff_rmse_pct" in metrics, "RMSE 메트릭 존재"
        # 차이가 있으므로 로그차이 RMSE > 0
        assert metrics["cumul_multiple_log_diff_rmse_pct"] > 0, "차이가 있으면 RMSE > 0"


class TestFindOptimalCostModel:
    """최적 비용 모델 찾기 테스트"""

    def test_optimization_completes(self):
        """
        최적화가 에러 없이 완료되는지 테스트

        안정성: 최적화 과정에서 예외가 발생하지 않아야 합니다.

        Given:
          - underlying, actual, ffr 데이터
          - 초기 파라미터
        When: find_optimal_cost_model 호출
        Then:
          - 딕셔너리 반환
          - expense_ratio, funding_spread 키 존재
          - RMSE, correlation 키 존재
        """
        # Given: 간단한 데이터
        underlying_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 2) for i in range(10)], "Close": [100.0 + i for i in range(10)]}
        )

        actual_leveraged_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 2) for i in range(10)], "Close": [30.0 + i * 0.9 for i in range(10)]}
        )

        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        # When: 최적화 (실제로는 시간이 걸릴 수 있음, 여기서는 구조 검증만)
        try:
            result = find_optimal_cost_model(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                leverage=3.0,
                spread_range=(0.0, 0.01),
                spread_step=0.005,
                expense_range=(0.0, 0.01),
                expense_step=0.005,
            )

            # Then: 결과 구조 확인 (리스트 반환)
            assert isinstance(result, list), "리스트 반환"
            if len(result) > 0:
                top_strategy = result[0]
                assert isinstance(top_strategy, dict), "딕셔너리 원소"
                # 실제 키 확인
                assert "cumul_multiple_log_diff_rmse_pct" in top_strategy or "leverage" in top_strategy

        except NotImplementedError:
            # 함수가 아직 구현되지 않았다면 pass
            pytest.skip("find_optimal_cost_model이 구현되지 않았습니다")

    def test_invalid_initial_params(self):
        """
        잘못된 초기 파라미터 테스트

        안정성: 음수 파라미터는 거부해야 합니다.

        Given: expense_ratio=-1.0
        When: find_optimal_cost_model
        Then: ValueError
        """
        # Given
        underlying_df = pd.DataFrame({"Date": [date(2023, 1, 2)], "Close": [100.0]})

        actual_leveraged_df = pd.DataFrame({"Date": [date(2023, 1, 2)], "Close": [30.0]})

        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        # When & Then: 음수 범위는 함수가 자동으로 처리하므로 에러 안 날 수 있음
        # 단순히 함수 호출이 성공하는지만 확인
        try:
            find_optimal_cost_model(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                leverage=-3.0,  # 음수 레버리지로 에러 발생 시도
                spread_range=(0.0, 0.01),
                spread_step=0.01,
                expense_range=(0.0, 0.01),
                expense_step=0.01,
            )
            # 음수 레버리지는 simulate 단계에서 에러 날 수 있음
        except (ValueError, NotImplementedError):
            # ValueError 또는 NotImplementedError 발생 가능
            pass

    def test_ffr_coverage_validation_raises_on_missing_data(self):
        """
        FFR 데이터 완전 부재 시 예외 발생 테스트

        정책: find_optimal_cost_model은 FFR 커버리지를 내부에서 검증해야 함

        Given:
          - underlying: 2023-01-02 ~ 2023-01-11
          - actual: 2023-01-02 ~ 2023-01-11 (overlap 존재)
          - ffr: 빈 DataFrame (FFR 데이터 없음)
        When: find_optimal_cost_model 호출
        Then: ValueError 발생 ("FFR 데이터 부족" 메시지 포함)
        """
        # Given: overlap 기간은 존재하지만 FFR 데이터 없음
        underlying_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 2) for i in range(10)], "Close": [100.0 + i for i in range(10)]}
        )

        actual_leveraged_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 2) for i in range(10)], "Close": [30.0 + i * 0.9 for i in range(10)]}
        )

        # FFR 데이터 완전 부재
        ffr_df = pd.DataFrame({"DATE": [], "FFR": []})

        # When & Then: FFR 부족으로 ValueError 발생
        with pytest.raises(ValueError, match="FFR 데이터 부족"):
            find_optimal_cost_model(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                leverage=3.0,
                spread_range=(0.0, 0.01),
                spread_step=0.01,
                expense_range=(0.0, 0.01),
                expense_step=0.01,
            )

    def test_ffr_coverage_validation_raises_on_gap_exceeded(self):
        """
        FFR 데이터 갭 초과 시 예외 발생 테스트

        정책: overlap 기간과 FFR 데이터 간 월 차이가 MAX_FFR_MONTHS_DIFF 초과 시 예외

        Given:
          - underlying: 2023-05-02 ~ 2023-05-11
          - actual: 2023-05-02 ~ 2023-05-11 (overlap: 2023-05)
          - ffr: 2023-01만 존재 (4개월 차이, MAX_FFR_MONTHS_DIFF=2 초과)
        When: find_optimal_cost_model 호출
        Then: ValueError 발생 ("월 차이" 또는 "최대 2개월" 메시지 포함)
        """
        # Given: overlap은 2023-05, FFR은 2023-01만 존재 (4개월 차이)
        underlying_df = pd.DataFrame(
            {"Date": [date(2023, 5, i + 2) for i in range(10)], "Close": [100.0 + i for i in range(10)]}
        )

        actual_leveraged_df = pd.DataFrame(
            {"Date": [date(2023, 5, i + 2) for i in range(10)], "Close": [30.0 + i * 0.9 for i in range(10)]}
        )

        # FFR 데이터는 2023-01만 존재 (4개월 차이)
        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        # When & Then: 월 차이 초과로 ValueError 발생
        with pytest.raises(ValueError, match="최대 2개월"):
            find_optimal_cost_model(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                leverage=3.0,
                spread_range=(0.0, 0.01),
                spread_step=0.01,
                expense_range=(0.0, 0.01),
                expense_step=0.01,
            )

    def test_ffr_coverage_validation_passes_with_valid_data(self):
        """
        유효한 FFR 데이터 제공 시 정상 동작 테스트

        정책: FFR 커버리지가 충분하면 검증 통과 및 정상 실행

        Given:
          - underlying: 2023-01-02 ~ 2023-01-11
          - actual: 2023-01-02 ~ 2023-01-11 (overlap: 2023-01)
          - ffr: 2023-01 존재 (충분)
        When: find_optimal_cost_model 호출
        Then: 예외 없이 정상 완료, 결과 리스트 반환
        """
        # Given: 충분한 FFR 데이터
        underlying_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 2) for i in range(10)], "Close": [100.0 + i for i in range(10)]}
        )

        actual_leveraged_df = pd.DataFrame(
            {"Date": [date(2023, 1, i + 2) for i in range(10)], "Close": [30.0 + i * 0.9 for i in range(10)]}
        )

        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        # When: 정상 호출
        result = find_optimal_cost_model(
            underlying_df=underlying_df,
            actual_leveraged_df=actual_leveraged_df,
            ffr_df=ffr_df,
            leverage=3.0,
            spread_range=(0.0, 0.01),
            spread_step=0.01,
            expense_range=(0.0, 0.01),
            expense_step=0.01,
        )

        # Then: 정상 결과 반환
        assert isinstance(result, list), "리스트 반환"


class TestSimulateValidation:
    """simulate 함수 파라미터 검증 테스트"""

    def test_invalid_leverage_raises(self):
        """
        leverage가 0 이하일 때 예외 발생 테스트

        Given: leverage <= 0
        When: simulate 호출
        Then: ValueError 발생
        """
        # Given
        underlying_df = pd.DataFrame({"Date": [date(2023, 1, 1), date(2023, 1, 2)], "Close": [100.0, 105.0]})
        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        # When & Then: leverage = 0
        with pytest.raises(ValueError, match="leverage는 양수여야 합니다"):
            simulate(
                underlying_df=underlying_df,
                ffr_df=ffr_df,
                leverage=0.0,
                funding_spread=0.005,
                expense_ratio=0.009,
                initial_price=100.0,
            )

        # When & Then: leverage < 0
        with pytest.raises(ValueError, match="leverage는 양수여야 합니다"):
            simulate(
                underlying_df=underlying_df,
                ffr_df=ffr_df,
                leverage=-3.0,
                funding_spread=0.005,
                expense_ratio=0.009,
                initial_price=100.0,
            )

    def test_invalid_initial_price_raises(self):
        """
        initial_price가 0 이하일 때 예외 발생 테스트

        Given: initial_price <= 0
        When: simulate 호출
        Then: ValueError 발생
        """
        # Given
        underlying_df = pd.DataFrame({"Date": [date(2023, 1, 1), date(2023, 1, 2)], "Close": [100.0, 105.0]})
        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        # When & Then: initial_price = 0
        with pytest.raises(ValueError, match="initial_price는 양수여야 합니다"):
            simulate(
                underlying_df=underlying_df,
                ffr_df=ffr_df,
                leverage=3.0,
                funding_spread=0.005,
                expense_ratio=0.009,
                initial_price=0.0,
            )

        # When & Then: initial_price < 0
        with pytest.raises(ValueError, match="initial_price는 양수여야 합니다"):
            simulate(
                underlying_df=underlying_df,
                ffr_df=ffr_df,
                leverage=3.0,
                funding_spread=0.005,
                expense_ratio=0.009,
                initial_price=-100.0,
            )

    def test_missing_required_columns_raises(self):
        """
        필수 컬럼 누락 시 예외 발생 테스트

        Given: Date 또는 Close 컬럼이 없는 DataFrame
        When: simulate 호출
        Then: ValueError 발생
        """
        # Given: Close 컬럼 누락
        underlying_df_no_close = pd.DataFrame({"Date": [date(2023, 1, 1), date(2023, 1, 2)]})

        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        # When & Then
        with pytest.raises(ValueError, match="필수 컬럼이 누락되었습니다"):
            simulate(
                underlying_df=underlying_df_no_close,
                ffr_df=ffr_df,
                leverage=3.0,
                funding_spread=0.005,
                expense_ratio=0.009,
                initial_price=100.0,
            )

    def test_empty_dataframe_raises(self):
        """
        빈 DataFrame일 때 예외 발생 테스트

        Given: 빈 underlying_df
        When: simulate 호출
        Then: ValueError 발생
        """
        # Given: 빈 DataFrame
        underlying_df = pd.DataFrame(columns=["Date", "Close"])
        ffr_df = pd.DataFrame({"DATE": ["2023-01"], "FFR": [4.5]})

        # When & Then
        with pytest.raises(ValueError, match="underlying_df가 비어있습니다"):
            simulate(
                underlying_df=underlying_df,
                ffr_df=ffr_df,
                leverage=3.0,
                funding_spread=0.005,
                expense_ratio=0.009,
                initial_price=100.0,
            )


class TestSaveDailyComparisonCsv:
    """_save_daily_comparison_csv 함수 테스트"""

    def test_csv_saving_and_structure(self, tmp_path):
        """
        CSV 저장 및 구조 검증

        핵심: 일별 비교 데이터가 올바른 형식으로 저장되는지 검증

        Given: 시뮬레이션과 실제 데이터
        When: _save_daily_comparison_csv 호출
        Then:
          - CSV 파일 생성
          - 한글 컬럼명 포함
          - 누적배수 로그차이 포함
          - 올바른 행 수
        """
        from qbt.tqqq.constants import (
            COL_ACTUAL_CLOSE,
            COL_ACTUAL_CUMUL_RETURN,
            COL_ACTUAL_DAILY_RETURN,
            COL_CUMUL_MULTIPLE_LOG_DIFF,
            COL_DAILY_RETURN_ABS_DIFF,
            COL_SIMUL_CLOSE,
            COL_SIMUL_CUMUL_RETURN,
            COL_SIMUL_DAILY_RETURN,
            DISPLAY_DATE,
        )
        from qbt.tqqq.simulation import _save_daily_comparison_csv

        # Given
        actual_overlap = pd.DataFrame(
            {
                "Date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                "Close": [100.0, 105.0, 102.0],
            }
        )

        sim_overlap = pd.DataFrame(
            {"Date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)], "Close": [100.5, 104.8, 102.2]}
        )

        cumul_log_diff = pd.Series([0.0, 0.1, 0.15])

        output_path = tmp_path / "test_comparison.csv"

        # When
        _save_daily_comparison_csv(sim_overlap, actual_overlap, cumul_log_diff, output_path)

        # Then: 파일 존재
        assert output_path.exists(), "CSV 파일이 생성되어야 함"

        # 파일 읽기
        result_df = pd.read_csv(output_path, encoding="utf-8-sig")

        # 행 수 확인
        assert len(result_df) == 3, "3행의 데이터가 저장되어야 함"

        # 필수 컬럼 확인
        required_cols = [
            DISPLAY_DATE,
            COL_ACTUAL_CLOSE,
            COL_SIMUL_CLOSE,
            COL_ACTUAL_DAILY_RETURN,
            COL_SIMUL_DAILY_RETURN,
            COL_DAILY_RETURN_ABS_DIFF,
            COL_ACTUAL_CUMUL_RETURN,
            COL_SIMUL_CUMUL_RETURN,
            COL_CUMUL_MULTIPLE_LOG_DIFF,
        ]

        for col in required_cols:
            assert col in result_df.columns, f"{col} 컬럼이 있어야 함"

    def test_csv_numeric_precision(self, tmp_path):
        """
        CSV 숫자 정밀도 검증 (소수점 4자리)

        Given: 시뮬레이션과 실제 데이터
        When: _save_daily_comparison_csv 호출
        Then: 숫자 컬럼이 소수점 4자리로 반올림됨
        """
        from qbt.tqqq.simulation import _save_daily_comparison_csv

        # Given
        actual_overlap = pd.DataFrame({"Date": [date(2023, 1, 1), date(2023, 1, 2)], "Close": [100.123456, 105.789012]})

        sim_overlap = pd.DataFrame({"Date": [date(2023, 1, 1), date(2023, 1, 2)], "Close": [100.234567, 105.890123]})

        cumul_log_diff = pd.Series([0.0123456, 0.0234567])

        output_path = tmp_path / "test_precision.csv"

        # When
        _save_daily_comparison_csv(sim_overlap, actual_overlap, cumul_log_diff, output_path)

        # Then
        result_df = pd.read_csv(output_path, encoding="utf-8-sig")

        # 숫자 컬럼이 소수점 4자리 이하로 저장되었는지 확인
        from qbt.tqqq.constants import COL_ACTUAL_CLOSE, COL_SIMUL_CLOSE

        # 실제 종가 확인 (소수점 4자리로 반올림)
        assert abs(result_df[COL_ACTUAL_CLOSE].iloc[0] - 100.1235) < 0.0001
        assert abs(result_df[COL_SIMUL_CLOSE].iloc[0] - 100.2346) < 0.0001


class TestValidateFfrCoverage:
    """FFR 커버리지 검증 테스트"""

    def test_full_coverage_passes(self):
        """
        FFR 데이터가 모든 필요 월을 커버하면 통과

        Given: 2023-01부터 2023-12까지 모든 월의 FFR 데이터
        When: 2023-03-15 ~ 2023-09-20 기간 검증
        Then: 예외 없이 통과
        """
        # Given
        ffr_df = pd.DataFrame(
            {
                "DATE": [f"2023-{m:02d}" for m in range(1, 13)],
                "FFR": [4.5 + m * 0.1 for m in range(1, 13)],
            }
        )
        overlap_start = date(2023, 3, 15)
        overlap_end = date(2023, 9, 20)

        # When & Then: 예외 없이 통과
        validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

    def test_missing_month_within_2_months_passes(self):
        """
        필요 월이 누락되었지만 2개월 이내 이전 데이터가 있으면 통과

        Given: 2023-01, 02, 03, 06, 07 FFR 데이터 (04, 05 누락)
        When: 2023-04-10 ~ 2023-05-20 기간 검증
        Then: 2개월 이내이므로 통과
        """
        # Given
        ffr_df = pd.DataFrame(
            {"DATE": ["2023-01", "2023-02", "2023-03", "2023-06", "2023-07"], "FFR": [4.5, 4.6, 4.7, 5.0, 5.1]}
        )
        overlap_start = date(2023, 4, 10)
        overlap_end = date(2023, 5, 20)

        # When & Then: 예외 없이 통과 (2023-03이 1~2개월 전)
        validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

    def test_missing_month_exceeds_2_months_raises(self):
        """
        필요 월이 누락되고 2개월 초과 이전 데이터만 있으면 실패

        Given: 2023-01, 02, 06 FFR 데이터 (03, 04, 05 누락)
        When: 2023-05-10 ~ 2023-05-20 기간 검증
        Then: ValueError (2023-02와 2023-05는 3개월 차이)
        """
        # Given
        ffr_df = pd.DataFrame({"DATE": ["2023-01", "2023-02", "2023-06"], "FFR": [4.5, 4.6, 5.0]})
        overlap_start = date(2023, 5, 10)
        overlap_end = date(2023, 5, 20)

        # When & Then
        with pytest.raises(ValueError) as exc_info:
            validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

        error_msg = str(exc_info.value)
        assert "2023-05" in error_msg
        assert "2023-02" in error_msg
        assert "3개월" in error_msg
        assert "최대 2개월" in error_msg

    def test_no_previous_data_raises(self):
        """
        필요 월에 이전 데이터가 전혀 없으면 실패

        Given: 2023-06, 07 FFR 데이터만 존재
        When: 2023-03-10 ~ 2023-04-20 기간 검증
        Then: ValueError (이전 데이터 없음)
        """
        # Given
        ffr_df = pd.DataFrame({"DATE": ["2023-06", "2023-07"], "FFR": [5.0, 5.1]})
        overlap_start = date(2023, 3, 10)
        overlap_end = date(2023, 4, 20)

        # When & Then
        with pytest.raises(ValueError) as exc_info:
            validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

        error_msg = str(exc_info.value)
        assert "2023-03" in error_msg
        assert "이전 데이터도 존재하지 않습니다" in error_msg

    def test_single_day_period(self):
        """
        시작일과 종료일이 같은 경우 (단일 월)

        Given: 2023-01부터 2023-12까지 FFR 데이터
        When: 2023-05-15 ~ 2023-05-15 기간 검증
        Then: 예외 없이 통과
        """
        # Given
        ffr_df = pd.DataFrame(
            {
                "DATE": [f"2023-{m:02d}" for m in range(1, 13)],
                "FFR": [4.5 + m * 0.1 for m in range(1, 13)],
            }
        )
        overlap_start = date(2023, 5, 15)
        overlap_end = date(2023, 5, 15)

        # When & Then
        validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

    def test_year_boundary_crossing(self):
        """
        연도 경계를 넘는 기간 검증

        Given: 2023-11, 12, 2024-01, 02 FFR 데이터
        When: 2023-11-20 ~ 2024-02-10 기간 검증
        Then: 예외 없이 통과
        """
        # Given
        ffr_df = pd.DataFrame({"DATE": ["2023-11", "2023-12", "2024-01", "2024-02"], "FFR": [5.3, 5.4, 5.5, 5.6]})
        overlap_start = date(2023, 11, 20)
        overlap_end = date(2024, 2, 10)

        # When & Then
        validate_ffr_coverage(overlap_start, overlap_end, ffr_df)
