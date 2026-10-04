"""대용 시계열 테스트

실물 ETF 상장 전 구간을 대용 시세로 채우는 함수의 계약을 검증한다.
이음매(실물 첫 거래일)에서의 비율 접합, 매일 비율을 맞추는 합성 바스켓, 입력 검증을 다룬다.

왜 중요한가요?
대용 파일은 백테스트의 입력이다. 이음매 뒤 구간이 실물과 한 행이라도 다르거나,
이음매 앞 구간의 수익률이 대용과 어긋나면 2007년부터 돌리는 주 비교의 성과가 조용히 틀린다.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from qbt.common_constants import COL_CLOSE, COL_DATE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME, REQUIRED_COLUMNS
from qbt.utils.proxy_series import (
    build_daily_rebalanced_composite,
    compute_seam_scale,
    rescale_to_actual,
    splice_proxy,
)

DAYS = [date(2024, 1, 1) + timedelta(days=i) for i in range(6)]
REL_TOL = 1e-12


def _make_df(
    dates: list[date],
    closes: list[float],
    *,
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[int] | None = None,
) -> pd.DataFrame:
    """시세 DataFrame 을 만든다. 시가 · 고가 · 저가를 생략하면 종가에서 만든다."""
    opens = opens if opens is not None else [c * 0.99 for c in closes]
    highs = highs if highs is not None else [max(o, c) * 1.01 for o, c in zip(opens, closes, strict=True)]
    lows = lows if lows is not None else [min(o, c) * 0.98 for o, c in zip(opens, closes, strict=True)]
    volumes = volumes if volumes is not None else [1000 + i for i in range(len(dates))]
    return pd.DataFrame(
        {
            COL_DATE: dates,
            COL_OPEN: opens,
            COL_HIGH: highs,
            COL_LOW: lows,
            COL_CLOSE: closes,
            COL_VOLUME: volumes,
        }
    )


def _close_returns(df: pd.DataFrame) -> dict[date, float]:
    """날짜별 종가 수익률 (첫 행 제외)."""
    closes = df[COL_CLOSE].tolist()
    dates = df[COL_DATE].tolist()
    return {dates[i]: closes[i] / closes[i - 1] - 1.0 for i in range(1, len(dates))}


class TestComputeSeamScale:
    """이음매 스케일 = 실물 첫 거래일 종가 ÷ 그날 대용 종가."""

    def test_scale_is_ratio_of_seam_closes(self) -> None:
        """
        목적: 스케일은 이음매 날의 두 종가 비율이다

        Given: 이음매 DAYS[2] 의 대용 종가 12, 실물 종가 60
        When: compute_seam_scale
        Then: 5.0
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])

        # When
        scale = compute_seam_scale(proxy, actual)

        # Then
        assert scale == pytest.approx(5.0, rel=REL_TOL)


class TestRescaleToActual:
    """대용 전 구간을 실물 첫 거래일 종가에 맞춰 스케일한다."""

    def test_seam_close_matches_actual(self) -> None:
        """
        목적: 이음매(실물 첫 거래일)의 대용 종가가 실물 종가와 같아진다

        Given: 대용 종가 10 – 15, 실물은 DAYS[2] 에 종가 60 으로 시작
        When: rescale_to_actual
        Then: DAYS[2] 종가 = 60
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])

        # When
        result = rescale_to_actual(proxy, actual)

        # Then
        seam_close = float(result.loc[result[COL_DATE] == DAYS[2], COL_CLOSE].iloc[0])
        assert seam_close == pytest.approx(60.0, rel=REL_TOL)

    def test_all_price_columns_scaled_by_same_factor(self) -> None:
        """
        목적: 가격 4열이 모두 같은 배수로 바뀌어 수익률 · 봉 모양이 그대로다

        Given: 이음매 종가 비율 60 / 12 = 5
        When: rescale_to_actual
        Then: 시가 · 고가 · 저가 · 종가가 전 구간에서 원래 값 × 5
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])

        # When
        result = rescale_to_actual(proxy, actual)

        # Then
        for col in (COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE):
            assert result[col].tolist() == pytest.approx((proxy[col] * 5.0).tolist(), rel=REL_TOL)

    def test_volume_and_dates_unchanged(self) -> None:
        """
        목적: 거래량과 날짜는 스케일하지 않는다

        Given: 대용과 실물
        When: rescale_to_actual
        Then: 날짜 · 거래량이 대용 그대로
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])

        # When
        result = rescale_to_actual(proxy, actual)

        # Then
        assert result[COL_DATE].tolist() == proxy[COL_DATE].tolist()
        assert result[COL_VOLUME].tolist() == proxy[COL_VOLUME].tolist()

    def test_seam_missing_in_proxy_raises(self) -> None:
        """
        목적: 이음매 날짜가 대용에 없으면 스케일 기준이 없으므로 예외

        Given: 실물 첫 거래일이 대용 날짜에 없음
        When: rescale_to_actual
        Then: ValueError
        """
        # Given
        proxy = _make_df([DAYS[0], DAYS[1], DAYS[3]], [10.0, 11.0, 13.0])
        actual = _make_df(DAYS[2:4], [60.0, 66.0])

        # When / Then
        with pytest.raises(ValueError, match="이음매"):
            rescale_to_actual(proxy, actual)

    def test_inputs_not_mutated(self) -> None:
        """
        목적: 입력 DataFrame 을 바꾸지 않는다

        Given: 대용과 실물의 사본
        When: rescale_to_actual
        Then: 입력이 사본과 같다
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])
        proxy_copy, actual_copy = proxy.copy(), actual.copy()

        # When
        rescale_to_actual(proxy, actual)

        # Then
        pd.testing.assert_frame_equal(proxy, proxy_copy)
        pd.testing.assert_frame_equal(actual, actual_copy)


