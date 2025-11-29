"""전략 실행 모듈"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

import pandas as pd

from qbt.backtest.config import (
    DEFAULT_BUFFER_ZONE_PCT,
    DEFAULT_HOLD_DAYS,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_MA_WINDOW,
    DEFAULT_RECENT_MONTHS,
    MIN_BUFFER_ZONE_PCT,
    MIN_HOLD_DAYS,
    MIN_LOOKBACK_FOR_LOW,
    MIN_VALID_ROWS,
    SLIPPAGE_RATE,
)
from qbt.backtest.metrics import calculate_summary
from qbt.utils import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyParams:
    """전략 파라미터를 담는 데이터 클래스."""

    short_window: int
    long_window: int
    stop_loss_pct: float = 0.10  # 최대 손실 허용 비율 (10%)
    lookback_for_low: int = MIN_LOOKBACK_FOR_LOW  # 최근 저점 탐색 기간
    initial_capital: float = DEFAULT_INITIAL_CAPITAL  # 초기 자본금


def run_strategy(
    df: pd.DataFrame,
    params: StrategyParams,
    ma_type: Literal["sma", "ema"] = "sma",
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    이동평균 교차 전략으로 백테스트를 실행한다.

    롱 온리, 최대 1 포지션 전략을 사용한다.
    신호 발생 다음 날 시가에 진입/청산하며, 손절 규칙과 거래 비용을 적용한다.

    Args:
        df: 이동평균이 계산된 DataFrame (add_moving_averages 적용 필수)
        params: 전략 파라미터
        ma_type: 이동평균 유형 ("sma" 또는 "ema")

    Returns:
        tuple: (trades_df, equity_df, summary)
            - trades_df: 거래 내역 DataFrame
            - equity_df: 자본 곡선 DataFrame
            - summary: 요약 지표 딕셔너리
    """
    logger.debug(f"전략 실행 시작: ma_type={ma_type}, params={params}")

    # 1. 이동평균 컬럼명 설정
    ma_short_col = f"ma_short_{ma_type}"
    ma_long_col = f"ma_long_{ma_type}"

    # 2. 필수 컬럼 확인
    required_cols = [ma_short_col, ma_long_col, "Open", "Close", "Low", "Date"]
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 3. 유효 데이터만 사용 (long_window 이후부터)
    df = df.copy()
    df = df[df[ma_long_col].notna()].reset_index(drop=True)

    # 4. 초기화
    capital = params.initial_capital
    position = 0  # 보유 주식 수
    entry_price = 0.0  # 진입 가격
    entry_date = None  # 진입 날짜
    entry_idx = 0  # 진입 인덱스

    trades = []  # 거래 내역
    equity_records = []  # 자본 곡선

    # 손절 파라미터
    effective_lookback = max(params.lookback_for_low, MIN_LOOKBACK_FOR_LOW)

    # 5. 백테스트 루프 (인덱스 1부터 시작 - 전일 비교 필요)
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]
        current_date = row["Date"]

        # 5-1. 포지션 보유 중 손절 체크
        if position > 0:
            # 진입 후 경과 일수 계산
            days_held = i - entry_idx

            # 최근 저점 계산 (Low 기준)
            lookback_start = max(entry_idx, i - effective_lookback)
            if days_held < effective_lookback:
                # 진입 후 경과 일수가 lookback보다 작으면 진입 이후 데이터만 사용
                lookback_start = entry_idx
            recent_low = df.iloc[lookback_start : i + 1]["Low"].min()

            # 손절 가격 계산
            hard_stop = entry_price * (1 - params.stop_loss_pct)
            stop_price = max(recent_low, hard_stop)

            # 전일 종가가 손절 가격 이하면 다음 날 시가에 손절
            if prev_row["Close"] <= stop_price:
                # 손절 매도 (당일 시가)
                sell_price_raw = row["Open"]
                sell_price = sell_price_raw * (1 - SLIPPAGE_RATE)
                sell_amount = position * sell_price
                capital += sell_amount

                trades.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": current_date,
                        "entry_price": entry_price,
                        "exit_price": sell_price,
                        "shares": position,
                        "pnl": (sell_price - entry_price) * position,
                        "pnl_pct": (sell_price - entry_price) / entry_price,
                        "exit_reason": "stop_loss",
                    }
                )

                # logger.debug(
                #     f"손절 매도: {current_date}, 가격={sell_price:.2f}, "
                #     f"손익률={((sell_price - entry_price) / entry_price) * 100:.2f}%"
                # )

                position = 0
                entry_price = 0.0
                entry_date = None

        # 5-2. 매매 신호 확인
        prev_short = prev_row[ma_short_col]
        prev_long = prev_row[ma_long_col]
        curr_short = row[ma_short_col]
        curr_long = row[ma_long_col]

        # 골든 크로스 (매수 신호): 전일 short <= long, 당일 short > long
        buy_signal = (prev_short <= prev_long) and (curr_short > curr_long)

        # 데드 크로스 (매도 신호): 전일 short >= long, 당일 short < long
        sell_signal = (prev_short >= prev_long) and (curr_short < curr_long)

        # 5-3. 매수 실행 (다음 날 시가에 진입이므로, 신호 당일에 기록)
        if buy_signal and position == 0 and i + 1 < len(df):
            next_row = df.iloc[i + 1]
            buy_price_raw = next_row["Open"]
            buy_price = buy_price_raw * (1 + SLIPPAGE_RATE)

            # 매수 가능 주식 수 계산
            shares = int(capital / buy_price)

            if shares > 0:
                buy_amount = shares * buy_price
                capital -= buy_amount

                position = shares
                entry_price = buy_price
                entry_date = next_row["Date"]
                entry_idx = i + 1

                # logger.debug(
                #     f"매수: {entry_date}, 가격={buy_price:.2f}, 수량={shares}"
                # )

        # 5-4. 매도 실행 (교차 신호에 의한 청산)
        elif sell_signal and position > 0 and i + 1 < len(df):
            next_row = df.iloc[i + 1]
            sell_price_raw = next_row["Open"]
            sell_price = sell_price_raw * (1 - SLIPPAGE_RATE)
            sell_amount = position * sell_price
            capital += sell_amount

            trades.append(
                {
                    "entry_date": entry_date,
                    "exit_date": next_row["Date"],
                    "entry_price": entry_price,
                    "exit_price": sell_price,
                    "shares": position,
                    "pnl": (sell_price - entry_price) * position,
                    "pnl_pct": (sell_price - entry_price) / entry_price,
                    "exit_reason": "signal",
                }
            )

            # logger.debug(
            #     f"매도: {next_row['Date']}, 가격={sell_price:.2f}, "
            #     f"손익률={((sell_price - entry_price) / entry_price) * 100:.2f}%"
            # )

            position = 0
            entry_price = 0.0
            entry_date = None

        # 5-5. 자본 곡선 기록
        if position > 0:
            equity = capital + position * row["Close"]
        else:
            equity = capital

        equity_records.append({"Date": current_date, "equity": equity, "position": position})

    # 6. 마지막 포지션 청산 (백테스트 종료 시)
    if position > 0:
        last_row = df.iloc[-1]
        sell_price = last_row["Close"] * (1 - SLIPPAGE_RATE)
        sell_amount = position * sell_price
        capital += sell_amount

        trades.append(
            {
                "entry_date": entry_date,
                "exit_date": last_row["Date"],
                "entry_price": entry_price,
                "exit_price": sell_price,
                "shares": position,
                "pnl": (sell_price - entry_price) * position,
                "pnl_pct": (sell_price - entry_price) / entry_price,
                "exit_reason": "end_of_data",
            }
        )

    # 7. 결과 DataFrame 생성
    trades_df = pd.DataFrame(trades)
    equity_df = pd.DataFrame(equity_records)

    # 8. 요약 지표 계산
    summary = calculate_summary(trades_df, equity_df, params.initial_capital)
    summary["ma_type"] = ma_type
    summary["short_window"] = params.short_window
    summary["long_window"] = params.long_window

    logger.debug(f"전략 실행 완료: 총 거래={summary['total_trades']}, " f"총 수익률={summary['total_return_pct']:.2f}%")

    return trades_df, equity_df, summary


