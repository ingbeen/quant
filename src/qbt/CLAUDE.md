# qbt 패키지 가이드

> CRITICAL: qbt 패키지 작업 전에 이 문서를 반드시 읽어야 합니다.

프로젝트 전반의 공통 규칙은 [루트 CLAUDE.md](../../CLAUDE.md)를 참고하세요.

---

## 패키지 목적

qbt는 주식 백테스팅 CLI 도구의 코어 패키지입니다.

담당 도메인:

- 시계열 데이터 수집 및 검증
- 이동평균 기반 거래 전략 백테스트
- 레버리지 상품 시뮬레이션 및 최적화
- 대화형 시각화 대시보드

qbt 패키지는 순수 비즈니스 로직만 담당합니다. CLI 인터페이스는 `scripts/`에서 제공합니다.

---

## 디렉토리 구조

```
src/qbt/
├── common_constants.py  # 공통 상수 (경로, 컬럼명, 연간 영업일 등)
├── backtest/            # 백테스트 도메인
│   ├── constants.py          # 백테스트 전용 상수
│   ├── types.py              # TypedDict 정의 (성과 요약, 최적 파라미터 등)
│   ├── analysis.py           # 이동평균 계산 및 성과 지표
│   ├── walkforward.py        # 워크포워드 검증(WFO) 비즈니스 로직
│   ├── parameter_stability.py # 파라미터 고원 분석
│   ├── portfolio_types.py    # 포트폴리오 백테스트 타입 정의
│   ├── portfolio_configs.py  # 포트폴리오 실험 설정
│   ├── runners.py            # 전략 러너 팩토리
│   ├── csv_export.py         # 백테스트 CSV 저장용 변환 유틸리티
│   ├── strategy_registry.py  # 전략 레지스트리 (StrategySpec, STRATEGY_REGISTRY)
│   ├── strategies/           # 전략 클래스 (SignalStrategy Protocol 기반)
│   └── engines/              # 백테스트 엔진 (단일 자산, 포트폴리오)
├── tqqq/                # 레버리지 ETF 시뮬레이션 도메인
│   ├── constants.py        # 시뮬레이션 전용 상수
│   ├── simulation.py       # 시뮬레이션 엔진 (코어)
│   ├── analysis_helpers.py # 금리-오차 분석 함수
│   ├── spread_lab_helpers.py # Spread Lab 앱 전용 분석 함수
│   ├── visualization.py    # Plotly 차트 생성
│   └── data_loader.py      # TQQQ 전용 데이터 로더
└── utils/               # 공통 유틸리티
    ├── logger.py            # 로거 설정
    ├── formatting.py        # 출력 포맷팅 (TableLogger 포함)
    ├── data_loader.py       # CSV 로딩 통합
    ├── cli_helpers.py       # 예외 처리 데코레이터
    ├── parallel_executor.py # 병렬 처리
    ├── stock_downloader.py  # 주식 데이터 다운로드 및 검증
    └── meta_manager.py      # 실행 메타데이터 관리
```

---

## 아키텍처 원칙

### 1. 계층 분리 원칙

프로젝트는 명확한 2계층 구조를 따릅니다.

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

### 2. 상수 관리 (3계층)

상수 배치 규칙 (사용 범위 기반):

| 사용 범위                        | 배치 위치             |
| -------------------------------- | --------------------- |
| 2개 이상 도메인에서 사용         | `common_constants.py` |
| 도메인 내 2개 이상 파일에서 사용 | `도메인/constants.py` |
| 1개 파일에서만 사용              | 해당 파일 상단        |

카운트 규칙:

- 제외: 테스트 코드 (`tests/`), 단순 로그 출력
- 포함: 비즈니스 로직 (`src/`, `scripts/`)

공통 상수 (`common_constants.py`): 모든 도메인에서 공유하는 공통 상수

- 경로 상수 (디렉토리, 데이터 파일, 결과 파일)
- 데이터 상수 (컬럼명, 연간 영업일 수 등)
- 수치 안정성 상수 (분모 0 방지 및 로그 계산 안정성 확보)

도메인 상수 (`도메인/constants.py`): 도메인 내 여러 파일에서 공유하는 상수

- 백테스트 파라미터 (초기 자본, 비용 비율, 그리드 서치 범위 등)
- 시뮬레이션 기본값 (레버리지 배율, 비용 모델 파라미터 등)

로컬 상수 (해당 파일 상단): 단일 파일에서만 사용되는 상수

- 예: 특정 모듈의 DISPLAY 상수, 스크립트 전용 DEFAULT 상수
- 코드 근접성 향상으로 가독성 개선

원칙: 상수 중복 금지 - 계층 간 중복 정의 시 즉시 통합

상수 명명 규칙 (4가지 접두사):

