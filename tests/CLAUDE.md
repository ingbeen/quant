# tests 폴더 가이드

> CRITICAL: 테스트 작성/수정 전에 이 문서를 반드시 읽어야 합니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../CLAUDE.md)를 참고하세요.

## 폴더 목적

tests 폴더(`tests/`)는 QBT 프로젝트의 테스트 코드를 관리하며, 핵심 비즈니스 로직의 정확성을 보장합니다.

테스트 철학: 정책/불변조건/계약을 코드로 고정하여 회귀 방지

폴더 구조:

```

tests/
├── CLAUDE.md # tests 관련 규칙 (이 문서)
├── conftest.py # 공통 픽스처
├── test_analysis.py # 성과 지표/분석 로직 테스트
├── test_cli_helpers.py # CLI 예외 처리 데코레이터 테스트
├── test_data_loader.py # 데이터 로더 테스트
├── test_formatting.py # 터미널 출력 포맷팅 테스트
├── test_integration.py # 통합 테스트 (백테스트/TQQQ 파이프라인)
├── test_logger.py # 로거 테스트
├── test_meta_manager.py # 메타데이터 관리 테스트
├── test_numpy_warnings.py # NumPy 부동소수점 경고 테스트
├── test_parallel_executor.py # 병렬 처리 테스트
├── test_strategy.py # 백테스트 전략 테스트
├── test_tqqq_analysis_helpers.py # TQQQ 금리-오차 분석 테스트
├── test_tqqq_data_loader.py # TQQQ 데이터 로더 테스트
├── test_tqqq_optimization.py # TQQQ softplus 파라미터 최적화 테스트
├── test_tqqq_simulation.py # TQQQ 시뮬레이션 (core) 테스트
├── test_tqqq_walkforward.py # TQQQ 워크포워드 검증 테스트
└── test_tqqq_visualization.py # TQQQ 차트 생성 테스트

# pytest 설정 (루트 디렉토리)

../pytest.ini # pytest 기본 설정/마커 정의
../validate_project.py # 통합 품질 검증 스크립트 (Ruff + PyRight + Pytest)

```

---

# pytest 설정 (루트 디렉토리)

pytest 설정은 루트의 `pytest.ini`가 Single Source of Truth입니다.

- 테스트 탐색 경로: `tests/`
- 파일 패턴: `test_*.py`
- pytest.ini의 마커 설정은 참고용이며, 테스트 실행은 기본적으로 전체 실행을 기준으로 한다.

근거 위치: [../pytest.ini](../pytest.ini)

---

## 테스트 실행 방법

### 통합 품질 검증 (권장)

테스트 실행 예시:

```bash
# 전체 검증 (Ruff + Pyright + Pytest)
poetry run python validate_project.py

# 테스트만 실행
poetry run python validate_project.py --only-tests

# 커버리지 포함 테스트만 실행
poetry run python validate_project.py --cov
```

### 특정 모듈/파일 테스트 (예외)

특정 모듈이나 파일만 테스트할 때는 직접 pytest 명령을 사용할 수 있습니다:

```bash
# 특정 모듈만 실행
poetry run pytest tests/test_strategy.py -v

# 특정 클래스만 실행
poetry run pytest tests/test_strategy.py::TestRunBufferStrategy -v

# 특정 테스트만 실행
poetry run pytest tests/test_strategy.py::TestRunBufferStrategy::test_normal_execution_with_trades -v

# 실패한 테스트만 재실행
poetry run pytest --lf -v

# 디버깅 모드 (print 출력 포함)
poetry run pytest tests/test_xxx.py -s -vv
```

---

## 테스트 작성 원칙

### 1. 핵심 로직 보호

필수 테스트 대상: 백테스트/시뮬레이션의 핵심 계산 로직(= 계약/불변조건)

- 백테스트 도메인:

  - 이동평균 계산 (`analysis.py`)
  - 버퍼존 밴드 계산 (`strategies/buffer_zone_helpers.py`)
  - 거래 신호 생성 (매수/매도 조건)
  - 체결 타이밍 규칙 (신호일 vs 체결일 분리)
  - Pending Order 정책 (단일 슬롯, 충돌 감지)
  - Equity 및 Final Capital 정의
  - 성과 지표 (CAGR, MDD, 승률 등)
  - 동적 파라미터 조정 (최근 매수 기반)

