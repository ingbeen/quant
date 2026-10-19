"""전략 공통 모듈

단일/포트폴리오 엔진이 공통으로 사용하는 전략 인터페이스(SignalStrategy Protocol)를 제공한다.

버퍼존 전용 헬퍼(compute_bands, detect_buy_signal, detect_sell_signal)는
buffer_zone_helpers.py 에 있다.
"""

from typing import Protocol, runtime_checkable

import pandas as pd

# ============================================================================
# SignalStrategy Protocol
# ============================================================================


@runtime_checkable
class SignalStrategy(Protocol):
    """전략 인터페이스 Protocol.

    단일 백테스트 엔진과 포트폴리오 엔진이 공통으로 사용하는 전략 인터페이스.
    이 Protocol을 준수하는 클래스는 check_buy, check_sell, get_buy_meta 메서드를 구현해야 한다.

    설계 원칙:
    - 전략은 Stateful: 내부 _prev 상태를 관리하며, i 인덱스로 signal_df에 직접 접근한다.
    - check_buy는 bool만 반환하고, 매수 메타데이터는 get_buy_meta()가 따로 반환한다.
    - 엔진은 전략 내부 상태(밴드, 유지일 대기 등)를 알 필요가 없다.
    """

    def check_buy(
        self,
        signal_df: pd.DataFrame,
        i: int,
    ) -> bool:
        """i번째 날 매수 신호 여부를 반환한다. 내부 prev 상태 갱신 포함.

        Args:
            signal_df: 시그널용 DataFrame (MA, Close 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)

        Returns:
            True이면 이번 날짜에 buy pending을 생성해야 함

        계약:
            - i=0 최초 호출: 내부 상태 초기화 후 False 반환
            - i>0 최초 호출: signal_df.iloc[i-1]로 초기화 후 정상 신호 체크
            - 이후 호출: prev 상태 기반 신호 감지
        """
        ...

    def check_sell(
        self,
        signal_df: pd.DataFrame,
        i: int,
    ) -> bool:
        """i번째 날 매도 신호 여부를 반환한다. 내부 prev 상태 갱신 포함.

        Args:
            signal_df: 시그널용 DataFrame (MA, Close 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)

        Returns:
            True이면 이번 날짜에 sell pending을 생성해야 함
        """
        ...

    def get_buy_meta(self) -> dict[str, float | int]:
        """check_buy True 직후 호출한다. TradeRecord 기록용 메타데이터를 반환한다.

        Returns:
            dict: 매수 메타데이터
                - BufferZoneStrategy: {"buy_buffer_pct": float, "hold_days_used": int}
                - BuyAndHoldStrategy: {}
        """
        ...
