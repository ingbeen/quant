"""live 도메인 상수 정의.

- 포트폴리오 식별자: 실매매 대상 PORTFOLIO_CONFIGS 키 (`LIVE_PORTFOLIO_ID`)
- DRIFT 임계값: ``DRIFT_WARNING_RATIO`` / ``DRIFT_CORRECTION_RATIO``
- 경로 기본값: qbt-live-state 프라이빗 리포 내부 구조
  (CLI 에서 실제 경로를 파라미터로 전달)
- idempotency 원장 자동 정리 주기 / history 파일명 / 출력 정밀도
- signal→trade 매핑 빌더: QBT 코어 ``PORTFOLIO_CONFIGS`` 에서 동적으로 파생하여
  SSoT 유지
- 티커 추출 유틸(:func:`extract_ticker_from_path`): live 도메인 내 유일한 티커
  추출 경로. 중복 재구현 금지.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

from qbt.backtest.portfolio_configs import get_portfolio_config
from qbt.backtest.portfolio_types import PortfolioConfig

# ============================================================================
# 포트폴리오 식별자
# ============================================================================

# 실매매 대상 포트폴리오 실험 식별자.
# QBT 코어 PORTFOLIO_CONFIGS 에 존재해야 하며, 전략을 바꾸려면 이 상수만 업데이트한다.
# 포트폴리오 구성(자산 / 비중 / 전략 유형) 자체는 QBT 코어 ``portfolio_configs`` 가
# 유일 정본이므로 본 파일에서는 구성 상세를 기재하지 않는다 (문서 내구성).
LIVE_PORTFOLIO_ID: Final[str] = "portfolio_q2_2xs"


# ============================================================================
# 스키마 버전 / 타임존
# ============================================================================

# LiveState JSON 직렬화 스키마 버전. 포맷 변경 시 증가시킨다.
SCHEMA_VERSION: Final[int] = 3

# 타임스탬프 표기용 타임존 이름 (state / history / 커밋 메시지 공통).
KST_TZ_NAME: Final[str] = "Asia/Seoul"

# live 도메인의 KST 타임존 객체 단일 정본. datetime.now(KST_TIMEZONE) 로 사용한다.
KST_TIMEZONE: Final[ZoneInfo] = ZoneInfo(KST_TZ_NAME)


# ============================================================================
# DRIFT 임계값 (비율, 0~1)
# ============================================================================

# drift 비율이 이 값 이상이면 "주의" 수준으로 분류.
DRIFT_WARNING_RATIO: Final[float] = 0.03

# drift 비율이 이 값 이상이면 "보정 필요" 수준으로 분류.
DRIFT_CORRECTION_RATIO: Final[float] = 0.05


# ============================================================================
# 파일 시스템 기본 경로 / 파일명
# ============================================================================

# 프라이빗 상태 리포의 원격 HTTPS URL.
# CLI 는 매 실행마다 이 리포를 tempdir 에 shallow clone 한 뒤 작업한다.
STATE_REPO_URL: Final[str] = "https://github.com/ingbeen/qbt-live-state.git"

# Firebase Cloud Storage 정본 버킷 이름.
# CLI 는 매 실행마다 이 버킷의 모든 blob 을 tempdir 로 download 한 뒤 작업한다
# (storage_gateway.state_workspace).
STATE_BUCKET_NAME: Final[str] = "qbt-live.firebasestorage.app"

# 프라이빗 상태 리포의 기본 디렉토리명 (ephemeral tempdir 내부 이름).
DEFAULT_LIVE_STATE_DIR: Final[Path] = Path("qbt-live-state")

# 주가 CSV 가 저장되는 하위 디렉토리.
DEFAULT_DATA_STOCK_SUBDIR: Final[Path] = Path("data/stock")

# LiveState JSON 파일명.
DEFAULT_LIVE_STATE_FILENAME: Final[str] = "live_state.json"

# applied_fill_ids JSON 파일명.
DEFAULT_APPLIED_FILL_IDS_FILENAME: Final[str] = "applied_fill_ids.json"

# applied_balance_adjust_ids JSON 파일명 (자산 직접 보정 idempotency 원장).
DEFAULT_APPLIED_BALANCE_ADJUST_IDS_FILENAME: Final[str] = "applied_balance_adjust_ids.json"


# ============================================================================
# history 파일 이름 / 하위 디렉토리 (qbt-live-state/history/ 내부)
# ============================================================================

# 일별 상세 로그(``{date}.json``) 가 저장되는 서브디렉토리 이름.
HISTORY_DAILY_SUBDIR: Final[str] = "daily"

# 일별 ``live_state.json`` 스냅샷(``{date}.json``) 이 저장되는 서브디렉토리 이름.
# run-daily 종료 시점의 LiveState 전체를 날짜 키 파일로 보존하여, 과거 시점의 상태를
# git log 파싱 없이 직접 조회할 수 있게 한다. 같은 날 재실행 시 덮어쓴다 (영구 보존).
HISTORY_STATES_SUBDIR: Final[str] = "states"

# 일별 요약 append-only 파일 (1 줄당 1 일).
HISTORY_SUMMARY_FILENAME: Final[str] = "summary.jsonl"

# 사용자 체결 입력 audit append-only 파일 (차트 마커 원본).
HISTORY_USER_TRADES_FILENAME: Final[str] = "user_trades.jsonl"

# 신호 이력 append-only 파일 (차트 마커 원본).
HISTORY_SIGNALS_FILENAME: Final[str] = "signals.jsonl"

# 자산 직접 보정(balance_adjust) audit append-only 파일.
HISTORY_BALANCE_ADJUSTS_FILENAME: Final[str] = "balance_adjusts.jsonl"

# 체결 스킵(fill_dismiss) audit append-only 파일.
HISTORY_FILL_DISMISSES_FILENAME: Final[str] = "fill_dismisses.jsonl"


# ============================================================================
# 출력 정밀도
# ============================================================================

# 반올림 상수는 qbt.backtest.constants 의 ROUND_* 를 직접 사용한다.
# live 독자 상수를 정의하지 않고, qbt 것을 적극 재사용하는 원칙.


# ============================================================================
# 기타 기본값
# ============================================================================

# yfinance 에서 최근 OHLCV 를 조회할 때 기본 일수 (``fetch_recent_ohlc`` 용).
DEFAULT_RECENT_FETCH_DAYS: Final[int] = 5

# 텔레그램 Bot API 호출 시 HTTP 타임아웃 (초).
TELEGRAM_TIMEOUT_SECONDS: Final[int] = 10

# ``cli.py`` history 커맨드에서 --tail 의 기본값.
DEFAULT_HISTORY_TAIL_LINES: Final[int] = 10


# ============================================================================
# 알림 제목 / Git 봇 정보
# ============================================================================

# FCM / 텔레그램 알림 제목 (일일 리포트 + 실패 알림 공통).
NOTIFICATION_TITLE: Final[str] = "QBT Live"

# ephemeral state repo commit 시 사용하는 Git 사용자 정보.
GIT_BOT_NAME: Final[str] = "qbt-live-bot"
GIT_BOT_EMAIL: Final[str] = "qbt-live-bot@noreply.github.com"


# ============================================================================
# idempotency ledger 자동 정리 주기
# ============================================================================

# applied_fill_ids / applied_balance_adjust_ids 에서 이 일수 이상 경과한 ID 를
# 자동 정리한다. 두 원장 모두 동일 주기를 사용한다.
APPLIED_FILL_IDS_MAX_AGE_DAYS: Final[int] = 90


# ============================================================================
# 외부 서비스 / 인프라 상수
# ============================================================================

# Firebase RTDB 기본 URL (Admin SDK 초기화 시 사용).
FIREBASE_DB_URL: Final[str] = "https://qbt-live-default-rtdb.asia-southeast1.firebasedatabase.app"

# exchange_calendars NYSE 달력 코드.
NYSE_CALENDAR_CODE: Final[str] = "XNYS"

# GitHub Actions / 로컬 .env 에서 공급되는 환경변수 키 모음.
FIREBASE_CRED_ENV_KEY: Final[str] = "GOOGLE_APPLICATION_CREDENTIALS"
TELEGRAM_TOKEN_ENV_KEY: Final[str] = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ENV_KEY: Final[str] = "TELEGRAM_CHAT_ID"
STATE_REPO_PAT_ENV_KEY: Final[str] = "STATE_REPO_PAT"


# ============================================================================
# 데이터 검증 임계값
# ============================================================================

# 전일 종가 차이율 임계값 (비율, 0~1). CSV 마지막 종가 vs yfinance 재조회 종가의
# 차이가 이 값 이상이면 스플릿 / 무상증자 / 사용자 수동 조작이 의심되므로
# ``data_validator.validate_prev_close`` 가 에러로 취급한다.
PREV_CLOSE_DIFF_THRESHOLD: Final[float] = 0.01


# ============================================================================
# Intent 타입 집합 (signal_state 매핑 및 일반 검증용)
# ============================================================================

# ENTER_TO_TARGET / INCREASE_TO_TARGET 은 매수 방향 intent.
BUY_INTENT_TYPES: Final[frozenset[str]] = frozenset({"ENTER_TO_TARGET", "INCREASE_TO_TARGET"})

# EXIT_ALL / REDUCE_TO_TARGET 은 매도 방향 intent.
SELL_INTENT_TYPES: Final[frozenset[str]] = frozenset({"EXIT_ALL", "REDUCE_TO_TARGET"})


# ============================================================================
# 헬퍼 함수
# ============================================================================


def get_live_portfolio_config() -> PortfolioConfig:
    """실매매 대상 포트폴리오 설정을 QBT 코어에서 조회한다.

    SSoT 원칙: 포트폴리오 구성은 ``qbt.backtest.portfolio_configs`` 가 정본이다.

    Returns:
        ``LIVE_PORTFOLIO_ID`` 에 해당하는 ``PortfolioConfig`` 인스턴스.

    Raises:
        ValueError: ``LIVE_PORTFOLIO_ID`` 가 QBT PORTFOLIO_CONFIGS 에 존재하지 않을 때.
    """
    return get_portfolio_config(LIVE_PORTFOLIO_ID)


def build_signal_trade_map() -> dict[str, str]:
    """signal 티커 → trade 티커 매핑을 live 포트폴리오 슬롯에서 빌드한다.

    각 슬롯의 ``signal_data_path`` / ``trade_data_path`` 파일명에서 첫 ``_`` 이전
    부분을 티커로 사용한다 (``{TICKER}_*.csv`` 규칙).

    Returns:
        ``{signal_ticker: trade_ticker}`` 형태의 새 dict (호출마다 독립 사본).

    Raises:
        RuntimeError: config 의 경로에서 티커를 추출할 수 없을 때
            (내부 불변조건 위반).
    """
    config = get_live_portfolio_config()
    mapping: dict[str, str] = {}
    for slot in config.asset_slots:
        signal_ticker = extract_ticker_from_path(slot.signal_data_path)
        trade_ticker = extract_ticker_from_path(slot.trade_data_path)
        mapping[signal_ticker] = trade_ticker
    return mapping


def build_asset_signal_ticker_map() -> dict[str, str]:
    """asset_id → signal 티커 매핑을 live 포트폴리오 슬롯에서 빌드한다.

    MA 근접도 등 signal 데이터 기반 지표를 표시할 때, asset_id(sso, qld) 대신
    실제 signal 티커(SPY, QQQ)를 사용하기 위한 매핑이다.

    Returns:
        ``{asset_id: signal_ticker}`` 형태의 새 dict (호출마다 독립 사본).
        예: ``{"sso": "SPY", "qld": "QQQ", "gld": "GLD", "tlt": "TLT"}``

    Raises:
        RuntimeError: config 의 경로에서 티커를 추출할 수 없을 때
            (내부 불변조건 위반).
    """
    config = get_live_portfolio_config()
    mapping: dict[str, str] = {}
    for slot in config.asset_slots:
        signal_ticker = extract_ticker_from_path(slot.signal_data_path)
        mapping[slot.asset_id] = signal_ticker
    return mapping


def live_csv_path(state_dir: Path, ticker: str) -> Path:
    """qbt-live-state 리포 내 주가 CSV 파일 경로를 반환한다.

    live 도메인 내 주가 CSV 경로 규칙은 본 함수 한 곳에서 관리한다. 파일명 규칙이
    바뀔 경우 이 함수만 수정하면 된다.

    Args:
        state_dir: qbt-live-state 작업 디렉토리 (ephemeral clone 루트).
        ticker: 티커 기호 (대/소문자 무관, 파일명에는 그대로 사용).

    Returns:
        ``{state_dir}/data/stock/{TICKER}.csv`` 경로.
    """
    return state_dir / DEFAULT_DATA_STOCK_SUBDIR / f"{ticker}.csv"


def extract_ticker_from_path(path: Path) -> str:
    """경로 파일명에서 티커 기호를 추출한다 (``{TICKER}_...`` 규칙).

    live 도메인의 모든 티커 추출은 본 함수를 거쳐야 한다. 규칙이 바뀌면 한 곳만
    수정하면 되도록 SSoT 로 운영한다.

    Args:
        path: CSV 경로 (예: ``storage/stock/SPY_max.csv``).

    Returns:
        대문자 티커 기호 (예: ``"SPY"``).

    Raises:
        RuntimeError: 파일명에 ``_`` 구분자가 없어 티커를 추출할 수 없을 때
            (내부 불변조건 위반).
    """
    stem = path.stem
    if "_" not in stem:
        raise RuntimeError(f"내부 불변조건 위반: CSV 파일명에서 티커를 추출할 수 없음. path={path}")
    ticker = stem.split("_", 1)[0]
    return ticker.upper()
