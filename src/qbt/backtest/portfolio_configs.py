"""포트폴리오 백테스트 실험 설정

정의돈 실험을 PortfolioConfig 인스턴스로 구현한다.

실험 목적:
- A 시리즈: TQQQ 없는 기본 분산 포트폴리오 (QQQ/SPY/GLD) — 주식:금 비율 탐색
- B 시리즈: TQQQ 소량 포함 + 현금 버퍼 (분산 효과 비교)
- C-1: QQQ+TQQQ만 (레버리지 기준선, 분산 없음)
- D 시리즈: 단일 자산 비교군 (QQQ 100%, TQQQ 100%)
- E 시리즈: SPY + GLD + TLT (레버리지 없음, TLT 순효과 측정)
- F 시리즈: SPY + TQQQ + GLD + TLT (레버리지 혼합)
- G 시리즈: SPY/GLD/TLT 구성 고정 + 버퍼존 vs B&H 팩토리얼 (기여도 격리)
- H 시리즈: TQQQ 60% 집중 + 방어 자산 조합
"""

from pathlib import Path

from qbt.backtest.portfolio_types import AssetSlotConfig, PortfolioConfig
from qbt.common_constants import (
    GLD_DATA_PATH,
    PORTFOLIO_RESULTS_DIR,
    QQQ_DATA_PATH,
    SPY_DATA_PATH,
    TLT_DATA_PATH,
    TQQQ_SYNTHETIC_DATA_PATH,
)

# ============================================================================
# 공통 포트폴리오 설정 기본값
# ============================================================================

_DEFAULT_TOTAL_CAPITAL = 10_000_000.0


def _make_result_dir(experiment_name: str) -> Path:
    """실험명 기반 결과 저장 디렉토리를 반환한다."""
    return PORTFOLIO_RESULTS_DIR / experiment_name


# ============================================================================
# 포트폴리오 실험 설정 정의
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
    result_dir=_make_result_dir("portfolio_a1"),
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
    result_dir=_make_result_dir("portfolio_a2"),
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
    result_dir=_make_result_dir("portfolio_a3"),
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
    result_dir=_make_result_dir("portfolio_b1"),
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
    result_dir=_make_result_dir("portfolio_b2"),
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
    result_dir=_make_result_dir("portfolio_b3"),
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
    result_dir=_make_result_dir("portfolio_c1"),
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
    result_dir=_make_result_dir("portfolio_d1"),
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
    result_dir=_make_result_dir("portfolio_d2"),
)

# ============================================================================
# E 시리즈: SPY + GLD + TLT (레버리지 없음, TLT 순효과 측정)
# 전 자산 버퍼존 전략 적용. GLD+TLT 합산 ≤ 40%.
# ============================================================================

# E-1: SPY 60% / GLD 25% / TLT 15% (균등 방어)
_CONFIG_E1 = PortfolioConfig(
    experiment_name="portfolio_e1",
    display_name="E-1 (SPY 60% / GLD 25% / TLT 15%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.15,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_e1"),
)

# E-2: SPY 60% / GLD 20% / TLT 20% (GLD:TLT 1:1)
_CONFIG_E2 = PortfolioConfig(
    experiment_name="portfolio_e2",
    display_name="E-2 (SPY 60% / GLD 20% / TLT 20%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.20,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.20,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_e2"),
)

# E-3: SPY 60% / GLD 30% / TLT 10% (GLD 우위)
_CONFIG_E3 = PortfolioConfig(
    experiment_name="portfolio_e3",
    display_name="E-3 (SPY 60% / GLD 30% / TLT 10%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.30,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.10,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_e3"),
)

# E-4: SPY 70% / GLD 20% / TLT 10% (주식 비중 70%)
_CONFIG_E4 = PortfolioConfig(
    experiment_name="portfolio_e4",
    display_name="E-4 (SPY 70% / GLD 20% / TLT 10%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.70,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.20,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.10,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_e4"),
)

