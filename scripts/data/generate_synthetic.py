"""
합성 시세 생성 스크립트

실물 ETF 상장 전 구간을 채운 합성 시세({TICKER}_synthetic_max.csv)를 모두 만들고 검증 표를 남긴다.
새 시세를 받으면 download_data.py 다음에 이 스크립트 하나만 돌린다.

1. 1배 대용 합성 (QQQ ← 나스닥 100 지수): 실물 첫 거래일 앞은 그날 종가 비율로 맞춘 대용(시가 = 그날 종가),
   그날부터는 실물 행 그대로 (qbt.utils.proxy_series.build_proxy_synthetic). 검증 ① 대용 ↔ 실물
2. 레버리지 합성 (TQQQ · QLD): 저장한 QQQ 합성 전체를 SoftPlus 동적 스프레드 모델로 시뮬레이션하고(가산금리 상한은
   1998-12 까지의 달에만), 실제 ETF 첫 거래일 앞은 합성, 그날부터는 실제 ETF 로 잇는다 (qbt.tqqq.synthetic)
3. 레버리지 검증: ② 합성 ↔ 실물 추적, ③ 상장 전 펀드(UOPIX · RYNVX) 대조, ④ 가정만 바꾼 판
   (qbt.tqqq.leveraged_comparison)

검증 숫자로는 멈추지 않는다 — 멈추는 것은 이어 붙인 결과의 이음매 뒤 행이 실물과 다를 때뿐이다.
검증 표는 저장한 뒤 콘솔에 직전 저장값과 나란히 낸다 — 연도별 · 해마다 표는 CSV 만.

출력: storage/stock/QQQ_synthetic_max.csv · TQQQ_synthetic_max.csv · QLD_synthetic_max.csv,
      storage/results/proxy_validation/ 의 summary.csv · years.csv (①), tracking.csv (②),
      funds.csv · fund_years.csv (③), assumptions.csv (④)

실행 명령어:
    poetry run python scripts/data/generate_synthetic.py
"""

import sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import Final

import pandas as pd

from qbt.common_constants import (
    COL_DATE,
    NDX_DATA_PATH,
    PROXY_VALIDATION_RESULTS_DIR,
    QLD_SYNTHETIC_DATA_PATH,
    QQQ_DATA_PATH,
    QQQ_SYNTHETIC_DATA_PATH,
    ROUND_PERCENT,
    ROUND_RATIO,
    RYNVX_DATA_PATH,
    SSO_DATA_PATH,
    UOPIX_DATA_PATH,
    VFINX_DATA_PATH,
)
from qbt.tqqq.constants import (
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    LEVERAGED_SYNTHETIC_TARGETS,
)
from qbt.tqqq.data_loader import create_ffr_dict, load_monthly_data
from qbt.tqqq.leveraged_comparison import (
    VARIANT_ADOPTED,
    annual_gap_rate,
    assumption_variants,
    compare_around,
    summarize_tracking,
    yearly_costs,
)
from qbt.tqqq.synthetic import (
    LeveragedRun,
    build_cost_inputs,
    month_of,
    save_leveraged_synthetics,
    simulate_leveraged,
)
from qbt.utils import get_logger
from qbt.utils.cli_helpers import cli_exception_handler
from qbt.utils.data_loader import load_stock_data
from qbt.utils.formatting import Align, TableLogger
from qbt.utils.proxy_comparison import (
    DISPLAY_ACTUAL_CAGR,
    DISPLAY_ACTUAL_MDD,
    DISPLAY_CAGR_DIFF,
    DISPLAY_DAILY_CORR,
    DISPLAY_END,
    DISPLAY_MDD_DIFF,
    DISPLAY_MONTHLY_CORR,
    DISPLAY_PROXY_CAGR,
    DISPLAY_PROXY_MDD,
    DISPLAY_ROLLING_MIN,
    DISPLAY_ROLLING_MIN_DATE,
    DISPLAY_START,
    DISPLAY_TRADING_DAYS,
    PairSummary,
    align_closes,
    calendar_year_periods,
    pair_summary_record,
    period_summary_records,
    round_for_display,
    summarize_pair,
    summarize_periods,
)
from qbt.utils.proxy_series import build_proxy_synthetic
from qbt.utils.stock_downloader import save_stock_csv

logger = get_logger(__name__)

# 1배 대용 합성 대상 — (이름, 대용 시세, 실물 시세, 저장 경로)
PROXY_TARGETS: Final[tuple[tuple[str, Path, Path, Path], ...]] = (
    ("QQQ", NDX_DATA_PATH, QQQ_DATA_PATH, QQQ_SYNTHETIC_DATA_PATH),
)

