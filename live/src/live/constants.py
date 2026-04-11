"""live 도메인 상수 정의.

- 포트폴리오 식별자: Q-2-2XS 전략 고정 (`LIVE_PORTFOLIO_ID`)
- DRIFT 임계값: 0~3% 정상 / 3~5% 주의 / 5%+ 보정 필요 (설계서 14장)
- 경로 기본값: qbt-live-state 프라이빗 리포 내부 구조 (CLI 에서 실제 경로를 파라미터로 전달)
- applied_fill_ids 정리 주기: 90일 (설계서 6.2)
- signal→trade 매핑 빌더: QBT 코어 `PORTFOLIO_CONFIGS` 에서 동적으로 파생하여 SSoT 유지

설계서: ``docs/DESIGN_QBT_LIVE_FINAL.md`` 부록 B, 5.1, 14장.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from qbt.backtest.portfolio_configs import get_portfolio_config
from qbt.backtest.portfolio_types import PortfolioConfig

# ============================================================================
# 포트폴리오 식별자
# ============================================================================

# 실매매 대상 포트폴리오 실험 식별자.
# QBT 코어 PORTFOLIO_CONFIGS 에 존재해야 하며, 전략 변경 시 이 상수만 업데이트한다.
# Q-2-2XS: SSO 35% / QLD 35% / GLD 15% B&H / TLT 15% B&H
LIVE_PORTFOLIO_ID: Final[str] = "portfolio_q2_2xs"


# ============================================================================
# 스키마 버전 / 타임존
# ============================================================================

# LiveState JSON 직렬화 스키마 버전. 포맷 변경 시 증가시킨다.
SCHEMA_VERSION: Final[int] = 1

# 타임스탬프 표기용 타임존 이름 (설계서 12장).
KST_TZ_NAME: Final[str] = "Asia/Seoul"


# ============================================================================
# DRIFT 임계값 (비율, 0~1)
# ============================================================================

# drift % 가 이 값 이상이면 "주의" 수준 (설계서 14장: 3~5% 주의).
DRIFT_WARNING_RATIO: Final[float] = 0.03

# drift % 가 이 값 이상이면 "보정 필요" 수준 (설계서 14장: 5%+ 보정 필요).
DRIFT_CORRECTION_RATIO: Final[float] = 0.05


# ============================================================================
# 파일 시스템 기본 경로 / 파일명
# ============================================================================

# 프라이빗 상태 리포의 원격 HTTPS URL.
# CLI 는 매 실행마다 이 리포를 tempdir 에 shallow clone 한 뒤 작업한다.
STATE_REPO_URL: Final[str] = "https://github.com/ingbeen/qbt-live-state.git"

# 프라이빗 상태 리포의 기본 디렉토리명 (ephemeral tempdir 내부 이름).
DEFAULT_LIVE_STATE_DIR: Final[Path] = Path("qbt-live-state")

# 주가 CSV 가 저장되는 하위 디렉토리.
DEFAULT_DATA_STOCK_SUBDIR: Final[Path] = Path("data/stock")

# LiveState JSON 파일명.
DEFAULT_LIVE_STATE_FILENAME: Final[str] = "live_state.json"

# applied_fill_ids JSON 파일명.
DEFAULT_APPLIED_FILL_IDS_FILENAME: Final[str] = "applied_fill_ids.json"


# ============================================================================
# fill idempotency
# ============================================================================

# applied_fill_ids 에서 이 일수 이상 경과한 ID 를 자동 정리한다 (설계서 6.2).
APPLIED_FILL_IDS_MAX_AGE_DAYS: Final[int] = 90


# ============================================================================
# 헬퍼 함수
# ============================================================================


def get_live_portfolio_config() -> PortfolioConfig:
    """실매매 대상 포트폴리오 설정을 QBT 코어에서 조회한다.

    SSoT 원칙: 포트폴리오 구성은 ``qbt.backtest.portfolio_configs`` 가 정본이다.

    Returns:
        Q-2-2XS PortfolioConfig 인스턴스.

    Raises:
        ValueError: ``LIVE_PORTFOLIO_ID`` 가 QBT PORTFOLIO_CONFIGS 에 존재하지 않을 때.
    """
    return get_portfolio_config(LIVE_PORTFOLIO_ID)


def build_signal_trade_map() -> dict[str, str]:
    """signal 티커 → trade 티커 매핑을 QBT Q-2-2XS 슬롯에서 빌드한다.

    AssetSlotConfig 의 signal_data_path 및 trade_data_path 는 ``{TICKER}_max.csv``
    형식을 따른다. 각 경로의 파일명에서 첫 ``_`` 이전 부분을 티커로 사용한다.

    Q-2-2XS 예시:
        - SPY → SSO
        - QQQ → QLD
        - GLD → GLD
        - TLT → TLT

    Returns:
        ``{signal_ticker: trade_ticker}`` 형태의 새 dict (호출마다 독립 사본).

    Raises:
        RuntimeError: Q-2-2XS config 의 경로에서 티커를 추출할 수 없을 때
            (내부 불변조건 위반).
    """
    config = get_live_portfolio_config()
    mapping: dict[str, str] = {}
    for slot in config.asset_slots:
        signal_ticker = _extract_ticker_from_path(slot.signal_data_path)
        trade_ticker = _extract_ticker_from_path(slot.trade_data_path)
        mapping[signal_ticker] = trade_ticker
    return mapping


def _extract_ticker_from_path(path: Path) -> str:
    """경로 파일명에서 티커 기호를 추출한다 (``{TICKER}_...`` 규칙).

    Args:
        path: CSV 경로 (예: ``storage/stock/SPY_max.csv``).

    Returns:
        대문자 티커 기호 (예: ``"SPY"``).

    Raises:
        RuntimeError: 파일명에 ``_`` 구분자가 없어 티커를 추출할 수 없을 때.
    """
    stem = path.stem
    if "_" not in stem:
        raise RuntimeError(f"내부 불변조건 위반: CSV 파일명에서 티커를 추출할 수 없음. path={path}")
    ticker = stem.split("_", 1)[0]
    return ticker.upper()
