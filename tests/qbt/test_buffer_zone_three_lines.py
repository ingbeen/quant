"""
backtest/buffer_zone_three_lines 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 몫 하나의 실행: 민감도의 run_rule 과 같은 규칙이고, 몫끼리 독립이다
2. 첫날 보유: 둘째 날 시가에 사고 그 뒤는 같은 매도 규칙이다
3. 자본 곡선 합산: 세 몫의 평균이고 날짜가 어긋나면 멈춘다
4. 진입가 대비 · 고점 대비 손익: 손계산 값, 청산일 종가 제외, 보유 중 평가
5. 닷컴 칸: 구간 낙폭, 고점 날 보유 몫, 구간이 없으면 비어 있음
6. 측정 범위: 투자자 표, 고원 값
7. 결과 표: 행 수, 거래 수 일치, 합격 칸 없음

왜 중요한가요?
이 결과로 세 줄의 고원과 투자자별 성과를 판단한다. 몫이 서로 영향을 주거나 구간이 어긋나면
에러 없이 틀린 수익률이 나가고, 낙폭과 진입가 대비 손익을 혼동하면 번 거래를 잃은 거래로 읽는다.
"""

import math
from datetime import date, timedelta
from typing import cast

import pandas as pd
import pytest

from qbt.backtest.buffer_zone_sensitivity import (
    DISPLAY_CLOSED,
    DISPLAY_ENTRY_DATE,
    DISPLAY_EXIT_DATE,
    DISPLAY_LOSSES,
    DISPLAY_LOWEST,
    DISPLAY_PNL,
    DISPLAY_STATUS,
    DISPLAY_WINS,
    DISPLAY_WORST,
    STATUS_CLOSED,
    STATUS_OPEN,
    RuleParams,
    run_rule,
    slice_period,
)
from qbt.backtest.buffer_zone_three_lines import (
    CASES,
    CHECK_COST_CAP,
    CHECK_PRE_BUBBLE,
    DISPLAY_BH_DOTCOM,
    DISPLAY_CENTER,
    DISPLAY_DOTCOM,
    DISPLAY_EQUITY_DATE,
    DISPLAY_FINAL,
    DISPLAY_FIRST_BUY,
    DISPLAY_FROM_PEAK,
    DISPLAY_HELD_AT_PEAK,
    DISPLAY_METHOD,
    DISPLAY_SELL_LINE,
    INVESTOR_2004,
    INVESTOR_DOTCOM,
    METHOD_ONE,
    METHOD_THREE,
    PLATEAU_CENTERS,
    SELL_LINES,
    ThreeLinesCase,
    average_equity,
    evaluate_case,
    from_peak_pct,
    held_lines_on,
    line_widths,
    round_three_lines_csv,
    run_line,
    trade_row_stats,
    window_drawdown_pct,
)
from qbt.common_constants import NDX_DATA_PATH, QLD_SYNTHETIC_DATA_PATH, QQQ_DATA_PATH, TQQQ_SYNTHETIC_DATA_PATH

MA_COL = "ma_200"
FIRST_DAY = date(2024, 1, 1)


def _day(i: int) -> date:
    return FIRST_DAY + timedelta(days=i)


def _prices(closes: list[float], opens: list[float] | None = None) -> pd.DataFrame:
    """일별 시세 표. 시가를 주지 않으면 시가 · 고가 · 저가가 종가와 같다."""
    return pd.DataFrame(
        {
            "Date": [_day(i) for i in range(len(closes))],
            "Open": closes if opens is None else opens,
            "High": closes,
            "Low": closes,
            "Close": closes,
        }
    )


def _with_flat_ma(closes: list[float]) -> pd.DataFrame:
    """이평선이 100 으로 고정된 표 — 매도선 92.5 · 90 · 87.5 를 손으로 셀 수 있다."""
    return _prices(closes).assign(**{MA_COL: 100.0})


