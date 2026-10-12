"""formatting.py 모듈 테스트

터미널 출력 포맷팅 기능의 계약을 검증한다.

테스트 대상:
- _get_display_width(): 문자열 터미널 폭 계산
- _format_cell(): 셀 정렬 (LEFT/RIGHT)
- _format_row(): 행 포맷팅
- TableLogger: 테이블 출력 클래스
- Align: 정렬 방향 enum
"""

import logging
from io import StringIO

import pytest

from qbt.utils.formatting import Align, TableLogger, _format_cell, _format_row, _get_display_width


class TestGetDisplayWidth:
    """_get_display_width() 함수 테스트

    목적: 한글/영문 혼용 문자열의 터미널 폭을 정확히 계산하는지 검증
    """

    def test_empty_string(self):
        """
        빈 문자열의 폭은 0이어야 한다.

        Given: 빈 문자열
        When: _get_display_width() 호출
        Then: 0 반환
        """
        # Given
        text = ""

        # When
        width = _get_display_width(text)

        # Then
        assert width == 0

    def test_english_only(self):
        """
        영문/숫자/기호는 각 1칸으로 계산된다.

        Given: 영문 문자열 "Hello123!@#"
        When: _get_display_width() 호출
        Then: 11 반환 (각 문자 1칸씩)
        """
        # Given
        text = "Hello123!@#"

        # When
        width = _get_display_width(text)

        # Then
        assert width == 11

    def test_korean_only(self):
        """
        한글은 각 2칸으로 계산된다.

        Given: 한글 문자열 "안녕하세요"
        When: _get_display_width() 호출
        Then: 10 반환 (5글자 × 2칸)
        """
        # Given
        text = "안녕하세요"

        # When
        width = _get_display_width(text)

        # Then
        assert width == 10

    def test_mixed_korean_english(self):
        """
        한글과 영문이 혼용된 경우 정확히 계산된다.

        Given: "Hello안녕123" (영문5칸 + 한글4칸 + 숫자3칸)
        When: _get_display_width() 호출
        Then: 12 반환
        """
        # Given
        text = "Hello안녕123"

        # When
        width = _get_display_width(text)

        # Then
        # "Hello" (5) + "안녕" (4) + "123" (3) = 12
        assert width == 12


class TestFormatCell:
    """_format_cell() 함수 테스트

    목적: 셀 정렬(LEFT/RIGHT)과 폭 부족 케이스 검증
    """

    def test_left_align_english(self):
        """
        영문 문자열 왼쪽 정렬 시 오른쪽에 패딩이 추가된다.

        Given: "ABC", width=10, align=LEFT
        When: _format_cell() 호출
        Then: "ABC       " 반환 (3글자 + 7칸 패딩)
        """
        # Given
        text = "ABC"
        width = 10
        align = Align.LEFT

        # When
        result = _format_cell(text, width, align)

        # Then
        assert result == "ABC       "
        assert len(result) == 10

    def test_right_align_english(self):
        """
        영문 문자열 오른쪽 정렬 시 왼쪽에 패딩이 추가된다.

        Given: "ABC", width=10, align=RIGHT
        When: _format_cell() 호출
        Then: "       ABC" 반환 (7칸 패딩 + 3글자)
        """
        # Given
        text = "ABC"
        width = 10
        align = Align.RIGHT

        # When
        result = _format_cell(text, width, align)

        # Then
        assert result == "       ABC"
        assert len(result) == 10

    def test_left_align_korean(self):
        """
        한글 문자열 왼쪽 정렬 시 터미널 폭 기준으로 패딩이 추가된다.

        Given: "안녕" (4칸), width=10, align=LEFT
        When: _format_cell() 호출
        Then: "안녕      " 반환 (한글 2글자(4칸) + 6칸 패딩)
        """
        # Given
        text = "안녕"
        width = 10
        align = Align.LEFT

        # When
        result = _format_cell(text, width, align)

        # Then
        # "안녕"은 4칸, 나머지 6칸은 공백
        assert result == "안녕      "
        # 실제 문자 길이는 2 + 6 = 8이지만, 터미널 폭은 10
        assert _get_display_width(result) == 10

    def test_insufficient_width(self):
        """
        폭이 부족한 경우 원본 문자열을 그대로 반환한다.

        Given: "VeryLongText", width=5 (부족)
        When: _format_cell() 호출
        Then: "VeryLongText" 반환 (잘림 없음)
        """
        # Given
        text = "VeryLongText"
        width = 5

        # When
        result = _format_cell(text, width, Align.LEFT)

        # Then
        assert result == text

    def test_exact_width(self):
        """
        문자열 폭이 목표 폭과 정확히 일치하면 패딩 없이 반환한다.

        Given: "ABC", width=3
        When: _format_cell() 호출
        Then: "ABC" 반환 (패딩 없음)
        """
        # Given
        text = "ABC"
        width = 3

        # When
        result = _format_cell(text, width, Align.LEFT)

        # Then
        assert result == "ABC"
        assert len(result) == 3