# E-5: SPY 80% / GLD 15% / TLT 5% (주식 비중 80%, 방어 자산 최소화)
_CONFIG_E5 = PortfolioConfig(
    experiment_name="portfolio_e5",
    display_name="E-5 (SPY 80% / GLD 15% / TLT 5%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.80,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.15,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.05,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_e5"),
)

# ============================================================================
# F 시리즈: SPY + TQQQ + GLD + TLT (레버리지 혼합)
# 전 자산 버퍼존 전략 적용. GLD+TLT 합산 = 40%.
# 유효 주식 노출 = SPY×1 + TQQQ×3
# ============================================================================

# F-1: SPY 40% / TQQQ 20% / GLD 25% / TLT 15% (유효 주식 노출 100%)
_CONFIG_F1 = PortfolioConfig(
    experiment_name="portfolio_f1",
    display_name="F-1 (SPY 40% / TQQQ 20% / GLD 25% / TLT 15%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.40,
        ),
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.20,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.15,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_f1"),
)

# F-2: SPY 30% / TQQQ 30% / GLD 25% / TLT 15% (유효 주식 노출 120%)
_CONFIG_F2 = PortfolioConfig(
    experiment_name="portfolio_f2",
    display_name="F-2 (SPY 30% / TQQQ 30% / GLD 25% / TLT 15%)",
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
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.15,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_f2"),
)

# F-3: SPY 40% / TQQQ 20% / GLD 30% / TLT 10% (GLD 비중 증가, 유효 주식 노출 100%)
_CONFIG_F3 = PortfolioConfig(
    experiment_name="portfolio_f3",
    display_name="F-3 (SPY 40% / TQQQ 20% / GLD 30% / TLT 10%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.40,
        ),
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.20,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.30,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.10,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_f3"),
)

# F-4: SPY 20% / TQQQ 40% / GLD 25% / TLT 15% (유효 주식 노출 140%)
_CONFIG_F4 = PortfolioConfig(
    experiment_name="portfolio_f4",
    display_name="F-4 (SPY 20% / TQQQ 40% / GLD 25% / TLT 15%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.20,
        ),
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.40,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.15,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_f4"),
)

# ============================================================================
# G 시리즈: SPY/GLD/TLT 구성 고정, 전략만 변경 (버퍼존 vs B&H 팩토리얼)
# 구성: SPY(버퍼존) 60% / GLD 25% / TLT 15%
# GLD·TLT에 적용하는 전략(버퍼존/strategy_id)만 변경하는 2×2 팩토리얼 설계.
# strategy_id="buy_and_hold": 버퍼존 매도 신호 무시, 항상 투자 상태 유지
# ============================================================================

# G-1: 전부 버퍼존 (E-1과 동일 구성, G 시리즈 비교 기준선)
_CONFIG_G1 = PortfolioConfig(
    experiment_name="portfolio_g1",
    display_name="G-1 (SPY 60%(버퍼존) / GLD 25%(버퍼존) / TLT 15%(버퍼존))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.15,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_g1"),
)

# G-2: GLD B&H (SPY 버퍼존 / GLD strategy_id=buy_and_hold / TLT 버퍼존)
_CONFIG_G2 = PortfolioConfig(
    experiment_name="portfolio_g2",
    display_name="G-2 (SPY 60%(버퍼존) / GLD 25%(B&H) / TLT 15%(버퍼존))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.25,
            strategy_id="buy_and_hold",  # GLD: B&H (버퍼존 매도 신호 무시)
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.15,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_g2"),
)

# G-3: TLT B&H (SPY 버퍼존 / GLD 버퍼존 / TLT strategy_id=buy_and_hold)
_CONFIG_G3 = PortfolioConfig(
    experiment_name="portfolio_g3",
    display_name="G-3 (SPY 60%(버퍼존) / GLD 25%(버퍼존) / TLT 15%(B&H))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.25,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",  # TLT: B&H (버퍼존 매도 신호 무시)
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_g3"),
)

