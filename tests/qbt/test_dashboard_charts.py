"""대시보드 차트 생성 테스트

툴팁 · 선 · 마커 · 히트맵 칸의 값이 틀려도 화면은 에러 없이 그려진다.
아래 테스트는 각 값이 «어느 표의 어느 날짜 행»에서 오는지를 고정한다.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import pandas as pd
import pytest

from qbt.backtest.dashboard_charts import (
    ChartPane,
    build_equity_panes,
    build_monthly_heatmap,
    build_price_pane,
    build_trade_markers,
    chart_component_args,
)


def _signal_df(dates: list[Any]) -> pd.DataFrame:
    """3일치 시그널 표 — 첫날은 전일대비%와 이동평균이 비어 있다."""
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": [100.0, 101.0, 102.0],
            "High": [101.0, 102.5, 103.0],
            "Low": [99.0, 100.5, 101.0],
            "Close": [100.5, 102.0, 101.5],
            "open_pct": [float("nan"), 0.4975, 0.0],
            "high_pct": [float("nan"), 1.99, 0.98],
            "low_pct": [float("nan"), 0.0, -0.98],
            "close_pct": [float("nan"), 1.4925, -0.4902],
            "ma_2": [float("nan"), 101.25, 101.75],
        }
    )


def _series_data(series: dict[str, object]) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], series["data"])


def _tooltip(pane: ChartPane, i: int) -> dict[str, str]:
    return cast(dict[str, str], _series_data(pane["series"][0])[i]["customValues"])


class TestBuildPricePane:
    def test_tooltip_reads_overlay_row_of_same_date(self) -> None:
        """
        목적: 툴팁의 밴드 · 에쿼티 · 드로우다운은 겹침 표에서 «같은 날짜» 행의 값이다

        Given: 시그널 3일, 겹침 표는 둘째 · 셋째 날만 있고 행 순서가 뒤집혀 있다. 셋째 날 밴드는 비어 있다
        When: 캔들 패널을 만든다
        Then: 둘째 날 툴팁에 둘째 날 값이 표기 형식대로 들어가고, 겹침 행이 없는 첫날과 빈 값에는 그 키가 없다
        """
        # Given
        days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        overlay_df = pd.DataFrame(
            {
                "Date": [days[2], days[1]],
                "upper_band": [float("nan"), 104.2],
                "lower_band": [float("nan"), 96.2],
                "equity": [10_250_000.0, 10_123_456.0],
                "drawdown_pct": [-1.5, -0.25],
            }
        )

        # When
        pane = build_price_pane(_signal_df(days), overlay_df, [], title="T")

        # Then
        assert _tooltip(pane, 1) == {
            "open": "101.00",
            "high": "102.50",
            "low": "100.50",
            "close": "102.00",
            "open_pct": "+0.50",
            "high_pct": "+1.99",
            "low_pct": "+0.00",
            "close_pct": "+1.49",
            "ma": "101.25",
            "upper": "104.20",
            "lower": "96.20",
            "equity": "10,123,456",
            "dd": "-0.25",
        }
        assert _tooltip(pane, 0) == {"open": "100.00", "high": "101.00", "low": "99.00", "close": "100.50"}
        assert ("upper" in _tooltip(pane, 2), "equity" in _tooltip(pane, 2)) == (False, True)

    def test_band_lines_come_from_overlay_table(self) -> None:
        """
        목적: 밴드 선은 시그널 표가 아니라 넘겨받은 겹침 표에서 읽고, 이동평균 선은 시그널 표에서 읽는다

        Given: 시그널 표(날짜 열이 datetime)와 겹침 표가 서로 다른 밴드 값을 갖는다
        When: 캔들 패널을 만든다
        Then: 상단 · 하단 밴드 선은 겹침 표 값(빈 칸 제외) · 점선이고, 이동평균 선은 시그널 표 값 · 실선이다
        """
        # Given
        days = list(pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]))
        signal_df = _signal_df(days).assign(upper_band=[1.0, 1.0, 1.0], lower_band=[1.0, 1.0, 1.0])
        overlay_df = pd.DataFrame(
            {"Date": days, "upper_band": [float("nan"), 104.2, 104.8], "lower_band": [float("nan"), 96.2, 96.7]}
        )

        # When
        pane = build_price_pane(signal_df, overlay_df, [], title="T")

        # Then
        ma_line, upper_line, lower_line = pane["series"][1:]
        assert _series_data(ma_line) == [
            {"time": "2024-01-03", "value": 101.25},
            {"time": "2024-01-04", "value": 101.75},
        ]
        assert _series_data(upper_line) == [
            {"time": "2024-01-03", "value": 104.2},
            {"time": "2024-01-04", "value": 104.8},
        ]
        assert _series_data(lower_line) == [
            {"time": "2024-01-03", "value": 96.2},
            {"time": "2024-01-04", "value": 96.7},
        ]
        assert "lineStyle" not in cast(dict[str, object], ma_line["options"])
        assert cast(dict[str, object], upper_line["options"])["lineStyle"] == 2

    def test_no_moving_average_or_bands(self) -> None:
        """
        목적: 이동평균 · 밴드 열이 없는 시세(매수 후 보유)는 캔들만 그린다 (경계)

        Given: 이동평균 열이 없는 시그널 표와 밴드 열이 없는 겹침 표
        When: 캔들 패널을 만든다
        Then: 시리즈가 캔들 하나이고 툴팁에 이동평균 키가 없다. 마커는 넘긴 그대로 캔들에 붙는다
        """
        # Given
        days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        signal_df = _signal_df(days).drop(columns="ma_2")
        overlay_df = pd.DataFrame({"Date": days, "equity": [1.0, 2.0, 3.0]})
        markers: list[dict[str, object]] = [{"time": "2024-01-03", "text": "Buy"}]

        # When
        pane = build_price_pane(signal_df, overlay_df, markers, title="T")

        # Then
        assert [s["type"] for s in pane["series"]] == ["Candlestick"]
        assert "ma" not in _tooltip(pane, 2)
        assert pane["series"][0]["markers"] == markers

    def test_markers_are_sorted_by_time(self) -> None:
        """
        목적: 마커는 넘긴 순서와 관계없이 시간순으로 붙는다 — 차트가 보이는 구간의 마커를 날짜로 이진 탐색한다

        Given: 윈도우 중간 날짜의 경계 마커를 앞에 붙이고 거래 마커가 뒤따르는 목록 (워크포워드 모양)
        When: 캔들 패널을 만든다
        Then: 캔들의 마커가 날짜순이다
        """
        # Given
        days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        trades_df = pd.DataFrame({"entry_date": [days[0]], "exit_date": [days[2]], "pnl_pct": [0.01]})
        markers: list[dict[str, object]] = [
            {"time": "2024-01-03", "text": "OOS Start"},
            *build_trade_markers(trades_df),
        ]

        # When
        pane = build_price_pane(_signal_df(days), pd.DataFrame({"Date": days}), markers, title="T")

        # Then
        attached = cast(list[dict[str, object]], pane["series"][0]["markers"])
        assert [(m["time"], m["text"]) for m in attached] == [
            ("2024-01-02", "Buy"),
            ("2024-01-03", "OOS Start"),
            ("2024-01-04", "Sell +1.0%"),
        ]


class TestBuildEquityPanes:
    def test_equity_and_drawdown_columns(self) -> None:
        """
        목적: 에쿼티 패널은 equity 열, 드로우다운 패널은 drawdown_pct 열을 날짜별로 그린다

        Given: 2일치 에쿼티 표
        When: 에쿼티 패널을 만든다
        Then: 두 패널의 순서 · 제목 · 값이 열과 맞는다
        """
        # Given
        equity_df = pd.DataFrame(
            {
                "Date": [date(2024, 1, 2), date(2024, 1, 3)],
                "equity": [10_000_000, 9_800_000],
                "drawdown_pct": [0.0, -2.0],
            }
        )

        # When
        equity_pane, drawdown_pane = build_equity_panes(equity_df)

        # Then
        assert equity_pane["title"] == "에쿼티 (원)"
        assert _series_data(equity_pane["series"][0]) == [
            {"time": "2024-01-02", "value": 10_000_000.0},
            {"time": "2024-01-03", "value": 9_800_000.0},
        ]
        assert drawdown_pane["title"] == "드로우다운 (%)"
        assert _series_data(drawdown_pane["series"][0]) == [
            {"time": "2024-01-02", "value": 0.0},
            {"time": "2024-01-03", "value": -2.0},
        ]


class TestBuildTradeMarkers:
    def test_buy_and_sell_marker_per_trade(self) -> None:
        """
        목적: 거래마다 진입일 Buy · 청산일 Sell ±손익% 를 둔다 (거래 순서 — 정렬은 캔들 패널이 한다)

        Given: 거래 표 2행 (손익률은 비율)
        When: 마커를 만든다
        Then: 거래마다 Buy(진입일, 막대 아래) · Sell ±손익%(청산일, 막대 위) 한 쌍이다
        """
        # Given
        trades_df = pd.DataFrame(
            {
                "entry_date": [date(2024, 1, 2), date(2024, 3, 1)],
                "exit_date": [date(2024, 2, 1), date(2024, 4, 1)],
                "pnl_pct": [-0.05, 0.123],
            }
        )

        # When
        markers = build_trade_markers(trades_df)

        # Then
        assert [(m["time"], m["text"]) for m in markers] == [
            ("2024-01-02", "Buy"),
            ("2024-02-01", "Sell -5.0%"),
            ("2024-03-01", "Buy"),
            ("2024-04-01", "Sell +12.3%"),
        ]
        assert [m["position"] for m in markers] == ["belowBar", "aboveBar", "belowBar", "aboveBar"]

    def test_open_position_without_closed_trades(self) -> None:
        """
        목적: 미청산 진입일이면 「Buy (보유중)」 마커를 둔다 — 청산된 거래가 없어도 (경계)

        Given: 행이 없는 거래 표(머리글만)와 미청산 진입일
        When: 마커를 만든다
        Then: 그 진입일의 「Buy (보유중)」 하나다. 미청산이 없으면 마커가 없다
        """
        # Given
        empty_trades = pd.DataFrame({"entry_date": [], "exit_date": [], "pnl_pct": []})

        # When
        with_open = build_trade_markers(empty_trades, open_entry_date="2024-05-02")
        without_open = build_trade_markers(empty_trades)

        # Then
        assert [(m["time"], m["text"], m["position"]) for m in with_open] == [("2024-05-02", "Buy (보유중)", "belowBar")]
        assert without_open == []


class TestChartComponentArgs:
    def test_height_is_sum_of_panes(self) -> None:
        """
        목적: 컴포넌트 높이는 패널 높이의 합이다 — 모자라면 아래 패널이 잘린다

        Given: 캔들 · 에쿼티 · 드로우다운 패널
        When: 컴포넌트 인자를 만든다
        Then: 높이가 세 패널 높이의 합이고 이름 · 키 · 패널이 그대로 실린다
        """
        # Given
        days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        equity_df = pd.DataFrame({"Date": days, "equity": [1.0, 2.0, 3.0], "drawdown_pct": [0.0, 0.0, 0.0]})
        panes = [build_price_pane(_signal_df(days), equity_df, [], title="T"), *build_equity_panes(equity_df)]

        # When
        args = chart_component_args(panes, name="n", key="k")

        # Then
        assert args["height"] == sum(pane["height"] for pane in panes)
        assert (args["name"], args["key"], args["charts"]) == ("n", "k", panes)


class TestBuildMonthlyHeatmap:
    @staticmethod
    def _returns() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """2023-03 에 시작해 2024-01 에 끝나는 결과 — 2023 의 1 · 2월과 2024 의 2월 이후가 없다."""
        monthly = [{"year": 2023, "month": m, "return_pct": float(m)} for m in range(3, 13)]
        monthly.append({"year": 2024, "month": 1, "return_pct": -4.0})
        yearly = [{"year": 2024, "return_pct": -4.0}, {"year": 2023, "return_pct": 30.0}]
        return monthly, yearly

    def test_cells_by_year_and_month(self) -> None:
        """
        목적: 칸은 연도(오름차순) × 월 자리에 놓이고, 연간 열은 같은 연도 행에 붙는다

        Given: 3월에 시작해 다음 해 1월에 끝나는 월별 · 연간 수익률 (연간은 연도 역순으로 저장)
        When: 히트맵을 만든다
        Then: 없는 달은 빈 칸 · 빈 글자이고, 연간 열이 연도 행과 맞는다
        """
        # Given
        monthly, yearly = self._returns()

        # When
        data = build_monthly_heatmap(monthly, yearly).to_dict()["data"]

        # Then
        monthly_trace, yearly_trace = data
        assert list(monthly_trace["y"]) == ["2023", "2024"]
        assert list(monthly_trace["z"][0]) == [None, None, *[float(m) for m in range(3, 13)]]
        assert list(monthly_trace["z"][1]) == [-4.0, *[None] * 11]
        assert list(monthly_trace["text"][0][:3]) == ["", "", "3.00%"]
        assert [list(row) for row in yearly_trace["z"]] == [[30.0], [-4.0]]

    def test_monthly_and_yearly_color_ranges_are_separate(self) -> None:
        """
        목적: 월별과 연간은 색 범위를 따로 잡고, 각자 0 을 가운데로 대칭이다

        Given: 월별 절댓값 최대 12, 연간 절댓값 최대 30
        When: 히트맵을 만든다
        Then: 월별 칸은 coloraxis(±12), 연간 칸은 coloraxis2(±30)를 쓴다
        """
        # Given
        monthly, yearly = self._returns()

        # When
        fig = build_monthly_heatmap(monthly, yearly).to_dict()

        # Then
        assert [trace["coloraxis"] for trace in fig["data"]] == ["coloraxis", "coloraxis2"]
        layout = fig["layout"]
        assert (layout["coloraxis"]["cmin"], layout["coloraxis"]["cmax"]) == (pytest.approx(-12.0), pytest.approx(12.0))
        assert (layout["coloraxis2"]["cmin"], layout["coloraxis2"]["cmax"]) == (
            pytest.approx(-30.0),
            pytest.approx(30.0),
        )

    def test_missing_yearly_return_stops(self) -> None:
        """
        목적: 월별에 있는 해의 연간 수익률이 없으면 빈 칸으로 넘기지 않고 멈춘다

        Given: 2024 의 연간 수익률이 빠진 결과
        When: 히트맵을 만든다
        Then: KeyError
        """
        # Given
        monthly, yearly = self._returns()
        yearly = [entry for entry in yearly if entry["year"] != 2024]

        # When / Then
        with pytest.raises(KeyError):
            build_monthly_heatmap(monthly, yearly)
