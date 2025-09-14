# CLAUDE.md

이 파일은 Claude Code(claude.ai/code)가 이 저장소의 코드 작업 시 참고할 가이드를 제공합니다.

## 프로젝트 개요

이 프로젝트는 DuckDB를 데이터 캐싱에, CSV를 Git을 통한 데이터 공유에 사용하는 Python 퀀트 금융 주식 데이터 처리 프로젝트입니다. 현재는 주식 데이터 다운로드와 DuckDB 캐시 관리 기능이 구현되어 있으며, 향후 백테스팅 프레임워크로 확장될 예정입니다.

## 프로젝트 구조

```
scripts/                    # 핵심 스크립트
├── download_data.py        # 주식 데이터 다운로드 (Yahoo Finance)
└── create_duckdb_cache.py  # DuckDB 캐시 관리

data/raw/                   # CSV 주식 데이터 (Git 추적)
cache/                      # DuckDB 파일들 (Git 무시, 로컬 캐시만)
notebooks/                  # Jupyter 노트북 (분석 및 실험용)
```

## 현재 구현된 기능

### 1. 주식 데이터 다운로드
- Yahoo Finance API를 통한 주식 데이터 수집
- CSV 형태로 `data/raw/` 디렉토리에 저장
- 다양한 기간 설정 지원 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

### 2. DuckDB 캐시 시스템
- CSV 데이터를 DuckDB 데이터베이스로 변환
- 빠른 쿼리 성능을 위한 로컬 캐시
- 다중 심볼 지원 및 효율적인 데이터 관리

## 데이터 플로우

1. **데이터 수집**: `download_data.py`로 Yahoo Finance에서 주식 데이터 다운로드
2. **CSV 저장**: `data/raw/` 디렉토리에 CSV 형태로 저장 (Git 추적됨)
3. **DuckDB 캐시**: `create_duckdb_cache.py`로 DuckDB 데이터베이스 생성
4. **빠른 접근**: 캐시된 DuckDB에서 고성능 쿼리 수행

## 명령어 사용법

### 주식 데이터 다운로드
```bash
# 특정 심볼의 최대 기간 데이터 다운로드
python scripts/download_data.py QQQ --period=max

# 여러 심볼 다운로드
python scripts/download_data.py AAPL MSFT GOOGL --period=1y

# 사용 가능한 옵션 확인
python scripts/download_data.py --help
```

### DuckDB 캐시 관리
```bash
# 특정 CSV 파일을 DuckDB로 변환
python scripts/create_duckdb_cache.py data/raw/QQQ_max.csv

# 모든 CSV 파일을 DuckDB로 변환
python scripts/create_duckdb_cache.py --rebuild-all

# 도움말 확인
python scripts/create_duckdb_cache.py --help
```

### 환경 설정
```bash
# 의존성 설치
poetry install

# 개발 환경 활성화
poetry shell

# 패키지 관리
poetry add pandas numpy  # 새 패키지 추가
poetry remove requests  # 패키지 제거
```

## 개발 환경

### 필수 의존성
- **Python**: ^3.10
- **pandas**: 데이터 조작 및 처리
- **yfinance**: Yahoo Finance 데이터 수집
- **duckdb**: 고성능 로컬 데이터베이스
- **numpy**: 수치 연산
- **jupyter**: 노트북 환경

### 개발 도구
- **black**: 코드 포매터
- **ipykernel**: Jupyter 커널

## DBeaver 통합

DuckDB 캐시 파일은 DBeaver에서 SQL 분석이 가능합니다:

1. **연결 생성**: DBeaver에서 새 DuckDB 연결 생성
2. **데이터베이스 파일**: `cache/market_data.db` 파일 지정
3. **테이블 구조**:
   - 테이블명: `stocks`
   - 컬럼: `ticker, date, open, high, low, close, adj_close, volume`

## Git 워크플로우

- **CSV 파일**: `data/raw/` 디렉토리의 CSV 파일은 Git에 커밋하여 팀과 공유
- **DuckDB 캐시**: `cache/` 디렉토리는 `.gitignore`에 포함되어 로컬 전용
- **코드 변경**: scripts/ 디렉토리의 Python 파일은 표준 Git 워크플로우 적용
- **데이터 업데이트**: CSV 파일 업데이트 후 팀원들은 로컬에서 캐시 재구축 필요