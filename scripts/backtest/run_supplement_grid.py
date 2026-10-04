"""보완 전략 비중 그리드 실행 스크립트

후보 4개(금 확대 · HAA · 로테이션 · EWY)와 기준선(SHY)을 「Q-2-2XS (100−w)% + 후보 w%」로
주 비교 · 보조 기간에 돌리고, 대용 검증 관문 · 쌍별 비교를 함께 돌려 요약 CSV 셋만 저장한다.
실행별 결과 폴더는 만들지 않는다 (공식 등록은 통과 후보만, 설계서 D21).
실행 목록 · 판정 · 관문 계산은 qbt.backtest.supplement_experiment 가 하고, 이 스크립트는 병렬 실행 ·
반올림 · 저장만 한다.

실행 명령어:
    poetry run python scripts/backtest/run_supplement_grid.py
"""

import os
import sys
import time
from typing import Any

import pandas as pd

from qbt.backtest.constants import ROUND_PERCENT, ROUND_RATIO
from qbt.backtest.portfolio_configs import get_portfolio_config
from qbt.backtest.supplement_experiment import (
    BASIS_BOTH,
    BASIS_SUB_ONLY,
    CANDIDATE_DISPLAY_NAMES,
    GATE_HAA_BUNDLE,
    GATE_HAA_PAIR_BIL,
    GATE_HAA_PAIR_PDBC,
    GATE_HAA_PAIR_VEA,
    GATE_ROTATION,
    GROUP_GATE_HAA,
    GROUP_GATE_ROTATION,
    GROUP_MAIN,
    GROUP_PAIR_BIL,
    GROUP_PAIR_PDBC,
    GROUP_PAIR_VEA,
    GROUP_SUB,
    PHASE_WINDOWS,
    SIGNAL_AGREEMENT_PASS_RATE,
    VARIANT_GATE_REAL,
    VARIANT_PAIR_BIL,
    VARIANT_PAIR_PDBC,
    VARIANT_PAIR_VEA,
    VARIANT_PURE,
    VARIANT_REAL,
    VARIANT_SPLICED,
    W_PCTS,
    GateRow,
    GridCaseResult,
    JudgmentRow,
    build_experiment_config,
    build_grid_cases,
    collect_gates,
    collect_judgments,
    compute_advantages,
    run_grid_case,
)
from qbt.common_constants import META_JSON_PATH, PORTFOLIO_GRID_RESULTS_DIR
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.meta_manager import save_metadata
from qbt.utils.parallel_executor import execute_parallel_with_kwargs

logger = get_logger(__name__)

_GRID_RUNS_FILENAME = "grid_runs.csv"
_JUDGMENT_FILENAME = "judgment.csv"
_PROXY_GATE_FILENAME = "proxy_gate.csv"
# 한글 헤더라 Excel 이 UTF-8 로 열도록 BOM 을 붙인다 (사람이 읽고 판정하는 산출물 — 대시보드는 읽지 않는다)
_CSV_ENCODING = "utf-8-sig"

# --- 표시 이름 ---
_GROUP_DISPLAY = {
    GROUP_MAIN: "주 비교",
    GROUP_SUB: "보조",
    GROUP_GATE_ROTATION: "로테이션 관문",
    GROUP_GATE_HAA: "HAA 관문",
    GROUP_PAIR_VEA: "HAA VEA 쌍",
    GROUP_PAIR_BIL: "HAA BIL 쌍",
    GROUP_PAIR_PDBC: "HAA PDBC 쌍",
}
_VARIANT_DISPLAY = {
    VARIANT_SPLICED: "이어 붙인 판",
    VARIANT_REAL: "실물판",
    VARIANT_GATE_REAL: "관문 실물판",
    VARIANT_PURE: "순수 대용판",
    VARIANT_PAIR_VEA: "VEA 만 실물",
    VARIANT_PAIR_BIL: "BIL 만 실물",
    VARIANT_PAIR_PDBC: "PDBC 만 실물",
}
_BASIS_DISPLAY = {
    BASIS_BOTH: "주 비교 + 보조",
    BASIS_SUB_ONLY: "보조만 (대용 탈락 시 · 금융위기 미검증)",
}
_GATE_DISPLAY = {
    GATE_ROTATION: "로테이션 VXUS 대용 (관문)",
    GATE_HAA_BUNDLE: "HAA 대용 묶음 (관문)",
    GATE_HAA_PAIR_VEA: "HAA VEA 쌍 (원인)",
    GATE_HAA_PAIR_BIL: "HAA BIL 쌍 (원인)",
    GATE_HAA_PAIR_PDBC: "HAA PDBC 쌍 (원인)",
}

