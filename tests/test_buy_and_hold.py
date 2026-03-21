"""
backtest/strategies/buy_and_hold 모듈 테스트

이 파일은 무엇을 검증하나요?
1. create_runner 팩토리 함수 (QQQ, TQQQ) — runners.create_buy_and_hold_runner 기반
2. CONFIGS 정합성 (strategy_name/display_name 유일성)

왜 중요한가요?
Buy & Hold는 다른 전략의 벤치마크이므로 정확성이 특히 중요합니다.
엔진 기반으로 실행하므로 signal_df/equity_df/trades_df/summary 구조를 검증합니다.
"""

from datetime import date

import pandas as pd

from qbt.backtest import runners


class TestCreateRunner:
    """create_runner 팩토리 함수 테스트

    목적: runners.create_buy_and_hold_runner로 생성한 runner가 SingleBacktestResult를 올바르게 반환하는지 검증
    """

    def test_buy_and_hold_qqq_create_runner_returns_result(self, tmp_path, monkeypatch):
        """
        목적: create_buy_and_hold_runner로 생성한 QQQ Buy & Hold runner가 SingleBacktestResult를 올바르게 반환하는지 검증

        Given: 10일 데이터 (load_stock_data를 mock하여 테스트 DataFrame 반환)
        When: runners.create_buy_and_hold_runner(config)()로 실행
        Then: SingleBacktestResult 필드 정합성 확인, trades_df는 빈 DataFrame, data_info 포함
        """
        from pathlib import Path

        from qbt.backtest.strategies.buy_and_hold import BuyAndHoldConfig
        from qbt.backtest.types import SingleBacktestResult

        # Given: 테스트용 DataFrame
        test_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i for i in range(10)],
                "High": [102 + i for i in range(10)],
                "Low": [98 + i for i in range(10)],
                "Close": [101 + i for i in range(10)],
                "Volume": [1000000] * 10,
            }
        )

        # 테스트용 config
        config = BuyAndHoldConfig(
            strategy_name="buy_and_hold_qqq",
            display_name="Buy & Hold (QQQ)",
            trade_data_path=Path("dummy_qqq.csv"),
            result_dir=tmp_path / "buy_and_hold_qqq",
        )

        # load_stock_data를 mock하여 테스트 DataFrame 반환
        monkeypatch.setattr(runners, "load_stock_data", lambda _path: test_df.copy())

        # When
        runner = runners.create_buy_and_hold_runner(config)
        result = runner()

        # Then
        assert isinstance(result, SingleBacktestResult)
        assert result.strategy_name == "buy_and_hold_qqq"
        assert result.display_name == "Buy & Hold (QQQ)"
        assert isinstance(result.signal_df, pd.DataFrame)
        assert isinstance(result.equity_df, pd.DataFrame)
        assert result.trades_df.empty
        assert isinstance(result.summary, dict)
        assert "strategy" in result.params_json
        assert result.params_json["strategy"] == "buy_and_hold_qqq"
        assert result.result_dir == tmp_path / "buy_and_hold_qqq"
        assert isinstance(result.data_info, dict)
        assert "trade_path" in result.data_info

    def test_buy_and_hold_tqqq_create_runner_returns_result(self, tmp_path, monkeypatch):
        """
        목적: create_buy_and_hold_runner로 생성한 TQQQ Buy & Hold runner가 SingleBacktestResult를 올바르게 반환하는지 검증

        Given: 10일 데이터 (load_stock_data를 mock하여 테스트 DataFrame 반환)
        When: runners.create_buy_and_hold_runner(tqqq_config)()로 실행
        Then: strategy_name="buy_and_hold_tqqq", display_name="Buy & Hold (TQQQ)" 확인
        """
        from pathlib import Path

        from qbt.backtest.strategies.buy_and_hold import BuyAndHoldConfig
        from qbt.backtest.types import SingleBacktestResult

        # Given: 테스트용 DataFrame
        test_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [50 + i for i in range(10)],
                "High": [52 + i for i in range(10)],
                "Low": [48 + i for i in range(10)],
                "Close": [51 + i for i in range(10)],
                "Volume": [2000000] * 10,
            }
        )

        # 테스트용 TQQQ config
        config = BuyAndHoldConfig(
            strategy_name="buy_and_hold_tqqq",
            display_name="Buy & Hold (TQQQ)",
            trade_data_path=Path("dummy_tqqq.csv"),
            result_dir=tmp_path / "buy_and_hold_tqqq",
        )

        # load_stock_data를 mock하여 테스트 DataFrame 반환
        monkeypatch.setattr(runners, "load_stock_data", lambda _path: test_df.copy())

        # When
        runner = runners.create_buy_and_hold_runner(config)
        result = runner()

        # Then
        assert isinstance(result, SingleBacktestResult)
        assert result.strategy_name == "buy_and_hold_tqqq"
        assert result.display_name == "Buy & Hold (TQQQ)"
        assert result.trades_df.empty
        assert result.params_json["strategy"] == "buy_and_hold_tqqq"
        assert result.result_dir == tmp_path / "buy_and_hold_tqqq"

    def test_buy_and_hold_runner_open_position_present(self, tmp_path, monkeypatch):
        """
        목적: B&H runner 실행 시 포지션을 항상 보유하므로 summary["open_position"]이 존재하는지 검증

        Given: 10일 데이터
        When: runners.create_buy_and_hold_runner(config)() 실행
        Then: summary["open_position"] 존재 (entry_date, entry_price, shares)
        """
        from pathlib import Path

        from qbt.backtest.strategies.buy_and_hold import BuyAndHoldConfig

        test_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i for i in range(10)],
                "High": [102 + i for i in range(10)],
                "Low": [98 + i for i in range(10)],
                "Close": [101 + i for i in range(10)],
                "Volume": [1000000] * 10,
            }
        )
        config = BuyAndHoldConfig(
            strategy_name="buy_and_hold_qqq",
            display_name="Buy & Hold (QQQ)",
            trade_data_path=Path("dummy.csv"),
            result_dir=tmp_path / "bh",
        )
        monkeypatch.setattr(runners, "load_stock_data", lambda _path: test_df.copy())

        result = runners.create_buy_and_hold_runner(config)()

        from typing import cast

        from qbt.backtest.types import OpenPositionDict

        assert "open_position" in result.summary, "B&H는 항상 open_position이 있어야 함"
        open_pos = cast(OpenPositionDict, result.summary["open_position"])
        assert open_pos["shares"] > 0, "보유 수량은 양수"

    def test_buy_and_hold_runner_trades_df_empty(self, tmp_path, monkeypatch):
        """
        목적: B&H runner는 매도 신호가 없으므로 trades_df가 항상 비어있음을 검증

        Given: 10일 데이터
        When: runners.create_buy_and_hold_runner(config)() 실행
        Then: result.trades_df.empty == True
        """
        from pathlib import Path

        from qbt.backtest.strategies.buy_and_hold import BuyAndHoldConfig

        test_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i for i in range(10)],
                "High": [102 + i for i in range(10)],
                "Low": [98 + i for i in range(10)],
                "Close": [101 + i for i in range(10)],
                "Volume": [1000000] * 10,
            }
        )
        config = BuyAndHoldConfig(
            strategy_name="buy_and_hold_qqq",
            display_name="Buy & Hold (QQQ)",
            trade_data_path=Path("dummy.csv"),
            result_dir=tmp_path / "bh",
        )
        monkeypatch.setattr(runners, "load_stock_data", lambda _path: test_df.copy())

        result = runners.create_buy_and_hold_runner(config)()

        assert result.trades_df.empty, "B&H는 매도가 없으므로 trades_df가 비어있어야 함"

    def test_buy_and_hold_runner_signal_df_has_ohlc_no_ma(self, tmp_path, monkeypatch):
        """
        목적: B&H runner의 signal_df에 OHLC 컬럼만 있고 ma_* 컬럼이 없음을 검증

        Given: 10일 데이터
        When: runners.create_buy_and_hold_runner(config)() 실행
        Then: signal_df에 "Date", "Open", "High", "Low", "Close" 존재, ma_* 없음
        """
        from pathlib import Path

        from qbt.backtest.strategies.buy_and_hold import BuyAndHoldConfig

        test_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i for i in range(10)],
                "High": [102 + i for i in range(10)],
                "Low": [98 + i for i in range(10)],
                "Close": [101 + i for i in range(10)],
                "Volume": [1000000] * 10,
            }
        )
        config = BuyAndHoldConfig(
            strategy_name="buy_and_hold_qqq",
            display_name="Buy & Hold (QQQ)",
            trade_data_path=Path("dummy.csv"),
            result_dir=tmp_path / "bh",
        )
        monkeypatch.setattr(runners, "load_stock_data", lambda _path: test_df.copy())

        result = runners.create_buy_and_hold_runner(config)()

        sig_cols = set(result.signal_df.columns)
        assert "Date" in sig_cols, "signal_df에 Date 컬럼이 있어야 함"
        assert "Open" in sig_cols, "signal_df에 Open 컬럼이 있어야 함"
        assert "Close" in sig_cols, "signal_df에 Close 컬럼이 있어야 함"
        ma_cols = [c for c in sig_cols if c.startswith("ma_")]
        assert len(ma_cols) == 0, f"signal_df에 ma_* 컬럼이 없어야 함. 실제: {ma_cols}"


