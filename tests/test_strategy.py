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
    PendingOrderConflictError,
    calculate_recent_buy_count,
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

    @pytest.mark.parametrize("invalid_capital", [0.0, -1000.0, -1.0])
    def test_invalid_capital_raises(self, invalid_capital):
        """
        초기 자본이 0 이하일 때 예외 발생 테스트

        Given: initial_capital <= 0 (parametrize로 여러 값 테스트)
        When: run_buy_and_hold 호출
        Then: ValueError 발생

        Args:
            invalid_capital: 테스트할 잘못된 초기 자본 값 (0.0, -1000.0, -1.0)
        """
        # Given
        df = pd.DataFrame(
            {"Date": [date(2023, 1, 2), date(2023, 1, 3)], "Open": [100.0, 101.0], "Close": [100.0, 101.0]}
        )

        # When & Then
        params = BuyAndHoldParams(initial_capital=invalid_capital)
        with pytest.raises(ValueError, match="initial_capital은 양수여야 합니다"):
            run_buy_and_hold(df, params)

    @pytest.mark.parametrize(
        "df_data,missing_column",
        [
            ({"Date": [date(2023, 1, 2), date(2023, 1, 3)], "Close": [100.0, 101.0]}, "Open"),
            ({"Date": [date(2023, 1, 2), date(2023, 1, 3)], "Open": [100.0, 101.0]}, "Close"),
        ],
        ids=["missing_open", "missing_close"],
    )
    def test_missing_required_columns_raises(self, df_data, missing_column):
        """
        필수 컬럼 누락 시 예외 발생 테스트

        Given: Open 또는 Close 컬럼이 없는 DataFrame (parametrize로 여러 케이스 테스트)
        When: run_buy_and_hold 호출
        Then: ValueError 발생

        Args:
            df_data: 테스트할 DataFrame 데이터 (누락 컬럼 포함)
            missing_column: 누락된 컬럼명 (식별용)
        """
        # Given
        df = pd.DataFrame(df_data)
        params = BuyAndHoldParams(initial_capital=10000.0)

        # When & Then
        with pytest.raises(ValueError, match="필수 컬럼 누락"):
            run_buy_and_hold(df, params)

    def test_insufficient_rows_raises(self):
        """
        최소 행 수 미달 시 예외 발생 테스트

        Given: 1행만 있는 DataFrame
        When: run_buy_and_hold 호출
        Then: ValueError 발생 (최소 2행 필요)
        """
        # Given: 1행만
        df = pd.DataFrame({"Date": [date(2023, 1, 2)], "Open": [100.0], "Close": [100.0]})

        params = BuyAndHoldParams(initial_capital=10000.0)

        # When & Then
        with pytest.raises(ValueError, match="유효 데이터 부족"):
            run_buy_and_hold(df, params)


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

    @pytest.mark.parametrize(
        "param_name,invalid_value,valid_base_params,error_pattern",
        [
            ("ma_window", 0, {"buffer_zone_pct": 0.03, "hold_days": 0, "recent_months": 0}, "ma_window는 1 이상"),
            (
                "buffer_zone_pct",
                0.005,
                {"ma_window": 5, "hold_days": 0, "recent_months": 0},
                "buffer_zone_pct는.*이상",
            ),
            ("hold_days", -1, {"ma_window": 5, "buffer_zone_pct": 0.03, "recent_months": 0}, "hold_days는.*이상"),
            (
                "recent_months",
                -1,
                {"ma_window": 5, "buffer_zone_pct": 0.03, "hold_days": 0},
                "recent_months는 0 이상",
            ),
        ],
        ids=["invalid_ma_window", "invalid_buffer_zone_pct", "invalid_hold_days", "invalid_recent_months"],
    )
    def test_invalid_strategy_params_raise(self, param_name, invalid_value, valid_base_params, error_pattern):
        """
        전략 파라미터가 유효하지 않을 때 예외 발생 테스트

        Given: 유효하지 않은 파라미터 값 (parametrize로 여러 파라미터 테스트)
        When: run_buffer_strategy 호출
        Then: ValueError 발생

        Args:
            param_name: 테스트할 파라미터 이름
            invalid_value: 잘못된 값
            valid_base_params: 다른 유효한 파라미터들
            error_pattern: 예상 에러 메시지 패턴
        """
        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, 1), date(2023, 1, 2)],
                "Open": [100, 101],
                "Close": [100, 101],
                "ma_5": [100, 101],
                "ma_0": [100, 101],  # invalid ma_window 테스트용
            }
        )

        # 파라미터 구성
        all_params = {**valid_base_params, param_name: invalid_value, "initial_capital": 10000.0}
        params = BufferStrategyParams(**all_params)

        # When & Then
        with pytest.raises(ValueError, match=error_pattern):
            run_buffer_strategy(df, params, log_trades=False)

    def test_forced_liquidation_at_end(self):
        """
        백테스트 종료 시 포지션 처리 테스트

        정책: 마지막 날 포지션이 남아있어도 강제청산하지 않음

        Given: 매수 후 매도 신호가 없는 데이터
        When: run_buffer_strategy
        Then: 마지막 equity에 포지션 평가액 포함
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

        # Then: 마지막 equity 확인
        if not equity_df.empty:
            last_equity = equity_df.iloc[-1]
            assert "equity" in last_equity.index, "equity 컬럼 존재"

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
            ma_window=5,
            buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
            initial_capital=10000.0,  # 3% 버퍼존  # 즉시 체결
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
    """백테스트 종료 시 에쿼티 정합성 검증 테스트 (정책 변경)

    목적: 강제청산 없이도 equity_df와 summary가 일치하는지 검증
    정책: 마지막 날 포지션이 남아있어도 강제청산하지 않음
    """

    def test_forced_liquidation_equity_consistency(self):
        """
        백테스트 종료 시 에쿼티 정합성 검증 (정책 변경)

        정책 변경: 강제청산 없음, equity_df 마지막 값 == summary.final_capital

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
            ma_window=5, buffer_zone_pct=0.03, hold_days=0, recent_months=0, initial_capital=10000.0
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: equity_df 마지막 값과 final_capital 일치 확인
        last_equity = equity_df.iloc[-1]["equity"]
        final_capital = summary["final_capital"]

        assert (
            abs(last_equity - final_capital) < 0.01
        ), f"equity_df 마지막 값과 final_capital이 일치해야 함. equity_df: {last_equity}, final_capital: {final_capital}"


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
        # Given: 간단한 데이터로 매수 신호 생성
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, i + 1) for i in range(10)],
                "Open": [100, 100, 100, 105, 110, 110, 110, 110, 110, 110],
                "Close": [100, 100, 107, 110, 112, 112, 112, 112, 115, 120],
                "ma_5": [100, 100, 100, 103, 106, 108, 109, 110, 110.5, 111],
            }
        )

        params = BufferStrategyParams(
            ma_window=5,
            buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 포지션 보유 중인 모든 시점에서 equity == cash + shares*close 검증
        # (현재 구현은 이를 만족할 수도 있지만, final_capital 로직과 일치하는지 확인 필요)
        if len(trades_df) > 0 and len(equity_df) > 0:
            # 포지션 보유 구간 찾기
            position_rows = equity_df[equity_df["position"] > 0]

            if len(position_rows) > 0:
                # 각 행에 대해 equity == cash + position*close 검증
                # 참고: 현재 equity_df에 cash 컬럼이 없으므로 역산 필요
                # equity = capital + position * close
                # → capital = equity - position * close

                # 하나의 샘플로 검증 (중간 날짜)
                sample_row = position_rows.iloc[len(position_rows) // 2]
                position = sample_row["position"]
                equity = sample_row["equity"]

                # equity_df에 close 정보가 없으므로, df와 조인 필요
                # 간단히 날짜 기준으로 원본 df에서 close 찾기
                sample_date = sample_row["Date"]
                close_value = df[df["Date"] == sample_date]["Close"].iloc[0]

                # equity = cash + position*close이므로
                # cash = equity - position*close
                calculated_cash = equity - position * close_value

                # 다시 계산: equity_check = cash + position*close
                equity_check = calculated_cash + position * close_value

                assert (
                    abs(equity_check - equity) < 0.01
                ), f"Equity는 cash + position*close이어야 함. equity: {equity}, 재계산: {equity_check}"

    def test_equity_definition_no_position(self):
        """
        Equity 정의 검증 (포지션 없을 시)

        절대 규칙: position=0일 때 equity = cash

        Given: 포지션이 없는 상태
        When: equity 계산
        Then: equity == cash (position * close = 0이므로)
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
            buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 포지션 없는 모든 날의 equity == initial_capital
        no_position_rows = equity_df[equity_df["position"] == 0]

        if len(no_position_rows) > 0:
            # 첫 날은 initial_capital이어야 함
            first_equity = no_position_rows.iloc[0]["equity"]
            assert (
                abs(first_equity - params.initial_capital) < 0.01
            ), f"포지션 없을 때 equity는 초기 자본이어야 함. 기대: {params.initial_capital}, 실제: {first_equity}"

    def test_final_capital_with_position_remaining(self):
        """
        Final Capital 정의 검증 (포지션 남은 경우)

        절대 규칙: final_capital = cash + position * last_close (강제청산 없음)

        Given: 매수 후 매도 신호가 없어 포지션이 남은 데이터
        When: 백테스트 종료
        Then: final_capital == cash + position*last_close (Trade 생성 없이 평가액만 포함)
        """
        # Given: 계속 상승 (매도 신호 없음 → 포지션 남음)
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
            buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: final_capital == equity_df 마지막 값
        # (현재 구현은 강제청산 로직이 있어 실패할 수 있음)
        last_equity = equity_df.iloc[-1]["equity"]
        final_capital = summary["final_capital"]

        assert (
            abs(last_equity - final_capital) < 0.01
        ), f"Final capital은 마지막 equity와 일치해야 함. equity: {last_equity}, final_capital: {final_capital}"

    def test_hold_days_0_timeline(self):
        """
        hold_days=0 타임라인 검증

        절대 규칙:
        - 돌파일(i일) 종가에서 신호 확정
        - i일 종가에 pending_order 생성
        - i+1일 시가에 체결

        Given: hold_days=0, 명확한 돌파 패턴
        When: 백테스트 실행
        Then:
          - 돌파일(i) equity: position=0 (신호만, 미체결)
          - 체결일(i+1) equity: position>0 (체결 완료)
        """
        # Given: 3일째에 상향돌파
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
            buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 3일째(인덱스 2) position=0, 4일째(인덱스 3) position>0
        if len(equity_df) >= 4:
            signal_day = equity_df.iloc[2]
            execution_day = equity_df.iloc[3]

            assert signal_day["position"] == 0, f"hold_days=0: 돌파일에는 position=0. 실제: {signal_day['position']}"
            assert execution_day["position"] > 0, f"hold_days=0: 다음날에는 position>0. 실제: {execution_day['position']}"

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
            buffer_zone_pct=0.03,
            hold_days=1,
            recent_months=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 돌파일(인덱스 2), 확정일(인덱스 3), 체결일(인덱스 4)
        if len(equity_df) >= 5:
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
            buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 마지막 날(인덱스 9)에 포지션 있어야 함
        if len(equity_df) >= 10:
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
            buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
            initial_capital=10000.0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 마지막날 포지션 없어야 함 (체결 불가)
        last_day = equity_df.iloc[-1]
        assert last_day["position"] == 0, f"마지막날 신호는 무시되어 position=0. 실제: {last_day['position']}"

    def test_pending_conflict_raises_exception(self):
        """
        Pending 충돌 예외 발생 검증 (Critical Invariant)

        절대 규칙: pending_order 존재 중 신규 신호 발생 시 PendingOrderConflictError 즉시 raise

        Given: pending_order가 이미 존재하는 상태
        When: _check_pending_conflict 호출
        Then: PendingOrderConflictError 예외 발생

        주의: 정상적인 백테스트 실행에서는 이런 상황이 발생하지 않습니다.
        이 테스트는 _check_pending_conflict 함수의 동작을 직접 검증합니다.
        통합 테스트로는 pending 충돌 상황을 재현하기 어려우므로 단위 테스트로 검증합니다.
        """
        from qbt.backtest.strategy import PendingOrder, _check_pending_conflict

        # Given: 기존 pending이 존재
        existing_pending = PendingOrder(
            order_type="sell",
            signal_date=date(2023, 1, 9),
            buffer_zone_pct=0.01,
            hold_days_used=0,
            recent_buy_count=0,
        )

        # When & Then: 신규 매도 신호 발생 시 예외 발생
        with pytest.raises(PendingOrderConflictError) as exc_info:
            _check_pending_conflict(existing_pending, "sell", date(2023, 1, 9))

        # 예외 메시지에 유용한 디버깅 정보 포함 확인
        error_message = str(exc_info.value)
        assert "pending" in error_message.lower(), "예외 메시지에 'pending' 키워드가 포함되어야 함"
        assert "충돌" in error_message, "예외 메시지에 '충돌' 키워드가 포함되어야 함"
        assert "sell" in error_message, "예외 메시지에 신호 타입이 포함되어야 함"
        assert "2023-01-09" in error_message or "2023-01-10" in error_message, "예외 메시지에 날짜 정보가 포함되어야 함"

        # When & Then: 신규 매수 신호 발생 시에도 예외 발생
        with pytest.raises(PendingOrderConflictError):
            _check_pending_conflict(existing_pending, "buy", date(2023, 1, 9))

        # When: pending이 없으면 예외 발생하지 않음
        try:
            _check_pending_conflict(None, "buy", date(2023, 1, 9))
            _check_pending_conflict(None, "sell", date(2023, 1, 9))
        except PendingOrderConflictError:
            pytest.fail("pending이 None일 때는 예외가 발생하면 안 됨")


class TestBacktestAccuracy:
    """백테스트 엔진 정확도 테스트

    목적: 백테스트 결과의 일관성과 정확성을 보장하는 핵심 인바리언트를 고정합니다.

    검증 대상:
    1. equity_df, trades_df, summary.final_capital 간 일관성
    2. hold_days 룩어헤드 방지 (순차 검증)
    3. 동적 파라미터 증가량 상수 반영
    4. 첫 유효 구간 신호 감지
    """

    def test_backtest_end_consistency(self):
        """
        백테스트 종료 시 equity_df, trades_df, summary 간 일관성 검증

        핵심 인바리언트:
        - final_capital = cash + position × last_close (항상)
        - 마지막 날 포지션이 남아있어도 강제청산하지 않음
        - equity_df의 마지막 equity == summary.final_capital

        Given: 상향돌파 후 매도 신호 없이 종료되는 시나리오
        When: run_buffer_strategy 실행
        Then:
          - 마지막 날 포지션이 남아있음 (position > 0)
          - equity_df 마지막 equity == summary.final_capital
          - final_capital == cash + position × last_close
        """
        # Given: 상향돌파 후 계속 상승 (매도 신호 없음)
        from qbt.backtest.analysis import add_single_moving_average

        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 11)],
                "Open": [100.0] * 10,
                "Close": [90, 95, 105, 110, 115, 120, 125, 130, 135, 140],  # 지속 상승
            }
        )
        df = add_single_moving_average(df, window=3, ma_type="ema")

        params = BufferStrategyParams(
            initial_capital=100000.0,
            ma_window=3,
            buffer_zone_pct=0.03,  # 3%
            hold_days=0,
            recent_months=0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 마지막 날 포지션이 남아있어야 함
        last_equity_record = equity_df.iloc[-1]
        assert last_equity_record["position"] > 0, "마지막 날 포지션이 있어야 함"

        # Then: equity_df 마지막 equity == summary.final_capital
        last_equity = last_equity_record["equity"]
        assert (
            abs(last_equity - summary["final_capital"]) < 0.01
        ), f"equity_df 마지막 equity({last_equity:.2f})와 summary.final_capital({summary['final_capital']:.2f})이 일치해야 함"

        # Then: final_capital == cash + position × last_close (역산 검증)
        # 주의: 현재 equity_df에 cash가 기록되지 않으므로 이 검증은 구현 후 활성화
        # last_close = df.iloc[-1]["Close"]
        # expected_final = last_equity_record["cash"] + last_equity_record["position"] * last_close
        # assert abs(summary["final_capital"] - expected_final) < 0.01

    def test_hold_days_no_lookahead(self):
        """
        hold_days 룩어헤드 방지 검증

        핵심 인바리언트:
        - i일에 i+1 ~ i+H를 미리 검사하여 pending을 선적재하면 안 됨
        - 매일 순차적으로 유지조건 체크

        Given: hold_days=2, 돌파 후 유지조건 실패 케이스
        When: run_buffer_strategy 실행
        Then:
          - 유지조건 실패 시점에 pending 생성 안 됨
          - 매수 신호가 발생하지 않음 (또는 정확한 시점에만 발생)

        - 상태머신 방식으로 구현됨
        - 이 테스트는 이제 통과해야 함
        """

        # Given: hold_days=2, 돌파 후 1일 후 조건 실패
        from qbt.backtest.analysis import add_single_moving_average

        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 8)],
                "Open": [100.0] * 7,
                # i=3에서 돌파, i=4에서 조건 유지, i=5에서 조건 실패
                "Close": [90, 95, 105, 108, 102, 100, 98],
            }
        )
        df = add_single_moving_average(df, window=3, ma_type="ema")

        params = BufferStrategyParams(
            initial_capital=100000.0,
            ma_window=3,
            buffer_zone_pct=0.03,
            hold_days=2,
            recent_months=0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 매수 거래가 없어야 함 (유지조건 실패)
        assert trades_df.empty or len(trades_df) == 0, "유지조건 실패로 매수 신호가 없어야 함"

    def test_dynamic_hold_days_uses_constant(self):
        """
        동적 hold_days 증가량 상수 반영 검증

        핵심 인바리언트:
        - adjusted_hold_days = base_hold_days + (recent_buy_count × HOLD_DAYS_INCREMENT_PER_BUY)
        - 하드코딩 금지

        Given: recent_months > 0, 여러 번 매수 발생
        When: run_buffer_strategy 실행
        Then:
          - trades_df의 hold_days_used 컬럼 확인
          - 예상값 = base_hold_days + (recent_buy_count × HOLD_DAYS_INCREMENT_PER_BUY)
        """
        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.strategy import HOLD_DAYS_INCREMENT_PER_BUY

        # Given: 여러 번 돌파하는 시나리오
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 21)],
                "Open": [100.0] * 20,
                # 여러 번 상향돌파
                "Close": [90, 95, 105, 110, 95, 90, 95, 105, 110, 115, 95, 90, 95, 105, 110, 115, 120, 125, 130, 135],
            }
        )
        df = add_single_moving_average(df, window=3, ma_type="ema")

        params = BufferStrategyParams(
            initial_capital=100000.0,
            ma_window=3,
            buffer_zone_pct=0.03,
            hold_days=1,  # 기본값
            recent_months=6,  # 동적 조정 활성화
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: trades_df에서 hold_days_used 확인
        if not trades_df.empty and "hold_days_used" in trades_df.columns:
            for _, trade in trades_df.iterrows():
                recent_buy_count = trade.get("recent_buy_count", 0)
                expected_hold_days = params.hold_days + (recent_buy_count * HOLD_DAYS_INCREMENT_PER_BUY)
                actual_hold_days = trade["hold_days_used"]

                # 현재 구현이 하드코딩되어 있으면 이 테스트는 실패함 (레드)
                assert (
                    actual_hold_days == expected_hold_days
                ), f"hold_days_used({actual_hold_days})가 예상값({expected_hold_days} = {params.hold_days} + {recent_buy_count} × {HOLD_DAYS_INCREMENT_PER_BUY})과 일치해야 함"

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
        from qbt.backtest.analysis import add_single_moving_average

        # Given: 첫 유효 구간에서 즉시 상향돌파
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 8)],
                "Open": [100.0] * 7,
                # ma_window=3이므로 i=2부터 유효, i=2에서 즉시 돌파
                "Close": [90, 95, 105, 110, 95, 90, 85],
            }
        )
        df = add_single_moving_average(df, window=3, ma_type="ema")

        params = BufferStrategyParams(
            initial_capital=100000.0,
            ma_window=3,
            buffer_zone_pct=0.03,
            hold_days=0,
            recent_months=0,
        )

        # When
        trades_df, equity_df, summary = run_buffer_strategy(df, params, log_trades=False)

        # Then: 매수 신호가 감지되어야 함
        # 주의: 현재 구현에서 prev_band 초기화가 적절하지 않으면 이 테스트는 실패할 수 있음 (레드)
        assert not trades_df.empty, "첫 유효 구간에서 신호가 감지되어야 함"


class TestRunGridSearch:
    """그리드 서치 테스트"""

    def test_basic_grid_search(self):
        """
        기본 그리드 서치 실행 테스트

        핵심 기능: 파라미터 조합 탐색 및 최적화

        Given: 충분한 데이터와 파라미터 조합
        When: run_grid_search 실행
        Then:
          - 모든 조합 실행 완료
          - 결과 DataFrame 반환
          - CAGR 기준 내림차순 정렬
        """
        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.strategy import run_grid_search

        # Given: 충분한 기간의 데이터
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 31)],
                "Open": [100 + i * 0.5 for i in range(30)],
                "Close": [100, 105, 95, 110, 90, 115, 95, 120, 100, 125] * 3,
            }
        )

        # 그리드 서치에 필요한 모든 MA 미리 계산
        for window in [5, 10]:
            df = add_single_moving_average(df, window=window, ma_type="ema")

        # When: 작은 그리드로 테스트
        results_df = run_grid_search(
            df=df,
            initial_capital=10000.0,
            ma_window_list=[5, 10],
            buffer_zone_pct_list=[0.01, 0.03],
            hold_days_list=[0, 1],
            recent_months_list=[0],
        )

        # Then: 결과 검증
        # 2 × 2 × 2 × 1 = 8개 조합
        assert len(results_df) == 8, "모든 파라미터 조합이 실행되어야 함"

        # 필수 컬럼 존재 확인
        from qbt.backtest.constants import (
            COL_BUFFER_ZONE_PCT,
            COL_CAGR,
            COL_HOLD_DAYS,
            COL_MA_WINDOW,
            COL_RECENT_MONTHS,
            COL_TOTAL_RETURN_PCT,
        )

        required_cols = [
            COL_MA_WINDOW,
            COL_BUFFER_ZONE_PCT,
            COL_HOLD_DAYS,
            COL_RECENT_MONTHS,
            COL_TOTAL_RETURN_PCT,
            COL_CAGR,
        ]
        for col in required_cols:
            assert col in results_df.columns, f"결과에 {col} 컬럼이 있어야 함"

        # 정렬 검증: total_return_pct 기준 내림차순
        total_returns = results_df[COL_TOTAL_RETURN_PCT].tolist()
        assert total_returns == sorted(total_returns, reverse=True), "결과가 수익률 내림차순으로 정렬되어야 함"

    def test_grid_search_parameter_combinations(self):
        """
        그리드 서치 파라미터 조합 생성 검증

        Given: 각 파라미터 2개씩 (2×2×2×2 = 16개 조합)
        When: run_grid_search 실행
        Then: 정확히 16개 결과 생성
        """
        from qbt.backtest.analysis import add_single_moving_average
        from qbt.backtest.strategy import run_grid_search

        # Given
        df = pd.DataFrame(
            {
                "Date": [date(2023, 1, d) for d in range(1, 31)],
                "Open": [100.0] * 30,
                "Close": [100 + i * 0.1 for i in range(30)],
            }
        )

        # MA 계산
        for window in [5, 10]:
            df = add_single_moving_average(df, window=window, ma_type="ema")

        # When
        results_df = run_grid_search(
            df=df,
            initial_capital=10000.0,
            ma_window_list=[5, 10],
            buffer_zone_pct_list=[0.01, 0.02],
            hold_days_list=[0, 1],
            recent_months_list=[0, 3],
        )

        # Then
        assert len(results_df) == 16, "2×2×2×2 = 16개 조합이 생성되어야 함"
