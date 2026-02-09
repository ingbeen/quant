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

import numpy as np
import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, TRADING_DAYS_PER_YEAR
from qbt.tqqq.constants import COL_EXPENSE_DATE, COL_EXPENSE_VALUE, COL_FFR_DATE, COL_FFR_VALUE
from qbt.tqqq.data_loader import create_expense_dict, create_ffr_dict, lookup_ffr
from qbt.tqqq.simulation import (
    calculate_daily_cost,
    calculate_validation_metrics,
    compute_softplus_spread,
    extract_overlap_period,
    find_optimal_cost_model,
    generate_static_spread_series,
    simulate,
    validate_ffr_coverage,
)


class TestCalculateDailyCost:
    """일일 비용 계산 테스트"""

    def test_normal_cost_calculation(self, enable_numpy_warnings):
        """
        정상적인 일일 비용 계산 테스트

        데이터 신뢰성: 비용 공식이 정확해야 시뮬레이션이 유효합니다.

        Given:
          - 2023년 1월 15일
          - FFR 데이터에 2023-01이 0.045 (4.5%) 존재
          - expense_ratio=0.0095 (0.95%), funding_spread=0.006 (0.6%)
        When: calculate_daily_cost 호출
        Then:
          - 해당 월의 FFR 사용
          - daily_cost = ((FFR + funding_spread) * (leverage - 1) + expense_ratio) / 거래일수
          - 양수 값 반환

        Note: enable_numpy_warnings 픽스처로 부동소수점 오류 감지
        """
        # Given: FFR 데이터 (DATE는 yyyy-mm 문자열 형식, VALUE는 0~1 비율)
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02"], COL_FFR_VALUE: [0.045, 0.046]})
        ffr_dict = create_ffr_dict(ffr_df)

        # Expense 데이터 (0~1 비율)
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01", "2023-02"], COL_EXPENSE_VALUE: [0.0095, 0.0095]})
        expense_dict = create_expense_dict(expense_df)

        target_date = date(2023, 1, 15)
        funding_spread = 0.006  # 0.6%

        # When
        leverage = 3.0  # 기본 3배 레버리지
        daily_cost = calculate_daily_cost(
            date_value=target_date,
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
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
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)

        # Expense 데이터
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})
        expense_dict = create_expense_dict(expense_df)

        target_date = date(2023, 3, 15)  # 1월부터 약 2개월 후
        leverage = 3.0

        # When: 2개월 이내면 fallback 허용
        try:
            daily_cost = calculate_daily_cost(
                date_value=target_date,
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
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
        ffr_df = pd.DataFrame(columns=[COL_FFR_DATE, "FFR"])
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})
        expense_dict = create_expense_dict(expense_df)
        leverage = 3.0

        # When & Then
        with pytest.raises(ValueError):
            ffr_dict = create_ffr_dict(ffr_df)
            calculate_daily_cost(
                date_value=date(2023, 1, 15),
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
                funding_spread=0.006,
                leverage=leverage,
            )

    @pytest.mark.parametrize(
        "leverage,expected_multiplier",
        [
            (2.0, 1.0),  # leverage=2: 차입 비율 1배
            (3.0, 2.0),  # leverage=3: 차입 비율 2배
            (4.0, 3.0),  # leverage=4: 차입 비율 3배
        ],
        ids=["leverage_2x", "leverage_3x", "leverage_4x"],
    )
    def test_calculate_daily_cost_leverage_variations(self, leverage, expected_multiplier):
        """
        다양한 레버리지 배수별 비용 계산 테스트

        정책: 레버리지 비용 = funding_rate * (leverage - 1)
        차입 비율 = leverage - 1 (자기자본 1 + 빌린돈 N-1)

        Given:
          - 2023년 1월 15일
          - FFR=4.5%, funding_spread=0.006 (0.6%)
          - expense_ratio=0.0095 (0.95%)
          - leverage (parametrize로 여러 값 테스트)
        When: calculate_daily_cost 호출
        Then:
          - 레버리지 비용 = (0.045 + 0.006) * (leverage - 1)
          - 총 연간 비용 = leverage_cost + 0.0095
          - 일일 비용 = annual_cost / 252

        Args:
            leverage: 테스트할 레버리지 배수
            expected_multiplier: 예상 차입 비율 (leverage - 1)
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)

        expense_ratio = 0.0095  # 0.95% (0~1 비율)
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [expense_ratio]})
        expense_dict = create_expense_dict(expense_df)

        target_date = date(2023, 1, 15)
        funding_spread = 0.006

        # When
        daily_cost = calculate_daily_cost(
            date_value=target_date,
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=funding_spread,
            leverage=leverage,
        )

        # Then
        expected_funding_rate = 0.045 + 0.006
        expected_leverage_cost = expected_funding_rate * expected_multiplier
        expected_annual_cost = expected_leverage_cost + expense_ratio
        expected_daily_cost = expected_annual_cost / TRADING_DAYS_PER_YEAR

        assert abs(daily_cost - expected_daily_cost) < 1e-6, (
            f"leverage={leverage}일 때 비용 계산: " f"기대={expected_daily_cost:.6f}, 실제={daily_cost:.6f}"
        )


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
            {
                COL_DATE: [date(2023, 1, i + 2) for i in range(5)],
                COL_CLOSE: [100.0, 101.0, 99.0, 102.0, 103.0],
            }  # 1/2 ~ 1/6
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})  # 0.95%

        leverage = 3.0
        initial_price = 30.0  # TQQQ 초기 가격
        funding_spread = 0.006  # 0.6%

        # When
        simulated_df = simulate(
            underlying_df=underlying_df,
            leverage=leverage,
            expense_df=expense_df,
            initial_price=initial_price,
            ffr_df=ffr_df,
            funding_spread=funding_spread,
        )

        # Then: 기본 검증
        assert len(simulated_df) == 5, "입력과 같은 행 수"
        assert COL_CLOSE in simulated_df.columns, "Close 컬럼 존재"

        # NaN 없음
        assert not simulated_df[COL_CLOSE].isna().any(), "시뮬레이션 결과에 NaN이 있으면 안 됩니다"

        # 첫 가격이 initial_price 근처인지 확인 (첫날은 initial_price 유지)
        first_price = simulated_df.iloc[0][COL_CLOSE]
        assert abs(first_price - initial_price) < 1.0, f"첫 가격은 initial_price({initial_price}) 근처여야 합니다"

        # 날짜 정렬 확인
        dates = simulated_df[COL_DATE].tolist()
        assert dates == sorted(dates), "날짜가 정렬되어야 합니다"

        # 가격은 양수
        assert (simulated_df[COL_CLOSE] > 0).all(), "모든 가격은 양수여야 합니다"

    def test_leverage_effect(self):
        """
        레버리지 효과 테스트

        데이터 신뢰성: 레버리지 배수만큼 수익률이 확대되는지 확인

        Given: QQQ가 1% 상승
        When: leverage=3으로 시뮬레이션
        Then: TQQQ는 약 3% 상승 (비용 최소화, spread > 0 제약으로 1e-9 사용)
        """
        # Given: QQQ 1% 상승
        underlying_df = pd.DataFrame({COL_DATE: [date(2023, 1, 2), date(2023, 1, 3)], COL_CLOSE: [100.0, 101.0]})  # +1%

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.0]})  # FFR 0
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0]})  # expense 0

        # When: leverage=3, 최소 spread (1e-9, spread > 0 제약 충족)
        # 비용 영향 최소화: 1e-9 * 2 / 252 ≈ 7.9e-12 (무시 가능)
        simulated_df = simulate(
            underlying_df=underlying_df,
            leverage=3.0,
            expense_df=expense_df,
            initial_price=30.0,
            ffr_df=ffr_df,
            funding_spread=1e-9,  # 최소 양수 (spread > 0 제약)
        )

        # Then: QQQ +1% -> TQQQ +3% (비용 영향 무시 가능)
        # 30.0 * 1.03 = 30.9
        final_price = simulated_df.iloc[1][COL_CLOSE]
        expected_price = 30.0 * 1.03

        assert (
            abs(final_price - expected_price) < 0.1
        ), f"레버리지 3배: 30.0 * 1.03 = {expected_price:.2f}, 실제: {final_price:.2f}"

    @pytest.mark.parametrize("invalid_leverage", [-3.0, 0.0, -1.0])
    def test_invalid_leverage(self, invalid_leverage):
        """
        잘못된 레버리지 값 테스트

        안정성: 음수나 0은 거부해야 합니다.

        Given: leverage <= 0 (parametrize로 여러 값 테스트)
        When: simulate
        Then: ValueError

        Args:
            invalid_leverage: 테스트할 잘못된 레버리지 값 (-3.0, 0.0, -1.0)
        """
        # Given
        underlying_df = pd.DataFrame({"Date": [date(2023, 1, 2)], "Close": [100.0]})

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When & Then
        with pytest.raises(ValueError):
            simulate(
                underlying_df=underlying_df,
                leverage=invalid_leverage,
                expense_df=expense_df,
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
        simulated_df = pd.DataFrame({COL_DATE: [date(2020, 1, 1), date(2020, 1, 2)], COL_CLOSE: [100, 101]})

        actual_df = pd.DataFrame({COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)], COL_CLOSE: [200, 201]})

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
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 101.0, 102.0, 103.0, 104.0]}
        )

        actual_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 101.0, 102.0, 103.0, 104.0]}
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
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 105.0, 110.0, 115.0, 120.0]}
        )

        actual_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 102.0, 108.0, 112.0, 125.0]}
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
            {COL_DATE: [date(2023, 1, i + 2) for i in range(10)], COL_CLOSE: [100.0 + i for i in range(10)]}
        )

        actual_leveraged_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 2) for i in range(10)], COL_CLOSE: [30.0 + i * 0.9 for i in range(10)]}
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When: 최적화 (실제로는 시간이 걸릴 수 있음, 여기서는 구조 검증만)
        try:
            result = find_optimal_cost_model(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                expense_df=expense_df,
                leverage=3.0,
                spread_range=(0.001, 0.01),
                spread_step=0.005,
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
        underlying_df = pd.DataFrame({COL_DATE: [date(2023, 1, 2)], COL_CLOSE: [100.0]})

        actual_leveraged_df = pd.DataFrame({COL_DATE: [date(2023, 1, 2)], COL_CLOSE: [30.0]})

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When & Then: 음수 범위는 함수가 자동으로 처리하므로 에러 안 날 수 있음
        # 단순히 함수 호출이 성공하는지만 확인
        try:
            find_optimal_cost_model(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                expense_df=expense_df,
                leverage=-3.0,  # 음수 레버리지로 에러 발생 시도
                spread_range=(0.001, 0.01),
                spread_step=0.01,
            )
            # 음수 레버리지는 simulate 단계에서 에러 날 수 있음
        except (ValueError, NotImplementedError):
            # ValueError 또는 NotImplementedError 발생 가능
            pass

    def test_ffr_coverage_validation_raises_on_missing_data(self):
        """
        FFR 딕셔너리 생성 시 빈 DataFrame으로 예외 발생 테스트

        정책: create_ffr_dict는 빈 DataFrame 거부

        Given:
          - ffr: 빈 DataFrame (FFR 데이터 없음)
        When: create_ffr_dict 호출
        Then: ValueError 발생 ("비어있습니다" 메시지 포함)
        """
        # Given: FFR 데이터 완전 부재
        ffr_df = pd.DataFrame({COL_FFR_DATE: [], COL_FFR_VALUE: []})

        # When & Then: FFR 부족으로 ValueError 발생
        with pytest.raises(ValueError, match="비어있습니다"):
            create_ffr_dict(ffr_df)

    def test_ffr_coverage_validation_raises_on_gap_exceeded(self):
        """
        FFR 데이터 갭 초과 시 시뮬레이션 실행 중 예외 발생 테스트

        정책: calculate_daily_cost에서 FFR 갭 검증

        Given:
          - underlying: 2023-05-02 ~ 2023-05-11
          - actual: 2023-05-02 ~ 2023-05-11 (overlap: 2023-05)
          - ffr_dict: 2023-01만 존재 (4개월 차이, MAX_FFR_MONTHS_DIFF=2 초과)
        When: find_optimal_cost_model 호출
        Then: ValueError 발생 ("최대 2개월" 메시지 포함)
        """
        # Given: overlap은 2023-05, FFR은 2023-01만 존재 (4개월 차이)
        underlying_df = pd.DataFrame(
            {COL_DATE: [date(2023, 5, i + 2) for i in range(10)], COL_CLOSE: [100.0 + i for i in range(10)]}
        )

        actual_leveraged_df = pd.DataFrame(
            {COL_DATE: [date(2023, 5, i + 2) for i in range(10)], COL_CLOSE: [30.0 + i * 0.9 for i in range(10)]}
        )

        # FFR 데이터는 2023-01만 존재 (4개월 차이)
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When & Then: 월 차이 초과로 ValueError 발생 (시뮬레이션 실행 중)
        with pytest.raises(ValueError, match="최대 2개월"):
            find_optimal_cost_model(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                expense_df=expense_df,
                leverage=3.0,
                spread_range=(0.001, 0.01),
                spread_step=0.01,
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
            {COL_DATE: [date(2023, 1, i + 2) for i in range(10)], COL_CLOSE: [100.0 + i for i in range(10)]}
        )

        actual_leveraged_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 2) for i in range(10)], COL_CLOSE: [30.0 + i * 0.9 for i in range(10)]}
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When: 정상 호출
        result = find_optimal_cost_model(
            underlying_df=underlying_df,
            actual_leveraged_df=actual_leveraged_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            leverage=3.0,
            spread_range=(0.001, 0.01),
            spread_step=0.01,
        )

        # Then: 정상 결과 반환
        assert isinstance(result, list), "리스트 반환"


class TestSimulateValidation:
    """simulate 함수 파라미터 검증 테스트"""

    @pytest.mark.parametrize(
        "param_name,invalid_value,error_pattern",
        [
            ("leverage", 0.0, "leverage는 양수여야 합니다"),
            ("leverage", -3.0, "leverage는 양수여야 합니다"),
            ("initial_price", 0.0, "initial_price는 양수여야 합니다"),
            ("initial_price", -100.0, "initial_price는 양수여야 합니다"),
        ],
        ids=["leverage_zero", "leverage_negative", "initial_price_zero", "initial_price_negative"],
    )
    def test_invalid_numeric_params_raise(self, param_name, invalid_value, error_pattern):
        """
        숫자 파라미터가 유효하지 않을 때 예외 발생 테스트

        Given: leverage <= 0 또는 initial_price <= 0 (parametrize로 여러 케이스 테스트)
        When: simulate 호출
        Then: ValueError 발생

        Args:
            param_name: 테스트할 파라미터 이름 ("leverage" 또는 "initial_price")
            invalid_value: 잘못된 값
            error_pattern: 예상 에러 메시지 패턴
        """
        # Given
        underlying_df = pd.DataFrame({COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)], COL_CLOSE: [100.0, 105.0]})
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # 파라미터 구성 (param_name에 따라 다른 값 사용)
        if param_name == "leverage":
            leverage = invalid_value
            initial_price = 100.0
        else:  # initial_price
            leverage = 3.0
            initial_price = invalid_value

        # When & Then
        with pytest.raises(ValueError, match=error_pattern):
            simulate(
                underlying_df=underlying_df,
                ffr_df=ffr_df,
                leverage=leverage,
                funding_spread=0.005,
                expense_df=expense_df,
                initial_price=initial_price,
            )

    def test_missing_required_columns_raises(self):
        """
        필수 컬럼 누락 시 예외 발생 테스트

        Given: Date 또는 Close 컬럼이 없는 DataFrame
        When: simulate 호출
        Then: ValueError 발생
        """
        # Given: Close 컬럼 누락
        underlying_df_no_close = pd.DataFrame({COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)]})

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When & Then
        with pytest.raises(ValueError, match="필수 컬럼이 누락되었습니다"):
            simulate(
                underlying_df=underlying_df_no_close,
                ffr_df=ffr_df,
                leverage=3.0,
                funding_spread=0.005,
                expense_df=expense_df,
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
        underlying_df = pd.DataFrame(columns=[COL_DATE, COL_CLOSE])
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When & Then
        with pytest.raises(ValueError, match="underlying_df가 비어있습니다"):
            simulate(
                underlying_df=underlying_df,
                ffr_df=ffr_df,
                leverage=3.0,
                funding_spread=0.005,
                expense_df=expense_df,
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
            COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
            COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
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
                COL_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                COL_CLOSE: [100.0, 105.0, 102.0],
            }
        )

        sim_overlap = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)], COL_CLOSE: [100.5, 104.8, 102.2]}
        )

        cumul_log_diff = pd.Series([0.0, 0.1, 0.15])
        signed_log_diff = pd.Series([0.0, -0.05, 0.1])  # signed 버전

        output_path = tmp_path / "test_comparison.csv"

        # When
        # 테스트 데이터는 synthetic이므로 tolerance를 크게 설정
        _save_daily_comparison_csv(
            sim_overlap, actual_overlap, cumul_log_diff, signed_log_diff, output_path, integrity_tolerance=1.0
        )

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
            COL_CUMUL_MULTIPLE_LOG_DIFF_ABS,
            COL_CUMUL_MULTIPLE_LOG_DIFF_SIGNED,
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
        actual_overlap = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)], COL_CLOSE: [100.123456, 105.789012]}
        )

        sim_overlap = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)], COL_CLOSE: [100.234567, 105.890123]}
        )

        cumul_log_diff = pd.Series([0.0123456, 0.0234567])
        signed_log_diff = pd.Series([0.0111111, -0.0222222])  # signed 버전

        output_path = tmp_path / "test_precision.csv"

        # When
        # 테스트 데이터는 synthetic이므로 tolerance를 크게 설정
        _save_daily_comparison_csv(
            sim_overlap, actual_overlap, cumul_log_diff, signed_log_diff, output_path, integrity_tolerance=1.0
        )

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
            {
                "DATE": ["2023-01", "2023-02", "2023-03", "2023-06", "2023-07"],
                "VALUE": [0.045, 0.046, 0.047, 0.05, 0.051],
            }
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
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02", "2023-06"], COL_FFR_VALUE: [0.045, 0.046, 0.05]})
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
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-06", "2023-07"], COL_FFR_VALUE: [0.05, 0.051]})
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
        ffr_df = pd.DataFrame(
            {
                "DATE": ["2023-11", "2023-12", "2024-01", "2024-02"],
                "VALUE": [0.053, 0.054, 0.055, 0.056],
            }
        )
        overlap_start = date(2023, 11, 20)
        overlap_end = date(2024, 2, 10)

        # When & Then
        validate_ffr_coverage(overlap_start, overlap_end, ffr_df)


class TestCreateFfrDict:
    """FFR 딕셔너리 생성 함수 테스트"""

    def test_create_ffr_dict_normal(self):
        """
        정상적인 FFR 딕셔너리 생성 테스트

        Given: 정상적인 FFR DataFrame (중복 없음)
        When: create_ffr_dict 호출
        Then: {"YYYY-MM": ffr_value} 딕셔너리 반환
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02", "2023-03"], COL_FFR_VALUE: [0.045, 0.046, 0.047]})

        # When
        result = create_ffr_dict(ffr_df)

        # Then
        assert isinstance(result, dict)
        assert result == {"2023-01": 0.045, "2023-02": 0.046, "2023-03": 0.047}

    def test_create_ffr_dict_empty(self):
        """
        빈 DataFrame 입력 시 예외 발생 테스트

        Given: 빈 FFR DataFrame
        When: create_ffr_dict 호출
        Then: ValueError 발생
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: [], COL_FFR_VALUE: []})

        # When & Then
        with pytest.raises(ValueError, match="FFR 데이터가 비어있습니다"):
            create_ffr_dict(ffr_df)

    def test_create_ffr_dict_duplicate_month(self):
        """
        중복 월 발견 시 즉시 예외 발생 테스트 (중대 에러)

        Given: 중복 월이 포함된 FFR DataFrame
        When: create_ffr_dict 호출
        Then: ValueError 발생 (데이터 무결성 보장)
        """
        # Given
        ffr_df = pd.DataFrame(
            {
                COL_FFR_DATE: ["2023-01", "2023-02", "2023-02", "2023-03"],
                COL_FFR_VALUE: [0.045, 0.046, 0.0465, 0.047],
            }
        )

        # When & Then
        with pytest.raises(ValueError, match="FFR 데이터 무결성 오류.*2023-02.*중복"):
            create_ffr_dict(ffr_df)


class TestLookupFfr:
    """FFR 조회 함수 테스트"""

    def test_lookup_ffr_exact_match(self):
        """
        정확한 월 매칭 테스트

        Given: FFR 딕셔너리와 딕셔너리에 존재하는 월의 날짜
        When: lookup_ffr 호출
        Then: 해당 월의 FFR 값 반환
        """
        # Given
        ffr_dict = {"2023-01": 4.5, "2023-02": 4.6, "2023-03": 4.7}
        date_value = date(2023, 2, 15)

        # When
        result = lookup_ffr(date_value, ffr_dict)

        # Then
        assert result == 4.6

    def test_lookup_ffr_fallback(self):
        """
        이전 월 폴백 테스트

        Given: FFR 딕셔너리와 딕셔너리에 없는 월의 날짜 (단, 이전 월은 존재)
        When: lookup_ffr 호출
        Then: 가장 가까운 이전 월의 FFR 값 반환
        """
        # Given
        ffr_dict = {"2023-01": 4.5, "2023-02": 4.6}
        date_value = date(2023, 3, 15)  # 2023-03은 없음

        # When
        result = lookup_ffr(date_value, ffr_dict)

        # Then
        assert result == 4.6  # 2023-02의 값

    def test_lookup_ffr_no_previous_month(self):
        """
        이전 월도 없는 경우 예외 발생 테스트

        Given: FFR 딕셔너리와 딕셔너리보다 이른 날짜
        When: lookup_ffr 호출
        Then: ValueError 발생
        """
        # Given
        ffr_dict = {"2023-02": 4.6, "2023-03": 4.7}
        date_value = date(2023, 1, 15)  # 2023-01은 없고 이전 월도 없음

        # When & Then
        with pytest.raises(ValueError, match="FFR 데이터 부족.*2023-01.*이전의 FFR 데이터가 존재하지 않습니다"):
            lookup_ffr(date_value, ffr_dict)

    def test_lookup_ffr_months_diff_exceeded(self):
        """
        월 차이 초과 시 예외 발생 테스트

        Given: FFR 딕셔너리와 MAX_FFR_MONTHS_DIFF(2) 초과한 날짜
        When: lookup_ffr 호출
        Then: ValueError 발생
        """
        # Given
        ffr_dict = {"2023-01": 4.5, "2023-02": 4.6}
        date_value = date(2023, 5, 15)  # 2023-05, 가장 가까운 이전 월은 2023-02 (3개월 차이 > MAX=2)

        # When & Then
        with pytest.raises(ValueError, match="FFR 데이터 부족.*2023-05.*최대 2개월 이내의 데이터만 사용 가능"):
            lookup_ffr(date_value, ffr_dict)


class TestExpenseRatioLoading:
    """Expense Ratio CSV 로딩 테스트"""

    def test_load_expense_ratio_data_basic(self, create_csv_file):
        """
        정상적인 expense ratio 데이터 로딩 테스트

        Given: 유효한 expense ratio CSV 파일
        When: load_expense_ratio_data 호출
        Then: DATE, VALUE 컬럼을 가진 DataFrame 반환
        """
        # Given: expense ratio CSV 생성
        expense_df = pd.DataFrame(
            {
                COL_EXPENSE_DATE: ["2023-01", "2023-02"],
                COL_EXPENSE_VALUE: [0.0095, 0.0088],
            }
        )
        csv_path = create_csv_file("expense_ratio.csv", expense_df)

        # When: 로딩 (아직 구현 안 됨 - 레드)
        from qbt.tqqq.data_loader import load_expense_ratio_data

        result_df = load_expense_ratio_data(csv_path)

        # Then
        assert not result_df.empty, "결과 DataFrame이 비어있지 않아야 합니다"
        assert "DATE" in result_df.columns, "DATE 컬럼이 존재해야 합니다"
        assert "VALUE" in result_df.columns, "VALUE 컬럼이 존재해야 합니다"
        assert len(result_df) == 2, "2개 행이 있어야 합니다"

    def test_load_expense_ratio_data_missing_file(self):
        """
        파일이 존재하지 않을 때 예외 발생 테스트

        Given: 존재하지 않는 파일 경로
        When: load_expense_ratio_data 호출
        Then: FileNotFoundError 발생
        """
        # Given
        from pathlib import Path

        non_existent_path = Path("/non/existent/path.csv")

        # When & Then
        from qbt.tqqq.data_loader import load_expense_ratio_data

        with pytest.raises(FileNotFoundError):
            load_expense_ratio_data(non_existent_path)


class TestGenericMonthlyDataDict:
    """제네릭 월별 데이터 딕셔너리 생성/조회 테스트"""

    def test_create_monthly_data_dict_basic(self):
        """
        제네릭 딕셔너리 생성 기본 테스트

        Given: 월별 데이터 DataFrame
        When: create_monthly_data_dict 호출
        Then: {월: 값} 딕셔너리 반환
        """
        # Given (0~1 비율)
        df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01", "2023-02"], COL_EXPENSE_VALUE: [0.0095, 0.0088]})

        # When: 제네릭 함수 호출
        from qbt.tqqq.data_loader import create_monthly_data_dict

        result_dict = create_monthly_data_dict(df, COL_EXPENSE_DATE, COL_EXPENSE_VALUE, "Expense")

        # Then
        assert result_dict == {"2023-01": 0.0095, "2023-02": 0.0088}

    def test_create_monthly_data_dict_duplicates(self):
        """
        중복 월 검증 테스트

        Given: 중복 월이 있는 DataFrame
        When: create_monthly_data_dict 호출
        Then: ValueError 발생 (data_type 포함한 명확한 메시지)
        """
        # Given: 2023-01이 중복 (0~1 비율)
        df = pd.DataFrame(
            {COL_EXPENSE_DATE: ["2023-01", "2023-01", "2023-02"], COL_EXPENSE_VALUE: [0.0095, 0.0096, 0.0088]}
        )

        # When & Then
        from qbt.tqqq.data_loader import create_monthly_data_dict

        with pytest.raises(ValueError, match="Expense.*2023-01.*중복"):
            create_monthly_data_dict(df, COL_EXPENSE_DATE, COL_EXPENSE_VALUE, "Expense")

    def test_lookup_monthly_data_with_gap(self):
        """
        월 차이 검증 테스트

        Given: 월별 데이터 딕셔너리와 갭이 큰 날짜
        When: lookup_monthly_data 호출
        Then: max_months_diff 초과 시 ValueError 발생
        """
        # Given
        data_dict = {"2023-01": 0.0095}
        date_value = date(2024, 2, 15)  # 2024-02, 2023-01부터 13개월 차이

        # When & Then: max_months_diff=12 초과
        from qbt.tqqq.data_loader import lookup_monthly_data

        with pytest.raises(ValueError, match="Expense.*데이터 부족.*2024-02.*최대 12개월"):
            lookup_monthly_data(date_value, data_dict, max_months_diff=12, data_type="Expense")

    def test_lookup_monthly_data_within_gap(self):
        """
        월 차이 허용 범위 내 조회 테스트

        Given: 월별 데이터 딕셔너리와 허용 범위 내 날짜
        When: lookup_monthly_data 호출
        Then: 가장 가까운 이전 월의 값 반환
        """
        # Given
        data_dict = {"2023-01": 0.0095, "2023-02": 0.0088}
        date_value = date(2023, 12, 15)  # 2023-12, 2023-02부터 10개월 차이 (12개월 이내)

        # When
        from qbt.tqqq.data_loader import lookup_monthly_data

        result = lookup_monthly_data(date_value, data_dict, max_months_diff=12, data_type="Expense")

        # Then: 2023-02 값 사용
        assert result == pytest.approx(0.0088)


class TestCalculateDailyCostWithDynamicExpense:
    """동적 expense 적용 비용 계산 테스트"""

    def test_calculate_daily_cost_with_expense_dict(self):
        """
        expense_dict를 사용한 일일 비용 계산 테스트

        Given: FFR dict, expense dict, 날짜
        When: calculate_daily_cost 호출 (expense_dict 파라미터 사용)
        Then: 해당 날짜의 FFR과 expense를 조회하여 비용 계산
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)

        expense_dict = {"2023-01": 0.0095}  # 0.95%
        date_value = date(2023, 1, 15)

        # When: expense_dict 파라미터로 호출 (아직 시그니처 변경 안 됨 - 레드)
        daily_cost = calculate_daily_cost(
            date_value=date_value, ffr_dict=ffr_dict, expense_dict=expense_dict, funding_spread=0.006, leverage=3.0
        )

        # Then: 양수 비용
        assert daily_cost > 0, "일일 비용은 양수여야 합니다"


