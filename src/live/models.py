"""live 도메인 데이터 모델.

실매매 파이프라인이 사용하는 모든 dataclass / TypedDict 를 정의한다. 핵심 원칙:

- ``LiveState`` 는 ``model_*`` 와 ``actual_*`` 두 축을 명시적으로 분리한다.
  두 축은 서로를 덮어쓰지 않는다.
- ``PendingOrderDict`` 는 명시적 체결 예정일(``execute_on``) 을 저장하지 않는다.
  체결은 다음 거래일 시가에 자동 수행된다.
- QBT 본체 타입(:class:`OrderIntent`, :class:`ExecutionResult`, :class:`HoldState`)
  을 재정의하지 않고 import 재사용하여 SSoT 원칙을 유지한다.
- ``live`` 에서는 위 타입들을 ``from live.models import OrderIntent`` 형태로 일관되게
  재노출하여 호출자가 단일 import 경로를 쓸 수 있게 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict, get_args

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
    "IntentTypeLiteral",
    "VALID_INTENT_TYPES",
    "PendingOrderDict",
    "BufferZoneState",
    "AssetLiveState",
    "LiveState",
    "ActualFill",
    "BalanceAdjust",
    "FillDismiss",
    "ModelSync",
    "SignalDetection",
    "ChartMeta",
    "ChartSeries",
    "EquityChartMeta",
    "EquityChartSeries",
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


IntentTypeLiteral = Literal["EXIT_ALL", "ENTER_TO_TARGET", "REDUCE_TO_TARGET", "INCREASE_TO_TARGET"]
"""주문 의도(``OrderIntent.intent_type``) 의 허용 값 집합.

QBT 본체의 ``portfolio_planning.OrderIntent.intent_type`` 과 동일한 Literal 로
좁혀 live 쪽 타입 체크와 완전히 일치시킨다.
"""

# IntentTypeLiteral 에서 파생한 유효 값 집합. state.py 등에서 런타임 검증에 사용.
VALID_INTENT_TYPES: frozenset[str] = frozenset(get_args(IntentTypeLiteral))


class PendingOrderDict(TypedDict):
    """익일 체결 예정 주문.

    ``execute_on`` 필드는 포함하지 않는다. 체결은 다음 거래일 시가로 자동 실행되며,
    명시적 체결 예정일을 저장하지 않는다 (신호 발생 다음 거래일 시가로 고정).
    """

    asset_id: str
    intent_type: IntentTypeLiteral
    signal_date: str  # ISO 8601 날짜 (예: "2026-04-10")
    current_amount: float
    target_amount: float
    delta_amount: float  # 금액(원). 음수 = 매도, 양수 = 매수
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
    JSON 으로 저장/복원해야 한다. 실제 추출/복원은 :mod:`live.buffer_serializer`
    어댑터가 담당한다 (QBT 본체 수정 없음).
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

    model / actual 분리 원칙:

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
    signal_state: Literal["buy", "sell"]  # QBT AssetState.signal_state 와 동일
    entry_hold_days: int
    buffer_zone_state: BufferZoneState | None

    # --- 미입력 체결 추적 ---
    unfilled_order_date: str | None = None  # ISO 8601 날짜. model 체결 후 fill 미도착 시 set, fill/dismiss 시 clear


# ============================================================================
# LiveState — 전체 포트폴리오 상태
# ============================================================================


@dataclass
class LiveState:
    """전체 포트폴리오의 live 상태.

    qbt-live-state 리포의 ``live_state.json`` 에 직렬화되어 저장되는 최상위 원장.
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
    direction: Literal["buy", "sell"]
    actual_price: float
    actual_shares: int
    trade_date: str  # ISO 8601 날짜
    input_time_kst: str  # ISO 8601 KST
    memo: str | None
    rtdb_key: str
    reason: str = ""


# ============================================================================
# BalanceAdjust — 앱에서 입력한 자산 직접 보정
# ============================================================================


