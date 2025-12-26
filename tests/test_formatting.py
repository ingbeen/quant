"""formatting.py 모듈 테스트

터미널 출력 포맷팅 기능의 계약을 검증한다.

테스트 대상:
- get_display_width(): 문자열 터미널 폭 계산
- format_cell(): 셀 정렬 (LEFT/RIGHT/CENTER)
- format_row(): 행 포맷팅
- TableLogger: 테이블 출력 클래스
- Align: 정렬 방향 enum
"""

import logging
from io import StringIO

import pytest

from qbt.utils.formatting import Align, TableLogger, format_cell, format_row, get_display_width


class TestGetDisplayWidth:
    """get_display_width() 함수 테스트

    목적: 한글/영문 혼용 문자열의 터미널 폭을 정확히 계산하는지 검증
    """

    def test_empty_string(self):
        """
        빈 문자열의 폭은 0이어야 한다.

        Given: 빈 문자열
        When: get_display_width() 호출
        Then: 0 반환
        """
        # Given
        text = ""

        # When
        width = get_display_width(text)

        # Then
        assert width == 0

    def test_english_only(self):
        """
        영문/숫자/기호는 각 1칸으로 계산된다.

        Given: 영문 문자열 "Hello123!@#"
        When: get_display_width() 호출
        Then: 11 반환 (각 문자 1칸씩)
        """
        # Given
        text = "Hello123!@#"

        # When
        width = get_display_width(text)

        # Then
        assert width == 11

    def test_korean_only(self):
        """
        한글은 각 2칸으로 계산된다.

        Given: 한글 문자열 "안녕하세요"
        When: get_display_width() 호출
        Then: 10 반환 (5글자 × 2칸)
        """
        # Given
        text = "안녕하세요"

        # When
        width = get_display_width(text)

        # Then
        assert width == 10

    def test_mixed_korean_english(self):
        """
        한글과 영문이 혼용된 경우 정확히 계산된다.

        Given: "Hello안녕123" (영문5칸 + 한글4칸 + 숫자3칸)
        When: get_display_width() 호출
        Then: 12 반환
        """
        # Given
        text = "Hello안녕123"

        # When
        width = get_display_width(text)

        # Then
        # "Hello" (5) + "안녕" (4) + "123" (3) = 12
        assert width == 12


class TestFormatCell:
    """format_cell() 함수 테스트

    목적: 셀 정렬(LEFT/RIGHT/CENTER)과 폭 부족 케이스 검증
    """

    def test_left_align_english(self):
        """
        영문 문자열 왼쪽 정렬 시 오른쪽에 패딩이 추가된다.

        Given: "ABC", width=10, align=LEFT
        When: format_cell() 호출
        Then: "ABC       " 반환 (3글자 + 7칸 패딩)
        """
        # Given
        text = "ABC"
        width = 10
        align = Align.LEFT

        # When
        result = format_cell(text, width, align)

        # Then
        assert result == "ABC       "
        assert len(result) == 10

    def test_right_align_english(self):
        """
        영문 문자열 오른쪽 정렬 시 왼쪽에 패딩이 추가된다.

        Given: "ABC", width=10, align=RIGHT
        When: format_cell() 호출
        Then: "       ABC" 반환 (7칸 패딩 + 3글자)
        """
        # Given
        text = "ABC"
        width = 10
        align = Align.RIGHT

        # When
        result = format_cell(text, width, align)

        # Then
        assert result == "       ABC"
        assert len(result) == 10

    def test_center_align_english(self):
        """
        영문 문자열 중앙 정렬 시 좌우에 패딩이 균등 분배된다.

        Given: "ABC", width=10, align=CENTER
        When: format_cell() 호출
        Then: "   ABC    " 반환 (좌 3칸 + 3글자 + 우 4칸)
        """
        # Given
        text = "ABC"
        width = 10
        align = Align.CENTER

        # When
        result = format_cell(text, width, align)

        # Then
        # 좌우 패딩 균등 분배: 7칸 / 2 = 좌 3칸, 우 4칸
        assert result == "   ABC    "
        assert len(result) == 10

    def test_left_align_korean(self):
        """
        한글 문자열 왼쪽 정렬 시 터미널 폭 기준으로 패딩이 추가된다.

        Given: "안녕" (4칸), width=10, align=LEFT
        When: format_cell() 호출
        Then: "안녕      " 반환 (한글 2글자(4칸) + 6칸 패딩)
        """
        # Given
        text = "안녕"
        width = 10
        align = Align.LEFT

        # When
        result = format_cell(text, width, align)

        # Then
        # "안녕"은 4칸, 나머지 6칸은 공백
        assert result == "안녕      "
        # 실제 문자 길이는 2 + 6 = 8이지만, 터미널 폭은 10
        assert get_display_width(result) == 10

    def test_insufficient_width(self):
        """
        폭이 부족한 경우 원본 문자열을 그대로 반환한다.

        Given: "VeryLongText", width=5 (부족)
        When: format_cell() 호출
        Then: "VeryLongText" 반환 (잘림 없음)
        """
        # Given
        text = "VeryLongText"
        width = 5

        # When
        result = format_cell(text, width, Align.LEFT)

        # Then
        assert result == text

    def test_exact_width(self):
        """
        문자열 폭이 목표 폭과 정확히 일치하면 패딩 없이 반환한다.

        Given: "ABC", width=3
        When: format_cell() 호출
        Then: "ABC" 반환 (패딩 없음)
        """
        # Given
        text = "ABC"
        width = 3

        # When
        result = format_cell(text, width, Align.LEFT)

        # Then
        assert result == "ABC"
        assert len(result) == 3


