"""조합 실험 모듈 테스트

「Q-2-2XS (100 − h − r)% + HAA h% + 로테이션 r%」 16칸을 세 판으로 돌리는 실험의
실행 목록 · 같은 합계의 셋(기준선 · HAA 단독 · 로테이션 단독) 대비 우위 · 4방향 덩어리 판정 ·
대체 판 확인의 계약을 검증한다 (설계서 D55 – D57 · D63 – D66 · D69).

왜 중요한가요?
조합을 쓸 이유는 「단독보다 낫다」이고(D56 ②), 그 기준은 결과를 보기 전에 정했다.
비교 상대(같은 묶음 · 같은 합계), 「셋 모두보다 높다」, 판정에 쓰는 두 판, 상하좌우 이웃이
한 군데만 어긋나도 판정이 에러 없이 바뀐다.
"""

import dataclasses
from collections.abc import Callable
from datetime import date

import pandas as pd
import pytest

from qbt.backtest import combo_experiment as cx
from qbt.backtest import supplement_experiment as se
from qbt.backtest.engines.portfolio_data import validate_portfolio_config
from qbt.backtest.portfolio_configs import get_portfolio_config
from qbt.backtest.portfolio_types import PortfolioConfig, PortfolioResult
from qbt.common_constants import COL_DATE

_Q2_SLOTS = get_portfolio_config("portfolio_q2_2xs").asset_slots
_MONTHS = [date(2016, m, 1) for m in range(1, 5)]

# ============================================================================
# 공통 헬퍼
# ============================================================================


def _summary(calmar: float, start: date, trading_days: int = 4800) -> se.RunSummary:
    return se.RunSummary(
        start_date=start,
        end_date=date(2026, 9, 24),
        trading_days=trading_days,
        cagr=10.0,
        mdd=-20.0,
        calmar=calmar,
        sell_trades=0,
        annual_turnover=0.0,
        phase_returns={},
        phase_mdds={},
    )


