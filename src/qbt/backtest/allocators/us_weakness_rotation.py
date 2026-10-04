"""미국 약세 감지 로테이션 배분 규칙

「VXUS ÷ SPY」 비율이 그 이동평균보다 위면(미국 외 주식이 미국보다 강해지는 추세) VXUS 100%, 아니면 SHY 100%.
공개 전략이 아니라 이 저장소의 보완 전략 설계에서 만든 규칙이다. 파라미터는 Q-2-2XS 와 같은 200일이다.
"""

import math
from collections.abc import Mapping
from datetime import date
from typing import Final

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import ma_col_name
from qbt.common_constants import COL_CLOSE, COL_DATE

ROTATION_RISK_ASSET_ID: Final = "vxus"
ROTATION_SAFE_ASSET_ID: Final = "shy"
ROTATION_ASSET_IDS: Final = (ROTATION_RISK_ASSET_ID, ROTATION_SAFE_ASSET_ID)
ROTATION_BENCHMARK_SERIES_ID: Final = "spy"
ROTATION_SERIES_IDS: Final = (ROTATION_BENCHMARK_SERIES_ID,)


class UsWeaknessRotationAllocator:
    """첫 판단은 첫 호출에서 하고(비율은 매일 정의되므로 시작일에 현금으로 기다리지 않는다),
    그 뒤 전환은 판단일(월 마지막 거래일)에만 한다. 이동평균을 낼 행이 모자라면 판단을 보류한다(None).
    """

    def __init__(self, ma_window: int) -> None:
        self._ma_window = ma_window
        self._ratio_df: pd.DataFrame | None = None
        self._decided = False

    def target_weights(
        self,
        data: Mapping[str, pd.DataFrame],
        i: int,
        current_date: date,  # noqa: ARG002
        is_check_day: bool,
    ) -> Mapping[str, float] | None:
        if self._decided and not is_check_day:
            return None
        ratio_df = self._ratio_with_average(data)
        ratio = float(ratio_df[COL_CLOSE].iloc[i])
        average = float(ratio_df[ma_col_name(self._ma_window)].iloc[i])
        if math.isnan(average):
            return None
        self._decided = True
        if ratio > average:
            return {ROTATION_RISK_ASSET_ID: 1.0, ROTATION_SAFE_ASSET_ID: 0.0}
        return {ROTATION_RISK_ASSET_ID: 0.0, ROTATION_SAFE_ASSET_ID: 1.0}

    def _ratio_with_average(self, data: Mapping[str, pd.DataFrame]) -> pd.DataFrame:
        if self._ratio_df is None:
            risk = data[ROTATION_RISK_ASSET_ID]
            benchmark = data[ROTATION_BENCHMARK_SERIES_ID]
            if risk[COL_DATE].tolist() != benchmark[COL_DATE].tolist():
                raise ValueError(
                    f"{ROTATION_RISK_ASSET_ID} 와 {ROTATION_BENCHMARK_SERIES_ID} 시세의 거래일이 다릅니다 — "
                    "두 시세를 같은 거래일로 맞춰 넘기세요"
                )
            ratio = pd.DataFrame(
                {
                    COL_DATE: risk[COL_DATE].to_numpy(),
                    COL_CLOSE: risk[COL_CLOSE].to_numpy() / benchmark[COL_CLOSE].to_numpy(),
                }
            )
            self._ratio_df = add_single_moving_average(ratio, self._ma_window)
        return self._ratio_df
