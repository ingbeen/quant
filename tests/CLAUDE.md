# tests 폴더 가이드

> 이 문서는 `tests/` 폴더의 테스트 작성 및 실행 규칙에 대한 상세 가이드입니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../CLAUDE.md)를 참고하세요.

## 폴더 목적

tests 폴더는 QBT 프로젝트의 테스트 코드를 관리하며, 핵심 비즈니스 로직의 정확성을 보장합니다.

**폴더 구조**:

```
tests/
├── CLAUDE.md            # tests 관련 규칙 (이 문서)
├── conftest.py          # 공통 픽스처
├── test_*.py            # 테스트 모듈
└── pytest.ini           # pytest 설정
```

---

## 테스트 실행 방법

### 기본 실행

```bash
# 전체 테스트 (권장)
./run_tests.sh
# 또는
poetry run pytest tests/ -v

# 특정 모듈만 실행
./run_tests.sh strategy
# 또는
poetry run pytest tests/test_strategy.py -v

# 커버리지 포함
./run_tests.sh cov
# 또는 HTML 리포트 생성
./run_tests.sh html

# 실패한 테스트만 재실행
poetry run pytest --lf

# 디버깅 모드 (print 출력 포함)
poetry run pytest tests/test_xxx.py -s -vv

# 도움말
./run_tests.sh help
```

### 품질 게이트 커맨드

프로젝트 수준의 품질 검증:

```bash
# 테스트
./run_tests.sh

# 커버리지
./run_tests.sh cov

# 린트
poetry run ruff check .

# 포맷
poetry run black --check .
```

---

## 테스트 작성 원칙

### 1. 핵심 로직 보호

백테스트/시뮬레이션의 핵심 계산 로직은 반드시 테스트로 보호합니다:

- 이동평균 계산
- 수익률 산출
- 거래 신호 생성
- 비용 모델
- 레버리지 효과

### 2. Given-When-Then 패턴

모든 테스트는 명확한 3단계 구조를 따릅니다:

```python
def test_example(self):
    """
    테스트 설명

    Given: 초기 조건
    When: 실행할 동작
    Then: 기대하는 결과
    """
    # Given: 테스트 데이터 준비
    df = pd.DataFrame({
        'Date': [date(2023, 1, 1), date(2023, 1, 2)],
        'Close': [100.0, 101.0]
    })

    # When: 함수 실행
    result = function_under_test(df)

    # Then: 결과 검증
    assert expected_condition
```

### 3. 경계 조건 테스트

정상 케이스뿐만 아니라 엣지 케이스도 테스트:

- 빈 데이터
- 극단값 (0, 음수, 매우 큰 값)
- 경계 조건 (윈도우 크기 부족, 자본 부족 등)

### 4. 결정적 테스트 (Deterministic)

테스트는 항상 같은 결과를 보장해야 합니다:

```python
from freezegun import freeze_time

@freeze_time("2023-06-15 14:30:00")
def test_with_fixed_time(self):
    # 시간이 고정되어 타임스탬프가 항상 동일
    save_metadata("grid_results", {"test": "data"})
```

**주요 기법**:

- 시간 고정: `@freeze_time` 사용
- 파일 격리: `tmp_path` 픽스처 사용
- 랜덤성 제거: 시드 고정 또는 결정적 데이터 사용

### 5. 파일 격리

테스트는 실제 파일에 영향을 주지 않아야 합니다:

```python
def test_with_temp_files(self, mock_storage_paths):
    # tmp_path를 사용하여 테스트 후 자동 삭제
    meta_path = mock_storage_paths['META_JSON_PATH']
    # 테스트 실행...
```

### 6. 문서화

모든 테스트는 초보자도 이해할 수 있도록 주석 포함:

- docstring에 목적/조건/결과 명시
- 복잡한 로직은 인라인 주석
- Python 기초 문법 설명 (필요시)

---

## 주요 픽스처 (conftest.py)

모든 테스트에서 사용하는 공통 설정과 테스트 데이터:

- `sample_stock_df`: 기본 주식 데이터
- `sample_ffr_df`: FFR 금리 데이터 (yyyy-mm 문자열 형식)
- `create_csv_file`: CSV 파일 생성 헬퍼
- `mock_storage_paths`: 임시 경로 설정 (파일 격리)

---

## tests 폴더 운영 원칙

1. **테스트 코드만 유지**: tests 폴더는 테스트 코드(.py) 중심
2. **임시 문서는 금지**: 작업 중 생성된 임시 문서는 `docs/archive/`로
3. **커버리지 목표**: 핵심 모듈 최대한 높게 유지

---

## 커버리지

### 현재 커버리지 확인

```bash
poetry run pytest --cov=src/qbt --cov-report=term-missing tests/
```

### HTML 리포트 생성

```bash
poetry run pytest --cov=src/qbt --cov-report=html tests/
# 결과: htmlcov/index.html 브라우저로 열기
```

**목표**:

- 핵심 모듈: 최대한 높은 커버리지 유지
- 전체 프로젝트: 지속적 개선

---

## 자주 발생하는 문제

### 1. 컬럼명 불일치

```python
# 잘못된 예
df['Equity']  # 대문자

# 올바른 예
df['equity']  # 소문자 (실제 프로덕션 코드 확인!)
```

**중요**: 프로덕션 코드의 실제 컬럼명을 반드시 확인하세요.

### 2. FFR 데이터 형식

```python
# 잘못된 예
'DATE': [date(2023, 1, 1)]  # date 객체

# 올바른 예
'DATE': ['2023-01']  # yyyy-mm 문자열
```

### 3. 파라미터 단위

```python
# 잘못된 예
buffer_zone_pct=3.0  # 퍼센트

# 올바른 예
buffer_zone_pct=0.03  # 비율 (3%)
```

### 4. 함수 시그니처

프로덕션 코드가 데이터클래스를 사용하는 경우, 테스트도 동일한 구조를 사용해야 합니다.

### 5. 타임스탬프 검증

ISO 8601 형식을 고려하여 타임스탬프를 검증하세요 (`freezegun` 사용 권장).

---

## 테스트 작성 체크리스트

테스트 작성 전 확인사항:

- [ ] 프로덕션 코드의 실제 시그니처 확인
- [ ] 실제 반환값 구조 확인
- [ ] 실제 컬럼명 확인
- [ ] 실제 에러 메시지 확인
- [ ] Given-When-Then 패턴 사용
- [ ] 엣지 케이스 포함
- [ ] 결정적 테스트 (시간/파일 격리)
- [ ] 명확한 주석 및 docstring

---

## 지속적 개선

### 새 기능 추가 시

1. **테스트 먼저 작성** (TDD)

   ```python
   # 1. 실패하는 테스트 작성
   def test_new_feature(self):
       result = new_feature()
       assert result == expected

   # 2. 기능 구현
   # 3. 테스트 통과 확인
   ```

2. **기존 테스트 실행**
   ```bash
   poetry run pytest tests/ -v  # 회귀 방지
   ```

### 버그 발견 시

1. **재현 테스트 작성**

   ```python
   def test_bug_reproduction(self):
       # 버그를 재현하는 테스트
       # 먼저 실패하는지 확인
   ```

2. **버그 수정**

3. **테스트 통과 확인**

---

**사용 중인 플러그인**:

- **pytest-cov**: 코드 커버리지 측정
- **freezegun**: 시간 고정 (결정적 테스트)
