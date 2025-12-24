# QBT 테스트 가이드

> 백테스트 프로젝트의 전체 테스트 스위트 문서

## 🎯 현재 상태

**전체 테스트: 46개 중 46개 통과 (100%)** ✅

```bash
poetry run pytest tests/ -v
# ======================== 46 passed in 0.34s ========================
```

## 📁 테스트 구조

```
tests/
├── conftest.py                 # 공통 픽스처 정의
├── test_analysis.py            # 백테스트 분석 (7개 테스트)
├── test_data_loader.py         # 데이터 로딩 (9개 테스트)
├── test_meta_manager.py        # 메타데이터 관리 (5개 테스트)
├── test_strategy.py            # 전략 실행 (12개 테스트)
├── test_tqqq_simulation.py     # TQQQ 시뮬레이션 (13개 테스트)
├── pytest.ini                  # pytest 설정
├── run_tests.sh                # 테스트 실행 스크립트
├── TEST_COMPLETE.md            # 상세 완료 보고서
└── archive/                    # 작업 중 생성된 임시 문서들
```

## 🚀 빠른 시작

### 필수 패키지 설치

```bash
# Poetry로 개발 의존성 설치
poetry install

# 테스트 관련 패키지 확인
poetry show pytest pytest-cov freezegun
```

### 테스트 실행

```bash
# 전체 테스트 실행
poetry run pytest tests/ -v

# 특정 모듈만 실행
poetry run pytest tests/test_strategy.py -v

# 커버리지 포함 실행
poetry run pytest --cov=src/qbt --cov-report=html tests/

# 실패한 테스트만 재실행
poetry run pytest --lf

# 디버깅 모드 (print 출력 포함)
poetry run pytest tests/test_xxx.py -s -vv
```

## 📋 테스트 모듈 설명

### 1. `conftest.py` - 공통 픽스처

모든 테스트에서 사용하는 공통 설정과 테스트 데이터를 제공합니다.

**주요 픽스처:**
- `sample_stock_df`: 기본 주식 데이터
- `sample_ffr_df`: FFR 금리 데이터 (yyyy-mm 문자열 형식)
- `create_csv_file`: CSV 파일 생성 헬퍼
- `mock_storage_paths`: 임시 경로 설정 (파일 격리)

### 2. `test_data_loader.py` - 데이터 로딩 검증

CSV 파일 로딩, 데이터 검증, 전처리 로직을 테스트합니다.

**테스트 항목:**
- ✅ 정상 CSV 로딩 및 파싱
- ✅ 필수 컬럼 검증
- ✅ 날짜 자동 정렬
- ✅ 중복 날짜 제거
- ✅ 파일 없음 에러 처리
- ✅ FFR 데이터 로딩 (문자열 DATE)
- ✅ 비교 데이터 검증 (한글 컬럼명)

### 3. `test_analysis.py` - 백테스트 분석

이동평균 계산과 성과 지표 산출을 테스트합니다.

**테스트 항목:**
- ✅ SMA/EMA 이동평균 계산
- ✅ CAGR (연평균 복리 수익률)
- ✅ MDD (최대 낙폭)
- ✅ 승률, 거래 통계
- ✅ 엣지 케이스 (거래 없음, 모든 손실, MDD=0)

### 4. `test_meta_manager.py` - 메타데이터 관리

실행 이력 저장 및 관리를 테스트합니다.

**테스트 항목:**
- ✅ JSON 파일 생성 및 저장
- ✅ ISO 8601 타임스탬프 자동 추가
- ✅ 이력 순환 관리 (최대 5개)
- ✅ 최신 항목이 맨 앞 (prepend)
- ✅ CSV 타입별 독립 관리
- ✅ 잘못된 타입 거부

### 5. `test_strategy.py` - 백테스트 전략

Buy & Hold와 버퍼존 전략 실행을 테스트합니다.

**테스트 항목:**
- ✅ Buy & Hold 벤치마크
- ✅ 버퍼존 전략 (동적 파라미터)
- ✅ 매수/매도 신호 생성
- ✅ 슬리피지 적용
- ✅ 최근 매수 횟수 계산
- ✅ 홀딩 조건 체크
- ✅ 강제 청산 처리
- ✅ 자본 부족 처리

### 6. `test_tqqq_simulation.py` - TQQQ 시뮬레이션

레버리지 ETF 시뮬레이션과 검증을 테스트합니다.

**테스트 항목:**
- ✅ FFR 기반 일일 비용 계산
- ✅ FFR fallback 로직 (2개월 이내)
- ✅ 오래된 FFR 거부 (6개월 초과)
- ✅ 레버리지 효과 검증 (3배)
- ✅ 겹치는 기간 추출
- ✅ 검증 메트릭 계산 (누적배수 로그차이)
- ✅ 최적 비용 모델 탐색