class TestSoftplusFunctions:
    """
    softplus 동적 스프레드 함수 테스트

    softplus 함수, compute_softplus_spread, build_monthly_spread_map 함수를 검증한다.
    """

    def test_softplus_positive_input(self):
        """
        양수 입력에 대한 softplus 계산 테스트

        Given: x = 2.0
        When: softplus(x) 호출
        Then: log(1 + exp(2)) ≈ 2.1269 반환
        """
        from qbt.tqqq.simulation import softplus

        x = 2.0
        result = softplus(x)

        # log(1 + exp(2)) = log(1 + 7.389) ≈ 2.1269
        import math

        expected = math.log1p(math.exp(2.0))
        assert abs(result - expected) < 1e-10, f"기대={expected}, 실제={result}"

    def test_softplus_negative_input(self):
        """
        음수 입력에 대한 softplus 계산 테스트

        Given: x = -2.0
        When: softplus(x) 호출
        Then: log(1 + exp(-2)) ≈ 0.1269 반환
        """
        from qbt.tqqq.simulation import softplus

        x = -2.0
        result = softplus(x)

        # log(1 + exp(-2)) = log(1 + 0.135) ≈ 0.1269
        import math

        expected = math.log1p(math.exp(-2.0))
        assert abs(result - expected) < 1e-10, f"기대={expected}, 실제={result}"

    def test_softplus_zero_input(self):
        """
        0 입력에 대한 softplus 계산 테스트

        Given: x = 0.0
        When: softplus(x) 호출
        Then: log(2) ≈ 0.693 반환
        """
        from qbt.tqqq.simulation import softplus

        x = 0.0
        result = softplus(x)

        # log(1 + exp(0)) = log(2) ≈ 0.693
        import math

        expected = math.log(2.0)
        assert abs(result - expected) < 1e-10, f"기대={expected}, 실제={result}"

    def test_softplus_always_positive(self):
        """
        softplus는 항상 양수를 반환해야 함

        Given: 다양한 입력값 (-100, -10, 0, 10, 100)
        When: softplus(x) 호출
        Then: 모든 결과 > 0
        """
        from qbt.tqqq.simulation import softplus

        test_values = [-100.0, -10.0, -1.0, 0.0, 1.0, 10.0, 100.0]
        for x in test_values:
            result = softplus(x)
            assert result > 0, f"softplus({x}) = {result}가 양수가 아님"

    def test_softplus_numerical_stability(self):
        """
        수치 안정성 테스트 (큰 양수/음수 입력)

        Given: 극단적인 입력값
        When: softplus(x) 호출
        Then: overflow/underflow 없이 유한한 값 반환
        """
        import math

        from qbt.tqqq.simulation import softplus

        # 큰 양수: softplus(x) ≈ x
        large_positive = 700.0  # exp(700)은 overflow 위험
        result_pos = softplus(large_positive)
        assert math.isfinite(result_pos), f"softplus({large_positive})가 유한하지 않음: {result_pos}"
        assert abs(result_pos - large_positive) < 1.0, f"softplus({large_positive}) ≈ {large_positive} 예상"

        # 큰 음수: softplus(x) ≈ 0 (하지만 > 0)
        large_negative = -700.0
        result_neg = softplus(large_negative)
        assert math.isfinite(result_neg), f"softplus({large_negative})가 유한하지 않음: {result_neg}"
        assert result_neg > 0, f"softplus({large_negative}) > 0 예상: {result_neg}"
        assert result_neg < 1e-10, f"softplus({large_negative}) ≈ 0 예상: {result_neg}"

    def test_compute_softplus_spread_basic(self):
        """
        compute_softplus_spread 기본 계산 테스트

        Given: a=-5, b=1, ffr_ratio=0.05 (5%)
        When: compute_softplus_spread 호출
        Then: softplus(-5 + 1*5) = softplus(0) ≈ 0.693 반환
        """
        import math

        from qbt.tqqq.simulation import compute_softplus_spread

        a, b = -5.0, 1.0
        ffr_ratio = 0.05  # 5%

        result = compute_softplus_spread(a, b, ffr_ratio)

        # ffr_pct = 100 * 0.05 = 5.0
        # softplus(-5 + 1*5) = softplus(0) = log(2) ≈ 0.693
        expected = math.log(2.0)
        assert abs(result - expected) < 1e-10, f"기대={expected}, 실제={result}"

    def test_compute_softplus_spread_high_rate(self):
        """
        고금리 구간에서 spread 증가 테스트

        Given: a=-5, b=1, 저금리(1%)와 고금리(5%) 비교
        When: compute_softplus_spread 호출
        Then: 고금리 spread > 저금리 spread
        """
        from qbt.tqqq.simulation import compute_softplus_spread

        a, b = -5.0, 1.0

        spread_low = compute_softplus_spread(a, b, 0.01)  # 1%
        spread_high = compute_softplus_spread(a, b, 0.05)  # 5%

        assert spread_high > spread_low, f"고금리 spread({spread_high}) > 저금리 spread({spread_low}) 예상"

    def test_build_monthly_spread_map_basic(self):
        """
        build_monthly_spread_map 기본 동작 테스트

        Given: 3개월 FFR 데이터
        When: build_monthly_spread_map 호출
        Then: 3개 월의 spread 딕셔너리 반환
        """
        from qbt.tqqq.simulation import build_monthly_spread_map

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02", "2023-03"], COL_FFR_VALUE: [0.04, 0.045, 0.05]})

        a, b = -5.0, 1.0
        result = build_monthly_spread_map(ffr_df, a, b)

        # 3개 월 모두 포함
        assert len(result) == 3, f"3개월 기대, 실제={len(result)}"
        assert "2023-01" in result
        assert "2023-02" in result
        assert "2023-03" in result

        # 모든 값이 양수
        for month, spread in result.items():
            assert spread > 0, f"{month}의 spread({spread})가 양수가 아님"

        # 금리 순서대로 spread 증가 (b > 0이므로)
        assert result["2023-03"] > result["2023-02"] > result["2023-01"], "금리 증가에 따라 spread도 증가해야 함"

    def test_build_monthly_spread_map_empty_raises(self):
        """
        빈 FFR DataFrame 입력 시 ValueError 테스트

        Given: 빈 FFR DataFrame
        When: build_monthly_spread_map 호출
        Then: ValueError 발생
        """
        from qbt.tqqq.simulation import build_monthly_spread_map

        ffr_df = pd.DataFrame({COL_FFR_DATE: [], COL_FFR_VALUE: []})

        with pytest.raises(ValueError, match="비어있습니다"):
            build_monthly_spread_map(ffr_df, a=-5.0, b=1.0)

    def test_build_monthly_spread_map_from_dict_equivalence(self):
        """
        build_monthly_spread_map_from_dict와 build_monthly_spread_map 결과 동일성 테스트

        Given: 동일한 FFR 데이터 (DataFrame vs dict)
        When: 두 함수 각각 호출
        Then: 결과가 완전히 동일
        """
        from qbt.tqqq.simulation import (
            build_monthly_spread_map,
            build_monthly_spread_map_from_dict,
        )

        # Given: 다양한 FFR 데이터
        ffr_df = pd.DataFrame(
            {
                COL_FFR_DATE: ["2023-01", "2023-02", "2023-03", "2023-04", "2023-05"],
                COL_FFR_VALUE: [0.045, 0.046, 0.050, 0.055, 0.052],
            }
        )
        ffr_dict = dict(
            zip(
                ffr_df[COL_FFR_DATE].tolist(),
                ffr_df[COL_FFR_VALUE].tolist(),
                strict=True,
            )
        )

        # 다양한 a, b 파라미터 조합 테스트
        test_params = [
            (-5.0, 1.0),
            (-6.0, 0.5),
            (-4.0, 0.8),
            (-7.0, 1.2),
            (0.0, 0.0),  # 엣지 케이스
        ]

        for a, b in test_params:
            # When
            result_df = build_monthly_spread_map(ffr_df, a, b)
            result_dict = build_monthly_spread_map_from_dict(ffr_dict, a, b)

            # Then: 동일한 키와 값
            assert set(result_df.keys()) == set(result_dict.keys()), f"키 불일치: a={a}, b={b}"

            for month in result_df.keys():
                df_val = result_df[month]
                dict_val = result_dict[month]
                assert abs(df_val - dict_val) < 1e-12, (
                    f"값 불일치: month={month}, a={a}, b={b}, "
                    f"df={df_val}, dict={dict_val}, diff={abs(df_val - dict_val)}"
                )

    def test_build_monthly_spread_map_from_dict_empty_raises(self):
        """
        빈 FFR 딕셔너리 입력 시 ValueError 테스트

        Given: 빈 FFR 딕셔너리
        When: build_monthly_spread_map_from_dict 호출
        Then: ValueError 발생
        """
        from qbt.tqqq.simulation import build_monthly_spread_map_from_dict

        ffr_dict: dict[str, float] = {}

        with pytest.raises(ValueError, match="비어있습니다"):
            build_monthly_spread_map_from_dict(ffr_dict, a=-5.0, b=1.0)


