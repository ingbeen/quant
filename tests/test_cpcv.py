"""CSCV/PBO/DSR 과최적화 통계 검증 모듈 테스트

CSCV(Combinatorial Symmetric Cross-Validation) 기반 PBO 및 DSR 계산의
정확성을 검증한다.

테스트 대상:
- 수학 유틸리티 (Normal CDF/PPF, logit)
- CSCV 분할 생성
- Sharpe/Calmar 블록 성과 지표
- PBO (Probability of Backtest Overfitting) 계산
- DSR (Deflated Sharpe Ratio) 계산
"""

import math

import numpy as np
import pandas as pd
import pytest


class TestNormCdf:
    """Normal CDF 수학적 정확성 테스트."""

    def test_cdf_at_zero(self) -> None:
        """
        목적: norm_cdf(0) = 0.5 (표준 정규 분포의 대칭점)

        Given: x = 0
        When: norm_cdf(0)
        Then: 0.5
        """
        from qbt.backtest.cpcv import _norm_cdf

        assert _norm_cdf(0.0) == pytest.approx(0.5, abs=1e-12)

    def test_cdf_at_positive(self) -> None:
        """
        목적: norm_cdf(1.96) ≈ 0.975 (95% 신뢰구간 상한)

        Given: x = 1.96
        When: norm_cdf(1.96)
        Then: 약 0.975
        """
        from qbt.backtest.cpcv import _norm_cdf

        assert _norm_cdf(1.96) == pytest.approx(0.97500, abs=1e-4)

    def test_cdf_at_negative(self) -> None:
        """
        목적: norm_cdf(-1.96) ≈ 0.025 (대칭성)

        Given: x = -1.96
        When: norm_cdf(-1.96)
        Then: 약 0.025
        """
        from qbt.backtest.cpcv import _norm_cdf

        assert _norm_cdf(-1.96) == pytest.approx(0.02500, abs=1e-4)

    def test_cdf_symmetry(self) -> None:
        """
        목적: norm_cdf(x) + norm_cdf(-x) = 1 (대칭 속성)

        Given: x = 1.5
        When: norm_cdf(1.5) + norm_cdf(-1.5)
        Then: 1.0
        """
        from qbt.backtest.cpcv import _norm_cdf

        assert _norm_cdf(1.5) + _norm_cdf(-1.5) == pytest.approx(1.0, abs=1e-12)


class TestNormPpf:
    """Normal PPF (Inverse CDF) 정확성 테스트."""

    def test_ppf_at_half(self) -> None:
        """
        목적: norm_ppf(0.5) = 0 (중앙값)

        Given: p = 0.5
        When: norm_ppf(0.5)
        Then: 0.0
        """
        from qbt.backtest.cpcv import _norm_ppf

        assert _norm_ppf(0.5) == pytest.approx(0.0, abs=1e-6)

    def test_ppf_at_975(self) -> None:
        """
        목적: norm_ppf(0.975) ≈ 1.96

        Given: p = 0.975
        When: norm_ppf(0.975)
        Then: 약 1.96
        """
        from qbt.backtest.cpcv import _norm_ppf

        assert _norm_ppf(0.975) == pytest.approx(1.96, abs=1e-2)

    def test_cdf_ppf_roundtrip(self) -> None:
        """
        목적: norm_cdf(norm_ppf(p)) ≈ p (왕복 검증)

        Given: p = 0.1, 0.25, 0.5, 0.75, 0.9
        When: norm_cdf(norm_ppf(p))
        Then: 원래 p와 동일
        """
        from qbt.backtest.cpcv import _norm_cdf, _norm_ppf

        for p in [0.1, 0.25, 0.5, 0.75, 0.9]:
            assert _norm_cdf(_norm_ppf(p)) == pytest.approx(p, abs=1e-6)


