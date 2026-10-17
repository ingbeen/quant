"""WFO 윈도우 생성 테스트

generate_wfo_windows()의 Expanding Anchored 및 Rolling 모드 윈도우 생성 계약을 검증한다.
"""

from datetime import date

import pytest

from qbt.backtest.walkforward import generate_wfo_windows


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
        # Given — 6년(72개월) IS + 2년(24개월) OOS = 최소 8년 필요, 5년만 제공
        data_start = date(2020, 1, 1)
        data_end = date(2025, 1, 1)

        # When/Then
        with pytest.raises(ValueError, match="부족"):
            generate_wfo_windows(data_start, data_end, 72, 24)

    @pytest.mark.parametrize(
        "data_end,expected_count,expected_last_oos",
        [
            (date(2025, 3, 3), 10, (date(2023, 3, 1), date(2025, 2, 28))),
            (date(2026, 2, 27), 10, (date(2023, 3, 1), date(2025, 2, 28))),
            (date(2026, 2, 28), 10, (date(2023, 3, 1), date(2025, 2, 28))),
            (date(2026, 3, 1), 11, (date(2025, 3, 1), date(2026, 3, 1))),
        ],
        ids=["oos_first_day", "oos_under_one_year", "oos_twelfth_month_end", "oos_one_year"],
    )
    def test_truncated_last_oos_needs_one_year(self, data_end, expected_count, expected_last_oos):
        """
        목적: 데이터 끝에서 잘린 마지막 OOS 는 데이터가 OOS 시작 1년 뒤 같은 날에 닿을 때만 윈도우가 됨을 검증 — 더 짧은
              OOS 는 연율화가 구간을 늘려 잡아(거래가 없는 며칠은 0, 몇 달은 WFE 가 다른 윈도우의 몇 배) 온전한 윈도우와
              섞이면 요약이 흔들리고, OOS 가 1행이면 백테스트가 「유효 데이터 부족」으로 멈춘다

        Given: 1999-03-01 시작, IS=72개월, OOS=24개월 — 마지막 OOS 가 2025-03-01 에 시작한다
        When: 데이터 끝이 그 OOS 의 첫날 · 1년 직전 · 12개월째 끝날 · 1년 뒤 같은 날로 generate_wfo_windows 호출
        Then: 1년 뒤 같은 날 전이면 그 윈도우가 없고(앞 윈도우가 마지막), 그날이면 데이터 끝까지 잘린 윈도우가 생긴다
        """
        # Given
        data_start = date(1999, 3, 1)

        # When
        windows = generate_wfo_windows(data_start, data_end, 72, 24)

        # Then
        assert len(windows) == expected_count
        assert windows[-1][2:] == expected_last_oos