class TestFormatRow:
    """format_row() 함수 테스트

    목적: 다중 셀 포맷팅과 들여쓰기 검증
    """

    def test_single_cell(self):
        """
        단일 셀 행 포맷팅 시 들여쓰기가 적용된다.

        Given: cells=[("ABC", 10, LEFT)], indent=2
        When: format_row() 호출
        Then: "  ABC       " 반환 (2칸 들여쓰기 + 셀)
        """
        # Given
        cells = [("ABC", 10, Align.LEFT)]
        indent = 2

        # When
        result = format_row(cells, indent)

        # Then
        assert result == "  ABC       "

    def test_multiple_cells(self):
        """
        다중 셀 행 포맷팅 시 각 셀이 정렬되어 연결된다.

        Given: cells=[("A", 5, LEFT), ("B", 5, RIGHT)]
        When: format_row() 호출
        Then: "  A        B" 반환
        """
        # Given
        cells = [("A", 5, Align.LEFT), ("B", 5, Align.RIGHT)]
        indent = 2

        # When
        result = format_row(cells, indent)

        # Then
        # indent(2) + "A    " + "    B"
        assert result == "  A        B"

    def test_zero_indent(self):
        """
        들여쓰기가 0인 경우 셀만 출력된다.

        Given: cells=[("ABC", 5, LEFT)], indent=0
        When: format_row() 호출
        Then: "ABC  " 반환 (들여쓰기 없음)
        """
        # Given
        cells = [("ABC", 5, Align.LEFT)]
        indent = 0

        # When
        result = format_row(cells, indent)

        # Then
        assert result == "ABC  "