def _targets(rows: list[dict[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=pd.Index(_MONTHS, name=COL_DATE))


_HAA_TARGETS = _targets([{"spy": 0.25, "bil": 0.75}] * 4)
_ROTATION_TARGETS = _targets([{"vxus": 1.0, "shy": 0.0}] * 4)


def _default_targets(case: cx.ComboCase) -> dict[str, pd.DataFrame]:
    if case.candidate == cx.CANDIDATE_COMBO:
        return {se.CANDIDATE_HAA: _HAA_TARGETS, se.CANDIDATE_ROTATION: _ROTATION_TARGETS}
    if case.candidate == se.CANDIDATE_HAA:
        return {se.CANDIDATE_HAA: _HAA_TARGETS}
    if case.candidate == se.CANDIDATE_ROTATION:
        return {se.CANDIDATE_ROTATION: _ROTATION_TARGETS}
    return {}


def _fake_results(
    calmar_of: Callable[[cx.ComboCase], float],
    targets_of: Callable[[cx.ComboCase], dict[str, pd.DataFrame]] = _default_targets,
) -> list[cx.ComboCaseResult]:
    """152개 실행 전부에 가짜 요약을 붙인다."""
    return [
        cx.ComboCaseResult(case, _summary(calmar_of(case), case.start_date), [], targets_of(case))
        for case in cx.build_combo_cases()
    ]


def _all_cells(value: bool) -> dict[cx.Cell, bool]:
    return {cell: value for cell in cx.COMBO_CELLS}


def _cells_on(*cells: cx.Cell) -> dict[cx.Cell, bool]:
    above = _all_cells(False)
    for cell in cells:
        above[cell] = True
    return above


def _combo_wins_in(groups: set[str], cells: set[cx.Cell]) -> Callable[[cx.ComboCase], float]:
    """groups 의 cells 조합만 0.7, 나머지 조합은 0.4, 단독 · 기준선은 0.5 — 그 칸들만 「셋보다 높음」."""

    def calmar(case: cx.ComboCase) -> float:
        if case.candidate != cx.CANDIDATE_COMBO:
            return 0.5
        return 0.7 if case.group in groups and case.cell in cells else 0.4

    return calmar


# ============================================================================
# 실행 목록
# ============================================================================


class TestComboCases:
    """build_combo_cases 의 실행 수 · 묶음 · 비교 상대 계약 (D69 ⑤)."""

    def test_case_counts(self) -> None:
        """
        목적: 묶음 넷 × 38 = 152회 — 조합 16, 기준선 · HAA 단독 · 로테이션 단독 각 7, Q-2-2XS 단독 1.

        Given: 실행 목록
        When:  묶음 · 구성별로 센다
        Then:  계획한 수
        """
        # When
        cases = cx.build_combo_cases()
        counts: dict[tuple[str, str], int] = {}
        for case in cases:
            counts[(case.group, case.candidate)] = counts.get((case.group, case.candidate), 0) + 1

        # Then
        assert len(cases) == 152
        for group in (cx.GROUP_ALT, cx.GROUP_SPLICED, cx.GROUP_REAL, cx.GROUP_ALT_OVERLAP):
            assert counts[(group, cx.CANDIDATE_COMBO)] == 16
            assert counts[(group, se.CANDIDATE_BASELINE)] == 7
            assert counts[(group, se.CANDIDATE_HAA)] == 7
            assert counts[(group, se.CANDIDATE_ROTATION)] == 7
            assert counts[(group, se.CANDIDATE_Q2_2XS)] == 1

    def test_cases_are_unique(self) -> None:
        """
        목적: 결과를 찾는 키(묶음 · 구성 · 합계 · 칸)가 겹치지 않는다 — 겹치면 판정이 다른 실행을 읽는다.

        Given: 실행 목록
        When:  키를 센다
        Then:  중복 없음
        """
        # When
        keys = [(c.group, c.candidate, c.w_pct, c.cell) for c in cx.build_combo_cases()]

        # Then
        assert len(keys) == len(set(keys))

    def test_group_variant_and_start(self) -> None:
        """
        목적: 묶음마다 판과 시작일이 하나다 — 대체 판 2001-08-31 · 이어 붙인 판 2007-06-22 · 완전 실물판 2012-01-30 ·
        대체 판 겹침 2007-06-22 (D66 · D69 ⑤).

        Given: 실행 목록
        When:  묶음별 (판, 시작일) 집합을 모은다
        Then:  묶음마다 하나이고 정한 값이다
        """
        # When
        specs: dict[str, set[tuple[str, date]]] = {}
        for case in cx.build_combo_cases():
            specs.setdefault(case.group, set()).add((case.variant, case.start_date))

        # Then
        assert specs == {
            cx.GROUP_ALT: {(se.VARIANT_ALT, date(2001, 8, 31))},
            cx.GROUP_SPLICED: {(se.VARIANT_SPLICED, date(2007, 6, 22))},
            cx.GROUP_REAL: {(se.VARIANT_REAL, date(2012, 1, 30))},
            cx.GROUP_ALT_OVERLAP: {(se.VARIANT_ALT, date(2007, 6, 22))},
        }

    def test_combo_cells_and_sum(self) -> None:
        """
        목적: 조합 칸은 HAA 5 – 20% × 로테이션 5 – 20% 의 16칸이고 합계 = h + r 이다. 단독에는 칸이 없다.

        Given: 실행 목록
        When:  조합 실행의 칸을 모은다
        Then:  묶음마다 16칸 전부, 합계가 h + r
        """
        for group in (cx.GROUP_ALT, cx.GROUP_SPLICED, cx.GROUP_REAL, cx.GROUP_ALT_OVERLAP):
            # When
            combos = [c for c in cx.build_combo_cases() if c.group == group and c.candidate == cx.CANDIDATE_COMBO]

            # Then
            assert {c.cell for c in combos} == set(cx.COMBO_CELLS)
            for c in combos:
                assert c.cell is not None
                assert c.w_pct == c.cell[0] + c.cell[1]
        assert all(c.cell is None for c in cx.build_combo_cases() if c.candidate != cx.CANDIDATE_COMBO)
        assert len(cx.COMBO_CELLS) == 16

    def test_every_combo_has_same_sum_comparators(self) -> None:
        """
        목적: 조합 칸마다 같은 묶음에 합계가 같은 기준선 · HAA 단독 · 로테이션 단독이 있다 (D56 ②).

        Given: 실행 목록
        When:  비교 상대 (묶음, 구성, 합계) 집합을 만든다
        Then:  모든 조합의 비교 상대 셋이 그 안에 있다
        """
        # Given
        cases = cx.build_combo_cases()
        present = {(c.group, c.candidate, c.w_pct) for c in cases}

        # When / Then
        for case in cases:
            if case.candidate == cx.CANDIDATE_COMBO:
                for comparator in cx.COMPARATORS:
                    assert (case.group, comparator, case.w_pct) in present, (case, comparator)

    def test_every_case_config_passes_validation(self) -> None:
        """
        목적: 152개 실행의 설정이 모두 엔진의 설정 검증을 통과한다.

        Given: 실행 목록
        When:  build_case_config → validate_portfolio_config
        Then:  예외 없음 (파일은 읽지 않는다)
        """
        for case in cx.build_combo_cases():
            # When / Then
            validate_portfolio_config(cx.build_case_config(_Q2_SLOTS, case))


# ============================================================================
# 우위 · 「셋보다 높음」
# ============================================================================


class TestComboAdvantages:
    """compute_combo_advantages — 같은 묶음 · 같은 합계의 셋과 비교한다 (D56 ② · D69 ⑥)."""

    def test_advantage_against_each_same_sum_comparator(self) -> None:
        """
        목적: 우위 = 조합 Calmar − 같은 묶음 · 합계 h + r 의 기준선 · HAA 단독 · 로테이션 단독 Calmar.

        Given: 이어 붙인 판 조합 (10, 15) 0.7, 같은 묶음 합계 25 의 기준선 0.5 · HAA 0.6 · 로테이션 0.65,
               다른 묶음(대체 판)의 합계 25 기준선 0.9
        When:  우위를 계산한다
        Then:  {기준선 0.2, HAA 0.1, 로테이션 0.05} — 다른 묶음의 값은 쓰지 않는다
        """

        # Given
        def calmar(case: cx.ComboCase) -> float:
            if case.group == cx.GROUP_SPLICED and case.cell == (10, 15):
                return 0.7
            if case.group == cx.GROUP_SPLICED and case.w_pct == 25 and case.cell is None:
                return {se.CANDIDATE_BASELINE: 0.5, se.CANDIDATE_HAA: 0.6, se.CANDIDATE_ROTATION: 0.65}.get(
                    case.candidate, 0.5
                )
            if case.group == cx.GROUP_ALT and case.w_pct == 25 and case.candidate == se.CANDIDATE_BASELINE:
                return 0.9
            return 0.5

        # When
        advantages = cx.compute_combo_advantages(_fake_results(calmar))

        # Then
        cell = advantages[(cx.GROUP_SPLICED, (10, 15))]
        assert cell.combo_calmar == pytest.approx(0.7, abs=1e-12)
        assert dict(cell.advantages) == pytest.approx(
            {se.CANDIDATE_BASELINE: 0.2, se.CANDIDATE_HAA: 0.1, se.CANDIDATE_ROTATION: 0.05}, abs=1e-12
        )
        assert cell.above

    @pytest.mark.parametrize(
        ("haa_calmar", "expected_above"),
        [
            (0.69, True),  # 셋 모두보다 높다
            (0.7, False),  # HAA 단독과 같다 — 높지 않다
            (0.71, False),  # HAA 단독보다 낮다 — 둘보다만 높아도 아니다
        ],
    )
    def test_above_needs_strictly_higher_than_all_three(self, haa_calmar: float, expected_above: bool) -> None:
        """
        목적: 「셋보다 높음」은 셋 모두에 대해 엄격한 `>` 다 (D47 · D56 ②).

        Given: 조합 0.7, 기준선 0.5 · 로테이션 0.6, HAA 단독이 0.69 / 0.7 / 0.71
        When:  우위를 계산한다
        Then:  0.69 일 때만 높음
        """

        # Given
        def calmar(case: cx.ComboCase) -> float:
            if case.candidate == cx.CANDIDATE_COMBO:
                return 0.7
            return {se.CANDIDATE_HAA: haa_calmar, se.CANDIDATE_ROTATION: 0.6}.get(case.candidate, 0.5)

        # When
        advantages = cx.compute_combo_advantages(_fake_results(calmar))

        # Then
        assert advantages[(cx.GROUP_REAL, (5, 5))].above is expected_above

    def test_missing_comparator_raises(self) -> None:
        """
        목적: 비교 상대가 없으면 ValueError — 빠진 채 판정하면 그 칸이 조용히 유리해진다.

        Given: 이어 붙인 판 합계 20 의 로테이션 단독 실행이 빠진 결과
        When:  우위를 계산한다
        Then:  ValueError
        """
        # Given
        results = [
            r
            for r in _fake_results(lambda case: 0.5)
            if not (
                r.case.group == cx.GROUP_SPLICED and r.case.candidate == se.CANDIDATE_ROTATION and r.case.w_pct == 20
            )
        ]

        # When / Then
        with pytest.raises(ValueError, match="비교 상대"):
            cx.compute_combo_advantages(results)

    def test_different_actual_period_raises(self) -> None:
        """
        목적: 조합과 비교 상대의 실제 기간(시작 · 끝 · 거래일 수)이 다르면 ValueError — 다른 기간의 Calmar 를 빼게 된다.

        Given: 완전 실물판 합계 30 기준선의 거래일 수만 다른 결과
        When:  우위를 계산한다
        Then:  ValueError
        """

        # Given
        def shifted(r: cx.ComboCaseResult) -> cx.ComboCaseResult:
            if r.case.group == cx.GROUP_REAL and r.case.candidate == se.CANDIDATE_BASELINE and r.case.w_pct == 30:
                return cx.ComboCaseResult(r.case, _summary(0.5, r.case.start_date, trading_days=4799), [], {})
            return r

        results = [shifted(r) for r in _fake_results(lambda case: 0.5)]

        # When / Then
        with pytest.raises(ValueError, match="기간"):
            cx.compute_combo_advantages(results)


# ============================================================================
# 덩어리 · 판정
# ============================================================================


class TestFindClusters:
    """find_clusters — 상하좌우로 이어진 「높음」 칸 덩어리 중 3칸 이상 (D65)."""

    def test_l_shape_of_three_is_a_cluster(self) -> None:
        """
        목적: 상하좌우로 이어진 3칸은 ㄱ자여도 한 덩어리다.

        Given: (10, 10) · (10, 15) · (15, 15)
        When:  덩어리를 찾는다
        Then:  그 셋이 한 덩어리
        """
        # When
        clusters = cx.find_clusters(_cells_on((10, 10), (10, 15), (15, 15)))

        # Then
        assert clusters == (((10, 10), (10, 15), (15, 15)),)

    def test_two_cells_are_not_enough(self) -> None:
        """
        목적: 2칸 덩어리는 고원이 아니다 (D56 ② 「3칸 이상」).

        Given: (5, 5) · (5, 10)
        When:  덩어리를 찾는다
        Then:  없음
        """
        assert cx.find_clusters(_cells_on((5, 5), (5, 10))) == ()

    def test_diagonal_cells_are_not_neighbors(self) -> None:
        """
        목적: 대각선으로만 붙은 칸은 이웃이 아니다 — 4방향 (D65).

        Given: (5, 5) · (10, 10) · (15, 15) — 대각선으로만 이어진 3칸
        When:  덩어리를 찾는다
        Then:  없음
        """
        assert cx.find_clusters(_cells_on((5, 5), (10, 10), (15, 15))) == ()

    def test_multiple_clusters_are_all_reported(self) -> None:
        """
        목적: 3칸 이상 덩어리가 여럿이면 모두 보고한다 (D47 · D65).

        Given: 왼쪽 위 3칸과 오른쪽 아래 3칸, 서로 떨어져 있음
        When:  덩어리를 찾는다
        Then:  둘 다, 첫 칸 순서로
        """
        # Given
        above = _cells_on((5, 5), (5, 10), (10, 5), (20, 15), (20, 20), (15, 20))

        # When
        clusters = cx.find_clusters(above)

        # Then
        assert clusters == (((5, 5), (5, 10), (10, 5)), ((15, 20), (20, 15), (20, 20)))

    def test_all_cells_are_one_cluster(self) -> None:
        """
        목적: 16칸 전부 높으면 16칸 한 덩어리다 (경계 조건).

        Given: 모든 칸이 높음
        When:  덩어리를 찾는다
        Then:  16칸 하나
        """
        assert cx.find_clusters(_all_cells(True)) == (tuple(sorted(cx.COMBO_CELLS)),)

    def test_missing_cell_raises(self) -> None:
        """
        목적: 16칸이 다 있지 않으면 ValueError — 빠진 칸이 「낮음」으로 읽히면 덩어리가 끊긴다.

        Given: 한 칸이 빠진 표
        When:  덩어리를 찾는다
        Then:  ValueError
        """
        # Given
        above = _all_cells(True)
        del above[(10, 10)]

        # When / Then
        with pytest.raises(ValueError):
            cx.find_clusters(above)


class TestComboJudgment:
    """collect_combo_judgments — 판정 기준 넷과 「판정」은 이어 붙인 판 · 완전 실물판 둘 다 (D63 · D69 ⑦)."""

    def test_rows_cover_four_bases(self) -> None:
        """
        목적: 판정 기준 넷 × 16칸 행을 낸다.

        Given: 모든 Calmar 0.5 인 결과
        When:  판정 행을 모은다
        Then:  64행, 기준별 16칸
        """
        # When
        rows = cx.collect_combo_judgments(_fake_results(lambda case: 0.5))

        # Then
        assert len(rows) == 64
        for basis in (cx.BASIS_ALT, cx.BASIS_SPLICED, cx.BASIS_REAL, cx.BASIS_JUDGMENT):
            assert {r.cell for r in rows if r.basis == basis} == set(cx.COMBO_CELLS)

    def test_judgment_needs_both_spliced_and_real(self) -> None:
        """
        목적: 판정에 세는 칸은 이어 붙인 판 · 완전 실물판 둘 다 높은 칸이다.

        Given: 이어 붙인 판은 (5, 5) · (5, 10) · (5, 15) · (5, 20) 이 높고, 완전 실물판은 (5, 5) · (5, 10) 만 높다
        When:  판정 행을 모은다
        Then:  판정 기준은 탈락(2칸), 이어 붙인 판 지도는 통과(4칸)
        """
        # Given
        column = {(5, 5), (5, 10), (5, 15), (5, 20)}

        def calmar(case: cx.ComboCase) -> float:
            if case.candidate != cx.CANDIDATE_COMBO:
                return 0.5
            if case.group == cx.GROUP_SPLICED and case.cell in column:
                return 0.7
            if case.group == cx.GROUP_REAL and case.cell in {(5, 5), (5, 10)}:
                return 0.7
            return 0.4

        # When
        rows = cx.collect_combo_judgments(_fake_results(calmar))

        # Then
        judgment = [r for r in rows if r.basis == cx.BASIS_JUDGMENT]
        spliced = [r for r in rows if r.basis == cx.BASIS_SPLICED]
        assert {r.cell for r in judgment if r.counted_above} == {(5, 5), (5, 10)}
        assert not judgment[0].passed
        assert judgment[0].clusters == ()
        assert spliced[0].passed
        assert spliced[0].clusters == (((5, 5), (5, 10), (5, 15), (5, 20)),)

    def test_alt_is_not_used_for_judgment(self) -> None:
        """
        목적: 대체 판은 판정에 쓰지 않는다 — 대체 판만 높아도 판정은 탈락, 대체 판 지도에는 통과로 보인다 (D63).

        Given: 대체 판(2001 · 2007 묶음)만 16칸 모두 높다
        When:  판정 행을 모은다
        Then:  판정 기준 탈락, 대체 판 지도 통과
        """
        # When
        rows = cx.collect_combo_judgments(
            _fake_results(_combo_wins_in({cx.GROUP_ALT, cx.GROUP_ALT_OVERLAP}, set(cx.COMBO_CELLS)))
        )

        # Then
        assert not next(r for r in rows if r.basis == cx.BASIS_JUDGMENT).passed
        assert next(r for r in rows if r.basis == cx.BASIS_ALT).passed

    def test_cluster_of_each_cell(self) -> None:
        """
        목적: 행마다 그 칸이 속한 3칸 이상 덩어리를 싣는다 — 덩어리 밖 칸은 빈 값.

        Given: 두 판 모두 (15, 5) · (15, 10) · (20, 10) 이 높다
        When:  판정 행을 모은다
        Then:  그 셋의 행은 그 덩어리, 나머지는 빈 덩어리, 판정 통과
        """
        # Given
        cells = {(15, 5), (15, 10), (20, 10)}

        # When
        rows = cx.collect_combo_judgments(_fake_results(_combo_wins_in({cx.GROUP_SPLICED, cx.GROUP_REAL}, cells)))

        # Then
        judgment = {r.cell: r for r in rows if r.basis == cx.BASIS_JUDGMENT}
        expected = ((15, 5), (15, 10), (20, 10))
        for cell, row in judgment.items():
            assert row.cluster == (expected if cell in cells else ())
            assert row.passed

    def test_boundary_marks_near_zero_advantage(self) -> None:
        """
        목적: 판정에 쓴 우위 중 절댓값이 0.00005 미만인 것이 있으면 「경계」 (D48 ⑥).

        Given: 완전 실물판 (20, 20) 조합이 기준선보다 0.00003 만 높다
        When:  판정 행을 모은다
        Then:  완전 실물판 · 판정 기준의 그 칸만 경계, 이어 붙인 판 지도의 그 칸은 경계 아님
        """

        # Given
        def calmar(case: cx.ComboCase) -> float:
            if case.group == cx.GROUP_REAL and case.cell == (20, 20):
                return 0.50003
            return 0.5 if case.candidate != cx.CANDIDATE_COMBO else 0.4

        # When
        rows = cx.collect_combo_judgments(_fake_results(calmar))

        # Then
        flagged = {(r.basis, r.cell) for r in rows if r.boundary}
        assert flagged == {(cx.BASIS_REAL, (20, 20)), (cx.BASIS_JUDGMENT, (20, 20))}


# ============================================================================
# 대체 판 확인
# ============================================================================


class TestAltCheck:
    """collect_alt_check — 대체 판 겹침(2007-06-22 부터)과 이어 붙인 판의 일치 (D66 · D69 ⑧)."""

    def test_cell_match_and_count(self) -> None:
        """
        목적: 칸마다 두 묶음의 「셋보다 높음」이 같은지와 16칸 중 일치 수, 덩어리 유무 일치를 낸다.

        Given: 이어 붙인 판은 (5, 5) · (5, 10) · (5, 15) 가 높고, 대체 판 겹침은 (5, 5) · (5, 10) 만 높다
        When:  확인 행을 모은다
        Then:  (5, 15) 만 불일치, 일치 15, 덩어리 유무 불일치(이어 붙인 판만 있음)
        """

        # Given
        def calmar(case: cx.ComboCase) -> float:
            if case.candidate != cx.CANDIDATE_COMBO:
                return 0.5
            if case.group == cx.GROUP_SPLICED and case.cell in {(5, 5), (5, 10), (5, 15)}:
                return 0.7
            if case.group == cx.GROUP_ALT_OVERLAP and case.cell in {(5, 5), (5, 10)}:
                return 0.7
            return 0.4

        # When
        rows = cx.collect_alt_check(_fake_results(calmar))

        # Then
        assert len(rows) == 16
        assert {r.cell for r in rows if not r.sign_match} == {(5, 15)}
        assert {r.match_count for r in rows} == {15}
        assert {r.cluster_verdict_match for r in rows} == {False}

    def test_different_end_date_raises(self) -> None:
        """
        목적: 대체 판 겹침과 이어 붙인 판의 실제 끝날이 다르면 ValueError — 다른 기간의 Calmar 를 견주게 된다.

        Given: 대체 판 겹침 묶음 실행만 끝날이 하루 늦다(묶음 안의 비교 상대와는 같은 기간)
        When:  확인 행을 모은다
        Then:  ValueError
        """

        # Given
        def later(r: cx.ComboCaseResult) -> cx.ComboCaseResult:
            if r.case.group != cx.GROUP_ALT_OVERLAP:
                return r
            summary = dataclasses.replace(r.summary, end_date=date(2026, 9, 25))
            return cx.ComboCaseResult(r.case, summary, [], r.decision_targets)

        results = [later(r) for r in _fake_results(lambda case: 0.5)]

        # When / Then
        with pytest.raises(ValueError, match="기간"):
            cx.collect_alt_check(results)

    def test_decision_agreement_uses_combo_runs_of_both_groups(self) -> None:
        """
        목적: HAA · 로테이션 판단 일치율은 같은 칸의 두 묶음 조합 실행에서 잰다 (D48 ① 정의).

        Given: 대체 판 겹침 조합의 HAA 판단이 4달 중 1달 다르고 로테이션은 모두 같다
        When:  확인 행을 모은다
        Then:  HAA 0.75 · 로테이션 1.0 · 비교 달 4
        """
        # Given
        changed = _targets([{"spy": 0.25, "bil": 0.75}] * 3 + [{"spy": 0.0, "bil": 1.0}])

        def targets(case: cx.ComboCase) -> dict[str, pd.DataFrame]:
            base = _default_targets(case)
            if case.group == cx.GROUP_ALT_OVERLAP and case.candidate == cx.CANDIDATE_COMBO:
                return {**base, se.CANDIDATE_HAA: changed}
            return base

        # When
        rows = cx.collect_alt_check(_fake_results(lambda case: 0.5, targets))

        # Then
        for row in rows:
            assert row.haa_agreement == pytest.approx(0.75, abs=1e-12)
            assert row.rotation_agreement == pytest.approx(1.0, abs=1e-12)
            assert row.signal_months == 4


# ============================================================================
# 워커
# ============================================================================


class TestRunComboCase:
    """run_combo_case 의 시작일 확인과 판단 비중표."""

    def test_later_actual_start_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        목적: 결과의 첫 날짜가 묶음 시작일과 다르면 ValueError — 엔진의 start_date 는 하한이라 조용히 늦게 시작한다.

        Given: 엔진이 요청보다 늦게 시작한 결과를 돌려준다
        When:  조합 워커를 실행한다
        Then:  ValueError
        """
        # Given
        case = next(c for c in cx.build_combo_cases() if c.group == cx.GROUP_ALT and c.candidate == cx.CANDIDATE_COMBO)
        late = pd.DataFrame({COL_DATE: [date(2001, 9, 4), date(2001, 9, 5)], "equity": [1.0, 1.0]})

        def _fake_run(config: PortfolioConfig, start_date: date | None = None) -> PortfolioResult:
            return PortfolioResult("t", "t", late, pd.DataFrame(), {}, config)

        monkeypatch.setattr(se, "run_portfolio_backtest", _fake_run)

        # When / Then
        with pytest.raises(ValueError, match="시작일"):
            cx.run_combo_case(case, _Q2_SLOTS)

    def test_decision_targets_by_candidate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        목적: 워커가 돌려주는 판단 비중표 — 조합은 HAA · 로테이션 둘, 단독은 그 매매법 하나, 기준선 · Q-2-2XS 단독은 없음.
        대체 판 확인은 조합 실행의 두 표를 쓴다 — 하나가 빠지면 실행을 다 돈 뒤에야 멈추고, 표가 뒤바뀌면 일치율이
        오류 없이 틀린다. 그래서 매매법 id 와 그 표의 자산 열을 함께 본다.

        Given: 요청 시작일부터 시작하고 상태 로그에 HAA(spy) · 로테이션(vxus) 목표 비중 열이 있는 가짜 결과
        When:  이어 붙인 판 묶음의 조합 · HAA 단독 · 로테이션 단독 · 기준선 · Q-2-2XS 단독 워커를 돌린다
        Then:  구성마다 {매매법 id: 자산 열} 이 정한 것과 같다
        """

        # Given
        def _fake_run(config: PortfolioConfig, start_date: date | None = None) -> PortfolioResult:
            assert start_date is not None
            days = [
                start_date,
                date(start_date.year, start_date.month, 25),
                date(start_date.year, start_date.month, 26),
            ]
            state_log = pd.DataFrame(
                {
                    COL_DATE: days,
                    "is_month_end": [True, False, False],
                    "haa.spy_target_weight": [0.25, 0.25, 0.25],
                    "rotation.vxus_target_weight": [1.0, 1.0, 1.0],
                }
            )
            equity = pd.DataFrame({COL_DATE: days, "equity": [100.0, 101.0, 102.0]})
            summary = {"cagr": 1.0, "mdd": -1.0, "calmar": 1.0}
            return PortfolioResult("t", "t", equity, pd.DataFrame(), summary, config, state_log_df=state_log)

        monkeypatch.setattr(se, "run_portfolio_backtest", _fake_run)
        monkeypatch.setattr(cx, "validate_portfolio_result", lambda result: [])
        spliced = [c for c in cx.build_combo_cases() if c.group == cx.GROUP_SPLICED]
        picks = {
            cx.CANDIDATE_COMBO: next(c for c in spliced if c.cell == (5, 5)),
            se.CANDIDATE_HAA: next(c for c in spliced if c.candidate == se.CANDIDATE_HAA and c.w_pct == 10),
            se.CANDIDATE_ROTATION: next(c for c in spliced if c.candidate == se.CANDIDATE_ROTATION and c.w_pct == 10),
            se.CANDIDATE_BASELINE: next(c for c in spliced if c.candidate == se.CANDIDATE_BASELINE and c.w_pct == 10),
            se.CANDIDATE_Q2_2XS: next(c for c in spliced if c.candidate == se.CANDIDATE_Q2_2XS),
        }

        # When
        targets = {
            name: {m: set(t.columns) for m, t in cx.run_combo_case(case, _Q2_SLOTS).decision_targets.items()}
            for name, case in picks.items()
        }

        # Then
        assert targets == {
            cx.CANDIDATE_COMBO: {se.CANDIDATE_HAA: {"spy"}, se.CANDIDATE_ROTATION: {"vxus"}},
            se.CANDIDATE_HAA: {se.CANDIDATE_HAA: {"spy"}},
            se.CANDIDATE_ROTATION: {se.CANDIDATE_ROTATION: {"vxus"}},
            se.CANDIDATE_BASELINE: {},
            se.CANDIDATE_Q2_2XS: {},
        }