@dataclass
class BalanceAdjust:
    """앱이 RTDB ``/balance_adjust/inbox/`` 에 기록한 자산 잔고 보정.

    :class:`ActualFill` 과 다른 점: fill 은 "buy/sell 이벤트" 인 반면 balance_adjust
    는 "현재 잔고를 이 값으로 덮어쓰기" 라는 의미. 사용자가 오프라인에서 여러 거래를
    했거나 세금/배당 등으로 인한 잔고 조정, 평균가 / 진입일 재입력이 필요할 때 사용한다.

    **actual 축 전용**: balance_adjust 는 ``actual_*`` / ``shared_cash_actual`` 만
    건드리며 ``model_*`` / ``shared_cash_model`` 은 절대 변경하지 않는다
    (model/actual 분리 원칙, :mod:`src/live/CLAUDE.md` §핵심원칙 2 참고).

    필드 규칙:

    - ``asset_id`` + ``new_shares`` 지정 시 해당 자산의 ``actual_shares`` 를 교체.
      ``new_shares == 0`` 이면 ``actual_avg_entry_price`` / ``actual_entry_date``
      도 함께 리셋된다 (포지션 없음 규칙).
    - ``asset_id`` + ``new_avg_price`` 지정 시 ``actual_avg_entry_price`` 교체.
      ``new_shares > 0`` 과 동시 지정 시 두 필드 모두 갱신된다. 단독 지정도 가능.
    - ``asset_id`` + ``new_entry_date`` 지정 시 ``actual_entry_date`` 교체.
      ``new_shares > 0`` 과 동시 지정 시 두 필드 모두 갱신된다. 단독 지정도 가능.
    - ``new_cash`` 지정 시 ``shared_cash_actual`` 을 교체.
    - 여러 필드를 동시에 지정하면 한 번에 적용된다.
    - 네 필드가 모두 ``None`` 이면 무효 (validation 에서 걸러짐).

    제약 (fail-fast ValueError):

    - ``new_avg_price`` / ``new_entry_date`` 지정 시 ``asset_id`` 는 필수이다
      (어느 자산의 값을 바꿀지 특정할 수 없으므로).
    - 현재 ``actual_shares == 0`` 인 자산에 ``new_avg_price`` / ``new_entry_date``
      단독 지정은 불가하다 (포지션 없이 평균가 / 진입일만 있는 것은 논리적 오류).
    - ``new_shares=0`` 리셋 규칙은 ``new_avg_price`` / ``new_entry_date`` 보다 우선
      (포지션이 없는데 평균가 / 진입일이 남는 것은 논리적 오류).

    idempotency: ``rtdb_key`` 는 ``applied_balance_adjust_ids.json`` 에 저장되어
    중복 반영을 방지한다.
    """

    rtdb_key: str
    input_time_kst: str  # ISO 8601 KST
    reason: str
    asset_id: str | None = None
    new_shares: int | None = None
    new_avg_price: float | None = None
    new_entry_date: str | None = None  # ISO 8601 날짜
    new_cash: float | None = None


# ============================================================================
# FillDismiss — 앱에서 체결 리마인더를 명시적으로 스킵
# ============================================================================


@dataclass
class FillDismiss:
    """앱이 RTDB ``/fill_dismiss/inbox/`` 에 기록한 체결 스킵 레코드.

    사용자가 시그널에 따른 체결을 입력하지 않기로 결정했을 때 "스킵" 버튼으로
    전송한다. live 는 이 레코드를 처리하여 해당 자산의 ``unfilled_order_date`` 를
    ``None`` 으로 해제하고 리마인더를 중지한다. **잔고는 일체 변경하지 않는다.**

    :class:`ActualFill` / :class:`BalanceAdjust` 와의 차이:

    - fill: 실제 체결 이벤트 — actual 축 가감
    - balance_adjust: 잔고 직접 교체 — actual 축 덮어쓰기
    - fill_dismiss: 리마인더 해제 전용 — actual 축 불변

    idempotency: ``rtdb_key`` 는 ``applied_fill_dismiss_ids.json`` 에 저장되어
    중복 반영을 방지한다.
    """

    rtdb_key: str
    input_time_kst: str  # ISO 8601 KST
    asset_id: str
    reason: str = ""


# ============================================================================
# ModelSync — 앱에서 요청한 model 축 동기화 (model = actual 덮어쓰기)
# ============================================================================


