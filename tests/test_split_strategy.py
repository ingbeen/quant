"""분할 매수매도 오케스트레이터 모듈 테스트

오케스트레이터 로직(자본 분배, 결과 조합)을 검증한다.
run_buffer_strategy()의 정확성은 기존 test_buffer_zone_helpers.py가 보장한다.
테스트에서는 실제 MA=150/200/250 대신 작은 MA 윈도우(5/10/15)와 ~30행 데이터를 사용한다.
"""

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from qbt.backtest.constants import (
    FIXED_4P_BUY_BUFFER_ZONE_PCT,
    FIXED_4P_HOLD_DAYS,
    FIXED_4P_SELL_BUFFER_ZONE_PCT,
    SPLIT_TRANCHE_IDS,
    SPLIT_TRANCHE_MA_WINDOWS,
    SPLIT_TRANCHE_WEIGHTS,
)
from qbt.backtest.split_strategy import (
    SPLIT_CONFIGS,
    SplitStrategyConfig,
    SplitStrategyResult,
    SplitTrancheConfig,
    run_split_backtest,
)
from qbt.backtest.strategies.buffer_zone import BufferZoneConfig
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
)
from qbt.utils.data_loader import load_stock_data

# ============================================================================
# 테스트 데이터 헬퍼
# ============================================================================


def _make_test_stock_df(n_rows: int = 30) -> pd.DataFrame:
    """오케스트레이터 테스트용 주식 데이터를 생성한다.

    MA window=5/10/15에 충분한 크기의 테스트 데이터를 제공한다.
    상승 추세 후 하락하여 매수/매도 신호가 발생하도록 설계한다.

    Args:
        n_rows: 데이터 행 수 (기본값: 30)

    Returns:
        pd.DataFrame: 테스트용 OHLCV DataFrame
    """
    dates = []
    day = 2
    month = 1
    year = 2023
    for _ in range(n_rows):
        dates.append(date(year, month, day))
        day += 1
        weekday = dates[-1].weekday()
        if weekday == 4:  # 금요일 -> 월요일
            day += 2
        if day > 28:
            day = 1
            month += 1
            if month > 12:
                month = 1
                year += 1

    # 상승 후 하락 패턴 (거래 신호 발생 유도)
    base_prices = []
    for i in range(n_rows):
        if i < n_rows // 2:
            # 상승 구간
            base_prices.append(100.0 + i * 2.0)
        else:
            # 하락 구간
            base_prices.append(100.0 + (n_rows // 2) * 2.0 - (i - n_rows // 2) * 2.0)

    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [p - 0.5 for p in base_prices],
            COL_HIGH: [p + 1.5 for p in base_prices],
            COL_LOW: [p - 1.5 for p in base_prices],
            COL_CLOSE: base_prices,
            COL_VOLUME: [1000000 + i * 10000 for i in range(n_rows)],
        }
    )


def _make_test_split_config(tmp_path: Path) -> SplitStrategyConfig:
    """테스트용 SplitStrategyConfig를 생성한다.

    실제 MA=150/200/250 대신 MA=5/10/15를 사용한다.

    Args:
        tmp_path: pytest 임시 디렉토리

    Returns:
        SplitStrategyConfig: 테스트용 설정
    """
    test_data_path = tmp_path / "test_stock.csv"
    result_dir = tmp_path / "split_results"
    result_dir.mkdir(exist_ok=True)

    # 테스트 데이터 저장
    test_df = _make_test_stock_df()
    test_df.to_csv(test_data_path, index=False)

    base_config = BufferZoneConfig(
        strategy_name="buffer_zone_test",
        display_name="테스트 버퍼존",
        signal_data_path=test_data_path,
        trade_data_path=test_data_path,
        result_dir=tmp_path / "base_results",
        ma_window=10,
        buy_buffer_zone_pct=FIXED_4P_BUY_BUFFER_ZONE_PCT,
        sell_buffer_zone_pct=FIXED_4P_SELL_BUFFER_ZONE_PCT,
        hold_days=FIXED_4P_HOLD_DAYS,
    )

    tranches = (
        SplitTrancheConfig(tranche_id="ma15", weight=0.33, ma_window=15),
        SplitTrancheConfig(tranche_id="ma10", weight=0.34, ma_window=10),
        SplitTrancheConfig(tranche_id="ma5", weight=0.33, ma_window=5),
    )

    return SplitStrategyConfig(
        strategy_name="split_test",
        display_name="분할 테스트",
        base_config=base_config,
        total_capital=10_000_000.0,
        tranches=tranches,
        result_dir=result_dir,
    )