# G-4: GLD+TLT 모두 B&H (SPY 버퍼존 / GLD strategy_id=buy_and_hold / TLT strategy_id=buy_and_hold)
_CONFIG_G4 = PortfolioConfig(
    experiment_name="portfolio_g4",
    display_name="G-4 (SPY 60%(버퍼존) / GLD 25%(B&H) / TLT 15%(B&H))",
    asset_slots=(
        AssetSlotConfig(
            asset_id="spy",
            signal_data_path=SPY_DATA_PATH,
            trade_data_path=SPY_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.25,
            strategy_id="buy_and_hold",  # GLD: B&H (버퍼존 매도 신호 무시)
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.15,
            strategy_id="buy_and_hold",  # TLT: B&H (버퍼존 매도 신호 무시)
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_g4"),
)

# ============================================================================
# H 시리즈: TQQQ 60% 집중 + 방어 자산 조합
# 전 자산 버퍼존 전략 적용. GLD+TLT 합산 = 40%.
# ============================================================================

# H-1: TQQQ 60% / GLD 20% / TLT 20% (균등 방어)
_CONFIG_H1 = PortfolioConfig(
    experiment_name="portfolio_h1",
    display_name="H-1 (TQQQ 60% / GLD 20% / TLT 20%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.20,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.20,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_h1"),
)

# H-2: TQQQ 60% / GLD 40% (GLD 집중)
_CONFIG_H2 = PortfolioConfig(
    experiment_name="portfolio_h2",
    display_name="H-2 (TQQQ 60% / GLD 40%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="gld",
            signal_data_path=GLD_DATA_PATH,
            trade_data_path=GLD_DATA_PATH,
            target_weight=0.40,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_h2"),
)

# H-3: TQQQ 60% / TLT 40% (TLT 집중)
_CONFIG_H3 = PortfolioConfig(
    experiment_name="portfolio_h3",
    display_name="H-3 (TQQQ 60% / TLT 40%)",
    asset_slots=(
        AssetSlotConfig(
            asset_id="tqqq",
            signal_data_path=QQQ_DATA_PATH,  # TQQQ는 QQQ 시그널 사용
            trade_data_path=TQQQ_SYNTHETIC_DATA_PATH,
            target_weight=0.60,
        ),
        AssetSlotConfig(
            asset_id="tlt",
            signal_data_path=TLT_DATA_PATH,
            trade_data_path=TLT_DATA_PATH,
            target_weight=0.40,
        ),
    ),
    total_capital=_DEFAULT_TOTAL_CAPITAL,
    result_dir=_make_result_dir("portfolio_h3"),
)

# ============================================================================
# 공개 컬렉션 및 함수
# ============================================================================

PORTFOLIO_CONFIGS: list[PortfolioConfig] = [
    # A 시리즈: QQQ/SPY/GLD 주식:금 비율 탐색
    _CONFIG_A1,
    _CONFIG_A2,
    _CONFIG_A3,
    # B 시리즈: TQQQ 소량 편입 + 현금 버퍼
    _CONFIG_B1,
    _CONFIG_B2,
    _CONFIG_B3,
    # C 시리즈: 분산 없는 레버리지 기준선
    _CONFIG_C1,
    # D 시리즈: 단일 자산 기준선
    _CONFIG_D1,
    _CONFIG_D2,
    # E 시리즈: SPY + GLD + TLT (TLT 순효과 측정)
    _CONFIG_E1,
    _CONFIG_E2,
    _CONFIG_E3,
    _CONFIG_E4,
    _CONFIG_E5,
    # F 시리즈: SPY + TQQQ + GLD + TLT (레버리지 혼합)
    _CONFIG_F1,
    _CONFIG_F2,
    _CONFIG_F3,
    _CONFIG_F4,
    # G 시리즈: 버퍼존 vs B&H 팩토리얼 (기여도 격리)
    _CONFIG_G1,
    _CONFIG_G2,
    _CONFIG_G3,
    _CONFIG_G4,
    # H 시리즈: TQQQ 60% + 방어 자산 조합
    _CONFIG_H1,
    _CONFIG_H2,
    _CONFIG_H3,
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
