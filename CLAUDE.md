# QBT 프로젝트 가이드라인

> CRITICAL: 특정 패키지 또는 폴더의 파일을 분석하거나 작업할 때는
> 반드시 해당 폴더에 위치한 `CLAUDE.md`를 먼저 읽고 참고해야 합니다.
> 이는 필수 요구사항입니다. 루트 문서는 프로젝트 전반의 공통 규칙을 제공하며,
> 각 패키지 문서는 해당 도메인의 구체적인 맥락과 핵심 개념을 제공합니다.

## 문서 목적

이 문서는 AI 모델(Sonnet)이 QBT 프로젝트를 정확히 이해하고, 일관성 있는 응답을 생성하도록 돕습니다.
사람을 위한 상세 문서가 아닌, AI 모델의 판단 기준과 프로젝트 맥락을 제공합니다.

---

## 도메인별 CLAUDE.md 참고 규칙

각 작업 전에 해당 도메인의 CLAUDE.md를 반드시 읽습니다

- 공통 규칙: `CLAUDE.md`(루트), `scripts/CLAUDE.md`(스크립트), `src/qbt/utils/CLAUDE.md`(유틸), `tests/CLAUDE.md`(테스트)
- 도메인 규칙: 작업 대상 경로의 `CLAUDE.md`
  - 예: `src/qbt/backtest/CLAUDE.md`, `src/qbt/tqqq/CLAUDE.md` 등

---

## 계획서(Plan) 작성이 필요한 경우

원칙: 모든 코드 변경은 계획서를 작성한 후 진행합니다.

예외 (계획서 없이 바로 진행 가능):

- 오타 수정
- 주석 수정
- 로그 메시지 수정

위 예외를 제외한 모든 변경은 먼저 [`docs/CLAUDE.md`](docs/CLAUDE.md)를 읽고 `docs/plans/`에 계획서를 작성해야 합니다.

계획서 작성 절차 및 품질 게이트: [`docs/CLAUDE.md`](docs/CLAUDE.md)에서 상세 내용 확인

---

## 프로젝트 개요

QBT(Quant BackTest)는 주식 백테스팅 CLI 도구입니다.

핵심 기능 도메인:

- 시계열 데이터 수집 및 검증
- 이동평균 기반 거래 전략 백테스트
- 레버리지 상품 시뮬레이션 및 최적화
- 대화형 시각화 대시보드

기술 환경:

- Python 3.12 (`str | None` 문법 사용)
- 의존성 관리: Poetry
- 코드 품질: Black, Ruff
- 타입 체커: PyRight (strict mode for src/)
- 주요 라이브러리: pandas, yfinance, Plotly, Streamlit

---

## 디렉토리 구조

```
quant/
├── docs/              # 프로젝트 문서 및 계획서
│   ├── plans/         # 작업 계획서 저장소
│   └── archive/       # 완료/폐기 계획서
├── tests/             # 테스트 코드
│   └── conftest.py    # pytest 픽스처
├── scripts/           # CLI 스크립트 (도메인별 분리)
│   ├── data/          # 데이터 다운로드
│   ├── backtest/      # 백테스트 실행
│   └── tqqq/          # 레버리지 ETF 관련
│       ├── streamlit_daily_comparison.py  # 일별 비교 대시보드
│       └── streamlit_rate_spread_lab.py   # 금리-오차 분석 앱
├── src/qbt/           # 비즈니스 로직
│   ├── common_constants.py  # 공통 상수 (경로, 컬럼명, 연간 영업일 등)
│   ├── backtest/      # 백테스트 도메인
│   │   ├── constants.py  # 백테스트 전용 상수
│   │   ├── analysis.py   # 이동평균 계산 및 성과 지표
│   │   └── strategy.py   # 전략 실행 엔진
│   ├── tqqq/          # 레버리지 ETF 시뮬레이션
│   │   ├── constants.py        # 시뮬레이션 전용 상수
│   │   ├── simulation.py       # 시뮬레이션 엔진
│   │   ├── analysis_helpers.py # 금리-오차 분석 함수
│   │   ├── visualization.py    # Plotly 차트 생성
│   │   └── data_loader.py      # TQQQ 전용 데이터 로더
│   └── utils/         # 공통 유틸리티
│       ├── logger.py
│       ├── formatting.py
│       ├── data_loader.py       # CSV 로딩 통합
│       ├── cli_helpers.py       # 예외 처리 데코레이터
│       ├── parallel_executor.py # 병렬 처리
│       └── meta_manager.py      # 실행 메타데이터 관리
└── storage/           # 데이터 저장소
    ├── stock/         # 주식 데이터 CSV
    ├── etc/           # 기타 데이터 (금리 등)
    └── results/       # 분석 결과 CSV 및 메타데이터
        └── meta.json  # 실행 이력 메타데이터
```

