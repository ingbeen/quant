"""레버리지 합성 검증 테스트

검증 ② (합성 ↔ 실물 레버리지 ETF 추적), ③ (상장 전 펀드 대조 — 연 수익 · 해마다 비용),
④ (가정만 바꾼 판) 의 계산을 검증한다.

왜 중요한가요?
합성 생성은 이 숫자를 저장 · 표시만 하고 멈추지 않는다(합격선 없음). 계산이 틀리면 틀린 판단 근거가 에러 없이 남는다.
"""

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from qbt.common_constants import ANNUAL_DAYS, COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME
from qbt.tqqq.constants import COL_EXPENSE_DATE, COL_EXPENSE_VALUE, COL_FFR_DATE, COL_FFR_VALUE
from qbt.tqqq.leveraged_comparison import (
    VARIANT_ADOPTED,
    VARIANT_DIVIDEND,
    VARIANT_UNCAPPED,
    VARIANT_ZERO_SPREAD,
    annual_gap_rate,
    assumption_variants,
    compare_around,
    summarize_tracking,
    yearly_costs,
)
from qbt.tqqq.synthetic import build_cost_inputs, simulate_leveraged
from qbt.utils.proxy_comparison import align_closes, summarize_pair

DAYS = [date(2024, 1, 1) + timedelta(days=i) for i in range(6)]


def _df(dates: list[date], closes: list[float], *, opens: list[float] | None = None) -> pd.DataFrame:
    opens = opens if opens is not None else closes
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: opens,
            COL_HIGH: [max(o, c) for o, c in zip(opens, closes, strict=True)],
            COL_LOW: [min(o, c) for o, c in zip(opens, closes, strict=True)],
            COL_CLOSE: closes,
            COL_VOLUME: [0] * len(closes),
        }
    )


