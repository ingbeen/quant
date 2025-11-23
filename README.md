# QBT (Quant BackTest)

주식 데이터 다운로드 및 백테스팅을 위한 Python 프레임워크

## 주요 기능

- Yahoo Finance에서 주식 데이터 다운로드
- 이동평균선 교차 전략 백테스트 (SMA/EMA)
- 파라미터 그리드 서치
- 워킹 포워드 테스트
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

지정한 파라미터로 SMA/EMA 전략과 Buy&Hold 벤치마크를 비교합니다.

```bash
# SMA + EMA + Buy&Hold 비교
poetry run python scripts/run_single_backtest.py \
    --short 20 --long 50 --stop-loss 0.10 --lookback 20

# 그리드 서치 최적 파라미터 적용
poetry run python scripts/run_single_backtest.py \
    --short 20 --long 200 --stop-loss 0.05 --lookback 20

# EMA 전략만 실행
poetry run python scripts/run_single_backtest.py \
    --short 20 --long 200 --stop-loss 0.05 --lookback 20 --ma-type ema
```

**파라미터 설명:**
- `--short`: 단기 이동평균 기간 (필수)
- `--long`: 장기 이동평균 기간 (필수)
- `--stop-loss`: 손절 비율 (필수, 예: 0.10 = 10%)
- `--lookback`: 최근 저점 탐색 기간 (필수)
- `--ma-type`: 이동평균 유형 (`sma` 또는 `ema`, 미지정 시 둘 다 실행)

### 파라미터 그리드 서치

여러 파라미터 조합을 탐색하여 최적 전략을 찾습니다.

```bash
poetry run python scripts/run_grid_search.py
```

결과는 `data/raw/grid_results.csv`에 저장됩니다.

### 워킹 포워드 테스트

과거 기간에서 최적 파라미터를 선택하고, 다음 기간에 적용하는 워킹 포워드 테스트를 실행합니다.

```bash
# 기본 설정 (5년 학습, 1년 테스트, CAGR 기준)
poetry run python scripts/run_walkforward.py \
    --train 5 --test 1 --metric cagr

# 3년 학습, 1년 테스트, MDD 기준 최적화
poetry run python scripts/run_walkforward.py \
    --train 3 --test 1 --metric mdd

# 수익률 기준 최적화
poetry run python scripts/run_walkforward.py \
    --train 5 --test 1 --metric total_return_pct
```

**파라미터 설명:**
- `--train`: 학습 기간 (년, 필수)
- `--test`: 테스트 기간 (년, 필수)
- `--metric`: 최적 파라미터 선택 기준 (필수, `cagr`, `total_return_pct`, `mdd` 중 선택)

결과는 `data/raw/walkforward_results.csv`에 저장됩니다.

## 프로젝트 구조

```
quant/
├── scripts/                     # 실행 스크립트
│   ├── download_data.py         # 데이터 다운로드
│   ├── run_single_backtest.py   # 단일 백테스트
│   ├── run_grid_search.py       # 그리드 서치
│   └── run_walkforward.py       # 워킹 포워드 테스트
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

### 이동평균선 교차 전략

- **골든 크로스**: 단기 이동평균이 장기 이동평균을 상향 돌파 시 매수
- **데드 크로스**: 단기 이동평균이 장기 이동평균을 하향 돌파 시 매도
- **손절**: 하드 스톱(진입가 기준) 또는 트레일링 스톱(최근 저점 기준) 중 높은 가격에서 손절

### 거래 비용

- **슬리피지**: 매수/매도 시 가격에 적용 (기본 0.3%, 수수료 포함)

### 성과 지표

- **총 수익률**: (최종 자본 - 초기 자본) / 초기 자본
- **CAGR**: 연평균 복합 성장률
- **MDD**: 최대 낙폭 (Maximum Drawdown)
- **승률**: 이익 거래 / 전체 거래
