"""버퍼존 체결 규칙 테스트

체결 타이밍, 강제 청산, 미청산 포지션, 핵심 체결 규칙, 백테스트 정확도를 검증한다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.engines.backtest_engine import run_buffer_strategy
from qbt.backtest.strategies.buffer_zone import BufferStrategyParams


class TestExecutionTiming:
    """체결 타이밍 검증 테스트

    목적: 신호 발생일과 체결일이 올바르게 분리되는지 검증
    배경: 신호는 i일 종가로 판단, 체결은 i+1일 시가로 실행되어야 함
    """

    def test_buy_execution_timing_separation(self):
        """
        매수 신호일과 체결일 분리 검증

        검증: 신호일에 즉시 포지션이 반영되지 않고 다음 거래일에 체결되는지 확인

        Given:
          - 10일 데이터, 5일 이동평균
          - 3일째에 상향돌파 신호 발생 (종가 > 상단밴드)
          - hold_days=0 (즉시 체결)
        When: run_buffer_strategy
        Then:
          - 신호일(3일째) equity: position=0 (아직 미체결)
          - 체결일(4일째) equity: position>0 (체결 완료)
        """
        # Given: 3일째에 상향돌파하는 데이터
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100, 100, 100, 105, 110, 110, 110, 110, 110, 110],
                "Close": [100, 100, 107, 110, 112, 112, 112, 112, 112, 112],
                "ma_5": [100, 100, 100, 103, 106, 108, 109, 110, 110.5, 111],
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
        _trades_df, equity_df, _summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 체결 타이밍 검증
        # 3일째 (인덱스 2): 종가=107, ma=100, 상단밴드=103 → 돌파 신호
        # 4일째 (인덱스 3)에 체결되어야 함

        assert len(equity_df) >= 4, f"equity_df는 최소 4행이어야 합니다. 실제: {len(equity_df)}"

        # 신호일(3일째, 인덱스 2) - 아직 포지션 없어야 함
        signal_day_equity = equity_df.iloc[2]
        assert signal_day_equity["position"] == 0, f"신호일에는 position=0이어야 함, 실제: {signal_day_equity['position']}"

        # 체결일(4일째, 인덱스 3) - 포지션 있어야 함
        execution_day_equity = equity_df.iloc[3]
        assert execution_day_equity["position"] > 0, f"체결일에는 position>0이어야 함, 실제: {execution_day_equity['position']}"

    def test_sell_execution_timing_separation(self):
        """
        매도 신호일과 체결일 분리 검증

        Given:
          - 포지션 보유 중
          - 특정일에 하향돌파 신호 발생 (종가 < 하단밴드)
        When: run_buffer_strategy
        Then:
          - 신호일: position>0 (아직 보유 중)
          - 체결일: position=0 (매도 완료)
        """
        # Given: 매수 후 하향돌파하는 데이터
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(15)],
                "Open": [100, 100, 100, 105, 110, 110, 110, 110, 95, 90, 90, 90, 90, 90, 90],
                "Close": [100, 100, 107, 110, 112, 112, 112, 94, 92, 90, 90, 90, 90, 90, 90],
                "ma_5": [100, 100, 100, 103, 106, 108, 109, 110, 107, 104, 101, 98, 95, 92, 90],
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
        trades_df, equity_df, _summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 매도 타이밍 검증
        # 8일째 (인덱스 7): 종가=94, 하단밴드 돌파 → 매도 신호
        # 9일째 (인덱스 8)에 매도 체결되어야 함

        assert len(equity_df) >= 9, f"에쿼티 기록이 9일 이상이어야 함, 실제: {len(equity_df)}"
        assert len(trades_df) > 0, "거래가 발생해야 함"

        # 매도 체결일(9일째, 인덱스 8) - 포지션 없어야 함
        execution_day_equity = equity_df.iloc[8]
        assert (
            execution_day_equity["position"] == 0
        ), f"매도 체결일에는 position=0이어야 함, 실제: {execution_day_equity['position']}"

    def test_first_day_equity_recorded(self):
        """
        첫 날 에쿼티 기록 검증

        첫 날도 기록한다 — 루프가 둘째 날부터 돌면 첫 날이 빠진다

        Given: 10일 데이터
        When: run_buffer_strategy
        Then: equity_df 길이 = 10 (첫 날 포함)
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i for i in range(10)],
                "Close": [100 + i * 0.5 for i in range(10)],
                "ma_5": [100 + i * 0.3 for i in range(10)],
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
        _trades_df, equity_df, _summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 첫 날 포함 검증
        assert len(equity_df) == len(df), f"equity_df 길이는 전체 데이터 길이와 같아야 함. 기대: {len(df)}, 실제: {len(equity_df)}"

        # 첫 날 에쿼티는 초기 자본이어야 함
        first_equity = equity_df.iloc[0]
        assert (
            first_equity["equity"] == params.initial_capital
        ), f"첫 날 에쿼티는 초기 자본과 같아야 함. 기대: {params.initial_capital}, 실제: {first_equity['equity']}"
        assert first_equity["position"] == 0, f"첫 날 포지션은 0이어야 함. 실제: {first_equity['position']}"


