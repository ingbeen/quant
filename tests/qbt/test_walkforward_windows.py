"""WFO 윈도우 생성 테스트

generate_wfo_windows()의 Expanding Anchored 및 Rolling 모드 윈도우 생성 계약을 검증한다.
"""

from datetime import date

import pytest


class TestGenerateWfoWindows:
    """WFO 윈도우 생성 함수 테스트."""

    def test_window_count_and_boundaries(self):
        """
        목적: Expanding Anchored 윈도우의 수와 날짜 경계를 검증

        Given: 1999-03 ~ 2025-02 기간, IS=72개월, OOS=24개월
        When: generate_wfo_windows() 호출
        Then: 약 10개 윈도우, 모든 IS는 1999-03-01에서 시작,
              OOS 기간은 24개월씩
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)

        # When
        windows = generate_wfo_windows(data_start, data_end, 72, 24)

        # Then
        assert len(windows) >= 8  # 최소 8개 이상
        assert len(windows) <= 12  # 최대 12개 이하

        # 모든 윈도우의 IS는 data_start에서 시작 (Expanding Anchored)
        for is_start, _, _, _ in windows:
            assert is_start == data_start

        # 각 윈도우의 OOS start는 IS end + 1일
        for _, is_end, oos_start, _ in windows:
            assert oos_start > is_end

        # OOS는 연속적이어야 함
        for i in range(1, len(windows)):
            prev_oos_end = windows[i - 1][3]
            curr_oos_start = windows[i][2]
            # 이전 OOS 종료 다음 달이 현재 OOS 시작
            assert curr_oos_start > prev_oos_end

    def test_insufficient_data_raises_error(self):
        """
        목적: 데이터가 첫 OOS를 만들기에 부족하면 ValueError 발생

        Given: 5년 미만의 데이터 기간
        When: generate_wfo_windows(initial_is=72, oos=24) 호출
        Then: ValueError 발생
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given — 6년(72개월) IS + 2년(24개월) OOS = 최소 8년 필요, 5년만 제공
        data_start = date(2020, 1, 1)
        data_end = date(2025, 1, 1)

        # When/Then
        with pytest.raises(ValueError, match="부족"):
            generate_wfo_windows(data_start, data_end, 72, 24)


class TestRollingWfoWindows:
    """Rolling Window WFO 윈도우 생성 테스트.

    Expanding Anchored WFO와 Rolling WFO가 동일한 OOS 기간을 공유하면서
    IS 시작점만 다르게 동작하는지 검증한다.
    """

    def test_rolling_same_oos_timing(self):
        """
        목적: Rolling과 Expanding의 OOS 기간이 동일한지 검증

        Given: 1999-03 ~ 2025-02 기간, rolling_is_months=120
        When: Expanding과 Rolling 윈도우를 각각 생성
        Then: 모든 윈도우에서 oos_start, oos_end가 동일
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)

        # When
        expanding = generate_wfo_windows(data_start, data_end, 72, 24)
        rolling = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=120)

        # Then — 윈도우 수가 동일
        assert len(expanding) == len(rolling)

        # 모든 윈도우에서 OOS 기간이 동일
        for exp_w, roll_w in zip(expanding, rolling, strict=True):
            assert exp_w[2] == roll_w[2], "oos_start가 동일해야 함"
            assert exp_w[3] == roll_w[3], "oos_end가 동일해야 함"

    def test_rolling_is_start_diverges(self):
        """
        목적: 특정 윈도우부터 Rolling IS 시작점이 Expanding과 달라지는지 검증

        Given: 1999-03 ~ 2025-02 기간, rolling_is_months=120
        When: Expanding과 Rolling 윈도우를 각각 생성
        Then: 초기 윈도우에서는 동일하다가 IS가 120개월을 초과하는 시점부터 분기
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)

        # When
        expanding = generate_wfo_windows(data_start, data_end, 72, 24)
        rolling = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=120)

        # Then — 초기 윈도우에서는 IS 시작이 동일(Expanding IS ≤ 120개월)
        # 후반 윈도우에서는 Rolling IS 시작이 더 늦음
        found_divergence = False
        for exp_w, roll_w in zip(expanding, rolling, strict=True):
            if exp_w[0] != roll_w[0]:
                found_divergence = True
                # Rolling IS 시작은 Expanding보다 늦어야 함
                assert roll_w[0] > exp_w[0]
                # Rolling IS 시작은 data_start 이후
                assert roll_w[0] >= data_start

        assert found_divergence, "Rolling에서 IS 시작점이 분기되는 윈도우가 없음"

    def test_rolling_is_length_capped(self):
        """
        목적: Rolling IS 길이가 rolling_is_months를 초과하지 않는지 검증

        Given: 1999-03 ~ 2025-02 기간, rolling_is_months=120
        When: Rolling 윈도우를 생성
        Then: 모든 윈도우에서 IS 길이(개월) ≤ rolling_is_months
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)
        rolling_is_months = 120

        # When
        rolling = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=rolling_is_months)

        # Then — 모든 윈도우에서 IS 길이 ≤ 120개월
        for is_start, is_end, _, _ in rolling:
            # 월 단위 길이 계산
            is_months = (is_end.year - is_start.year) * 12 + (is_end.month - is_start.month)
            # IS 종료가 IS 시작 월 + rolling_is_months 이내
            assert is_months <= rolling_is_months, f"IS 길이 {is_months}개월이 {rolling_is_months}개월 초과: {is_start}~{is_end}"

    def test_rolling_none_preserves_expanding(self):
        """
        목적: rolling_is_months=None이면 기존 Expanding 동작과 동일한지 검증

        Given: 1999-03 ~ 2025-02 기간
        When: rolling_is_months=None과 rolling_is_months 미지정으로 각각 생성
        Then: 두 결과가 완전히 동일
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)

        # When
        default = generate_wfo_windows(data_start, data_end, 72, 24)
        explicit_none = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=None)

        # Then — 완전히 동일
        assert default == explicit_none

    def test_rolling_early_windows_identical(self):
        """
        목적: Rolling에서 IS < rolling_is_months인 초기 윈도우가
              Expanding과 동일한지 검증

        Given: 1999-03 ~ 2025-02 기간, rolling_is_months=120
        When: 두 모드의 윈도우를 생성
        Then: IS 기간이 120개월 미만인 윈도우들은 두 모드에서 동일
        """
        from qbt.backtest.walkforward import generate_wfo_windows

        # Given
        data_start = date(1999, 3, 1)
        data_end = date(2025, 2, 28)
        rolling_is_months = 120

        # When
        expanding = generate_wfo_windows(data_start, data_end, 72, 24)
        rolling = generate_wfo_windows(data_start, data_end, 72, 24, rolling_is_months=rolling_is_months)

        # Then — 초기 윈도우(IS < 120개월)에서는 완전히 동일
        for exp_w, roll_w in zip(expanding, rolling, strict=True):
            exp_is_months = (exp_w[1].year - exp_w[0].year) * 12 + (exp_w[1].month - exp_w[0].month)
            if exp_is_months < rolling_is_months:
                assert exp_w == roll_w, (
                    f"IS {exp_is_months}개월 < {rolling_is_months}개월인데 " f"Expanding({exp_w})과 Rolling({roll_w})이 다름"
                )
