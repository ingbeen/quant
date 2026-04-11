"""live 도메인 CLI 엔트리포인트.

설계서 부록 A 의 명령어를 argparse subcommand 구조로 구현한다.

명령어:

- ``init`` — 초기 LiveState 생성 (capital 지정)
- ``run-daily`` — 일일 실행 통합 루프 (data → daily_runner → state → RTDB → 알림 → history)
- ``init-data`` — yfinance 로 6 종 티커 전체 기간 다운로드
- ``rebuild-data`` — 단일 티커 재다운로드 (스플릿 대응)
- ``drift`` — 현재 drift 지표 출력
- ``fetch-state`` — qbt-live-state 리포 git pull
- ``push-state`` — qbt-live-state 리포 git add/commit/push
- ``fetch-fills`` — RTDB 의 미처리 fill 목록 조회 출력
- ``history`` — history/summary.jsonl 의 최근 N 줄 출력
- ``notify-failure`` — 수동 실패 알림 발송 (Actions retry job 등에서 호출)

원칙:

- 에러 발생 시 자동 복구 / 롤백 금지. 즉시 중단 + 실패 알림 발송.
- CLI 계층만 ERROR 로그 사용.
- 외부 호출(RTDB / 알림) 은 ``--no-rtdb``, ``--no-notify`` 로 비활성화 가능 (테스트 / 오프라인).
- 파일 I/O 는 ``pathlib.Path`` 기반.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from live import git_state, history, notifier, rtdb_gateway
from live.chart_data import build_chart_series
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
from live.models import ActualFill, AssetMarketData, DailyResult, MarketBundle
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
# 환경변수 키
# ============================================================================

_ENV_FIREBASE_DB_URL = "FIREBASE_DB_URL"
_ENV_FIREBASE_CRED = "GOOGLE_APPLICATION_CREDENTIALS"
_ENV_TG_TOKEN = "TELEGRAM_BOT_TOKEN"
_ENV_TG_CHAT = "TELEGRAM_CHAT_ID"

_DEFAULT_FIREBASE_DB_URL = "https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app"


# ============================================================================
# 티커 헬퍼
# ============================================================================


def _ticker_from_slot_signal(slot: AssetSlotConfig) -> str:
    return slot.signal_data_path.stem.split("_", 1)[0].upper()


def _ticker_from_slot_trade(slot: AssetSlotConfig) -> str:
    return slot.trade_data_path.stem.split("_", 1)[0].upper()


def _collect_all_tickers() -> list[str]:
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
    return state_dir / DEFAULT_DATA_STOCK_SUBDIR / f"{ticker}.csv"


def _history_dir(state_dir: Path) -> Path:
    return state_dir / "history"


# ============================================================================
# RTDB / 알림 헬퍼
# ============================================================================


def _initialize_rtdb_app() -> Any | None:
    """환경변수에서 Firebase 자격증명을 읽어 App 초기화. 실패 시 ``None``."""
    cred_path_str = os.environ.get(_ENV_FIREBASE_CRED)
    if not cred_path_str:
        logger.warning(f"{_ENV_FIREBASE_CRED} 미설정 — RTDB 비활성화")
        return None
    db_url = os.environ.get(_ENV_FIREBASE_DB_URL, _DEFAULT_FIREBASE_DB_URL)
    try:
        return rtdb_gateway.initialize_firebase_app(Path(cred_path_str), db_url)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Firebase 초기화 실패: {exc}")
        return None


def _safe_notify_failure(rtdb_app: Any | None, message: str) -> None:
    """RTDB 에서 device 토큰을 읽고 실패 알림을 발송한다.

    토큰 조회나 발송이 실패해도 본 함수는 절대 raise 하지 않는다 (이미 메인 흐름이
    실패한 상태이므로 알림 자체가 실패해도 메인 예외를 가리지 않는다).
    """
    tg_token = os.environ.get(_ENV_TG_TOKEN, "")
    tg_chat = os.environ.get(_ENV_TG_CHAT, "")
    tokens: list[str] = []
    if rtdb_app is not None:
        try:
            tokens = rtdb_gateway.read_device_tokens(rtdb_app)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"실패 알림 — 토큰 조회 실패: {exc}")
    try:
        notifier.send_failure_all(tokens, tg_token, tg_chat, message)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"실패 알림 발송 자체 실패: {exc}")


def _publish_to_rtdb(
    rtdb_app: Any,
    state_dir: Path,
    state: Any,
    result: DailyResult,
) -> None:
    """RTDB 에 read model + chart_data 를 갱신하고 처리된 fill 을 마킹한다."""
    # 1. read model 갱신
    rtdb_gateway.write_read_model(rtdb_app, state, result)

    # 2. 차트 데이터 갱신
    chart_series = build_chart_series(state_dir)
    rtdb_gateway.write_chart_data(rtdb_app, chart_series)

    # 3. 처리된 fill 마킹
    processed_keys = list(result.updated_applied_fill_ids.keys())
    if processed_keys:
        rtdb_gateway.mark_fills_processed(rtdb_app, processed_keys)


def _send_daily_notifications(rtdb_app: Any | None, result: DailyResult) -> None:
    """FCM + 텔레그램 동시 발송. 만료 토큰은 RTDB 에서 정리."""
    tg_token = os.environ.get(_ENV_TG_TOKEN, "")
    tg_chat = os.environ.get(_ENV_TG_CHAT, "")

    tokens: list[str] = []
    if rtdb_app is not None:
        try:
            tokens = rtdb_gateway.read_device_tokens(rtdb_app)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"device 토큰 조회 실패: {exc}")

    outcome = notifier.send_all(tokens, tg_token, tg_chat, result)
    logger.debug(
        f"알림 발송 결과: fcm={outcome.fcm_sent_count}, "
        f"telegram={outcome.telegram_ok}, invalid_tokens={len(outcome.fcm_invalid_tokens)}"
    )

    if rtdb_app is not None and outcome.fcm_invalid_tokens:
        try:
            rtdb_gateway.remove_invalid_tokens(rtdb_app, outcome.fcm_invalid_tokens)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"만료 토큰 정리 실패: {exc}")


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
# run-daily — 통합 흐름
# ============================================================================


def _cmd_run_daily(args: argparse.Namespace) -> int:
    """설계서 4.2 일일 실행 통합 루프.

    어떤 단계든 예외 발생 시 ``_safe_notify_failure`` 호출 후 재전파.
    """
    state_dir: Path = args.state_dir
    trade_date_str: str | None = args.trade_date
    no_rtdb: bool = args.no_rtdb
    no_notify: bool = args.no_notify

    rtdb_app: Any | None = None

    try:
        # 1. 상태 로드
        state_path = state_dir / DEFAULT_LIVE_STATE_FILENAME
        applied_path = state_dir / DEFAULT_APPLIED_FILL_IDS_FILENAME
        try:
            state = load_state(state_path)
            applied_ids = load_applied_fill_ids(applied_path)
        except (FileNotFoundError, ValueError) as exc:
            raise RuntimeError(f"상태 파일 로드 실패: {exc}") from exc

        # 2. trade_date 결정
        trade_date = date.fromisoformat(trade_date_str) if trade_date_str else date.today()

        # 3. CSV append (data_fetcher)
        try:
            _refresh_live_csvs(state_dir, trade_date)
        except ValueError as exc:
            raise RuntimeError(f"데이터 검증 실패: {exc}") from exc

        # 4. market_bundle 준비
        try:
            bundle = _build_market_bundle(state_dir)
        except (FileNotFoundError, ValueError) as exc:
            raise RuntimeError(f"market_bundle 준비 실패: {exc}") from exc

        # 5. RTDB 초기화 (옵션)
        if not no_rtdb:
            rtdb_app = _initialize_rtdb_app()

        # 6. RTDB fills 가져오기
        pending_fills: list[ActualFill] = []
        if rtdb_app is not None:
            try:
                pending_fills = rtdb_gateway.fetch_unprocessed_fills(rtdb_app)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB fills 읽기 실패: {exc}") from exc

        # 7. run_daily (순수 계산)
        try:
            result = run_daily(
                trade_date=trade_date,
                state=state,
                market_bundle=bundle,
                pending_fills=pending_fills,
                applied_fill_ids=applied_ids,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"엔진 실행 실패: {exc}. 상태 변경 없음") from exc

        # 8. 상태 저장 + applied_ids 정리
        save_state(result.updated_state, state_path)
        cleaned_ids = cleanup_old_fill_ids(result.updated_applied_fill_ids, max_age_days=APPLIED_FILL_IDS_MAX_AGE_DAYS)
        save_applied_fill_ids(cleaned_ids, applied_path)

        # 9. 영구 히스토리 저장
        try:
            _persist_history(state_dir, trade_date, result)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"히스토리 저장 실패 (계속 진행): {exc}")

        # 10. RTDB 갱신 (선택)
        if rtdb_app is not None:
            try:
                _publish_to_rtdb(rtdb_app, state_dir, result.updated_state, result)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB 갱신 실패: {exc}") from exc

        # 11. 알림 발송 (옵션)
        if not no_notify:
            _send_daily_notifications(rtdb_app, result)

        logger.debug(
            f"run-daily 완료: equity={result.model_equity:,.0f}, "
            f"pending={len(result.order_intents)}, drift={result.drift_pct:.2f}%, "
            f"reminders={len(result.pending_fill_reminders)}"
        )
        return 0

    except Exception as exc:
        # 어떤 단계든 실패하면 알림 발송 후 재전파
        if not no_notify:
            _safe_notify_failure(rtdb_app, str(exc))
        raise


def _refresh_live_csvs(state_dir: Path, trade_date: date) -> None:
    """각 자산 티커에 대해 최근 OHLC 를 가져와 CSV 에 append."""
    for ticker in _collect_all_tickers():
        recent = fetch_recent_ohlc(ticker, days=5)
        today_row = recent[recent["Date"] == trade_date]
        if today_row.empty:
            logger.debug(f"{ticker}: {trade_date} 데이터 없음 (휴장일?) — skip")
            continue
        csv_path = _live_csv_path(state_dir, ticker)
        append_today_to_csv(csv_path, today_row.head(1))


def _build_market_bundle(state_dir: Path) -> MarketBundle:
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

        signal_df = add_single_moving_average(signal_df, window=slot.ma_window, ma_type=slot.ma_type)
        bundle[slot.asset_id] = AssetMarketData(signal_df=signal_df, trade_df=trade_df)
    return bundle


def _persist_history(state_dir: Path, trade_date: date, result: DailyResult) -> None:
    """일별 상세 + 요약을 history/ 에 영구 저장."""
    hist_dir = _history_dir(state_dir)
    daily_payload = {
        "execution_date": result.execution_date,
        "model_equity": result.model_equity,
        "actual_equity": result.actual_equity,
        "drift_pct": result.drift_pct,
        "rebalance_triggered": result.rebalance_triggered,
        "ema_distances": result.ema_distances,
        "pending_fill_reminders": result.pending_fill_reminders,
    }
    history.save_daily_log(trade_date.isoformat(), daily_payload, hist_dir)
    history.append_summary(
        {
            "date": trade_date.isoformat(),
            "model_equity": result.model_equity,
            "actual_equity": result.actual_equity,
            "drift_pct": result.drift_pct,
        },
        hist_dir,
    )


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
# fetch-state / push-state
# ============================================================================


def _cmd_fetch_state(args: argparse.Namespace) -> int:
    state_dir: Path = args.state_dir
    git_state.git_pull(state_dir)
    logger.debug(f"fetch-state 완료: {state_dir}")
    return 0


def _cmd_push_state(args: argparse.Namespace) -> int:
    state_dir: Path = args.state_dir
    message: str = args.message
    pushed = git_state.git_commit_and_push(state_dir, message)
    if pushed:
        logger.debug(f"push-state 완료: {state_dir}")
    else:
        logger.debug(f"push-state 변경 없음 (skip): {state_dir}")
    return 0


# ============================================================================
# fetch-fills
# ============================================================================


def _cmd_fetch_fills(args: argparse.Namespace) -> int:
    rtdb_app = _initialize_rtdb_app()
    if rtdb_app is None:
        logger.error("RTDB 초기화 실패 — 환경변수 확인 필요")
        return 1
    fills = rtdb_gateway.fetch_unprocessed_fills(rtdb_app)
    payload = [
        {
            "rtdb_key": f.rtdb_key,
            "asset_id": f.asset_id,
            "direction": f.direction,
            "actual_price": f.actual_price,
            "actual_shares": f.actual_shares,
            "trade_date": f.trade_date,
            "input_time_kst": f.input_time_kst,
        }
        for f in fills
    ]
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return 0


# ============================================================================
# history
# ============================================================================


def _cmd_history(args: argparse.Namespace) -> int:
    state_dir: Path = args.state_dir
    n: int = args.tail
    summary_path = _history_dir(state_dir) / "summary.jsonl"
    if not summary_path.exists():
        logger.debug(f"summary.jsonl 없음: {summary_path}")
        return 0
    lines = summary_path.read_text(encoding="utf-8").strip().splitlines()
    tail_lines = lines[-n:] if n > 0 else lines
    sys.stdout.write("\n".join(tail_lines) + "\n")
    return 0


# ============================================================================
# notify-failure
# ============================================================================


def _cmd_notify_failure(args: argparse.Namespace) -> int:
    """수동 실패 알림 발송 (Actions retry job 등에서 호출)."""
    message: str = args.message
    rtdb_app = _initialize_rtdb_app()  # 실패 시 None
    _safe_notify_failure(rtdb_app, message)
    return 0


# ============================================================================
# argparse + dispatch
# ============================================================================


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="live.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="초기 LiveState 생성")
    p_init.add_argument("--capital", type=float, required=True)
    p_init.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_init.set_defaults(func=_cmd_init)

    # run-daily
    p_run = sub.add_parser("run-daily", help="일일 실행 통합 루프")
    p_run.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_run.add_argument("--trade-date", type=str, default=None)
    p_run.add_argument("--no-rtdb", action="store_true", help="RTDB 호출 비활성화 (오프라인 dry-run)")
    p_run.add_argument("--no-notify", action="store_true", help="알림 발송 비활성화")
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

    # fetch-state
    p_fetch_state = sub.add_parser("fetch-state", help="qbt-live-state git pull")
    p_fetch_state.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_fetch_state.set_defaults(func=_cmd_fetch_state)

    # push-state
    p_push_state = sub.add_parser("push-state", help="qbt-live-state git add/commit/push")
    p_push_state.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_push_state.add_argument(
        "--message",
        "-m",
        type=str,
        default=f"auto: live update {date.today().isoformat()}",
    )
    p_push_state.set_defaults(func=_cmd_push_state)

    # fetch-fills
    p_fetch_fills = sub.add_parser("fetch-fills", help="RTDB 미처리 fill 목록 출력")
    p_fetch_fills.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_fetch_fills.set_defaults(func=_cmd_fetch_fills)

    # history
    p_hist = sub.add_parser("history", help="history/summary.jsonl 최근 N 줄 출력")
    p_hist.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_hist.add_argument("--tail", type=int, default=10)
    p_hist.set_defaults(func=_cmd_history)

    # notify-failure
    p_notify = sub.add_parser("notify-failure", help="수동 실패 알림 발송")
    p_notify.add_argument("--state-dir", type=Path, default=DEFAULT_LIVE_STATE_DIR)
    p_notify.add_argument(
        "--message",
        "-m",
        type=str,
        default="수동 실패 알림 (notify-failure 명령)",
    )
    p_notify.set_defaults(func=_cmd_notify_failure)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. ``argv`` 가 None 이면 ``sys.argv[1:]`` 사용.

    에러 처리 정책 (설계서 11장 + live/CLAUDE.md):

    - 모든 비즈니스 예외를 ERROR 로그로 기록 후 exit code 1 반환
    - 자동 복구 / 롤백 금지 — 호출자(GitHub Actions) 가 retry 정책 결정
    - argparse 의 ``SystemExit`` 는 그대로 전파
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