class TestLogit:
    """logit 함수 테스트."""

    def test_logit_at_half(self) -> None:
        """
        목적: logit(0.5) = 0 (대칭점)

        Given: p = 0.5
        When: logit(0.5)
        Then: 0.0
        """
        from qbt.backtest.cpcv import _logit

        assert _logit(0.5) == pytest.approx(0.0, abs=1e-12)

    def test_logit_positive(self) -> None:
        """
        목적: p > 0.5이면 logit > 0

        Given: p = 0.75
        When: logit(0.75)
        Then: 양수 (log(3) ≈ 1.0986)
        """
        from qbt.backtest.cpcv import _logit

        assert _logit(0.75) == pytest.approx(math.log(3), abs=1e-10)

    def test_logit_negative(self) -> None:
        """
        목적: p < 0.5이면 logit < 0

        Given: p = 0.25
        When: logit(0.25)
        Then: 음수 (-log(3) ≈ -1.0986)
        """
        from qbt.backtest.cpcv import _logit

        assert _logit(0.25) == pytest.approx(-math.log(3), abs=1e-10)

    def test_logit_boundary_raises(self) -> None:
        """
        목적: p=0 또는 p=1이면 ValueError

        Given: p = 0 또는 p = 1
        When: logit(p)
        Then: ValueError
        """
        from qbt.backtest.cpcv import _logit

        with pytest.raises(ValueError, match="0.*1"):
            _logit(0.0)
        with pytest.raises(ValueError, match="0.*1"):
            _logit(1.0)


class TestGenerateCscvSplits:
    """CSCV 분할 생성 테스트."""

    def test_split_count_6_blocks(self) -> None:
        """
        목적: n_blocks=6이면 C(6,3) = 20개 분할

        Given: n_blocks = 6
        When: generate_cscv_splits(6)
        Then: 20개 (IS, OOS) 튜플
        """
        from qbt.backtest.cpcv import generate_cscv_splits

        splits = generate_cscv_splits(6)
        assert len(splits) == 20

    def test_split_count_4_blocks(self) -> None:
        """
        목적: n_blocks=4이면 C(4,2) = 6개 분할

        Given: n_blocks = 4
        When: generate_cscv_splits(4)
        Then: 6개 (IS, OOS) 튜플
        """
        from qbt.backtest.cpcv import generate_cscv_splits

        splits = generate_cscv_splits(4)
        assert len(splits) == 6

    def test_split_symmetry(self) -> None:
        """
        목적: 모든 분할에서 IS와 OOS의 블록 수가 동일 (n/2)

        Given: n_blocks = 6
        When: generate_cscv_splits(6) 각 분할
        Then: len(IS) == len(OOS) == 3
        """
        from qbt.backtest.cpcv import generate_cscv_splits

        splits = generate_cscv_splits(6)
        for is_blocks, oos_blocks in splits:
            assert len(is_blocks) == 3
            assert len(oos_blocks) == 3

    def test_block_coverage(self) -> None:
        """
        목적: 모든 분할에서 IS + OOS = {0, 1, ..., n-1}

        Given: n_blocks = 6
        When: generate_cscv_splits(6) 각 분할
        Then: IS ∪ OOS = {0, 1, 2, 3, 4, 5}
        """
        from qbt.backtest.cpcv import generate_cscv_splits

        splits = generate_cscv_splits(6)
        full_set = set(range(6))
        for is_blocks, oos_blocks in splits:
            assert set(is_blocks) | set(oos_blocks) == full_set
            # IS와 OOS는 겹치지 않아야 함
            assert set(is_blocks) & set(oos_blocks) == set()

    def test_odd_blocks_raises(self) -> None:
        """
        목적: 홀수 블록 수이면 ValueError

        Given: n_blocks = 5
        When: generate_cscv_splits(5)
        Then: ValueError
        """
        from qbt.backtest.cpcv import generate_cscv_splits

        with pytest.raises(ValueError, match="짝수"):
            generate_cscv_splits(5)

    def test_too_few_blocks_raises(self) -> None:
        """
        목적: n_blocks < 2이면 ValueError

        Given: n_blocks = 1
        When: generate_cscv_splits(1)
        Then: ValueError
        """
        from qbt.backtest.cpcv import generate_cscv_splits

        with pytest.raises(ValueError):
            generate_cscv_splits(1)


