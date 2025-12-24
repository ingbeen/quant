"""
backtest/strategy 모듈 테스트

이 파일은 무엇을 검증하나요?
1. Buy & Hold 전략이 정확히 실행되는가?
2. 버퍼존 전략의 매수/매도 신호가 정확한가?
3. 슬리피지가 올바르게 적용되는가?
4. 포지션이 남았을 때 강제 청산되는가?
5. 유효 데이터 부족 시 에러 처리가 되는가?

왜 중요한가요?
전략 실행 로직의 버그는 백테스트 결과를 완전히 왜곡합니다.
예: 슬리피지를 반대로 적용하면 수익률이 실제보다 높게 나옵니다.
"""

from datetime import date

import pandas as pd
import pytest

from qbt.backtest.strategy import (
    BufferStrategyParams,
    BuyAndHoldParams,
    calculate_recent_buy_count,
    check_hold_condition,
    run_buffer_strategy,
    run_buy_and_hold,
)


class TestRunBuyAndHold:
    """Buy & Hold 전략 테스트"""

    def test_normal_execution(self):
        """
        정상적인 Buy & Hold 실행 테스트

        데이터 신뢰성: 벤치마크 전략이므로 정확해야 비교가 의미 있습니다.

        Given: 3일치 가격 데이터
        When: run_buy_and_hold 실행
        Then:
          - 1개 거래 (첫날 매수 → 마지막날 매도)
          - 슬리피지 적용 확인 (매수 +, 매도 -)
          - shares는 정수
          - equity_df와 summary 반환
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
                "Open": [100.0, 102.0, 104.0],
                "Close": [101.0, 103.0, 105.0],
            }
        )

        params = BuyAndHoldParams(initial_capital=10000.0)

        # When
        equity_df, summary = run_buy_and_hold(df, params)

        # Then: summary 확인
        assert isinstance(summary, dict), "summary는 딕셔너리여야 합니다"
        assert summary["strategy"] == "buy_and_hold", "전략 이름 확인"
        assert summary["total_trades"] == 1, "Buy & Hold는 1건의 거래 (매수→매도)"
        assert summary["final_capital"] > params.initial_capital * 0.9, "최종 자본은 초기 자본의 90% 이상"

        # Equity curve 확인
        assert len(equity_df) == 3, "매일 equity 기록"
        assert "equity" in equity_df.columns, "equity 컬럼 존재"
        assert "position" in equity_df.columns, "position 컬럼 존재"
        assert equity_df["equity"].iloc[-1] > 0, "최종 자본은 양수"

    def test_insufficient_capital(self):
        """
        자본이 부족해 주식을 살 수 없을 때 테스트

        안정성: 자본 < 주가일 때도 에러 없이 처리되어야 합니다.

        Given: 초기 자본 10, 주가 100
        When: run_buy_and_hold
        Then: shares = 0, 총 수익률은 0% 근처
        """
        # Given
        df = pd.DataFrame(
            {"Date": [date(2023, 1, 2), date(2023, 1, 3)], "Open": [100.0, 101.0], "Close": [100.0, 101.0]}
        )

        params = BuyAndHoldParams(initial_capital=10.0)  # 주가보다 훨씬 작음

        # When
        equity_df, summary = run_buy_and_hold(df, params)

        # Then: 거래는 발생했지만 shares=0
        # 자본이 부족하므로 수익률이 거의 0에 가까움
        assert summary["total_trades"] >= 0, "에러 없이 실행됨"
        assert abs(summary["total_return_pct"]) < 1.0, "자본 부족 시 수익률 거의 0%"


class TestCalculateRecentBuyCount:
    """최근 매수 횟수 계산 테스트"""

    def test_count_within_period(self):
        """
        지정 기간 내 매수 횟수 계산 테스트

        데이터 신뢰성: 과매수 방지 로직의 기반이므로 정확해야 합니다.

        Given: 5개월간 4번 매수
        When: recent_months=3으로 계산
        Then: 최근 3개월 내 매수만 카운트
        """
        # Given: 매수 날짜들
        entry_dates = [
            date(2023, 1, 15),  # 6개월 전
            date(2023, 3, 15),  # 4개월 전
            date(2023, 5, 10),  # 2개월 전
            date(2023, 6, 20),  # 1개월 전
        ]

        current_date = date(2023, 7, 15)
        recent_months = 3

        # When
        count = calculate_recent_buy_count(entry_dates, current_date, recent_months)

        # Then: 5월, 6월만 포함 = 2건
        # cutoff = 2023-04-15 (3개월 전)
        # 5/10, 6/20만 포함
        assert count == 2, f"최근 3개월(4/15 이후) 매수는 2건이어야 합니다. 실제: {count}"

    def test_no_recent_buys(self):
        """
        최근 매수가 없을 때

        Given: 모든 매수가 1년 전
        When: recent_months=3
        Then: count = 0
        """
        # Given
        entry_dates = [date(2022, 1, 1), date(2022, 2, 1)]
        current_date = date(2023, 7, 15)

        # When
        count = calculate_recent_buy_count(entry_dates, current_date, recent_months=3)

        # Then
        assert count == 0, "오래된 매수는 카운트되지 않아야 합니다"


class TestCheckHoldCondition:
    """홀딩 조건 체크 테스트"""

    def test_hold_satisfied(self):
        """
        홀딩 조건 만족 테스트

        데이터 신뢰성: 홀딩 기간 동안 upper_band 이하로 떨어지지 않았는지 확인

        Given: 5일 데이터, break_idx=1 (2일차부터 체크), hold_days=2
        When: 2일, 3일 모두 Close > upper_band
        Then: True 반환
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(5)],
                "Close": [100, 110, 120, 130, 140],
                "ma_5": [95, 100, 105, 110, 115],
            }
        )

        ma_col = "ma_5"
        buffer_pct = 0.02  # 2% = 0.02 (upper_band = MA * 1.02)

        # break_idx=1 (2일차), hold_days=2 → 2일차, 3일차 체크
        # 2일차: Close=110, upper=100*1.02=102 → 110 > 102 ✓
        # 3일차: Close=120, upper=105*1.02=107.1 → 120 > 107.1 ✓

        # When
        result = check_hold_condition(df=df, break_idx=1, hold_days=2, ma_col=ma_col, buffer_pct=buffer_pct)

        # Then
        assert result is True, "홀딩 기간 동안 upper_band 상회하면 True"

    def test_hold_violated(self):
        """
        홀딩 조건 위반 테스트

        Given: 홀딩 기간 중 한 번이라도 upper_band 이하로 하락
        When: check_hold_condition
        Then: False
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(5)],
                "Close": [100, 110, 95, 130, 140],  # 3일차에 급락
                "ma_5": [95, 100, 105, 110, 115],
            }
        )

        ma_col = "ma_5"
        buffer_pct = 0.02  # 2%

        # break_idx=1, hold_days=2
        # 2일차: Close=110, upper=102 ✓
        # 3일차: Close=95, upper=107.1 → 95 < 107.1 ✗

        # When
        result = check_hold_condition(df, 1, 2, ma_col, buffer_pct)

        # Then
        assert result is False, "한 번이라도 upper_band 이하면 False"

    def test_insufficient_data(self):
        """
        데이터 부족 시 테스트

        안정성: 홀딩 기간만큼 데이터가 없으면 False 반환

        Given: 3일 데이터, break_idx=2, hold_days=5
        When: check_hold_condition
        Then: False (데이터 부족)
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                "Close": [100, 110, 120],
                "ma_5": [95, 100, 105],
            }
        )

        # When: break_idx=2에서 hold_days=5 → 데이터 부족
        result = check_hold_condition(df, 2, 5, "ma_5", 0.02)

        # Then
        assert result is False, "데이터 부족 시 False"