def run_buy_and_hold(
    df: pd.DataFrame,
    initial_capital: float = 10_000_000.0,
) -> tuple[pd.DataFrame, dict]:
    """
    Buy & Hold 벤치마크 전략을 실행한다.

    첫날 시가에 매수, 마지막 날 종가에 매도한다.

    Args:
        df: 주식 데이터 DataFrame
        initial_capital: 초기 자본금

    Returns:
        tuple: (equity_df, summary)
            - equity_df: 자본 곡선 DataFrame
            - summary: 요약 지표 딕셔너리
    """
    logger.debug("Buy & Hold 실행 시작")

    df = df.copy()

    # 1. 첫날 시가에 매수
    buy_price_raw = df.iloc[0]["Open"]
    buy_price = buy_price_raw * (1 + SLIPPAGE_RATE)
    shares = int(initial_capital / buy_price)
    buy_amount = shares * buy_price
    capital_after_buy = initial_capital - buy_amount

    # 2. 자본 곡선 계산
    equity_records = []
    for _, row in df.iterrows():
        equity = capital_after_buy + shares * row["Close"]
        equity_records.append({"Date": row["Date"], "equity": equity, "position": shares})

    equity_df = pd.DataFrame(equity_records)

    # 3. 마지막 날 종가에 매도
    sell_price_raw = df.iloc[-1]["Close"]
    sell_price = sell_price_raw * (1 - SLIPPAGE_RATE)
    sell_amount = shares * sell_price
    final_capital = capital_after_buy + sell_amount

    # 4. 요약 지표 계산
    total_return = final_capital - initial_capital
    total_return_pct = (total_return / initial_capital) * 100

    # 기간 계산 (연 단위)
    start_date = pd.to_datetime(df.iloc[0]["Date"])
    end_date = pd.to_datetime(df.iloc[-1]["Date"])
    years = (end_date - start_date).days / 365.25

    # CAGR
    if years > 0:
        cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
    else:
        cagr = 0.0

    # MDD 계산
    equity_df["peak"] = equity_df["equity"].cummax()
    equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"]
    mdd = equity_df["drawdown"].min() * 100

    summary = {
        "strategy": "buy_and_hold",
        "initial_capital": initial_capital,
        "final_capital": final_capital,
        "total_return": total_return,
        "total_return_pct": total_return_pct,
        "cagr": cagr,
        "mdd": mdd,
        "total_trades": 1,
        "start_date": str(df.iloc[0]["Date"]),
        "end_date": str(df.iloc[-1]["Date"]),
    }

    logger.debug(f"Buy & Hold 완료: 총 수익률={total_return_pct:.2f}%, CAGR={cagr:.2f}%")

    return equity_df, summary