def _swinging_prices(rows: int = 900, first_day: date = FIRST_DAY) -> pd.DataFrame:
    """크게 오르내려 매수 · 손절이 여러 번 나오는 결정적 시세."""
    closes = [100.0 + 40.0 * math.sin(i / 35.0) for i in range(rows)]
    return _prices(closes).assign(Date=[first_day + timedelta(days=i) for i in range(rows)])


# 91 까지만 내려와 7.5% 몫만 팔리고, 다시 돌파해 그 몫만 재매수
# i=1 돌파, i=21 신호, i=22 매수 / i=26 하향돌파, i=46 손절선 92, i=47 손절 / i=48 돌파, i=68 신호, i=69 재매수
_ONLY_NARROW_LINE_SELLS = [104.0] + [106.0] * 25 + [92.0] * 21 + [91.0] + [106.0] * 23


class TestRunLine:
    def test_same_rule_as_sensitivity_run_rule(self) -> None:
        """
        목적: 한 몫은 민감도의 눌림 제거 규칙과 같다 — 두 경로가 갈라지면 세 줄과 한 줄을 비교할 수 없다

        Given: 합성 시세, 2배, 매도 기본폭 10%
        When: run_line 과 run_rule
        Then: 거래 표와 자본 곡선이 같고 거래가 실제로 있다
        """
        # Given
        signal_df, trade_df = slice_period(_swinging_prices(), [200], None, None)
        params = RuleParams(
            ma_window=200, buy_base_pct=0.05, sell_base_pct=0.10, month_days=21, wait_for_pullback=False
        )

        # When
        trades, equity, _ = run_line(signal_df, trade_df, 0.10, 2)
        expected_trades, expected_equity, _ = run_rule(signal_df, trade_df, params, 2)

        # Then
        assert len(trades) > 0
        pd.testing.assert_frame_equal(trades, expected_trades)
        pd.testing.assert_frame_equal(equity, expected_equity)

    def test_lines_are_independent(self) -> None:
        """
        목적: 한 몫이 팔려도 다른 몫은 그대로이고, 팔린 몫만 다시 산다

        Given: 종가가 91 까지만 내려간다 — 하단 92.5 만 뚫고 90 · 87.5 는 뚫지 못한다
        When: 매도 기본폭 7.5 · 10 · 12.5% 로 각각 실행
        Then: 7.5% 몫은 i=47 에 팔고 i=69 에 재매수, 나머지는 i=22 진입 그대로 보유 중
        """
        # Given
        df = _with_flat_ma(_ONLY_NARROW_LINE_SELLS)

        # When
        narrow_trades, _, narrow = run_line(df, df, 0.075, 1)
        middle_trades, _, middle = run_line(df, df, 0.10, 1)
        wide_trades, _, wide = run_line(df, df, 0.125, 1)

        # Then
        assert list(narrow_trades["exit_date"]) == [_day(47)]
        assert narrow.get("open_position", {}).get("entry_date") == str(_day(69))
        assert (len(middle_trades), len(wide_trades)) == (0, 0)
        assert middle.get("open_position", {}).get("entry_date") == str(_day(22))
        assert wide.get("open_position", {}).get("entry_date") == str(_day(22))


class TestHeldFromStart:
    # 하단 92.5 를 뚫어 i=5 시작, i=25 손절선 92, i=26 손절
    CLOSES = [100.0] * 5 + [92.0] * 21 + [91.0, 91.0]

    def test_buys_on_second_day_open(self) -> None:
        """
        목적: 돌파가 없어도 둘째 날 시가에 산다 — Buy & Hold 와 같은 시점이고, 버블 직전에 들어간 사람의 대조가 된다

        Given: 매수선을 넘지 않는 시세
        When: 첫날 보유 / 빈손 시작
        Then: 첫날 보유는 진입일이 둘째 날, 빈손은 거래 · 보유가 없다
        """
        # Given
        df = _with_flat_ma([100.0] * 5)

        # When
        _, _, held = run_line(df, df, 0.075, 1, held_from_start=True)
        empty_trades, _, empty = run_line(df, df, 0.075, 1)

        # Then
        assert held.get("open_position", {}).get("entry_date") == str(_day(1))
        assert len(empty_trades) == 0
        assert "open_position" not in empty

    def test_sell_rule_stays_the_same(self) -> None:
        """
        목적: 첫날 보유는 시작만 다르고 매도 규칙은 그대로다

        Given: 하단 92.5 를 뚫는 시세
        When: 첫날 보유로 실행
        Then: i=1 진입, i=26 에 손절선 92 아래 시가 91 로 판다
        """
        # Given
        df = _with_flat_ma(self.CLOSES)

        # When
        trades, _, _ = run_line(df, df, 0.075, 1, held_from_start=True)

        # Then
        assert list(trades["entry_date"]) == [_day(1)]
        assert list(trades["exit_date"]) == [_day(26)]
        assert trades["exit_price"].iloc[0] == pytest.approx(91.0 * (1 - 0.003), abs=0.01)


