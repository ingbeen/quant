"""전략 공통 모듈

SignalStrategy Protocol과 예외 클래스를 제공한다.

포함 내용:
- SignalStrategy Protocol: 단일/포트폴리오 엔진이 공통으로 사용하는 전략 인터페이스
- PendingOrderConflictError: Pending Order 충돌 예외

버퍼존 전용 헬퍼(HoldState, compute_bands, detect_buy_signal, detect_sell_signal)는
buffer_zone_helpers.py로 이동하였다.
"""

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd

# ============================================================================
# 예외 클래스
# ============================================================================


class PendingOrderConflictError(Exception):
    """Pending Order 충돌 예외

    이 예외는 백테스트의 Critical Invariant 위반을 나타냅니다.

    발생 조건:
    - pending_order가 이미 존재하는 상태에서 새로운 신호가 발생하려 할 때

    왜 중요한가:
    - pending은 "신호일 종가 → 체결일 시가" 사이의 단일 예약 상태를 나타냄
    - 이 기간에 새로운 신호가 발생하면 논리적 모순 (두 신호가 동시에 존재할 수 없음)
    - 이는 매우 크리티컬한 버그로, 발견 즉시 백테스트를 중단해야 함

    디버깅 방법:
    - 예외 메시지에서 기존 pending 정보 및 새 신호 발생 시점 확인
    - hold_days 로직, 신호 감지 로직에서 타이밍 문제 검토
    """

    pass


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
    - check_buy는 bool만 반환한다 (이전: tuple[bool, HoldState | None]).
    - get_buy_meta()로 매수 메타데이터를 분리 반환한다.
    - 엔진은 전략 내부 상태(밴드, hold_state 등)를 알 필요가 없다.
    """

    def check_buy(
        self,
        signal_df: pd.DataFrame,
        i: int,
        current_date: date,
    ) -> bool:
        """i번째 날 매수 신호 여부를 반환한다. 내부 prev 상태 갱신 포함.

        Args:
            signal_df: 시그널용 DataFrame (MA, Close 컬럼 포함)
            i: 현재 인덱스 (0부터 시작)
            current_date: 현재 날짜 (HoldState.start_date 기록용)

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
