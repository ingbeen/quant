"""보완 전략 실험 — Q-2-2XS (100−w)% + 후보 w% 비중 그리드 · 대용 검증 · 통과 판정

설계서(`docs/research/Q2_2XS_보완_전략_설계.md`) 7 – 9장의 실험을 담는다.
구성 만들기 · 실행 목록 · 실행 지표 · 신호 일치율 · 기준선 대비 우위 · 통과 판정(D24 · D47) ·
대용 검증(D23 · D41 · D48)이 여기 있고, 러너(`scripts/backtest/run_supplement_grid.py`)는
병렬 실행 · 반올림 · 저장만 한다.

판정 입력은 모두 반올림 전 값이다 — 우위 폭이 0.01 단위라 저장 자릿수로 다시 계산하면 판정이 바뀔 수 있다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

import numpy as np
import pandas as pd

from qbt.backtest.allocators.ewy_buffer_zone import EWY_RISK_ASSET_ID, EWY_SAFE_ASSET_ID
from qbt.backtest.allocators.haa import HAA_ASSET_IDS, HAA_CANARY_SERIES_ID
from qbt.backtest.allocators.us_weakness_rotation import (
    ROTATION_BENCHMARK_SERIES_ID,
    ROTATION_RISK_ASSET_ID,
    ROTATION_SAFE_ASSET_ID,
)
from qbt.backtest.constants import COL_EQUITY, DEFAULT_INITIAL_CAPITAL
from qbt.backtest.engines.portfolio_engine import run_portfolio_backtest
from qbt.backtest.portfolio_types import (
    POSITION_KEY_SEPARATOR,
    AllocationAssetConfig,
    AllocatorMethodConfig,
    AssetSlotConfig,
    MethodConfig,
    PortfolioConfig,
    PortfolioResult,
    SignalSeriesConfig,
    SlotMethodConfig,
)
from qbt.backtest.portfolio_validation import validate_portfolio_result
from qbt.common_constants import (
    ANNUAL_DAYS,
    BIL_DATA_PATH,
    BIL_SYNTHETIC_DATA_PATH,
    COL_DATE,
    DBC_DATA_PATH,
    EFA_DATA_PATH,
    EWY_DATA_PATH,
    GLD_DATA_PATH,
    IEF_DATA_PATH,
    IWM_DATA_PATH,
    PDBC_DATA_PATH,
    PDBC_SYNTHETIC_DATA_PATH,
    PORTFOLIO_RESULTS_DIR,
    SHY_DATA_PATH,
    SPY_DATA_PATH,
    TIP_DATA_PATH,
    TLT_DATA_PATH,
    VEA_DATA_PATH,
    VEA_SYNTHETIC_DATA_PATH,
    VNQ_DATA_PATH,
    VWO_DATA_PATH,
    VXUS_DATA_PATH,
    VXUS_PROXY_DATA_PATH,
    VXUS_SYNTHETIC_DATA_PATH,
)

# ============================================================================
# 비중 · 판정 기준
# ============================================================================

W_PCTS: Final[tuple[int, ...]] = (10, 15, 20, 25, 30, 35, 40)  # 후보 비중 w (%, D6)
MIN_PLATEAU_STEPS: Final = 3  # 고원 = 기준선보다 높은 w 가 연속 3단계 이상 (D24)
SIGNAL_AGREEMENT_PASS_RATE: Final = 0.95  # 대용 관문 ② 신호 일치율 비율 (0.95 = 95%, D23)
# 우위 절댓값이 이보다 작으면 소수 4자리 저장에서 0 이 된다 — 「경계」로 표시해 사용자가 판단한다 (D41 · D48 ⑥)
ADVANTAGE_BOUNDARY: Final = 0.00005
# 배분 규칙 비중은 0.25 단위 · 0 / 1 이라 같은 판단이면 정확히 같다. 합산 순서 차이만 허용한다
_WEIGHT_TOLERANCE: Final = 1e-9

# ============================================================================
# 후보 · 데이터 판 · 실행 묶음
# ============================================================================

CANDIDATE_Q2_2XS: Final = "q2_2xs"  # Q-2-2XS 단독 (국면 표의 비교용)
CANDIDATE_BASELINE: Final = "shy"
CANDIDATE_GOLD: Final = "gold"
CANDIDATE_HAA: Final = "haa"
CANDIDATE_ROTATION: Final = "rotation"
CANDIDATE_EWY: Final = "ewy"
SUPPLEMENT_CANDIDATES: Final[tuple[str, ...]] = (CANDIDATE_GOLD, CANDIDATE_HAA, CANDIDATE_ROTATION, CANDIDATE_EWY)
PROXY_CANDIDATES: Final[tuple[str, ...]] = (CANDIDATE_HAA, CANDIDATE_ROTATION)  # 상장 전 구간에 대용을 쓴다
CANDIDATE_DISPLAY_NAMES: Final[dict[str, str]] = {
    CANDIDATE_Q2_2XS: "Q-2-2XS 단독",
    CANDIDATE_BASELINE: "SHY(기준선)",
    CANDIDATE_GOLD: "금",
    CANDIDATE_HAA: "HAA",
    CANDIDATE_ROTATION: "미국 약세 로테이션",
    CANDIDATE_EWY: "EWY 200일선",
}

VARIANT_SPLICED: Final = "spliced"  # 이어 붙인 판 (주 비교)
VARIANT_REAL: Final = "real"  # 실물판 (보조 기간)
VARIANT_GATE_REAL: Final = "gate_real"  # HAA 관문 실물판 (PDBC 도 실물)
VARIANT_PURE: Final = "pure"  # 순수 대용판 (관문 비교)
VARIANT_PAIR_VEA: Final = "pair_vea"  # HAA 쌍별 — 한 쌍만 실물
VARIANT_PAIR_BIL: Final = "pair_bil"
VARIANT_PAIR_PDBC: Final = "pair_pdbc"

# HAA 대용 3쌍의 판별 파일 (vea, bil, pdbc). 나머지 HAA 자산은 판과 무관하다
_HAA_PROXY_PATHS: Final[dict[str, tuple[Path, Path, Path]]] = {
    VARIANT_SPLICED: (VEA_SYNTHETIC_DATA_PATH, BIL_SYNTHETIC_DATA_PATH, PDBC_SYNTHETIC_DATA_PATH),
    VARIANT_REAL: (VEA_DATA_PATH, BIL_DATA_PATH, PDBC_SYNTHETIC_DATA_PATH),  # 원자재는 이어 붙인 판 (D46)
    VARIANT_GATE_REAL: (VEA_DATA_PATH, BIL_DATA_PATH, PDBC_DATA_PATH),
    VARIANT_PURE: (EFA_DATA_PATH, SHY_DATA_PATH, DBC_DATA_PATH),
    VARIANT_PAIR_VEA: (VEA_DATA_PATH, SHY_DATA_PATH, DBC_DATA_PATH),
    VARIANT_PAIR_BIL: (EFA_DATA_PATH, BIL_DATA_PATH, DBC_DATA_PATH),
    VARIANT_PAIR_PDBC: (EFA_DATA_PATH, SHY_DATA_PATH, PDBC_DATA_PATH),
}
_HAA_FIXED_PATHS: Final[dict[str, Path]] = {
    "spy": SPY_DATA_PATH,
    "iwm": IWM_DATA_PATH,
    "vwo": VWO_DATA_PATH,
    "vnq": VNQ_DATA_PATH,
    "ief": IEF_DATA_PATH,
    "tlt": TLT_DATA_PATH,  # Q-2-2XS 와 같은 파일이라 상계된다 (D17)
}
_ROTATION_VXUS_PATHS: Final[dict[str, Path]] = {
    VARIANT_SPLICED: VXUS_SYNTHETIC_DATA_PATH,
    VARIANT_REAL: VXUS_DATA_PATH,
    VARIANT_PURE: VXUS_PROXY_DATA_PATH,
}
_PLAIN_VARIANTS: Final[tuple[str, ...]] = (VARIANT_SPLICED, VARIANT_REAL)  # 대용이 없는 후보는 두 판의 데이터가 같다

GROUP_MAIN: Final = "main"
GROUP_SUB: Final = "sub"
GROUP_GATE_ROTATION: Final = "gate_rotation"
GROUP_GATE_HAA: Final = "gate_haa"
GROUP_PAIR_VEA: Final = "pair_vea"
GROUP_PAIR_BIL: Final = "pair_bil"
GROUP_PAIR_PDBC: Final = "pair_pdbc"

# 묶음 시작일 — Q-2-2XS 70% + 후보 30% 를 엔진에 올려 잰 가장 늦은 시작일 (설계서 8.3, D45)
MAIN_START_DATE: Final = date(2007, 6, 22)  # Q-2-2XS 와 섞은 HAA
SUB_START_DATE: Final = date(2011, 11, 10)  # 실물 VXUS 로테이션
HAA_GATE_START_DATE: Final = date(2015, 11, 9)  # 실물 PDBC + 12개월 점수
PAIR_VEA_START_DATE: Final = date(2008, 7, 25)
PAIR_BIL_START_DATE: Final = date(2008, 5, 29)

BASIS_BOTH: Final = "main_and_sub"  # 주 비교 + 보조 (D47)
BASIS_SUB_ONLY: Final = "sub_only"  # 대용이 탈락한 후보 — 보조 기간만 (D23)

GATE_ROTATION: Final = "rotation_vxus"
GATE_HAA_BUNDLE: Final = "haa_bundle"  # 대용 셋을 한꺼번에 — 관문 (D41)
GATE_HAA_PAIR_VEA: Final = "haa_pair_vea"  # 쌍별 — 원인 파악용
GATE_HAA_PAIR_BIL: Final = "haa_pair_bil"
GATE_HAA_PAIR_PDBC: Final = "haa_pair_pdbc"
GATE_IDS: Final[tuple[str, ...]] = (
    GATE_ROTATION,
    GATE_HAA_BUNDLE,
    GATE_HAA_PAIR_VEA,
    GATE_HAA_PAIR_BIL,
    GATE_HAA_PAIR_PDBC,
)

_COL_IS_MONTH_END: Final = "is_month_end"
_TARGET_WEIGHT_SUFFIX: Final = "_target_weight"
_EXEC_SHARES_SUFFIX: Final = "_exec_shares"
_EXEC_PRICE_SUFFIX: Final = "_exec_price"


# ============================================================================
# 국면 구간 (설계서 9.2, D48 ⑦)
# ============================================================================


@dataclass(frozen=True)
class PhaseWindow:
    """국면 구간 하나 (양 끝 포함)."""

    phase_id: str
    display_name: str
    start: date
    end: date


PHASE_WINDOWS: Final[tuple[PhaseWindow, ...]] = (
    PhaseWindow("financial_crisis", "금융위기", date(2007, 10, 9), date(2009, 3, 9)),
    PhaseWindow("us_weak_1", "미국 약세 2009-11", date(2009, 3, 10), date(2011, 4, 29)),
    PhaseWindow("us_weak_2", "미국 약세 2017", date(2017, 1, 1), date(2017, 12, 31)),
    PhaseWindow("us_weak_3", "미국 약세 2025-26", date(2025, 1, 1), date(2026, 9, 24)),
    PhaseWindow("sideways_2011", "횡보장 2011", date(2011, 1, 1), date(2011, 12, 31)),
    PhaseWindow("sideways_2015", "횡보장 2015", date(2015, 1, 1), date(2015, 12, 31)),
    PhaseWindow("sideways_2018", "횡보장 2018", date(2018, 1, 1), date(2018, 12, 31)),
    PhaseWindow("crash_2020", "급락 2020", date(2020, 2, 19), date(2020, 3, 23)),
    PhaseWindow("crash_2025", "급락 2025", date(2025, 2, 19), date(2025, 4, 8)),
    PhaseWindow("inflation_2022", "물가 약세장 2022", date(2022, 1, 3), date(2022, 10, 12)),
    PhaseWindow("gold_weak", "금 약세기 2013-15", date(2013, 1, 1), date(2015, 12, 31)),
)


# ============================================================================
# 구성 만들기
# ============================================================================


def _allowed_variants(candidate: str) -> tuple[str, ...]:
    if candidate == CANDIDATE_HAA:
        return tuple(_HAA_PROXY_PATHS)
    if candidate == CANDIDATE_ROTATION:
        return tuple(_ROTATION_VXUS_PATHS)
    if candidate in (CANDIDATE_Q2_2XS, CANDIDATE_BASELINE, CANDIDATE_GOLD, CANDIDATE_EWY):
        return _PLAIN_VARIANTS
    raise ValueError(f"알 수 없는 후보입니다: {candidate!r} (가능: {list(CANDIDATE_DISPLAY_NAMES)})")


def _allocation_asset(asset_id: str, path: Path) -> AllocationAssetConfig:
    return AllocationAssetConfig(asset_id, path, path)


def _buy_and_hold_slot(asset_id: str, path: Path) -> AssetSlotConfig:
    return AssetSlotConfig(
        asset_id=asset_id,
        signal_data_path=path,
        trade_data_path=path,
        target_weight=1.00,
        strategy_id="buy_and_hold",
    )


def _candidate_method(candidate: str, share: float, variant: str) -> MethodConfig:
    if candidate == CANDIDATE_BASELINE:
        return SlotMethodConfig(CANDIDATE_BASELINE, "SHY 보유 (기준선)", share, (_buy_and_hold_slot("shy", SHY_DATA_PATH),))
    if candidate == CANDIDATE_GOLD:
        # Q-2-2XS 의 gld 와 같은 자산 id · 같은 파일이라 종목 단위로 상계된다 (D17)
        return SlotMethodConfig(CANDIDATE_GOLD, "금 보유", share, (_buy_and_hold_slot("gld", GLD_DATA_PATH),))
    if candidate == CANDIDATE_HAA:
        vea, bil, pdbc = _HAA_PROXY_PATHS[variant]
        paths = {**_HAA_FIXED_PATHS, "vea": vea, "bil": bil, "pdbc": pdbc}
        return AllocatorMethodConfig(
            CANDIDATE_HAA,
            "HAA",
            share,
            tuple(_allocation_asset(asset_id, paths[asset_id]) for asset_id in HAA_ASSET_IDS),
            allocator_id="haa",
            signal_series=(SignalSeriesConfig(HAA_CANARY_SERIES_ID, TIP_DATA_PATH),),
        )
    if candidate == CANDIDATE_ROTATION:
        return AllocatorMethodConfig(
            CANDIDATE_ROTATION,
            "미국 약세 감지 로테이션",
            share,
            (
                _allocation_asset(ROTATION_RISK_ASSET_ID, _ROTATION_VXUS_PATHS[variant]),
                _allocation_asset(ROTATION_SAFE_ASSET_ID, SHY_DATA_PATH),
            ),
            allocator_id="us_weakness_rotation",
            signal_series=(SignalSeriesConfig(ROTATION_BENCHMARK_SERIES_ID, SPY_DATA_PATH),),
        )
    if candidate == CANDIDATE_EWY:
        return AllocatorMethodConfig(
            CANDIDATE_EWY,
            "EWY 200일선",
            share,
            (_allocation_asset(EWY_RISK_ASSET_ID, EWY_DATA_PATH), _allocation_asset(EWY_SAFE_ASSET_ID, SHY_DATA_PATH)),
            allocator_id="ewy_buffer_zone",
        )
    raise RuntimeError(f"내부 불변조건 위반: _allowed_variants 를 지난 후보가 매매법 표에 없다 (candidate={candidate!r})")


def build_experiment_config(
    q2_2xs_slots: tuple[AssetSlotConfig, ...],
    candidate: str,
    w_pct: int,
    variant: str,
    start_date: date,
) -> PortfolioConfig:
    """「Q-2-2XS (100−w)% + 후보 w%」 실험 설정을 만든다. 그리드와 등록 실험이 같은 구성임을 이 함수 하나가 보장한다.

    Q-2-2XS 단독(candidate="q2_2xs")은 w_pct=0, 매매법 하나짜리 줄임 표기라 공식 portfolio_q2_2xs 와 같다.

    Args:
        q2_2xs_slots: Q-2-2XS 슬롯 (SoT 는 portfolio_configs 의 portfolio_q2_2xs —
            portfolio_configs 가 이 함수로 등록 실험을 만들므로 여기서 import 하면 순환한다)
        start_date: 설정의 min_start_date (등록 실험이 그리드와 같은 기간으로 돈다)

    Raises:
        ValueError: 정하지 않은 후보 · w · 판 조합 (대용이 없는 후보에 대용 판 등)
    """
    if variant not in _allowed_variants(candidate):
        raise ValueError(f"후보 {candidate!r} 에는 판 {variant!r} 이 없습니다 (가능: {list(_allowed_variants(candidate))})")
    suffix = "" if variant == VARIANT_SPLICED else f"_{variant}"

    if candidate == CANDIDATE_Q2_2XS:
        if w_pct != 0:
            raise ValueError(f"Q-2-2XS 단독은 w_pct=0 이어야 합니다: {w_pct}")
        name = f"portfolio_q2_2xs_alone{suffix}"
        return PortfolioConfig(
            experiment_name=name,
            display_name=CANDIDATE_DISPLAY_NAMES[CANDIDATE_Q2_2XS],
            total_capital=DEFAULT_INITIAL_CAPITAL,
            result_dir=PORTFOLIO_RESULTS_DIR / name,
            asset_slots=q2_2xs_slots,
            min_start_date=start_date,
        )

    if w_pct not in W_PCTS:
        raise ValueError(f"w_pct 는 {list(W_PCTS)} 중 하나여야 합니다: {w_pct}")
    name = f"portfolio_q2_2xs_{candidate}{w_pct}{suffix}"
    return PortfolioConfig(
        experiment_name=name,
        display_name=f"Q-2-2XS {100 - w_pct}% + {CANDIDATE_DISPLAY_NAMES[candidate]} {w_pct}%",
        total_capital=DEFAULT_INITIAL_CAPITAL,
        result_dir=PORTFOLIO_RESULTS_DIR / name,
        methods=(
            SlotMethodConfig(CANDIDATE_Q2_2XS, "Q-2-2XS", (100 - w_pct) / 100, q2_2xs_slots),
            _candidate_method(candidate, w_pct / 100, variant),
        ),
        min_start_date=start_date,
    )


# ============================================================================
# 실행 목록
# ============================================================================


@dataclass(frozen=True)
class GridCase:
    """그리드 실행 하나. w_pct 는 Q-2-2XS 단독이면 0."""

    group: str
    candidate: str
    w_pct: int
    variant: str
    start_date: date


def _cases(group: str, candidate: str, variant: str, start_date: date) -> list[GridCase]:
    return [GridCase(group, candidate, w, variant, start_date) for w in W_PCTS]


def build_grid_cases() -> list[GridCase]:
    """실행 목록 — 주 비교 · 보조 각 36, 로테이션 관문 7, HAA 관문 21, HAA 쌍별 49 (계 149).

    관문 · 쌍별 묶음의 실물판 · 기준선이 다른 묶음에 이미 있으면(같은 시작일) 다시 돌리지 않는다.
    """
    judged = (CANDIDATE_BASELINE, *SUPPLEMENT_CANDIDATES)
    cases: list[GridCase] = []
    for group, variant, start in (
        (GROUP_MAIN, VARIANT_SPLICED, MAIN_START_DATE),
        (GROUP_SUB, VARIANT_REAL, SUB_START_DATE),
    ):
        for candidate in judged:
            cases += _cases(group, candidate, variant, start)
        cases.append(GridCase(group, CANDIDATE_Q2_2XS, 0, variant, start))
    # 로테이션 관문: 실물판 · 기준선은 보조 묶음(같은 2011-11-10)
    cases += _cases(GROUP_GATE_ROTATION, CANDIDATE_ROTATION, VARIANT_PURE, SUB_START_DATE)
    cases += _cases(GROUP_GATE_HAA, CANDIDATE_HAA, VARIANT_GATE_REAL, HAA_GATE_START_DATE)
    cases += _cases(GROUP_GATE_HAA, CANDIDATE_HAA, VARIANT_PURE, HAA_GATE_START_DATE)
    cases += _cases(GROUP_GATE_HAA, CANDIDATE_BASELINE, VARIANT_REAL, HAA_GATE_START_DATE)
    for group, variant, start in (
        (GROUP_PAIR_VEA, VARIANT_PAIR_VEA, PAIR_VEA_START_DATE),
        (GROUP_PAIR_BIL, VARIANT_PAIR_BIL, PAIR_BIL_START_DATE),
    ):
        cases += _cases(group, CANDIDATE_HAA, variant, start)
        cases += _cases(group, CANDIDATE_HAA, VARIANT_PURE, start)
        cases += _cases(group, CANDIDATE_BASELINE, VARIANT_REAL, start)
    # PDBC 쌍: 순수 대용판 · 기준선은 HAA 관문 묶음(같은 2015-11-09)
    cases += _cases(GROUP_PAIR_PDBC, CANDIDATE_HAA, VARIANT_PAIR_PDBC, HAA_GATE_START_DATE)
    return cases


# ============================================================================
# 실행 지표
# ============================================================================


@dataclass(frozen=True)
class RunSummary:
    """실행 하나의 반올림 전 지표. CAGR · MDD · 국면 값은 % (MDD 는 음수), 회전율은 연 비율 (1.0 = 100%)."""

    start_date: date
    end_date: date
    trading_days: int
    cagr: float
    mdd: float
    calmar: float
    sell_trades: int
    annual_turnover: float
    phase_returns: Mapping[str, float | None]
    phase_mdds: Mapping[str, float | None]


def _to_date(value: object) -> date:
    if isinstance(value, datetime):  # pd.Timestamp 도 datetime 이고, datetime 은 date 의 하위 클래스라 먼저 본다
        return value.date()
    if isinstance(value, date):
        return value
    raise ValueError(f"날짜가 아닌 값입니다: {value!r}")


def phase_metrics(
    dates: Sequence[date], equity: Sequence[float], window: PhaseWindow
) -> tuple[float | None, float | None]:
    """국면 구간의 (수익률 %, 구간 MDD %).

    수익률 = 구간 마지막 거래일 자본 ÷ 구간 첫 거래일 전날 자본 − 1, 구간 MDD = 그 전날 자본을 첫 고점으로 둔
    구간 안의 최대 낙폭. 구간이 실행 기간 안에 다 들지 않으면(전날이 없거나 구간 끝이 실행 끝보다 뒤) (None, None)
    — 일부만 겹친 구간은 길이가 달라 비교할 수 없다.
    """
    inside = [i for i, d in enumerate(dates) if window.start <= d <= window.end]
    if not inside or inside[0] == 0 or window.end > dates[-1]:
        return None, None
    first, last = inside[0], inside[-1]
    base = equity[first - 1]
    segment = np.asarray([base, *equity[first : last + 1]], dtype=float)
    drawdown = segment / np.maximum.accumulate(segment) - 1.0
    return (equity[last] / base - 1.0) * 100.0, float(drawdown.min()) * 100.0


def annual_turnover(state_log_df: pd.DataFrame, equity_df: pd.DataFrame) -> float:
    """연 회전율 = Σ(체결 주수 × 체결가, 매수 · 매도 모두) ÷ 평균 자본 ÷ 연수.

    상태 로그 그대로라 매매법 장부 단위(종목 상계 전)이고, 체결가는 매도가 비용을 뺀 값 · 매수가 시가다 (D48 ⑪).
    """
    traded = 0.0
    for shares_col in [c for c in state_log_df.columns if c.endswith(_EXEC_SHARES_SUFFIX)]:
        price_col = f"{shares_col.removesuffix(_EXEC_SHARES_SUFFIX)}{_EXEC_PRICE_SUFFIX}"
        traded += float((state_log_df[shares_col] * state_log_df[price_col]).sum())
    first = _to_date(equity_df[COL_DATE].iloc[0])
    last = _to_date(equity_df[COL_DATE].iloc[-1])
    years = (last - first).days / ANNUAL_DAYS
    if years <= 0:
        raise ValueError(f"실행 기간이 0 이하라 회전율을 계산할 수 없습니다: {first} ~ {last}")
    return traded / float(equity_df[COL_EQUITY].mean()) / years


def summarize_run(result: PortfolioResult) -> RunSummary:
    """엔진 결과에서 판정 · 표에 쓰는 지표를 뽑는다. CAGR · MDD · Calmar 는 엔진 요약의 반올림 전 값 그대로."""
    dates = [_to_date(d) for d in result.equity_df[COL_DATE]]
    equity = [float(v) for v in result.equity_df[COL_EQUITY]]
    phases = {window.phase_id: phase_metrics(dates, equity, window) for window in PHASE_WINDOWS}
    return RunSummary(
        start_date=dates[0],
        end_date=dates[-1],
        trading_days=len(dates),
        cagr=float(str(result.summary["cagr"])),
        mdd=float(str(result.summary["mdd"])),
        calmar=float(str(result.summary["calmar"])),
        sell_trades=len(result.trades_df),
        annual_turnover=annual_turnover(result.state_log_df, result.equity_df),
        phase_returns={phase_id: values[0] for phase_id, values in phases.items()},
        phase_mdds={phase_id: values[1] for phase_id, values in phases.items()},
    )


# ============================================================================
# 신호 일치율 (D23 관문 ②, D48 ①)
# ============================================================================


def extract_decision_targets(state_log_df: pd.DataFrame, method_id: str) -> pd.DataFrame:
    """배분 규칙 매매법의 월말 판단 직후 목표 비중표 (행 = 월 마지막 거래일 다음 거래일, 열 = 자산 id).

    상태 로그의 목표 비중은 그날 체결이 맞추려던 목표라, 판단일 다음 거래일 행이 곧 그 달의 판단이다.
    날마다 비교하지 않는 이유: 월 1회 판단이 한 달 내내 같은 값으로 세져 일치율이 부풀려진다.

    Raises:
        ValueError: 상태 로그에 그 매매법의 목표 비중 열이 없을 때
    """
    prefix = f"{method_id}{POSITION_KEY_SEPARATOR}"
    cols = [c for c in state_log_df.columns if c.startswith(prefix) and c.endswith(_TARGET_WEIGHT_SUFFIX)]
    if not cols:
        raise ValueError(f"상태 로그에 매매법 {method_id!r} 의 목표 비중 열이 없습니다 — 배분 규칙 매매법인지 확인하세요")
    after_month_end = state_log_df[_COL_IS_MONTH_END].shift(1, fill_value=False).astype(bool).to_numpy()
    targets = state_log_df.loc[after_month_end, [COL_DATE, *cols]].set_index(COL_DATE)
    targets.columns = [c.removeprefix(prefix).removesuffix(_TARGET_WEIGHT_SUFFIX) for c in cols]
    return targets


def decision_agreement(targets_a: pd.DataFrame, targets_b: pd.DataFrame) -> tuple[float, int]:
    """(신호 일치율, 비교 달 수) — 한 달의 모든 자산 목표 비중이 같아야 일치로 센다.

    Raises:
        ValueError: 두 표의 판단 달 · 자산이 다르거나 비교할 달이 없을 때 (같은 시작일 실행끼리만 비교한다)
    """
    if list(targets_a.index) != list(targets_b.index):
        raise ValueError("두 판단 비중표의 판단 달이 다릅니다 — 같은 시작일의 실행끼리만 비교할 수 있습니다")
    if set(targets_a.columns) != set(targets_b.columns):
        raise ValueError(f"두 판단 비중표의 자산이 다릅니다: {list(targets_a.columns)} vs {list(targets_b.columns)}")
    if targets_a.empty:
        raise ValueError("비교할 판단 달이 없습니다")
    diff = targets_a.to_numpy(dtype=float) - targets_b[list(targets_a.columns)].to_numpy(dtype=float)
    same_month = (np.abs(diff) <= _WEIGHT_TOLERANCE).all(axis=1)
    return float(same_month.mean()), len(targets_a)


# ============================================================================
# 실행 (병렬 워커)
# ============================================================================


@dataclass(frozen=True, eq=False)
class GridCaseResult:
    """실행 하나의 결과. 결과 전체(상태 로그 수 MB) 대신 요약 · 위반 · 판단 비중표만 넘긴다.

    decision_targets 는 대용을 쓰는 후보(HAA · 로테이션)만 있다.
    """

    case: GridCase
    summary: RunSummary
    violations: list[str]
    decision_targets: pd.DataFrame | None


def run_grid_case(case: GridCase, q2_2xs_slots: tuple[AssetSlotConfig, ...]) -> GridCaseResult:
    """실행 → 시작일 확인 → 정합성 검사 → 요약 (병렬 워커, 모듈 최상위라 pickle 가능).

    Raises:
        ValueError: 실제 시작일이 묶음 시작일과 다를 때 — 엔진의 start_date 는 하한이라 데이터가 늦게 시작하는
            구성은 조용히 늦게 시작해 같은 기간 비교가 깨진다
    """
    config = build_experiment_config(q2_2xs_slots, case.candidate, case.w_pct, case.variant, case.start_date)
    result = run_portfolio_backtest(config, start_date=case.start_date)
    actual_start = _to_date(result.equity_df[COL_DATE].iloc[0])
    if actual_start != case.start_date:
        raise ValueError(
            f"[{config.experiment_name}] 실제 시작일 {actual_start} 가 묶음 시작일 {case.start_date} 와 다릅니다 — "
            f"이 구성의 데이터가 늦게 시작해 같은 기간 비교가 깨집니다. 묶음 시작일을 다시 재세요"
        )
    violations = validate_portfolio_result(result)
    targets = (
        extract_decision_targets(result.state_log_df, case.candidate) if case.candidate in PROXY_CANDIDATES else None
    )
    return GridCaseResult(case, summarize_run(result), violations, targets)


# ============================================================================
# 기준선 대비 우위 · 판정 (D24 · D47)
# ============================================================================


def compute_advantages(results: Sequence[GridCaseResult]) -> dict[GridCase, float]:
    """후보 실행마다 Calmar 우위 = 후보 Calmar − 같은 시작일 · 같은 w 의 기준선 Calmar (반올림 전).

    후보와 기준선의 실제 기간(시작 · 끝 · 거래일 수)이 같아야 한다 — 엔진은 실험마다 모든 시세의 공통 거래일만 쓰므로,
    한 시세가 일찍 끝나거나 중간 날짜가 빠지면 같은 시작일이어도 다른 기간의 Calmar 를 빼게 된다.

    Raises:
        ValueError: 같은 시작일 · 같은 w 의 기준선이 없거나 둘 이상일 때, 후보와 기준선의 실제 기간이 다를 때
    """
    baselines: dict[tuple[date, int], RunSummary] = {}
    for r in results:
        if r.case.candidate != CANDIDATE_BASELINE:
            continue
        key = (r.case.start_date, r.case.w_pct)
        if key in baselines:
            raise ValueError(f"같은 시작일 · 같은 w 의 기준선이 둘 이상입니다: {key}")
        baselines[key] = r.summary

    advantages: dict[GridCase, float] = {}
    for r in results:
        if r.case.candidate not in SUPPLEMENT_CANDIDATES:
            continue
        key = (r.case.start_date, r.case.w_pct)
        if key not in baselines:
            raise ValueError(f"기준선이 없는 후보 실행입니다: {r.case} — 같은 시작일 · 같은 w 의 기준선을 함께 돌리세요")
        baseline = baselines[key]
        period = (r.summary.start_date, r.summary.end_date, r.summary.trading_days)
        baseline_period = (baseline.start_date, baseline.end_date, baseline.trading_days)
        if period != baseline_period:
            raise ValueError(
                f"후보와 기준선의 실제 기간이 다릅니다: {r.case} 의 (시작, 끝, 거래일 수) {period} vs 기준선 {baseline_period} — "
                f"후보 시세 중 일찍 끝나거나 날짜가 빠진 파일이 있는지 확인하세요"
            )
        advantages[r.case] = r.summary.calmar - baseline.calmar
    return advantages


def _require_all_w(values: Mapping[int, object]) -> None:
    if set(values) != set(W_PCTS):
        raise ValueError(f"w 7단계가 모두 있어야 합니다: {sorted(values)} (필요: {list(W_PCTS)})")


def find_plateaus(above: Mapping[int, bool]) -> tuple[tuple[int, int], ...]:
    """기준선보다 높은 w 가 연속 MIN_PLATEAU_STEPS 단계 이상인 구간들 ((시작 w, 끝 w), w 오름차순)."""
    _require_all_w(above)
    plateaus: list[tuple[int, int]] = []
    run: list[int] = []
    for w in (*W_PCTS, None):
        if w is not None and above[w]:
            run.append(w)
            continue
        if len(run) >= MIN_PLATEAU_STEPS:
            plateaus.append((run[0], run[-1]))
        run = []
    return tuple(plateaus)


@dataclass(frozen=True)
class Judgment:
    """후보 하나의 판정. counted_above[w] = 판정에 센 「기준선보다 높다」."""

    passed: bool
    plateaus: tuple[tuple[int, int], ...]
    counted_above: Mapping[int, bool]


def judge(main_adv: Mapping[int, float] | None, sub_adv: Mapping[int, float]) -> Judgment:
    """D24 판정 (D47 해석) — 같은 w 에서 두 기간 모두 기준선보다 Calmar 가 높은 w 가 3단계 이상 연달아 있으면 통과.

    「높다」는 엄격한 `>` 다 (기준선과 같으면 높지 않다). main_adv 가 None 이면 보조 기간만으로 판정한다
    (대용이 탈락한 후보, D23).
    """
    _require_all_w(sub_adv)
    if main_adv is not None:
        _require_all_w(main_adv)
    above = {w: sub_adv[w] > 0 and (main_adv is None or main_adv[w] > 0) for w in W_PCTS}
    plateaus = find_plateaus(above)
    return Judgment(passed=bool(plateaus), plateaus=plateaus, counted_above=above)


@dataclass(frozen=True)
class GateAgreement:
    """판정 일치 (D41) — w 별 「기준선보다 높은가」가 대용판 · 실물판에서 같은가."""

    sign_match: Mapping[int, bool]
    match_count: int
    proxy_plateaus: tuple[tuple[int, int], ...]
    real_plateaus: tuple[tuple[int, int], ...]
    plateau_verdict_match: bool  # 고원(연속 3단계) 유무가 같은가


def gate_agreement(proxy_adv: Mapping[int, float], real_adv: Mapping[int, float]) -> GateAgreement:
    """대용판 · 실물판 우위로 판정 일치를 잰다."""
    _require_all_w(proxy_adv)
    _require_all_w(real_adv)
    sign_match = {w: (proxy_adv[w] > 0) == (real_adv[w] > 0) for w in W_PCTS}
    proxy_plateaus = find_plateaus({w: proxy_adv[w] > 0 for w in W_PCTS})
    real_plateaus = find_plateaus({w: real_adv[w] > 0 for w in W_PCTS})
    return GateAgreement(
        sign_match=sign_match,
        match_count=sum(sign_match.values()),
        proxy_plateaus=proxy_plateaus,
        real_plateaus=real_plateaus,
        plateau_verdict_match=bool(proxy_plateaus) == bool(real_plateaus),
    )


# ============================================================================
# 모으기 — 어느 실행을 어느 실행과 비교하는가
# ============================================================================


@dataclass(frozen=True)
class JudgmentRow:
    """판정 표 한 행 (후보 × 판정 기준 × w). 통과 · 고원은 후보 × 판정 기준 단위 값을 행마다 싣는다.

    main_advantage 는 보조 기간만으로 판정하는 기준이면 None (판정에 쓰지 않는다).
    boundary 는 판정에 쓴 우위 중 하나라도 |우위| < ADVANTAGE_BOUNDARY 인가.
    """

    candidate: str
    basis: str
    w_pct: int
    main_advantage: float | None
    sub_advantage: float
    counted_above: bool
    boundary: bool
    passed: bool
    plateaus: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class GateRow:
    """대용 검증 표 한 행 (관문 × w). 부호 일치 수 · 고원 · 고원 판정 일치는 관문 단위 값을 행마다 싣는다."""

    gate: str
    start_date: date
    w_pct: int
    proxy_calmar: float
    real_calmar: float
    proxy_advantage: float
    real_advantage: float
    sign_match: bool
    boundary: bool
    signal_agreement: float
    signal_months: int
    signal_pass: bool
    match_count: int
    proxy_plateaus: tuple[tuple[int, int], ...]
    real_plateaus: tuple[tuple[int, int], ...]
    plateau_verdict_match: bool


@dataclass(frozen=True)
class _GateSpec:
    gate: str
    candidate: str
    proxy: tuple[str, str]  # (묶음, 판)
    real: tuple[str, str]


_GATE_SPECS: Final[tuple[_GateSpec, ...]] = (
    _GateSpec(GATE_ROTATION, CANDIDATE_ROTATION, (GROUP_GATE_ROTATION, VARIANT_PURE), (GROUP_SUB, VARIANT_REAL)),
    _GateSpec(GATE_HAA_BUNDLE, CANDIDATE_HAA, (GROUP_GATE_HAA, VARIANT_PURE), (GROUP_GATE_HAA, VARIANT_GATE_REAL)),
    _GateSpec(GATE_HAA_PAIR_VEA, CANDIDATE_HAA, (GROUP_PAIR_VEA, VARIANT_PURE), (GROUP_PAIR_VEA, VARIANT_PAIR_VEA)),
    _GateSpec(GATE_HAA_PAIR_BIL, CANDIDATE_HAA, (GROUP_PAIR_BIL, VARIANT_PURE), (GROUP_PAIR_BIL, VARIANT_PAIR_BIL)),
    _GateSpec(GATE_HAA_PAIR_PDBC, CANDIDATE_HAA, (GROUP_GATE_HAA, VARIANT_PURE), (GROUP_PAIR_PDBC, VARIANT_PAIR_PDBC)),
)


def _index_results(results: Sequence[GridCaseResult]) -> dict[tuple[str, str, str, int], GridCaseResult]:
    return {(r.case.group, r.case.candidate, r.case.variant, r.case.w_pct): r for r in results}


def _lookup(
    index: Mapping[tuple[str, str, str, int], GridCaseResult], group: str, candidate: str, variant: str, w_pct: int
) -> GridCaseResult:
    key = (group, candidate, variant, w_pct)
    if key not in index:
        raise ValueError(f"실행 결과가 없습니다: {key} — build_grid_cases 의 실행 목록을 모두 돌렸는지 확인하세요")
    return index[key]


def collect_judgments(results: Sequence[GridCaseResult]) -> list[JudgmentRow]:
    """후보별 판정 행. 대용을 쓰는 후보는 두 판정 기준(주 비교 + 보조 / 보조만)을 모두 낸다 —
    그리드는 대용 탈락 여부(사용자 판단)보다 먼저 돌기 때문이다 (D48 ⑤)."""
    advantages = compute_advantages(results)
    index = _index_results(results)
    rows: list[JudgmentRow] = []
    for candidate in SUPPLEMENT_CANDIDATES:
        main = {w: advantages[_lookup(index, GROUP_MAIN, candidate, VARIANT_SPLICED, w).case] for w in W_PCTS}
        sub = {w: advantages[_lookup(index, GROUP_SUB, candidate, VARIANT_REAL, w).case] for w in W_PCTS}
        bases = (BASIS_BOTH, BASIS_SUB_ONLY) if candidate in PROXY_CANDIDATES else (BASIS_BOTH,)
        for basis in bases:
            main_used = main if basis == BASIS_BOTH else None
            judgment = judge(main_used, sub)
            for w in W_PCTS:
                used = [sub[w]] if main_used is None else [main_used[w], sub[w]]
                rows.append(
                    JudgmentRow(
                        candidate=candidate,
                        basis=basis,
                        w_pct=w,
                        main_advantage=None if main_used is None else main_used[w],
                        sub_advantage=sub[w],
                        counted_above=judgment.counted_above[w],
                        boundary=any(abs(v) < ADVANTAGE_BOUNDARY for v in used),
                        passed=judgment.passed,
                        plateaus=judgment.plateaus,
                    )
                )
    return rows


def collect_gates(results: Sequence[GridCaseResult]) -> list[GateRow]:
    """대용 검증 행 — 관문 다섯(로테이션 · HAA 묶음 · HAA 쌍 셋)마다 같은 시작일의 대용판 · 실물판을 짝짓는다."""
    advantages = compute_advantages(results)
    index = _index_results(results)
    rows: list[GateRow] = []
    for spec in _GATE_SPECS:
        proxy = {w: _lookup(index, spec.proxy[0], spec.candidate, spec.proxy[1], w) for w in W_PCTS}
        real = {w: _lookup(index, spec.real[0], spec.candidate, spec.real[1], w) for w in W_PCTS}
        agreement = gate_agreement(
            {w: advantages[proxy[w].case] for w in W_PCTS}, {w: advantages[real[w].case] for w in W_PCTS}
        )
        for w in W_PCTS:
            proxy_r, real_r = proxy[w], real[w]
            if proxy_r.case.start_date != real_r.case.start_date:
                raise RuntimeError(f"내부 불변조건 위반: 관문의 대용판 · 실물판 시작일이 다르다 ({proxy_r.case} vs {real_r.case})")
            if proxy_r.decision_targets is None or real_r.decision_targets is None:
                raise RuntimeError(f"내부 불변조건 위반: 대용 후보 실행에 판단 비중표가 없다 ({proxy_r.case})")
            rate, months = decision_agreement(proxy_r.decision_targets, real_r.decision_targets)
            proxy_adv = advantages[proxy_r.case]
            real_adv = advantages[real_r.case]
            rows.append(
                GateRow(
                    gate=spec.gate,
                    start_date=proxy_r.case.start_date,
                    w_pct=w,
                    proxy_calmar=proxy_r.summary.calmar,
                    real_calmar=real_r.summary.calmar,
                    proxy_advantage=proxy_adv,
                    real_advantage=real_adv,
                    sign_match=agreement.sign_match[w],
                    boundary=min(abs(proxy_adv), abs(real_adv)) < ADVANTAGE_BOUNDARY,
                    signal_agreement=rate,
                    signal_months=months,
                    signal_pass=rate >= SIGNAL_AGREEMENT_PASS_RATE,
                    match_count=agreement.match_count,
                    proxy_plateaus=agreement.proxy_plateaus,
                    real_plateaus=agreement.real_plateaus,
                    plateau_verdict_match=agreement.plateau_verdict_match,
                )
            )
    return rows