@dataclass
class ModelSync:
    """앱이 RTDB ``/model_sync/inbox/`` 에 기록한 model 동기화 요청.

    사용자가 "지금 내 실제 포지션을 새 출발점으로 삼겠다" 고 선언했을 때 앱이
    UUID 를 key 로 생성하는 요청이다. daily runner 는 이 레코드가 하나라도
    존재하면 **모든 자산의 model 축 (주수 / 평균가 / 진입일) 과 model 현금을
    actual 값으로 일괄 교체**하고, 동기화 시점의 모든 ``pending_order`` /
    ``unfilled_order_date`` 를 ``None`` 으로 해제한다.

    **전체 동기화 전용**: ``asset_id`` 필드는 없다. 자산별 / 선택 동기화는
    지원하지 않는다.

    **사유 필드 없음**: 앱 UI 의 확인 다이얼로그 1 회 만으로 충분하므로
    ``reason`` 필드를 두지 않는다.

    멱등성: "model = actual" 덮어쓰기이므로 같은 요청을 여러 번 처리해도 결과가
    동일하다. 따라서 별도 ``applied_model_sync_ids.json`` 원장은 두지 않고 RTDB
    ``processed`` 플래그만으로 중복 처리를 방지한다 (:class:`ActualFill` /
    :class:`BalanceAdjust` 와 달리 idempotency 원장이 없다).
    """

    rtdb_key: str
    input_time_kst: str  # ISO 8601 KST


# ============================================================================
# SignalDetection — 시그널 감지 결과 (알림/차트 재사용)
# ============================================================================


@dataclass
class SignalDetection:
    """시그널 감지 결과. 알림 본문 및 차트 오버레이에서 재사용된다.

    ``ma_distance_pct`` 는 MA 근접도 지표이며
    ``(close - ma_value) / ma_value`` 로 정의된다 (비율, 음수 가능).

    ``state`` 는 당일 감지된 신호이며 ``AssetLiveState.signal_state`` (누적 원장)
    와는 별도 타입이다. ``"none"`` 은 "오늘 새로 뜬 신호 없음" 을 의미한다.
    """

    state: Literal["buy", "sell", "none"]
    close: float
    upper_band: float | None
    lower_band: float | None
    ma_value: float | None
    ma_distance_pct: float


# ============================================================================
# ChartMeta / ChartSeries — 차트 시계열 (meta + recent + archive/{YYYY})
# ============================================================================


@dataclass
class ChartMeta:
    """앱 차트의 자산별 메타데이터.

    RTDB ``/charts/prices/{asset_id}/meta`` 에 저장된다. 앱은 이 메타를 먼저
    읽어 (a) recent 로딩, (b) 줌아웃 시 어느 archive 연도를 로드할지, (c) 워밍업
    길이 (``ma_window``) 를 판단한다.
    """

    first_date: str  # CSV 의 첫 거래일 (ISO 8601)
    last_date: str  # CSV 의 마지막 거래일 (ISO 8601)
    ma_window: int
    recent_months: int  # /recent 슬라이스가 포함한 개월 수
    archive_years: list[int]  # /archive/{YYYY} 가 존재하는 연도 목록 (오름차순)


@dataclass
class ChartSeries:
    """자산별 차트 슬라이스 (recent 또는 archive/{YYYY}).

    RTDB ``/charts/prices/{asset_id}/recent`` 또는
    ``/charts/prices/{asset_id}/archive/{YYYY}`` 에 저장된다.

    - ``dates`` 는 ISO 8601 날짜 배열이며, ``close`` / ``ma_value`` /
      ``upper_band`` / ``lower_band`` 는 같은 길이 / 같은 인덱스의 값 배열이다.
    - MA 워밍업 구간 (``slot.ma_window - 1`` 개) 은 ``None`` 으로 채워진다.
    - 마커 4 종은 **ISO 날짜 문자열 배열** 이다 (인덱스 기반 아님). 분할된 슬라이스
      사이에서 위치 독립적으로 표현하기 위함.
    """

    dates: list[str]
    close: list[float]
    ma_value: list[float | None]
    upper_band: list[float | None]
    lower_band: list[float | None]
    buy_signals: list[str]
    sell_signals: list[str]
    user_buys: list[str]
    user_sells: list[str]


# ============================================================================
# EquityChartMeta / EquityChartSeries — equity 차트 (/charts/equity/)
# ============================================================================