- TQQQ 시뮬레이션 도메인:

  - 일일 비용 계산 (`calculate_daily_cost`)
  - 레버리지 수익률 적용 (`simulate`)
  - 복리 효과 검증
  - 누적배수 로그차이 계산 (스케일 무관 추적오차)
  - Softplus 파라미터 최적화 (`find_optimal_softplus_params`)

- 공통 유틸리티:

  - 메타데이터 저장/로드 (순환 저장 검증)
  - 데이터 로더 (CSV 로딩 및 전처리)
  - 겹치는 기간 추출 (`extract_overlap_period`)
  - 병렬 처리/결과 정렬(입력 순서 보장)

근거 위치:

- [test_strategy.py](test_strategy.py)
- [test_analysis.py](test_analysis.py)
- [test_tqqq_simulation.py](test_tqqq_simulation.py)
- [test_tqqq_analysis_helpers.py](test_tqqq_analysis_helpers.py)
- [test_tqqq_data_loader.py](test_tqqq_data_loader.py)
- [test_tqqq_visualization.py](test_tqqq_visualization.py)
- [test_data_loader.py](test_data_loader.py)
- [test_meta_manager.py](test_meta_manager.py)
- [test_parallel_executor.py](test_parallel_executor.py)
- [test_cli_helpers.py](test_cli_helpers.py)
- [test_formatting.py](test_formatting.py)
- [test_logger.py](test_logger.py)
- [test_numpy_warnings.py](test_numpy_warnings.py)

---

### 2. Given-When-Then 패턴

모든 테스트는 명확한 3단계 구조를 따릅니다.

```python
def test_example(self):
    """
    목적: 무엇을 검증하는가(불변조건/계약)

    Given: 어떤 입력/상태를 준비했는가
    When: 어떤 함수를 실행했는가
    Then: 어떤 결과/부작용을 검증했는가
    """
    # Given
    df = ...

    # When
    result = function_under_test(df)

    # Then
    assert ...
```

규칙:

- "Then"은 되도록 한 가지 계약을 명확히 고정합니다.
- 복잡한 로직은 한 테스트에 여러 assert를 넣기보다, 테스트를 쪼개서 계약 단위로 고정하세요.

---

### 3. 경계 조건 테스트

정상 케이스뿐 아니라 엣지 케이스도 포함합니다.

- 빈 데이터 / 최소 길이 데이터
- 윈도우 크기 부족(이동평균 등)
- 자본 부족/주문 불가 시나리오
- 극단값 (0, 음수, 매우 큰 값)
- 날짜 중복/정렬 불량(필요 시 입력 정규화 계약)
- NaN/결측치(프로덕션 정책에 따라 허용/금지 명확히)

> 중요: "엣지 케이스를 어떻게 처리해야 하는가"는 도메인 정책입니다.
> 정책이 정해져 있다면 테스트는 그 정책을 고정해야 합니다.

---

### 4. 결정적 테스트 (Deterministic)

테스트는 환경/시간/순서에 상관없이 항상 같은 결과를 보장해야 합니다.

```python
from freezegun import freeze_time

@freeze_time("2023-06-15 14:30:00")
def test_with_fixed_time(self):
    # 시간이 고정되어 타임스탬프가 항상 동일
    save_metadata("grid_results", {"test": "data"})
```

주요 기법:

- 시간 고정: `@freeze_time` 사용
- 파일 격리: `tmp_path`, `mock_storage_paths` 사용
- 랜덤성 제거: 랜덤을 쓰면 시드 고정(가능하면 랜덤 자체를 제거)
- 순서 안정화: 결과가 리스트/딕트/DF 정렬에 민감하면 정렬 규칙을 테스트에서 명시

#### 부동소수점/DF 비교 규칙(필수)

부동소수점 오차가 발생할 수 있는 모든 연산 결과는 명시적 허용오차와 함께 비교합니다.

**스칼라 비교** (모든 연산 결과):

```python
# 금지 패턴
assert abs(a - b) < tolerance

# 필수 패턴
assert actual == pytest.approx(expected, abs=tolerance)
```

**허용오차 기준표**:

| 검증 대상 | 허용오차 | 예시 |
|-----------|----------|------|
| 수학적 정확 계산 (MA, 로그차이 등) | `EPSILON` (1e-12) | 이동평균, 승률 |
| 초정밀 함수 (softplus) | `1e-10` | softplus 계산값 |
| 일일 비용 계산 | `1e-6` | 연간 비용/252 |
| 가격/금액 비교 | `0.01` ~ `0.1` | equity, 종가 |
| 비율(%) 지표 | `0.1` | total_return_pct, MDD |
| CAGR (근사 계산) | `1.0` | 복리 연환산 |