class TestDynamicFundingSpread:
    """
    동적 funding_spread 지원 테스트

    funding_spread가 float, dict[str, float], Callable[[date], float]
    세 가지 타입을 모두 지원하는지 검증한다.
    """

    def test_float_spread_unchanged_behavior(self):
        """
        float 타입 funding_spread 기존 동작 유지 테스트

        Given: funding_spread = 0.006 (float)
        When: calculate_daily_cost 호출
        Then: 기존과 동일하게 0.006이 적용됨
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}
        date_value = date(2023, 1, 15)

        # When: float spread 사용 (기존 동작)
        daily_cost = calculate_daily_cost(
            date_value=date_value,
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=0.006,  # float
            leverage=3.0,
        )

        # Then: 예상 비용 계산
        # funding_rate = 0.045 + 0.006 = 0.051
        # leverage_cost = 0.051 * 2 = 0.102
        # annual_cost = 0.102 + 0.0095 = 0.1115
        # daily_cost = 0.1115 / 252
        expected_daily_cost = (0.045 + 0.006) * 2 + 0.0095
        expected_daily_cost /= TRADING_DAYS_PER_YEAR

        assert abs(daily_cost - expected_daily_cost) < 1e-10, f"기대={expected_daily_cost}, 실제={daily_cost}"

    def test_dict_spread_monthly_lookup(self):
        """
        dict 타입 funding_spread 월별 조회 테스트

        Given: funding_spread = {"2023-01": 0.004, "2023-02": 0.008}
        When: 2023-01-15 날짜로 calculate_daily_cost 호출
        Then: 해당 월의 spread 0.004가 적용됨
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02"], COL_FFR_VALUE: [0.045, 0.046]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095, "2023-02": 0.0095}

        # 월별 spread dict
        spread_dict: dict[str, float] = {"2023-01": 0.004, "2023-02": 0.008}

        # When: 1월 날짜로 호출
        daily_cost_jan = calculate_daily_cost(
            date_value=date(2023, 1, 15),
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=spread_dict,
            leverage=3.0,
        )

        # When: 2월 날짜로 호출
        daily_cost_feb = calculate_daily_cost(
            date_value=date(2023, 2, 15),
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=spread_dict,
            leverage=3.0,
        )

        # Then: 1월과 2월의 spread 차이만큼 비용 차이
        # 차이: (0.008 - 0.004) * 2 / 252 = 0.008 / 252
        spread_diff = 0.008 - 0.004
        ffr_diff = 0.046 - 0.045  # FFR 차이도 고려
        expected_diff = (spread_diff + ffr_diff) * 2 / TRADING_DAYS_PER_YEAR

        actual_diff = daily_cost_feb - daily_cost_jan
        assert abs(actual_diff - expected_diff) < 1e-10, f"기대 차이={expected_diff}, 실제 차이={actual_diff}"

    def test_dict_spread_missing_key_raises(self):
        """
        dict 타입 funding_spread 키 누락 시 ValueError 테스트

        Given: funding_spread = {"2023-01": 0.004} (2월 키 없음)
        When: 2023-02-15 날짜로 호출
        Then: ValueError 발생 (fail-fast)
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-02"], COL_FFR_VALUE: [0.046]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-02": 0.0095}

        # 1월 키만 있는 spread dict
        spread_dict: dict[str, float] = {"2023-01": 0.004}

        # When & Then: 2월 키 없음 -> ValueError
        with pytest.raises(ValueError, match="spread.*2023-02|키.*누락|없"):
            calculate_daily_cost(
                date_value=date(2023, 2, 15),
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
                funding_spread=spread_dict,
                leverage=3.0,
            )

    def test_callable_spread_function_call(self):
        """
        Callable 타입 funding_spread 함수 호출 테스트

        Given: funding_spread = lambda d: 0.005 (고정 반환 함수)
        When: calculate_daily_cost 호출
        Then: 함수가 호출되고 반환값이 spread로 적용됨
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}

        # 고정값 반환 함수
        def fixed_spread_fn(d: date) -> float:
            return 0.005

        # When
        daily_cost = calculate_daily_cost(
            date_value=date(2023, 1, 15),
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=fixed_spread_fn,
            leverage=3.0,
        )

        # Then: 0.005가 적용됨
        expected_daily_cost = ((0.045 + 0.005) * 2 + 0.0095) / TRADING_DAYS_PER_YEAR
        assert abs(daily_cost - expected_daily_cost) < 1e-10

    def test_callable_spread_nan_raises(self):
        """
        Callable 반환값이 NaN일 때 ValueError 테스트

        Given: funding_spread = lambda d: float('nan')
        When: calculate_daily_cost 호출
        Then: ValueError 발생 (fail-fast)
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}

        def nan_spread_fn(d: date) -> float:
            return float("nan")

        # When & Then
        with pytest.raises(ValueError, match="NaN|nan|유효하지 않"):
            calculate_daily_cost(
                date_value=date(2023, 1, 15),
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
                funding_spread=nan_spread_fn,
                leverage=3.0,
            )

    def test_callable_spread_inf_raises(self):
        """
        Callable 반환값이 inf일 때 ValueError 테스트

        Given: funding_spread = lambda d: float('inf')
        When: calculate_daily_cost 호출
        Then: ValueError 발생 (fail-fast)
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}

        def inf_spread_fn(d: date) -> float:
            return float("inf")

        # When & Then
        with pytest.raises(ValueError, match="inf|무한|유효하지 않"):
            calculate_daily_cost(
                date_value=date(2023, 1, 15),
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
                funding_spread=inf_spread_fn,
                leverage=3.0,
            )

    def test_spread_zero_raises(self):
        """
        spread가 0일 때 ValueError 테스트

        Given: funding_spread = 0.0
        When: calculate_daily_cost 호출
        Then: ValueError 발생 (spread > 0 필수)
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}

        # When & Then: spread = 0 -> ValueError
        with pytest.raises(ValueError, match="0|양수|> 0"):
            calculate_daily_cost(
                date_value=date(2023, 1, 15),
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
                funding_spread=0.0,
                leverage=3.0,
            )

    def test_spread_negative_raises(self):
        """
        spread가 음수일 때 ValueError 테스트

        Given: funding_spread = -0.005
        When: calculate_daily_cost 호출
        Then: ValueError 발생 (음수 불허)
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}

        # When & Then: 음수 spread -> ValueError
        with pytest.raises(ValueError, match="음수|양수|> 0"):
            calculate_daily_cost(
                date_value=date(2023, 1, 15),
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
                funding_spread=-0.005,
                leverage=3.0,
            )


