"""포트폴리오 백테스트 실험 설정

PLAN_portfolio_experiment.md에 정의된 7가지 실험(A-1~A-3, B-1~B-3, C-1)을
PortfolioConfig 인스턴스로 구현한다.

실험 목적:
- A 시리즈: TQQQ 없는 기본 분산 포트폴리오 (QQQ/SPY/GLD)
- B 시리즈: TQQQ 소량 포함 + 현금 버퍼 (분산 효과 비교)
- C-1: QQQ+TQQQ만 (레버리지 기준선, 분산 없음)
"""

from pathlib import Path

from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.common_constants import (
    GLD_DATA_PATH,
    PORTFOLIO_RESULTS_DIR,
    QQQ_DATA_PATH,
    SPY_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)

# ============================================================================
# 전 자산 공통 4P 파라미터 (PLAN_portfolio_experiment.md §4.1)
# ============================================================================

_DEFAULT_MA_WINDOW = 200
_DEFAULT_BUY_BUFFER = 0.03  # 매수 버퍼존 비율 (0.03 = 3%)
_DEFAULT_SELL_BUFFER = 0.05  # 매도 버퍼존 비율 (0.05 = 5%)
_DEFAULT_HOLD_DAYS = 3
_DEFAULT_MA_TYPE = "ema"
_DEFAULT_REBALANCE_THRESHOLD = 0.20  # 상대 리밸런싱 임계값 (0.20 = ±20%)
_DEFAULT_TOTAL_CAPITAL = 10_000_000.0


def _make_result_dir(experiment_name: str) -> Path:
    """실험명 기반 결과 저장 디렉토리를 반환한다."""
    return PORTFOLIO_RESULTS_DIR / experiment_name


# ============================================================================
# 7가지 실험 설정 정의
# ============================================================================

# A-1: 역변동성 근사 (참고용) — QQQ 25% / SPY 25% / GLD 50%
_CONFIG_A1 = PortfolioConfig(
    experiment_name="portfolio_a1",
    display_name="A-1 (QQQ 25% / SPY 25% / GLD 50%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QQQ_DATA_PATH,
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.50,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD,
    result_dir=_make_result_dir("portfolio_a1"),
    ma_window=_DEFAULT_MA_WINDOW,
    buy_buffer_zone_pct=_DEFAULT_BUY_BUFFER,
    sell_buffer_zone_pct=_DEFAULT_SELL_BUFFER,
    hold_days=_DEFAULT_HOLD_DAYS,
    ma_type=_DEFAULT_MA_TYPE,
)

# A-2: 60:40 전통 배분 (기본, 사전 결정) — QQQ 30% / SPY 30% / GLD 40%
_CONFIG_A2 = PortfolioConfig(
    experiment_name="portfolio_a2",
    display_name="A-2 (QQQ 30% / SPY 30% / GLD 40%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QQQ_DATA_PATH,
            target_weight=0.30,
        ),
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.30,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.40,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD,
    result_dir=_make_result_dir("portfolio_a2"),
    ma_window=_DEFAULT_MA_WINDOW,
    buy_buffer_zone_pct=_DEFAULT_BUY_BUFFER,
    sell_buffer_zone_pct=_DEFAULT_SELL_BUFFER,
    hold_days=_DEFAULT_HOLD_DAYS,
    ma_type=_DEFAULT_MA_TYPE,
)

# A-3: 공격적 구성 (민감도 확인) — QQQ 35% / SPY 35% / GLD 30%
_CONFIG_A3 = PortfolioConfig(
    experiment_name="portfolio_a3",
    display_name="A-3 (QQQ 35% / SPY 35% / GLD 30%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QQQ_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.35,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.30,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD,
    result_dir=_make_result_dir("portfolio_a3"),
    ma_window=_DEFAULT_MA_WINDOW,
    buy_buffer_zone_pct=_DEFAULT_BUY_BUFFER,
    sell_buffer_zone_pct=_DEFAULT_SELL_BUFFER,
    hold_days=_DEFAULT_HOLD_DAYS,
    ma_type=_DEFAULT_MA_TYPE,
)

# B-1: TQQQ 소량(7%) + 현금 14% — QQQ 19.5% / TQQQ 7% / SPY 19.5% / GLD 40%
# target_weight 합 = 0.86 → 현금 14% 자동 확보
_CONFIG_B1 = PortfolioConfig(
    experiment_name="portfolio_b1",
    display_name="B-1 (QQQ 19.5% / TQQQ 7% / SPY 19.5% / GLD 40% / 현금 14%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QQQ_DATA_PATH,
            target_weight=0.195,
        ),
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.07,
        ),
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.195,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.40,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD,
    result_dir=_make_result_dir("portfolio_b1"),
    ma_window=_DEFAULT_MA_WINDOW,
    buy_buffer_zone_pct=_DEFAULT_BUY_BUFFER,
    sell_buffer_zone_pct=_DEFAULT_SELL_BUFFER,
    hold_days=_DEFAULT_HOLD_DAYS,
    ma_type=_DEFAULT_MA_TYPE,
)

