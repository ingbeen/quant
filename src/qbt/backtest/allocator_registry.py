"""배분 규칙 레지스트리

비중이 바뀌는 매매법(AllocatorMethodConfig)이 allocator_id 문자열로 배분 규칙을 조회한다.
strategy_registry 와 같은 모양이며, 포트폴리오 엔진은 이 레지스트리만 거쳐 규칙을 만든다.

배분 규칙 구현(HAA · 미국 약세 감지 로테이션 등)은 이 레지스트리에 항목을 추가한다.
엔진은 바꾸지 않는다.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

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


ALLOCATOR_REGISTRY: dict[str, AllocatorSpec] = {}
