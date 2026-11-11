"""포트폴리오 백테스트 실험 설정

정의된 실험을 PortfolioConfig 인스턴스로 구현한다.

실험 목적:
- QQQ B&H: 매매 규칙 없이 QQQ 100% 를 사서 보유하는 기준점
- D 시리즈: 단일 자산 비교군 (QQQ 100%)
- Q 시리즈: SPY/QQQ + 방어자산(GLD·TLT) 혼합. 주식 구간을 1x · 2x · 3x 레버리지로 교체하여
  수익·위험 프로필을 비교한다. 운용은 2x 칸 일부를 1x 보유로 바꾼 Q-2-2XS-H20 이다.
"""

from pathlib import Path

from qbt.backtest.constants import DEFAULT_INITIAL_CAPITAL
from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.common_constants import (
    GLD_SYNTHETIC_DATA_PATH,
    PORTFOLIO_RESULTS_DIR,
    QLD_SYNTHETIC_DATA_PATH,
    QQQ_SYNTHETIC_DATA_PATH,
    SPY_SYNTHETIC_DATA_PATH,
    SSO_SYNTHETIC_DATA_PATH,
    TLT_SYNTHETIC_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
    UPRO_SYNTHETIC_DATA_PATH,
)


def _make_result_dir(experiment_name: str) -> Path:
    """실험명 기반 결과 저장 디렉토리를 반환한다."""
    return PORTFOLIO_RESULTS_DIR / experiment_name


# ============================================================================
# 포트폴리오 실험 설정 정의
# 실물 파일이 하나라도 섞이면 시작일이 그 상장일로 줄어듦 → 슬롯은 모두 합성 시세 (docs/research/백테스트_기간_연장.md 결정 10)
# ============================================================================

# QQQ B&H: QQQ 100% 매수 후 보유 (매매 규칙 없는 기준점) -- 같은 자산을 버퍼존으로 매매하는 D-1 과 같은 시작일 정책
_CONFIG_QQQ_BH = PortfolioConfig(
    experiment_name="portfolio_qqq_bh",
    display_name="QQQ B&H (QQQ 100% 보유)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_SYNTHETIC_DATA_PATH,
            trade_data_path=QQQ_SYNTHETIC_DATA_PATH,
            target_weight=1.00,
            strategy_id="buy_and_hold",
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_qqq_bh"),
)

# D-1: QQQ 단일 자산 (버퍼존 100%, 비교군) -- QQQ 100%
_CONFIG_D1 = PortfolioConfig(
    experiment_name="portfolio_d1",
    display_name="D-1 (QQQ 100%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_SYNTHETIC_DATA_PATH,
            trade_data_path=QQQ_SYNTHETIC_DATA_PATH,
            target_weight=1.00,
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_d1"),
)

# ============================================================================
# Q 시리즈: SPY/QQQ 주식 + 방어자산(GLD·TLT, B&H) 혼합
# 주식 구간을 1x(Q-2) · 2x(Q-2-2XS) · 3x(Q-2-3XS)로 교체하여 비교한다.
# ============================================================================

# Q-2: SPY 35% / QQQ 35% / GLD 15%(B&H) / TLT 15%(B&H) -- 1x 주식 + 방어자산 B&H
_CONFIG_Q2 = PortfolioConfig(
    experiment_name="portfolio_q2",
    display_name="Q-2 (SPY 35% / QQQ 35% / GLD 15%(B&H) / TLT 15%(B&H))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_SYNTHETIC_DATA_PATH,
            trade_data_path=SPY_SYNTHETIC_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_SYNTHETIC_DATA_PATH,
            trade_data_path=QQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_SYNTHETIC_DATA_PATH,
            trade_data_path=GLD_SYNTHETIC_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_SYNTHETIC_DATA_PATH,
            trade_data_path=TLT_SYNTHETIC_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_q2"),
)