# B-2: TQQQ 증가(12%) + 현금 24% — QQQ 12% / TQQQ 12% / SPY 12% / GLD 40%
# target_weight 합 = 0.76 → 현금 24% 자동 확보
_CONFIG_B2 = PortfolioConfig(
    experiment_name="portfolio_b2",
    display_name="B-2 (QQQ 12% / TQQQ 12% / SPY 12% / GLD 40% / 현금 24%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QQQ_DATA_PATH,
            target_weight=0.12,
        ),
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.12,
        ),
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.12,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.40,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD,
    result_dir=_make_result_dir("portfolio_b2"),
    ma_window=_DEFAULT_MA_WINDOW,
    buy_buffer_zone_pct=_DEFAULT_BUY_BUFFER,
    sell_buffer_zone_pct=_DEFAULT_SELL_BUFFER,
    hold_days=_DEFAULT_HOLD_DAYS,
    ma_type=_DEFAULT_MA_TYPE,
)

# B-3: 현금 없이 전액 투자 — QQQ 15% / TQQQ 15% / SPY 30% / GLD 40%
# target_weight 합 = 1.0 → 현금 없음
_CONFIG_B3 = PortfolioConfig(
    experiment_name="portfolio_b3",
    display_name="B-3 (QQQ 15% / TQQQ 15% / SPY 30% / GLD 40%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QQQ_DATA_PATH,
            target_weight=0.15,
        ),
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.15,
        ),
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.30,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.40,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD,
    result_dir=_make_result_dir("portfolio_b3"),
    ma_window=_DEFAULT_MA_WINDOW,
    buy_buffer_zone_pct=_DEFAULT_BUY_BUFFER,
    sell_buffer_zone_pct=_DEFAULT_SELL_BUFFER,
    hold_days=_DEFAULT_HOLD_DAYS,
    ma_type=_DEFAULT_MA_TYPE,
)

# C-1: QQQ+TQQQ만 (레버리지만, 분산 없음) — QQQ 50% / TQQQ 50%
# target_weight 합 = 1.0 → 전액 투자, 분산 없음
_CONFIG_C1 = PortfolioConfig(
    experiment_name="portfolio_c1",
    display_name="C-1 (QQQ 50% / TQQQ 50%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="qqq",
            signal_data_path=QQQ_DATA_PATH,
            trade_data_path=QQQ_DATA_PATH,
            target_weight=0.50,
        ),
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.50,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD,
    result_dir=_make_result_dir("portfolio_c1"),
    ma_window=_DEFAULT_MA_WINDOW,
    buy_buffer_zone_pct=_DEFAULT_BUY_BUFFER,
    sell_buffer_zone_pct=_DEFAULT_SELL_BUFFER,
    hold_days=_DEFAULT_HOLD_DAYS,
    ma_type=_DEFAULT_MA_TYPE,
)

# D-1: QQQ 단일 자산 (버퍼존 100%, 비교군) — QQQ 100%
# target_weight 합 = 1.0 → 전액 투자, 분산 없음
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
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD,
    result_dir=_make_result_dir("portfolio_d1"),
    ma_window=_DEFAULT_MA_WINDOW,
    buy_buffer_zone_pct=_DEFAULT_BUY_BUFFER,
    sell_buffer_zone_pct=_DEFAULT_SELL_BUFFER,
    hold_days=_DEFAULT_HOLD_DAYS,
    ma_type=_DEFAULT_MA_TYPE,
)

# D-2: TQQQ 단일 자산 (버퍼존 100%, 비교군) — TQQQ 100%
# target_weight 합 = 1.0 → 전액 투자, 분산 없음
_CONFIG_D2 = PortfolioConfig(
    experiment_name="portfolio_d2",
    display_name="D-2 (TQQQ 100%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=1.00,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    rebalance_threshold_rate=_DEFAULT_REBALANCE_THRESHOLD,
    result_dir=_make_result_dir("portfolio_d2"),
    ma_window=_DEFAULT_MA_WINDOW,
    buy_buffer_zone_pct=_DEFAULT_BUY_BUFFER,
    sell_buffer_zone_pct=_DEFAULT_SELL_BUFFER,
    hold_days=_DEFAULT_HOLD_DAYS,
    ma_type=_DEFAULT_MA_TYPE,
)

# ============================================================================
# 공개 컬렉션 및 함수
# ============================================================================

PORTFOLIO_CONFIGS: list[PortfolioConfig] = [
    _CONFIG_A1,
    _CONFIG_A2,
    _CONFIG_A3,
    _CONFIG_B1,
    _CONFIG_B2,
    _CONFIG_B3,
    _CONFIG_C1,
    _CONFIG_D1,
    _CONFIG_D2,
]


def get_portfolio_config(experiment_name: str) -> PortfolioConfig:
    """실험명으로 PortfolioConfig를 조회한다.

    Args:
        experiment_name: 실험 식별자 (예: "portfolio_a2")

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
