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

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, TRADING_DAYS_PER_YEAR
from qbt.tqqq.constants import COL_EXPENSE_DATE, COL_EXPENSE_VALUE, COL_FFR_DATE, COL_FFR_VALUE
from qbt.tqqq.data_loader import create_expense_dict, create_ffr_dict, lookup_ffr
from qbt.tqqq.optimization import (
    _precompute_daily_costs_vectorized,
    evaluate_softplus_candidate,
)
from qbt.tqqq.simulation import (
    _calculate_daily_cost,
    calculate_validation_metrics,
    compute_softplus_spread,
    generate_static_spread_series,
    simulate,
    validate_ffr_coverage,
)
from qbt.tqqq.walkforward import (
    calculate_fixed_ab_stitched_rmse,
    calculate_rate_segmented_rmse,
    calculate_stitched_walkforward_rmse,
)
from qbt.utils.parallel_executor import WORKER_CACHE


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
        When: _calculate_daily_cost 호출
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
        daily_cost = _calculate_daily_cost(
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
        When: _calculate_daily_cost
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

        # When: 2개월 이내이므로 fallback 성공 (MAX_FFR_MONTHS_DIFF=2)
        daily_cost = _calculate_daily_cost(
            date_value=target_date,
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=0.006,
            leverage=leverage,
        )

        # Then: fallback으로 1월 FFR을 사용하여 비용이 정상 계산됨
        assert daily_cost > 0, "fallback 시에도 비용이 양수여야 합니다"

    def test_empty_ffr_dataframe(self):
        """
        FFR DataFrame이 비었을 때 테스트

        안정성: 빈 데이터는 즉시 에러

        Given: 빈 FFR DataFrame
        When: _calculate_daily_cost
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
            _calculate_daily_cost(
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
    def test__calculate_daily_cost_leverage_variations(self, leverage, expected_multiplier):
        """
        다양한 레버리지 배수별 비용 계산 테스트

        정책: 레버리지 비용 = funding_rate * (leverage - 1)
        차입 비율 = leverage - 1 (자기자본 1 + 빌린돈 N-1)

        Given:
          - 2023년 1월 15일
          - FFR=4.5%, funding_spread=0.006 (0.6%)
          - expense_ratio=0.0095 (0.95%)
          - leverage (parametrize로 여러 값 테스트)
        When: _calculate_daily_cost 호출
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
        daily_cost = _calculate_daily_cost(
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

        assert daily_cost == pytest.approx(expected_daily_cost, abs=1e-6), (
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
                COL_OPEN: [100.0, 100.5, 99.5, 101.5, 102.5],
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
        assert first_price == pytest.approx(initial_price, abs=1.0), f"첫 가격은 initial_price({initial_price}) 근처여야 합니다"

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
        underlying_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 2), date(2023, 1, 3)], COL_OPEN: [100.0, 100.5], COL_CLOSE: [100.0, 101.0]}
        )  # +1%

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

        assert final_price == pytest.approx(
            expected_price, abs=0.1
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
        underlying_df = pd.DataFrame({"Date": [date(2023, 1, 2)], "Open": [100.0], "Close": [100.0]})

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

    def test_high_low_approximation_for_synthetic_data(self):
        """
        합성 데이터의 High/Low가 Open/Close 기반 근사값으로 생성되는지 검증한다.

        Given: QQQ 데이터 (Open과 Close가 다른 값)
        When: simulate 호출
        Then: High == max(Open, Close), Low == min(Open, Close)
        """
        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
                COL_OPEN: [100.0, 100.5, 99.5],
                COL_CLOSE: [100.0, 101.0, 99.0],
            }
        )
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.0]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0]})

        # When
        result = simulate(
            underlying_df=underlying_df,
            leverage=3.0,
            expense_df=expense_df,
            initial_price=30.0,
            ffr_df=ffr_df,
            funding_spread=1e-9,
        )

        # Then: High == max(Open, Close), Low == min(Open, Close)
        for i in range(len(result)):
            row = result.iloc[i]
            expected_high = max(row[COL_OPEN], row[COL_CLOSE])
            expected_low = min(row[COL_OPEN], row[COL_CLOSE])
            assert row[COL_HIGH] == pytest.approx(
                expected_high, abs=1e-6
            ), f"행 {i}: High={row[COL_HIGH]}, expected max(O,C)={expected_high}"
            assert row[COL_LOW] == pytest.approx(
                expected_low, abs=1e-6
            ), f"행 {i}: Low={row[COL_LOW]}, expected min(O,C)={expected_low}"

    def test_high_low_relationship(self):
        """
        High >= Low 불변조건을 검증한다.

        Given: QQQ 데이터
        When: simulate 호출
        Then: 모든 행에서 High >= Low
        """
        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)],
                COL_OPEN: [100.0, 100.5, 99.5, 101.5],
                COL_CLOSE: [100.0, 101.0, 99.0, 102.0],
            }
        )
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When
        result = simulate(
            underlying_df=underlying_df,
            leverage=3.0,
            expense_df=expense_df,
            initial_price=30.0,
            ffr_df=ffr_df,
            funding_spread=0.006,
        )

        # Then: High >= Low
        assert (result[COL_HIGH] >= result[COL_LOW]).all(), "모든 행에서 High >= Low 이어야 합니다"


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
        underlying_df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, 1), date(2023, 1, 2)], COL_OPEN: [100.0, 104.0], COL_CLOSE: [100.0, 105.0]}
        )
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
        underlying_df = pd.DataFrame(columns=[COL_DATE, COL_OPEN, COL_CLOSE])
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
        assert result_df[COL_ACTUAL_CLOSE].iloc[0] == pytest.approx(100.1235, abs=0.0001)
        assert result_df[COL_SIMUL_CLOSE].iloc[0] == pytest.approx(100.2346, abs=0.0001)


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

        # When: expense ratio 데이터 로딩
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

    def test__calculate_daily_cost_with_expense_dict(self):
        """
        expense_dict를 사용한 일일 비용 계산 테스트

        Given: FFR dict, expense dict, 날짜
        When: _calculate_daily_cost 호출 (expense_dict 파라미터 사용)
        Then: 해당 날짜의 FFR과 expense를 조회하여 비용 계산
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)

        expense_dict = {"2023-01": 0.0095}  # 0.95%
        date_value = date(2023, 1, 15)

        # When: expense_dict 파라미터로 일일 비용 계산
        daily_cost = _calculate_daily_cost(
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
        from qbt.tqqq.simulation import _softplus

        x = 2.0
        result = _softplus(x)

        # log(1 + exp(2)) = log(1 + 7.389) ≈ 2.1269
        import math

        expected = math.log1p(math.exp(2.0))
        assert result == pytest.approx(expected, abs=1e-10), f"기대={expected}, 실제={result}"

    def test_softplus_negative_input(self):
        """
        음수 입력에 대한 softplus 계산 테스트

        Given: x = -2.0
        When: softplus(x) 호출
        Then: log(1 + exp(-2)) ≈ 0.1269 반환
        """
        from qbt.tqqq.simulation import _softplus

        x = -2.0
        result = _softplus(x)

        # log(1 + exp(-2)) = log(1 + 0.135) ≈ 0.1269
        import math

        expected = math.log1p(math.exp(-2.0))
        assert result == pytest.approx(expected, abs=1e-10), f"기대={expected}, 실제={result}"

    def test_softplus_zero_input(self):
        """
        0 입력에 대한 softplus 계산 테스트

        Given: x = 0.0
        When: softplus(x) 호출
        Then: log(2) ≈ 0.693 반환
        """
        from qbt.tqqq.simulation import _softplus

        x = 0.0
        result = _softplus(x)

        # log(1 + exp(0)) = log(2) ≈ 0.693
        import math

        expected = math.log(2.0)
        assert result == pytest.approx(expected, abs=1e-10), f"기대={expected}, 실제={result}"

    def test_softplus_always_positive(self):
        """
        softplus는 항상 양수를 반환해야 함

        Given: 다양한 입력값 (-100, -10, 0, 10, 100)
        When: softplus(x) 호출
        Then: 모든 결과 > 0
        """
        from qbt.tqqq.simulation import _softplus

        test_values = [-100.0, -10.0, -1.0, 0.0, 1.0, 10.0, 100.0]
        for x in test_values:
            result = _softplus(x)
            assert result > 0, f"_softplus({x}) = {result}가 양수가 아님"

    def test_softplus_numerical_stability(self):
        """
        수치 안정성 테스트 (큰 양수/음수 입력)

        Given: 극단적인 입력값
        When: softplus(x) 호출
        Then: overflow/underflow 없이 유한한 값 반환
        """
        import math

        from qbt.tqqq.simulation import _softplus

        # 큰 양수: softplus(x) ≈ x
        large_positive = 700.0  # exp(700)은 overflow 위험
        result_pos = _softplus(large_positive)
        assert math.isfinite(result_pos), f"_softplus({large_positive})가 유한하지 않음: {result_pos}"
        assert result_pos == pytest.approx(
            large_positive, abs=1.0
        ), f"_softplus({large_positive}) ≈ {large_positive} 예상"

        # 큰 음수: softplus(x) ≈ 0 (하지만 > 0)
        large_negative = -700.0
        result_neg = _softplus(large_negative)
        assert math.isfinite(result_neg), f"_softplus({large_negative})가 유한하지 않음: {result_neg}"
        assert result_neg > 0, f"_softplus({large_negative}) > 0 예상: {result_neg}"
        assert result_neg < 1e-10, f"_softplus({large_negative}) ≈ 0 예상: {result_neg}"

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
        assert result == pytest.approx(expected, abs=1e-10), f"기대={expected}, 실제={result}"

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

    def test__build_monthly_spread_map_from_dict_equivalence(self):
        """
        _build_monthly_spread_map_from_dict와 build_monthly_spread_map 결과 동일성 테스트

        Given: 동일한 FFR 데이터 (DataFrame vs dict)
        When: 두 함수 각각 호출
        Then: 결과가 완전히 동일
        """
        from qbt.tqqq.optimization import _build_monthly_spread_map_from_dict
        from qbt.tqqq.simulation import build_monthly_spread_map

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
            result_dict = _build_monthly_spread_map_from_dict(ffr_dict, a, b)

            # Then: 동일한 키와 값
            assert set(result_df.keys()) == set(result_dict.keys()), f"키 불일치: a={a}, b={b}"

            for month in result_df.keys():
                df_val = result_df[month]
                dict_val = result_dict[month]
                assert df_val == pytest.approx(dict_val, abs=1e-12), (
                    f"값 불일치: month={month}, a={a}, b={b}, " f"df={df_val}, dict={dict_val}"
                )

    def test__build_monthly_spread_map_from_dict_empty_raises(self):
        """
        빈 FFR 딕셔너리 입력 시 ValueError 테스트

        Given: 빈 FFR 딕셔너리
        When: _build_monthly_spread_map_from_dict 호출
        Then: ValueError 발생
        """
        from qbt.tqqq.optimization import _build_monthly_spread_map_from_dict

        ffr_dict: dict[str, float] = {}

        with pytest.raises(ValueError, match="비어있습니다"):
            _build_monthly_spread_map_from_dict(ffr_dict, a=-5.0, b=1.0)


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
        When: _calculate_daily_cost 호출
        Then: 기존과 동일하게 0.006이 적용됨
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}
        date_value = date(2023, 1, 15)

        # When: float spread 사용 (기존 동작)
        daily_cost = _calculate_daily_cost(
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

        assert daily_cost == pytest.approx(expected_daily_cost, abs=1e-10), f"기대={expected_daily_cost}, 실제={daily_cost}"

    def test_dict_spread_monthly_lookup(self):
        """
        dict 타입 funding_spread 월별 조회 테스트

        Given: funding_spread = {"2023-01": 0.004, "2023-02": 0.008}
        When: 2023-01-15 날짜로 _calculate_daily_cost 호출
        Then: 해당 월의 spread 0.004가 적용됨
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01", "2023-02"], COL_FFR_VALUE: [0.045, 0.046]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095, "2023-02": 0.0095}

        # 월별 spread dict
        spread_dict: dict[str, float] = {"2023-01": 0.004, "2023-02": 0.008}

        # When: 1월 날짜로 호출
        daily_cost_jan = _calculate_daily_cost(
            date_value=date(2023, 1, 15),
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=spread_dict,
            leverage=3.0,
        )

        # When: 2월 날짜로 호출
        daily_cost_feb = _calculate_daily_cost(
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
        assert actual_diff == pytest.approx(expected_diff, abs=1e-10), f"기대 차이={expected_diff}, 실제 차이={actual_diff}"

    def test_dict_spread_fallback_within_limit(self):
        """
        dict 타입 funding_spread 키 누락 시 이전 월 fallback 테스트

        Given: funding_spread = {"2023-01": 0.004} (2월 키 없음)
        When: 2023-02-15 날짜로 호출
        Then: 1개월 이내이므로 1월 값 0.004 fallback 적용
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-02"], COL_FFR_VALUE: [0.046]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-02": 0.0095}

        # 1월 키만 있는 spread dict
        spread_dict: dict[str, float] = {"2023-01": 0.004}

        # When: 2월 키 없음 -> 1월 값 fallback (1개월 차이, MAX_FFR_MONTHS_DIFF=2 이내)
        daily_cost = _calculate_daily_cost(
            date_value=date(2023, 2, 15),
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=spread_dict,
            leverage=3.0,
        )

        # Then: 1월 spread(0.004) + 2월 FFR(0.046) 적용
        expected = ((0.046 + 0.004) * 2 + 0.0095) / TRADING_DAYS_PER_YEAR
        assert daily_cost == pytest.approx(expected, abs=1e-10)

    def test_dict_spread_fallback_boundary_2months(self):
        """
        dict 타입 funding_spread fallback 경계값 테스트 (정확히 2개월 차이)

        Given: funding_spread = {"2023-01": 0.004}
        When: 2023-03-15 날짜로 호출
        Then: 2개월 차이 = MAX_FFR_MONTHS_DIFF(2) 이내 -> fallback 성공
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-03"], COL_FFR_VALUE: [0.047]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-03": 0.0095}
        spread_dict: dict[str, float] = {"2023-01": 0.004}

        # When: 3월 키 없음 -> 1월 값 fallback (2개월 차이 = 허용 경계)
        daily_cost = _calculate_daily_cost(
            date_value=date(2023, 3, 15),
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=spread_dict,
            leverage=3.0,
        )

        # Then: 1월 spread(0.004) + 3월 FFR(0.047) 적용
        expected = ((0.047 + 0.004) * 2 + 0.0095) / TRADING_DAYS_PER_YEAR
        assert daily_cost == pytest.approx(expected, abs=1e-10)

    def test_dict_spread_fallback_exceeds_limit_raises(self):
        """
        dict 타입 funding_spread fallback 월 차이 초과 시 ValueError 테스트

        Given: funding_spread = {"2023-01": 0.004} (4월 키 없음, 3개월 차이)
        When: 2023-04-15 날짜로 호출
        Then: MAX_FFR_MONTHS_DIFF(2개월) 초과 -> ValueError 발생
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-04"], COL_FFR_VALUE: [0.048]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-04": 0.0095}
        spread_dict: dict[str, float] = {"2023-01": 0.004}

        # When & Then: 3개월 차이 -> ValueError
        with pytest.raises(ValueError, match="funding_spread"):
            _calculate_daily_cost(
                date_value=date(2023, 4, 15),
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
                funding_spread=spread_dict,
                leverage=3.0,
            )

    def test_dict_spread_no_previous_months_raises(self):
        """
        dict 타입 funding_spread에 이전 월 데이터가 없을 때 ValueError 테스트

        Given: funding_spread = {"2023-06": 0.004}
        When: 2023-01-15 날짜로 호출
        Then: 이전 월 데이터 없음 -> ValueError 발생
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}
        spread_dict: dict[str, float] = {"2023-06": 0.004}

        # When & Then: 이전 월 없음 -> ValueError
        with pytest.raises(ValueError, match="funding_spread"):
            _calculate_daily_cost(
                date_value=date(2023, 1, 15),
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
                funding_spread=spread_dict,
                leverage=3.0,
            )

    def test_callable_spread_function_call(self):
        """
        Callable 타입 funding_spread 함수 호출 테스트

        Given: funding_spread = lambda d: 0.005 (고정 반환 함수)
        When: _calculate_daily_cost 호출
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
        daily_cost = _calculate_daily_cost(
            date_value=date(2023, 1, 15),
            ffr_dict=ffr_dict,
            expense_dict=expense_dict,
            funding_spread=fixed_spread_fn,
            leverage=3.0,
        )

        # Then: 0.005가 적용됨
        expected_daily_cost = ((0.045 + 0.005) * 2 + 0.0095) / TRADING_DAYS_PER_YEAR
        assert daily_cost == pytest.approx(expected_daily_cost, abs=1e-10)

    def test_callable_spread_nan_raises(self):
        """
        Callable 반환값이 NaN일 때 ValueError 테스트

        Given: funding_spread = lambda d: float('nan')
        When: _calculate_daily_cost 호출
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
            _calculate_daily_cost(
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
        When: _calculate_daily_cost 호출
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
            _calculate_daily_cost(
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
        When: _calculate_daily_cost 호출
        Then: ValueError 발생 (spread > 0 필수)
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}

        # When & Then: spread = 0 -> ValueError
        with pytest.raises(ValueError, match="0|양수|> 0"):
            _calculate_daily_cost(
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
        When: _calculate_daily_cost 호출
        Then: ValueError 발생 (음수 불허)
        """
        # Given
        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = {"2023-01": 0.0095}

        # When & Then: 음수 spread -> ValueError
        with pytest.raises(ValueError, match="음수|양수|> 0"):
            _calculate_daily_cost(
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
        import qbt.tqqq.optimization as opt_module

        # Stage 1: a in [-6, -5] step 1.0, b in [0.5, 1.0] step 0.5 -> 4조합
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_RANGE", (-6.0, -5.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_STEP", 1.0)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_RANGE", (0.5, 1.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_STEP", 0.5)

        # Stage 2: delta=0.5, step=0.5 -> 작은 범위
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_DELTA", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_STEP", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_DELTA", 0.25)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_STEP", 0.25)

        # When
        from qbt.tqqq.optimization import find_optimal_softplus_params

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
        from qbt.tqqq.optimization import find_optimal_softplus_params

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
        from qbt.tqqq.optimization import find_optimal_softplus_params

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
        import qbt.tqqq.optimization as opt_module

        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_RANGE", (-5.0, -5.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_STEP", 1.0)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_RANGE", (1.0, 1.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_STEP", 1.0)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_DELTA", 0.0)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_STEP", 1.0)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_DELTA", 0.0)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_STEP", 1.0)

        # When
        from qbt.tqqq.optimization import find_optimal_softplus_params

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
        from qbt.tqqq.walkforward import _local_refine_search

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
        from qbt.tqqq.walkforward import _local_refine_search

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


class TestFixedBParameter:
    """
    fixed_b 파라미터 테스트

    b를 고정하고 a만 최적화하는 모드의 동작을 검증한다.
    과최적화 진단을 위해 b의 자유도를 제거하는 기능이다.
    """

    def test_find_optimal_softplus_params_fixed_b(self, monkeypatch):
        """
        fixed_b 전달 시 반환된 b_best가 fixed_b와 동일한지 검증

        Given: 간단한 데이터, 작은 그리드, fixed_b=0.37
        When: find_optimal_softplus_params(fixed_b=0.37) 호출
        Then:
          - b_best == 0.37 (고정값과 동일)
          - a_best는 float
          - all_candidates의 모든 b가 0.37
        """
        # Given
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

        # 작은 그리드로 패치
        import qbt.tqqq.optimization as opt_module

        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_RANGE", (-6.0, -5.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_STEP", 1.0)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_RANGE", (0.0, 1.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_STEP", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_DELTA", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_STEP", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_DELTA", 0.25)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_STEP", 0.25)

        fixed_b_value = 0.37

        # When
        from qbt.tqqq.optimization import find_optimal_softplus_params

        a_best, b_best, best_rmse, all_candidates = find_optimal_softplus_params(
            underlying_df=underlying_df,
            actual_leveraged_df=actual_leveraged_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            leverage=3.0,
            max_workers=1,
            fixed_b=fixed_b_value,
        )

        # Then
        assert b_best == pytest.approx(fixed_b_value), f"b_best는 fixed_b와 동일해야 함: {b_best}"
        assert isinstance(a_best, float), f"a_best는 float이어야 함: {type(a_best)}"
        assert best_rmse >= 0, f"best_rmse는 0 이상이어야 함: {best_rmse}"

        # 모든 candidate의 b가 fixed_b와 동일
        for candidate in all_candidates:
            assert candidate["b"] == pytest.approx(fixed_b_value), f"candidate의 b가 fixed_b와 동일해야 함: {candidate['b']}"

    def test_local_refine_search_fixed_b(self):
        """
        _local_refine_search에 fixed_b 전달 시 b_best가 fixed_b와 동일한지 검증

        Given: 간단한 데이터, fixed_b=0.5
        When: _local_refine_search(fixed_b=0.5) 호출
        Then:
          - b_best == 0.5
          - 모든 candidates의 b가 0.5
        """
        # Given
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

        fixed_b_value = 0.5

        # When
        from qbt.tqqq.walkforward import _local_refine_search

        a_best, b_best, best_rmse, candidates = _local_refine_search(
            underlying_df=underlying_df,
            actual_df=actual_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            a_prev=-6.0,
            b_prev=0.5,
            leverage=3.0,
            max_workers=1,
            fixed_b=fixed_b_value,
        )

        # Then
        assert b_best == pytest.approx(fixed_b_value), f"b_best는 fixed_b와 동일해야 함: {b_best}"
        for candidate in candidates:
            assert candidate["b"] == pytest.approx(fixed_b_value), f"candidate의 b가 fixed_b와 동일해야 함: {candidate['b']}"

    def test_find_optimal_softplus_params_fixed_b_negative_raises(self, monkeypatch):
        """
        fixed_b가 음수이면 ValueError 발생

        Given: fixed_b=-0.1
        When: find_optimal_softplus_params(fixed_b=-0.1) 호출
        Then: ValueError 발생
        """
        # Given
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

        # 작은 그리드로 패치
        import qbt.tqqq.optimization as opt_module

        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_RANGE", (-6.0, -5.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_STEP", 1.0)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_RANGE", (0.0, 1.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_STEP", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_DELTA", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_STEP", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_DELTA", 0.25)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_STEP", 0.25)

        # When & Then
        from qbt.tqqq.optimization import find_optimal_softplus_params

        with pytest.raises(ValueError, match="fixed_b"):
            find_optimal_softplus_params(
                underlying_df=underlying_df,
                actual_leveraged_df=actual_leveraged_df,
                ffr_df=ffr_df,
                expense_df=expense_df,
                leverage=3.0,
                max_workers=1,
                fixed_b=-0.1,
            )


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
        from qbt.tqqq.walkforward import run_walkforward_validation

        # Given: 50개월 데이터 (60개월 train 불가)
        dates = []
        opens_underlying = []
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
                    close_price = 100.0 + i * 0.1
                    opens_underlying.append(close_price - 0.05)
                    closes_underlying.append(close_price)
                    closes_actual.append(30.0 + i * 0.3)
                except ValueError:
                    pass

        underlying_df = pd.DataFrame({COL_DATE: dates, COL_OPEN: opens_underlying, COL_CLOSE: closes_underlying})
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

    def test_run_walkforward_validation_fixed_b(self, monkeypatch):
        """
        fixed_b 전달 시 모든 결과 행의 b_best가 fixed_b와 동일한지 검증

        Given: 4개월 데이터, train_window_months=2, fixed_b=0.37
        When: run_walkforward_validation(fixed_b=0.37, train_window_months=2) 호출
        Then:
          - 모든 결과 행의 b_best == 0.37
          - 결과 DataFrame이 비어있지 않음
          - summary의 b_mean == 0.37, b_std == 0.0
        """
        # Given: 4개월 데이터 (2개월 train + 2개월 test)
        import qbt.tqqq.optimization as opt_module
        import qbt.tqqq.walkforward as wf_module

        # 작은 그리드로 패치 (속도 향상) — SOFTPLUS_GRID_*는 optimization 모듈에 위치
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_RANGE", (-6.0, -5.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_A_STEP", 1.0)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_RANGE", (0.0, 1.0))
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE1_B_STEP", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_DELTA", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_A_STEP", 0.5)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_DELTA", 0.25)
        monkeypatch.setattr(opt_module, "SOFTPLUS_GRID_STAGE2_B_STEP", 0.25)
        # WALKFORWARD_LOCAL_REFINE_*는 walkforward 모듈에 위치
        monkeypatch.setattr(wf_module, "WALKFORWARD_LOCAL_REFINE_A_DELTA", 0.5)
        monkeypatch.setattr(wf_module, "WALKFORWARD_LOCAL_REFINE_A_STEP", 0.5)
        monkeypatch.setattr(wf_module, "WALKFORWARD_LOCAL_REFINE_B_DELTA", 0.25)
        monkeypatch.setattr(wf_module, "WALKFORWARD_LOCAL_REFINE_B_STEP", 0.25)

        dates = []
        opens_underlying = []
        closes_underlying = []
        closes_actual = []
        ffr_dates = []

        # 4개월 데이터 생성 (2023-01 ~ 2023-04)
        for month_offset in range(4):
            month = month_offset + 1
            for day in range(1, 21):
                try:
                    d = date(2023, month, day + 1)
                    dates.append(d)
                    close_price = 100.0 + month_offset * 2.0 + day * 0.1
                    opens_underlying.append(close_price - 0.05)
                    closes_underlying.append(close_price)
                    closes_actual.append(30.0 + month_offset * 1.8 + day * 0.09)
                except ValueError:
                    pass
            ffr_dates.append(f"2023-{month:02d}")

        underlying_df = pd.DataFrame({COL_DATE: dates, COL_OPEN: opens_underlying, COL_CLOSE: closes_underlying})
        actual_df = pd.DataFrame({COL_DATE: dates, COL_CLOSE: closes_actual})
        ffr_df = pd.DataFrame({COL_FFR_DATE: ffr_dates, COL_FFR_VALUE: [0.045] * 4})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ffr_dates, COL_EXPENSE_VALUE: [0.0095] * 4})

        fixed_b_value = 0.37

        # When
        from qbt.tqqq.walkforward import run_walkforward_validation

        result_df, summary = run_walkforward_validation(
            underlying_df=underlying_df,
            actual_df=actual_df,
            ffr_df=ffr_df,
            expense_df=expense_df,
            leverage=3.0,
            train_window_months=2,
            max_workers=1,
            fixed_b=fixed_b_value,
        )

        # Then: 결과가 비어있지 않아야 함
        assert len(result_df) > 0, "워크포워드 결과 DataFrame이 비어있음"

        # Then: 모든 결과 행의 b_best가 fixed_b와 동일
        for _, row in result_df.iterrows():
            assert row["b_best"] == pytest.approx(fixed_b_value), f"b_best가 fixed_b와 동일해야 함: {row['b_best']}"

        # Then: summary의 b 통계
        assert summary["b_mean"] == pytest.approx(fixed_b_value), f"b_mean이 fixed_b와 동일해야 함: {summary['b_mean']}"
        assert summary["b_std"] == pytest.approx(0.0), f"b_std가 0이어야 함 (고정값): {summary['b_std']}"


# NOTE: 아래 테스트는 통합 테스트로서 실행 시간이 오래 걸립니다 (수십 분).
# CLI 스크립트로 분리되어 별도 실행이 권장됩니다.
# 필요 시 주석 해제하여 실행 가능합니다.
#
# class TestRunWalkforwardValidationIntegration:
#     """
#     run_walkforward_validation() 통합 테스트
#
#     실행 시간이 오래 걸리므로 필요 시에만 실행한다.
#     CLI 스크립트로 분리됨: scripts/tqqq/validate_walkforward.py
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

        Given: scripts/tqqq/spread_lab/ 디렉토리
        When: tune_softplus_params.py 존재 여부 확인
        Then: 파일이 존재함
        """
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "scripts" / "tqqq" / "spread_lab" / "tune_softplus_params.py"
        assert script_path.exists(), f"스크립트 파일이 존재해야 함: {script_path}"

    def test_walkforward_validation_script_exists(self):
        """
        워크포워드 검증 스크립트 파일 존재 테스트

        Given: scripts/tqqq/spread_lab/ 디렉토리
        When: validate_walkforward.py 존재 여부 확인
        Then: 파일이 존재함
        """
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "scripts" / "tqqq" / "spread_lab" / "validate_walkforward.py"
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
        # 시가: 종가에서 소폭 차이 (오버나이트 갭 시뮬레이션)
        opens = [prices[0]] + [prices[i - 1] * (1 + 0.001 * ((-1) ** i)) for i in range(1, 20)]

        underlying_df = pd.DataFrame({COL_DATE: dates, COL_OPEN: opens, COL_CLOSE: prices})

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
        from qbt.tqqq.optimization import (
            _build_monthly_spread_map_from_dict,
            _precompute_daily_costs_vectorized,
            _simulate_prices_vectorized,
        )
        from qbt.tqqq.simulation import simulate

        # Given
        underlying_df, ffr_df, expense_df, initial_price = self._create_test_data()
        leverage = 3.0

        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = create_expense_dict(expense_df)

        # softplus 파라미터 사용 (dict spread)
        a, b = -5.0, 0.8
        spread_map = _build_monthly_spread_map_from_dict(ffr_dict, a, b)

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
          - calculate_metrics_fast() 실행하여 RMSE 획득
        Then:
          - 두 RMSE 값이 1e-10 이내에서 동일
          - mean, max 값도 동일
        """
        from qbt.tqqq.simulation import (
            calculate_metrics_fast,
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
        actual_rmse, actual_mean, actual_max = calculate_metrics_fast(
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
        사전 계산된 일일 비용이 개별 _calculate_daily_cost() 호출 결과와 동일한지 검증한다.

        Given:
          - 2개월에 걸친 20일 거래 데이터
          - FFR, expense, softplus spread 데이터
        When:
          - _precompute_daily_costs_vectorized로 전체 비용 배열 한 번에 계산
          - _calculate_daily_cost로 각 날짜별 개별 계산
        Then:
          - 모든 날짜에서 비용이 1e-10 이내에서 동일
        """
        from qbt.tqqq.optimization import (
            _build_monthly_spread_map_from_dict,
            _precompute_daily_costs_vectorized,
        )
        from qbt.tqqq.simulation import _calculate_daily_cost

        # Given
        underlying_df, ffr_df, expense_df, _ = self._create_test_data()
        leverage = 3.0

        ffr_dict = create_ffr_dict(ffr_df)
        expense_dict = create_expense_dict(expense_df)

        a, b = -5.0, 0.8
        spread_map = _build_monthly_spread_map_from_dict(ffr_dict, a, b)

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
                _calculate_daily_cost(
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
            err_msg="사전 계산 비용이 개별 _calculate_daily_cost()와 동일해야 합니다",
        )


class TestCalculateStitchedWalkforwardRmse:
    """
    calculate_stitched_walkforward_rmse() 함수 테스트

    워크포워드 결과를 연속으로 붙인(stitched) 시뮬레이션 기반 RMSE를 계산한다.
    정적 RMSE와 동일한 수식(누적배수 로그차이 RMSE)을 사용하여 비교 가능하게 한다.
    """

    @pytest.fixture
    def stitched_test_data(self):
        """
        연속 워크포워드 RMSE 테스트용 데이터 세트를 생성한다.

        3개월분의 기초자산(QQQ), 실제 TQQQ, FFR, Expense 데이터와
        1개월짜리 워크포워드 결과를 생성한다.
        """
        # 기초자산 (QQQ) - 3개월, 각 월 약 21일
        base_dates = []
        base_open = []
        base_close = []
        price = 100.0
        prev_close = 100.0
        for month in [1, 2, 3]:
            for day in range(1, 22):
                try:
                    d = date(2023, month, day)
                    # 주말 제외 (간단히)
                    if d.weekday() < 5:
                        base_dates.append(d)
                        price *= 1.001  # 매일 0.1% 상승
                        base_open.append(round(prev_close * 1.0002, 2))
                        base_close.append(round(price, 2))
                        prev_close = price
                except ValueError:
                    pass

        underlying_df = pd.DataFrame({COL_DATE: base_dates, COL_OPEN: base_open, COL_CLOSE: base_close})

        # 실제 TQQQ - 동일 날짜, 3배 레버리지 근사
        tqqq_prices = [50.0]
        for i in range(1, len(base_close)):
            daily_ret = base_close[i] / base_close[i - 1] - 1
            leveraged_ret = daily_ret * 3.0 - 0.0002  # 약간의 비용 차감
            tqqq_prices.append(round(tqqq_prices[-1] * (1 + leveraged_ret), 2))

        actual_df = pd.DataFrame({COL_DATE: base_dates, COL_CLOSE: tqqq_prices})

        # FFR 데이터
        ffr_df = pd.DataFrame(
            {
                COL_FFR_DATE: ["2022-11", "2022-12", "2023-01", "2023-02", "2023-03"],
                COL_FFR_VALUE: [0.04, 0.045, 0.045, 0.046, 0.047],
            }
        )

        # Expense 데이터
        expense_df = pd.DataFrame(
            {
                "DATE": ["2022-01", "2023-01", "2023-02", "2023-03"],
                "VALUE": [0.0095, 0.0095, 0.0095, 0.0095],
            }
        )

        # 워크포워드 결과 (테스트 월: 2023-03, spread_test: softplus(-6.0 + 0.37 * 4.7))
        spread_test = compute_softplus_spread(-6.0, 0.37, 0.047)
        walkforward_df = pd.DataFrame(
            {
                "test_month": ["2023-03"],
                "spread_test": [spread_test],
                "a_best": [-6.0],
                "b_best": [0.37],
            }
        )

        return {
            "underlying_df": underlying_df,
            "actual_df": actual_df,
            "ffr_df": ffr_df,
            "expense_df": expense_df,
            "walkforward_df": walkforward_df,
        }

    def test_normal_stitched_rmse_returns_positive(self, stitched_test_data):
        """
        정상 케이스: 유효한 입력으로 양수 RMSE 반환

        Given: 3개월 기초자산/TQQQ + 1개월 워크포워드 결과
        When: calculate_stitched_walkforward_rmse 호출
        Then: 양수 RMSE(%) 반환
        """
        # Given
        data = stitched_test_data

        # When
        rmse = calculate_stitched_walkforward_rmse(
            walkforward_result_df=data["walkforward_df"],
            underlying_df=data["underlying_df"],
            actual_df=data["actual_df"],
            ffr_df=data["ffr_df"],
            expense_df=data["expense_df"],
        )

        # Then
        assert rmse > 0, "연속 RMSE는 양수여야 합니다"
        assert rmse < 100, "RMSE가 비정상적으로 크면 안 됩니다"

    def test_empty_walkforward_raises_error(self, stitched_test_data):
        """
        경계 케이스: 빈 워크포워드 result_df이면 ValueError 발생

        Given: 빈 워크포워드 result_df
        When: calculate_stitched_walkforward_rmse 호출
        Then: ValueError 발생
        """
        # Given
        data = stitched_test_data
        empty_wf = pd.DataFrame(columns=["test_month", "spread_test"])

        # When & Then
        with pytest.raises(ValueError, match="비어있습니다"):
            calculate_stitched_walkforward_rmse(
                walkforward_result_df=empty_wf,
                underlying_df=data["underlying_df"],
                actual_df=data["actual_df"],
                ffr_df=data["ffr_df"],
                expense_df=data["expense_df"],
            )

    def test_missing_columns_raises_error(self, stitched_test_data):
        """
        경계 케이스: 필수 컬럼이 누락되면 ValueError 발생

        Given: spread_test 컬럼이 없는 워크포워드 result_df
        When: calculate_stitched_walkforward_rmse 호출
        Then: ValueError 발생
        """
        # Given
        data = stitched_test_data
        bad_wf = pd.DataFrame({"test_month": ["2023-03"], "a_best": [-6.0]})

        # When & Then
        with pytest.raises(ValueError, match="필수 컬럼"):
            calculate_stitched_walkforward_rmse(
                walkforward_result_df=bad_wf,
                underlying_df=data["underlying_df"],
                actual_df=data["actual_df"],
                ffr_df=data["ffr_df"],
                expense_df=data["expense_df"],
            )

    def test_single_month_stitched_equals_monthly_rmse(self, stitched_test_data):
        """
        정합성 검증: 워크포워드 1개월일 때, 연속 RMSE와 월별 RMSE가 동일해야 한다.

        1개월만 있으면 리셋이 발생하지 않으므로 연속=월별이 동일하다.

        Given: 1개월짜리 워크포워드 결과
        When: 연속 RMSE와 별도 시뮬레이션 RMSE를 각각 계산
        Then: 두 값이 부동소수점 오차 범위 내에서 동일
        """
        # Given
        data = stitched_test_data

        # When: 연속 RMSE
        stitched_rmse = calculate_stitched_walkforward_rmse(
            walkforward_result_df=data["walkforward_df"],
            underlying_df=data["underlying_df"],
            actual_df=data["actual_df"],
            ffr_df=data["ffr_df"],
            expense_df=data["expense_df"],
        )

        # When: 월별 시뮬레이션으로 직접 RMSE 계산 (1개월이므로 리셋 없음)
        spread_test = float(data["walkforward_df"]["spread_test"].iloc[0])
        test_month = "2023-03"

        # 테스트 월 데이터 필터링
        underlying = data["underlying_df"].copy()
        actual = data["actual_df"].copy()
        underlying["_m"] = underlying[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")
        actual["_m"] = actual[COL_DATE].apply(lambda d: f"{d.year:04d}-{d.month:02d}")

        test_underlying = underlying[underlying["_m"] == test_month].drop(columns=["_m"])
        test_actual = actual[actual["_m"] == test_month].drop(columns=["_m"])

        initial_price = float(test_actual.iloc[0][COL_CLOSE])
        spread_map = {test_month: spread_test}

        sim_df = simulate(
            underlying_df=test_underlying,
            leverage=3.0,
            expense_df=data["expense_df"],
            initial_price=initial_price,
            ffr_df=data["ffr_df"],
            funding_spread=spread_map,
        )

        metrics = calculate_validation_metrics(simulated_df=sim_df, actual_df=test_actual)
        monthly_rmse = metrics["cumul_multiple_log_diff_rmse_pct"]

        # Then: 두 RMSE가 동일 (부동소수점 오차 허용)
        assert stitched_rmse == pytest.approx(monthly_rmse, abs=1e-6), (
            f"1개월 워크포워드에서 연속 RMSE({stitched_rmse:.6f})와 " f"월별 RMSE({monthly_rmse:.6f})가 동일해야 합니다"
        )


class TestCalculateFixedAbStitchedRmse:
    """
    calculate_fixed_ab_stitched_rmse() 함수 테스트

    전체기간 최적 고정 (a, b)를 아웃오브샘플에 그대로 적용한 stitched RMSE를 검증한다.
    """

    @pytest.fixture
    def fixed_ab_test_data(self):
        """
        고정 (a,b) stitched RMSE 테스트용 데이터 세트를 생성한다.

        train_window_months=2로 설정하여 3개월 중 마지막 1개월이 테스트 기간이 된다.
        """
        # 기초자산 (QQQ) - 3개월, 각 월 약 15~21 거래일
        base_dates = []
        base_open = []
        base_close = []
        price = 100.0
        prev_close = 100.0
        for month in [1, 2, 3]:
            for day in range(1, 22):
                try:
                    d = date(2023, month, day)
                    if d.weekday() < 5:
                        base_dates.append(d)
                        price *= 1.001
                        base_open.append(round(prev_close * 1.0002, 2))
                        base_close.append(round(price, 2))
                        prev_close = price
                except ValueError:
                    pass

        underlying_df = pd.DataFrame({COL_DATE: base_dates, COL_OPEN: base_open, COL_CLOSE: base_close})

        # 실제 TQQQ - 3배 레버리지 근사
        tqqq_prices = [50.0]
        for i in range(1, len(base_close)):
            daily_ret = base_close[i] / base_close[i - 1] - 1
            leveraged_ret = daily_ret * 3.0 - 0.0002
            tqqq_prices.append(round(tqqq_prices[-1] * (1 + leveraged_ret), 2))

        actual_df = pd.DataFrame({COL_DATE: base_dates, COL_CLOSE: tqqq_prices})

        # FFR 데이터
        ffr_df = pd.DataFrame(
            {
                COL_FFR_DATE: ["2022-11", "2022-12", "2023-01", "2023-02", "2023-03"],
                COL_FFR_VALUE: [0.04, 0.045, 0.045, 0.046, 0.047],
            }
        )

        # Expense 데이터
        expense_df = pd.DataFrame(
            {
                "DATE": ["2022-01", "2023-01", "2023-02", "2023-03"],
                "VALUE": [0.0095, 0.0095, 0.0095, 0.0095],
            }
        )

        return {
            "underlying_df": underlying_df,
            "actual_df": actual_df,
            "ffr_df": ffr_df,
            "expense_df": expense_df,
        }

    def test_calculate_fixed_ab_stitched_rmse_basic(self, fixed_ab_test_data):
        """
        목적: 고정 (a,b) stitched RMSE 계산이 정상 동작하는지 검증

        Given: 3개월 QQQ/TQQQ/FFR/Expense 데이터, a=-6.0, b=0.4, train_window=2개월
        When: calculate_fixed_ab_stitched_rmse() 호출
        Then: float 반환, 양수, 합리적 범위 내 (0~100)
        """
        # Given
        data = fixed_ab_test_data

        # When
        rmse = calculate_fixed_ab_stitched_rmse(
            underlying_df=data["underlying_df"],
            actual_df=data["actual_df"],
            ffr_df=data["ffr_df"],
            expense_df=data["expense_df"],
            a=-6.0,
            b=0.4,
            train_window_months=2,
        )

        # Then
        assert isinstance(rmse, float)
        assert rmse > 0, "RMSE는 양수여야 합니다"
        assert rmse < 100, "RMSE가 비정상적으로 크면 안 됩니다"

    def test_calculate_fixed_ab_stitched_rmse_empty_data(self, fixed_ab_test_data):
        """
        목적: 빈 데이터 입력 시 ValueError 발생 검증

        Given: 빈 underlying_df
        When: calculate_fixed_ab_stitched_rmse() 호출
        Then: ValueError 발생
        """
        # Given
        data = fixed_ab_test_data
        empty_df = pd.DataFrame(columns=[COL_DATE, COL_OPEN, COL_CLOSE])

        # When & Then
        with pytest.raises(ValueError, match="비어있습니다"):
            calculate_fixed_ab_stitched_rmse(
                underlying_df=empty_df,
                actual_df=data["actual_df"],
                ffr_df=data["ffr_df"],
                expense_df=data["expense_df"],
                a=-6.0,
                b=0.4,
                train_window_months=2,
            )


class TestCalculateRateSegmentedRmse:
    """
    calculate_rate_segmented_rmse() 함수 테스트

    금리 구간별 RMSE 분해가 정상 동작하는지 검증한다.
    """

    def test_calculate_rate_segmented_rmse_basic(self):
        """
        목적: 저금리/고금리 혼합 데이터에서 금리 구간별 RMSE 분해 검증

        Given: 저금리(1%) 3일 + 고금리(5%) 3일 데이터
        When: calculate_rate_segmented_rmse() 호출
        Then: low_rate_rmse, high_rate_rmse 모두 양수, 각 일수 정확
        """
        # Given: 6일간 가격 데이터
        actual_prices = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
        # 시뮬레이션은 약간 다르게
        simulated_prices = np.array([100.0, 100.5, 101.5, 102.0, 103.5, 104.0])

        # 저금리 3일 + 고금리 3일
        dates = [
            date(2023, 1, 2),  # 저금리 (1%)
            date(2023, 1, 3),
            date(2023, 1, 4),
            date(2023, 6, 1),  # 고금리 (5%)
            date(2023, 6, 2),
            date(2023, 6, 5),
        ]

        # FFR: 1월은 1% (저금리), 6월은 5% (고금리)
        ffr_df = pd.DataFrame(
            {
                "DATE": ["2022-11", "2022-12", "2023-01", "2023-02", "2023-03", "2023-04", "2023-05", "2023-06"],
                "VALUE": [0.01, 0.01, 0.01, 0.01, 0.03, 0.04, 0.05, 0.05],
            }
        )

        # When
        result = calculate_rate_segmented_rmse(
            actual_prices=actual_prices,
            simulated_prices=simulated_prices,
            dates=dates,
            ffr_df=ffr_df,
            rate_boundary_pct=2.0,
        )

        # Then
        assert result["low_rate_rmse"] is not None
        assert result["high_rate_rmse"] is not None
        assert result["low_rate_rmse"] > 0
        assert result["high_rate_rmse"] > 0
        assert result["low_rate_days"] == 3
        assert result["high_rate_days"] == 3
        assert result["rate_boundary_pct"] == 2.0

    def test_calculate_rate_segmented_rmse_single_segment(self):
        """
        목적: 모든 데이터가 한 구간에만 속할 때 (모두 저금리) 정상 동작 검증

        Given: 모든 거래일이 저금리(1%) 구간
        When: calculate_rate_segmented_rmse() 호출
        Then: low_rate_rmse는 양수, high_rate_rmse는 None, high_rate_days는 0
        """
        # Given: 모두 저금리
        actual_prices = np.array([100.0, 101.0, 102.0, 103.0])
        simulated_prices = np.array([100.0, 100.8, 101.5, 102.5])

        dates = [
            date(2023, 1, 2),
            date(2023, 1, 3),
            date(2023, 1, 4),
            date(2023, 1, 5),
        ]

        ffr_df = pd.DataFrame(
            {
                "DATE": ["2022-11", "2022-12", "2023-01"],
                "VALUE": [0.01, 0.01, 0.01],  # 모두 1% (저금리)
            }
        )

        # When
        result = calculate_rate_segmented_rmse(
            actual_prices=actual_prices,
            simulated_prices=simulated_prices,
            dates=dates,
            ffr_df=ffr_df,
            rate_boundary_pct=2.0,
        )

        # Then
        assert result["low_rate_rmse"] is not None
        assert result["low_rate_rmse"] > 0
        assert result["high_rate_rmse"] is None
        assert result["low_rate_days"] == 4
        assert result["high_rate_days"] == 0


class TestEvaluateSoftplusCandidate:
    """evaluate_softplus_candidate WORKER_CACHE 기반 테스트

    병렬 워커 함수를 직접 호출하여 반환 구조와 핵심 계산 경로를 검증한다.
    WORKER_CACHE를 직접 설정하고 함수 호출 후 정리한다.
    """

    @pytest.fixture(autouse=True)
    def setup_and_cleanup_worker_cache(self):
        """
        WORKER_CACHE에 최소 테스트 데이터를 설정하고 테스트 후 정리한다.

        Given: 10일치 가격 데이터 (2023-01-02 ~ 2023-01-13)
        - underlying_returns: QQQ 일일 수익률 (9개, pct_change 첫 행 제외)
        - actual_prices: TQQQ 실제 종가 (10개)
        - FFR/Expense: 2023-01 단일 월
        """
        # 10일치 QQQ 가격 (미세한 등락)
        qqq_prices = np.array([300.0, 301.5, 299.8, 302.0, 303.1, 301.0, 304.2, 302.5, 305.0, 303.8])

        # pct_change().fillna(0.0) 방식: 첫 요소를 0.0으로 설정하여 10개 배열 생성
        # (프로덕션 코드의 find_optimal_softplus_params 동일 방식)
        returns = np.diff(qqq_prices) / qqq_prices[:-1]
        underlying_returns = np.concatenate([[0.0], returns])  # 10개

        # TQQQ 실제 종가 (10일, 3배 레버리지 근사)
        actual_prices = np.array([30.0, 30.45, 29.83, 30.61, 30.94, 30.31, 31.28, 30.77, 31.52, 31.16])

        actual_cumulative_return = float(actual_prices[-1] / actual_prices[0]) - 1.0

        WORKER_CACHE.update(
            {
                "ffr_dict": {"2023-01": 0.045},
                "underlying_returns": underlying_returns,
                "actual_prices": actual_prices,
                "expense_dict": {"2023-01": 0.0095},
                "date_month_keys": np.array(["2023-01"] * 10),
                "overlap_start": date(2023, 1, 2),
                "overlap_end": date(2023, 1, 13),
                "overlap_days": 10,
                "actual_cumulative_return": actual_cumulative_return,
            }
        )

        yield

        WORKER_CACHE.clear()

    def test_returns_candidate_dict_with_all_keys(self):
        """
        목적: WORKER_CACHE 설정 후 호출 시 SoftplusCandidateDict 필수 키 반환 검증

        Given: WORKER_CACHE에 10일치 데이터 설정 (autouse fixture)
        When: evaluate_softplus_candidate 호출
        Then: 반환 딕셔너리에 모든 필수 키 존재, a/b 입력값 유지, RMSE >= 0
        """
        from qbt.tqqq.constants import (
            KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX,
            KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN,
            KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
            KEY_CUMULATIVE_RETURN_ACTUAL,
            KEY_CUMULATIVE_RETURN_REL_DIFF,
            KEY_CUMULATIVE_RETURN_SIMULATED,
            KEY_FINAL_CLOSE_ACTUAL,
            KEY_FINAL_CLOSE_REL_DIFF,
            KEY_FINAL_CLOSE_SIMULATED,
            KEY_OVERLAP_DAYS,
            KEY_OVERLAP_END,
            KEY_OVERLAP_START,
        )

        # When
        params = {"a": -5.0, "b": 0.5, "leverage": 3.0, "initial_price": 30.0}
        result = evaluate_softplus_candidate(params)

        # Then: 필수 키 존재
        required_keys = [
            "a",
            "b",
            "leverage",
            KEY_OVERLAP_START,
            KEY_OVERLAP_END,
            KEY_OVERLAP_DAYS,
            KEY_FINAL_CLOSE_ACTUAL,
            KEY_FINAL_CLOSE_SIMULATED,
            KEY_FINAL_CLOSE_REL_DIFF,
            KEY_CUMULATIVE_RETURN_SIMULATED,
            KEY_CUMULATIVE_RETURN_ACTUAL,
            KEY_CUMULATIVE_RETURN_REL_DIFF,
            KEY_CUMUL_MULTIPLE_LOG_DIFF_MEAN,
            KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
            KEY_CUMUL_MULTIPLE_LOG_DIFF_MAX,
        ]
        for key in required_keys:
            assert key in result, f"필수 키 누락: {key}"

        # a, b 입력값 유지
        assert result["a"] == pytest.approx(-5.0, abs=1e-12)
        assert result["b"] == pytest.approx(0.5, abs=1e-12)

        # RMSE >= 0
        assert result[KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE] >= 0, "RMSE는 0 이상이어야 합니다"

        # overlap_days == WORKER_CACHE 설정값
        assert result[KEY_OVERLAP_DAYS] == 10

        # 시뮬레이션 종가는 양수
        assert result[KEY_FINAL_CLOSE_SIMULATED] > 0, "시뮬레이션 종가는 양수여야 합니다"


class TestPrecomputeDailyCostsVectorizedErrors:
    """_precompute_daily_costs_vectorized 에러 케이스 테스트"""

    def test_spread_map_missing_key_raises(self):
        """
        목적: spread_map에 필요한 월 키가 누락되면 ValueError 발생 검증

        Given: month_keys에 "2023-01"이 있지만 spread_map은 빈 dict
        When: _precompute_daily_costs_vectorized 호출
        Then: ValueError 발생, "spread_map" 메시지 포함
        """
        # Given
        month_keys = np.array(["2023-01", "2023-01", "2023-01"])
        ffr_dict: dict[str, float] = {"2023-01": 0.045}
        expense_dict: dict[str, float] = {"2023-01": 0.0095}
        spread_map: dict[str, float] = {}  # 빈 딕셔너리 (키 누락)
        leverage = 3.0

        # When & Then
        with pytest.raises(ValueError, match="spread_map"):
            _precompute_daily_costs_vectorized(
                month_keys=month_keys,
                ffr_dict=ffr_dict,
                expense_dict=expense_dict,
                spread_map=spread_map,
                leverage=leverage,
            )


class TestSimulateOvernightOpen:
    """simulate() 함수의 오버나이트 갭 기반 Open 가격 계산 테스트

    레버리지 ETF의 시가(Open)는 기초 자산의 오버나이트 갭(전일 종가 → 당일 시가)을
    레버리지 배율로 확대하여 계산해야 한다.

    수식: TQQQ_Open(t) = TQQQ_Close(t-1) × (1 + (QQQ_Open(t)/QQQ_Close(t-1) - 1) × leverage)
    """

    def test_open_reflects_overnight_gap(self):
        """
        오버나이트 갭이 레버리지 배율로 Open에 반영되는지 확인한다.

        Given:
          - QQQ 3일 데이터, day2의 Open(102.0)이 day1의 Close(100.0)와 다름 (+2%)
          - leverage=3.0, 비용 최소화 (FFR=0, expense=0, spread=1e-9)
        When: simulate() 호출
        Then:
          - TQQQ_Open(day2) ≈ TQQQ_Close(day1) × (1 + 0.02 × 3.0) = TQQQ_Close(day1) × 1.06
          - TQQQ_Open(day3)도 동일 수식으로 계산됨
        """
        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
                COL_OPEN: [100.0, 102.0, 104.0],  # day2: +2% gap, day3: 갭 있음
                COL_CLOSE: [100.0, 105.0, 103.0],
            }
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.0]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0]})

        # When
        result = simulate(
            underlying_df=underlying_df,
            leverage=3.0,
            expense_df=expense_df,
            initial_price=30.0,
            ffr_df=ffr_df,
            funding_spread=1e-9,
        )

        # Then: day2 Open 검증
        # QQQ 오버나이트 수익률 = 102.0 / 100.0 - 1 = 0.02
        # TQQQ_Open(day2) = TQQQ_Close(day1) × (1 + 0.02 × 3.0) = 30.0 × 1.06 = 31.8
        tqqq_close_day1 = result.iloc[0][COL_CLOSE]
        expected_open_day2 = tqqq_close_day1 * (1 + (102.0 / 100.0 - 1) * 3.0)
        actual_open_day2 = result.iloc[1][COL_OPEN]

        assert actual_open_day2 == pytest.approx(
            expected_open_day2, abs=0.01
        ), f"day2 Open: expected={expected_open_day2:.4f}, actual={actual_open_day2:.4f}"

        # Then: day3 Open 검증
        # QQQ 오버나이트 수익률 = 104.0 / 105.0 - 1 ≈ -0.00952
        # TQQQ_Open(day3) = TQQQ_Close(day2) × (1 + (-0.00952) × 3.0)
        tqqq_close_day2 = result.iloc[1][COL_CLOSE]
        overnight_return_day3 = 104.0 / 105.0 - 1
        expected_open_day3 = tqqq_close_day2 * (1 + overnight_return_day3 * 3.0)
        actual_open_day3 = result.iloc[2][COL_OPEN]

        assert actual_open_day3 == pytest.approx(
            expected_open_day3, abs=0.01
        ), f"day3 Open: expected={expected_open_day3:.4f}, actual={actual_open_day3:.4f}"

    def test_first_day_open_equals_initial_price(self):
        """
        첫날 Open은 initial_price여야 한다.

        Given: Open 컬럼 포함된 underlying 데이터, initial_price=30.0
        When: simulate() 호출
        Then: 첫날 Open = 30.0 (initial_price)
        """
        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 2), date(2023, 1, 3)],
                COL_OPEN: [100.0, 101.5],
                COL_CLOSE: [100.0, 101.0],
            }
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When
        result = simulate(
            underlying_df=underlying_df,
            leverage=3.0,
            expense_df=expense_df,
            initial_price=30.0,
            ffr_df=ffr_df,
            funding_spread=0.006,
        )

        # Then
        assert result.iloc[0][COL_OPEN] == pytest.approx(30.0, abs=0.01), "첫날 Open은 initial_price여야 합니다"

    def test_close_unchanged_after_open_improvement(self):
        """
        Open 계산 변경이 Close에 영향을 주지 않는지 확인한다.

        Close는 기존 수식 그대로여야 한다:
        TQQQ_Close(t) = TQQQ_Close(t-1) × (1 + underlying_return(t) × leverage - daily_cost)

        Given: QQQ 2일 데이터 (underlying_return = 1%), leverage=3.0, 최소 비용
        When: simulate() 호출
        Then: Close는 initial_price × (1 + 0.01 × 3.0) ≈ 30.9 (비용 무시 가능)
        """
        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 2), date(2023, 1, 3)],
                COL_OPEN: [100.0, 100.5],
                COL_CLOSE: [100.0, 101.0],  # +1%
            }
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.0]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0]})

        # When
        result = simulate(
            underlying_df=underlying_df,
            leverage=3.0,
            expense_df=expense_df,
            initial_price=30.0,
            ffr_df=ffr_df,
            funding_spread=1e-9,
        )

        # Then: QQQ +1% → TQQQ +3% (비용 무시)
        # 30.0 × 1.03 = 30.9
        expected_close = 30.0 * 1.03
        actual_close = result.iloc[1][COL_CLOSE]
        assert actual_close == pytest.approx(
            expected_close, abs=0.01
        ), f"Close는 기존 로직과 동일해야 합니다: expected={expected_close:.4f}, actual={actual_close:.4f}"

    def test_open_required_column(self):
        """
        Open 컬럼이 누락되면 ValueError가 발생해야 한다.

        Given: Date + Close만 있는 underlying_df (Open 없음)
        When: simulate() 호출
        Then: ValueError (필수 컬럼 누락)
        """
        # Given
        underlying_df = pd.DataFrame(
            {
                COL_DATE: [date(2023, 1, 2), date(2023, 1, 3)],
                COL_CLOSE: [100.0, 101.0],
            }
        )

        ffr_df = pd.DataFrame({COL_FFR_DATE: ["2023-01"], COL_FFR_VALUE: [0.045]})
        expense_df = pd.DataFrame({COL_EXPENSE_DATE: ["2023-01"], COL_EXPENSE_VALUE: [0.0095]})

        # When & Then
        with pytest.raises(ValueError, match="필수 컬럼이 누락되었습니다"):
            simulate(
                underlying_df=underlying_df,
                leverage=3.0,
                expense_df=expense_df,
                initial_price=30.0,
                ffr_df=ffr_df,
                funding_spread=0.006,
            )
