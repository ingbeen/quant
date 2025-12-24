# QBT 테스트 전략 및 구현 요약

이 문서는 QBT 프로젝트의 테스트 전략과 구현 내용을 요약합니다.

---

## 1. 테스트 전략 요약

### 1.1 데이터 신뢰성 검증 (최우선)

백테스팅 결과의 정확성은 입력 데이터 품질에 절대적으로 의존합니다.

**스키마 무결성**:
- 필수 컬럼 존재 여부 검증 → 누락 시 `ValueError`
- 타입 정확성 검증 (날짜는 `datetime.date`, 가격은 `float`)
- 컬럼명 일관성 검증 (rename 작업 후 기대 컬럼 확인)

**데이터 정렬 및 중복 제거**:
- 시계열 오름차순 정렬 필수 (백테스트 로직 의존성)
- 중복 날짜 제거 (첫 번째 값 유지)
- 중복 발견 시 경고 로깅 (caplog로 검증)

**경계 조건 및 에러 핸들링**:
- 파일 부재 → `FileNotFoundError`
- 빈 데이터/최소 행 수 미달 → `ValueError`
- 날짜 파싱 실패 → 즉시 거부

### 1.2 안정성 검증

**결정적 테스트 (Deterministic Tests)**:
- 시간 고정: `freezegun`으로 메타데이터 timestamp 고정
- 네트워크 격리: 모든 파일 I/O는 `tmp_path` 사용
- 재현 가능성: 같은 입력 → 항상 같은 출력

**파라미터 검증**:
- 음수/0 검증: window, leverage, initial_capital 등
- 범위 검증: buffer_pct, slippage 등
- None/누락 처리: 필수 인자 누락 시 명확한 에러

**상태 관리**:
- 포지션 정리: 백테스트 종료 시 강제 청산 검증
- 순환 버퍼: 메타데이터 이력 크기 제한 (MAX_HISTORY_COUNT)

### 1.3 회귀 방지

**출력 스키마 검증**:
- 컬럼 존재: 기대한 컬럼이 모두 있는지
- 행 수 논리: 거래 발생 시 trades_df 행 수 > 0
- 정렬 유지: 출력 DataFrame도 날짜 오름차순

**수치 정확성**:
- 작은 합성 데이터: 손으로 계산 가능한 기대값 비교
- `pandas.testing`: `assert_frame_equal`, `assert_series_equal`
- 핵심 지표: CAGR, MDD, win_rate 등 합리적 범위 검증

**로직 경로 커버리지**:
- 분기 커버: `hold_days=0` vs `>0`, FFR 있을 때/없을 때
- 엣지 케이스: 거래 0건, 데이터 1행, 최대 fallback 기간 초과

---

## 2. 필요한 개발 의존성

```bash
# Poetry로 설치 (권장)
poetry add --group dev pytest pytest-cov freezegun

# 또는 pip로 설치
pip install pytest pytest-cov freezegun
```

### 패키지 역할

| 패키지 | 역할 | 왜 필요한가? |
|--------|------|--------------|
| `pytest` | 테스트 프레임워크 | 테스트 실행, 결과 보고, 픽스처 관리 |
| `pytest-cov` | 코드 커버리지 측정 | 어느 코드가 테스트되었는지 확인 |
| `freezegun` | 시간 고정 | 메타데이터 timestamp 결정적 테스트 |

---

## 3. 테스트 파일 구조

```
quant/
├── tests/
│   ├── conftest.py                # 공통 픽스처
│   ├── test_data_loader.py        # 데이터 로딩 테스트
│   ├── test_meta_manager.py       # 메타데이터 관리 테스트
│   ├── test_analysis.py           # 백테스트 분석 테스트
│   ├── test_strategy.py           # 백테스트 전략 테스트
│   ├── test_tqqq_simulation.py    # TQQQ 시뮬레이션 테스트
│   └── README_TESTS.md            # 초보자용 가이드
├── pytest.ini                     # pytest 설정
├── run_tests.sh                   # 테스트 실행 스크립트
└── TESTING_SUMMARY.md             # 이 문서
```

---

## 4. 테스트 커버리지 상세

