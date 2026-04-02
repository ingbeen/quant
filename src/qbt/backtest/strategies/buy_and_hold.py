"""Buy & Hold 벤치마크 전략 모듈

매수 후 보유하는 가장 기본적인 전략을 구현한다.
버퍼존 전략의 성과를 비교하기 위한 벤치마크 용도이다.

팩토리 패턴:
    BuyAndHoldConfig로 티커별 설정을 정의하고,
    runners.create_buy_and_hold_runner()로 각 설정에 대한 실행 함수를 생성한다.
    CONFIGS 리스트에 티커를 추가하면 자동으로 전략이 확장된다.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from qbt.backtest.strategies.strategy_common import SignalStrategy
from qbt.common_constants import (
    BACKTEST_RESULTS_DIR,
    EEM_DATA_PATH,
    EFA_DATA_PATH,
    GLD_DATA_PATH,
    IWM_DATA_PATH,
    QQQ_DATA_PATH,
    SPY_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)

# ============================================================================
# 설정 데이터클래스 및 팩토리
# ============================================================================


@dataclass(frozen=True)
class BuyAndHoldConfig:
    """Buy & Hold 전략의 티커별 설정.

    각 티커(QQQ, TQQQ 등)에 대한 전략 식별 정보와 데이터 경로를 담는다.
    CONFIGS 리스트에 추가하면 자동으로 전략 레지스트리에 등록된다.
    """

    strategy_name: str  # 전략 내부 식별자 (예: "buy_and_hold_qqq")
    display_name: str  # 전략 표시명 (예: "Buy & Hold (QQQ)")
    trade_data_path: Path  # 매매용 데이터 경로
    result_dir: Path  # 결과 저장 디렉토리


# 티커별 설정 목록 (새 티커 추가 시 여기에 한 줄 추가)
CONFIGS: list[BuyAndHoldConfig] = [
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_qqq",
        display_name="Buy & Hold (QQQ)",
        trade_data_path=QQQ_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buy_and_hold_qqq",
    ),
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_tqqq",
        display_name="Buy & Hold (TQQQ)",
        trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buy_and_hold_tqqq",
    ),
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_spy",
        display_name="Buy & Hold (SPY)",
        trade_data_path=SPY_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buy_and_hold_spy",
    ),
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_iwm",
        display_name="Buy & Hold (IWM)",
        trade_data_path=IWM_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buy_and_hold_iwm",
    ),
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_efa",
        display_name="Buy & Hold (EFA)",
        trade_data_path=EFA_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buy_and_hold_efa",
    ),
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_eem",
        display_name="Buy & Hold (EEM)",
        trade_data_path=EEM_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buy_and_hold_eem",
    ),
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_gld",
        display_name="Buy & Hold (GLD)",
        trade_data_path=GLD_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buy_and_hold_gld",
    ),
    BuyAndHoldConfig(
        strategy_name="buy_and_hold_tlt",
        display_name="Buy & Hold (TLT)",
        trade_data_path=TLT_DATA_PATH,
        result_dir=BACKTEST_RESULTS_DIR / "buy_and_hold_tlt",
    ),
]


# ============================================================================
# 전략 클래스
# ============================================================================


class BuyAndHoldStrategy(SignalStrategy):
    """Buy & Hold 전략 클래스 (Stateless).

    SignalStrategy Protocol을 구현한다.
    check_buy는 항상 True, check_sell은 항상 False, get_buy_meta는 빈 dict를 반환한다.

    사용 예:
        strategy = BuyAndHoldStrategy()
        buy = strategy.check_buy(signal_df, i, current_date)  # 항상 True
        sell = strategy.check_sell(signal_df, i)               # 항상 False
    """

    def check_buy(
        self,
        signal_df: pd.DataFrame,
        i: int,
        current_date: date,
    ) -> bool:
        """항상 매수 신호를 반환한다 (파라미터 무시).

        Buy & Hold는 모든 i에서 즉시 매수를 원하므로 항상 True를 반환한다.
        엔진이 이미 position > 0인 경우에는 check_buy 자체를 호출하지 않는다.

        Args:
            signal_df: 시그널 DataFrame (무시)
            i: 현재 인덱스 (무시)
            current_date: 현재 날짜 (무시)

        Returns:
            True — 항상 매수
        """
        return True

    def check_sell(
        self,
        signal_df: pd.DataFrame,
        i: int,
    ) -> bool:
        """항상 매도하지 않음을 반환한다 (파라미터 무시).

        Buy & Hold는 매도하지 않으므로 항상 False를 반환한다.

        Args:
            signal_df: 시그널 DataFrame (무시)
            i: 현재 인덱스 (무시)

        Returns:
            False — 항상 매도하지 않음
        """
        return False

    def get_buy_meta(self) -> dict[str, float | int]:
        """빈 dict를 반환한다. Buy & Hold는 메타데이터가 없다.

        Returns:
            {} — 빈 딕셔너리
        """
        return {}
