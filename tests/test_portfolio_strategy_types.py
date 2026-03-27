"""포트폴리오 전략 타입 동작 테스트

strategy_id="buy_and_hold" vs "buffer_zone" 동작 계약을 검증한다.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from qbt.backtest.engines.portfolio_engine import run_portfolio_backtest
from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME

# ============================================================================
# 공통 헬퍼
# ============================================================================


def _make_flat_price_df(n_rows: int = 20, price: float = 100.0) -> pd.DataFrame:
    """가격이 고정된 합성 주식 데이터를 생성한다.

    always_invested 테스트 목적:
    - buy_buffer=0.03 → upper_band = MA * 1.03 ≈ 103
    - price=100 → upper_band(103)을 절대 돌파하지 않음 → 버퍼존 매수 신호 없음
    - always_invested=True라면 신호 없이도 즉시 매수 가능
    """
    start = date(2024, 1, 2)
    dates: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)

    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [price - 0.1] * n_rows,
            COL_HIGH: [price + 0.1] * n_rows,
            COL_LOW: [price - 0.1] * n_rows,
            COL_CLOSE: [price] * n_rows,
            COL_VOLUME: [1_000_000] * n_rows,
        }
    )


def _make_sell_signal_df(n_rows: int = 20, initial_price: float = 100.0, drop_price: float = 80.0) -> pd.DataFrame:
    """초반 고가→후반 저가(매도 신호 구간)를 포함한 합성 데이터를 생성한다.

    - 처음 5행: initial_price (MA ≈ initial_price, lower_band = initial_price * 0.95 = 95)
    - 나머지: drop_price = 80 (lower_band 95 하향 돌파 → 버퍼존 매도 신호)
    """
    start = date(2024, 1, 2)
    dates: list[date] = []
    current = start
    for _ in range(n_rows):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        dates.append(current)
        current += timedelta(days=1)

    closes = [initial_price] * 5 + [drop_price] * (n_rows - 5)
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [c - 0.1 for c in closes],
            COL_HIGH: [c + 0.1 for c in closes],
            COL_LOW: [c - 0.1 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * n_rows,
        }
    )


# ============================================================================
# 테스트 클래스
# ============================================================================


class TestStrategyTypeBehavior:
    """strategy_id 동작 통합 테스트.

    검증 정책:
    1. strategy_id="buy_and_hold": 버퍼존 매수 신호 없이도 day 1에 즉시 매수
    2. strategy_id="buy_and_hold": 매도 신호 발생 시에도 포지션 유지
    3. strategy_id="buffer_zone"(기본값): 매수 신호 없으면 절대 매수하지 않음
    4. AssetSlotConfig 기본값: strategy_id="buffer_zone"
    """

    def test_buy_and_hold_buys_immediately(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: strategy_id="buy_and_hold" 자산이 버퍼존 매수 신호 없이도 즉시 매수됨을 검증.

        Given:
            - 가격 100 고정 → upper_band(103) 돌파 없음 → 버퍼존 매수 신호 없음
            - strategy_id="buy_and_hold" 자산 슬롯 (target_weight=1.0)

        When: run_portfolio_backtest() 실행

        Then:
            - 마지막 날 {asset_id}_value > 0 (즉시 매수 후 포지션 유지)
        """
        # Given: 가격 100 고정 (upper_band=103 돌파 없음 → 버퍼존 신호 없음)
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_always.csv", df)

        config_true = PortfolioConfig(
            experiment_name="test_always_true",
            display_name="Test Always True",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_a",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_id="buy_and_hold",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "always_true",
        )

        # When
        result = run_portfolio_backtest(config_true)

        # Then: 마지막 날 포지션 보유 (매수 신호 없어도 항상 투자)
        equity_df = result.equity_df
        last_value = float(equity_df["asset_a_value"].iloc[-1])
        assert last_value > 0, f"strategy_id='buy_and_hold' 자산은 마지막 날 포지션을 보유해야 함, 실제: {last_value}"

    def test_buffer_zone_does_not_buy_without_signal(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: strategy_id="buffer_zone"(기본값)이면 버퍼존 신호 없이 절대 매수하지 않음을 검증.

        Given:
            - 가격 100 고정 → upper_band(103) 돌파 없음 → 버퍼존 매수 신호 없음
            - strategy_id="buffer_zone" (기본 버퍼존 전략)

        When: run_portfolio_backtest() 실행

        Then:
            - 전체 기간 {asset_id}_value = 0 (매수 신호 없어서 포지션 없음)
            - trades_df가 비어있음
        """
        # Given: 동일 가격 데이터, strategy_id="buffer_zone"(기본값)
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_normal.csv", df)

        config_false = PortfolioConfig(
            experiment_name="test_always_false",
            display_name="Test Always False",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_b",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_id="buffer_zone",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "always_false",
        )

        # When
        result = run_portfolio_backtest(config_false)

        # Then: 전체 기간 포지션 없음
        equity_df = result.equity_df
        assert (equity_df["asset_b_value"] == 0).all(), "strategy_id='buffer_zone' 자산은 매수 신호 없이 포지션을 가지면 안 됨"
        assert result.trades_df.empty, "strategy_id='buffer_zone' 자산은 신호 없으면 거래가 없어야 함"

    def test_buy_and_hold_does_not_sell_on_signal(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: strategy_id="buy_and_hold" 자산이 매도 신호(하단 밴드 하향 돌파)에도 매도하지 않음을 검증.

        Given:
            - 처음 5행: 가격 100 (MA ≈ 100, lower_band = 95)
            - 이후 15행: 가격 80 (lower_band 95 하향 돌파 → 버퍼존 매도 신호 발생)
            - strategy_id="buy_and_hold"

        When: run_portfolio_backtest() 실행

        Then:
            - 마지막 날 {asset_id}_value > 0 (매도하지 않고 포지션 유지)
            - trades_df가 비어있음 (완료된 매도 거래 없음)
        """
        # Given: 초반 100 → 후반 80 (매도 신호 발생 구간)
        df = _make_sell_signal_df(n_rows=20, initial_price=100.0, drop_price=80.0)
        csv_path = create_csv_file("asset_sell_signal.csv", df)

        config = PortfolioConfig(
            experiment_name="test_no_sell",
            display_name="Test No Sell",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_c",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_id="buy_and_hold",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "no_sell",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then: 마지막 날 포지션 보유 (매도 신호 무시)
        equity_df = result.equity_df
        last_value = float(equity_df["asset_c_value"].iloc[-1])
        assert last_value > 0, f"strategy_id='buy_and_hold' 자산은 매도 신호에도 포지션을 유지해야 함, 실제: {last_value}"

        # 완료된 거래(entry + exit) 없음
        assert result.trades_df.empty, (
            f"strategy_id='buy_and_hold' 자산은 매도 기록이 없어야 함, " f"실제 거래 수: {len(result.trades_df)}"
        )

    def test_strategy_type_default_is_buffer_zone(self, tmp_path: Path) -> None:
        """
        목적: AssetSlotConfig.strategy_id 기본값이 "buffer_zone"임을 검증.

        Given: strategy_id 파라미터 없이 AssetSlotConfig 생성
        When:  AssetSlotConfig 인스턴스 생성
        Then:  strategy_id == "buffer_zone"
        """
        # Given/When: strategy_id 명시 없이 생성
        slot = AssetSlotConfig(
            asset_id="test",
            signal_data_path=tmp_path / "dummy.csv",
            trade_data_path=tmp_path / "dummy.csv",
            target_weight=0.50,
        )

        # Then: 기본값 "buffer_zone"
        assert (
            slot.strategy_id == "buffer_zone"
        ), f"AssetSlotConfig.strategy_id 기본값은 'buffer_zone'이어야 함, 실제: {slot.strategy_id}"

    def test_params_json_includes_strategy_type_flag(self, tmp_path: Path, create_csv_file):  # type: ignore[no-untyped-def]
        """
        목적: params_json에 strategy_id 필드가 포함됨을 검증.

        Given: strategy_id="buy_and_hold" 자산을 포함한 포트폴리오 config
        When:  run_portfolio_backtest() 실행
        Then:  result.params_json["assets"][0]["strategy_id"] == "buy_and_hold"
        """
        # Given
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_json.csv", df)

        config = PortfolioConfig(
            experiment_name="test_params_json",
            display_name="Test Params JSON",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_d",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_id="buy_and_hold",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "params_json",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then: params_json에 strategy_id 포함
        assets_json = result.params_json.get("assets", [])
        assert len(assets_json) == 1, "자산이 1개이어야 함"
        assert "strategy_id" in assets_json[0], "params_json[assets][0]에 strategy_id 키가 있어야 함"
        assert assets_json[0]["strategy_id"] == "buy_and_hold", (
            f"strategy_id='buy_and_hold'가 params_json에 반영되어야 함, " f"실제: {assets_json[0].get('strategy_id')}"
        )


class TestStrategyType:
    """strategy_id 기능 계약 테스트.

    핵심 계약:
    1. AssetSlotConfig.strategy_id 기본값 == "buffer_zone"
    2. strategy_id="buy_and_hold": 버퍼존 신호 없이 즉시 매수
    3. strategy_id="buy_and_hold": 매도 신호에도 포지션 유지
    4. params_json에 strategy_id 키 포함
    """

    def test_strategy_type_default_is_buffer_zone(self) -> None:
        """
        목적: AssetSlotConfig.strategy_id 기본값이 "buffer_zone"임을 검증.

        Given: strategy_id 명시 없이 AssetSlotConfig 생성
        When:  .strategy_id 속성 조회
        Then:  "buffer_zone"
        """
        # Given/When
        slot = AssetSlotConfig(
            asset_id="test",
            signal_data_path=Path("dummy"),
            trade_data_path=Path("dummy"),
            target_weight=0.50,
        )

        # Then
        assert slot.strategy_id == "buffer_zone"

    def test_strategy_type_buy_and_hold_buys_immediately(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: strategy_id="buy_and_hold" 자산이 버퍼존 신호 없이 즉시 매수됨을 검증.

        Given: 가격 100 고정 → upper_band(103) 돌파 없음 → 버퍼존 매수 신호 없음
               strategy_id="buy_and_hold"
        When:  run_portfolio_backtest() 실행
        Then:  마지막 날 value > 0 (즉시 매수 후 포지션 유지)
        """
        # Given
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_bnh.csv", df)

        config = PortfolioConfig(
            experiment_name="test_bnh",
            display_name="Test B&H",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_bnh",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_id="buy_and_hold",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "bnh",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then
        last_value = float(result.equity_df["asset_bnh_value"].iloc[-1])
        assert last_value > 0, f"strategy_id='buy_and_hold' 자산은 즉시 매수되어야 함, 실제: {last_value}"

    def test_strategy_type_buy_and_hold_ignores_sell_signal(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: strategy_id="buy_and_hold" 자산이 매도 신호에도 포지션 유지됨을 검증.

        Given: 처음 5행 100 → 이후 80 (매도 신호 발생)
               strategy_id="buy_and_hold"
        When:  run_portfolio_backtest() 실행
        Then:  마지막 날 value > 0 (매도 신호 무시)
               trades_df 비어있음 (완료된 매도 거래 없음)
        """
        # Given
        df = _make_sell_signal_df(n_rows=20, initial_price=100.0, drop_price=80.0)
        csv_path = create_csv_file("asset_bnh_sell.csv", df)

        config = PortfolioConfig(
            experiment_name="test_bnh_sell",
            display_name="Test B&H Sell",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_bnh_s",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_id="buy_and_hold",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "bnh_sell",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then
        last_value = float(result.equity_df["asset_bnh_s_value"].iloc[-1])
        assert last_value > 0, "strategy_id='buy_and_hold' 자산은 매도 신호에도 포지션을 유지해야 함"
        assert result.trades_df.empty, "strategy_id='buy_and_hold' 자산은 완료된 매도 기록이 없어야 함"

    def test_params_json_includes_strategy_type(
        self, tmp_path: Path, create_csv_file  # type: ignore[no-untyped-def]
    ) -> None:
        """
        목적: params_json에 strategy_id 필드가 포함됨을 검증.

        Given: strategy_id="buy_and_hold" 자산 포함 config
        When:  run_portfolio_backtest() 실행
        Then:  result.params_json["assets"][0]["strategy_id"] == "buy_and_hold"
        """
        # Given
        df = _make_flat_price_df(n_rows=20, price=100.0)
        csv_path = create_csv_file("asset_pj.csv", df)

        config = PortfolioConfig(
            experiment_name="test_params_json_st",
            display_name="Test Params JSON ST",
            asset_slots=(
                AssetSlotConfig(
                    asset_id="asset_pj",
                    signal_data_path=csv_path,
                    trade_data_path=csv_path,
                    target_weight=1.0,
                    strategy_id="buy_and_hold",
                ),
            ),
            total_capital=1_000_000.0,
            result_dir=tmp_path / "params_json_st",
        )

        # When
        result = run_portfolio_backtest(config)

        # Then
        assets_json = result.params_json.get("assets", [])
        assert len(assets_json) == 1
        assert "strategy_id" in assets_json[0], "params_json[assets][0]에 strategy_id 키가 있어야 함"
        assert assets_json[0]["strategy_id"] == "buy_and_hold"
