"""여러 매매법 포트폴리오 테스트

한 실험에 여러 매매법(각자 몫 · 현금 · 보유 주수 · 손익 장부)을 두는 엔진 확장의 계약을 검증한다.
설정 검증, 자산 키, 종목 단위 상계, 매매법 사이 비중 되돌리기, 비중이 바뀌는 매매법(배분 규칙),
0주 체결 기록, 장부 항등식 검사 규칙을 다룬다.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.allocator_registry import ALLOCATOR_REGISTRY, AllocatorSpec
from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.backtest.engines.portfolio_data import validate_portfolio_config
from qbt.backtest.engines.portfolio_engine import compute_portfolio_effective_start_date, run_portfolio_backtest
from qbt.backtest.engines.portfolio_methods import (
    account_target_weights,
    cap_transfers,
    compute_allocation_projection,
    compute_netting,
    generate_allocation_intents,
    plan_method_transfers,
    summarize_methods,
)
from qbt.backtest.engines.portfolio_planning import ProjectedPortfolio
from qbt.backtest.engines.portfolio_rebalance import RebalancePolicy
from qbt.backtest.portfolio_types import (
    AllocationAssetConfig,
    AllocatorMethodConfig,
    AssetSlotConfig,
    PortfolioConfig,
    PortfolioResult,
    SignalSeriesConfig,
    SlotMethodConfig,
    position_key,
    resolve_methods,
)
from qbt.backtest.portfolio_validation import _check_method_transfers, validate_portfolio_result
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME

# ============================================================================
# 공통 헬퍼
# ============================================================================

_DUMMY = Path("dummy")


def _trading_dates() -> list[date]:
    """2024-01-02 ~ 2024-02-29 평일."""
    dates: list[date] = []
    current = date(2024, 1, 2)
    while current <= date(2024, 2, 29):
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def _price_df(jump_date: date, price_before: float, price_after: float) -> pd.DataFrame:
    """jump_date 부터 시가 · 종가가 price_after 로 바뀌는 합성 시세 (시가 = 종가)."""
    dates = _trading_dates()
    closes = [price_after if d >= jump_date else price_before for d in dates]
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: closes,
            COL_HIGH: [c + 1.0 for c in closes],
            COL_LOW: [c - 1.0 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * len(dates),
        }
    )


def _flat_df(price: float) -> pd.DataFrame:
    return _price_df(date(2099, 1, 1), price, price)


def _hold_slot(asset_id: str, path: Path, weight: float) -> AssetSlotConfig:
    return AssetSlotConfig(asset_id, path, path, target_weight=weight, strategy_id="buy_and_hold")


class _SeriesSwitchAllocator:
    """테스트용 배분 규칙: 신호용 시세 s 의 종가가 100 을 넘으면 x 100%, 아니면 z 100% (매일 판단)."""

    def target_weights(
        self,
        data: Mapping[str, pd.DataFrame],
        i: int,
        current_date: date,
        is_check_day: bool,
    ) -> Mapping[str, float] | None:
        if float(data["s"].iloc[i][COL_CLOSE]) > 100.0:
            return {"x": 1.0}
        return {"z": 1.0}


@pytest.fixture
def series_switch_allocator(monkeypatch: pytest.MonkeyPatch) -> str:
    """테스트용 배분 규칙을 레지스트리에 등록하고 그 id 를 돌려준다."""
    spec = AllocatorSpec(
        allocator_id="test_series_switch",
        create_allocator=lambda method: _SeriesSwitchAllocator(),
        get_warmup_periods=lambda method: 0,
    )
    monkeypatch.setitem(ALLOCATOR_REGISTRY, "test_series_switch", spec)
    return "test_series_switch"


def _ledger_value(result: PortfolioResult, method_id: str, d: date, column: str) -> object:
    ledger = result.ledger_df
    return ledger.loc[(ledger[COL_DATE] == d) & (ledger["method_id"] == method_id), column].iloc[0]


# ============================================================================
# 설정 · 자산 키
# ============================================================================


class TestMethodConfigValidation:
    """설정 검증 계약.

    핵심 계약: asset_slots(매매법 하나 줄임 표기) · methods 중 정확히 하나, 매매법 몫 합 1.0 · 각 몫 > 0,
    id 중복 · '.' 금지, 같은 자산 id 는 매매법이 달라도 같은 매매 데이터 경로,
    비중변동 매매법의 allocator_id 등록 · 신호용 시세 id 가 매매 자산 id 와 겹치지 않음.
    """

    def _config(self, *, asset_slots: tuple[AssetSlotConfig, ...] = (), methods: tuple = ()) -> PortfolioConfig:
        return PortfolioConfig(
            experiment_name="test_methods",
            display_name="Test Methods",
            total_capital=10_000_000.0,
            result_dir=_DUMMY,
            asset_slots=asset_slots,
            methods=methods,
        )

    def _slot_method(
        self, method_id: str, weight: float, asset_id: str = "gld", path: Path = _DUMMY
    ) -> SlotMethodConfig:
        return SlotMethodConfig(method_id, method_id.upper(), weight, (_hold_slot(asset_id, path, 1.0),))

    def test_valid_two_method_config_passes(self, series_switch_allocator: str) -> None:
        """
        목적: 올바른 두 매매법 설정은 검증을 통과한다.

        Given: 슬롯 매매법 0.7 + 비중변동 매매법 0.3 (신호용 시세 s)
        When:  validate_portfolio_config()
        Then:  예외 없음
        """
        methods = (
            self._slot_method("q2", 0.7),
            AllocatorMethodConfig(
                "rot",
                "ROT",
                0.3,
                (AllocationAssetConfig("x", _DUMMY, _DUMMY), AllocationAssetConfig("z", _DUMMY, _DUMMY)),
                allocator_id=series_switch_allocator,
                signal_series=(SignalSeriesConfig("s", _DUMMY),),
            ),
        )

        validate_portfolio_config(self._config(methods=methods))

    def test_both_asset_slots_and_methods_raises(self) -> None:
        """asset_slots 와 methods 를 함께 채우면 ValueError."""
        with pytest.raises(ValueError, match="asset_slots"):
            validate_portfolio_config(
                self._config(asset_slots=(_hold_slot("gld", _DUMMY, 1.0),), methods=(self._slot_method("m", 1.0),))
            )

    def test_neither_asset_slots_nor_methods_raises(self) -> None:
        """둘 다 비우면 ValueError."""
        with pytest.raises(ValueError, match="asset_slots"):
            validate_portfolio_config(self._config())

    def test_method_weights_must_sum_to_one(self) -> None:
        """매매법 몫 합이 1.0 이 아니면 ValueError."""
        with pytest.raises(ValueError, match="몫"):
            validate_portfolio_config(self._config(methods=(self._slot_method("a", 0.6), self._slot_method("b", 0.3))))

    def test_method_weight_must_be_positive(self) -> None:
        """몫이 0 이하인 매매법이 있으면 ValueError."""
        with pytest.raises(ValueError, match="몫"):
            validate_portfolio_config(self._config(methods=(self._slot_method("a", 1.0), self._slot_method("b", 0.0))))

    def test_duplicate_method_id_raises(self) -> None:
        """method_id 중복이면 ValueError."""
        with pytest.raises(ValueError, match="method_id"):
            validate_portfolio_config(self._config(methods=(self._slot_method("a", 0.5), self._slot_method("a", 0.5))))

    @pytest.mark.parametrize(("method_id", "asset_id"), [("a.b", "gld"), ("a", "g.ld")])
    def test_dot_in_ids_raises(self, method_id: str, asset_id: str) -> None:
        """자산 키 구분자 '.' 가 method_id · asset_id 에 있으면 ValueError."""
        methods = (self._slot_method(method_id, 0.5, asset_id), self._slot_method("other", 0.5))
        with pytest.raises(ValueError, match="'.'"):
            validate_portfolio_config(self._config(methods=methods))

    def test_same_asset_id_with_different_trade_path_raises(self) -> None:
        """같은 자산 id 를 두 매매법이 다른 매매 데이터로 들면 ValueError (상계 기준이 종목이다)."""
        methods = (
            self._slot_method("a", 0.5, "gld", Path("GLD.csv")),
            self._slot_method("b", 0.5, "gld", Path("OTHER.csv")),
        )
        with pytest.raises(ValueError, match="매매 데이터 경로"):
            validate_portfolio_config(self._config(methods=methods))

    def test_unknown_allocator_id_raises(self) -> None:
        """등록되지 않은 allocator_id 면 ValueError."""
        methods = (
            AllocatorMethodConfig("a", "A", 1.0, (AllocationAssetConfig("x", _DUMMY, _DUMMY),), allocator_id="nope"),
        )
        with pytest.raises(ValueError, match="allocator_id"):
            validate_portfolio_config(self._config(methods=methods))

    def test_signal_series_id_colliding_with_asset_id_raises(self, series_switch_allocator: str) -> None:
        """신호용 시세 id 가 매매 자산 id 와 같으면 ValueError (배분 규칙의 입력 키가 겹친다)."""
        methods = (
            AllocatorMethodConfig(
                "a",
                "A",
                1.0,
                (AllocationAssetConfig("x", _DUMMY, _DUMMY),),
                allocator_id=series_switch_allocator,
                signal_series=(SignalSeriesConfig("x", _DUMMY),),
            ),
        )
        with pytest.raises(ValueError, match="series_id"):
            validate_portfolio_config(self._config(methods=methods))


class TestPositionKeyAndResolveMethods:
    """자산 키와 줄임 표기 해석 계약.

    핵심 계약: 매매법이 하나면 자산 키 = 자산 id (기존 결과 파일과 같다),
    둘 이상이면 「매매법.자산」. asset_slots 줄임 표기는 method_id = experiment_name, 몫 1.0 인 매매법 하나다.
    """

    def test_single_method_key_is_asset_id(self) -> None:
        assert position_key("q2_2xs", "gld", multi_method=False) == "gld"

    def test_multi_method_key_has_method_prefix(self) -> None:
        assert position_key("q2_2xs", "gld", multi_method=True) == "q2_2xs.gld"

    def test_asset_slots_shorthand_resolves_to_one_method(self) -> None:
        """
        Given: asset_slots 로만 만든 설정
        When:  resolve_methods()
        Then:  SlotMethodConfig 하나, method_id = experiment_name, 몫 1.0, 슬롯 그대로
        """
        slots = (_hold_slot("gld", _DUMMY, 0.6), _hold_slot("tlt", _DUMMY, 0.4))
        config = PortfolioConfig(
            experiment_name="portfolio_x", display_name="X", total_capital=1.0, result_dir=_DUMMY, asset_slots=slots
        )

        methods = resolve_methods(config)

        assert len(methods) == 1
        method = methods[0]
        assert isinstance(method, SlotMethodConfig)
        assert method.method_id == "portfolio_x"
        assert method.target_weight == 1.0
        assert method.asset_slots == slots


# ============================================================================
# 상계 · 매매법 사이 이전 · 배분 변화 (단위)
# ============================================================================


class TestNetting:
    """종목 단위 상계 계약.

    핵심 계약: 같은 날 같은 종목을 매매법들이 반대로 매매하면 계좌는 순량만 체결한다.
    장부는 각자 단독 매매처럼 비용을 내므로 절감 = (Σ|Δ| − |ΣΔ|) × 시가 × SLIPPAGE_RATE.
    """

    def test_opposite_trades_save_cost(self) -> None:
        """
        목적: D18 의 예 — A 가 TLT 10,000주 매도, B 가 6,000주 매수, 시가 100 → 절감 3,600.
        """
        result = compute_netting([-10_000, 6_000], 100.0)

        assert result.gross_shares == 16_000
        assert result.net_shares == -4_000
        assert result.savings == pytest.approx(12_000 * 100.0 * SLIPPAGE_RATE, abs=1e-6)
        assert result.savings == pytest.approx(3_600.0, abs=1e-6)

    def test_same_direction_saves_nothing(self) -> None:
        result = compute_netting([-100, -50], 100.0)
        assert result.savings == pytest.approx(0.0, abs=1e-12)

    def test_single_trade_saves_nothing(self) -> None:
        result = compute_netting([-100, 0], 100.0)
        assert result.savings == pytest.approx(0.0, abs=1e-12)


class TestMethodTransfers:
    """매매법 사이 비중 되돌리기 계약 (D29 · D34 ③).

    핵심 계약: 어느 매매법이든 몫의 상대 편차가 임계값을 넘으면 전 매매법을 목표 몫으로 되돌리는 이전액을 낸다.
    체결 때는 내주는 쪽의 매도 뒤 현금 안에서만 내주고, 모자라면 받는 쪽을 계획 비율대로 줄인다.
    """

    def test_triggers_and_transfers_sum_to_zero(self) -> None:
        """
        Given: 자본 a 7,500,000 · b 2,500,000, 목표 몫 0.7 · 0.3 → b 몫 0.25, 상대 편차 16.7%
        When:  plan_method_transfers(threshold 0.10)
        Then:  a −500,000, b +500,000
        """
        transfers = plan_method_transfers({"a": 7_500_000.0, "b": 2_500_000.0}, {"a": 0.7, "b": 0.3}, 0.10)

        assert transfers is not None
        assert transfers["a"] == pytest.approx(-500_000.0, abs=0.01)
        assert transfers["b"] == pytest.approx(500_000.0, abs=0.01)

    def test_within_threshold_returns_none(self) -> None:
        """b 몫 0.28 (편차 6.7%), a 몫 0.72 (편차 2.9%) → None."""
        assert plan_method_transfers({"a": 7_200_000.0, "b": 2_800_000.0}, {"a": 0.7, "b": 0.3}, 0.10) is None

    def test_cap_when_giver_cash_is_short(self) -> None:
        """
        Given: 계획 a −500,000 → b +500,000, 매도 뒤 a 현금 300,000
        When:  cap_transfers()
        Then:  a −300,000, b +300,000 (어느 현금도 음수가 되지 않는다)
        """
        capped = cap_transfers({"a": -500_000.0, "b": 500_000.0}, {"a": 300_000.0, "b": 0.0})

        assert capped["a"] == pytest.approx(-300_000.0, abs=0.01)
        assert capped["b"] == pytest.approx(300_000.0, abs=0.01)

    def test_cap_prorates_receivers(self) -> None:
        """
        Given: 계획 a −600 → b +400 · c +200, a 현금 300
        Then:  b +200, c +100 (계획 비율대로)
        """
        capped = cap_transfers({"a": -600.0, "b": 400.0, "c": 200.0}, {"a": 300.0, "b": 0.0, "c": 0.0})

        assert capped["a"] == pytest.approx(-300.0, abs=1e-9)
        assert capped["b"] == pytest.approx(200.0, abs=1e-9)
        assert capped["c"] == pytest.approx(100.0, abs=1e-9)


class TestAllocationIntents:
    """비중이 바뀌는 매매법의 배분 변화 계약 (D19 · D30).

    핵심 계약: 목표 0 이 된 보유 종목은 전량 청산, 보유 0 에서 목표 > 0 이면 진입(목표 = 매매법 자본 × 비중),
    보유 중 목표가 바뀌면 그 금액으로 증감. 진입 · 조정 종목은 그날 리밸런싱 편차 판정에서 뺀다.
    """

    def test_switch_exits_old_and_enters_new(self) -> None:
        """
        Given: 목표 {a:1} → {b:1}, a 100주(10,000), 매매법 자본 10,000
        Then:  a EXIT_ALL, b ENTER_TO_TARGET 목표 10,000
        """
        intents = generate_allocation_intents(
            old_targets={"a": 1.0, "b": 0.0},
            new_targets={"b": 1.0},
            positions={"a": 100, "b": 0},
            equity_vals={"a": 10_000.0, "b": 0.0},
            method_equity=10_000.0,
        )

        assert intents["a"].intent_type == "EXIT_ALL"
        assert intents["b"].intent_type == "ENTER_TO_TARGET"
        assert intents["b"].target_amount == pytest.approx(10_000.0, abs=0.01)

    def test_weight_change_adjusts_held_assets(self) -> None:
        """
        Given: 목표 {a:0.5, b:0.5} → {a:0.25, b:0.75}, 둘 다 5,000 보유, 매매법 자본 10,000
        Then:  a REDUCE −2,500, b INCREASE +2,500
        """
        intents = generate_allocation_intents(
            old_targets={"a": 0.5, "b": 0.5},
            new_targets={"a": 0.25, "b": 0.75},
            positions={"a": 50, "b": 50},
            equity_vals={"a": 5_000.0, "b": 5_000.0},
            method_equity=10_000.0,
        )

        assert intents["a"].intent_type == "REDUCE_TO_TARGET"
        assert intents["a"].delta_amount == pytest.approx(-2_500.0, abs=0.01)
        assert intents["b"].intent_type == "INCREASE_TO_TARGET"
        assert intents["b"].delta_amount == pytest.approx(2_500.0, abs=0.01)

    def test_none_means_no_change(self) -> None:
        intents = generate_allocation_intents(
            old_targets={"a": 1.0},
            new_targets=None,
            positions={"a": 100},
            equity_vals={"a": 10_000.0},
            method_equity=10_000.0,
        )
        assert intents == {}

    @pytest.mark.parametrize("bad_targets", [{"q": 1.0}, {"a": -0.1}, {"a": 0.7, "b": 0.5}])
    def test_invalid_targets_raise(self, bad_targets: dict[str, float]) -> None:
        """모르는 종목 · 음수 비중 · 합 1 초과는 ValueError."""
        with pytest.raises(ValueError):
            generate_allocation_intents(
                old_targets={"a": 0.5, "b": 0.5},
                new_targets=bad_targets,
                positions={"a": 0, "b": 0},
                equity_vals={"a": 0.0, "b": 0.0},
                method_equity=10_000.0,
            )

    def test_projection_excludes_entering_and_adjusted_assets(self) -> None:
        """
        Given: 위 「갈아타기」 의도 (a 청산 10,000, b 진입), 현금 0
        When:  compute_allocation_projection()
        Then:  active = {b}, 판정 제외 = {b}, 예상 현금 10,000, a 예상 금액 0
        """
        intents = generate_allocation_intents(
            old_targets={"a": 1.0, "b": 0.0},
            new_targets={"b": 1.0},
            positions={"a": 100, "b": 0},
            equity_vals={"a": 10_000.0, "b": 0.0},
            method_equity=10_000.0,
        )

        projected = compute_allocation_projection({"a": 0.0, "b": 1.0}, intents, {"a": 10_000.0, "b": 0.0}, 0.0)

        assert projected.active_assets == {"b"}
        assert projected.check_excluded_assets == {"b"}
        assert projected.projected_cash == pytest.approx(10_000.0, abs=0.01)
        assert projected.projected_amounts["a"] == pytest.approx(0.0, abs=0.01)

    def test_projection_excludes_adjusted_assets(self) -> None:
        """조정 의도가 난 종목은 보유 중이어도 판정에서 뺀다."""
        intents = generate_allocation_intents(
            old_targets={"a": 0.5, "b": 0.5},
            new_targets={"a": 0.25, "b": 0.75},
            positions={"a": 50, "b": 50},
            equity_vals={"a": 5_000.0, "b": 5_000.0},
            method_equity=10_000.0,
        )

        projected = compute_allocation_projection({"a": 0.25, "b": 0.75}, intents, {"a": 5_000.0, "b": 5_000.0}, 0.0)

        assert projected.check_excluded_assets == {"a", "b"}


# ============================================================================
# 엔진 시나리오
# ============================================================================


class TestTwoMethodNetting:
    """두 매매법이 같은 날 같은 종목을 반대로 매매하는 엔진 시나리오.

    매매법 a(몫 0.5): x · y 보유 0.5 · 0.5. 매매법 b(몫 0.5): 테스트용 배분 규칙(신호용 시세 s 가 100 초과면 x, 아니면 z).
    x 가 2024-01-15 부터 +30% → a 안에서 x 상대 편차 약 13% → 2024-01-31 판단으로 a 는 x 를 판다.
    s 가 2024-01-31 에 50 → 150 → b 는 z 를 팔고 x 를 산다. 2024-02-01 시가에 x 가 상계된다.
    매매법 몫은 a 약 0.535 (상대 편차 약 7%) 라 매매법 사이 되돌리기는 일어나지 않는다.
    """

    def _frames(self, open_offset: float = 0.0) -> dict[str, pd.DataFrame]:
        """시나리오의 시세. open_offset 을 주면 시가만 그만큼 옮긴다 (시가와 종가를 구분해야 하는 검사용)."""
        frames = {
            "x": _price_df(date(2024, 1, 15), 100.0, 130.0),
            "y": _flat_df(100.0),
            "z": _flat_df(100.0),
            "s": _price_df(date(2024, 1, 31), 50.0, 150.0),
        }
        for df in frames.values():
            df[COL_OPEN] = df[COL_OPEN] + open_offset
        return frames

    def _run(
        self, tmp_path: Path, create_csv_file, allocator_id: str, frames: dict[str, pd.DataFrame] | None = None
    ) -> PortfolioResult:
        frames = self._frames() if frames is None else frames
        x = create_csv_file("X_max.csv", frames["x"])
        y = create_csv_file("Y_max.csv", frames["y"])
        z = create_csv_file("Z_max.csv", frames["z"])
        s = create_csv_file("S_max.csv", frames["s"])
        config = PortfolioConfig(
            experiment_name="test_two_methods",
            display_name="Test Two Methods",
            total_capital=10_000_000.0,
            result_dir=tmp_path,
            methods=(
                SlotMethodConfig("a", "A", 0.5, (_hold_slot("x", x, 0.5), _hold_slot("y", y, 0.5))),
                AllocatorMethodConfig(
                    "b",
                    "B",
                    0.5,
                    (AllocationAssetConfig("z", z, z), AllocationAssetConfig("x", x, x)),
                    allocator_id=allocator_id,
                    signal_series=(SignalSeriesConfig("s", s),),
                ),
            ),
        )
        return run_portfolio_backtest(config)

    def test_netting_row_and_savings(self, tmp_path: Path, create_csv_file, series_switch_allocator: str) -> None:
        """
        Then: 상계 행은 2024-02-01 x 하나, 절감 = 2 × a 의 x 매도 주수 × 시가 130 × SLIPPAGE_RATE
        """
        result = self._run(tmp_path, create_csv_file, series_switch_allocator)

        netting = result.netting_df
        assert list(zip(netting[COL_DATE], netting["asset_id"], strict=True)) == [(date(2024, 2, 1), "x")]
        trades = result.trades_df
        a_sells = trades[(trades["asset_id"] == "a.x") & (trades["exit_date"] == date(2024, 2, 1))]
        assert len(a_sells) == 1, "a 는 2024-02-01 에 x 를 한 번 줄여야 한다"
        sold = int(a_sells["shares"].iloc[0])
        assert netting["savings"].iloc[0] == pytest.approx(2 * sold * 130.0 * SLIPPAGE_RATE, abs=0.01)
        # 상계된 주수 = 사는 쪽과 파는 쪽이 서로 맞춘 주수 (a 가 판 만큼, 양쪽에서 두 번 세지 않는다)
        assert summarize_methods(result)["netting"]["netted_shares"] == sold

    def test_keys_ledger_and_validation(self, tmp_path: Path, create_csv_file, series_switch_allocator: str) -> None:
        """
        Then: 결과 키가 「매매법.종목」, 장부가 거래일 × 2 행, 계좌 자본 = Σ 매매법 자본 + 상계 절감, 검사기 위반 0건
        """
        result = self._run(tmp_path, create_csv_file, series_switch_allocator)

        assert {"a.x_shares", "a.y_shares", "b.x_shares", "b.z_shares"} <= set(result.equity_df.columns)
        assert len(result.ledger_df) == 2 * len(result.equity_df)
        last_date = result.equity_df[COL_DATE].iloc[-1]
        methods_equity = sum(float(_ledger_value(result, m, last_date, "equity")) for m in ("a", "b"))
        savings = float(result.equity_df["netting_savings"].iloc[-1])
        # 누적 절감은 상계 행의 합과 같아야 한다 (계좌 자본 등식이 같은 누적 변수를 쓰므로 따로 고정한다)
        assert savings > 0
        assert savings == pytest.approx(float(result.netting_df["savings"].sum()), abs=1e-9)
        assert float(result.equity_df["equity"].iloc[-1]) == pytest.approx(methods_equity + savings, abs=0.01)
        assert validate_portfolio_result(result) == []

    def test_check_excluded_on_allocation_switch(
        self, tmp_path: Path, create_csv_file, series_switch_allocator: str
    ) -> None:
        """
        목적: b 의 갈아타기(진입)가 b 안의 리밸런싱을 일으키지 않음 — b 는 그날 리밸런싱 없음, a 는 정기 리밸런싱.
        """
        result = self._run(tmp_path, create_csv_file, series_switch_allocator)

        assert bool(_ledger_value(result, "a", date(2024, 2, 1), "rebalanced")) is True
        assert bool(_ledger_value(result, "b", date(2024, 2, 1), "rebalanced")) is False

    def test_ledger_cost_is_own_turnover_times_open_times_slippage(
        self, tmp_path: Path, create_csv_file, series_switch_allocator: str
    ) -> None:
        """
        목적: 장부 비용 = 그 매매법이 단독으로 매매했을 때의 비용 누적 — 날마다 Σ |주수 변화| × 시가 × SLIPPAGE_RATE
              (상계로 계좌가 아낀 비용은 장부 비용에서 빼지 않는다)

        Given: 두 매매법 시나리오에서 시가만 종가보다 1 낮춘 시세 (종가로 계산한 비용과 구분된다)
        When: 실행
        Then: 매매법마다 상태 로그의 주수 변화와 시가로 다시 계산한 비용이 마지막 날 장부 cost 와 같고 0 보다 크다
        """
        # Given
        frames = self._frames(open_offset=-1.0)

        # When
        result = self._run(tmp_path, create_csv_file, series_switch_allocator, frames)

        # Then: 상계가 일어난 실행이어야 「절감을 장부 비용에서 빼지 않는다」가 검사된다
        assert not result.netting_df.empty
        state = result.state_log_df
        open_on = {asset_id: dict(zip(df[COL_DATE], df[COL_OPEN], strict=True)) for asset_id, df in frames.items()}
        last_date = state[COL_DATE].iloc[-1]
        for method_id, asset_ids in (("a", ("x", "y")), ("b", ("z", "x"))):
            expected = 0.0
            for asset_id in asset_ids:
                shares = state[f"{method_id}.{asset_id}_shares"]
                turnover = shares.diff().fillna(shares).abs()
                expected += sum(
                    float(moved) * open_on[asset_id][d] * SLIPPAGE_RATE
                    for moved, d in zip(turnover, state[COL_DATE], strict=True)
                )
            assert expected > 0
            assert float(_ledger_value(result, method_id, last_date, "cost")) == pytest.approx(expected, abs=1e-6)


class TestInterMethodRebalance:
    """매매법 사이 비중 되돌리기 엔진 시나리오 (D29).

    매매법 a(몫 0.5): x 보유 1.0, b(몫 0.5): y 보유 1.0. x 가 2024-01-15 부터 +40% →
    a 몫 약 0.583 (상대 편차 약 17%) → 2024-01-31 판단, 2024-02-01 체결로 a 가 b 에 자본을 넘긴다.
    """

    def _run(self, tmp_path: Path, create_csv_file) -> PortfolioResult:
        x = create_csv_file("X_max.csv", _price_df(date(2024, 1, 15), 100.0, 140.0))
        y = create_csv_file("Y_max.csv", _flat_df(100.0))
        config = PortfolioConfig(
            experiment_name="test_inter_method",
            display_name="Test Inter Method",
            total_capital=10_000_000.0,
            result_dir=tmp_path,
            methods=(
                SlotMethodConfig("a", "A", 0.5, (_hold_slot("x", x, 1.0),)),
                SlotMethodConfig("b", "B", 0.5, (_hold_slot("y", y, 1.0),)),
            ),
        )
        return run_portfolio_backtest(config)

    def test_transfer_recorded_and_shares_restored(self, tmp_path: Path, create_csv_file) -> None:
        """
        Then: 2024-02-01 장부 사유 methods, 이전 누적 a < 0 < b 이고 합 0, 그날 종가 몫이 목표 대비 20% 이내, 위반 0건
        """
        result = self._run(tmp_path, create_csv_file)
        d = date(2024, 2, 1)

        assert _ledger_value(result, "a", d, "rebalance_reason") == "methods"
        assert _ledger_value(result, "b", d, "rebalance_reason") == "methods"
        a_transfer = float(_ledger_value(result, "a", d, "transfers"))
        b_transfer = float(_ledger_value(result, "b", d, "transfers"))
        assert a_transfer < 0 < b_transfer
        assert a_transfer + b_transfer == pytest.approx(0.0, abs=0.01)
        for method_id in ("a", "b"):
            share = float(_ledger_value(result, method_id, d, "share"))
            assert abs(share / 0.5 - 1.0) <= 0.20
        assert validate_portfolio_result(result) == []

    def test_no_transfer_before_check_day(self, tmp_path: Path, create_csv_file) -> None:
        """월중(2024-01-15 이후)에는 몫이 벌어져도 이전이 없다 — 2024-01-31 까지 이전 누적 0."""
        result = self._run(tmp_path, create_csv_file)

        assert float(_ledger_value(result, "a", date(2024, 1, 31), "transfers")) == pytest.approx(0.0, abs=1e-9)


class TestZeroShareFill:
    """1주 미만 리밸런싱 주문 계약 (D34 ⑥, 미룬 지적).

    매매법 하나(줄임 표기), 초기 자본 1,000, a · b 보유 0.5 · 0.5 (가격 100 → 각 4주).
    b 가 2024-01-15 부터 125 → 2024-01-31 판단에서 a 상대 편차 약 27% 로 리밸런싱.
    b 의 증액 목표(약 48.8)는 1주(125.375)보다 작아 2024-02-01 에 0주 체결된다.
    """

    def test_zero_share_fill_is_recorded_and_passes_validation(self, tmp_path: Path, create_csv_file) -> None:
        """
        Then: 2024-02-01 상태 로그 b_executed_intent = INCREASE_TO_TARGET, b_exec_shares = 0, 검사기 위반 0건
        """
        a = create_csv_file("A_max.csv", _flat_df(100.0))
        b = create_csv_file("B_max.csv", _price_df(date(2024, 1, 15), 100.0, 125.0))
        config = PortfolioConfig(
            experiment_name="test_zero_share",
            display_name="Test Zero Share",
            total_capital=1_000.0,
            result_dir=tmp_path,
            asset_slots=(_hold_slot("a", a, 0.5), _hold_slot("b", b, 0.5)),
        )

        result = run_portfolio_backtest(config)

        state_log = result.state_log_df
        row = state_log[state_log[COL_DATE] == date(2024, 2, 1)].iloc[0]
        assert row["b_executed_intent"] == "INCREASE_TO_TARGET"
        assert int(row["b_exec_shares"]) == 0
        assert validate_portfolio_result(result) == []


# ============================================================================
# 검사 규칙 6 · 7
# ============================================================================


class TestLedgerValidationRules:
    """장부 항등식(규칙 6) · 매매법 사이 되돌리기(규칙 7 — 장부 몫 열 · 판단일 판정과 이전 · 되돌리기 뒤 몫) 검사 계약.

    핵심 계약: 정상 결과는 위반 0건, 장부 값을 어긋나게 바꾼 결과는 해당 규칙 위반이 나온다.
    """

    def test_rule6_detects_broken_identity(self, tmp_path: Path, create_csv_file) -> None:
        """장부의 매매법 자본 한 칸을 1,000 늘리면 [규칙6] 위반."""
        result = TestInterMethodRebalance()._run(tmp_path, create_csv_file)
        ledger = result.ledger_df.copy()
        ledger.loc[ledger.index[10], "equity"] = float(ledger.loc[ledger.index[10], "equity"]) + 1_000.0

        violations = validate_portfolio_result(replace(result, ledger_df=ledger))

        assert any(v.startswith("[규칙6]") for v in violations), violations

    def test_rule7_detects_share_off_target_after_transfer(self, tmp_path: Path, create_csv_file) -> None:
        """매매법 사이 되돌리기 체결일의 매매법 현금을 3,000,000 늘리면 (판단일 종가 평가 몫이 목표에서 벗어나) [규칙7] 위반."""
        result = TestInterMethodRebalance()._run(tmp_path, create_csv_file)
        ledger = result.ledger_df.copy()
        mask = (ledger[COL_DATE] == date(2024, 2, 1)) & (ledger["method_id"] == "a")
        ledger.loc[mask, "cash"] = ledger.loc[mask, "cash"] + 3_000_000.0

        violations = validate_portfolio_result(replace(result, ledger_df=ledger))

        assert any(v.startswith("[규칙7]") for v in violations), violations

    def test_rule7_ignores_price_gap_on_execution_day(self, tmp_path: Path, create_csv_file) -> None:
        """
        목적: 체결일 시가 · 종가가 크게 빠져도(이전은 계획대로 체결) 규칙 7 이 거짓 위반을 내지 않는다.

        Given: 매매법 a(x 1.0) · b(y 1.0) 0.5 / 0.5, x 가 2024-01-15 부터 +40% → 2024-01-31 판단으로 a 가 자본을 넘김.
               체결일 2024-02-01 부터 x 시가 · 종가가 140 → 77 (-45%)
        When:  run_portfolio_backtest() → validate_portfolio_result()
        Then:  위반 0건 (몫은 판단일 종가로 평가한다)
        """
        dates = _trading_dates()
        closes = [77.0 if d >= date(2024, 2, 1) else 140.0 if d >= date(2024, 1, 15) else 100.0 for d in dates]
        x_df = pd.DataFrame(
            {
                COL_DATE: dates,
                COL_OPEN: closes,
                COL_HIGH: [c + 1.0 for c in closes],
                COL_LOW: [c - 1.0 for c in closes],
                COL_CLOSE: closes,
                COL_VOLUME: [1_000_000] * len(dates),
            }
        )
        x = create_csv_file("X_max.csv", x_df)
        y = create_csv_file("Y_max.csv", _flat_df(100.0))
        config = PortfolioConfig(
            experiment_name="test_gap",
            display_name="Test Gap",
            total_capital=10_000_000.0,
            result_dir=tmp_path,
            methods=(
                SlotMethodConfig("a", "A", 0.5, (_hold_slot("x", x, 1.0),)),
                SlotMethodConfig("b", "B", 0.5, (_hold_slot("y", y, 1.0),)),
            ),
        )

        result = run_portfolio_backtest(config)

        assert _ledger_value(result, "a", date(2024, 2, 1), "rebalance_reason") == "methods"
        assert validate_portfolio_result(result) == []

    @pytest.mark.parametrize(
        "defect",
        [
            pytest.param(lambda planned, cash: {m: 0.0 for m in planned}, id="skipped"),
            pytest.param(
                lambda planned, cash: {m: (1.0 if v > 0 else -1.0 if v < 0 else 0.0) for m, v in planned.items()},
                id="one_won",
            ),
            pytest.param(
                lambda planned, cash: {m: 0.5 * v for m, v in cap_transfers(planned, cash).items()}, id="half"
            ),
        ],
    )
    def test_rule7_detects_transfer_short_of_plan(
        self, tmp_path: Path, create_csv_file, monkeypatch: pytest.MonkeyPatch, defect
    ) -> None:
        """
        목적: 매매법 사이 이전이 계획보다 적은데 내주는 쪽에 현금이 남으면(상한이 걸린 것이 아니면) 규칙 7 이 잡는다.

        Given: TestInterMethodRebalance 구성(2024-01-31 판단일 a 몫 편차 약 17%), 엔진의 이전 상한 계산 결함 —
               이전을 통째로 빠뜨림 · 1 만 옮김 · 절반만 옮김. a 는 자기 종목을 팔아 사유가 methods 로 남는다
        When:  run_portfolio_backtest() → validate_portfolio_result()
        Then:  「2024-02-01 a: 계획보다 적게 냈는데 현금이 남음」 [규칙7] 위반
        """
        monkeypatch.setattr("qbt.backtest.engines.portfolio_engine.cap_transfers", defect)

        result = TestInterMethodRebalance()._run(tmp_path, create_csv_file)

        violations = validate_portfolio_result(result)
        assert any(v.startswith("[규칙7] 2024-02-01 a") and "적게" in v for v in violations), violations

    def test_rule7_detects_transfer_without_trigger(
        self, tmp_path: Path, create_csv_file, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        목적: 판단일 몫이 임계값 안인데 매매법 사이 이전이 일어나면 규칙 7 이 잡는다.

        Given: 매매법 a(x 1.0) · b(y 1.0) 0.5 / 0.5, x 가 2024-01-15 부터 +10% → 2024-01-31 a 몫 편차 약 4.8%(임계값 10% 안).
               엔진이 매매법 사이 판정에 임계값 0 을 쓰는 결함
        When:  run_portfolio_backtest() → validate_portfolio_result()
        Then:  「2024-02-01 매매법 사이 이전이 있는데 직전 거래일이 판정을 넘은 판단일이 아님」 [규칙7] 위반
        """
        monkeypatch.setattr(
            "qbt.backtest.engines.portfolio_engine.plan_method_transfers",
            lambda equities, targets, threshold_rate: plan_method_transfers(equities, targets, 0.0),
        )
        x = create_csv_file("X_max.csv", _price_df(date(2024, 1, 15), 100.0, 110.0))
        y = create_csv_file("Y_max.csv", _flat_df(100.0))
        config = PortfolioConfig(
            experiment_name="test_untriggered_transfer",
            display_name="Test Untriggered Transfer",
            total_capital=10_000_000.0,
            result_dir=tmp_path,
            methods=(
                SlotMethodConfig("a", "A", 0.5, (_hold_slot("x", x, 1.0),)),
                SlotMethodConfig("b", "B", 0.5, (_hold_slot("y", y, 1.0),)),
            ),
        )

        result = run_portfolio_backtest(config)

        violations = validate_portfolio_result(result)
        assert any(v.startswith("[규칙7] 2024-02-01") and "판정을 넘은 판단일이 아님" in v for v in violations), violations

    def test_rule7_detects_share_column_mismatch(self, tmp_path: Path, create_csv_file) -> None:
        """판단일이 아닌 날(2024-01-10) 장부 몫 한 칸을 0.6 으로 바꾸면 「장부 몫 × 매매법 자본 합 != 매매법 자본」 [규칙7] 위반."""
        result = TestInterMethodRebalance()._run(tmp_path, create_csv_file)
        ledger = result.ledger_df.copy()
        mask = (ledger[COL_DATE] == date(2024, 1, 10)) & (ledger["method_id"] == "a")
        ledger.loc[mask, "share"] = 0.6

        violations = validate_portfolio_result(replace(result, ledger_df=ledger))

        assert any(v.startswith("[규칙7] 2024-01-10 a") and "장부 몫" in v for v in violations), violations


