"""터미널 출력 포맷팅 유틸리티

한글/영문 혼용 시 터미널 폭을 정확히 계산하여 정렬한다.
"""

import logging
from enum import Enum


class Align(Enum):
    """텍스트 정렬 방향을 나타내는 열거형"""

    LEFT = "left"
    RIGHT = "right"
    CENTER = "center"


def get_display_width(text: str) -> int:
    """
    문자열의 실제 터미널 출력 폭을 계산한다.

    한글, 한자 등 동아시아 문자는 2칸, 영문/숫자/기호는 1칸으로 계산한다.

    Args:
        text: 폭을 계산할 문자열

    Returns:
        터미널에서 차지하는 실제 폭 (칸 수)
    """
    width = 0
    for char in text:
        # 한글, 한자 등 동아시아 문자는 2칸
        if ord(char) > 0x1100:
            width += 2
        else:
            width += 1
    return width


def format_cell(text: str, width: int, align: Align = Align.LEFT) -> str:
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
    content_width = get_display_width(content)
    available_padding = width - content_width

    # 폭이 부족한 경우 원본 반환
    if available_padding <= 0:
        return content

    # 정렬 방향에 따라 패딩 적용
    if align == Align.LEFT:
        return content + " " * available_padding

    if align == Align.RIGHT:
        return " " * available_padding + content

    # CENTER: 좌우 균등 분배
    left_padding = available_padding // 2
    right_padding = available_padding - left_padding
    return " " * left_padding + content + " " * right_padding


def format_row(cells: list[tuple[str, int, Align]], indent: int = 2) -> str:
    """
    여러 셀을 한 번에 포맷팅하여 행을 생성한다.

    Args:
        cells: [(텍스트, 폭, 정렬), ...] 튜플 리스트
        indent: 들여쓰기 칸 수

    Returns:
        포맷팅된 행 문자열
    """
    formatted_cells = [format_cell(text, width, align) for text, width, align in cells]
    return " " * indent + "".join(formatted_cells)


class TableLogger:
    """테이블 형식으로 로그를 출력하는 클래스

    컬럼 정의를 받아서 테이블 구조를 설정하고, 헤더/데이터/푸터를 출력합니다.
    한글/영문 혼용 시 터미널 폭을 정확히 계산하여 정렬합니다.

    Examples:
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

    def __init__(
        self,
        columns: list[tuple[str, int, Align]],
        logger: logging.Logger,
        indent: int = 2
    ) -> None:
        """
        TableLogger를 초기화한다.

        Args:
            columns: [(컬럼명, 폭, 정렬), ...] 튜플 리스트
            logger: 로거 인스턴스
            indent: 들여쓰기 칸 수
        """
        self.columns = columns
        self.logger = logger
        self.indent = indent
        self._total_width = indent + sum(width for _, width, _ in columns)

    def print_header(self, title: str | None = None) -> None:
        """
        테이블 헤더를 출력한다.

        상단 구분선, 제목(선택), 컬럼 헤더, 구분선을 출력합니다.

        Args:
            title: 테이블 제목 (None이면 제목 없음)
        """
        # 상단 구분선
        self.logger.debug("=" * self._total_width)

        # 제목 (있는 경우)
        if title:
            self.logger.debug(title)

        # 컬럼 헤더
        header_cells = [(name, width, align) for name, width, align in self.columns]
        header_line = format_row(header_cells, self.indent)
        self.logger.debug(header_line)

        # 헤더 하단 구분선
        self.logger.debug("-" * self._total_width)

    def print_row(self, data: list) -> None:
        """
        데이터 행을 출력한다.

        Args:
            data: 컬럼 순서대로 정렬된 데이터 리스트

        Raises:
            ValueError: 데이터 길이가 컬럼 수와 일치하지 않는 경우
        """
        if len(data) != len(self.columns):
            raise ValueError(
                f"데이터 길이({len(data)})가 컬럼 수({len(self.columns)})와 일치하지 않습니다"
            )

        cells = [
            (str(value), width, align)
            for value, (_, width, align) in zip(data, self.columns)
        ]
        row_line = format_row(cells, self.indent)
        self.logger.debug(row_line)

    def print_footer(self) -> None:
        """테이블 푸터(하단 구분선)를 출력한다."""
        self.logger.debug("=" * self._total_width)

    def print_table(self, rows: list, title: str | None = None) -> None:
        """
        전체 테이블을 출력한다.

        헤더, 모든 데이터 행, 푸터를 한 번에 출력합니다.

        Args:
            rows: 데이터 행 리스트 (각 행은 컬럼 순서대로 정렬된 리스트)
            title: 테이블 제목 (None이면 제목 없음)
        """
        self.print_header(title)
        for row in rows:
            self.print_row(row)
        self.print_footer()
