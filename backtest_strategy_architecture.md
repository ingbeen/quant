# 전략 분리 아키텍처 설계

> 이 문서는 백테스트 전략을 파일 단위로 분리하는 구조를 정의한다.
> 현재 구현된 2개 전략(버퍼존, Buy & Hold) 기준으로 진행하며,
> 향후 새 전략 추가가 용이한 구조를 목표로 한다.

---

## 1. 설계 배경

### 현재 구조의 문제

```
현재:
  src/qbt/backtest/strategy.py (866줄)
    ← 버퍼존 + Buy&Hold + 그리드서치 + 헬퍼 함수 + 예외 클래스 전부 한 파일

문제:
  1. 새 전략을 추가하려면 strategy.py를 직접 수정해야 함
  2. 전략 간 공통 코드(매수/매도 체결, 밴드 계산 등)를 재사용할 수 없음
  3. 전략마다 입력 데이터/시그널/매매 방법이 다를 수 있는데 구조가 이를 지원하지 않음
```

### 설계 목표

- 전략 1개 = 파일 1개 (독립적 실행)
- 기존 버퍼존과 Buy & Hold를 분리
- 공통 헬퍼를 추출하여 향후 전략이 재사용할 수 있도록 구조화
- 전략별 결과를 독립 폴더에 저장
- **리팩토링 전후 백테스트 결과 동일성 보장** (가장 중요)

---

## 2. 핵심 원칙: 입력은 자유, 출력만 통일

각 전략이 공유하는 것은 **출력 형식**뿐이다.
입력 데이터, 시그널 생성, 매매 로직은 전략마다 완전히 다를 수 있다.

```
전략 A (Buy & Hold):
  입력: TQQQ 데이터만
  매수: 첫날 시가
  매도: 없음 (강제청산 없음)

전략 B (버퍼존):
  입력: QQQ(시그널) + TQQQ(매매)
  매수: QQQ 종가 > EMA 상단밴드 돌파 → 다음날 TQQQ 시가
  매도: QQQ 종가 < EMA 하단밴드 돌파 → 다음날 TQQQ 시가
```

---

## 3. 현재 strategy.py 구성요소 분류

### A. 데이터 클래스 (4개)

| 클래스 | 역할 | 분리 대상 |
|--------|------|-----------|
| `BaseStrategyParams` | 공통 파라미터 기반 (initial_capital) | helpers.py |
| `BufferStrategyParams` | 버퍼존 전략 파라미터 | strategies/buffer_zone.py |
| `BuyAndHoldParams` | B&H 파라미터 | strategies/buy_and_hold.py |
| `PendingOrder` | 예약 주문 정보 | helpers.py |

### B. 예외 클래스 (1개)

| 클래스 | 역할 | 분리 대상 |
|--------|------|-----------|
| `PendingOrderConflictError` | Pending 충돌 예외 (Critical Invariant) | helpers.py |

### C. 헬퍼 함수 (9개, 모두 private)

| 함수 | 역할 | 분리 대상 |
|------|------|-----------|
| `_validate_buffer_strategy_inputs()` | 입력 검증 | helpers.py |
| `_compute_bands()` | MA 밴드 계산 | helpers.py |
| `_check_pending_conflict()` | Pending 충돌 검사 | helpers.py |
| `_record_equity()` | Equity 기록 생성 | helpers.py |
| `_execute_buy_order()` | 매수 체결 | helpers.py |
| `_execute_sell_order()` | 매도 체결 | helpers.py |
| `_detect_buy_signal()` | 상향돌파 감지 | helpers.py |
| `_detect_sell_signal()` | 하향돌파 감지 | helpers.py |
| `_calculate_recent_buy_count()` | 최근 매수 횟수 계산 | helpers.py |

### D. 전략 실행 함수 (4개)

| 함수 | 역할 | 분리 대상 |
|------|------|-----------|
| `run_buy_and_hold()` | B&H 전략 실행 | strategies/buy_and_hold.py |
| `run_buffer_strategy()` | 버퍼존 전략 실행 | strategies/buffer_zone.py |
| `run_grid_search()` | 그리드 서치 | strategies/buffer_zone.py |
| `_run_buffer_strategy_for_grid()` | 그리드 워커 | strategies/buffer_zone.py |

### E. 로컬 상수 (3개)

| 상수 | 값 | 분리 대상 |
|------|-----|-----------|
| `DEFAULT_BUFFER_INCREMENT_PER_BUY` | 0.01 | helpers.py |
| `DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY` | 1 | helpers.py |
| `DEFAULT_DAYS_PER_MONTH` | 30 | helpers.py |

---

## 4. 분리 후 디렉토리 구조

### 비즈니스 로직 (src/qbt/backtest/)