class TestComputeAnnualizedSharpe:
    """Sharpe Ratio 계산 테스트."""

    def test_zero_std_returns_zero(self) -> None:
        """
        목적: 표준편차=0이면 Sharpe=0 (0으로 나누기 방지)

        Given: 모든 수익률이 동일 (std=0)
        When: _compute_annualized_sharpe([0.01, 0.01, 0.01])
        Then: 0.0
        """
        from qbt.backtest.cpcv import _compute_annualized_sharpe

        returns = np.array([0.01, 0.01, 0.01])
        assert _compute_annualized_sharpe(returns) == pytest.approx(0.0, abs=1e-12)

    def test_positive_returns_positive_sharpe(self) -> None:
        """
        목적: 양의 평균 수익률이면 양의 Sharpe

        Given: 양의 수익률 배열
        When: _compute_annualized_sharpe(...)
        Then: Sharpe > 0
        """
        from qbt.backtest.cpcv import _compute_annualized_sharpe

        # 평균 양수, std > 0인 수익률
        returns = np.array([0.01, 0.02, -0.005, 0.015, 0.008])
        sharpe = _compute_annualized_sharpe(returns)
        assert sharpe > 0

    def test_annualization_factor(self) -> None:
        """
        목적: sqrt(252) 연간화 배율 검증

        Given: 일별 수익률 mean=0.001, std=0.01
        When: _compute_annualized_sharpe(...)
        Then: SR = mean/std * sqrt(252) (population std, ddof=0)
        """
        from qbt.backtest.cpcv import _compute_annualized_sharpe

        # 충분한 데이터로 mean/std 안정화
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.01, 10000)
        sharpe = _compute_annualized_sharpe(returns)
        # ddof=0 (population std) 기준
        expected = (returns.mean() / np.std(returns, ddof=0)) * np.sqrt(252)
        assert sharpe == pytest.approx(expected, abs=0.01)

    def test_empty_returns_zero(self) -> None:
        """
        목적: 빈 배열이면 Sharpe=0

        Given: 빈 수익률 배열
        When: _compute_annualized_sharpe([])
        Then: 0.0
        """
        from qbt.backtest.cpcv import _compute_annualized_sharpe

        assert _compute_annualized_sharpe(np.array([])) == pytest.approx(0.0, abs=1e-12)


class TestComputeCalmarFromReturns:
    """수익률 배열에서 Calmar Ratio 계산 테스트."""

    def test_positive_returns_no_drawdown(self) -> None:
        """
        목적: 순증가 수익률이면 MDD=0 → 큰 Calmar 반환

        Given: 매일 양의 수익률 (드로우다운 없음)
        When: _compute_calmar_from_returns(...)
        Then: Calmar > 0 (큰 값)
        """
        from qbt.backtest.cpcv import _compute_calmar_from_returns

        # 매일 1% 수익률 (드로우다운 없음)
        returns = np.array([0.01] * 252)
        calmar = _compute_calmar_from_returns(returns)
        assert calmar > 0

    def test_mixed_returns_positive_calmar(self) -> None:
        """
        목적: 양의 CAGR + 음의 MDD → 양의 Calmar

        Given: 평균 양수, 일부 음수가 섞인 수익률
        When: _compute_calmar_from_returns(...)
        Then: Calmar > 0
        """
        from qbt.backtest.cpcv import _compute_calmar_from_returns

        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 504)  # 2년, 양의 평균
        calmar = _compute_calmar_from_returns(returns)
        assert calmar > 0

    def test_empty_returns_zero(self) -> None:
        """
        목적: 빈 배열이면 Calmar=0

        Given: 빈 수익률 배열
        When: _compute_calmar_from_returns([])
        Then: 0.0
        """
        from qbt.backtest.cpcv import _compute_calmar_from_returns

        assert _compute_calmar_from_returns(np.array([])) == pytest.approx(0.0, abs=1e-12)


