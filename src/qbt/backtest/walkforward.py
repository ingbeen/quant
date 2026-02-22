"""백테스트 워크포워드 검증(WFO) 모듈

Expanding Anchored Walk-Forward Optimization을 제공한다.
- 윈도우 생성: 월 기반 Expanding Anchored 윈도우
- IS 최적화: 그리드 서치 + Calmar(CAGR/|MDD|) 목적함수
- OOS 평가: 독립 구간 백테스트
- Stitched Equity: params_schedule 기반 연속 자본곡선
- 모드 요약: OOS 성과 통계 + WFE + 파라미터 안정성 진단
"""

from datetime import date
from statistics import median

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import (
    COL_CAGR,
    COL_MDD,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST,
    DEFAULT_WFO_HOLD_DAYS_LIST,
    DEFAULT_WFO_INITIAL_IS_MONTHS,
    DEFAULT_WFO_MA_WINDOW_LIST,
    DEFAULT_WFO_OOS_MONTHS,
    DEFAULT_WFO_RECENT_MONTHS_LIST,
    DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST,
)
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyParams,
    run_buffer_strategy,
    run_grid_search,
)
from qbt.backtest.types import BestGridParams, WfoModeSummaryDict, WfoWindowResultDict
from qbt.common_constants import COL_DATE, EPSILON
from qbt.utils import get_logger

logger = get_logger(__name__)


def generate_wfo_windows(
    data_start: date,
    data_end: date,
    initial_is_months: int = DEFAULT_WFO_INITIAL_IS_MONTHS,
    oos_months: int = DEFAULT_WFO_OOS_MONTHS,
) -> list[tuple[date, date, date, date]]:
    """월 기반 Expanding Anchored 윈도우를 생성한다.

    IS는 항상 data_start에서 시작하며, OOS 기간만큼 확장하면서 윈도우를 생성한다.

    Args:
        data_start: 데이터 시작일
        data_end: 데이터 종료일
        initial_is_months: 초기 IS 기간 (개월, 기본값: 72)
        oos_months: OOS 기간 (개월, 기본값: 24)

    Returns:
        (is_start, is_end, oos_start, oos_end) 튜플 리스트

    Raises:
        ValueError: 데이터가 첫 OOS를 만들기에 부족한 경우
    """
    windows: list[tuple[date, date, date, date]] = []

    # 월 기반 오프셋 계산
    is_start = data_start

    # 초기 IS 종료 = data_start + initial_is_months
    is_end_year = data_start.year + (data_start.month - 1 + initial_is_months) // 12
    is_end_month = (data_start.month - 1 + initial_is_months) % 12 + 1
    # IS 종료일 = IS 종료 월의 마지막 날 전일 (OOS 시작 전날)
    is_end = (
        _last_day_of_month(is_end_year, is_end_month - 1)
        if is_end_month > 1
        else _last_day_of_month(is_end_year - 1, 12)
    )

    window_idx = 0
    while True:
        # OOS 시작 = IS 종료 다음 달 1일
        oos_start_year = is_end.year + (is_end.month) // 12
        oos_start_month = (is_end.month) % 12 + 1
        oos_start = date(oos_start_year, oos_start_month, 1)

        # OOS 종료 = OOS 시작 + oos_months - 1 개월의 마지막 날
        oos_end_year = oos_start.year + (oos_start.month - 1 + oos_months - 1) // 12
        oos_end_month = (oos_start.month - 1 + oos_months - 1) % 12 + 1
        oos_end = _last_day_of_month(oos_end_year, oos_end_month)

        # OOS 종료가 데이터 범위를 초과하면 중단
        if oos_start > data_end:
            break

        # OOS 종료를 데이터 범위로 클리핑
        if oos_end > data_end:
            oos_end = data_end

        windows.append((is_start, is_end, oos_start, oos_end))
        window_idx += 1

        # 다음 윈도우: IS 확장 (OOS 기간만큼)
        next_is_end_year = is_end.year + (is_end.month - 1 + oos_months) // 12
        next_is_end_month = (is_end.month - 1 + oos_months) % 12 + 1
        is_end = _last_day_of_month(next_is_end_year, next_is_end_month)

    if len(windows) == 0:
        raise ValueError(
            f"데이터 부족: 워크포워드에 최소 {initial_is_months + oos_months}개월 필요, " f"현재 기간: {data_start} ~ {data_end}"
        )

    return windows


def _last_day_of_month(year: int, month: int) -> date:
    """해당 월의 마지막 날을 반환한다."""
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1).replace(day=1) - __import__("datetime").timedelta(days=1)


