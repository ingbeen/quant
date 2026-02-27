# QBT (Quant BackTest)

주식 백테스팅 및 레버리지 ETF 시뮬레이션을 위한 Python CLI 도구입니다.

## 주요 기능

- 시계열 데이터 수집 및 검증 (Yahoo Finance 기반)
- 이동평균 기반 거래 전략 백테스트
- 레버리지 ETF 시뮬레이션 및 비용 모델 최적화
- 대화형 시각화 대시보드 (Streamlit + Plotly)

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
# 의존성 설치
poetry install

# 품질 검증 (Ruff + PyRight + Pytest)
poetry run python validate_project.py
```

---

## 워크플로우 1: 백테스트 전략 분석

이동평균 기반 버퍼존 전략의 최적 파라미터를 탐색하고 성과를 평가합니다.

```bash
# 1. 데이터 다운로드
poetry run python scripts/data/download_data.py QQQ

# 2. 파라미터 최적화 (그리드 서치)
poetry run python scripts/backtest/run_grid_search.py
# 출력: storage/results/backtest/{전략명}/grid_results.csv

# --strategy 인자로 특정 전략만 실행 가능 (all / buffer_zone_tqqq / buffer_zone_atr_tqqq / buffer_zone_qqq, 기본값: all)
poetry run python scripts/backtest/run_grid_search.py --strategy buffer_zone_tqqq

# 3. 단일 전략 검증 + 결과 저장
poetry run python scripts/backtest/run_single_backtest.py
# 출력: 콘솔 (버퍼존 vs Buy&Hold 비교) + 전략별 결과 폴더 (signal, equity, trades, summary)

# --strategy 인자로 특정 전략만 실행 가능 (all / buffer_zone / buy_and_hold, 기본값: all)
poetry run python scripts/backtest/run_single_backtest.py --strategy buffer_zone

# 4. 워크포워드 검증 (과최적화 검증, 선행: 1~2)
poetry run python scripts/backtest/run_walkforward.py
# 출력: 3-Mode 비교 (동적/sell고정/전체고정) + stitched equity
# 진단 지표: WFE (CAGR/Calmar), Profit Concentration, min_trades 필터링
# 결과: storage/results/backtest/{전략명}/walkforward_*.csv, walkforward_summary.json

# --strategy 인자로 특정 전략만 실행 가능 (all / buffer_zone_tqqq / buffer_zone_atr_tqqq / buffer_zone_qqq, 기본값: all)
poetry run python scripts/backtest/run_walkforward.py --strategy buffer_zone_tqqq

# 5. CSCV/PBO/DSR 과최적화 통계 검증 (선행: 1)
poetry run python scripts/backtest/run_cpcv_analysis.py
# 출력: PBO (과최적화 확률), DSR (보정 Sharpe 유의성)
# 결과: storage/results/backtest/{전략명}/cscv_analysis.json, cscv_logit_lambdas.csv

# --strategy 인자로 특정 전략만 실행 가능 (all / buffer_zone_tqqq / buffer_zone_atr_tqqq / buffer_zone_qqq, 기본값: all)
poetry run python scripts/backtest/run_cpcv_analysis.py --strategy buffer_zone_tqqq

# 6. 대시보드 시각화 (선행: 3)
poetry run streamlit run scripts/backtest/app_single_backtest.py
```

**파라미터 변경**: [src/qbt/backtest/constants.py](src/qbt/backtest/constants.py)

---

## 워크플로우 2: TQQQ 레버리지 ETF 시뮬레이션

QQQ로부터 TQQQ를 시뮬레이션하고 실제 데이터와 비교하여 비용 모델을 검증합니다.

```bash
# 1. 필수 데이터 다운로드
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

### 스프레드 모델 검증 (spread_lab/)

스프레드 모델이 확정되어 일상적으로 사용할 일은 없지만, 재검증이 필요한 경우 사용합니다.

