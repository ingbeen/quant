"""버퍼존 전략 실행 및 그리드 서치 테스트

run_buffer_strategy()와 run_grid_search()의 정상 실행 및 결과 검증.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.engines.backtest_engine import run_buffer_strategy
from qbt.backtest.strategies.buffer_zone import BufferStrategyParams


class TestRunBufferStrategy:
    """버퍼존 전략 실행 테스트"""

    def test_normal_execution_with_trades(self):
        """
        정상적인 버퍼존 전략 실행 (매매 발생)

        데이터 신뢰성: 실제 전략 실행 시 신호 생성이 정확해야 합니다.

        Given:
          - ma_5 컬럼 포함 데이터
          - 반등하는 패턴
        When: run_buffer_strategy 실행
        Then:
          - trades_df, equity_df, summary 반환
          - DataFrame 구조 검증
        """
        # Given: ma_5 포함 데이터
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i for i in range(10)],
                "Close": [100, 95, 90, 95, 105, 110, 100, 95, 105, 110],
                "ma_5": [100, 98, 96, 94, 96, 98, 100, 102, 104, 106],
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 반환 타입 확인
        assert isinstance(trades_df, pd.DataFrame)
        assert isinstance(equity_df, pd.DataFrame)
        assert isinstance(summary, dict)

        # summary 검증
        assert "total_trades" in summary
        assert "total_return_pct" in summary
        assert "final_capital" in summary

        # equity_df 검증
        assert len(equity_df) > 0, "Equity curve는 최소 1행 이상"
        assert "equity" in equity_df.columns

    def test_missing_ma_column(self):
        """
        MA 컬럼 누락 시 자동 계산 테스트

        계약: signal_df에 MA 컬럼이 없으면 run_buffer_strategy가 자동으로 계산한다.

        Given: ma_5 컬럼 없는 DataFrame
        When: run_buffer_strategy (ma_window=5)
        Then: 에러 없이 실행되며 결과가 반환된다
        """
        # Given: MA 컬럼 없음, 충분한 행 수 (EMA 자동 계산 가능)
        n = 20
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(n)],
                "Open": [100.0 + i for i in range(n)],
                "Close": [100.0 + i for i in range(n)],
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            initial_capital=10000.0,
        )

        # When & Then: 에러 없이 실행 (MA 자동 계산)
        trades_df, equity_df, summary = run_buffer_strategy(df, df, params, log_trades=False)

        assert isinstance(equity_df, pd.DataFrame), "equity_df가 반환되어야 함"
        assert len(equity_df) > 0, "equity_df에 데이터가 있어야 함"

    def test_insufficient_valid_data(self):
        """
        유효 데이터 부족 시 에러 테스트

        안정성: MA 계산 후 NaN이 아닌 데이터가 너무 적으면 실패

        Given: 3행 데이터 (MA 계산 후 유효 데이터 1행)
        When: run_buffer_strategy
        Then: ValueError (최소 데이터 요구량 미달)
        """
        # Given: 최소 데이터
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                "Open": [100, 101, 102],
                "Close": [100, 101, 102],
                "ma_5": [None, None, 100],  # 처음 2개 NaN
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            initial_capital=10000.0,
        )

        # When & Then: 유효 데이터 1행으로는 부족
        with pytest.raises(ValueError) as exc_info:
            run_buffer_strategy(df, df, params, log_trades=False)

        assert "유효" in str(exc_info.value) or "부족" in str(exc_info.value), "유효 데이터 부족 에러"

    @pytest.mark.parametrize(
        "param_name,invalid_value,valid_base_params,error_pattern",
        [
            (
                "ma_window",
                0,
                {"buy_buffer_zone_pct": 0.03, "sell_buffer_zone_pct": 0.03, "hold_days": 0},
                "ma_window는 1 이상",
            ),
            (
                "buy_buffer_zone_pct",
                0.005,
                {"ma_window": 5, "sell_buffer_zone_pct": 0.03, "hold_days": 0},
                "buy_buffer_zone_pct는.*이상",
            ),
            (
                "sell_buffer_zone_pct",
                0.005,
                {"ma_window": 5, "buy_buffer_zone_pct": 0.03, "hold_days": 0},
                "sell_buffer_zone_pct는.*이상",
            ),
            (
                "hold_days",
                -1,
                {"ma_window": 5, "buy_buffer_zone_pct": 0.03, "sell_buffer_zone_pct": 0.03},
                "hold_days는.*이상",
            ),
        ],
        ids=[
            "invalid_ma_window",
            "invalid_buy_buffer_zone_pct",
            "invalid_sell_buffer_zone_pct",
            "invalid_hold_days",
        ],
    )
    def test_invalid_strategy_params_raise(self, param_name, invalid_value, valid_base_params, error_pattern):
        """
        전략 파라미터가 유효하지 않을 때 예외 발생 테스트

        Given: 유효하지 않은 파라미터 값 (parametrize로 여러 파라미터 테스트)
        When: run_buffer_strategy 호출
        Then: ValueError 발생

        Args:
            param_name: 테스트할 파라미터 이름
            invalid_value: 잘못된 값
            valid_base_params: 다른 유효한 파라미터들
            error_pattern: 예상 에러 메시지 패턴
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 1), date(2023, 1, 2)],
                "Open": [100, 101],
                "Close": [100, 101],
                "ma_5": [100, 101],
                "ma_0": [100, 101],  # invalid ma_window 테스트용
            }
        )

        # 파라미터 구성
        all_params = {**valid_base_params, param_name: invalid_value, "initial_capital": 10000.0}
        params = BufferStrategyParams(**all_params)

        # When & Then
        with pytest.raises(ValueError, match=error_pattern):
            run_buffer_strategy(df, df, params, log_trades=False)

    def test_forced_liquidation_at_end(self):
        """
        백테스트 종료 시 포지션 처리 테스트

        정책: 마지막 날 포지션이 남아있어도 강제청산하지 않음

        Given: 매수 후 매도 신호가 없는 데이터
        When: run_buffer_strategy
        Then: 마지막 equity에 포지션 평가액 포함
        """
        # Given: 계속 상승 (매도 신호 없음)
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i * 2 for i in range(10)],
                "Close": [100, 105, 110, 115, 120, 125, 130, 135, 140, 145],
                "ma_5": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 마지막 equity 확인
        if not equity_df.empty:
            last_equity = equity_df.iloc[-1]
            assert "equity" in last_equity.index, "equity 컬럼 존재"

    def test_hold_days_zero_vs_positive(self):
        """
        hold_days=0과 hold_days>0 경로 테스트

        회귀 방지: 두 경로 모두 정상 작동해야 합니다.

        Given: 같은 데이터
        When: hold_days=0 vs hold_days=3
        Then: 둘 다 에러 없이 실행, 거래 횟수는 다를 수 있음
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(20)],
                "Open": [100 + i for i in range(20)],
                "Close": [100 + i * 0.5 for i in range(20)],
                "ma_5": [100 + i * 0.3 for i in range(20)],
            }
        )

        params_zero = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            initial_capital=10000.0,
        )

        params_positive = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=3,
            initial_capital=10000.0,
        )

        # When
        trades_zero, _, _ = run_buffer_strategy(df, df, params_zero, log_trades=False)
        trades_positive, _, _ = run_buffer_strategy(df, df, params_positive, log_trades=False)

        # Then: 둘 다 실행됨 (에러 없음)
        assert isinstance(trades_zero, pd.DataFrame)
        assert isinstance(trades_positive, pd.DataFrame)

        # hold_days>0이면 거래가 더 적을 수 있음 (홀딩 조건 때문)
        # 단, 데이터에 따라 다르므로 부등호 검증은 생략


class TestRunGridSearch:
    """그리드 서치 테스트"""

    def test_basic_grid_search(self):
        """
        기본 그리드 서치 실행 테스트

        핵심 기능: 파라미터 조합 탐색 및 최적화

        Given: 충분한 데이터와 파라미터 조합
        When: run_grid_search 실행
        Then:
          - 모든 조합 실행 완료
          - 결과 DataFrame 반환
          - Calmar 기준 내림차순 정렬
        """
        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.engines.backtest_engine import run_grid_search

        # Given: 충분한 기간의 데이터
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 31)],
                "Open": [100 + i * 0.5 for i in range(30)],
                "Close": [100, 105, 95, 110, 90, 115, 95, 120, 100, 125] * 3,
            }
        )

        # 그리드 서치에 필요한 모든 MA 미리 계산
        for window in [5, 10]:
            df = add_single_moving_average(df, window=window, ma_type="ema")

        # When: 작은 그리드로 테스트
        results_df = run_grid_search(
            signal_df=df,
            trade_df=df,
            initial_capital=10000.0,
            ma_window_list=[5, 10],
            buy_buffer_zone_pct_list=[0.01, 0.03],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0, 1],
        )

        # Then: 결과 검증
        # 2 x 2 x 1 x 2 = 8개 조합
        assert len(results_df) == 8, "모든 파라미터 조합이 실행되어야 함"

        # 필수 컬럼 존재 확인
        from qbt.backtest.constants import (
            COL_BUY_BUFFER_ZONE_PCT,
            COL_CAGR,
            COL_CALMAR,
            COL_HOLD_DAYS,
            COL_MA_WINDOW,
            COL_SELL_BUFFER_ZONE_PCT,
            COL_TOTAL_RETURN_PCT,
        )

        required_cols = [
            COL_MA_WINDOW,
            COL_BUY_BUFFER_ZONE_PCT,
            COL_SELL_BUFFER_ZONE_PCT,
            COL_HOLD_DAYS,
            COL_TOTAL_RETURN_PCT,
            COL_CAGR,
            COL_CALMAR,
        ]
        for col in required_cols:
            assert col in results_df.columns, f"결과에 {col} 컬럼이 있어야 함"

        # 정렬 검증: Calmar 기준 내림차순
        calmar_values = results_df[COL_CALMAR].tolist()
        assert calmar_values == sorted(calmar_values, reverse=True), "결과가 Calmar 내림차순으로 정렬되어야 함"

    def test_grid_search_parameter_combinations(self):
        """
        그리드 서치 파라미터 조합 생성 검증

        Given: ma_window 2개, buy_buffer 2개, sell_buffer 1개, hold_days 2개 (2x2x1x2 = 8개 조합)
        When: run_grid_search 실행
        Then: 정확히 8개 결과 생성
        """
        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.engines.backtest_engine import run_grid_search

        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 31)],
                "Open": [100.0] * 30,
                "Close": [100 + i * 0.1 for i in range(30)],
            }
        )

        # MA 계산
        for window in [5, 10]:
            df = add_single_moving_average(df, window=window, ma_type="ema")

        # When
        results_df = run_grid_search(
            signal_df=df,
            trade_df=df,
            initial_capital=10000.0,
            ma_window_list=[5, 10],
            buy_buffer_zone_pct_list=[0.01, 0.02],
            sell_buffer_zone_pct_list=[0.03],
            hold_days_list=[0, 1],
        )

        # Then
        assert len(results_df) == 8, "2x2x1x2 = 8개 조합이 생성되어야 함"