def run_grid_search(
    df: pd.DataFrame,
    short_window_list: list[int],
    long_window_list: list[int],
    stop_loss_pct_list: list[float],
    lookback_for_low_list: list[int],
    initial_capital: float = 10_000_000.0,
) -> pd.DataFrame:
    """
    파라미터 그리드 탐색을 수행한다.

    모든 파라미터 조합에 대해 SMA와 EMA 전략을 각각 실행하고
    성과 지표를 기록한다.

    Args:
        df: 주식 데이터 DataFrame (load_data로 로드된 상태)
        short_window_list: 단기 이동평균 기간 목록
        long_window_list: 장기 이동평균 기간 목록
        stop_loss_pct_list: 손절 비율 목록
        lookback_for_low_list: 최근 저점 탐색 기간 목록
        initial_capital: 초기 자본금

    Returns:
        그리드 탐색 결과 DataFrame (각 조합별 성과 지표 포함)
    """
    logger.debug(
        f"그리드 탐색 시작: "
        f"short={short_window_list}, long={long_window_list}, "
        f"stop_loss={stop_loss_pct_list}, lookback={lookback_for_low_list}"
    )

    # 1. 모든 유니크한 윈도우에 대해 이동평균 미리 계산
    df = df.copy()
    all_windows = set(short_window_list) | set(long_window_list)
    logger.debug(f"이동평균 사전 계산: {sorted(all_windows)}")

    for window in all_windows:
        df[f"sma_{window}"] = df["Close"].rolling(window=window).mean()
        df[f"ema_{window}"] = df["Close"].ewm(span=window, adjust=False).mean()

    logger.debug("이동평균 사전 계산 완료")

    results = []
    total_combinations = (
        len(short_window_list)
        * len(long_window_list)
        * len(stop_loss_pct_list)
        * len(lookback_for_low_list)
        * 2  # SMA, EMA
    )
    current = 0

    # 2. 모든 파라미터 조합 순회
    for short_window in short_window_list:
        for long_window in long_window_list:
            # short >= long인 경우 스킵
            if short_window >= long_window:
                current += len(stop_loss_pct_list) * len(lookback_for_low_list) * 2
                continue

            # 3. 미리 계산된 이동평균을 사용할 DataFrame 준비
            df_with_ma = df.copy()
            df_with_ma["ma_short_sma"] = df[f"sma_{short_window}"]
            df_with_ma["ma_long_sma"] = df[f"sma_{long_window}"]
            df_with_ma["ma_short_ema"] = df[f"ema_{short_window}"]
            df_with_ma["ma_long_ema"] = df[f"ema_{long_window}"]

            for stop_loss_pct in stop_loss_pct_list:
                for lookback_for_low in lookback_for_low_list:
                    params = StrategyParams(
                        short_window=short_window,
                        long_window=long_window,
                        stop_loss_pct=stop_loss_pct,
                        lookback_for_low=lookback_for_low,
                        initial_capital=initial_capital,
                    )

                    # 4. SMA, EMA 전략 실행
                    ma_types: list[Literal["sma", "ema"]] = ["sma", "ema"]
                    for ma_type in ma_types:
                        current += 1
                        try:
                            _, _, summary = run_strategy(df_with_ma, params, ma_type=ma_type)

                            # 5. 결과 기록
                            results.append(
                                {
                                    "ma_type": ma_type,
                                    "short_window": short_window,
                                    "long_window": long_window,
                                    "stop_loss_pct": stop_loss_pct,
                                    "lookback_for_low": lookback_for_low,
                                    "total_return_pct": summary["total_return_pct"],
                                    "cagr": summary["cagr"],
                                    "mdd": summary["mdd"],
                                    "total_trades": summary["total_trades"],
                                    "win_rate": summary["win_rate"],
                                    "final_capital": summary["final_capital"],
                                }
                            )
                        except Exception as e:
                            logger.warning(
                                f"전략 실행 실패: {ma_type}, short={short_window}, " f"long={long_window}, error={e}"
                            )
                            continue

                        if current % 10 == 0:
                            logger.debug(f"그리드 탐색 진행: {current}/{total_combinations}")

    # 6. 결과 DataFrame 생성
    results_df = pd.DataFrame(results)

    if not results_df.empty:
        # 7. 수익률 기준 정렬
        results_df = results_df.sort_values(by="total_return_pct", ascending=False).reset_index(drop=True)

    logger.debug(f"그리드 탐색 완료: {len(results_df)}개 조합 테스트됨")

    return results_df