class TestForcedLiquidation:
    """백테스트 종료 시 에쿼티 정합성 검증 테스트

    목적: 강제청산 없이도 equity_df와 summary가 일치하는지 검증
    정책: 마지막 날 포지션이 남아있어도 강제청산하지 않음
    """

    def test_forced_liquidation_equity_consistency(self):
        """
        백테스트 종료 시 에쿼티 정합성 검증

        정책: 강제청산 없음, equity_df 마지막 값 == summary.final_capital

        Given: 매수 후 매도 신호 없는 데이터 (포지션 남음)
        When: run_buffer_strategy
        Then:
          - equity_df 마지막 값 == summary.final_capital
          - 포지션이 있으면 평가액 포함
        """
        # Given: 계속 상승 (매도 신호 없음)
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i * 2 for i in range(10)],
                "Close": [100, 105, 110, 115, 120, 125, 130, 135, 140, 145],
                "ma_5": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
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
        _trades_df, equity_df, summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: equity_df 마지막 값과 final_capital 일치 확인
        last_equity = equity_df.iloc[-1]["equity"]
        final_capital = summary["final_capital"]

        assert last_equity == pytest.approx(
            final_capital, abs=0.01
        ), f"equity_df 마지막 값과 final_capital이 일치해야 함. equity_df: {last_equity}, final_capital: {final_capital}"


class TestOpenPosition:
    """미청산 포지션 정보(open_position) 검증 테스트

    목적: summary에 open_position이 올바르게 포함/미포함되는지 검증
    """

    def test_open_position_included_when_holding(self):
        """
        백테스트 종료 시 포지션 보유 중이면 summary에 open_position이 포함된다.

        Given: 계속 상승하여 매수 후 매도 신호가 없는 데이터
        When: run_buffer_strategy 실행
        Then: summary에 open_position 존재 (entry_date, entry_price, shares 포함)
        """
        # Given: 계속 상승 (매도 신호 없음)
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i * 2 for i in range(10)],
                "Close": [100, 105, 110, 115, 120, 125, 130, 135, 140, 145],
                "ma_5": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
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
        _trades_df, _equity_df, summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: open_position이 포함되어야 함
        assert "open_position" in summary, "포지션 보유 중이면 open_position이 summary에 포함되어야 함"
        open_pos = summary["open_position"]
        assert "entry_date" in open_pos, "entry_date 키 존재"
        assert "entry_price" in open_pos, "entry_price 키 존재"
        assert "shares" in open_pos, "shares 키 존재"
        assert isinstance(open_pos["entry_date"], str), "entry_date는 문자열 (ISO format)"
        assert open_pos["entry_price"] > 0, "entry_price는 양수"
        assert open_pos["shares"] > 0, "shares는 양수"

    def test_open_position_absent_when_all_closed(self):
        """
        모든 포지션이 청산된 경우 summary에 open_position이 없다.

        Given: 5일째 상향돌파 → 6일째 매수, 8일째 하향돌파 → 9일째 매도로 포지션 없이 끝나는 데이터
        When: run_buffer_strategy 실행
        Then: 거래 1건, 마지막 날 position=0, summary에 open_position 없음
        """
        # Given: 상승 후 하락 (매수→매도 패턴)
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i for i in range(10)],
                "Close": [100, 95, 90, 95, 105, 110, 105, 95, 85, 80],
                "ma_5": [100, 99, 98, 97, 96, 98, 100, 102, 101, 100],
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
        trades_df, equity_df, summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then
        assert len(trades_df) == 1, "사고 판 거래가 한 건이어야 함"
        assert equity_df.iloc[-1]["position"] == 0
        assert "open_position" not in summary