class TestBuyAndHoldConfigs:
    """Buy & Hold CONFIGS 정합성 테스트"""

    def test_configs_has_multiple_entries(self):
        """
        목적: CONFIGS에 최소 2개 이상의 설정이 존재하는지 검증

        Given: buy_and_hold.CONFIGS
        When: 길이 확인
        Then: 최소 2개 이상
        """
        from qbt.backtest.strategies.buy_and_hold import CONFIGS

        assert len(CONFIGS) >= 2, f"CONFIGS에 최소 2개 항목이 필요합니다. 실제: {len(CONFIGS)}"

    def test_configs_strategy_names_unique(self):
        """
        목적: CONFIGS 내 strategy_name이 모두 유일한지 검증

        Given: buy_and_hold.CONFIGS
        When: strategy_name 중복 확인
        Then: 중복 없음
        """
        from qbt.backtest.strategies.buy_and_hold import CONFIGS

        names = [c.strategy_name for c in CONFIGS]
        assert len(names) == len(set(names)), f"strategy_name 중복 발견: {names}"

    def test_configs_display_names_unique(self):
        """
        목적: CONFIGS 내 display_name이 모두 유일한지 검증

        Given: buy_and_hold.CONFIGS
        When: display_name 중복 확인
        Then: 중복 없음
        """
        from qbt.backtest.strategies.buy_and_hold import CONFIGS

        display_names = [c.display_name for c in CONFIGS]
        assert len(display_names) == len(set(display_names)), f"display_name 중복 발견: {display_names}"

    def test_configs_contains_qqq_and_tqqq(self):
        """
        목적: CONFIGS에 QQQ와 TQQQ 설정이 모두 존재하는지 검증

        Given: buy_and_hold.CONFIGS
        When: strategy_name 확인
        Then: buy_and_hold_qqq와 buy_and_hold_tqqq 모두 포함
        """
        from qbt.backtest.strategies.buy_and_hold import CONFIGS

        names = {c.strategy_name for c in CONFIGS}
        assert "buy_and_hold_qqq" in names, "QQQ 설정이 CONFIGS에 포함되어야 합니다"
        assert "buy_and_hold_tqqq" in names, "TQQQ 설정이 CONFIGS에 포함되어야 합니다"

    def test_configs_contains_cross_asset_tickers(self):
        """
        목적: CONFIGS에 cross-asset 6개 자산의 B&H 설정이 모두 존재하는지 검증

        Given: buy_and_hold.CONFIGS
        When: strategy_name 확인
        Then: SPY, IWM, EFA, EEM, GLD, TLT 모두 포함
        """
        from qbt.backtest.strategies.buy_and_hold import CONFIGS

        names = {c.strategy_name for c in CONFIGS}
        expected = [
            "buy_and_hold_spy",
            "buy_and_hold_iwm",
            "buy_and_hold_efa",
            "buy_and_hold_eem",
            "buy_and_hold_gld",
            "buy_and_hold_tlt",
        ]
        for name in expected:
            assert name in names, f"{name} 설정이 CONFIGS에 포함되어야 합니다"

    def test_configs_total_count(self):
        """
        목적: CONFIGS의 전체 항목 수가 8개인지 검증 (QQQ + TQQQ + 6개 cross-asset)

        Given: buy_and_hold.CONFIGS
        When: 길이 확인
        Then: 8개
        """
        from qbt.backtest.strategies.buy_and_hold import CONFIGS

        assert len(CONFIGS) == 8, f"CONFIGS는 8개여야 합니다 (QQQ+TQQQ+6개 cross-asset). 실제: {len(CONFIGS)}"
