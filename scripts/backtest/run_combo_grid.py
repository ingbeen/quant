"""조합 그리드 실행 스크립트 — Q-2-2XS + HAA + 로테이션, 세 판

「Q-2-2XS (100 − h − r)% + HAA h% + 로테이션 r%」 16칸을 대체 판 · 이어 붙인 판 · 완전 실물판(과 대체 판 확인용
겹침 묶음)으로 돌리고, 같은 합계의 기준선 · HAA 단독 · 로테이션 단독 · Q-2-2XS 단독을 함께 돌려 요약 CSV 셋만
저장한다. 실행별 결과 폴더는 만들지 않는다. 실행 목록 · 판정 · 대체 판 확인 계산은
qbt.backtest.combo_experiment 가 하고, 이 스크립트는 병렬 실행 · 반올림 · 저장만 한다.

실행 명령어:
    poetry run python scripts/backtest/run_combo_grid.py
"""

import os
import sys
import time
from typing import Any

import pandas as pd

from qbt.backtest.combo_experiment import (
    BASIS_ALT,
    BASIS_GROUPS,
    BASIS_JUDGMENT,
    BASIS_REAL,
    BASIS_SPLICED,
    CANDIDATE_COMBO,
    COMBO_CELLS,
    COMPARATORS,
    GROUP_ALT,
    GROUP_ALT_OVERLAP,
    GROUP_REAL,
    GROUP_SPLICED,
    AltCheckRow,
    Cell,
    ComboCaseResult,
    ComboJudgmentRow,
    build_case_config,
    build_combo_cases,
    collect_alt_check,
    collect_combo_judgments,
    run_combo_case,
)
from qbt.backtest.constants import ROUND_PERCENT, ROUND_RATIO
from qbt.backtest.portfolio_configs import get_portfolio_config
from qbt.backtest.supplement_experiment import (
    ALL_PHASE_WINDOWS,
    CANDIDATE_BASELINE,
    CANDIDATE_HAA,
    CANDIDATE_Q2_2XS,
    CANDIDATE_ROTATION,
    COMBO_PCTS,
    W_PCTS,
)
from qbt.common_constants import META_JSON_PATH, PORTFOLIO_COMBO_GRID_RESULTS_DIR
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata
from qbt.utils.parallel_executor import execute_parallel_with_kwargs

logger = get_logger(__name__)

_RUNS_FILENAME = "combo_runs.csv"
_JUDGMENT_FILENAME = "combo_judgment.csv"
_ALT_CHECK_FILENAME = "combo_alt_check.csv"
# 한글 헤더라 Excel 이 UTF-8 로 열도록 BOM 을 붙인다 (사람이 읽고 판정하는 산출물 — 대시보드는 읽지 않는다)
_CSV_ENCODING = "utf-8-sig"

# --- 표시 이름 ---
_GROUP_DISPLAY = {
    GROUP_ALT: "대체 판",
    GROUP_SPLICED: "이어 붙인 판",
    GROUP_REAL: "완전 실물판",
    GROUP_ALT_OVERLAP: "대체 판 (이어 붙인 판 시작일부터)",
}
_CANDIDATE_DISPLAY = {
    CANDIDATE_COMBO: "조합",
    CANDIDATE_BASELINE: "SHY(기준선)",
    CANDIDATE_HAA: "HAA 단독",
    CANDIDATE_ROTATION: "로테이션 단독",
    CANDIDATE_Q2_2XS: "Q-2-2XS 단독",
}
_BASIS_DISPLAY = {
    BASIS_ALT: "대체 판 지도",
    BASIS_SPLICED: "이어 붙인 판 지도",
    BASIS_REAL: "완전 실물판 지도",
    BASIS_JUDGMENT: "판정 (이어 붙인 판 · 완전 실물판 모두)",
}
_ADVANTAGE_DISPLAY = {
    CANDIDATE_BASELINE: "기준선 대비 우위",
    CANDIDATE_HAA: "HAA 단독 대비 우위",
    CANDIDATE_ROTATION: "로테이션 단독 대비 우위",
}

