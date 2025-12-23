"""전략 실행 모듈

학습 포인트:
1. @dataclass: 데이터를 담는 클래스를 간결하게 정의하는 데코레이터
2. 백테스팅: 과거 데이터로 거래 전략을 시뮬레이션하여 성능 검증
3. 이동평균 전략: 가격이 이동평균선을 돌파하면 매수/매도하는 전략
4. 슬리피지: 실제 체결 가격이 예상 가격과 다른 현상 (수수료와 별도)
"""

from dataclasses import dataclass
from datetime import timedelta

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
    MIN_BUFFER_ZONE_PCT,
    MIN_HOLD_DAYS,
    MIN_VALID_ROWS,
    SLIPPAGE_RATE,
)
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN
from qbt.utils import get_logger
from qbt.utils.parallel_executor import execute_parallel_with_kwargs

logger = get_logger(__name__)


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
    df: pd.DataFrame,
    params: BufferStrategyParams,
) -> dict | None:
    """
    그리드 서치를 위해 단일 파라미터 조합에 대해 버퍼존 전략을 실행한다.

    병렬 실행을 위한 헬퍼 함수. 예외 발생 시 None을 반환한다.

    Args:
        df: 이동평균이 계산된 DataFrame
        params: 전략 파라미터

    Returns:
        성과 지표 딕셔너리 또는 None (실패 시)
    """
    try:
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
    except Exception:
        # 병렬 실행에서는 로그 생략 (프로세스 간 로거 공유 이슈)
        return None


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
                    # 딕셔너리에 df와 params 객체를 담아 리스트에 추가
                    param_combinations.append(
                        {
                            "df": df,  # 모든 조합에 동일한 DataFrame 전달
                            "params": BufferStrategyParams(  # 데이터클래스 인스턴스 생성
                                ma_window=ma_window,
                                buffer_zone_pct=buffer_zone_pct,
                                hold_days=hold_days,
                                recent_months=recent_months,
                                initial_capital=initial_capital,
                            ),
                        }
                    )

    logger.debug(f"총 {len(param_combinations)}개 조합 병렬 실행 시작")

    # 3. 병렬 실행
    # ProcessPoolExecutor를 사용해 CPU 병렬 처리
    results = execute_parallel_with_kwargs(
        func=_run_buffer_strategy_for_grid,  # 실행할 함수
        inputs=param_combinations,  # 각 파라미터 조합 (딕셔너리 리스트)
        max_workers=None,  # CPU 코어 수 - 1 (자동 결정)
    )

    # 4. 실패 건 필터링
    # 학습 포인트: 리스트 컴프리헨션 with 조건
    # [식 for 변수 in 리스트 if 조건]
    # r이 None이 아닌 것만 선택 (성공한 결과만 유지)
    results = [r for r in results if r is not None]

    # 딕셔너리 리스트를 DataFrame으로 변환
    results_df = pd.DataFrame(results)

    # 5. 정렬
    if not results_df.empty:  # DataFrame이 비어있지 않으면
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


def check_hold_condition(
    df: pd.DataFrame,
    break_idx: int,
    hold_days: int,
    ma_col: str,
    buffer_pct: float,
) -> bool:
    """
    상향돌파 이후 유지조건을 확인한다.

    break_idx 이후 hold_days 일 동안 종가가 상단 밴드 위에 있는지 확인한다.
    돌파 시점의 buffer_pct를 고정하여 사용한다.

    Args:
        df: 데이터프레임
        break_idx: 돌파 발생 인덱스
        hold_days: 유지해야 할 일수
        ma_col: 이동평균 컬럼명
        buffer_pct: 버퍼존 비율 (돌파 시점 고정값)

    Returns:
        유지조건 만족 여부
    """
    # break_idx 다음 날부터 hold_days 일간 체크
    start_idx = break_idx + 1
    end_idx = start_idx + hold_days

    if end_idx > len(df):
        return False  # 데이터 부족

    for i in range(start_idx, end_idx):
        row = df.iloc[i]
        upper_band = row[ma_col] * (1 + buffer_pct)

        if row[COL_CLOSE] <= upper_band:
            return False  # 유지 실패

    return True  # 모든 날 유지 성공


