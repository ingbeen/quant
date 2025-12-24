# QBT 테스트 가이드 (초보자용)

이 문서는 pytest를 처음 사용하는 개발자를 위한 친절한 가이드입니다.

## 목차

1. [테스트가 무엇인가요?](#테스트가-무엇인가요)
2. [설치 방법](#설치-방법)
3. [테스트 실행 방법](#테스트-실행-방법)
4. [테스트 파일 구조](#테스트-파일-구조)
5. [자주 묻는 질문](#자주-묻는-질문)

---

## 테스트가 무엇인가요?

테스트는 **코드가 의도대로 작동하는지 자동으로 확인**하는 작은 프로그램들입니다.

### 왜 테스트를 작성하나요?

1. **버그 조기 발견**: 코드 변경 시 무엇이 깨졌는지 즉시 알 수 있습니다
2. **리팩토링 안전성**: 코드를 개선해도 기능이 유지되는지 확인
3. **문서화**: 테스트를 읽으면 함수가 어떻게 작동하는지 이해 가능
4. **자신감**: 배포 전에 주요 기능이 작동함을 확인

### QBT 프로젝트에서 테스트의 목적

백테스팅 결과는 **데이터의 품질과 계산의 정확성**에 절대적으로 의존합니다.
테스트는 다음을 보장합니다:

- **데이터 신뢰성**: 날짜 정렬, 중복 제거, 필수 컬럼 존재
- **계산 정확성**: CAGR, MDD, 승률 등 핵심 지표
- **안정성**: 파일 부재, 잘못된 파라미터 등 예외 상황 처리
- **회귀 방지**: 코드 변경 후에도 기존 기능 유지

---

## 설치 방법

### Poetry 사용 (권장)

```bash
# 프로젝트 루트 디렉토리에서
poetry add --group dev pytest pytest-cov freezegun
```

### pip 사용

```bash
# 가상환경 활성화 후
pip install pytest pytest-cov freezegun
```

### 패키지 설명

- **pytest**: 테스트 프레임워크 (테스트 실행, 결과 보고)
- **pytest-cov**: 코드 커버리지 측정 (어느 코드가 테스트되었는지)
- **freezegun**: 시간 고정 (결정적 테스트를 위해)

---

## 테스트 실행 방법

### 기본 실행

```bash
# 모든 테스트 실행 (간결한 출력)
pytest -q

# 상세 출력 (각 테스트 이름 표시)
pytest -v

# 아주 상세한 출력 (print 문도 표시)
pytest -s
```

### 특정 테스트만 실행

```bash
# 특정 파일만
pytest tests/test_data_loader.py

# 특정 테스트 함수만
pytest tests/test_data_loader.py::test_load_stock_data_normal

# 특정 클래스의 모든 테스트
pytest tests/test_data_loader.py::TestLoadStockData

# 이름 패턴으로 필터링 (예: "load" 포함된 모든 테스트)
pytest -k "load"
```

### 커버리지 측정

```bash
# 커버리지 리포트와 함께 실행
pytest --cov=src/qbt --cov-report=term-missing

# HTML 리포트 생성 (브라우저로 상세 확인 가능)
pytest --cov=src/qbt --cov-report=html
# 생성된 htmlcov/index.html을 브라우저로 열기
```

### 디버깅

```bash
# 첫 실패 시 즉시 중단
pytest -x

# 실패한 테스트만 재실행
pytest --lf

# 마지막 실패 지점에서 디버거 시작
pytest --pdb

# 로그 출력 보기
pytest --log-cli-level=DEBUG
```

---

## 테스트 파일 구조

### 디렉토리 구조

```
quant/
├── src/qbt/              # 프로덕션 코드
│   ├── utils/
│   ├── backtest/
│   └── tqqq/
├── tests/                # 테스트 코드
│   ├── conftest.py       # 공통 픽스처
│   ├── test_data_loader.py
│   ├── test_meta_manager.py
│   ├── test_analysis.py
│   ├── test_strategy.py
│   └── test_tqqq_simulation.py
```

### 각 파일의 역할

#### conftest.py
- **역할**: 모든 테스트에서 공유하는 픽스처(재사용 가능한 테스트 데이터) 정의
- **포함 내용**:
  - `sample_stock_df`: 기본 주식 데이터
  - `sample_ffr_df`: 금리 데이터
  - `create_csv_file`: CSV 파일 생성 헬퍼
  - `mock_storage_paths`: 임시 디렉토리로 경로 변경

#### test_data_loader.py
- **테스트 대상**: `qbt/utils/data_loader.py`
- **검증 내용**:
  - CSV 파일 로딩
  - 필수 컬럼 검증
  - 날짜 파싱 및 정렬
  - 중복 제거 및 경고 로그

#### test_meta_manager.py
- **테스트 대상**: `qbt/utils/meta_manager.py`
- **검증 내용**:
  - 메타데이터 저장
  - 타임스탬프 기록 (freezegun으로 시간 고정)
  - 이력 개수 제한 (순환 버퍼)

#### test_analysis.py
- **테스트 대상**: `qbt/backtest/analysis.py`
- **검증 내용**:
  - 이동평균 계산
  - 백테스트 성과 지표 (CAGR, MDD, 승률)

#### test_strategy.py
- **테스트 대상**: `qbt/backtest/strategy.py`
- **검증 내용**:
  - Buy & Hold 전략
  - 버퍼존 전략
  - 슬리피지 적용
  - 강제 청산

#### test_tqqq_simulation.py
- **테스트 대상**: `qbt/tqqq/simulation.py`
- **검증 내용**:
  - 일일 비용 계산
  - FFR fallback 로직
  - 레버리지 ETF 시뮬레이션
  - 검증 메트릭

---

## 테스트 읽는 법

### Given-When-Then 패턴

모든 테스트는 다음 구조로 작성되어 있습니다:

```python
def test_example():
    """
    테스트 설명

    Given: 초기 조건 (테스트 데이터 준비)
    When: 실행 (테스트할 함수 호출)
    Then: 검증 (결과가 기대와 일치하는지 확인)
    """
    # Given: 준비
    data = [1, 2, 3]

    # When: 실행
    result = sum(data)

    # Then: 검증
    assert result == 6, "1+2+3은 6이어야 합니다"
```

### 예시 테스트 읽어보기

```python
def test_load_stock_data_normal(self, tmp_path, sample_stock_df):
    """
    정상적인 주식 데이터 로딩 테스트

    Given: 올바른 스키마의 CSV 파일
    When: load_stock_data 호출
    Then: DataFrame이 반환되고, 필수 컬럼이 모두 존재
    """
    # Given: CSV 파일 생성
    csv_path = tmp_path / "AAPL_max.csv"
    sample_stock_df.to_csv(csv_path, index=False)

    # When: 데이터 로딩
    df = load_stock_data(csv_path)

    # Then: 스키마 검증
    assert isinstance(df, pd.DataFrame), "반환값은 DataFrame이어야 합니다"
    assert 'Close' in df.columns, "필수 컬럼 'Close'가 있어야 합니다"
```

**읽는 법**:
1. **docstring**: 이 테스트가 무엇을 검증하는지 먼저 읽기
2. **Given**: 어떤 데이터로 테스트하는지 확인
3. **When**: 어떤 함수를 호출하는지 확인
4. **Then**: 어떤 결과를 기대하는지 확인

---

## 자주 묻는 질문

### Q1: 테스트가 실패하면 어떻게 하나요?

**A**: 실패 메시지를 자세히 읽어보세요!

```
tests/test_data_loader.py::test_load_stock_data_missing_columns FAILED
______________________________ test_load_stock_data_missing_columns ______________________________

    def test_load_stock_data_missing_columns():
>       load_stock_data(csv_path)
E       ValueError: 필수 컬럼이 없습니다: {'Close'}

tests/test_data_loader.py:45: ValueError
```

- `>`: 실패한 코드 라인
- `E`: 예외 메시지 (무엇이 잘못되었는지)
- 파일명:라인번호로 빠르게 해당 코드로 이동 가능

**디버깅 팁**:
1. 실패한 테스트만 다시 실행: `pytest --lf`
2. print 문 추가 후 `-s` 옵션으로 실행: `pytest -s tests/test_data_loader.py::test_name`
3. 디버거 사용: `pytest --pdb`

### Q2: 픽스처(fixture)가 뭔가요?

**A**: 테스트에서 반복적으로 사용하는 데이터를 만드는 함수입니다.

```python
@pytest.fixture
def sample_stock_df():
    return pd.DataFrame({
        'Date': [date(2023, 1, 2), date(2023, 1, 3)],
        'Close': [100.0, 101.0]
    })

def test_something(sample_stock_df):  # 픽스처를 인자로 받음
    # sample_stock_df를 바로 사용 가능
    assert len(sample_stock_df) == 2
```

**장점**:
- 코드 재사용
- 테스트 함수가 간결해짐
- 각 테스트마다 독립적인 데이터 생성 (서로 영향 없음)

### Q3: tmp_path는 무엇인가요?

**A**: pytest가 자동으로 제공하는 임시 디렉토리입니다.

```python
def test_file_creation(tmp_path):
    # tmp_path는 테스트마다 새로 생성되는 임시 폴더
    file_path = tmp_path / "test.csv"
    pd.DataFrame({'A': [1, 2]}).to_csv(file_path)

    # 파일 존재 확인
    assert file_path.exists()

    # 테스트 종료 후 자동 삭제됨 (청소 불필요!)
```

**장점**:
- 실제 파일 시스템 사용 (진짜 파일 I/O 테스트 가능)
- 테스트 간 격리 (각 테스트는 독립적인 폴더 사용)
- 자동 정리 (테스트 후 자동 삭제)

### Q4: caplog는 무엇인가요?

**A**: 로그 메시지를 캡처해서 검증하는 도구입니다.

```python
def test_logging(caplog):
    with caplog.at_level("WARNING"):
        logger.warning("중복된 날짜 발견")

    # 로그가 실제로 찍혔는지 확인
    assert "중복된 날짜" in caplog.text
```

**왜 필요한가요?**
- 중요한 경고나 에러가 제대로 로깅되는지 검증
- 디버깅 시 로그가 유용한지 확인

### Q5: freezegun은 무엇인가요?

**A**: 시간을 고정하는 도구입니다.

```python
from freezegun import freeze_time

@freeze_time("2023-06-15 14:30:00")
def test_timestamp():
    # 이 테스트 안에서는 항상 2023-06-15 14:30:00
    now = datetime.now()
    assert now.year == 2023
    assert now.month == 6
```

**왜 필요한가요?**
- 결정적 테스트: 같은 입력 → 항상 같은 출력
- 메타데이터의 timestamp가 매번 바뀌면 테스트 실패
- freezegun으로 고정하면 예측 가능

### Q6: 테스트를 어떻게 작성하나요?

**A**: 다음 순서로 작성하세요:

1. **함수의 정상 케이스 먼저**
   ```python
   def test_normal_case():
       # 가장 일반적인 사용 사례
   ```

2. **경계 조건**
   ```python
   def test_edge_case():
       # 빈 데이터, 최소/최대 값 등
   ```

3. **에러 케이스**
   ```python
   def test_error_handling():
       with pytest.raises(ValueError):
           # 잘못된 입력 시 에러 발생 확인
   ```

### Q7: assert 메시지는 왜 작성하나요?

**A**: 테스트 실패 시 원인을 빠르게 파악하기 위해!

```python
# 나쁜 예
assert len(df) == 3

# 좋은 예
assert len(df) == 3, "중복 제거 후 행 수가 3이어야 합니다"
```

실패 시 출력:
```
AssertionError: 중복 제거 후 행 수가 3이어야 합니다
```

### Q8: 커버리지가 뭔가요?

**A**: 테스트가 실행한 코드의 비율입니다.

```bash
pytest --cov=src/qbt --cov-report=term-missing
```

출력 예시:
```
Name                          Stmts   Miss  Cover   Missing
-----------------------------------------------------------
src/qbt/utils/data_loader.py     45      5    89%   12-14, 23
```

- **Stmts**: 전체 코드 라인 수
- **Miss**: 테스트가 실행하지 않은 라인 수
- **Cover**: 커버리지 비율 (89%)
- **Missing**: 실행되지 않은 라인 번호 (12-14, 23번 줄)

**목표**: 핵심 로직은 80% 이상 커버리지 권장

---

## 테스트 작성 팁

### 1. 작은 테스트부터 시작

복잡한 함수는 여러 개의 작은 테스트로 나누세요.

```python
# 나쁜 예: 한 테스트에서 모든 것 검증
def test_everything():
    # 정상 케이스, 에러 케이스, 경계 조건 모두...

# 좋은 예: 각각 분리
def test_normal_case():
    # 정상 케이스만

def test_error_case():
    # 에러 케이스만

def test_edge_case():
    # 경계 조건만
```

### 2. 테스트는 독립적이어야 합니다

한 테스트의 결과가 다른 테스트에 영향을 주면 안 됩니다.

```python
# 나쁜 예: 전역 변수 사용
global_data = []

def test_append():
    global_data.append(1)
    assert len(global_data) == 1  # 첫 실행은 통과, 재실행 시 실패!

# 좋은 예: 픽스처 사용
@pytest.fixture
def data():
    return []

def test_append(data):
    data.append(1)
    assert len(data) == 1  # 항상 통과
```

### 3. 명확한 이름 사용

테스트 이름만 보고도 무엇을 테스트하는지 알 수 있어야 합니다.

```python
# 나쁜 예
def test_1():
    ...

# 좋은 예
def test_load_stock_data_with_missing_columns_raises_error():
    ...
```

---

## 다음 단계

1. **모든 테스트 실행**: `pytest -v`
2. **커버리지 확인**: `pytest --cov=src/qbt --cov-report=html`
3. **실패한 테스트 디버깅**: `pytest --pdb`
4. **코드 변경 후 재실행**: `pytest --lf`

테스트를 통해 더 안정적이고 신뢰할 수 있는 백테스팅 도구를 만들어보세요!

---

## 참고 자료

- [pytest 공식 문서](https://docs.pytest.org/)
- [freezegun GitHub](https://github.com/spulec/freezegun)
- [Real Python: Testing Guide](https://realpython.com/pytest-python-testing/)
