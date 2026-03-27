"""포트폴리오 리밸런싱 정책 — 이중 트리거 리밸런싱 정책과 월 첫 거래일 판정 함수"""

from dataclasses import dataclass
from datetime import date

from qbt.backtest.engines.portfolio_planning import OrderIntent, ProjectedPortfolio
from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.common_constants import EPSILON


@dataclass(frozen=True)
class RebalancePolicy:
    """이중 트리거 리밸런싱 정책.

    monthly_threshold_rate와 daily_threshold_rate를 기반으로
    리밸런싱 발동 여부를 판단하고 intent를 생성한다.

    Attributes:
        monthly_threshold_rate: 월 첫 거래일 리밸런싱 임계값 (0.10 = 10%)
        daily_threshold_rate: 매일 긴급 리밸런싱 임계값 (0.20 = 20%)
    """

    monthly_threshold_rate: float
    daily_threshold_rate: float

    def get_threshold(self, is_month_start: bool) -> float:
        """is_month_start에 따라 적용할 리밸런싱 임계값을 반환한다.

        Args:
            is_month_start: True이면 월 첫 거래일

        Returns:
            월 첫 거래일이면 monthly_threshold_rate, 그 외이면 daily_threshold_rate
        """
        return self.monthly_threshold_rate if is_month_start else self.daily_threshold_rate

    def should_rebalance(
        self,
        projected: ProjectedPortfolio,
        slot_dict: dict[str, AssetSlotConfig],
        total_equity_projected: float,
        is_month_start: bool,
    ) -> bool:
        """active 자산 중 임계값 초과 자산이 있는지 판정한다.

        Args:
            projected: signal intents 반영 후 예상 포트폴리오 상태
            slot_dict: {asset_id: AssetSlotConfig} (target_weight 참조용)
            total_equity_projected: projected 상태 기준 총 에쿼티
            is_month_start: True이면 monthly_threshold_rate 사용, False이면 daily_threshold_rate 사용

        Returns:
            True이면 리밸런싱 실행 필요, False이면 스킵
        """
        if total_equity_projected < EPSILON:
            return False
        threshold = self.get_threshold(is_month_start)
        for asset_id in projected.active_assets:
            slot = slot_dict.get(asset_id)
            if slot is None or slot.target_weight == 0:
                continue
            current_amount = projected.projected_amounts.get(asset_id, 0.0)
            actual_weight = current_amount / total_equity_projected
            deviation = abs(actual_weight / slot.target_weight - 1.0)
            if deviation > threshold:
                return True
        return False

    def build_rebalance_intents(
        self,
        projected: ProjectedPortfolio,
        slot_dict: dict[str, AssetSlotConfig],
        total_equity_projected: float,
        current_date: date,
    ) -> dict[str, OrderIntent]:
        """projected 상태 기반으로 리밸런싱 intent를 생성한다.

        threshold 체크 없이 항상 intent를 생성한다.
        should_rebalance()가 True인 경우에만 호출해야 한다.

        1. active_assets 전체에 대해 REDUCE_TO_TARGET / INCREASE_TO_TARGET 생성
        2. scale_factor: projected_cash + 예상 매도 수익 기준 매수 가능액 계산

        Args:
            projected: ProjectedPortfolio (signal intents 반영 후 예상 상태)
            slot_dict: {asset_id: AssetSlotConfig} (target_weight 참조용)
            total_equity_projected: projected 상태 기준 총 에쿼티
            current_date: 현재 날짜 (OrderIntent.reason 기록용)

        Returns:
            {asset_id: OrderIntent}
        """
        if total_equity_projected < EPSILON:
            return {}

        # 1. active_assets 전체에 대해 매도/매수 금액 계산
        sell_intents: dict[str, float] = {}  # {asset_id: 매도 필요 금액}
        buy_intents: dict[str, float] = {}  # {asset_id: 매수 필요 금액}

        for asset_id in projected.active_assets:
            slot = slot_dict.get(asset_id)
            if slot is None:
                continue
            target_amount = total_equity_projected * slot.target_weight
            current_amount = projected.projected_amounts.get(asset_id, 0.0)
            delta = target_amount - current_amount
            if delta < 0:
                sell_intents[asset_id] = abs(delta)
            elif delta > 0:
                buy_intents[asset_id] = delta

        # 2. 현금 부족 시 scale_factor 비례 축소
        estimated_sell_proceeds = sum(sell_intents.values())
        available_cash = projected.projected_cash + estimated_sell_proceeds
        total_buy_needed = sum(buy_intents.values())

        if total_buy_needed > available_cash and total_buy_needed > EPSILON:
            scale_factor = available_cash / total_buy_needed
            buy_intents = {aid: amt * scale_factor for aid, amt in buy_intents.items()}

        # 3. OrderIntent 생성
        result: dict[str, OrderIntent] = {}

        for asset_id, excess_value in sell_intents.items():
            slot = slot_dict[asset_id]
            current_amount = projected.projected_amounts.get(asset_id, 0.0)
            target_amount = total_equity_projected * slot.target_weight
            result[asset_id] = OrderIntent(
                asset_id=asset_id,
                intent_type="REDUCE_TO_TARGET",
                current_amount=current_amount,
                target_amount=target_amount,
                delta_amount=-excess_value,
                target_weight=slot.target_weight,
                reason=f"rebalance {current_date}",
            )

        for asset_id, buy_amount in buy_intents.items():
            slot = slot_dict[asset_id]
            current_amount = projected.projected_amounts.get(asset_id, 0.0)
            target_amount = total_equity_projected * slot.target_weight
            result[asset_id] = OrderIntent(
                asset_id=asset_id,
                intent_type="INCREASE_TO_TARGET",
                current_amount=current_amount,
                target_amount=target_amount,
                delta_amount=buy_amount,
                target_weight=slot.target_weight,
                reason=f"rebalance {current_date}",
            )

        return result


# 기본 리밸런싱 정책 인스턴스
# 월 첫 거래일: 편차 10% 초과 시 트리거 (정기 리밸런싱)
# 매일: 편차 20% 초과 시 긴급 트리거
DEFAULT_REBALANCE_POLICY = RebalancePolicy(
    monthly_threshold_rate=0.10,
    daily_threshold_rate=0.20,
)


def is_first_trading_day_of_month(trade_dates: list[date], i: int) -> bool:
    """월 첫 거래일 여부를 판정한다.

    Args:
        trade_dates: 전체 거래일 목록
        i: 현재 인덱스 (0-based)

    Returns:
        True이면 이전 거래일과 월이 다름 (= 월 첫 거래일)
        False이면 i=0이거나 동일 월
    """
    if i <= 0:
        return False
    return trade_dates[i].month != trade_dates[i - 1].month
