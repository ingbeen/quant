"""
backtest/strategies/buffer_zone 통합 모듈 테스트

이 파일은 무엇을 검증하나요?
1. BufferZoneConfig frozen dataclass 구조 및 CONFIGS 정합성
2. get_config() 이름 조회 및 에러 처리
3. resolve_params_for_config() 파라미터 결정 (직접 설정 + 기본값)
4. create_runner() 팩토리 함수 및 SingleBacktestResult 반환 구조
5. signal_path == trade_path 분기 (overlap 호출 여부)
6. TQQQ/QQQ config별 resolve_params_for_config 파라미터 검증
7. TQQQ/QQQ config별 create_runner run_single 구조 검증

왜 중요한가요?
buffer_zone.py는 8개 자산의 config-driven 통합 전략 모듈입니다.
전 자산 4P 고정 파라미터(MA=200, buy=0.03, sell=0.05, hold=3)로 통일된
설정 정합성과 팩토리 패턴의 정확성이 핵심입니다.
"""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from qbt.backtest import runners
from qbt.backtest.strategies.buffer_zone import (
    CONFIGS,
    BufferZoneConfig,
    get_config,
    resolve_params_for_config,
)
from qbt.backtest.types import SingleBacktestResult


class TestBufferZoneConfig:
    """BufferZoneConfig dataclass 및 CONFIGS 정합성 테스트

    목적: config-driven 아키텍처의 기반이 되는 데이터 구조가 올바른지 검증
    """

    def test_config_frozen_dataclass(self):
        """
        목적: BufferZoneConfig가 frozen dataclass인지 검증 (불변성 보장)

        Given: BufferZoneConfig 인스턴스 생성
        When: 속성 변경 시도
        Then: FrozenInstanceError 또는 AttributeError 발생
        """
        # Given
        config = BufferZoneConfig(
            strategy_name="test",
            display_name="테스트",
            signal_data_path=Path("signal.csv"),
            trade_data_path=Path("trade.csv"),
            result_dir=Path("results/test"),
        )

        # When & Then: frozen이므로 속성 변경 시 예외 발생
        with pytest.raises((AttributeError, Exception)):
            config.strategy_name = "changed"  # type: ignore[misc]

    def test_configs_list_has_expected_count(self):
        """
        목적: CONFIGS 리스트가 8개 설정을 포함하는지 검증

        Given: buffer_zone.CONFIGS
        When: 길이 확인
        Then: 8개
        """
        # Then
        assert len(CONFIGS) == 8, f"CONFIGS는 8개여야 합니다. 실제: {len(CONFIGS)}"

    def test_configs_unique_strategy_names(self):
        """
        목적: 모든 strategy_name이 고유한지 검증

        Given: buffer_zone.CONFIGS
        When: strategy_name 중복 확인
        Then: 중복 없음
        """
        # Given
        names = [c.strategy_name for c in CONFIGS]

        # Then
        assert len(names) == len(set(names)), f"strategy_name 중복 발견: {names}"

    def test_get_config_returns_correct_config(self):
        """
        목적: get_config("buffer_zone_tqqq")가 올바른 설정을 반환하는지 검증

        Given: CONFIGS에 buffer_zone_tqqq 설정 존재
        When: get_config("buffer_zone_tqqq") 호출
        Then: strategy_name이 "buffer_zone_tqqq"인 config 반환
        """
        # When
        config = get_config("buffer_zone_tqqq")

        # Then
        assert config.strategy_name == "buffer_zone_tqqq"
        assert isinstance(config, BufferZoneConfig)

    def test_get_config_raises_for_unknown(self):
        """
        목적: 존재하지 않는 이름에 ValueError 발생 검증

        Given: "nonexistent_strategy"라는 이름
        When: get_config("nonexistent_strategy") 호출
        Then: ValueError 발생
        """
        # When & Then
        with pytest.raises(ValueError):
            get_config("nonexistent_strategy")