class TestAverageEquity:
    def test_mean_of_lines(self) -> None:
        """
        목적: 세 몫의 자산을 평균한다 — 각 몫이 같은 돈으로 시작하므로 3등분의 합과 같은 뜻이다

        Given: 자산이 다른 세 몫
        When: average_equity
        Then: 날짜별 평균이다
        """
        # Given
        days = [_day(0), _day(1)]
        lines = [
            pd.DataFrame({"Date": days, "equity": values}) for values in ([100.0, 130.0], [100.0, 100.0], [100.0, 70.0])
        ]

        # When
        actual = average_equity(lines)

        # Then
        assert list(actual["Date"]) == days
        assert list(actual["equity"]) == pytest.approx([100.0, 100.0], abs=1e-12)

    def test_mismatched_dates_raise(self) -> None:
        """
        목적: 날짜가 어긋나면 멈춘다 — 인덱스로 더하면 에러 없이 틀린 자산이 나온다

        Given: 날짜가 다른 두 몫
        When: average_equity
        Then: RuntimeError
        """
        # Given
        first = pd.DataFrame({"Date": [_day(0), _day(1)], "equity": [100.0, 100.0]})
        second = pd.DataFrame({"Date": [_day(0), _day(2)], "equity": [100.0, 100.0]})

        # When / Then
        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            average_equity([first, second])


class TestFromPeak:
    # 시가 ≠ 종가. i=1 진입이면 진입가 101 × 1.003 = 101.303
    TRADE_DF = _prices(
        [100.0, 102.0, 150.0, 110.0, 100.0, 300.0, 120.0, 130.0],
        opens=[100.0, 101.0, 99.0, 105.0, 100.0, 90.0, 118.0, 125.0],
    )

    def test_closed_trade_can_be_profit_below_peak(self) -> None:
        """
        목적: 고점보다 크게 떨어져 팔아도 진입가 대비로는 벌 수 있다 — 낙폭과 손익을 한 줄에서 구분한다

        Given: i=1 진입(101.303), i=4 청산, 진입가 대비 +10%, 보유 중 최고 종가 150
        When: from_peak_pct
        Then: 101.303 × 1.10 / 150 - 1 = -25.71%
        """
        # When
        actual = from_peak_pct(self.TRADE_DF, _day(1), _day(4), 10.0)

        # Then
        assert actual == pytest.approx(-25.7111, abs=0.001)

    def test_exit_day_close_is_not_counted(self) -> None:
        """
        목적: 청산일 종가는 보유 중이 아니다 — 판 뒤의 종가로 고점을 잡으면 실제보다 나쁘게 나온다

        Given: i=4 ~ 5 거래, 청산일 i=5 의 종가 300 이 가장 높다
        When: from_peak_pct
        Then: 고점은 300 이 아니라 100, 100.3 × 0.8 / 100 - 1 = -19.76%
        """
        # When
        actual = from_peak_pct(self.TRADE_DF, _day(4), _day(5), -20.0)

        # Then
        assert actual == pytest.approx(-19.76, abs=0.001)

    def test_open_trade_counts_to_the_last_close(self) -> None:
        """
        목적: 보유 중 거래는 마지막 종가까지가 보유 구간이다

        Given: i=6 진입(118.354), 마지막 종가 130 이 최고, 평가 손익 = 130 / 118.354 - 1
        When: from_peak_pct
        Then: 고점 = 마지막 종가라 0%
        """
        # Given
        pnl_pct = (130.0 / (118.0 * 1.003) - 1) * 100.0

        # When
        actual = from_peak_pct(self.TRADE_DF, _day(6), None, pnl_pct)

        # Then
        assert actual == pytest.approx(0.0, abs=1e-9)

    def test_no_held_close_raises(self) -> None:
        """
        목적: 보유 중 종가가 없는 거래는 있을 수 없다 — 조용히 넘기면 틀린 값이 나간다

        Given: 진입일과 청산일이 같은 거래
        When: from_peak_pct
        Then: RuntimeError
        """
        # When / Then
        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            from_peak_pct(self.TRADE_DF, _day(4), _day(4), 0.0)


