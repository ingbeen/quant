"""터미널 출력 포맷팅 유틸리티

한글/영문 혼용 시 터미널 폭을 정확히 계산하여 정렬한다.
"""

import logging
import unicodedata
from collections.abc import Sequence
from enum import Enum

_INDENT = 2


class Align(Enum):
    """텍스트 정렬 방향을 나타내는 열거형"""

    LEFT = "left"  # 왼쪽 정렬
    RIGHT = "right"  # 오른쪽 정렬


def _get_display_width(text: str) -> int:
    """
    문자열의 실제 터미널 출력 폭을 계산한다.

    unicodedata.east_asian_width를 사용하여 문자폭을 정확히 계산한다.
    - W (Wide), F (Fullwidth): 2칸
    - 나머지 (Na, H, N, A): 1칸

    Args:
        text: 폭을 계산할 문자열

    Returns:
        터미널에서 차지하는 실제 폭 (칸 수)
    """
    width = 0

    for char in text:
        ea_width = unicodedata.east_asian_width(char)
        if ea_width in ("W", "F"):
            width += 2  # 전각 문자 (한글, 한자, 전각 기호 등)
        else:
            width += 1  # 반각 문자 (영문, 숫자, 반각 기호 등)

    return width


def _format_cell(text: str, width: int, align: Align = Align.LEFT) -> str:
    """
    터미널 폭을 고려하여 문자열을 정렬한다.

    한글과 영문이 섞인 문자열도 올바르게 정렬한다.

    Args:
        text: 정렬할 문자열
        width: 목표 폭 (칸 수)
        align: 정렬 방향 (Align enum)

    Returns:
        정렬된 문자열
    """
    content = str(text)
    content_width = _get_display_width(content)
    available_padding = width - content_width

    # 폭이 부족한 경우 원본 반환
    if available_padding <= 0:
        return content

    if align == Align.LEFT:
        return content + " " * available_padding

    return " " * available_padding + content


def _format_row(cells: list[tuple[str, int, Align]]) -> str:
    """
    여러 셀을 한 번에 포맷팅하여 행을 생성한다.

    Args:
        cells: [(텍스트, 폭, 정렬), ...] 튜플 리스트

    Returns:
        포맷팅된 행 문자열 (왼쪽에 들여쓰기 포함)
    """
    formatted_cells = [_format_cell(text, width, align) for text, width, align in cells]
    return " " * _INDENT + "".join(formatted_cells)


class TableLogger:
    """테이블 형식으로 로그를 출력하는 클래스

    컬럼 정의를 받아서 테이블 구조를 설정하고, 헤더/데이터/푸터를 출력합니다.
    한글/영문 혼용 시 터미널 폭을 정확히 계산하여 정렬합니다.

    Examples:
        >>> # 컬럼 정의: (컬럼명, 폭, 정렬) 튜플의 리스트
        >>> columns = [
        ...     ("날짜", 12, Align.LEFT),
        ...     ("가격", 12, Align.RIGHT),
        ...     ("변동률", 10, Align.RIGHT),
        ... ]
        >>> table = TableLogger(columns, logger)
        >>> rows = [
        ...     ["2024-01-01", "100.50", "+2.5%"],
        ...     ["2024-01-02", "102.00", "+1.5%"],
        ... ]
        >>> table.print_table(rows, title="가격 변동 내역")
    """

    def __init__(self, columns: list[tuple[str, int, Align]], logger: logging.Logger) -> None:
        """
        TableLogger를 초기화한다.

        Args:
            columns: [(컬럼명, 폭, 정렬), ...] 튜플 리스트
            logger: 로거 인스턴스
        """
        self.columns = columns
        self.logger = logger
        self._total_width = _INDENT + sum(width for _, width, _ in columns)

    def print_table(self, rows: Sequence[Sequence[str | int | float]], title: str | None = None) -> None:
        """
        전체 테이블을 출력한다.

        상단 구분선, 제목(선택), 컬럼 헤더, 구분선, 데이터 행, 하단 구분선을 순서대로 출력합니다.
        모든 줄을 이 메서드 안에서 찍는다 — 로그 포맷이 함수 이름을 넣으므로, 헤더와 행을 서로 다른 메서드가
        찍으면 이름 길이 차이만큼 열이 어긋난다.

        Args:
            rows: 데이터 행 시퀀스 (각 행은 컬럼 순서대로 정렬된 시퀀스, str 외 타입은 str 변환)
            title: 테이블 제목 (None이면 제목 없음)

        Raises:
            ValueError: 행의 데이터 길이가 컬럼 수와 일치하지 않는 경우 (아무 줄도 찍지 않는다)
        """
        lines = ["=" * self._total_width]
        if title:
            lines.append(title)
        lines.append(_format_row(self.columns))
        lines.append("-" * self._total_width)

        for data in rows:
            if len(data) != len(self.columns):
                raise ValueError(f"데이터 길이({len(data)})가 컬럼 수({len(self.columns)})와 일치하지 않습니다")
            cells = [(str(value), width, align) for value, (_, width, align) in zip(data, self.columns, strict=True)]
            lines.append(_format_row(cells))

        lines.append("=" * self._total_width)

        for line in lines:
            self.logger.debug(line)
