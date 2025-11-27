"""전략 실행 모듈"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal, cast

import pandas as pd

from qbt.backtest.config import (
    DEFAULT_INITIAL_CAPITAL,
    MIN_LOOKBACK_FOR_LOW,
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


def add_moving_averages(
    df: pd.DataFrame,
    short_window: int,
    long_window: int,
) -> pd.DataFrame:
    """
    이동평균선(SMA, EMA)을 계산하여 컬럼으로 추가한다.

    동일한 윈도우 설정에 대해 SMA와 EMA를 동시에 계산한다.
    추가되는 컬럼: ma_short_sma, ma_long_sma, ma_short_ema, ma_long_ema

    Args:
        df: 주식 데이터 DataFrame (Close 컬럼 필수)
        short_window: 단기 이동평균 기간
        long_window: 장기 이동평균 기간

    Returns:
        이동평균 컬럼이 추가된 DataFrame (원본 복사본)

    Raises:
        ValueError: short_window >= long_window인 경우
    """
    # 1. 파라미터 유효성 검증
    if short_window >= long_window:
        raise ValueError(
            f"short_window({short_window})는 "
            f"long_window({long_window})보다 작아야 합니다"
        )

    logger.debug(f"이동평균 계산 시작: short={short_window}, long={long_window}")

    # 2. DataFrame 복사 (원본 보존)
    df = df.copy()

    # 3. SMA (Simple Moving Average) 계산
    df["ma_short_sma"] = df["Close"].rolling(window=short_window).mean()
    df["ma_long_sma"] = df["Close"].rolling(window=long_window).mean()

    # 4. EMA (Exponential Moving Average) 계산
    df["ma_short_ema"] = df["Close"].ewm(span=short_window, adjust=False).mean()
    df["ma_long_ema"] = df["Close"].ewm(span=long_window, adjust=False).mean()

    # 5. 유효 데이터 수 확인
    valid_rows = df["ma_long_sma"].notna().sum()
    logger.debug(
        f"이동평균 계산 완료: 유효 데이터 {valid_rows:,}행 (전체 {len(df):,}행)"
    )

    return df


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

        equity_records.append(
            {"Date": current_date, "equity": equity, "position": position}
        )

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

    logger.debug(
        f"전략 실행 완료: 총 거래={summary['total_trades']}, "
        f"총 수익률={summary['total_return_pct']:.2f}%"
    )

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
        equity_records.append(
            {"Date": row["Date"], "equity": equity, "position": shares}
        )

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
    equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df[
        "peak"
    ]
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

    logger.debug(
        f"Buy & Hold 완료: 총 수익률={total_return_pct:.2f}%, CAGR={cagr:.2f}%"
    )

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

    results = []
    total_combinations = (
        len(short_window_list)
        * len(long_window_list)
        * len(stop_loss_pct_list)
        * len(lookback_for_low_list)
        * 2  # SMA, EMA
    )
    current = 0

    # 1. 모든 파라미터 조합 순회
    for short_window in short_window_list:
        for long_window in long_window_list:
            # short >= long인 경우 스킵
            if short_window >= long_window:
                current += len(stop_loss_pct_list) * len(lookback_for_low_list) * 2
                continue

            # 2. 이동평균 계산 (조합당 한 번만)
            df_with_ma = add_moving_averages(df, short_window, long_window)

            for stop_loss_pct in stop_loss_pct_list:
                for lookback_for_low in lookback_for_low_list:
                    params = StrategyParams(
                        short_window=short_window,
                        long_window=long_window,
                        stop_loss_pct=stop_loss_pct,
                        lookback_for_low=lookback_for_low,
                        initial_capital=initial_capital,
                    )

                    # 3. SMA, EMA 전략 실행
                    ma_types: list[Literal["sma", "ema"]] = ["sma", "ema"]
                    for ma_type in ma_types:
                        current += 1
                        try:
                            _, _, summary = run_strategy(
                                df_with_ma, params, ma_type=ma_type
                            )

                            # 4. 결과 기록
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
                                f"전략 실행 실패: {ma_type}, short={short_window}, "
                                f"long={long_window}, error={e}"
                            )
                            continue

                        if current % 10 == 0:
                            logger.debug(
                                f"그리드 탐색 진행: {current}/{total_combinations}"
                            )

    # 5. 결과 DataFrame 생성
    results_df = pd.DataFrame(results)

    if not results_df.empty:
        # 6. 수익률 기준 정렬
        results_df = results_df.sort_values(
            by="total_return_pct", ascending=False
        ).reset_index(drop=True)

    logger.debug(f"그리드 탐색 완료: {len(results_df)}개 조합 테스트됨")

    return results_df


def generate_walkforward_windows(
    df: pd.DataFrame,
    train_years: int = 5,
    test_years: int = 1,
) -> list[dict]:
    """
    워킹 포워드 테스트를 위한 Train/Test 윈도우를 생성한다.

    전체 데이터를 train_years + test_years 단위로 롤링하며 구간을 나눈다.

    Args:
        df: 주식 데이터 DataFrame (Date 컬럼 필수)
        train_years: 학습 기간 (년)
        test_years: 테스트 기간 (년)

    Returns:
        윈도우 정보 리스트 [{train_start, train_end, test_start, test_end}, ...]
    """
    logger.debug(f"워킹 포워드 윈도우 생성: train={train_years}년, test={test_years}년")

    # 날짜를 datetime으로 변환
    dates = pd.to_datetime(df["Date"])
    start_date = dates.min()
    end_date = dates.max()

    windows = []
    current_train_start = start_date

    while True:
        # Train 기간 계산
        train_end = current_train_start + timedelta(days=train_years * 365)

        # Test 기간 계산
        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=test_years * 365)

        # 데이터 범위 초과 시 종료
        if train_end > end_date:
            break

        # Test 기간이 데이터 범위를 초과하면 마지막 날까지로 조정
        if test_end > end_date:
            test_end = end_date

        # Test 기간이 너무 짧으면 (최소 30일) 스킵
        if (test_end - test_start).days < 30:
            break

        windows.append(
            {
                "train_start": current_train_start.date(),
                "train_end": train_end.date(),
                "test_start": test_start.date(),
                "test_end": test_end.date(),
            }
        )

        # 다음 윈도우로 이동 (test_years만큼 롤링)
        current_train_start = current_train_start + timedelta(days=test_years * 365)

    logger.debug(f"워킹 포워드 윈도우 생성 완료: {len(windows)}개 구간")

    return windows


def run_walkforward(
    df: pd.DataFrame,
    short_window_list: list[int],
    long_window_list: list[int],
    stop_loss_pct_list: list[float],
    lookback_for_low_list: list[int],
    train_years: int = 5,
    test_years: int = 1,
    initial_capital: float = 10_000_000.0,
    selection_metric: str = "cagr",
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    워킹 포워드 테스트를 실행한다.

    각 Train 구간에서 그리드 서치로 최적 파라미터를 선택하고,
    Test 구간에 해당 파라미터로 백테스트를 실행한다.

    Args:
        df: 주식 데이터 DataFrame (load_data로 로드된 상태)
        short_window_list: 단기 이동평균 기간 목록
        long_window_list: 장기 이동평균 기간 목록
        stop_loss_pct_list: 손절 비율 목록
        lookback_for_low_list: 최근 저점 탐색 기간 목록
        train_years: 학습 기간 (년)
        test_years: 테스트 기간 (년)
        initial_capital: 초기 자본금
        selection_metric: 최적 파라미터 선택 기준 ("cagr", "total_return_pct", "mdd")

    Returns:
        tuple: (walkforward_results_df, combined_equity_df, summary)
            - walkforward_results_df: 구간별 결과 DataFrame
            - combined_equity_df: 연결된 자본 곡선 DataFrame
            - summary: 전체 요약 지표
    """
    logger.debug(
        f"워킹 포워드 테스트 시작: train={train_years}년, test={test_years}년, "
        f"metric={selection_metric}"
    )

    # 1. 윈도우 생성
    windows = generate_walkforward_windows(df, train_years, test_years)

    if not windows:
        raise ValueError(
            "워킹 포워드 윈도우를 생성할 수 없습니다. 데이터 기간을 확인하세요."
        )

    # 날짜를 datetime.date로 변환
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.date

    results = []
    equity_segments = []
    current_capital = initial_capital

    # 2. 각 윈도우에 대해 Train/Test 실행
    for idx, window in enumerate(windows):
        logger.debug(
            f"윈도우 {idx + 1}/{len(windows)}: "
            f"Train {window['train_start']} ~ {window['train_end']}, "
            f"Test {window['test_start']} ~ {window['test_end']}"
        )

        # 2-1. Train 데이터 추출
        train_mask = (df["Date"] >= window["train_start"]) & (
            df["Date"] <= window["train_end"]
        )
        train_df = df[train_mask].reset_index(drop=True)

        if len(train_df) < 100:
            logger.warning(f"윈도우 {idx + 1}: Train 데이터 부족 ({len(train_df)}행)")
            continue

        # 2-2. Train 구간 그리드 서치
        try:
            grid_results = run_grid_search(
                train_df,
                short_window_list,
                long_window_list,
                stop_loss_pct_list,
                lookback_for_low_list,
                initial_capital=current_capital,
            )
        except Exception as e:
            logger.warning(f"윈도우 {idx + 1}: 그리드 서치 실패 - {e}")
            continue

        if grid_results.empty:
            logger.warning(f"윈도우 {idx + 1}: 그리드 서치 결과 없음")
            continue

        # 2-3. 최적 파라미터 선택
        if selection_metric == "mdd":
            # MDD는 음수이므로 최대값(가장 작은 낙폭) 선택
            best_idx = int(grid_results["mdd"].idxmax())
        else:
            # cagr, total_return_pct 등은 최대값 선택
            best_idx = int(grid_results[selection_metric].idxmax())

        best_params = grid_results.iloc[best_idx]

        logger.debug(
            f"윈도우 {idx + 1} 최적 파라미터: "
            f"ma={best_params['ma_type']}, "
            f"short={best_params['short_window']}, long={best_params['long_window']}, "
            f"stop={best_params['stop_loss_pct']}, "
            f"lookback={best_params['lookback_for_low']}, "
            f"{selection_metric}={best_params[selection_metric]:.2f}"
        )

        # 2-4. Test 데이터 추출
        test_mask = (df["Date"] >= window["test_start"]) & (
            df["Date"] <= window["test_end"]
        )
        test_df = df[test_mask].reset_index(drop=True)

        if len(test_df) < 30:
            logger.warning(f"윈도우 {idx + 1}: Test 데이터 부족 ({len(test_df)}행)")
            continue

        # 2-5. Test 구간 백테스트 실행
        try:
            test_df_with_ma = add_moving_averages(
                test_df,
                int(best_params["short_window"]),
                int(best_params["long_window"]),
            )

            params = StrategyParams(
                short_window=int(best_params["short_window"]),
                long_window=int(best_params["long_window"]),
                stop_loss_pct=float(best_params["stop_loss_pct"]),
                lookback_for_low=int(best_params["lookback_for_low"]),
                initial_capital=current_capital,
            )

            ma_type = cast(Literal["sma", "ema"], best_params["ma_type"])
            _, equity_df, test_summary = run_strategy(
                test_df_with_ma,
                params,
                ma_type=ma_type,
            )
        except Exception as e:
            logger.warning(f"윈도우 {idx + 1}: Test 백테스트 실패 - {e}")
            continue

        # 2-6. 결과 기록
        results.append(
            {
                "window_idx": idx + 1,
                "train_start": window["train_start"],
                "train_end": window["train_end"],
                "test_start": window["test_start"],
                "test_end": window["test_end"],
                "best_ma_type": best_params["ma_type"],
                "best_short_window": int(best_params["short_window"]),
                "best_long_window": int(best_params["long_window"]),
                "best_stop_loss_pct": float(best_params["stop_loss_pct"]),
                "best_lookback_for_low": int(best_params["lookback_for_low"]),
                "train_metric": float(best_params[selection_metric]),
                "test_return_pct": test_summary["total_return_pct"],
                "test_cagr": test_summary["cagr"],
                "test_mdd": test_summary["mdd"],
                "test_trades": test_summary["total_trades"],
                "test_win_rate": test_summary["win_rate"],
                "start_capital": current_capital,
                "end_capital": test_summary["final_capital"],
            }
        )

        # 2-7. 자본 곡선 연결
        if not equity_df.empty:
            equity_df = equity_df.copy()
            equity_df["window_idx"] = idx + 1
            equity_segments.append(equity_df)
            current_capital = test_summary["final_capital"]

    # 3. 결과 DataFrame 생성
    walkforward_results_df = pd.DataFrame(results)

    # 4. 자본 곡선 연결
    if equity_segments:
        combined_equity_df = pd.concat(equity_segments, ignore_index=True)
    else:
        combined_equity_df = pd.DataFrame()

    # 5. 전체 요약 지표 계산
    if not walkforward_results_df.empty:
        final_capital = walkforward_results_df.iloc[-1]["end_capital"]
        total_return = final_capital - initial_capital
        total_return_pct = (total_return / initial_capital) * 100

        # 기간 계산
        first_test_start = pd.to_datetime(walkforward_results_df.iloc[0]["test_start"])
        last_test_end = pd.to_datetime(walkforward_results_df.iloc[-1]["test_end"])
        years = (last_test_end - first_test_start).days / 365.25

        # CAGR
        if years > 0:
            cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100
        else:
            cagr = 0.0

        # MDD (combined equity에서 계산)
        if not combined_equity_df.empty:
            combined_equity_df["peak"] = combined_equity_df["equity"].cummax()
            combined_equity_df["drawdown"] = (
                combined_equity_df["equity"] - combined_equity_df["peak"]
            ) / combined_equity_df["peak"]
            mdd = combined_equity_df["drawdown"].min() * 100
        else:
            mdd = 0.0

        summary = {
            "strategy": "walkforward",
            "initial_capital": initial_capital,
            "final_capital": final_capital,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "cagr": cagr,
            "mdd": mdd,
            "total_windows": len(walkforward_results_df),
            "avg_test_return_pct": walkforward_results_df["test_return_pct"].mean(),
            "selection_metric": selection_metric,
            "train_years": train_years,
            "test_years": test_years,
        }
    else:
        summary = {
            "strategy": "walkforward",
            "initial_capital": initial_capital,
            "final_capital": initial_capital,
            "total_return": 0.0,
            "total_return_pct": 0.0,
            "cagr": 0.0,
            "mdd": 0.0,
            "total_windows": 0,
        }

    logger.debug(
        f"워킹 포워드 테스트 완료: {len(results)}개 윈도우, "
        f"총 수익률={summary['total_return_pct']:.2f}%"
    )

    return walkforward_results_df, combined_equity_df, summary