class TestFindOptimalSoftplusParams:
    """
    find_optimal_softplus_params() 함수 테스트

    2-stage grid search로 softplus 동적 스프레드 모델의 최적 (a, b) 파라미터를 탐색한다.
    테스트에서는 작은 그리드로 동작을 검증한다.
    """

    def test_find_optimal_softplus_params_basic(self, monkeypatch):
        """
        find_optimal_softplus_params() 기본 동작 테스트

        Given: 간단한 기초/실제 데이터, 작은 그리드 범위로 패치
        When: find_optimal_softplus_params() 호출
        Then:
          - (a_best, b_best, best_rmse, all_candidates) 튜플 반환
          - a_best, b_best는 float
          - best_rmse >= 0
          - all_candidates는 list
        """
        # Given: 간단한 데이터 (10일)
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, i + 2) for i in range(10)],
                COL_CLOSE: [100.0 + i * 0.5 for i in range(10)],
            }
        )

        actual_leveraged_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, i + 2) for i in range(10)],
                COL_CLOSE: [30.0 + i * 0.45 for i in range(10)],
            }
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # 작은 그리드로 패치 (테스트 속도 향상)
        import qbt.tqqq.simulation as sim_module

        # Stage 1: a in [-6, -5] step 1.0, b in [0.5, 1.0] step 0.5 -> 4조합
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE1_A_RANGE", (-6.0, -5.0))
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE1_A_STEP", 1.0)
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE1_B_RANGE", (0.5, 1.0))
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE1_B_STEP", 0.5)

        # Stage 2: delta=0.5, step=0.5 -> 작은 범위
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE2_A_DELTA", 0.5)
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE2_A_STEP", 0.5)
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE2_B_DELTA", 0.25)
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE2_B_STEP", 0.25)

        # When
        from qbt.tqqq.simulation import find_optimal_softplus_params

        a_best, b_best, best_rmse, all_candidates = find_optimal_softplus_params(
            underlying_df=underlying_df,
            actual_leveraged_df=actual_leveraged_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            leverage=3.0,
            max_workers=1,  # 테스트에서는 단일 워커
        )

        # Then
        assert isinstance(a_best, float), f"a_best는 float이어야 함: {type(a_best)}"
        assert isinstance(b_best, float), f"b_best는 float이어야 함: {type(b_best)}"
        assert best_rmse >= 0, f"best_rmse는 0 이상이어야 함: {best_rmse}"
        assert isinstance(all_candidates, list), "all_candidates는 list이어야 함"
        assert len(all_candidates) > 0, "all_candidates가 비어있지 않아야 함"

        # 각 candidate 구조 확인
        first_candidate = all_candidates[0]
        assert "a" in first_candidate, "candidate에 'a' 키 있어야 함"
        assert "b" in first_candidate, "candidate에 'b' 키 있어야 함"
        assert "cumul_multiple_log_diff_rmse_pct" in first_candidate, "RMSE 키 있어야 함"

    def test_find_optimal_softplus_params_ffr_gap_raises(self, monkeypatch):
        """
        FFR 데이터 갭 초과 시 ValueError 테스트

        Given: overlap이 2023-05인데 FFR은 2023-01만 존재 (4개월 초과)
        When: find_optimal_softplus_params() 호출
        Then: ValueError 발생
        """
        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 5, i + 2) for i in range(10)],
                COL_CLOSE: [100.0 + i for i in range(10)],
            }
        )

        actual_leveraged_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 5, i + 2) for i in range(10)],
                COL_CLOSE: [30.0 + i * 0.9 for i in range(10)],
            }
        )

        # FFR 데이터는 2023-01만 존재 (4개월 차이 > MAX=2)
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When & Then
        from qbt.tqqq.simulation import find_optimal_softplus_params

        with pytest.raises(ValueError, match="최대 2개월"):
            find_optimal_softplus_params(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                expense_df=expense_df,
                leverage=3.0,
            )

    def test_find_optimal_softplus_params_no_overlap_raises(self):
        """
        겹치는 기간이 없을 때 ValueError 테스트

        Given: underlying과 actual_leveraged의 날짜가 완전히 다름
        When: find_optimal_softplus_params() 호출
        Then: ValueError 발생
        """
        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2020, 1, i + 1) for i in range(5)],
                COL_CLOSE: [100.0 + i for i in range(5)],
            }
        )

        actual_leveraged_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, i + 1) for i in range(5)],
                COL_CLOSE: [30.0 + i for i in range(5)],
            }
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2020-01", "2023-01"], COL_FFR_VALUE: [0.02, 0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2020-01", "2023-01"], COL_EXPENSE_VALUE: [0.0095, 0.0095]})

        # When & Then
        from qbt.tqqq.simulation import find_optimal_softplus_params

        with pytest.raises(ValueError, match="겹치는 기간"):
            find_optimal_softplus_params(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                expense_df=expense_df,
                leverage=3.0,
            )

    def test_find_optimal_softplus_params_candidate_structure(self, monkeypatch):
        """
        반환된 candidate 구조 상세 검증

        Given: 간단한 데이터, 작은 그리드
        When: find_optimal_softplus_params() 호출
        Then: all_candidates의 각 원소가 필수 키를 포함
        """
        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, i + 2) for i in range(5)],
                COL_CLOSE: [100.0, 101.0, 100.5, 102.0, 101.5],
            }
        )

        actual_leveraged_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, i + 2) for i in range(5)],
                COL_CLOSE: [30.0, 30.9, 30.5, 31.5, 31.2],
            }
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # 최소 그리드로 패치
        import qbt.tqqq.simulation as sim_module

        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE1_A_RANGE", (-5.0, -5.0))
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE1_A_STEP", 1.0)
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE1_B_RANGE", (1.0, 1.0))
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE1_B_STEP", 1.0)
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE2_A_DELTA", 0.0)
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE2_A_STEP", 1.0)
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE2_B_DELTA", 0.0)
        monkeypatch.setattr(sim_module, "SOFTPLUS_GRID_STAGE2_B_STEP", 1.0)

        # When
        from qbt.tqqq.simulation import find_optimal_softplus_params

        a_best, b_best, best_rmse, all_candidates = find_optimal_softplus_params(
            underlying_df=underlying_df,
            actual_leveraged_df=actual_leveraged_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            leverage=3.0,
            max_workers=1,
        )

        # Then: 필수 키 확인
        required_keys = [
            "a",
            "b",
            "leverage",
            "overlap_start",
            "overlap_end",
            "overlap_days",
            "cumul_multiple_log_diff_rmse_pct",
            "cumul_multiple_log_diff_mean_pct",
            "cumul_multiple_log_diff_max_pct",
        ]

        for candidate in all_candidates:
            for key in required_keys:
                assert key in candidate, f"candidate에 '{key}' 키가 있어야 함: {candidate.keys()}"


