# QBT (Quant BackTest)

주식 백테스팅 및 레버리지 ETF 시뮬레이션을 위한 Python CLI 도구입니다.

## 주요 기능

### qbt 패키지 (`src/qbt/`)

- 시계열 데이터 수집 및 검증 (Yahoo Finance 기반)
- 이동평균 기반 버퍼존 거래 전략 백테스트 — 엔진-전략 분리 아키텍처 (`SignalStrategy` Protocol, stateful 전략 클래스)
- 멀티자산 포트폴리오 백테스트 (목표 비중 배분 + 이중 트리거 리밸런싱, 자산 슬롯별 전략 파라미터 독립 설정 — 실험 구성은 `src/qbt/backtest/portfolio_configs.py`의 `PORTFOLIO_CONFIGS` 참고)
- 레버리지 ETF 시뮬레이션 및 비용 모델 최적화
- 대화형 시각화 대시보드 (Streamlit + Plotly)

### live 패키지 (`src/live/`)

- QBT 포트폴리오 전략의 실매매 알림 시스템
- GitHub Actions 자동 실행 (매일 장 마감 후)
- 주가 수집, 시그널 감지, FCM/텔레그램 알림
- Firebase RTDB 기반 Android 앱 연동

## 기술 스택

- **언어**: Python 3.12
- **의존성 관리**: Poetry
- **데이터 처리**: pandas, yfinance
- **시각화**: Plotly, Streamlit, matplotlib
- **코드 품질**: Black, Ruff
- **타입 체커**: PyRight
- **테스트**: pytest, pytest-cov, freezegun

## 빠른 시작

```bash
# 의존성 설치 (qbt만)
poetry install

# live 패키지 포함 설치
poetry install -E live

# 품질 검증 (Ruff + PyRight + Pytest)
poetry run python validate_project.py
```

---

## 워크플로우 1: 백테스트 전략 분석

이동평균 기반 버퍼존 전략의 성과를 평가합니다.

```bash
# 1. 데이터 다운로드 (전체 종목 일괄)
poetry run python scripts/data/download_data.py
# 또는 특정 종목만
poetry run python scripts/data/download_data.py QQQ

# 2. 단일 전략 검증 + 결과 저장
# 출력: 콘솔 (버퍼존 vs Buy&Hold 비교) + 전략별 결과 폴더 (signal, equity, trades, summary)
# --strategy 인자로 특정 전략만 실행 가능 (all / buffer_zone_tqqq / buffer_zone_tlt / ... / buy_and_hold_qqq 등, 기본값: all)
poetry run python scripts/backtest/run_single_backtest.py
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone_tqqq

# 3. 포트폴리오 백테스트 (선행: 1, TQQQ 합성 데이터 필요)
# 실험 구성은 src/qbt/backtest/portfolio_configs.py의 PORTFOLIO_CONFIGS 참고 (목록은 자주 변경됨)
# 자산 슬롯별 전략 파라미터 독립 설정 (ma_window, buy/sell_buffer_zone_pct, hold_days, ma_type)
# 리밸런싱: 엔진 레벨 고정 — 월 첫 거래일 편차 10% 초과 / 매일 편차 20% 초과 (실험 설정으로 변경 불가)
# 출력: storage/results/portfolio/{experiment_name}/ (equity, trades, summary, signal_{asset_id}, state_log, execution_comparison)
# 실행 직후 5개 정합성 규칙 자동 검증 (시그널-체결 lag, 리밸런싱 비중, EXIT_ALL 주수, 현금 비음수, 에쿼티 등식)
# 위반 발견 시 결과 저장 후 스크립트 중지 (ValueError)
poetry run python scripts/backtest/run_portfolio_backtest.py
# --experiment 인자로 특정 실험 선택 가능 (실험명은 PORTFOLIO_CONFIGS 참고, 기본값: all)
poetry run python scripts/backtest/run_portfolio_backtest.py --experiment <experiment_name>

# 4. 워크포워드 검증 (과최적화 검증, 선행: 1)
poetry run python scripts/backtest/run_walkforward.py
# 출력: 2-Mode 비교 (Dynamic/Fully Fixed) + stitched equity
# 진단 지표: WFE (CAGR/Calmar), Profit Concentration, min_trades 필터링
# 결과: storage/results/backtest/{전략명}/walkforward_*.csv, walkforward_summary.json

# --strategy 인자로 특정 전략만 실행 가능 (all / buffer_zone_tqqq / buffer_zone_qqq, 기본값: all)
poetry run python scripts/backtest/run_walkforward.py --strategy buffer_zone_tqqq

# 5. 파라미터 고원 분석 (선행: 1)
poetry run python scripts/backtest/run_param_plateau_all.py
# 파라미터(hold_days/sell_buffer/buy_buffer/ma_window) 통합 고원 분석
# --experiment 인자: all(기본) / hold_days / sell_buffer / buy_buffer / ma_window
# 출력: storage/results/backtest/param_plateau/ (피벗 CSV)

# 6. 대시보드 시각화 (선행: 2)
poetry run streamlit run scripts/backtest/app_single_backtest.py

# 7. 포트폴리오 비교 대시보드 (선행: 3)
poetry run streamlit run scripts/backtest/app_portfolio_backtest.py
# 시각화: 전체 비교(에쿼티 곡선/드로우다운 비교, 성과 지표 테이블), 실험별 탭(자산별 비중 추이, 거래 현황, 시그널 차트)

# 7-1. 포트폴리오 디버그 대시보드 (선행: 3)
poetry run streamlit run scripts/backtest/app_portfolio_debug.py
# 시각화: 일별 상태 네비게이터, 동기화 시계열 차트(에쿼티/비중/현금/주수), 체결 상세 테이블, 시그널-체결 추적

# 8. WFO 결과 시각화 대시보드 (선행: 3)
poetry run streamlit run scripts/backtest/app_walkforward.py
# 시각화: QQQ vs TQQQ 나란히 비교 (모드 요약, Stitched Equity, IS/OOS, 파라미터 추이, WFE 분포)

# 9. 파라미터 고원 시각화 대시보드 (선행: 4)
poetry run streamlit run scripts/backtest/app_parameter_stability.py
# 시각화: 4개 파라미터(MA/Buy/Sell/Hold) x 멀티자산 Calmar 라인차트, 고원 구간 하이라이트
```

