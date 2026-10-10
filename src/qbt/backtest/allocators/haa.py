"""HAA 배분 규칙 (Keller & Keuning 2023, Hybrid Asset Allocation)

공격 자산 8개 중 모멘텀 점수 상위 4개를 25% 씩 담는다. 카나리아(TIP) 점수가 0 이하면 전부 방어 자산으로,
상위 4개 중 점수가 음수인 자리만 방어 자산으로 간다. 방어 자산은 IEF 와 BIL 중 점수가 높은 쪽이다.
점수는 달력 월말 종가 기준 1 · 3 · 6 · 12개월 수익률의 평균이다(논문과 같다).
"""

from collections.abc import Mapping
from datetime import date
from typing import Final

import pandas as pd

from qbt.common_constants import COL_CLOSE, COL_DATE

# 동점이면 이 순서가 앞선다
HAA_OFFENSIVE_ASSET_IDS: Final = ("spy", "iwm", "vea", "vwo", "vnq", "pdbc", "ief", "tlt")
HAA_DEFENSIVE_ASSET_IDS: Final = ("ief", "bil")
HAA_ASSET_IDS: Final = (*HAA_OFFENSIVE_ASSET_IDS, "bil")
HAA_CANARY_SERIES_ID: Final = "tip"
HAA_SERIES_IDS: Final = (HAA_CANARY_SERIES_ID,)
HAA_LOOKBACK_MONTHS: Final = (1, 3, 6, 12)
HAA_TOP_N: Final = 4
# 12개월 × 21거래일 + 1. 점수가 달력 월말 기준이라 행 수로는 「이전 월말 12개」를 보장할 수 없다 — 모자라면 판단을 보류한다
HAA_WARMUP_ROWS: Final = 253


class HaaAllocator:
    """HAA. 판단일(월 마지막 거래일)에만 판단하고, 이전 월말이 12개 안 되면 판단을 보류한다(None)."""

    def __init__(self) -> None:
        self._months: list[tuple[int, int]] | None = None
        self._month_end_rows: list[int] = []

    def momentum_scores(self, data: Mapping[str, pd.DataFrame], i: int) -> dict[str, float] | None:
        """i 행 종가 기준 자산 · 카나리아별 점수. i 의 달보다 앞선 달의 월말이 12개 안 되면 None."""
        past_month_ends = self._past_month_ends(data, i)
        if len(past_month_ends) < max(HAA_LOOKBACK_MONTHS):
            return None
        scores: dict[str, float] = {}
        for key in (*HAA_ASSET_IDS, *HAA_SERIES_IDS):
            closes = data[key][COL_CLOSE]
            current = float(closes.iloc[i])
            returns = [current / float(closes.iloc[past_month_ends[-months]]) - 1.0 for months in HAA_LOOKBACK_MONTHS]
            scores[key] = sum(returns) / len(returns)
        return scores

    def target_weights(
        self,
        data: Mapping[str, pd.DataFrame],
        i: int,
        current_date: date,
        is_check_day: bool,
    ) -> Mapping[str, float] | None:
        if not is_check_day:
            return None
        scores = self.momentum_scores(data, i)
        if scores is None:
            return None

        defensive = max(HAA_DEFENSIVE_ASSET_IDS, key=lambda key: scores[key])
        weights = {key: 0.0 for key in HAA_ASSET_IDS}
        if scores[HAA_CANARY_SERIES_ID] <= 0:
            weights[defensive] = 1.0
            return weights

        ranked = sorted(HAA_OFFENSIVE_ASSET_IDS, key=lambda key: scores[key], reverse=True)
        for key in ranked[:HAA_TOP_N]:
            weights[key if scores[key] >= 0 else defensive] += 1.0 / HAA_TOP_N
        return weights

    def _past_month_ends(self, data: Mapping[str, pd.DataFrame], i: int) -> list[int]:
        """i 의 달보다 앞선 달들의 마지막 거래일 행 (오름차순).

        그 행들은 i 이하 행만 보고 정해진다 — 다음 행이 i 의 달 안에 있거나 그보다 앞서기 때문이다.
        """
        if self._months is None:
            self._months = [(d.year, d.month) for d in data[HAA_CANARY_SERIES_ID][COL_DATE]]
            self._month_end_rows = [
                row for row in range(len(self._months) - 1) if self._months[row] != self._months[row + 1]
            ]
        current_month = self._months[i]
        return [row for row in self._month_end_rows if self._months[row] < current_month]
