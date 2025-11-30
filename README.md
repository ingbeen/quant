# QBT (Quant BackTest)

주식 데이터 다운로드 및 백테스팅을 위한 Python 프레임워크

## 주요 기능

- Yahoo Finance에서 주식 데이터 다운로드
- 버퍼존 기반 이동평균 전략 백테스트
- 파라미터 그리드 서치
- Buy & Hold 벤치마크 비교

## 설치

```bash
poetry install
```

## 데이터 다운로드

### 기본 사용 (전체 기간)

```bash
poetry run python scripts/download_data.py QQQ
```

### 시작 날짜 지정

```bash
poetry run python scripts/download_data.py SPY --start 2020-01-01
```

### 기간 지정

```bash
poetry run python scripts/download_data.py AAPL --start 2020-01-01 --end 2023-12-31
```

## 백테스트 실행

### 단일 전략 백테스트

지정한 파라미터로 버퍼존 전략과 Buy&Hold 벤치마크를 비교합니다.

```bash
# 버퍼존만 모드 (유지조건 없음)
poetry run python scripts/run_single_backtest.py \
    --buffer-zone 0.01 --hold-days 0 --recent-months 6

# 버퍼존 + 유지조건 1일
poetry run python scripts/run_single_backtest.py \
    --buffer-zone 0.01 --hold-days 1 --recent-months 6

# 200일 EMA (기본값) 대신 100일 EMA 사용
poetry run python scripts/run_single_backtest.py \
    --ma-window 100 --buffer-zone 0.02 --hold-days 2 --recent-months 6
```

**파라미터 설명:**
- `--ma-window`: 이동평균 기간 (기본값: 200, EMA 사용)
- `--buffer-zone`: 초기 버퍼존 비율 (필수, 예: 0.01 = 1%)
- `--hold-days`: 초기 유지조건 일수 (기본값: 1, 0이면 버퍼존만 모드)
- `--recent-months`: 최근 매수 기간 (개월, 기본값: 6, 동적 조정에 사용)

### 파라미터 그리드 서치

여러 파라미터 조합을 탐색하여 최적 전략을 찾습니다.

```bash
poetry run python scripts/run_grid_search.py
```

결과는 `data/raw/grid_results.csv`에 저장됩니다.

## 스크립트 사용 가이드

### 스크립트별 역할 및 출력물

| 스크립트 | 역할 | 출력물 |
|---------|------|--------|
| `download_data.py` | 데이터 수집 | `data/raw/{TICKER}_max.csv` |
| `run_single_backtest.py` | 단일 전략 검증 | 콘솔 출력 (성과 비교) |
| `run_grid_search.py` | 파라미터 최적화 | `data/raw/grid_results.csv` |

### 처리 흐름 및 의존성

```
[Yahoo Finance API]
       │
       ▼
┌──────────────┐
│download_data │ ──▶ data/raw/{TICKER}_max.csv
└──────────────┘
       │
       │ (CSV 파일 의존)
       ▼
┌────────────────────────────────────────────┐
│          백테스트 스크립트                   │
│                                            │
│  run_grid_search ──▶ grid_results.csv     │
│         │            (최적 파라미터 탐색)   │
│         ▼                                  │
│  run_single_backtest ──▶ 콘솔 (전략 비교)  │
│                (특정 파라미터 상세 분석)    │
└────────────────────────────────────────────┘
```

### 권장 사용 순서

1. **데이터 준비**: `download_data.py`로 CSV 생성
2. **파라미터 탐색**: `run_grid_search.py`로 최적 조합 탐색
3. **단일 검증**: `run_single_backtest.py`로 특정 파라미터 상세 분석

## 프로젝트 구조

```
quant/
├── scripts/                     # 실행 스크립트
│   ├── download_data.py         # 데이터 다운로드
│   ├── run_single_backtest.py   # 단일 백테스트
│   └── run_grid_search.py       # 그리드 서치
├── src/qbt/                     # 비즈니스 로직 패키지
│   ├── backtest/                # 백테스트 엔진
│   │   ├── config.py            # 설정 상수
│   │   ├── data.py              # 데이터 로딩/검증
│   │   ├── strategy.py          # 전략 실행 로직
│   │   ├── metrics.py           # 성과 지표 계산
│   │   ├── report.py            # 리포트 생성
│   │   └── exceptions.py        # 커스텀 예외
│   └── utils/                   # 유틸리티
│       ├── logger.py            # 로깅 설정
│       └── cli.py               # CLI 공통 함수
└── data/raw/                    # CSV 데이터 저장소
```

## 전략 설명

### 버퍼존 전략

이동평균선을 중심으로 상하 버퍼존을 설정하여 매매 신호를 생성하는 전략입니다.

**버퍼존 밴드:**
- 상단 밴드 = 이동평균 × (1 + 버퍼존 비율)
- 하단 밴드 = 이동평균 × (1 - 버퍼존 비율)

**매수 신호:**
- 조건: 종가가 상단 밴드를 상향 돌파 (전일 ≤ 상단 AND 당일 > 상단)
- 유지조건: hold_days > 0이면 돌파 후 N일간 상단 밴드 위 유지 필요
- 익일 시가에 매수 실행

**매도 신호:**
- 조건: 종가가 하단 밴드를 하향 돌파 (전일 ≥ 하단 AND 당일 < 하단)
- 익일 시가에 매도 실행

**동적 파라미터 조정:**
- 최근 N개월 내 매수 횟수에 따라 버퍼존과 유지조건을 자동 증가
- 매수 1회당: 버퍼존 +1%, 유지조건 +1일
- 목적: 과도한 거래 빈도 방지 및 신호 품질 향상

### 거래 규칙

- **롱 온리**: 매수만 가능, 공매도 불가
- **최대 1 포지션**: 한 번에 하나의 포지션만 보유
- **익일 시가 진입/청산**: 신호 발생 다음 날 시가에 거래 실행
- **거래 비용**: 슬리피지 0.3% (매수 +0.3%, 매도 -0.3%, 수수료 포함)

### 성과 지표

- **총 수익률**: (최종 자본 - 초기 자본) / 초기 자본
- **CAGR**: 연평균 복합 성장률
- **MDD**: 최대 낙폭 (Maximum Drawdown)
- **승률**: 이익 거래 / 전체 거래