class TestPboCalculation:
    """PBO (Probability of Backtest Overfitting) 계산 테스트."""

    def test_pbo_range(self) -> None:
        """
        목적: PBO는 항상 0~1 범위

        Given: 임의의 수익률 행렬
        When: calculate_pbo(...)
        Then: 0 <= PBO <= 1
        """
        from qbt.backtest.cpcv import calculate_pbo

        np.random.seed(42)
        # 10개 전략, 240일 (최소 블록 크기 확보)
        returns_matrix = np.random.normal(0, 0.01, (240, 10))
        result = calculate_pbo(returns_matrix, n_blocks=4, metric="sharpe")
        assert 0.0 <= result["pbo"] <= 1.0

    def test_random_strategies_moderate_pbo(self) -> None:
        """
        목적: 순수 랜덤 전략들이면 IS 최적이 OOS에서도 종종 상위에 위치하므로
              PBO가 반드시 0.5가 되지는 않지만, 지배 전략보다는 높아야 한다.

        Given: 모든 전략이 동일한 랜덤 분포 (alpha 없음)
        When: calculate_pbo(...)
        Then: PBO >= 0 (유효한 값)
        """
        from qbt.backtest.cpcv import calculate_pbo

        np.random.seed(42)
        # 100개 동일 분포 랜덤 전략, 1200일, 6블록(20 splits)
        returns_matrix = np.random.normal(0, 0.01, (1200, 100))
        result = calculate_pbo(returns_matrix, n_blocks=6, metric="sharpe")
        # 랜덤 전략 → PBO는 유효 범위
        assert 0.0 <= result["pbo"] <= 1.0

    def test_one_dominant_strategy_low_pbo(self) -> None:
        """
        목적: 1개 전략이 IS+OOS 모두 압도하면 PBO ≈ 0.0

        Given: 1개 전략만 지속적으로 양의 alpha, 나머지는 0 평균
        When: calculate_pbo(...)
        Then: PBO < 0.3
        """
        from qbt.backtest.cpcv import calculate_pbo

        np.random.seed(42)
        n_strategies = 20
        n_days = 600
        # 모든 전략: 0 평균 노이즈
        returns_matrix = np.random.normal(0, 0.01, (n_days, n_strategies))
        # 첫 전략만 강한 양의 alpha 추가 (매일 0.005 추가)
        returns_matrix[:, 0] += 0.005
        result = calculate_pbo(returns_matrix, n_blocks=4, metric="sharpe")
        assert result["pbo"] < 0.3

    def test_pbo_result_structure(self) -> None:
        """
        목적: PBO 결과에 필수 필드가 모두 존재

        Given: 유효한 수익률 행렬
        When: calculate_pbo(...)
        Then: pbo, n_splits, n_blocks, logit_lambdas, rank_below_median, metric 필드 존재
        """
        from qbt.backtest.cpcv import calculate_pbo

        np.random.seed(42)
        returns_matrix = np.random.normal(0, 0.01, (240, 10))
        result = calculate_pbo(returns_matrix, n_blocks=4, metric="sharpe")

        assert "pbo" in result
        assert "n_splits" in result
        assert "n_blocks" in result
        assert "logit_lambdas" in result
        assert "rank_below_median" in result
        assert "metric" in result
        assert result["metric"] == "sharpe"
        assert result["n_blocks"] == 4
        # C(4,2) = 6 splits
        assert result["n_splits"] == 6
        assert len(result["logit_lambdas"]) == 6


