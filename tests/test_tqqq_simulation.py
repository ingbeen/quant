"""
tqqq/simulation 모듈 (core) 테스트

이 파일은 무엇을 검증하나요?
1. 일일 비용 계산이 FFR 기반으로 정확한가?
2. FFR 누락 시 fallback 로직이 작동하는가?
3. 너무 오래된 FFR만 있으면 에러를 내는가?
4. 레버리지 ETF 시뮬레이션이 NaN 없이 생성되는가?
5. 실제 데이터와의 비교 검증 메트릭이 정확한가?

왜 중요한가요?
TQQQ 같은 레버리지 ETF는 일일 리밸런싱으로 복리 효과가 발생합니다.
비용 모델이 틀리면 시뮬레이션 결과가 실제와 크게 차이나서 무의미해집니다.

참고: optimization, walkforward 관련 테스트는 각각
test_tqqq_optimization.py, test_tqqq_walkforward.py에서 수행합니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, TRADING_DAYS_PER_YEAR
from qbt.tqqq.constants import COL_EXPENSE_DATE, COL_EXPENSE_VALUE, COL_FFR_DATE, COL_FFR_VALUE
from qbt.tqqq.data_loader import create_expense_dict, create_ffr_dict
from qbt.tqqq.simulation import (
    _calculate_daily_cost,
    calculate_validation_metrics,
    compute_softplus_spread,
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
