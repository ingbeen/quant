"""버퍼존 통합 전략 모듈

config-driven 방식으로 멀티 자산의 버퍼존 전략을 통합 관리한다.
전 자산 4P 고정 파라미터(MA=200, buy=0.03, sell=0.05, hold=3)로 통일한다.

CONFIGS 목록:
    - buffer_zone_tqqq: QQQ 시그널 + TQQQ 합성 매매 (4P 고정, ma_type=ema)
    - buffer_zone_qqq: QQQ 시그널 + QQQ 매매 (4P 고정)
    - buffer_zone_spy ~ buffer_zone_tlt: 교차 자산 검증 (4P 고정)
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import pandas as pd

from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    FIXED_4P_BUY_BUFFER_ZONE_PCT,
    FIXED_4P_HOLD_DAYS,
    FIXED_4P_MA_WINDOW,
    FIXED_4P_SELL_BUFFER_ZONE_PCT,
    MIN_BUY_BUFFER_ZONE_PCT,
    MIN_HOLD_DAYS,
    MIN_SELL_BUFFER_ZONE_PCT,
)
from qbt.backtest.strategies.buffer_zone_helpers import (
    HoldState,
    compute_bands,
    detect_buy_signal,
    detect_sell_signal,
)
from qbt.backtest.strategies.strategy_common import SignalStrategy
from qbt.backtest.types import BufferStrategyParams
from qbt.common_constants import (
    BUFFER_ZONE_EEM_RESULTS_DIR,
    BUFFER_ZONE_EFA_RESULTS_DIR,
    BUFFER_ZONE_GLD_RESULTS_DIR,
    BUFFER_ZONE_IWM_RESULTS_DIR,
    BUFFER_ZONE_QQQ_RESULTS_DIR,
    BUFFER_ZONE_SPY_RESULTS_DIR,
    BUFFER_ZONE_TLT_RESULTS_DIR,
    BUFFER_ZONE_TQQQ_RESULTS_DIR,
    EEM_DATA_PATH,
    EFA_DATA_PATH,
    GLD_DATA_PATH,
    IWM_DATA_PATH,
    QQQ_DATA_PATH,
    SPY_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger

logger = get_logger(__name__)


# ============================================================================
# 파라미터 결정 공통 함수
# ============================================================================


def resolve_buffer_params(
    ma_window: int,
    buy_buffer_zone_pct: float,
    sell_buffer_zone_pct: float,
    hold_days: int,
) -> tuple[BufferStrategyParams, dict[str, str]]:
    """버퍼존 전략의 파라미터를 결정한다.

    전달받은 파라미터로 BufferStrategyParams를 생성한다.

    Args:
        ma_window: 이동평균 기간
        buy_buffer_zone_pct: 매수 버퍼존 비율
        sell_buffer_zone_pct: 매도 버퍼존 비율
        hold_days: 유지일수

    Returns:
        tuple: (params, sources)
            - params: 전략 파라미터
            - sources: 각 파라미터의 출처 딕셔너리

    Raises:
        ValueError: 파라미터 범위 위반 시
    """
    if buy_buffer_zone_pct < MIN_BUY_BUFFER_ZONE_PCT:
        raise ValueError(f"buy_buffer_zone_pct는 {MIN_BUY_BUFFER_ZONE_PCT} 이상이어야 합니다: {buy_buffer_zone_pct}")
    if sell_buffer_zone_pct < MIN_SELL_BUFFER_ZONE_PCT:
        raise ValueError(f"sell_buffer_zone_pct는 {MIN_SELL_BUFFER_ZONE_PCT} 이상이어야 합니다: {sell_buffer_zone_pct}")
    if hold_days < MIN_HOLD_DAYS:
        raise ValueError(f"hold_days는 {MIN_HOLD_DAYS} 이상이어야 합니다: {hold_days}")

    params = BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=ma_window,
        buy_buffer_zone_pct=buy_buffer_zone_pct,
        sell_buffer_zone_pct=sell_buffer_zone_pct,
        hold_days=hold_days,
    )

    sources = {
        "ma_window": "FIXED",
        "buy_buffer_zone_pct": "FIXED",
        "sell_buffer_zone_pct": "FIXED",
        "hold_days": "FIXED",
    }

    logger.debug(
        f"파라미터 결정: ma_window={ma_window}, "
        f"buy_buffer={buy_buffer_zone_pct}, "
        f"sell_buffer={sell_buffer_zone_pct}, "
        f"hold_days={hold_days}"
    )

    return params, sources


# ============================================================================
# 설정 데이터클래스
# ============================================================================


@dataclass(frozen=True)
class BufferZoneConfig:
    """버퍼존 통합 전략의 자산별 설정.

    각 자산에 대한 전략 식별 정보, 데이터 경로, 파라미터를 담는다.
    CONFIGS 리스트에 추가하면 자동으로 전략 레지스트리에 등록된다.

    파라미터는 직접 설정하며, 기본값은 4P 확정 파라미터를 사용한다.
    """

    strategy_name: str  # 전략 내부 식별자 (예: "buffer_zone_tqqq")
    display_name: str  # 전략 표시명 (예: "버퍼존 전략 (TQQQ)")
    signal_data_path: Path  # 시그널용 데이터 경로
    trade_data_path: Path  # 매매용 데이터 경로
    result_dir: Path  # 결과 저장 디렉토리
    ma_window: int = FIXED_4P_MA_WINDOW  # 이동평균 기간
    buy_buffer_zone_pct: float = FIXED_4P_BUY_BUFFER_ZONE_PCT  # 매수 버퍼존 비율
    sell_buffer_zone_pct: float = FIXED_4P_SELL_BUFFER_ZONE_PCT  # 매도 버퍼존 비율
    hold_days: int = FIXED_4P_HOLD_DAYS  # 유지일수
    ma_type: Literal["ema", "sma"] = "ema"  # 이동평균 유형


# ============================================================================
# CONFIGS 리스트
# ============================================================================

CONFIGS: list[BufferZoneConfig] = [
    # --- TQQQ (QQQ 시그널 + TQQQ 합성 매매) ---
    BufferZoneConfig(
        strategy_name="buffer_zone_tqqq",
        display_name="버퍼존 전략 (TQQQ)",
        signal_data_path=QQQ_DATA_PATH,
        trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
        result_dir=BUFFER_ZONE_TQQQ_RESULTS_DIR,
    ),
    # --- QQQ ---
    BufferZoneConfig(
        strategy_name="buffer_zone_qqq",
        display_name="버퍼존 전략 (QQQ)",
        signal_data_path=QQQ_DATA_PATH,
        trade_data_path=QQQ_DATA_PATH,
        result_dir=BUFFER_ZONE_QQQ_RESULTS_DIR,
    ),
    # --- cross-asset ---
    BufferZoneConfig(
        strategy_name="buffer_zone_spy",
        display_name="버퍼존 전략 (SPY)",
        signal_data_path=SPY_DATA_PATH,
        trade_data_path=SPY_DATA_PATH,
        result_dir=BUFFER_ZONE_SPY_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_iwm",
        display_name="버퍼존 전략 (IWM)",
        signal_data_path=IWM_DATA_PATH,
        trade_data_path=IWM_DATA_PATH,
        result_dir=BUFFER_ZONE_IWM_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_efa",
        display_name="버퍼존 전략 (EFA)",
        signal_data_path=EFA_DATA_PATH,
        trade_data_path=EFA_DATA_PATH,
        result_dir=BUFFER_ZONE_EFA_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_eem",
        display_name="버퍼존 전략 (EEM)",
        signal_data_path=EEM_DATA_PATH,
        trade_data_path=EEM_DATA_PATH,
        result_dir=BUFFER_ZONE_EEM_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_gld",
        display_name="버퍼존 전략 (GLD)",
        signal_data_path=GLD_DATA_PATH,
        trade_data_path=GLD_DATA_PATH,
        result_dir=BUFFER_ZONE_GLD_RESULTS_DIR,
    ),
    BufferZoneConfig(
        strategy_name="buffer_zone_tlt",
        display_name="버퍼존 전략 (TLT)",
        signal_data_path=TLT_DATA_PATH,
        trade_data_path=TLT_DATA_PATH,
        result_dir=BUFFER_ZONE_TLT_RESULTS_DIR,
    ),
]


# ============================================================================
# 설정 조회 함수
# ============================================================================


def get_config(strategy_name: str) -> BufferZoneConfig:
    """이름으로 BufferZoneConfig를 조회한다.

    Args:
        strategy_name: 전략 내부 식별자 (예: "buffer_zone_tqqq")

    Returns:
        BufferZoneConfig: 해당 설정

    Raises:
        ValueError: strategy_name이 CONFIGS에 존재하지 않는 경우
    """
    for config in CONFIGS:
        if config.strategy_name == strategy_name:
            return config
    available = [c.strategy_name for c in CONFIGS]
    raise ValueError(f"존재하지 않는 strategy_name: '{strategy_name}'. 사용 가능: {available}")


# ============================================================================
# 파라미터 결정 함수
# ============================================================================


def resolve_params_for_config(
    config: BufferZoneConfig,
) -> tuple[BufferStrategyParams, dict[str, str]]:
    """BufferZoneConfig에 따라 전략 파라미터를 결정한다.

    config의 파라미터를 resolve_buffer_params()에 전달한다.

    Args:
        config: 버퍼존 전략 설정

    Returns:
        tuple: (params, sources)
            - params: 전략 파라미터
            - sources: 각 파라미터의 출처 딕셔너리
    """
    return resolve_buffer_params(
        config.ma_window,
        config.buy_buffer_zone_pct,
        config.sell_buffer_zone_pct,
        config.hold_days,
    )


# ============================================================================
# 전략 클래스
# ============================================================================


class BufferZoneStrategy(SignalStrategy):
    """버퍼존 전략 클래스 (Stateful).

    SignalStrategy Protocol을 구현한다.
    내부 상태(_prev_upper, _prev_lower, _hold_state)를 관리하여 엔진이
    밴드 값을 직접 다룰 필요가 없도록 한다.

    생성자 파라미터:
        ma_col: 이동평균 컬럼명 (예: "ma_200")
        buy_buffer_pct: 매수 버퍼존 비율 (0~1)
        sell_buffer_pct: 매도 버퍼존 비율 (0~1)
        hold_days: 상향돌파 후 유지일수 (0=즉시 신호)
        ma_type: 이동평균 유형 ("ema" 또는 "sma"), 기본값 "ema"

    사용 예:
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 3)
        buy = strategy.check_buy(signal_df, i, current_date)
        sell = strategy.check_sell(signal_df, i)
        if buy:
            meta = strategy.get_buy_meta()
    """

    def __init__(
        self,
        ma_col: str,
        buy_buffer_pct: float,
        sell_buffer_pct: float,
        hold_days: int,
        ma_type: str = "ema",
    ) -> None:
        self._ma_col = ma_col
        self._buy_buffer_pct = buy_buffer_pct
        self._sell_buffer_pct = sell_buffer_pct
        self._hold_days = hold_days
        self._ma_type = ma_type

        # 내부 상태 (None이면 미초기화)
        self._prev_upper: float | None = None
        self._prev_lower: float | None = None
        self._hold_state: HoldState | None = None

        # get_buy_meta() 반환 값 (check_buy → True 직후 갱신)
        self._last_buy_buffer_pct: float = 0.0
        self._last_hold_days_used: int = 0

    def _init_prev_from_row(self, signal_df: pd.DataFrame, idx: int) -> None:
        """idx행 기준으로 _prev_upper/_prev_lower를 초기화한다."""
        ma_val = float(signal_df.iloc[idx][self._ma_col])
        self._prev_upper, self._prev_lower = compute_bands(ma_val, self._buy_buffer_pct, self._sell_buffer_pct)

    def check_buy(
        self,
        signal_df: pd.DataFrame,
        i: int,
        current_date: date,
    ) -> bool:
        """i번째 날 매수 신호 여부를 반환한다. 내부 prev 상태 갱신 포함.

        최초 호출 처리:
        - _prev_upper is None: 미초기화 상태
          - i=0: 현재 행(row[0])으로 초기화 → False 반환 (신호 없음)
          - i>0: row[i-1]로 초기화 → 정상 신호 체크 진행

        이후 호출:
        - hold_days=0: detect_buy_signal로 즉시 신호 판단
        - hold_days>0: 상태머신 처리 (대기/유지/해제)
        - 항상 _prev_upper/_prev_lower를 현재 행 값으로 갱신

        Args:
            signal_df: 시그널용 DataFrame (ma_col, Close 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)
            current_date: 현재 날짜 (HoldState.start_date 기록용)

        Returns:
            True이면 매수 신호
        """
        from qbt.common_constants import COL_CLOSE

        row = signal_df.iloc[i]
        ma_val = float(row[self._ma_col])
        cur_upper, cur_lower = compute_bands(ma_val, self._buy_buffer_pct, self._sell_buffer_pct)
        cur_close = float(row[COL_CLOSE])

        # 최초 호출 처리
        if self._prev_upper is None:
            if i == 0:
                # i=0: 현재 행으로 초기화 후 False 반환
                self._prev_upper = cur_upper
                self._prev_lower = cur_lower
                return False
            else:
                # i>0: i-1 행으로 초기화 후 정상 신호 체크 진행
                self._init_prev_from_row(signal_df, i - 1)

        # 이 시점에서 _prev_upper는 초기화된 상태 (_prev_lower는 check_sell에서 사용)
        prev_upper: float = self._prev_upper  # type: ignore[assignment]
        prev_close = float(signal_df.iloc[i - 1][COL_CLOSE])

        # 현재 행으로 prev 갱신 (신호 판단 후에도 동일 값 사용)
        self._prev_upper = cur_upper
        self._prev_lower = cur_lower

        # 신호 판단
        if self._hold_days == 0:
            # 즉시 신호: detect_buy_signal 결과 반환
            buy = detect_buy_signal(prev_close, cur_close, prev_upper, cur_upper)
            if buy:
                self._last_buy_buffer_pct = self._buy_buffer_pct
                self._last_hold_days_used = 0
            return buy

        # hold_days > 0: 상태머신 처리
        if self._hold_state is not None:
            # 대기 중 — 상단밴드 위 유지 여부 확인
            if cur_close > cur_upper:
                new_days_passed = self._hold_state["days_passed"] + 1
                if new_days_passed >= self._hold_state["hold_days_required"]:
                    # 유지 조건 충족 → 매수 신호
                    self._last_buy_buffer_pct = self._hold_state["buffer_pct"]
                    self._last_hold_days_used = self._hold_state["hold_days_required"]
                    self._hold_state = None
                    return True
                else:
                    # 유지 중 — days_passed 증가
                    self._hold_state = {
                        "start_date": self._hold_state["start_date"],
                        "days_passed": new_days_passed,
                        "buffer_pct": self._hold_state["buffer_pct"],
                        "hold_days_required": self._hold_state["hold_days_required"],
                    }
                    return False
            else:
                # 상단밴드 아래로 이탈 → 상태 해제
                self._hold_state = None
                return False

        # hold_state가 None인 경우 — 상향돌파 감지
        breakout = detect_buy_signal(prev_close, cur_close, prev_upper, cur_upper)
        if breakout:
            # 상향돌파 감지 → HoldState 생성 (아직 매수 아님)
            self._hold_state = {
                "start_date": current_date,
                "days_passed": 0,
                "buffer_pct": self._buy_buffer_pct,
                "hold_days_required": self._hold_days,
            }
        return False

    def check_sell(
        self,
        signal_df: pd.DataFrame,
        i: int,
    ) -> bool:
        """i번째 날 매도 신호 여부를 반환한다. 내부 prev 상태 갱신 포함.

        최초 호출 처리:
        - _prev_lower is None: 미초기화 상태
          - i=0: 현재 행으로 초기화 → False 반환
          - i>0: row[i-1]로 초기화 → 정상 신호 체크 진행

        이후 호출:
        - detect_sell_signal로 하향돌파 감지
        - 항상 _prev_upper/_prev_lower를 현재 행 값으로 갱신

        Args:
            signal_df: 시그널용 DataFrame (ma_col, Close 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)

        Returns:
            True이면 매도 신호
        """
        from qbt.common_constants import COL_CLOSE

        row = signal_df.iloc[i]
        ma_val = float(row[self._ma_col])
        cur_upper, cur_lower = compute_bands(ma_val, self._buy_buffer_pct, self._sell_buffer_pct)
        cur_close = float(row[COL_CLOSE])

        # 최초 호출 처리
        if self._prev_lower is None:
            if i == 0:
                # i=0: 현재 행으로 초기화 후 False 반환
                self._prev_upper = cur_upper
                self._prev_lower = cur_lower
                return False
            else:
                # i>0: i-1 행으로 초기화 후 정상 신호 체크 진행
                self._init_prev_from_row(signal_df, i - 1)

        # 이 시점에서 _prev_lower는 초기화된 상태
        prev_lower: float = self._prev_lower  # type: ignore[assignment]
        prev_close = float(signal_df.iloc[i - 1][COL_CLOSE])

        # 현재 행으로 prev 갱신
        self._prev_upper = cur_upper
        self._prev_lower = cur_lower

        return detect_sell_signal(prev_close, cur_close, prev_lower, cur_lower)

    def get_buy_meta(self) -> dict[str, float | int]:
        """check_buy True 직후 호출. TradeRecord 기록용 메타데이터를 반환한다.

        Returns:
            dict: {"buy_buffer_pct": float, "hold_days_used": int}
        """
        return {
            "buy_buffer_pct": self._last_buy_buffer_pct,
            "hold_days_used": self._last_hold_days_used,
        }