### 4.1 test_data_loader.py

**테스트 대상**: `qbt/utils/data_loader.py`

**핵심 테스트 케이스**:

| 테스트 함수 | 검증 내용 | 중요도 |
|------------|----------|--------|
| `test_normal_load` | CSV 정상 로딩, 스키마 검증, 날짜 타입 확인 | ★★★ |
| `test_file_not_found` | 파일 부재 시 `FileNotFoundError` | ★★★ |
| `test_missing_required_columns` | 필수 컬럼 누락 시 `ValueError` | ★★★ |
| `test_duplicate_dates_removed` | 중복 제거 + 경고 로그 (caplog) | ★★★ |
| `test_date_sorting` | 날짜 자동 정렬 확인 | ★★☆ |

**데이터 신뢰성 기여**:
- 잘못된 데이터가 시스템에 들어오는 것을 원천 차단
- 중복 날짜는 백테스트 로직을 망가뜨릴 수 있음 (첫 값 유지 규칙 확인)
- 날짜 정렬은 시계열 분석의 필수 조건

### 4.2 test_meta_manager.py

**테스트 대상**: `qbt/utils/meta_manager.py`

**핵심 테스트 케이스**:

| 테스트 함수 | 검증 내용 | 중요도 |
|------------|----------|--------|
| `test_create_new_meta_file` | meta.json 자동 생성, timestamp 고정 (freezegun) | ★★★ |
| `test_append_to_existing_meta` | 기존 데이터 보존하면서 추가 | ★★☆ |
| `test_history_limit_enforcement` | MAX_HISTORY_COUNT 초과 시 오래된 항목 제거 | ★★★ |
| `test_invalid_csv_type` | 잘못된 csv_type 거부 | ★★☆ |
| `test_multiple_csv_types` | 여러 타입 독립 관리 | ★☆☆ |

**안정성 기여**:
- `freezegun`으로 시간 고정 → 결정적 테스트
- 실행 이력 추적으로 재현성 확보
- 무한정 커지는 파일 방지 (성능 유지)

### 4.3 test_analysis.py

**테스트 대상**: `qbt/backtest/analysis.py`

**핵심 테스트 케이스**:

| 테스트 함수 | 검증 내용 | 중요도 |
|------------|----------|--------|
| `test_normal_calculation` | 이동평균 수식 정확성 (손계산 비교) | ★★★ |
| `test_window_larger_than_data` | 데이터 부족 시 NaN 처리 | ★★☆ |
| `test_invalid_window` | 0/음수 window 거부 | ★★☆ |
| `test_normal_summary` | CAGR, MDD, 승률 계산 정확성 | ★★★ |
| `test_no_trades` | 거래 0건 시 안전 처리 | ★★☆ |
| `test_all_losing_trades` | 승률 0% 처리 | ★☆☆ |
| `test_mdd_zero` | MDD=0 (계속 상승) 처리 | ★☆☆ |

**데이터 신뢰성 기여**:
- MA 계산 오류는 잘못된 매매 신호 생성
- 성과 지표 오류는 전략 평가 왜곡
- 작은 합성 데이터로 수치 정확성 검증

### 4.4 test_strategy.py

**테스트 대상**: `qbt/backtest/strategy.py`

**핵심 테스트 케이스**:

| 테스트 함수 | 검증 내용 | 중요도 |
|------------|----------|--------|
| `test_normal_execution` | Buy & Hold 슬리피지 적용, shares 정수 확인 | ★★★ |
| `test_insufficient_capital` | 자본 부족 시 안전 처리 | ★★☆ |
| `test_count_within_period` | 최근 매수 횟수 계산 정확성 | ★★☆ |
| `test_hold_satisfied` / `test_hold_violated` | 홀딩 조건 로직 정확성 | ★★★ |
| `test_normal_execution_with_trades` | 버퍼존 전략 정상 실행 | ★★★ |
| `test_missing_ma_column` | MA 컬럼 누락 시 즉시 실패 | ★★★ |
| `test_insufficient_valid_data` | 유효 데이터 부족 시 에러 | ★★☆ |
| `test_forced_liquidation_at_end` | 마지막 날 강제 청산 확인 | ★★★ |
| `test_hold_days_zero_vs_positive` | hold_days 분기 경로 커버 | ★★☆ |