class TestTradeRowStats:
    @staticmethod
    def _row(status: str, pnl: float, lowest: float) -> dict[str, object]:
        return {DISPLAY_STATUS: status, DISPLAY_PNL: pnl, DISPLAY_LOWEST: lowest}

    def test_closed_and_open_rows(self) -> None:
        """
        목적: 익절 · 손절 · 최악은 끝난 행만, 최저는 보유 중 행까지 본다 — 평가 손익을 익절로 세면 안 판 거래가 번 거래가 된다

        Given: +10% · -25% 끝난 행, 평가 -40% · 최저 -50% 인 보유 중 행
        When: trade_row_stats
        Then: 끝난 2 · 익절 1 · 손절 1 · 최악 -25%, 최저 -50%
        """
        # Given
        rows = [
            self._row(STATUS_CLOSED, 10.0, -5.0),
            self._row(STATUS_CLOSED, -25.0, -30.0),
            self._row(STATUS_OPEN, -40.0, -50.0),
        ]

        # When
        stats = trade_row_stats(rows)

        # Then
        assert (stats.closed, stats.wins, stats.losses) == (2, 1, 1)
        assert stats.worst_pnl_pct == pytest.approx(-25.0, abs=1e-12)
        assert stats.lowest_vs_entry_pct == pytest.approx(-50.0, abs=1e-12)

    def test_zero_pnl_is_loss(self) -> None:
        """
        목적: 손익 0 은 익절이 아니다 — 민감도 표와 같은 기준이다

        Given: 손익 0 인 끝난 행
        When: trade_row_stats
        Then: 익절 0 · 손절 1
        """
        # When
        stats = trade_row_stats([self._row(STATUS_CLOSED, 0.0, -1.0)])

        # Then
        assert (stats.wins, stats.losses) == (0, 1)

    def test_no_rows(self) -> None:
        """
        목적: 한 번도 사지 않으면 최악 · 최저는 비어 있다 — 0 으로 채우면 손익이 0 이었다는 뜻이 된다

        Given: 행 없음
        When: trade_row_stats
        Then: 끝난 0, 최악 None, 최저 None
        """
        # When
        stats = trade_row_stats([])

        # Then
        assert stats.closed == 0
        assert stats.worst_pnl_pct is None
        assert stats.lowest_vs_entry_pct is None


