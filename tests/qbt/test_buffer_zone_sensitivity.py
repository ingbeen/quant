"""
backtest/buffer_zone_sensitivity 모듈 테스트

이 파일은 무엇을 검증하나요?
1. 구간 자르기: 이평선은 자르기 전 시세로 계산하고 시작 · 끝을 포함하며, 이평선 실험은 값마다 같은 기간이다
2. 칸 하나 실행: 폭은 기본폭 × 배수, Buy & Hold 는 같은 구간
3. 진입가 대비 손익: 끝난 거래 · 보유 중 · 거래 없음
4. 측정 범위: 데이터 · 실험 · 규칙 조합 표
5. 결과 표: 칸 수, 같은 구간 대비 차이, 거래 목록과 거래 수의 일치, 합격 칸 없음

왜 중요한가요?
이 결과로 과최적화인지 판단한다. 구간이 어긋나면 Buy & Hold 와의 차이가 에러 없이 틀리고,
안 본 구간에 본 구간이 섞이면 그 구분의 뜻이 사라진다.
"""

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from qbt.backtest.buffer_zone_sensitivity import (
    DATASETS,
    DISPLAY_BH_CAGR,
    DISPLAY_BH_MDD,
    DISPLAY_CAGR,
    DISPLAY_CAGR_DIFF,
    DISPLAY_CLOSED,
    DISPLAY_DATASET,
    DISPLAY_ENTRY_DATE,
    DISPLAY_EXIT_DATE,
    DISPLAY_EXPERIMENT,
    DISPLAY_LOWEST,
    DISPLAY_MDD,
    DISPLAY_MDD_DIFF,
    DISPLAY_PNL,
    DISPLAY_START,
    DISPLAY_STATUS,
    DISPLAY_VALUE,
    EXPERIMENT_BUY,
    EXPERIMENT_MA,
    EXPERIMENT_MONTH,
    EXPERIMENT_SELL,
    GROUP_FULL,
    GROUP_SEEN,
    GROUP_UNSEEN,
    MA_WINDOW_VALUES,
    RULE_COMBOS,
    STATUS_OPEN,
    RuleParams,
    SensitivityDataset,
    build_cases,
    entry_stats,
    evaluate_dataset,
    held_days_pct,
    run_buy_and_hold,
    run_rule,
    slice_period,
    trade_rows,
)
from qbt.backtest.constants import SLIPPAGE_RATE
from qbt.backtest.types import SummaryDict
from qbt.common_constants import (
    GLD_DATA_PATH,
    GSPC_DATA_PATH,
    IXIC_DATA_PATH,
    NDX_DATA_PATH,
    QLD_SYNTHETIC_DATA_PATH,
    QQQ_DATA_PATH,
    SPY_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)

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
    """이평선이 100 으로 고정된 표 — 폭이 어느 가격을 가리키는지 손으로 셀 수 있다."""
    return _prices(closes).assign(**{MA_COL: 100.0})


def _params(buy: float = 0.05, sell: float = 0.05, month: int = 2) -> RuleParams:
    return RuleParams(ma_window=200, buy_base_pct=buy, sell_base_pct=sell, month_days=month, wait_for_pullback=False)