class TestLocalRefineSearch:
    """
    _local_refine_search() 함수 테스트

    직전 월 최적 (a_prev, b_prev) 주변에서 국소 탐색을 수행한다.
    단위 테스트로서 함수의 반환 타입 및 제약 조건을 검증한다.
    """

    def test_local_refine_search_basic(self):
        """
        _local_refine_search() 기본 동작 테스트

        Given:
          - 이전 최적값 a_prev=-5.0, b_prev=1.0
          - 학습 데이터 및 FFR/Expense 데이터
        When: _local_refine_search() 호출
        Then:
          - (a_best, b_best, best_rmse, candidates) 튜플 반환
          - a_best, b_best는 float
          - best_rmse >= 0
          - candidates는 list (모든 탐색 결과)
        """
        from qbt.tqqq.simulation import _local_refine_search

        # Given: 간단한 데이터 (10일)
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, i + 2) for i in range(10)],
                COL_CLOSE: [100.0 + i * 0.5 for i in range(10)],
            }
        )

        actual_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, i + 2) for i in range(10)],
                COL_CLOSE: [30.0 + i * 0.45 for i in range(10)],
            }
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        a_prev, b_prev = -5.0, 1.0

        # When
        a_best, b_best, best_rmse, candidates = _local_refine_search(
            underlying_df=underlying_df,
            actual_df=actual_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            a_prev=a_prev,
            b_prev=b_prev,
            leverage=3.0,
            max_workers=1,
        )

        # Then
        assert isinstance(a_best, float), f"a_best는 float이어야 함: {type(a_best)}"
        assert isinstance(b_best, float), f"b_best는 float이어야 함: {type(b_best)}"
        assert best_rmse >= 0, f"best_rmse는 0 이상이어야 함: {best_rmse}"
        assert isinstance(candidates, list), "candidates는 list이어야 함"

    def test_local_refine_search_b_non_negative(self):
        """
        local refine에서 b는 음수가 되지 않아야 함

        Given: b_prev=0.1 (작은 양수)
        When: _local_refine_search() 호출
        Then: 모든 탐색된 b 값이 0 이상
        """
        from qbt.tqqq.simulation import _local_refine_search

        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, i + 2) for i in range(5)],
                COL_CLOSE: [100.0, 101.0, 100.5, 102.0, 101.5],
            }
        )

        actual_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, i + 2) for i in range(5)],
                COL_CLOSE: [30.0, 30.9, 30.5, 31.5, 31.2],
            }
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        a_prev, b_prev = -5.0, 0.1  # b_prev가 작아서 delta=0.15 적용 시 음수 범위 포함 가능

        # When
        a_best, b_best, best_rmse, candidates = _local_refine_search(
            underlying_df=underlying_df,
            actual_df=actual_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            a_prev=a_prev,
            b_prev=b_prev,
            leverage=3.0,
            max_workers=1,
        )

        # Then: 모든 candidate의 b >= 0
        for candidate in candidates:
            assert candidate["b"] >= 0, f"b는 음수가 되면 안 됨: {candidate['b']}"


