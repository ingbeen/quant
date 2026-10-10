"""
대체-실물 비교 계산 스크립트

대체 시세가 기준 시세(대개 실물 ETF)를 얼마나 잘 따르는지 등록 쌍마다 재어 요약 CSV 로 남긴다.
비교는 기준 첫 거래일부터 두 시세가 모두 있는 날만 쓴다 — 실물 상장 전 구간은 대조할 실물이 없어
기존 대용과 교차 확인하는 쌍을 따로 둔다. 계산은 src/qbt/utils/proxy_comparison.py 가 하고
이 스크립트는 쌍 목록 · 반올림 · 저장만 한다.

출력: storage/results/proxy_comparison/summary.csv (쌍마다 한 행) · periods.csv (쌍 × 연도 · 국면)
선행: 쌍의 시세와 대용 · 대체 생성 파일 (generate_proxy_series.py · generate_long_proxy_series.py)

실행 명령어:
    poetry run python scripts/data/generate_proxy_comparison.py
"""

import sys
from datetime import date
from pathlib import Path
from typing import Any, Final

import pandas as pd

from qbt.backtest.constants import ROUND_PERCENT, ROUND_RATIO
from qbt.backtest.supplement_experiment import PHASE_WINDOWS
from qbt.common_constants import (
    BIL_DATA_PATH,
    BIL_PROXY_DATA_PATH,
    COL_DATE,
    DBC_DATA_PATH,
    EEM_DATA_PATH,
    EFA_DATA_PATH,
    GLD_DATA_PATH,
    GOLD_FUTURES_DATA_PATH,
    IEF_DATA_PATH,
    PDBC_DATA_PATH,
    PROXY_COMPARISON_RESULTS_DIR,
    QLD_DATA_PATH,
    QLD_PROXY_DATA_PATH,
    SHY_DATA_PATH,
    SPGSCI_DATA_PATH,
    SSO_DATA_PATH,
    SSO_PROXY_DATA_PATH,
    TIP_DATA_PATH,
    TLT_DATA_PATH,
    VEA_DATA_PATH,
    VEIEX_DATA_PATH,
    VFISX_DATA_PATH,
    VFITX_DATA_PATH,
    VGSIX_DATA_PATH,
    VGTSX_DATA_PATH,
    VIPSX_DATA_PATH,
    VNQ_DATA_PATH,
    VTMGX_DATA_PATH,
    VUSTX_DATA_PATH,
    VWO_DATA_PATH,
    VXUS_DATA_PATH,
    VXUS_PROXY_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata
from qbt.utils.proxy_comparison import (
    DISPLAY_BASE,
    DISPLAY_BASE_FILE,
    DISPLAY_BEFORE,
    DISPLAY_GROUP,
    DISPLAY_PERIOD_KIND,
    DISPLAY_PROXY,
    DISPLAY_PROXY_FILE,
    DISPLAY_PROXY_FIRST_DATE,
    PERCENT_DISPLAY_COLUMNS,
    RATIO_DISPLAY_COLUMNS,
    ROLLING_WINDOW_DAYS,
    Period,
    align_closes,
    calendar_year_periods,
    pair_summary_record,
    period_summary_records,
    summarize_pair,
    summarize_periods,
)

logger = get_logger(__name__)

GROUP_LONG: Final = "대체 판 (대체 ↔ 실물)"
GROUP_SPLICED: Final = "이어 붙인 판 (기존 대용 ↔ 실물)"
GROUP_CROSS: Final = "상장 전 교차 확인 (대체 ↔ 기존 대용)"

# 묶음마다 표를 따로 둔다 — 묶음 이름은 표가 정한다.
# 「상장 전 교차 확인」으로 나가는 쌍은 CROSS_PAIRS 에만 있고, 그 표의 쌍은 자를 실물 칸을 반드시 가진다

# (대체, 기준) — 대체 판. 실물과 직접 잰다
# 원자재는 DBC 상장 전에만 S&P GSCI 를 쓰므로 그 대체를 DBC 와 잰다 (DBC → PDBC 는 이어 붙인 판 묶음)
LONG_PAIRS: Final[tuple[tuple[Path, Path], ...]] = (
    (SSO_PROXY_DATA_PATH, SSO_DATA_PATH),
    (QLD_PROXY_DATA_PATH, QLD_DATA_PATH),
    (GOLD_FUTURES_DATA_PATH, GLD_DATA_PATH),
    (VUSTX_DATA_PATH, TLT_DATA_PATH),
    (VFITX_DATA_PATH, IEF_DATA_PATH),
    (VFISX_DATA_PATH, SHY_DATA_PATH),
    (BIL_PROXY_DATA_PATH, BIL_DATA_PATH),
    (VIPSX_DATA_PATH, TIP_DATA_PATH),
    (VTMGX_DATA_PATH, VEA_DATA_PATH),
    (VEIEX_DATA_PATH, VWO_DATA_PATH),
    (VGSIX_DATA_PATH, VNQ_DATA_PATH),
    (VGTSX_DATA_PATH, VXUS_DATA_PATH),
    (SPGSCI_DATA_PATH, DBC_DATA_PATH),
)

# (기존 대용, 기준) — 이어 붙인 판. 실물과 직접 잰다
SPLICED_PAIRS: Final[tuple[tuple[Path, Path], ...]] = (
    (EFA_DATA_PATH, VEA_DATA_PATH),
    (SHY_DATA_PATH, BIL_DATA_PATH),
    (DBC_DATA_PATH, PDBC_DATA_PATH),
    (VXUS_PROXY_DATA_PATH, VXUS_DATA_PATH),
)

# (대체, 기존 대용, 비교를 그 첫 거래일 앞까지로 자를 실물) — 상장 전 교차 확인
# 실물이 없던 구간만 본다 — 실물 상장 뒤는 위 두 묶음이 실물과 직접 잰다.
# 자를 실물이 빠지면 상장 뒤 구간이 섞이므로 이 표의 쌍은 그 칸을 반드시 가진다
CROSS_PAIRS: Final[tuple[tuple[Path, Path, Path], ...]] = (
    (VTMGX_DATA_PATH, EFA_DATA_PATH, VEA_DATA_PATH),
    (VGTSX_DATA_PATH, VXUS_PROXY_DATA_PATH, VXUS_DATA_PATH),
    (VEIEX_DATA_PATH, EEM_DATA_PATH, VWO_DATA_PATH),
)

PERIOD_KIND_YEAR: Final = "연도"
PERIOD_KIND_PHASE: Final = "국면"

_CSV_ENCODING = "utf-8-sig"
_SUMMARY_FILENAME = "summary.csv"
_PERIODS_FILENAME = "periods.csv"


def _series_name(path: Path) -> str:
    return path.name.removesuffix("_max.csv")


def _round(df: pd.DataFrame) -> pd.DataFrame:
    digits = {col: ROUND_RATIO for col in RATIO_DISPLAY_COLUMNS} | {
        col: ROUND_PERCENT for col in PERCENT_DISPLAY_COLUMNS
    }
    return df.round({col: digit for col, digit in digits.items() if col in df.columns})


@cli_exception_handler
def main() -> int:
    """
    대체-실물 비교 계산.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    phases = [Period(window.display_name, window.start, window.end) for window in PHASE_WINDOWS]
    summary_rows: list[dict[str, object]] = []
    period_rows: list[dict[str, object]] = []

    # (묶음, 대체, 기준, 자를 실물 파일 이름, 비교 제한일) — 교차 확인 쌍은 실물의 첫 거래일을 여기서 반드시 읽는다
    jobs: list[tuple[str, Path, Path, str | None, date | None]] = [
        (group, proxy, base, None, None)
        for group, pairs in ((GROUP_LONG, LONG_PAIRS), (GROUP_SPLICED, SPLICED_PAIRS))
        for proxy, base in pairs
    ]
    jobs += [
        (GROUP_CROSS, proxy, base, listing.name, load_stock_data(listing)[COL_DATE].iloc[0])
        for proxy, base, listing in CROSS_PAIRS
    ]

    for group, proxy_path, base_path, _listing_name, before in jobs:
        proxy_df = load_stock_data(proxy_path)
        base_df = load_stock_data(base_path)
        aligned = align_closes(proxy_df, base_df, before=before)
        summary = summarize_pair(aligned)
        identity = {
            DISPLAY_GROUP: group,
            DISPLAY_PROXY: _series_name(proxy_path),
            DISPLAY_BASE: _series_name(base_path),
        }
        summary_rows.append(
            {
                **identity,
                DISPLAY_PROXY_FILE: proxy_path.name,
                DISPLAY_BASE_FILE: base_path.name,
                DISPLAY_PROXY_FIRST_DATE: proxy_df[COL_DATE].iloc[0],
                DISPLAY_BEFORE: before,
                **pair_summary_record(summary),
            }
        )
        for kind, periods in (
            (PERIOD_KIND_YEAR, calendar_year_periods(summary.start, summary.end)),
            (PERIOD_KIND_PHASE, phases),
        ):
            for record in period_summary_records(summarize_periods(aligned, periods)):
                period_rows.append({**identity, DISPLAY_PERIOD_KIND: kind, **record})
        logger.debug(f"비교 완료: {_series_name(proxy_path)} ↔ {_series_name(base_path)} ({summary.start} ~ {summary.end})")

    PROXY_COMPARISON_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = PROXY_COMPARISON_RESULTS_DIR / _SUMMARY_FILENAME
    periods_path = PROXY_COMPARISON_RESULTS_DIR / _PERIODS_FILENAME
    _round(pd.DataFrame(summary_rows)).to_csv(summary_path, index=False, encoding=_CSV_ENCODING)
    _round(pd.DataFrame(period_rows)).to_csv(periods_path, index=False, encoding=_CSV_ENCODING)

    metadata: dict[str, Any] = {
        "pair_count": len(jobs),
        "period_row_count": len(period_rows),
        "rolling_window_days": ROLLING_WINDOW_DAYS,
        "outputs": [str(summary_path), str(periods_path)],
        "pairs": [
            {"group": g, "proxy": p.name, "base": b.name, "before_listing_of": listing_name}
            for g, p, b, listing_name, _before in jobs
        ],
    }
    save_metadata("proxy_comparison", metadata)
    logger.debug(f"대체-실물 비교 {len(jobs)}쌍 저장: {summary_path}, {periods_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
