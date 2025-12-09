"""레버리지 ETF 시뮬레이션 모듈

QQQ와 같은 기초 자산 데이터로부터 TQQQ와 같은 레버리지 ETF를 시뮬레이션한다.
일일 리밸런싱 기반의 3배 레버리지 ETF 동작을 재현한다.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from qbt.utils import get_logger

logger = get_logger(__name__)


def calculate_daily_cost(
    date_value: date,
    ffr_df: pd.DataFrame,
    expense_ratio: float,
    funding_spread: float = 0.6,
) -> float:
    """
    특정 날짜의 일일 비용률을 계산한다.

    Args:
        date_value: 계산 대상 날짜
        ffr_df: 연방기금금리 DataFrame (DATE: str (yyyy-mm), FFR: float)
        expense_ratio: 연간 expense ratio (예: 0.009 = 0.9%)
        funding_spread: FFR에 더해지는 스프레드 (예: 0.6 = 0.6%)

    Returns:
        일일 비용률 (소수, 예: 0.0001905 = 0.01905%)
    """
    # 1. 해당 월의 FFR 조회 (Year-Month 기준, 문자열 형식)
    year_month_str = f"{date_value.year:04d}-{date_value.month:02d}"
    ffr_row = ffr_df[ffr_df["DATE"] == year_month_str]

    if ffr_row.empty:
        # FFR 데이터 없으면 가장 가까운 이전 월 값 사용 (최대 2개월 전까지)
        previous_dates = ffr_df[ffr_df["DATE"] < year_month_str]
        if not previous_dates.empty:
            closest_date_str = previous_dates.iloc[-1]["DATE"]

            # 월 차이 계산 (yyyy-mm 문자열 파싱)
            current_year, current_month = date_value.year, date_value.month
            closest_year, closest_month = map(int, closest_date_str.split("-"))
            total_months = (current_year - closest_year) * 12 + (current_month - closest_month)

            if total_months > 2:
                raise ValueError(
                    f"FFR 데이터 부족: {year_month_str}의 FFR 데이터가 없으며, "
                    f"가장 가까운 이전 데이터는 {closest_date_str} ({total_months}개월 전)입니다. "
                    f"최대 2개월 이내의 데이터만 사용 가능합니다."
                )

            ffr = float(previous_dates.iloc[-1]["FFR"])
            logger.debug(
                f"{year_month_str} FFR 데이터 없음. "
                f"{closest_date_str} 데이터 사용 (FFR: {ffr:.4f}%)"
            )
        else:
            raise ValueError(
                f"FFR 데이터 부족: {year_month_str} 이전의 FFR 데이터가 존재하지 않습니다."
            )
    else:
        ffr = float(ffr_row.iloc[0]["FFR"])

    # 2. All-in funding rate 계산
    funding_rate = (ffr + funding_spread) / 100  # % → 소수

    # 3. 레버리지 비용 (2배만 - 3배 중 빌린 돈만)
    leverage_cost = funding_rate * 2

    # 4. 총 연간 비용
    annual_cost = leverage_cost + expense_ratio

    # 5. 일별 비용 (252 영업일 가정)
    daily_cost = annual_cost / 252

    return daily_cost


def simulate_leveraged_etf(
    underlying_df: pd.DataFrame,
    leverage: float,
    expense_ratio: float,
    initial_price: float,
    ffr_df: pd.DataFrame,
    funding_spread: float = 0.6,
) -> pd.DataFrame:
    """
    기초 자산 데이터로부터 레버리지 ETF를 시뮬레이션한다.

    일일 리밸런싱을 가정하여 각 거래일마다 기초 자산 수익률의
    레버리지 배수만큼 움직이도록 계산한다. 스왑비용은 연방기금금리와
    스프레드를 기반으로 동적으로 계산하며, expense ratio를 추가한다.

    Args:
        underlying_df: 기초 자산 DataFrame (Date, Close 컬럼 필수)
        leverage: 레버리지 배수 (예: 3.0)
        expense_ratio: 연간 비용 비율 (예: 0.009 = 0.9%)
        initial_price: 시작 가격
        ffr_df: 연방기금금리 DataFrame (DATE: Timestamp, FFR: float)
        funding_spread: FFR에 더해지는 스프레드 (예: 0.6 = 0.6%)

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

    # 5. 레버리지 ETF 가격 계산 (복리, 동적 비용 반영)
    # 첫 날은 initial_price, 이후는 전일 가격 * (1 + 수익률)
    leveraged_prices = [initial_price]

    for i in range(1, len(df)):
        underlying_return = df.iloc[i]["underlying_return"]

        if pd.isna(underlying_return):
            # 첫 번째 행의 경우 수익률이 NaN이므로 initial_price 유지
            leveraged_prices.append(initial_price)
        else:
            # 동적 비용 계산
            current_date = df.iloc[i]["Date"]
            daily_cost = calculate_daily_cost(current_date, ffr_df, expense_ratio, funding_spread)

            # 레버리지 수익률
            leveraged_return = underlying_return * leverage - daily_cost

            # 가격 업데이트
            new_price = leveraged_prices[-1] * (1 + leveraged_return)
            leveraged_prices.append(new_price)

    df["Close"] = leveraged_prices

    # 6. OHLV 데이터 구성
    # Open: 전일 Close (첫날은 initial_price)
    df["Open"] = df["Close"].shift(1).fillna(initial_price)

    # High, Low, Volume: 0 (합성 데이터이므로 사용하지 않음)
    df["High"] = 0.0
    df["Low"] = 0.0
    df["Volume"] = 0

    # 7. 불필요한 컬럼 제거 및 순서 정렬
    result_df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()

    return result_df