---

## 아키텍처 원칙

### 1. 계층 분리 원칙

프로젝트는 명확한 2계층 구조를 따릅니다:

CLI 계층 (`scripts/`):

- 사용자 인터페이스 제공
- argparse로 명령행 인자 파싱
- 로거 초기화
- `@cli_exception_handler` 데코레이터로 예외 처리
- 비즈니스 로직 호출
- 종료 코드 반환 (0=성공, 1=실패)

비즈니스 로직 계층 (`src/qbt/`):

- 핵심 도메인 로직 구현
- 데이터 검증 및 변환
- ERROR 로그 금지 (CLI에서만 로깅)
- 예외는 `raise`로 전파

### 2. 상수 관리 (2계층)

공통 상수 (`common_constants.py`): 모든 도메인에서 공유하는 공통 상수

- 경로 상수 (디렉토리, 데이터 파일, 결과 파일)
- 데이터 상수 (컬럼명, 연간 영업일 수 등)
- 수치 안정성 상수 (분모 0 방지 및 로그 계산 안정성 확보)

도메인 상수 (`도메인/constants.py`): 각 도메인 전용 비즈니스 로직 상수

- 백테스트 파라미터 (초기 자본, 비용 비율, 그리드 서치 범위 등)
- 시뮬레이션 기본값 (레버리지 배율, 비용 모델 파라미터 등)

원칙: 상수 중복 금지 - 계층 간 중복 정의 시 즉시 통합

상수 명명 규칙:

4가지 접두사만 사용합니다:

- `COL_`: DataFrame 컬럼명 (내부 계산용 영문 토큰, 예: `COL_DATE`, `COL_CLOSE`, `COL_MONTH`)
- `KEY_`: 딕셔너리나 JSON 형태의 키값 (예: `KEY_SPREAD`, `KEY_OVERLAP_START`)
- `DISPLAY_`: CSV 출력이나 UI 표시용 한글 레이블 (예: `DISPLAY_DATE`, `DISPLAY_CAGR`, `DISPLAY_MONTH`)
- `DEFAULT_`: 분석/시뮬레이션 기본값 파라미터 (예: `DEFAULT_MIN_MONTHS`, `DEFAULT_HISTOGRAM_BINS`)

내부/출력 분리 원칙 (특히 Rate Spread Lab 등 CSV 저장이 필요한 모듈):

- 내부 계산: `COL_*` (영문 토큰, 예: `COL_RATE_PCT = "rate_pct"`)
- CSV 출력 헤더: `DISPLAY_*` (한글, 예: `DISPLAY_RATE_PCT = "금리수준(%)"`)
- 저장 직전에 `rename(COL -> DISPLAY)` 적용

지양하는 접두사 (새로 사용하지 않음):

- `PARAM_*` -> `DEFAULT_*` 사용
- `COL_TEMP_*`, `KEY_TEMP_*` -> 필요 시 `COL_*` 또는 로컬 변수 사용
- `CATEGORY_VALUE_*`, `TEMPLATE_*` -> 리터럴 또는 f-string 사용

도메인 한 곳에서만 사용되는 상수는 해당 도메인의 `constants.py`에 정의