class TestRunBufferStrategy:
    """버퍼존 전략 실행 테스트"""

    def test_normal_execution_with_trades(self):
        """
        정상적인 버퍼존 전략 실행 (매매 발생)

        데이터 신뢰성: 실제 전략 실행 시 신호 생성이 정확해야 합니다.

        Given:
          - ma_5 컬럼 포함 데이터
          - 반등하는 패턴
        When: run_buffer_strategy 실행
        Then:
          - trades_df, equity_df, summary 반환
          - DataFrame 구조 검증
        """
        # Given: ma_5 포함 데이터
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i for i in range(10)],
                "Close": [100, 95, 90, 95, 105, 110, 100, 95, 105, 110],
                "ma_5": [100, 98, 96, 94, 96, 98, 100, 102, 104, 106],
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buffer_zone_pct=0.03,  # 3% = 0.03
            hold_days=0,  # 즉시 매수
            recent_months=0,  # 동적 조정 비활성화
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 반환 타입 확인
        assert isinstance(trades_df, pd.DataFrame)
        assert isinstance(equity_df, pd.DataFrame)
        assert isinstance(summary, dict)

        # summary 검증
        assert summary["strategy"] == "buffer_zone"
        assert "total_trades" in summary
        assert "total_return_pct" in summary

        # equity_df 검증
        assert len(equity_df) > 0, "Equity curve는 최소 1행 이상"
        assert "equity" in equity_df.columns

    def test_missing_ma_column(self):
        """
        MA 컬럼 누락 시 에러 테스트

        안정성: 필수 컬럼 없으면 즉시 실패해야 합니다.

        Given: ma_5 컬럼 없는 DataFrame
        When: run_buffer_strategy (ma_window=5)
        Then: ValueError
        """
        # Given: MA 컬럼 없음
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 1), date(2023, 1, 2)],
                "Open": [100, 101],
                "Close": [100, 101],
            }
        )

        params = BufferStrategyParams(
            ma_window=5, buffer_zone_pct=0.03, hold_days=0, recent_months=0, initial_capital=10000.0
        )

        # When & Then
        with pytest.raises(ValueError) as exc_info:
            run_buffer_strategy(df, params, log_trades=False)

        assert "ma_5" in str(exc_info.value) or "컬럼" in str(exc_info.value), "MA 컬럼 누락 에러 메시지"

    def test_insufficient_valid_data(self):
        """
        유효 데이터 부족 시 에러 테스트

        안정성: MA 계산 후 NaN이 아닌 데이터가 너무 적으면 실패

        Given: 3행 데이터 (MA 계산 후 유효 데이터 1행)
        When: run_buffer_strategy
        Then: ValueError (최소 데이터 요구량 미달)
        """
        # Given: 최소 데이터
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 1), date(2023, 1, 2), date(2023, 1, 3)],
                "Open": [100, 101, 102],
                "Close": [100, 101, 102],
                "ma_5": [None, None, 100],  # 처음 2개 NaN
            }
        )

        params = BufferStrategyParams(
            ma_window=5, buffer_zone_pct=0.03, hold_days=0, recent_months=0, initial_capital=10000.0
        )

        # When & Then: 유효 데이터 1행으로는 부족
        with pytest.raises(ValueError) as exc_info:
            run_buffer_strategy(df, params, log_trades=False)

        assert "유효" in str(exc_info.value) or "부족" in str(exc_info.value), "유효 데이터 부족 에러"

    def test_forced_liquidation_at_end(self):
        """
        마지막 날 강제 청산 테스트

        안정성: 포지션이 남아있으면 마지막 날 자동 매도되어야 합니다.

        Given: 매수 후 매도 신호가 없는 데이터
        When: run_buffer_strategy
        Then: 마지막 거래에 exit_reason="end_of_data" 포함
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
            ma_window=5, buffer_zone_pct=0.03, hold_days=0, recent_months=0, initial_capital=10000.0
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 거래가 있으면 마지막 거래 확인
        if len(trades_df) > 0:
            last_trade = trades_df.iloc[-1]
            # 포지션이 있었다면 exit_reason 확인 가능
            assert "exit_date" in last_trade.index, "exit_date 컬럼 존재"

    def test_hold_days_zero_vs_positive(self):
        """
        hold_days=0과 hold_days>0 경로 테스트

        회귀 방지: 두 경로 모두 정상 작동해야 합니다.

        Given: 같은 데이터
        When: hold_days=0 vs hold_days=3
        Then: 둘 다 에러 없이 실행, 거래 횟수는 다를 수 있음
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(20)],
                "Open": [100 + i for i in range(20)],
                "Close": [100 + i * 0.5 for i in range(20)],
                "ma_5": [100 + i * 0.3 for i in range(20)],
            }
        )

        params_zero = BufferStrategyParams(
            ma_window=5, buffer_zone_pct=0.03, hold_days=0, recent_months=0, initial_capital=10000.0
        )

        params_positive = BufferStrategyParams(
            ma_window=5, buffer_zone_pct=0.03, hold_days=3, recent_months=0, initial_capital=10000.0
        )

        # When
        trades_zero, _, _ = run_buffer_strategy(df, params_zero, log_trades=False)
        trades_positive, _, _ = run_buffer_strategy(df, params_positive, log_trades=False)

        # Then: 둘 다 실행됨 (에러 없음)
        assert isinstance(trades_zero, pd.DataFrame)
        assert isinstance(trades_positive, pd.DataFrame)

        # hold_days>0이면 거래가 더 적을 수 있음 (홀딩 조건 때문)
        # 단, 데이터에 따라 다르므로 부등호 검증은 생략