def run_buffer_strategy(
    df: pd.DataFrame,
    params: BufferStrategyParams,
    log_trades: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    버퍼존 전략으로 백테스트를 실행한다.

    롱 온리, 최대 1 포지션 전략을 사용한다.
    버퍼존 상단 돌파 시 매수, 하단 돌파 시 매도하며, 동적으로 버퍼존과 유지조건을 조정한다.

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
    """
    if log_trades:
        logger.debug(f"버퍼존 전략 실행 시작: params={params}")

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
    ma_col = f"ma_{params.ma_window}"
    required_cols = [ma_col, COL_OPEN, COL_CLOSE, COL_DATE]
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

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

    # 이전 날의 밴드 값 (돌파 감지용)
    # None으로 초기화하여 첫 날에는 매매하지 않도록 함
    prev_upper_band = None
    prev_lower_band = None

    # 5. 백테스트 루프 (인덱스 1부터 시작 - 전일 비교 필요)
    # 학습 포인트: 인덱스 1부터 시작하는 이유
    # - i-1 (전일 데이터)에 접근하므로 i는 최소 1부터 시작
    # - 돌파 감지는 전일과 당일을 비교하여 판단
    for i in range(1, len(df)):
        # 당일 행과 전일 행 추출
        row = df.iloc[i]  # i번째 행 (당일)
        prev_row = df.iloc[i - 1]  # i-1번째 행 (전일)
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
                current_hold_days = params.hold_days + recent_buy_count
            else:
                # hold_days=0이면 유지조건 증가 안 함
                current_hold_days = params.hold_days
        else:  # 동적 조정 비활성화
            current_buffer_pct = params.buffer_zone_pct
            current_hold_days = params.hold_days
            recent_buy_count = 0

        # 5-2. 버퍼존 밴드 계산
        # 학습 포인트: 이동평균을 기준으로 상하 밴드 계산
        ma_value = row[ma_col]  # 현재 이동평균 값
        # 상단 밴드 = 이동평균 × (1 + 버퍼존%)
        upper_band = ma_value * (1 + current_buffer_pct)
        # 하단 밴드 = 이동평균 × (1 - 버퍼존%)
        lower_band = ma_value * (1 - current_buffer_pct)

        # 5-3. 매수 신호 체크 (포지션 없을 때)
        # 학습 포인트: and 연산자 - 모든 조건이 True여야 함
        # position == 0: 현재 포지션 없음
        # prev_upper_band is not None: 이전 밴드 값이 존재 (첫 날 제외)
        if position == 0 and prev_upper_band is not None:
            # 5-3-1. 상향돌파 감지
            # 학습 포인트: 돌파의 정의
            # 전일 종가가 상단 밴드 이하였다가 당일 종가가 상단 밴드를 초과하는 경우
            # <= 와 > 를 함께 사용하여 "경계를 넘는 순간"을 포착
            if prev_row[COL_CLOSE] <= prev_upper_band and row[COL_CLOSE] > upper_band:
                # 5-3-2. 유지조건 확인
                # 돌파 이후 일정 기간 동안 종가가 상단 밴드 위를 유지하는지 확인한다.
                if current_hold_days > 0:  # 유지조건이 있을 때
                    hold_satisfied = check_hold_condition(df, i, current_hold_days, ma_col, current_buffer_pct)

                    # 학습 포인트: pass - 아무것도 하지 않음 (문법상 필요)
                    # if 문에는 최소 1개 이상의 문장이 필요하므로 pass 사용
                    if not hold_satisfied:
                        # 유지조건 미충족 - 매수 스킵
                        pass  # 아무것도 안 함
                    else:
                        # 5-3-3. 유지조건 충족 - 익일 시가 매수
                        # 유지조건 마지막 날 다음날 시가에 진입한다.
                        # 학습 포인트: 인덱스 계산
                        # i (돌파일) + current_hold_days (유지일수) + 1 (다음날)
                        buy_idx = i + current_hold_days + 1

                        # 학습 포인트: 경계 검사 - 인덱스가 범위를 벗어나는지 확인
                        if buy_idx < len(df):  # 데이터가 충분한지 확인
                            buy_row = df.iloc[buy_idx]  # 매수할 날의 데이터
                            buy_price_raw = buy_row[COL_OPEN]  # 시가
                            buy_price = buy_price_raw * (1 + SLIPPAGE_RATE)  # 슬리피지 반영
                            shares = int(capital / buy_price)  # 살 수 있는 주식 수

                            if shares > 0:  # 주식을 살 수 있는지 확인
                                buy_amount = shares * buy_price  # 총 구매 금액
                                capital -= buy_amount  # 현금 차감

                                # 포지션 상태 업데이트
                                position = shares
                                entry_price = buy_price
                                entry_date = buy_row[COL_DATE]
                                all_entry_dates.append(entry_date)  # 리스트에 추가

                                if log_trades:
                                    logger.debug(
                                        f"매수: {entry_date}, 가격={buy_price:.2f}, "
                                        f"수량={shares}, 버퍼존={current_buffer_pct:.2%}, "
                                        f"유지조건={current_hold_days}일"
                                    )
                            else:
                                logger.debug(f"자금 부족으로 매수 불가: {current_date}, 자본={capital:.0f}, 가격={buy_price:.2f}")
                else:
                    # 5-3-4. 버퍼존만 모드 (hold_days = 0)
                    # 유지조건 없이 돌파 즉시 익일 시가 매수
                    buy_idx = i + 1
                    if buy_idx < len(df):
                        buy_row = df.iloc[buy_idx]
                        buy_price_raw = buy_row[COL_OPEN]
                        buy_price = buy_price_raw * (1 + SLIPPAGE_RATE)
                        shares = int(capital / buy_price)

                        if shares > 0:
                            buy_amount = shares * buy_price
                            capital -= buy_amount

                            position = shares
                            entry_price = buy_price
                            entry_date = buy_row[COL_DATE]
                            all_entry_dates.append(entry_date)

                            if log_trades:
                                logger.debug(
                                    f"매수: {entry_date}, 가격={buy_price:.2f}, 수량={shares}, 버퍼존={current_buffer_pct:.2%}"
                                )
                        else:
                            logger.debug(f"자금 부족으로 매수 불가: {current_date}, 자본={capital:.0f}, 가격={buy_price:.2f}")

        # 5-4. 매도 신호 체크 (포지션 있을 때)
        elif position > 0 and prev_lower_band is not None:
            # 전일 종가 >= 하단 & 당일 종가 < 하단 (하향돌파)
            if prev_row[COL_CLOSE] >= prev_lower_band and row[COL_CLOSE] < lower_band:
                # 매도 실행 (다음 날 시가)
                sell_idx = i + 1
                if sell_idx < len(df):
                    sell_row = df.iloc[sell_idx]
                    sell_price_raw = sell_row[COL_OPEN]
                    sell_price = sell_price_raw * (1 - SLIPPAGE_RATE)
                    sell_amount = position * sell_price
                    capital += sell_amount

                    trades.append(
                        {
                            "entry_date": entry_date,
                            "exit_date": sell_row[COL_DATE],
                            "entry_price": entry_price,
                            "exit_price": sell_price,
                            "shares": position,
                            "pnl": (sell_price - entry_price) * position,
                            "pnl_pct": (sell_price - entry_price) / entry_price,
                            "exit_reason": "signal",
                            "buffer_zone_pct": current_buffer_pct,
                            "hold_days_used": current_hold_days,
                            "recent_buy_count": recent_buy_count,
                        }
                    )

                    if log_trades:
                        logger.debug(
                            f"매도: {sell_row[COL_DATE]}, 가격={sell_price:.2f}, "
                            f"손익률={((sell_price - entry_price) / entry_price) * 100:.2f}%"
                        )

                    position = 0
                    entry_price = 0.0
                    entry_date = None

        # 5-5. 자본 곡선 기록
        if position > 0:
            equity = capital + position * row[COL_CLOSE]
        else:
            equity = capital

        equity_records.append(
            {
                COL_DATE: current_date,
                "equity": equity,
                "position": position,
                "buffer_zone_pct": current_buffer_pct,
                "upper_band": upper_band,
                "lower_band": lower_band,
            }
        )

        # 5-6. 다음 루프를 위해 전일 밴드 저장
        prev_upper_band = upper_band
        prev_lower_band = lower_band

    # 6. 마지막 포지션 청산 (백테스트 종료 시)
    if position > 0:
        last_row = df.iloc[-1]
        sell_price = last_row[COL_CLOSE] * (1 - SLIPPAGE_RATE)
        sell_amount = position * sell_price
        capital += sell_amount

        # 마지막 동적 파라미터 계산 (매매 신호 로직과 동일)
        if params.recent_months > 0:
            recent_buy_count = calculate_recent_buy_count(all_entry_dates, last_row[COL_DATE], params.recent_months)
            current_buffer_pct = params.buffer_zone_pct + (recent_buy_count * BUFFER_INCREMENT_PER_BUY)
            if params.hold_days > 0:
                current_hold_days = params.hold_days + recent_buy_count
            else:
                current_hold_days = params.hold_days
        else:
            current_buffer_pct = params.buffer_zone_pct
            current_hold_days = params.hold_days
            recent_buy_count = 0

        trades.append(
            {
                "entry_date": entry_date,
                "exit_date": last_row[COL_DATE],
                "entry_price": entry_price,
                "exit_price": sell_price,
                "shares": position,
                "pnl": (sell_price - entry_price) * position,
                "pnl_pct": (sell_price - entry_price) / entry_price,
                "exit_reason": "end_of_data",
                "buffer_zone_pct": current_buffer_pct,
                "hold_days_used": current_hold_days,
                "recent_buy_count": recent_buy_count,
            }
        )

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
        logger.debug(f"버퍼존 전략 완료: 총 거래={summary['total_trades']}, 총 수익률={summary['total_return_pct']:.2f}%")

    return trades_df, equity_df, summary
