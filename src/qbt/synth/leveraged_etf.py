"""레버리지 ETF 시뮬레이션 모듈

QQQ와 같은 기초 자산 데이터로부터 TQQQ와 같은 레버리지 ETF를 시뮬레이션한다.
일일 리밸런싱 기반의 3배 레버리지 ETF 동작을 재현한다.
"""

import numpy as np
import pandas as pd


def simulate_leveraged_etf(
    underlying_df: pd.DataFrame,
    leverage: float,
    expense_ratio: float,
    initial_price: float,
) -> pd.DataFrame:
    """
    기초 자산 데이터로부터 레버리지 ETF를 시뮬레이션한다.

    일일 리밸런싱을 가정하여 각 거래일마다 기초 자산 수익률의
    레버리지 배수만큼 움직이도록 계산한다. Expense ratio를 일일 비용으로
    환산하여 차감한다.

    Args:
        underlying_df: 기초 자산 DataFrame (Date, Close 컬럼 필수)
        leverage: 레버리지 배수 (예: 3.0)
        expense_ratio: 연간 비용 비율 (예: 0.0095 = 0.95%)
        initial_price: 시작 가격

    Returns:
        시뮬레이션된 레버리지 ETF DataFrame (Date, Open, High, Low, Close, Volume 컬럼)

    Raises:
        ValueError: 파라미터가 유효하지 않을 때
        ValueError: 필수 컬럼이 누락되었을 때
    """
    # 1. 파라미터 검증
    if leverage <= 0:
        raise ValueError(f"leverage는 양수여야 합니다: {leverage}")

    if expense_ratio < 0 or expense_ratio > 0.1:
        raise ValueError(f"expense_ratio는 0~10% 범위여야 합니다: {expense_ratio}")

    if initial_price <= 0:
        raise ValueError(f"initial_price는 양수여야 합니다: {initial_price}")

    # 2. 필수 컬럼 검증
    required_cols = {"Date", "Close"}
    missing_cols = required_cols - set(underlying_df.columns)
    if missing_cols:
        raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_cols}")

    if underlying_df.empty:
        raise ValueError("underlying_df가 비어있습니다")

    # 3. 데이터 복사 (원본 보존)
    df = underlying_df[["Date", "Close"]].copy()

    # 4. 일일 수익률 계산
    df["underlying_return"] = df["Close"].pct_change()

    # 5. 일일 비용 계산 (연간 비용 / 거래일 수)
    daily_expense = expense_ratio / 252

    # 6. 레버리지 ETF 수익률 계산
    # leveraged_return = underlying_return * leverage - daily_expense
    df["leveraged_return"] = df["underlying_return"] * leverage - daily_expense

    # 7. 레버리지 ETF 가격 계산 (복리)
    # 첫 날은 initial_price, 이후는 전일 가격 * (1 + 수익률)
    leveraged_prices = [initial_price]
    for ret in df["leveraged_return"].iloc[1:]:
        if pd.isna(ret):
            # 첫 번째 행의 경우 수익률이 NaN이므로 initial_price 유지
            leveraged_prices.append(initial_price)
        else:
            new_price = leveraged_prices[-1] * (1 + ret)
            leveraged_prices.append(new_price)

    df["Close"] = leveraged_prices

    # 8. OHLV 데이터 구성
    # Open: 전일 Close (첫날은 initial_price)
    df["Open"] = df["Close"].shift(1).fillna(initial_price)

    # High, Low, Volume: 0 (합성 데이터이므로 사용하지 않음)
    df["High"] = 0.0
    df["Low"] = 0.0
    df["Volume"] = 0

    # 9. 불필요한 컬럼 제거 및 순서 정렬
    result_df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()

    return result_df