class TestSlicePeriod:
    def test_moving_average_uses_prices_before_start(self) -> None:
        """
        목적: 이평선은 자르기 전 시세로 계산한다 — 자른 뒤 계산하면 앞부분이 비어 시작일이 밀린다

        Given: 종가 1 ~ 10, 3일 이평선, 여섯째 날부터
        When: slice_period
        Then: 첫 행은 여섯째 날이고 이평선은 앞 이틀을 포함한 (4 + 5 + 6) / 3 = 5
        """
        # Given
        df = _prices([float(i) for i in range(1, 11)])

        # When
        signal_df, trade_df = slice_period(df, [3], _day(5), None)

        # Then
        assert signal_df.iloc[0]["Date"] == _day(5)
        assert signal_df.iloc[0]["ma_3"] == pytest.approx(5.0, abs=1e-12)
        assert list(signal_df["Date"]) == list(trade_df["Date"])

    def test_start_and_end_are_inclusive(self) -> None:
        """
        목적: 시작일과 끝날을 모두 포함한다 — 안 본 구간의 끝날 다음부터가 본 구간이다

        Given: 종가 10행, 2일 이평선, 셋째 ~ 여섯째 날
        When: slice_period
        Then: 4행이고 양 끝이 그 날짜다
        """
        # Given
        df = _prices([float(i) for i in range(1, 11)])

        # When
        signal_df, _ = slice_period(df, [2], _day(2), _day(5))

        # Then
        assert list(signal_df["Date"]) == [_day(2), _day(3), _day(4), _day(5)]

    def test_no_start_begins_on_first_valid_day_of_longest_window(self) -> None:
        """
        목적: 시작일이 없으면 가장 긴 이평선이 계산되는 첫날부터다 — 이평선 실험의 값들이 같은 기간이 된다

        Given: 종가 10행, 2 · 4일 이평선
        When: slice_period
        Then: 넷째 날부터이고 두 이평선 모두 비어 있지 않다
        """
        # Given
        df = _prices([float(i) for i in range(1, 11)])

        # When
        signal_df, _ = slice_period(df, [2, 4], None, None)

        # Then
        assert signal_df.iloc[0]["Date"] == _day(3)
        assert signal_df[["ma_2", "ma_4"]].notna().all().all()

    def test_input_is_not_modified(self) -> None:
        """
        목적: 원본 시세 표를 바꾸지 않는다

        Given: 시세 표
        When: slice_period
        Then: 이평선 열이 원본에 생기지 않는다
        """
        # Given
        df = _prices([float(i) for i in range(1, 11)])
        columns = list(df.columns)

        # When
        slice_period(df, [3], None, None)

        # Then
        assert list(df.columns) == columns


class TestRunRule:
    def test_buy_band_widens_with_leverage(self) -> None:
        """
        목적: 매수 폭은 기본폭 × 배수다

        Given: 이평선 100, 종가 106 — 1배 상단 105 는 뚫고 2배 상단 110 은 못 뚫는다
        When: 배수 1 과 2 로 실행
        Then: 1배만 보유 중이다
        """
        # Given
        df = _with_flat_ma([104.0, 106.0, 106.0, 106.0, 106.0])

        # When
        _, _, one = run_rule(df, df, _params(), leverage=1)
        _, _, two = run_rule(df, df, _params(), leverage=2)

        # Then
        assert "open_position" in one
        assert "open_position" not in two

    def test_sell_band_widens_with_leverage_and_base(self) -> None:
        """
        목적: 매도 폭도 기본폭 × 배수다

        Given: 94 는 95 만 뚫는다. 하단 95 면 i=5 에 손절선 94 가 서고 i=7 에 판다.
            기본폭 10% 이거나 기본폭 5% × 2배면 하단이 90 이라 팔지 않는다
        When: 세 경우로 실행 (2배는 매수 기본폭 2.5% 로 상단을 105 에 맞춘다)
        Then: 끝난 거래가 1 · 0 · 0건
        """
        # Given
        df = _with_flat_ma([104.0, 106.0, 106.0, 106.0, 94.0, 94.0, 94.0, 80.0])

        # When
        narrow, _, _ = run_rule(df, df, _params(), leverage=1)
        wide_base, _, _ = run_rule(df, df, _params(sell=0.10), leverage=1)
        wide_leverage, _, _ = run_rule(df, df, _params(buy=0.025), leverage=2)

        # Then
        assert (len(narrow), len(wide_base), len(wide_leverage)) == (1, 0, 0)

    def test_buy_and_hold_buys_second_day_open_of_same_period(self) -> None:
        """
        목적: 비교 대상 Buy & Hold 는 넘겨받은 구간 안에서 둘째 날 시가에 산다

        Given: 시세를 잘라 만든 표
        When: run_buy_and_hold
        Then: 시작일이 그 표의 첫날이고 진입일이 둘째 날이다
        """
        # Given
        df = _prices([float(i) for i in range(1, 11)])
        signal_df, trade_df = slice_period(df, [2], _day(4), None)

        # When
        summary = run_buy_and_hold(signal_df, trade_df)

        # Then
        open_position = summary.get("open_position")
        assert summary["start_date"] == str(_day(4))
        assert open_position is not None
        assert open_position["entry_date"] == str(_day(5))


