"""
QBT Logging Module

로깅 정책:
- DEBUG: 개발 중 상세 정보 (필터링 가능)
- WARNING: 경고성 메시지
- ERROR: 에러 발생 시

로그 포맷: 시간 - 레벨 - 함수명 - 메시지
"""

import logging
import sys
from pathlib import Path


class ClickableFormatter(logging.Formatter):
    """VSCode에서 클릭 가능한 파일 경로를 포함하는 로그 포맷터"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.project_root = self._find_project_root()

    def _find_project_root(self) -> Path:
        """
        pyproject.toml 또는 .git을 찾아 프로젝트 루트 반환

        Returns:
            프로젝트 루트 Path 객체
        """
        current = Path(__file__).resolve().parent

        # 최대 10단계 상위 디렉토리까지 탐색
        for _ in range(10):
            # pyproject.toml 우선 확인 (Poetry 프로젝트)
            if (current / "pyproject.toml").exists():
                return current
            # .git 대체 확인 (Git 저장소)
            if (current / ".git").exists():
                return current

            parent = current.parent
            if parent == current:  # 루트 디렉토리 도달
                break
            current = parent

        # 찾지 못하면 현재 작업 디렉토리 사용
        return Path.cwd()

    def format(self, record):
        """
        로그 레코드에 상대 경로 정보 추가

        Args:
            record: 로그 레코드

        Returns:
            포맷팅된 로그 문자열
        """
        pathname = Path(record.pathname)

        try:
            # 프로젝트 루트 기준 상대 경로 계산
            relative_path = pathname.relative_to(self.project_root)
        except ValueError:
            # 외부 라이브러리는 절대 경로 사용
            relative_path = pathname

        # VSCode 클릭 가능 형식: 파일경로:줄번호
        record.location = f"{relative_path}:{record.lineno}"

        return super().format(record)


def setup_logger(
    name: str = "qbt",
    level: str | None = None,
) -> logging.Logger:
    """
    QBT 프로젝트용 Logger 설정

    Args:
        name: Logger 이름
        level: 로그 레벨 (DEBUG, WARNING, ERROR). None이면 DEBUG 사용

    Returns:
        설정된 Logger 인스턴스
    """
    logger = logging.getLogger(name)

    # 이미 핸들러가 설정되어 있으면 재설정하지 않음
    if logger.handlers:
        return logger

    # 로그 레벨 설정
    if level is None:
        level = "DEBUG"

    log_level = getattr(logging, level.upper(), logging.DEBUG)
    logger.setLevel(log_level)

    # 콘솔 핸들러 생성
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # 포맷 설정 (VSCode 클릭 가능한 형식)
    formatter = ClickableFormatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname)s [%(location)s] [%(funcName)s] : %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    # 핸들러 추가
    logger.addHandler(console_handler)

    # 상위 로거로 전파 방지
    logger.propagate = False

    return logger


def get_logger(name: str = "qbt") -> logging.Logger:
    """
    기존에 설정된 Logger를 가져오거나 새로 설정

    Args:
        name: Logger 이름

    Returns:
        Logger 인스턴스
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # 핸들러가 없으면 기본 설정으로 초기화
        logger = setup_logger(name)
    return logger


def set_log_level(level: str, logger_name: str = "qbt") -> None:
    """
    실행 중 로그 레벨 변경

    Args:
        level: 변경할 로그 레벨 (DEBUG, WARNING, ERROR)
        logger_name: 대상 Logger 이름
    """
    logger = logging.getLogger(logger_name)
    log_level = getattr(logging, level.upper(), logging.DEBUG)
    logger.setLevel(log_level)

    # 핸들러의 레벨도 함께 변경
    for handler in logger.handlers:
        handler.setLevel(log_level)
