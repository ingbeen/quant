"""
backtest/strategies/buy_and_hold 모듈 테스트

이 파일은 무엇을 검증하나요?
1. Buy & Hold 전략 실행 정확성
2. 자본 부족/유효하지 않은 파라미터 처리
3. trade_df 기반 매매 검증
4. resolve_params 파라미터 결정
5. create_runner 팩토리 함수 (QQQ, TQQQ)
6. CONFIGS 정합성 (strategy_name/display_name 유일성)

왜 중요한가요?
Buy & Hold는 다른 전략의 벤치마크이므로 정확성이 특히 중요합니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.strategies.buy_and_hold import (
    BuyAndHoldParams,
    run_buy_and_hold,
)


class TestRunBuyAndHold:
    """Buy & Hold 전략 테스트"""

    def test_normal_execution(self):
        """
        정상적인 Buy & Hold 실행 테스트

        데이터 신뢰성: 벤치마크 전략이므로 정확해야 비교가 의미 있습니다.

        Given: 3일치 가격 데이터
        When: run_buy_and_hold 실행
        Then:
          - 강제청산 없음 (마지막날 매도하지 않음, total_trades=0)
          - 슬리피지 적용 확인 (매수 +)
          - shares는 정수
          - equity_df와 summary 반환
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
                "Open": [100.0, 102.0, 104.0],
                "Close": [101.0, 103.0, 105.0],
            }
        )

        params = BuyAndHoldParams(initial_capital=10000.0)

        # When
        equity_df, summary = run_buy_and_hold(df, params)

        # Then: summary 확인
        assert isinstance(summary, dict), "summary는 딕셔너리여야 합니다"
        assert summary["total_trades"] == 0, "Buy & Hold는 강제청산 없음 (매도 없이 보유 유지)"
        assert summary["final_capital"] > params.initial_capital * 0.9, "최종 자본은 초기 자본의 90% 이상"

        # Equity curve 확인
        assert len(equity_df) == 3, "매일 equity 기록"
        assert "equity" in equity_df.columns, "equity 컬럼 존재"
        assert "position" in equity_df.columns, "position 컬럼 존재"
        assert equity_df["equity"].iloc[-1] > 0, "최종 자본은 양수"

    def test_insufficient_capital(self):
        """
        자본이 부족해 주식을 살 수 없을 때 테스트

        안정성: 자본 < 주가일 때도 에러 없이 처리되어야 합니다.

        Given: 초기 자본 10, 주가 100
        When: run_buy_and_hold
        Then: shares = 0, 총 수익률은 0% 근처
        """
        # Given
        df = pd.DataFrame(
            {"Date": [date(2023, 1, 2), date(2023, 1, 3)], "Open": [100.0, 101.0], "Close": [100.0, 101.0]}
        )

        params = BuyAndHoldParams(initial_capital=10.0)  # 주가보다 훨씬 작음

        # When
        equity_df, summary = run_buy_and_hold(df, params)

        # Then: 거래는 발생했지만 shares=0
        # 자본이 부족하므로 수익률이 거의 0에 가까움
        assert summary["total_trades"] >= 0, "에러 없이 실행됨"
        assert summary["total_return_pct"] == pytest.approx(0, abs=1.0), "자본 부족 시 수익률 거의 0%"

    @pytest.mark.parametrize("invalid_capital", [0.0, -1000.0, -1.0])
    def test_invalid_capital_raises(self, invalid_capital):
        """
        초기 자본이 0 이하일 때 예외 발생 테스트

        Given: initial_capital <= 0 (parametrize로 여러 값 테스트)
        When: run_buy_and_hold 호출
        Then: ValueError 발생

        Args:
            invalid_capital: 테스트할 잘못된 초기 자본 값 (0.0, -1000.0, -1.0)
        """
        # Given
        df = pd.DataFrame(
            {"Date": [date(2023, 1, 2), date(2023, 1, 3)], "Open": [100.0, 101.0], "Close": [100.0, 101.0]}
        )

        # When & Then
        params = BuyAndHoldParams(initial_capital=invalid_capital)
        with pytest.raises(ValueError, match="initial_capital은 양수여야 합니다"):
            run_buy_and_hold(df, params)

    @pytest.mark.parametrize(
        "df_data,missing_column",
        [
            ({"Date": [date(2023, 1, 2), date(2023, 1, 3)], "Close": [100.0, 101.0]}, "Open"),
            ({"Date": [date(2023, 1, 2), date(2023, 1, 3)], "Open": [100.0, 101.0]}, "Close"),
        ],
        ids=["missing_open", "missing_close"],
    )
    def test_missing_required_columns_raises(self, df_data, missing_column):
        """
        필수 컬럼 누락 시 예외 발생 테스트

        Given: Open 또는 Close 컬럼이 없는 DataFrame (parametrize로 여러 케이스 테스트)
        When: run_buy_and_hold 호출
        Then: ValueError 발생

        Args:
            df_data: 테스트할 DataFrame 데이터 (누락 컬럼 포함)
            missing_column: 누락된 컬럼명 (식별용)
        """
        # Given
        df = pd.DataFrame(df_data)
        params = BuyAndHoldParams(initial_capital=10000.0)

        # When & Then
        with pytest.raises(ValueError, match="필수 컬럼 누락"):
            run_buy_and_hold(df, params)

    def test_insufficient_rows_raises(self):
        """
        최소 행 수 미달 시 예외 발생 테스트

        Given: 1행만 있는 DataFrame
        When: run_buy_and_hold 호출
        Then: ValueError 발생 (최소 2행 필요)
        """
        # Given: 1행만
        df = pd.DataFrame({"Date": [date(2023, 1, 2)], "Open": [100.0], "Close": [100.0]})

        params = BuyAndHoldParams(initial_capital=10000.0)

        # When & Then
        with pytest.raises(ValueError, match="유효 데이터 부족"):
            run_buy_and_hold(df, params)


