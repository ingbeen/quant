"""
대용 시계열 생성 스크립트

실물 ETF 상장 전 구간을 비슷하게 움직이는 다른 시세(대용)로 채운 파일을 만든다.
- 이어 붙인 판 ({TICKER}_synthetic_max.csv): 상장 전은 대용, 상장 후는 실물 행 그대로
- VXUS 순수 합성판 (VXUS_proxy_max.csv): 전 구간 EFA · EEM 매일 비율 유지 합성

선행: 대상과 대용 시세를 download_data.py 로 받아 둔다.
원본을 다시 받으면 대용 파일이 낡으므로 이 스크립트도 다시 실행한다.

실행 명령어:
    poetry run python scripts/data/generate_proxy_series.py
"""

import sys
from pathlib import Path
from typing import Any, Final

import pandas as pd

from qbt.common_constants import (
    BIL_DATA_PATH,
    BIL_SYNTHETIC_DATA_PATH,
    COL_DATE,
    DBC_DATA_PATH,
    EEM_DATA_PATH,
    EFA_DATA_PATH,
    PDBC_DATA_PATH,
    PDBC_SYNTHETIC_DATA_PATH,
    PRICE_COLUMNS,
    SHY_DATA_PATH,
    VEA_DATA_PATH,
    VEA_SYNTHETIC_DATA_PATH,
    VXUS_DATA_PATH,
    VXUS_PROXY_DATA_PATH,
    VXUS_SYNTHETIC_DATA_PATH,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.meta_manager import save_metadata
from qbt.utils.proxy_series import (
    build_daily_rebalanced_composite,
    compute_seam_scale,
    rescale_to_actual,
    splice_proxy,
)
from qbt.utils.stock_downloader import validate_stock_data

logger = get_logger(__name__)

# 1:1 대용 — (실물, 대용, 이어 붙인 판)
ONE_TO_ONE_PROXIES: Final = (
    (VEA_DATA_PATH, EFA_DATA_PATH, VEA_SYNTHETIC_DATA_PATH),
    (BIL_DATA_PATH, SHY_DATA_PATH, BIL_SYNTHETIC_DATA_PATH),
    (PDBC_DATA_PATH, DBC_DATA_PATH, PDBC_SYNTHETIC_DATA_PATH),
)

# VXUS 대용 합성 — VXUS 주간 수익률이 선진국(VEA) 약 75% · 신흥국(VWO) 약 25% 로 분해되어,
# 2007년 이전에도 있는 EFA · EEM 을 같은 비율로 섞는다
VXUS_COMPOSITE_WEIGHTS: Final = ((EFA_DATA_PATH, 0.75), (EEM_DATA_PATH, 0.25))


def _save_price_csv(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    """다운로더와 같은 순서로 저장한다: 가격 6자리 반올림 → 검증 → 저장."""
    rounded = df.copy()
    rounded[PRICE_COLUMNS] = rounded[PRICE_COLUMNS].round(6)
    validate_stock_data(rounded)
    path.parent.mkdir(parents=True, exist_ok=True)
    rounded.to_csv(path, index=False)
    logger.debug(f"저장: {path} ({len(rounded):,}행, {rounded[COL_DATE].min()} ~ {rounded[COL_DATE].max()})")
    return rounded


def _describe(
    path: Path, saved: pd.DataFrame, actual_df: pd.DataFrame, scale: float, sources: list[str]
) -> dict[str, Any]:
    return {
        "path": str(path),
        "sources": sources,
        "row_count": len(saved),
        "start_date": str(saved[COL_DATE].min()),
        "end_date": str(saved[COL_DATE].max()),
        "seam_date": str(actual_df[COL_DATE].iloc[0]),
        "seam_scale": round(scale, 6),
    }


@cli_exception_handler
def main() -> int:
    """
    대용 시계열 생성.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    outputs: list[dict[str, Any]] = []

    for actual_path, proxy_path, output_path in ONE_TO_ONE_PROXIES:
        actual_df = load_stock_data(actual_path)
        proxy_df = load_stock_data(proxy_path)
        saved = _save_price_csv(splice_proxy(proxy_df, actual_df), output_path)
        scale = compute_seam_scale(proxy_df, actual_df)
        outputs.append(_describe(output_path, saved, actual_df, scale, [proxy_path.name, actual_path.name]))

    composite = build_daily_rebalanced_composite(
        [(load_stock_data(path), weight) for path, weight in VXUS_COMPOSITE_WEIGHTS]
    )
    vxus_df = load_stock_data(VXUS_DATA_PATH)
    scale = compute_seam_scale(composite, vxus_df)
    composite_sources = [path.name for path, _ in VXUS_COMPOSITE_WEIGHTS]

    saved = _save_price_csv(splice_proxy(composite, vxus_df), VXUS_SYNTHETIC_DATA_PATH)
    outputs.append(
        _describe(VXUS_SYNTHETIC_DATA_PATH, saved, vxus_df, scale, [*composite_sources, VXUS_DATA_PATH.name])
    )

    saved = _save_price_csv(rescale_to_actual(composite, vxus_df), VXUS_PROXY_DATA_PATH)
    outputs.append(_describe(VXUS_PROXY_DATA_PATH, saved, vxus_df, scale, composite_sources))

    save_metadata(
        "proxy_series",
        {
            "vxus_composite_weights": {path.name: weight for path, weight in VXUS_COMPOSITE_WEIGHTS},
            "outputs": outputs,
        },
    )
    logger.debug(f"대용 시계열 {len(outputs)}개 생성 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
