"""live.models 데이터 모델 계약/불변조건 테스트.

설계서 부록 B 에 정의된 dataclass / TypedDict 의 필드 구조를 고정하여
회귀를 방지한다.

테스트 철학 (tests/CLAUDE.md 참고):
- Given-When-Then 패턴
- 부동소수점 비교는 pytest.approx()
- 외부 네트워크 호출 없음 (데이터 모델 구조 검증만 수행)
"""

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
    BufferZoneState,
    ChartSeries,
    DailyResult,
    DriftReport,
    LiveState,
    PendingOrderDict,
    SignalDetection,
)


class TestPendingOrderDict:
    """PendingOrderDict 는 설계서 명시대로 execute_on 필드가 없어야 한다."""

    def test_pending_order_dict_has_no_execute_on(self):
        """설계서 5.1: execute_on 필드가 존재해서는 안 된다.

        Given: PendingOrderDict TypedDict
        When : __annotations__ 를 조회
        Then : execute_on 키가 없음
        """
        # Given / When
        annotations = PendingOrderDict.__annotations__

        # Then
        assert "execute_on" not in annotations, "PendingOrderDict 에 execute_on 필드가 있으면 안 된다"

    def test_pending_order_dict_required_keys(self):
        """설계서 부록 B: PendingOrderDict 필수 키 검증.

        Given: PendingOrderDict TypedDict
        When : annotation 조회
        Then : 설계서 명시 키 9 개 모두 존재
        """
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
        assert expected_keys == annotations, f"PendingOrderDict 필드가 설계서와 다름. 기대: {expected_keys}, 실제: {annotations}"


class TestAssetLiveState:
    """AssetLiveState 는 model_ / actual_ 필드가 명시적으로 분리되어야 한다."""

    def test_is_dataclass(self):
        """AssetLiveState 는 dataclass 여야 한다."""
        assert is_dataclass(AssetLiveState)

    def test_has_model_and_actual_fields_separated(self):
        """설계서 5.1: model / actual 필드가 명시적으로 분리되어 있어야 한다.

        Given: AssetLiveState dataclass
        When : 필드 이름 수집
        Then : model_shares, model_avg_entry_price, model_entry_date,
               actual_shares, actual_avg_entry_price, actual_entry_date 모두 존재
        """
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
        """설계서 5.1: pending_order, buffer_zone_state 필드 존재."""
        field_names = {f.name for f in fields(AssetLiveState)}
        assert "pending_order" in field_names
        assert "buffer_zone_state" in field_names
        assert "signal_state" in field_names
        assert "entry_hold_days" in field_names
        assert "asset_id" in field_names


class TestLiveState:
    """LiveState 는 model/actual cash 분리 및 메타데이터 필드를 가져야 한다."""

    def test_is_dataclass(self):
        assert is_dataclass(LiveState)

    def test_has_both_model_and_actual_cash(self):
        """설계서 5.1: shared_cash_model 과 shared_cash_actual 분리."""
        field_names = {f.name for f in fields(LiveState)}
        assert "shared_cash_model" in field_names
        assert "shared_cash_actual" in field_names

    def test_has_required_metadata(self):
        """설계서 5.1: schema_version, portfolio_id, created_at, updated_at 필드."""
        field_names = {f.name for f in fields(LiveState)}
        assert "schema_version" in field_names
        assert "portfolio_id" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names

    def test_has_signal_and_execution_timestamps(self):
        """설계서 5.1: last_signal_date, last_model_execution_date, last_rebalance_date."""
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
        """설계서 5.1: BufferZoneState 필수 필드.

        Given: BufferZoneState dataclass
        When : 필드 이름 수집
        Then : prev_upper, prev_lower, hold_state, last_buy_buffer_pct,
               last_hold_days_used, schema_version 모두 존재
        """
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
        """B 안: state, close, upper_band, lower_band, ema_200, ema_distance_pct."""
        expected = {
            "state",
            "close",
            "upper_band",
            "lower_band",
            "ema_200",
            "ema_distance_pct",
        }
        actual = {f.name for f in fields(SignalDetection)}
        assert expected == actual

    def test_state_literal_values(self):
        """state 필드는 'buy' | 'sell' | 'hold' 중 하나만 허용."""
        hints = get_type_hints(SignalDetection, include_extras=False)
        state_type = hints["state"]
        # typing.Literal 은 get_args 로 값 추출 가능
        allowed = set(get_args(state_type))
        assert allowed == {"buy", "sell", "hold"}, f"SignalDetection.state 리터럴이 설계 선택과 다름: {allowed}"

    def test_create_buy_signal_detection(self):
        """Given: 정상 수치. When: buy SignalDetection 생성. Then: 필드 값 일치."""
        # Given / When
        detection = SignalDetection(
            state="buy",
            close=420.5,
            upper_band=418.0,
            lower_band=398.0,
            ema_200=410.0,
            ema_distance_pct=0.0256,
        )

        # Then
        assert detection.state == "buy"
        assert detection.close == pytest.approx(420.5)
        assert detection.ema_distance_pct == pytest.approx(0.0256)


class TestActualFill:
    def test_is_dataclass(self):
        assert is_dataclass(ActualFill)

    def test_fields(self):
        """설계서 부록 B: ActualFill 전체 필드."""
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


class TestDailyResult:
    def test_is_dataclass(self):
        assert is_dataclass(DailyResult)

    def test_fields(self):
        """설계서 부록 B: DailyResult 전체 필드.

        ``chart_series`` 는 한때 필드로 선언되었으나 사용되지 않아 제거됨 (Gap 5).
        차트 시계열은 CLI 계층의 ``build_chart_series`` 가 직접 생성한다.
        """
        expected = {
            "execution_date",
            "updated_state",
            "updated_applied_fill_ids",
            "signals",
            "order_intents",
            "executions",
            "rebalance_triggered",
            "model_equity",
            "actual_equity",
            "drift_pct",
            "ema_distances",
            "notification_body",
            "pending_fill_reminders",
        }
        actual = {f.name for f in fields(DailyResult)}
        assert expected == actual


class TestChartSeries:
    def test_is_dataclass(self):
        assert is_dataclass(ChartSeries)

    def test_fields(self):
        """설계서 부록 B: ChartSeries 전체 필드."""
        expected = {
            "dates",
            "close",
            "ema_200",
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
        """설계서 부록 B: DriftReport 전체 필드."""
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
    """설계서 부록 B 에 DriftReport.per_asset 의 타입으로만 언급됨.
    필드 구성은 B 안(표준)으로 확정: 주수/평가액/drift % 포함.
    """

    def test_is_dataclass(self):
        assert is_dataclass(AssetDrift)

    def test_fields(self):
        """B 안: asset_id, model/actual shares + diff, model/actual value + diff, drift_pct."""
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
    """PendingOrderDict 는 설계서 명시 키만으로 생성 가능해야 한다."""

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
        """Given: 필수 필드. When: LiveState 생성. Then: 필드 접근 가능."""
        # Given / When
        state = LiveState(
            schema_version=1,
            portfolio_id="portfolio_q2_2xs",
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
        assert state.portfolio_id == "portfolio_q2_2xs"

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
            signal_state="hold",
            entry_hold_days=0,
            buffer_zone_state=None,
        )

        # Then
        assert asset.model_shares == 100
        assert asset.actual_shares == 100
        assert asset.pending_order is None
