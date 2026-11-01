"""
backtest/strategies/buffer_zone_v2 모듈과 엔진 장중 손절 테스트

이 파일은 무엇을 검증하나요?
1. 매수 대기: 돌파일을 1일째로 세고, 종가가 이평선에 닿으면 취소하고, 한달 뒤 처음 상단 아래인 날이 신호다
2. 손절선: 하향돌파 후 한달 동안 닿지 않으면 그 기간 장중 저가의 최저가 손절선이 되고, 종가가 닿으면 풀린다
3. run_backtest 의 장중 손절: 손절선 가격 체결 · 시가 갭 · 세운 날 미작동
4. 자산별 설정 표: 시세 · 배수 · 밴드

왜 중요한가요?
V2 는 체결 타이밍 규칙의 유일한 예외(장중 손절)를 가진 전략이고, 대기 상태가 길어 어느 날 무엇을 보느냐가
결과를 바꾼다. 달력 계산 없이 짧은 합성 표(month_days=3)로 상태 전이를 하루 단위로 고정한다.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest import runners
from qbt.backtest.engines.backtest_engine import run_backtest
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.backtest.strategies.buffer_zone_v2 import (
    BUFFER_ZONE_V2_MONTH_DAYS,
    CONFIGS,
    BufferZoneV2Config,
    BufferZoneV2Strategy,
)
from qbt.backtest.strategies.strategy_common import IntradayStopStrategy, SignalStrategy
from qbt.backtest.types import SingleBacktestResult, SummaryDict
from qbt.common_constants import (
    GLD_DATA_PATH,
    QLD_SYNTHETIC_DATA_PATH,
    QQQ_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)

MA_COL = "ma_200"
MA_VALUE = 100.0
BAND_PCT = 0.05  # 상단 105 · 하단 95


def _make_df(
    closes: list[float],
    *,
    lows: dict[int, float] | None = None,
    highs: dict[int, float] | None = None,
    opens: dict[int, float] | None = None,
) -> pd.DataFrame:
    """이평선이 100 으로 고정된 일별 표. 시가 · 고가 · 저가는 지정하지 않으면 종가와 같다."""
    n = len(closes)
    days = [date(2024, 1, 1) + timedelta(days=i) for i in range(n)]
    return pd.DataFrame(
        {
            "Date": days,
            "Open": [(opens or {}).get(i, closes[i]) for i in range(n)],
            "High": [(highs or {}).get(i, closes[i]) for i in range(n)],
            "Low": [(lows or {}).get(i, closes[i]) for i in range(n)],
            "Close": closes,
            MA_COL: [MA_VALUE] * n,
        }
    )


def _buy_signal_days(df: pd.DataFrame, month_days: int = 3) -> list[int]:
    strategy = BufferZoneV2Strategy(MA_COL, BAND_PCT, month_days)
    return [i for i in range(len(df)) if strategy.check_buy(df, i)]


def _stop_by_day(df: pd.DataFrame, month_days: int = 3) -> list[float | None]:
    strategy = BufferZoneV2Strategy(MA_COL, BAND_PCT, month_days)
    stops: list[float | None] = []
    for i in range(len(df)):
        strategy.check_sell(df, i)
        stops.append(strategy.stop_price())
    return stops


class TestBuySignal:
    """매수 대기 상태 전이 (month_days=3, 이평선 100, 상단 105)."""

    def test_signal_on_month_day_when_below_upper(self) -> None:
        """
        목적: 돌파일이 1일째이고, 3일째 종가가 상단 아래면 그날이 신호다

        Given: i=1 돌파(1일째), i=2 위(2일째), i=3 상단 아래(3일째)
        When: 날마다 check_buy
        Then: i=3 하나만 True
        """
        # Given
        df = _make_df([104.0, 106.0, 106.0, 104.0])

        # When
        signals = _buy_signal_days(df)

        # Then
        assert signals == [3]

    def test_waits_above_upper_until_first_close_below(self) -> None:
        """
        목적: 한달이 지나도 종가가 상단 위면 기다리고, 처음 아래로 온 날 한 번만 신호를 낸다

        Given: 3일째(i=3)와 그 뒤 종가가 상단 위, i=5 에 처음 아래, i=6 도 아래
        When: 날마다 check_buy
        Then: i=5 하나만 True
        """
        # Given
        df = _make_df([104.0, 106.0, 106.0, 106.0, 107.0, 104.5, 104.0])

        # When
        signals = _buy_signal_days(df)

        # Then
        assert signals == [5]

    def test_close_equal_to_upper_is_not_signal(self) -> None:
        """
        목적: 「상단 아래」는 엄격히 아래다 (경계)

        Given: 한달이 지난 i=3 종가가 상단과 같고, i=4 에 아래로 온다
        When: 날마다 check_buy
        Then: i=4 만 True
        """
        # Given
        df = _make_df([104.0, 106.0, 106.0, 105.0, 104.0])

        # When
        signals = _buy_signal_days(df)

        # Then
        assert signals == [4]

    def test_close_touch_cancels_and_next_breakout_counts_from_one(self) -> None:
        """
        목적: 한달 안에 종가가 이평선에 닿으면 취소되고, 다시 돌파한 날이 새 1일째다

        Given: i=1 돌파, i=2 종가 = 이평선(경계)으로 취소, i=4 재돌파, i=6 상단 아래
        When: 날마다 check_buy
        Then: 재돌파에서 3일째인 i=6 만 True
        """
        # Given
        df = _make_df([104.0, 106.0, 100.0, 103.0, 106.0, 106.0, 104.0])

        # When
        signals = _buy_signal_days(df)

        # Then
        assert signals == [6]

    def test_touch_on_month_day_cancels(self) -> None:
        """
        목적: 한달의 마지막 날(3일째)도 「한달 동안」에 든다 — 그날 닿으면 신호가 아니라 취소다

        Given: 3일째 종가가 이평선 아래
        When: 날마다 check_buy
        Then: 신호 없음
        """
        # Given
        df = _make_df([104.0, 106.0, 106.0, 99.0])

        # When
        signals = _buy_signal_days(df)

        # Then
        assert signals == []

    def test_intraday_low_touch_does_not_cancel(self) -> None:
        """
        목적: 닿음은 종가로만 본다 (사용자 결정 2026-11-01) — 저가만 이평선 아래로 내려간 날은 취소가 아니다

        Given: 2일째 저가 99, 종가 106
        When: 날마다 check_buy
        Then: 3일째 i=3 이 True
        """
        # Given
        df = _make_df([104.0, 106.0, 106.0, 104.0], lows={2: 99.0})

        # When
        signals = _buy_signal_days(df)

        # Then
        assert signals == [3]

    def test_close_back_in_band_keeps_count(self) -> None:
        """
        목적: 밴드 안으로 돌아와도 이평선에 닿지 않으면 세기를 멈추지 않는다 — 기존 버퍼존의 유지일과 다른 점

        Given: 2일째 종가가 상단 아래(이평선 위), 3일째도 아래
        When: 날마다 check_buy
        Then: 2일째는 한달 전이라 신호가 아니고, 3일째 i=3 이 True
        """
        # Given
        df = _make_df([104.0, 106.0, 103.0, 104.0])

        # When
        signals = _buy_signal_days(df)

        # Then
        assert signals == [3]

    def test_touch_after_month_does_not_cancel(self) -> None:
        """
        목적: 한달이 지난 뒤에는 닿아도 취소하지 않는다 — 「한달 동안」만 취소다

        Given: 3일째까지 위, i=4 에 종가가 이평선과 같다 (상단 아래이기도 하다)
        When: 날마다 check_buy
        Then: i=4 가 True
        """
        # Given
        df = _make_df([104.0, 106.0, 106.0, 106.0, 100.0])

        # When
        signals = _buy_signal_days(df)

        # Then
        assert signals == [4]

    def test_breakout_compares_previous_close_with_previous_band(self) -> None:
        """
        목적: 돌파 판정은 전일 종가와 전일 밴드를 비교한다 — 밴드는 이평선을 따라 매일 바뀐다

        Given: 전일 이평선 102(상단 107.1), 당일 이평선 100(상단 105), 종가 106 · 106.
               당일 밴드로 전일 종가를 재면 이미 위라 돌파가 아니다
        When: month_days=1 로 날마다 check_buy
        Then: i=1 이 돌파이고 i=2 (종가 104.9) 가 신호다
        """
        # Given
        df = _make_df([106.0, 106.0, 104.9])
        df[MA_COL] = [102.0, 100.0, 100.0]

        # When
        signals = _buy_signal_days(df, month_days=1)

        # Then
        assert signals == [2]

    def test_first_row_never_signals(self) -> None:
        """
        목적: 첫 행은 전일이 없어 돌파를 판정하지 않는다 (경계)

        Given: 첫 종가가 이미 상단 위
        When: i=0 에 check_buy · check_sell
        Then: 신호 없음, 손절선 없음
        """
        # Given
        df = _make_df([106.0, 106.0])
        strategy = BufferZoneV2Strategy(MA_COL, BAND_PCT, 3)

        # When
        buy = strategy.check_buy(df, 0)
        sell = strategy.check_sell(df, 0)

        # Then
        assert buy is False
        assert sell is False
        assert strategy.stop_price() is None


class TestStopLine:
    """하향돌파 뒤 손절선 상태 전이 (month_days=3, 이평선 100, 하단 95)."""

    def test_stop_is_lowest_intraday_low_of_the_month(self) -> None:
        """
        목적: 한달째 날 끝에 그 기간 «장중 저가»의 최저가 손절선이 되고, 그 전에는 없다

        Given: i=1 하향돌파(1일째), i=3 이 3일째. 저가 93 · 92 · 93.5, 종가는 모두 94
        When: 날마다 check_sell
        Then: i=2 까지 없음, i=3 에 92 (종가 최저 94 가 아니다)
        """
        # Given
        df = _make_df([96.0, 94.0, 94.0, 94.0], lows={1: 93.0, 2: 92.0, 3: 93.5})

        # When
        stops = _stop_by_day(df)

        # Then
        assert stops == [None, None, None, 92.0]

    def test_breakdown_day_low_counts(self) -> None:
        """
        목적: 돌파일의 저가도 「한달 기간」에 든다 (돌파일 포함)

        Given: 돌파일 저가 90 이 기간 최저
        When: 날마다 check_sell
        Then: 손절선 90
        """
        # Given
        df = _make_df([96.0, 94.0, 94.0, 94.0], lows={1: 90.0, 2: 92.0, 3: 93.0})

        # When
        stops = _stop_by_day(df)

        # Then
        assert stops[3] == 90.0

    def test_check_sell_is_always_false(self) -> None:
        """
        목적: 매도는 장중 손절로만 일어난다 — 하향돌파도, 손절선을 세운 날도 예약 매도가 아니다

        Given: 하향돌파 후 손절선이 서는 표
        When: 날마다 check_sell
        Then: 전부 False
        """
        # Given
        df = _make_df([96.0, 94.0, 94.0, 94.0, 93.0])
        strategy = BufferZoneV2Strategy(MA_COL, BAND_PCT, 3)

        # When
        results = [strategy.check_sell(df, i) for i in range(len(df))]

        # Then
        assert results == [False] * len(df)

    def test_close_touch_cancels_and_restart_uses_new_lows_only(self) -> None:
        """
        목적: 한달 안에 종가가 이평선에 닿으면 취소되고, 재돌파 뒤 손절선은 새 기간의 저가만 본다

        Given: i=1 돌파(저가 90), i=2 종가 = 이평선으로 취소, i=3 재돌파, i=5 가 새 3일째
        When: 날마다 check_sell
        Then: i=5 에 새 기간 최저 92 (취소된 기간의 90 이 아니다)
        """
        # Given
        df = _make_df([96.0, 94.0, 100.0, 94.0, 94.0, 94.0], lows={1: 90.0, 3: 93.0, 4: 92.0, 5: 93.0})

        # When
        stops = _stop_by_day(df)

        # Then
        assert stops == [None, None, None, None, None, 92.0]

    def test_intraday_high_touch_does_not_cancel(self) -> None:
        """
        목적: 닿음은 종가로만 본다 (사용자 결정 2026-11-01) — 고가만 이평선 위로 올라간 날은 취소가 아니다

        Given: 2일째 고가 101, 종가 94
        When: 날마다 check_sell
        Then: 3일째에 손절선이 선다
        """
        # Given
        df = _make_df([96.0, 94.0, 94.0, 94.0], highs={2: 101.0})

        # When
        stops = _stop_by_day(df)

        # Then
        assert stops[3] == 94.0

    def test_close_back_in_band_keeps_count(self) -> None:
        """
        목적: 하단 위로 돌아와도 이평선에 닿지 않으면 세기를 멈추지 않는다

        Given: 2일째 종가 97 (하단 위, 이평선 아래)
        When: 날마다 check_sell
        Then: 3일째 i=3 에 손절선이 선다
        """
        # Given
        df = _make_df([96.0, 94.0, 97.0, 94.0])

        # When
        stops = _stop_by_day(df)

        # Then
        assert stops == [None, None, None, 94.0]

    def test_close_touch_releases_stop_and_next_breakdown_restarts(self) -> None:
        """
        목적: 손절선이 선 뒤 종가가 이평선에 닿으면 풀리고, 다시 하향돌파해야 새로 센다 (사용자 결정 2026-11-01)

        Given: i=3 에 손절선 94, i=4 종가 = 이평선, i=5 재돌파(저가 91), i=7 이 새 3일째
        When: 날마다 check_sell
        Then: i=4 부터 풀리고 i=7 에 91
        """
        # Given
        df = _make_df([96.0, 94.0, 94.0, 94.0, 100.0, 94.0, 94.0, 94.0], lows={5: 91.0})

        # When
        stops = _stop_by_day(df)

        # Then
        assert stops == [None, None, None, 94.0, None, None, None, 91.0]

    def test_new_breakdown_while_stop_is_set_is_ignored(self) -> None:
        """
        목적: 손절선이 살아 있는 동안의 새 하향돌파는 손절선을 바꾸지 않는다 — 닿아야 풀린다

        Given: i=3 에 손절선 92, i=4 하단 위로 회복(이평선 아래), i=5 재돌파, 그 뒤 더 낮은 저가
        When: 날마다 check_sell
        Then: 끝까지 92
        """
        # Given
        df = _make_df([96.0, 94.0, 94.0, 94.0, 97.0, 94.0, 94.0, 94.0], lows={2: 92.0, 5: 93.0, 6: 93.0, 7: 93.0})

        # When
        stops = _stop_by_day(df)

        # Then
        assert stops[3:] == [92.0] * 5

    def test_check_buy_clears_sell_state(self) -> None:
        """
        목적: 포지션이 없어 check_buy 가 불리면 직전 보유의 손절선은 끝난 것이다

        Given: 손절선이 선 상태
        When: 같은 표에서 check_buy 를 부른다
        Then: 손절선이 없다
        """
        # Given
        df = _make_df([96.0, 94.0, 94.0, 94.0, 94.0])
        strategy = BufferZoneV2Strategy(MA_COL, BAND_PCT, 3)
        for i in range(4):
            strategy.check_sell(df, i)
        assert strategy.stop_price() == 94.0

        # When
        strategy.check_buy(df, 4)

        # Then
        assert strategy.stop_price() is None


class TestConstructor:
    @pytest.mark.parametrize(
        ("band_pct", "month_days", "message"),
        [
            (0.0, 3, "band_pct"),
            (1.0, 3, "band_pct"),
            (float("nan"), 3, "band_pct"),
            (0.05, 0, "month_days"),
        ],
    )
    def test_out_of_range_params_raise(self, band_pct: float, month_days: int, message: str) -> None:
        """
        목적: 범위 밖 파라미터로는 전략을 만들 수 없다

        Given: 하나만 범위 밖인 파라미터 (0 · 1 · NaN · 0일)
        When: 전략 생성
        Then: 그 파라미터 이름이 든 ValueError
        """
        with pytest.raises(ValueError, match=message):
            BufferZoneV2Strategy(MA_COL, band_pct, month_days)

    def test_protocols_and_buy_meta(self) -> None:
        """
        목적: 두 Protocol 을 만족하고, 거래 기록용 메타는 밴드와 한달 길이다

        Given: BufferZoneV2Strategy
        When: Protocol 확인과 get_buy_meta
        Then: 둘 다 참, 밴드 · 한달 길이
        """
        # Given
        strategy = BufferZoneV2Strategy(MA_COL, 0.15, 21)

        # When
        meta = strategy.get_buy_meta()

        # Then
        assert isinstance(strategy, SignalStrategy)
        assert isinstance(strategy, IntradayStopStrategy)
        assert meta == {"buy_buffer_pct": 0.15, "hold_days_used": 21}


def _stop_out_df(day6: tuple[float, float, float]) -> pd.DataFrame:
    """month_days=2 시나리오 — i=3 시가 104 에 사서 i=5 에 손절선 92 가 서고, i=6 이 시가 · 저가 · 종가를 받는다."""
    opening, low, close = day6
    return _make_df(
        [104.0, 106.0, 104.0, 104.0, 94.0, 94.0, close],
        opens={6: opening},
        lows={4: 93.0, 5: 92.0, 6: low},
        highs={6: max(opening, close)},
    )


def _run(df: pd.DataFrame, capital: float = 10_000.0) -> tuple[pd.DataFrame, pd.DataFrame, SummaryDict]:
    strategy = BufferZoneV2Strategy(MA_COL, BAND_PCT, 2)
    return run_backtest(strategy, df, df, capital, log_trades=False)


class TestIntradayStopInEngine:
    """run_backtest 의 장중 손절. 손계산: 매수 104 × 1.003 = 104.312, 95주, 비용 9,909.64, 현금 90.36."""

    def test_stop_fills_at_stop_price_with_slippage(self) -> None:
        """
        목적: 저가가 손절선 아래로 가면 그날 손절선 가격에 팔고, 슬리피지를 뺀다

        Given: i=6 시가 94, 저가 91, 손절선 92
        When: 백테스트
        Then: 진입 i=3 · 청산 i=6, 청산가 92 × 0.997 = 91.724, 그날 에쿼티 = 현금 8,804.14, 포지션 0
        """
        # Given
        df = _stop_out_df((94.0, 91.0, 93.0))

        # When
        trades_df, equity_df, _ = _run(df)

        # Then
        assert len(trades_df) == 1
        trade = trades_df.iloc[0]
        assert trade["entry_date"] == df["Date"].iloc[3]
        assert trade["exit_date"] == df["Date"].iloc[6]
        assert trade["entry_price"] == pytest.approx(104.312, abs=1e-9)
        assert trade["exit_price"] == pytest.approx(91.724, abs=1e-9)
        assert trade["shares"] == 95
        assert equity_df["equity"].iloc[6] == pytest.approx(8804.14, abs=0.01)
        assert equity_df["position"].iloc[6] == 0

    def test_gap_below_stop_fills_at_open(self) -> None:
        """
        목적: 시가가 이미 손절선 아래면 손절선 가격에 팔 수 없다 — 시가에 체결한다

        Given: i=6 시가 90, 저가 89, 손절선 92
        When: 백테스트
        Then: 청산가 90 × 0.997 = 89.73
        """
        # Given
        df = _stop_out_df((90.0, 89.0, 89.5))

        # When
        trades_df, _, _ = _run(df)

        # Then
        assert trades_df["exit_price"].iloc[0] == pytest.approx(89.73, abs=1e-9)

    def test_low_equal_to_stop_does_not_fill(self) -> None:
        """
        목적: 「하향돌파」는 엄격히 아래다 (경계)

        Given: i=6 저가 = 손절선 92
        When: 백테스트
        Then: 거래 없음, 보유 중
        """
        # Given
        df = _stop_out_df((94.0, 92.0, 93.0))

        # When
        trades_df, equity_df, summary = _run(df)

        # Then
        assert trades_df.empty
        assert equity_df["position"].iloc[-1] == 95
        assert "open_position" in summary

    def test_stop_does_not_work_on_the_day_it_is_set(self) -> None:
        """
        목적: 손절선은 다음 날부터 작동한다 — 세운 날의 저가는 이미 손절선을 정한 값이다

        Given: i=5 에 손절선이 서는 표에서 끝을 i=5 로 자른다
        When: 백테스트
        Then: 거래 없음
        """
        # Given
        df = _stop_out_df((94.0, 91.0, 93.0)).iloc[:6].reset_index(drop=True)

        # When
        trades_df, _, _ = _run(df)

        # Then
        assert trades_df.empty

    def test_buy_signal_after_stop_on_same_day(self) -> None:
        """
        목적: 손절한 날 종가는 포지션이 없는 날이라 매수 판정을 그대로 한다

        Given: i=6 저가로 손절 후 종가 106 이 상단 돌파(1일째), i=7 종가 104 가 2일째 신호, i=8 시가 체결
        When: 백테스트
        Then: i=8 에 다시 보유 (진입일이 i=8)
        """
        # Given
        base = _stop_out_df((94.0, 91.0, 106.0))
        extra = _make_df([104.0, 104.0]).assign(Date=[date(2024, 1, 8), date(2024, 1, 9)])
        df = pd.concat([base, extra], ignore_index=True)

        # When
        _, equity_df, summary = _run(df)

        # Then
        assert equity_df["position"].iloc[6] == 0
        assert equity_df["position"].iloc[8] > 0
        open_position = summary.get("open_position")
        assert open_position is not None
        assert open_position["entry_date"] == "2024-01-09"

    def test_stop_strategy_needs_low_column(self) -> None:
        """
        목적: 손절 전략인데 매매 시세에 저가가 없으면 행을 돌기 전에 멈춘다

        Given: Low 열이 없는 매매 표
        When: V2 전략으로 백테스트
        Then: Low 가 든 ValueError
        """
        # Given
        df = _stop_out_df((94.0, 91.0, 93.0))
        trade_df = df.drop(columns=["Low"])
        strategy = BufferZoneV2Strategy(MA_COL, BAND_PCT, 2)

        # When & Then
        with pytest.raises(ValueError, match="Low"):
            run_backtest(strategy, df, trade_df, 10_000.0, log_trades=False)

    def test_existing_strategy_runs_without_low_column(self) -> None:
        """
        목적: 손절이 없는 전략은 저가를 요구하지 않는다 — 기존 계약

        Given: Low 열이 없는 시그널 · 매매 표와 BufferZoneStrategy
        When: 백테스트
        Then: 예외 없이 끝난다
        """
        # Given
        df = _make_df([100.0, 104.0, 106.0, 106.0]).drop(columns=["Low", "High"])
        strategy = BufferZoneStrategy(MA_COL, 0.03, 0.05, 0)

        # When
        _, equity_df, _ = run_backtest(strategy, df, df, 10_000.0, log_trades=False)

        # Then
        assert len(equity_df) == 4


class TestConfigs:
    def test_band_and_data_by_asset(self) -> None:
        """
        목적: 자산별 시세와 밴드를 고정한다 — 밴드는 5% × 배수, 신호와 매매는 같은 시세

        Given: buffer_zone_v2.CONFIGS
        When: 이름별로 모은다
        Then: 요청의 표와 같다 (정책 값이라 숫자로 고정)
        """
        # Given / When
        actual = {c.strategy_name: (c.data_path, c.band_pct) for c in CONFIGS}

        # Then
        assert actual.keys() == {
            "buffer_zone_v2_qqq",
            "buffer_zone_v2_qld",
            "buffer_zone_v2_tqqq",
            "buffer_zone_v2_gld",
            "buffer_zone_v2_tlt",
        }
        assert actual["buffer_zone_v2_qqq"] == (QQQ_DATA_PATH, pytest.approx(0.05))
        assert actual["buffer_zone_v2_qld"] == (QLD_SYNTHETIC_DATA_PATH, pytest.approx(0.10))
        assert actual["buffer_zone_v2_tqqq"] == (TQQQ_SYNTHETIC_DATA_PATH, pytest.approx(0.15))
        assert actual["buffer_zone_v2_gld"] == (GLD_DATA_PATH, pytest.approx(0.05))
        assert actual["buffer_zone_v2_tlt"] == (TLT_DATA_PATH, pytest.approx(0.05))

    def test_month_is_21_trading_days(self) -> None:
        """
        목적: 한달은 21거래일이다 (사용자 결정 2026-11-01) — 정책 값이라 숫자로 고정

        Given: 상수
        When: 값을 읽는다
        Then: 21
        """
        assert BUFFER_ZONE_V2_MONTH_DAYS == 21


class TestRunner:
    def test_runner_returns_result_with_bands(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        목적: 러너가 이평선 워밍업 뒤 구간으로 돌고 대시보드가 읽을 이평선 · 밴드 열을 담는다

        Given: 종가가 일정한 260행 시세 (워밍업 199행)
        When: create_buffer_zone_v2_runner 로 실행
        Then: 신호 표 61행에 ma_200, 에쿼티에 상단 · 하단 밴드, 파라미터에 밴드 · 한달 길이
        """
        # Given
        n = 260
        df = pd.DataFrame(
            {
                "Date": [date(2020, 1, 1) + timedelta(days=i) for i in range(n)],
                "Open": [100.0] * n,
                "High": [101.0] * n,
                "Low": [99.0] * n,
                "Close": [100.0] * n,
                "Volume": [1000] * n,
            }
        )
        config = BufferZoneV2Config(
            strategy_name="buffer_zone_v2_test",
            display_name="버퍼존 V2 (테스트)",
            data_path=Path("dummy.csv"),
            result_dir=tmp_path / "v2",
            leverage=2,
        )
        monkeypatch.setattr(runners, "load_stock_data", lambda _path: df.copy())

        # When
        result = runners.create_buffer_zone_v2_runner(config)()

        # Then
        assert isinstance(result, SingleBacktestResult)
        assert result.signal_df["ma_200"].notna().all()
        assert len(result.signal_df) == n - 199
        assert result.equity_df["upper_band"].iloc[0] == pytest.approx(110.0, abs=1e-9)
        assert result.equity_df["lower_band"].iloc[0] == pytest.approx(90.0, abs=1e-9)
        assert result.params_json["band_pct"] == pytest.approx(0.10)
        assert result.params_json["month_days"] == 21
        assert result.data_info == {"trade_path": "dummy.csv"}
