"""TQQQ 시뮬레이션 비용 모델 테스트

일일 비용 계산, FFR 커버리지 검증, 동적 비용 계산, softplus 함수, 동적 펀딩 스프레드를 검증한다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.common_constants import TRADING_DAYS_PER_YEAR
from qbt.tqqq.constants import COL_EXPENSE_DATE, COL_EXPENSE_VALUE, COL_FFR_DATE, COL_FFR_VALUE
from qbt.tqqq.data_loader import create_expense_dict, create_ffr_dict
from qbt.tqqq.simulation import (
    _calculate_daily_cost,
    _validate_ffr_coverage,
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
        _validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

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
        _validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

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
            _validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

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
            _validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

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
        _validate_ffr_coverage(overlap_start, overlap_end, ffr_df)

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
        _validate_ffr_coverage(overlap_start, overlap_end, ffr_df)


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

    softplus 함수, _compute_softplus_spread, build_monthly_spread_map 함수를 검증한다.
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
        _compute_softplus_spread 기본 계산 테스트

        Given: a=-5, b=1, ffr_ratio=0.05 (5%)
        When: _compute_softplus_spread 호출
        Then: softplus(-5 + 1*5) = softplus(0) ≈ 0.693 반환
        """
        import math

        from qbt.tqqq.simulation import _compute_softplus_spread

        a, b = -5.0, 1.0
        ffr_ratio = 0.05  # 5%

        result = _compute_softplus_spread(a, b, ffr_ratio)

        # ffr_pct = 100 * 0.05 = 5.0
        # softplus(-5 + 1*5) = softplus(0) = log(2) ≈ 0.693
        expected = math.log(2.0)
        assert result == pytest.approx(expected, abs=1e-10), f"기대={expected}, 실제={result}"

    def test_compute_softplus_spread_high_rate(self):
        """
        고금리 구간에서 spread 증가 테스트

        Given: a=-5, b=1, 저금리(1%)와 고금리(5%) 비교
        When: _compute_softplus_spread 호출
        Then: 고금리 spread > 저금리 spread
        """
        from qbt.tqqq.simulation import _compute_softplus_spread

        a, b = -5.0, 1.0

        spread_low = _compute_softplus_spread(a, b, 0.01)  # 1%
        spread_high = _compute_softplus_spread(a, b, 0.05)  # 5%

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


class TestDynamicFundingSpread:
    """
    동적 funding_spread 지원 테스트

    funding_spread가 float 또는 dict[str, float] 타입을 지원함을 검증
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