**안정성 기여**:
- 슬리피지 방향 오류는 수익률을 완전히 왜곡
- 홀딩 조건 버그는 전략 의도와 다른 매매 발생
- 강제 청산 누락은 잘못된 equity curve 생성

### 4.5 test_tqqq_simulation.py

**테스트 대상**: `qbt/tqqq/simulation.py`

**핵심 테스트 케이스**:

| 테스트 함수 | 검증 내용 | 중요도 |
|------------|----------|--------|
| `test_normal_cost_calculation` | 일일 비용 공식 정확성 | ★★★ |
| `test_ffr_fallback_within_2_months` | FFR fallback 로직 | ★★★ |
| `test_ffr_too_old_raises_error` | 너무 오래된 FFR 거부 | ★★★ |
| `test_empty_ffr_dataframe` | 빈 FFR 데이터 거부 | ★★☆ |
| `test_normal_simulation` | NaN 없이 시뮬레이션 생성 | ★★★ |
| `test_leverage_effect` | 레버리지 배수 정확성 | ★★★ |
| `test_invalid_leverage` | 0/음수 레버리지 거부 | ★★☆ |
| `test_normal_overlap` | 중복 기간 추출 정확성 | ★★☆ |
| `test_perfect_match` | RMSE=0, correlation=1.0 검증 | ★★☆ |

**데이터 신뢰성 기여**:
- 비용 모델 오류는 시뮬레이션을 무의미하게 만듦
- FFR 누락/오래된 데이터로 계산하면 부정확
- 레버리지 효과가 틀리면 실제와 큰 차이 발생

---

## 5. 테스트 실행 방법

### 5.1 기본 실행

```bash
# 모든 테스트 실행 (간결한 출력)
pytest -q

# 상세 출력
pytest -v

# print 문 출력 보기
pytest -s
```

### 5.2 특정 테스트만 실행

```bash
# 특정 파일
pytest tests/test_data_loader.py

# 특정 함수
pytest tests/test_data_loader.py::test_load_stock_data_normal

# 특정 클래스
pytest tests/test_data_loader.py::TestLoadStockData

# 이름 패턴 필터링
pytest -k "load"  # "load" 포함된 모든 테스트
```

### 5.3 커버리지 측정

```bash
# 터미널 리포트
pytest --cov=src/qbt --cov-report=term-missing

# HTML 리포트 (브라우저로 확인)
pytest --cov=src/qbt --cov-report=html
# htmlcov/index.html 열기
```

### 5.4 디버깅

```bash
# 첫 실패 시 중단
pytest -x

# 실패한 테스트만 재실행
pytest --lf

# 디버거 시작
pytest --pdb

# 로그 출력
pytest --log-cli-level=DEBUG
```

### 5.5 편리한 스크립트 사용

```bash
# 스크립트에 실행 권한 부여 (최초 1회)
chmod +x run_tests.sh

# 다양한 옵션으로 실행
./run_tests.sh                # 전체 테스트
./run_tests.sh quick          # 빠른 실행
./run_tests.sh coverage       # 커버리지 측정
./run_tests.sh failed         # 실패한 것만
./run_tests.sh debug          # print 출력
./run_tests.sh help           # 도움말
```

---

## 6. 초보자를 위한 학습 포인트

### 6.1 Given-When-Then 패턴

모든 테스트는 3단계 구조로 작성되어 있습니다:

```python
def test_example():
    """
    Given: 초기 조건 (준비)
    When: 실행 (함수 호출)
    Then: 검증 (assert)
    """
    # Given
    data = prepare_test_data()

    # When
    result = function_to_test(data)

    # Then
    assert result == expected_value, "명확한 에러 메시지"
```

### 6.2 픽스처 (Fixture) 이해

픽스처는 테스트 데이터를 재사용 가능하게 만듭니다:

```python
@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_with_fixture(sample_data):  # 자동 주입
    assert sample_data["key"] == "value"
```