# 레버리지 ETF 상장 전 펀드의 배율 — 검증 ③
UOPIX_LEVERAGE: Final = 2.0  # ProFunds 나스닥 100 2배
RYNVX_LEVERAGE: Final = 1.5  # Rydex S&P 500 1.5배

DISPLAY_TARGET: Final = "대상"
DISPLAY_PROXY_FILE: Final = "대용 파일"
DISPLAY_ACTUAL_FILE: Final = "실물 파일"
DISPLAY_PROXY_FIRST_DATE: Final = "대용 첫날"

# ② 추적 표
DISPLAY_PRODUCT: Final = "상품"
DISPLAY_LEVERAGE: Final = "배율"
DISPLAY_TRACK_RMSE: Final = "누적 차 RMSE(%)"
DISPLAY_TRACK_MEAN: Final = "누적 차 평균(%)"
DISPLAY_TRACK_MAX: Final = "누적 차 최대(%)"
DISPLAY_TRACK_MAX_DATE: Final = "누적 차 최대 날짜"
DISPLAY_TRACK_LAST: Final = "마지막 날 누적 차(%)"
DISPLAY_DAILY_ABS_DIFF: Final = "하루 수익률 절대차 평균(%p)"
DISPLAY_ONE_DAY_OPEN: Final = "한 날치 시가 오차(%p)"
DISPLAY_ONE_DAY_CLOSE: Final = "한 날치 종가 오차(%p)"
DISPLAY_ONE_DAY_HIGH: Final = "한 날치 고가 오차(%p)"
DISPLAY_ONE_DAY_LOW: Final = "한 날치 저가 오차(%p)"
# 누적 차는 1% 안팎이라 백분율 기본(ROUND_PERCENT)으로는 1.0243 이 1.02 가 됨 — 보고서 §49.4 와 같은 자릿수
ROUND_TRACKING_PERCENT: Final = 4
TRACKING_PERCENT_COLUMNS: Final = (
    DISPLAY_TRACK_RMSE,
    DISPLAY_TRACK_MEAN,
    DISPLAY_TRACK_MAX,
    DISPLAY_TRACK_LAST,
    DISPLAY_DAILY_ABS_DIFF,
    DISPLAY_ONE_DAY_OPEN,
    DISPLAY_ONE_DAY_CLOSE,
    DISPLAY_ONE_DAY_HIGH,
    DISPLAY_ONE_DAY_LOW,
)

# ③ 펀드 대조 표
DISPLAY_FUND: Final = "펀드"
DISPLAY_COMPARED: Final = "견준 시세"
DISPLAY_SEGMENT: Final = "구간"
DISPLAY_COMPARED_CAGR: Final = "견준 시세 CAGR(%)"
DISPLAY_FUND_CAGR: Final = "펀드 CAGR(%)"
DISPLAY_COMPARED_MDD: Final = "견준 시세 MDD(%)"
DISPLAY_FUND_MDD: Final = "펀드 MDD(%)"
DISPLAY_BASE: Final = "기초"
DISPLAY_YEAR: Final = "연도"
DISPLAY_MEAN_FFR: Final = "평균 금리(%)"
DISPLAY_ACTUAL_COST: Final = "실제 비용(%)"
DISPLAY_MODEL_COST: Final = "모형 비용(%)"
DISPLAY_COST_DIFF: Final = "비용 차(%p)"

# ④ 가정 판 표
DISPLAY_VARIANT: Final = "판"
DISPLAY_CAGR: Final = "CAGR(%)"
DISPLAY_MDD: Final = "MDD(%)"
DISPLAY_VARIANT_CAGR_DIFF: Final = "채택 대비 CAGR 차(%p)"
DISPLAY_VARIANT_MDD_DIFF: Final = "채택 대비 MDD 차(%p)"

# 콘솔에 직전 저장값과 나란히 낼 ① 요약 열
CONSOLE_SUMMARY_COLUMNS: Final = (
    DISPLAY_START,
    DISPLAY_END,
    DISPLAY_TRADING_DAYS,
    DISPLAY_DAILY_CORR,
    DISPLAY_MONTHLY_CORR,
    DISPLAY_PROXY_CAGR,
    DISPLAY_ACTUAL_CAGR,
    DISPLAY_CAGR_DIFF,
    DISPLAY_PROXY_MDD,
    DISPLAY_ACTUAL_MDD,
    DISPLAY_MDD_DIFF,
    DISPLAY_ROLLING_MIN,
    DISPLAY_ROLLING_MIN_DATE,
)

