"""live 도메인 CLI 엔트리포인트.

argparse subcommand 구조로 실매매 파이프라인의 모든 운영 명령을 제공한다.

명령어:

- ``reset`` — 전체 초기화 (state + CSV + history + RTDB)
- ``run-daily`` — 일일 실행 통합 루프 (data → daily_runner → state → RTDB → 알림 → history)
- ``rebuild-data`` — 티커 CSV 재다운로드. 티커 생략 시 전체 운영 티커 재다운로드
  (스플릿 대응 및 최초 배포 데이터 초기화)
- ``drift`` — 현재 drift 지표 출력
- ``fetch-fills`` — RTDB 의 미처리 fill 목록 조회 출력
- ``backfill-chart-years`` — 차트 연도 슬라이스 전체 재생성 (스플릿 대응 수동 명령)
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
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from exchange_calendars import ExchangeCalendar, get_calendar

from live import data_validator, history, notifier, rtdb_gateway, storage_gateway
from live.chart_data import (
    build_chart_meta_and_year_slices,
    build_equity_meta,
    build_equity_year_slice,
    build_equity_year_slices,
)
from live.constants import (
    APPLIED_FILL_IDS_MAX_AGE_DAYS,
    DEFAULT_APPLIED_BALANCE_ADJUST_IDS_FILENAME,
    DEFAULT_APPLIED_FILL_IDS_FILENAME,
    DEFAULT_LIVE_STATE_FILENAME,
    DEFAULT_RECENT_FETCH_DAYS,
    FIREBASE_CRED_ENV_KEY,
    FIREBASE_DB_URL,
    KST_TIMEZONE,
    NYSE_CALENDAR_CODE,
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
from live.models import (
    ActualFill,
    AssetMarketData,
    BalanceAdjust,
    DailyResult,
    FillDismiss,
    MarketBundle,
    ModelSync,
)
from live.state import (
    cleanup_old_applied_ids,
    create_initial_state,
    load_applied_balance_adjust_ids,
    load_applied_fill_dismiss_ids,
    load_applied_fill_ids,
    load_state,
    save_applied_balance_adjust_ids,
    save_applied_fill_dismiss_ids,
    save_applied_fill_ids,
    save_state,
    save_state_snapshot,
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

# 프로젝트 루트 (src/live/cli.py 로부터 3단계 위)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
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


def _now_kst_iso() -> str:
    """RTDB / GCS 정본 history 미러용 KST ISO 8601 타임스탬프.

    예: ``"2026-04-11T07:27:15+09:00"``. ``run-daily`` 진입 시 1 회 산출하여
    이번 실행에서 새로 적용된 모든 fill / balance_adjust 의 ``applied_at`` 으로
    동일하게 부여한다 (배치 단위 통일). 마이크로초는 잘라 가독성 우선.
    """
    return datetime.now(KST_TIMEZONE).replace(microsecond=0).isoformat()


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
    """환경변수에서 Firebase 자격증명을 읽어 App 초기화. 실패 시 ``None``.

    실패해도 계속 진행해도 되는 경로(``drift``, ``history``, ``notify-failure``) 에서만
    사용한다. ``run-daily`` / ``fetch-fills`` 와 같이 RTDB 가 필수인 경로는
    :func:`_require_rtdb_app` 을 써서 실패 시 즉시 ``RuntimeError`` 로 중단하고
    공통 알림 훅이 실패 알림을 발송하게 한다.
    """
    cred_path_str = os.environ.get(FIREBASE_CRED_ENV_KEY)
    if not cred_path_str:
        logger.warning(f"{FIREBASE_CRED_ENV_KEY} 미설정 — RTDB 비활성화")
        return None
    try:
        return rtdb_gateway.initialize_firebase_app(Path(cred_path_str), FIREBASE_DB_URL)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Firebase 초기화 실패: {exc}")
        return None


def _require_rtdb_app() -> Any:
    """RTDB 가 필수인 경로에서 사용. 초기화 실패 시 ``RuntimeError`` 전파.

    ``_initialize_rtdb_app`` 와 달리 ``None`` 반환을 허용하지 않는다.
    RuntimeError 는 상위 ``main()`` 공통 알림 훅이 잡아 실패 알림을 발송한다.
    """
    app = _initialize_rtdb_app()
    if app is None:
        raise RuntimeError("Firebase 초기화 실패 — RTDB 가 필수인 명령(run-daily / fetch-fills)" " 은 진행 불가. 환경변수 / 자격증명 확인 필요")
    return app


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
    newly_applied_fill_keys: set[str],
) -> None:
    """RTDB 에 read model + chart_data (meta/years/{현재_연도}) 를 갱신하고
    신규 fill 을 processed 마킹한다.
    """
    # 1. read model 갱신
    rtdb_gateway.write_read_model(rtdb_app, state, result)

    # 2. 차트 데이터 갱신 — meta + 현재 연도 슬라이스
    #    (이전 연도 슬라이스는 backfill CLI 가 1 회 생성하고 스플릿 등 이벤트 시
    #    수동 재생성한다. daily runner 는 건드리지 않는다.)
    execution_date = date.fromisoformat(result.execution_date)
    history_dir = _history_dir(state_dir)
    user_trades = history.load_user_trades(history_dir)
    signal_history = history.load_signal_history(history_dir)

    current_year = execution_date.year
    # 자산 frame 1 회 로드로 meta + 현재 연도 슬라이스 동시 생성 (N+1 회피).
    meta_map, slices_map = build_chart_meta_and_year_slices(
        state_dir,
        years=[current_year],
        user_trades=user_trades,
        signal_history=signal_history,
    )
    rtdb_gateway.write_chart_meta(rtdb_app, meta_map)
    rtdb_gateway.write_chart_year_slice(rtdb_app, year=current_year, year_map=slices_map[current_year])

    # 3-b. equity 차트 갱신 — meta + 현재 연도 슬라이스 (/charts/equity/)
    #      데이터 소스는 GCS 정본 history/summary.jsonl. run-daily 는 이 시점에
    #      _persist_history 를 통해 당일 1 줄을 이미 append 했으므로 파일이 최소
    #      1 줄 이상 보장된다. 과거 연도 슬라이스는 backfill CLI 로만 재생성.
    equity_meta = build_equity_meta(state_dir)
    rtdb_gateway.write_equity_meta(rtdb_app, equity_meta)
    equity_year = build_equity_year_slice(state_dir, year=current_year)
    rtdb_gateway.write_equity_year_slice(rtdb_app, year=current_year, series=equity_year)

    # 3-c. /history/signals/ 미러 — 당일 4 자산 전체 덮어쓰기 (idempotent).
    #      fills / balance_adjusts 미러는 cli 본문(run-daily)에서 신규 키만 선별해
    #      처리하지만, signals 는 매 실행마다 4 자산 보장이 되므로 여기서 일괄 처리.
    rtdb_gateway.write_history_signals(rtdb_app, result.execution_date, result.signals)

    # 4. 신규 fill 만 processed 마킹 (기존 적용 ID 는 skip)
    if newly_applied_fill_keys:
        rtdb_gateway.mark_fills_processed(rtdb_app, list(newly_applied_fill_keys))


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
# reset
# ============================================================================


def _cmd_reset(args: argparse.Namespace) -> int:
    """전체 초기화 (state + CSV + applied_ids + history + RTDB) + RTDB 주가 차트 재생성.

    신규 9 단계 순서 (안정성 우선):

    1. 사전 검증 — Firebase 초기화 가능 여부 확인. 실패 시 정본 / RTDB 미수정.
    2. GCS 정본 다운로드 (state workspace 컨텍스트 진입)
    3. ``live_state.json`` 초기값 저장
    4. ``applied_*_ids.json`` 3 개 파일 삭제
    5. ``history/`` 디렉토리 삭제 (summary / user_trades / signals / balance_adjusts 포함)
    6. CSV 전체 재다운로드 (``period="max"``)
    7. RTDB 전체 삭제 (``device_tokens`` 제외)
    8. RTDB 주가 차트 재생성 — meta / 연도별 슬라이스. 체결/시그널 마커는 빈 리스트.
    9. GCS 정본 업로드 (state workspace 컨텍스트 종료 시 변경분 자동 동기화)

    equity 차트 / ``/history/*`` 는 summary.jsonl 이 없어 이 시점에 생성 불가.
    매일 ``run-daily`` 가 당일분을 누적하면서 자연스럽게 채워진다.

    실패 정책 (루트 CLAUDE.md 원칙 1): 어떤 단계든 예외 발생 시 즉시 중단.
    reset 은 사용자 직접 실행 명령이므로 실패 알림을 발송하지 않는다 (터미널 stderr +
    ERROR 로그로만 노출). 재실행 시 멱등 복구 가능하다 (모든 단계가 덮어쓰기).
    """
    capital: float = args.capital

    # 1. 사전 검증: Firebase 초기화 가능 여부. 실패 시 아무것도 건드리지 않고 중단.
    rtdb_app: Any = _require_rtdb_app()

    # 2~6, 7~8, 9. GCS 다운로드 → 파일 작업 → RTDB 삭제 → 차트 재생성 → 변경분 GCS 업로드.
    with storage_gateway.state_workspace(push_on_success=True) as state_dir:
        # 3. live_state.json 초기화
        state = create_initial_state(capital)
        save_state(state, state_dir / DEFAULT_LIVE_STATE_FILENAME)

        # 4. applied_*_ids.json 삭제
        for filename in [
            DEFAULT_APPLIED_FILL_IDS_FILENAME,
            DEFAULT_APPLIED_BALANCE_ADJUST_IDS_FILENAME,
            "applied_fill_dismiss_ids.json",
        ]:
            p = state_dir / filename
            if p.exists():
                p.unlink()

        # 5. history/ 삭제
        hist_dir = _history_dir(state_dir)
        if hist_dir.exists():
            shutil.rmtree(hist_dir)

        # 6. CSV 전체 재다운로드
        for ticker in _collect_all_tickers():
            csv_path = live_csv_path(state_dir, ticker)
            rebuild_full_csv(ticker, csv_path, period="max")
            logger.debug(f"reset: {ticker} CSV 재다운로드 → {csv_path}")

        # 7. RTDB 전체 삭제 (device_tokens 제외)
        rtdb_gateway.delete_all_except_device_tokens(rtdb_app)
        logger.debug("RTDB 초기화 완료 (device_tokens 유지)")

        # 8. RTDB 주가 차트 재생성 — 체결/시그널 마커는 빈 리스트.
        #    summary.jsonl 이 없어 equity 차트는 생성하지 않는다 (run-daily 가 누적).
        #    years=None 으로 호출 → 자산 frame 1 회 로드로 meta + 전체 연도 슬라이스 동시 생성.
        meta_map, slices_map = build_chart_meta_and_year_slices(
            state_dir,
            years=None,
            user_trades={},
            signal_history={},
        )
        rtdb_gateway.write_chart_meta(rtdb_app, meta_map)
        for year in sorted(slices_map.keys()):
            rtdb_gateway.write_chart_year_slice(rtdb_app, year=year, year_map=slices_map[year])

    logger.debug(f"reset 완료: capital={capital:,.0f}")
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

    # trade_date 결정 (state workspace 비용 전에 선제 판정)
    trade_date = date.fromisoformat(trade_date_str) if trade_date_str else date.today()

    # 휴장 체크 — 비영업일이면 조기 정상 종료.
    # --trade-date 가 명시되어 있으면 사용자가 의도적으로 해당 날짜를 지정한 것이므로
    # 휴장 여부와 무관하게 진행한다 (주말 재현 테스트 허용).
    if not is_explicit_trade_date and not _is_nyse_session(trade_date):
        logger.debug(f"{trade_date} 는 NYSE 비영업일 — run-daily 조기 종료 (정상)")
        return 0

    # RTDB / GCS 정본 history 미러용 단일 KST timestamp.
    # 이번 실행에서 새로 적용된 모든 fill / balance_adjust 의 ``applied_at`` 에 동일 부여.
    applied_at_kst = _now_kst_iso()

    with storage_gateway.state_workspace(push_on_success=True) as state_dir:
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

        # RTDB 초기화 — run-daily 는 필수. 실패 시 즉시 RuntimeError 로 중단한다.
        rtdb_app: Any = _require_rtdb_app()

        # RTDB fills 가져오기
        try:
            pending_fills: list[ActualFill] = rtdb_gateway.fetch_unprocessed_fills(rtdb_app)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"RTDB fills 읽기 실패: {exc}") from exc

        # RTDB balance_adjusts 가져오기
        try:
            pending_adjusts: list[BalanceAdjust] = rtdb_gateway.fetch_pending_balance_adjusts(rtdb_app)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"RTDB balance_adjusts 읽기 실패: {exc}") from exc

        # RTDB fill_dismisses 가져오기
        try:
            pending_dismisses: list[FillDismiss] = rtdb_gateway.fetch_pending_fill_dismisses(rtdb_app)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"RTDB fill_dismisses 읽기 실패: {exc}") from exc

        # RTDB model_sync 가져오기 (전체 model=actual 동기화 요청, 멱등)
        try:
            pending_model_syncs: list[ModelSync] = rtdb_gateway.fetch_unprocessed_model_syncs(rtdb_app)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"RTDB model_syncs 읽기 실패: {exc}") from exc

        # applied_balance_adjust_ids 원장 로드 (run_daily 에 전달)
        adjust_path = state_dir / DEFAULT_APPLIED_BALANCE_ADJUST_IDS_FILENAME
        try:
            applied_adjust_ids = load_applied_balance_adjust_ids(adjust_path)
        except ValueError as exc:
            raise RuntimeError(f"applied_balance_adjust_ids.json 로드 실패: {exc}") from exc

        # applied_fill_dismiss_ids 원장 로드
        dismiss_path = state_dir / "applied_fill_dismiss_ids.json"
        try:
            applied_dismiss_ids = load_applied_fill_dismiss_ids(dismiss_path)
        except ValueError as exc:
            raise RuntimeError(f"applied_fill_dismiss_ids.json 로드 실패: {exc}") from exc

        prev_adjust_keys_snapshot = set(applied_adjust_ids.keys())
        prev_dismiss_keys_snapshot = set(applied_dismiss_ids.keys())

        # run_daily (순수 계산 — fills + balance_adjust + model_sync + fill_dismiss 처리 포함)
        try:
            result = run_daily(
                trade_date=trade_date,
                state=state,
                market_bundle=bundle,
                pending_fills=pending_fills,
                applied_fill_ids=applied_ids,
                pending_adjusts=pending_adjusts,
                applied_balance_adjust_ids=applied_adjust_ids,
                pending_dismisses=pending_dismisses,
                applied_fill_dismiss_ids=applied_dismiss_ids,
                pending_model_syncs=pending_model_syncs,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"엔진 실행 실패: {exc}. 상태 변경 없음") from exc

        # run_daily 결과의 최종 applied_*_ids 를 반영
        applied_adjust_ids = result.updated_applied_balance_adjust_ids
        applied_dismiss_ids = result.updated_applied_fill_dismiss_ids

        # 상태 저장 + applied_ids 정리
        save_state(result.updated_state, state_path)
        # 일별 상태 스냅샷 저장 (history/states/{YYYY-MM-DD}.json). 실패 시 예외 전파 →
        # 공통 예외 훅이 실패 알림 발송. 자동 재시도 / 롤백 없음 (원칙 1).
        save_state_snapshot(result.updated_state, _history_dir(state_dir), trade_date)
        cleaned_ids = cleanup_old_applied_ids(
            result.updated_applied_fill_ids, max_age_days=APPLIED_FILL_IDS_MAX_AGE_DAYS
        )
        save_applied_fill_ids(cleaned_ids, applied_path)

        # balance_adjust 원장 정리 + 저장
        cleaned_adjust_ids = cleanup_old_applied_ids(applied_adjust_ids, max_age_days=APPLIED_FILL_IDS_MAX_AGE_DAYS)
        save_applied_balance_adjust_ids(cleaned_adjust_ids, adjust_path)

        # fill_dismiss 원장 정리 + 저장
        cleaned_dismiss_ids = cleanup_old_applied_ids(applied_dismiss_ids, max_age_days=APPLIED_FILL_IDS_MAX_AGE_DAYS)
        save_applied_fill_dismiss_ids(cleaned_dismiss_ids, dismiss_path)

        # 새로 반영된 fill 을 user_trades.jsonl 에 append + RTDB /history/fills/ 미러.
        # run_daily 전후의 applied_fill_ids 차분으로 신규 fill 을 식별한다 (차트 마커용).
        prev_applied_set = set(applied_ids.keys())
        newly_applied_ids = set(result.updated_applied_fill_ids.keys()) - prev_applied_set
        newly_applied_fills: list[ActualFill] = []
        if newly_applied_ids:
            hist_dir = _history_dir(state_dir)
            for fill in pending_fills:
                if fill.rtdb_key not in newly_applied_ids:
                    continue
                newly_applied_fills.append(fill)
                # JSONL 페이로드: 차트 마커 빌더 호환 (asset_id/date/direction) +
                # RTDB /history/fills/ 미러용 풀 페이로드.
                history.append_user_trade(
                    {
                        "asset_id": fill.asset_id,
                        "date": fill.trade_date,
                        "direction": fill.direction,
                        "actual_price": fill.actual_price,
                        "actual_shares": fill.actual_shares,
                        "trade_date": fill.trade_date,
                        "input_time_kst": fill.input_time_kst,
                        "memo": fill.memo,
                        "reason": fill.reason,
                        "rtdb_key": fill.rtdb_key,
                        "applied_at": applied_at_kst,
                    },
                    hist_dir,
                )

            # RTDB /history/fills/ 미러 — 실패 시 즉시 중단, 공통 알림 훅이 처리.
            try:
                rtdb_gateway.write_history_fills(rtdb_app, newly_applied_fills, applied_at_kst)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB /history/fills/ 미러 실패: {exc}") from exc

        # 새로 반영된 balance_adjust 를 audit 히스토리에 append + RTDB mark + /history 미러.
        # prev 스냅샷과 apply 후 applied_adjust_ids 의 차분으로 신규 식별.
        newly_applied_adjust_keys = set(applied_adjust_ids.keys()) - prev_adjust_keys_snapshot
        newly_applied_adjusts: list[BalanceAdjust] = []
        if newly_applied_adjust_keys:
            hist_dir = _history_dir(state_dir)
            for adjust in pending_adjusts:
                if adjust.rtdb_key not in newly_applied_adjust_keys:
                    continue
                newly_applied_adjusts.append(adjust)
                history.append_balance_adjust(
                    {
                        "rtdb_key": adjust.rtdb_key,
                        "asset_id": adjust.asset_id,
                        "new_shares": adjust.new_shares,
                        "new_avg_price": adjust.new_avg_price,
                        "new_entry_date": adjust.new_entry_date,
                        "new_cash": adjust.new_cash,
                        "reason": adjust.reason,
                        "input_time_kst": adjust.input_time_kst,
                        "applied_at": applied_at_kst,
                    },
                    hist_dir,
                )

            # RTDB processed 마킹
            try:
                rtdb_gateway.mark_balance_adjusts_processed(rtdb_app, list(newly_applied_adjust_keys))
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB balance_adjusts mark_processed 실패: {exc}") from exc

            # RTDB /history/balance_adjusts/ 미러
            try:
                rtdb_gateway.write_history_balance_adjusts(rtdb_app, newly_applied_adjusts, applied_at_kst)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB /history/balance_adjusts/ 미러 실패: {exc}") from exc

        # 새로 반영된 fill_dismiss 를 audit 히스토리에 append + RTDB mark.
        newly_applied_dismiss_keys = set(applied_dismiss_ids.keys()) - prev_dismiss_keys_snapshot
        if newly_applied_dismiss_keys:
            hist_dir = _history_dir(state_dir)
            for dismiss in pending_dismisses:
                if dismiss.rtdb_key in newly_applied_dismiss_keys:
                    history.append_fill_dismiss(
                        {
                            "rtdb_key": dismiss.rtdb_key,
                            "asset_id": dismiss.asset_id,
                            "reason": dismiss.reason,
                            "input_time_kst": dismiss.input_time_kst,
                        },
                        hist_dir,
                    )

            # RTDB processed 마킹
            try:
                rtdb_gateway.mark_fill_dismisses_processed(rtdb_app, list(newly_applied_dismiss_keys))
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB fill_dismisses mark_processed 실패: {exc}") from exc

        # model_sync 는 applied_ids 원장이 없으며 "model = actual" 덮어쓰기로 멱등이므로
        # 읽어온 모든 key 를 적용 여부와 무관하게 processed 마킹한다. 별도 history 파일
        # 저장 없이 DailyResult.model_sync_applied + history/states/{date}.json 스냅샷으로 추적한다.
        if pending_model_syncs:
            try:
                rtdb_gateway.mark_model_syncs_processed(rtdb_app, [s.rtdb_key for s in pending_model_syncs])
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"RTDB model_syncs mark_processed 실패: {exc}") from exc

        # 영구 히스토리 저장 — 실패 시 즉시 중단 + 알림 (자동 복구 금지)
        try:
            _persist_history(state_dir, trade_date, result)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"히스토리 저장 실패: {exc}") from exc

        # RTDB 갱신
        try:
            _publish_to_rtdb(rtdb_app, state_dir, result.updated_state, result, newly_applied_ids)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"RTDB 갱신 실패: {exc}") from exc

        # 알림 발송
        _send_daily_notifications(rtdb_app, result)

        logger.debug(
            f"run-daily 완료: equity={result.model_equity:,.0f}, "
            f"pending={len(result.order_intents)}, drift={result.drift_pct * 100:.2f}%, "
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
        recent = fetch_recent_ohlc(ticker, days=DEFAULT_RECENT_FETCH_DAYS)
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
        # 이미 위에서 로드한 csv_df 를 전달하여 append_today_to_csv 내부의 재로드를 피한다.
        append_today_to_csv(csv_path, today_row.head(1), existing_df=csv_df)


def _build_market_bundle(state_dir: Path) -> MarketBundle:
    """자산별 시그널/체결 DataFrame 을 로드하고, 전 자산 공통 기간으로 정렬한다.

    QBT 포트폴리오 엔진의 ``_load_portfolio_data_with_common_period`` 와 동일한
    패턴으로, 모든 자산의 trade_df 날짜 교집합을 계산한 뒤 signal_df / trade_df 를
    공통 기간으로 필터링한다. 이를 통해 ``_validate_trade_date_alignment`` 에서
    요구하는 날짜 집합 동일성 불변조건을 보장한다.
    """
    config = get_live_portfolio_config()

    # 1. 자산별 데이터 로드 + MA 계산
    raw_bundle: dict[str, AssetMarketData] = {}
    for slot in config.asset_slots:
        signal_ticker = _ticker_from_slot_signal(slot)
        trade_ticker = _ticker_from_slot_trade(slot)

        signal_df = load_csv(live_csv_path(state_dir, signal_ticker))
        if signal_ticker == trade_ticker:
            trade_df = signal_df.copy()
        else:
            trade_df = load_csv(live_csv_path(state_dir, trade_ticker))

        signal_df = add_single_moving_average(signal_df, window=slot.ma_window, ma_type=slot.ma_type)
        raw_bundle[slot.asset_id] = AssetMarketData(signal_df=signal_df, trade_df=trade_df)

    # 2. 전 자산 trade_df 날짜 교집합 계산
    date_sets = [set(data.trade_df[COL_DATE]) for data in raw_bundle.values()]
    common_dates: set[date] = date_sets[0]
    for ds in date_sets[1:]:
        common_dates &= ds

    if not common_dates:
        raise ValueError("전 자산의 공통 거래 기간이 없습니다.")

    # 3. 공통 기간으로 필터링
    bundle: MarketBundle = {}
    for asset_id, data in raw_bundle.items():
        signal_mask = data.signal_df[COL_DATE].isin(common_dates)
        trade_mask = data.trade_df[COL_DATE].isin(common_dates)
        bundle[asset_id] = AssetMarketData(
            signal_df=data.signal_df[signal_mask].reset_index(drop=True),
            trade_df=data.trade_df[trade_mask].reset_index(drop=True),
        )

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
        "model_sync_applied": result.model_sync_applied,
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

    # 신호 이력 append — 차트 마커 원본 + RTDB /history/signals/ 미러용 풀 페이로드.
    # 차트 마커 빌더(load_signal_history)는 date/asset_id/state 만 사용하며 새 필드는 무시.
    signal_entries = [
        {
            "date": trade_date.isoformat(),
            "asset_id": asset_id,
            "state": sig.state,
            "close": sig.close,
            "ma_value": sig.ma_value,
            "ma_distance_pct": sig.ma_distance_pct,
            "upper_band": sig.upper_band,
            "lower_band": sig.lower_band,
        }
        for asset_id, sig in result.signals.items()
    ]
    history.append_signal_history(signal_entries, hist_dir)


# ============================================================================
# rebuild-data
# ============================================================================


def _cmd_rebuild_data(args: argparse.Namespace) -> int:
    """단일 또는 전체 티커 CSV 재다운로드.

    - ``ticker`` 생략 시: 모든 운영 티커를 ``period="max"`` 로 전체 재다운로드.
    - ``ticker`` 명시 시: 해당 티커만 재다운로드 (스플릿 대응 시나리오).
    """
    ticker_arg: str | None = args.ticker
    if ticker_arg is None:
        with storage_gateway.state_workspace(push_on_success=True) as state_dir:
            for ticker in _collect_all_tickers():
                csv_path = live_csv_path(state_dir, ticker)
                rebuild_full_csv(ticker, csv_path, period="max")
                logger.debug(f"rebuild-data: {ticker} → {csv_path}")
        return 0

    ticker = ticker_arg.upper()
    with storage_gateway.state_workspace(push_on_success=True) as state_dir:
        csv_path = live_csv_path(state_dir, ticker)
        rebuild_full_csv(ticker, csv_path, period="max")
        logger.debug(f"rebuild-data: {ticker} → {csv_path}")
    return 0


# ============================================================================
# drift
# ============================================================================


def _cmd_drift(args: argparse.Namespace) -> int:
    del args  # 사용하지 않음
    with storage_gateway.state_workspace(push_on_success=False) as state_dir:
        state = load_state(state_dir / DEFAULT_LIVE_STATE_FILENAME)

        bundle = _build_market_bundle(state_dir)
        closes: dict[str, float] = {}
        for asset_id, md in bundle.items():
            closes[asset_id] = float(md.trade_df[COL_CLOSE].iloc[-1])

        report = compute_drift(state, closes)
        logger.debug(
            f"drift: model={report.model_equity:,.0f}, actual={report.actual_equity:,.0f}, "
            f"{report.drift_pct * 100:.2f}% [{report.recommendation}]"
        )
    return 0


# ============================================================================
# fetch-fills
# ============================================================================


def _cmd_fetch_fills(args: argparse.Namespace) -> int:
    del args  # 사용하지 않음
    rtdb_app = _require_rtdb_app()
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


def _cmd_backfill_chart_years(args: argparse.Namespace) -> int:
    """차트 연도 슬라이스를 일괄 재생성한다 (최초 배포 / 스플릿 대응 수동 명령).

    daily runner 는 매 실행마다 meta + years/{현재_연도} 만 갱신하므로,
    (1) 최초 배포 직후 과거 연도 슬라이스가 아예 없는 상태이거나,
    (2) 스플릿/무상증자 발생으로 과거 연도 슬라이스를 새 조정가 기준으로 다시
    쓸 필요가 있을 때, 운영자가 이 명령을 수동 실행한다.

    옵션:

    - ``--target prices|equity|all``: 재생성 대상 차트 종류 (기본값 ``all``).
    - ``--year YYYY``: 단일 연도만 재생성 (기본: 대상 차트의 years 전체).
    - ``--dry-run``: 실제 RTDB 쓰기 없이 대상 연도만 출력.

    본 명령은 state workspace 를 read-only 로 clone 하여 CSV / summary.jsonl
    만 사용한다. GCS 업로드는 수행하지 않는다.
    """
    target: str = args.target
    year_arg: int | None = args.year
    dry_run: bool = args.dry_run

    with storage_gateway.state_workspace(push_on_success=False) as state_dir:
        history_dir = _history_dir(state_dir)
        user_trades = history.load_user_trades(history_dir)
        signal_history = history.load_signal_history(history_dir)

        do_prices = target in ("prices", "all")
        do_equity = target in ("equity", "all")

        # 주가 차트: 자산 frame 1 회 로드로 meta + 전체 연도 슬라이스 동시 빌드.
        prices_meta_map: dict[str, Any] = {}
        prices_slices_map: dict[int, dict[str, Any]] = {}
        prices_years: list[int] = []
        if do_prices:
            prices_meta_map, prices_slices_map = build_chart_meta_and_year_slices(
                state_dir,
                years=None,
                user_trades=user_trades,
                signal_history=signal_history,
            )
            prices_years = sorted(prices_slices_map.keys())

        equity_meta = None
        equity_slices_map: dict[int, Any] = {}
        equity_years: list[int] = []
        if do_equity:
            equity_meta = build_equity_meta(state_dir)
            equity_years = sorted(equity_meta.years)
            equity_slices_map = build_equity_year_slices(state_dir, years=equity_years)

        target_prices_years: list[int]
        target_equity_years: list[int]
        if year_arg is not None:
            if do_prices and year_arg not in prices_years and not (do_equity and year_arg in equity_years):
                logger.warning(f"--year={year_arg} 가 주가 / equity years 어디에도 없음. 대상 연도 없음.")
                return 0
            target_prices_years = [year_arg] if (do_prices and year_arg in prices_years) else []
            target_equity_years = [year_arg] if (do_equity and year_arg in equity_years) else []
        else:
            target_prices_years = prices_years if do_prices else []
            target_equity_years = equity_years if do_equity else []

        if dry_run:
            sys.stdout.write(
                f"[dry-run] target={target} | 주가 자산 {sorted(prices_meta_map.keys())} × 연도 {target_prices_years} "
                f"| equity 연도 {target_equity_years}\n"
            )
            return 0

        rtdb_app = _require_rtdb_app()

        for year in target_prices_years:
            rtdb_gateway.write_chart_year_slice(rtdb_app, year=year, year_map=prices_slices_map[year])
            logger.debug(f"prices/years/{year} 재생성 완료")

        if do_prices:
            rtdb_gateway.write_chart_meta(rtdb_app, prices_meta_map)

        for year in target_equity_years:
            rtdb_gateway.write_equity_year_slice(rtdb_app, year=year, series=equity_slices_map[year])
            logger.debug(f"equity/years/{year} 재생성 완료")

        if do_equity and equity_meta is not None:
            rtdb_gateway.write_equity_meta(rtdb_app, equity_meta)
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

    # reset
    p_reset = sub.add_parser("reset", help="전체 초기화 (state + CSV + history + RTDB)")
    p_reset.add_argument("--capital", type=float, required=True)
    p_reset.set_defaults(func=_cmd_reset)

    # run-daily
    p_run = sub.add_parser("run-daily", help="일일 실행 통합 루프")
    p_run.add_argument(
        "--trade-date",
        type=str,
        default=None,
        help="선택. ISO 날짜로 과거 재현 디버깅 (기본: 오늘)",
    )
    p_run.set_defaults(func=_cmd_run_daily)

    # rebuild-data
    p_rebuild = sub.add_parser(
        "rebuild-data",
        help="티커 CSV 재다운로드. 티커 생략 시 전체 운영 티커 재다운로드 (스플릿 대응 / 최초 배포 초기화)",
    )
    p_rebuild.add_argument(
        "ticker",
        nargs="?",
        default=None,
        help="선택. 티커 생략 시 모든 운영 티커를 period=max 로 재다운로드",
    )
    p_rebuild.set_defaults(func=_cmd_rebuild_data)

    # drift
    p_drift = sub.add_parser("drift", help="현재 drift 지표 출력")
    p_drift.set_defaults(func=_cmd_drift)

    # fetch-fills
    p_fetch_fills = sub.add_parser("fetch-fills", help="RTDB 미처리 fill 목록 출력")
    p_fetch_fills.set_defaults(func=_cmd_fetch_fills)

    # backfill-chart-years
    p_backfill = sub.add_parser(
        "backfill-chart-years",
        help="차트 연도 슬라이스 전체 재생성 (최초 배포 / 스플릿 대응 수동 명령)",
    )
    p_backfill.add_argument(
        "--target",
        choices=["prices", "equity", "all"],
        default="all",
        help="선택. 재생성 대상 차트 종류 (기본: all = 주가 + equity)",
    )
    p_backfill.add_argument(
        "--year",
        type=int,
        default=None,
        help="선택. 단일 연도만 재생성 (기본: 대상 차트의 years 전체)",
    )
    p_backfill.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 RTDB 쓰기 없이 대상 연도 목록만 출력",
    )
    p_backfill.set_defaults(func=_cmd_backfill_chart_years)

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


#: 실패 시 FCM + 텔레그램 알림을 발송할 **자동 실행 커맨드 allow-list**.
#: GitHub Actions cron 으로 무인 실행되는 커맨드만 포함한다. 사용자 직접 실행
#: 커맨드 (``reset`` / ``rebuild-data`` / ``drift`` / ``fetch-fills`` /
#: ``backfill-chart-years``) 는 터미널 stderr + ERROR 로그로만 실패를 노출한다.
#: ``notify-failure`` 는 재귀 방지를 위해 allow-list 에 포함하지 않는다.
_NOTIFY_FAILURE_COMMANDS: frozenset[str] = frozenset({"run-daily"})


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. ``argv`` 가 None 이면 ``sys.argv[1:]`` 사용.

    에러 처리 정책:

    - **자동 실행 커맨드 (`run-daily`)** 의 예외만 이 함수의 공통 훅에서
      ``_safe_notify_failure`` 를 통해 FCM + 텔레그램 실패 알림으로 전파된다.
      사용자가 터미널을 보고 있지 않은 상황 (Actions cron) 을 위한 최후 알림.
    - 사용자 직접 실행 커맨드 (``reset`` / ``rebuild-data`` / ``drift`` /
      ``fetch-fills`` / ``backfill-chart-years``) 의 실패는
      터미널 stderr + ERROR 로그로만 노출한다 (FCM / 텔레그램 알림 없음).
    - 자동 복구 / 롤백 금지 — 호출자(GitHub Actions) 가 retry 정책 결정.
    - argparse 의 ``SystemExit`` 는 그대로 전파.
    - ``notify-failure`` 는 allow-list 에 없으므로 자체 실패 시에도 재귀
      알림을 발송하지 않는다 (알림 채널 실패 상황에서 알림을 다시 보내면 무한 루프).
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
        if command_name in _NOTIFY_FAILURE_COMMANDS:
            _safe_notify_failure(None, f"{command_name} 실패: {exc}")
        logger.error("예외 발생", exc_info=True)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