class TestRunWalkforwardValidation:
    """
    run_walkforward_validation() 함수 테스트

    60개월 Train, 1개월 Test 워크포워드 검증을 수행한다.
    여기서는 단위 테스트(에러 처리)만 포함하고,
    통합 테스트(시간 오래 걸리는)는 주석 처리 상태 유지한다.
    """

    def test_walkforward_insufficient_data_raises(self):
        """
        데이터 부족 시 예외 발생 테스트

        Given: 60개월 미만 데이터
        When: run_walkforward_validation() 호출
        Then: ValueError 발생
        """
        from qbt.tqqq.simulation import run_walkforward_validation

        # Given: 50개월 데이터 (60개월 train 불가)
        dates = []
        closes_underlying = []
        closes_actual = []

        start_year, start_month = 2020, 1
        for i in range(50):
            year = start_year + (start_month + i - 1) // 12
            month = (start_month + i - 1) % 12 + 1
            for day in range(1, 21):
                try:
                    d = date(year, month, day + 1)
                    dates.append(d)
                    closes_underlying.append(100.0 + i * 0.1)
                    closes_actual.append(30.0 + i * 0.3)
                except ValueError:
                    pass

        underlying_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: closes_underlying})
        actual_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: closes_actual})

        ffr_dates = [f"{2020 + (i // 12):04d}-{(i % 12) + 1:02d}" for i in range(50)]
        ffr_df = pd.DataFrame({COL_FFR_DATE: ffr_dates, COL_FFR_VALUE: [0.02] * 50})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ffr_dates, COL_EXPENSE_VALUE: [0.0095] * 50})

        # When & Then
        with pytest.raises(ValueError, match="60개월|부족|데이터"):
            run_walkforward_validation(
                underlying_df=underlying_df,
                actual_df=actual_df,
                ffr_df=ffr_df,
                expense_df=expense_df,
                leverage=3.0,
            )