### 3. 핵심 패턴

#### CSV 데이터 로딩

- 중앙 집중식: `utils/data_loader.py`에서 모든 CSV 로딩
- 로딩 시 자동 전처리 (날짜 파싱, 정렬, 중복 제거)
- 순환 임포트 방지

#### CLI 예외 처리

- 데코레이터 패턴: `@cli_exception_handler` 사용
- 자동 로거 감지
- 스택 트레이스 포함
- try-except 블록 불필요

#### 데이터 검증

- 다운로드 시 엄격한 검증 (결측치, 0값, 음수, 급등락)
- 보간 금지: 이상 발견 시 즉시 예외
- 검증 통과 후에만 저장

#### 병렬 처리

- 중앙 집중식: `utils/parallel_executor.py` 모듈 사용
- ProcessPoolExecutor 기반 CPU 집약적 작업 병렬화
- 입력 순서 보장된 결과 반환
- 단일 인자 함수용, 키워드 인자 함수용 두 가지 제공
- Windows 환경 대응 (pickle 가능한 함수만 사용)
- 예외 처리: 병렬 워커에서 예외 발생 시 즉시 전파하여 스크립트 실패 종료
  - 예외를 숨기고 None 반환하는 패턴 금지
  - 디버깅 용이성 및 잘못된 결과 방지

### 4. 구현 원칙

프로젝트 전반의 비즈니스 로직 구현 시 준수해야 하는 원칙입니다.

#### 데이터 불변성

- 원본 DataFrame을 변경하지 않음
- 계산 시 복사본 사용 (예: `df.copy()`)
- 함수 호출 후 원본 데이터 보장

#### 명시적 검증

- 파라미터 유효성 즉시 검증
- 유효하지 않은 입력 시 즉시 예외 발생 (ValueError)
- 암묵적 가정 금지

#### 상태 비저장

- 함수는 상태를 유지하지 않음
- 모든 입력을 파라미터로 전달
- 순수 함수 스타일 지향

#### 병렬 처리 지원

- 독립적인 연산은 병렬 실행 가능하도록 설계
- 순서 보장 필요 시 중앙 병렬 처리 모듈 사용 (`utils/parallel_executor.py`)
- pickle 가능한 함수만 사용 (모듈 최상위 레벨 정의)
- 워커 초기화 시 WORKER_CACHE 활용

---

## 코딩 표준

### 필수 규칙

타입 안정성:

- 모든 함수에 타입 힌트 필수
- Optional 타입은 `|` 문법 사용 (예: `str | None`, `int | None`)
- 여러 타입 허용 시에도 `|` 사용 (예: `int | float`, `Path | str`)

파일 처리:

- Path 객체만 사용 (문자열 경로 금지)

비율 표기 규칙:

- 모든 비율 값은 0~1 사이 소수로 정의 (0.03 = 3%)
- 주석에서 % 표기 시 혼란 방지를 위해 "비율 (0.03 = 3%)" 형식 사용
- 변수명 접미사: `_rate`, `_ratio`, `_pct` (모두 0~1 범위)
- 예시:
  - `SLIPPAGE_RATE = 0.003  # 슬리피지 비율 (0.003 = 0.3%)`
  - `buffer_zone_pct: float  # 버퍼존 비율 (0.03 = 3%)`

문서화:

- Google 스타일 Docstring
- 한글 작성
- 복잡한 로직은 넘버링 주석
- 주석 작성 원칙:
  - 현재 코드의 상태와 동작만 설명
  - 과거 상태, 변경 이력, 계획 단계는 기록하지 않음
  - 금지 패턴: "Phase 0", "Phase 3", "레드", "그린" 등 개발 단계 표현 사용 금지

네이밍:

- 함수/변수: `snake_case`
- 클래스: `PascalCase`
- 상수: `UPPER_SNAKE_CASE`

품질 검증:

- 모든 품질 검증은 `validate_project.py`를 통해서만 수행
  - 통합 스크립트: Ruff (린트) + PyRight (타입 체크) + Pytest (테스트)
  - 위치: 프로젝트 루트 `./validate_project.py`