def find_optimal_multiplier(
    underlying_df: pd.DataFrame,
    actual_leveraged_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_ratio: float = 0.009,
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
        ffr_df: 연방기금금리 DataFrame (DATE: Timestamp, FFR: float)
        expense_ratio: 연간 비용 비율 (예: 0.009 = 0.9%)
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
            leverage=float(multiplier),
            expense_ratio=expense_ratio,
            initial_price=initial_price,
            ffr_df=ffr_df,
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
            best_multiplier = float(multiplier)
            best_metrics = {
                "multiplier": float(multiplier),
                "correlation": correlation,
                "rmse": rmse,
                "final_price_diff_pct": final_price_diff_pct,
                "score": score,
            }

    return best_multiplier, best_metrics


def find_optimal_cost_model(
    underlying_df: pd.DataFrame,
    actual_leveraged_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    leverage: float = 3.0,
    spread_range: tuple[float, float] = (0.4, 0.8),
    spread_step: float = 0.01,
    expense_range: tuple[float, float] = (0.0075, 0.0105),
    expense_step: float = 0.0005,
) -> list[dict]:
    """
    multiplier를 고정하고 비용 모델 파라미터를 2D grid search로 캘리브레이션한다.

    funding_spread와 expense_ratio의 조합을 탐색하여 실제 레버리지 ETF와
    가장 유사한 시뮬레이션을 생성하는 최적 비용 모델을 찾는다.

    Args:
        underlying_df: 기초 자산 DataFrame (QQQ)
        actual_leveraged_df: 실제 레버리지 ETF DataFrame (TQQQ)
        ffr_df: 연방기금금리 DataFrame (DATE: Timestamp, FFR: float)
        leverage: 레버리지 배수 (기본값: 3.0)
        spread_range: funding spread 탐색 범위 (min, max) (%)
        spread_step: funding spread 탐색 간격 (%)
        expense_range: expense ratio 탐색 범위 (min, max) (소수)
        expense_step: expense ratio 탐색 간격 (소수)

    Returns:
        top_strategies: 누적수익률 상대차이 기준 상위 50개 전략 리스트

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

    # 3. 2D Grid search
    spread_values = np.arange(spread_range[0], spread_range[1] + 1e-12, spread_step)
    expense_values = np.arange(expense_range[0], expense_range[1] + 1e-12, expense_step)

    # 전체 경우의 수 계산
    total_cases = len(spread_values) * len(expense_values)
    logger.debug(f"Grid search 시작 - 전체 경우의 수: {total_cases:,}")

    candidates = []
    current_case = 0

    for spread in spread_values:
        for expense in expense_values:
            current_case += 1

            # 진행도 로그 (매 10케이스마다 출력)
            if current_case % 10 == 0 or current_case == 1:
                progress_pct = (current_case / total_cases) * 100
                logger.debug(f"진행도: {current_case:,}/{total_cases:,} ({progress_pct:.1f}%)")

            # 시뮬레이션 실행
            sim_df = simulate_leveraged_etf(
                underlying_overlap,
                leverage=leverage,
                expense_ratio=float(expense),
                initial_price=initial_price,
                ffr_df=ffr_df,
                funding_spread=float(spread),
            )

            # 검증 지표 계산
            metrics = validate_simulation(sim_df, actual_overlap)

            # candidate 딕셔너리 생성
            candidate = {
                "leverage": leverage,
                "funding_spread": spread,
                "expense_ratio": expense,
                **metrics,
            }
            candidates.append(candidate)

    # 4. 누적수익률_상대차이_pct 기준 오름차순 정렬
    candidates.sort(key=lambda x: x["cumulative_return_relative_diff_pct"])

    # 5. 상위 50개 전략 반환
    top_strategies = candidates[:50]

    return top_strategies


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
            # 기간 정보
            'overlap_start': 겹치는 기간 시작일,
            'overlap_end': 겹치는 기간 종료일,
            'overlap_days': 겹치는 일수,

            # 누적 수익률
            'cumulative_return_simulated': 시뮬레이션 누적 수익률,
            'cumulative_return_actual': 실제 누적 수익률,
            'cumulative_return_relative_diff_pct': 누적 수익률 상대 차이 (%),
            'rmse_cumulative_return': 누적수익률 RMSE,
            'max_error_cumulative_return': 누적수익률 최대 오차,
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

    # 3. 누적 수익률 계산
    sim_prod = (1 + sim_returns).prod()
    actual_prod = (1 + actual_returns).prod()
    sim_cumulative = float(sim_prod) - 1.0  # type: ignore[arg-type]
    actual_cumulative = float(actual_prod) - 1.0  # type: ignore[arg-type]

    # 3-1. 누적 수익률 상대 오차 계산
    cumulative_return_relative_diff_pct = (
        abs(sim_cumulative - actual_cumulative) / (abs(actual_cumulative) + 1e-12) * 100.0
    )

    # 4. 누적수익률 기준 RMSE, MaxError
    sim_cumulative_series = sim_overlap["Close"] / sim_overlap.iloc[0]["Close"] - 1
    actual_cumulative_series = actual_overlap["Close"] / actual_overlap.iloc[0]["Close"] - 1
    cumulative_return_diff_series = actual_cumulative_series - sim_cumulative_series
    rmse_cumulative_return = float(np.sqrt((cumulative_return_diff_series**2).mean()))
    max_error_cumulative_return = float(np.abs(cumulative_return_diff_series).max())

    return {
        # 기간 정보
        "overlap_start": overlap_dates[0],
        "overlap_end": overlap_dates[-1],
        "overlap_days": len(overlap_dates),
        # 누적 수익률
        "cumulative_return_simulated": sim_cumulative,
        "cumulative_return_actual": actual_cumulative,
        "cumulative_return_relative_diff_pct": cumulative_return_relative_diff_pct,
        "rmse_cumulative_return": rmse_cumulative_return,
        "max_error_cumulative_return": max_error_cumulative_return,
    }


def generate_daily_comparison_csv(
    simulated_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    output_path: Path,
) -> None:
    """
    일별 상세 비교 CSV를 생성한다.

    시뮬레이션 결과와 실제 데이터를 날짜별로 비교하여
    각종 지표를 계산하고 CSV 파일로 저장한다.

    Args:
        simulated_df: 시뮬레이션 DataFrame (Date, Close 컬럼 필수)
        actual_df: 실제 DataFrame (Date, Close 컬럼 필수)
        output_path: CSV 저장 경로 (pathlib.Path)

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

    # 2. 기본 데이터 준비
    comparison_data = {
        "날짜": actual_overlap["Date"],
        "실제_종가": actual_overlap["Close"],
        "시뮬_종가": sim_overlap["Close"],
    }

    # 3. 일일 수익률 계산
    actual_returns = actual_overlap["Close"].pct_change() * 100  # %
    sim_returns = sim_overlap["Close"].pct_change() * 100  # %

    comparison_data["실제_일일수익률"] = actual_returns
    comparison_data["시뮬_일일수익률"] = sim_returns
    comparison_data["일일수익률_차이"] = (actual_returns - sim_returns).abs()

    # 4. 누적수익률
    initial_actual = float(actual_overlap.iloc[0]["Close"])
    initial_sim = float(sim_overlap.iloc[0]["Close"])

    actual_cumulative = (actual_overlap["Close"] / initial_actual - 1) * 100  # %
    sim_cumulative = (sim_overlap["Close"] / initial_sim - 1) * 100  # %

    comparison_data["실제_누적수익률"] = actual_cumulative
    comparison_data["시뮬_누적수익률"] = sim_cumulative
    comparison_data["누적수익률_차이"] = actual_cumulative - sim_cumulative

    # 6. DataFrame 생성 및 반올림
    comparison_df = pd.DataFrame(comparison_data)
    num_cols = [c for c in comparison_df.columns if c != "날짜"]
    comparison_df[num_cols] = comparison_df[num_cols].round(4)

    # 7. CSV 저장
    comparison_df.to_csv(output_path, index=False, encoding="utf-8-sig")