def _transfer_ledger(moved_a: float, moved_b: float, cash_a_after: float) -> pd.DataFrame:
    """매매법 a · b (목표 0.5 / 0.5) 장부 3일치. 2024-01-31 판단일에 a 몫 0.6 → 계획 이전 a −1,000 · b +1,000.

    체결일 2024-02-01 의 이전 누적은 moved_a · moved_b, a 의 그날 끝 현금은 cash_a_after.
    """
    days = (
        (date(2024, 1, 30), 0.0, 0.0, 500.0),
        (date(2024, 1, 31), 0.0, 0.0, 500.0),
        (date(2024, 2, 1), moved_a, moved_b, cash_a_after),
    )
    rows: list[dict[str, object]] = []
    for d, transfer_a, transfer_b, cash_a in days:
        equity_a, equity_b = 6_000.0 + transfer_a, 4_000.0 + transfer_b
        total = equity_a + equity_b
        rows.append(
            {
                COL_DATE: d,
                "method_id": "a",
                "equity": equity_a,
                "cash": cash_a,
                "share": equity_a / total,
                "transfers": transfer_a,
            }
        )
        rows.append(
            {
                COL_DATE: d,
                "method_id": "b",
                "equity": equity_b,
                "cash": 100.0,
                "share": equity_b / total,
                "transfers": transfer_b,
            }
        )
    return pd.DataFrame(rows)