_CSV_ENCODING = "utf-8-sig"
_SUMMARY_FILENAME = "summary.csv"
_YEARS_FILENAME = "years.csv"
_TRACKING_FILENAME = "tracking.csv"
_FUNDS_FILENAME = "funds.csv"
_FUND_YEARS_FILENAME = "fund_years.csv"
_ASSUMPTIONS_FILENAME = "assumptions.csv"
_NO_PREVIOUS = "없음"
_KEY_JOINER = " · "


def _read_table_as_text(path: Path, key_columns: Sequence[str]) -> dict[str, dict[str, str]]:
    """검증 CSV 를 행 키별 {열: 저장된 글자} 로 읽는다. 파일이 없거나 키 열이 없으면(표 모양이 바뀜) 빈 딕셔너리."""
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=_CSV_ENCODING)
    missing = [col for col in key_columns if col not in df.columns]
    if missing:
        logger.warning(f"직전 표 {path} 에 키 열 {missing} 이 없어 직전 값 없이 표시합니다 — 표 모양이 바뀌었습니다")
        return {}
    return {
        _KEY_JOINER.join(str(row[col]) for col in key_columns): {str(k): str(v) for k, v in row.items()}
        for _, row in df.iterrows()
    }


def _print_against_previous(
    previous: dict[str, dict[str, str]],
    current: dict[str, dict[str, str]],
    columns: Sequence[str],
    title: str,
) -> None:
    """행마다 열을 「직전 저장값 · 이번」으로 나란히 낸다 — 합격선은 두지 않는다."""
    table_columns = [
        ("지표", 30, Align.LEFT),
        ("직전", 14, Align.RIGHT),
        ("이번", 14, Align.RIGHT),
        ("변화", 8, Align.RIGHT),
    ]
    table = TableLogger(table_columns, logger)
    for key, now in current.items():
        before = previous.get(key, {})
        rows: list[list[str]] = []
        for col in columns:
            old = before.get(col, _NO_PREVIOUS)
            new = now.get(col, "")
            change = "-" if old == _NO_PREVIOUS else ("같음" if old == new else "바뀜")
            rows.append([col, old, new, change])
        table.print_table(rows, title=f"[{key}] {title} — 직전 저장값과 이번")


def _save_and_show(
    rows: list[dict[str, object]],
    filename: str,
    digits: dict[str, int],
    key_columns: Sequence[str],
    title: str,
) -> None:
    """검증 표를 반올림해 저장하고, 키 열 밖의 열을 직전 저장값과 나란히 낸다."""
    path = PROXY_VALIDATION_RESULTS_DIR / filename
    previous = _read_table_as_text(path, key_columns)
    df = pd.DataFrame(rows)
    df.round(digits).to_csv(path, index=False, encoding=_CSV_ENCODING)
    logger.debug(f"검증 표 저장: {path} ({len(df)}행)")
    # 저장한 파일을 다시 읽어 견줌 — 직전 값과 같은 글자로 비교
    columns = [col for col in df.columns if col not in key_columns]
    _print_against_previous(previous, _read_table_as_text(path, key_columns), columns, title)