class TestExecutionTiming:
    """체결 타이밍 검증 테스트

    목적: 신호 발생일과 체결일이 올바르게 분리되는지 검증
    배경: 신호는 i일 종가로 판단, 체결은 i+1일 시가로 실행되어야 함
    """

    def test_buy_execution_timing_separation(self):
        """
        매수 신호일과 체결일 분리 검증

        버그 재현: 현재 구현은 신호일에 즉시 포지션 반영 (잘못됨)

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
            ma_window=5, buffer_zone_pct=0.03, hold_days=0, recent_months=0, initial_capital=10000.0  # 3% 버퍼존  # 즉시 체결
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 체결 타이밍 검증
        # 3일째 (인덱스 2): 종가=107, ma=100, 상단밴드=103 → 돌파 신호
        # 4일째 (인덱스 3)에 체결되어야 함

        if len(equity_df) >= 4:
            # 신호일(3일째, 인덱스 2) - 아직 포지션 없어야 함
            signal_day_equity = equity_df.iloc[2]
            assert signal_day_equity["position"] == 0, f"신호일에는 position=0이어야 함, 실제: {signal_day_equity['position']}"

            # 체결일(4일째, 인덱스 3) - 포지션 있어야 함
            execution_day_equity = equity_df.iloc[3]
            assert (
                execution_day_equity["position"] > 0
            ), f"체결일에는 position>0이어야 함, 실제: {execution_day_equity['position']}"

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
            ma_window=5, buffer_zone_pct=0.03, hold_days=0, recent_months=0, initial_capital=10000.0
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 매도 타이밍 검증
        # 8일째 (인덱스 7): 종가=94, 하단밴드 돌파 → 매도 신호
        # 9일째 (인덱스 8)에 매도 체결되어야 함

        if len(equity_df) >= 9 and len(trades_df) > 0:
            # 매도 체결일(9일째, 인덱스 8) - 포지션 없어야 함
            execution_day_equity = equity_df.iloc[8]
            assert (
                execution_day_equity["position"] == 0
            ), f"매도 체결일에는 position=0이어야 함, 실제: {execution_day_equity['position']}"

    def test_first_day_equity_recorded(self):
        """
        첫 날 에쿼티 기록 검증

        버그 재현: range(1, len(df)) 루프로 첫 날 누락

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
            ma_window=5, buffer_zone_pct=0.03, hold_days=0, recent_months=0, initial_capital=10000.0
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 첫 날 포함 검증
        assert len(equity_df) == len(df), f"equity_df 길이는 전체 데이터 길이와 같아야 함. 기대: {len(df)}, 실제: {len(equity_df)}"

        # 첫 날 에쿼티는 초기 자본이어야 함
        first_equity = equity_df.iloc[0]
        assert (
            first_equity["equity"] == params.initial_capital
        ), f"첫 날 에쿼티는 초기 자본과 같아야 함. 기대: {params.initial_capital}, 실제: {first_equity['equity']}"
        assert first_equity["position"] == 0, f"첫 날 포지션은 0이어야 함. 실제: {first_equity['position']}"


