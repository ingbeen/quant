"""이동평균 유형 정책 테스트

이 프로젝트의 이동평균은 SMA(단순이동평균) 하나뿐이다.
`add_single_moving_average`는 유형을 고르는 파라미터를 갖지 않으며, 항상 단순이동평균을 계산한다.

왜 중요한가요?
EMA와 SMA 중 무엇을 쓸지 고르는 행위 자체가 과최적화 자유도로 계산됩니다
(`docs/research/전략_검증_보고서.md` §5.3 및 부록 G).
선택지를 코드에서 없애 그 자유도를 봉인했으며, 이 테스트가 그 상태를 고정합니다.
파라미터가 다시 생기면 첫 번째 테스트가 실패합니다.
"""

import inspect
from datetime import date

import pandas as pd
import pytest

from qbt.backtest.analysis import add_single_moving_average
from qbt.common_constants import COL_CLOSE, COL_DATE, EPSILON


def _make_close_df() -> pd.DataFrame:
    """종가 100~140의 5행 데이터를 만든다.

    3일 이동평균의 손계산이 쉬운 값으로 골랐다.
    단순평균은 110.0 / 120.0 / 130.0 이고, 같은 입력의 EMA(span=3)는 112.5 / 121.25 / 130.625 이므로
    두 방식은 결과값으로 구분된다.

    Returns:
        `Date`와 `Close` 컬럼을 가진 5행 DataFrame.
    """
    return pd.DataFrame(
        {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 110.0, 120.0, 130.0, 140.0]}
    )


class TestMaTypeParameterIsRemoved:
    """이동평균 유형 선택 파라미터가 존재하지 않음을 고정."""

    def test_signature_has_no_ma_type_parameter(self) -> None:
        """
        목적: 이동평균 유형을 고르는 파라미터가 공개 API에 없음을 고정한다.

        선택지를 되살리는 변경(예: 편의를 위한 `ma_type` 재도입)은
        과최적화 자유도를 다시 늘리므로 이 테스트로 막는다.

        Given: `add_single_moving_average` 함수
        When:  시그니처의 파라미터 목록을 조회
        Then:  `ma_type`이 존재하지 않음
        """
        # Given / When
        parameters = inspect.signature(add_single_moving_average).parameters

        # Then
        assert "ma_type" not in parameters


class TestMovingAverageIsSma:
    """계산 결과가 항상 단순이동평균임을 고정."""

    def test_produces_sma_values(self) -> None:
        """
        목적: 계산 결과가 단순평균 값과 일치함을 고정한다.

        Given: 종가 100~140의 5행 데이터
        When:  3일 이동평균 계산
        Then:  단순평균 값(110.0 / 120.0 / 130.0)과 일치
        """
        # Given
        df = _make_close_df()

        # When
        result = add_single_moving_average(df, window=3)

        # Then: (100+110+120)/3 = 110.0
        assert result.iloc[2]["ma_3"] == pytest.approx(110.0, abs=EPSILON)
        # (110+120+130)/3 = 120.0
        assert result.iloc[3]["ma_3"] == pytest.approx(120.0, abs=EPSILON)
        # (120+130+140)/3 = 130.0
        assert result.iloc[4]["ma_3"] == pytest.approx(130.0, abs=EPSILON)

    def test_leaves_warmup_rows_as_nan(self) -> None:
        """
        목적: 워밍업 구간이 NaN으로 남는 단순이동평균 특성을 고정한다 (경계 조건).

        창이 차기 전에는 값을 내지 않는 것이 이 프로젝트의 정책이다.
        지수이동평균은 첫 행부터 값이 채워지므로, 앞 `window-1`행이 NaN이라는 사실 자체가
        단순이동평균이 적용되었다는 증거가 된다.

        Given: 종가 100~140의 5행 데이터
        When:  3일 이동평균 계산
        Then:  앞 2행(window-1)이 NaN
        """
        # Given
        df = _make_close_df()

        # When
        result = add_single_moving_average(df, window=3)

        # Then
        assert pd.isna(result.iloc[0]["ma_3"])
        assert pd.isna(result.iloc[1]["ma_3"])
