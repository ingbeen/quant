# QBT (Quant BackTest)

주식 데이터 다운로드 및 백테스팅을 위한 Python CLI 도구

## 프로젝트 초기 설정

프로젝트를 클론한 후 다음 명령어로 환경을 구성하세요:

```bash
# 의존성 설치
poetry install
```

## 스크립트 실행 가이드

### 1. download_data.py - 주식 데이터 다운로드

Yahoo Finance에서 주식 데이터를 다운로드합니다.

**실행 명령어:**
```bash
# 전체 기간 다운로드
poetry run python scripts/data/download_data.py QQQ

# 시작 날짜 지정
poetry run python scripts/data/download_data.py SPY --start 2020-01-01

# 기간 지정
poetry run python scripts/data/download_data.py AAPL --start 2020-01-01 --end 2023-12-31
```

**파라미터:**
- `ticker` (필수): 주식 티커 심볼 (예: QQQ, SPY)
- `--start`: 시작 날짜 (YYYY-MM-DD)
- `--end`: 종료 날짜 (YYYY-MM-DD)

**출력:**
- `data/raw/{TICKER}_max.csv` (전체 기간)
- `data/raw/{TICKER}_{START}_{END}.csv` (기간 지정)
- `data/raw/{TICKER}_{START}_latest.csv` (시작일만 지정)

**의존성:** 없음 (독립 실행)

---

### 2. run_single_backtest.py - 단일 전략 백테스트

버퍼존 전략과 Buy&Hold 벤치마크를 비교합니다.

**실행 명령어:**
```bash
# 버퍼존만 모드 (유지조건 없음)
poetry run python scripts/backtest/run_single_backtest.py \
    --buffer-zone 0.01 --hold-days 0 --recent-months 6

# 버퍼존 + 유지조건 1일
poetry run python scripts/backtest/run_single_backtest.py \
    --buffer-zone 0.01 --hold-days 1 --recent-months 6

# 100일 이동평균 사용
poetry run python scripts/backtest/run_single_backtest.py \
    --ma-window 100 --buffer-zone 0.02 --hold-days 2 --recent-months 6
```

**파라미터:**
- `--ma-window`: 이동평균 기간 (기본값: 200)
- `--buffer-zone` (필수): 초기 버퍼존 비율 (예: 0.01 = 1%)
- `--hold-days`: 초기 유지조건 일수 (기본값: 1, 0이면 버퍼존만 모드)
- `--recent-months`: 최근 매수 기간 (개월, 기본값: 6)

**출력:** 콘솔 출력 (전략 비교 결과)

**의존 CSV:** `data/raw/QQQ_max.csv`

---

### 3. run_grid_search.py - 파라미터 그리드 서치

버퍼존 전략의 최적 파라미터를 탐색합니다.

**실행 명령어:**
```bash
poetry run python scripts/backtest/run_grid_search.py
```

**파라미터:** 없음 (코드 내부 상수 사용)

**출력:**
- 콘솔: 상위 10개 전략 (수익률/CAGR 기준)
- `data/raw/grid_results.csv`: 전체 결과

**의존 CSV:** `data/raw/QQQ_max.csv`

---

### 4. validate_tqqq_simulation.py - TQQQ 시뮬레이션 검증

레버리지 ETF 비용 모델의 최적 파라미터를 탐색합니다.

**실행 명령어:**
```bash
# 기본 범위로 그리드 서치
poetry run python scripts/tqqq/validate_tqqq_simulation.py

# 탐색 범위 좁히기
poetry run python scripts/tqqq/validate_tqqq_simulation.py \
    --spread-min 0.6 --spread-max 0.7 \
    --expense-min 0.008 --expense-max 0.010
```

**파라미터:**
- `--qqq-path`: QQQ CSV 파일 경로 (기본값: data/raw/QQQ_max.csv)
- `--tqqq-path`: TQQQ CSV 파일 경로 (기본값: data/raw/TQQQ_max.csv)
- `--ffr-path`: 연방기금금리 CSV 파일 경로 (기본값: data/raw/federal_funds_rate_monthly.csv)
- `--leverage`: 레버리지 배수 (기본값: 3.0)
- `--spread-min`, `--spread-max`, `--spread-step`: funding spread 탐색 범위
- `--expense-min`, `--expense-max`, `--expense-step`: expense ratio 탐색 범위

**출력:**
- 콘솔: 상위 전략
- `results/tqqq_validation.csv`: 검증 결과

**의존 CSV:**
- `data/raw/QQQ_max.csv`
- `data/raw/TQQQ_max.csv`
- `data/raw/federal_funds_rate_monthly.csv`

---

### 5. generate_synthetic_tqqq.py - 합성 TQQQ 데이터 생성

QQQ 데이터로부터 TQQQ를 시뮬레이션합니다.

**실행 명령어:**
```bash
# 기본 파라미터로 생성
poetry run python scripts/tqqq/generate_synthetic_tqqq.py

# 시작 날짜 지정
poetry run python scripts/tqqq/generate_synthetic_tqqq.py --start-date 2010-01-01

# 모든 파라미터 지정
poetry run python scripts/tqqq/generate_synthetic_tqqq.py \
    --start-date 1999-03-10 \
    --multiplier 3.0 \
    --funding-spread 0.5 \
    --expense-ratio 0.009 \
    --initial-price 100.0 \
    --output data/raw/TQQQ_synthetic_1999-03-10_max.csv
```

