"""이동평균 유형 정책 테스트

이 프로젝트의 이동평균은 SMA(단순이동평균)로 통일한다.
그 정책이 선언된 세 지점을 고정하고, 선언값이 실제 계산에도 적용되는지 확인한다.

1. 엔진/그리드서치 기본 상수 (`DEFAULT_BUFFER_MA_TYPE`)
2. 포트폴리오 자산 슬롯 기본값 (`AssetSlotConfig.ma_type`)
3. 단일 전략 설정 기본값 (`BufferZoneConfig.ma_type`)

왜 중요한가요?
SMA와 EMA는 같은 `ma_{window}` 컬럼명을 쓰므로 계산 결과만 보고는 어느 쪽인지 알 수 없습니다.
기본값이 조용히 바뀌면 백테스트 수치 전체가 달라지므로 정책을 테스트로 고정합니다.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from qbt.backtest.analysis import add_single_moving_average
from qbt.backtest.constants import DEFAULT_BUFFER_MA_TYPE
from qbt.backtest.portfolio_types import AssetSlotConfig
from qbt.backtest.strategies.buffer_zone import BufferZoneConfig
from qbt.common_constants import COL_CLOSE, COL_DATE, EPSILON

# 경로 필드를 채우기 위한 더미 값. 이 테스트는 파일에 접근하지 않는다.
_DUMMY_PATH = Path("dummy.csv")


def _make_default_slot() -> AssetSlotConfig:
    """`ma_type`을 지정하지 않은 자산 슬롯을 생성한다.

    Returns:
        선택 필드를 모두 기본값으로 둔 `AssetSlotConfig`.
    """
    return AssetSlotConfig(
        asset_id="test_asset",
        signal_data_path=_DUMMY_PATH,
        trade_data_path=_DUMMY_PATH,
        target_weight=1.0,
    )


def _make_default_buffer_zone_config() -> BufferZoneConfig:
    """`ma_type`을 지정하지 않은 단일 전략 설정을 생성한다.

    Returns:
        선택 필드를 모두 기본값으로 둔 `BufferZoneConfig`.
    """
    return BufferZoneConfig(
        strategy_name="test_strategy",
        display_name="테스트 전략",
        signal_data_path=_DUMMY_PATH,
        trade_data_path=_DUMMY_PATH,
        result_dir=_DUMMY_PATH,
    )


class TestMaTypeDefaults:
    """이동평균 유형 기본값 정책 테스트."""

    def test_engine_default_ma_type_is_sma(self) -> None:
        """
        목적: 엔진/그리드서치가 쓰는 기본 MA 유형이 SMA임을 고정한다.

        Given: `DEFAULT_BUFFER_MA_TYPE` 상수
        When:  값을 확인
        Then:  "sma"
        """
        assert DEFAULT_BUFFER_MA_TYPE == "sma"

    def test_asset_slot_default_ma_type_is_sma(self) -> None:
        """
        목적: 포트폴리오 슬롯이 `ma_type`을 생략하면 SMA가 적용됨을 고정한다.

        Given: `ma_type`을 지정하지 않은 `AssetSlotConfig`
        When:  `ma_type` 필드를 확인
        Then:  "sma"
        """
        slot = _make_default_slot()

        assert slot.ma_type == "sma"

    def test_buffer_zone_config_default_ma_type_is_sma(self) -> None:
        """
        목적: 단일 전략 설정이 `ma_type`을 생략하면 SMA가 적용됨을 고정한다.

        Given: `ma_type`을 지정하지 않은 `BufferZoneConfig`
        When:  `ma_type` 필드를 확인
        Then:  "sma"
        """
        config = _make_default_buffer_zone_config()

        assert config.ma_type == "sma"


class TestMaTypeCalculation:
    """기본값이 실제 계산 결과에 반영되는지 검증."""

    def test_slot_default_produces_sma_values(self) -> None:
        """
        목적: 슬롯 기본 `ma_type`으로 계산한 결과가 SMA 값과 일치함을 고정한다.

        선언값만 확인하면 상수는 SMA인데 계산 경로는 EMA인 상태를 놓칠 수 있으므로,
        실제 계산을 거쳐 검증한다. 같은 입력의 EMA(span=3)는 112.5 / 121.25 / 130.625 이므로
        두 방식은 값으로 구분된다.

        Given: 종가 100~140의 5행 데이터와 `ma_type`을 생략한 슬롯
        When:  슬롯의 `ma_type`으로 3일 이동평균 계산
        Then:  단순평균 값(110.0 / 120.0 / 130.0)과 일치
        """
        # Given
        df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 110.0, 120.0, 130.0, 140.0]}
        )
        slot = _make_default_slot()

        # When
        result = add_single_moving_average(df, window=3, ma_type=slot.ma_type)

        # Then: (100+110+120)/3 = 110.0
        assert result.iloc[2]["ma_3"] == pytest.approx(110.0, abs=EPSILON)
        # (110+120+130)/3 = 120.0
        assert result.iloc[3]["ma_3"] == pytest.approx(120.0, abs=EPSILON)
        # (120+130+140)/3 = 130.0
        assert result.iloc[4]["ma_3"] == pytest.approx(130.0, abs=EPSILON)

    def test_slot_default_leaves_warmup_rows_as_nan(self) -> None:
        """
        목적: 워밍업 구간이 NaN으로 남는 SMA 특성을 고정한다 (경계 조건).

        EMA는 첫 행부터 값이 채워지므로, 앞 `window-1`행이 NaN이라는 사실 자체가
        SMA가 적용되었다는 증거가 된다.

        Given: 종가 100~140의 5행 데이터와 `ma_type`을 생략한 슬롯
        When:  슬롯의 `ma_type`으로 3일 이동평균 계산
        Then:  앞 2행(window-1)이 NaN
        """
        # Given
        df = pd.DataFrame(
            {COL_DATE: [date(2023, 1, i + 1) for i in range(5)], COL_CLOSE: [100.0, 110.0, 120.0, 130.0, 140.0]}
        )
        slot = _make_default_slot()

        # When
        result = add_single_moving_average(df, window=3, ma_type=slot.ma_type)

        # Then
        assert pd.isna(result.iloc[0]["ma_3"])
        assert pd.isna(result.iloc[1]["ma_3"])
