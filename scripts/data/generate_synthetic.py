"""
합성 시세 생성 스크립트

실물 ETF 상장 전 구간을 채운 합성 시세({TICKER}_synthetic_max.csv)를 모두 만들고 검증 표를 남긴다.
새 시세를 받으면 download_data.py 다음에 이 스크립트 하나만 돌린다.

1. 1배 대용 합성 (대상 표 PROXY_TARGETS 와 GLD): 실물 첫 거래일 앞은 그날 종가 비율로 맞춘 대용(시가 = 그날 종가),
   그날부터는 실물 행 그대로 (qbt.utils.proxy_series.build_proxy_synthetic). GLD 의 대용은 미국 거래일에 붙인 금 사슬
   「Perth 호주달러 × 환율 → Perth 달러 → 금 선물」이다 (qbt.utils.gold_proxy). 검증 ① 대용 ↔ 실물 — 금 사슬은 이음매마다,
   비교에서 빠진 날 수와 함께
2. 레버리지 합성 (상품 표 qbt.tqqq.constants.LEVERAGED_SYNTHETIC_TARGETS — 상품마다 기초인 1배 합성): 저장한 기초 전체를
   SoftPlus 동적 스프레드 모델로 시뮬레이션하고(가산금리 상한은 1998-12 까지의 달에만), 실제 ETF 첫 거래일 앞은 합성,
   그날부터는 실제 ETF 로 잇는다 (qbt.tqqq.synthetic)
3. 레버리지 검증: ② 합성 ↔ 실물 추적, ③ 상장 전 펀드 대조, ④ 가정만 바꾼 판 (qbt.tqqq.leveraged_comparison)

검증 숫자로는 멈추지 않는다 — 멈추는 것은 이어 붙인 결과의 이음매 뒤 행이 실물과 다를 때와, 상품 표와 ④ 대상 표의
기초가 어긋날 때다. 검증 표는 저장한 뒤 콘솔에 직전 저장값과 나란히 낸다 — 연도별 · 해마다 표는 CSV 만.

출력: storage/stock/ 의 두 표가 정한 합성 파일과 GLD 합성({TICKER}_synthetic_max.csv),
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
    AUD_USD_DATA_PATH,
    COL_DATE,
    GCF_DATA_PATH,
    GLD_DATA_PATH,
    GLD_SYNTHETIC_DATA_PATH,
    NDX_DATA_PATH,
    PERTH_MINT_GOLD_DATA_PATH,
    PROXY_VALIDATION_RESULTS_DIR,
    QLD_SYNTHETIC_DATA_PATH,
    QQQ_DATA_PATH,
    QQQ_SYNTHETIC_DATA_PATH,
    ROUND_PERCENT,
    ROUND_RATIO,
    RYNVX_DATA_PATH,
    SPY_DATA_PATH,
    SPY_SYNTHETIC_DATA_PATH,
    SSO_SYNTHETIC_DATA_PATH,
    TLT_DATA_PATH,
    TLT_SYNTHETIC_DATA_PATH,
    ULPIX_DATA_PATH,
    UOPIX_DATA_PATH,
    VFINX_DATA_PATH,
    VUSTX_DATA_PATH,
)
from qbt.tqqq.constants import EXPENSE_RATIO_DATA_PATH, FFR_DATA_PATH
from qbt.tqqq.data_loader import create_ffr_dict, load_monthly_data
from qbt.tqqq.leveraged_comparison import (
    VARIANT_ADOPTED,
    AssumptionResult,
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
from qbt.utils.gold_proxy import build_gold_proxy, load_gold_proxy_sources
from qbt.utils.proxy_comparison import (
    DISPLAY_ACTUAL_CAGR,
    DISPLAY_ACTUAL_MDD,
    DISPLAY_ACTUAL_ONLY_DAYS,
    DISPLAY_CAGR_DIFF,
    DISPLAY_DAILY_CORR,
    DISPLAY_END,
    DISPLAY_MDD_DIFF,
    DISPLAY_MONTHLY_CORR,
    DISPLAY_PROXY_CAGR,
    DISPLAY_PROXY_MDD,
    DISPLAY_PROXY_ONLY_DAYS,
    DISPLAY_ROLLING_MIN,
    DISPLAY_ROLLING_MIN_DATE,
    DISPLAY_START,
    DISPLAY_TRADING_DAYS,
    PairSummary,
    align_closes,
    calendar_year_periods,
    count_unmatched_days,
    pair_summary_record,
    period_summary_records,
    round_for_display,
    summarize_pair,
    summarize_periods,
    unmatched_days_record,
)
from qbt.utils.proxy_series import build_proxy_synthetic
from qbt.utils.stock_downloader import save_stock_csv

logger = get_logger(__name__)

# 1배 대용 합성 대상 — (이름, 대용 시세, 실물 시세, 저장 경로)
PROXY_TARGETS: Final[tuple[tuple[str, Path, Path, Path], ...]] = (
    ("QQQ", NDX_DATA_PATH, QQQ_DATA_PATH, QQQ_SYNTHETIC_DATA_PATH),
    ("SPY", VFINX_DATA_PATH, SPY_DATA_PATH, SPY_SYNTHETIC_DATA_PATH),
    ("TLT", VUSTX_DATA_PATH, TLT_DATA_PATH, TLT_SYNTHETIC_DATA_PATH),
)

# 금 사슬을 붙일 미국 거래일 — 1980-01-02 부터 있는 저장소 시세는 VFINX 뿐이고, 첫날이 금 합성의 첫날 (결정 6)
US_CALENDAR_DATA_PATH: Final = VFINX_DATA_PATH

# 레버리지 ETF 상장 전 펀드의 배율 — 검증 ③
UOPIX_LEVERAGE: Final = 2.0  # ProFunds 나스닥 100 2배
ULPIX_LEVERAGE: Final = 2.0  # ProFunds S&P 500 2배
RYNVX_LEVERAGE: Final = 1.5  # Rydex S&P 500 1.5배

# 검증 ④ 대상 — (1배 기초, 구간 끝을 정하는 첫 레버리지 상품, 배당 보정 폭을 잴 1배 대상 — None 이면 보정 판 없음)
ASSUMPTION_TARGETS: Final[tuple[tuple[Path, Path, str | None], ...]] = (
    (QQQ_SYNTHETIC_DATA_PATH, UOPIX_DATA_PATH, "QQQ"),
    # VFINX 는 배당을 담음 → 보정할 것이 없음
    (SPY_SYNTHETIC_DATA_PATH, RYNVX_DATA_PATH, None),
)

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
    DISPLAY_PROXY_ONLY_DAYS,
    DISPLAY_ACTUAL_ONLY_DAYS,
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


def _save_proxy_synthetic(
    name: str, proxy_df: pd.DataFrame, actual_df: pd.DataFrame, output_path: Path, proxy_label: str
) -> None:
    synthetic_df = build_proxy_synthetic(proxy_df, actual_df)
    save_stock_csv(synthetic_df, output_path)
    logger.debug(
        f"{name}: 이음매 {actual_df[COL_DATE].iloc[0]} 앞 {len(synthetic_df) - len(actual_df):,}행을 "
        f"{proxy_label} 로 채움, 이음매 뒤 {len(actual_df):,}행은 실물과 같음"
    )


def _proxy_pair_rows(
    name: str, proxy_label: str, actual_label: str, proxy_df: pd.DataFrame, actual_df: pd.DataFrame
) -> tuple[PairSummary, dict[str, object], list[dict[str, object]]]:
    """검증 ① 한 대상 — (비교 요약, 요약 표의 행, 연도별 표의 행)."""
    aligned = align_closes(proxy_df, actual_df)
    summary = summarize_pair(aligned)
    identity = {DISPLAY_TARGET: name}
    summary_row: dict[str, object] = {
        **identity,
        DISPLAY_PROXY_FILE: proxy_label,
        DISPLAY_ACTUAL_FILE: actual_label,
        DISPLAY_PROXY_FIRST_DATE: proxy_df[COL_DATE].iloc[0],
        **pair_summary_record(summary),
        **unmatched_days_record(count_unmatched_days(proxy_df, actual_df)),
    }
    years = summarize_periods(aligned, calendar_year_periods(summary.start, summary.end))
    return summary, summary_row, [{**identity, **record} for record in period_summary_records(years)]


def _gold_pairs() -> list[tuple[str, str, str, pd.DataFrame, pd.DataFrame]]:
    """GLD 합성을 금 사슬로 만들어 저장하고, 검증 ① 에 낼 (이름, 대용 이름, 실물 이름, 대용, 실물) 을 돌려준다.

    사슬 안 이음매 둘(GC=F 앞 · 1991년 앞)은 합성 파일이 없어, 다음 고리와 견주는 이 자리가 유일한 검증이다.
    """
    perth_df, aud_usd_df = load_gold_proxy_sources(PERTH_MINT_GOLD_DATA_PATH, AUD_USD_DATA_PATH)
    futures_df = load_stock_data(GCF_DATA_PATH)
    us_dates = load_stock_data(US_CALENDAR_DATA_PATH)[COL_DATE].tolist()
    gold = build_gold_proxy(perth_df, aud_usd_df, futures_df, us_dates)
    gld_df = load_stock_data(GLD_DATA_PATH)

    perth_name, fx_name = PERTH_MINT_GOLD_DATA_PATH.name, AUD_USD_DATA_PATH.name
    chain_label = f"{perth_name} · {fx_name} · {GCF_DATA_PATH.name}"
    _save_proxy_synthetic("GLD", gold.chain, gld_df, GLD_SYNTHETIC_DATA_PATH, f"금 사슬 ({chain_label})")
    return [
        ("GLD", chain_label, GLD_DATA_PATH.name, gold.chain, gld_df),
        ("GC=F", f"{perth_name} (달러)", GCF_DATA_PATH.name, gold.perth_usd, futures_df),
        ("Perth 달러", f"{perth_name} (호주달러) × {fx_name}", f"{perth_name} (달러)", gold.aud_in_usd, gold.perth_usd),
    ]


def _generate_proxy_synthetics() -> dict[str, PairSummary]:
    """1배 대용 합성 시세를 만들고, 대용 ↔ 실물 검증 표를 저장 · 표시한다. 대상별 비교 요약을 돌려준다."""
    pairs: list[tuple[str, str, str, pd.DataFrame, pd.DataFrame]] = []
    for name, proxy_path, actual_path, output_path in PROXY_TARGETS:
        proxy_df = load_stock_data(proxy_path)
        actual_df = load_stock_data(actual_path)
        _save_proxy_synthetic(name, proxy_df, actual_df, output_path, proxy_path.name)
        pairs.append((name, proxy_path.name, actual_path.name, proxy_df, actual_df))
    pairs.extend(_gold_pairs())

    summaries: dict[str, PairSummary] = {}
    summary_rows: list[dict[str, object]] = []
    year_rows: list[dict[str, object]] = []
    for name, proxy_label, actual_label, proxy_df, actual_df in pairs:
        summary, summary_row, years = _proxy_pair_rows(name, proxy_label, actual_label, proxy_df, actual_df)
        summaries[name] = summary
        summary_rows.append(summary_row)
        year_rows.extend(years)

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
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
) -> None:
    """검증 ③ — 레버리지 ETF 상장 전 펀드와 연 수익 · 해마다 비용을 견준다.

    연 수익: UOPIX ↔ 이 저장소의 QLD 합성 파일, RYNVX ↔ VFINX 로 만든 S&P 500 1.5배 합성, ULPIX ↔ SSO 합성 파일
    — 실물 ETF(QLD · SSO) 첫날 앞 · 뒤.
    해마다 비용의 기초는 2008년 전 펀드면 VFINX · ^NDX 다 — 저장소 SPY · QQQ 는 그 시기 하루 단위로 흔들린다.
    레버리지 ETF 는 그 합성을 만든 기초다.
    """
    uopix_df = load_stock_data(UOPIX_DATA_PATH)
    ulpix_df = load_stock_data(ULPIX_DATA_PATH)
    rynvx_df = load_stock_data(RYNVX_DATA_PATH)
    vfinx_df = load_stock_data(VFINX_DATA_PATH)
    ndx_df = load_stock_data(NDX_DATA_PATH)
    qld_synthetic_df = load_stock_data(QLD_SYNTHETIC_DATA_PATH)
    sso_synthetic_df = load_stock_data(SSO_SYNTHETIC_DATA_PATH)
    qld_first = runs_by_name["QLD"].actual[COL_DATE].iloc[0]
    sso_first = runs_by_name["SSO"].actual[COL_DATE].iloc[0]

    sp500_costs = build_cost_inputs(ffr_df, expense_df, month_of(vfinx_df[COL_DATE].iloc[0]))
    sp500_x15 = simulate_leveraged(vfinx_df, RYNVX_LEVERAGE, sp500_costs)
    sp500_x2 = simulate_leveraged(vfinx_df, ULPIX_LEVERAGE, sp500_costs)
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
        ("ULPIX", ulpix_df, "SSO 합성", "SSO 실물 (합성 파일의 이음매 뒤)", sso_synthetic_df, "SSO", sso_first),
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

    ffr_dict = create_ffr_dict(ffr_df)
    cost_targets: list[tuple[str, str, float, pd.DataFrame, pd.DataFrame, pd.DataFrame]] = [
        ("RYNVX", "VFINX", RYNVX_LEVERAGE, vfinx_df, rynvx_df, sp500_x15),
        ("UOPIX", "^NDX", UOPIX_LEVERAGE, ndx_df, uopix_df, ndx_x2),
        ("ULPIX", "VFINX", ULPIX_LEVERAGE, vfinx_df, ulpix_df, sp500_x2),
    ]
    # 레버리지 ETF 는 합성을 만든 기초로 잼 → 상품 표의 기초를 바꿔도 따라감
    base_names = {output_path: name for name, _, _, output_path in PROXY_TARGETS}
    cost_targets += [
        (
            run.name,
            base_names.get(run.underlying_path, run.underlying_path.name),
            run.leverage,
            run.underlying,
            run.actual,
            run.simulated,
        )
        for run in sorted(runs_by_name.values(), key=lambda run: run.name)
    ]
    year_rows: list[dict[str, object]] = []
    for product, base, leverage, base_df, product_df, model_df in cost_targets:
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
    runs: Sequence[LeveragedRun],
    ffr_df: pd.DataFrame,
    expense_df: pd.DataFrame,
    proxy_summaries: dict[str, PairSummary],
) -> None:
    """검증 ④ — 기초마다 대조할 실물이 없는 구간(1배 합성 첫날 ~ 첫 레버리지 상품 첫날 전날)에서 가정만 바꾼 판.

    상품은 합성을 만든 기초로 묶는다. 배당 보정 폭은 ① 에서 지수의 연 수익을 실물 ETF 의 연 수익으로 맞추는 비율이다
    (배당 − ETF 보수).

    Raises:
        ValueError: 대상 표에 기초가 없는 상품이 있거나, 대상 표의 기초를 쓰는 상품이 없을 때 — 빠진 채 저장하지 않는다
    """
    target_bases = [underlying_path for underlying_path, _, _ in ASSUMPTION_TARGETS]
    uncovered = [run.name for run in runs if run.underlying_path not in target_bases]
    if uncovered:
        raise ValueError(f"검증 ④ 대상 표(ASSUMPTION_TARGETS)에 기초가 없는 레버리지 상품: {uncovered} — 그 기초를 대상 표에 더하세요")

    results: list[AssumptionResult] = []
    for underlying_path, first_product_path, dividend_target in ASSUMPTION_TARGETS:
        group = [run for run in runs if run.underlying_path == underlying_path]
        if not group:
            raise ValueError(
                f"검증 ④ 대상 표의 기초 {underlying_path} 를 쓰는 레버리지 상품이 없습니다 — " "상품 표(LEVERAGED_SYNTHETIC_TARGETS)의 기초와 맞추세요"
            )
        underlying_df = group[0].underlying
        end = load_stock_data(first_product_path)[COL_DATE].iloc[0] - timedelta(days=1)
        products = [(run.name, run.leverage) for run in group]
        dividend_gap_rate: float | None = None
        if dividend_target is not None:
            summary = proxy_summaries[dividend_target]
            dividend_gap_rate = annual_gap_rate(summary.proxy_cagr, summary.actual_cagr)
            logger.debug(f"{dividend_target} 배당 보정 폭: 연 {dividend_gap_rate * 100:.4f}% (① 지수 연 수익을 실물로 맞추는 비율)")
        results.extend(
            assumption_variants(
                underlying_df,
                ffr_df,
                expense_df,
                products,
                end=end,
                dividend_gap_rate=dividend_gap_rate,
            )
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
    _save_and_show(rows, _ASSUMPTIONS_FILENAME, digits, (DISPLAY_VARIANT, DISPLAY_PRODUCT), "가정만 바꾼 판")


def _generate_leveraged_synthetics(proxy_summaries: dict[str, PairSummary]) -> None:
    """레버리지 합성(상품 표)을 저장된 1배 합성으로 만들어 저장하고, 검증 ② ③ ④ 를 저장 · 표시한다."""
    ffr_df = load_monthly_data(FFR_DATA_PATH)
    expense_df = load_monthly_data(EXPENSE_RATIO_DATA_PATH)

    runs = save_leveraged_synthetics(ffr_df, expense_df)
    runs_by_name = {run.name: run for run in runs}

    _save_tracking(runs)
    _save_fund_comparisons(runs_by_name, ffr_df, expense_df)
    _save_assumptions(runs, ffr_df, expense_df, proxy_summaries)


@cli_exception_handler
def main() -> int:
    """
    합성 시세 생성 — 1배 대용 합성을 먼저, 레버리지 합성과 그 검증을 다음에 만든다.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    proxy_summaries = _generate_proxy_synthetics()
    _generate_leveraged_synthetics(proxy_summaries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