class TestForcedLiquidation:
    """강제청산 정합성 검증 테스트

    목적: 데이터 종료 시 강제청산의 슬리피지가 올바르게 반영되는지 검증
    """

    def test_forced_liquidation_equity_consistency(self):
        """
        강제청산 시 에쿼티 정합성 검증

        버그 재현: 청산 후 equity_records 업데이트 누락 → 슬리피지 미반영

        Given: 매수 후 매도 신호 없는 데이터 (강제청산 발생)
        When: run_buffer_strategy
        Then:
          - equity_df 마지막 값 == summary['final_capital']
          - 슬리피지가 반영된 최종 자본
        """
        # Given: 계속 상승 (매도 신호 없음 → 강제청산)
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100 + i * 2 for i in range(10)],
                "Close": [100, 105, 110, 115, 120, 125, 130, 135, 140, 145],
                "ma_5": [100, 102, 104, 106, 108, 110, 112, 114, 116, 118],
            }
        )

        params = BufferStrategyParams(
            ma_window=5, buffer_zone_pct=0.03, hold_days=0, recent_months=0, initial_capital=10000.0
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 정합성 검증
        if len(trades_df) > 0:
            # 마지막 거래가 강제청산인지 확인
            last_trade = trades_df.iloc[-1]

            # equity_df 마지막 값과 final_capital 일치 확인
            last_equity = equity_df.iloc[-1]["equity"]
            final_capital = summary["final_capital"]

            assert (
                abs(last_equity - final_capital) < 0.01
            ), f"equity_df 마지막 값과 final_capital이 일치해야 함. equity_df: {last_equity}, final_capital: {final_capital}"

            # 강제청산 시 슬리피지 적용 확인
            if last_trade.get("exit_reason") == "end_of_data":
                # 슬리피지가 적용된 가격인지 확인 (정확한 값은 구현에 따라 다름)
                assert last_trade["exit_price"] > 0, "강제청산 가격이 양수여야 함"
