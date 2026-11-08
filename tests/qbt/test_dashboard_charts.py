"""대시보드 차트 생성 테스트

툴팁 · 선 · 마커 · 히트맵 칸의 값이 틀려도 화면은 에러 없이 그려진다.
아래 테스트는 각 값이 «어느 표의 어느 날짜 행»에서 오는지를 고정한다.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

import pandas as pd
import plotly.graph_objects as go
import pytest

from qbt.backtest.constants import KOREAN_DATE_AXIS
from qbt.backtest.dashboard_charts import (
    ChartPane,
    build_concentration_table,
    build_consistency_table,
    build_equity_panes,
    build_monthly_heatmap,
    build_price_pane,
    build_regime_comparison_table,
    build_regime_table,
    build_rolling_chart,
    build_rolling_table,
    build_split_comparison_table,
    build_split_table,
    build_trade_markers,
    build_yearly_contribution_chart,
    chart_component_args,
    signal_chart_title,
    style_period_table,
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


def _traces(fig: go.Figure) -> list[Any]:
    return list(cast(Any, fig.data))


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
            "date": "2024-01-03",
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
        assert _tooltip(pane, 0) == {
            "date": "2024-01-02",
            "open": "100.00",
            "high": "101.00",
            "low": "99.00",
            "close": "100.50",
        }
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


class TestKoreanDates:
    def test_candle_chart_uses_korean_locale(self) -> None:
        """
        목적: 캔들 차트의 눈금 월 이름은 브라우저 언어가 아니라 한글이다

        Given: 시그널 3일
        When: 캔들 패널을 만든다
        Then: 차트 설정의 locale 이 ko-KR 이다
        """
        # Given
        days = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]

        # When
        pane = build_price_pane(_signal_df(days), _signal_df(days), [], title="T")

        # Then
        assert cast(dict[str, Any], pane["chart"]["localization"])["locale"] == "ko-KR"

    def test_plotly_axis_formats_have_no_month_names(self) -> None:
        """
        목적: Plotly 날짜 축은 긴 간격부터 숫자 · 한글 형식을 고른다 — 먼저 맞는 항목을 쓰고 경계가 양쪽에 걸린다

        Given: 날짜 축 설정
        When: 눈금 형식과 정보창 형식을 본다
        Then: 해 → 달 → 일 순서이고 영문 월 이름(%b · %B)이 없다
        """
        # Given
        stops = KOREAN_DATE_AXIS["tickformatstops"]

        # When
        starts = [stop["dtickrange"][0] for stop in stops]
        formats = [stop["value"] for stop in stops] + [KOREAN_DATE_AXIS["hoverformat"]]

        # Then
        assert starts == ["M12", "M1", None]
        assert formats == ["%Y년", "%Y년 %-m월", "%Y-%m-%d", "%Y-%m-%d"]


class TestSignalChartTitle:
    @pytest.mark.parametrize(
        ("trade", "signal", "expected"),
        [
            ("TQQQ", "QQQ", "TQQQ 시그널 차트 (신호: QQQ)"),
            ("QQQ", "QQQ", "QQQ 시그널 차트"),
            ("GLD", None, "GLD 시그널 차트"),
        ],
    )
    def test_signal_ticker_appears_only_when_different(self, trade: str, signal: str | None, expected: str) -> None:
        """
        목적: 캔들이 매매 종목과 다른 시세일 때만 신호 종목을 적는다

        Given: 매매 · 신호 종목
        When: 패널 제목을 만든다
        Then: 다를 때만 「(신호: …)」가 붙는다
        """
        # Given / When
        title = signal_chart_title(trade, signal)

        # Then
        assert title == expected


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
        with_open = build_trade_markers(empty_trades, open_entry_dates=["2024-05-02"])
        without_open = build_trade_markers(empty_trades)

        # Then
        assert [(m["time"], m["text"], m["position"]) for m in with_open] == [("2024-05-02", "Buy (보유중)", "belowBar")]
        assert without_open == []

    def test_every_open_lot_gets_a_marker(self) -> None:
        """
        목적: 스플릿처럼 미청산 진입이 여럿이면 그 수만큼 「Buy (보유중)」 마커를 둔다 — 같은 날이어도 빼지 않는다

        Given: 행이 없는 거래 표와 미청산 진입일 3개 (둘은 같은 날)
        When: 마커를 만든다
        Then: 마커 3개가 입력 순서대로 있다
        """
        # Given
        empty_trades = pd.DataFrame({"entry_date": [], "exit_date": [], "pnl_pct": []})

        # When
        markers = build_trade_markers(empty_trades, open_entry_dates=["2024-05-02", "2024-05-02", "2024-06-03"])

        # Then
        assert [(m["time"], m["text"]) for m in markers] == [
            ("2024-05-02", "Buy (보유중)"),
            ("2024-05-02", "Buy (보유중)"),
            ("2024-06-03", "Buy (보유중)"),
        ]


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


def _split(label: str, cagr: float | None) -> dict[str, Any]:
    return {
        "label": label,
        "start_date": "2000-01-03",
        "end_date": "2010-01-04",
        "cagr": cagr,
        "mdd": None if cagr is None else -10.5,
        "total_return_pct": None if cagr is None else 100.0,
    }


def _regime(label: str, return_pct: float | None, signal: float | None) -> dict[str, Any]:
    return {
        "kind": "하락장",
        "label": label,
        "start_date": "2020-02-19",
        "end_date": "2020-03-23",
        "return_pct": return_pct,
        "mdd": return_pct,
        "signal_return_pct": signal,
    }


def _horizon(years: int, cagrs: list[float]) -> dict[str, Any]:
    return {
        "years": years,
        "points": [{"start_date": f"2000-0{i + 1}-03", "cagr": cagr} for i, cagr in enumerate(cagrs)],
        "count": len(cagrs),
        "min_cagr": min(cagrs) if cagrs else None,
        "min_start_date": "2000-01-03" if cagrs else None,
        "p10_cagr": min(cagrs) if cagrs else None,
        "median_cagr": max(cagrs) if cagrs else None,
        "negative_count": sum(1 for cagr in cagrs if cagr < 0),
    }


_CONCENTRATION: dict[str, Any] = {
    "year_count": 5,
    "positive_years": 3,
    "negative_years": 1,
    "median_pct": 10.0,
    "mean_pct": 14.0,
    "top_years": [2023, 2021, 2020],
    "top3_share_pct": 114.29,
    "mean_without_top3_pct": -2.0,
    "mean_without_top5_pct": 0.0,
}


class TestPeriodTables:
    def test_split_table_shows_period_text_and_missing_values(self) -> None:
        """
        목적: 기간은 「시작 ~ 끝」 한 칸이고, 값이 없는 구간은 빈 값으로 남는다

        Given: 값이 있는 구간과 없는 구간
        When: 표를 만든다
        Then: 기간 표기가 맞고 없는 구간의 연 수익은 결측이다
        """
        # Given
        splits = [_split("전체", 12.5), _split("닷컴 정점부터", None)]

        # When
        table = build_split_table(splits)

        # Then
        assert list(table.columns) == ["구간", "기간", "연 수익 (%)", "최악 낙폭 (%)", "총 수익률 (%)"]
        assert table.loc[0, "기간"] == "2000-01-03 ~ 2010-01-04"
        assert table.loc[0, "연 수익 (%)"] == pytest.approx(12.5, abs=1e-9)
        assert pd.isna(table.loc[1, "연 수익 (%)"])

    def test_numbers_show_two_decimals(self) -> None:
        """
        목적: 표의 숫자는 소수 둘째 자리로 보인다

        Given: 연 수익 12.5 인 표
        When: 표기를 입힌다
        Then: 그려진 HTML 에 12.50 이 있다
        """
        # Given
        table = build_split_table([_split("전체", 12.5)])

        # When
        html = style_period_table(table).to_html()

        # Then
        assert "12.50" in html

    def test_regime_table_has_signal_column_only_with_signal(self) -> None:
        """
        목적: 신호 시세 등락 열은 그 값이 있는 결과(단일 전략)에만 둔다

        Given: 신호가 있는 국면 목록과 없는 국면 목록
        When: 표를 만든다
        Then: 앞의 표에만 신호 열이 있다
        """
        # Given
        with_signal = [_regime("코로나", -25.0, -50.0)]
        without_signal = [_regime("코로나", -25.0, None)]

        # When
        first, second = build_regime_table(with_signal), build_regime_table(without_signal)

        # Then
        assert ("신호 시세 등락 (%)" in first.columns, "신호 시세 등락 (%)" in second.columns) == (True, False)
        assert first.loc[0, "종류"] == "하락장"

    def test_rolling_table_values(self) -> None:
        """
        목적: 보유 기간마다 요약 한 줄이다

        Given: 5년 · 10년 요약
        When: 표를 만든다
        Then: 두 줄이고 마이너스 횟수가 그대로다
        """
        # Given
        rolling = [_horizon(5, [-1.0, 3.0]), _horizon(10, [2.0])]

        # When
        table = build_rolling_table(rolling)

        # Then
        assert table["보유 기간"].tolist() == ["5년", "10년"]
        assert table["마이너스 횟수"].tolist() == [1, 0]

    def test_concentration_table_joins_top_years(self) -> None:
        """
        목적: 최고 3개 해는 한 칸에 이어 적는다

        Given: 쏠림 값
        When: 표를 만든다
        Then: 한 줄이고 해가 순위대로 이어진다
        """
        # Given / When
        table = build_concentration_table(_CONCENTRATION)

        # Then
        assert len(table) == 1
        assert table.loc[0, "최고 3개 해"] == "2023 · 2021 · 2020"

    def test_comparison_tables_have_one_row_per_experiment(self) -> None:
        """
        목적: 비교 표는 실험마다 한 줄이고 칸은 구간 · 국면 이름이다

        Given: 두 실험의 구간별 성과
        When: 세 비교 표를 만든다
        Then: 값이 실험 · 구간에 맞게 들어간다
        """
        # Given
        perf_a = {
            "splits": [_split("전체", 12.5)],
            "regimes": [_regime("코로나", -25.0, None)],
            "rolling": [_horizon(5, [-1.0, 3.0])],
            "concentration": _CONCENTRATION,
        }
        perf_b = {
            "splits": [_split("전체", 8.0)],
            "regimes": [_regime("코로나", -5.0, None)],
            "rolling": [_horizon(5, [2.0])],
            "concentration": {**_CONCENTRATION, "top3_share_pct": None},
        }
        named = [("A", perf_a), ("B", perf_b)]

        # When
        cagr = build_split_comparison_table(named, "cagr")
        regimes = build_regime_comparison_table(named)
        consistency = build_consistency_table(named)

        # Then
        assert cagr["전체"].tolist() == pytest.approx([12.5, 8.0], abs=1e-9)
        assert regimes["코로나"].tolist() == pytest.approx([-25.0, -5.0], abs=1e-9)
        assert consistency["5년 보유 마이너스 횟수"].tolist() == ["1 / 2", "0 / 1"]
        assert pd.isna(consistency.loc[1, "최고 3개 해의 몫 (%)"])


class TestPeriodCharts:
    def test_more_horizons_than_colors_still_draws(self) -> None:
        """
        목적: 보유 햇수를 늘려도 대시보드가 멈추지 않는다 — 색 수에 보유 햇수 수가 묶이지 않는다

        Given: 세 가지 보유 햇수 (준비한 색은 둘)
        When: 그림을 만든다
        Then: 선이 셋이다
        """
        # Given
        rolling = [_horizon(3, [1.0]), _horizon(5, [2.0]), _horizon(10, [3.0])]

        # When
        fig = build_rolling_chart(rolling)

        # Then
        assert [trace.name for trace in _traces(fig)] == ["3년 보유", "5년 보유", "10년 보유"]

    def test_rolling_chart_skips_empty_horizon(self) -> None:
        """
        목적: 경우가 없는 보유 기간은 빈 선을 그리지 않고, 가로축은 한글 날짜 형식이다

        Given: 5년만 경우가 있는 결과
        When: 그림을 만든다
        Then: 선은 하나고 눈금 형식이 날짜 축 설정과 같다
        """
        # Given
        rolling = [_horizon(5, [-1.0, 3.0]), _horizon(10, [])]

        # When
        fig = build_rolling_chart(rolling)

        # Then
        assert [trace.name for trace in _traces(fig)] == ["5년 보유"]
        assert list(_traces(fig)[0].y) == pytest.approx([-1.0, 3.0], abs=1e-9)
        assert fig.layout.xaxis.hoverformat == "%Y-%m-%d"
        assert fig.layout.xaxis.tickformatstops[0].value == "%Y년"

    @staticmethod
    def _yearly(other: float) -> list[dict[str, Any]]:
        return [
            {"year": 2020, "return_pct": 20.0, "assets": {"a": 15.0, "b": 5.0}, "other_pct": 0.0},
            {"year": 2021, "return_pct": -10.0, "assets": {"a": -7.5, "b": -2.5}, "other_pct": other},
        ]

    def test_contribution_bars_follow_asset_colors(self) -> None:
        """
        목적: 자산별 막대는 넘겨받은 색을 쓰고(비중 그림과 같은 색), 위아래로 나뉘어 쌓인다. 반올림 잔여뿐이면 기타를 그리지 않는다

        Given: 자산 둘의 기여, 기타 0
        When: 그림을 만든다
        Then: 막대 둘 + 그해 수익률 점이고 색이 지정한 값이다
        """
        # Given
        colors = {"a": "#111111", "b": "#222222"}

        # When
        fig = build_yearly_contribution_chart(self._yearly(0.0), colors)

        # Then
        assert [trace.name for trace in _traces(fig)] == ["A", "B", "그해 수익률"]
        assert [_traces(fig)[0].marker.color, _traces(fig)[1].marker.color] == ["#111111", "#222222"]
        assert list(_traces(fig)[0].y) == pytest.approx([15.0, -7.5], abs=1e-9)
        assert fig.layout.barmode == "relative"

    def test_other_bar_appears_when_some_profit_is_unattributed(self) -> None:
        """
        목적: 자산에 나뉘지 않은 몫이 있으면 기타 막대로 보인다 — 막대 합이 그해 수익률과 맞게

        Given: 기타 +3 인 해가 있는 결과
        When: 그림을 만든다
        Then: 기타 막대가 있다
        """
        # Given / When
        fig = build_yearly_contribution_chart(self._yearly(3.0), {"a": "#111111", "b": "#222222"})

        # Then
        assert "기타" in [trace.name for trace in _traces(fig)]