- 직접 명령어 실행 금지 (원칙):
  - 금지: `poetry run ruff check .`
  - 금지: `poetry run pyright`
  - 금지: `poetry run pytest tests/`
- 표준 진입점:
  - 전체 검증: `poetry run python validate_project.py` (Ruff + PyRight + Pytest)
  - Ruff만: `poetry run python validate_project.py --only-lint`
  - PyRight만: `poetry run python validate_project.py --only-pyright`
  - Pytest만: `poetry run python validate_project.py --only-tests`
  - 커버리지 포함 테스트: `poetry run python validate_project.py --cov`
- 예외: 특정 모듈/파일만 테스트할 때 직접 pytest 명령 허용
  - 예: `poetry run pytest tests/test_strategy.py -v`
  - 예: `poetry run pytest tests/test_analysis.py::TestClass::test_method -v`
- 타입 체커: PyRight 단일 사용 (Mypy 제거됨)
  - 설정 파일: `pyrightconfig.json`
  - src 폴더: strict 모드 적용
  - tests, scripts 폴더: basic 모드 적용

### 로깅 정책

레벨 사용:

- DEBUG: 실행 흐름, 데이터 처리 상태
- WARNING: 잠재적 문제 상황
- ERROR: CLI 계층에서만 사용

금지 사항:

- INFO 레벨 사용 금지 (일반 정보는 DEBUG 사용)
- 이모지 사용 금지
- 함수명 중복 기재 금지 (로그 포맷에 자동 포함)

테이블 출력:

- 한글/영문 혼용 시 터미널 폭 정확 계산 (한글=2칸)
- `TableLogger` 클래스 사용
- 컬럼 정의 (이름, 폭, 정렬) -> 인스턴스 생성 -> 데이터 출력

요약 통계:

- 주요 지표를 간결하게 표시
- 구분선으로 섹션 분리

### 테스트

- 테스트 코드도 동일한 품질 기준 적용

---

## 데이터 처리 규칙

### CSV 파일 저장 위치

주식 데이터 (`storage/stock/`):

- `{TICKER}_max.csv`: 전체 기간
- `{TICKER}_{START}_{END}.csv`: 기간 지정
- `{TICKER}_{START}_latest.csv`: 시작일만
- `{TICKER}_synthetic_max.csv`: 합성 데이터

기타 데이터 (`storage/etc/`):

- `federal_funds_rate_monthly.csv`: 연방기금금리 월별 데이터
- `tqqq_net_expense_ratio_monthly.csv`: TQQQ 운용비율 월별 데이터

분석 결과 (`storage/results/`):

- `grid_results.csv`: 백테스트 그리드 서치 결과
- `tqqq_validation.csv`: TQQQ 시뮬레이션 검증 결과
- `tqqq_daily_comparison.csv`: TQQQ 일별 비교 데이터
- `meta.json`: 실행 이력 메타데이터 (각 CSV 생성 시점, 파라미터 등)

### 데이터 로딩 (utils/data_loader.py)

모든 CSV 로딩은 이 모듈을 통해 수행:

1. 파일 존재 확인
2. CSV 읽기
3. 필수 컬럼 검증
4. 날짜 파싱
5. 정렬
6. 중복 제거
7. DataFrame 반환

### 데이터 검증 (다운로드 시)

- 결측치, 0값, 음수값, 급등락 검사
- 보간 금지
- 즉시 커스텀 예외 발생
- 검증 통과 시에만 저장

### 데이터 정제

- 최근 일정 기간 제외 (데이터 소스 안정성 고려)
- 날짜는 `date` 객체로 통일
- 가격 정밀도는 소수점 자리 통일

---

## 개발 원칙

1. YAGNI: 필요성이 확인될 때 구현
2. 간결성: 불필요한 추상화 지양
3. 확장성: 도메인별 모듈 독립성 유지
4. 사용자 중심: 한글 메시지, 명확한 오류 정보