class TestFormatRow:
    """_format_row() 함수 테스트

    목적: 다중 셀 포맷팅과 들여쓰기(2칸) 검증
    """

    def test_single_cell(self):
        """
        단일 셀 행 포맷팅 시 들여쓰기가 적용된다.

        Given: cells=[("ABC", 10, LEFT)]
        When: _format_row() 호출
        Then: "  ABC       " 반환 (2칸 들여쓰기 + 셀)
        """
        # Given
        cells = [("ABC", 10, Align.LEFT)]

        # When
        result = _format_row(cells)

        # Then
        assert result == "  ABC       "

    def test_multiple_cells(self):
        """
        다중 셀 행 포맷팅 시 각 셀이 정렬되어 연결된다.

        Given: cells=[("A", 5, LEFT), ("B", 5, RIGHT)]
        When: _format_row() 호출
        Then: "  A        B" 반환
        """
        # Given
        cells = [("A", 5, Align.LEFT), ("B", 5, Align.RIGHT)]

        # When
        result = _format_row(cells)

        # Then
        # indent(2) + "A    " + "    B"
        assert result == "  A        B"


class TestTableLogger:
    """TableLogger 클래스 테스트

    목적: 테이블 출력 줄과 컬럼 수 불일치 예외 검증
    """

    @pytest.fixture
    def mock_logger(self):
        """테스트용 로거 픽스처

        StringIO를 사용하여 로그 출력을 캡처한다.
        """
        logger = logging.getLogger("test_table_logger")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []  # 기존 핸들러 제거

        # StringIO 핸들러 추가 (로그 출력 캡처)
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        return logger, stream

    def test_print_table_with_title(self, mock_logger):
        """
        전체 테이블 출력 시 구분선, 제목, 헤더, 구분선, 모든 행, 구분선이 순서대로 출력된다.

        Given: 컬럼 정의(폭 10 · 8), 행 2개, title="명단"
        When: print_table() 호출
        Then: 7줄이 정해진 모양으로 출력된다 — 헤더와 행 모두 2칸 들여쓰기에서 시작한다
        """
        # Given
        logger, stream = mock_logger
        columns = [("이름", 10, Align.LEFT), ("나이", 8, Align.RIGHT)]
        table = TableLogger(columns, logger)
        rows = [["홍길동", 30], ["김철수", 25]]

        # When
        table.print_table(rows, title="명단")

        # Then
        assert stream.getvalue().splitlines() == [
            "=" * 20,
            "명단",
            "  이름          나이",
            "-" * 20,
            "  홍길동          30",
            "  김철수          25",
            "=" * 20,
        ]

    def test_print_table_without_title(self, mock_logger):
        """
        제목 없는 테이블 출력 시 제목 줄이 빠진다.

        Given: 컬럼 정의, 행 1개, title=None
        When: print_table() 호출
        Then: 구분선, 헤더, 구분선, 행, 구분선 5줄 출력
        """
        # Given
        logger, stream = mock_logger
        table = TableLogger([("이름", 10, Align.LEFT)], logger)

        # When
        table.print_table([["홍길동"]])

        # Then
        assert stream.getvalue().splitlines() == ["=" * 12, "  이름      ", "-" * 12, "  홍길동    ", "=" * 12]

    def test_all_lines_are_logged_from_same_function(self, mock_logger):
        """
        목적: 표의 모든 줄이 같은 함수에서 찍히는지 검증
              — 로그 포맷이 함수 이름을 넣어, 헤더와 행을 다른 메서드가 찍으면 이름 길이 차이만큼 열이 어긋난다

        Given: 함수 이름을 앞에 붙이는 로그 포맷
        When: print_table() 호출
        Then: 모든 줄의 함수 이름이 같다
        """
        # Given
        logger, stream = mock_logger
        logger.handlers[0].setFormatter(logging.Formatter("[%(funcName)s] %(message)s"))
        table = TableLogger([("이름", 10, Align.LEFT), ("나이", 8, Align.RIGHT)], logger)

        # When
        table.print_table([["홍길동", 30]], title="명단")

        # Then
        func_names = {line.split("] ", 1)[0] for line in stream.getvalue().splitlines()}
        assert func_names == {"[print_table"}

    def test_row_column_mismatch(self, mock_logger):
        """
        데이터 길이가 컬럼 수와 일치하지 않으면 ValueError가 발생하고 아무 줄도 출력하지 않는다.

        Given: 컬럼 2개, 둘째 행의 data 3개
        When: print_table() 호출
        Then: ValueError 발생, 출력 없음
        """
        # Given
        logger, stream = mock_logger
        columns = [("이름", 10, Align.LEFT), ("나이", 8, Align.RIGHT)]
        table = TableLogger(columns, logger)

        # When & Then
        with pytest.raises(ValueError, match="데이터 길이.*컬럼 수"):
            table.print_table([["김철수", 25], ["홍길동", 30, "추가"]])
        assert stream.getvalue() == ""
