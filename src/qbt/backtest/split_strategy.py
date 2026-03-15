"""분할 매수매도 오케스트레이터 모듈

3개 트랜치(ma250/ma200/ma150)를 공유 자본으로 운용하는 오케스트레이터.
매수 시 현금 ÷ 미보유 트랜치 수로 배분, 매도 시 대금은 공유 현금으로 복귀한다.

포함 내용:
- DataClasses: SplitTrancheConfig, SplitStrategyConfig, SplitTrancheResult, SplitStrategyResult
- 설정 리스트: SPLIT_CONFIGS
- 핵심 함수: run_split_backtest
- 헬퍼 함수: _combine_trades, _calculate_combined_summary, _build_params_json, _build_combined_equity

설계 근거: docs/tranche_architecture.md, docs/tranche_final_recommendation.md
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from qbt.backtest.analysis import add_single_moving_average, calculate_summary
from qbt.backtest.constants import (
    SLIPPAGE_RATE,
    SPLIT_TRANCHE_IDS,
    SPLIT_TRANCHE_MA_WINDOWS,
    SPLIT_TRANCHE_WEIGHTS,
)
from qbt.backtest.strategies.buffer_zone import BufferZoneConfig
from qbt.backtest.strategies.buffer_zone_helpers import (
    BufferStrategyResultDict,
    HoldState,
    PendingOrder,
    TradeRecord,
    _compute_bands,  # pyright: ignore[reportPrivateUsage]
    _detect_buy_signal,  # pyright: ignore[reportPrivateUsage]
    _detect_sell_signal,  # pyright: ignore[reportPrivateUsage]
)
from qbt.backtest.types import OpenPositionDict, SummaryDict
from qbt.common_constants import (
    BUFFER_ZONE_QQQ_RESULTS_DIR,
    BUFFER_ZONE_TQQQ_RESULTS_DIR,
    COL_CLOSE,
    COL_DATE,
    COL_OPEN,
    QQQ_DATA_PATH,
    SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR,
    SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR,
    TQQQ_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.data_loader import extract_overlap_period, load_stock_data

logger = get_logger(__name__)


# ============================================================================
# 데이터 클래스
# ============================================================================


@dataclass(frozen=True)
class SplitTrancheConfig:
    """분할 매수매도 트랜치별 설정."""

    tranche_id: str  # "ma250", "ma200", "ma150"
    weight: float  # 0.33, 0.34, 0.33
    ma_window: int  # 250, 200, 150


@dataclass(frozen=True)
class SplitStrategyConfig:
    """분할 매수매도 전략 설정."""

    strategy_name: str  # "split_buffer_zone_tqqq"
    display_name: str  # "분할 버퍼존 (TQQQ)"
    base_config: BufferZoneConfig  # 기존 자산 설정 (데이터 경로, 4P 파라미터)
    total_capital: float  # 총 자본금
    tranches: tuple[SplitTrancheConfig, ...]  # 트랜치별 설정 (frozen 지원)
    result_dir: Path  # 결과 저장 디렉토리


@dataclass
class SplitTrancheResult:
    """트랜치별 백테스트 결과."""

    tranche_id: str
    config: SplitTrancheConfig
    trades_df: pd.DataFrame
    equity_df: pd.DataFrame
    summary: BufferStrategyResultDict


@dataclass
class SplitStrategyResult:
    """분할 매수매도 전체 결과."""

    strategy_name: str
    display_name: str
    combined_equity_df: pd.DataFrame  # 합산 에쿼티 (시각화 메인)
    combined_trades_df: pd.DataFrame  # 전체 거래 (tranche_id 포함)
    combined_summary: SummaryDict  # 분할 레벨 성과 지표
    per_tranche: list[SplitTrancheResult]  # 트랜치별 결과
    config: SplitStrategyConfig  # 원본 설정 (재현성)
    params_json: dict[str, Any]  # JSON 저장용
    signal_df: pd.DataFrame  # 시그널 데이터 (OHLCV + MA, 시각화용)


# ============================================================================
# 기본 트랜치 설정 생성
# ============================================================================


def _build_default_tranches() -> tuple[SplitTrancheConfig, ...]:
    """기본 트랜치 설정을 생성한다.

    constants.py의 SPLIT_TRANCHE_* 상수를 기반으로
    SplitTrancheConfig 튜플을 생성한다.

    Returns:
        tuple: 기본 트랜치 설정 (ma250/ma200/ma150)
    """
    return tuple(
        SplitTrancheConfig(
            tranche_id=tranche_id,
            weight=weight,
            ma_window=ma_window,
        )
        for tranche_id, weight, ma_window in zip(
            SPLIT_TRANCHE_IDS,
            SPLIT_TRANCHE_WEIGHTS,
            SPLIT_TRANCHE_MA_WINDOWS,
            strict=True,
        )
    )


_DEFAULT_TRANCHES = _build_default_tranches()


# ============================================================================
# base_config 참조용 BufferZoneConfig
# ============================================================================

_TQQQ_BASE_CONFIG = BufferZoneConfig(
    strategy_name="buffer_zone_tqqq",
    display_name="버퍼존 전략 (TQQQ)",
    signal_data_path=QQQ_DATA_PATH,
    trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
    result_dir=BUFFER_ZONE_TQQQ_RESULTS_DIR,
)

_QQQ_BASE_CONFIG = BufferZoneConfig(
    strategy_name="buffer_zone_qqq",
    display_name="버퍼존 전략 (QQQ)",
    signal_data_path=QQQ_DATA_PATH,
    trade_data_path=QQQ_DATA_PATH,
    result_dir=BUFFER_ZONE_QQQ_RESULTS_DIR,
)


# ============================================================================
# SPLIT_CONFIGS 리스트
# ============================================================================

SPLIT_CONFIGS: list[SplitStrategyConfig] = [
    SplitStrategyConfig(
        strategy_name="split_buffer_zone_tqqq",
        display_name="분할 버퍼존 (TQQQ)",
        base_config=_TQQQ_BASE_CONFIG,
        total_capital=10_000_000.0,
        tranches=_DEFAULT_TRANCHES,
        result_dir=SPLIT_BUFFER_ZONE_TQQQ_RESULTS_DIR,
    ),
    SplitStrategyConfig(
        strategy_name="split_buffer_zone_qqq",
        display_name="분할 버퍼존 (QQQ)",
        base_config=_QQQ_BASE_CONFIG,
        total_capital=10_000_000.0,
        tranches=_DEFAULT_TRANCHES,
        result_dir=SPLIT_BUFFER_ZONE_QQQ_RESULTS_DIR,
    ),
]


# ============================================================================
# 헬퍼 함수
# ============================================================================


def _get_latest_entry_price(
    trades_df: pd.DataFrame,
    equity_df: pd.DataFrame,
    current_date: object,
    open_position: OpenPositionDict | None = None,
) -> float | None:
    """트랜치의 현재 보유 포지션에 대한 entry_price를 반환한다.

    trades_df에서 entry_date <= current_date인 매수 기록 중
    아직 청산되지 않은(exit_date > current_date이거나 미청산) 기록의 entry_price를 반환한다.
    미청산 포지션은 open_position에서 추출한다.

    Args:
        trades_df: 해당 트랜치의 거래 기록
        equity_df: 해당 트랜치의 에쿼티 기록
        current_date: 현재 날짜
        open_position: 미청산 포지션 정보 (summary의 open_position)

    Returns:
        float | None: 현재 보유 포지션의 진입가 (없으면 None)
    """
    if trades_df.empty:
        # trades가 없지만 미청산 포지션이 있는 경우
        if open_position is not None:
            return float(open_position["entry_price"])
        return None

    eligible = trades_df[trades_df["entry_date"] <= current_date]
    if eligible.empty:
        return None

    last_trade = eligible.iloc[-1]

    # exit_date가 current_date 이후이면 아직 보유 중 → entry_price 반환
    if last_trade["exit_date"] > current_date:
        return float(last_trade["entry_price"])

    # 모든 거래가 청산 완료 → 미청산 포지션 케이스
    if open_position is not None:
        return float(open_position["entry_price"])
    return None


def _combine_trades(
    tranche_results: list[SplitTrancheResult],
) -> pd.DataFrame:
    """트랜치별 거래를 합산하여 태깅된 DataFrame을 생성한다.

    기존 TradeRecord 컬럼 + tranche_id, tranche_seq, ma_window 컬럼을 추가한다.
    entry_date 오름차순 → tranche_id 오름차순으로 정렬한다.

    Args:
        tranche_results: 트랜치별 백테스트 결과 리스트

    Returns:
        pd.DataFrame: 전체 거래 DataFrame (빈 DataFrame 가능)
    """
    all_trades: list[pd.DataFrame] = []

    for tr in tranche_results:
        if tr.trades_df.empty:
            continue

        trades_copy = tr.trades_df.copy()
        trades_copy["tranche_id"] = tr.tranche_id
        trades_copy["tranche_seq"] = range(1, len(trades_copy) + 1)
        trades_copy["ma_window"] = tr.config.ma_window
        all_trades.append(trades_copy)

    if not all_trades:
        return pd.DataFrame()

    combined = pd.concat(all_trades, ignore_index=True)
    combined = combined.sort_values(["entry_date", "tranche_id"]).reset_index(drop=True)

    return combined


def _calculate_combined_summary(
    combined_equity_df: pd.DataFrame,
    combined_trades_df: pd.DataFrame,
    total_capital: float,
    tranche_results: list[SplitTrancheResult],
) -> SummaryDict:
    """합산 에쿼티로부터 분할 레벨 요약 지표를 계산한다.

    calculate_summary()를 재사용하고, 미청산 포지션 수를 별도 계산한다.

    Args:
        combined_equity_df: 합산 에쿼티 DataFrame
        combined_trades_df: 합산 거래 DataFrame
        total_capital: 총 자본금
        tranche_results: 트랜치별 결과 (미청산 포지션 확인용)

    Returns:
        SummaryDict: 분할 레벨 성과 지표
    """
    # 1. calculate_summary()용 equity_df 준비 (Date, equity 컬럼만 필요)
    equity_for_summary = combined_equity_df[[COL_DATE, "equity"]].copy()

    # 2. calculate_summary() 호출
    summary = calculate_summary(combined_trades_df, equity_for_summary, total_capital)

    return summary


def _build_params_json(
    config: SplitStrategyConfig,
) -> dict[str, Any]:
    """JSON 저장용 파라미터 딕셔너리를 생성한다.

    Args:
        config: 분할 매수매도 전략 설정

    Returns:
        dict: JSON 저장용 파라미터
    """
    tranches_info: list[dict[str, Any]] = []
    for tranche in config.tranches:
        info: dict[str, Any] = {
            "tranche_id": tranche.tranche_id,
            "ma_window": tranche.ma_window,
            "weight": tranche.weight,
            "initial_capital": round(config.total_capital * tranche.weight),
        }
        tranches_info.append(info)

    return {
        "total_capital": round(config.total_capital),
        "buy_buffer_zone_pct": config.base_config.buy_buffer_zone_pct,
        "sell_buffer_zone_pct": config.base_config.sell_buffer_zone_pct,
        "hold_days": config.base_config.hold_days,
        "ma_type": config.base_config.ma_type,
        "tranches": tranches_info,
    }


# ============================================================================
# 공유 자본 오케스트레이터
# ============================================================================


@dataclass
class _TrancheState:
    """트랜치별 내부 상태 (공유 자본 오케스트레이터용)."""

    tranche_id: str
    ma_window: int
    ma_col: str
    buy_buffer_zone_pct: float
    sell_buffer_zone_pct: float
    hold_days: int
    position: int = 0
    entry_price: float = 0.0
    entry_date: date | None = None
    entry_hold_days: int = 0
    pending_order: PendingOrder | None = None
    hold_state: HoldState | None = None
    prev_upper_band: float = 0.0
    prev_lower_band: float = 0.0
    trades: list[TradeRecord] | None = None
    equity_records: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.trades is None:
            self.trades = []
        if self.equity_records is None:
            self.equity_records = []


def run_split_backtest(
    config: SplitStrategyConfig,
) -> SplitStrategyResult:
    """공유 자본 방식의 분할 매수매도 백테스트를 실행한다.

    날짜별 통합 루프에서 3개 트랜치의 시그널을 판정하고,
    공유 현금(shared_cash)에서 자본을 배분하여 매수한다.

    매수 투입 자본 = shared_cash ÷ 미보유 트랜치 수 (자기 포함)
    매도 시 = 해당 트랜치 보유 주식 전량 매도, 매도 대금은 shared_cash에 복귀

    Args:
        config: 분할 매수매도 전략 설정

    Returns:
        SplitStrategyResult: 분할 매수매도 결과

    Raises:
        ValueError: 트랜치 설정이 유효하지 않은 경우
    """
    # 1. 입력 검증
    tranche_ids = [t.tranche_id for t in config.tranches]
    if len(tranche_ids) != len(set(tranche_ids)):
        raise ValueError(f"중복된 트랜치 ID가 존재합니다: {tranche_ids}")

    logger.debug(f"분할 매수매도 실행 시작: {config.strategy_name}, 트랜치={tranche_ids}")

    # 2. 데이터 로딩 (1회만)
    bc = config.base_config
    if bc.signal_data_path == bc.trade_data_path:
        trade_df = load_stock_data(bc.trade_data_path)
        signal_df = trade_df.copy()
    else:
        signal_df = load_stock_data(bc.signal_data_path)
        trade_df = load_stock_data(bc.trade_data_path)
        signal_df, trade_df = extract_overlap_period(signal_df, trade_df)

    # 3. 모든 트랜치 MA 사전 계산
    for tranche in config.tranches:
        ma_col = f"ma_{tranche.ma_window}"
        if ma_col not in signal_df.columns:
            signal_df = add_single_moving_average(signal_df, tranche.ma_window, ma_type=bc.ma_type)

    # 4. MA 유효 시작점 결정 (가장 큰 MA 윈도우 기준)
    max_ma_window = max(t.ma_window for t in config.tranches)
    max_ma_col = f"ma_{max_ma_window}"
    valid_mask = signal_df[max_ma_col].notna()
    signal_df = signal_df[valid_mask].reset_index(drop=True)
    trade_df = trade_df[valid_mask].reset_index(drop=True)

    logger.debug(f"데이터 로딩 완료: {len(signal_df)}행")

    # 5. 트랜치별 상태 초기화
    states: dict[str, _TrancheState] = {}
    for tranche in config.tranches:
        ma_col = f"ma_{tranche.ma_window}"
        first_ma = signal_df.iloc[0][ma_col]
        upper, lower = _compute_bands(first_ma, bc.buy_buffer_zone_pct, bc.sell_buffer_zone_pct)
        states[tranche.tranche_id] = _TrancheState(
            tranche_id=tranche.tranche_id,
            ma_window=tranche.ma_window,
            ma_col=ma_col,
            buy_buffer_zone_pct=bc.buy_buffer_zone_pct,
            sell_buffer_zone_pct=bc.sell_buffer_zone_pct,
            hold_days=bc.hold_days,
            prev_upper_band=upper,
            prev_lower_band=lower,
        )

    shared_cash = config.total_capital

    # 첫 날 에쿼티 기록
    first_date = signal_df.iloc[0][COL_DATE]
    for st in states.values():
        assert st.equity_records is not None
        st.equity_records.append(
            {
                COL_DATE: first_date,
                "equity": 0.0,
                "position": 0,
            }
        )

    # 6. 날짜별 통합 루프
    for i in range(1, len(signal_df)):
        signal_row = signal_df.iloc[i]
        trade_row = trade_df.iloc[i]
        current_date = signal_row[COL_DATE]
        trade_open = trade_row[COL_OPEN]
        trade_close = trade_row[COL_CLOSE]

        # 6-1. pending order 체결 (트랜치 순서: ma250 → ma200 → ma150)
        for tid in [t.tranche_id for t in config.tranches]:
            st = states[tid]
            if st.pending_order is None:
                continue

            if st.pending_order.order_type == "buy" and st.position == 0:
                # 매수 체결: 체결 시점의 shared_cash에서 배분
                buy_price = trade_open * (1 + SLIPPAGE_RATE)
                unowned = sum(1 for s in states.values() if s.position == 0)
                buy_capital = shared_cash / unowned if unowned > 0 else 0.0
                shares = int(buy_capital / buy_price)

                if shares > 0:
                    cost = shares * buy_price
                    shared_cash -= cost
                    st.position = shares
                    st.entry_price = buy_price
                    st.entry_date = current_date
                    st.entry_hold_days = st.pending_order.hold_days_used
                    logger.debug(
                        f"매수 체결: {tid}, {current_date}, "
                        f"가격={buy_price:.2f}, 수량={shares}, "
                        f"배분자본={buy_capital:.0f}, 미보유={unowned}"
                    )

            elif st.pending_order.order_type == "sell" and st.position > 0:
                # 매도 체결: 대금을 shared_cash에 복귀
                sell_price = trade_open * (1 - SLIPPAGE_RATE)
                sell_amount = st.position * sell_price

                assert st.trades is not None
                assert st.entry_date is not None
                trade_record: TradeRecord = {
                    "entry_date": st.entry_date,
                    "exit_date": current_date,
                    "entry_price": st.entry_price,
                    "exit_price": sell_price,
                    "shares": st.position,
                    "pnl": (sell_price - st.entry_price) * st.position,
                    "pnl_pct": (sell_price - st.entry_price) / st.entry_price,
                    "buy_buffer_pct": st.pending_order.buy_buffer_zone_pct,
                    "hold_days_used": st.entry_hold_days,
                }
                st.trades.append(trade_record)
                shared_cash += sell_amount
                logger.debug(
                    f"매도 체결: {tid}, {current_date}, "
                    f"손익률={trade_record['pnl_pct']*100:.2f}%, "
                    f"복귀금={sell_amount:.0f}"
                )
                st.position = 0
                st.entry_price = 0.0
                st.entry_date = None

            st.pending_order = None

        # 6-2. 밴드 계산 + 에쿼티 기록
        for st in states.values():
            ma_value = signal_row[st.ma_col]
            upper, lower = _compute_bands(ma_value, st.buy_buffer_zone_pct, st.sell_buffer_zone_pct)

            # 에쿼티: 해당 트랜치의 주식 평가액
            tranche_equity = float(st.position * trade_close)
            assert st.equity_records is not None
            st.equity_records.append(
                {
                    COL_DATE: current_date,
                    "equity": tranche_equity,
                    "position": st.position,
                }
            )

            # 6-3. 시그널 판정
            prev_signal_row = signal_df.iloc[i - 1]

            if st.position == 0:
                # 매수 로직 (hold_days 상태머신)
                if st.hold_state is not None:
                    if signal_row[COL_CLOSE] > upper:
                        st.hold_state["days_passed"] += 1
                        if st.hold_state["days_passed"] >= st.hold_state["hold_days_required"]:
                            st.pending_order = PendingOrder(
                                order_type="buy",
                                signal_date=current_date,
                                buy_buffer_zone_pct=st.hold_state["buffer_pct"],
                                hold_days_used=st.hold_state["hold_days_required"],
                            )
                            st.hold_state = None
                    else:
                        st.hold_state = None

                if st.hold_state is None and st.pending_order is None:
                    breakout = _detect_buy_signal(
                        prev_close=prev_signal_row[COL_CLOSE],
                        close=signal_row[COL_CLOSE],
                        prev_upper_band=st.prev_upper_band,
                        upper_band=upper,
                    )
                    if breakout:
                        if st.hold_days > 0:
                            st.hold_state = {
                                "start_date": current_date,
                                "days_passed": 0,
                                "buffer_pct": st.buy_buffer_zone_pct,
                                "hold_days_required": st.hold_days,
                            }
                        else:
                            st.pending_order = PendingOrder(
                                order_type="buy",
                                signal_date=current_date,
                                buy_buffer_zone_pct=st.buy_buffer_zone_pct,
                                hold_days_used=0,
                            )

            elif st.position > 0:
                # 매도 로직
                sell_detected = _detect_sell_signal(
                    prev_close=prev_signal_row[COL_CLOSE],
                    close=signal_row[COL_CLOSE],
                    prev_lower_band=st.prev_lower_band,
                    lower_band=lower,
                )
                if sell_detected:
                    st.pending_order = PendingOrder(
                        order_type="sell",
                        signal_date=current_date,
                        buy_buffer_zone_pct=st.buy_buffer_zone_pct,
                        hold_days_used=0,
                    )

            # 다음 루프용 전일 밴드 저장
            st.prev_upper_band = upper
            st.prev_lower_band = lower

    # 7. 결과 조합
    tranche_results: list[SplitTrancheResult] = []
    for tranche in config.tranches:
        st = states[tranche.tranche_id]
        assert st.trades is not None
        assert st.equity_records is not None

        trades_df_t = pd.DataFrame(st.trades)
        equity_df_t = pd.DataFrame(st.equity_records)

        # summary 계산 (트랜치별)
        # initial_capital은 첫 매수 시 배분된 금액이 아닌, 총자본의 가중치 비율로 표시
        tranche_initial = config.total_capital * tranche.weight
        base_summary = calculate_summary(trades_df_t, equity_df_t, tranche_initial)
        summary_t: BufferStrategyResultDict = {
            **base_summary,
            "strategy": f"{config.strategy_name}_{tranche.tranche_id}",
            "ma_window": tranche.ma_window,
            "buy_buffer_zone_pct": bc.buy_buffer_zone_pct,
            "sell_buffer_zone_pct": bc.sell_buffer_zone_pct,
            "hold_days": bc.hold_days,
        }

        # 미청산 포지션 기록
        if st.position > 0 and st.entry_date is not None:
            summary_t["open_position"] = {
                "entry_date": str(st.entry_date),
                "entry_price": round(st.entry_price, 6),
                "shares": st.position,
            }

        tranche_results.append(
            SplitTrancheResult(
                tranche_id=tranche.tranche_id,
                config=tranche,
                trades_df=trades_df_t,
                equity_df=equity_df_t,
                summary=summary_t,
            )
        )

    # 8. 합산 에쿼티 구성
    combined_equity_df = _build_combined_equity(tranche_results, shared_cash, config.total_capital)
    combined_trades_df = _combine_trades(tranche_results)
    combined_summary = _calculate_combined_summary(
        combined_equity_df, combined_trades_df, config.total_capital, tranche_results
    )
    params_json = _build_params_json(config)

    logger.debug(f"분할 매수매도 완료: {config.strategy_name}, 합산 수익률={combined_summary['total_return_pct']:.2f}%")

    return SplitStrategyResult(
        strategy_name=config.strategy_name,
        display_name=config.display_name,
        combined_equity_df=combined_equity_df,
        combined_trades_df=combined_trades_df,
        combined_summary=combined_summary,
        per_tranche=tranche_results,
        config=config,
        params_json=params_json,
        signal_df=signal_df,
    )


def _build_combined_equity(
    tranche_results: list[SplitTrancheResult],
    final_cash: float,
    total_capital: float,
) -> pd.DataFrame:
    """공유 자본 방식의 합산 에쿼티 DataFrame을 구성한다.

    각 트랜치의 equity_records에서 날짜별 주식 평가액을 합산하고,
    공유 현금을 더하여 전체 에쿼티를 계산한다.

    Args:
        tranche_results: 트랜치별 백테스트 결과
        final_cash: 최종 공유 현금
        total_capital: 총 자본금

    Returns:
        pd.DataFrame: 합산 에쿼티 DataFrame
    """
    # 1. 트랜치별 equity merge
    combined: pd.DataFrame | None = None
    for tr in tranche_results:
        tid = tr.tranche_id
        eq = tr.equity_df[[COL_DATE, "equity", "position"]].copy()
        eq = eq.rename(columns={"equity": f"{tid}_equity", "position": f"{tid}_position"})

        if combined is None:
            combined = eq
        else:
            combined = pd.merge(combined, eq, on=COL_DATE, how="outer")

    assert combined is not None

    combined = combined.sort_values(COL_DATE).reset_index(drop=True)

    # NaN 채우기
    equity_cols = []
    position_cols = []
    for tr in tranche_results:
        tid = tr.tranche_id
        eq_col = f"{tid}_equity"
        pos_col = f"{tid}_position"
        equity_cols.append(eq_col)
        position_cols.append(pos_col)
        combined[eq_col] = combined[eq_col].fillna(0.0)
        combined[pos_col] = combined[pos_col].fillna(0).astype(int)

    # 2. 합산 equity (주식 평가액 합 + 현금)
    # 현금은 날짜별로 추적하지 않았으므로, 역산한다:
    # 총 에쿼티 = total_capital + 실현손익 누적 + 미실현손익
    # 간단한 방식: equity = cash + sum(tranche_equity)
    # cash는 매수/매도 시 변하므로, 거래 이벤트에서 역산
    stock_total = combined[equity_cols].sum(axis=1)

    # 현금 추적: 거래 이벤트별로 현금 변동을 재구성
    # 모든 거래를 시간순으로 정렬하여 날짜별 현금을 계산
    all_trades: list[dict[str, Any]] = []
    for tr in tranche_results:
        if not tr.trades_df.empty:
            for _, row in tr.trades_df.iterrows():
                # 매수 이벤트 (entry_date에 현금 감소)
                all_trades.append(
                    {
                        "date": row["entry_date"],
                        "cash_change": -(row["entry_price"] * row["shares"]),
                    }
                )
                # 매도 이벤트 (exit_date에 현금 증가)
                all_trades.append(
                    {
                        "date": row["exit_date"],
                        "cash_change": row["exit_price"] * row["shares"],
                    }
                )

    # 미청산 포지션의 매수도 반영
    for tr in tranche_results:
        open_pos = tr.summary.get("open_position")
        if open_pos is not None:
            all_trades.append(
                {
                    "date": open_pos["entry_date"],
                    "cash_change": -(open_pos["entry_price"] * open_pos["shares"]),
                }
            )

    # 날짜별 현금 계산
    cash_by_date: dict[object, float] = {}
    current_cash = total_capital
    if all_trades:
        trades_sorted = sorted(all_trades, key=lambda x: str(x["date"]))
        trade_idx = 0
        for _, row in combined.iterrows():
            d = row[COL_DATE]
            while trade_idx < len(trades_sorted) and str(trades_sorted[trade_idx]["date"]) <= str(d):
                current_cash += trades_sorted[trade_idx]["cash_change"]
                trade_idx += 1
            cash_by_date[d] = current_cash
    else:
        for _, row in combined.iterrows():
            cash_by_date[row[COL_DATE]] = total_capital

    combined["_cash"] = combined[COL_DATE].map(cash_by_date)
    combined["equity"] = combined["_cash"] + stock_total
    combined = combined.drop(columns=["_cash"])

    # 3. active_tranches
    combined["active_tranches"] = combined[position_cols].gt(0).sum(axis=1).astype(int)

    # 4. avg_entry_price
    avg_prices: list[float | None] = []
    for _, row in combined.iterrows():
        weighted_sum = 0.0
        total_shares = 0
        for tr in tranche_results:
            tid = tr.tranche_id
            pos = int(row[f"{tid}_position"])
            if pos > 0:
                open_pos = tr.summary.get("open_position")
                ep = _get_latest_entry_price(tr.trades_df, tr.equity_df, row[COL_DATE], open_position=open_pos)
                if ep is not None:
                    weighted_sum += ep * pos
                    total_shares += pos
        if total_shares > 0:
            avg_prices.append(weighted_sum / total_shares)
        else:
            avg_prices.append(None)

    combined["avg_entry_price"] = avg_prices

    # 5. 컬럼 순서 정리
    base_cols = [COL_DATE, "equity", "active_tranches", "avg_entry_price"]
    extra_cols = []
    for tr in tranche_results:
        extra_cols.append(f"{tr.tranche_id}_equity")
        extra_cols.append(f"{tr.tranche_id}_position")
    combined = combined[base_cols + extra_cols]

    return combined