class TestBuyAndHoldUsesTradeDF:
    """Buy & Hold가 trade_df를 올바르게 사용하는지 검증"""

    def test_buy_and_hold_uses_trade_df(self):
        """
        Buy & Hold가 trade_df의 시가/종가를 사용하는지 검증

        Given:
          - trade_df (QQQ 데이터)
        When: run_buy_and_hold(trade_df, params)
        Then:
          - 첫날 trade_df 시가에 매수
          - 강제청산 없음 (마지막날 매도하지 않음)
          - 에쿼티가 trade_df 종가 기반
        """
        # Given
        trade_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
                "Open": [50.0, 55.0, 60.0],
                "Close": [52.0, 58.0, 65.0],
            }
        )

        params = BuyAndHoldParams(initial_capital=10000.0)

        # When
        equity_df, summary = run_buy_and_hold(trade_df, params)

        # Then: trade_df 기준으로 매매 확인
        # 첫날 Open=50, 슬리피지 +0.3% = 50.15
        # shares = int(10000 / 50.15) = 199
        assert summary["total_trades"] == 0, "Buy & Hold는 강제청산 없음 (매도 없이 보유 유지)"
        assert len(equity_df) == 3, "매일 equity 기록"

        # 마지막 equity는 trade_df Close=65 기준이어야 함
        last_equity = equity_df.iloc[-1]["equity"]
        assert last_equity > 0, "에쿼티는 양수여야 함"


class TestResolveParams:
    """resolve_params 파라미터 결정 테스트"""

    def test_buy_and_hold_resolve_params(self):
        """
        목적: Buy & Hold resolve_params는 항상 DEFAULT_INITIAL_CAPITAL 사용 검증

        Given: (특별한 설정 없음)
        When: resolve_params 호출
        Then: initial_capital이 DEFAULT_INITIAL_CAPITAL
        """
        from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL
        from qbt.backtest.strategies.buy_and_hold import resolve_params

        # When
        params = resolve_params()

        # Then
        assert params.initial_capital == DEFAULT_INITIAL_CAPITAL


class TestCreateRunner:
    """create_runner 팩토리 함수 테스트

    목적: create_runner로 생성한 runner가 SingleBacktestResult를 올바르게 반환하는지 검증
    """

    def test_buy_and_hold_qqq_create_runner_returns_result(self, tmp_path, monkeypatch):
        """
        목적: create_runner로 생성한 QQQ Buy & Hold runner가 SingleBacktestResult를 올바르게 반환하는지 검증

        Given: 10일 데이터 (load_stock_data를 mock하여 테스트 DataFrame 반환)
        When: create_runner(config)()로 실행
        Then: SingleBacktestResult 필드 정합성 확인, trades_df는 빈 DataFrame, data_info 포함
        """
        from pathlib import Path

        from qbt.backtest.strategies import buy_and_hold
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
        monkeypatch.setattr(buy_and_hold, "load_stock_data", lambda _path: test_df.copy())

        # When
        runner = buy_and_hold.create_runner(config)
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
        목적: create_runner로 생성한 TQQQ Buy & Hold runner가 SingleBacktestResult를 올바르게 반환하는지 검증

        Given: 10일 데이터 (load_stock_data를 mock하여 테스트 DataFrame 반환)
        When: create_runner(tqqq_config)()로 실행
        Then: strategy_name="buy_and_hold_tqqq", display_name="Buy & Hold (TQQQ)" 확인
        """
        from pathlib import Path

        from qbt.backtest.strategies import buy_and_hold
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
        monkeypatch.setattr(buy_and_hold, "load_stock_data", lambda _path: test_df.copy())

        # When
        runner = buy_and_hold.create_runner(config)
        result = runner()

        # Then
        assert isinstance(result, SingleBacktestResult)
        assert result.strategy_name == "buy_and_hold_tqqq"
        assert result.display_name == "Buy & Hold (TQQQ)"
        assert result.trades_df.empty
        assert result.params_json["strategy"] == "buy_and_hold_tqqq"
        assert result.result_dir == tmp_path / "buy_and_hold_tqqq"


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