class TestSummarizeTracking:
    """검증 ② — 실물 첫날부터 누적 배수의 로그 차 · 하루 수익률 차 · 한 날치 예측 오차"""

    def test_identical_series_all_zero(self):
        """
        목적: 시뮬레이션이 실물과 같으면 모든 오차가 0 이다

        Given: 가격 수준만 다른(× 0.01) 같은 시세
        When: summarize_tracking
        Then: 누적 차 · 하루 수익률 차 · 한 날치 예측 오차 모두 0
        """
        # Given
        actual = _df(DAYS[:3], [100.0, 110.0, 99.0], opens=[100.0, 104.0, 108.0])
        simulated = _df(DAYS[:3], [1.0, 1.1, 0.99], opens=[1.0, 1.04, 1.08])

        # When
        summary = summarize_tracking(simulated, actual)

        # Then
        values = [
            summary.rmse,
            summary.mean,
            summary.max,
            summary.last,
            summary.daily_abs_diff_mean,
            summary.one_day_open,
            summary.one_day_close,
            summary.one_day_high,
            summary.one_day_low,
        ]
        assert values == pytest.approx([0.0] * len(values), abs=1e-9)

    def test_cumulative_log_diff_and_daily_diff(self):
        """
        목적: 누적 차는 실물 첫날을 1 로 맞춘 누적 배수의 로그 비(%) 이고 첫날(0)을 포함한 RMSE · 평균 · 최대(날짜) · 마지막 날이다

        Given: 실물 종가 100 · 110 · 121, 시뮬레이션 1.0 · 1.11 · 1.21
        When: summarize_tracking
        Then: 둘째 날 차 x = 100 ln(1.11 / 1.10), RMSE x / √3, 평균 x / 3, 최대 x (둘째 날), 마지막 0,
              하루 수익률 절대차 평균 = (|10 − 11| + |10 − 9.0090…|) / 2
        """
        # Given
        actual = _df(DAYS[:3], [100.0, 110.0, 121.0])
        simulated = _df(DAYS[:3], [1.0, 1.11, 1.21])

        # When
        summary = summarize_tracking(simulated, actual)

        # Then
        x = 100 * math.log(1.11 / 1.10)
        second_sim_return = (1.21 / 1.11 - 1) * 100
        assert summary.start == DAYS[0]
        assert summary.end == DAYS[2]
        assert summary.trading_days == 3
        assert summary.rmse == pytest.approx(x / math.sqrt(3), abs=1e-12)
        assert summary.mean == pytest.approx(x / 3, abs=1e-12)
        assert summary.max == pytest.approx(x, abs=1e-12)
        assert summary.max_date == DAYS[1]
        assert summary.last == pytest.approx(0.0, abs=1e-12)
        assert summary.daily_abs_diff_mean == pytest.approx((1.0 + abs(10.0 - second_sim_return)) / 2, abs=1e-9)

    def test_one_day_error_uses_simulation_ratio(self):
        """
        목적: 한 날치 예측 = 전날 실물 종가 × 시뮬의 그날 값 ÷ 시뮬의 전날 종가 — 시뮬레이션이 낸 값을 그대로 쓴다

        Given: 실물 시가 105 (전날 종가 100), 시뮬 시가 1.06 (전날 종가 1.0) → 예측 106, 셋째 날은 시뮬 비율이 실물과 같음
        When: summarize_tracking
        Then: 시가 오차 RMSE = √((1² + 0²) / 2)
        """
        # Given
        actual = _df(DAYS[:3], [100.0, 110.0, 120.0], opens=[100.0, 105.0, 115.0])
        simulated = _df(DAYS[:3], [1.0, 1.1, 1.2], opens=[1.0, 1.06, 1.1 * 115.0 / 110.0])

        # When
        summary = summarize_tracking(simulated, actual)

        # Then
        assert summary.one_day_open == pytest.approx(math.sqrt(0.5), abs=1e-9)

    def test_ignores_simulation_before_actual(self):
        """
        목적: 실물 첫날 앞의 시뮬레이션(상장 전 합성 구간)은 추적 오차에 들지 않는다

        Given: 같은 실물, 앞에 엉뚱한 날이 하나 더 있는 시뮬레이션
        When: summarize_tracking
        Then: 앞날이 없는 시뮬레이션과 결과가 같다
        """
        # Given
        actual = _df(DAYS[1:4], [100.0, 110.0, 121.0])
        simulated = _df(DAYS[1:4], [1.0, 1.11, 1.21])
        longer = _df(DAYS[:4], [5.0, 1.0, 1.11, 1.21])

        # When / Then
        assert summarize_tracking(longer, actual) == summarize_tracking(simulated, actual)

    def test_rejects_less_than_two_overlap_days(self):
        """
        목적: 겹치는 날이 2일 미만이면 멈춘다 (경계)

        Given: 하루만 겹치는 두 시세
        When: summarize_tracking
        Then: ValueError
        """
        # Given
        actual = _df(DAYS[2:4], [100.0, 101.0])
        simulated = _df(DAYS[:3], [1.0, 1.1, 1.2])

        # When / Then
        with pytest.raises(ValueError, match="2"):
            summarize_tracking(simulated, actual)


