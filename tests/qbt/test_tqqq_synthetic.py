"""레버리지 합성 테스트

비용 입력(금리 · 운용비율 · 상한 건 가산금리)과 상품 하나의 합성(시뮬레이션 → 이어 붙이기 → 이음매 뒤 실물 검사),
상품 표 전체의 저장을 검증한다.

왜 중요한가요?
합성 TQQQ · QLD 는 전략이 매매 시세로 읽는다. 상한이 1999년 뒤 달에 걸리면 기존 합성의 1999년 이후 값이 바뀌고,
상품 표 → 저장 경로 연결이 어긋나면 2배 시세가 3배 파일을 에러 없이 덮는다.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from qbt.common_constants import (
    COL_CLOSE,
    COL_DATE,
    COL_HIGH,
    COL_LOW,
    COL_OPEN,
    COL_VOLUME,
    TRADING_DAYS_PER_YEAR,
)
from qbt.tqqq.constants import (
    COL_EXPENSE_DATE,
    COL_EXPENSE_VALUE,
    COL_FFR_DATE,
    COL_FFR_VALUE,
    DEFAULT_PRE_LISTING_EXPENSE_RATIO,
    DEFAULT_SOFTPLUS_A,
    DEFAULT_SOFTPLUS_B,
    SPREAD_CAP,
)
from qbt.tqqq.simulation import build_monthly_spread_map
from qbt.tqqq.synthetic import (
    CostInputs,
    build_cost_inputs,
    build_leveraged_synthetic,
    save_leveraged_synthetics,
    simulate_leveraged,
)
from qbt.utils.data_loader import load_stock_data
from qbt.utils.proxy_series import splice_proxy

# 상한 마지막 달(1998-12)을 걸치는 거래일 — 이음매는 1999-01-05
DAYS = [
    date(1998, 12, 28),
    date(1998, 12, 29),
    date(1998, 12, 30),
    date(1998, 12, 31),
    date(1999, 1, 4),
    date(1999, 1, 5),
    date(1999, 1, 6),
    date(1999, 1, 7),
]
SEAM_INDEX = 5
HIGH_RATE = 0.08  # 비율 (0.08 = 8%) — softplus 가산금리가 상한을 넘는 금리


def _price_df(dates: list[date], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: [c * 0.995 for c in closes],
            COL_HIGH: [c * 1.01 for c in closes],
            COL_LOW: [c * 0.98 for c in closes],
            COL_CLOSE: closes,
            COL_VOLUME: [1000] * len(closes),
        }
    )


def _underlying() -> pd.DataFrame:
    # 둘째 날 +20% — 3배면 하루 +60% 라 급등락 검사를 켜면 저장이 멈춘다
    return _price_df(DAYS, [100.0, 120.0, 118.0, 121.0, 123.0, 120.0, 124.0, 125.0])


def _actual(closes: list[float]) -> pd.DataFrame:
    return _price_df(DAYS[SEAM_INDEX:], closes)


def _ffr_df() -> pd.DataFrame:
    return pd.DataFrame({COL_FFR_DATE: ["1998-12", "1999-01"], COL_FFR_VALUE: [HIGH_RATE, HIGH_RATE]})


def _expense_df() -> pd.DataFrame:
    return pd.DataFrame({COL_EXPENSE_DATE: ["2010-02"], COL_EXPENSE_VALUE: [0.0095]})


def _near_zero_costs() -> CostInputs:
    # 시뮬레이션은 가산금리 0 을 거부한다 — 비용이 사실상 0 이라 하루 수익률이 배율 × 기초 수익률이 된다
    months = ["1998-12", "1999-01"]
    return CostInputs(
        ffr={m: 0.0 for m in months},
        expense={m: 0.0 for m in months},
        spread={m: 1e-12 for m in months},
    )


def _returns(closes: pd.Series) -> pd.Series:
    return closes / closes.shift(1) - 1.0


class TestBuildCostInputs:
    """합성 비용 입력 — 금리 · 운용비율(시작 달부터) · 가산금리(1998-12 까지 상한)"""

    def test_spread_capped_only_through_1998(self):
        """
        목적: 가산금리 상한은 1998-12 까지의 달에만 걸린다 — 1999-01 부터는 모형 값 그대로 (결정 4)

        Given: 1998-12 · 1999-01 금리 8% (모형 가산금리가 상한을 넘는다)
        When: build_cost_inputs
        Then: 1998-12 = 상한, 1999-01 = 모형 값
        """
        # Given
        model = build_monthly_spread_map(_ffr_df(), DEFAULT_SOFTPLUS_A, DEFAULT_SOFTPLUS_B)
        assert model["1998-12"] > SPREAD_CAP

        # When
        costs = build_cost_inputs(_ffr_df(), _expense_df(), "1998-12")

        # Then
        assert costs.spread["1998-12"] == SPREAD_CAP
        assert costs.spread["1999-01"] == model["1999-01"]

    def test_no_cap_option(self):
        """
        목적: 상한 없는 판(검증 ④)은 모든 달이 모형 값이다

        Given: 같은 금리
        When: build_cost_inputs(spread_cap=None)
        Then: 두 달 모두 모형 값
        """
        # Given
        model = build_monthly_spread_map(_ffr_df(), DEFAULT_SOFTPLUS_A, DEFAULT_SOFTPLUS_B)

        # When
        costs = build_cost_inputs(_ffr_df(), _expense_df(), "1998-12", spread_cap=None)

        # Then
        assert costs.spread == model

    def test_expense_from_first_month(self):
        """
        목적: 운용비율은 기초 시세의 첫 달부터 상장 전 고정값으로 덮인다

        Given: 2010-02 부터인 운용비율, 첫 달 1998-12
        When: build_cost_inputs
        Then: 1998-12 고정값, 1998-11 없음, 금리는 파일 그대로
        """
        # When
        costs = build_cost_inputs(_ffr_df(), _expense_df(), "1998-12")

        # Then
        assert costs.expense["1998-12"] == DEFAULT_PRE_LISTING_EXPENSE_RATIO
        assert "1998-11" not in costs.expense
        assert costs.ffr == {"1998-12": HIGH_RATE, "1999-01": HIGH_RATE}


class TestBuildLeveragedSynthetic:
    """상품 하나의 합성 — 이음매 앞 시뮬레이션, 이음매부터 실물, 이음매 뒤 검사"""

    def test_rows_from_seam_equal_actual(self):
        """
        목적: 이음매 날부터는 실물 행 그대로다

        Given: 기초 8일, 실물은 이음매(1999-01-05)부터 3일
        When: simulate_leveraged → build_leveraged_synthetic
        Then: 이음매 뒤 행 = 실물 행
        """
        # Given
        actual = _actual([50.0, 52.0, 51.0])
        costs = build_cost_inputs(_ffr_df(), _expense_df(), "1998-12")

        # When
        result = build_leveraged_synthetic(simulate_leveraged(_underlying(), 3.0, costs), actual)

        # Then
        from_seam = result[result[COL_DATE] >= DAYS[SEAM_INDEX]].reset_index(drop=True)
        pd.testing.assert_frame_equal(from_seam, actual.reset_index(drop=True))

    def test_pre_seam_return_is_leverage_minus_cost(self):
        """
        목적: 이음매 앞 하루 수익률 = 배율 × 기초 수익률 − 그날 비용이고, 비용의 가산금리는 1998-12 에 상한, 1999-01 에 모형 값이다

        Given: 금리 8%, 운용비율 0.95%(상장 전 고정값), 배율 3
        When: simulate_leveraged → build_leveraged_synthetic
        Then: 이음매 앞 넷째 날까지 하루 수익률이 손계산과 같다
        """
        # Given
        leverage = 3.0
        costs = build_cost_inputs(_ffr_df(), _expense_df(), "1998-12")
        underlying = _underlying()

        # When
        result = build_leveraged_synthetic(simulate_leveraged(underlying, leverage, costs), _actual([50.0, 52.0, 51.0]))

        # Then
        result_returns = _returns(result[COL_CLOSE])
        underlying_returns = _returns(underlying[COL_CLOSE])
        for i in range(1, SEAM_INDEX):
            month = f"{DAYS[i].year:04d}-{DAYS[i].month:02d}"
            daily_cost = (
                (HIGH_RATE + costs.spread[month]) * (leverage - 1) + DEFAULT_PRE_LISTING_EXPENSE_RATIO
            ) / TRADING_DAYS_PER_YEAR
            expected = underlying_returns.iloc[i] * leverage - daily_cost
            assert result_returns.iloc[i] == pytest.approx(expected, abs=1e-12)

    def test_stops_when_rows_from_seam_differ(self, monkeypatch: pytest.MonkeyPatch):
        """
        목적: 이어 붙인 결과의 이음매 뒤 행이 실물과 다르면 저장하기 전에 멈춘다 (불변 조건 ⑥)

        Given: 이음매 날 시가를 종가로 덮어쓴 결과를 돌려주는 splice_proxy
        When: build_leveraged_synthetic
        Then: RuntimeError (내부 불변조건 위반)
        """

        # Given
        def splice_overwriting_seam_open(proxy_df: pd.DataFrame, actual_df: pd.DataFrame) -> pd.DataFrame:
            spliced = splice_proxy(proxy_df, actual_df)
            seam_mask = spliced[COL_DATE] == actual_df[COL_DATE].iloc[0]
            spliced.loc[seam_mask, COL_OPEN] = spliced.loc[seam_mask, COL_CLOSE]
            return spliced

        monkeypatch.setattr("qbt.tqqq.synthetic.splice_proxy", splice_overwriting_seam_open)
        costs = build_cost_inputs(_ffr_df(), _expense_df(), "1998-12")
        simulated = simulate_leveraged(_underlying(), 2.0, costs)

        # When / Then
        with pytest.raises(RuntimeError, match="내부 불변조건 위반"):
            build_leveraged_synthetic(simulated, _actual([50.0, 52.0, 51.0]))


class TestSaveLeveragedSynthetics:
    """상품 표 전체 저장 — 상품마다 자기 실물에 자기 배율로 이어 자기 경로에 저장"""

    @staticmethod
    def _targets(tmp_path: Path) -> tuple[tuple[str, Path, float, Path], ...]:
        actual_a = tmp_path / "AAA_max.csv"
        actual_b = tmp_path / "BBB_max.csv"
        _actual([50.0, 52.0, 51.0]).to_csv(actual_a, index=False)
        _actual([20.0, 21.0, 20.5]).to_csv(actual_b, index=False)
        return (
            ("AAA", actual_a, 3.0, tmp_path / "out" / "AAA_synthetic_max.csv"),
            ("BBB", actual_b, 2.0, tmp_path / "out" / "BBB_synthetic_max.csv"),
        )

    def test_each_product_saved_with_own_leverage_and_actual(self, tmp_path: Path):
        """
        목적: 상품 표 → 저장 경로 연결을 고정한다 — 저장 대상을 다른 상품 경로로 바꾸거나 배율 · 실물을 섞으면 실패한다.
              하루 +60% 인 날(3배)이 있어도 저장한다(급등락 검사를 끈다)

        Given: 상품 둘 (3배 · 2배, 실물이 다름), 비용이 사실상 0 인 입력
        When: save_leveraged_synthetics
        Then: 각 파일의 이음매 앞 하루 수익률 = 자기 배율 × 기초 수익률, 이음매 뒤 종가 = 자기 실물 종가
        """
        # Given
        targets = self._targets(tmp_path)
        underlying = _underlying()

        # When
        save_leveraged_synthetics(underlying, _near_zero_costs(), targets)

        # Then
        underlying_returns = _returns(underlying[COL_CLOSE])
        for _, actual_path, leverage, output_path in targets:
            saved = load_stock_data(output_path)
            saved_returns = _returns(saved[COL_CLOSE])
            for i in range(1, SEAM_INDEX):
                assert saved_returns.iloc[i] == pytest.approx(leverage * underlying_returns.iloc[i], abs=1e-6)
            from_seam = saved[saved[COL_DATE] >= DAYS[SEAM_INDEX]][COL_CLOSE].tolist()
            assert from_seam == load_stock_data(actual_path)[COL_CLOSE].tolist()

    def test_returns_runs_in_target_order(self, tmp_path: Path):
        """
        목적: 검증 ② 에 넘길 상품별 시뮬레이션 · 실물을 표 순서대로 돌려준다

        Given: 상품 둘
        When: save_leveraged_synthetics
        Then: 이름 · 배율이 표 순서, 시뮬레이션은 기초 전 기간, 실물은 그 상품의 실물
        """
        # Given
        targets = self._targets(tmp_path)

        # When
        runs = save_leveraged_synthetics(_underlying(), _near_zero_costs(), targets)

        # Then
        assert [(run.name, run.leverage) for run in runs] == [("AAA", 3.0), ("BBB", 2.0)]
        assert runs[0].simulated[COL_DATE].tolist() == DAYS
        assert runs[1].actual[COL_CLOSE].tolist() == [20.0, 21.0, 20.5]
