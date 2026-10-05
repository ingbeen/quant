"""조합 실험 — Q-2-2XS + HAA + 로테이션 16칸 · 세 판 · 같은 합계의 셋 대비 판정

설계서(`docs/research/Q2_2XS_보완_전략_설계.md`) D55 – D57 · D63 – D69 의 실험을 담는다.
「Q-2-2XS (100 − h − r)% + HAA h% + 로테이션 r%」(h · r = 5 – 20%)를 대체 판 · 이어 붙인 판 · 완전 실물판으로
돌려, 칸마다 같은 판 · 같은 합계의 기준선 · HAA 단독 · 로테이션 단독 셋과 Calmar 를 견준다.

구성 만들기는 `supplement_experiment` 가 한다(단독과 같은 매매법 정의). 여기는 실행 목록 · 워커 · 우위 ·
4방향 덩어리 판정 · 대체 판 확인을 하고, 러너(`scripts/backtest/run_combo_grid.py`)는 병렬 실행 · 반올림 ·
저장만 한다. 판정 입력은 모두 반올림 전 값이다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

import pandas as pd

from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.backtest.portfolio_validation import validate_portfolio_result
from qbt.backtest.supplement_experiment import (
    ADVANTAGE_BOUNDARY,
    CANDIDATE_BASELINE,
    CANDIDATE_HAA,
    CANDIDATE_Q2_2XS,
    CANDIDATE_ROTATION,
    COMBO_PCTS,
    MAIN_START_DATE,
    VARIANT_ALT,
    VARIANT_REAL,
    VARIANT_SPLICED,
    W_PCTS,
    RunSummary,
    build_combo_config,
    build_experiment_config,
    decision_agreement,
    extract_decision_targets,
    run_with_start_check,
    summarize_run,
)

# ============================================================================
# 칸 · 비교 상대 · 판정 기준
# ============================================================================

type Cell = tuple[int, int]  # (HAA %, 로테이션 %)

CANDIDATE_COMBO: Final = "combo"
COMBO_CELLS: Final[tuple[Cell, ...]] = tuple((h, r) for h in COMBO_PCTS for r in COMBO_PCTS)
# 같은 합계의 비교 상대 — 조합은 셋 모두보다 높아야 한다 (D56 ②)
COMPARATORS: Final[tuple[str, ...]] = (CANDIDATE_BASELINE, CANDIDATE_HAA, CANDIDATE_ROTATION)
MIN_COMBO_CLUSTER_CELLS: Final = 3  # 고원 = 상하좌우로 이어진 「높음」 칸 3칸 이상 (D56 ② · D65)

GROUP_ALT: Final = "alt"  # 대체 판
GROUP_SPLICED: Final = "spliced"  # 이어 붙인 판
GROUP_REAL: Final = "real"  # 완전 실물판 (원자재는 DBC → PDBC, D64)
GROUP_ALT_OVERLAP: Final = "alt_overlap"  # 대체 판을 이어 붙인 판 시작일부터 — 확인용 (D66)

# 묶음 시작일 — 묶음 안 모든 구성이 시작할 수 있는 가장 늦은 날 (엔진 compute_portfolio_effective_start_date 로 잰 값.
# 데이터가 바뀌어 어긋나면 워커가 실제 시작일 대조에서 멈춘다)
ALT_START_DATE: Final = date(2001, 8, 31)  # 금 선물 시작(2000-08-30) + HAA 12개월 점수
REAL_START_DATE: Final = date(2012, 1, 30)  # 실물 VXUS 상장(2011-01) + HAA 12개월 점수

_GROUP_SPECS: Final[tuple[tuple[str, str, date], ...]] = (
    (GROUP_ALT, VARIANT_ALT, ALT_START_DATE),
    (GROUP_SPLICED, VARIANT_SPLICED, MAIN_START_DATE),
    (GROUP_REAL, VARIANT_REAL, REAL_START_DATE),
    (GROUP_ALT_OVERLAP, VARIANT_ALT, MAIN_START_DATE),
)

BASIS_ALT: Final = "alt"
BASIS_SPLICED: Final = "spliced"
BASIS_REAL: Final = "real"
BASIS_JUDGMENT: Final = "spliced_and_real"
# 판정 기준 → 그 기준이 「높음」을 요구하는 묶음. 판정은 이어 붙인 판 · 완전 실물판 둘 다이고(D63),
# 판 하나씩의 지도는 보고용이다
BASIS_GROUPS: Final[dict[str, tuple[str, ...]]] = {
    BASIS_ALT: (GROUP_ALT,),
    BASIS_SPLICED: (GROUP_SPLICED,),
    BASIS_REAL: (GROUP_REAL,),
    BASIS_JUDGMENT: (GROUP_SPLICED, GROUP_REAL),
}

# 판단 비중표를 뽑는 배분 규칙 매매법 — 조합은 HAA · 로테이션 둘
_ALLOCATOR_METHODS: Final[dict[str, tuple[str, ...]]] = {
    CANDIDATE_COMBO: (CANDIDATE_HAA, CANDIDATE_ROTATION),
    CANDIDATE_HAA: (CANDIDATE_HAA,),
    CANDIDATE_ROTATION: (CANDIDATE_ROTATION,),
}

# ============================================================================
# 실행 목록 · 워커
# ============================================================================


@dataclass(frozen=True)
class ComboCase:
    """조합 그리드 실행 하나.

    w_pct 는 합계 비중이다 — 조합은 h + r, 단독 · 기준선은 그 비중, Q-2-2XS 단독은 0. cell 은 조합만 (HAA %, 로테이션 %).
    """

    group: str
    candidate: str
    w_pct: int
    variant: str
    start_date: date
    cell: Cell | None = None


def build_combo_cases() -> list[ComboCase]:
    """실행 목록 — 묶음 넷 × (조합 16 + 기준선 · HAA 단독 · 로테이션 단독 각 7 + Q-2-2XS 단독 1) = 152."""
    cases: list[ComboCase] = []
    for group, variant, start in _GROUP_SPECS:
        cases += [ComboCase(group, CANDIDATE_COMBO, h + r, variant, start, (h, r)) for h, r in COMBO_CELLS]
        for candidate in COMPARATORS:
            cases += [ComboCase(group, candidate, w, variant, start) for w in W_PCTS]
        cases.append(ComboCase(group, CANDIDATE_Q2_2XS, 0, variant, start))
    return cases


def _cell(case: ComboCase) -> Cell:
    if case.cell is None:
        raise ValueError(f"조합 실행에는 칸(cell)이 있어야 합니다: {case}")
    return case.cell


def build_case_config(q2_2xs_slots: tuple[AssetSlotConfig, ...], case: ComboCase) -> PortfolioConfig:
    """실행 하나의 설정 — 조합은 build_combo_config, 단독 · 기준선 · Q-2-2XS 단독은 build_experiment_config."""
    if case.candidate == CANDIDATE_COMBO:
        h, r = _cell(case)
        return build_combo_config(q2_2xs_slots, h, r, case.variant, case.start_date)
    return build_experiment_config(q2_2xs_slots, case.candidate, case.w_pct, case.variant, case.start_date)


@dataclass(frozen=True, eq=False)
class ComboCaseResult:
    """실행 하나의 결과. 결과 전체 대신 요약 · 위반 · 판단 비중표(배분 규칙 매매법 id → 표)만 넘긴다."""

    case: ComboCase
    summary: RunSummary
    violations: list[str]
    decision_targets: Mapping[str, pd.DataFrame]


def run_combo_case(case: ComboCase, q2_2xs_slots: tuple[AssetSlotConfig, ...]) -> ComboCaseResult:
    """실행 → 시작일 확인 → 정합성 검사 → 요약 (병렬 워커, 모듈 최상위라 pickle 가능).

    Raises:
        ValueError: 실제 시작일이 묶음 시작일과 다를 때 (run_with_start_check)
    """
    result = run_with_start_check(build_case_config(q2_2xs_slots, case), case.start_date)
    targets = {m: extract_decision_targets(result.state_log_df, m) for m in _ALLOCATOR_METHODS.get(case.candidate, ())}
    return ComboCaseResult(case, summarize_run(result), validate_portfolio_result(result), targets)


# ============================================================================
# 같은 합계의 셋 대비 우위 (D56 ② · D69 ⑥)
# ============================================================================


@dataclass(frozen=True)
class CellAdvantage:
    """조합 칸 하나의 비교. advantages = 비교 상대(COMPARATORS) → 조합 Calmar − 그 상대 Calmar (반올림 전)."""

    combo_calmar: float
    advantages: Mapping[str, float]

    @property
    def above(self) -> bool:
        """셋 모두보다 높은가 — 엄격한 `>` (같으면 높지 않다, D47)."""
        return all(value > 0 for value in self.advantages.values())

    @property
    def boundary(self) -> bool:
        """우위 중 하나라도 저장 자릿수(4)로 0 이 되는가 (D48 ⑥)."""
        return any(abs(value) < ADVANTAGE_BOUNDARY for value in self.advantages.values())


def _period(summary: RunSummary) -> tuple[date, date, int]:
    return (summary.start_date, summary.end_date, summary.trading_days)


def compute_combo_advantages(results: Sequence[ComboCaseResult]) -> dict[tuple[str, Cell], CellAdvantage]:
    """(묶음, 칸) → 같은 묶음 · 같은 합계의 기준선 · HAA 단독 · 로테이션 단독 대비 우위.

    조합과 비교 상대의 실제 기간(시작 · 끝 · 거래일 수)이 같아야 한다 — 엔진은 실험마다 시세의 공통 거래일만 쓴다.

    Raises:
        ValueError: 비교 상대가 없거나 둘 이상일 때, 같은 (묶음, 칸) 조합이 둘 이상일 때, 실제 기간이 다를 때
    """
    comparators: dict[tuple[str, str, int], RunSummary] = {}
    for r in results:
        if r.case.candidate not in COMPARATORS:
            continue
        key = (r.case.group, r.case.candidate, r.case.w_pct)
        if key in comparators:
            raise ValueError(f"같은 묶음 · 구성 · 합계의 실행이 둘 이상입니다: {key}")
        comparators[key] = r.summary

    out: dict[tuple[str, Cell], CellAdvantage] = {}
    for r in results:
        if r.case.candidate != CANDIDATE_COMBO:
            continue
        cell_key = (r.case.group, _cell(r.case))
        if cell_key in out:
            raise ValueError(f"같은 묶음 · 칸의 조합 실행이 둘 이상입니다: {cell_key}")
        advantages: dict[str, float] = {}
        for comparator in COMPARATORS:
            key = (r.case.group, comparator, r.case.w_pct)
            if key not in comparators:
                raise ValueError(
                    f"비교 상대가 없는 조합 실행입니다: {r.case} — 같은 묶음 · 합계 {r.case.w_pct}% 의 " f"{comparator} 실행을 함께 돌리세요"
                )
            other = comparators[key]
            if _period(r.summary) != _period(other):
                raise ValueError(
                    f"조합과 비교 상대의 실제 기간이 다릅니다: {r.case} 의 (시작, 끝, 거래일 수) {_period(r.summary)} vs "
                    f"{comparator} {_period(other)} — 시세 중 일찍 끝나거나 날짜가 빠진 파일이 있는지 확인하세요"
                )
            advantages[comparator] = r.summary.calmar - other.calmar
        out[cell_key] = CellAdvantage(r.summary.calmar, advantages)
    return out


def _group_cells(advantages: Mapping[tuple[str, Cell], CellAdvantage], group: str) -> dict[Cell, CellAdvantage]:
    missing = [cell for cell in COMBO_CELLS if (group, cell) not in advantages]
    if missing:
        raise ValueError(f"묶음 {group!r} 의 조합 실행 결과가 없는 칸이 있습니다: {missing}")
    return {cell: advantages[(group, cell)] for cell in COMBO_CELLS}


# ============================================================================
# 덩어리 · 판정 (D63 · D65)
# ============================================================================


def find_clusters(above: Mapping[Cell, bool]) -> tuple[tuple[Cell, ...], ...]:
    """「높음」 칸이 상하좌우로 이어진 덩어리 가운데 MIN_COMBO_CLUSTER_CELLS 칸 이상인 것들.

    이웃은 HAA 비중만 또는 로테이션 비중만 한 단계 다른 칸이다 — 대각선은 이웃이 아니다 (D65).
    덩어리 안의 칸은 오름차순, 덩어리는 첫 칸 순서다.

    Raises:
        ValueError: 16칸이 다 있지 않을 때 — 빠진 칸을 「낮음」으로 읽으면 덩어리가 조용히 끊긴다
    """
    if set(above) != set(COMBO_CELLS):
        raise ValueError(f"{len(COMBO_CELLS)}칸이 모두 있어야 합니다: {sorted(above)} (필요: {list(COMBO_CELLS)})")
    index = {pct: i for i, pct in enumerate(COMBO_PCTS)}
    seen: set[Cell] = set()
    clusters: list[tuple[Cell, ...]] = []
    for start in COMBO_CELLS:
        if not above[start] or start in seen:
            continue
        seen.add(start)
        stack = [start]
        members: list[Cell] = []
        while stack:
            h, r = stack.pop()
            members.append((h, r))
            for dh, dr in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                hi, ri = index[h] + dh, index[r] + dr
                if not (0 <= hi < len(COMBO_PCTS) and 0 <= ri < len(COMBO_PCTS)):
                    continue
                neighbor = (COMBO_PCTS[hi], COMBO_PCTS[ri])
                if above[neighbor] and neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        if len(members) >= MIN_COMBO_CLUSTER_CELLS:
            clusters.append(tuple(sorted(members)))
    return tuple(sorted(clusters))


@dataclass(frozen=True)
class ComboJudgment:
    """판정 기준 하나의 결과. counted_above[칸] = 그 기준의 묶음 모두에서 「셋보다 높음」."""

    counted_above: Mapping[Cell, bool]
    clusters: tuple[tuple[Cell, ...], ...]
    passed: bool


def judge_combo(above_maps: Sequence[Mapping[Cell, bool]]) -> ComboJudgment:
    """묶음 모두에서 높은 칸으로 덩어리를 찾는다 — 3칸 이상 덩어리가 하나라도 있으면 통과 (D56 ② · D63 · D65).

    Raises:
        ValueError: 지도가 없을 때
    """
    if not above_maps:
        raise ValueError("판정할 「높음」 지도가 없습니다")
    counted = {cell: all(m[cell] for m in above_maps) for cell in COMBO_CELLS}
    clusters = find_clusters(counted)
    return ComboJudgment(counted_above=counted, clusters=clusters, passed=bool(clusters))


@dataclass(frozen=True)
class ComboJudgmentRow:
    """판정 표 한 행 (판정 기준 × 칸).

    per_group 은 그 기준이 쓰는 묶음 → 이 칸의 비교 값. 통과 · 덩어리 목록은 기준 단위 값을 행마다 싣고,
    cluster 는 이 칸이 속한 3칸 이상 덩어리다(없으면 빈 튜플). boundary 는 쓴 우위 중 하나라도 0 근처인가.
    """

    basis: str
    cell: Cell
    per_group: Mapping[str, CellAdvantage]
    counted_above: bool
    boundary: bool
    cluster: tuple[Cell, ...]
    passed: bool
    clusters: tuple[tuple[Cell, ...], ...]


def collect_combo_judgments(results: Sequence[ComboCaseResult]) -> list[ComboJudgmentRow]:
    """판정 기준 넷(판 하나씩의 지도 셋 + 판정) × 16칸 행."""
    advantages = compute_combo_advantages(results)
    rows: list[ComboJudgmentRow] = []
    for basis, groups in BASIS_GROUPS.items():
        per_group = {group: _group_cells(advantages, group) for group in groups}
        judgment = judge_combo([{cell: v.above for cell, v in cells.items()} for cells in per_group.values()])
        cluster_of = {cell: cluster for cluster in judgment.clusters for cell in cluster}
        for cell in COMBO_CELLS:
            used = {group: per_group[group][cell] for group in groups}
            rows.append(
                ComboJudgmentRow(
                    basis=basis,
                    cell=cell,
                    per_group=used,
                    counted_above=judgment.counted_above[cell],
                    boundary=any(v.boundary for v in used.values()),
                    cluster=cluster_of.get(cell, ()),
                    passed=judgment.passed,
                    clusters=judgment.clusters,
                )
            )
    return rows


# ============================================================================
# 대체 판 확인 (D66 · D69 ⑧) — 보고용, 관문이 아니다
# ============================================================================


@dataclass(frozen=True)
class AltCheckRow:
    """대체 판 확인 한 행 (칸). 일치 수 · 덩어리 · 덩어리 유무 일치는 16칸 단위 값을 행마다 싣는다."""

    cell: Cell
    alt: CellAdvantage
    spliced: CellAdvantage
    sign_match: bool
    boundary: bool
    haa_agreement: float
    rotation_agreement: float
    signal_months: int
    match_count: int
    alt_clusters: tuple[tuple[Cell, ...], ...]
    spliced_clusters: tuple[tuple[Cell, ...], ...]
    cluster_verdict_match: bool


def _decision_targets(result: ComboCaseResult, method_id: str) -> pd.DataFrame:
    if method_id not in result.decision_targets:
        raise RuntimeError(f"내부 불변조건 위반: 조합 실행에 {method_id} 판단 비중표가 없다 ({result.case})")
    return result.decision_targets[method_id]


def collect_alt_check(results: Sequence[ComboCaseResult]) -> list[AltCheckRow]:
    """대체 판 겹침 묶음(이어 붙인 판 시작일부터)과 이어 붙인 판을 칸마다 견준다.

    「셋보다 높음」 일치와 조합 실행의 HAA · 로테이션 월말 판단 일치율(D48 ①)을 낸다. 판단은 시세만 보므로
    일치율은 칸마다 같아야 한다.
    """
    advantages = compute_combo_advantages(results)
    alt = _group_cells(advantages, GROUP_ALT_OVERLAP)
    spliced = _group_cells(advantages, GROUP_SPLICED)
    alt_judgment = judge_combo([{cell: v.above for cell, v in alt.items()}])
    spliced_judgment = judge_combo([{cell: v.above for cell, v in spliced.items()}])
    sign_match = {cell: alt[cell].above == spliced[cell].above for cell in COMBO_CELLS}
    combos = {
        (r.case.group, _cell(r.case)): r
        for r in results
        if r.case.candidate == CANDIDATE_COMBO and r.case.group in (GROUP_ALT_OVERLAP, GROUP_SPLICED)
    }

    rows: list[AltCheckRow] = []
    for cell in COMBO_CELLS:
        alt_run, spliced_run = combos[(GROUP_ALT_OVERLAP, cell)], combos[(GROUP_SPLICED, cell)]
        if alt_run.case.start_date != spliced_run.case.start_date:
            raise RuntimeError(f"내부 불변조건 위반: 대체 판 확인의 두 실행 시작일이 다르다 ({alt_run.case} vs {spliced_run.case})")
        # 거래일 수는 대조하지 않는다 — 대체 판은 금 선물에 없는 미국 거래일이 빠져 원래 다르다
        alt_span = (alt_run.summary.start_date, alt_run.summary.end_date)
        spliced_span = (spliced_run.summary.start_date, spliced_run.summary.end_date)
        if alt_span != spliced_span:
            raise ValueError(
                f"대체 판 확인의 두 실행 기간이 다릅니다: 칸 {cell} 대체 판 {alt_span} vs 이어 붙인 판 {spliced_span} — "
                f"한쪽 시세만 다시 받았거나 대체 시세를 다시 만들지 않았는지 확인하세요"
            )
        haa_rate, months = decision_agreement(
            _decision_targets(alt_run, CANDIDATE_HAA), _decision_targets(spliced_run, CANDIDATE_HAA)
        )
        rotation_rate, rotation_months = decision_agreement(
            _decision_targets(alt_run, CANDIDATE_ROTATION), _decision_targets(spliced_run, CANDIDATE_ROTATION)
        )
        if rotation_months != months:
            raise RuntimeError(f"내부 불변조건 위반: 같은 실행의 HAA · 로테이션 판단 달 수가 다르다 ({months} vs {rotation_months}, {cell})")
        rows.append(
            AltCheckRow(
                cell=cell,
                alt=alt[cell],
                spliced=spliced[cell],
                sign_match=sign_match[cell],
                boundary=alt[cell].boundary or spliced[cell].boundary,
                haa_agreement=haa_rate,
                rotation_agreement=rotation_rate,
                signal_months=months,
                match_count=sum(sign_match.values()),
                alt_clusters=alt_judgment.clusters,
                spliced_clusters=spliced_judgment.clusters,
                cluster_verdict_match=alt_judgment.passed == spliced_judgment.passed,
            )
        )
    return rows
