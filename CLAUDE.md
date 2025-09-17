# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소의 코드 작업 시 참고할 가이드를 제공합니다.

## ⚠️ Claude 개발 가이드라인 (필수)

**이 프로젝트에서 Claude는 모든 Python 코드를 Black 포맷터 규칙에 맞춰 작성해야 합니다.**

- **라인 길이**: 88자 제한 (`line-length = 88`)
- **타겟 버전**: Python 3.10 (`target-version = ['py310']`)
- **포맷팅 규칙**: Black 기본 규칙 준수 (import 정렬, 문자열 쿼터 통일, 공백 규칙 등)
- **사용하지 않는 함수 구현 금지**: 실제로 호출되지 않는 함수나 메서드는 구현하지 않습니다. YAGNI(You Aren't Gonna Need It) 원칙을 따라 필요한 기능만 구현합니다.

## 프로젝트 개요

이 프로젝트는 **QBT (Quant BackTest)** - DuckDB를 데이터 캐싱에, CSV를 Git을 통한 데이터 공유에 사용하는 Python 퀀트 금융 주식 백테스팅 프레임워크입니다.

### 주요 기능
1. **주식 데이터 수집 및 관리**: Yahoo Finance API를 통한 데이터 다운로드
2. **고성능 데이터 캐싱**: DuckDB를 활용한 빠른 데이터 접근
3. **백테스팅 엔진**: 다양한 투자 전략의 성과 분석
4. **병렬 처리**: 여러 전략을 동시에 실행하여 성능 비교

## 프로젝트 구조 (리팩토링됨)

```
quant/
├── src/qbt/                    # QBT 메인 패키지 (표준 src 레이아웃)
│   ├── __init__.py            # 패키지 진입점
│   ├── core/                  # 백테스팅 핵심 엔진
│   │   ├── data_loader.py     # DuckDB 데이터 로더
│   │   ├── engine.py          # 백테스팅 실행 엔진
│   │   ├── executor.py        # 매매 실행 및 포지션 관리
│   │   └── parallel_runner.py # 병렬 실행 관리자
│   ├── strategies/            # 투자 전략 모듈
│   │   ├── base.py           # 전략 기본 추상 클래스
│   │   ├── buyandhold.py     # Buy & Hold 전략 (벤치마크)
│   │   └── seasonal.py       # 계절성 전략 (Sell in May)
│   ├── analysis/             # 성과 분석 모듈
│   │   ├── metrics.py        # 성과 지표 계산
│   │   └── comparator.py     # 전략 비교 분석
│   └── cli/                  # CLI 인터페이스
│       └── run_backtest.py   # 백테스팅 실행 CLI
├── scripts/                   # 실행 스크립트 (얇은 래퍼)
│   ├── download_data.py      # 주식 데이터 다운로드
│   ├── create_duckdb_cache.py # DuckDB 캐시 생성
│   └── run_backtest.py       # 백테스팅 실행 (래퍼)
├── data/raw/                 # CSV 주식 데이터 (Git 추적)
├── cache/                    # DuckDB 파일들 (Git 무시, 로컬 캐시만)
├── notebooks/                # Jupyter 노트북 (분석 및 실험용)
└── .vscode/settings.json     # VSCode Black 자동 포맷팅 설정
```

## 백테스팅 실행 방법 (3가지)

### 1. CLI 엔트리포인트 (권장)
```bash
poetry run run-backtest
```

### 2. 모듈 방식 실행
```bash
poetry run python -m qbt.cli.run_backtest
```

### 3. 기존 스크립트 방식 (호환성)
```bash
poetry run python scripts/run_backtest.py
```

## QBT 패키지 사용법

### 프로그래밍 방식으로 사용하기
```python
from qbt.core.data_loader import DataLoader
from qbt.core.parallel_runner import ParallelRunner
from qbt.strategies.buyandhold import BuyAndHoldStrategy
from qbt.strategies.seasonal import SeasonalStrategy

# 데이터 로더 초기화
data_loader = DataLoader("cache/market_data.db")

# 데이터 로드
data = data_loader.load_data(
    ticker="QQQ", start_date="2020-01-01", end_date="2024-12-31"
)

# 전략 생성
strategies = [
    BuyAndHoldStrategy(),  # 벤치마크
    SeasonalStrategy(),    # 계절성 전략
]

# 병렬 백테스팅 실행
parallel_runner = ParallelRunner()
results = parallel_runner.run_strategies(strategies=strategies, data=data, ticker="QQQ")
```

## 데이터 관리

### 주식 데이터 다운로드
```bash
# 특정 심볼의 최대 기간 데이터 다운로드
poetry run python scripts/download_data.py QQQ --period=max

# 여러 심볼 다운로드
poetry run python scripts/download_data.py AAPL MSFT GOOGL --period=1y

# 사용 가능한 옵션 확인
poetry run python scripts/download_data.py --help
```

### DuckDB 캐시 관리
```bash
# 특정 CSV 파일을 DuckDB로 변환
poetry run python scripts/create_duckdb_cache.py data/raw/QQQ_max.csv

# 모든 CSV 파일을 DuckDB로 변환
poetry run python scripts/create_duckdb_cache.py --rebuild-all

# 도움말 확인
poetry run python scripts/create_duckdb_cache.py --help
```

## 개발 환경 설정

### 필수 의존성
- **Python**: ^3.10
- **pandas**: ^2.0.0 (데이터 조작 및 처리)
- **yfinance**: ^0.2.0 (Yahoo Finance 데이터 수집)
- **duckdb**: ^0.9.0 (고성능 로컬 데이터베이스)
- **numpy**: ^1.24.0 (수치 연산)
- **jupyter**: ^1.0.0 (노트북 환경)

### 개발 도구
- **black**: ^23.0.0 (코드 포매터, **필수 사용**)
- **ipykernel**: ^6.25.0 (Jupyter 커널)

### 환경 설정 명령어
```bash
# 의존성 설치
poetry install

# 개발 환경 활성화
poetry shell

# 패키지 관리
poetry add pandas numpy  # 새 패키지 추가
poetry remove requests   # 패키지 제거
```

## DBeaver SQL 분석 통합

DuckDB 캐시 파일은 DBeaver에서 SQL 분석이 가능합니다:

1. **연결 생성**: DBeaver에서 새 DuckDB 연결 생성
2. **데이터베이스 파일**: `cache/market_data.db` 파일 지정
3. **테이블 구조**:
   - 테이블명: `stocks`
   - 컬럼: `ticker, date, open, high, low, close, adj_close, volume`

## Git 워크플로우

- **CSV 파일**: `data/raw/` 디렉토리의 CSV 파일은 Git에 커밋하여 팀과 공유
- **DuckDB 캐시**: `cache/` 디렉토리는 `.gitignore`에 포함되어 로컬 전용
- **QBT 패키지**: `src/qbt/` 디렉토리의 모든 Python 파일은 표준 Git 워크플로우 적용
- **스크립트**: `scripts/` 디렉토리는 얇은 래퍼로 유지
- **데이터 업데이트**: CSV 파일 업데이트 후 팀원들은 로컬에서 캐시 재구축 필요

## 백테스팅 결과 예시

성공적인 백테스팅 실행 시 다음과 같은 결과를 확인할 수 있습니다:

```
============================================================
 QQQ 백테스팅 시스템
============================================================
[1] 데이터 로더 초기화...
[2] QQQ 데이터 로드 중...
    로드된 데이터: 1258개 레코드
    기간: 2020-01-02 ~ 2024-12-31
    캐시 상태: 1개 데이터셋, 0.1MB
[3] 투자 전략 생성...
    - BuyAndHold 전략
    - Seasonal 전략
[4] 병렬 실행기 초기화...
[5] 병렬 백테스팅 실행...

============================================================
 백테스팅 결과 요약
============================================================
[벤치마크] BuyAndHold
  수익률: 141.28%
  거래횟수: 2회
  승률: 100.0%

[전략] Seasonal
  수익률: 43.73%
  거래횟수: 12회
  승률: 66.7%
  초과수익률: -97.55%
============================================================
```