class TestMethodTransferCheck:
    """규칙 7 (이전)의 상한 규칙 계약 — 장부만으로 판정한다.

    내주는 쪽은 0 부터 계획액까지 내고, 계획보다 적게 냈다면 그날 끝 현금이 0 이어야 한다(매도 뒤 현금을 다 냈다).
    받는 쪽은 내준 합을 계획 비율대로 받는다.
    """

    @pytest.mark.parametrize(
        ("moved_a", "moved_b", "cash_a_after"),
        [
            pytest.param(-1_000.0, 1_000.0, 500.0, id="planned_in_full"),
            pytest.param(-400.0, 400.0, 0.0, id="capped_by_cash"),
            pytest.param(0.0, 0.0, 0.0, id="capped_to_zero"),
        ],
    )
    def test_transfers_following_cap_rule_pass(self, moved_a: float, moved_b: float, cash_a_after: float) -> None:
        """계획대로 · 매도 뒤 현금만큼만 · 현금이 0 이라 0 원 — 셋 다 엔진의 정상 동작이라 위반 0건."""
        ledger = _transfer_ledger(moved_a, moved_b, cash_a_after)

        assert _check_method_transfers(ledger, {"a": 0.5, "b": 0.5}, 0.10) == []

    @pytest.mark.parametrize(
        ("moved_a", "moved_b", "cash_a_after", "fragment"),
        [
            pytest.param(0.0, 0.0, 500.0, "적게", id="short_with_cash_left"),
            pytest.param(-400.0, 0.0, 0.0, "받은 이전", id="receiver_not_prorated"),
            pytest.param(-2_000.0, 2_000.0, 0.0, "사이가 아님", id="given_beyond_plan"),
            pytest.param(1_000.0, -1_000.0, 0.0, "사이가 아님", id="wrong_direction"),
        ],
    )
    def test_transfers_breaking_cap_rule_fail(
        self, moved_a: float, moved_b: float, cash_a_after: float, fragment: str
    ) -> None:
        """상한으로 설명되지 않는 이전은 [규칙7] 2024-02-01 위반."""
        ledger = _transfer_ledger(moved_a, moved_b, cash_a_after)

        violations = _check_method_transfers(ledger, {"a": 0.5, "b": 0.5}, 0.10)

        assert any(v.startswith("[규칙7] 2024-02-01") and fragment in v for v in violations), violations


