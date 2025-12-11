# Claude Code Guidelines for QBT Project

## 프로젝트 개요

QBT(Quant BackTest)는 주식 백테스팅 Python CLI 도구입니다.

**주요 기능**:

- Yahoo Finance 데이터 다운로드
- 버퍼존 기반 이동평균 전략 백테스트
- 레버리지 ETF 시뮬레이션
- Streamlit 대시보드

**기술 스택**:

- Python 3.10+ (`str | None` 문법 사용)
- Poetry, pandas, yfinance, Plotly, Streamlit
- Black, Ruff

## 디렉토리 구조

```
quant/
├── scripts/           # CLI 스크립트 (도메인별 분리)
│   ├── data/          # 데이터 다운로드
│   ├── backtest/      # 백테스트 실행
│   └── tqqq/          # 레버리지 ETF 관련
├── src/qbt/           # 비즈니스 로직
│   ├── common_constants.py  # 공통 상수 (경로, 컬럼명, 연간 영업일 등)
│   ├── backtest/      # 백테스트 도메인
│   │   ├── constants.py  # 백테스트 전용 상수
│   │   ├── data.py
│   │   ├── strategy.py
│   │   └── metrics.py
│   ├── synth/         # 합성 데이터 생성
│   │   └── constants.py  # 시뮬레이션 전용 상수
│   ├── visualization/ # 시각화
│   └── utils/         # 공통 유틸리티
│       ├── logger.py
│       ├── formatting.py
│       ├── data_loader.py       # CSV 로딩 통합
│       ├── cli_helpers.py       # 예외 처리 데코레이터
│       └── parallel_executor.py # 병렬 처리
├── data/raw/          # CSV 저장소
└── results/           # 분석 결과
```

## 아키텍처 원칙

### 1. 2계층 구조

**CLI Layer (scripts/)**:

- 로거 초기화
- argparse로 커맨드 파싱
- 예외 처리 데코레이터 사용
- 유틸리티 모듈로 비즈니스 로직 호출
- 종료 코드 반환 (0=성공, 1=실패)

**Business Logic Layer (src/qbt/)**:

- 핵심 기능 수행
- 데이터 검증
- **ERROR 로그 금지** (CLI에서만 로깅)
- 예외는 `raise`로 전파

### 2. 상수 관리 (2계층)

- **공통 constants** (`common_constants.py`): 모든 도메인에서 공유하는 공통 상수
  - 경로 상수 (디렉토리, 데이터 파일, 결과 파일)
  - 데이터 상수 (컬럼명, 연간 영업일 수 등)
- **도메인 constants** (`도메인/constants.py`): 각 도메인 전용 비즈니스 로직 상수
  - 백테스트 파라미터 (초기 자본, 슬리피지, 그리드 서치 범위 등)
  - 시뮬레이션 기본값 (레버리지 배율, 비용 모델 파라미터 등)
- 상수 중복 금지 - 계층 간 중복 정의 시 즉시 통합

### 3. 핵심 패턴

#### CSV 데이터 로딩

- **중앙 집중식**: `utils/data_loader.py`에서 모든 CSV 로딩
- 로딩 시 자동 전처리 (날짜 파싱, 정렬, 중복 제거)
- 순환 임포트 방지

#### CLI 예외 처리

- **데코레이터 패턴**: `@cli_exception_handler` 사용
- 자동 로거 감지
- 스택 트레이스 포함
- try-except 블록 불필요

#### 데이터 검증

- 다운로드 시 엄격한 검증 (결측치, 0값, 음수, 급등락)
- **보간 금지**: 이상 발견 시 즉시 예외
- 검증 통과 후에만 저장

#### 병렬 처리

- **중앙 집중식**: `utils/parallel_executor.py` 모듈 사용
- ProcessPoolExecutor 기반 CPU 집약적 작업 병렬화
- 입력 순서 보장된 결과 반환
- 단일 인자 함수용, 키워드 인자 함수용 두 가지 제공
- Windows 환경 대응 (pickle 가능한 함수만 사용)

## 코딩 규칙

### 필수 규칙

- **타입 힌트**: 모든 함수에 필수 (`str | None` 문법)
- **pathlib.Path**: 모든 파일 작업에 사용
- **Docstring**: Google 스타일, 한글 작성
- **네이밍**: 함수=`snake_case`, 클래스=`PascalCase`, 상수=`UPPER_SNAKE_CASE`
- **포맷**: Black (120자), 수동 실행 금지 (에디터 자동화)
- **로그 레벨**: DEBUG/WARNING/ERROR만 사용 (INFO 금지)

### 테스트

- Claude Code는 테스트 실행 금지
- 테스트 작성은 가능
- 사용자가 직접 실행

### 주석

- 복잡한 로직은 넘버링 주석
- 일반적 표현 사용 ("5회" → "임계값 초과 시")
- 코드 수정 시 주석도 함께 업데이트

## 로깅

### 로그 레벨

- **DEBUG**: 데이터 처리, 실행 흐름
- **WARNING**: 잠재적 문제
- **ERROR**: CLI에서만 사용

**INFO 사용 금지** - 일반 정보는 DEBUG 사용

### 가이드라인

- 한글 작성
- 이모지 금지
- 간결하게
- 함수명은 로그 포맷에 자동 포함 (중복 기재 금지)

### 테이블 출력

- 한글/영문 혼용 시 터미널 폭 정확 계산 (한글=2칸)
- `TableLogger` 클래스 사용
- 컬럼 정의 (이름, 폭, 정렬) → 인스턴스 생성 → 데이터 출력

## 데이터 처리

### CSV 파일명 규칙

- `{TICKER}_max.csv`: 전체 기간
- `{TICKER}_{START}_{END}.csv`: 기간 지정
- `{TICKER}_{START}_latest.csv`: 시작일만
- `{TICKER}_synthetic_max.csv`: 합성 데이터

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

- 최근 일정 기간 제외 (Yahoo Finance 안정성)
- 날짜는 `date` 객체
- 가격은 소수점 6자리

## 백테스트

### 버퍼존 전략

- 이동평균 주변 상하 버퍼존 설정
- 버퍼존 돌파 시 매매 신호
- 최근 거래 빈도로 파라미터 동적 조정
- 롱 온리, 최대 1 포지션
- 익일 시가 진입/청산
- 슬리피지 적용

## 레버리지 ETF 시뮬레이션

- 일일 리밸런싱
- 동적 비용 모델 (연방기금금리 + 스프레드)
- 복리 효과 반영
- 2D 그리드 서치로 파라미터 최적화
- 실제 데이터와 비교 검증

## Streamlit 대시보드

- 스크립트에 진입점, 비즈니스 로직은 분리
- 데이터 캐싱 데코레이터
- Plotly 인터랙티브 차트
- 순수 함수로 차트 작성
- 필수 컬럼 검증, 결측치 처리

## 개발 철학

1. **YAGNI**: 필요할 때 구현
2. **간결성**: 불필요한 추상화 지양
3. **확장성**: 도메인별 모듈 분리
4. **사용자 중심**: 한글 메시지, 명확한 에러
