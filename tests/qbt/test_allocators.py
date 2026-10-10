"""보완 전략 배분 규칙 테스트

HAA · 미국 약세 감지 로테이션 · EWY 200일선 배분 규칙의 계약을 검증한다.
판단 규칙, 판단 시점, 미래 참조 금지, 설정 검증, 엔진에 올렸을 때의 정합성을 다룬다.

왜 중요한가요?
배분 규칙은 매매법의 목표 비중을 정한다. 순위 · 피신 조건 · 신호 시점이 한 군데만 어긋나도
그리드 전체의 통과 · 탈락 판정이 조용히 바뀐다.
"""

import math
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.allocator_registry import ALLOCATOR_REGISTRY
from qbt.backtest.allocators.ewy_buffer_zone import EWY_ASSET_IDS, EwyBufferZoneAllocator
from qbt.backtest.allocators.haa import HAA_ASSET_IDS, HAA_SERIES_IDS, HaaAllocator
from qbt.backtest.allocators.us_weakness_rotation import (
    ROTATION_ASSET_IDS,
    ROTATION_SERIES_IDS,
    UsWeaknessRotationAllocator,
)
from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import ma_col_name
from qbt.backtest.engines.portfolio_engine import run_portfolio_backtest
from qbt.backtest.portfolio_types import (
    AllocationAssetConfig,
    AllocatorMethodConfig,
    AssetSlotConfig,
    PortfolioConfig,
    SignalSeriesConfig,
    SlotMethodConfig,
)
from qbt.backtest.portfolio_validation import validate_portfolio_result
from qbt.backtest.strategies.buffer_zone import BufferZoneStrategy
from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME, EPSILON

_DUMMY = Path("dummy")

# ============================================================================
# 공통 헬퍼
# ============================================================================