# --- CSV 헤더 ---
DISPLAY_GROUP = "묶음"
DISPLAY_CANDIDATE = "후보"
DISPLAY_W = "w(%)"
DISPLAY_VARIANT = "판"
DISPLAY_START = "시작일"
DISPLAY_END = "끝날"
DISPLAY_CAGR = "CAGR(%)"
DISPLAY_MDD = "MDD(%)"
DISPLAY_CALMAR = "Calmar"
DISPLAY_ADVANTAGE = "기준선 대비 Calmar 우위"
DISPLAY_SELL_TRADES = "매도 거래 수"
DISPLAY_TURNOVER = "연 회전율"
DISPLAY_BASIS = "판정 기준"
DISPLAY_MAIN_ADVANTAGE = "주 비교 우위"
DISPLAY_SUB_ADVANTAGE = "보조 우위"
DISPLAY_COUNTED_ABOVE = "판정에 센 높음"
DISPLAY_BOUNDARY = "경계(우위 0 근처)"
DISPLAY_PASSED = "판정"
DISPLAY_PLATEAUS = "고원 구간"
DISPLAY_GATE = "관문"
DISPLAY_PROXY_CALMAR = "대용판 Calmar"
DISPLAY_REAL_CALMAR = "실물판 Calmar"
DISPLAY_CALMAR_DIFF = "Calmar 차이(실물-대용)"
DISPLAY_PROXY_ADVANTAGE = "대용판 우위"
DISPLAY_REAL_ADVANTAGE = "실물판 우위"
DISPLAY_SIGN_MATCH = "판정 일치"
DISPLAY_SIGNAL_RATE = "신호 일치율"
DISPLAY_SIGNAL_MONTHS = "비교 달 수"
DISPLAY_SIGNAL_PASS = "신호 관문(95%)"
DISPLAY_MATCH_COUNT = "판정 일치 수(7 중)"
DISPLAY_PROXY_PLATEAUS = "대용판 고원"
DISPLAY_REAL_PLATEAUS = "실물판 고원"
DISPLAY_PLATEAU_VERDICT_MATCH = "고원 판정 일치"

_YES = "예"
_NO = "아니오"


def _yes_no(value: bool) -> str:
    return _YES if value else _NO


def _format_plateaus(plateaus: tuple[tuple[int, int], ...]) -> str:
    return " · ".join(f"{start}-{end}%" for start, end in plateaus)


def _round_or_none(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def _grid_runs_df(results: list[GridCaseResult]) -> pd.DataFrame:
    advantages = compute_advantages(results)
    rows: list[dict[str, Any]] = []
    for r in results:
        s = r.summary
        advantage = advantages.get(r.case)
        row: dict[str, Any] = {
            DISPLAY_GROUP: _GROUP_DISPLAY[r.case.group],
            DISPLAY_CANDIDATE: CANDIDATE_DISPLAY_NAMES[r.case.candidate],
            DISPLAY_W: r.case.w_pct,
            DISPLAY_VARIANT: _VARIANT_DISPLAY[r.case.variant],
            DISPLAY_START: str(s.start_date),
            DISPLAY_END: str(s.end_date),
            DISPLAY_CAGR: round(s.cagr, ROUND_PERCENT),
            DISPLAY_MDD: round(s.mdd, ROUND_PERCENT),
            DISPLAY_CALMAR: round(s.calmar, ROUND_RATIO),
            DISPLAY_ADVANTAGE: _round_or_none(advantage, ROUND_RATIO),
            DISPLAY_SELL_TRADES: s.sell_trades,
            DISPLAY_TURNOVER: round(s.annual_turnover, ROUND_RATIO),
        }
        for window in PHASE_WINDOWS:
            row[f"{window.display_name} 수익률(%)"] = _round_or_none(s.phase_returns[window.phase_id], ROUND_PERCENT)
            row[f"{window.display_name} 구간MDD(%)"] = _round_or_none(s.phase_mdds[window.phase_id], ROUND_PERCENT)
        rows.append(row)
    return pd.DataFrame(rows)


def _judgment_df(rows: list[JudgmentRow]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                DISPLAY_CANDIDATE: CANDIDATE_DISPLAY_NAMES[row.candidate],
                DISPLAY_BASIS: _BASIS_DISPLAY[row.basis],
                DISPLAY_W: row.w_pct,
                DISPLAY_MAIN_ADVANTAGE: _round_or_none(row.main_advantage, ROUND_RATIO),
                DISPLAY_SUB_ADVANTAGE: round(row.sub_advantage, ROUND_RATIO),
                DISPLAY_COUNTED_ABOVE: _yes_no(row.counted_above),
                DISPLAY_BOUNDARY: _YES if row.boundary else "",
                DISPLAY_PASSED: "통과" if row.passed else "탈락",
                DISPLAY_PLATEAUS: _format_plateaus(row.plateaus),
            }
            for row in rows
        ]
    )


