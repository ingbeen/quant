"""WFO 판단 문구 생성 모듈

워크포워드 결과(`walkforward_summary.json`, 윈도우별 결과 DataFrame)로부터
대시보드에 표시할 "현재 지표 해석 & 판단" 문장을 생성한다.

수치와 대소관계를 결과 파일에서 직접 읽어 서술하므로,
워크포워드를 재실행해 결과가 바뀌면 문장도 함께 따라온다.

용어 설명과 해석 방법처럼 데이터와 무관한 설명은 이 모듈의 책임이 아니며,
대시보드가 정적 텍스트로 유지한다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pandas as pd

# --- 판단 임계값 ---
# 근거: 대시보드 「지표를 해석하는 방법」 블록이 명시한 기준을 그대로 상수화한다.

# Profit Concentration 집중 경고 기준 (0.5 = 전체 수익의 50%)
# "0.5 이상이면 수익이 특정 윈도우에 집중되어 있어 전략 안정성에 주의 필요"
PC_CONCENTRATION_THRESHOLD = 0.5

# WFE Calmar Robust 재현성 기준
# "1에 가까우면 IS 성과가 OOS에서도 유지됨. 0 또는 음수면 재현되지 않음"
WFE_REPRODUCIBLE_THRESHOLD = 1.0

# Stitched Calmar 양호 기준
# "1 이상이면 위험 대비 수익이 양호"
STITCHED_CALMAR_GOOD_THRESHOLD = 1.0

# 두 모드의 CAGR 차이를 "사실상 비슷"으로 볼 상한 (%p)
# 근거: 기존 해석이 0.64%p 차이를 "사실상 비슷"으로 판단해온 관행을 상수화한다.
CAGR_SIMILAR_THRESHOLD_PP = 1.0

# 판단 근거가 되는 요약 키
_KEY_DYNAMIC = "dynamic"
_KEY_FULLY_FIXED = "fully_fixed"

_LABEL_DYNAMIC = "Dynamic"
_LABEL_FIXED = "Fixed"

_NO_DATA = "데이터 없음"


def _get_mode(summary: Mapping[str, object], key: str) -> Mapping[str, object]:
    """요약에서 모드 딕셔너리를 안전하게 꺼낸다. 없으면 빈 매핑."""
    mode = summary.get(key)
    return mode if isinstance(mode, Mapping) else {}


def _get_number(mode: Mapping[str, object], key: str) -> float | None:
    """모드 딕셔너리에서 수치를 안전하게 꺼낸다. 없거나 수치가 아니면 None."""
    value = mode.get(key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _get_number_list(mode: Mapping[str, object], key: str) -> list[float]:
    """모드 딕셔너리에서 수치 리스트를 안전하게 꺼낸다. 없으면 빈 리스트."""
    values = mode.get(key)
    if not isinstance(values, Sequence) or isinstance(values, str | bytes):
        return []
    result: list[float] = []
    for item in values:
        if isinstance(item, bool):
            continue
        if isinstance(item, int | float):
            result.append(float(item))
    return result


def _format_number(value: float) -> str:
    """정수로 떨어지는 값은 정수로, 그 외는 소수점 이하를 정리해 표기한다."""
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def _window_label(idx: float) -> str:
    """윈도우 인덱스를 W 표기로 바꾼다."""
    return f"W{int(idx)}"


def _describe_cagr_gap(dynamic_cagr: float, fixed_cagr: float) -> tuple[str, str]:
    """두 모드의 Stitched CAGR 관계를 (한 줄 요약, 상세 서술)로 서술한다.

    Args:
        dynamic_cagr: Dynamic 모드 Stitched CAGR (%)
        fixed_cagr: Fully Fixed 모드 Stitched CAGR (%)

    Returns:
        (한 줄 요약, 상세 서술) 튜플
    """
    gap = dynamic_cagr - fixed_cagr
    abs_gap = abs(gap)
    detail_head = f"Stitched CAGR은 {_LABEL_DYNAMIC} {dynamic_cagr:.2f}%, {_LABEL_FIXED} {fixed_cagr:.2f}%입니다."

    if abs_gap < CAGR_SIMILAR_THRESHOLD_PP:
        summary = "**파라미터를 매번 바꾸든 처음 것을 고정하든 결과 차이는 크지 않습니다.** 고정 파라미터가 충분히 안정적입니다."
        detail = f"{detail_head} 차이는 {abs_gap:.2f}%p로 사실상 비슷한 수준입니다."
        return summary, detail

    if gap > 0:
        summary = "**Dynamic이 Fully Fixed를 앞섭니다.** 윈도우마다 파라미터를 다시 고른 것이 성과에 기여했습니다."
        detail = f"{detail_head} {_LABEL_DYNAMIC}이 {abs_gap:.2f}%p 높습니다."
        return summary, detail

    summary = "**Fully Fixed가 Dynamic을 앞섭니다.** 동적 재최적화가 추가 가치를 만들지 못했습니다."
    detail = f"{detail_head} {_LABEL_FIXED}가 {abs_gap:.2f}%p 높습니다."
    return summary, detail


def _describe_wfe(dynamic_wfe: float | None, fixed_wfe: float | None) -> str:
    """WFE Calmar Robust로 OOS 재현성을 서술한다."""
    parts: list[str] = []
    for label, value in ((_LABEL_DYNAMIC, dynamic_wfe), (_LABEL_FIXED, fixed_wfe)):
        if value is None:
            continue
        parts.append(f"{label} {value:.2f}")
    if not parts:
        return ""

    head = f"WFE Calmar Robust는 {', '.join(parts)}입니다."

    values = [v for v in (dynamic_wfe, fixed_wfe) if v is not None]
    worst = min(values)
    best = max(values)

    if worst <= 0:
        tail = "0 이하인 모드가 있어 IS 성과가 OOS에서 재현되지 않았습니다. 과최적화를 의심해야 합니다."
    elif best >= WFE_REPRODUCIBLE_THRESHOLD:
        tail = "1 이상이면 IS 성과가 OOS에서 그대로 또는 그 이상 재현됐다는 뜻입니다. 다만 이 지표 하나로 robustness를 단정하기보다 보조 근거로 봅니다."
    else:
        tail = f"IS 성과의 약 {best * 100:.0f}%가 OOS에서 재현된다는 뜻으로, 보조 검증 근거로 해석합니다."

    return f"{head} {tail}"


def _describe_profit_concentration(mode: Mapping[str, object]) -> str:
    """Profit Concentration 최대값으로 수익 집중도를 서술한다."""
    pc = _get_number(mode, "profit_concentration_max")
    if pc is None:
        return ""

    idx = _get_number(mode, "profit_concentration_window_idx")
    where = f" (최대 기여 윈도우 {_window_label(idx)})" if idx is not None else ""

    if pc >= PC_CONCENTRATION_THRESHOLD:
        return (
            f"PC 최대 {pc:.2f}{where} — 기준 {PC_CONCENTRATION_THRESHOLD} 이상으로 수익이 특정 윈도우에 집중되어 있습니다. "
            "특정 구간 의존성이 크다는 점에서 리스크 요인으로 해석해야 합니다."
        )
    return f"PC 최대 {pc:.2f}{where} — 기준 {PC_CONCENTRATION_THRESHOLD} 미만으로 " "수익이 비교적 고르게 분산되어 있어 양호합니다."


def _render_blocks(blocks: list[str]) -> str:
    """전략별 블록을 하나의 마크다운 문자열로 합친다."""
    return "\n\n".join(blocks) if blocks else ""


def build_mode_summary_verdict(summaries_by_label: Mapping[str, Mapping[str, object]]) -> str:
    """모드별 요약 비교 섹션의 판단 문구를 생성한다.

    Args:
        summaries_by_label: 표시명 -> walkforward_summary.json 딕셔너리

    Returns:
        마크다운 문자열. 입력이 비어 있으면 빈 문자열
    """
    blocks: list[str] = []

    for label, summary in summaries_by_label.items():
        dynamic = _get_mode(summary, _KEY_DYNAMIC)
        fixed = _get_mode(summary, _KEY_FULLY_FIXED)

        dynamic_cagr = _get_number(dynamic, "stitched_cagr")
        fixed_cagr = _get_number(fixed, "stitched_cagr")

        lines: list[str] = [f"**{label}**:", ""]

        if dynamic_cagr is not None and fixed_cagr is not None:
            summary_line, detail_line = _describe_cagr_gap(dynamic_cagr, fixed_cagr)
            lines.append(f"- 한 줄 요약: {summary_line}")
            lines.append(f"- {detail_line}")
        else:
            lines.append(f"- Stitched CAGR: {_NO_DATA}")

        wfe_line = _describe_wfe(
            _get_number(dynamic, "wfe_calmar_robust"),
            _get_number(fixed, "wfe_calmar_robust"),
        )
        if wfe_line:
            lines.append(f"- {wfe_line}")

        pc_line = _describe_profit_concentration(dynamic)
        if pc_line:
            lines.append(f"- {pc_line}")

        blocks.append("\n".join(lines))

    return _render_blocks(blocks)


def build_stitched_equity_verdict(summaries_by_label: Mapping[str, Mapping[str, object]]) -> str:
    """Stitched Equity 곡선 섹션의 판단 문구를 생성한다.

    Args:
        summaries_by_label: 표시명 -> walkforward_summary.json 딕셔너리

    Returns:
        마크다운 문자열. 입력이 비어 있으면 빈 문자열
    """
    blocks: list[str] = []

    for label, summary in summaries_by_label.items():
        dynamic = _get_mode(summary, _KEY_DYNAMIC)
        fixed = _get_mode(summary, _KEY_FULLY_FIXED)

        dynamic_cagr = _get_number(dynamic, "stitched_cagr")
        fixed_cagr = _get_number(fixed, "stitched_cagr")

        lines: list[str] = [f"**{label}**:", ""]

        if dynamic_cagr is not None and fixed_cagr is not None:
            summary_line, detail_line = _describe_cagr_gap(dynamic_cagr, fixed_cagr)
            lines.append(f"- 한 줄 요약: {summary_line}")
            lines.append(f"- {detail_line}")
        else:
            lines.append(f"- Stitched CAGR: {_NO_DATA}")

        dynamic_mdd = _get_number(dynamic, "stitched_mdd")
        fixed_mdd = _get_number(fixed, "stitched_mdd")
        if dynamic_mdd is not None and fixed_mdd is not None:
            shallower = _LABEL_DYNAMIC if dynamic_mdd > fixed_mdd else _LABEL_FIXED
            lines.append(
                f"- 최대 낙폭은 {_LABEL_DYNAMIC} {dynamic_mdd:.2f}%, {_LABEL_FIXED} {fixed_mdd:.2f}%로 "
                f"{shallower} 쪽 낙폭이 더 얕습니다."
            )

        dynamic_calmar = _get_number(dynamic, "stitched_calmar")
        fixed_calmar = _get_number(fixed, "stitched_calmar")
        if dynamic_calmar is not None and fixed_calmar is not None:
            best_calmar = max(dynamic_calmar, fixed_calmar)
            verdict = (
                "위험 대비 수익이 양호한 수준입니다."
                if best_calmar >= STITCHED_CALMAR_GOOD_THRESHOLD
                else f"{STITCHED_CALMAR_GOOD_THRESHOLD}에 못 미쳐 수익 대비 낙폭 부담이 큽니다."
            )
            lines.append(
                f"- Stitched Calmar는 {_LABEL_DYNAMIC} {dynamic_calmar:.2f}, "
                f"{_LABEL_FIXED} {fixed_calmar:.2f}로 {verdict}"
            )

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
        lines: list[str] = [f"**{label}**:", ""]

        required = {"is_calmar", "oos_calmar"}
        if window_df.empty or not required.issubset(window_df.columns):
            lines.append(f"- {_NO_DATA}")
            blocks.append("\n".join(lines))
            continue

        is_calmar = pd.to_numeric(window_df["is_calmar"], errors="coerce")
        oos_calmar = pd.to_numeric(window_df["oos_calmar"], errors="coerce")
        valid = is_calmar.notna() & oos_calmar.notna()

        total = int(valid.sum())
        if total == 0:
            lines.append(f"- {_NO_DATA}")
            blocks.append("\n".join(lines))
            continue

        stronger = int((oos_calmar[valid] > is_calmar[valid]).sum())
        negative = int((oos_calmar[valid] < 0).sum())

        lines.append(f"- 전체 {total}개 윈도우 중 {stronger}개에서 OOS Calmar가 IS를 웃돌았고, " f"{negative}개 윈도우는 OOS가 음수입니다.")

        if negative == 0 and stronger * 2 >= total:
            lines.append("- IS에서만 좋고 OOS에서 무너지는 붕괴 패턴은 나타나지 않습니다.")
        elif negative * 2 >= total:
            lines.append("- 음수 윈도우가 절반 이상이므로, 특정 국면에서 전략이 버티지 못한다는 점을 감안해 보수적으로 해석해야 합니다.")
        else:
            lines.append("- 윈도우별 편차는 있으나 전 구간이 무너지는 형태는 아니므로, 과최적화 여부를 판정하는 보조 자료로 봅니다.")

        blocks.append("\n".join(lines))

    return _render_blocks(blocks)


def build_param_drift_verdict(summaries_by_label: Mapping[str, Mapping[str, object]]) -> str:
    """파라미터 추이 섹션의 판단 문구를 생성한다.

    Args:
        summaries_by_label: 표시명 -> walkforward_summary.json 딕셔너리

    Returns:
        마크다운 문자열. 입력이 비어 있으면 빈 문자열
    """
    blocks: list[str] = []

    # (표시 라벨, summary 키, 비율 여부) — 비율은 % 로 환산해 보여준다
    param_specs: list[tuple[str, str, bool]] = [
        ("MA Window", "param_ma_windows", False),
        ("Buy Buffer(%)", "param_buy_buffers", True),
        ("Sell Buffer(%)", "param_sell_buffers", True),
        ("Hold Days", "param_hold_days", False),
    ]

    for label, summary in summaries_by_label.items():
        dynamic = _get_mode(summary, _KEY_DYNAMIC)
        lines: list[str] = [f"**{label}** (Dynamic 모드):", ""]

        stable_count = 0
        described_count = 0

        for param_label, key, is_ratio in param_specs:
            values = _get_number_list(dynamic, key)
            if is_ratio:
                values = [v * 100 for v in values]
            lines.append(f"- **{param_label}:** {describe_param_series(values)}")

            if values:
                described_count += 1
                if len(set(values)) == 1:
                    stable_count += 1

        if described_count > 0:
            if stable_count == described_count:
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
    required = {"window_idx", "is_start", "is_end", "oos_start", "oos_end"}
    blocks: list[str] = []

    for label, window_df in windows_by_label.items():
        if window_df.empty or not required.issubset(window_df.columns):
            blocks.append(f"**{label}**\n\n{_NO_DATA}")
            continue

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
    try:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
    except ValueError:
        return "-"

    days = (end_ts - start_ts).days
    if days < 0:
        return "-"

    years = days / 365.25
    if years < 1:
        return f"약 {round(years * 12)}개월"
    return f"약 {round(years)}년"


def describe_param_series(values: Sequence[float | int]) -> str:
    """윈도우별 파라미터 값 리스트를 사람이 읽을 서술로 변환한다.

    전 윈도우가 같은 값이면 고정으로, 값이 바뀌면 전환 지점을 짚어 서술한다.

    Args:
        values: 윈도우 순서대로 선택된 파라미터 값

    Returns:
        서술 문자열. 빈 리스트면 "데이터 없음"
    """
    if not values:
        return _NO_DATA

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