class TestHeldDays:
    def test_share_of_days_holding_shares(self) -> None:
        """
        목적: 보유 날 비율은 포지션이 있는 날의 비율이다

        Given: 네 날 중 두 날 보유
        When: held_days_pct
        Then: 50%
        """
        # Given
        equity_df = pd.DataFrame({"position": [0, 0, 10, 10]})

        # When / Then
        assert held_days_pct(equity_df) == pytest.approx(50.0, abs=1e-12)


def _trades(rows: list[tuple[int, int, float]]) -> pd.DataFrame:
    """(진입 행, 청산 행, 손익 비율) 목록으로 만든 거래 표."""
    return pd.DataFrame(
        {
            "entry_date": [_day(entry) for entry, _, _ in rows],
            "exit_date": [_day(exit_) for _, exit_, _ in rows],
            "pnl_pct": [pnl for _, _, pnl in rows],
        },
        columns=["entry_date", "exit_date", "pnl_pct"],
    )


def _summary(open_entry: int | None = None) -> SummaryDict:
    summary = SummaryDict(
        initial_capital=10_000.0,
        final_capital=10_000.0,
        total_return=0.0,
        total_return_pct=0.0,
        cagr=0.0,
        mdd=0.0,
        calmar=0.0,
        total_trades=0,
        winning_trades=0,
        losing_trades=0,
        win_rate=0.0,
        start_date=str(FIRST_DAY),
        end_date=str(FIRST_DAY),
    )
    if open_entry is not None:
        summary["open_position"] = {"entry_date": str(_day(open_entry)), "entry_price": 0.0, "shares": 1}
    return summary


class TestEntryStats:
    # 진입가는 시가 100 × 1.003 = 100.3
    TRADE_DF = _prices([100.0, 100.0, 90.0, 110.0, 100.0, 80.0, 120.0, 130.0], opens=[100.0] * 8)

    def test_closed_and_open_trades(self) -> None:
        """
        목적: 끝난 거래의 익절 · 손절 · 최악을 세고, 최저는 보유 중인 거래까지 본다

        Given: +10% 거래(i=1 ~ 3, 보유 중 최저 종가 90), -25% 거래(i=4 ~ 5, 보유 중 종가 100), 보유 중 거래(최저 120)
        When: entry_stats
        Then: 끝난 2 · 익절 1 · 손절 1 · 최악 -25%, 최저는 90 / 100.3 - 1 = -10.27%
        """
        # Given
        trades_df = _trades([(1, 3, 0.10), (4, 5, -0.25)])

        # When
        stats = entry_stats(trades_df, _summary(open_entry=6), self.TRADE_DF)

        # Then
        assert (stats.closed, stats.wins, stats.losses) == (2, 1, 1)
        assert stats.worst_pnl_pct == pytest.approx(-25.0, abs=1e-9)
        assert stats.lowest_vs_entry_pct == pytest.approx(-10.2692, abs=0.001)

    def test_exit_day_close_is_not_counted(self) -> None:
        """
        목적: 청산일 종가는 보유 중이 아니다 — 장중에 판 뒤의 종가라 그 값으로 최저를 잡으면 실제보다 나쁘게 나온다

        Given: i=4 ~ 5 거래, 청산일 i=5 의 종가 80 이 진입일 종가 100 보다 낮다
        When: entry_stats
        Then: 최저는 80 이 아니라 100 / 100.3 - 1 = -0.30%
        """
        # When
        stats = entry_stats(_trades([(4, 5, -0.25)]), _summary(), self.TRADE_DF)

        # Then
        assert stats.lowest_vs_entry_pct == pytest.approx(-0.2991, abs=0.001)

    def test_open_only_has_low_but_no_worst_trade(self) -> None:
        """
        목적: 보유 중 거래만 있으면 최악 거래 손익은 비어 있고 최저는 있다

        Given: 끝난 거래 없음, i=6 부터 보유
        When: entry_stats
        Then: 끝난 0, 최악 None, 최저 120 / 100.3 - 1 = +19.64%
        """
        # When
        stats = entry_stats(_trades([]), _summary(open_entry=6), self.TRADE_DF)

        # Then
        assert stats.closed == 0
        assert stats.worst_pnl_pct is None
        assert stats.lowest_vs_entry_pct == pytest.approx(19.6411, abs=0.001)

    def test_no_trades_at_all(self) -> None:
        """
        목적: 한 번도 사지 않으면 두 값 모두 비어 있다 — 0 으로 채우면 손익이 0 이었다는 뜻이 된다

        Given: 끝난 거래 없음, 보유 없음
        When: entry_stats
        Then: 끝난 0, 최악 None, 최저 None
        """
        # When
        stats = entry_stats(_trades([]), _summary(), self.TRADE_DF)

        # Then
        assert stats.closed == 0
        assert stats.worst_pnl_pct is None
        assert stats.lowest_vs_entry_pct is None

    def test_zero_pnl_counts_as_loss(self) -> None:
        """
        목적: 손익 0 은 익절이 아니다 — 비용을 내고 본전이면 번 것이 없다

        Given: 손익 0 인 거래 하나
        When: entry_stats
        Then: 익절 0 · 손절 1
        """
        # When
        stats = entry_stats(_trades([(1, 3, 0.0)]), _summary(), self.TRADE_DF)

        # Then
        assert (stats.wins, stats.losses) == (0, 1)


