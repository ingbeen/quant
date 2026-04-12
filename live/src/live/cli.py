"""live 도메인 CLI 엔트리포인트.

argparse subcommand 구조로 실매매 파이프라인의 모든 운영 명령을 제공한다.

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
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from exchange_calendars import ExchangeCalendar, get_calendar

from live import data_validator, git_state, history, notifier, rtdb_gateway
from live.chart_data import build_chart_series
from live.constants import (
    APPLIED_FILL_IDS_MAX_AGE_DAYS,
    DEFAULT_APPLIED_BALANCE_ADJUST_IDS_FILENAME,
    DEFAULT_APPLIED_FILL_IDS_FILENAME,
    DEFAULT_LIVE_STATE_DIR,
    DEFAULT_LIVE_STATE_FILENAME,
    FIREBASE_CRED_ENV_KEY,
    FIREBASE_DB_URL,
    HISTORY_SUMMARY_FILENAME,
    KST_TIMEZONE,
    NYSE_CALENDAR_CODE,
    STATE_REPO_PAT_ENV_KEY,
    STATE_REPO_URL,
    TELEGRAM_CHAT_ENV_KEY,
    TELEGRAM_TOKEN_ENV_KEY,
    extract_ticker_from_path,
    get_live_portfolio_config,
    live_csv_path,
)
from live.daily_runner import run_daily
from live.data_fetcher import (
    append_today_to_csv,
    fetch_recent_ohlc,
    load_csv,
    rebuild_full_csv,
)
from live.drift import compute_drift
from live.models import ActualFill, AssetMarketData, BalanceAdjust, DailyResult, MarketBundle
from live.state import (
    cleanup_old_applied_ids,
    create_initial_state,
    load_applied_balance_adjust_ids,
    load_applied_fill_ids,
    load_state,
    save_applied_balance_adjust_ids,
    save_applied_fill_ids,
    save_state,
)
from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.common_constants import COL_CLOSE, COL_DATE
from qbt.utils.logger import get_logger

logger = get_logger(__name__)

__all__ = ["main"]


# ============================================================================
# 환경 / 경로
# ============================================================================

# 프로젝트 루트 (live/src/live/cli.py 로부터 4단계 위)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DOTENV_PATH = _PROJECT_ROOT / ".env"


def _load_dotenv_if_present(dotenv_path: Path = _DOTENV_PATH) -> None:
    """프로젝트 루트의 ``.env`` 파일을 자동 로드.

    - 파일이 없으면 조용히 리턴 (GitHub Actions 등 파일이 없는 환경 대응).
    - ``python-dotenv`` 미설치 시 ``ImportError`` 는 **잡지 않고 전파**한다.
      live extras 가 설치되어 있지 않다는 뚜렷한 신호이므로 즉시 실패가 안전.
    - ``override=False`` — 이미 설정된 환경변수는 덮어쓰지 않아 Actions 의
      ``env:`` 블록이 항상 우선된다.
    """
    if not dotenv_path.is_file():
        return
    load_dotenv(dotenv_path=dotenv_path, override=False)
    logger.debug(f".env 자동 로드 완료: {dotenv_path}")


def _now_kst_for_commit() -> str:
    """커밋 메시지용 KST 타임스탬프 (``YYYY-MM-DD HH:MM:SS KST``)."""
    return datetime.now(KST_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S KST")


def _get_nyse_calendar() -> ExchangeCalendar:
    """NYSE 영업일 달력 (``exchange_calendars`` ``XNYS``) 을 반환한다.

    ``_is_nyse_session`` / ``_refresh_live_csvs`` 가 호출하며, 테스트에서는
    ``monkeypatch`` 로 이 함수를 가짜 달력 객체를 반환하도록 교체할 수 있다.
    """
    return get_calendar(NYSE_CALENDAR_CODE)


def _is_nyse_session(trade_date: date) -> bool:
    """``trade_date`` 가 NYSE 영업일인지 확인.

    cron 이 주말/공휴일에 돌거나 사용자가 workflow_dispatch 에서 휴장일을
    지정해도 불필요한 전체 파이프라인 실행을 막는다.
    """
    calendar = _get_nyse_calendar()
    return bool(calendar.is_session(pd.Timestamp(trade_date)))


@contextmanager
def ephemeral_state_repo(*, push_on_success: bool, commit_subcommand: str) -> Iterator[Path]:
    """매 CLI 실행마다 ``qbt-live-state`` 리포를 shallow clone → yield → (쓰기 명령만)
    commit + push → tempdir cleanup 하는 컨텍스트 매니저.

    로컬과 GitHub Actions 가 **동일한 코드 경로**로 state 리포를 다루도록 하여
    실행 결과가 둘 다 원격 리포의 새 커밋으로 수렴하게 한다.

    Args:
        push_on_success: ``True`` 면 컨텍스트 종료 시 변경사항을 commit & push.
            읽기 전용 명령(``drift``, ``history``)은 ``False``.
        commit_subcommand: 커밋 메시지에 포함될 서브명령 이름 (예: ``run-daily``).

    Yields:
        tempdir 내부의 clone 루트 경로 (``Path``). 이 경로를 ``state_dir`` 로 사용.

    Raises:
        ValueError: ``STATE_REPO_PAT`` 환경변수 미설정.
        RuntimeError: git clone / commit / push 실패 시. 자동 복구 금지 원칙에 따라
            예외는 호출자에게 전파된다.
    """
    pat = os.environ.get(STATE_REPO_PAT_ENV_KEY, "")
    if not pat:
        raise ValueError(f"{STATE_REPO_PAT_ENV_KEY} 환경변수가 설정되지 않았습니다. " "로컬: .env 파일, Actions: workflow env: 블록 확인")

    with tempfile.TemporaryDirectory(prefix="qbt-live-") as td:
        clone_root = Path(td) / DEFAULT_LIVE_STATE_DIR.name
        logger.debug(f"ephemeral state repo clone 시작: {clone_root}")
        git_state.git_clone_shallow(STATE_REPO_URL, clone_root, pat=pat)
        logger.debug("clone 완료")

        # 명령 수행 — 컨텍스트 내부에서 예외 발생 시 push 건너뜀
        yield clone_root

        if push_on_success:
            message = f"auto: live {commit_subcommand} {_now_kst_for_commit()}"
            pushed = git_state.git_commit_and_push(clone_root, message)
            if pushed:
                logger.debug(f"원격 push 완료: {message}")
            else:
                logger.debug("변경사항 없음 — push skip")
    # TemporaryDirectory 의 __exit__ 가 tempdir 자동 삭제


# ============================================================================
# 티커 헬퍼
# ============================================================================


def _ticker_from_slot_signal(slot: AssetSlotConfig) -> str:
    return extract_ticker_from_path(slot.signal_data_path)


def _ticker_from_slot_trade(slot: AssetSlotConfig) -> str:
    return extract_ticker_from_path(slot.trade_data_path)


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


def _history_dir(state_dir: Path) -> Path:
    return state_dir / "history"


# ============================================================================
# RTDB / 알림 헬퍼
# ============================================================================


def _initialize_rtdb_app() -> Any | None:
    """환경변수에서 Firebase 자격증명을 읽어 App 초기화. 실패 시 ``None``."""
    cred_path_str = os.environ.get(FIREBASE_CRED_ENV_KEY)
    if not cred_path_str:
        logger.warning(f"{FIREBASE_CRED_ENV_KEY} 미설정 — RTDB 비활성화")
        return None
    try:
        return rtdb_gateway.initialize_firebase_app(Path(cred_path_str), FIREBASE_DB_URL)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Firebase 초기화 실패: {exc}")
        return None


def _safe_notify_failure(rtdb_app: Any | None, message: str) -> None:
    """RTDB 에서 device 토큰을 읽고 실패 알림을 발송한다.

    토큰 조회나 발송이 실패해도 본 함수는 절대 raise 하지 않는다 (이미 메인 흐름이
    실패한 상태이므로 알림 자체가 실패해도 메인 예외를 가리지 않는다).
    """
    tg_token = os.environ.get(TELEGRAM_TOKEN_ENV_KEY, "")
    tg_chat = os.environ.get(TELEGRAM_CHAT_ENV_KEY, "")
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

    # 2. 차트 데이터 갱신 — 사용자 체결 이력 + 신호 이력 로드해 마커까지 포함
    history_dir = _history_dir(state_dir)
    user_trades = history.load_user_trades(history_dir)
    signal_history = history.load_signal_history(history_dir)
    chart_series = build_chart_series(
        state_dir,
        user_trades=user_trades,
        signal_history=signal_history,
    )
    rtdb_gateway.write_chart_data(rtdb_app, chart_series)

    # 3. 처리된 fill 마킹
    processed_keys = list(result.updated_applied_fill_ids.keys())
    if processed_keys:
        rtdb_gateway.mark_fills_processed(rtdb_app, processed_keys)


def _send_daily_notifications(rtdb_app: Any | None, result: DailyResult) -> None:
    """FCM + 텔레그램 동시 발송. 만료 토큰은 RTDB 에서 정리."""
    tg_token = os.environ.get(TELEGRAM_TOKEN_ENV_KEY, "")
    tg_chat = os.environ.get(TELEGRAM_CHAT_ENV_KEY, "")

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
    capital: float = args.capital
    with ephemeral_state_repo(push_on_success=True, commit_subcommand="init") as state_dir:
        state = create_initial_state(capital)
        state_path = state_dir / DEFAULT_LIVE_STATE_FILENAME
        save_state(state, state_path)
        logger.debug(f"live_state.json 생성 완료: {state_path}")
    return 0


# ============================================================================
# run-daily — 통합 흐름
# ============================================================================


def _cmd_run_daily(args: argparse.Namespace) -> int:
    """일일 실행 통합 루프.

    조기 정상 종료(exit 0) 조건:

    - ``trade_date`` 가 NYSE 비영업일 (휴장 체크) — cron 이 주말/공휴일에 돌 때
    - ``trade_date`` 가 이미 처리된 날짜 (``state.last_model_execution_date`` 와
      동일) 이고 ``--trade-date`` 가 명시되지 않은 경우 (cron 중복 실행 방지)

    ``--trade-date`` 를 명시적으로 전달한 경우 두 체크 모두 bypass 하여
    주말/과거 재현 디버깅을 허용한다.

    예외 처리: 어떤 단계든 예외가 발생하면 그대로 전파한다. 상위 ``main()`` 의
    공통 알림 훅이 ``_safe_notify_failure`` 를 호출한 뒤 exit 1 을 반환한다.
    """
    trade_date_str: str | None = args.trade_date
    is_explicit_trade_date = trade_date_str is not None

    # trade_date 결정 (ephemeral clone 비용 전에 선제 판정)
    trade_date = date.fromisoformat(trade_date_str) if trade_date_str else date.today()

    # 휴장 체크 — 비영업일이면 조기 정상 종료.
    # --trade-date 가 명시되어 있으면 사용자가 의도적으로 해당 날짜를 지정한 것이므로
    # 휴장 여부와 무관하게 진행한다 (주말 재현 테스트 허용).
    if not is_explicit_trade_date and not _is_nyse_session(trade_date):
        logger.debug(f"{trade_date} 는 NYSE 비영업일 — run-daily 조기 종료 (정상)")
        return 0

    with ephemeral_state_repo(push_on_success=True, commit_subcommand="run-daily") as state_dir:
        # 상태 로드
        state_path = state_dir / DEFAULT_LIVE_STATE_FILENAME
        applied_path = state_dir / DEFAULT_APPLIED_FILL_IDS_FILENAME
        try:
            state = load_state(state_path)
            applied_ids = load_applied_fill_ids(applied_path)
        except (FileNotFoundError, ValueError) as exc:
            raise RuntimeError(f"상태 파일 로드 실패: {exc}") from exc

        # idempotency 체크 — 같은 trade_date 가 이미 처리된 경우 조기 종료.
        # --trade-date 명시 시 bypass (디버그/테스트 모드).
        if not is_explicit_trade_date and state.last_model_execution_date == trade_date.isoformat():
            logger.debug(f"{trade_date} 는 이미 처리됨 (last_model_execution_date) — " "run-daily 조기 종료 (정상, 중복 실행 방지)")
            return 0

        # 주가 CSV append (data_fetcher)
        try:
            _refresh_live_csvs(state_dir, trade_date)
        except ValueError as exc:
            raise RuntimeError(f"데이터 검증 실패: {exc}") from exc

        # market_bundle 준비
        try:
            bundle = _build_market_bundle(state_dir)
        except (FileNotFoundError, ValueError) as exc:
            raise RuntimeError(f"market_bundle 준비 실패: {exc}") from exc

        # RTDB 초기화
        rtdb_app: Any | None = _initialize_rtdb_app()

        # RTDB fills 가져오기
        pending_fills: list[ActualFill] = []
        if rtdb_app is not None:
            try:
                pending_fills = rtdb_gateway.fetch_unprocessed_fills(rtdb_app)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB fills 읽기 실패: {exc}") from exc

        # RTDB balance_adjusts 가져오기
        pending_adjusts: list[BalanceAdjust] = []
        if rtdb_app is not None:
            try:
                pending_adjusts = rtdb_gateway.fetch_pending_balance_adjusts(rtdb_app)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB balance_adjusts 읽기 실패: {exc}") from exc

        # applied_balance_adjust_ids 원장 로드 (run_daily 에 전달)
        adjust_path = state_dir / DEFAULT_APPLIED_BALANCE_ADJUST_IDS_FILENAME
        try:
            applied_adjust_ids = load_applied_balance_adjust_ids(adjust_path)
        except ValueError as exc:
            raise RuntimeError(f"applied_balance_adjust_ids.json 로드 실패: {exc}") from exc

        prev_adjust_keys_snapshot = set(applied_adjust_ids.keys())

        # run_daily (순수 계산 — fills + balance_adjust 처리 포함)
        try:
            result = run_daily(
                trade_date=trade_date,
                state=state,
                market_bundle=bundle,
                pending_fills=pending_fills,
                applied_fill_ids=applied_ids,
                pending_adjusts=pending_adjusts,
                applied_balance_adjust_ids=applied_adjust_ids,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"엔진 실행 실패: {exc}. 상태 변경 없음") from exc

        # run_daily 결과의 최종 applied_adjust_ids 를 반영
        applied_adjust_ids = result.updated_applied_balance_adjust_ids

        # 상태 저장 + applied_ids 정리
        save_state(result.updated_state, state_path)
        cleaned_ids = cleanup_old_applied_ids(
            result.updated_applied_fill_ids, max_age_days=APPLIED_FILL_IDS_MAX_AGE_DAYS
        )
        save_applied_fill_ids(cleaned_ids, applied_path)

        # balance_adjust 원장 정리 + 저장
        cleaned_adjust_ids = cleanup_old_applied_ids(applied_adjust_ids, max_age_days=APPLIED_FILL_IDS_MAX_AGE_DAYS)
        save_applied_balance_adjust_ids(cleaned_adjust_ids, adjust_path)

        # 새로 반영된 fill 을 user_trades.jsonl 에 append.
        # run_daily 전후의 applied_fill_ids 차분으로 신규 fill 을 식별한다 (차트 마커용).
        prev_applied_set = set(applied_ids.keys())
        newly_applied_ids = set(result.updated_applied_fill_ids.keys()) - prev_applied_set
        if newly_applied_ids:
            hist_dir = _history_dir(state_dir)
            for fill in pending_fills:
                if fill.rtdb_key in newly_applied_ids:
                    history.append_user_trade(
                        {
                            "asset_id": fill.asset_id,
                            "date": fill.trade_date,
                            "direction": fill.direction,
                        },
                        hist_dir,
                    )

        # 새로 반영된 balance_adjust 를 audit 히스토리에 append + RTDB mark.
        # prev 스냅샷과 apply 후 applied_adjust_ids 의 차분으로 신규 식별.
        newly_applied_adjust_keys = set(applied_adjust_ids.keys()) - prev_adjust_keys_snapshot
        if newly_applied_adjust_keys:
            hist_dir = _history_dir(state_dir)
            for adjust in pending_adjusts:
                if adjust.rtdb_key in newly_applied_adjust_keys:
                    history.append_balance_adjust(
                        {
                            "rtdb_key": adjust.rtdb_key,
                            "asset_id": adjust.asset_id,
                            "new_shares": adjust.new_shares,
                            "new_cash": adjust.new_cash,
                            "reason": adjust.reason,
                            "input_time_kst": adjust.input_time_kst,
                        },
                        hist_dir,
                    )

            # RTDB processed 마킹
            if rtdb_app is not None:
                try:
                    rtdb_gateway.mark_balance_adjusts_processed(rtdb_app, list(newly_applied_adjust_keys))
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError(f"RTDB balance_adjusts mark_processed 실패: {exc}") from exc

        # 영구 히스토리 저장 — 실패 시 즉시 중단 + 알림 (자동 복구 금지)
        try:
            _persist_history(state_dir, trade_date, result)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"히스토리 저장 실패: {exc}") from exc

        # RTDB 갱신
        if rtdb_app is not None:
            try:
                _publish_to_rtdb(rtdb_app, state_dir, result.updated_state, result)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB 갱신 실패: {exc}") from exc

        # 알림 발송
        _send_daily_notifications(rtdb_app, result)

        logger.debug(
            f"run-daily 완료: equity={result.model_equity:,.0f}, "
            f"pending={len(result.order_intents)}, drift={result.drift_pct:.2f}%, "
            f"reminders={len(result.pending_fill_reminders)}"
        )
    return 0


def _validate_against_csv(
    ticker: str,
    recent_df: pd.DataFrame,
    csv_df: pd.DataFrame | None,
    *,
    trade_date: date | None = None,
    calendar: ExchangeCalendar | None = None,
) -> None:
    """yfinance 가 반환한 최근 OHLC 행들에 대해 검증 실행.

    1. 각 행의 OHLC 논리 검증 (High/Low/Close 가 상식에 맞는지)
    2. 기존 CSV 가 있으면, yfinance 와 **같은 날짜** 가 존재하는 행들에 대해
       ``validate_prev_close`` 로 종가 일치 여부 검증.
       이 비교는 **스플릿 감지** (yfinance 가 과거 값을 재조정) 와 **사용자 조작 감지**
       (CSV 를 손으로 수정한 경우) 를 모두 잡아낸다.
    3. ``trade_date`` + ``calendar`` 가 제공되면 ``validate_date_gap`` 으로
       CSV 마지막 거래일과 trade_date 사이의 거래일 누락을 검증.

    Args:
        ticker: 검증 대상 티커 (에러 메시지에 포함).
        recent_df: ``fetch_recent_ohlc`` 반환값 (최근 ~5 거래일 OHLC).
        csv_df: 기존 CSV 로드 결과. 파일이 없으면 ``None``.
        trade_date: 현재 처리 대상 거래일. 거래일 gap 검증에 사용.
        calendar: NYSE 달력 인스턴스. 거래일 gap 검증에 사용.

    Raises:
        ValueError: 검증 실패 시. 메시지에 티커 / 날짜 / 원인 포함.
    """
    # 1. 각 yfinance 행의 OHLC 논리 검증
    for _, yf_row in recent_df.iterrows():
        errors = data_validator.validate_ohlc_logic(yf_row)
        if errors:
            yf_date = yf_row[COL_DATE]
            raise ValueError(f"{ticker} {yf_date}: {errors[0]}")

    if csv_df is None or csv_df.empty:
        return

    # 2. CSV 와 겹치는 날짜에 대해 종가 일치 검증 (스플릿 + 사용자 조작 감지)
    csv_by_date = {row[COL_DATE]: float(row[COL_CLOSE]) for _, row in csv_df.iterrows()}
    for _, yf_row in recent_df.iterrows():
        yf_date = yf_row[COL_DATE]
        if yf_date not in csv_by_date:
            continue
        csv_close = csv_by_date[yf_date]
        yf_close = float(yf_row[COL_CLOSE])
        errors = data_validator.validate_prev_close(csv_close, yf_close)
        if errors:
            raise ValueError(f"{ticker} {yf_date}: {errors[0]}")

    # 3. 거래일 gap 검증 (trade_date / calendar 가 주입된 경우에만)
    if trade_date is not None and calendar is not None:
        csv_last = max(csv_by_date.keys())
        errors = data_validator.validate_date_gap(csv_last, trade_date, calendar)
        if errors:
            raise ValueError(f"{ticker}: {errors[0]}")


def _refresh_live_csvs(state_dir: Path, trade_date: date) -> None:
    """각 자산 티커에 대해 최근 OHLC 를 가져와 검증 후 CSV 에 append.

    검증 실패 시 ``ValueError`` 를 전파하여 상위 ``_cmd_run_daily`` 가
    ``RuntimeError("데이터 검증 실패: ...")`` 로 래핑한 뒤 알림을 발송한다.

    validate_date_gap 을 위한 NYSE 달력은 모든 티커가 공유한다 (싱글톤).
    """
    # NYSE 달력 싱글톤 로드 (validate_date_gap 용). 테스트는 monkeypatch 로
    # _get_nyse_calendar 를 가짜로 교체하여 네트워크 없이 검증할 수 있다.
    # 로드 실패 시 RuntimeError 가 호출자로 전파되어 상위 알림 훅에 도달한다.
    calendar = _get_nyse_calendar()

    for ticker in _collect_all_tickers():
        recent = fetch_recent_ohlc(ticker, days=5)
        csv_path = live_csv_path(state_dir, ticker)
        csv_df = load_csv(csv_path) if csv_path.exists() else None

        # 검증 — 실패 시 ValueError 전파 (상위에서 RuntimeError 로 래핑)
        _validate_against_csv(
            ticker,
            recent,
            csv_df,
            trade_date=trade_date,
            calendar=calendar,
        )

        today_row = recent[recent[COL_DATE] == trade_date]
        if today_row.empty:
            logger.debug(f"{ticker}: {trade_date} 데이터 없음 (휴장일?) — skip")
            continue
        append_today_to_csv(csv_path, today_row.head(1))


def _build_market_bundle(state_dir: Path) -> MarketBundle:
    config = get_live_portfolio_config()
    bundle: MarketBundle = {}
    for slot in config.asset_slots:
        signal_ticker = _ticker_from_slot_signal(slot)
        trade_ticker = _ticker_from_slot_trade(slot)

        signal_df = load_csv(live_csv_path(state_dir, signal_ticker))
        if signal_ticker == trade_ticker:
            trade_df = signal_df.copy()
        else:
            trade_df = load_csv(live_csv_path(state_dir, trade_ticker))

        signal_df = add_single_moving_average(signal_df, window=slot.ma_window, ma_type=slot.ma_type)
        bundle[slot.asset_id] = AssetMarketData(signal_df=signal_df, trade_df=trade_df)
    return bundle


def _persist_history(state_dir: Path, trade_date: date, result: DailyResult) -> None:
    """일별 상세 + 요약 + 신호 이력을 history/ 에 영구 저장."""
    hist_dir = _history_dir(state_dir)
    daily_payload = {
        "execution_date": result.execution_date,
        "model_equity": result.model_equity,
        "actual_equity": result.actual_equity,
        "drift_pct": result.drift_pct,
        "rebalance_triggered": result.rebalance_triggered,
        "ma_distances": result.ma_distances,
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

    # 신호 이력 append — 차트 마커 원본
    signal_entries = [
        {"date": trade_date.isoformat(), "asset_id": asset_id, "state": sig.state}
        for asset_id, sig in result.signals.items()
    ]
    history.append_signal_history(signal_entries, hist_dir)


# ============================================================================
# init-data / rebuild-data
# ============================================================================


def _cmd_init_data(args: argparse.Namespace) -> int:
    del args  # 사용하지 않음
    with ephemeral_state_repo(push_on_success=True, commit_subcommand="init-data") as state_dir:
        for ticker in _collect_all_tickers():
            csv_path = live_csv_path(state_dir, ticker)
            rebuild_full_csv(ticker, csv_path, period="max")
            logger.debug(f"init-data: {ticker} → {csv_path}")
    return 0


def _cmd_rebuild_data(args: argparse.Namespace) -> int:
    ticker: str = args.ticker.upper()
    with ephemeral_state_repo(push_on_success=True, commit_subcommand=f"rebuild-data {ticker}") as state_dir:
        csv_path = live_csv_path(state_dir, ticker)
        rebuild_full_csv(ticker, csv_path, period="max")
        logger.debug(f"rebuild-data: {ticker} → {csv_path}")
    return 0


# ============================================================================
# drift
# ============================================================================


def _cmd_drift(args: argparse.Namespace) -> int:
    del args  # 사용하지 않음
    with ephemeral_state_repo(push_on_success=False, commit_subcommand="drift") as state_dir:
        state = load_state(state_dir / DEFAULT_LIVE_STATE_FILENAME)

        bundle = _build_market_bundle(state_dir)
        closes: dict[str, float] = {}
        for asset_id, md in bundle.items():
            closes[asset_id] = float(md.trade_df[COL_CLOSE].iloc[-1])

        report = compute_drift(state, closes)
        logger.debug(
            f"drift: model={report.model_equity:,.0f}, actual={report.actual_equity:,.0f}, "
            f"{report.drift_pct:.2f}% [{report.recommendation}]"
        )
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
    n: int = args.tail
    with ephemeral_state_repo(push_on_success=False, commit_subcommand="history") as state_dir:
        summary_path = _history_dir(state_dir) / HISTORY_SUMMARY_FILENAME
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
    p_init.set_defaults(func=_cmd_init)

    # run-daily
    p_run = sub.add_parser("run-daily", help="일일 실행 통합 루프")
    p_run.add_argument(
        "--trade-date",
        type=str,
        default=None,
        help="선택. ISO 날짜로 과거 재현 디버깅 (기본: 오늘)",
    )
    p_run.set_defaults(func=_cmd_run_daily)

    # init-data
    p_init_data = sub.add_parser("init-data", help="yfinance 전체 기간 다운로드 (6종)")
    p_init_data.set_defaults(func=_cmd_init_data)

    # rebuild-data
    p_rebuild = sub.add_parser("rebuild-data", help="단일 티커 재다운로드 (스플릿 대응)")
    p_rebuild.add_argument("ticker")
    p_rebuild.set_defaults(func=_cmd_rebuild_data)

    # drift
    p_drift = sub.add_parser("drift", help="현재 drift 지표 출력")
    p_drift.set_defaults(func=_cmd_drift)

    # fetch-fills
    p_fetch_fills = sub.add_parser("fetch-fills", help="RTDB 미처리 fill 목록 출력")
    p_fetch_fills.set_defaults(func=_cmd_fetch_fills)

    # history
    p_hist = sub.add_parser("history", help="history/summary.jsonl 최근 N 줄 출력")
    p_hist.add_argument("--tail", type=int, default=10)
    p_hist.set_defaults(func=_cmd_history)

    # notify-failure
    p_notify = sub.add_parser("notify-failure", help="수동 실패 알림 발송")
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

    에러 처리 정책:

    - **모든** 커맨드의 예외는 이 함수의 공통 훅에서 ``_safe_notify_failure`` 를
      통해 FCM + 텔레그램 실패 알림으로 전파된다. 알림 발송 후 exit code 1 반환.
    - 자동 복구 / 롤백 금지 — 호출자(GitHub Actions) 가 retry 정책 결정.
    - argparse 의 ``SystemExit`` 는 그대로 전파.
    - ``notify-failure`` 커맨드 자체의 실패는 재귀 방지를 위해 알림을 재발송
      하지 않는다 (알림 채널 자체가 막힌 상황에서 알림을 다시 보내면 무한 루프).
    """
    _load_dotenv_if_present()
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        command_name = getattr(args, "command", None)
        if command_name != "notify-failure":
            _safe_notify_failure(None, f"{command_name or 'unknown'} 실패: {exc}")
        logger.error("예외 발생", exc_info=True)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