```
src/qbt/backtest/
├── __init__.py              # 패키지 공개 API
├── analysis.py              # 변경 없음
├── constants.py             # 변경 없음
├── types.py                 # 변경 없음
├── helpers.py               # [신규] strategy.py에서 공통 헬퍼 추출
│                              BaseStrategyParams, PendingOrder, PendingOrderConflictError,
│                              _compute_bands, _execute_buy_order, _execute_sell_order,
│                              _detect_buy_signal, _detect_sell_signal, _record_equity,
│                              _check_pending_conflict, _calculate_recent_buy_count,
│                              _validate_buffer_strategy_inputs, 동적 조정 상수 3개
│
├── strategies/              # [신규] 전략 파일들 (1 전략 = 1 파일)
│   ├── __init__.py
│   ├── buy_and_hold.py      # BuyAndHoldParams + run_buy_and_hold
│   └── buffer_zone.py       # BufferStrategyParams + run_buffer_strategy + run_grid_search
│
├── strategy.py              # [삭제]
└── CLAUDE.md                # 업데이트
```

### 결과 저장 (storage/results/backtest/)

```
storage/results/backtest/
├── buffer_zone/                    # [신규] 버퍼존 전략 결과
│   ├── signal.csv
│   ├── equity.csv
│   ├── trades.csv
│   ├── summary.json
│   └── grid_results.csv
│
├── buy_and_hold/                   # [신규] Buy & Hold 전략 결과
│   ├── signal.csv
│   ├── equity.csv
│   ├── trades.csv
│   └── summary.json
│
├── single_backtest_*.csv           # [삭제] 기존 결과 (전략별 폴더로 이동)
├── grid_results.csv                # [삭제] 기존 결과 (buffer_zone/ 하위로 이동)
└── meta.json                       # 유지
```

전략 폴더명이 곧 전략 식별자이므로, 폴더 내 파일명은 모든 전략이 동일하다:
`signal.csv`, `equity.csv`, `trades.csv`, `summary.json`

---

## 5. 각 파일 상세

### 5-1. helpers.py (공통 빌딩 블록)

향후 버퍼존 계열 전략들(StopLoss, Trailing 등)이 공유하는 헬퍼를 모은다.

```
포함 목록:
  데이터 클래스:
    - BaseStrategyParams        (모든 전략의 기본)
    - PendingOrder              (예약 주문)

  예외 클래스:
    - PendingOrderConflictError

  함수:
    - _validate_buffer_strategy_inputs()
    - _compute_bands()
    - _check_pending_conflict()
    - _record_equity()
    - _execute_buy_order()
    - _execute_sell_order()
    - _detect_buy_signal()
    - _detect_sell_signal()
    - _calculate_recent_buy_count()

  상수:
    - DEFAULT_BUFFER_INCREMENT_PER_BUY
    - DEFAULT_HOLD_DAYS_INCREMENT_PER_BUY
    - DEFAULT_DAYS_PER_MONTH
```

### 5-2. strategies/buy_and_hold.py

```
포함 목록:
  데이터 클래스:
    - BuyAndHoldParams

  함수:
    - run_buy_and_hold()

  helpers.py 의존: 없음 (완전 독립적)
```

### 5-3. strategies/buffer_zone.py

```
포함 목록:
  데이터 클래스:
    - BufferStrategyParams      (BaseStrategyParams 상속)

  함수:
    - run_buffer_strategy()     (핵심 전략 루프)
    - run_grid_search()         (파라미터 탐색)
    - _run_buffer_strategy_for_grid()  (병렬 워커)

  helpers.py 의존: 대부분의 헬퍼 import
```

### 5-4. 그리드 서치 소유 정책

`run_grid_search()`는 `buffer_zone.py`에 포함한다.
내부에서 `BufferStrategyParams` 조합을 생성하고 `run_buffer_strategy()`를 직접 호출하므로
버퍼존 전략 전용이다.

향후 새 전략이 그리드 서치를 필요로 하면 해당 전략 파일에 자체 구현한다.
전략마다 탐색 파라미터가 다르므로 범용 그리드 서치는 만들지 않는다.

```
buffer_zone:     ma_window, buffer_zone_pct, hold_days, recent_months       (4개)
buffer_stoploss: 위 4개 + stop_loss_pct                                     (5개)
buffer_trailing: 위 4개 + atr_period, atr_multiplier, activate_pct, ...     (7개+)
```

---

## 6. 전략 파일 규약

### 각 전략 파일이 반드시 제공하는 것

1. **Params dataclass**: 전략 고유 파라미터
2. **run() 함수**: 전략 실행 진입점
3. **반환값**: `(signal_df, trades_df, equity_df, summary)` 형식 통일

### 결과 파일 통일 규약

**모든 전략은 동일한 4개 파일을 동일한 형식으로 생성한다.**

