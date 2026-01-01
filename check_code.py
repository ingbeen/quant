#!/usr/bin/env python3
"""
통합 코드 품질 체크 스크립트 (ruff + mypy)

AI가 실행하고 로그를 읽어 문제를 수정할 수 있도록 명확한 출력을 제공합니다.
"""

import subprocess
import sys


def print_section(title: str) -> None:
    """섹션 제목을 출력합니다."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def run_ruff() -> tuple[bool, int]:
    """
    Ruff 린트 체크를 실행합니다.

    Returns:
        tuple[bool, int]: (성공 여부, 오류 개수)
    """
    print_section("1. Ruff 린트 체크")

    result = subprocess.run(
        ["poetry", "run", "ruff", "check", "."],
        capture_output=True,
        text=True,
    )

    # Ruff 출력 표시
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Ruff는 문제가 있으면 exit code 1 반환
    success = result.returncode == 0

    if success:
        print("✓ Ruff 체크 통과")
    else:
        # Ruff 출력에서 오류 개수 추정 (정확한 파싱은 복잡하므로 간단히)
        error_count = result.stdout.count("\n") if result.stdout else 0
        print("✗ Ruff 체크 실패 (오류/경고 발견)")
        return False, error_count

    return True, 0


def run_mypy() -> tuple[bool, int]:
    """
    Mypy 타입 체크를 실행합니다.

    Returns:
        tuple[bool, int]: (성공 여부, 오류 개수)
    """
    print_section("2. Mypy 타입 체크")

    # src/, scripts/, tests/ 전체 체크
    result = subprocess.run(
        ["poetry", "run", "mypy", "src/", "scripts/", "tests/"],
        capture_output=True,
        text=True,
    )

    # Mypy 출력 표시
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Mypy는 오류가 있으면 exit code 1 반환
    success = result.returncode == 0

    # Mypy 출력에서 오류 개수 파싱
    error_count = 0
    if not success and result.stdout:
        # "Found X errors in Y files" 형식 파싱
        for line in result.stdout.split("\n"):
            if "error" in line.lower() and "found" in line.lower():
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.lower() == "found" and i + 1 < len(parts):
                        try:
                            error_count = int(parts[i + 1])
                            break
                        except ValueError:
                            pass

    if success:
        print("✓ Mypy 체크 통과")
    else:
        print(f"✗ Mypy 체크 실패 (오류: {error_count}개)")

    return success, error_count


def main() -> int:
    """
    메인 함수: ruff와 mypy를 순차 실행하고 결과를 집계합니다.

    Returns:
        int: 종료 코드 (0=성공, 1=실패)
    """
    print("\n" + "=" * 80)
    print("  코드 품질 통합 체크 (Ruff + Mypy)")
    print("=" * 80)

    # 1. Ruff 실행
    ruff_success, ruff_errors = run_ruff()

    # 2. Mypy 실행
    mypy_success, mypy_errors = run_mypy()

    # 최종 결과 요약
    print_section("최종 결과")

    total_errors = ruff_errors + mypy_errors
    all_success = ruff_success and mypy_success

    print(f"Ruff:  {'✓ 통과' if ruff_success else f'✗ 실패 (오류/경고: {ruff_errors}개)'}")
    print(f"Mypy:  {'✓ 통과' if mypy_success else f'✗ 실패 (오류: {mypy_errors}개)'}")
    print(f"\n총 오류/경고: {total_errors}개")

    if all_success:
        print("\n🎉 모든 코드 품질 체크 통과!")
        return 0
    else:
        print("\n❌ 코드 품질 체크 실패. 위 오류를 수정해주세요.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
