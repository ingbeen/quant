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
poetry run python scripts/backtest/run_single_backtest.py
```

**파라미터:** 없음 (모든 파라미터는 [constants.py](src/qbt/backtest/constants.py)에서 상수로 정의됨)

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
poetry run python scripts/tqqq/validate_tqqq_simulation.py
```

**파라미터:** 없음 (모든 파라미터는 [constants.py](src/qbt/tqqq/constants.py)에서 상수로 정의됨)

**출력:**
- 콘솔: 상위 전략
- `results/tqqq_validation.csv`: 검증 결과

**의존 CSV:**
- `data/raw/QQQ_max.csv`
- `data/raw/TQQQ_max.csv`
- `data/raw/federal_funds_rate_monthly.csv`

---

### 5. generate_tqqq_daily_comparison.py - TQQQ 일별 비교 CSV 생성

시뮬레이션과 실제 TQQQ를 일별로 비교합니다.

**실행 명령어:**
```bash
poetry run python scripts/tqqq/generate_tqqq_daily_comparison.py
```

**파라미터:** 없음 (모든 파라미터는 [constants.py](src/qbt/tqqq/constants.py)에서 상수로 정의됨)

**출력:** `results/tqqq_daily_comparison.csv`

**의존 CSV:**
- `data/raw/QQQ_max.csv`
- `data/raw/TQQQ_max.csv`
- `data/raw/federal_funds_rate_monthly.csv`

---

### 6. generate_synthetic_tqqq.py - 합성 TQQQ 데이터 생성

QQQ 데이터로부터 TQQQ를 시뮬레이션합니다.
QQQ의 가장 빠른 시작일부터 자동으로 데이터를 생성합니다.

**실행 명령어:**
```bash
poetry run python scripts/tqqq/generate_synthetic_tqqq.py
```

**파라미터:** 없음 (모든 파라미터는 [constants.py](src/qbt/tqqq/constants.py)에서 상수로 정의됨)

**출력:** `data/raw/TQQQ_synthetic_max.csv`

**의존 CSV:**
- `data/raw/QQQ_max.csv`
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
│  └──────────────────────┘                   │
│  ┌──────────────────────┐                   │
│  │ generate_tqqq_daily_ │──▶ tqqq_daily_    │
│  │   comparison         │    comparison.csv │
│  └──────────┬───────────┘                   │
│             │                                │
│             ▼                                │
│  ┌──────────────────────┐                   │
│  │ generate_synthetic_  │──▶ TQQQ_          │
│  │   tqqq               │    synthetic.csv  │
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
3. `generate_tqqq_daily_comparison.py` - 일별 비교 데이터 생성
4. `generate_synthetic_tqqq.py` - 합성 데이터 생성 (QQQ 전체 기간)
5. `streamlit_app.py` - 검증 결과 시각화
