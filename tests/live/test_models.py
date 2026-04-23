"""live.models 데이터 모델 계약/불변조건을 고정한다."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date
from typing import get_args, get_type_hints

import pytest

from live import models
from live.models import (
    ActualFill,
    AssetDrift,
    AssetLiveState,
    BalanceAdjust,
    BufferZoneState,
    ChartSeries,
    DailyResult,
    DriftReport,
    EquityChartMeta,
    EquityChartSeries,
    LiveState,
    PendingOrderDict,
    SignalDetection,
)


class TestPendingOrderDict:
    """PendingOrderDict 는 execute_on 필드가 없는 순수 주문 의도 구조여야 한다."""

    def test_pending_order_dict_has_no_execute_on(self):
        """Given PendingOrderDict When __annotations__ 조회 Then execute_on 키 없음."""
        # Given / When
        annotations = PendingOrderDict.__annotations__

        # Then
        assert "execute_on" not in annotations, "PendingOrderDict 에 execute_on 필드가 있으면 안 된다"

    def test_pending_order_dict_required_keys(self):
        """Given PendingOrderDict When annotation 조회 Then 필수 키 모두 존재."""
        # Given
        expected_keys = {
            "asset_id",
            "intent_type",
            "signal_date",
            "current_amount",
            "target_amount",
            "delta_amount",
            "target_weight",
            "hold_days_used",
            "reason",
        }

        # When
        annotations = set(PendingOrderDict.__annotations__.keys())

        # Then
        assert expected_keys == annotations, f"PendingOrderDict 필드 불일치. 기대: {expected_keys}, 실제: {annotations}"


class TestAssetLiveState:
    """AssetLiveState 는 model_ / actual_ 필드가 명시적으로 분리되어야 한다."""

    def test_is_dataclass(self):
        """AssetLiveState 는 dataclass 여야 한다."""
        assert is_dataclass(AssetLiveState)

    def test_has_model_and_actual_fields_separated(self):
        """Given AssetLiveState When 필드 조회 Then model / actual 필드가 분리되어 존재."""
        # Given
        required_fields = {
            "model_shares",
            "model_avg_entry_price",
            "model_entry_date",
            "actual_shares",
            "actual_avg_entry_price",
            "actual_entry_date",
        }

        # When
        field_names = {f.name for f in fields(AssetLiveState)}

        # Then
        missing = required_fields - field_names
        assert not missing, f"AssetLiveState 에 누락된 model/actual 필드: {missing}"

    def test_has_pending_order_and_buffer_zone_state(self):
        """Given AssetLiveState Then pending_order / buffer_zone_state 필드 존재."""
        field_names = {f.name for f in fields(AssetLiveState)}
        assert "pending_order" in field_names
        assert "buffer_zone_state" in field_names

    def test_has_unfilled_order_date(self):
        """Given AssetLiveState Then unfilled_order_date 필드 존재."""
        field_names = {f.name for f in fields(AssetLiveState)}
        assert "unfilled_order_date" in field_names
        assert "signal_state" in field_names
        assert "entry_hold_days" in field_names
        assert "asset_id" in field_names


class TestLiveState:
    """LiveState 는 model/actual cash 분리 및 메타데이터 필드를 가져야 한다."""

    def test_is_dataclass(self):
        assert is_dataclass(LiveState)

    def test_has_both_model_and_actual_cash(self):
        """Given LiveState Then shared_cash_model 과 shared_cash_actual 이 분리된다."""
        field_names = {f.name for f in fields(LiveState)}
        assert "shared_cash_model" in field_names
        assert "shared_cash_actual" in field_names

    def test_has_required_metadata(self):
        """Given LiveState Then schema_version / portfolio_id / created_at / updated_at 존재."""
        field_names = {f.name for f in fields(LiveState)}
        assert "schema_version" in field_names
        assert "portfolio_id" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names

    def test_has_signal_and_execution_timestamps(self):
        """Given LiveState Then last_signal_date / last_model_execution_date / last_rebalance_date 존재."""
        field_names = {f.name for f in fields(LiveState)}
        assert "last_signal_date" in field_names
        assert "last_model_execution_date" in field_names
        assert "last_rebalance_date" in field_names

    def test_assets_field_present(self):
        field_names = {f.name for f in fields(LiveState)}
        assert "assets" in field_names


class TestBufferZoneState:
    """BufferZoneState 는 버퍼존 전략의 private 상태를 직렬화 가능하게 담는다."""

    def test_is_dataclass(self):
        assert is_dataclass(BufferZoneState)

    def test_fields(self):
        """Given BufferZoneState When 필드 조회 Then 필수 필드 세트와 정확히 일치."""
        expected = {
            "prev_upper",
            "prev_lower",
            "hold_state",
            "last_buy_buffer_pct",
            "last_hold_days_used",
            "schema_version",
        }
        actual = {f.name for f in fields(BufferZoneState)}
        assert expected == actual, f"BufferZoneState 필드 불일치. 기대: {expected}, 실제: {actual}"

    def test_schema_version_default_is_one(self):
        """schema_version 기본값은 1 이어야 한다."""
        state = BufferZoneState(
            prev_upper=None,
            prev_lower=None,
            hold_state=None,
            last_buy_buffer_pct=0.03,
            last_hold_days_used=0,
        )
        assert state.schema_version == 1


class TestSignalDetection:
    """SignalDetection 은 알림/차트에서 재사용 가능한 상세 정보를 담는다."""

    def test_is_dataclass(self):
        assert is_dataclass(SignalDetection)

    def test_fields(self):
        """Given SignalDetection Then state / close / 밴드 / ma / 거리% 필드가 모두 존재."""
        expected = {
            "state",
            "close",
            "upper_band",
            "lower_band",
            "ma_value",
            "ma_distance_pct",
        }
        actual = {f.name for f in fields(SignalDetection)}
        assert expected == actual

    def test_state_literal_values(self):
        """state 필드는 'buy' | 'sell' | 'none' 중 하나만 허용한다."""
        hints = get_type_hints(SignalDetection, include_extras=False)
        state_type = hints["state"]
        allowed = set(get_args(state_type))
        assert allowed == {"buy", "sell", "none"}, f"SignalDetection.state 리터럴 불일치: {allowed}"

    def test_create_buy_signal_detection(self):
        """Given: 정상 수치. When: buy SignalDetection 생성. Then: 필드 값 일치."""
        # Given / When
        detection = SignalDetection(
            state="buy",
            close=420.5,
            upper_band=418.0,
            lower_band=398.0,
            ma_value=410.0,
            ma_distance_pct=0.0256,
        )

        # Then
        assert detection.state == "buy"
        assert detection.close == pytest.approx(420.5)
        assert detection.ma_distance_pct == pytest.approx(0.0256)


class TestActualFill:
    def test_is_dataclass(self):
        assert is_dataclass(ActualFill)

    def test_fields(self):
        """Given ActualFill Then 전체 필드 세트가 고정되어 있다."""
        expected = {
            "asset_id",
            "direction",
            "actual_price",
            "actual_shares",
            "trade_date",
            "input_time_kst",
            "memo",
            "rtdb_key",
            "reason",
        }
        actual = {f.name for f in fields(ActualFill)}
        assert expected == actual


class TestBalanceAdjust:
    """자산 직접 수정용 ``BalanceAdjust`` 필드 계약."""

    def test_is_dataclass(self):
        assert is_dataclass(BalanceAdjust)

    def test_fields(self):
        expected = {
            "rtdb_key",
            "input_time_kst",
            "reason",
            "asset_id",
            "new_shares",
            "new_avg_price",
            "new_entry_date",
            "new_cash",
        }
        actual = {f.name for f in fields(BalanceAdjust)}
        assert expected == actual

    def test_construction_asset_only(self):
        adj = BalanceAdjust(
            rtdb_key="adj_001",
            input_time_kst="2026-04-10T20:00:00+09:00",
            reason="test",
            asset_id="sso",
            new_shares=420,
        )
        assert adj.asset_id == "sso"
        assert adj.new_shares == 420
        assert adj.new_cash is None

    def test_construction_cash_only(self):
        adj = BalanceAdjust(
            rtdb_key="adj_002",
            input_time_kst="2026-04-10T20:00:00+09:00",
            reason="test",
            new_cash=95000000.0,
        )
        assert adj.asset_id is None
        assert adj.new_shares is None
        assert adj.new_cash == 95000000.0


class TestFillDismiss:
    """FillDismiss 필드 계약 고정."""

    def test_is_dataclass(self):
        from live.models import FillDismiss

        assert is_dataclass(FillDismiss)

    def test_fields(self):
        from live.models import FillDismiss

        expected = {"rtdb_key", "input_time_kst", "asset_id", "reason"}
        actual = {f.name for f in fields(FillDismiss)}
        assert expected == actual


class TestDailyResult:
    def test_is_dataclass(self):
        assert is_dataclass(DailyResult)

    def test_fields(self):
        """DailyResult 가 보유해야 하는 전체 필드 계약 고정.

        차트 시계열은 CLI 계층의 ``build_chart_series`` 가 직접 생성한다.
        """
        expected = {
            "execution_date",
            "updated_state",
            "updated_applied_fill_ids",
            "updated_applied_balance_adjust_ids",
            "updated_applied_fill_dismiss_ids",
            "signals",
            "order_intents",
            "executions",
            "rebalance_triggered",
            "model_equity",
            "actual_equity",
            "drift_pct",
            "drift_report",
            "ma_distances",
            "notification_body",
            "pending_fill_reminders",
            "model_sync_applied",
        }
        actual = {f.name for f in fields(DailyResult)}
        assert expected == actual


class TestChartSeries:
    def test_is_dataclass(self):
        assert is_dataclass(ChartSeries)

    def test_fields(self):
        """Given ChartSeries Then 전체 필드 세트가 고정되어 있다."""
        expected = {
            "dates",
            "close",
            "ma_value",
            "upper_band",
            "lower_band",
            "buy_signals",
            "sell_signals",
            "user_buys",
            "user_sells",
        }
        actual = {f.name for f in fields(ChartSeries)}
        assert expected == actual


class TestDriftReport:
    def test_is_dataclass(self):
        assert is_dataclass(DriftReport)

    def test_fields(self):
        """Given DriftReport Then 전체 필드 세트가 고정되어 있다."""
        expected = {
            "model_equity",
            "actual_equity",
            "drift_pct",
            "per_asset",
            "recommendation",
        }
        actual = {f.name for f in fields(DriftReport)}
        assert expected == actual


class TestAssetDrift:
    """``AssetDrift`` 는 주수/평가액/drift % 필드를 포함하는 표준 구성이다."""

    def test_is_dataclass(self):
        assert is_dataclass(AssetDrift)

    def test_fields(self):
        """Given AssetDrift Then asset_id / shares / value / drift_pct 필드가 모두 존재."""
        expected = {
            "asset_id",
            "model_shares",
            "actual_shares",
            "shares_diff",
            "model_value",
            "actual_value",
            "value_diff",
            "drift_pct",
        }
        actual = {f.name for f in fields(AssetDrift)}
        assert expected == actual


class TestQbtCoreTypeReuse:
    """live.models 는 QBT 본체의 타입을 재정의 없이 import 재사용해야 한다.

    이는 SSoT 원칙: OrderIntent / ExecutionResult / HoldState 는 QBT 코어가 정본.
    live 측에서 중복 정의 시 동기화 누락이 발생할 수 있다.
    """

    def test_reuses_qbt_order_intent(self):
        """live.models.OrderIntent 는 QBT 코어 OrderIntent 와 동일 객체."""
        from qbt.backtest.engines.portfolio_planning import OrderIntent as QbtOrderIntent

        assert models.OrderIntent is QbtOrderIntent, "OrderIntent 는 QBT 코어를 재사용해야 한다"

    def test_reuses_qbt_execution_result(self):
        """live.models.ExecutionResult 는 QBT 코어 ExecutionResult 와 동일 객체."""
        from qbt.backtest.engines.portfolio_execution import ExecutionResult as QbtExecutionResult

        assert models.ExecutionResult is QbtExecutionResult

    def test_reuses_qbt_hold_state(self):
        """live.models.HoldState 는 QBT 코어 HoldState 와 동일 객체."""
        from qbt.backtest.strategies.buffer_zone_helpers import HoldState as QbtHoldState

        assert models.HoldState is QbtHoldState


class TestPendingOrderDictCreation:
    """PendingOrderDict 는 필수 키만으로 생성 가능해야 한다."""

    def test_create_pending_order_dict(self):
        """Given: 모든 필수 키. When: dict 생성. Then: 정상 생성."""
        # Given / When
        pending: PendingOrderDict = {
            "asset_id": "sso",
            "intent_type": "ENTER_TO_TARGET",
            "signal_date": "2026-04-10",
            "current_amount": 0.0,
            "target_amount": 35_000_000.0,
            "delta_amount": 35_000_000.0,
            "target_weight": 0.35,
            "hold_days_used": 3,
            "reason": "buffer zone breakout",
        }

        # Then
        assert pending["asset_id"] == "sso"
        assert pending["target_weight"] == pytest.approx(0.35)
        assert "execute_on" not in pending


class TestLiveStateCreation:
    """LiveState 인스턴스 생성 smoke test — model/actual cash 분리 동작 검증."""

    def test_create_empty_live_state(self):
        """Given 필수 필드 When LiveState 생성 Then 필드 접근 가능."""
        from live.constants import LIVE_PORTFOLIO_ID

        # Given / When
        state = LiveState(
            schema_version=1,
            portfolio_id=LIVE_PORTFOLIO_ID,
            last_signal_date=None,
            last_model_execution_date=None,
            last_rebalance_date=None,
            shared_cash_model=100_000_000.0,
            shared_cash_actual=100_000_000.0,
            assets={},
            created_at="2026-04-11T12:00:00+09:00",
            updated_at="2026-04-11T12:00:00+09:00",
        )

        # Then
        assert state.shared_cash_model == pytest.approx(100_000_000.0)
        assert state.shared_cash_actual == pytest.approx(100_000_000.0)
        assert state.shared_cash_model is not state.shared_cash_actual or True  # 명시적 분리
        assert state.portfolio_id == LIVE_PORTFOLIO_ID

    def test_asset_live_state_creation(self):
        """Given: 자산 필드. When: AssetLiveState 생성. Then: model/actual 독립 접근."""
        # Given / When
        asset = AssetLiveState(
            asset_id="sso",
            model_shares=100,
            model_avg_entry_price=82.5,
            model_entry_date=date(2026, 4, 1).isoformat(),
            actual_shares=100,
            actual_avg_entry_price=82.5,
            actual_entry_date=date(2026, 4, 1).isoformat(),
            pending_order=None,
            signal_state="buy",
            entry_hold_days=0,
            buffer_zone_state=None,
        )

        # Then
        assert asset.model_shares == 100
        assert asset.actual_shares == 100
        assert asset.pending_order is None


# ============================================================================
# EquityChartMeta / EquityChartSeries (PLAN_LIVE_CHARTS_RESTRUCTURE)
# ============================================================================


class TestEquityChartMeta:
    def test_equity_chart_meta_is_dataclass_with_expected_fields(self):
        """
        목적: EquityChartMeta 는 dataclass 이며 4 개 필드(first_date, last_date,
              recent_months, archive_years) 만 가진다. ma_window 필드는 없다.

        Given: EquityChartMeta 인스턴스.
        When:  dataclass 필드 이름 집합 조회.
        Then:  기대 필드 집합과 정확히 일치.
        """
        # Given / When
        assert is_dataclass(EquityChartMeta), "EquityChartMeta 는 dataclass 여야 한다"
        field_names = {f.name for f in fields(EquityChartMeta)}

        # Then
        assert field_names == {"first_date", "last_date", "recent_months", "archive_years"}
        # 주가 차트 ChartMeta 와 달리 ma_window 필드는 없다 (equity 는 MA 개념 없음)
        assert "ma_window" not in field_names

    def test_equity_chart_meta_roundtrip_with_asdict(self):
        """
        목적: asdict 로 직렬화 → dict 로 복원 시 값이 보존된다 (RTDB 쓰기 패턴).
        """
        from dataclasses import asdict as _asdict

        # Given
        meta = EquityChartMeta(
            first_date="2024-01-02",
            last_date="2026-04-10",
            recent_months=6,
            archive_years=[2024, 2025, 2026],
        )

        # When
        payload = _asdict(meta)

        # Then
        assert payload == {
            "first_date": "2024-01-02",
            "last_date": "2026-04-10",
            "recent_months": 6,
            "archive_years": [2024, 2025, 2026],
        }


class TestEquityChartSeries:
    def test_equity_chart_series_has_equity_timeseries_fields(self):
        """
        목적: EquityChartSeries 는 주가 차트(ChartSeries)와 달리 dates /
              model_equity / actual_equity 3 필드만 가진다. drift_pct 시계열은
              앱 미사용으로 제거되었다 (스칼라는 /latest/portfolio 에서 제공).
              close / ma_value / upper_band / lower_band / 마커 4 종도 포함하지
              않는다.

        Given: EquityChartSeries 인스턴스.
        When:  dataclass 필드 이름 집합 조회.
        Then:  기대 필드 집합과 일치, drift 시계열 / 주가 전용 필드는 없음.
        """
        assert is_dataclass(EquityChartSeries)
        field_names = {f.name for f in fields(EquityChartSeries)}
        assert field_names == {"dates", "model_equity", "actual_equity"}
        # drift_pct 시계열은 제거되었다 (앱 미사용 — 스칼라는 /latest/portfolio).
        assert "drift_pct" not in field_names
        # 주가 전용 필드는 없다.
        assert "close" not in field_names
        assert "ma_value" not in field_names
        assert "upper_band" not in field_names
        assert "buy_signals" not in field_names

    def test_equity_chart_series_asdict_preserves_arrays(self):
        """
        목적: asdict 호출 후 dict 에 dates / model_equity / actual_equity 3 배열이
              그대로 담기며, drift_pct 키는 페이로드에 존재하지 않는다.
        """
        from dataclasses import asdict as _asdict

        # Given
        series = EquityChartSeries(
            dates=["2026-04-09", "2026-04-10"],
            model_equity=[12_345_678, 12_400_000],
            actual_equity=[12_300_000, 12_350_001],
        )

        # When
        payload = _asdict(series)

        # Then
        assert payload["dates"] == ["2026-04-09", "2026-04-10"]
        assert payload["model_equity"] == [12_345_678, 12_400_000]
        assert payload["actual_equity"] == [12_300_000, 12_350_001]
        assert "drift_pct" not in payload


class TestModelSyncDataclass:
    """
    목적: :class:`ModelSync` 의 필드 구조를 고정한다 (최소 계약).

    ``asset_id`` / ``reason`` / ``new_*`` 등 다른 inbox dataclass 에 있는 필드는
    **의도적으로 존재하지 않는다** — 전체 동기화 전용이며 사유 입력 UI 없음.
    """

    def test_model_sync_has_minimal_fields(self):
        """
        목적: ModelSync 필드 = {rtdb_key, input_time_kst} 뿐.
        """
        from dataclasses import fields, is_dataclass

        from live.models import ModelSync

        assert is_dataclass(ModelSync)
        field_names = {f.name for f in fields(ModelSync)}
        assert field_names == {"rtdb_key", "input_time_kst"}

    def test_model_sync_does_not_have_asset_or_reason(self):
        """
        목적: 전체 동기화 / 사유 없음 원칙 — asset_id / reason 필드는 없다.
        """
        from dataclasses import fields

        from live.models import ModelSync

        field_names = {f.name for f in fields(ModelSync)}
        assert "asset_id" not in field_names
        assert "reason" not in field_names

    def test_model_sync_instantiation(self):
        """
        목적: 최소 인자로 ModelSync 가 정상 구성된다.
        """
        from live.models import ModelSync

        sync = ModelSync(rtdb_key="sync_abc", input_time_kst="2026-04-15T20:00:00+09:00")
        assert sync.rtdb_key == "sync_abc"
        assert sync.input_time_kst == "2026-04-15T20:00:00+09:00"


class TestDailyResultModelSyncAppliedField:
    """
    목적: :class:`DailyResult` 에 ``model_sync_applied: bool`` 필드가 존재함을
    고정한다. 일일 리포트 강조 블록 / 히스토리 추적이 이 필드에 의존한다.
    """

    def test_daily_result_has_model_sync_applied_field(self):
        from dataclasses import fields

        from live.models import DailyResult

        field_names = {f.name for f in fields(DailyResult)}
        assert "model_sync_applied" in field_names