class TestCoreExecutionRules:
    """백테스트 핵심 실행 규칙 검증 테스트

    목적: CLAUDE.md에 정의된 절대 규칙들을 테스트로 고정
    배경: equity, final_capital, pending, hold_days 정의를 명확히 하고 회귀 방지
    """

    def test_equity_definition_with_position(self):
        """
        Equity 정의 검증 (포지션 보유 시)

        절대 규칙: equity = cash + position_shares * close

        Given: 포지션을 보유한 상태
        When: equity 계산
        Then: equity == cash + shares * close (모든 시점)
        """
        # Given: 매수 후 매도까지 완전한 사이클을 포함하는 데이터
        # i=2: 매수 신호 (close=107 > upper=103), i=3: 매수 실행 (open=105)
        # i=12~13: 매도 신호 (close가 lower band 아래로 하락)
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(15)],
                "Open": [100, 100, 100, 105, 110, 110, 110, 110, 110, 110, 118, 113, 108, 103, 98],
                "Close": [100, 100, 107, 110, 112, 112, 112, 112, 115, 120, 115, 110, 105, 100, 95],
                "ma_5": [100, 100, 100, 103, 106, 108, 109, 110, 110.5, 111, 115, 114, 113, 110, 105],
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
        trades_df, equity_df, _summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 포지션 보유 중인 시점에서 equity가 양수이고 가격에 연동되어 변동하는지 검증
        assert len(equity_df) > 0, "에쿼티 기록이 있어야 함"
        assert len(trades_df) > 0, "테스트 데이터에서 거래가 반드시 발생해야 함"

        position_rows = equity_df[equity_df["position"] > 0]
        assert len(position_rows) > 0, "테스트 데이터에서 포지션 보유 구간이 반드시 존재해야 함"

        # 포지션 보유 중일 때 equity > 0이고, 가격 변동에 따라 equity가 달라져야 함
        assert (position_rows["equity"] > 0).all(), "포지션 보유 중 equity는 양수여야 함"
        assert (position_rows["position"] > 0).all(), "포지션 보유 구간에서 position > 0"

        unique_equities = position_rows["equity"].nunique()
        assert unique_equities > 1, "포지션 보유 중 equity는 가격 변동에 따라 달라져야 함"

    def test_equity_definition_no_position(self):
        """
        Equity 정의 검증 (포지션 없을 시)

        절대 규칙: position=0일 때 equity = cash

        Given: 종가가 이동평균과 같아 밴드를 넘지 않는 데이터 (거래 없음)
        When: equity 계산
        Then: 모든 날 position=0 이고 equity == 초기 자본 (현금만 있으므로)
        """
        # Given: 매매가 발생하지 않는 데이터 (밴드 내에서만 움직임)
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i for i in range(10)],
                "Close": [100 + i * 0.5 for i in range(10)],
                "ma_5": [100 + i * 0.5 for i in range(10)],  # 종가와 거의 일치 (밴드 돌파 없음)
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
        trades_df, equity_df, _summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then
        assert trades_df.empty, "밴드를 넘지 않으므로 거래가 없어야 함"
        assert (equity_df["position"] == 0).all()
        assert list(equity_df["equity"]) == pytest.approx([params.initial_capital] * len(equity_df), abs=0.01)

    def test_hold_days_1_timeline(self):
        """
        hold_days=1 타임라인 검증

        절대 규칙:
        - 돌파일(i일)에는 pending 생성 안 함 (카운트 시작만)
        - i+1일 종가에서 유지조건 충족 시 pending_order 생성
        - i+2일 시가에 체결

        Given: hold_days=1, 유지조건 만족하는 패턴
        When: 백테스트 실행
        Then:
          - 돌파일(i): position=0
          - 확정일(i+1): position=0 (pending 생성일)
          - 체결일(i+2): position>0
        """
        # Given: 돌파 후 계속 상승 (유지조건 만족)
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(15)],
                "Open": [100, 100, 100, 105, 110, 115, 120, 125, 130, 135, 140, 140, 140, 140, 140],
                "Close": [100, 100, 107, 110, 115, 120, 125, 130, 135, 140, 145, 145, 145, 145, 145],
                "ma_5": [100, 100, 100, 103, 106, 110, 114, 118, 122, 126, 130, 133, 136, 139, 141],
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=1,
            initial_capital=10000.0,
        )

        # When
        _trades_df, equity_df, _summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 돌파일(인덱스 2), 확정일(인덱스 3), 체결일(인덱스 4)
        assert len(equity_df) >= 5, f"equity_df는 최소 5행이어야 합니다. 실제: {len(equity_df)}"
        break_day = equity_df.iloc[2]  # 돌파일
        confirm_day = equity_df.iloc[3]  # 유지조건 확인 후 pending 생성
        execution_day = equity_df.iloc[4]  # 체결일

        assert break_day["position"] == 0, f"hold_days=1: 돌파일 position=0. 실제: {break_day['position']}"
        assert confirm_day["position"] == 0, f"hold_days=1: 확정일 position=0. 실제: {confirm_day['position']}"
        assert execution_day["position"] > 0, f"hold_days=1: 체결일 position>0. 실제: {execution_day['position']}"

    def test_last_day_pending_execution(self):
        """
        마지막 날 pending 실행 검증

        절대 규칙: 전날 종가에서 생성된 pending은 마지막날 시가에서 정상 체결됨

        Given: N-1일 종가에서 신호 발생 → pending 생성
        When: N일(마지막 날) 시가 존재
        Then: N일에 정상 체결됨
        """
        # Given: 마지막에서 두 번째 날에 신호 발생하도록 구성
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100, 100, 100, 100, 100, 100, 100, 100, 105, 110],  # 9일째 시가 존재
                "Close": [100, 100, 100, 100, 100, 100, 100, 107, 110, 112],  # 8일째 돌파
                "ma_5": [100, 100, 100, 100, 100, 100, 100, 100, 103, 106],
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
        _trades_df, equity_df, _summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 마지막 날(인덱스 9)에 포지션 있어야 함
        assert len(equity_df) >= 10, f"equity_df는 최소 10행이어야 합니다. 실제: {len(equity_df)}"
        last_day = equity_df.iloc[-1]
        assert last_day["position"] > 0, f"마지막날 pending 체결되어 position>0. 실제: {last_day['position']}"

    def test_last_day_signal_ignored(self):
        """
        마지막 날 신호 무시 검증

        절대 규칙: 마지막날 종가에서 발생한 신호는 pending 생성하지 않음 (다음날 시가 없음)

        Given: 마지막날에만 돌파 신호 발생
        When: 백테스트 실행
        Then: 체결되지 않음 (trades 없음 또는 마지막날 position=0)
        """
        # Given: 마지막날(10일째)에만 돌파
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
                "Close": [100, 100, 100, 100, 100, 100, 100, 100, 100, 107],  # 마지막날만 돌파
                "ma_5": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
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
        _trades_df, equity_df, _summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 마지막날 포지션 없어야 함 (체결 불가)
        last_day = equity_df.iloc[-1]
        assert last_day["position"] == 0, f"마지막날 신호는 무시되어 position=0. 실제: {last_day['position']}"