def _proxy_gate_df(rows: list[GateRow]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                DISPLAY_GATE: _GATE_DISPLAY[row.gate],
                DISPLAY_START: str(row.start_date),
                DISPLAY_W: row.w_pct,
                DISPLAY_PROXY_CALMAR: round(row.proxy_calmar, ROUND_RATIO),
                DISPLAY_REAL_CALMAR: round(row.real_calmar, ROUND_RATIO),
                DISPLAY_CALMAR_DIFF: round(row.real_calmar - row.proxy_calmar, ROUND_RATIO),
                DISPLAY_PROXY_ADVANTAGE: round(row.proxy_advantage, ROUND_RATIO),
                DISPLAY_REAL_ADVANTAGE: round(row.real_advantage, ROUND_RATIO),
                DISPLAY_SIGN_MATCH: _yes_no(row.sign_match),
                DISPLAY_BOUNDARY: _YES if row.boundary else "",
                DISPLAY_SIGNAL_RATE: round(row.signal_agreement, ROUND_RATIO),
                DISPLAY_SIGNAL_MONTHS: row.signal_months,
                DISPLAY_SIGNAL_PASS: _yes_no(row.signal_pass),
                DISPLAY_MATCH_COUNT: row.match_count,
                DISPLAY_PROXY_PLATEAUS: _format_plateaus(row.proxy_plateaus),
                DISPLAY_REAL_PLATEAUS: _format_plateaus(row.real_plateaus),
                DISPLAY_PLATEAU_VERDICT_MATCH: _yes_no(row.plateau_verdict_match),
            }
            for row in rows
        ]
    )


def _print_judgments(rows: list[JudgmentRow]) -> None:
    table_rows: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if (row.candidate, row.basis) in seen:
            continue
        seen.add((row.candidate, row.basis))
        table_rows.append(
            [
                CANDIDATE_DISPLAY_NAMES[row.candidate],
                _BASIS_DISPLAY[row.basis],
                "통과" if row.passed else "탈락",
                _format_plateaus(row.plateaus) or "-",
            ]
        )
    columns = [("후보", 20, Align.LEFT), ("판정 기준", 40, Align.LEFT), ("판정", 6, Align.LEFT), ("고원", 20, Align.LEFT)]
    TableLogger(columns, logger).print_table(table_rows, title="[통과 판정 (D24 · D47)]")


def _print_gates(rows: list[GateRow]) -> None:
    table_rows: list[list[str]] = []
    for gate in _GATE_DISPLAY:
        gate_rows = [r for r in rows if r.gate == gate]
        first = gate_rows[0]
        table_rows.append(
            [
                _GATE_DISPLAY[gate],
                str(first.start_date),
                f"{first.match_count}/{len(W_PCTS)}",
                f"{min(r.signal_agreement for r in gate_rows):.4f}",
                _yes_no(first.plateau_verdict_match),
            ]
        )
    columns = [
        ("관문", 28, Align.LEFT),
        ("시작일", 12, Align.LEFT),
        ("판정 일치", 10, Align.LEFT),
        ("최소 신호 일치율", 18, Align.LEFT),
        ("고원 판정 일치", 14, Align.LEFT),
    ]
    TableLogger(columns, logger).print_table(table_rows, title=f"[대용 검증 — 신호 관문 {SIGNAL_AGREEMENT_PASS_RATE:.0%}]")


