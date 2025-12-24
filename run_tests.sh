#!/bin/bash

# QBT 테스트 실행 스크립트
# 다양한 테스트 실행 옵션 제공

set -e  # 에러 발생 시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 함수: 헬프 메시지
show_help() {
    echo -e "${BLUE}QBT 테스트 실행 스크립트${NC}"
    echo ""
    echo "사용법: ./run_tests.sh [옵션]"
    echo ""
    echo "옵션:"
    echo "  all              전체 테스트 실행 (기본값)"
    echo "  analysis         analysis 모듈 테스트만"
    echo "  data             data_loader 모듈 테스트만"
    echo "  meta             meta_manager 모듈 테스트만"
    echo "  strategy         strategy 모듈 테스트만"
    echo "  tqqq             tqqq_simulation 모듈 테스트만"
    echo "  cov              커버리지 포함 실행"
    echo "  html             커버리지 HTML 리포트 생성"
    echo "  fast             실패한 테스트만 재실행"
    echo "  help             이 도움말 표시"
    echo ""
    echo "예시:"
    echo "  ./run_tests.sh              # 전체 테스트"
    echo "  ./run_tests.sh strategy     # strategy 모듈만"
    echo "  ./run_tests.sh cov          # 커버리지 포함"
}

# 함수: 테스트 실행
run_test() {
    local test_path=$1
    local description=$2

    echo -e "${YELLOW}▶ ${description}${NC}"
    poetry run pytest ${test_path} -v

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 테스트 통과${NC}"
    else
        echo -e "${RED}✗ 테스트 실패${NC}"
        exit 1
    fi
}

# 인자가 없으면 all로 설정
OPTION=${1:-all}

case $OPTION in
    all)
        echo -e "${BLUE}전체 테스트 실행${NC}"
        run_test "tests/" "전체 테스트 스위트"
        ;;

    analysis)
        run_test "tests/test_analysis.py" "백테스트 분석 테스트"
        ;;

    data)
        run_test "tests/test_data_loader.py" "데이터 로더 테스트"
        ;;

    meta)
        run_test "tests/test_meta_manager.py" "메타데이터 관리 테스트"
        ;;

    strategy)
        run_test "tests/test_strategy.py" "백테스트 전략 테스트"
        ;;

    tqqq)
        run_test "tests/test_tqqq_simulation.py" "TQQQ 시뮬레이션 테스트"
        ;;

    cov)
        echo -e "${BLUE}커버리지 포함 테스트 실행${NC}"
        poetry run pytest --cov=src/qbt --cov-report=term-missing tests/ -v
        ;;

    html)
        echo -e "${BLUE}커버리지 HTML 리포트 생성${NC}"
        poetry run pytest --cov=src/qbt --cov-report=html tests/ -v
        echo -e "${GREEN}✓ HTML 리포트 생성 완료: htmlcov/index.html${NC}"
        ;;

    fast)
        echo -e "${BLUE}실패한 테스트만 재실행${NC}"
        poetry run pytest --lf -v
        ;;

    help|--help|-h)
        show_help
        ;;

    *)
        echo -e "${RED}✗ 알 수 없는 옵션: $OPTION${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}테스트 실행 완료${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