# ============================================================================
# 배분 규칙 시세 · 조정일 검사 · 입력과 불변조건 가드
# ============================================================================


class _RecordingAllocator:
    """첫 판단의 행 번호 · 날짜와 받은 시세의 첫 날짜를 기록하는 테스트용 배분 규칙 (x 100%)."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, date, date, date]] = []

    def target_weights(
        self,
        data: Mapping[str, pd.DataFrame],
        i: int,
        current_date: date,
        is_check_day: bool,
    ) -> Mapping[str, float] | None:
        x = data["x"]
        self.calls.append((i, current_date, x[COL_DATE].iloc[i], x[COL_DATE].iloc[0]))
        return {"x": 1.0}


class _AlternatingAllocator:
    """테스트용 배분 규칙: 날마다 x · y 비중을 번갈아 바꾸고 z 는 0.10 으로 둔다."""

    def target_weights(
        self,
        data: Mapping[str, pd.DataFrame],
        i: int,
        current_date: date,
        is_check_day: bool,
    ) -> Mapping[str, float] | None:
        if i % 2 == 0:
            return {"x": 0.45, "y": 0.45, "z": 0.10}
        return {"x": 0.35, "y": 0.55, "z": 0.10}


def _register(monkeypatch: pytest.MonkeyPatch, allocator_id: str, allocator: object, warmup: int) -> None:
    spec = AllocatorSpec(
        allocator_id=allocator_id,
        create_allocator=lambda method: allocator,
        get_warmup_periods=lambda method: warmup,
    )
    monkeypatch.setitem(ALLOCATOR_REGISTRY, allocator_id, spec)


def _single_allocator_config(
    tmp_path: Path, assets: tuple[AllocationAssetConfig, ...], allocator_id: str
) -> PortfolioConfig:
    return PortfolioConfig(
        experiment_name="test_allocator",
        display_name="Test Allocator",
        total_capital=10_000_000.0,
        result_dir=tmp_path,
        methods=(AllocatorMethodConfig("m", "M", 1.0, assets, allocator_id=allocator_id),),
    )


class TestAllocatorSeesHistory:
    """배분 규칙은 워밍업 · 시작일로 잘리기 전 시세를 받는다 (get_warmup_periods 가 약속한 과거 행).

    잘린 시세를 주면 i 가 0 부터 시작해 i − n 이 음수가 되고, pandas 는 음수 iloc 을 끝에서부터 세어
    미래 가격을 조용히 읽는다(미래 참조).
    """

    @pytest.mark.parametrize(
        ("start_date", "expected_first_index", "expected_first_date"),
        [(None, 4, date(2024, 1, 8)), (date(2024, 1, 15), 9, date(2024, 1, 15))],
    )
    def test_first_call_index_points_into_full_history(
        self,
        tmp_path: Path,
        create_csv_file,
        monkeypatch: pytest.MonkeyPatch,
        start_date,
        expected_first_index,
        expected_first_date,
    ) -> None:
        """
        Given: 워밍업 5 행인 배분 규칙, 시세 2024-01-02 부터
        When:  run_portfolio_backtest() (시작일 없음 / 2024-01-15)
        Then:  첫 판단의 i 는 잘리기 전 시세의 행 번호이고, 그 행의 날짜가 오늘이며, 시세는 2024-01-02 부터 있다
        """
        x = create_csv_file("X_max.csv", _flat_df(100.0))
        allocator = _RecordingAllocator()
        _register(monkeypatch, "test_recording", allocator, warmup=5)
        config = _single_allocator_config(tmp_path, (AllocationAssetConfig("x", x, x),), "test_recording")

        run_portfolio_backtest(config, start_date=start_date)

        first_index, first_date, row_date, data_first_date = allocator.calls[0]
        assert first_index == expected_first_index
        assert first_date == expected_first_date
        assert row_date == first_date, "배분 규칙 시세의 i 행은 오늘이어야 한다 (행 정렬)"
        assert data_first_date == date(2024, 1, 2), "과거 행이 잘리지 않아야 한다"


class TestAllocatorAdjustmentValidation:
    """배분 규칙의 조정만 있는 날의 규칙 2 계약.

    - 상태 로그의 목표 비중은 그날 체결이 맞추려던(전날 정한) 값이다 — 오늘 판단으로 바뀐 다음 날 목표가 아니다
    - 조정한 자산만 검사하고, 매매하지 않은 자산의 월중 이탈은 검사하지 않는다
    """

    def test_daily_alternating_allocator_passes_validation(
        self, tmp_path: Path, create_csv_file, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: 날마다 x · y 비중을 번갈아 바꾸는 배분 규칙, z(목표 0.10)는 2024-01-15 부터 +35% (상대 이탈 20% 초과)
        When:  run_portfolio_backtest() → validate_portfolio_result()
        Then:  위반 0건, 상태 로그의 x 목표 비중은 그날 체결이 맞추려던 값이다
        """
        x = create_csv_file("X_max.csv", _flat_df(100.0))
        y = create_csv_file("Y_max.csv", _flat_df(100.0))
        z = create_csv_file("Z_max.csv", _price_df(date(2024, 1, 15), 100.0, 135.0))
        _register(monkeypatch, "test_alternating", _AlternatingAllocator(), warmup=0)
        assets = (AllocationAssetConfig("x", x, x), AllocationAssetConfig("y", y, y), AllocationAssetConfig("z", z, z))
        config = _single_allocator_config(tmp_path, assets, "test_alternating")

        result = run_portfolio_backtest(config)

        assert validate_portfolio_result(result) == []
        state_log = result.state_log_df
        # i=1(2024-01-03) 판단 목표 x 0.35 → i=2(2024-01-04) 에 체결되므로 그날 기록된 목표는 0.35
        row = state_log[state_log[COL_DATE] == date(2024, 1, 4)].iloc[0]
        assert float(row["x_target_weight"]) == pytest.approx(0.35, abs=1e-12)


