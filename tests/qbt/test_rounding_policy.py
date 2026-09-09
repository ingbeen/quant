"""가격 반올림 자릿수 정책 테스트

결과 파일에 저장하는 가격은 소수점 4자리를 넘기지 않는다.
자릿수는 `ROUND_PRICE` 하나로 관리하며, 각 저장 지점에 숫자를 직접 적는 방식은 쓰지 않는다.

왜 중요한가요?
소수점 5자리 이하는 실제 시세에 존재하지 않는 부동소수점 표현 잡음입니다
(수집한 시세 파일에 `44.490002`·`44.919998` 형태로 실제로 들어 있습니다).
결과를 차트와 대조할 때 그대로 방해가 되므로 상한을 두었으며, 이 테스트가 그 상한을 고정합니다.
자릿수를 되돌리면 이 테스트가 실패합니다.
"""

from qbt.backtest.constants import ROUND_PRICE

MAX_PRICE_DECIMALS = 4


class TestPriceRoundingUpperBound:
    """가격 반올림 자릿수의 상한을 고정."""

    def test_round_price_does_not_exceed_upper_bound(self) -> None:
        """
        목적: 가격 자릿수가 4자리 상한을 넘지 않음을 고정한다.

        Given: 백테스트 도메인의 가격 반올림 상수
        When:  상한값과 비교
        Then:  4자리 이하
        """
        # Given / When
        actual = ROUND_PRICE

        # Then
        assert actual <= MAX_PRICE_DECIMALS
