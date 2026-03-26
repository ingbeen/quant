"""포트폴리오 백테스트 타입 정의

포트폴리오 백테스트 엔진에서 사용하는 데이터클래스 및 TypedDict를 정의한다.

포함 내용:
- AssetSlotConfig: 자산 슬롯 설정 (frozen=True)
- PortfolioConfig: 포트폴리오 실험 설정 (frozen=True)
- PortfolioAssetResult: 자산별 결과 (거래 내역 + 시그널 데이터)
- PortfolioResult: 포트폴리오 전체 결과
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

# ============================================================================
# 설정 데이터클래스 (frozen=True: 불변)
# ============================================================================


@dataclass(frozen=True)
class AssetSlotConfig:
    """자산 슬롯 설정.

    EMA-200 시그널 소스와 실제 매매 대상을 분리하여 정의한다.
    예: TQQQ는 QQQ 데이터로 시그널을 생성하고, 합성 TQQQ 데이터로 매매한다.

    Attributes:
        asset_id: 자산 식별자 ("qqq", "tqqq", "spy", "gld" 등)
        signal_data_path: EMA-200 계산 대상 데이터 경로 (TQQQ → QQQ 경로)
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
        ma_type: 이동평균 유형 (buffer_zone 슬롯에서 사용, 기본값 "ema")
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
    ma_type: Literal["ema", "sma"] = "ema"


@dataclass(frozen=True)
class PortfolioConfig:
    """포트폴리오 실험 설정.

    복수 자산의 목표 비중, 리밸런싱 정책을 담는다.
    전략 파라미터(ma_window, buffer_pct 등)는 슬롯 레벨(AssetSlotConfig)로 이동하였다.
    target_weight 합이 1.0 미만인 경우 잔여분은 현금으로 유지된다 (B시리즈).

    리밸런싱 정책은 엔진 레벨 상수로 고정된다:
        - 월 첫 거래일: MONTHLY_REBALANCE_THRESHOLD_RATE (10%) 초과 시 트리거
        - 매일: DAILY_REBALANCE_THRESHOLD_RATE (20%) 초과 시 긴급 트리거

    Attributes:
        experiment_name: 실험 식별자 ("portfolio_a2" 등)
        display_name: 표시 이름 ("A-2 (QQQ 30% / SPY 30% / GLD 40%)")
        asset_slots: 자산 슬롯 설정 튜플
        total_capital: 총 초기 자본금
        result_dir: 결과 저장 디렉토리
    """

    experiment_name: str
    display_name: str
    asset_slots: tuple[AssetSlotConfig, ...]
    total_capital: float
    result_dir: Path


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
        - rebalanced: 해당일 리밸런싱 실행 여부 (bool)

    trades_df 추가 컬럼:
        - asset_id: 자산 식별자
        - trade_type: 거래 원인 ("signal" 또는 "rebalance")

    Attributes:
        experiment_name: 실험 식별자
        display_name: 표시 이름
        equity_df: 합산 에쿼티 DataFrame
        trades_df: 전 자산 거래 DataFrame (asset_id, trade_type 컬럼 포함)
        summary: 성과 요약 딕셔너리 (calculate_summary() 호환)
        per_asset: 자산별 결과 리스트
        config: 포트폴리오 설정
        params_json: JSON 저장용 파라미터 딕셔너리
    """

    experiment_name: str
    display_name: str
    equity_df: pd.DataFrame
    trades_df: pd.DataFrame
    summary: Mapping[str, object]
    per_asset: list[PortfolioAssetResult] = field(default_factory=list)
    config: PortfolioConfig = field(
        default_factory=lambda: PortfolioConfig(
            experiment_name="",
            display_name="",
            asset_slots=(),
            total_capital=0.0,
            result_dir=Path("."),
        )
    )
    params_json: dict[str, Any] = field(default_factory=dict)
