"""
합성 시세 생성 스크립트

실물 ETF 상장 전 구간을 채운 합성 시세({TICKER}_synthetic_max.csv)를 모두 만든다.
새 시세를 받으면 download_data.py 다음에 이 스크립트 하나만 돌린다.

1. 1배 대용 합성 (QQQ ← 나스닥 100 지수): 실물 첫 거래일 앞은 그날 종가 비율로 맞춘 대용(시가 = 그날 종가),
   그날부터는 실물 행 그대로 (qbt.utils.proxy_series.build_proxy_synthetic).
   대용 ↔ 실물 검증 표를 저장하고 콘솔에 직전 저장값과 나란히 낸다
2. 레버리지 합성 (TQQQ · QLD): QQQ 전체 기간을 SoftPlus 동적 스프레드 모델로 시뮬레이션하고,
   실제 ETF 첫 거래일 앞은 합성 구간(가격을 그날 종가 비율로 맞춤), 그날부터는 실제 ETF 로 이어 붙인다

검증 숫자로는 멈추지 않는다 — 멈추는 것은 이어 붙인 결과의 이음매 뒤 행이 실물과 다를 때뿐이다.

출력: storage/stock/QQQ_synthetic_max.csv · TQQQ_synthetic_max.csv · QLD_synthetic_max.csv,
      storage/results/proxy_validation/summary.csv (대상마다 한 행) · years.csv (대상 × 연도)

실행 명령어:
    poetry run python scripts/data/generate_synthetic.py
"""

import sys
from pathlib import Path
from typing import Final

import pandas as pd

from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    NDX_DATA_PATH,
    PROXY_VALIDATION_RESULTS_DIR,
    QQQ_DATA_PATH,
    QQQ_SYNTHETIC_DATA_PATH,
)
from qbt.tqqq import build_monthly_spread_map, simulate
from qbt.tqqq.constants import (
    DAILY_COMPARISON_TARGETS,
    DEFAULT_SOFTPLUS_A,
    DEFAULT_SOFTPLUS_B,
    EXPENSE_RATIO_DATA_PATH,
    FFR_DATA_PATH,
    SYNTHETIC_DATA_PATHS,
)
from qbt.tqqq.data_loader import (
    build_extended_expense_dict,
    create_ffr_dict,
    load_monthly_data,
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
    align_closes,
    calendar_year_periods,
    pair_summary_record,
    period_summary_records,
    round_for_display,
    summarize_pair,
    summarize_periods,
)
from qbt.utils.proxy_series import build_proxy_synthetic, splice_proxy
from qbt.utils.stock_downloader import save_stock_csv

logger = get_logger(__name__)

# 1배 대용 합성 대상 — (이름, 대용 시세, 실물 시세, 저장 경로)
PROXY_TARGETS: Final[tuple[tuple[str, Path, Path, Path], ...]] = (
    ("QQQ", NDX_DATA_PATH, QQQ_DATA_PATH, QQQ_SYNTHETIC_DATA_PATH),
)

DISPLAY_TARGET: Final = "대상"
DISPLAY_PROXY_FILE: Final = "대용 파일"
DISPLAY_ACTUAL_FILE: Final = "실물 파일"
DISPLAY_PROXY_FIRST_DATE: Final = "대용 첫날"

# 콘솔에 직전 저장값과 나란히 낼 요약 열
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
_NO_PREVIOUS = "없음"


def _read_summary_as_text(path: Path) -> dict[str, dict[str, str]]:
    """검증 요약 CSV 를 대상별 {열: 저장된 글자} 로 읽는다. 파일이 없으면 빈 딕셔너리."""
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding=_CSV_ENCODING)
    return {str(row[DISPLAY_TARGET]): {str(k): str(v) for k, v in row.items()} for _, row in df.iterrows()}


def _print_against_previous(previous: dict[str, dict[str, str]], current: dict[str, dict[str, str]]) -> None:
    """대상마다 요약 열을 「직전 저장값 · 이번」으로 나란히 낸다 — 합격선은 두지 않는다."""
    columns = [
        ("지표", 20, Align.LEFT),
        ("직전", 14, Align.RIGHT),
        ("이번", 14, Align.RIGHT),
        ("변화", 8, Align.RIGHT),
    ]
    table = TableLogger(columns, logger)
    for target, now in current.items():
        before = previous.get(target, {})
        rows: list[list[str]] = []
        for col in CONSOLE_SUMMARY_COLUMNS:
            old = before.get(col, _NO_PREVIOUS)
            new = now.get(col, "")
            change = "-" if old == _NO_PREVIOUS else ("같음" if old == new else "바뀜")
            rows.append([col, old, new, change])
        table.print_table(rows, title=f"[{target}] 대용 ↔ 실물 검증 — 직전 저장값과 이번")