- `COL_`: DataFrame 컬럼명 (내부 계산용 영문 토큰)
- `KEY_`: 딕셔너리나 JSON 형태의 키값
- `DISPLAY_`: CSV 출력이나 UI 표시용 한글 레이블
- `DEFAULT_`: 분석/시뮬레이션 기본값 파라미터

내부/출력 분리 원칙:

- 내부 계산: `COL_*` (영문 토큰)
- CSV 출력 헤더: `DISPLAY_*` (한글)
- 저장 직전에 `rename(COL -> DISPLAY)` 적용

지양하는 접두사 (새로 사용하지 않음):

- `PARAM_*` -> `DEFAULT_*` 사용
- `COL_TEMP_*`, `KEY_TEMP_*` -> 필요 시 `COL_*` 또는 로컬 변수 사용
- `CATEGORY_VALUE_*`, `TEMPLATE_*` -> 리터럴 또는 f-string 사용

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

---

## 구현 원칙

qbt 비즈니스 로직 구현 시 준수해야 하는 원칙입니다.

### 상태 비저장

- 함수는 상태를 유지하지 않음
- 모든 입력을 파라미터로 전달
- 순수 함수 스타일 지향

### 병렬 처리 지원

- 독립적인 연산은 병렬 실행 가능하도록 설계
- 순서 보장 필요 시 중앙 병렬 처리 모듈 사용 (`utils/parallel_executor.py`)
- pickle 가능한 함수만 사용 (모듈 최상위 레벨 정의)
- 워커 초기화 시 WORKER_CACHE 활용

병렬 처리 적합성 판단 기준:

ProcessPool 생성/소멸 + pickle 직렬화에는 고정 오버헤드가 존재한다.
작업의 계산량이 이 오버헤드보다 충분히 클 때만 병렬 처리가 유리하다.

| 조건             | 병렬 유리                   | 순차 유리                    |
| ---------------- | --------------------------- | ---------------------------- |
| Pool 생성 횟수   | 1~2회 (일괄 배치)           | 다수 (반복 생성/소멸)        |
| 작업당 계산량    | 높음 (Python 루프, 초 단위) | 낮음 (numpy 벡터화, ms 단위) |
| 작업 개수        | 수백 개 이상                | 소수                         |
| 오버헤드 vs 계산 | 오버헤드 << 계산            | 오버헤드 >= 계산             |

적용 사례:

- 병렬 유리: 그리드 서치 (1회 Pool 생성, 수백 개 Python 루프 작업 분배)
- 순차 유리: 워크포워드 최적화 (반복 호출마다 Pool 재생성, numpy 벡터화된 빠른 작업)

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

분석 결과 - 공통 (`storage/results/`):

- `meta.json`: 실행 이력 메타데이터 (각 CSV 생성 시점, 파라미터 등)

분석 결과 - 백테스트 (`storage/results/backtest/{strategy_name}/`):

각 전략의 결과는 전략명 하위 폴더에 저장된다.

- `signal.csv`: 시그널 데이터 (OHLC + MA + 전일대비%)
- `equity.csv`: 에쿼티 곡선 + 밴드 + 드로우다운
- `trades.csv`: 거래 내역 + 보유기간
- `summary.json`: 요약 지표 + 파라미터 + 월별 수익률
- `walkforward_*.csv`: WFO 모드별 윈도우 결과 및 Stitched Equity (버퍼존 전략 전용)
- `walkforward_summary.json`: WFO 모드별 요약 통계 (버퍼존 전략 전용)

분석 결과 - 포트폴리오 (`storage/results/portfolio/`):

- 포트폴리오 백테스트 결과 (실험별 하위 폴더)

분석 결과 - TQQQ 시뮬레이션 (`storage/results/tqqq/`):

- `tqqq_daily_comparison.csv`: TQQQ 일별 비교 데이터
- `spread_lab/`: 스프레드 모델 검증 결과 (튜닝, 시계열, 금리-오차 분석, 워크포워드 검증)

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

## 테이블 출력

- 한글/영문 혼용 시 터미널 폭 정확 계산 (한글=2칸)
- `TableLogger` 클래스 사용
- 컬럼 정의 (이름, 폭, 정렬) -> 인스턴스 생성 -> 데이터 출력
- 요약 통계: 주요 지표를 간결하게 표시, 구분선으로 섹션 분리

---

## 하위 도메인 CLAUDE.md 참조

각 하위 도메인 작업 시 해당 CLAUDE.md를 반드시 읽어야 합니다:

- [backtest/CLAUDE.md](backtest/CLAUDE.md): 백테스트 전략, 엔진, WFO, 포트폴리오 관련 규칙
- [tqqq/CLAUDE.md](tqqq/CLAUDE.md): 레버리지 ETF 시뮬레이션, 스프레드 모델 관련 규칙
- [utils/CLAUDE.md](utils/CLAUDE.md): 공통 유틸리티 모듈 관련 규칙
