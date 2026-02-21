"""
tqqq/walkforward 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 로컬 정밀 탐색(_local_refine_search)이 올바른 구조를 반환하는가?
2. 워크포워드 검증(run_walkforward_validation)이 데이터 부족 시 예외를 내는가?
3. 연속(stitched) RMSE가 정상적으로 계산되는가?
4. 고정 (a,b) stitched RMSE가 양수를 반환하는가?
5. 금리 구간별 RMSE 분해가 정확한가?

왜 중요한가요?
워크포워드 검증은 softplus 모델의 아웃오브샘플 성능을 평가하는 핵심 도구입니다.
과최적화 여부를 진단하고, 금리 환경별 모델 성능 차이를 파악합니다.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN
from qbt.tqqq.constants import COL_EXPENSE_DATE, COL_EXPENSE_VALUE, COL_FFR_DATE, COL_FFR_VALUE
from qbt.tqqq.simulation import calculate_validation_metrics, compute_softplus_spread, simulate
from qbt.tqqq.walkforward import (
    calculate_fixed_ab_stitched_rmse,
    calculate_rate_segmented_rmse,
    calculate_stitched_walkforward_rmse,
)


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