**예외** (변경 불필요):

- 단순 부등식 상한/하한 검증: `assert value < threshold`
- 정확히 일치해야 하는 값 (라벨, 컬럼명, 날짜 등): `assert value == expected`
- 배열 비교: `np.allclose(actual, expected, rtol=...)` (허용)

**DataFrame 비교**:

- `pd.testing.assert_frame_equal(..., rtol=..., atol=...)`
- 컬럼 순서/인덱스 정책을 함께 고정(필요 시 `check_like=True` 사용)

> "정확히 일치"가 정책인 값은 `==`로 고정하고,
> **모든 연산 결과는 `pytest.approx()` 사용이 필수**입니다.

---

### 5. 파일 격리

테스트는 실제 파일/실제 storage에 영향을 주지 않아야 합니다.

```python
def test_with_temp_files(self, mock_storage_paths):
    # tmp_path 기반 임시 경로를 사용 (테스트 후 자동 삭제)
    meta_path = mock_storage_paths["META_JSON_PATH"]
    ...
```

규칙:

- 테스트에서 `storage/` 실경로(프로덕션 경로) 접근 금지
- 파일 기반 기능은 반드시:

  - `tmp_path` 또는
  - `mock_storage_paths`(= `common_constants` 경로 패치)
    를 통해 격리합니다.

- 모듈이 import 시점에 경로 상수를 캡처할 수 있으므로,
  필요한 경우 관련 모듈도 함께 monkeypatch 되어야 합니다.
  (현재 `conftest.py`는 `meta_manager.META_JSON_PATH`도 패치합니다.)

근거 위치: [conftest.py](conftest.py)

---

### 6. 문서화

테스트 가독성: 초보자도 이해 가능하도록 작성합니다.

- Docstring 권장(테스트가 짧아도 "무엇을 고정하는지"는 남기기)

  - 테스트 목적(검증 계약)
  - Given-When-Then 구조
  - 예외 케이스인 경우 "왜 예외가 맞는가"

- 복잡한 계산/로직: 인라인 주석으로 단계별 설명
- 필요 시 Python 기초 문법 설명(최소한으로):

  - 예: 리스트 컴프리헨션, `pytest.raises`, `@freeze_time`, `monkeypatch`

문서화 목적: 테스트 자체가 도메인 규칙의 "실행 가능한 문서" 역할을 합니다.