class TestTradeRows:
    # 시가 ≠ 종가 — 평가에 어느 값을 쓰는지 구분한다
    TRADE_DF = _prices(
        [100.0, 102.0, 90.0, 110.0, 100.0, 80.0, 120.0, 130.0],
        opens=[100.0, 101.0, 99.0, 105.0, 100.0, 90.0, 118.0, 125.0],
    )

    def test_closed_trade_row(self) -> None:
        """
        목적: 끝난 거래의 손익은 % 이고 보유 중 최저에 청산일 뒤 종가를 넣지 않는다

        Given: i=1 진입(101 × 1.003 = 101.303), i=3 청산, 손익 비율 0.10. 보유 중 종가 102 · 90, 청산 뒤 종가 80
        When: trade_rows
        Then: 손익 +10%, 최저 90 / 101.303 - 1 = -11.16%, 상태 끝남
        """
        # When
        rows = trade_rows({"이름": "합성"}, _trades([(1, 3, 0.10)]), _summary(), self.TRADE_DF)

        # Then
        assert len(rows) == 1
        assert rows[0]["이름"] == "합성"
        assert rows[0][DISPLAY_STATUS] == "끝남"
        assert rows[0][DISPLAY_PNL] == pytest.approx(10.0, abs=1e-9)
        assert rows[0][DISPLAY_LOWEST] == pytest.approx(-11.1576, abs=0.001)

    def test_open_trade_row_uses_last_close(self) -> None:
        """
        목적: 보유 중 거래는 마지막 시가가 아니라 마지막 종가로 평가한다

        Given: i=6 진입(118 × 1.003 = 118.354), 마지막 종가 130 · 마지막 시가 125
        When: trade_rows
        Then: 손익 130 / 118.354 - 1 = +9.84%, 최저 120 / 118.354 - 1 = +1.39%, 청산일 없음
        """
        # When
        rows = trade_rows({}, _trades([]), _summary(open_entry=6), self.TRADE_DF)

        # Then
        assert len(rows) == 1
        assert rows[0][DISPLAY_STATUS] == STATUS_OPEN
        assert rows[0][DISPLAY_EXIT_DATE] is None
        assert rows[0][DISPLAY_PNL] == pytest.approx(9.8400, abs=0.001)
        assert rows[0][DISPLAY_LOWEST] == pytest.approx(1.3907, abs=0.001)


