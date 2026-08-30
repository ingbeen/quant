"""포트폴리오 백테스트 실험 설정

정의된 실험을 PortfolioConfig 인스턴스로 구현한다.

실험 목적:
- D 시리즈: 단일 자산 비교군 (QQQ 100%)
- Q 시리즈: SPY/QQQ + 방어자산(GLD·TLT) 혼합. 주식 구간을 1x 또는 2x 레버리지로 교체하여
  수익·위험 프로필을 비교한다.
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

# ============================================================================
# Q 시리즈: SPY/QQQ 주식 + 방어자산(GLD·TLT, B&H) 혼합
# 주식 구간을 1x(Q-2) 또는 2x(Q-2-2XS)로 교체하여 비교한다.
# ============================================================================

# Q-2: SPY 35% / QQQ 35% / GLD 15%(B&H) / TLT 15%(B&H) -- 1x 주식 + 방어자산 B&H
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

# Q-2-2XS: 주식만 2x, 방어자산 1x B&H -- SSO 35% / QLD 35% / GLD 15%(B&H) / TLT 15%(B&H)
_CONFIG_Q2_2XS = PortfolioConfig(
    experiment_name="portfolio_q2_2xs",
    display_name="Q-2-2XS (SSO 35% / QLD 35% / GLD 15%(B&H) / TLT 15%(B&H))",
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
    result_dir=_make_result_dir("portfolio_q2_2xs"),
)

# Q-2-2XS sell10: Q-2-2XS 와 동일하되 주식 슬롯의 매도 버퍼만 10% (부록 G.7.2 쟁점 검증용 대조군)
_CONFIG_Q2_2XS_SELL10 = PortfolioConfig(
    experiment_name="portfolio_q2_2xs_sell10",
    display_name="Q-2-2XS sell10 (주식 슬롯 매도버퍼 10%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="sso",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SSO_DATA_PATH,
            target_weight=0.35,
            sell_buffer_zone_pct=0.10,
        ),
        AssetSlotConfig(
            asset_id="qld",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QLD_DATA_PATH,
            target_weight=0.35,
            sell_buffer_zone_pct=0.10,
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
    result_dir=_make_result_dir("portfolio_q2_2xs_sell10"),
)

# ============================================================================
# 공개 컬렉션 및 함수
# ============================================================================

PORTFOLIO_CONFIGS: list[PortfolioConfig] = [
    _CONFIG_D1,
    _CONFIG_Q2,
    _CONFIG_Q2_2XS,
    _CONFIG_Q2_2XS_SELL10,
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
