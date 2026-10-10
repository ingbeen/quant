"""WFO 판단 문구 생성 테스트

이 모듈이 고정하는 계약은 "결과가 바뀌면 문장도 바뀐다"이다.
과거에 하드코딩된 해석 문구가 EMA→SMA 전환 후에도 남아
Dynamic/Fixed 대소관계가 뒤집힌 채 반대 결론을 표시한 사고가 있었다.
아래 테스트는 그 재발을 막는 것을 목적으로 한다.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from qbt.backtest.walkforward_verdict import (
    CAGR_SIMILAR_THRESHOLD_PP,
    PC_CONCENTRATION_THRESHOLD,
    STITCHED_CALMAR_GOOD_THRESHOLD,
    WFE_REPRODUCIBLE_THRESHOLD,
    build_is_vs_oos_verdict,
    build_mode_summary_verdict,
    build_param_drift_verdict,
    build_stitched_equity_verdict,
    build_window_schedule_table,
    describe_param_series,
)

# 결론을 가르는 구절 — 수치가 달라 문구가 다른 것과, 결론이 다른 것을 구분해 단언한다
_DYNAMIC_AHEAD = "Dynamic이 Fully Fixed(4P)를 앞섭니다"
_FIXED_AHEAD = "Fully Fixed(4P)가 Dynamic을 앞섭니다"
_SIMILAR = "결과 차이는 크지 않습니다"
_PC_CONCENTRATED = "특정 윈도우에 집중되어 있습니다"
_PC_SPREAD = "고르게 분산되어 있어 양호합니다"
_WFE_NOT_REPRODUCED = "재현되지 않았습니다"
_WFE_REPRODUCED = "그대로 또는 그 이상 재현됐다"
_NO_COLLAPSE = "붕괴 패턴은 나타나지 않습니다"
_MOSTLY_NEGATIVE = "음수 윈도우가 절반 이상"
_MIXED_WINDOWS = "보조 자료로 봅니다"


def _make_mode(
    *,
    stitched_cagr: float = 10.0,
    wfe_calmar_robust: float = 1.0,
    profit_concentration_max: float = 0.3,
    profit_concentration_window_idx: int = 0,
    stitched_calmar: float = 0.5,
    stitched_mdd: float = -20.0,
    param_ma_windows: list[int] | None = None,
    param_buy_buffers: list[float] | None = None,
    param_sell_buffers: list[float] | None = None,
    param_hold_days: list[int] | None = None,
) -> dict[str, Any]:
    """WFO 모드 요약 딕셔너리를 만든다 (테스트 편의용 팩토리)."""
    return {
        "n_windows": 3,
        "stitched_cagr": stitched_cagr,
        "stitched_mdd": stitched_mdd,
        "stitched_calmar": stitched_calmar,
        "wfe_calmar_robust": wfe_calmar_robust,
        "profit_concentration_max": profit_concentration_max,
        "profit_concentration_window_idx": profit_concentration_window_idx,
        "param_ma_windows": param_ma_windows if param_ma_windows is not None else [200, 200, 200],
        "param_buy_buffers": param_buy_buffers if param_buy_buffers is not None else [0.03, 0.03, 0.03],
        "param_sell_buffers": param_sell_buffers if param_sell_buffers is not None else [0.05, 0.05, 0.05],
        "param_hold_days": param_hold_days if param_hold_days is not None else [3, 3, 3],
    }


def _make_summary(dynamic: dict[str, Any], fully_fixed: dict[str, Any]) -> dict[str, Any]:
    """walkforward_summary.json 구조의 딕셔너리를 만든다."""
    return {"strategy": "buffer_zone_test", "dynamic": dynamic, "fully_fixed": fully_fixed}


class TestModeSummaryVerdictDirection:
    """모드 요약 판단이 실제 대소관계를 따라가는지 고정한다.

    핵심 계약: Dynamic이 우세한 입력과 Fixed가 우세한 입력은
    서로 다른 결론을 내야 한다. 이 계약이 깨지면 문구가 데이터와
    무관하게 고정된 것이므로 과거 사고가 재현된 것이다.
    """

    def test_dynamic_superior_is_described_as_dynamic(self) -> None:
        """
        목적: Dynamic CAGR이 명확히 높으면 Dynamic 우세로 서술된다

        Given: Dynamic 19.38%, Fixed 9.25%
        When: build_mode_summary_verdict 호출
        Then: 두 수치가 모두 문구에 나타나고, 결론은 Dynamic 우세다
        """
        # Given
        summaries = {
            "TQQQ": _make_summary(
                dynamic=_make_mode(stitched_cagr=19.38),
                fully_fixed=_make_mode(stitched_cagr=9.25),
            )
        }

        # When
        result = build_mode_summary_verdict(summaries)

        # Then
        assert "19.38" in result
        assert "9.25" in result
        assert _DYNAMIC_AHEAD in result
        assert _FIXED_AHEAD not in result

    def test_direction_flips_when_fixed_is_superior(self) -> None:
        """
        목적: 대소관계가 뒤집히면 결론도 뒤집힌다 (이 모듈의 존재 이유)

        Given: 동일한 두 값을 Dynamic/Fixed에 서로 바꿔 넣은 두 입력
        When: 각각 build_mode_summary_verdict 호출
        Then: 한쪽은 Dynamic 우세, 다른 쪽은 Fixed 우세로 서술된다
        """
        # Given
        dynamic_wins = {
            "QQQ": _make_summary(
                dynamic=_make_mode(stitched_cagr=19.38),
                fully_fixed=_make_mode(stitched_cagr=9.25),
            )
        }
        fixed_wins = {
            "QQQ": _make_summary(
                dynamic=_make_mode(stitched_cagr=9.25),
                fully_fixed=_make_mode(stitched_cagr=19.38),
            )
        }

        # When
        result_dynamic = build_mode_summary_verdict(dynamic_wins)
        result_fixed = build_mode_summary_verdict(fixed_wins)

        # Then
        assert _DYNAMIC_AHEAD in result_dynamic
        assert _FIXED_AHEAD not in result_dynamic
        assert _FIXED_AHEAD in result_fixed
        assert _DYNAMIC_AHEAD not in result_fixed

    def test_small_gap_is_described_as_similar(self) -> None:
        """
        목적: 임계값 미만의 차이는 "비슷"으로 서술된다

        Given: 임계값(1.0%p)보다 작은 0.5%p 차이와, 임계값의 10배 차이
        When: build_mode_summary_verdict 호출
        Then: 작은 차이만 「차이는 크지 않다」로, 큰 차이는 우세로 서술된다
        """
        # Given
        small_gap = {
            "QQQ": _make_summary(
                dynamic=_make_mode(stitched_cagr=10.0),
                fully_fixed=_make_mode(stitched_cagr=10.0 - (CAGR_SIMILAR_THRESHOLD_PP / 2)),
            )
        }
        large_gap = {
            "QQQ": _make_summary(
                dynamic=_make_mode(stitched_cagr=10.0),
                fully_fixed=_make_mode(stitched_cagr=10.0 - (CAGR_SIMILAR_THRESHOLD_PP * 10)),
            )
        }

        # When
        result_small = build_mode_summary_verdict(small_gap)
        result_large = build_mode_summary_verdict(large_gap)

        # Then
        assert _SIMILAR in result_small
        assert _DYNAMIC_AHEAD not in result_small
        assert _SIMILAR not in result_large
        assert _DYNAMIC_AHEAD in result_large


class TestProfitConcentrationThreshold:
    """Profit Concentration 임계값 경계에서 판단이 갈리는지 고정한다."""

    def test_pc_above_threshold_warns_concentration(self) -> None:
        """
        목적: PC가 기준 이상이면 집중 경고가 나온다

        Given: PC 0.90
        When: build_mode_summary_verdict 호출
        Then: 해당 수치와 집중 경고가 문구에 포함된다
        """
        # Given
        summaries = {
            "TQQQ": _make_summary(
                dynamic=_make_mode(profit_concentration_max=0.9024, profit_concentration_window_idx=9),
                fully_fixed=_make_mode(profit_concentration_max=0.6488),
            )
        }

        # When
        result = build_mode_summary_verdict(summaries)

        # Then
        assert "0.9" in result
        assert _PC_CONCENTRATED in result

    def test_pc_at_threshold_warns_concentration(self) -> None:
        """
        목적: PC가 기준과 정확히 같으면 집중 경고다 (기준 「이상」)

        Given: PC = PC_CONCENTRATION_THRESHOLD
        When: build_mode_summary_verdict 호출
        Then: 집중 경고가 나온다
        """
        # Given
        summaries = {
            "QQQ": _make_summary(
                dynamic=_make_mode(profit_concentration_max=PC_CONCENTRATION_THRESHOLD),
                fully_fixed=_make_mode(),
            )
        }

        # When
        result = build_mode_summary_verdict(summaries)

        # Then
        assert _PC_CONCENTRATED in result

    def test_pc_below_and_above_threshold_differ(self) -> None:
        """
        목적: 임계값 경계를 사이에 둔 두 입력은 다른 판단을 낸다

        Given: PC가 임계값 바로 아래인 입력과 바로 위인 입력
        When: 각각 build_mode_summary_verdict 호출
        Then: 아래는 「고르게 분산」, 위는 「집중」으로 서술된다
        """
        # Given
        below = {
            "QQQ": _make_summary(
                dynamic=_make_mode(profit_concentration_max=PC_CONCENTRATION_THRESHOLD - 0.01),
                fully_fixed=_make_mode(),
            )
        }
        above = {
            "QQQ": _make_summary(
                dynamic=_make_mode(profit_concentration_max=PC_CONCENTRATION_THRESHOLD + 0.01),
                fully_fixed=_make_mode(),
            )
        }

        # When
        result_below = build_mode_summary_verdict(below)
        result_above = build_mode_summary_verdict(above)

        # Then
        assert _PC_SPREAD in result_below
        assert _PC_CONCENTRATED not in result_below
        assert _PC_CONCENTRATED in result_above
        assert _PC_SPREAD not in result_above


class TestWfeReproducibility:
    """WFE Calmar Robust 기반 재현성 판정을 고정한다."""

    def test_negative_wfe_is_described_as_not_reproduced(self) -> None:
        """
        목적: WFE가 음수면 OOS 재현 실패로 서술된다

        Given: 두 모드 모두 WFE Calmar Robust -0.0436 (음수)인 입력과, 두 모드 모두 1.15 인 입력
        When: build_mode_summary_verdict 호출
        Then: 음수는 「재현되지 않았다」, 1 이상은 「재현됐다」로 서술된다
        """
        # Given
        negative = {
            "TQQQ": _make_summary(
                dynamic=_make_mode(wfe_calmar_robust=-0.0436),
                fully_fixed=_make_mode(wfe_calmar_robust=-0.0436),
            )
        }
        positive = {
            "TQQQ": _make_summary(
                dynamic=_make_mode(wfe_calmar_robust=1.15),
                fully_fixed=_make_mode(wfe_calmar_robust=1.15),
            )
        }

        # When
        result_negative = build_mode_summary_verdict(negative)
        result_positive = build_mode_summary_verdict(positive)

        # Then
        assert _WFE_NOT_REPRODUCED in result_negative
        assert _WFE_REPRODUCED not in result_negative
        assert _WFE_REPRODUCED in result_positive
        assert _WFE_NOT_REPRODUCED not in result_positive


class TestDescribeParamSeries:
    """윈도우별 파라미터 값 리스트의 서술 계약을 고정한다."""

    def test_constant_series_is_described_as_fixed(self) -> None:
        """
        목적: 전 윈도우가 같은 값이면 고정으로 서술된다

        Given: 모든 윈도우가 200
        When: describe_param_series 호출
        Then: 값 200이 서술에 포함된다
        """
        # Given
        values = [200, 200, 200, 200]

        # When
        result = describe_param_series(values)

        # Then
        assert "200" in result

    def test_changing_series_differs_from_constant(self) -> None:
        """
        목적: 값이 바뀌는 계열은 고정 계열과 다르게 서술된다

        Given: W0~W3=100, W4~=200
        When: describe_param_series 호출
        Then: 고정 계열의 서술과 다르고, 두 값이 모두 나타난다
        """
        # Given
        changing = [100, 100, 100, 100, 200, 200, 200]
        constant = [200, 200, 200, 200, 200, 200, 200]

        # When
        result_changing = describe_param_series(changing)
        result_constant = describe_param_series(constant)

        # Then
        assert result_changing != result_constant
        assert "100" in result_changing
        assert "200" in result_changing

    def test_empty_series_is_safe(self) -> None:
        """
        목적: 빈 입력에서 예외 없이 안전한 문자열을 반환한다

        Given: 빈 리스트
        When: describe_param_series 호출
        Then: 비어있지 않은 문자열이 반환된다 (예외 없음)
        """
        # Given
        values: list[int] = []

        # When
        result = describe_param_series(values)

        # Then
        assert isinstance(result, str)
        assert result != ""


class TestParamDriftVerdict:
    """파라미터 추이 판단 문구가 summary의 param 리스트를 반영하는지 고정한다."""

    def test_param_values_appear_in_verdict(self) -> None:
        """
        목적: summary의 파라미터 리스트 값이 문구에 반영된다

        Given: ma_window가 100에서 200으로 바뀐 dynamic 요약 (나머지 셋은 고정)
        When: build_param_drift_verdict 호출
        Then: 두 값이 모두 문구에 나타나고, 넷 중 셋이 고정이라고 서술된다
        """
        # Given
        summaries = {
            "QQQ": _make_summary(
                dynamic=_make_mode(param_ma_windows=[100, 100, 200, 200]),
                fully_fixed=_make_mode(),
            )
        }

        # When
        result = build_param_drift_verdict(summaries)

        # Then
        assert "100" in result
        assert "200" in result
        assert "네 파라미터 중 3개는 전 구간 고정" in result

    def test_all_fixed_and_all_changing_reach_opposite_conclusions(self) -> None:
        """
        목적: 네 파라미터가 모두 고정인 입력과 모두 바뀌는 입력은 반대 결론을 낸다

        Given: 네 파라미터가 전 윈도우 같은 dynamic 요약과, 네 파라미터가 모두 바뀌는 dynamic 요약
        When: 각각 build_param_drift_verdict 호출
        Then: 앞은 「고정 파라미터 사용의 근거」, 뒤는 「고정값 사용은 신중」으로 서술된다
        """
        # Given
        all_fixed = {"QQQ": _make_summary(dynamic=_make_mode(), fully_fixed=_make_mode())}
        all_changing = {
            "QQQ": _make_summary(
                dynamic=_make_mode(
                    param_ma_windows=[100, 150, 200],
                    param_buy_buffers=[0.01, 0.03, 0.05],
                    param_sell_buffers=[0.05, 0.03, 0.01],
                    param_hold_days=[0, 3, 5],
                ),
                fully_fixed=_make_mode(),
            )
        }

        # When
        result_fixed = build_param_drift_verdict(all_fixed)
        result_changing = build_param_drift_verdict(all_changing)

        # Then
        assert "고정 파라미터 사용의 근거" in result_fixed
        assert "고정값 사용은 신중" not in result_fixed
        assert "고정값 사용은 신중" in result_changing
        assert "고정 파라미터 사용의 근거" not in result_changing


class TestStitchedEquityVerdict:
    """Stitched Equity 판단이 두 모드의 실제 성과를 따라가는지 고정한다."""

    def test_verdict_flips_with_mode_superiority(self) -> None:
        """
        목적: Stitched 성과의 우열이 바뀌면 결론도 바뀐다

        Given: Dynamic 우세 입력과 Fixed 우세 입력 (CAGR 이 높은 쪽의 낙폭이 더 깊다)
        When: 각각 build_stitched_equity_verdict 호출
        Then: CAGR 우세와 낙폭이 얕은 쪽이 입력을 따라 서로 반대로 서술된다
        """
        # Given
        dynamic_wins = {
            "QQQ": _make_summary(
                dynamic=_make_mode(stitched_cagr=9.46, stitched_mdd=-26.43),
                fully_fixed=_make_mode(stitched_cagr=5.16, stitched_mdd=-23.18),
            )
        }
        fixed_wins = {
            "QQQ": _make_summary(
                dynamic=_make_mode(stitched_cagr=5.16, stitched_mdd=-23.18),
                fully_fixed=_make_mode(stitched_cagr=9.46, stitched_mdd=-26.43),
            )
        }

        # When
        result_dynamic = build_stitched_equity_verdict(dynamic_wins)
        result_fixed = build_stitched_equity_verdict(fixed_wins)

        # Then
        assert _DYNAMIC_AHEAD in result_dynamic
        assert _FIXED_AHEAD not in result_dynamic
        assert "Fixed 쪽 낙폭이 더 얕습니다" in result_dynamic
        assert _FIXED_AHEAD in result_fixed
        assert _DYNAMIC_AHEAD not in result_fixed
        assert "Dynamic 쪽 낙폭이 더 얕습니다" in result_fixed

    def test_calmar_verdict_follows_threshold(self) -> None:
        """
        목적: Stitched Calmar 가 기준 이상이면 「양호」, 미만이면 「못 미친다」로 서술된다

        Given: 두 모드 모두 Calmar 1.2 인 입력과, 두 모드 모두 0.5 인 입력
        When: 각각 build_stitched_equity_verdict 호출
        Then: 앞은 「양호한 수준」, 뒤는 「못 미쳐」로 서술된다
        """
        # Given
        good = {
            "QQQ": _make_summary(dynamic=_make_mode(stitched_calmar=1.2), fully_fixed=_make_mode(stitched_calmar=1.2))
        }
        poor = {
            "QQQ": _make_summary(dynamic=_make_mode(stitched_calmar=0.5), fully_fixed=_make_mode(stitched_calmar=0.5))
        }

        # When
        result_good = build_stitched_equity_verdict(good)
        result_poor = build_stitched_equity_verdict(poor)

        # Then
        assert "양호한 수준" in result_good
        assert "못 미쳐" not in result_good
        assert "못 미쳐" in result_poor
        assert "양호한 수준" not in result_poor


class TestIsVsOosVerdict:
    """IS vs OOS 판단이 윈도우별 실제 관계를 반영하는지 고정한다."""

    def test_all_oos_stronger_differs_from_all_weaker(self) -> None:
        """
        목적: OOS가 전부 강한 경우와 전부 약한 경우는 다르게 서술된다

        Given: OOS Calmar가 IS보다 모두 높은 DF와 모두 낮은 DF (음수는 없음)
        When: 각각 build_is_vs_oos_verdict 호출
        Then: 앞은 3개 중 3개가 웃돌아 「붕괴 패턴 없음」, 뒤는 0개가 웃돌아 「보조 자료」로 서술된다
        """
        # Given
        stronger = pd.DataFrame({"window_idx": [0, 1, 2], "is_calmar": [1.0, 1.0, 1.0], "oos_calmar": [2.0, 2.0, 2.0]})
        weaker = pd.DataFrame({"window_idx": [0, 1, 2], "is_calmar": [2.0, 2.0, 2.0], "oos_calmar": [0.1, 0.1, 0.1]})

        # When
        result_stronger = build_is_vs_oos_verdict({"QQQ": stronger})
        result_weaker = build_is_vs_oos_verdict({"QQQ": weaker})

        # Then
        assert "3개 윈도우 중 3개에서" in result_stronger
        assert _NO_COLLAPSE in result_stronger
        assert "3개 윈도우 중 0개에서" in result_weaker
        assert _NO_COLLAPSE not in result_weaker
        assert _MIXED_WINDOWS in result_weaker

    def test_negative_oos_windows_are_counted(self) -> None:
        """
        목적: OOS가 음수인 윈도우 수가 판단에 반영된다

        Given: 3개 윈도우 중 2개의 OOS Calmar가 음수인 DF와, 음수가 없는 DF
        When: build_is_vs_oos_verdict 호출
        Then: 앞은 음수 2개 · 「음수 윈도우가 절반 이상」, 뒤는 음수 0개로 그 경고가 없다
        """
        # Given
        with_negative = pd.DataFrame(
            {"window_idx": [0, 1, 2], "is_calmar": [1.0, 1.0, 1.0], "oos_calmar": [-0.5, -0.3, 1.2]}
        )
        without_negative = pd.DataFrame(
            {"window_idx": [0, 1, 2], "is_calmar": [1.0, 1.0, 1.0], "oos_calmar": [0.5, 0.3, 1.2]}
        )

        # When
        result_with = build_is_vs_oos_verdict({"QQQ": with_negative})
        result_without = build_is_vs_oos_verdict({"QQQ": without_negative})

        # Then
        assert "2개 윈도우는 OOS가 음수" in result_with
        assert _MOSTLY_NEGATIVE in result_with
        assert "0개 윈도우는 OOS가 음수" in result_without
        assert _MOSTLY_NEGATIVE not in result_without


class TestVerdictThresholdBoundaries:
    """값이 기준과 정확히 같을 때 어느 쪽 결론인지 고정한다 (수익 집중도의 경계는 위 클래스에 있다)."""

    def test_cagr_gap_equal_to_threshold_is_not_similar(self) -> None:
        """
        목적: CAGR 차이가 기준과 같으면 「비슷」이 아니다 (기준 「미만」만 비슷)

        Given: Dynamic = CAGR_SIMILAR_THRESHOLD_PP, Fixed = 0.0 (차이가 부동소수 오차 없이 기준과 같다)
        When: build_mode_summary_verdict 호출
        Then: Dynamic 우세로 서술된다
        """
        # Given
        summaries = {
            "QQQ": _make_summary(
                dynamic=_make_mode(stitched_cagr=CAGR_SIMILAR_THRESHOLD_PP),
                fully_fixed=_make_mode(stitched_cagr=0.0),
            )
        }

        # When
        result = build_mode_summary_verdict(summaries)

        # Then
        assert _DYNAMIC_AHEAD in result
        assert _SIMILAR not in result

    def test_wfe_equal_to_reproducible_threshold_is_reproduced(self) -> None:
        """
        목적: WFE 가 재현 기준과 같으면 「재현됐다」다 (기준 「이상」)

        Given: 두 모드 모두 WFE Calmar Robust = WFE_REPRODUCIBLE_THRESHOLD
        When: build_mode_summary_verdict 호출
        Then: 「재현됐다」로 서술된다
        """
        # Given
        mode = _make_mode(wfe_calmar_robust=WFE_REPRODUCIBLE_THRESHOLD)
        summaries = {"QQQ": _make_summary(dynamic=mode, fully_fixed=mode)}

        # When
        result = build_mode_summary_verdict(summaries)

        # Then
        assert _WFE_REPRODUCED in result

    def test_wfe_between_zero_and_threshold_is_partial_reproduction(self) -> None:
        """
        목적: WFE 가 0 초과 · 재현 기준 미만이면 「약 N% 재현」이다 — 「재현됐다」도 「재현되지 않았다」도 아니다

        Given: 두 모드 모두 WFE Calmar Robust = 0.5
        When: build_mode_summary_verdict 호출
        Then: 「약 50%가 OOS에서 재현」으로 서술되고 나머지 두 결론은 없다
        """
        # Given
        mode = _make_mode(wfe_calmar_robust=0.5)
        summaries = {"QQQ": _make_summary(dynamic=mode, fully_fixed=mode)}

        # When
        result = build_mode_summary_verdict(summaries)

        # Then
        assert "약 50%가 OOS에서 재현" in result
        assert _WFE_REPRODUCED not in result
        assert _WFE_NOT_REPRODUCED not in result

    def test_wfe_zero_is_not_reproduced(self) -> None:
        """
        목적: WFE 가 정확히 0 이면 「재현되지 않았다」다 (0 「이하」)

        Given: 두 모드 모두 WFE Calmar Robust = 0.0
        When: build_mode_summary_verdict 호출
        Then: 「재현되지 않았다」로 서술된다
        """
        # Given
        mode = _make_mode(wfe_calmar_robust=0.0)
        summaries = {"QQQ": _make_summary(dynamic=mode, fully_fixed=mode)}

        # When
        result = build_mode_summary_verdict(summaries)

        # Then
        assert _WFE_NOT_REPRODUCED in result

    def test_calmar_equal_to_threshold_is_good(self) -> None:
        """
        목적: Stitched Calmar 가 기준과 같으면 「양호」다 (기준 「이상」)

        Given: 두 모드 모두 Stitched Calmar = STITCHED_CALMAR_GOOD_THRESHOLD
        When: build_stitched_equity_verdict 호출
        Then: 「양호한 수준」으로 서술된다
        """
        # Given
        mode = _make_mode(stitched_calmar=STITCHED_CALMAR_GOOD_THRESHOLD)
        summaries = {"QQQ": _make_summary(dynamic=mode, fully_fixed=mode)}

        # When
        result = build_stitched_equity_verdict(summaries)

        # Then
        assert "양호한 수준" in result

    def test_exactly_half_windows_stronger_is_no_collapse(self) -> None:
        """
        목적: OOS 가 IS 를 웃돈 윈도우가 정확히 절반이고 음수가 없으면 「붕괴 패턴 없음」이다 (절반 「이상」)

        Given: 윈도우 2개 — 하나만 OOS Calmar 가 IS 보다 높고 음수는 없음
        When: build_is_vs_oos_verdict 호출
        Then: 「붕괴 패턴은 나타나지 않습니다」로 서술된다
        """
        # Given
        window_df = pd.DataFrame({"window_idx": [0, 1], "is_calmar": [1.0, 1.0], "oos_calmar": [2.0, 0.5]})

        # When
        result = build_is_vs_oos_verdict({"QQQ": window_df})

        # Then
        assert _NO_COLLAPSE in result

    def test_exactly_half_windows_negative_is_mostly_negative(self) -> None:
        """
        목적: OOS 가 음수인 윈도우가 정확히 절반이면 「음수 윈도우가 절반 이상」이다

        Given: 윈도우 2개 — 하나의 OOS Calmar 가 음수
        When: build_is_vs_oos_verdict 호출
        Then: 「음수 윈도우가 절반 이상」으로 서술된다
        """
        # Given
        window_df = pd.DataFrame({"window_idx": [0, 1], "is_calmar": [1.0, 1.0], "oos_calmar": [-0.5, 2.0]})

        # When
        result = build_is_vs_oos_verdict({"QQQ": window_df})

        # Then
        assert _MOSTLY_NEGATIVE in result


class TestWindowScheduleTable:
    """윈도우 기간 표가 결과 파일의 실제 날짜를 따라가는지 고정한다.

    과거에는 이 표가 정적 텍스트여서 마지막 윈도우의 OOS 종료일이
    데이터 갱신 후에도 갱신되지 않은 채 남아 있었다.
    """

    def test_table_uses_actual_dates(self) -> None:
        """
        목적: 표의 기간이 DataFrame 값에서 생성된다

        Given: OOS 종료일이 2026-08-21인 윈도우
        When: build_window_schedule_table 호출
        Then: 해당 연월이 표에 나타난다
        """
        # Given
        window_df = pd.DataFrame(
            {
                "window_idx": [0],
                "is_start": ["1999-03-10"],
                "is_end": ["2005-02-28"],
                "oos_start": ["2025-03-01"],
                "oos_end": ["2026-08-21"],
            }
        )

        # When
        result = build_window_schedule_table({"QQQ": window_df})

        # Then
        assert "2026-08" in result
        assert "1999-03" in result

    def test_strategies_with_different_end_dates_are_separated(self) -> None:
        """
        목적: 전략마다 종료일이 다르면 각각의 날짜가 모두 표시된다

        Given: 마지막 OOS 종료일이 서로 다른 두 전략
        When: build_window_schedule_table 호출
        Then: 두 종료일이 모두 나타난다
        """

        # Given
        def _df(oos_end: str) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "window_idx": [10],
                    "is_start": ["1999-03-10"],
                    "is_end": ["2025-02-28"],
                    "oos_start": ["2025-03-01"],
                    "oos_end": [oos_end],
                }
            )

        # When
        result = build_window_schedule_table({"QQQ": _df("2026-08-21"), "TQQQ": _df("2026-03-12")})

        # Then
        assert "2026-08" in result
        assert "2026-03" in result

    def test_empty_input_returns_empty_string(self) -> None:
        """
        목적: 빈 입력에서 빈 문자열을 반환한다

        Given: 빈 딕셔너리
        When: build_window_schedule_table 호출
        Then: 빈 문자열이 반환된다
        """
        # Given / When
        result = build_window_schedule_table({})

        # Then
        assert result == ""


class TestMissingDataSafety:
    """결측 입력에서 예외 없이 동작하는지 고정한다.

    대시보드는 결과 파일이 부분적으로만 존재할 수 있으므로,
    키가 없어도 화면 전체가 깨지지 않아야 한다.
    """

    def test_empty_input_returns_empty_string(self) -> None:
        """
        목적: 빈 입력에서 빈 문자열을 반환한다

        Given: 빈 딕셔너리
        When: 각 build 함수 호출
        Then: 모두 빈 문자열을 반환한다 (예외 없음)
        """
        # Given
        empty: dict[str, dict[str, object]] = {}

        # When / Then
        assert build_mode_summary_verdict(empty) == ""
        assert build_stitched_equity_verdict(empty) == ""
        assert build_param_drift_verdict(empty) == ""
        assert build_is_vs_oos_verdict({}) == ""

    def test_missing_keys_do_not_raise(self) -> None:
        """
        목적: 필수 키가 없어도 예외를 던지지 않는다

        Given: dynamic/fully_fixed가 비어있는 요약
        When: build_mode_summary_verdict 호출
        Then: 문자열이 반환된다 (예외 없음)
        """
        # Given
        summaries: dict[str, dict[str, object]] = {"QQQ": {"strategy": "x", "dynamic": {}, "fully_fixed": {}}}

        # When
        result = build_mode_summary_verdict(summaries)

        # Then
        assert isinstance(result, str)

    def test_empty_dataframe_does_not_raise(self) -> None:
        """
        목적: 빈 DataFrame에서 예외를 던지지 않는다

        Given: 컬럼만 있고 행이 없는 DataFrame
        When: build_is_vs_oos_verdict 호출
        Then: 문자열이 반환된다 (예외 없음)
        """
        # Given
        empty_df = pd.DataFrame({"window_idx": [], "is_calmar": [], "oos_calmar": []})

        # When
        result = build_is_vs_oos_verdict({"QQQ": empty_df})

        # Then
        assert isinstance(result, str)