# --- CSV 헤더 ---
DISPLAY_GROUP = "묶음"
DISPLAY_CANDIDATE = "구성"
DISPLAY_HAA = "HAA(%)"
DISPLAY_ROTATION = "로테이션(%)"
DISPLAY_TOTAL = "합계(%)"
DISPLAY_START = "시작일"
DISPLAY_END = "끝날"
DISPLAY_CAGR = "CAGR(%)"
DISPLAY_MDD = "MDD(%)"
DISPLAY_CALMAR = "Calmar"
DISPLAY_SELL_TRADES = "매도 거래 수"
DISPLAY_TURNOVER = "연 회전율"
DISPLAY_BASIS = "판정 기준"
DISPLAY_COMBO_CALMAR = "조합 Calmar"
DISPLAY_SPLICED_ABOVE = "이어 붙인 판 높음"
DISPLAY_REAL_ABOVE = "완전 실물판 높음"
DISPLAY_COUNTED_ABOVE = "셋보다 높음(판정에 센 것)"
DISPLAY_BOUNDARY = "경계(우위 0 근처)"
DISPLAY_CLUSTER = "이 칸의 덩어리(HAA/로테이션 %)"
DISPLAY_PASSED = "판정"
DISPLAY_CLUSTERS = "통과 덩어리(HAA/로테이션 %)"
DISPLAY_ALT_CALMAR = "대체 판 Calmar"
DISPLAY_SPLICED_CALMAR = "이어 붙인 판 Calmar"
DISPLAY_CALMAR_DIFF = "Calmar 차이(대체-이어 붙인)"
DISPLAY_ALT_ABOVE = "대체 판 높음"
DISPLAY_SIGN_MATCH = "일치"
DISPLAY_HAA_AGREEMENT = "HAA 판단 일치율"
DISPLAY_ROTATION_AGREEMENT = "로테이션 판단 일치율"
DISPLAY_SIGNAL_MONTHS = "비교 달 수"
DISPLAY_MATCH_COUNT = f"일치 수({len(COMBO_CELLS)} 중)"
DISPLAY_ALT_CLUSTERS = "대체 판 통과 덩어리"
DISPLAY_SPLICED_CLUSTERS = "이어 붙인 판 통과 덩어리"
DISPLAY_CLUSTER_VERDICT_MATCH = "통과 여부 일치"

_YES = "예"
_NO = "아니오"


def _yes_no(value: bool) -> str:
    return _YES if value else _NO


def _format_cell(cell: Cell) -> str:
    return f"{cell[0]}/{cell[1]}"


def _format_cluster(cluster: tuple[Cell, ...]) -> str:
    return " · ".join(_format_cell(cell) for cell in cluster)


def _format_clusters(clusters: tuple[tuple[Cell, ...], ...]) -> str:
    return " | ".join(_format_cluster(cluster) for cluster in clusters)