@dataclass
class BufferStrategyParams:
    """버퍼존 전략 파라미터를 담는 데이터 클래스."""

    ma_window: int = DEFAULT_MA_WINDOW  # 이동평균 기간 (200일)
    buffer_zone_pct: float = DEFAULT_BUFFER_ZONE_PCT  # 초기 버퍼존 (1%)
    hold_days: int = DEFAULT_HOLD_DAYS  # 초기 유지조건 (1일)
    recent_months: int = DEFAULT_RECENT_MONTHS  # 최근 매수 기간 (6개월)
    initial_capital: float = DEFAULT_INITIAL_CAPITAL  # 초기 자본금


def add_single_moving_average(
    df: pd.DataFrame,
    window: int,
    ma_type: str = "sma",
) -> pd.DataFrame:
    """
    지정된 기간의 이동평균을 계산하여 컬럼으로 추가한다.

    Args:
        df: 주식 데이터 DataFrame (Close 컬럼 필수)
        window: 이동평균 기간
        ma_type: 이동평균 유형 ("sma" 또는 "ema", 기본값: "sma")

    Returns:
        이동평균 컬럼이 추가된 DataFrame (원본 복사본)

    Raises:
        ValueError: window < 1인 경우
    """
    if window < 1:
        raise ValueError(f"window는 1 이상이어야 합니다: {window}")

    logger.debug(f"이동평균 계산: window={window}, type={ma_type}")

    # DataFrame 복사 (원본 보존)
    df = df.copy()

    # 컬럼명 설정
    col_name = f"ma_{window}"

    # 이동평균 계산
    if ma_type == "sma":
        df[col_name] = df["Close"].rolling(window=window).mean()
    elif ma_type == "ema":
        df[col_name] = df["Close"].ewm(span=window, adjust=False).mean()
    else:
        raise ValueError(f"지원하지 않는 ma_type: {ma_type}")

    # 유효 데이터 수 확인
    valid_rows = df[col_name].notna().sum()
    logger.debug(f"이동평균 계산 완료: 유효 데이터 {valid_rows:,}행 (전체 {len(df):,}행)")

    return df


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
    cutoff_date = current_date - timedelta(days=recent_months * 30)
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

        if row["Close"] <= upper_band:
            return False  # 유지 실패

    return True  # 모든 날 유지 성공


