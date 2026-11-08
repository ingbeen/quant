"""구간별 성과 테스트

구간을 어디서 자르고 낙폭을 어디부터 재느냐가 틀려도 화면은 그럴듯한 숫자를 보인다.
아래 테스트는 구간 정의 · 값이 없는 구간의 처리 · 쏠림과 자산 기여의 산식을 손 계산으로 고정한다.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

import pandas as pd
import pytest

from qbt.backtest.analysis import calculate_summary
from qbt.backtest.period_performance import (
    calculate_period_performance,
    calculate_yearly_asset_contributions,
)

from helpers import weekdays


def _equity_df(points: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame({"Date": [date.fromisoformat(d) for d, _ in points], "equity": [v for _, v in points]})


def _row(rows: Sequence[Mapping[str, Any]], label: str) -> Mapping[str, Any]:
    return next(row for row in rows if row["label"] == label)


class TestSplits:
    def test_full_period_matches_summary(self) -> None:
        """
        목적: 「전체」 구간의 값은 기존 요약 지표와 같다

        Given: 첫 값이 초기 자본인 자본 곡선
        When: 구간별 성과를 계산한다
        Then: 연 수익 · 최악 낙폭 · 총 수익률이 calculate_summary 와 같다
        """
        # Given
        df = _equity_df([("2020-01-02", 100.0), ("2021-01-04", 150.0), ("2022-01-03", 120.0), ("2023-01-03", 180.0)])
        summary = calculate_summary(pd.DataFrame(), df, initial_capital=100.0)

        # When
        row = _row(calculate_period_performance(df, signal_df=None)["splits"], "전체")

        # Then
        assert (row["start_date"], row["end_date"]) == ("2020-01-02", "2023-01-03")
        assert row["cagr"] == pytest.approx(summary["cagr"], abs=0.01)
        assert row["mdd"] == pytest.approx(summary["mdd"], abs=0.01)
        assert row["total_return_pct"] == pytest.approx(80.0, abs=0.01)

    def test_halves_share_the_middle_trading_day(self) -> None:
        """
        목적: 앞 · 뒤 절반은 가운데 날 이하 마지막 거래일을 함께 쓴다 — 두 구간의 복리가 전체와 같다

        Given: 가운데 날(2021-07-04 근처)이 거래일이 아닌 곡선
        When: 구간별 성과를 계산한다
        Then: 앞의 끝과 뒤의 시작이 2021-01-04 이고, (1 + 앞)(1 + 뒤) = 1 + 전체
        """
        # Given
        df = _equity_df([("2020-01-02", 100.0), ("2021-01-04", 150.0), ("2022-01-03", 120.0), ("2023-01-03", 180.0)])

        # When
        splits = calculate_period_performance(df, signal_df=None)["splits"]
        first, second = _row(splits, "앞 절반"), _row(splits, "뒤 절반")

        # Then
        assert (first["end_date"], second["start_date"]) == ("2021-01-04", "2021-01-04")
        combined = (1 + first["total_return_pct"] / 100) * (1 + second["total_return_pct"] / 100)
        assert combined == pytest.approx(1.8, abs=0.001)

    def test_recent_years_start_on_or_after_requested_day(self) -> None:
        """
        목적: 최근 N년은 끝날에서 N년을 뺀 날 이상 첫 거래일부터 잰다

        Given: 끝날 2025-06-30, 10년 전 · 5년 전 날짜에 행이 있는 곡선
        When: 구간별 성과를 계산한다
        Then: 최근 10년 · 5년의 시작일과 총 수익률이 그 행 기준이다
        """
        # Given
        df = _equity_df(
            [
                ("2005-01-03", 100.0),
                ("2015-06-30", 200.0),
                ("2015-07-01", 210.0),
                ("2020-06-30", 420.0),
                ("2025-06-30", 840.0),
            ]
        )

        # When
        splits = calculate_period_performance(df, signal_df=None)["splits"]

        # Then
        assert _row(splits, "최근 10년")["start_date"] == "2015-06-30"
        assert _row(splits, "최근 10년")["total_return_pct"] == pytest.approx(320.0, abs=0.01)
        assert _row(splits, "최근 5년")["total_return_pct"] == pytest.approx(100.0, abs=0.01)

    def test_period_starting_before_first_day_has_no_values(self) -> None:
        """
        목적: 구간 시작이 데이터 첫날보다 이르면 일부만 잰 값을 내지 않는다

        Given: 2005 년에 시작하는 곡선
        When: 구간별 성과를 계산한다
        Then: 2000 년에 시작하는 구간은 요청한 날짜와 빈 값이다
        """
        # Given
        df = _equity_df([("2005-01-03", 100.0), ("2010-01-04", 200.0)])

        # When
        row = _row(calculate_period_performance(df, signal_df=None)["splits"], "닷컴 정점부터")

        # Then
        assert (row["start_date"], row["end_date"]) == ("2000-03-24", "2010-01-04")
        assert (row["cagr"], row["mdd"], row["total_return_pct"]) == (None, None, None)

    def test_period_start_snaps_to_next_trading_day(self) -> None:
        """
        목적: 구간 시작일이 거래일이 아니면 그 뒤 첫 거래일부터 잰다

        Given: 2000-03-24 에 행이 없는 곡선
        When: 구간별 성과를 계산한다
        Then: 「닷컴 정점부터」는 2000-03-27 부터 잰다
        """
        # Given
        df = _equity_df([("2000-03-23", 100.0), ("2000-03-27", 110.0), ("2001-03-27", 121.0)])

        # When
        row = _row(calculate_period_performance(df, signal_df=None)["splits"], "닷컴 정점부터")

        # Then
        assert row["start_date"] == "2000-03-27"
        assert row["total_return_pct"] == pytest.approx(10.0, abs=0.01)

    def test_drawdown_restarts_at_period_start(self) -> None:
        """
        목적: 구간 최악 낙폭은 구간 첫날을 고점으로 다시 잰다 — 구간 전의 고점을 끌고 오지 않는다

        Given: 구간 전에 200 까지 갔다가 구간 시작일에 100, 그 뒤 90 까지 빠지는 곡선
        When: 구간별 성과를 계산한다
        Then: 최악 낙폭은 -55% 가 아니라 -10% 다
        """
        # Given
        df = _equity_df([("2000-01-03", 200.0), ("2000-03-24", 100.0), ("2000-06-01", 90.0), ("2001-01-02", 120.0)])

        # When
        row = _row(calculate_period_performance(df, signal_df=None)["splits"], "닷컴 정점부터")

        # Then
        assert row["mdd"] == pytest.approx(-10.0, abs=0.01)

    def test_fewer_than_two_rows_stops(self) -> None:
        """
        목적: 구간을 잴 수 없는 입력은 멈춘다

        Given: 1행짜리 곡선
        When: 구간별 성과를 계산한다
        Then: ValueError
        """
        # Given
        df = _equity_df([("2020-01-02", 100.0)])

        # When / Then
        with pytest.raises(ValueError, match="2행"):
            calculate_period_performance(df, signal_df=None)


class TestRegimes:
    _POINTS = [("2020-01-02", 100.0), ("2020-02-19", 120.0), ("2020-03-23", 90.0), ("2020-12-31", 130.0)]

    def test_regime_return_and_signal_move(self) -> None:
        """
        목적: 국면 값은 그 구간 안의 수익률 · 낙폭이고, 신호 시세가 있으면 같은 구간의 등락을 붙인다

        Given: 코로나 구간에 120 → 90 인 곡선과 400 → 200 인 신호 시세
        When: 구간별 성과를 계산한다
        Then: 수익률 -25%, 낙폭 -25%, 신호 등락 -50%, 종류는 하락장
        """
        # Given
        df = _equity_df(self._POINTS)
        signal_df = pd.DataFrame(
            {
                "Date": [date.fromisoformat(d) for d, _ in self._POINTS],
                "Close": [300.0, 400.0, 200.0, 500.0],
            }
        )

        # When
        row = _row(calculate_period_performance(df, signal_df=signal_df)["regimes"], "코로나")

        # Then
        assert row["kind"] == "하락장"
        assert row["return_pct"] == pytest.approx(-25.0, abs=0.01)
        assert row["mdd"] == pytest.approx(-25.0, abs=0.01)
        assert row["signal_return_pct"] == pytest.approx(-50.0, abs=0.01)

    def test_no_signal_leaves_signal_move_empty(self) -> None:
        """
        목적: 신호 시세를 주지 않으면 신호 등락은 비어 있다

        Given: 신호 시세 없음
        When: 구간별 성과를 계산한다
        Then: signal_return_pct 가 None
        """
        # Given
        df = _equity_df(self._POINTS)

        # When
        row = _row(calculate_period_performance(df, signal_df=None)["regimes"], "코로나")

        # Then
        assert row["signal_return_pct"] is None

    def test_regime_outside_data_has_no_values(self) -> None:
        """
        목적: 데이터 시작 전의 국면은 정의한 날짜와 빈 값이다

        Given: 2020 년에 시작하는 곡선
        When: 구간별 성과를 계산한다
        Then: 1987 국면의 값이 비어 있다
        """
        # Given
        df = _equity_df(self._POINTS)

        # When
        row = _row(calculate_period_performance(df, signal_df=None)["regimes"], "1987 블랙먼데이")

        # Then
        assert (row["start_date"], row["end_date"]) == ("1987-08-25", "1987-10-19")
        assert (row["return_pct"], row["mdd"]) == (None, None)

    def test_regime_ending_after_data_end_has_no_values(self) -> None:
        """
        목적: 데이터가 국면 중간에 끝나면 일부만 잰 값을 내지 않는다

        Given: 코로나 구간 중간인 2020-03-01 에 끝나는 곡선
        When: 구간별 성과를 계산한다
        Then: 코로나 국면의 값이 비어 있다
        """
        # Given
        df = _equity_df([("2020-01-02", 100.0), ("2020-02-19", 120.0), ("2020-03-01", 90.0)])

        # When
        row = _row(calculate_period_performance(df, signal_df=None)["regimes"], "코로나")

        # Then
        assert row["return_pct"] is None


class TestRolling:
    def test_constant_growth_gives_same_return_for_every_start(self) -> None:
        """
        목적: 달마다 첫 거래일에 시작하고, 끝이 데이터 밖인 시작은 넣지 않는다

        Given: 연 10% 로 일정하게 불어나는 2010-01 ~ 2016-06 곡선
        When: 구간별 성과를 계산한다
        Then: 5년 보유는 18가지(2010-01 ~ 2011-06 시작)이고 모두 연 10%, 10년 보유는 0가지라 요약이 비어 있다
        """
        # Given
        days = weekdays(date(2010, 1, 1), date(2016, 6, 30))
        values = [100.0 * 1.1 ** ((d - days[0]).days / 365.25) for d in days]
        df = pd.DataFrame({"Date": days, "equity": values})

        # When
        five, ten = calculate_period_performance(df, signal_df=None)["rolling"]

        # Then
        assert (five["years"], five["count"], len(five["points"])) == (5, 18, 18)
        assert five["points"][0]["start_date"] == "2010-01-01"
        assert five["points"][-1]["start_date"] == "2011-06-01"
        assert five["min_cagr"] == pytest.approx(10.0, abs=0.01)
        assert five["negative_count"] == 0
        assert (ten["years"], ten["count"], ten["min_cagr"], ten["min_start_date"]) == (10, 0, None, None)

    def test_summary_statistics(self) -> None:
        """
        목적: 최저 · 하위 10% · 중앙 · 마이너스 횟수가 시작 달별 연 수익에서 나온다

        Given: 2010 년 1 ~ 6월 시작값 100, 5년 뒤 값 50 · 80 · 100 · 121 · 144 · 169
        When: 구간별 성과를 계산한다
        Then: 경우 6, 마이너스 2 (0% 는 세지 않음), 최저는 2010-01 시작, 하위 10% 는 c0 와 c1 의 가운데, 중앙은 c2 와 c3 의 가운데
        """
        # Given
        finals = [50.0, 80.0, 100.0, 121.0, 144.0, 169.0]
        starts = [(f"2010-0{m}-01", 100.0) for m in range(1, 7)]
        ends = [(f"2015-0{m}-01", finals[m - 1]) for m in range(1, 7)]
        df = _equity_df(starts + ends)
        c = [((v / 100.0) ** (365.25 / 1826) - 1) * 100 for v in finals]

        # When
        five = calculate_period_performance(df, signal_df=None)["rolling"][0]

        # Then
        assert five["count"] == 6
        assert five["negative_count"] == 2
        assert five["min_start_date"] == "2010-01-01"
        assert five["min_cagr"] == pytest.approx(c[0], abs=0.01)
        assert five["p10_cagr"] == pytest.approx((c[0] + c[1]) / 2, abs=0.01)
        assert five["median_cagr"] == pytest.approx((c[2] + c[3]) / 2, abs=0.01)


class TestConcentration:
    def test_counts_share_and_zeroed_means(self) -> None:
        """
        목적: 쏠림 값이 연간 수익률에서 부록 O.8 의 정의대로 나온다 (0% 인 해는 플러스도 마이너스도 아니다)

        Given: 연간 +10 · +20 · -10 · +50 · 0%
        When: 구간별 성과를 계산한다
        Then: 플러스 3 · 마이너스 1 · 중앙 10 · 평균 14 · 최고 3개 해 2023 · 2021 · 2020, 몫 80 / 70, 0% 로 바꾼 평균 -2 와 0
        """
        # Given
        df = _equity_df(
            [
                ("2020-01-02", 100.0),
                ("2020-12-31", 110.0),
                ("2021-12-31", 132.0),
                ("2022-12-30", 118.8),
                ("2023-12-29", 178.2),
                ("2024-12-31", 178.2),
            ]
        )

        # When
        result = calculate_period_performance(df, signal_df=None)["concentration"]

        # Then
        assert (result["year_count"], result["positive_years"], result["negative_years"]) == (5, 3, 1)
        assert result["median_pct"] == pytest.approx(10.0, abs=0.01)
        assert result["mean_pct"] == pytest.approx(14.0, abs=0.01)
        assert result["top_years"] == [2023, 2021, 2020]
        assert result["top3_share_pct"] == pytest.approx(114.29, abs=0.01)
        assert result["mean_without_top3_pct"] == pytest.approx(-2.0, abs=0.01)
        assert result["mean_without_top5_pct"] == pytest.approx(0.0, abs=0.01)

    def test_non_positive_total_has_no_share(self) -> None:
        """
        목적: 전체 합이 0 이하면 몫을 내지 않는다 — 음수로 나눈 값은 뜻이 없다

        Given: 연간 -10 · +5%
        When: 구간별 성과를 계산한다
        Then: top3_share_pct 가 None
        """
        # Given
        df = _equity_df([("2020-01-02", 100.0), ("2020-12-31", 90.0), ("2021-12-31", 94.5)])

        # When
        result = calculate_period_performance(df, signal_df=None)["concentration"]

        # Then
        assert result["top3_share_pct"] is None

    def test_tied_years_keep_earlier_year_first(self) -> None:
        """
        목적: 수익률이 같은 해는 이른 해가 먼저다 — 실행마다 저장 결과가 달라지지 않게

        Given: 연간 +10 · +10 · +10 · +10%
        When: 구간별 성과를 계산한다
        Then: 최고 3개 해가 2020 · 2021 · 2022
        """
        # Given
        df = _equity_df(
            [
                ("2020-01-02", 100.0),
                ("2020-12-31", 110.0),
                ("2021-12-31", 121.0),
                ("2022-12-30", 133.1),
                ("2023-12-29", 146.41),
            ]
        )

        # When
        result = calculate_period_performance(df, signal_df=None)["concentration"]

        # Then
        assert result["top_years"] == [2020, 2021, 2022]


class TestYearlyAssetContributions:
    @staticmethod
    def _df(equity_2021: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "Date": [date(2020, 1, 2), date(2020, 12, 31), date(2021, 12, 31)],
                "equity": [100.0, 120.0, equity_2021],
                "a_contribution": [0.0, 15.0, 6.0],
                "b_contribution": [0.0, 5.0, 2.0],
            }
        )

    def test_assets_add_up_to_the_year_return(self) -> None:
        """
        목적: 자산별 기여는 그해 변화를 직전 연말 계좌로 나눈 값이고, 합이 그해 수익률이다

        Given: 2020 년 +20 (a 15 · b 5), 2021 년 -10% (a -9 · b -3, 기준 120)
        When: 자산 기여를 계산한다
        Then: 2021 년 a -7.5 · b -2.5, 기타 0
        """
        # Given
        df = self._df(equity_2021=108.0)

        # When
        rows = calculate_yearly_asset_contributions(df, ["a", "b"])

        # Then
        assert [row["year"] for row in rows] == [2020, 2021]
        assert rows[0]["assets"] == {"a": pytest.approx(15.0, abs=0.01), "b": pytest.approx(5.0, abs=0.01)}
        assert rows[1]["return_pct"] == pytest.approx(-10.0, abs=0.01)
        assert rows[1]["assets"] == {"a": pytest.approx(-7.5, abs=0.01), "b": pytest.approx(-2.5, abs=0.01)}
        assert rows[1]["other_pct"] == pytest.approx(0.0, abs=0.01)

    def test_unattributed_change_goes_to_other(self) -> None:
        """
        목적: 자산에 나뉘지 않은 손익(상계 절감 등)은 기타로 남는다

        Given: 2021 년 계좌만 12 더 늘어난 곡선 (기준 120)
        When: 자산 기여를 계산한다
        Then: 기타가 +10
        """
        # Given
        df = self._df(equity_2021=120.0)

        # When
        rows = calculate_yearly_asset_contributions(df, ["a", "b"])

        # Then
        assert rows[1]["other_pct"] == pytest.approx(10.0, abs=0.01)

    def test_tiny_negative_rounds_to_plain_zero(self) -> None:
        """
        목적: 반올림으로 0 이 된 작은 음수는 -0.0 으로 저장하지 않는다 — 표에 「-0.00」으로 보인다

        Given: 자산 기여 합보다 계좌가 아주 조금 덜 변한 해 (기타 약 -0.00008%)
        When: 자산 기여를 계산한다
        Then: 기타의 부호가 양수인 0
        """
        # Given
        df = self._df(equity_2021=107.9999)

        # When
        rows = calculate_yearly_asset_contributions(df, ["a", "b"])

        # Then
        assert (rows[1]["other_pct"], math.copysign(1.0, rows[1]["other_pct"])) == (0.0, 1.0)

    def test_missing_contribution_column_stops(self) -> None:
        """
        목적: 기여 열이 없으면 0 으로 메우지 않고 멈춘다

        Given: c 자산의 기여 열이 없는 표
        When: 자산 기여를 계산한다
        Then: ValueError
        """
        # Given
        df = self._df(equity_2021=108.0)

        # When / Then
        with pytest.raises(ValueError, match="c_contribution"):
            calculate_yearly_asset_contributions(df, ["a", "c"])

    def test_fewer_than_two_rows_stops(self) -> None:
        """
        목적: 해를 나눌 수 없는 입력은 멈춘다

        Given: 1행짜리 표
        When: 자산 기여를 계산한다
        Then: ValueError
        """
        # Given
        df = self._df(equity_2021=108.0).iloc[:1]

        # When / Then
        with pytest.raises(ValueError, match="2행"):
            calculate_yearly_asset_contributions(df, ["a", "b"])
