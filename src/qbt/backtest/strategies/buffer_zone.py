"""버퍼존 통합 전략 모듈

config-driven 방식으로 멀티 자산의 버퍼존 전략을 통합 관리한다.
전 자산 4P 고정 파라미터(``FIXED_4P_*`` 상수 참조)로 통일한다. 자산 추가/삭제는
``CONFIGS`` 리스트에 한 줄을 추가/삭제하면 된다 — 자세한 자산 라인업은 본
파일의 ``CONFIGS`` 정의를 직접 확인할 것.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from qbt.backtest.constants import (
    DEFAULT_INITIAL_CAPITAL,
    FIXED_4P_BUY_BUFFER_ZONE_PCT,
    FIXED_4P_HOLD_DAYS,
    FIXED_4P_MA_WINDOW,
    FIXED_4P_SELL_BUFFER_ZONE_PCT,
)
from qbt.backtest.strategies.buffer_zone_helpers import (
    compute_bands,
    detect_buy_signal,
    detect_sell_signal,
)
from qbt.backtest.strategies.strategy_common import SignalStrategy
from qbt.backtest.types import BufferStrategyParams
from qbt.common_constants import (
    BACKTEST_RESULTS_DIR,
    COL_CLOSE,
    GLD_DATA_PATH,
    QQQ_DATA_PATH,
    SPY_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
    UBT_DATA_PATH,
    UGL_DATA_PATH,
)

# 전략 파라미터 하한 (BufferZoneStrategy 생성자가 검증한다)
MIN_BUY_BUFFER_ZONE_PCT = 0.01  # 최소 매수 버퍼존 비율 (0.01 = 1%)
MIN_SELL_BUFFER_ZONE_PCT = 0.01  # 최소 매도 버퍼존 비율 (0.01 = 1%)
MIN_HOLD_DAYS = 0  # 최소 유지조건 (0일 = 버퍼존만 모드)

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
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_tqqq",
    ),
    # --- QQQ ---
    BufferZoneConfig(
        strategy_name="buffer_zone_qqq",
        display_name="버퍼존 전략 (QQQ)",
        signal_data_path=QQQ_DATA_PATH,
        trade_data_path=QQQ_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_qqq",
    ),
    # --- SPY ---
    BufferZoneConfig(
        strategy_name="buffer_zone_spy",
        display_name="버퍼존 전략 (SPY)",
        signal_data_path=SPY_DATA_PATH,
        trade_data_path=SPY_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_spy",
    ),
    # --- GLD ---
    BufferZoneConfig(
        strategy_name="buffer_zone_gld",
        display_name="버퍼존 전략 (GLD)",
        signal_data_path=GLD_DATA_PATH,
        trade_data_path=GLD_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_gld",
    ),
    # --- TLT ---
    BufferZoneConfig(
        strategy_name="buffer_zone_tlt",
        display_name="버퍼존 전략 (TLT)",
        signal_data_path=TLT_DATA_PATH,
        trade_data_path=TLT_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_tlt",
    ),
    # --- UGL (GLD 시그널 + UGL 2x 레버리지 매매) ---
    BufferZoneConfig(
        strategy_name="buffer_zone_ugl",
        display_name="버퍼존 전략 (UGL)",
        signal_data_path=GLD_DATA_PATH,
        trade_data_path=UGL_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_ugl",
    ),
    # --- UBT (TLT 시그널 + UBT 2x 레버리지 매매) ---
    BufferZoneConfig(
        strategy_name="buffer_zone_ubt",
        display_name="버퍼존 전략 (UBT)",
        signal_data_path=TLT_DATA_PATH,
        trade_data_path=UBT_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buffer_zone_ubt",
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
) -> BufferStrategyParams:
    """BufferZoneConfig 의 파라미터로 BufferStrategyParams 를 만든다.

    값의 범위는 보지 않는다 — 버퍼존 비율 · 유지일수는 BufferZoneStrategy 생성자가, 이동평균 기간은
    add_single_moving_average 가 검증한다.

    Args:
        config: 버퍼존 전략 설정

    Returns:
        전략 파라미터
    """
    return BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=config.ma_window,
        buy_buffer_zone_pct=config.buy_buffer_zone_pct,
        sell_buffer_zone_pct=config.sell_buffer_zone_pct,
        hold_days=config.hold_days,
    )


# ============================================================================
# 전략 클래스
# ============================================================================


class BufferZoneStrategy(SignalStrategy):
    """버퍼존 전략 클래스 (Stateful).

    SignalStrategy Protocol을 구현한다.
    내부 상태(_prev_upper, _prev_lower, _hold_days_passed)를 관리하여 엔진이
    밴드 값을 직접 다룰 필요가 없도록 한다.

    생성자 파라미터:
        ma_col: 이동평균 컬럼명 (예: "ma_200")
        buy_buffer_pct: 매수 버퍼존 비율 (0~1)
        sell_buffer_pct: 매도 버퍼존 비율 (0~1)
        hold_days: 상향돌파 후 유지일수 (0=즉시 신호)

    Raises:
        ValueError: 버퍼존 비율이 하한 미만이거나 1 이상일 때, 유지일수가 하한 미만일 때

    사용 예:
        strategy = BufferZoneStrategy("ma_200", 0.03, 0.05, 3)
        buy = strategy.check_buy(signal_df, i)
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
    ) -> None:
        # 전략을 만드는 모든 경로가 이 생성자를 지나므로 범위 검증은 여기 한 곳에 둔다.
        # 범위 밖 값은 예외 없이 다른 결과를 낸다 — 음수 유지일은 유지일 1 처럼 돌고, 1 이상인 매도 버퍼는 밴드가 0 이하라 팔지 않는다
        if not MIN_BUY_BUFFER_ZONE_PCT <= buy_buffer_pct < 1:
            raise ValueError(
                f"매수 버퍼존 비율(buy_buffer_pct)은 {MIN_BUY_BUFFER_ZONE_PCT} 이상 1 미만이어야 합니다(0.03 = 3%): {buy_buffer_pct}"
            )
        if not MIN_SELL_BUFFER_ZONE_PCT <= sell_buffer_pct < 1:
            raise ValueError(
                f"매도 버퍼존 비율(sell_buffer_pct)은 {MIN_SELL_BUFFER_ZONE_PCT} 이상 1 미만이어야 합니다(0.05 = 5%): {sell_buffer_pct}"
            )
        if not hold_days >= MIN_HOLD_DAYS:
            raise ValueError(f"유지일수(hold_days)는 {MIN_HOLD_DAYS} 이상이어야 합니다: {hold_days}")

        self._ma_col = ma_col
        self._buy_buffer_pct = buy_buffer_pct
        self._sell_buffer_pct = sell_buffer_pct
        self._hold_days = hold_days

        # 내부 상태 (None이면 미초기화)
        self._prev_upper: float | None = None
        self._prev_lower: float | None = None
        # 상향돌파 뒤 상단 밴드 위에서 지난 날 수. None 이면 대기 중이 아니다
        self._hold_days_passed: int | None = None

    def _init_prev_from_row(self, signal_df: pd.DataFrame, idx: int) -> None:
        """idx행 기준으로 _prev_upper/_prev_lower를 초기화한다."""
        ma_val = float(signal_df.iloc[idx][self._ma_col])
        self._prev_upper, self._prev_lower = compute_bands(ma_val, self._buy_buffer_pct, self._sell_buffer_pct)

    def _update_bands(
        self,
        signal_df: pd.DataFrame,
        i: int,
    ) -> tuple[float, float, float, float, float, float] | None:
        """밴드를 계산하고 prev 상태를 갱신한다.

        최초 호출(i=0 또는 prev 미초기화) 시 초기화 후 None 반환.
        정상 상태이면 (prev_close, cur_close, prev_upper, cur_upper, prev_lower, cur_lower)
        반환 후 prev 상태를 현재 값으로 갱신한다.

        check_buy와 check_sell 모두 이 메서드를 통해 밴드를 계산하므로
        _prev_upper와 _prev_lower가 항상 동시에 갱신된다.

        주의: 같은 인덱스 i에서 check_buy와 check_sell을 모두 호출하면
        두 번째 호출 시 prev 값이 이미 현재 값으로 덮어써져 돌파 감지가 실패한다.
        엔진은 포지션 유무에 따라 한쪽만 호출해야 한다.

        Args:
            signal_df: 시그널용 DataFrame (ma_col, Close 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)

        Returns:
            None이면 초기화 완료 후 신호 없음.
            6-tuple이면 신호 판단에 필요한 (prev_close, cur_close, prev_upper, cur_upper, prev_lower, cur_lower).
        """
        row = signal_df.iloc[i]
        ma_val = float(row[self._ma_col])
        cur_upper, cur_lower = compute_bands(ma_val, self._buy_buffer_pct, self._sell_buffer_pct)

        # 최초 호출 처리
        if self._prev_upper is None or self._prev_lower is None:
            if i == 0:
                self._prev_upper = cur_upper
                self._prev_lower = cur_lower
                return None
            else:
                self._init_prev_from_row(signal_df, i - 1)

        if self._prev_upper is None or self._prev_lower is None:
            raise RuntimeError(f"내부 불변조건 위반: 이전 밴드가 초기화되지 않았다 (i={i})")
        prev_upper = self._prev_upper
        prev_lower = self._prev_lower
        prev_close = float(signal_df.iloc[i - 1][COL_CLOSE])
        cur_close = float(row[COL_CLOSE])

        # prev 상태를 현재 값으로 갱신
        self._prev_upper = cur_upper
        self._prev_lower = cur_lower

        return (prev_close, cur_close, prev_upper, cur_upper, prev_lower, cur_lower)

    def check_buy(
        self,
        signal_df: pd.DataFrame,
        i: int,
    ) -> bool:
        """i번째 날 매수 신호 여부를 반환한다. 내부 prev 상태 갱신 포함.

        _update_bands()로 밴드 계산 및 prev 갱신을 수행한 후 상향돌파와 유지일을 본다.
        유지일이 0 이면 돌파한 날이 신호다. 그 밖에는 돌파한 날부터 상단 밴드 위에서 유지일만큼 지난 날이 신호이고,
        그 전에 밴드 아래로 내려오면 대기를 푼다.

        Args:
            signal_df: 시그널용 DataFrame (ma_col, Close 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)

        Returns:
            True이면 매수 신호
        """
        ctx = self._update_bands(signal_df, i)
        if ctx is None:
            return False
        prev_close, cur_close, prev_upper, cur_upper, _, _ = ctx

        if self._hold_days_passed is not None:
            if cur_close <= cur_upper:
                self._hold_days_passed = None
                return False
            self._hold_days_passed += 1
            if self._hold_days_passed < self._hold_days:
                return False
            self._hold_days_passed = None
            return True

        if not detect_buy_signal(prev_close, cur_close, prev_upper, cur_upper):
            return False
        if self._hold_days == 0:
            return True
        self._hold_days_passed = 0
        return False

    def check_sell(
        self,
        signal_df: pd.DataFrame,
        i: int,
    ) -> bool:
        """i번째 날 매도 신호 여부를 반환한다. 내부 prev 상태 갱신 포함.

        _update_bands()로 밴드 계산 및 prev 갱신을 수행한 후 하향돌파를 감지한다.

        Args:
            signal_df: 시그널용 DataFrame (ma_col, Close 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)

        Returns:
            True이면 매도 신호
        """
        ctx = self._update_bands(signal_df, i)
        if ctx is None:
            return False
        prev_close, cur_close, _, _, prev_lower, cur_lower = ctx

        return detect_sell_signal(prev_close, cur_close, prev_lower, cur_lower)

    def get_buy_meta(self) -> dict[str, float | int]:
        """check_buy True 직후 호출. TradeRecord 기록용 메타데이터를 반환한다.

        Returns:
            dict: {"buy_buffer_pct": float, "hold_days_used": int}
        """
        return {
            "buy_buffer_pct": self._buy_buffer_pct,
            "hold_days_used": self._hold_days,
        }