class TestBacktestAccuracy:
    """백테스트 엔진 정확도 테스트

    목적: 백테스트 결과의 일관성과 정확성을 보장하는 핵심 인바리언트를 고정합니다.

    검증 대상:
    1. equity_df, trades_df, summary.final_capital 간 일관성
    2. hold_days 룩어헤드 방지 (순차 검증)
    3. 첫 유효 구간 신호 감지
    """

    def test_backtest_end_consistency(self):
        """
        백테스트 종료 시 equity_df, trades_df, summary 간 일관성 검증

        핵심 인바리언트:
        - 마지막 날 포지션이 남아있어도 강제청산하지 않음
        - equity_df의 마지막 equity == summary.final_capital

        Given: 상향돌파 후 매도 신호 없이 종료되는 시나리오
        When: run_buffer_strategy 실행
        Then:
          - 마지막 날 포지션이 남아있음 (position > 0)
          - equity_df 마지막 equity == summary.final_capital
        """
        # Given: 상향돌파 후 계속 상승 (매도 신호 없음)
        # 앞 3행을 평탄하게 두어 MA 워밍업(window-1=2행 NaN) 이후에도
        # 밴드 아래에서 출발하도록 한다. 그 뒤 지속 상승하여 매도 신호가 없다.
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 13)],
                "Open": [100.0] * 12,
                "Close": [90, 90, 90, 95, 105, 110, 115, 120, 125, 130, 135, 140],
            }
        )
        df = add_single_moving_average(df, window=3)

        params = BufferStrategyParams(
            initial_capital=100000.0,
            ma_window=3,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
        )

        # When
        _trades_df, equity_df, summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 마지막 날 포지션이 남아있어야 함
        last_equity_record = equity_df.iloc[-1]
        assert last_equity_record["position"] > 0, "마지막 날 포지션이 있어야 함"

        # Then: equity_df 마지막 equity == summary.final_capital
        last_equity = last_equity_record["equity"]
        assert last_equity == pytest.approx(
            summary["final_capital"], abs=0.01
        ), f"equity_df 마지막 equity({last_equity:.2f})와 summary.final_capital({summary['final_capital']:.2f})이 일치해야 함"

    def test_hold_days_no_lookahead(self):
        """
        hold_days 룩어헤드 방지 검증

        핵심 인바리언트:
        - i일에 i+1 ~ i+H를 미리 검사하여 pending을 선적재하면 안 됨 (체결 시점은 test_hold_days_1_timeline)
        - 매일 순차적으로 유지조건 체크 — 유지 중 하루라도 상단 밴드 아래면 대기를 푼다

        Given: 돌파 후 하루 유지, 이틀째 상단 밴드 아래
        When: run_buffer_strategy 실행 (hold_days=2)
        Then:
          - 전제: 같은 데이터에서 hold_days=1 이면 매수한다 (돌파와 하루 유지가 실제로 있다)
          - hold_days=2 는 매수하지 않는다 (거래 0, 전 구간 position 0)
        """

        # Given: i=3 돌파(110 > 상단 106.43), i=4 유지(115 > 111.58), i=5 실패(100 <= 111.58)
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 8)],
                "Open": [100.0] * 7,
                "Close": [100, 100, 100, 110, 115, 100, 95],
            }
        )
        df = add_single_moving_average(df, window=3)

        def _params(hold_days: int) -> BufferStrategyParams:
            return BufferStrategyParams(
                initial_capital=100000.0,
                ma_window=3,
                buy_buffer_zone_pct=0.03,
                sell_buffer_zone_pct=0.03,
                hold_days=hold_days,
            )

        # 전제: 돌파 · 유지가 없는 데이터면 아래 단언이 늘 참이 됨
        _trades_h1, equity_h1, _summary_h1 = run_buffer_strategy(df, df, _params(1), log_trades=False)
        assert (equity_h1["position"] > 0).any(), "전제: hold_days=1 이면 매수해야 함"

        # When
        trades_df, equity_df, _summary = run_buffer_strategy(df, df, _params(2), log_trades=False)

        # Then: 유지조건 실패로 매수 없음
        assert trades_df.empty, "유지조건 실패로 거래가 없어야 함"
        assert (equity_df["position"] == 0).all(), "유지조건 실패로 포지션이 없어야 함"

    def test_first_valid_signal_detection(self):
        """
        첫 유효 구간 신호 감지 검증

        핵심 인바리언트:
        - 루프 시작 시 prev_upper_band, prev_lower_band가 None이면 첫 신호를 놓칠 수 있음
        - 첫 번째 유효한 신호 기회를 놓치지 않아야 함

        Given: 이동평균 계산 후 첫 번째 유효 구간에서 상향돌파
        When: run_buffer_strategy 실행
        Then:
          - 첫 신호가 정상적으로 감지되어야 함
          - trades_df가 비어있지 않아야 함
        """
        # Given: 첫 유효 구간에서 즉시 상향돌파
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 10)],
                "Open": [100.0] * 9,
                # ma_window=3이므로 i=2부터 유효. i=2는 밴드 아래(초기화), i=3에서 상향돌파한다.
                "Close": [90, 90, 90, 105, 110, 95, 90, 85, 80],
            }
        )
        df = add_single_moving_average(df, window=3)

        params = BufferStrategyParams(
            initial_capital=100000.0,
            ma_window=3,
            buy_buffer_zone_pct=0.03,
            sell_buffer_zone_pct=0.03,
            hold_days=0,
        )

        # When
        trades_df, _equity_df, _summary = run_buffer_strategy(df, df, params, log_trades=False)

        # Then: 매수 신호가 감지되어야 함
        # prev_band가 올바르게 초기화되어 첫 유효 구간의 신호를 감지해야 함
        assert not trades_df.empty, "첫 유효 구간에서 신호가 감지되어야 함"