class TestScope:
    def test_datasets(self) -> None:
        """
        목적: 데이터 · 배수 · 구간을 고정한다 — 안 본 구간의 끝날은 그 시세로 후보를 처음 잰 날의 전날이다

        Given: DATASETS
        When: 이름별로 모은다
        Then: 사용자가 정한 표와 같다 (정책 값이라 숫자로 고정)
        """
        # Given / When
        actual = {d.label: (d.group, d.data_path, d.leverage, d.start, d.end) for d in DATASETS}

        # Then
        y2004 = date(2004, 1, 2)
        end_gspc = date(1993, 11, 10)
        end_nasdaq = date(1999, 12, 20)
        assert actual == {
            "QQQ 2004 ~": (GROUP_SEEN, QQQ_DATA_PATH, 1, y2004, None),
            "QLD 2004 ~": (GROUP_SEEN, QLD_SYNTHETIC_DATA_PATH, 2, y2004, None),
            "TQQQ 2004 ~": (GROUP_SEEN, TQQQ_SYNTHETIC_DATA_PATH, 3, y2004, None),
            "QQQ 1999 ~": (GROUP_SEEN, QQQ_DATA_PATH, 1, None, None),
            "QLD 1999 ~": (GROUP_SEEN, QLD_SYNTHETIC_DATA_PATH, 2, None, None),
            "TQQQ 1999 ~": (GROUP_SEEN, TQQQ_SYNTHETIC_DATA_PATH, 3, None, None),
            "SPY": (GROUP_SEEN, SPY_DATA_PATH, 1, None, None),
            "GLD": (GROUP_SEEN, GLD_DATA_PATH, 1, None, None),
            "TLT": (GROUP_SEEN, TLT_DATA_PATH, 1, None, None),
            "^GSPC 1962 ~ 1993": (GROUP_UNSEEN, GSPC_DATA_PATH, 1, date(1962, 1, 2), end_gspc),
            "^NDX ~ 1999": (GROUP_UNSEEN, NDX_DATA_PATH, 1, None, end_nasdaq),
            "^IXIC ~ 1999": (GROUP_UNSEEN, IXIC_DATA_PATH, 1, None, end_nasdaq),
            "^GSPC 전체": (GROUP_FULL, GSPC_DATA_PATH, 1, date(1962, 1, 2), None),
            "^NDX 전체": (GROUP_FULL, NDX_DATA_PATH, 1, None, None),
            "^IXIC 전체": (GROUP_FULL, IXIC_DATA_PATH, 1, None, None),
        }

    def test_experiment_values(self) -> None:
        """
        목적: 실험마다 값과 기준을 고정한다 — 매도 10% 가 의심 대상이라 다른 실험은 매도 5% · 10% 두 기준으로 잰다

        Given: build_cases
        When: (실험, 기준 매도 폭)별로 값을 모은다
        Then: 사용자에게 보인 표와 같고 전부 64칸이다
        """
        # Given
        cases = build_cases()

        # When
        values: dict[tuple[str, float | None], list[float]] = {}
        for case in cases:
            values.setdefault((case.experiment, case.base_sell_pct), []).append(case.value)

        # Then
        sell = [
            0.03,
            0.04,
            0.05,
            0.06,
            0.07,
            0.075,
            0.08,
            0.09,
            0.10,
            0.11,
            0.12,
            0.125,
            0.13,
            0.14,
            0.15,
            0.16,
            0.18,
            0.20,
        ]
        buy = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.075, 0.08, 0.10, 0.12, 0.15]
        ma = [100, 150, 200, 250, 300]
        month = [15, 18, 20, 21, 22, 25]
        assert values == {
            (EXPERIMENT_SELL, None): sell,
            (EXPERIMENT_BUY, 0.05): buy,
            (EXPERIMENT_BUY, 0.10): buy,
            (EXPERIMENT_MA, 0.05): ma,
            (EXPERIMENT_MA, 0.10): ma,
            (EXPERIMENT_MONTH, 0.05): month,
            (EXPERIMENT_MONTH, 0.10): month,
        }
        assert len(cases) == 64

    def test_case_params_change_one_value_at_a_time(self) -> None:
        """
        목적: 칸마다 값 하나만 바뀌고 나머지는 이평선 200 · 한달 21 · 매수 5% · 눌림 제거다

        Given: build_cases
        When: 실험별 대표 칸의 파라미터를 본다
        Then: 그 값만 다르다
        """
        # Given
        cases = {(c.experiment, c.base_sell_pct, c.value): c.params for c in build_cases()}

        # When / Then
        assert cases[(EXPERIMENT_SELL, None, 0.125)] == RuleParams(200, 0.05, 0.125, 21, False)
        assert cases[(EXPERIMENT_BUY, 0.10, 0.03)] == RuleParams(200, 0.03, 0.10, 21, False)
        assert cases[(EXPERIMENT_MA, 0.05, 150)] == RuleParams(150, 0.05, 0.05, 21, False)
        assert cases[(EXPERIMENT_MONTH, 0.10, 25)] == RuleParams(200, 0.05, 0.10, 25, False)

    def test_rule_combos(self) -> None:
        """
        목적: 규칙 조합 네 개를 고정한다 — 첫 줄이 V2 규칙이다

        Given: RULE_COMBOS
        When: 파라미터의 눌림 · 매도 폭을 모은다
        Then: 눌림 있음 · 없음 × 매도 5% · 10%
        """
        # When
        actual = [(params.wait_for_pullback, params.sell_base_pct) for _, params in RULE_COMBOS]

        # Then
        assert actual == [(True, 0.05), (False, 0.05), (True, 0.10), (False, 0.10)]


