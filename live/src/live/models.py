"""live 도메인 데이터 모델.

설계서 부록 B 의 dataclass / TypedDict 정의. 설계서 5.1 의 model / actual 분리 원칙과
부록 B 의 PendingOrderDict (execute_on 없음) 계약을 준수한다.

QBT 본체 타입 재사용 (SSoT 원칙):

- :class:`OrderIntent` — ``qbt.backtest.engines.portfolio_planning``
- :class:`ExecutionResult` — ``qbt.backtest.engines.portfolio_execution``
- :class:`HoldState` — ``qbt.backtest.strategies.buffer_zone_helpers``

live 에서는 위 타입들을 재정의하지 않고 import 재사용만 한다. 이 파일은 ``models``
모듈 레벨에서 위 심볼을 re-export 하여 후속 Step 에서 ``from live.models import
OrderIntent`` 형태로 일관되게 접근할 수 있도록 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

import pandas as pd

# QBT 본체 타입 재사용 (SSoT) ------------------------------------------------
from qbt.backtest.engines.portfolio_execution import ExecutionResult
from qbt.backtest.engines.portfolio_planning import OrderIntent
from qbt.backtest.strategies.buffer_zone_helpers import HoldState

__all__ = [
    # QBT 재사용
    "OrderIntent",
    "ExecutionResult",
    "HoldState",
    # live 전용
    "PendingOrderDict",
    "BufferZoneState",
    "AssetLiveState",
    "LiveState",
    "ActualFill",
    "SignalDetection",
    "ChartSeries",
    "AssetDrift",
    "DriftReport",
    "DailyResult",
    "AssetMarketData",
    "MarketBundle",
    "UserTrade",
]


# ============================================================================
# PendingOrderDict (TypedDict — JSON 왕복 단순)
# ============================================================================


class PendingOrderDict(TypedDict):
    """익일 체결 예정 주문.

    설계서 부록 B 명시: ``execute_on`` 필드를 포함하지 않는다. 체결은 다음 거래일
    시가로 자동 실행되며, 명시적 체결 예정일을 저장하지 않는다 (신호 발생 다음 거래일
    시가로 고정).
    """

    asset_id: str
    intent_type: str  # "EXIT_ALL" | "ENTER_TO_TARGET" | "REDUCE_TO_TARGET" | "INCREASE_TO_TARGET"
    signal_date: str  # ISO 8601 날짜 (예: "2026-04-10")
    current_amount: float
    target_amount: float
    delta_amount: float  # 음수 = 매도, 양수 = 매수
    target_weight: float  # 0~1 비율
    hold_days_used: int
    reason: str


# ============================================================================
# BufferZoneState — BufferZoneStrategy 의 직렬화 가능 상태
# ============================================================================


@dataclass
class BufferZoneState:
    """BufferZoneStrategy 의 private 변수를 직렬화 가능하게 담는다.

    ``BufferZoneStrategy`` 는 백테스트 엔진 안에서 ``_prev_upper``, ``_prev_lower``,
    ``_hold_state``, ``_last_buy_buffer_pct``, ``_last_hold_days_used`` 5개의 내부
    상태를 유지한다. live 환경에서는 매일 실행이 중단되었다가 재개되므로 이 상태를
    JSON 으로 저장/복원해야 한다. 복원 로직은 Step 4 의 어댑터 (``extract_buffer_state``,
    ``restore_buffer_state``) 에서 구현한다.
    """

    prev_upper: float | None
    prev_lower: float | None
    hold_state: HoldState | None
    last_buy_buffer_pct: float
    last_hold_days_used: int
    schema_version: int = 1


# ============================================================================
# AssetLiveState — 자산별 model / actual 분리 원장
# ============================================================================


@dataclass
class AssetLiveState:
    """자산별 live 상태.

    설계서 5.1 model / actual 분리 원칙:

    - ``model_*``: daily runner 가 계산한 이론적 포지션
    - ``actual_*``: 사용자가 입력한 실제 체결 포지션 (앱 → RTDB → runner)

    두 축은 서로를 덮어쓰지 않는다. drift 는 이 두 축의 차이로 계산된다.
    """

    asset_id: str

    # --- model 축 (daily runner 가 관리) ---
    model_shares: int
    model_avg_entry_price: float
    model_entry_date: str | None  # ISO 8601 날짜

    # --- actual 축 (앱 입력만 갱신) ---
    actual_shares: int
    actual_avg_entry_price: float
    actual_entry_date: str | None

    # --- 전략 상태 ---
    pending_order: PendingOrderDict | None
    signal_state: str  # "buy" | "sell" | "hold"
    entry_hold_days: int
    buffer_zone_state: BufferZoneState | None


# ============================================================================
# LiveState — 전체 포트폴리오 상태
# ============================================================================


@dataclass
class LiveState:
    """전체 포트폴리오의 live 상태.

    설계서 5.1 에 정의된 최상위 원장. qbt-live-state 리포의 ``live_state.json`` 에
    직렬화되어 저장된다.
    """

    schema_version: int
    portfolio_id: str
    last_signal_date: str | None
    last_model_execution_date: str | None
    last_rebalance_date: str | None
    shared_cash_model: float
    shared_cash_actual: float
    assets: dict[str, AssetLiveState]
    created_at: str  # ISO 8601 KST
    updated_at: str  # ISO 8601 KST


# ============================================================================
# ActualFill — 앱에서 입력한 실제 체결
# ============================================================================


@dataclass
class ActualFill:
    """앱이 RTDB ``/fills/inbox/`` 에 기록한 실제 체결 입력.

    daily runner 는 이 레코드를 읽어 :class:`AssetLiveState` 의 ``actual_*`` 축을
    갱신한다. ``rtdb_key`` 는 idempotency 를 위한 고유 키이며
    ``applied_fill_ids.json`` 에 저장되어 중복 반영을 방지한다.
    """

    asset_id: str
    direction: str  # "buy" | "sell"
    actual_price: float
    actual_shares: int
    trade_date: str  # ISO 8601 날짜
    input_time_kst: str  # ISO 8601 KST
    memo: str | None
    rtdb_key: str
    reason: str = ""


# ============================================================================
# SignalDetection — 시그널 감지 결과 (알림/차트 재사용)
# ============================================================================


@dataclass
class SignalDetection:
    """시그널 감지 결과. 알림 본문 및 차트 오버레이에서 재사용된다.

    ``ema_distance_pct`` 는 설계서 8장의 "200일선 근접도" 지표이며
    ``(close - ema_200) / ema_200`` 로 정의된다 (0~1 비율, 음수 가능).
    """

    state: Literal["buy", "sell", "hold"]
    close: float
    upper_band: float | None
    lower_band: float | None
    ema_200: float | None
    ema_distance_pct: float


# ============================================================================
# ChartSeries — 차트 시계열 (자산별 전체 기간)
# ============================================================================


@dataclass
class ChartSeries:
    """앱 차트 렌더링용 자산별 전체 기간 시계열.

    RTDB ``/latest/chart_data/{asset_id}`` 에 저장된다. 200일 EMA 의 초기 199 개는
    ``None`` 으로 채워진다.
    """

    dates: list[str]
    close: list[float]
    ema_200: list[float | None]
    upper_band: list[float | None]
    lower_band: list[float | None]
    buy_signals: list[int]
    sell_signals: list[int]
    user_buys: list[int]
    user_sells: list[int]


# ============================================================================
# DriftReport — model vs actual 차이 리포트
# ============================================================================


@dataclass
class AssetDrift:
    """자산별 drift 지표.

    설계서 본문에는 ``DriftReport.per_asset: dict[str, AssetDrift]`` 로만 언급되며
    구체 필드는 본 계획서에서 확정한다 (B 안: 표준).
    """

    asset_id: str
    model_shares: int
    actual_shares: int
    shares_diff: int  # actual - model
    model_value: float
    actual_value: float
    value_diff: float  # actual - model
    drift_pct: float  # |value_diff| / model_value * 100 (%)


@dataclass
class DriftReport:
    """전체 포트폴리오 drift 리포트.

    ``recommendation`` 은 설계서 14장 기준 문자열:

    - "정상" (0~3%)
    - "주의" (3~5%)
    - "보정 필요" (5%+)
    """

    model_equity: float
    actual_equity: float
    drift_pct: float  # |actual - model| / model * 100 (%)
    per_asset: dict[str, AssetDrift]
    recommendation: str


# ============================================================================
# DailyResult — run_daily 의 반환 컨테이너
# ============================================================================


@dataclass
class DailyResult:
    """``daily_runner.run_daily`` 의 반환 컨테이너.

    파일 I/O 전의 순수 계산 결과이며, CLI 계층이 이 객체를 받아 Git push / RTDB /
    알림 발송을 수행한다. 설계서 4.2 실행 순서 참고.
    """

    execution_date: str  # ISO 8601 날짜
    updated_state: LiveState
    updated_applied_fill_ids: dict[str, str]  # Step 3 D1: ID → ISO 타임스탬프
    signals: dict[str, SignalDetection]
    order_intents: dict[str, OrderIntent]
    executions: ExecutionResult | None
    rebalance_triggered: bool
    model_equity: float
    actual_equity: float
    drift_pct: float
    ema_distances: dict[str, float]
    notification_body: str
    pending_fill_reminders: list[str]


# ============================================================================
# MarketBundle — run_daily 에 전달되는 자산별 가격 데이터 묶음
# ============================================================================


@dataclass
class AssetMarketData:
    """자산별 시그널/체결 DataFrame 묶음.

    - ``signal_df``: 시그널 계산용 CSV (MA 컬럼 포함, 예: ``ma_200``)
    - ``trade_df``: 체결 가격 CSV (Open/Close 사용)

    QBT 포트폴리오 엔진의 ``load_and_prepare_data`` 결과와 동일한 구조이다.
    """

    signal_df: pd.DataFrame
    trade_df: pd.DataFrame


# run_daily 의 market_bundle 파라미터 타입.
# 호출자는 자산 ID 를 키로 하여 ``AssetMarketData`` 를 준비해야 한다.
type MarketBundle = dict[str, AssetMarketData]


# ============================================================================
# UserTrade — 차트 화면의 사용자 체결 마커
# ============================================================================


@dataclass
class UserTrade:
    """차트 화면에 표시할 사용자 체결 마커.

    설계서 7장: ``ChartSeries.user_buys`` / ``user_sells`` 에 인덱스로 매핑된다.
    """

    date: str  # ISO 8601 날짜
    direction: Literal["buy", "sell"]