def _round_or_none(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _shares(result: ComboCaseResult) -> tuple[int | None, int | None]:
    """(HAA %, 로테이션 %) — 조합은 칸, 단독은 그 비중, 기준선 · Q-2-2XS 단독은 빈 값."""
    case = result.case
    if case.cell is not None:
        return case.cell
    if case.candidate == CANDIDATE_HAA:
        return case.w_pct, None
    if case.candidate == CANDIDATE_ROTATION:
        return None, case.w_pct
    return None, None


def _runs_df(results: list[ComboCaseResult]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for r in results:
        s = r.summary
        haa, rotation = _shares(r)
        row: dict[str, Any] = {
            DISPLAY_GROUP: _GROUP_DISPLAY[r.case.group],
            DISPLAY_CANDIDATE: _CANDIDATE_DISPLAY[r.case.candidate],
            DISPLAY_HAA: haa,
            DISPLAY_ROTATION: rotation,
            DISPLAY_TOTAL: r.case.w_pct,
            DISPLAY_START: str(s.start_date),
            DISPLAY_END: str(s.end_date),
            DISPLAY_CAGR: round(s.cagr, ROUND_PERCENT),
            DISPLAY_MDD: round(s.mdd, ROUND_PERCENT),
            DISPLAY_CALMAR: round(s.calmar, ROUND_RATIO),
            DISPLAY_SELL_TRADES: s.sell_trades,
            DISPLAY_TURNOVER: round(s.annual_turnover, ROUND_RATIO),
        }
        for window in ALL_PHASE_WINDOWS:
            row[f"{window.display_name} 수익률(%)"] = _round_or_none(s.phase_returns[window.phase_id], ROUND_PERCENT)
            row[f"{window.display_name} 구간MDD(%)"] = _round_or_none(s.phase_mdds[window.phase_id], ROUND_PERCENT)
        rows.append(row)
    return pd.DataFrame(rows)


def _judgment_df(rows: list[ComboJudgmentRow]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for row in rows:
        single = row.per_group[BASIS_GROUPS[row.basis][0]] if len(row.per_group) == 1 else None
        record: dict[str, Any] = {
            DISPLAY_BASIS: _BASIS_DISPLAY[row.basis],
            DISPLAY_HAA: row.cell[0],
            DISPLAY_ROTATION: row.cell[1],
            DISPLAY_TOTAL: row.cell[0] + row.cell[1],
            DISPLAY_COMBO_CALMAR: None if single is None else round(single.combo_calmar, ROUND_RATIO),
        }
        for comparator in COMPARATORS:
            value = None if single is None else single.advantages[comparator]
            record[_ADVANTAGE_DISPLAY[comparator]] = _round_or_none(value, ROUND_RATIO)
        spliced = row.per_group.get(GROUP_SPLICED) if single is None else None
        real = row.per_group.get(GROUP_REAL) if single is None else None
        record[DISPLAY_SPLICED_ABOVE] = "" if spliced is None else _yes_no(spliced.above)
        record[DISPLAY_REAL_ABOVE] = "" if real is None else _yes_no(real.above)
        record[DISPLAY_COUNTED_ABOVE] = _yes_no(row.counted_above)
        record[DISPLAY_BOUNDARY] = _YES if row.boundary else ""
        record[DISPLAY_CLUSTER] = _format_cluster(row.cluster)
        record[DISPLAY_PASSED] = "통과" if row.passed else "탈락"
        record[DISPLAY_CLUSTERS] = _format_clusters(row.clusters)
        records.append(record)
    return pd.DataFrame(records)


def _alt_check_df(rows: list[AltCheckRow]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                DISPLAY_HAA: row.cell[0],
                DISPLAY_ROTATION: row.cell[1],
                DISPLAY_TOTAL: row.cell[0] + row.cell[1],
                DISPLAY_ALT_CALMAR: round(row.alt.combo_calmar, ROUND_RATIO),
                DISPLAY_SPLICED_CALMAR: round(row.spliced.combo_calmar, ROUND_RATIO),
                DISPLAY_CALMAR_DIFF: round(row.alt.combo_calmar - row.spliced.combo_calmar, ROUND_RATIO),
                DISPLAY_ALT_ABOVE: _yes_no(row.alt.above),
                DISPLAY_SPLICED_ABOVE: _yes_no(row.spliced.above),
                DISPLAY_SIGN_MATCH: _yes_no(row.sign_match),
                DISPLAY_BOUNDARY: _YES if row.boundary else "",
                DISPLAY_HAA_AGREEMENT: round(row.haa_agreement, ROUND_RATIO),
                DISPLAY_ROTATION_AGREEMENT: round(row.rotation_agreement, ROUND_RATIO),
                DISPLAY_SIGNAL_MONTHS: row.signal_months,
                DISPLAY_MATCH_COUNT: row.match_count,
                DISPLAY_ALT_CLUSTERS: _format_clusters(row.alt_clusters),
                DISPLAY_SPLICED_CLUSTERS: _format_clusters(row.spliced_clusters),
                DISPLAY_CLUSTER_VERDICT_MATCH: _yes_no(row.cluster_verdict_match),
            }
            for row in rows
        ]
    )


def _print_maps(rows: list[ComboJudgmentRow]) -> None:
    """판정 기준마다 4 × 4 지도 — 행 HAA, 열 로테이션. O = 셋보다 높음, * = 통과 덩어리 안."""
    for basis in BASIS_GROUPS:
        basis_rows = {r.cell: r for r in rows if r.basis == basis}
        table_rows: list[list[str]] = []
        for h in COMBO_PCTS:
            marks = []
            for r in COMBO_PCTS:
                row = basis_rows[(h, r)]
                marks.append(("O" if row.counted_above else ".") + ("*" if row.cluster else ""))
            table_rows.append([f"HAA {h}%", *marks])
        first = next(iter(basis_rows.values()))
        verdict = "통과" if first.passed else "탈락"
        clusters = _format_clusters(first.clusters) or "-"
        columns = [("HAA \\ 로테이션", 14, Align.LEFT)] + [(f"{r}%", 6, Align.LEFT) for r in COMBO_PCTS]
        TableLogger(columns, logger).print_table(
            table_rows, title=f"[{_BASIS_DISPLAY[basis]}] {verdict} · 통과 덩어리 {clusters}"
        )


def _print_alt_check(rows: list[AltCheckRow]) -> None:
    first = rows[0]
    columns = [
        ("일치 칸", 10, Align.LEFT),
        ("HAA 판단 일치율", 16, Align.LEFT),
        ("로테이션 판단 일치율", 20, Align.LEFT),
        ("비교 달 수", 10, Align.LEFT),
        ("통과 여부 일치", 14, Align.LEFT),
    ]
    TableLogger(columns, logger).print_table(
        [
            [
                f"{first.match_count}/{len(COMBO_CELLS)}",
                f"{min(r.haa_agreement for r in rows):.4f} – {max(r.haa_agreement for r in rows):.4f}",
                f"{min(r.rotation_agreement for r in rows):.4f} – {max(r.rotation_agreement for r in rows):.4f}",
                str(first.signal_months),
                _yes_no(first.cluster_verdict_match),
            ]
        ],
        title="[대체 판 확인 — 이어 붙인 판 시작일부터 겹치는 기간, 보고용]",
    )


@cli_exception_handler
def main() -> int:
    """메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 실행 목록 (Q-2-2XS 슬롯의 SoT 는 공식 실험 portfolio_q2_2xs)
    q2_2xs_slots = get_portfolio_config("portfolio_q2_2xs").asset_slots
    cases = build_combo_cases()
    logger.debug(f"조합 그리드 실행 {len(cases)}회")

    # 2. 병렬 실행 (워커가 시작일 확인 · 정합성 검사 · 요약까지 한다)
    raw_count = os.cpu_count()
    max_workers = max(1, raw_count - 1) if raw_count is not None else None
    started = time.perf_counter()
    results: list[ComboCaseResult] = execute_parallel_with_kwargs(
        func=run_combo_case,
        inputs=[{"case": case, "q2_2xs_slots": q2_2xs_slots} for case in cases],
        max_workers=max_workers,
    )
    logger.debug(f"실행 완료: {len(results)}회, {time.perf_counter() - started:.1f}초 (워커 {max_workers})")

    # 3. 정합성 위반이면 그 구성과 함께 멈춘다 (포트폴리오 러너와 같은 정책)
    violated = [r for r in results if r.violations]
    if violated:
        for r in violated:
            name = build_case_config(q2_2xs_slots, r.case).experiment_name
            logger.error(f"[{name}] (시작 {r.case.start_date}) 정합성 위반 {len(r.violations)}건")
            for v in r.violations:
                logger.error(f"  {v}")
        raise ValueError(f"정합성 검증 위반이 있는 실행 {len(violated)}개. 상세 내역은 위 로그를 확인하세요.")
    periods = sorted({(r.case.group, str(r.summary.start_date), str(r.summary.end_date)) for r in results})
    logger.debug(f"정합성 위반 0. 묶음별 실제 기간: {periods}")

    # 4. 판정 · 대체 판 확인 (반올림 전 값)
    judgments = collect_combo_judgments(results)
    alt_check = collect_alt_check(results)

    # 5. 저장
    PORTFOLIO_COMBO_GRID_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    runs_path = PORTFOLIO_COMBO_GRID_RESULTS_DIR / _RUNS_FILENAME
    judgment_path = PORTFOLIO_COMBO_GRID_RESULTS_DIR / _JUDGMENT_FILENAME
    alt_check_path = PORTFOLIO_COMBO_GRID_RESULTS_DIR / _ALT_CHECK_FILENAME
    _runs_df(results).to_csv(runs_path, index=False, encoding=_CSV_ENCODING)
    _judgment_df(judgments).to_csv(judgment_path, index=False, encoding=_CSV_ENCODING)
    _alt_check_df(alt_check).to_csv(alt_check_path, index=False, encoding=_CSV_ENCODING)
    logger.debug(f"저장 완료: {runs_path}, {judgment_path}, {alt_check_path}")

    # 6. 요약 출력
    _print_maps(judgments)
    _print_alt_check(alt_check)

    # 7. 메타데이터
    verdicts = {
        basis: {
            "passed": next(r.passed for r in judgments if r.basis == basis),
            "clusters": _format_clusters(next(r.clusters for r in judgments if r.basis == basis)),
        }
        for basis in BASIS_GROUPS
    }
    metadata: dict[str, Any] = {
        "params": {
            "combo_pcts": list(COMBO_PCTS),
            "w_pcts": list(W_PCTS),
            "run_count": len(results),
            "group_periods": [list(item) for item in periods],
        },
        "results_summary": {"verdicts": verdicts, "alt_check_match_count": alt_check[0].match_count},
        "output_files": {
            "combo_runs_csv": str(runs_path),
            "combo_judgment_csv": str(judgment_path),
            "combo_alt_check_csv": str(alt_check_path),
        },
    }
    save_metadata("portfolio_combo_grid", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
