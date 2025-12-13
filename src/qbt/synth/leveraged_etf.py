"""레버리지 ETF 시뮬레이션 모듈

QQQ와 같은 기초 자산 데이터로부터 TQQQ와 같은 레버리지 ETF를 시뮬레이션한다.
일일 리밸런싱 기반의 3배 레버리지 ETF 동작을 재현한다.
"""

from datetime import date
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd

from qbt.common_constants import (
    COL_ACTUAL_CLOSE,
    COL_ACTUAL_CUMUL_RETURN,
    COL_ACTUAL_DAILY_RETURN,
    COL_ASSET_MULTIPLE_REL_DIFF,
    COL_CLOSE,
    COL_DAILY_RETURN_ABS_DIFF,
    COL_DATE,
    COL_DATE_KR,
    COL_FFR,
    COL_FFR_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_SIMUL_CLOSE,
    COL_SIMUL_CUMUL_RETURN,
    COL_SIMUL_DAILY_RETURN,
    COL_VOLUME,
    REQUIRED_COLUMNS,
    TRADING_DAYS_PER_YEAR,
)
from qbt.synth.constants import (
    DEFAULT_EXPENSE_RANGE,
    DEFAULT_EXPENSE_STEP,
    DEFAULT_FUNDING_SPREAD,
    DEFAULT_LEVERAGE_MULTIPLIER,
    DEFAULT_SPREAD_RANGE,
    DEFAULT_SPREAD_STEP,
    MAX_EXPENSE_RATIO,
    MAX_FFR_MONTHS_DIFF,
    MAX_TOP_STRATEGIES,
)
from qbt.utils import execute_parallel, get_logger

logger = get_logger(__name__)


