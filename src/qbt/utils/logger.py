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

    # 포맷 설정
    formatter = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname)s [%(funcName)s] : %(message)s",
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
