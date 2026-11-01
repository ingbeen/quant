"""버퍼존 V2 전략 모듈

신호와 매매를 같은 티커로 하고, 돌파 뒤 한달을 지켜본 다음에야 움직이는 버퍼존이다.
규칙과 결정 근거는 `docs/research/전략_검증_보고서.md` 부록 N.

기존 버퍼존과 다른 점:
- 유지일 대신 한달(`BUFFER_ZONE_V2_MONTH_DAYS`)을 센다. 그동안 종가가 이평선에 닿지 않아야 한다
- 매수는 한달이 지난 뒤 종가가 상단 아래로 온 날에 신호를 낸다 (돌파를 뒤쫓지 않는다)
- 매도는 예약 매도가 없고, 한달 저점을 손절선으로 세워 엔진이 장중에 체결한다 (`IntradayStopStrategy`)
- 밴드는 상단 · 하단이 같고 레버리지 배수만큼 넓다
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

from qbt.backtest.strategies.buffer_zone_helpers import (
    compute_bands,
    detect_buy_signal,
    detect_sell_signal,
)
from qbt.backtest.strategies.strategy_common import IntradayStopStrategy
from qbt.common_constants import (
    BACKTEST_RESULTS_DIR,
    COL_CLOSE,
    COL_LOW,
    GLD_DATA_PATH,
    QLD_SYNTHETIC_DATA_PATH,
    QQQ_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
    TRADING_DAYS_PER_YEAR,
)

BUFFER_ZONE_V2_MA_WINDOW: Final = 200  # 이동평균 기간
BUFFER_ZONE_V2_BASE_BAND_PCT: Final = 0.05  # 배수 1 의 밴드 비율 (0.05 = 5%)
BUFFER_ZONE_V2_MONTH_DAYS: Final = TRADING_DAYS_PER_YEAR // 12  # 한달 (거래일, 돌파일이 1일째)


@dataclass(frozen=True)
class BufferZoneV2Config:
    """버퍼존 V2 의 자산별 설정. CONFIGS 에 추가하면 러너 · 대시보드에 자동으로 등록된다."""

    strategy_name: str  # 전략 내부 식별자 (예: "buffer_zone_v2_tqqq")
    display_name: str  # 전략 표시명 (예: "버퍼존 V2 (TQQQ)")
    data_path: Path  # 신호 · 매매 공용 시세 경로
    result_dir: Path  # 결과 저장 디렉토리
    leverage: int = 1  # 레버리지 배수 — 밴드가 이 배수만큼 넓어진다

    @property
    def band_pct(self) -> float:
        """상단 · 하단 공통 밴드 비율 (0.15 = 15%)."""
        return BUFFER_ZONE_V2_BASE_BAND_PCT * self.leverage


CONFIGS: list[BufferZoneV2Config] = [
    BufferZoneV2Config(
        strategy_name="buffer_zone_v2_qqq",
        display_name="버퍼존 V2 (QQQ)",
        data_path=QQQ_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_v2_qqq",
    ),
    BufferZoneV2Config(
        strategy_name="buffer_zone_v2_qld",
        display_name="버퍼존 V2 (QLD)",
        data_path=QLD_SYNTHETIC_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_v2_qld",
        leverage=2,
    ),
    BufferZoneV2Config(
        strategy_name="buffer_zone_v2_tqqq",
        display_name="버퍼존 V2 (TQQQ)",
        data_path=TQQQ_SYNTHETIC_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_v2_tqqq",
        leverage=3,
    ),
    BufferZoneV2Config(
        strategy_name="buffer_zone_v2_gld",
        display_name="버퍼존 V2 (GLD)",
        data_path=GLD_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_v2_gld",
    ),
    BufferZoneV2Config(
        strategy_name="buffer_zone_v2_tlt",
        display_name="버퍼존 V2 (TLT)",
        data_path=TLT_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_v2_tlt",
    ),
]


class BufferZoneV2Strategy(IntradayStopStrategy):
    """버퍼존 V2 전략 클래스 (Stateful).

    엔진은 포지션이 없는 날 check_buy, 있는 날 check_sell 을 하루 한 번 순서대로 부른다.
    종가가 이평선에 닿았는지(`≤` · `≥`)만 대기를 푼다 — 장중 고가 · 저가는 대기에 쓰지 않는다.

    Args:
        ma_col: 이평선 열 이름
        band_pct: 상단 밴드 비율 (0.05 = 5%)
        month_days: 한달 길이 (거래일, 돌파일이 1일째)
        sell_band_pct: 하단 밴드 비율. None 이면 상단과 같다
        wait_for_pullback: True 면 한달 뒤 종가가 상단 아래로 온 날, False 면 한달째 날에 신호를 낸다

    Raises:
        ValueError: 밴드 비율이 0 초과 1 미만이 아니거나 한달 길이가 1 미만일 때
    """

    def __init__(
        self,
        ma_col: str,
        band_pct: float,
        month_days: int,
        *,
        sell_band_pct: float | None = None,
        wait_for_pullback: bool = True,
    ) -> None:
        if not 0 < band_pct < 1:
            raise ValueError(f"밴드 비율(band_pct)은 0 초과 1 미만이어야 합니다(0.05 = 5%): {band_pct}")
        if sell_band_pct is not None and not 0 < sell_band_pct < 1:
            raise ValueError(f"매도 밴드 비율(sell_band_pct)은 0 초과 1 미만이어야 합니다(0.05 = 5%): {sell_band_pct}")
        if month_days < 1:
            raise ValueError(f"한달 길이(month_days)는 1 이상이어야 합니다: {month_days}")

        self._ma_col = ma_col
        self._band_pct = band_pct
        self._sell_band_pct = band_pct if sell_band_pct is None else sell_band_pct
        self._month_days = month_days
        self._wait_for_pullback = wait_for_pullback

        # 상향돌파 뒤 센 날 수 (돌파일이 1). None 이면 대기 중이 아니다
        self._buy_days: int | None = None
        # 하향돌파 뒤 (센 날 수, 그동안의 최저 저가). None 이면 대기 중이 아니다
        self._sell_wait: tuple[int, float] | None = None
        self._stop: float | None = None

    def _band_at(self, signal_df: pd.DataFrame, i: int) -> tuple[float, float]:
        return compute_bands(float(signal_df.iloc[i][self._ma_col]), self._band_pct, self._sell_band_pct)

    def check_buy(self, signal_df: pd.DataFrame, i: int) -> bool:
        """i번째 날 매수 신호 여부를 반환한다.

        Args:
            signal_df: 시그널용 DataFrame (ma_col, Close 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)

        Returns:
            True이면 다음 날 시가에 매수
        """
        # 포지션이 없을 때만 불린다 → 직전 보유의 매도 대기 · 손절선은 끝난 것
        self._sell_wait = None
        self._stop = None

        if i == 0:
            return False

        row = signal_df.iloc[i]
        close = float(row[COL_CLOSE])
        upper, _ = self._band_at(signal_df, i)

        if self._buy_days is None:
            prev_upper, _ = self._band_at(signal_df, i - 1)
            if detect_buy_signal(float(signal_df.iloc[i - 1][COL_CLOSE]), close, prev_upper, upper):
                self._buy_days = 1
            return False

        # 닿으면 취소는 한달 동안만이다 — 한달이 지나면 상단 아래로 오는 날을 기다린다
        if self._buy_days < self._month_days:
            if close <= float(row[self._ma_col]):
                self._buy_days = None
                return False
            self._buy_days += 1

        if self._buy_days >= self._month_days and (not self._wait_for_pullback or close < upper):
            self._buy_days = None
            return True
        return False

    def check_sell(self, signal_df: pd.DataFrame, i: int) -> bool:
        """하향돌파 대기와 손절선을 갱신한다. 매도는 장중 손절로만 하므로 늘 False 를 반환한다.

        Args:
            signal_df: 시그널용 DataFrame (ma_col, Close, Low 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)

        Returns:
            False — 예약 매도가 없다
        """
        if i == 0:
            return False

        row = signal_df.iloc[i]
        close = float(row[COL_CLOSE])
        low = float(row[COL_LOW])
        ma = float(row[self._ma_col])

        # 손절선을 그대로 두면 회복 뒤에도 수년 전 가격에 묶여 다음 하락에 팔지 못한다
        if self._stop is not None:
            if close >= ma:
                self._stop = None
            return False

        if self._sell_wait is None:
            _, lower = self._band_at(signal_df, i)
            _, prev_lower = self._band_at(signal_df, i - 1)
            if not detect_sell_signal(float(signal_df.iloc[i - 1][COL_CLOSE]), close, prev_lower, lower):
                return False
            days, lowest = 1, low
        else:
            if close >= ma:
                self._sell_wait = None
                return False
            days, lowest = self._sell_wait[0] + 1, min(self._sell_wait[1], low)

        if days >= self._month_days:
            self._stop = lowest
            self._sell_wait = None
        else:
            self._sell_wait = (days, lowest)
        return False

    def stop_price(self) -> float | None:
        """전날 종가까지 세운 손절선을 반환한다. 없으면 None."""
        return self._stop

    def get_buy_meta(self) -> dict[str, float | int]:
        """check_buy True 직후 호출. TradeRecord 기록용 메타데이터를 반환한다.

        Returns:
            dict: {"buy_buffer_pct": 밴드 비율, "hold_days_used": 한달 길이}
        """
        return {
            "buy_buffer_pct": self._band_pct,
            "hold_days_used": self._month_days,
        }