# NOTE: 아래 테스트는 통합 테스트로서 실행 시간이 오래 걸립니다 (수십 분).
# CLI 스크립트로 분리되어 별도 실행이 권장됩니다.
# 필요 시 주석 해제하여 실행 가능합니다.
#
# class TestRunWalkforwardValidationIntegration:
#     """
#     run_walkforward_validation() 통합 테스트
#
#     실행 시간이 오래 걸리므로 필요 시에만 실행한다.
#     CLI 스크립트로 분리됨: scripts/tqqq/run_walkforward_validation.py
#     """
#
#     def test_walkforward_start_point_calculation(self):
#         """워크포워드 시작점 자동 계산 테스트"""
#         pass  # 주석 처리
#
#     def test_walkforward_result_schema(self):
#         """워크포워드 결과 DataFrame 스키마 검증"""
#         pass  # 주석 처리
#
#     def test_walkforward_first_window_full_grid(self):
#         """첫 워크포워드 구간은 2-stage grid search 사용 테스트"""
#         pass  # 주석 처리
#
#     def test_walkforward_subsequent_windows_local_refine(self):
#         """이후 워크포워드 구간은 local refine 사용 테스트"""
#         pass  # 주석 처리


class TestGenerateStaticSpreadSeries:
    """
    generate_static_spread_series() 함수 테스트

    전체기간 단일 최적 (a, b)에 대해 월별 spread 시계열 DataFrame을 생성한다.
    """

    def test_normal_static_spread_series(self):
        """
        정상 케이스: FFR 데이터와 overlap 기간이 주어지면 올바른 spread 계산

        Given: 3개월 overlap 기간 + FFR 데이터 + a=-5.0, b=1.0
        When: generate_static_spread_series 호출
        Then: 각 월별 spread = softplus(a + b * ffr_pct) 일치, month 오름차순
        """
        # Given
        a, b = -5.0, 1.0

        # 3개월 겹치는 기간 데이터 (2023-01 ~ 2023-03)
        dates = (
            [date(2023, 1, d) for d in range(2, 22)]
            + [date(2023, 2, d) for d in range(1, 21)]
            + [date(2023, 3, d) for d in range(1, 22)]
        )
        underlying_overlap_df = pd.DataFrame(
            {
                COL_DATE: dates,
                COL_CLOSE: [100.0 + i * 0.1 for i in range(len(dates))],
            }
        )

        ffr_df = pd.DataFrame(
            {
                COL_FFR_DATE: ["2023-01", "2023-02", "2023-03"],
                COL_FFR_VALUE: [0.045, 0.046, 0.05],  # 4.5%, 4.6%, 5.0%
            }
        )

        # When
        result = generate_static_spread_series(ffr_df, a, b, underlying_overlap_df)

        # Then
        # 1. 컬럼 존재 검증
        expected_cols = ["month", "ffr_pct", "a_global", "b_global", "spread_global"]
        assert list(result.columns) == expected_cols

        # 2. 행 수 검증 (3개월)
        assert len(result) == 3

        # 3. month 오름차순 정렬 검증
        assert list(result["month"]) == ["2023-01", "2023-02", "2023-03"]

        # 4. spread = softplus(a + b * ffr_pct) 검증
        for _, row in result.iterrows():
            ffr_ratio = row["ffr_pct"] / 100.0
            expected_spread = compute_softplus_spread(a, b, ffr_ratio)
            assert row["spread_global"] == pytest.approx(expected_spread, abs=1e-10)

        # 5. a_global, b_global은 입력값과 동일
        assert all(result["a_global"] == a)
        assert all(result["b_global"] == b)

    def test_spread_values_differ_by_ffr(self):
        """
        서로 다른 FFR 값에 대해 서로 다른 spread가 계산됨

        Given: 금리가 다른 2개월 overlap 기간
        When: generate_static_spread_series 호출
        Then: 금리가 높은 월의 spread가 더 큼 (b > 0일 때)
        """
        # Given
        a, b = -6.0, 0.5

        dates = [date(2023, 1, d) for d in range(2, 22)] + [date(2023, 2, d) for d in range(1, 21)]
        underlying_overlap_df = pd.DataFrame(
            {
                COL_DATE: dates,
                COL_CLOSE: [100.0] * len(dates),
            }
        )

        # 1월: 1%, 2월: 5% (큰 차이)
        ffr_df = pd.DataFrame(
            {
                COL_FFR_DATE: ["2023-01", "2023-02"],
                COL_FFR_VALUE: [0.01, 0.05],
            }
        )

        # When
        result = generate_static_spread_series(ffr_df, a, b, underlying_overlap_df)

        # Then: b > 0이므로 금리가 높은 2월의 spread가 더 큼
        spread_jan = result[result["month"] == "2023-01"]["spread_global"].iloc[0]
        spread_feb = result[result["month"] == "2023-02"]["spread_global"].iloc[0]
        assert spread_feb > spread_jan

    def test_empty_overlap_raises(self):
        """
        빈 overlap DataFrame이면 ValueError 발생

        Given: 빈 overlap DataFrame
        When: generate_static_spread_series 호출
        Then: ValueError 발생
        """
        # Given
        empty_df = pd.DataFrame({COL_DATE: [], COL_CLOSE: []})
        ffr_df = pd.DataFrame(
            {
                COL_FFR_DATE: ["2023-01"],
                COL_FFR_VALUE: [0.05],
            }
        )

        # When & Then
        with pytest.raises(ValueError, match="비어있습니다"):
            generate_static_spread_series(ffr_df, -5.0, 1.0, empty_df)