## 🔧 테스트 작성 가이드

### Given-When-Then 패턴

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
    result = add_single_moving_average(df, window=3)

    # Then: 결과 검증
    assert 'ma_3' in result.columns
    assert pd.isna(result.iloc[0]['ma_3'])
```

### 결정적 테스트 (Deterministic)

테스트는 항상 같은 결과를 보장해야 합니다:

```python
from freezegun import freeze_time

@freeze_time("2023-06-15 14:30:00")
def test_with_fixed_time(self):
    # 시간이 고정되어 타임스탬프가 항상 동일
    save_metadata("grid_results", {"test": "data"})
```

### 파일 격리

테스트는 실제 파일에 영향을 주지 않아야 합니다:

```python
def test_with_temp_files(self, mock_storage_paths):
    # tmp_path를 사용하여 테스트 후 자동 삭제
    meta_path = mock_storage_paths['META_JSON_PATH']
    # 테스트 실행...
```

## 📊 커버리지

### 현재 커버리지 확인

```bash
poetry run pytest --cov=src/qbt --cov-report=term-missing tests/
```

### HTML 리포트 생성

```bash
poetry run pytest --cov=src/qbt --cov-report=html tests/
# 결과: htmlcov/index.html 브라우저로 열기
```

### 목표 커버리지
- **핵심 모듈**: 100% (data_loader, analysis, strategy, meta_manager)
- **전체 프로젝트**: 80% 이상

## 🐛 문제 해결

### 테스트 실패 시

1. **상세 에러 보기**
   ```bash
   poetry run pytest tests/test_xxx.py -vv --tb=long
   ```

2. **특정 테스트만 실행**
   ```bash
   poetry run pytest tests/test_xxx.py::TestClass::test_method -s
   ```

3. **print 디버깅**
   ```python
   # 테스트에 print 추가
   print(f"Debug: actual={actual}, expected={expected}")
   # -s 플래그로 실행하면 print 출력됨
   ```

### 자주 발생하는 문제

#### 1. 컬럼명 불일치
```python
# ❌ 잘못된 예
df['Equity']  # 대문자

# ✅ 올바른 예
df['equity']  # 소문자 (실제 프로덕션 코드 확인!)
```

#### 2. FFR 데이터 형식
```python
# ❌ 잘못된 예
'DATE': [date(2023, 1, 1)]  # date 객체

# ✅ 올바른 예
'DATE': ['2023-01']  # yyyy-mm 문자열
```

#### 3. 파라미터 단위
```python
# ❌ 잘못된 예
buffer_zone_pct=3.0  # 퍼센트

# ✅ 올바른 예
buffer_zone_pct=0.03  # 비율 (3%)
```

## 📚 참고 자료

### pytest 문서
- [pytest 공식 문서](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [pytest parametrize](https://docs.pytest.org/en/stable/parametrize.html)

### 사용 중인 플러그인
- **pytest-cov**: 코드 커버리지 측정
- **freezegun**: 시간 고정 (결정적 테스트)

### 프로젝트 문서
- `TEST_COMPLETE.md`: 완료 보고서 및 상세 내역
- `CLAUDE.md`: 프로젝트 전반 가이드라인
- `pytest.ini`: pytest 설정 파일

## 🔄 지속적 개선

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

## 🎓 학습 포인트

### 초보자를 위한 주석

모든 테스트는 pytest 초보자도 이해할 수 있도록 상세한 주석을 포함합니다:

```python
def test_example(self):
    """
    무엇을 테스트하는가?
    왜 중요한가?

    Given: ...
    When: ...
    Then: ...
    """
    # Given: pd.DataFrame 생성 - 엑셀 시트 같은 표 형태
    df = pd.DataFrame(...)  # 딕셔너리를 DataFrame으로

    # 리스트 컴프리헨션 사용
    dates = [date(2023, 1, i+1) for i in range(5)]

    # assert: 조건이 True가 아니면 테스트 실패
    assert len(df) == 5, "5행이어야 합니다"
```

### pytest 핵심 개념

- **픽스처 (Fixture)**: 테스트 데이터 준비 및 정리
- **파라미터화 (Parametrize)**: 같은 테스트를 다양한 입력으로 실행
- **모킹 (Mocking)**: 외부 의존성 대체
- **단언 (Assertion)**: 기대값과 실제값 비교

## ✅ 체크리스트

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

**관리자**: QBT 개발팀
**최종 업데이트**: 2024-01-01
**pytest 버전**: 9.0.2
**Python 버전**: 3.12.3