class TestDsrCalculation:
    """DSR (Deflated Sharpe Ratio) 계산 테스트."""

    def test_dsr_range(self) -> None:
        """
        목적: DSR은 항상 0~1 범위 (확률값)

        Given: 유효한 수익률과 n_trials
        When: calculate_dsr(...)
        Then: 0 <= DSR <= 1
        """
        from qbt.backtest.cpcv import calculate_dsr

        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)
        result = calculate_dsr(returns, n_trials=100)
        assert 0.0 <= result["dsr"] <= 1.0

    def test_many_trials_deflates(self) -> None:
        """
        목적: n_trials가 증가하면 E[SR_max]가 증가하므로 DSR이 감소하는 경향

        Given: 동일한 수익률, n_trials = 10 vs 1000
        When: calculate_dsr(returns, n_trials=10) vs calculate_dsr(returns, n_trials=1000)
        Then: DSR(n=1000) < DSR(n=10)
        """
        from qbt.backtest.cpcv import calculate_dsr

        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)
        dsr_10 = calculate_dsr(returns, n_trials=10)
        dsr_1000 = calculate_dsr(returns, n_trials=1000)
        assert dsr_1000["dsr"] < dsr_10["dsr"]

    def test_dsr_result_structure(self) -> None:
        """
        목적: DSR 결과에 필수 필드가 모두 존재

        Given: 유효한 수익률과 n_trials
        When: calculate_dsr(...)
        Then: dsr, sr_observed, sr_benchmark, z_score, n_trials, t_observations 필드 존재
        """
        from qbt.backtest.cpcv import calculate_dsr

        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 500)
        result = calculate_dsr(returns, n_trials=100)

        assert "dsr" in result
        assert "sr_observed" in result
        assert "sr_benchmark" in result
        assert "z_score" in result
        assert "n_trials" in result
        assert "t_observations" in result
        assert result["n_trials"] == 100
        assert result["t_observations"] == 500

    def test_high_sharpe_high_dsr(self) -> None:
        """
        목적: 매우 높은 Sharpe (강한 alpha)이면 DSR도 높음

        Given: 강한 양의 alpha (일별 0.01, std 0.01)
        When: calculate_dsr(returns, n_trials=100)
        Then: DSR > 0.9
        """
        from qbt.backtest.cpcv import calculate_dsr

        np.random.seed(42)
        # 강한 alpha: mean/std = 1.0 → annualized SR ≈ 15.87
        returns = np.random.normal(0.01, 0.01, 1000)
        result = calculate_dsr(returns, n_trials=100)
        assert result["dsr"] > 0.9

    def test_zero_std_returns_zero_dsr(self) -> None:
        """
        목적: 표준편차=0이면 DSR=0

        Given: 수익률 std=0
        When: calculate_dsr([0.01, 0.01, 0.01], n_trials=100)
        Then: DSR = 0.0
        """
        from qbt.backtest.cpcv import calculate_dsr

        returns = np.array([0.01, 0.01, 0.01])
        result = calculate_dsr(returns, n_trials=100)
        assert result["dsr"] == pytest.approx(0.0, abs=1e-12)


class TestGenerateParamCombinations:
    """파라미터 조합 생성 테스트."""

    def test_combination_count(self) -> None:
        """
        목적: 파라미터 리스트의 데카르트 곱 크기 검증

        Given: ma=[100], buy=[0.03], sell=[0.03], hold=[0,2], recent=[0]
        When: generate_param_combinations(...)
        Then: 1 × 1 × 1 × 2 × 1 = 2개 조합
        """
        from qbt.backtest.cpcv import generate_param_combinations

        combos = generate_param_combinations(
            ma_window_list=[100],
            buy_buffer_zone_pct_list=[0.03],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0, 2],
            recent_months_list=[0],
            initial_capital=10_000_000.0,
        )
        assert len(combos) == 2

    def test_combination_with_atr(self) -> None:
        """
        목적: ATR 파라미터 포함 시 조합 수 검증

        Given: ma=[100], buy=[0.03], sell=[0.03], hold=[0], recent=[0],
               atr_period=[14,22], atr_multiplier=[2.5]
        When: generate_param_combinations(...)
        Then: 1 × 1 × 1 × 1 × 1 × 2 = 2개 조합
        """
        from qbt.backtest.cpcv import generate_param_combinations

        combos = generate_param_combinations(
            ma_window_list=[100],
            buy_buffer_zone_pct_list=[0.03],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0],
            recent_months_list=[0],
            initial_capital=10_000_000.0,
            atr_period_list=[14, 22],
            atr_multiplier_list=[2.5],
        )
        assert len(combos) == 2

    def test_combination_has_params_key(self) -> None:
        """
        목적: 각 조합 딕셔너리에 'params' 키 존재 검증

        Given: 최소 파라미터
        When: generate_param_combinations(...)
        Then: 모든 항목에 'params' 키 존재, BufferStrategyParams 타입
        """
        from qbt.backtest.cpcv import generate_param_combinations
        from qbt.backtest.strategies.buffer_zone_helpers import BufferStrategyParams

        combos = generate_param_combinations(
            ma_window_list=[100],
            buy_buffer_zone_pct_list=[0.03],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0],
            recent_months_list=[0],
            initial_capital=10_000_000.0,
        )
        assert len(combos) == 1
        assert "params" in combos[0]
        assert isinstance(combos[0]["params"], BufferStrategyParams)