주석 작성 원칙: [루트 CLAUDE.md](../CLAUDE.md#코딩-표준)의 문서화 규칙을 참고하세요.

---

### 7. 병렬처리 테스트 파라미터 최소화

병렬처리(`parallel_executor`) 테스트 시 실행 시간 단축을 위해 최소 파라미터를 사용합니다.

원칙:

- 테스트 목적 달성에 필요한 최소한의 입력 사용
- 순서 보장 검증: 5개 입력이면 충분 (20개 불필요)
- 캐시 동작 검증: 1~2개 입력이면 충분
- `max_workers`: 2를 기본으로 권장 (병렬 동작 검증에 충분)

파라미터 가이드라인:

| 테스트 유형 | 권장 입력 수 | 권장 workers |
|------------|------------|-------------|
| 기본 실행 검증 | 3~5개 | 2 |
| 순서 보장 검증 | 5개 | 2 |
| 캐시 초기화/재초기화 | 1~2개 | 1~2 |
| 예외 처리 검증 | 0~1개 | 2 |

근거:

- 병렬처리 핵심 계약(순서 보장, 캐시 동작)은 소량 데이터로 검증 가능
- 프로세스 풀 생성/해제 오버헤드가 테스트 시간의 주요 요인
- 불필요하게 큰 입력은 테스트 시간만 증가시킴

---

## 주요 픽스처 (conftest.py)

공통 픽스처: 모든 테스트에서 재사용 가능한 설정과 테스트 데이터

- `sample_stock_df`: 기본 주식 데이터(OHLCV, 3행), `Date`는 `datetime.date`
- `integration_stock_df`: 통합 테스트용 주식 데이터(OHLCV, 25행), MA 계산에 충분한 크기
- `sample_ffr_df`: FFR 금리 데이터

  - 중요: `DATE` 컬럼은 `date` 객체가 아닌 `"yyyy-mm"` 문자열
  - 이유: 프로덕션 코드에서 월별 금리를 문자열 키로 처리

- `sample_expense_df`: Expense Ratio 운용비율 데이터

  - `DATE` 컬럼: `"yyyy-mm"` 문자열 (FFR과 동일 형식)
  - `VALUE` 컬럼: 0~1 비율

- `create_csv_file`: CSV 파일 생성 헬퍼(팩토리)
- `mock_stock_dir`: `common_constants.STOCK_DIR`만 임시 경로로 패치
- `mock_etc_dir`: `common_constants.ETC_DIR`만 임시 경로로 패치
- `mock_results_dir`: `RESULTS_DIR`, `META_JSON_PATH` 임시 경로로 패치 (meta_manager 포함)
- `mock_storage_paths`: 통합 픽스처 — 모든 storage 경로를 임시 경로로 패치

  - `tmp_path` 기반 디렉토리 생성 후 자동 삭제
  - `common_constants.py`의 경로 상수를 임시 경로로 패치
  - `meta_manager` 등 "import 시점에 상수를 들고 있는 모듈"도 함께 패치

- `enable_numpy_warnings`: NumPy 부동소수점 경고 활성화 픽스처 (디버깅용)

  - 목적: 디버깅/테스트 시 부동소수점 오류 조기 발견
  - 동작: `np.errstate(all='warn')`로 모든 부동소수점 오류를 경고로 출력
  - 사용 시나리오: 수치 계산 테스트에서 숨은 오류 감지
  - 사용 예시:
    ```python
    def test_calculation(self, enable_numpy_warnings):
        # 이 테스트 안에서 NumPy 경고가 활성화됨
        result = calculate_some_metric(df)
    ```
  - 프로덕션 영향: 없음 (테스트 환경에서만 활성화)
  - 기존 안전 장치: EPSILON 기반 방식은 그대로 유지

픽스처 사용 시 주의사항:

- 프로덕션 코드의 실제 데이터 형식 확인 필수
- 컬럼명 대소문자 확인 (예: `equity` vs `Equity`)
- FFR 데이터 형식 (`date` vs `"yyyy-mm"` 문자열)

근거 위치: [conftest.py](conftest.py)

---

## tests 폴더 운영 원칙

폴더 순수성:

1. 테스트 코드만 유지: tests 폴더는 테스트 코드(`.py`)와 문서만 포함

   - `conftest.py`: 공통 픽스처
   - `test_*.py`: 도메인별 테스트 모듈
   - 이 문서(`CLAUDE.md`): 테스트 규칙/철학

2. 커버리지 목표: 핵심 모듈 최대한 높게 유지

   - 백테스트 도메인: `src/qbt/backtest/`
   - TQQQ 시뮬레이션: `src/qbt/tqqq/`
   - 공통 유틸리티: `src/qbt/utils/`

외부 의존성 금지(원칙):

- 테스트에서 네트워크/외부 API 호출 금지
- 환경 의존(로컬 파일, 사용자 홈, OS별 경로) 금지
- 필요하면 `monkeypatch`로 외부 호출을 스텁/대체하고,
  테스트 데이터는 `tmp_path` + CSV/DF로 구성합니다.

예외(에러) 테스트 규칙(권장):

- 예외 타입을 먼저 고정하고, 메시지는 정책인 경우에만 엄격하게 고정합니다.
- 일반적으로는 핵심 키워드만 `match=`로 부분 매칭:

```python
import pytest

def test_pending_order_conflict_raises(...):
    with pytest.raises(PendingOrderConflictError, match="pending"):
        ...
```

---

## 커버리지

### 현재 커버리지 확인

```bash
# 통합 검증 스크립트 사용 (권장)
poetry run python validate_project.py --cov  # 테스트 + 커버리지만 실행
```

### HTML 리포트 생성

커버리지 HTML 리포트가 필요한 경우 직접 pytest 명령 사용 (예외):

```bash
poetry run pytest --cov=src/qbt --cov-report=html tests/
# 결과: htmlcov/index.html 브라우저로 열기
```

목표:

- 핵심 모듈: 최대한 높은 커버리지 유지
- 전체 프로젝트: 지속적 개선(회귀 방지가 최우선)

---

## 자주 발생하는 문제

### 1. 컬럼명 불일치

```python
# 잘못된 예
df["Equity"]  # 대문자

# 올바른 예
df["equity"]  # 소문자 (실제 프로덕션 코드 확인!)
```

중요: 프로덕션 코드의 실제 컬럼명을 반드시 확인하세요.

### 2. FFR 데이터 형식

```python
# 잘못된 예
"DATE": [date(2023, 1, 1)]  # date 객체

# 올바른 예
"DATE": ["2023-01"]  # yyyy-mm 문자열
```

### 3. 파라미터 단위

```python
# 잘못된 예
buffer_zone_pct=3.0  # 퍼센트

# 올바른 예
buffer_zone_pct=0.03  # 비율 (3%)
```

### 4. 함수 시그니처

프로덕션 코드가 데이터클래스/특정 구조를 사용하는 경우,
테스트도 동일한 구조를 사용해야 "진짜 계약"을 고정할 수 있습니다.

- 테스트에서 임의 dict를 쓰기 전에, 프로덕션 입력 타입을 먼저 확인하세요.

### 5. 타임스탬프 검증

- ISO 8601 형식/타임존 정책을 고려해 검증하세요.
- 시간이 관여하면 `freezegun`을 기본으로 고려하세요.

### 6. 부동소수점 값 정밀도

원칙: 테스트 데이터는 적절한 자릿수로 작성하여 가독성을 높입니다.

좋은 예:

```python
# 명확한 소수점 표기
ffr_df = pd.DataFrame({
    "DATE": ["2023-01", "2023-02"],
    "VALUE": [0.045, 0.046]  # 4.5%, 4.6%
})

expense_df = pd.DataFrame({
    "DATE": ["2023-01", "2023-02"],
    "VALUE": [0.0095, 0.0088]  # 0.95%, 0.88%
})
```

나쁜 예:

```python
# 부동소수점 오차로 인한 긴 소수점
ffr_df = pd.DataFrame({
    "DATE": ["2023-01", "2023-02"],
    "VALUE": [0.04650000000000001, 0.055999999999999994]  # 가독성 저하
})

# 과학적 표기법 (의도가 불명확)
expense_df = pd.DataFrame({
    "DATE": ["2023-01", "2023-02"],
    "VALUE": [9.499999999999999e-05, 8.800000000000001e-05]  # 0.0095인지 0.000095인지 혼란
})
```

정밀도 가이드라인:

소수점 자릿수 기준은 루트 [`CLAUDE.md`](../CLAUDE.md)의 "출력 데이터 반올림 규칙" 참고.
테스트 데이터 작성 시에도 동일한 자릿수 기준을 따릅니다.

부동소수점 오차 처리:

- 테스트 작성 시 부동소수점 반올림 오차가 포함된 값은 정리하여 작성
- 예: `0.054000000000000006` -> `0.054`
- 검증 시 허용 오차:
  - 매우 작은 값 (로그 차이): `1e-6 ~ 1e-12` (EPSILON 기반)
  - 일반 수익률: `0.1 ~ 1.0`
  - 부동소수점 민감한 값: `pytest.approx()` 또는 `pd.testing.assert_frame_equal(rtol=...)`

---

## 테스트 작성 체크리스트

테스트 작성 전/작성 중 확인사항:

- [ ] 프로덕션 코드의 실제 시그니처/입력 타입 확인
- [ ] 실제 반환값 구조/컬럼명/정렬 정책 확인
- [ ] 예외 타입/정책 확인 (`pytest.raises`로 고정)
- [ ] Given-When-Then 패턴 적용
- [ ] 엣지 케이스 포함(최소 1개 이상)
- [ ] 결정적 테스트(시간 고정/파일 격리/순서 안정화)
- [ ] 부동소수점 비교는 `approx/rtol/atol` 고려
- [ ] 네트워크/외부 의존성 없음 확인
- [ ] 명확한 주석 및(가능하면) docstring

---

## 지속적 개선

### 새 기능 추가 시

1. 테스트 먼저 작성 (가능하면 TDD)

```python
# 1. 실패하는 테스트 작성
def test_new_feature(self):
    result = new_feature()
    assert result == expected

# 2. 기능 구현
# 3. 테스트 통과 확인
```

2. 기존 테스트 실행

```bash
poetry run python validate_project.py  # 회귀 방지 (전체 검증)
```

### 버그 발견 시

1. 재현 테스트 작성

```python
def test_bug_reproduction(self):
    # 버그를 재현하는 테스트
    # 먼저 실패하는지 확인
    ...
```

2. 버그 수정
3. 테스트 통과 확인

---

사용 중인 플러그인:

- pytest-cov: 코드 커버리지 측정
- freezegun: 시간 고정 (결정적 테스트)
