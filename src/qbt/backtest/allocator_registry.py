"""배분 규칙 레지스트리

비중이 바뀌는 매매법(AllocatorMethodConfig)이 allocator_id 문자열로 배분 규칙을 조회한다.
strategy_registry 와 같은 모양이며, 포트폴리오 엔진은 이 레지스트리만 거쳐 규칙을 만든다.

배분 규칙 구현은 allocators/ 패키지에 두고 이 레지스트리에 항목을 추가한다. 엔진은 바꾸지 않는다.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

from qbt.backtest.allocators.ewy_buffer_zone import EWY_ASSET_IDS, EwyBufferZoneAllocator
from qbt.backtest.allocators.haa import HAA_ASSET_IDS, HAA_SERIES_IDS, HAA_WARMUP_ROWS, HaaAllocator
from qbt.backtest.allocators.us_weakness_rotation import (
    ROTATION_ASSET_IDS,
    ROTATION_SERIES_IDS,
    UsWeaknessRotationAllocator,
)
from qbt.backtest.constants import (
    FIXED_4P_BUY_BUFFER_ZONE_PCT,
    FIXED_4P_HOLD_DAYS,
    FIXED_4P_MA_WINDOW,
    FIXED_4P_SELL_BUFFER_ZONE_PCT,
)
from qbt.backtest.portfolio_types import AllocatorMethodConfig


class WeightAllocator(Protocol):
    """매매법 자본 대비 종목별 목표 비중을 내는 배분 규칙."""

    def target_weights(
        self,
        data: Mapping[str, pd.DataFrame],
        i: int,
        current_date: date,
        is_check_day: bool,
    ) -> Mapping[str, float] | None:
        """i 번째 거래일 종가 기준 목표 비중을 반환한다. 체결은 다음 거래일 시가다.

        Args:
            data: 매매 자산 시세(자산 id 키)와 신호용 시세(series_id 키). 모두 같은 거래일 행으로 정렬돼 있다
            i: 현재 행 인덱스. i 행까지만 봐야 한다 (미래 참조 금지)
            current_date: 현재 거래일
            is_check_day: 월 마지막 거래일(리밸런싱 판단일) 여부. 월 1회 규칙은 이 날만 판단한다

        Returns:
            {자산 id: 비중} — 비중 0 이상, 합 1 이하, 없는 자산은 0. None 이면 목표를 바꾸지 않는다
        """
        ...


@dataclass(frozen=True)
class AllocatorSpec:
    """배분 규칙 명세.

    Attributes:
        allocator_id: ALLOCATOR_REGISTRY 의 키
        create_allocator: 매매법 설정을 받아 배분 규칙 객체를 만든다
        get_warmup_periods: 판단에 필요한 행 수 — ma_window 와 같은 뜻으로, 이 값 − 1 번째 행부터 판단할 수 있다.
            0 이면 첫 행부터 판단한다
    """

    allocator_id: str
    create_allocator: Callable[[AllocatorMethodConfig], WeightAllocator]
    get_warmup_periods: Callable[[AllocatorMethodConfig], int]


def _require_ids(method: AllocatorMethodConfig, asset_ids: tuple[str, ...], series_ids: tuple[str, ...]) -> None:
    """규칙은 역할을 자산 · 시세 id 로 알아본다(설정에 파라미터 칸이 없다). 설정의 id 가 요구와 정확히 같아야 한다."""
    configured_assets = sorted(asset.asset_id for asset in method.assets)
    configured_series = sorted(series.series_id for series in method.signal_series)
    if configured_assets != sorted(asset_ids) or configured_series != sorted(series_ids):
        raise ValueError(
            f"배분 규칙 '{method.allocator_id}' 은 자산 {sorted(asset_ids)} 과 신호용 시세 {sorted(series_ids)} 를 "
            f"요구합니다 (method_id={method.method_id}, 설정: 자산 {configured_assets} · 시세 {configured_series}). "
            "설정의 id 를 맞추세요"
        )


def _create_haa(method: AllocatorMethodConfig) -> WeightAllocator:
    _require_ids(method, HAA_ASSET_IDS, HAA_SERIES_IDS)
    return HaaAllocator()


def _create_us_weakness_rotation(method: AllocatorMethodConfig) -> WeightAllocator:
    _require_ids(method, ROTATION_ASSET_IDS, ROTATION_SERIES_IDS)
    return UsWeaknessRotationAllocator(ma_window=FIXED_4P_MA_WINDOW)


def _create_ewy_buffer_zone(method: AllocatorMethodConfig) -> WeightAllocator:
    _require_ids(method, EWY_ASSET_IDS, ())
    return EwyBufferZoneAllocator(
        ma_window=FIXED_4P_MA_WINDOW,
        buy_buffer_pct=FIXED_4P_BUY_BUFFER_ZONE_PCT,
        sell_buffer_pct=FIXED_4P_SELL_BUFFER_ZONE_PCT,
        hold_days=FIXED_4P_HOLD_DAYS,
    )


ALLOCATOR_REGISTRY: dict[str, AllocatorSpec] = {
    "haa": AllocatorSpec(
        allocator_id="haa",
        create_allocator=_create_haa,
        get_warmup_periods=lambda method: HAA_WARMUP_ROWS,
    ),
    "us_weakness_rotation": AllocatorSpec(
        allocator_id="us_weakness_rotation",
        create_allocator=_create_us_weakness_rotation,
        get_warmup_periods=lambda method: FIXED_4P_MA_WINDOW,
    ),
    "ewy_buffer_zone": AllocatorSpec(
        allocator_id="ewy_buffer_zone",
        create_allocator=_create_ewy_buffer_zone,
        get_warmup_periods=lambda method: FIXED_4P_MA_WINDOW,
    ),
}