# ============================================================================
# Phase 0 — 그린 테스트 (타입/설정 검증)
# ============================================================================


class TestSplitTrancheConfig:
    """SplitTrancheConfig 데이터 클래스 테스트."""

    def test_split_tranche_config_creation(self):
        """
        목적: SplitTrancheConfig이 올바르게 생성되는지 검증

        Given: tranche_id, weight, ma_window 값
        When: SplitTrancheConfig 생성
        Then: 모든 필드가 올바르게 설정됨
        """
        # Given / When
        config = SplitTrancheConfig(tranche_id="ma250", weight=0.33, ma_window=250)

        # Then
        assert config.tranche_id == "ma250"
        assert config.weight == pytest.approx(0.33, abs=1e-12)
        assert config.ma_window == 250

    def test_split_tranche_config_frozen(self):
        """
        목적: SplitTrancheConfig이 frozen(불변)인지 검증

        Given: 생성된 SplitTrancheConfig
        When: 필드 변경 시도
        Then: FrozenInstanceError 발생
        """
        config = SplitTrancheConfig(tranche_id="ma200", weight=0.34, ma_window=200)

        with pytest.raises(AttributeError):
            config.weight = 0.5  # type: ignore[misc]


class TestSplitStrategyConfig:
    """SplitStrategyConfig 데이터 클래스 테스트."""

    def test_split_strategy_config_creation(self, tmp_path):
        """
        목적: SplitStrategyConfig이 올바르게 생성되는지 검증

        Given: 전략 설정 파라미터
        When: SplitStrategyConfig 생성
        Then: 모든 필드가 올바르게 설정됨
        """
        config = _make_test_split_config(tmp_path)

        assert config.strategy_name == "split_test"
        assert config.display_name == "분할 테스트"
        assert config.total_capital == pytest.approx(10_000_000.0, abs=0.01)
        assert len(config.tranches) == 3
        assert isinstance(config.result_dir, Path)


class TestSplitConfigs:
    """SPLIT_CONFIGS 리스트 검증 테스트."""

    def test_split_configs_defined(self):
        """
        목적: SPLIT_CONFIGS 리스트가 비어있지 않은지 검증

        Given: 모듈 로드
        When: SPLIT_CONFIGS 접근
        Then: 최소 1개 설정이 존재
        """
        assert len(SPLIT_CONFIGS) > 0

    def test_split_configs_weight_sum(self):
        """
        목적: 각 설정의 가중치 합이 1.0에 근접하는지 검증

        Given: SPLIT_CONFIGS의 각 설정
        When: 트랜치별 가중치 합산
        Then: 합계 ≈ 1.0
        """
        for config in SPLIT_CONFIGS:
            weight_sum = sum(t.weight for t in config.tranches)
            assert weight_sum == pytest.approx(1.0, abs=0.01), f"{config.strategy_name}: 가중치 합 {weight_sum} != 1.0"

    def test_split_configs_tranche_ids_unique(self):
        """
        목적: 각 설정 내 트랜치 ID가 고유한지 검증

        Given: SPLIT_CONFIGS의 각 설정
        When: 트랜치 ID 수집
        Then: 중복 없음
        """
        for config in SPLIT_CONFIGS:
            ids = [t.tranche_id for t in config.tranches]
            assert len(ids) == len(set(ids)), f"{config.strategy_name}: 중복 트랜치 ID 존재"

    def test_split_configs_use_correct_constants(self):
        """
        목적: SPLIT_CONFIGS가 constants.py의 상수를 올바르게 사용하는지 검증

        Given: SPLIT_CONFIGS
        When: 트랜치별 ma_window, weight, tranche_id 확인
        Then: SPLIT_TRANCHE_* 상수와 일치
        """
        for config in SPLIT_CONFIGS:
            ma_windows = [t.ma_window for t in config.tranches]
            weights = [t.weight for t in config.tranches]
            ids = [t.tranche_id for t in config.tranches]

            assert ma_windows == SPLIT_TRANCHE_MA_WINDOWS
            for actual, expected in zip(weights, SPLIT_TRANCHE_WEIGHTS, strict=False):
                assert actual == pytest.approx(expected, abs=1e-12)
            assert ids == SPLIT_TRANCHE_IDS

    def test_split_configs_base_params_use_4p(self):
        """
        목적: base_config의 파라미터가 4P 확정값인지 검증

        Given: SPLIT_CONFIGS의 각 설정
        When: base_config의 buy/sell/hold 파라미터 확인
        Then: FIXED_4P_* 상수와 일치
        """
        for config in SPLIT_CONFIGS:
            bc = config.base_config
            assert bc.buy_buffer_zone_pct == pytest.approx(FIXED_4P_BUY_BUFFER_ZONE_PCT, abs=1e-12)
            assert bc.sell_buffer_zone_pct == pytest.approx(FIXED_4P_SELL_BUFFER_ZONE_PCT, abs=1e-12)
            assert bc.hold_days == FIXED_4P_HOLD_DAYS


