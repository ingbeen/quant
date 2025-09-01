# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소의 코드 작업 시 참고할 가이드를 제공합니다.

## 프로젝트 개요

이 프로젝트는 DuckDB를 데이터 캐싱에, CSV를 Git을 통한 데이터 공유에 사용하는 Python 퀀트 금융 주식 백테스팅 프로젝트입니다. 이 프레임워크는 다양한 트레이딩 전략, 포트폴리오 관리, 포괄적인 성과 분석을 지원합니다.

## 프로젝트 구조

```
src/backtest/          # 핵심 백테스팅 모듈
├── portfolio.py       # 포트폴리오 및 포지션 관리
├── strategy.py        # 트레이딩 전략 및 기술적 지표
├── data_handler.py    # DuckDB 데이터 로딩 및 처리
├── engine.py          # 백테스팅 실행 엔진
└── analyzer.py        # 성과 분석 및 리포팅

scripts/               # 유틸리티 스크립트
├── download_data.py   # 주식 데이터 다운로드 (Yahoo Finance)
└── create_duckdb_cache.py  # DuckDB 캐시 관리

data/raw/             # CSV 주식 데이터 (Git 추적)
cache/               # DuckDB 파일들 (Git 무시, 로컬 캐시만)
```

## 핵심 아키텍처

### 데이터 흐름
1. **CSV 저장**: `data/raw/` 디렉토리에 CSV 파일로 원시 주식 데이터 저장 (Git 추적)
2. **DuckDB 캐시**: `cache/` 디렉토리의 빠른 쿼리 레이어 (Git 무시) 
3. **전략 엔진**: 데이터로부터 매수/매도 신호 생성
4. **포트폴리오 관리자**: 거래 실행, 포지션 추적, P&L 계산
5. **성과 분석기**: 포괄적인 지표 및 시각화

### 주요 클래스
- `DataHandler`: DuckDB에서 데이터 로드, 다중 심볼 처리
- `Portfolio`: 현금, 포지션, 거래 내역을 수수료 추적과 함께 관리
- `BaseStrategy`: 트레이딩 전략의 추상 클래스 (SMA, RSI, 볼린저 밴드)
- `BacktestEngine`: 전략 실행과 신호 처리 조율
- `PerformanceAnalyzer`: 위험 지표 계산, 리포트 및 차트 생성

## 개발 명령어

### 데이터 관리
```bash
# 주식 데이터 다운로드
python scripts/download_data.py QQQ --period=max

# DuckDB 캐시 생성/업데이트
python scripts/create_duckdb_cache.py data/raw/QQQ_max.csv
python scripts/create_duckdb_cache.py --rebuild-all

# 사용 가능한 데이터 목록 조회
python scripts/create_duckdb_cache.py --list-symbols
```

### 환경 설정
```bash
# 의존성 설치
poetry install

# 개발 환경 시작
poetry shell

# 테스트 실행 (구현 시)
poetry run pytest

# 코드 포매팅
poetry run black src/ scripts/
poetry run ruff check src/ scripts/
```

## 사용 예제

### 기본 백테스팅
```python
from src.backtest.data_handler import DataHandler
from src.backtest.strategy import SMAStrategy
from src.backtest.engine import BacktestEngine, BacktestConfig
from src.backtest.analyzer import PerformanceAnalyzer

# 구성요소 초기화
data_handler = DataHandler()
strategy = SMAStrategy(short_window=20, long_window=50)
engine = BacktestEngine(data_handler)

# 백테스트 설정
config = BacktestConfig(
    initial_cash=Decimal('100000'),
    commission_rate=Decimal('0.001')
)

# 백테스트 실행
result = engine.run_backtest(strategy, 'QQQ', config)

# 결과 분석
analyzer = PerformanceAnalyzer(result)
analyzer.print_summary()
analyzer.plot_performance()
```

## DBeaver 통합

DuckDB 캐시 파일들은 SQL 분석을 위해 DBeaver에서 열 수 있습니다:
1. DBeaver에서 새 DuckDB 연결 생성
2. `cache/market_data.db`를 가리키도록 설정
3. 스키마 `symbol, date, open, high, low, close, adj_close, volume`를 가진 `stocks` 테이블 쿼리

## Git 워크플로우

- **CSV 파일들**: 팀 공유를 위해 Git에 커밋
- **DuckDB 캐시**: 로컬 전용, 필요시 CSV에서 재생성
- **코드 변경사항**: 표준 Git 워크플로우
- **데이터 업데이트**: CSV 업데이트, 팀 멤버들은 로컬에서 캐시 재구축