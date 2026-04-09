"""포트폴리오 백테스트 실험 설정

정의된 실험을 PortfolioConfig 인스턴스로 구현한다.

실험 목적:
- D 시리즈: 단일 자산 비교군 (QQQ 100%)
- F 시리즈: SPY + TQQQ + GLD + TLT (레버리지 혼합, B&H 변형)
- Q 시리즈: TQQQ->QQQ 교체 (합성 데이터 제거) + 2x 레버리지 변형
"""

from pathlib import Path

from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL
from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.common_constants import (
    GLD_DATA_PATH,
    PORTFOLIO_RESULTS_DIR,
    QLD_DATA_PATH,
    QQQ_DATA_PATH,
    SPY_DATA_PATH,
    SSO_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
    UBT_DATA_PATH,
    UGL_DATA_PATH,
)


def _make_result_dir(experiment_name: str) -> Path:
    """실험명 기반 결과 저장 디렉토리를 반환한다."""
    return PORTFOLIO_RESULTS_DIR / experiment_name


# ============================================================================
# 포트폴리오 실험 설정 정의
# ============================================================================

# D-1: QQQ 단일 자산 (버퍼존 100%, 비교군) -- QQQ 100%
_CONFIG_D1 = PortfolioConfig(
    experiment_name="portfolio_d1",
    display_name="D-1 (QQQ 100%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QQQ_DATA_PATH,
            target_weight=1.00,
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_d1"),
)

# F-6H: SPY 30% / TQQQ 30% / GLD 20%(B&H) / TLT 20%(B&H)
_CONFIG_F6H = PortfolioConfig(
    experiment_name="portfolio_f6h",
    display_name="F-6H (SPY 30% / TQQQ 30% / GLD 20%(B&H) / TLT 20%(B&H))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.30,
        ),
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.30,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.20,
            strategy_id="buy_and_hold",  # GLD: B&H
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.20,
            strategy_id="buy_and_hold",  # TLT: B&H
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_f6h"),
)

# ============================================================================
# Q 시리즈: TQQQ->QQQ 교체 (합성 데이터 제거) + 방어 비중 민감도
# F-6H 구조에서 TQQQ를 QQQ로 교체하여 실데이터만 사용.
# GLD/TLT는 B&H 유지 (F 시리즈 결론 적용).
# ============================================================================

# Q-2: SPY 35% / QQQ 35% / GLD 15%(B&H) / TLT 15%(B&H) -- 방어 축소, 수익 확대
_CONFIG_Q2 = PortfolioConfig(
    experiment_name="portfolio_q2",
    display_name="Q-2 (SPY 35% / QQQ 35% / GLD 15%(B&H) / TLT 15%(B&H))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QQQ_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_q2"),
)

# Q-2-2X: Q-2의 2배 레버리지 버전 -- SSO 35% / QLD 35% / UGL 15%(B&H) / UBT 15%(B&H)
_CONFIG_Q2_2X = PortfolioConfig(
    experiment_name="portfolio_q2_2x",
    display_name="Q-2-2X (SSO 35% / QLD 35% / UGL 15%(B&H) / UBT 15%(B&H))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="sso",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SSO_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="qld",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QLD_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="ugl",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=UGL_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
        AssetSlotConfig(
            asset_id="ubt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=UBT_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_q2_2x"),
)

# Q-2-2XH: Q-2-2X에서 UGL/UBT도 버퍼존 적용 (전 자산 버퍼존, 1x 시그널 기반)
_CONFIG_Q2_2XH = PortfolioConfig(
    experiment_name="portfolio_q2_2xh",
    display_name="Q-2-2XH (SSO 35% / QLD 35% / UGL 15% / UBT 15%) 전 자산 버퍼존",
    asset_slots=(
        AssetSlotConfig(
            asset_id="sso",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SSO_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="qld",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QLD_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="ugl",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=UGL_DATA_PATH,
            target_weight=0.15,
        ),
        AssetSlotConfig(
            asset_id="ubt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=UBT_DATA_PATH,
            target_weight=0.15,
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_q2_2xh"),
)

# ============================================================================
# 공개 컬렉션 및 함수
# ============================================================================

PORTFOLIO_CONFIGS: list[PortfolioConfig] = [
    _CONFIG_D1,
    _CONFIG_F6H,
    _CONFIG_Q2,
    _CONFIG_Q2_2X,
    _CONFIG_Q2_2XH,
]


def get_portfolio_config(experiment_name: str) -> PortfolioConfig:
    """실험명으로 PortfolioConfig를 조회한다.

    Args:
        experiment_name: 실험 식별자 (예: "portfolio_d1")

    Returns:
        해당 PortfolioConfig 인스턴스

    Raises:
        ValueError: PORTFOLIO_CONFIGS에 없는 실험명인 경우
    """
    for config in PORTFOLIO_CONFIGS:
        if config.experiment_name == experiment_name:
            return config

    available = [c.experiment_name for c in PORTFOLIO_CONFIGS]
    raise ValueError(f"실험명을 찾을 수 없습니다: {experiment_name!r} " f"(사용 가능: {available})")