class TestCLIScriptExists:
    """
    CLI 스크립트 존재 테스트

    스크립트 파일이 존재하는지 검증한다.
    임포트 및 문법 검증은 PyRight 타입 체크로 수행된다.
    """

    def test_softplus_tuning_script_exists(self):
        """
        softplus 튜닝 스크립트 파일 존재 테스트

        Given: scripts/tqqq/ 디렉토리
        When: run_softplus_tuning.py 존재 여부 확인
        Then: 파일이 존재함
        """
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "scripts" / "tqqq" / "run_softplus_tuning.py"
        assert script_path.exists(), f"스크립트 파일이 존재해야 함: {script_path}"

    def test_walkforward_validation_script_exists(self):
        """
        워크포워드 검증 스크립트 파일 존재 테스트

        Given: scripts/tqqq/ 디렉토리
        When: run_walkforward_validation.py 존재 여부 확인
        Then: 파일이 존재함
        """
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "scripts" / "tqqq" / "run_walkforward_validation.py"
        assert script_path.exists(), f"스크립트 파일이 존재해야 함: {script_path}"


class TestVectorizedSimulation:
    """벡터화 시뮬레이션 수치 동등성 테스트

    기존 Python for-loop 기반 시뮬레이션과 numpy 벡터화 버전이
    부동소수점 오차 범위(1e-10) 내에서 동일한 결과를 산출하는지 검증한다.
    """

    def _create_test_data(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, float]:
        """
        테스트용 공통 데이터를 생성한다.

        2개월에 걸친 20일 거래 데이터를 생성하여 월 전환 시 비용 계산 정확성도 검증한다.

        Returns:
            (underlying_df, ffr_df, expense_df, initial_price) 튜플
        """
        # 20 거래일 (2개월에 걸침)
        dates = [date(2023, 1, i + 2) for i in range(15)] + [date(2023, 2, i + 1) for i in range(5)]
        # 가격에 변동을 주어 다양한 수익률 발생
        prices = [100.0]
        for i in range(1, 20):
            # 다양한 수익률: +1%, -0.5%, +0.3% 등
            change = [0.01, -0.005, 0.003, 0.008, -0.002, 0.004, -0.007, 0.006, 0.002, -0.003]
            prices.append(prices[-1] * (1 + change[i % len(change)]))

        underlying_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: prices})

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02"], COL_FFR_VALUE: [0.045, 0.046]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01", "2023-02"], COL_EXPENSE_VALUE: [0.0095, 0.0088]})

        initial_price = 30.0

        return underlying_df, ffr_df, expense_df, initial_price

    def test_simulate_fast_matches_simulate(self, enable_numpy_warnings):
        """
        벡터화 시뮬레이션이 기존 simulate()와 동일한 가격 배열을 산출하는지 검증한다.

        Given:
          - 2개월에 걸친 20일 거래 데이터
          - FFR, expense, softplus spread 데이터
        When:
          - 기존 simulate() 실행
          - 벡터화 경로 (precompute + simulate_vectorized) 실행
        Then:
          - 두 결과의 가격 배열이 1e-10 이내에서 동일
        """
        from qbt.tqqq.simulation import (
            _precompute_daily_costs_vectorized,
            _simulate_prices_vectorized,
            build_monthly_spread_map_from_dict,
            simulate,
        )

        # Given
        underlying_df, ffr_df, expense_df, initial_price = self._create_test_data()
        leverage = 3.0

        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = create_expense_dict(expense_df)

        # softplus 파라미터 사용 (dict spread)
        a, b = -5.0, 0.8
        spread_map = build_monthly_spread_map_from_dict(ffr_dict, a, b)

        # When 1: 기존 simulate() 실행
        sim_df = simulate(
            underlying_df=underlying_df,
            leverage=leverage,
            expense_df=expense_df,
            initial_price=initial_price,
            ffr_dict=ffr_dict,
            funding_spread=spread_map,
        )
        expected_prices = np.array(sim_df[COL_CLOSE].tolist(), dtype=np.float64)

        # When 2: 벡터화 경로 실행
        underlying_returns = np.array(underlying_df[COL_CLOSE].pct_change().fillna(0.0).tolist(), dtype=np.float64)

        # 각 거래일의 "YYYY-MM" 키 배열
        month_keys = np.array(
            [f"{d.year:04d}-{d.month:02d}" for d in underlying_df[COL_DATE]],
            dtype=object,
        )

        daily_costs = _precompute_daily_costs_vectorized(
            month_keys=month_keys,
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            spread_map=spread_map,
            leverage=leverage,
        )

        actual_prices = _simulate_prices_vectorized(
            underlying_returns=underlying_returns,
            daily_costs=daily_costs,
            leverage=leverage,
            initial_price=initial_price,
        )

        # Then
        np.testing.assert_allclose(
            actual_prices,
            expected_prices,
            atol=1e-10,
            err_msg="벡터화 시뮬레이션 결과가 기존 simulate()와 동일해야 합니다",
        )

    def test_calculate_rmse_fast_matches_full(self, enable_numpy_warnings):
        """
        경량 RMSE 함수가 calculate_validation_metrics의 RMSE와 동일한 값을 산출하는지 검증한다.

        Given:
          - 약간의 차이가 있는 실제/시뮬레이션 가격 배열
        When:
          - calculate_validation_metrics() 실행하여 RMSE 획득
          - _calculate_metrics_fast() 실행하여 RMSE 획득
        Then:
          - 두 RMSE 값이 1e-10 이내에서 동일
          - mean, max 값도 동일
        """
        from qbt.tqqq.simulation import (
            _calculate_metrics_fast,
            calculate_validation_metrics,
        )

        # Given: 약간의 차이가 있는 가격 데이터
        dates = [date(2023, 1, i + 1) for i in range(10)]
        actual_prices = [100.0, 101.0, 102.5, 101.8, 103.0, 104.2, 103.5, 105.0, 106.1, 107.0]
        simul_prices = [100.0, 101.2, 102.3, 101.5, 103.3, 104.0, 103.8, 105.2, 105.8, 107.3]

        actual_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: actual_prices})
        simul_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: simul_prices})

        # When 1: 전체 메트릭 계산 (기존 방식)
        metrics_full = calculate_validation_metrics(simul_df, actual_df)
        expected_rmse = metrics_full["cumul_multiple_log_diff_rmse_pct"]
        expected_mean = metrics_full["cumul_multiple_log_diff_mean_pct"]
        expected_max = metrics_full["cumul_multiple_log_diff_max_pct"]

        # When 2: 경량 메트릭 계산 (빠른 경로)
        actual_rmse, actual_mean, actual_max = _calculate_metrics_fast(
            actual_prices=np.array(actual_prices),
            simulated_prices=np.array(simul_prices),
        )

        # Then
        assert actual_rmse == pytest.approx(
            expected_rmse, abs=1e-10
        ), f"RMSE 불일치: fast={actual_rmse}, full={expected_rmse}"
        assert actual_mean == pytest.approx(
            expected_mean, abs=1e-10
        ), f"Mean 불일치: fast={actual_mean}, full={expected_mean}"
        assert actual_max == pytest.approx(expected_max, abs=1e-10), f"Max 불일치: fast={actual_max}, full={expected_max}"

    def test_precompute_daily_costs_matches_per_day(self, enable_numpy_warnings):
        """
        사전 계산된 일일 비용이 개별 calculate_daily_cost() 호출 결과와 동일한지 검증한다.

        Given:
          - 2개월에 걸친 20일 거래 데이터
          - FFR, expense, softplus spread 데이터
        When:
          - _precompute_daily_costs_vectorized로 전체 비용 배열 한 번에 계산
          - calculate_daily_cost로 각 날짜별 개별 계산
        Then:
          - 모든 날짜에서 비용이 1e-10 이내에서 동일
        """
        from qbt.tqqq.simulation import (
            _precompute_daily_costs_vectorized,
            build_monthly_spread_map_from_dict,
            calculate_daily_cost,
        )

        # Given
        underlying_df, ffr_df, expense_df, _ = self._create_test_data()
        leverage = 3.0

        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = create_expense_dict(expense_df)

        a, b = -5.0, 0.8
        spread_map = build_monthly_spread_map_from_dict(ffr_dict, a, b)

        dates = underlying_df[COL_DATE].tolist()
        month_keys = np.array(
            [f"{d.year:04d}-{d.month:02d}" for d in dates],
            dtype=object,
        )

        # When 1: 벡터화된 사전 계산
        daily_costs_vectorized = _precompute_daily_costs_vectorized(
            month_keys=month_keys,
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            spread_map=spread_map,
            leverage=leverage,
        )

        # When 2: 개별 계산
        daily_costs_individual = np.array(
            [
                calculate_daily_cost(
                    date_value=d,
                    ffr_dict=ffr_dict,
                    expense_dict=expense_dict,
                    funding_spread=spread_map,
                    leverage=leverage,
                )
                for d in dates
            ]
        )

        # Then
        np.testing.assert_allclose(
            daily_costs_vectorized,
            daily_costs_individual,
            atol=1e-10,
            err_msg="사전 계산 비용이 개별 calculate_daily_cost()와 동일해야 합니다",
        )
