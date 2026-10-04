"""포트폴리오 백테스트 타입 정의

포트폴리오 백테스트 엔진에서 사용하는 데이터클래스 및 TypedDict를 정의한다.

포함 내용:
- AssetState: 자산별 런타임 상태
- AssetSlotConfig: 자산 슬롯 설정 (frozen=True)
- SlotMethodConfig / AllocatorMethodConfig: 매매법 설정 (frozen=True)
- PortfolioConfig: 포트폴리오 실험 설정 (frozen=True)
- resolve_methods / position_key: 매매법 목록 해석과 결과 파일의 자산 키
- PortfolioAssetResult: 자산별 결과 (거래 내역 + 시그널 데이터)
- PortfolioResult: 포트폴리오 전체 결과
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Final, Literal

import pandas as pd

# ============================================================================
# 자산별 컬럼 접미사 (equity_df / state_log_df 공용)
# ============================================================================
# 포트폴리오 엔진이 생성하는 자산별 컬럼명 규칙. 검증 / CSV 저장 / 대시보드 등
# 모든 호출부가 동일 규칙으로 컬럼을 만들고/읽어야 하므로 SSoT 로 중앙화한다.

ASSET_COL_SUFFIX_CLOSE: Final[str] = "_close"
ASSET_COL_SUFFIX_SHARES: Final[str] = "_shares"
ASSET_COL_SUFFIX_WEIGHT: Final[str] = "_weight"
ASSET_COL_SUFFIX_VALUE: Final[str] = "_value"
ASSET_COL_SUFFIX_SIGNAL_TODAY: Final[str] = "_signal_today"
ASSET_COL_SUFFIX_PENDING_INTENT: Final[str] = "_pending_intent"
ASSET_COL_SUFFIX_EXECUTED_INTENT: Final[str] = "_executed_intent"


def asset_close_col(asset_id: str) -> str:
    """state_log_df 의 ``{asset_id}_close`` 컬럼명을 반환한다."""
    return f"{asset_id}{ASSET_COL_SUFFIX_CLOSE}"


def asset_shares_col(asset_id: str) -> str:
    """equity_df / state_log_df 의 ``{asset_id}_shares`` 컬럼명을 반환한다."""
    return f"{asset_id}{ASSET_COL_SUFFIX_SHARES}"


def asset_weight_col(asset_id: str) -> str:
    """equity_df / state_log_df 의 ``{asset_id}_weight`` 컬럼명을 반환한다."""
    return f"{asset_id}{ASSET_COL_SUFFIX_WEIGHT}"


def asset_value_col(asset_id: str) -> str:
    """equity_df 의 ``{asset_id}_value`` 컬럼명을 반환한다."""
    return f"{asset_id}{ASSET_COL_SUFFIX_VALUE}"


def asset_signal_today_col(asset_id: str) -> str:
    """state_log_df 의 ``{asset_id}_signal_today`` 컬럼명을 반환한다."""
    return f"{asset_id}{ASSET_COL_SUFFIX_SIGNAL_TODAY}"


def asset_pending_intent_col(asset_id: str) -> str:
    """state_log_df 의 ``{asset_id}_pending_intent`` 컬럼명을 반환한다."""
    return f"{asset_id}{ASSET_COL_SUFFIX_PENDING_INTENT}"


def asset_executed_intent_col(asset_id: str) -> str:
    """state_log_df 의 ``{asset_id}_executed_intent`` 컬럼명을 반환한다."""
    return f"{asset_id}{ASSET_COL_SUFFIX_EXECUTED_INTENT}"


# ============================================================================
# 런타임 상태
# ============================================================================


@dataclass
class AssetState:
    """자산별 런타임 상태."""

    position: int  # 보유 수량
    signal_state: Literal["buy", "sell"]  # 현재 시그널 상태


# ============================================================================
# 설정 데이터클래스 (frozen=True: 불변)
# ============================================================================


@dataclass(frozen=True)
class AssetSlotConfig:
    """자산 슬롯 설정.

    이동평균 시그널 소스와 실제 매매 대상을 분리하여 정의한다.
    예: TQQQ는 QQQ 데이터로 시그널을 생성하고, 합성 TQQQ 데이터로 매매한다.

    Attributes:
        asset_id: 자산 식별자 ("qqq", "tqqq", "spy", "gld" 등)
        signal_data_path: 이동평균 계산 대상 데이터 경로 (TQQQ → QQQ 경로)
        trade_data_path: 실제 매매 대상 데이터 경로 (TQQQ → 합성 데이터 경로)
        target_weight: 목표 비중 (예: 0.30 = 30%)
        strategy_id: STRATEGY_REGISTRY 키. 유효하지 않은 값은 엔진이 ValueError로 처리한다.
            "buffer_zone" = 버퍼존 신호에 따라 매수/매도 (기본값).
            "buy_and_hold" = 즉시 매수 후 매도 신호 무시, 항상 투자 상태 유지.
            G 시리즈에서 GLD·TLT B&H 처리에 사용.
        ma_window: 이동평균 기간 (buffer_zone 슬롯에서 사용, 기본값 200)
        buy_buffer_zone_pct: 매수 버퍼존 비율 (buffer_zone 슬롯에서 사용, 기본값 0.03)
        sell_buffer_zone_pct: 매도 버퍼존 비율 (buffer_zone 슬롯에서 사용, 기본값 0.05)
        hold_days: 유지일수 (buffer_zone 슬롯에서 사용, 기본값 3)
    """

    asset_id: str
    signal_data_path: Path
    trade_data_path: Path
    target_weight: float  # 목표 비중 (0.30 = 30%)
    strategy_id: str = "buffer_zone"  # STRATEGY_REGISTRY 키 (예: "buffer_zone", "buy_and_hold")
    # 전략별 파라미터 (buffer_zone에서 사용, buy_and_hold는 무시)
    ma_window: int = 200
    buy_buffer_zone_pct: float = 0.03
    sell_buffer_zone_pct: float = 0.05
    hold_days: int = 3


# 매매법이 둘 이상인 실험의 자산 키 구분자 ({method_id}.{asset_id}). 그래서 id 에 쓸 수 없다
POSITION_KEY_SEPARATOR: Final[str] = "."


@dataclass(frozen=True)
class SlotMethodConfig:
    """고정 비중 슬롯 묶음으로 매매하는 매매법 (예: Q-2-2XS).

    매매법은 자기 몫(자본) · 현금 · 보유 주수를 따로 갖는다. 슬롯의 target_weight 는
    계좌가 아니라 이 매매법 자본 대비 비중이다.

    Attributes:
        method_id: 매매법 식별자 (매매법이 둘 이상이면 결과 키 접두사)
        display_name: 표시 이름
        target_weight: 계좌 대비 목표 몫 (0.70 = 70%)
        asset_slots: 매매법 안의 자산 슬롯
    """

    method_id: str
    display_name: str
    target_weight: float
    asset_slots: tuple[AssetSlotConfig, ...]


@dataclass(frozen=True)
class AllocationAssetConfig:
    """비중이 바뀌는 매매법이 매매하는 자산."""

    asset_id: str
    signal_data_path: Path
    trade_data_path: Path


@dataclass(frozen=True)
class SignalSeriesConfig:
    """배분 규칙이 판단에만 쓰고 보유하지 않는 시세 (예: HAA 의 TIP)."""

    series_id: str
    data_path: Path


@dataclass(frozen=True)
class AllocatorMethodConfig:
    """배분 규칙이 날마다 종목별 목표 비중을 정하는 매매법 (예: HAA).

    Attributes:
        method_id: 매매법 식별자
        display_name: 표시 이름
        target_weight: 계좌 대비 목표 몫
        assets: 매매하는 자산
        allocator_id: allocator_registry.ALLOCATOR_REGISTRY 키
        signal_series: 판단에만 쓰는 시세. series_id 는 자산 id 와 겹칠 수 없다
    """

    method_id: str
    display_name: str
    target_weight: float
    assets: tuple[AllocationAssetConfig, ...]
    allocator_id: str
    signal_series: tuple[SignalSeriesConfig, ...] = ()


type MethodConfig = SlotMethodConfig | AllocatorMethodConfig


@dataclass(frozen=True)
class PortfolioConfig:
    """포트폴리오 실험 설정.

    asset_slots 와 methods 중 정확히 하나를 채운다. asset_slots 는 매매법 하나짜리 실험의
    줄임 표기다(resolve_methods 참고). 슬롯 target_weight 합이 1.0 미만이면 잔여분은 현금이다 (B시리즈).

    리밸런싱 정책은 엔진 레벨 상수로 고정되며 실험 설정으로 바꿀 수 없다
    (월 마지막 거래일 판단, 임계값은 portfolio_rebalance.DEFAULT_REBALANCE_POLICY).
    매매법 사이 비중 되돌리기도 같은 판단일 · 임계값을 쓴다.

    Attributes:
        experiment_name: 실험 식별자 ("portfolio_a2" 등)
        display_name: 표시 이름 ("A-2 (QQQ 30% / SPY 30% / GLD 40%)")
        total_capital: 총 초기 자본금
        result_dir: 결과 저장 디렉토리
        asset_slots: 매매법 하나짜리 실험의 자산 슬롯
        methods: 여러 매매법 (각 매매법 target_weight 합 1.0)
        min_start_date: 이 날짜보다 앞서 시작하지 않는다. 포트폴리오 러너만 읽고 엔진은 읽지 않는다 —
            등록 실험의 기간을 보완 전략 그리드의 비교 기간과 맞출 때 쓴다
    """

    experiment_name: str
    display_name: str
    total_capital: float
    result_dir: Path
    asset_slots: tuple[AssetSlotConfig, ...] = ()
    methods: tuple[MethodConfig, ...] = ()
    min_start_date: date | None = None


def resolve_methods(config: PortfolioConfig) -> tuple[MethodConfig, ...]:
    """실험의 매매법 목록을 반환한다.

    asset_slots 줄임 표기는 method_id = experiment_name, 몫 1.0 인 슬롯 매매법 하나로 읽는다.
    """
    if config.methods:
        return config.methods
    return (SlotMethodConfig(config.experiment_name, config.display_name, 1.0, config.asset_slots),)


def position_key(method_id: str, asset_id: str, *, multi_method: bool) -> str:
    """결과 파일의 자산 키를 반환한다.

    매매법이 하나면 자산 id 그대로라 기존 결과 파일의 열 이름이 바뀌지 않는다.
    """
    if multi_method:
        return f"{method_id}{POSITION_KEY_SEPARATOR}{asset_id}"
    return asset_id


@dataclass(frozen=True)
class PositionKeyInfo:
    """결과 파일의 자산 키 하나의 출처.

    Attributes:
        key: 자산 키 (position_key)
        method_id: 매매법
        method_share: 매매법의 계좌 대비 목표 몫
        asset_id: 자산 id (같은 종목이면 매매법이 달라도 같다)
        slot: 슬롯 매매법의 슬롯. 비중이 바뀌는 매매법 자산이면 None (목표 비중이 날마다 바뀐다)
    """

    key: str
    method_id: str
    method_share: float
    asset_id: str
    slot: AssetSlotConfig | None


def list_position_keys(config: PortfolioConfig) -> list[PositionKeyInfo]:
    """실험의 자산 키를 매매법 · 자산 순서대로 반환한다 (엔진의 결과 열 순서와 같다)."""
    methods = resolve_methods(config)
    multi_method = len(methods) > 1
    infos: list[PositionKeyInfo] = []
    for method in methods:
        if isinstance(method, SlotMethodConfig):
            for slot in method.asset_slots:
                key = position_key(method.method_id, slot.asset_id, multi_method=multi_method)
                infos.append(PositionKeyInfo(key, method.method_id, method.target_weight, slot.asset_id, slot))
        else:
            for asset in method.assets:
                key = position_key(method.method_id, asset.asset_id, multi_method=multi_method)
                infos.append(PositionKeyInfo(key, method.method_id, method.target_weight, asset.asset_id, None))
    return infos


# ============================================================================
# 결과 데이터클래스
# ============================================================================


@dataclass
class PortfolioAssetResult:
    """자산별 결과.

    포지션별 거래 내역과 시그널 데이터를 담는다.
    대시보드에서 자산별 시그널 오버레이 및 거래 마커를 표시하는 데 사용된다.

    Attributes:
        asset_id: 자산 식별자
        trades_df: 해당 자산 거래 내역 DataFrame
        signal_df: 시그널 데이터 DataFrame (OHLCV + MA + 밴드 컬럼 포함)
    """

    asset_id: str
    trades_df: pd.DataFrame
    signal_df: pd.DataFrame


@dataclass
class PortfolioResult:
    """포트폴리오 전체 결과.

    합산 에쿼티, 전 자산 거래 내역, 성과 요약, 자산별 결과를 담는다.

    equity_df 컬럼 명세:
        - Date: 날짜 (date)
        - equity: 합산 에쿼티 (shared_cash + 전 자산 평가액)
        - cash: 미투자 현금
        - drawdown_pct: 드로우다운 (%)
        - {asset_id}_value: 자산별 주식 평가액 (position × close)
        - {asset_id}_weight: 자산별 실제 비중 (value / equity)
        - {asset_id}_signal: 자산별 시그널 ("buy" 또는 "sell")
        - {asset_id}_shares, {asset_id}_avg_price: 자산별 보유 상태
        - {asset_id}_realized_pnl, {asset_id}_unrealized_pnl: 자산별 손익 추적
        - {asset_id}_current_price: 보유 시 value/shares, 미보유 시 0.0 (build_combined_equity SSoT)
        - {asset_id}_return_pct: 보유 + 유효 평균가 시 (current/avg - 1)*100, 그 외 0.0
        - {asset_id}_contribution: realized_pnl + unrealized_pnl (자산별 누적 기여 손익, build_combined_equity SSoT)
        - total_pnl: equity - initial_capital (포트폴리오 누적 손익)
        - total_return_pct: total_pnl / initial_capital * 100 (포트폴리오 누적 수익률 %)
        - rebalanced: 해당일 리밸런싱 실행 여부 (bool)

    trades_df 추가 컬럼:
        - asset_id: 자산 식별자
        - trade_type: 거래 원인 ("signal" 또는 "rebalance")

    state_log_df 컬럼 명세 (매 거래일 1행):
        기본: Date, equity, cash, is_month_end, rebalanced, rebalance_reason
        자산별 ({asset_id}_ 접두사):
        - {aid}_close, {aid}_shares, {aid}_weight: 당일 상태
        - {aid}_signal_today: 당일 시그널 판정 ("buy"/"sell"/"hold")
        - {aid}_pending_intent: 익일 체결 예정 intent_type
        - {aid}_pending_reason, {aid}_pending_delta: pending intent 상세
        - {aid}_executed_intent: 당일 처리된 intent_type (1주 미만이라 0주로 끝나도 기록)
        - {aid}_exec_side, {aid}_exec_shares, {aid}_exec_price: 체결 상세 (0주면 가격 0.0)
        - {aid}_target_weight: 비중이 바뀌는 매매법 자산만 — 그날 매매법 자본 대비 목표 비중

    자산 키({aid}): 매매법이 하나면 자산 id, 둘 이상이면 「매매법.자산」(position_key).

    ledger_df 컬럼 명세 (매 거래일 × 매매법 1행):
        Date, method_id, equity(매매법 자본), cash, share(Σ 매매법 자본 대비 몫), target_share,
        pnl(실현 + 미실현 누적), cost(단독 매매로 매긴 비용 누적), transfers(매매법 사이 이전 누적),
        rebalanced, rebalance_reason("monthly" | "methods" | "")

    netting_df 컬럼 명세 (상계가 있던 날 × 자산 1행, 매매법이 둘 이상일 때만 행이 생긴다):
        Date, asset_id, gross_shares(Σ|Δ|), net_shares(ΣΔ), open_price, savings

    Attributes:
        experiment_name: 실험 식별자
        display_name: 표시 이름
        equity_df: 합산 에쿼티 DataFrame
        trades_df: 전 자산 거래 DataFrame (asset_id, trade_type 컬럼 포함)
        summary: 성과 요약 딕셔너리 (calculate_summary() 호환)
        per_asset: 자산별 결과 리스트
        config: 포트폴리오 설정
        params_json: JSON 저장용 파라미터 딕셔너리
        state_log_df: 일별 상태 로그 DataFrame (디버깅/검증용)
        ledger_df: 매매법별 장부 DataFrame (매매법이 하나여도 만든다 — 검사기가 한 경로로 검사)
        netting_df: 종목 단위 상계 내역 DataFrame
    """

    experiment_name: str
    display_name: str
    equity_df: pd.DataFrame
    trades_df: pd.DataFrame
    summary: Mapping[str, object]
    config: PortfolioConfig
    per_asset: list[PortfolioAssetResult] = field(default_factory=list)
    params_json: dict[str, Any] = field(default_factory=dict)
    state_log_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    ledger_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    netting_df: pd.DataFrame = field(default_factory=pd.DataFrame)
