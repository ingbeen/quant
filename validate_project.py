#!/usr/bin/env python3
"""
통합 품질 검증 스크립트 (Ruff + PyRight + Pytest)

프로젝트의 모든 품질 검증을 단일 진입점으로 실행합니다.
AI가 실행하고 로그를 읽어 문제를 수정할 수 있도록 명확한 출력을 제공합니다.

사용법:
    poetry run python validate_project.py                # 전체 실행 (Ruff + PyRight + Pytest)
    poetry run python validate_project.py --only-lint    # Ruff만 실행
    poetry run python validate_project.py --only-pyright # PyRight만 실행
    poetry run python validate_project.py --only-tests   # Pytest만 실행
    poetry run python validate_project.py --cov          # Pytest + 커버리지만 실행
"""

import argparse
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
        return True, 0

    # Ruff 출력에서 오류 개수 파싱: "Found X error." 또는 "Found X errors."
    error_count = 0
    if result.stdout:
        for line in result.stdout.split("\n"):
            # "Found 1 error." 또는 "Found X errors." 형식 파싱
            if "Found" in line and "error" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "Found" and i + 1 < len(parts):
                        try:
                            error_count = int(parts[i + 1])
                            break
                        except ValueError:
                            pass
                if error_count > 0:
                    break

    # 파싱 실패 시 기본값 1 (실패했지만 개수를 알 수 없음)
    if error_count == 0:
        error_count = 1

    print(f"✗ Ruff 체크 실패 (오류/경고: {error_count}개)")
    return False, error_count


def run_pyright() -> tuple[bool, int]:
    """
    PyRight 타입 체크를 실행합니다.

    Returns:
        tuple[bool, int]: (성공 여부, 오류 개수)
    """
    result = subprocess.run(
        ["poetry", "run", "pyright"],
        capture_output=True,
        text=True,
    )

    # PyRight 출력 표시
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # PyRight는 오류가 있으면 exit code 1 반환
    success = result.returncode == 0

    if success:
        print("✓ PyRight 체크 통과")
        return True, 0

    # PyRight 출력에서 오류 개수 파싱: "X error, Y warnings, Z informations"
    error_count = 0
    if result.stdout:
        for line in result.stdout.split("\n"):
            # "1 error, 0 warnings, 0 informations" 형식 파싱
            if "error" in line and ("warning" in line or "information" in line):
                parts = line.split()
                # 첫 번째 숫자가 error 개수
                for part in parts:
                    try:
                        error_count = int(part)
                        break
                    except ValueError:
                        pass
                if error_count > 0:
                    break

    # 파싱 실패 시 기본값 1 (실패했지만 개수를 알 수 없음)
    if error_count == 0:
        error_count = 1

    print(f"✗ PyRight 체크 실패 (오류: {error_count}개)")
    return False, error_count


def run_pytest(with_coverage: bool = False) -> tuple[bool, int, int, int]:
    """
    Pytest 테스트를 실행합니다.

    Args:
        with_coverage: True일 경우 커버리지 포함 실행

    Returns:
        tuple[bool, int, int, int]: (성공 여부, passed 수, failed 수, skipped 수)
    """
    if with_coverage:
        cmd = ["poetry", "run", "pytest", "--cov=src/qbt", "--cov-report=term-missing", "tests/", "-v"]
    else:
        cmd = ["poetry", "run", "pytest", "tests/", "-v"]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    # Pytest 출력 표시
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # Pytest는 실패가 있으면 exit code 1 반환
    success = result.returncode == 0

    # Pytest 출력에서 passed/failed/skipped 파싱
    passed = 0
    failed = 0
    skipped = 0
    if result.stdout:
        for line in result.stdout.split("\n"):
            # "= 10 passed, 2 failed, 1 skipped in 0.50s =" 형식 파싱
            # 또는 "= 10 passed in 0.50s =" 형식
            if "passed" in line or "failed" in line or "skipped" in line:
                parts = line.split()
                i = 0
                while i < len(parts):
                    try:
                        # 숫자 다음에 passed/failed/skipped가 오는 패턴 찾기
                        if i + 1 < len(parts):
                            num = int(parts[i])
                            next_part = parts[i + 1].rstrip(",")
                            if next_part == "passed":
                                passed = num
                            elif next_part == "failed":
                                failed = num
                            elif next_part == "skipped":
                                skipped = num
                    except ValueError:
                        pass
                    i += 1
                # 유효한 파싱이 되었으면 종료
                if passed > 0 or failed > 0 or skipped > 0:
                    break

    if success:
        print(f"✓ Pytest 통과 (passed={passed}, failed={failed}, skipped={skipped})")
    else:
        print(f"✗ Pytest 실패 (passed={passed}, failed={failed}, skipped={skipped})")

    return success, passed, failed, skipped


