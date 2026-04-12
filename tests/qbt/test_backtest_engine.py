"""백테스트 엔진(backtest_engine.py) 계약 테스트

params_schedule 전환 로직, filter_valid_rows 헬퍼 함수의 계약을 고정한다.
"""

from datetime import date

import pandas as pd

from qbt.backtest.constants import ma_col_name
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_OPEN


class TestFilterValidRows:
    """filter_valid_rows 헬퍼 함수 계약 테스트."""

    def test_filter_valid_rows_removes_nan(self) -> None:
        """
        목적: MA NaN 행이 제거되고 signal/trade가 동일 행수를 유지하는지 검증

        Given: signal_df에 ma_200 컬럼이 있고 앞 3행이 NaN
        When: filter_valid_rows(signal_df, trade_df, "ma_200") 호출
        Then: 반환된 두 DataFrame의 행수가 동일하고 NaN 행이 제거됨
        """
        # Given
        dates = [date(2020, 1, i) for i in range(1, 8)]
        ma_col = ma_col_name(200)

        signal_df = pd.DataFrame(
            {
                COL_DATE: dates,
                COL_CLOSE: [100.0] * 7,
                ma_col: [None, None, None, 100.0, 101.0, 102.0, 103.0],
            }
        )
        trade_df = pd.DataFrame(
            {
                COL_DATE: dates,
                COL_OPEN: [99.0] * 7,
                COL_CLOSE: [100.0] * 7,
            }
        )

        # When
        from qbt.backtest.engines.backtest_engine import filter_valid_rows

        filtered_signal, filtered_trade = filter_valid_rows(signal_df, trade_df, ma_col)

        # Then
        assert len(filtered_signal) == 4, "NaN 3행 제거 후 4행 남아야 함"
        assert len(filtered_trade) == 4, "trade_df도 동일 행수"
        assert filtered_signal[ma_col].isna().sum() == 0, "NaN이 없어야 함"
        assert filtered_signal.index.tolist() == [0, 1, 2, 3], "인덱스가 재설정되어야 함"

    def test_filter_valid_rows_all_valid(self) -> None:
        """
        목적: 모든 행이 유효하면 원본과 동일한 행수를 반환하는지 검증

        Given: signal_df의 ma_200 컬럼에 NaN 없음
        When: filter_valid_rows 호출
        Then: 원본과 동일한 행수
        """
        # Given
        dates = [date(2020, 1, i) for i in range(1, 5)]
        ma_col = ma_col_name(200)

        signal_df = pd.DataFrame(
            {
                COL_DATE: dates,
                COL_CLOSE: [100.0] * 4,
                ma_col: [100.0, 101.0, 102.0, 103.0],
            }
        )
        trade_df = pd.DataFrame(
            {
                COL_DATE: dates,
                COL_OPEN: [99.0] * 4,
                COL_CLOSE: [100.0] * 4,
            }
        )

        # When
        from qbt.backtest.engines.backtest_engine import filter_valid_rows

        filtered_signal, filtered_trade = filter_valid_rows(signal_df, trade_df, ma_col)

        # Then
        assert len(filtered_signal) == 4
        assert len(filtered_trade) == 4


class TestParamsScheduleWhile:
    """params_schedule 전환 로직 계약 테스트."""

    def test_params_schedule_skips_multiple_dates(self) -> None:
        """
        목적: 데이터 갭으로 2개 이상의 전환 날짜를 건너뛸 때
              최종 전략만 적용되는지 검증

        Given: 3개의 전환 날짜(1/5, 1/10, 1/15)와
               1/5~1/9 사이 데이터가 없는 signal/trade DataFrame.
               첫 데이터가 1/1, 그 다음 1/12에 재개.
        When: run_backtest()를 params_schedule과 함께 호출
        Then: 1/12 시점에서 1/5, 1/10 전환을 모두 건너뛰고
              1/10의 전략이 적용됨 (1/15 전략은 아직 미적용)

        이 테스트는 현재 `if` 로직에서는 1/5 전략만 적용되어 실패하고,
        `while` 루프로 변경 후에야 통과한다.
        """
        # Given: 간단한 mock 전략으로 검증
        # 데이터 갭이 있는 시나리오: 1/1~1/4 정상, 1/5~1/11 갭, 1/12~1/20 재개
        from unittest.mock import MagicMock

        from qbt.backtest.engines.backtest_engine import run_backtest
        from qbt.backtest.strategies.strategy_common import SignalStrategy

        dates = [date(2020, 1, d) for d in range(1, 5)] + [  # 1/1~1/4
            date(2020, 1, d) for d in range(12, 21)
        ]  # 1/12~1/20 (갭 후 재개)
        n = len(dates)

        signal_df = pd.DataFrame(
            {
                COL_DATE: dates,
                COL_CLOSE: [100.0] * n,
            }
        )
        trade_df = pd.DataFrame(
            {
                COL_DATE: dates,
                COL_OPEN: [100.0] * n,
                COL_CLOSE: [100.0] * n,
            }
        )

        # 3개 전략 생성 (각각 check_buy=False, check_sell=False)
        def make_mock_strategy(name: str) -> SignalStrategy:
            s = MagicMock(spec=SignalStrategy)
            s.check_buy.return_value = False
            s.check_sell.return_value = False
            s._name = name
            return s

        strategy_initial = make_mock_strategy("initial")
        strategy_jan5 = make_mock_strategy("jan5")
        strategy_jan10 = make_mock_strategy("jan10")
        strategy_jan15 = make_mock_strategy("jan15")

        params_schedule = {
            date(2020, 1, 5): strategy_jan5,
            date(2020, 1, 10): strategy_jan10,
            date(2020, 1, 15): strategy_jan15,
        }

        # When
        run_backtest(
            strategy_initial,
            signal_df,
            trade_df,
            initial_capital=10_000_000.0,
            log_trades=False,
            params_schedule=params_schedule,
        )

        # Then: 1/12일 시점에서 strategy_jan10이 적용되어야 함
        # 1/12~1/14는 strategy_jan10이 사용됨 (check_buy/check_sell 호출)
        # 1/15~1/20은 strategy_jan15가 사용됨

        # strategy_jan5는 1/5~1/9 사이에 적용되어야 하지만 데이터 없으므로
        # check_buy/check_sell이 호출되지 않아야 함
        assert (
            strategy_jan5.check_buy.call_count == 0  # pyright: ignore[reportAttributeAccessIssue]
        ), "데이터 갭으로 건너뛴 jan5 전략은 호출되지 않아야 함"

        # strategy_jan10은 1/12~1/14 (3일) 동안 호출되어야 함
        assert (
            strategy_jan10.check_buy.call_count > 0  # pyright: ignore[reportAttributeAccessIssue]
        ), "while 루프로 1/10 전환을 건너뛴 후 jan10 전략이 적용되어야 함"

        # strategy_jan15는 1/15~1/20 (6일) 동안 호출되어야 함
        assert (
            strategy_jan15.check_buy.call_count > 0  # pyright: ignore[reportAttributeAccessIssue]
        ), "1/15 이후 jan15 전략이 적용되어야 함"