class TestSpliceProxy:
    """이음매 앞은 스케일한 대용, 이음매부터는 실물인 시계열을 만든다."""

    def test_rows_from_seam_equal_actual(self) -> None:
        """
        목적: 이음매부터는 실물 파일 행이 그대로 들어간다

        Given: 대용 6일, 실물은 DAYS[2] 부터
        When: splice_proxy
        Then: DAYS[2] 이후 행이 실물 행과 같다
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0], volumes=[7, 8, 9, 10])

        # When
        result = splice_proxy(proxy, actual)

        # Then
        from_seam = result[result[COL_DATE] >= DAYS[2]].reset_index(drop=True)
        pd.testing.assert_frame_equal(from_seam, actual.reset_index(drop=True))

    def test_returns_up_to_seam_equal_proxy(self) -> None:
        """
        목적: 이음매 앞 구간과 이음매 날의 종가 수익률은 대용의 수익률이다

        Given: 대용 종가 10, 11, 12.5, … 실물 이음매 종가 60
        When: splice_proxy
        Then: DAYS[1] · DAYS[2](이음매) 수익률 = 대용 수익률, DAYS[3] 부터는 실물 수익률
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.5, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])

        # When
        result = splice_proxy(proxy, actual)

        # Then
        result_returns = _close_returns(result)
        proxy_returns = _close_returns(proxy)
        actual_returns = _close_returns(actual)
        assert result_returns[DAYS[1]] == pytest.approx(proxy_returns[DAYS[1]], rel=REL_TOL)
        assert result_returns[DAYS[2]] == pytest.approx(proxy_returns[DAYS[2]], rel=REL_TOL)
        assert result_returns[DAYS[3]] == pytest.approx(actual_returns[DAYS[3]], rel=REL_TOL)

    def test_pre_seam_volume_is_zero(self) -> None:
        """
        목적: 이음매 앞 행의 거래량은 0 이다 (대용의 거래량은 실물 거래량이 아니다)

        Given: 대용 거래량이 0 이 아님
        When: splice_proxy
        Then: 이음매 앞 행 거래량 전부 0
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])

        # When
        result = splice_proxy(proxy, actual)

        # Then
        pre_seam = result[result[COL_DATE] < DAYS[2]]
        assert len(pre_seam) == 2
        assert pre_seam[COL_VOLUME].tolist() == [0, 0]

    def test_no_proxy_rows_before_seam_raises(self) -> None:
        """
        목적: 대용이 실물보다 먼저 시작하지 않으면 채울 구간이 없으므로 예외

        Given: 대용과 실물이 같은 날 시작
        When: splice_proxy
        Then: ValueError
        """
        # Given
        proxy = _make_df(DAYS[2:], [12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])

        # When / Then
        with pytest.raises(ValueError, match="이음매"):
            splice_proxy(proxy, actual)

    def test_columns_and_strictly_increasing_dates(self) -> None:
        """
        목적: 결과 열은 저장 형식(REQUIRED_COLUMNS)이고 날짜가 중복 없이 오름차순이다

        Given: 대용과 실물
        When: splice_proxy
        Then: 열 순서 = REQUIRED_COLUMNS, 날짜 = DAYS 전체(이음매 행 한 번)
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])

        # When
        result = splice_proxy(proxy, actual)

        # Then
        assert list(result.columns) == REQUIRED_COLUMNS
        assert result[COL_DATE].tolist() == DAYS

    def test_inputs_not_mutated(self) -> None:
        """
        목적: 입력 DataFrame 을 바꾸지 않는다

        Given: 대용과 실물의 사본
        When: splice_proxy
        Then: 입력이 사본과 같다
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])
        proxy_copy, actual_copy = proxy.copy(), actual.copy()

        # When
        splice_proxy(proxy, actual)

        # Then
        pd.testing.assert_frame_equal(proxy, proxy_copy)
        pd.testing.assert_frame_equal(actual, actual_copy)

    def test_pure_rescaled_pre_seam_equals_spliced_pre_seam(self) -> None:
        """
        목적: 순수판(전 구간 스케일)의 이음매 앞 가격이 이어 붙인 판의 이음매 앞 가격과 같다

        Given: 같은 대용 · 실물
        When: rescale_to_actual 과 splice_proxy
        Then: 이음매 앞 가격 4열이 같다
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = _make_df(DAYS[2:], [60.0, 66.0, 61.0, 70.0])

        # When
        pure = rescale_to_actual(proxy, actual)
        spliced = splice_proxy(proxy, actual)

        # Then
        price_cols = [COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE]
        pure_pre = pure[pure[COL_DATE] < DAYS[2]][price_cols].reset_index(drop=True)
        spliced_pre = spliced[spliced[COL_DATE] < DAYS[2]][price_cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(pure_pre, spliced_pre)


class TestBuildDailyRebalancedComposite:
    """매일 비율을 맞추는 합성 바스켓."""

    @staticmethod
    def _components() -> tuple[pd.DataFrame, pd.DataFrame]:
        a = _make_df(
            DAYS[:4],
            [100.0, 102.0, 99.0, 104.0],
            opens=[99.0, 101.0, 100.0, 103.0],
            highs=[101.0, 103.0, 101.0, 105.0],
            lows=[98.0, 100.0, 98.5, 102.0],
        )
        b = _make_df(
            DAYS[:4],
            [50.0, 49.0, 51.0, 52.5],
            opens=[50.5, 49.5, 50.0, 51.5],
            highs=[51.0, 50.0, 51.5, 53.0],
            lows=[49.5, 48.5, 49.0, 51.0],
        )
        return a, b

    def test_first_close_is_one(self) -> None:
        """
        목적: 합성 종가는 첫날 1.0 에서 시작한다

        Given: 구성 종목 둘
        When: build_daily_rebalanced_composite
        Then: 첫 종가 1.0
        """
        # Given
        a, b = self._components()

        # When
        result = build_daily_rebalanced_composite([(a, 0.75), (b, 0.25)])

        # Then
        assert float(result[COL_CLOSE].iloc[0]) == pytest.approx(1.0, rel=REL_TOL)

    def test_close_return_is_weighted_sum(self) -> None:
        """
        목적: 매일 종가 수익률 = Σ 비중 × 구성 종목 종가 수익률 (매일 비율을 다시 맞춘다)

        Given: 비중 0.75 · 0.25
        When: build_daily_rebalanced_composite
        Then: 둘째 날부터 수익률이 가중합과 같다
        """
        # Given
        a, b = self._components()

        # When
        result = build_daily_rebalanced_composite([(a, 0.75), (b, 0.25)])

        # Then
        result_returns = _close_returns(result)
        a_returns, b_returns = _close_returns(a), _close_returns(b)
        for day in DAYS[1:4]:
            expected = 0.75 * a_returns[day] + 0.25 * b_returns[day]
            assert result_returns[day] == pytest.approx(expected, rel=REL_TOL)

    def test_open_high_low_follow_previous_close(self) -> None:
        """
        목적: 시가 · 고가 · 저가 = 전날 합성 종가 × Σ 비중 × (구성 종목 그 값 ÷ 구성 종목 전날 종가).
              첫날은 전날 종가 자리에 1.0 과 그날 종가를 쓴다

        Given: 구성 종목 둘
        When: build_daily_rebalanced_composite
        Then: 매일 시가 · 고가 · 저가가 산식과 같다
        """
        # Given
        a, b = self._components()
        weights = (0.75, 0.25)

        # When
        result = build_daily_rebalanced_composite([(a, weights[0]), (b, weights[1])])

        # Then
        closes = result[COL_CLOSE].tolist()
        for col in (COL_OPEN, COL_HIGH, COL_LOW):
            for i in range(4):
                if i == 0:
                    base = 1.0
                    ratio_a = a[col].iloc[0] / a[COL_CLOSE].iloc[0]
                    ratio_b = b[col].iloc[0] / b[COL_CLOSE].iloc[0]
                else:
                    base = closes[i - 1]
                    ratio_a = a[col].iloc[i] / a[COL_CLOSE].iloc[i - 1]
                    ratio_b = b[col].iloc[i] / b[COL_CLOSE].iloc[i - 1]
                expected = base * (weights[0] * ratio_a + weights[1] * ratio_b)
                assert float(result[col].iloc[i]) == pytest.approx(expected, rel=REL_TOL)

    def test_high_and_low_bracket_open_and_close(self) -> None:
        """
        목적: 구성 종목에서 고가 ≥ 시가 · 종가 ≥ 저가이면 합성에서도 성립한다

        Given: 봉 모양이 올바른 구성 종목
        When: build_daily_rebalanced_composite
        Then: 매일 고가 ≥ max(시가, 종가), 저가 ≤ min(시가, 종가)
        """
        # Given
        a, b = self._components()

        # When
        result = build_daily_rebalanced_composite([(a, 0.75), (b, 0.25)])

        # Then
        for _, row in result.iterrows():
            assert row[COL_HIGH] >= max(row[COL_OPEN], row[COL_CLOSE])
            assert row[COL_LOW] <= min(row[COL_OPEN], row[COL_CLOSE])

    def test_period_is_common_range(self) -> None:
        """
        목적: 기간은 가장 늦은 시작일부터 가장 이른 끝날까지다

        Given: A 는 DAYS[0] – DAYS[5], B 는 DAYS[1] – DAYS[3]
        When: build_daily_rebalanced_composite
        Then: 날짜 = DAYS[1] – DAYS[3]
        """
        # Given
        a = _make_df(DAYS, [100.0, 101.0, 102.0, 103.0, 104.0, 105.0])
        b = _make_df(DAYS[1:4], [50.0, 51.0, 52.0])

        # When
        result = build_daily_rebalanced_composite([(a, 0.75), (b, 0.25)])

        # Then
        assert result[COL_DATE].tolist() == DAYS[1:4]

    def test_date_mismatch_inside_common_range_raises(self) -> None:
        """
        목적: 공통 구간 안에서 한 종목에만 있는 날짜가 있으면 메우지 않고 예외 (보간 금지)

        Given: A 는 DAYS[0] – DAYS[4], B 는 DAYS[2] 가 빠짐
        When: build_daily_rebalanced_composite
        Then: ValueError
        """
        # Given
        a = _make_df(DAYS[:5], [100.0, 101.0, 102.0, 103.0, 104.0])
        b = _make_df([DAYS[0], DAYS[1], DAYS[3], DAYS[4]], [50.0, 51.0, 53.0, 54.0])

        # When / Then
        with pytest.raises(ValueError, match="날짜"):
            build_daily_rebalanced_composite([(a, 0.75), (b, 0.25)])

    def test_no_common_range_raises(self) -> None:
        """
        목적: 겹치는 기간이 없으면 예외

        Given: A 는 DAYS[0] – DAYS[1], B 는 DAYS[3] – DAYS[4]
        When: build_daily_rebalanced_composite
        Then: ValueError
        """
        # Given
        a = _make_df(DAYS[:2], [100.0, 101.0])
        b = _make_df(DAYS[3:5], [50.0, 51.0])

        # When / Then
        with pytest.raises(ValueError, match="겹치는"):
            build_daily_rebalanced_composite([(a, 0.75), (b, 0.25)])

    def test_single_component_raises(self) -> None:
        """
        목적: 구성 종목이 하나면 합성이 아니므로 예외

        Given: 구성 1개
        When: build_daily_rebalanced_composite
        Then: ValueError
        """
        # Given
        a, _ = self._components()

        # When / Then
        with pytest.raises(ValueError, match="구성"):
            build_daily_rebalanced_composite([(a, 1.0)])

    @pytest.mark.parametrize("weights", [(1.0, 0.0), (1.25, -0.25)])
    def test_non_positive_weight_raises(self, weights: tuple[float, float]) -> None:
        """
        목적: 비중은 0 보다 커야 한다

        Given: 비중 0 또는 음수 (합은 1)
        When: build_daily_rebalanced_composite
        Then: ValueError
        """
        # Given
        a, b = self._components()

        # When / Then
        with pytest.raises(ValueError, match="비중"):
            build_daily_rebalanced_composite([(a, weights[0]), (b, weights[1])])

    def test_weights_not_summing_to_one_raises(self) -> None:
        """
        목적: 비중 합은 1 이어야 한다

        Given: 비중 0.7 · 0.25
        When: build_daily_rebalanced_composite
        Then: ValueError
        """
        # Given
        a, b = self._components()

        # When / Then
        with pytest.raises(ValueError, match="비중"):
            build_daily_rebalanced_composite([(a, 0.7), (b, 0.25)])

    def test_volume_is_zero_and_columns_are_required(self) -> None:
        """
        목적: 합성의 거래량은 0 이고 열은 저장 형식(REQUIRED_COLUMNS)이다

        Given: 구성 종목 둘
        When: build_daily_rebalanced_composite
        Then: 거래량 전부 0, 열 순서 = REQUIRED_COLUMNS
        """
        # Given
        a, b = self._components()

        # When
        result = build_daily_rebalanced_composite([(a, 0.75), (b, 0.25)])

        # Then
        assert result[COL_VOLUME].tolist() == [0, 0, 0, 0]
        assert list(result.columns) == REQUIRED_COLUMNS

    def test_inputs_not_mutated(self) -> None:
        """
        목적: 입력 DataFrame 을 바꾸지 않는다

        Given: 구성 종목의 사본
        When: build_daily_rebalanced_composite
        Then: 입력이 사본과 같다
        """
        # Given
        a, b = self._components()
        a_copy, b_copy = a.copy(), b.copy()

        # When
        build_daily_rebalanced_composite([(a, 0.75), (b, 0.25)])

        # Then
        pd.testing.assert_frame_equal(a, a_copy)
        pd.testing.assert_frame_equal(b, b_copy)


class TestInputDateOrder:
    """세 함수 모두 날짜가 중복 없이 오름차순인 입력만 받는다."""

    @staticmethod
    def _unsorted() -> pd.DataFrame:
        return _make_df([DAYS[0], DAYS[2], DAYS[1], DAYS[3]], [10.0, 12.0, 11.0, 13.0])

    @staticmethod
    def _duplicated() -> pd.DataFrame:
        return _make_df([DAYS[0], DAYS[1], DAYS[1], DAYS[2]], [10.0, 11.0, 11.0, 12.0])

    @pytest.mark.parametrize("bad_kind", ["unsorted", "duplicated"])
    def test_rescale_rejects_bad_order(self, bad_kind: str) -> None:
        """
        목적: rescale_to_actual 은 날짜 순서가 틀린 대용을 거부한다

        Given: 정렬되지 않았거나 중복 날짜가 있는 대용
        When: rescale_to_actual
        Then: ValueError
        """
        # Given
        proxy = self._unsorted() if bad_kind == "unsorted" else self._duplicated()
        actual = _make_df(DAYS[2:4], [60.0, 66.0])

        # When / Then
        with pytest.raises(ValueError, match="오름차순"):
            rescale_to_actual(proxy, actual)

    @pytest.mark.parametrize("bad_kind", ["unsorted", "duplicated"])
    def test_splice_rejects_bad_order_in_actual(self, bad_kind: str) -> None:
        """
        목적: splice_proxy 는 날짜 순서가 틀린 실물을 거부한다

        Given: 정렬되지 않았거나 중복 날짜가 있는 실물
        When: splice_proxy
        Then: ValueError
        """
        # Given
        proxy = _make_df(DAYS, [10.0, 11.0, 12.0, 13.0, 14.0, 15.0])
        actual = self._unsorted() if bad_kind == "unsorted" else self._duplicated()

        # When / Then
        with pytest.raises(ValueError, match="오름차순"):
            splice_proxy(proxy, actual)

    @pytest.mark.parametrize("bad_kind", ["unsorted", "duplicated"])
    def test_composite_rejects_bad_order(self, bad_kind: str) -> None:
        """
        목적: build_daily_rebalanced_composite 는 날짜 순서가 틀린 구성 종목을 거부한다

        Given: 정렬되지 않았거나 중복 날짜가 있는 구성 종목
        When: build_daily_rebalanced_composite
        Then: ValueError
        """
        # Given
        good = _make_df(DAYS[:4], [50.0, 51.0, 52.0, 53.0])
        bad = self._unsorted() if bad_kind == "unsorted" else self._duplicated()

        # When / Then
        with pytest.raises(ValueError, match="오름차순"):
            build_daily_rebalanced_composite([(good, 0.75), (bad, 0.25)])
