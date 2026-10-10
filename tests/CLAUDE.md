# tests 폴더 가이드

> CRITICAL: 테스트 작성/수정 전에 이 문서를 반드시 읽어야 합니다.
> 프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../CLAUDE.md)를 참고하세요.

## 폴더 목적

tests 폴더(`tests/`)는 QBT 프로젝트 전체의 테스트 코드를 관리하며, 핵심 비즈니스 로직의 정확성을 보장합니다.

- `tests/qbt/`: qbt 패키지(`src/qbt/`) 테스트 (백테스트, TQQQ 시뮬레이션, 공통 유틸리티)

`__init__.py`를 포함하지 않습니다 (src 패키지와의 이름 충돌 방지).

저장소를 가리지 않는 테스트 규칙은 전역 `~/.claude/rules/python-tests.md` 가 정합니다. 이 문서에는 QBT 고유의 것만 둡니다.

폴더 구조:

```
tests/
├── CLAUDE.md           # 공통 테스트 규칙 (이 문서)
└── qbt/                # qbt 패키지 테스트
    ├── conftest.py     # qbt 공통 픽스처
    └── test_*.py       # qbt 모듈별 테스트
```

구체적인 테스트 파일 목록은 해당 디렉토리를 직접 참조하세요.

---

# pytest 설정 (루트 디렉토리)

pytest 설정은 루트의 `pytest.ini`가 Single Source of Truth입니다.

- 테스트 탐색 경로: `tests` (하위 디렉토리를 재귀적으로 탐색)
- 파일 패턴: `test_*.py`
- pytest.ini의 마커 설정은 참고용이며, 테스트 실행은 기본적으로 전체 실행을 기준으로 한다.

근거 위치: [../pytest.ini](../pytest.ini)

---

## 테스트 실행 방법

실행 명령어는 [docs/COMMANDS.md](../docs/COMMANDS.md)의 "품질 검증" 및 "테스트 (특정 모듈/파일)" 섹션을 참고한다.

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

- TQQQ 시뮬레이션 도메인:

  - 일일 비용 계산 (`_calculate_daily_cost`)
  - 레버리지 수익률 적용 (`simulate`)
  - 복리 효과 검증
  - 누적배수 로그차이 계산 (스케일 무관 추적오차)
- 공통 유틸리티:

  - 메타데이터 저장/로드 (순환 저장 검증)
  - 데이터 로더 (CSV 로딩 및 전처리)
  - 겹치는 기간 추출 (`extract_overlap_period`)
  - 병렬 처리/결과 정렬(입력 순서 보장)

근거 위치: `tests/qbt/` 디렉토리의 각 `test_*.py` 파일 참조

---

### 2. 경계 조건 테스트

- 자본 부족/주문 불가 시나리오
- 날짜 중복/정렬 불량(필요 시 입력 정규화 계약)

---

### 3. 결정적 테스트 (Deterministic)

결정성의 일반 규칙(시간 · 파일 · 시드 · 순서)은 `python-tests.md`. 아래는 QBT 고유의 허용오차다.

#### 부동소수점/DF 비교 규칙(필수)

**허용오차 기준표**:

| 검증 대상 | 허용오차 | 예시 |
|-----------|----------|------|
| 수학적 정확 계산 (MA, 로그차이 등) | `EPSILON` (1e-12) | 이동평균, 승률 |
| 초정밀 함수 (softplus) | `1e-10` | softplus 계산값 |
| 일일 비용 계산 | `1e-6` | 연간 비용/252 |
| 가격/금액 비교 | `0.01` ~ `0.1` | equity, 종가 |
| 비율(%) 지표 | `0.1` | total_return_pct, MDD |
| CAGR (근사 계산) | `1.0` | 복리 연환산 |
| 반올림 · 분모처럼 «작은 차이 자체»를 검증할 때 | 그 차이보다 충분히 작게 (`abs=1e-9`, `rel=1e-15`) | 저장 자릿수, 분모의 EPSILON 유무 |

위 표는 계산 결과를 견줄 때의 값이다. 검증하려는 것이 반올림 단위나 EPSILON 만큼의 차이라면 표의 값은 그 차이보다 커서, 반올림을 지워도 테스트가 통과한다 — 마지막 행을 쓴다.

---

### 4. 병렬처리 테스트 파라미터 최소화

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

## 주요 픽스처 (qbt/conftest.py)

qbt 공통 픽스처: qbt 테스트에서 재사용 가능한 설정과 테스트 데이터

- `sample_stock_df`: 기본 주식 데이터(OHLCV, 3행), `Date`는 `datetime.date`
- `integration_stock_df`: 통합 테스트용 주식 데이터(OHLCV, 25행), MA 계산에 충분한 크기
- `sample_ffr_df`: FFR 금리 데이터

  - 중요: `DATE` 컬럼은 `date` 객체가 아닌 `"yyyy-mm"` 문자열
  - 이유: 프로덕션 코드에서 월별 금리를 문자열 키로 처리

- `sample_expense_df`: Expense Ratio 운용비율 데이터

  - `DATE` 컬럼: `"yyyy-mm"` 문자열 (FFR과 동일 형식)
  - `VALUE` 컬럼: 0~1 비율

- `create_csv_file`: CSV 파일 생성 헬퍼(팩토리)
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

근거 위치: [conftest.py](qbt/conftest.py)

---

## 커버리지

실행 명령은 [docs/COMMANDS.md](../docs/COMMANDS.md) 「커버리지」. 핵심 모듈(`src/qbt/backtest` · `tqqq` · `utils`)은 최대한 높게 유지하고, 회귀 방지가 최우선이다.

---

## 자주 발생하는 문제

### 1. FFR 데이터 형식

```python
# 잘못된 예
"DATE": [date(2023, 1, 1)]  # date 객체

# 올바른 예
"DATE": ["2023-01"]  # yyyy-mm 문자열
```

### 2. 테스트 데이터의 자릿수

사람이 읽는 자릿수로 쓰는 일반 규칙은 `python-tests.md`. QBT 고유 — 소수점 자릿수의 SoT 는 [src/qbt/backtest/constants.py](../src/qbt/backtest/constants.py) 의 `ROUND_*` 상수이고 테스트 데이터도 같은 기준을 따른다. 허용오차는 위 「부동소수점/DF 비교 규칙」 표.

---

사용 중인 플러그인:

- pytest-cov: 코드 커버리지 측정
- freezegun: 시간 고정 (결정적 테스트)
