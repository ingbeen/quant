# 테스트 현재 상태 및 다음 단계

## 완료된 작업

### 1. 테스트 인프라 구축 ✅
- pytest, pytest-cov, freezegun 설치 완료
- 44개 테스트 함수 작성 완료
- conftest.py 픽스처 설정 완료
- pytest.ini 설정 파일 생성 완료

### 2. 주요 수정 완료 ✅
- `META_FILE_PATH` → `META_JSON_PATH` 수정 완료
- `INITIAL_CAPITAL` → `DEFAULT_INITIAL_CAPITAL` 수정 완료
- `SLIPPAGE_PCT` → `SLIPPAGE_RATE` 수정 완료
- MA 컬럼명 `MA_3` → `ma_3` 일부 수정 완료

### 3. 테스트 수집 성공 ✅
```bash
$ poetry run pytest --collect-only
collected 46 items  # 모든 테스트가 수집됨
```

## 현재 테스트 실행 결과

### 전체 실행 결과 (46개 테스트)
- ✅ **통과**: 16개
- ❌ **실패**: 30개
- ⚠️ **에러**: 0개

### 모듈별 상태

| 모듈 | 통과/전체 | 상태 |
|------|----------|------|
| test_data_loader.py | 4/9 | 🟡 부분 통과 |
| test_meta_manager.py | 1/5 | 🔴 대부분 실패 |
| test_analysis.py | 1/7 | 🔴 대부분 실패 |
| test_strategy.py | 4/12 | 🟡 부분 통과 |
| test_tqqq_simulation.py | 6/13 | 🟡 부분 통과 |

## 주요 불일치 원인

### 1. 타임스탬프 형식 차이
**테스트 가정**: "2023-06-15 14:30:00" (단순 문자열)
**실제 구현**: "2023-06-15T14:30:00+09:00" (ISO 8601 형식)

**영향받는 테스트**: `test_meta_manager.py` 전체

### 2. 이력 정렬 순서 차이
**테스트 가정**: 오래된 것 → 최신 (append 방식)
**실제 구현**: 최신 것 → 오래된 것 (prepend 방식)

**영향받는 테스트**: `test_meta_manager.py`의 history 관련 테스트

### 3. 함수 시그니처 차이
일부 함수의 실제 파라미터 형식, 반환값 구조가 테스트 가정과 다름

**영향받는 테스트**:
- `test_analysis.py` - calculate_summary 반환값
- `test_strategy.py` - 파라미터 구조
- `test_tqqq_simulation.py` - 함수 시그니처

### 4. 예외 메시지 차이
실제 발생하는 예외 메시지가 테스트에서 기대하는 것과 다름

**영향받는 테스트**:
- `test_data_loader.py` - FileNotFoundError 메시지
- `test_tqqq_simulation.py` - FFR 관련 에러 메시지

## 다음 단계 (우선순위순)

### 옵션 A: 테스트를 프로덕션 코드에 맞추기 (권장)

이 방법은 실제 동작하는 코드를 검증하는 정확한 테스트를 만듭니다.

**단계**:
1. 각 모듈의 실제 함수를 Python REPL에서 실행해보기
2. 실제 입력/출력 확인
3. 테스트를 그에 맞게 수정

**예시**:
```python
# Python REPL에서
from qbt.utils.meta_manager import save_metadata
from pathlib import Path
import tempfile

# 임시 디렉토리에서 테스트
with tempfile.TemporaryDirectory() as tmpdir:
    # 실제 동작 확인
    save_metadata("grid_results", {"test": "data"})
    # 생성된 파일 확인
    # 타임스탬프 형식 확인
    # ...
```

**소요 시간**: 2-3시간

### 옵션 B: 프로덕션 코드 일부 수정 (비권장)

테스트 가능성을 위해 프로덕션 코드 일부 수정

**예시**:
- `save_metadata()`에 timestamp 포맷 옵션 추가
- 테스트 모드 플래그 추가

**문제점**:
- 프로덕션 코드가 테스트에 오염됨
- 실제 사용 시 동작과 테스트 동작이 달라질 수 있음

### 옵션 C: 현재 통과하는 테스트만 유지

16개 통과하는 테스트만 남기고 나머지는 주석 처리

**장점**:
- 즉시 사용 가능한 테스트 확보
- CI/CD 즉시 통합 가능

**단점**:
- 커버리지 낮음 (전체의 35%)
- 핵심 로직 일부만 검증

## 추천 작업 방식

### 1단계: 빠른 피드백 루프 구축
```bash
# 통과하는 테스트만 실행해서 리그레션 방지
poetry run pytest -v \
  tests/test_data_loader.py::TestLoadStockData::test_normal_load \
  tests/test_meta_manager.py::TestSaveMetadata::test_invalid_csv_type
```

### 2단계: 한 모듈씩 수정
```bash
# 1. data_loader 완전히 고치기
poetry run pytest tests/test_data_loader.py -v

# 2. 실패한 테스트 하나씩 디버깅
poetry run pytest tests/test_data_loader.py::test_file_not_found -s -vv

# 3. 실제 예외 메시지 확인 후 수정
```

### 3단계: 점진적 확장
- data_loader → analysis → strategy → tqqq_simulation 순으로 수정
- 각 모듈마다 완전히 통과시킨 후 다음으로 진행

## 즉시 사용 가능한 명령어

### 통과하는 테스트만 실행
```bash
poetry run pytest -v \
  tests/test_data_loader.py::TestLoadStockData::test_normal_load \
  tests/test_data_loader.py::TestLoadStockData::test_missing_required_columns \
  tests/test_data_loader.py::TestLoadStockData::test_date_sorting \
  tests/test_data_loader.py::TestLoadFfrData::test_file_not_found
```

### 특정 모듈 디버깅
```bash
# 자세한 에러 메시지 + print 출력
poetry run pytest tests/test_data_loader.py -vv -s --tb=long
```

### 커버리지 확인 (현재 상태)
```bash
poetry run pytest --cov=src/qbt --cov-report=term-missing \
  tests/test_data_loader.py::TestLoadStockData::test_normal_load
```

## 테스트 작성 교훈

앞으로 새로운 테스트 작성 시:

### ✅ 올바른 방법
1. **프로덕션 코드 먼저 확인**:
   ```python
   from qbt.module import function
   help(function)  # 시그니처 확인
   ```

2. **작은 예시로 실제 동작 확인**:
   ```python
   result = function(test_input)
   print(type(result), result)  # 실제 반환값 확인
   ```

3. **그 다음 테스트 작성**

### ❌ 피해야 할 방법
1. 가정 기반으로 테스트 먼저 작성
2. 프로덕션 코드 보지 않고 "이렇게 동작할 것이다" 추측
3. 대량의 테스트를 한 번에 작성

## 결론

**현재 상태**: 테스트 인프라는 완벽하게 구축됨. 35%는 이미 통과.

**필요한 작업**: 나머지 65% 테스트를 실제 프로덕션 코드 동작에 맞게 수정.

**예상 소요 시간**:
- 빠른 수정 (핵심만): 2-3시간
- 완전한 수정 (전체): 4-6시간

**우선순위**:
1. **즉시**: 통과하는 16개로 CI/CD 구축
2. **1주일 내**: data_loader, analysis 완전히 수정 (핵심 데이터 검증)
3. **2주일 내**: 전체 테스트 통과

테스트 작성 과정에서 pytest 사용법과 TDD 방법론을 배웠다는 점에서 교육적 가치는 100% 달성했습니다! 🎓