def _generate_proxy_synthetics() -> dict[str, PairSummary]:
    """1배 대용 합성 시세를 만들고, 대용 ↔ 실물 검증 표를 저장 · 표시한다. 대상별 비교 요약을 돌려준다."""
    summaries: dict[str, PairSummary] = {}
    summary_rows: list[dict[str, object]] = []
    year_rows: list[dict[str, object]] = []
    for name, proxy_path, actual_path, output_path in PROXY_TARGETS:
        proxy_df = load_stock_data(proxy_path)
        actual_df = load_stock_data(actual_path)

        synthetic_df = build_proxy_synthetic(proxy_df, actual_df)
        save_stock_csv(synthetic_df, output_path)
        logger.debug(
            f"{name}: 이음매 {actual_df[COL_DATE].iloc[0]} 앞 {len(synthetic_df) - len(actual_df):,}행을 "
            f"{proxy_path.name} 로 채움, 이음매 뒤 {len(actual_df):,}행은 실물과 같음"
        )

        aligned = align_closes(proxy_df, actual_df)
        summary = summarize_pair(aligned)
        summaries[name] = summary
        identity = {DISPLAY_TARGET: name}
        summary_rows.append(
            {
                **identity,
                DISPLAY_PROXY_FILE: proxy_path.name,
                DISPLAY_ACTUAL_FILE: actual_path.name,
                DISPLAY_PROXY_FIRST_DATE: proxy_df[COL_DATE].iloc[0],
                **pair_summary_record(summary),
            }
        )
        years = summarize_periods(aligned, calendar_year_periods(summary.start, summary.end))
        year_rows.extend({**identity, **record} for record in period_summary_records(years))

    summary_path = PROXY_VALIDATION_RESULTS_DIR / _SUMMARY_FILENAME
    years_path = PROXY_VALIDATION_RESULTS_DIR / _YEARS_FILENAME
    previous = _read_table_as_text(summary_path, (DISPLAY_TARGET,))

    PROXY_VALIDATION_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    round_for_display(pd.DataFrame(summary_rows)).to_csv(summary_path, index=False, encoding=_CSV_ENCODING)
    round_for_display(pd.DataFrame(year_rows)).to_csv(years_path, index=False, encoding=_CSV_ENCODING)
    logger.debug(f"대용 ↔ 실물 검증 저장: {summary_path}, {years_path}")

    # 저장한 파일을 다시 읽어 견줌 — 직전 값과 같은 글자로 비교
    current = _read_table_as_text(summary_path, (DISPLAY_TARGET,))
    _print_against_previous(previous, current, CONSOLE_SUMMARY_COLUMNS, "대용 ↔ 실물 검증")
    return summaries


def _save_tracking(runs: Sequence[LeveragedRun]) -> None:
    """검증 ② — 상품마다 이어 붙이기 전 시뮬레이션과 실물의 추적 오차."""
    rows: list[dict[str, object]] = []
    for run in runs:
        tracking = summarize_tracking(run.simulated, run.actual)
        rows.append(
            {
                DISPLAY_PRODUCT: run.name,
                DISPLAY_LEVERAGE: run.leverage,
                DISPLAY_START: tracking.start,
                DISPLAY_END: tracking.end,
                DISPLAY_TRADING_DAYS: tracking.trading_days,
                DISPLAY_TRACK_RMSE: tracking.rmse,
                DISPLAY_TRACK_MEAN: tracking.mean,
                DISPLAY_TRACK_MAX: tracking.max,
                DISPLAY_TRACK_MAX_DATE: tracking.max_date,
                DISPLAY_TRACK_LAST: tracking.last,
                DISPLAY_DAILY_ABS_DIFF: tracking.daily_abs_diff_mean,
                DISPLAY_ONE_DAY_OPEN: tracking.one_day_open,
                DISPLAY_ONE_DAY_CLOSE: tracking.one_day_close,
                DISPLAY_ONE_DAY_HIGH: tracking.one_day_high,
                DISPLAY_ONE_DAY_LOW: tracking.one_day_low,
            }
        )
    digits = {col: ROUND_TRACKING_PERCENT for col in TRACKING_PERCENT_COLUMNS}
    _save_and_show(rows, _TRACKING_FILENAME, digits, (DISPLAY_PRODUCT,), "합성 ↔ 실물 추적")


def _fund_return_record(fund: str, compared: str, segment: str, summary: PairSummary) -> dict[str, object]:
    return {
        DISPLAY_FUND: fund,
        DISPLAY_SEGMENT: segment,
        DISPLAY_COMPARED: compared,
        DISPLAY_START: summary.start,
        DISPLAY_END: summary.end,
        DISPLAY_TRADING_DAYS: summary.trading_days,
        DISPLAY_DAILY_CORR: summary.daily_corr,
        DISPLAY_COMPARED_CAGR: summary.proxy_cagr,
        DISPLAY_FUND_CAGR: summary.actual_cagr,
        DISPLAY_CAGR_DIFF: summary.cagr_diff,
        DISPLAY_COMPARED_MDD: summary.proxy_mdd,
        DISPLAY_FUND_MDD: summary.actual_mdd,
    }


