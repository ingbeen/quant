"""버퍼존 듀얼 티커 전략 테스트

QQQ 시그널 + TQQQ 매매 조합의 듀얼 티커 전략 계약을 검증한다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.engines.backtest_engine import run_buffer_strategy
from qbt.backtest.strategies.buffer_zone import BufferStrategyParams


class TestDualTickerStrategy:
    """듀얼 티커 전략 테스트 (QQQ 시그널 + TQQQ 매매)

    목적: signal_df와 trade_df 분리가 올바르게 동작하는지 검증
    배경: QQQ로 시그널 생성, TQQQ로 실제 매수/매도 수행
    """

    def test_signal_from_signal_df_trade_from_trade_df(self):
        """
        시그널은 signal_df, 체결은 trade_df 사용 검증

        Given:
          - signal_df(QQQ): 3일째 상향돌파 (종가 > 상단밴드)
          - trade_df(TQQQ): signal_df와 다른 가격 (3배 레버리지 수준)
        When: run_buffer_strategy(signal_df, trade_df, params)
        Then:
          - 3일째(인덱스 2): position=0 (시그널만, 미체결)
          - 4일째(인덱스 3): position>0 (trade_df 시가로 체결)
          - 체결 가격은 trade_df의 Open 기반 (signal_df의 Open이 아님)
        """
        # Given: signal_df (QQQ) - 3일째에 상향돌파
        signal_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100, 100, 100, 105, 110, 110, 110, 110, 110, 110],
                "Close": [100, 100, 107, 110, 112, 112, 112, 112, 112, 112],
                "ma_5": [100, 100, 100, 103, 106, 108, 109, 110, 110.5, 111],
            }
        )

        # trade_df (TQQQ) - 같은 날짜, 다른 가격 (대략 3배 변동)
        trade_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [50, 50, 50, 65, 80, 80, 80, 80, 80, 80],
                "Close": [50, 50, 71, 80, 86, 86, 86, 86, 86, 86],
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(signal_df, trade_df, params, log_trades=False)

        # Then: 체결 타이밍 검증
        assert len(equity_df) >= 4, "에쿼티 기록이 4일 이상이어야 함"

        # 신호일(3일째, 인덱스 2) - 아직 포지션 없어야 함
        signal_day = equity_df.iloc[2]
        assert signal_day["position"] == 0, f"신호일에는 position=0이어야 함, 실제: {signal_day['position']}"

        # 체결일(4일째, 인덱스 3) - trade_df 시가로 체결
        execution_day = equity_df.iloc[3]
        assert execution_day["position"] > 0, f"체결일에는 position>0이어야 함, 실제: {execution_day['position']}"

        # 체결 가격이 trade_df의 Open(65) 기반인지 확인
        if not trades_df.empty:
            entry_price = trades_df.iloc[0]["entry_price"]
            # trade_df의 4일째 Open=65, 슬리피지 +0.3% 적용
            expected_price = 65 * (1 + 0.003)
            assert entry_price == pytest.approx(
                expected_price, abs=0.01
            ), f"체결가는 trade_df의 Open 기반이어야 함. 기대: {expected_price:.2f}, 실제: {entry_price:.2f}"

    def test_equity_uses_trade_df_close(self):
        """
        에쿼티가 trade_df의 종가로 계산되는지 검증

        Given:
          - signal_df와 trade_df의 종가가 다름
          - 포지션 보유 중
        When: run_buffer_strategy
        Then: equity = cash + position * trade_df.Close (signal_df.Close가 아님)
        """
        # Given
        signal_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100, 100, 100, 105, 110, 110, 110, 110, 110, 110],
                "Close": [100, 100, 107, 110, 112, 112, 112, 112, 112, 112],
                "ma_5": [100, 100, 100, 103, 106, 108, 109, 110, 110.5, 111],
            }
        )

        # trade_df - 종가가 signal_df와 다름 (TQQQ 가격)
        trade_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [50, 50, 50, 65, 80, 80, 80, 80, 80, 80],
                "Close": [50, 50, 71, 80, 86, 86, 86, 86, 86, 86],
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(signal_df, trade_df, params, log_trades=False)

        # Then: 포지션 보유 시점의 equity가 trade_df 종가 기반인지 검증
        position_rows = equity_df[equity_df["position"] > 0]
        if len(position_rows) > 0:
            # 5일째(인덱스 4): trade_df Close=86, signal_df Close=112
            # equity는 trade_df 기준이어야 함
            row = position_rows.iloc[0]
            position_shares = row["position"]
            equity_value = row["equity"]
            # trade_df의 해당 날짜 종가로 계산된 equity 확인
            # equity가 signal_df 종가(112) 기준이면 더 큰 값이 됨
            assert equity_value < position_shares * 112, "에쿼티는 trade_df 종가(86) 기반이어야 하므로 signal_df 종가(112) 기반보다 작아야 함"

    def test_date_alignment_validation(self):
        """
        signal_df와 trade_df의 날짜 불일치 시 예외 발생 검증

        Given: signal_df와 trade_df의 날짜가 다름
        When: run_buffer_strategy 호출
        Then: ValueError 발생
        """
        # Given: 날짜 불일치
        signal_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
                "Open": [100.0, 102.0, 104.0],
                "Close": [101.0, 103.0, 105.0],
                "ma_5": [100.0, 101.0, 102.0],
            }
        )

        trade_df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)],  # 날짜 다름
                "Open": [50.0, 55.0, 60.0],
                "Close": [52.0, 58.0, 65.0],
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
            initial_capital=10000.0,
        )

        # When & Then
        with pytest.raises(ValueError, match="날짜"):
            run_buffer_strategy(signal_df, trade_df, params, log_trades=False)