def parse_args() -> argparse.Namespace:
    """명령행 인자를 파싱합니다."""
    parser = argparse.ArgumentParser(
        description="통합 품질 검증 스크립트 (Ruff + PyRight + Pytest)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  poetry run python validate_project.py                # 전체 실행 (Ruff + PyRight + Pytest)
  poetry run python validate_project.py --only-lint    # Ruff만 실행
  poetry run python validate_project.py --only-pyright # PyRight만 실행
  poetry run python validate_project.py --only-tests   # Pytest만 실행
  poetry run python validate_project.py --cov          # Pytest + 커버리지만 실행

참고:
  --only-* 옵션들은 상호 배타적입니다. 하나만 선택할 수 있습니다.
  --cov 옵션은 단독으로 사용하거나 --only-tests와 함께 사용할 수 있습니다.
        """,
    )

    only_group = parser.add_mutually_exclusive_group()
    only_group.add_argument(
        "--only-lint",
        action="store_true",
        help="Ruff 린트 체크만 실행",
    )
    only_group.add_argument(
        "--only-pyright",
        action="store_true",
        help="PyRight 타입 체크만 실행",
    )
    only_group.add_argument(
        "--only-tests",
        action="store_true",
        help="Pytest 테스트만 실행",
    )

    parser.add_argument(
        "--cov",
        action="store_true",
        help="커버리지 포함 테스트만 실행 (단독 사용 시 Ruff, PyRight 제외)",
    )

    return parser.parse_args()


def main() -> int:
    """
    메인 함수: 옵션에 따라 Ruff, PyRight, Pytest를 실행하고 결과를 집계합니다.

    Returns:
        int: 종료 코드 (0=성공, 1=실패)
    """
    args = parse_args()

    # --cov 옵션 검증
    if args.cov and (args.only_lint or args.only_pyright):
        print("오류: --cov 옵션은 --only-lint, --only-pyright와 함께 사용할 수 없습니다.")
        return 1

    # 실행할 도구 결정
    if args.cov:
        # --cov 옵션: 테스트 + 커버리지만 실행
        should_run_lint = False
        should_run_pyright = False
        should_run_tests = True
    else:
        # 전체 실행인지 개별 도구 실행인지 판단
        is_only_mode = args.only_lint or args.only_pyright or args.only_tests

        should_run_lint = args.only_lint or not is_only_mode
        should_run_pyright = args.only_pyright or not is_only_mode
        should_run_tests = args.only_tests or not is_only_mode

    # 타이틀 생성
    tools = []
    if should_run_lint:
        tools.append("Ruff")
    if should_run_pyright:
        tools.append("PyRight")
    if should_run_tests:
        tools.append("Pytest")
    title = f"프로젝트 품질 검증 ({' + '.join(tools)})"

    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

    # 결과 수집
    results = {}
    section_num = 1

    # 1. Ruff 실행
    if should_run_lint:
        print_section(f"{section_num}. Ruff 린트 체크")
        section_num += 1
        ruff_success, ruff_errors = run_ruff()
        results["ruff"] = (ruff_success, ruff_errors)

    # 2. PyRight 실행
    if should_run_pyright:
        print_section(f"{section_num}. PyRight 타입 체크")
        section_num += 1
        pyright_success, pyright_errors = run_pyright()
        results["pyright"] = (pyright_success, pyright_errors)

    # 3. Pytest 실행
    if should_run_tests:
        print_section(f"{section_num}. Pytest 테스트")
        section_num += 1
        pytest_success, passed, failed, skipped = run_pytest(with_coverage=args.cov)
        results["pytest"] = (pytest_success, passed, failed, skipped)

    # 최종 결과 요약
    print_section("최종 결과")

    total_errors = 0
    all_success = True

    if "ruff" in results:
        ruff_success, ruff_errors = results["ruff"]
        total_errors += ruff_errors
        all_success &= ruff_success
        print(f"Ruff:    {'✓ 통과' if ruff_success else f'✗ 실패 (오류/경고: {ruff_errors}개)'}")

    if "pyright" in results:
        pyright_success, pyright_errors = results["pyright"]
        total_errors += pyright_errors
        all_success &= pyright_success
        print(f"PyRight: {'✓ 통과' if pyright_success else f'✗ 실패 (오류: {pyright_errors}개)'}")

    if "pytest" in results:
        pytest_success, passed, failed, skipped = results["pytest"]
        total_errors += failed
        all_success &= pytest_success
        print(f"Pytest:  {'✓ 통과' if pytest_success else '✗ 실패'} (passed={passed}, failed={failed}, skipped={skipped})")

    print(f"\n총 오류/경고: {total_errors}개")

    if all_success:
        print("\n🎉 모든 품질 검증 통과!")
        return 0
    else:
        print("\n❌ 품질 검증 실패. 위 오류를 수정해주세요.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