@dataclass
class EquityChartMeta:
    """앱 equity 차트의 메타데이터.

    RTDB ``/charts/equity/meta`` 에 저장된다. 주가 차트(:class:`ChartMeta`) 와 달리
    포트폴리오 전체를 대상으로 하므로 자산 반복 / ``ma_window`` 가 없다.
    데이터 소스는 Git 정본 ``history/summary.jsonl``.
    """

    first_date: str  # summary.jsonl 의 첫 날짜 (ISO 8601, 운영 시작일)
    last_date: str  # summary.jsonl 의 마지막 날짜 (ISO 8601)
    recent_months: int  # /recent 슬라이스가 포함한 개월 수
    archive_years: list[int]  # /archive/{YYYY} 가 존재하는 연도 목록 (오름차순)


@dataclass
class EquityChartSeries:
    """equity 차트 슬라이스 (recent 또는 archive/{YYYY}).

    RTDB ``/charts/equity/recent`` 또는 ``/charts/equity/archive/{YYYY}`` 에 저장된다.
    주가 차트와 달리 포트폴리오 전체 1 개 시계열만 담으며, 한 경로에 ``dates`` /
    ``model_equity`` / ``actual_equity`` 세 배열을 같은 날짜 인덱스로 저장한다.
    drift 스칼라는 ``/latest/portfolio.drift_pct`` 로 별도 노출되며 시계열 형태로는
    제공하지 않는다 (앱 미사용).

    - 모든 배열은 같은 길이 / 같은 날짜 인덱스.
    - ``model_equity`` / ``actual_equity`` 는 자본금 반올림(``ROUND_CAPITAL = 0`` 자리).
    """

    dates: list[str]
    model_equity: list[float]
    actual_equity: list[float]


# ============================================================================
# DriftReport — model vs actual 차이 리포트
# ============================================================================


@dataclass
class AssetDrift:
    """자산별 drift 지표.

    전체 포트폴리오 drift 요약(:class:`DriftReport`) 의 per_asset 엔트리 한 개를 나타낸다.
    """

    asset_id: str
    model_shares: int
    actual_shares: int
    shares_diff: int  # actual - model
    model_value: float
    actual_value: float
    value_diff: float  # actual - model
    drift_pct: float  # |value_diff| / model_value (비율 0~1, 0.03 = 3%)


@dataclass
class DriftReport:
    """전체 포트폴리오 drift 리포트.

    ``recommendation`` 은 ``DRIFT_WARNING_RATIO`` / ``DRIFT_CORRECTION_RATIO``
    임계값에 따라 "정상" / "주의" / "보정 필요" 중 하나가 된다.
    """

    model_equity: float
    actual_equity: float
    drift_pct: float  # |actual - model| / model (비율 0~1, 0.03 = 3%)
    per_asset: dict[str, AssetDrift]
    recommendation: str


# ============================================================================
# DailyResult — run_daily 의 반환 컨테이너
# ============================================================================


@dataclass
class DailyResult:
    """``daily_runner.run_daily`` 의 반환 컨테이너.

    파일 I/O 전의 순수 계산 결과이며, CLI 계층이 이 객체를 받아 Git push / RTDB /
    알림 발송을 수행한다.
    """

    execution_date: str  # ISO 8601 날짜
    updated_state: LiveState
    updated_applied_fill_ids: dict[str, str]  # fill rtdb_key → ISO 8601 KST 타임스탬프
    updated_applied_balance_adjust_ids: dict[str, str]  # balance_adjust rtdb_key → ISO 타임스탬프
    updated_applied_fill_dismiss_ids: dict[str, str]  # fill_dismiss rtdb_key → ISO 타임스탬프
    signals: dict[str, SignalDetection]
    order_intents: dict[str, OrderIntent]
    executions: ExecutionResult | None
    rebalance_triggered: bool
    model_equity: float
    actual_equity: float
    drift_pct: float
    drift_report: DriftReport
    ma_distances: dict[str, float]
    notification_body: str
    pending_fill_reminders: list[str]
    model_sync_applied: bool  # 이번 run_daily 에서 model_sync Stage 3 이 1 회 이상 적용되었는지 여부


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

    ``ChartSeries.user_buys`` / ``user_sells`` 에 dates 기준 인덱스로 매핑된다.
    """

    date: str  # ISO 8601 날짜
    direction: Literal["buy", "sell"]