| 파일 | 설명 |
|------|------|
| `signal.csv` | 시그널 데이터 (OHLC + MA + 전일대비% 등) |
| `equity.csv` | 에쿼티 곡선 (자산 평가액 + 포지션) |
| `trades.csv` | 거래 내역 |
| `summary.json` | 요약 지표 + 파라미터 |

### 각 파일 필수 컬럼

#### signal.csv

| 컬럼 | 타입 | 필수 | 설명 |
|------|------|------|------|
| Date | date | O | 날짜 |
| Open | float | O | 시가 |
| High | float | O | 고가 |
| Low | float | O | 저가 |
| Close | float | O | 종가 |

전략별로 추가 컬럼 허용 (ma_N, change_pct, upper_band 등).

#### equity.csv

| 컬럼 | 타입 | 필수 | 설명 |
|------|------|------|------|
| Date | date | O | 날짜 |
| equity | float | O | 해당 시점 평가 자산 |
| position | int | O | 보유 수량 |

전략별로 추가 컬럼 허용 (buffer_zone_pct, upper_band, trailing_stop 등).

#### trades.csv

| 컬럼 | 타입 | 필수 | 설명 |
|------|------|------|------|
| entry_date | date | O | 진입일 |
| exit_date | date | O | 청산일 |
| entry_price | float | O | 진입가 |
| exit_price | float | O | 청산가 |
| pnl_pct | float | O | 손익률 (0~1) |

전략별로 추가 컬럼 허용 (shares, pnl, buffer_zone_pct 등).

#### summary.json

| 키 | 타입 | 필수 | 설명 |
|-----|------|------|------|
| strategy | str | O | 전략 식별자 |
| initial_capital | float | O | 초기 자본금 |
| final_capital | float | O | 최종 자본금 |
| total_return_pct | float | O | 총 수익률 (%) |
| cagr | float | O | 연평균 복합 성장률 (%) |
| mdd | float | O | 최대 낙폭 (%) |
| total_trades | int | O | 총 거래 수 |
| winning_trades | int | O | 수익 거래 수 |
| losing_trades | int | O | 손실 거래 수 |
| win_rate | float | O | 승률 (%) |
| start_date | str | O | 시작일 |
| end_date | str | O | 종료일 |

전략별로 추가 키 허용 (ma_window, buffer_zone_pct, params 등).

---

## 7. 영향 범위

하위 호환은 고려하지 않는다.
리팩토링이므로 기존 import 경로가 깨지면 해당 파일을 새 경로로 수정한다.

### 변경 없는 파일

| 파일 | 이유 |
|------|------|
| `analysis.py` | strategy.py를 import하지 않음 |
| `constants.py` | 독립적 |
| `types.py` | 독립적 |

### 변경이 필요한 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backtest/__init__.py` | 새 모듈 경로로 import 변경 |
| `scripts/backtest/run_single_backtest.py` | import 경로 변경 + 결과 저장 경로 변경 |
| `scripts/backtest/run_grid_search.py` | import 경로 변경 + 결과 저장 경로 변경 |
| `scripts/backtest/app_single_backtest.py` | 결과 로딩 경로 변경 |
| `tests/test_strategy.py` | import 경로를 새 위치로 변경 |
| `backtest/CLAUDE.md` | 모듈 구성 문서 업데이트 |
| `common_constants.py` | 결과 경로 상수 변경 (전략별 폴더) |

---

## 8. 결과 동일성 검증 (가장 중요)

리팩토링 전후 백테스트 결과가 **완전히 동일**해야 한다.

### 검증 방법

```
1. 리팩토링 전: 현재 코드로 백테스트 실행, 결과 CSV/JSON 보관
2. 리팩토링 후: 동일 파라미터로 백테스트 실행
3. 비교: equity, trades, summary 값이 소수점까지 일치하는지 확인
```

### 검증 대상

- `single_backtest_equity.csv`: equity, position 값
- `single_backtest_trades.csv`: entry_date, exit_date, entry_price, exit_price, pnl_pct 값
- `single_backtest_summary.json`: CAGR, MDD, 총 수익률, 거래 수 등
- `grid_results.csv`: 모든 파라미터 조합의 결과

로직 변경 없이 순수 구조 분리이므로 결과가 달라질 이유가 없다.
만약 다르다면 분리 과정에서 실수가 있는 것이다.

---

## 9. 향후 새 전략 추가 시 작업 범위

```
새 전략 추가 = 파일 1개만 추가:
  src/qbt/backtest/strategies/새전략.py
    - Params dataclass (BaseStrategyParams 상속)
    - run() 함수
    - (필요 시) 자체 run_grid_search()

  helpers.py에서 공통 함수 import:
    _compute_bands, _execute_buy_order, _execute_sell_order, ...

  기존 코드 변경 없음 (개방-폐쇄 원칙)
```
