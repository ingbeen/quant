"""전략 실행 모듈

학습 포인트:
1. @dataclass: 데이터를 담는 클래스를 간결하게 정의하는 데코레이터
2. 백테스팅: 과거 데이터로 거래 전략을 시뮬레이션하여 성능 검증
3. 이동평균 전략: 가격이 이동평균선을 돌파하면 매수/매도하는 전략
4. 슬리피지: 실제 체결 가격이 예상 가격과 다른 현상 (수수료와 별도)
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average, calculate_summary
from qbt.backtest.constants import (
    BUFFER_INCREMENT_PER_BUY,
    COL_BUFFER_ZONE_PCT,
    COL_CAGR,
    COL_FINAL_CAPITAL,
    COL_HOLD_DAYS,
    COL_MA_WINDOW,
    COL_MDD,
    COL_RECENT_MONTHS,
    COL_TOTAL_RETURN_PCT,
    COL_TOTAL_TRADES,
    COL_WIN_RATE,
    DAYS_PER_MONTH,
    HOLD_DAYS_INCREMENT_PER_BUY,
    MIN_BUFFER_ZONE_PCT,
    MIN_HOLD_DAYS,
    MIN_VALID_ROWS,
    SLIPPAGE_RATE,
)
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN
from qbt.utils import get_logger
from qbt.utils.parallel_executor import WORKER_CACHE, execute_parallel_with_kwargs, init_worker_cache

logger = get_logger(__name__)


# ============================================================================
# Helper Functions for run_buffer_strategy
# ============================================================================


def _validate_buffer_strategy_inputs(params: "BufferStrategyParams", df: pd.DataFrame, ma_col: str) -> None:
    """
    버퍼존 전략의 입력 파라미터와 데이터를 검증한다.

    Args:
        params: 전략 파라미터
        df: 검증할 DataFrame
        ma_col: 이동평균 컬럼명

    Raises:
        ValueError: 검증 실패 시
    """
    # 1. 파라미터 검증
    if params.ma_window < 1:
        raise ValueError(f"ma_window는 1 이상이어야 합니다: {params.ma_window}")

    if params.buffer_zone_pct < MIN_BUFFER_ZONE_PCT:
        raise ValueError(f"buffer_zone_pct는 {MIN_BUFFER_ZONE_PCT} 이상이어야 합니다: {params.buffer_zone_pct}")

    if params.hold_days < MIN_HOLD_DAYS:
        raise ValueError(f"hold_days는 {MIN_HOLD_DAYS} 이상이어야 합니다: {params.hold_days}")

    if params.recent_months < 0:
        raise ValueError(f"recent_months는 0 이상이어야 합니다: {params.recent_months}")

    # 2. 필수 컬럼 확인
    required_cols = [ma_col, COL_OPEN, COL_CLOSE, COL_DATE]
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")


def _compute_bands(ma_value: float, buffer_zone_pct: float) -> tuple[float, float]:
    """
    이동평균 기준 상하단 밴드를 계산한다.

    Args:
        ma_value: 이동평균 값
        buffer_zone_pct: 버퍼존 비율 (0~1)

    Returns:
        tuple: (upper_band, lower_band)
            - upper_band: 상단 밴드 = ma * (1 + buffer_zone_pct)
            - lower_band: 하단 밴드 = ma * (1 - buffer_zone_pct)
    """
    upper_band = ma_value * (1 + buffer_zone_pct)
    lower_band = ma_value * (1 - buffer_zone_pct)
    return upper_band, lower_band


def _check_pending_conflict(
    pending_order: "PendingOrder | None", signal_type: Literal["buy", "sell"], current_date: date
) -> None:
    """
    Pending order 충돌을 검사한다 (Critical Invariant).

    Args:
        pending_order: 현재 pending order
        signal_type: 발생한 신호 타입
        current_date: 현재 날짜

    Raises:
        PendingOrderConflictError: pending이 이미 존재하는 경우
    """
    if pending_order is not None:
        raise PendingOrderConflictError(
            f"Pending order 충돌 감지: 기존 pending(type={pending_order.order_type}, "
            f"signal_date={pending_order.signal_date}, execute_date={pending_order.execute_date}) "
            f"존재 중 신규 {signal_type} 신호 발생(current_date={current_date})"
        )


def _record_equity(
    current_date: date,
    capital: float,
    position: int,
    close_price: float,
    current_buffer_pct: float,
    upper_band: float | None,
    lower_band: float | None,
) -> dict:
    """
    현재 시점의 equity를 기록한다.

    Args:
        current_date: 현재 날짜
        capital: 현재 보유 현금
        position: 현재 포지션 수량
        close_price: 현재 종가
        current_buffer_pct: 현재 버퍼존 비율
        upper_band: 상단 밴드 (첫 날은 None 가능)
        lower_band: 하단 밴드 (첫 날은 None 가능)

    Returns:
        dict: equity 기록 딕셔너리
    """
    if position > 0:
        equity = capital + position * close_price
    else:
        equity = capital

    return {
        COL_DATE: current_date,
        "equity": equity,
        "position": position,
        "buffer_zone_pct": current_buffer_pct,
        "upper_band": upper_band,
        "lower_band": lower_band,
    }


# ============================================================================
# Exceptions
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


@dataclass
class BaseStrategyParams:
    """전략 파라미터의 기본 클래스.

    학습 포인트:
    1. @dataclass 데코레이터: 클래스를 데이터 컨테이너로 만듦
    2. 타입 힌트와 함께 변수 선언만 하면 __init__ 메서드 자동 생성
    3. 클래스 상속의 기본 - 공통 속성을 부모 클래스에 정의
    """

    initial_capital: float  # 초기 자본금


@dataclass
class BufferStrategyParams(BaseStrategyParams):
    """버퍼존 전략 파라미터를 담는 데이터 클래스.

    학습 포인트:
    - 클래스 상속: (BaseStrategyParams) - 부모 클래스의 속성 상속
    - BaseStrategyParams의 initial_capital도 사용 가능
    """

    ma_window: int  # 이동평균 기간 (예: 20일)
    buffer_zone_pct: float  # 초기 버퍼존 비율 (예: 5.0 = 5%)
    hold_days: int  # 최소 보유 일수 (예: 5일)
    recent_months: int  # 최근 매수 기간 (예: 6개월)


@dataclass
class BuyAndHoldParams:
    """Buy & Hold 전략 파라미터를 담는 데이터 클래스.

    Buy & Hold: 매수 후 그대로 보유하는 가장 기본적인 전략 (벤치마크용)
    """

    initial_capital: float  # 초기 자본금


@dataclass
class PendingOrder:
    """예약된 주문 정보

    신호 발생 시점에 생성되며, 지정된 날짜에 실제 체결됩니다.
    이를 통해 신호 발생일과 체결일을 명확히 분리합니다.

    타입 안정성:
    - order_type은 Literal["buy", "sell"]로 제한하여 타입 체크 시점에 오류 방지
    """

    execute_date: date  # 실행할 날짜
    order_type: Literal["buy", "sell"]  # 주문 유형 (타입 안전)
    price_raw: float  # 슬리피지 적용 전 원가격 (시가)
    signal_date: date  # 신호 발생 날짜 (디버깅/로깅용)
    buffer_zone_pct: float  # 신호 시점의 버퍼존 비율 (0~1)
    hold_days_used: int  # 신호 시점의 유지일수
    recent_buy_count: int  # 신호 시점의 최근 매수 횟수


def _execute_buy_order(
    order: PendingOrder,
    capital: float,
    position: int,
) -> tuple[int, float, float, date, bool]:
    """
    매수 주문을 실행한다.

    Args:
        order: 실행할 매수 주문
        capital: 현재 보유 현금
        position: 현재 포지션 (0이어야 함)

    Returns:
        tuple: (new_position, new_capital, entry_price, entry_date, executed)
            - new_position: 새 포지션 수량
            - new_capital: 새 자본
            - entry_price: 진입 가격 (슬리피지 적용)
            - entry_date: 진입 날짜
            - executed: 실행 여부 (자본 부족 시 False)
    """
    # 슬리피지 적용 (매수 시 +0.3%)
    buy_price = order.price_raw * (1 + SLIPPAGE_RATE)
    shares = int(capital / buy_price)

    if shares > 0:
        buy_amount = shares * buy_price
        new_capital = capital - buy_amount
        return shares, new_capital, buy_price, order.execute_date, True
    else:
        # 자본 부족으로 매수 불가
        return position, capital, 0.0, order.execute_date, False


def _execute_sell_order(
    order: PendingOrder,
    capital: float,
    position: int,
    entry_price: float,
    entry_date: date,
) -> tuple[int, float, dict]:
    """
    매도 주문을 실행한다.

    Args:
        order: 실행할 매도 주문
        capital: 현재 보유 현금
        position: 현재 포지션 수량
        entry_price: 진입 가격
        entry_date: 진입 날짜

    Returns:
        tuple: (new_position, new_capital, trade_record)
            - new_position: 새 포지션 (0)
            - new_capital: 새 자본 (매도 금액 추가)
            - trade_record: 거래 기록 딕셔너리
    """
    # 슬리피지 적용 (매도 시 -0.3%)
    sell_price = order.price_raw * (1 - SLIPPAGE_RATE)
    sell_amount = position * sell_price
    new_capital = capital + sell_amount

    trade_record = {
        "entry_date": entry_date,
        "exit_date": order.execute_date,
        "entry_price": entry_price,
        "exit_price": sell_price,
        "shares": position,
        "pnl": (sell_price - entry_price) * position,
        "pnl_pct": (sell_price - entry_price) / entry_price,
        "exit_reason": "signal",
        "buffer_zone_pct": order.buffer_zone_pct,
        "hold_days_used": order.hold_days_used,
        "recent_buy_count": order.recent_buy_count,
    }

    return 0, new_capital, trade_record


def _detect_buy_signal(
    prev_close: float,
    close: float,
    prev_upper_band: float,
    upper_band: float,
) -> bool:
    """
    상향돌파 신호를 감지한다 (상태머신 방식).

    - hold_days 체크 로직 제거 (메인 루프의 상태머신으로 이동)
    - 돌파 감지만 수행
    - 반환값 단순화: bool만 반환

    Args:
        prev_close: 전일 종가
        close: 당일 종가
        prev_upper_band: 전일 상단 밴드
        upper_band: 당일 상단 밴드

    Returns:
        bool: 상향돌파 감지 여부
    """
    # 상향돌파 체크: 전일 종가 <= 상단밴드 AND 당일 종가 > 상단밴드
    return prev_close <= prev_upper_band and close > upper_band


def _detect_sell_signal(
    prev_close: float,
    close: float,
    prev_lower_band: float,
    lower_band: float,
) -> bool:
    """
    하향돌파 신호를 감지한다 (상태머신 방식).

    - 반환값 단순화: bool만 반환 (일관성 유지)
    - 매도는 hold_days 없음 (즉시 실행)

    Args:
        prev_close: 전일 종가
        close: 당일 종가
        prev_lower_band: 전일 하단 밴드
        lower_band: 당일 하단 밴드

    Returns:
        bool: 하향돌파 감지 여부
    """
    # 하향돌파 체크: 전일 종가 >= 하단밴드 AND 당일 종가 < 하단밴드
    return prev_close >= prev_lower_band and close < lower_band


def run_buy_and_hold(
    df: pd.DataFrame,  # 파라미터 타입 힌트
    params: BuyAndHoldParams,  # 데이터클래스 인스턴스
) -> tuple[pd.DataFrame, dict]:  # 반환 타입: 튜플(DataFrame, 딕셔너리)
    """
    Buy & Hold 벤치마크 전략을 실행한다.

    첫날 시가에 매수, 마지막 날 종가에 매도한다.

    학습 포인트:
    1. tuple 반환: 여러 값을 묶어서 반환 (언패킹 가능)
    2. 데이터클래스 사용: params.initial_capital처럼 속성 접근
    3. 리스트 컴프리헨션: [식 for 변수 in 리스트 if 조건]

    Args:
        df: 주식 데이터 DataFrame
        params: Buy & Hold 파라미터

    Returns:
        tuple: (equity_df, summary)
            - equity_df: 자본 곡선 DataFrame
            - summary: 요약 지표 딕셔너리
    """
    # 1. 파라미터 검증
    if params.initial_capital <= 0:
        raise ValueError(f"initial_capital은 양수여야 합니다: {params.initial_capital}")

    # 2. 필수 컬럼 검증
    # 학습 포인트: 리스트 vs set
    # - 리스트 []: 순서 있음, 중복 가능
    # - set {}: 순서 없음, 중복 불가, 집합 연산 가능
    required_cols = [COL_OPEN, COL_CLOSE, COL_DATE]
    missing = set(required_cols) - set(df.columns)  # 차집합 연산
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 3. 최소 행 수 검증
    if len(df) < MIN_VALID_ROWS:
        raise ValueError(f"유효 데이터 부족: {len(df)}행 (최소 {MIN_VALID_ROWS}행 필요)")

    logger.debug("Buy & Hold 실행 시작")

    # .copy(): DataFrame 복사 (원본 보호)
    # copy() 없이 수정하면 원본도 바뀔 수 있음 (참조 문제)
    df = df.copy()

    # 4. 첫날 시가에 매수
    # 학습 포인트: .iloc[행인덱스][컬럼명] - 인덱스 기반 접근
    buy_price_raw = df.iloc[0][COL_OPEN]  # 첫 번째 행의 시가
    buy_price = buy_price_raw * (1 + SLIPPAGE_RATE)  # 슬리피지 반영 (실제 체결가)

    # int() 함수: 실수를 정수로 변환 (소수점 버림)
    # 주식은 소수점 이하로 살 수 없으므로 정수로 변환
    shares = int(params.initial_capital / buy_price)  # 살 수 있는 주식 수
    buy_amount = shares * buy_price  # 실제 지출 금액
    capital_after_buy = params.initial_capital - buy_amount  # 남은 현금

    # 5. 자본 곡선 계산
    # 학습 포인트: 빈 리스트에 딕셔너리를 누적 추가
    equity_records = []  # 빈 리스트 생성

    # 학습 포인트: .iterrows() - DataFrame을 행 단위로 순회
    # for 인덱스, 행 in df.iterrows():
    # 여기서는 인덱스를 사용하지 않으므로 _ (언더스코어)로 무시
    for _, row in df.iterrows():
        # 현재 총 자산 = 현금 + 주식 평가액
        equity = capital_after_buy + shares * row[COL_CLOSE]

        # 딕셔너리 생성하여 리스트에 추가
        equity_records.append({COL_DATE: row[COL_DATE], "equity": equity, "position": shares})

    # 리스트를 DataFrame으로 변환
    equity_df = pd.DataFrame(equity_records)

    # 6. 마지막 날 종가에 매도
    sell_price_raw = df.iloc[-1][COL_CLOSE]
    sell_price = sell_price_raw * (1 - SLIPPAGE_RATE)
    sell_amount = shares * sell_price

    # 7. 거래 내역 생성 (calculate_summary 호출을 위해)
    trades_df = pd.DataFrame(
        [
            {
                "entry_date": df.iloc[0][COL_DATE],
                "exit_date": df.iloc[-1][COL_DATE],
                "entry_price": buy_price,
                "exit_price": sell_price,
                "shares": shares,
                "pnl": sell_amount - buy_amount,
                "pnl_pct": (sell_price - buy_price) / buy_price,
            }
        ]
    )

    # 8. calculate_summary 호출
    summary = calculate_summary(trades_df, equity_df, params.initial_capital)
    summary["strategy"] = "buy_and_hold"

    logger.debug(f"Buy & Hold 완료: 총 수익률={summary['total_return_pct']:.2f}%, CAGR={summary['cagr']:.2f}%")

    return equity_df, summary


def _run_buffer_strategy_for_grid(
    params: BufferStrategyParams,
) -> dict:
    """
    그리드 서치를 위해 단일 파라미터 조합에 대해 버퍼존 전략을 실행한다.

    병렬 실행을 위한 헬퍼 함수. 예외 발생 시 즉시 전파한다.
    DataFrame은 WORKER_CACHE에서 조회한다.

    Args:
        params: 전략 파라미터

    Returns:
        성과 지표 딕셔너리

    Raises:
        예외 발생 시 즉시 전파
    """
    # WORKER_CACHE에서 DataFrame 조회
    df = WORKER_CACHE["df"]
    _, _, summary = run_buffer_strategy(df, params, log_trades=False)

    return {
        COL_MA_WINDOW: params.ma_window,
        COL_BUFFER_ZONE_PCT: params.buffer_zone_pct,
        COL_HOLD_DAYS: params.hold_days,
        COL_RECENT_MONTHS: params.recent_months,
        COL_TOTAL_RETURN_PCT: summary["total_return_pct"],
        COL_CAGR: summary["cagr"],
        COL_MDD: summary["mdd"],
        COL_TOTAL_TRADES: summary["total_trades"],
        COL_WIN_RATE: summary["win_rate"],
        COL_FINAL_CAPITAL: summary["final_capital"],
    }


def run_grid_search(
    df: pd.DataFrame,
    ma_window_list: list[int],
    buffer_zone_pct_list: list[float],
    hold_days_list: list[int],
    recent_months_list: list[int],
    initial_capital: float = 10_000_000.0,
) -> pd.DataFrame:
    """
    버퍼존 전략 파라미터 그리드 탐색을 수행한다.

    모든 파라미터 조합에 대해 EMA 기반 버퍼존 전략을 실행하고
    성과 지표를 기록한다.

    Args:
        df: 주식 데이터 DataFrame (load_data로 로드된 상태)
        ma_window_list: 이동평균 기간 목록
        buffer_zone_pct_list: 버퍼존 비율 목록
        hold_days_list: 유지조건 일수 목록
        recent_months_list: 최근 매수 기간 목록
        initial_capital: 초기 자본금

    Returns:
        그리드 탐색 결과 DataFrame (각 조합별 성과 지표 포함)
    """
    logger.debug(
        f"그리드 탐색 시작: "
        f"ma_window={ma_window_list}, buffer_zone_pct={buffer_zone_pct_list}, "
        f"hold_days={hold_days_list}, recent_months={recent_months_list}"
    )

    # 1. 모든 이동평균 기간에 대해 EMA 미리 계산
    df = df.copy()
    logger.debug(f"이동평균 사전 계산 (EMA): {sorted(ma_window_list)}")

    for window in ma_window_list:
        df = add_single_moving_average(df, window, ma_type="ema")

    logger.debug("이동평균 사전 계산 완료")

    # 2. 파라미터 조합 생성
    # 학습 포인트: 중첩 for 루프를 활용한 그리드 생성
    # 모든 파라미터 조합을 생성 (예: 3 × 4 × 2 × 2 = 48개)
    param_combinations = []  # 빈 리스트

    # 4중 for 루프: 모든 조합을 순회
    for ma_window in ma_window_list:
        for buffer_zone_pct in buffer_zone_pct_list:
            for hold_days in hold_days_list:
                for recent_months in recent_months_list:
                    # params만 담아 리스트에 추가 (df는 캐시에서 조회)
                    param_combinations.append(
                        {
                            "params": BufferStrategyParams(  # 데이터클래스 인스턴스 생성
                                ma_window=ma_window,
                                buffer_zone_pct=buffer_zone_pct,
                                hold_days=hold_days,
                                recent_months=recent_months,
                                initial_capital=initial_capital,
                            ),
                        }
                    )

    logger.debug(f"총 {len(param_combinations)}개 조합 병렬 실행 시작 (DataFrame 캐시 사용)")

    # 3. 병렬 실행 (DataFrame을 워커 캐시에 저장)
    # ProcessPoolExecutor를 사용해 CPU 병렬 처리
    results = execute_parallel_with_kwargs(
        func=_run_buffer_strategy_for_grid,  # 실행할 함수
        inputs=param_combinations,  # 각 파라미터 조합 (딕셔너리 리스트)
        max_workers=None,  # CPU 코어 수 - 1 (자동 결정)
        initializer=init_worker_cache,  # 공통 워커 초기화 함수
        initargs=({"df": df},),  # 캐시할 데이터
    )

    # 4. 딕셔너리 리스트를 DataFrame으로 변환
    results_df = pd.DataFrame(results)

    # 5. 정렬
    # 학습 포인트: 체이닝 (메서드를 연속으로 호출)
    # .sort_values(): 특정 컬럼 기준 정렬
    # ascending=False: 내림차순 (큰 값이 먼저)
    # .reset_index(drop=True): 인덱스를 0부터 다시 매김
    results_df = results_df.sort_values(by=COL_TOTAL_RETURN_PCT, ascending=False).reset_index(drop=True)

    logger.debug(f"그리드 탐색 완료: {len(results_df)}개 조합 테스트됨")

    return results_df


def calculate_recent_buy_count(
    entry_dates: list,
    current_date,
    recent_months: int,
) -> int:
    """
    최근 N개월 내 매수 횟수를 계산한다.

    Args:
        entry_dates: 모든 매수 날짜 리스트 (datetime.date 객체)
        current_date: 현재 날짜 (datetime.date 객체)
        recent_months: 최근 기간 (개월)

    Returns:
        최근 N개월 내 매수 횟수
    """
    # 최근 N개월을 일수로 환산
    # 정확한 월 계산 대신 근사값 사용 (백테스트 성능 최적화)
    cutoff_date = current_date - timedelta(days=recent_months * DAYS_PER_MONTH)
    count = sum(1 for d in entry_dates if d >= cutoff_date and d < current_date)
    return count


def run_buffer_strategy(
    df: pd.DataFrame,
    params: BufferStrategyParams,
    log_trades: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    버퍼존 전략으로 백테스트를 실행한다.

    롱 온리, 최대 1 포지션 전략을 사용한다.
    버퍼존 상단 돌파 시 매수, 하단 돌파 시 매도하며, 동적으로 버퍼존과 유지조건을 조정한다.

    핵심 실행 규칙:
    - equity = cash + position * close (모든 시점)
    - final_capital = 마지막 equity (평가액 포함)
    - 신호: i일 close, 체결: i+1일 open
    - pending_order: 단일 슬롯 (충돌 시 PendingOrderConflictError)

    Args:
        df: 이동평균이 계산된 DataFrame (add_single_moving_average 적용 필수)
        params: 전략 파라미터
        log_trades: 거래 로그 출력 여부 (기본값: True)

    Returns:
        tuple: (trades_df, equity_df, summary)
            - trades_df: 거래 내역 DataFrame
            - equity_df: 자본 곡선 DataFrame
            - summary: 요약 지표 딕셔너리

    Raises:
        ValueError: 파라미터 검증 실패 또는 필수 컬럼 누락 시
        PendingOrderConflictError: pending 존재 중 신규 신호 발생 시 (Critical Invariant 위반)
    """
    if log_trades:
        logger.debug(f"버퍼존 전략 실행 시작: params={params}")

    # 1. 파라미터 및 데이터 검증
    ma_col = f"ma_{params.ma_window}"
    _validate_buffer_strategy_inputs(params, df, ma_col)

    # 3. 유효 데이터만 사용 (ma_window 이후부터)
    df = df.copy()
    df = df[df[ma_col].notna()].reset_index(drop=True)

    if len(df) < MIN_VALID_ROWS:
        raise ValueError(f"유효 데이터 부족: {len(df)}행 (최소 {MIN_VALID_ROWS}행 필요)")

    # 4. 초기화
    # 학습 포인트: 상태 변수를 사용한 시뮬레이션
    # 변수들이 루프를 돌며 계속 업데이트됨
    capital = params.initial_capital  # 현재 보유 현금
    position = 0  # 보유 주식 수 (0 = 포지션 없음)
    entry_price = 0.0  # 진입 가격 (매수한 가격)
    entry_date = None  # 진입 날짜 (None = 포지션 없음)
    all_entry_dates = []  # 모든 매수 날짜 리스트 (동적 조정용)

    trades = []  # 거래 내역을 담을 빈 리스트
    equity_records = []  # 자본 곡선을 담을 빈 리스트
    pending_order: PendingOrder | None = None  # 예약된 주문 (단일 슬롯)

    # hold_days 상태머신 변수 추가
    # 유지조건 추적을 위한 상태 (None = 유지조건 추적 안 함)
    # 구조: {"start_date": date, "days_passed": int, "buffer_pct": float, "hold_days_required": int}
    hold_state: dict | None = None

    # 매수 시점의 hold_days 정보 저장 (거래 기록용)
    entry_hold_days = 0
    entry_recent_buy_count = 0

    # 4-1. 첫 날 에쿼티 기록 및 prev band 초기화
    first_row = df.iloc[0]
    first_ma_value = first_row[ma_col]
    first_upper_band, first_lower_band = _compute_bands(first_ma_value, params.buffer_zone_pct)

    first_equity_record = _record_equity(
        first_row[COL_DATE],
        params.initial_capital,
        0,
        first_row[COL_CLOSE],
        params.buffer_zone_pct,
        first_upper_band,
        first_lower_band,
    )
    equity_records.append(first_equity_record)

    # 이전 날의 밴드 값 초기화 (첫 날 값으로)
    # i=1부터 시작하므로 i=1의 prev는 i=0이 됨
    prev_upper_band = first_upper_band
    prev_lower_band = first_lower_band

    # 5. 백테스트 루프 (인덱스 1부터 시작 - 전일 비교 필요)
    # 학습 포인트: 인덱스 1부터 시작하는 이유
    # - i-1 (전일 데이터)에 접근하므로 i는 최소 1부터 시작
    # - 돌파 감지는 전일과 당일을 비교하여 판단
    #
    # 버그 수정: 체결 예약 시스템 도입
    # - 신호 발생일과 체결일을 명확히 분리
    # - 순서: (1) 예약 주문 실행 → (2) 에쿼티 기록 → (3) 신호 감지 및 주문 예약
    for i in range(1, len(df)):
        # 당일 행 추출 (전일 행은 헬퍼 함수 내부에서 사용)
        row = df.iloc[i]  # i번째 행 (당일)
        current_date = row[COL_DATE]

        # 5-1. 동적 파라미터 계산
        # 최근 N개월 내 매수 횟수를 기반으로 버퍼존과 유지조건을 동적으로 조정한다.
        # 매수 빈도가 높을수록 더 엄격한 진입 조건을 적용하여 과도한 거래를 방지한다.
        # - recent_months=0: 동적 조정 비활성화
        # - hold_days=0: 유지조건 증가 금지, 버퍼존만 증가
        if params.recent_months > 0:  # 동적 조정 활성화
            recent_buy_count = calculate_recent_buy_count(all_entry_dates, current_date, params.recent_months)
            # 최근 매수가 많을수록 버퍼존 증가 (진입 조건 엄격화)
            current_buffer_pct = params.buffer_zone_pct + (recent_buy_count * BUFFER_INCREMENT_PER_BUY)

            if params.hold_days > 0:
                # 유지조건도 증가 (더 오래 유지해야 매수)
                current_hold_days = params.hold_days + (recent_buy_count * HOLD_DAYS_INCREMENT_PER_BUY)
            else:
                # hold_days=0이면 유지조건 증가 안 함
                current_hold_days = params.hold_days
        else:  # 동적 조정 비활성화
            current_buffer_pct = params.buffer_zone_pct
            current_hold_days = params.hold_days
            recent_buy_count = 0

        # 5-2. 예약된 주문 실행 (당일 실행 대상만)
        # 단일 슬롯: pending_order가 존재하고 실행일이 오늘이면 실행
        if pending_order is not None and pending_order.execute_date == current_date:
            if pending_order.order_type == "buy" and position == 0:
                # 매수 주문 실행
                position, capital, entry_price, entry_date, success = _execute_buy_order(
                    pending_order, capital, position
                )
                if success:
                    all_entry_dates.append(entry_date)
                    # 매수 시점의 hold_days 정보 저장 (거래 기록용)
                    entry_hold_days = pending_order.hold_days_used
                    entry_recent_buy_count = pending_order.recent_buy_count
                    if log_trades:
                        logger.debug(
                            f"매수 체결: {entry_date}, 가격={entry_price:.2f}, "
                            f"수량={position}, 버퍼존={pending_order.buffer_zone_pct:.2%}"
                        )
                # 실행 완료 후 pending_order 초기화
                pending_order = None

            elif pending_order.order_type == "sell" and position > 0:
                # 매도 주문 실행
                assert entry_date is not None, "포지션이 있으면 entry_date는 None이 아니어야 함"
                position, capital, trade_record = _execute_sell_order(
                    pending_order, capital, position, entry_price, entry_date
                )
                # 거래 기록에 매수 시점의 hold_days 정보 사용
                trade_record["hold_days_used"] = entry_hold_days
                trade_record["recent_buy_count"] = entry_recent_buy_count
                trades.append(trade_record)
                if log_trades:
                    logger.debug(
                        f"매도 체결: {pending_order.execute_date}, " f"손익률={trade_record['pnl_pct']*100:.2f}%"
                    )
                # 실행 완료 후 pending_order 초기화
                pending_order = None

        # 5-3. 버퍼존 밴드 계산
        ma_value = row[ma_col]
        upper_band, lower_band = _compute_bands(ma_value, current_buffer_pct)

        # 5-4. 에쿼티 기록 (주문 실행 후 상태)
        equity_record = _record_equity(
            current_date, capital, position, row[COL_CLOSE], current_buffer_pct, upper_band, lower_band
        )
        equity_records.append(equity_record)

        # 5-5. 신호 감지 및 주문 예약 (상태머신 방식)
        # Critical Invariant: pending_order 존재 중 신규 신호 발생 시 예외
        prev_row = df.iloc[i - 1]

        if position == 0 and prev_upper_band is not None:
            # 매수 로직 (상태머신)

            # 5-5-1. 유지조건 체크 (hold_state가 존재하면)
            if hold_state is not None:
                # 유지조건 검증: 현재 종가가 상단 밴드 위에 있는가?
                if row[COL_CLOSE] > upper_band:
                    # 조건 통과: days_passed 증가
                    hold_state["days_passed"] += 1

                    # 유지조건 완료 확인
                    if hold_state["days_passed"] >= hold_state["hold_days_required"]:
                        # 유지조건 완료 -> pending_order 생성
                        _check_pending_conflict(pending_order, "buy", current_date)

                        # 다음 날 시가에 매수 예약
                        if i + 1 < len(df):
                            buy_row = df.iloc[i + 1]
                            pending_order = PendingOrder(
                                execute_date=buy_row[COL_DATE],
                                order_type="buy",
                                price_raw=buy_row[COL_OPEN],
                                signal_date=current_date,
                                buffer_zone_pct=hold_state["buffer_pct"],
                                hold_days_used=hold_state["hold_days_required"],
                                recent_buy_count=recent_buy_count,
                            )

                        # hold_state 초기화
                        hold_state = None
                else:
                    # 조건 실패: hold_state 리셋
                    hold_state = None

            # 5-5-2. 상향돌파 감지 (hold_state가 없을 때만)
            if hold_state is None:
                breakout_detected = _detect_buy_signal(
                    prev_close=prev_row[COL_CLOSE],
                    close=row[COL_CLOSE],
                    prev_upper_band=prev_upper_band,
                    upper_band=upper_band,
                )

                if breakout_detected:
                    if current_hold_days > 0:
                        # hold_days > 0: 유지조건 추적 시작
                        hold_state = {
                            "start_date": current_date,
                            "days_passed": 0,
                            "buffer_pct": current_buffer_pct,
                            "hold_days_required": current_hold_days,
                        }
                    else:
                        # hold_days = 0: 즉시 다음 날 시가에 매수 예약
                        _check_pending_conflict(pending_order, "buy", current_date)

                        if i + 1 < len(df):
                            buy_row = df.iloc[i + 1]
                            pending_order = PendingOrder(
                                execute_date=buy_row[COL_DATE],
                                order_type="buy",
                                price_raw=buy_row[COL_OPEN],
                                signal_date=current_date,
                                buffer_zone_pct=current_buffer_pct,
                                hold_days_used=0,
                                recent_buy_count=recent_buy_count,
                            )

        elif position > 0 and prev_lower_band is not None:
            # 매도 로직 (hold_days 없음, 즉시 실행)
            breakout_detected = _detect_sell_signal(
                prev_close=prev_row[COL_CLOSE],
                close=row[COL_CLOSE],
                prev_lower_band=prev_lower_band,
                lower_band=lower_band,
            )

            if breakout_detected:
                # Critical Invariant 체크
                _check_pending_conflict(pending_order, "sell", current_date)

                # 다음 날 시가에 매도 예약
                if i + 1 < len(df):
                    sell_row = df.iloc[i + 1]
                    pending_order = PendingOrder(
                        execute_date=sell_row[COL_DATE],
                        order_type="sell",
                        price_raw=sell_row[COL_OPEN],
                        signal_date=current_date,
                        buffer_zone_pct=current_buffer_pct,
                        hold_days_used=0,  # 매도는 hold_days 없음
                        recent_buy_count=recent_buy_count,
                    )

        # 5-6. 다음 루프를 위해 전일 밴드 저장
        prev_upper_band = upper_band
        prev_lower_band = lower_band

    # 6. 백테스트 종료 (강제청산 없음)
    # 마지막 날 포지션이 남아있어도 그대로 둠
    # equity_df의 마지막 equity가 final_capital이 됨 (cash + position × last_close)

    # 7. 결과 DataFrame 생성
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_records)

    # 8. 요약 지표 계산
    summary = calculate_summary(trades_df, equity_df, params.initial_capital)
    summary["strategy"] = "buffer_zone"
    summary["ma_window"] = params.ma_window
    summary["buffer_zone_pct"] = params.buffer_zone_pct
    summary["hold_days"] = params.hold_days

    if log_trades:
        logger.debug(
            f"버퍼존 전략 완료: 총 거래={summary['total_trades']}, 총 수익률={summary['total_return_pct']:.2f}%"
        )

    return trades_df, equity_df, summary