def find_optimal_multiplier(
    underlying_df: pd.DataFrame,
    actual_leveraged_df: pd.DataFrame,
    expense_ratio: float = 0.0095,
    search_range: tuple[float, float] = (2.8, 3.2),
    search_step: float = 0.01,
) -> tuple[float | None, dict | None]:
    """
    실제 레버리지 ETF와 가장 유사한 시뮬레이션을 생성하는 최적 multiplier를 찾는다.

    Grid search 방식으로 여러 multiplier를 시도하고,
    실제 데이터와의 상관계수 및 RMSE를 기준으로 최적값을 선택한다.

    Args:
        underlying_df: 기초 자산 DataFrame (QQQ)
        actual_leveraged_df: 실제 레버리지 ETF DataFrame (TQQQ)
        expense_ratio: 연간 비용 비율
        search_range: 탐색 범위 (min, max)
        search_step: 탐색 간격

    Returns:
        (최적 multiplier, 평가 지표 딕셔너리)
        평가 지표: {
            'multiplier': 최적 multiplier 값,
            'correlation': 일일 수익률 상관계수,
            'rmse': 누적 수익률 RMSE,
            'final_price_diff_pct': 최종 가격 차이 비율,
            'score': 종합 점수
        }

    Raises:
        ValueError: 겹치는 기간이 없을 때
    """
    # 1. 겹치는 기간 추출
    underlying_dates = set(underlying_df["Date"])
    actual_dates = set(actual_leveraged_df["Date"])
    overlap_dates = underlying_dates & actual_dates

    if not overlap_dates:
        raise ValueError("기초 자산과 레버리지 ETF 간 겹치는 기간이 없습니다")

    # 날짜순 정렬
    overlap_dates = sorted(overlap_dates)

    # 겹치는 기간의 데이터만 추출
    underlying_overlap = (
        underlying_df[underlying_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)
    )
    actual_overlap = (
        actual_leveraged_df[actual_leveraged_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)
    )

    # 2. 실제 TQQQ 첫날 가격을 initial_price로 사용
    initial_price = float(actual_overlap.iloc[0]["Close"])

    # 3. Grid search
    multipliers = np.arange(search_range[0], search_range[1] + search_step, search_step)
    best_score = -np.inf
    best_multiplier = None
    best_metrics = None

    for multiplier in multipliers:
        # 시뮬레이션 실행
        sim_df = simulate_leveraged_etf(
            underlying_overlap,
            leverage=multiplier,
            expense_ratio=expense_ratio,
            initial_price=initial_price,
        )

        # 평가 지표 계산
        # 일일 수익률
        sim_returns = sim_df["Close"].pct_change().dropna()
        actual_returns = actual_overlap["Close"].pct_change().dropna()

        # 상관계수
        correlation = sim_returns.corr(actual_returns)

        # 누적 수익률 RMSE
        sim_cumulative = (1 + sim_returns).cumprod() - 1
        actual_cumulative = (1 + actual_returns).cumprod() - 1
        rmse = np.sqrt(np.mean((sim_cumulative - actual_cumulative) ** 2))

        # 최종 가격 차이 비율
        final_sim_price = float(sim_df.iloc[-1]["Close"])
        final_actual_price = float(actual_overlap.iloc[-1]["Close"])
        final_price_diff_pct = abs(final_sim_price - final_actual_price) / final_actual_price

        # 종합 점수 (상관계수 최대화, RMSE 최소화, 최종 가격 차이 최소화)
        # RMSE 정규화 (0~1 범위로)
        rmse_normalized = rmse / (abs(actual_cumulative.iloc[-1]) + 1e-10)
        score = correlation * 0.7 - rmse_normalized * 0.2 - final_price_diff_pct * 0.1

        # 최고 점수 업데이트
        if score > best_score:
            best_score = score
            best_multiplier = multiplier
            best_metrics = {
                "multiplier": multiplier,
                "correlation": correlation,
                "rmse": rmse,
                "final_price_diff_pct": final_price_diff_pct,
                "score": score,
            }

    return best_multiplier, best_metrics


