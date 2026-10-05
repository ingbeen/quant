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
│   ├── strategies/           # 전략 클래스 (SignalStrategy Protocol 기반)
│   ├── allocators/           # 배분 규칙 (비중이 바뀌는 매매법, WeightAllocator Protocol 기반)
│   └── engines/              # 백테스트 엔진 (단일 자산, 포트폴리오)
├── tqqq/                # 레버리지 ETF 시뮬레이션 도메인
└── utils/               # 공통 유틸리티
```

---

## 아키텍처 원칙

### 1. 계층 분리 원칙

프로젝트는 명확한 2계층 구조를 따릅니다.

CLI 계층 (`scripts/`): [scripts/CLAUDE.md](../../scripts/CLAUDE.md) 참고

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

상수 명명 규칙 (4가지 접두사): 전역 `~/.claude/rules/python.md` 「네이밍」 참고

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
- `{TICKER}_synthetic_max.csv`: 합성 데이터 (상장 전은 시뮬레이션 또는 대용, 상장 후는 실물)
- `{TICKER}_proxy_max.csv`: 전 구간이 대용인 합성 데이터 (실물 구간 없음)
- 티커에 특수 문자가 있으면 파일 이름에도 그대로 쓴다 (예: `^SPGSCI_max.csv` · `GC=F_max.csv`)

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
- `summary.json`: 요약 지표 + 파라미터 + 월별/연간 수익률
- `walkforward_*.csv`: WFO 모드별 윈도우 결과 및 Stitched Equity (버퍼존 전략 전용)
- `walkforward_summary.json`: WFO 모드별 요약 통계 (버퍼존 전략 전용)

분석 결과 - 포트폴리오 (`storage/results/portfolio/`):

- 포트폴리오 백테스트 결과 (실험별 하위 폴더)

분석 결과 - 보완 전략 비중 그리드 (`storage/results/portfolio_grid/`):

- 실행별 지표 · 통과 판정 · 대용 검증 요약 CSV (실험별 결과 폴더 없음, 포트폴리오 폴더 밖이라 대시보드 탐색에 섞이지 않는다)

분석 결과 - 조합 그리드 (`storage/results/portfolio_combo_grid/`):

- Q-2-2XS + HAA + 로테이션 비중 격자 · 세 판의 실행별 지표 · 판정 기준별 지도 · 대체 판 확인 요약 CSV (실험별 결과 폴더 없음)

분석 결과 - 대체-실물 비교 (`storage/results/proxy_comparison/`):

- `summary.csv` (쌍마다 한 행) · `periods.csv` (쌍 × 연도 · 국면). 대시보드는 등록 쌍 표만 읽고 차트는 즉석 계산한다

분석 결과 - TQQQ 시뮬레이션 (`storage/results/tqqq/`):

- `tqqq_daily_comparison.csv`: TQQQ 일별 비교 데이터
- `spread_lab/`: 스프레드 모델 검증 결과 (튜닝, 시계열, 금리-오차 분석, 워크포워드 검증)

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
