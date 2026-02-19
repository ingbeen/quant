"""
통합 테스트 모듈

이 파일은 무엇을 검증하나요?
1. 백테스트 파이프라인이 모듈 간 올바르게 연결되는가?
2. TQQQ 시뮬레이션 파이프라인이 끊기지 않고 실행되는가?

왜 중요한가요?
단위 테스트는 각 부품의 정확성을 보장하지만,
부품들이 조립되었을 때도 데이터가 올바르게 흘러가는지는 별도로 확인해야 합니다.

통합 테스트 원칙:
- 값의 정확성보다 파이프라인 연결에 초점 (값 정확성은 단위 테스트에서 보장)
- 데이터는 최소 크기 사용 (백테스트: ~25행, TQQQ: ~10행)
- 파일 격리 필수 (tmp_path, mock_storage_paths)
"""

from datetime import date

import pandas as pd
from freezegun import freeze_time

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.strategy import BufferStrategyParams, run_buffer_strategy
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME
from qbt.tqqq import build_monthly_spread_map, calculate_validation_metrics, extract_overlap_period, simulate
from qbt.tqqq.constants import (
    KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
    KEY_OVERLAP_DAYS,
    KEY_OVERLAP_END,
    KEY_OVERLAP_START,
)
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata


class TestBacktestWorkflow:
    """백테스트 파이프라인 통합 테스트

    호출 체인: CSV 저장 -> load_stock_data -> add_single_moving_average
               -> run_buffer_strategy -> save_metadata
    값의 정확성보다 파이프라인 연결 검증에 초점
    """

    @freeze_time("2024-01-15 10:00:00")
    def test_full_backtest_pipeline(self, mock_storage_paths, integration_stock_df, create_csv_file):
        """
        목적: 백테스트 전체 파이프라인이 연결되어 실행되는지 검증

        Given: 25행 주식 데이터 CSV, BufferStrategyParams(ma_window=5)
        When:
            1. CSV 저장 -> load_stock_data로 로드
            2. add_single_moving_average(window=5) 적용
            3. run_buffer_strategy 실행
            4. save_metadata 호출
        Then:
            - load_stock_data 반환 DataFrame에 OHLCV + Date 컬럼 존재
            - add_single_moving_average 후 MA 컬럼 추가됨
            - run_buffer_strategy 반환 tuple 3개 (trades_df, equity_df, summary_dict)
            - equity_df 행 수 > 0
            - summary_dict에 필수 키 존재
            - meta.json 파일이 생성됨
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
            buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
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

        # When 4: 메타데이터 저장
        metadata = {
            "test": True,
            "total_return_pct": summary["total_return_pct"],
        }
        save_metadata("grid_results", metadata)

        # Then 4: meta.json 파일 생성 확인
        meta_path = mock_storage_paths["META_JSON_PATH"]
        assert meta_path.exists(), "meta.json 파일이 생성되어야 합니다"


class TestTQQQSimulationWorkflow:
    """TQQQ 시뮬레이션 파이프라인 통합 테스트

    호출 체인: 데이터 준비 -> extract_overlap_period -> build_monthly_spread_map
               -> simulate -> calculate_validation_metrics -> save_metadata
    """

    @freeze_time("2024-01-15 10:00:00")
    def test_full_tqqq_pipeline(self, mock_storage_paths):
        """
        목적: TQQQ 시뮬레이션 전체 파이프라인이 연결되어 실행되는지 검증

        Given:
            - QQQ 데이터 (~10행), TQQQ 데이터 (~10행, 동일 날짜)
            - FFR 데이터 (해당 월 커버, 2행)
            - Expense Ratio 데이터 (2행)
        When:
            1. extract_overlap_period(qqq_df, tqqq_df)
            2. build_monthly_spread_map(ffr_df, a=-6.1, b=0.37)
            3. simulate(...)
            4. calculate_validation_metrics(...)
            5. save_metadata(...)
        Then:
            - overlap 두 DataFrame 길이 동일
            - spread_map이 비어있지 않음
            - simulated_df에 Date, Close 컬럼 존재
            - ValidationMetricsDict 필수 키 존재
            - CSV 파일 생성됨
            - meta.json 파일 생성됨
        """
        # Given: 테스트 데이터 구성
        test_dates = [
            date(2023, 1, 3),
            date(2023, 1, 4),
            date(2023, 1, 5),
            date(2023, 1, 6),
            date(2023, 1, 9),
            date(2023, 1, 10),
            date(2023, 1, 11),
            date(2023, 1, 12),
            date(2023, 1, 13),
            date(2023, 1, 16),
        ]

        # QQQ 가격 (미세 등락)
        qqq_closes = [300.0, 301.5, 299.8, 302.0, 303.1, 301.0, 304.2, 302.5, 305.0, 303.8]
        qqq_df = pd.DataFrame(
            {
                COL_DATE: test_dates,
                COL_OPEN: [p - 0.3 for p in qqq_closes],
                COL_HIGH: [p + 1.0 for p in qqq_closes],
                COL_LOW: [p - 1.0 for p in qqq_closes],
                COL_CLOSE: qqq_closes,
                COL_VOLUME: [5000000] * 10,
            }
        )

        # TQQQ 가격 (3배 레버리지 근사)
        tqqq_closes = [30.0, 30.45, 29.83, 30.61, 30.94, 30.31, 31.28, 30.77, 31.52, 31.16]
        tqqq_df = pd.DataFrame(
            {
                COL_DATE: test_dates,
                COL_OPEN: [p - 0.1 for p in tqqq_closes],
                COL_HIGH: [p + 0.3 for p in tqqq_closes],
                COL_LOW: [p - 0.3 for p in tqqq_closes],
                COL_CLOSE: tqqq_closes,
                COL_VOLUME: [8000000] * 10,
            }
        )

        # FFR 데이터 (2023-01 커버)
        ffr_df = pd.DataFrame({"DATE": ["2022-12", "2023-01"], "VALUE": [0.043, 0.045]})

        # Expense Ratio 데이터
        expense_df = pd.DataFrame({"DATE": ["2022-12", "2023-01"], "VALUE": [0.0095, 0.0095]})

        # When 1: 겹치는 기간 추출
        qqq_overlap, tqqq_overlap = extract_overlap_period(qqq_df, tqqq_df)

        # Then 1: 두 DataFrame 길이 동일
        assert len(qqq_overlap) == len(tqqq_overlap), "overlap 길이가 동일해야 합니다"
        assert len(qqq_overlap) == 10, "10행 데이터"

        # When 2: softplus 스프레드 맵 생성
        spread_map = build_monthly_spread_map(ffr_df, a=-6.1, b=0.37)

        # Then 2: 비어있지 않음
        assert isinstance(spread_map, dict), "spread_map은 dict"
        assert len(spread_map) > 0, "spread_map이 비어있지 않아야 합니다"

        # When 3: 시뮬레이션 실행
        initial_price = float(tqqq_overlap.iloc[0][COL_CLOSE])
        simulated_df = simulate(
            underlying_df=qqq_overlap,
            leverage=3.0,
            initial_price=initial_price,
            ffr_df=ffr_df,
            expense_df=expense_df,
            funding_spread=spread_map,
        )

        # Then 3: simulated_df 구조 검증
        assert COL_DATE in simulated_df.columns, "Date 컬럼 존재"
        assert COL_CLOSE in simulated_df.columns, "Close 컬럼 존재"
        assert len(simulated_df) == len(qqq_overlap), "행 수가 원본과 동일"
        assert (simulated_df[COL_CLOSE] > 0).all(), "모든 가격은 양수"

        # When 4: 검증 지표 계산 + CSV 저장
        output_path = mock_storage_paths["TQQQ_RESULTS_DIR"] / "tqqq_daily_comparison.csv"
        validation_results = calculate_validation_metrics(
            simulated_df=simulated_df,
            actual_df=tqqq_overlap,
            output_path=output_path,
        )

        # Then 4: ValidationMetricsDict 필수 키 존재
        required_keys = [
            KEY_OVERLAP_START,
            KEY_OVERLAP_END,
            KEY_OVERLAP_DAYS,
            KEY_CUMUL_MULTIPLE_LOG_DIFF_RMSE,
        ]
        for key in required_keys:
            assert key in validation_results, f"검증 지표 필수 키 누락: {key}"

        assert validation_results[KEY_OVERLAP_DAYS] > 0, "겹치는 일수 > 0"

        # CSV 파일 생성 확인
        assert output_path.exists(), "일별 비교 CSV 파일이 생성되어야 합니다"
        saved_df = pd.read_csv(output_path)
        assert len(saved_df) > 0, "CSV에 데이터가 있어야 합니다"

        # When 5: 메타데이터 저장
        metadata = {
            "test": True,
            "overlap_days": validation_results[KEY_OVERLAP_DAYS],
        }
        save_metadata("tqqq_daily_comparison", metadata)

        # Then 5: meta.json 파일 생성 확인
        meta_path = mock_storage_paths["META_JSON_PATH"]
        assert meta_path.exists(), "meta.json 파일이 생성되어야 합니다"