def validate_simulation(
    simulated_df: pd.DataFrame,
    actual_df: pd.DataFrame,
) -> dict:
    """
    시뮬레이션 결과를 실제 데이터와 비교하여 검증 지표를 계산한다.

    Args:
        simulated_df: 시뮬레이션된 DataFrame
        actual_df: 실제 DataFrame

    Returns:
        검증 결과 딕셔너리: {
            'overlap_start': 겹치는 기간 시작일,
            'overlap_end': 겹치는 기간 종료일,
            'overlap_days': 겹치는 일수,
            'correlation': 일일 수익률 상관계수,
            'mean_return_diff': 일일 수익률 평균 차이,
            'std_return_diff': 일일 수익률 표준편차 차이,
            'cumulative_return_simulated': 시뮬레이션 누적 수익률,
            'cumulative_return_actual': 실제 누적 수익률,
            'cumulative_return_diff_pct': 누적 수익률 차이 (%),
            'final_price_diff_pct': 최종 가격 차이 (%)
        }

    Raises:
        ValueError: 겹치는 기간이 없을 때
    """
    # 1. 겹치는 기간 추출
    sim_dates = set(simulated_df["Date"])
    actual_dates = set(actual_df["Date"])
    overlap_dates = sim_dates & actual_dates

    if not overlap_dates:
        raise ValueError("시뮬레이션과 실제 데이터 간 겹치는 기간이 없습니다")

    # 날짜순 정렬
    overlap_dates = sorted(overlap_dates)

    # 겹치는 기간의 데이터만 추출
    sim_overlap = simulated_df[simulated_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)
    actual_overlap = actual_df[actual_df["Date"].isin(overlap_dates)].sort_values("Date").reset_index(drop=True)

    # 2. 일일 수익률 계산
    sim_returns = sim_overlap["Close"].pct_change().dropna()
    actual_returns = actual_overlap["Close"].pct_change().dropna()

    # 3. 검증 지표 계산
    correlation = float(sim_returns.corr(actual_returns))
    mean_return_diff = float(sim_returns.mean() - actual_returns.mean())
    std_return_diff = float(sim_returns.std() - actual_returns.std())

    # 4. 누적 수익률 계산
    sim_prod = (1 + sim_returns).prod()
    actual_prod = (1 + actual_returns).prod()
    sim_cumulative = float(sim_prod) - 1.0  # type: ignore[arg-type]
    actual_cumulative = float(actual_prod) - 1.0  # type: ignore[arg-type]
    cumulative_return_diff_pct = (sim_cumulative - actual_cumulative) * 100

    # 5. 최종 가격 차이
    final_sim_price = float(sim_overlap.iloc[-1]["Close"])
    final_actual_price = float(actual_overlap.iloc[-1]["Close"])
    final_price_diff_pct = float((final_sim_price - final_actual_price) / final_actual_price * 100)

    # 6. 일별 가격 차이 분석
    # 각 날짜마다 시뮬레이션 가격과 실제 가격의 차이를 계산
    price_diff_pct = ((sim_overlap["Close"] - actual_overlap["Close"]) / actual_overlap["Close"] * 100).abs()
    max_price_diff_pct = float(price_diff_pct.max())
    mean_price_diff_pct = float(price_diff_pct.mean())

    # 7. 일별 수익률 차이 분석
    return_diff_abs = (sim_returns - actual_returns).abs()
    mean_return_diff_abs = float(return_diff_abs.mean())
    max_return_diff_abs = float(return_diff_abs.max())

    return {
        "overlap_start": overlap_dates[0],
        "overlap_end": overlap_dates[-1],
        "overlap_days": len(overlap_dates),
        "correlation": correlation,
        "mean_return_diff": mean_return_diff,
        "std_return_diff": std_return_diff,
        "mean_return_diff_abs": mean_return_diff_abs,
        "max_return_diff_abs": max_return_diff_abs,
        "cumulative_return_simulated": sim_cumulative,
        "cumulative_return_actual": actual_cumulative,
        "cumulative_return_diff_pct": cumulative_return_diff_pct,
        "final_price_diff_pct": final_price_diff_pct,
        "max_price_diff_pct": max_price_diff_pct,
        "mean_price_diff_pct": mean_price_diff_pct,
    }