class TestCompareAround:
    """검증 ③ 연 수익 — 나누는 날 앞 · 뒤 두 구간에서 견줄 시세와 펀드를 비교"""

    def test_splits_before_and_after(self):
        """
        목적: 나누는 날 앞(그날 제외)과 뒤(그날 포함)로 잘라 summarize_pair 와 같은 값을 낸다

        Given: 6일 시세 둘, 나누는 날 넷째 날
        When: compare_around
        Then: 앞 = 첫날 ~ 셋째 날, 뒤 = 넷째 날 ~ 끝, 각 구간의 summarize_pair 와 같다
        """
        # Given
        product = _df(DAYS, [10.0, 11.0, 10.5, 12.0, 12.5, 13.0])
        fund = _df(DAYS, [20.0, 21.5, 20.0, 23.0, 24.5, 25.0])

        # When
        before, after = compare_around(product, fund, DAYS[3])

        # Then
        expected_before = summarize_pair(align_closes(product.iloc[:3], fund.iloc[:3]))
        expected_after = summarize_pair(align_closes(product.iloc[3:], fund.iloc[3:]))
        assert before == expected_before
        assert after == expected_after
        assert (before.start, before.end, after.start, after.end) == (DAYS[0], DAYS[2], DAYS[3], DAYS[5])

    def test_before_starts_at_fund_first_day(self):
        """
        목적: 펀드가 늦게 시작하면 앞 구간은 펀드 첫날부터다 — 두 시세가 모두 있는 날만 쓴다

        Given: 펀드가 둘째 날부터
        When: compare_around
        Then: 앞 구간 시작 = 둘째 날
        """
        # Given
        product = _df(DAYS, [10.0, 11.0, 10.5, 12.0, 12.5, 13.0])
        fund = _df(DAYS[1:], [21.5, 20.0, 23.0, 24.5, 25.0])

        # When
        before, _ = compare_around(product, fund, DAYS[3])

        # Then
        assert before.start == DAYS[1]

    def test_rejects_empty_side(self):
        """
        목적: 나누는 날이 펀드 첫날이면 앞 구간이 비어 멈춘다 (경계)

        Given: 펀드 첫날 = 나누는 날
        When: compare_around
        Then: ValueError
        """
        # Given
        product = _df(DAYS, [10.0, 11.0, 10.5, 12.0, 12.5, 13.0])
        fund = _df(DAYS[3:], [23.0, 24.5, 25.0])

        # When / Then
        with pytest.raises(ValueError):
            compare_around(product, fund, DAYS[3])


class TestYearlyCosts:
    """검증 ③ 해마다 비용 — 실제 = Σ ln(1 + 배율 × 기초 r) − Σ ln(1 + 상품 r), 모형은 같은 식에 합성"""

    @staticmethod
    def _dates() -> list[date]:
        # 2022 끝 두 날(수익률 하루) + 2023 다섯 날 + 2024 두 날 — 첫 해 · 마지막 해는 부분 연도
        return (
            [date(2022, 12, 29), date(2022, 12, 30)]
            + [date(2023, 1, d) for d in (2, 3, 4, 5, 6)]
            + [date(2024, 1, 2), date(2024, 1, 3)]
        )

    @staticmethod
    def _decaying(start: float, daily: float, n: int) -> list[float]:
        return [start * (1 - daily) ** i for i in range(n)]

    def test_flat_base_cost_is_minus_log_decay(self):
        """
        목적: 기초가 움직이지 않으면 실제 비용 = −Σ ln(1 − 하루 비용) 이다. 평균 금리는 그해 거래일의 금리 평균이다

        Given: 기초 종가 고정, 상품은 하루 0.1% · 합성은 0.05% 씩 줄어듦, 금리 2023-01 5%
        When: yearly_costs(min_days=5)
        Then: 2023 한 해 — 거래일 5, 실제 = −5 ln(0.999) × 100, 모형 = −5 ln(0.9995) × 100, 평균 금리 5
        """
        # Given
        dates = self._dates()
        base = _df(dates, [100.0] * len(dates))
        product = _df(dates, self._decaying(50.0, 0.001, len(dates)))
        model = _df(dates, self._decaying(1.0, 0.0005, len(dates)))
        ffr = {"2022-12": 0.04, "2023-01": 0.05, "2024-01": 0.06}

        # When
        years = yearly_costs(base, product, model, 2.0, ffr, min_days=5)

        # Then
        assert [y.year for y in years] == [2023]
        assert years[0].trading_days == 5
        assert years[0].actual_cost == pytest.approx(-5 * math.log(0.999) * 100, abs=1e-9)
        assert years[0].model_cost == pytest.approx(-5 * math.log(0.9995) * 100, abs=1e-9)
        assert years[0].mean_ffr == pytest.approx(5.0, abs=1e-12)

    def test_first_and_last_year_excluded(self):
        """
        목적: 공통 날짜의 첫 해 · 마지막 해는 거래일과 상관없이 빠진다 — 그해 합이 1년 치가 아니라 연 비용으로 읽히면 틀린다
              (2026 이 10개월 치로 섞인 일이 있다)

        Given: 2022 · 2023 · 2024 에 걸친 공통 날짜
        When: min_days 1
        Then: 2023 만
        """
        # Given
        dates = self._dates()
        base = _df(dates, [100.0] * len(dates))
        product = _df(dates, self._decaying(50.0, 0.001, len(dates)))
        ffr = {"2022-12": 0.04, "2023-01": 0.05, "2024-01": 0.06}

        # When
        years = yearly_costs(base, product, product, 2.0, ffr, min_days=1)

        # Then
        assert [y.year for y in years] == [2023]

    def test_short_middle_year_excluded(self):
        """
        목적: 가운데 해라도 거래일이 기준보다 적으면 빠진다 (경계 — 기준과 같으면 남는다)

        Given: 2023 다섯 날
        When: min_days 5 와 6
        Then: 5 면 2023, 6 이면 없음
        """
        # Given
        dates = self._dates()
        base = _df(dates, [100.0] * len(dates))
        product = _df(dates, self._decaying(50.0, 0.001, len(dates)))
        ffr = {"2022-12": 0.04, "2023-01": 0.05, "2024-01": 0.06}

        # When / Then
        assert [y.year for y in yearly_costs(base, product, product, 2.0, ffr, min_days=5)] == [2023]
        assert yearly_costs(base, product, product, 2.0, ffr, min_days=6) == []

    def test_rejects_leveraged_loss_beyond_total(self):
        """
        목적: 배율 × 기초 하루 수익률이 −100% 이하면 로그를 잴 수 없어 멈춘다

        Given: 기초 하루 −50%, 배율 3
        When: yearly_costs
        Then: ValueError
        """
        # Given
        dates = self._dates()[:3]
        base = _df(dates, [100.0, 100.0, 50.0])
        product = _df(dates, [10.0, 10.0, 1.0])
        ffr = {"2022-12": 0.04, "2023-01": 0.05}

        # When / Then
        with pytest.raises(ValueError, match="−100%"):
            yearly_costs(base, product, product, 3.0, ffr, min_days=1)


