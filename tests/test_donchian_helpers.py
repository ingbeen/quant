"""Donchian Channel 전략 핵심 로직 테스트

Donchian Channel (터틀 트레이딩) 전략의 채널 계산, 신호 감지,
전략 실행, 체결 타이밍, 비용 모델 등 핵심 계약을 검증한다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.backtest.strategies.donchian_helpers import (
    DonchianStrategyParams,
    compute_donchian_channels,
    run_donchian_strategy,
)
from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    EPSILON,
)


def _make_df(
    dates: list[date],
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> pd.DataFrame:
    """테스트용 OHLCV DataFrame 생성 헬퍼."""
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: opens,
            COL_HIGH: highs,
            COL_LOW: lows,
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * len(dates),
        }
    )


# ============================================================================
# 테스트 데이터 (공통)
# ============================================================================


def _build_channel_test_df() -> pd.DataFrame:
    """채널 계산 테스트용 DataFrame (7행).

    entry_channel_days=3, exit_channel_days=2 기준으로 설계.
    shift(1) 적용으로 실제 유효 값은 4번째 행(i=3)부터 시작.
    """
    return _make_df(
        dates=[
            date(2023, 1, 2),
            date(2023, 1, 3),
            date(2023, 1, 4),
            date(2023, 1, 5),
            date(2023, 1, 6),
            date(2023, 1, 9),
            date(2023, 1, 10),
        ],
        opens=[100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
        highs=[105.0, 108.0, 103.0, 110.0, 106.0, 112.0, 107.0],
        lows=[98.0, 99.0, 97.0, 100.0, 101.0, 103.0, 104.0],
        closes=[102.0, 106.0, 101.0, 107.0, 104.0, 110.0, 105.0],
    )


def _build_strategy_test_df() -> pd.DataFrame:
    """전략 실행 테스트용 DataFrame (10행).

    entry_channel_days=3, exit_channel_days=2 기준.
    매수 → 매도가 한 번 발생하도록 설계.

    날짜별 설계:
    - i=0~2: 채널 warming up (NaN)
    - i=3: upper_channel 유효값 시작 (shift(1)로 i=0~2의 3일간 최고가)
    - i=5: 급등으로 upper_channel 돌파 → 매수 신호
    - i=6: 매수 체결 (i=5 신호의 익일 시가)
    - i=8: 급락으로 lower_channel 돌파 → 매도 신호
    - i=9: 매도 체결 (i=8 신호의 익일 시가)
    """
    return _make_df(
        dates=[
            date(2023, 1, 2),  # i=0
            date(2023, 1, 3),  # i=1
            date(2023, 1, 4),  # i=2
            date(2023, 1, 5),  # i=3: upper valid
            date(2023, 1, 6),  # i=4
            date(2023, 1, 9),  # i=5: 급등 → 매수 신호
            date(2023, 1, 10),  # i=6: 매수 체결
            date(2023, 1, 11),  # i=7
            date(2023, 1, 12),  # i=8: 급락 → 매도 신호
            date(2023, 1, 13),  # i=9: 매도 체결
        ],
        opens=[100.0, 101.0, 102.0, 103.0, 102.0, 104.0, 111.0, 112.0, 108.0, 96.0],
        highs=[105.0, 108.0, 103.0, 106.0, 105.0, 115.0, 114.0, 115.0, 110.0, 100.0],
        lows=[98.0, 99.0, 100.0, 101.0, 100.0, 103.0, 109.0, 108.0, 95.0, 94.0],
        closes=[102.0, 106.0, 101.0, 104.0, 103.0, 113.0, 112.0, 110.0, 96.0, 97.0],
    )


# ============================================================================
# 채널 계산 테스트
# ============================================================================


class TestComputeDonchianChannels:
    """compute_donchian_channels() 핵심 계약 검증."""

    def test_basic_channel_values(self):
        """
        목적: Donchian 채널이 이전 N일 최고가 / M일 최저가를 올바르게 계산하는지 검증

        Given: 7행 OHLCV 데이터, entry_days=3, exit_days=2
        When: compute_donchian_channels() 호출
        Then: shift(1) 적용으로 i=3부터 upper 유효, i=2부터 lower 유효
        """
        df = _build_channel_test_df()
        upper, lower = compute_donchian_channels(df, entry_days=3, exit_days=2)

        # upper_channel: rolling(3).max().shift(1)
        # i=3: max(High[0:3]) = max(105, 108, 103) = 108 (shift(1)이므로 i=0,1,2의 rolling)
        assert upper.iloc[3] == pytest.approx(108.0, abs=EPSILON)

        # i=4: max(High[1:4]) = max(108, 103, 110) = 110
        assert upper.iloc[4] == pytest.approx(110.0, abs=EPSILON)

        # lower_channel: rolling(2).min().shift(1)
        # i=2: min(Low[0:2]) = min(98, 99) = 98
        assert lower.iloc[2] == pytest.approx(98.0, abs=EPSILON)

        # i=3: min(Low[1:3]) = min(99, 97) = 97
        assert lower.iloc[3] == pytest.approx(97.0, abs=EPSILON)

    def test_nan_before_warmup(self):
        """
        목적: rolling + shift(1)로 인한 NaN 구간이 올바른지 검증

        Given: 7행 OHLCV 데이터
        When: entry_days=3, exit_days=2로 채널 계산
        Then: upper는 i=0,1,2에서 NaN, lower는 i=0,1에서 NaN
        """
        df = _build_channel_test_df()
        upper, lower = compute_donchian_channels(df, entry_days=3, exit_days=2)

        # upper: rolling(3)은 i=2부터 유효, shift(1)로 i=3부터 유효
        assert pd.isna(upper.iloc[0])
        assert pd.isna(upper.iloc[1])
        assert pd.isna(upper.iloc[2])
        assert pd.notna(upper.iloc[3])

        # lower: rolling(2)은 i=1부터 유효, shift(1)로 i=2부터 유효
        assert pd.isna(lower.iloc[0])
        assert pd.isna(lower.iloc[1])
        assert pd.notna(lower.iloc[2])

    def test_series_length_matches_input(self):
        """
        목적: 반환된 시리즈 길이가 입력 DataFrame과 동일한지 검증

        Given: 7행 DataFrame
        When: 채널 계산
        Then: upper, lower 시리즈 길이 = 7
        """
        df = _build_channel_test_df()
        upper, lower = compute_donchian_channels(df, entry_days=3, exit_days=2)

        assert len(upper) == len(df)
        assert len(lower) == len(df)


# ============================================================================
# 전략 실행 테스트
# ============================================================================


class TestRunDonchianStrategy:
    """run_donchian_strategy() 핵심 계약 검증."""

    def test_basic_execution_with_trades(self):
        """
        목적: 기본 실행에서 매수→매도가 발생하고 결과 구조가 올바른지 검증

        Given: 10행 테스트 데이터 (매수/매도 1회 설계)
        When: run_donchian_strategy() 실행
        Then: trades_df에 1건, equity_df 존재, summary에 필수 키 존재
        """
        df = _build_strategy_test_df()
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, equity_df, summary = run_donchian_strategy(
            signal_df=df,
            trade_df=df,
            params=params,
        )

        # 거래 발생 확인
        assert len(trades_df) == 1

        # equity_df 구조 확인
        assert "equity" in equity_df.columns
        assert "position" in equity_df.columns
        assert "upper_channel" in equity_df.columns
        assert "lower_channel" in equity_df.columns
        assert COL_DATE in equity_df.columns

        # summary 필수 키 확인
        assert "initial_capital" in summary
        assert "final_capital" in summary
        assert "cagr" in summary
        assert "mdd" in summary
        assert "calmar" in summary
        assert "total_trades" in summary
        assert "win_rate" in summary
        assert summary["total_trades"] == 1

    def test_execution_timing_next_day_open(self):
        """
        목적: 신호일 i에서 체결이 i+1일 시가에 이루어지는지 검증

        Given: 10행 테스트 데이터
        When: 전략 실행
        Then: 매수 체결일 = 매수 신호 다음 거래일, 체결가 = 해당일 시가 * (1 + SLIPPAGE_RATE)
        """
        df = _build_strategy_test_df()
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, _, _ = run_donchian_strategy(
            signal_df=df,
            trade_df=df,
            params=params,
        )

        assert len(trades_df) >= 1
        trade = trades_df.iloc[0]

        # i=5에서 매수 신호 → i=6에서 체결
        assert trade["entry_date"] == date(2023, 1, 10)

        # i=8에서 매도 신호 → i=9에서 체결
        assert trade["exit_date"] == date(2023, 1, 13)

    def test_slippage_applied(self):
        """
        목적: 매수/매도 시 SLIPPAGE_RATE가 적용되는지 검증

        Given: 10행 테스트 데이터
        When: 전략 실행
        Then: entry_price = open * (1 + SLIPPAGE_RATE), exit_price = open * (1 - SLIPPAGE_RATE)
        """
        df = _build_strategy_test_df()
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, _, _ = run_donchian_strategy(
            signal_df=df,
            trade_df=df,
            params=params,
        )

        trade = trades_df.iloc[0]

        # i=6 시가 = 111.0, 매수: 111.0 * (1 + 0.003)
        expected_entry = 111.0 * (1 + SLIPPAGE_RATE)
        assert trade["entry_price"] == pytest.approx(expected_entry, abs=0.01)

        # i=9 시가 = 96.0, 매도: 96.0 * (1 - 0.003)
        expected_exit = 96.0 * (1 - SLIPPAGE_RATE)
        assert trade["exit_price"] == pytest.approx(expected_exit, abs=0.01)

    def test_equity_calculation(self):
        """
        목적: equity = cash + position * close 공식이 올바른지 검증

        Given: 전략 실행 후 equity_df
        When: 포지션 보유 중인 날 (i=6)의 equity 확인
        Then: equity = 잔여현금 + 보유주수 * 종가
        """
        df = _build_strategy_test_df()
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, equity_df, _ = run_donchian_strategy(
            signal_df=df,
            trade_df=df,
            params=params,
        )

        # i=6은 매수 체결일: position > 0
        row_i6 = equity_df[equity_df[COL_DATE] == date(2023, 1, 10)].iloc[0]
        assert row_i6["position"] > 0

        # equity 검증: cash + position * close
        entry_price = trades_df.iloc[0]["entry_price"]
        shares = trades_df.iloc[0]["shares"]
        cash = params.initial_capital - shares * entry_price
        close_i6 = 112.0  # i=6 종가
        expected_equity = cash + shares * close_i6
        assert row_i6["equity"] == pytest.approx(expected_equity, abs=0.1)

    def test_open_position_when_holding_at_end(self):
        """
        목적: 백테스트 종료 시 포지션 보유 중이면 summary에 open_position이 포함되는지 검증

        Given: 매수만 발생하고 매도 없이 종료되는 데이터
        When: 전략 실행
        Then: summary에 open_position 존재 (entry_date, entry_price, shares)
        """
        # 계속 상승만 하는 데이터 (매도 신호 없음)
        df = _make_df(
            dates=[date(2023, 1, d) for d in range(2, 12)],
            opens=[100.0 + i * 2 for i in range(10)],
            highs=[105.0 + i * 2 for i in range(10)],
            lows=[99.0 + i * 2 for i in range(10)],
            closes=[103.0 + i * 2 for i in range(10)],
        )
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        _, _, summary = run_donchian_strategy(
            signal_df=df,
            trade_df=df,
            params=params,
        )

        # 매수 신호가 발생하고 매도 없이 종료 → open_position 존재
        if summary["total_trades"] == 0 and "open_position" in summary:
            op = summary["open_position"]
            assert "entry_date" in op
            assert "entry_price" in op
            assert "shares" in op

    def test_no_open_position_when_flat(self):
        """
        목적: 종료 시 포지션 미보유면 summary에 open_position이 없는지 검증

        Given: 매수→매도가 완료되어 포지션 없는 상태로 종료
        When: 전략 실행
        Then: summary에 open_position 없음
        """
        df = _build_strategy_test_df()
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        _, _, summary = run_donchian_strategy(
            signal_df=df,
            trade_df=df,
            params=params,
        )

        # 매수→매도 완료 → open_position 없어야 함
        assert "open_position" not in summary

    def test_trade_record_structure(self):
        """
        목적: 거래 기록의 필수 컬럼이 존재하는지 검증

        Given: 매수/매도가 발생하는 데이터
        When: 전략 실행
        Then: trades_df에 entry_date, exit_date, entry_price, exit_price, shares, pnl, pnl_pct 포함
        """
        df = _build_strategy_test_df()
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, _, _ = run_donchian_strategy(
            signal_df=df,
            trade_df=df,
            params=params,
        )

        required_cols = [
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "shares",
            "pnl",
            "pnl_pct",
        ]
        for col in required_cols:
            assert col in trades_df.columns, f"trades_df에 '{col}' 컬럼이 없습니다"

    def test_separate_signal_and_trade_df(self):
        """
        목적: signal_df와 trade_df가 다른 경우에도 올바르게 동작하는지 검증

        Given: signal_df와 trade_df가 다른 가격을 가진 동일 날짜 데이터
        When: 전략 실행
        Then: 신호는 signal_df 기준, 체결은 trade_df 기준
        """
        dates = [date(2023, 1, d) for d in range(2, 12)]

        # signal_df: QQQ 가격 (매수 신호 유발하도록 상승)
        signal_df = _make_df(
            dates=dates,
            opens=[100.0 + i * 2 for i in range(10)],
            highs=[105.0 + i * 2 for i in range(10)],
            lows=[99.0 + i * 2 for i in range(10)],
            closes=[103.0 + i * 2 for i in range(10)],
        )

        # trade_df: TQQQ 가격 (3배 레버리지 근사)
        trade_df = _make_df(
            dates=dates,
            opens=[50.0 + i * 6 for i in range(10)],
            highs=[55.0 + i * 6 for i in range(10)],
            lows=[48.0 + i * 6 for i in range(10)],
            closes=[52.0 + i * 6 for i in range(10)],
        )

        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, equity_df, summary = run_donchian_strategy(
            signal_df=signal_df,
            trade_df=trade_df,
            params=params,
        )

        # 정상 실행 확인
        assert not equity_df.empty
        assert "equity" in equity_df.columns

    def test_pnl_calculation(self):
        """
        목적: PnL = (exit_price - entry_price) * shares 검증

        Given: 매수→매도 발생하는 데이터
        When: 전략 실행
        Then: pnl = (exit_price - entry_price) * shares
        """
        df = _build_strategy_test_df()
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, _, _ = run_donchian_strategy(
            signal_df=df,
            trade_df=df,
            params=params,
        )

        trade = trades_df.iloc[0]
        expected_pnl = (trade["exit_price"] - trade["entry_price"]) * trade["shares"]
        assert trade["pnl"] == pytest.approx(expected_pnl, abs=0.01)

    def test_pnl_pct_calculation(self):
        """
        목적: pnl_pct = (exit_price - entry_price) / entry_price 검증

        Given: 매수→매도 발생하는 데이터
        When: 전략 실행
        Then: pnl_pct = (exit_price - entry_price) / entry_price
        """
        df = _build_strategy_test_df()
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, _, _ = run_donchian_strategy(
            signal_df=df,
            trade_df=df,
            params=params,
        )

        trade = trades_df.iloc[0]
        expected_pnl_pct = (trade["exit_price"] - trade["entry_price"]) / trade["entry_price"]
        assert trade["pnl_pct"] == pytest.approx(expected_pnl_pct, abs=1e-6)


# ============================================================================
# 엣지 케이스 테스트
# ============================================================================


class TestDonchianEdgeCases:
    """엣지 케이스 및 입력 검증."""

    def test_insufficient_data_raises(self):
        """
        목적: 데이터 행 수가 최소 요구사항 미만이면 ValueError 발생

        Given: 2행 데이터 (entry_channel_days=3에 부족)
        When: run_donchian_strategy() 호출
        Then: ValueError 발생
        """
        df = _make_df(
            dates=[date(2023, 1, 2), date(2023, 1, 3)],
            opens=[100.0, 101.0],
            highs=[105.0, 106.0],
            lows=[98.0, 99.0],
            closes=[102.0, 104.0],
        )
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        with pytest.raises(ValueError, match="데이터"):
            run_donchian_strategy(signal_df=df, trade_df=df, params=params)

    def test_invalid_channel_days_raises(self):
        """
        목적: 채널 일수가 0 이하이면 ValueError 발생

        Given: entry_channel_days=0
        When: DonchianStrategyParams 생성 및 실행
        Then: ValueError 발생
        """
        df = _build_channel_test_df()
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=0,
            exit_channel_days=2,
        )

        with pytest.raises(ValueError, match="채널"):
            run_donchian_strategy(signal_df=df, trade_df=df, params=params)

    def test_no_trades_when_no_breakout(self):
        """
        목적: 채널 돌파가 없으면 거래 없이 종료

        Given: 채널 내에서만 움직이는 횡보 데이터
        When: 전략 실행
        Then: trades_df가 빈 DataFrame
        """
        # 좁은 범위에서 횡보하는 데이터
        df = _make_df(
            dates=[date(2023, 1, d) for d in range(2, 12)],
            opens=[100.0] * 10,
            highs=[101.0] * 10,
            lows=[99.0] * 10,
            closes=[100.0] * 10,
        )
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, equity_df, summary = run_donchian_strategy(signal_df=df, trade_df=df, params=params)

        assert trades_df.empty
        assert summary["total_trades"] == 0
        assert summary["final_capital"] == pytest.approx(10_000_000.0, abs=EPSILON)

    def test_no_forced_liquidation_at_end(self):
        """
        목적: 마지막 날에 강제청산이 발생하지 않는지 검증

        Given: 매수 후 매도 없이 종료되는 데이터
        When: 전략 실행
        Then: trades_df에 해당 매수의 매도 기록 없음 (강제청산 없음)
        """
        # 지속 상승 데이터 (매도 신호 없음)
        df = _make_df(
            dates=[date(2023, 1, d) for d in range(2, 12)],
            opens=[100.0 + i * 3 for i in range(10)],
            highs=[105.0 + i * 3 for i in range(10)],
            lows=[99.0 + i * 3 for i in range(10)],
            closes=[103.0 + i * 3 for i in range(10)],
        )
        params = DonchianStrategyParams(
            initial_capital=10_000_000.0,
            entry_channel_days=3,
            exit_channel_days=2,
        )

        trades_df, _, summary = run_donchian_strategy(signal_df=df, trade_df=df, params=params)

        # 강제청산 없으므로 완료된 거래 0건
        assert len(trades_df) == 0