def _swinging_prices(rows: int = 700) -> pd.DataFrame:
    """크게 오르내려 매수 · 손절이 여러 번 나오는 결정적 시세 — 이평선 300 이 계산되고 남을 만큼 길다."""
    closes = [100.0 + 40.0 * math.sin(i / 35.0) for i in range(rows)]
    return _prices(closes)


class TestEvaluateDataset:
    DATASET = SensitivityDataset(label="합성", group=GROUP_SEEN, data_path=QQQ_DATA_PATH)

    def test_row_counts_and_no_pass_column(self) -> None:
        """
        목적: 데이터 하나가 64칸 · 규칙 4행이고, 어느 표에도 합격 칸이 없다 (사용자 결정: 합격 점수를 두지 않는다)

        Given: 합성 시세
        When: evaluate_dataset
        Then: 행 수가 맞고 열 이름에 「합격」이 없다
        """
        # When
        tables = evaluate_dataset(self.DATASET, _swinging_prices())

        # Then
        assert len(tables.cells) == 64
        assert len(tables.rules) == 4
        for rows in (tables.cells, tables.rules, tables.trades):
            assert rows
            assert not [column for column in rows[0] if "합격" in column]

    def test_diff_is_against_same_period_buy_and_hold(self) -> None:
        """
        목적: 차이는 같은 구간 Buy & Hold 대비다 — 이평선 칸은 더 늦게 시작하므로 Buy & Hold 도 그 기간으로 잰다

        Given: 합성 시세와 두 기간으로 따로 잰 Buy & Hold
        When: evaluate_dataset
        Then: 칸마다 자기 기간의 Buy & Hold 를 적고, 차이 = 값 - Buy & Hold 이며, 두 기간의 값이 실제로 다르다
        """
        # Given
        prices = _swinging_prices()
        ma_expected = run_buy_and_hold(*slice_period(prices, MA_WINDOW_VALUES, None, None))
        base_expected = run_buy_and_hold(*slice_period(prices, [200], None, None))

        # When
        tables = evaluate_dataset(self.DATASET, prices)

        # Then
        df = pd.DataFrame(tables.cells)
        is_ma = df[DISPLAY_EXPERIMENT] == EXPERIMENT_MA
        assert ma_expected["cagr"] != pytest.approx(base_expected["cagr"], abs=0.01)
        assert set(df.loc[is_ma, DISPLAY_BH_CAGR]) == {ma_expected["cagr"]}
        assert set(df.loc[~is_ma, DISPLAY_BH_CAGR]) == {base_expected["cagr"]}
        assert set(df.loc[is_ma, DISPLAY_BH_MDD]) == {ma_expected["mdd"]}
        assert set(df.loc[~is_ma, DISPLAY_BH_MDD]) == {base_expected["mdd"]}
        assert (df[DISPLAY_CAGR] - df[DISPLAY_BH_CAGR]).tolist() == pytest.approx(
            df[DISPLAY_CAGR_DIFF].tolist(), abs=1e-9
        )
        assert (df[DISPLAY_MDD] - df[DISPLAY_BH_MDD]).tolist() == pytest.approx(df[DISPLAY_MDD_DIFF].tolist(), abs=1e-9)
        assert df.loc[is_ma, DISPLAY_START].nunique() == 1
        assert df.loc[is_ma, DISPLAY_START].iloc[0] > df.loc[~is_ma, DISPLAY_START].iloc[0]

    def test_trade_rows_match_closed_counts(self) -> None:
        """
        목적: 거래 목록의 끝난 거래 수가 칸의 끝난 거래 수와 같다 — 과최적화를 거래 목록으로 판단하므로 빠지면 안 된다

        Given: 합성 시세
        When: evaluate_dataset
        Then: 칸 표와 규칙 표의 끝난 거래 수 합이 거래 목록의 끝난 행 수와 같고, 거래가 실제로 있다
        """
        # When
        tables = evaluate_dataset(self.DATASET, _swinging_prices())

        # Then
        closed_in_tables = sum(int(str(row[DISPLAY_CLOSED])) for row in [*tables.cells, *tables.rules])
        closed_in_trades = sum(1 for row in tables.trades if row["상태"] == "끝남")
        assert closed_in_tables == closed_in_trades > 0

    def test_dataset_label_and_value_on_rows(self) -> None:
        """
        목적: 행마다 데이터 이름과 값이 있어 화면이 값별로 고를 수 있다

        Given: 합성 시세
        When: evaluate_dataset
        Then: 칸 표의 데이터 이름은 하나이고, 매도 실험의 값이 18개다
        """
        # When
        tables = evaluate_dataset(self.DATASET, _swinging_prices())

        # Then
        df = pd.DataFrame(tables.cells)
        assert set(df[DISPLAY_DATASET]) == {"합성"}
        assert df.loc[df[DISPLAY_EXPERIMENT] == EXPERIMENT_SELL, DISPLAY_VALUE].nunique() == 18

    def test_open_trade_pnl_is_valued_at_last_close(self) -> None:
        """
        목적: 보유 중 거래의 손익은 마지막 종가로 평가한 값이다 — 진입가는 그날 시가 + 슬리피지

        Given: 합성 시세 (시가 = 종가)
        When: evaluate_dataset
        Then: 보유 중 행마다 손익 = 마지막 종가 / (진입일 시가 × (1 + SLIPPAGE_RATE)) - 1, 보유 중 행이 실제로 있다
        """
        # Given
        prices = _swinging_prices()
        open_by_day = dict(zip(prices["Date"], prices["Open"], strict=True))
        last_close = float(prices["Close"].iloc[-1])

        # When
        tables = evaluate_dataset(self.DATASET, prices)

        # Then
        open_rows = [row for row in tables.trades if row[DISPLAY_STATUS] == STATUS_OPEN]
        assert open_rows
        for row in open_rows:
            entry_price = open_by_day[row[DISPLAY_ENTRY_DATE]] * (1 + SLIPPAGE_RATE)
            assert row[DISPLAY_PNL] == pytest.approx((last_close / entry_price - 1) * 100.0, abs=1e-9)