def select_best_calmar_params(grid_df: pd.DataFrame) -> BestGridParams:
    """그리드 서치 결과에서 Calmar 기준 최적 파라미터를 선택한다.

    Calmar = CAGR / |MDD|. MDD=0이고 CAGR>0이면 최우선 처리.

    Args:
        grid_df: 그리드 서치 결과 DataFrame (cagr, mdd 컬럼 필수)

    Returns:
        최적 파라미터 딕셔너리 (ma_window, buy_buffer_zone_pct, sell_buffer_zone_pct,
        hold_days, recent_months)
    """
    df = grid_df.copy()

    # Calmar 계산: MDD=0 처리
    def _calmar(row: pd.Series) -> float:
        cagr = float(row[COL_CAGR])
        mdd = float(row[COL_MDD])
        abs_mdd = abs(mdd)

        if abs_mdd < EPSILON:
            # MDD=0: CAGR>0이면 최우선 (inf 대용으로 큰 값)
            if cagr > 0:
                return 1e10 + cagr
            else:
                return 0.0
        return cagr / abs_mdd

    df["calmar"] = df.apply(_calmar, axis=1)
    df = df.sort_values("calmar", ascending=False).reset_index(drop=True)

    best = df.iloc[0]
    return {
        "ma_window": int(best["ma_window"]),
        "buy_buffer_zone_pct": float(best["buy_buffer_zone_pct"]),
        "sell_buffer_zone_pct": float(best["sell_buffer_zone_pct"]),
        "hold_days": int(best["hold_days"]),
        "recent_months": int(best["recent_months"]),
    }