**파라미터 변경**: [src/qbt/backtest/constants.py](src/qbt/backtest/constants.py)

---

## 워크플로우 2: TQQQ 레버리지 ETF 시뮬레이션

QQQ로부터 TQQQ를 시뮬레이션하고 실제 데이터와 비교하여 비용 모델을 검증합니다.

```bash
# 1. 필수 데이터 다운로드 (전체 종목 일괄)
poetry run python scripts/data/download_data.py
# 또는 개별 다운로드
poetry run python scripts/data/download_data.py QQQ
poetry run python scripts/data/download_data.py TQQQ

# 2. 일별 비교 데이터 생성 (softplus 동적 스프레드 모델)
poetry run python scripts/tqqq/generate_daily_comparison.py
# 출력: storage/results/tqqq/tqqq_daily_comparison.csv

# 3. 합성 TQQQ 데이터 생성 (선택)
poetry run python scripts/tqqq/generate_synthetic.py
# 출력: storage/stock/TQQQ_synthetic_max.csv
```

### 대시보드 앱 실행

```bash
# 일별 비교 대시보드
# 선행: 1 → 2
# 필요: storage/results/tqqq/tqqq_daily_comparison.csv
poetry run streamlit run scripts/tqqq/app_daily_comparison.py
```

### 스프레드 모델 검증 결과 열람 (spread_lab/)

스프레드 모델 파라미터는 확정 상태이며, 결과 열람용 시각화 앱만 제공합니다.

```bash
# 금리-오차 관계 분석 앱 (시각화 전용)
# 필수: storage/results/tqqq/tqqq_daily_comparison.csv
# 선택: storage/results/tqqq/spread_lab/ 하위 결과 CSV
poetry run streamlit run scripts/tqqq/spread_lab/app_rate_spread_lab.py
```

**파라미터 변경**: [src/qbt/tqqq/constants.py](src/qbt/tqqq/constants.py)

---

## 워크플로우 3: QBT Live (실매매 알림)

QBT 포트폴리오 전략의 실매매 알림 시스템입니다. GitHub Actions에서 매일 장 마감 후 자동 실행됩니다.

```bash
# 의존성 설치 (live extras 포함)
poetry install -E live

# 초기 1회 (원격 qbt-live-state 리포에 초기 상태 push)
poetry run python -m live init --capital 100000000
poetry run python -m live init-data

# 최초 배포 직후 또는 스플릿/무상증자 대응 후 1회 (과거 연도 차트 archive 일괄 생성)
poetry run python -m live backfill-chart-archive
poetry run python -m live backfill-chart-archive --dry-run
poetry run python -m live backfill-chart-archive --year 2025

# 매일 (GitHub Actions 가 자동 실행, 로컬에서 수동 실행도 가능)
poetry run python -m live run-daily
poetry run python -m live run-daily --trade-date 2026-04-10

# 디버깅 / 조회
poetry run python -m live drift
poetry run python -m live history --tail 20
poetry run python -m live fetch-fills
poetry run python -m live notify-failure -m "수동 테스트"
```