@cli_exception_handler
def main() -> int:
    """메인 실행 함수.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    # 1. 실행 목록 (Q-2-2XS 슬롯의 SoT 는 공식 실험 portfolio_q2_2xs)
    q2_2xs_slots = get_portfolio_config("portfolio_q2_2xs").asset_slots
    cases = build_grid_cases()
    logger.debug(f"보완 전략 그리드 실행 {len(cases)}회")

    # 2. 병렬 실행 (워커가 시작일 확인 · 정합성 검사 · 요약까지 한다)
    raw_count = os.cpu_count()
    max_workers = max(1, raw_count - 1) if raw_count is not None else None
    started = time.perf_counter()
    results: list[GridCaseResult] = execute_parallel_with_kwargs(
        func=run_grid_case,
        inputs=[{"case": case, "q2_2xs_slots": q2_2xs_slots} for case in cases],
        max_workers=max_workers,
    )
    logger.debug(f"실행 완료: {len(results)}회, {time.perf_counter() - started:.1f}초 (워커 {max_workers})")

    # 3. 정합성 위반이면 그 구성과 함께 멈춘다 (포트폴리오 러너와 같은 정책)
    violated = [r for r in results if r.violations]
    if violated:
        for r in violated:
            name = build_experiment_config(
                q2_2xs_slots, r.case.candidate, r.case.w_pct, r.case.variant, r.case.start_date
            ).experiment_name
            logger.error(f"[{name}] (시작 {r.case.start_date}) 정합성 위반 {len(r.violations)}건")
            for v in r.violations:
                logger.error(f"  {v}")
        raise ValueError(f"정합성 검증 위반이 있는 실행 {len(violated)}개. 상세 내역은 위 로그를 확인하세요.")
    starts = sorted({(r.case.group, str(r.summary.start_date), str(r.summary.end_date)) for r in results})
    logger.debug(f"정합성 위반 0. 묶음별 실제 기간: {starts}")

    # 4. 판정 · 대용 검증 (반올림 전 값)
    judgments = collect_judgments(results)
    gates = collect_gates(results)

    # 5. 저장
    PORTFOLIO_GRID_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    grid_runs_path = PORTFOLIO_GRID_RESULTS_DIR / _GRID_RUNS_FILENAME
    judgment_path = PORTFOLIO_GRID_RESULTS_DIR / _JUDGMENT_FILENAME
    proxy_gate_path = PORTFOLIO_GRID_RESULTS_DIR / _PROXY_GATE_FILENAME
    _grid_runs_df(results).to_csv(grid_runs_path, index=False, encoding=_CSV_ENCODING)
    _judgment_df(judgments).to_csv(judgment_path, index=False, encoding=_CSV_ENCODING)
    _proxy_gate_df(gates).to_csv(proxy_gate_path, index=False, encoding=_CSV_ENCODING)
    logger.debug(f"저장 완료: {grid_runs_path}, {judgment_path}, {proxy_gate_path}")

    # 6. 요약 출력
    _print_judgments(judgments)
    _print_gates(gates)

    # 7. 메타데이터
    passed = sorted(
        {f"{CANDIDATE_DISPLAY_NAMES[r.candidate]} / {_BASIS_DISPLAY[r.basis]}" for r in judgments if r.passed}
    )
    metadata: dict[str, Any] = {
        "params": {
            "w_pcts": list(W_PCTS),
            "run_count": len(results),
            "group_periods": [list(item) for item in starts],
        },
        "results_summary": {"passed": passed},
        "output_files": {
            "grid_runs_csv": str(grid_runs_path),
            "judgment_csv": str(judgment_path),
            "proxy_gate_csv": str(proxy_gate_path),
        },
    }
    save_metadata("portfolio_grid", metadata)
    logger.debug(f"메타데이터 저장 완료: {META_JSON_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
