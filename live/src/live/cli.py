"""live 도메인 CLI 엔트리포인트.

설계서 부록 A 의 명령어를 argparse subcommand 구조로 구현한다. 현재 지원:

핵심 명령어:

- ``init`` — 초기 LiveState 생성 (capital 지정)
- ``run-daily`` — 일일 실행 통합 루프 (data_fetcher → validator → daily_runner → state 저장)
- ``init-data`` — yfinance 로 6 종 티커 전체 기간 다운로드
- ``rebuild-data`` — 단일 티커 전체 재다운로드 (스플릿 대응)
- ``drift`` — 현재 drift 지표 출력

플레이스홀더 (후속 Step 에서 완성):

- ``fetch-state``, ``push-state``: Git 연동 (Step 11 GitHub Actions 에서 주로 처리)
- ``fetch-fills``: RTDB 연동 (Step 12)
- ``history``: 영구 히스토리 조회 (Step 15)
- ``notify-failure``: 수동 실패 알림 발송 (Step 13)

원칙:

- 에러 발생 시 자동 복구 / 롤백 금지. 중단 + 실패 알림 훅 호출.
- CLI 계층만 ERROR 로그 사용.
- 파일 I/O 는 ``pathlib.Path`` 기반.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from live.constants import (
    APPLIED_FILL_IDS_MAX_AGE_DAYS,
    DEFAULT_APPLIED_FILL_IDS_FILENAME,
    DEFAULT_DATA_STOCK_SUBDIR,
    DEFAULT_LIVE_STATE_DIR,
    DEFAULT_LIVE_STATE_FILENAME,
    get_live_portfolio_config,
)
from live.daily_runner import run_daily
from live.data_fetcher import (
    append_today_to_csv,
    fetch_recent_ohlc,
    load_csv,
    rebuild_full_csv,
)
from live.drift import compute_drift
from live.models import AssetMarketData, MarketBundle
from live.state import (
    cleanup_old_fill_ids,
    create_initial_state,
    load_applied_fill_ids,
    load_state,
    save_applied_fill_ids,
    save_state,
)
from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = ["main"]


# ============================================================================
# 실패 알림 훅 (Step 13 에서 실제 notifier 와 연결)
# ============================================================================


def _notify_failure(message: str) -> None:
    """실패 알림 훅. 현재는 ERROR 로그만 기록한다.

    Step 13 notifier 완성 후 ``live.notifier.send_failure_all`` 로 교체된다.
    테스트에서는 monkeypatch 로 감시 가능.
    """
    logger.error(f"실패 알림: {message}")


# ============================================================================
# 티커 추출 헬퍼
# ============================================================================


def _ticker_from_slot_signal(slot: AssetSlotConfig) -> str:
    """AssetSlotConfig.signal_data_path 에서 티커 심볼 추출 (예: ``SPY``)."""
    return slot.signal_data_path.stem.split("_", 1)[0].upper()


def _ticker_from_slot_trade(slot: AssetSlotConfig) -> str:
    """AssetSlotConfig.trade_data_path 에서 티커 심볼 추출 (예: ``SSO``)."""
    return slot.trade_data_path.stem.split("_", 1)[0].upper()


def _collect_all_tickers() -> list[str]:
    """LIVE 포트폴리오의 모든 자산 티커 (signal + trade) 를 수집."""
    config = get_live_portfolio_config()
    seen: set[str] = set()
    ordered: list[str] = []
    for slot in config.asset_slots:
        for ticker in (_ticker_from_slot_signal(slot), _ticker_from_slot_trade(slot)):
            if ticker not in seen:
                seen.add(ticker)
                ordered.append(ticker)
    return ordered


def _live_csv_path(state_dir: Path, ticker: str) -> Path:
    """live 전용 CSV 경로 (``{state_dir}/data/stock/{TICKER}.csv``)."""
    return state_dir / DEFAULT_DATA_STOCK_SUBDIR / f"{ticker}.csv"


# ============================================================================
# init
# ============================================================================


def _cmd_init(args: argparse.Namespace) -> int:
    state_dir: Path = args.state_dir
    capital: float = args.capital

    state = create_initial_state(capital)
    state_path = state_dir / DEFAULT_LIVE_STATE_FILENAME
    save_state(state, state_path)
    logger.debug(f"live_state.json 생성 완료: {state_path}")
    return 0


# ============================================================================
# run-daily
# ============================================================================


def _cmd_run_daily(args: argparse.Namespace) -> int:
    state_dir: Path = args.state_dir
    trade_date_str: str | None = args.trade_date

    # 1. 상태 로드
    state_path = state_dir / DEFAULT_LIVE_STATE_FILENAME
    applied_path = state_dir / DEFAULT_APPLIED_FILL_IDS_FILENAME
    try:
        state = load_state(state_path)
        applied_ids = load_applied_fill_ids(applied_path)
    except (FileNotFoundError, ValueError) as exc:
        _notify_failure(f"상태 파일 로드 실패: {exc}")
        raise

    # 2. trade_date 결정
    if trade_date_str:
        trade_date = date.fromisoformat(trade_date_str)
    else:
        trade_date = date.today()

    # 3. 각 자산 CSV append (data_fetcher + data_validator)
    try:
        _refresh_live_csvs(state_dir, trade_date)
    except ValueError as exc:
        _notify_failure(f"데이터 검증 실패: {exc}")
        raise

    # 4. market_bundle 준비
    try:
        bundle = _build_market_bundle(state_dir)
    except (FileNotFoundError, ValueError) as exc:
        _notify_failure(f"market_bundle 준비 실패: {exc}")
        raise

    # 5. run_daily 호출 (에러 시 상태 변경 없이 전파)
    try:
        result = run_daily(
            trade_date=trade_date,
            state=state,
            market_bundle=bundle,
            pending_fills=[],  # Step 12 에서 rtdb_gateway 연결
            applied_fill_ids=applied_ids,
        )
    except Exception as exc:
        _notify_failure(f"엔진 실행 실패: {exc}. 상태 변경 없음")
        raise

    # 6. 상태 저장 + applied_fill_ids 정리
    save_state(result.updated_state, state_path)
    cleaned_ids = cleanup_old_fill_ids(result.updated_applied_fill_ids, max_age_days=APPLIED_FILL_IDS_MAX_AGE_DAYS)
    save_applied_fill_ids(cleaned_ids, applied_path)

    logger.debug(
        f"run-daily 완료: equity={result.model_equity:,.0f}, "
        f"pending={len(result.order_intents)}, drift={result.drift_pct:.2f}%"
    )
    return 0


def _refresh_live_csvs(state_dir: Path, trade_date: date) -> None:
    """각 자산 티커에 대해 최근 OHLC 를 가져와 CSV 에 append.

    데이터 검증(OHLC 논리, 전일 종가 연속성, 거래일 누락) 은 본 함수에서 수행하지
    않고 호출자가 추가로 검증할 수도 있다. 본 함수는 수집과 append 만 담당한다.
    Step 10 에서는 기본 수집만 담당하며, 검증 호출 통합은 후속 Step 확장 포인트.
    """
    for ticker in _collect_all_tickers():
        recent = fetch_recent_ohlc(ticker, days=5)
        today_row = recent[recent["Date"] == trade_date]
        if today_row.empty:
            # 오늘 데이터가 아직 없으면 skip (휴장일 등)
            logger.debug(f"{ticker}: {trade_date} 데이터 없음 (휴장일?) — skip")
            continue
        csv_path = _live_csv_path(state_dir, ticker)
        append_today_to_csv(csv_path, today_row.head(1))


def _build_market_bundle(state_dir: Path) -> MarketBundle:
    """qbt-live-state 내부 CSV 들을 로드하여 MarketBundle 구성.

    asset_id 별 signal_df (MA 컬럼 포함) 와 trade_df 를 준비한다.
    """
    config = get_live_portfolio_config()
    bundle: MarketBundle = {}
    for slot in config.asset_slots:
        signal_ticker = _ticker_from_slot_signal(slot)
        trade_ticker = _ticker_from_slot_trade(slot)

        signal_df = load_csv(_live_csv_path(state_dir, signal_ticker))
        if signal_ticker == trade_ticker:
            trade_df = signal_df.copy()
        else:
            trade_df = load_csv(_live_csv_path(state_dir, trade_ticker))

        # MA 컬럼 계산 (ma_{window})
        signal_df = add_single_moving_average(signal_df, window=slot.ma_window, ma_type=slot.ma_type)

        bundle[slot.asset_id] = AssetMarketData(signal_df=signal_df, trade_df=trade_df)
    return bundle


# ============================================================================
# init-data / rebuild-data
# ============================================================================


def _cmd_init_data(args: argparse.Namespace) -> int:
    state_dir: Path = args.state_dir
    for ticker in _collect_all_tickers():
        csv_path = _live_csv_path(state_dir, ticker)
        rebuild_full_csv(ticker, csv_path, period="max")
        logger.debug(f"init-data: {ticker} → {csv_path}")
    return 0


def _cmd_rebuild_data(args: argparse.Namespace) -> int:
    state_dir: Path = args.state_dir
    ticker: str = args.ticker.upper()
    period: str = args.period
    csv_path = _live_csv_path(state_dir, ticker)
    rebuild_full_csv(ticker, csv_path, period=period)
    logger.debug(f"rebuild-data: {ticker} ({period}) → {csv_path}")
    return 0


# ============================================================================
# drift
# ============================================================================


def _cmd_drift(args: argparse.Namespace) -> int:
    state_dir: Path = args.state_dir
    state = load_state(state_dir / DEFAULT_LIVE_STATE_FILENAME)

    bundle = _build_market_bundle(state_dir)
    closes: dict[str, float] = {}
    for asset_id, md in bundle.items():
        closes[asset_id] = float(md.trade_df["Close"].iloc[-1])

    report = compute_drift(state, closes)
    logger.debug(
        f"drift: model={report.model_equity:,.0f}, actual={report.actual_equity:,.0f}, "
        f"{report.drift_pct:.2f}% [{report.recommendation}]"
    )
    return 0


# ============================================================================
# 플레이스홀더 명령어
# ============================================================================


def _cmd_placeholder(args: argparse.Namespace) -> int:
    command: str = args.command
    logger.error(f"'{command}' 는 후속 Step 에서 구현됩니다 (Step 11 ~ 15).")
    return 1


# ============================================================================
# argparse + dispatch
# ============================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="live.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    # 공통: --state-dir
    common_parents: list[argparse.ArgumentParser] = []

    # init
    p_init = sub.add_parser("init", help="초기 LiveState 생성")
    p_init.add_argument("--capital", type=float, required=True)
    p_init.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_init.set_defaults(func=_cmd_init)

    # run-daily
    p_run = sub.add_parser("run-daily", help="일일 실행 루프")
    p_run.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_run.add_argument("--trade-date", type=str, default=None)
    p_run.set_defaults(func=_cmd_run_daily)

    # init-data
    p_init_data = sub.add_parser("init-data", help="yfinance 전체 기간 다운로드 (6종)")
    p_init_data.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_init_data.set_defaults(func=_cmd_init_data)

    # rebuild-data
    p_rebuild = sub.add_parser("rebuild-data", help="단일 티커 재다운로드 (스플릿 대응)")
    p_rebuild.add_argument("ticker")
    p_rebuild.add_argument("--period", type=str, default="max")
    p_rebuild.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_rebuild.set_defaults(func=_cmd_rebuild_data)

    # drift
    p_drift = sub.add_parser("drift", help="현재 drift 지표 출력")
    p_drift.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_drift.set_defaults(func=_cmd_drift)

    # 플레이스홀더 명령어
    for cmd_name in ("fetch-state", "push-state", "fetch-fills", "history", "notify-failure"):
        p = sub.add_parser(cmd_name, help=f"({cmd_name}) 후속 Step 에서 구현")
        p.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
        p.set_defaults(func=_cmd_placeholder)

    _ = common_parents  # linter 방지
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. ``argv`` 가 None 이면 ``sys.argv[1:]`` 사용.

    에러 처리 정책 (설계서 11장 + live/CLAUDE.md):

    - 모든 비즈니스 예외를 ERROR 로그로 기록 후 exit code 1 반환
    - 자동 복구 / 롤백 금지 — 호출자(GitHub Actions) 가 retry 정책 결정
    - argparse 의 ``SystemExit`` 는 그대로 전파 (parsing 실패 시 표준 동작)
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception:
        logger.error("예외 발생", exc_info=True)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