def _generate_proxy_synthetics() -> None:
    """1배 대용 합성 시세를 만들고, 대용 ↔ 실물 검증 표를 저장 · 표시한다."""
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
    previous = _read_summary_as_text(summary_path)

    PROXY_VALIDATION_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    round_for_display(pd.DataFrame(summary_rows)).to_csv(summary_path, index=False, encoding=_CSV_ENCODING)
    round_for_display(pd.DataFrame(year_rows)).to_csv(years_path, index=False, encoding=_CSV_ENCODING)
    logger.debug(f"대용 ↔ 실물 검증 저장: {summary_path}, {years_path}")

    # 저장한 파일을 다시 읽어 견줌 — 직전 값과 같은 글자로 비교
    _print_against_previous(previous, _read_summary_as_text(summary_path))


def _generate_leveraged_synthetics() -> None:
    """합성+실제 레버리지 ETF 병합 데이터 생성."""
    logger.debug("합성+실제 레버리지 ETF 병합 데이터 생성 시작")
    logger.debug(f"파라미터: softplus(a={DEFAULT_SOFTPLUS_A}, b={DEFAULT_SOFTPLUS_B})")

    # 1. 데이터 로드: QQQ, FFR, Expense Ratio
    qqq_df = load_stock_data(QQQ_DATA_PATH)
    ffr_df = load_monthly_data(FFR_DATA_PATH)
    expense_df = load_monthly_data(EXPENSE_RATIO_DATA_PATH)

    logger.debug(f"QQQ: {len(qqq_df):,}행 ({qqq_df[COL_DATE].min()} ~ {qqq_df[COL_DATE].max()})")

    # 2. SoftPlus 스프레드 맵 생성
    spread_map = build_monthly_spread_map(ffr_df, a=DEFAULT_SOFTPLUS_A, b=DEFAULT_SOFTPLUS_B)
    logger.debug(f"SoftPlus 스프레드 맵 생성 완료: {len(spread_map)}개월")

    ffr_dict = create_ffr_dict(ffr_df)

    # 3. expense_dict 확장 (1999-01 ~ expense_df 최초월 직전까지 고정값 채우기)
    extended_expense_dict = build_extended_expense_dict(expense_df)
    logger.debug(
        f"확장된 expense_dict: {len(extended_expense_dict)}개월 "
        f"({min(extended_expense_dict.keys())} ~ {max(extended_expense_dict.keys())})"
    )

    for product_name, actual_path, leverage in DAILY_COMPARISON_TARGETS:
        actual_df = load_stock_data(actual_path)
        logger.debug(
            f"{product_name}(실제): {len(actual_df):,}행 ({actual_df[COL_DATE].min()} ~ {actual_df[COL_DATE].max()})"
        )

        # 4. simulate() 실행 (QQQ 전체 기간). 가격 수준은 이어 붙일 때 실제 ETF 첫 거래일 종가로 다시 맞추므로
        # 시작 가격은 결과에 남지 않는다
        logger.debug(f"{product_name} 시뮬레이션 실행 중... (multiplier={leverage})")
        synthetic_df = simulate(
            underlying_df=qqq_df,
            leverage=leverage,
            initial_price=1.0,
            ffr_dict=ffr_dict,
            expense_dict=extended_expense_dict,
            funding_spread=spread_map,
        )
        logger.debug(f"시뮬레이션 완료: {len(synthetic_df):,}행")

        # 5. 실제 ETF 첫 거래일 앞은 합성, 그날부터는 실제 행 그대로
        merged_df = splice_proxy(synthetic_df, actual_df)
        logger.debug(f"병합 완료: {len(merged_df):,}행 (이어 붙인 날: 실제 {product_name} 첫 거래일 {actual_df[COL_DATE].iloc[0]})")

        # 6. CSV 저장 — 다운로더의 급등락 검사는 쓰지 않는다(3배 합성은 하루 50% 를 넘는 날이 있다, 2001-01-03)
        save_stock_csv(merged_df, SYNTHETIC_DATA_PATHS[product_name], check_price_spikes=False)

        # 7. 결과 요약 출력
        initial_close = float(merged_df.iloc[0][COL_CLOSE])
        final_close = float(merged_df.iloc[-1][COL_CLOSE])
        cumulative_return_pct = (final_close / initial_close - 1) * 100

        logger.debug(f"초기 가격: {initial_close:.6f}")
        logger.debug(f"최종 가격: {final_close:.6f}")
        logger.debug(f"누적 수익률: {cumulative_return_pct:+.2f}%")


@cli_exception_handler
def main() -> int:
    """
    합성 시세 생성 — 1배 대용 합성을 먼저, 레버리지 합성을 다음에 만든다.

    Returns:
        종료 코드 (0: 성공, 1: 실패)
    """
    _generate_proxy_synthetics()
    _generate_leveraged_synthetics()
    return 0


if __name__ == "__main__":
    sys.exit(main())