class TestResolveParamsForConfig:
    """resolve_params_for_config 파라미터 결정 테스트

    목적: config의 파라미터가 올바르게 resolve되는지 검증
    """

    def test_explicit_params_used(self):
        """
        목적: 직접 설정한 파라미터가 사용되는지 검증

        Given: 파라미터가 직접 설정된 config
        When: resolve_params_for_config 호출
        Then: 설정된 값이 params에 반영, 출처 "FIXED"
        """
        # Given
        config = BufferZoneConfig(
            strategy_name="test_explicit",
            display_name="테스트 직접 설정",
            signal_data_path=Path("signal.csv"),
            trade_data_path=Path("trade.csv"),
            result_dir=Path("results/test"),
            ma_window=200,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
        )

        # When
        params, sources = resolve_params_for_config(config)

        # Then
        assert params.ma_window == 200
        assert params.buy_buffer_zone_pct == 0.03
        assert params.sell_buffer_zone_pct == 0.05
        assert params.hold_days == 0
        assert all(s == "FIXED" for s in sources.values())

    def test_default_values_when_not_specified(self):
        """
        목적: 기본값만으로 생성 시 FIXED_4P_* 기본값이 적용되는지 검증

        Given: 필수 필드만 설정한 config (기본값 사용)
        When: resolve_params_for_config 호출
        Then: FIXED_4P_* 기본값 사용, 출처 "FIXED"
        """
        from qbt.backtest.constants import (
            FIXED_4P_BUY_BUFFER_ZONE_PCT,
            FIXED_4P_HOLD_DAYS,
            FIXED_4P_MA_WINDOW,
            FIXED_4P_SELL_BUFFER_ZONE_PCT,
        )

        # Given
        config = BufferZoneConfig(
            strategy_name="test_default",
            display_name="테스트 디폴트",
            signal_data_path=Path("signal.csv"),
            trade_data_path=Path("trade.csv"),
            result_dir=Path("results/test"),
        )

        # When
        params, sources = resolve_params_for_config(config)

        # Then
        assert params.ma_window == FIXED_4P_MA_WINDOW
        assert params.buy_buffer_zone_pct == FIXED_4P_BUY_BUFFER_ZONE_PCT
        assert params.sell_buffer_zone_pct == FIXED_4P_SELL_BUFFER_ZONE_PCT
        assert params.hold_days == FIXED_4P_HOLD_DAYS
        assert all(s == "FIXED" for s in sources.values())

    def test_4p_config_sets_hold_days_three(self):
        """
        목적: 전 자산 4P 고정 파라미터에서 hold_days=3 확인

        Given: 4P 고정 패턴의 config (override로 고정값 설정)
        When: resolve_params_for_config 호출
        Then: hold_days=3 확인
        """
        # Given: 4P 패턴 (SPY 예시)
        config = get_config("buffer_zone_spy")

        # When
        params, _sources = resolve_params_for_config(config)

        # Then: 4P 확정 hold_days=3 (overfitting_analysis_report.md §2.1 기반)
        assert params.hold_days == 3, "4P config는 hold_days=3이어야 합니다"

    def test_tqqq_config_uses_4p_defaults(self):
        """
        목적: buffer_zone_tqqq config가 4P 기본값을 사용하는지 검증

        Given: buffer_zone_tqqq config (CONFIGS에서 가져옴)
        When: resolve_params_for_config 호출
        Then: FIXED_4P_* 기본값 사용, 출처 "FIXED"
        """
        from qbt.backtest.constants import (
            FIXED_4P_BUY_BUFFER_ZONE_PCT,
            FIXED_4P_HOLD_DAYS,
            FIXED_4P_MA_WINDOW,
            FIXED_4P_SELL_BUFFER_ZONE_PCT,
        )

        # Given
        config = get_config("buffer_zone_tqqq")

        # When
        params, sources = resolve_params_for_config(config)

        # Then
        assert params.ma_window == FIXED_4P_MA_WINDOW
        assert params.buy_buffer_zone_pct == FIXED_4P_BUY_BUFFER_ZONE_PCT
        assert params.sell_buffer_zone_pct == FIXED_4P_SELL_BUFFER_ZONE_PCT
        assert params.hold_days == FIXED_4P_HOLD_DAYS
        assert all(s == "FIXED" for s in sources.values())

    def test_custom_params_applied(self):
        """
        목적: 직접 파라미터를 설정한 config에서 해당 값이 사용되는지 검증

        Given: 커스텀 파라미터가 설정된 config
        When: resolve_params_for_config 호출
        Then: 커스텀 값이 사용됨, 출처 "FIXED"
        """
        # Given
        config = BufferZoneConfig(
            strategy_name="buffer_zone_tqqq",
            display_name="버퍼존 전략 (TQQQ)",
            signal_data_path=Path("signal.csv"),
            trade_data_path=Path("trade.csv"),
            result_dir=Path("results/tqqq"),
            ma_window=50,
            buy_buffer_zone_pct=0.05,
            sell_buffer_zone_pct=0.04,
            hold_days=3,
        )

        # When
        params, sources = resolve_params_for_config(config)

        # Then
        assert params.ma_window == 50
        assert params.buy_buffer_zone_pct == 0.05
        assert params.sell_buffer_zone_pct == 0.04
        assert params.hold_days == 3
        assert all(s == "FIXED" for s in sources.values())


