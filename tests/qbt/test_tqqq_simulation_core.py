"""TQQQ 시뮬레이션 코어 테스트

simulate() 함수의 핵심 계약, 입력 검증, 오버나이트 오픈 동작을 검증한다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN
from qbt.tqqq.constants import COL_EXPENSE_DATE, COL_EXPENSE_VALUE, COL_FFR_DATE, COL_FFR_VALUE
from qbt.tqqq.simulation import (
    simulate,
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