**환경변수**: 로컬 실행 시 프로젝트 루트의 `.env` 파일이 자동 로드됩니다. 필요한 변수:

- `STATE_REPO_PAT` — `qbt-live-state` 리포 clone/push용 GitHub PAT
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — 알림 발송용
- `GOOGLE_APPLICATION_CREDENTIALS` — Firebase service account JSON 절대 경로

상세 가이드: [src/live/CLAUDE.md](src/live/CLAUDE.md)

---

## 주요 명령어

### 품질 검증 (통합)

```bash
# 전체 검증 (Ruff + PyRight + Pytest) - 권장
poetry run python validate_project.py

# 커버리지 포함 전체 검증
poetry run python validate_project.py --cov

# 테스트만 실행
poetry run python validate_project.py --only-tests

# Ruff 린트만 실행
poetry run python validate_project.py --only-lint

# PyRight 타입 체크만 실행
poetry run python validate_project.py --only-pyright
```

### 테스트 (특정 모듈/파일)

```bash
# qbt 특정 모듈만 테스트
poetry run pytest tests/qbt/test_buffer_zone_run.py -v

# 특정 클래스만 테스트
poetry run pytest tests/qbt/test_buffer_zone_run.py::TestRunBufferStrategy -v

# live 테스트만 실행
poetry run pytest tests/live/ -v

# 실패한 테스트만 재실행
poetry run pytest --lf -v

# 디버깅 모드 (print 출력 포함)
poetry run pytest tests/qbt/test_xxx.py -s -vv
```

### 코드 포맷

```bash
# 포맷 적용 (마지막 단계에서만)
poetry run black .

# ruff 자동 수정 (예외적 사용)
poetry run ruff check --fix .
```

### 커버리지

```bash
# 커버리지 포함 검증 (권장)
poetry run python validate_project.py --cov

# HTML 리포트 생성 (직접 pytest 사용)
poetry run pytest --cov=src/qbt --cov-report=html tests/qbt/
poetry run pytest --cov=src/live --cov-report=html tests/live/
poetry run pytest --cov=src/qbt --cov=src/live --cov-report=html tests/
# 결과: htmlcov/index.html 브라우저로 열기
```

---

## 데이터 다운로드 옵션

```bash
# 전체 종목 일괄 다운로드 (SPY, IWM, EFA, EEM, GLD, TLT, QQQ, TQQQ)
poetry run python scripts/data/download_data.py

# 특정 종목 전체 기간
poetry run python scripts/data/download_data.py TICKER

# 시작일 지정
poetry run python scripts/data/download_data.py TICKER --start YYYY-MM-DD

# 기간 지정
poetry run python scripts/data/download_data.py TICKER --start YYYY-MM-DD --end YYYY-MM-DD

# 예시
poetry run python scripts/data/download_data.py QQQ --start 2020-01-01
```

---

## 프로젝트 구조

```
quant/
├── src/               # 패키지 소스 코드
│   ├── qbt/           # 백테스트 코어 패키지
│   │   ├── common_constants.py  # 공통 상수
│   │   ├── backtest/  # 백테스트 도메인 (strategies/, engines/)
│   │   ├── tqqq/      # TQQQ 시뮬레이션
│   │   └── utils/     # 공통 유틸리티
│   └── live/          # 실매매 알림 패키지
├── tests/             # 테스트 코드
│   ├── qbt/           # qbt 패키지 테스트
│   └── live/          # live 패키지 테스트
├── scripts/           # CLI 스크립트 (사용자 실행)
│   ├── data/          # download_data.py
│   ├── backtest/      # 백테스트 실행 + 대시보드 앱
│   └── tqqq/          # generate_*.py, app_daily_comparison.py
├── docs/              # 프로젝트 문서 및 계획서
│   ├── plans/         # 작업 계획서 저장소
│   └── archive/       # 완료/폐기 계획서
├── storage/           # 데이터 저장소
│   ├── stock/         # 주식 데이터 CSV
│   ├── etc/           # 금리 데이터
│   └── results/       # 분석 결과 (backtest/, portfolio/, tqqq/)
└── vendor/            # 서드파티 포크
```

---

## 주요 결과 파일

### 백테스트

각 전략의 결과는 `storage/results/backtest/{strategy_name}/` 하위에 저장됩니다.