class TestDotcomCells:
    def test_window_drawdown(self) -> None:
        """
        목적: 구간 낙폭은 그 구간 안의 고점 대비다 — 구간 앞 고점은 보지 않는다

        Given: 구간 앞 고점 1000, 구간 안 100 → 200 → 50
        When: window_drawdown_pct
        Then: 200 → 50 = -75%
        """
        # Given
        days = [date(2000, 1, 3), date(2000, 3, 10), date(2000, 6, 1), date(2002, 10, 31), date(2002, 11, 1)]
        values = pd.Series([1000.0, 100.0, 200.0, 50.0, 10.0])

        # When
        actual = window_drawdown_pct(days, values)

        # Then
        assert actual == pytest.approx(-75.0, abs=1e-9)

    def test_window_drawdown_without_rows_is_none(self) -> None:
        """
        목적: 구간을 겪지 않은 투자자의 칸은 비어 있다 — 0 으로 채우면 낙폭이 없었다는 뜻이 된다

        Given: 2004 년부터의 자본
        When: window_drawdown_pct
        Then: None
        """
        # When / Then
        assert window_drawdown_pct([date(2004, 1, 2), date(2004, 1, 5)], pd.Series([100.0, 90.0])) is None

    def test_held_lines_on_peak_day(self) -> None:
        """
        목적: 고점 날 보유 몫을 센다 — 그날 산 몫은 들고 있고, 그날 판 몫은 들고 있지 않다

        Given: 그날 판 몫, 그날 산 몫, 그 뒤에 판 몫, 아직 보유 중인 몫, 그 뒤에 산 몫
        When: held_lines_on
        Then: 3
        """
        # Given
        peak = date(2000, 3, 10)
        periods: list[tuple[date, date | None]] = [
            (date(1990, 1, 2), peak),
            (peak, date(2001, 1, 2)),
            (date(1995, 1, 3), date(2000, 10, 9)),
            (date(1999, 1, 4), None),
            (date(2003, 1, 2), None),
        ]

        # When / Then
        assert held_lines_on(periods, peak) == 3


class TestScope:
    def test_cases(self) -> None:
        """
        목적: 투자자 · 시세 · 구간 · 시작 방식을 고정한다 (사용자 결정 2026-11-01, 정책 값이라 숫자로 고정)

        Given: CASES
        When: (투자자, 배수)별로 모은다
        Then: 사용자에게 보인 표와 같다
        """
        # When
        actual = {
            (c.investor, c.leverage): (c.data_path, c.synthetic, c.capped_cost, c.start, c.held_from_start)
            for c in CASES
        }

        # Then
        y2004 = date(2004, 1, 2)
        assert actual == {
            (INVESTOR_2004, 1): (QQQ_DATA_PATH, False, False, y2004, False),
            (INVESTOR_2004, 2): (QLD_SYNTHETIC_DATA_PATH, False, False, y2004, False),
            (INVESTOR_2004, 3): (TQQQ_SYNTHETIC_DATA_PATH, False, False, y2004, False),
            (INVESTOR_DOTCOM, 1): (NDX_DATA_PATH, False, False, None, False),
            (INVESTOR_DOTCOM, 2): (NDX_DATA_PATH, True, False, None, False),
            (INVESTOR_DOTCOM, 3): (NDX_DATA_PATH, True, False, None, False),
            (CHECK_COST_CAP, 2): (NDX_DATA_PATH, True, True, None, False),
            (CHECK_COST_CAP, 3): (NDX_DATA_PATH, True, True, None, False),
            (CHECK_PRE_BUBBLE, 1): (QQQ_DATA_PATH, False, False, None, True),
            (CHECK_PRE_BUBBLE, 2): (QLD_SYNTHETIC_DATA_PATH, False, False, None, True),
            (CHECK_PRE_BUBBLE, 3): (TQQQ_SYNTHETIC_DATA_PATH, False, False, None, True),
        }

    def test_sell_lines_and_centers(self) -> None:
        """
        목적: 세 몫의 매도선과 고원 값을 고정한다 — 가운데 10% 의 세 줄이 곧 사용자가 고른 규칙이다

        Given: SELL_LINES · PLATEAU_CENTERS
        When: line_widths
        Then: 7.5 · 10 · 12.5%, 가운데 6 ~ 15%, 소수 오차가 없다
        """
        # When / Then
        assert SELL_LINES == (0.075, 0.10, 0.125)
        assert PLATEAU_CENTERS == (0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15)
        assert line_widths(0.10) == SELL_LINES
        assert line_widths(0.06) == (0.035, 0.06, 0.085)