def run_buffer_strategy(
    df: pd.DataFrame,
    params: BufferStrategyParams,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    버퍼존 전략으로 백테스트를 실행한다.

    롱 온리, 최대 1 포지션 전략을 사용한다.
    버퍼존 상단 돌파 시 매수, 하단 돌파 시 매도하며, 동적으로 버퍼존과 유지조건을 조정한다.

    Args:
        df: 이동평균이 계산된 DataFrame (add_single_moving_average 적용 필수)
        params: 전략 파라미터

    Returns:
        tuple: (trades_df, equity_df, summary)
            - trades_df: 거래 내역 DataFrame
            - equity_df: 자본 곡선 DataFrame
            - summary: 요약 지표 딕셔너리

    Raises:
        ValueError: 파라미터 검증 실패 또는 필수 컬럼 누락 시
    """  # noqa: E501
    logger.debug(f"버퍼존 전략 실행 시작: params={params}")

    # 1. 파라미터 검증
    if params.ma_window < 1:
        raise ValueError(f"ma_window는 1 이상이어야 합니다: {params.ma_window}")

    if params.buffer_zone_pct < MIN_BUFFER_ZONE_PCT:
        raise ValueError(f"buffer_zone_pct는 {MIN_BUFFER_ZONE_PCT} 이상이어야 합니다: " f"{params.buffer_zone_pct}")

    if params.hold_days < MIN_HOLD_DAYS:
        raise ValueError(f"hold_days는 {MIN_HOLD_DAYS} 이상이어야 합니다: {params.hold_days}")

    if params.recent_months < 1:
        raise ValueError(f"recent_months는 1 이상이어야 합니다: {params.recent_months}")

    # 2. 필수 컬럼 확인
    ma_col = f"ma_{params.ma_window}"
    required_cols = [ma_col, "Open", "Close", "Date"]
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    # 3. 유효 데이터만 사용 (ma_window 이후부터)
    df = df.copy()
    df = df[df[ma_col].notna()].reset_index(drop=True)

    if len(df) < MIN_VALID_ROWS:
        raise ValueError(f"유효 데이터 부족: {len(df)}행 (최소 {MIN_VALID_ROWS}행 필요)")

    # 4. 초기화
    capital = params.initial_capital
    position = 0  # 보유 주식 수
    entry_price = 0.0  # 진입 가격
    entry_date = None  # 진입 날짜
    all_entry_dates = []  # 모든 매수 날짜 (동적 조정용)

    trades = []  # 거래 내역
    equity_records = []  # 자본 곡선

    prev_upper_band = None
    prev_lower_band = None

    # 5. 백테스트 루프 (인덱스 1부터 시작 - 전일 비교 필요)
    for i in range(1, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i - 1]
        current_date = row["Date"]

        # 5-1. 동적 파라미터 계산
        recent_buy_count = calculate_recent_buy_count(all_entry_dates, current_date, params.recent_months)
        current_buffer_pct = params.buffer_zone_pct + (recent_buy_count * 0.01)
        current_hold_days = params.hold_days + recent_buy_count

        # 5-2. 버퍼존 밴드 계산
        ma_value = row[ma_col]
        upper_band = ma_value * (1 + current_buffer_pct)
        lower_band = ma_value * (1 - current_buffer_pct)

        # 5-3. 매수 신호 체크 (포지션 없을 때)
        if position == 0 and prev_upper_band is not None:
            # 전일 종가 <= 상단 & 당일 종가 > 상단 (상향돌파)
            if prev_row["Close"] <= prev_upper_band and row["Close"] > upper_band:
                # 유지조건 체크 (hold_days > 0인 경우)
                if current_hold_days > 0:
                    hold_satisfied = check_hold_condition(df, i, current_hold_days, ma_col, current_buffer_pct)
                    if not hold_satisfied:
                        # 유지조건 실패, 매수 스킵
                        pass
                    else:
                        # 유지조건 만족, 매수 실행
                        buy_idx = i + current_hold_days + 1
                        if buy_idx < len(df):
                            buy_row = df.iloc[buy_idx]
                            buy_price_raw = buy_row["Open"]
                            buy_price = buy_price_raw * (1 + SLIPPAGE_RATE)
                            shares = int(capital / buy_price)

                            if shares > 0:
                                buy_amount = shares * buy_price
                                capital -= buy_amount

                                position = shares
                                entry_price = buy_price
                                entry_date = buy_row["Date"]
                                all_entry_dates.append(entry_date)

                                logger.debug(
                                    f"매수: {entry_date}, 가격={buy_price:.2f}, "
                                    f"수량={shares}, 버퍼존={current_buffer_pct:.2%}, "
                                    f"유지조건={current_hold_days}일"
                                )
                            else:
                                logger.debug(f"자금 부족으로 매수 불가: {current_date}, " f"자본={capital:.0f}, 가격={buy_price:.2f}")
                else:
                    # 버퍼존만 모드 (hold_days = 0)
                    buy_idx = i + 1
                    if buy_idx < len(df):
                        buy_row = df.iloc[buy_idx]
                        buy_price_raw = buy_row["Open"]
                        buy_price = buy_price_raw * (1 + SLIPPAGE_RATE)
                        shares = int(capital / buy_price)

                        if shares > 0:
                            buy_amount = shares * buy_price
                            capital -= buy_amount

                            position = shares
                            entry_price = buy_price
                            entry_date = buy_row["Date"]
                            all_entry_dates.append(entry_date)

                            logger.debug(
                                f"매수: {entry_date}, 가격={buy_price:.2f}, " f"수량={shares}, 버퍼존={current_buffer_pct:.2%}"
                            )
                        else:
                            logger.debug(f"자금 부족으로 매수 불가: {current_date}, " f"자본={capital:.0f}, 가격={buy_price:.2f}")

        # 5-4. 매도 신호 체크 (포지션 있을 때)
        elif position > 0 and prev_lower_band is not None:
            # 전일 종가 >= 하단 & 당일 종가 < 하단 (하향돌파)
            if prev_row["Close"] >= prev_lower_band and row["Close"] < lower_band:
                # 매도 실행 (다음 날 시가)
                sell_idx = i + 1
                if sell_idx < len(df):
                    sell_row = df.iloc[sell_idx]
                    sell_price_raw = sell_row["Open"]
                    sell_price = sell_price_raw * (1 - SLIPPAGE_RATE)
                    sell_amount = position * sell_price
                    capital += sell_amount

                    trades.append(
                        {
                            "entry_date": entry_date,
                            "exit_date": sell_row["Date"],
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

                    logger.debug(
                        f"매도: {sell_row['Date']}, 가격={sell_price:.2f}, "
                        f"손익률={((sell_price - entry_price) / entry_price) * 100:.2f}%"
                    )

                    position = 0
                    entry_price = 0.0
                    entry_date = None

        # 5-5. 자본 곡선 기록
        if position > 0:
            equity = capital + position * row["Close"]
        else:
            equity = capital

        equity_records.append(
            {
                "Date": current_date,
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
        sell_price = last_row["Close"] * (1 - SLIPPAGE_RATE)
        sell_amount = position * sell_price
        capital += sell_amount

        # 마지막 동적 파라미터 계산
        recent_buy_count = calculate_recent_buy_count(all_entry_dates, last_row["Date"], params.recent_months)
        current_buffer_pct = params.buffer_zone_pct + (recent_buy_count * 0.01)
        current_hold_days = params.hold_days + recent_buy_count

        trades.append(
            {
                "entry_date": entry_date,
                "exit_date": last_row["Date"],
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

    logger.debug(f"버퍼존 전략 완료: 총 거래={summary['total_trades']}, " f"총 수익률={summary['total_return_pct']:.2f}%")

    return trades_df, equity_df, summary