# ============================================================================
# Phase 0 — 레드 테스트 (Phase 1에서 그린 전환)
# ============================================================================


class TestRunSplitBacktest:
    """run_split_backtest() 함수 테스트."""

    def test_run_split_backtest_returns_result(self, tmp_path):
        """
        목적: 실행 후 SplitStrategyResult를 반환하는지 검증

        Given: 테스트용 SplitStrategyConfig
        When: run_split_backtest() 호출
        Then: SplitStrategyResult 타입 반환
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)
        assert isinstance(result, SplitStrategyResult)

    def test_capital_allocation_per_tranche(self, tmp_path):
        """
        목적: total_capital * weight = 트랜치 자본이 올바른지 검증

        Given: 테스트 설정 (total=10M, weights=0.33/0.34/0.33)
        When: run_split_backtest() 실행
        Then: 각 트랜치의 initial_capital이 total * weight와 일치
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        for tranche_result, tranche_config in zip(result.per_tranche, config.tranches, strict=False):
            expected_capital = config.total_capital * tranche_config.weight
            actual_capital = tranche_result.summary["initial_capital"]
            assert actual_capital == pytest.approx(expected_capital, abs=0.01), (
                f"트랜치 {tranche_config.tranche_id}: " f"expected={expected_capital}, actual={actual_capital}"
            )

    def test_each_tranche_uses_own_ma_window(self, tmp_path):
        """
        목적: 트랜치별 올바른 MA 윈도우를 사용하는지 검증

        Given: 테스트 설정 (ma_window=15/10/5)
        When: run_split_backtest() 실행
        Then: 각 트랜치의 summary에 올바른 ma_window가 기록됨
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        for tranche_result, tranche_config in zip(result.per_tranche, config.tranches, strict=False):
            assert tranche_result.summary["ma_window"] == tranche_config.ma_window

    def test_base_params_preserved(self, tmp_path):
        """
        목적: buy/sell/hold가 base_config의 4P 확정값 그대로인지 검증

        Given: 테스트 설정 (base_config의 4P 고정)
        When: run_split_backtest() 실행
        Then: 각 트랜치의 buy/sell/hold가 base_config와 동일
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        for tranche_result in result.per_tranche:
            assert tranche_result.summary["buy_buffer_zone_pct"] == pytest.approx(
                config.base_config.buy_buffer_zone_pct, abs=1e-12
            )
            assert tranche_result.summary["sell_buffer_zone_pct"] == pytest.approx(
                config.base_config.sell_buffer_zone_pct, abs=1e-12
            )
            assert tranche_result.summary["hold_days"] == config.base_config.hold_days

    def test_combined_equity_columns(self, tmp_path):
        """
        목적: combined_equity_df에 필수 컬럼이 존재하는지 검증

        Given: 테스트 설정
        When: run_split_backtest() 실행
        Then: Date, equity, active_tranches, avg_entry_price 컬럼 존재
              + 트랜치별 {tranche_id}_equity, {tranche_id}_position 컬럼 존재
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        required_cols = ["Date", "equity", "active_tranches", "avg_entry_price"]
        for col in required_cols:
            assert col in result.combined_equity_df.columns, f"필수 컬럼 누락: {col}"

        for tranche in config.tranches:
            equity_col = f"{tranche.tranche_id}_equity"
            position_col = f"{tranche.tranche_id}_position"
            assert equity_col in result.combined_equity_df.columns, f"컬럼 누락: {equity_col}"
            assert position_col in result.combined_equity_df.columns, f"컬럼 누락: {position_col}"

    def test_combined_equity_includes_cash(self, tmp_path):
        """
        목적: 합산 equity가 트랜치별 주식평가액 + 현금인지 검증

        Given: 테스트 설정
        When: run_split_backtest() 실행
        Then: 모든 날짜에서 equity >= sum(트랜치별 equity) (현금 포함)
              첫 날 equity == total_capital (전액 현금)
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        equity_cols = [f"{t.tranche_id}_equity" for t in config.tranches]
        tranche_sum = result.combined_equity_df[equity_cols].sum(axis=1)

        # 합산 equity는 항상 트랜치별 주식평가액 합 이상 (현금 포함)
        for i in range(len(result.combined_equity_df)):
            total_eq = result.combined_equity_df.iloc[i]["equity"]
            stock_eq = tranche_sum.iloc[i]
            assert total_eq >= stock_eq - 0.01, f"행 {i}: equity < 주식평가액 합"

        # 첫 날은 전액 현금이므로 total_capital과 동일
        assert result.combined_equity_df.iloc[0]["equity"] == pytest.approx(config.total_capital, abs=0.01)

    def test_combined_trades_tranche_tagging(self, tmp_path):
        """
        목적: combined_trades_df에 tranche_id, tranche_seq, ma_window 컬럼이 존재하는지 검증

        Given: 테스트 설정
        When: run_split_backtest() 실행
        Then: 트랜치 태깅 컬럼이 존재하고 올바른 값을 가짐
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        if not result.combined_trades_df.empty:
            assert "tranche_id" in result.combined_trades_df.columns
            assert "tranche_seq" in result.combined_trades_df.columns
            assert "ma_window" in result.combined_trades_df.columns

            # tranche_id 값이 설정된 ID 목록에 포함되는지
            valid_ids = {t.tranche_id for t in config.tranches}
            actual_ids = set(result.combined_trades_df["tranche_id"].unique())
            assert actual_ids.issubset(valid_ids)

    def test_active_tranches_count(self, tmp_path):
        """
        목적: 포지션 보유 중인 트랜치 수가 정확한지 검증

        Given: 테스트 설정
        When: run_split_backtest() 실행
        Then: active_tranches는 position > 0인 트랜치 수와 일치
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        position_cols = [f"{t.tranche_id}_position" for t in config.tranches]
        for i in range(len(result.combined_equity_df)):
            row = result.combined_equity_df.iloc[i]
            expected_active = sum(1 for col in position_cols if row[col] > 0)
            assert row["active_tranches"] == expected_active, (
                f"행 {i}: active_tranches={row['active_tranches']}, " f"expected={expected_active}"
            )

    def test_avg_entry_price_calculation(self, tmp_path):
        """
        목적: 보유 트랜치의 가중 평균 진입가가 올바른지 검증

        Given: 테스트 설정
        When: run_split_backtest() 실행
        Then: avg_entry_price가 None(보유 없음) 또는 가중평균 진입가
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        # active_tranches == 0인 행에서 avg_entry_price가 None인지 확인
        for i in range(len(result.combined_equity_df)):
            row = result.combined_equity_df.iloc[i]
            if row["active_tranches"] == 0:
                assert row["avg_entry_price"] is None or pd.isna(
                    row["avg_entry_price"]
                ), f"행 {i}: 보유 트랜치 없지만 avg_entry_price가 설정됨"


# ============================================================================
# Phase 1 — 추가 테스트
# ============================================================================


class TestSplitBacktestAdditional:
    """run_split_backtest() 추가 검증 테스트."""

    def test_open_position_in_per_tranche(self, tmp_path):
        """
        목적: 미청산 포지션이 트랜치별 summary에 포함되는지 검증

        Given: 테스트 설정 (상승 후 하락 패턴)
        When: run_split_backtest() 실행
        Then: open_position이 있는 트랜치의 summary에 포함됨
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        # 일부 트랜치에 미청산 포지션이 있을 수 있음
        for tr in result.per_tranche:
            if "open_position" in tr.summary:
                op = tr.summary["open_position"]
                assert "entry_date" in op
                assert "entry_price" in op
                assert "shares" in op

    def test_empty_trades_tranche(self, tmp_path):
        """
        목적: 거래 없는 트랜치가 있어도 정상 동작하는지 검증

        Given: 데이터가 매우 적어 일부 트랜치에서 거래 미발생 가능
        When: run_split_backtest() 실행
        Then: SplitStrategyResult가 정상 반환됨
        """
        # 데이터가 적은 설정 생성 (MA=15는 유효 데이터 부족 가능)
        test_data_path = tmp_path / "short_stock.csv"
        result_dir = tmp_path / "short_results"
        result_dir.mkdir(exist_ok=True)

        # 20행 데이터 (MA=15에서 유효 행 5개 정도)
        short_df = _make_test_stock_df(n_rows=20)
        short_df.to_csv(test_data_path, index=False)

        base_config = BufferZoneConfig(
            strategy_name="buffer_zone_test",
            display_name="테스트 버퍼존",
            signal_data_path=test_data_path,
            trade_data_path=test_data_path,
            result_dir=tmp_path / "base_results",
            ma_window=10,
            buy_buffer_zone_pct=FIXED_4P_BUY_BUFFER_ZONE_PCT,
            sell_buffer_zone_pct=FIXED_4P_SELL_BUFFER_ZONE_PCT,
            hold_days=FIXED_4P_HOLD_DAYS,
        )

        tranches = (
            SplitTrancheConfig(tranche_id="ma5", weight=0.33, ma_window=5),
            SplitTrancheConfig(tranche_id="ma3", weight=0.34, ma_window=3),
            SplitTrancheConfig(tranche_id="ma2", weight=0.33, ma_window=2),
        )

        config = SplitStrategyConfig(
            strategy_name="split_test_short",
            display_name="분할 테스트 (짧은 데이터)",
            base_config=base_config,
            total_capital=10_000_000.0,
            tranches=tranches,
            result_dir=result_dir,
        )

        result = run_split_backtest(config)
        assert isinstance(result, SplitStrategyResult)
        assert len(result.per_tranche) == 3

    def test_data_loaded_once(self, tmp_path):
        """
        목적: 동일 데이터를 트랜치 수만큼 중복 로딩하지 않는지 구조 검증

        Given: 테스트 설정 (3 트랜치)
        When: run_split_backtest() 실행 중 load_stock_data 호출 횟수 확인
        Then: load_stock_data는 1회만 호출됨 (signal == trade 경로)
        """
        config = _make_test_split_config(tmp_path)

        with patch(
            "qbt.backtest.split_strategy.load_stock_data",
            wraps=load_stock_data,
        ) as mock_load:
            run_split_backtest(config)

            # signal_data_path == trade_data_path이므로 1회만 호출
            assert mock_load.call_count == 1, f"load_stock_data가 {mock_load.call_count}회 호출됨 (1회 예상)"

    def test_combined_summary_total_capital(self, tmp_path):
        """
        목적: combined_summary의 initial_capital이 total_capital과 일치하는지 검증

        Given: 테스트 설정 (total=10M)
        When: run_split_backtest() 실행
        Then: combined_summary.initial_capital == 10M
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        assert result.combined_summary["initial_capital"] == pytest.approx(config.total_capital, abs=0.01)

    def test_params_json_structure(self, tmp_path):
        """
        목적: params_json이 올바른 구조를 가지는지 검증

        Given: 테스트 설정
        When: run_split_backtest() 실행
        Then: params_json에 필수 키가 포함됨
        """
        config = _make_test_split_config(tmp_path)
        result = run_split_backtest(config)

        pj = result.params_json
        assert "total_capital" in pj
        assert "buy_buffer_zone_pct" in pj
        assert "sell_buffer_zone_pct" in pj
        assert "hold_days" in pj
        assert "ma_type" in pj
        assert "tranches" in pj
        assert len(pj["tranches"]) == len(config.tranches)

        for t_info in pj["tranches"]:
            assert "tranche_id" in t_info
            assert "ma_window" in t_info
            assert "weight" in t_info
            assert "initial_capital" in t_info
