"""파라미터 고원 분석 모듈

고원 분석 CSV(param_plateau/)를 로딩하고 시각화용 데이터를 가공한다.
4개 파라미터(ma_window, buy_buffer, sell_buffer, hold_days)의
고원 구간 탐지 및 현재 확정값 제공 기능을 포함한다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from qbt.backtest.constants import (
    FIXED_4P_BUY_BUFFER_ZONE_PCT,
    FIXED_4P_HOLD_DAYS,
    FIXED_4P_MA_WINDOW,
    FIXED_4P_SELL_BUFFER_ZONE_PCT,
)
from qbt.common_constants import BACKTEST_RESULTS_DIR

# 고원 분석 결과 디렉토리
_PLATEAU_DIR = BACKTEST_RESULTS_DIR / "param_plateau"

# 4P 확정 파라미터 (constants.py FIXED_4P_* 참조)
_CURRENT_VALUES: dict[str, int | float] = {
    "ma_window": FIXED_4P_MA_WINDOW,
    "buy_buffer": FIXED_4P_BUY_BUFFER_ZONE_PCT,
    "sell_buffer": FIXED_4P_SELL_BUFFER_ZONE_PCT,
    "hold_days": FIXED_4P_HOLD_DAYS,
}


def load_plateau_pivot(param_name: str, metric: str) -> pd.DataFrame:
    """피벗 CSV를 로드한다.

    Args:
        param_name: 파라미터명 ("hold_days", "sell_buffer", "buy_buffer", "ma_window")
        metric: 지표명 ("calmar", "cagr", "mdd", "trades", "win_rate")

    Returns:
        피벗 DataFrame (index=자산, columns=파라미터값)

    Raises:
        FileNotFoundError: CSV 파일이 존재하지 않을 때
    """
    filename = f"param_plateau_{param_name}_{metric}.csv"
    path = _PLATEAU_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"고원 분석 결과 파일을 찾을 수 없습니다: {path}")

    return pd.read_csv(path, index_col=0)


def load_plateau_detail() -> pd.DataFrame:
    """상세 CSV를 로드한다.

    Returns:
        상세 결과 DataFrame

    Raises:
        FileNotFoundError: CSV 파일이 존재하지 않을 때
    """
    path = _PLATEAU_DIR / "param_plateau_all_detail.csv"

    if not path.exists():
        raise FileNotFoundError(f"고원 분석 상세 파일을 찾을 수 없습니다: {path}")

    return pd.read_csv(path)


def get_current_value(param_name: str) -> int | float:
    """현재 확정 파라미터값을 반환한다.

    Args:
        param_name: 파라미터명 ("ma_window", "buy_buffer", "sell_buffer", "hold_days")

    Returns:
        확정 파라미터 값

    Raises:
        ValueError: 알 수 없는 파라미터명
    """
    if param_name not in _CURRENT_VALUES:
        raise ValueError(f"알 수 없는 파라미터: '{param_name}'. " f"사용 가능: {list(_CURRENT_VALUES.keys())}")
    return _CURRENT_VALUES[param_name]


def get_plateau_dir() -> Path:
    """고원 분석 결과 디렉토리 경로를 반환한다.

    Returns:
        고원 분석 결과 디렉토리 Path
    """
    return _PLATEAU_DIR


def find_plateau_range(
    series: pd.Series[float],
    threshold_ratio: float = 0.9,
) -> tuple[float, float] | None:
    """고원 구간을 탐지한다.

    최대값 대비 threshold_ratio 이상인 연속 범위를 찾는다.

    Args:
        series: 파라미터값을 인덱스, 지표값을 값으로 가지는 Series
        threshold_ratio: 최대값 대비 임계 비율 (0.9 = 90%)

    Returns:
        (시작값, 끝값) 튜플. 고원 구간이 없으면 None
    """
    if series.empty:
        return None

    max_val = float(series.max())
    if max_val <= 0:
        return None

    threshold = max_val * threshold_ratio

    # threshold 이상인 값의 인덱스를 추출
    above_mask = series >= threshold
    above_indices = series.index[above_mask].tolist()

    if not above_indices:
        return None

    return (float(above_indices[0]), float(above_indices[-1]))
