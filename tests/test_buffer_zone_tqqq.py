"""
backtest/strategies/buffer_zone_tqqq 모듈 테스트

이 파일은 무엇을 검증하나요?
1. resolve_params 폴백 체인 (OVERRIDE -> grid_best -> DEFAULT)
2. run_single이 SingleBacktestResult 구조를 올바르게 반환하는지

왜 중요한가요?
buffer_zone_tqqq는 QQQ 시그널 + TQQQ 합성 데이터 매매 전략의 설정 및 실행을 담당합니다.
파라미터 결정 로직과 전체 실행 파이프라인의 정합성을 보장해야 합니다.
"""

from datetime import date

import pandas as pd


class TestResolveParams:
    """resolve_params 파라미터 결정 테스트

    목적: buffer_zone_tqqq의 resolve_params 함수가 올바른 폴백 체인을 따르는지 검증
    """

    def test_buffer_zone_resolve_params_default(self, tmp_path, monkeypatch):
        """
        목적: OVERRIDE=None, grid=None -> DEFAULT 사용 검증

        Given: OVERRIDE 상수 전부 None, grid_results.csv 없음
        When: resolve_params 호출
        Then: 모든 파라미터가 DEFAULT 상수 값 사용, 출처 "DEFAULT"
        """
        from qbt.backtest.constants import (
            DEFAULT_BUFFER_ZONE_PCT,
            DEFAULT_HOLD_DAYS,
            DEFAULT_MA_WINDOW,
            DEFAULT_RECENT_MONTHS,
        )
        from qbt.backtest.strategies import buffer_zone_tqqq

        # Given
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_MA_WINDOW", None)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_BUFFER_ZONE_PCT", None)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_HOLD_DAYS", None)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_RECENT_MONTHS", None)
        monkeypatch.setattr(buffer_zone_tqqq, "GRID_RESULTS_PATH", tmp_path / "nonexistent.csv")

        # When
        params, sources = buffer_zone_tqqq.resolve_params()

        # Then
        assert params.ma_window == DEFAULT_MA_WINDOW
        assert params.buffer_zone_pct == DEFAULT_BUFFER_ZONE_PCT
        assert params.hold_days == DEFAULT_HOLD_DAYS
        assert params.recent_months == DEFAULT_RECENT_MONTHS
        assert all(s == "DEFAULT" for s in sources.values())

    def test_buffer_zone_resolve_params_override(self, tmp_path, monkeypatch):
        """
        목적: OVERRIDE 값 설정 시 OVERRIDE 우선 검증

        Given: OVERRIDE 상수에 특정 값 설정
        When: resolve_params 호출
        Then: OVERRIDE 값이 사용됨, 출처 "OVERRIDE"
        """
        from qbt.backtest.strategies import buffer_zone_tqqq

        # Given
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_MA_WINDOW", 50)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_BUFFER_ZONE_PCT", 0.05)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_HOLD_DAYS", 3)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_RECENT_MONTHS", 6)
        monkeypatch.setattr(buffer_zone_tqqq, "GRID_RESULTS_PATH", tmp_path / "nonexistent.csv")

        # When
        params, sources = buffer_zone_tqqq.resolve_params()

        # Then
        assert params.ma_window == 50
        assert params.buffer_zone_pct == 0.05
        assert params.hold_days == 3
        assert params.recent_months == 6
        assert all(s == "OVERRIDE" for s in sources.values())

    def test_buffer_zone_resolve_params_grid(self, tmp_path, monkeypatch):
        """
        목적: grid_results.csv 존재 시 grid_best 사용 검증

        Given: OVERRIDE=None, grid_results.csv에 파라미터 존재
        When: resolve_params 호출
        Then: grid_results.csv의 첫 행 값 사용, 출처 "grid_best"
        """
        from qbt.backtest.constants import (
            DISPLAY_BUFFER_ZONE,
            DISPLAY_HOLD_DAYS,
            DISPLAY_MA_WINDOW,
            DISPLAY_RECENT_MONTHS,
        )
        from qbt.backtest.strategies import buffer_zone_tqqq

        # Given
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_MA_WINDOW", None)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_BUFFER_ZONE_PCT", None)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_HOLD_DAYS", None)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_RECENT_MONTHS", None)

        grid_path = tmp_path / "grid_results.csv"
        grid_df = pd.DataFrame(
            {
                DISPLAY_MA_WINDOW: [150],
                DISPLAY_BUFFER_ZONE: [0.04],
                DISPLAY_HOLD_DAYS: [2],
                DISPLAY_RECENT_MONTHS: [4],
            }
        )
        grid_df.to_csv(grid_path, index=False)
        monkeypatch.setattr(buffer_zone_tqqq, "GRID_RESULTS_PATH", grid_path)

        # When
        params, sources = buffer_zone_tqqq.resolve_params()

        # Then
        assert params.ma_window == 150
        assert params.buffer_zone_pct == 0.04
        assert params.hold_days == 2
        assert params.recent_months == 4
        assert all(s == "grid_best" for s in sources.values())


class TestRunSingle:
    """run_single 테스트

    목적: buffer_zone_tqqq의 run_single 함수가 SingleBacktestResult를 올바르게 반환하는지 검증
    """

    def test_buffer_zone_tqqq_run_single_returns_result(self, tmp_path, monkeypatch):
        """
        목적: buffer_zone_tqqq run_single이 SingleBacktestResult 구조를 올바르게 반환하는지 검증

        Given: 20일 데이터 (load_stock_data를 mock하여 테스트 DataFrame 반환)
        When: buffer_zone_tqqq.run_single() 호출 (인자 없음, 자체 로딩)
        Then: SingleBacktestResult 필드 정합성 확인, data_info 포함
        """
        from qbt.backtest.strategies import buffer_zone_tqqq
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
        monkeypatch.setattr(buffer_zone_tqqq, "load_stock_data", lambda _path: test_df.copy())
        monkeypatch.setattr(buffer_zone_tqqq, "extract_overlap_period", lambda s, t: (s.copy(), t.copy()))
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_MA_WINDOW", 5)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_BUFFER_ZONE_PCT", 0.03)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_HOLD_DAYS", 0)
        monkeypatch.setattr(buffer_zone_tqqq, "OVERRIDE_RECENT_MONTHS", 0)
        monkeypatch.setattr(buffer_zone_tqqq, "GRID_RESULTS_PATH", tmp_path / "nonexistent.csv")
        monkeypatch.setattr(buffer_zone_tqqq, "BUFFER_ZONE_TQQQ_RESULTS_DIR", tmp_path / "buffer_zone_tqqq")

        # When
        result = buffer_zone_tqqq.run_single()

        # Then
        assert isinstance(result, SingleBacktestResult)
        assert result.strategy_name == "buffer_zone_tqqq"
        assert result.display_name == "버퍼존 전략 (TQQQ)"
        assert isinstance(result.signal_df, pd.DataFrame)
        assert isinstance(result.equity_df, pd.DataFrame)
        assert isinstance(result.trades_df, pd.DataFrame)
        assert isinstance(result.summary, dict)
        assert isinstance(result.params_json, dict)
        assert "ma_window" in result.params_json
        assert "ma_type" in result.params_json
        assert result.result_dir == tmp_path / "buffer_zone_tqqq"
        assert isinstance(result.data_info, dict)
        assert "signal_path" in result.data_info
        assert "trade_path" in result.data_info