class TestAnnualGapRate:
    """배당 보정 폭 — 한 연 수익을 다른 연 수익으로 맞추는 연 비율"""

    def test_ratio_not_difference(self):
        """
        목적: 보정 폭은 두 연 수익의 비로 정한다 — 단순 차(0.57%p)를 복리로 붙이면 실물 QQQ(10.71%)를 넘는다

        Given: 지수 10.14%, 실물 10.71%
        When: annual_gap_rate
        Then: 1.1071 ÷ 1.1014 − 1 (약 0.0052), 단순 차 0.0057 보다 작다
        """
        # When
        gap = annual_gap_rate(10.14, 10.71)

        # Then
        assert gap == pytest.approx(1.1071 / 1.1014 - 1, abs=1e-15)
        assert gap < 0.0057

    def test_zero_when_equal(self):
        """
        목적: 두 연 수익이 같으면 보정하지 않는다 (경계)

        Given: 같은 연 수익
        When: annual_gap_rate
        Then: 0
        """
        # When / Then
        assert annual_gap_rate(8.0, 8.0) == pytest.approx(0.0, abs=1e-15)


class TestAssumptionVariants:
    """검증 ④ — 같은 기초로 가정만 바꾼 판의 Buy & Hold 연 수익 · 최악 낙폭"""

    @staticmethod
    def _underlying(start: date, n: int) -> pd.DataFrame:
        dates = [start + timedelta(days=i) for i in range(n)]
        closes = [100.0 * (1.01 if i % 2 else 0.995) ** i for i in range(n)]
        return _df(dates, closes)

    @staticmethod
    def _ffr_df() -> pd.DataFrame:
        return pd.DataFrame({COL_FFR_DATE: ["1998-12", "1999-01"], COL_FFR_VALUE: [0.08, 0.08]})

    @staticmethod
    def _expense_df() -> pd.DataFrame:
        return pd.DataFrame({COL_EXPENSE_DATE: ["2010-02"], COL_EXPENSE_VALUE: [0.0095]})

    def _run(self, start: date, n: int = 10) -> list:
        underlying = self._underlying(start, n)
        return assumption_variants(
            underlying,
            self._ffr_df(),
            self._expense_df(),
            [("TQQQ", 3.0), ("QLD", 2.0)],
            end=underlying[COL_DATE].iloc[-1],
            dividend_gap_rate=0.0057,
        )

    def test_rows_are_variants_by_product(self):
        """
        목적: 판 넷 × 상품의 행을 판 순서 · 상품 순서로 낸다

        Given: 상품 TQQQ · QLD
        When: assumption_variants
        Then: (채택, TQQQ), (채택, QLD), (상한 없음, TQQQ) … 8행
        """
        # When
        rows = self._run(date(1998, 12, 20))

        # Then
        variants = [VARIANT_ADOPTED, VARIANT_UNCAPPED, VARIANT_ZERO_SPREAD, VARIANT_DIVIDEND]
        assert [(r.variant, r.product, r.leverage) for r in rows] == [
            (v, p, lev) for v in variants for p, lev in (("TQQQ", 3.0), ("QLD", 2.0))
        ]

    def test_no_dividend_variant_without_gap(self):
        """
        목적: 보정 폭을 주지 않으면(None) 배당 보정 판을 내지 않고 나머지 판은 그대로다 — 기초가 배당을 담으면(VFINX)
              보정할 것이 없다

        Given: 같은 기초 · 상품, 보정 폭 None 과 0.0057
        When: assumption_variants
        Then: None 은 (채택 · 상한 없음 · 가산금리 0) × 상품 6행이고, 0.0057 판의 앞 6행과 같다
        """
        # Given
        underlying = self._underlying(date(1998, 12, 20), 10)

        # When
        rows = assumption_variants(
            underlying,
            self._ffr_df(),
            self._expense_df(),
            [("TQQQ", 3.0), ("QLD", 2.0)],
            end=underlying[COL_DATE].iloc[-1],
            dividend_gap_rate=None,
        )

        # Then
        variants = [VARIANT_ADOPTED, VARIANT_UNCAPPED, VARIANT_ZERO_SPREAD]
        assert [(r.variant, r.product) for r in rows] == [(v, p) for v in variants for p in ("TQQQ", "QLD")]
        assert rows == self._run(date(1998, 12, 20))[: len(rows)]

    def test_adopted_equals_buy_and_hold_of_synthetic(self):
        """
        목적: 채택 판은 합성 파일과 같은 비용 입력으로 만든 시세의 종가 Buy & Hold 다 — 연 수익은 달력일 기준

        Given: 1998-12 걸친 10일
        When: assumption_variants
        Then: 채택 TQQQ 의 연 수익 · 최악 낙폭 = simulate_leveraged 종가로 직접 잰 값
        """
        # Given
        underlying = self._underlying(date(1998, 12, 20), 10)
        costs = build_cost_inputs(self._ffr_df(), self._expense_df(), "1998-12")
        closes = simulate_leveraged(underlying, 3.0, costs)[COL_CLOSE]
        days = (underlying[COL_DATE].iloc[-1] - underlying[COL_DATE].iloc[0]).days
        expected_cagr = ((closes.iloc[-1] / closes.iloc[0]) ** (ANNUAL_DAYS / days) - 1) * 100
        expected_mdd = (closes / closes.cummax() - 1).min() * 100

        # When
        adopted = next(r for r in self._run(date(1998, 12, 20)) if r.variant == VARIANT_ADOPTED and r.product == "TQQQ")

        # Then
        assert adopted.cagr == pytest.approx(expected_cagr, abs=1e-9)
        assert adopted.mdd == pytest.approx(expected_mdd, abs=1e-9)

    def test_cap_matters_only_before_1999(self):
        """
        목적: 상한은 1998-12 까지만 걸리므로 1999년 뒤만 있는 구간에서는 채택 = 상한 없음, 1998-12 고금리 달이 있으면 채택이 더 높다

        Given: 1999-01 만 있는 구간 · 1998-12 를 걸친 구간 (금리 8%)
        When: assumption_variants
        Then: 앞은 연 수익이 같고, 뒤는 채택 > 상한 없음
        """

        # Given / When
        def cagr(rows: list, variant: str) -> float:
            return next(r.cagr for r in rows if r.variant == variant and r.product == "TQQQ")

        only_1999 = self._run(date(1999, 1, 5))
        across = self._run(date(1998, 12, 20))

        # Then
        assert cagr(only_1999, VARIANT_ADOPTED) == pytest.approx(cagr(only_1999, VARIANT_UNCAPPED), abs=1e-12)
        assert cagr(across, VARIANT_ADOPTED) > cagr(across, VARIANT_UNCAPPED)

    def test_zero_spread_and_dividend_raise_return(self):
        """
        목적: 가산금리 0 판과 배당 보정 판은 채택 판보다 연 수익이 높다 — 비용을 덜 빼거나 기초 수익을 더한다

        Given: 1998-12 를 걸친 구간
        When: assumption_variants
        Then: 두 판의 연 수익 > 채택
        """
        # When
        rows = self._run(date(1998, 12, 20))
        by_variant = {r.variant: r.cagr for r in rows if r.product == "QLD"}

        # Then
        assert by_variant[VARIANT_ZERO_SPREAD] > by_variant[VARIANT_ADOPTED]
        assert by_variant[VARIANT_DIVIDEND] > by_variant[VARIANT_ADOPTED]

    def test_dividend_drift_compounds_exactly_on_calendar_days(self):
        """
        목적: 배당 보정 판의 기초는 연 수익이 정확히 보정 폭만큼 복리로 오른다 — 연 수익을 달력일로 재므로 달력일 비례로 붙인다
              (거래일 수로 나누면 해마다 거래일이 다른 만큼 어긋난다)

        Given: 비용이 0 인 1배 (운용비율 0, 배율 1 이라 금리 비용 없음), 띄엄띄엄한 날짜(주말 포함), 보정 폭 0.0052
        When: assumption_variants
        Then: 배당 보정 판의 연 수익 = (1 + 채택) × (1 + 0.0052) − 1
        """
        # Given
        dates = [date(1999, 1, 4), date(1999, 1, 5), date(1999, 1, 8), date(1999, 1, 11), date(1999, 1, 20)]
        underlying = _df(dates, [100.0, 101.0, 99.5, 102.0, 103.5])
        no_expense = pd.DataFrame({COL_EXPENSE_DATE: ["1999-01"], COL_EXPENSE_VALUE: [0.0]})
        gap = 0.0052

        # When
        rows = assumption_variants(
            underlying,
            self._ffr_df(),
            no_expense,
            [("X", 1.0)],
            end=dates[-1],
            dividend_gap_rate=gap,
        )

        # Then
        by_variant = {r.variant: r.cagr for r in rows}
        expected = ((1 + by_variant[VARIANT_ADOPTED] / 100) * (1 + gap) - 1) * 100
        assert by_variant[VARIANT_DIVIDEND] == pytest.approx(expected, abs=1e-9)

    def test_rejects_window_under_two_days(self):
        """
        목적: 구간에 날이 2일 미만이면 멈춘다 (경계)

        Given: 끝날이 기초 첫날
        When: assumption_variants
        Then: ValueError
        """
        # Given
        underlying = self._underlying(date(1999, 1, 5), 5)

        # When / Then
        with pytest.raises(ValueError, match="2"):
            assumption_variants(
                underlying,
                self._ffr_df(),
                self._expense_df(),
                [("TQQQ", 3.0)],
                end=underlying[COL_DATE].iloc[0],
                dividend_gap_rate=0.0057,
            )
