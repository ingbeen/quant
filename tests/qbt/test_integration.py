"""
통합 테스트 모듈

이 파일은 무엇을 검증하나요?
1. 백테스트 파이프라인이 모듈 간 올바르게 연결되는가?

왜 중요한가요?
단위 테스트는 각 부품의 정확성을 보장하지만,
부품들이 조립되었을 때도 데이터가 올바르게 흘러가는지는 별도로 확인해야 합니다.

통합 테스트 원칙:
- 값의 정확성보다 파이프라인 연결에 초점 (값 정확성은 단위 테스트에서 보장)
- 데이터는 최소 크기 사용 (백테스트: ~25행)
- 파일 격리 필수 (tmp_path)
"""

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.engines.backtest_engine import run_buffer_strategy
from qbt.backtest.strategies.buffer_zone import BufferStrategyParams
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME
from qbt.utils.data_loader import load_stock_data


class TestBacktestWorkflow:
    """백테스트 파이프라인 통합 테스트

    호출 체인: CSV 저장 -> load_stock_data -> add_single_moving_average
               -> run_buffer_strategy
    값의 정확성보다 파이프라인 연결 검증에 초점
    """

    def test_full_backtest_pipeline(self, integration_stock_df, create_csv_file):
        """
        목적: 백테스트 전체 파이프라인이 연결되어 실행되는지 검증

        Given: 25행 주식 데이터 CSV, BufferStrategyParams(ma_window=5)
        When:
            1. CSV 저장 -> load_stock_data로 로드
            2. add_single_moving_average(window=5) 적용
            3. run_buffer_strategy 실행
        Then:
            - load_stock_data 반환 DataFrame에 OHLCV + Date 컬럼 존재
            - add_single_moving_average 후 MA 컬럼 추가됨
            - run_buffer_strategy 반환 tuple 3개 (trades_df, equity_df, summary_dict)
            - equity_df 행 수 > 0
            - summary_dict에 필수 키 존재
        """
        # Given: CSV 파일 저장
        csv_path = create_csv_file("QQQ_max.csv", integration_stock_df)

        # When 1: 데이터 로드
        df = load_stock_data(csv_path)

        # Then 1: 필수 컬럼 존재
        for col in [COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME]:
            assert col in df.columns, f"필수 컬럼 누락: {col}"
        assert len(df) == 25, "25행 데이터 로드"

        # When 2: 이동평균 계산
        df_with_ma = add_single_moving_average(df, window=5)

        # Then 2: MA 컬럼 추가됨
        assert "ma_5" in df_with_ma.columns, "ma_5 컬럼이 추가되어야 합니다"
        # 처음 4행은 NaN, 5행부터 값 존재
        assert df_with_ma["ma_5"].notna().sum() == 21, "window=5, 25행 중 21행에 MA 값 존재"

        # When 3: 버퍼존 전략 실행
        params = BufferStrategyParams(
            initial_capital=10000.0,
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
        )
        trades_df, equity_df, summary = run_buffer_strategy(df_with_ma, df_with_ma, params, log_trades=False)

        # Then 3: 반환 구조 검증
        assert isinstance(trades_df, pd.DataFrame), "trades_df는 DataFrame"
        assert isinstance(equity_df, pd.DataFrame), "equity_df는 DataFrame"
        assert isinstance(summary, dict), "summary는 dict"
        assert len(equity_df) > 0, "equity_df에 데이터가 있어야 합니다"

        # summary 필수 키 확인
        required_keys = [
            "initial_capital",
            "final_capital",
            "total_return_pct",
            "cagr",
            "mdd",
            "total_trades",
            "win_rate",
        ]
        for key in required_keys:
            assert key in summary, f"summary 필수 키 누락: {key}"

        # final_capital > 0 (양수 자본)
        assert summary["final_capital"] > 0, "최종 자본은 양수여야 합니다"