class TestCreateRunner:
    """create_buffer_zone_runner 팩토리 함수 테스트

    목적: runners.create_buffer_zone_runner로 생성한 runner가 올바른 SingleBacktestResult를 반환하는지 검증
    """

    def _make_test_df(self, n_rows: int = 20) -> pd.DataFrame:
        """테스트용 주식 데이터 DataFrame 생성 헬퍼"""
        return pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(n_rows)],
                "Open": [100 + i for i in range(n_rows)],
                "High": [102 + i for i in range(n_rows)],
                "Low": [98 + i for i in range(n_rows)],
                "Close": [100 + i * 0.5 for i in range(n_rows)],
                "Volume": [1000000] * n_rows,
            }
        )

    def test_create_runner_returns_callable(self, tmp_path):
        """
        목적: create_runner가 호출 가능 함수를 반환하는지 검증

        Given: BufferZoneConfig
        When: create_runner(config) 호출
        Then: 반환값이 callable
        """
        # Given
        config = BufferZoneConfig(
            strategy_name="test_callable",
            display_name="테스트",
            signal_data_path=Path("signal.csv"),
            trade_data_path=Path("trade.csv"),
            result_dir=tmp_path / "test",
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
        )

        # When
        runner = runners.create_buffer_zone_runner(config)

        # Then
        assert callable(runner)

    @patch("qbt.backtest.runners.load_stock_data")
    def test_run_single_returns_single_backtest_result(self, mock_load, tmp_path):
        """
        목적: 반환값이 SingleBacktestResult 구조를 충족하는지 검증

        Given: signal==trade인 config, load_stock_data를 mock
        When: create_runner(config)() 실행
        Then: SingleBacktestResult 필드 정합성 확인
        """
        # Given
        test_df = self._make_test_df()
        mock_load.return_value = test_df.copy()

        data_path = Path("same_data.csv")
        config = BufferZoneConfig(
            strategy_name="test_result",
            display_name="테스트 결과",
            signal_data_path=data_path,
            trade_data_path=data_path,
            result_dir=tmp_path / "test_result",
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
        )

        # When
        runner = runners.create_buffer_zone_runner(config)
        result = runner()

        # Then
        assert isinstance(result, SingleBacktestResult)
        assert result.strategy_name == "test_result"
        assert result.display_name == "테스트 결과"
        assert isinstance(result.signal_df, pd.DataFrame)
        assert isinstance(result.equity_df, pd.DataFrame)
        assert isinstance(result.trades_df, pd.DataFrame)
        assert isinstance(result.summary, dict)
        assert isinstance(result.params_json, dict)
        assert "ma_window" in result.params_json
        assert "ma_type" in result.params_json

    @patch("qbt.backtest.runners.load_stock_data")
    def test_signal_equals_trade_no_overlap(self, mock_load, tmp_path):
        """
        목적: signal_path == trade_path 시 extract_overlap_period 미호출 검증

        Given: signal_data_path == trade_data_path인 config
        When: create_runner(config)() 실행
        Then: extract_overlap_period가 호출되지 않음
        """
        # Given
        test_df = self._make_test_df()
        mock_load.return_value = test_df.copy()

        same_path = Path("same_data.csv")
        config = BufferZoneConfig(
            strategy_name="test_no_overlap",
            display_name="테스트",
            signal_data_path=same_path,
            trade_data_path=same_path,
            result_dir=tmp_path / "test",
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
        )

        # When
        with patch("qbt.backtest.runners.extract_overlap_period") as mock_overlap:
            runner = runners.create_buffer_zone_runner(config)
            runner()

            # Then: signal == trade이면 overlap 호출하지 않음
            mock_overlap.assert_not_called()

    @patch("qbt.backtest.runners.extract_overlap_period")
    @patch("qbt.backtest.runners.load_stock_data")
    def test_signal_differs_trade_calls_overlap(self, mock_load, mock_overlap, tmp_path):
        """
        목적: signal_path != trade_path 시 extract_overlap_period 호출 검증

        Given: signal_data_path != trade_data_path인 config
        When: create_runner(config)() 실행
        Then: extract_overlap_period가 호출됨
        """
        # Given
        test_df = self._make_test_df()
        mock_load.return_value = test_df.copy()
        mock_overlap.return_value = (test_df.copy(), test_df.copy())

        config = BufferZoneConfig(
            strategy_name="test_overlap",
            display_name="테스트",
            signal_data_path=Path("signal.csv"),
            trade_data_path=Path("trade.csv"),
            result_dir=tmp_path / "test",
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
        )

        # When
        runner = runners.create_buffer_zone_runner(config)
        runner()

        # Then: signal != trade이면 overlap 호출
        mock_overlap.assert_called_once()

    @patch("qbt.backtest.runners.load_stock_data")
    def test_data_info_contains_paths(self, mock_load, tmp_path):
        """
        목적: data_info에 signal_path, trade_path가 포함되는지 검증

        Given: config에 signal_data_path, trade_data_path 설정
        When: create_runner(config)() 실행
        Then: result.data_info에 signal_path, trade_path 키 존재
        """
        # Given
        test_df = self._make_test_df()
        mock_load.return_value = test_df.copy()

        signal_path = Path("my_signal.csv")
        trade_path = Path("my_signal.csv")  # signal == trade
        config = BufferZoneConfig(
            strategy_name="test_data_info",
            display_name="테스트",
            signal_data_path=signal_path,
            trade_data_path=trade_path,
            result_dir=tmp_path / "test",
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.05,
            hold_days=0,
        )

        # When
        runner = runners.create_buffer_zone_runner(config)
        result = runner()

        # Then
        assert "signal_path" in result.data_info
        assert "trade_path" in result.data_info
        assert result.data_info["signal_path"] == str(signal_path)
        assert result.data_info["trade_path"] == str(trade_path)

    @patch("qbt.backtest.runners.extract_overlap_period")
    @patch("qbt.backtest.runners.load_stock_data")
    def test_tqqq_config_run_single_returns_result(self, mock_load, mock_overlap, tmp_path):
        """
        목적: buffer_zone_tqqq config로 run_single 실행 시 SingleBacktestResult 구조 검증

        Given: buffer_zone_tqqq config (signal != trade, override 고정)
        When: create_runner(config)() 실행
        Then: strategy_name, display_name, data_info 정합성 확인
        """
        # Given
        test_df = self._make_test_df()
        mock_load.return_value = test_df.copy()
        mock_overlap.return_value = (test_df.copy(), test_df.copy())

        tqqq_config = get_config("buffer_zone_tqqq")
        config = BufferZoneConfig(
            strategy_name=tqqq_config.strategy_name,
            display_name=tqqq_config.display_name,
            signal_data_path=tqqq_config.signal_data_path,
            trade_data_path=tqqq_config.trade_data_path,
            result_dir=tmp_path / "buffer_zone_tqqq",
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
        )

        # When
        runner = runners.create_buffer_zone_runner(config)
        result = runner()

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
        assert isinstance(result.data_info, dict)
        assert "signal_path" in result.data_info
        assert "trade_path" in result.data_info

    @patch("qbt.backtest.runners.load_stock_data")
    def test_qqq_config_run_single_returns_result(self, mock_load, tmp_path):
        """
        목적: buffer_zone_qqq config로 run_single 실행 시 SingleBacktestResult 구조 검증

        Given: buffer_zone_qqq config (signal == trade, overlap 불필요)
        When: create_runner(config)() 실행
        Then: strategy_name, display_name, data_info 정합성 확인
        """
        # Given
        test_df = self._make_test_df()
        mock_load.return_value = test_df.copy()

        qqq_config = get_config("buffer_zone_qqq")
        config = BufferZoneConfig(
            strategy_name=qqq_config.strategy_name,
            display_name=qqq_config.display_name,
            signal_data_path=qqq_config.signal_data_path,
            trade_data_path=qqq_config.trade_data_path,
            result_dir=tmp_path / "buffer_zone_qqq",
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
        )

        # When
        runner = runners.create_buffer_zone_runner(config)
        result = runner()

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
        assert isinstance(result.data_info, dict)
        assert "signal_path" in result.data_info
        assert "trade_path" in result.data_info