**파라미터:**
- `--qqq-path`: QQQ CSV 파일 경로 (기본값: data/raw/QQQ_max.csv)
- `--start-date`: 시작 날짜 (기본값: 1999-03-10)
- `--multiplier`: 레버리지 배수 (기본값: 3.0)
- `--expense-ratio`: 연간 비용 비율 (기본값: 0.008)
- `--funding-spread`: 펀딩 스프레드 (기본값: 0.5)
- `--ffr-path`: 연방기금금리 CSV 파일 경로 (기본값: data/raw/federal_funds_rate_monthly.csv)
- `--initial-price`: 초기 가격 (기본값: 200.0)
- `--output`: 출력 CSV 파일 경로 (기본값: data/raw/TQQQ_synthetic_max.csv)

**출력:** `data/raw/TQQQ_synthetic_max.csv` (또는 지정한 경로)

**의존 CSV:**
- `data/raw/QQQ_max.csv`
- `data/raw/federal_funds_rate_monthly.csv`

---

### 6. generate_tqqq_daily_comparison.py - TQQQ 일별 비교 CSV 생성

시뮬레이션과 실제 TQQQ를 일별로 비교합니다.

**실행 명령어:**
```bash
# 기본 파라미터로 일별 비교 생성
poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py

# 특정 파라미터로 생성
poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py \
    --funding-spread 0.65 \
    --expense-ratio 0.009

# 출력 파일 경로 지정
poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py \
    --output results/tqqq_daily_custom.csv
```

**파라미터:**
- `--qqq-path`: QQQ CSV 파일 경로 (기본값: data/raw/QQQ_max.csv)
- `--tqqq-path`: TQQQ CSV 파일 경로 (기본값: data/raw/TQQQ_max.csv)
- `--ffr-path`: 연방기금금리 CSV 파일 경로 (기본값: data/raw/federal_funds_rate_monthly.csv)
- `--leverage`: 레버리지 배수 (기본값: 3.0)
- `--funding-spread`: 펀딩 스프레드 (기본값: 0.5)
- `--expense-ratio`: 연간 비용 비율 (기본값: 0.008)
- `--output`: 출력 CSV 파일 경로 (기본값: results/tqqq_daily_comparison.csv)

**출력:** `results/tqqq_daily_comparison.csv` (또는 지정한 경로)

**의존 CSV:**
- `data/raw/QQQ_max.csv`
- `data/raw/TQQQ_max.csv`
- `data/raw/federal_funds_rate_monthly.csv`

---

### 7. streamlit_app.py - TQQQ 검증 대시보드

일별 비교 데이터를 시각화합니다 (Streamlit + Plotly).

**실행 명령어:**
```bash
poetry run streamlit run scripts/tqqq/streamlit_app.py
```

**파라미터:** 없음

**출력:** 웹 대시보드 (http://localhost:8501)

**의존 CSV:** `results/tqqq_daily_comparison.csv`

---

## 스크립트 실행 순서 및 의존 관계

```
[1단계] 데이터 다운로드
┌────────────────────────┐
│ download_data.py       │
│ (QQQ, TQQQ, FFR 등)    │
└──────────┬─────────────┘
           │
           │ 생성
           ▼
   ┌─────────────────────────────┐
   │ data/raw/QQQ_max.csv        │
   │ data/raw/TQQQ_max.csv       │
   │ data/raw/federal_funds_     │
   │   rate_monthly.csv          │
   └──────────┬──────────────────┘
              │
              │ 사용
              ▼
┌──────────────────────────────────────────────┐
│         [2단계] 분석 실행 (병렬 가능)           │
├──────────────────────────────────────────────┤
│                                              │
│  [백테스트 영역]                               │
│  ┌──────────────────────┐                   │
│  │ run_single_backtest  │──▶ 콘솔 출력       │
│  └──────────────────────┘                   │
│  ┌──────────────────────┐                   │
│  │ run_grid_search      │──▶ grid_results   │
│  └──────────────────────┘     .csv          │
│                                              │
│  [TQQQ 시뮬레이션 영역]                        │
│  ┌──────────────────────┐                   │
│  │ validate_tqqq_       │──▶ tqqq_          │
│  │   simulation         │    validation.csv │
│  └──────────┬───────────┘                   │
│             │ 최적 파라미터                   │
│             ▼                                │
│  ┌──────────────────────┐                   │
│  │ generate_synthetic_  │──▶ TQQQ_          │
│  │   tqqq               │    synthetic.csv  │
│  └──────────────────────┘                   │
│  ┌──────────────────────┐                   │
│  │ generate_tqqq_daily_ │──▶ tqqq_daily_    │
│  │   comparison         │    comparison.csv │
│  └──────────┬───────────┘                   │
└─────────────┼────────────────────────────────┘
              │
              │ 사용
              ▼
      ┌──────────────┐
      │ streamlit_   │──▶ 웹 대시보드
      │   app        │
      └──────────────┘
```

### 권장 실행 순서

#### 백테스트 워크플로우:
1. `download_data.py` - QQQ 데이터 다운로드
2. `run_grid_search.py` - 최적 파라미터 탐색
3. `run_single_backtest.py` - 특정 파라미터 검증

#### TQQQ 시뮬레이션 워크플로우:
1. `download_data.py` - QQQ, TQQQ, FFR 데이터 다운로드
2. `validate_tqqq_simulation.py` - 최적 비용 모델 파라미터 탐색
3. `generate_synthetic_tqqq.py` - 최적 파라미터로 합성 데이터 생성
4. `generate_tqqq_daily_comparison.py` - 일별 비교 데이터 생성
5. `streamlit_app.py` - 검증 결과 시각화