# Q-2-2XS: 주식만 2x, 방어자산 1x B&H -- 비교 실험, 운용은 Q-2-2XS-H20 (docs/research/전략_검증_보고서.md 부록 O · R)
_CONFIG_Q2_2XS = PortfolioConfig(
    experiment_name="portfolio_q2_2xs",
    display_name="Q-2-2XS (SSO 35% / QLD 35% / GLD 15%(B&H) / TLT 15%(B&H))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="sso",
            signal_data_path=SPY_SYNTHETIC_DATA_PATH,
            trade_data_path=SSO_SYNTHETIC_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="qld",
            signal_data_path=QQQ_SYNTHETIC_DATA_PATH,
            trade_data_path=QLD_SYNTHETIC_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_SYNTHETIC_DATA_PATH,
            trade_data_path=GLD_SYNTHETIC_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_SYNTHETIC_DATA_PATH,
            trade_data_path=TLT_SYNTHETIC_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_q2_2xs"),
)

# Q-2-3XS: Q-2-2XS 에서 주식 칸의 매매 상품만 3x -- 신호는 그대로 1x (비교 실험)
_CONFIG_Q2_3XS = PortfolioConfig(
    experiment_name="portfolio_q2_3xs",
    display_name="Q-2-3XS (UPRO 35% / TQQQ 35% / GLD 15%(B&H) / TLT 15%(B&H))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="upro",
            signal_data_path=SPY_SYNTHETIC_DATA_PATH,
            trade_data_path=UPRO_SYNTHETIC_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_SYNTHETIC_DATA_PATH,
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_SYNTHETIC_DATA_PATH,
            trade_data_path=GLD_SYNTHETIC_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_SYNTHETIC_DATA_PATH,
            trade_data_path=TLT_SYNTHETIC_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_q2_3xs"),
)

# Q-2-2XS-H20: Q-2-2XS 의 2x 칸을 25% 씩으로 줄이고 SPY · QQQ 1x B&H 10% 씩 -- 운용 포트폴리오
# 1x 보유 비중은 1986 ~ 2026 구간별 수익이 가장 고르게 나온 쪽에서 고름 (docs/research/전략_검증_보고서.md 부록 R)
_CONFIG_Q2_2XS_H20 = PortfolioConfig(
    experiment_name="portfolio_q2_2xs_h20",
    display_name="Q-2-2XS-H20 (SSO 25% / QLD 25% / SPY 10%(B&H) / QQQ 10%(B&H) / GLD 15%(B&H) / TLT 15%(B&H))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="sso",
            signal_data_path=SPY_SYNTHETIC_DATA_PATH,
            trade_data_path=SSO_SYNTHETIC_DATA_PATH,
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="qld",
            signal_data_path=QQQ_SYNTHETIC_DATA_PATH,
            trade_data_path=QLD_SYNTHETIC_DATA_PATH,
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_SYNTHETIC_DATA_PATH,
            trade_data_path=SPY_SYNTHETIC_DATA_PATH,
            target_weight=0.10,
            strategy_id="buy_and_hold",
        ),
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_SYNTHETIC_DATA_PATH,
            trade_data_path=QQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.10,
            strategy_id="buy_and_hold",
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_SYNTHETIC_DATA_PATH,
            trade_data_path=GLD_SYNTHETIC_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_SYNTHETIC_DATA_PATH,
            trade_data_path=TLT_SYNTHETIC_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",
        ),
    ),
    total_capital=DEFAULT_INITIAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_q2_2xs_h20"),
)

# ============================================================================
# 공개 컬렉션 및 함수
# ============================================================================

PORTFOLIO_CONFIGS: list[PortfolioConfig] = [
    _CONFIG_QQQ_BH,
    _CONFIG_D1,
    _CONFIG_Q2,
    _CONFIG_Q2_2XS,
    _CONFIG_Q2_3XS,
    _CONFIG_Q2_2XS_H20,
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