def _weekdays(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _month_weekdays(year: int, month: int) -> list[date]:
    first = date(year, month, 1)
    next_first = date(year + month // 12, month % 12 + 1, 1)
    return _weekdays(first, next_first - timedelta(days=1))


def _df(dates: list[date], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: closes,
            COL_HIGH: [c * 1.001 for c in closes],
            COL_LOW: [c * 0.999 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1_000_000] * len(dates),
        }
    )


def _monthly_df(month_closes: list[float]) -> pd.DataFrame:
    """2020-01 부터 달마다 평일 종가가 month_closes[m] 로 일정한 시세."""
    dates: list[date] = []
    closes: list[float] = []
    for m, close in enumerate(month_closes):
        days = _month_weekdays(2020 + m // 12, m % 12 + 1)
        dates += days
        closes += [close] * len(days)
    return _df(dates, closes)


def _haa_data(scores: dict[str, float], months: int = 14) -> dict[str, pd.DataFrame]:
    """마지막 달 종가만 100 × (1 + 점수), 그 전 달은 100 인 시세 — 1 · 3 · 6 · 12개월 수익률이 모두 그 점수다."""
    return {
        key: _monthly_df([100.0] * (months - 1) + [100.0 * (1.0 + scores.get(key, 0.0))])
        for key in (*HAA_ASSET_IDS, *HAA_SERIES_IDS)
    }


def _last_row(data: dict[str, pd.DataFrame]) -> int:
    return len(next(iter(data.values()))) - 1


def _haa_weights(scores: dict[str, float]) -> dict[str, float]:
    data = _haa_data(scores)
    result = HaaAllocator().target_weights(data, _last_row(data), date(2021, 2, 26), True)
    assert result is not None
    return dict(result)


_OFFENSIVE_DESCENDING = {
    "spy": 0.10,
    "iwm": 0.09,
    "vea": 0.08,
    "vwo": 0.07,
    "vnq": 0.06,
    "pdbc": 0.05,
    "ief": 0.04,
    "tlt": 0.03,
}


def _method(allocator_id: str, asset_ids: tuple[str, ...], series_ids: tuple[str, ...]) -> AllocatorMethodConfig:
    return AllocatorMethodConfig(
        "cand",
        "Candidate",
        1.0,
        tuple(AllocationAssetConfig(asset_id, _DUMMY, _DUMMY) for asset_id in asset_ids),
        allocator_id=allocator_id,
        signal_series=tuple(SignalSeriesConfig(series_id, _DUMMY) for series_id in series_ids),
    )


# ============================================================================
# HAA
# ============================================================================


class TestHaaScores:
    """점수 = 달력 월말 종가 기준 1 · 3 · 6 · 12개월 수익률의 평균."""

    def test_score_is_mean_of_month_end_returns(self) -> None:
        """
        목적: 점수가 1 · 3 · 6 · 12개월 전 월말 종가로 계산한 수익률의 평균이다

        Given: 14개월 시세, 마지막 달 100 · 1개월 전 80 · 3개월 전 50 · 6개월 전 200 · 12개월 전 125
        When: momentum_scores (마지막 달의 마지막 거래일)
        Then: (0.25 + 1.0 − 0.5 − 0.2) ÷ 4 = 0.1375
        """
        # Given
        data = _haa_data({})
        month_closes = [100.0] * 14
        month_closes[12], month_closes[10], month_closes[7], month_closes[1] = 80.0, 50.0, 200.0, 125.0
        data["spy"] = _monthly_df(month_closes)

        # When
        scores = HaaAllocator().momentum_scores(data, _last_row(data))

        # Then
        assert scores is not None
        assert scores["spy"] == pytest.approx(0.1375, abs=EPSILON)

    def test_fewer_than_twelve_past_month_ends_returns_none(self) -> None:
        """
        목적: 이전 월말이 12개 안 되면 점수를 낼 수 없다

        Given: 12개월 시세 (마지막 달 앞의 월말 11개)
        When: momentum_scores · target_weights (판단일)
        Then: 둘 다 None
        """
        # Given
        data = _haa_data({"tip": 0.05}, months=12)
        allocator = HaaAllocator()

        # When / Then
        assert allocator.momentum_scores(data, _last_row(data)) is None
        assert allocator.target_weights(data, _last_row(data), date(2020, 12, 31), True) is None


class TestHaaRules:
    """카나리아 피신 · 상위 4개 · 음수 자리 방어 · 방어 자산 선택."""

    @pytest.mark.parametrize("tip_score", [0.0, -0.05])
    def test_canary_non_positive_goes_all_defensive(self, tip_score: float) -> None:
        """
        목적: TIP 점수가 0 이하면 방어 자산 100%

        Given: 공격 자산 점수는 모두 양수, TIP 점수 0 또는 음수, BIL 점수 > IEF 점수
        When: target_weights
        Then: BIL 1.0, 나머지 0
        """
        # When
        weights = _haa_weights({**_OFFENSIVE_DESCENDING, "ief": 0.01, "bil": 0.02, "tip": tip_score})

        # Then
        assert weights["bil"] == pytest.approx(1.0, abs=EPSILON)
        assert sum(weights.values()) == pytest.approx(1.0, abs=EPSILON)

    def test_top_four_equal_weight(self) -> None:
        """
        목적: TIP 점수가 양수면 공격 자산 점수 상위 4개에 25% 씩

        Given: 공격 점수 SPY > IWM > VEA > VWO > … , TIP 양수
        When: target_weights
        Then: SPY · IWM · VEA · VWO 0.25, 나머지 0
        """
        # When
        weights = _haa_weights({**_OFFENSIVE_DESCENDING, "bil": 0.001, "tip": 0.05})

        # Then
        expected = {key: 0.0 for key in HAA_ASSET_IDS} | {"spy": 0.25, "iwm": 0.25, "vea": 0.25, "vwo": 0.25}
        assert weights == pytest.approx(expected, abs=EPSILON)

    def test_negative_score_in_top_four_goes_defensive(self) -> None:
        """
        목적: 상위 4개 중 점수가 음수인 자리만 방어 자산으로 바꾼다

        Given: 공격 점수 SPY 0.10 · IWM 0.05 · 나머지 음수, 방어는 BIL(점수 > IEF)
        When: target_weights
        Then: SPY 0.25 · IWM 0.25 · BIL 0.50
        """
        # Given
        scores = {"spy": 0.10, "iwm": 0.05, "vea": -0.01, "vwo": -0.02, "vnq": -0.03, "pdbc": -0.04}
        scores |= {"ief": -0.05, "tlt": -0.06, "bil": 0.001, "tip": 0.05}

        # When
        weights = _haa_weights(scores)

        # Then
        expected = {key: 0.0 for key in HAA_ASSET_IDS} | {"spy": 0.25, "iwm": 0.25, "bil": 0.50}
        assert weights == pytest.approx(expected, abs=EPSILON)

    def test_ief_as_offensive_and_defensive_adds_up(self) -> None:
        """
        목적: IEF 가 상위 4개이면서 방어 자산이면 비중이 합쳐진다

        Given: 공격 점수 SPY 0.10 · IEF 0.09 · IWM 0.08 · VEA −0.01(4위), BIL 점수 < IEF 점수
        When: target_weights
        Then: SPY 0.25 · IWM 0.25 · IEF 0.50
        """
        # Given
        scores = {"spy": 0.10, "ief": 0.09, "iwm": 0.08, "vea": -0.01, "vwo": -0.02, "vnq": -0.03}
        scores |= {"pdbc": -0.04, "tlt": -0.05, "bil": -0.02, "tip": 0.05}

        # When
        weights = _haa_weights(scores)

        # Then
        expected = {key: 0.0 for key in HAA_ASSET_IDS} | {"spy": 0.25, "iwm": 0.25, "ief": 0.50}
        assert weights == pytest.approx(expected, abs=EPSILON)

    def test_ties_follow_list_order(self) -> None:
        """
        목적: 점수가 같으면 공격 자산은 목록 순서(SPY · IWM · VEA · VWO …), 방어는 IEF 가 앞이다

        Given: 공격 점수 모두 0.05 / TIP 음수이고 IEF · BIL 점수가 같음
        When: target_weights
        Then: SPY · IWM · VEA · VWO 0.25 / IEF 1.0
        """
        # When
        all_equal = _haa_weights({key: 0.05 for key in _OFFENSIVE_DESCENDING} | {"bil": 0.0, "tip": 0.05})
        defensive_tie = _haa_weights({**_OFFENSIVE_DESCENDING, "ief": 0.02, "bil": 0.02, "tip": -0.01})

        # Then
        top_four = {key: 0.0 for key in HAA_ASSET_IDS} | {"spy": 0.25, "iwm": 0.25, "vea": 0.25, "vwo": 0.25}
        assert all_equal == pytest.approx(top_four, abs=EPSILON)
        assert defensive_tie["ief"] == pytest.approx(1.0, abs=EPSILON)

    def test_weights_cover_all_assets_and_sum_to_one(self) -> None:
        """
        목적: 비중은 9개 자산을 모두 담고 합이 1 이다

        Given: 일반적인 점수
        When: target_weights
        Then: 키 = HAA 자산 9개, 합 1
        """
        # When
        weights = _haa_weights({**_OFFENSIVE_DESCENDING, "bil": 0.001, "tip": 0.05})

        # Then
        assert set(weights) == set(HAA_ASSET_IDS)
        assert sum(weights.values()) == pytest.approx(1.0, abs=EPSILON)


class TestHaaTiming:
    """판단일에만 판단하고, 미래 행을 읽지 않는다."""

    def test_not_check_day_returns_none(self) -> None:
        """
        목적: 판단일(월 마지막 거래일)이 아니면 목표를 바꾸지 않는다

        Given: 점수를 낼 수 있는 시세
        When: target_weights(is_check_day=False)
        Then: None
        """
        # Given
        data = _haa_data({**_OFFENSIVE_DESCENDING, "tip": 0.05})

        # When / Then
        assert HaaAllocator().target_weights(data, _last_row(data), date(2021, 2, 26), False) is None

    def test_future_rows_do_not_change_decision(self) -> None:
        """
        목적: i 행 뒤의 시세를 바꿔도 i 행의 판단이 같다 (미래 참조 금지)

        Given: 15개월 시세, i = 14번째 달(2021-02)의 마지막 거래일. 다른 시세는 마지막 달 종가만 크게 바꿈
        When: 두 시세로 각각 새 규칙을 만들어 i 행 판단
        Then: 판단이 같다
        """
        # Given
        scores = {**_OFFENSIVE_DESCENDING, "bil": 0.001, "tip": 0.05}
        base = {
            key: _monthly_df([100.0] * 13 + [100.0 * (1.0 + scores.get(key, 0.0))] + [100.0])
            for key in (*HAA_ASSET_IDS, *HAA_SERIES_IDS)
        }
        changed = {key: df.copy() for key, df in base.items()}
        i = len(base["spy"]) - len(_month_weekdays(2021, 3)) - 1
        for key, df in changed.items():
            future = df.index > i
            df.loc[future, [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]] = 1.0 if key == "tip" else 500.0

        # When
        expected = HaaAllocator().target_weights(base, i, date(2021, 2, 26), True)
        actual = HaaAllocator().target_weights(changed, i, date(2021, 2, 26), True)

        # Then
        assert expected is not None
        assert actual == pytest.approx(dict(expected), abs=EPSILON)


# ============================================================================
# 미국 약세 감지 로테이션
# ============================================================================


def _rotation_data(ratios: list[float]) -> dict[str, pd.DataFrame]:
    """SPY 100 고정, VXUS = 100 × 비율. 날짜는 2020-01-01 부터 평일."""
    dates = _weekdays(date(2020, 1, 1), date(2020, 12, 31))[: len(ratios)]
    return {
        "vxus": _df(dates, [100.0 * r for r in ratios]),
        "shy": _df(dates, [50.0] * len(dates)),
        "spy": _df(dates, [100.0] * len(dates)),
    }


_VXUS = {"vxus": 1.0, "shy": 0.0}
_SHY = {"vxus": 0.0, "shy": 1.0}


class TestUsWeaknessRotation:
    """VXUS ÷ SPY 비율이 이동평균보다 위면 VXUS, 아니면 SHY. 첫 호출과 월말에만 판단한다."""

    def test_first_call_decides_even_if_not_check_day(self) -> None:
        """
        목적: 첫 호출은 판단일이 아니어도 규칙대로 판단한다

        Given: 비율이 5일 평균보다 위 (마지막 날 상승)
        When: 첫 호출(is_check_day=False)
        Then: VXUS 100%
        """
        # Given
        data = _rotation_data([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1])

        # When
        weights = UsWeaknessRotationAllocator(ma_window=5).target_weights(data, 6, date(2020, 1, 9), False)

        # Then
        assert weights == _VXUS

    def test_after_first_call_decides_only_on_check_day(self) -> None:
        """
        목적: 첫 판단 뒤에는 판단일에만 판단한다

        Given: 첫 호출 때 비율이 평균 위, 다음 날 평균 아래로 떨어짐
        When: 같은 규칙을 다음 날 is_check_day=False 로 호출한 뒤, 같은 날 is_check_day=True 로 다시 호출
        Then: 판단일 아님 → None, 판단일 → SHY
        """
        # Given
        data = _rotation_data([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 0.8])
        allocator = UsWeaknessRotationAllocator(ma_window=5)
        allocator.target_weights(data, 6, date(2020, 1, 9), False)

        # When / Then
        assert allocator.target_weights(data, 7, date(2020, 1, 10), False) is None
        assert allocator.target_weights(data, 7, date(2020, 1, 10), True) == _SHY

    def test_ratio_equal_to_average_goes_to_shy(self) -> None:
        """
        목적: 비율이 평균과 같으면 SHY (평균보다 「위」일 때만 VXUS)

        Given: 비율이 일정 (비율 = 평균)
        When: 첫 호출
        Then: SHY 100%
        """
        # Given
        data = _rotation_data([1.0] * 7)

        # When / Then
        assert UsWeaknessRotationAllocator(ma_window=5).target_weights(data, 6, date(2020, 1, 9), True) == _SHY

    def test_insufficient_history_returns_none_and_keeps_first_decision_pending(self) -> None:
        """
        목적: 평균을 낼 행이 모자라면 판단하지 않고, 첫 판단은 평균이 생긴 뒤 첫 호출로 미뤄진다

        Given: 5일 평균, i=2 에서 첫 호출
        When: i=2 호출 뒤 i=6 (판단일 아님) 호출
        Then: i=2 → None, i=6 → 판단(VXUS)
        """
        # Given
        data = _rotation_data([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1])
        allocator = UsWeaknessRotationAllocator(ma_window=5)

        # When / Then
        assert allocator.target_weights(data, 2, date(2020, 1, 3), False) is None
        assert allocator.target_weights(data, 6, date(2020, 1, 9), False) == _VXUS

    def test_future_rows_do_not_change_decision(self) -> None:
        """
        목적: i 행 뒤의 시세를 바꿔도 i 행의 판단이 같다 (미래 참조 금지)

        Given: 같은 앞부분에 뒷부분만 크게 다른 두 비율
        When: 두 시세로 각각 새 규칙을 만들어 i=6 판단
        Then: 같다
        """
        # Given
        base = _rotation_data([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 1.0, 1.0, 1.0])
        changed = _rotation_data([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1, 5.0, 5.0, 5.0])

        # When
        expected = UsWeaknessRotationAllocator(ma_window=5).target_weights(base, 6, date(2020, 1, 9), True)
        actual = UsWeaknessRotationAllocator(ma_window=5).target_weights(changed, 6, date(2020, 1, 9), True)

        # Then
        assert expected == actual == _VXUS


# ============================================================================
# EWY 200일선
# ============================================================================


def _ewy_path(length: int) -> list[float]:
    """오르내리는 시세: 버퍼존 매수 · 매도 신호가 여러 번 난다."""
    return [100.0 + 30.0 * math.sin(2.0 * math.pi * k / 60.0) + 0.1 * k for k in range(length)]


def _ewy_data(length: int) -> dict[str, pd.DataFrame]:
    dates = _weekdays(date(2020, 1, 1), date(2021, 12, 31))[:length]
    return {"ewy": _df(dates, _ewy_path(length)), "shy": _df(dates, [50.0] * length)}


_EWY_PARAMS = {"ma_window": 10, "buy_buffer_pct": 0.03, "sell_buffer_pct": 0.05, "hold_days": 2}


class TestEwyBufferZone:
    """EWY 에 버퍼존 신호, 매수 구간 EWY 100% · 매도 구간 SHY 100%. 첫 호출은 SHY."""

    def test_first_call_is_shy(self) -> None:
        """
        목적: 첫 호출은 매도 구간의 자리(SHY 100%)다

        Given: 이동평균을 낼 수 있는 시세
        When: 첫 호출
        Then: SHY 100%
        """
        # Given
        data = _ewy_data(120)

        # When
        weights = EwyBufferZoneAllocator(**_EWY_PARAMS).target_weights(data, 9, date(2020, 1, 14), False)

        # Then
        assert weights == {"ewy": 0.0, "shy": 1.0}

    def test_switch_dates_match_buffer_zone_strategy(self) -> None:
        """
        목적: 전환 날짜가 같은 시세 · 같은 파라미터의 BufferZoneStrategy 신호 날짜와 같다
              (미보유면 check_buy, 보유면 check_sell 을 하루 한 번 — 슬롯과 같은 호출 순서)

        Given: 오르내리는 EWY 시세 240일, 10일 평균 · 3% · 5% · 2일
        When: 규칙을 매일 호출 / 같은 시세로 BufferZoneStrategy 를 같은 순서로 호출
        Then: 전환 날짜와 방향이 같고, 매수 · 매도가 각각 한 번 이상 있다
        """
        # Given
        data = _ewy_data(240)
        start = _EWY_PARAMS["ma_window"] - 1
        allocator = EwyBufferZoneAllocator(**_EWY_PARAMS)
        signal_df = add_single_moving_average(data["ewy"], _EWY_PARAMS["ma_window"])
        strategy = BufferZoneStrategy(ma_col_name(_EWY_PARAMS["ma_window"]), 0.03, 0.05, 2)

        # When
        actual: list[tuple[int, str]] = []
        expected: list[tuple[int, str]] = []
        held = False
        for i in range(start, len(signal_df)):
            current_date = signal_df[COL_DATE].iloc[i]
            weights = allocator.target_weights(data, i, current_date, False)
            if weights is not None and i > start:
                actual.append((i, "buy" if weights["ewy"] == 1.0 else "sell"))
            if not held and strategy.check_buy(signal_df, i, current_date):
                held = True
                expected.append((i, "buy"))
            elif held and strategy.check_sell(signal_df, i):
                held = False
                expected.append((i, "sell"))

        # Then
        assert actual == expected
        assert {"buy", "sell"} <= {side for _, side in actual}

    def test_first_call_after_warmup_does_not_judge_breakout(self) -> None:
        """
        목적: 첫 호출이 워밍업 행보다 늦어도(엔진에 시작일을 준 경우) 첫날은 돌파를 판정하지 않고 SHY 로 시작한다
              — 엔진은 슬롯에 시작일로 자른 시세를 넘겨 슬롯의 첫 호출은 늘 0 행이다

        Given: 20일 동안 100, 그 뒤 120 인 EWY, 10일 평균 · 즉시 신호(hold 0), 첫 호출 i=20 (그날 상단 밴드 돌파)
        When: 첫 호출
        Then: SHY 100% (전날 행으로 밴드를 잡아 첫날 매수하지 않는다)
        """
        # Given
        dates = _weekdays(date(2020, 1, 1), date(2020, 3, 31))[:40]
        data = {"ewy": _df(dates, [100.0] * 20 + [120.0] * 20), "shy": _df(dates, [50.0] * 40)}
        allocator = EwyBufferZoneAllocator(ma_window=10, buy_buffer_pct=0.03, sell_buffer_pct=0.05, hold_days=0)

        # When
        weights = allocator.target_weights(data, 20, dates[20], False)

        # Then
        assert weights == {"ewy": 0.0, "shy": 1.0}

    def test_no_signal_returns_none(self) -> None:
        """
        목적: 신호가 없는 날은 목표를 바꾸지 않는다

        Given: 첫 호출 뒤 시세가 평평한 날
        When: 다음 날 호출
        Then: None
        """
        # Given
        dates = _weekdays(date(2020, 1, 1), date(2020, 3, 31))[:30]
        data = {"ewy": _df(dates, [100.0] * 30), "shy": _df(dates, [50.0] * 30)}
        allocator = EwyBufferZoneAllocator(**_EWY_PARAMS)
        allocator.target_weights(data, 9, dates[9], False)

        # When / Then
        assert allocator.target_weights(data, 10, dates[10], False) is None


# ============================================================================
# 레지스트리 · 설정 검증
# ============================================================================


_REQUIRED_IDS = {
    "haa": (HAA_ASSET_IDS, HAA_SERIES_IDS),
    "us_weakness_rotation": (ROTATION_ASSET_IDS, ROTATION_SERIES_IDS),
    "ewy_buffer_zone": (EWY_ASSET_IDS, ()),
}


class TestRegistry:
    """세 규칙의 등록 · 워밍업 · 설정 검증."""

    @pytest.mark.parametrize(
        ("allocator_id", "expected_warmup"),
        [("haa", 253), ("us_weakness_rotation", 200), ("ewy_buffer_zone", 200)],
    )
    def test_registered_with_warmup(self, allocator_id: str, expected_warmup: int) -> None:
        """
        목적: 세 규칙이 등록돼 있고 워밍업 행 수가 정해진 값이다

        Given: 규칙이 요구하는 id 그대로의 설정
        When: 레지스트리 조회 · create_allocator · get_warmup_periods
        Then: 생성 성공, 워밍업 = HAA 253 · 로테이션 200 · EWY 200
        """
        # Given
        asset_ids, series_ids = _REQUIRED_IDS[allocator_id]
        method = _method(allocator_id, asset_ids, series_ids)
        spec = ALLOCATOR_REGISTRY[allocator_id]

        # When
        spec.create_allocator(method)
        warmup = spec.get_warmup_periods(method)

        # Then
        assert warmup == expected_warmup

    @pytest.mark.parametrize("allocator_id", ["haa", "us_weakness_rotation", "ewy_buffer_zone"])
    @pytest.mark.parametrize("defect", ["missing_asset", "extra_asset", "wrong_series"])
    def test_config_ids_must_match(self, allocator_id: str, defect: str) -> None:
        """
        목적: 설정의 자산 id · 시세 id 가 규칙이 요구하는 것과 정확히 같아야 한다

        Given: 자산 하나 빠짐 / 자산 하나 더 있음 / 시세 id 가 다름
        When: create_allocator
        Then: ValueError
        """
        # Given
        asset_ids, series_ids = _REQUIRED_IDS[allocator_id]
        if defect == "missing_asset":
            asset_ids = asset_ids[1:]
        elif defect == "extra_asset":
            asset_ids = (*asset_ids, "gld")
        else:
            series_ids = ("qqq",)
        method = _method(allocator_id, asset_ids, series_ids)

        # When / Then
        with pytest.raises(ValueError, match=allocator_id):
            ALLOCATOR_REGISTRY[allocator_id].create_allocator(method)


# ============================================================================
# 엔진 통합
# ============================================================================


def _wave(length: int, phase: float, period: float, drift: float) -> list[float]:
    return [100.0 * (1.0 + 0.15 * math.sin(2.0 * math.pi * (k / period + phase)) + drift * k) for k in range(length)]


def _engine_config(
    tmp_path: Path,
    create_csv_file,
    allocator_id: str,
    closes_by_id: dict[str, list[float]],
    series_ids: tuple[str, ...],
) -> PortfolioConfig:
    dates = _weekdays(date(2020, 1, 1), date(2021, 12, 31))[: len(next(iter(closes_by_id.values())))]
    paths = {key: create_csv_file(f"{key.upper()}_max.csv", _df(dates, closes)) for key, closes in closes_by_id.items()}
    gld = create_csv_file("GLD_max.csv", _df(dates, _wave(len(dates), 0.3, 90.0, 0.0002)))
    asset_ids = [key for key in closes_by_id if key not in series_ids]
    return PortfolioConfig(
        experiment_name="test_allocator_engine",
        display_name="Test Allocator Engine",
        total_capital=10_000_000.0,
        result_dir=tmp_path,
        methods=(
            SlotMethodConfig("base", "Base", 0.7, (AssetSlotConfig("gld", gld, gld, 1.0, strategy_id="buy_and_hold"),)),
            AllocatorMethodConfig(
                "cand",
                "Candidate",
                0.3,
                tuple(AllocationAssetConfig(key, paths[key], paths[key]) for key in asset_ids),
                allocator_id=allocator_id,
                signal_series=tuple(SignalSeriesConfig(key, paths[key]) for key in series_ids),
            ),
        ),
    )


def _held_assets(result_equity: pd.DataFrame) -> set[str]:
    """한 번이라도 보유한 배분 규칙 매매법 자산."""
    return {
        column.removeprefix("cand.").removesuffix("_shares")
        for column in result_equity.columns
        if column.startswith("cand.") and column.endswith("_shares") and float(result_equity[column].max()) > 0
    }


class TestEngineIntegration:
    """등록된 규칙을 슬롯 매매법과 섞어 엔진에 올리면 정합성 위반이 없다."""

    def test_haa_runs_in_engine(self, tmp_path: Path, create_csv_file) -> None:
        """
        Given: 고정 비중 매매법 70% + HAA 30%, 18개월 합성 시세(자산마다 다른 주기 · 위상, TIP 은 꾸준히 상승)
        When: run_portfolio_backtest → validate_portfolio_result
        Then: 위반 0, HAA 가 두 종목 이상을 보유했다
        """
        length = 390
        closes = {
            key: _wave(length, phase=n / 9.0, period=70.0 + 10.0 * n, drift=0.0003)
            for n, key in enumerate(HAA_ASSET_IDS)
        }
        closes["tip"] = [100.0 * (1.0 + 0.0005 * k) for k in range(length)]
        config = _engine_config(tmp_path, create_csv_file, "haa", closes, HAA_SERIES_IDS)

        result = run_portfolio_backtest(config)

        assert validate_portfolio_result(result) == []
        assert len(_held_assets(result.equity_df)) >= 2

    def test_rotation_runs_in_engine(self, tmp_path: Path, create_csv_file) -> None:
        """
        Given: 고정 비중 매매법 70% + 로테이션 30%, VXUS ÷ SPY 비율이 오르내리는 300일 합성 시세
        When: run_portfolio_backtest → validate_portfolio_result
        Then: 위반 0, VXUS · SHY 를 모두 보유했다
        """
        length = 300
        closes = {
            "vxus": _wave(length, phase=0.0, period=40.0, drift=0.0),
            "shy": [50.0 + 0.001 * k for k in range(length)],
            "spy": [100.0] * length,
        }
        config = _engine_config(tmp_path, create_csv_file, "us_weakness_rotation", closes, ROTATION_SERIES_IDS)

        result = run_portfolio_backtest(config)

        assert validate_portfolio_result(result) == []
        assert _held_assets(result.equity_df) == {"vxus", "shy"}

    def test_ewy_runs_in_engine(self, tmp_path: Path, create_csv_file) -> None:
        """
        Given: 고정 비중 매매법 70% + EWY 30%, 오르내리는 400일 합성 EWY
        When: run_portfolio_backtest → validate_portfolio_result
        Then: 위반 0, EWY · SHY 를 모두 보유했다
        """
        length = 400
        closes = {
            "ewy": [100.0 + 30.0 * math.sin(2.0 * math.pi * k / 120.0) + 0.05 * k for k in range(length)],
            "shy": [50.0 + 0.001 * k for k in range(length)],
        }
        config = _engine_config(tmp_path, create_csv_file, "ewy_buffer_zone", closes, ())

        result = run_portfolio_backtest(config)

        assert validate_portfolio_result(result) == []
        assert _held_assets(result.equity_df) == {"ewy", "shy"}

    def test_ewy_matches_buffer_zone_slot_with_late_start(self, tmp_path: Path, create_csv_file) -> None:
        """
        목적: 시작일을 워밍업보다 늦게 줘도 EWY 규칙의 매수 · 매도 체결일이 같은 EWY 버퍼존 슬롯과 같다

        Given: 오르내리는 400일 합성 EWY, 고정 비중 매매법 70% + (EWY 규칙 | EWY 버퍼존 슬롯) 30%, 시작일 = 260번째 행
        When: 두 설정을 같은 시작일로 run_portfolio_backtest
        Then: EWY 주수가 0 → 양수 · 양수 → 0 으로 바뀐 날이 같고, 한 번 이상 있다
        """
        # Given
        length = 400
        ewy_closes = [100.0 + 30.0 * math.sin(2.0 * math.pi * k / 120.0) + 0.05 * k for k in range(length)]
        closes = {"ewy": ewy_closes, "shy": [50.0 + 0.001 * k for k in range(length)]}
        allocator_config = _engine_config(tmp_path, create_csv_file, "ewy_buffer_zone", closes, ())
        ewy_path = tmp_path / "EWY_max.csv"
        slot_config = replace(
            allocator_config,
            methods=(
                allocator_config.methods[0],
                SlotMethodConfig("cand", "Candidate", 0.3, (AssetSlotConfig("ewy", ewy_path, ewy_path, 1.0),)),
            ),
        )
        start = _weekdays(date(2020, 1, 1), date(2021, 12, 31))[260]

        # When
        allocator_equity = run_portfolio_backtest(allocator_config, start_date=start).equity_df
        slot_equity = run_portfolio_backtest(slot_config, start_date=start).equity_df

        # Then
        def transitions(equity: pd.DataFrame) -> list[tuple[date, bool]]:
            shares = equity["cand.ewy_shares"].tolist()
            dates = equity[COL_DATE].tolist()
            return [(dates[k], shares[k] > 0) for k in range(1, len(shares)) if (shares[k - 1] > 0) != (shares[k] > 0)]

        assert transitions(allocator_equity) == transitions(slot_equity)
        assert transitions(allocator_equity)