class TestEvaluateCase:
    PRICES = _swinging_prices(first_day=date(1999, 1, 1))
    MAIN = ThreeLinesCase(INVESTOR_DOTCOM, 1, QQQ_DATA_PATH)
    CHECK = ThreeLinesCase(CHECK_PRE_BUBBLE, 1, QQQ_DATA_PATH, held_from_start=True)

    def test_no_pass_column(self) -> None:
        """
        목적: 어느 표에도 합격 칸이 없다 (사용자 결정: 합격 점수를 두지 않는다)

        Given: 합성 시세
        When: evaluate_case
        Then: 표마다 행이 있고 열 이름에 「합격」이 없다
        """
        # When
        tables = evaluate_case(self.MAIN, self.PRICES)

        # Then
        columns = [*tables.investor_row, *tables.trades[0], *tables.plateau[0], *tables.equity.columns]
        assert not [column for column in columns if "합격" in column]

    def test_trade_rows_match_closed_count_and_lines(self) -> None:
        """
        목적: 매도 내역이 빠지지 않는다 — 끝난 행 수가 투자자 행의 거래 수와 같고, 세 매도선이 모두 나온다

        Given: 합성 시세
        When: evaluate_case
        Then: 끝난 행 수 = 끝난 거래 > 0, 매도선 7.5 · 10 · 12.5, 몫마다 손익과 고점 대비 칸이 있다
        """
        # When
        tables = evaluate_case(self.MAIN, self.PRICES)

        # Then
        closed = [row for row in tables.trades if row[DISPLAY_STATUS] == STATUS_CLOSED]
        assert len(closed) == tables.investor_row[DISPLAY_CLOSED]
        assert len(closed) > 0
        assert {row[DISPLAY_SELL_LINE] for row in tables.trades} == {7.5, 10.0, 12.5}
        for row in tables.trades:
            assert DISPLAY_PNL in row
            assert DISPLAY_FROM_PEAK in row

    def test_from_peak_column_uses_each_row_period(self) -> None:
        """
        목적: 고점 대비 칸은 그 행의 진입일 · 청산일 · 손익으로 계산한다 — 청산일을 빠뜨리면 판 뒤의 고점까지 봐 틀린 낙폭이 나간다

        Given: 파동마다 고점이 높아지는 시세 — 판 뒤의 고점이 보유 중 고점보다 높아 청산일을 빠뜨리면 값이 달라진다
        When: evaluate_case
        Then: 행마다 from_peak_pct 를 그 행의 값으로 부른 결과와 같고, 청산일을 뺀 값과는 다르며,
            투자자 행의 익절 · 손절 · 최악 · 최저가 거래 행 집계와 같다
        """
        # Given
        rising = self.PRICES.assign(
            **{
                col: [value + 0.2 * i for i, value in enumerate(self.PRICES[col])]
                for col in ("Open", "High", "Low", "Close")
            }
        )
        _, trade_df = slice_period(rising, [200], None, None)

        # When
        tables = evaluate_case(self.MAIN, rising)

        # Then
        closed = [row for row in tables.trades if row[DISPLAY_STATUS] == STATUS_CLOSED]
        assert closed
        for row in closed:
            without_exit = from_peak_pct(trade_df, row[DISPLAY_ENTRY_DATE], None, row[DISPLAY_PNL])
            assert row[DISPLAY_FROM_PEAK] != pytest.approx(without_exit, abs=1e-9)
        for row in tables.trades:
            expected = from_peak_pct(trade_df, row[DISPLAY_ENTRY_DATE], row[DISPLAY_EXIT_DATE], row[DISPLAY_PNL])
            assert row[DISPLAY_FROM_PEAK] == pytest.approx(expected, abs=1e-9)
        stats = trade_row_stats(tables.trades)
        investor_row = tables.investor_row
        assert (investor_row[DISPLAY_WINS], investor_row[DISPLAY_LOSSES]) == (stats.wins, stats.losses)
        assert investor_row[DISPLAY_WORST] == stats.worst_pnl_pct
        assert investor_row[DISPLAY_LOWEST] == stats.lowest_vs_entry_pct

    def test_sell_line_scales_with_leverage(self) -> None:
        """
        목적: 매도선은 기본폭 × 배수로 표시한다 — 화면의 몫 이름이 실제 쓰인 폭이다

        Given: 2배
        When: evaluate_case
        Then: 15 · 20 · 25
        """
        # When
        tables = evaluate_case(ThreeLinesCase(INVESTOR_DOTCOM, 2, QQQ_DATA_PATH), self.PRICES)

        # Then
        assert {row[DISPLAY_SELL_LINE] for row in tables.trades} == {15.0, 20.0, 25.0}

    def test_held_from_start_reaches_every_line(self) -> None:
        """
        목적: 첫날 보유 판은 세 몫 모두 둘째 날 시가에 산다 — 연결이 끊기면 「버블 직전 진입」이 빈손 시작으로 바뀌어 낙폭이 0% 로 나온다

        Given: 둘째 날에 돌파가 없는 합성 시세
        When: 첫날 보유 판과 빈손 판
        Then: 첫날 보유는 매도선 셋 모두 가장 이른 진입일이 둘째 날이고, 빈손은 그보다 늦다
        """
        # Given
        second_day = slice_period(self.PRICES, [200], None, None)[0]["Date"].iloc[1]

        # When
        held = evaluate_case(self.CHECK, self.PRICES)
        empty = evaluate_case(self.MAIN, self.PRICES)

        # Then
        for line in (7.5, 10.0, 12.5):
            entries = [row[DISPLAY_ENTRY_DATE] for row in held.trades if row[DISPLAY_SELL_LINE] == line]
            assert min(entries) == second_day
        assert empty.investor_row[DISPLAY_FIRST_BUY] > second_day

    def test_first_buy_is_earliest_entry(self) -> None:
        """
        목적: 첫 매수일은 세 몫 진입일의 가장 이른 날이다

        Given: 합성 시세
        When: evaluate_case
        Then: 거래 표의 가장 이른 진입일과 같다
        """
        # When
        tables = evaluate_case(self.MAIN, self.PRICES)

        # Then
        assert tables.investor_row[DISPLAY_FIRST_BUY] == min(row[DISPLAY_ENTRY_DATE] for row in tables.trades)

    def test_final_multiple_is_mean_of_lines(self) -> None:
        """
        목적: 최종 자산 배수는 세 몫 최종 자산 평균 ÷ 초기 자본이다

        Given: 합성 시세와 몫별 실행
        When: evaluate_case
        Then: 몫별 최종 자산의 평균 배수와 같다
        """
        # Given
        signal_df, trade_df = slice_period(self.PRICES, [200], None, None)
        finals = [run_line(signal_df, trade_df, width, 1)[2]["final_capital"] for width in SELL_LINES]

        # When
        tables = evaluate_case(self.MAIN, self.PRICES)

        # Then
        assert tables.investor_row[DISPLAY_FINAL] == pytest.approx(sum(finals) / 3 / 10_000_000.0, abs=1e-9)

    def test_dotcom_cells_filled_when_period_overlaps(self) -> None:
        """
        목적: 닷컴 구간을 겪으면 세 칸이 채워지고, 2004 년 시작이면 비어 있다

        Given: 1999 년부터의 시세와 2004 년부터의 시세
        When: evaluate_case
        Then: 앞은 낙폭 · 보유 몫이 있고, 뒤는 None
        """
        # Given
        later = _swinging_prices(first_day=date(2004, 1, 1))

        # When
        early_row = evaluate_case(self.MAIN, self.PRICES).investor_row
        later_row = evaluate_case(ThreeLinesCase(INVESTOR_2004, 1, QQQ_DATA_PATH), later).investor_row

        # Then
        assert early_row[DISPLAY_DOTCOM] is not None
        assert early_row[DISPLAY_BH_DOTCOM] is not None
        assert early_row[DISPLAY_HELD_AT_PEAK] is not None
        assert later_row[DISPLAY_DOTCOM] is None
        assert later_row[DISPLAY_BH_DOTCOM] is None
        assert later_row[DISPLAY_HELD_AT_PEAK] is None

    def test_plateau_and_equity_only_for_main_investors(self) -> None:
        """
        목적: 대조 판은 표에만 넣는다 — 화면이 복잡하다는 지적을 받아 고원 · 곡선은 본 답 두 투자자만이다

        Given: 본 답과 대조
        When: evaluate_case
        Then: 본 답은 가운데 10개 × 방식 2개와 일별 자산이 있고, 대조는 비어 있다
        """
        # When
        main = evaluate_case(self.MAIN, self.PRICES)
        check = evaluate_case(self.CHECK, self.PRICES)

        # Then
        assert len(main.plateau) == 20
        assert len(main.equity) > 0
        assert check.plateau == []
        assert check.equity.empty

    def test_plateau_center_ten_matches_rule(self) -> None:
        """
        목적: 고원의 가운데 10% 세 줄과 한 줄이 각각 투자자 행 · 매도 10% 실행과 같다 — 차트와 표가 어긋나지 않는다

        Given: 합성 시세
        When: evaluate_case
        Then: 세 줄 칸의 최종 값이 투자자 행 연복리와, 한 줄 칸이 run_line(0.10) 연복리와 같다
        """
        # Given
        signal_df, trade_df = slice_period(self.PRICES, [200], None, None)
        one_line = run_line(signal_df, trade_df, 0.10, 1)[2]

        # When
        tables = evaluate_case(self.MAIN, self.PRICES)

        # Then
        cells = {(row[DISPLAY_METHOD], row[DISPLAY_CENTER]): row["연복리(%)"] for row in tables.plateau}
        assert cells[(METHOD_THREE, 10.0)] == pytest.approx(tables.investor_row["연복리(%)"], abs=1e-9)
        assert cells[(METHOD_ONE, 10.0)] == pytest.approx(one_line["cagr"], abs=1e-9)

    def test_equity_multiples_start_at_one(self) -> None:
        """
        목적: 자산 곡선은 시작 1 배이고 끝은 투자자 행의 최종 배수다

        Given: 합성 시세
        When: evaluate_case
        Then: 첫 행 1배, 마지막 행 = 최종 자산 배수, 날짜 오름차순
        """
        # When
        tables = evaluate_case(self.MAIN, self.PRICES)

        # Then
        first = tables.equity.iloc[0]
        last = tables.equity.iloc[-1]
        assert first["세 줄 자산 배수"] == pytest.approx(1.0, abs=1e-9)
        assert last["세 줄 자산 배수"] == pytest.approx(tables.investor_row[DISPLAY_FINAL], abs=1e-9)
        assert tables.equity[DISPLAY_EQUITY_DATE].is_monotonic_increasing

    def test_exit_date_empty_only_for_open_rows(self) -> None:
        """
        목적: 청산일은 보유 중인 행만 비어 있다

        Given: 합성 시세
        When: evaluate_case
        Then: 끝난 행은 청산일이 있고 진입일보다 뒤다
        """
        # When
        tables = evaluate_case(self.MAIN, self.PRICES)

        # Then
        for row in tables.trades:
            if row[DISPLAY_STATUS] == STATUS_CLOSED:
                assert cast(date, row[DISPLAY_EXIT_DATE]) > cast(date, row[DISPLAY_ENTRY_DATE])
            else:
                assert row[DISPLAY_EXIT_DATE] is None


class TestRounding:
    def test_new_columns_are_rounded(self) -> None:
        """
        목적: 새 열도 저장 자릿수를 지킨다 — % 는 2자리, 배수는 4자리

        Given: 자릿수가 긴 값
        When: round_three_lines_csv
        Then: 그 자릿수로 반올림된다. 표에 없는 열은 건너뛴다
        """
        # Given
        df = pd.DataFrame({DISPLAY_FROM_PEAK: [-12.34567], DISPLAY_DOTCOM: [-1.23456], DISPLAY_FINAL: [1.234567]})

        # When
        actual = round_three_lines_csv(df).iloc[0]

        # Then
        assert actual[DISPLAY_FROM_PEAK] == pytest.approx(-12.35, abs=1e-9)
        assert actual[DISPLAY_DOTCOM] == pytest.approx(-1.23, abs=1e-9)
        assert actual[DISPLAY_FINAL] == pytest.approx(1.2346, abs=1e-9)
