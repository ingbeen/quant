"""
장기 대체 시계열 생성 스크립트

대체 판(실물 ETF 가 없던 2000-08 이전부터 돌리는 백테스트)에 쓰는 전 구간 대체 파일을 만든다.
- SSO_proxy_max.csv · QLD_proxy_max.csv: SPY · QQQ 2배 합성 (TQQQ 비용 모델을 배율 2 로)
- BIL_proxy_max.csv: 연방기금금리로 이자를 누적한 초단기 국채 대체
- DBC_synthetic_max.csv: DBC 상장 전은 S&P GSCI 지수, 상장 후는 DBC 실물

2배 합성과 금리 누적은 가격 수준만 실물 첫 거래일 종가에 맞추고(이음매 스케일), 수익률은 합성 그대로다.
같은 펀드의 뮤추얼 클래스 · 금 선물처럼 받은 시세를 그대로 쓰는 대체는 이 스크립트가 만들지 않는다.

선행: 기초 · 실물 · 대체 시세를 download_data.py 로 받아 둔다.
원본이나 금리 파일을 다시 받으면 생성 파일이 낡으므로 이 스크립트도 다시 실행한다.

실행 명령어:
    poetry run python scripts/data/generate_long_proxy_series.py
"""

import sys
from datetime import date
from pathlib import Path
from typing import Final

import pandas as pd

from qbt.common_constants import (
    BIL_DATA_PATH,
    BIL_PROXY_DATA_PATH,
    COL_DATE,
    DBC_DATA_PATH,
    DBC_SYNTHETIC_DATA_PATH,
    PRICE_COLUMNS,
    QLD_DATA_PATH,
    QLD_PROXY_DATA_PATH,
    QQQ_DATA_PATH,
    SPGSCI_DATA_PATH,
    SPY_DATA_PATH,
    SSO_DATA_PATH,
    SSO_PROXY_DATA_PATH,
)
from qbt.tqqq.constants import (
    COL_FFR_DATE,
    DEFAULT_SOFTPLUS_A,
    DEFAULT_SOFTPLUS_B,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
)
from qbt.tqqq.data_loader import (
    build_extended_expense_dict,
    create_ffr_dict,
    load_expense_ratio_data,
    load_ffr_data,
    lookup_ffr,
)
from qbt.tqqq.simulation import build_monthly_spread_map, simulate
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.proxy_series import (
    build_rate_accrual_series,
    rescale_to_actual,
    splice_proxy,
)
from qbt.utils.stock_downloader import validate_stock_data

logger = get_logger(__name__)

LEVERAGE_2X: Final = 2.0

# 2배 합성 — (기초 자산, 실물 2배 ETF, 생성 파일)
LEVERAGED_PROXIES: Final = (
    (SPY_DATA_PATH, SSO_DATA_PATH, SSO_PROXY_DATA_PATH),
    (QQQ_DATA_PATH, QLD_DATA_PATH, QLD_PROXY_DATA_PATH),
)


def _save_price_csv(df: pd.DataFrame, path: Path) -> None:
    """다운로더와 같은 순서로 저장한다: 가격 6자리 반올림 → 검증 → 저장."""
    rounded = df.copy()
    rounded[PRICE_COLUMNS] = rounded[PRICE_COLUMNS].round(6)
    validate_stock_data(rounded)
    path.parent.mkdir(parents=True, exist_ok=True)
    rounded.to_csv(path, index=False)
    logger.debug(f"저장: {path} ({len(rounded):,}행, {rounded[COL_DATE].min()} ~ {rounded[COL_DATE].max()})")


def _month_first_day(month: str) -> date:
    """ "YYYY-MM" 월 키의 첫날."""
    return date(int(month[:4]), int(month[5:7]), 1)


@cli_exception_handler
def main() -> int:
    """
    장기 대체 시계열 생성.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    ffr_df = load_ffr_data(FFR_DATA_PATH)
    expense_df = load_expense_ratio_data(EXPENSE_RATIO_DATA_PATH)
    expense_dict = build_extended_expense_dict(expense_df)
    spread_map = build_monthly_spread_map(ffr_df, a=DEFAULT_SOFTPLUS_A, b=DEFAULT_SOFTPLUS_B)

    # 그 앞은 계산할 수 없다 — 2배 합성은 금리 · 운용보수가 둘 다 있는 첫 달부터, 금리 누적은 금리의 첫 달부터
    ffr_first_day = _month_first_day(str(ffr_df[COL_FFR_DATE].min()))
    leveraged_first_day = max(ffr_first_day, _month_first_day(min(expense_dict)))

    for underlying_path, actual_path, output_path in LEVERAGED_PROXIES:
        underlying_df = load_stock_data(underlying_path)
        underlying_df = underlying_df[underlying_df[COL_DATE] >= leveraged_first_day].reset_index(drop=True)
        simulated = simulate(
            underlying_df=underlying_df,
            leverage=LEVERAGE_2X,
            expense_df=expense_df,
            initial_price=1.0,
            ffr_df=ffr_df,
            expense_dict=expense_dict,
            funding_spread=spread_map,
        )
        _save_price_csv(rescale_to_actual(simulated, load_stock_data(actual_path)), output_path)

    # 금리 누적은 SPY 거래일을 달력으로 쓴다
    calendar = load_stock_data(SPY_DATA_PATH)
    dates = calendar.loc[calendar[COL_DATE] >= ffr_first_day, COL_DATE].tolist()
    ffr_dict = create_ffr_dict(ffr_df)
    accrued = build_rate_accrual_series(dates, [lookup_ffr(day, ffr_dict) for day in dates])
    _save_price_csv(rescale_to_actual(accrued, load_stock_data(BIL_DATA_PATH)), BIL_PROXY_DATA_PATH)

    _save_price_csv(
        splice_proxy(load_stock_data(SPGSCI_DATA_PATH), load_stock_data(DBC_DATA_PATH)), DBC_SYNTHETIC_DATA_PATH
    )

    logger.debug("장기 대체 시계열 생성 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
