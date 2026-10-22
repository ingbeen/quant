"""WFO 판단 문구 생성 모듈

워크포워드 결과(`walkforward_summary.json`, 윈도우별 결과 DataFrame)로부터
대시보드에 표시할 "현재 지표 해석 & 판단" 문장을 생성한다.

수치와 대소관계를 결과 파일에서 직접 읽어 서술하므로,
워크포워드를 재실행해 결과가 바뀌면 문장도 함께 따라온다.
결과 파일에 있어야 할 키가 없으면 KeyError 로 멈춘다 — 「데이터 없음」으로 넘기면 저장 형식이 바뀐 것이 화면에서 가려진다.

용어 설명과 해석 방법처럼 데이터와 무관한 설명은 이 모듈의 책임이 아니며,
대시보드가 정적 텍스트로 유지한다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from qbt.backtest.constants import (
    KEY_WFO_DYNAMIC,
    KEY_WFO_FULLY_FIXED,
    PC_CONCENTRATION_THRESHOLD,
    STITCHED_CALMAR_GOOD_THRESHOLD,
    WFO_PARAM_SPECS,
)
from qbt.common_constants import ANNUAL_DAYS

# WFE Calmar Robust 가 이 이상이면 IS 성과가 OOS 에서 재현됐다고 쓴다. 1 은 「OOS 성과 = IS 성과」라는 뜻이고
# 재현 문구(「그대로 또는 그 이상 재현됐다」)가 이 뜻으로 쓰여 있다 — 1 이 아닌 값으로 바꾸면 그 문구도 다시 쓴다
WFE_REPRODUCIBLE_THRESHOLD = 1.0

# 두 모드의 CAGR 차이를 "사실상 비슷"으로 볼 상한 (%p) — 이보다 작은 차이로는 우열을 말하지 않는다
CAGR_SIMILAR_THRESHOLD_PP = 1.0

_LABEL_DYNAMIC = "Dynamic"
_LABEL_FIXED = "Fixed"


def _format_number(value: float) -> str:
    """정수로 떨어지는 값은 정수로, 그 외는 소수점 이하를 정리해 표기한다."""
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def _window_label(idx: float) -> str:
    """윈도우 인덱스를 W 표기로 바꾼다."""
    return f"W{int(idx)}"


# 4P 는 전 기간을 보고 정했으므로 OOS 구간도 4P 에게는 본 구간이다 — 4P 가 앞서는 것만으로 동결의 근거가 되지 않는다
_HINDSIGHT_NOTE = "다만 4P 는 전 기간을 보고 정한 값이라 이 비교는 4P 에 유리하고, 4P 를 확정한 뒤의 구간에서만 독립적인 점검입니다."


def _describe_cagr_gap(dynamic_cagr: float, fixed_cagr: float) -> tuple[str, str]:
    """두 모드의 Stitched CAGR 관계를 (한 줄 요약, 상세 서술)로 서술한다.

    Args:
        dynamic_cagr: Dynamic 모드 Stitched CAGR (%)
        fixed_cagr: Fully Fixed(4P 고정) 모드 Stitched CAGR (%)

    Returns:
        (한 줄 요약, 상세 서술) 튜플
    """
    gap = dynamic_cagr - fixed_cagr
    abs_gap = abs(gap)
    detail_head = f"Stitched CAGR은 {_LABEL_DYNAMIC} {dynamic_cagr:.2f}%, {_LABEL_FIXED} {fixed_cagr:.2f}%입니다."

    if abs_gap < CAGR_SIMILAR_THRESHOLD_PP:
        summary = f"**파라미터를 매번 바꾸든 확정값(4P)으로 고정하든 결과 차이는 크지 않습니다.** {_HINDSIGHT_NOTE}"
        detail = f"{detail_head} 차이는 {abs_gap:.2f}%p로 사실상 비슷한 수준입니다."
        return summary, detail

    if gap > 0:
        summary = "**Dynamic이 Fully Fixed(4P)를 앞섭니다.** 4P 에 유리한 비교인데도 윈도우마다 다시 고른 쪽이 앞섰습니다."
        detail = f"{detail_head} {_LABEL_DYNAMIC}이 {abs_gap:.2f}%p 높습니다."
        return summary, detail

    summary = f"**Fully Fixed(4P)가 Dynamic을 앞섭니다.** {_HINDSIGHT_NOTE}"
    detail = f"{detail_head} {_LABEL_FIXED}가 {abs_gap:.2f}%p 높습니다."
    return summary, detail


def _cagr_gap_lines(dynamic: Mapping[str, Any], fixed: Mapping[str, Any]) -> list[str]:
    """두 모드의 Stitched CAGR 관계를 (한 줄 요약, 상세 서술) 두 줄로 만든다."""
    summary_line, detail_line = _describe_cagr_gap(dynamic["stitched_cagr"], fixed["stitched_cagr"])
    return [f"- 한 줄 요약: {summary_line}", f"- {detail_line}"]


def _describe_wfe(dynamic_wfe: float, fixed_wfe: float) -> str:
    """WFE Calmar Robust로 OOS 재현성을 서술한다.

    재현성은 Dynamic 값으로만 판단한다 — 4P 는 OOS 를 포함한 전 기간을 보고 정한 값이라 그 값은 OOS 재현을 재지 않는다.
    """
    head = (
        f"WFE Calmar Robust는 {_LABEL_DYNAMIC} {dynamic_wfe:.2f}, {_LABEL_FIXED} {fixed_wfe:.2f}입니다. "
        f"{_LABEL_FIXED}(4P)의 값은 과최적화를 재지 않습니다 — 4P 는 OOS 를 포함한 전 기간을 보고 정했습니다."
    )

    if dynamic_wfe <= 0:
        tail = f"{_LABEL_DYNAMIC}이 0 이하라 IS 성과가 OOS에서 재현되지 않았습니다. 과최적화를 의심해야 합니다."
    elif dynamic_wfe >= WFE_REPRODUCIBLE_THRESHOLD:
        tail = (
            f"{_LABEL_DYNAMIC}이 {WFE_REPRODUCIBLE_THRESHOLD:g} 이상이라 IS 성과가 OOS에서 그대로 또는 그 이상 재현됐다는 뜻입니다. "
            "다만 이 지표 하나로 robustness를 단정하기보다 보조 근거로 봅니다."
        )
    else:
        tail = f"{_LABEL_DYNAMIC} 기준으로 IS 성과의 약 {dynamic_wfe * 100:.0f}%가 OOS에서 재현된다는 뜻으로, 보조 검증 근거로 해석합니다."

    return f"{head} {tail}"


def _describe_profit_concentration(mode: Mapping[str, Any]) -> str:
    """Profit Concentration 최대값으로 수익 집중도를 서술한다.

    이어 붙인 자본곡선이 손실이면 서술하지 않는다 — 기여 비중은 전체 순이익이 양수일 때만 정의되어,
    요약의 PC 는 그때 측정값이 아니라 자리표시 0(최대 기여 윈도우 W0)이다(`walkforward._calculate_profit_concentration`).
    """
    if mode["stitched_cagr"] <= 0:
        return "PC — 이어 붙인 자본곡선이 손실이라 수익 집중도를 재지 않습니다(기여 비중은 전체 순이익이 양수일 때만 정의됩니다)."

    pc = mode["profit_concentration_max"]
    where = f" (최대 기여 윈도우 {_window_label(mode['profit_concentration_window_idx'])})"

    if pc >= PC_CONCENTRATION_THRESHOLD:
        return (
            f"PC 최대 {pc:.2f}{where} — 기준 {PC_CONCENTRATION_THRESHOLD} 이상으로 수익이 특정 윈도우에 집중되어 있습니다. "
            "특정 구간 의존성이 크다는 점에서 리스크 요인으로 해석해야 합니다."
        )
    return f"PC 최대 {pc:.2f}{where} — 기준 {PC_CONCENTRATION_THRESHOLD} 미만으로 " "수익이 비교적 고르게 분산되어 있어 양호합니다."


def _render_blocks(blocks: list[str]) -> str:
    """전략별 블록을 하나의 마크다운 문자열로 합친다."""
    return "\n\n".join(blocks) if blocks else ""


def build_mode_summary_verdict(summaries_by_label: Mapping[str, Mapping[str, Any]]) -> str:
    """모드별 요약 비교 섹션의 판단 문구를 생성한다.

    Args:
        summaries_by_label: 표시명 -> walkforward_summary.json 딕셔너리

    Returns:
        마크다운 문자열. 입력이 비어 있으면 빈 문자열
    """
    blocks: list[str] = []

    for label, summary in summaries_by_label.items():
        dynamic = summary[KEY_WFO_DYNAMIC]
        fixed = summary[KEY_WFO_FULLY_FIXED]
        lines: list[str] = [
            f"**{label}**:",
            "",
            *_cagr_gap_lines(dynamic, fixed),
            f"- {_describe_wfe(dynamic['wfe_calmar_robust'], fixed['wfe_calmar_robust'])}",
            f"- {_describe_profit_concentration(dynamic)}",
        ]
        blocks.append("\n".join(lines))

    return _render_blocks(blocks)


def build_stitched_equity_verdict(summaries_by_label: Mapping[str, Mapping[str, Any]]) -> str:
    """Stitched Equity 곡선 섹션의 판단 문구를 생성한다.

    Args:
        summaries_by_label: 표시명 -> walkforward_summary.json 딕셔너리

    Returns:
        마크다운 문자열. 입력이 비어 있으면 빈 문자열
    """
    blocks: list[str] = []

    for label, summary in summaries_by_label.items():
        dynamic = summary[KEY_WFO_DYNAMIC]
        fixed = summary[KEY_WFO_FULLY_FIXED]

        dynamic_mdd = dynamic["stitched_mdd"]
        fixed_mdd = fixed["stitched_mdd"]
        shallower = _LABEL_DYNAMIC if dynamic_mdd > fixed_mdd else _LABEL_FIXED

        # 양호 판단은 Dynamic 값으로만 한다 — 4P 의 Calmar 는 전 기간을 보고 정한 값의 성과라 OOS 성과가 아니다
        dynamic_calmar = dynamic["stitched_calmar"]
        verdict = (
            f"{_LABEL_DYNAMIC}의 위험 대비 수익이 양호한 수준입니다."
            if dynamic_calmar >= STITCHED_CALMAR_GOOD_THRESHOLD
            else f"{_LABEL_DYNAMIC}이 {STITCHED_CALMAR_GOOD_THRESHOLD}에 못 미쳐 수익 대비 낙폭 부담이 큽니다."
        )

        lines: list[str] = [
            f"**{label}**:",
            "",
            *_cagr_gap_lines(dynamic, fixed),
            f"- 최대 낙폭은 {_LABEL_DYNAMIC} {dynamic_mdd:.2f}%, {_LABEL_FIXED} {fixed_mdd:.2f}%로 "
            f"{shallower} 쪽 낙폭이 더 얕습니다.",
            f"- Stitched Calmar는 {_LABEL_DYNAMIC} {dynamic_calmar:.2f}, "
            f"{_LABEL_FIXED} {fixed['stitched_calmar']:.2f}입니다. {verdict}",
        ]
        blocks.append("\n".join(lines))

    return _render_blocks(blocks)


def build_is_vs_oos_verdict(windows_by_label: Mapping[str, pd.DataFrame]) -> str:
    """IS vs OOS 성과 비교 섹션의 판단 문구를 생성한다.

    Args:
        windows_by_label: 표시명 -> 윈도우별 WFO 결과 DataFrame (is_calmar, oos_calmar 컬럼 사용)

    Returns:
        마크다운 문자열. 입력이 비어 있으면 빈 문자열
    """
    blocks: list[str] = []

    for label, window_df in windows_by_label.items():
        is_calmar = window_df["is_calmar"]
        oos_calmar = window_df["oos_calmar"]

        total = len(window_df)
        stronger = int((oos_calmar > is_calmar).sum())
        negative = int((oos_calmar < 0).sum())

        lines: list[str] = [
            f"**{label}**:",
            "",
            f"- 전체 {total}개 윈도우 중 {stronger}개에서 OOS Calmar가 IS를 웃돌았고, {negative}개 윈도우는 OOS가 음수입니다.",
        ]

        if negative == 0 and stronger * 2 >= total:
            lines.append("- IS에서만 좋고 OOS에서 무너지는 붕괴 패턴은 나타나지 않습니다.")
        elif negative * 2 >= total:
            lines.append("- 음수 윈도우가 절반 이상이므로, 특정 국면에서 전략이 버티지 못한다는 점을 감안해 보수적으로 해석해야 합니다.")
        else:
            lines.append("- 윈도우별 편차는 있으나 전 구간이 무너지는 형태는 아니므로, 과최적화 여부를 판정하는 보조 자료로 봅니다.")

        blocks.append("\n".join(lines))

    return _render_blocks(blocks)


def build_param_drift_verdict(summaries_by_label: Mapping[str, Mapping[str, Any]]) -> str:
    """파라미터 추이 섹션의 판단 문구를 생성한다.

    Args:
        summaries_by_label: 표시명 -> walkforward_summary.json 딕셔너리

    Returns:
        마크다운 문자열. 입력이 비어 있으면 빈 문자열
    """
    blocks: list[str] = []

    for label, summary in summaries_by_label.items():
        dynamic = summary[KEY_WFO_DYNAMIC]
        lines: list[str] = [f"**{label}** (Dynamic 모드):", ""]

        stable_count = 0
        for param_label, key, is_ratio in WFO_PARAM_SPECS:
            values: list[float] = [float(v) * 100 if is_ratio else float(v) for v in dynamic[key]]
            lines.append(f"- **{param_label}:** {describe_param_series(values)}")
            if len(set(values)) == 1:
                stable_count += 1

        if stable_count == len(WFO_PARAM_SPECS):
            lines.append("- 네 파라미터 모두 전 윈도우에서 동일하게 선택되어, 고정 파라미터 사용의 근거가 됩니다.")
        elif stable_count == 0:
            lines.append("- 모든 파라미터가 윈도우에 따라 달라집니다. 파라미터 안정성이 낮으므로 고정값 사용은 신중해야 합니다.")
        else:
            lines.append(
                f"- 네 파라미터 중 {stable_count}개는 전 구간 고정이고 나머지는 구간에 따라 달라집니다. "
                "파라미터 안정성과 전략 성과 robustness는 분리해서 해석해야 합니다."
            )

        blocks.append("\n".join(lines))

    return _render_blocks(blocks)


def build_window_schedule_table(windows_by_label: Mapping[str, pd.DataFrame]) -> str:
    """윈도우별 IS/OOS 기간을 마크다운 표로 만든다.

    전략마다 데이터 종료일이 달라 마지막 윈도우 길이가 다를 수 있으므로
    전략별로 표를 나누어 생성한다.

    Args:
        windows_by_label: 표시명 -> 윈도우별 WFO 결과 DataFrame

    Returns:
        마크다운 문자열. 입력이 비어 있으면 빈 문자열
    """
    blocks: list[str] = []

    for label, window_df in windows_by_label.items():
        rows: list[str] = [
            f"**{label}**",
            "",
            "| W | IS 기간 | IS 길이 | OOS 기간 |",
            "|---|---------|---------|----------|",
        ]

        for _, row in window_df.iterrows():
            is_start = str(row["is_start"])
            is_end = str(row["is_end"])
            oos_start = str(row["oos_start"])
            oos_end = str(row["oos_end"])
            rows.append(
                f"| {_window_label(float(row['window_idx']))} "
                f"| {is_start[:7]} ~ {is_end[:7]} "
                f"| {_describe_span(is_start, is_end)} "
                f"| {oos_start[:7]} ~ {oos_end[:7]} |"
            )

        blocks.append("\n".join(rows))

    return _render_blocks(blocks)


def _describe_span(start: str, end: str) -> str:
    """ISO 날짜 문자열 두 개의 간격을 "약 N년" 형태로 서술한다."""
    years = (pd.Timestamp(end) - pd.Timestamp(start)).days / ANNUAL_DAYS
    if years < 1:
        return f"약 {round(years * 12)}개월"
    return f"약 {round(years)}년"


def describe_param_series(values: Sequence[float | int]) -> str:
    """윈도우별 파라미터 값 리스트를 사람이 읽을 서술로 변환한다.

    전 윈도우가 같은 값이면 고정으로, 값이 바뀌면 전환 지점을 짚어 서술한다.

    Args:
        values: 윈도우 순서대로 선택된 파라미터 값 (1개 이상)

    Returns:
        서술 문자열
    """
    numeric = [float(v) for v in values]
    if len(set(numeric)) == 1:
        return f"전 윈도우 {_format_number(numeric[0])} 고정"

    # 연속으로 같은 값이 이어지는 구간을 묶어 "W0~W3 100" 형태로 서술한다
    segments: list[str] = []
    start = 0
    for i in range(1, len(numeric) + 1):
        if i == len(numeric) or numeric[i] != numeric[start]:
            end = i - 1
            span = f"W{start}" if start == end else f"W{start}~W{end}"
            segments.append(f"{span} {_format_number(numeric[start])}")
            start = i

    return " → ".join(segments)