def _save_fund_comparisons(
    runs_by_name: dict[str, LeveragedRun],
    qqq_synthetic_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    uopix_df: pd.DataFrame,
) -> None:
    """검증 ③ — 레버리지 ETF 상장 전 펀드와 연 수익 · 해마다 비용을 견준다.

    연 수익: UOPIX ↔ 이 저장소의 QLD 합성 파일, RYNVX ↔ VFINX 로 만든 S&P 500 1.5배 합성 — 실물 ETF(QLD · SSO) 첫날 앞 · 뒤.
    해마다 비용의 기초는 2008년 전 펀드면 VFINX · ^NDX 다 — 저장소 SPY · QQQ 는 그 시기 하루 단위로 흔들린다.
    """
    rynvx_df = load_stock_data(RYNVX_DATA_PATH)
    vfinx_df = load_stock_data(VFINX_DATA_PATH)
    ndx_df = load_stock_data(NDX_DATA_PATH)
    qld_synthetic_df = load_stock_data(QLD_SYNTHETIC_DATA_PATH)
    qld_first = runs_by_name["QLD"].actual[COL_DATE].iloc[0]
    sso_first = load_stock_data(SSO_DATA_PATH)[COL_DATE].iloc[0]

    sp500_costs = build_cost_inputs(ffr_df, expense_df, month_of(vfinx_df[COL_DATE].iloc[0]))
    sp500_x15 = simulate_leveraged(vfinx_df, RYNVX_LEVERAGE, sp500_costs)
    ndx_costs = build_cost_inputs(ffr_df, expense_df, month_of(ndx_df[COL_DATE].iloc[0]))
    ndx_x2 = simulate_leveraged(ndx_df, UOPIX_LEVERAGE, ndx_costs)

    # 견준 시세 이름은 구간마다 — QLD 합성 파일의 상장 뒤 행은 실물 QLD 라 그 행은 실물 ETF ↔ 펀드의 기준선
    return_rows: list[dict[str, object]] = []
    for fund, fund_df, compared_before, compared_after, compared_df, etf, split in (
        ("UOPIX", uopix_df, "QLD 합성", "QLD 실물 (합성 파일의 이음매 뒤)", qld_synthetic_df, "QLD", qld_first),
        (
            "RYNVX",
            rynvx_df,
            "S&P 500 1.5배 합성 (VFINX)",
            "S&P 500 1.5배 합성 (VFINX)",
            sp500_x15,
            "SSO",
            sso_first,
        ),
    ):
        before, after = compare_around(compared_df, fund_df, split)
        return_rows.append(_fund_return_record(fund, compared_before, f"{etf} 상장 전", before))
        return_rows.append(_fund_return_record(fund, compared_after, f"{etf} 상장 뒤", after))
    return_digits = {col: ROUND_PERCENT for col in (DISPLAY_COMPARED_CAGR, DISPLAY_FUND_CAGR, DISPLAY_CAGR_DIFF)}
    return_digits |= {
        DISPLAY_COMPARED_MDD: ROUND_PERCENT,
        DISPLAY_FUND_MDD: ROUND_PERCENT,
        DISPLAY_DAILY_CORR: ROUND_RATIO,
    }
    _save_and_show(return_rows, _FUNDS_FILENAME, return_digits, (DISPLAY_FUND, DISPLAY_SEGMENT), "상장 전 펀드 대조")

    qld_run = runs_by_name["QLD"]
    tqqq_run = runs_by_name["TQQQ"]
    ffr_dict = create_ffr_dict(ffr_df)
    year_rows: list[dict[str, object]] = []
    for product, base, leverage, base_df, product_df, model_df in (
        ("RYNVX", "VFINX", RYNVX_LEVERAGE, vfinx_df, rynvx_df, sp500_x15),
        ("UOPIX", "^NDX", UOPIX_LEVERAGE, ndx_df, uopix_df, ndx_x2),
        ("QLD", "QQQ", qld_run.leverage, qqq_synthetic_df, qld_run.actual, qld_run.simulated),
        ("TQQQ", "QQQ", tqqq_run.leverage, qqq_synthetic_df, tqqq_run.actual, tqqq_run.simulated),
    ):
        for cost in yearly_costs(base_df, product_df, model_df, leverage, ffr_dict):
            year_rows.append(
                {
                    DISPLAY_PRODUCT: product,
                    DISPLAY_BASE: base,
                    DISPLAY_LEVERAGE: leverage,
                    DISPLAY_YEAR: cost.year,
                    DISPLAY_TRADING_DAYS: cost.trading_days,
                    DISPLAY_MEAN_FFR: cost.mean_ffr,
                    DISPLAY_ACTUAL_COST: cost.actual_cost,
                    DISPLAY_MODEL_COST: cost.model_cost,
                    DISPLAY_COST_DIFF: cost.actual_cost - cost.model_cost,
                }
            )
    year_digits = {
        col: ROUND_PERCENT for col in (DISPLAY_MEAN_FFR, DISPLAY_ACTUAL_COST, DISPLAY_MODEL_COST, DISPLAY_COST_DIFF)
    }
    years_path = PROXY_VALIDATION_RESULTS_DIR / _FUND_YEARS_FILENAME
    pd.DataFrame(year_rows).round(year_digits).to_csv(years_path, index=False, encoding=_CSV_ENCODING)
    logger.debug(f"해마다 비용 저장: {years_path} ({len(year_rows)}행)")


