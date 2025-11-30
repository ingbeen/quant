"""터미널 출력 포맷팅 유틸리티

한글/영문 혼용 시 터미널 폭을 정확히 계산하여 정렬한다.
"""

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
