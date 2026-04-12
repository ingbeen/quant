"""주가 데이터 검증 3종.

yfinance 로부터 받은 최근 OHLC 데이터를 CSV 에 append 하기 전에 수행하는 3 가지
순수 함수 검증을 제공한다. 본 모듈은 이상 발견 시 예외를 직접 발생시키지 않고
**에러 메시지 리스트를 반환**한다. 호출자(CLI) 가 리스트가 비어있지 않으면 즉시
중단 + 알림을 발송한다.

검증 종류:

1. :func:`validate_ohlc_logic` — OHLC 내부 논리 (High < Low, 가격 0/음수, Close 범위)
2. :func:`validate_prev_close` — 전일 종가 연속성 (1% 이상 차이는 스플릿 의심)
3. :func:`validate_date_gap` — 거래일 누락 (NYSE 달력 기준)

원칙:

- 보간 금지. 이상 발견 시 메시지만 반환하고 호출자가 중단 여부를 결정한다.
- 자동 복구 없음.
- 에러 메시지에는 구체 수치/날짜 포함 (사용자 디버깅 용이).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from live.constants import PREV_CLOSE_DIFF_THRESHOLD
from qbt.common_constants import COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN

__all__ = [
    "validate_ohlc_logic",
    "validate_prev_close",
    "validate_date_gap",
]


def validate_ohlc_logic(row: pd.Series | pd.DataFrame) -> list[str]:
    """1 행 OHLC 의 내부 논리를 검증한다.

    검증 항목:

    - High < Low → 에러
    - Open / High / Low / Close 중 하나라도 0 또는 음수 → 에러
    - Close 가 High 보다 크거나 Low 보다 작으면 → 에러

    Args:
        row: OHLC 필드를 포함한 Series 또는 1 행 DataFrame.

    Returns:
        에러 메시지 리스트. 빈 리스트이면 통과.
    """
    errors: list[str] = []

    if isinstance(row, pd.DataFrame):
        if len(row) != 1:
            return [f"validate_ohlc_logic 입력은 1 행이어야 한다. 실제: {len(row)} 행"]
        series = row.iloc[0]
    else:
        series = row

    try:
        open_ = float(series[COL_OPEN])
        high = float(series[COL_HIGH])
        low = float(series[COL_LOW])
        close = float(series[COL_CLOSE])
    except (KeyError, ValueError, TypeError) as exc:
        return [f"OHLC 필드 접근 실패: {exc}"]

    # 1. 가격 0 / 음수 검사
    for name, value in ((COL_OPEN, open_), (COL_HIGH, high), (COL_LOW, low), (COL_CLOSE, close)):
        if value <= 0:
            errors.append(f"OHLC 이상: {name}={value} (0 또는 음수)")

    # 2. High / Low 순서 검사
    if high < low:
        errors.append(f"OHLC 논리 오류: High({high}) < Low({low})")

    # 3. Close 가 High~Low 범위 안에 있는지
    if high >= low and not (low <= close <= high):
        errors.append(f"OHLC 논리 오류: Close({close}) 가 [Low={low}, High={high}] 범위 밖")

    # 4. Open 도 범위 검사 (보조)
    if high >= low and not (low <= open_ <= high):
        errors.append(f"OHLC 논리 오류: Open({open_}) 가 [Low={low}, High={high}] 범위 밖")

    return errors


def validate_prev_close(csv_close: float, yf_close: float) -> list[str]:
    """전일 종가 연속성을 검증한다 (스플릿/무상증자 감지).

    CSV 의 마지막 종가와 yfinance 가 돌려주는 "같은 날짜" 의 종가가 1% 이상
    차이나면 스플릿이 의심되므로 즉시 중단한다.

    Args:
        csv_close: 기존 CSV 의 마지막 종가.
        yf_close: yfinance 가 반환한 동일 날짜 종가.

    Returns:
        에러 메시지 리스트. 빈 리스트이면 통과.
    """
    errors: list[str] = []

    if csv_close <= 0:
        return [f"validate_prev_close: csv_close 는 양수여야 함. 입력: {csv_close}"]
    if yf_close <= 0:
        return [f"validate_prev_close: yf_close 는 양수여야 함. 입력: {yf_close}"]

    diff_ratio = abs(yf_close - csv_close) / csv_close
    if diff_ratio >= PREV_CLOSE_DIFF_THRESHOLD:
        errors.append("전일 종가 불일치 (스플릿 의심): " f"CSV={csv_close}, yfinance={yf_close}, 차이율={diff_ratio:.4%}")
    return errors


def validate_date_gap(csv_last: date, today: date, calendar: Any) -> list[str]:
    """CSV 마지막 날짜와 오늘 사이에 누락된 거래일이 있는지 검증한다.

    ``exchange_calendars`` NYSE 달력을 사용하여 두 날짜 사이(양 끝 제외) 에 열려
    있었던 거래일 수를 조회한다. 하나 이상 있으면 누락으로 간주한다.

    Args:
        csv_last: 기존 CSV 의 마지막 거래일.
        today: 현재 거래일 (append 대상).
        calendar: ``exchange_calendars.ExchangeCalendar`` 인스턴스 (테스트 주입 가능).

    Returns:
        에러 메시지 리스트.
    """
    if csv_last >= today:
        # 이상 상태 (미래 날짜 이미 저장됨 등) — 본 검증 대상 아님
        return []

    # (csv_last, today) 사이의 거래일 조회 — 양 끝 모두 제외
    start = csv_last + timedelta(days=1)
    end = today - timedelta(days=1)
    if start > end:
        return []

    try:
        sessions = calendar.sessions_in_range(
            pd.Timestamp(start),
            pd.Timestamp(end),
        )
    except Exception as exc:  # noqa: BLE001
        return [f"거래일 달력 조회 실패: {exc}"]

    if len(sessions) == 0:
        return []

    missing_dates = [s.date().isoformat() for s in sessions]
    return ["거래일 누락: " f"CSV 마지막={csv_last.isoformat()}, 오늘={today.isoformat()}, " f"누락된 거래일={missing_dates}"]