```bash
# Softplus 동적 스프레드 모델 튜닝
poetry run python scripts/tqqq/spread_lab/tune_softplus_params.py
# 결과: storage/results/tqqq/spread_lab/tqqq_softplus_tuning.csv
#       storage/results/tqqq/spread_lab/tqqq_softplus_spread_series_static.csv

# 워크포워드 검증 (3가지 모드 순차 실행: 동적/b고정/완전고정)
# 필요: storage/results/tqqq/spread_lab/tqqq_softplus_tuning.csv
poetry run python scripts/tqqq/spread_lab/validate_walkforward.py
# 결과: storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_walkforward.csv
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_walkforward_summary.csv
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_walkforward_fixed_b.csv
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_walkforward_fixed_b_summary.csv
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_walkforward_fixed_ab.csv
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_walkforward_fixed_ab_summary.csv

# 금리-오차 분석 CSV 생성
# 필요: storage/results/tqqq/tqqq_daily_comparison.csv
poetry run python scripts/tqqq/spread_lab/generate_rate_spread_lab.py
# 결과: storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_monthly.csv
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_summary.csv
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_model.csv (조건부)

# 금리-오차 관계 분석 앱
# 필수: storage/results/tqqq/tqqq_daily_comparison.csv
# 선택: storage/results/tqqq/spread_lab/tqqq_softplus_tuning.csv
#       storage/results/tqqq/spread_lab/tqqq_softplus_spread_series_static.csv
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_walkforward.csv (+summary)
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_walkforward_fixed_b.csv (+summary)
#       storage/results/tqqq/spread_lab/tqqq_rate_spread_lab_walkforward_fixed_ab.csv (+summary)
poetry run streamlit run scripts/tqqq/spread_lab/app_rate_spread_lab.py
```

**파라미터 변경**: [src/qbt/tqqq/constants.py](src/qbt/tqqq/constants.py)

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
# 특정 모듈만 테스트
poetry run pytest tests/test_strategy.py -v

# 특정 클래스만 테스트
poetry run pytest tests/test_strategy.py::TestRunBufferStrategy -v

# 실패한 테스트만 재실행
poetry run pytest --lf -v

# 디버깅 모드 (print 출력 포함)
poetry run pytest tests/test_xxx.py -s -vv
```

### 코드 포맷

```bash
# 포맷 적용 (마지막 단계에서만)
poetry run black .