class TestReviewGuards:
    """입력 검증 · 불변조건 가드."""

    def test_nan_weight_raises(self) -> None:
        """배분 규칙이 NaN 비중을 내면 ValueError (뒤에서 엉뚱한 오류로 멈추지 않는다)."""
        with pytest.raises(ValueError, match="NaN"):
            generate_allocation_intents(
                old_targets={"a": 0.0},
                new_targets={"a": float("nan")},
                positions={"a": 0},
                equity_vals={"a": 0.0},
                method_equity=10_000.0,
            )

    def test_empty_ledger_raises(self, tmp_path: Path, create_csv_file) -> None:
        """장부가 빈 결과는 검사를 건너뛰지 않고 RuntimeError."""
        result = TestInterMethodRebalance()._run(tmp_path, create_csv_file)

        with pytest.raises(RuntimeError, match="ledger_df"):
            validate_portfolio_result(replace(result, ledger_df=pd.DataFrame()))

    def test_unknown_allocator_in_start_date_raises_value_error(self) -> None:
        """유효 시작일 계산도 설정 검증을 먼저 거쳐, 모르는 allocator_id 는 안내 메시지가 있는 ValueError."""
        config = _single_allocator_config(_DUMMY, (AllocationAssetConfig("x", _DUMMY, _DUMMY),), "not_registered")

        with pytest.raises(ValueError, match="allocator_id"):
            compute_portfolio_effective_start_date(config)

    def test_empty_slot_method_raises(self) -> None:
        """슬롯이 없는 매매법은 ValueError."""
        config = PortfolioConfig(
            experiment_name="test_empty_slots",
            display_name="Test Empty Slots",
            total_capital=1.0,
            result_dir=_DUMMY,
            methods=(
                SlotMethodConfig("a", "A", 0.5, ()),
                SlotMethodConfig("b", "B", 0.5, (_hold_slot("g", _DUMMY, 1.0),)),
            ),
        )

        with pytest.raises(ValueError, match="슬롯"):
            validate_portfolio_config(config)

    def test_rebalance_intents_raise_when_active_asset_has_no_target(self) -> None:
        """active 자산이 목표 비중에 없으면 그 주문을 조용히 빼지 않고 RuntimeError."""
        projected = ProjectedPortfolio(projected_amounts={"x": 100.0}, projected_cash=0.0, active_assets={"x"})

        with pytest.raises(RuntimeError, match="target_weights"):
            RebalancePolicy(threshold_rate=0.10).build_rebalance_intents(projected, {}, 100.0, date(2024, 1, 2))

    def test_account_target_weights_raise_without_state_log(
        self, tmp_path: Path, create_csv_file, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """비중변동 매매법 결과에 상태 로그가 없으면 목표 비중을 0 으로 대신하지 않고 RuntimeError."""
        x = create_csv_file("X_max.csv", _flat_df(100.0))
        _register(monkeypatch, "test_recording", _RecordingAllocator(), warmup=0)
        result = run_portfolio_backtest(
            _single_allocator_config(tmp_path, (AllocationAssetConfig("x", x, x),), "test_recording")
        )

        with pytest.raises(RuntimeError, match="state_log_df"):
            account_target_weights(replace(result, state_log_df=pd.DataFrame()))
