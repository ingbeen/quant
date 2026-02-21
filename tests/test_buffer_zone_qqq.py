"""
backtest/strategies/buffer_zone_qqq 모듈 테스트

이 파일은 무엇을 검증하나요?
1. run_single이 SingleBacktestResult 구조를 올바르게 반환하는지

왜 중요한가요?
buffer_zone_qqq는 QQQ 시그널 + QQQ 매매 전략의 설정 및 실행을 담당합니다.
전체 실행 파이프라인의 정합성을 보장해야 합니다.
"""

from datetime import date

import pandas as pd


class TestRunSingle:
    """run_single 테스트

    목적: buffer_zone_qqq의 run_single 함수가 SingleBacktestResult를 올바르게 반환하는지 검증
    """

    def test_buffer_zone_qqq_run_single_returns_result(self, tmp_path, monkeypatch):
        """
        목적: buffer_zone_qqq run_single이 SingleBacktestResult 구조를 올바르게 반환하는지 검증

        Given: 20일 데이터 (load_stock_data를 mock하여 테스트 DataFrame 반환)
        When: buffer_zone_qqq.run_single() 호출 (인자 없음, 자체 로딩)
        Then: SingleBacktestResult 필드 정합성 확인, data_info 포함
        """
        from qbt.backtest.strategies import buffer_zone_qqq
        from qbt.backtest.types import SingleBacktestResult

        # Given: 테스트용 DataFrame
        test_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(20)],
                "Open": [100 + i for i in range(20)],
                "High": [102 + i for i in range(20)],
                "Low": [98 + i for i in range(20)],
                "Close": [100 + i * 0.5 for i in range(20)],
                "Volume": [1000000] * 20,
            }
        )

        # load_stock_data를 mock하여 테스트 DataFrame 반환
        monkeypatch.setattr(buffer_zone_qqq, "load_stock_data", lambda _path: test_df.copy())
        monkeypatch.setattr(buffer_zone_qqq, "OVERRIDE_MA_WINDOW", 5)
        monkeypatch.setattr(buffer_zone_qqq, "OVERRIDE_BUFFER_ZONE_PCT", 0.03)
        monkeypatch.setattr(buffer_zone_qqq, "OVERRIDE_HOLD_DAYS", 0)
        monkeypatch.setattr(buffer_zone_qqq, "OVERRIDE_RECENT_MONTHS", 0)
        monkeypatch.setattr(buffer_zone_qqq, "GRID_RESULTS_PATH", tmp_path / "nonexistent.csv")
        monkeypatch.setattr(buffer_zone_qqq, "BUFFER_ZONE_QQQ_RESULTS_DIR", tmp_path / "buffer_zone_qqq")

        # When
        result = buffer_zone_qqq.run_single()

        # Then
        assert isinstance(result, SingleBacktestResult)
        assert result.strategy_name == "buffer_zone_qqq"
        assert result.display_name == "버퍼존 전략 (QQQ)"
        assert isinstance(result.signal_df, pd.DataFrame)
        assert isinstance(result.equity_df, pd.DataFrame)
        assert isinstance(result.trades_df, pd.DataFrame)
        assert isinstance(result.summary, dict)
        assert isinstance(result.params_json, dict)
        assert "ma_window" in result.params_json
        assert "ma_type" in result.params_json
        assert result.result_dir == tmp_path / "buffer_zone_qqq"
        assert isinstance(result.data_info, dict)
        assert "signal_path" in result.data_info
        assert "trade_path" in result.data_info