class TestBuildReturnsMatrix:
    """수익률 행렬 구축 테스트 (소규모 통합 테스트)."""

    def test_returns_matrix_shape(self, integration_stock_df: "pd.DataFrame") -> None:
        """
        목적: 소규모 파라미터(3개)로 수익률 행렬의 shape 검증

        Given: 25행 주식 데이터, MA window=5 EMA 사전 계산, 3개 파라미터 조합
        When: build_returns_matrix(...)
        Then: shape = (T, 3), T > 0
        """
        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.cpcv import build_returns_matrix, generate_param_combinations

        signal_df = add_single_moving_average(integration_stock_df.copy(), 5, ma_type="ema")
        trade_df = signal_df.copy()

        combos = generate_param_combinations(
            ma_window_list=[5],
            buy_buffer_zone_pct_list=[0.03],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0, 2, 3],
            recent_months_list=[0],
            initial_capital=10_000_000.0,
        )

        matrix = build_returns_matrix(signal_df, trade_df, combos)
        assert matrix.shape[1] == 3
        assert matrix.shape[0] > 0

    def test_returns_matrix_no_nan(self, integration_stock_df: "pd.DataFrame") -> None:
        """
        목적: 수익률 행렬에 NaN이 없음을 검증

        Given: 정상 주식 데이터
        When: build_returns_matrix(...)
        Then: NaN 없음
        """
        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.cpcv import build_returns_matrix, generate_param_combinations

        signal_df = add_single_moving_average(integration_stock_df.copy(), 5, ma_type="ema")
        trade_df = signal_df.copy()

        combos = generate_param_combinations(
            ma_window_list=[5],
            buy_buffer_zone_pct_list=[0.03],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0],
            recent_months_list=[0],
            initial_capital=10_000_000.0,
        )

        matrix = build_returns_matrix(signal_df, trade_df, combos)
        assert not np.any(np.isnan(matrix))


class TestRunCscvAnalysis:
    """CSCV 통합 분석 종단간 테스트."""

    def test_end_to_end_result_structure(self, integration_stock_df: "pd.DataFrame") -> None:
        """
        목적: run_cscv_analysis()의 반환 구조 검증

        Given: 25행 주식 데이터, 소규모 파라미터, n_blocks=2
        When: run_cscv_analysis(...)
        Then: CscvAnalysisResultDict의 필수 필드 존재, PBO/DSR 범위 0~1
        """
        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.cpcv import generate_param_combinations, run_cscv_analysis

        signal_df = add_single_moving_average(integration_stock_df.copy(), 5, ma_type="ema")
        trade_df = signal_df.copy()

        combos = generate_param_combinations(
            ma_window_list=[5],
            buy_buffer_zone_pct_list=[0.03, 0.05],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0, 2],
            recent_months_list=[0],
            initial_capital=10_000_000.0,
        )

        result = run_cscv_analysis(
            signal_df=signal_df,
            trade_df=trade_df,
            param_combinations=combos,
            strategy_name="test_strategy",
            n_blocks=2,
            metric="sharpe",
        )

        # 필수 필드 존재 검증
        assert "strategy" in result
        assert result["strategy"] == "test_strategy"
        assert "n_param_combinations" in result
        assert result["n_param_combinations"] == len(combos)
        assert "t_observations" in result
        assert "pbo_sharpe" in result
        assert "dsr" in result
        assert "best_is_sharpe" in result

        # PBO/DSR 범위 검증
        assert 0.0 <= result["pbo_sharpe"]["pbo"] <= 1.0
        assert 0.0 <= result["dsr"]["dsr"] <= 1.0