### 6.3 주요 pytest 도구

| 도구 | 역할 | 사용 예시 |
|------|------|----------|
| `tmp_path` | 임시 디렉토리 | 파일 I/O 테스트 격리 |
| `caplog` | 로그 캡처 | 경고 로그 검증 |
| `freezegun` | 시간 고정 | 결정적 테스트 |
| `monkeypatch` | 함수/변수 대체 | 경로 변경, 모킹 |
| `pytest.raises` | 예외 검증 | 에러 발생 확인 |

### 6.4 assert 메시지의 중요성

```python
# 나쁜 예
assert len(df) == 3

# 좋은 예
assert len(df) == 3, "중복 제거 후 행 수가 3이어야 합니다"
```

실패 시 원인을 즉시 파악할 수 있습니다.

---

## 7. 테스트 가능성을 위한 코드 개선 제안 (선택)

현재 프로덕션 코드는 대부분 테스트 가능하지만, 필요 시 다음 개선을 고려하세요:

### 7.1 의존성 주입

```python
# 현재 (하드코딩된 경로)
def save_data():
    with open("/fixed/path/data.csv", "w") as f:
        ...

# 개선 (경로를 인자로 받음)
def save_data(output_path: Path):
    with open(output_path, "w") as f:
        ...
```

### 7.2 시간 의존성 분리

```python
# 현재 (현재 시간 사용)
def process():
    timestamp = datetime.now()
    ...

# 개선 (시간을 인자로 받음)
def process(timestamp: datetime | None = None):
    if timestamp is None:
        timestamp = datetime.now()
    ...
```

### 7.3 로거 주입

```python
# 현재 (전역 로거)
logger = get_logger(__name__)

def process():
    logger.info("Processing...")

# 개선 (로거 주입, 테스트 시 모킹 가능)
def process(logger: Logger | None = None):
    if logger is None:
        logger = get_logger(__name__)
    logger.info("Processing...")
```

**주의**: 과도한 추상화는 오히려 복잡도를 높입니다. 꼭 필요할 때만 개선하세요.

---

## 8. CI/CD 통합 (향후)

GitHub Actions 등에서 자동 테스트를 실행하려면:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install poetry
      - run: poetry install
      - run: poetry run pytest --cov=src/qbt --cov-report=xml
      - uses: codecov/codecov-action@v3  # 커버리지 업로드 (선택)
```

---

## 9. 테스트 작성 체크리스트

새 기능 추가 시 다음을 확인하세요:

- [ ] 정상 케이스 테스트 작성
- [ ] 경계 조건 테스트 (빈 데이터, 최소/최대 값)
- [ ] 에러 케이스 테스트 (잘못된 입력 시 명확한 예외)
- [ ] Given-When-Then 주석 추가
- [ ] assert에 명확한 메시지 포함
- [ ] 테스트 함수명이 검증 내용을 설명
- [ ] 픽스처 활용으로 중복 제거
- [ ] `tmp_path`로 파일 I/O 격리
- [ ] `freezegun`으로 시간 의존성 제거
- [ ] `caplog`로 로깅 검증 (필요 시)

---

## 10. 참고 자료

- **pytest 공식 문서**: https://docs.pytest.org/
- **freezegun GitHub**: https://github.com/spulec/freezegun
- **Real Python 테스트 가이드**: https://realpython.com/pytest-python-testing/
- **테스트 초보자 가이드**: `tests/README_TESTS.md` (이 프로젝트 내)

---

## 11. 결론

이 테스트 suite는 다음을 보장합니다:

1. **데이터 신뢰성**: 잘못된 데이터가 시스템에 들어오지 않음
2. **계산 정확성**: 핵심 지표(CAGR, MDD 등)가 수학적으로 정확
3. **안정성**: 예외 상황에서도 안전하게 처리
4. **회귀 방지**: 코드 변경 후에도 기존 기능 유지
5. **학습 도구**: 초보자가 pytest를 배우면서 실무 경험 축적

**테스트는 코드 품질의 안전망입니다.**
백테스팅 결과에 자신감을 가지려면 테스트로 검증된 코드를 사용하세요!