# ruff 자동 수정 (예외적 사용)
poetry run ruff check --fix .
```

---

## 데이터 다운로드 옵션

```bash
# 전체 기간
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
├── docs/              # 프로젝트 문서 및 계획서
│   ├── plans/         # 작업 계획서 저장소
│   └── archive/       # 완료/폐기 계획서
├── scripts/           # CLI 스크립트 (사용자 실행)
│   ├── data/          # download_data.py
│   ├── backtest/      # run_grid_search.py, run_single_backtest.py, run_walkforward.py, run_cpcv_analysis.py, app_single_backtest.py
│   └── tqqq/          # generate_*.py, app_daily_comparison.py
│       ├── app_daily_comparison.py        # 일별 비교 대시보드
│       └── spread_lab/                    # 스프레드 모델 검증 (확정 후 아카이빙)
│           ├── tune_softplus_params.py    # Softplus 튜닝 CLI
│           ├── validate_walkforward.py    # 워크포워드 검증 CLI (3모드 통합)
│           ├── generate_rate_spread_lab.py # 금리-오차 분석 CSV 생성
│           └── app_rate_spread_lab.py     # 금리-오차 분석 앱 (시각화)
├── src/qbt/           # 비즈니스 로직
│   ├── common_constants.py  # 공통 상수
│   ├── backtest/      # 백테스트 도메인 (constants.py, types.py, cpcv.py, strategies/)
│   ├── tqqq/          # TQQQ 시뮬레이션 (constants.py, types.py)
│   └── utils/         # 공통 유틸리티
├── storage/           # 데이터 저장소
│   ├── stock/         # 주식 데이터 CSV
│   ├── etc/           # 금리 데이터
│   └── results/       # 분석 결과 + meta.json
│       ├── backtest/          # 백테스트 결과 (전략별 하위 폴더)
│       │   ├── buffer_zone_tqqq/      # 버퍼존 전략 (TQQQ) 결과
│       │   ├── buffer_zone_atr_tqqq/ # 버퍼존 ATR 전략 (TQQQ) 결과
│       │   ├── buffer_zone_qqq/      # 버퍼존 전략 (QQQ) 결과
│       │   ├── buy_and_hold_qqq/  # Buy & Hold (QQQ) 전략 결과
│       │   └── buy_and_hold_tqqq/ # Buy & Hold (TQQQ) 전략 결과
│       └── tqqq/              # TQQQ 시뮬레이션 결과
│           └── spread_lab/    # 스프레드 모델 검증 결과
└── tests/             # 테스트 코드
```

---

## 주요 결과 파일

### 백테스트

각 전략의 결과는 `storage/results/backtest/{strategy_name}/` 하위에 저장됩니다.

- `grid_results.csv`: 파라미터 그리드 서치 결과 (버퍼존 전략 전용)
- `signal.csv`: 시그널 데이터 (OHLC + MA + 전일대비%)
- `equity.csv`: 에쿼티 곡선 + 밴드 + 드로우다운
- `trades.csv`: 거래 내역 + 보유기간
- `summary.json`: 요약 지표 + 파라미터 + 월별 수익률
- `walkforward_dynamic.csv`, `walkforward_sell_fixed.csv`, `walkforward_fully_fixed.csv`: WFO 윈도우별 결과
- `walkforward_equity_dynamic.csv`, `walkforward_equity_sell_fixed.csv`, `walkforward_equity_fully_fixed.csv`: stitched equity
- `walkforward_summary.json`: 3-Mode 비교 요약 (WFE CAGR/Calmar, Profit Concentration, min_trades 포함)
- `cscv_analysis.json`: CSCV/PBO/DSR 과최적화 통계 검증 결과 (버퍼존 전략 전용)
- `cscv_logit_lambdas.csv`: CSCV logit lambda 분포 (PBO 진단용, 버퍼존 전략 전용)

### TQQQ 시뮬레이션

- `storage/results/tqqq/tqqq_daily_comparison.csv`: 일별 비교 데이터 (대시보드 입력, softplus 동적 스프레드)
- `storage/stock/TQQQ_synthetic_max.csv`: 합성 TQQQ 데이터
- `storage/results/meta.json`: 실행 이력 메타데이터
- `storage/results/tqqq/spread_lab/`: 스프레드 모델 검증 결과 (튜닝, 워크포워드, 금리-오차 분석 등)

---

## 문제 해결

### 데이터 다운로드 실패

```bash
# 다른 기간으로 재시도
poetry run python scripts/data/download_data.py QQQ --start 2020-01-01
```

### 테스트 실패

```bash
# 전체 품질 검증 후 재실행
poetry run python validate_project.py
```

### 대시보드 실행 오류

각 앱은 선행 스크립트의 결과 파일이 필요합니다. 해당 워크플로우의 순서를 따라 실행하세요.

```bash
# 백테스트 대시보드 (선행: 워크플로우 1의 1~3)
poetry run streamlit run scripts/backtest/app_single_backtest.py

# 일별 비교 대시보드 (선행: 워크플로우 2의 1~2)
poetry run streamlit run scripts/tqqq/app_daily_comparison.py

# 금리-오차 분석 앱 (선행: spread_lab 스크립트 실행)
poetry run streamlit run scripts/tqqq/spread_lab/app_rate_spread_lab.py
```

---

## 개발 가이드

### 파라미터 변경

- **백테스트**: [src/qbt/backtest/constants.py](src/qbt/backtest/constants.py)
- **TQQQ 시뮬레이션**: [src/qbt/tqqq/constants.py](src/qbt/tqqq/constants.py)
- **공통 설정**: [src/qbt/common_constants.py](src/qbt/common_constants.py)

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

- [프로젝트 가이드라인](CLAUDE.md): 전체 프로젝트 규칙
- [문서 및 계획서 가이드](docs/CLAUDE.md): 계획서 작성 및 운영 규칙
- [CLI 스크립트 가이드](scripts/CLAUDE.md): CLI 스크립트 계층 규칙
- [유틸리티 가이드](src/qbt/utils/CLAUDE.md): 공통 유틸리티 규칙
- [백테스트 도메인](src/qbt/backtest/CLAUDE.md): 백테스트 로직
- [TQQQ 시뮬레이션](src/qbt/tqqq/CLAUDE.md): 레버리지 ETF 시뮬레이션
- [테스트 가이드](tests/CLAUDE.md): 테스트 작성 규칙

---

**라이선스**: 개인 학습 및 연구 목적
