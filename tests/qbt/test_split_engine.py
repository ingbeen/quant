"""
backtest/engines/split_engine 모듈과 스플릿 매매 설정 테스트

이 파일은 무엇을 검증하나요?
1. 칸 가격: 고점 × 0.95^회차 매수, 앞 칸 매수가 매도, 깊은 칸부터 팔림
2. 장중 지정가 체결과 시가 갭, 같은 날 순서(캔들 방향)
3. 사이클 복리 칸 금액, 고점 갱신, 칸 한도
4. 에쿼티 · 미청산 칸 · 설정 표

왜 중요한가요?
스플릿은 단일 포지션 엔진을 쓰지 않는 유일한 전략이고, 일봉에서 장중 순서를 가정한다.
체결 순서와 칸 금액이 결과를 바꾸므로 손으로 계산한 작은 표로 고정한다.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest import runners
from qbt.backtest.engines.split_engine import run_split_backtest
from qbt.backtest.strategies import buffer_zone, buffer_zone_v2, buy_and_hold, split_ladder
from qbt.backtest.types import SummaryDict
from qbt.common_constants import TQQQ_SYNTHETIC_DATA_PATH

CAPITAL = 30_000.0
DROP = 0.05


def _bars(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """(시가, 고가, 저가, 종가) 일봉 표."""
    return pd.DataFrame(
        {
            "Date": [date(2024, 1, 1) + timedelta(days=i) for i in range(len(rows))],
            "Open": [r[0] for r in rows],
            "High": [r[1] for r in rows],
            "Low": [r[2] for r in rows],
            "Close": [r[3] for r in rows],
        }
    )


def _flat(close: float) -> tuple[float, float, float, float]:
    return (close, close, close, close)


def _open_entry_prices(summary: SummaryDict) -> list[float]:
    return [lot["entry_price"] for lot in summary.get("open_lots", [])]


class TestLadderPrices:
    """100 기준 칸 가격 95 · 90.25 · 85.7375."""

    def test_buys_fill_at_ladder_prices_in_order(self) -> None:
        """
        목적: 저가가 칸 가격에 닿으면 그 가격에 사고(슬리피지 포함), 다음 칸은 앞 칸의 5% 아래다

        Given: 첫날 종가 100, 날마다 저가가 다음 칸까지만 내려간다
        When: 백테스트
        Then: 미청산 칸의 진입가 95 · 90.25 · 85.7375 × 1.003, 주수는 칸 금액 1,000 을 그 진입가로 나눠 내림
        """
        # Given
        df = _bars([_flat(100.0), (99.0, 99.0, 94.0, 94.0), (93.0, 93.0, 90.0, 90.0), (89.0, 89.0, 85.0, 86.0)])

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert trades_df.empty
        lots = summary.get("open_lots", [])
        assert [lot["entry_price"] for lot in lots] == pytest.approx([95.285, 90.5208, 85.9947], abs=1e-4)
        assert [lot["shares"] for lot in lots] == [
            int(1000 / 95.285),
            int(1000 / 90.52075),
            int(1000 / 85.9947125),
        ]
        assert [lot["entry_date"] for lot in lots] == ["2024-01-02", "2024-01-03", "2024-01-04"]

    def test_sells_at_previous_buy_price_deepest_first(self) -> None:
        """
        목적: 매도가는 앞 칸의 매수가이고 깊은 칸부터 팔린다 — 90.25 에 산 칸은 95, 95 에 산 칸은 100

        Given: 95 · 90.25 를 산 뒤 고가가 95 까지, 이어서 100 까지 오른다
        When: 백테스트
        Then: 거래 순서가 2번째 칸 → 1번째 칸, 청산가 95 · 100 × 0.997
        """
        # Given
        df = _bars(
            [
                _flat(100.0),
                (99.0, 99.0, 94.0, 94.0),
                (93.0, 93.0, 90.0, 90.0),
                (91.0, 96.0, 91.0, 95.5),
                (96.0, 101.0, 96.0, 99.0),
            ]
        )

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert trades_df["entry_price"].tolist() == pytest.approx([90.52075, 95.285], abs=1e-9)
        assert trades_df["exit_price"].tolist() == pytest.approx([94.715, 99.7], abs=1e-9)
        assert trades_df["exit_date"].tolist() == [date(2024, 1, 4), date(2024, 1, 5)]
        assert "open_lots" not in summary

    def test_first_day_does_not_trade(self) -> None:
        """
        목적: 첫날은 고점만 기록한다 — 그날 범위가 칸 가격을 지나도 매매하지 않는다 (경계)

        Given: 첫날 시가 · 저가가 종가보다 훨씬 아래
        When: 백테스트
        Then: 거래 · 미청산 없음
        """
        # Given
        df = _bars([(50.0, 100.0, 50.0, 100.0), _flat(99.0)])

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert trades_df.empty
        assert "open_lots" not in summary

    def test_thirtieth_lot_price_and_its_sell_target(self) -> None:
        """
        목적: 100 기준 30회차는 21.4639 에 사고 29회차 가격 22.59355 까지 버틴다 (요청의 값)

        Given: 하루에 30칸을 다 사는 하락, 다음 날 고가 22.6
        When: 칸 한도 30 으로 백테스트
        Then: 깊은 칸 진입가 21.4639 × 1.003, 그 칸만 22.59355 × 0.997 에 팔림
        """
        # Given
        df = _bars([_flat(100.0), (100.0, 100.0, 20.0, 20.0), (21.0, 22.6, 21.0, 22.0)])

        # When
        trades_df, _, summary = run_split_backtest(df, 3_000_000.0, DROP, 30)

        # Then
        assert len(summary.get("open_lots", [])) == 29
        assert trades_df["entry_price"].iloc[0] == pytest.approx(21.5283, abs=1e-3)
        assert trades_df["exit_price"].iloc[0] == pytest.approx(22.5258, abs=1e-3)
        assert len(trades_df) == 1


class TestGapFills:
    def test_gap_down_fills_at_open_and_keeps_ladder(self) -> None:
        """
        목적: 시가가 칸 가격을 건너뛰면 시가에 사고, 다음 칸 가격과 매도가는 원래 사다리 그대로다

        Given: 시가 93 (95 아래), 다음 날 저가 90 (90.25 도달), 그 다음 날 고가 95.5
        When: 백테스트
        Then: 첫 칸 93 × 1.003, 둘째 칸 90.25 × 1.003 진입 뒤 95 × 0.997 청산 (93 기준 사슬이 아니다)
        """
        # Given
        df = _bars(
            [
                _flat(100.0),
                (93.0, 93.0, 92.0, 92.0),
                (91.0, 91.0, 90.0, 90.0),
                (91.0, 95.5, 91.0, 92.0),
            ]
        )

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert _open_entry_prices(summary) == pytest.approx([93.279], abs=1e-4)
        assert trades_df["entry_price"].iloc[0] == pytest.approx(90.52075, abs=1e-9)
        assert trades_df["exit_price"].iloc[0] == pytest.approx(94.715, abs=1e-9)

    def test_gap_down_through_several_lots(self) -> None:
        """
        목적: 시가가 여러 칸을 건너뛰면 그 칸들을 모두 시가에 산다

        Given: 시가 88 (95 · 90.25 아래, 85.7375 위)
        When: 백테스트
        Then: 두 칸 모두 88 × 1.003
        """
        # Given
        df = _bars([_flat(100.0), _flat(88.0)])

        # When
        _, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert _open_entry_prices(summary) == pytest.approx([88.264, 88.264], abs=1e-4)

    def test_gap_up_sells_at_open(self) -> None:
        """
        목적: 시가가 매도가를 건너뛰면 시가에 판다

        Given: 95 · 90.25 보유, 시가 97 (95 위, 100 아래)
        When: 백테스트
        Then: 깊은 칸만 97 × 0.997
        """
        # Given
        df = _bars(
            [
                _flat(100.0),
                (99.0, 99.0, 94.0, 94.0),
                (93.0, 93.0, 90.0, 90.0),
                _flat(97.0),
            ]
        )

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert len(trades_df) == 1
        assert trades_df["exit_price"].iloc[0] == pytest.approx(96.709, abs=1e-9)
        assert len(summary.get("open_lots", [])) == 1


class TestSameDayOrder:
    """양봉은 시가 → 저가 → 고가 → 종가, 음봉은 시가 → 고가 → 저가 → 종가."""

    def test_bull_candle_touches_low_first(self) -> None:
        """
        목적: 양봉은 저가가 먼저다 — 그날 95 에 사서 100 에 판다 (같은 날 왕복)

        Given: 시가 96, 저가 94, 고가 101, 종가 100 (양봉)
        When: 백테스트
        Then: 거래 1건, 진입일 = 청산일, 미청산 없음
        """
        # Given
        df = _bars([_flat(100.0), (96.0, 101.0, 94.0, 100.0)])

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert len(trades_df) == 1
        assert trades_df["entry_date"].iloc[0] == trades_df["exit_date"].iloc[0]
        assert "open_lots" not in summary

    def test_bear_candle_touches_high_first(self) -> None:
        """
        목적: 음봉은 고가가 먼저다 — 고가 101 은 산 칸이 없을 때 지나가므로 그날 팔지 않는다

        Given: 시가 99, 고가 101, 저가 94, 종가 96 (음봉). 위 양봉과 고가 · 저가가 같다
        When: 백테스트
        Then: 거래 0건, 미청산 1칸
        """
        # Given
        df = _bars([_flat(100.0), (99.0, 101.0, 94.0, 96.0)])

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert trades_df.empty
        assert len(summary.get("open_lots", [])) == 1

    def test_doji_counts_as_bull_candle(self) -> None:
        """
        목적: 시가 = 종가는 양봉으로 친다 (경계)

        Given: 시가 96, 종가 96, 저가 94, 고가 101
        When: 백테스트
        Then: 같은 날 왕복 1건
        """
        # Given
        df = _bars([_flat(100.0), (96.0, 101.0, 94.0, 96.0)])

        # When
        trades_df, _, _ = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert len(trades_df) == 1

    def test_bear_candle_sells_on_the_way_to_close(self) -> None:
        """
        목적: 음봉의 저가 → 종가 구간에서도 매도가에 닿으면 판다

        Given: 빈 상태에서 음봉 시가 97 · 고가 97 · 저가 90 · 종가 95.5.
               저가에서 95 · 90.25 를 사고, 종가로 오르며 95 에 둘째 칸을 판다
        When: 백테스트
        Then: 거래 1건(청산가 95 × 0.997), 미청산 1칸
        """
        # Given
        df = _bars([_flat(100.0), (97.0, 97.0, 90.0, 95.5)])

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert trades_df["exit_price"].tolist() == pytest.approx([94.715], abs=1e-9)
        assert len(summary.get("open_lots", [])) == 1


class TestLotLimit:
    def test_no_more_buys_after_limit_and_no_stop(self) -> None:
        """
        목적: 칸이 다 차면 더 떨어져도 사지도 팔지도 않는다 — 그냥 둔다

        Given: 칸 한도 2, 가격이 80 까지 하락
        When: 백테스트
        Then: 미청산 2칸, 거래 0건
        """
        # Given
        df = _bars([_flat(100.0), _flat(80.0), _flat(70.0)])

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 2)

        # Then
        assert trades_df.empty
        assert len(summary.get("open_lots", [])) == 2


class TestCycleSizing:
    def test_lot_amount_is_fixed_within_a_cycle(self) -> None:
        """
        목적: 사이클 안에서는 칸 금액이 고정이다 — 둘째 칸의 왕복 이익이 다음 매수 금액에 들어가지 않는다

        Given: 자본 300,000 · 칸 3 (칸 금액 100,000). 95 · 90.25 를 사고 둘째 칸을 95 에 판 뒤 90.25 에 다시 산다
        When: 백테스트
        Then: 다시 산 둘째 칸의 주수가 처음과 같다 1,104 (남은 현금 ÷ 남은 칸이면 1,130)
        """
        # Given
        df = _bars(
            [
                _flat(100.0),
                (99.0, 99.0, 94.0, 94.0),
                (93.0, 93.0, 90.0, 90.0),
                (91.0, 96.0, 91.0, 95.5),
                (93.0, 93.0, 90.0, 90.0),
            ]
        )

        # When
        trades_df, _, summary = run_split_backtest(df, 300_000.0, DROP, 3)

        # Then
        assert trades_df["shares"].iloc[0] == 1104
        assert [lot["shares"] for lot in summary.get("open_lots", [])] == [1049, 1104]

    def test_lot_amount_resets_when_all_lots_are_sold(self) -> None:
        """
        목적: 칸이 모두 비면 그때 자산 ÷ 칸 수로 칸 금액을 다시 정한다

        Given: 자본 30,000 · 칸 3. 95 에 104주 사서 100 에 판 뒤(현금 30,459.16) 다시 95 에 산다
        When: 백테스트
        Then: 다시 산 칸의 주수 int(10,153.05 / 95.285) = 106
        """
        # Given
        df = _bars(
            [
                _flat(100.0),
                (99.0, 99.0, 94.0, 94.0),
                (96.0, 100.0, 96.0, 99.0),
                (97.0, 97.0, 94.0, 94.0),
            ]
        )

        # When
        trades_df, _, summary = run_split_backtest(df, CAPITAL, DROP, 3)

        # Then
        assert trades_df["shares"].tolist() == [104]
        assert [lot["shares"] for lot in summary.get("open_lots", [])] == [106]

    def test_too_small_amount_skips_no_lot_and_retries(self) -> None:
        """
        목적: 칸 금액으로 1주도 못 사면 그 칸을 건너뛰지 않고 다음 기회에 같은 칸부터 다시 산다 (경계)

        Given: 칸 금액 10. 첫 하락 95 에서는 못 사고, 다음 날 시가 9 에 칸 순서대로 산다
        When: 칸 한도 3 으로 백테스트
        Then: 첫 날은 0칸, 끝에 3칸 모두 9 × 1.003
        """
        # Given
        df = _bars([_flat(100.0), _flat(94.0), _flat(9.0)])

        # When
        _, equity_df, summary = run_split_backtest(df, 30.0, DROP, 3)

        # Then
        assert equity_df["position"].tolist() == [0, 0, 3]
        assert _open_entry_prices(summary) == pytest.approx([9.027, 9.027, 9.027], abs=1e-4)


class TestAnchor:
    def test_anchor_follows_closing_high_not_intraday_high(self) -> None:
        """
        목적: 고점은 종가 기준이다 — 고가 120 이어도 종가 110 이 고점이다

        Given: 빈 상태에서 고가 120 · 종가 110, 다음 날 저가 106
        When: 백테스트
        Then: 첫 칸은 104.5 라 사지 않는다 (고가 기준이면 114 에 샀다)
        """
        # Given
        df = _bars([_flat(100.0), (105.0, 120.0, 105.0, 110.0), (107.0, 107.0, 106.0, 106.0)])

        # When
        _, equity_df, _ = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert equity_df["position"].iloc[-1] == 0

    def test_new_high_moves_ladder_and_old_high_stays_otherwise(self) -> None:
        """
        목적: 빈 상태의 새 최고 종가가 사다리를 옮기고, 그 뒤 낮은 종가는 고점을 내리지 않는다

        Given: 100 → 110 → 106 → 저가 104 (110 기준 첫 칸 104.5)
        When: 백테스트
        Then: 진입가 104.5 × 1.003
        """
        # Given
        df = _bars([_flat(100.0), _flat(110.0), _flat(106.0), (105.0, 105.0, 104.0, 104.0)])

        # When
        _, _, summary = run_split_backtest(df, CAPITAL, DROP, 30)

        # Then
        assert _open_entry_prices(summary) == pytest.approx([104.8135], abs=1e-4)


class TestEquityAndValidation:
    def test_equity_is_cash_plus_shares_at_close(self) -> None:
        """
        목적: 에쿼티는 시세 행마다 있고 현금 + 보유 주수 × 종가다

        Given: 첫날 종가 100, 둘째 날 95 에 104주(비용 9,909.64), 종가 94
        When: 백테스트
        Then: 2행, 첫 행 30,000, 둘째 행 20,090.36 + 104 × 94 = 29,866.36, 포지션 104
        """
        # Given
        df = _bars([_flat(100.0), (99.0, 99.0, 94.0, 94.0)])

        # When
        _, equity_df, _ = run_split_backtest(df, CAPITAL, DROP, 3)

        # Then
        assert equity_df["Date"].tolist() == df["Date"].tolist()
        assert equity_df["equity"].tolist() == pytest.approx([30000.0, 29866.36], abs=0.01)
        assert equity_df["position"].tolist() == [0, 104]

    def test_input_df_is_not_changed(self) -> None:
        """
        목적: 입력 시세를 바꾸지 않는다

        Given: 일봉 표와 사본
        When: 백테스트
        Then: 표가 사본과 같다
        """
        # Given
        df = _bars([_flat(100.0), (99.0, 99.0, 94.0, 94.0)])
        before = df.copy()

        # When
        run_split_backtest(df, CAPITAL, DROP, 3)

        # Then
        pd.testing.assert_frame_equal(df, before)

    @pytest.mark.parametrize(
        ("drop_pct", "max_lots", "message"),
        [
            (0.0, 3, "drop_pct"),
            (1.0, 3, "drop_pct"),
            (float("nan"), 3, "drop_pct"),
            (0.05, 0, "max_lots"),
        ],
    )
    def test_out_of_range_params_raise(self, drop_pct: float, max_lots: int, message: str) -> None:
        """
        목적: 범위 밖 파라미터는 즉시 멈춘다

        Given: 하나만 범위 밖인 파라미터
        When: 백테스트
        Then: 그 파라미터 이름이 든 ValueError
        """
        df = _bars([_flat(100.0), _flat(99.0)])

        with pytest.raises(ValueError, match=message):
            run_split_backtest(df, CAPITAL, drop_pct, max_lots)

    def test_too_few_rows_raise(self) -> None:
        """
        목적: 첫날 하루뿐이면 멈춘다 (경계)

        Given: 1행
        When: 백테스트
        Then: ValueError
        """
        with pytest.raises(ValueError, match="데이터 부족"):
            run_split_backtest(_bars([_flat(100.0)]), CAPITAL, DROP, 3)

    def test_missing_column_raises(self) -> None:
        """
        목적: 장중 체결에 저가 · 고가가 필요하다

        Given: Low 열이 없는 표
        When: 백테스트
        Then: Low 가 든 ValueError
        """
        df = _bars([_flat(100.0), _flat(99.0)]).drop(columns=["Low"])

        with pytest.raises(ValueError, match="Low"):
            run_split_backtest(df, CAPITAL, DROP, 3)


class TestRunnerAndConfigs:
    def test_start_date_cuts_data_and_resets_anchor(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        목적: 시작일 전 시세는 고점에 쓰지 않는다 — 옛 고점을 이어받으면 첫날 칸이 다 찬다

        Given: 2003년 종가 1000, 2004-01-02 부터 종가 10 · 10.
        When: 시작일 2004-01-01 러너 실행
        Then: 표가 2004-01-02 에서 시작하고 매매가 없다
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2003, 12, 30), date(2004, 1, 2), date(2004, 1, 5)],
                "Open": [1000.0, 10.0, 10.0],
                "High": [1000.0, 10.0, 10.0],
                "Low": [1000.0, 10.0, 10.0],
                "Close": [1000.0, 10.0, 10.0],
                "Volume": [1, 1, 1],
            }
        )
        config = split_ladder.SplitLadderConfig(
            strategy_name="split_test",
            display_name="스플릿 (테스트)",
            data_path=Path("dummy.csv"),
            result_dir=tmp_path / "split",
            start_date=date(2004, 1, 1),
        )
        monkeypatch.setattr(runners, "load_stock_data", lambda _path: df.copy())

        # When
        result = runners.create_split_runner(config)()

        # Then
        assert result.signal_df["Date"].tolist() == [date(2004, 1, 2), date(2004, 1, 5)]
        assert result.equity_df["position"].tolist() == [0, 0]
        assert result.signal_df.columns.tolist() == ["Date", "Open", "High", "Low", "Close"]
        assert result.params_json["start_date"] == "2004-01-01"
        assert result.params_json["max_lots"] == 30

    def test_policy_values(self) -> None:
        """
        목적: 하락 폭과 칸 수를 고정한다 — 정책 값이라 숫자로 쓴다

        Given: 상수와 설정 표
        When: 값을 읽는다
        Then: 5% · 30칸, 합성 TQQQ 전 구간과 2004년 시작
        """
        assert split_ladder.SPLIT_DROP_PCT == 0.05
        assert split_ladder.SPLIT_MAX_LOTS == 30
        assert {c.strategy_name: (c.data_path, c.start_date) for c in split_ladder.CONFIGS} == {
            "split_tqqq": (TQQQ_SYNTHETIC_DATA_PATH, None),
            "split_tqqq_2004": (TQQQ_SYNTHETIC_DATA_PATH, date(2004, 1, 1)),
        }

    def test_all_strategy_lists_are_unique_and_complete(self) -> None:
        """
        목적: 러너 등록 표는 이름 딕셔너리라 겹치면 조용히 덮어쓴다 — 네 목록을 합쳐 이름 · 결과 폴더를 고정한다

        Given: 버퍼존 · V2 · 스플릿 · Buy & Hold 설정 목록
        When: 이름과 결과 폴더를 모은다
        Then: 18개 이름이 요청과 같고 UGL · UBT 가 없으며 결과 폴더가 겹치지 않는다
        """
        # Given
        configs = [*buffer_zone.CONFIGS, *buffer_zone_v2.CONFIGS, *split_ladder.CONFIGS, *buy_and_hold.CONFIGS]

        # When
        names = [c.strategy_name for c in configs]
        result_dirs = [c.result_dir for c in configs]

        # Then
        assert len(names) == len(set(names))
        assert len(result_dirs) == len(set(result_dirs))
        assert set(names) == {
            "buffer_zone_tqqq",
            "buffer_zone_qqq",
            "buffer_zone_spy",
            "buffer_zone_gld",
            "buffer_zone_tlt",
            "buffer_zone_qld",
            "buffer_zone_v2_qqq",
            "buffer_zone_v2_qld",
            "buffer_zone_v2_tqqq",
            "buffer_zone_v2_gld",
            "buffer_zone_v2_tlt",
            "split_tqqq",
            "split_tqqq_2004",
            "buy_and_hold_qqq",
            "buy_and_hold_tqqq",
            "buy_and_hold_gld",
            "buy_and_hold_tlt",
            "buy_and_hold_qld",
        }
