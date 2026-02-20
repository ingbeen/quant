"""
tqqq/optimization 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 2-stage grid search로 최적 softplus 파라미터 (a, b) 탐색이 정상 동작하는가?
2. fixed_b 모드에서 b가 고정되는가?
3. 벡터화 시뮬레이션이 기존 루프 기반과 수치적으로 동일한가?
4. WORKER_CACHE 기반 병렬 워커 함수가 올바른 결과를 반환하는가?
5. 벡터화 비용 계산의 에러 처리가 정확한가?

왜 중요한가요?
softplus 파라미터 최적화는 동적 스프레드 모델의 핵심입니다.
벡터화 경로의 수치 동등성이 보장되지 않으면 병렬 탐색 결과를 신뢰할 수 없습니다.
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN
from qbt.tqqq.constants import COL_EXPENSE_DATE, COL_EXPENSE_VALUE, COL_FFR_DATE, COL_FFR_VALUE
from qbt.tqqq.data_loader import create_expense_dict, create_ffr_dict
from qbt.tqqq.optimization import (
    _precompute_daily_costs_vectorized,
    evaluate_softplus_candidate,
)
from qbt.utils.parallel_executor import WORKER_CACHE


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