- `signal.csv`: 시그널 데이터 (OHLC + MA + 전일대비%)
- `equity.csv`: 에쿼티 곡선 + 밴드 + 드로우다운
- `trades.csv`: 거래 내역 + 보유기간
- `summary.json`: 요약 지표 + 파라미터 + 월별 수익률
- `walkforward_dynamic.csv`, `walkforward_fully_fixed.csv`: WFO 윈도우별 결과
- `walkforward_equity_dynamic.csv`, `walkforward_equity_fully_fixed.csv`: stitched equity
- `walkforward_summary.json`: 2-Mode 비교 요약 (Dynamic/Fully Fixed, WFE CAGR/Calmar, Profit Concentration)

### 포트폴리오 백테스트

각 실험의 결과는 `storage/results/portfolio/{experiment_name}/` 하위에 저장됩니다.

- `equity.csv`: 합산 에쿼티 + 현금 + 드로우다운 + 자산별 평가액/비중/시그널 + 리밸런싱 여부
- `trades.csv`: 전 자산 거래 내역 (asset_id, trade_type, holding_days 포함)
- `summary.json`: 전체 포트폴리오 요약 + 자산별 요약(target_weight, 거래수, 승률) + 설정 파라미터
- `signal_{asset_id}.csv`: 자산별 시그널 (OHLCV + MA + 밴드 + 전일종가대비%)
- `state_log.csv`: 일별 엔진 내부 상태 (시그널 판정, 주문 의도, 체결 결과, 포지션/비중 변화)
- `execution_comparison.csv`: 체결 발생일의 자산별 전후 비중/주수/평가액 비교

실험 구성 및 자산 배분 상세는 [portfolio_configs.py](src/qbt/backtest/portfolio_configs.py)의 `PORTFOLIO_CONFIGS`를 직접 참고하세요. 실험 목록은 변경 빈도가 높아 README에 직접 명시하지 않습니다.

### TQQQ 시뮬레이션

- `storage/results/tqqq/tqqq_daily_comparison.csv`: 일별 비교 데이터 (대시보드 입력, softplus 동적 스프레드)
- `storage/stock/TQQQ_synthetic_max.csv`: 합성 TQQQ 데이터
- `storage/results/meta.json`: 실행 이력 메타데이터
- `storage/results/tqqq/spread_lab/`: 스프레드 모델 검증 결과 (튜닝, 워크포워드, 금리-오차 분석 등)

---

## 개발 가이드

### 파라미터 변경

- **백테스트 파라미터** (그리드 범위, 4P 고정값 등): [src/qbt/backtest/constants.py](src/qbt/backtest/constants.py)
- **포트폴리오 실험 설정** (자산 구성, 목표 비중, 슬롯별 전략 파라미터): [src/qbt/backtest/portfolio_configs.py](src/qbt/backtest/portfolio_configs.py)
- **TQQQ 시뮬레이션**: [src/qbt/tqqq/constants.py](src/qbt/tqqq/constants.py)
- **공통 설정** (경로, 컬럼명 등): [src/qbt/common_constants.py](src/qbt/common_constants.py)

### 코딩 표준

- **타입 힌트**: 모든 함수 필수 (`str | None` 문법)
- **타입 체커**: PyRight (strict mode for src/, basic mode for tests/scripts)
- **문서화**: Google 스타일 Docstring (한글)
- **네이밍**: 함수/변수 `snake_case`, 클래스 `PascalCase`, 상수 `UPPER_SNAKE_CASE`
- **로깅**: DEBUG(실행 흐름), WARNING(경고), ERROR(CLI만) / INFO 및 이모지 금지

### 테스트 작성

- **패턴**: Given-When-Then
- **격리**: `tmp_path` 픽스처
- **결정성**: `@freeze_time` 데코레이터

---

## 참고 문서

프로젝트의 상세 규칙과 아키텍처는 각 디렉토리의 `CLAUDE.md` 파일을 참고하세요:

- [프로젝트 가이드라인](CLAUDE.md): 전체 프로젝트 공통 규칙
- [qbt 패키지 가이드](src/qbt/CLAUDE.md): qbt 패키지 아키텍처 및 규칙
- [live 패키지 가이드](src/live/CLAUDE.md): live 도메인 규칙
- [문서 및 계획서 가이드](docs/CLAUDE.md): 계획서 작성 및 운영 규칙
- [CLI 스크립트 가이드](scripts/CLAUDE.md): CLI 스크립트 계층 규칙
- [백테스트 도메인](src/qbt/backtest/CLAUDE.md): 백테스트 로직
- [TQQQ 시뮬레이션](src/qbt/tqqq/CLAUDE.md): 레버리지 ETF 시뮬레이션
- [유틸리티 가이드](src/qbt/utils/CLAUDE.md): 공통 유틸리티 규칙
- [테스트 가이드](tests/CLAUDE.md): 테스트 작성 규칙

---

**라이선스**: 개인 학습 및 연구 목적