def calculate_daily_cost(
    date_value: date,
    ffr_df: pd.DataFrame,
    expense_ratio: float,
    funding_spread: float = DEFAULT_FUNDING_SPREAD,
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
    ffr_row = ffr_df[ffr_df[COL_FFR_DATE] == year_month_str]

    if ffr_row.empty:
        # FFR 데이터 없으면 가장 가까운 이전 월 값 사용 (최대 2개월 전까지)
        previous_dates = ffr_df[ffr_df[COL_FFR_DATE] < year_month_str]
        if not previous_dates.empty:
            closest_date_str = previous_dates.iloc[-1][COL_FFR_DATE]

            # 월 차이 계산 (yyyy-mm 문자열 파싱)
            current_year, current_month = date_value.year, date_value.month
            closest_year, closest_month = map(int, closest_date_str.split("-"))
            total_months = (current_year - closest_year) * 12 + (current_month - closest_month)

            if total_months > MAX_FFR_MONTHS_DIFF:
                raise ValueError(
                    f"FFR 데이터 부족: {year_month_str}의 FFR 데이터가 없으며, "
                    f"가장 가까운 이전 데이터는 {closest_date_str} ({total_months}개월 전)입니다. "
                    f"최대 {MAX_FFR_MONTHS_DIFF}개월 이내의 데이터만 사용 가능합니다."
                )

            ffr = float(previous_dates.iloc[-1][COL_FFR])
        else:
            raise ValueError(f"FFR 데이터 부족: {year_month_str} 이전의 FFR 데이터가 존재하지 않습니다.")
    else:
        ffr = float(ffr_row.iloc[0][COL_FFR])

    # 2. All-in funding rate 계산
    funding_rate = (ffr + funding_spread) / 100  # % → 소수

    # 3. 레버리지 비용 (2배만 - 3배 중 빌린 돈만)
    leverage_cost = funding_rate * 2

    # 4. 총 연간 비용
    annual_cost = leverage_cost + expense_ratio

    # 5. 일별 비용 (연간 거래일 수로 환산)
    daily_cost = annual_cost / TRADING_DAYS_PER_YEAR

    return daily_cost


def simulate_leveraged_etf(
    underlying_df: pd.DataFrame,
    leverage: float,
    expense_ratio: float,
    initial_price: float,
    ffr_df: pd.DataFrame,
    funding_spread: float = DEFAULT_FUNDING_SPREAD,
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

    if expense_ratio < 0 or expense_ratio > MAX_EXPENSE_RATIO:
        raise ValueError(f"expense_ratio는 0~{MAX_EXPENSE_RATIO*100}% 범위여야 합니다: {expense_ratio}")

    if initial_price <= 0:
        raise ValueError(f"initial_price는 양수여야 합니다: {initial_price}")

    # 2. 필수 컬럼 검증
    required_cols = {COL_DATE, COL_CLOSE}
    missing_cols = required_cols - set(underlying_df.columns)
    if missing_cols:
        raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_cols}")

    if underlying_df.empty:
        raise ValueError("underlying_df가 비어있습니다")

    # 3. 데이터 복사 (원본 보존)
    df = underlying_df[[COL_DATE, COL_CLOSE]].copy()

    # 4. 일일 수익률 계산
    df["underlying_return"] = df[COL_CLOSE].pct_change()

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
            current_date = df.iloc[i][COL_DATE]
            daily_cost = calculate_daily_cost(current_date, ffr_df, expense_ratio, funding_spread)

            # 레버리지 수익률
            leveraged_return = underlying_return * leverage - daily_cost

            # 가격 업데이트
            new_price = leveraged_prices[-1] * (1 + leveraged_return)
            leveraged_prices.append(new_price)

    df[COL_CLOSE] = leveraged_prices

    # 6. OHLV 데이터 구성
    # Open: 전일 Close (첫날은 initial_price)
    df[COL_OPEN] = df[COL_CLOSE].shift(1).fillna(initial_price)

    # High, Low, Volume: 0 (합성 데이터이므로 사용하지 않음)
    df[COL_HIGH] = 0.0
    df[COL_LOW] = 0.0
    df[COL_VOLUME] = 0

    # 7. 불필요한 컬럼 제거 및 순서 정렬
    result_df = df[REQUIRED_COLUMNS].copy()

    return result_df


def _evaluate_cost_model_candidate(params: dict) -> dict:
    """
    단일 비용 모델 파라미터 조합을 시뮬레이션하고 평가한다.

    그리드 서치에서 병렬 실행을 위한 헬퍼 함수. pickle 가능하도록 최상위 레벨에 정의한다.

    Args:
        params: 파라미터 딕셔너리 {
            "underlying_overlap": 기초 자산 DataFrame,
            "actual_overlap": 실제 레버리지 ETF DataFrame,
            "ffr_df": 연방기금금리 DataFrame,
            "leverage": 레버리지 배수,
            "spread": funding spread 값,
            "expense": expense ratio 값,
            "initial_price": 초기 가격,
        }

    Returns:
        후보 평가 결과 딕셔너리
    """
    # 시뮬레이션 실행
    sim_df = simulate_leveraged_etf(
        params["underlying_overlap"],
        leverage=params["leverage"],
        expense_ratio=params["expense"],
        initial_price=params["initial_price"],
        ffr_df=params["ffr_df"],
        funding_spread=params["spread"],
    )

    # 검증 지표 계산
    metrics = calculate_validation_metrics(
        simulated_df=sim_df,
        actual_df=params["actual_overlap"],
        output_path=None,  # CSV 저장 안 함
    )

    # candidate 딕셔너리 생성
    candidate = {
        "leverage": params["leverage"],
        "funding_spread": params["spread"],
        "expense_ratio": params["expense"],
        **metrics,
    }

    return candidate


def extract_overlap_period(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
) -> tuple[list[date], pd.DataFrame, pd.DataFrame]:
    """
    두 DataFrame의 겹치는 기간을 추출한다.

    Args:
        df1: 첫 번째 DataFrame (Date 컬럼 필수)
        df2: 두 번째 DataFrame (Date 컬럼 필수)

    Returns:
        (overlap_dates, df1_overlap, df2_overlap) 튜플
            - overlap_dates: 날짜순 정렬된 겹치는 날짜 리스트
            - df1_overlap: 겹치는 기간의 df1 (reset_index 완료)
            - df2_overlap: 겹치는 기간의 df2 (reset_index 완료)

    Raises:
        ValueError: 겹치는 기간이 없을 때
    """
    # 1. 겹치는 날짜 추출
    dates1 = set(df1[COL_DATE])
    dates2 = set(df2[COL_DATE])
    overlap_dates = dates1 & dates2

    if not overlap_dates:
        raise ValueError("두 DataFrame 간 겹치는 기간이 없습니다")

    # 2. 날짜순 정렬
    overlap_dates = sorted(overlap_dates)

    # 3. 겹치는 기간 데이터 추출
    df1_overlap = df1[df1[COL_DATE].isin(overlap_dates)].sort_values(COL_DATE).reset_index(drop=True)
    df2_overlap = df2[df2[COL_DATE].isin(overlap_dates)].sort_values(COL_DATE).reset_index(drop=True)

    return overlap_dates, df1_overlap, df2_overlap


def _calculate_cumulative_return_relative_diff(
    actual_prices: pd.Series,
    simulated_prices: pd.Series,
    rolling_window: int = TRADING_DAYS_PER_YEAR,
) -> pd.Series:
    """
    자산배수(Asset Multiple) 기반 상대차이를 계산한다.

    [초반 252일] 첫날 기준 고정 자산배수
      - 실제 자산배수 = 실제 종가 / 첫날 실제 종가
      - 시뮬 자산배수 = 시뮬 종가 / 첫날 시뮬 종가
      - 상대차이 = |(실제 - 시뮬)| / |실제| * 100 (%)

    [중후반 252일~] 롤링 252일 기준 자산배수
      - 실제 자산배수 = 실제 종가 / 252일 전 실제 종가
      - 시뮬 자산배수 = 시뮬 종가 / 252일 전 시뮬 종가
      - 상대차이 = |(실제 - 시뮬)| / |실제| * 100 (%)

    목적: 장기간 누적 차이가 아닌, 최근 1년 기준 상대적 성과 차이를 측정
    자산배수(multiple = price / base_price)를 사용하여 초반 구간의 상대차이 폭발 방지

    Args:
        actual_prices: 실제 가격 시계열
        simulated_prices: 시뮬레이션 가격 시계열
        rolling_window: 롤링 윈도우 크기 (기본값: 252일)

    Returns:
        자산배수 상대차이 시계열 (단위: %)

    Raises:
        ValueError: 입력 시계열 길이가 다를 때
    """
    if len(actual_prices) != len(simulated_prices):
        raise ValueError(
            f"가격 시계열 길이가 일치하지 않습니다: " f"actual={len(actual_prices)}, simulated={len(simulated_prices)}"
        )

    # 1. 초반 기간: 첫날 기준 자산배수
    initial_actual = float(actual_prices.iloc[0])
    initial_sim = float(simulated_prices.iloc[0])

    actual_multiple_early = actual_prices / initial_actual
    sim_multiple_early = simulated_prices / initial_sim

    early_period_diff = (
        (actual_multiple_early - sim_multiple_early).abs() / (actual_multiple_early.abs() + 1e-12) * 100.0
    )

    # 2. 중후반 기간: 롤링 window 기준 자산배수
    rolling_actual_base = actual_prices.shift(rolling_window)
    rolling_sim_base = simulated_prices.shift(rolling_window)

    actual_multiple_rolling = actual_prices / (rolling_actual_base + 1e-12)
    sim_multiple_rolling = simulated_prices / (rolling_sim_base + 1e-12)

    rolling_diff = (
        (actual_multiple_rolling - sim_multiple_rolling).abs() / (actual_multiple_rolling.abs() + 1e-12) * 100.0
    )

    # 3. 병합: rolling_window 이전은 고정 기준, 이후는 롤링 기준
    combined_diff = rolling_diff.fillna(early_period_diff)

    return combined_diff


def _save_daily_comparison_csv(
    sim_overlap: pd.DataFrame,
    actual_overlap: pd.DataFrame,
    asset_multiple_rel_diff_series: pd.Series,
    output_path: Path,
) -> None:
    """
    일별 비교 CSV를 저장한다.

    calculate_validation_metrics()의 헬퍼 함수.
    자산배수 상대차이는 이미 계산된 값을 받아서 사용한다.

    Args:
        sim_overlap: 겹치는 기간의 시뮬레이션 DataFrame
        actual_overlap: 겹치는 기간의 실제 DataFrame
        asset_multiple_rel_diff_series: 자산배수 상대차이 시계열 (이미 계산됨)
        output_path: CSV 저장 경로
    """
    # 1. 기본 데이터 준비
    comparison_data = {
        COL_DATE_KR: actual_overlap[COL_DATE],
        COL_ACTUAL_CLOSE: actual_overlap[COL_CLOSE],
        COL_SIMUL_CLOSE: sim_overlap[COL_CLOSE],
    }

    # 2. 일일 수익률 계산
    actual_returns = actual_overlap[COL_CLOSE].pct_change() * 100  # %
    sim_returns = sim_overlap[COL_CLOSE].pct_change() * 100  # %

    comparison_data[COL_ACTUAL_DAILY_RETURN] = actual_returns
    comparison_data[COL_SIMUL_DAILY_RETURN] = sim_returns
    comparison_data[COL_DAILY_RETURN_ABS_DIFF] = (actual_returns - sim_returns).abs()

    # 3. 누적수익률 (%)
    initial_actual = float(actual_overlap.iloc[0][COL_CLOSE])
    initial_sim = float(sim_overlap.iloc[0][COL_CLOSE])

    actual_cumulative = (actual_overlap[COL_CLOSE] / initial_actual - 1) * 100
    sim_cumulative = (sim_overlap[COL_CLOSE] / initial_sim - 1) * 100

    comparison_data[COL_ACTUAL_CUMUL_RETURN] = actual_cumulative
    comparison_data[COL_SIMUL_CUMUL_RETURN] = sim_cumulative

    # 4. 자산배수 상대차이 (롤링 기준)
    comparison_data[COL_ASSET_MULTIPLE_REL_DIFF] = asset_multiple_rel_diff_series

    # 5. DataFrame 생성 및 반올림
    comparison_df = pd.DataFrame(comparison_data)
    num_cols = [c for c in comparison_df.columns if c != COL_DATE_KR]
    comparison_df[num_cols] = comparison_df[num_cols].round(4)

    # 6. CSV 저장
    comparison_df.to_csv(output_path, index=False, encoding="utf-8-sig")


def calculate_validation_metrics(
    simulated_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    output_path: Path | None = None,
) -> dict:
    """
    시뮬레이션 검증 지표를 계산하고, 선택적으로 일별 비교 CSV를 생성한다.

    자산배수 상대차이를 한 번만 계산하고 검증 지표와 CSV 생성에 활용한다.

    Args:
        simulated_df: 시뮬레이션 DataFrame (Date, Close 컬럼 필수)
        actual_df: 실제 DataFrame (Date, Close 컬럼 필수)
        output_path: CSV 저장 경로 (None이면 저장 안 함)

    Returns:
        검증 결과 딕셔너리: {
            'overlap_start': date,
            'overlap_end': date,
            'overlap_days': int,
            'cumulative_return_simulated': float,
            'cumulative_return_actual': float,
            'asset_multiple_mean_diff_pct': float,
            'asset_multiple_rmse_diff_pct': float,
            'asset_multiple_max_diff_pct': float,
        }

    Raises:
        ValueError: 겹치는 기간이 없을 때
    """
    # 1. 겹치는 기간 추출
    overlap_dates, sim_overlap, actual_overlap = extract_overlap_period(simulated_df, actual_df)

    # 2. 일일 수익률 계산 (검증 지표용)
    sim_returns = sim_overlap[COL_CLOSE].pct_change().dropna()
    actual_returns = actual_overlap[COL_CLOSE].pct_change().dropna()

    # 3. 누적 수익률 (전통적 방식)
    sim_prod = (1 + sim_returns).prod()
    actual_prod = (1 + actual_returns).prod()
    # Scalar 타입을 Python float로 안전하게 변환 (타입 캐스팅)
    sim_cumulative = cast(float, sim_prod) - 1.0
    actual_cumulative = cast(float, actual_prod) - 1.0

    # 4. 자산배수 상대차이 계산
    asset_multiple_rel_diff_series = _calculate_cumulative_return_relative_diff(
        actual_overlap[COL_CLOSE],
        sim_overlap[COL_CLOSE],
    )

    # 5. 검증 지표 계산
    asset_multiple_mean_diff = float(asset_multiple_rel_diff_series.mean())
    asset_multiple_rmse_diff = float(np.sqrt((asset_multiple_rel_diff_series**2).mean()))
    asset_multiple_max_diff = float(asset_multiple_rel_diff_series.max())

    # 6. 일별 비교 CSV 생성 (요청 시에만)
    if output_path is not None:
        _save_daily_comparison_csv(sim_overlap, actual_overlap, asset_multiple_rel_diff_series, output_path)

    # 7. 검증 결과 반환
    return {
        # 기간 정보
        "overlap_start": overlap_dates[0],
        "overlap_end": overlap_dates[-1],
        "overlap_days": len(overlap_dates),
        # 누적 수익률
        "cumulative_return_simulated": sim_cumulative,
        "cumulative_return_actual": actual_cumulative,
        # 자산배수 기반 정확도 지표
        "asset_multiple_mean_diff_pct": asset_multiple_mean_diff,
        "asset_multiple_rmse_diff_pct": asset_multiple_rmse_diff,
        "asset_multiple_max_diff_pct": asset_multiple_max_diff,
    }


def find_optimal_cost_model(
    underlying_df: pd.DataFrame,
    actual_leveraged_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    leverage: float = DEFAULT_LEVERAGE_MULTIPLIER,
    spread_range: tuple[float, float] = DEFAULT_SPREAD_RANGE,
    spread_step: float = DEFAULT_SPREAD_STEP,
    expense_range: tuple[float, float] = DEFAULT_EXPENSE_RANGE,
    expense_step: float = DEFAULT_EXPENSE_STEP,
    max_workers: int | None = None,
) -> list[dict]:
    """
    multiplier를 고정하고 비용 모델 파라미터를 2D grid search로 캘리브레이션한다.

    funding_spread와 expense_ratio의 조합을 탐색하여 실제 레버리지 ETF와
    가장 유사한 시뮬레이션을 생성하는 최적 비용 모델을 찾는다.

    ProcessPoolExecutor를 사용하여 병렬로 실행된다.

    Args:
        underlying_df: 기초 자산 DataFrame (QQQ)
        actual_leveraged_df: 실제 레버리지 ETF DataFrame (TQQQ)
        ffr_df: 연방기금금리 DataFrame (DATE: Timestamp, FFR: float)
        leverage: 레버리지 배수 (기본값: 3.0)
        spread_range: funding spread 탐색 범위 (min, max) (%)
        spread_step: funding spread 탐색 간격 (%)
        expense_range: expense ratio 탐색 범위 (min, max) (소수)
        expense_step: expense ratio 탐색 간격 (소수)
        max_workers: 최대 워커 수 (None이면 CPU 코어 수 - 1)

    Returns:
        top_strategies: 자산배수 상대차이 평균 기준 상위 전략 리스트

    Raises:
        ValueError: 겹치는 기간이 없을 때
    """
    # 1. 겹치는 기간 추출
    overlap_dates, underlying_overlap, actual_overlap = extract_overlap_period(underlying_df, actual_leveraged_df)
    logger.debug(f"겹치는 기간: {overlap_dates[0]} ~ {overlap_dates[-1]} ({len(overlap_dates):,}일)")

    # 2. 실제 레버리지 ETF 첫날 가격을 initial_price로 사용
    initial_price = float(actual_overlap.iloc[0][COL_CLOSE])

    # 3. 2D Grid search를 위한 파라미터 조합 생성
    spread_values = np.arange(spread_range[0], spread_range[1] + 1e-12, spread_step)
    expense_values = np.arange(expense_range[0], expense_range[1] + 1e-12, expense_step)

    # 모든 파라미터 조합 리스트 생성
    param_combinations = []
    for spread in spread_values:
        for expense in expense_values:
            param_combinations.append(
                {
                    "underlying_overlap": underlying_overlap,
                    "actual_overlap": actual_overlap,
                    "ffr_df": ffr_df,
                    "leverage": leverage,
                    "spread": float(spread),
                    "expense": float(expense),
                    "initial_price": initial_price,
                }
            )

    # 4. 병렬 실행
    candidates = execute_parallel(_evaluate_cost_model_candidate, param_combinations, max_workers=max_workers)

    # 5. 자산배수 상대차이 평균 기준 오름차순 정렬 (낮을수록 우수)
    candidates.sort(key=lambda x: x["asset_multiple_mean_diff_pct"])

    # 6. 상위 전략 반환
    top_strategies = candidates[:MAX_TOP_STRATEGIES]

    return top_strategies