def _save_assumptions(
    qqq_synthetic_df: pd.DataFrame,
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    uopix_df: pd.DataFrame,
    qqq_summary: PairSummary,
) -> None:
    """검증 ④ — 대조할 실물이 없는 구간(합성 첫날 ~ UOPIX 첫날 전날)에서 가정만 바꾼 판.

    배당 보정 폭은 ① 에서 나스닥 100 지수의 연 수익을 실물 QQQ 의 연 수익으로 맞추는 비율이다 (배당 − QQQ 보수).
    """
    end = uopix_df[COL_DATE].iloc[0] - timedelta(days=1)
    products = [(name, leverage) for name, _, leverage, _ in LEVERAGED_SYNTHETIC_TARGETS]
    dividend_gap_rate = annual_gap_rate(qqq_summary.proxy_cagr, qqq_summary.actual_cagr)
    results = assumption_variants(
        qqq_synthetic_df,
        ffr_df,
        expense_df,
        products,
        end=end,
        dividend_gap_rate=dividend_gap_rate,
    )
    adopted = {r.product: r for r in results if r.variant == VARIANT_ADOPTED}
    rows: list[dict[str, object]] = [
        {
            DISPLAY_VARIANT: r.variant,
            DISPLAY_PRODUCT: r.product,
            DISPLAY_LEVERAGE: r.leverage,
            DISPLAY_START: r.start,
            DISPLAY_END: r.end,
            DISPLAY_CAGR: r.cagr,
            DISPLAY_MDD: r.mdd,
            DISPLAY_VARIANT_CAGR_DIFF: r.cagr - adopted[r.product].cagr,
            DISPLAY_VARIANT_MDD_DIFF: r.mdd - adopted[r.product].mdd,
        }
        for r in results
    ]
    digits = {
        col: ROUND_PERCENT for col in (DISPLAY_CAGR, DISPLAY_MDD, DISPLAY_VARIANT_CAGR_DIFF, DISPLAY_VARIANT_MDD_DIFF)
    }
    logger.debug(f"배당 보정 폭: 연 {dividend_gap_rate * 100:.4f}% (① 지수 연 수익을 실물 QQQ 로 맞추는 비율)")
    _save_and_show(rows, _ASSUMPTIONS_FILENAME, digits, (DISPLAY_VARIANT, DISPLAY_PRODUCT), "가정만 바꾼 판")


def _generate_leveraged_synthetics(qqq_summary: PairSummary) -> None:
    """레버리지 합성(TQQQ · QLD)을 저장된 QQQ 합성으로 만들어 저장하고, 검증 ② ③ ④ 를 저장 · 표시한다."""
    # 방금 저장한 파일을 다시 읽음 — 파일만으로 다시 만들 때와 같은 입력
    qqq_synthetic_df = load_stock_data(QQQ_SYNTHETIC_DATA_PATH)
    ffr_df = load_monthly_data(FFR_DATA_PATH)
    expense_df = load_monthly_data(EXPENSE_RATIO_DATA_PATH)
    first_month = month_of(qqq_synthetic_df[COL_DATE].iloc[0])
    logger.debug(f"QQQ 합성: {len(qqq_synthetic_df):,}행, 비용 입력은 {first_month} 부터")

    costs = build_cost_inputs(ffr_df, expense_df, first_month)
    runs = save_leveraged_synthetics(qqq_synthetic_df, costs)
    runs_by_name = {run.name: run for run in runs}

    uopix_df = load_stock_data(UOPIX_DATA_PATH)
    _save_tracking(runs)
    _save_fund_comparisons(runs_by_name, qqq_synthetic_df, ffr_df, expense_df, uopix_df)
    _save_assumptions(qqq_synthetic_df, ffr_df, expense_df, uopix_df, qqq_summary)


@cli_exception_handler
def main() -> int:
    """
    합성 시세 생성 — 1배 대용 합성을 먼저, 레버리지 합성과 그 검증을 다음에 만든다.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    proxy_summaries = _generate_proxy_synthetics()
    _generate_leveraged_synthetics(proxy_summaries["QQQ"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
