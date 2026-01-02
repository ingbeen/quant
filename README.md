# QBT (Quant BackTest)

주식 백테스팅 및 레버리지 ETF 시뮬레이션을 위한 Python CLI 도구입니다.

## 주요 기능

- 시계열 데이터 수집 및 검증 (Yahoo Finance 기반)
- 이동평균 기반 거래 전략 백테스트
- 레버리지 ETF 시뮬레이션 및 비용 모델 최적화
- 대화형 시각화 대시보드 (Streamlit + Plotly)

## 기술 스택

- **언어**: Python 3.10+
- **의존성 관리**: Poetry
- **데이터 처리**: pandas, yfinance
- **시각화**: Plotly, Streamlit, matplotlib
- **코드 품질**: Black, Ruff
- **테스트**: pytest, pytest-cov, freezegun

## 빠른 시작

```bash
# 의존성 설치
poetry install

# 테스트 실행
./run_tests.sh

# 코드 품질 체크 (ruff + mypy)
poetry run python check_code.py
```

---

## 워크플로우 1: 백테스트 전략 분석

이동평균 기반 버퍼존 전략의 최적 파라미터를 탐색하고 성과를 평가합니다.

```bash
# 1. 데이터 다운로드
poetry run python scripts/data/download_data.py QQQ

# 2. 파라미터 최적화 (그리드 서치)
poetry run python scripts/backtest/run_grid_search.py
# 출력: storage/results/grid_results.csv

# 3. 단일 전략 검증
poetry run python scripts/backtest/run_single_backtest.py
# 출력: 콘솔 (버퍼존 vs Buy&Hold 비교)
```

**파라미터 변경**: [src/qbt/backtest/constants.py](src/qbt/backtest/constants.py)

---

## 워크플로우 2: TQQQ 레버리지 ETF 시뮬레이션

QQQ로부터 TQQQ를 시뮬레이션하고 실제 데이터와 비교하여 비용 모델을 검증합니다.

```bash
# 1. 필수 데이터 다운로드
poetry run python scripts/data/download_data.py QQQ
poetry run python scripts/data/download_data.py TQQQ

# 2. 비용 모델 파라미터 최적화
poetry run python scripts/tqqq/validate_tqqq_simulation.py
# 출력: storage/results/tqqq_validation.csv

# 3. 일별 비교 데이터 생성
poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py
# 출력: storage/results/tqqq_daily_comparison.csv

# 4. 대시보드 시각화
poetry run streamlit run scripts/tqqq/streamlit_app.py
# 브라우저에서 http://localhost:8501 열림

# 5. 합성 TQQQ 데이터 생성
poetry run python scripts/tqqq/generate_synthetic_tqqq.py
# 출력: storage/stock/TQQQ_synthetic_max.csv
```

**파라미터 변경**: [src/qbt/tqqq/constants.py](src/qbt/tqqq/constants.py)

---

## 주요 명령어

### 테스트

```bash
# 전체 테스트
./run_tests.sh

# 커버리지 확인
./run_tests.sh cov

# 특정 모듈 테스트
./run_tests.sh strategy

# HTML 커버리지 리포트
./run_tests.sh html
# 결과: htmlcov/index.html
```

### 코드 품질

```bash
# 통합 품질 체크 (ruff + mypy)
poetry run python check_code.py

# ruff 자동 수정
poetry run ruff check --fix .

# mypy만 실행
poetry run mypy src/ scripts/ tests/

# 포맷 확인
poetry run black --check .

# 포맷 적용
poetry run black .
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
├── scripts/           # CLI 스크립트 (사용자 실행)
│   ├── data/          # download_data.py
│   ├── backtest/      # run_grid_search.py, run_single_backtest.py
│   └── tqqq/          # validate_tqqq_simulation.py, generate_*.py, streamlit_app.py
├── src/qbt/           # 비즈니스 로직
│   ├── backtest/      # 백테스트 도메인 + constants.py
│   ├── tqqq/          # TQQQ 시뮬레이션 + constants.py
│   └── utils/         # 공통 유틸리티
├── storage/           # 데이터 저장소
│   ├── stock/         # 주식 데이터 CSV
│   ├── etc/           # 금리 데이터
│   └── results/       # 분석 결과 + meta.json
└── tests/             # 테스트 코드
```

---

## 주요 결과 파일

### 백테스트

- `storage/results/grid_results.csv`: 파라미터 그리드 서치 결과

### TQQQ 시뮬레이션

- `storage/results/tqqq_validation.csv`: 비용 모델 최적화 결과 (RMSE 기준 정렬)
- `storage/results/tqqq_daily_comparison.csv`: 일별 비교 데이터 (대시보드 입력)
- `storage/stock/TQQQ_synthetic_max.csv`: 합성 TQQQ 데이터
- `storage/results/meta.json`: 실행 이력 메타데이터

---

## 문제 해결

### 데이터 다운로드 실패

```bash
# 다른 기간으로 재시도
poetry run python scripts/data/download_data.py QQQ --start 2020-01-01
```

### 테스트 실패

```bash
# 코드 품질 체크 후 재실행
poetry run python check_code.py
./run_tests.sh
```

### 대시보드 실행 오류

```bash
# 의존 파일 먼저 생성
poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py
poetry run streamlit run scripts/tqqq/streamlit_app.py
```

---

## 개발 가이드

### 파라미터 변경

- **백테스트**: [src/qbt/backtest/constants.py](src/qbt/backtest/constants.py)
- **TQQQ 시뮬레이션**: [src/qbt/tqqq/constants.py](src/qbt/tqqq/constants.py)
- **공통 설정**: [src/qbt/common_constants.py](src/qbt/common_constants.py)

### 코딩 표준

- **타입 힌트**: 모든 함수 필수 (`str | None` 문법)
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
- [테스트 가이드](tests/CLAUDE.md): 테스트 작성 규칙
- [백테스트 도메인](src/qbt/backtest/CLAUDE.md): 백테스트 로직
- [TQQQ 시뮬레이션](src/qbt/tqqq/CLAUDE.md): 레버리지 ETF 시뮬레이션

---

**라이선스**: 개인 학습 및 연구 목적