class TestTableLogger:
    """TableLogger 클래스 테스트

    목적: 테이블 헤더/행/푸터 출력 및 컬럼 수 불일치 예외 검증
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

    def test_print_header_without_title(self, mock_logger):
        """
        제목 없는 헤더 출력 시 구분선과 컬럼명만 출력된다.

        Given: 컬럼 정의, title=None
        When: print_header() 호출
        Then: 상단 구분선, 컬럼 헤더, 하단 구분선 출력
        """
        # Given
        logger, stream = mock_logger
        columns = [("이름", 10, Align.LEFT), ("나이", 8, Align.RIGHT)]
        table = TableLogger(columns, logger, indent=2)

        # When
        table.print_header()

        # Then
        output = stream.getvalue()
        lines = output.strip().split("\n")

        # 3줄 출력: 상단 구분선, 헤더, 하단 구분선
        assert len(lines) == 3
        # 상단 구분선: "=" * (indent + sum(widths)) = "=" * 20
        assert "=" in lines[0]
        # 헤더: "  이름      나이    "
        assert "이름" in lines[1]
        assert "나이" in lines[1]
        # 하단 구분선: "-" * 20
        assert "-" in lines[2]

    def test_print_header_with_title(self, mock_logger):
        """
        제목이 있는 헤더 출력 시 제목도 함께 출력된다.

        Given: 컬럼 정의, title="테스트 테이블"
        When: print_header() 호출
        Then: 상단 구분선, 제목, 컬럼 헤더, 하단 구분선 출력
        """
        # Given
        logger, stream = mock_logger
        columns = [("이름", 10, Align.LEFT)]
        table = TableLogger(columns, logger, indent=2)

        # When
        table.print_header(title="테스트 테이블")

        # Then
        output = stream.getvalue()
        lines = output.strip().split("\n")

        # 4줄 출력: 상단 구분선, 제목, 헤더, 하단 구분선
        assert len(lines) == 4
        assert "테스트 테이블" in lines[1]

    def test_print_row(self, mock_logger):
        """
        데이터 행 출력 시 각 셀이 정렬되어 출력된다.

        Given: 컬럼 정의, data=["홍길동", 30]
        When: print_row() 호출
        Then: 정렬된 행이 출력됨
        """
        # Given
        logger, stream = mock_logger
        columns = [("이름", 10, Align.LEFT), ("나이", 8, Align.RIGHT)]
        table = TableLogger(columns, logger, indent=2)

        # When
        table.print_row(["홍길동", 30])

        # Then
        output = stream.getvalue()
        assert "홍길동" in output
        assert "30" in output

    def test_print_row_column_mismatch(self, mock_logger):
        """
        데이터 길이가 컬럼 수와 일치하지 않으면 ValueError가 발생한다.

        Given: 컬럼 2개, data 3개
        When: print_row() 호출
        Then: ValueError 발생
        """
        # Given
        logger, stream = mock_logger
        columns = [("이름", 10, Align.LEFT), ("나이", 8, Align.RIGHT)]
        table = TableLogger(columns, logger, indent=2)

        # When & Then
        with pytest.raises(ValueError, match="데이터 길이.*컬럼 수"):
            table.print_row(["홍길동", 30, "추가"])

    def test_print_footer(self, mock_logger):
        """
        푸터 출력 시 하단 구분선이 출력된다.

        Given: 컬럼 정의
        When: print_footer() 호출
        Then: "=" * total_width 출력
        """
        # Given
        logger, stream = mock_logger
        columns = [("이름", 10, Align.LEFT)]
        table = TableLogger(columns, logger, indent=2)

        # When
        table.print_footer()

        # Then
        output = stream.getvalue()
        assert "=" in output

    def test_print_table(self, mock_logger):
        """
        전체 테이블 출력 시 헤더, 모든 행, 푸터가 순서대로 출력된다.

        Given: 컬럼 정의, rows 데이터
        When: print_table() 호출
        Then: 헤더 + 행들 + 푸터 출력
        """
        # Given
        logger, stream = mock_logger
        columns = [("이름", 10, Align.LEFT), ("나이", 8, Align.RIGHT)]
        table = TableLogger(columns, logger, indent=2)
        rows = [["홍길동", 30], ["김철수", 25]]

        # When
        table.print_table(rows, title="명단")

        # Then
        output = stream.getvalue()
        lines = output.strip().split("\n")

        # 최소 7줄: 상단 구분선, 제목, 헤더, 하단 구분선, 행1, 행2, 푸터
        assert len(lines) >= 7
        assert "명단" in output
        assert "홍길동" in output
        assert "김철수" in output


class TestAlign:
    """Align enum 테스트

    목적: enum 값 접근과 사용 검증
    """

    def test_enum_values(self):
        """
        Align enum의 각 값이 올바르게 정의되어 있다.

        Given: Align enum
        When: 각 값 접근
        Then: 예상된 문자열 값 반환
        """
        # Given & When & Then
        assert Align.LEFT.value == "left"
        assert Align.RIGHT.value == "right"
        assert Align.CENTER.value == "center"

    def test_enum_comparison(self):
        """
        Align enum 값끼리 비교 가능하다.

        Given: Align enum 값들
        When: == 비교
        Then: 동일한 값은 True, 다른 값은 False
        """
        # Given & When & Then
        assert Align.LEFT == Align.LEFT
        assert Align.LEFT != Align.RIGHT
        assert Align.RIGHT != Align.CENTER
