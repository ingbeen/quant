"""포트폴리오 리밸런싱 정책 — 월말 판단 리밸런싱 정책과 판단일(월 마지막 거래일) 판정 함수"""

from dataclasses import dataclass
from datetime import date

from qbt.backtest.engines.portfolio_planning import OrderIntent, ProjectedPortfolio
from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.common_constants import EPSILON


@dataclass(frozen=True)
class RebalancePolicy:
    """월말 판단 리밸런싱 정책.

    판단일(월 마지막 거래일)인지는 엔진이 `is_last_trading_day_of_month` 로 정하고,
    이 정책은 판단일에 리밸런싱이 필요한지(편차)와 intent 생성만 맡는다.

    Attributes:
        threshold_rate: 목표 비중 대비 상대 편차 임계값 (0.10 = 10%)
    """

    threshold_rate: float

    def should_rebalance(
        self,
        projected: ProjectedPortfolio,
        slot_dict: dict[str, AssetSlotConfig],
        total_equity_projected: float,
    ) -> bool:
        """active 자산 중 임계값 초과 자산이 있는지 판정한다.

        Args:
            projected: signal intents 반영 후 예상 포트폴리오 상태
            slot_dict: {asset_id: AssetSlotConfig} (target_weight 참조용)
            total_equity_projected: projected 상태 기준 총 에쿼티

        Returns:
            True이면 리밸런싱 실행 필요, False이면 스킵
        """
        if total_equity_projected < EPSILON:
            raise RuntimeError(
                f"내부 불변조건 위반: total_equity_projected < EPSILON "
                f"(비레버리지 포트폴리오에서 총 에쿼티 소멸 불가, total_equity_projected={total_equity_projected})"
            )
        # active_assets 는 asset_states 키의 부분집합이며 asset_states 는 slot_dict 와
        # 동일한 자산 집합으로 초기화되므로 slot_dict[asset_id] 는 항상 존재한다.
        for asset_id in projected.active_assets:
            slot = slot_dict[asset_id]
            if slot.target_weight == 0:
                continue
            current_amount = projected.projected_amounts.get(asset_id, 0.0)
            actual_weight = current_amount / total_equity_projected
            deviation = abs(actual_weight / slot.target_weight - 1.0)
            if deviation > self.threshold_rate:
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
            raise RuntimeError(
                f"내부 불변조건 위반: total_equity_projected < EPSILON "
                f"(비레버리지 포트폴리오에서 총 에쿼티 소멸 불가, total_equity_projected={total_equity_projected})"
            )

        # 1. active_assets 전체에 대해 매도/매수 금액 계산
        sell_intents: dict[str, float] = {}  # {asset_id: 매도 필요 금액}
        buy_intents: dict[str, float] = {}  # {asset_id: 매수 필요 금액}

        # active_assets ⊆ slot_dict.keys() 가 항상 성립한다 (should_rebalance 동일 가정).
        for asset_id in projected.active_assets:
            slot = slot_dict[asset_id]
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
# 월 마지막 거래일 종가에 편차 10% 초과 자산이 있으면 다음 거래일 시가에 리밸런싱한다.
# 평일 긴급 리밸런싱은 두지 않는다 — 실제 운용(월말 종가 확인 → 다음 달 첫 시가에 한 번)과 맞추기 위해서다.
# 결정 근거와 측정값: docs/research/전략_검증_보고서.md 부록 L
DEFAULT_REBALANCE_POLICY = RebalancePolicy(threshold_rate=0.10)


def is_last_trading_day_of_month(trade_dates: list[date], i: int) -> bool:
    """리밸런싱 판단일(그 달의 마지막 거래일) 여부를 판정한다.

    다음 거래일의 «날짜»(거래소 달력)만 보고 가격은 보지 않으므로 미래 참조가 아니다.
    마지막 행은 체결할 다음 거래일이 없으므로 False 다.

    Args:
        trade_dates: 전체 거래일 목록
        i: 현재 인덱스 (0-based)

    Returns:
        True이면 다음 거래일과 월이 다름 (= 그 달의 마지막 거래일)
    """
    if i >= len(trade_dates) - 1:
        return False
    return trade_dates[i + 1].month != trade_dates[i].month