def run_walkforward(
    signal_df: pd.DataFrame,
    trade_df: pd.DataFrame,
    ma_window_list: list[int] | None = None,
    buy_buffer_zone_pct_list: list[float] | None = None,
    sell_buffer_zone_pct_list: list[float] | None = None,
    hold_days_list: list[int] | None = None,
    recent_months_list: list[int] | None = None,
    initial_is_months: int = DEFAULT_WFO_INITIAL_IS_MONTHS,
    oos_months: int = DEFAULT_WFO_OOS_MONTHS,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> list[WfoWindowResultDict]:
    """핵심 WFO 루프를 실행한다.

    각 윈도우에서 IS 그리드 서치 → Calmar 최적 → OOS 독립 평가를 수행한다.

    Args:
        signal_df: 시그널용 DataFrame (MA 컬럼 미포함, 내부에서 계산)
        trade_df: 매매용 DataFrame
        ma_window_list: MA 윈도우 리스트 (None이면 기본값)
        buy_buffer_zone_pct_list: 매수 버퍼존 리스트 (None이면 기본값)
        sell_buffer_zone_pct_list: 매도 버퍼존 리스트 (None이면 기본값)
        hold_days_list: 유지일 리스트 (None이면 기본값)
        recent_months_list: 조정기간 리스트 (None이면 기본값)
        initial_is_months: 초기 IS 기간 (개월)
        oos_months: OOS 기간 (개월)
        initial_capital: 초기 자본금

    Returns:
        윈도우별 결과 리스트
    """
    # 기본값 설정
    if ma_window_list is None:
        ma_window_list = list(DEFAULT_WFO_MA_WINDOW_LIST)
    if buy_buffer_zone_pct_list is None:
        buy_buffer_zone_pct_list = list(DEFAULT_WFO_BUY_BUFFER_ZONE_PCT_LIST)
    if sell_buffer_zone_pct_list is None:
        sell_buffer_zone_pct_list = list(DEFAULT_WFO_SELL_BUFFER_ZONE_PCT_LIST)
    if hold_days_list is None:
        hold_days_list = list(DEFAULT_WFO_HOLD_DAYS_LIST)
    if recent_months_list is None:
        recent_months_list = list(DEFAULT_WFO_RECENT_MONTHS_LIST)

    # 1. 윈도우 생성
    data_start = signal_df[COL_DATE].min()
    data_end = signal_df[COL_DATE].max()
    windows = generate_wfo_windows(data_start, data_end, initial_is_months, oos_months)

    logger.debug(f"WFO 윈도우 {len(windows)}개 생성 완료")

    results: list[WfoWindowResultDict] = []

    for idx, (is_start, is_end, oos_start, oos_end) in enumerate(windows):
        logger.debug(f"WFO [{idx + 1}/{len(windows)}] " f"IS={is_start}~{is_end}, OOS={oos_start}~{oos_end}")

        # 2. IS 데이터 슬라이스
        is_mask = (signal_df[COL_DATE] >= is_start) & (signal_df[COL_DATE] <= is_end)
        is_signal = signal_df[is_mask].reset_index(drop=True)
        is_trade = trade_df[is_mask].reset_index(drop=True)

        # 3. IS 그리드 서치 실행
        grid_df = run_grid_search(
            signal_df=is_signal,
            trade_df=is_trade,
            ma_window_list=ma_window_list,
            buy_buffer_zone_pct_list=buy_buffer_zone_pct_list,
            sell_buffer_zone_pct_list=sell_buffer_zone_pct_list,
            hold_days_list=hold_days_list,
            recent_months_list=recent_months_list,
            initial_capital=initial_capital,
        )

        # 4. Calmar 기준 최적 파라미터 추출
        best = select_best_calmar_params(grid_df)
        best_ma = best["ma_window"]
        best_buy_buf = best["buy_buffer_zone_pct"]
        best_sell_buf = best["sell_buffer_zone_pct"]
        best_hold = best["hold_days"]
        best_recent = best["recent_months"]

        # IS Calmar 계산 (grid_df에서 best 행의 cagr/mdd)
        best_row_mask = (
            (grid_df["ma_window"] == best_ma)
            & (grid_df["buy_buffer_zone_pct"] == best_buy_buf)
            & (grid_df["sell_buffer_zone_pct"] == best_sell_buf)
            & (grid_df["hold_days"] == best_hold)
            & (grid_df["recent_months"] == best_recent)
        )
        best_row = grid_df[best_row_mask].iloc[0]
        is_cagr = float(best_row[COL_CAGR])
        is_mdd = float(best_row[COL_MDD])
        is_trades = int(best_row["total_trades"])
        is_win_rate = float(best_row["win_rate"])
        is_calmar = _safe_calmar(is_cagr, is_mdd)

        # 5. OOS 데이터 슬라이스
        oos_mask = (signal_df[COL_DATE] >= oos_start) & (signal_df[COL_DATE] <= oos_end)
        oos_signal = signal_df[oos_mask].reset_index(drop=True)
        oos_trade = trade_df[oos_mask].reset_index(drop=True)

        # 6. OOS 독립 평가 (MA 사전 계산)
        oos_signal = add_single_moving_average(oos_signal, best_ma, ma_type="ema")

        oos_params = BufferStrategyParams(
            initial_capital=initial_capital,
            ma_window=best_ma,
            buy_buffer_zone_pct=best_buy_buf,
            sell_buffer_zone_pct=best_sell_buf,
            hold_days=best_hold,
            recent_months=best_recent,
        )

        _, _, oos_summary = run_buffer_strategy(oos_signal, oos_trade, oos_params, log_trades=False)

        oos_cagr = float(oos_summary["cagr"])
        oos_mdd = float(oos_summary["mdd"])
        oos_trades = int(oos_summary["total_trades"])
        oos_win_rate = float(oos_summary["win_rate"])
        oos_calmar = _safe_calmar(oos_cagr, oos_mdd)

        # 7. WFE (Walk-Forward Efficiency) = OOS Calmar / IS Calmar
        if abs(is_calmar) > EPSILON:
            wfe_calmar = oos_calmar / is_calmar
        else:
            wfe_calmar = 0.0

        result: WfoWindowResultDict = {
            "window_idx": idx,
            "is_start": str(is_start),
            "is_end": str(is_end),
            "oos_start": str(oos_start),
            "oos_end": str(oos_end),
            "best_ma_window": best_ma,
            "best_buy_buffer_zone_pct": best_buy_buf,
            "best_sell_buffer_zone_pct": best_sell_buf,
            "best_hold_days": best_hold,
            "best_recent_months": best_recent,
            "is_cagr": is_cagr,
            "is_mdd": is_mdd,
            "is_calmar": is_calmar,
            "is_trades": is_trades,
            "is_win_rate": is_win_rate,
            "oos_cagr": oos_cagr,
            "oos_mdd": oos_mdd,
            "oos_calmar": oos_calmar,
            "oos_trades": oos_trades,
            "oos_win_rate": oos_win_rate,
            "wfe_calmar": wfe_calmar,
        }
        results.append(result)

        logger.debug(
            f"WFO [{idx + 1}/{len(windows)}] 완료: "
            f"IS Calmar={is_calmar:.2f}, OOS Calmar={oos_calmar:.2f}, WFE={wfe_calmar:.2f}"
        )

    return results


def _safe_calmar(cagr: float, mdd: float) -> float:
    """MDD=0 안전 처리된 Calmar를 계산한다."""
    abs_mdd = abs(mdd)
    if abs_mdd < EPSILON:
        if cagr > 0:
            return 1e10
        return 0.0
    return cagr / abs_mdd


def build_params_schedule(
    window_results: list[WfoWindowResultDict],
) -> tuple[BufferStrategyParams, dict[date, BufferStrategyParams]]:
    """WFO 결과에서 params_schedule을 구성한다.

    첫 윈도우의 최적 파라미터를 초기 params로 사용하고,
    두 번째 윈도우부터 OOS 시작일을 전환 키로 사용한다.

    Args:
        window_results: run_walkforward() 반환 결과

    Returns:
        (initial_params, schedule) 튜플
            - initial_params: 첫 윈도우 기반 파라미터
            - schedule: {oos2_start: params2, oos3_start: params3, ...}
    """
    if not window_results:
        raise ValueError("window_results가 비어있습니다")

    first = window_results[0]
    initial_params = BufferStrategyParams(
        initial_capital=DEFAULT_INITIAL_CAPITAL,
        ma_window=first["best_ma_window"],
        buy_buffer_zone_pct=first["best_buy_buffer_zone_pct"],
        sell_buffer_zone_pct=first["best_sell_buffer_zone_pct"],
        hold_days=first["best_hold_days"],
        recent_months=first["best_recent_months"],
    )

    schedule: dict[date, BufferStrategyParams] = {}
    for wr in window_results[1:]:
        oos_start = date.fromisoformat(wr["oos_start"])
        schedule[oos_start] = BufferStrategyParams(
            initial_capital=DEFAULT_INITIAL_CAPITAL,
            ma_window=wr["best_ma_window"],
            buy_buffer_zone_pct=wr["best_buy_buffer_zone_pct"],
            sell_buffer_zone_pct=wr["best_sell_buffer_zone_pct"],
            hold_days=wr["best_hold_days"],
            recent_months=wr["best_recent_months"],
        )

    return initial_params, schedule


def calculate_wfo_mode_summary(
    window_results: list[WfoWindowResultDict],
    stitched_summary: dict[str, object] | None = None,
) -> WfoModeSummaryDict:
    """WFO 모드별 요약 통계를 계산한다.

    Args:
        window_results: run_walkforward() 반환 결과
        stitched_summary: stitched equity의 calculate_summary() 결과 (선택적)

    Returns:
        모드별 요약 통계 딕셔너리
    """
    n = len(window_results)

    oos_cagrs = [wr["oos_cagr"] for wr in window_results]
    oos_mdds = [wr["oos_mdd"] for wr in window_results]
    oos_calmars = [wr["oos_calmar"] for wr in window_results]
    oos_trades_list = [wr["oos_trades"] for wr in window_results]
    oos_win_rates = [wr["oos_win_rate"] for wr in window_results]
    wfe_calmars = [wr["wfe_calmar"] for wr in window_results]

    summary: WfoModeSummaryDict = {
        "n_windows": n,
        "oos_cagr_mean": sum(oos_cagrs) / n if n > 0 else 0.0,
        "oos_cagr_std": _std(oos_cagrs),
        "oos_mdd_mean": sum(oos_mdds) / n if n > 0 else 0.0,
        "oos_mdd_worst": min(oos_mdds) if oos_mdds else 0.0,
        "oos_calmar_mean": sum(oos_calmars) / n if n > 0 else 0.0,
        "oos_calmar_std": _std(oos_calmars),
        "oos_trades_total": sum(oos_trades_list),
        "oos_win_rate_mean": sum(oos_win_rates) / n if n > 0 else 0.0,
        "wfe_calmar_mean": sum(wfe_calmars) / n if n > 0 else 0.0,
        "wfe_calmar_median": median(wfe_calmars) if wfe_calmars else 0.0,
        "param_ma_windows": [wr["best_ma_window"] for wr in window_results],
        "param_buy_buffers": [wr["best_buy_buffer_zone_pct"] for wr in window_results],
        "param_sell_buffers": [wr["best_sell_buffer_zone_pct"] for wr in window_results],
        "param_hold_days": [wr["best_hold_days"] for wr in window_results],
        "param_recent_months": [wr["best_recent_months"] for wr in window_results],
    }

    # Stitched Equity 지표 추가
    if stitched_summary is not None:
        stitched_cagr = float(stitched_summary.get("cagr", 0.0))  # type: ignore[arg-type]
        stitched_mdd = float(stitched_summary.get("mdd", 0.0))  # type: ignore[arg-type]
        summary["stitched_cagr"] = stitched_cagr
        summary["stitched_mdd"] = stitched_mdd
        summary["stitched_calmar"] = _safe_calmar(stitched_cagr, stitched_mdd)
        summary["stitched_total_return_pct"] = float(stitched_summary.get("total_return_pct", 0.0))  # type: ignore[arg-type]

    return summary


def _std(values: list[float]) -> float:
    """표본 표준편차를 계산한다 (n<2이면 0.0)."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return variance**0.5
