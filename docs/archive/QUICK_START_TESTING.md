# 테스트 빠른 시작 가이드

이 문서는 5분 안에 테스트를 실행할 수 있도록 안내합니다.

## 1단계: 필요한 패키지 설치

프로젝트 루트 디렉토리에서 다음 명령어를 실행하세요:

```bash
cd /home/leeyubeen/workspace/quant

# Poetry로 개발 의존성 설치
poetry add --group dev pytest pytest-cov freezegun
```

**예상 소요 시간**: 1-2분

## 2단계: 테스트 실행

### 방법 1: 직접 pytest 실행

```bash
# 모든 테스트 실행 (간결한 출력)
poetry run pytest -q

# 상세 출력으로 실행
poetry run pytest -v
```

### 방법 2: 편리한 스크립트 사용

```bash
# 스크립트에 실행 권한 부여 (최초 1회만)
chmod +x run_tests.sh

# 전체 테스트 실행
./run_tests.sh

# 커버리지 측정
./run_tests.sh coverage

# 도움말 보기
./run_tests.sh help
```

## 3단계: 결과 확인

### 성공 시

```
====================================== test session starts ======================================
platform linux -- Python 3.10.x, pytest-7.x.x
collected 50 items

tests/test_data_loader.py ........                                                        [ 16%]
tests/test_meta_manager.py .....                                                          [ 26%]
tests/test_analysis.py .......                                                            [ 40%]
tests/test_strategy.py ..........                                                         [ 60%]
tests/test_tqqq_simulation.py ....................                                        [100%]

====================================== 50 passed in 2.50s =======================================
```

### 실패 시

실패 메시지를 읽고 해당 파일로 이동하여 확인하세요:

```
tests/test_data_loader.py::test_load_stock_data_missing_columns FAILED
______________________________ test_load_stock_data_missing_columns ______________________________

    def test_load_stock_data_missing_columns():
>       load_stock_data(csv_path)
E       ValueError: 필수 컬럼이 없습니다: {'Close'}

tests/test_data_loader.py:45: ValueError
```

## 4단계: 커버리지 확인 (선택)

```bash
# 커버리지 측정
poetry run pytest --cov=src/qbt --cov-report=term-missing

# HTML 리포트 생성 (브라우저로 보기)
poetry run pytest --cov=src/qbt --cov-report=html
# 생성된 htmlcov/index.html을 브라우저로 열기
```

## 주요 명령어 요약

| 명령어 | 설명 |
|--------|------|
| `pytest -q` | 간결한 출력으로 전체 테스트 실행 |
| `pytest -v` | 상세 출력 (각 테스트 이름 표시) |
| `pytest -s` | print 문 출력 포함 |
| `pytest -k "data_loader"` | 이름에 "data_loader" 포함된 테스트만 |
| `pytest --lf` | 이전에 실패한 테스트만 재실행 |
| `pytest --cov=src/qbt` | 커버리지 측정 |
| `./run_tests.sh` | 스크립트로 실행 (간편) |

## 문제 해결

### Q: ModuleNotFoundError가 발생합니다

**A**: PYTHONPATH를 설정하세요:

```bash
export PYTHONPATH=/home/leeyubeen/workspace/quant/src:$PYTHONPATH
poetry run pytest -v
```

또는 pytest.ini에 추가:

```ini
[pytest]
pythonpath = src
```

### Q: 일부 테스트가 실패합니다

**A**: 프로덕션 코드와 테스트 가정이 다를 수 있습니다. 다음을 확인하세요:

1. **함수 시그니처**: 프로덕션 코드의 함수 인자가 테스트와 일치하는지
2. **예외 타입**: 실제로 발생하는 예외가 테스트에서 기대한 것과 같은지
3. **컬럼명**: 실제 DataFrame 컬럼명이 테스트에서 사용한 것과 일치하는지

실패한 테스트를 하나씩 디버깅:

```bash
# 특정 테스트만 실행
pytest tests/test_data_loader.py::test_load_stock_data_normal -v

# print 문 출력 보기
pytest tests/test_data_loader.py::test_load_stock_data_normal -s

# 디버거로 실행
pytest tests/test_data_loader.py::test_load_stock_data_normal --pdb
```

### Q: 테스트 실행이 너무 느립니다

**A**: 병렬 실행을 시도하세요:

```bash
# pytest-xdist 설치
poetry add --group dev pytest-xdist

# 병렬 실행
poetry run pytest -n auto
```

## 다음 단계

1. **모든 테스트가 통과하면**: `tests/README_TESTS.md`를 읽고 테스트 작성법 학습
2. **일부 실패하면**: 실패 원인 분석 후 필요 시 테스트 수정
3. **새 기능 추가 시**: 테스트 먼저 작성 (TDD 방식)

## 도움이 필요하면

- **초보자 가이드**: `tests/README_TESTS.md`
- **전체 요약**: `TESTING_SUMMARY.md`
- **pytest 공식 문서**: https://docs.pytest.org/

행운을 빕니다! 🚀
